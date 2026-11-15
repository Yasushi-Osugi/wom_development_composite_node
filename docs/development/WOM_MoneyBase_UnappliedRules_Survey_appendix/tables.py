# -*- coding: utf-8 -*-
"""Markdown tables for the report + the final type of every unapplied row (manual judgement, see the report §2)."""
import os
import shutil

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.dirname(os.path.abspath(__file__))
APX = os.path.join(REPO, "docs", "development", "WOM_MoneyBase_UnappliedRules_Survey_appendix")
os.makedirs(APX, exist_ok=True)

s = pd.read_csv(os.path.join(OUT, "summary_by_file.csv"))
u = pd.read_csv(os.path.join(OUT, "unapplied_rows.csv"))
u = u[u.ledger == "PPC"].copy()          # every VC row is applied after the CONSUMER match


def final(r):
    """Final type (Q1), judgement (Q2) and group of each unapplied row."""
    m, f, row = r.model, r.file, r.row
    if m == "smartx-2027-2029" and f in ("ppc_edge_cost_rule.csv", "ppc_tariff_rule.csv"):
        return "a", "引かれるべき（大杉さんの判断どおり）", "G1"
    if m == "smartphone-global-2026-2029":
        if f == "ppc_node_cost_rule.csv" and row.startswith("DC_") and "conversion_cost" in row:
            return "e", "引かれるべき（DC の作業費。今は計上されていない）", "G3"
        if f == "ppc_node_cost_rule.csv" and row.startswith("DC_") and "logistics_cost" in row:
            return "e", "引かない（国際輸送は supply point → 市場の区間で計上済み。足すと二重）", "G3"
        if row.startswith("EMS_A_IN"):
            return "e", "決められない（計画は米州をインド組立から出すが、PPC は中国組立で計上）", "G3"
        return "e", "決められない（EMS の仕入値 450 等に含まれるなら引かない）", "G3"
    if f == "ppc_supplier_cost.csv":
        if m == "smartx-2027-2029":
            return "e", "決められない（原価を完成品の仕入値で持つか、部材の積み上げで持つか）", "G2"
        return "e", "引かない（部材の仕入値＋組立費で同じ額を計上済み。足すと二重）", "G2"
    if f == "ppc_transfer_price_rule.csv":
        return "e", "決められない（今の PPC は製品ごとに最後の工場の移転価格 1 つだけ）", "G4"
    if m == "soysauce-us-2027":
        return "c", "問題なし（このケースは欧州の需要が 0）", "G5"
    if m == "cosmetics-sg-th-2027-2029":
        return "e", "PPC では引かない（同じ SGD 3 を SG_EC の sga_cost で計上。Value Chain は区間で計上し、両者の一致を確かめている）", "G6"
    return r.type, "要確認", "?"


u[["type_final", "q2", "group"]] = u.apply(lambda r: pd.Series(final(r)), axis=1)
u.to_csv(os.path.join(APX, "unapplied_rows.csv"), index=False, encoding="utf-8-sig")
assert not (u.group == "?").any()

# model x type
models = sorted(s.model.unique())
mt = u.groupby(["model", "type_final"]).size().unstack(fill_value=0)
L = ["| モデル | 0 でない行 | 引かれた | 引かれていない | (a) 鍵が合わない | (b) 木に無い | (c) 実出荷が無い | (d) 先に当たる | (e) その他 | 0 の行で引かれていない |",
     "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
tot = s.groupby("model")[["nonzero", "applied", "not_applied", "zero_not_applied"]].sum()
for m in models:
    t = tot.loc[m]
    g = mt.loc[m] if m in mt.index else pd.Series(dtype=int)
    L.append(f"| {m} | {t.nonzero} | {t.applied} | {t.not_applied} | " +
             " | ".join(str(int(g.get(k, 0))) if int(g.get(k, 0)) else "—" for k in ("a", "b", "c", "d", "e")) +
             f" | {t.zero_not_applied or '—'} |")
t = tot.sum()
L.append(f"| **計** | {t.nonzero} | {t.applied} | {t.not_applied} | " +
         " | ".join(str(int(mt[k].sum())) if k in mt and int(mt[k].sum()) else "—" for k in ("a", "b", "c", "d", "e")) +
         f" | {t.zero_not_applied} |")
open(os.path.join(APX, "table_model_x_type.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")

# model x file
L = ["| モデル | 規則のファイル | 出どころ | 行の数 | 0 の行 | 0 でない行 | 引かれた | 引かれていない | 0 の行で引かれていない |",
     "|---|---|---|---:|---:|---:|---:|---:|---:|"]
for r in s.itertuples():
    src = "モデル" if r.source == "model" else r.source.replace("shared:", "共有 ")
    n = r.rows if r.source == "model" else f"{r.rows_for_model}（ファイル全体 {r.rows}）"
    L.append(f"| {r.model} | {r.file} | {src} | {n} | {r.zero} | {r.nonzero} | {r.applied} | "
             f"{'**' + str(r.not_applied) + '**' if r.not_applied else 0} | {r.zero_not_applied} |")
open(os.path.join(APX, "table_model_x_file.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
s.to_csv(os.path.join(APX, "summary_by_file.csv"), index=False, encoding="utf-8-sig")
for f in ("zero_rows_not_applied.csv", "q3_mom_supplier_rows.csv", "smartx_fix_plan.csv",
          "smartx_node_logistics_booked.csv", "smartphone_dc_rows.csv", "amounts.json", "run_all.json",
          "run_all.py", "survey.py", "amounts.py", "tables.py"):
    shutil.copyfile(os.path.join(OUT, f), os.path.join(APX, f))
print(open(os.path.join(APX, "table_model_x_type.md"), encoding="utf-8").read())
print(u.groupby(["group", "model", "file", "type_final", "q2"]).size().to_string())
