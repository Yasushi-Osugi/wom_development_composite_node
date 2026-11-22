# -*- coding: utf-8 -*-
"""
wom/strategy/compare.py — 変換した案の要約（P0・追加費用・控除後の比較値・①〜⑤・波及・押し戻し）
=================================================================================================
RequestLetter_Promo_Convert_Slice1 §4・§5・§7。計算は比較の道具の関数を使い、二重に作らない：

- P0・追加費用・控除後 ………… wom.cockpit.case_runner.compare_cases（tools.compare_scenarios の固定費の表）
- ①〜⑤ ……………………………… tools.period_fulfillment（①＝②＋③、②＝④＋⑤ を要求週で検査して止める）
- 在庫・年齢 …………………… tools.compare_scenarios.load_run（vc_inventory_weekly・shelf_life_summary）
- 押し戻し ……………………… wom.strategy.overflow（エンジンの overflow_by_node）

比較値の名前（業務定義 v0.1 §4）：
    P0       追加販促費の控除前の現行比較値（報告期間、vc_v3_weekly の profit_r2_hq_wk の合計）
    B_add    案の外の追加費用（報告通貨。案の inputs/fixed_cost.csv。P0 には入っていない）
    A        控除後の比較値 ＝ P0 − B_add（グループの営業利益や Net Cash ではない）
    ΔA       A − A（基準の案）
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional

import pandas as pd

from wom.cockpit import cases as C
from wom.strategy import StrategyError

SNAP_KEYS = ("period", "products", "forward", "backward", "ppc", "psi")


def _ensure_path():
    if C.REPO not in sys.path:
        sys.path.insert(0, C.REPO)


def _cost_cell(rows: List[dict], side: str) -> float:
    """B_add of one side from the fixed-cost table rows of compare_cases (the 合計 row if there is one)."""
    items = [r for r in rows if r.get("cost_item")]
    if not items:
        return 0.0
    tot = [r for r in items if r["cost_item"] == "合計"]
    r = tot[0] if tot else items[0]
    v = r.get(f"cost_{side}")
    if v in ("", None, "未算出"):
        raise StrategyError(f"費用の前提の {r['cost_item']} の {side} が未設定・未算出です（控除後が出せない）")
    return float(v)


def _demand_log_totals(ws: str, cid: str, sku: str, market: str, rs: str, re_: str) -> dict:
    p = os.path.join(C.case_dir(ws, cid), "inputs", "strategy_change_log.csv")
    if not os.path.exists(p):
        return {"plan_id": "", "d": 0, "residual": "", "log": False}
    log = pd.read_csv(p, dtype=str, keep_default_na=False)
    key = f"{sku}|{market}"
    dm = log[(log["key"] == key) & (log["column"] == "quantity") & (log["rule"] != "residual")]
    dm = dm[(dm["week"] >= rs) & (dm["week"] <= re_)]
    d = int(sum(int(a) - int(b) for a, b in zip(dm["after"], dm["before"])))
    res = log[(log["key"] == key) & (log["rule"] == "residual")]["after"].tolist()
    return {"plan_id": log["plan_id"].iloc[0] if len(log) else "", "d": d, "residual": ";".join(res), "log": True}


def _snapshot_same(a: Optional[dict], b: Optional[dict]) -> str:
    if not a or not b:
        return "比べられない（snapshot.json が無い）"
    diff = [k for k in SNAP_KEYS if a.get(k) != b.get(k)]
    return "同じ" if not diff else f"違う（{', '.join(diff)}）"


def compare_plans(ws: str, base: str, cases: List[str], sku: str, market: str, out: Optional[str] = None,
                  overflow: bool = True) -> dict:
    _ensure_path()
    from wom.cockpit import case_runner as R
    from tools import compare_scenarios as CS
    from tools import period_fulfillment as PF
    from wom.strategy import overflow as OV
    wsj = C.open_workspace(ws)
    rs, re_ = wsj["report_period"]["start"], wsj["report_period"]["end"]
    out = out or os.path.join(ws, "strategy_compare", "_".join([base] + cases))
    os.makedirs(out, exist_ok=True)
    recs = {c: R.compare_cases(ws, base, c) for c in cases}

    # base demand B of the target key over the report period (the frozen base the converter reads)
    bdem = pd.read_csv(os.path.join(wsj["source_model"], C.DEMAND), dtype={"quantity": str})
    bk = bdem[(bdem["sku_id"] == sku) & (bdem["region"] == market) & (bdem["week"] >= rs) & (bdem["week"] <= re_)]
    B = int(sum(int(float(q)) for q in bk["quantity"]))

    allc = [base] + cases
    cts = {c: PF.case_tables(ws, c) for c in allc}
    keys = pd.DataFrame([r for c in allc for r in PF.key_rows(cts[c])])
    keys = keys[keys["region"] != "*"]
    runs = {}
    for c in allc:
        cd = C.case_dir(ws, c)
        rr = C.read_case(ws, c)["run"]
        runs[c] = CS.load_run(os.path.join(cd, "run"), os.path.join(cd, rr["money_model"]))

    ov_rows = []
    ov_total = {}
    if overflow:
        for c in allc:
            cd = C.case_dir(ws, c)
            rr = C.read_case(ws, c)["run"]
            mdir = os.path.join(cd, rr["money_model"])
            cache = os.path.join(out, f"overflow_{c}.json")
            inh = json.dumps(rr["input_hashes"], sort_keys=True)
            rec = None
            if os.path.exists(cache):
                j = json.load(open(cache, encoding="utf-8"))
                if j.get("input_hashes") == inh:
                    rec = j["record"]
            if rec is None:
                rec = OV.overflow_by_factory(mdir, R.recommended_plugins(mdir))
                json.dump({"input_hashes": inh, "record": rec}, open(cache, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
            ov_rows += OV.rows(rec, c)
            ov_total[c] = rec["pushed_total"]
    pd.DataFrame(ov_rows, columns=["case", "policy", "product", "factory", "market", "pushed", "denominator"]).to_csv(
        os.path.join(out, "overflow_by_factory_market.csv"), index=False, encoding="utf-8-sig")

    def krow(c, s, m):
        k = keys[(keys["case"] == c) & (keys["sku_id"] == s) & (keys["region"] == m)]
        if len(k) != 1:
            raise StrategyError(f"案 {c} の ①〜⑤ に {s} × {m} の行がありません")
        return k.iloc[0]

    rows = []
    p0b = recs[cases[0]]["P0_base"] if cases else C.read_case(ws, base)["run"]["summary"]["P0_report"]
    costb = _cost_cell(recs[cases[0]]["fixed_cost"], "base") if cases else 0.0
    A_base = p0b - costb
    for c in allc:
        rec = recs.get(c)
        p0 = p0b if c == base else rec["P0_alt"]
        cost = costb if c == base else _cost_cell(rec["fixed_cost"], "alt")
        if c != base and abs(rec["P0_base"] - p0b) > 0.5:
            raise StrategyError(f"比較ごとに基準の P0 が違います（{rec['P0_base']} と {p0b}）")
        t = krow(c, sku, market)
        lg = _demand_log_totals(ws, c, sku, market, rs, re_)
        if int(t["q1"]) != B + lg["d"]:
            raise StrategyError(f"案 {c}：対象 {sku} × {market} の ① {int(t['q1'])} が B {B} ＋ d {lg['d']} と合いません")
        shelf = runs[c]["shelf"]
        sh_all = shelf[(shelf["product"] == "*") & (shelf["channel"] == "*")]
        sh_t = shelf[(shelf["product"] == sku) & (shelf["channel"] == t["market"])]
        inv = runs[c]["inv"]
        inv = inv[inv["external"].astype(int) == 0]
        inv_w = inv.groupby("week_index")["lots"].sum()
        other = keys[(keys["case"] == c) & ~((keys["sku_id"] == sku) & (keys["region"] == market))]
        otherb = keys[(keys["case"] == base) & ~((keys["sku_id"] == sku) & (keys["region"] == market))]
        mo = other.merge(otherb, on=["sku_id", "region"], suffixes=("", "_b"))
        d4 = (mo["delivered"] - mo["delivered_b"]).astype(int)
        d5 = (mo["q5"] - mo["q5_b"]).astype(int)
        moved = "; ".join(f"{r.sku_id}×{r.region} ④{int(a):+d} ⑤{int(b):+d}"
                          for r, a, b in zip(mo.itertuples(), d4, d5) if a or b)
        A = p0 - cost
        rows.append({
            "case": c, "case_name": C.read_case(ws, c)["name"], "plan_id": lg["plan_id"],
            "P0": p0, "B_add": cost, "A": A, "dA_vs_base": A - A_base, "dP0_vs_base": p0 - p0b,
            "target": f"{sku}×{market}", "B_report": B, "d_report": lg["d"], "residual": lg["residual"],
            "q1": int(t["q1"]), "q2": int(t["q2"]), "q3": int(t["q3"]), "q4_delivered": int(t["delivered"]),
            "on_time": int(t["on_time"]), "early": int(t["early"]), "late": int(t["late"]), "q5": int(t["q5"]),
            "other_markets_d4_total": int(d4.sum()), "other_markets_d5_total": int(d5.sum()),
            "other_markets_changes": moved or "なし",
            "inventory_lots_max_week": int(inv_w.max()) if len(inv_w) else 0,
            "age_max_all": sh_all["fifo_age_max"].iloc[0] if len(sh_all) else "",
            "age_max_target": sh_t["fifo_age_max"].iloc[0] if len(sh_t) else "",
            "over_max_age_all": sh_all["over_max_age"].iloc[0] if len(sh_all) else "",
            "overflow_pushed_total": ov_total.get(c, "") if overflow else "未計測",
            "engine_vs_base": "（基準）" if c == base else _snapshot_same(runs[base].get("snapshot"),
                                                                       runs[c].get("snapshot")),
            "model_inputs_vs_base": "（基準）" if c == base else (
                "同じ" if C.read_case(ws, c)["run"]["input_hashes"] == C.read_case(ws, base)["run"]["input_hashes"]
                else "違う"),
        })
    summ = pd.DataFrame(rows)
    summ.to_csv(os.path.join(out, "strategy_summary.csv"), index=False, encoding="utf-8-sig")
    keys.to_csv(os.path.join(out, "fulfillment_by_key.csv"), index=False, encoding="utf-8-sig")
    _write_md(summ, os.path.join(out, "strategy_summary.md"), ws, base, cases, rs, re_)
    return {"dir": out, "summary": summ, "keys": keys, "overflow": ov_rows, "compares": recs}


def _write_md(summ: pd.DataFrame, path: str, ws: str, base: str, cases: List[str], rs: str, re_: str) -> None:
    L = [f"# 施策の変換の要約（{base} を基準に {', '.join(cases)}）", "",
         f"- 作業：`{ws}`、報告期間 {rs}〜{re_}",
         "- P0＝追加費用の控除前の現行比較値、B_add＝案の外の追加費用（円）、A＝P0−B_add、ΔA＝A−A(基準)。"
         "A はグループの営業利益や Net Cash ではない", "",
         "| 案 | 名前 | P0 | B_add | A | ΔA | ① | ② | ③ | ④ | ⑤ | 他市場 ④差 | 他市場 ⑤差 | 押し戻し | エンジン（基準と） |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in summ.itertuples():
        L.append(f"| {r.case} | {r.case_name} | {r.P0:,.0f} | {r.B_add:,.0f} | {r.A:,.0f} | {r.dA_vs_base:+,.0f} | "
                 f"{r.q1} | {r.q2} | {r.q3} | {r.q4_delivered} | {r.q5} | {r.other_markets_d4_total:+d} | "
                 f"{r.other_markets_d5_total:+d} | {r.overflow_pushed_total} | {r.engine_vs_base} |")
    L += ["", "他の市場の変化：", ""] + [f"- {r.case}：{r.other_markets_changes}" for r in summ.itertuples()]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
