# -*- coding: utf-8 -*-
"""Horizon test, before the trial: B1 (usable weeks from inputs only), the 4 copies (Data only),
B2, B3, the quotas, and the time-phased reference (S4). Stops with exit 1 if B1 fails.

    python output/bsseaf_cosmetics/hz_work/build.py     (from the repository root)
"""
import csv
import json
import os
import shutil
import sys

sys.path[:0] = [os.getcwd(), "output/bsseaf_cosmetics/p2a_work"]
import make_allocation as MA                                     # noqa: E402
import wom.allocation.upper_demand_plan as U                     # noqa: E402
from wom.engine.plan_period import detect_plan_period             # noqa: E402
from wom.engine.warmup import materialize_warmup, read_planning_config  # noqa: E402

COS = "output/bsseaf_cosmetics"
W = COS + "/hz_work"
BASE = "data/sample/cosmetics-sg-th-2027-2029"
AF_P2A2 = "docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix/records/allocation_qty_P2a2.csv"
SKUS = ("COS_Serum", "COS_Cream")
CAP = {"COS_Serum": (17, 14), "COS_Cream": (13, 11)}
STEADY = {"COS_Serum": {"SG_Store": 4, "SG_EC": 3, "SG_Distributor": 6, "TH_Distributor": 4},
          "COS_Cream": {"SG_Store": 3, "SG_EC": 2, "SG_Distributor": 5, "TH_Distributor": 3}}
HAND = {"E13": {"COS_Serum": 156, "COS_Cream": 127}, "E26": {"COS_Serum": 208, "COS_Cream": 166}}
EXT = {"E13": 13, "E26": 26}
RULES = {"A0e": "proportional_even", "A3": "trim_to_capacity_latest"}


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig", newline="")))


def usable_weeks(md):
    """Inputs only (demand_forecast, capacity_plan, sc_tree_master): no planning result is read.
    first = plan start + the raw-material LT (leaf_in lt_wks). last = last demand week - the shortest
    factory-to-market lead (lt_wks along the tree, without ss_days). good cap = int(cap_soft x yield)."""
    weeks = sorted({r["week"] for r in rd(md + "/demand_forecast.csv")}, key=U._week_key)
    res = U._sku_resources(md, list(SKUS), weeks)
    tree = rd(md + "/sc_tree_master.csv")
    out = {}
    for s in SKUS:
        raw = max(int(float(r["lt_wks"] or 0)) for r in tree if r["product_name"] == s and r["node_type"] == "leaf_in")
        lead = min(res[s]["lead"].values())
        a, b = raw, len(weeks) - 1 - lead
        cap = res[s]["cap"]
        out[s] = {"plan_start": weeks[0], "plan_end": weeks[-1], "plan_weeks": len(weeks), "raw_lt": raw,
                  "leads": res[s]["lead"], "lead_used": lead, "first_week": weeks[a], "last_week": weeks[b],
                  "usable_weeks": b - a + 1, "excluded_head": weeks[:a], "excluded_tail": weeks[b + 1:],
                  "good_cap_values": sorted(set(cap[a:b + 1])), "supply_total": sum(cap[a:b + 1])}
    return out


def c3a_copy(d):
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(BASE, d, ignore=shutil.ignore_patterns("README.md"))
    p = d + "/capacity_plan.csv"
    cr = rd(p)
    fields = list(cr[0])
    for r in cr:
        r["max_supply"], r["cap_soft"] = CAP[r["sku_id"]]
    with open(p, "w", encoding="utf-8", newline="") as f:
        cw = csv.DictWriter(f, fields, lineterminator="\n")
        cw.writeheader()
        cw.writerows(cr)


def extend(d, n):
    weeks = [f"2030-W{i:02d}" for i in range(1, n + 1)]
    with open(d + "/demand_forecast.csv", "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        for s in sorted(STEADY):
            for reg in sorted(STEADY[s]):
                for wk in weeks:
                    w.writerow([s, reg, wk, STEADY[s][reg]])
    with open(d + "/capacity_plan.csv", "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        for s in sorted(CAP):
            for wk in weeks:
                w.writerow([s, "Factory_JP", wk, CAP[s][0], CAP[s][1], "plan"])


res = {}
c3a = COS + "/C3a"
# steady-week check of the letter's numbers against the sample
d0 = rd(BASE + "/demand_forecast.csv")
res["steady_check"] = {f"{r['sku_id']}|{r['region']}": [int(float(r["quantity"])), STEADY[r["sku_id"]][r["region"]]]
                       for r in d0 if r["week"] == "2029-W52"}
assert all(a == b for a, b in res["steady_check"].values())

# B1
b1 = usable_weeks(c3a)
res["B1"] = b1
res["B1_ok"] = b1["COS_Serum"]["supply_total"] == 2184 and b1["COS_Cream"]["supply_total"] == 1680
if not res["B1_ok"]:
    json.dump(res, open(W + "/pre.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("STOP: B1 not reproduced", b1)
    sys.exit(1)

# the quota rule on E0 must reproduce P2-a2
MA.SUPPLY = {s: b1[s]["supply_total"] for s in SKUS}
a0, g0 = MA.p2a2(MA.demand(c3a))
p2 = {(r["sku_id"], r["region"]): int(r["alloc_lots"]) for r in rd(AF_P2A2)}
res["E0_quota_same_as_P2a2"] = a0 == p2
assert res["E0_quota_same_as_P2a2"]

os.makedirs(W + "/quota", exist_ok=True)
res["copies"], res["quota"], res["refs_before"], res["rule_detail_before"] = {}, {}, {}, {}
c3a_cap = open(c3a + "/capacity_plan.csv", "rb").read()
base_dem = open(BASE + "/demand_forecast.csv", "rb").read()
for e, n in EXT.items():
    first = None
    for a, rule in RULES.items():
        case = f"H_{e}_{a}"
        d = f"{COS}/{case}"
        shutil.rmtree(f"{COS}/_planning_state/{case}", ignore_errors=True)
        c3a_copy(d)
        extend(d, n)
        materialize_warmup(d)                 # same call as the tool: the file must stay as built
        dem_b, cap_b = open(d + "/demand_forecast.csv", "rb").read(), open(d + "/capacity_plan.csv", "rb").read()
        per = detect_plan_period(d + "/demand_forecast.csv")
        wl = sorted({r["week"] for r in rd(d + "/demand_forecast.csv")}, key=U._week_key)
        cw = sorted({r["week"] for r in rd(d + "/capacity_plan.csv")}, key=U._week_key)
        drow, crow = rd(d + "/demand_forecast.csv"), rd(d + "/capacity_plan.csv")
        res["copies"][case] = {
            "plan_start": per.start, "plan_end": per.weeks[-1], "weeks": per.n_weeks,
            "warmup_lt": read_planning_config(d)[0],
            "demand_prefix_same_as_sample": dem_b.startswith(base_dem),
            "capacity_prefix_same_as_C3a": cap_b.startswith(c3a_cap),
            "added_demand_rows": len(dem_b.splitlines()) - len(base_dem.splitlines()),
            "added_capacity_rows": len(cap_b.splitlines()) - len(c3a_cap.splitlines()),
            "weeks_same_demand_capacity": wl == cw,
            "rows_per_week_ok": all(sum(1 for r in drow if r["week"] == w) == 8 and sum(1 for r in crow if r["week"] == w) == 2 for w in wl),
            "holiday_rows": len(rd(d + "/holiday_calendar.csv"))}
        if first is None:
            first = usable_weeks(d)
            supply = {s: first[s]["supply_total"] for s in SKUS}
            MA.SUPPLY = supply
            dem = MA.demand(d)
            alloc, gs = MA.p2a2(dem)
            qf = f"{W}/quota/allocation_qty_{e}.csv"
            MA.write(qf, alloc)
            cut = {s: sum(v for k, v in dem.items() if k[0] == s) - supply[s] for s in SKUS}
            res["quota"][e] = {"usable": first, "supply": supply, "demand": {f"{k[0]}|{k[1]}": v for k, v in sorted(dem.items())},
                               "alloc": {f"{k[0]}|{k[1]}": v for k, v in sorted(alloc.items())}, "groups": gs,
                               "cut_by_sku": cut, "cut_hand": HAND[e], "same_as_hand": cut == HAND[e], "file": qf}
        qf = f"{W}/quota/allocation_qty_{e}.csv"
        led = U.build_demand_ledger(d)
        sel = U.select_mode1_capacity(led, qf, d) if a == "A3" else U.select_mode1(led, qf, rule)
        res["refs_before"][case] = {r["sku_id"]: r["ontime_short_ref"] for r in U.time_phased_check(d, sel, True, True)}
        if a == "A3":
            res["rule_detail_before"][case] = U.capacity_rule_detail(d, sel)
json.dump([{"id": "WOM-SEM-SUPPLY-ALLOCATION-001", "version": "v0.5", "applicability": "①〜⑤、U4（化粧品：A3）"},
           {"id": "WOM-DESIGN-UPPER-DEMAND-PLAN-001", "version": "0.3",
            "applicability": "モード 1、規則 proportional_even・trim_to_capacity_latest、§4 診断"},
           {"id": "次の段階の判断資料", "version": "v0.2", "applicability": "第 1 部（H-1〜H-3 決定）"}],
          open(W + "/knowledge.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(res, open(W + "/pre.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ("B1_ok", "E0_quota_same_as_P2a2", "copies", "refs_before", "rule_detail_before")}, ensure_ascii=False, indent=0))
for e in EXT:
    print(e, res["quota"][e]["supply"], res["quota"][e]["cut_by_sku"], res["quota"][e]["same_as_hand"], res["quota"][e]["alloc"])
print({s: {k: b1[s][k] for k in ("plan_start", "raw_lt", "lead_used", "first_week", "last_week", "usable_weeks", "good_cap_values", "excluded_head", "excluded_tail", "supply_total")} for s in SKUS})
