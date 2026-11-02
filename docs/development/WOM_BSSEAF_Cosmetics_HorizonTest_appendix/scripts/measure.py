# -*- coding: utf-8 -*-
"""Horizon test: H1-H6, S3, S4 from the outputs (no number typed by hand). E0 is read from the
tracked appendix of the capacity-aware report (not rerun as a plan; only its stock is re-observed).

    python output/bsseaf_cosmetics/hz_work/measure.py      (from the repository root)
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

sys.path[:0] = [os.getcwd(), "output/bsseaf_cosmetics/p2a_work"]
import make_allocation as MA                                     # noqa: E402
from tools import shelf_life_check as SL                         # noqa: E402
from tools.run_headless_from_folder import run                   # noqa: E402
from wom.model.plan_node import I, P                             # noqa: E402
import wom.allocation.upper_demand_plan as U                     # noqa: E402

COS = "output/bsseaf_cosmetics"
W = COS + "/hz_work"
AP = "docs/development/WOM_BSSEAF_Cosmetics_CapacityAwareWeekRule_U4_appendix"
FIXED = 213719220.0
CPU = 24
DIST = ("SG_Distributor", "TH_Distributor")
SKUS = ("COS_Serum", "COS_Cream")
REGS = ("SG_Store", "SG_EC", "SG_Distributor", "TH_Distributor")
LAB = {"COS_Serum": "美容液", "COS_Cream": "クリーム", "SG_Distributor": "代理店（SG）", "TH_Distributor": "代理店（TH）",
       "SG_Store": "直営店", "SG_EC": "公式 EC"}
ES, AS = ("E0", "E13", "E26"), ("A0e", "A3")
RULE = {"A0e": "proportional_even", "A3": "trim_to_capacity_latest"}
COMMON_END = U._week_key("2029-W52")
LATE_FROM = U._week_key("2029-W21")
K = U._week_key
pre = json.load(open(W + "/pre.json", encoding="utf-8"))


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def load(u):
    res = {r["source_demand_ref"]: r for r in rd(u + "/udp_result_by_request.csv")}
    rows = []
    for x in rd(u + "/udp_selection_ledger.csv"):
        sku, reg, wk = x["source_demand_ref"].split("|")
        r = res[x["source_demand_ref"]]
        a = {"sku_id": sku, "region": reg, "request_week": wk, "reason_code": x["reason_code"],
             **{c: int(x[c]) for c in ("q1", "q2", "q3")}, **{c: int(r[c]) for c in ("on_time", "early", "late", "q5")}}
        assert a["q1"] == a["q2"] + a["q3"] and a["q2"] == a["on_time"] + a["early"] + a["late"] + a["q5"]
        rows.append(a)
    return rows


M = {}
for e in ES:
    for a in AS:
        if e == "E0":
            case = {"A0e": "U4_A0e_r2", "A3": "U4_A3"}[a]
            u = f"{AP}/udp/{case}"
            shelf = f"{COS}/cap_work/shelf/{case}"
        else:
            case = f"H_{e}_{a}"
            u = f"{COS}/udp/{case}_{RULE[a]}"
            shelf = f"{W}/shelf/{case}"
        m = {"case": case, "rows": load(u), "supply": rd(u + "/udp_supply_runs.csv"),
             "plan": json.load(open(u + "/udp_plan.json", encoding="utf-8"))}
        m["age"] = next(r for r in rd(shelf + "/" + next(f for f in os.listdir(shelf) if f.endswith("summary.csv")))
                        if r["product"] == "*" and r["channel"] == "*")
        st = json.load(open(f"{COS}/_planning_state/{case}/Q01.json", encoding="utf-8"))
        capt = SL._capture_plugin()
        snap = run(f"{COS}/{case}", verbose=False, demand_file="demand_forecast_Q01.csv", ppc=False,
                   warmup_real_start=st["period"]["warmup_real_start"], extra_plugins=[capt], output_ppc_dir=f"{W}/_noppc/{case}")
        t = capt.tree
        wl = list(t.week_labels)
        m["stock"], m["fac"] = {}, {}
        for s in t.products:
            nodes = list(t.iter_all_nodes(s))
            sp = next(n for n in nodes if n.node_type == "supply_point")
            f = next(n for n in nodes if n.node_name == "Factory_JP")
            ii = [len(sp.psi4supply[w][I]) for w in range(len(wl))]
            pp = [len(f.psi4supply[w][P]) for w in range(len(wl))]
            nz = [i for i, v in enumerate(pp) if v]
            m["stock"][s] = {"max": max(ii), "week": wl[ii.index(max(ii))]}
            m["fac"][s] = {"P_total": sum(pp), "first": wl[nz[0]], "last": wl[nz[-1]]}
        m["period"] = snap["period"]
        m["state"] = st
        M[(e, a)] = m


def sumr(rows, f, c=lambda r: True):
    return sum(r[f] for r in rows if c(r))


def common(rows):
    return [r for r in rows if K(r["request_week"]) <= COMMON_END]


chk = {"no_early_late": all(r["early"] == 0 and r["late"] == 0 for m in M.values() for r in m["rows"])}
assert chk["no_early_late"]         # so q5 at 2029-W52 of the common demand = q2 - on_time
chk["plan_status"] = {m["case"]: [m["plan"]["calc_status"], m["plan"]["consistency_status"]] for m in M.values()}
chk["knowledge_written"] = {m["case"]: [m["plan"]["knowledge_used"] == json.load(open(W + "/knowledge.json", encoding="utf-8")),
                                        m["plan"]["owner_decisions"]] for (e, a), m in M.items() if e != "E0"}
chk["period"] = {m["case"]: m["period"] for m in M.values()}
chk["factory_P_vs_B1"] = {m["case"]: m["fac"] for m in M.values()}
chk["refs_after"] = {}
for (e, a), m in M.items():
    if e == "E0":
        md = f"{COS}/{m['case']}"
    else:
        md = f"{COS}/H_{e}_{a}"
    chk["refs_after"][m["case"]] = {r["sku_id"]: r["ontime_short_ref"] for r in U.time_phased_check(md, m["rows"], True, True)}
    m["ref"] = chk["refs_after"][m["case"]]
chk["refs_before_equal_after"] = {c: v == chk["refs_after"][c] for c, v in pre["refs_before"].items()}
chk["golden_like_E0_q5"] = {m["case"]: sumr(m["rows"], "q5") for (e, a), m in M.items() if e == "E0"}

# money
ppc = json.load(open(COS + "/money_m0_work/checks_ppc.json", encoding="utf-8"))
ur = {(r["product_id"], r["channel"]): r["unit_revenue"] for r in ppc["M0"]["sku_channel"]}
chk["fixed_from_unit_revenue"] = None


def added_fixed(rows):
    """store revenue x 45% + EC revenue x 10% of the demand after 2029-W52 (all supplied in full)."""
    return sum(r["q1"] * CPU * ur[(r["sku_id"], r["region"])] * MA.ADD_BACK[r["region"]]
               for r in rows if K(r["request_week"]) > COMMON_END)


def contrib(rows):
    return sum((r["on_time"] + r["early"] + r["late"]) * CPU * MA.CM[(r["sku_id"], r["region"])] for r in rows)


base_rows = M[("E0", "A3")]["rows"]
fx = sum(r["q1"] * CPU * ur[(r["sku_id"], r["region"])] * MA.ADD_BACK[r["region"]] for r in base_rows)
chk["fixed_from_unit_revenue"] = {"derived": fx, "letter": FIXED}
for m in M.values():
    c = common(m["rows"])
    m["eval_common"] = contrib(c) - FIXED
    m["fixed_all"] = FIXED + added_fixed(m["rows"])
    m["eval_all"] = contrib(m["rows"]) - m["fixed_all"]


def interval(rows, s, reg):
    v = [r for r in rows if r["sku_id"] == s and r["region"] == reg]
    wks = [r["request_week"] for r in v if r["q3"]]
    all_w = [r["request_week"] for r in v]
    if not wks:
        return None
    a, b = all_w.index(wks[0]), all_w.index(wks[-1])
    return {"from": wks[0], "to": wks[-1], "span": b - a + 1, "cut_weeks": len(wks), "lots": sum(r["q3"] for r in v),
            "max_per_week": max(r["q3"] for r in v)}


def bucket(w):
    k = K(w)
    return "〜2028" if k[0] <= 2028 else "2029-W01〜W20" if k < LATE_FROM else "2029-W21〜W52" if k <= COMMON_END else "2030"


def rates(rows, s, reg, lo=None, hi=None):
    v = [r for r in rows if r["sku_id"] == s and r["region"] == reg and r["q1"]
         and (lo is None or K(r["request_week"]) >= lo) and (hi is None or K(r["request_week"]) <= hi)]
    if not v:
        return None
    return {"rate": sumr(v, "on_time") / sumr(v, "q1") * 100, "min": min(r["on_time"] / r["q1"] for r in v) * 100}


d = lambda r: r["region"] in DIST
out = ["# horizon test tables (generated by measure.py)\n", "### まとめの表\n"]
out.append("減らす区間は代理店 4 鍵の中の最も早い始まり・最も遅い終わりと、鍵ごとの長さの範囲。「共通」は要求週 2027-W01〜2029-W52。参考値は条件 2 つ。\n")
out.append("| 期間 | 規則 | ③ 外す量（全体） | 減らす区間の始まり | 終わり | 長さ（週、鍵ごとの範囲） | 共通の当週の充足率（全体） | （代理店） | 未充足（2029-W52 にそろえて） | 未充足（期末） | 参考値（美容液／クリーム） | 年齢の最大 |\n|---|---|---:|---|---|---|---:|---:|---:|---:|---|---:|")
summ = {}
for e in ES:
    for a in AS:
        m = M[(e, a)]
        rows, c = m["rows"], common(m["rows"])
        iv = [interval(rows, s, r) for s in SKUS for r in DIST]
        iv = [x for x in iv if x]
        row = {"q3": sumr(rows, "q3"), "from": min((x["from"] for x in iv), key=K), "to": max((x["to"] for x in iv), key=K),
               "span": [min(x["span"] for x in iv), max(x["span"] for x in iv)],
               "rate_all": sumr(c, "on_time") / sumr(c, "q1") * 100, "rate_dist": sumr(c, "on_time", d) / sumr(c, "q1", d) * 100,
               "q5_w52": sumr(c, "q2") - sumr(c, "on_time"), "q5_end": sumr(rows, "q5"), "ref": m["ref"], "age": m["age"]["fifo_age_max"]}
        summ[f"{e}|{a}"] = row
        out.append(f"| {e} | {a} | {row['q3']} | {row['from']} | {row['to']} | {row['span'][0]}〜{row['span'][1]} | {row['rate_all']:.2f}% | {row['rate_dist']:.2f}% | {row['q5_w52']} | {row['q5_end']} | {row['ref']['COS_Serum']}／{row['ref']['COS_Cream']} | {row['age']} |")

out.append("\n### H1 減らす区間（鍵ごと）\n\n長さは始まりの週から終わりの週までの週数。減らす週は、その間で ③ が 1 以上の週の数。\n\n| SKU・チャネル | 期間 | 規則 | 始まり | 終わり | 長さ | 減らす週 | ③ | 週の最大 |\n|---|---|---|---|---|---:|---:|---:|---:|")
h1 = {}
for s in SKUS:
    for reg in DIST:
        for a in AS:
            for e in ES:
                x = interval(M[(e, a)]["rows"], s, reg)
                h1[f"{s}|{reg}|{e}|{a}"] = x
                out.append(f"| {LAB[s]} {LAB[reg]} | {e} | {a} | {x['from']} | {x['to']} | {x['span']} | {x['cut_weeks']} | {x['lots']} | {x['max_per_week']} |")

out.append("\n### H2 共通の期間の E0 との差\n\n要求週 2027-W01〜2029-W52 の全鍵。差のある鍵・週の全件は付録 `records/h2_diff.csv`。\n\n| 比べる組 | ② の差がある鍵・週 | 当週の差がある鍵・週 | ② の合計（E0 → E） | 当週の合計（E0 → E） | 差の最初の要求週 | 差の最後の要求週 |\n|---|---:|---:|---|---|---|---|")
h2rows, h2 = [], {}
for a in AS:
    b = {(r["sku_id"], r["region"], r["request_week"]): r for r in common(M[("E0", a)]["rows"])}
    for e in ("E13", "E26"):
        c = {(r["sku_id"], r["region"], r["request_week"]): r for r in common(M[(e, a)]["rows"])}
        assert set(b) == set(c)
        dq2 = [k for k in b if b[k]["q2"] != c[k]["q2"]]
        dot = [k for k in b if b[k]["on_time"] != c[k]["on_time"]]
        for k in sorted(set(dq2) | set(dot), key=lambda k: (k[0], k[1], K(k[2]))):
            h2rows.append([e, a, *k, b[k]["q1"], b[k]["q2"], c[k]["q2"], b[k]["on_time"], c[k]["on_time"]])
        ws = sorted({k[2] for k in set(dq2) | set(dot)}, key=K)
        h2[f"{e}|{a}"] = {"dq2": len(dq2), "dot": len(dot), "same_q2": not dq2, "first": ws[0] if ws else "", "last": ws[-1] if ws else "",
                          "q2_abs_sum": sum(abs(b[k]["q2"] - c[k]["q2"]) for k in b),
                          "q2_up": sum(max(0, c[k]["q2"] - b[k]["q2"]) for k in b), "q2_down": sum(max(0, b[k]["q2"] - c[k]["q2"]) for k in b)}
        out.append(f"| {e} {a} | {len(dq2)} | {len(dot)} | {sum(x['q2'] for x in b.values()):,} → {sum(x['q2'] for x in c.values()):,} | {sum(x['on_time'] for x in b.values()):,} → {sum(x['on_time'] for x in c.values()):,} | {ws[0] if ws else '無し'} | {ws[-1] if ws else '無し'} |")
with open(W + "/h2_diff.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["period", "rule", "sku_id", "region", "request_week", "q1", "q2_E0", "q2_E", "on_time_E0", "on_time_E"])
    w.writerows(h2rows)

out.append("\n### H3 共通の期間の代理店の当週の充足率\n\n率 ＝ 当週 ÷ ①。前半 2027-W01〜2029-W20、後半 2029-W21〜2029-W52。最低は共通の期間の ① が 1 以上の週の最小。延長分は 2030 年の要求週（参考）。\n\n| SKU・チャネル | 規則 | 期間 | 前半 | 後半 | 週の最低 | 延長分 | 延長分の週の最低 |\n|---|---|---|---:|---:|---:|---:|---:|")
h3 = {}
for s in SKUS:
    for reg in DIST:
        for a in AS:
            for e in ES:
                rows = M[(e, a)]["rows"]
                f, l, al, x = rates(rows, s, reg, None, (2029, 20)), rates(rows, s, reg, LATE_FROM, COMMON_END), rates(rows, s, reg, None, COMMON_END), rates(rows, s, reg, (2030, 1), None)
                h3[f"{s}|{reg}|{e}|{a}"] = [f["rate"], l["rate"], al["min"], x and x["rate"], x and x["min"]]
                out.append(f"| {LAB[s]} {LAB[reg]} | {a} | {e} | {f['rate']:.1f}% | {l['rate']:.1f}% | {al['min']:.0f}% | " + (f"{x['rate']:.1f}% | {x['min']:.0f}%" if x else "— | —") + " |")

out.append("\n### H4 未充足・参考値・年齢・作り置き\n\n未充足（W52）＝共通の期間の需要で 2029-W52 までに届かなかった量。前倒し・遅配はどの案も 0。参考値は条件 2 つ（試行の前に出した値）。作り置きは supply point の I の最大。\n\n| 期間 | 規則 | SKU | 未充足（W52） | 未充足（期末） | 参考値（試行の前） | 参考値（試行の後） | 作り置きの最大 | 週 |\n|---|---|---|---:|---:|---:|---:|---:|---|")
for e in ES:
    for a in AS:
        m = M[(e, a)]
        for s in SKUS:
            v = [r for r in m["rows"] if r["sku_id"] == s]
            cv = common(v)
            before = pre["refs_before"].get(m["case"], {}).get(s, "前回の報告書")
            out.append(f"| {e} | {a} | {LAB[s]} | {sumr(cv, 'q2') - sumr(cv, 'on_time')} | {sumr(v, 'q5')} | {before} | {m['ref'][s]} | {m['stock'][s]['max']} | {m['stock'][s]['week']} |")
out.append("\n年齢（全体）\n\n| 期間 | 規則 | 納品 lot | 年齢の最大 | 52 週超 | Lot_ID の滞留の最大 | 滞留 52 週超 | 代理店の供給 0 の最長の連続 |\n|---|---|---:|---:|---:|---:|---:|---:|")
for e in ES:
    for a in AS:
        m = M[(e, a)]
        x = m["age"]
        z = max(int(s["longest_zero_run"]) for s in m["supply"] if s["region"] in DIST)
        out.append(f"| {e} | {a} | {x['deliveries']} | {x['fifo_age_max']} | {x['over_max_age']} | {x['lot_dwell_max']} | {x['lot_dwell_over_max_age']} | {z} |")

out.append("\n### H5 外す量（③）\n\n| 期間 | 規則 | SKU | ① | ② | ③ | 手計算の目安 | 〜2028 | 2029-W01〜W20 | 2029-W21〜W52 | 2030 |\n|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
h5 = {}
for e in ES:
    for a in AS:
        for s in SKUS:
            v = [r for r in M[(e, a)]["rows"] if r["sku_id"] == s]
            b = Counter()
            for r in v:
                b[bucket(r["request_week"])] += r["q3"]
            hand = pre["quota"][e]["cut_hand"][s] if e != "E0" else {"COS_Serum": 104, "COS_Cream": 88}[s]
            h5[f"{e}|{a}|{s}"] = dict(b)
            out.append(f"| {e} | {a} | {LAB[s]} | {sumr(v, 'q1'):,} | {sumr(v, 'q2'):,} | {sumr(v, 'q3')} | {hand} | {b['〜2028']} | {b['2029-W01〜W20']} | {b['2029-W21〜W52']} | {b['2030']} |")
out.append("\n数量枠の内訳（使える週 × 良品の平準化の上限 ＝ 供給の対象の合計）\n\n| 期間 | SKU | 最初の週 | 最後の週 | 使える週 | 上限 | 供給の対象 | 除いた週（頭） | 除いた週（末） |\n|---|---|---|---|---:|---:|---:|---|---|")
for e in ES:
    q = pre["B1"] if e == "E0" else pre["quota"][e]["usable"]
    for s in SKUS:
        x = q[s]
        out.append(f"| {e} | {LAB[s]} | {x['first_week']} | {x['last_week']} | {x['usable_weeks']} | {x['good_cap_values'][0]} | {x['supply_total']:,} | {'、'.join(x['excluded_head'])} | {x['excluded_tail'][0]}〜{x['excluded_tail'][-1]} |")
out.append("\n鍵ごとの数量枠（lot）\n\n| SKU・チャネル | ① E0 | ② E0 | ① E13 | ② E13 | ① E26 | ② E26 |\n|---|---:|---:|---:|---:|---:|---:|")
for s in SKUS:
    for reg in REGS:
        c = []
        for e in ES:
            v = [r for r in M[(e, "A3")]["rows"] if r["sku_id"] == s and r["region"] == reg]
            c += [f"{sumr(v, 'q1'):,}", f"{sumr(v, 'q2'):,}"]
        out.append(f"| {LAB[s]} {LAB[reg]} | " + " | ".join(c) + " |")

out.append("\n### H6 評価の額（円）\n\n式：共通の期間 ＝ Σ 共通の要求週の ④ × 24 × 単位の貢献利益 − 213,719,220。延ばした全体 ＝ Σ 全要求週の ④ × 24 × 単位の貢献利益 −（213,719,220 ＋ 延ばした週の直営店の売上 × 45％ ＋ 公式 EC の売上 × 10％）。単価は P2-a と同じ。\n\n| 期間 | 規則 | 共通の期間 | E0 との差 | 延ばした全体の固定費の相当額 | 延ばした全体 |\n|---|---|---:|---:|---:|---:|")
for e in ES:
    for a in AS:
        m = M[(e, a)]
        out.append(f"| {e} | {a} | {m['eval_common']:,.0f} | {m['eval_common'] - M[('E0', a)]['eval_common']:+,.0f} | {m['fixed_all']:,.0f} | {m['eval_all']:,.0f} |")

with open(W + "/t2_all.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["period", "rule", "sku_id", "region", "request_week", "q1", "q2", "q3", "on_time", "early", "late", "q5", "reason_code"])
    for (e, a), m in M.items():
        for r in m["rows"]:
            w.writerow([e, a, r["sku_id"], r["region"], r["request_week"], r["q1"], r["q2"], r["q3"], r["on_time"], r["early"], r["late"], r["q5"], r["reason_code"]])
open(W + "/report_tables.md", "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
dump = {"checks": chk, "summary": summ, "h1": h1, "h2": h2, "h3": h3, "h5": h5,
        "eval": {f"{e}|{a}": {"common": M[(e, a)]["eval_common"], "all": M[(e, a)]["eval_all"], "fixed_all": M[(e, a)]["fixed_all"]} for e, a in M},
        "stock": {f"{e}|{a}": M[(e, a)]["stock"] for e, a in M}}
json.dump(dump, open(W + "/measure.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(open(W + "/report_tables.md", encoding="utf-8").read())
print(json.dumps(chk, ensure_ascii=False, default=str)[:3500])
print(json.dumps(h2, ensure_ascii=False))
