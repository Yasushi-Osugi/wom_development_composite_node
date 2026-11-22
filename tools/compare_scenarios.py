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
RequestLetter_Cockpit_Stage3_Step2 A で、増産の確保費（GPT-MC の業務定義 v0.1）のために、固定費の表の
count_outside_report 列（1 なら助走の週も数える）、費目が 2 つ以上のときの合計の行と費目ごとの境目、
planned_output_weeks.csv（計画の生産量ちょうど作った週）を足した。

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
    fixed_cost_breakeven.csv     固定費の逆転点（業務定義 §4：P0・有償の週・W・週額・費用・控除後・ΔP0・ΔW・境目）。
                                 費目が 2 つ以上なら合計の行と、ほかの費目の案間の差を差し引いた境目
    planned_output_weeks.csv     案 × SKU：工場が計画の生産量（floor(cap_soft × 歩留まり)）ちょうど作った最初・最後の週、
                                 その間の週数（報告期間の内・外）、ちょうど作った週・下回った週の数
    market_map.csv               製品 × 需要の地域 → 市場のノード（sc_tree_master.csv の市場の行の region、段 4 A2）
    holding_base.csv             案 × 期間（報告期間 report・助走 warmup）× SKU × 所在の種類（node・transit・*）：
                                 グループの法人が持つ評価済みの在庫の連結原価・週（B_group_hq）、lot・週、未評価の lot・週
                                 （週ごとの合計を vc_v3_weekly.csv の inv_group_hq と照合。合わなければ止める）
    holding_by_week_sku.csv      その明細（案 × 週 × SKU）と、年率 5・10・15% の保有費（週率 ＝ 年率 ÷ 52）
    holding_sensitivity.csv      年率ごとの保有費（報告期間・助走・計）、案の差、費目ごとの境目
                                 f* ＝（ΔP0 − ほかの費目の差 − 保有費の差）÷ ΔW（助走を含む・報告期間だけ）。P0 には入れない
    comparison_summary.md        まとめ

止める条件（CompareError）：ファイルが無い、要求週別の供給の鍵ごとの合計が Flow Check の表 2 と合わない、
SKU 別の試算利益の合計が vc_v3_weekly.csv の profit_r2_hq_wk と週ごとに合わない、
数量配分の結果を渡した案で、金額の実行の出荷（Lot_ID）が数量配分の結果と鍵 × 要求週で合わない、
市場の実出荷の Lot_ID が需要に無い・同じ Lot_ID が 2 回出荷された、
固定費の表に報告通貨（モデルの vc_config.csv の hq_currency、無ければ JPY）以外の週額の行がある
（RequestLetter_Promo_Convert_Slice1 §3.4。控除後・合計・境目のどれを計算する前にも止める。前は通貨によらず
週額をそのまま引き、境目だけ「条件外」と出していた）。
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
K_INBOUND_MOVE = "inbound_move"        # a factory (MOM) that is not the last one ships to the next factory
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
    cu = os.path.join(run_dir, "capacity.csv")       # 段 4 A3: the capacity the engine used (absent in older runs)
    r["capacity_used"] = (pd.read_csv(cu, dtype={"week": str}, keep_default_na=False)
                          if os.path.exists(cu) else None)
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


# ── 需要の地域と市場の名前（段 4 A2）─────────────────────────────────
def market_map(run: dict) -> Dict[Tuple[str, str], str]:
    """(product, demand region) -> market node name, from the leaf_out rows of sc_tree_master.csv (the region
    column ties the demand's region to the market node one to one). Stops if, within a product, a region names two
    markets or a market has no region. Cached in the run."""
    if "_market_map" in run:
        return run["_market_map"]
    t = run["tree"].fillna("")
    lf = t[t["node_type"].astype(str).str.strip() == "leaf_out"]
    out: Dict[Tuple[str, str], str] = {}
    for _, r in lf.iterrows():
        prod, reg, node = str(r["product_name"]).strip(), str(r["region"]).strip(), str(r["node_name"]).strip()
        if not reg:
            raise CompareError(f"{run['model_dir']}: 製品 {prod} の市場 {node} に地域（sc_tree_master.csv の region）がありません。"
                               "直し方：市場の行に需要の地域名を書く")
        if (prod, reg) in out and out[(prod, reg)] != node:
            raise CompareError(f"{run['model_dir']}: 製品 {prod} の地域 {reg} が 2 つの市場（{out[(prod, reg)]}・{node}）に当たります。"
                               "直し方：市場ごとに地域名を分ける")
        out[(prod, reg)] = node
    run["_market_map"] = out
    return out


def market_of(run: dict, sku: str, region: str) -> str:
    m = market_map(run)
    if (sku, region) not in m:
        raise CompareError(f"{run['model_dir']}: 需要の地域 {region}（製品 {sku}）に当たる市場がありません"
                           "（sc_tree_master.csv の市場の行の region）。直し方：市場の行の region を需要の地域名にする")
    return m[(sku, region)]


def key_label(sku: str, region: str, mm: Optional[Dict[Tuple[str, str], str]] = None) -> str:
    """'sku:market（region）' when the market's name differs from the demand region, else 'sku:region'."""
    node = (mm or {}).get((sku, region))
    return f"{sku}:{node}（{region}）" if node and node != region else f"{sku}:{region}"


def market_table(run: dict) -> pd.DataFrame:
    return pd.DataFrame([{"sku_id": s, "region": g, "market": n} for (s, g), n in sorted(market_map(run).items())],
                        columns=["sku_id", "region", "market"])


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
        market_of(run, s, g)                                # every demand region must name one market
        for seq in range(1, int(q) + 1):
            demand_lots[f"{s}:{g}:{w}:{seq:05d}"] = (s, g, w)
    cs = run["ship"][run["ship"]["kind"] == K_CONSUMER]
    shipped: Dict[str, int] = {}
    for lot, node, wk, lots in cs[["lot_id", "node", "ship_week_index", "lots"]].itertuples(index=False):
        if lot not in demand_lots:
            raise CompareError(f"{run['run_dir']}: 市場の実出荷の Lot_ID {lot} が需要（demand_forecast.csv）にありません")
        s, g, w, _ = parse_lot(lot)
        if node != market_of(run, s, g):
            raise CompareError(f"{run['run_dir']}: Lot_ID {lot} が別の市場 {node} で出荷されています"
                               f"（地域 {g} の市場は {market_of(run, s, g)}）")
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
    fl = fl.rename(columns={"product": "sku_id", "leaf": "market"})
    inv = {(s, n): g for (s, g), n in market_map(run).items()}       # market node -> demand region
    fl["region"] = [inv.get((s, n), n) for s, n in zip(fl["sku_id"], fl["market"])]
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
    """Per case x product x factory (MOM) x week: production (lots shipped out of the factory) and the capacity.
    段 4 A3: when the run has run/capacity.csv (the capacity the ENGINE used: run_headless_from_folder
    --capacity-out), every MOM gets its rows and the capacity comes from that file (capacity_source="engine",
    with cap_soft_source / shifts / closed). Without it (runs made before), the old reading: capacity_plan.csv,
    one factory per product (capacity_source="capacity_plan" = not the engine's value)."""
    labels = run["week_labels"]
    sh = run["ship"]
    out_of = sh[sh["kind"].isin([K_HANDOFF, K_INBOUND_MOVE])]
    made = out_of.groupby(["product", "node", "ship_week_index"])["lots"].sum()

    def fl(v, y):
        try:
            return math.floor(float(v) * y + 1e-9)
        except (TypeError, ValueError):
            return None
    rows = []
    cu = run.get("capacity_used")
    if cu is not None:
        for (p, f), g in cu.groupby(["product", "factory"], sort=True):
            byw = {r["week"]: r for _, r in g.iterrows()}
            for i, w in enumerate(labels):
                r = byw.get(w, {})
                y = float(r.get("yield_rate", 1.0) or 1.0) if r is not None and len(r) else 1.0
                rows.append({"case": name, "product": p, "factory": f, "week_index": i, "week": w,
                             "production_lots": int(made.get((p, f, i), 0)),
                             "max_supply": _blank(r.get("cap_hard", "")), "cap_soft": _blank(r.get("cap_soft", "")),
                             "yield_rate": y, "shippable_hard": fl(r.get("cap_hard", ""), y),
                             # a closed week (0 shifts / holiday) has no planned output: not "below the plan"
                             "shippable_soft": None if int(r.get("closed", 0) or 0) else fl(r.get("cap_soft", ""), y),
                             "capacity_source": "engine",
                             "cap_soft_source": _blank(r.get("cap_soft_source", "")),
                             "shifts": _blank(r.get("shifts", "")), "closed": int(r.get("closed", 0) or 0)})
        return pd.DataFrame(rows)
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
    hand = sh[sh["kind"] == K_HANDOFF].groupby(["product", "ship_week_index"])["lots"].sum()
    for p in sorted(momname):
        for i, w in enumerate(labels):
            hard, soft = capd.get((p, w), ("", ""))
            rows.append({"case": name, "product": p, "factory": momname[p], "week_index": i, "week": w,
                         "production_lots": int(hand.get((p, i), 0)),
                         "max_supply": hard, "cap_soft": soft, "yield_rate": yld.get(p, 1.0),
                         "shippable_hard": fl(hard, yld.get(p, 1.0)), "shippable_soft": fl(soft, yld.get(p, 1.0)),
                         "capacity_source": "capacity_plan", "cap_soft_source": "", "shifts": "", "closed": 0})
    return pd.DataFrame(rows)


def _blank(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return v


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
    if "factory" not in x.columns:
        x["factory"] = ""
    return x[["case", "product", "factory", "week_index", "week", "production_lots", "shippable_soft",
              "unused_vs_soft"]]


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


# ── 固定費の逆転点（GPT-MC 業務定義 v0.1 §3・§4、増産の確保費 v0.1）─────────────
FIXED_COST_COLS = ["case", "cost_item", "entity", "paid_start_week", "paid_end_week", "weekly_amount",
                   "currency", "note"]
COUNT_OUTSIDE_COL = "count_outside_report"   # optional: 1 = count the paid weeks over the plan period
DISPLAY_COL = "display_name"                 # optional: the name shown on a screen (copied; not used in sums)
TOTAL_ITEM = "合計"
ZERO_TOL = 0.5      # yen


def _wk_monday(label: str):
    import datetime
    y, w = str(label).strip().split("-W")
    return datetime.date.fromisocalendar(int(y), int(w), 1)


def paid_weeks(paid_start: str, paid_end: str, period_start: str, period_end: str) -> int:
    """ISO weeks in [paid_start, paid_end] ∩ [period_start, period_end] (both ends included).
    The period is the report period, or the plan period for a row with count_outside_report = 1."""
    try:
        a, b = _wk_monday(paid_start), _wk_monday(paid_end)
        ra, rb = _wk_monday(period_start), _wk_monday(period_end)
    except (ValueError, TypeError):
        raise CompareError(f"週のラベルが不正です: {paid_start}〜{paid_end}（期間 {period_start}〜{period_end}）")
    if b < a:
        raise CompareError(f"有償の週の終わり {paid_end} が始まり {paid_start} より前です")
    lo, hi = max(a, ra), min(b, rb)
    return 0 if hi < lo else (hi - lo).days // 7 + 1


def read_fixed_cost_plan(path: str) -> pd.DataFrame:
    df = _csv(path, dtype=str, keep_default_na=False)
    missing = [c for c in FIXED_COST_COLS if c not in df.columns]
    if missing:
        raise CompareError(f"{path}: 列が足りません {missing}")
    if COUNT_OUTSIDE_COL not in df.columns:
        df[COUNT_OUTSIDE_COL] = ""                      # old tables: the report period only
    if DISPLAY_COL not in df.columns:
        df[DISPLAY_COL] = ""
    for i, r in df.iterrows():
        if r["case"] not in ("base", "alt"):
            raise CompareError(f"{path} の {i + 2} 行目: case は base か alt（{r['case']!r}）")
        if r["cost_item"].strip() == TOTAL_ITEM:
            raise CompareError(f"{path} の {i + 2} 行目: cost_item に {TOTAL_ITEM!r} は使えません（合計の行の名前）")
        if r["weekly_amount"].strip() != "":
            try:
                v = float(r["weekly_amount"])
            except ValueError:
                raise CompareError(f"{path} の {i + 2} 行目: weekly_amount={r['weekly_amount']!r} は数値ではありません")
            if v < 0:
                raise CompareError(f"{path} の {i + 2} 行目: weekly_amount は 0 以上")
        if r[COUNT_OUTSIDE_COL].strip() not in ("", "0", "1"):
            raise CompareError(f"{path} の {i + 2} 行目: {COUNT_OUTSIDE_COL}={r[COUNT_OUTSIDE_COL]!r} は 0・1・空欄"
                               "（空欄は 0 ＝ 報告期間だけを数える）")
    if df.duplicated(["case", "cost_item"]).any():
        raise CompareError(f"{path}: 同じ case・cost_item の行が重複しています")
    for item, g in df.groupby("cost_item"):
        flags = {x.strip() or "0" for x in g[COUNT_OUTSIDE_COL]}
        if len(flags) > 1:
            raise CompareError(f"{path}: {item} の {COUNT_OUTSIDE_COL} が base と alt で違います。直し方：同じ値にする")
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


FC_COLS = ["cost_item", "display_name", "entity", "P0_base", "P0_alt", "count_outside_report", "paid_start_base", "paid_end_base",
           "W_base", "paid_start_alt", "paid_end_alt", "W_alt", "weekly_amount_base", "weekly_amount_alt", "cost_base",
           "cost_alt", "P_after_base", "P_after_alt", "delta_P0", "delta_P0_by_product", "delta_W",
           "other_items_cost_diff", "delta_P0_net", "boundary", "f_star_per_week", "boundary_assumption",
           "delta_P_after", "valuation_status", "note"]
UNSET = ""            # an item row keeps the old blank cell for an unset weekly amount (screen: 「未設定」)
NOT_COMPUTED = "未算出"  # the 合計 row only
NOT_APPLICABLE = "対象外"  # the case does not bear the item (no row): W = 0, cost 0


def report_currency(model_dir: str) -> str:
    """hq_currency of the model's vc_config.csv; JPY when the model has none (the tool's earlier fixed value)."""
    p = os.path.join(model_dir, "vc_config.csv")
    if os.path.exists(p):
        df = _csv(p, dtype=str, keep_default_na=False)
        if {"key", "value"} <= set(df.columns):
            v = df.loc[df["key"].str.strip() == "hq_currency", "value"].str.strip()
            if len(v) and v.iloc[0]:
                return v.iloc[0]
    return "JPY"


def check_report_currency(plan: pd.DataFrame, hq_currency: str, source: str = "固定費の表") -> None:
    """RequestLetter_Promo_Convert_Slice1 §3.4: a weekly amount in another currency than the report currency
    stops before any after-cost value, total or boundary is computed (the weekly amount is used as yen in all
    three). The fix is to write the amount converted to the report currency."""
    for i, r in plan.reset_index(drop=True).iterrows():
        ccy = str(r.get("currency", "")).strip()
        if ccy != hq_currency:
            raise CompareError(
                f"{source} の {i + 2} 行目（case={r.get('case', '')}, cost_item={r.get('cost_item', '')}）：通貨 {ccy!r} は"
                f"報告通貨 {hq_currency} ではありません。週額は控除後・合計・境目の計算にそのまま使うので、"
                f"報告通貨以外は計算しません。直し方：週額を報告通貨（{hq_currency}）に換算して書く（換算のレートと元の額は note に）")


def fixed_cost_table(plan: Optional[pd.DataFrame], p0: Dict[str, float], status: Dict[str, str],
                     report_start: str, report_end: str, hq_currency: str = "JPY",
                     dp0_by_product: str = "", plan_start: Optional[str] = None,
                     plan_end: Optional[str] = None) -> pd.DataFrame:
    """One row per cost_item (and a 合計 row when there are two or more):
    per-case P0, paid weeks, W, weekly amount, cost, P0 after cost, ΔP0, ΔW and the boundary.

    W counts the paid weeks inside the report period; a row with count_outside_report = 1 counts them inside
    the plan period (plan_start..plan_end), warm-up weeks included. A case without a row for an item does not
    bear that cost (W = 0, cost 0). A row with a blank weekly amount is 未設定.

    The boundary of an item treats only that item's weekly amount as unknown:
        f* = (ΔP0 − Σ other items' (cost_alt − cost_base)) ÷ ΔW_item
    An other item with an unset weekly amount enters that sum as 0, and boundary_assumption says so."""
    dp0 = p0["alt"] - p0["base"]
    unval = [f"{c}: {status[c]}" for c in ("base", "alt") if status[c] != "評価済み"]
    if plan is None or plan.empty:
        lab, _ = boundary_label(dp0, None, "固定費の表なし（有償週未設定）")
        return pd.DataFrame([{"cost_item": "", "entity": "", "P0_base": p0["base"], "P0_alt": p0["alt"],
                              "delta_P0": dp0, "delta_P0_by_product": dp0_by_product, "delta_W": "",
                              "boundary": lab, "f_star_per_week": "",
                              "valuation_status": "; ".join(unval) or "評価済み"}], columns=FC_COLS)
    check_report_currency(plan, hq_currency)
    if COUNT_OUTSIDE_COL not in plan.columns:
        plan = plan.assign(**{COUNT_OUTSIDE_COL: ""})
    if DISPLAY_COL not in plan.columns:
        plan = plan.assign(**{DISPLAY_COL: ""})
    items = sorted(set(plan["cost_item"]))
    info = {}
    for item in items:
        names = [x.strip() for x in plan.loc[plan["cost_item"] == item, DISPLAY_COL] if x.strip()]
        r = {"cost_item": item, "display_name": names[0] if names else "",
             "entity": ",".join(sorted(set(plan.loc[plan["cost_item"] == item, "entity"])))}
        outside = (plan.loc[plan["cost_item"] == item, COUNT_OUTSIDE_COL].str.strip() == "1").any()
        if outside and not (plan_start and plan_end):
            raise CompareError(f"{item}: {COUNT_OUTSIDE_COL}=1 には計画期間が要ります")
        ps, pe = (plan_start, plan_end) if outside else (report_start, report_end)
        r["count_outside_report"] = 1 if outside else 0
        amounts, ccys, has = {}, set(), {}
        for c in ("base", "alt"):
            sub = plan[(plan["cost_item"] == item) & (plan["case"] == c)]
            r[f"P0_{c}"] = p0[c]
            if sub.empty:                           # this case does not bear the item
                r[f"paid_start_{c}"], r[f"paid_end_{c}"], r[f"W_{c}"] = "", "", 0
                amounts[c], has[c] = 0.0, False
                continue
            x = sub.iloc[0]
            has[c] = True
            r[f"paid_start_{c}"], r[f"paid_end_{c}"] = x["paid_start_week"], x["paid_end_week"]
            r[f"W_{c}"] = paid_weeks(x["paid_start_week"], x["paid_end_week"], ps, pe)
            amounts[c] = float(x["weekly_amount"]) if x["weekly_amount"].strip() != "" else None
            ccys.add(x["currency"].strip())
        reason = ""
        if unval:
            reason = "連結利益未評価"
        elif has["base"] and has["alt"] and all(amounts[c] is not None for c in ("base", "alt")) \
                and amounts["base"] != amounts["alt"]:
            reason = "共通の円建て週額の条件外（週額が案で違う）"
        known = all(amounts[c] is not None for c in ("base", "alt"))
        for c in ("base", "alt"):
            a = amounts[c]
            r[f"weekly_amount_{c}"] = (NOT_APPLICABLE if not has[c] else (UNSET if a is None else a))
            r[f"cost_{c}"] = UNSET if a is None else a * r[f"W_{c}"]
        info[item] = (r, reason, known, (r["cost_alt"] - r["cost_base"]) if known else None)
    rows = []
    for item in items:
        r, reason, known, _cd = info[item]
        dw = r["W_alt"] - r["W_base"]
        others = [o for o in items if o != item]
        def _same_weeks(o):     # borne by both cases for the same number of weeks: the difference is 0 under
            ro = info[o][0]     # the common weekly amount of the definition (§4), not an assumption
            return ro["W_base"] == ro["W_alt"] and NOT_APPLICABLE not in (ro["weekly_amount_base"],
                                                                          ro["weekly_amount_alt"])
        unset_others = [o for o in others if info[o][3] is None and not _same_weeks(o)]
        same_weeks = [o for o in others if info[o][3] is None and _same_weeks(o)]
        other_diff = sum(info[o][3] for o in others if info[o][3] is not None)
        dp_net = dp0 - other_diff
        lab, fstar = boundary_label(dp_net, dw, reason)
        assume = ""
        if others:
            parts = []
            if other_diff:
                parts.append(f"ほかの費用の案間の差 {other_diff:,.0f} 円を差し引いた")
            if unset_others:
                parts.append(f"ほかの未設定の費用（{', '.join(unset_others)}）の案間の差を 0 と置いた場合")
            if same_weeks:
                parts.append(f"{', '.join(same_weeks)} は両案で同じ週数なので案間の差は 0")
            assume = "；".join(parts) or "ほかの費用の案間の差は 0"
        for c in ("base", "alt"):
            r[f"P_after_{c}"] = "" if r[f"cost_{c}"] == UNSET else p0[c] - r[f"cost_{c}"]
        r.update({"delta_P0": dp0, "delta_P0_by_product": dp0_by_product, "delta_W": dw,
                  "other_items_cost_diff": other_diff if others else "", "delta_P0_net": dp_net if others else "",
                  "boundary": lab, "f_star_per_week": "" if fstar is None else fstar, "boundary_assumption": assume,
                  "delta_P_after": (r["P_after_alt"] - r["P_after_base"]) if known else "",
                  "valuation_status": "; ".join(unval) or "評価済み",
                  "note": "" if known else "週額が未設定：境目だけ"})
        rows.append(r)
    if len(items) >= 2:
        all_known = all(info[i][2] for i in items)
        t = {"cost_item": TOTAL_ITEM, "entity": ",".join(sorted(set(plan["entity"]))),
             "P0_base": p0["base"], "P0_alt": p0["alt"], "delta_P0": dp0, "delta_P0_by_product": dp0_by_product,
             "valuation_status": "; ".join(unval) or "評価済み"}
        for c in ("base", "alt"):
            t[f"cost_{c}"] = sum(r[f"cost_{c}"] for r in rows) if all_known else NOT_COMPUTED
            t[f"P_after_{c}"] = (p0[c] - t[f"cost_{c}"]) if all_known else NOT_COMPUTED
        t["delta_P_after"] = (t["P_after_alt"] - t["P_after_base"]) if all_known else NOT_COMPUTED
        t["boundary"] = "合計（費目ごとの境目は上の行）"
        for col in FC_COLS:                     # blank, not NaN (keeps the item rows' integer columns as they are)
            t.setdefault(col, "")
        t["note"] = "" if all_known else "週額が未設定の費用がある：費用・控除後の利益は未算出、採算の順位は保留"
        rows.append(t)
    return pd.DataFrame(rows, columns=FC_COLS)


def planned_output_weeks(fw: pd.DataFrame, report_start: str, report_end: str,
                         mom_names: Optional[Dict[str, Dict[str, str]]] = None) -> pd.DataFrame:
    """Per case x product: the weeks the factory made exactly its planned shippable output (floor(cap_soft x yield)).
    Used to check the paid weeks written in the fixed cost table (the tool does not decide them)."""
    rows = []
    ra, rb = _wk_monday(report_start), _wk_monday(report_end)
    varies = False

    def measure(g, soft, inrep):
        at = g[soft.notna() & (g["production_lots"] == soft)]
        below = g[soft.notna() & (g["production_lots"] < soft)]
        r = {"weeks_at_cap": len(at), "weeks_at_cap_in_report": int(inrep[at.index].sum()),
             "weeks_at_cap_outside_report": int((~inrep[at.index]).sum()),
             "weeks_below_cap": len(below), "weeks_below_cap_in_report": int(inrep[below.index].sum())}
        if len(at):
            span = g[(g["week_index"] >= at["week_index"].iloc[0]) & (g["week_index"] <= at["week_index"].iloc[-1])]
            ss = soft[span.index]
            r.update({"first_week_at_cap": at["week"].iloc[0], "last_week_at_cap": at["week"].iloc[-1],
                      "span_weeks": len(span), "span_weeks_in_report": int(inrep[span.index].sum()),
                      "span_weeks_outside_report": int((~inrep[span.index]).sum()),
                      "weeks_below_cap_inside_span": int((span["production_lots"] < ss).sum())})
        return r

    if "factory" not in fw.columns:
        fw = fw.assign(factory=[(mom_names or {}).get(c, {}).get(p, "") for c, p in zip(fw["case"], fw["product"])])
    for (case, prod, fac), g in fw.groupby(["case", "product", "factory"], sort=True):
        g = g.sort_values("week_index")
        soft = pd.to_numeric(g["shippable_soft"], errors="coerce")
        inrep = g["week"].map(lambda w: ra <= _wk_monday(w) <= rb)
        vals = sorted(soft.dropna().unique())
        head = {"case": case, "product": prod, "factory": fac}
        rows.append({**head, "row": "全体", "shippable_soft_values": ",".join(str(int(v)) for v in vals),
                     **measure(g, soft, inrep)})
        if len(vals) > 1:
            # 段 4: the plan varies by week -> one more row per shippable value, measured on the weeks planned at
            # that value only (first / last / number of weeks planned at it; at-cap and below-cap weeks)
            varies = True
            for v in vals:
                sub = g[soft == v]
                rows.append({**head, "row": "値ごと", "shippable_soft_values": str(int(v)),
                             "planned_first_week": sub["week"].iloc[0], "planned_last_week": sub["week"].iloc[-1],
                             "planned_weeks": len(sub), "planned_weeks_in_report": int(inrep[sub.index].sum()),
                             "planned_weeks_outside_report": int((~inrep[sub.index]).sum()),
                             **measure(sub, soft[sub.index], inrep[sub.index])})
    cols = ["case", "product", "factory", "shippable_soft_values", "first_week_at_cap", "last_week_at_cap",
            "span_weeks", "span_weeks_in_report", "span_weeks_outside_report", "weeks_at_cap",
            "weeks_at_cap_in_report", "weeks_at_cap_outside_report", "weeks_below_cap", "weeks_below_cap_in_report",
            "weeks_below_cap_inside_span"]
    if varies:   # a uniform plan keeps the table as it was (one row per case x product, same columns)
        cols += ["row", "planned_first_week", "planned_last_week", "planned_weeks", "planned_weeks_in_report",
                 "planned_weeks_outside_report"]
    t = pd.DataFrame(rows).reindex(columns=cols)
    # counts stay integers when some rows are blank (a factory without a planned output, the whole-case rows)
    for c in ("span_weeks", "span_weeks_in_report", "span_weeks_outside_report", "weeks_below_cap_inside_span",
              "planned_weeks", "planned_weeks_in_report", "planned_weeks_outside_report"):
        if c in t.columns:
            t[c] = t[c].astype("Int64")
    return t


# ── 在庫の保有費（感度） ─────────────────────────────────────────────────
# RequestLetter_Cockpit_HoldingCost_Sensitivity（2026-11-17）、業務定義 GPT-MC v0.1 ＋ 大杉さんの判断：
# 資本拘束分だけ。週末の連結原価（group_hq）の在庫。グループの法人が持つ評価済みの在庫（移送中を含む、
# グループの外は除く）。報告期間と助走を別欄に。年率は感度（採用する率は未設定）。週率 ＝ 年率 ÷ 52。
# P0 には入れない（Value Chain の holding_rate_weekly は空欄のまま）。
HOLDING_RATES = (0.05, 0.10, 0.15)
WEEKS_PER_YEAR = 52
PERIOD_REPORT, PERIOD_WARMUP, PERIOD_AFTER = "report", "warmup", "after"
HB_COLS = ["case", "period", "product", "location_kind", "weeks", "B_group_hq", "lots_weeks", "unvalued_lots_weeks"]


def group_entities(run: dict) -> set:
    """The group's legal entities (vc_entity.csv: kind = group, or consolidated = 1 when there is no kind)."""
    ent = run["entity"]
    if "kind" in ent.columns:
        s = set(ent.loc[ent["kind"].astype(str).str.strip() == "group", "entity_id"])
    else:
        s = set(ent.loc[ent["consolidated"].astype(str).str.strip() == "1", "entity_id"])
    if not s:
        raise CompareError("vc_entity.csv にグループの法人（kind=group）がありません")
    return s


def week_period(label: str, report_start: str, report_end: str) -> str:
    m = _wk_monday(label)
    if m < _wk_monday(report_start):
        return PERIOD_WARMUP
    return PERIOD_REPORT if m <= _wk_monday(report_end) else PERIOD_AFTER


def holding_inventory(run: dict, name: str, report_start: str, report_end: str) -> pd.DataFrame:
    """Week x SKU x location kind: the inventory the holding cost is charged on (group-owned, not external).
    B_group_hq and lots count the valued rows only; unvalued_lots counts the rest (no amount).
    Stops (CompareError) when the week totals of B_group_hq differ from vc_v3_weekly.csv inv_group_hq."""
    inv = run["inv"]
    grp = group_entities(run)
    own = inv[inv["owner"].isin(grp) & (inv["external"].astype(int) == 0)].copy()
    val = own["valued"].astype(int) == 1
    own["B_group_hq"] = own["group_hq"].where(val, 0.0).astype(float)
    own["lots_v"] = own["lots"].where(val, 0)
    own["lots_u"] = own["lots"].where(~val, 0)
    g = own.groupby(["week_index", "week", "product", "location_kind"]).agg(
        B_group_hq=("B_group_hq", "sum"), lots=("lots_v", "sum"), unvalued_lots=("lots_u", "sum")).reset_index()
    g.insert(0, "case", name)
    g.insert(3, "period", g["week"].map(lambda w: week_period(w, report_start, report_end)))
    v3 = run["v3"][run["v3"]["group_key"] == "GROUP"].set_index("week_index")
    wk = g.groupby("week_index")["B_group_hq"].sum().reindex(v3.index, fill_value=0.0)
    bad = (wk - v3["inv_group_hq"].astype(float)).abs()
    if (bad > ZERO_TOL).any():
        w = bad.idxmax()
        raise CompareError(f"{name}: 在庫の連結原価が vc_v3_weekly.csv の inv_group_hq と合いません"
                           f"（週 {v3.loc[w, 'week']}: 在庫の合計 {wk.loc[w]:,.2f}、inv_group_hq "
                           f"{float(v3.loc[w, 'inv_group_hq']):,.2f}）")
    return g


def holding_base(hi: pd.DataFrame, weeks_by_period: Optional[Dict[str, int]] = None) -> pd.DataFrame:
    """A1: case x period x SKU x location kind, with '*' totals (all SKUs, all location kinds).
    weeks = the plan weeks of the period (weeks_by_period), else the weeks that have a row."""
    rows = []
    for (case, period), gp in hi.groupby(["case", "period"], sort=False):
        weeks = (weeks_by_period or {}).get(period, gp["week_index"].nunique())
        for prod in sorted(gp["product"].unique()) + ["*"]:
            gs = gp if prod == "*" else gp[gp["product"] == prod]
            for lk in sorted(gs["location_kind"].unique()) + ["*"]:
                x = gs if lk == "*" else gs[gs["location_kind"] == lk]
                rows.append({"case": case, "period": period, "product": prod, "location_kind": lk, "weeks": weeks,
                             "B_group_hq": float(x["B_group_hq"].sum()), "lots_weeks": int(x["lots"].sum()),
                             "unvalued_lots_weeks": int(x["unvalued_lots"].sum())})
    return pd.DataFrame(rows, columns=HB_COLS)


def holding_by_week(hi: pd.DataFrame, rates=HOLDING_RATES) -> pd.DataFrame:
    """The detail: case x week x SKU (all location kinds): B_group_hq and the holding cost at each rate."""
    g = hi.groupby(["case", "week_index", "week", "period", "product"]).agg(
        B_group_hq=("B_group_hq", "sum"), lots=("lots", "sum"), unvalued_lots=("unvalued_lots", "sum")).reset_index()
    for r in rates:
        g[f"holding_{rate_tag(r)}"] = g["B_group_hq"] * r / WEEKS_PER_YEAR
    return g


def rate_tag(r: float) -> str:
    return f"{round(r * 100):d}pct"


HS_COLS = ["annual_rate", "weekly_rate", "cost_item", "display_name",
           "H_base_report", "H_base_warmup", "H_base_total", "H_alt_report", "H_alt_warmup", "H_alt_total",
           "dH_report", "dH_warmup", "dH_total", "delta_P0", "delta_P0_net", "delta_W",
           "boundary_incl_warmup", "f_star_incl_warmup", "boundary_report_only", "f_star_report_only",
           "boundary_assumption", "valuation_status", "note"]


def holding_sensitivity(hb: pd.DataFrame, fc: pd.DataFrame, base_name: str, alt_name: str,
                        rates=HOLDING_RATES) -> pd.DataFrame:
    """A2: per annual rate, the holding cost of each case (report / warm-up / total), the difference (alt − base),
    and for each fixed cost item the boundary with the holding cost counted as one more cost of the other items:
        f* = (ΔP0 − Σ other items' cost difference − ΔH) ÷ ΔW_item
    once with ΔH over warm-up + report, once over the report period only. The weekly amount of the item stays
    unknown, so the after-cost profit is not computed here."""
    tot = hb[(hb["product"] == "*") & (hb["location_kind"] == "*")]

    def B(case, period):
        x = tot[(tot["case"] == case) & (tot["period"] == period)]
        return float(x["B_group_hq"].sum())
    unval = {c: int(tot[tot["case"] == c]["unvalued_lots_weeks"].sum()) for c in (base_name, alt_name)}
    vstat = "; ".join(f"{c}: 一部未評価（未評価の在庫 lot・週 {n:,}）" for c, n in unval.items() if n) or "評価済み"
    items = fc[~fc["cost_item"].isin(["", TOTAL_ITEM])] if fc is not None and len(fc) else pd.DataFrame()
    rows = []
    for r in rates:
        wr = r / WEEKS_PER_YEAR
        h = {}
        for side, case in (("base", base_name), ("alt", alt_name)):
            h[f"H_{side}_report"] = wr * B(case, PERIOD_REPORT)
            h[f"H_{side}_warmup"] = wr * B(case, PERIOD_WARMUP)
            h[f"H_{side}_total"] = h[f"H_{side}_report"] + h[f"H_{side}_warmup"]
        for p in ("report", "warmup", "total"):
            h[f"dH_{p}"] = h[f"H_alt_{p}"] - h[f"H_base_{p}"]
        head = {"annual_rate": r, "weekly_rate": wr, **h, "valuation_status": vstat,
                "note": f"保有費 ＝ 年率 {r * 100:g}% の仮置き（採用する率は未設定）。P0 には入っていない"}
        if items.empty:
            dp0 = float(fc["delta_P0"].iloc[0]) if fc is not None and len(fc) else ""
            rows.append({**head, "cost_item": "", "display_name": "", "delta_P0": dp0, "delta_P0_net": "",
                         "delta_W": "", "boundary_incl_warmup": "未算出（固定費の表なし（有償週未設定））",
                         "f_star_incl_warmup": "", "boundary_report_only": "未算出（固定費の表なし（有償週未設定））",
                         "f_star_report_only": "", "boundary_assumption": ""})
            continue
        for _, it in items.iterrows():
            dp0 = float(it["delta_P0"])
            net = it.get("delta_P0_net", "")
            dp_net = float(net) if str(net) not in ("", "nan") else dp0
            dw = it["delta_W"]
            row = {**head, "cost_item": it["cost_item"], "display_name": it.get("display_name", ""),
                   "delta_P0": dp0, "delta_P0_net": dp_net, "delta_W": dw,
                   "boundary_assumption": it.get("boundary_assumption", "")}
            for scope, dh in (("incl_warmup", h["dH_total"]), ("report_only", h["dH_report"])):
                if str(it["boundary"]).startswith("未算出"):
                    lab, f = it["boundary"], None
                else:
                    lab, f = boundary_label(dp_net - dh, None if str(dw) in ("", "nan") else int(dw))
                row[f"boundary_{scope}"] = lab
                row[f"f_star_{scope}"] = "" if f is None else f
            rows.append(row)
    return pd.DataFrame(rows, columns=HS_COLS)


# ── 全体 ─────────────────────────────────────────────────────────────
def compare(base_run: str, alt_run: str, base_model: str, alt_model: str, out: str,
            fixed_cost_plan: Optional[str] = None, base_name: str = "base", alt_name: str = "alt",
            base_udp: Optional[str] = None, alt_udp: Optional[str] = None) -> dict:
    os.makedirs(out, exist_ok=True)
    # §3.4 (Promo_Convert_Slice1): a weekly amount not in the report currency stops before anything is computed
    plan = read_fixed_cost_plan(fixed_cost_plan) if fixed_cost_plan else None
    if plan is not None:
        check_report_currency(plan, report_currency(base_model), fixed_cost_plan)
    base, alt = load_run(base_run, base_model), load_run(alt_run, alt_model)
    if base["week_labels"] != alt["week_labels"]:
        raise CompareError("2 案の計画の週が違います（計画期間をそろえてください）")
    labels = base["week_labels"]
    res = {}
    mm = {**market_map(base), **market_map(alt)}
    pd.concat([market_table(base), market_table(alt)]).drop_duplicates().to_csv(
        os.path.join(out, "market_map.csv"), index=False)
    res["market_map"] = mm

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
    fc = fixed_cost_table(plan, {"base": pb, "alt": pa}, {"base": stb, "alt": sta}, rs, re_, dp0_by_product=by_prod,
                          plan_start=labels[0], plan_end=labels[-1], hq_currency=report_currency(base_model))
    fc.to_csv(os.path.join(out, "fixed_cost_breakeven.csv"), index=False)
    moms = {}
    for nm, run in ((base_name, base), (alt_name, alt)):
        t = run["tree"]
        moms[nm] = {r["product_name"]: r["node_name"] for _, r in t[t["node_type"] == "mom"].iterrows()}
    pw = planned_output_weeks(fw, rs, re_, moms)
    pw.to_csv(os.path.join(out, "planned_output_weeks.csv"), index=False)
    hi = pd.concat([holding_inventory(base, base_name, rs, re_), holding_inventory(alt, alt_name, rs, re_)])
    wbp = pd.Series([week_period(w, rs, re_) for w in labels]).value_counts().to_dict()
    hb = holding_base(hi, wbp)
    hb.to_csv(os.path.join(out, "holding_base.csv"), index=False)
    holding_by_week(hi).to_csv(os.path.join(out, "holding_by_week_sku.csv"), index=False)
    hs = holding_sensitivity(hb, fc, base_name, alt_name)
    hs.to_csv(os.path.join(out, "holding_sensitivity.csv"), index=False)

    res.update({"holding_base": hb, "holding_sensitivity": hs})
    res.update({"labels": labels, "demand_diff": dd, "entry_plan_diff": epd, "supply": ssbs, "supply_check": chk,
                "money": msbs, "totals": tsbs, "inventory_sku": isku, "factory": fw, "age": ag,
                "diff_weeks": dw, "picks": picks, "boundary": bd, "factory_idle": fi, "fixed_cost": fc, "alloc": alloc,
                "planned_output_weeks": pw,
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
    mm = res.get("market_map") or {}

    def lab(s, g):
        return key_label(s, g, mm)
    L = [f"# 2 案の比較（{bn} → {an}）", "",
         f"- base（{bn}）：実行 `{base_run}`、モデル `{base_model}`",
         f"- alt（{an}）：実行 `{alt_run}`、モデル `{alt_model}`",
         f"- 計画の週：{res['labels'][0]}〜{res['labels'][-1]}（{len(res['labels'])} 週）", "",
         "## 入力の表の違い", ""]
    epd = res["entry_plan_diff"]
    L += ["（違いなし）"] if epd.empty else [f"- {lab(r.sku_id, r.region)} `{r.column}`：{r.base} → {r.alt}"
                                            for r in epd.itertuples()]
    dd = res["demand_diff"]
    g = dd.groupby(["sku_id", "region"])[["demand_base", "demand_alt", "diff"]].sum().reset_index()
    L += ["", "## 需要（lot、全計画期間）", "", "| 鍵 | base | alt | 差 |", "|---|---:|---:|---:|"]
    L += [f"| {lab(r.sku_id, r.region)} | {r.demand_base} | {r.demand_alt} | {r.diff:+d} |" for r in g.itertuples()]
    s = res["supply"]
    gs = s.groupby(["sku_id", "region"])[[f"{c}_{x}" for c in SUPPLY_COLS for x in ("base", "alt")]].sum().reset_index()
    L += ["", "## 供給（Lot_ID で要求週へ戻した合計。Flow Check の表 2 と一致を確認済み）", "",
          "| 鍵 | 需要 base/alt | 当週 base/alt | 遅配 base/alt | 早出し base/alt | 期末の未充足 base/alt |",
          "|---|---|---|---|---|---|"]
    for r in gs.itertuples():
        L.append(f"| {lab(r.sku_id, r.region)} | {r.demand_base:.0f}/{r.demand_alt:.0f} | {r.on_time_base:.0f}/{r.on_time_alt:.0f} "
                 f"| {r.late_base:.0f}/{r.late_alt:.0f} | {r.early_base:.0f}/{r.early_alt:.0f} "
                 f"| {r.backlog_end_base:.0f}/{r.backlog_end_alt:.0f} |")
    al = res.get("alloc")
    if al is not None:
        ga = al.groupby(["sku_id", "region"])[[f"{c}_{x}" for c in UDP_COLS for x in ("base", "alt")]].sum().reset_index()
        L += ["", "## 数量配分（① 元の需要 ＝ ② 供給の対象 ＋ ③ 未配分、② ＝ 当週 ＋ 早出し ＋ 遅配 ＋ ⑤ 配分後の未充足）", "",
              "| 鍵 | ① base/alt | ② base/alt | ③ base/alt | 当週 base/alt | 遅配 base/alt | ⑤ base/alt |",
              "|---|---|---|---|---|---|---|"]
        for r in ga.itertuples():
            L.append(f"| {lab(r.sku_id, r.region)} | {r.q1_original_base:.0f}/{r.q1_original_alt:.0f} "
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
    multi = set(fi.groupby("product")["factory"].nunique().loc[lambda x: x > 1].index) if len(fi) else set()
    for (c, p, f), gg in fi.groupby(["case", "product", "factory"]):
        L.append(f"- {c} {p}{'・' + f if p in multi else ''}：{', '.join(gg['week'])}"
                 f"（未使用 計 {gg['unused_vs_soft'].sum():.0f} lot）")
    L += ["", "## 固定費の逆転点（GPT-MC 業務定義 v0.1 §4）", ""]
    for fc in res["fixed_cost"].itertuples():
        fs = str(fc.f_star_per_week)
        L.append(f"- {fc.cost_item or '（固定費の表なし）'}：P0 base {_fmt(fc.P0_base)} / alt {_fmt(fc.P0_alt)}、"
                 f"ΔP0 {_fmt(fc.delta_P0)}（{fc.delta_P0_by_product}）、W base {getattr(fc, 'W_base', '')} / alt "
                 f"{getattr(fc, 'W_alt', '')}、ΔW {fc.delta_W} → {fc.boundary}"
                 + (f"：**{_fmt(fc.f_star_per_week)} 円／週**" if fs not in ("", "nan") else "")
                 + (f"（{fc.boundary_assumption}）" if str(fc.boundary_assumption) not in ("", "nan") else "")
                 + f"（{fc.valuation_status}）")
    hs = res.get("holding_sensitivity")
    if hs is not None and len(hs):
        L += ["", "## 在庫の保有費（感度。年率は仮置き、採用する率は未設定。P0 には入っていない）", "",
              "対象：グループの法人が持つ評価済みの在庫（移送中を含む、グループの外は除く）、週末の連結原価（group_hq）。"
              "保有費 ＝ 年率 ÷ 52 × 連結原価の在庫・週。", "",
              "| 年率 | 保有費 base 報告/助走 | alt 報告/助走 | 差 報告/助走/計 | 費目 | 境目（助走を含む） | 境目（報告期間だけ） |",
              "|---|---|---|---|---|---|---|"]
        for r in hs.itertuples():
            def fs(v, lab):
                return f"{_fmt(v)} 円／週（{lab}）" if str(v) not in ("", "nan") else str(lab)
            L.append(f"| {r.annual_rate * 100:g}% | {_fmt(r.H_base_report)} / {_fmt(r.H_base_warmup)} "
                     f"| {_fmt(r.H_alt_report)} / {_fmt(r.H_alt_warmup)} "
                     f"| {_fmt(r.dH_report)} / {_fmt(r.dH_warmup)} / {_fmt(r.dH_total)} | {r.cost_item or '—'} "
                     f"| {fs(r.f_star_incl_warmup, r.boundary_incl_warmup)} | {fs(r.f_star_report_only, r.boundary_report_only)} |")
        L.append(f"\n（{hs['valuation_status'].iloc[0]}）")
    pw = res.get("planned_output_weeks")
    if pw is not None and len(pw):
        L += ["", "## 計画の生産量ちょうど作った週（有償の週の確かめ用。道具は有償の週を決めない）", ""]
        for r in pw.itertuples():
            if getattr(r, "row", "全体") == "値ごと":
                L.append(f"  - うち上限 {r.shippable_soft_values} の週（{r.planned_first_week}〜{r.planned_last_week}・"
                         f"{r.planned_weeks} 週、報告期間 {r.planned_weeks_in_report}・外 {r.planned_weeks_outside_report}）："
                         f"ちょうど作った週 {r.weeks_at_cap}（報告期間 {r.weeks_at_cap_in_report}）、"
                         f"下回った週 {r.weeks_below_cap}（報告期間 {r.weeks_below_cap_in_report}）")
                continue
            L.append(f"- {r.case} {r.product}（{r.factory}、上限 {r.shippable_soft_values}）：最初 {r.first_week_at_cap}・"
                     f"最後 {r.last_week_at_cap}・その間 {r.span_weeks} 週（報告期間 {r.span_weeks_in_report}・"
                     f"外 {r.span_weeks_outside_report}）、ちょうど作った週 {r.weeks_at_cap}（報告期間 {r.weeks_at_cap_in_report}）、"
                     f"下回った週 {r.weeks_below_cap}")
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
