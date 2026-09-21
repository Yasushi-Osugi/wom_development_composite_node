"""
wom/ppc/ppc_forward.py
=======================
Step 1: Supplier Offering Cost Forward Propagation.

Walks the supply chain path from Supplier -> MOM, accumulating costs
per lot. Generates PPCEvents for each cost item.

Design:
    - Input: LotCostAccumulator list (lot_id, week, channel)
    - Output: PPCEvent list (supplier_cost, conversion_cost events)
    - transfer_price is NOT set here (see ppc_transfer.py, Step 2)
    - Inbound edge logistics/insurance added here (before tariff)

Node parameters (supplier_node, mom_node) accept either str or
dict[product_id -> node_id] for multi-product models.
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Optional, Tuple, Union

from .ppc_models import LotCostAccumulator, PPCEvent
from .ppc_fx import FXConverter
from .ppc_rules import PPCRuleSet


def _resolve_node(node: Union[str, Dict[str, str]], product_id: str) -> str:
    """Resolve node name: accepts str or dict[product_id -> node_id]."""
    if isinstance(node, dict):
        return node.get(product_id, next(iter(node.values()), ""))
    return node


def _resolve_node_list(
    node: Union[str, List[str], Dict[str, str], Dict[str, List[str]]],
    product_id: str,
) -> List[str]:
    """Resolve supplier_node to an ordered list of node_ids for a product.

    Accepts (in order of precedence):
      dict[str, list]  -> node[product_id]                (multi-supplier, per product)
      dict[str, str]   -> [node[product_id]]               (single-supplier, per product; legacy)
      list[str]        -> node                              (multi-supplier, same for all products)
      str              -> [node]                             (single-supplier; legacy default)
    Falls back to the first available product's value if product_id is missing,
    matching the legacy _resolve_node behavior.
    """
    if isinstance(node, dict):
        val = node.get(product_id, next(iter(node.values()), []))
        if isinstance(val, list):
            return val
        return [val] if val else []
    if isinstance(node, list):
        return node
    return [node] if node else []


def run_forward_propagation(
    accumulators: List[LotCostAccumulator],
    rules: PPCRuleSet,
    fx: FXConverter,
    sc_paths: Dict[str, List[Tuple[str, str, str]]],
    mom_node: Union[str, Dict[str, str]] = "MOM_China",
    supplier_node: Union[str, List[str], Dict[str, str], Dict[str, List[str]]] = "Supplier_CN",
    mom_nodes_chain: Optional[Dict[Tuple[str, str], List[str]]] = None,
    bom_qty_map: Optional[Dict[Tuple[str, str], int]] = None,
) -> List[PPCEvent]:
    """
    Step 1: Forward cost accumulation from Supplier(s) -> MOM.

    Parameters
    ----------
    accumulators  : mutable list; updates supplier_cost_base, conversion_cost_base, etc.
    rules         : PPCRuleSet
    fx            : FXConverter
    sc_paths      : channel_node -> [(node_id, edge_id, country), ...]
                    in supply-chain order (Supplier first, market channel last)
    mom_node      : MOM node_id string OR dict[product_id -> node_id]
    supplier_node : leaf_in (Supplier) node_id(s). Accepts a single string,
                    a list[str] (multiple Tier-1 suppliers feeding one MOM,
                    e.g. Battery/Motor/ECU), dict[product_id -> node_id], or
                    dict[product_id -> list[str]]. Every resolved supplier
                    node contributes its own supplier_cost event (so per-node
                    P&L can attribute cost to each Tier-1 supplier correctly)
                    and all of them are summed into acc.supplier_cost_base.
    mom_nodes_chain : dict[(product_id, leaf_in_node) -> list[str]], optional.
                    Ordered, leaf-side-first list of intermediate "mom"-type
                    ancestor nodes between a given leaf_in supplier and the
                    terminal mom_node (see wom/model/sc_tree.py's
                    walk_ancestor_chain, and Coding Request Letter
                    smartx-2027-2029-fix-request-letter.md Problem B).
                    Missing/empty entries fall back to the original
                    single-hop supplier_node->mom_node behavior, so this
                    parameter is fully backward-compatible: every existing
                    single-tier InBound scenario produces events identical
                    to before this parameter was introduced.
                    Each intermediate tier node contributes ONLY its own
                    ppc_node_cost_rule.csv entries (conversion_cost /
                    logistics_cost) -- never a ppc_supplier_cost.csv entry
                    (reserved for leaf_in nodes), keeping the accounting
                    rule uniform across every "mom"-type node regardless of
                    tier depth, including the terminal mom_node (Step 1c).
    bom_qty_map   : dict[(product_id, node_id), int], optional (Letter B:
                    request_letter_b_bom_qty.md, "1 set rule"). Scales ONLY
                    the Step 1a supplier_cost line for that supplier node --
                    ppc_supplier_cost.csv prices are per PHYSICAL COMPONENT
                    UNIT (e.g. $/tyre), so a vehicle needing 4 tyres must see
                    4x that price. Deliberately NOT applied to Step 1b (edge
                    logistics_cost) or Step 1c (terminal MOM's own node
                    costs): ppc_edge_cost_rule.csv / ppc_node_cost_rule.csv
                    rates are already per FINAL ASSEMBLED UNIT (see their
                    `* 1` literal below, not `* qty`), so multiplying them by
                    bom_qty again would double-count -- freight for "the
                    tyres" and assembly labor for "the vehicle" do not scale
                    with how many tyres one vehicle happens to need. Missing
                    entries (or bom_qty_map=None) default to 1, so every
                    existing model -- none of which set bom_qty -- produces
                    events identical to before this parameter was introduced.
                    (product_id, node_id) assumes a tree, not a DAG: every
                    node has exactly one parent, confirmed across all 16
                    tracked sample models before this parameter was added.

                    Step 1b convention confirmed empirically (owner review,
                    Letter B step (1) revision) against 3 sample models:
                      - soysauce-jpy-2027 Materials_JP->Brewing_Noda: the
                        ONLY existing ppc_edge_cost_rule.csv row for an
                        inbound (supplier->MOM) edge in the whole repo.
                        $0.3/lot -- read in context as "cost to move the
                        materials for ONE finished case", not "$/kg of
                        soybean". Single supplier, no BOM multiplicity, but
                        the rate is denominated per finished lot.
                      - apparel-us-2026 Fabric_CN->Factory_Import_CN: no
                        ppc_edge_cost_rule.csv row exists for this edge at
                        all. Fabric_CN's own ppc_supplier_cost.csv price is
                        $0 -- fabric cost is folded entirely into
                        Factory_Import_CN's own conversion_cost ("CIF価格
                        （生地込み）" = CIF price INCLUDING the fabric, i.e.
                        per finished garment lot, in ppc_node_cost_rule.csv).
                      - ev-europe-2026 Battery/Motor/ECU->Factory_Import_HU:
                        no ppc_edge_cost_rule.csv row exists for these edges
                        either (the only edge_cost_rule rows in that model
                        are the OUTBOUND Factory->SP->DC legs, downstream of
                        the MOM -- irrelevant to Step 1b's inbound walk).
                        Component freight is not modeled as a separate line
                        at all; ppc_supplier_cost.csv's per-piece purchase
                        price (correctly bom_qty-scaled in Step 1a) is the
                        only cost carried for each of the 3 Tier-1 parts.
                    No existing model populates an inbound edge cost for a
                    genuine multi-BOM supplier set, so this is "no
                    counter-evidence + one supportive precedent" rather than
                    an exhaustive proof -- but combined with the structural
                    fact that ppc_edge_cost_rule.csv uses the identical
                    basis="per_lot" / `rate * 1 + fixed_amount` convention as
                    ppc_node_cost_rule.csv (Step 1c, unambiguously "per
                    finished unit" per the apparel CIF note above), the
                    evidence is consistent: edge costs in this codebase are
                    denominated per finished/assembled lot, not per physical
                    component piece -- confirming Step 1b stays untouched.

    Returns
    -------
    List of PPCEvent (forward direction)
    """
    events: List[PPCEvent] = []
    _event_counter = itertools.count(1)

    for acc in accumulators:
        channel = acc.channel_node
        product = acc.product_id
        week = acc.week

        s_nodes = _resolve_node_list(supplier_node, product)
        m_node = _resolve_node(mom_node, product)

        # ── Step 1a: Supplier purchase cost (one or more Tier-1 suppliers) ──
        for s_node in s_nodes:
            price_local, currency = rules.get_supplier_cost(s_node, product, week)
            # Letter B (request_letter_b_bom_qty.md): ppc_supplier_cost.csv is
            # priced per PHYSICAL COMPONENT UNIT (e.g. $/tyre), not per parent
            # unit -- see this function's bom_qty_map docstring. Scaling here,
            # before the fx conversion, means amount_local/amount_base already
            # represent "cost of bom_qty units of this component" so the
            # ledger reads directly as "this many pieces at this rate", and
            # the existing acc.qty multiplication downstream (ppc_kpi.py)
            # needs no changes at all.
            bom = bom_qty_map.get((product, s_node), 1) if bom_qty_map else 1
            price_local *= bom
            fx_rate, price_base = fx.convert(price_local, currency, week)

            acc.supplier_cost_base += price_base
            profit_zone = rules.get_profit_zone(s_node, product)

            events.append(PPCEvent(
                event_id=f"FWD-{next(_event_counter):06d}",
                week=week,
                lot_id=acc.lot_id,
                node_id=s_node,
                edge_id="",
                product_id=product,
                qty=int(round(acc.qty)),
                ppc_event_type="supplier_cost",
                amount_local=price_local,
                currency=currency,
                fx_rate=fx_rate,
                amount_base=price_base,
                amount_per_unit_base=price_base,
                source_rule="ppc_supplier_cost.csv",
                direction="forward",
                profit_zone=profit_zone,
                cost_phase="EXW",
            ))

            # ── Step 1b: Walk the InBound tier chain from this Supplier to MOM ──
            # tier_path = [intermediate mom-type ancestors..., m_node], leaf
            # -side-first. When mom_nodes_chain has no entry for (product,
            # s_node) -- the common single-tier case -- tier_path == [m_node]
            # and this loop reduces to exactly the original single-hop
            # s_node->m_node edge lookup (byte-identical events to before
            # this fix).
            tier_chain: List[str] = []
            if mom_nodes_chain is not None:
                tier_chain = mom_nodes_chain.get((product, s_node), [])
            tier_path = tier_chain + [m_node]

            hop_from = s_node
            for tier_node in tier_path:
                inbound_edge = f"{hop_from}->{tier_node}"
                for _, row in rules.get_edge_costs(inbound_edge, product).iterrows():
                    if row["cost_type"] == "logistics_cost":
                        e_amount_local = float(row["rate"]) * 1 + float(row["fixed_amount"])
                        e_currency = str(row["currency"])
                        if e_amount_local == 0:
                            continue
                        e_fx_rate, e_amount_base = fx.convert(e_amount_local, e_currency, week)
                        acc.logistics_in_base += e_amount_base
                        events.append(PPCEvent(
                            event_id=f"FWD-{next(_event_counter):06d}",
                            week=week,
                            lot_id=acc.lot_id,
                            node_id=tier_node,
                            edge_id=inbound_edge,
                            product_id=product,
                            qty=int(round(acc.qty)),
                            ppc_event_type="logistics_cost",
                            amount_local=e_amount_local,
                            currency=e_currency,
                            fx_rate=e_fx_rate,
                            amount_base=e_amount_base,
                            amount_per_unit_base=e_amount_base,
                            source_rule="ppc_edge_cost_rule.csv",
                            direction="forward",
                            profit_zone=rules.get_profit_zone(tier_node, product),
                            cost_phase="FOB",
                        ))

                # Intermediate tier's own node costs (conversion_cost /
                # logistics_cost from ppc_node_cost_rule.csv only -- see
                # docstring). The terminal m_node is deliberately skipped
                # here to avoid double-counting: its own node costs are
                # applied once, below, by the existing Step 1c block.
                if tier_node != m_node:
                    tier_zone = rules.get_profit_zone(tier_node, product)
                    for _, row in rules.get_node_costs(tier_node, product).iterrows():
                        cost_type = row["cost_type"]
                        if cost_type not in ("conversion_cost", "logistics_cost"):
                            continue
                        c_local = float(row["rate"]) * 1 + float(row["fixed_amount"])
                        c_currency = str(row["currency"])
                        if c_local == 0:
                            continue
                        c_fx_rate, c_base = fx.convert(c_local, c_currency, week)
                        if cost_type == "conversion_cost":
                            acc.conversion_cost_base += c_base
                            ev_type  = "conversion_cost"
                            ev_phase = "MOM"
                        else:
                            acc.logistics_in_base += c_base
                            ev_type  = "logistics_cost"
                            ev_phase = "FOB"
                        events.append(PPCEvent(
                            event_id=f"FWD-{next(_event_counter):06d}",
                            week=week,
                            lot_id=acc.lot_id,
                            node_id=tier_node,
                            edge_id="",
                            product_id=product,
                            qty=int(round(acc.qty)),
                            ppc_event_type=ev_type,
                            amount_local=c_local,
                            currency=c_currency,
                            fx_rate=c_fx_rate,
                            amount_base=c_base,
                            amount_per_unit_base=c_base,
                            source_rule="ppc_node_cost_rule.csv",
                            direction="forward",
                            profit_zone=tier_zone,
                            cost_phase=ev_phase,
                        ))

                hop_from = tier_node

        # ── Step 1c: MOM node costs (conversion + logistics) ─────────
        mom_profit_zone = rules.get_profit_zone(m_node, product)
        for _, row in rules.get_node_costs(m_node, product).iterrows():
            cost_type = row["cost_type"]
            if cost_type not in ("conversion_cost", "logistics_cost"):
                continue
            c_local = float(row["rate"]) * 1 + float(row["fixed_amount"])
            c_currency = str(row["currency"])
            if c_local == 0:
                continue
            c_fx_rate, c_base = fx.convert(c_local, c_currency, week)
            if cost_type == "conversion_cost":
                acc.conversion_cost_base += c_base
                ev_type   = "conversion_cost"
                ev_phase  = "MOM"
            else:
                # logistics_cost at MOM node = domestic transport to export port (FOB)
                acc.logistics_in_base += c_base
                ev_type   = "logistics_cost"
                ev_phase  = "FOB"
            events.append(PPCEvent(
                event_id=f"FWD-{next(_event_counter):06d}",
                week=week,
                lot_id=acc.lot_id,
                node_id=m_node,
                edge_id="",
                product_id=product,
                qty=int(round(acc.qty)),
                ppc_event_type=ev_type,
                amount_local=c_local,
                currency=c_currency,
                fx_rate=c_fx_rate,
                amount_base=c_base,
                amount_per_unit_base=c_base,
                source_rule="ppc_node_cost_rule.csv",
                direction="forward",
                profit_zone=mom_profit_zone,
                cost_phase=ev_phase,
            ))

    return events
