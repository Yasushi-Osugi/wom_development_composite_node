# -*- coding: utf-8 -*-
"""Thai cream minimum 70% trial (plan §6, T0-T2): copies, inputs, MS50 reproduction, TH70.

    python output/bsseaf_cosmetics_th70/work/th70_trial.py T0|T1|T2     (from the repository root)

Only copies under output/ are written. The sample, code, golden and protected core are not changed.
Based on docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/scripts/run_trial.py.
"""
import csv
import filecmp
import hashlib
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.getcwd())
import wom.allocation.upper_demand_plan as U                     # noqa: E402

OUT = "output/bsseaf_cosmetics_th70"
W = OUT + "/work"
BASE = "data/sample/cosmetics-sg-th-2027-2029"
MSA = "docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix"
AF_BASE = "docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix/records/allocation_qty_P2a2.csv"
POL_BASE = MSA + "/policy/udp_policy_MS50.csv"
CAP = {"COS_Serum": (17, 14), "COS_Cream": (13, 11)}             # C3a (docs/scenarios/cosmetics.md)
NOTE = "当該期間は供給の対象にしない予測需要（仮定、化粧品設計書 v0.5 D18）"
RULE = "trim_to_capacity_latest"
PLAN = "requests/Plan_BSSEAF_Cosmetics_ThaiCream_Minimum70_NewAgent_v0.1.md"
DEC_MS50 = "requests/BSSEAF_Cosmetics_DemandPlan_Horizon_Priority_v0.1.md §5"
DEC_H1 = PLAN + " §7 H1（タイのクリームは全量を守る、大杉さん 2026-11-06）"
DEC_H2 = PLAN + " §7 H2（試行 T0〜T3 は同じ担当が写しで行う、大杉さん 2026-11-06）"
UDP_FILES = ["udp_selection_ledger.csv", "udp_result_by_request.csv", "udp_min_supply_check.csv",
             "udp_capacity_check.csv", "udp_supply_runs.csv"]
TH_NEW, SG_NEW = 299, 666
TAG = "P2-a2 から TH 最低 7 割のために 25 lot を TH へ（試行 TH70）"


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


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


def t0():
    os.makedirs(W, exist_ok=True)
    for name in ("MS50", "TH70"):
        copy_c3a(f"{OUT}/{name}")
    # quota: copy U4 P2-a2, change the two cream distributor rows
    rows = list(csv.reader(open(AF_BASE, encoding="utf-8-sig", newline="")))
    with open(W + "/allocation_qty_TH70.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        for r in rows:
            if r[:2] == ["COS_Cream", "SG_Distributor"]:
                r = [r[0], r[1], str(SG_NEW), TAG]
            elif r[:2] == ["COS_Cream", "TH_Distributor"]:
                r = [r[0], r[1], str(TH_NEW), TAG]
            w.writerow(r)
    # policy: copy MS50, policy_id MS50TH70, TH cream 0.7
    rows = list(csv.reader(open(POL_BASE, encoding="utf-8-sig", newline="")))
    with open(W + "/udp_policy_MS50TH70.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(rows[0])
        for r in rows[1:]:
            r = list(r)
            r[0] = "MS50TH70"
            if r[2:4] == ["COS_Cream", "TH_Distributor"]:
                r[4] = "0.7"
                r[7] = "タイのクリームの最低供給量 7 割（依頼書 BSSEAF-COS-LOOP4、作業計画 H1）"
            else:
                r[7] = "代理店への最低供給量（MS50 のまま）"
            w.writerow(r)
    kn = [{"id": "WOM-SEM-SUPPLY-ALLOCATION-001", "version": "0.6",
           "applicability": "①〜⑤（§3）、最低供給量の二段階の確認と衝突（§6.1）"},
          {"id": "WOM-DESIGN-UPPER-DEMAND-PLAN-001", "version": "0.3",
           "applicability": "§3.1 trim_to_capacity_latest、§3.2 最低供給量、§4 診断（参考値）"},
          {"id": "WOM-KB-BSSEAF-001", "version": "v0.5", "applicability": "8 段階（段階 4 の試行）、一巡の記録"},
          {"id": "作業計画 TH70", "version": "v0.1", "applicability": PLAN + " §5・§6"}]
    json.dump(kn, open(W + "/knowledge.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    hashes = {p: sha(p) for p in (AF_BASE, POL_BASE, W + "/allocation_qty_TH70.csv", W + "/udp_policy_MS50TH70.csv",
                                  W + "/knowledge.json", BASE + "/demand_forecast.csv")}
    for name in ("MS50", "TH70"):
        hashes[f"{name}/capacity_plan.csv"] = sha(f"{OUT}/{name}/capacity_plan.csv")
    json.dump(hashes, open(W + "/t0_hashes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(hashes, indent=1))


def run(name, af, pf, decs):
    d = f"{OUT}/{name}"
    shutil.rmtree(f"{OUT}/_planning_state/{name}", ignore_errors=True)
    shutil.rmtree(f"{OUT}/udp/{name}_{RULE}", ignore_errors=True)
    led = U.build_demand_ledger(d)
    pol = U.read_policy(pf, led)
    pre = {"conflicts_before": U.min_supply_conflicts(led, af, pol)}
    sel = U.select_mode1_capacity(led, af, d, policy_file=pf, reference_only=True)
    pre["refs_before"] = {r["sku_id"]: r["ontime_short_ref"] for r in U.time_phased_check(d, sel, True, True)}
    cmd = [sys.executable, "-m", "tools.run_quantity_allocation", "--model-dir", d, "--allocation-file", af,
           "--week-rule", RULE, "--policy-file", pf, "--udp-out", OUT + "/udp", "--knowledge-file", W + "/knowledge.json",
           "--out-dir", OUT + "/_planning_state", "--unallocated-note", NOTE]
    for x in decs:
        cmd += ["--decision-ref", x]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    pre["rc"] = r.returncode
    pre["cmd"] = cmd
    open(f"{W}/{name}_stdout.txt", "w", encoding="utf-8").write(r.stdout + "\n--- stderr ---\n" + r.stderr)
    print(name, "rc", r.returncode)
    print(r.stdout[-2500:], r.stderr[-1500:])
    if os.path.exists(f"{d}/demand_forecast_Q01.csv"):
        s = subprocess.run([sys.executable, "-m", "tools.shelf_life_check", "--model-dir", d, "--max-age-weeks", "52",
                            "--demand-file", "demand_forecast_Q01.csv", "--warmup-real-start", "2027-W01",
                            "--out", f"{OUT}/shelf/{name}"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        pre["shelf_rc"] = s.returncode
        open(f"{W}/{name}_shelf_stdout.txt", "w", encoding="utf-8").write(s.stdout + "\n--- stderr ---\n" + s.stderr)
        print("\n".join(l for l in s.stdout.splitlines() if l.startswith("[shelf_life]") or l.startswith("*")))
    json.dump(pre, open(f"{W}/{name}_pre.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: v for k, v in pre.items() if k != "cmd"}, ensure_ascii=False, default=str)[:1500])
    return pre


def t1():
    pre = run("MS50", AF_BASE, POL_BASE, [DEC_MS50, DEC_H2])
    u = f"{OUT}/udp/MS50_{RULE}"
    cmp = {f: filecmp.cmp(f"{MSA}/udp/MS50/{f}", f"{u}/{f}", shallow=False) for f in UDP_FILES}
    old = json.load(open(f"{MSA}/udp/MS50/udp_plan.json", encoding="utf-8"))
    new = json.load(open(f"{u}/udp_plan.json", encoding="utf-8"))
    cmp["output_hashes_same"] = old["output_hashes"] == new["output_hashes"]
    cmp["input_hashes_same"] = old["input_hashes"] == new["input_hashes"]
    cmp["plan_keys_differ"] = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
    cmp["totals"] = new["totals"]
    cmp["rc"] = pre["rc"]
    json.dump(cmp, open(W + "/t1_compare.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(cmp, ensure_ascii=False, indent=1))
    ok = all(cmp[f] for f in UDP_FILES) and cmp["output_hashes_same"] and pre["rc"] == 0
    print("T1", "MATCH" if ok else "MISMATCH")
    sys.exit(0 if ok else 9)


def t2():
    run("TH70", W + "/allocation_qty_TH70.csv", W + "/udp_policy_MS50TH70.csv", [DEC_H1, DEC_H2])


if __name__ == "__main__":
    {"T0": t0, "T1": t1, "T2": t2}[sys.argv[1]]()
