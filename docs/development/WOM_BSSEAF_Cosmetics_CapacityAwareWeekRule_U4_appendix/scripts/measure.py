# -*- coding: utf-8 -*-
"""Letter 4.3: T1-T10 and the summary from the outputs (no number typed by hand).
A0 and A1 are read from the U4 appendix and earlier outputs (quoted, not rerun).

    python output/bsseaf_cosmetics/cap_work/measure.py      (from the repository root)
"""
import csv
import filecmp
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

sys.path[:0] = [os.getcwd(), "output/bsseaf_cosmetics/p2a_work"]
import make_allocation as MA                                     # noqa: E402
from tools import shelf_life_check as SL                         # noqa: E402
from tools.run_headless_from_folder import run                   # noqa: E402
from wom.model.plan_node import P, S                             # noqa: E402
import wom.allocation.upper_demand_plan as U                     # noqa: E402

COS = "output/bsseaf_cosmetics"
W = COS + "/cap_work"
AP = "docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix"
FIXED = 213719220.0
CPU = 24
DIST = ("SG_Distributor", "TH_Distributor")
SKUS = ("COS_Serum", "COS_Cream")
REGS = ("SG_Store", "SG_EC", "SG_Distributor", "TH_Distributor")
LAB = {"COS_Serum": "美容液", "COS_Cream": "クリーム", "SG_Distributor": "代理店（SG）", "TH_Distributor": "代理店（TH）",
       "SG_Store": "直営店", "SG_EC": "公式 EC"}
ORDER = ("A0", "A0e", "A1", "A3")
QUOTED = {"A0": "U4_A0", "A1": "U4_A1"}
LIVE = {"A0e": ("U4_A0e_r2", "proportional_even"), "A3": ("U4_A3", "trim_to_capacity_latest")}


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def as_int(r):
    return {"sku_id": r["sku_id"], "region": r["region"], "request_week": r["request_week"],
            **{c: int(r[c]) for c in ("q1", "q2", "q3", "on_time", "early", "late", "q5")}}


M = {}
old = defaultdict(list)
for r in rd(AP + "/records/t2_all.csv"):
    old[r["case"]].append(as_int(r))
for name, case in QUOTED.items():
    M[name] = {"rows": old[name], "supply": rd(f"{AP}/udp/{case}/udp_supply_runs.csv"),
               "selection": [dict(x, q2=x["q2"]) for x in old[name]], "shelf": f"{COS}/u4_work/shelf/{case}"}
for name, (case, rule) in LIVE.items():
    u = f"{COS}/udp/{case}_{rule}"
    res = {r["source_demand_ref"]: r for r in rd(u + "/udp_result_by_request.csv")}
    rows = []
    for x in rd(u + "/udp_selection_ledger.csv"):
        sku, reg, wk = x["source_demand_ref"].split("|")
        r = res[x["source_demand_ref"]]
        rows.append(as_int(dict(sku_id=sku, region=reg, request_week=wk, q1=x["q1"], q2=x["q2"], q3=x["q3"], on_time=r["on_time"],
                                early=r["early"], late=r["late"], q5=r["q5"])))
    assert all(a["q1"] == a["q2"] + a["q3"] and a["q2"] == a["on_time"] + a["early"] + a["late"] + a["q5"] for a in rows)
    M[name] = {"rows": rows, "supply": rd(u + "/udp_supply_runs.csv"), "selection": rows, "udp": u,
               "plan": json.load(open(u + "/udp_plan.json", encoding="utf-8")), "shelf": f"{W}/shelf/{case}", "case": case}
    capt = SL._capture_plugin()
    st = json.load(open(f"{COS}/_planning_state/{case}/Q01.json", encoding="utf-8"))
    snap = run(f"{COS}/{case}", verbose=False, demand_file="demand_forecast_Q01.csv", ppc=False,
               warmup_real_start=st["period"]["warmup_real_start"], extra_plugins=[capt], output_ppc_dir=f"{W}/_noppc/{case}")
    t = capt.tree
    wl = list(t.week_labels)
    fac = {}
    for p in t.products:
        f = next(n for n in t.iter_all_nodes(p) if n.node_name == "Factory_JP")
        fac[p] = {"P": [len(f.psi4supply[w][P]) for w in range(len(wl))],
                  "cap": [f.shippable_planned(w) for w in range(len(wl))], "weeks": wl}
    M[name].update(fac=fac, period=snap["period"], state=st)

MD = COS + "/U4_A3"


def refs(n, *flags):
    return {r["sku_id"]: r["ontime_short_ref"] for r in U.time_phased_check(MD, M[n]["selection"], *flags)}


for n in M:
    M[n]["ref_plain"], M[n]["ref_cond"] = refs(n), refs(n, True, True)
    x = next(r for r in rd(M[n]["shelf"] + "/" + next(f for f in os.listdir(M[n]["shelf"]) if f.endswith("summary.csv")))
             if r["product"] == "*" and r["channel"] == "*")
    M[n]["age"] = x


def evaluate(rows):
    k = defaultdict(Counter)
    for r in rows:
        c = k[(r["sku_id"], r["region"])]
        for f in ("q1", "q2", "q3", "q5"):
            c[f] += r[f]
        c["q4"] += r["on_time"] + r["early"] + r["late"]
    tot = Counter()
    for key, c in k.items():
        cm = MA.CM[key]
        tot["contribution"] += c["q4"] * CPU * cm
        tot["lost_q3"] += c["q3"] * CPU * cm
        tot["lost_q5"] += c["q5"] * CPU * cm
    return {**tot, "evaluation": tot["contribution"] - FIXED}


P2 = json.load(open(COS + "/p2a_work/evaluation.json", encoding="utf-8"))["P2a2"]["evaluation"]
for n in M:
    M[n]["eval"] = evaluate(M[n]["rows"])
    M[n]["eval"]["diff_p2a2"] = M[n]["eval"]["evaluation"] - P2

# B3 / T8
u_old = f"{AP}/udp/U4_A0e"
u_new = M["A0e"]["udp"]
chk = {"B3_selection_same": filecmp.cmp(u_old + "/udp_selection_ledger.csv", u_new + "/udp_selection_ledger.csv", shallow=False),
       "B3_result_same": filecmp.cmp(u_old + "/udp_result_by_request.csv", u_new + "/udp_result_by_request.csv", shallow=False),
       "B3_demand_same": filecmp.cmp(f"{COS}/U4_A0e/demand_forecast_Q01.csv", f"{COS}/U4_A0e_r2/demand_forecast_Q01.csv", shallow=False),
       "B3_q5": sum(r["q5"] for r in M["A0e"]["rows"]), "B3_eval": M["A0e"]["eval"]["evaluation"]}
for f in ("flow_check_market.csv", "flow_check_nodes.csv"):
    chk["B3_" + f] = filecmp.cmp(f"{COS}/_planning_state/U4_A0e/Q01_flow_check/{f}", f"{COS}/_planning_state/U4_A0e_r2/Q01_flow_check/{f}", shallow=False)
chk["capacity_same_as_C3a"] = {n: sha(f"{COS}/{M[n]['case']}/capacity_plan.csv") == sha(COS + "/C3a/capacity_plan.csv") for n in LIVE}
chk["base_demand_same_as_sample"] = {n: sha(f"{COS}/{M[n]['case']}/demand_forecast.csv") == sha("data/sample/cosmetics-sg-th-2027-2029/demand_forecast.csv") for n in LIVE}
chk["period"] = {n: M[n]["period"] for n in LIVE}
chk["same_quota_totals"] = {n: {f"{s}|{r}": sum(x["q2"] for x in M[n]["rows"] if x["sku_id"] == s and x["region"] == r) for s in SKUS for r in REGS} for n in ("A0e", "A3")}
chk["same_quota"] = chk["same_quota_totals"]["A0e"] == chk["same_quota_totals"]["A3"]
chk["A3_plan"] = {k: M["A3"]["plan"][k] for k in ("calc_status", "consistency_status", "target_status", "owner_status", "target_commit", "code_dirty", "week_rule_detail")}
pre = json.load(open(W + "/pre_checks.json", encoding="utf-8"))["A3_before_trial"]
chk["A3_ref_same_before_and_after"] = pre["ontime_short_ref_with_conditions"] == M["A3"]["ref_cond"]


def sumr(rows, f, c=lambda r: True):
    return sum(r[f] for r in rows if c(r))


d = lambda r: r["region"] in DIST
f0 = lambda x: f"{x:,.0f}"
q4 = lambda rows: sumr(rows, "on_time") + sumr(rows, "early") + sumr(rows, "late")
hdr = "| " + " | ".join(ORDER) + " |"
sep = "---:|" * len(ORDER)
out = ["# capacity-aware week rule tables (generated by measure.py)\n", "### まとめの表\n\nA0・A1 は前回の報告書の値の引用（再実行していない）。\n\n| 項目 " + hdr + "\n|---|" + sep]


def line(label, fn):
    out.append(f"| {label} | " + " | ".join(str(fn(M[n])) for n in ORDER) + " |")


line("① 元の需要", lambda m: f0(sumr(m["rows"], "q1")))
line("② 供給対象", lambda m: f0(sumr(m["rows"], "q2")))
line("③ 未配分", lambda m: f0(sumr(m["rows"], "q3")))
line("④ 実納品", lambda m: f0(q4(m["rows"])))
line("⑤ 配分後の未充足", lambda m: f0(sumr(m["rows"], "q5")))
line("当週の充足率（全体）", lambda m: f"{sumr(m['rows'], 'on_time') / sumr(m['rows'], 'q1') * 100:.2f}%")
line("当週の充足率（代理店）", lambda m: f"{sumr(m['rows'], 'on_time', d) / sumr(m['rows'], 'q1', d) * 100:.2f}%")
line("参考値 条件なし（美容液／クリーム）", lambda m: f"{m['ref_plain']['COS_Serum']}／{m['ref_plain']['COS_Cream']}")
line("参考値 条件 2 つ（美容液／クリーム）", lambda m: f"{m['ref_cond']['COS_Serum']}／{m['ref_cond']['COS_Cream']}")
line("遅配", lambda m: f0(sumr(m["rows"], "late")))
line("代理店の供給 0 の最長の連続（週）", lambda m: max(int(s["longest_zero_run"]) for s in m["supply"] if s["region"] in DIST))
line("年齢の最大（週）", lambda m: m["age"]["fifo_age_max"])
line("評価の額（円）", lambda m: f0(m["eval"]["evaluation"]))
line("P2-a2 との差（円）", lambda m: f"{m['eval']['diff_p2a2']:+,.0f}")
out.append("\n### T1 鍵ごとの ①〜⑤（lot）\n\n前倒し・遅配はどの案も " + str(sum(sumr(M[n]["rows"], "early") + sumr(M[n]["rows"], "late") for n in M)) + " lot。\n\n| SKU・チャネル | ① | ③ | ② | ④ A0 | ⑤ A0 | ④ A0e | ⑤ A0e | ④ A1 | ⑤ A1 | ④ A3 | ⑤ A3 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for s in SKUS:
    for reg in REGS:
        v = {n: [r for r in M[n]["rows"] if r["sku_id"] == s and r["region"] == reg] for n in M}
        for c in ("q1", "q2", "q3"):
            assert len({sumr(v[n], c) for n in M}) == 1
        out.append(f"| {LAB[s]} {LAB[reg]} | {sumr(v['A0'], 'q1')} | {sumr(v['A0'], 'q3')} | {sumr(v['A0'], 'q2')} | " + " | ".join(f"{q4(v[n])} | {sumr(v[n], 'q5')}" for n in ORDER) + " |")
allw = sorted({r["request_week"] for r in M["A0"]["rows"]}, key=U._week_key)
last = allw[-30:]
idx = {n: {(r["sku_id"], r["region"], r["request_week"]): r for r in M[n]["rows"]} for n in M}
with open(W + "/t2_all.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["case", "sku_id", "region", "request_week", "q1", "q2", "q3", "on_time", "early", "late", "q5", "ontime_rate"])
    for n in LIVE:
        for r in M[n]["rows"]:
            w.writerow([n, r["sku_id"], r["region"], r["request_week"], r["q1"], r["q2"], r["q3"], r["on_time"], r["early"], r["late"], r["q5"],
                        f"{r['on_time'] / r['q1']:.4f}" if r["q1"] else "対象なし"])
out.append("\n### T2 要求週ごと（代理店 4 鍵、期間の終わりの 30 週）\n\n各セルは ②／当週／⑤。率は当週 ÷ ①。全週は付録 `records/t2_all.csv`（A0e・A3）と U4 の付録（A0・A1）。")
for s in SKUS:
    for reg in DIST:
        out.append(f"\n**{LAB[s]} {LAB[reg]}**\n\n| 要求週 | ① | A0 | 率 | A0e | 率 | A1 | 率 | A3 | 率 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for wk in last:
            c = []
            for n in ORDER:
                r = idx[n][(s, reg, wk)]
                c += [f"{r['q2']}／{r['on_time']}／{r['q5']}", f"{r['on_time'] / r['q1'] * 100:.0f}%" if r["q1"] else "対象なし"]
            out.append(f"| {wk} | {idx['A0'][(s, reg, wk)]['q1']} | " + " | ".join(c) + " |")
out.append("\n### 代理店の当週の充足率の区間（鍵ごと）\n\n率 ＝ 当週 ÷ ①。前半は 2027-W01〜2029-W20、後半は 2029-W21〜2029-W52。最低は ① が 1 以上の週の中の最小。\n\n| SKU・チャネル | 案 | 前半 | 後半 | 最低の週の率 | 当週が 0 の週の数 |\n|---|---|---:|---:|---:|---:|")
late_from = U._week_key("2029-W21")
rate_stats = {}
for s in SKUS:
    for reg in DIST:
        for n in ORDER:
            v = [r for r in M[n]["rows"] if r["sku_id"] == s and r["region"] == reg and r["q1"]]
            a = [r for r in v if U._week_key(r["request_week"]) < late_from]
            b = [r for r in v if U._week_key(r["request_week"]) >= late_from]
            ra = sumr(a, "on_time") / sumr(a, "q1") * 100
            rb = sumr(b, "on_time") / sumr(b, "q1") * 100
            mn = min(r["on_time"] / r["q1"] for r in v) * 100
            z = sum(1 for r in v if r["on_time"] == 0)
            rate_stats[f"{s}|{reg}|{n}"] = [ra, rb, mn, z]
            out.append(f"| {LAB[s]} {LAB[reg]} | {n} | {ra:.1f}% | {rb:.1f}% | {mn:.0f}% | {z} |")
out.append("\n### T3 時間の可否の参考値・未充足 ⑤・遅配（lot）\n\n| SKU | 案 | 参考値（条件なし） | 参考値（条件 2 つ） | ⑤ | 遅配 |\n|---|---|---:|---:|---:|---:|")
for s in SKUS:
    for n in ORDER:
        v = [r for r in M[n]["rows"] if r["sku_id"] == s]
        out.append(f"| {LAB[s]} | {n} | {M[n]['ref_plain'][s]} | {M[n]['ref_cond'][s]} | {sumr(v, 'q5')} | {sumr(v, 'late')} |")
out.append("\n### T4 代理店の供給 0 の週\n\n| SKU・チャネル | A0 | A0e | A1 | A3 |\n|---|---|---|---|---|")
for s in SKUS:
    for reg in DIST:
        c = []
        for n in ORDER:
            x = next(a for a in M[n]["supply"] if a["sku_id"] == s and a["region"] == reg)
            c.append(f"{x['zero_supply_weeks']}／{x['longest_zero_run']}" + (f"（{x['longest_zero_run_from']}）" if x["longest_zero_run_from"] else ""))
        out.append(f"| {LAB[s]} {LAB[reg]} | " + " | ".join(c) + " |")
wl = M["A0e"]["fac"]["COS_Serum"]["weeks"]
out.append("\n### T5 工場の週ごとの能力の余り（期間の終わりの 30 週、良品 lot。余り ＝ 平準化の上限 − 工場の P）\n\n| 週 | 美容液 上限 | A0e | A3 | クリーム 上限 | A0e | A3 |\n|---|---:|---:|---:|---:|---:|---:|")
for i in range(len(wl) - 30, len(wl)):
    c = [wl[i]]
    for s in SKUS:
        cp = M["A0e"]["fac"][s]["cap"][i]
        c += [f"{cp:.0f}"] + [f"{cp - M[n]['fac'][s]['P'][i]:.0f}" for n in ("A0e", "A3")]
    out.append("| " + " | ".join(c) + " |")
slack30 = {n: {s: sum(max(0, M[n]["fac"][s]["cap"][i] - M[n]["fac"][s]["P"][i]) for i in range(len(wl) - 30, len(wl))) for s in SKUS} for n in LIVE}
slack20 = {n: {s: sum(max(0, M[n]["fac"][s]["cap"][i] - M[n]["fac"][s]["P"][i]) for i in range(len(wl) - 20, len(wl))) for s in SKUS} for n in LIVE}
out.append("\n### T6 先入れ先出しの年齢（週）\n\n| 案 | 納品 lot | 最小 | 最大 | 52 週超 | Lot_ID の滞留の最大 | 滞留 52 週超の lot |\n|---|---:|---:|---:|---:|---:|---:|")
for n in ORDER:
    x = M[n]["age"]
    out.append("| " + n + " | " + " | ".join(str(x[c]) for c in ("deliveries", "fifo_age_min", "fifo_age_max", "over_max_age", "lot_dwell_max", "lot_dwell_over_max_age")) + " |")
out.append("\n### T7 評価の額（円）\n\n| " + hdr + "\n|---|" + sep)
for lab, k in (("④ の貢献利益", "contribution"), ("③ の逸失", "lost_q3"), ("⑤ の逸失", "lost_q5"), ("評価の額（④ − 固定費の相当額 213,719,220）", "evaluation")):
    out.append(f"| {lab} | " + " | ".join(f0(M[n]["eval"][k]) for n in ORDER) + " |")
out.append("| P2-a2 との差 | " + " | ".join(f"{M[n]['eval']['diff_p2a2']:+,.0f}" for n in ORDER) + " |")
out.append("\n### T9 ⑤ の内訳（鍵・要求週：lot）\n\n| 案 | 鍵 | lot | 要求週 |\n|---|---|---:|---|")
for n in ORDER:
    by = defaultdict(list)
    for r in M[n]["rows"]:
        if r["q5"]:
            by[(r["sku_id"], r["region"])].append((r["request_week"], r["q5"]))
    if not by:
        out.append(f"| {n} | 無し | 0 | |")
    for k, v in sorted(by.items()):
        t = "、".join(f"{w_}:{q}" for w_, q in v) if len(v) <= 8 else f"{v[0][0]}〜{v[-1][0]}（{len(v)} 週）。週の明細は付録"
        out.append(f"| {n} | {LAB[k[0]]} {LAB[k[1]]} | {sum(q for _, q in v)} | {t} |")
out.append("\n### T10 選んだ週に届いたか\n\n分母は ②（選んだ lot）。届かなかった lot は ② − 当週（前倒し・遅配は 0 なので ⑤ と同じ）。\n\n| 案 | ② | 当週に届いた | 割合 | 届かなかった lot | 届かなかった要求週 | 代理店の ② の割合 |\n|---|---:|---:|---:|---:|---|---:|")
t10 = {}
for n in ORDER:
    rows = M[n]["rows"]
    a, b = sumr(rows, "q2"), sumr(rows, "on_time")
    miss = [r for r in rows if r["q2"] > r["on_time"]]
    span = f"{min((r['request_week'] for r in miss), key=U._week_key)}〜{max((r['request_week'] for r in miss), key=U._week_key)}（{len({r['request_week'] for r in miss})} 週）" if miss else "無し"
    da, db = sumr(rows, "q2", d), sumr(rows, "on_time", d)
    t10[n] = {"q2": a, "on_time": b, "miss": a - b, "dist_q2": da, "dist_on_time": db}
    out.append(f"| {n} | {a:,} | {b:,} | {b / a * 100:.2f}% | {a - b} | {span} | {db / da * 100:.2f}% |")
open(W + "/report_tables.md", "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
dump = {"checks": chk, "slack30": slack30, "slack20": slack20, "t10": t10, "rate_stats": rate_stats,
        "eval": {n: M[n]["eval"] for n in M}, "ref_plain": {n: M[n]["ref_plain"] for n in M}, "ref_cond": {n: M[n]["ref_cond"] for n in M}}
json.dump(dump, open(W + "/measure.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(dump, ensure_ascii=False, indent=0, default=str)[:7000])
