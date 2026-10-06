# -*- coding: utf-8 -*-
"""
三つの視点（RequestLetter_StageD_Phase1 §1-5、設計 §1）と照合（受入 3・4）

V1  ノード・区間の管理評価：全ノード。法人内の区間も管理価格（無ければ原価振替）で売上・仕入
V2  法人別：外部と他法人への売上と、その原価（法人の帳簿＝entity の原価）。法人内の管理売上は除く
V3  連結範囲。2 つの値を並べて持つ（RequestLetter_StageD_Phase2）：
    第 1 回（消去前）  外部売上 − 外部売上の原価（法人の原価）− 費用 ＋ 内部取引の利益
                       列：external_revenue・external_cogs・expense・ic_profit・profit
    第 2 回（消去後）  外部売上 − 外部売上の原価（グループの原価）− 費用
                       列：external_cogs_r2・profit_r2
    差は「内部の未実現利益の増減」（unrealized_change ＝ 週末残高の増減 ＋ 未評価へ移った分）。
    週末残高 unrealized_balance、グループの在庫 inv_group・inv_entity（連結の法人・評価済み）

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
    unreal, unreal_week = _unrealized(ledger, a, labels, report_idx)
    if not v3_tab.empty:
        r2m = r2_tab.set_index("week_index") if not r2_tab.empty else None
        uw = unreal_week.set_index("week_index")
        for cur in ("hq", "common"):
            for per in ("wk", "cum"):
                for src, dst in ((f"external_cogs_{cur}_{per}", f"external_cogs_r2_{cur}_{per}"),
                                 (f"profit_{cur}_{per}", f"profit_r2_{cur}_{per}")):
                    # nothing sold outside yet: round 2 recognises no profit
                    v3_tab[dst] = (v3_tab["week_index"].map(r2m[src]).fillna(0.0)
                                   if r2m is not None and src in r2m else 0.0)
                v3_tab[f"unrealized_change_{cur}_{per}"] = v3_tab["week_index"].map(uw[f"change_{cur}_{per}"])
            v3_tab[f"unrealized_balance_{cur}_wk"] = v3_tab["week_index"].map(uw[f"balance_{cur}"])
            v3_tab[f"unrealized_balance_{cur}_cum"] = v3_tab[f"unrealized_balance_{cur}_wk"]
        for col in ("inv_group_hq", "inv_entity_hq", "inv_group_common", "inv_entity_common",
                    "lots_unvalued", "to_unvalued_hq", "eliminated_hq", "realized_hq"):
            v3_tab[col] = v3_tab["week_index"].map(uw[col])

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
    return {"agg": a, "v1": v1_tab, "v2": v2_tab, "v3": v3_tab, "observation": obs_tab, "inventory": inv,
            "unrealized": unreal, "unrealized_week": unreal_week}


UNREAL_KEYS = ["owner", "product", "location_kind", "location"]
EVENTS = ("eliminated", "transfer_in", "transfer_out", "realized", "to_unvalued")


def _unrealized(ledger, a, labels, report_idx):
    """(detail, weekly) of the internal unrealized profit (round 2).

    detail: week x owner x product x location -- the week-end balance of the valued group
    inventory (entity cost, group cost, U = entity - group, HQ and common), the lots whose U is
    unvalued, the week's events, and the change of the balance.
    weekly: the group's totals and the reconciliation term change = balance change + to_unvalued."""
    n = len(labels)
    ents = ledger.m.entities
    cons = {e for e, x in ents.items() if x.is_group and x.consolidated}
    inv = pd.DataFrame(ledger.inv_rows)
    if inv.empty:
        inv = pd.DataFrame(columns=["week_index", "owner", "product", "location_kind", "location", "valued",
                                    "external", "lots", "entity_hq", "group_hq", "entity_common",
                                    "group_common"])
    inv = inv[(inv["external"] == 0) & inv["owner"].isin(cons)].copy()
    val = inv[inv["valued"] == 1]
    vcols = ["lots", "entity_hq", "group_hq", "entity_common", "group_common"]
    bal = val.groupby(["week_index"] + UNREAL_KEYS)[vcols].sum()
    unv = inv[inv["valued"] == 0].groupby(["week_index"] + UNREAL_KEYS)["lots"].sum().rename("lots_unvalued")
    ev_rows = [list(k) + list(v) for k, v in ledger.unreal.items()]
    ev = pd.DataFrame(ev_rows, columns=["week_index"] + UNREAL_KEYS + ["event", "hq", "common"])
    parts = [bal, unv]
    for cur in ("hq", "common"):
        if ev.empty:
            continue
        pv = ev.pivot_table(index=["week_index"] + UNREAL_KEYS, columns="event", values=cur, aggfunc="sum",
                            fill_value=0.0)
        pv.columns = [f"{c}_{cur}" for c in pv.columns]
        parts.append(pv)
    d = pd.concat(parts, axis=1).fillna(0.0).reset_index() if any(len(x) for x in parts) else         pd.DataFrame(columns=["week_index"] + UNREAL_KEYS)
    ecols = [f"{e}_{c}" for e in EVENTS for c in ("hq", "common")]
    for c in vcols + ["lots_unvalued"] + ecols:
        if c not in d:
            d[c] = 0.0
    # complete grid per key, so the change of a balance that went to zero is seen
    keys = list(d[UNREAL_KEYS].drop_duplicates().itertuples(index=False, name=None))
    full = pd.MultiIndex.from_tuples([tuple(k) + (w,) for k in keys for w in range(n)],
                                     names=UNREAL_KEYS + ["week_index"])
    d = (d.set_index(UNREAL_KEYS + ["week_index"])[vcols + ["lots_unvalued"] + ecols]
         .reindex(full, fill_value=0.0).reset_index())
    d["unrealized_hq"] = d["entity_hq"] - d["group_hq"]
    d["unrealized_common"] = d["entity_common"] - d["group_common"]
    d = d.sort_values(UNREAL_KEYS + ["week_index"]).reset_index(drop=True)
    for cur in ("hq", "common"):
        prev = d.groupby(UNREAL_KEYS)[f"unrealized_{cur}"].shift(1).fillna(0.0)
        d[f"change_{cur}"] = d[f"unrealized_{cur}"] - prev
    d["week"] = d["week_index"].map(lambda i: labels[int(i)])
    d["in_report"] = d["week_index"] >= report_idx

    w = pd.DataFrame({"week_index": range(n)})
    g = d.groupby("week_index")
    for col in ["unrealized_hq", "unrealized_common", "entity_hq", "group_hq", "entity_common",
                "group_common", "lots_unvalued"] + ecols:
        w[col] = w["week_index"].map(g[col].sum()).fillna(0.0) if len(d) else 0.0
    w = w.rename(columns={"unrealized_hq": "balance_hq", "unrealized_common": "balance_common",
                          "entity_hq": "inv_entity_hq", "group_hq": "inv_group_hq",
                          "entity_common": "inv_entity_common", "group_common": "inv_group_common"})
    w["week"] = w["week_index"].map(lambda i: labels[i])
    w["in_report"] = w["week_index"] >= report_idx
    for cur in ("hq", "common"):
        delta = w[f"balance_{cur}"].diff().fillna(w[f"balance_{cur}"])
        w[f"change_{cur}_wk"] = delta + w[f"to_unvalued_{cur}"]
        w[f"change_{cur}_cum"] = w[f"change_{cur}_wk"].where(w["in_report"], 0.0).cumsum()
    # keep only the rows that say something (the balance, unvalued lots, a change or an event)
    keep = d[["lots", "lots_unvalued", "unrealized_hq", "change_hq"] + ecols].abs().sum(axis=1) > 0
    d = d[keep].reset_index(drop=True)
    return d, w


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


def check_unrealized(ledger, views, tol=1e-6) -> dict:
    """受入 2・3（第 2 回）：
    週ごと   第 1 回の利益 − 第 2 回の利益 ＝ 内部の未実現利益の週末残高の増減 ＋ 未評価へ移った分
    法人ごと 残高の増減 ＝ eliminated ＋ transfer_in − transfer_out − realized − to_unvalued
    期間     報告の期間の累計で、第 1 回 − 第 2 回 ＝ 期末の残高 − 期首の残高 ＋ 期間中に未評価へ移った分
    （HQ の報告通貨。週ごとの式は共通の評価通貨でも確かめる）"""
    v3 = views["v3"]
    d = views["unrealized"]
    w = views["unrealized_week"]
    out = {}
    if v3.empty:
        return {"ok": True, "note": "V3 is empty"}
    t = v3.sort_values("week_index")
    for cur in ("hq", "common"):
        diff = (t[f"profit_{cur}_wk"] - t[f"profit_r2_{cur}_wk"] - t[f"unrealized_change_{cur}_wk"]).abs()
        scale = max(1.0, float(t[f"profit_{cur}_wk"].abs().max()), float(w[f"balance_{cur}"].abs().max()))
        out[f"weekly_max_abs_diff_{cur}"] = float(diff.max())
        out[f"weekly_ok_{cur}"] = bool((diff <= tol * scale).all())
    worst = 0.0
    if not d.empty:
        e = d.groupby(["owner", "week_index"])[["change_hq", "eliminated_hq", "transfer_in_hq",
                                                 "transfer_out_hq", "realized_hq", "to_unvalued_hq"]].sum()
        r = (e["change_hq"] - (e["eliminated_hq"] + e["transfer_in_hq"] - e["transfer_out_hq"]
                               - e["realized_hq"] - e["to_unvalued_hq"])).abs()
        worst = float(r.max())
    out["per_owner_max_abs_diff_hq"] = worst
    out["per_owner_ok"] = worst <= tol * max(1.0, float(w["balance_hq"].abs().max()) if len(w) else 1.0)
    rep = int(t[t["in_report"]]["week_index"].min()) if t["in_report"].any() else 0
    last = int(t["week_index"].max())
    ww = w.set_index("week_index")
    opening = float(ww["balance_hq"].get(rep - 1, 0.0)) if rep > 0 else 0.0
    closing = float(ww["balance_hq"].get(last, 0.0))
    out_rep = float(w[w["in_report"]]["to_unvalued_hq"].sum())
    r1 = float(t[t["in_report"]]["profit_hq_wk"].sum())
    r2 = float(t[t["in_report"]]["profit_r2_hq_wk"].sum())
    out["period"] = {"report_start": str(t[t["week_index"] == rep]["week"].iloc[0]),
                     "last_week": str(t["week"].iloc[-1]),
                     "profit_round1_hq": r1, "profit_round2_hq": r2, "round1_minus_round2": r1 - r2,
                     "unrealized_opening_hq": opening, "unrealized_closing_hq": closing,
                     "to_unvalued_in_period_hq": out_rep,
                     "rhs_closing_minus_opening_plus_to_unvalued": closing - opening + out_rep}
    out["period_ok"] = abs((r1 - r2) - (closing - opening + out_rep)) <= tol * max(1.0, abs(r1), abs(closing))
    by = []
    if not d.empty:
        for owner, x in d.groupby("owner"):
            def at(wk, col):
                return float(x[x["week_index"] == wk][col].sum())
            by.append({"entity": owner,
                       "opening_hq": at(rep - 1, "unrealized_hq") if rep > 0 else 0.0,
                       "closing_hq": at(last, "unrealized_hq"),
                       "opening_common": at(rep - 1, "unrealized_common") if rep > 0 else 0.0,
                       "closing_common": at(last, "unrealized_common"),
                       "eliminated_in_period_hq": float(x[x["in_report"]]["eliminated_hq"].sum()),
                       "realized_in_period_hq": float(x[x["in_report"]]["realized_hq"].sum()),
                       "to_unvalued_in_period_hq": float(x[x["in_report"]]["to_unvalued_hq"].sum()),
                       "unvalued_lots_closing": int(at(last, "lots_unvalued"))})
    out["by_entity"] = by
    out["unvalued_lots_closing"] = int(ww["lots_unvalued"].get(last, 0)) if len(w) else 0
    out["ok"] = bool(out["weekly_ok_hq"] and out["weekly_ok_common"] and out["per_owner_ok"]
                     and out["period_ok"])
    return out
