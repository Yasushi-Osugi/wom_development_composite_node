# -*- coding: utf-8 -*-
"""Minimum supply trial: B2 and the reference (before the trial), then MS_base, MS50, MS70.

    python output/bsseaf_cosmetics/ms_work/run_trial.py     (from the repository root)
"""
import csv
import json
import os
import shutil
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.getcwd())
import wom.allocation.upper_demand_plan as U                     # noqa: E402

COS = "output/bsseaf_cosmetics"
W = COS + "/ms_work"
BASE = "data/sample/cosmetics-sg-th-2027-2029"
AF = "docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix/records/allocation_qty_P2a2.csv"
CAP = {"COS_Serum": (17, 14), "COS_Cream": (13, 11)}
NOTE = "当該期間は供給の対象にしない予測需要（仮定、化粧品設計書 v0.5 D18）"
DEC = "requests/BSSEAF_Cosmetics_DemandPlan_Horizon_Priority_v0.1.md §5"
RULE = "trim_to_capacity_latest"
KEYS = [(s, r) for s in ("COS_Serum", "COS_Cream") for r in ("SG_Distributor", "TH_Distributor")]
CASES = {"MS_base": None, "MS50": "0.5", "MS70": "0.7"}
COLS = ["policy_id", "policy_version", "sku_id", "region", "min_supply_ratio", "min_supply_rounding", "min_supply_kind", "reason"]


def copy_c3a(d):
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(BASE, d, ignore=shutil.ignore_patterns("README.md"))
    p = d + "/capacity_plan.csv"
    cr = list(csv.DictReader(open(p, encoding="utf-8", newline="")))
    fields = list(cr[0])
    for r in cr:
        r["max_supply"], r["cap_soft"] = CAP[r["sku_id"]]
    with open(p, "w", encoding="utf-8", newline="") as f:
        cw = csv.DictWriter(f, fields, lineterminator="\n")
        cw.writeheader()
        cw.writerows(cr)


os.makedirs(W + "/policy", exist_ok=True)
pre = {"refs_before": {}, "B2": {}}
json.dump([{"id": "WOM-SEM-SUPPLY-ALLOCATION-001", "version": "v0.5",
            "applicability": "①〜⑤、U4（化粧品：能力対応案。今回の 3 つの期間では鍵ごとの減らし始める週が同じ）"},
           {"id": "WOM-DESIGN-UPPER-DEMAND-PLAN-001", "version": "0.3",
            "applicability": "§2.2 udp_policy.csv、§3.1 trim_to_capacity_latest、§4 診断"},
           {"id": "次の段階の判断資料", "version": "v0.4", "applicability": "第 2 部（P-1〜P-6 決定）"}],
          open(W + "/knowledge.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for name, ratio in CASES.items():
    d = f"{COS}/{name}"
    shutil.rmtree(f"{COS}/_planning_state/{name}", ignore_errors=True)
    copy_c3a(d)
    pf = None
    if ratio:
        pf = f"{W}/policy/udp_policy_{name}.csv"
        with open(pf, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(COLS)
            for s, r in KEYS:
                w.writerow([name, "1", s, r, ratio, "ceil", "required", "代理店への最低供給量（大杉さん P-2、2026-11-03）"])
    led = U.build_demand_ledger(d)
    if pf:
        pol = U.read_policy(pf, led)
        by = {}
        for s, r in KEYS:
            rows = [x for x in led if x["sku_id"] == s and x["region"] == r and x["q1"]]
            mins = Counter((x["q1"], U.min_supply_lots(x["q1"], pol["keys"][(s, r)])) for x in rows)
            quota = next(int(q["alloc_lots"]) for q in csv.DictReader(open(AF, encoding="utf-8-sig")) if q["sku_id"] == s and q["region"] == r)
            by[f"{s}|{r}"] = {"weeks_by_q1_min": {f"{a}->{b}": n for (a, b), n in sorted(mins.items())},
                              "q1": sum(x["q1"] for x in rows), "min_total": sum(a * 0 + b * n for (a, b), n in mins.items()),
                              "quota": quota, "max_cut_steady": max(mins)[0] - max(mins)[1]}
        pre["B2"][name] = by
        conflicts = U.min_supply_conflicts(led, AF, pol)
        pre.setdefault("conflicts_before", {})[name] = conflicts
        sel = U.select_mode1_capacity(led, AF, d, policy_file=pf, reference_only=True)
    else:
        sel = U.select_mode1_capacity(led, AF, d)
    pre["refs_before"][name] = {r["sku_id"]: r["ontime_short_ref"] for r in U.time_phased_check(d, sel, True, True)}
    if ratio == "0.7":
        pre["refs_before"][name]["注"] = "クリームは衝突の鍵（タイ）を除いた参考の台帳の値"
    cmd = [sys.executable, "-m", "tools.run_quantity_allocation", "--model-dir", d, "--allocation-file", AF, "--week-rule", RULE,
           "--udp-out", COS + "/udp", "--knowledge-file", W + "/knowledge.json", "--decision-ref", DEC,
           "--out-dir", COS + "/_planning_state", "--unallocated-note", NOTE]
    r = subprocess.run(cmd + (["--policy-file", pf] if pf else []), capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(name, "rc", r.returncode)
    print(r.stdout[-1300:], r.stderr[-500:])
    pre.setdefault("rc", {})[name] = r.returncode
    if os.path.exists(f"{d}/demand_forecast_Q01.csv"):
        s = subprocess.run([sys.executable, "-m", "tools.shelf_life_check", "--model-dir", d, "--max-age-weeks", "52",
                            "--demand-file", "demand_forecast_Q01.csv", "--warmup-real-start", "2027-W01",
                            "--out", f"{W}/shelf/{name}"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("\n".join(l for l in s.stdout.splitlines() if l.startswith("[shelf_life]") or l.startswith("*")))
json.dump(pre, open(W + "/pre.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(pre, ensure_ascii=False, indent=0)[:3500])
