# -*- coding: utf-8 -*-
"""
reconcile_ch1.py — 知識体系 第 1 章（1 ロットの一生と金額）の手計算を、Value Chain の実際の出力と照合する。
出力のファイルとモデルの CSV を読むだけ（WOM を import しない）。

    python -I output/knowledge_ch1/reconcile_ch1.py --runs output/knowledge_ch1 --out output/knowledge_ch1/result

前提のフォルダ（依頼書 §1）：
    <runs>/base          正式なサンプル
    <runs>/e2_tp5500     法人間の価格 5,500 円（vc_price_rule・ppc_transfer_price_rule のクリーム）
    <runs>/e3_tariff30   タイ向けのクリームの関税 30%（ppc_tariff_rule の WH_JP_Released->DC_TH・COS_Cream）
"""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd

LOT_EC = "COS_Cream:SG_EC:2028-W30:00001"
LOT_TH = "COS_Cream:TH_Distributor:2028-W30:00001"
UNITS = 24
G5_TOTALS = {"round1": 629_395_560.0, "round2": 631_119_240.0, "unrealized_opening": 1_723_680.0}
LINE_COLS = ["line_id", "week", "kind", "scope", "basis", "family", "price_type", "entity", "counterparty", "node",
             "amount_orig", "currency_orig", "amt_hq", "valued", "src_id", "note"]


def money(d):
    return pd.read_csv(os.path.join(d, "vc_money_lines.csv.gz"), low_memory=False)


def ships(d):
    s = pd.read_csv(os.path.join(d, "vc_shipments.csv.gz"), dtype=str)
    for c in ("ship_week_index", "arrival_week_index"):
        s[c] = pd.to_numeric(s[c], errors="coerce")
    return s


def has_basis(b, k):
    return b.fillna("").str.split(",").apply(lambda xs: k in xs or "all" in xs)


def amt(x):
    return float(x["amt_hq"].sum())


def chk(rows, name, got, exp, tol=0.5):
    ok = (got is not None) and abs(float(got) - float(exp)) <= tol
    rows.append({"check": name, "expected": exp, "got": got, "ok": bool(ok)})
    return ok


def lot_frame(m, lot):
    x = m[m["lot_id"] == lot].copy()
    x = x.sort_values(["week_index", "line_id"])
    return x


def week_end_positions(s, lot, wlab):
    """the lot's location at each week-end from the first shipment to the sale (from the shipments)."""
    x = s[s["lot_id"] == lot].sort_values("ship_week_index")
    sale = x[x["kind"] == "consumer_sale"]
    w_sale = int(sale["ship_week_index"].iloc[0])
    pos = []
    for w in range(int(x["ship_week_index"].min()), w_sale):
        loc = None
        for r in x.itertuples():
            a = r.arrival_week_index
            if r.kind == "consumer_sale" or pd.isna(a):
                continue
            if r.ship_week_index <= w < a:                 # shipped by the week-end, not yet arrived
                loc = ("transit", f"{r.phys_from}->{r.to}")
            elif a <= w:                                   # arrived; still there if the next leg leaves later
                nxt = x[(x["phys_from"] == r.to) & (x["ship_week_index"] > w)]
                left = x[(x["phys_from"] == r.to) & (x["ship_week_index"] <= w)]
                if len(nxt) and not len(left):
                    loc = ("node", r.to)
        pos.append({"week_index": w, "week": wlab.get(w, ""), "location_kind": loc[0] if loc else "",
                    "location": loc[1] if loc else ""})
    return pd.DataFrame(pos), w_sale


def lot_balances(lines, pos):
    """cumulative entity-basis / group-basis stock of the lot at each week-end (acquisitions capitalised, the
    stock leaves at the intercompany sale for the seller and at the external sale for the group)."""
    out = []
    for p in pos.itertuples():
        upto = lines[lines["week_index"] <= p.week_index]
        acq = upto[upto["kind"] == "acquisition"]
        # owner = the entity holding the lot after the last intercompany purchase (else the first owner)
        icp = acq[(acq["scope"] == "intercompany")]
        owner = icp["entity"].iloc[-1] if len(icp) else acq["entity"].iloc[0]
        ent = acq[has_basis(acq["basis"], "entity") & (acq["entity"] == owner)]
        grp = acq[has_basis(acq["basis"], "group")]
        if len(icp):        # the seller's entity-basis stock left at the intercompany sale
            pass
        e = amt(ent)
        g = amt(grp)
        out.append({"week": p.week, "location_kind": p.location_kind, "location": p.location, "owner": owner,
                    "entity_hq": e, "group_hq": g, "unrealized_hq": e - g})
    return pd.DataFrame(out)


def aggregate_check(run, bal, product="COS_Cream"):
    """the per-lot balance against the location's aggregate in vc_inventory_weekly / vc_unrealized_weekly
    (aggregate ÷ lots), at each week-end of the lot."""
    inv = pd.read_csv(os.path.join(run, "vc_inventory_weekly.csv"))
    un = pd.read_csv(os.path.join(run, "vc_unrealized_weekly.csv"))
    rows = []
    for b in bal.itertuples():
        i = inv[(inv["product"] == product) & (inv["week"] == b.week) & (inv["location"] == b.location)
                & (inv["owner"] == b.owner) & (inv["valued"] == 1)]
        u = un[(un["product"] == product) & (un["week"] == b.week) & (un["location"] == b.location)
               & (un["owner"] == b.owner)]
        lots = float(i["lots"].sum())
        e_avg = float(i["entity_hq"].sum()) / lots if lots else None
        g_avg = float(i["group_hq"].sum()) / lots if lots else None
        u_avg = float(u["unrealized_hq"].sum()) / float(u["lots"].sum()) if len(u) and float(u["lots"].sum()) else None
        rows.append({"week": b.week, "location": b.location, "owner": b.owner, "agg_lots": lots,
                     "agg_entity_per_lot": e_avg, "agg_group_per_lot": g_avg, "agg_unrealized_per_lot": u_avg,
                     "lot_entity": b.entity_hq, "lot_group": b.group_hq, "lot_unrealized": b.unrealized_hq,
                     "same": (e_avg is not None and abs(e_avg - b.entity_hq) < 0.5 and abs(g_avg - b.group_hq) < 0.5
                              and (u_avg is None or abs(u_avg - b.unrealized_hq) < 0.5))})
    return pd.DataFrame(rows)


def ec_lot(m, s, run, wlab):
    x = lot_frame(m, LOT_EC)
    r = []
    q = lambda **k: x[pd.concat([x[c] == v for c, v in k.items()], axis=1).all(axis=1)]
    chk(r, "原料の仕入 1,300×24", amt(q(family="purchase", scope="external")), 1300 * UNITS)
    chk(r, "工場の加工費 600×24", amt(q(family="conversion_cost", entity="E_JP")), 600 * UNITS)
    chk(r, "工場 → 倉庫の運賃 20×24", amt(q(family="freight", node="WH_JP_Released", kind="acquisition", entity="E_JP")
                                     [lambda d: d["counterparty"] == "E_JP"]), 20 * UNITS)
    wh = q(family="warehouse_cost")
    chk(r, "倉庫費 720（金額）", amt(wh), 30 * UNITS)
    chk(r, "倉庫費の行の数（受入の 1 回）", len(wh), 1)
    ic_rev = q(kind="revenue", scope="intercompany")
    chk(r, "日本本社の法人間売上", amt(ic_rev), 120_000)
    chk(r, "法人間売上の行の数", len(ic_rev), 1)
    ic_cogs_e = x[(x["kind"] == "cogs") & (x["scope"] == "intercompany") & has_basis(x["basis"], "entity")
                  & (x["entity"] == "E_JP")]
    chk(r, "法人間売上に対応する原価（entity、海上運賃を含む）", amt(ic_cogs_e), 47_520)
    chk(r, "日本本社の法人間粗利益", amt(ic_rev) - amt(ic_cogs_e), 72_480)
    sea = q(family="freight", entity="E_JP", kind="acquisition")[lambda d: d["counterparty"] == "E_SG"]
    chk(r, "海上運賃（日本本社の負担、グループの在庫原価）", amt(sea), 60 * UNITS)
    sg_fr_wh = x[(x["entity"] == "E_SG") & (x["family"] == "freight") & (x["kind"] == "acquisition")
                 & (x["node"] == "DC_SG")]
    chk(r, "販社の取得に海上運賃を足していない（E_SG の DC_SG の運賃の行の額）", amt(sg_fr_wh), 0)
    sg_pur = q(kind="acquisition", scope="intercompany", entity="E_SG")
    chk(r, "販社の取得（法人間の価格）", amt(sg_pur), 120_000)
    chk(r, "DC の取扱・通関 0.5 SGD×24", amt(q(family="conversion_cost", entity="E_SG")), 1_380)
    chk(r, "DC → EC の運賃 0.3 SGD×24", amt(q(family="freight", entity="E_SG", node="SG_EC", kind="acquisition")), 828)
    ext = q(kind="revenue", scope="external")
    chk(r, "外部売上", amt(ext), 361_560)
    chk(r, "外部売上の行の数", len(ext), 1)
    ce = q(kind="cogs", scope="external", basis="entity")
    cg = q(kind="cogs", scope="external", basis="group")
    chk(r, "外部売上原価（販社、entity）", amt(ce), 122_208)
    chk(r, "外部売上原価（連結、group）", amt(cg), 49_728)
    chk(r, "粗利益（販社）", amt(ext) - amt(ce), 239_352)
    chk(r, "粗利益（連結）", amt(ext) - amt(cg), 311_832)
    sel = q(kind="expense", scope="selling")
    for pt, v in (("hq_sga_allocation", 36_156), ("payment_platform_fee", 18_078), ("digital_ad", 54_234),
                  ("delivery_packing_cost", 8_280)):
        chk(r, f"販売費 {pt}", amt(sel[sel["price_type"] == pt]), v)
    chk(r, "販売費の行の数（4 費目）", len(sel), 4)
    chk(r, "売上比率の 3 費目", amt(sel[sel["price_type"] != "delivery_packing_cost"]), 108_468)
    w_sale = ext["week_index"].iloc[0]
    sw = x[x["week_index"] == w_sale]
    grp_pl = (amt(sw[(sw["kind"] == "revenue") & (sw["scope"] == "external")])
              - amt(sw[(sw["kind"] == "cogs") & (sw["basis"] == "group")])
              - amt(sw[(sw["kind"] == "expense") & has_basis(sw["basis"], "group")]))
    chk(r, "販売の週の連結の試算損益", grp_pl, 195_084)
    life = (amt(ext) - amt(cg) - amt(x[(x["kind"] == "expense") & has_basis(x["basis"], "group")]))
    chk(r, "ロット全期間の試算の採算（倉庫費を含む）", life, 194_364)
    wh_w = wh["week_index"].iloc[0]
    chk(r, "倉庫費の週が販売の週より前（週の差）", int(w_sale - wh_w) > 0, True)
    chk(r, "未評価の行の数", int((x["valued"] != 1).sum()), 0)
    # the rows that are not sales of the lot: management transfers and V1-basis cost rows
    mg = x[x["scope"] == "management"]
    pos, _ = week_end_positions(s, LOT_EC, wlab)
    bal = lot_balances(x, pos)
    agg = aggregate_check(run, bal)
    # realised at the sale week = entity cogs − group cogs
    chk(r, "外部販売の週に実現する内部の利益（entity − group の売上原価）", amt(ce) - amt(cg), 72_480)
    return x, r, pos, bal, agg, mg


def th_lot(m, s, run):
    x = lot_frame(m, LOT_TH)
    r = []
    chk(r, "日本本社 → タイの DC の法人間売上の行の数", int(((x["kind"] == "revenue") & (x["scope"] == "intercompany")).sum()), 0)
    ws = x[(x["kind"] == "revenue") & (x["scope"] == "external")]
    chk(r, "代理店への卸売（バーツ）1,600×24", float(ws["amount_orig"].sum()), 1600 * UNITS)
    chk(r, "卸売の行の数", len(ws), 1)
    cv = pd.read_csv(os.path.join(run, "vc_customs_valuation.csv"))
    c = cv[cv["lot_id"] == LOT_TH]
    chk(r, "課税価格の記録の行の数", len(c), 1)
    chk(r, "商品価額 5,000×24", float(c["goods_value"].iloc[0]), 5000 * UNITS)
    chk(r, "加える運賃 70×24", float(c["freight_added"].iloc[0]), 70 * UNITS)
    chk(r, "課税価格 5,070×24", float(c["customs_value"].iloc[0]), 5070 * UNITS)
    return x, r, c


def th_e3(base_m, e3_m, e3_run, s):
    xb = lot_frame(base_m, LOT_TH)
    x3 = lot_frame(e3_m, LOT_TH)
    r = []
    cv = pd.read_csv(os.path.join(e3_run, "vc_customs_valuation.csv"))
    c = cv[cv["lot_id"] == LOT_TH]
    duty = x3[(x3["family"] == "tariff") & (x3["amt_hq"] != 0)]
    chk(r, "関税の行の数（0 でない）", len(duty), 1)
    chk(r, "関税の額 5,070×24×0.3", amt(duty), 36_504)
    chk(r, "関税の行は在庫原価（acquisition）", (duty["kind"] == "acquisition").all(), True)
    chk(r, "関税の週 ＝ 受入の週（課税価格の記録の duty_week）", duty["week"].iloc[0] == c["duty_week"].iloc[0], True)
    rcv = s[(s["lot_id"] == LOT_TH) & (s["to"] == "DC_TH")]
    chk(r, "受入の週（出荷の記録）＝ 関税の週", rcv["arrival_week"].iloc[0] == duty["week"].iloc[0], True)
    chk(r, "関税の期間費用（expense）の 0 でない行", int(((x3["kind"] == "expense") & (x3["family"] == "tariff")
                                                    & (x3["amt_hq"] != 0)).sum()), 0)
    for b in ("entity", "group"):
        d = (amt(x3[(x3["kind"] == "cogs") & (x3["scope"] == "external") & (x3["basis"] == b)])
             - amt(xb[(xb["kind"] == "cogs") & (xb["scope"] == "external") & (xb["basis"] == b)]))
        chk(r, f"卸売の売上原価の増加（{b}）", d, 36_504)
    def life(x):
        return (amt(x[(x["kind"] == "revenue") & (x["scope"] == "external")])
                - amt(x[(x["kind"] == "cogs") & (x["scope"] == "external") & (x["basis"] == "group")])
                - amt(x[(x["kind"] == "expense") & has_basis(x["basis"], "group")]))
    chk(r, "このロットの連結の試算利益の減少", life(xb) - life(x3), 36_504)
    sale_w = x3[(x3["kind"] == "revenue") & (x3["scope"] == "external")]["week"].iloc[0]
    return x3, r, {"duty_week": duty["week"].iloc[0], "sale_week": sale_w}


def e2_ec(base_m, e2_m, s, e2_run, wlab):
    xb = lot_frame(base_m, LOT_EC)
    x2 = lot_frame(e2_m, LOT_EC)
    r = []
    def gp_jp(x):
        rev = amt(x[(x["kind"] == "revenue") & (x["scope"] == "intercompany")])
        c = amt(x[(x["kind"] == "cogs") & (x["scope"] == "intercompany") & has_basis(x["basis"], "entity")
                  & (x["entity"] == "E_JP")])
        return rev - c
    def gp_sg(x):
        return (amt(x[(x["kind"] == "revenue") & (x["scope"] == "external")])
                - amt(x[(x["kind"] == "cogs") & (x["scope"] == "external") & (x["basis"] == "entity")]))
    def gp_grp(x):
        return (amt(x[(x["kind"] == "revenue") & (x["scope"] == "external")])
                - amt(x[(x["kind"] == "cogs") & (x["scope"] == "external") & (x["basis"] == "group")]))
    def life(x):
        return gp_grp(x) - amt(x[(x["kind"] == "expense") & has_basis(x["basis"], "group")])
    chk(r, "日本本社の粗利益／個（基準）", gp_jp(xb) / UNITS, 3_020)
    chk(r, "日本本社の粗利益／個（E2）", gp_jp(x2) / UNITS, 3_520)
    chk(r, "販社の粗利益／個（基準）", gp_sg(xb) / UNITS, 9_973)
    chk(r, "販社の粗利益／個（E2）", gp_sg(x2) / UNITS, 9_473)
    pos, _ = week_end_positions(s, LOT_EC, wlab)
    bb = lot_balances(xb, pos)
    b2 = lot_balances(x2, pos)
    held = bb[bb["owner"] == "E_SG"]
    if len(held):
        w = held["week"].iloc[0]
        chk(r, f"未販売の内部の利益の増加（{w} の週末、1 ロット）",
            float(b2.set_index("week").loc[w, "unrealized_hq"] - bb.set_index("week").loc[w, "unrealized_hq"]), 12_000)
    chk(r, "連結の粗利益（E2）", gp_grp(x2), 311_832)
    chk(r, "全期間の採算（E2）", life(x2), 194_364)
    return x2, r, b2


def run_info(run):
    c = json.load(open(os.path.join(run, "vc_checks.json"), encoding="utf-8"))
    return c


def model_totals(run):
    """round 1 (before elimination) and round 2 (after elimination) period profit from vc_checks.json."""
    c = run_info(run)
    r2 = c.get("round2") or c.get("unrealized") or {}
    return c, r2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    base = os.path.join(a.runs, "base")
    e2 = os.path.join(a.runs, "e2_tp5500")
    e3 = os.path.join(a.runs, "e3_tariff30")
    mb = money(base)
    sb = ships(base)
    wlab = dict(zip(sb["ship_week_index"].dropna().astype(int), sb["ship_week"]))
    res = {}
    x, r, pos, bal, agg, mg = ec_lot(mb, sb, base, wlab)
    x[LINE_COLS].to_csv(os.path.join(a.out, "ec_lot_lines_base.csv"), index=False, encoding="utf-8-sig")
    sb[sb["lot_id"] == LOT_EC].to_csv(os.path.join(a.out, "ec_lot_shipments.csv"), index=False, encoding="utf-8-sig")
    bal.to_csv(os.path.join(a.out, "ec_lot_week_end_balances.csv"), index=False, encoding="utf-8-sig")
    agg.to_csv(os.path.join(a.out, "ec_lot_week_end_vs_aggregate.csv"), index=False, encoding="utf-8-sig")
    res["ec_lot"] = {"lot_id": LOT_EC, "checks": r, "management_rows": len(mg)}
    xt, rt, ct = th_lot(mb, sb, base)
    xt[LINE_COLS].to_csv(os.path.join(a.out, "th_lot_lines_base.csv"), index=False, encoding="utf-8-sig")
    sb[sb["lot_id"] == LOT_TH].to_csv(os.path.join(a.out, "th_lot_shipments.csv"), index=False, encoding="utf-8-sig")
    res["th_lot"] = {"lot_id": LOT_TH, "checks": rt}
    if os.path.isdir(e3):
        m3 = money(e3)
        x3, r3, info3 = th_e3(mb, m3, e3, sb)
        x3[LINE_COLS].to_csv(os.path.join(a.out, "th_lot_lines_e3.csv"), index=False, encoding="utf-8-sig")
        res["e3"] = {"checks": r3, **info3}
    if os.path.isdir(e2):
        m2 = money(e2)
        x2, r2, b2 = e2_ec(mb, m2, sb, e2, wlab)
        x2[LINE_COLS].to_csv(os.path.join(a.out, "ec_lot_lines_e2.csv"), index=False, encoding="utf-8-sig")
        b2.to_csv(os.path.join(a.out, "ec_lot_week_end_balances_e2.csv"), index=False, encoding="utf-8-sig")
        res["e2"] = {"checks": r2}
    json.dump(res, open(os.path.join(a.out, "reconcile_result.json"), "w", encoding="utf-8"), ensure_ascii=False,
              indent=1, default=str)
    n = sum(len(v["checks"]) for v in res.values())
    bad = [(k, c) for k, v in res.items() for c in v["checks"] if not c["ok"]]
    print(f"checks {n}, not ok {len(bad)}")
    for k, c in bad:
        print("  NG", k, c)
    print(bal.to_string(index=False))
    print(agg.to_string(index=False))


if __name__ == "__main__":
    main()
