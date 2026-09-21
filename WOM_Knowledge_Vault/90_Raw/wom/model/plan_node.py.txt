"""
wom/model/plan_node.py
======================
WOM Planning Layer -- PlanNode dataclass

PSI Bucket index convention (confirmed):
    S  = 0   Sales / Fulfilled shipment
    CO = 1   Carry Over (受注残) -- unfulfilled demand rolled forward
    I  = 2   Inventory
    P  = 3   Purchase / Production plan (replenishment)

    psi4demand[week_idx][bucket] = list[lot_ID: str]
    psi4supply[week_idx][bucket] = list[lot_ID: str]
    capacity[week_idx][0: CapHard, 1: CapSoft] = float

CO generation rules:
  v1r0m2: CO generated ONLY in Forward Planning when I+P < S demand.
  v1r0m3: BackwardPlanner also generates CO at MOM nodes when demand > cap_hard.
          psi4demand[w][CO] = overflow lots carried back to psi4demand[w-1][S].

Tier numbering:
    tier = 0  ->  closest to supply_point
    tier increases toward leaf (farthest from supply_point)

    OutBound example:
        supply_point   (bridge)
        L- DAD         tier=0  (出荷ヤード)
           L- ...      tier=1  (域内倉庫)
              L- leaf  tier=N  (sales channel)

    InBound example:
        supply_point   (bridge)
        L- MOM         tier=0  (Mother Plant / 最終組立)
           L- ...      tier=1  (Tier-1 Supplier)
              L- leaf  tier=N  (raw material)

lt_wks usage:
    Backward Planning:  child.S[w]  ->  parent.P[w + lt_wks]   (demand propagation)
    Forward  Planning:  parent.P[w] ->  child.S[w + lt_wks]    (supply propagation)

ss_days usage:
    Safety stock days; backward planner adds ceil(ss_days/7) extra weeks
    on top of lt_wks offset so upstream sees demand earlier, creating a
    buffer at this node.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# PSI bucket index constants
# ---------------------------------------------------------------------------
S  = 0   # Sales / Fulfilled shipment
CO = 1   # Carry Over (受注残)
I  = 2   # Inventory
P  = 3   # Purchase / Production plan

PSI_BUCKETS = (S, CO, I, P)
PSI_BUCKET_NAMES = {S: "S", CO: "CO", I: "I", P: "P"}

# Capacity index constants
CAP_HARD = 0   # Equipment / physical limit
CAP_SOFT = 1   # Operational plan limit (softer ceiling)

# Operating calendar: 1 week = MAX_SHIFTS shifts (3 shifts/day * 7 days; 1 shift = 8H).
# op_shifts[w] == 0 => closed week (skipped in traversal); N>0 => open;
# None => no calendar entry (always open). Future: cap_soft = N * cap_hard / MAX_SHIFTS.
MAX_SHIFTS = 21


# ---------------------------------------------------------------------------
# PlanNode
# ---------------------------------------------------------------------------
@dataclass
class PlanNode:
    """
    One node in the WOM Planning Layer tree.

    A PlanNode represents one supply chain location for one product.
    Physical layer (NetworkX GUI node) is linked separately via
    gui_node.sku_dict[product_name] = plan_node.

    Tree entry points (held on the SCTree / WOMModel level):
        prod_tree_dict_OT[prod_nm]  ->  OutBound tree root PlanNode
        prod_tree_dict_IN[prod_nm]  ->  InBound  tree root PlanNode
    """

    # -- Identity ──────────────────────────────────────────────────────────
    node_id:   str          # unique ID, e.g. "OUT:RegionA:SKU-001"
    node_name: str          # human-readable label
    product:   str          # product name (key into prod_tree_dict_OT/IN)
    side:      str          # "outbound" | "inbound"

    # -- Topology ──────────────────────────────────────────────────────────
    node_type: str          # see NODE_TYPE_* constants below
    tier:      int          # 0 = closest to supply_point, increases to leaf

    # -- Planning parameters ───────────────────────────────────────────────
    lt_wks:         int = 1  # lead time to parent [weeks] -- used by BackwardPlanner
                             #   Backward: child.S[w] -> parent.P[w + lt_wks]
    transit_lt_wks: int = 0  # physical transit time [weeks] -- used by ForwardPlanner
                             #   Forward (PUSH_SUB): child.S[w] -> parent.P[w + transit_lt_wks]
                             #   Defaults to lt_wks if not specified in CSV
    # cpu_size removed (Request Letter A: request_letter_a_cpu_size_to_plan.md) --
    # it is a plan-wide value, not a per-node one; see SCTree.cpu_size.
    ss_days:  int = 0       # safety stock [days]; 0 = no extra buffer
                            # backward planner adds ceil(ss_days/7) to lt_wks offset
                            # so upstream demand is placed earlier -> creates buffer at this node
    init_stock_days: int = 0  # X2: warm-up / initial stock coverage [days]; 0 = none.
                              # BackwardPlanner adds ceil(init_stock_days/7) on top of
                              # (lt_wks + ss_wks) on the OUTBOUND side only, so upstream
                              # demand is placed earlier and Forward builds this node's
                              # opening inventory as a result.
                              # Decision 7: InBound-side pre-build is owned by
                              # push_lead_time_weeks (Mode 4); X2 is OutBound-only.

    @property
    def ss_wks(self) -> int:
        """Safety stock additional offset weeks = ceil(ss_days / 7)."""
        return (self.ss_days + 6) // 7 if self.ss_days > 0 else 0

    @property
    def init_stock_wks(self) -> int:
        """X2: initial (warm-up) stock offset weeks = ceil(init_stock_days / 7)."""
        return (self.init_stock_days + 6) // 7 if self.init_stock_days > 0 else 0

    # -- PSI lists  (initialized by init_psi) ─────────────────────────────
    # psi4demand[week_idx][bucket] = [lot_ID, ...]   (demand side)
    # psi4supply[week_idx][bucket] = [lot_ID, ...]   (supply side)
    # capacity  [week_idx][0:CapHard, 1:CapSoft] = float
    psi4demand: List[List[List[str]]] = field(default_factory=list)
    psi4supply: List[List[List[str]]] = field(default_factory=list)
    capacity:   List[List[float]]     = field(default_factory=list)

    # -- Tree linkage ──────────────────────────────────────────────────────
    parent:   Optional["PlanNode"]  = field(default=None,  repr=False)
    children: List["PlanNode"]      = field(default_factory=list, repr=False)

    # -- Planning mode ─────────────────────────────────────────────────────
    is_decoupling: bool = False    # True -> PUSH/PULL boundary (buffer stock)
    plan_mode:     str  = "pull"   # "pull" (backward/demand-driven)
                                   # "push" (forward/supply-driven)

    # -- Demand-envelope mode (Phase 2 Fork B) ─────────────────────────────
    # Per-node policy for how BackwardPlanner allocates demand (fill target):
    #   "hard" (default) : fill up to cap_hard; overflow -> CO/carry-back.
    #                      cap_soft is a flag only (overtime). Suits perishable /
    #                      non-inventoriable / make-to-order nodes (no pre-build).
    #   "soft"           : level production at cap_soft; excess is carried back
    #                      (pre-built) into earlier weeks' slack (cap_soft-demand).
    #                      cap_hard stays the physical ceiling. Suits inventoriable
    #                      nodes that plan leveled production (heijunka).
    demand_envelope: str = "hard"

    # -- Supply role (A1 fix, Request Letter: request_fix_a1_supply_role_rev2.md) ──
    # Interpreted as an edge attribute: "how does THIS node's demand relate to
    # its siblings under the same parent?" Read from sc_tree_master.csv's
    # supply_role column (on the CHILD's row). Only meaningful when a node
    # has 2+ children in the InBound tree -- BackwardPlanner._in_propagate
    # groups children by this attribute before propagating demand downward:
    #   "confluence" : same-kind supply converging from multiple routes
    #                  (e.g. milk from two collection circles). Siblings
    #                  marked "confluence" SPLIT the parent's demand between
    #                  them (equal + remainder), since either one satisfying
    #                  part of the need is physically correct.
    #   "assembly"   : different components that must all be present
    #                  (e.g. a battery AND a motor AND an ECU per vehicle).
    #                  Each "assembly" sibling receives the FULL lot list,
    #                  unmultiplied. A future BOM quantity N (the "1 set
    #                  rule", e.g. 4 tyres per vehicle) does NOT touch this
    #                  list -- lot counts stay 1:1 parent-to-child so
    #                  Lot_ID identity is preserved; N instead scales the
    #                  physical quantity a lot represents (capacity
    #                  thresholds, cost formulas, KPI unit counts, PPC
    #                  display), entirely outside this layer.
    #   "" (blank)   : treated as "assembly" (safe default -- this preserves
    #                  every existing model's current "duplicate to every
    #                  child" behaviour unchanged).
    supply_role: str = "assembly"

    # -- BOM quantity (Letter B: request_letter_b_bom_qty.md, "1 set rule") ─
    # Interpreted as an edge attribute like supply_role: "how many of THIS
    # node's own units does one parent unit require?" (e.g. 4 tyres per
    # vehicle). Read from sc_tree_master.csv's bom_qty column (on the
    # CHILD's row). Meaningful ONLY for supply_role="assembly" children;
    # sc_tree_builder.py forces bom_qty=1 for "confluence" children
    # regardless of the CSV value (a confluence sibling splits demand, it
    # does not multiply it -- see request_fix_a1_supply_role_rev2.md §3.2).
    #
    # bom_qty is a PER-NODE value (unlike cpu_size, which is plan-wide on
    # SCTree -- do not confuse the two). It NEVER touches the Lot_ID list:
    # Planning Engine / lot_generator are completely unaware of it. It only
    # scales the physical-quantity INTERPRETATION of a lot count, downstream
    # of planning: sc_tree_to_df.py, GUI chart panels, and (for leaf_in
    # supplier-cost lines only) the PPC engine, per
    #     S_Qty[w] = len(psi[w]["S"]) * cpu_size * bom_qty
    bom_qty: int = 1

    # -- Week index lookup (set after init_psi) ────────────────────────────
    # week_labels[week_idx] = ISO week string, e.g. "2026-W01"
    week_labels: List[str] = field(default_factory=list, repr=False)

    # ======================================================================
    # Initialisation
    # ======================================================================

    def init_psi(self, week_labels: List[str]) -> None:
        """
        Allocate PSI list space for all weeks.

        Parameters
        ----------
        week_labels:
            Ordered list of ISO week strings, e.g. ["2026-W01", "2026-W02", ...]
            Length defines the planning horizon.
        """
        n = len(week_labels)
        self.week_labels = list(week_labels)

        def _empty_buckets() -> List[List[str]]:
            return [[], [], [], []]   # index 0:S  1:CO  2:I  3:P

        self.psi4demand = [_empty_buckets() for _ in range(n)]
        self.psi4supply = [_empty_buckets() for _ in range(n)]
        self.capacity   = [[0.0, 0.0] for _ in range(n)]
        # Phase 2 operating calendar: per-week shift count (0..MAX_SHIFTS).
        # None = no calendar entry (always open); 0 = closed; N>0 = open with N shifts.
        self.op_shifts  = [None] * n
        # Kitting List stage 1 (request_kitting_stage1.md, record-only).
        # kitting[assembly_week][lot_id] = {child_node_name: arrival_week}
        #   assembly_week : the week THIS node's own backward-planned demand
        #                   (psi4demand[w][S]) needed this lot -- a single
        #                   value shared by all assembly siblings regardless
        #                   of each child's own lt_wks/ss_wks or forward-plan
        #                   delay (see ForwardPlanner._get_demand_week_index).
        #   arrival_week  : the week THIS child's shipment actually landed in
        #                   this node's psi4supply[w][P] (may differ per
        #                   child -- e.g. one part arrives early, another
        #                   late).
        # Only populated for children whose supply_role != "confluence"
        # (see PlanNode.kitting_required). Record-only: does NOT affect
        # P/S/I/CO. Explicit init (not defaultdict), matching op_shifts.
        self.kitting: List[Dict[str, Dict[str, int]]] = [{} for _ in range(n)]

    # ======================================================================
    # Week index helper
    # ======================================================================

    def week_idx(self, week_label: str) -> int:
        """Return the integer index for an ISO week label string."""
        return self.week_labels.index(week_label)

    # ======================================================================
    # Quantity accessors  (quantity = len of lot-ID list)
    # ======================================================================

    def qty_demand(self, week: int, bucket: int) -> int:
        """Number of lots in psi4demand[week][bucket]."""
        return len(self.psi4demand[week][bucket])

    def qty_supply(self, week: int, bucket: int) -> int:
        """Number of lots in psi4supply[week][bucket]."""
        return len(self.psi4supply[week][bucket])

    # ======================================================================
    # Lot mutation helpers
    # ======================================================================

    def add_lot_demand(self, week: int, bucket: int, lot_id: str) -> None:
        """Append a lot-ID to psi4demand[week][bucket]."""
        self.psi4demand[week][bucket].append(lot_id)

    def add_lot_supply(self, week: int, bucket: int, lot_id: str) -> None:
        """Append a lot-ID to psi4supply[week][bucket]."""
        self.psi4supply[week][bucket].append(lot_id)

    def pop_lot_demand(self, week: int, bucket: int) -> str:
        """Remove and return the last lot-ID from psi4demand[week][bucket]."""
        return self.psi4demand[week][bucket].pop()

    def pop_lot_supply(self, week: int, bucket: int) -> str:
        """Remove and return the last lot-ID from psi4supply[week][bucket]."""
        return self.psi4supply[week][bucket].pop()

    def move_lot_demand(
        self,
        src_week: int, src_bucket: int,
        dst_week: int, dst_bucket: int,
        lot_id: str,
    ) -> None:
        """
        Move a specific lot-ID within psi4demand from one (week, bucket)
        to another.  Raises ValueError if lot_id is not found in src.
        """
        self.psi4demand[src_week][src_bucket].remove(lot_id)
        self.psi4demand[dst_week][dst_bucket].append(lot_id)

    # ======================================================================
    # Capacity accessors
    # ======================================================================

    def cap_hard(self, week: int) -> float:
        """Equipment / physical capacity ceiling for the week [lot units]."""
        return self.capacity[week][CAP_HARD]

    def cap_soft(self, week: int) -> float:
        """Operational plan capacity ceiling for the week [lot units]."""
        return self.capacity[week][CAP_SOFT]

    def set_capacity(
        self,
        week: int,
        cap_hard: float = 0.0,
        cap_soft: float = 0.0,
    ) -> None:
        self.capacity[week][CAP_HARD] = cap_hard
        self.capacity[week][CAP_SOFT] = cap_soft

    # ======================================================================
    # Operating calendar (per-week shift count; Phase 2)
    # ======================================================================

    def set_operating_shifts(self, week: int, shifts) -> None:
        """Set the operating shift count for one week.
        0 = closed (skipped in traversal, like SS/holiday); N>0 = open with N
        shifts/week (1 week = MAX_SHIFTS=21 max). None keeps 'no calendar / open'."""
        self.op_shifts[week] = shifts

    def operating_shifts(self, week: int):
        """Return the operating shift count for the week (None = unset / always open)."""
        return self.op_shifts[week]

    def is_open(self, week: int) -> bool:
        """True if the node operates this week. Unset (None) => always open;
        0 shifts => closed; N>0 => open."""
        s = self.op_shifts[week]
        return s is None or s > 0

    # ======================================================================
    # Kitting List (stage 1, request_kitting_stage1.md) -- judgement helpers
    # ======================================================================

    def kitting_required(self) -> set:
        """
        Set of child node_names this node's kitting must see arrive before a
        lot is "complete" -- every child EXCEPT supply_role == "confluence"
        siblings (confluence = same-kind supply converging from multiple
        routes; there is no "must all be present" concept for them).

        Written to be reused unchanged by stage 3 gate keeping.
        """
        return {c.node_name for c in self.children if c.supply_role != "confluence"}

    def kitting_status(self, week: int, lot_id: str) -> dict:
        """
        Read-only judgement for one (week, lot_id) kitting entry.

        Stage 1: informational only -- callers must NOT use this to withhold
        lots from P (KITTING_GATE_ENABLED in forward_planner.py stays False).
        Stage 3 gate keeping can call this exact method.
        """
        required = self.kitting_required()
        arrived  = set(self.kitting[week].get(lot_id, {}).keys())
        missing  = required - arrived
        return {
            "required":    required,
            "arrived":     arrived,
            "missing":     missing,
            "is_complete": not missing,
        }

    # ======================================================================
    # Carry Over helper (Forward Planning only)
    # ======================================================================

    def apply_carry_over_demand(self, week: int) -> None:
        """
        Forward Planning: if S demand cannot be fulfilled by I+P this week,
        roll the unfulfilled S lots into CO of the NEXT week.

        Called week-by-week during forward pass.
        CO is NEVER touched in Backward Planning.
        """
        if week + 1 >= len(self.psi4demand):
            return   # last week -- nowhere to carry over

        supply_lots = (
            self.psi4demand[week][I]
            + self.psi4demand[week][P]
        )
        demand_lots = self.psi4demand[week][S]

        supplied_ids = set(supply_lots)
        unfulfilled = [lot for lot in demand_lots if lot not in supplied_ids]

        for lot_id in unfulfilled:
            self.psi4demand[week][S].remove(lot_id)
            self.psi4demand[week + 1][CO].append(lot_id)

    # ======================================================================
    # Tree traversal helpers
    # ======================================================================

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def is_root(self) -> bool:
        return self.parent is None

    def walk_postorder(self):
        """
        Yield nodes in POST-ORDER (children before parent).
        Used for:
          - Backward planning on OutBound tree (Leaf -> DAD -> supply_point)
          - Forward  planning on InBound tree  (Leaf -> MOM -> supply_point)
        """
        for child in self.children:
            yield from child.walk_postorder()
        yield self

    def walk_preorder(self):
        """
        Yield nodes in PRE-ORDER (parent before children).
        Used for:
          - Backward planning on InBound tree  (MOM -> Tier-1 -> Leaf)
          - Forward  planning on OutBound tree  (DAD -> Intermediate -> Leaf)
        """
        yield self
        for child in self.children:
            yield from child.walk_preorder()

    # ======================================================================
    # Utility
    # ======================================================================

    def add_child(self, child: "PlanNode") -> None:
        """Attach a child node and set its parent back-pointer."""
        child.parent = self
        self.children.append(child)

    def psi_summary(self, week: int) -> dict:
        """
        Return a dict summarising demand-side PSI quantities for one week.
        Useful for logging and GUI display.
        """
        return {
            "week":    self.week_labels[week] if self.week_labels else week,
            "node_id": self.node_id,
            "S":  self.qty_demand(week, S),
            "CO": self.qty_demand(week, CO),
            "I":  self.qty_demand(week, I),
            "P":  self.qty_demand(week, P),
            "cap_hard": self.cap_hard(week),
            "cap_soft": self.cap_soft(week),
        }

    def __repr__(self) -> str:
        n_children = len(self.children)
        n_weeks    = len(self.psi4demand)
        return (
            f"PlanNode("
            f"id={self.node_id!r}, "
            f"side={self.side!r}, "
            f"type={self.node_type!r}, "
            f"tier={self.tier}, "
            f"lt={self.lt_wks}w, "
            f"children={n_children}, "
            f"weeks={n_weeks})"
        )


# ---------------------------------------------------------------------------
# node_type string constants (for readability -- not enforced by dataclass)
# ---------------------------------------------------------------------------
NODE_TYPE_LEAF_OUT     = "leaf_out"      # OutBound leaf (sales channel)
NODE_TYPE_DAD          = "dad"           # OutBound intermediate (倉庫, DC等)
NODE_TYPE_SUPPLY_POINT = "supply_point"  # Bridge between OutBound / InBound
NODE_TYPE_MOM          = "mom"           # InBound intermediate (Mother Plant, Tier-N)
NODE_TYPE_LEAF_IN      = "leaf_in"       # InBound leaf (raw material supplier)
NODE_TYPE_STOCKYARD    = "stockyard"     # InBound intermediate (Stage 3a-1,
                                          # request_stage3a1_stockyard_passthrough.md):
                                          # component staging node inserted between a
                                          # leaf_in supplier and its assembly (mom)
                                          # parent. No special-cased branch anywhere in
                                          # the engine reads this constant -- node_type
                                          # is an unvalidated free string throughout
                                          # sc_tree_builder.py / backward_planner.py /
                                          # forward_planner.py / push_pull.py, confirmed
                                          # empirically (Sec 4 impact scan) to behave as
                                          # a plain pass-through intermediate node with
                                          # lt_wks=0. Defined here only for readability
                                          # and parity with the other NODE_TYPE_* names.
