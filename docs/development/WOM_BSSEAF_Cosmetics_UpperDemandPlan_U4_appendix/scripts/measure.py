# -*- coding: utf-8 -*-
"""U4 Part B: T1-T9 from the outputs (no number typed by hand). Writes u4_work/measure.json,
report_tables.md, t2_all.csv and the appendix CSV copies.

    python output/bsseaf_cosmetics/u4_work/measure.py      (from the repository root)
"""
import csv
import filecmp
import hashlib
import json
import os
import shutil
import sys
from collections import Counter, defaultdict

sys.path[:0] = [os.getcwd(), "output/bsseaf_cosmetics/p2a_work"]
import make_allocation as MA                                     # noqa: E402
from tools import shelf_life_check as SL                         # noqa: E402
from tools.run_headless_from_folder import run                   # noqa: E402
from wom.model.plan_node import P, S                             # noqa: E402

COS = "output/bsseaf_cosmetics"
W = COS + "/u4_work"
CASES = [("A0", "U4_A0", "proportional_early_tie"), ("A0e", "U4_A0e", "proportional_even"),
         ("A1", "U4_A1", "earliest_first")]
FIXED = 213719220.0
CPU = 24
DIST = ("SG_Distributor", "TH_Distributor")
SKUS = ("COS_Serum", "COS_Cream")
LAB = {"COS_Serum": "美容液", "COS_Cream": "クリーム", "SG_Distributor": "代理店（SG）", "TH_Distributor": "代理店（TH）",
       "SG_Store": "直営店", "SG_EC": "公式 EC"}


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


M = {}
for name, case, rule in CASES:
    u = f"{COS}/udp/{case}_{rule}"
    st = json.load(open(f"{COS}/_planning_state/{case}/Q01.json", encoding="utf-8"))
    sel = rd(u + "/udp_selection_ledger.csv")
    res = {r["source_demand_ref"]: r for r in rd(u + "/udp_result_by_request.csv")}
    rows = []
    for x in sel:
        sku, reg, wk = x["source_demand_ref"].split("|")
        r = res[x["source_demand_ref"]]
        rows.append({"case": name, "sku_id": sku, "region": reg, "request_week": wk, "q1": int(x["q1"]), "q2": int(x["q2"]),
                     "q3": int(x["q3"]), "on_time": int(r["on_time"]), "early": int(r["early"]), "late": int(r["late"]),
                     "q5": int(r["q5"]), "reason_code": x["reason_code"]})
    assert all(a["q1"] == a["q2"] + a["q3"] and a["q2"] == a["on_time"] + a["early"] + a["late"] + a["q5"] for a in rows)
    cap = rd(u + "/udp_capacity_check.csv")
    ref = {s: int(next(c for c in cap if c["sku_id"] == s)["ontime_short_ref"]) for s in SKUS}
    peak = {s: max((c for c in cap if c["sku_id"] == s), key=lambda c: int(c["cum_excess"]))["week"] for s in SKUS}
    # re-plan once for the factory PSI and the cause of (5) (read only)
    capt = SL._capture_plugin()
    snap = run(f"{COS}/{case}", verbose=False, demand_file="demand_forecast_Q01.csv", ppc=False,
               warmup_real_start=st["period"]["warmup_real_start"], extra_plugins=[capt],
               output_ppc_dir=f"{W}/_noppc/{case}")
    t = capt.tree
    wl = list(t.week_labels)
    fac, cause = {}, {}
    for p in t.products:
        nd = {n.node_name: n for n in t.iter_all_nodes(p)}
        f = nd["Factory_JP"]
        plan = {l: w for w in range(len(wl)) for l in f.psi4demand[w][S]}
        made = {l for w in range(len(wl)) for l in f.psi4supply[w][P]}
        fac[p] = {"P": [len(f.psi4supply[w][P]) for w in range(len(wl))],
                  "cap": [f.shippable_planned(w) for w in range(len(wl))], "weeks": wl,
                  "first_P": next(wl[w] for w in range(len(wl)) if f.psi4supply[w][P])}
        c = Counter()
        pw = Counter()
        for n in nd.values():
            if n.node_type != "leaf_out":
                continue
            ship = {l for ids in (n._actual_ship or {}).values() for l in ids}
            for w in range(len(wl)):
                for l in n.psi4supply[w][S]:
                    if l not in ship:
                        c["not_in_factory_plan" if l not in plan else ("planned_not_made" if l not in made else "made_not_shipped")] += 1
                        if l in plan:
                            pw[wl[plan[l]]] += 1
        cause[p] = {"counts": dict(c), "factory_plan_weeks": dict(sorted(pw.items()))}
    age = rd(f"{W}/shelf/{case}/" + next(f for f in os.listdir(f"{W}/shelf/{case}") if f.endswith("summary.csv"))) if any(
        f.endswith("summary.csv") for f in os.listdir(f"{W}/shelf/{case}")) else None
    plan_json = json.load(open(u + "/udp_plan.json", encoding="utf-8"))
    # the reference with two approximation conditions removed (T3): capacity of the first plan
    # week not usable (material LT), store demand 2 weeks earlier (ss_wks)
    adj = {}
    for s_ in SKUS:
        cr = [c for c in cap if c["sku_id"] == s_]
        ix = {c["week"]: i for i, c in enumerate(cr)}
        need = [int(c["need_good_lots"]) for c in cr]
        cp = [int(c["cap_good_lots"]) for c in cr]
        cp[0] = 0
        for r in rows:
            if r["sku_id"] == s_ and r["region"] == "SG_Store" and r["q2"]:
                i = ix[r["request_week"]] - 4
                need[i] -= r["q2"]
                need[i - 2] += r["q2"]
        cum_n = cum_c = 0
        best = None
        for n_, c_ in zip(need, cp):
            cum_n += n_
            cum_c += c_
            best = cum_n - cum_c if best is None else max(best, cum_n - cum_c)
        adj[s_] = best
    M[name] = {"case": case, "rule": rule, "udp": u, "rows": rows, "ref": ref, "ref_week": peak, "state": st,
               "supply": rd(u + "/udp_supply_runs.csv"), "fac": fac, "cause": cause, "age": age, "plan": plan_json,
               "period": snap["period"], "cap_rows": cap, "adj": adj}

# A0 against P2-a2
chk = {"A0_demand_csv_same_as_P2a2": filecmp.cmp(f"{COS}/U4_A0/demand_forecast_Q01.csv", f"{COS}/P2a2/demand_forecast_Q01.csv", shallow=False)}
for f in ("flow_check_market.csv", "flow_check_nodes.csv"):
    chk["A0_" + f] = filecmp.cmp(f"{COS}/_planning_state/U4_A0/Q01_flow_check/{f}", f"{COS}/_planning_state/P2a2/Q01_flow_check/{f}", shallow=False)
chk["capacity_same_as_C3a"] = {n: sha(f"{COS}/{c}/capacity_plan.csv") == sha(f"{COS}/C3a/capacity_plan.csv") for n, c, _ in CASES}
chk["base_demand_same_as_sample"] = {n: sha(f"{COS}/{c}/demand_forecast.csv") == sha("data/sample/cosmetics-sg-th-2027-2029/demand_forecast.csv") for n, c, _ in CASES}
chk["period"] = {n: M[n]["period"] for n in M}
chk["evidence_hashes_same"] = len({json.dumps(M[n]["state"]["evidence"]["capacity_hashes"], sort_keys=True) for n in M}) == 1


# T7
def evaluate(rows):
    k = defaultdict(lambda: Counter())
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
    return {"contribution": tot["contribution"], "lost_q3": tot["lost_q3"], "lost_q5": tot["lost_q5"],
            "evaluation": tot["contribution"] - FIXED, "by_key": {f"{a}|{b}": dict(c) for (a, b), c in sorted(k.items())}}


for n in M:
    M[n]["eval"] = evaluate(M[n]["rows"])
P2 = json.load(open(COS + "/p2a_work/evaluation.json", encoding="utf-8"))["P2a2"]["evaluation"]
for n in M:
    M[n]["eval"]["diff_p2a2"] = M[n]["eval"]["evaluation"] - P2


def sumr(rows, f, cond=lambda r: True):
    return sum(r[f] for r in rows if cond(r))


f0 = lambda x: f"{x:,.0f}"
out = ["# U4 tables (generated by measure.py)\n"]
# summary
out.append("### まとめの表\n\n| 項目 | A0 | A0e | A1 |\n|---|---:|---:|---:|")


def line(label, fn):
    out.append(f"| {label} | " + " | ".join(str(fn(M[n])) for n in ("A0", "A0e", "A1")) + " |")


d = lambda r: r["region"] in DIST
line("① 元の需要", lambda m: f0(sumr(m["rows"], "q1")))
line("② 供給対象", lambda m: f0(sumr(m["rows"], "q2")))
line("③ 未配分", lambda m: f0(sumr(m["rows"], "q3")))
line("④ 実納品", lambda m: f0(sumr(m["rows"], "on_time") + sumr(m["rows"], "early") + sumr(m["rows"], "late")))
line("⑤ 配分後の未充足", lambda m: f0(sumr(m["rows"], "q5")))
line("当週の充足率（全体）", lambda m: f"{sumr(m['rows'], 'on_time') / sumr(m['rows'], 'q1') * 100:.2f}%")
line("当週の充足率（代理店）", lambda m: f"{sumr(m['rows'], 'on_time', d) / sumr(m['rows'], 'q1', d) * 100:.2f}%")
line("時間の可否の参考値（美容液／クリーム）", lambda m: f"{m['ref']['COS_Serum']}／{m['ref']['COS_Cream']}")
line("遅配", lambda m: f0(sumr(m["rows"], "late")))
line("代理店の供給 0 の最長の連続（週）", lambda m: max(int(s["longest_zero_run"]) for s in m["supply"] if s["region"] in DIST))
agex = lambda m: next(r for r in m["age"] if r["product"] == "*" and r["channel"] == "*")
line("年齢の最大（週）", lambda m: agex(m)["fifo_age_max"])
line("評価の額（円）", lambda m: f0(m["eval"]["evaluation"]))
line("P2-a2 との差（円）", lambda m: f"{m['eval']['diff_p2a2']:+,.0f}")
# T1
out.append("\n### T1 鍵ごとの ①〜⑤（lot）\n\n| SKU・チャネル | ① | ③ | ② | ④ A0（当週／前倒し／遅配） | ⑤ A0 | ④ A0e | ⑤ A0e | ④ A1 | ⑤ A1 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for s in SKUS:
    for reg in ("SG_Store", "SG_EC", "SG_Distributor", "TH_Distributor"):
        f = lambda n, c: sum(r[c] for r in M[n]["rows"] if r["sku_id"] == s and r["region"] == reg)
        q4 = lambda n: f(n, "on_time") + f(n, "early") + f(n, "late")
        assert f("A0", "q2") == f("A1", "q2") == f("A0e", "q2") and f("A0", "q3") == f("A1", "q3")
        out.append(f"| {LAB[s]} {LAB[reg]} | {f('A0','q1')} | {f('A0','q3')} | {f('A0','q2')} | {q4('A0')}（{f('A0','on_time')}／{f('A0','early')}／{f('A0','late')}） | {f('A0','q5')} | {q4('A0e')} | {f('A0e','q5')} | {q4('A1')} | {f('A1','q5')} |")
out.append("\nA0e・A1 も前倒し・遅配は " + str(sum(sumr(M[n]["rows"], "early") + sumr(M[n]["rows"], "late") for n in M)) + " lot。\n")
# T2
allw = sorted({r["request_week"] for r in M["A0"]["rows"]})
last26 = allw[-26:]
idx = {n: {(r["sku_id"], r["region"], r["request_week"]): r for r in M[n]["rows"]} for n in M}
with open(W + "/t2_all.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["case", "sku_id", "region", "request_week", "q1", "q2", "q3", "on_time", "early", "late", "q5", "ontime_rate"])
    for n in M:
        for r in M[n]["rows"]:
            w.writerow([n, r["sku_id"], r["region"], r["request_week"], r["q1"], r["q2"], r["q3"], r["on_time"], r["early"],
                        r["late"], r["q5"], f"{r['on_time'] / r['q1']:.4f}" if r["q1"] else "対象なし"])
out.append("### T2 要求週ごと（代理店 4 鍵、期間の終わりの 26 週）\n\n各セルは ②／当週／⑤。遅配はどの案も 0。率は当週 ÷ ①。\n")
for s in SKUS:
    for reg in DIST:
        out.append(f"\n**{LAB[s]} {LAB[reg]}**\n\n| 要求週 | ① | A0 | A0 率 | A0e | A0e 率 | A1 | A1 率 |\n|---|---:|---:|---:|---:|---:|---:|---:|")
        for wk in last26:
            cells = []
            for n in ("A0", "A0e", "A1"):
                r = idx[n][(s, reg, wk)]
                cells += [f"{r['q2']}／{r['on_time']}／{r['q5']}", f"{r['on_time'] / r['q1'] * 100:.0f}%" if r["q1"] else "対象なし"]
            out.append(f"| {wk} | {idx['A0'][(s, reg, wk)]['q1']} | " + " | ".join(cells) + " |")
# T3
out.append("\n### T3 時間の可否の参考値・期末の未充足 ⑤・遅配（lot）\n\n| SKU | 案 | 参考値 | cum_excess が最大の週 | ⑤ | 遅配 | ⑤ − 参考値 | 条件 2 つを外した値 |\n|---|---|---:|---|---:|---:|---:|---:|")
for s in SKUS:
    for n in M:
        q5 = sum(r["q5"] for r in M[n]["rows"] if r["sku_id"] == s)
        lt = sum(r["late"] for r in M[n]["rows"] if r["sku_id"] == s)
        out.append(f"| {LAB[s]} | {n} | {M[n]['ref'][s]} | {M[n]['ref_week'][s]} | {q5} | {lt} | {q5 - M[n]['ref'][s]} | {M[n]['adj'][s]} |")
out.append("\n### T6 先入れ先出しの年齢（週）\n\n| 案 | 納品 lot | 最小 | 最大 | 52 週超 | Lot_ID の滞留の最大 | 滞留 52 週超の lot |\n|---|---:|---:|---:|---:|---:|---:|")
for n in M:
    x = agex(M[n])
    out.append("| " + n + " | " + " | ".join(str(x[c]) for c in ("deliveries", "fifo_age_min", "fifo_age_max", "over_max_age", "lot_dwell_max", "lot_dwell_over_max_age")) + " |")
# T4
out.append("\n### T4 代理店の供給 0 の週\n\n| SKU・チャネル | A0 週数／最長（開始） | A0e | A1 |\n|---|---|---|---|")
for s in SKUS:
    for reg in DIST:
        c = []
        for n in M:
            x = next(a for a in M[n]["supply"] if a["sku_id"] == s and a["region"] == reg)
            c.append(f"{x['zero_supply_weeks']}／{x['longest_zero_run']}" + (f"（{x['longest_zero_run_from']}）" if x["longest_zero_run_from"] else ""))
        out.append(f"| {LAB[s]} {LAB[reg]} | " + " | ".join(c) + " |")
# T5
wl = M["A0"]["fac"]["COS_Serum"]["weeks"]
out.append("\n### T5 工場の週ごとの能力の余り（期間の終わりの 20 週、良品 lot。余り ＝ 平準化の上限 − 工場の P）\n\n| 週 | 美容液 上限 | A0 | A0e | A1 | クリーム 上限 | A0 | A0e | A1 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for i in range(len(wl) - 20, len(wl)):
    c = [wl[i]]
    for s in SKUS:
        cap = M["A0"]["fac"][s]["cap"][i]
        c.append(f"{cap:.0f}")
        c += [f"{cap - M[n]['fac'][s]['P'][i]:.0f}" for n in M]
    out.append("| " + " | ".join(c) + " |")
tot = {n: {s: sum(max(0, M[n]["fac"][s]["cap"][i] - M[n]["fac"][s]["P"][i]) for i in range(len(wl) - 20, len(wl))) for s in SKUS} for n in M}
all_slack = {n: {s: sum(max(0, M[n]["fac"][s]["cap"][i] - M[n]["fac"][s]["P"][i]) for i in range(len(wl))) for s in SKUS} for n in M}
first_p = {n: {s: M[n]["fac"][s]["first_P"] for s in SKUS} for n in M}
# T7
out.append("\n### T7 評価の額（円）\n\n| | A0 | A0e | A1 |\n|---|---:|---:|---:|")
for lab, k in (("④ の貢献利益", "contribution"), ("③ の逸失", "lost_q3"), ("⑤ の逸失", "lost_q5"), ("評価の額（④ − 固定費の相当額 213,719,220）", "evaluation")):
    out.append(f"| {lab} | " + " | ".join(f0(M[n]["eval"][k]) for n in M) + " |")
out.append("| P2-a2 との差 | " + " | ".join(f"{M[n]['eval']['diff_p2a2']:+,.0f}" for n in M) + " |")
# T9
out.append("\n### T9 ⑤ の内訳（鍵・要求週：lot）\n\n| 案 | 鍵 | lot | 要求週 |\n|---|---|---:|---|")
for n in M:
    by = defaultdict(list)
    for r in M[n]["rows"]:
        if r["q5"]:
            by[(r["sku_id"], r["region"])].append((r["request_week"], r["q5"]))
    for k, v in sorted(by.items()):
        s = "、".join(f"{w}:{q}" for w, q in v) if len(v) <= 8 else f"{v[0][0]}〜{v[-1][0]}（{len(v)} 週）。週の明細は付録"
        out.append(f"| {n} | {LAB[k[0]]} {LAB[k[1]]} | {sum(q for _, q in v)} | {s} |")
open(W + "/report_tables.md", "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
dump = {n: {k: v for k, v in M[n].items() if k not in ("rows", "fac", "state", "plan", "cap_rows")} for n in M}
dump["checks"] = chk
dump["slack_last20"] = tot
dump["slack_all"] = all_slack
dump["first_P"] = first_p
dump["P2a2_eval"] = P2
json.dump(dump, open(W + "/measure.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({"checks": chk, "slack20": tot, "slack_all": all_slack, "first_P": first_p,
                  "ref": {n: M[n]["ref"] for n in M}, "ref_week": {n: M[n]["ref_week"] for n in M},
                  "cause": {n: M[n]["cause"] for n in M},
                  "eval": {n: {k: M[n]["eval"][k] for k in ("evaluation", "lost_q5", "diff_p2a2")} for n in M},
                  "plan": {n: {k: M[n]["plan"][k] for k in ("calc_status", "consistency_status", "target_status", "owner_status", "target_commit", "code_dirty", "quota_sources")} for n in M}},
                 ensure_ascii=False, indent=0)[:6000])
