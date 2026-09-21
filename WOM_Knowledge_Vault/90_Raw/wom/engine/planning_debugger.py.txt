"""
wom/engine/planning_debugger.py
──────────────────────────────
Planning Operation Debugger — step-by-step operator execution.

Each "step" corresponds to one Planning Operator
(BackwardPlanner, copy_demand_to_supply, ForwardPlanner, etc.).

Before/after each step the PSI lot-counts for all nodes are
captured as lightweight snapshots, allowing the UI to show:
  - current SC State (psi4demand + psi4supply)
  - delta (what changed in this step)

Usage from DebugPanel in app.py::

    dbg = PlanningDebugger()
    dbg.initialize(sc_tree, weeks, steps, callables)
    dbg.step_forward()
    snap  = dbg.get_snapshot(dbg.current_step)
    delta = dbg.get_delta(dbg.current_step, "Buffer_Wafer_TW")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Data types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class OperatorStep:
    """One planning operator in the sequence."""
    name: str          # Human-readable label, e.g. "BackwardPlanner"
    key: str           # Internal key, e.g. "backward_planner"
    description: str   # Short tooltip shown in the UI


# PSI snapshot: node_name -> {"demand": [[S,CO,I,P] x n_weeks], "supply": [...]}
PSISnapshot = Dict[str, Dict[str, List[List[int]]]]


# ──────────────────────────────────────────────────────────────────────────────
# PlanningDebugger
# ──────────────────────────────────────────────────────────────────────────────

class PlanningDebugger:
    """
    Manages step-by-step execution of the WOM Planning Engine.

    The caller (DebugPanel) is responsible for building the sc_tree and
    registering the operator callables in the correct order.  This class
    only manages execution sequencing and snapshot storage.
    """

    def __init__(self) -> None:
        self.sc_tree = None
        self.weeks: List[str] = []
        self.products: List[str] = []

        self._steps: List[OperatorStep] = []
        self._callables: List[Callable] = []

        # snapshots[i] = PSI state *after* step i has been executed
        self._snapshots: List[PSISnapshot] = []
        # snapshot of the state before any step (right after lot assignment)
        self._initial_snapshot: Optional[PSISnapshot] = None

        # -1 = no step run yet
        self.current_step: int = -1
        self.initialized: bool = False

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def total_steps(self) -> int:
        return len(self._steps)

    @property
    def steps(self) -> List[OperatorStep]:
        return list(self._steps)

    def initialize(
        self,
        sc_tree,
        weeks: List[str],
        steps: List[OperatorStep],
        callables: List[Callable],
    ) -> None:
        """
        Set up the debugger.

        sc_tree  — freshly built, lots assigned, capacity applied,
                   but NO planning operators run yet.
        weeks    — list of "YYYY-Www" labels.
        steps    — ordered OperatorStep descriptors.
        callables — matching callables; callables[i] executes steps[i].
        """
        assert len(steps) == len(callables), \
            "steps and callables must have the same length"

        self.sc_tree = sc_tree
        self.weeks = list(weeks)
        self.products = list(sc_tree.products)
        self._steps = list(steps)
        self._callables = list(callables)
        self._snapshots = []
        self.current_step = -1
        self.initialized = True

        # Capture initial (pre-planning) state
        self._initial_snapshot = self._take_snapshot()

    def step_forward(self) -> bool:
        """
        Execute the next operator step and capture a snapshot.
        Returns True if a step was executed, False if already at the last step.
        """
        next_idx = self.current_step + 1
        if next_idx >= len(self._callables):
            return False

        self._callables[next_idx]()
        self.current_step = next_idx

        snap = self._take_snapshot()
        if len(self._snapshots) <= next_idx:
            self._snapshots.append(snap)
        else:
            self._snapshots[next_idx] = snap
        return True

    def run_all(self) -> None:
        """Execute all remaining steps."""
        while self.step_forward():
            pass

    @property
    def is_at_start(self) -> bool:
        return self.current_step == -1

    @property
    def is_at_end(self) -> bool:
        return self.current_step >= len(self._callables) - 1

    def get_snapshot(self, step_idx: int) -> Optional[PSISnapshot]:
        """
        Return the PSI snapshot for the state *after* step_idx.
        step_idx == -1  → initial snapshot (before any step).
        Returns None if the snapshot is not yet available.
        """
        if step_idx == -1:
            return self._initial_snapshot
        if 0 <= step_idx < len(self._snapshots):
            return self._snapshots[step_idx]
        return None

    def get_psi_arrays(
        self,
        step_idx: int,
        node_name: str,
        layer: str = "supply",
    ):
        """
        Return [[S, CO, I, P] x n_weeks] for node_name at step_idx.
        layer: "demand" or "supply"
        Returns None if unavailable.
        """
        snap = self.get_snapshot(step_idx)
        if snap is None:
            return None
        node_snap = snap.get(node_name)
        if node_snap is None:
            return None
        return node_snap.get(layer)

    def get_delta(self, step_idx: int, node_name: str) -> Optional[dict]:
        """
        Compute before/after delta for node_name at step_idx.

        Returns dict:
          "demand"         [[dS, dCO, dI, dP] x n_weeks]
          "supply"         [[dS, dCO, dI, dP] x n_weeks]
          "changes_demand" [(week_idx, bucket_idx, delta), ...]  non-zero only
          "changes_supply" [(week_idx, bucket_idx, delta), ...]  non-zero only
          "summary_lines"  list[str]  human-readable summary
        """
        before = self.get_snapshot(step_idx - 1)
        after  = self.get_snapshot(step_idx)
        if before is None or after is None:
            return None
        b_node = before.get(node_name)
        a_node = after.get(node_name)
        if b_node is None or a_node is None:
            return None

        n = len(b_node["demand"])
        bucket_names = ["S", "CO", "I", "P"]

        delta_demand = [
            [a_node["demand"][w][k] - b_node["demand"][w][k] for k in range(4)]
            for w in range(n)
        ]
        delta_supply = [
            [a_node["supply"][w][k] - b_node["supply"][w][k] for k in range(4)]
            for w in range(n)
        ]

        changes_d = [
            (w, k, delta_demand[w][k])
            for w in range(n) for k in range(4)
            if delta_demand[w][k] != 0
        ]
        changes_s = [
            (w, k, delta_supply[w][k])
            for w in range(n) for k in range(4)
            if delta_supply[w][k] != 0
        ]

        # Build human-readable summary
        def _fmt_changes(changes, label):
            if not changes:
                return [f"  {label}: no change"]
            # group by bucket
            by_bucket: Dict[int, List] = {}
            for w, k, d in changes:
                by_bucket.setdefault(k, []).append((w, d))
            lines = [f"  {label}:"]
            for k in sorted(by_bucket):
                wds = by_bucket[k]
                total = sum(d for _, d in wds)
                wk_list = [f"W{w}({'+' if d>0 else ''}{d})" for w, d in wds[:5]]
                suffix = "…" if len(wds) > 5 else ""
                lines.append(
                    f"    {bucket_names[k]}: total {'+' if total>0 else ''}{total}"
                    f"  [{', '.join(wk_list)}{suffix}]"
                )
            return lines

        summary = []
        summary.extend(_fmt_changes(changes_d, "Demand layer"))
        summary.extend(_fmt_changes(changes_s, "Supply layer"))

        return {
            "demand":         delta_demand,
            "supply":         delta_supply,
            "changes_demand": changes_d,
            "changes_supply": changes_s,
            "summary_lines":  summary,
        }

    def all_node_names(self) -> List[str]:
        """Return all unique node names across all products (insertion order)."""
        if self.sc_tree is None:
            return []
        names: List[str] = []
        seen: set = set()
        for prod in self.products:
            for node in self.sc_tree.iter_all_nodes(prod):
                if node.node_name not in seen:
                    names.append(node.node_name)
                    seen.add(node.node_name)
        return names

    def get_node(self, product: str, node_name: str):
        """Return PlanNode matching product + node_name, or None."""
        if self.sc_tree is None:
            return None
        for node in self.sc_tree.iter_all_nodes(product):
            if node.node_name == node_name:
                return node
        return None

    # ── Internal ──────────────────────────────────────────────────────────────

    def _take_snapshot(self) -> PSISnapshot:
        """Capture current PSI lot-counts for all nodes (lightweight copy)."""
        from wom.model.plan_node import S as S_, CO as CO_, I as I_, P as P_

        snap: PSISnapshot = {}
        if self.sc_tree is None:
            return snap

        seen: set = set()
        for prod in self.products:
            for node in self.sc_tree.iter_all_nodes(prod):
                nn = node.node_name
                if nn in seen:
                    continue
                seen.add(nn)
                n = len(node.psi4demand)
                sf_raw = getattr(node, '_push_shortfall', None)
                snap[nn] = {
                    "demand": [
                        [
                            len(node.psi4demand[w][S_]),
                            len(node.psi4demand[w][CO_]),
                            len(node.psi4demand[w][I_]),
                            len(node.psi4demand[w][P_]),
                        ]
                        for w in range(n)
                    ],
                    "supply": [
                        [
                            len(node.psi4supply[w][S_]),
                            len(node.psi4supply[w][CO_]),
                            len(node.psi4supply[w][I_]),
                            len(node.psi4supply[w][P_]),
                        ]
                        for w in range(n)
                    ],
                    "shortfall": [
                        sf_raw.get(w, 0) if sf_raw else 0
                        for w in range(n)
                    ],
                }
        return snap

    def get_shortfall(self, step_idx: int, node_name: str):
        """
        Return per-week shortage count for a PUSH decoupling node at step_idx.
        Returns list[int] or None if unavailable / no shortage.
        """
        snap = self.get_snapshot(step_idx)
        if snap is None:
            return None
        node_snap = snap.get(node_name)
        if node_snap is None:
            return None
        return node_snap.get("shortfall")
