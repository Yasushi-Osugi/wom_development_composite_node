# -*- coding: utf-8 -*-
"""Stage 7 verify, V2: an independent route (not the trial's scripts).

    python output/bsseaf_cosmetics_th70_verify/v2/v2_run.py    (from the repository root)

- copies the sample and sets C3a capacity from docs/scenarios/cosmetics.md (own code)
- writes TH70 quota from the AllocationP2a appendix file (no quota_source column) + plan §5.1,
  and the policy from udp_policy_MS50.csv with only the TH cream ratio changed (own code)
- runs tools.run_quantity_allocation and tools.shelf_life_check directly (no knowledge / decision refs)
"""
import csv
import os
import shutil
import subprocess
import sys

PY = sys.executable
V = "output/bsseaf_cosmetics_th70_verify/v2"
BASE = "data/sample/cosmetics-sg-th-2027-2029"
Q_P2A2 = "docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/allocation/allocation_qty_P2a2.csv"
POL_MS50 = "docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/policy/udp_policy_MS50.csv"
C3A = {"COS_Serum": ("17", "14"), "COS_Cream": ("13", "11")}


def make_copy(d):
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(BASE, d)
    p = os.path.join(d, "capacity_plan.csv")
    with open(p, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    h = rows[0]
    im, ic, isk = h.index("max_supply"), h.index("cap_soft"), h.index("sku_id")
    for r in rows[1:]:
        r[im], r[ic] = C3A[r[isk]]
    with open(p, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def main():
    os.makedirs(V + "/in", exist_ok=True)
    for n in ("MS50", "TH70"):
        make_copy(f"{V}/{n}")
    # quota MS50 = P2a2 values ; TH70 = same but cream SG 666 / TH 299
    with open(Q_P2A2, encoding="utf-8-sig") as f:
        q = list(csv.reader(f))
    with open(V + "/in/allocation_qty_P2a2.csv", "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(q)
    new = {("COS_Cream", "SG_Distributor"): "666", ("COS_Cream", "TH_Distributor"): "299"}
    q2 = [q[0]] + [[r[0], r[1], new.get((r[0], r[1]), r[2])] for r in q[1:]]
    with open(V + "/in/allocation_qty_TH70.csv", "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(q2)
    with open(POL_MS50, encoding="utf-8-sig") as f:
        p = list(csv.reader(f))
    p2 = [p[0]]
    for r in p[1:]:
        r = list(r)
        r[0] = "MS50TH70"
        if (r[2], r[3]) == ("COS_Cream", "TH_Distributor"):
            r[4] = "0.7"
        p2.append(r)
    with open(V + "/in/udp_policy_MS50TH70.csv", "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(p2)

    cases = {"MS50": (V + "/in/allocation_qty_P2a2.csv", POL_MS50),
             "TH70": (V + "/in/allocation_qty_TH70.csv", V + "/in/udp_policy_MS50TH70.csv")}
    for n, (af, pf) in cases.items():
        shutil.rmtree(f"{V}/udp/{n}_trim_to_capacity_latest", ignore_errors=True)
        shutil.rmtree(f"{V}/_ps/{n}", ignore_errors=True)
        cmd = [PY, "-m", "tools.run_quantity_allocation", "--model-dir", f"{V}/{n}", "--allocation-file", af,
               "--week-rule", "trim_to_capacity_latest", "--policy-file", pf, "--udp-out", V + "/udp",
               "--out-dir", V + "/_ps"]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        open(f"{V}/{n}_stdout.txt", "w", encoding="utf-8").write(" ".join(cmd) + "\n" + r.stdout + "\n--- stderr ---\n" + r.stderr)
        print(n, "run_quantity_allocation rc", r.returncode)
        s = subprocess.run([PY, "-m", "tools.shelf_life_check", "--model-dir", f"{V}/{n}", "--max-age-weeks", "52",
                            "--demand-file", "demand_forecast_Q01.csv", "--warmup-real-start", "2027-W01",
                            "--out", f"{V}/shelf/{n}"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        open(f"{V}/{n}_shelf_stdout.txt", "w", encoding="utf-8").write(s.stdout + "\n--- stderr ---\n" + s.stderr)
        print(n, "shelf_life_check rc", s.returncode)


if __name__ == "__main__":
    main()
