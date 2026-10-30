# -*- coding: utf-8 -*-
"""P2-a evaluation amounts (RequestLetter_BSSEAF_Cosmetics_AllocationP2a §3.3).

    python output/bsseaf_cosmetics/p2a_work/evaluate.py      (from the repository root)

evaluation = sum over keys (4) lots x 24 x contribution margin per unit - common fixed-cost part
common fixed-cost part = store revenue x 45% + EC revenue x 10% of M0 (C3b copy), whole horizon;
computed once here from the M0 PPC results and compared with the letter (213,719,220).
Lost contribution by (3) and by (5) are shown separately. P1 from its Q01.json, C3b from the
M0 trial's Lot_ID records ((4) = demand Lot_IDs actually shipped).
Also: the Thai 30% tariff case (M4 sensitivity) -- the P2-a1 / P2-a2 rules with the Thai
contribution margin lowered by the tariff per unit, compared with the P1 allocation.
This is a comparison value for allocations, not an operating profit.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import make_allocation as MA   # noqa: E402

CPU = 24
FIXED_LETTER = 213719220.0
FORECAST = {"P2a1": (506522172, 314996928), "P2a2": (506499132, 314961828), "P1": (506447292, 314873376)}
THAI_TARIFF = {"COS_Serum": 1800.0, "COS_Cream": 1500.0}


def keys_from_q01(case):
    st = json.load(open(os.path.join(COS, "_planning_state", case, "Q01.json"), encoding="utf-8"))
    return {(k["sku_id"], k["region"]): {"q1": k["q1_original"], "q2": k["q2_in_supply_scope"],
                                         "q3": k["q3_not_in_supply_scope"], "q4": k["q4_delivered"]["total"],
                                         "q5": k["q5_backlog_end"]} for k in st["quantities"]["by_key"]}


def keys_from_m0():
    lots = json.load(open(os.path.join(COS, "money_m0_work", "M0_result", "lots.json"), encoding="utf-8"))
    out = {}
    for p, d in lots.items():
        for leaf, v in d.items():
            dem = set(v["demand"])
            shipped = {i for ids in v["ship"].values() for i in ids}
            q4 = len(dem & shipped)
            out[(p, leaf)] = {"q1": len(dem), "q2": len(dem), "q3": 0, "q4": q4, "q5": len(dem) - q4}
    return out


def evaluate(keys, fixed):
    e = {"by_key": [], "by_sku": {}}
    for (s, r), q in sorted(keys.items()):
        cm = MA.CM[(s, r)]
        e["by_key"].append({"sku_id": s, "region": r, **q, "cm": cm,
                            "contribution_q4": q["q4"] * CPU * cm, "contribution_q2": q["q2"] * CPU * cm,
                            "lost_q3": q["q3"] * CPU * cm, "lost_q5": q["q5"] * CPU * cm})
    for s in MA.SKUS:
        rows = [x for x in e["by_key"] if x["sku_id"] == s]
        e["by_sku"][s] = {k: sum(x[k] for x in rows) for k in
                          ("q1", "q2", "q3", "q4", "q5", "contribution_q4", "contribution_q2", "lost_q3", "lost_q5")}
    tot = {k: sum(v[k] for v in e["by_sku"].values()) for k in e["by_sku"]["COS_Serum"]}
    e["total"] = tot
    e["fixed_part"] = fixed
    e["evaluation"] = tot["contribution_q4"] - fixed
    return e


def main():
    p = json.load(open(os.path.join(COS, "money_m0_work", "checks_ppc.json"), encoding="utf-8"))
    rev = {(r["product_id"], r["channel"]): r["total_revenue"] for r in p["M0"]["sku_channel"]}
    fixed = sum(rev[(s, "SG_Store")] * 0.45 + rev[(s, "SG_EC")] * 0.10 for s in MA.SKUS)
    res = {"fixed_part_from_M0": fixed, "fixed_part_letter": FIXED_LETTER,
           "fixed_part_same": abs(fixed - FIXED_LETTER) < 0.01}
    cases = {"P2a1": keys_from_q01("P2a1"), "P2a2": keys_from_q01("P2a2"), "P1": keys_from_q01("P1"),
             "C3b": keys_from_m0()}
    for c, k in cases.items():
        res[c] = evaluate(k, FIXED_LETTER)
    base = res["P2a1"]["evaluation"]
    res["diff_vs_P2a1"] = {c: res[c]["evaluation"] - base for c in cases}
    res["forecast_check"] = {c: {"serum_q2_forecast": f[0], "serum_q2": res[c]["by_sku"]["COS_Serum"]["contribution_q2"],
                                 "cream_q2_forecast": f[1], "cream_q2": res[c]["by_sku"]["COS_Cream"]["contribution_q2"],
                                 "same": abs(res[c]["by_sku"]["COS_Serum"]["contribution_q2"] - f[0]) < 0.01
                                 and abs(res[c]["by_sku"]["COS_Cream"]["contribution_q2"] - f[1]) < 0.01}
                             for c, f in FORECAST.items()}
    # Thai 30% tariff: the same rules with the Thai margin lowered
    saved = dict(MA.CM)
    try:
        for s in MA.SKUS:
            MA.CM[(s, "TH_Distributor")] = saved[(s, "TH_Distributor")] - THAI_TARIFF[s]
        dem = MA.demand(os.path.join(COS, "C3a"))
        a1 = MA.p2a1(dem)
        a2, g2 = MA.p2a2(dem)
        p1 = {}
        with open(os.path.join(COS, "P1", "allocation_qty_P1.csv"), encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                p1[(r["sku_id"], r["region"])] = int(r["alloc_lots"])
        res["thai30"] = {"cm_thai": {s: MA.CM[(s, "TH_Distributor")] for s in MA.SKUS},
                         "order": {s: MA.order(s, dem) for s in MA.SKUS}, "groups_p2a2": g2,
                         "p2a1_equals_P1": a1 == p1, "p2a2_equals_P1": a2 == p1,
                         "p2a1": {f"{k[0]}|{k[1]}": v for k, v in sorted(a1.items())}}
    finally:
        MA.CM.clear()
        MA.CM.update(saved)
    json.dump(res, open(os.path.join(HERE, "evaluation.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("fixed part", fixed, res["fixed_part_same"])
    for c in cases:
        t = res[c]["total"]
        print(f"{c:<5} q4 {t['q4']:>5} contribution {t['contribution_q4']:>16,.0f} eval {res[c]['evaluation']:>16,.0f}"
              f" diff {res['diff_vs_P2a1'][c]:>12,.0f}  lost q3 {t['lost_q3']:>12,.0f} q5 {t['lost_q5']:>10,.0f}")
    print("forecast", {c: v["same"] for c, v in res["forecast_check"].items()})
    print("thai30", res["thai30"]["cm_thai"], res["thai30"]["order"], "p2a1==P1", res["thai30"]["p2a1_equals_P1"],
          "p2a2==P1", res["thai30"]["p2a2_equals_P1"], res["thai30"]["groups_p2a2"])


if __name__ == "__main__":
    main()
