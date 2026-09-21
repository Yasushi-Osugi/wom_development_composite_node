"""
wom/engine/sc_tree_to_df.py
────────────────────────────
Convert a fully-planned SCTree (lot-based) into a quantity-based DataFrame
that is structurally identical to the output of wom/engine/inventory.py.

This is the bridge between the Planning Engine (Step 3-11) and the
Management Layer (money.py / management.py / KPI charts).

Lot → Quantity conversion:
    quantity = len(psi4supply[w][bucket]) × sc_tree.cpu_size × node.bom_qty
    (cpu_size is a plan-wide value, not per-node -- Request Letter A:
    request_letter_a_cpu_size_to_plan.md. bom_qty is per-node, default 1 --
    Letter B: request_letter_b_bom_qty.md. Neither ever touches the Lot_ID
    list itself, only this display-layer conversion.)

Output columns (match inventory.py rows exactly):
    scenario, sku_id, region, week,
    opening_inv, supply_receipt, gross_avail,
    demand_fcst, demand_fulfilled, stockout_qty,
    closing_inv, safety_stock_qty, reorder_qty,
    fill_rate, inv_cover_wks, inv_value (0.0 — filled by simulator later)

Usage
-----
    from wom.engine.sc_tree_to_df import sc_tree_to_planning_df
    df = sc_tree_to_planning_df(sc_tree, scenario_name="Planning")
    scenario_manager.add("Planning", df)
"""

from __future__ import annotations
import pandas as pd
from wom.data.schema import Cols
from wom.model.plan_node import S, CO, I, P as P_, NODE_TYPE_DAD


SCENARIO_PLANNING = "Planning"


def sc_tree_to_planning_df(
    sc_tree,
    scenario_name: str = SCENARIO_PLANNING,
    cpu_size_default: int = 1,
) -> pd.DataFrame:
    """
    Convert SCTree lot-PSI data to a quantity DataFrame.

    Parameters
    ----------
    sc_tree : SCTree
        Fully-planned SCTree (BackwardPlanner + ForwardPlanner completed).
    scenario_name : str
        Value written to the ``scenario`` column (default "Planning").
    cpu_size_default : int
        Unused (Request Letter A: request_letter_a_cpu_size_to_plan.md).
        cpu_size is now a plan-wide value read from ``sc_tree.cpu_size``
        (always present, default 1 -- see SCTree.__init__), not a per-node
        attribute, so there is nothing left for this parameter to fall back
        for. Kept only for call-signature compatibility.

    Returns
    -------
    pd.DataFrame
        One row per (sku_id, region, week) with standard PSI columns.
    """
    rows = []
    weeks = sc_tree.week_labels

    for prod_nm in sc_tree.products:
        # ── Collect OutBound leaf_out nodes (one per region) ──────────
        try:
            ot_root = sc_tree.get_ot_root(prod_nm)
            leaf_outs = [nd for nd in ot_root.walk_preorder()
                         if not nd.children]
        except Exception:
            continue

        for leaf in leaf_outs:
            # Derive region from node_id: "OUT:Sales:{region}:{sku}"
            parts  = leaf.node_id.split(":")
            region = parts[2] if len(parts) >= 4 else "?"
            cpu    = sc_tree.cpu_size * leaf.bom_qty

            prev_closing = 0.0

            for w, wk_label in enumerate(weeks):
                d_psi  = leaf.psi4demand[w]
                s_psi  = leaf.psi4supply[w]

                demand_fcst      = len(d_psi[S]) * cpu
                demand_fulfilled = len(s_psi[S]) * cpu
                stockout_qty     = max(0.0, demand_fcst - demand_fulfilled)
                closing_inv      = len(s_psi[I]) * cpu
                supply_receipt   = len(s_psi[P_]) * cpu
                co_qty           = len(s_psi[CO]) * cpu

                opening_inv  = prev_closing
                gross_avail  = opening_inv + supply_receipt
                fill_rate    = (demand_fulfilled / demand_fcst
                                if demand_fcst > 0 else 1.0)
                # Inventory cover: closing / avg weekly demand
                avg_demand   = demand_fcst or 1.0
                inv_cover    = min(closing_inv / avg_demand, 999.0)

                rows.append({
                    Cols.SCENARIO:         scenario_name,
                    Cols.SKU_ID:           prod_nm,
                    Cols.REGION:           region,
                    Cols.WEEK:             wk_label,
                    Cols.OPENING_INV:      round(opening_inv,  4),
                    Cols.SUPPLY_RECEIPT:   round(supply_receipt, 4),
                    Cols.GROSS_AVAIL:      round(gross_avail,  4),
                    Cols.DEMAND_FCST:      round(demand_fcst,  4),
                    Cols.DEMAND_FULFILLED: round(demand_fulfilled, 4),
                    Cols.STOCKOUT_QTY:     round(stockout_qty, 4),
                    Cols.CLOSING_INV:      round(closing_inv,  4),
                    Cols.SAFETY_STOCK_QTY: 0.0,
                    Cols.REORDER_QTY:      round(supply_receipt, 4),
                    Cols.FILL_RATE:        round(fill_rate,    4),
                    Cols.INV_COVER_WKS:    round(inv_cover,    2),
                    Cols.INV_VALUE:        0.0,   # filled by caller with unit_cost
                    # Extra Planning-specific columns
                    "co_qty":              round(co_qty, 4),
                })

                prev_closing = closing_inv

    # ── v1r0m2: DAD nodes (DC / 流通在庫) ────────────────────────────
    # Include DAD inventory so that 販社在庫日数 appears in the KPI DataFrame.
    # Region key is prefixed with "DAD:" to distinguish from leaf_out rows.
    for prod_nm in sc_tree.products:
        try:
            ot_root = sc_tree.get_ot_root(prod_nm)
            dad_nodes = [nd for nd in ot_root.walk_preorder()
                         if nd.node_type == NODE_TYPE_DAD]
        except Exception:
            continue

        for dad in dad_nodes:
            # Derive region from node_id e.g. "OUT:DC:JP:SKU-A" -> "JP"
            parts  = dad.node_id.split(":")
            region = parts[2] if len(parts) >= 4 else dad.node_name
            cpu    = sc_tree.cpu_size * dad.bom_qty

            prev_closing = 0.0

            for w, wk_label in enumerate(weeks):
                d_psi = dad.psi4demand[w]
                s_psi = dad.psi4supply[w]

                demand_fcst      = len(d_psi[S]) * cpu
                demand_fulfilled = len(s_psi[S]) * cpu
                stockout_qty     = max(0.0, demand_fcst - demand_fulfilled)
                closing_inv      = len(s_psi[I]) * cpu
                supply_receipt   = len(s_psi[P_]) * cpu
                co_qty           = len(s_psi[CO]) * cpu

                opening_inv  = prev_closing
                gross_avail  = opening_inv + supply_receipt
                fill_rate    = (demand_fulfilled / demand_fcst
                                if demand_fcst > 0 else 1.0)
                avg_demand   = demand_fcst or 1.0
                inv_cover    = min(closing_inv / avg_demand, 999.0)

                rows.append({
                    Cols.SCENARIO:         scenario_name,
                    Cols.SKU_ID:           prod_nm,
                    Cols.REGION:           f"DAD:{region}",
                    Cols.WEEK:             wk_label,
                    Cols.OPENING_INV:      round(opening_inv,  4),
                    Cols.SUPPLY_RECEIPT:   round(supply_receipt, 4),
                    Cols.GROSS_AVAIL:      round(gross_avail,  4),
                    Cols.DEMAND_FCST:      round(demand_fcst,  4),
                    Cols.DEMAND_FULFILLED: round(demand_fulfilled, 4),
                    Cols.STOCKOUT_QTY:     round(stockout_qty, 4),
                    Cols.CLOSING_INV:      round(closing_inv,  4),
                    Cols.SAFETY_STOCK_QTY: 0.0,
                    Cols.REORDER_QTY:      round(supply_receipt, 4),
                    Cols.FILL_RATE:        round(fill_rate,    4),
                    Cols.INV_COVER_WKS:    round(inv_cover,    2),
                    Cols.INV_VALUE:        0.0,
                    "co_qty":              round(co_qty, 4),
                })

                prev_closing = closing_inv

    df = pd.DataFrame(rows)
    return df


def apply_inv_value(df: pd.DataFrame, sku_master: pd.DataFrame) -> pd.DataFrame:
    """
    Fill the inv_value column using unit_cost from sku_master.

    Modifies df in-place and returns it.
    """
    if sku_master is None or sku_master.empty:
        return df
    cost_map = {}
    for _, row in sku_master.iterrows():
        sku  = str(row.get(Cols.SKU_ID, ""))
        cost = float(row.get(Cols.UNIT_COST, 0.0) or 0.0)
        cost_map[sku] = cost

    df[Cols.INV_VALUE] = df.apply(
        lambda r: r[Cols.CLOSING_INV] * cost_map.get(str(r[Cols.SKU_ID]), 0.0),
        axis=1,
    )
    return df
