# -*- coding: utf-8 -*-
"""Thai cream minimum 70% trial, T3: compare MS50 (reproduced) and TH70 from the outputs.

    python output/bsseaf_cosmetics_th70/work/th70_measure.py      (from the repository root)

Based on docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/scripts/measure.py.
No number is typed by hand; the evaluation uses the unit contributions of the git-tracked
docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/scripts/make_allocation.py (CM).
"""
import csv
import hashlib
import json
import os
import sys
from collections import Counter

sys.path[:0] = [os.getcwd(), "docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/scripts"]
import make_allocation as MA                                     # noqa: E402
from tools import shelf_life_check as SL                         # noqa: E402
from tools.run_headless_from_folder import run                   # noqa: E402
from wom.model.plan_node import I, P                             # noqa: E402
import wom.allocation.upper_demand_plan as U                     # noqa: E402

OUT = "output/bsseaf_cosmetics_th70"
W = OUT + "/work"
RULE = "trim_to_capacity_latest"
FIXED = 213719220.0
CPU = 24
CASES = ("MS50", "TH70")
SKUS = ("COS_Serum", "COS_Cream")
DIST = ("SG_Distributor", "TH_Distributor")
REGS = ("SG_Store", "SG_EC", "SG_Distributor", "TH_Distributor")
LAB = {"COS_Serum": "美容液", "COS_Cream": "クリーム", "SG_Distributor": "代理店（SG）", "TH_Distributor": "代理店（TH）",
       "SG_Store": "直営店", "SG_EC": "公式 EC"}
K = U._week_key
LATE = K("2029-W21")


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load(u):
    res = {r["source_demand_ref"]: r for r in rd(u + "/udp_result_by_request.csv")}
    rows = []
    for x in rd(u + "/udp_selection_ledger.csv"):
        sku, reg, wk = x["source_demand_ref"].split("|")
        r = res[x["source_demand_ref"]]
        a = {"sku_id": sku, "region": reg, "request_week": wk, **{c: int(x[c]) for c in ("q1", "q2", "q3")},
             **{c: int(r[c]) for c in ("on_time", "early", "late", "q5")}}
        assert a["q1"] == a["q2"] + a["q3"] and a["q2"] == a["on_time"] + a["early"] + a["late"] + a["q5"], a
        rows.append(a)
    return rows


def sumr(rows, f, c=lambda r: True):
    return sum(r[f] for r in rows if c(r))


def key(rows, s, r):
    return [x for x in rows if x["sku_id"] == s and x["region"] == r]


def interval(rows, s, reg):
    v = key(rows, s, reg)
    cut = [r["request_week"] for r in v if r["q3"]]
    all_w = [r["request_week"] for r in v]
    if not cut:
        return None
    return {"from": cut[0], "to": cut[-1], "span": all_w.index(cut[-1]) - all_w.index(cut[0]) + 1, "cut_weeks": len(cut),
            "lots": sum(r["q3"] for r in v), "max_per_week": max(r["q3"] for r in v)}


def contrib(rows):
    return sum((r["on_time"] + r["early"] + r["late"]) * CPU * MA.CM[(r["sku_id"], r["region"])] for r in rows)


M = {}
for n in CASES:
    u = f"{OUT}/udp/{n}_{RULE}"
    pre = json.load(open(f"{W}/{n}_pre.json", encoding="utf-8"))
    m = {"rows": load(u), "supply": rd(u + "/udp_supply_runs.csv"), "plan": json.load(open(u + "/udp_plan.json", encoding="utf-8")),
         "check": rd(u + "/udp_min_supply_check.csv"), "cap": rd(u + "/udp_capacity_check.csv"), "pre": pre, "u": u}
    sd = f"{OUT}/shelf/{n}"
    summ = rd(sd + "/" + next(f for f in os.listdir(sd) if f.endswith("summary.csv")))
    m["age"] = next(r for r in summ if r["product"] == "*" and r["channel"] == "*")
    m["age_rows"] = summ
    st = json.load(open(f"{OUT}/_planning_state/{n}/Q01.json", encoding="utf-8"))
    capt = SL._capture_plugin()
    snap = run(f"{OUT}/{n}", verbose=False, demand_file="demand_forecast_Q01.csv", ppc=False,
               warmup_real_start=st["period"]["warmup_real_start"], extra_plugins=[capt], output_ppc_dir=f"{W}/_noppc/{n}")
    t = capt.tree
    wl = list(t.week_labels)
    m["stock"], m["fac"], m["stock_series"] = {}, {}, {}
    for s in t.products:
        nodes = list(t.iter_all_nodes(s))
        sp = next(x for x in nodes if x.node_type == "supply_point")
        f = next(x for x in nodes if x.node_name == "Factory_JP")
        ii = [len(sp.psi4supply[w][I]) for w in range(len(wl))]
        m["stock"][s] = {"max": max(ii), "week": wl[ii.index(max(ii))], "lot_weeks": sum(ii)}
        m["stock_series"][s] = dict(zip(wl, ii))
        m["fac"][s] = {w: len(f.psi4supply[i][P]) for i, w in enumerate(wl)}
    m["period"] = snap["period"]
    m["ref_after"] = {r["sku_id"]: r["ontime_short_ref"] for r in U.time_phased_check(f"{OUT}/{n}", m["rows"], True, True)}
    m["eval"] = contrib(m["rows"]) - FIXED
    M[n] = m

a, b = M["MS50"], M["TH70"]
idx = lambda rows: {(r["sku_id"], r["region"], r["request_week"]): r for r in rows}
ia, ib = idx(a["rows"]), idx(b["rows"])
changed_keys = sorted({k[:2] for k in ia if ia[k] != ib[k]})
th = key(b["rows"], "COS_Cream", "TH_Distributor")
chk = {
    "rc": {n: M[n]["pre"]["rc"] for n in CASES},
    "conflicts_before": {n: M[n]["pre"]["conflicts_before"] for n in CASES},
    "status": {n: [M[n]["plan"]["calc_status"], M[n]["plan"]["consistency_status"], M[n]["plan"]["target_status"]] for n in CASES},
    "totals": {n: M[n]["plan"]["totals"] for n in CASES},
    "no_early_late": all(r["early"] == 0 and r["late"] == 0 for m in M.values() for r in m["rows"]),
    "input_hash_diff": sorted(k for k in set(a["plan"]["input_hashes"]) | set(b["plan"]["input_hashes"])
                              if a["plan"]["input_hashes"].get(k) != b["plan"]["input_hashes"].get(k)),
    "period": {n: M[n]["period"] for n in CASES},
    "keys_with_any_change": [f"{s}|{r}" for s, r in changed_keys],
    "TH_cream_weeks": len([r for r in th if r["q1"]]),
    "TH_cream_all_on_time_full": all(r["on_time"] == r["q1"] for r in th),
    "factory_P_same": {s: a["fac"][s] == b["fac"][s] for s in SKUS},
    "factory_P_total": {n: {s: sum(M[n]["fac"][s].values()) for s in SKUS} for n in CASES},
    "refs_before": {n: M[n]["pre"]["refs_before"] for n in CASES},
    "refs_after": {n: M[n]["ref_after"] for n in CASES},
    "min_supply_summary": {n: {k: [v["weeks"], len(v["plan_below_weeks"]), len(v["delivered_below_weeks"])]
                               for k, v in M[n]["plan"]["min_supply_summary"].items()} for n in CASES},
    "plan_policy": {n: [M[n]["plan"]["policy_id"], M[n]["plan"]["policy_version"], M[n]["plan"]["policy_hash"]] for n in CASES},
    "plan_meta": {n: {k: M[n]["plan"].get(k) for k in ("target_commit", "code_dirty", "owner_decisions", "knowledge_used",
                                                         "adoption_status", "owner_status")} for n in CASES},
}
assert chk["no_early_late"]

# factory weekly P differences (cream)
fd = [(w, a["fac"]["COS_Cream"][w], b["fac"]["COS_Cream"][w]) for w in a["fac"]["COS_Cream"] if a["fac"]["COS_Cream"][w] != b["fac"]["COS_Cream"][w]]
chk["cream_factory_P_diff_weeks"] = fd
sd_ = [(w, a["stock_series"]["COS_Cream"][w], b["stock_series"]["COS_Cream"][w]) for w in a["stock_series"]["COS_Cream"]
       if a["stock_series"]["COS_Cream"][w] != b["stock_series"]["COS_Cream"][w]]
chk["cream_stock_diff_weeks"] = sd_

# the plan's estimate vs the tool (SG cream)
iv = interval(b["rows"], "COS_Cream", "SG_Distributor")
sg = [r for r in key(b["rows"], "COS_Cream", "SG_Distributor") if r["q1"]]
cutrows = [r for r in sg if r["q3"]]
chk["estimate_vs_tool"] = {"estimate": {"q3": 88, "from": "2029-W07", "to": "2029-W50", "cut_weeks": 44, "fill_in_cut_weeks": "3/5"},
                           "tool": {"q3": iv["lots"], "from": iv["from"], "to": iv["to"], "cut_weeks": iv["cut_weeks"],
                                    "span": iv["span"], "max_per_week": iv["max_per_week"],
                                    "fill_in_cut_weeks": dict(Counter(f"{r['on_time']}/{r['q1']}" for r in cutrows))}}

rates = {}
for n in CASES:
    for s in SKUS:
        for r in DIST:
            v = [x for x in key(M[n]["rows"], s, r) if x["q1"]]
            e = [x for x in v if K(x["request_week"]) < LATE]
            l = [x for x in v if K(x["request_week"]) >= LATE]
            rates[f"{n}|{s}|{r}"] = [sumr(e, "on_time") / sumr(e, "q1") * 100, sumr(l, "on_time") / sumr(l, "q1") * 100,
                                     min(x["on_time"] / x["q1"] for x in v) * 100]

NAME = {"MS50": "MS50（基準、再現）", "TH70": "TH70"}
out = ["# TH70 trial tables (generated by th70_measure.py)\n", "### まとめの表\n", "| 項目 | MS50（再現） | TH70 |\n|---|---:|---:|"]
row = lambda lab, fn: out.append(f"| {lab} | " + " | ".join(str(fn(M[n])) for n in CASES) + " |")
row("終了コード", lambda m: m["pre"]["rc"])
row("③ 外す量", lambda m: sumr(m["rows"], "q3"))
row("④ 実納品（すべて当週）", lambda m: f"{sumr(m['rows'], 'on_time'):,}")
row("⑤ 未充足", lambda m: sumr(m["rows"], "q5"))
for s in SKUS:
    for r in DIST:
        out.append(f"| 週の最低の充足率 {LAB[s]} {LAB[r]} | " + " | ".join(f"{rates[f'{n}|{s}|{r}'][2]:.0f}%" for n in CASES) + " |")
row("最低供給量を下回った週（計画の時／実行の結果）", lambda m: "{}／{}".format(
    sum(len(v["plan_below_weeks"]) for v in m["plan"]["min_supply_summary"].values()),
    sum(len(v["delivered_below_weeks"]) for v in m["plan"]["min_supply_summary"].values())))
row("時間の可否の参考値（美容液／クリーム、試行の前）", lambda m: f"{m['pre']['refs_before']['COS_Serum']}／{m['pre']['refs_before']['COS_Cream']}")
row("年齢の最大（週）", lambda m: m["age"]["fifo_age_max"])
row("年齢 52 週超", lambda m: m["age"]["over_max_age"])
row("Lot_ID の滞留の最大（参考）", lambda m: m["age"]["lot_dwell_max"])
row("作り置きの最大 クリーム（lot、週）", lambda m: f"{m['stock']['COS_Cream']['max']}（{m['stock']['COS_Cream']['week']}）")
row("作り置きの lot・週の合計 クリーム", lambda m: f"{m['stock']['COS_Cream']['lot_weeks']:,}")
row("作り置きの最大 美容液（lot、週）", lambda m: f"{m['stock']['COS_Serum']['max']}（{m['stock']['COS_Serum']['week']}）")
row("比べるための評価の額（円）", lambda m: f"{m['eval']:,.0f}")
out.append(f"| 評価の額の差（TH70 − MS50） | | {b['eval'] - a['eval']:+,.0f} |")

out.append("\n### 鍵ごとの ①〜⑤ と減らす区間\n\n| SKU・チャネル | 案 | ① | ② | ③ | ④ | ⑤ | 始まり | 終わり | 長さ | 減らす週 | 週の最大 |\n|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|")
for s in SKUS:
    for r in REGS:
        for n in CASES:
            v = key(M[n]["rows"], s, r)
            iv2 = interval(M[n]["rows"], s, r)
            tail = f"{iv2['from']} | {iv2['to']} | {iv2['span']} | {iv2['cut_weeks']} | {iv2['max_per_week']}" if iv2 else "— | — | — | — | —"
            out.append(f"| {LAB[s]} {LAB[r]} | {NAME[n]} | {sumr(v, 'q1')} | {sumr(v, 'q2')} | {sumr(v, 'q3')} | {sumr(v, 'on_time')} | {sumr(v, 'q5')} | {tail} |")

out.append("\n### 最低供給量の二段階の確認\n\n| 鍵 | 案 | 比率 | 確認した週 | 計画の時に下回った週 | 実行の結果で下回った週 |\n|---|---|---:|---:|---:|---:|")
for n in CASES:
    pol = {(r["sku_id"], r["region"]): r["min_supply_ratio"] for r in rd(
        "docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/policy/udp_policy_MS50.csv" if n == "MS50" else W + "/udp_policy_MS50TH70.csv")}
    for k, v in M[n]["plan"]["min_supply_summary"].items():
        s, r = k.split("|")
        out.append(f"| {LAB[s]} {LAB[r]} | {NAME[n]} | {pol[(s, r)]} | {v['weeks']} | {len(v['plan_below_weeks'])} | {len(v['delivered_below_weeks'])} |")

out.append("\n### 代理店の当週の充足率（前半 2027-W01〜2029-W20、後半 2029-W21〜W52）\n\n| SKU・チャネル | 案 | 前半 | 後半 | 週の最低 |\n|---|---|---:|---:|---:|")
for s in SKUS:
    for r in DIST:
        for n in CASES:
            e, l, mn = rates[f"{n}|{s}|{r}"]
            out.append(f"| {LAB[s]} {LAB[r]} | {NAME[n]} | {e:.1f}% | {l:.1f}% | {mn:.0f}% |")

out.append("\n### 年齢（先入れ先出し）SKU・チャネル別\n\n| 案 | SKU | チャネル | 納品 | 最小 | 最大 | 52 週超 | Lot_ID の滞留の最大 |\n|---|---|---|---:|---:|---:|---:|---:|")
for n in CASES:
    for r in M[n]["age_rows"]:
        out.append(f"| {NAME[n]} | {r['product']} | {r['channel']} | {r['deliveries']} | {r['fifo_age_min']} | {r['fifo_age_max']} | {r['over_max_age']} | {r['lot_dwell_max']} |")

out.append("\n### 作業計画の近似と道具の結果（クリーム 代理店（SG））\n")
out.append("```\n" + json.dumps(chk["estimate_vs_tool"], ensure_ascii=False, indent=1) + "\n```")
out.append(f"\n工場のクリームの週の生産 P が違う週：{len(fd)}（合計 MS50 {chk['factory_P_total']['MS50']['COS_Cream']}、TH70 {chk['factory_P_total']['TH70']['COS_Cream']}）")
out.append(f"\n作り置き（クリーム）が違う週：{len(sd_)}")

open(W + "/report_tables.md", "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
with open(W + "/th70_all.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["case", "sku_id", "region", "request_week", "q1", "q2", "q3", "on_time", "early", "late", "q5"])
    for n in CASES:
        for r in M[n]["rows"]:
            w.writerow([n] + [r[c] for c in ("sku_id", "region", "request_week", "q1", "q2", "q3", "on_time", "early", "late", "q5")])
with open(W + "/cream_factory_stock_by_week.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["week", "factory_P_MS50", "factory_P_TH70", "supply_point_I_MS50", "supply_point_I_TH70"])
    for wk in a["fac"]["COS_Cream"]:
        w.writerow([wk, a["fac"]["COS_Cream"][wk], b["fac"]["COS_Cream"][wk],
                    a["stock_series"]["COS_Cream"][wk], b["stock_series"]["COS_Cream"][wk]])
dump = {"checks": chk, "rates": rates, "eval": {n: M[n]["eval"] for n in CASES}, "stock": {n: M[n]["stock"] for n in CASES},
        "age": {n: M[n]["age"] for n in CASES}}
json.dump(dump, open(W + "/measure.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(open(W + "/report_tables.md", encoding="utf-8").read())
print(json.dumps({k: v for k, v in chk.items() if k not in ("plan_meta", "cream_factory_P_diff_weeks", "cream_stock_diff_weeks")},
                 ensure_ascii=False, default=str))
print(json.dumps(chk["plan_meta"], ensure_ascii=False, default=str))
