# -*- coding: utf-8 -*-
"""Letter 4: the base A0e_r2 and A3, built the same way as U4 (C3a capacity, P2-a2 quota).

    python output/bsseaf_cosmetics/cap_work/run_trial.py     (from the repository root)
"""
import csv
import os
import shutil
import subprocess
import sys

COS = "output/bsseaf_cosmetics"
W = COS + "/cap_work"
BASE = "data/sample/cosmetics-sg-th-2027-2029"
CAP = {"COS_Serum": (17, 14), "COS_Cream": (13, 11)}
AF = "docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix/records/allocation_qty_P2a2.csv"
NOTE = "当該期間は供給の対象にしない予測需要（仮定、化粧品設計書 v0.5 D18）"
CASES = {"U4_A0e_r2": "proportional_even", "U4_A3": "trim_to_capacity_latest"}

for case, rule in CASES.items():
    d = f"{COS}/{case}"
    shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(f"{COS}/_planning_state/{case}", ignore_errors=True)
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
    same = open(p, "rb").read() == open(COS + "/C3a/capacity_plan.csv", "rb").read()
    r = subprocess.run([sys.executable, "-m", "tools.run_quantity_allocation", "--model-dir", d, "--allocation-file", AF,
                        "--week-rule", rule, "--udp-out", COS + "/udp", "--out-dir", COS + "/_planning_state",
                        "--unallocated-note", NOTE], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(case, rule, "rc", r.returncode, "capacity_same_as_C3a", same)
    print(r.stdout[-1000:], r.stderr[-400:])
    s = subprocess.run([sys.executable, "-m", "tools.shelf_life_check", "--model-dir", d, "--max-age-weeks", "52",
                        "--demand-file", "demand_forecast_Q01.csv", "--warmup-real-start", "2027-W01",
                        "--out", f"{W}/shelf/{case}"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("\n".join(l for l in s.stdout.splitlines() if l.startswith("[shelf_life]") or l.startswith("*")))
