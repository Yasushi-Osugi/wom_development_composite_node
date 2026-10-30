# -*- coding: utf-8 -*-
"""Step 5: write the report's number tables (markdown) from checks_ppc.json / checks_vc.json,
so no figure in the report is typed by hand.
python output/bsseaf_cosmetics/money_m0_work/step5_tables.py  -> money_m0_work/report_tables.md"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m0_common as C   # noqa: E402

P = json.load(open(os.path.join(C.HERE, "checks_ppc.json"), encoding="utf-8"))
V = json.load(open(os.path.join(C.HERE, "checks_vc.json"), encoding="utf-8"))
B = json.load(open(os.path.join(C.HERE, "base", "base_record.json"), encoding="utf-8"))
G = json.load(open(os.path.join(C.HERE, "gen_record.json"), encoding="utf-8"))
OUT = []
CH = {"SG_Store": "直営店", "SG_EC": "公式 EC", "SG_Distributor": "代理店（SG）", "TH_Distributor": "代理店（TH）"}
SK = {"COS_Serum": "美容液", "COS_Cream": "クリーム"}
ORDER = [(s, c) for s in C.SKUS for c in C.LEAVES]


def f0(x):
    return f"{x:,.0f}"


def f2(x):
    return f"{x:,.2f}"


def ok(b):
    return "合格" if b else "**不合格**"


def h(t):
    OUT.append(f"\n### {t}\n")


def tbl(head, rows):
    OUT.append("| " + " | ".join(head) + " |")
    OUT.append("|" + "|".join("---" if i == 0 else "---:" for i in range(len(head))) + "|")
    for r in rows:
        OUT.append("| " + " | ".join(str(x) for x in r) + " |")


h("T1 受入条件 A1〜A8（PPC）")
rows = []
for a in ("A1", "A2", "A3", "A4", "A5", "A6"):
    rows.append([a] + [ok(P[c][a]["ok"]) for c in ("M0", "M0t", "M0a")])
rows.append(["Lot_ID 数×24 ＝ PPC の qty（SKU×チャネル×週）"] + [
    f"{ok(P[c]['ship_vs_ppc_qty']['ok'])}（{P[c]['ship_vs_ppc_qty']['records']} 記録）" for c in ("M0", "M0t", "M0a")])
rows.append(["§4.2 M0t と M0 の差", "—", ok(P["M0t_vs_M0"]["ok"]), "—"])
rows.append(["A7（M0a の未充足と売上差）", "—", "—", ok(P["A7"]["ok"])])
rows.append(["A8（未設定の金額規則が無い）"] + [ok(P["A8"][c]["ok"]) for c in ("M0", "M0t", "M0a")])
rows.append(["A4 の合成入力（1 個と 24 個）", ok(P["unit_check"]["ok"]), "—", "—"])
tbl(["条件", "M0", "M0t", "M0a"], rows)

h("T2 実行の条件（3 ケース共通の確認）")
tbl(["項目", "M0", "M0t", "M0a"], [
    ["元", "C3b", "M0（C3b）", "C3a"],
    ["期間"] + [f"{P[c]['period']['start']} から {P[c]['period']['weeks']} 週" for c in ("M0", "M0t", "M0a")],
    ["プラグイン（観測用の Capture を除く）"] + [", ".join(x for x in P[c]["config"]["plugins"] if x != "Capture")
                                     for c in ("M0", "M0t", "M0a")],
    ["数量の入力が元と同じ（sha256）"] + [str(G[c]["quantity_inputs_equal_to_source"]) for c in ("M0", "M0t", "M0a")],
    ["実行で入力が変わらなかった"] + [str(P[c]["inputs_unchanged_by_run"]) for c in ("M0", "M0t", "M0a")],
    ["valuation_status"] + [P[c]["A1"]["valuation_status"] for c in ("M0", "M0t", "M0a")],
    ["規則の出どころ"] + ["9 ファイルとも model" if P[c]["A2"]["ok"] else "要確認" for c in ("M0", "M0t", "M0a")],
])

h("T3 1 個当たり（JPY）：§4.1 の期待値と PPC の実行値")
rows = []
for s, c in ORDER:
    for case in ("M0", "M0t"):
        r = next(x for x in P[case]["A3"]["rows"] if x["product_id"] == s and x["channel"] == c)
        if case == "M0t" and c != "TH_Distributor":
            continue
        rows.append([f"{SK[s]} {CH[c]}" + ("（M0t）" if case == "M0t" else ""),
                     f2(r["expected"][0]), f2(r["actual"][0]), f2(r["expected"][1]), f2(r["actual"][1]),
                     f2(r["expected"][2]), f2(r["actual"][2]), f"{r['max_abs_diff']:.6f}"])
tbl(["SKU・チャネル", "売上 期待", "売上 実行", "費用 期待", "費用 実行", "利益 期待", "利益 実行", "最大の差"], rows)
OUT.append("\nM0a の 8 行は M0 と同じ単価（A3 合格）。")

h("T4 1 個当たりの費用の内訳（M0、JPY）")
rows = []
for s, c in ORDER:
    r = next(x for x in P["M0"]["sku_channel"] if x["product_id"] == s and x["channel"] == c)
    rows.append([f"{SK[s]} {CH[c]}", f2(r["unit_material"]), f2(r["unit_processing"]), f2(r["unit_freight"]),
                 f2(r["unit_node_cost"]), f2(r["unit_tariff"]), f2(r["unit_channel_cost"]), f2(r["unit_cost"])])
tbl(["SKU・チャネル", "原料", "加工", "物理区間の運賃", "ノード費用（倉庫・DC）", "関税", "販売費（チャネル）", "計"], rows)

for case in ("M0", "M0t", "M0a"):
    h(f"T5-{case} SKU × チャネルの合計（全期間、JPY）")
    rows = []
    for s, c in ORDER:
        r = next(x for x in P[case]["sku_channel"] if x["product_id"] == s and x["channel"] == c)
        rows.append([f"{SK[s]} {CH[c]}", f0(r["lots"]), f0(r["units"]), f0(r["total_revenue"]),
                     f0(r["total_cost"]), f0(r["total_profit"])])
    a5 = P[case]["A5"]
    rows.append(["**計（台帳）**", f0(sum(x["lots"] for x in P[case]["sku_channel"])),
                 f0(sum(x["units"] for x in P[case]["sku_channel"])),
                 f0(a5["ledger"]["revenue"]), f0(a5["ledger"]["cost"]), f0(a5["ledger"]["profit"])])
    rows.append(["**全体 KPI**", "—", f0(a5["total_qty_units"]), f0(a5["kpi"]["revenue"]),
                 f0(a5["kpi"]["cost"]), f0(a5["kpi"]["profit"])])
    tbl(["SKU・チャネル", "lot", "個", "売上", "費用", "試算利益"], rows)
    bc = a5["ledger_by_category"]
    OUT.append("\n費用の内訳（台帳、JPY）：" + "、".join(
        f"{k} {f0(v)}" for k, v in (("原料", bc["material"]), ("加工", bc["processing"]),
                                    ("物理区間の運賃", bc["freight"]), ("ノード費用", bc["node_cost"]),
                                    ("関税", bc["tariff"]), ("販売費", bc["channel_cost"]))) + "。")

h("T6 費用の内訳の金額（M0、全期間、JPY）")
m0 = {(x["product_id"], x["channel"]): x for x in P["M0"]["sku_channel"]}
store35 = {s: m0[(s, "SG_Store")]["total_revenue"] * 0.35 for s in C.SKUS}
store10 = {s: m0[(s, "SG_Store")]["total_revenue"] * 0.10 for s in C.SKUS}
ec_ship = {s: m0[(s, "SG_EC")]["units"] * 3.0 * 115 for s in C.SKUS}
g12 = {(r["product_id"], r["node"], r["cost_type"]): r["ppc_jpy"] for r in V["M0"]["G1_G2"]}
mdf = {(s, c): g12[(s, c, "marketing_cost")] for s in C.SKUS for c in ("SG_Distributor", "TH_Distributor")}
tbl(["項目", "美容液", "クリーム", "計"], [
    ["直営店 sga 45%（PPC）"] + [f0(g12[(s, "SG_Store", "sga_cost")]) for s in C.SKUS]
    + [f0(sum(g12[(s, "SG_Store", "sga_cost")] for s in C.SKUS))],
    ["　うち店舗運営費 35%（固定費の近似、M5）"] + [f0(store35[s]) for s in C.SKUS] + [f0(sum(store35.values()))],
    ["　うち販社販管費 10%"] + [f0(store10[s]) for s in C.SKUS] + [f0(sum(store10.values()))],
    ["EC の配送梱包 SGD 3/個（sga_cost に含む）"] + [f0(ec_ship[s]) for s in C.SKUS] + [f0(sum(ec_ship.values()))],
    ["MDF（SG 代理店、負担候補 シンガポール販社）"] + [f0(mdf[(s, "SG_Distributor")]) for s in C.SKUS]
    + [f0(sum(mdf[(s, "SG_Distributor")] for s in C.SKUS))],
    ["MDF（TH 代理店、負担候補 日本本社）"] + [f0(mdf[(s, "TH_Distributor")]) for s in C.SKUS]
    + [f0(sum(mdf[(s, "TH_Distributor")] for s in C.SKUS))],
])
OUT.append("\n35% と 10% の内訳は、PPC の 1 行（45%）を報告で分けた計算（売上 × 0.35 / 0.10）。PPC はこの内訳を持たない。")

h("T7 M0t と M0（タイ関税 30%）")
t = P["M0t_vs_M0"]
tbl(["項目", "美容液", "クリーム", "計"], [
    ["タイの実出荷（個）"] + [f0(t["thai_units"][s]) for s in C.SKUS] + [f0(sum(t["thai_units"].values()))],
    ["関税（JPY/個、PPC）"] + [f2(t["tariff_per_unit"][s]) for s in C.SKUS] + ["—"],
    ["利益の減少 期待（個×1,800／1,500）", "—", "—", f0(t["expected_profit_drop"])],
    ["利益の減少 実行（M0 − M0t の全体 KPI）", "—", "—", f0(t["profit_drop"])],
])

h("T8 M0a（C3a の配分後）")
a7 = P["A7"]
tbl(["項目", "期待", "実行"], [
    ["元需要①（lot）", "4,056", f0(a7["demand_lots"])],
    ["実出荷で満たした需要④（lot）", "3,864", f0(a7["ship_lots"])],
    ["期末未充足⑤（lot、要求 ID − 実出荷 ID）", "192（タイ 美容液 104・クリーム 88）",
     "、".join(f"{SK[p]} {sum(d.values())}" for p, d in a7["unmet_lots"].items())],
    ["M0 の未充足（lot）", "0", f0(a7["M0_unmet_lots"])],
    ["売上の対象（個、market_revenue の qty）", "92,736", f0(a7["revenue_units_M0a"])],
    ["M0 との売上差 美容液（JPY）", f0(a7["expected_diff_by_sku"]["COS_Serum"]), f0(a7["revenue_diff_by_sku"]["COS_Serum"])],
    ["M0 との売上差 クリーム（JPY）", f0(a7["expected_diff_by_sku"]["COS_Cream"]), f0(a7["revenue_diff_by_sku"]["COS_Cream"])],
    ["M0 との売上差 計（JPY）", f0(a7["expected_total"]), f0(a7["revenue_diff_total"])],
    ["前提：元需要が M0 と同じ", "True", str(a7["demand_same_as_M0"])],
    ["前提：タイ以外の実出荷（SKU×チャネル×週）が M0 と同じ", "True", str(a7["non_thai_shipments_same_as_M0"])],
    ["前提：実出荷の差（M0 − M0a、lot）", "192", f0(a7["ship_lots_M0_minus_M0a"])],
])
OUT.append("\n代表 Lot：")
for p, r in a7["representative"].items():
    OUT.append(f"- {SK[p]} `{r['lot_id']}`：需要週 {r['demand_week']}。M0 では {r['M0_ship_week']} に実出荷され、"
               f"PPC の週次記録 `{r['M0_ppc_record']}`（qty {r['M0_ppc_record_qty']}）に入る。M0a では実出荷されず、"
               f"同じ週次記録の qty は {r['M0a_ppc_record_qty'] if r['M0a_ppc_record_qty'] is not None else '記録なし（その週の実出荷 0）'}。")

h("T9 A8 金額規則の行と参照（M0）")
rows = []
for r in P["A8_rows_M0"]:
    rate = r["rate"] if r["file"] != "ppc_tariff_rule.csv" else r["amount"]
    amt = r["amount"] if r["file"] != "ppc_tariff_rule.csv" else ""
    state = ("価格あり（費用ではない。関税の課税価格に使う）" if r["file"] == "ppc_transfer_price_rule.csv"
             else r["state"])
    rows.append([r["file"].replace(".csv", ""), r["key"].replace("|", " × "), r["cost_type"], r["basis"], rate, amt,
                 r["currency"], f0(r["lookups"]), state])
tbl(["ファイル", "ノード・区間 × 製品", "費目（関税は課税価格の基準）", "basis", "率", "1 個当たりの額・価格",
     "通貨", "参照回数", "状態"], rows)
OUT.append("\nM0t の関税の行（M0 と違うのはタイの 2 行だけ）：" + "、".join(
    f"{r['key'].replace('|', ' × ')} 率 {r['amount']}（参照 {f0(r['lookups'])}、{r['state']}）"
    for r in P["A8_rows_M0t_tariff"] if "DC_TH" in r["key"] and "WH_JP" in r["key"]) + "。")
OUT.append("\n参照したのに行が無かった費用の規則：" + ("なし" if not P["A8"]["M0"]["lookups_without_rule"] else
           str(P["A8"]["M0"]["lookups_without_rule"])) + "。利益ゾーンの 2 ファイルは見出しだけ（依頼書 §3.1 で可）なので、"
           f"利益ゾーンの参照 {len(P['A8']['M0']['profit_zone_lookups_without_row'])} 組合せは既定の区分（OPERATION_NODE_COST_BASE）になった。"
           "仮想ノード（SP_COS_*）には行を置いておらず、計算も参照しない。")

h("T10 Value Chain の実行（観測）")
tbl(["項目", "M0", "M0t", "M0a"], [
    ["実行", *(V[c]["run"] for c in ("M0", "M0t", "M0a"))],
    ["計画が PPC 試行と同じ（PPC 台帳の sha256）", *(str(V[c]["same_plan_as_ppc_trial(ppc ledger sha)"]) for c in ("M0", "M0t", "M0a"))],
    ["消費者への販売の件数 ＝ 実出荷", *(str(V[c]["consumer_sales_equal_actual_ships"]) for c in ("M0", "M0t", "M0a"))],
    ["保存の検査（conservation）", *(f"{V[c]['conservation_ok']}（{V[c]['conservation_rows']} 行）" for c in ("M0", "M0t", "M0a"))],
    ["価格の欠け・未評価の明細", *(f"{V[c]['missing_price_rows']}・{V[c]['unvalued_lines']}" for c in ("M0", "M0t", "M0a"))],
    ["為替の代用（最初の週・未評価）", *(f"{V[c]['fx_first_week_rate_uses']}・{V[c]['fx_unvalued_uses']}" for c in ("M0", "M0t", "M0a"))],
    ["issues", *("<br>".join(f"{k}：{v}" for k, v in V[c]["issues"].items()) for c in ("M0", "M0t", "M0a"))],
    ["PPC との比較", *(V[c]["ppc_comparison"] for c in ("M0", "M0t", "M0a"))],
])
for c in ("M0", "M0t", "M0a"):
    rows = [[r["item"], f0(r["ppc"]), f0(r["ledger_v3"]), f0(r["difference_ledger_minus_ppc"])]
            for r in V[c]["ppc_comparison_rows"] if not r["item"].startswith("売上 COS")]
    h(f"T11-{c} Value Chain の PPC との比較（vc_ppc_comparison.csv、全期間、JPY）")
    tbl(["項目", "PPC", "台帳 V3", "台帳 − PPC"], rows)

h("T12 G1・G2：Value Chain に入らない販売費（M0、全期間、JPY）")
rows = [[r["G"], SK[r["product_id"]], r["node"], r["cost_type"], f0(r["ppc_jpy"]), f0(r["vc_jpy"]),
         f0(r["not_in_vc_jpy"]), r["vc_issue_count"], r["payer_candidate"]]
        for r in sorted(V["M0"]["G1_G2"], key=lambda r: (r["G"], r["node"], r["cost_type"], r["product_id"]))]
tbl(["G", "SKU", "ノード", "費目", "PPC", "Value Chain", "入らない額", "issues（両 SKU の lot 数）", "負担の候補"], rows)
for c in ("M0", "M0t", "M0a"):
    g1 = sum(r["not_in_vc_jpy"] for r in V[c]["G1_G2"] if r["G"] == "G1")
    g2 = sum(r["not_in_vc_jpy"] for r in V[c]["G1_G2"] if r["G"] == "G2")
    prow = next(r for r in V[c]["ppc_comparison_rows"] if r["item"].startswith("利益 合計"))
    OUT.append(f"\n{c}：G1 {f0(g1)} ＋ G2 {f0(g2)} ＝ {f0(g1 + g2)}。Value Chain と PPC の利益の差（全期間）"
               f" {f0(prow['difference_ledger_minus_ppc'])}。")

h("T13 G3：代理店の売上の週（代表 Lot、M0）")
rows = []
for k, r in V["M0"]["G3_representative"].items():
    s, leaf = k.split(" ")
    rows.append([f"{SK[s]} {CH[leaf]}", f"`{r['lot_id']}`", r["dc_ship_week"], r["leaf_receipt_week(P)"],
                 r["leaf_actual_ship_week(S)"],
                 f"{r['vc_revenue_week'][0]}（{r['vc_revenue_node'][0]}、{r['vc_revenue_currency'][0]} {r['vc_revenue_price_local'][0]:g}）",
                 f"{r['vc_observation_week'][0]}（{r['vc_observation_price_local'][0]:g}）",
                 f"{r['ppc_revenue_week']}（{r['ppc_price_local']:g}）"])
tbl(["SKU・チャネル", "Lot_ID", "DC の出荷週", "代理店の受入週（P）", "代理店 leaf の実出荷週（S）",
     "VC の売上週（計上ノード、単価）", "VC の観測の週（単価）", "PPC の売上週（単価）"], rows)
OUT.append("")
for c in ("M0", "M0t", "M0a"):
    lags = "、".join(f"{SK[x['product_id']]} {CH[x['leaf']]} {x['lots']} lot：{x['lag_weeks_hist']}" for x in V[c]["G3"])
    w = V[c]["G3_weekly"]
    OUT.append(f"- {c}：VC の売上週 − PPC の売上週（週）の分布 {lags}。代理店の売上の全期間の合計 VC {f0(w['total_vc'])} ／ "
               f"PPC {f0(w['total_ppc'])}、週の値が違う週 {w['weeks_with_diff']}、最大の差 {f0(w['max_abs_week_diff'])}。")
u = V["M0a"]["unmet_lots_in_vc"]
OUT.append("- M0a の未充足 Lot：" + "、".join(
    f"{SK[p]} {x['unmet_lots']} lot（Value Chain の出荷の行 {x['vc_shipment_rows']}、売上の明細 {x['vc_revenue_lines']}、例 `{x['example']}`）"
    for p, x in u.items()) + "。")

h("T14 G4：タイの関税の課税価格（M0t）")
rows = [[SK[r["product_id"]], f0(r["units"]), f2(r["ppc_per_unit"]), f2(r["cif_assumption_per_unit"]),
         f2(r["diff_per_unit"]), f0(r["ppc_total"]), f0(r["cif_total"]), f0(r["diff_total"])] for r in V["G4"]["rows"]]
rows.append(["計", f0(sum(r["units"] for r in V["G4"]["rows"])), "", "", "",
             f0(sum(r["ppc_total"] for r in V["G4"]["rows"])), f0(sum(r["cif_total"] for r in V["G4"]["rows"])),
             f0(sum(r["diff_total"] for r in V["G4"]["rows"]))])
tbl(["SKU", "タイの実出荷（個）", "PPC（振替価格×30%）", "CIF の仮定（（振替価格＋70）×30%）", "差/個",
     "PPC 計", "CIF 計", "差 計"], rows)
OUT.append(f"\nValue Chain（M0t）の関税の合計：{f0(V['G4']['vc_M0t_tariff_jpy'])}（明細："
           + "、".join(f"{r['entity']} {r['node']} {r['kind']} {f0(r['amt_hq'])}" for r in V["G4"]["vc_M0t_tariff_by_entity_kind"]
                      if r["amt_hq"]) + "）。")

h("T15 G5：CIF の海上運賃（WH_JP_Released → DC_SG、M0）")
g5 = V["M0"]["G5"]
tbl(["項目", "値"], [
    ["Value Chain の運賃の明細", f"{g5['vc_freight_lines']} 行、法人 {', '.join(g5['vc_entity'])}、種類 {', '.join(g5['vc_kind'])}"],
    ["金額（JPY）", f"{f0(g5['vc_amount_jpy'])}（{f0(g5['units'])} 個 × {f2(g5['per_unit_jpy'])}）"],
    ["報告開始の前の週の末に E_SG の在庫に残る運賃", f"{g5['lots_in_E_SG_stock_end_of_week_before_report']} lot、{f0(g5['jpy_in_E_SG_stock_before_report'])} JPY"],
    ["最後の週の末に E_SG の在庫に残る運賃", f"{g5['lots_in_E_SG_stock_last_week']} lot、{f0(g5['jpy_in_E_SG_stock_last_week'])} JPY"],
])

h("T16 元モデルと写しの数量入力（sha256）")
rows = []
for case in ("C3b", "C3a"):
    for fn, hsh in B[case]["quantity_input_sha256"].items():
        rows.append([case, fn, hsh[:16] + "…",
                     "同じ" if G["M0" if case == "C3b" else "M0a"]["quantity_input_sha256"].get(fn) == hsh else "**違う**"])
tbl(["元", "ファイル", "sha256（先頭 16 桁）", "写し（M0・M0a）"], rows)

with open(os.path.join(C.HERE, "report_tables.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(OUT) + "\n")
print("written", len(OUT), "lines")
