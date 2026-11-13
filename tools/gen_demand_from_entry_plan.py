# -*- coding: utf-8 -*-
"""
tools/gen_demand_from_entry_plan.py — 投入の表から週別需要を作る
================================================================
RequestLetter_Cockpit_FirstComparison_Observe §2（2026-11-13）。

    python -m tools.gen_demand_from_entry_plan --model-dir <モデル> --plan-start 2026-W37 --plan-end 2029-W52 [--out <CSV>]

入力：モデルのフォルダの market_entry_plan.csv（1 行 ＝ 製品 × 販売先・チャネル）

    sku_id, region, launch_week, steady_lots_per_week, ramp_weeks, ramp_ratio,
    price, currency, promotion_note, basis_note

規則（鍵ごと・週ごと）：
    週 < launch_week                          → 0
    launch_week ≦ 週 < launch_week + ramp_weeks → steady × ramp_ratio を四捨五入（0.5 は切り上げ）
    それ以降                                   → steady

出力：
    demand_forecast.csv（既定はモデルの demand_forecast.csv。列 sku_id,region,week,quantity。改行は LF。
        並びは WOM の助走の正規形：最初の非ゼロ需要週より前は週ごとに sku_id・region の昇順、
        それ以降は鍵ごと（入力の表の行の順）に週の昇順。materialize_warmup が書き直さない並び）
    demand_generation_log.json（出力と同じフォルダ。入力の表の内容と sha256、期間、鍵ごとの合計、行数）

止める条件（ファイル・行・値と直し方を出す。黙った既定値を作らない）：
    列の不足、鍵の重複、鍵が計画の木の市場（sc_tree_master.csv の leaf_out の region）に無い、
    週のラベルが不正、launch_week が期間の外、数値でない・負（ramp_weeks・ramp_ratio の空欄を含む）、
    価格・通貨が ppc_market_price.csv と食い違う。

WOM のエンジンは import しない（CSV を読んで CSV を書くだけ）。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, List, Tuple

PLAN_FILE = "market_entry_plan.csv"
REQUIRED_COLS = ["sku_id", "region", "launch_week", "steady_lots_per_week", "ramp_weeks", "ramp_ratio",
                 "price", "currency", "promotion_note", "basis_note"]
_WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")


class EntryPlanError(ValueError):
    """The entry plan cannot be turned into demand (the message says where and how to fix it)."""


# ── 週 ───────────────────────────────────────────────────────────────
def parse_week(label: str) -> datetime.date:
    """ISO week label 'YYYY-Www' -> Monday of that week. Raises ValueError if invalid."""
    m = _WEEK_RE.match(str(label).strip())
    if not m:
        raise ValueError(f"week label must look like 2027-W01: {label!r}")
    y, w = int(m.group(1)), int(m.group(2))
    try:
        d = datetime.date.fromisocalendar(y, w, 1)
    except ValueError:
        raise ValueError(f"{label!r} does not exist (year {y} has no week {w})")
    return d


def week_label(d: datetime.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_range(start: str, end: str) -> List[str]:
    a, b = parse_week(start), parse_week(end)
    if b < a:
        raise EntryPlanError(f"--plan-end {end} is before --plan-start {start}")
    out, d = [], a
    while d <= b:
        out.append(week_label(d))
        d += datetime.timedelta(days=7)
    return out


def round_half_up(x: Decimal) -> int:
    return int(x.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def demand_for_week(idx_from_launch: int, steady: int, ramp_weeks: int, ramp_ratio: Decimal) -> int:
    """idx_from_launch: weeks since launch (negative = before launch)."""
    if idx_from_launch < 0:
        return 0
    if idx_from_launch < ramp_weeks:
        return round_half_up(Decimal(steady) * ramp_ratio)
    return steady


# ── 読み込みと検査 ────────────────────────────────────────────────────
def _leaf_out_regions(model_dir: str) -> Dict[str, set]:
    """product -> set of leaf_out regions (sc_tree_master.csv)."""
    p = os.path.join(model_dir, "sc_tree_master.csv")
    if not os.path.exists(p):
        raise EntryPlanError(f"{p} がありません（市場の鍵を確かめるのに使います）")
    out: Dict[str, set] = {}
    with open(p, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("node_type") or "").strip() == "leaf_out":
                out.setdefault(r["product_name"].strip(), set()).add((r.get("region") or "").strip())
    return out


def _market_prices(model_dir: str) -> Dict[Tuple[str, str], set]:
    """(sku, region) -> {(price Decimal, currency)} from ppc_market_price.csv (empty if no file)."""
    p = os.path.join(model_dir, "ppc_market_price.csv")
    out: Dict[Tuple[str, str], set] = {}
    if not os.path.exists(p):
        return out
    with open(p, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            key = (r["product_id"].strip(), r["market_node"].strip())
            out.setdefault(key, set()).add((Decimal(r["market_price"].strip()), r["currency"].strip()))
    return out


def read_plan(model_dir: str, plan_path: str = None) -> Tuple[List[dict], bytes, str]:
    """Returns (rows, raw bytes, path). Checks columns and per-cell values (not the period)."""
    path = plan_path or os.path.join(model_dir, PLAN_FILE)
    if not os.path.exists(path):
        raise EntryPlanError(f"{path} がありません。直し方：{PLAN_FILE} をモデルのフォルダに置く")
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    cols = [c.strip() for c in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED_COLS if c not in cols]
    if missing:
        raise EntryPlanError(f"{path}: 列が足りません {missing}。直し方：見出しに {REQUIRED_COLS} を置く"
                             "（値が無い列も見出しは要ります）")
    regions = _leaf_out_regions(model_dir)
    prices = _market_prices(model_dir)
    rows, seen = [], {}
    for i, r in enumerate(reader, start=2):
        r = {k.strip(): (v or "").strip() for k, v in r.items() if k is not None}
        where = f"{path} の {i} 行目（sku_id={r['sku_id']!r}, region={r['region']!r}）"
        key = (r["sku_id"], r["region"])
        if not r["sku_id"] or not r["region"]:
            raise EntryPlanError(f"{where}: sku_id・region が空です")
        if key in seen:
            raise EntryPlanError(f"{where}: 鍵が {seen[key]} 行目と重複しています。直し方：1 鍵 1 行にする")
        seen[key] = i
        if r["region"] not in regions.get(r["sku_id"], set()):
            raise EntryPlanError(
                f"{where}: この鍵は計画の木の市場にありません（sc_tree_master.csv の leaf_out、製品 "
                f"{r['sku_id']} の region は {sorted(regions.get(r['sku_id'], set()))}）。直し方：region を "
                "leaf_out の region に合わせる")
        try:
            parse_week(r["launch_week"])
        except ValueError as e:
            raise EntryPlanError(f"{where}: launch_week が不正です（{e}）")

        def _int(col):
            v = r[col]
            if v == "":
                raise EntryPlanError(f"{where}: {col} が空欄です。直し方：値を明示する（空欄は不可）")
            try:
                d = Decimal(v)
            except InvalidOperation:
                raise EntryPlanError(f"{where}: {col}={v!r} は数値ではありません")
            if d < 0 or d != d.to_integral_value():
                raise EntryPlanError(f"{where}: {col}={v!r} は 0 以上の整数にしてください")
            return int(d)

        steady = _int("steady_lots_per_week")
        ramp_weeks = _int("ramp_weeks")
        if r["ramp_ratio"] == "":
            raise EntryPlanError(f"{where}: ramp_ratio が空欄です。直し方：値を明示する（例 0.5）")
        try:
            ratio = Decimal(r["ramp_ratio"])
        except InvalidOperation:
            raise EntryPlanError(f"{where}: ramp_ratio={r['ramp_ratio']!r} は数値ではありません")
        if ratio < 0:
            raise EntryPlanError(f"{where}: ramp_ratio={r['ramp_ratio']!r} は負です")
        # 価格の記録（書いてあれば ppc_market_price.csv と同じであること）
        if r["price"] or r["currency"]:
            if not (r["price"] and r["currency"]):
                raise EntryPlanError(f"{where}: price と currency は両方書くか、両方空欄にしてください")
            try:
                pr = Decimal(r["price"])
            except InvalidOperation:
                raise EntryPlanError(f"{where}: price={r['price']!r} は数値ではありません")
            if pr < 0:
                raise EntryPlanError(f"{where}: price={r['price']!r} は負です")
            got = prices.get(key)
            if not got:
                raise EntryPlanError(f"{where}: ppc_market_price.csv にこの鍵の価格がありません。"
                                     "直し方：価格を ppc_market_price.csv に置くか、表の price・currency を空欄にする")
            bad = sorted({(str(p), c) for p, c in got if (p, c) != (pr, r["currency"])})
            if bad:
                raise EntryPlanError(f"{where}: 価格 {r['price']} {r['currency']} が ppc_market_price.csv "
                                     f"の {bad} と違います。直し方：どちらかを直す")
        rows.append({"sku_id": r["sku_id"], "region": r["region"], "launch_week": r["launch_week"],
                     "steady": steady, "ramp_weeks": ramp_weeks, "ramp_ratio": ratio,
                     "row": i, "raw": r})
    if not rows:
        raise EntryPlanError(f"{path}: 行がありません")
    return rows, raw, path


# ── 生成 ─────────────────────────────────────────────────────────────
def generate(rows: List[dict], weeks: List[str], plan_path: str = "") -> List[Tuple[str, str, str, int]]:
    """Returns [(sku, region, week, qty)] in the WOM canonical order of a demand CSV.

    The order matches what wom.engine.warmup.materialize_warmup leaves (so the planner does not
    rewrite the file): weeks before the first non-zero demand week (real_start) are written week by
    week, keys sorted by (sku_id, region); from real_start on, key by key in the order of the entry
    plan rows, weeks ascending.
    """
    pos = {w: i for i, w in enumerate(weeks)}
    for r in rows:
        if r["launch_week"] not in pos:
            raise EntryPlanError(
                f"{plan_path} の {r['row']} 行目（sku_id={r['sku_id']!r}, region={r['region']!r}）: "
                f"launch_week {r['launch_week']} が期間 {weeks[0]}〜{weeks[-1]} の外です。"
                "直し方：--plan-start・--plan-end を広げるか launch_week を直す")
    q = {}
    for r in rows:
        for wi, w in enumerate(weeks):
            q[(r["sku_id"], r["region"], w)] = demand_for_week(
                wi - pos[r["launch_week"]], r["steady"], r["ramp_weeks"], r["ramp_ratio"])
    nz = [pos[w] for (_s, _g, w), v in q.items() if v != 0]
    real_i = min(nz) if nz else len(weeks)
    keyed = sorted(rows, key=lambda r: (r["sku_id"], r["region"]))
    out = []
    for w in weeks[:real_i]:
        for r in keyed:
            out.append((r["sku_id"], r["region"], w, q[(r["sku_id"], r["region"], w)]))
    for r in rows:
        for w in weeks[real_i:]:
            out.append((r["sku_id"], r["region"], w, q[(r["sku_id"], r["region"], w)]))
    return out


def write_demand(lines, out_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("sku_id,region,week,quantity\n")
        for s, g, w, q in lines:
            f.write(f"{s},{g},{w},{q}\n")


def run(model_dir: str, plan_start: str, plan_end: str, out: str = None, plan_path: str = None) -> dict:
    for lab, v in (("--plan-start", plan_start), ("--plan-end", plan_end)):
        try:
            parse_week(v)
        except ValueError as e:
            raise EntryPlanError(f"{lab}: {e}")
    rows, raw, ppath = read_plan(model_dir, plan_path)
    weeks = week_range(plan_start, plan_end)
    lines = generate(rows, weeks, ppath)
    out = out or os.path.join(model_dir, "demand_forecast.csv")
    write_demand(lines, out)
    totals: Dict[str, int] = {}
    for s, g, _w, q in lines:
        totals[f"{s}:{g}"] = totals.get(f"{s}:{g}", 0) + q
    log = {
        "tool": "tools.gen_demand_from_entry_plan",
        "entry_plan_path": os.path.abspath(ppath),
        "entry_plan_sha256": hashlib.sha256(raw).hexdigest(),
        "entry_plan_rows": [r["raw"] for r in rows],
        "plan_start": plan_start, "plan_end": plan_end, "weeks": len(weeks),
        "rule": "before launch 0; first ramp_weeks weeks round_half_up(steady*ramp_ratio); then steady",
        "totals_by_key": totals,
        "total_lots": sum(totals.values()),
        "rows_written": len(lines),
        "out": os.path.abspath(out),
        "out_sha256": hashlib.sha256(open(out, "rb").read()).hexdigest(),
    }
    with open(os.path.join(os.path.dirname(os.path.abspath(out)), "demand_generation_log.json"),
              "w", encoding="utf-8", newline="\n") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return log


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate weekly demand from market_entry_plan.csv")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--plan-start", required=True, help="first week written to the demand CSV (e.g. 2026-W37)")
    ap.add_argument("--plan-end", required=True, help="last week written to the demand CSV (e.g. 2029-W52)")
    ap.add_argument("--out", default=None, help="default: <model-dir>/demand_forecast.csv")
    a = ap.parse_args(argv)
    try:
        log = run(a.model_dir, a.plan_start, a.plan_end, a.out)
    except EntryPlanError as e:
        print(f"[gen_demand] 止めました: {e}", file=sys.stderr)
        return 2
    print(f"[gen_demand] {log['rows_written']} rows, {log['weeks']} weeks, total {log['total_lots']} lots "
          f"-> {log['out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
