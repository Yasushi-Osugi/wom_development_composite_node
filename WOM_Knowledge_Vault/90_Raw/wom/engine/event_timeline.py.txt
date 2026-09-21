"""
wom/engine/event_timeline.py
─────────────────────────────
Build a per-week activity snapshot from a fully-planned SCTree.

Used by Event Flow Tracing animation in the GUI.
No modifications to the SCTree — purely read-only post-processing.

GUI node label ↔ PlanNode mapping (hammock model):
  "Mother\nPlant"      → sc_tree.get_in_root(prod_nm)          (MOM)
  "SKU:{sku}"          → InBound tier-1 supplier node           (MOM child)
  "Region:{reg}"       → OutBound leaf_out node for that region
  "Global\nProcurement"→ no direct PlanNode (InBound supply origin, synthetic)
  "Global\nMarketing"  → no direct PlanNode (OutBound sink, synthetic)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class NodeActivity:
    """Lot-count activity on one GUI node for one week."""
    gui_label: str          # e.g. "Mother\nPlant", "SKU:SKU-A001", "Region:AMER"
    s_count:   int = 0      # fulfilled lots (S bucket)
    co_count:  int = 0      # carry-over lots (CO bucket)
    i_count:   int = 0      # inventory lots  (I bucket)
    p_count:   int = 0      # production/purchase lots (P bucket)

    @property
    def total(self) -> int:
        return self.s_count + self.co_count + self.i_count + self.p_count

    @property
    def flow(self) -> int:
        """Lots 'in motion' this week (S + P — ignoring I/CO for visual weight)."""
        return self.s_count + self.p_count


@dataclass
class EdgeFlow:
    """Flow quantity on one directed edge for one week."""
    src: str        # GUI label of source node
    dst: str        # GUI label of destination node
    lot_count: int  # number of lots flowing
    direction: str  # "supply" | "demand"
    bucket: str     # "S" | "P" | "CO"


@dataclass
class WeekSnapshot:
    """Complete activity picture for one planning week."""
    week_idx:   int
    week_label: str
    # keyed by gui_label
    node_activity: Dict[str, NodeActivity] = field(default_factory=dict)
    # ordered: supply edges first, then demand edges
    edge_flows:    List[EdgeFlow]          = field(default_factory=list)

    def get_node(self, gui_label: str) -> NodeActivity:
        if gui_label not in self.node_activity:
            self.node_activity[gui_label] = NodeActivity(gui_label)
        return self.node_activity[gui_label]

    @property
    def max_flow(self) -> int:
        if not self.edge_flows:
            return 0
        return max(e.lot_count for e in self.edge_flows)


# ── Builder ────────────────────────────────────────────────────────────────────

def build_event_timeline(sc_tree) -> List[WeekSnapshot]:
    """
    Build a list of WeekSnapshot from a fully-planned SCTree.

    Returns one WeekSnapshot per week (same order as sc_tree.week_labels).
    """
    from wom.model.plan_node import S, CO, I, P as P_

    weeks = sc_tree.week_labels
    n     = len(weeks)

    snapshots: List[WeekSnapshot] = [
        WeekSnapshot(week_idx=w, week_label=weeks[w]) for w in range(n)
    ]

    MOTHER_LABEL = "Mother\nPlant"

    for prod_nm in sc_tree.products:
        # ── InBound nodes ─────────────────────────────────────────────
        try:
            mom = sc_tree.get_in_root(prod_nm)
        except Exception:
            continue

        # MOM (Mother Plant node)
        for w in range(n):
            snap  = snapshots[w]
            na    = snap.get_node(MOTHER_LABEL)
            psi   = mom.psi4supply[w]
            na.s_count  += len(psi[S])
            na.co_count += len(psi[CO])
            na.i_count  += len(psi[I])
            na.p_count  += len(psi[P_])

        # InBound tier-1 children (SKU supplier nodes)
        for child in getattr(mom, "children", []):
            gui_label = f"SKU:{prod_nm}"
            for w in range(n):
                snap  = snapshots[w]
                na    = snap.get_node(gui_label)
                psi   = child.psi4supply[w]
                na.p_count += len(psi[P_])
                na.i_count += len(psi[I])

                # Supply edge: SKU node → Mother Plant
                p_cnt = len(psi[P_])
                if p_cnt > 0:
                    snap.edge_flows.append(EdgeFlow(
                        src=gui_label, dst=MOTHER_LABEL,
                        lot_count=p_cnt, direction="supply", bucket="P"))

        # ── OutBound nodes ────────────────────────────────────────────
        try:
            ot_root = sc_tree.get_ot_root(prod_nm)
            leaves  = [nd for nd in ot_root.walk_preorder()
                       if not nd.children]
        except Exception:
            leaves = []

        for leaf in leaves:
            # Determine region from node_id: "OUT:Sales:{region}:{sku}"
            parts  = leaf.node_id.split(":")
            region = parts[2] if len(parts) >= 3 else "?"
            gui_label = f"Region:{region}"

            for w in range(n):
                snap  = snapshots[w]
                na    = snap.get_node(gui_label)
                psi   = leaf.psi4supply[w]
                s_cnt  = len(psi[S])
                co_cnt = len(psi[CO])
                na.s_count  += s_cnt
                na.co_count += co_cnt
                na.i_count  += len(psi[I])
                na.p_count  += len(psi[P_])

                # Demand edge: Mother Plant → Region
                if s_cnt > 0:
                    snap.edge_flows.append(EdgeFlow(
                        src=MOTHER_LABEL, dst=gui_label,
                        lot_count=s_cnt, direction="demand", bucket="S"))
                if co_cnt > 0:
                    snap.edge_flows.append(EdgeFlow(
                        src=MOTHER_LABEL, dst=gui_label,
                        lot_count=co_cnt, direction="demand", bucket="CO"))

    # ── Aggregate duplicate edges per week ────────────────────────────────
    for snap in snapshots:
        merged: dict = {}
        for ef in snap.edge_flows:
            key = (ef.src, ef.dst, ef.direction, ef.bucket)
            if key in merged:
                merged[key].lot_count += ef.lot_count
            else:
                merged[key] = EdgeFlow(ef.src, ef.dst, ef.lot_count,
                                       ef.direction, ef.bucket)
        snap.edge_flows = list(merged.values())

    return snapshots


# ── Convenience ────────────────────────────────────────────────────────────────

def max_activity(snapshots: List[WeekSnapshot]) -> int:
    """Return the maximum node.total across all weeks (for normalising sizes)."""
    val = 0
    for snap in snapshots:
        for na in snap.node_activity.values():
            val = max(val, na.total)
    return val or 1
