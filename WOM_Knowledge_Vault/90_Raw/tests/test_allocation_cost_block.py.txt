# -*- coding: utf-8 -*-
"""
tests/test_allocation_cost_block.py — Step 0.5 導出器の Integration テスト
=========================================================================
`wom/allocation/cost_block.py` が **実 CSV → ローダ → CostBlock** の経路を実際に通し、
参照実装 proto_terrain2.py / 仕様 §5.1 の導出値を再現することを固定する。

これは「CSV → ローダ → データ経路欠落」（cap_soft / init_stock_days と同型の休眠）を
機械的に防ぐ層（Request Letter §2.4 / CLAUDE.md §10）。受け入れ基準 #10 に対応。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.transmission import Scenario, unit_pnl

ALLOC_DIR = os.path.join(os.path.dirname(__file__), "..",
                         "data", "sample", "soysauce-jpy-2027-alloc")


def _blocks():
    return derive_cost_blocks(ALLOC_DIR)


# --- 導出ブロックが proto / §5.1 導出表と一致 ---------------------------------
def test_derived_blocks_match_prototype():
    blocks, _tp = _blocks()
    assert set(blocks) == {"JP", "US", "EU"}

    jp = blocks["JP"]
    assert jp.usd == pytest.approx(9.10, abs=1e-6)
    assert jp.eur == pytest.approx(0.0, abs=1e-6)
    assert jp.jpy == pytest.approx(1725.0, abs=1e-6)
    assert jp.tariff_rate == pytest.approx(0.0, abs=1e-6)
    assert jp.price_local == pytest.approx(3840.0) and jp.ccy == "JPY"
    assert jp.demand_qty == 30150

    us = blocks["US"]
    assert us.usd == pytest.approx(15.65, abs=1e-6)   # SF/NY 1:1 平均（4.0/4.5→4.25）
    assert us.eur == pytest.approx(0.0, abs=1e-6)
    assert us.jpy == pytest.approx(1575.0, abs=1e-6)
    assert us.tariff_rate == pytest.approx(0.125, abs=1e-6)
    assert us.price_local == pytest.approx(40.0) and us.ccy == "USD"
    assert us.demand_qty == 35176

    eu = blocks["EU"]
    assert eu.usd == pytest.approx(14.60, abs=1e-6)
    assert eu.eur == pytest.approx(2.15, abs=1e-6)
    assert eu.jpy == pytest.approx(1575.0, abs=1e-6)
    assert eu.tariff_rate == pytest.approx(0.08, abs=1e-6)
    assert eu.price_local == pytest.approx(38.0) and eu.ccy == "EUR"
    assert eu.demand_qty == 35175


def test_transfer_price_usd():
    _blocks_, tp = _blocks()
    assert tp == pytest.approx(17.6, abs=1e-6)   # 2400/150 × 1.1


def test_material_base_is_six():
    blocks, _ = _blocks()
    for cb in blocks.values():
        assert cb.material_usd_base == pytest.approx(6.0, abs=1e-6)


# --- 受入 #10: 導出ブロック × transmission が §5.1 の JP マージン4点を再現 ----------
@pytest.mark.parametrize("fx,mat,exp_pct", [
    (150, 6.0,  19.53),
    (200, 6.0,   7.68),
    (200, 8.0,  -2.73),
    (200, 6.5,   5.08),
])
def test_jp_margin_pct_4points(fx, mat, exp_pct):
    blocks, _ = _blocks()
    jp = blocks["JP"]
    u = unit_pnl(jp, Scenario(fx_usd=fx, material_usd=mat))
    got_pct = 100.0 * u["margin"] / u["rev"]
    assert got_pct == pytest.approx(exp_pct, abs=0.1), f"JP@FX{fx}/${mat}: {got_pct:.2f}% != {exp_pct}% (±0.1pp)"


def test_derivation_conservation_identity():
    """§5.1 恒等式：導出ブロック合計 × レート = unit_cost_ex_tariff（保存性）。"""
    blocks, _ = _blocks()
    sc = Scenario(fx_usd=150, material_usd=6.0)
    r = {"JPY": 1.0, "USD": 150.0, "EUR": 162.0}
    for cb in blocks.values():
        # 関税前 unit_cost = usd×fx + eur×eur_rate + jpy（tariff_rate=... は除く）
        ex_tariff = cb.usd * r["USD"] + cb.eur * r["EUR"] + cb.jpy
        u = unit_pnl(cb, sc)  # 関税込み
        duty = cb.tariff_rate * (16.0 * 1.1) * r["USD"]
        assert u["cost"] == pytest.approx(ex_tariff + duty, abs=1e-6)


if __name__ == "__main__":
    test_derived_blocks_match_prototype()
    test_transfer_price_usd()
    test_material_base_is_six()
    for a in [(150,6.0,19.53),(200,6.0,7.68),(200,8.0,-2.73),(200,6.5,5.08)]:
        test_jp_margin_pct_4points(*a)
    test_derivation_conservation_identity()
    print("All cost_block derivation tests passed.")
