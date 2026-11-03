# -*- coding: utf-8 -*-
"""Minimum supply trial: B1, S3, M1-M7 from the outputs (no number typed by hand).

    python output/bsseaf_cosmetics/ms_work/measure.py      (from the repository root)
"""
import csv
import filecmp
import hashlib
import json
import os
import sys
from collections import defaultdict

sys.path[:0] = [os.getcwd(), "output/bsseaf_cosmetics/p2a_work"]
import make_allocation as MA                                     # noqa: E402
from tools import shelf_life_check as SL                         # noqa: E402
from tools.run_headless_from_folder import run                   # noqa: E402
from wom.model.plan_node import I, P                             # noqa: E402
import wom.allocation.upper_demand_plan as U                     # noqa: E402

COS = "output/bsseaf_cosmetics"
W = COS + "/ms_work"
AP = "docs/development/WOM_BSSEAF_Cosmetics_CapacityAwareWeekRule_U4_appendix/udp/U4_A3"
RULE = "trim_to_capacity_latest"
FIXED = 213719220.0
CPU = 24
DIST = ("SG_Distributor", "TH_Distributor")
SKUS = ("COS_Serum", "COS_Cream")
REGS = ("SG_Store", "SG_EC", "SG_Distributor", "TH_Distributor")
LAB = {"COS_Serum": "美容液", "COS_Cream": "クリーム", "SG_Distributor": "代理店（SG）", "TH_Distributor": "代理店（TH）",
       "SG_Store": "直営店", "SG_EC": "公式 EC"}
RUN = ("MS_base", "MS50")
NAME = {"MS_base": "基準", "MS50": "MS50", "MS70": "MS70"}
LATE = U._week_key("2029-W21")
K = U._week_key
pre = json.load(open(W + "/pre.json", encoding="utf-8"))


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
        assert a["q1"] == a["q2"] + a["q3"] and a["q2"] == a["on_time"] + a["early"] + a["late"] + a["q5"]
        rows.append(a)
    return rows


def sumr(rows, f, c=lambda r: True):
    return sum(r[f] for r in rows if c(r))


def interval(rows, s, reg):
    v = [r for r in rows if r["sku_id"] == s and r["region"] == reg]
    cut = [r["request_week"] for r in v if r["q3"]]
    all_w = [r["request_week"] for r in v]
    if not cut:
        return None
    return {"from": cut[0], "to": cut[-1], "span": all_w.index(cut[-1]) - all_w.index(cut[0]) + 1, "cut_weeks": len(cut),
            "lots": sum(r["q3"] for r in v), "max_per_week": max(r["q3"] for r in v)}


def contrib(rows):
    return sum((r["on_time"] + r["early"] + r["late"]) * CPU * MA.CM[(r["sku_id"], r["region"])] for r in rows)


M = {}
for name in RUN:
    u = f"{COS}/udp/{name}_{RULE}"
    m = {"rows": load(u), "supply": rd(u + "/udp_supply_runs.csv"), "plan": json.load(open(u + "/udp_plan.json", encoding="utf-8")), "u": u}
    sd = f"{W}/shelf/{name}"
    m["age"] = next(r for r in rd(sd + "/" + next(f for f in os.listdir(sd) if f.endswith("summary.csv"))) if r["product"] == "*" and r["channel"] == "*")
    st = json.load(open(f"{COS}/_planning_state/{name}/Q01.json", encoding="utf-8"))
    capt = SL._capture_plugin()
    snap = run(f"{COS}/{name}", verbose=False, demand_file="demand_forecast_Q01.csv", ppc=False, warmup_real_start=st["period"]["warmup_real_start"],
               extra_plugins=[capt], output_ppc_dir=f"{W}/_noppc/{name}")
    t = capt.tree
    wl = list(t.week_labels)
    m["stock"], m["fac"] = {}, {}
    for s in t.products:
        nodes = list(t.iter_all_nodes(s))
        sp = next(n for n in nodes if n.node_type == "supply_point")
        f = next(n for n in nodes if n.node_name == "Factory_JP")
        ii = [len(sp.psi4supply[w][I]) for w in range(len(wl))]
        m["stock"][s] = {"max": max(ii), "week": wl[ii.index(max(ii))]}
        m["fac"][s] = sum(len(f.psi4supply[w][P]) for w in range(len(wl)))
    m["period"] = snap["period"]
    m["ref"] = {r["sku_id"]: r["ontime_short_ref"] for r in U.time_phased_check(f"{COS}/{name}", m["rows"], True, True)}
    m["eval"] = contrib(m["rows"]) - FIXED
    M[name] = m

chk = {"no_early_late": all(r["early"] == 0 and r["late"] == 0 for m in M.values() for r in m["rows"]),
       "B1_selection_same": filecmp.cmp(AP + "/udp_selection_ledger.csv", M["MS_base"]["u"] + "/udp_selection_ledger.csv", shallow=False),
       "B1_result_same": filecmp.cmp(AP + "/udp_result_by_request.csv", M["MS_base"]["u"] + "/udp_result_by_request.csv", shallow=False),
       "B1_q5": sumr(M["MS_base"]["rows"], "q5"), "B1_eval": M["MS_base"]["eval"],
       "plan_status": {n: [m["plan"]["calc_status"], m["plan"]["consistency_status"], m["plan"]["target_status"]] for n, m in M.items()},
       "capacity_same_as_C3a": {n: sha(f"{COS}/{n}/capacity_plan.csv") == sha(COS + "/C3a/capacity_plan.csv") for n in RUN + ("MS70",)},
       "demand_same_as_sample": {n: sha(f"{COS}/{n}/demand_forecast.csv") == sha("data/sample/cosmetics-sg-th-2027-2029/demand_forecast.csv") for n in RUN + ("MS70",)},
       "period": {n: M[n]["period"] for n in RUN}, "factory_P": {n: M[n]["fac"] for n in RUN},
       "refs_before_equal_after": {n: pre["refs_before"][n] == M[n]["ref"] for n in RUN}}
assert chk["no_early_late"]

# MS70
u70 = f"{COS}/udp/MS70_{RULE}"
p70 = json.load(open(u70 + "/udp_plan.json", encoding="utf-8"))
conf = rd(u70 + "/udp_conflicts.csv")
ref = []
for x in rd(u70 + "/udp_selection_reference.csv"):
    sku, reg, wk = x["source_demand_ref"].split("|")
    ref.append({"sku_id": sku, "region": reg, "request_week": wk, "q1": int(x["q1"]), "q2": int(x["q2"]), "q3": int(x["q3"])})
chk["MS70"] = {"status": [p70["calc_status"], p70["consistency_status"], p70["target_status"]], "totals": p70["totals"], "rc": pre["rc"]["MS70"],
               "Q01_exists": os.path.exists(f"{COS}/MS70/demand_forecast_Q01.csv"), "state_exists": os.path.exists(f"{COS}/_planning_state/MS70/Q01.json"),
               "policy": [p70["policy_id"], p70["policy_version"], p70["policy_hash"]]}

d = lambda r: r["region"] in DIST
out = ["# minimum supply tables (generated by measure.py)\n", "### まとめの表\n"]
out.append("| 項目 | 基準 | MS50 | MS70 |\n|---|---:|---:|---:|")


def cell(fn, ms70):
    return " | ".join(str(fn(M[n])) for n in RUN) + f" | {ms70}"


def span(m):
    iv = [interval(m["rows"], s, r) for s in SKUS for r in DIST]
    return f"{min((x['from'] for x in iv), key=K)}〜{max((x['to'] for x in iv), key=K)}"


rates = {}
for n in RUN:
    for s in SKUS:
        for r in DIST:
            v = [x for x in M[n]["rows"] if x["sku_id"] == s and x["region"] == r and x["q1"]]
            a = [x for x in v if K(x["request_week"]) < LATE]
            b = [x for x in v if K(x["request_week"]) >= LATE]
            rates[f"{n}|{s}|{r}"] = [sumr(a, "on_time") / sumr(a, "q1") * 100, sumr(b, "on_time") / sumr(b, "q1") * 100,
                                     min(x["on_time"] / x["q1"] for x in v) * 100]
out.append("| ③ 外す量 | " + cell(lambda m: sumr(m["rows"], "q3"), "未実行") + " |")
out.append("| 減らす区間 | " + cell(span, "未実行") + " |")
out.append("| ④ 実納品 | " + cell(lambda m: f"{sumr(m['rows'], 'on_time'):,}", "未実行") + " |")
out.append("| ⑤ 未充足 | " + cell(lambda m: sumr(m["rows"], "q5"), "未実行") + " |")
for s in SKUS:
    for r in DIST:
        out.append(f"| 週の最低 {LAB[s]} {LAB[r]} | " + " | ".join(f"{rates[f'{n}|{s}|{r}'][2]:.0f}%" for n in RUN) + " | 未実行 |")
check = {n: rd(f"{COS}/udp/{n}_{RULE}/udp_min_supply_check.csv") for n in ("MS50",)}
summ = M["MS50"]["plan"]["min_supply_summary"]
pb = sum(len(v["plan_below_weeks"]) for v in summ.values())
db = sum(len(v["delivered_below_weeks"]) for v in summ.values())
out.append(f"| 最低供給量を下回った週（計画の時／実行の結果） | 対象外 | {pb}／{db} | 未実行 |")
out.append("| 評価の額（円） | " + cell(lambda m: f"{m['eval']:,.0f}", "未実行") + " |")
out.append(f"| 衝突 | 無し | 無し | クリーム 代理店（TH）で {conf[0]['unplaceable_lots']} lot |")

out.append("\n### M1 鍵ごとの ①〜⑤ と減らす区間\n\n| SKU・チャネル | 案 | ① | ② | ③ | ④ | ⑤ | 始まり | 終わり | 長さ | 減らす週 | 週の最大 |\n|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|")
for s in SKUS:
    for r in REGS:
        for n in RUN:
            v = [x for x in M[n]["rows"] if x["sku_id"] == s and x["region"] == r]
            iv = interval(M[n]["rows"], s, r)
            tail = f"{iv['from']} | {iv['to']} | {iv['span']} | {iv['cut_weeks']} | {iv['max_per_week']}" if iv else "— | — | — | — | —"
            out.append(f"| {LAB[s]} {LAB[r]} | {NAME[n]} | {sumr(v, 'q1')} | {sumr(v, 'q2')} | {sumr(v, 'q3')} | {sumr(v, 'on_time')} | {sumr(v, 'q5')} | {tail} |")

out.append("\n### M2 最低供給量の二段階の確認（MS50）\n\n| 鍵 | 確認した週 | 計画の時に下回った週 | 実行の結果で下回った週 |\n|---|---:|---:|---:|")
for k, v in summ.items():
    s, r = k.split("|")
    out.append(f"| {LAB[s]} {LAB[r]} | {v['weeks']} | {len(v['plan_below_weeks'])} | {len(v['delivered_below_weeks'])} |")

out.append("\n### M3 代理店の当週の充足率\n\n前半 2027-W01〜2029-W20、後半 2029-W21〜2029-W52。週の最低は ① が 1 以上の週の最小。\n\n| SKU・チャネル | 案 | 前半 | 後半 | 週の最低 |\n|---|---|---:|---:|---:|")
for s in SKUS:
    for r in DIST:
        for n in RUN:
            a, b, c = rates[f"{n}|{s}|{r}"]
            out.append(f"| {LAB[s]} {LAB[r]} | {NAME[n]} | {a:.1f}% | {b:.1f}% | {c:.0f}% |")
out.append("\n全体の当週の充足率\n\n| 案 | 全体 | 代理店 |\n|---|---:|---:|")
for n in RUN:
    v = M[n]["rows"]
    out.append(f"| {NAME[n]} | {sumr(v, 'on_time') / sumr(v, 'q1') * 100:.2f}% | {sumr(v, 'on_time', d) / sumr(v, 'q1', d) * 100:.2f}% |")

out.append("\n### M4 時間の可否の参考値（条件 2 つ）と未充足\n\n| 案 | SKU | 参考値（試行の前） | ⑤ |\n|---|---|---:|---:|")
for n in RUN:
    for s in SKUS:
        out.append(f"| {NAME[n]} | {LAB[s]} | {pre['refs_before'][n][s]} | {sumr([x for x in M[n]['rows'] if x['sku_id'] == s], 'q5')} |")
for s in SKUS:
    extra = "（衝突の鍵を除いた参考の台帳の値）" if s == "COS_Cream" else ""
    out.append(f"| MS70 | {LAB[s]} | {pre['refs_before']['MS70'][s]}{extra} | 未実行 |")

out.append("\n### M5 年齢・作り置き・評価の額\n\n| 案 | 年齢の最大 | 52 週超 | Lot_ID の滞留の最大 | 滞留 52 週超 | 作り置きの最大（美容液／クリーム） | 代理店の供給 0 の最長の連続 | 評価の額（円） | 基準との差 |\n|---|---:|---:|---:|---:|---|---:|---:|---:|")
for n in RUN:
    m = M[n]
    a = m["age"]
    z = max(int(x["longest_zero_run"]) for x in m["supply"] if x["region"] in DIST)
    out.append(f"| {NAME[n]} | {a['fifo_age_max']} | {a['over_max_age']} | {a['lot_dwell_max']} | {a['lot_dwell_over_max_age']} | {m['stock']['COS_Serum']['max']}／{m['stock']['COS_Cream']['max']} | {z} | {m['eval']:,.0f} | {m['eval'] - M['MS_base']['eval']:+,.0f} |")
out.append("| MS70 | 未実行 | 未実行 | 未実行 | 未実行 | 未実行 | 未実行 | 未実行 | 未実行 |")

out.append("\n### M6 MS70 の衝突の記録（`udp_conflicts.csv`）\n\n| 鍵 | 外す量 | 置ける量 | 置けない量 | 比率 | 端数 |\n|---|---:|---:|---:|---:|---|")
for c in conf:
    out.append(f"| {LAB[c['sku_id']]} {LAB[c['region']]} | {c['quota_cut_lots']} | {c['placeable_cut_lots']} | {c['unplaceable_lots']} | {c['min_supply_ratio']} | {c['rounding']} |")
out.append(f"\n原因：{conf[0]['reason']}\n\n代わりの案：{conf[0]['alternatives']}")

out.append("\n### M7 参考：MS70 で衝突の無い鍵の選び方\n\n`udp_selection_reference.csv`。エンジンに渡していないので、④⑤ は未実行。\n\n| SKU・チャネル | ① | ② | ③ | 始まり | 終わり | 長さ | 減らす週 | 週の最大 | 基準の始まり |\n|---|---:|---:|---:|---|---|---:|---:|---:|---|")
for s in SKUS:
    for r in DIST:
        if s == "COS_Cream" and r == "TH_Distributor":
            continue
        iv = interval(ref, s, r)
        v = [x for x in ref if x["sku_id"] == s and x["region"] == r]
        out.append(f"| {LAB[s]} {LAB[r]} | {sumr(v, 'q1')} | {sumr(v, 'q2')} | {sumr(v, 'q3')} | {iv['from']} | {iv['to']} | {iv['span']} | {iv['cut_weeks']} | {iv['max_per_week']} | {interval(M['MS_base']['rows'], s, r)['from']} |")

open(W + "/report_tables.md", "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
with open(W + "/t2_all.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["case", "sku_id", "region", "request_week", "q1", "q2", "q3", "on_time", "early", "late", "q5"])
    for n in RUN:
        for r in M[n]["rows"]:
            w.writerow([n] + [r[c] for c in ("sku_id", "region", "request_week", "q1", "q2", "q3", "on_time", "early", "late", "q5")])
dump = {"checks": chk, "rates": rates, "eval": {n: M[n]["eval"] for n in RUN}, "stock": {n: M[n]["stock"] for n in RUN}, "min_supply_summary": summ,
        "stock_week": {n: M[n]["stock"] for n in RUN}}
json.dump(dump, open(W + "/measure.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(open(W + "/report_tables.md", encoding="utf-8").read())
print(json.dumps(chk, ensure_ascii=False, default=str)[:2800])
