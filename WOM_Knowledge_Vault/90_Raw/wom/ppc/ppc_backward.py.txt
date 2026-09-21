"""
wom/ppc/ppc_backward.py
=======================
Step 5: Market Requesting Price Backward Propagation (Lot-based).

mom_node / dad_node accept str or dict[product_id -> node_id].
dad_nodes_chain accepts an ordered list (MOM-side first, channel-side last)
or dict[product_id -> list[str]] for multi-tier DC chains such as:
  [DC_Import_Buffer, DC_Import_Main]  (Cookie_Import import chain)
  [DC_Local_JP]                       (Cookie_Local domestic chain)

Costs are accumulated correctly at EVERY node/edge in the chain,
so SGA at DC_JP_MAIN is no longer ignored.
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Optional, Tuple, Union

from .ppc_models import LotCostAccumulator, PPCEvent
from .ppc_fx import FXConverter
from .ppc_rules import PPCRuleSet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_node(node: Union[str, Dict[str, str]], product_id: str) -> str:
    if isinstance(node, dict):
        return node.get(product_id, next(iter(node.values()), ""))
    return node


def _resolve_node_list(
    chain: Union[None, List[str], Dict[str, List[str]], Dict[Tuple[str, str], List[str]], str, Dict[str, str]],
    product_id: str,
    channel_node: str,
) -> List[str]:
    """Resolve dad_nodes_chain to an ordered list for a specific product/channel.

    Accepts (checked in this order):
      dict[(product_id, channel_node) -> list]  -> preferred, per-Lot chain
        (see wom/model/sc_tree.py's walk_ancestor_chain and Coding Request
        Letter smartx-2027-2029-fix-request-letter.md, Problem C+D)
      None            -> []   (caller must fall back to single dad_node)
      list[str]       -> as-is
      dict[str,list]  -> chain[product_id]   (legacy, per-product flat)
      str             -> [str]   (single-node legacy)
      dict[str,str]   -> [chain[product_id]]  (single-node legacy dict)
    """
    if isinstance(chain, dict):
        key = (product_id, channel_node)
        if key in chain:
            val = chain[key]
            return val if isinstance(val, list) else ([val] if val else [])
        val = chain.get(product_id, [])
        if isinstance(val, list):
            return val
        return [val] if val else []
    if chain is None:
        return []
    if isinstance(chain, list):
        return chain
    return [chain] if chain else []


def _node_costs_base(
    node_id: str,
    product: str,
    week: str,
    market_price_local: float,
    rules: PPCRuleSet,
    fx: FXConverter,
) -> float:
    """Sum all node costs for (node_id, product) → base currency."""
    total = 0.0
    for _, row in rules.get_node_costs(node_id, product).iterrows():
        basis = str(row["basis"])
        rate  = float(row["rate"])
        fixed = float(row["fixed_amount"])
        cur   = str(row["currency"])
        if basis == "revenue":
            c_local = rate * market_price_local + fixed
        elif basis == "qty":
            c_local = rate * 1 + fixed
        else:          # per_lot / fixed
            c_local = fixed
        _, c_base = fx.convert(c_local, cur, week)
        total += c_base
    return total


def _edge_costs_base(
    edge_id: str,
    product: str,
    week: str,
    transfer_price_local: float,
    transfer_price_base: float,
    rules: PPCRuleSet,
    fx: FXConverter,
) -> float:
    """Sum all edge costs for edge_id → base currency."""
    total = 0.0
    for _, row in rules.get_edge_costs(edge_id, product).iterrows():
        ct  = str(row["cost_type"])
        cur = str(row["currency"])
        if ct == "insurance_cost":
            base_val = transfer_price_local if cur == "USD" else transfer_price_base
            e_local  = float(row["rate"]) * base_val + float(row["fixed_amount"])
        else:
            e_local  = float(row["rate"]) * 1 + float(row["fixed_amount"])
        _, e_base = fx.convert(e_local, cur, week)
        total += e_base
    return total


def _tariff_base(
    edge_id: str,
    product: str,
    week: str,
    transfer_price_local: float,
    rules: PPCRuleSet,
    fx: FXConverter,
    tp_currency: str = "USD",
) -> float:
    """Compute tariff on edge_id → base currency (0 if no rule).

    tp_currency must match the transfer-price currency used in ppc_tariff.py
    (e.g. "JPY" for Cookie-jp-2026, "USD" for iphone).
    Defaults to "USD" for backward-compatibility with existing unit tests.
    """
    t = rules.get_tariff(edge_id, product)
    if t is None:
        return 0.0
    t_local = transfer_price_local * float(t["tariff_rate"])
    _, t_base = fx.convert(t_local, tp_currency, week)
    return t_base


# ---------------------------------------------------------------------------
# Main backward propagation
# ---------------------------------------------------------------------------

def run_backward_propagation(
    accumulators: List[LotCostAccumulator],
    rules: PPCRuleSet,
    fx: FXConverter,
    sc_paths: Dict[str, List[Tuple[str, str, str]]],
    mom_node: Union[str, Dict[str, str]] = "MOM_China",
    dad_node: Union[str, Dict[str, str]] = "DAD_Japan",
    dad_nodes_chain: Union[None, List[str], Dict[str, List[str]]] = None,
) -> List[PPCEvent]:
    """
    Step 5: Lot-based backward requesting price propagation.

    Walks the full OutBound cost chain from channel back to MOM:

      market_price
        - channel node costs  (SGA at leaf_out)
        - last_dad → channel edge costs
        - last_dad node costs  (SGA / DC ops / logistics at last DAD)
        - (intermediate dad-to-dad edge costs)
        - (intermediate dad node costs)
        - first_dad node costs
        - mom → first_dad inbound edge costs  (CIF freight, insurance)
        - mom → first_dad inbound tariff
      = backward_allowable @ MOM

    If dad_nodes_chain is None or empty, falls back to single dad_node
    (legacy rice / iphone behavior unchanged).
    """
    events: List[PPCEvent] = []
    _ctr = itertools.count(1)

    for acc in accumulators:
        product = acc.product_id
        week    = acc.week
        channel = acc.channel_node

        m_node = _resolve_node(mom_node, product)

        # Resolve transfer-price currency so inbound tariff matches forward Step 3
        tp_rule = rules.get_transfer_price_rule(m_node, product)
        tp_currency = str(tp_rule["currency"]) if tp_rule is not None else "USD"

        # Build ordered DAD chain (MOM-side first, channel-side last)
        chain = _resolve_node_list(dad_nodes_chain, product, channel)
        if not chain:
            chain = [_resolve_node(dad_node, product)]  # legacy single-DAD

        last_dad  = chain[-1]

        # ── Market price ───────────────────────────────────────────────
        market_price_local, market_currency = rules.get_market_price(
            channel, product, week
        )
        _, market_base = fx.convert(market_price_local, market_currency, week)
        allowable = market_base

        # ── 1. Channel (leaf_out) node costs ──────────────────────────
        allowable -= _node_costs_base(
            channel, product, week, market_price_local, rules, fx
        )

        # ── 2. last_dad → channel outbound edge + tariff ──────────────
        outbound_edge = f"{last_dad}->{channel}"
        allowable -= _edge_costs_base(
            outbound_edge, product, week,
            acc.transfer_price_local, acc.transfer_price_base, rules, fx,
        )
        allowable -= _tariff_base(
            outbound_edge, product, week,
            acc.transfer_price_local, rules, fx,
        )

        # ── 3. Walk DAD chain from channel-side back to MOM-side ──────
        #   For each DAD i (from last to first):
        #     a. Subtract this DAD's node costs
        #     b. Subtract edge from prev_dad (or MOM) to this DAD
        #        + inbound tariff on MOM → first_dad edge
        for i in range(len(chain) - 1, -1, -1):
            d = chain[i]

            # 3a. DAD node costs (SGA, DC ops, logistics, etc.)
            allowable -= _node_costs_base(
                d, product, week, market_price_local, rules, fx
            )

            # 3b. Edge from upstream node to this DAD
            if i > 0:
                upstream = chain[i - 1]
                edge = f"{upstream}->{d}"
                allowable -= _edge_costs_base(
                    edge, product, week,
                    acc.transfer_price_local, acc.transfer_price_base,
                    rules, fx,
                )
                # No tariff on inter-DAD domestic edges
            else:
                # First DAD: inbound from MOM (freight + tariff)
                inbound_edge = f"{m_node}->{d}"
                allowable -= _edge_costs_base(
                    inbound_edge, product, week,
                    acc.transfer_price_local, acc.transfer_price_base,
                    rules, fx,
                )
                allowable -= _tariff_base(
                    inbound_edge, product, week,
                    acc.transfer_price_local, rules, fx,
                    tp_currency=tp_currency,
                )

        # ── Store result ───────────────────────────────────────────────
        acc.backward_allowable_base = allowable

        backward_zone = rules.get_profit_zone(m_node, product)
        events.append(PPCEvent(
            event_id=f"BWD-{next(_ctr):06d}",
            week=week,
            lot_id=acc.lot_id,
            node_id=m_node,
            edge_id="",
            product_id=product,
            qty=int(round(acc.qty)),
            ppc_event_type="backward_allowable",
            amount_local=allowable,
            currency=fx.base_currency,
            fx_rate=1.0,
            amount_base=allowable,
            amount_per_unit_base=allowable,
            source_rule="computed:market_price - downstream_costs",
            direction="backward",
            profit_zone=backward_zone,
        ))

    return events
