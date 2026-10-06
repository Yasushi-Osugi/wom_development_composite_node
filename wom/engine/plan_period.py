# -*- coding: utf-8 -*-
"""
計画期間の自動検出（RequestLetter_PeriodDetection_Fix）

計画期間は、需要 CSV（demand_forecast.csv）の**最初の週から最後の週までの、連続した ISO の暦の週**。
CSV に載っていない週（需要 0 の週を書いていない、年をまたぐ W53 など）は需要 0 の週として期間に
含め、どの週を 0 で埋めたかを返す（呼ぶ側がログと計画の結果の情報に出す。黙って埋めない）。

以前は「最初の週 ＋ 週の名前の種類の数」で決めていたため、途中に抜けがあると、その数だけ期間の
終わりが切れ、最後の週の需要が計画に入らなかった（apparel-us-2026：30 週、rice：2026-W53）。

headless（tools/run_headless_from_folder.py）と GUI（wom/gui/app.py）の両方がこの関数を使う。
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import List

import pandas as pd

_WEEK = re.compile(r"^(\d{4})-W(\d{1,2})$")


def parse_week(label: str) -> datetime.date:
    """Monday of the ISO week `YYYY-Www`. A label that is not an ISO week is an error."""
    m = _WEEK.match(str(label).strip())
    if not m:
        raise ValueError(f"not an ISO week label: {label!r} (expected YYYY-Www)")
    try:
        return datetime.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    except ValueError as exc:     # e.g. 2027-W53 (2027 has 52 weeks)
        raise ValueError(f"not an ISO week: {label!r} ({exc})") from None


def format_week(d: datetime.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def calendar_weeks(start: str, n_weeks: int) -> List[str]:
    """n_weeks consecutive ISO week labels from `start`."""
    d = parse_week(start)
    out = []
    for _ in range(int(n_weeks)):
        out.append(format_week(d))
        d += datetime.timedelta(weeks=1)
    return out


@dataclass
class PlanPeriod:
    start: str
    end: str
    weeks: List[str]                       # every ISO week from start to end
    filled_weeks: List[str] = field(default_factory=list)   # not in the CSV: demand 0

    @property
    def n_weeks(self) -> int:
        return len(self.weeks)

    def warning(self) -> str:
        if not self.filled_weeks:
            return ""
        shown = ", ".join(self.filled_weeks[:12]) + (" …" if len(self.filled_weeks) > 12 else "")
        return (f"需要 CSV に無い週 {len(self.filled_weeks)} 週を需要 0 として計画期間に含めた：{shown}")


def detect_plan_period(demand_path: str, week_col: str = "week") -> PlanPeriod:
    """The plan period of a demand CSV: its first to its last week, every calendar week."""
    df = pd.read_csv(demand_path, usecols=lambda c: c == week_col)
    if week_col not in df.columns:
        raise ValueError(f"{demand_path}: no {week_col!r} column")
    labels = sorted({str(w).strip() for w in df[week_col].dropna()}, key=parse_week)
    if not labels:
        raise ValueError(f"{demand_path}: no weeks")
    start, end = labels[0], labels[-1]
    n = (parse_week(end) - parse_week(start)).days // 7 + 1
    weeks = calendar_weeks(start, n)
    present = {format_week(parse_week(w)) for w in labels}   # "2026-W7" == "2026-W07"
    filled = [w for w in weeks if w not in present]
    return PlanPeriod(start, end, weeks, filled)
