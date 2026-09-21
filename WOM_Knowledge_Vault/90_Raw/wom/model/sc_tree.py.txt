"""
wom/model/sc_tree.py
====================
WOM Planning Layer — SCTree

Holds the OutBound + InBound PlanNode tree pair for every product.

Tree entry points:
    prod_tree_dict_OT[prod_nm]  →  supply_point PlanNode (OutBound root)
    prod_tree_dict_IN[prod_nm]  →  MOM PlanNode at tier=0 (InBound root)

Hammock model:
                    \u250c──────────────────────────────────────\u2510
    InBound tree        \u2502          OutBound tree               \u2502
    (supply side)       \u2502          (demand side)               \u2502
                        \u2502                                      \u2502
    leaf_in             \u2502   supply_point ──▶ DAD(tier=0) ──▶ leaf_out
      └─ MOM(tier=0) ──▶\u2502   (OT root)        └─▶ DC  ──▶ leaf_out
           └─ tier-1    \u2502                    └─▶ ...
                └─ leaf \u2502
                        └──────────────────────────────────────\u2518

Traversal rules:
    Backward planning (demand allocation, ideal / CO-free):
        1. walk_postorder(OT root)    leaf_out → DAD → supply_point
        2. Bridge: supply_point demand lots → MOM
        3. walk_preorder(IN root)     MOM → tier-1 → leaf_in

    Forward planning (supply propagation, CO may be generated):
        1. walk_postorder(IN root)    leaf_in → tier-1 → MOM
        2. Bridge: MOM supply lots → supply_point
        3. walk_preorder(OT root)     supply_point → DAD → leaf_out
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Dict, Generator, Iterable, Iterator, List, Optional, Tuple

import pandas as pd

from wom.model.plan_node import (
    PlanNode,
    NODE_TYPE_SUPPLY_POINT,
    NODE_TYPE_DAD,
    NODE_TYPE_LEAF_OUT,
    NODE_TYPE_MOM,
    NODE_TYPE_LEAF_IN,
    S, CO, I, P,
)


# ---------------------------------------------------------------------------
# BridgeTransfer  (data class for supply_point <-> MOM handoff)
# ---------------------------------------------------------------------------
@dataclass
class BridgeTransfer:
    prod_nm:    str
    week:       int
    bucket:     int
    lot_ids:    List[str]
    direction:  str            # "backward" | "forward"


# ---------------------------------------------------------------------------
# SCTree
# ---------------------------------------------------------------------------
class SCTree:
    def __init__(self, week_labels: List[str]) -> None:
        if not week_labels:
            raise ValueError("week_labels must not be empty")
        self.week_labels: List[str] = list(week_labels)
        self.prod_tree_dict_OT: Dict[str, PlanNode] = {}
        self.prod_tree_dict_IN: Dict[str, PlanNode] = {}
        self._in_roots_dict: Dict[str, Dict[str, PlanNode]] = {}
        # Common Planning Unit (lots -> physical quantity), plan-wide (Request
        # Letter A: request_letter_a_cpu_size_to_plan.md). Formerly a per-node
        # PlanNode field, which contradicted the WOM principle that every node
        # in a plan shares one cpu_size; now a single value for the whole tree,
        # read from planning_config.csv's cpu_size key (see
        # wom.engine.warmup.read_cpu_size) by the pipeline entry points
        # (app.py / run_headless_from_folder.py / sweep_flags.py) and assigned
        # here. Always present (default 1) so callers can read sc_tree.cpu_size
        # directly -- no getattr(..., 1) fallback needed, and none should be
        # added (a silent fallback would hide a wiring gap; see Letter A §2.4).
        self.cpu_size: int = 1

    def register(self, prod_nm: str, ot_root: PlanNode, in_root: PlanNode) -> None:
        if ot_root.node_type != NODE_TYPE_SUPPLY_POINT:
            raise ValueError(
                f"ot_root must be NODE_TYPE_SUPPLY_POINT, got {ot_root.node_type!r}"
            )
        self.prod_tree_dict_OT[prod_nm] = ot_root
        self.prod_tree_dict_IN[prod_nm] = in_root
        if prod_nm not in self._in_roots_dict:
            self._in_roots_dict[prod_nm] = {}
        self._in_roots_dict[prod_nm][in_root.node_id] = in_root

    def register_extra_mom(self, prod_nm: str, mom_node: PlanNode) -> None:
        if prod_nm not in self._in_roots_dict:
            raise KeyError(f"Product {prod_nm!r} not yet registered. Call register() first.")
        self._in_roots_dict[prod_nm][mom_node.node_id] = mom_node

    def init_all_psi(self) -> None:
        seen: set = set()
        for node in self._iter_all_nodes_global():
            if id(node) not in seen:
                node.init_psi(self.week_labels)
                seen.add(id(node))

    @property
    def products(self) -> List[str]:
        return list(self.prod_tree_dict_OT.keys())

    def get_ot_root(self, prod_nm: str) -> PlanNode:
        try:
            return self.prod_tree_dict_OT[prod_nm]
        except KeyError:
            raise KeyError(f"Product {prod_nm!r} not found in OutBound trees")

    def get_in_root(self, prod_nm: str) -> PlanNode:
        try:
            return self.prod_tree_dict_IN[prod_nm]
        except KeyError:
            raise KeyError(f"Product {prod_nm!r} not found in InBound trees")

    def get_in_roots(self, prod_nm: str) -> Dict[str, PlanNode]:
        return dict(self._in_roots_dict.get(prod_nm, {
            self.prod_tree_dict_IN[prod_nm].node_id: self.prod_tree_dict_IN[prod_nm]
        }))

    def num_weeks(self) -> int:
        return len(self.week_labels)

    def week_idx(self, week_label: str) -> int:
        return self.week_labels.index(week_label)

    def iter_backward(self, prod_nm: str) -> Iterator[PlanNode]:
        ot_root = self.get_ot_root(prod_nm)
        in_root = self.get_in_root(prod_nm)
        yield from ot_root.walk_postorder()
        yield from in_root.walk_preorder()

    def iter_forward(self, prod_nm: str) -> Iterator[PlanNode]:
        ot_root = self.get_ot_root(prod_nm)
        in_root = self.get_in_root(prod_nm)
        yield from in_root.walk_postorder()
        yield from ot_root.walk_preorder()

    def iter_all_nodes(self, prod_nm: str) -> Iterator[PlanNode]:
        seen: set = set()
        in_roots = self.get_in_roots(prod_nm)
        for node in itertools.chain(
            self.get_ot_root(prod_nm).walk_preorder(),
            *(mom.walk_preorder() for mom in in_roots.values()),
        ):
            if id(node) not in seen:
                seen.add(id(node))
                yield node

    def bridge_backward(self, prod_nm: str, week: int,
                        market_priority: Optional[List[str]] = None) -> BridgeTransfer:
        sp  = self.get_ot_root(prod_nm)
        mom = self.get_in_root(prod_nm)
        lots = list(sp.psi4demand[week][S])
        for lot_id in lots:
            mom.add_lot_demand(week, S, lot_id)
        return BridgeTransfer(prod_nm=prod_nm, week=week, bucket=S,
                              lot_ids=lots, direction="backward")

    def bridge_forward(self, prod_nm: str, week: int) -> BridgeTransfer:
        sp  = self.get_ot_root(prod_nm)
        mom = self.get_in_root(prod_nm)
        lots = list(mom.psi4supply[week][P])
        for lot_id in lots:
            sp.add_lot_supply(week, P, lot_id)
        return BridgeTransfer(prod_nm=prod_nm, week=week, bucket=P,
                              lot_ids=lots, direction="forward")

    def _iter_all_nodes_global(self) -> Iterator[PlanNode]:
        for prod_nm in self.products:
            yield from self.iter_all_nodes(prod_nm)

    @staticmethod
    def walk_ancestor_chain(
        start_node: PlanNode,
        node_type_filter: str,
        stop_node: Optional[PlanNode] = None,
    ) -> List[str]:
        """
        Walk start_node.parent upward until stop_node (exclusive), collecting
        node_name of every ancestor whose node_type == node_type_filter.

        Returns the chain in start_node-side-first order (nearest ancestor
        first). Callers that need mom-side-first order (e.g. OutBound DAD
        chains, to match ppc_tariff.py's existing "MOM-side first, channel
        -side last" convention) must reverse the result themselves.

        This replaces the old product_id-level flat chain lists (built by a
        single preorder sweep over the whole tree, see
        wom/ppc/ppc_runner.py's GENERIC scenario detection prior to the
        wom-v1r1m7-fix4all_case fix), which conflated parallel branches
        (e.g. multiple independent regional DAD nodes fed by the same
        supply_point) into one fake sequential chain. Because a Lot's
        channel_node / leaf_in is already fixed by the time PPC runs (see
        Coding Request Letter smartx-2027-2029-fix-request-letter.md,
        section 4-5), the chain should always be resolved dynamically from
        that specific node's real tree ancestry, not precomputed once per
        product_id.

        Used for two symmetric purposes:
          - OutBound (dad chain):  start_node=leaf_out, node_type_filter=
            NODE_TYPE_DAD, stop_node=supply_point (OT root). Reverse the
            result for ppc_tariff.py / ppc_backward.py.
          - InBound (mom chain):   start_node=leaf_in, node_type_filter=
            NODE_TYPE_MOM, stop_node=None. The terminal MOM (IN root) is
            detected automatically (a node with no parent) and excluded
            from the returned chain -- it is handled separately by the
            caller's existing single-node logic (e.g. ppc_forward.py's
            Step 1c for m_node's own costs). This lets the same call work
            correctly even when a product still has multiple InBound
            roots (multi-MOM, pre-SKU-split state): each leaf_in's walk
            naturally terminates at ITS OWN root, without the caller
            having to know in advance which root that is.

        Returns an empty list if no matching ancestor exists before
        stop_node (or the tree root) is reached -- this is the expected
        result for the common single-tier case (e.g. Apparel/EV/Oil's
        single DAD, or a product with no intermediate InBound tiers), and
        callers must fall back to their existing single-node legacy
        behavior in that case (unchanged from before this fix).
        """
        chain: List[str] = []
        cur = start_node.parent
        while cur is not None and cur is not stop_node:
            if stop_node is None and cur.parent is None:
                # Reached the tree root (e.g. terminal MOM / IN root) without
                # an explicit stop_node -- exclude it, caller handles it
                # separately.
                break
            if cur.node_type == node_type_filter:
                chain.append(cur.node_name)
            cur = cur.parent
        return chain

    def summary(self) -> str:
        lines = [
            f"SCTree  weeks={self.num_weeks()}  "
            f"({self.week_labels[0]} \u2026 {self.week_labels[-1]})",
            f"  products ({len(self.products)}): {self.products}",
        ]
        for prod_nm in self.products:
            ot_nodes = list(self.get_ot_root(prod_nm).walk_preorder())
            in_nodes = list(self.get_in_root(prod_nm).walk_preorder())
            lines.append(
                f"  [{prod_nm}]  OT nodes={len(ot_nodes)}  IN nodes={len(in_nodes)}"
            )
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"SCTree(products={self.products}, weeks={self.num_weeks()})"


# ---------------------------------------------------------------------------
# Demo / test builder
# ---------------------------------------------------------------------------

def build_demo_sc_tree(
    sku_master: "pd.DataFrame",
    week_labels: List[str],
    lt_wks_ot: int = 1,
    lt_wks_in: int = 2,
    cpu_size:  int = 1,
) -> SCTree:
    from wom.data.schema import Cols

    tree = SCTree(week_labels)
    # cpu_size is plan-wide (Request Letter A: request_letter_a_cpu_size_to_plan.md),
    # so it is set once on the tree, not per PlanNode.
    tree.cpu_size = cpu_size
    skus = sku_master[Cols.SKU_ID].unique().tolist()

    for sku_id in skus:
        sku_rows = sku_master[sku_master[Cols.SKU_ID] == sku_id]
        regions  = sku_rows[Cols.REGION].tolist()

        # OutBound tree
        sp = PlanNode(
            node_id   = f"SP:{sku_id}",
            node_name = f"Supply Point [{sku_id}]",
            product   = sku_id,
            side      = "outbound",
            node_type = NODE_TYPE_SUPPLY_POINT,
            tier      = 0,
            lt_wks    = 0,
        )

        for region in regions:
            lt = int(
                sku_rows.loc[sku_rows[Cols.REGION] == region, Cols.LT_WKS]
                .values[0]
            ) if Cols.LT_WKS in sku_rows.columns else lt_wks_ot

            dad = PlanNode(
                node_id   = f"OUT:DC:{region}:{sku_id}",
                node_name = f"DC {region} [{sku_id}]",
                product   = sku_id,
                side      = "outbound",
                node_type = NODE_TYPE_DAD,
                tier      = 0,
                lt_wks    = max(lt, 1),
            )
            leaf_out = PlanNode(
                node_id   = f"OUT:Sales:{region}:{sku_id}",
                node_name = f"Sales {region} [{sku_id}]",
                product   = sku_id,
                side      = "outbound",
                node_type = NODE_TYPE_LEAF_OUT,
                tier      = 1,
                lt_wks    = 1,
            )
            dad.add_child(leaf_out)
            sp.add_child(dad)

        # InBound tree
        mom = PlanNode(
            node_id   = f"IN:MFG:{sku_id}",
            node_name = f"Mother Plant [{sku_id}]",
            product   = sku_id,
            side      = "inbound",
            node_type = NODE_TYPE_MOM,
            tier      = 0,
            lt_wks    = lt_wks_in,
        )
        tier1 = PlanNode(
            node_id   = f"IN:T1:{sku_id}",
            node_name = f"Tier-1 Supplier [{sku_id}]",
            product   = sku_id,
            side      = "inbound",
            node_type = NODE_TYPE_MOM,
            tier      = 1,
            lt_wks    = lt_wks_in,
        )
        raw_mat = PlanNode(
            node_id   = f"IN:RAW:{sku_id}",
            node_name = f"Raw Material [{sku_id}]",
            product   = sku_id,
            side      = "inbound",
            node_type = NODE_TYPE_LEAF_IN,
            tier      = 2,
            lt_wks    = 1,
        )
        tier1.add_child(raw_mat)
        mom.add_child(tier1)

        tree.register(sku_id, ot_root=sp, in_root=mom)

    tree.init_all_psi()
    return tree
