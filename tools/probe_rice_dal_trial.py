#!/usr/bin/env python3
"""Rice DAL Trial at a fixed WOM SHA. New case/data and read-only probes only.

Run from the repository root with PYTHONHASHSEED=0 and MPLBACKEND=Agg.
  python -m tools.probe_rice_dal_trial prepare --out /absolute/output
  python -m tools.probe_rice_dal_trial measure --case baseline --out /absolute/output
  python -m tools.probe_rice_dal_trial measure --case legacy_calendar --out /absolute/output
  python -m tools.probe_rice_dal_trial measure --case dal_current --out /absolute/output
  python -m tools.probe_rice_dal_trial prepare-increased --out /absolute/output
  python -m tools.probe_rice_dal_trial measure --case dal_increased --out /absolute/output
  python -m tools.probe_rice_dal_trial measure --case dal_observed --out /absolute/output

No git add/commit/push, no protected-core, original-data or golden writes.
The only monkeypatches wrap calls, read lists, and restore functions in finally.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import csv
import datetime as dt
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time
from unittest.mock import patch

import pandas as pd

BASE_SHA = "d848c5fa0565d70f6817c1a0257341067712deca"
ORIGINAL = Path("data/sample/rice-japan-2027-2028")
TRIAL = Path("data/sample/rice-japan-2027-2028-dal")
REPORT_START, REPORT_END = "2027-W01", "2028-W52"
RICE_PLUGINS = "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,HarvestBatchPlugin"
DAL_PLUGINS = "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"


def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()


def check_base():
    if git("rev-parse", "HEAD") != BASE_SHA:
        raise RuntimeError("wrong HEAD; this probe requires " + BASE_SHA)
    # Only untracked additions are allowed. Tracked code, all samples and goldens stay intact.
    if git("diff", "HEAD", "--name-only"):
        raise RuntimeError("tracked files differ from the measurement baseline")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str, sort_keys=True)


def write_csv(path, rows, fields=None):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        rows = list(rows); fields = list(rows[0]) if rows else []
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "wt", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fields); wr.writeheader(); wr.writerows(rows)


def iso_weeks(start, end):
    y, w = map(int, start.split("-W")); date = dt.date.fromisocalendar(y, w, 1)
    out = []
    while True:
        yy, ww, _ = date.isocalendar(); label = f"{yy}-W{ww:02d}"
        if label > end: return out
        out.append(label); date += dt.timedelta(weeks=1)


def node_rows(tree, prod):
    return list(tree.iter_all_nodes(prod))


def prepare(out):
    check_base(); out.mkdir(parents=True, exist_ok=True)
    if TRIAL.exists(): raise RuntimeError("trial already exists; refusing overwrite")
    shutil.copytree(ORIGINAL, TRIAL)
    # Only explicitly listed demand/period/config/capacity adjustments. No automatic warmup.
    d = pd.read_csv(ORIGINAL / "demand_forecast.csv")
    old_weeks = sorted(d.week.unique())
    pattern = d[d.week.str.startswith("2026-")].copy()
    prior = pattern[pattern.week.str[-2:].astype(int) >= 37].copy()
    prior["week"] = prior.week.str.replace("2026-", "2025-", regex=False)
    demand = pd.concat([prior, d], ignore_index=True)
    # Original demand misses valid ISO 2026-W53. Explicit zero, never an inferred forecast.
    extra = pattern[pattern.week == "2026-W52"].copy()
    extra["week"] = "2026-W53"; extra["quantity"] = 0
    demand = pd.concat([demand, extra], ignore_index=True)
    demand.sort_values(["sku_id", "region", "week"]).to_csv(TRIAL / "demand_forecast.csv", index=False)
    cap = pd.read_csv(ORIGINAL / "capacity_plan.csv")
    prior_cap = cap[(cap.week.str.startswith("2026-")) &
                    (cap.week.str[-2:].astype(int).between(37, 52))].copy()
    prior_cap["week"] = prior_cap.week.str.replace("2026-", "2025-", regex=False)
    prior_cap["source"] = prior_cap.source.astype(str) + "_2025試行写し"
    # Original capacity ends 2028-W51 (156 consecutive ISO weeks). Supply explicit W52 rows.
    tail = cap[cap.week == "2026-W52"].copy(); tail["week"] = "2028-W52"
    tail["source"] = tail.source.astype(str) + "_2028W52試行補完"
    pd.concat([prior_cap, cap, tail], ignore_index=True).sort_values(
        ["week", "sku_id", "node_name"]).to_csv(TRIAL / "capacity_plan.csv", index=False)
    (TRIAL / "planning_config.csv").write_text("key,value\nlot_flow_mode,identity\n", encoding="utf-8")
    weeks = sorted(demand.week.unique())
    assert weeks == iso_weeks("2025-W37", REPORT_END)
    control = out / "models" / "legacy_calendar" / ORIGINAL.name
    control.parent.mkdir(parents=True, exist_ok=True); shutil.copytree(ORIGINAL, control)
    pd.concat([d, extra], ignore_index=True).sort_values(["sku_id", "region", "week"]).to_csv(
        control / "demand_forecast.csv", index=False)
    pd.concat([cap, tail], ignore_index=True).sort_values(["week", "sku_id", "node_name"]).to_csv(
        control / "capacity_plan.csv", index=False)
    integrity = {p: sha(p) for p in git("ls-files").splitlines() if Path(p).is_file()}
    env = {"python": platform.python_version(), "platform": platform.platform(),
           "packages": {m: importlib.metadata.version(m) for m in
                        ["pandas", "numpy", "matplotlib", "pytest", "networkx", "scipy"]}}
    write_json(out / "raw/qualification/tracked_sha256_before.json", integrity)
    write_json(out / "raw/qualification/environment.json", env)
    write_json(out / "raw/preparation.json", {
        "baseline_sha": BASE_SHA, "report_start": REPORT_START, "report_end": REPORT_END,
        "trial_start": weeks[0], "trial_end": weeks[-1], "trial_weeks": len(weeks),
        "start_selection": "earliest existing crop-window start: Hokkaido W37; Q1 measured, not assumed",
        "original_demand_unique_weeks": len(old_weeks), "original_detected_end": "2028-W51",
        "original_csv_end": "2028-W52", "missing_original_demand_weeks": ["2026-W53"],
        "original_capacity_end": str(cap.week.max()),
        "zero_demand_assumption": "2026-W53 explicitly zero; no 53rd-week sales forecast is available",
        "changes": ["2025-W37..W52 demand copied from 2026 same week-number", "2025 capacity same crop windows",
                    "2026-W53 explicit zero demand", "2028-W52 capacity copied from 2026-W52",
                    "identity mode; no warmup_lt/planning_start; HarvestBatch disabled by runner plugin selection"],
        "original_model_hashes": {p.name: sha(p) for p in ORIGINAL.iterdir() if p.is_file()},
        "trial_model_hashes": {p.name: sha(p) for p in TRIAL.iterdir() if p.is_file()}})
    print("PREPARED", len(weeks), weeks[0], weeks[-1], flush=True)


def prepare_increased(out):
    check_base()
    summary = json.loads((out / "raw/dal_current/summary.json").read_text())
    dst = out / "models/dal_increased" / TRIAL.name
    if dst.exists(): raise RuntimeError("increased case already exists")
    dst.parent.mkdir(parents=True, exist_ok=True); shutil.copytree(TRIAL, dst)
    cap = pd.read_csv(dst / "capacity_plan.csv"); changes = []
    for prod, field, crop_weeks in [("Koshihikari", "Tanbo_Niigata", 3),
                                   ("Yumepirika", "Tanbo_Hokkaido", 7)]:
        full_annual = [v for y, v in summary["demand_by_product_year"][prod].items() if y != "2025"]
        target = max(full_annual)
        needed = (target + crop_weeks - 1) // crop_weeks
        mask = (cap.sku_id == prod) & (cap.node_name == field) & (cap.max_supply >= 1)
        old = sorted(cap.loc[mask, "max_supply"].unique().tolist())
        new = max(int(max(old)), needed)
        cap.loc[mask, "max_supply"] = new
        changes.append({"product": prod, "field": field, "old_per_crop_week": old,
                        "new_per_crop_week": new, "crop_weeks": crop_weeks,
                        "annual_capacity": new * crop_weeks, "max_observed_annual_demand": target,
                        "basis": "maximum complete-year demand after HolidayCalendar, rounded up; annual sufficiency only"})
    cap.to_csv(dst / "capacity_plan.csv", index=False)
    write_json(out / "raw/increased_capacity_definition.json", changes)
    print("INCREASED", changes, flush=True)


def fingerprint(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def record_state(tree, prod, phase, dest):
    rows = []
    production = []
    for n in node_rows(tree, prod):
        for w, label in enumerate(tree.week_labels):
            rows.append({"phase": phase, "product": prod, "node_id": n.node_id,
                "node": n.node_name, "node_type": n.node_type, "week": label,
                "S": len(n.psi4demand[w][0]), "CO": len(n.psi4demand[w][1]),
                "I": len(n.psi4demand[w][2]), "P": len(n.psi4demand[w][3]),
                "cap_hard": n.cap_hard(w), "cap_soft": n.cap_soft(w), "is_open": n.is_open(w)})
            if n.node_type == "leaf_in":
                for lot in n.psi4demand[w][3]:
                    production.append({"product": prod, "node_id": n.node_id, "node": n.node_name,
                                       "week": label, "week_index": w, "lot_id": lot})
    write_csv(dest / f"{prod}_{phase}_demand_counts.csv", rows)
    write_csv(dest / f"{prod}_{phase}_field_P.csv.gz", production,
              ["product", "node_id", "node", "week", "week_index", "lot_id"])


def measure(case, out):
    check_base(); raw = out / "raw" / case
    if raw.exists(): raise RuntimeError("case output already exists: " + str(raw))
    raw.mkdir(parents=True)
    if case == "baseline": model, plugins = ORIGINAL, RICE_PLUGINS
    elif case == "legacy_calendar": model, plugins = out / "models/legacy_calendar" / ORIGINAL.name, RICE_PLUGINS
    elif case in ("dal_current", "dal_observed"): model, plugins = TRIAL, DAL_PLUGINS
    elif case == "dal_increased": model, plugins = out / "models/dal_increased" / TRIAL.name, DAL_PLUGINS
    else: raise ValueError(case)
    before = {p.name: sha(p) for p in model.iterdir() if p.is_file()}
    import tools.run_headless_from_folder as rh
    import wom.engine.backward_planner as bp
    import wom.engine.forward_planner as fp
    import wom.engine.hook_bus as hb
    import wom.ppc.ppc_runner as pr
    old_b, old_f, old_h, old_s, old_p = bp.BackwardPlanner.run, fp.ForwardPlanner.run, hb.HookBus.fire, rh._psi_signature, pr.run_ppc_from_psi
    store = {"bres": {}, "fres": {}}

    def b(self, prod):
        r = old_b(self, prod); store["bres"][prod] = r
        record_state(self.sc_tree, prod, "post_backward", raw)
        return r

    def h(self, hook, **kw):
        result = old_h(self, hook, **kw)
        if hook == hb.HOOK_POST_BACKWARD:
            record_state(kw["sc_tree"], kw["prod_nm"], "post_backward_hooks", raw)
        return result

    def f(self, prod):
        r = old_f(self, prod); store["fres"][prod] = r
        return r

    def s(tree, n):
        store["tree"] = tree; return old_s(tree, n)

    def p(*args, **kw):
        result = old_p(*args, **kw)
        store["ppc_source"] = {"sales_source": result.get("sales_source"), "psi_mode": result.get("_psi_mode"),
                               "data_dir": kw.get("data_dir"), "use_node_name": kw.get("use_node_name")}
        return result

    t0 = time.perf_counter()
    with patch.object(bp.BackwardPlanner, "run", b), patch.object(fp.ForwardPlanner, "run", f), \
         patch.object(hb.HookBus, "fire", h), patch.object(rh, "_psi_signature", s), \
         patch.object(pr, "run_ppc_from_psi", p), tempfile.TemporaryDirectory(prefix="rice_dal_") as tmp:
        if case == "dal_observed":
            from wom.lovem.observer import observe_run
            snap = observe_run(str(model), str(out / "lovem/run_dal_current"), plugins=plugins,
                               repo=os.getcwd(), label="rice_dal_trial", lot_flow_mode="identity")
            ppc_dir = out / "lovem/run_dal_current/ppc"
        else:
            work = Path(tmp) / model.name; shutil.copytree(model, work)
            ppc_dir = raw / "ppc"
            snap = rh.run(str(work), plugins_spec=plugins, output_ppc_dir=str(ppc_dir), verbose=True)
        tree = store["tree"]
        summarize(tree, store, snap, raw, ppc_dir, case, plugins)
    after = {p.name: sha(p) for p in model.iterdir() if p.is_file()}
    assert before == after, "model was mutated"
    write_json(raw / "run_manifest.json", {"baseline_sha": BASE_SHA, "case": case,
        "model_path": str(model), "model_sha256": before, "plugins": plugins.split(","),
        "lot_flow_mode": tree.lot_flow_mode, "cpu_size": tree.cpu_size,
        "report_start": REPORT_START, "report_end": REPORT_END,
        "elapsed_seconds": round(time.perf_counter() - t0, 3), "model_unchanged": True})
    print("COMPLETED", case, round(time.perf_counter() - t0, 2), flush=True)


def summarize(tree, store, snap, raw, ppc_dir, case, plugins):
    labels = tree.week_labels; n_weeks = len(labels)
    write_json(raw / "headless_snapshot.json", snap)
    write_json(raw / "backward_results.json.gz", {p: vars(r) for p, r in store["bres"].items()})
    write_json(raw / "forward_results.json.gz", {p: {k: v for k, v in vars(r).items() if not k.startswith("_")}
                                                for p, r in store["fres"].items()})
    anchors = {}; node_due = {}; demand_year = collections.defaultdict(collections.Counter)
    node_counts, markets, q1 = [], [], []
    state_fingerprints, actual_fingerprints = {}, {}
    anchor_rows = []
    for prod in tree.products:
        for nd in node_rows(tree, prod):
            # Market S after HolidayCalendar is the actual anchor, including holiday-specific IDs.
            ndue = {}
            for w in range(n_weeks):
                # push_sub rewrites supply S as a display of physical shipments.
                # Original node demand must come from psi4demand, never that display.
                for lot in nd.psi4demand[w][0]: ndue.setdefault(lot, w)
                if nd.node_type == "leaf_out":
                    for lot in nd.psi4demand[w][0]:
                        if lot in anchors: raise AssertionError("duplicate market anchor: " + lot)
                        anchors[lot] = (prod, nd.node_id, w)
                        demand_year[prod][labels[w][:4]] += 1
                        anchor_rows.append({"product": prod, "node_id": nd.node_id, "node": nd.node_name,
                                            "required_week": labels[w], "required_week_index": w, "lot_id": lot})
            node_due[nd.node_id] = ndue
            for layer, psi in [("demand", nd.psi4demand), ("supply", nd.psi4supply)]:
                state_fingerprints[prod + "|" + nd.node_id + "|" + layer] = fingerprint(psi)
            actual_fingerprints[prod + "|" + nd.node_id] = fingerprint(nd._actual_ship)
    write_csv(raw / "demand_anchors.csv.gz", anchor_rows)
    shipments, statuses = [], []
    early_node = late_node = unknown_node = 0
    for prod in tree.products:
        for nd in node_rows(tree, prod):
            due = node_due[nd.node_id]; actual = {}
            for w, ids in nd._actual_ship.items():
                for occurrence, lot in enumerate(ids):
                    dw = due.get(lot); mw = anchors.get(lot, (None, None, None))[2]
                    # push_sub intentionally sends before requests; outside the normal rule.
                    if nd.plan_mode != "push_sub":
                        early_node += int(dw is not None and w < dw)
                        late_node += int(dw is not None and w > dw)
                        unknown_node += int(dw is None)
                    shipments.append({"product": prod, "node_id": nd.node_id, "node": nd.node_name,
                        "week": labels[w], "week_index": w, "sequence": occurrence,
                        "lot_id": lot, "node_required_week_index": dw,
                        "market_required_week_index": mw, "plan_mode": nd.plan_mode})
                    actual.setdefault(lot, []).append(w)
            for w, label in enumerate(labels):
                co_end = list(nd.psi4supply[w + 1][1]) if w + 1 < n_weeks else []
                inv = nd.psi4supply[w][2]
                node_counts.append({"product": prod, "node_id": nd.node_id, "node": nd.node_name,
                    "node_type": nd.node_type, "side": nd.side, "plan_mode": nd.plan_mode,
                    "week": label, "week_index": w, "in_report": REPORT_START <= label <= REPORT_END,
                    "demand_S": len(nd.psi4demand[w][0]), "demand_P": len(nd.psi4demand[w][3]),
                    "supply_S": len(nd.psi4supply[w][0]), "supply_P": len(nd.psi4supply[w][3]),
                    "I": len(inv), "CO_start": len(nd.psi4supply[w][1]),
                    "actual_S": len(nd._actual_ship.get(w, [])), "cap_hard": nd.cap_hard(w),
                    "cap_soft": nd.cap_soft(w), "is_open": nd.is_open(w)})
            if nd.node_type == "leaf_out":
                market_ids = {lot: a[2] for lot, a in anchors.items() if a[1] == nd.node_id}
                for lot, w in market_ids.items():
                    sw = actual.get(lot, [])
                    status = ("not_shipped" if not sw else "early" if sw[0] < w else
                              "on_time" if sw[0] == w else "late")
                    statuses.append({"product": prod, "node": nd.node_name, "node_id": nd.node_id,
                        "lot_id": lot, "required_week": labels[w], "required_week_index": w,
                        "in_report": REPORT_START <= labels[w] <= REPORT_END, "status": status,
                        "shipment_week": labels[sw[0]] if sw else "", "shipment_week_index": sw[0] if sw else "",
                        "delay_weeks": sw[0] - w if sw else "", "shipment_occurrences": len(sw)})
                for scope in ["all", "report"]:
                    rr = [r for r in statuses if r["node_id"] == nd.node_id and (scope == "all" or r["in_report"])]
                    c = collections.Counter(r["status"] for r in rr)
                    markets.append({"product": prod, "node": nd.node_name, "scope": scope,
                        "demand": len(rr), "on_time": c["on_time"], "late": c["late"], "early": c["early"],
                        "not_shipped": c["not_shipped"], "actual_shipped_for_cohort": len(rr) - c["not_shipped"],
                        "on_time_fill_rate": c["on_time"] / len(rr) if rr else None,
                        "cohort_fill_by_horizon_end": (len(rr) - c["not_shipped"]) / len(rr) if rr else None,
                        "max_delay_weeks": max((r["delay_weeks"] for r in rr if r["delay_weeks"] != ""), default=0),
                        "duplicate_shipped_ids": sum(r["shipment_occurrences"] > 1 for r in rr)})
            if nd.node_type == "leaf_in":
                harvest = [w for w in range(n_weeks) if nd.is_open(w) and int(nd.cap_hard(w)) > 0]
                for w in range(n_weeks):
                    for lot in nd.psi4demand[w][3]:
                        dw = due.get(lot)
                        eligible = [ww for ww in harvest if dw is not None and ww <= dw]
                        latest = max(eligible) if eligible else None
                        q1.append({"product": prod, "field": nd.node_name, "lot_id": lot,
                            "market_due_week": labels[anchors[lot][2]] if lot in anchors else "",
                            "field_required_week": labels[dw] if dw is not None else "",
                            "field_P_week": labels[w], "field_P_week_index": w,
                            "is_harvest_week": w in harvest,
                            "latest_eligible_harvest": labels[latest] if latest is not None else "",
                            "matches_latest_eligible_harvest": latest == w if latest is not None else False,
                            "no_prior_crop_in_horizon": latest is None})
    write_csv(raw / "node_week.csv", node_counts)
    write_csv(raw / "actual_shipments.csv.gz", shipments)
    write_csv(raw / "market_lot_status.csv.gz", statuses)
    write_csv(raw / "market_summary.csv", markets)
    write_csv(raw / "q1_field_placement.csv.gz", q1)
    opening = {p: dict(getattr(r, "opening_inv_counts", {})) for p, r in store["fres"].items()}
    q1summary = {}
    for prod in tree.products:
        rr = [r for r in q1 if r["product"] == prod]
        q1summary[prod] = {"field_P_occurrences": len(rr), "in_crop_week": sum(r["is_harvest_week"] for r in rr),
                          "latest_crop_match": sum(r["matches_latest_eligible_harvest"] for r in rr),
                          "no_prior_crop_in_horizon": sum(r["no_prior_crop_in_horizon"] for r in rr)}
    ppch = {p.name: sha(p) for p in sorted(ppc_dir.iterdir()) if p.is_file()}
    fps = {"states": state_fingerprints, "actual": actual_fingerprints,
           "forward": {p: fingerprint(vars(r)) for p, r in store["fres"].items()},
           "backward": {p: fingerprint(vars(r)) for p, r in store["bres"].items()},
           "snapshot": fingerprint(snap), "ppc_files": ppch}
    write_json(raw / "fingerprints.json", fps)
    write_json(raw / "summary.json", {"case": case, "period": snap["period"], "labels_end": labels[-1],
        "lot_flow_mode": tree.lot_flow_mode, "cpu_size": tree.cpu_size,
        "demand_by_product_year": {p: dict(c) for p, c in demand_year.items()},
        "markets": markets, "q1": q1summary, "opening_inv_counts": opening,
        "opening_inv_total": sum(sum(x.values()) for x in opening.values()),
        "synthetic_shipment_occurrences": sum(r["lot_id"].startswith("OI_") for r in shipments),
        "total_node_shipment_occurrences": len(shipments), "node_early_shipment_occurrences": early_node,
        "node_late_shipment_occurrences": late_node, "node_unknown_request_occurrences": unknown_node,
        "ppc": snap["ppc"], "ppc_source": store["ppc_source"],
        "forward": snap["forward"], "backward": snap["backward"]})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["prepare", "prepare-increased", "measure"])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--case", choices=["baseline", "legacy_calendar", "dal_current", "dal_increased", "dal_observed"])
    a = ap.parse_args(); out = a.out.resolve()
    if a.action == "prepare": prepare(out)
    elif a.action == "prepare-increased": prepare_increased(out)
    else:
        if not a.case: ap.error("measure requires --case")
        measure(a.case, out)


if __name__ == "__main__": main()
