# -*- coding: utf-8 -*-
"""
verify_g3.py — G3 業務定義（sell-in の売上の計上週）を、Value Chain の出力で照らす。

    python docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix/verify_g3.py ^
        --g3-dir output/g3_verify ^
        --sample-dir data/sample/cosmetics-sg-th-2027-2029 ^
        --out docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_appendix

出力（tools.valuechain_run が書いたファイル）と、モデルの入力の CSV（vc_price_rule.csv）を読むだけ。
WOM のコードは import しない（計算し直さない）。

前提のフォルダ（依頼書 §3）：
    <g3-dir>/run_1_first   1 回目の実行の出力（2 回目の前に写したもの）
    <g3-dir>/run_1         同じ場所への 2 回目の実行の後
    <g3-dir>/run_2         別の場所への実行
    <g3-dir>/sample_hash_before.txt   実行の前のサンプルのハッシュ（sha256sum の書式）
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from collections import Counter

import pandas as pd

LOT = "COS_Cream:SG_Distributor:2028-W29:00002"
DIST_EDGES = {"DC_SG->SG_Distributor": "SG_Distributor", "DC_TH->TH_Distributor": "TH_Distributor"}
EXPECT_A5 = 443_922_960
REP_COLS = ["week", "kind", "scope", "family", "price_type", "entity", "counterparty", "node",
            "amount_orig", "currency_orig", "src_id"]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def gz_text_sha(path: str) -> str:
    with gzip.open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def b1_hash(sample_dir: str, before_file: str) -> dict:
    before = {}
    with open(before_file, encoding="utf-8") as f:
        for line in f:
            h, p = line.strip().split(None, 1)
            before[os.path.basename(p.lstrip("*"))] = h
    after = {fn: sha256(os.path.join(sample_dir, fn)) for fn in sorted(os.listdir(sample_dir))
             if os.path.isfile(os.path.join(sample_dir, fn))}
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    return {"files_before": len(before), "files_after": len(after), "changed": changed, "ok": not changed}


def iso_monday(w: str):
    from datetime import date
    return date.fromisocalendar(int(w[:4]), int(w[-2:]), 1)


def price_of(pr: pd.DataFrame, edge: str, prod: str, week: str):
    r = pr[(pr.edge_id == edge) & (pr.product_id == prod) & (pr.price_type == "wholesale") & (pr.week <= week)]
    if r.empty:
        return None, None
    r = r.sort_values("week").iloc[-1]
    return float(r.price), r.currency


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--g3-dir", required=True)
    ap.add_argument("--sample-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    run = os.path.join(a.g3_dir, "run_1")
    m = pd.read_csv(os.path.join(run, "vc_money_lines.csv.gz"), low_memory=False)
    s = pd.read_csv(os.path.join(run, "vc_shipments.csv.gz"), low_memory=False)
    pr = pd.read_csv(os.path.join(a.sample_dir, "vc_price_rule.csv"))
    res: dict = {}

    # ---- B1 / B3 ----
    res["B1"] = b1_hash(a.sample_dir, os.path.join(a.g3_dir, "sample_hash_before.txt"))
    sl = s[s.lot_id == LOT]
    dc = sl[sl.edge == "DC_SG->SG_Distributor"]
    leaf = sl[sl.kind == "consumer_sale"]
    res["B3"] = {
        "dc_ship_week": dc.ship_week.tolist(), "receipt_week": dc.arrival_week.tolist(),
        "leaf_ship_week": leaf.ship_week.tolist(),
        "ok": dc.ship_week.tolist() == ["2028-W28"] and dc.arrival_week.tolist() == ["2028-W29"]
              and leaf.ship_week.tolist() == ["2028-W29"]}

    # ---- 4.1 代表の Lot ----
    ml = m[m.lot_id == LOT].copy()
    ml[REP_COLS].to_csv(os.path.join(a.out, "rep_lot_money_lines.csv"), index=False, encoding="utf-8")
    sl.to_csv(os.path.join(a.out, "rep_lot_shipments.csv"), index=False, encoding="utf-8")
    l1 = ml[(ml.kind == "revenue") & (ml.scope == "external")]
    r1 = l1.iloc[0] if len(l1) == 1 else None
    res["L1"] = {"rows": len(l1), "row": None if r1 is None else {k: (r1[k] if not isinstance(r1[k], float) else float(r1[k])) for k in REP_COLS}}
    res["L1"]["ok"] = bool(r1 is not None and r1.week == "2028-W28" and r1.node == "DC_SG" and r1.entity == "E_SG"
                           and r1.counterparty == "EXT_CH_SG_DIST" and r1.price_type == "wholesale"
                           and float(r1.amount_orig) == 1488.0 and r1.currency_orig == "SGD")
    l2 = ml[(ml.kind == "revenue") & (ml.week == "2028-W29")]
    res["L2"] = {"rows": len(l2), "ok": len(l2) == 0}
    l3 = ml[ml.kind == "observation_sale"]
    res["L3"] = {"rows": len(l3), "weeks": l3.week.tolist(), "nodes": l3.node.tolist(), "scopes": l3.scope.tolist(),
                 "ok": len(l3) == 1 and l3.week.iloc[0] == "2028-W29" and l3.node.iloc[0] == "SG_Distributor"
                       and l3.scope.iloc[0] == "observation"}
    res["L4"] = {"dc_ship_id": dc.ship_id.tolist(), "leaf_ship_id": leaf.ship_id.tolist(),
                 "L1_src_id": None if r1 is None else r1.src_id,
                 "ok": len(dc) == 1 and len(leaf) == 1 and r1 is not None and r1.src_id == dc.ship_id.iloc[0]
                       and dc.arrival_week.iloc[0] == leaf.ship_week.iloc[0]}

    # ---- 4.2 全部の卸売 ----
    ds = s[s.edge.isin(DIST_EDGES) & (s.kind == "outbound_move")].copy()
    rev_ext = m[(m.kind == "revenue") & (m.scope == "external")]
    cnt = rev_ext.groupby("src_id").size()
    ds["rev_rows"] = ds.ship_id.map(cnt).fillna(0).astype(int)
    a1_dist = Counter(ds.rev_rows)
    # 外部代理店への売上の行が、代理店への出荷以外から立っていないか
    ext_ch = rev_ext[rev_ext.counterparty.isin(["EXT_CH_SG_DIST", "EXT_CH_TH_DIST"])]
    stray = sorted(set(ext_ch.src_id) - set(ds.ship_id))
    res["A1"] = {"shipments": len(ds), "rev_rows_per_shipment": {str(k): v for k, v in a1_dist.items()},
                 "by_edge": ds.groupby("edge").size().to_dict(), "stray_revenue_src": len(stray),
                 "ok": set(a1_dist) == {1} and not stray}
    rv = rev_ext.set_index("src_id")
    ds1 = ds[ds.rev_rows == 1]
    j = ds1.join(rv[["week", "amount_orig", "currency_orig", "amt_hq", "entity", "node"]]
                 .rename(columns={"node": "rev_node"}), on="ship_id")
    j["week_ok"] = j.week == j.ship_week
    res["A2"] = {"checked": len(j), "mismatch": int((~j.week_ok).sum()), "ok": bool(j.week_ok.all())}
    # A3：受入の週・leaf の出荷の週に、その Lot の revenue の行
    dist_lots = ds[["lot_id", "edge", "arrival_week"]]
    leaf_s = s[(s.kind == "consumer_sale") & s.node.isin(DIST_EDGES.values())][["lot_id", "ship_week"]]
    wk = pd.concat([dist_lots.rename(columns={"arrival_week": "w"})[["lot_id", "w"]],
                    leaf_s.rename(columns={"ship_week": "w"})]).drop_duplicates()
    rv_all = m[m.kind == "revenue"][["lot_id", "week", "scope", "node"]]
    a3 = wk.merge(rv_all, left_on=["lot_id", "w"], right_on=["lot_id", "week"])
    res["A3"] = {"lot_week_pairs": len(wk), "lots": int(wk.lot_id.nunique()),
                 "leaf_sales": len(leaf_s), "revenue_rows": len(a3), "ok": len(a3) == 0}
    # A4
    bad = []
    for _, r in j.iterrows():
        p, c = price_of(pr, r.edge, r["product"], r.ship_week)
        if p is None or abs(float(r.amount_orig) - float(r.units) * p) > 1e-6 or r.currency_orig != c:
            bad.append({"ship_id": r.ship_id, "amount": r.amount_orig, "units": r.units, "price": p, "ccy": c})
    res["A4"] = {"checked": len(j), "mismatch": len(bad), "examples": bad[:5], "ok": not bad}
    # A5
    tot = float(j.amt_hq.sum())
    res["A5"] = {"total_hq": tot, "expect": EXPECT_A5, "diff": tot - EXPECT_A5,
                 "by_edge_product": j.groupby(["edge", "product"]).amt_hq.sum().round(2).to_dict(),
                 "ok": abs(tot - EXPECT_A5) < 0.5}
    res["A5"]["by_edge_product"] = {f"{k[0]} {k[1]}": v for k, v in res["A5"]["by_edge_product"].items()}
    # 観測の明細がグループの売上に入っていないこと（参考）
    obs = m[m.kind == "observation_sale"]
    res["observation"] = {"rows": len(obs), "scopes": sorted(obs.scope.unique().tolist()),
                          "basis": sorted(obs.basis.astype(str).unique().tolist())}

    # ---- 4.3 再取込・再計算 ----
    def compare(x: str, y: str, drop_line_id: bool) -> dict:
        dx = pd.read_csv(os.path.join(a.g3_dir, x, "vc_money_lines.csv.gz"), low_memory=False)
        dy = pd.read_csv(os.path.join(a.g3_dir, y, "vc_money_lines.csv.gz"), low_memory=False)
        out = {"rows_" + x: len(dx), "rows_" + y: len(dy),
               "text_sha_" + x: gz_text_sha(os.path.join(a.g3_dir, x, "vc_money_lines.csv.gz")),
               "text_sha_" + y: gz_text_sha(os.path.join(a.g3_dir, y, "vc_money_lines.csv.gz"))}
        if drop_line_id:
            dx, dy = dx.drop(columns="line_id"), dy.drop(columns="line_id")
        out["equal"] = bool(len(dx) == len(dy) and dx.equals(dy))
        out["ok"] = out["equal"]
        return out
    res["R1"] = compare("run_1_first", "run_1", False)
    res["R2"] = compare("run_1", "run_2", True)
    res["R2"]["text_sha_equal"] = res["R2"]["text_sha_run_1"] == res["R2"]["text_sha_run_2"]

    # ---- 4.4 参考：PPC ----
    ev = pd.read_csv(os.path.join(run, "ppc", "ppc_event_ledger.csv"), low_memory=False)
    mr = ev[ev.ppc_event_type == "market_revenue"]
    rec = f"PSI-COS_Cream-SG_Distributor-{leaf.ship_week.iloc[0]}" if len(leaf) else None
    pr_rec = mr[mr.lot_id == rec]
    res["ppc_rep"] = {"record": rec, "rows": len(pr_rec),
                      "week": pr_rec.week.tolist(), "qty": pr_rec.qty.tolist(),
                      # PPC の amount_local・amount_base は 1 個当たり（合計は × qty）。記録は週・leaf ごとにまとめた 1 件
                      "price_per_unit_local": pr_rec.amount_local.tolist(), "currency": pr_rec.currency.tolist(),
                      "record_total_local": [float(x) * float(q) for x, q in zip(pr_rec.amount_local, pr_rec.qty)],
                      "rep_lot_share_local": [float(x) * 24 for x in pr_rec.amount_local],
                      "vc_lines_with_ppc_src": int(m.src_id.astype(str).str.startswith("PSI-").sum())}
    leaf_w = leaf_s.set_index("lot_id").ship_week
    diffs = Counter()
    for _, r in j.iterrows():
        lw = leaf_w.get(r.lot_id)
        lv = DIST_EDGES[r.edge]
        ok = not mr[(mr.lot_id == f"PSI-{r['product']}-{lv}-{lw}") & (mr.week == lw)].empty
        key = f"{r.edge} {r['product']}"
        diffs[(key, (iso_monday(lw) - iso_monday(r.week)).days // 7 if ok else "no_ppc_record")] += 1
    res["ppc_week_diff"] = {f"{k[0]} | PPC-VC={k[1]}": v for k, v in sorted(diffs.items(), key=str)}
    md = mr[mr.node_id.isin(DIST_EDGES.values())]
    ppc_dist_tot = float((md.amount_base * md.qty).sum())
    res["ppc_dist_total_base"] = ppc_dist_tot

    keys = ["B1", "B3", "L1", "L2", "L3", "L4", "A1", "A2", "A3", "A4", "A5", "R1", "R2"]
    res["summary"] = {k: res[k]["ok"] for k in keys}
    res["all_ok"] = all(res["summary"].values())
    with open(os.path.join(a.out, "verify_g3_result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2, default=str)
    for k in keys:
        print(f"{k}: {'OK' if res[k]['ok'] else 'NG'}")
    print("ALL", "OK" if res["all_ok"] else "NG")
    return 0 if res["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
