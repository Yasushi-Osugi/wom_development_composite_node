# -*- coding: utf-8 -*-
"""
計画期間の自動検出（RequestLetter_PeriodDetection_Fix）

計画期間 ＝ 需要 CSV の最初の週から最後の週までの、連続した ISO の暦の週。CSV に無い週は需要 0 として
含め、その週を必ず返す（黙って埋めない）。
"""
from __future__ import annotations

import os

import pytest

from wom.engine.plan_period import calendar_weeks, detect_plan_period, parse_week

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _csv(tmp_path, weeks):
    p = tmp_path / "demand_forecast.csv"
    rows = ["sku_id,region,week,quantity"] + [f"A,R,{w},10" for w in weeks]
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(p)


def test_gap_in_the_middle(tmp_path):
    p = detect_plan_period(_csv(tmp_path, ["2027-W01", "2027-W02", "2027-W05", "2027-W06"]))
    assert (p.start, p.end, p.n_weeks) == ("2027-W01", "2027-W06", 6)
    assert p.weeks == ["2027-W01", "2027-W02", "2027-W03", "2027-W04", "2027-W05", "2027-W06"]
    assert p.filled_weeks == ["2027-W03", "2027-W04"]
    assert "2 週" in p.warning() and "2027-W03" in p.warning()


def test_missing_w53_across_the_year(tmp_path):
    # 2026 has 53 ISO weeks; a CSV that jumps from 2026-W52 to 2027-W01 skips 2026-W53
    p = detect_plan_period(_csv(tmp_path, ["2026-W51", "2026-W52", "2027-W01", "2027-W02"]))
    assert p.weeks == ["2026-W51", "2026-W52", "2026-W53", "2027-W01", "2027-W02"]
    assert p.filled_weeks == ["2026-W53"]
    # 2027 has 52: no W53 to fill
    q = detect_plan_period(_csv(tmp_path, ["2027-W52", "2028-W01"]))
    assert q.weeks == ["2027-W52", "2028-W01"] and q.filled_weeks == []


def test_no_gap_is_unchanged(tmp_path):
    weeks = calendar_weeks("2025-W50", 8)
    p = detect_plan_period(_csv(tmp_path, list(reversed(weeks)) + weeks))   # order and repeats
    assert p.weeks == weeks and p.filled_weeks == [] and p.warning() == ""


def test_unpadded_labels_are_the_same_week(tmp_path):
    p = detect_plan_period(_csv(tmp_path, ["2027-W01", "2027-W2", "2027-W03"]))
    assert p.n_weeks == 3 and p.filled_weeks == []


def test_a_label_that_is_not_an_iso_week_stops(tmp_path):
    with pytest.raises(ValueError, match="ISO week"):
        detect_plan_period(_csv(tmp_path, ["2027-W01", "2027-W53"]))      # 2027 has 52 weeks
    with pytest.raises(ValueError, match="ISO week"):
        parse_week("2027-01")


def test_sample_models():
    """apparel-us: 30 weeks were missing (period 91 -> 121); rice: 2026-W53 (156 -> 157)."""
    a = detect_plan_period(os.path.join(REPO, "data", "sample", "apparel-us-2026", "demand_forecast.csv"))
    assert (a.start, a.end, a.n_weeks, len(a.filled_weeks)) == ("2025-W37", "2027-W52", 121, 30)
    assert {"2026-W07", "2026-W08", "2026-W53", "2027-W46", "2027-W47"} <= set(a.filled_weeks)
    r = detect_plan_period(os.path.join(REPO, "data", "sample", "rice-japan-2027-2028", "demand_forecast.csv"))
    assert (r.start, r.end, r.n_weeks, r.filled_weeks) == ("2026-W01", "2028-W52", 157, ["2026-W53"])


def test_headless_and_gui_use_the_same_function():
    import inspect
    import tools.run_headless_from_folder as H
    src_h = inspect.getsource(H)
    src_g = open(os.path.join(REPO, "wom", "gui", "app.py"), encoding="utf-8").read()
    assert "detect_plan_period" in src_h and "detect_plan_period" in src_g
    # the old "first week + number of week names" is gone from both
    old = 'sorted(dem_df["week"].dropna().unique().tolist())'
    assert old not in src_h and old not in src_g
