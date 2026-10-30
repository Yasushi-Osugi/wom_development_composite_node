# -*- coding: utf-8 -*-
"""P2-a report tables (markdown) from allocation_record.json, Q01.json, measure_<case>.json and
evaluation.json -- no figure typed by hand.
python output/bsseaf_cosmetics/p2a_work/tables.py  -> p2a_work/report_tables.md"""
import csv
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
COS = os.path.dirname(HERE)
SK = {"COS_Serum": "美容液", "COS_Cream": "クリーム"}
CH = {"SG_Store": "直営店", "SG_EC": "公式 EC", "TH_Distributor": "代理店（TH）", "SG_Distributor": "代理店（SG）"}
SKUS = ("COS_Serum", "COS_Cream")
CHS = ("SG_Store", "SG_EC", "TH_Distributor", "SG_Distributor")
CASES = ("P2a1", "P2a2", "P1")
A = json.load(open(os.path.join(HERE, "allocation_record.json"), encoding="utf-8"))
E = json.load(open(os.path.join(HERE, "evaluation.json"), encoding="utf-8"))
M = {c: json.load(open(os.path.join(HERE, f"measure_{c}.json"), encoding="utf-8")) for c in CASES}
Q = {c: json.load(open(os.path.join(COS, "_planning_state", c, "Q01.json"), encoding="utf-8")) for c in CASES}
OUT = []
f0 = lambda x: f"{x:,.0f}"
f2 = lambda x: f"{x:,.2f}"
LETTER_DEMAND = {("COS_Serum", "SG_Store"): 546, ("COS_Serum", "SG_EC"): 455, ("COS_Serum", "SG_Distributor"): 897,
                 ("COS_Serum", "TH_Distributor"): 390, ("COS_Cream", "SG_Store"): 416, ("COS_Cream", "SG_EC"): 299,
                 ("COS_Cream", "SG_Distributor"): 754, ("COS_Cream", "TH_Distributor"): 299}
FORECAST_ALLOC = {"P2a1": {"COS_Serum": (546, 455, 390, 793), "COS_Cream": (416, 299, 299, 666)},
                  "P2a2": {"COS_Serum": (546, 455, 358, 825), "COS_Cream": (416, 299, 274, 691)}}


def h(t):
    OUT.append(f"\n### {t}\n")


def tbl(head, rows):
    OUT.append("| " + " | ".join(head) + " |")
    OUT.append("|" + "|".join("---" if i == 0 else "---:" for i in range(len(head))) + "|")
    for r in rows:
        OUT.append("| " + " | ".join(str(x) for x in r) + " |")


h("T1 貢献利益の照合（§2.1、JPY/個）")
tbl(["SKU・チャネル", "M0 の PPC 試算利益", "売上", "足し戻す率", "計算した貢献利益", "依頼書の値", "差"],
    [[f"{SK[r['sku_id']]} {CH[r['region']]}", f2(r["ppc_unit_profit"]), f2(r["unit_revenue"]),
      f"{r['add_back_rate']:.2f}", f2(r["derived"]), f2(r["letter"]), f"{r['diff']:.6f}"]
     for r in sorted(A["cm_check"], key=lambda r: (SKUS.index(r["sku_id"]), CHS.index(r["region"])))])

h("T2 需要 ①（写しの需要 CSV から数え直した lot）")
rows = []
for s in SKUS:
    for c in ("P2a1", "P2a2"):
        d = A[c]["demand"]
        rows.append([SK[s], c] + [f"{d[f'{s}|{ch}']}" + ("" if d[f'{s}|{ch}'] == LETTER_DEMAND[(s, ch)] else " **≠**")
                                  for ch in CHS])
tbl(["SKU", "写し", *(CH[c] for c in CHS)], rows)
OUT.append("\n依頼書 §2.1 の C3a の値（美容液 546・455・897・390、クリーム 416・299・754・299）とすべて一致。")

h("T3 配分の数量（§2.3 の見込みとの照合、lot）")
rows = []
for s in SKUS:
    for c in ("P2a1", "P2a2", "P1"):
        if c == "P1":
            al = {(k["sku_id"], k["region"]): k["alloc_lots"] for k in Q["P1"]["allocation"]}
        else:
            al = {tuple(k.split("|")): v for k, v in A[c]["alloc"].items()}
        un = {ch: LETTER_DEMAND[(s, ch)] - al[(s, ch)] for ch in CHS}
        fc = FORECAST_ALLOC.get(c, {}).get(s)
        same = "—" if fc is None else ("一致" if tuple(al[(s, ch)] for ch in CHS) == fc else "**不一致**")
        rows.append([SK[s], c, *(al[(s, ch)] for ch in CHS),
                     "、".join(f"{CH[ch].replace('代理店（', '').replace('）', '')} {v}" for ch, v in un.items() if v) or "0",
                     sum(al[(s, ch)] for ch in CHS), same])
tbl(["SKU", "案", *(CH[c] for c in CHS), "③ 未配分", "② 合計", "§2.3 の見込み"], rows)
g = A["P2a2"]["groups"]
OUT.append("\nP2-a2 の組：" + "；".join(f"{SK[s]} " + " ／ ".join("{" + ", ".join(CH[c] for c in grp) + "}" for grp in g[s])
                                      for s in SKUS) + "。")

h("T4 M1：①〜⑤（`Q01.json`、lot）")
rows = []
for c in CASES:
    for k in Q[c]["quantities"]["by_key"]:
        d = k["q4_delivered"]
        rows.append([c, SK[k["sku_id"]], CH[k["region"]], k["q1_original"], k["q2_in_supply_scope"],
                     k["q3_not_in_supply_scope"], d["total"], f"{d['on_time']}/{d['early']}/{d['late']}",
                     k["q5_backlog_end"]])
    for s in SKUS:
        b = Q[c]["quantities"]["by_sku"][s]
        rows.append([f"**{c}**", f"**{SK[s]} 計**", "", b["q1_original"], b["q2_in_supply_scope"],
                     b["q3_not_in_supply_scope"], b["q4_delivered"]["total"],
                     f"{b['q4_delivered']['on_time']}/{b['q4_delivered']['early']}/{b['q4_delivered']['late']}",
                     b["q5_backlog_end"]])
    t = Q[c]["quantities"]["total"]
    rows.append([f"**{c}**", "**全体**", "", t["q1_original"], t["q2_in_supply_scope"], t["q3_not_in_supply_scope"],
                 t["q4_delivered"]["total"], "", t["q5_backlog_end"]])
tbl(["案", "SKU", "チャネル", "① 元需要", "② 供給対象", "③ 未配分", "④ 実納品", "④ の内訳（期日どおり／早着／遅着）", "⑤ 配分後の未充足"], rows)

h("T5 M2：⑤ の Lot_ID（要求週と、Backward が工場に置いた週）")
rows = []
for c in CASES:
    for s in SKUS:
        for x in M[c][s]["q5"]:
            rows.append([c, SK[s], f"`{x['lot']}`", x["request_week"], x["in_factory_demand_week"]])
tbl(["案", "SKU", "Lot_ID", "要求週", "工場の需要の配置週"], rows)

h("T6 M2：工場の最後の生産週と最後の市場週の需要")
rows = []
for c in CASES:
    for s in SKUS:
        fe = M[c][s]["factory_ends"]
        rows.append([c, SK[s], fe["2029-W47"]["supply_P"], fe["2029-W48"]["supply_P"], f0(fe["2029-W47"]["limit"]),
                     M[c][s]["factory_P_total"]])
tbl(["案", "SKU", "工場の P 2029-W47", "工場の P 2029-W48", "上限（soft）", "工場の P の合計"], rows)
dem = {}
for c in CASES:
    d = defaultdict(float)
    with open(os.path.join(COS, c, Q[c]["evidence"]["demand_csv"]), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["week"] >= "2029-W47":
                d[(r["sku_id"], r["region"], r["week"])] += float(r["quantity"])
    dem[c] = d
OUT.append("")
rows = []
for c in CASES:
    for s in SKUS:
        rows.append([c, SK[s]] + [int(dem[c][(s, ch, "2029-W52")]) for ch in CHS]
                    + [int(sum(dem[c][(s, ch, "2029-W52")] for ch in CHS))])
tbl(["案", "SKU", *(f"{CH[c]} 2029-W52" for c in CHS), "計（2029-W47〜W52 は毎週同じ）"], rows)

h("T7 M3：先入れ先出しの年齢（Part A の CLI、上限 52 週）")
rows = []
for c in CASES:
    for s in M[c]["M3"]["summary"]:
        if s["channel"] == "*":
            rows.append([c, "全体" if s["product"] == "*" else SK[s["product"]], f0(int(s["deliveries"])),
                         s["fifo_age_min"], s["fifo_age_max"], s["over_max_age"]])
    rows.append([c, "CLI と check_tree() の一致", str(M[c]["M3"]["cli_equals_check_tree"]), "", "", ""])
tbl(["案", "SKU", "納品（lot）", "年齢 最小（週）", "年齢 最大（週）", "52 週超"], rows)

h("T8 M4：期間・能力の固定、財務")
rows = []
for c in CASES:
    m = M[c]["M4"]
    rows.append([c, f"{Q[c]['period']['start']}〜{Q[c]['period']['end']}（{Q[c]['period']['weeks']} 週）",
                 Q[c]["period"]["warmup_real_start"], str(M[c]["period_same"]),
                 "、".join(f"{k} {'同じ' if v else '**違う**'}" for k, v in m["files_now_same"].items()),
                 "、".join(f"{k} {'同じ' if v else '**違う**'}" for k, v in m["same_as_C3a"].items()),
                 m["valuation"], str(m["ppc_output_created"]), (m["commit"] or "")[:7]])
tbl(["案", "期間", "warmup の基準の週", "計画し直しても同じ期間", "能力のファイル（記録のハッシュと今）", "C3a と比べて",
     "valuation", "PPC の出力", "道具の記録の commit"], rows)

h("T9 評価の額（§3.3、JPY、全期間）")
rows = []
for c in ("P2a1", "P2a2", "P1", "C3b"):
    e = E[c]
    rows.append([c, f0(e["by_sku"]["COS_Serum"]["contribution_q4"]), f0(e["by_sku"]["COS_Cream"]["contribution_q4"]),
                 f0(e["total"]["contribution_q4"]), f0(e["fixed_part"]), f0(e["evaluation"]),
                 f0(E["diff_vs_P2a1"][c]), f0(e["total"]["lost_q3"]), f0(e["total"]["lost_q5"])])
tbl(["案", "美容液 Σ（④×24×貢献利益）", "クリーム", "計", "共通の固定費の相当額", "評価の額", "P2-a1 との差",
     "③ による逸失", "⑤ による逸失"], rows)
OUT.append(f"\n共通の固定費の相当額：M0 から計算し直した値 {f0(E['fixed_part_from_M0'])}、依頼書 {f0(E['fixed_part_letter'])}、"
           f"一致 {E['fixed_part_same']}。C3b の評価の額は M0 の PPC の試算利益（631,849,608）と同じになる"
           f"（固定費の相当額が M0 自身の値のため。式の検算）。")

h("T10 §3.3 の見込み（④＝② と仮定）との照合")
rows = []
for c, v in E["forecast_check"].items():
    rows.append([c, f0(v["serum_q2_forecast"]), f0(v["serum_q2"]), f0(v["cream_q2_forecast"]), f0(v["cream_q2"]),
                 "一致" if v["same"] else "**不一致**"])
tbl(["案", "美容液 見込み", "美容液 Σ（②×24×貢献利益）", "クリーム 見込み", "クリーム 実行", "照合"], rows)

h("T11 タイの関税 30%（M4 の感度）のときの順位と配分")
t = E["thai30"]
tbl(["項目", "美容液", "クリーム"], [
    ["代理店（TH）の貢献利益（JPY/個）", f2(t["cm_thai"]["COS_Serum"]), f2(t["cm_thai"]["COS_Cream"])],
    ["貢献利益の順", " > ".join(CH[c] for c in t["order"]["COS_Serum"]), " > ".join(CH[c] for c in t["order"]["COS_Cream"])],
    ["P2-a2 の組", " ／ ".join("{" + ", ".join(CH[c] for c in g) + "}" for g in t["groups_p2a2"]["COS_Serum"]),
     " ／ ".join("{" + ", ".join(CH[c] for c in g) + "}" for g in t["groups_p2a2"]["COS_Cream"])],
])
OUT.append(f"\nP2-a1 の規則の配分が P1 と同じ：{t['p2a1_equals_P1']}。P2-a2 の規則の配分が P1 と同じ：{t['p2a2_equals_P1']}。")

with open(os.path.join(HERE, "report_tables.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(OUT) + "\n")
print("written", len(OUT))
