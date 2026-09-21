# -*- coding: utf-8 -*-
"""
tests/test_allocation_merit_order.py — Phase 4 ①メリットオーダー曲線（配分版）のテスト
======================================================================================
設計正典: requests/Phase4_DesignMD_AllocationMeritRegime.md §3 / §7.1
検証台: data/sample/soysauce-jpy-2027-alloc（三角図で答えが出ている唯一のケース）
"""
import os

import pytest

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.transmission import CostBlock, Scenario
from wom.allocation.grid import MARKETS, scan_surface
from wom.allocation.merit_order import build_allocation_merit_order, compare_with_grid

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..",
                         "data", "sample", "soysauce-jpy-2027-alloc")
CAP_WK = 800.0


@pytest.fixture(scope="module")
def soysauce_blocks():
    blocks, tp = derive_cost_blocks(MODEL_DIR)
    return blocks, tp


def test_merit_order_descending(soysauce_blocks):
    """ブロックが単位マージン降順（昇順でない）であること"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, CAP_WK, transfer_price_usd=tp)

    margins = [b["margin"] for b in mo["blocks"]]
    assert margins == sorted(margins, reverse=True)
    # soysauce は EU > US > JP のはず
    assert [b["market"] for b in mo["blocks"]] == ["EU", "US", "JP"]


def test_merit_order_lambda_is_marginal_market_margin(soysauce_blocks):
    """λ が限界市場のマージンと一致すること"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, CAP_WK, transfer_price_usd=tp)

    assert mo["marginal_market"] is not None
    marginal_block = next(b for b in mo["blocks"] if b["market"] == mo["marginal_market"])
    assert mo["lambda"] == marginal_block["margin"]
    assert marginal_block["served"] == "partial"


def test_merit_order_soysauce_regression(soysauce_blocks):
    """soysauce 実データで λ=750, x=(0.1544, 0.4228, 0.4228), 利益 135,529,822.5 JPY"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, CAP_WK, transfer_price_usd=tp)

    assert mo["lambda"] == pytest.approx(750.0)
    assert mo["marginal_market"] == "JP"
    assert mo["x"]["JP"] == pytest.approx(0.1544, abs=1e-4)
    assert mo["x"]["US"] == pytest.approx(0.4228, abs=1e-4)
    assert mo["x"]["EU"] == pytest.approx(0.4228, abs=1e-4)
    assert mo["profit"] == pytest.approx(135_529_822.5, abs=1.0)
    assert mo["idle"] == pytest.approx(0.0, abs=1e-6)
    assert mo["excluded"] == []


def test_merit_order_capacity_surplus():
    """需要合計 < 能力のとき λ=0、marginal_market が None、idle > 0"""
    blocks = {
        "JP": CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                        price_local=200, ccy="JPY", demand_qty=100,
                     material_usd_base=6.0),
        "US": CostBlock(usd=0, eur=0, jpy=150, tariff_rate=0.0,
                        price_local=300, ccy="JPY", demand_qty=100,
                     material_usd_base=6.0),
        "EU": CostBlock(usd=0, eur=0, jpy=120, tariff_rate=0.0,
                        price_local=250, ccy="JPY", demand_qty=100,
                     material_usd_base=6.0),
    }
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    # cap_wk × weeks を需要合計(300)よりずっと大きくする
    mo = build_allocation_merit_order(blocks, sc, cap_wk=100.0, transfer_price_usd=0.0, weeks=10)

    assert mo["cap"] == 1000.0
    assert mo["lambda"] == 0.0
    assert mo["marginal_market"] is None
    assert mo["idle"] == pytest.approx(1000.0 - 300.0)
    for m in MARKETS:
        assert mo["unmet"][m] == 0.0
        # 全市場フル供給
    assert all(b["served"] == "full" for b in mo["blocks"])


def test_merit_order_excludes_negative_margin(soysauce_blocks):
    """FX200/$8 で JP（-105）が excluded に入り、配分されないこと"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=200.0, material_usd=8.0)
    mo = build_allocation_merit_order(blocks, sc, CAP_WK, transfer_price_usd=tp)

    assert "JP" in mo["excluded"]
    assert mo["x"]["JP"] == 0.0
    assert all(b["market"] != "JP" for b in mo["blocks"])
    assert mo["unmet"]["JP"] == blocks["JP"].demand_qty


def test_compare_with_grid_soysauce(soysauce_blocks):
    """グリッド最適 132,133,072.5 JPY、乖離 3,396,750 JPY（+2.57%）"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, CAP_WK, transfer_price_usd=tp)
    surface = scan_surface(blocks, tp, sc, CAP_WK)

    cmp = compare_with_grid(mo, surface)

    assert cmp["grid_best_profit"] == pytest.approx(132_133_072.5, abs=1.0)
    assert cmp["gap_amt"] == pytest.approx(3_396_750.0, abs=1.0)
    assert cmp["gap_pct"] == pytest.approx(0.0257, abs=1e-3)
    assert cmp["grid_best_x"] == pytest.approx((0.10, 0.45, 0.45))


def test_gap_attributable_to_grid_resolution(soysauce_blocks):
    """soysauce では乖離が grid_idle × lambda で厳密に説明でき、構造由来の残差はゼロ"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, CAP_WK, transfer_price_usd=tp)
    surface = scan_surface(blocks, tp, sc, CAP_WK)

    cmp = compare_with_grid(mo, surface)

    assert cmp["absorbable"] is True
    assert cmp["marginal_market"] == "JP"
    # 予測乖離が実測乖離と厳密に一致する（1 JPY 未満）
    assert abs(cmp["expected_gap_from_grid_resolution"] - cmp["gap_amt"]) < 1.0
    assert abs(cmp["structural_residual"]) < 1.0
    assert cmp["attributable_to_grid_resolution"] is True


def test_expected_gap_equals_idle_times_lambda(soysauce_blocks):
    """乖離 = 格子最適点の遊休能力 × λ という恒等式（§3.5 rev.2 の判定の根拠）"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, CAP_WK, transfer_price_usd=tp)
    surface = scan_surface(blocks, tp, sc, CAP_WK)

    cmp = compare_with_grid(mo, surface)

    assert cmp["grid_idle"] == pytest.approx(4529.0)
    assert cmp["lambda"] == pytest.approx(750.0)
    assert cmp["expected_gap_from_grid_resolution"] == pytest.approx(4529.0 * 750.0)
    assert cmp["gap_amt"] == pytest.approx(3396750.0)
    # 限界市場に回せる余地があること
    assert cmp["marginal_unmet_at_grid_best"] >= cmp["grid_idle"]


def test_merit_order_x_sums_to_one_when_capacity_binding(soysauce_blocks):
    """能力が制約になるとき Σx = 1.0"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, CAP_WK, transfer_price_usd=tp)

    assert sum(mo["x"].values()) == pytest.approx(1.0, abs=1e-9)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
