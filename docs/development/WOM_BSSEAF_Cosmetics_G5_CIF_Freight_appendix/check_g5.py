# -*- coding: utf-8 -*-
"""
check_g5.py — G5（シンガポール向けの CIF の海上運賃）の照合。出力のファイルとモデルの CSV を読むだけ
（WOM を import しない）。G4 の check_g4.py の作りに倣う。

    python -I docs/development/WOM_BSSEAF_Cosmetics_G5_CIF_Freight_appendix/check_g5.py --g5-dir output/g5_trial --out <appendix>

前提のフォルダ（依頼書 §3・§5）：
    <g5-dir>/t0                  正式なサンプル（G4 を commit した後、コードの改修前）
    <g5-dir>/t1_sample           正式なサンプル（改修後のコード、表なし）
    <g5-dir>/t1_cif, t1_buyer    写しのモデル（model_cif・model_buyer）の実行
    <g5-dir>/t1_cif_first, t1_cif_other   model_cif の 1 回目の写し・別の場所の実行（V10）
段の出力が無ければ、その照合は飛ばす（"skipped"）。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os

import pandas as pd

LOT = "COS_Cream:SG_Store:2028-W30:00001"
EDGE = "WH_JP_Released->DC_SG"
SHIP = "ship:COS_Cream:OUT:dad:WH_JP_Released:COS_Cream:93:0"
W_SHIP, W_TRANSIT, W_RCPT, W_SALE = "2028-W25", "2028-W26", "2028-W27", "2028-W30"
C = 46_080.0
FREIGHT = 1_440.0
PRICE = 120_000.0
COGS_ENTITY_T0, COGS_GROUP = 123_648.0, 49_728.0
N_SHIP, TOTAL = 3_367, 4_848_480.0
COLS = ["line_id", "week", "src_id", "kind", "scope", "basis", "family", "price_type", "entity", "node",
        "counterparty", "amount_orig", "currency_orig", "amt_hq", "valued", "note"]


def money(d):
    return pd.read_csv(os.path.join(d, "vc_money_lines.csv.gz"), low_memory=False)


def ships(d):
    return pd.read_csv(os.path.join(d, "vc_shipments.csv.gz"), dtype=str)


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def gz_sha(p):
    with gzip.open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def has(*ds):
    return all(os.path.isdir(d) for d in ds)


def has_b(series, b):
    return series.astype(str).str.split(",").apply(lambda xs: b in xs or "all" in xs)


def lot_rows(m):
    return m[m.lot_id == LOT][COLS]


def wk_le(series, w):
    return series.astype(str) <= w      # ISO week labels sort as strings


# ── T0（B1〜B4）────────────────────────────────────────────────────
def check_t0(g):
    d = os.path.join(g, "t0")
    if not has(d):
        return {"skipped": True}
    sh, m = ships(d), money(d)
    lot = sh[sh.lot_id == LOT]
    e = lot[lot.edge == EDGE].iloc[0]
    sale = lot[lot.kind == "consumer_sale"].iloc[0]
    l = lot_rows(m)
    cl = l[(l.kind == "cogs") & (l.scope == "intercompany") & (l.basis == "entity") & (l.src_id == SHIP)]
    out = {"B1": {"ship": e.ship_week, "arrival": e.arrival_week, "sale": sale.ship_week,
                  "C_line": cl[["line_id", "week", "amt_hq"]].to_dict("records"),
                  "ok": e.ship_id == SHIP and e.ship_week == W_SHIP and e.arrival_week == W_RCPT
                  and sale.ship_week == W_SALE and len(cl) == 1 and float(cl.iloc[0].amt_hq) == C}}
    fl = l[(l.family == "freight") & (l.src_id == SHIP)]
    out["B2"] = {"lines": fl[["line_id", "week", "entity", "kind", "basis", "amt_hq"]].to_dict("records"),
                 "ok": len(fl) == 1 and fl.iloc[0].week == W_SHIP and fl.iloc[0].entity == "E_SG"
                 and fl.iloc[0].basis == "v1,entity,group" and float(fl.iloc[0].amt_hq) == FREIGHT}
    ids = set(sh.loc[sh.edge == EDGE, "ship_id"])
    f = m[(m.family == "freight") & m.src_id.isin(ids)]
    out["B3"] = {"lines": int(len(f)), "total": float(f.amt_hq.sum()), "entities": sorted(f.entity.unique()),
                 "ok": len(f) == N_SHIP and float(f.amt_hq.sum()) == TOTAL and set(f.entity) == {"E_SG"}}
    sc = l[(l.kind == "cogs") & (l.week == W_SALE)]
    cg = {b: float(sc[sc.basis == b].amt_hq.sum()) for b in ("entity", "group")}
    out["B4"] = {"sale_cogs": cg, "ok": cg["entity"] == COGS_ENTITY_T0 and cg["group"] == COGS_GROUP}
    return out


# ── T1（V1〜V11）───────────────────────────────────────────────────
def lot_cost(l, basis, entity=None, upto=None):
    """sum of the lot's acquisition lines on a basis (optionally of one entity, up to a week)."""
    x = l[(l.kind == "acquisition") & has_b(l.basis, basis)]
    if entity:
        x = x[x.entity == entity]
    if upto:
        x = x[wk_le(x.week, upto)]
    return x


def check_t1(g, out_dir):
    res = {}
    d0, dc = os.path.join(g, "t0"), os.path.join(g, "t1_cif")
    if has(dc, d0):
        m, sh = money(dc), ships(dc)
        m0 = money(d0)
        l = lot_rows(m)
        # V1
        ej = l[(l.entity == "E_JP") & (l.family == "freight") & (l.src_id == SHIP)]
        jc = ej[ej.kind == "cogs"]
        cl = l[(l.kind == "cogs") & (l.scope == "intercompany") & (l.basis == "entity") & (l.src_id == SHIP)
               & (l.family == "sale")]
        brk = lot_cost(l, "entity", "E_JP")
        brk = brk[(brk.line_id < int(cl.iloc[0].line_id))]
        res["V1"] = {"E_JP_freight_lines": ej[["line_id", "week", "kind", "scope", "basis", "amt_hq", "note"]]
                     .to_dict("records"),
                     "C_line_id": int(cl.iloc[0].line_id), "C": float(cl.iloc[0].amt_hq),
                     "C_breakdown_line_ids": brk.line_id.astype(int).tolist(),
                     "C_breakdown_sum": float(brk.amt_hq.sum()),
                     "ok": len(jc) == 2 and set(jc.basis) == {"v1", "entity"} and (jc.week == W_SHIP).all()
                     and (jc.scope == "intercompany").all() and (jc.amt_hq == FREIGHT).all()
                     and float(cl.iloc[0].amt_hq) == C and cl.iloc[0].week == W_SHIP
                     and float(brk.amt_hq.sum()) == C}
        # V2
        sg = l[(l.entity == "E_SG") & (l.kind == "acquisition")]
        w25 = sg[sg.week == W_SHIP]
        sgf = sg[(sg.family == "freight") & (sg.src_id == SHIP)]
        rc = sg[(sg.week == W_RCPT) & (sg.family == "freight") & (sg.src_id == SHIP)]
        res["V2"] = {"E_SG_W25": w25[["line_id", "family", "basis", "amt_hq"]].to_dict("records"),
                     "E_SG_edge_freight": int(len(sgf)), "E_SG_receipt_freight": int(len(rc)),
                     "ok": len(w25[w25.family == "purchase"]) == 1
                     and float(w25[w25.family == "purchase"].amt_hq.iloc[0]) == PRICE
                     and set(w25.family) <= {"purchase", "tariff"} and float(w25[w25.family == "tariff"].amt_hq.abs().sum()) == 0
                     and len(sgf) == 0 and len(rc) == 0}
        # V3 group cost of the lot at the transit week-ends (acquisitions on the group basis up to the week)
        gw = {w: float(lot_cost(l, "group", upto=w).amt_hq.sum()) for w in (W_SHIP, W_TRANSIT)}
        sc = l[(l.kind == "cogs") & (l.week == W_SALE)]
        gfl = l[(l.family == "freight") & (l.src_id == SHIP) & (l.kind == "acquisition") & has_b(l.basis, "group")]
        res["V3"] = {"group_cost_transit_weekend": gw, "sale_cogs_group": float(sc[sc.basis == "group"].amt_hq.sum()),
                     "edge_freight_in_group_cost_lines": int(len(gfl)),
                     "ok": all(v == C + FREIGHT for v in gw.values())
                     and float(sc[sc.basis == "group"].amt_hq.sum()) == COGS_GROUP and len(gfl) == 1}
        # V4
        ce = float(sc[sc.basis == "entity"].amt_hq.sum())
        res["V4"] = {"sale_cogs_entity": ce, "ok": ce == COGS_ENTITY_T0 - FREIGHT == 122_208}
        # V5 unrealized: lot U at the transit week-ends, and the in-transit balance of every week = sum of lot U
        u_lot = {w: float(lot_cost(l, "entity", "E_SG", upto=w).amt_hq.sum()) - gw[w] for w in gw}
        e = sh[sh.edge == EDGE].copy()
        e["sw"], e["aw"] = e.ship_week_index.astype(int), e.arrival_week_index.astype(int)
        ids = set(e.ship_id)
        ml = m[m.src_id.isin(ids) | m.lot_id.isin(set(e.lot_id))]
        price = ml[(ml.kind == "acquisition") & (ml.family == "purchase") & (ml.entity == "E_SG") & ml.src_id.isin(ids)] \
            .groupby("src_id").amt_hq.sum()
        grp = m[(m.kind == "acquisition") & has_b(m.basis, "group") & m.lot_id.isin(set(e.lot_id))]
        uw = pd.read_csv(os.path.join(dc, "vc_unrealized_weekly.csv"))
        ut = uw[(uw.owner == "E_SG") & (uw.location_kind == "transit") & (uw.location == EDGE)]
        mism, n_cmp = 0, 0
        wi = m[["week", "week_index"]].drop_duplicates().set_index("week").week_index
        grp = grp.assign(wi=grp.week.map(wi))
        for (prod, w), x in ut.groupby(["product", "week_index"]):
            tr = e[(e["product"] == prod) & (e.sw <= w) & (e.aw > w)]
            u = 0.0
            for r in tr.itertuples():
                gc = float(grp[(grp.lot_id == r.lot_id) & (grp.wi <= r.sw)].amt_hq.sum())
                u += float(price.get(r.ship_id, 0.0)) - gc
            n_cmp += 1
            if abs(u - float(x.unrealized_hq.sum())) > 1e-6:
                mism += 1
        res["V5"] = {"lot_U_transit_weekend": u_lot, "transit_weeks_compared": n_cmp, "mismatches": mism,
                     "ok": all(v == PRICE - (C + FREIGHT) == 72_480 for v in u_lot.values()) and mism == 0 and n_cmp > 0}
        # V6 + detail (entity x week x shipment)
        f = m[(m.family == "freight") & m.src_id.isin(ids)]
        jcog = f[(f.entity == "E_JP") & (f.kind == "cogs") & (f.basis == "entity")]
        per = pd.DataFrame({"sid": sorted(ids)})
        cnt = lambda x: per.sid.map(x.groupby("src_id").size()).fillna(0).astype(int)
        per["jp_cogs_entity"] = cnt(jcog)
        per["jp_cogs_v1"] = cnt(f[(f.entity == "E_JP") & (f.kind == "cogs") & (f.basis == "v1")])
        per["group_once"] = cnt(f[(f.kind == "acquisition") & has_b(f.basis, "group")])
        per["sg_entity_acq"] = cnt(f[(f.entity == "E_SG") & (f.kind == "acquisition") & has_b(f.basis, "entity")])
        wk = f.merge(e[["ship_id", "ship_week"]], left_on="src_id", right_on="ship_id")
        res["V6"] = {"E_JP_cogs_entity_lines": int(len(jcog)), "E_JP_cogs_entity_total": float(jcog.amt_hq.sum()),
                     "E_SG_edge_freight_acq": int(per.sg_entity_acq.sum()),
                     "shipments_exactly_one": {c: int((per[c] == (0 if c == "sg_entity_acq" else 1)).sum())
                                               for c in ("jp_cogs_entity", "jp_cogs_v1", "group_once", "sg_entity_acq")},
                     "all_at_ship_week": bool((wk.week == wk.ship_week).all()),
                     "ok": len(jcog) == N_SHIP and float(jcog.amt_hq.sum()) == TOTAL and int(per.sg_entity_acq.sum()) == 0
                     and bool((per.jp_cogs_entity == 1).all() and (per.jp_cogs_v1 == 1).all() and (per.group_once == 1).all())
                     and bool((wk.week == wk.ship_week).all())}
        # V7 entity profit (whole horizon)
        v2c, v20 = pd.read_csv(os.path.join(dc, "vc_v2_weekly.csv")), pd.read_csv(os.path.join(d0, "vc_v2_weekly.csv"))
        pc, p0 = v2c.groupby("entity").profit_hq_wk.sum(), v20.groupby("entity").profit_hq_wk.sum()
        dlt = {k: float(pc.get(k, 0) - p0.get(k, 0)) for k in sorted(set(pc.index) | set(p0.index))}
        res["V7"] = {"delta_vs_t0": dlt, "sum_t0": float(p0.sum()), "sum_t1": float(pc.sum()),
                     "ok": dlt.get("E_JP") == -TOTAL and dlt.get("E_SG") == TOTAL and abs(float(pc.sum() - p0.sum())) < 1e-6}
        # V8 consolidated
        v3c, v30 = pd.read_csv(os.path.join(dc, "vc_v3_weekly.csv")), pd.read_csv(os.path.join(d0, "vc_v3_weekly.csv"))
        diff_cols = [c for c in v30.columns if not v30[c].equals(v3c[c])]
        # consolidated after elimination (round 2) and the group inventory: must not move by 1 yen.
        # The round-1 columns (before elimination, entity books) and the unrealized-profit columns move
        # by design (the freight leaves E_SG's entity cost; U shrinks by the freight).
        r2_cols = [c for c in v30.columns if ("_r2_" in c or c.startswith("inv_group") or c == "lots_unvalued"
                                              or c.startswith("to_unvalued"))]
        r2_same = all(v30[c].equals(v3c[c]) for c in r2_cols)
        ic = [c for c in v30.columns if c.endswith("_wk") and c.split("_")[0] in ("ic", "external") and "_r2_" not in c]
        inv_c, inv_0 = (pd.read_csv(os.path.join(x, "vc_inventory_weekly.csv")) for x in (dc, d0))
        inv_same = all(inv_0[c].equals(inv_c[c]) for c in ("group_hq", "group_common")) and len(inv_0) == len(inv_c)
        cc, c0 = pd.read_csv(os.path.join(dc, "vc_ppc_comparison.csv")), pd.read_csv(os.path.join(d0, "vc_ppc_comparison.csv"))
        moved = {}
        for i in range(len(c0)):
            d_ = float(cc.ledger_v3.iloc[i]) - float(c0.ledger_v3.iloc[i])
            if d_ != 0:
                moved[str(c0["item"].iloc[i])] = d_
        cons = pd.read_csv(os.path.join(dc, "vc_conservation.csv"))
        pr = lambda c, pref: float(c[c["item"].astype(str).str.startswith(pref)].ledger_v3.iloc[-1])
        p_wk_diff = (v3c.profit_hq_wk - v30.profit_hq_wk)
        res["V8"] = {"v3_round2_and_group_inventory_columns_same": r2_same, "v3_round2_columns_checked": r2_cols,
                     "v3_columns_that_differ": diff_cols,
                     "v3_round1_profit_total_diff_whole_horizon": float(p_wk_diff.sum()),
                     "v3_round1_profit_weeks_differ": int((p_wk_diff.abs() > 1e-6).sum()),
                     "inventory_group_columns_same": inv_same,
                     "ppc_comparison_moved_rows": moved,
                     "ppc_freight_row_same": pr(cc, "費用 運賃") == pr(c0, "費用 運賃"),
                     "ppc_profit_total_same": pr(cc, "利益 合計") == pr(c0, "利益 合計"),
                     "conservation_all_ok": bool(cons.ok.all()),
                     "ok": r2_same and inv_same and bool(cons.ok.all()) and pr(cc, "利益 合計") == pr(c0, "利益 合計")
                     and pr(cc, "費用 運賃") == pr(c0, "費用 運賃") and len(moved) == 2
                     and all(v == -TOTAL for v in moved.values())}
        if out_dir:
            lot_rows(m).to_csv(os.path.join(out_dir, "t1_cif_lot_money_lines.csv"), index=False, encoding="utf-8")
            lot_rows(m0).to_csv(os.path.join(out_dir, "t0_lot_money_lines.csv"), index=False, encoding="utf-8")
    else:
        for k in ("V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8"):
            res[k] = {"skipped": True}

    def same_outputs(da, db, ignore_checks_keys=()):
        same = {}
        for fn in sorted(os.listdir(da)):
            pa, pb = os.path.join(da, fn), os.path.join(db, fn)
            if fn in ("vc_run_info.json", "ppc") or os.path.isdir(pa):
                continue
            if not os.path.exists(pb):
                same[fn] = False
            elif fn == "vc_shipments.csv.gz":      # plan_id carries the git state
                same[fn] = ships(da).drop(columns=["plan_id"]).equals(ships(db).drop(columns=["plan_id"]))
            elif fn == "vc_checks.json":
                ja, jb = (json.load(open(x, encoding="utf-8")) for x in (pa, pb))
                for k in ignore_checks_keys:
                    ja.pop(k, None), jb.pop(k, None)
                same[fn] = ja == jb
            else:
                same[fn] = (gz_sha(pa) == gz_sha(pb)) if fn.endswith(".gz") else sha(pa) == sha(pb)
        extra = sorted(set(os.listdir(db)) - set(os.listdir(da)))
        return same, extra

    db = os.path.join(g, "t1_buyer")
    if has(db, d0):
        same, extra = same_outputs(d0, db, ignore_checks_keys=("trade_terms",))
        res["V9"] = {"files": same, "extra_files": extra,
                     "note": "vc_checks.json は trade_terms の記録（表の内容）を除いて比べた",
                     "ok": all(same.values()) and not extra}
    else:
        res["V9"] = {"skipped": True}
    df_, do = os.path.join(g, "t1_cif_first"), os.path.join(g, "t1_cif_other")
    if has(df_, dc, do):
        files = ("vc_money_lines.csv.gz", "vc_inventory_weekly.csv", "vc_unrealized_weekly.csv", "vc_v2_weekly.csv")
        h = {fn: [gz_sha(os.path.join(x, fn)) if fn.endswith(".gz") else sha(os.path.join(x, fn)) for x in (df_, dc, do)]
             for fn in files}
        res["V10"] = {"same": {fn: len(set(v)) == 1 for fn, v in h.items()}, "ok": all(len(set(v)) == 1 for v in h.values())}
    else:
        res["V10"] = {"skipped": True}
    ds = os.path.join(g, "t1_sample")
    if has(ds, d0):
        same, extra = same_outputs(d0, ds)
        res["V11a"] = {"files": same, "extra_files": extra, "ok": all(same.values()) and not extra}
    else:
        res["V11a"] = {"skipped": True}
    pc = {}
    for b in ("t1_sample", "t1_cif", "t1_buyer"):
        pa, pb = os.path.join(d0, "ppc"), os.path.join(g, b, "ppc")
        if has(pa, pb):
            pc[f"t0 vs {b}"] = {fn: os.path.exists(os.path.join(pb, fn)) and sha(os.path.join(pa, fn)) == sha(os.path.join(pb, fn))
                                for fn in sorted(os.listdir(pa))}
    res["V11b"] = {"pairs": pc, "ok": bool(pc) and all(all(v.values()) for v in pc.values())}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--g5-dir", default="output/g5_trial")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.out:
        os.makedirs(a.out, exist_ok=True)
    res = {"T0": check_t0(a.g5_dir), "T1": check_t1(a.g5_dir, a.out)}
    res["summary"] = {f"{s}.{k}": (None if v.get("ok") is None else bool(v.get("ok")))
                      for s in ("T0", "T1") for k, v in res[s].items() if isinstance(v, dict)}
    s = json.dumps(res, ensure_ascii=False, indent=1,
                   default=lambda o: None if (isinstance(o, float) and math.isnan(o)) else
                   (bool(o) if type(o).__name__ == "bool_" else (int(o) if type(o).__name__.startswith("int") else str(o))))
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1))
    if a.out:
        with open(os.path.join(a.out, "check_g5_result.json"), "w", encoding="utf-8") as f:
            f.write(s)


if __name__ == "__main__":
    main()
