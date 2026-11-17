# -*- coding: utf-8 -*-
"""
wom/cockpit/after_cost.py — 増産の確保費の週額の仮置きと在庫の保有費で、案の控除後の利益を並べる
==========================================================================================
RequestLetter_Cockpit_AfterCost_ThreeCases（2026-11-18）。週額は GPT-MC の見積もり v0.1 の仮置き
（採用額ではない）。保有費は在庫の保有費の段（holding_base.csv と同じ作り方：グループの法人・評価済み・
連結原価・助走を含む。P0 の外の別欄）。

    控除後の利益 ＝ P0（報告期間）− 確保費（有償の週 × その案の週額）− 保有費（年率 ÷ 52 × 連結原価の在庫・週）

- 週額の表 `<作業>/inputs/raise_cost_scenarios.csv` が無い作業では、週額は「未設定」（黙って既定値を作らない）。
- 案が「全期間」か「期間を絞った」かは、有償の週の範囲が計画の全週と同じかで決める（同じなら全期間の額）。
  増産の行が無い案は確保費 0。
- 一時費用・最低保証・通常の加工費との重なりは入れない（注記だけ）。
- どちらが良いかは書かない（数字を並べるだけ）。

計算は `after_cost_rows`（入力は案ごとの事実の dict）だけで行い、CLI（tools/cockpit_cases after-cost）と
比較の画面（compare_view_model）が同じ関数を使う。
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence

import pandas as pd

SCENARIO_FILE = "raise_cost_scenarios.csv"
SCEN_COLS = ["scenario", "level", "premium_pct", "weekly_amount_full", "weekly_amount_narrowed", "status", "note"]
HOLDING_RATES: Sequence[Optional[float]] = (None, 0.05, 0.10, 0.15)     # None = 保有費なし
WEEKS_PER_YEAR = 52
UNSET = "未設定"
NOT_COMPUTED = "未算出"
NO_TABLE = "（週額の表なし）"
KIND_NONE, KIND_FULL, KIND_NARROWED = "増産しない", "全期間", "期間を絞った"
RAISE_ITEM = "planned_output_raise"
OVERLAP_NOTE = ("工場の通常の加工費（1 個 600 円）は P0 に入っている。応援の人件費と重なる部分は差し引いていない"
                "（今回の計算に入れない。注記だけ）。一時費用・最低保証は入れていない")
ROW_COLS = ["scenario", "level", "premium_pct", "scenario_status", "holding_rate", "holding_rate_text", "case",
            "case_name", "raise_kind", "paid_start", "paid_end", "W", "weekly_amount", "raise_cost", "P0",
            "H_report", "H_warmup", "H_total", "P_after", "diff_vs_first", "note"]


class AfterCostError(ValueError):
    """The scenario table or a case cannot be used."""


def scenario_path(ws: str) -> str:
    return os.path.join(ws, "inputs", SCENARIO_FILE)


def read_raise_scenarios(ws: str) -> Optional[pd.DataFrame]:
    """The workspace's weekly amount scenarios, or None when the workspace has no table (= 未設定).
    Stops on missing columns, a blank or negative amount, a premium that is not a number, a repeated scenario."""
    p = scenario_path(ws)
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    miss = [c for c in SCEN_COLS if c not in df.columns]
    if miss:
        raise AfterCostError(f"{p}: 列が足りません {miss}。直し方：{', '.join(SCEN_COLS)} の列を置く")
    if df.empty:
        raise AfterCostError(f"{p}: 行がありません。直し方：シナリオを 1 行以上書くか、ファイルを消す（未設定に戻す）")
    for i, r in df.iterrows():
        where = f"{p} の {i + 2} 行目（{r['scenario']}）"
        if not r["scenario"].strip():
            raise AfterCostError(f"{where}: scenario が空")
        for c in ("premium_pct", "weekly_amount_full", "weekly_amount_narrowed"):
            try:
                v = float(r[c])
            except ValueError:
                raise AfterCostError(f"{where}: {c}={r[c]!r} は数ではない。直し方：数を入れる（空欄は不可）")
            if v < 0:
                raise AfterCostError(f"{where}: {c} は 0 以上")
    if df["scenario"].duplicated().any():
        raise AfterCostError(f"{p}: 同じ scenario の行が重複しています {sorted(df.loc[df['scenario'].duplicated(), 'scenario'])}")
    return df


def raise_kind(paid_start: str, paid_end: str, plan_start: str, plan_end: str) -> str:
    if not paid_start:
        return KIND_NONE
    return KIND_FULL if (paid_start, paid_end) == (plan_start, plan_end) else KIND_NARROWED


def rate_text(r: Optional[float]) -> str:
    return "なし" if r is None else f"{r * 100:g}%"


def after_cost_rows(scen: Optional[pd.DataFrame], facts: List[dict], rates=HOLDING_RATES) -> pd.DataFrame:
    """facts: one dict per case, in order (the first is the reference of diff_vs_first):
        case, case_name, P0, paid_start, paid_end, W, kind (KIND_*), B_report, B_warmup, note
    One row per scenario x holding rate x case."""
    scen_rows = ([dict(r) for _, r in scen.iterrows()] if scen is not None else
                 [{"scenario": NO_TABLE, "level": "", "premium_pct": "", "status": "", "note": "",
                   "weekly_amount_full": None, "weekly_amount_narrowed": None}])
    rows = []
    for s in scen_rows:
        for rate in rates:
            first = None
            for f in facts:
                if f["kind"] == KIND_NONE:
                    wa, cost = 0.0, 0.0
                else:
                    col = "weekly_amount_full" if f["kind"] == KIND_FULL else "weekly_amount_narrowed"
                    wa = None if s[col] in (None, "") else float(s[col])
                    cost = None if wa is None else wa * f["W"]
                if rate is None:
                    hr = hw = 0.0
                else:
                    hr = rate / WEEKS_PER_YEAR * f["B_report"]
                    hw = rate / WEEKS_PER_YEAR * f["B_warmup"]
                after = None if cost is None else f["P0"] - cost - (hr + hw)
                if first is None:
                    first = after
                rows.append({
                    "scenario": s["scenario"], "level": s["level"], "premium_pct": s["premium_pct"],
                    "scenario_status": s["status"], "holding_rate": "" if rate is None else rate,
                    "holding_rate_text": rate_text(rate), "case": f["case"], "case_name": f.get("case_name", ""),
                    "raise_kind": f["kind"], "paid_start": f["paid_start"], "paid_end": f["paid_end"], "W": f["W"],
                    "weekly_amount": UNSET if wa is None else wa, "raise_cost": UNSET if cost is None else cost,
                    "P0": f["P0"], "H_report": hr, "H_warmup": hw, "H_total": hr + hw,
                    "P_after": NOT_COMPUTED if after is None else after,
                    "diff_vs_first": NOT_COMPUTED if (after is None or first is None) else after - first,
                    "note": f.get("note", "")})
    return pd.DataFrame(rows, columns=ROW_COLS)


def pair_diffs(rows: pd.DataFrame, base: str, alt: str) -> pd.DataFrame:
    """For two cases: one row per scenario x rate with each case's after-cost profit and alt − base."""
    out = []
    for (sc, rt), g in rows.groupby(["scenario", "holding_rate_text"], sort=False):
        b, a = g[g["case"] == base].iloc[0], g[g["case"] == alt].iloc[0]
        ok = NOT_COMPUTED not in (b["P_after"], a["P_after"])
        out.append({"scenario": sc, "level": b["level"], "premium_pct": b["premium_pct"],
                    "holding_rate": b["holding_rate"], "holding_rate_text": rt,
                    "weekly_amount_base": b["weekly_amount"], "weekly_amount_alt": a["weekly_amount"],
                    "raise_cost_base": b["raise_cost"], "raise_cost_alt": a["raise_cost"],
                    "H_total_base": b["H_total"], "H_total_alt": a["H_total"],
                    "P_after_base": b["P_after"], "P_after_alt": a["P_after"],
                    "diff": (a["P_after"] - b["P_after"]) if ok else NOT_COMPUTED})
    return pd.DataFrame(out)


# ── 案の事実（CLI 用：案の実行の出力から読む） ─────────────────────────────────
def case_facts(ws: str, cid: str) -> dict:
    """P0 (report period), the raise cost row of the case's cost premises and the holding base, from the case's
    run (tools/compare_scenarios.py's functions; the same numbers as a comparison). The case must be 済み."""
    import sys
    from wom.cockpit import cases as C
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if repo not in sys.path:
        sys.path.insert(0, repo)
    from tools import compare_scenarios as CS
    st = C.status(ws, cid)
    if st["state"] != C.ST_DONE:
        raise AfterCostError(f"案 {cid} は「{st['state']}」です（{st['reason']}）。並べられるのは「済み」の案だけ")
    case = C.read_case(ws, cid)
    cdir = C.case_dir(ws, cid)
    rd = os.path.join(cdir, "run")
    vc = os.path.join(rd, "vc")
    mdl = os.path.join(cdir, (case.get("run") or {}).get("money_model") or "model")
    run = {"inv": pd.read_csv(os.path.join(vc, "vc_inventory_weekly.csv")),
           "v3": pd.read_csv(os.path.join(vc, "vc_v3_weekly.csv")),
           "entity": pd.read_csv(os.path.join(mdl, "vc_entity.csv"), dtype=str)}
    p0, vstat, rs, re_ = CS.report_p0(run)
    labels = list(run["v3"][run["v3"]["group_key"] == "GROUP"].sort_values("week_index")["week"])
    hb = CS.holding_base(CS.holding_inventory(run, cid, rs, re_))
    tot = hb[(hb["product"] == "*") & (hb["location_kind"] == "*")].set_index("period")["B_group_hq"]
    unval = int(hb[(hb["product"] == "*") & (hb["location_kind"] == "*")]["unvalued_lots_weeks"].sum())
    notes = []
    if vstat != "評価済み":
        notes.append(vstat)
    if unval:
        notes.append(f"未評価の在庫 lot・週 {unval:,}")
    ps = pe = ""
    w = 0
    fcp = os.path.join(cdir, "inputs", C.FIXED_COST_FILE)
    if os.path.exists(fcp):
        fc = pd.read_csv(fcp, dtype=str, keep_default_na=False)
        rr = fc[fc["cost_item"] == RAISE_ITEM]
        other = sorted(set(fc["cost_item"]) - {RAISE_ITEM})
        if other:
            notes.append(f"ほかの費目（{', '.join(other)}）は入れていない")
        if len(rr):
            x = rr.iloc[0]
            ps, pe = x["paid_start_week"], x["paid_end_week"]
            outside = str(x.get(CS.COUNT_OUTSIDE_COL, "")).strip() == "1"
            a, b = (labels[0], labels[-1]) if outside else (rs, re_)
            w = CS.paid_weeks(ps, pe, a, b)
    return {"case": cid, "case_name": case.get("name", ""), "P0": p0, "paid_start": ps, "paid_end": pe, "W": w,
            "kind": raise_kind(ps, pe, labels[0], labels[-1]),
            "B_report": float(tot.get("report", 0.0)), "B_warmup": float(tot.get("warmup", 0.0)),
            "note": "；".join(notes), "report_period": (rs, re_), "plan_period": (labels[0], labels[-1])}


def after_cost(ws: str, cases: List[str], name: Optional[str] = None) -> dict:
    """Write <ws>/after_cost/<name>/after_cost_table.csv and after_cost_summary.md. Returns {"dir", "rows"}."""
    if len(cases) < 2:
        raise AfterCostError("案を 2 つ以上並べる（例 C01,C02,C03）")
    if len(set(cases)) != len(cases):
        raise AfterCostError(f"同じ案が 2 回あります {cases}")
    scen = read_raise_scenarios(ws)
    facts = [case_facts(ws, c) for c in cases]
    rp = {f["report_period"] for f in facts}
    if len(rp) > 1:
        raise AfterCostError(f"案の報告期間が違います {sorted(rp)}")
    rows = after_cost_rows(scen, facts)
    out = os.path.join(ws, "after_cost", name or "_".join(cases))
    os.makedirs(out, exist_ok=True)
    rows.to_csv(os.path.join(out, "after_cost_table.csv"), index=False, encoding="utf-8-sig")
    write_summary(rows, facts, scen, os.path.join(out, "after_cost_summary.md"))
    return {"dir": out, "rows": rows, "facts": facts, "scenarios": scen}


def _yen(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"{f:,.0f}" if abs(f - round(f)) < 1e-6 else f"{f:,.2f}"


def write_summary(rows: pd.DataFrame, facts: List[dict], scen: Optional[pd.DataFrame], path: str) -> None:
    cases = [f["case"] for f in facts]
    first = cases[0]
    L = [f"# 控除後の利益（{' ・ '.join(cases)}）", "",
         "控除後の利益 ＝ P0（報告期間）− 確保費（有償の週 × その案の週額）− 在庫の保有費（年率 ÷ 52 × 連結原価の在庫・週、"
         "助走を含む）。円。", "",
         "週額は GPT-MC の見積もり v0.1 の仮置き（採用額ではない）。保有費の年率も仮置き（採用する率は未設定）。"
         if scen is not None else f"週額の表（inputs/{SCENARIO_FILE}）が無い：週額は「{UNSET}」、増産する案の控除後の利益は「{NOT_COMPUTED}」。",
         "", f"注：{OVERLAP_NOTE}。", "", "## 案", "",
         "| 案 | 名前 | P0（報告期間） | 増産 | 有償の週 | W | 連結原価の在庫・週 報告期間 | 助走 | 注 |",
         "|---|---|---:|---|---|---:|---:|---:|---|"]
    for f in facts:
        L.append(f"| {f['case']} | {f['case_name']} | {_yen(f['P0'])} | {f['kind']} | "
                 f"{(f['paid_start'] + '〜' + f['paid_end']) if f['paid_start'] else '—'} | {f['W']} | "
                 f"{_yen(f['B_report'])} | {_yen(f['B_warmup'])} | {f['note']} |")
    L += ["", f"## 控除後の利益（シナリオ × 保有費の年率）。差は {first} との差", "",
          "| シナリオ | 水準 | 割増 | 年率 | " + " | ".join(f"{c} 控除後" for c in cases) + " | "
          + " | ".join(f"{c} − {first}" for c in cases[1:]) + " |",
          "|---|---|---:|---|" + "---:|" * (2 * len(cases) - 1)]
    for (sc, rt), g in rows.groupby(["scenario", "holding_rate_text"], sort=False):
        g = g.set_index("case")
        L.append(f"| {sc} | {g.iloc[0]['level']} | {g.iloc[0]['premium_pct']} | {rt} | "
                 + " | ".join(_yen(g.loc[c, "P_after"]) for c in cases) + " | "
                 + " | ".join(_yen(g.loc[c, "diff_vs_first"]) for c in cases[1:]) + " |")
    L += ["", "## 週額と確保費", "", "| シナリオ | " + " | ".join(f"{c} 週額 | {c} 確保費" for c in cases) + " |",
          "|---|" + "---:|" * (2 * len(cases))]
    for sc, g in rows[rows["holding_rate_text"] == "なし"].groupby("scenario", sort=False):
        g = g.set_index("case")
        L.append(f"| {sc} | " + " | ".join(f"{_yen(g.loc[c, 'weekly_amount'])} | {_yen(g.loc[c, 'raise_cost'])}"
                                           for c in cases) + " |")
    L += ["", "（数字を並べただけ。どの案が良いかは書かない）", ""]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))
