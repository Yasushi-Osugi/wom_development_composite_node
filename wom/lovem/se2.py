# -*- coding: utf-8 -*-
"""
wom/lovem/se2.py — fixes the DEFINITION of the SE2 check case (request A1/A4-5).

SE2 = Explicit Closure report §6 SE2: ev-thailand-2026 / EVmaker_Import /
Factory_Import_CN (push), 2026-W38 and 2026-W39: planned S 150+150 vs actual
shipment 132+0 -> 168 lots.

This module only COUNTS (per week) from the saved run folder. It does not
classify any lot (early / on-time / late / unmet): that is stage C (Astra君).
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

SE2 = {
    "case_id": "SE2",
    "source": "docs/development/WOM_ExplicitClosure_v1r5m0_Report.md §6 SE2",
    "model_dir": "data/sample/ev-thailand-2026",
    "plugins": ["BufferingStockOptimizerPlugin", "CapacityOverridePlugin", "HolidayCalendarPlugin"],
    "product_id": "EVmaker_Import",
    "node_name": "Factory_Import_CN",
    "target_weeks": ["2026-W38", "2026-W39"],
    "closure_weeks": ["2026-W40", "2026-W41"],
}

FORMULAS = {
    "planned_s": "entry_count of state_digests (snapshot=<product>/final, layer=supply, bucket=S) at the node/week",
    "actual_s": "number of events.jsonl rows event_type=actual_ship at the node/week",
    "signed_gap": "planned_s - actual_s",
    "shortfall": "max(0, planned_s - actual_s)",
    "excess": "max(0, actual_s - planned_s)",
    "push_shortfall": "events.jsonl event_type=push_shortfall quantity (engine PlanNode._push_shortfall)",
    "SE2_168": "sum over target_weeks of shortfall (== sum of push_shortfall over target_weeks)",
}


from wom.lovem.io import iter_jsonl as _jsonl, run_file


def weekly_counts(run_dir: str, product: str, node_name: str) -> dict:
    import csv
    with open(os.path.join(run_dir, "nodes.csv"), encoding="utf-8") as f:
        node_id = next(r["node_id"] for r in csv.DictReader(f)
                       if r["product_id"] == product and r["node_name"] == node_name)
    with open(os.path.join(run_dir, "weeks.csv"), encoding="utf-8") as f:
        labels = [r["engine_week_label"] for r in csv.DictReader(f)]
    planned = {}
    for d in _jsonl(run_file(run_dir, "state_digests.jsonl")):
        if (d["snapshot_id"] == f"{product}/final" and d["node_id"] == node_id
                and d["layer"] == "supply" and d["bucket"] == "S"):
            planned[d["week_index"]] = d["entry_count"]
    actual, psf = defaultdict(int), defaultdict(int)
    for e in _jsonl(run_file(run_dir, "events.jsonl")):
        if e["node_id"] != node_id or e["product_id"] != product:
            continue
        if e["event_type"] == "actual_ship":
            actual[e["week_index"]] += 1
        elif e["event_type"] == "push_shortfall":
            psf[e["week_index"]] += e["quantity"]
    rows = []
    for w, lbl in enumerate(labels):
        p, a = planned.get(w), actual.get(w, 0)
        rows.append({"week_index": w, "week": lbl, "planned_s": p, "actual_s": a,
                     "signed_gap": None if p is None else p - a,
                     "shortfall": None if p is None else max(0, p - a),
                     "excess": None if p is None else max(0, a - p),
                     "push_shortfall": psf.get(w, 0)})
    return {"node_id": node_id, "labels": labels, "rows": rows}


def build_se2_case(run_dir: str, comparison: dict = None) -> dict:
    wc = weekly_counts(run_dir, SE2["product_id"], SE2["node_name"])
    tw = [r for r in wc["rows"] if r["week"] in SE2["target_weeks"]]
    man = json.load(open(os.path.join(run_dir, "manifest.json"), encoding="utf-8"))
    case = dict(SE2)
    case.update({
        "run_id": man["run_id"], "code_sha": man["code_sha"],
        "node_id": wc["node_id"], "formulas": FORMULAS,
        "target_week_rows": tw,
        "sum_signed_gap_target_weeks": sum(r["signed_gap"] for r in tw),
        "sum_shortfall_target_weeks": sum(r["shortfall"] for r in tw),
        "sum_push_shortfall_target_weeks": sum(r["push_shortfall"] for r in tw),
        "horizon_totals": {
            "actual_s": sum(r["actual_s"] for r in wc["rows"]),
            "planned_s": sum(r["planned_s"] or 0 for r in wc["rows"]),
            "push_shortfall": sum(r["push_shortfall"] for r in wc["rows"]),
            "shortfall_weeks": [r["week"] for r in wc["rows"] if r["shortfall"]],
        },
        "which_is_168": None,
        "classification": "not performed here (stage C, independent checker)",
    })
    if comparison is not None:
        case["comparison_run"] = comparison
        cmp_rows = {r["week"]: r for r in comparison.get("target_week_rows", [])}
        case["diff_vs_comparison_target_weeks"] = {
            wk: {"shortfall": r["shortfall"] - cmp_rows.get(wk, {}).get("shortfall", 0),
                 "actual_s": r["actual_s"] - cmp_rows.get(wk, {}).get("actual_s", 0)}
            for wk, r in ((r["week"], r) for r in tw)}
        case["sum_diff_shortfall_vs_comparison"] = sum(
            v["shortfall"] for v in case["diff_vs_comparison_target_weeks"].values())
    cands = {"sum_signed_gap_target_weeks": case["sum_signed_gap_target_weeks"],
             "sum_shortfall_target_weeks": case["sum_shortfall_target_weeks"],
             "sum_push_shortfall_target_weeks": case["sum_push_shortfall_target_weeks"],
             "sum_diff_shortfall_vs_comparison": case.get("sum_diff_shortfall_vs_comparison")}
    case["candidates"] = cands
    case["which_is_168"] = [k for k, v in cands.items() if v == 168]
    with open(os.path.join(run_dir, "se2_case.json"), "w", encoding="utf-8") as f:
        json.dump(case, f, ensure_ascii=False, indent=2)
    return case
