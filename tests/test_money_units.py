# -*- coding: utf-8 -*-
"""
tests/test_money_units.py — RequestLetter_StalePPC_Units_KittingView P4

money の units（Landed Cost の運賃・KD 組立費に使う lot 数）は、市場へ売った数量である。
計画の DataFrame には、市場 leaf の行のほかに DAD（DC）の行（地域が "DAD:…"）があり、同じ lot が
DC を通るたびにもう一度現れる。P4 の前は、その行も合計していたので、units が 2 倍（DAD 1 段）・
3 倍（2 段）になり、運賃が同じ倍率で過大だった。方式（legacy／identity）によらない数え方の誤り。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from wom.data.schema import Cols
from wom.engine.money import evaluate_money, build_scenario_money_kpi, is_dad_region

SKU_MASTER = pd.DataFrame([
    {"sku_id": "A", "region": "JP", "selling_price": 100.0, "unit_cost": 60.0, "dso_wks": 6, "dpo_wks": 8},
    {"sku_id": "A", "region": "US", "selling_price": 120.0, "unit_cost": 60.0, "dso_wks": 6, "dpo_wks": 8},
])


def _rows(basis):
    """市場 2 つ（JP 10、US 5）と、2 段の DAD（どちらも 15 lot が通る）。"""
    out = []
    for region, qty in (("JP", 10.0), ("US", 5.0), ("DAD:Buffer", 15.0), ("DAD:Main", 15.0)):
        for wk in ("2026-W01", "2026-W02"):
            out.append({Cols.SCENARIO: "Planning", Cols.SKU_ID: "A", Cols.REGION: region, Cols.WEEK: wk,
                        Cols.DEMAND_FULFILLED: qty, Cols.CLOSING_INV: 0.0, Cols.QTY_BASIS: basis})
    return pd.DataFrame(out)


def test_is_dad_region():
    assert list(is_dad_region(pd.Series(["JP", "DAD:JP", "DAD:Buffer", "dad", "US"]))) == [
        False, True, True, False, False]


@pytest.mark.parametrize("basis", ["request", "actual_ship"])     # legacy も identity も同じ数え方
def test_units_count_market_rows_only(basis):
    weekly, summary = evaluate_money(_rows(basis), SKU_MASTER)
    by_region = dict(zip(summary[Cols.REGION], summary["total_units"]))
    assert by_region == {"JP": 20.0, "US": 10.0, "DAD:Buffer": 0.0, "DAD:Main": 0.0}
    kpi = build_scenario_money_kpi(summary).iloc[0]
    assert kpi["units"] == 30.0                 # 前は 90（市場 30 ＋ DAD 30×2）
    # units 以外は変わらない：売上・原価は市場の行だけに価格があるので、もともと市場の分だけ
    assert kpi["revenue"] == 20 * 100.0 + 10 * 120.0 and kpi["cogs"] == 30 * 60.0
    assert "_market_units" not in weekly.columns and "_market_units" not in summary.columns
    # 週次の表の DAD の行の数量そのものは残る（在庫・通過量の行として）
    assert weekly[weekly[Cols.REGION] == "DAD:Main"][Cols.DEMAND_FULFILLED].sum() == 30.0


def test_simulator_rows_are_all_market_rows():
    """シミュレーターのシナリオには DAD の行が無い：units は全行の合計のまま。"""
    df = pd.DataFrame([{Cols.SCENARIO: "Base", Cols.SKU_ID: "A", Cols.REGION: r, Cols.WEEK: "2026-W01",
                        Cols.DEMAND_FULFILLED: q, Cols.CLOSING_INV: 0.0} for r, q in (("JP", 7.0), ("US", 3.0))])
    _w, summary = evaluate_money(df, SKU_MASTER)
    assert build_scenario_money_kpi(summary)["units"].iloc[0] == 10.0


def test_landed_cost_freight_uses_market_units():
    from wom.engine.landed_cost import LandedCostScenario, RouteProfile, compute_landed_cost_kpi
    _w, summary = evaluate_money(_rows("actual_ship"), SKU_MASTER)
    kpi = build_scenario_money_kpi(summary)
    scen = LandedCostScenario(name="Base", profiles=[
        RouteProfile(src_region="CN", dst_region="JP", tariff_rate=0.0, fx_rate=150.0, freight_usd_per_lot=2.0)])
    lc = compute_landed_cost_kpi(kpi, scen, {}).iloc[0]
    assert lc["freight_total"] == 2.0 * 30 * 150.0          # 1 lot あたりの運賃 × 市場の lot 数 × 為替
    assert lc["revenue"] == kpi["revenue"].iloc[0] and lc["cogs"] == kpi["cogs"].iloc[0]
