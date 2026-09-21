"""
wom/engine/hammock_layout.py
============================
Attribute-driven E2E Hammock Layout for SCTree PlanNodes.

Layout axes
-----------
X axis  =  distance from supply_point (bridge)
  supply_point        →  x = 0
  OutBound dad/leaf   →  x = +tier
  InBound  mom/leaf   →  x = -(tier+1)
  sales_office        →  x = max_ot_depth + 1
  procurement_office  →  x = -(max_in_depth + 2)

Y axis  =  peer position at each X level, centred on 0

Multi-MOM support (v1r0m1)
--------------------------
  All MOM roots and their subtrees are rendered.
  Each MOM gets its own bridge edge to the supply_point.

Lane assignment edges (v1r0m1)
------------------------------
  When lane_df (from lane_assignment.csv) is supplied to
  build_hammock_graph(), direct MOM → DC edges are added with
  edge_type="lane" and mom_id stored as edge attribute.
  The renderer draws these as thick coloured logistics lines,
  showing which factory supplies which distribution centre.

Supply Point rendering hint (v1r0m1)
-------------------------------------
  supply_point nodes carry  is_bridge=True  so the renderer can
  draw them smaller and semi-transparent (HQ / logical node).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

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


# ── Layout constants ──────────────────────────────────────────────────────

Y_SPACING    = 1.8
PRODUCT_GAP  = 0.0
X_SPACING    = 1.0

# ── Colour mapping by node_type ───────────────────────────────────────────

NODE_COLOUR = {
    NODE_TYPE_SUPPLY_POINT: "#FFEB3B",   # yellow  – bridge / supply_point
    NODE_TYPE_MOM:          "#66BB6A",   # green   – InBound production nodes
    NODE_TYPE_LEAF_IN:      "#26A69A",   # teal    – InBound leaf (raw material)
    NODE_TYPE_DAD:          "#42A5F5",   # blue    – OutBound DC / warehouse
    NODE_TYPE_LEAF_OUT:     "#AB47BC",   # purple  – OutBound leaf (market)
    "virtual":              "#FF9800",   # orange  – procurement/sales office
}

NODE_SIZE = {
    NODE_TYPE_SUPPLY_POINT: 2400,
    NODE_TYPE_MOM:          1600,
    NODE_TYPE_LEAF_IN:      1200,
    NODE_TYPE_DAD:          1600,
    NODE_TYPE_LEAF_OUT:     1200,
    "virtual":              1000,
}

# Lane edge colours — cycled per unique MOM
LANE_COLOURS = [
    "#FF6F00",   # amber  (1st MOM)
    "#E53935",   # red    (2nd MOM)
    "#7B1FA2",   # purple (3rd MOM)
    "#1565C0",   # blue   (4th MOM)
    "#2E7D32",   # green  (5th MOM)
]


# ──────────────────────────────────────────────────────────────────────────
# Position computation
# ──────────────────────────────────────────────────────────────────────────

def compute_hammock_positions(
    sc_tree: SCTree,
    prod_nm: Optional[str] = None,
    y_spacing: float = Y_SPACING,
    x_spacing: float = X_SPACING,
    lane_df: Optional["pd.DataFrame"] = None,
) -> Dict[str, Tuple[float, float]]:
    """Compute (x, y) layout positions for all nodes of one product.

    When lane_df is supplied, OutBound DAD/leaf nodes are reordered
    so each DC's Y aligns with its assigned MOM's Y, eliminating
    lane-edge crossings in the Hammock graph.
    """
    if prod_nm is None:
        prod_nm = sc_tree.products[0]

    x_buckets: Dict[int, List[Tuple[str, Optional[PlanNode]]]] = defaultdict(list)
    seen_node_ids: set = set()

    sp = sc_tree.get_ot_root(prod_nm)
    x_buckets[0].append((sp.node_id, sp))
    seen_node_ids.add(sp.node_id)

    for node in sp.walk_preorder():
        if node is sp:
            continue
        if node.node_id not in seen_node_ids:
            x_buckets[node.tier].append((node.node_id, node))
            seen_node_ids.add(node.node_id)

    in_roots = list(sc_tree.get_in_roots(prod_nm).values())
    for in_root in in_roots:
        for node in in_root.walk_preorder():
            if node.node_id not in seen_node_ids:
                x = -(node.tier + 1)
                x_buckets[x].append((node.node_id, node))
                seen_node_ids.add(node.node_id)

    max_ot = max(
        (n.tier for n in sp.walk_preorder() if n is not sp), default=1
    )
    max_in = max(
        (n.tier for ir in in_roots for n in ir.walk_preorder()), default=0
    )
    x_buckets[max_ot + 1].append(("sales_office", None))
    x_buckets[-(max_in + 2)].append(("procurement_office", None))

    positions: Dict[str, Tuple[float, float]] = {}
    for x_level, bucket in x_buckets.items():
        n = len(bucket)
        for i, (node_id, _node) in enumerate(bucket):
            y = (i - (n - 1) / 2) * y_spacing
            positions[node_id] = (float(x_level) * x_spacing, y)

    # ── Reorder OutBound nodes to align with lane assignment ──────────
    if lane_df is not None and not lane_df.empty:
        positions = _reorder_outbound_by_lane(positions, sc_tree, prod_nm, lane_df)

    return positions


def _reorder_outbound_by_lane(
    positions: Dict[str, Tuple[float, float]],
    sc_tree: SCTree,
    prod_nm: str,
    lane_df: "pd.DataFrame",
) -> Dict[str, Tuple[float, float]]:
    """
    Reorder OutBound DAD (DC) and leaf_out Y positions so that each DC's
    vertical position aligns with its assigned MOM, eliminating X-shaped
    lane-edge crossings.

    Algorithm:
      1. Build dc_id → mom_id from lane_df (via build_lane_edges).
      2. Sort DC nodes by their MOM's Y (descending: upper MOM → upper DC).
      3. Redistribute the existing DC Y values according to the new order.
      4. Shift each DC's leaf_out children by the same delta_y.
    """
    lane_edges = build_lane_edges(sc_tree, prod_nm, lane_df)
    if not lane_edges:
        return positions

    dc_to_mom: Dict[str, str] = {dc_id: mom_id
                                  for mom_id, dc_id, _ in lane_edges}

    # OutBound tree: dc_id → [leaf_out_id, ...]
    sp = sc_tree.get_ot_root(prod_nm)
    dc_to_leaves: Dict[str, List[str]] = {}
    for dad_node in sp.children:
        dc_to_leaves[dad_node.node_id] = [c.node_id for c in dad_node.children]

    dc_ids = [dc_id for dc_id in dc_to_leaves if dc_id in positions]
    if not dc_ids:
        return positions

    # Sort DCs by their assigned MOM's Y (desc) — stable sort preserves
    # relative order among DCs sharing the same MOM.
    def _mom_y(dc_id: str) -> float:
        mid = dc_to_mom.get(dc_id)
        return positions[mid][1] if (mid and mid in positions) else 0.0

    sorted_dcs = sorted(dc_ids, key=_mom_y, reverse=True)

    # Redistribute: assign the largest existing Y to the DC with the
    # highest MOM, etc.
    existing_y_values = sorted(
        (positions[d][1] for d in dc_ids), reverse=True
    )

    new_positions = dict(positions)
    for dc_id, new_y in zip(sorted_dcs, existing_y_values):
        old_y = positions[dc_id][1]
        dc_x  = positions[dc_id][0]
        new_positions[dc_id] = (dc_x, new_y)
        delta_y = new_y - old_y
        for leaf_id in dc_to_leaves.get(dc_id, []):
            if leaf_id in new_positions:
                lx, ly = new_positions[leaf_id]
                new_positions[leaf_id] = (lx, ly + delta_y)

    return new_positions


def compute_hammock_positions_all(
    sc_tree: SCTree,
    y_spacing: float = Y_SPACING,
    x_spacing: float = X_SPACING,
    product_gap: float = PRODUCT_GAP,
) -> Dict[str, Tuple[float, float]]:
    """Compute positions for ALL products, stacked vertically."""
    all_pos: Dict[str, Tuple[float, float]] = {}
    y_offset = 0.0

    for prod_nm in sc_tree.products:
        prod_pos = compute_hammock_positions(sc_tree, prod_nm,
                                            y_spacing=y_spacing,
                                            x_spacing=x_spacing)
        for node_id, (x, y) in prod_pos.items():
            if node_id in ("sales_office", "procurement_office"):
                uid = f"{node_id}_{prod_nm}"
            else:
                uid = node_id
            all_pos[uid] = (x, y + y_offset)

        if prod_pos:
            ys = [v[1] for v in prod_pos.values()]
            y_offset += (max(ys) - min(ys) + y_spacing) + product_gap

    return all_pos


# ──────────────────────────────────────────────────────────────────────────
# Lane assignment helpers
# ──────────────────────────────────────────────────────────────────────────

def build_lane_edges(
    sc_tree: SCTree,
    prod_nm: str,
    lane_df: pd.DataFrame,
) -> List[Tuple[str, str, str]]:
    """
    Derive physical logistics edges from lane_assignment.csv.

    Returns list of (mom_node_id, dc_node_id, mom_node_id) tuples.
    The third element (mom_node_id again) is used by the renderer to
    assign a consistent colour per factory.

    Strategy: map leaf_node_name → parent DAD node_id via the OT tree,
    then return (mom_node_id, dad_node_id) pairs.
    """
    if lane_df is None or lane_df.empty:
        return []

    sp = sc_tree.get_ot_root(prod_nm)

    # leaf_out node_name → parent DAD node_id
    leaf_name_to_dad_id: Dict[str, str] = {}
    for dad_node in sp.children:
        for leaf_node in dad_node.children:
            leaf_name_to_dad_id[leaf_node.node_name] = dad_node.node_id

    # filter for this product
    col_sku = "sku_id" if "sku_id" in lane_df.columns else None
    if col_sku:
        rows = lane_df[lane_df[col_sku] == prod_nm]
    else:
        rows = lane_df

    edges: List[Tuple[str, str, str]] = []
    seen: set = set()
    for _, row in rows.iterrows():
        leaf_nm = str(row.get("leaf_node_name", "")).strip()
        mom_id  = str(row.get("mom_node_id",   "")).strip()
        dad_id  = leaf_name_to_dad_id.get(leaf_nm)
        if dad_id and mom_id and (mom_id, dad_id) not in seen:
            edges.append((mom_id, dad_id, mom_id))
            seen.add((mom_id, dad_id))

    return edges


def lane_colour_map(lane_edges: List[Tuple[str, str, str]]) -> Dict[str, str]:
    """Return {mom_node_id: colour} for the given lane edges."""
    unique_moms = list(dict.fromkeys(e[2] for e in lane_edges))
    return {mid: LANE_COLOURS[i % len(LANE_COLOURS)]
            for i, mid in enumerate(unique_moms)}


# ──────────────────────────────────────────────────────────────────────────
# Graph builder  (NetworkX DiGraph)
# ──────────────────────────────────────────────────────────────────────────

def build_hammock_graph(
    sc_tree: SCTree,
    prod_nm: Optional[str] = None,
    lane_df: Optional[pd.DataFrame] = None,
):
    """
    Build a NetworkX DiGraph in hammock E2E layout for one product.

    Parameters
    ----------
    sc_tree  : built SCTree
    prod_nm  : product name; if None, uses sc_tree.products[0]
    lane_df  : lane_assignment DataFrame (optional).
               When supplied, direct MOM→DC "lane" edges are added with
               attributes  edge_type="lane"  and  mom_id=<mom_node_id>.

    Returns
    -------
    G    : nx.DiGraph
    pos  : dict  node_id → (x, y)
    """
    try:
        import networkx as nx
    except ImportError:
        raise ImportError("networkx is required: pip install networkx")

    if prod_nm is None:
        prod_nm = sc_tree.products[0]

    G   = nx.DiGraph()
    pos = compute_hammock_positions(sc_tree, prod_nm, lane_df=lane_df)

    sp       = sc_tree.get_ot_root(prod_nm)
    in_roots = list(sc_tree.get_in_roots(prod_nm).values())

    # ── Add nodes ─────────────────────────────────────────────────────
    G.add_node(sp.node_id,
               kind=sp.node_type, node_type=sp.node_type,
               node_obj=sp, label=sp.node_name, is_bridge=True)

    for node in sp.walk_preorder():
        if node is sp:
            continue
        G.add_node(node.node_id,
                   kind=node.node_type, node_type=node.node_type,
                   node_obj=node, label=node.node_name, is_bridge=False)

    seen_in: set = set()
    for in_root in in_roots:
        for node in in_root.walk_preorder():
            if node.node_id not in seen_in:
                G.add_node(node.node_id,
                           kind=node.node_type, node_type=node.node_type,
                           node_obj=node, label=node.node_name, is_bridge=False)
                seen_in.add(node.node_id)

    max_ot = max((n.tier for n in sp.walk_preorder() if n is not sp), default=1)
    max_in = max(
        (n.tier for ir in in_roots for n in ir.walk_preorder()), default=0
    )
    G.add_node("sales_office",
               kind="virtual", node_type="virtual",
               node_obj=None, label="sales\noffice", is_bridge=False)
    G.add_node("procurement_office",
               kind="virtual", node_type="virtual",
               node_obj=None, label="procurement\noffice", is_bridge=False)

    # ── Topology edges ────────────────────────────────────────────────
    _add_edges_preorder(G, sp)

    seen_roots: set = set()
    for in_root in in_roots:
        if in_root.node_id not in seen_roots:
            _add_edges_preorder(G, in_root)
            G.add_edge(in_root.node_id, sp.node_id, edge_type="topology")
            seen_roots.add(in_root.node_id)

    for node in sp.walk_preorder():
        if node.node_type == NODE_TYPE_LEAF_OUT:
            G.add_edge(node.node_id, "sales_office", edge_type="topology")

    seen_leaf_in: set = set()
    for in_root in in_roots:
        for node in in_root.walk_preorder():
            if node.node_type == NODE_TYPE_LEAF_IN and node.node_id not in seen_leaf_in:
                G.add_edge("procurement_office", node.node_id, edge_type="topology")
                seen_leaf_in.add(node.node_id)

    # ── Lane assignment edges (MOM → DC) ──────────────────────────────
    if lane_df is not None and not lane_df.empty:
        for mom_id, dc_id, mid in build_lane_edges(sc_tree, prod_nm, lane_df):
            if mom_id in G.nodes and dc_id in G.nodes:
                G.add_edge(mom_id, dc_id,
                           edge_type="lane",
                           mom_id=mom_id)

    return G, pos


def _add_edges_preorder(G, root: PlanNode) -> None:
    """Add parent→child topology edges for the tree rooted at root."""
    for node in root.walk_preorder():
        for child in node.children:
            G.add_edge(node.node_id, child.node_id, edge_type="topology")


# ──────────────────────────────────────────────────────────────────────────
# Colour / size helpers
# ──────────────────────────────────────────────────────────────────────────

def node_colour(node_type: str, is_selected: bool = False,
                highlight_colour: str = "#FFFF00") -> str:
    if is_selected:
        return highlight_colour
    return NODE_COLOUR.get(node_type, "#607D8B")


def node_size(node_type: str, is_selected: bool = False) -> int:
    if is_selected:
        return 3000
    return NODE_SIZE.get(node_type, 1400)
