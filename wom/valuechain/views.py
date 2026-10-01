# -*- coding: utf-8 -*-
"""
三つの視点（RequestLetter_StageD_Phase1 §1-5、設計 §1）と照合（受入 3・4）

V1  ノード・区間の管理評価：全ノード。法人内の区間も管理価格（無ければ原価振替）で売上・仕入
V2  法人別：外部と他法人への売上と、その原価（法人の帳簿＝entity の原価）。法人内の管理売上は除く
V3  連結範囲：外部売上・その原価・費用に、「内部取引の利益（未実現利益の消去前）」を加える。
    **第 1 回は内部の未実現利益を消さない**（表示は「消去前」）。第 2 回の値（group の原価）は
    `profit_r2` などの列に持つが、画面には出さない（テストの期待値の確認用）

単週（_wk）と累計（_cum）。累計は報告の開始週（report_start）から。報告の期間の前（助走週）の
売上・費用は、報告の期間の利益に入らない。期首の在庫原価は、報告の開始週の前の週末の残高。

金額は、valued（評価できた明細）の合計と、未評価の明細の件数（n_unvalued）を並べる。
未評価を 0 として足さない。
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

AGG_COLS = ["week_index", "product", "entity", "node", "counterparty", "kind", "scope", "basis", "family",
            "price_type",
            "hq", "common", "func", "local", "n_valued", "n_unvalued", "n_lines", "hq_known"]


def agg_frame(ledger) -> pd.DataFrame:
    rows = [list(k) + list(v) for k, v in ledger.agg.items()]
    return pd.DataFrame(rows, columns=AGG_COLS)


def _has(basis_series, b):
    return basis_series.str.split(",").apply(lambda xs: b in xs or "all" in xs)


def _weekly(df, keys, valcols, labels, report_idx):
    """complete weeks x keys grid; _wk and _cum (from report_idx) columns."""
    n = len(labels)
    if df.empty:
        idx = pd.MultiIndex.from_product([range(n)] + [[]] * len(keys), names=["week_index"] + keys)
        return pd.DataFrame(index=idx).reset_index()
    groups = df.groupby(keys + ["week_index"])[valcols].sum()
    key_vals = df[keys].drop_duplicates().itertuples(index=False, name=None)
    full = pd.MultiIndex.from_tuples([tuple(k) + (w,) for k in key_vals for w in range(n)],
                                     names=keys + ["week_index"])
    g = groups.reindex(full, fill_value=0.0).reset_index()
    g["week"] = g["week_index"].map(lambda i: labels[i])
    g["in_report"] = g["week_index"] >= report_idx
    for c in valcols:
        g = g.rename(columns={c: f"{c}_wk"})
        mask = g["in_report"]
        g[f"{c}_cum"] = (g[f"{c}_wk"].where(mask, 0.0)).groupby([g[k] for k in keys]).cumsum()
    return g


def build_views(ledger, report_idx: int) -> Dict[str, pd.DataFrame]:
    m = ledger.m
    labels = ledger.labels
    a = agg_frame(ledger)
    ents = m.entities
    a["consolidated"] = a["entity"].map(lambda e: bool(ents[e].consolidated) if e in ents else False)
    a["is_group"] = a["entity"].map(lambda e: ents[e].is_group if e in ents else False)

    def pick(kind, scopes=None, basis=None, group_only=True):
        x = a[a["kind"] == kind]
        if scopes is not None:
            x = x[x["scope"].isin(scopes)]
        if basis is not None:
            x = x[_has(x["basis"], basis)]
        if group_only:
            x = x[x["is_group"]]
        return x

    def signed(frames):
        parts = []
        for f, sign, name in frames:
            if f.empty:
                continue
            g = f.copy()
            for c in ("hq", "common", "func", "local"):
                g[c] = g[c] * sign
            g["item"] = name
            parts.append(g)
        return pd.concat(parts, ignore_index=True) if parts else a.iloc[0:0].assign(item="")

    # ── V1 (node) ───────────────────────────────────────────────
    v1 = signed([(pick("revenue", ["external", "intercompany", "management"]), 1, "revenue"),
                 (pick("cogs", ["external", "intercompany", "management"], "v1"), -1, "cogs"),
                 (pick("expense"), -1, "expense")])
    v1_tab = _items_table(v1, ["product", "node", "entity"], labels, report_idx)

    # ── V2 (entity) ─────────────────────────────────────────────
    v2 = signed([(pick("revenue", ["external", "intercompany"]), 1, "revenue"),
                 (pick("cogs", ["external", "intercompany"], "entity"), -1, "cogs"),
                 (pick("expense"), -1, "expense")])
    v2_tab = _items_table(v2, ["entity"], labels, report_idx)
    # local profit translated at the week's rate (design §5.5: kept apart from the
    # management evaluation, which carries the acquisition-time HQ cost)
    if not v2_tab.empty:
        fx = ledger.fx
        hq = m.hq_currency

        def tr(r):
            f = ents[r["entity"]].functional_currency
            rate, _ = fx.rate(f, hq, r["week"], "translation of local profit")
            return r["profit_func_wk"] * rate if not math.isnan(rate) else float("nan")
        v2_tab["profit_local_translated_hq_wk"] = v2_tab.apply(tr, axis=1)
        v2_tab["profit_local_translated_hq_cum"] = (
            v2_tab["profit_local_translated_hq_wk"].where(v2_tab["in_report"], 0.0)
            .groupby(v2_tab["entity"]).cumsum())
        v2_tab["functional_currency"] = v2_tab["entity"].map(lambda e: ents[e].functional_currency)

    # ── V3 (consolidated) ───────────────────────────────────────
    cons = a[a["consolidated"]]

    def cpick(kind, scopes, basis=None):
        x = cons[(cons["kind"] == kind) & cons["scope"].isin(scopes)]
        if basis is not None:
            x = x[_has(x["basis"], basis)]
        return x
    v3 = signed([(cpick("revenue", ["external"]), 1, "external_revenue"),
                 (cpick("cogs", ["external"], "entity"), -1, "external_cogs"),
                 (cons[cons["kind"] == "expense"], -1, "expense"),
                 (cpick("revenue", ["intercompany"]), 1, "ic_profit"),
                 (cpick("cogs", ["intercompany"], "entity"), -1, "ic_profit")])
    v3["group_key"] = "GROUP"
    v3_tab = _items_table(v3, ["group_key"], labels, report_idx)
    r2 = signed([(cpick("revenue", ["external"]), 1, "external_revenue"),
                 (cpick("cogs", ["external"], "group"), -1, "external_cogs"),
                 (cons[cons["kind"] == "expense"], -1, "expense")])
    r2["group_key"] = "GROUP"
    r2_tab = _items_table(r2, ["group_key"], labels, report_idx)
    if not v3_tab.empty:
        if not r2_tab.empty:
            r2m = r2_tab.set_index("week_index")
            v3_tab["profit_r2_hq_wk"] = v3_tab["week_index"].map(r2m["profit_hq_wk"]).fillna(0.0)
            v3_tab["profit_r2_hq_cum"] = v3_tab["week_index"].map(r2m["profit_hq_cum"]).fillna(0.0)
        else:      # nothing sold outside yet: round 2 recognises no profit
            v3_tab["profit_r2_hq_wk"] = 0.0
            v3_tab["profit_r2_hq_cum"] = 0.0

    # ── observation (external channels ②) ───────────────────────
    obs = a[a["kind"] == "observation_sale"].copy()
    obs_tab = _weekly(obs.rename(columns={"local": "sale_local", "hq": "sale_hq", "common": "sale_common"}),
                      ["product", "node", "entity"], ["sale_hq", "sale_common", "sale_local", "n_valued"],
                      labels, report_idx) if not obs.empty else pd.DataFrame()

    # ── inventory ───────────────────────────────────────────────
    inv = pd.DataFrame(ledger.inv_rows)
    if inv.empty:
        inv = pd.DataFrame(columns=["week_index", "week", "owner", "location_kind", "location", "product",
                                    "item", "valued", "external", "lots", "v1_hq", "entity_hq",
                                    "group_hq", "entity_common", "entity_func", "v1_common", "group_common"])
    return {"agg": a, "v1": v1_tab, "v2": v2_tab, "v3": v3_tab, "observation": obs_tab, "inventory": inv}


def _items_table(df, keys, labels, report_idx):
    if df.empty:
        return pd.DataFrame()
    piv = df.pivot_table(index=keys + ["week_index"], columns="item",
                         values=["hq", "common", "func", "n_unvalued", "n_valued", "hq_known"], aggfunc="sum",
                         fill_value=0.0)
    piv.columns = [f"{it}_{v}" for v, it in piv.columns]
    piv = piv.reset_index()
    vals = [c for c in piv.columns if c not in keys + ["week_index"]]
    items = sorted(set(df["item"]))
    for cur in ("hq", "common", "func"):
        piv[f"profit_{cur}"] = sum(piv.get(f"{it}_{cur}", 0.0) for it in items)
    piv["n_unvalued"] = sum(piv.get(f"{it}_n_unvalued", 0.0) for it in items)
    vals = [c for c in piv.columns if c not in keys + ["week_index"]]
    return _weekly(piv, keys, vals, labels, report_idx)


# ──────────────────────────────────────────────────────────────────────
# checks
# ──────────────────────────────────────────────────────────────────────

def check_conservation(ledger, views, tol=1e-6) -> pd.DataFrame:
    """受入 3：法人ごと・週ごとに 期首 ＋ 受け入れ（在庫原価）− 払い出し − 未評価への移り ＝ 期末
    （entity の原価、HQ 通貨、評価できた分）。"""
    a = views["agg"]
    inv = views["inventory"]
    labels = ledger.labels
    rows = []
    acq = a[(a["kind"] == "acquisition") & _has(a["basis"], "entity")].groupby(["entity", "week_index"])["hq"].sum()
    cogs = a[(a["kind"] == "cogs") & (a["basis"] == "entity") &
             a["scope"].isin(["external", "intercompany"])].groupby(["entity", "week_index"])["hq"].sum()
    iv = inv[(inv["valued"] == 1) & (inv["external"] == 0)]
    close = iv.groupby(["owner", "week_index"])["entity_hq"].sum()
    for eid, ent in ledger.m.entities.items():
        if not ent.is_group:
            continue
        prev = 0.0
        for w in range(len(labels)):
            c = float(close.get((eid, w), 0.0))
            r = float(acq.get((eid, w), 0.0))
            i = float(cogs.get((eid, w), 0.0))
            u = float(ledger.unvalued_out.get((w, eid), 0.0))
            up = float(ledger.unpriced_issue.get((w, eid), 0.0))
            diff = prev + r - i - up - u - c
            rows.append({"entity": eid, "week_index": w, "week": labels[w], "opening": prev,
                         "receipts": r, "issues": i, "issues_unpriced_sale": up, "to_unvalued": u,
                         "closing": c, "diff": diff,
                         "ok": abs(diff) <= tol * max(1.0, abs(prev) + abs(r) + abs(c))})
            prev = c
    return pd.DataFrame(rows)


def check_external_sales(ledger, views, records) -> dict:
    """受入 4：Σ 連結対象の法人の売上 − 連結対象の法人どうしの売上 ＝ V3 の外部売上
    ＝ 連結範囲から外部の相手への出荷の記録 × 価格（記録と価格表から別に計算）。"""
    a = views["agg"]
    # revenue amounts that are known (hq_known): the identity is about sales amounts,
    # whether or not the cost of each sale could be valued
    cons = a[a["consolidated"] & (a["kind"] == "revenue")]
    total = float(cons[cons["scope"].isin(["external", "intercompany"])]["hq_known"].sum())
    ic = float(cons[cons["scope"] == "intercompany"]["hq_known"].sum())
    v3_ext = float(cons[cons["scope"] == "external"]["hq_known"].sum())
    n_unvalued = int(cons[cons["scope"] == "external"]["n_unvalued"].sum())
    # independent: shipment records x price
    m, fx = ledger.m, ledger.fx
    owner_of = {}
    indep, n_ship, n_nan = 0.0, 0, 0
    for s in records.shipments:
        if s.kind not in ("outbound_move", "consumer_sale"):
            continue
        src_node = s.node if s.kind == "consumer_sale" else s.phys_from
        seller = m.entity_of(src_node, s.product)
        if not (seller.is_group and seller.consolidated):
            continue
        wk = records.week_labels[s.week]
        if s.kind == "consumer_sale":
            price, ccy, _ = m.market(s.node, s.product, wk)
        else:
            buyer = m.entity_of(s.to, s.product)
            if buyer.is_group and buyer.consolidated:
                continue
            tp = m.transfer_price.get((s.phys_from, s.product))
            if tp is not None and records.nodes[(s.product, s.phys_from)].is_terminal_mom and tp["method"] == "fixed":
                price, ccy = tp["fixed_price"], tp["currency"]
            else:
                ptype = "wholesale" if buyer.kind == "external_channel" else "intercompany"
                price, ccy, _ = m.price_rule(s.edge, s.product, ptype, wk)
        n_ship += 1
        if price is None or (isinstance(price, float) and math.isnan(price)):
            n_nan += 1
            continue
        r, _ = fx.rate(ccy, m.hq_currency, wk, "check")
        if math.isnan(r):
            n_nan += 1
            continue
        indep += price * s.units * r
    return {"sum_consolidated_revenue": total, "intercompany_revenue": ic,
            "v3_external_revenue": v3_ext, "lhs_total_minus_ic": total - ic,
            "records_times_price": indep, "external_shipments": n_ship,
            "external_shipments_unvalued": n_nan, "v3_external_revenue_unvalued_lines": n_unvalued,
            "ok_identity": abs((total - ic) - v3_ext) <= 1e-6 * max(1.0, abs(v3_ext)),
            "ok_records": abs(indep - v3_ext) <= 1e-6 * max(1.0, abs(v3_ext))}
