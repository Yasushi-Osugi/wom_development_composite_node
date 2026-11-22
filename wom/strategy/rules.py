# -*- coding: utf-8 -*-
"""
wom/strategy/rules.py — 型ごとの規則（純関数。ファイルを読まない）
=================================================================
RequestLetter_Promo_Convert_Slice1 §3.1・§3.2、販促の業務定義 v0.1 §2.2・§3。

- promo_demand_delta：反応週 ＝ 実施の週を lag_weeks 後ろへ移した区間。x(w) ＝ B(w) × rate
  （反応週の B を掛ける。広告の週の B ではない）。反動減は反応の区間の翌週から rebound_weeks 週、
  x(w) ＝ −B(w) × rebound_rate。正の区間と負の区間を別々に、区間ごとに累積を切り捨て、前の週の累積との
  差をその週の d(w) にする。区間の終わりの端数は「未反映の端数」として返し、後の週・別の施策・別の水準へ
  移さない。計算は Decimal（浮動小数点で 0.1 を足すと 1 よりわずかに小さくなり、切り捨てで 0 になりうる）。
- promo_external_cost：費用の発生の各週の為替（その週以前で最も新しい行）で報告通貨へ換算。期間内で
  レートが 1 つでなければ止める（初版）。
"""
from __future__ import annotations

import datetime
from decimal import Decimal, ROUND_FLOOR, InvalidOperation
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from wom.strategy import StrategyError


# ── 週 ────────────────────────────────────────────────────────────────
def _monday(label: str) -> datetime.date:
    try:
        y, w = str(label).strip().split("-W")
        return datetime.date.fromisocalendar(int(y), int(w), 1)
    except (ValueError, TypeError):
        raise StrategyError(f"週のラベル {label!r} が不正です（例 2028-W10）")


def week_label(d: datetime.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_add(label: str, n: int) -> str:
    return week_label(_monday(label) + datetime.timedelta(weeks=int(n)))


def week_range(start: str, end: str) -> List[str]:
    """ISO weeks start..end, both ends included."""
    a, b = _monday(start), _monday(end)
    if b < a:
        raise StrategyError(f"週の終わり {end} が始まり {start} より前です")
    return [week_label(a + datetime.timedelta(weeks=i)) for i in range((b - a).days // 7 + 1)]


def dec(v, what: str) -> Decimal:
    """A number read from text as Decimal (never through float)."""
    try:
        d = Decimal(str(v).strip())
    except (InvalidOperation, TypeError):
        raise StrategyError(f"{what}={v!r} は数値ではありません")
    if not d.is_finite():
        raise StrategyError(f"{what}={v!r} は数値ではありません")
    return d


def _floor(d: Decimal) -> int:
    return int(d.to_integral_value(rounding=ROUND_FLOOR))


# ── 需要の増減 ──────────────────────────────────────────────────────────
def integerize(xs: Sequence[Decimal]) -> Tuple[List[int], Decimal]:
    """One interval of non-negative amounts: d(w) = floor A(w) − floor A(w−1), A = running sum from 0.
    Returns (integer steps, residual = A_end − floor A_end)."""
    a = Decimal(0)
    prev = 0
    out = []
    for x in xs:
        if x < 0:
            raise StrategyError(f"区間の量 {x} が負です（正の区間と負の区間は別々に渡す）")
        a += x
        f = _floor(a)
        out.append(f - prev)
        prev = f
    return out, a - prev


def demand_delta(base: Dict[str, Decimal], start: str, end: str, rate, lag_weeks, rebound_rate=0,
                 rebound_weeks=0, plan_weeks: Optional[Iterable[str]] = None) -> dict:
    """The integer demand change of one promotion measure on one key.

    base: week -> B(w) (the frozen base demand of the key). start..end: the weeks the measure runs.
    Returns {"d": {week: int}, "intervals": [{"kind": "response"|"rebound", "weeks": [...], "x": [...],
    "steps": [...], "residual": Decimal}]}. Weeks outside the plan period stop (no silent cut)."""
    rate, rebound_rate = Decimal(str(rate)), Decimal(str(rebound_rate))
    lag, rw = int(lag_weeks), int(rebound_weeks)
    if rate < 0 or rebound_rate < 0:
        raise StrategyError(f"反応の率 {rate}・反動の率 {rebound_rate} は 0 以上にしてください（反動は rebound_rate で書く）")
    if lag < 0 or rw < 0:
        raise StrategyError(f"lag_weeks={lag}・rebound_weeks={rw} は 0 以上の整数にしてください")
    if rw == 0 and rebound_rate != 0:
        raise StrategyError(f"rebound_rate={rebound_rate} なのに rebound_weeks=0 です（反動の週が無い）")
    plan = set(plan_weeks) if plan_weeks is not None else set(base)
    resp = week_range(week_add(start, lag), week_add(end, lag))
    reb = [week_add(resp[-1], i + 1) for i in range(rw)]
    outside = [w for w in resp + reb if w not in plan]
    if outside:
        raise StrategyError(f"反応・反動の週 {outside[0]}〜{outside[-1]}（{len(outside)} 週）が計画の期間の外です"
                            f"（実施 {start}〜{end}、遅れ {lag} 週、反動 {rw} 週）。直し方：施策の週・遅れ・反動の週を"
                            "計画の期間の中に収める（期間を延ばすのは別の判断。黙って切り捨てない）")
    missing = [w for w in resp + reb if w not in base]
    if missing:
        raise StrategyError(f"基準の需要に週 {missing[0]} の行がありません（{len(missing)} 週）")
    d: Dict[str, int] = {}
    intervals = []
    for kind, weeks, r, sign in (("response", resp, rate, 1), ("rebound", reb, rebound_rate, -1)):
        if not weeks:
            continue
        xs = [base[w] * r for w in weeks]
        steps, residual = integerize(xs)
        for w, s in zip(weeks, steps):
            d[w] = d.get(w, 0) + sign * s
        intervals.append({"kind": kind, "weeks": weeks, "x": [sign * x for x in xs],
                          "steps": [sign * s for s in steps], "residual": sign * residual})
    return {"d": d, "intervals": intervals, "response_weeks": resp, "rebound_weeks": reb}


def apply_delta(base: Dict[str, Decimal], d: Dict[str, int], what: str = "") -> Dict[str, Decimal]:
    """D(w) = B(w) + d(w) for the weeks of d. A negative D stops before anything is written."""
    out = {}
    for w in sorted(d):
        v = base[w] + d[w]
        if v < 0:
            raise StrategyError(f"{what}週 {w} の需要が負になります（B={num_text(base[w])}、d={d[w]:+d}、D={num_text(v)}）。"
                                "直し方：反動の率・週を見直す（0 や負の値として黙って保存しない）")
        out[w] = v
    return out


# ── 円への換算 ──────────────────────────────────────────────────────────
def fx_rate_for_weeks(fx_rows: Sequence[dict], currency: str, hq_currency: str, weeks: Sequence[str],
                      source: str = "ppc_fx_rate.csv") -> Decimal:
    """The single rate currency -> hq_currency over the weeks (each week: the latest row on or before it).
    Stops if a week has no rate or the rate is not one value over the weeks."""
    if currency == hq_currency:
        return Decimal(1)
    rows = sorted(((r["week"].strip(), dec(r["rate"], f"{source} の rate"))
                   for r in fx_rows if r.get("currency", "").strip() == currency
                   and r.get("base_currency", "").strip() == hq_currency), key=lambda t: t[0])
    rates = {}
    for w in weeks:
        prior = [rt for wk, rt in rows if wk <= w]
        if not prior:
            raise StrategyError(f"{source} に {currency}→{hq_currency} の {w} 以前のレートがありません。"
                                f"直し方：{source} に行を足す")
        rates[w] = prior[-1]
    vals = sorted(set(rates.values()))
    if len(vals) != 1:
        ch = [w for w in weeks[1:] if rates[w] != rates[weeks[weeks.index(w) - 1]]]
        raise StrategyError(f"費用の期間 {weeks[0]}〜{weeks[-1]} で {currency}→{hq_currency} のレートが 1 つではありません"
                            f"（{', '.join(str(v) for v in vals)}、変わる週 {ch}）。初版は扱いません。直し方：期間を"
                            "レートが同じ週ごとに分けた別の施策にする（費目の週別の分割は次の版）")
    return vals[0]


def num_text(d: Decimal) -> str:
    """A Decimal as CSV text (integers without '.0')."""
    if d == d.to_integral_value():
        return str(int(d))
    return format(d.normalize(), "f")
