"""
wom/engine/sc_tree_builder.py
==============================
Phase B — Multi-tier SCTree builder from CSV master.

Reads a sc_tree_master.csv that describes an arbitrary-depth supply chain
tree (ported from original WOM pysi/network/tree.py  create_tree_set_attribute).

CSV schema (required)
---------------------
    node_name    : str   — unique name within this product (e.g. "Foxconn_CN")
    parent_node  : str   — parent's node_name; empty / NaN means this is a root
    product_name : str   — SKU / product key (matches demand_forecast sku_id)
    node_type    : str   — supply_point | dad | leaf_out | mom | leaf_in
    side         : str   — outbound | inbound
    lt_wks       : int   — lead time in weeks

CSV schema (optional)
---------------------
    ss_days      : int   — safety stock days (default 0); backward planner adds
                           ceil(ss_days/7) extra offset weeks on top of lt_wks
    region       : str   — geographic region; REQUIRED on leaf_out nodes for
                           demand-lot assignment to work (e.g. "AMER")
    supply_role  : str   — "confluence" | "assembly" | "" (default "assembly").
                           Only meaningful when a node has 2+ children in the
                           InBound tree; see PlanNode.supply_role / A1 fix
                           (request_fix_a1_supply_role_rev2.md).
    bom_qty      : int   — BOM quantity per parent unit (default 1). Only
                           meaningful for supply_role="assembly" children;
                           forced to 1 for "confluence" children regardless
                           of the CSV value. See PlanNode.bom_qty / Letter B
                           (request_letter_b_bom_qty.md, "1 set rule").

NOT read from this CSV: `cpu_size` moved to planning_config.csv (Request
Letter A: request_letter_a_cpu_size_to_plan.md) -- it is a plan-wide value
(SCTree.cpu_size), not per-node, so a column here would let nodes disagree.

Tree topology rules
-------------------
OutBound (demand side):
    supply_point  <- OT root (no parent, side=outbound, node_type=supply_point)
      └─ dad(s)   <- distribution centres, warehouses
           └─ leaf_out(s)  <- sales channels; MUST have region

InBound (supply side):
    mom  <- IN root (no parent, side=inbound, node_type=mom)
      └─ mom(s)   <- tier-1, tier-2 suppliers / factories
           └─ leaf_in(s)  <- raw material / component sources

Backward planning order (demand -> supply):
    OT postorder -> bridge SP->MOM -> IN preorder

Forward planning order (supply -> demand):
    IN postorder -> bridge MOM->SP -> OT preorder

Compatibility
-------------
The built SCTree is identical in interface to build_demo_sc_tree() output.
BackwardPlanner, ForwardPlanner, assign_demand_lots_from_dict, and all
downstream KPI engines work unchanged.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from wom.model.plan_node import (
    PlanNode,
    NODE_TYPE_SUPPLY_POINT,
    NODE_TYPE_DAD,
    NODE_TYPE_LEAF_OUT,
    NODE_TYPE_MOM,
    NODE_TYPE_LEAF_IN,
)
from wom.model.sc_tree import SCTree


# ──────────────────────────────────────────────────────────────────────────
# Required / optional columns
# ──────────────────────────────────────────────────────────────────────────

REQUIRED_COLS = {"node_name", "parent_node", "product_name",
                 "node_type", "side", "lt_wks"}


def _is_sc_tree_master(df: pd.DataFrame) -> bool:
    """Return True if df looks like a sc_tree_master (has parent_node column)."""
    return "parent_node" in df.columns and "node_type" in df.columns


# ──────────────────────────────────────────────────────────────────────────
# Node-id builders  (must match _infer_region_from_node convention in
# wom/model/lot_generator.py so demand-lot assignment works correctly)
# ──────────────────────────────────────────────────────────────────────────

def _make_node_id(
    node_type: str,
    side: str,
    node_name: str,
    region: str,
    prod_nm: str,
) -> str:
    """
    Build a node_id that is parseable by lot_generator._infer_region_from_node.

    Convention (from lot_generator.py):
        OT leaf_out :  "OUT:<anything>:<region>:<prod_nm>"
                       ->  parts[0]=="OUT", len>=4, region=parts[2]
        All other   :  "OUT:<type>:<name>:<prod_nm>"  or
                       "IN:<type>:<name>:<prod_nm>"
    """
    safe_name = node_name.replace(":", "_")
    safe_prod = prod_nm.replace(":", "_")
    safe_region = region.replace(":", "_") if region else "NA"

    if side == "outbound" and node_type == NODE_TYPE_LEAF_OUT:
        # Must be "OUT:X:REGION:PROD" so parts[2] == region
        return f"OUT:leaf_out:{safe_region}:{safe_prod}"

    prefix = "OUT" if side == "outbound" else "IN"
    return f"{prefix}:{node_type}:{safe_name}:{safe_prod}"


def _parse_bom_qty(raw) -> int:
    """
    Parse one sc_tree_master.csv bom_qty cell (Letter B:
    request_letter_b_bom_qty.md, "1 set rule").

    Defined behaviour for invalid input (section 9.1): blank, 0, negative,
    non-integer (e.g. "2.5"), or non-numeric (e.g. a string) all default to
    1 -- the same safe-default philosophy already used for supply_role /
    demand_envelope / cpu_size. This column only ever multiplies a
    KPI/display/PPC quantity downstream of Planning; a bad value must never
    raise, only fall back silently to "no multiplier".
    """
    s = str(raw).strip() if raw is not None else ""
    if s == "" or s.lower() == "nan":
        return 1
    try:
        f = float(s)
    except (ValueError, TypeError):
        return 1
    if f <= 0 or f != int(f):
        return 1
    return int(f)


# ──────────────────────────────────────────────────────────────────────────
# Main builder
# ──────────────────────────────────────────────────────────────────────────

def build_sc_tree_from_master(
    df: pd.DataFrame,
    week_labels: List[str],
) -> SCTree:
    """
    Build an arbitrary-depth SCTree from a sc_tree_master DataFrame.

    Parameters
    ----------
    df:
        DataFrame loaded from sc_tree_master.csv.
        Required columns: node_name, parent_node, product_name,
                          node_type, side, lt_wks
        Optional columns: ss_days, init_stock_days, region, supply_role
        (cpu_size is NOT read here -- see planning_config.csv / SCTree.cpu_size)
    week_labels:
        Ordered ISO week strings for the planning horizon.

    Returns
    -------
    SCTree
        Fully wired and init_psi() called, ready for BackwardPlanner.

    Raises
    ------
    ValueError
        If required columns are missing, or if a product has no supply_point
        or no inbound MOM root.
    """
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"sc_tree_master is missing required columns: {missing}"
        )

    tree = SCTree(week_labels)

    for prod_nm in df["product_name"].unique():
        prod_df = df[df["product_name"] == prod_nm].copy()
        _build_product_tree(tree, prod_nm, prod_df)

    tree.init_all_psi()
    return tree


def _build_product_tree(
    tree: SCTree,
    prod_nm: str,
    prod_df: pd.DataFrame,
) -> None:
    """Build and register OT + IN trees for one product."""

    nodes: Dict[str, PlanNode] = {}

    # ── Step 1: Create all PlanNode objects ──────────────────────────────
    for _, row in prod_df.iterrows():
        node_name = str(row["node_name"]).strip()
        node_type = str(row["node_type"]).strip()
        side      = str(row["side"]).strip()
        # Bug fix (2026-09-04, request_stage3a1_stockyard_passthrough.md):
        # `int(row.get("lt_wks", 1) or 1)` treated an explicit lt_wks=0 as
        # falsy and silently forced it to 1 -- invisible until Stage 3a-1's
        # stockyard nodes (deliberately lt_wks=0, pass-through) were the
        # first non-root nodes in any model to actually specify 0. The
        # forced-to-1 value double-shifted backward demand offsets by one
        # extra week at each Yard hop, pushing boundary-week lots past
        # week 0 into negative (past-due) territory and silently dropping
        # them. Root nodes (supply_point/mom) already used lt_wks=0 in
        # every sample model but never hit this path's effect, since a
        # root's own lt_wks is never read by _offset_week (only a CHILD's
        # lt_wks is, when propagating demand up to ITS parent).
        _lt_raw = row.get("lt_wks", 1)
        lt_wks = 1 if (_lt_raw is None or (isinstance(_lt_raw, float) and pd.isna(_lt_raw))) else int(_lt_raw)
        # transit_lt_wks: physical supply transit time (ForwardPlanner)
        # Falls back to lt_wks if not specified (empty/0) in CSV
        _tlt          = row.get("transit_lt_wks", None)
        transit_lt_wks = int(float(_tlt)) if (_tlt is not None and str(_tlt).strip() not in ("", "0", "nan")) else lt_wks
        ss_days       = int(row.get("ss_days", 0) or 0)
        # X2: warm-up / initial stock coverage [days] (OutBound only; default 0).
        # Column may be absent in existing models -> 0 = unchanged behaviour.
        init_stock_days = int(row.get("init_stock_days", 0) or 0)
        region        = str(row.get("region", "") or "").strip()
        is_decoupling = bool(int(row.get("buffering_stock_flag", 0) or 0))
        # Phase 2 Fork B: per-node demand-envelope mode (hard/soft, default hard).
        demand_envelope = str(row.get("demand_envelope", "hard") or "hard").strip().lower()
        if demand_envelope not in ("hard", "soft"):
            demand_envelope = "hard"
        # A1 fix (request_fix_a1_supply_role_rev2.md): blank/unspecified/typo'd
        # values all default to "assembly" (safe default, existing behaviour).
        supply_role = str(row.get("supply_role", "") or "").strip().lower()
        if supply_role != "confluence":
            supply_role = "assembly"
        # Letter B (request_letter_b_bom_qty.md, "1 set rule"): bom_qty is a
        # per-node BOM multiplier, meaningful only for "assembly" children.
        bom_qty = _parse_bom_qty(row.get("bom_qty", ""))
        # confluence siblings SPLIT demand rather than multiply it, so bom_qty
        # is forced to 1 regardless of the CSV value (request_fix_a1_supply_role_rev2.md
        # §3.2 -- writing bom_qty>1 on a confluence row is a lint error candidate,
        # not silently honored here).
        if supply_role == "confluence":
            bom_qty = 1

        node_id = _make_node_id(node_type, side, node_name, region, prod_nm)

        pnode = PlanNode(
            node_id       = node_id,
            node_name     = node_name,
            product       = prod_nm,
            side          = side,
            node_type     = node_type,
            tier          = 0,       # calculated in Step 3
            lt_wks         = lt_wks,
            transit_lt_wks = transit_lt_wks,
            ss_days        = ss_days,
            init_stock_days = init_stock_days,
            is_decoupling  = is_decoupling,
            demand_envelope = demand_envelope,
            supply_role    = supply_role,
            bom_qty        = bom_qty,
        )
        nodes[node_name] = pnode

    # ── Step 2: Wire parent -> child ──────────────────────────────────────
    for _, row in prod_df.iterrows():
        node_name   = str(row["node_name"]).strip()
        parent_name = str(row.get("parent_node", "") or "").strip()
        if parent_name and parent_name in nodes:
            nodes[parent_name].add_child(nodes[node_name])

    # ── Step 3: Compute tier depth (0 = tree root, increases toward leaf) ─
    for node in nodes.values():
        depth = 0
        n = node
        while n.parent is not None:
            depth += 1
            n = n.parent
        node.tier = depth

    # ── Step 4: Identify OT root (supply_point) and IN root (top MOM) ────
    ot_roots = [
        n for n in nodes.values()
        if n.node_type == NODE_TYPE_SUPPLY_POINT and n.parent is None
    ]
    in_roots = [
        n for n in nodes.values()
        if n.node_type == NODE_TYPE_MOM and n.parent is None
    ]

    if not ot_roots:
        raise ValueError(
            f"Product {prod_nm!r}: no 'supply_point' root found. "
            f"Add a row with node_type='supply_point', parent_node='' "
            f"on the outbound side."
        )
    if not in_roots:
        raise ValueError(
            f"Product {prod_nm!r}: no 'mom' root found. "
            f"Add a row with node_type='mom', parent_node='' "
            f"on the inbound side."
        )
    if len(ot_roots) > 1:
        raise ValueError(
            f"Product {prod_nm!r}: multiple supply_point roots found: "
            f"{[n.node_name for n in ot_roots]}"
        )
    # Multiple top-level MOM roots are allowed for multi-factory scenarios
    # (Production Allocation Policy).  The first MOM (lowest node_id
    # alphabetically, for determinism) is registered as the primary.
    # Additional MOMs are registered via register_extra_mom() and will be
    # routed to by LaneTable during BackwardPlanner Phase 2.
    in_roots_sorted = sorted(in_roots, key=lambda n: n.node_id)
    primary_in_root = in_roots_sorted[0]

    tree.register(prod_nm, ot_root=ot_roots[0], in_root=primary_in_root)

    for extra_mom in in_roots_sorted[1:]:
        tree.register_extra_mom(prod_nm, extra_mom)
        print(f"[SCTreeBuilder] {prod_nm}: extra MOM root registered: {extra_mom.node_id}")


# ──────────────────────────────────────────────────────────────────────────
# Introspection helper
# ──────────────────────────────────────────────────────────────────────────

def print_sc_tree_structure(tree: SCTree) -> None:
    """Print a human-readable tree structure for debugging."""
    for prod_nm in tree.products:
        print(f"\n{'='*60}")
        print(f"Product: {prod_nm}")
        print("  OutBound:")
        _print_node(tree.get_ot_root(prod_nm), indent=4)
        print("  InBound:")
        for mom in tree.get_in_roots(prod_nm).values():
            _print_node(mom, indent=4)


def _print_node(node: PlanNode, indent: int = 0) -> None:
    pad = " " * indent
    print(f"{pad}[{node.node_type}] {node.node_name}  "
          f"(tier={node.tier}, lt={node.lt_wks}w, id={node.node_id})")
    for child in node.children:
        _print_node(child, indent + 4)
