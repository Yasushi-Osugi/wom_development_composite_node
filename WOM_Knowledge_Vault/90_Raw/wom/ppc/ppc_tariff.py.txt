"""
wom/ppc/ppc_tariff.py
=====================
Step 3: Tariff & Landed Cost Calculation.

Applies import duty and logistics/insurance on cross-border edges.
Uses FIXED transfer_price from Step 2 (never recomputed here).

Landed cost formula:
    landed_cost = transfer_price + logistics + insurance + tariff

Edge processing order (multi-tier DAD chain):
    1. MOM -> chain[0]      (cross-border: tariff + CIF freight)
    2. chain[0] node costs (e.g. DC_JP_BONDED: customs handling)
    3. chain[0] -> chain[1] inter-DAD edge (domestic transport)
    4. chain[1] node costs (e.g. DC_JP_MAIN: SGA + DC ops)
    ...
    N. chain[-1] -> Channel  (outbound: tariff if cross-border)

cost_phase tagging (Phase 3):
    TARIFF  : import duty (inbound or outbound)
    CIF     : MOM->first_DAD edge logistics/insurance
              + first_DAD node costs when tariff_in_base > 0
                (ocean freight captured as bonded-warehouse node cost)
    DAD     : inter-DAD edge costs + subsequent DAD node costs
              + first_DAD node costs when no tariff (domestic product)
    SGA     : sga_cost at any DAD node
    ""       : landed_cost_total (informational summary event)

mom_node and dad_node accept either str or dict[product_id -> node_id].
dad_nodes_chain: list[str], dict[product_id -> list[str]] (legacy), or
dict[(product_id, channel_node) -> list[str]] (preferred, per-Lot; see
wom-v1r1m7-fix4all_case Coding Request Letter, Problem C+D). MOM-side first.
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Optional, Tuple, Union

from .ppc_models import LotCostAccumulator, PPCEvent
from .ppc_fx import FXConverter
from .ppc_rules import PPCRuleSet


def _resolve_node(node: Union[str, Dict[str, str]], product_id: str) -> str:
    if isinstance(node, dict):
        return node.get(product_id, next(iter(node.values()), ""))
    return node


def _resolve_chain(
    chain: Union[None, List[str], Dict[str, List[str]], Dict[Tuple[str, str], List[str]], str],
    product_id: str,
    channel_node: str,
    fallback_dad: str,
) -> List[str]:
    """Resolve dad_nodes_chain to ordered list; fall back to single dad_node.

    Accepts (checked in this order):
      dict[(product_id, channel_node) -> list]  -- new, per-Lot chain built
        by walking the Lot's actual leaf_out ancestry (see
        wom/model/sc_tree.py's walk_ancestor_chain and Coding Request
        Letter smartx-2027-2029-fix-request-letter.md, Problem C+D).
        Checked first when present, since a given product_id may have
        several parallel DAD branches (e.g. smartx-2027-2029's
        DC_AMER/DC_EMEA/DC_APAC) that must not be conflated into one
        chain shared by every channel.
      dict[product_id -> list]                   -- legacy, per-product flat
        chain (still used by the "cookie"/"iphone_global" named scenarios
        in wom/ppc/ppc_engine.py, which only ever have a single DAD branch
        per product_id so the distinction is moot for them).
      list[str] / str / None                     -- legacy, single value
        shared by every product/channel.
    """
    if isinstance(chain, dict):
        key = (product_id, channel_node)
        if key in chain:
            val = chain[key]
            return val if val else [fallback_dad]
        val = chain.get(product_id, [])
        if isinstance(val, list):
            return val if val else [fallback_dad]
        return [val] if val else [fallback_dad]
    if chain is None:
        return [fallback_dad]
    if isinstance(chain, list):
        return chain if chain else [fallback_dad]
    return [chain] if chain else [fallback_dad]


def run_tariff_and_landed_cost(
    accumulators: List[LotCostAccumulator],
    rules: PPCRuleSet,
    fx: FXConverter,
    sc_paths: Dict[str, List[Tuple[str, str, str]]],
    mom_node: Union[str, Dict[str, str]] = "MOM_China",
    dad_node: Union[str, Dict[str, str]] = "DAD_Japan",
    dad_nodes_chain: Optional[Union[List[str], Dict[str, List[str]]]] = None,
) -> List[PPCEvent]:
    """
    Step 3: Tariff, logistics, DAD node costs for the full DAD chain.

    Walks chain[0] ... chain[-1] in order (MOM-side first, channel-side last).
    For each lot:
      a) MOM -> chain[0] inbound edge (tariff + CIF logistics)
      b) chain[0] node costs
      c) For i=1...N-1: chain[i-1]->chain[i] edge + chain[i] node costs
      d) chain[-1] -> channel outbound edge (+ outbound tariff if any)
    """
    events: List[PPCEvent] = []
    _ctr = itertools.count(1)

    for acc in accumulators:
        product = acc.product_id
        week = acc.week
        channel = acc.channel_node

        m_node = _resolve_node(mom_node, product)
        fallback = _resolve_node(dad_node, product)
        chain = _resolve_chain(dad_nodes_chain, product, channel, fallback)

        first_dad = chain[0]
        last_dad  = chain[-1]

        # ── a) MOM -> first_DAD cross-border edge ──────────────────────
        inbound_edge = f"{m_node}->{first_dad}"

        # a-1) Tariff (MOM->first_DAD)
        tariff_row = rules.get_tariff(inbound_edge, product)
        if tariff_row is not None:
            tariff_rate  = float(tariff_row["tariff_rate"])
            tariff_basis = str(tariff_row["tariff_basis"])

            tp_rule = rules.get_transfer_price_rule(m_node, product)
            actual_tp_currency = str(tp_rule["currency"]) if tp_rule is not None else "JPY"

            if tariff_basis in ("transfer_price", ""):
                basis_local = acc.transfer_price_local
                tp_currency = actual_tp_currency
            elif tariff_basis == "material_cost":
                mom_fx_rate, _ = fx.get_rate(week, actual_tp_currency)
                basis_local = acc.supplier_cost_base / mom_fx_rate if mom_fx_rate else 0.0
                tp_currency = actual_tp_currency
            else:
                basis_local = acc.transfer_price_local
                tp_currency = actual_tp_currency

            tariff_local = basis_local * tariff_rate
            t_fx_rate, tariff_base = fx.convert(tariff_local, tp_currency, week)
            acc.tariff_in_base += tariff_base

            events.append(PPCEvent(
                event_id=f"TAR-{next(_ctr):06d}",
                week=week, lot_id=acc.lot_id, node_id=first_dad,
                edge_id=inbound_edge, product_id=product, qty=int(round(acc.qty)),
                ppc_event_type="tariff_cost",
                amount_local=tariff_local, currency=tp_currency,
                fx_rate=t_fx_rate, amount_base=tariff_base,
                amount_per_unit_base=tariff_base,
                source_rule="ppc_tariff_rule.csv", direction="forward",
                profit_zone=rules.get_profit_zone(first_dad, product),
                cost_phase="TARIFF",
            ))

        # a-2) Inbound logistics + insurance (MOM->first_DAD)
        # NOTE (2026-07-10 fix): logistics_cost here is MOM->DAD freight
        # (e.g. ocean/air freight), a cost borne by the buyer/DAD side under
        # FOB-style terms -- it goes to acc.mom_to_dad_freight_base, NOT
        # acc.logistics_in_base (which is reserved for Supplier->MOM inbound
        # logistics, see ppc_forward.py Step 1b). Mixing the two previously
        # caused ppc_reconcile.py's MOM_PROFIT_TOO_LOW check to incorrectly
        # subtract MOM->DAD freight from MOM's own margin. insurance_cost
        # correctly routes to the (previously unused) insurance_in_base field.
        for _, row in rules.get_edge_costs(inbound_edge, product).iterrows():
            ct = str(row["cost_type"])
            if ct not in ("logistics_cost", "insurance_cost"):
                continue
            e_currency = str(row["currency"])
            if ct == "insurance_cost":
                base_val = acc.transfer_price_local if e_currency == "USD" else acc.transfer_price_base
                e_local = float(row["rate"]) * base_val + float(row["fixed_amount"])
            else:
                e_local = float(row["rate"]) * 1 + float(row["fixed_amount"])
            if e_local == 0:
                continue
            e_fx_rate, e_base = fx.convert(e_local, e_currency, week)
            if ct == "insurance_cost":
                acc.insurance_in_base += e_base
            else:
                acc.mom_to_dad_freight_base += e_base
            events.append(PPCEvent(
                event_id=f"TAR-{next(_ctr):06d}",
                week=week, lot_id=acc.lot_id, node_id=first_dad,
                edge_id=inbound_edge, product_id=product, qty=int(round(acc.qty)),
                ppc_event_type=ct, amount_local=e_local, currency=e_currency,
                fx_rate=e_fx_rate, amount_base=e_base, amount_per_unit_base=e_base,
                source_rule="ppc_edge_cost_rule.csv", direction="forward",
                profit_zone=rules.get_profit_zone(first_dad, product),
                cost_phase="CIF",
            ))

        # a-3) Landed cost informational event (at first_dad)
        landed_base = (
            acc.transfer_price_base + acc.logistics_in_base
            + acc.mom_to_dad_freight_base
            + acc.insurance_in_base + acc.tariff_in_base
        )
        events.append(PPCEvent(
            event_id=f"TAR-{next(_ctr):06d}",
            week=week, lot_id=acc.lot_id, node_id=first_dad,
            edge_id=inbound_edge, product_id=product, qty=int(round(acc.qty)),
            ppc_event_type="landed_cost_total",
            amount_local=landed_base, currency=fx.base_currency, fx_rate=1.0,
            amount_base=landed_base, amount_per_unit_base=landed_base,
            source_rule="computed", direction="forward",
            profit_zone=rules.get_profit_zone(first_dad, product),
            cost_phase="",
        ))

        # ── b/c) Walk ALL DAD nodes: node costs + inter-DAD edges ─────
        # is_import: True when this lot has a cross-border tariff, meaning the
        # first DAD node is a bonded-warehouse / customs point rather than a
        # domestic DC.  In that case first-DAD node costs (ocean freight already
        # captured as DC_JP_BONDED node cost + bonded handling) are tagged "CIF";
        # subsequent DAD costs are tagged "DAD".
        is_import = acc.tariff_in_base > 0

        for i, d in enumerate(chain):
            d_zone = rules.get_profit_zone(d, product)
            # First DAD of an import product -> CIF zone (bonded warehouse / customs)
            # Any other DAD (or first DAD of a domestic product) -> DAD zone
            first_dad_import = (i == 0 and is_import)

            # DAD[i] node costs (logistics, conversion, SGA, warehouse, etc.)
            for _, row in rules.get_node_costs(d, product).iterrows():
                ct = str(row["cost_type"])
                n_currency = str(row["currency"])
                n_local = float(row["rate"]) * 1 + float(row["fixed_amount"])
                n_fx_rate, n_base = fx.convert(n_local, n_currency, week)

                if ct == "sga_cost":
                    acc.dad_sga_base += n_base
                    cp = "SGA"
                else:
                    # logistics_cost, conversion_cost, warehouse_cost
                    acc.warehouse_base += n_base
                    cp = "CIF" if first_dad_import else "DAD"

                events.append(PPCEvent(
                    event_id=f"DAD-{next(_ctr):06d}",
                    week=week, lot_id=acc.lot_id, node_id=d,
                    edge_id="", product_id=product, qty=int(round(acc.qty)),
                    ppc_event_type=ct, amount_local=n_local, currency=n_currency,
                    fx_rate=n_fx_rate, amount_base=n_base, amount_per_unit_base=n_base,
                    source_rule="ppc_node_cost_rule.csv", direction="forward",
                    profit_zone=d_zone,
                    cost_phase=cp,
                ))

            # Inter-DAD edge: chain[i] -> chain[i+1]
            if i + 1 < len(chain):
                next_dad = chain[i + 1]
                inter_edge = f"{d}->{next_dad}"
                next_zone = rules.get_profit_zone(next_dad, product)
                for _, row in rules.get_edge_costs(inter_edge, product).iterrows():
                    ct = str(row["cost_type"])
                    if ct not in ("logistics_cost", "insurance_cost"):
                        continue
                    e_currency = str(row["currency"])
                    e_local = float(row["rate"]) * 1 + float(row["fixed_amount"])
                    if e_local == 0:
                        continue
                    e_fx_rate, e_base = fx.convert(e_local, e_currency, week)
                    # NOTE (2028-07-13 fix, apparel-global-2028-2029): routed to
                    # inter_dad_freight_base, NOT logistics_in_base -- see
                    # LotCostAccumulator.inter_dad_freight_base docstring
                    # (ppc_models.py) for why. This mirrors the mom_to_dad_
                    # freight_base fix above (section a-2) for the same class
                    # of bug, now hit by the inter-DAD leg of a 2+-tier DAD
                    # chain instead of the mom->first_DAD leg.
                    acc.inter_dad_freight_base += e_base
                    events.append(PPCEvent(
                        event_id=f"DAD-{next(_ctr):06d}",
                        week=week, lot_id=acc.lot_id, node_id=next_dad,
                        edge_id=inter_edge, product_id=product, qty=int(round(acc.qty)),
                        ppc_event_type=ct, amount_local=e_local, currency=e_currency,
                        fx_rate=e_fx_rate, amount_base=e_base, amount_per_unit_base=e_base,
                        source_rule="ppc_edge_cost_rule.csv", direction="forward",
                        profit_zone=next_zone,
                        cost_phase="DAD",
                    ))

        # ── d) last_DAD -> Channel outbound edge ───────────────────────
        outbound_edge = f"{last_dad}->{channel}"
        out_profit_zone = rules.get_profit_zone(channel, product)

        for _, row in rules.get_edge_costs(outbound_edge, product).iterrows():
            ct = str(row["cost_type"])
            e_currency = str(row["currency"])
            e_local = float(row["rate"]) * 1 + float(row["fixed_amount"])
            e_fx_rate, e_base = fx.convert(e_local, e_currency, week)
            acc.logistics_out_base += e_base
            events.append(PPCEvent(
                event_id=f"OUT-{next(_ctr):06d}",
                week=week, lot_id=acc.lot_id, node_id=channel,
                edge_id=outbound_edge, product_id=product, qty=int(round(acc.qty)),
                ppc_event_type=ct, amount_local=e_local, currency=e_currency,
                fx_rate=e_fx_rate, amount_base=e_base, amount_per_unit_base=e_base,
                source_rule="ppc_edge_cost_rule.csv", direction="forward",
                profit_zone=out_profit_zone,
                cost_phase="DAD",
            ))

        out_tariff_row = rules.get_tariff(outbound_edge, product)
        if out_tariff_row is not None:
            t_rate = float(out_tariff_row["tariff_rate"])
            basis_local = acc.transfer_price_local
            t_currency = "USD"
            t_local = basis_local * t_rate
            t_fx_rate, t_base = fx.convert(t_local, t_currency, week)
            acc.tariff_out_base += t_base
            events.append(PPCEvent(
                event_id=f"OUT-{next(_ctr):06d}",
                week=week, lot_id=acc.lot_id, node_id=channel,
                edge_id=outbound_edge, product_id=product, qty=int(round(acc.qty)),
                ppc_event_type="tariff_cost", amount_local=t_local, currency=t_currency,
                fx_rate=t_fx_rate, amount_base=t_base, amount_per_unit_base=t_base,
                source_rule="ppc_tariff_rule.csv", direction="forward",
                profit_zone=out_profit_zone,
                cost_phase="TARIFF",
            ))

    return events
