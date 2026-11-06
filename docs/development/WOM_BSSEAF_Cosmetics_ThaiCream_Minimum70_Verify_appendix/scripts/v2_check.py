# -*- coding: utf-8 -*-
"""Stage 7 verify, V2 checks 3-8 with own aggregation over the V2 run outputs.

    python output/bsseaf_cosmetics_th70_verify/v2/v2_check.py   (from the repository root)
"""
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.getcwd())
from tools.run_headless_from_folder import run              # noqa: E402
from wom.engine.plugin_base import WOMPlugin                 # noqa: E402
from wom.model.plan_node import I, P                         # noqa: E402

V = "output/bsseaf_cosmetics_th70_verify/v2"
CASES = ("MS50", "TH70")
POL = {"MS50": "docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/policy/udp_policy_MS50.csv",
       "TH70": V + "/in/udp_policy_MS50TH70.csv"}
CM_FILE = "docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/scripts/make_allocation.py"


def rd(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def wk(label):
    y, w = label.split("-W")
    return int(y), int(w)


def rows_of(n):
    u = f"{V}/udp/{n}_trim_to_capacity_latest"
    res = {r["source_demand_ref"]: r for r in rd(u + "/udp_result_by_request.csv")}
    out = {}
    for x in rd(u + "/udp_selection_ledger.csv"):
        k = x["source_demand_ref"]
        r = res[k]
        out[tuple(k.split("|"))] = {c: int(x[c]) for c in ("q1", "q2", "q3")} | {c: int(r[c]) for c in ("on_time", "early", "late", "q5")}
    assert set(res) == {"|".join(k) for k in out}
    return out


class Capture(WOMPlugin):
    name = "v2_capture"
    label = "v2 capture"

    def on_post_plan(self, sc_tree, weeks, config, **kw):
        self.tree = sc_tree


def tree_of(n):
    c = Capture()
    run(f"{V}/{n}", verbose=False, demand_file="demand_forecast_Q01.csv", ppc=False,
        warmup_real_start="2027-W01", extra_plugins=[c], output_ppc_dir=f"{V}/_noppc/{n}")
    t = c.tree
    wl = list(t.week_labels)
    fac, sp = {}, {}
    for s in t.products:
        for node in t.iter_all_nodes(s):
            if node.node_type == "mom":
                fac[s] = [len(node.psi4supply[w][P]) for w in range(len(wl))]
            if node.node_type == "supply_point":
                sp[s] = [len(node.psi4supply[w][I]) for w in range(len(wl))]
    return wl, fac, sp


R = {n: rows_of(n) for n in CASES}
out = {}

# 3. identities and totals
for n in CASES:
    bad = [k for k, r in R[n].items() if r["q1"] != r["q2"] + r["q3"] or r["q2"] != r["on_time"] + r["early"] + r["late"] + r["q5"]]
    tot = {c: sum(r[c] for r in R[n].values()) for c in ("q1", "q2", "q3", "on_time", "early", "late", "q5")}
    out[f"3_{n}"] = {"rows": len(R[n]), "identity_violations": len(bad), "totals": tot}

# 4. TH cream full on time; minimum per key recomputed from the policy
for n in CASES:
    pol = {(r["sku_id"], r["region"]): float(r["min_supply_ratio"]) for r in rd(POL[n])}
    th = [r for k, r in R[n].items() if k[:2] == ("COS_Cream", "TH_Distributor") and r["q1"] > 0]
    below = {}
    for key, ratio in pol.items():
        v = [(k, r) for k, r in R[n].items() if k[:2] == key and r["q1"] > 0]
        mins = [(k, math.ceil(ratio * r["q1"] - 1e-9)) for k, r in v]
        below["|".join(key)] = {"ratio": ratio, "weeks": len(v),
                                "plan_below": sum(1 for (k, m), (_, r) in zip(mins, v) if r["q2"] < m),
                                "delivered_below": sum(1 for (k, m), (_, r) in zip(mins, v) if r["on_time"] < m),
                                "min_fill_pct": round(min(r["on_time"] / r["q1"] for _, r in v) * 100, 1)}
    out[f"4_{n}"] = {"TH_cream_weeks": len(th), "TH_cream_on_time_eq_q1": sum(1 for r in th if r["on_time"] == r["q1"]),
                     "TH_cream_q1": sum(r["q1"] for r in th), "keys": below}

# 5. changed keys and SG cream interval / early rate
changed = sorted({"|".join(k[:2]) for k in R["MS50"] if R["MS50"][k] != R["TH70"][k]})
out["5_changed_keys"] = changed
for n in CASES:
    for reg in ("SG_Distributor", "TH_Distributor"):
        v = sorted([(k[2], r) for k, r in R[n].items() if k[:2] == ("COS_Cream", reg)], key=lambda x: wk(x[0]))
        cut = [w for w, r in v if r["q3"] > 0]
        early = [r for w, r in v if wk("2027-W01") <= wk(w) <= wk("2029-W20")]
        late = [r for w, r in v if wk(w) >= wk("2029-W21")]
        fills = Counter(f"{r['on_time']}/{r['q1']}" for w, r in v if r["q3"] > 0)
        out[f"5_{n}_{reg}"] = {"q3": sum(r["q3"] for _, r in v),
                               "cut_from": cut[0] if cut else None, "cut_to": cut[-1] if cut else None,
                               "cut_weeks": len(cut),
                               "early_rate_pct": round(100 * sum(r["on_time"] for r in early) / sum(r["q1"] for r in early), 2),
                               "late_rate_pct": round(100 * sum(r["on_time"] for r in late) / sum(r["q1"] for r in late), 2),
                               "fill_in_cut_weeks": dict(fills)}

# 6. factory P and supply point stock (own tree capture)
T = {n: tree_of(n) for n in CASES}
wl = T["MS50"][0]
assert wl == T["TH70"][0]
out["6"] = {"weeks": len(wl), "first": wl[0], "last": wl[-1]}
for s in ("COS_Serum", "COS_Cream"):
    fa, fb = T["MS50"][1][s], T["TH70"][1][s]
    sa, sb = T["MS50"][2][s], T["TH70"][2][s]
    diff_weeks = [wl[i] for i in range(len(wl)) if sa[i] != sb[i]]
    out["6"][s] = {"factory_P_weeks_differ": sum(1 for i in range(len(wl)) if fa[i] != fb[i]),
                   "factory_P_total": [sum(fa), sum(fb)],
                   "stock_max": [max(sa), max(sb)], "stock_max_week": [wl[sa.index(max(sa))], wl[sb.index(max(sb))]],
                   "stock_lot_weeks": [sum(sa), sum(sb)],
                   "stock_lot_weeks_change_pct": round(100 * (sum(sb) - sum(sa)) / sum(sa), 2) if sum(sa) else None,
                   "stock_diff_weeks": [diff_weeks[0], diff_weeks[-1], len(diff_weeks)] if diff_weeks else None,
                   "stock_max_extra": max(b - a for a, b in zip(sa, sb))}

# 7. ages: re-count from the per-delivery file with own week arithmetic, and match deliveries to the ledger
for n in CASES:
    d = rd(f"{V}/shelf/{n}/shelf_life_deliveries.csv")
    idx = {w: i for i, w in enumerate(wl)}
    ages = [idx[r["delivery_week"]] - idx[r["manufacture_week"]] for r in d]
    col_ok = all(a == int(r["fifo_age"]) for a, r in zip(ages, d))
    per = Counter((r["product"], r["channel"], r["delivery_week"]) for r in d)
    led = Counter()
    for (s, reg, w), r in R[n].items():
        if r["on_time"]:
            led[(s, reg, w)] += r["on_time"]
    out[f"7_{n}"] = {"deliveries": len(d), "age_max": max(ages), "over_52": sum(1 for a in ages if a > 52),
                     "age_column_consistent": col_ok, "deliveries_by_week_equal_on_time_by_request_week": per == led}

# 8. comparison value difference with the git-tracked unit contributions
ns = {}
src = open(CM_FILE, encoding="utf-8").read()
block = src[src.index("CM = {"):src.index("}", src.index("CM = {")) + 1]
exec(block, ns)
CM = ns["CM"]
val = {n: sum((r["on_time"] + r["early"] + r["late"]) * 24 * CM[k[:2]] for k, r in R[n].items()) for n in CASES}
out["8"] = {"contribution": val, "diff": val["TH70"] - val["MS50"],
            "with_fixed_213719220": {n: val[n] - 213719220.0 for n in CASES}}

json.dump(out, open(V + "/v2_check.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
