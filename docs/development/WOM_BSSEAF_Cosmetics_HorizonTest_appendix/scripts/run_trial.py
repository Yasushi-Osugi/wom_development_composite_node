# -*- coding: utf-8 -*-
"""Horizon test: the 4 runs and the age summaries. Run build.py first.

    python output/bsseaf_cosmetics/hz_work/run_trial.py     (from the repository root)
"""
import subprocess
import sys

COS = "output/bsseaf_cosmetics"
W = COS + "/hz_work"
NOTE = "当該期間は供給の対象にしない予測需要（仮定、化粧品設計書 v0.5 D18）"
DEC = "requests/BSSEAF_Cosmetics_DemandPlan_Horizon_Priority_v0.1.md §5"
RULES = {"A0e": "proportional_even", "A3": "trim_to_capacity_latest"}
for e in ("E13", "E26"):
    for a, rule in RULES.items():
        case = f"H_{e}_{a}"
        d = f"{COS}/{case}"
        r = subprocess.run([sys.executable, "-m", "tools.run_quantity_allocation", "--model-dir", d,
                            "--allocation-file", f"{W}/quota/allocation_qty_{e}.csv", "--week-rule", rule,
                            "--udp-out", COS + "/udp", "--knowledge-file", W + "/knowledge.json", "--decision-ref", DEC,
                            "--out-dir", COS + "/_planning_state", "--unallocated-note", NOTE],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(case, rule, "rc", r.returncode)
        print(r.stdout[-1300:], r.stderr[-500:])
        s = subprocess.run([sys.executable, "-m", "tools.shelf_life_check", "--model-dir", d, "--max-age-weeks", "52",
                            "--demand-file", "demand_forecast_Q01.csv", "--warmup-real-start", "2027-W01",
                            "--out", f"{W}/shelf/{case}"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("\n".join(l for l in s.stdout.splitlines() if l.startswith("[shelf_life]") or l.startswith("*")))
