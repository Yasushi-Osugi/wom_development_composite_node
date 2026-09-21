"""
wom/engine/push_pull.py
=======================
WOM Step 8 — PUSH / PULL Buffer Stock Switching

Overview
--------
PULL (default): demand-driven. psi4supply[P] at leaf_in is set by backward
demand propagation. Production = what demand needs.

PUSH: supply-driven. psi4supply[P] at leaf_in is set by a PUSH production
schedule (fixed weekly qty or buffer-replenishment formula), independent of
downstream demand. The entire InBound sub-chain below the decoupling node
acts as a pass-through pipeline — each node ships ALL available supply upward
so that the decoupling node (MOM) accumulates buffer inventory.

plan_mode values
----------------
"pull"     : default, demand-driven (OutBound + PULL InBound nodes)
"push"     : decoupling node (MOM) — receives push supply, ships to demand,
             holds buffer inventory
"push_sub" : InBound nodes BELOW the decoupling node — ship ALL available
             supply upward (no demand-side gate)

Execution order (per planning cycle)
-------------------------------------
    Step 4  BackwardPlanner.run()          fills psi4demand (demand truth)
    Step 5  copy_demand_to_supply()        psi4supply <- copy of psi4demand
    Step 8  PushProductionPlanner.setup()  overwrite leaf_in P + mark modes
    Step 6  ForwardPlanner.run()           propagates from leaf_in forward

PushProductionPlanner.setup() MUST run between Step 5 and Step 6.

PUSH production modes
---------------------
Mode 1 - Fixed quantity  (push_qty_per_week > 0):
    leaf_in.psi4supply[w][P] = push_qty_per_week lots for every week w.

Mode 2 - Replenishment-to-buffer  (push_qty_per_week == 0, no LT):
    Simulate rolling inventory at MOM:
        I[0]    = buffer_lots  (start at full buffer)
        push[w] = max(buffer_lots - I_prev + demand_w, 0)
        I[w]    = max(I_prev + push[w] - demand_w, 0)

Mode 3 - Time-phased (pre_build_qty_per_week > 0 AND pre_build_end_week set):
    Phase 1 (w <= pre_build_end_week): fixed pre_build_qty_per_week
        -> buffer accumulates intentionally (差分が積み上がる: pre-build intent)
    Phase 2 (w > pre_build_end_week): classic order-up-to replenishment
        from decoupling node itself (staircase signal, no further accumulation)

Mode 4 - LT-shifted demand  (push_lead_time_weeks > 0):
    push[w] = demand_ref_node.psi4demand[w + LT][S]
    When w + LT >= n_weeks: produce 0 (natural EOL stop).

    This single parameter captures the full DBR buffer lifecycle:
      - Pre-build : weeks where demand[w+LT] > 0 but demand[w] = 0
                    -> production starts LT weeks before demand arrives
      - Steady    : production = staircase = consumption (buffer flat)
      - Staircase : production steps DOWN LT weeks BEFORE consumption steps
                    -> buffer absorbs the LT-week gap at each step
      - EOL stop  : demand[w+LT] = 0 -> production = 0, LT weeks before
                    last demand week -> buffer depletes to 0 at lifecycle end

    IMPORTANT (2028-07-13, per user correction on WOM's core Lot_ID
    principle): Lot_IDs are minted exactly ONCE, up front, at initial
    planning (assign_demand_lots_from_dict) -- never fabricated mid-plan.
    Mode 4's leaf-in assignment therefore does NOT mint new Lot_IDs; it
    re-times the EXISTING Lot_IDs already sitting at
    demand_ref_node.psi4demand[w+LT][S] (see setup(), the
    is_lt_shifted_mode() branch). Modes 1-3 remain anonymous PUSH-to-stock
    schedules (no single future demand event to anchor to) and still mint
    fresh Lot_IDs via LotIDGenerator -- see the KNOWN LIMITATION note in
    setup() for the downstream-matching caveat this implies for those modes.

Region-proportional lot assignment
------------------------------------
PUSH lots must carry region tags to route correctly through SP -> DAD in
ForwardPlanner._propagate_to_child. Distribution uses TOTAL regional demand
ratio (sum across all weeks) so every production week is tagged correctly.
(Modes 1-3 only -- Mode 4 lots already carry their original region tag,
inherited from the reused Lot_ID.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from wom.model.plan_node import (
    PlanNode, S, CO, I, P,
    NODE_TYPE_LEAF_IN, NODE_TYPE_LEAF_OUT, NODE_TYPE_MOM,
)
from wom.model.sc_tree      import SCTree
from wom.model.lot_generator import LotIDGenerator

# plan_mode constants
PULL_MODE     = "pull"
PUSH_MODE     = "push"
PUSH_SUB_MODE = "push_sub"


@dataclass
class PushConfig:
    """
    PUSH production configuration for one decoupling node.

    node_id                : node_id of the decoupling node (MOM/InBound root)
    push_qty_per_week      : fixed lots/week  (Mode 1; 0 = other modes)
    buffer_lots            : target buffer inventory (Mode 2/3 replenishment)
    sku_id                 : SKU for lot-ID generation (inferred if empty)
    mode_only              : True = set plan_mode flags ONLY; skip P-schedule.
    mom_ref_node_id        : demand signal node for Mode 2/4 replenishment.
                             Default "" = decoupling node itself (staircase).
                             Set to Foxconn_CN for raw-demand signal (pre-v1r0m2).
    pre_build_qty_per_week : Mode 3 Phase-1 fixed qty (lots/week).
    pre_build_end_week     : Mode 3 Phase-1 end week label (e.g. "2026-W52").
    push_lead_time_weeks   : Mode 4 — LT offset (weeks).
                             push[w] = demand_ref_node.psi4demand[w+LT][S]
                             Implements the full DBR buffer lifecycle:
                               pre-build -> steady -> staircase gap absorption
                               -> natural EOL stop -> buffer depletes to 0.
                             Priority over Mode 3 when both are set.
    push_eol_week          : Mode 1 EOL stop — week label after which push[w]=0.
                             e.g. "2027-W06" means production stops at that week.
                             Computed from: ceil(total_demand / push_qty_per_week).
                             Ignored when push_qty_per_week == 0.
    """
    node_id:                str
    push_qty_per_week:      int  = 0
    buffer_lots:            int  = 0
    sku_id:                 str  = ""
    mode_only:              bool = False
    mom_ref_node_id:        str  = ""
    pre_build_qty_per_week: int  = 0
    pre_build_end_week:     str  = ""
    push_lead_time_weeks:   int  = 0
    push_eol_week:          str  = ""

    def is_fixed_mode(self) -> bool:
        return self.push_qty_per_week > 0

    def is_lt_shifted_mode(self) -> bool:
        return self.push_lead_time_weeks > 0

    def is_time_phased_mode(self) -> bool:
        return (
            self.pre_build_qty_per_week > 0
            and bool(self.pre_build_end_week)
            and not self.is_lt_shifted_mode()
        )

    def effective_sku(self) -> str:
        if self.sku_id:
            return self.sku_id
        parts = self.node_id.split(":")
        return parts[-1] if len(parts) >= 3 else self.node_id


@dataclass
class PushSetupResult:
    prod_nm:         str
    mode:            str  = "fixed"
    push_lots_total: int  = 0
    push_events:     List[Tuple[str, str, int]] = field(default_factory=list)

    def record(self, node_id: str, week_label: str, qty: int) -> None:
        self.push_events.append((node_id, week_label, qty))
        self.push_lots_total += qty

    def __str__(self) -> str:
        return (
            f"PushSetupResult[{self.prod_nm}]  mode={self.mode}  "
            f"push_lots={self.push_lots_total}  events={len(self.push_events)}"
        )


class PushProductionPlanner:
    """
    Overwrites psi4supply[P] on leaf_in nodes with PUSH lots and sets
    plan_mode flags on the InBound subtree.

    Run AFTER copy_demand_to_supply, BEFORE ForwardPlanner.run.
    """

    def __init__(
        self,
        sc_tree:       SCTree,
        lot_generator: Optional[LotIDGenerator] = None,
    ) -> None:
        self.sc_tree       = sc_tree
        self.lot_generator = lot_generator or LotIDGenerator()

    def setup(self, prod_nm: str, config: PushConfig) -> PushSetupResult:
        n_weeks = self.sc_tree.num_weeks()
        result  = PushSetupResult(
            prod_nm = prod_nm,
            mode    = (
                "fixed"       if config.is_fixed_mode()       else
                "lt_shifted"  if config.is_lt_shifted_mode()  else
                "time_phased" if config.is_time_phased_mode() else
                "replenishment"
            ),
        )

        # 1. Locate decoupling node
        decoupling_node = self._find_node(prod_nm, config.node_id)
        if decoupling_node is None:
            raise ValueError(
                f"Decoupling node {config.node_id!r} not found for {prod_nm!r}"
            )

        # 1b. Demand reference node
        demand_ref_node = decoupling_node
        if config.mom_ref_node_id and not config.is_lt_shifted_mode():
            _ref = self._find_node(prod_nm, config.mom_ref_node_id)
            if _ref is not None:
                demand_ref_node = _ref
            else:
                import warnings
                warnings.warn(
                    f"[PushPull] mom_ref_node_id={config.mom_ref_node_id!r} "
                    f"not found for {prod_nm!r}; falling back to decoupling node."
                )

        # 2. Set plan_mode flags
        decoupling_node.is_decoupling = True
        decoupling_node.plan_mode     = PUSH_MODE

        # Nodes BELOW decoupling (leaf_in side) -> PUSH_SUB (feed buffer)
        for node in decoupling_node.walk_preorder():
            if node is not decoupling_node:
                node.plan_mode = PUSH_SUB_MODE

        # Nodes ABOVE decoupling (toward MOM root) -> PUSH_SUB (PUSH forward pass)
        # Buffer_Wafer_TW.S drives TSMC_TW.P -> Foxconn_CN.P as pass-through.
        _up = decoupling_node.parent
        while _up is not None:
            _up.plan_mode = PUSH_SUB_MODE
            _up = _up.parent

        # 5. Leaf-in assignment
        leaf_in_nodes = [
            node for node in decoupling_node.walk_preorder()
            if node.node_type == NODE_TYPE_LEAF_IN
        ]
        if not leaf_in_nodes:
            raise ValueError(f"No leaf_in nodes under {config.node_id!r}")

        if config.mode_only:
            return result

        sku_id   = config.effective_sku()
        n_leaves = len(leaf_in_nodes)

        if config.is_lt_shifted_mode():
            # Mode 4 -- Lot_ID-identity-preserving re-timing.
            #
            # WOM principle (2028-07-13, per user correction): Lot_IDs are
            # minted exactly ONCE, up front, at initial planning
            # (assign_demand_lots_from_dict) -- never fabricated mid-plan.
            # The original _lt_shifted_schedule()/_generate_regional_lots()
            # combination violated this: it read
            # demand_ref_node.psi4demand[w+LT][S] only to COUNT how many
            # lots were needed, discarded that list, and then minted
            # brand-new Lot_IDs (via LotIDGenerator) carrying the
            # PRODUCTION week instead of the original DEMAND week.
            # Downstream OutBound PULL nodes (SP/DAD/leaf_out) still hold
            # the ORIGINAL demand-anchored Lot_IDs and match supply by
            # strict Lot_ID identity (_match_by_identity in
            # forward_planner.py) -- so the freshly-minted lots could never
            # satisfy them, and OutBound Carry-Over grew without bound even
            # though InBound Carry-Over was fixed and aggregate volumes
            # balanced (see data/sample/apparel-global-2028-2029/verify/
            # README.md for the full diagnosis).
            #
            # Fix: re-time the EXISTING Lot_IDs instead of creating new
            # ones. leaf_in's P at week w becomes the exact same Lot_ID
            # list already sitting at demand_ref_node.psi4demand[w+LT][S]
            # -- i.e. "produce these specific lots earlier," not "produce
            # some other lots of the same quantity."
            ref = demand_ref_node if demand_ref_node is not None else decoupling_node
            lt_weeks = config.push_lead_time_weeks

            # Bug fix (2026-08-30, per Request Letter
            # request_fix_mode4_double_count.md): Step 5
            # (copy_demand_to_supply) deep-copies psi4demand[P] into
            # psi4supply[P] for EVERY week of every node, including these
            # leaf_in nodes. The loop below only overwrites the specific
            # weeks it actually re-times (w such that
            # ref.psi4demand[w+lt_weeks][S] is non-empty); any other week
            # was left holding that Step-5 "natural" (non-shifted) copy.
            # Since the natural copy sits at week (d - tau) -- tau being
            # this leaf_in's own cumulative transit offset (lt_wks +
            # ss_wks) back to the decoupling node -- and this loop places
            # the SAME Lot_IDs at week (d - lt_weeks), the two land on
            # different weeks whenever lt_weeks != tau, duplicating every
            # Lot_ID across two weeks and inflating this leaf_in's P_sum
            # (confirmed by tools/sweep_specs/apparel_s1_lt3.yaml -- P_sum
            # returns exactly to baseline only at the coincidental
            # lt_weeks == tau point). Clearing every week up front, for
            # ONLY the leaf_in nodes this mode is about to (re)populate,
            # restores the intended "re-timing, not duplication" semantics
            # without touching any other node or PUSH mode.
            for leaf_node in leaf_in_nodes:
                for w in range(n_weeks):
                    leaf_node.psi4supply[w][P] = []

            # Bug fix (2026-09-04, Request Letter
            # request_fix_mode4_supply_role_semantics.md): Mode4 must not
            # re-decide WHO supplies each lot -- BackwardPlanner already did,
            # via supply_role ("assembly" siblings each get the full demand
            # list; "confluence" siblings split it -- see
            # backward_planner._propagate_to_children). The contiguous
            # divmod(len(lots), n_leaves) slicing this replaces was written
            # before supply_role existed and re-allocates as if every
            # leaf_in were an interchangeable confluence producer, which
            # silently turns "assembly" BOM components (e.g. Battery+Motor+
            # ECU, each needing the FULL lot list) into a 1/n split --
            # confirmed on ev-europe-2026 / Factory_Import_HU via Kitting
            # Stage 1 (kitting complete = 0 / 7,945; every lot missing 2 of
            # its 3 required components).
            #
            # Canonical rule: Backward decides WHO; Mode4 decides WHEN only.
            # WHO = each leaf_in's own horizon-wide psi4demand[*][S]
            # membership (the recipient set BackwardPlanner already fixed
            # for it -- looked up across ALL weeks, not just future_w,
            # because a leaf's own lt_wks/ss_wks/closure offset can place
            # the same Demand Anchored Lot_ID at a different week than the
            # reference node's own demand week). No second supply_role
            # branch is added here -- this reads Backward's decision back
            # as a fact, it does not recompute the policy.
            leaf_membership: Dict[str, set] = {}
            for leaf_node in leaf_in_nodes:
                membership: set = set()
                for dw in range(n_weeks):
                    membership.update(leaf_node.psi4demand[dw][S])
                leaf_membership[leaf_node.node_id] = membership

            for w in range(n_weeks):
                future_w = w + lt_weeks
                future_lots = list(ref.psi4demand[future_w][S]) if future_w < n_weeks else []
                if not future_lots:
                    continue
                wk_label = self.sc_tree.week_labels[w]

                # WHEN only: re-time each leaf's own (Backward-assigned)
                # lots to this production week, preserving future_lots order.
                # Identity is preserved throughout -- no LotIDGenerator call.
                for leaf_node in leaf_in_nodes:
                    membership = leaf_membership[leaf_node.node_id]
                    leaf_lots = [lot_id for lot_id in future_lots if lot_id in membership]
                    if not leaf_lots:
                        continue
                    leaf_node.psi4supply[w][P] = list(leaf_lots)
                    result.record(leaf_node.node_id, wk_label, len(leaf_lots))
            return result

        # Modes 1-3 (fixed / replenishment / time-phased): these are
        # anonymous PUSH-to-stock schedules with no single future demand
        # event to anchor to, so they still mint fresh Lot_IDs via
        # LotIDGenerator. KNOWN LIMITATION (2028-07-13): if the decoupling
        # node bridges (directly or via push_sub pass-through) into an
        # OutBound chain that does Lot_ID-identity PULL matching, these
        # modes will hit the same downstream-matching gap Mode 4 had --
        # not fixed in this pass; see verify/README.md.
        # 3. Compute push quantities
        push_qtys = self._compute_push_quantities(
            decoupling_node, config, n_weeks, demand_ref_node
        )

        # 4. Regional distribution
        region_totals = self._compute_region_totals(prod_nm, n_weeks)

        for w in range(n_weeks):
            total_qty = push_qtys[w]
            wk_label  = self.sc_tree.week_labels[w]
            if total_qty <= 0:
                continue

            # Leaf-in P = PUSH production schedule (feeds the buffer)
            base, remainder = divmod(total_qty, n_leaves)

            for leaf_idx, leaf_node in enumerate(leaf_in_nodes):
                leaf_qty = base + (1 if leaf_idx < remainder else 0)
                if leaf_qty <= 0:
                    continue

                lots = self._generate_regional_lots(
                    sku_id, wk_label, leaf_qty, region_totals
                )
                leaf_node.psi4supply[w][P] = lots
                result.record(leaf_node.node_id, wk_label, len(lots))

        return result

    def setup_all(
        self,
        push_configs: Dict[str, PushConfig],
    ) -> Dict[str, PushSetupResult]:
        return {
            prod_nm: self.setup(prod_nm, cfg)
            for prod_nm, cfg in push_configs.items()
        }

    # ------------------------------------------------------------------
    # Push quantity calculation
    # ------------------------------------------------------------------

    def _compute_push_quantities(
        self,
        decoupling_node:  PlanNode,
        config:           PushConfig,
        n_weeks:          int,
        demand_ref_node:  Optional[PlanNode] = None,
    ) -> List[int]:
        if config.is_fixed_mode():
            qty  = config.push_qty_per_week
            # Mode 1 + EOL stop: production = 0 from push_eol_week onward
            eol_idx = -1
            if config.push_eol_week:
                week_labels = self.sc_tree.week_labels
                for i, lbl in enumerate(week_labels):
                    if lbl >= config.push_eol_week:
                        eol_idx = i
                        break
            if eol_idx < 0:
                return [qty] * n_weeks
            return [qty if w < eol_idx else 0 for w in range(n_weeks)]
        if config.is_lt_shifted_mode():
            ref = demand_ref_node if demand_ref_node is not None else decoupling_node
            return self._lt_shifted_schedule(ref, config.push_lead_time_weeks, n_weeks)
        if config.is_time_phased_mode():
            return self._time_phased_schedule(decoupling_node, config, n_weeks)
        ref = demand_ref_node if demand_ref_node is not None else decoupling_node
        return self._replenishment_schedule(ref, config.buffer_lots, n_weeks)

    def _lt_shifted_schedule(
        self,
        demand_ref_node: PlanNode,
        lt_weeks:        int,
        n_weeks:         int,
    ) -> List[int]:
        """
        Mode 4 — LT-shifted demand schedule (QUANTITY-ONLY variant).

        Retained for backward compatibility / result.mode reporting and
        any external caller that only needs the count. NOT used by
        setup()'s actual leaf-in assignment anymore for Mode 4 -- see the
        is_lt_shifted_mode() branch in setup(), which reuses the EXISTING
        Lot_ID list directly instead of just this count (2028-07-13 fix).

        push[w] = len(demand_ref_node.psi4demand[w + lt_weeks][S])
        When w + lt_weeks >= n_weeks: push[w] = 0  (natural EOL stop).
        """
        schedule: List[int] = []
        for w in range(n_weeks):
            future_w = w + lt_weeks
            qty = len(demand_ref_node.psi4demand[future_w][S]) if future_w < n_weeks else 0
            schedule.append(qty)
        return schedule

    def _time_phased_schedule(
        self,
        decoupling_node: PlanNode,
        config:          PushConfig,
        n_weeks:         int,
    ) -> List[int]:
        """
        Mode 3 — two-phase schedule.
        Phase 1 (w <= pre_build_end_week): fixed pre_build_qty_per_week.
        Phase 2 (w > pre_build_end_week):  classic order-up-to replenishment.
        """
        week_labels = self.sc_tree.week_labels
        cutoff = n_weeks
        for i, label in enumerate(week_labels):
            if label > config.pre_build_end_week:
                cutoff = i
                break

        schedule: List[int] = [config.pre_build_qty_per_week] * min(cutoff, n_weeks)

        I_prev = config.buffer_lots
        for w in range(cutoff, n_weeks):
            demand_w = len(decoupling_node.psi4demand[w][S])
            deficit  = max(config.buffer_lots - I_prev + demand_w, 0)
            push_w   = deficit
            I_w      = max(I_prev + push_w - demand_w, 0)
            schedule.append(push_w)
            I_prev = I_w

        return schedule

    def _replenishment_schedule(
        self,
        mom:         PlanNode,
        buffer_lots: int,
        n_weeks:     int,
    ) -> List[int]:
        """
        Mode 2 — classic order-up-to replenishment.
        push[w] = max(buffer_lots - I_prev + demand_w, 0)
        I[w]    = max(I_prev + push[w] - demand_w, 0)
        I_prev starts at buffer_lots (buffer assumed full).
        """
        schedule: List[int] = []
        I_prev = buffer_lots

        for w in range(n_weeks):
            demand_w = len(mom.psi4demand[w][S])
            deficit  = max(buffer_lots - I_prev + demand_w, 0)
            push_w   = deficit
            I_w      = max(I_prev + push_w - demand_w, 0)
            schedule.append(push_w)
            I_prev = I_w

        return schedule

    # ------------------------------------------------------------------
    # Regional distribution helpers
    # ------------------------------------------------------------------

    def _compute_region_totals(
        self,
        prod_nm: str,
        n_weeks: int,
    ) -> Dict[str, int]:
        ot_root       = self.sc_tree.get_ot_root(prod_nm)
        region_totals: Dict[str, int] = {}

        for node in ot_root.walk_preorder():
            if node.node_type != NODE_TYPE_LEAF_OUT:
                continue
            region = _extract_region_from_node_id(node.node_id)
            if not region:
                continue
            total_qty = sum(len(node.psi4demand[w][S]) for w in range(n_weeks))
            region_totals[region] = region_totals.get(region, 0) + total_qty

        return region_totals

    def _generate_regional_lots(
        self,
        sku_id:     str,
        wk_label:   str,
        total_qty:  int,
        region_map: Dict[str, int],
    ) -> List[str]:
        if not region_map or sum(region_map.values()) == 0:
            return self.lot_generator.generate(sku_id, "PUSH", wk_label, total_qty)

        regions      = list(region_map.keys())
        total_demand = sum(region_map.values())
        lots: List[str] = []
        remaining = total_qty

        for idx, region in enumerate(regions):
            if idx == len(regions) - 1:
                count = remaining
            else:
                fraction = region_map[region] / total_demand
                count    = max(round(total_qty * fraction), 0)
                remaining -= count

            if count > 0:
                lots += self.lot_generator.generate(sku_id, region, wk_label, count)

        return lots

    # ------------------------------------------------------------------
    # Node lookup
    # ------------------------------------------------------------------

    def _find_node(self, prod_nm: str, node_id: str) -> Optional[PlanNode]:
        """Find node by node_id (full) or node_name (short name in CSV)."""
        for node in self.sc_tree.iter_all_nodes(prod_nm):
            if node.node_id == node_id or node.node_name == node_id:
                return node
        return None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def mark_pull_mode(sc_tree: SCTree, prod_nm: str, node_id: str) -> None:
    for node in sc_tree.iter_all_nodes(prod_nm):
        if node.node_id == node_id:
            node.is_decoupling = False
            node.plan_mode     = PULL_MODE
            for child in node.walk_preorder():
                if child is not node:
                    child.plan_mode = PULL_MODE
            return
    raise ValueError(f"Node {node_id!r} not found for product {prod_nm!r}")


def get_push_pull_summary(sc_tree: SCTree, prod_nm: str) -> List[dict]:
    return [
        {
            "node_id":       node.node_id,
            "side":          node.side,
            "node_type":     node.node_type,
            "plan_mode":     node.plan_mode,
            "is_decoupling": node.is_decoupling,
        }
        for node in sc_tree.iter_all_nodes(prod_nm)
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_region_from_node_id(node_id: str) -> Optional[str]:
    parts = node_id.split(":")
    if len(parts) >= 4 and parts[0] in ("OUT", "IN"):
        return parts[2]
    return None
