# -*- coding: utf-8 -*-
"""RequestLetter_MoneyBase_Smartx_CostFix C + D on data/sample/smartx-2027-2029 (one-off data change, recorded).

C: ppc_cost_basis.csv (4 products finished_goods at their terminal assembly plant); remove the rows that the
   purchase price now contains (parts suppliers, Taiwan fab supplier rows, fab + assembly node costs, fab transfer
   prices).
D: SmartX / SmartXNext freight and tariffs re-keyed from the supply-point edges to the physical edges, as Pro
   (international leg assembly -> DC, the domestic 0.9 / 1.2 on DC -> market); the 9 DC node freight rows removed.
Writes output/moneybase_costfix/smartx_changed_rows.csv (every removed / added row)."""
import csv
import io
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
S = os.path.join(REPO, "data", "sample", "smartx-2027-2029")
log = []


def load(name):
    with open(os.path.join(S, name), encoding="utf-8", newline="") as f:
        text = f.read()
    rd = csv.DictReader(io.StringIO(text))
    return rd.fieldnames, list(rd)


def save(name, fields, rows):
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    with open(os.path.join(S, name), "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())


def drop(name, pred, why):
    fields, rows = load(name)
    keep = []
    for r in rows:
        if pred(r):
            log.append({"file": name, "change": "removed", "row": ",".join(r[k] for k in fields), "why": why})
        else:
            keep.append(r)
    save(name, fields, keep)


# ── C ─────────────────────────────────────────────────────────────────
FG = {"SmartX": "AssemblyCN_g1", "SmartXNext": "AssemblyCN_g3", "SmartXPro_CN": "AssemblyCN", "SmartXPro_IN": "AssemblyIN"}
with open(os.path.join(S, "ppc_cost_basis.csv"), "w", encoding="utf-8", newline="") as f:
    f.write("product_id,cost_basis,purchase_node\n")
    for p, n in FG.items():
        f.write(f"{p},finished_goods,{n}\n")
        log.append({"file": "ppc_cost_basis.csv", "change": "added", "row": f"{p},finished_goods,{n}",
                    "why": "原価を組立工場での完成品の仕入値で持つ（新しいファイル）"})

PARTS_SUPPLIERS = {"WaferFab_TW", "WaferFab_TW_g1", "WaferFab_TW_g3", "SensorIN", "FoundryTW", "FoundryTW_g1",
                   "FoundryTW_g3"}
drop("ppc_supplier_cost.csv", lambda r: r["supplier_node"] in PARTS_SUPPLIERS,
     "完成品の仕入値に含まれる（部材・台湾の工場の仕入値）")
UPSTREAM_NODES = {"FoundryTW", "FoundryTW_g1", "FoundryTW_g3", "AssemblyCN", "AssemblyCN_g1", "AssemblyCN_g3", "AssemblyIN"}
drop("ppc_node_cost_rule.csv", lambda r: r["node_id"] in UPSTREAM_NODES,
     "完成品の仕入値に含まれる（台湾の工場・組立工場の加工費と入荷の運賃）")
drop("ppc_transfer_price_rule.csv", lambda r: r["mom_node"] in {"FoundryTW", "FoundryTW_g1", "FoundryTW_g3"},
     "台湾の工場の移転価格（PPC は最後の工場の移転価格だけ使う。完成品の仕入値に含まれる）")

# ── D ─────────────────────────────────────────────────────────────────
DC_NODES = {"DC_AMER", "DC_EMEA", "DC_APAC", "DC_AMER_g1", "DC_EMEA_g1", "DC_APAC_g1", "DC_AMER_g3", "DC_EMEA_g3",
            "DC_APAC_g3"}
drop("ppc_node_cost_rule.csv", lambda r: r["node_id"] in DC_NODES and r["cost_type"] == "logistics_cost",
     "DC のノードの運賃（国際輸送は区間だけに書く：大杉さんの判断）")

LINES = {"SmartX": ("AssemblyCN_g1", "SP_SmartX", "_g1"), "SmartXNext": ("AssemblyCN_g3", "SP_SmartXNext", "_g3")}
fields, rows = load("ppc_edge_cost_rule.csv")
out = []
for r in rows:
    prod = r["product_id"]
    if prod in LINES:
        mom, sp, sfx = LINES[prod]
        log.append({"file": "ppc_edge_cost_rule.csv", "change": "removed", "row": ",".join(r[k] for k in fields),
                    "why": "supply point 経由の鍵（PPC が引かない）"})
        continue
    out.append(r)
for prod, (mom, sp, sfx) in LINES.items():
    old = {r["edge_id"]: r for r in rows if r["product_id"] == prod}
    dom = old[f"{mom}->{sp}"]["fixed_amount"]
    for reg in ("AMER", "EMEA", "APAC"):
        src = old[f"{sp}->Retail_{reg}{sfx}"]
        for edge, amt, why in ((f"{mom}->DC_{reg}{sfx}", src["fixed_amount"], "国際輸送（組立工場 → DC）"),
                               (f"DC_{reg}{sfx}->Retail_{reg}{sfx}", dom, "国内（DC → 市場。Pro と同じ寄せ方）")):
            n = dict(src, edge_id=edge, fixed_amount=amt)
            out.append(n)
            log.append({"file": "ppc_edge_cost_rule.csv", "change": "added", "row": ",".join(n[k] for k in fields),
                        "why": why})
save("ppc_edge_cost_rule.csv", fields, out)

fields, rows = load("ppc_tariff_rule.csv")
out = []
for r in rows:
    if r["product_id"] in LINES:
        log.append({"file": "ppc_tariff_rule.csv", "change": "removed", "row": ",".join(r[k] for k in fields),
                    "why": "supply point 経由の鍵（PPC が引かない）"})
        continue
    out.append(r)
for prod, (mom, sp, sfx) in LINES.items():
    old = {r["edge_id"]: r for r in rows if r["product_id"] == prod}
    for reg in ("AMER", "EMEA", "APAC"):
        src = old[f"{sp}->Retail_{reg}{sfx}"]
        a = dict(src, edge_id=f"{mom}->DC_{reg}{sfx}")
        b = dict(src, edge_id=f"DC_{reg}{sfx}->Retail_{reg}{sfx}", from_country=src["to_country"], tariff_rate="0.0")
        for n, why in ((a, "国境の区間（組立工場 → DC）。税率はそのまま"), (b, "DC → 市場（国内、0%。Pro と同じ）")):
            out.append(n)
            log.append({"file": "ppc_tariff_rule.csv", "change": "added", "row": ",".join(n[k] for k in fields),
                        "why": why})
save("ppc_tariff_rule.csv", fields, out)

with open(os.path.join(REPO, "output", "moneybase_costfix", "smartx_changed_rows.csv"), "w", encoding="utf-8-sig",
          newline="") as f:
    w = csv.DictWriter(f, fieldnames=["file", "change", "row", "why"])
    w.writeheader()
    w.writerows(log)
from collections import Counter
print(Counter((x["file"], x["change"]) for x in log))
