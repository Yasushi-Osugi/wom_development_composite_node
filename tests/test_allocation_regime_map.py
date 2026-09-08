# -*- coding: utf-8 -*-
"""
tests/test_allocation_regime_map.py — Phase 4 ②レジーム地図（配分版）のテスト
================================================================================
設計正典: requests/Phase4_DesignMD_AllocationMeritRegime.md §4 / §7.2-7.3
検証台: data/sample/soysauce-jpy-2027-alloc
"""
import os

import matplotlib
matplotlib.use("Agg")

import pytest

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.analytics import switching_points
from wom.allocation.regime_map import scan_regime_grid
from wom.allocation.merit_order import build_allocation_merit_order, compare_with_grid
from wom.allocation.transmission import Scenario
from wom.allocation.grid import scan_surface
from tools.plot_allocation_merit_regime import (
    plot_allocation_merit_order,
    plot_allocation_merit_shift,
    plot_regime_map,
    parse_args,
    run,
)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..",
                         "data", "sample", "soysauce-jpy-2027-alloc")
CAP_WK = 800.0


def _nonempty(p):
    return os.path.exists(p) and os.path.getsize(p) > 1000


@pytest.fixture(scope="module")
def soysauce_blocks():
    return derive_cost_blocks(MODEL_DIR)


# ---------------------------------------------------------------------------
# ② レジーム地図のロジックテスト（5件）
# ---------------------------------------------------------------------------

def test_regime_map_reproduces_switching_points(soysauce_blocks):
    """material_usd=6.0 の水平断面が switching_points() の切替点（117円/119円）を
    再現すること（②が既存 V&V と同じ対象を見ていることの証明。最重要）"""
    blocks, tp = soysauce_blocks

    sw = switching_points(blocks, tp, fx_lo=100, fx_hi=220, mat=6.0)
    fx_thresholds = [p["fx"] for p in sw]
    assert 117 in fx_thresholds
    assert 119 in fx_thresholds

    x_values = list(range(100, 221))
    grid = scan_regime_grid(blocks, "fx_usd", x_values, "material_usd", [6.0],
                            transfer_price_usd=tp)

    row = grid["regimes"][0]  # material_usd=6.0 の唯一の行
    # switching_points() の各区間について、regimes の対応する区間が同じ順序であること
    for i, p in enumerate(sw):
        lo = p["fx"]
        hi = sw[i + 1]["fx"] - 1 if i + 1 < len(sw) else 220
        expected_label = ">".join(p["order"])
        for fx in range(lo, hi + 1):
            idx = x_values.index(fx)
            assert row[idx] == expected_label, f"fx={fx}: expected {expected_label}, got {row[idx]}"


def test_regime_map_axis_tariff(soysauce_blocks):
    """tariff_rate:US を軸に取れること"""
    blocks, tp = soysauce_blocks
    grid = scan_regime_grid(blocks, "tariff_rate:US", [0.0, 0.125, 0.30],
                            "fx_usd", [150.0], transfer_price_usd=tp)

    assert grid["axis_x"] == "tariff_rate:US"
    assert len(grid["regimes"]) == 1
    assert len(grid["regimes"][0]) == 3
    # US関税を上げるほどUSのマージンは下がる
    m_low = grid["margins"][0][0]["US"]
    m_high = grid["margins"][0][2]["US"]
    assert m_high < m_low


def test_regime_map_regime_ids_consistent(soysauce_blocks):
    """regime_ids と regime_labels の対応が全点で整合すること"""
    blocks, tp = soysauce_blocks
    grid = scan_regime_grid(blocks, "fx_usd", list(range(100, 221, 5)),
                            "material_usd", [4.0, 6.0, 8.0, 10.0],
                            transfer_price_usd=tp)

    for row_labels, row_ids in zip(grid["regimes"], grid["regime_ids"]):
        for label, rid in zip(row_labels, row_ids):
            assert grid["regime_labels"][rid] == label


def test_regime_map_negative_margin_mask(soysauce_blocks):
    """高FX・高原料の隅で JP が negative_margin_mask に入ること"""
    blocks, tp = soysauce_blocks
    grid = scan_regime_grid(blocks, "fx_usd", [150.0, 220.0],
                            "material_usd", [6.0, 10.0], transfer_price_usd=tp)

    # y=10.0 (index 1), x=220.0 (index 1) の隅
    corner_mask = grid["negative_margin_mask"][1][1]
    assert "JP" in corner_mask

    # 基準点 (150, 6.0) では負マージンなし
    base_mask = grid["negative_margin_mask"][0][0]
    assert base_mask == []


def test_regime_map_invalid_axis(soysauce_blocks):
    """不正な軸名は ValueError"""
    blocks, tp = soysauce_blocks
    with pytest.raises(ValueError):
        scan_regime_grid(blocks, "bogus_axis", [1, 2], "fx_usd", [150.0],
                         transfer_price_usd=tp)
    with pytest.raises(ValueError):
        scan_regime_grid(blocks, "fx_usd", [150.0], "tariff_rate:CN", [0.1],
                         transfer_price_usd=tp)


# ---------------------------------------------------------------------------
# 描画スモークテスト（4件）
# ---------------------------------------------------------------------------

def test_plot_allocation_merit_order(soysauce_blocks, tmp_path):
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, CAP_WK, transfer_price_usd=tp)
    surface = scan_surface(blocks, tp, sc, CAP_WK)
    cmp = compare_with_grid(mo, surface)

    out = str(tmp_path / "merit_order.png")
    assert _nonempty(plot_allocation_merit_order(mo, out, comparison=cmp))


def test_plot_allocation_merit_shift(soysauce_blocks, tmp_path):
    blocks, tp = soysauce_blocks
    mo_before = build_allocation_merit_order(
        blocks, Scenario(fx_usd=115.0, material_usd=6.0), CAP_WK, transfer_price_usd=tp)
    mo_after = build_allocation_merit_order(
        blocks, Scenario(fx_usd=125.0, material_usd=6.0), CAP_WK, transfer_price_usd=tp)

    out = str(tmp_path / "merit_shift.png")
    assert _nonempty(plot_allocation_merit_shift(mo_before, mo_after, out))


def test_plot_regime_map(soysauce_blocks, tmp_path):
    blocks, tp = soysauce_blocks
    grid = scan_regime_grid(blocks, "fx_usd", list(range(100, 221, 5)),
                            "material_usd", [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
                            transfer_price_usd=tp)

    out = str(tmp_path / "regime_map.png")
    assert _nonempty(plot_regime_map(
        grid, out, mark_points=[(150.0, 6.0, "base"), (200.0, 8.0, "shock")]))


def test_cli_demo_generates_all(tmp_path):
    args = parse_args(["--model-dir", MODEL_DIR, "--cap-wk", "800", "--demo",
                       "--out", str(tmp_path)])
    made = run(args)

    assert len(made) == 4
    assert all(_nonempty(p) for p in made)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
