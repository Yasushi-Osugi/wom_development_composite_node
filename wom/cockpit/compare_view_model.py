# -*- coding: utf-8 -*-
"""
wom/cockpit/compare_view_model.py — 事業計画の比較の 1 画面に出す表（画面に依存しない。Tk を import しない）
=========================================================================================================
RequestLetter_Cockpit_Stage3_Step2 B・Step3 A、設計書 `requests/Cockpit_Stage3_DesignMD_PlanCompareScreen_v0.1.md`
§1・§2。

段 1 の関数（`wom/cockpit/cases.py`・`case_runner.py`）と、道具 2（`tools/compare_scenarios.py`）の出力から、
① 案の表、② 選んだ案の入力、③ 基準と相手の比較（要点・供給・工場・金額と境目）、④ 読むときの注意 を作る。
**数字を作り直さない**（ファイルを読み、並べ替え、見出しを付け、文章に並べるだけ）。ファイルは書かない。

黙って誤らないための決まり（設計書 §2.2、段 3 B3）：
1. 案の状態が「入力が変わった」なら、結果を出さず「実行し直す」と変わったファイルの名前を出す。
2. 比較の状態が「済み」でなければ（未実行・入力が変わった・不整合）、③ の数字を出さず理由だけを出す。
   費用の前提だけが変わったときは、固定費の表と要点の「判断に要るもの」だけを出さない（並べ直す）。
3. 未設定と 0 を分ける：週額が空欄の行は「未設定」。控除後の利益は合計の行だけに出し、未設定があれば「未算出」。
4. どちらの案が良いかは言わない（差・境目・順位を決められない理由まで）。
5. 衝突・未達・止まった・不整合の案は、状態と理由を出す。
"""
from __future__ import annotations

import glob
import json
import math
import os
from typing import Dict, List, Optional

import pandas as pd

from wom.cockpit import cases as C
from wom.cockpit import case_runner as R

UNSET = "未設定"
NOT_COMPUTED = "未算出"
NOT_APPLICABLE = "対象外"
PENDING = "保留"
RERUN = "実行し直す"
RECOMPARE = "並べ直す"
STATE_DISPLAY = {C.ST_CHANGED: RERUN}
WEEK_RULE_SHORT = {"trim_to_capacity_latest": "削って最低", "proportional_early_tie": "比例・早い週優先",
                   "proportional_even": "比例・均等", "earliest_first": "早い週から"}
EDGE_WEEKS_TEXT = "計画の端の週（計画の最初の 1 週と最後の 4 週）"


# ── 小道具 ─────────────────────────────────────────────────────────────
def _csv(path: str, **kw) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", **kw)


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() in ("", "nan")


def _num(v) -> Optional[float]:
    try:
        f = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def fmt_yen(v) -> str:
    f = _num(v)
    if f is None:
        return str(v) if not _blank(v) else ""
    return f"{f:,.0f}" if abs(f - round(f)) < 1e-6 else f"{f:,.2f}"


KEY_WORDS = ("置けない", "衝突", "不整合", "止め", "未達", "Error", "error", "がありません", "違います")


def message_gist(msg: str, limit: int = 3) -> str:
    """The lines of a tool's message that say what happened (not the output path that often comes last)."""
    lines = [x.strip() for x in (msg or "").splitlines() if x.strip() and not x.strip().startswith("->")]
    key = [x for x in lines if any(w in x for w in KEY_WORDS)]
    pick = key[-limit:] if key else lines[-1:]
    return " / ".join(pick)[:400]


def compare_dir(ws: str, base: str, alt: str) -> str:
    return os.path.join(ws, "compare", f"{base}__{alt}")


def available_comparisons(ws: str) -> List[tuple]:
    out = []
    for d in sorted(glob.glob(os.path.join(ws, "compare", "*__*"))):
        b, a = os.path.basename(d).split("__", 1)
        out.append((b, a))
    return out


def policy_short(pol: Optional[dict]) -> str:
    """Short name of a supply policy for the case table (the file names go to ②)."""
    if not pol:
        return "なし"
    rule = WEEK_RULE_SHORT.get(pol.get("week_rule") or "", pol.get("week_rule") or "")
    return ("数量枠＋最低供給" if pol.get("min_supply") or pol.get("policy_file") else "数量枠") + f"・{rule}"


def side_label(side: str, cid: str) -> str:
    return f"{'基準' if side == 'base' else '相手'}（{cid}）"


# ── ① 案の表 ───────────────────────────────────────────────────────────
def case_table(ws: str) -> dict:
    """{"columns": [...], "rows": [ {"id", "cells": [...], "state", "show_result", "reason"} ]}.
    Only the inputs that differ between cases get a column (as cases.format_list)."""
    rows = C.list_cases(ws)
    for r in rows:      # 段 4 A3: a case that has run shows the capacity the engine used for its factories
        e = engine_capacity(ws, r["id"])
        if e is not None:
            for (p, f), g in e.groupby(["product", "factory"]):
                r["inputs"]["capacity"][f"{p}@{f}"] = engine_capacity_cell(g)

    def varying(getter):
        keys = sorted({k for r in rows for k in getter(r)})
        return [k for k in keys if len({getter(r).get(k) for r in rows}) > 1]

    lw = varying(lambda r: r["inputs"]["launch_week"])
    cap = varying(lambda r: r["inputs"]["capacity"])
    skus = sorted({s for r in rows for s in ((r["result"] or {}).get("deliveries_by_sku") or {})})
    cols = ["ID", "案の名前", "親"] + [f"投入 {k}" for k in lw] + [f"能力 {k}（hard/soft）" for k in cap] + \
        ["供給の方針"] + [f"納品 {s}" for s in skus] + ["未配分", "未充足（期末）", "P0（円、報告期間）", "状態"]
    out = []
    for r in rows:
        res = r["result"] or {}
        show = r["state"] == C.ST_DONE and bool(res)
        cells = [r["id"], r["name"], r["parent"] or "—"] + [r["inputs"]["launch_week"].get(k, "") for k in lw] + \
            [r["inputs"]["capacity"].get(k, "") for k in cap] + [policy_short(r["inputs"]["policy"])]
        if show:
            ua = res.get("unallocated_by_key")
            cells += [f"{(res.get('deliveries_by_sku') or {}).get(s, 0):,}" for s in skus]
            ml = case_market_labels(ws, r["id"])
            cells += ["—" if ua is None else _kv(ua, ml), _kv(res.get("backlog_end_by_key"), ml),
                      fmt_yen(res.get("P0_report"))]
        else:
            cells += [""] * (len(skus) + 3)
        cells.append(STATE_DISPLAY.get(r["state"], r["state"]))
        out.append({"id": r["id"], "name": r["name"], "cells": cells, "state": r["state"], "show_result": show,
                    "reason": r["reason"], "result": res if show else None})
    return {"columns": cols, "rows": out}


def _kv(d, labels: Optional[Dict[str, str]] = None) -> str:
    d = {k: v for k, v in (d or {}).items() if v}
    return "、".join(f"{(labels or {}).get(k, k)} {v}" for k, v in sorted(d.items())) or "0"


def case_market_labels(ws: str, cid: str) -> Dict[str, str]:
    """'sku:region' -> 'sku:market（region）' from the case model's sc_tree_master.csv (段 4 A2); same names unchanged."""
    p = os.path.join(C.case_dir(ws, cid), "model", "sc_tree_master.csv")
    if not os.path.exists(p):
        return {}
    t = _csv(p, dtype=str, keep_default_na=False)
    t = t[t["node_type"].str.strip() == "leaf_out"]
    return {f"{r.product_name}:{r.region}": f"{r.product_name}:{r.node_name}（{r.region}）"
            for r in t.itertuples() if r.region and r.region != r.node_name}


# ── 到達点 5：製品 × 市場の表・需要の仮説 ──────────────────────────────
def entry_matrix(ws: str, cid: str) -> dict:
    """The entry plan as a product x market table: {"products": [...], "markets": [...],
    "cells": {(sku, region): {"text": '2028-W01・定常 3・×0.5（13 週）', **row}}}. Markets are listed in the
    order of the entry plan rows; a product without a row in a market has no cell."""
    rows = case_inputs(ws, cid)["entry_plan"]
    products = list(dict.fromkeys(r["sku_id"] for r in rows))
    markets = list(dict.fromkeys(r["region"] for r in rows))
    cells = {(r["sku_id"], r["region"]): {**r, "text": f"{r['launch_week']}・定常 {r['steady_lots_per_week']}・"
                                                     f"×{r['ramp_ratio']}（{r['ramp_weeks']} 週）"} for r in rows}
    return {"products": products, "markets": markets, "cells": cells}


def notes_changed_after_compare(ws: str, base: str, alt: str) -> List[str]:
    """Keys whose entry-plan text (basis_note / promotion_note) changed after the comparison (到達点 5 A0-4).
    The numbers of the comparison stay valid; only the text on the screen is newer. Empty when the comparison
    has no record of the text (made before)."""
    p = os.path.join(compare_dir(ws, base, alt), "compare.json")
    if not os.path.exists(p):
        return []
    rec = json.load(open(p, encoding="utf-8"))
    out = []
    for cid, key in ((base, "base_entry_notes"), (alt, "alt_entry_notes")):
        if key not in rec:
            continue
        now = C.entry_notes(ws, cid)
        for k in sorted(set(now) | set(rec[key])):
            if now.get(k) != rec[key].get(k):
                out.append(f"{cid} {k}")
    return out


# ── ② 選んだ案の入力 ─────────────────────────────────────────────────────
def _calendar(cdir: str) -> Optional[pd.DataFrame]:
    p = os.path.join(cdir, "model", C.OPCAL)
    return _csv(p, dtype=str, keep_default_na=False) if os.path.exists(p) else None


def engine_capacity(ws: str, cid: str) -> Optional[pd.DataFrame]:
    """The capacity the engine used in the case's last run (run/capacity.csv, 段 4 A3), only when the case is 済み
    (the run matches the inputs). None otherwise (not run, inputs changed, or a run made before the file existed)."""
    p = os.path.join(C.case_dir(ws, cid), "run", "capacity.csv")
    if not os.path.exists(p) or C.status(ws, cid)["state"] != C.ST_DONE:
        return None
    return _csv(p, dtype=str, keep_default_na=False)


def engine_capacity_text(e: pd.DataFrame) -> str:
    """One factory's planned output as the engine used it, e.g. '18 シフト → 686 lot／週（設備 800 × 18 ÷ 21）、
    休業 2027-W18, 2028-W18, 2028-W33' or 'max_supply 13・cap_soft 2028-W11〜2029-W46 は 12、ほかは 11'."""
    opn = e[e["closed"].astype(str) != "1"].to_dict("records")
    closed = sorted(e[e["closed"].astype(str) == "1"]["week"])
    tail = f"、休業 {len(closed)} 週（{', '.join(closed)}）" if closed else ""
    if not opn:
        return "全週休業"
    if all(r["cap_soft_source"] == "calendar" for r in opn):
        groups = {}
        for r in opn:
            groups.setdefault((r["shifts"], r["cap_hard"], r["cap_soft"]), []).append(r)
        if len(groups) == 1:
            (sh, ch, cs), = groups.keys()
            return f"{sh} シフト → {cs} lot／週（設備 {ch} × {sh} ÷ {C.MAX_SHIFTS}）{tail}（エンジンの値）"
        txt, _m = range_text([{**r, "v": f"{r['shifts']} シフト → {r['cap_soft']}"} for r in opn], "v")
        return f"{txt} lot／週（設備 × シフト ÷ {C.MAX_SHIFTS}）{tail}（エンジンの値）"
    hard, _ = range_text(opn, "cap_hard")
    soft, _ = range_text(opn, "cap_soft")
    return f"max_supply {hard}・cap_soft {soft}{tail}（エンジンの値）"


def engine_capacity_cell(e: pd.DataFrame) -> str:
    """① the case table's capacity cell from the engine's values: 'hard/soft' over the open weeks."""
    opn = [{"week": r["week"], "max_supply": r["cap_hard"], "cap_soft": r["cap_soft"]}
           for r in e.to_dict("records") if str(r["closed"]) != "1"]
    return C.capacity_text(opn) if opn else "休業"


def range_text(rows: List[dict], col: str):
    """(text, main value) of one capacity column over the weeks of the rows.
    One value → ('11', '11'). Several → ('2028-W11〜2029-W46 は 12、ほかは 11', '11'): the value at both ends of
    the plan is 'ほか' (else the value held for the most weeks); the other values are listed with their week ranges
    (never shown as one value)."""
    srt = sorted(rows, key=lambda r: r["week"])
    runs = []
    for r in srt:
        v = (r.get(col) or "").strip()
        if runs and runs[-1][0] == v:
            runs[-1][2] = r["week"]
            runs[-1][3] += 1
        else:
            runs.append([v, r["week"], r["week"], 1])
    weeks = {}
    for v, _a, _b, n in runs:
        weeks[v] = weeks.get(v, 0) + n
    if len(weeks) == 1:
        v = next(iter(weeks))
        return (v if v else UNSET), v
    # 'ほか' = the value at both ends of the plan (a raise inside the plan reads "<range> は 12、ほかは 11");
    # if the two ends differ, the value held for the most weeks
    main = runs[0][0] if runs[0][0] == runs[-1][0] else max(weeks, key=lambda v: (weeks[v], v))
    parts = []
    for v in sorted((v for v in weeks if v != main), key=lambda v: min(a for x, a, _b, _n in runs if x == v)):
        rng = "・".join(f"{a}〜{b}" if a != b else a for x, a, b, _n in runs if x == v)
        parts.append(f"{rng} は {v if v else UNSET}")
    return "、".join(parts) + f"、ほかは {main if main else UNSET}", main


def case_inputs(ws: str, cid: str) -> dict:
    cdir = C.case_dir(ws, cid)
    case = C.read_case(ws, cid)
    st = C.status(ws, cid)
    run = case.get("run") or {}
    out = {"id": cid, "name": case["name"], "parent": case.get("parent"), "state": st["state"],
           "state_display": STATE_DISPLAY.get(st["state"], st["state"]), "reason": st["reason"],
           "changed_files": st.get("changed_files", []), "entry_plan": [], "capacity": [], "policy": None,
           "fixed_cost": [], "run_message": run.get("message", "") if st["state"] not in (C.ST_DONE, C.ST_CHANGED) else "",
           "log_dir": os.path.join(cdir, "run", "logs"),
           "note": "入力を変えるのは ② の下のボタンから（変えたら実行し直す）"}
    ep = os.path.join(cdir, "model", C.ENTRY_PLAN)
    if os.path.exists(ep):
        d = _csv(ep, dtype=str, keep_default_na=False)
        for c in C.NOTE_COLS:
            if c not in d.columns:
                d[c] = ""
        out["entry_plan"] = d[["sku_id", "region", "launch_week", "steady_lots_per_week", "ramp_weeks",
                               "ramp_ratio", "basis_note", "promotion_note"]].to_dict("records")
    cap = _csv(os.path.join(cdir, "model", C.CAPACITY), dtype=str, keep_default_na=False)
    if "cap_soft" not in cap.columns:
        cap["cap_soft"] = ""
    eng = engine_capacity(ws, cid)
    cal = _calendar(cdir)
    out["has_calendar"] = cal is not None
    out["capacity_source"] = "engine" if eng is not None else "inputs"
    for (sku, node), g in cap.groupby(["sku_id", "node_name"]):
        recs = g.to_dict("records")
        ms_text, ms_main = range_text(recs, "max_supply")
        cs_text, cs_main = range_text(recs, "cap_soft")
        cr = cal[(cal["sku_id"] == sku) & (cal["node_name"] == node)].to_dict("records") if cal is not None else []
        x = {"sku_id": sku, "node": node, "rows": len(g), "max_supply": ms_text, "cap_soft": cs_text,
             "max_supply_main": ms_main, "cap_soft_main": cs_main, "runs": C.capacity_runs(recs),
             "calendar": bool(cr), "shifts": "", "shifts_main": "", "closed_weeks": [], "source": "inputs"}
        if cr:
            opn = [r for r in cr if str(r["shifts"]).strip() != "0"]
            x["closed_weeks"] = sorted(r["week"] for r in cr if str(r["shifts"]).strip() == "0")
            x["shifts"], x["shifts_main"] = range_text(opn, "shifts") if opn else ("", "")
        e = eng[(eng["product"] == sku) & (eng["factory"] == node)] if eng is not None else None
        if e is not None and len(e):
            x["source"] = "engine"
            x["text"] = engine_capacity_text(e)
        elif cr:
            x["text"] = (f"max_supply {ms_text}・シフト {x['shifts']}"
                         + (f"（休業 {', '.join(x['closed_weeks'])}）" if x["closed_weeks"] else "")
                         + "。計画値はシフトで決まる（実行するとエンジンの値が出る）")
        else:
            x["text"] = f"max_supply {ms_text}・cap_soft {cs_text}"
        out["capacity"].append(x)
    pol = case["inputs"].get("policy")
    if pol:
        out["policy"] = {"allocation_file": pol.get("allocation_file"), "policy_file": pol.get("policy_file"),
                         "week_rule": pol.get("week_rule"), "knowledge_file": pol.get("knowledge_file"),
                         "unallocated_note": pol.get("unallocated_note"), "short": policy_short(pol)}
    fc = case["inputs"].get("fixed_cost")
    if fc and os.path.exists(os.path.join(cdir, fc)):
        d = _csv(os.path.join(cdir, fc), dtype=str, keep_default_na=False)
        for _, r in d.iterrows():
            out["fixed_cost"].append({
                "cost_item": r["cost_item"], "display_name": (r.get(C.DISPLAY_COL, "") or "").strip(),
                "label": (r.get(C.DISPLAY_COL, "") or "").strip() or r["cost_item"], "entity": r["entity"],
                "paid_start_week": r["paid_start_week"], "paid_end_week": r["paid_end_week"],
                "paid": f"{r['paid_start_week']}〜{r['paid_end_week']}",
                "weekly_amount": r["weekly_amount"] if r["weekly_amount"].strip() else UNSET,
                "weekly_amount_raw": r["weekly_amount"].strip(), "currency": r["currency"],
                "count_outside_report": (r.get(C.COUNT_OUTSIDE_COL, "") or "").strip() == "1",
                "note": r.get("note", "")})
    return out


# ── ③ 比較 ─────────────────────────────────────────────────────────────
def _min_supply_exact(ws: str, cid: str) -> Dict[tuple, bool]:
    """(sku, region, request week) -> True when the supply in scope equals the minimum supply
    (udp_min_supply_check.csv of a policy case). The value says whether the week was cut to the minimum
    (unallocated > 0) or the demand itself equals the minimum."""
    run = (C.read_case(ws, cid).get("run") or {})
    if not run.get("udp_dir"):
        return {}
    p = os.path.join(C.case_dir(ws, cid), run["udp_dir"], "udp_min_supply_check.csv")
    if not os.path.exists(p):
        return {}
    d = _csv(p)
    sel = os.path.join(C.case_dir(ws, cid), run["udp_dir"], "udp_selection_ledger.csv")
    q3 = {}
    if os.path.exists(sel):
        s = _csv(sel, dtype=str)
        q3 = {r["source_demand_ref"]: int(r["q3"]) for _, r in s.iterrows()}
    out = {}
    for _, r in d.iterrows():
        if int(r["min_supply_lots"]) > 0 and int(r["q2"]) == int(r["min_supply_lots"]):
            sku, reg, wk = r["source_demand_ref"].split("|")
            out[(sku, reg, wk)] = q3.get(r["source_demand_ref"], 0) > 0
    return out


def comparison(ws: str, base: str, alt: str) -> dict:
    """③ and the comparison part of ④. When the comparison is not 済み, only state and reason.
    When only the cost premises changed, everything but the fixed cost table (and the judgement paragraph)."""
    st = R.compare_status(ws, base, alt)
    d = compare_dir(ws, base, alt)
    out = {"base": base, "alt": alt, "state": st, "reason": "", "available": False, "cost_stale": False}
    if st not in (C.ST_DONE, R.ST_COST_CHANGED):
        if st == C.ST_NOT_RUN:
            out["reason"] = "この 2 案はまだ並べていない（「並べる」を押す）"
        elif st == C.ST_CHANGED:
            out["reason"] = f"比べた後に案の入力が変わったか、案を実行し直した。{RECOMPARE}"
        else:
            rec = json.load(open(os.path.join(d, "compare.json"), encoding="utf-8"))
            out["reason"] = rec.get("message", "")
        return out
    out["available"] = True
    if st == R.ST_COST_CHANGED:
        out["cost_stale"] = True
        out["reason"] = f"費用の前提が変わった：{RECOMPARE}（固定費の表と「判断に要るもの」は出さない）"
    out["record"] = json.load(open(os.path.join(d, "compare.json"), encoding="utf-8"))
    out["supply"] = supply_view(ws, base, alt)
    out["supply_diff"] = supply_diff(out["supply"], base, alt)
    out["factory"] = factory_view(d, base, alt)
    out["money"] = money_view(d, base, alt, hide_fixed_cost=out["cost_stale"])
    out["summary"] = summary(ws, base, alt, out)
    return out


SUPPLY_KEYS = ["demand", "in_scope", "unallocated", "on_time", "early", "late", "backlog"]


def market_labels(d: str) -> Dict[tuple, str]:
    """(sku, demand region) -> 'sku:market（region）' (or 'sku:region' when the names are the same), from the
    comparison's market_map.csv (段 4 A2). Comparisons made before have no file: 'sku:region'."""
    p = os.path.join(d, "market_map.csv")
    out = {}
    if os.path.exists(p):
        for r in _csv(p, dtype=str, keep_default_na=False).itertuples():
            out[(r.sku_id, r.region)] = (f"{r.sku_id}:{r.market}（{r.region}）" if r.market != r.region
                                         else f"{r.sku_id}:{r.region}")
    return out


def key_text(sv: dict, sku: str, region: str) -> str:
    return (sv.get("labels") or {}).get((sku, region), f"{sku}:{region}")


def supply_view(ws: str, base: str, alt: str) -> dict:
    """Key x request week for both cases: demand, on time, early, late, unallocated (③),
    backlog after allocation (⑤), and the minimum-supply-exact mark."""
    d = compare_dir(ws, base, alt)
    p = os.path.join(d, "supply_allocation_by_request_week.csv")
    if os.path.exists(p):
        s = _csv(p, dtype={"request_week": str})
        m = {"demand": "q1_original", "in_scope": "q2_in_scope", "unallocated": "q3_unallocated",
             "on_time": "on_time", "early": "early", "late": "late", "backlog": "q5_backlog_end"}
        allocation = True
    else:
        s = _csv(os.path.join(d, "supply_by_request_week.csv"), dtype={"request_week": str})
        m = {"demand": "demand", "in_scope": "demand", "unallocated": None, "on_time": "on_time", "early": "early",
             "late": "late", "backlog": "backlog_end"}
        allocation = False
    marks = {base: _min_supply_exact(ws, base), alt: _min_supply_exact(ws, alt)}
    cells, totals = [], []
    for side, cid in (("base", base), ("alt", alt)):
        for _, r in s.iterrows():
            k = (r["sku_id"], r["region"], r["request_week"])
            x = {"case": cid, "side": side, "sku_id": k[0], "region": k[1], "request_week": k[2]}
            for name, col in m.items():
                x[name] = 0 if col is None else int(r[f"{col}_{side}"])
            x["min_supply_exact"] = k in marks[cid]
            x["cut_to_minimum"] = bool(marks[cid].get(k, False))
            cells.append(x)
    cdf = pd.DataFrame(cells)
    for (cid, side, sku, reg), g in cdf.groupby(["case", "side", "sku_id", "region"], sort=False):
        totals.append({"case": cid, "side": side, "sku_id": sku, "region": reg,
                       **{k: int(g[k].sum()) for k in SUPPLY_KEYS},
                       "min_supply_exact_weeks": int(g["min_supply_exact"].sum()),
                       "cut_to_minimum_weeks": int(g["cut_to_minimum"].sum())})
    return {"allocation": allocation, "cells": cdf, "totals": pd.DataFrame(totals),
            "weeks": list(dict.fromkeys(s["request_week"])),
            "keys": list(dict.fromkeys(zip(s["sku_id"], s["region"]))), "labels": market_labels(d)}


DIFF_COLS = ["demand", "on_time", "early", "late", "unallocated", "backlog", "min_supply_exact_weeks"]


def supply_diff(sv: dict, base: str, alt: str) -> pd.DataFrame:
    """Key totals: alt − base, only the keys where some difference is not 0 (empty = 供給の差なし)."""
    t = sv["totals"]
    b = t[t["side"] == "base"].set_index(["sku_id", "region"])
    a = t[t["side"] == "alt"].set_index(["sku_id", "region"])
    rows = []
    for k in sv["keys"]:
        dif = {c: int(a.loc[k, c]) - int(b.loc[k, c]) for c in DIFF_COLS}
        if any(dif.values()):
            rows.append({"sku_id": k[0], "region": k[1], **dif})
    return pd.DataFrame(rows, columns=["sku_id", "region"] + DIFF_COLS)


def factory_view(d: str, base: str, alt: str) -> dict:
    fw = _csv(os.path.join(d, "factory_weekly.csv"), dtype={"week": str})
    inv = _csv(os.path.join(d, "inventory_by_week_sku.csv"), dtype={"week": str})
    age = _csv(os.path.join(d, "age_summary.csv"), dtype=str)
    pw_p = os.path.join(d, "planned_output_weeks.csv")
    pw = _csv(pw_p, dtype=str, keep_default_na=False) if os.path.exists(pw_p) else pd.DataFrame()
    idle = _csv(os.path.join(d, "factory_idle_weeks.csv"), dtype={"week": str})
    inv_sum = []
    for p, g in inv.groupby("product"):
        last = g[g["week_index"] == g["week_index"].max()]
        inv_sum.append({"product": p, "lot_weeks_base": int(g["lots_base"].sum()),
                        "lot_weeks_alt": int(g["lots_alt"].sum()), "max_base": int(g["lots_base"].max()),
                        "max_alt": int(g["lots_alt"].max()), "end_base": int(last["lots_base"].sum()),
                        "end_alt": int(last["lots_alt"].sum())})
    a = age[age["channel"] == "*"][["case", "product", "deliveries", "fifo_age_max", "over_max_age"]]
    labels = list(dict.fromkeys(fw["week"]))
    # 段 4 A3: the factories to choose on the screen. One factory per SKU -> the SKU alone (as before);
    # several -> 'SKU @ factory'. Comparisons made before have no factory column.
    choices = []
    if "factory" in fw.columns:
        n = fw.groupby("product")["factory"].nunique()
        for (p, f) in dict.fromkeys(zip(fw["product"], fw["factory"])):
            choices.append({"label": p if n[p] == 1 else f"{p} @ {f}", "sku": p, "factory": f})
    else:
        choices = [{"label": p, "sku": p, "factory": None} for p in dict.fromkeys(fw["product"])]
    engine = ("capacity_source" in fw.columns and (fw["capacity_source"] == "engine").all())
    return {"weekly": fw, "inventory": inv, "inventory_summary": pd.DataFrame(inv_sum), "age": a,
            "planned_output_weeks": pw, "idle": idle, "labels": labels, "choices": choices,
            "capacity_from_engine": bool(engine),
            "boundary_weeks": [labels[0]] + labels[-4:] if len(labels) >= 5 else labels,
            "note": "計画の上限は soft の値（良品＝floor(cap_soft × 歩留まり)）。物理の上限（hard）は計画には使わない"
                    + ("。上限はエンジンが使った値（操業カレンダーのシフトを含む）" if engine else
                       "。上限は capacity_plan.csv の値で、エンジンの値ではない（この比較の実行には能力の記録が無い）")}


def _fc_display(r: pd.Series) -> dict:
    """One row of fixed_cost_breakeven.csv for the screen. Blank weekly amount of a present row = 未設定;
    a case without a row = 対象外 (0). The P0 after cost is shown on the 合計 row only (rule 3)."""
    x = {k: ("" if _blank(v) else v) for k, v in r.items()}
    total = x.get("cost_item") == "合計"
    x["label"] = "合計" if total else (x.get("display_name") or x.get("cost_item") or "（固定費の表なし）")
    for c in ("base", "alt"):
        if total:
            continue
        has = not _blank(x.get(f"paid_start_{c}"))
        wa = x.get(f"weekly_amount_{c}", "")
        if not has:
            x[f"weekly_amount_{c}"] = NOT_APPLICABLE
            x[f"cost_{c}"] = 0
        elif wa == "":
            x[f"weekly_amount_{c}"] = UNSET
            x[f"cost_{c}"] = UNSET
        x[f"P_after_{c}"] = ""                  # the after-cost profit lives on the 合計 row only
    if not total:
        x["delta_P_after"] = ""
    return x


def money_view(d: str, base: str, alt: str, hide_fixed_cost: bool = False) -> dict:
    tot = _csv(os.path.join(d, "money_totals.csv"), dtype=str)
    rep = tot[tot["period"] == "report"]
    full = tot[tot["period"] == "full"]
    mb = _csv(os.path.join(d, "money_by_week_sku.csv"), dtype={"week": str})
    star = mb.groupby(["week_index", "week", "in_report"])[["profit_r2_base", "profit_r2_alt"]].sum().reset_index()
    r_ = star[star["in_report"].astype(str) == "True"].sort_values("week_index").copy()
    r_["cum_base"] = r_["profit_r2_base"].cumsum()
    r_["cum_alt"] = r_["profit_r2_alt"].cumsum()
    fc = _csv(os.path.join(d, "fixed_cost_breakeven.csv"), dtype=str, keep_default_na=False)
    rows = [_fc_display(r) for _, r in fc.iterrows()]
    names = {r["cost_item"]: r["label"] for r in rows if r.get("cost_item") not in ("", "合計")}
    for r in rows:                              # the assumption text of tool 2 names the items by code
        a = r.get("boundary_assumption", "")
        for code, label in names.items():
            a = a.replace(code, label)
        r["boundary_assumption"] = a
    if len(rows) == 1 and rows[0].get("cost_item") not in ("", "合計"):
        # one item: the after-cost profit of that item is the total -> a 合計 row the reader can rely on
        x = dict(rows[0])
        t = {k: "" for k in x}
        t.update({"cost_item": "合計", "label": "合計", "P0_base": x.get("P0_base"), "P0_alt": x.get("P0_alt"),
                  "delta_P0": x.get("delta_P0"), "valuation_status": x.get("valuation_status")})
        src = fc.iloc[0]
        for c in ("base", "alt"):
            t[f"cost_{c}"] = src[f"cost_{c}"] if src[f"cost_{c}"] != "" else (NOT_COMPUTED if x[f"weekly_amount_{c}"] == UNSET else 0)
            t[f"P_after_{c}"] = src[f"P_after_{c}"] if src[f"P_after_{c}"] != "" else (
                NOT_COMPUTED if x[f"weekly_amount_{c}"] == UNSET else x.get(f"P0_{c}"))
        t["delta_P_after"] = src["delta_P_after"] if src["delta_P_after"] != "" else NOT_COMPUTED
        rows.append(t)
    rows.sort(key=lambda r: 0 if r.get("cost_item") == "合計" else 1)          # the 合計 row on top
    unset = sorted({r["label"] for r in rows if r.get("cost_item") not in ("", "合計")
                    and UNSET in (r.get("weekly_amount_base"), r.get("weekly_amount_alt"))})
    no_table = any(r.get("cost_item", "") == "" for r in rows)
    ranking = PENDING if (unset or no_table or hide_fixed_cost) else "週額が設定済み：合計の行の控除後の差を見る"
    return {"report_by_product": rep, "full_by_product": full, "cumulative_report": r_,
            "fixed_cost": [] if hide_fixed_cost else [r for r in rows if r.get("cost_item")],
            "no_fixed_cost_table": no_table, "unset_costs": unset, "ranking": ranking,
            "hidden": hide_fixed_cost}


# ── 要点 ───────────────────────────────────────────────────────────────
def _inv_totals(fv: dict) -> tuple:
    s = fv["inventory_summary"]
    return int(s["lot_weeks_base"].sum()), int(s["lot_weeks_alt"].sum())


def _pct(b: int, a: int) -> str:
    return f"{(a - b) / b * 100:+.1f}%" if b else "—"


def inventory_text(fv: dict) -> str:
    """Lot-weeks per SKU and in total, base -> alt (difference in %)."""
    s = fv["inventory_summary"]
    parts = [f"{r.product} {r.lot_weeks_base:,} → {r.lot_weeks_alt:,}（{_pct(r.lot_weeks_base, r.lot_weeks_alt)}）"
             for r in s.itertuples()]
    lb, la = _inv_totals(fv)
    return "、".join(parts) + f"、計 {lb:,} → {la:,}（{_pct(lb, la)}）"


def summary(ws: str, base: str, alt: str, cmp: dict) -> List[dict]:
    """Five paragraphs of the comparison, built from numbers already on the screen. Never says which is better."""
    B, A = side_label("base", base), side_label("alt", alt)
    out = []
    # 違い
    ib, ia = case_inputs(ws, base), case_inputs(ws, alt)
    diffs = []
    eb = {(r["sku_id"], r["region"]): r for r in ib["entry_plan"]}
    ea = {(r["sku_id"], r["region"]): r for r in ia["entry_plan"]}
    for k in sorted(set(eb) | set(ea)):
        x, y = eb.get(k, {}), ea.get(k, {})
        for col, name in (("launch_week", "投入週"), ("steady_lots_per_week", "定常の lot／週"),
                          ("ramp_weeks", "立ち上がりの週数"), ("ramp_ratio", "立ち上がりの割合")):
            if x.get(col) != y.get(col):
                diffs.append(f"{k[0]}:{k[1]} の{name}（基準 {x.get(col, 'なし')}、相手 {y.get(col, 'なし')}）")
        for col, name in (("basis_note", "根拠"), ("promotion_note", "販促のメモ")):     # 到達点 5: the text now in the files
            if (x.get(col) or "") != (y.get(col) or ""):
                diffs.append(f"{k[0]}:{k[1]} の{name}（基準「{x.get(col) or 'なし'}」、相手「{y.get(col) or 'なし'}」）")
    late = notes_changed_after_compare(ws, base, alt)
    if late:
        diffs.append(f"（根拠の文は比べた後に変わった（数字は同じ）：{'、'.join(late)}）")
    cb = {(r["sku_id"], r["node"]): r for r in ib["capacity"]}
    ca = {(r["sku_id"], r["node"]): r for r in ia["capacity"]}
    for k in sorted(set(cb) | set(ca)):
        x, y = cb.get(k, {}), ca.get(k, {})
        if x.get("calendar") or y.get("calendar"):
            if (x.get("text"), x.get("shifts")) != (y.get("text"), y.get("shifts")):
                diffs.append(f"{k[0]} @ {k[1]} の計画の生産量（基準 {x.get('text')}；相手 {y.get('text')}）")
        elif (x.get("max_supply"), x.get("cap_soft")) != (y.get("max_supply"), y.get("cap_soft")):
            diffs.append(f"{k[0]} の計画の生産量（cap_soft 基準 {x.get('cap_soft')}、相手 {y.get('cap_soft')}；"
                         f"max_supply 基準 {x.get('max_supply')}、相手 {y.get('max_supply')}）")
    if (ib["policy"] or {}).get("short") != (ia["policy"] or {}).get("short") or \
            {k: v for k, v in (ib["policy"] or {}).items() if k.endswith("_file")} != \
            {k: v for k, v in (ia["policy"] or {}).items() if k.endswith("_file")}:
        pb, pa = ib["policy"] or {}, ia["policy"] or {}
        if pb.get("short") != pa.get("short"):
            diffs.append(f"供給の方針（基準 {pb.get('short', 'なし')}、相手 {pa.get('short', 'なし')}）")
        for col, name in (("allocation_file", "数量枠"), ("policy_file", "最低供給量")):
            if pb and pa and pb.get(col) != pa.get(col):
                diffs.append(f"{name}のファイル（基準 {os.path.basename(pb.get(col) or '') or 'なし'}、"
                             f"相手 {os.path.basename(pa.get(col) or '') or 'なし'}）")
    fb = {f["cost_item"]: f for f in ib["fixed_cost"]}
    fa = {f["cost_item"]: f for f in ia["fixed_cost"]}
    for k in sorted(set(fb) | set(fa)):
        x, y = fb.get(k), fa.get(k)
        name = (x or y)["label"]
        if x is None or y is None:
            diffs.append(f"{name}（{'相手' if x is None else '基準'}だけにある）")
        elif (x["paid"], x["weekly_amount"], x["count_outside_report"]) != (y["paid"], y["weekly_amount"],
                                                                            y["count_outside_report"]):
            diffs.append(f"{name}の有償の週（基準 {x['paid']}、相手 {y['paid']}）")
    out.append({"title": "違い", "text": ("2 案で違う入力：" + "、".join(diffs) + "。") if diffs else "入力の違いなし。"})
    # 工場
    fv = cmp["factory"]
    labels = fv["labels"]
    pw = fv["planned_output_weeks"]
    if len(pw) and "row" in pw.columns:
        per_value = pw[pw["row"] == "値ごと"]
        pw = pw[pw["row"] != "値ごと"]
    else:
        per_value = pd.DataFrame()
    parts = []
    multi = set(pw.groupby("product")["factory"].nunique().loc[lambda x: x > 1].index) if len(pw) else set()
    if len(pw):
        for (sku, fac), g in pw.groupby(["product", "factory"], sort=False):
            rb = g[g["case"] == base]
            ra = g[g["case"] == alt]
            if rb.empty or ra.empty:
                continue
            rb, ra = rb.iloc[0], ra.iloc[0]
            fw = fv["weekly"]
            fsel = (fw["factory"] == fac) if "factory" in fw.columns else True
            made = {c: int(fw[(fw["case"] == c) & (fw["product"] == sku) & fsel]["production_lots"].sum())
                    for c in (base, alt)}
            name = f"{sku} @ {fac}" if sku in multi else sku
            same = all(r.span_weeks == r.weeks_at_cap for r in (rb, ra))
            if not (rb.shippable_soft_values or ra.shippable_soft_values):
                t = f"{name}：計画の上限（soft）なし（設備の上限だけで動く）。"
            else:
                t = (f"{name}：上限（良品）基準 {rb.shippable_soft_values or 'なし'}・相手 {ra.shippable_soft_values or 'なし'} lot／週。"
                     f"上限ちょうど作った期間 基準 {rb.first_week_at_cap}〜{rb.last_week_at_cap}（{rb.span_weeks} 週）、"
                     f"相手 {ra.first_week_at_cap}〜{ra.last_week_at_cap}（{ra.span_weeks} 週）"
                     + ("、2 案とも途中に穴なし" if same else "") + "。")
            if rb.first_week_at_cap in labels and ra.first_week_at_cap in labels:
                dw = labels.index(rb.first_week_at_cap) - labels.index(ra.first_week_at_cap)
                if dw > 0:
                    t += f"相手は {dw} 週早く作り始めた。"
                elif dw < 0:
                    t += f"相手は {-dw} 週遅く作り始めた。"
            if made[base] != made[alt]:
                t += f"作った量 基準 {made[base]:,}・相手 {made[alt]:,} lot（差 {made[alt] - made[base]:+,}）。"
            for c, who in ((base, "基準"), (alt, "相手")):
                pv = (per_value[(per_value["case"] == c) & (per_value["product"] == sku) & (per_value["factory"] == fac)]
                      if len(per_value) else per_value)
                if len(pv):
                    t += f"{who}は週で上限が違う：" + "、".join(
                        f"上限 {r.shippable_soft_values} の {r.planned_weeks} 週（{r.planned_first_week}〜"
                        f"{r.planned_last_week}）のうち、ちょうど作った週 {r.weeks_at_cap}" for r in pv.itertuples()) + "。"
            parts.append(t)
    parts.append(f"在庫 lot・週（基準 → 相手）：{inventory_text(fv)}。")
    out.append({"title": "工場", "text": "".join(parts)})
    # 供給
    sv, sd = cmp["supply"], cmp["supply_diff"]
    t = sv["totals"]
    parts = []
    for r in sd.itertuples():
        ch = [f"{n} {getattr(r, c):+,}" for c, n in (("unallocated", "未配分"), ("backlog", "配分後の未充足"),
                                                      ("late", "遅配"), ("demand", "需要"), ("on_time", "当週"))
              if getattr(r, c)]
        if ch:
            parts.append(f"{key_text(sv, r.sku_id, r.region)} は 相手 − 基準 で " + "、".join(ch))
    if not parts:
        parts.append("鍵ごとの供給の差なし")
    full = []
    for sku in sorted(set(t["sku_id"])):
        g = t[t["sku_id"] == sku]
        if ((g["on_time"] + g["early"] + g["late"]) == g["demand"]).all():
            full.append(sku)
    text = "。".join(parts) + "。"
    if full:
        text += f"{'・'.join(full)} は 2 案とも需要が全部届いた。"
    for c in common_shortages(sv):
        text += c + "。"
    out.append({"title": "供給", "text": text})
    # お金
    mv = cmp["money"]
    rep = mv["report_by_product"]
    star = rep[rep["product"] == "*"].iloc[0]
    by = [f"{r.product} {fmt_yen(r.profit_r2_diff)}" for r in rep.itertuples() if r.product != "*"
          and abs(float(r.profit_r2_diff)) >= 0.5]
    fullr = mv["full_by_product"]
    fs = fullr[fullr["product"] == "*"]
    text = (f"報告期間の P0（固定費の前）基準 {fmt_yen(star.profit_r2_base)}・相手 {fmt_yen(star.profit_r2_alt)}、"
            f"差 {fmt_yen(star.profit_r2_diff)} 円" + (f"（内訳 {'、'.join(by)}）" if by else "") + "。")
    if len(fs):
        text += f"（参考：全計画期間の差 {fmt_yen(fs.iloc[0].profit_r2_diff)} 円）"
    out.append({"title": "お金", "text": text})
    # 判断に要るもの
    if mv["hidden"]:
        out.append({"title": "判断に要るもの", "text": f"費用の前提が変わった：{RECOMPARE}（境目は出さない）。"})
    elif mv["no_fixed_cost_table"]:
        out.append({"title": "判断に要るもの", "text": f"費用の前提が無い：採算の順位は{PENDING}。"})
    else:
        parts = []
        for r in mv["fixed_cost"]:
            if r.get("cost_item") == "合計":
                continue
            parts.append(_judgement(r))
        tot = [r for r in mv["fixed_cost"] if r.get("cost_item") == "合計"]
        if tot and tot[0].get("delta_P_after") not in ("", NOT_COMPUTED):
            parts.append(f"週額を入れた費用を引いた後の差（相手 − 基準）{fmt_yen(tot[0]['delta_P_after'])} 円")
        elif mv["unset_costs"]:
            parts.append(f"週額が未設定の費用があるので、控除後の利益は{NOT_COMPUTED}、採算の順位は{PENDING}")
        out.append({"title": "判断に要るもの", "text": "。".join(parts) + "。"})
    return out


def _judgement(r: dict) -> str:
    """One cost item in words, from its row of the fixed cost table (no new numbers)."""
    name = r["label"]
    dw = _num(r.get("delta_W"))
    f = _num(r.get("f_star_per_week"))
    unset = UNSET in (r.get("weekly_amount_base"), r.get("weekly_amount_alt"))
    assume = r.get("boundary_assumption", "")
    if dw == 0 and NOT_APPLICABLE not in (r.get("weekly_amount_base"), r.get("weekly_amount_alt")):
        return f"{name}：両案で同じ週数（{r.get('W_base')} 週）なので打ち消し合う"
    if not unset:
        cb, ca = _num(r.get("cost_base")) or 0, _num(r.get("cost_alt")) or 0
        return f"{name}：費用 基準 {fmt_yen(cb)}・相手 {fmt_yen(ca)} 円（差 {fmt_yen(ca - cb)} 円）"
    wtxt = f"有償の週 基準 {r.get('W_base')}・相手 {r.get('W_alt')} 週（差 {r.get('delta_W')}）"
    if f is not None and dw is not None:
        dp = _num(r.get("delta_P0_net")) if not _blank(r.get("delta_P0_net")) else _num(r.get("delta_P0"))
        if dw > 0 and (dp or 0) > 0:
            t = (f"{name}：週額は未設定。{wtxt}。週額が {fmt_yen(f)} 円／週より小さければ相手の試算利益が上、"
                 f"等しければ同額、大きければ基準が上")
        else:
            t = f"{name}：週額は未設定。{wtxt}。境目 {fmt_yen(f)} 円／週（{r.get('boundary', '')}）"
    else:
        t = f"{name}：週額は未設定。{wtxt}。{r.get('boundary', '')}"
    if assume:
        t += f"（{assume}）"
    return t


def common_shortages(sv: dict) -> List[str]:
    """Keys whose unallocated or backlog-after-allocation is the same (and > 0) in both cases."""
    t = sv["totals"]
    b = t[t["side"] == "base"].set_index(["sku_id", "region"])
    a = t[t["side"] == "alt"].set_index(["sku_id", "region"])
    out = []
    for k in sv["keys"]:
        for c, n in (("unallocated", "未配分"), ("backlog", "配分後の未充足")):
            if int(b.loc[k, c]) > 0 and int(b.loc[k, c]) == int(a.loc[k, c]):
                out.append(f"{key_text(sv, k[0], k[1])} の{n} {int(b.loc[k, c]):,} lot は 2 案に共通（比べている入力では変わらない）")
    return out


# ── ④ 読むときの注意 ─────────────────────────────────────────────────────
def notes(ws: str, base: Optional[str], alt: Optional[str], cmp: Optional[dict] = None) -> List[str]:
    out = []
    if base and alt:
        late = notes_changed_after_compare(ws, base, alt)
        if late:
            out.append(f"根拠の文は比べた後に変わった（数字は同じ。画面の文は今のファイルのもの）：{'、'.join(late)}")
    table = case_table(ws)
    for r in table["rows"]:
        if r["state"] == C.ST_CHANGED:
            out.append(f"{r['id']}（{r['name']}）：{RERUN}。{r['reason']}")
        elif r["state"] not in (C.ST_DONE,):
            line = f"{r['id']}（{r['name']}）：{r['state']}" + (f"。{r['reason']}" if r["reason"] else "")
            msg = (C.read_case(ws, r["id"]).get("run") or {}).get("message", "")
            if msg and r["state"] != C.ST_NOT_RUN:
                line += f"。理由：{message_gist(msg)}（ログ：{os.path.join(ws, r['id'], 'run', 'logs')}）"
            out.append(line)
        elif r["result"] and r["result"].get("unvalued_consolidated_lines"):
            out.append(f"{r['id']}：連結の法人の未評価の明細 {r['result']['unvalued_consolidated_lines']} 件")
    if not (base and alt):
        out.append("基準（◎）と相手（○）を選ぶと、2 案の比較を出す")
        return out
    cmp = cmp or comparison(ws, base, alt)
    if not cmp["available"]:
        out.append(f"比較 {base} → {alt}：{cmp['state']}。{cmp['reason']}（数字は出さない）")
        return out
    if cmp["cost_stale"]:
        out.append(f"比較 {base} → {alt}：{cmp['reason']}")
    mv = cmp["money"]
    if mv["unset_costs"]:
        out.append(f"週額が未設定の費用：{'、'.join(mv['unset_costs'])} → 控除後の利益は{NOT_COMPUTED}、"
                   f"採算の順位は{PENDING}（出すのは差と境目だけ）")
    elif mv["ranking"] == PENDING and not mv["hidden"]:
        out.append(f"費用の前提が無い → 採算の順位は{PENDING}")
    for r in mv["fixed_cost"]:
        if r.get("boundary_assumption"):
            out.append(f"{r['label']} の境目：{r['boundary_assumption']}")
    fv = cmp["factory"]
    out.append(f"在庫の保管費は金額に入っていない。在庫 lot・週（基準 {base} → 相手 {alt}）：{inventory_text(fv)}")
    for c in common_shortages(cmp["supply"]):
        out.append(c)
    out.append(f"{EDGE_WEEKS_TEXT}：{', '.join(fv['boundary_weeks'])}。ここで工場が計画値より少なく作るのは計画の端の効果")
    sv = cmp["supply"]
    t = sv["totals"]
    ex = t[t["min_supply_exact_weeks"] > 0]
    for x in ex.itertuples():
        cut = f"（うち削って最低ちょうど {x.cut_to_minimum_weeks} 週）" if x.cut_to_minimum_weeks else "（需要が最低供給量と同じ）"
        out.append(f"{x.case} {key_text(sv, x.sku_id, x.region)}：最低供給量ちょうどの週 {x.min_supply_exact_weeks}{cut}")
    out.append("突き合わせ：要求週別の供給の合計 ＝ Flow Check の表 2、SKU 別の試算利益の合計 ＝ 連結の値"
               + ("、金額の実行の出荷 ＝ 数量配分の結果" if sv["allocation"] else "") + "（道具 2 で確認済み）")
    out.append("どちらの案が上かは、この画面は言わない（差・境目・決められない理由まで）")
    return out
