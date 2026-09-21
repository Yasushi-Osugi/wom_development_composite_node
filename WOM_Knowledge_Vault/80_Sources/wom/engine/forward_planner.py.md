---
tags: [wom, code]
---
# wom/engine/forward_planner.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/forward_planner.py) · [原文テキスト](../../../90_Raw/wom/engine/forward_planner.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/03_Planning|Planning]]

## モジュール説明（docstring原文）

```text
wom/engine/forward_planner.py
==============================
WOM Forward Planning Engine (Step 6)

Operates on psi4supply (psi4demand is never modified here).
Generates CO when supply falls short of demand.
Applies capacity constraints (Step 7 CapHard/CapSoft).
Respects PUSH/PULL mode flags (Step 8).

plan_mode handling
------------------
"pull"     : normal PSI roll-forward (demand-constrained shipment)
"push"     : decoupling node (MOM) -- normal PSI; holds buffer inventory
"push_sub" : InBound pass-through -- ship ALL available supply upward;
             no demand-side gate; I always = 0 at these nodes

Algorithm
---------
Preparation
    Clear psi4supply[w][P] on derived nodes (rebuilt during forward pass).
    Source P kept: leaf_in (push or pull), supply_point (filled by bridge).

Phase 1 -- InBound POST-ORDER (leaf_in -> tier-1 -> MOM)
    Step 0a: CapHard seal P[w]; excess -> CO[w+1]
    Step 0b: CapSoft check (flag only)
    PSI:
        push_sub: s_plan = available (ship everything upward)
        others  : normal CO+S demand calculation

Phase 2 -- Bridge MOM -> supply_point
    SP.psi4supply[w][P] = list(MOM.psi4supply[w][S])

Phase 3 -- OutBound PRE-ORDER (supply_point -> DAD -> leaf_out)
    Same capacity + PSI logic as Phase 1 (all OT nodes are "pull").

Lot routing (OutBound)
----------------------
Each lot is Demand Anchored: its destination leaf_out is fixed at lot-generation
time and encoded in the lot_id.  _propagate_to_child routes each lot by walking
the lot's leaf_out node upward via .parent pointers until it reaches the direct
child of the current parent node.  No node_id parsing is required.
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| ClassDef | `ForwardPlanResult` | 69 | docstringなし（下のコード参照） |
| ClassDef | `ForwardPlanner` | 122 | Runs the forward planning pass for one or all products in an SCTree. |
| FunctionDef | `record_kitting_fallback` | 96 | docstringなし（下のコード参照） |
| FunctionDef | `record_shortfall` | 99 | docstringなし（下のコード参照） |
| FunctionDef | `record_cap_hard_sealed` | 103 | docstringなし（下のコード参照） |
| FunctionDef | `record_cap_soft_violation` | 108 | docstringなし（下のコード参照） |
| FunctionDef | `__str__` | 111 | docstringなし（下のコード参照） |
| FunctionDef | `__init__` | 134 | docstringなし（下のコード参照） |
| FunctionDef | `run` | 145 | docstringなし（下のコード参照） |
| FunctionDef | `run_all` | 276 | docstringなし（下のコード参照） |
| FunctionDef | `_run_ot_push_pull` | 283 | Apply push_pull_all_psi2i_decouple4supply5 logic to the OT tree. |
| FunctionDef | `_push_pull_node` | 314 | Recursively process one OT node. |
| FunctionDef | `_pull_subtree` | 355 | PULL mode: overwrite psi4supply[w][P] with psi4demand[w][P] |
| FunctionDef | `_clear_derived_p` | 376 | Clear P on derived nodes (rebuilt by forward propagation). |
| FunctionDef | `_match_by_identity` | 401 | Match demand-side Lot_IDs (CO[w] + S[w]) against supply-side Lot_IDs |
| FunctionDef | `_process_node` | 437 | Compute psi4supply[I]/[CO] and the "actual shipped" set for one node |
| FunctionDef | `_process_assembly_with_yards` | 569 | Joint, week-interleaved processing for an assembly (mom) node whose |
| FunctionDef | `_get_demand_week_index` | 692 | Kitting List stage 1 (request_kitting_stage1.md): lazily build/cache |
| FunctionDef | `_propagate_to_parent` | 719 | InBound: child's ACTUAL shipment[w] -> parent P[w + node.transit_lt_wks]. |
| FunctionDef | `_propagate_to_child` | 766 | OutBound: parent S[w] -> child P[w + child.lt_wks]. |
| FunctionDef | `_build_lot_leaf_index` | 827 | Build {lot_id: leaf_out_node} from psi4demand[w][S] of all leaf_out nodes. |

## 関連する知識源

- [[80_Sources/wom/model/plan_node.py|wom/model/plan_node.py]]
- [[80_Sources/wom/model/sc_tree.py|wom/model/sc_tree.py]]
- [[80_Sources/wom/model/lot_generator.py|wom/model/lot_generator.py]]

## 全文（コメント・原文を省略せず収録）

````python
"""
wom/engine/forward_planner.py
==============================
WOM Forward Planning Engine (Step 6)

Operates on psi4supply (psi4demand is never modified here).
Generates CO when supply falls short of demand.
Applies capacity constraints (Step 7 CapHard/CapSoft).
Respects PUSH/PULL mode flags (Step 8).

plan_mode handling
------------------
"pull"     : normal PSI roll-forward (demand-constrained shipment)
"push"     : decoupling node (MOM) -- normal PSI; holds buffer inventory
"push_sub" : InBound pass-through -- ship ALL available supply upward;
             no demand-side gate; I always = 0 at these nodes

Algorithm
---------
Preparation
    Clear psi4supply[w][P] on derived nodes (rebuilt during forward pass).
    Source P kept: leaf_in (push or pull), supply_point (filled by bridge).

Phase 1 -- InBound POST-ORDER (leaf_in -> tier-1 -> MOM)
    Step 0a: CapHard seal P[w]; excess -> CO[w+1]
    Step 0b: CapSoft check (flag only)
    PSI:
        push_sub: s_plan = available (ship everything upward)
        others  : normal CO+S demand calculation

Phase 2 -- Bridge MOM -> supply_point
    SP.psi4supply[w][P] = list(MOM.psi4supply[w][S])

Phase 3 -- OutBound PRE-ORDER (supply_point -> DAD -> leaf_out)
    Same capacity + PSI logic as Phase 1 (all OT nodes are "pull").

Lot routing (OutBound)
----------------------
Each lot is Demand Anchored: its destination leaf_out is fixed at lot-generation
time and encoded in the lot_id.  _propagate_to_child routes each lot by walking
the lot's leaf_out node upward via .parent pointers until it reaches the direct
child of the current parent node.  No node_id parsing is required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from wom.model.plan_node import PlanNode, S, CO, I, P, NODE_TYPE_LEAF_IN, NODE_TYPE_STOCKYARD
from wom.model.sc_tree   import SCTree
from wom.model.lot_generator import LotIDGenerator


# Kitting Gate switch (request_kitting_stage1.md §3.7; enabled by
# request_stage3a2_kitting_gate.md). When True, an assembly (mom) node whose
# direct children are ALL node_type=="stockyard" is processed by
# _process_assembly_with_yards() instead of the normal per-child
# _propagate_to_parent extend -- only a Lot_ID present in EVERY sibling
# Yard's I bucket (a set intersection, not a quantity) is paid out, exactly
# once, into the assembly's own P. Trees with no stockyard nodes take
# exactly the same code path as before this flag existed (the condition
# that selects _process_assembly_with_yards is `stockyard_children`, which
# is empty for every model that predates Stage 3a).
KITTING_GATE_ENABLED = True


@dataclass
class ForwardPlanResult:
    prod_nm:        str
    ot_processed:   int = 0
    in_processed:   int = 0
    bridge_lots:    int = 0
    co_generated:   int = 0
    shortfall_weeks: List[tuple] = field(default_factory=list)

    # Step 7
    cap_hard_sealed: int = 0
    cap_hard_events: List[tuple] = field(default_factory=list)
    cap_soft_violations: List[tuple] = field(default_factory=list)

    # Ready kits deferred BEFORE component consumption. Weekly counts, not
    # unique orders; unlike sealing, this does not add another CO entry.
    kitting_capacity_deferred: List[tuple] = field(default_factory=list)

    # Kitting List stage 1 (request_kitting_stage1.md §1 owner review):
    # count of lot_ids that could NOT be found in the parent's own
    # backward-planned demand (psi4demand[*][S]) when recording kitting, so
    # arrival_week (target_w) was used as the assembly_week fallback instead
    # of the parent's demand week. See ForwardPlanner._get_demand_week_index.
    # Under Demand Anchored design this should normally be 0; a nonzero count
    # is a signal worth investigating (e.g. opening_inv-seeded lots that never
    # passed through BackwardPlanner demand propagation), not a silent no-op.
    kitting_fallback_events: List[tuple] = field(default_factory=list)

    def record_kitting_fallback(self, node_id, week_label, lot_id):
        self.kitting_fallback_events.append((node_id, week_label, lot_id))

    def record_shortfall(self, node_id, week_label, count):
        self.shortfall_weeks.append((node_id, week_label, count))
        self.co_generated += count

    def record_cap_hard_sealed(self, node_id, week_label, count):
        self.cap_hard_events.append((node_id, week_label, count))
        self.cap_hard_sealed += count
        self.co_generated    += count

    def record_cap_soft_violation(self, node_id, week_label, over_by):
        self.cap_soft_violations.append((node_id, week_label, over_by))

    def __str__(self):
        return (
            f"ForwardPlanResult[{self.prod_nm}]  "
            f"IN={self.in_processed}  OT={self.ot_processed}  "
            f"bridge={self.bridge_lots}  CO={self.co_generated}  "
            f"cap_hard_sealed={self.cap_hard_sealed}  "
            f"cap_soft_violations={len(self.cap_soft_violations)}  "
            f"kitting_fallback={len(self.kitting_fallback_events)}"
        )


class ForwardPlanner:
    """
    Runs the forward planning pass for one or all products in an SCTree.

    Usage:
        fp     = ForwardPlanner(sc_tree)
        result = fp.run("SKU-A")
        results = fp.run_all()

    opening_inv: {node_id: [lot_id, ...]} -- pre-horizon inventory seed.
    """

    def __init__(
        self,
        sc_tree:              SCTree,
        opening_inv:          Optional[Dict[str, List[str]]] = None,
        decouple_node_ids:    Optional[set]                  = None,
    ) -> None:
        self.sc_tree             = sc_tree
        self.opening_inv         = opening_inv or {}
        self.decouple_node_ids   = decouple_node_ids  # None = auto-detect
        self._lot_leaf_index: Dict[str, PlanNode] = {}

    def run(self, prod_nm: str) -> ForwardPlanResult:
        result  = ForwardPlanResult(prod_nm=prod_nm)
        n_weeks = self.sc_tree.num_weeks()

        ot_root  = self.sc_tree.get_ot_root(prod_nm)
        in_roots = self.sc_tree.get_in_roots(prod_nm)  # Dict[node_id, PlanNode]

        self._clear_derived_p(in_roots, ot_root, n_weeks)
        # {node_id: {w: [lot, ...]}} -- Lot_IDs ACTUALLY shipped this week at
        # every node (identity-matched against physical availability).
        # Kept separate from psi4supply[w][S]/[CO], which always hold the
        # PLANNED/demand-anchored record and are never overwritten by the
        # fulfillment outcome. All downstream physical propagation
        # (_propagate_to_parent / _propagate_to_child / MOM->supply_point
        # bridge) reads from this dict, not from psi4supply[w][S].
        self._actual_s: Dict[str, Dict[int, List[str]]] = {}
        # Kitting List stage 1 (request_kitting_stage1.md): per-parent cache
        # of {lot_id: assembly_week}, lazily built from the parent's own
        # psi4demand[*][S] -- see _get_demand_week_index. Reset per run() so
        # a stale index from a previous product/run is never reused.
        self._kitting_week_index: Dict[str, Dict[str, int]] = {}

        # Phase 1: InBound POST-ORDER (all MOM roots)
        #
        # InBound PUSH/PULL decouple design (v1r0m2):
        #   Upstream of is_decoupling node  → PUSH (propagation-driven)
        #   At is_decoupling node           → Demand-S copy: override P with
        #                                     psi4demand[w][P] (demand-anchored)
        #   Downstream of is_decoupling     → InBound PULL: P = demand[P]
        #
        # This prevents buffer accumulation at the decoupling node (Buffer.I→0)
        # while keeping the upstream leaf_in in PUSH mode.
        for mom_root in in_roots.values():
            in_pull_mode = False   # False = PUSH; True = demand-anchored PULL
            for node in mom_root.walk_postorder():
                # Stage 3a-2 (request_stage3a2_kitting_gate.md): a stockyard
                # node's own P/S/I is decided jointly with its siblings when
                # its assembly parent is visited below (postorder guarantees
                # the parent comes after every child, including this one) --
                # skip its own _process_node/_propagate_to_parent entirely.
                if KITTING_GATE_ENABLED and node.node_type == NODE_TYPE_STOCKYARD:
                    result.in_processed += 1
                    continue

                stockyard_children = (
                    [c for c in node.children if c.node_type == NODE_TYPE_STOCKYARD]
                    if KITTING_GATE_ENABLED else []
                )

                # Demand-S copy at decouple node, or InBound PULL downstream.
                # plan_mode=="push" MOM nodes are excluded: their P is set by
                # upstream PUSH propagation (_propagate_to_parent) and must NOT be
                # overwritten with demand[P], otherwise PUSH buffer inventory is lost.
                if ((node.is_decoupling or in_pull_mode)
                        and node.node_type != NODE_TYPE_LEAF_IN
                        and node.plan_mode != "push"):
                    for w in range(n_weeks):
                        node.psi4supply[w][P] = list(node.psi4demand[w][P])

                opening = list(self.opening_inv.get(node.node_id, []))
                if stockyard_children:
                    self._process_assembly_with_yards(
                        node, stockyard_children, n_weeks, result, opening_lots=opening)
                else:
                    self._process_node(node, n_weeks, result, opening_lots=opening)
                result.in_processed += 1

                if node.is_decoupling and node.plan_mode == "push":
                    # PUSH decoupling node: propagate ACTUAL lots (not display S) to parent.
                    # psi4supply[w][S] = demand_staircase (maintained for display/CO visibility).
                    # actual_s = min(available, demand) -- physically shipped to TSMC_TW etc.
                    #
                    # Kitting List stage 1 (request_kitting_stage1.md): NOT recorded here.
                    # This inline extend is a second, separate propagation path from
                    # _propagate_to_parent below and does not update parent.kitting.
                    # No current model combines is_decoupling+push with an assembly
                    # parent, so this is out of scope for stage 1 -- but it means a
                    # stage-3 assembly parent fed (even partially) through THIS path
                    # would see its kitting stay empty for that child's contribution
                    # (mis-detected as "missing", not "not applicable"). Needs explicit
                    # handling before stage 3 gate keeping is enabled on such a tree.
                    if node.parent is not None:
                        actual_by_w = self._actual_s.get(node.node_id, {})
                        for w in range(n_weeks):
                            actual_s = actual_by_w.get(w, [])
                            if actual_s:
                                target_w = w + node.lt_wks
                                if 0 <= target_w < n_weeks:
                                    node.parent.psi4supply[target_w][P].extend(actual_s)
                elif node.is_decoupling:
                    # Non-PUSH decoupling: upstream nodes become demand-anchored PULL
                    in_pull_mode = True
                elif not in_pull_mode and node.parent is not None:
                    # Normal PUSH_SUB propagation (e.g. SiliconWafer_TW -> Buffer)
                    self._propagate_to_parent(node, n_weeks, result)

        # Phase 2: Bridge ALL MOM roots -> supply_point
        # Uses _actual_s (physically-matched shipment), NOT psi4supply[w][S]
        # (which is the planned/demand-anchored record and may exceed what a
        # capacity-constrained MOM can actually ship).
        for w in range(n_weeks):
            all_lots: list = []
            for mom_root in in_roots.values():
                all_lots.extend(self._actual_s.get(mom_root.node_id, {}).get(w, []))
            ot_root.psi4supply[w][P] = all_lots
            result.bridge_lots += len(all_lots)

        # Phase 3: OutBound PUSH/PULL
        # Build lot -> leaf_out index once before traversal.
        self._lot_leaf_index = self._build_lot_leaf_index(ot_root)

        # Resolve decouple nodes:
        #   1. Explicit set passed by caller (highest priority)
        #   2. is_decoupling flag from CSV (buffering_stock_flag column)
        #   3. Fallback: auto-detect all 'dad' nodes (backward compat for older CSVs)
        if self.decouple_node_ids is not None:
            decouple_ids = set(self.decouple_node_ids)
        else:
            flag_nodes = {
                n.node_id for n in ot_root.walk_preorder()
                if n.is_decoupling
            }
            decouple_ids = flag_nodes if flag_nodes else {
                n.node_id for n in ot_root.walk_preorder()
                if n.node_type == "dad"
            }

        self._run_ot_push_pull(ot_root, decouple_ids, n_weeks, result)

        return result

    def run_all(self) -> Dict[str, ForwardPlanResult]:
        return {p: self.run(p) for p in self.sc_tree.products}

    # ------------------------------------------------------------------
    # Phase 3: OutBound PUSH / PULL (push_pull_all_psi2i_decouple4supply5)
    # ------------------------------------------------------------------

    def _run_ot_push_pull(self, ot_root, decouple_ids, n_weeks, result):
        """
        Apply push_pull_all_psi2i_decouple4supply5 logic to the OT tree.

        Reproduces the original PySI 4-step decouple design:

        The decouple point is NOT fixed to DAD -- it is any node designated in
        decouple_ids (equivalent to original PySI's decouple_nodes parameter).
        Typical choices include DAD (DC buffer), leaf_out (VMI / consignment),
        or any intermediate node in the SC lane.

            Step 1+3 (PUSH at decouple node):
                _process_node(decouple) runs with actual supply from upstream.
                decouple.I > 0 when supply surplus; CO when supply short.
                (In WOM lot-based: supply.S is already demand-anchored by
                 copy_demand_to_supply(), so _process_node handles both steps
                 in one pass -- equivalent to original calcPS2I + copy_S + PUSH.)

            Step 4 (PULL at all descendants of decouple node):
                Descendants receive demand-anchored supply:
                    psi4supply[w][P] = psi4demand[w][P]
                _process_node then fully satisfies each node's demand,
                hiding any decouple-level CO from downstream nodes.
                (Equivalent to apply_pull_process() in original PySI.)

        Supply propagation summary:
            upstream  -> _propagate_to_child -> decouple.P  (PUSH: actual supply)
            decouple  -> (no propagation)    -> child.P     (PULL: demand.P copied)
        """
        self._push_pull_node(ot_root, decouple_ids, n_weeks, result)

    def _push_pull_node(self, node, decouple_ids, n_weeks, result, pull_mode=False):
        """
        Recursively process one OT node.

        pull_mode=False (default): PUSH -- uses supply.P as set by _propagate_to_child
                                   (actual supply from parent).
        pull_mode=True:            PULL -- overrides supply.P with demand.P before
                                   processing (demand-anchored, original PySI Step 4).

        decouple_ids drives the PUSH->PULL transition.  Any node whose node_id
        is in decouple_ids becomes the buffer/decouple point: it is processed
        with PUSH (real supply), while all its descendants switch to PULL.
        The node_type (DAD etc.) has no bearing on this decision.
        """
        if pull_mode:
            # Original PySI Step 4 (apply_pull_process equivalent):
            # Demand-anchor this node's P so _process_node sees full demand supply.
            # supply.S is already demand-anchored from copy_demand_to_supply().
            for w in range(n_weeks):
                node.psi4supply[w][P] = list(node.psi4demand[w][P])

        opening = list(self.opening_inv.get(node.node_id, []))
        self._process_node(node, n_weeks, result, opening_lots=opening)
        result.ot_processed += 1

        # Is THIS node the designated decouple/buffer point?
        # Determined solely by decouple_ids -- NOT by node_type.
        # (decouple_ids is set by ForwardPlanner caller or auto-detected as
        #  all DAD nodes when decouple_node_ids is None in __init__.)
        is_decouple = (node.node_id in decouple_ids)

        for child in node.children:
            if not pull_mode and not is_decouple:
                # PUSH: propagate actual supply (S[w]) to child's P[w + lt_wks]
                self._propagate_to_child(node, child, n_weeks)
            # In pull_mode or is_decouple: do NOT call _propagate_to_child.
            # Child's P will be overwritten with demand.P at the top of the next
            # recursive call (pull_mode=True branch above).
            self._push_pull_node(child, decouple_ids, n_weeks, result,
                                 pull_mode=pull_mode or is_decouple)

    def _pull_subtree(self, node, n_weeks, result):
        """
        PULL mode: overwrite psi4supply[w][P] with psi4demand[w][P]
        (the backward-planned demand lots, P=S at each node from _ot_propagate),
        then calcPS2I.  For leaf_out: P = demand = S -> I = 0, flat demand PSI.
        Recurse for deeper subtrees.
        """
        for w in range(n_weeks):
            node.psi4supply[w][P] = list(node.psi4demand[w][P])

        opening = list(self.opening_inv.get(node.node_id, []))
        self._process_node(node, n_weeks, result, opening_lots=opening)
        result.ot_processed += 1

        for child in node.children:
            self._pull_subtree(child, n_weeks, result)

    # ------------------------------------------------------------------
    # Preparation
    # ------------------------------------------------------------------

    def _clear_derived_p(self, in_roots, ot_root, n_weeks):
        """
        Clear P on derived nodes (rebuilt by forward propagation).
        Source nodes whose P is KEPT:
            leaf_in  -- external supply (PULL demand or PUSH schedule)
            supply_point -- P filled by bridge in Phase 2

        in_roots: Dict[node_id, PlanNode] -- all MOM roots for this product.
        """
        for mom_root in in_roots.values():
            for node in mom_root.walk_preorder():
                if node.node_type != NODE_TYPE_LEAF_IN:
                    for w in range(n_weeks):
                        node.psi4supply[w][P] = []

        for node in ot_root.walk_preorder():
            if node is not ot_root:
                for w in range(n_weeks):
                    node.psi4supply[w][P] = []

    # ------------------------------------------------------------------
    # Core node processing
    # ------------------------------------------------------------------

    @staticmethod
    def _match_by_identity(demand_lots: List[str], supply_lots: List[str]):
        """
        Match demand-side Lot_IDs (CO[w] + S[w]) against supply-side Lot_IDs
        (I[w-1] + P[w]) by Lot_ID IDENTITY -- not by position/count.

        This reproduces the original PySI push_pull engine's
        calcPS2I4supply()/fifo_lot_diff() design (pysi/network/node_base.py),
        generalized to also match CO by identity (not just S).

        Returns
        -------
        matched:            Lot_IDs present in both -- these physically ship
                             this week. This becomes psi4supply[w]'s "actual"
                             shipment (see ForwardPlanner._actual_s), used for
                             downstream propagation. psi4supply[w][S] itself
                             is NEVER overwritten with this value.
        unmatched_demand:   Demanded Lot_IDs with no physical backing this
                             week -- carried forward as next week's CO[w+1]
                             (a genuine, Lot_ID-specific shortfall).
        unmatched_supply:   Physically-available Lot_IDs not yet claimed by
                             any demand this week -- becomes this week's I[w]
                             (inventory / early-arrival safety-stock buffer).
        """
        supply_set = set(supply_lots)
        matched: List[str] = []
        unmatched_demand: List[str] = []
        matched_set = set()
        for lot in demand_lots:
            if lot in supply_set and lot not in matched_set:
                matched.append(lot)
                matched_set.add(lot)
            else:
                unmatched_demand.append(lot)
        unmatched_supply = [lot for lot in supply_lots if lot not in matched_set]
        return matched, unmatched_demand, unmatched_supply

    def _process_node(self, node, n_weeks, result, opening_lots):
        """
        Compute psi4supply[I]/[CO] and the "actual shipped" set for one node
        across all weeks.

        Step 0a  CapHard sealing: P[w] truncated to cap_hard; excess -> CO[w+1]
        Step 0b  CapSoft check: flag if P[w] > cap_soft (no movement)

        PSI formula (normal / PULL) -- Lot_ID IDENTITY matching:
            available   = I[w-1] + P[w]
            demand_lots = CO[w] + S[w]
            matched, unmatched_demand, unmatched_supply =
                _match_by_identity(demand_lots, available)

            I[w]   = unmatched_supply     (early-arrival / surplus buffer)
            CO[w+1] += unmatched_demand   (genuine, Lot_ID-specific shortfall)
            actual_s[w] = matched         (drives downstream propagation)

            S[w] and CO[w] are NEVER overwritten -- they remain the
            planned/demand-anchored record (from copy_demand_to_supply /
            CapHard sealing). "Plan" and "actual fulfillment" are kept in
            separate channels; see ForwardPlanner._actual_s.

        PSI formula (push_sub -- InBound pass-through):
            s_plan = available          (ship ALL supply upward)
            -> always I=0, no CO generated, actual_s = available
        """
        prev_inv_lots: List[str] = list(opening_lots)
        is_push_sub  = (node.plan_mode == "push_sub")
        is_push_mode = (node.plan_mode == "push")    # PUSH decoupling (Buffer_Wafer_TW等)

        for w in range(n_weeks):
            wk_label = node.week_labels[w] if node.week_labels else str(w)

            # Step 0a: CapHard sealing
            # PUSH decoupling nodes (e.g. Buffer_Wafer_TW) skip sealing:
            # their P bucket holds incoming inventory (already produced upstream),
            # not production at this node. Surplus P flows to I via PUSH_MODE logic.
            ch = node.cap_hard(w)
            if not is_push_mode and ch > 0 and len(node.psi4supply[w][P]) > int(ch):
                excess = node.psi4supply[w][P][int(ch):]
                node.psi4supply[w][P] = node.psi4supply[w][P][:int(ch)]
                if w + 1 < n_weeks:
                    node.psi4supply[w + 1][CO].extend(excess)
                result.record_cap_hard_sealed(node.node_id, wk_label, len(excess))

            # Step 0b: CapSoft check
            cs = node.cap_soft(w)
            if cs > 0 and len(node.psi4supply[w][P]) > int(cs):
                result.record_cap_soft_violation(
                    node.node_id, wk_label,
                    len(node.psi4supply[w][P]) - int(cs),
                )

            # Supply side
            p_lots    = list(node.psi4supply[w][P])
            available = prev_inv_lots + p_lots

            # Demand side
            if is_push_mode:
                # PUSH decoupling node (e.g. Buffer_Wafer_TW):
                #   S = demand_staircase (display signal -- NOT reduced on shortage)
                #   Each week is INDEPENDENT: no CO cascade.
                #   Shortage bar = per-week Action-TODO signal for the operator.
                #   (CO cascade caused exponential snowball and is not meaningful
                #    for PUSH nodes that have their own production schedule.)
                s_plan    = list(node.psi4supply[w][S])   # demand_staircase
                node.psi4supply[w][CO] = []               # no CO carry-forward
                avail_cnt = len(available)
                total_cnt = len(s_plan)
                actual_s  = available[:total_cnt]         # lots physically shipped

                if avail_cnt >= total_cnt:
                    node.psi4supply[w][I] = available[total_cnt:]  # surplus -> buffer
                else:
                    node.psi4supply[w][I] = []
                    shortfall_cnt = total_cnt - avail_cnt
                    if shortfall_cnt:
                        result.record_shortfall(node.node_id, wk_label, shortfall_cnt)

                # Store actual_s for parent propagation (separate from display S)
                nid = node.node_id
                if nid not in self._actual_s:
                    self._actual_s[nid] = {}
                self._actual_s[nid][w] = actual_s

                # Record shortage count on node for Debugger visualization
                if not hasattr(node, '_push_shortfall'):
                    node._push_shortfall = {}
                node._push_shortfall[w] = max(0, total_cnt - avail_cnt)

                prev_inv_lots = node.psi4supply[w][I]
                continue

            nid = node.node_id
            if nid not in self._actual_s:
                self._actual_s[nid] = {}

            if is_push_sub:
                # PUSH sub-node: ship ALL available supply upward.
                # No demand gate; inventory stays at zero. S[w] here has no
                # separate "planned" meaning (no demand list to match against),
                # so it continues to display the same value that is shipped.
                node.psi4supply[w][S] = list(available)
                node.psi4supply[w][I] = []
                self._actual_s[nid][w] = list(available)
                prev_inv_lots         = []
                continue

            # -- Normal / PULL: Lot_ID identity matching -----------------
            # S[w] and CO[w] are read but NEVER overwritten here -- they
            # stay as the planned/demand-anchored record.
            co_lots     = list(node.psi4supply[w][CO])
            s_plan      = list(node.psi4supply[w][S])
            demand_lots = co_lots + s_plan

            matched, unmatched_demand, unmatched_supply = self._match_by_identity(
                demand_lots, available)

            node.psi4supply[w][I] = unmatched_supply
            prev_inv_lots         = unmatched_supply
            self._actual_s[nid][w] = matched

            if unmatched_demand:
                if (w + 1) < n_weeks:
                    node.psi4supply[w + 1][CO].extend(unmatched_demand)
                result.record_shortfall(node.node_id, wk_label, len(unmatched_demand))

    # ------------------------------------------------------------------
    # Stage 3a-2 Kitting Gate (request_stage3a2_kitting_gate.md)
    # ------------------------------------------------------------------

    def _process_assembly_with_yards(self, node, yard_children, n_weeks, result, opening_lots):
        """
        Joint, week-interleaved processing for an assembly (mom) node whose
        direct children are all node_type=="stockyard" pass-through buffers.

        Must be interleaved week-by-week -- NOT "let every yard accumulate
        its whole horizon independently, then gate afterward" -- because
        each yard's carried-forward inventory for week w+1 is whatever the
        SAME week's gate did not consume at week w. Two separate full-
        horizon passes cannot express that dependency.

        Per week:
          1. Each yard's raw arrivals (already placed in yard.psi4supply[w][P]
             by its own leaf_in child's ordinary _propagate_to_parent call,
             earlier in this same postorder walk -- unchanged) are added to
             that yard's carried-forward inventory.
          2. For normal pull/all-yard assembly, retain uncompleted requests
             across weeks in original order, exclude opening/produced finished
             IDs, and apply hard capacity BEFORE any component consumption.
             Other configurations retain the legacy current-demand gate.
             For each eligible lot_id
             present in the Lot_ID-identity INTERSECTION of every yard's
             current inventory (not a quantity comparison -- see the
             Request Letter §2.1 for why quantity would let unrelated Lots
             be mixed into one kit), pay it out: remove it from every
             yard's inventory, record it as that yard's actual shipment
             (kitting + _actual_s, using the exact same {child_name:
             arrival_week} shape _propagate_to_parent already used in
             Stage 1), and append it -- ONCE -- to node's own P. A lot_id
             not in the intersection, or waiting for capacity, retains its
             available components in their yards this week and,
             being absent from node's P, resolves as node's own CO through
             the ordinary _process_node identity match run at the end of
             this method.

        Deliberate departure from the "S is planned, never overwritten"
        invariant that holds for every OTHER node type: a stockyard's own
        S is not a demand-anchored plan copy here -- it IS the gate's
        actual payout record, which is the whole point of the design (see
        Request Letter §2.3). copy_demand_to_supply() still seeds it with
        the demand-mirror "natural copy" beforehand; that value is
        deliberately discarded (cleared) below before the gate writes the
        real one.
        """
        for w in range(n_weeks):
            node.psi4supply[w][P] = []          # defensive: rebuild from scratch
        for yard in yard_children:
            for w in range(n_weeks):
                yard.psi4supply[w][S] = []       # discard the Step-5 "planned" copy

        demand_week_idx = self._get_demand_week_index(node)
        yard_prev_inv: Dict[str, List[str]] = {yard.node_id: [] for yard in yard_children}

        # RequestLetter_Composite_Kitting_Backlog_v1.md: scope the change to
        # normal assembly with ALL children represented by component yards.
        recover_kits = node.plan_mode == "pull" and len(yard_children) == len(node.children)
        pending: Dict[str, None] = {}  # insertion order: older requirements first
        completed = set(opening_lots)

        for w in range(n_weeks):
            wk_label = node.week_labels[w] if node.week_labels else str(w)

            for yard in yard_children:
                arrivals = list(yard.psi4supply[w][P])
                yard.psi4supply[w][I] = yard_prev_inv[yard.node_id] + arrivals
                # Kitting record: on EVERY fresh arrival, independent of the
                # gate outcome below -- this is the diagnostic half (Stage 1
                # semantics: "who delivered when"), which must keep working
                # for lots that never complete, not just the ones that do.
                for lot_id in arrivals:
                    assembly_w = demand_week_idx.get(lot_id)
                    if assembly_w is None:
                        assembly_w = w
                        result.record_kitting_fallback(node.node_id, wk_label, lot_id)
                    node.kitting[assembly_w].setdefault(lot_id, {})[yard.node_name] = w

            intersection = set(yard_children[0].psi4supply[w][I])
            for yard in yard_children[1:]:
                intersection &= set(yard.psi4supply[w][I])

            if recover_kits:
                for lot_id in list(node.psi4supply[w][CO]) + list(node.psi4demand[w][S]):
                    if lot_id not in completed:
                        pending.setdefault(lot_id, None)
                candidates = list(pending)
                ch = node.cap_hard(w)
                remaining = int(ch) if ch > 0 else len(candidates)
            else:
                candidates = list(node.psi4demand[w][S])
                remaining = len(candidates)

            deferred = 0
            if intersection:
                for lot_id in candidates:
                    if lot_id not in intersection:
                        continue
                    if recover_kits and remaining == 0:
                        deferred += 1
                        continue
                    for yard in yard_children:
                        yard.psi4supply[w][I].remove(lot_id)
                        yard.psi4supply[w][S].append(lot_id)
                        self._actual_s.setdefault(
                            yard.node_id, {}).setdefault(w, []).append(lot_id)
                    node.psi4supply[w][P].append(lot_id)
                    intersection.discard(lot_id)
                    if recover_kits:
                        remaining -= 1
                        completed.add(lot_id)
                        pending.pop(lot_id)

            if deferred:
                result.kitting_capacity_deferred.append((node.node_id, wk_label, deferred))

            for yard in yard_children:
                yard_prev_inv[yard.node_id] = list(yard.psi4supply[w][I])

        self._process_node(node, n_weeks, result, opening_lots=opening_lots)

    # ------------------------------------------------------------------
    # Supply propagation helpers
    # ------------------------------------------------------------------

    def _get_demand_week_index(self, parent: PlanNode) -> Dict[str, int]:
        """
        Kitting List stage 1 (request_kitting_stage1.md): lazily build/cache
        {lot_id: assembly_week} from parent.psi4demand[*][S].

        This is the week BackwardPlanner fixed as "when parent needs this
        lot" (see backward_planner._propagate_to_children: all assembly
        siblings receive the SAME all_lots from the SAME parent week `w`,
        even though each child's own child_w -- and later, each child's own
        forward-plan shipment week -- can differ). It is therefore the
        correct shared key for grouping sibling deliveries of the same lot,
        unlike each child's own arrival_week (target_w in
        _propagate_to_parent), which is per-child and can diverge when one
        sibling is capacity-delayed relative to another.

        psi4demand is never written by ForwardPlanner, so this mapping is
        stable for the whole forward pass; cached per parent.node_id.
        """
        idx = self._kitting_week_index.get(parent.node_id)
        if idx is None:
            idx = {}
            for w, wk in enumerate(parent.psi4demand):
                for lot_id in wk[S]:
                    idx.setdefault(lot_id, w)
            self._kitting_week_index[parent.node_id] = idx
        return idx

    def _propagate_to_parent(self, node, n_weeks, result=None):
        """InBound: child's ACTUAL shipment[w] -> parent P[w + node.transit_lt_wks].

        Uses transit_lt_wks (physical transport time) NOT lt_wks (demand planning LT).
        For PUSH_SUB nodes (e.g. SiliconWafer_TW in Taiwan), transit is ~1 week
        while lt_wks=26 is used only by BackwardPlanner for pre-build demand scheduling.

        Reads from self._actual_s (Lot_ID-identity-matched physical shipment),
        NOT psi4supply[w][S] (the planned/demand-anchored record -- see
        _process_node / _match_by_identity).

        Kitting List stage 1 (request_kitting_stage1.md): alongside the
        existing P extend (UNCHANGED, unconditional -- this stage never
        withholds a lot), records who-delivered-what into parent.kitting for
        every child whose supply_role != "confluence" (confluence siblings
        split the same-kind demand between them -- there is no "must all be
        present" concept to record). `result`, when given, receives a
        kitting_fallback event whenever a lot_id cannot be found in the
        parent's own demand (see _get_demand_week_index) -- expected to be
        rare/zero under Demand Anchored design; not a silent no-op.
        """
        parent = node.parent
        if parent is None:
            return
        actual_by_w   = self._actual_s.get(node.node_id, {})
        record_kitting = (node.supply_role != "confluence")
        demand_week_idx = self._get_demand_week_index(parent) if record_kitting else None
        for w in range(n_weeks):
            confirmed_s = actual_by_w.get(w, [])
            if not confirmed_s:
                continue
            tlt = node.transit_lt_wks if node.transit_lt_wks > 0 else node.lt_wks
            target_w = w + tlt
            if 0 <= target_w < n_weeks:
                parent.psi4supply[target_w][P].extend(confirmed_s)
                if record_kitting:
                    wk_label = node.week_labels[w] if node.week_labels else str(w)
                    for lot_id in confirmed_s:
                        assembly_w = demand_week_idx.get(lot_id)
                        if assembly_w is None:
                            assembly_w = target_w
                            if result is not None:
                                result.record_kitting_fallback(
                                    parent.node_id, wk_label, lot_id)
                        parent.kitting[assembly_w].setdefault(
                            lot_id, {})[node.node_name] = target_w

    def _propagate_to_child(self, parent, child, n_weeks):
        """
        OutBound: parent S[w] -> child P[w + child.lt_wks].

        Each lot is Demand Anchored - its destination leaf_out is fixed at
        lot-generation time.  Routing uses parent pointers:

            leaf_out  ->  .parent  ->  ...  ->  child  ->  parent

        For each lot, walk up from its leaf_out node via .parent until
        reaching the direct child of parent.  If that node IS child,
        the lot belongs to this child's subtree and is routed here.

        When parent has only one child, all lots flow through unconditionally
        (no routing decision needed).

        Reads from self._actual_s (Lot_ID-identity-matched physical shipment),
        NOT psi4supply[w][S] (the planned/demand-anchored record -- see
        _process_node / _match_by_identity).
        """
        actual_by_w = self._actual_s.get(parent.node_id, {})

        if len(parent.children) == 1:
            # Single child: all lots belong here -- no routing needed
            for w in range(n_weeks):
                confirmed_s = actual_by_w.get(w, [])
                if not confirmed_s:
                    continue
                target_w = w + child.lt_wks
                if 0 <= target_w < n_weeks:
                    child.psi4supply[target_w][P].extend(confirmed_s)
            return

        # Multiple children: route by walking parent pointers from each lot's leaf_out
        for w in range(n_weeks):
            confirmed_s = actual_by_w.get(w, [])
            if not confirmed_s:
                continue

            matched = []
            for lot in confirmed_s:
                leaf = self._lot_leaf_index.get(lot)
                if leaf is None:
                    continue
                node = leaf
                while node is not None and node.parent is not parent:
                    node = node.parent
                if node is child:
                    matched.append(lot)

            if not matched:
                continue
            target_w = w + child.lt_wks
            if 0 <= target_w < n_weeks:
                child.psi4supply[target_w][P].extend(matched)

    # ------------------------------------------------------------------
    # Lot-leaf index (built once per product before Phase 3)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_lot_leaf_index(ot_root):
        """Build {lot_id: leaf_out_node} from psi4demand[w][S] of all leaf_out nodes."""
        index = {}
        for node in ot_root.walk_preorder():
            if not node.children:
                for w_psi in node.psi4demand:
                    for lot_id in w_psi[S]:
                        index[lot_id] = node
        return index


````
