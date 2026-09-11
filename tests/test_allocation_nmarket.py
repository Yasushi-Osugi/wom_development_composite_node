# -*- coding: utf-8 -*-
"""
tests/test_allocation_nmarket.py — N市場経路の End-to-End 回帰
================================================================
Phase 6-2（次元の一般化）で A系統が3市場固定を外したことを、
「双子分割の不変性」で固定する。経済条件が完全に同一の2市場に1市場を
割っても、貪欲法の解と真の連続最適は変わらないはずである——これにより
N市場の正解表を用意せずに N市場経路の正しさを検証できる。

正典: requests/Phase6_DesignMD_NMarketHierarchy.md §4（rev.3）
依頼: requests/Phase6-2a_RequestLetter_to_CodeKun.md
"""
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.grid import scan_surface, best_point, markets_of, demand_ceilings
from wom.allocation.merit_order import build_allocation_merit_order, true_continuous_optimum
from wom.allocation.analytics import market_ranking
from wom.allocation.regime_map import scan_regime_grid
from wom.allocation.transmission import Scenario

ALLOC_DIR = os.path.join(os.path.dirname(__file__), "..",
                         "data", "sample", "soysauce-jpy-2027-alloc")

BLOCKS, TP = derive_cost_blocks(ALLOC_DIR)
SC = Scenario(fx_usd=150.0, material_usd=6.0)
CAP_WK = 800.0


def _twin_split(blocks, market, name_a, name_b):
    """market を、経済条件が同一・需要を折半した双子 (name_a, name_b) に割る。

    需要以外は一切変えない（`dataclasses.replace` で demand_qty のみ差し替え）。
    元の市場の位置に双子を並べる——markets_of() は dict のキー順なので、
    並び順が結果に影響しないことも同時に確認できる。
    """
    src = blocks[market]
    half = src.demand_qty / 2
    out = {}
    for m, cb in blocks.items():
        if m == market:
            out[name_a] = replace(src, demand_qty=half)
            out[name_b] = replace(src, demand_qty=half)
        else:
            out[m] = cb
    return out


BLOCKS4 = _twin_split(BLOCKS, "EU", "EU_A", "EU_B")


def test_markets_of_after_twin_split():
    assert markets_of(BLOCKS) == ("JP", "US", "EU")
    assert markets_of(BLOCKS4) == ("JP", "US", "EU_A", "EU_B")


def test_four_market_twin_split_invariance():
    """双子分割しても貪欲法の解と真の連続最適は1円も変わらないこと（最重要）。"""
    mo3 = build_allocation_merit_order(BLOCKS,  SC, cap_wk=CAP_WK, transfer_price_usd=TP)
    mo4 = build_allocation_merit_order(BLOCKS4, SC, cap_wk=CAP_WK, transfer_price_usd=TP)

    assert mo4["profit"] == mo3["profit"] == pytest.approx(135_529_822.5, abs=1e-6)
    assert mo4["lambda"] == mo3["lambda"] == pytest.approx(750.0, abs=1e-9)
    assert mo4["marginal_market"] == mo3["marginal_market"] == "JP"
    assert mo4["idle"] == mo3["idle"] == pytest.approx(0.0, abs=1e-6)
    assert mo4["excluded"] == mo3["excluded"] == []

    # 分割されていない市場の配分比率は不変
    assert mo4["x"]["JP"] == pytest.approx(mo3["x"]["JP"], abs=1e-12)
    assert mo4["x"]["US"] == pytest.approx(mo3["x"]["US"], abs=1e-12)
    # 双子は等分され、合計は元の EU と一致する
    assert mo4["x"]["EU_A"] == pytest.approx(mo4["x"]["EU_B"], abs=1e-12)
    assert mo4["x"]["EU_A"] + mo4["x"]["EU_B"] == pytest.approx(mo3["x"]["EU"], abs=1e-12)

    # 真の連続最適も同じく不変（cliff が無いので 2^0 = 1 ケース）
    to3 = true_continuous_optimum(BLOCKS,  SC, cap_wk=CAP_WK, transfer_price_usd=TP)
    to4 = true_continuous_optimum(BLOCKS4, SC, cap_wk=CAP_WK, transfer_price_usd=TP)
    assert to4["profit"] == to3["profit"] == pytest.approx(135_529_822.5, abs=1e-6)
    assert to4["cases_evaluated"] == to3["cases_evaluated"] == 1


def test_four_market_grid_degrades_with_dimension():
    """格子だけは次元の増加で劣化すること（Phase 6-3 が必要な理由を金額で固定）。"""
    s3 = scan_surface(BLOCKS,  TP, SC, cap_wk=CAP_WK)
    s4 = scan_surface(BLOCKS4, TP, SC, cap_wk=CAP_WK)
    assert len(s3) == 231 and len(s4) == 1_771

    b3, p3 = best_point(s3)
    b4, p4 = best_point(s4)
    assert b3 == pytest.approx(132_133_072.5, abs=1.0)
    assert b4 == pytest.approx(131_782_380.0, abs=1.0)
    assert b3 - b4 == pytest.approx(350_692.5, abs=1.0)

    # 格子は貪欲法の解に届かない（劣化の向きが逆転しないこと）
    assert b4 < b3 < 135_529_822.5
    assert len(p3) == 1 and len(p4) == 1


def test_four_market_pipeline_runs():
    """A系統の各モジュールが N=4 で動き、4市場すべてを扱うこと。"""
    # 需要天井: 双子は折半され、他は不変
    c3 = demand_ceilings(BLOCKS,  CAP_WK)
    c4 = demand_ceilings(BLOCKS4, CAP_WK)
    assert set(c4) == {"JP", "US", "EU_A", "EU_B"}
    assert c4["JP"] == pytest.approx(c3["JP"], abs=1e-12)
    assert c4["EU_A"] == c4["EU_B"] == pytest.approx(c3["EU"] / 2, abs=1e-12)

    # 単位マージン順位: EU が双子に展開されるだけで相対順位は変わらない
    assert market_ranking(BLOCKS,  TP, 150.0) == ("EU", "US", "JP")
    assert market_ranking(BLOCKS4, TP, 150.0) == ("EU_A", "EU_B", "US", "JP")

    # レジーム地図: ラベルが4市場ぶんになること＋双子の一方だけを軸にできること
    rg = scan_regime_grid(BLOCKS4, x_values=[115.0, 150.0, 200.0], y_values=[0.0, 0.125],
                          axis_x="fx_usd", axis_y="tariff_rate:EU_B",
                          transfer_price_usd=TP)
    for row in rg["regimes"]:
        for label in row:
            assert len(label.split(">")) == 4
            assert set(label.split(">")) == {"JP", "US", "EU_A", "EU_B"}
    # EU_B にだけ関税を掛けると、双子の順位が入れ替わること
    #（y=0.0 では EU_B が EU_A より上、y=0.125 では下）
    def _pos(label, mkt):
        return label.split(">").index(mkt)
    lo, hi = rg["regimes"][0][1], rg["regimes"][1][1]      # fx=150 の列
    assert _pos(lo, "EU_B") < _pos(lo, "EU_A")
    assert _pos(hi, "EU_B") > _pos(hi, "EU_A")

    # 存在しない市場を軸に指定したら、4市場すべてを挙げてエラーになること
    with pytest.raises(ValueError, match="EU_A"):
        scan_regime_grid(BLOCKS4, x_values=[150.0], y_values=[0.0],
                         axis_x="fx_usd", axis_y="tariff_rate:ZZ",
                         transfer_price_usd=TP)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
