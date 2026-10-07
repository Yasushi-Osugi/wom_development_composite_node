"""
wom/plugins/capacity_layer.py
──────────────────────────────
CapacityLayerPlugin（上位の能力の層）  Hook: POST_BACKWARD
RequestLetter_GenerationLine_UpperLayer §4.2

Right after Backward, for each product: builds the upper capacity problem
from the plan tree (wom/capacity_layer/serial_adapter.py), solves it
(wom/capacity_layer/solver.solve_lp: 1) maximise the lots allocated by their
original market request week, 2) among those, minimise the advance lot-weeks),
and passes the result to the engine ONLY as internal plan positions
(psi4demand of the non-market nodes). The market request (Lot_IDs, weeks) is
never changed and the demand CSV is not rewritten.

Default OFF (not in the headless "safe" set; GUI checkbox off). When OFF the
plan is exactly as before.

Settings: ``capacity_layer_config.csv`` next to capacity_plan.csv
    key,value
    max_advance_weeks,17      (required -- the prebuild window, weeks)
The file is required when the plugin is ON (no silent default window).

Results: ``self.results[product]`` and ``sc_tree.capacity_layer_results``
(served, unallocated lots by market, advance lot-weeks, LP diagnostics, the
list of unallocated Lot_IDs). Unallocated lots are printed; they stay at the
market as backlog (never dropped).
"""
from __future__ import annotations

import csv
import os
import time

from wom.engine.plugin_base import WOMPlugin


CONFIG_FILENAME = "capacity_layer_config.csv"


class CapacityLayerConfigError(ValueError):
    """capacity_layer_config.csv / push_config.csv cannot be used by the layer."""


def read_layer_config(model_dir: str) -> dict:
    path = os.path.join(model_dir, CONFIG_FILENAME)
    if not os.path.exists(path):
        raise CapacityLayerConfigError(
            f"Capacity Layer is ON but {CONFIG_FILENAME} is missing in {model_dir}. "
            "Create it with the line 'max_advance_weeks,<weeks>' (the prebuild window).")
    cfg = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cfg[(row.get("key") or "").strip()] = (row.get("value") or "").strip()
    try:
        cfg["max_advance_weeks"] = int(cfg["max_advance_weeks"])
    except (KeyError, ValueError):
        raise CapacityLayerConfigError(
            f"{path}: max_advance_weeks must be a whole number of weeks") from None
    if cfg["max_advance_weeks"] < 0:
        raise CapacityLayerConfigError(f"{path}: max_advance_weeks must be >= 0")
    return cfg


def read_push_leads(model_dir: str) -> dict:
    """{(sku_id, node_name): push_lead_time_weeks} for Mode 4 rows only."""
    path = os.path.join(model_dir, "push_config.csv")
    leads = {}
    if not os.path.exists(path):
        return leads
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if any(int(r.get(k) or 0) for k in ("push_qty_per_week", "buffer_lots",
                                                "pre_build_qty_per_week")):
                raise CapacityLayerConfigError(
                    f"push_config.csv {r.get('sku_id')}/{r.get('node_id')}: the Capacity Layer "
                    "supports only demand-anchored Mode 4 (push_lead_time_weeks)")
            lt = int(r.get("push_lead_time_weeks") or 0)
            if lt > 0:
                leads[(r["sku_id"].strip(), r["node_id"].strip())] = lt
    return leads


class CapacityLayerPlugin(WOMPlugin):
    name = "capacity_layer"
    label = "Capacity Layer（上位の能力の層）"
    description = ("After Backward, allocates each market lot to a feasible internal plan "
                   "week under the capacities (LP), keeping the market Lot_IDs and request "
                   "weeks. Needs capacity_layer_config.csv.")

    def __init__(self, *, max_advance_weeks: int = None, apply: bool = True,
                 capacity_override: dict = None, capture: dict = None):
        """Keyword arguments are for measuring tools (not used by the GUI).

        max_advance_weeks : overrides the config file's window.
        apply             : False = solve and record only, do not touch the plan.
        capacity_override : {(product, node_name): [cap or None per week]} --
                            replaces those nodes' capacities in the upper problem.
        capture           : dict filled with {product: (adapter, problem)}.
        """
        self._max_advance = max_advance_weeks
        self._apply = apply
        self._override = dict(capacity_override or {})
        self._capture = capture
        self.results: dict = {}

    def on_pre_plan(self, sc_tree, weeks, config, **kw):
        self.results = {}
        model_dir = os.path.dirname(config.get("cap_path", "") or "")
        self._model_dir = model_dir
        if self._max_advance is None:
            self._window = read_layer_config(model_dir)["max_advance_weeks"]
        else:
            self._window = int(self._max_advance)
        self._leads = read_push_leads(model_dir)
        sc_tree.capacity_layer_results = self.results

    def on_post_backward(self, sc_tree, prod_nm, weeks, config, **kw):
        from wom.capacity_layer.serial_adapter import SerialLineAdapter
        from wom.capacity_layer.solver import solve_lp
        t0 = time.perf_counter()
        adapter = SerialLineAdapter.from_tree(
            sc_tree, [prod_nm],
            push_leads_by_name={k: v for k, v in self._leads.items() if k[0] == prod_nm})
        problem = adapter.problem_from_tree(sc_tree, prod_nm, self._window)
        for (prod, name), caps in self._override.items():
            if prod != prod_nm:
                continue
            nid = next((n for n, r in adapter.nodes.items() if r["node_name"] == name), None)
            if nid is None:
                raise CapacityLayerConfigError(f"capacity_override: {prod}/{name} is not in the tree")
            for w, c in enumerate(caps):
                problem.capacities[nid, w] = c
                if ("backward_root:" + nid, w) in problem.capacities:
                    problem.capacities["backward_root:" + nid, w] = c
        if self._capture is not None:
            self._capture[prod_nm] = (adapter, problem)
        sol = solve_lp(problem)
        rows = adapter.expand(problem, sol)
        placed = adapter.apply_positions(sc_tree, prod_nm, rows) if self._apply else 0
        unalloc = [r for r in rows if r["status"] == "unallocated"]
        by_market = {}
        for r in unalloc:
            by_market[r["market"]] = by_market.get(r["market"], 0) + 1
        res = {
            "product": prod_nm, "max_advance_weeks": self._window,
            "demand_lots": sum(r.quantity for r in problem.requests),
            "served": sol.served, "unallocated": len(unalloc),
            "unallocated_by_market": by_market,
            "advance_lot_weeks": sol.advance_lot_weeks,
            "advanced_lots": sum(1 for r in rows if r["status"] == "assigned"
                                 and r["plan_index"] != r["due_index"]),
            "relaxation_upper_bound": sol.relaxation_upper_bound,
            "fractional_cells": sol.fractional_cells,
            "applied": self._apply, "placed": placed,
            "options": len(problem.options),
            "requests_without_option": problem.metadata["requests_without_option"],
            "unset_capacity_nodes": problem.metadata["unset_capacity_nodes"],
            "elapsed_seconds": round(time.perf_counter() - t0, 3),
            "unallocated_lots": [(r["lot_id"], r["market"], r["due_week"]) for r in unalloc],
            "assignments": rows,
        }
        self.results[prod_nm] = res
        msg = (f"[CapacityLayer] {prod_nm}: served {sol.served}/{res['demand_lots']}, "
               f"unallocated {len(unalloc)}, advance lot-weeks {sol.advance_lot_weeks}, "
               f"window {self._window} wks")
        print(msg)
        if unalloc:
            print(f"[CapacityLayer] WARNING {prod_nm}: {len(unalloc)} lots cannot be allocated "
                  f"by their request week (they stay as market backlog): {by_market}")
