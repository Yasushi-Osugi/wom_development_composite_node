"""
wom/engine/backward_planner.py
================================
WOM Backward Planning Engine (Step 4)

Backward planning = Demand Allocation in ideal / unconstrained state.
CO (Carry Over) is NEVER generated here.

─────────────────────────────────────────────────────────────────────────────
Algorithm
─────────────────────────────────────────────────────────────────────────────

Phase 1 — OutBound POST-ORDER (leaf_out → DAD → supply_point)
    For each node (children before parent):
        psi4demand[w][P] = psi4demand[w][S]          (ideal: receive = ship)
        parent.psi4demand[w - node.lt_wks][S] +=     (parent ships lt_wks earlier)
            node.psi4demand[w][S]

    lt_wks on each node = transit time for goods to arrive FROM parent TO this node.
    So "parent must ship in week  w - node.lt_wks"  for this node to have goods in week w.

Phase 2 — Bridge  (supply_point → MOM, week by week)
    MOM.psi4demand[w][S] +=  supply_point.psi4demand[w][S]   for all w
    (Full WOM: market-priority allocation happens here.
     BackwardPlanner v1: 1-to-1 copy, allocation deferred to future step.)

Phase 3 — InBound PRE-ORDER (MOM → tier-1 → leaf_in)
    For each node (parent before children):
        psi4demand[w][P] = psi4demand[w][S]          (ideal: receive = ship)
        for each child:
            child.psi4demand[w - child.lt_wks][S] += (child ships lt_wks earlier)
                node.psi4demand[w][S]

    InBound lt_wks on child = transit time from child (supplier) to parent (MOM).
    So "child must ship in week  w - child.lt_wks"  for parent to have goods in week w.

─────────────────────────────────────────────────────────────────────────────
Lot-ID handling
─────────────────────────────────────────────────────────────────────────────

Lots that fall outside the planning horizon  (offset week < 0)  are
accumulated in BackwardPlanResult.past_due_lots — they represent demand
that would require procurement action BEFORE the planning horizon begins.

─────────────────────────────────────────────────────────────────────────────
v1r0m2: Holiday Calendar closure-week skip
─────────────────────────────────────────────────────────────────────────────

When HolidayCalendarPlugin runs on_pre_plan it writes
    config["explicit_closures"] = {node_name: set(week_idx)}
BackwardPlanner reads this via __init__(config=...) and uses _offset_week()
to skip closed weeks when stepping back by lt_wks, adding extra offset for
each closed week found in the range.

─────────────────────────────────────────────────────────────────────────────
v1r0m3: MOM Constrained Demand Allocation (Phase 3b)
─────────────────────────────────────────────────────────────────────────────

After Phase 3 (InBound PRE-ORDER), an additional backward pass is applied
to MOM nodes when config["mom_constrained"] is True (default).

    _apply_mom_cap_backward(mom_node, n_weeks, result)

For each MOM node (node_type == "mom") with cap_hard > 0:
  - psi4demand[w][P] is clipped to cap_hard(w) lots
  - psi4demand[w][S] is also updated to within_cap (so Phase 3 propagates
    only capped lots to child nodes)
  - Overflow lots → psi4demand[w][CO]  +  psi4demand[w-1][S]  (carry-back)

Processing order: Phase 3b runs BEFORE Phase 3 (_in_propagate) so that
the cap-clipped S is what _in_propagate propagates to child nodes.
This makes child.S[w-LT] match MOM.P[w] in shape (same staircase).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from wom.model.plan_node import PlanNode, S, CO, I, P
from wom.model.sc_tree   import SCTree
from wom.engine.lane_assignment import LaneTable


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BackwardPlanResult:
    """
    Summary of one backward planning pass for a single product.
    """
    prod_nm: str

    # Total lot-propagation events recorded
    ot_propagations: int = 0   # OutBound phase lot moves
    bridge_lots:     int = 0   # Lots transferred at supply_point -> MOM bridge
    in_propagations: int = 0   # InBound phase lot moves

    # Lots that fell before the planning horizon (offset week < 0)
    # key = (node_id, lot_id)
    past_due_lots: List[Tuple[str, str, int]] = field(default_factory=list)
    # (node_id, lot_id, original_week)

    # Per-node demand summary  node_id -> {week_label: {S, P} qty}
    node_summary: Dict[str, Dict[str, Dict[str, int]]] = field(
        default_factory=dict
    )

    # cap_soft envelope violations (plan-time overtime signal, Fork A).
    # (node_id, week_label, over_by) where over_by = min(demand, cap_hard) - cap_soft.
    # Placement is NOT changed by cap_soft; this is a flag only.
    cap_soft_envelope_violations: List[Tuple[str, str, int]] = field(
        default_factory=list
    )

    def record_past_due(self, node_id: str, lot_id: str, week: int) -> None:
        self.past_due_lots.append((node_id, lot_id, week))

    def record_cap_soft_envelope(
        self, node_id: str, week_label: str, over_by: int
    ) -> None:
        """Plan-time flag: production placed within cap_hard exceeds cap_soft
        (regular-shift ceiling) by ``over_by`` lots -> requires overtime/burst.
        Does NOT move any lots."""
        self.cap_soft_envelope_violations.append((node_id, week_label, over_by))

    def __str__(self) -> str:
        return (
            f"BackwardPlanResult[{self.prod_nm}]  "
            f"OT={self.ot_propagations}  bridge={self.bridge_lots}  "
            f"IN={self.in_propagations}  past_due={len(self.past_due_lots)}"
        )


# ---------------------------------------------------------------------------
# BackwardPlanner
# ---------------------------------------------------------------------------

class BackwardPlanner:
    """
    Runs the backward planning pass for one or all products in an SCTree.

    Usage
    -----
        planner = BackwardPlanner(sc_tree)
        result  = planner.run("SKU-A")

        # or for all products:
        results = planner.run_all()

    v1r0m3: mom_constrained mode
    ----------------------------
    When config["mom_constrained"] is True (default), _apply_mom_cap_backward
    runs before _in_propagate so that cap-clipped S is propagated to children.
    Pass config={"mom_constrained": False} to restore v1r0m2 behaviour
    (used by test_step7_capacity.py to test ForwardPlanner cap enforcement).
    """

    def __init__(self, sc_tree: SCTree,
                 lane_table: Optional[LaneTable] = None,
                 config: Optional[dict] = None) -> None:
        self.sc_tree    = sc_tree
        self.lane_table = lane_table or LaneTable.empty()
        # v1r0m2: explicit_closures from HolidayCalendarPlugin via config
        # Structure: {node_name: set(week_idx)} — weeks that are supply-closed.
        # BackwardPlanner uses this to skip closed weeks during LT offset calc.
        cfg = config or {}
        self._explicit_closures: Dict[str, set] = cfg.get("explicit_closures", {})
        # v1r0m3: MOM constrained demand allocation (default: True)
        self._mom_constrained: bool = cfg.get("mom_constrained", True)
        # v1r2m2 Phase 2: per-node operating calendar (op_shifts==0 => closed week).
        # Union the plugin-injected explicit_closures with each node's intrinsic
        # closed weeks, keyed by node_name, so _offset_week skips BOTH sources.
        # (No calendar / no closures => empty => behaviour identical to before.)
        self._closed_by_name: Dict[str, set] = self._build_closed_index(sc_tree)

    # ======================================================================
    # Public API
    # ======================================================================

    def run(self, prod_nm: str) -> BackwardPlanResult:
        """
        Execute the full backward planning pass for one product.

        Parameters
        ----------
        prod_nm:
            Product name (key in sc_tree.prod_tree_dict_OT/IN).

        Returns
        -------
        BackwardPlanResult
        """
        result = BackwardPlanResult(prod_nm=prod_nm)
        n_weeks = self.sc_tree.num_weeks()

        ot_root = self.sc_tree.get_ot_root(prod_nm)
        in_root = self.sc_tree.get_in_root(prod_nm)

        # -- Phase 1: OutBound POST-ORDER ----------------------------------
        for node in ot_root.walk_postorder():
            self._ot_propagate(node, n_weeks, result)

        # -- Phase 2: Bridge supply_point -> MOM (with Lane Assignment) ---
        in_roots = self.sc_tree.get_in_roots(prod_nm)  # {node_id: PlanNode}
        primary_mom = self.sc_tree.get_in_root(prod_nm)

        if self.lane_table.is_empty() or len(in_roots) == 1:
            # No lane table or single MOM -> original 1:1 bridge
            for w in range(n_weeks):
                transfer = self.sc_tree.bridge_backward(prod_nm, w)
                result.bridge_lots += len(transfer.lot_ids)
        else:
            # Multi-MOM: route each lot to its assigned MOM via LaneTable
            lot_leaf_index = self._build_lot_leaf_index(ot_root)
            for w in range(n_weeks):
                for lot_id in list(ot_root.psi4demand[w][S]):
                    # Resolve destination MOM: leaf_node_name first, region fallback
                    leaf      = lot_leaf_index.get(lot_id)
                    leaf_name = leaf.node_name if leaf else ""
                    # PlanNode has no .region attribute; extract from lot_id
                    # lot_id format: "{sku_id}:{region}:{week}:{seq}"
                    _parts = lot_id.split(":")
                    region = _parts[1] if len(_parts) >= 3 else ""
                    mom_id     = self.lane_table.resolve(prod_nm, leaf_name, region)
                    target_mom = in_roots.get(mom_id, primary_mom)
                    target_mom.add_lot_demand(w, S, lot_id)
                    result.bridge_lots += 1

        # -- Phase 3b: MOM constrained demand allocation (v1r0m3) ----------
        # Must run BEFORE Phase 3 (_in_propagate) so that the cap-clipped S
        # is what gets propagated to child nodes (TSMC_TW etc.).
        # After this pass:  MOM.S[w] = MOM.P[w] = within_cap (capped lots only)
        # _in_propagate will then propagate this capped S to child.S[w-LT].
        if self._mom_constrained:
            for mom_node in in_roots.values():
                self._apply_mom_cap_backward(mom_node, n_weeks, result)

        # -- Phase 3: InBound PRE-ORDER (all MOM roots) -------------------
        for mom_node in in_roots.values():
            for node in mom_node.walk_preorder():
                self._in_propagate(node, n_weeks, result)

        # -- Build node summary -------------------------------------------
        for node in self.sc_tree.iter_all_nodes(prod_nm):
            self._record_summary(node, result)

        return result

    def run_all(self) -> Dict[str, BackwardPlanResult]:
        """Run backward planning for every product in the SCTree."""
        return {
            prod_nm: self.run(prod_nm)
            for prod_nm in self.sc_tree.products
        }

    # ======================================================================
    # v1r0m2: LT offset with closure-week skip
    # ======================================================================

    def _build_closed_index(self, sc_tree: SCTree) -> Dict[str, set]:
        """
        Build node_name -> set(closed week_idx), unioning two sources:
          - self._explicit_closures  (plugin-injected, via config)
          - each node's intrinsic operating calendar (op_shifts[w] == 0)
        Only names with at least one closed week are stored (empty => no entry,
        so _offset_week falls back to plain week - lt_wks == unchanged behaviour).
        """
        idx: Dict[str, set] = {}
        for prod in sc_tree.products:
            for nd in sc_tree.iter_all_nodes(prod):
                closed = set(self._explicit_closures.get(nd.node_name, set()))
                ops = getattr(nd, "op_shifts", None)
                if ops:
                    for w_, s_ in enumerate(ops):
                        if s_ == 0:
                            closed.add(w_)
                if closed:
                    idx[nd.node_name] = closed
        return idx

    def _offset_week(self, week: int, lt_wks: int, node_name: str) -> int:
        """
        Compute the upstream week index by stepping back lt_wks weeks,
        skipping any explicitly-closed weeks for the given node.

        Example: lt=2, week=10, closure_weeks={9} for node_name
            → step back from 10: skip 9 (closed), count 8, count 7 → return 7

        If node_name has no closures, this is equivalent to week - lt_wks.
        """
        closure_set = self._closed_by_name.get(node_name, set())
        if not closure_set:
            return week - lt_wks

        remaining = lt_wks
        w = week - 1
        while remaining > 0 and w >= -(lt_wks * 2 + len(closure_set)):
            if w not in closure_set:
                remaining -= 1
            w -= 1
        return w + 1  # w was decremented one extra at loop exit

    # ======================================================================
    # Phase 1: OutBound propagation  (POST-ORDER)
    # ======================================================================

    def _ot_propagate(
        self,
        node:    PlanNode,
        n_weeks: int,
        result:  BackwardPlanResult,
    ) -> None:
        """
        For each lot in node.S[w]:
          1. Copy lot to node.P[w]            (ideal: receive = ship)
          2. Add lot to parent.S[w - lt_wks]  (parent ships lt_wks earlier)
        """
        for w in range(n_weeks):
            # Iterate over a snapshot (list copy) because parent.S may be
            # extended by earlier iterations in the same pass.
            for lot_id in list(node.psi4demand[w][S]):
                # -- P = S  (ideal backward) --------------------------------
                node.psi4demand[w][P].append(lot_id)

                # -- Propagate to parent ------------------------------------
                if node.parent is None:
                    # supply_point: no further parent on OT side
                    continue

                # v1r0m2: skip closure weeks of the parent node when stepping back
                # LT_offset(D2S) = B + X1 + X2   [OutBound Tree only]
                #   B  = lt_wks          : E2E lead time (physical, given)
                #   X1 = ss_wks          : safety stock (demand variability absorption)
                #   X2 = init_stock_wks  : warm-up / initial stock coverage [weeks]
                #
                # Decision 7 -- role split by Tree:
                #   InBound  Tree : bottleneck relief  -> push_lead_time_weeks (Mode 4)
                #   OutBound Tree : demand variability -> init_stock_wks (X2, here)
                # X2 is applied ONLY on the OutBound side, so the two mechanisms
                # never double-shift the same lane.
                #
                # X2 is a CONSTANT offset: it persists into steady state and is
                # treated as part of this node's inventory policy, not a transient.
                # Per-node from CSV; 0 = no warm-up (unchanged behaviour).
                parent_w = self._offset_week(
                    w,
                    node.lt_wks + node.ss_wks + node.init_stock_wks,
                    node.parent.node_name,
                )
                if parent_w < 0:
                    result.record_past_due(node.node_id, lot_id, w)
                elif parent_w < n_weeks:
                    node.parent.psi4demand[parent_w][S].append(lot_id)
                    result.ot_propagations += 1

    # ======================================================================
    # Phase 3: InBound propagation  (PRE-ORDER)
    # ======================================================================

    def _in_propagate(
        self,
        node:    PlanNode,
        n_weeks: int,
        result:  BackwardPlanResult,
    ) -> None:
        """
        For each lot in node.S[w]:
          1. Copy lot to node.P[w]        (P = S, full demand signal)
          2. For each child:
             child.S[w - LT_offset] += lot   (child ships LT weeks earlier,
                                               skipping closure weeks)

        v1r0m3: capacity clipping removed from this method.
        ---------------------------------------------------
        BackwardPlanner is a pure demand-propagation pass.
        cap_hard enforcement is handled by _apply_mom_cap_backward (MOM nodes)
        and will be extended to other node types in future versions.
        Upstream nodes receive the full unconstrained demand signal so that
        ForwardPlanner can use it for supply allocation decisions.

        v1r0m3: P update skipped for MOM nodes in mom_constrained mode.
        P was already set by _apply_mom_cap_backward (Phase 3b) which runs
        before this method. Appending again would double-count within_cap lots.

        A1 fix (request_fix_a1_supply_role_rev2.md): when a node has 2+
        children, they are grouped by `supply_role` before propagation
        (see _propagate_to_children below). Previously EVERY child received
        a full copy of `all_lots` regardless of sibling count, which is only
        correct for "assembly" (BOM) semantics; "confluence" siblings (same
        physical supply arriving via multiple routes) must instead SPLIT the
        demand, or the same Lot_ID is counted once per sibling downstream
        (see India Ghee A1: Ghee_Plant_Anand P_sum inflated to ~2x with two
        leaf_in children, later clipped by cap_hard into phantom CO).
        """
        for w in range(n_weeks):
            all_lots = list(node.psi4demand[w][S])

            # -- P = S  (record full demand signal) -------------------------
            # Skip for MOM nodes in mom_constrained mode: P was already set
            # by _apply_mom_cap_backward (Phase 3b runs before Phase 3).
            # Appending again would double-count within_cap lots in P.
            if not (self._mom_constrained and node.node_type == "mom"):
                for lot_id in all_lots:
                    node.psi4demand[w][P].append(lot_id)

            self._propagate_to_children(node, w, all_lots, n_weeks, result)

    def _propagate_to_children(
        self,
        node:     PlanNode,
        w:        int,
        all_lots: List[str],
        n_weeks:  int,
        result:   BackwardPlanResult,
    ) -> None:
        """
        Distribute one week's demand lots from `node` to its InBound children,
        grouped by each child's `supply_role` (A1 fix, request_fix_a1_supply_role_rev2.md).

            "assembly"   (default): each child gets the FULL lot list.
                          A future BOM quantity N (the "1 set rule", e.g. 4
                          tyres per vehicle) does NOT belong here: lot counts
                          stay 1:1 between parent and child so Lot_ID identity
                          is preserved (repeating `all_lots` would recreate
                          the exact same-Lot_ID-counted-twice bug this fix
                          removes -- see the owner's note on
                          request_fix_a1_supply_role_rev2.md). N instead
                          multiplies the physical quantity a lot represents
                          (capacity thresholds, cost formulas, KPI unit
                          counts, PPC display), e.g.
                          S_Qty[w] = len(psi[w][S]) * cpu_size * N --
                          entirely outside this lot-identity layer.
            "confluence": all confluence siblings SPLIT all_lots between them
                          (equal share + remainder, divmod-based contiguous
                          slice -- same idiom as push_pull.py's Mode4 leaf-in
                          distribution). A single confluence child (or a
                          single child overall) gets 100% of the lots, same
                          as today.

        `child_w` is computed per child (lt_wks/ss_wks can differ per child).
        """
        if not node.children:
            return

        confluence_children = [c for c in node.children if c.supply_role == "confluence"]
        assembly_children   = [c for c in node.children if c.supply_role != "confluence"]

        # -- assembly: full copy per child ---------------------------------
        for child in assembly_children:
            child_w = self._offset_week(w, child.lt_wks + child.ss_wks, child.node_name)
            if child_w < 0:
                for lot_id in all_lots:
                    result.record_past_due(child.node_id, lot_id, w)
            elif child_w < n_weeks:
                for lot_id in all_lots:
                    child.psi4demand[child_w][S].append(lot_id)
                result.in_propagations += len(all_lots)

        # -- confluence: split all_lots across siblings (equal + remainder) ---
        if confluence_children:
            n = len(confluence_children)
            base, remainder = divmod(len(all_lots), n)
            idx = 0
            for i, child in enumerate(confluence_children):
                take = base + (1 if i < remainder else 0)
                child_lots = all_lots[idx: idx + take]
                idx += take
                child_w = self._offset_week(w, child.lt_wks + child.ss_wks, child.node_name)
                if child_w < 0:
                    for lot_id in child_lots:
                        result.record_past_due(child.node_id, lot_id, w)
                elif child_w < n_weeks:
                    for lot_id in child_lots:
                        child.psi4demand[child_w][S].append(lot_id)
                    result.in_propagations += len(child_lots)

    # ======================================================================
    # Phase 3b: MOM constrained demand allocation (v1r0m3)
    # ======================================================================

    def _apply_mom_cap_backward(
        self,
        node:    PlanNode,
        n_weeks: int,
        result:  BackwardPlanResult,
    ) -> None:
        """
        v1r0m3: Constrained Demand Allocation for MOM nodes.

        Apply cap_hard clipping to psi4demand[w][P] at MOM nodes.
        Overflow lots (demand > cap_hard) are:
          - recorded in psi4demand[w][CO]      (unfulfilled in-week demand)
          - pushed back to psi4demand[w-1][S]  (earlier production request)

        Additionally, psi4demand[w][S] is updated to within_cap so that
        _in_propagate (Phase 3, which runs after this method) propagates
        only the capped lots to child nodes.  This makes child.S[w-LT]
        match MOM.P[w] in shape (same staircase waveform).

        Processing is backward (w = n_weeks-1 → 0) so that cascading
        carry-back is accumulated correctly:
            w=155 overflow → pushed to w=154 S
            w=154 overflow (original + carry) → pushed to w=153 S
            ...

        Design notes
        ------------
        - Only applied to nodes with node_type == "mom".
        - Child node propagation is NOT re-triggered after carry-back.
          (Full re-propagation is deferred to v1r0m4+.)
        - Week 0 overflow → recorded as past_due (no earlier week exists).
        """
        if node.node_type != "mom":
            return  # only apply to MOM nodes

        for w in range(n_weeks - 1, -1, -1):
            cap_w = node.cap_hard(w)
            ops = getattr(node, "op_shifts", None)
            is_closed = bool(ops) and ops[w] == 0   # Phase 2 Slice 2-3b: closed week
            if cap_w <= 0.0 and not is_closed:
                continue  # unconstrained week (cap not set)

            s_lots  = list(node.psi4demand[w][S])
            cs = node.cap_soft(w)
            # Fill target (Phase 2 Fork B, per-node demand_envelope):
            #   closed week       => 0  (holiday: produce nothing, carry back)
            #   "soft" + cap_soft => cap_soft  (leveled production; the excess is
            #                        pre-built into earlier weeks' slack)
            #   "hard" (default)  => cap_hard  (current behaviour)
            # cap_hard stays the physical ceiling; the overflow/carry-back logic
            # below is UNCHANGED and simply uses this target.
            if is_closed:
                cap_int = 0
            elif node.demand_envelope == "soft" and cs > 0:
                cap_int = int(cs)
            else:
                cap_int = int(cap_w)

            # -- cap_soft envelope flag (Fork A: flag only, NO lot movement) --
            # Active in "hard" mode where placed production may exceed cap_soft
            # (=> overtime band). In "soft" mode the fill target IS cap_soft, so
            # placed_p <= cap_soft and this never fires (soft = no overtime).
            if cs > 0:
                placed_p = min(len(s_lots), cap_int)
                if placed_p > int(cs):
                    wk_label = node.week_labels[w] if node.week_labels else str(w)
                    result.record_cap_soft_envelope(
                        node.node_id, wk_label, placed_p - int(cs))

            if len(s_lots) <= cap_int:
                continue  # no overflow this week

            # -- Clip P at cap_hard ----------------------------------------
            within_cap = s_lots[:cap_int]
            overflow   = s_lots[cap_int:]

            # Overwrite P: was set to full S by _in_propagate; now capped
            node.psi4demand[w][P].clear()
            node.psi4demand[w][P].extend(within_cap)

            # -- Record overflow as CO (unfulfilled demand this week) -------
            for lot_id in overflow:
                node.psi4demand[w][CO].append(lot_id)

            # -- Also update S to within_cap --------------------------------
            # _in_propagate (Phase 3) uses psi4demand[w][S] to propagate to
            # child nodes.  By updating S here, child.S[w-LT] will carry only
            # the cap-clipped lots, making child.S match MOM.P in shape.
            node.psi4demand[w][S].clear()
            node.psi4demand[w][S].extend(within_cap)

            # -- Push overflow to previous week S (earlier production) ------
            if w > 0:
                for lot_id in overflow:
                    node.psi4demand[w - 1][S].append(lot_id)
                result.in_propagations += len(overflow)
            else:
                # Week 0: no earlier week — record as past_due
                for lot_id in overflow:
                    result.record_past_due(node.node_id, lot_id, w)

    # ======================================================================
    # Multi-MOM lane routing helper
    # ======================================================================

    def _build_lot_leaf_index(self, ot_root: PlanNode) -> dict:
        """
        Build lot_id -> leaf_out PlanNode index for multi-MOM lane routing.

        Traverses the OT tree; for every leaf node (no children) records
        which lot_ids appear in psi4demand[w][S].  After Phase 1 OT
        propagation, each lot originated from exactly one leaf_out node.

        Used by run() Phase 2 to look up the leaf_out node for each lot
        arriving at supply_point, so its node_name can be passed to
        LaneTable.resolve() for exact-channel matching.
        """
        index: dict = {}
        for node in ot_root.walk_preorder():
            if not node.children:          # leaf_out nodes have no children
                for w_psi in node.psi4demand:
                    for lot_id in w_psi[S]:
                        index[lot_id] = node
        return index

    # ======================================================================
    # Summary helper
    # ======================================================================

    @staticmethod
    def _record_summary(
        node:   PlanNode,
        result: BackwardPlanResult,
    ) -> None:
        if not node.week_labels:
            return
        summary: Dict[str, Dict[str, int]] = {}
        for w, wk_label in enumerate(node.week_labels):
            s_qty = node.qty_demand(w, S)
            p_qty = node.qty_demand(w, P)
            i_qty = node.qty_demand(w, I)
            if s_qty or p_qty:
                summary[wk_label] = {"S": s_qty, "P": p_qty, "I": i_qty}
        if summary:
            result.node_summary[node.node_id] = summary
