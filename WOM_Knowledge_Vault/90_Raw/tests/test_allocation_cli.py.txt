# -*- coding: utf-8 -*-
"""
tests/test_allocation_cli.py — run_allocation_map CLI のスモーク／回帰テスト
==========================================================================
`tools/run_allocation_map.run()` が §7 の出力 CSV を正しく生成し、シナリオ別の
最大利益が付録 A 回帰値（s1=132.1M / s2=207.2M / s4=176.7M / s5=85.8M）に一致することを固定。
出力は一時ディレクトリに書き、リポジトリを汚さない。
"""
import csv
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from tools.run_allocation_map import run, load_scenarios

ALLOC_DIR = os.path.join(os.path.dirname(__file__), "..",
                         "data", "sample", "soysauce-jpy-2027-alloc")


def _read(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_run_writes_seven_files(tmp_path):
    out = str(tmp_path)
    written = run(ALLOC_DIR, cap_wk=800, out_dir=out, verbose=False)
    for name in ["ga_cost_block_derived.csv", "ga_profit_surface.csv", "ga_fx_balance.csv",
                 "ga_plateau.csv", "ga_switching_point.csv", "ga_interaction.csv",
                 "ga_constraint_cost.csv"]:
        assert name in written and os.path.exists(written[name]), name


def test_profit_surface_row_count(tmp_path):
    out = str(tmp_path)
    run(ALLOC_DIR, cap_wk=800, out_dir=out, verbose=False)
    rows = _read(os.path.join(out, "ga_profit_surface.csv"))
    # 8 定常シナリオ（s1-s7 + s9_fta_cliff、Phase 5。s8 は時系列で対象外）× 231 点
    assert len(rows) == 8 * 231
    assert set(r["scenario_id"] for r in rows) >= {"s1_base", "s2_weak_yen", "s4_compound",
                                                     "s9_fta_cliff"}


def test_plateau_max_profit_regression(tmp_path):
    out = str(tmp_path)
    run(ALLOC_DIR, cap_wk=800, out_dir=out, verbose=False)
    pl = {r["scenario_id"]: r for r in _read(os.path.join(out, "ga_plateau.csv"))}
    assert float(pl["s1_base"]["max_profit"]) / 1e6 == pytest.approx(132.1, abs=0.1)
    assert float(pl["s2_weak_yen"]["max_profit"]) / 1e6 == pytest.approx(207.2, abs=0.1)
    assert float(pl["s4_compound"]["max_profit"]) / 1e6 == pytest.approx(176.7, abs=0.1)
    assert float(pl["s5_strong_yen"]["max_profit"]) / 1e6 == pytest.approx(85.8, abs=0.1)
    assert int(pl["s4_compound"]["plateau_size"]) == 3
    # s7（金利のみ）は粗利では s1 と同一
    assert pl["s7_rate_up"]["max_profit"] == pl["s1_base"]["max_profit"]


def test_switching_points_in_output(tmp_path):
    out = str(tmp_path)
    run(ALLOC_DIR, cap_wk=800, out_dir=out, verbose=False)
    sw = _read(os.path.join(out, "ga_switching_point.csv"))
    fxs = [int(r["fx_threshold_jpy"]) for r in sw]
    assert 117 in fxs and 119 in fxs


def test_cost_block_derived_output(tmp_path):
    out = str(tmp_path)
    run(ALLOC_DIR, cap_wk=800, out_dir=out, verbose=False)
    cb = {r["market"]: r for r in _read(os.path.join(out, "ga_cost_block_derived.csv"))}
    assert float(cb["JP"]["usd"]) == pytest.approx(9.1)
    assert float(cb["US"]["usd"]) == pytest.approx(15.65)
    assert float(cb["EU"]["eur"]) == pytest.approx(2.15)
    assert float(cb["US"]["transfer_price_usd"]) == pytest.approx(17.6)


def test_scenario_loader_time_series_flag():
    scens = {s["id"]: s for s in load_scenarios(ALLOC_DIR)}
    assert scens["s1_base"]["time_series"] is False
    assert scens["s8_actual_path"]["time_series"] is True    # 時系列は surface 対象外
    assert scens["s6_us_tariff_up"]["tariff"]["US"] == pytest.approx(0.25)


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        for fn in [test_run_writes_seven_files, test_profit_surface_row_count,
                   test_plateau_max_profit_regression, test_switching_points_in_output,
                   test_cost_block_derived_output]:
            import pathlib
            fn(pathlib.Path(td))
    test_scenario_loader_time_series_flag()
    print("All allocation CLI tests passed.")
