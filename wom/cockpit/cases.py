# -*- coding: utf-8 -*-
"""
wom/cockpit/cases.py — 事業計画の案の置き場と記録（画面に依存しない。Tk を import しない）
==========================================================================================
RequestLetter_Cockpit_Stage3_Step1_CasesAndRunner（2026-11-13）、設計書
`requests/Cockpit_Stage3_DesignMD_PlanCompareScreen_v0.1.md` §2.2・§3。

置き場：

    <作業>/
      workspace.json       元のモデル、作った時刻、Git の SHA、需要の期間、報告期間、年齢の上限
      <案の ID>/            C01, C02, …（連番）
        case.json          案の名前、親の案、入力の要点、入力のファイルの hash、実行の記録
        model/             モデルの写し（投入の表・需要・能力 …）
        inputs/            数量枠・最低供給量・知識・費用の前提（使う案だけ）
        run/               計画・PPC・Value Chain・年齢の検査・Flow Check の出力（case_runner）
        udp/               上位 Demand Plan の出力（方針ありの案だけ、case_runner）
      compare/<基準>__<相手>/   道具 2 の出力（case_runner.compare_cases）

規則：
- 元のモデルには書かない（作業を作るときに写すだけ）。
- 投入の表を変えたら、そのたびに道具 1（tools.gen_demand_from_entry_plan）で需要を作り直す
  （需要 CSV を直接書き換えない）。
- 実行の状態は記録から導く：実行の記録なし＝未実行、実行の記録の hash と今の入力の hash が違う＝
  入力が変わった（実行し直す）。入力を変えると hash が変わるので状態は「入力が変わった」になり、
  元に戻すと「済み」に戻る（実行の記録は消さない）。
- 記録の中のパスは、作業のフォルダからの相対パス（作業ごと別の場所に写しても同じ表が出る）。
- 止めるときは CaseError（ファイル・値・直し方を出す。黙った既定値を作らない）。
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

WORKSPACE_FILE = "workspace.json"
CASE_FILE = "case.json"
ENTRY_PLAN = "market_entry_plan.csv"
NOTE_COLS = ("basis_note", "promotion_note")   # 到達点 5: text only -- not part of the run's inputs
HYPOTHESIS_COLS = {"launch_week": "launch_week", "steady": "steady_lots_per_week", "ramp_weeks": "ramp_weeks",
                   "ramp_ratio": "ramp_ratio", "basis_note": "basis_note", "promotion_note": "promotion_note"}
CAPACITY = "capacity_plan.csv"
OPCAL = "operating_calendar.csv"               # 段 4 A1: the shift plan (the planned output where it has rows)
MAX_SHIFTS = 21                                # 3 shifts x 7 days (wom.model.plan_node.MAX_SHIFTS)
DEMAND = "demand_forecast.csv"
FIXED_COST_FILE = "fixed_cost.csv"            # inputs/ ; only the comparison reads it
FIXED_COST_COLS = ["cost_item", "entity", "paid_start_week", "paid_end_week", "weekly_amount",
                   "currency", "note"]
COUNT_OUTSIDE_COL = "count_outside_report"    # optional (段 2): 1 = the paid weeks include the warm-up weeks
DISPLAY_COL = "display_name"                  # optional (段 3): the name shown on the screen (blank = cost_item)
OPTIONAL_COST_COLS = [COUNT_OUTSIDE_COL, DISPLAY_COL]
POLICY_FILES = ("allocation_file", "policy_file", "knowledge_file")
_ID_RE = re.compile(r"^C(\d{2,})$")
_WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")

# run states (status())
ST_NOT_RUN = "未実行"
ST_RUNNING = "実行中"
ST_DONE = "済み"
ST_STOPPED = "止まった"
ST_CONFLICT = "衝突"
ST_SHORT = "未達"
ST_INCONSISTENT = "不整合"
ST_CHANGED = "入力が変わった"


class CaseError(ValueError):
    """The case cannot be created / changed / read (the message says where and how to fix it)."""


# ── 小道具 ─────────────────────────────────────────────────────────────
def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _git_head() -> Optional[str]:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                              text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _read_json(path: str) -> dict:
    if not os.path.exists(path):
        raise CaseError(f"{path} がありません")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, body: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _read_rows(path: str):
    """(fieldnames, rows as list of dict of str, line terminator) -- keeps the values as text."""
    if not os.path.exists(path):
        raise CaseError(f"{path} がありません")
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8-sig")
    term = "\r\n" if "\r\n" in text else "\n"
    rd = csv.DictReader(io.StringIO(text, newline=""))
    rows = [dict(r) for r in rd]
    return list(rd.fieldnames or []), rows, term, raw.startswith(b"\xef\xbb\xbf")


def _write_rows(path: str, fields, rows, term: str, bom: bool) -> None:
    buf = io.StringIO(newline="")
    wr = csv.DictWriter(buf, fieldnames=fields, lineterminator=term)
    wr.writeheader()
    for r in rows:
        wr.writerow({k: r.get(k, "") for k in fields})
    data = buf.getvalue().encode("utf-8")
    with open(path, "wb") as f:
        f.write((b"\xef\xbb\xbf" if bom else b"") + data)


def _num_text(v, what: str) -> str:
    """A non-negative number as the text written to the CSV (integers without '.0')."""
    try:
        d = Decimal(str(v).strip())
    except InvalidOperation:
        raise CaseError(f"{what}={v!r} は数値ではありません")
    if d < 0:
        raise CaseError(f"{what}={v!r} は負です。0 以上にしてください")
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), "f")


def _check_week(label: str, what: str) -> str:
    label = str(label).strip()
    if not _WEEK_RE.match(label):
        raise CaseError(f"{what}={label!r} は週のラベルではありません（例 2027-W27）")
    y, w = label.split("-W")
    try:
        datetime.date.fromisocalendar(int(y), int(w), 1)
    except ValueError:
        raise CaseError(f"{what}={label!r} は存在しない週です")
    return label


# ── 作業 ───────────────────────────────────────────────────────────────
def _demand_period(model_dir: str):
    p = os.path.join(model_dir, DEMAND)
    _f, rows, _t, _b = _read_rows(p)
    weeks = sorted({r["week"].strip() for r in rows})
    if not weeks:
        raise CaseError(f"{p}: 行がありません（需要の期間が決まりません）")
    return weeks[0], weeks[-1]


def _report_start(model_dir: str) -> str:
    p = os.path.join(model_dir, "vc_config.csv")
    if os.path.exists(p):
        _f, rows, _t, _b = _read_rows(p)
        for r in rows:
            if r.get("key", "").strip() == "report_start" and r.get("value", "").strip():
                return r["value"].strip()
    raise CaseError(f"{p} に report_start がありません。直し方：vc_config.csv に report_start を書く"
                    "（報告期間の始まり。黙った既定値は作らない）")


def create_workspace(ws_dir: str, model_dir: str, *, max_age_weeks: int, first_name: str = "基準") -> str:
    """Copy the model into <ws_dir>/C01/model and write workspace.json. Returns the first case id."""
    model_dir = os.path.abspath(model_dir)
    ws_dir = os.path.abspath(ws_dir)
    if not os.path.exists(os.path.join(model_dir, "sc_tree_master.csv")):
        raise CaseError(f"{model_dir} はモデルのフォルダではありません（sc_tree_master.csv がありません）")
    if os.path.exists(ws_dir) and os.listdir(ws_dir):
        raise CaseError(f"{ws_dir} は空ではありません。直し方：別の名前にするか、中を片付ける")
    if os.path.commonpath([model_dir, ws_dir]) == model_dir:
        raise CaseError(f"作業の置き場 {ws_dir} が元のモデル {model_dir} の中にあります")
    if int(max_age_weeks) <= 0:
        raise CaseError(f"max_age_weeks={max_age_weeks} は正の整数にしてください（年齢の検査の上限）")
    start, end = _demand_period(model_dir)
    report_start = _report_start(model_dir)
    os.makedirs(ws_dir, exist_ok=True)
    before = {f: _sha256_file(os.path.join(model_dir, f)) for f in sorted(os.listdir(model_dir))
              if os.path.isfile(os.path.join(model_dir, f))}
    ws = {"source_model": model_dir, "created": _now(), "git_sha": _git_head(),
          "demand_period": {"start": start, "end": end},
          "report_period": {"start": report_start, "end": end},
          "max_age_weeks": int(max_age_weeks),
          "source_model_sha256": before}
    _write_json(os.path.join(ws_dir, WORKSPACE_FILE), ws)
    cid = "C01"
    cdir = os.path.join(ws_dir, cid)
    os.makedirs(cdir)
    shutil.copytree(model_dir, os.path.join(cdir, "model"),
                    ignore=shutil.ignore_patterns("__pycache__", "output"))
    os.makedirs(os.path.join(cdir, "inputs"))
    case = {"id": cid, "name": first_name, "parent": None, "created": _now(),
            "inputs": {"policy": None, "fixed_cost": None}, "changes": [], "run": None}
    _write_json(os.path.join(cdir, CASE_FILE), case)
    return cid


def open_workspace(ws_dir: str) -> dict:
    ws = _read_json(os.path.join(ws_dir, WORKSPACE_FILE))
    ws["dir"] = os.path.abspath(ws_dir)
    return ws


def case_ids(ws_dir: str) -> List[str]:
    out = []
    for n in os.listdir(ws_dir):
        m = _ID_RE.match(n)
        if m and os.path.exists(os.path.join(ws_dir, n, CASE_FILE)):
            out.append((int(m.group(1)), n))
    return [n for _i, n in sorted(out)]


def case_dir(ws_dir: str, cid: str) -> str:
    d = os.path.join(ws_dir, cid)
    if not os.path.exists(os.path.join(d, CASE_FILE)):
        raise CaseError(f"案 {cid} がありません（{d}）。今ある案：{case_ids(ws_dir)}")
    return d


def read_case(ws_dir: str, cid: str) -> dict:
    return _read_json(os.path.join(case_dir(ws_dir, cid), CASE_FILE))


def write_case(ws_dir: str, cid: str, case: dict) -> None:
    _write_json(os.path.join(case_dir(ws_dir, cid), CASE_FILE), case)


def copy_case(ws_dir: str, parent: str, name: str) -> str:
    """Copy model/ and inputs/ of `parent` (not run/ or udp/) into the next id."""
    pdir = case_dir(ws_dir, parent)
    ids = case_ids(ws_dir)
    nxt = max(int(_ID_RE.match(i).group(1)) for i in ids) + 1
    cid = f"C{nxt:02d}"
    cdir = os.path.join(ws_dir, cid)
    os.makedirs(cdir)
    shutil.copytree(os.path.join(pdir, "model"), os.path.join(cdir, "model"))
    shutil.copytree(os.path.join(pdir, "inputs"), os.path.join(cdir, "inputs"))
    pc = read_case(ws_dir, parent)
    case = {"id": cid, "name": name, "parent": parent, "created": _now(),
            "inputs": json.loads(json.dumps(pc.get("inputs") or {})), "changes": [], "run": None}
    _write_json(os.path.join(cdir, CASE_FILE), case)
    return cid


def _record_change(ws_dir: str, cid: str, what: str, detail: dict) -> dict:
    case = read_case(ws_dir, cid)
    case.setdefault("changes", []).append({"at": _now(), "what": what, **detail})
    write_case(ws_dir, cid, case)
    return case


def _guard_not_running(ws_dir: str, cid: str) -> None:
    if (read_case(ws_dir, cid).get("run") or {}).get("state") == ST_RUNNING:
        raise CaseError(f"案 {cid} は実行中です。終わってから変えてください")


# ── 入力を変える ─────────────────────────────────────────────────────────
def regenerate_demand(ws_dir: str, cid: str) -> dict:
    """Tool 1 on the case's entry plan (the only way the demand CSV is written)."""
    import sys
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from tools.gen_demand_from_entry_plan import run as gen_run, EntryPlanError
    ws = open_workspace(ws_dir)
    mdir = os.path.join(case_dir(ws_dir, cid), "model")
    try:
        return gen_run(mdir, ws["demand_period"]["start"], ws["demand_period"]["end"])
    except EntryPlanError as e:
        raise CaseError(f"案 {cid} の需要を作れません（道具 1）：{e}")


def set_entry_plan(ws_dir: str, cid: str, plan_file: str) -> dict:
    """Place an entry plan file (market_entry_plan.csv) in the case, then regenerate the demand."""
    _guard_not_running(ws_dir, cid)
    if not os.path.exists(plan_file):
        raise CaseError(f"{plan_file} がありません")
    mdir = os.path.join(case_dir(ws_dir, cid), "model")
    dst = os.path.join(mdir, ENTRY_PLAN)
    old = open(dst, "rb").read() if os.path.exists(dst) else None
    shutil.copyfile(plan_file, dst)
    try:
        log = regenerate_demand(ws_dir, cid)
    except CaseError:
        if old is None:
            os.remove(dst)
        else:
            open(dst, "wb").write(old)
        raise
    _record_change(ws_dir, cid, "entry_plan", {"file": os.path.abspath(plan_file),
                                                "sha256": _sha256_file(dst), "total_lots": log["total_lots"]})
    return log


def set_launch_week(ws_dir: str, cid: str, sku: str, region: str, week: str) -> dict:
    """(a) one key's launch_week in the entry plan; regenerate the demand."""
    _guard_not_running(ws_dir, cid)
    week = _check_week(week, "launch_week")
    p = os.path.join(case_dir(ws_dir, cid), "model", ENTRY_PLAN)
    fields, rows, term, bom = _read_rows(p)
    hit = [r for r in rows if r.get("sku_id", "").strip() == sku and r.get("region", "").strip() == region]
    if len(hit) != 1:
        keys = sorted(f"{r.get('sku_id')}:{r.get('region')}" for r in rows)
        raise CaseError(f"{p}: 鍵 {sku}:{region} の行が {len(hit)} 行です（1 行のはず）。今ある鍵：{keys}")
    old_bytes = open(p, "rb").read()
    old = hit[0]["launch_week"]
    hit[0]["launch_week"] = week
    _write_rows(p, fields, rows, term, bom)
    try:
        log = regenerate_demand(ws_dir, cid)
    except CaseError:
        open(p, "wb").write(old_bytes)
        regenerate_demand(ws_dir, cid)
        raise
    _record_change(ws_dir, cid, "launch_week", {"key": f"{sku}:{region}", "from": old, "to": week,
                                                 "total_lots": log["total_lots"]})
    return log


def _hypothesis_values(changes: dict) -> dict:
    """Checked text values per entry-plan column (到達点 5). steady / ramp_weeks: integers >= 0; ramp_ratio: a
    number >= 0 (kept as written, e.g. '1.0'); launch_week: a week label; the two notes: any text."""
    out = {}
    for k, v in changes.items():
        if v is None:
            continue
        if k not in HYPOTHESIS_COLS:
            raise CaseError(f"{k} は需要の仮説の列ではありません（{sorted(HYPOTHESIS_COLS)}）")
        col = HYPOTHESIS_COLS[k]
        t = str(v).strip()
        if k in ("steady", "ramp_weeks"):
            try:
                d = Decimal(t)
            except InvalidOperation:
                raise CaseError(f"{col}={v!r} は数ではありません（0 以上の整数）")
            if d < 0 or d != d.to_integral_value():
                raise CaseError(f"{col}={v!r} は 0 以上の整数にしてください")
            t = str(int(d))
        elif k == "ramp_ratio":
            try:
                d = Decimal(t)
            except InvalidOperation:
                raise CaseError(f"ramp_ratio={v!r} は数ではありません（0 以上の数、例 1.0）")
            if d < 0 or not d.is_finite():
                raise CaseError(f"ramp_ratio={v!r} は 0 以上の数にしてください")
        elif k == "launch_week":
            t = _check_week(t, "launch_week")
        out[col] = t
    return out


def _entry_row(p: str, rows, sku: str, region: str) -> dict:
    hit = [r for r in rows if r.get("sku_id", "").strip() == sku and r.get("region", "").strip() == region]
    if len(hit) != 1:
        keys = sorted(f"{r.get('sku_id')}:{r.get('region')}" for r in rows)
        raise CaseError(f"{p}: 鍵 {sku}:{region} の行が {len(hit)} 行です（1 行のはず）。今ある鍵：{keys}")
    return hit[0]


def _same_value(col: str, a: str, b: str) -> bool:
    if col in NOTE_COLS or col == "launch_week":
        return (a or "").strip() == (b or "").strip()
    try:
        return Decimal((a or "").strip()) == Decimal((b or "").strip())
    except InvalidOperation:
        return (a or "").strip() == (b or "").strip()


def set_demand_hypothesis(ws_dir: str, cid: str, sku: str, region: str, **changes) -> dict:
    """到達点 5: change only the given columns of one key of the entry plan (launch_week, steady, ramp_weeks,
    ramp_ratio, basis_note, promotion_note). When a number (or the launch week) changes the demand is
    regenerated; a change of the two text columns only does not touch the demand, and the case stays 済み
    (the text columns are not part of the run's inputs, see input_hashes). Stops when the key is not one row,
    a value is wrong, or nothing changes. The change (before / after) is recorded in case.json."""
    _guard_not_running(ws_dir, cid)
    vals = _hypothesis_values(changes)
    if not vals:
        raise CaseError("変える値がありません（launch_week・steady・ramp_weeks・ramp_ratio・basis_note・promotion_note）")
    p = os.path.join(case_dir(ws_dir, cid), "model", ENTRY_PLAN)
    fields, rows, term, bom = _read_rows(p)
    for col in vals:
        if col not in fields:
            raise CaseError(f"{p}: 列 {col} がありません")
    row = _entry_row(p, rows, sku, region)
    diff = {col: [row.get(col, ""), v] for col, v in vals.items() if not _same_value(col, row.get(col, ""), v)}
    if not diff:
        raise CaseError(f"鍵 {sku}:{region} の値は今と同じです（変える値がありません）")
    numbers = [c for c in diff if c not in NOTE_COLS]
    old_bytes = open(p, "rb").read()
    for col, (_a, b) in diff.items():
        row[col] = b
    _write_rows(p, fields, rows, term, bom)
    log = None
    if numbers:
        try:
            log = regenerate_demand(ws_dir, cid)
        except CaseError:
            open(p, "wb").write(old_bytes)
            regenerate_demand(ws_dir, cid)
            raise
    _record_change(ws_dir, cid, "demand_hypothesis",
                   {"key": f"{sku}:{region}", "changes": diff, "demand_regenerated": bool(numbers),
                    **({"total_lots": log["total_lots"]} if log else {})})
    return {"key": f"{sku}:{region}", "changes": diff, "demand_regenerated": bool(numbers),
            "total_lots": log["total_lots"] if log else None}


def preview_demand_change(ws_dir: str, cid: str, sku: str, region: str, **changes) -> dict:
    """到達点 5: the demand of the key after the change, without writing anything (tool 1's own functions).
    {"weeks": [{"week", "before", "after", "diff"}] (weeks whose demand changes), "total_before", "total_after",
    "total_diff" (the key), "all_before", "all_after" (every key), "numbers_changed", "reason"}. With total_diff 0 after a change of the numbers, "reason" says why
    (e.g. rounding: '3 × 0.6 ＝ 1.8 → 2')."""
    import sys
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from tools import gen_demand_from_entry_plan as G
    vals = _hypothesis_values(changes)
    ws = open_workspace(ws_dir)
    mdir = os.path.join(case_dir(ws_dir, cid), "model")
    try:
        rows, _raw, path = G.read_plan(mdir)
    except G.EntryPlanError as e:
        raise CaseError(str(e))
    hit = [r for r in rows if r["sku_id"] == sku and r["region"] == region]
    if len(hit) != 1:
        raise CaseError(f"鍵 {sku}:{region} の行が {len(hit)} 行です（1 行のはず）")
    old = hit[0]
    new = dict(old)
    if "launch_week" in vals:
        new["launch_week"] = vals["launch_week"]
    if "steady_lots_per_week" in vals:
        new["steady"] = int(vals["steady_lots_per_week"])
    if "ramp_weeks" in vals:
        new["ramp_weeks"] = int(vals["ramp_weeks"])
    if "ramp_ratio" in vals:
        new["ramp_ratio"] = Decimal(vals["ramp_ratio"])
    weeks = G.week_range(ws["demand_period"]["start"], ws["demand_period"]["end"])
    try:
        before = {(s, g, w): q for s, g, w, q in G.generate(rows, weeks, path)}
        after = {(s, g, w): q for s, g, w, q in G.generate([new if r is old else r for r in rows], weeks, path)}
    except G.EntryPlanError as e:
        raise CaseError(str(e))
    wk = [{"week": w, "before": before[(sku, region, w)], "after": after[(sku, region, w)],
           "diff": after[(sku, region, w)] - before[(sku, region, w)]} for w in weeks
          if after[(sku, region, w)] != before[(sku, region, w)]]
    tb = sum(v for (s, g, _w), v in before.items() if (s, g) == (sku, region))
    ta = sum(v for (s, g, _w), v in after.items() if (s, g) == (sku, region))
    ab, aa = sum(before.values()), sum(after.values())
    numbers = any(new[k] != old[k] for k in ("launch_week", "steady", "ramp_weeks", "ramp_ratio"))
    reason = ""
    if numbers and ta == tb and not wk:
        parts = []
        if new["ramp_ratio"] != old["ramp_ratio"] or new["steady"] != old["steady"]:
            for lab, r in (("今", old), ("変えた後", new)):
                x = Decimal(r["steady"]) * r["ramp_ratio"]
                parts.append(f"{lab} {r['steady']} × {r['ramp_ratio']} ＝ {x.normalize():f} → {G.round_half_up(x)}")
        reason = "四捨五入で需要は変わらない（立ち上がりの週：" + "、".join(parts) + "）" if parts else             "需要は変わらない（週別の需要が今と同じ）"
    elif numbers and ta == tb:
        reason = "合計は同じ（週の配置だけが変わる）"
    return {"key": f"{sku}:{region}", "weeks": wk, "total_before": tb, "total_after": ta, "total_diff": ta - tb,
            "all_before": ab, "all_after": aa, "numbers_changed": numbers, "reason": reason}


def entry_notes(ws_dir: str, cid: str) -> Dict[str, dict]:
    """{'sku:region': {'basis_note': …, 'promotion_note': …}} of the case's entry plan (empty without one)."""
    p = os.path.join(case_dir(ws_dir, cid), "model", ENTRY_PLAN)
    if not os.path.exists(p):
        return {}
    _f, rows, _t, _b = _read_rows(p)
    return {f"{r.get('sku_id', '').strip()}:{r.get('region', '').strip()}": {c: (r.get(c) or "").strip()
                                                                           for c in NOTE_COLS} for r in rows}


def _entry_plan_digest(path: str) -> str:
    """The entry plan's hash without the text columns (basis_note, promotion_note): changing only the text
    does not change the run's inputs (到達点 5 A0-3). Prefixed so it is never mistaken for a file sha256."""
    _f, rows, _t, _b = _read_rows(path)
    fields = [c for c in _f if c not in NOTE_COLS]
    body = json.dumps([fields] + [[(r.get(c) or "") for c in fields] for r in rows], ensure_ascii=False)
    return "nonote:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _capacity_rows_for(p: str, rows, sku: str, node: Optional[str]):
    mine = [r for r in rows if r.get("sku_id", "").strip() == sku]
    if not mine:
        raise CaseError(f"{p}: SKU {sku} の行がありません。今ある SKU：{sorted({r.get('sku_id') for r in rows})}")
    nodes = sorted({r.get("node_name", "").strip() for r in mine})
    if node is None:
        if len(nodes) != 1:
            raise CaseError(f"{p}: SKU {sku} の工場が {nodes} の {len(nodes)} つです。直し方：工場を指定する")
        node = nodes[0]
    sel = [r for r in mine if r.get("node_name", "").strip() == node]
    if not sel:
        raise CaseError(f"{p}: SKU {sku}・工場 {node} の行がありません（今ある工場：{nodes}）")
    return sel, node


def set_planned_output(ws_dir: str, cid: str, sku: str, cap_soft, node: Optional[str] = None,
                       from_week: Optional[str] = None, to_week: Optional[str] = None) -> dict:
    """(b) the SKU's planned output: cap_soft of every row of the SKU's factory (warm-up rows included), or only
    of the rows from_week..to_week (both ends included; 段 4). The rows outside the range are not touched.
    Stops if the value exceeds max_supply on a changed row, or if from_week / to_week is not a week of the rows."""
    _guard_not_running(ws_dir, cid)
    p = os.path.join(case_dir(ws_dir, cid), "model", CAPACITY)
    fields, rows, term, bom = _read_rows(p)
    val = _num_text(cap_soft, "cap_soft")
    sel, node = _capacity_rows_for(p, rows, sku, node)
    sel, rng = _select_weeks(p, sel, sku, node, from_week, to_week)
    gov = calendar_weeks(ws_dir, cid, sku, node) & {r["week"].strip() for r in sel}
    if gov:
        raise CaseError(f"SKU {sku}・工場 {node} の計画値は操業カレンダーのシフトで決まります（{len(gov)} 週、"
                        f"例 {sorted(gov)[0]}。cap_soft は計画の読み込みでシフトから作り直される）。"
                        "直し方：「シフト…」（CLI は set … shifts）でシフトの数を変える")
    for c in ("max_supply", "cap_soft"):
        if c not in fields:
            raise CaseError(f"{p}: 列 {c} がありません")
    over = []
    for r in sel:
        ms = r["max_supply"].strip()
        if ms != "" and Decimal(val) > Decimal(ms):
            over.append(f"{r['week']}（max_supply {ms}）")
    if over:
        raise CaseError(f"{p}: SKU {sku}・工場 {node} の cap_soft={val} が max_supply を超える週があります："
                        f"{over[:5]}{' …' if len(over) > 5 else ''}（{len(over)} 週）。直し方：cap_soft を "
                        "max_supply 以下にするか、max_supply と cap_soft の組を変える")
    old = sorted({r["cap_soft"] for r in sel})
    for r in sel:
        r["cap_soft"] = val
    _write_rows(p, fields, rows, term, bom)
    _record_change(ws_dir, cid, "planned_output", {"sku": sku, "node": node, "cap_soft_from": old,
                                                    "cap_soft_to": val, "rows": len(sel),
                                                    "weeks": list(rng) if rng else "all"})
    return {"sku": sku, "node": node, "rows": len(sel), "cap_soft": val, "weeks": list(rng) if rng else "all"}


def _select_weeks(p: str, sel: List[dict], sku: str, node: str, from_week, to_week):
    """The rows of from_week..to_week (both ends included); all rows when both are omitted. Stops if only one end is
    given, an end is not a week of the rows, or the range is reversed."""
    if (from_week is None) != (to_week is None):
        raise CaseError("週の範囲は from_week と to_week の両方を指定してください（省略すると全週）")
    if from_week is None:
        return sel, None
    a, b = _check_week(from_week, "from_week"), _check_week(to_week, "to_week")
    weeks = sorted({r["week"].strip() for r in sel})
    missing = [w for w in (a, b) if w not in weeks]
    if missing:
        raise CaseError(f"{p}: SKU {sku}・工場 {node} の行に週 {missing} がありません（行の週は {weeks[0]}〜{weeks[-1]}）。"
                        "直し方：行のある週を指定する")
    if b < a:
        raise CaseError(f"週の範囲の終わり {b} が始まり {a} より前です")
    return [r for r in sel if a <= r["week"].strip() <= b], (a, b)


def calendar_weeks(ws_dir: str, cid: str, sku: str, node: str) -> set:
    """Weeks where the operating calendar decides the node's planned output (a row with shifts > 0)."""
    p = os.path.join(case_dir(ws_dir, cid), "model", OPCAL)
    if not os.path.exists(p):
        return set()
    _f, rows, _t, _b = _read_rows(p)
    out = set()
    for r in rows:
        if r.get("sku_id", "").strip() == sku and r.get("node_name", "").strip() == node:
            try:
                if int(str(r.get("shifts", "")).strip()) > 0:
                    out.add(r["week"].strip())
            except ValueError:
                pass
    return out


def set_shifts(ws_dir: str, cid: str, sku: str, node: str, shifts, from_week: Optional[str] = None,
               to_week: Optional[str] = None) -> dict:
    """段 4 A1: the number of shifts of the SKU x node in the copy's operating_calendar.csv (all weeks, or
    from_week..to_week, both ends included). 1..21. Weeks with 0 shifts (closed) are kept closed and returned.
    Stops when the model has no operating calendar or no row for the SKU x node (the file is never created)."""
    _guard_not_running(ws_dir, cid)
    p = os.path.join(case_dir(ws_dir, cid), "model", OPCAL)
    if not os.path.exists(p):
        raise CaseError(f"このモデルには操業カレンダー（{OPCAL}）がありません。シフトは変えられません。"
                        "直し方：計画の生産量は「生産量…」（cap_soft）で変える")
    fields, rows, term, bom = _read_rows(p)
    try:
        n = int(str(shifts).strip())
        if str(n) != str(shifts).strip():
            raise ValueError
    except ValueError:
        raise CaseError(f"shifts={shifts!r} は整数ではありません（1〜{MAX_SHIFTS}）")
    if not 1 <= n <= MAX_SHIFTS:
        raise CaseError(f"shifts={n} は 1〜{MAX_SHIFTS} の外です（0 は休業。休業はシフトの操作では作らない・消さない）")
    if not node:
        raise CaseError("工場（ノード）を指定してください")
    sel = [r for r in rows if r.get("sku_id", "").strip() == sku and r.get("node_name", "").strip() == node]
    if not sel:
        have = sorted({f"{r.get('sku_id')}@{r.get('node_name')}" for r in rows})
        raise CaseError(f"{p}: SKU {sku}・工場 {node} の行がありません（今ある行：{have}）")
    sel, rng = _select_weeks(p, sel, sku, node, from_week, to_week)
    closed = sorted(r["week"].strip() for r in sel if str(r.get("shifts", "")).strip() == "0")
    change = [r for r in sel if str(r.get("shifts", "")).strip() != "0"]
    old = sorted({r["shifts"].strip() for r in change}, key=lambda v: (len(v), v))
    for r in change:
        r["shifts"] = str(n)
    _write_rows(p, fields, rows, term, bom)
    _record_change(ws_dir, cid, "shifts", {"sku": sku, "node": node, "shifts_from": old, "shifts_to": str(n),
                                           "rows": len(change), "weeks": list(rng) if rng else "all",
                                           "closed_kept": closed})
    return {"sku": sku, "node": node, "rows": len(change), "shifts": n, "weeks": list(rng) if rng else "all",
            "closed_kept": closed}


def capacity_runs(rows: List[dict]) -> List[dict]:
    """Consecutive weeks with the same (max_supply, cap_soft), in week order: [{from, to, weeks, max_supply, cap_soft}]."""
    out = []
    for r in sorted(rows, key=lambda x: x["week"]):
        ms, cs = (r.get("max_supply") or "").strip(), (r.get("cap_soft") or "").strip()
        if out and (out[-1]["max_supply"], out[-1]["cap_soft"]) == (ms, cs):
            out[-1]["to"] = r["week"]
            out[-1]["weeks"] += 1
        else:
            out.append({"from": r["week"], "to": r["week"], "weeks": 1, "max_supply": ms, "cap_soft": cs})
    return out


def capacity_text(rows: List[dict]) -> str:
    """'13/11' when one pair, else '13/11・12（週で違う）' (never shown as one pair)."""
    ms = sorted({(r.get("max_supply") or "").strip() for r in rows}, key=lambda v: (len(v), v))
    cs = sorted({(r.get("cap_soft") or "").strip() for r in rows}, key=lambda v: (len(v), v))
    if len(ms) == 1 and len(cs) == 1:
        return f"{ms[0]}/{cs[0]}"
    return f"{'・'.join(ms)}/{'・'.join(cs)}（週で違う）"


def set_capacity(ws_dir: str, cid: str, sku: str, max_supply, cap_soft, node: Optional[str] = None) -> dict:
    """(c) the pair max_supply / cap_soft of every row of the SKU's factory."""
    _guard_not_running(ws_dir, cid)
    p = os.path.join(case_dir(ws_dir, cid), "model", CAPACITY)
    fields, rows, term, bom = _read_rows(p)
    ms, cs = _num_text(max_supply, "max_supply"), _num_text(cap_soft, "cap_soft")
    if Decimal(cs) > Decimal(ms):
        raise CaseError(f"cap_soft={cs} が max_supply={ms} を超えています。直し方：cap_soft ≦ max_supply にする")
    sel, node = _capacity_rows_for(p, rows, sku, node)
    old = sorted({(r["max_supply"], r["cap_soft"]) for r in sel})
    for r in sel:
        r["max_supply"], r["cap_soft"] = ms, cs
    _write_rows(p, fields, rows, term, bom)
    _record_change(ws_dir, cid, "capacity", {"sku": sku, "node": node, "from": [list(x) for x in old],
                                              "max_supply": ms, "cap_soft": cs, "rows": len(sel)})
    return {"sku": sku, "node": node, "rows": len(sel), "max_supply": ms, "cap_soft": cs}


def set_policy(ws_dir: str, cid: str, *, none: bool = False, allocation_file: str = None,
               policy_file: str = None, week_rule: str = None, knowledge_file: str = None,
               unallocated_note: str = None) -> dict:
    """(d) supply policy: none, or quantity quota + minimum supply files and the week rule."""
    _guard_not_running(ws_dir, cid)
    cdir = case_dir(ws_dir, cid)
    idir = os.path.join(cdir, "inputs")
    case = read_case(ws_dir, cid)
    for k in POLICY_FILES:                    # drop the old policy files
        old = (case["inputs"].get("policy") or {}).get(k)
        if old and os.path.exists(os.path.join(cdir, old)):
            os.remove(os.path.join(cdir, old))
    if none:
        if any([allocation_file, policy_file, week_rule, knowledge_file, unallocated_note]):
            raise CaseError("方針なし（--none）とファイルは一緒に指定できません")
        case["inputs"]["policy"] = None
    else:
        import sys
        if REPO not in sys.path:
            sys.path.insert(0, REPO)
        from wom.allocation.upper_demand_plan import WEEK_RULES, CAPACITY_RULE
        if not allocation_file:
            raise CaseError("数量枠のファイル（--allocation-file）がありません。方針をやめるなら --none")
        if not week_rule:
            raise CaseError(f"週の規則（--week-rule）がありません。選べる規則：{sorted(WEEK_RULES)}")
        if week_rule not in WEEK_RULES:
            raise CaseError(f"week_rule={week_rule!r} は使えません。選べる規則：{sorted(WEEK_RULES)}")
        if policy_file and week_rule != CAPACITY_RULE:
            raise CaseError(f"最低供給量のファイルは週の規則 {CAPACITY_RULE} と一緒にだけ使えます"
                            f"（今 {week_rule}）")
        pol = {"week_rule": week_rule, "unallocated_note": unallocated_note}
        for k, src in (("allocation_file", allocation_file), ("policy_file", policy_file),
                       ("knowledge_file", knowledge_file)):
            if src:
                if not os.path.exists(src):
                    raise CaseError(f"{src} がありません（{k}）")
                dst = os.path.join(idir, os.path.basename(src))
                shutil.copyfile(src, dst)
                pol[k] = os.path.relpath(dst, cdir).replace("\\", "/")
            else:
                pol[k] = None
        case["inputs"]["policy"] = pol
    case.setdefault("changes", []).append({"at": _now(), "what": "policy", "policy": case["inputs"]["policy"]})
    write_case(ws_dir, cid, case)
    return case["inputs"]["policy"]


def set_fixed_cost(ws_dir: str, cid: str, *, file: str = None, side: str = None, rows: List[dict] = None,
                   clear: bool = False) -> Optional[str]:
    """(e) cost premises (channel weekly fixed cost). Either rows (FIXED_COST_COLS), or a comparison
    table of tool 2 (column case base/alt) and the side to take. weekly_amount blank = 未設定."""
    _guard_not_running(ws_dir, cid)
    cdir = case_dir(ws_dir, cid)
    dst = os.path.join(cdir, "inputs", FIXED_COST_FILE)
    case = read_case(ws_dir, cid)
    if clear:
        if os.path.exists(dst):
            os.remove(dst)
        case["inputs"]["fixed_cost"] = None
        case.setdefault("changes", []).append({"at": _now(), "what": "fixed_cost", "cleared": True})
        write_case(ws_dir, cid, case)
        return None
    if file:
        fields, src_rows, _t, _b = _read_rows(file)
        if "case" in fields:
            if side not in ("base", "alt"):
                raise CaseError(f"{file} は 2 案の表（case 列あり）です。直し方：side に base か alt を指定する")
            src_rows = [r for r in src_rows if r["case"].strip() == side]
            if not src_rows:
                raise CaseError(f"{file}: case={side} の行がありません")
        rows = src_rows
    if not rows:
        raise CaseError("費用の前提の行がありません")
    out = []
    seen = set()
    for i, r in enumerate(rows, start=1):
        miss = [c for c in FIXED_COST_COLS if c not in r]
        if miss:
            raise CaseError(f"費用の前提の {i} 行目：列が足りません {miss}（列は {FIXED_COST_COLS}）")
        x = {c: (r.get(c) or "").strip() for c in FIXED_COST_COLS}
        for c in ("cost_item", "entity", "currency"):
            if not x[c]:
                raise CaseError(f"費用の前提の {i} 行目：{c} が空欄です")
        _check_week(x["paid_start_week"], f"{i} 行目の paid_start_week")
        _check_week(x["paid_end_week"], f"{i} 行目の paid_end_week")
        if x["weekly_amount"] != "":
            x["weekly_amount"] = _num_text(x["weekly_amount"], f"{i} 行目の weekly_amount")
        x[COUNT_OUTSIDE_COL] = (r.get(COUNT_OUTSIDE_COL) or "").strip()
        x[DISPLAY_COL] = (r.get(DISPLAY_COL) or "").strip()
        if x[COUNT_OUTSIDE_COL] not in ("", "0", "1"):
            raise CaseError(f"費用の前提の {i} 行目：{COUNT_OUTSIDE_COL}={x[COUNT_OUTSIDE_COL]!r} は 0・1・空欄"
                            "（空欄は 0 ＝ 報告期間だけを数える）")
        if x["cost_item"] in seen:
            raise CaseError(f"費用の前提：cost_item {x['cost_item']} が重複しています")
        seen.add(x["cost_item"])
        out.append(x)
    cols = FIXED_COST_COLS + [c for c in OPTIONAL_COST_COLS if any(x[c] for x in out)]
    _write_rows(dst, cols, out, "\n", False)
    case["inputs"]["fixed_cost"] = os.path.relpath(dst, cdir).replace("\\", "/")
    case.setdefault("changes", []).append({"at": _now(), "what": "fixed_cost", "rows": out})
    write_case(ws_dir, cid, case)
    return dst


# ── hash と状態 ─────────────────────────────────────────────────────────
def input_hashes(ws_dir: str, cid: str) -> Dict[str, str]:
    """sha256 of every file that the run reads: model/ (all files) and the policy files in inputs/.
    The cost premises (inputs/fixed_cost.csv) are read only by the comparison and are not included."""
    cdir = case_dir(ws_dir, cid)
    out = {}
    mdir = os.path.join(cdir, "model")
    for root, _dirs, files in os.walk(mdir):
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, cdir).replace("\\", "/")
            # 到達点 5 A0-3: the entry plan without its text columns; every other file as a whole
            out[rel] = _entry_plan_digest(p) if rel == f"model/{ENTRY_PLAN}" else _sha256_file(p)
    case = read_case(ws_dir, cid)
    pol = case["inputs"].get("policy") or {}
    for k in POLICY_FILES:
        rel = pol.get(k)
        if rel:
            p = os.path.join(cdir, rel)
            out[rel] = _sha256_file(p) if os.path.exists(p) else "missing"
    out["(policy)"] = hashlib.sha256(json.dumps(pol, sort_keys=True, ensure_ascii=False)
                                     .encode("utf-8")).hexdigest()
    return dict(sorted(out.items()))


def fixed_cost_hash(ws_dir: str, cid: str) -> Optional[str]:
    """sha256 of the case's cost premises (inputs/fixed_cost.csv), None without one. Not part of the run hash:
    the comparison records it, so a change of the cost premises asks for comparing again (段 3 B3-2)."""
    fc = (read_case(ws_dir, cid).get("inputs") or {}).get("fixed_cost")
    p = os.path.join(case_dir(ws_dir, cid), fc) if fc else None
    return _sha256_file(p) if p and os.path.exists(p) else None


def changed_files(ws_dir: str, cid: str) -> List[str]:
    run = read_case(ws_dir, cid).get("run") or {}
    then = run.get("input_hashes") or {}
    now = input_hashes(ws_dir, cid)
    ep = f"model/{ENTRY_PLAN}"
    out = []
    for k in set(then) | set(now):
        if then.get(k) == now.get(k):
            continue
        # a run recorded before 到達点 5 holds the entry plan's file sha256: unchanged if the file is the same
        if k == ep and then.get(k) and not str(then[k]).startswith("nonote:") and \
                then[k] == _sha256_file(os.path.join(case_dir(ws_dir, cid), ep)):
            continue
        out.append(k)
    return sorted(out)


def status(ws_dir: str, cid: str) -> dict:
    """{"state": …, "reason": …, "changed_files": […]} -- derived from the run record and the hashes."""
    run = read_case(ws_dir, cid).get("run")
    if not run:
        return {"state": ST_NOT_RUN, "reason": "", "changed_files": []}
    st = run.get("state")
    if st == ST_RUNNING:
        return {"state": ST_RUNNING, "reason": run.get("stage", ""), "changed_files": []}
    ch = changed_files(ws_dir, cid)
    if ch:
        return {"state": ST_CHANGED, "reason": f"実行の後に入力が変わった。実行し直す（{', '.join(ch[:6])}"
                f"{' …' if len(ch) > 6 else ''}）", "changed_files": ch, "last_state": st}
    return {"state": st, "reason": run.get("reason", ""), "changed_files": []}


# ── 入力の要点・一覧 ─────────────────────────────────────────────────────
def input_summary(ws_dir: str, cid: str) -> dict:
    cdir = case_dir(ws_dir, cid)
    s = {"launch_week": {}, "capacity": {}, "policy": None, "fixed_cost": []}
    ep = os.path.join(cdir, "model", ENTRY_PLAN)
    if os.path.exists(ep):
        _f, rows, _t, _b = _read_rows(ep)
        s["launch_week"] = {f"{r['sku_id'].strip()}:{r['region'].strip()}": r["launch_week"].strip() for r in rows}
    _f, rows, _t, _b = _read_rows(os.path.join(cdir, "model", CAPACITY))
    by = {}
    for r in rows:
        k = f"{r['sku_id'].strip()}@{r['node_name'].strip()}"
        by.setdefault(k, []).append(r)
    s["capacity"] = {k: capacity_text(v) for k, v in sorted(by.items())}
    case = read_case(ws_dir, cid)
    pol = case["inputs"].get("policy")
    if pol:
        s["policy"] = {"allocation": os.path.basename(pol.get("allocation_file") or ""),
                       "min_supply": os.path.basename(pol.get("policy_file") or "") or None,
                       "week_rule": pol.get("week_rule")}
    fc = case["inputs"].get("fixed_cost")
    if fc and os.path.exists(os.path.join(cdir, fc)):
        _f, rows, _t, _b = _read_rows(os.path.join(cdir, fc))
        s["fixed_cost"] = [{"cost_item": r["cost_item"], "paid": f"{r['paid_start_week']}〜{r['paid_end_week']}",
                            "weekly_amount": r["weekly_amount"] if r["weekly_amount"] != "" else "未設定",
                            "count_outside_report": (r.get(COUNT_OUTSIDE_COL) or "").strip() == "1",
                            "display_name": (r.get(DISPLAY_COL) or "").strip() or r["cost_item"]}
                           for r in rows]
    return s


def list_cases(ws_dir: str) -> List[dict]:
    """One row per case: id, name, parent, input summary, state and (done cases) the result summary.
    Results of a case whose inputs changed after the run are not shown (design §2.2 rule 1)."""
    out = []
    for cid in case_ids(ws_dir):
        case = read_case(ws_dir, cid)
        st = status(ws_dir, cid)
        row = {"id": cid, "name": case["name"], "parent": case.get("parent"), "inputs": input_summary(ws_dir, cid),
               "state": st["state"], "reason": st["reason"], "result": None}
        run = case.get("run") or {}
        if st["state"] == ST_DONE:
            row["result"] = run.get("summary")
        out.append(row)
    return out


def format_list(rows: List[dict]) -> str:
    """The case table as text: only the inputs that differ between cases, then the results."""
    def varying(getter):
        keys = sorted({k for r in rows for k in getter(r)})
        return [k for k in keys if len({getter(r).get(k) for r in rows}) > 1]
    lw = varying(lambda r: r["inputs"]["launch_week"])
    cap = varying(lambda r: r["inputs"]["capacity"])
    head = ["id", "name", "parent"] + [f"launch {k}" for k in lw] + [f"cap {k}" for k in cap] + \
        ["policy", "deliveries", "unallocated", "backlog_end", "P0", "state"]
    lines = ["\t".join(head)]
    for r in rows:
        pol = r["inputs"]["policy"]
        res = r["result"] or {}
        def kv(d):
            return " ".join(f"{k}={v}" for k, v in sorted((d or {}).items()) if v) or "0"
        cells = [r["id"], r["name"], r["parent"] or "—"] + [r["inputs"]["launch_week"].get(k, "") for k in lw] + \
            [r["inputs"]["capacity"].get(k, "") for k in cap] + \
            [("なし" if not pol else f"{pol['allocation']}+{pol['min_supply'] or '-'}/{pol['week_rule']}")]
        if res:
            cells += [kv(res.get("deliveries_by_sku")),
                      ("—" if res.get("unallocated_by_key") is None else kv(res.get("unallocated_by_key"))),
                      kv(res.get("backlog_end_by_key")), f"{res.get('P0_report', 0):,.0f}"]
        else:
            cells += ["", "", "", ""]
        cells.append(r["state"] + (f"（{r['reason']}）" if r["reason"] and r["state"] != ST_DONE else ""))
        lines.append("\t".join(str(c) for c in cells))
    return "\n".join(lines)
