# -*- coding: utf-8 -*-
"""
check_g4.py — G4（タイ向けの関税の課税価格）の照合。出力のファイルとモデルの CSV を読むだけ
（WOM を import しない）。G2 の check_g2.py の作りに倣う。

    python docs/development/WOM_BSSEAF_Cosmetics_G4_TariffBase_appendix/check_g4.py --g4-dir output/g4_trial --out <appendix>

前提のフォルダ（依頼書 §3・§5）：
    <g4-dir>/t0_0, t0_30         正式なサンプル／その 30% の写し（model_t0_30）。コードの改修前
    <g4-dir>/t1_sample           正式なサンプル（改修後のコード、表なし）
    <g4-dir>/t1_a0, t1_a30, t1_b30, t1_err30, t1_ins   写しのモデル（model_*）の実行
    <g4-dir>/t1_a30_first, t1_a30_other               model_a30 の 1 回目の写し・別の場所の実行（V10）
段の出力が無ければ、その照合は飛ばす（"skipped"）。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

LOT = "COS_Cream:TH_Distributor:2029-W03:00003"
EDGE = "WH_JP_Released->DC_TH"
SHIP = "ship:COS_Cream:OUT:dad:WH_JP_Released:COS_Cream:120:12"
SHIP_WEEK, RCPT_WEEK, TRANSIT_WEEK = "2028-W52", "2029-W02", "2029-W01"
EXPECT_CV = 121_680.0
EXPECT_DUTY30 = 36_504.0
EXPECT_COGS_T0 = 49_056.0
EXPECT_TOTAL30 = 27_959_256.0
EXPECT_SPLIT30 = {"COS_Cream": 10_914_696.0, "COS_Serum": 17_044_560.0}
EXPECT_CV_TOTAL = 93_197_520.0
EXPECT_PPC30 = 27_612_000.0
EXPECT_DIFF = 347_256.0
N_SHIP = 689
COLS = ["line_id", "week", "src_id", "kind", "scope", "basis", "family", "price_type", "entity", "node",
        "counterparty", "amount_orig", "currency_orig", "amt_hq", "valued", "note"]


def money(d):
    return pd.read_csv(os.path.join(d, "vc_money_lines.csv.gz"), low_memory=False)


def ships(d):
    return pd.read_csv(os.path.join(d, "vc_shipments.csv.gz"), dtype=str)


def cvrec(d):
    return pd.read_csv(os.path.join(d, "vc_customs_valuation.csv"), dtype={"duty_line_id": str})


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


def has(*ds):
    return all(os.path.isdir(d) for d in ds)


def duty_of(cv, rate):
    return float((Decimal(repr(float(cv))) * Decimal(repr(float(rate)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def edge_tariff(m, sh):
    ids = set(sh.loc[sh.edge == EDGE, "ship_id"])
    return m[(m.family == "tariff") & m.src_id.isin(ids)]


def ppc_tariff(d):
    e = pd.read_csv(os.path.join(d, "ppc", "ppc_event_ledger.csv"), low_memory=False)
    t = e[(e.ppc_event_type == "tariff_cost") & (e.edge_id == EDGE)]
    return float((t.amount_base * t.qty).sum()), int(len(t))


def cmp_row(d, prefix):
    c = pd.read_csv(os.path.join(d, "vc_ppc_comparison.csv"), encoding="utf-8")
    r = c[c["item"].astype(str).str.startswith(prefix)]
    return r.iloc[-1].to_dict() if len(r) else None


def lot_rows(m):
    return m[m.lot_id == LOT][COLS]


# ── T0（B1〜B4）────────────────────────────────────────────────────
def check_t0(g):
    d0, d30 = os.path.join(g, "t0_0"), os.path.join(g, "t0_30")
    if not has(d0, d30):
        return {"skipped": True}
    sh = ships(d0)
    lot = sh[sh.lot_id == LOT]
    e = lot[lot.edge == EDGE].iloc[0]
    dc = lot[lot.node == "DC_TH"].iloc[0]
    out = {"B1": {"ship_id": e.ship_id, "ship_week": e.ship_week, "arrival_week": e.arrival_week,
                  "dc_th_ship_week": dc.ship_week,
                  "ok": e.ship_id == SHIP and e.ship_week == SHIP_WEEK and e.arrival_week == RCPT_WEEK
                  and dc.ship_week == RCPT_WEEK}}
    m0 = money(d0)
    t = edge_tariff(m0, sh).merge(sh[["ship_id", "ship_week"]], left_on="src_id", right_on="ship_id")
    out["B2"] = {"lines": int(len(t)), "sum": float(t.amt_hq.sum()), "at_ship_week": bool((t.week == t.ship_week).all()),
                 "ok": len(t) == N_SHIP and float(t.amt_hq.abs().sum()) == 0.0 and bool((t.week == t.ship_week).all())}
    m30 = money(d30)
    t30 = edge_tariff(m30, ships(d30))
    lt = t30[t30.src_id == SHIP]
    pt, _ = ppc_tariff(d30)
    out["B3"] = {"lot_lines": lt[["week", "amt_hq"]].to_dict("records"), "vc_total": float(t30.amt_hq.sum()),
                 "ppc_total": pt,
                 "ok": len(lt) == 1 and lt.iloc[0].week == SHIP_WEEK and float(lt.iloc[0].amt_hq) == 36_000.0
                 and float(t30.amt_hq.sum()) == EXPECT_PPC30 and pt == EXPECT_PPC30}
    c = m0[(m0.lot_id == LOT) & (m0.kind == "cogs") & (m0.basis == "group") & (m0.week == RCPT_WEEK)]
    out["B4"] = {"cogs_group": float(c.amt_hq.sum()), "ok": float(c.amt_hq.sum()) == EXPECT_COGS_T0}
    return out


def lot_cv(cv):
    r = cv[cv.ship_id == SHIP]
    return r.iloc[0] if len(r) == 1 else None


# ── T1（V1〜V11）───────────────────────────────────────────────────
def check_t1(g, out_dir):
    res = {}
    da0, da30 = os.path.join(g, "t1_a0"), os.path.join(g, "t1_a30")
    d0, d30 = os.path.join(g, "t0_0"), os.path.join(g, "t0_30")

    if has(da0):
        cv, m, sh = cvrec(da0), money(da0), ships(da0)
        r = lot_cv(cv)
        lt = m[(m.family == "tariff") & (m.src_id == SHIP)]
        res["V1"] = {"goods_value": r.goods_value, "freight_added": r.freight_added,
                     "insurance_added": r.insurance_added, "customs_value": r.customs_value, "duty": r.duty,
                     "duty_week": r.duty_week, "tariff_lines": int(len(lt)),
                     "ok": r.goods_value == 120_000 and r.freight_added == 1_680 and r.insurance_added == 0
                     and r.customs_value == EXPECT_CV and r.duty == 0 and r.duty_week == RCPT_WEEK
                     and len(lt) == 0 and pd.isna(r.duty_line_id)}
        et = edge_tariff(m, sh)
        pt, _ = ppc_tariff(da0)
        res["V8"] = {"rows": int(len(cv)), "customs_value_total": float(cv.customs_value.sum()),
                     "duty_total": float(cv.duty.sum()), "edge_tariff_lines": int(len(et)), "ppc_tariff": pt,
                     "ok": len(cv) == N_SHIP and float(cv.customs_value.sum()) == EXPECT_CV_TOTAL
                     and float(cv.duty.abs().sum()) == 0 and len(et) == 0 and pt == 0}
    else:
        res["V1"] = res["V8"] = {"skipped": True}

    if has(da30):
        cv, m, sh = cvrec(da30), money(da30), ships(da30)
        r = lot_cv(cv)
        lt = m[(m.family == "tariff") & (m.src_id == SHIP)]
        lt_lot = m[(m.family == "tariff") & (m.lot_id == LOT) & (m.node == "DC_TH") & (m.kind == "acquisition")]
        ok = (len(lt) == 1 and lt.iloc[0].week == RCPT_WEEK and float(lt.iloc[0].amt_hq) == EXPECT_DUTY30
              and lt.iloc[0].entity == "E_JP" and lt.iloc[0].node == "DC_TH"
              and str(int(lt.iloc[0].line_id)) == str(r.duty_line_id)
              and not ((lt_lot.week == SHIP_WEEK) | (lt_lot.week == TRANSIT_WEEK)).any())
        res["V2"] = {"lines": lt[["line_id", "week", "entity", "node", "kind", "basis", "amt_hq", "src_id", "note"]]
                     .to_dict("records"), "duty_line_id": r.duty_line_id,
                     "lines_at_ship_or_transit_week": int(((lt_lot.week == SHIP_WEEK) | (lt_lot.week == TRANSIT_WEEK)).sum()),
                     "ok": bool(ok)}
        c = m[(m.lot_id == LOT) & (m.kind == "cogs") & (m.week == RCPT_WEEK) & m.basis.isin(["group", "entity"])]
        cg = {b: float(c[c.basis == b].amt_hq.sum()) for b in ("entity", "group")}
        res["V3"] = {"cogs": cg, "ok": cg["group"] == EXPECT_COGS_T0 + EXPECT_DUTY30 == 85_560
                     and cg["entity"] == 85_560}
        # V6 totals + per-shipment identity
        et = edge_tariff(m, sh)
        cv_ok = all(duty_of(a, b) == d for a, b, d in zip(cv.customs_value, cv.tariff_rate, cv.duty))
        split = {p: float(g_.amt_hq.sum()) for p, g_ in et.groupby("product")}
        cv_split = {p: float(g_.customs_value.sum()) for p, g_ in cv.groupby("product")}
        res["V6"] = {"lines": int(len(et)), "total": float(et.amt_hq.sum()), "split": split,
                     "customs_value_total": float(cv.customs_value.sum()), "customs_value_split": cv_split,
                     "duty_equals_cv_x_rate_all": cv_ok, "rate_all_0.3": bool((cv.tariff_rate == 0.3).all()),
                     "ok": len(et) == N_SHIP and float(et.amt_hq.sum()) == EXPECT_TOTAL30 and split == EXPECT_SPLIT30
                     and float(cv.customs_value.sum()) == EXPECT_CV_TOTAL and cv_ok}
        # detail join: entity x week x shipment (共通照合表 §3)
        j = et.merge(cv, left_on="src_id", right_on="ship_id", how="outer", indicator=True, suffixes=("", "_cv"))
        j = j.merge(sh[["ship_id", "arrival_week"]], on="ship_id", how="left")
        both = j[j["_merge"] == "both"]
        det = {"joined": int(len(both)), "only_lines": int((j["_merge"] == "left_only").sum()),
               "only_records": int((j["_merge"] == "right_only").sum()),
               "week_eq_duty_week": bool((both.week == both.duty_week).all()),
               "duty_week_eq_arrival": bool((both.duty_week == both.arrival_week).all()),
               "entity_eq": bool((both.entity == both.entity_cv).all()),
               "amount_eq": bool((both.amt_hq == both.duty).all()),
               "line_id_eq": bool((both.line_id.astype(int).astype(str) == both.duty_line_id).all())}
        det["ok"] = (det["joined"] == N_SHIP and det["only_lines"] == 0 and det["only_records"] == 0
                     and all(v for k, v in det.items() if k not in ("joined", "only_lines", "only_records")))
        res["V6_detail"] = det
        # V7 PPC
        pt, pn = ppc_tariff(da30)
        t_row, t_row0 = cmp_row(da30, "費用 関税"), cmp_row(d30, "費用 関税") if has(d30) else None
        p_row, p_row0 = cmp_row(da30, "利益"), cmp_row(d30, "利益") if has(d30) else None
        dt = t_row["difference_ledger_minus_ppc"]
        dp = p_row["difference_ledger_minus_ppc"] - (p_row0["difference_ledger_minus_ppc"] if p_row0 else 0)
        dvc = p_row["ledger_v3"] - (p_row0["ledger_v3"] if p_row0 else 0)
        res["V7"] = {"ppc_tariff": pt, "ppc_rows": pn, "vc_ppc_tariff_row": t_row,
                     "profit_row": p_row, "profit_row_t0_30": p_row0,
                     "tariff_diff": dt, "profit_diff_change_from_t0_30": dp, "ledger_profit_change": dvc,
                     "ok": pt == EXPECT_PPC30 and dt == EXPECT_DIFF and dp == -EXPECT_DIFF and dvc == -EXPECT_DIFF}
        if out_dir:
            lot_rows(m).to_csv(os.path.join(out_dir, "t1_a30_lot_money_lines.csv"), index=False, encoding="utf-8")
            cv[cv.lot_id == LOT].to_csv(os.path.join(out_dir, "t1_a30_lot_customs_valuation.csv"), index=False)
    else:
        for k in ("V2", "V3", "V6", "V6_detail", "V7"):
            res[k] = {"skipped": True}

    db, de = os.path.join(g, "t1_b30"), os.path.join(g, "t1_err30")
    if has(db, da30):
        cb, ca = cvrec(db), cvrec(da30)
        r = lot_cv(cb)
        mm = ca.merge(cb, on="ship_id", suffixes=("_a", "_b"))
        res["V4"] = {"customs_value": r.customs_value, "duty": r.duty, "freight_added": r.freight_added,
                     "same_as_a30_all": bool(len(mm) == N_SHIP and (mm.customs_value_a == mm.customs_value_b).all()
                                             and (mm.duty_a == mm.duty_b).all()),
                     "ok": r.customs_value == EXPECT_CV and r.duty == EXPECT_DUTY30 and r.freight_added == 0
                     and len(mm) == N_SHIP and bool((mm.customs_value_a == mm.customs_value_b).all())
                     and bool((mm.duty_a == mm.duty_b).all())}
        if out_dir:
            cb[cb.lot_id == LOT].to_csv(os.path.join(out_dir, "t1_b30_lot_customs_valuation.csv"), index=False)
    else:
        res["V4"] = {"skipped": True}
    if has(de):
        r = lot_cv(cvrec(de))
        judged_ok = r.customs_value == EXPECT_CV            # the check the script applies
        res["V5"] = {"customs_value": r.customs_value, "duty": r.duty,
                     "script_judgement": "期待（121,680）と一致" if judged_ok else "期待（121,680）と違う",
                     "ok": (not judged_ok) and r.customs_value == 123_360 and r.duty == 37_008}
    else:
        res["V5"] = {"skipped": True}

    di = os.path.join(g, "t1_ins")
    if has(di):
        cv, m, sh = cvrec(di), money(di), ships(di)
        et = edge_tariff(m, sh)
        iss = [x for x in checks_json(di)["issues"] if x.get("issue") == "customs_value_unvalued"]
        res["V9"] = {"customs_value_all_nan": bool(cv.customs_value.isna().all()),
                     "status": cv.status.value_counts().to_dict(), "edge_tariff_lines": int(len(et)),
                     "lines_nan": bool(et.amt_hq.isna().all()), "lines_valued": int(et.valued.sum()),
                     "issues": iss,
                     "ok": bool(cv.customs_value.isna().all()) and set(cv.status) == {"unvalued_insurance"}
                     and len(et) == N_SHIP and bool(et.amt_hq.isna().all()) and int(et.valued.sum()) == 0
                     and len(iss) == 2}
    else:
        res["V9"] = {"skipped": True}

    df, do = os.path.join(g, "t1_a30_first"), os.path.join(g, "t1_a30_other")
    if has(df, da30, do):
        files = ("vc_money_lines.csv.gz", "vc_customs_valuation.csv", "vc_inventory_weekly.csv")
        h = {fn: [gz_sha(os.path.join(x, fn)) if fn.endswith(".gz") else sha(os.path.join(x, fn))
                  for x in (df, da30, do)] for fn in files}
        res["V10"] = {"same": {fn: len(set(v)) == 1 for fn, v in h.items()}, "ok": all(len(set(v)) == 1 for v in h.values())}
    else:
        res["V10"] = {"skipped": True}

    # V11 (a) official sample: same as T0
    ds = os.path.join(g, "t1_sample")
    if has(ds, d0):
        same = {}
        for fn in sorted(os.listdir(d0)):
            p0, p1 = os.path.join(d0, fn), os.path.join(ds, fn)
            if fn in ("vc_run_info.json", "ppc") or os.path.isdir(p0):
                continue
            if fn == "vc_shipments.csv.gz":     # plan_id carries the git state (clean / +dirty): compare without it
                same[fn] = os.path.exists(p1) and ships(d0).drop(columns=["plan_id"]).equals(ships(ds).drop(columns=["plan_id"]))
                continue
            same[fn] = os.path.exists(p1) and ((gz_sha(p0) == gz_sha(p1)) if fn.endswith(".gz") else sha(p0) == sha(p1))
        extra = sorted(set(os.listdir(ds)) - set(os.listdir(d0)))
        res["V11a"] = {"files": same, "extra_files": extra, "ok": all(same.values()) and not extra}
    else:
        res["V11a"] = {"skipped": True}
    # V11 (b) a0 = T0 minus the 689 zero tariff lines of the edge (without line_id)
    if has(da0, d0):
        m0, ma = money(d0), money(da0)
        drop = edge_tariff(m0, ships(d0))
        rest0 = m0.drop(index=drop.index).drop(columns=["line_id"]).reset_index(drop=True)
        resta = ma.drop(columns=["line_id"]).reset_index(drop=True)
        eq = rest0.shape == resta.shape and rest0.astype(str).equals(resta.astype(str))
        res["V11b"] = {"t0_lines": int(len(m0)), "dropped": int(len(drop)), "dropped_all_zero": float(drop.amt_hq.abs().sum()) == 0,
                       "a0_lines": int(len(ma)), "ok": bool(eq) and len(drop) == N_SHIP}
    else:
        res["V11b"] = {"skipped": True}
    # V11 (c) PPC outputs byte-identical for the same inputs
    pairs = [("t0_0", "t1_sample"), ("t0_0", "t1_a0"), ("t0_30", "t1_a30"), ("t0_30", "t1_b30")]
    pc = {}
    for a, b in pairs:
        pa, pb = os.path.join(g, a, "ppc"), os.path.join(g, b, "ppc")
        if not has(pa, pb):
            continue
        pc[f"{a} vs {b}"] = {fn: os.path.exists(os.path.join(pb, fn)) and sha(os.path.join(pa, fn)) == sha(os.path.join(pb, fn))
                             for fn in sorted(os.listdir(pa))}
    res["V11c"] = {"pairs": pc, "ok": bool(pc) and all(all(v.values()) for v in pc.values())}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--g4-dir", default="output/g4_trial")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.out:
        os.makedirs(a.out, exist_ok=True)
    res = {"T0": check_t0(a.g4_dir), "T1": check_t1(a.g4_dir, a.out)}
    if a.out and os.path.isdir(os.path.join(a.g4_dir, "t0_30")):
        lot_rows(money(os.path.join(a.g4_dir, "t0_30"))).to_csv(
            os.path.join(a.out, "t0_30_lot_money_lines.csv"), index=False, encoding="utf-8")
    flat = {f"{s}.{k}": (None if v.get("ok") is None else bool(v.get("ok"))) for s in ("T0", "T1") for k, v in res[s].items() if isinstance(v, dict)}
    res["summary"] = flat
    s = json.dumps(res, ensure_ascii=False, indent=1, default=lambda o: None if (isinstance(o, float) and math.isnan(o)) else str(o))
    print(json.dumps(flat, ensure_ascii=False, indent=1))
    if a.out:
        with open(os.path.join(a.out, "check_g4_result.json"), "w", encoding="utf-8") as f:
            f.write(s)


if __name__ == "__main__":
    main()
