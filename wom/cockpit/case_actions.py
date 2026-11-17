# -*- coding: utf-8 -*-
"""
wom/cockpit/case_actions.py — 画面の操作を受ける薄い層（画面に依存しない。Tk を import しない）
================================================================================================
RequestLetter_Cockpit_Stage3_Step3 B。段 1 の関数（`cases.py`・`case_runner.py`）を呼ぶ前に入力を確かめ、
**例外を投げずに、画面に出す文（何が・どこで・どう直すか）を返す**。実行と比較は裏のスレッドで 1 本ずつ行い、
段ごとの進み具合を queue に入れる（画面は `after()` で `Worker.poll()` を読む。裏のスレッドから Tk を触らない）。
"""
from __future__ import annotations

import os
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Callable, List, Optional

from wom.cockpit import cases as C
from wom.cockpit import case_runner as R

_WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")
RAISE_ITEM = "planned_output_raise"
RAISE_NAME = "増産の確保費"


@dataclass
class Result:
    ok: bool
    message: str
    data: dict = field(default_factory=dict)


def _fail(what: str, where: str, fix: str) -> Result:
    return Result(False, f"{what}（{where}）。直し方：{fix}")


def _week_ok(w: str) -> bool:
    import datetime
    if not _WEEK_RE.match(w or ""):
        return False
    y, n = w.split("-W")
    try:
        datetime.date.fromisocalendar(int(y), int(n), 1)
    except ValueError:
        return False
    return True


def _guard(ws: str, cid: str) -> Optional[Result]:
    try:
        st = C.status(ws, cid)
    except C.CaseError as e:
        return Result(False, str(e))
    if st["state"] == C.ST_RUNNING:
        return _fail(f"案 {cid} は実行中", "① 案の表", "実行が終わってから変える")
    return None


def _call(fn: Callable, *a, ok_message: str, **kw) -> Result:
    try:
        data = fn(*a, **kw)
    except C.CaseError as e:
        return Result(False, str(e))
    except (OSError, ValueError) as e:
        return Result(False, f"{type(e).__name__}: {e}")
    return Result(True, ok_message, {"result": data})


# ── 複製・入力 ──────────────────────────────────────────────────────────
def copy(ws: str, cid: str, name: str) -> Result:
    if not (name or "").strip():
        return _fail("名前が空です", "複製", "案の名前を入れる")
    g = _guard(ws, cid)
    if g:
        return g
    try:
        new = C.copy_case(ws, cid, name.strip())
    except C.CaseError as e:
        return Result(False, str(e))
    return Result(True, f"{cid} を複製して {new}（{name.strip()}）を作った。未実行", {"id": new})


def set_launch_week(ws: str, cid: str, sku: str, region: str, week: str) -> Result:
    g = _guard(ws, cid)
    if g:
        return g
    week = (week or "").strip()
    if not _week_ok(week):
        return _fail(f"投入週 {week!r} は週のラベルではない", f"② 投入の表 {sku}:{region}", "2027-W27 の形で入れる")
    keys = {(r["sku_id"], r["region"]) for r in _entry_plan(ws, cid)}
    if (sku, region) not in keys:
        return _fail(f"鍵 {sku}:{region} が投入の表に無い", f"案 {cid}", f"今ある鍵 {sorted(keys)} から選ぶ")
    return _call(C.set_launch_week, ws, cid, sku, region, week,
                 ok_message=f"{cid}：{sku}:{region} の投入週を {week} にした（需要を作り直した）。実行し直す")


def _entry_plan(ws: str, cid: str) -> List[dict]:
    from wom.cockpit import compare_view_model as V
    return V.case_inputs(ws, cid)["entry_plan"]


def set_planned_output(ws: str, cid: str, sku: str, node: Optional[str], value: str,
                       from_week: Optional[str] = None, to_week: Optional[str] = None) -> Result:
    g = _guard(ws, cid)
    if g:
        return g
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation:
        return _fail(f"cap_soft {value!r} は数ではない", f"② 計画の生産量 {sku}", "0 以上の数を入れる（例 12）")
    if d < 0:
        return _fail(f"cap_soft {value} は負", f"② 計画の生産量 {sku}", "0 以上の数を入れる")
    rngr = _range(from_week, to_week, f"② 計画の生産量 {sku}")
    if isinstance(rngr, Result):
        return rngr
    from_week, to_week = rngr
    rng = f"（{from_week}〜{to_week}）" if from_week else ""
    return _call(C.set_planned_output, ws, cid, sku, value, node, from_week, to_week,
                 ok_message=f"{cid}：{sku} の計画の生産量（cap_soft）を {value} にした{rng}。実行し直す")


def _range(from_week, to_week, where: str):
    """(from, to) with blanks as None (= all weeks), or a Result when the input is wrong (段 4 A5)."""
    a = (from_week or "").strip() or None
    b = (to_week or "").strip() or None
    if (a is None) != (b is None):
        return _fail("週の範囲の始まりと終わりの片方だけが入っている", where, "両方入れるか、両方空欄（全週）にする")
    for w in (a, b):
        if w is not None and not _week_ok(w):
            return _fail(f"週 {w!r} が週のラベルではない", where, "例 2028-W11 の形で入れる")
    if a and b < a:
        return _fail(f"終わり {b} が始まり {a} より前", where, "始まり ≦ 終わり にする")
    return a, b


def _hyp_where(sku: str, region: str) -> str:
    return f"② 需要の仮説 {sku}:{region}"


def preview_demand(ws: str, cid: str, sku: str, region: str, values: dict) -> Result:
    """到達点 5: the demand change of the key before anything is written (weeks, totals, and the reason when the
    rounding leaves it unchanged)."""
    vals = {k: v for k, v in values.items() if v not in (None, "")} if values else {}
    try:
        pv = C.preview_demand_change(ws, cid, sku, region, **vals)
    except C.CaseError as e:
        return Result(False, f"{e}（{_hyp_where(sku, region)}）")
    if pv["total_diff"] or pv["weeks"]:
        wk = pv["weeks"]
        span = f"{wk[0]['week']}〜{wk[-1]['week']} の {len(wk)} 週" if wk else ""
        msg = (f"需要の差 {pv['total_diff']:+d} lot（この鍵 {pv['total_before']:,} → {pv['total_after']:,}、"
               f"全体 {pv['all_before']:,} → {pv['all_after']:,}、{span}）")
        if wk and len({(w['before'], w['after']) for w in wk}) == 1:
            msg += f"。週ごと：各 {wk[0]['before']} → {wk[0]['after']}（{wk[0]['diff']:+d}）"
        elif wk:
            shown = "、".join(f"{w['week']} {w['before']}→{w['after']}" for w in wk[:8])
            msg += f"。週ごと：{shown}" + (f" ほか {len(wk) - 8} 週" if len(wk) > 8 else "")
    elif pv["numbers_changed"]:
        msg = f"需要の差 0 lot：{pv['reason']}"
    else:
        msg = "需要は変わらない（文の列だけの変更なら、実行し直しは要らない）"
    return Result(True, msg, {"preview": pv})


def set_demand_hypothesis(ws: str, cid: str, sku: str, region: str, values: dict) -> Result:
    g = _guard(ws, cid)
    if g:
        return g
    vals = {k: v for k, v in values.items() if v is not None}
    for k in ("steady", "ramp_weeks", "ramp_ratio", "launch_week"):
        if k in vals and str(vals[k]).strip() == "":
            return _fail(f"{k} が空欄", _hyp_where(sku, region), "値を入れるか、今の値のままにする")
    if "launch_week" in vals and not _week_ok(str(vals["launch_week"]).strip()):
        return _fail(f"投入週 {vals['launch_week']!r} が週のラベルではない", _hyp_where(sku, region), "例 2028-W01")
    try:
        r = C.set_demand_hypothesis(ws, cid, sku, region, **vals)
    except C.CaseError as e:
        return Result(False, str(e))
    what = "、".join(f"{c} {a or '（空）'} → {b or '（空）'}" for c, (a, b) in r["changes"].items())
    tail = "。実行し直す" if r["demand_regenerated"] else "。文の列だけなので計画の結果は使い回す（実行し直しは要らない）"
    return Result(True, f"{cid}：{sku}:{region} の需要の仮説を変えた（{what}）{tail}", {"result": r})


def has_calendar(ws: str, cid: str) -> bool:
    return os.path.exists(os.path.join(C.case_dir(ws, cid), "model", C.OPCAL))


def set_shifts(ws: str, cid: str, sku: str, node: str, value: str, from_week: Optional[str] = None,
               to_week: Optional[str] = None) -> Result:
    """段 4 A1: the shifts of the SKU x node in the operating calendar (1..21; closed weeks stay closed)."""
    g = _guard(ws, cid)
    if g:
        return g
    where = f"② シフト {sku} @ {node}"
    if not has_calendar(ws, cid):
        return _fail("このモデルには操業カレンダーが無い", where, "計画の生産量は「生産量…」で変える")
    v = str(value).strip()
    if not v.isdigit() or not 1 <= int(v) <= C.MAX_SHIFTS:
        return _fail(f"シフトの数 {value!r} が 1〜{C.MAX_SHIFTS} の整数ではない", where,
                     f"1〜{C.MAX_SHIFTS} の整数を入れる（0 ＝休業はここでは作らない）")
    rngr = _range(from_week, to_week, where)
    if isinstance(rngr, Result):
        return rngr
    from_week, to_week = rngr
    try:
        r = C.set_shifts(ws, cid, sku, node, int(v), from_week, to_week)
    except C.CaseError as e:
        return Result(False, str(e))
    rng = f"（{from_week}〜{to_week}）" if from_week else ""
    kept = f"。休業の {len(r['closed_kept'])} 週（{', '.join(r['closed_kept'])}）は休業のまま" if r["closed_kept"] else ""
    return Result(True, f"{cid}：{sku} @ {node} のシフトを {v} にした{rng}{kept}。実行し直す", {"result": r})


def set_policy(ws: str, cid: str, none: bool = False, allocation_file: str = None, policy_file: str = None,
               week_rule: str = None, knowledge_file: str = None, unallocated_note: str = None) -> Result:
    g = _guard(ws, cid)
    if g:
        return g
    for f, name in ((allocation_file, "数量枠"), (policy_file, "最低供給量"), (knowledge_file, "知識")):
        if f and not os.path.exists(f):
            return _fail(f"{name}のファイル {f} が無い", "② 供給の方針", "ファイルを選び直す")
    return _call(C.set_policy, ws, cid, none=none, allocation_file=allocation_file or None,
                 policy_file=policy_file or None, week_rule=week_rule or None,
                 knowledge_file=knowledge_file or None, unallocated_note=unallocated_note or None,
                 ok_message=f"{cid}：供給の方針を{'なし' if none else '変えた'}。実行し直す")


COST_KEYS = ["cost_item", "display_name", "entity", "paid_start_week", "paid_end_week", "weekly_amount", "currency",
             "count_outside_report", "note"]


def set_fixed_cost(ws: str, cid: str, rows: List[dict]) -> Result:
    """Rows of the cost premises (an empty list removes them). count_outside_report: bool or '0'/'1'."""
    g = _guard(ws, cid)
    if g:
        return g
    if not rows:
        return _call(C.set_fixed_cost, ws, cid, clear=True, ok_message=f"{cid}：費用の前提を消した。比較は並べ直す")
    out = []
    for i, r in enumerate(rows, start=1):
        where = f"② 費用の前提の {i} 行目"
        x = {k: str(r.get(k, "") if r.get(k) is not None else "").strip() for k in COST_KEYS}
        if not x["cost_item"]:
            return _fail("費目のコード（cost_item）が空", where, "英数字の名前を入れる（例 planned_output_raise）")
        for k, name in (("paid_start_week", "有償の最初の週"), ("paid_end_week", "有償の最後の週")):
            if not _week_ok(x[k]):
                return _fail(f"{name} {x[k]!r} は週のラベルではない", where, "2027-W01 の形で入れる")
        if x["paid_end_week"] < x["paid_start_week"]:
            return _fail("有償の最後の週が最初の週より前", where, "週を入れ直す")
        if x["weekly_amount"]:
            try:
                if Decimal(x["weekly_amount"]) < 0:
                    raise InvalidOperation
            except InvalidOperation:
                return _fail(f"週額 {x['weekly_amount']!r} は 0 以上の数ではない", where, "数を入れるか、空欄（未設定）にする")
        if not x["entity"] or not x["currency"]:
            return _fail("法人（entity）か通貨（currency）が空", where, "例 E_JP・JPY")
        v = r.get("count_outside_report")
        x["count_outside_report"] = "1" if v in (True, "1", 1) else ("" if v in (False, "", "0", 0, None) else str(v))
        out.append(x)
    return _call(C.set_fixed_cost, ws, cid, rows=out,
                 ok_message=f"{cid}：費用の前提を {len(out)} 行にした。案は「済み」のまま、比較は並べ直す")


# ── 増産の有償の週の手助け ─────────────────────────────────────────────
def _planned_values(ws: str, cid: str, engine: bool):
    """{(sku, factory, week): (value, kind)} -- the planned output per week.
    engine=True: the engine's cap_soft in the case's last run (run/capacity.csv; open weeks only).
    engine=False: from the inputs: the calendar's shifts where it has a row with shifts > 0, else capacity_plan's
    cap_soft."""
    import csv
    out = {}
    if engine:
        from wom.cockpit import compare_view_model as V
        e = V.engine_capacity(ws, cid)
        for r in e.to_dict("records"):
            k = (r["product"], r["factory"], r["week"])
            if str(r["closed"]) == "1":
                out[k] = ("", "closed")
            elif r["cap_soft"] != "":
                out[k] = (r["cap_soft"], "engine")
        return out
    mdir = os.path.join(C.case_dir(ws, cid), "model")
    with open(os.path.join(mdir, C.CAPACITY), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out[(r["sku_id"].strip(), r["node_name"].strip(), r["week"].strip())] = ((r.get("cap_soft") or "").strip(),
                                                                                    "cap_soft")
    cal = os.path.join(mdir, C.OPCAL)
    if os.path.exists(cal):
        with open(cal, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                k = (r["sku_id"].strip(), r["node_name"].strip(), r["week"].strip())
                sh = str(r.get("shifts", "")).strip()
                if sh == "0":
                    out[k] = ("", "closed")
                elif sh:
                    out[k] = (sh, "shifts")
    return out


KIND_TEXT = {"engine": "エンジンの計画値", "shifts": "シフト", "cap_soft": "cap_soft"}


def raised_ranges(ws: str, cid: str) -> List[dict]:
    """段 4: the week ranges where the case's planned output is higher than in its parent case (consecutive weeks,
    per SKU x factory). When both cases have run (済み), the engine's values (run/capacity.csv) are compared, so a
    change of cap_soft and a change of shifts are found the same way; otherwise the inputs (shifts where the
    calendar decides, else cap_soft). [{sku, factory, first, last, span, in_report, outside, cap_from, cap_to, kind}]"""
    from wom.cockpit import compare_view_model as V
    case = C.read_case(ws, cid)
    parent = case.get("parent")
    if not parent:
        return []
    engine = V.engine_capacity(ws, cid) is not None and V.engine_capacity(ws, parent) is not None
    mine, theirs = _planned_values(ws, cid, engine), _planned_values(ws, parent, engine)

    def num(v):
        try:
            return Decimal(v)
        except (InvalidOperation, ValueError, TypeError):
            return None
    rp = (C._read_json(os.path.join(ws, C.WORKSPACE_FILE)).get("report_period") or {})
    rs, re_ = rp.get("start") or "", rp.get("end") or ""
    out = []
    for sku, node in sorted({(k[0], k[1]) for k in mine}):
        wk = sorted(k[2] for k in mine if k[:2] == (sku, node))
        run = None
        found = []
        for w in wk + [None]:
            up, key = False, None
            if w is not None:
                (va, ka), (vb, kb) = mine[(sku, node, w)], theirs.get((sku, node, w), ("", ""))
                if "closed" in (ka, kb):
                    continue    # a closed week inside a raised range does not end it (the raise is paid there too)
                a, b = num(va), num(vb)
                up = ka == kb and a is not None and b is not None and a > b
                key = (vb, va, ka) if up else None
            if run and (not up or key != run["key"]):
                found.append(run)
                run = None
            if up:
                if run is None:
                    run = {"sku": sku, "factory": node, "first": w, "last": w,
                           "key": key, "cap_from": key[0], "cap_to": key[1], "kind": key[2]}
                run["last"] = w
        for r in found:
            inside = [w for w in wk if r["first"] <= w <= r["last"]]   # closed weeks inside included
            r["span"] = len(inside)
            r["in_report"] = sum(1 for w in inside if rs and rs <= w <= re_)
            r["closed_inside"] = [w for w in inside if mine[(sku, node, w)][1] == "closed"]
            r.pop("key")
            r["outside"] = r["span"] - r["in_report"]
            out.append(r)
    return out


def _at_cap_in(ws: str, cid: str, rng: dict) -> Optional[int]:
    """Weeks the factory actually made exactly its planned output inside the range (from a comparison's
    factory_weekly.csv that contains the case); None when no comparison has been made."""
    import pandas as pd
    cdir = os.path.join(ws, "compare")
    for d in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        p = os.path.join(cdir, d, "factory_weekly.csv")
        if cid not in d.split("__") or not os.path.exists(p):
            continue
        fw = pd.read_csv(p, dtype={"week": str})
        sel = (fw["case"] == cid) & (fw["product"] == rng["sku"])
        if "factory" in fw.columns:
            sel &= fw["factory"] == rng["factory"]
        g = fw[sel & (fw["week"] >= rng["first"]) & (fw["week"] <= rng["last"])]
        soft = pd.to_numeric(g["shippable_soft"], errors="coerce")
        return int((soft.notna() & (g["production_lots"] == soft)).sum())
    return None


def raise_week_candidates(ws: str, cid: str) -> List[dict]:
    """Candidates for the paid weeks of the raise cost. First (段 4) the week ranges where the planned output was
    raised versus the parent case (kind "raised", with the weeks the factory actually made exactly its planned
    output inside the range, when a comparison exists); then, from every comparison that contains the case, the
    first / last week the factory made exactly its planned output (kind "measured", planned_output_weeks.csv).
    Only candidates -- nothing is written until apply_raise_weeks."""
    import pandas as pd
    out = []
    for r in raised_ranges(ws, cid):
        at = _at_cap_in(ws, cid, r)
        out.append({"kind": "raised", "compare": "", "sku": r["sku"], "factory": r["factory"],
                    "cap": f"{r['cap_from']}→{r['cap_to']}（{KIND_TEXT[r['kind']]}）", "first": r["first"], "last": r["last"],
                    "span": r["span"], "in_report": r["in_report"], "outside": r["outside"],
                    "closed_inside": r.get("closed_inside", []),
                    "at_cap": at, "gaps": None if at is None else r["span"] - len(r.get("closed_inside", [])) - at})
    for d in sorted(os.listdir(os.path.join(ws, "compare"))) if os.path.isdir(os.path.join(ws, "compare")) else []:
        if cid not in d.split("__"):
            continue
        p = os.path.join(ws, "compare", d, "planned_output_weeks.csv")
        if not os.path.exists(p):
            continue
        t = pd.read_csv(p, dtype=str, keep_default_na=False)
        if "row" in t.columns:
            t = t[t["row"] != "値ごと"]
        for r in t[t["case"] == cid].itertuples():
            # a plan whose output differs by week mixes the values in its whole-case row (段 4 F4): not offered
            if r.first_week_at_cap and "," not in str(r.shippable_soft_values):
                out.append({"kind": "measured", "compare": d, "sku": r.product, "factory": r.factory, "cap": r.shippable_soft_values,
                            "first": r.first_week_at_cap, "last": r.last_week_at_cap, "span": int(r.span_weeks),
                            "in_report": int(r.span_weeks_in_report), "outside": int(r.span_weeks_outside_report),
                            "gaps": int(r.weeks_below_cap_inside_span or 0)})
    seen, uniq = set(), []
    for c in out:
        k = (c["sku"], c["first"], c["last"])
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq


def apply_raise_weeks(ws: str, cid: str, candidate: dict, entity: str, currency: str,
                      cost_item: str = RAISE_ITEM, display_name: str = RAISE_NAME) -> Result:
    """Put the candidate's weeks on the raise-cost row (count_outside_report = 1). A weekly amount already on the
    row is kept; a new row has none (未設定)."""
    from wom.cockpit import compare_view_model as V
    rows = [{"cost_item": f["cost_item"], "display_name": f["display_name"], "entity": f["entity"],
             "paid_start_week": f["paid_start_week"], "paid_end_week": f["paid_end_week"],
             "weekly_amount": f["weekly_amount_raw"], "currency": f["currency"],
             "count_outside_report": f["count_outside_report"], "note": f["note"]}
            for f in V.case_inputs(ws, cid)["fixed_cost"]]
    if candidate.get("kind") == "raised":
        note = (f"有償の週は {candidate['sku']} の計画の生産量を親の案より上げた週（{candidate['cap']}）")
    else:
        note = (f"有償の週は {candidate['sku']} の計画の生産量ちょうど作った最初の週〜最後の週（助走を含む、"
                f"比較 {candidate['compare']} の実測）")
    hit = [r for r in rows if r["cost_item"] == cost_item]
    if hit:
        hit[0].update({"paid_start_week": candidate["first"], "paid_end_week": candidate["last"],
                       "count_outside_report": True, "note": note,
                       "display_name": hit[0]["display_name"] or display_name})
    else:
        rows.append({"cost_item": cost_item, "display_name": display_name, "entity": entity,
                     "paid_start_week": candidate["first"], "paid_end_week": candidate["last"], "weekly_amount": "",
                     "currency": currency, "count_outside_report": True, "note": note})
    r = set_fixed_cost(ws, cid, rows)
    if r.ok:
        what = "上げた週" if candidate.get("kind") == "raised" else "助走を含む"
        r.message = (f"{cid}：{display_name}の有償の週を {candidate['first']}〜{candidate['last']}"
                     f"（{candidate['span']} 週、{what}）にした。比較は並べ直す")
    return r


def can_compare(ws: str, base: Optional[str], alt: Optional[str]) -> Result:
    if not (base and alt):
        return _fail("基準 ◎ と相手 ○ が選ばれていない", "① 案の表", "案を選んで「基準にする」「比べる相手にする」を押す")
    for cid in (base, alt):
        st = C.status(ws, cid)
        if st["state"] != C.ST_DONE:
            return _fail(f"案 {cid} は「{st['state']}」", "① 案の表", "その案を実行してから並べる")
    return Result(True, "")


# ── 裏の実行（1 本ずつ） ─────────────────────────────────────────────────
class Worker:
    """One job at a time in a background thread. Events go to a queue; the screen reads them with poll().
    Event: {"kind": "start"|"progress"|"done"|"error", "job": "run"|"compare", "case"/"pair", "message", ...}."""

    def __init__(self):
        self.q: "queue.Queue[dict]" = queue.Queue()
        self.thread: Optional[threading.Thread] = None
        self.job: Optional[dict] = None
        self.t0 = 0.0

    @property
    def busy(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def poll(self) -> List[dict]:
        out = []
        while True:
            try:
                out.append(self.q.get_nowait())
            except queue.Empty:
                return out

    def _start(self, job: dict, target: Callable) -> Result:
        if self.busy:
            return _fail("ほかの実行が動いている", "画面の下の進み具合", "終わるのを待つ")
        self.job, self.t0 = job, time.perf_counter()
        self.q.put({"kind": "start", **job, "message": f"{job['label']} を始めた"})
        self.thread = threading.Thread(target=target, daemon=True)
        self.thread.start()
        return Result(True, f"{job['label']} を始めた")

    def start_run(self, ws: str, cid: str, tool: Callable = None, stage_funcs: dict = None) -> Result:
        g = _guard(ws, cid)
        if g:
            return g
        job = {"job": "run", "case": cid, "label": f"{cid} の実行"}

        def target():
            try:
                rec = R.run_case(ws, cid, on_progress=lambda e: self.q.put(
                    {"kind": "progress", **job, **e, "elapsed": round(time.perf_counter() - self.t0, 1)}),
                    tool=tool, stage_funcs=stage_funcs)
                if rec["state"] == C.ST_DONE:
                    self.q.put({"kind": "done", **job, "state": rec["state"],
                                "message": f"{cid}：済み（{time.perf_counter() - self.t0:.0f} 秒）"})
                else:
                    from wom.cockpit.compare_view_model import message_gist
                    self.q.put({"kind": "error", **job, "state": rec["state"],
                                "message": f"{cid}：{rec['state']}。{rec['reason']}：{message_gist(rec.get('message'))}"})
            except Exception as e:      # noqa: BLE001 -- a message, not a crash of the screen
                self.q.put({"kind": "error", **job, "state": C.ST_STOPPED, "message": f"{cid}：{type(e).__name__}: {e}"})
        return self._start(job, target)

    def start_compare(self, ws: str, base: str, alt: str) -> Result:
        r = can_compare(ws, base, alt)
        if not r.ok:
            return r
        job = {"job": "compare", "pair": f"{base}__{alt}", "label": f"{base} → {alt} を並べる"}

        def target():
            try:
                R.compare_cases(ws, base, alt)
                self.q.put({"kind": "done", **job, "message": f"{base} → {alt}：並べた（{time.perf_counter() - self.t0:.0f} 秒）"})
            except R.StageStop as e:
                self.q.put({"kind": "error", **job, "state": e.state, "message": f"{base} → {alt}：{e.state}。{e.message}"})
            except Exception as e:      # noqa: BLE001
                self.q.put({"kind": "error", **job, "message": f"{base} → {alt}：{type(e).__name__}: {e}"})
        return self._start(job, target)

    def wait(self, timeout: float = None) -> None:
        if self.thread:
            self.thread.join(timeout)
