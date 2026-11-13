# -*- coding: utf-8 -*-
"""
tools/compare_scenarios.py — 2 案の結果を並べる
==============================================
RequestLetter_Cockpit_FirstComparison_Observe §3（2026-11-13）。

    python -m tools.compare_scenarios --base <後期案の実行結果> --alt <早期案の実行結果>
        --base-model <後期案のモデル> --alt-model <早期案のモデル> --out <フォルダ>
        [--fixed-cost-plan <csv>] [--base-udp <上位 Demand Plan の出力>] [--alt-udp <…>]
        [--base-name late --alt-name early]

RequestLetter_Cockpit_FirstComparison_PolicyAndCapacity §4 で、数量配分の分け方と、GPT-MC の業務定義
v0.1 による固定費の逆転点を足した（--extra-fixed-cost-weeks は廃止）。

**出力とモデルの CSV を読むだけ（WOM を import しない）。**

実行結果のフォルダ（各案。同じプラグインの組で回したもの）：
    snapshot.json                       headless（tools.run_headless_from_folder --out）
    ppc/ppc_kpi_summary.json            PPC（--ppc-out）
    flow_check/<モデル名>/flow_check_market.csv   Flow Check の表 2（--flow-check-out）
    vc/                                 tools.valuechain_run の出力（vc_shipments.csv.gz・
                                        vc_money_lines.csv.gz・vc_v3_weekly.csv・vc_inventory_weekly.csv）
    shelf/shelf_life_summary.csv        tools.shelf_life_check の出力

出力（--out）：
    demand_diff.csv              鍵 × 週の需要（lot）の 2 案と差
    entry_plan_diff.csv          入力の表（market_entry_plan.csv）の違い（鍵 × 列）
    supply_by_request_week.csv   鍵 × 要求週の 需要・当週・早出し・遅配・期末の未充足（2 案と差）
    supply_by_key.csv            鍵ごとの合計（Flow Check の表 2 との突き合わせ付き）
    money_by_week_sku.csv        計上週 × SKU の外部売上・売上原価（グループ）・費用・試算利益（消去後）
    money_totals.csv             SKU 別の合計（報告期間・全計画期間）と PPC の合計
    inventory_weekly.csv         週末の在庫（場所 × SKU、lot 数とグループの原価。グループの所有分）
    inventory_by_week_sku.csv    週末の在庫の SKU 別の合計
    factory_weekly.csv           工場の週の生産（MOM → supply point の受け渡し）と能力
    age_summary.csv              製品の年齢（最大・52 週超の件数など、shelf_life_summary.csv から）
    diff_weeks.csv               差の出た最初の週と、差が最大の週
    representative_lots.csv      代表の lot の明細（需要 → 出荷の記録 → 金額の明細）
    boundary.csv                 計画の境界（最初の週・最後の 2 週）の差と、要求週別の期末の未充足
    factory_idle_weeks.csv       工場が出荷可能な soft 能力（floor(cap_soft × yield)）より少なく作った週
    supply_allocation_by_request_week.csv / supply_allocation_by_key.csv
                                 --base-udp・--alt-udp のとき：① 元の需要・② 供給の対象・③ 未配分・当週・早出し・
                                 遅配・⑤ 配分後の未充足（渡さない案は ①＝②＝需要、③＝0）
    fixed_cost_breakeven.csv     固定費の逆転点（業務定義 §4：P0・有償の週・W・週額・費用・控除後・ΔP0・ΔW・境目）
    comparison_summary.md        まとめ

止める条件（CompareError）：ファイルが無い、要求週別の供給の鍵ごとの合計が Flow Check の表 2 と合わない、
SKU 別の試算利益の合計が vc_v3_weekly.csv の profit_r2_hq_wk と週ごとに合わない、
数量配分の結果を渡した案で、金額の実行の出荷（Lot_ID）が数量配分の結果と鍵 × 要求週で合わない、
市場の実出荷の Lot_ID が需要に無い・同じ Lot_ID が 2 回出荷された。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import pandas as pd

TOL = 0.5          # yen: tolerance for the per-week profit check (sums of floats)
K_CONSUMER = "consumer_sale"
K_HANDOFF = "handoff_to_sp"
SUPPLY_COLS = ["demand", "on_time", "early", "late", "backlog_end"]
MONEY_COLS = ["external_revenue", "external_cogs_group", "expense", "profit_r2"]


class CompareError(ValueError):
    """The two runs cannot be compared, or a reconciliation does not add up."""


# ── 読み込み ──────────────────────────────────────────────────────────
def _need(path: str) -> str:
    if not os.path.exists(path):
        raise CompareError(f"{path} がありません")
    return path


def _csv(path: str, **kw) -> pd.DataFrame:
    return pd.read_csv(_need(path), encoding="utf-8-sig", **kw)


def _flow_check_path(run_dir: str) -> str:
    hits = sorted(glob.glob(os.path.join(run_dir, "flow_check", "*", "flow_check_market.csv")))
    if len(hits) != 1:
        raise CompareError(f"{run_dir}/flow_check/<モデル名>/flow_check_market.csv が 1 つではありません: {hits}")
    return hits[0]


def load_run(run_dir: str, model_dir: str) -> dict:
    vc = os.path.join(run_dir, "vc")
    r = {
        "run_dir": run_dir, "model_dir": model_dir,
        "demand": _csv(os.path.join(model_dir, "demand_forecast.csv"), dtype={"week": str}),
        "flow": _csv(_flow_check_path(run_dir)),
        "ship": _csv(os.path.join(vc, "vc_shipments.csv.gz"), dtype=str),
        "money": _csv(os.path.join(vc, "vc_money_lines.csv.gz"), dtype={"lot_id": str, "product": str}),
        "v3": _csv(os.path.join(vc, "vc_v3_weekly.csv")),
        "inv": _csv(os.path.join(vc, "vc_inventory_weekly.csv")),
        "entity": _csv(os.path.join(model_dir, "vc_entity.csv"), dtype=str),
        "shelf": _csv(os.path.join(run_dir, "shelf", "shelf_life_summary.csv"), dtype=str),
        "capacity": _csv(os.path.join(model_dir, "capacity_plan.csv"), dtype=str),
        "tree": _csv(os.path.join(model_dir, "sc_tree_master.csv"), dtype=str),
    }
    with open(_need(os.path.join(run_dir, "ppc", "ppc_kpi_summary.json")), encoding="utf-8") as f:
        r["ppc"] = json.load(f)
    snap = os.path.join(run_dir, "snapshot.json")
    r["snapshot"] = json.load(open(snap, encoding="utf-8")) if os.path.exists(snap) else None
    ep = os.path.join(model_dir, "market_entry_plan.csv")
    r["entry_plan"] = _csv(ep, dtype=str, keep_default_na=False) if os.path.exists(ep) else None
    for c in ("ship_week_index", "lots"):
        r["ship"][c] = pd.to_numeric(r["ship"][c])
    r["week_labels"] = list(r["v3"].loc[r["v3"]["group_key"] == "GROUP"].sort_values("week_index")["week"])
    return r


# ── 需要 ─────────────────────────────────────────────────────────────
def demand_diff(base: dict, alt: dict) -> pd.DataFrame:
    k = ["sku_id", "region", "week"]
    a = base["demand"][k + ["quantity"]].rename(columns={"quantity": "demand_base"})
    b = alt["demand"][k + ["quantity"]].rename(columns={"quantity": "demand_alt"})
    d = a.merge(b, on=k, how="outer").fillna(0)
    d["demand_base"] = d["demand_base"].astype(int)
    d["demand_alt"] = d["demand_alt"].astype(int)
    d["diff"] = d["demand_alt"] - d["demand_base"]
    return d.sort_values(["sku_id", "region", "week"]).reset_index(drop=True)


def entry_plan_diff(base: dict, alt: dict) -> pd.DataFrame:
    rows = []
    a, b = base["entry_plan"], alt["entry_plan"]
    if a is None or b is None:
        return pd.DataFrame([{"sku_id": "", "region": "", "column": "(market_entry_plan.csv が無い案がある)",
                              "base": "" if a is None else "present", "alt": "" if b is None else "present"}])
    ia = {(r["sku_id"], r["region"]): r for _, r in a.iterrows()}
    ib = {(r["sku_id"], r["region"]): r for _, r in b.iterrows()}
    for key in sorted(set(ia) | set(ib)):
        if key not in ia or key not in ib:
            rows.append({"sku_id": key[0], "region": key[1], "column": "(row)",
                         "base": "present" if key in ia else "missing", "alt": "present" if key in ib else "missing"})
            continue
        for c in a.columns:
            va, vb = str(ia[key].get(c, "")), str(ib[key].get(c, ""))
            if va != vb:
                rows.append({"sku_id": key[0], "region": key[1], "column": c, "base": va, "alt": vb})
    return pd.DataFrame(rows, columns=["sku_id", "region", "column", "base", "alt"])


# ── 要求週別の供給 ────────────────────────────────────────────────────
def parse_lot(lot_id: str) -> Tuple[str, str, str, int]:
    parts = str(lot_id).split(":")
    if len(parts) != 4:
        raise CompareError(f"Lot_ID の形が違います（<sku>:<region>:<週>:<連番>）: {lot_id!r}")
    return parts[0], parts[1], parts[2], int(parts[3])


def supply_by_request_week(run: dict) -> pd.DataFrame:
    """key x request week: demand / on_time / early / late / backlog_end (lots), by Lot_ID."""
    labels = run["week_labels"]
    widx = {w: i for i, w in enumerate(labels)}
    dem = run["demand"]
    demand_lots = {}
    for s, g, w, q in dem[["sku_id", "region", "week", "quantity"]].itertuples(index=False):
        for seq in range(1, int(q) + 1):
            demand_lots[f"{s}:{g}:{w}:{seq:05d}"] = (s, g, w)
    cs = run["ship"][run["ship"]["kind"] == K_CONSUMER]
    shipped: Dict[str, int] = {}
    for lot, node, wk, lots in cs[["lot_id", "node", "ship_week_index", "lots"]].itertuples(index=False):
        if lot not in demand_lots:
            raise CompareError(f"{run['run_dir']}: 市場の実出荷の Lot_ID {lot} が需要（demand_forecast.csv）にありません")
        s, g, w, _ = parse_lot(lot)
        if node != g:
            raise CompareError(f"{run['run_dir']}: Lot_ID {lot} が別の市場 {node} で出荷されています")
        if lot in shipped:
            raise CompareError(f"{run['run_dir']}: Lot_ID {lot} が 2 回出荷されています")
        if int(lots) != 1:
            raise CompareError(f"{run['run_dir']}: Lot_ID {lot} の出荷の lots が 1 ではありません（{lots}）")
        shipped[lot] = int(wk)
    agg = defaultdict(lambda: {c: 0 for c in SUPPLY_COLS})
    for lot, (s, g, w) in demand_lots.items():
        a = agg[(s, g, w)]
        a["demand"] += 1
        if lot not in shipped:
            a["backlog_end"] += 1
            continue
        if w not in widx:
            raise CompareError(f"{run['run_dir']}: 要求週 {w} が計画の週にありません（{lot}）")
        d = shipped[lot] - widx[w]
        a["on_time" if d == 0 else ("early" if d < 0 else "late")] += 1
    rows = [{"sku_id": s, "region": g, "request_week": w, **v} for (s, g, w), v in agg.items()]
    # keys with zero demand in some weeks: keep every demand row (quantity 0 too)
    for s, g, w, q in dem[["sku_id", "region", "week", "quantity"]].itertuples(index=False):
        if int(q) == 0:
            rows.append({"sku_id": s, "region": g, "request_week": w, **{c: 0 for c in SUPPLY_COLS}})
    df = pd.DataFrame(rows)
    return df.sort_values(["sku_id", "region", "request_week"]).reset_index(drop=True)


def check_against_flow(sup: pd.DataFrame, run: dict, name: str) -> pd.DataFrame:
    """Per key totals vs Flow Check table 2. Raises CompareError on any difference."""
    tot = sup.groupby(["sku_id", "region"])[SUPPLY_COLS].sum().reset_index()
    fl = run["flow"]
    fl = fl[~fl["product"].astype(str).str.startswith("Σ") & ~fl["leaf"].fillna("").astype(str).str.startswith("Σ")]
    fl = fl.rename(columns={"product": "sku_id", "leaf": "region"})
    m = tot.merge(fl[["sku_id", "region"] + SUPPLY_COLS], on=["sku_id", "region"], how="outer",
                  suffixes=("", "_flow_check"), indicator=True)
    bad = []
    for _, r in m.iterrows():
        if r["_merge"] != "both":
            bad.append(f"{r['sku_id']}:{r['region']} は片方にしかありません（{r['_merge']}）")
            continue
        for c in SUPPLY_COLS:
            if int(r[c]) != int(r[c + "_flow_check"]):
                bad.append(f"{r['sku_id']}:{r['region']} {c}: Lot_ID で数えた {int(r[c])} ≠ Flow Check {int(r[c + '_flow_check'])}")
    if bad:
        raise CompareError(f"{name}: 要求週別の供給の合計が Flow Check の表 2 と合いません:\n  " + "\n  ".join(bad))
    m = m.drop(columns="_merge")
    m.insert(0, "case", name)
    m["flow_check_match"] = True
    return m


def side_by_side(a: pd.DataFrame, b: pd.DataFrame, keys: List[str], cols: List[str]) -> pd.DataFrame:
    x = a[keys + cols].merge(b[keys + cols], on=keys, how="outer", suffixes=("_base", "_alt")).fillna(0)
    for c in cols:
        x[f"{c}_diff"] = x[f"{c}_alt"] - x[f"{c}_base"]
    return x


# ── 金額 ─────────────────────────────────────────────────────────────
def _has_basis(series: pd.Series, b: str) -> pd.Series:
    return series.fillna("").astype(str).str.split(",").apply(lambda xs: b in xs or "all" in xs)


def money_by_week_sku(run: dict, name: str) -> pd.DataFrame:
    """Consolidated round-2 profit by week x SKU from vc_money_lines; checked against vc_v3_weekly."""
    ent = run["entity"]
    cons = set(ent.loc[ent["consolidated"].astype(str).str.strip() == "1", "entity_id"])
    m = run["money"]
    m = m[m["entity"].isin(cons) & (m["valued"].astype(int) == 1)].copy()
    rev = m[(m["kind"] == "revenue") & (m["scope"] == "external")]
    cogs = m[(m["kind"] == "cogs") & (m["scope"] == "external") & _has_basis(m["basis"], "group")]
    exp = m[m["kind"] == "expense"]
    labels = run["week_labels"]
    prods = sorted(set(m["product"].fillna("(none)")))
    out = {(w, p): {c: 0.0 for c in MONEY_COLS} for w in range(len(labels)) for p in prods}
    for frame, col in ((rev, "external_revenue"), (cogs, "external_cogs_group"), (exp, "expense")):
        g = frame.assign(product=frame["product"].fillna("(none)")).groupby(["week_index", "product"])["amt_hq"].sum()
        for (w, p), v in g.items():
            out[(int(w), p)][col] += float(v)
    rows = []
    for (w, p), v in out.items():
        v["profit_r2"] = v["external_revenue"] - v["external_cogs_group"] - v["expense"]
        rows.append({"week_index": w, "week": labels[w], "product": p, **v})
    df = pd.DataFrame(rows).sort_values(["week_index", "product"]).reset_index(drop=True)
    v3 = run["v3"][run["v3"]["group_key"] == "GROUP"].set_index("week_index")
    df["in_report"] = df["week_index"].map(lambda i: str(v3.loc[i, "in_report"]) == "True")
    # check: sum over SKU == profit_r2_hq_wk, every week
    s = df.groupby("week_index")["profit_r2"].sum()
    bad = [(labels[i], s[i], float(v3.loc[i, "profit_r2_hq_wk"])) for i in s.index
           if abs(s[i] - float(v3.loc[i, "profit_r2_hq_wk"])) > TOL]
    if bad:
        raise CompareError(f"{name}: SKU 別の試算利益の合計が vc_v3_weekly.csv の profit_r2_hq_wk と合いません "
                           f"（{len(bad)} 週。最初：{bad[0][0]} 明細 {bad[0][1]:,.2f} ≠ v3 {bad[0][2]:,.2f}）")
    # unvalued lines in scope: note (not 0)
    mu = run["money"]
    nun = int(((mu["entity"].isin(cons)) & (mu["valued"].astype(int) != 1)).sum())
    df.attrs["unvalued_consolidated_lines"] = nun
    df.insert(0, "case", name)
    return df


def money_totals(mb: pd.DataFrame, run: dict, name: str) -> pd.DataFrame:
    rows = []
    for period, sel in (("report", mb["in_report"]), ("full", pd.Series(True, index=mb.index))):
        g = mb[sel].groupby("product")[MONEY_COLS].sum()
        for p, v in g.iterrows():
            rows.append({"case": name, "period": period, "product": p, **v.to_dict()})
        rows.append({"case": name, "period": period, "product": "*", **g.sum().to_dict()})
    v3 = run["v3"][run["v3"]["group_key"] == "GROUP"]
    ppc = run["ppc"]
    for r in rows:
        if r["product"] == "*":
            sel = v3["in_report"].astype(str) == "True" if r["period"] == "report" else slice(None)
            r["v3_profit_r2_hq"] = float(v3.loc[sel, "profit_r2_hq_wk"].sum())
            r["ppc_revenue_full"] = ppc.get("total_revenue_base")
            r["ppc_profit_full"] = ppc.get("gross_profit_base")
    return pd.DataFrame(rows)


# ── 在庫・工場・年齢 ──────────────────────────────────────────────────
def inventory_weekly(run: dict, name: str) -> pd.DataFrame:
    inv = run["inv"]
    inv = inv[inv["external"].astype(int) == 0]
    g = inv.groupby(["week_index", "week", "location_kind", "location", "product"]).agg(
        lots=("lots", "sum"), group_hq=("group_hq", "sum")).reset_index()
    g.insert(0, "case", name)
    return g


def factory_weekly(run: dict, name: str) -> pd.DataFrame:
    labels = run["week_labels"]
    sh = run["ship"][run["ship"]["kind"] == K_HANDOFF]
    prod = sh.groupby(["product", "ship_week_index"])["lots"].sum()
    tree = run["tree"]
    mom = tree[tree["node_type"] == "mom"]
    yld = {r["product_name"]: float(r["yield_rate"]) if str(r.get("yield_rate", "")).strip() not in ("", "nan") else 1.0
           for _, r in mom.iterrows()}
    momname = {r["product_name"]: r["node_name"] for _, r in mom.iterrows()}
    cap = run["capacity"]
    capd = {}
    for _, r in cap.iterrows():
        if r.get("node_name", momname.get(r["sku_id"])) == momname.get(r["sku_id"]):
            capd[(r["sku_id"], r["week"])] = (r.get("max_supply", ""), r.get("cap_soft", ""))

    def fl(v, y):
        try:
            return math.floor(float(v) * y + 1e-9)
        except (TypeError, ValueError):
            return None
    rows = []
    for p in sorted(momname):
        for i, w in enumerate(labels):
            hard, soft = capd.get((p, w), ("", ""))
            rows.append({"case": name, "product": p, "week_index": i, "week": w,
                         "production_lots": int(prod.get((p, i), 0)),
                         "max_supply": hard, "cap_soft": soft, "yield_rate": yld.get(p, 1.0),
                         "shippable_hard": fl(hard, yld.get(p, 1.0)), "shippable_soft": fl(soft, yld.get(p, 1.0))})
    return pd.DataFrame(rows)


def age_summary(run: dict, name: str) -> pd.DataFrame:
    s = run["shelf"].copy()
    s.insert(0, "case", name)
    return s


# ── 差の出た週・代表の lot ─────────────────────────────────────────────
def diff_weeks(sup_sbs: pd.DataFrame, money_sbs: pd.DataFrame, labels: List[str]) -> pd.DataFrame:
    rows = []
    cols = [f"{c}_diff" for c in ("on_time", "early", "late", "backlog_end", "demand")]
    s = sup_sbs.assign(absdiff=sup_sbs[cols].abs().sum(axis=1))
    by_w = s.groupby("request_week")["absdiff"].sum()
    nz = by_w[by_w > 0]
    if len(nz):
        rows.append({"measure": "supply_by_request_week", "which": "first", "week": nz.index.min(),
                     "abs_diff": float(nz[nz.index.min()])})
        rows.append({"measure": "supply_by_request_week", "which": "max", "week": nz.idxmax(),
                     "abs_diff": float(nz.max())})
    else:
        rows.append({"measure": "supply_by_request_week", "which": "none", "week": "", "abs_diff": 0.0})
    pw = money_sbs.groupby("week")["profit_r2_diff"].sum()
    nz = pw[pw.abs() > TOL]
    if len(nz):
        rows.append({"measure": "profit_r2_by_week", "which": "first", "week": nz.index.min(),
                     "abs_diff": float(abs(nz[nz.index.min()]))})
        rows.append({"measure": "profit_r2_by_week", "which": "max", "week": nz.abs().idxmax(),
                     "abs_diff": float(nz.abs().max())})
    else:
        rows.append({"measure": "profit_r2_by_week", "which": "none", "week": "", "abs_diff": 0.0})
    return pd.DataFrame(rows)


def _lot_status(run: dict) -> Dict[str, Optional[int]]:
    cs = run["ship"][run["ship"]["kind"] == K_CONSUMER]
    return dict(zip(cs["lot_id"], cs["ship_week_index"]))


def pick_representative_lots(base: dict, alt: dict, dw: pd.DataFrame) -> List[Tuple[str, str]]:
    """[(reason, lot_id)]: one lot per 'first'/'max' week whose fate differs between the cases."""
    sb, sa = _lot_status(base), _lot_status(alt)
    picks = []
    for _, r in dw.iterrows():
        if r["which"] not in ("first", "max"):
            continue
        week = r["week"]
        if r["measure"] == "supply_by_request_week":
            cand = []
            for run, other_dem in ((alt, base), (base, alt)):
                d = run["demand"]
                for s, g, w, q in d[d["week"] == week][["sku_id", "region", "week", "quantity"]].itertuples(index=False):
                    for seq in range(1, int(q) + 1):
                        cand.append(f"{s}:{g}:{w}:{seq:05d}")
            for lot in sorted(set(cand)):
                if sb.get(lot, "x") != sa.get(lot, "x"):
                    picks.append((f"supply {r['which']} request week {week}", lot))
                    break
        else:
            mb = base["money"][base["money"]["week"] == week]
            ma = alt["money"][alt["money"]["week"] == week]
            ga = ma.groupby("lot_id")["amt_hq"].sum()
            gb = mb.groupby("lot_id")["amt_hq"].sum()
            for lot in sorted(set(ga.index) | set(gb.index)):
                if abs(float(ga.get(lot, 0.0)) - float(gb.get(lot, 0.0))) > TOL:
                    picks.append((f"profit {r['which']} week {week}", lot))
                    break
    seen, out = set(), []
    for reason, lot in picks:
        if lot not in seen:
            seen.add(lot)
            out.append((reason, lot))
    return out


def lot_detail(runs: Dict[str, dict], reason: str, lot: str) -> List[dict]:
    s, g, w, seq = parse_lot(lot)
    rows = []
    for name, run in runs.items():
        d = run["demand"]
        q = d[(d["sku_id"] == s) & (d["region"] == g) & (d["week"] == w)]["quantity"]
        qty = int(q.iloc[0]) if len(q) else 0
        rows.append({"reason": reason, "lot_id": lot, "case": name, "step": "1 demand",
                     "week": w, "what": f"{s} {g} request week {w}: demand {qty} lots; this lot is seq {seq}"
                                       + ("" if seq <= qty else " (NOT in this case's demand)"),
                     "amount_hq": ""})
        sh = run["ship"][run["ship"]["lot_id"] == lot].sort_values(["ship_week_index"])
        if sh.empty:
            rows.append({"reason": reason, "lot_id": lot, "case": name, "step": "2 shipment", "week": "",
                         "what": "no shipment record", "amount_hq": ""})
        for _, x in sh.iterrows():
            rows.append({"reason": reason, "lot_id": lot, "case": name, "step": "2 shipment",
                         "week": x["ship_week"], "what": f"{x['kind']} {x['edge']} (arrive {x['arrival_week']})",
                         "amount_hq": ""})
        mo = run["money"][run["money"]["lot_id"] == lot].sort_values(["week_index", "line_id"])
        if mo.empty:
            rows.append({"reason": reason, "lot_id": lot, "case": name, "step": "3 money", "week": "",
                         "what": "no money line", "amount_hq": ""})
        for _, x in mo.iterrows():
            rows.append({"reason": reason, "lot_id": lot, "case": name, "step": "3 money", "week": x["week"],
                         "what": f"{x['entity']} {x['kind']}/{x['scope']}/{x['family']} basis={x['basis']} node={x['node']}",
                         "amount_hq": x["amt_hq"]})
    return rows


# ── 境界・固定費 ──────────────────────────────────────────────────────
def boundary(sup_sbs: pd.DataFrame, money_sbs: pd.DataFrame, labels: List[str]) -> pd.DataFrame:
    edge = {labels[0]: "first_week", labels[-2]: "last_2_weeks", labels[-1]: "last_2_weeks"}
    rows = []
    for w, tag in edge.items():
        s = sup_sbs[sup_sbs["request_week"] == w]
        m = money_sbs[money_sbs["week"] == w]
        rows.append({"week": w, "edge": tag,
                     "backlog_end_base": int(s["backlog_end_base"].sum()),
                     "backlog_end_alt": int(s["backlog_end_alt"].sum()),
                     "supply_abs_diff": int(s[[c for c in s.columns if c.endswith("_diff")]].abs().sum().sum()),
                     "profit_r2_diff": float(m["profit_r2_diff"].sum())})
    return pd.DataFrame(rows)


def factory_idle(fw: pd.DataFrame) -> pd.DataFrame:
    """Weeks where the factory produced less than its shippable soft capacity (per case, product)."""
    x = fw.copy()
    x["shippable_soft"] = pd.to_numeric(x["shippable_soft"], errors="coerce")
    x = x[x["shippable_soft"].notna() & (x["production_lots"] < x["shippable_soft"])].copy()
    x["unused_vs_soft"] = x["shippable_soft"] - x["production_lots"]
    return x[["case", "product", "week_index", "week", "production_lots", "shippable_soft", "unused_vs_soft"]]


# ── 数量配分（上位 Demand Plan）の結果 ─────────────────────────────────
UDP_COLS = ["q1_original", "q2_in_scope", "q3_unallocated", "on_time", "early", "late", "q5_backlog_end"]


def _udp_dir(path: str) -> str:
    """The folder holding udp_result_by_request.csv: the path itself or its only sub-folder that has it."""
    if os.path.exists(os.path.join(path, "udp_result_by_request.csv")):
        return path
    hits = sorted(glob.glob(os.path.join(path, "*", "udp_result_by_request.csv")))
    if len(hits) != 1:
        raise CompareError(f"{path}: udp_result_by_request.csv が 1 つ見つかりません（{hits}）")
    return os.path.dirname(hits[0])


def load_udp(path: str) -> pd.DataFrame:
    """key x request week: q1 / q2 / q3 (selection ledger) and on_time / early / late / q5 (result)."""
    d = _udp_dir(path)
    led = _csv(os.path.join(d, "udp_selection_ledger.csv"), dtype=str)
    res = _csv(os.path.join(d, "udp_result_by_request.csv"), dtype=str).set_index("source_demand_ref")
    rows = []
    for _, x in led.iterrows():
        ref = x["source_demand_ref"]
        sku, reg, wk = ref.split("|")
        if ref not in res.index:
            raise CompareError(f"{d}: {ref} が udp_result_by_request.csv にありません")
        r = res.loc[ref]
        a = {"sku_id": sku, "region": reg, "request_week": wk,
             "q1_original": int(x["q1"]), "q2_in_scope": int(x["q2"]), "q3_unallocated": int(x["q3"]),
             "on_time": int(r["on_time"]), "early": int(r["early"]), "late": int(r["late"]),
             "q5_backlog_end": int(r["q5"])}
        if int(r["q2"]) != a["q2_in_scope"]:
            raise CompareError(f"{d}: {ref} の q2 が台帳 {a['q2_in_scope']} と結果 {r['q2']} で違います")
        if a["q1_original"] != a["q2_in_scope"] + a["q3_unallocated"] or \
                a["q2_in_scope"] != a["on_time"] + a["early"] + a["late"] + a["q5_backlog_end"]:
            raise CompareError(f"{d}: {ref} で ①＝②＋③ または ②＝④＋⑤ が成り立ちません: {a}")
        rows.append(a)
    df = pd.DataFrame(rows)
    df.attrs["udp_dir"] = d
    return df


def allocation_table(sup: pd.DataFrame, udp: Optional[pd.DataFrame], name: str) -> pd.DataFrame:
    """Supply by request week with the allocation split.

    With udp: the money run's shipments (by Lot_ID, its demand = the allocated demand) must equal the
    quantity-allocation result per key x request week, else CompareError. Without udp: q1 = q2 = demand,
    q3 = 0, q5 = backlog_end.
    """
    k = ["sku_id", "region", "request_week"]
    plain = sup[k].copy()
    plain["q1_original"] = sup["demand"].astype(int)
    plain["q2_in_scope"] = sup["demand"].astype(int)
    plain["q3_unallocated"] = 0
    for c in ("on_time", "early", "late"):
        plain[c] = sup[c].astype(int)
    plain["q5_backlog_end"] = sup["backlog_end"].astype(int)
    if udp is None:
        plain.insert(0, "allocation_source", "none (demand as given)")
        return plain
    m = plain.merge(udp, on=k, how="outer", suffixes=("_run", ""), indicator=True)
    bad = []
    for _, r in m.iterrows():
        where = f"{r['sku_id']}:{r['region']}:{r['request_week']}"
        if r["_merge"] == "left_only":
            if r["q2_in_scope_run"] != 0:
                bad.append(f"{where} は数量配分の結果に無いのに金額の実行の需要 {int(r['q2_in_scope_run'])}")
            continue
        if r["_merge"] == "right_only":
            if r["q2_in_scope"] != 0:
                bad.append(f"{where} は金額の実行の需要に無い（② {int(r['q2_in_scope'])}）")
            continue
        for run_c, udp_c in (("q2_in_scope_run", "q2_in_scope"), ("on_time_run", "on_time"), ("early_run", "early"),
                             ("late_run", "late"), ("q5_backlog_end_run", "q5_backlog_end")):
            if int(r[run_c]) != int(r[udp_c]):
                bad.append(f"{where} {udp_c}: 金額の実行 {int(r[run_c])} ≠ 数量配分 {int(r[udp_c])}")
    if bad:
        raise CompareError(f"{name}: 金額の実行の出荷が数量配分モードの結果と合いません（{len(bad)} 件）:\n  "
                           + "\n  ".join(bad[:20]))
    out = m[m["_merge"] != "left_only"][k + UDP_COLS].fillna(0)
    for c in UDP_COLS:
        out[c] = out[c].astype(int)
    out.insert(0, "allocation_source", udp.attrs.get("udp_dir", "udp"))
    return out.sort_values(k).reset_index(drop=True)


# ── 固定費の逆転点（GPT-MC 業務定義 v0.1 §3・§4）────────────────────────
FIXED_COST_COLS = ["case", "cost_item", "entity", "paid_start_week", "paid_end_week", "weekly_amount",
                   "currency", "note"]
ZERO_TOL = 0.5      # yen


def _wk_monday(label: str):
    import datetime
    y, w = str(label).strip().split("-W")
    return datetime.date.fromisocalendar(int(y), int(w), 1)


def paid_weeks_in_report(paid_start: str, paid_end: str, report_start: str, report_end: str) -> int:
    """ISO weeks in [paid_start, paid_end] ∩ [report_start, report_end] (both ends included)."""
    try:
        a, b = _wk_monday(paid_start), _wk_monday(paid_end)
        ra, rb = _wk_monday(report_start), _wk_monday(report_end)
    except (ValueError, TypeError):
        raise CompareError(f"週のラベルが不正です: {paid_start}〜{paid_end}（報告期間 {report_start}〜{report_end}）")
    if b < a:
        raise CompareError(f"有償の週の終わり {paid_end} が始まり {paid_start} より前です")
    lo, hi = max(a, ra), min(b, rb)
    return 0 if hi < lo else (hi - lo).days // 7 + 1


def read_fixed_cost_plan(path: str) -> pd.DataFrame:
    df = _csv(path, dtype=str, keep_default_na=False)
    missing = [c for c in FIXED_COST_COLS if c not in df.columns]
    if missing:
        raise CompareError(f"{path}: 列が足りません {missing}")
    for i, r in df.iterrows():
        if r["case"] not in ("base", "alt"):
            raise CompareError(f"{path} の {i + 2} 行目: case は base か alt（{r['case']!r}）")
        if r["weekly_amount"].strip() != "":
            try:
                v = float(r["weekly_amount"])
            except ValueError:
                raise CompareError(f"{path} の {i + 2} 行目: weekly_amount={r['weekly_amount']!r} は数値ではありません")
            if v < 0:
                raise CompareError(f"{path} の {i + 2} 行目: weekly_amount は 0 以上")
    if df.duplicated(["case", "cost_item"]).any():
        raise CompareError(f"{path}: 同じ case・cost_item の行が重複しています")
    return df


def boundary_label(dp0: Optional[float], dw: Optional[int], undetermined: str = "") -> Tuple[str, Optional[float]]:
    """Business definition v0.1 §4 table. Returns (label, f* or None)."""
    if undetermined or dp0 is None or dw is None or (isinstance(dp0, float) and math.isnan(dp0)):
        return f"未算出（{undetermined or '値が未確定'}）", None
    zero = abs(dp0) < ZERO_TOL
    if dw == 0:
        return ("順位変化なし（発生週数が同じ）。両案同額" if zero else "順位変化なし（発生週数が同じ）"), None
    if zero:
        return "0円で同額（正の週額では発生週数の少ない案が上）", None
    f = dp0 / dw
    if dp0 > 0 and dw > 0:
        return "f* = ΔP0 ÷ ΔW（f が小さければ alt が上、等しければ同額、大きければ base が上）", f
    if dp0 < 0 and dw > 0:
        return "正の境目なし（base が上）", None
    if dw < 0 and dp0 < 0:
        return "f* = ΔP0 ÷ ΔW（f が境目を超えると alt が上）", f
    return "正の境目なし（alt が上）", None


def report_p0(run: dict) -> Tuple[float, str, str, str]:
    """(P0, valuation status, report_start, report_end) from vc_v3_weekly.csv (GROUP, in_report)."""
    v3 = run["v3"][run["v3"]["group_key"] == "GROUP"]
    rep = v3[v3["in_report"].astype(str) == "True"].sort_values("week_index")
    p0 = float(rep["profit_r2_hq_wk"].sum())
    nun = int(rep["n_unvalued_wk"].sum()) if "n_unvalued_wk" in rep.columns else 0
    nlot = int((rep["lots_unvalued"] > 0).sum()) if "lots_unvalued" in rep.columns else 0
    status = "評価済み" if nun == 0 and nlot == 0 else f"一部未評価（未評価の明細 {nun}、未評価の在庫の週 {nlot}）"
    return p0, status, str(rep["week"].iloc[0]), str(rep["week"].iloc[-1])


FC_COLS = ["cost_item", "entity", "P0_base", "P0_alt", "paid_start_base", "paid_end_base", "W_base",
           "paid_start_alt", "paid_end_alt", "W_alt", "weekly_amount_base", "weekly_amount_alt", "cost_base",
           "cost_alt", "P_after_base", "P_after_alt", "delta_P0", "delta_P0_by_product", "delta_W", "boundary",
           "f_star_per_week", "delta_P_after", "valuation_status", "note"]


def fixed_cost_table(plan: Optional[pd.DataFrame], p0: Dict[str, float], status: Dict[str, str],
                     report_start: str, report_end: str, hq_currency: str = "JPY",
                     dp0_by_product: str = "") -> pd.DataFrame:
    """One row per cost_item: per-case P0, paid weeks, W, weekly amount, cost, P0 after cost, ΔP0, ΔW, boundary."""
    dp0 = p0["alt"] - p0["base"]
    unval = [f"{c}: {status[c]}" for c in ("base", "alt") if status[c] != "評価済み"]
    if plan is None or plan.empty:
        lab, _ = boundary_label(dp0, None, "固定費の表なし（有償週未設定）")
        return pd.DataFrame([{"cost_item": "", "entity": "", "P0_base": p0["base"], "P0_alt": p0["alt"],
                              "delta_P0": dp0, "delta_P0_by_product": dp0_by_product, "delta_W": "",
                              "boundary": lab, "f_star_per_week": "",
                              "valuation_status": "; ".join(unval) or "評価済み"}], columns=FC_COLS)
    rows = []
    for item in sorted(set(plan["cost_item"])):
        r = {"cost_item": item,
             "entity": ",".join(sorted(set(plan.loc[plan["cost_item"] == item, "entity"])))}
        amounts, ccys = {}, set()
        for c in ("base", "alt"):
            sub = plan[(plan["cost_item"] == item) & (plan["case"] == c)]
            r[f"P0_{c}"] = p0[c]
            if sub.empty:
                r[f"paid_start_{c}"], r[f"paid_end_{c}"], r[f"W_{c}"] = "", "", 0
                amounts[c] = None
                continue
            x = sub.iloc[0]
            r[f"paid_start_{c}"], r[f"paid_end_{c}"] = x["paid_start_week"], x["paid_end_week"]
            r[f"W_{c}"] = paid_weeks_in_report(x["paid_start_week"], x["paid_end_week"], report_start, report_end)
            amounts[c] = float(x["weekly_amount"]) if x["weekly_amount"].strip() != "" else None
            ccys.add(x["currency"].strip())
        dw = r["W_alt"] - r["W_base"]
        reason = ""
        if unval:
            reason = "連結利益未評価"
        elif ccys - {hq_currency}:
            reason = f"共通の円建て週額の条件外（通貨 {sorted(ccys)}）"
        elif all(amounts[c] is not None for c in ("base", "alt")) and amounts["base"] != amounts["alt"]:
            reason = "共通の円建て週額の条件外（週額が案で違う）"
        lab, fstar = boundary_label(dp0, dw, reason)
        r.update({"delta_P0": dp0, "delta_P0_by_product": dp0_by_product, "delta_W": dw,
                  "boundary": lab, "f_star_per_week": "" if fstar is None else fstar})
        for c in ("base", "alt"):
            a = amounts[c]
            r[f"weekly_amount_{c}"] = "" if a is None else a
            r[f"cost_{c}"] = "" if a is None else a * r[f"W_{c}"]
            r[f"P_after_{c}"] = "" if a is None else p0[c] - a * r[f"W_{c}"]
        both = all(amounts[c] is not None for c in ("base", "alt"))
        r["delta_P_after"] = r["P_after_alt"] - r["P_after_base"] if both else ""
        r["valuation_status"] = "; ".join(unval) or "評価済み"
        r["note"] = "" if both else "週額が未設定：境目だけ"
        rows.append(r)
    return pd.DataFrame(rows, columns=FC_COLS)


# ── 全体 ─────────────────────────────────────────────────────────────
def compare(base_run: str, alt_run: str, base_model: str, alt_model: str, out: str,
            fixed_cost_plan: Optional[str] = None, base_name: str = "base", alt_name: str = "alt",
            base_udp: Optional[str] = None, alt_udp: Optional[str] = None) -> dict:
    os.makedirs(out, exist_ok=True)
    base, alt = load_run(base_run, base_model), load_run(alt_run, alt_model)
    if base["week_labels"] != alt["week_labels"]:
        raise CompareError("2 案の計画の週が違います（計画期間をそろえてください）")
    labels = base["week_labels"]
    res = {}

    dd = demand_diff(base, alt)
    dd.to_csv(os.path.join(out, "demand_diff.csv"), index=False)
    epd = entry_plan_diff(base, alt)
    epd.to_csv(os.path.join(out, "entry_plan_diff.csv"), index=False)

    sb, sa = supply_by_request_week(base), supply_by_request_week(alt)
    chk = pd.concat([check_against_flow(sb, base, base_name), check_against_flow(sa, alt, alt_name)])
    chk.to_csv(os.path.join(out, "supply_by_key.csv"), index=False)
    ssbs = side_by_side(sb, sa, ["sku_id", "region", "request_week"], SUPPLY_COLS)
    ssbs.to_csv(os.path.join(out, "supply_by_request_week.csv"), index=False)
    alloc = None
    if base_udp or alt_udp:
        ab = allocation_table(sb, load_udp(base_udp) if base_udp else None, base_name)
        aa = allocation_table(sa, load_udp(alt_udp) if alt_udp else None, alt_name)
        k3 = ["sku_id", "region", "request_week"]
        alloc = side_by_side(ab.drop(columns="allocation_source"), aa.drop(columns="allocation_source"), k3, UDP_COLS)
        alloc.to_csv(os.path.join(out, "supply_allocation_by_request_week.csv"), index=False)
        ak = side_by_side(ab.groupby(["sku_id", "region"])[UDP_COLS].sum().reset_index(),
                          aa.groupby(["sku_id", "region"])[UDP_COLS].sum().reset_index(), ["sku_id", "region"], UDP_COLS)
        ak.insert(0, "allocation_source_alt", aa["allocation_source"].iloc[0])
        ak.insert(0, "allocation_source_base", ab["allocation_source"].iloc[0])
        ak.to_csv(os.path.join(out, "supply_allocation_by_key.csv"), index=False)

    mb, ma = money_by_week_sku(base, base_name), money_by_week_sku(alt, alt_name)
    msbs = side_by_side(mb.drop(columns="case"), ma.drop(columns="case"),
                        ["week_index", "week", "product", "in_report"], MONEY_COLS)
    msbs.to_csv(os.path.join(out, "money_by_week_sku.csv"), index=False)
    tb, ta = money_totals(mb, base, base_name), money_totals(ma, alt, alt_name)
    tsbs = side_by_side(tb.drop(columns="case"), ta.drop(columns="case"), ["period", "product"],
                        MONEY_COLS + ["v3_profit_r2_hq", "ppc_revenue_full", "ppc_profit_full"])
    tsbs.to_csv(os.path.join(out, "money_totals.csv"), index=False)

    ib, ia = inventory_weekly(base, base_name), inventory_weekly(alt, alt_name)
    pd.concat([ib, ia]).to_csv(os.path.join(out, "inventory_weekly.csv"), index=False)
    isku = side_by_side(ib.groupby(["week_index", "week", "product"])[["lots", "group_hq"]].sum().reset_index(),
                        ia.groupby(["week_index", "week", "product"])[["lots", "group_hq"]].sum().reset_index(),
                        ["week_index", "week", "product"], ["lots", "group_hq"])
    isku.to_csv(os.path.join(out, "inventory_by_week_sku.csv"), index=False)
    fw = pd.concat([factory_weekly(base, base_name), factory_weekly(alt, alt_name)])
    fw.to_csv(os.path.join(out, "factory_weekly.csv"), index=False)
    ag = pd.concat([age_summary(base, base_name), age_summary(alt, alt_name)])
    ag.to_csv(os.path.join(out, "age_summary.csv"), index=False)

    dw = diff_weeks(ssbs, msbs, labels)
    dw.to_csv(os.path.join(out, "diff_weeks.csv"), index=False)
    picks = pick_representative_lots(base, alt, dw)
    det = []
    for reason, lot in picks:
        det += lot_detail({base_name: base, alt_name: alt}, reason, lot)
    pd.DataFrame(det, columns=["reason", "lot_id", "case", "step", "week", "what", "amount_hq"]).to_csv(
        os.path.join(out, "representative_lots.csv"), index=False)

    bd = boundary(ssbs, msbs, labels)
    bd.to_csv(os.path.join(out, "boundary.csv"), index=False)
    fi = factory_idle(fw)
    fi.to_csv(os.path.join(out, "factory_idle_weeks.csv"), index=False)
    pb, stb, rs, re_ = report_p0(base)
    pa, sta, rs2, re2 = report_p0(alt)
    if (rs, re_) != (rs2, re2):
        raise CompareError(f"2 案の報告期間が違います（{rs}〜{re_} と {rs2}〜{re2}）")
    rep = tsbs[(tsbs["period"] == "report") & (tsbs["product"] != "*")]
    by_prod = "; ".join(f"{r.product}: {r.profit_r2_diff:,.0f}" for r in rep.itertuples())
    plan = read_fixed_cost_plan(fixed_cost_plan) if fixed_cost_plan else None
    fc = fixed_cost_table(plan, {"base": pb, "alt": pa}, {"base": stb, "alt": sta}, rs, re_, dp0_by_product=by_prod)
    fc.to_csv(os.path.join(out, "fixed_cost_breakeven.csv"), index=False)

    res.update({"labels": labels, "demand_diff": dd, "entry_plan_diff": epd, "supply": ssbs, "supply_check": chk,
                "money": msbs, "totals": tsbs, "inventory_sku": isku, "factory": fw, "age": ag,
                "diff_weeks": dw, "picks": picks, "boundary": bd, "factory_idle": fi, "fixed_cost": fc, "alloc": alloc,
                "unvalued": {base_name: mb.attrs.get("unvalued_consolidated_lines", 0),
                             alt_name: ma.attrs.get("unvalued_consolidated_lines", 0)},
                "base_name": base_name, "alt_name": alt_name})
    write_summary(res, os.path.join(out, "comparison_summary.md"), base_run, alt_run, base_model, alt_model)
    return res


def _fmt(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if math.isnan(f):
        return "—"
    return f"{f:,.0f}" if abs(f - round(f)) < 1e-6 else f"{f:,.2f}"


def write_summary(res: dict, path: str, base_run, alt_run, base_model, alt_model) -> None:
    bn, an = res["base_name"], res["alt_name"]
    L = [f"# 2 案の比較（{bn} → {an}）", "",
         f"- base（{bn}）：実行 `{base_run}`、モデル `{base_model}`",
         f"- alt（{an}）：実行 `{alt_run}`、モデル `{alt_model}`",
         f"- 計画の週：{res['labels'][0]}〜{res['labels'][-1]}（{len(res['labels'])} 週）", "",
         "## 入力の表の違い", ""]
    epd = res["entry_plan_diff"]
    L += ["（違いなし）"] if epd.empty else [f"- {r.sku_id}:{r.region} `{r.column}`：{r.base} → {r.alt}"
                                            for r in epd.itertuples()]
    dd = res["demand_diff"]
    g = dd.groupby(["sku_id", "region"])[["demand_base", "demand_alt", "diff"]].sum().reset_index()
    L += ["", "## 需要（lot、全計画期間）", "", "| 鍵 | base | alt | 差 |", "|---|---:|---:|---:|"]
    L += [f"| {r.sku_id}:{r.region} | {r.demand_base} | {r.demand_alt} | {r.diff:+d} |" for r in g.itertuples()]
    s = res["supply"]
    gs = s.groupby(["sku_id", "region"])[[f"{c}_{x}" for c in SUPPLY_COLS for x in ("base", "alt")]].sum().reset_index()
    L += ["", "## 供給（Lot_ID で要求週へ戻した合計。Flow Check の表 2 と一致を確認済み）", "",
          "| 鍵 | 需要 base/alt | 当週 base/alt | 遅配 base/alt | 早出し base/alt | 期末の未充足 base/alt |",
          "|---|---|---|---|---|---|"]
    for r in gs.itertuples():
        L.append(f"| {r.sku_id}:{r.region} | {r.demand_base:.0f}/{r.demand_alt:.0f} | {r.on_time_base:.0f}/{r.on_time_alt:.0f} "
                 f"| {r.late_base:.0f}/{r.late_alt:.0f} | {r.early_base:.0f}/{r.early_alt:.0f} "
                 f"| {r.backlog_end_base:.0f}/{r.backlog_end_alt:.0f} |")
    al = res.get("alloc")
    if al is not None:
        ga = al.groupby(["sku_id", "region"])[[f"{c}_{x}" for c in UDP_COLS for x in ("base", "alt")]].sum().reset_index()
        L += ["", "## 数量配分（① 元の需要 ＝ ② 供給の対象 ＋ ③ 未配分、② ＝ 当週 ＋ 早出し ＋ 遅配 ＋ ⑤ 配分後の未充足）", "",
              "| 鍵 | ① base/alt | ② base/alt | ③ base/alt | 当週 base/alt | 遅配 base/alt | ⑤ base/alt |",
              "|---|---|---|---|---|---|---|"]
        for r in ga.itertuples():
            L.append(f"| {r.sku_id}:{r.region} | {r.q1_original_base:.0f}/{r.q1_original_alt:.0f} "
                     f"| {r.q2_in_scope_base:.0f}/{r.q2_in_scope_alt:.0f} | {r.q3_unallocated_base:.0f}/{r.q3_unallocated_alt:.0f} "
                     f"| {r.on_time_base:.0f}/{r.on_time_alt:.0f} | {r.late_base:.0f}/{r.late_alt:.0f} "
                     f"| {r.q5_backlog_end_base:.0f}/{r.q5_backlog_end_alt:.0f} |")
        L += ["", "（数量配分の結果を渡した案は、金額の実行の出荷と鍵 × 要求週で一致を確認済み）"]
    t = res["totals"]
    L += ["", "## 試算利益（消去後の連結、円。固定費の前）", "",
          "| 期間 | SKU | 外部売上 base | alt | 差 | 試算利益 base | alt | 差 |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in t.itertuples():
        L.append(f"| {r.period} | {r.product} | {_fmt(r.external_revenue_base)} | {_fmt(r.external_revenue_alt)} | "
                 f"{_fmt(r.external_revenue_diff)} | {_fmt(r.profit_r2_base)} | {_fmt(r.profit_r2_alt)} | {_fmt(r.profit_r2_diff)} |")
    star = t[(t["product"] == "*") & (t["period"] == "full")]
    if len(star):
        r = star.iloc[0]
        L += ["", f"PPC（全計画期間）：売上 base {_fmt(r['ppc_revenue_full_base'])} / alt {_fmt(r['ppc_revenue_full_alt'])}、"
                  f"試算利益 base {_fmt(r['ppc_profit_full_base'])} / alt {_fmt(r['ppc_profit_full_alt'])}"]
    L += [f"未評価の明細（連結の法人）：{res['unvalued']}"]
    isku = res["inventory_sku"]
    last = isku[isku["week_index"] == isku["week_index"].max()]
    L += ["", "## 在庫と年齢", "", "週末の在庫の合計（lot・週）と期末の在庫：", ""]
    for p, gg in isku.groupby("product"):
        e = last[last["product"] == p]
        L.append(f"- {p}：lot・週 base {gg['lots_base'].sum():.0f} / alt {gg['lots_alt'].sum():.0f}、"
                 f"最大 base {gg['lots_base'].max():.0f} / alt {gg['lots_alt'].max():.0f}、"
                 f"期末 base {e['lots_base'].sum():.0f} / alt {e['lots_alt'].sum():.0f}")
    ag = res["age"]
    for r in ag[ag["channel"] == "*"].itertuples():
        L.append(f"- 年齢 {r.case} {r.product}：納品 {r.deliveries}、最大 {r.fifo_age_max} 週、52 週超 {r.over_max_age}")
    L += ["", "## 差の出た週", ""]
    L += [f"- {r.measure} {r.which}：{r.week}（{_fmt(r.abs_diff)}）" for r in res["diff_weeks"].itertuples()]
    L += ["", "代表の lot：" + ("、".join(f"`{lot}`（{reason}）" for reason, lot in res["picks"]) or "なし"),
          "", "## 計画の境界", ""]
    L += [f"- {r.week}（{r.edge}）：期末の未充足 base {r.backlog_end_base} / alt {r.backlog_end_alt}、"
          f"供給の差 {r.supply_abs_diff}、試算利益の差 {_fmt(r.profit_r2_diff)}" for r in res["boundary"].itertuples()]
    fi = res["factory_idle"]
    L += ["", "工場が出荷可能な soft 能力より少なく作った週（計画の両端の効果の候補）："]
    for (c, p), gg in fi.groupby(["case", "product"]):
        L.append(f"- {c} {p}：{', '.join(gg['week'])}（未使用 計 {gg['unused_vs_soft'].sum():.0f} lot）")
    L += ["", "## 固定費の逆転点（GPT-MC 業務定義 v0.1 §4）", ""]
    for fc in res["fixed_cost"].itertuples():
        fs = str(fc.f_star_per_week)
        L.append(f"- {fc.cost_item or '（固定費の表なし）'}：P0 base {_fmt(fc.P0_base)} / alt {_fmt(fc.P0_alt)}、"
                 f"ΔP0 {_fmt(fc.delta_P0)}（{fc.delta_P0_by_product}）、W base {getattr(fc, 'W_base', '')} / alt "
                 f"{getattr(fc, 'W_alt', '')}、ΔW {fc.delta_W} → {fc.boundary}"
                 + (f"：**{_fmt(fc.f_star_per_week)} 円／週**" if fs not in ("", "nan") else "")
                 + f"（{fc.valuation_status}）")
    L.append("")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Compare two scenario runs (reads outputs only)")
    ap.add_argument("--base", required=True, help="run folder of the base case")
    ap.add_argument("--alt", required=True, help="run folder of the alternative case")
    ap.add_argument("--base-model", required=True)
    ap.add_argument("--alt-model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fixed-cost-plan", default=None,
                    help="CSV: case,cost_item,entity,paid_start_week,paid_end_week,weekly_amount,currency,note")
    ap.add_argument("--base-udp", default=None, help="upper demand plan output of the base case (quantity allocation)")
    ap.add_argument("--alt-udp", default=None, help="upper demand plan output of the alt case")
    ap.add_argument("--base-name", default="base")
    ap.add_argument("--alt-name", default="alt")
    a = ap.parse_args(argv)
    try:
        compare(a.base, a.alt, a.base_model, a.alt_model, a.out, a.fixed_cost_plan, a.base_name, a.alt_name,
                a.base_udp, a.alt_udp)
    except CompareError as e:
        print(f"[compare] 止めました: {e}", file=sys.stderr)
        return 2
    print(f"[compare] -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
