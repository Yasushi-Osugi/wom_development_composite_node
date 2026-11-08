# -*- coding: utf-8 -*-
"""
check_g1.py — G1（売上比率の費用）の照合。出力のファイルとモデルの CSV を読むだけ（WOM を import しない）。

    python docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_appendix/check_g1.py --g1-dir output/g1_trial --out <appendix>

前提のフォルダ（依頼書 §3・§5）：
    <g1-dir>/t0              正式なサンプル（コードの改修前）
    <g1-dir>/t1              model_t1（SG_EC->CONSUMER の 2 行、logistics_cost）
    <g1-dir>/model_t2        T1 の写し ＋ vc_sales_cost_rule.csv ＋ delivery_packing_cost
    <g1-dir>/t2, t2_first, t2_b   model_t2 の実行（同じ場所に 2 回・その 1 回目の写し・別の場所）
    <g1-dir>/t0_after        正式なサンプル（改修後のコード）
    <g1-dir>/sample_hash_before.txt
段の出力が無ければ、その段の照合は飛ばす（"skipped"）。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from collections import Counter

import pandas as pd

EC_LOT = "COS_Cream:SG_EC:2028-W28:00001"
ST_LOT = "COS_Cream:SG_Store:2028-W30:00001"
DIRECT = ("SG_EC", "SG_Store")
EXPECT_G1 = 281_015_748
EXPECT_DELIV = 6_243_120
MONEY_COLS = ["week", "kind", "scope", "basis", "family", "price_type", "entity", "counterparty", "node",
              "amount_orig", "currency_orig", "amt_hq", "src_id"]


def money(d):
    return pd.read_csv(os.path.join(d, "vc_money_lines.csv.gz"), low_memory=False)


def ships(d):
    return pd.read_csv(os.path.join(d, "vc_shipments.csv.gz"), low_memory=False)


def checks_json(d):
    with open(os.path.join(d, "vc_checks.json"), encoding="utf-8") as f:
        return json.load(f)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def gz_sha(p):
    with gzip.open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def ppc_hashes(d):
    p = os.path.join(d, "ppc")
    return {fn: sha(os.path.join(p, fn)) for fn in sorted(os.listdir(p))}


def issue_counts(d):
    c = Counter()
    for i in checks_json(d)["issues"]:
        c[(i.get("issue"), i.get("node", ""), i.get("cost_type", ""))] += 1
    return {" | ".join(k): v for k, v in sorted(c.items())}


def without_line_id(df):
    return df.drop(columns=["line_id"]).sort_values(list(df.columns.drop("line_id"))).reset_index(drop=True)


def consumer_sales(s):
    return s[(s.kind == "consumer_sale") & s.node.isin(DIRECT)]


def g1_lines(m):
    return m[(m.kind == "expense") & (m.scope == "selling") & m.node.isin(DIRECT)
             & m.counterparty.astype(str).str.startswith("CONSUMER:")]


def lot_table(m, lot):
    return m[m.lot_id == lot][MONEY_COLS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--g1-dir", required=True)
    ap.add_argument("--sample-dir", default="data/sample/cosmetics-sg-th-2027-2029")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    G = lambda *p: os.path.join(a.g1_dir, *p)
    os.makedirs(a.out, exist_ok=True)
    R: dict = {}

    # ── T0 / B1 / B3 ──
    m0, s0 = money(G("t0")), ships(G("t0"))
    b1 = {}
    for lot, leaf in ((EC_LOT, "SG_EC"), (ST_LOT, "SG_Store")):
        sl = s0[s0.lot_id == lot]
        rcv = sl[sl.to == leaf]
        sale = sl[sl.kind == "consumer_sale"]
        rev = m0[(m0.lot_id == lot) & (m0.kind == "revenue") & (m0.scope == "external")]
        b1[lot] = {"dc_ship_week": rcv.ship_week.tolist(), "receipt_week": rcv.arrival_week.tolist(),
                   "sale_week": sale.ship_week.tolist(), "sale_ship_id": sale.ship_id.tolist(),
                   "revenue": rev.amount_orig.tolist(), "revenue_ccy": rev.currency_orig.tolist(),
                   "revenue_week": rev.week.tolist()}
    b1["ok"] = (b1[EC_LOT]["receipt_week"] == ["2028-W28"] and b1[EC_LOT]["sale_week"] == ["2028-W28"]
                and b1[EC_LOT]["revenue"] == [3144.0] and b1[EC_LOT]["dc_ship_week"] == ["2028-W27"]
                and b1[ST_LOT]["receipt_week"] == ["2028-W28"] and b1[ST_LOT]["sale_week"] == ["2028-W30"]
                and b1[ST_LOT]["revenue"] == [3312.0])
    R["B1"] = b1
    R["B3_t0_issues"] = issue_counts(G("t0"))
    cs0 = consumer_sales(s0)
    R["T0_direct_sales"] = cs0.groupby("node").size().to_dict()
    lot_table(m0, EC_LOT).to_csv(os.path.join(a.out, "t0_ec_lot_money_lines.csv"), index=False)
    lot_table(m0, ST_LOT).to_csv(os.path.join(a.out, "t0_store_lot_money_lines.csv"), index=False)

    # ── T1 ──
    if os.path.exists(G("t1")):
        m1 = money(G("t1"))
        new = m1[(m1.kind == "expense") & (m1.scope == "selling") & (m1.node == "SG_EC")
                 & (m1.counterparty == "CONSUMER:SG_EC")]
        ec_sale_id = b1[EC_LOT]["sale_ship_id"][0]
        r1 = new[new.lot_id == EC_LOT]
        t1_1 = (len(r1) == 1 and r1.week.iloc[0] == "2028-W28" and r1.entity.iloc[0] == "E_SG"
                and float(r1.amount_orig.iloc[0]) == 72.0 and r1.currency_orig.iloc[0] == "SGD"
                and r1.src_id.iloc[0] == ec_sale_id)
        ec_sales = cs0[cs0.node == "SG_EC"]
        per = new.groupby("src_id").size()
        cover = ec_sales.ship_id.map(per).fillna(0).astype(int)
        t1_2 = {"ec_sales": len(ec_sales), "lines": len(new), "lines_per_sale": dict(Counter(cover)),
                "total_hq": float(new.amt_hq.sum())}
        t1_2["ok"] = set(cover) == {1} and len(new) == len(ec_sales) and round(t1_2["total_hq"]) == EXPECT_DELIV
        rest1 = without_line_id(m1.drop(new.index))
        same = bool(rest1.equals(without_line_id(m0)))
        p0, p1 = ppc_hashes(G("t0")), ppc_hashes(G("t1"))
        R["T1"] = {
            "1_rep_line": {"rows": len(r1), "row": r1[MONEY_COLS].to_dict("records"), "ok": bool(t1_1)},
            "2_all_ec_sales": t1_2,
            "3_rest_equals_t0": {"rows_t1": len(m1), "rows_t0": len(m0), "new": len(new), "ok": same},
            "4_ppc_equals_t0": {"files": len(p0), "diff": [k for k in p0 if p0[k] != p1.get(k)],
                                "ok": p0 == p1},
            "issues": issue_counts(G("t1")),
        }
        R["T1"]["ok"] = all(R["T1"][k]["ok"] for k in ("1_rep_line", "2_all_ec_sales", "3_rest_equals_t0",
                                                        "4_ppc_equals_t0"))
        lot_table(m1, EC_LOT).to_csv(os.path.join(a.out, "t1_ec_lot_money_lines.csv"), index=False)

    # ── T2 ──
    if os.path.exists(G("t2")):
        R["T2"] = check_t2(a, G, m0, s0, b1)

    keys = [("B1", lambda: R["B1"]["ok"])]
    if "T1" in R:
        keys.append(("T1", lambda: R["T1"]["ok"]))
    if "T2" in R:
        keys += [(k, (lambda k=k: R["T2"][k]["ok"])) for k in R["T2"] if k.startswith("V")]
    R["summary"] = {k: bool(f()) for k, f in keys}
    with open(os.path.join(a.out, "check_g1_result.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=2, default=str)
    for k, v in R["summary"].items():
        print(f"{k}: {'OK' if v else 'NG'}")
    return 0 if all(R["summary"].values()) else 1


def check_t2(a, G, m0, s0, b1):
    T: dict = {}
    m2, s2 = money(G("t2")), ships(G("t2"))
    rule = pd.read_csv(G("model_t2", "vc_sales_cost_rule.csv"))
    erule = pd.read_csv(G("model_t2", "ppc_edge_cost_rule.csv"))
    deliv = erule[erule.edge_id.str.endswith("->CONSUMER")]
    g1 = g1_lines(m2)
    cs = consumer_sales(s2)
    rev = m2[(m2.kind == "revenue") & (m2.scope == "external") & m2.node.isin(DIRECT)].set_index("src_id")

    # V1
    ec_id = b1[EC_LOT]["sale_ship_id"][0]
    e = g1[g1.lot_id == EC_LOT]
    exp_ec = {"hq_sga_allocation": 314.40, "payment_platform_fee": 157.20, "digital_ad": 471.60,
              "delivery_packing_cost": 72.00}
    got = {r.price_type: round(float(r.amount_orig), 6) for r in e.itertuples()}
    T["V1"] = {"rows": e[MONEY_COLS].to_dict("records"), "total_sgd": round(float(e.amount_orig.sum()), 6),
               "ok": (len(e) == 4 and got == exp_ec and set(e.week) == {"2028-W28"} and set(e.src_id) == {ec_id}
                      and set(e.entity) == {"E_SG"} and set(e.currency_orig) == {"SGD"})}
    # V2
    st = g1[g1.lot_id == ST_LOT]
    exp_st = {"store_operating": 1159.20, "hq_sga_allocation": 331.20}
    got = {r.price_type: round(float(r.amount_orig), 6) for r in st.itertuples()}
    T["V2"] = {"rows": st[MONEY_COLS].to_dict("records"), "total_sgd": round(float(st.amount_orig.sum()), 6),
               "rows_in_receipt_week_2028_W28": int((st.week == "2028-W28").sum()),
               "ok": len(st) == 2 and got == exp_st and set(st.week) == {"2028-W30"}
                     and int((st.week == "2028-W28").sum()) == 0}
    lot_table(m2, EC_LOT).to_csv(os.path.join(a.out, "t2_ec_lot_money_lines.csv"), index=False)
    lot_table(m2, ST_LOT).to_csv(os.path.join(a.out, "t2_store_lot_money_lines.csv"), index=False)
    # V3
    items = {n: set(rule[rule.node_id == n].cost_item) | (set(deliv[deliv.edge_id == f"{n}->CONSUMER"].cost_type))
             for n in DIRECT}
    cnt = g1.groupby(["src_id", "price_type"]).size()
    bad, per_sale = [], Counter()
    for r in cs.itertuples():
        n = 0
        for it in items[r.node]:
            k = cnt.get((r.ship_id, it), 0)
            n += k
            if k != 1:
                bad.append((r.ship_id, it, int(k)))
        per_sale[(r.node, n)] += 1
    stray = sorted(set(g1.src_id) - set(cs.ship_id))
    T["V3"] = {"sales": cs.groupby("node").size().to_dict(), "items": {k: sorted(v) for k, v in items.items()},
               "lines": len(g1), "lines_per_sale": {f"{k[0]}:{k[1]}": v for k, v in per_sale.items()},
               "not_exactly_one": len(bad), "examples": bad[:5], "stray_src": len(stray),
               "ok": not bad and not stray and len(g1) == sum(len(items[n]) * c for n, c in
                                                             cs.groupby("node").size().items())}
    # V4
    rr = rule.set_index(["node_id", "product_id", "cost_item"]).rate
    dd = deliv.assign(node=deliv.edge_id.str.replace("->CONSUMER", "", regex=False)) \
        .set_index(["node", "product_id", "cost_type"])
    mism = []
    for r in g1.itertuples():
        if r.price_type == "delivery_packing_cost":
            row = dd.loc[(r.node, r.product, r.price_type)]
            units = float(s2.set_index("ship_id").units.get(r.src_id))
            exp = (float(row.rate) + float(row.fixed_amount)) * units
        else:
            exp = float(rr.loc[(r.node, r.product, r.price_type)]) * float(rev.amount_orig.get(r.src_id))
            if r.currency_orig != rev.currency_orig.get(r.src_id):
                mism.append((r.src_id, r.price_type, "currency"))
        if abs(float(r.amount_orig) - exp) > 1e-6:
            mism.append((r.src_id, r.price_type, float(r.amount_orig), exp))
    T["V4"] = {"checked": len(g1), "mismatch": len(mism), "examples": mism[:5], "ok": not mism}
    # V5
    tot = float(g1.amt_hq.sum())
    by = g1.groupby(["node", "family", "price_type"]).amt_hq.sum().round(2)
    T["V5"] = {"total_hq": tot, "expect": EXPECT_G1, "diff": tot - EXPECT_G1,
               "delivery_packing_hq": float(g1[g1.price_type == "delivery_packing_cost"].amt_hq.sum()),
               "by_node_family_item": {" | ".join(k): v for k, v in by.items()},
               "by_node_product_item": {" | ".join(k): v for k, v in
                                        g1.groupby(["node", "product", "price_type"]).amt_hq.sum().round(0).items()},
               "ok": abs(tot - EXPECT_G1) < 0.5 and round(float(g1[g1.price_type == "delivery_packing_cost"]
                                                                .amt_hq.sum())) == EXPECT_DELIV}
    # V6：PPC（参考）
    ev = pd.read_csv(G("t2", "ppc", "ppc_event_ledger.csv"), low_memory=False)
    ev = ev[ev.node_id.isin(DIRECT) & ev.ppc_event_type.isin(["sga_cost", "marketing_cost"])].copy()
    ev["total"] = ev.amount_base * ev.qty
    maps = {("SG_EC", "sga_cost"): ["hq_sga_allocation", "payment_platform_fee", "delivery_packing_cost"],
            ("SG_EC", "marketing_cost"): ["digital_ad"],
            ("SG_Store", "sga_cost"): ["store_operating", "hq_sga_allocation"]}
    v6 = {}
    ok6 = True
    for (n, t), its in maps.items():
        p = float(ev[(ev.node_id == n) & (ev.ppc_event_type == t)].total.sum())
        v = float(g1[(g1.node == n) & g1.price_type.isin(its)].amt_hq.sum())
        pw = ev[(ev.node_id == n) & (ev.ppc_event_type == t)].groupby(["product_id", "week"]).total.sum()
        vw = g1[(g1.node == n) & g1.price_type.isin(its)].groupby(["product", "week"]).amt_hq.sum()
        j = pd.concat([pw.rename("ppc"), vw.rename("vc")], axis=1).fillna(0.0)
        j["d"] = j.vc - j.ppc
        v6[f"{n} {t}"] = {"ppc": p, "vc": v, "diff": v - p, "weeks": len(j),
                          "weeks_diff_gt_1yen": int((j.d.abs() > 1).sum()),
                          "max_abs_week_diff": float(j.d.abs().max())}
        ok6 = ok6 and abs(v - p) < 0.5
    T["V6"] = {"by_item": v6, "ok": ok6}
    # V7
    iss = issue_counts(G("t2"))
    direct_rev = {k: v for k, v in iss.items() if k.startswith("revenue_based_node_cost_not_supported")
                  and any(f"| {n} |" in k for n in DIRECT)}
    dist_rev = {k: v for k, v in iss.items() if "Distributor" in k}
    vcj = checks_json(G("t2"))
    T["V7"] = {"issues": iss, "direct_revenue_based": direct_rev, "distributor": dist_rev,
               "t0_issues": issue_counts(G("t0")),
               "ppc_only_rows_unused": vcj.get("sales_cost_rule"),
               "ok": not direct_rev}
    # V8
    def eq(x, y, drop):
        dx, dy = money(G(x)), money(G(y))
        if drop:
            dx, dy = dx.drop(columns="line_id"), dy.drop(columns="line_id")
        return bool(len(dx) == len(dy) and dx.equals(dy))
    T["V8"] = {"same_place": eq("t2_first", "t2", False), "other_place": eq("t2", "t2_b", True),
               "sha": {k: gz_sha(G(k, "vc_money_lines.csv.gz")) for k in ("t2_first", "t2", "t2_b")}}
    T["V8"]["ok"] = T["V8"]["same_place"] and T["V8"]["other_place"]
    # V9
    v9 = {}
    if os.path.exists(G("t0_after")):
        ma = money(G("t0_after"))
        v9["sample_vc_money_equals_t0"] = bool(ma.equals(m0))
        sa = ships(G("t0_after"))
        v9["sample_vc_shipments_equals_t0_wo_plan_id"] = bool(sa.drop(columns="plan_id").equals(s0.drop(columns="plan_id")))
        others = {}
        for fn in sorted(os.listdir(G("t0"))):
            p0, pa = G("t0", fn), G("t0_after", fn)
            if os.path.isfile(p0) and fn.endswith(".csv"):
                others[fn] = sha(p0) == sha(pa)
        v9["sample_vc_csv_equal"] = others
        v9["sample_ppc_equals_t0"] = ppc_hashes(G("t0")) == ppc_hashes(G("t0_after"))
        v9["sample_issues_equal"] = issue_counts(G("t0")) == issue_counts(G("t0_after"))
    v9["t2_ppc_equals_t0"] = ppc_hashes(G("t0")) == ppc_hashes(G("t2"))
    v9["ok"] = all(v if isinstance(v, bool) else all(v.values()) for k, v in v9.items())
    T["V9"] = v9
    # sample folder unchanged
    T["sample_hash"] = sample_hash(a)
    return T


def sample_hash(a):
    before = {}
    with open(os.path.join(a.g1_dir, "sample_hash_before.txt"), encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                h, n = line.split(None, 1)
                before[n.strip()] = h.lower()
    after = {fn: sha(os.path.join(a.sample_dir, fn)) for fn in os.listdir(a.sample_dir)
             if os.path.isfile(os.path.join(a.sample_dir, fn))}
    return {"files": len(after), "changed": sorted(k for k in set(before) | set(after)
                                                   if before.get(k) != after.get(k))}


if __name__ == "__main__":
    raise SystemExit(main())
