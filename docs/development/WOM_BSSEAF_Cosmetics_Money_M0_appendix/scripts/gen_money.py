# -*- coding: utf-8 -*-
"""Step 2a (letter §2.2・§3): make M0 / M0t / M0a and write the money files.

    M0  = inputs of C3b + money files, Thai tariff 0%
    M0t = M0 with only WH_JP_Released->DC_TH tariff_rate 0 -> 0.30
    M0a = inputs of C3a + the same money files as M0

The values are the owner's adopted assumptions (M1-M8, Money_Assumptions §5.1) as
written in the letter §3; nothing here is tuned to make a profit match.
All 9 PPC rule files are written inside each model (no shared rules).

python output/bsseaf_cosmetics/money_m0_work/gen_money.py   (after step1_base.py)
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m0_common as C   # noqa: E402

WL = json.load(open(os.path.join(C.HERE, "base", "week_labels.json"), encoding="utf-8"))
START = WL[0]                         # actual planning start, warm-up included

# ── §3.2 prices / purchase cost / transfer price (per unit) ──────────────
MARKET = {  # channel: (currency, serum, cream, note)
    "SG_Store":       ("SGD", 165, 138, "直営店。店頭価格（GST 9% 抜き）"),
    "SG_EC":          ("SGD", 157, 131, "公式 EC。店頭価格×0.95（値引き反映済み）"),
    "SG_Distributor": ("SGD", 74, 62, "自社（SG 販社）から外部代理店への卸売（sell-in）。消費者価格ではない"),
    "TH_Distributor": ("THB", 1900, 1600, "自社（日本本社）から外部代理店への卸売（sell-in）。消費者価格ではない"),
}
SUPPLIER = {"COS_Serum": 1500, "COS_Cream": 1300}          # JPY, yield loss NOT added (M3)
TRANSFER = {"COS_Serum": 6000, "COS_Cream": 5000}          # JPY, the price PPC's tariff reads

# ── §3.3 node costs: (node, cost_type, basis, rate, {sku: fixed} | fixed, currency, note)
NODE = [
    ("Materials_JP", "conversion_cost", "qty", 0, 0, "JPY",
     "明示の 0（M7）。原料の費用は ppc_supplier_cost.csv の仕入原価で計上する"),
    ("Factory_JP", "conversion_cost", "qty", 0, {"COS_Serum": 700, "COS_Cream": 600}, "JPY",
     "加工費（調合・充填・包装・品質確認・工場の間接費）。1 個当たり"),
    ("WH_JP_Released", "warehouse_cost", "qty", 0, 30, "JPY", "判定済み在庫の保管・出荷。1 個当たり"),
    ("DC_SG", "conversion_cost", "qty", 0, 0.50, "SGD",
     "取扱・通関等の 1 個当たりの仮定額。期間の在庫保有費を実装した意味ではない"),
    ("DC_TH", "conversion_cost", "qty", 0, 12, "THB",
     "取扱・通関等の 1 個当たりの仮定額。期間の在庫保有費を実装した意味ではない"),
    ("SG_Store", "sga_cost", "revenue", 0.45, 0, "SGD",
     "売上の 45% ＝ 店舗運営費 35%（固定費の近似、M5）＋ 販社販管費 10%"),
    ("SG_EC", "sga_cost", "revenue", 0.15, 3.00, "SGD",
     "売上の 15% ＝ 決済・基盤手数料 5% ＋ 販社販管費 10%。＋ 1 個当たり配送梱包 SGD 3.00"),
    ("SG_EC", "marketing_cost", "revenue", 0.15, 0, "SGD", "デジタル広告 15%"),
    ("SG_Distributor", "marketing_cost", "revenue", 0.05, 0, "SGD",
     "MDF 5%（自社負担。負担者はシンガポール販社）"),
    ("TH_Distributor", "marketing_cost", "revenue", 0.05, 0, "THB",
     "MDF 5%（自社負担。負担者は日本本社）"),
]

# ── §3.4 physical edges: (edge_id, fixed_amount, currency) ─────────────────
EDGE = [
    ("Materials_JP->Factory_JP", 0, "JPY"),
    ("Factory_JP->WH_JP_Released", 20, "JPY"),
    ("WH_JP_Released->DC_SG", 60, "JPY"),
    ("WH_JP_Released->DC_TH", 70, "JPY"),
    ("DC_SG->SG_Store", 0.30, "SGD"),
    ("DC_SG->SG_EC", 0.30, "SGD"),
    ("DC_SG->SG_Distributor", 0.30, "SGD"),
    ("DC_TH->TH_Distributor", 8, "THB"),
]

# ── §3.5 tariff: border edges = transfer_price; other physical edges = explicit 0 ──
COUNTRY = {"Materials_JP": "JP", "Factory_JP": "JP", "WH_JP_Released": "JP", "DC_SG": "SG",
           "DC_TH": "TH", "SG_Store": "SG", "SG_EC": "SG", "SG_Distributor": "SG",
           "TH_Distributor": "TH"}
BORDER = {"WH_JP_Released->DC_SG", "WH_JP_Released->DC_TH"}
HS = "3304"
FX = {"JPY": 1, "SGD": 115, "THB": 4.5, "USD": 150}

VC_PRICE = [  # (edge, price_type, serum, cream, currency)
    ("WH_JP_Released->DC_SG", "intercompany", 6000, 5000, "JPY"),
    ("DC_SG->SG_Distributor", "wholesale", 74, 62, "SGD"),
    ("DC_TH->TH_Distributor", "wholesale", 1900, 1600, "THB"),
]


def num(x):
    return f"{x:g}" if isinstance(x, (int, float)) else str(x)


def write(md, name, header, rows):
    with open(os.path.join(md, name), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([num(v) for v in r])


def write_money(md, thai_rate):
    write(md, "ppc_market_price.csv", ["market_node", "product_id", "week", "market_price", "currency"],
          [(ch, s, START, v[1] if s == "COS_Serum" else v[2], v[0])
           for ch, v in MARKET.items() for s in C.SKUS])
    write(md, "ppc_supplier_cost.csv", ["supplier_node", "product_id", "week", "purchase_price", "currency"],
          [("Materials_JP", s, START, SUPPLIER[s], "JPY") for s in C.SKUS])
    write(md, "ppc_transfer_price_rule.csv",
          ["mom_node", "product_id", "method", "margin_rate", "fixed_price", "currency"],
          [("Factory_JP", s, "fixed", 0, TRANSFER[s], "JPY") for s in C.SKUS])
    write(md, "ppc_node_cost_rule.csv",
          ["node_id", "product_id", "cost_type", "basis", "rate", "fixed_amount", "currency", "note"],
          [(n, s, ct, b, r, fx[s] if isinstance(fx, dict) else fx, cur, note)
           for (n, ct, b, r, fx, cur, note) in NODE for s in C.SKUS])
    write(md, "ppc_edge_cost_rule.csv",
          ["edge_id", "product_id", "cost_type", "basis", "rate", "fixed_amount", "currency"],
          [(e, s, "logistics_cost", "qty", 0, amt, cur) for (e, amt, cur) in EDGE for s in C.SKUS])
    trows = []
    for (e, _a, _c) in EDGE:
        a, b = e.split("->")
        if e in BORDER:
            rate = thai_rate if e.endswith("DC_TH") else 0.0
            basis = "transfer_price"
        else:
            rate, basis = 0.0, "material_cost"
        for s in C.SKUS:
            trows.append((e, COUNTRY[a], COUNTRY[b], s, HS, rate, basis))
    write(md, "ppc_tariff_rule.csv",
          ["edge_id", "from_country", "to_country", "product_id", "hs_code", "tariff_rate", "tariff_basis"],
          trows)
    write(md, "ppc_fx_rate.csv", ["week", "currency", "base_currency", "rate"],
          [(w, c, "JPY", r) for w in WL for c, r in FX.items()])
    write(md, "ppc_node_profit_zone.csv", ["node_id", "product_id", "profit_zone_role", "country"], [])
    write(md, "ppc_profit_zone_rule.csv",
          ["profit_zone_role", "product_id", "profit_type", "basis", "rate", "fixed_amount"], [])
    write(md, "vc_price_rule.csv", ["edge_id", "product_id", "price_type", "week", "price", "currency"],
          [(e, s, pt, START, sv if s == "COS_Serum" else cv, cur)
           for (e, pt, sv, cv, cur) in VC_PRICE for s in C.SKUS])


def readme(md, text):
    with open(os.path.join(md, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


rec = {"planning_start": START, "n_weeks": len(WL), "week_last": WL[-1]}
for case, src, thai in (("M0", "C3b", 0.0), ("M0t", "M0", 0.30), ("M0a", "C3a", 0.0)):
    src_dir = os.path.join(C.COS, src)
    md = os.path.join(C.COS, case)
    C.copy_inputs(src_dir, md)
    write_money(md, thai)
    readme(md, f"# BS-SEAF cosmetics money trial — {case}\n\n"
               f"Copy of the inputs of {src} (quantity inputs unchanged) + the money rule files "
               f"written by output/bsseaf_cosmetics/money_m0_work/gen_money.py "
               f"(RequestLetter_BSSEAF_Cosmetics_Money v0.2 §3). Thai tariff {thai:.0%}. "
               f"Trial only (not data/sample).\n")
    q_src = C.input_hashes(src_dir)
    q_new = C.input_hashes(md)
    rec[case] = {"source": src, "thai_tariff": thai,
                 "quantity_inputs_equal_to_source": q_src == q_new,
                 "quantity_input_sha256": q_new,
                 "money_sha256": C.input_hashes(md, money=True)}
    print(case, "quantity inputs equal to", src, ":", q_src == q_new, flush=True)

# SKU / node correspondence (letter §3.1): the ids written in the money files vs the tree
tree_rows = C.read_csv(os.path.join(C.COS, "M0", "sc_tree_master.csv"))
in_tree = {(r["product_name"], r["node_name"]): r["node_type"] for r in tree_rows}
used = {n for (n, *_r) in NODE} | {x for (e, *_r) in EDGE for x in e.split("->")} | set(MARKET)
mapping = [{"product_id": s, "node_id": n, "node_type": in_tree.get((s, n), "NOT IN TREE"),
            "used_in_money_files": n in used}
           for s in C.SKUS for n in sorted({nm for (p, nm) in in_tree if p == s})]
rec["node_map"] = mapping
rec["names_not_in_tree"] = sorted({n for n in used if all((s, n) not in in_tree for s in C.SKUS)})
C.write_json(os.path.join(C.HERE, "gen_record.json"), rec)
with open(os.path.join(C.HERE, "sku_node_map.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(mapping[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(mapping)
print("names not in tree:", rec["names_not_in_tree"])
