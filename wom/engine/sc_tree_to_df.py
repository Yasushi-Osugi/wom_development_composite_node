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
Extra Planning columns: co_qty, ship_qty, qty_basis, request_qty, on_time_qty,
co_end_qty.

Request vs actual shipment (RequestLetter_iPhoneWarmup_EVUpdateKitting_S2 C2)
----------------------------------------------------------------------------
Supply S is the REQUEST placed at the node (Demand Position); the actual
shipment is node._actual_ship (set by ForwardPlanner.run). Which of the two the
evaluation columns use is decided by the lot flow mode, passed explicitly
(``lot_flow_mode=``) or read from ``sc_tree.lot_flow_mode`` (set by the planning
pipeline: GUI / headless runner):

  legacy, or no mode given  (qty_basis = "request") -- the old evaluation,
      byte-for-byte unchanged:
        demand_fulfilled = len(supply S) x cpu
        stockout_qty     = max(0, demand_fcst - demand_fulfilled)
        fill_rate        = demand_fulfilled / demand_fcst   (1.0 when 0)
        ship_qty         = len(_actual_ship[w]) x cpu       (0 when no record)

  identity  (qty_basis = "actual_ship"):
        ship_qty         = len(_actual_ship[w]) x cpu -- everything shipped in
                           the week, late shipments included
        demand_fulfilled = ship_qty   (what Revenue / COGS are computed from)
        on_time_qty      = this week's request IDs that were shipped this week
                           (a carried-over request shipped now is NOT counted)
        stockout_qty     = request_qty - on_time_qty  (this week's request left
                           unfilled in its own week; summed over the horizon it
                           equals late + end backlog, each ID once)
        fill_rate        = on_time_qty / request_qty  (never above 1;
                           1.0 when there is no request -- the existing
                           contract of this column)
        co_qty           = requests carried INTO the week (start of week)
        co_end_qty       = requests still open at the END of the week
                           = (CO[w] + S[w]) not shipped in w, by Lot_ID

  identity but the node has no shipment record  (qty_basis = "unknown"):
        ship_qty / demand_fulfilled / on_time_qty / stockout_qty / fill_rate /
        co_end_qty are NaN. A missing record is never replaced by the request,
        and a recorded shipment of 0 is 0, not "no data".

request_qty = len(supply S) x cpu is written in every mode.

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

# Region prefix of the DAD (DC / distribution stock) rows. They are NOT market
# sales rows: the same lots appear once more in the leaf_out rows below them.
DAD_REGION_PREFIX = "DAD:"


def _ship_count(node, w: int) -> int:
    """Actual shipment lots of the week (node._actual_ship, set by
    ForwardPlanner.run); 0 when the node carries no such record."""
    actual = getattr(node, "_actual_ship", None) or {}
    return len(actual.get(w, []))


BASIS_REQUEST, BASIS_ACTUAL, BASIS_UNKNOWN = "request", "actual_ship", "unknown"


def resolve_eval_mode(sc_tree, lot_flow_mode=None):
    """The lot flow mode the evaluation should follow: the explicit argument,
    else sc_tree.lot_flow_mode (set by the planning pipeline), else None
    (= the old request-based evaluation)."""
    mode = lot_flow_mode if lot_flow_mode not in (None, "") else getattr(sc_tree, "lot_flow_mode", None)
    return str(mode).strip().lower() if mode not in (None, "") else None


def _eval_columns(node, w, cpu, demand_fcst, identity):
    """The mode-dependent columns of one node-week (see the module docstring)."""
    s_lots = node.psi4supply[w][S]
    request_qty = len(s_lots) * cpu
    if not identity:
        demand_fulfilled = request_qty
        return {
            Cols.DEMAND_FULFILLED: round(demand_fulfilled, 4),
            Cols.STOCKOUT_QTY:     round(max(0.0, demand_fcst - demand_fulfilled), 4),
            Cols.FILL_RATE:        round(demand_fulfilled / demand_fcst if demand_fcst > 0 else 1.0, 4),
            Cols.SHIP_QTY:         round(_ship_count(node, w) * cpu, 4),
            Cols.QTY_BASIS:        BASIS_REQUEST,
            Cols.REQUEST_QTY:      round(request_qty, 4),
            Cols.ON_TIME_QTY:      float("nan"),
            Cols.CO_END_QTY:       float("nan"),
        }
    actual = getattr(node, "_actual_ship", None)
    if actual is None:
        nan = float("nan")
        return {
            Cols.DEMAND_FULFILLED: nan, Cols.STOCKOUT_QTY: nan, Cols.FILL_RATE: nan,
            Cols.SHIP_QTY: nan, Cols.QTY_BASIS: BASIS_UNKNOWN,
            Cols.REQUEST_QTY: round(request_qty, 4), Cols.ON_TIME_QTY: nan, Cols.CO_END_QTY: nan,
        }
    shipped = actual.get(w, [])
    shipped_set = set(shipped)
    on_time = sum(1 for lot in s_lots if lot in shipped_set)
    open_end = sum(1 for lot in list(node.psi4supply[w][CO]) + list(s_lots) if lot not in shipped_set)
    ship_qty = len(shipped) * cpu
    return {
        Cols.DEMAND_FULFILLED: round(ship_qty, 4),
        Cols.STOCKOUT_QTY:     round((len(s_lots) - on_time) * cpu, 4),
        Cols.FILL_RATE:        round(on_time / len(s_lots) if s_lots else 1.0, 4),
        Cols.SHIP_QTY:         round(ship_qty, 4),
        Cols.QTY_BASIS:        BASIS_ACTUAL,
        Cols.REQUEST_QTY:      round(request_qty, 4),
        Cols.ON_TIME_QTY:      round(on_time * cpu, 4),
        Cols.CO_END_QTY:       round(open_end * cpu, 4),
    }


def sc_tree_to_planning_df(
    sc_tree,
    scenario_name: str = SCENARIO_PLANNING,
    cpu_size_default: int = 1,
    lot_flow_mode: str = None,
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
    lot_flow_mode : str, optional
        "identity" -> the evaluation columns use the ACTUAL shipment;
        "legacy" or None -> the old request-based evaluation (unchanged).
        When None, ``sc_tree.lot_flow_mode`` is used if the planning pipeline
        set it. See the module docstring.

    Returns
    -------
    pd.DataFrame
        One row per (sku_id, region, week) with standard PSI columns.
    """
    rows = []
    weeks = sc_tree.week_labels
    identity = resolve_eval_mode(sc_tree, lot_flow_mode) == "identity"
    unknown_nodes = []

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
                ev               = _eval_columns(leaf, w, cpu, demand_fcst, identity)
                closing_inv      = len(s_psi[I]) * cpu
                supply_receipt   = len(s_psi[P_]) * cpu
                co_qty           = len(s_psi[CO]) * cpu

                opening_inv  = prev_closing
                gross_avail  = opening_inv + supply_receipt
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
                    Cols.DEMAND_FULFILLED: ev[Cols.DEMAND_FULFILLED],
                    Cols.STOCKOUT_QTY:     ev[Cols.STOCKOUT_QTY],
                    Cols.CLOSING_INV:      round(closing_inv,  4),
                    Cols.SAFETY_STOCK_QTY: 0.0,
                    Cols.REORDER_QTY:      round(supply_receipt, 4),
                    Cols.FILL_RATE:        ev[Cols.FILL_RATE],
                    Cols.INV_COVER_WKS:    round(inv_cover,    2),
                    Cols.INV_VALUE:        0.0,   # filled by caller with unit_cost
                    # Extra Planning-specific columns
                    "co_qty":              round(co_qty, 4),
                    Cols.SHIP_QTY:         ev[Cols.SHIP_QTY],
                    Cols.QTY_BASIS:        ev[Cols.QTY_BASIS],
                    Cols.REQUEST_QTY:      ev[Cols.REQUEST_QTY],
                    Cols.ON_TIME_QTY:      ev[Cols.ON_TIME_QTY],
                    Cols.CO_END_QTY:       ev[Cols.CO_END_QTY],
                })
                if ev[Cols.QTY_BASIS] == BASIS_UNKNOWN and leaf.node_id not in unknown_nodes:
                    unknown_nodes.append(leaf.node_id)

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
                ev               = _eval_columns(dad, w, cpu, demand_fcst, identity)
                closing_inv      = len(s_psi[I]) * cpu
                supply_receipt   = len(s_psi[P_]) * cpu
                co_qty           = len(s_psi[CO]) * cpu

                opening_inv  = prev_closing
                gross_avail  = opening_inv + supply_receipt
                avg_demand   = demand_fcst or 1.0
                inv_cover    = min(closing_inv / avg_demand, 999.0)

                rows.append({
                    Cols.SCENARIO:         scenario_name,
                    Cols.SKU_ID:           prod_nm,
                    Cols.REGION:           f"{DAD_REGION_PREFIX}{region}",
                    Cols.WEEK:             wk_label,
                    Cols.OPENING_INV:      round(opening_inv,  4),
                    Cols.SUPPLY_RECEIPT:   round(supply_receipt, 4),
                    Cols.GROSS_AVAIL:      round(gross_avail,  4),
                    Cols.DEMAND_FCST:      round(demand_fcst,  4),
                    Cols.DEMAND_FULFILLED: ev[Cols.DEMAND_FULFILLED],
                    Cols.STOCKOUT_QTY:     ev[Cols.STOCKOUT_QTY],
                    Cols.CLOSING_INV:      round(closing_inv,  4),
                    Cols.SAFETY_STOCK_QTY: 0.0,
                    Cols.REORDER_QTY:      round(supply_receipt, 4),
                    Cols.FILL_RATE:        ev[Cols.FILL_RATE],
                    Cols.INV_COVER_WKS:    round(inv_cover,    2),
                    Cols.INV_VALUE:        0.0,
                    "co_qty":              round(co_qty, 4),
                    Cols.SHIP_QTY:         ev[Cols.SHIP_QTY],
                    Cols.QTY_BASIS:        ev[Cols.QTY_BASIS],
                    Cols.REQUEST_QTY:      ev[Cols.REQUEST_QTY],
                    Cols.ON_TIME_QTY:      ev[Cols.ON_TIME_QTY],
                    Cols.CO_END_QTY:       ev[Cols.CO_END_QTY],
                })
                if ev[Cols.QTY_BASIS] == BASIS_UNKNOWN and dad.node_id not in unknown_nodes:
                    unknown_nodes.append(dad.node_id)

                prev_closing = closing_inv

    if unknown_nodes:
        import warnings
        msg = (f"sc_tree_to_planning_df: lot_flow_mode=identity but {len(unknown_nodes)} node(s) "
               f"have no actual-shipment record (e.g. {unknown_nodes[0]}). Their shipment / "
               f"fulfilment columns are NaN (qty_basis='unknown'); the request S is NOT used instead.")
        warnings.warn(msg, RuntimeWarning, stacklevel=2)
        print(f"[WARN] {msg}")

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
