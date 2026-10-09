"""
wom/plugins/rice_seasonal.py
─────────────────────────────
RiceSeasonalPlugin（収穫・玄米保管・精米）  Hook: POST_BACKWARD
RequestLetter_RiceSeasonal_Implementation B

Allocates each market demand ID to a past harvest, the brown-rice warehouse
and a milling week close to the request (wom/capacity_layer/rice_seasonal.py)
and passes the result to the engine only as internal plan positions. The
market request (Lot_ID, request week) is never changed; IDs that cannot be
allocated stay as market backlog and are listed.

Joint computation point (letter B "フックの注意"): the planning loop runs
Backward -> POST_BACKWARD -> copy -> Forward one product at a time. A mill
shared by the products must be solved once for all of them, after every
PRE_PLAN plugin has changed the market demand (HolidayCalendar demand
multipliers). So the joint problem is solved at the FIRST product's
POST_BACKWARD (every product's market demand is final by then -- demand lots
are generated for all products before the loop and only PRE_PLAN changes
them), and each product's POST_BACKWARD writes only that product's
positions. Before writing, the product's market requests are compared with
the ones the joint problem used; any difference stops the run.

Registered last in ALL_BUILTIN_PLUGINS, so its positions are the last word
after the other POST_BACKWARD plugins. Default OFF. Needs the lot flow mode
"identity" and the rice_*.csv inputs (wom/capacity_layer/rice_seasonal.py
load_inputs); missing inputs stop the run. (The legacy HarvestBatchPlugin,
which made anonymous OI_ opening lots, was removed on 2026-10-09.)
"""
from __future__ import annotations

import os
import time

from wom.engine.plugin_base import WOMPlugin


class RiceSeasonalPlugin(WOMPlugin):
    name = "rice_seasonal"
    fatal_errors = True   # an error stops the run (wom/engine/hook_bus.py), never a silent plain plan
    label = "Rice Seasonal（収穫・玄米保管・精米）"
    description = ("Allocates market demand IDs to past harvests, the brown-rice warehouse and "
                   "milling weeks (upper layer, joint for all products). Needs rice_*.csv.")

    def __init__(self):
        self.results: dict = {}

    def on_pre_plan(self, sc_tree, weeks, config, **kw):
        self.results = {}
        self._model_dir = os.path.dirname(config.get("cap_path", "") or "")
        mode = config.get("lot_flow_mode")
        if mode is None:   # the GUI does not pass it; read the model's planning_config.csv
            from wom.engine.warmup import read_lot_flow_mode
            from wom.engine.forward_planner import resolve_lot_flow_mode
            mode = resolve_lot_flow_mode(read_lot_flow_mode(self._model_dir))
        self._mode = mode
        self._solved = None
        sc_tree.rice_seasonal_results = self.results

    def _market_signature(self, tree, product):
        return {nd.node_id: [tuple(nd.psi4demand[w][0]) for w in range(tree.num_weeks())]
                for nd in tree.iter_all_nodes(product) if nd.node_type == "leaf_out"}

    def _solve_all(self, sc_tree):
        from wom.capacity_layer import rice_seasonal as rs
        if not os.path.exists(os.path.join(self._model_dir, "rice_seasonal_config.csv")):
            raise rs.RiceInputError(
                "このモデルには Rice の設定（rice_seasonal_config.csv）がありません。"
                "Plugins の Rice Seasonal を OFF にして計画してください "
                f"(model folder: {self._model_dir or '(unknown)'})")
        if self._mode != "identity":
            raise rs.RiceInputError("Rice Seasonal needs lot_flow_mode=identity "
                                    "(planning_config.csv); the plan is in " + str(self._mode))
        t0 = time.perf_counter()
        products = list(sc_tree.products)
        inputs = rs.load_inputs(self._model_dir, list(sc_tree.week_labels))
        rp = rs.build_problem(sc_tree, products, inputs)
        sol = rs.solve(rp)
        rows = rs.expand(rp, sol)
        self._solved = {"problem": rp, "solution": sol, "rows": rows,
                        "signature": {p: self._market_signature(sc_tree, p) for p in products}}
        rs_start = inputs.policy.report_start
        rs_idx = rp.weeks.index(rs_start) if rs_start else 0
        un = [r for r in rows if r["status"] == "unallocated"]
        by = {}
        for r in un:
            k = (r["product"], "warmup" if r["due"] < rs_idx else "report")
            by[k] = by.get(k, 0) + 1
        self.results.update({
            "_problem": rp, "_solution": sol,      # for the check tools (objects)
            "_joint": {"stats": rp.stats, "solver": sol.stats, "objective":
                       {k: v for k, v in sol.objective.items() if k != "proportional_targets"},
                       "lp_upper_bound": sol.lp_upper_bound, "served": sol.served,
                       "unallocated": len(un),
                       "unallocated_by_product_period": {f"{p}|{t}": n for (p, t), n in sorted(by.items())},
                       "report_start": rs_start, "elapsed_seconds": round(time.perf_counter() - t0, 2)}})
        print(f"[RiceSeasonal] joint problem: {rp.stats['requests']} requests, {rp.stats['lots']} IDs, "
              f"{rp.stats['options']} options; served {sol.served}, unallocated {len(un)} "
              f"({round(time.perf_counter() - t0, 1)} s)")
        if un:
            print(f"[RiceSeasonal] WARNING: {len(un)} IDs cannot be allocated by their request week "
                  f"(they stay as market backlog): " +
                  ", ".join(f"{p} {t} {n}" for (p, t), n in sorted(by.items())))

    def on_post_backward(self, sc_tree, prod_nm, weeks, config, **kw):
        from wom.capacity_layer import rice_seasonal as rs
        if self._solved is None:
            self._solve_all(sc_tree)
        if self._market_signature(sc_tree, prod_nm) != self._solved["signature"][prod_nm]:
            raise rs.RiceInputError(f"{prod_nm}: the market requests changed after the joint Rice "
                                    "problem was solved (a plugin changed demand after PRE_PLAN)")
        rows = self._solved["rows"]
        placed = rs.apply_positions(sc_tree, prod_nm, self._solved["problem"], rows)
        mine = [r for r in rows if r["product"] == prod_nm]
        self.results[prod_nm] = {
            "demand_ids": len(mine), "placed": placed,
            "unallocated": sum(r["status"] == "unallocated" for r in mine),
            "rows": mine,
        }
