# -*- coding: utf-8 -*-
"""Walk the reproduction steps of docs/scenarios/cosmetics.md once, from data/sample only."""
import csv, filecmp, json, os, shutil, subprocess, sys
sys.path.insert(0, os.getcwd())
import tools.run_headless_from_folder as rh
BASE = "data/sample/cosmetics-sg-th-2027-2029"
W = "output/bsseaf_cosmetics/register_work"
R = W + "/repro"
OLD = "output/bsseaf_cosmetics"
PY = sys.executable
CAP = {"COS_Serum": (17, 14), "COS_Cream": (13, 11)}   # C3a values, as written in the scenario document
P1 = """sku_id,region,alloc_lots
COS_Cream,SG_Distributor,754
COS_Cream,SG_EC,299
COS_Cream,SG_Store,416
COS_Cream,TH_Distributor,211
COS_Serum,SG_Distributor,897
COS_Serum,SG_EC,455
COS_Serum,SG_Store,546
COS_Serum,TH_Distributor,286
"""
AP = "docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/allocation"
shutil.rmtree(R, ignore_errors=True); os.makedirs(R)


def copy(name):
    d = os.path.join(R, name)
    shutil.copytree(BASE, d, ignore=shutil.ignore_patterns("README.md"))
    return d


def to_c3a(d):
    p = os.path.join(d, "capacity_plan.csv")
    rows = list(csv.DictReader(open(p, encoding="utf-8", newline="")))
    fields = list(rows[0])
    for r in rows:
        r["max_supply"], r["cap_soft"] = CAP[r["sku_id"]]
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n"); w.writeheader(); w.writerows(rows)


out = {}
# C3a
d = copy("C3a"); to_c3a(d)
out["C3a_capacity_same_as_trial"] = filecmp.cmp(d + "/capacity_plan.csv", OLD + "/C3a/capacity_plan.csv", shallow=False)
s = rh.run(d, output_ppc_dir=d + "_ppc", verbose=False, flow_check_dir=d + "_fc")
m = list(csv.DictReader(open(d + "_fc/flow_check_market.csv", encoding="utf-8-sig")))
out["C3a"] = {"q5_rows": {f"{r['product']}|{r['leaf']}": int(r["backlog_end"]) for r in m if int(r["backlog_end"] or 0)},
              "revenue": s["ppc"]["revenue_base"], "profit": s["ppc"]["gross_profit_base"]}
for f in ("flow_check_market.csv", "flow_check_nodes.csv"):
    out["C3a"][f + "_same_as_M0a"] = filecmp.cmp(d + "_fc/" + f, OLD + "/money_m0_work/M0a_result/flow_check/" + f, shallow=False)
# M0t
d = copy("M0t")
p = d + "/ppc_tariff_rule.csv"
t = open(p, encoding="utf-8", newline="").read()
rows = list(csv.DictReader(t.splitlines()))
print(rows[0].keys())
n = 0
with open(p, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, list(rows[0]), lineterminator="\n"); w.writeheader()
    for r in rows:
        if r["edge_id"] == "WH_JP_Released->DC_TH":
            r["tariff_rate"] = "0.30"; n += 1
        w.writerow(r)
s = rh.run(d, output_ppc_dir=d + "_ppc", verbose=False)
out["M0t"] = {"rows_changed": n, "profit": s["ppc"]["gross_profit_base"], "tariff": s["ppc"]["tariff_base"],
              "ledger_same": filecmp.cmp(d + "_ppc/ppc_event_ledger.csv", OLD + "/money_m0_work/M0t_result/ppc/ppc_event_ledger.csv", shallow=False)
              if os.path.exists(OLD + "/money_m0_work/M0t_result/ppc/ppc_event_ledger.csv") else None}
# allocations
for name, src in [("P1", None), ("P2a1", AP + "/allocation_qty_P2a1.csv"), ("P2a2", AP + "/allocation_qty_P2a2.csv")]:
    d = copy(name); to_c3a(d)
    af = os.path.join(R, f"allocation_qty_{name}.csv")
    if src: shutil.copyfile(src, af)
    else: open(af, "w", encoding="utf-8", newline="").write(P1)
    r = subprocess.run([PY, "-m", "tools.run_quantity_allocation", "--model-dir", d, "--allocation-file", af,
                        "--out-dir", R + "/_state", "--unallocated-note",
                        "当該期間は供給の対象にしない予測需要（仮定、化粧品設計書 v0.5 D18）"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    new = json.load(open(f"{R}/_state/{name}/Q01.json", encoding="utf-8"))
    old = json.load(open(f"{OLD}/_planning_state/{name}/Q01.json", encoding="utf-8"))
    fc = {}
    for f in os.listdir(f"{R}/_state/{name}/Q01_flow_check"):
        fc[f] = filecmp.cmp(f"{R}/_state/{name}/Q01_flow_check/{f}", f"{OLD}/_planning_state/{name}/Q01_flow_check/{f}", shallow=False)
    out[name] = {"rc": r.returncode, "flow_check_same": fc,
                 "keys_differ": [k for k in new if new.get(k) != old.get(k)]}
    print(name, r.returncode, r.stdout[-300:])
json.dump(out, open(W + "/repro_result.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
