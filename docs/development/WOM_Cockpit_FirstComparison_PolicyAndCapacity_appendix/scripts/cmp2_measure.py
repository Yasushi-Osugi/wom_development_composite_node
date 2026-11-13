# -*- coding: utf-8 -*-
"""CMP2 measurements that tools/compare_scenarios.py does not print (run from the repository root).

    python docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix/scripts/cmp2_measure.py

1. B1: the comparison value of the Thai cream minimum 70% trial, computed the same way as
   docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_appendix/scripts/th70_measure.py
   (sum over request weeks of delivered lots x 24 x unit contribution CM - FIXED 213,719,220),
   from A_late's quantity-allocation result; and the same quantity from the money run (PPC, Value Chain).
2. O5: serum shipments and money lines of each run vs the cmp1 baseline (same launch week).
3. O3/O7: cream factory production per week vs the shippable soft capacity.
4. Overview table: six runs (delivery, unmet, P0, inventory, age).
Writes output/cockpit_cmp2/measure/cmp2_measure.json and prints a summary.
"""
import csv
import json
import os
import sys

import pandas as pd

sys.path[:0] = [os.getcwd(), "docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/scripts"]
import make_allocation as MA      # noqa: E402  (unit contributions CM, git-tracked)

O = "output/cockpit_cmp2"
C1 = "output/cockpit_cmp1"
FIXED = 213719220.0               # th70_measure.py
CPU = 24
RUNS = {  # name -> (run dir, model dir, cmp1 baseline run of the same launch week)
    "late_soft11": (f"{C1}/run_late", f"{C1}/model_late", None),
    "early_soft11": (f"{C1}/run_early", f"{C1}/model_early", None),
    "A_late": (f"{O}/run_A_late", f"{O}/A_late_m", f"{C1}/run_late"),
    "A_early": (f"{O}/run_A_early", f"{O}/A_early_m", f"{C1}/run_early"),
    "B_late": (f"{O}/run_B_late", f"{O}/B_late", f"{C1}/run_late"),
    "B_early": (f"{O}/run_B_early", f"{O}/B_early", f"{C1}/run_early"),
}
out = {}

# 1. B1 comparison value
res = {r["source_demand_ref"]: r for r in csv.DictReader(open(
    f"{O}/udp/A_late/A_late_trim_to_capacity_latest/udp_result_by_request.csv", encoding="utf-8-sig"))}
contrib = 0.0
for ref, r in res.items():
    sku, reg, _ = ref.split("|")
    contrib += (int(r["on_time"]) + int(r["early"]) + int(r["late"])) * CPU * MA.CM[(sku, reg)]
ppc = json.load(open(f"{O}/run_A_late/ppc/ppc_kpi_summary.json", encoding="utf-8"))
v3 = pd.read_csv(f"{O}/run_A_late/vc/vc_v3_weekly.csv")
v3 = v3[v3["group_key"] == "GROUP"]
out["B1_comparison_value"] = {
    "formula_th70_measure": contrib - FIXED,
    "ppc_gross_profit_base_full": ppc["gross_profit_base"],
    "vc_profit_r2_hq_full_period": float(v3["profit_r2_hq_wk"].sum()),
    "vc_profit_r2_hq_report_period": float(v3[v3["in_report"]]["profit_r2_hq_wk"].sum()),
}

# 2. O5 serum identity
SK = ["lot_id", "kind", "edge", "ship_week", "arrival_week", "lots"]
MK = ["lot_id", "week", "entity", "kind", "scope", "family", "basis", "node", "amt_hq"]


def serum_sets(run):
    sh = pd.read_csv(f"{run}/vc/vc_shipments.csv.gz", dtype=str)
    mo = pd.read_csv(f"{run}/vc/vc_money_lines.csv.gz", dtype={"lot_id": str})
    sh, mo = sh[sh["product"] == "COS_Serum"], mo[mo["product"] == "COS_Serum"].copy()
    mo["amt_hq"] = mo["amt_hq"].round(6)
    return set(map(tuple, sh[SK].astype(str).values)), set(map(tuple, mo[MK].astype(str).values))


out["O5_serum_vs_baseline"] = {}
for n, (run, _m, base) in RUNS.items():
    if base is None:
        continue
    a, b = serum_sets(base), serum_sets(run)
    out["O5_serum_vs_baseline"][n] = {"shipments_base": len(a[0]), "shipments_run": len(b[0]),
                                      "shipments_only_base": len(a[0] - b[0]), "shipments_only_run": len(b[0] - a[0]),
                                      "money_only_base": len(a[1] - b[1]), "money_only_run": len(b[1] - a[1])}

# 3/4. factory, overview
ov = {}
for n, (run, model, _b) in RUNS.items():
    fl = pd.read_csv([os.path.join(dp, f) for dp, _, fs in os.walk(f"{run}/flow_check") for f in fs
                      if f == "flow_check_market.csv"][0], encoding="utf-8-sig")
    fl = fl[~fl["leaf"].fillna("").astype(str).str.startswith("Σ") & ~fl["product"].astype(str).str.startswith("Σ")]
    g = lambda s, r, c: int(fl[(fl["product"] == s) & (fl["leaf"] == r)][c].sum())   # noqa: E731
    cream = fl[fl["product"] == "COS_Cream"]
    v = pd.read_csv(f"{run}/vc/vc_v3_weekly.csv")
    v = v[v["group_key"] == "GROUP"]
    inv = pd.read_csv(f"{run}/vc/vc_inventory_weekly.csv")
    inv = inv[(inv["external"] == 0)]
    ci = inv[inv["product"] == "COS_Cream"].groupby("week_index")["lots"].sum()
    sh = pd.read_csv(f"{run}/shelf/shelf_life_summary.csv", dtype=str)
    star = sh[(sh["product"] == "*") & (sh["channel"] == "*")].iloc[0]
    shp = pd.read_csv(f"{run}/vc/vc_shipments.csv.gz", dtype=str)
    prod = shp[(shp["kind"] == "handoff_to_sp") & (shp["product"] == "COS_Cream")]
    pw = prod.groupby("ship_week")["lots"].apply(lambda x: x.astype(float).sum())
    cap = pd.read_csv(f"{model}/capacity_plan.csv", dtype=str)
    cs = cap[(cap["sku_id"] == "COS_Cream") & (cap["node_name"] == "Factory_JP")]
    soft = {w: int(float(c) * 0.97 + 1e-9) for w, c in zip(cs["week"], cs["cap_soft"])}
    at = sum(1 for w in soft if pw.get(w, 0) == soft[w])
    below = {w: int(soft[w] - pw.get(w, 0)) for w in soft if pw.get(w, 0) < soft[w]}
    ov[n] = {
        "cream_delivered": int(cream["on_time"].sum() + cream["early"].sum() + cream["late"].sum()),
        "cream_unmet_TH": g("COS_Cream", "TH_Distributor", "backlog_end"),
        "cream_unmet_SG": int(cream[cream["leaf"] != "TH_Distributor"]["backlog_end"].sum()),
        "serum_delivered": int(fl[fl["product"] == "COS_Serum"][["on_time", "early", "late"]].sum().sum()),
        "serum_unmet": int(fl[fl["product"] == "COS_Serum"]["backlog_end"].sum()),
        "P0_report": float(v[v["in_report"]]["profit_r2_hq_wk"].sum()),
        "cream_inv_lot_weeks": int(ci.sum()), "cream_inv_max": int(ci.max()), "cream_inv_end": int(ci.iloc[-1]),
        "age_max": int(star["fifo_age_max"]), "age_over52": int(star["over_max_age"]),
        "cream_production": int(pw.sum()), "cream_weeks_at_soft": at, "cream_weeks_below_soft": below,
        "cream_soft_shippable_per_week": sorted(set(soft.values())),
    }
out["overview"] = ov
os.makedirs(f"{O}/measure", exist_ok=True)
json.dump(out, open(f"{O}/measure/cmp2_measure.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out["B1_comparison_value"], ensure_ascii=False, indent=1))
print(json.dumps(out["O5_serum_vs_baseline"], ensure_ascii=False, indent=1))
for n, x in ov.items():
    print(n, {k: v for k, v in x.items() if k != "cream_weeks_below_soft"}, "below:", x["cream_weeks_below_soft"])
