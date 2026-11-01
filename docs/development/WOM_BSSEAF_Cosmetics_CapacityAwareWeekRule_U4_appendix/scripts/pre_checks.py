# -*- coding: utf-8 -*-
"""Letter 2 B1, B2 and the A3 reference BEFORE the trial (S5). Reads only; writes pre_checks.json.

    python output/bsseaf_cosmetics/cap_work/pre_checks.py     (from the repository root)
"""
import csv
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.getcwd())
import wom.allocation.upper_demand_plan as U                     # noqa: E402

COS = "output/bsseaf_cosmetics"
W = COS + "/cap_work"
AP = "docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix"
MD = COS + "/U4_A0"                  # C3a capacity, the sample demand
QUOTA = AP + "/records/allocation_qty_P2a2.csv"
RULE = {"U4_A0": "proportional_early_tie", "U4_A0e": "proportional_even", "U4_A1": "earliest_first"}


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def load_sel(case):
    out = []
    for r in rd(f"{AP}/udp/{case}/udp_selection_ledger.csv"):
        sku, reg, wk = r["source_demand_ref"].split("|")
        out.append({"sku_id": sku, "region": reg, "request_week": wk, "q1": int(r["q1"]), "q2": int(r["q2"]),
                    "q3": int(r["q3"]), "reason_code": r["reason_code"]})
    return out


def refs(sel, *flags):
    return {r["sku_id"]: r["ontime_short_ref"] for r in U.time_phased_check(MD, sel, *flags)}


res = {"B1": {}}
for case in RULE:
    sel = load_sel(case)
    q5 = Counter()
    for r in rd(f"{AP}/udp/{case}/udp_result_by_request.csv"):
        q5[r["source_demand_ref"].split("|")[0]] += int(r["q5"])
    plain, both = refs(sel), refs(sel, True, True)
    res["B1"][case] = {"default": plain, "with_conditions": both, "q5": dict(q5),
                       "match": all(both[s] == q5[s] for s in both)}
res["B1_all_match"] = all(v["match"] for v in res["B1"].values())

weeks = sorted({r["request_week"] for r in load_sel("U4_A0")}, key=U._week_key)
base = U._sku_resources(MD, ["COS_Serum", "COS_Cream"], weeks)
ss = U._sku_resources(MD, ["COS_Serum", "COS_Cream"], weeks, ss_lead=True)
res["B2"] = {s: {"lead": base[s]["lead"], "lead_with_ss": ss[s]["lead"]} for s in base}

led = U.build_demand_ledger("data/sample/cosmetics-sg-th-2027-2029")
sel = U.select_mode1_capacity(led, QUOTA, MD)
res["A3_before_trial"] = U.capacity_rule_detail(MD, sel)
res["A3_before_trial"]["refs_default"] = refs(sel)
base_sel = load_sel("U4_A0e")
res["A0e_refs"] = {"default": refs(base_sel), "with_conditions": refs(base_sel, True, True)}
cut = {}
for x in sel:
    if x["q3"]:
        c = cut.setdefault(f"{x['sku_id']}|{x['region']}", {"lots": 0, "weeks": [], "max": 0})
        c["lots"] += x["q3"]
        c["weeks"].append(x["request_week"])
        c["max"] = max(c["max"], x["q3"])
res["A3_cut"] = {k: {"lots": v["lots"], "from": v["weeks"][0], "to": v["weeks"][-1], "weeks": len(v["weeks"]),
                     "max_per_week": v["max"]} for k, v in cut.items()}
res["A3_ledger_totals"] = {f: sum(x[f] for x in sel) for f in ("q1", "q2", "q3")}
res["A3_policy_ref"] = sel[0]["policy_ref"]
json.dump(res, open(W + "/pre_checks.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=0))
