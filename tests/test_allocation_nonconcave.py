# -*- coding: utf-8 -*-
"""
tests/test_allocation_nonconcave.py — Phase 5：数量依存関税（cliff型）と構造的乖離の検証
================================================================================================
設計正典: requests/Phase5_DesignMD_NonConcaveTariff.md
検証台: data/sample/soysauce-jpy-2027-alloc（s1_base=Phase4回帰、s9_fta_cliff=非凹性の合成シナリオ）
"""
import os
from dataclasses import replace

import pytest

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.transmission import CostBlock, Scenario, unit_pnl, unit_pnl_at_quantity
from wom.allocation.grid import MARKETS, scan_surface, best_point
from wom.allocation.merit_order import (
    build_allocation_merit_order, compare_with_grid, true_continuous_optimum,
)
from tools.run_allocation_map import load_scenarios, _blocks_for

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..",
                         "data", "sample", "soysauce-jpy-2027-alloc")


@pytest.fixture(scope="module")
def soysauce_blocks():
    """s1_base 相当（cliff未設定）。Phase 4 の回帰値と一致するはず。"""
    return derive_cost_blocks(MODEL_DIR)


@pytest.fixture(scope="module")
def s9_blocks():
    """s9_fta_cliff（US: 12.5%→0%、25,000lot以上で発動）。cap_wk=500 前提。"""
    base_blocks, tp = derive_cost_blocks(MODEL_DIR)
    scens = {s["id"]: s for s in load_scenarios(MODEL_DIR)}
    s9 = scens["s9_fta_cliff"]
    blocks = _blocks_for(base_blocks, s9["tariff"],
                         s9["tariff_preferential"], s9["preferential_threshold"])
    sc = Scenario(fx_usd=s9["fx_usd"], material_usd=s9["material_usd"])
    return blocks, tp, sc, 500.0


# ---------------------------------------------------------------------------
# 7.1 後方互換（4件）
# ---------------------------------------------------------------------------

def test_tariff_at_returns_base_when_no_cliff():
    """tariff_rate_preferential=None なら tariff_at(qty) が常に tariff_rate"""
    cb = CostBlock(usd=0, eur=0, jpy=0, tariff_rate=0.125,
                   price_local=100, ccy="JPY", demand_qty=10)
    assert cb.tariff_at(0) == 0.125
    assert cb.tariff_at(1e9) == 0.125


def test_unit_pnl_at_quantity_matches_unit_pnl_without_cliff(soysauce_blocks):
    """cliff なしで unit_pnl_at_quantity() と unit_pnl() が完全一致"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    for m in MARKETS:
        base = unit_pnl(blocks[m], sc, tp)
        for qty in (0.0, 1000.0, 1e9):
            at_qty = unit_pnl_at_quantity(blocks[m], sc, qty, tp)
            assert at_qty == base


def test_phase4_regression_unchanged(soysauce_blocks):
    """soysauce s1_base / cap_wk=800 で Phase 4 の回帰値が1円も変わらない"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, 800.0, transfer_price_usd=tp)

    assert mo["lambda"] == pytest.approx(750.0)
    assert mo["x"]["JP"] == pytest.approx(0.1544, abs=1e-4)
    assert mo["x"]["US"] == pytest.approx(0.4228, abs=1e-4)
    assert mo["x"]["EU"] == pytest.approx(0.4228, abs=1e-4)
    assert mo["profit"] == pytest.approx(135_529_822.5, abs=1.0)
    assert mo["preferential"] is None

    surface = scan_surface(blocks, tp, sc, 800.0)
    best, plateau = best_point(surface)
    assert best == pytest.approx(132_133_072.5, abs=1.0)
    assert plateau[0]["x"] == pytest.approx((0.10, 0.45, 0.45))


def test_evaluate_point_unchanged_without_cliff(soysauce_blocks):
    """evaluate_point() の改修後も cliff なしの結果が全231点で不変
    （数量に依存しない従来の unit_pnl() だけで独立に再計算し、一致を確認）"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    cap = 800.0 * 104
    surface = scan_surface(blocks, tp, sc, 800.0)

    ue = {m: unit_pnl(blocks[m], sc, tp) for m in MARKETS}
    for pt in surface:
        x = pt["x"]
        q = {m: min(xi * cap, blocks[m].demand_qty) for m, xi in zip(MARKETS, x)}
        expected_profit = (sum(q[m] * ue[m]["rev"] for m in MARKETS)
                           - sum(q[m] * ue[m]["cost"] for m in MARKETS))
        assert pt["profit"] == pytest.approx(expected_profit, abs=1e-6)


# ---------------------------------------------------------------------------
# 7.2 cliff の動作（4件）
# ---------------------------------------------------------------------------

def test_tariff_at_switches_at_threshold():
    """qty が閾値の前後で税率が切り替わる（境界値 qty==T は特恵側）"""
    cb = CostBlock(usd=0, eur=0, jpy=0, tariff_rate=0.125,
                   price_local=100, ccy="JPY", demand_qty=100,
                   tariff_rate_preferential=0.0, preferential_threshold_lot=50)
    assert cb.tariff_at(49) == 0.125
    assert cb.tariff_at(49.999) == 0.125
    assert cb.tariff_at(50) == 0.0
    assert cb.tariff_at(51) == 0.0


def test_preferential_flips_ranking(s9_blocks):
    """US に特恵が発動すると単価 2,077.5 > EU 1,831.5 で順位が逆転する"""
    blocks, tp, sc, _cap_wk = s9_blocks
    us_margin_triggered = unit_pnl_at_quantity(blocks["US"], sc, 25000.0, tp)["margin"]
    eu_margin = unit_pnl(blocks["EU"], sc, tp)["margin"]
    assert us_margin_triggered == pytest.approx(2077.5, abs=0.1)
    assert eu_margin == pytest.approx(1831.5, abs=0.1)
    assert us_margin_triggered > eu_margin


def test_merit_order_is_myopic(s9_blocks):
    """①が閾値を先読みしない（s9_fta_cliff で US=16,825 に留まり triggered=False）"""
    blocks, tp, sc, cap_wk = s9_blocks
    mo = build_allocation_merit_order(blocks, sc, cap_wk, transfer_price_usd=tp)

    # 順位付けは base rate（1747.5 < 1831.5）のまま：EU が先、US が次
    # （JP は base margin=750>0 なのでリストには残るが、cap が US で尽きるため配分0=none）
    order = [b["market"] for b in mo["blocks"]]
    assert order == ["EU", "US", "JP"]

    jp_block = next(b for b in mo["blocks"] if b["market"] == "JP")
    assert jp_block["allocated"] == pytest.approx(0.0)
    assert jp_block["served"] == "none"

    us_block = next(b for b in mo["blocks"] if b["market"] == "US")
    assert us_block["allocated"] == pytest.approx(16825.0)
    assert mo["preferential"]["US"]["triggered"] is False
    assert mo["preferential"]["US"]["threshold"] == 25000.0


def test_merit_order_profit_uses_effective_margin():
    """利益計算は実配分量に応じた単価を使う（順位付けの単価ではない）"""
    sc = Scenario(fx_usd=1.0, material_usd=0.0)
    transfer_price_usd = 10.0
    blocks = {
        # JP/EU は負マージンにして除外（US だけが配分対象になるよう単純化）
        "JP": CostBlock(usd=0, eur=0, jpy=0, tariff_rate=0.0, price_local=-100,
                        ccy="JPY", demand_qty=10, material_usd_base=0.0),
        "EU": CostBlock(usd=0, eur=0, jpy=0, tariff_rate=0.0, price_local=-100,
                        ccy="JPY", demand_qty=10, material_usd_base=0.0),
        "US": CostBlock(usd=0, eur=0, jpy=0, tariff_rate=0.20, price_local=100,
                        ccy="JPY", demand_qty=1000, material_usd_base=0.0,
                        tariff_rate_preferential=0.0, preferential_threshold_lot=50),
    }
    # cap_wk=200, weeks=1 -> cap=200 lot。US demand(1000) > cap なので allocated=200(>=50=threshold)
    mo = build_allocation_merit_order(blocks, sc, cap_wk=200.0,
                                      transfer_price_usd=transfer_price_usd, weeks=1)

    us_block = next(b for b in mo["blocks"] if b["market"] == "US")
    assert us_block["allocated"] == pytest.approx(200.0)
    assert us_block["margin"] == pytest.approx(98.0)              # ランキング単価（base rate）
    assert us_block["margin_effective"] == pytest.approx(100.0)   # 実配分単価（特恵発動）
    assert mo["preferential"]["US"]["triggered"] is True

    # 利益は margin_effective ベース（200*100=20000）であり、
    # margin（ランキング）ベースの 200*98=19600 ではない
    assert mo["profit"] == pytest.approx(20000.0)


# ---------------------------------------------------------------------------
# 7.3 構造的乖離の検出（3件）
# ---------------------------------------------------------------------------

def test_s9_cliff_regression(s9_blocks):
    """s9_fta_cliff / cap_wk=500 で ① 93,824,700 JPY、格子最適 103,552,800 JPY、
    x=(0.00,0.65,0.35)"""
    blocks, tp, sc, cap_wk = s9_blocks
    mo = build_allocation_merit_order(blocks, sc, cap_wk, transfer_price_usd=tp)
    assert mo["profit"] == pytest.approx(93_824_700.0, abs=1.0)

    surface = scan_surface(blocks, tp, sc, cap_wk)
    best, plateau = best_point(surface)
    assert best == pytest.approx(103_552_800.0, abs=1.0)
    assert plateau[0]["x"] == pytest.approx((0.00, 0.65, 0.35))
    assert plateau[0]["idle"] == pytest.approx(0.0, abs=1e-6)


def test_structural_residual_is_negative(s9_blocks):
    """residual ≈ -9,728,100 で負、attributable_to_grid_resolution が False"""
    blocks, tp, sc, cap_wk = s9_blocks
    mo = build_allocation_merit_order(blocks, sc, cap_wk, transfer_price_usd=tp)
    surface = scan_surface(blocks, tp, sc, cap_wk)

    cmp = compare_with_grid(mo, surface)
    assert cmp["gap_amt"] == pytest.approx(-9_728_100.0, abs=1.0)
    assert cmp["expected_gap_from_grid_resolution"] == pytest.approx(0.0, abs=1e-6)
    assert cmp["structural_residual"] == pytest.approx(-9_728_100.0, abs=1.0)
    assert cmp["structural_residual"] < 0
    assert cmp["attributable_to_grid_resolution"] is False


def test_residual_underestimates_true_gap(s9_blocks):
    """真の連続最適 103,891,296.0（Phase 6-1 で true_continuous_optimum() が実計算した
    回帰値）に対し、|residual| が構造由来の取りこぼし 10,066,596 の下界であること（96.6%）"""
    blocks, tp, sc, cap_wk = s9_blocks
    mo = build_allocation_merit_order(blocks, sc, cap_wk, transfer_price_usd=tp)
    surface = scan_surface(blocks, tp, sc, cap_wk)
    cmp = compare_with_grid(mo, surface)

    # true_continuous_optimum() を実計算で呼ぶ（ハードコードしない）。
    # ケースが変わっても自動追従する。
    true_optimum = true_continuous_optimum(blocks, sc, cap_wk, transfer_price_usd=tp)
    true_optimum_profit = true_optimum["profit"]
    assert true_optimum_profit == pytest.approx(103_891_296.0, abs=1.0)
    true_structural_gap = true_optimum_profit - mo["profit"]
    assert true_structural_gap == pytest.approx(10_066_596.0, abs=1.0)

    ratio = abs(cmp["structural_residual"]) / true_structural_gap
    assert ratio == pytest.approx(0.966, abs=0.005)
    assert abs(cmp["structural_residual"]) <= true_structural_gap  # 下界であること


# ---------------------------------------------------------------------------
# 7.4 シナリオ読込（2件）
# ---------------------------------------------------------------------------

def test_scenario_csv_loads_cliff_columns():
    """s9_fta_cliff の US 行から特恵税率と閾値が読める"""
    scens = {s["id"]: s for s in load_scenarios(MODEL_DIR)}
    s9 = scens["s9_fta_cliff"]
    assert s9["tariff_preferential"] == {"US": 0.0}
    assert s9["preferential_threshold"] == {"US": 25000.0}

    # 既存シナリオは cliff 列が空欄 -> 空 dict（従来動作）
    s1 = scens["s1_base"]
    assert s1["tariff_preferential"] == {}
    assert s1["preferential_threshold"] == {}


def test_scenario_csv_missing_columns_ok(tmp_path):
    """2列が存在しない古い CSV でも例外にならない"""
    csv_content = (
        "scenario_id,quarter,market,currency,tariff_rate,fx_spot_jpy,"
        "material_price_usd,interest_rate_annual,note\n"
        "sX,2027Q1,JP,JPY,0.000,1.00,6.00,0.030,\n"
        "sX,2027Q1,US,USD,0.125,150.00,6.00,0.030,\n"
        "sX,2027Q1,EU,EUR,0.080,162.00,6.00,0.030,\n"
    )
    (tmp_path / "ga_scenario_master.csv").write_text(csv_content, encoding="utf-8")

    scens = load_scenarios(str(tmp_path))
    assert len(scens) == 1
    assert scens[0]["tariff_preferential"] == {}
    assert scens[0]["preferential_threshold"] == {}


# ---------------------------------------------------------------------------
# 7.5 Phase 6-1: true_continuous_optimum()（7件）
# 正典: requests/Phase6-1_RequestLetter_to_CodeKun.md V4
# ---------------------------------------------------------------------------

def test_true_optimum_s9_regression(s9_blocks):
    """s9_fta_cliff の真の連続最適 103,891,296.0 JPY（Phase 6-1 で実装確定した回帰値）。

    設計書§2.3の手計算値 103,881,758.0 は誤りだった（配分 JP=7/US=35,168/EU=16,825 は
    最適ではなく、US +8 lot・JP -7 lot で +9,538.5 円改善できる）。この実装が正しい
    最適点 JP=0/US=35,176/EU=16,824 を検出したことで判明した（Request Letter V4.1 追記）。
    """
    blocks, tp, sc, cap_wk = s9_blocks
    result = true_continuous_optimum(blocks, sc, cap_wk, transfer_price_usd=tp)

    assert result["profit"] == pytest.approx(103_891_296.0, abs=1.0)
    assert "US" in result["active_cliffs"]
    assert result["idle"] == pytest.approx(0.0, abs=1e-6)


def test_true_optimum_case_a_matches_greedy(s9_blocks):
    """ケース S={}（US が特恵未発動）を単独で解いた利益が、①メリットオーダーの
    実測値 93,824,700.0 と厳密一致すること（±1 JPY）。

    ケース内ソルバ（Request Letter V1.2 手順4）が正しいことの直接の証拠。
    """
    blocks, tp, sc, cap_wk = s9_blocks
    result = true_continuous_optimum(blocks, sc, cap_wk, transfer_price_usd=tp,
                                     _return_all_cases=True)

    case_a = next(c for c in result["_all_cases"] if c["active_cliffs"] == ())
    assert case_a["feasible"] is True
    assert case_a["profit"] == pytest.approx(93_824_700.0, abs=1.0)


def test_true_optimum_respects_threshold_lower_bound(s9_blocks):
    """閾値制約が binding になる合成ケースで、下界制約を持たない素朴な解法
    （設計書§3.3の事後チェック方式）では取り逃す解が正しく拾えること。

    US の特恵マージンが EU の基本マージンよりわずかに低くなるよう調整する。
    こうすると「US が特恵を発動する」ケースでも US の順位が EU より下になり、
    下界制約（先に閾値まで確保する）が無ければ US は閾値未満で止まってしまう
    ——これが Request Letter V1.2 が §3.3 を置き換える理由そのもの。
    """
    blocks, tp, sc, cap_wk = s9_blocks
    us_cb = blocks["US"]
    eu_margin = unit_pnl(blocks["EU"], sc, tp)["margin"]

    # US の特恵税率を、発動時マージンが EU の基本マージンよりわずかに
    # (1.5 JPY) 低くなる値まで二分探索で調整する（tariff_rate と margin の
    # 線形係数をハードコードせず、unit_pnl() を直接使って数値的に求める）
    target_margin = eu_margin - 1.5
    lo, hi = 0.0, us_cb.tariff_rate
    for _ in range(60):
        mid = (lo + hi) / 2.0
        m = unit_pnl(replace(us_cb, tariff_rate=mid), sc, tp)["margin"]
        if m > target_margin:
            lo = mid
        else:
            hi = mid
    rate_pref = (lo + hi) / 2.0

    adjusted_us = replace(us_cb, tariff_rate_preferential=rate_pref)
    adjusted_blocks = dict(blocks)
    adjusted_blocks["US"] = adjusted_us

    triggered_margin = unit_pnl_at_quantity(adjusted_us, sc, 25000.0, tp)["margin"]
    assert triggered_margin < eu_margin   # 前提の確認：発動してもEUより低い単価のまま

    result = true_continuous_optimum(adjusted_blocks, sc, cap_wk, transfer_price_usd=tp)

    assert "US" in result["active_cliffs"]
    assert result["q"]["US"] >= adjusted_us.preferential_threshold_lot - 1e-6
    assert result["cases_feasible"] >= 2   # S={} と S={US} の両方が実行可能


def test_true_optimum_equals_greedy_when_linear(soysauce_blocks):
    """cliff が無ければ真の連続最適は貪欲法の解と厳密一致する
    （線形なら均等限界原理が成立し、貪欲法が厳密解を与えるため）"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, 800.0, transfer_price_usd=tp)
    result = true_continuous_optimum(blocks, sc, 800.0, transfer_price_usd=tp)

    assert result["profit"] == pytest.approx(mo["profit"], abs=1.0)
    assert result["profit"] == pytest.approx(135_529_822.5, abs=1.0)
    assert result["cases_evaluated"] == 1
    assert result["active_cliffs"] == []


def test_true_optimum_is_upper_bound(soysauce_blocks, s9_blocks):
    """真の連続最適は、格子最適・貪欲法の利益のいずれも下回らない
    （格子は連続空間の部分集合。貪欲法は最適を超えない）。

    structural_residual が下界であることの根拠そのもの。
    """
    blocks1, tp1 = soysauce_blocks
    sc1 = Scenario(fx_usd=150.0, material_usd=6.0)
    mo1 = build_allocation_merit_order(blocks1, sc1, 800.0, transfer_price_usd=tp1)
    surf1 = scan_surface(blocks1, tp1, sc1, 800.0)
    grid_best1, _ = best_point(surf1)
    true1 = true_continuous_optimum(blocks1, sc1, 800.0, transfer_price_usd=tp1)
    assert true1["profit"] >= grid_best1 - 1e-6
    assert true1["profit"] >= mo1["profit"] - 1e-6

    blocks9, tp9, sc9, cap_wk9 = s9_blocks
    mo9 = build_allocation_merit_order(blocks9, sc9, cap_wk9, transfer_price_usd=tp9)
    surf9 = scan_surface(blocks9, tp9, sc9, cap_wk9)
    grid_best9, _ = best_point(surf9)
    true9 = true_continuous_optimum(blocks9, sc9, cap_wk9, transfer_price_usd=tp9)
    assert true9["profit"] >= grid_best9 - 1e-6
    assert true9["profit"] >= mo9["profit"] - 1e-6


def test_compare_with_grid_backward_compatible(soysauce_blocks):
    """true_optimum を渡さない compare_with_grid() の返却が Phase 5 と完全に同一
    であること（追加4キーは None）"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, 800.0, transfer_price_usd=tp)
    surface = scan_surface(blocks, tp, sc, 800.0)

    cmp = compare_with_grid(mo, surface)

    assert cmp["merit_order_profit"] == pytest.approx(135_529_822.5, abs=1.0)
    assert cmp["grid_best_profit"] == pytest.approx(132_133_072.5, abs=1.0)
    assert cmp["gap_amt"] == pytest.approx(3_396_750.0, abs=1.0)
    assert cmp["structural_residual"] == pytest.approx(0.0, abs=1.0)
    assert cmp["attributable_to_grid_resolution"] is True

    assert cmp["true_optimum"] is None
    assert cmp["structural_optimality_gap"] is None
    assert cmp["grid_resolution_error"] is None
    assert cmp["residual_coverage"] is None


def test_residual_coverage_none_when_linear(soysauce_blocks):
    """s1_base（線形）で structural_optimality_gap==0 のとき residual_coverage は
    None であること（ゼロ除算も nan も発生しない）"""
    blocks, tp = soysauce_blocks
    sc = Scenario(fx_usd=150.0, material_usd=6.0)
    mo = build_allocation_merit_order(blocks, sc, 800.0, transfer_price_usd=tp)
    surface = scan_surface(blocks, tp, sc, 800.0)
    true_opt = true_continuous_optimum(blocks, sc, 800.0, transfer_price_usd=tp)

    cmp = compare_with_grid(mo, surface, true_optimum=true_opt)

    assert cmp["structural_optimality_gap"] == pytest.approx(0.0, abs=1.0)
    assert cmp["residual_coverage"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
