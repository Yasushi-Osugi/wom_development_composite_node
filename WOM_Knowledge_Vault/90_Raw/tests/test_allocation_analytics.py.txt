# -*- coding: utf-8 -*-
"""
tests/test_allocation_analytics.py — 切替点・交互作用・robust_point・制約コスト
============================================================================
`wom/allocation/analytics.py` が proto / Request Letter 付録 A.4・A.5・§5.6b を
再現することを固定する。受け入れ基準 #14（切替点 119/117）・#15（robust_point）に対応。
交互作用は §3.2/§A.5 の「主役級」を数値で確認する。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.grid import scan_surface, best_point
from wom.allocation.analytics import (
    market_ranking, switching_points, interaction, robust_point, constraint_cost,
)
from wom.allocation.transmission import Scenario

ALLOC_DIR = os.path.join(os.path.dirname(__file__), "..",
                         "data", "sample", "soysauce-jpy-2027-alloc")
BLOCKS, TP = derive_cost_blocks(ALLOC_DIR)


# --- 切替点（#14: 117 / 119 円） ---------------------------------------------
def test_switching_points_117_119():
    pts = switching_points(BLOCKS, TP, fx_lo=100, fx_hi=220)
    fxs = [p["fx"] for p in pts]
    orders = {p["fx"]: p["order"] for p in pts}
    assert fxs == [100, 117, 119]
    assert orders[100] == ("JP", "EU", "US")   # 円高: 国内最優先
    assert orders[117] == ("EU", "JP", "US")   # JP が 2 位へ
    assert orders[119] == ("EU", "US", "JP")   # 米国が JP を抜く（JP 最下位）


def test_market_ranking_endpoints():
    assert market_ranking(BLOCKS, TP, 150) == ("EU", "US", "JP")   # 基準（円安寄り）
    assert market_ranking(BLOCKS, TP, 100)[0] == "JP"              # 円高で国内首位


# --- 交互作用（§3.2 / §A.5・主役級） ------------------------------------------
def test_interaction_base_point():
    r = interaction((0.30, 0.35, 0.35), BLOCKS, TP, cap_wk=800)
    assert r["fx_only"] / 1e6 == pytest.approx(54.0, abs=0.1)
    assert r["mat_only"] / 1e6 == pytest.approx(-25.0, abs=0.1)
    assert r["total"] / 1e6 == pytest.approx(20.7, abs=0.1)
    assert r["interaction"] / 1e6 == pytest.approx(-8.3, abs=0.1)
    assert r["ratio"] == pytest.approx(-0.402, abs=0.005)
    assert r["layer_decomposition_valid"] is False   # 5% 超 → 層分解は無効


def test_interaction_sign_flip_point():
    """(0.60,0.20,0.20): 単独和は +だが実測は −（交互作用が符号を反転）。"""
    r = interaction((0.60, 0.20, 0.20), BLOCKS, TP, cap_wk=800)
    assert r["total"] / 1e6 == pytest.approx(-1.8, abs=0.1)
    assert r["interaction"] / 1e6 == pytest.approx(-6.3, abs=0.1)
    assert (r["fx_only"] + r["mat_only"]) > 0 and r["total"] < 0   # 符号反転


# --- robust_point（#15 / §5.6b・ミニマックス） --------------------------------
def test_robust_point_on_compound_plateau():
    # 円安×原油（能力800・200円・$8）の台地3点でミニマックス
    surf = scan_surface(BLOCKS, TP, Scenario(fx_usd=200, material_usd=8.0), cap_wk=800)
    _best, plateau = best_point(surf)
    assert len(plateau) == 3
    scen = [Scenario(fx_usd=150, material_usd=6.0), Scenario(fx_usd=200, material_usd=6.0),
            Scenario(fx_usd=200, material_usd=8.0), Scenario(fx_usd=115, material_usd=6.0)]
    rp = robust_point(plateau, BLOCKS, TP, scen, cap_wk=800)
    plateau_xs = [tuple(r["x"]) for r in plateau]
    assert rp["robust_point"] in plateau_xs
    # ミニマックス点の最悪利益は、素朴な argmax[0] の最悪利益以上
    from wom.allocation.grid import evaluate_point
    naive_worst = min(evaluate_point(plateau[0]["x"], BLOCKS, TP, s, 800)["profit"] for s in scen)
    assert rp["robust_worst_profit"] >= naive_worst - 1e-6


# --- constraint_cost（§5.6b・国内20%フロア） ----------------------------------
def test_constraint_cost_domestic_floor():
    # 複合ショックでは無制約最適が x_JP=0.00（国内停止）。国内20%維持のコストを測る。
    sc = Scenario(fx_usd=200, material_usd=8.0)
    r = constraint_cost(BLOCKS, TP, sc, cap_wk=800, constraint=lambda x: x[0] >= 0.20)
    assert r["cost_of_constraint"] > 0                     # 制約は利益を削る
    assert r["profit_constrained"] < r["profit_unconstrained"]
    assert 0 < r["feasible_points"] < 231


if __name__ == "__main__":
    test_switching_points_117_119()
    test_market_ranking_endpoints()
    test_interaction_base_point()
    test_interaction_sign_flip_point()
    test_robust_point_on_compound_plateau()
    test_constraint_cost_domestic_floor()
    print("All allocation analytics tests passed.")
