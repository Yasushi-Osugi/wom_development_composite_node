"""
wom/engine/holiday_calendar_plugin.py
HolidayCalendarPlugin: supply_closure / demand_multiplier / pre-holiday buffer build.
CSV schema: holiday_id, holiday_name, start_week, end_week, node_name, effect, value
"""

from __future__ import annotations

import csv
import os
from typing import Dict, List, Tuple

from wom.engine.plugin_base import WOMPlugin
from wom.model.plan_node import S, P as P_IDX, NODE_TYPE_LEAF_IN


class HolidayCalendarPlugin(WOMPlugin):
    name        = "holiday_calendar"
    label       = "Holiday Calendar"
    description = "Supply closure + demand multiplier + pre-holiday buffer build."

    def __init__(self, csv_path: str = "") -> None:
        self.csv_path  = csv_path
        self._rules: List[dict] = []
        self._hol_seq: Dict[Tuple, int] = {}

    def set_csv_path(self, path: str) -> None:
        self.csv_path = path

    # ------------------------------------------------------------------
    # Hook: PRE_PLAN
    # ------------------------------------------------------------------

    def on_pre_plan(self, sc_tree, weeks: list, config: dict, **kw) -> None:
        path = config.get("holiday_cal_path", "") or self.csv_path
        if not path or not os.path.exists(path):
            return
        rules = self._load_rules(path, weeks)
        if not rules:
            return
        self._rules = rules

        node_lookup: Dict[str, list] = {}
        for prod_nm in sc_tree.products:
            for node in sc_tree.iter_all_nodes(prod_nm):
                node_lookup.setdefault(node.node_name, []).append(node)

        for rule in rules:
            nodes = node_lookup.get(rule["node_name"], [])
            if not nodes:
                print(f"[HolidayCalendar] WARNING node {rule['node_name']!r} not found "
                      f"(holiday: {rule['holiday_id']})")
                continue
            if rule["effect"] == "supply_closure":
                self._apply_supply_closure(
                    nodes, rule["week_idxs"], rule["week_labels"],
                    rule["value"], rule["holiday_name"])
            elif rule["effect"] == "demand_multiplier":
                self._apply_demand_multiplier(
                    nodes, rule["week_idxs"], rule["week_labels"],
                    rule["value"], rule["holiday_id"])
            else:
                print(f"[HolidayCalendar] Unknown effect {rule['effect']!r} -- skipped")

        # v1r0m2: Build explicit_closures and share via config so that
        # BackwardPlanner can skip closure weeks during LT offset calculation.
        # Structure: {node_name: set(week_idx)}
        explicit_closures: Dict[str, set] = {}
        for rule in rules:
            if rule["effect"] == "supply_closure":
                explicit_closures.setdefault(
                    rule["node_name"], set()).update(rule["week_idxs"])
        config["explicit_closures"] = explicit_closures
        print(f"[HolidayCalendar] explicit_closures written to config: "
              f"{len(explicit_closures)} nodes")

    def _apply_supply_closure(self, nodes, w_idxs, w_lbls, cap_val, name):
        for node in nodes:
            for w in w_idxs:
                node.set_capacity(w, cap_hard=cap_val)
        print(
            f"[HolidayCalendar] Supply closure {name!r}: "
            f"{nodes[0].node_name} cap_hard={cap_val} "
            f"{w_lbls[0]}..{w_lbls[-1]} ({len(w_idxs)} weeks)"
        )

    def _apply_demand_multiplier(self, nodes, w_idxs, w_lbls, multiplier, holiday_id):
        for node in nodes:
            if node.children:
                continue
            prod   = getattr(node, "product", "")
            region = self._infer_region(node)
            for w, wk_label in zip(w_idxs, w_lbls):
                existing    = node.psi4demand[w][S]
                current_qty = len(existing)
                if current_qty == 0:
                    continue
                target_qty = max(0, round(current_qty * multiplier))
                delta      = target_qty - current_qty
                if delta > 0:
                    key       = (holiday_id, prod, region, wk_label)
                    seq_start = self._hol_seq.get(key, 1)
                    for i in range(delta):
                        existing.append(
                            f"HOL:{holiday_id}:{prod}:{region}:{wk_label}:{seq_start+i:05d}")
                    self._hol_seq[key] = seq_start + delta
                elif delta < 0:
                    remove = min(-delta, current_qty)
                    node.psi4demand[w][S] = existing[:current_qty - remove]
                if delta != 0:
                    new_qty = len(node.psi4demand[w][S])
                    print(f"[HolidayCalendar] Demand x{multiplier:.2f}: "
                          f"{node.node_name} {wk_label} {current_qty}->{new_qty} (d{delta:+d})")

    # ------------------------------------------------------------------
    # Hook: POST_BACKWARD
    # ------------------------------------------------------------------

    def on_post_backward(self, sc_tree, prod_nm: str,
                         weeks: list, config: dict, **kw) -> None:
        """
        Shift P-lots from explicitly-closed weeks to nearest open weeks.

        FIX (MemoryError prevention):
        - Uses self._rules to identify closure weeks, NOT cap_hard(w)==0.
        - plan_node.py defaults ALL weeks to cap_hard=0.0, so the old
          cap_hard check incorrectly treated EVERY week with P-lots as
          a closure week, accumulating lots exponentially -> MemoryError.
        - When no open weeks exist, lots are dropped (already cleared from
          psi4demand). ForwardPlanner shows the shortfall via fill_rate/CO.
        """
        n_weeks = len(weeks)

        # Build node -> set of explicitly-closed week indices from loaded rules
        explicit_closures: Dict[str, set] = {}
        for rule in self._rules:
            if rule["effect"] == "supply_closure":
                explicit_closures.setdefault(
                    rule["node_name"], set()).update(rule["week_idxs"])

        for node in sc_tree.iter_all_nodes(prod_nm):
            if node.node_type != NODE_TYPE_LEAF_IN:
                continue

            node_closure_set = explicit_closures.get(node.node_name, set())
            if not node_closure_set:
                continue

            # Only process closure weeks that have P-lots
            closure_idxs = sorted(
                w for w in node_closure_set
                if w < n_weeks and len(node.psi4demand[w][P_IDX]) > 0
            )
            if not closure_idxs:
                continue

            # Collect displaced lots and clear closure weeks
            displaced: List[str] = []
            for w in closure_idxs:
                displaced.extend(node.psi4demand[w][P_IDX])
                node.psi4demand[w][P_IDX] = []
            if not displaced:
                continue

            # Open weeks = any week NOT in the explicit closure set
            first_closure = min(closure_idxs)
            last_closure  = max(closure_idxs)

            pre_open = [w for w in range(first_closure - 1, -1, -1)
                        if w not in node_closure_set]
            if not pre_open:
                pre_open = [w for w in range(last_closure + 1, n_weeks)
                            if w not in node_closure_set]

            if not pre_open:
                print(
                    f"[HolidayCalendar] WARNING {node.node_name} ({prod_nm}): "
                    f"no open weeks -- {len(displaced)} lots dropped "
                    f"(all weeks closed; check holiday_calendar.csv)"
                )
                continue

            # Distribute lots into open weeks (nearest to closure first)
            lot_iter = iter(displaced)
            placed   = 0
            for w in pre_open:
                ch        = node.cap_hard(w)
                current_p = len(node.psi4demand[w][P_IDX])
                space     = max(0, int(ch) - current_p) if ch > 0 else len(displaced)
                chunk: List[str] = []
                for _ in range(space):
                    lot = next(lot_iter, None)
                    if lot is None:
                        break
                    chunk.append(lot)
                node.psi4demand[w][P_IDX].extend(chunk)
                placed += len(chunk)
                if placed >= len(displaced):
                    break

            remaining = list(lot_iter)
            if remaining:
                fallback_w = pre_open[-1]
                node.psi4demand[fallback_w][P_IDX].extend(remaining)
                placed += len(remaining)
                print(f"[HolidayCalendar] WARNING {node.node_name} ({prod_nm}): "
                      f"{len(remaining)} overflow lots -> {weeks[fallback_w]}")

            closure_labels = [weeks[w] for w in closure_idxs]
            target_labels  = [weeks[w] for w in pre_open
                              if len(node.psi4demand[w][P_IDX]) > 0]
            print(
                f"[HolidayCalendar] Pre-holiday buffer: "
                f"{node.node_name} ({prod_nm}) {placed} lots  "
                f"closure={closure_labels} -> buffer={target_labels}"
            )

    # ------------------------------------------------------------------
    # CSV loader
    # ------------------------------------------------------------------

    @staticmethod
    def _load_rules(path: str, weeks: list) -> List[dict]:
        week_idx_map = {wk: i for i, wk in enumerate(weeks)}
        rules = []
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    start = row.get("start_week", "").strip()
                    end   = row.get("end_week",   "").strip()
                    si = week_idx_map.get(start)
                    ei = week_idx_map.get(end)
                    if si is None or ei is None:
                        continue
                    rules.append({
                        "holiday_id":   row.get("holiday_id",   "").strip(),
                        "holiday_name": row.get("holiday_name", "").strip(),
                        "node_name":    row.get("node_name",    "").strip(),
                        "effect":       row.get("effect",       "").strip(),
                        "value":        float(row.get("value", "0") or 0),
                        "week_idxs":    list(range(si, ei + 1)),
                        "week_labels":  weeks[si: ei + 1],
                    })
        except Exception as exc:
            print(f"[HolidayCalendarPlugin] Error loading {path}: {exc}")
        print(f"[HolidayCalendar] Loaded {len(rules)} rules from {os.path.basename(path)}")
        return rules

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_region(node) -> str:
        parts = node.node_id.split(":")
        if len(parts) >= 4 and parts[0] == "OUT":
            return parts[2]
        name = node.node_name
        if name.startswith("Sales "):
            return name[6:].split(" ")[0]
        return "XX"
