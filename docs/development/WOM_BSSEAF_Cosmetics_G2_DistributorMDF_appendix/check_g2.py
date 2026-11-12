# -*- coding: utf-8 -*-
"""
check_g2.py — G2（代理店向けの販促協賛金、MDF）の照合。出力のファイルとモデルの CSV を読むだけ
（WOM を import しない）。G1 の check_g1.py の作りに倣う。

    python docs/development/WOM_BSSEAF_Cosmetics_G2_DistributorMDF_appendix/check_g2.py --g2-dir output/g2_trial --out <appendix>

前提のフォルダ（依頼書 §3・§5）：
    <g2-dir>/t0              正式なサンプル（コードの改修前）
    <g2-dir>/t1              model_t1（区間の運賃の 4 行に卸価格の 5% を足した写し）
    <g2-dir>/model_t2        正式なサンプルの写し ＋ vc_sales_cost_rule.csv に 4 行
    <g2-dir>/t2, t2_first, t2_b   model_t2 の実行（同じ場所に 2 回・その 1 回目の写し・別の場所）
    <g2-dir>/t2_norule       model_t2 から表の 4 行を除いた写しの実行（V7）
    <g2-dir>/t0_after        正式なサンプル（改修後のコード）
    <g2-dir>/sample_hash_before.txt
段の出力が無ければ、その段の照合は飛ばす（"skipped"）。
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

SG_LOT = "COS_Cream:SG_Distributor:2028-W29:00002"
TH_LOT = "COS_Cream:TH_Distributor:2029-W03:00003"
SG_SRC = "ship:COS_Cream:OUT:dad:DC_SG:COS_Cream:96:6"
DIST = ("SG_Distributor", "TH_Distributor")
EXPECT_TOTAL = 22_196_148
EXPECT_SPLIT = {("COS_Cream", "SG_Distributor"): 6_451_224, ("COS_Serum", "SG_Distributor"): 9_160_164,
                ("COS_Cream", "TH_Distributor"): 2_583_360, ("COS_Serum", "TH_Distributor"): 4_001_400}
EXPECT_SALES = 2_340
D4_ISSUE = "revenue_based_cost_on_external_channel_not_booked"
COLS = ["week", "src_id", "kind", "scope", "basis", "family", "price_type", "entity", "node",
        "counterparty", "amount_orig", "currency_orig", "amt_hq", "note"]


def money(d):
    return pd.read_csv(os.path.join(d, "vc_money_lines.csv.gz"), low_memory=False)


def checks_json(d):
    with open(os.path.join(d, "vc_checks.json"), encoding="utf-8") as f:
        return json.load(f)


def gz_sha(p):
    with gzip.open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def ppc_profit_diff(d):
    c = pd.read_csv(os.path.join(d, "vc_ppc_comparison.csv"))
    r = c[c["item"].str.startswith("利益 合計")].iloc[0]
    return float(r["difference_ledger_minus_ppc"])


def wholesale(m):
    """the external wholesale revenue lines (one per sale to an external distributor)"""
    return m[(m.kind == "revenue") & (m.scope == "external") & (m.price_type == "wholesale")]


def dist_freight(m):
    return m[(m.kind == "expense") & (m.scope == "selling") & (m.price_type == "logistics_cost")
             & m.counterparty.isin(["EXT_CH_SG_DIST", "EXT_CH_TH_DIST"])]


def lot_rows(m, lot):
    return m[m.lot_id == lot][COLS]


def r2(x):
    return float(Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def norm(m, drop_line_id=True):
    x = m.copy()
    if drop_line_id:
        x = x.drop(columns=["line_id"])
    return x.reset_index(drop=True)


def check_t0(g2):
    d = os.path.join(g2, "t0")
    m = money(d)
    out = {}
    sg = m[(m.lot_id == SG_LOT) & (m.price_type == "wholesale") & (m.kind == "revenue")]
    th = m[(m.lot_id == TH_LOT) & (m.price_type == "wholesale") & (m.kind == "revenue")]
    out["B1"] = {
        "sg": {"week": sg.week.tolist(), "amount": sg.amount_orig.tolist(), "ccy": sg.currency_orig.tolist(),
               "src_id": sg.src_id.tolist()},
        "th": {"week": th.week.tolist(), "amount": th.amount_orig.tolist(), "ccy": th.currency_orig.tolist(),
               "src_id": th.src_id.tolist()},
    }
    out["B1"]["ok"] = (sg.week.tolist() == ["2028-W28"] and sg.amount_orig.tolist() == [1488.0]
                       and sg.src_id.tolist() == [SG_SRC] and th.week.tolist() == ["2029-W02"]
                       and th.amount_orig.tolist() == [38400.0])
    dist_lines = m[m.node.isin(DIST) & (m.family == "marketing_cost")]
    mdf_lines = m[m.price_type.isin(["distributor_mdf", "marketing_cost"]) & m.node.isin(DIST)]
    iss = checks_json(d)["issues"]
    out["B2"] = {"mdf_lines_at_distributor": int(len(dist_lines) + len(mdf_lines)),
                 "issues": iss, "ok": len(dist_lines) == 0 and len(mdf_lines) == 0 and len(iss) == 0}
    diff = ppc_profit_diff(d)
    out["B3"] = {"profit_diff_vc_minus_ppc": diff, "ok": abs(diff - EXPECT_TOTAL) < 0.5}
    out["external_wholesale_sales"] = int(len(wholesale(m)))
    return out, m


def check_t1(g2, m0):
    d = os.path.join(g2, "t1")
    if not os.path.exists(os.path.join(d, "vc_money_lines.csv.gz")):
        return {"skipped": True}
    m1 = money(d)
    f0, f1 = dist_freight(m0), dist_freight(m1)
    out = {}
    rep = {}
    for lot, inc, ccy in ((SG_LOT, 74.4, "SGD"), (TH_LOT, 1920.0, "THB")):
        a, b = f0[f0.lot_id == lot], f1[f1.lot_id == lot]
        rep[lot] = {"t0": a[["week", "amount_orig", "currency_orig"]].values.tolist(),
                    "t1": b[["week", "amount_orig", "currency_orig"]].values.tolist(),
                    "increase": float(b.amount_orig.sum() - a.amount_orig.sum()),
                    "ok": len(a) == 1 and len(b) == 1 and a.week.iloc[0] == b.week.iloc[0]
                    and abs(b.amount_orig.sum() - a.amount_orig.sum() - inc) < 1e-6
                    and b.currency_orig.iloc[0] == ccy}
    out["(1)"] = rep
    j = f0[["line_id", "amount_orig", "amt_hq"]].merge(f1[["line_id", "amount_orig", "amt_hq"]], on="line_id",
                                                      suffixes=("_0", "_1"))
    inc_rows = j[(j.amt_hq_1 - j.amt_hq_0).abs() > 1e-9]
    inc_hq = float((j.amt_hq_1 - j.amt_hq_0).sum())
    out["(2)"] = {"rows_increased": int(len(inc_rows)), "increase_jpy": inc_hq,
                  "ok": len(j) == len(f0) == len(f1) and len(inc_rows) == EXPECT_SALES
                  and abs(inc_hq - EXPECT_TOTAL) < 0.5}
    # (3) all other lines equal
    keep = ~m0.line_id.isin(f0.line_id)
    a = m0[keep].reset_index(drop=True)
    b = m1[~m1.line_id.isin(f1.line_id)].reset_index(drop=True)
    same_other = a.equals(b)
    fa = f0.drop(columns=["amount_orig", "amt_hq", "amt_common", "amt_func", "amt_local"]).reset_index(drop=True)
    fb = f1.drop(columns=["amount_orig", "amt_hq", "amt_common", "amt_func", "amt_local"]).reset_index(drop=True)
    out["(3)"] = {"other_lines_equal": bool(same_other), "freight_lines_equal_except_amount": bool(fa.equals(fb)),
                  "ok": bool(same_other and fa.equals(fb))}
    out["ok"] = all(v["ok"] for v in rep.values()) and out["(2)"]["ok"] and out["(3)"]["ok"]
    return out


def check_t2(g2, m0, appendix):
    d = os.path.join(g2, "t2")
    if not os.path.exists(os.path.join(d, "vc_money_lines.csv.gz")):
        return {"skipped": True}
    m = money(d)
    mdf = m[m.price_type == "distributor_mdf"]
    ws = wholesale(m)
    out = {}
    # V1 / V2
    rep = {}
    for lot, wk, wk_next, amt, ccy, ent, node, cp in (
            (SG_LOT, "2028-W28", "2028-W29", 74.40, "SGD", "E_SG", "DC_SG", "EXT_CH_SG_DIST"),
            (TH_LOT, "2029-W02", "2029-W03", 1920.00, "THB", "E_JP", "DC_TH", "EXT_CH_TH_DIST")):
        x = mdf[mdf.lot_id == lot]
        w = ws[ws.lot_id == lot]
        r = {"rows": x[COLS].to_dict("records"), "rows_next_week": int((x.week == wk_next).sum())}
        r["ok"] = (len(x) == 1 and x.week.iloc[0] == wk and abs(x.amount_orig.iloc[0] - amt) < 1e-9
                   and x.currency_orig.iloc[0] == ccy and x.entity.iloc[0] == ent and x.node.iloc[0] == node
                   and x.counterparty.iloc[0] == cp and x.src_id.iloc[0] == w.src_id.iloc[0]
                   and x.kind.iloc[0] == "expense" and x.scope.iloc[0] == "selling"
                   and x.family.iloc[0] == "marketing_cost" and x.basis.iloc[0] == "v1,entity,group"
                   and r["rows_next_week"] == 0)
        rep[lot] = r
        if appendix:
            lot_rows(m, lot).to_csv(os.path.join(appendix, f"t2_{lot.split(':')[1]}_lot_money_lines.csv"),
                                    index=False, encoding="utf-8")
            lot_rows(m0, lot).to_csv(os.path.join(appendix, f"t0_{lot.split(':')[1]}_lot_money_lines.csv"),
                                     index=False, encoding="utf-8")
    out["V1"], out["V2"] = rep[SG_LOT], rep[TH_LOT]
    out["V2"]["amt_hq"] = float(mdf[mdf.lot_id == TH_LOT].amt_hq.iloc[0])
    # V3
    cnt = mdf.groupby("src_id").size()
    ws_src = set(ws.src_id)
    out["V3"] = {"wholesale_sales": int(len(ws)), "mdf_rows": int(len(mdf)),
                 "sales_with_exactly_one": int(sum(cnt.get(s, 0) == 1 for s in ws_src)),
                 "mdf_from_non_wholesale": int((~mdf.src_id.isin(ws_src)).sum())}
    out["V3"]["ok"] = (len(ws) == EXPECT_SALES and out["V3"]["sales_with_exactly_one"] == EXPECT_SALES
                       and out["V3"]["mdf_from_non_wholesale"] == 0 and len(mdf) == EXPECT_SALES)
    # V4
    j = mdf.merge(ws[["src_id", "amount_orig", "currency_orig", "week"]], on="src_id", suffixes=("", "_ws"))
    exp = j.amount_orig_ws.map(lambda v: r2(v * 0.05))
    out["V4"] = {"amount_mismatch": int(((j.amount_orig - exp).abs() > 1e-9).sum()),
                 "currency_mismatch": int((j.currency_orig != j.currency_orig_ws).sum()),
                 "week_mismatch": int((j.week != j.week_ws).sum()), "rows": int(len(j))}
    out["V4"]["ok"] = (len(j) == EXPECT_SALES and out["V4"]["amount_mismatch"] == 0
                       and out["V4"]["currency_mismatch"] == 0 and out["V4"]["week_mismatch"] == 0)
    # V5
    to_leaf = mdf.note.str.replace("販促の対象：", "", regex=False)
    split = mdf.assign(leaf=to_leaf).groupby(["product", "leaf"]).amt_hq.sum()
    total = float(mdf.amt_hq.sum())
    out["V5"] = {"total_jpy": total, "split": {f"{p}|{l}": float(v) for (p, l), v in split.items()}}
    out["V5"]["ok"] = (abs(total - EXPECT_TOTAL) < 0.5
                       and all(abs(split.get(k, 0) - v) < 0.5 for k, v in EXPECT_SPLIT.items()))
    # V6
    diff = ppc_profit_diff(d)
    ppc_ev = pd.read_csv(os.path.join(d, "ppc", "ppc_event_ledger.csv"), low_memory=False)
    out["V6"] = {"profit_diff_vc_minus_ppc": diff}
    mdf = mdf.copy()
    # PPC books the distributor's marketing_cost (ppc_node_cost_rule.csv) at the distributor leaf's
    # shipment week; the Value Chain books the MDF at the wholesale (DC shipment) week.
    # one PPC event = node x product x week; amount_base / amount_per_unit_base are per unit (x qty)
    sel = ppc_ev[ppc_ev.node_id.isin(DIST) & (ppc_ev.ppc_event_type == "marketing_cost")].copy()
    sel["amount_total_base"] = sel.amount_per_unit_base * sel.qty
    ppc_total = float(sel.amount_total_base.sum())
    out["V6"]["ppc_distributor_marketing_total"] = ppc_total
    out["V6"]["ppc_distributor_marketing_events"] = int(len(sel))
    out["V6"]["vc_mdf_total"] = float(mdf.amt_hq.sum())
    leaf = mdf.note.str.replace("販促の対象：", "", regex=False)
    vcw = mdf.assign(leaf=leaf).groupby(["leaf", "product", "week"]).amt_hq.sum()
    ppw = sel.groupby(["node_id", "product_id", "week"]).amount_total_base.sum()
    weeks = sorted(set(m.week.unique()))
    nxt = {w: weeks[i + 1] for i, w in enumerate(weeks[:-1])}
    vc_shift = {}
    for (l, p, w), v in vcw.items():
        k = (l, p, nxt.get(w, "after_horizon"))
        vc_shift[k] = vc_shift.get(k, 0.0) + v
    keys = set(vc_shift) | set(ppw.index)
    same_week = sum(1 for k in set(vcw.index) | set(ppw.index) if abs(vcw.get(k, 0) - ppw.get(k, 0)) < 0.5)
    shifted = sum(1 for k in keys if abs(vc_shift.get(k, 0) - ppw.get(k, 0)) < 0.5)
    out["V6"]["weekly"] = {"cells_vc_week_plus_1_vs_ppc": len(keys), "cells_equal_after_shift": shifted,
                           "cells_equal_same_week": same_week,
                           "note": "PPC は代理店の leaf の出荷の週（卸売の週の 1 週後）に立てる"}
    out["V6"]["ok"] = abs(diff) < 0.5 and abs(ppc_total - out["V6"]["vc_mdf_total"]) < 0.5
    # V7
    iss = checks_json(d)["issues"]
    d4 = [i for i in iss if i.get("issue") == D4_ISSUE]
    out["V7"] = {"t2_d4": len(d4), "t2_issues": iss}
    nd = os.path.join(g2, "t2_norule")
    if os.path.exists(os.path.join(nd, "vc_checks.json")):
        iss_n = checks_json(nd)["issues"]
        d4n = [i for i in iss_n if i.get("issue") == D4_ISSUE]
        out["V7"]["norule_d4"] = d4n
        out["V7"]["norule_other_issues"] = [i for i in iss_n if i.get("issue") != D4_ISSUE]
    t0_iss = checks_json(os.path.join(g2, "t0"))["issues"]
    out["V7"]["ok"] = (len(d4) == 0 and len(out["V7"].get("norule_d4", [])) == 4
                       and [i for i in iss if i.get("issue") != D4_ISSUE] == t0_iss
                       and out["V7"].get("norule_other_issues", None) == t0_iss)
    # V8
    v8 = {}
    h = gz_sha(os.path.join(d, "vc_money_lines.csv.gz"))
    for other in ("t2_first", "t2_b"):
        p = os.path.join(g2, other, "vc_money_lines.csv.gz")
        v8[other] = (gz_sha(p) == h) if os.path.exists(p) else "skipped"
    out["V8"] = v8
    out["V8"]["ok"] = all(v is True for v in v8.values())
    # V9 (a)
    a = norm(m[m.price_type != "distributor_mdf"])
    b = norm(m0)
    out["V9a"] = {"equal": bool(a.equals(b))}
    out["V9a"]["ok"] = out["V9a"]["equal"]
    # V9 (b) official sample after the change
    da = os.path.join(g2, "t0_after")
    if os.path.exists(os.path.join(da, "vc_money_lines.csv.gz")):
        same_lines = gz_sha(os.path.join(da, "vc_money_lines.csv.gz")) == gz_sha(
            os.path.join(g2, "t0", "vc_money_lines.csv.gz"))
        ca, c0 = checks_json(da), checks_json(os.path.join(g2, "t0"))
        d4a = [i for i in ca["issues"] if i.get("issue") == D4_ISSUE]
        ca_wo = dict(ca)
        ca_wo["issues"] = [i for i in ca["issues"] if i.get("issue") != D4_ISSUE]
        other_files = {}
        for fn in ("vc_ppc_comparison.csv", "vc_v1_weekly.csv", "vc_v2_weekly.csv", "vc_v3_weekly.csv",
                   "vc_observation_weekly.csv", "vc_inventory_weekly.csv", "vc_unrealized_weekly.csv",
                   "vc_conservation.csv", "vc_missing_prices.csv", "vc_edge_flows.csv", "vc_cost_policy.csv"):
            other_files[fn] = sha(os.path.join(da, fn)) == sha(os.path.join(g2, "t0", fn))
        out["V9b"] = {"money_lines_equal": same_lines, "d4_issues": len(d4a), "checks_equal_except_d4": ca_wo == c0,
                      "other_files_equal": other_files}
        out["V9b"]["ok"] = same_lines and len(d4a) == 4 and ca_wo == c0 and all(other_files.values())
        # (c) PPC outputs byte identical
        pdir_a, pdir_0 = os.path.join(da, "ppc"), os.path.join(g2, "t0", "ppc")
        ppc_cmp = {}
        for fn in sorted(os.listdir(pdir_0)):
            pa = os.path.join(pdir_a, fn)
            ppc_cmp[fn] = os.path.exists(pa) and sha(pa) == sha(os.path.join(pdir_0, fn))
        out["V9c"] = {"files": ppc_cmp, "ok": all(ppc_cmp.values())}
    else:
        out["V9b"] = out["V9c"] = {"skipped": True}
    # sample unchanged
    hb = os.path.join(g2, "sample_hash_before.txt")
    ha = os.path.join(g2, "sample_hash_after.txt")
    if os.path.exists(hb) and os.path.exists(ha):
        out["sample_unchanged"] = open(hb).read() == open(ha).read()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--g2-dir", default="output/g2_trial")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.out:
        os.makedirs(a.out, exist_ok=True)
    res = {}
    res["T0"], m0 = check_t0(a.g2_dir)
    if a.out:
        for lot in (SG_LOT, TH_LOT):
            lot_rows(m0, lot).to_csv(os.path.join(a.out, f"t0_{lot.split(':')[1]}_lot_money_lines.csv"),
                                     index=False, encoding="utf-8")
    res["T1"] = check_t1(a.g2_dir, m0)
    res["T2"] = check_t2(a.g2_dir, m0, a.out)
    s = json.dumps(res, ensure_ascii=False, indent=1, default=str)
    print(s)
    if a.out:
        with open(os.path.join(a.out, "check_g2_result.json"), "w", encoding="utf-8") as f:
            f.write(s)


if __name__ == "__main__":
    main()
