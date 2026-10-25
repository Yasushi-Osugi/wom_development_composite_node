# -*- coding: utf-8 -*-
"""
tests/test_yield_rate_part_a.py — RequestLetter_YieldRate_PartA（2026-10-25）
============================================================================
完成品の出荷時点の歩留まり（yield_rate）。Ship_Qty = Production_Qty × yield_rate。

cap_hard / cap_soft は物理の投入能力のまま。エンジンが lot を置く・封じるときの上限だけを
良品の上限 floor（能力 × yield_rate）にする。不良の分の Lot_ID は作らない・消さない。

  Unit        : 1〜8（合成の木、CSV を通さない）
  Integration : 9〜10（sc_tree_master.csv → 実ローダ → PlanNode、headless の経路で止まる）
  E2E golden  : tests/test_golden.py（列を持つモデルは無いので不変）
"""
import copy
import os
import runpy
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from wom.model.plan_node import S, P
from wom.model.sc_tree import build_demo_sc_tree
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner
from wom.engine.plan_copy import copy_demand_to_supply
from wom.engine.forward_planner import ForwardPlanner
from wom.engine.holiday_calendar_plugin import HolidayCalendarPlugin
from wom.engine.sc_tree_builder import build_sc_tree_from_master
from wom.engine.yield_rate import (
    YieldRateError, check_yield_rate_context, check_forward_yield)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COOKIE = os.path.join(REPO, "data", "sample", "Cookie-jp-2026")
SKU = "SKU-A"
N = 26
WEEKS = [f"2024-W{i:02d}" for i in range(1, N + 1)]
RAW = f"Raw Material [{SKU}]"


def _tree():
    rows = [{"sku_id": SKU, "sku_name": "A", "region": "JP", "lead_time_wks": 1}]
    return build_demo_sc_tree(pd.DataFrame(rows), WEEKS, lt_wks_ot=1, lt_wks_in=2)


def _node(tree, name):
    return next(nd for nd in tree.iter_all_nodes(SKU) if nd.node_name == name)


def _plan(yield_rate=None, cap_hard=None, cap_soft=None, demand=None,
          envelope="hard", mom_constrained=True, per_week=None):
    """Backward -> copy -> Forward on the demo tree. per_week: {w: (hard, soft)}."""
    t = _tree()
    mom = t.get_in_root(SKU)
    if yield_rate is not None:
        mom.yield_rate = yield_rate
    mom.demand_envelope = envelope
    for w in range(N):
        h, s = (per_week or {}).get(w, (cap_hard, cap_soft))
        mom.set_capacity(w, cap_hard=h, cap_soft=s)
    assign_demand_lots_from_dict(t, demand or {(SKU, "JP", "2024-W15"): 4}, cpu_size=1)
    bres = BackwardPlanner(t, config={"mom_constrained": mom_constrained}).run(SKU)
    copy_demand_to_supply(t, SKU)
    fp = ForwardPlanner(t)
    fres = fp.run(SKU)
    return t, mom, bres, fres, fp


def _psi(t):
    """Every node, week and bucket, both layers, as Lot_ID lists (order kept)."""
    return {nd.node_id: (copy.deepcopy(nd.psi4demand), copy.deepcopy(nd.psi4supply))
            for nd in t.iter_all_nodes(SKU)}


def _demand_weeks(weeks, qty):
    return {(SKU, "JP", WEEKS[w]): qty for w in weeks}


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------

def test_1_hard_capacity_limits_good_lots_backward_and_forward():
    t, mom, _b, _f, _fp = _plan(yield_rate=0.97, cap_hard=100,
                                demand=_demand_weeks(range(12, 18), 120))
    total = 6 * 120
    assert max(len(mom.psi4demand[w][P]) for w in range(N)) <= 97
    assert max(len(mom.psi4supply[w][P]) for w in range(N)) <= 97
    # the excess is carried back to earlier weeks' S, not lost (no Lot_ID removed)
    assert [len(mom.psi4demand[w][S]) for w in range(8, 16)] == [41] + [97] * 7
    assert sum(len(mom.psi4demand[w][S]) for w in range(N)) == total
    assert sum(len(mom.psi4supply[w][P]) for w in range(N)) == total


def test_2_soft_envelope_fill_target_is_floor_of_soft_times_yield():
    t, mom, _b, _f, _fp = _plan(yield_rate=0.9, cap_hard=200, cap_soft=80, envelope="soft",
                                demand=_demand_weeks([15], 100))
    # fill target 72 (= floor(80 * 0.9)); the excess 28 is pre-built in week 13
    assert len(mom.psi4demand[13][P]) == 72
    assert max(len(mom.psi4demand[w][P]) for w in range(N)) == 72


def test_3_cap_soft_flags_compare_against_good_soft_limit():
    # Backward (hard mode): target floor(100*0.9)=90, placed 85 > soft 72 -> 13
    _t, _m, bres, _f, _fp = _plan(yield_rate=0.9, cap_hard=100, cap_soft=80,
                                  demand=_demand_weeks([15], 85))
    assert sum(o for (_n, _w, o) in bres.cap_soft_envelope_violations) == 13
    # Forward: Backward unconstrained, P=85 <= 90 is not sealed; soft flag 85-72=13
    _t, _m, _b, fres, _fp = _plan(yield_rate=0.9, cap_hard=100, cap_soft=80,
                                  demand=_demand_weeks([15], 85), mom_constrained=False)
    assert sum(o for (_n, _w, o) in fres.cap_soft_violations) == 13
    # without the yield the same plan flags 5 (85 - 80)
    _t, _m, _b, fres1, _fp = _plan(cap_hard=100, cap_soft=80,
                                   demand=_demand_weeks([15], 85), mom_constrained=False)
    assert sum(o for (_n, _w, o) in fres1.cap_soft_violations) == 5


def test_4_zero_unset_and_closed_weeks_behave_as_before():
    # zero capacity in w12, closed in w13, every other week unset (None)
    def run(y):
        t = _tree()
        mom = t.get_in_root(SKU)
        if y is not None:
            mom.yield_rate = y
        mom.set_capacity(12, cap_hard=0.0)
        mom.set_operating_shifts(13, 0)
        assign_demand_lots_from_dict(t, _demand_weeks([14, 15], 3), cpu_size=1)
        BackwardPlanner(t, config={"mom_constrained": True}).run(SKU)
        copy_demand_to_supply(t, SKU)
        ForwardPlanner(t).run(SKU)
        return t, mom
    t1, mom1 = run(None)
    t2, mom2 = run(0.5)
    assert _psi(t1) == _psi(t2)
    assert mom2.shippable_limit(12) == 0.0
    assert mom2.shippable_limit(13) == 0.0
    assert mom2.shippable_limit(14) is None and mom2.shippable_planned(14) is None


def test_5_float_rounding_does_not_lose_a_lot():
    t = _tree()
    mom = t.get_in_root(SKU)
    mom.yield_rate = 0.29
    assert mom.shippable_of(100.0) == 29.0          # 100 * 0.29 = 28.999...
    _t, mom, _b, _f, _fp = _plan(yield_rate=0.29, cap_hard=100,
                                 demand=_demand_weeks([15], 60))
    assert max(len(mom.psi4supply[w][P]) for w in range(N)) == 29


def test_6_explicit_one_equals_no_attribute_psi_identical():
    per_week = {w: (3.0, 2.0) for w in range(N)}
    per_week[11] = (0.0, None)
    dem = _demand_weeks([10, 14, 15, 16], 5)
    t0, *_ = _plan(per_week=per_week, demand=dem)
    t1, *_ = _plan(yield_rate=1.0, per_week=per_week, demand=dem)
    assert _psi(t0) == _psi(t1)
    t0s, *_ = _plan(per_week=per_week, demand=dem, envelope="soft")
    t1s, *_ = _plan(yield_rate=1.0, per_week=per_week, demand=dem, envelope="soft")
    assert _psi(t0s) == _psi(t1s)


H = runpy.run_path(str(Path(__file__).with_name("test_stage3a2_kitting_gate.py")))


def test_7_kitting_recovery_completes_at_most_good_limit():
    tree, mom, yards, _leaves = H["_build_tree"]()
    H["_seed_demand"](mom, [5], 3)
    BackwardPlanner(tree).run(H["PROD"])
    copy_demand_to_supply(tree, H["PROD"])
    mom.yield_rate = 0.5
    for w in range(len(H["WEEKS"])):
        mom.set_capacity(w, cap_hard=4)            # good limit floor(4*0.5) = 2
    fp = ForwardPlanner(tree)
    res = fp.run(H["PROD"])
    for w in range(len(H["WEEKS"])):
        assert len(fp._actual_s.get(mom.node_id, {}).get(w, [])) <= 2
        assert len(mom.psi4supply[w][P]) <= 2
    assert res.kitting_capacity_deferred == [(mom.node_id, H["WEEKS"][5], 1)]
    assert sum(len(b[P]) for b in mom.psi4supply) == 3     # no lot lost


def _holiday_csv(tmp_path, node, a, b):
    path = tmp_path / "holiday_calendar.csv"
    path.write_text("holiday_id,holiday_name,start_week,end_week,node_name,effect,value\n"
                    f"H0,Holiday,{a},{b},{node},supply_closure,0\n", encoding="utf-8")
    return str(path)


def test_8_holiday_replacement_respects_good_limit(tmp_path):
    # The re-placement only handles leaf_in nodes (a MOM-only column cannot
    # reach it from the CSV); the yield is set directly to test the reader.
    t = _tree()
    raw = _node(t, RAW)
    raw.yield_rate = 0.5
    for w in range(N):
        raw.set_capacity(w, cap_hard=4)             # good limit 2
    assign_demand_lots_from_dict(t, _demand_weeks([14], 4), cpu_size=1)
    plugin = HolidayCalendarPlugin()
    cfg = {"holiday_cal_path": _holiday_csv(tmp_path, RAW, "2024-W10", "2024-W10")}
    plugin.on_pre_plan(t, WEEKS, cfg)
    cfg["mom_constrained"] = False
    BackwardPlanner(t, config=cfg).run(SKU)
    # put the lots into the closed week so the re-placement must move them
    lots = [l for w in range(N) for l in raw.psi4demand[w][P]]
    for w in range(N):
        raw.psi4demand[w][P] = []
    raw.psi4demand[9][P] = list(lots)
    plugin.on_post_backward(t, SKU, WEEKS, cfg)
    assert raw.psi4demand[9][P] == []
    open_weeks = [w for w in range(N) if w != 9 and raw.psi4demand[w][P]]
    # filled to the good limit (2), not the physical cap (4); the excess goes
    # to the fallback week as before (the plugin's own overflow rule)
    assert len(raw.psi4demand[8][P]) == 2
    assert sum(len(raw.psi4demand[w][P]) for w in open_weeks) == 4


# ---------------------------------------------------------------------------
# Integration：CSV → 実ローダ → PlanNode
# ---------------------------------------------------------------------------

def _cookie_df(yield_by_node=None):
    df = pd.read_csv(os.path.join(COOKIE, "sc_tree_master.csv"))
    if yield_by_node is not None:
        df["yield_rate"] = ""
        for name, val in yield_by_node.items():
            df.loc[df["node_name"] == name, "yield_rate"] = val
    return df


def _cookie_csv_tree(tmp_path, yield_by_node=None):
    p = tmp_path / "sc_tree_master.csv"
    _cookie_df(yield_by_node).to_csv(p, index=False)
    return build_sc_tree_from_master(pd.read_csv(p), WEEKS)


def _find(tree, prod, name):
    return next(nd for nd in tree.iter_all_nodes(prod) if nd.node_name == name)


def test_9_column_reaches_plan_node(tmp_path):
    t = _cookie_csv_tree(tmp_path, {"Factory_DP_JP": "0.9", "Factory_GP_CN": ""})
    assert _find(t, "Cookie_Local", "Factory_DP_JP").yield_rate == 0.9
    assert _find(t, "Cookie_Local", "Factory_DP_JP").yield_rate_line == 15
    assert _find(t, "Cookie_Import", "Factory_GP_CN").yield_rate == 1.0      # blank
    t0 = build_sc_tree_from_master(_cookie_df(), WEEKS)                      # no column
    assert all(nd.yield_rate == 1.0 for p in t0.products for nd in t0.iter_all_nodes(p))


@pytest.mark.parametrize("val", ["abc", "0", "-0.1", "1.2"])
def test_10a_invalid_value_stops(tmp_path, val):
    with pytest.raises(YieldRateError) as e:
        _cookie_csv_tree(tmp_path, {"Factory_DP_JP": val})
    msg = str(e.value)
    assert "sc_tree_master.csv line 15" in msg and "Factory_DP_JP" in msg
    shown = val if val == "abc" else str(float(val))      # read_csv parses numbers
    assert f"yield_rate={shown!r}" in msg or f"yield_rate={shown}" in msg
    assert "(0, 1]" in msg


def test_10b_non_mom_node_stops(tmp_path):
    with pytest.raises(YieldRateError) as e:
        _cookie_csv_tree(tmp_path, {"Ingredients_JP": "0.9"})
    msg = str(e.value)
    assert "line 16" in msg and "Ingredients_JP" in msg and "'leaf_in'" in msg
    assert "node_type='mom'" in msg
    _cookie_csv_tree(tmp_path, {"Ingredients_JP": "1.0"})       # 1.0 is allowed anywhere


def _cookie_copy(tmp_path, yield_by_node, push_rows=None):
    dst = tmp_path / "Cookie-jp-2026"
    shutil.copytree(COOKIE, dst)
    _cookie_df(yield_by_node).to_csv(dst / "sc_tree_master.csv", index=False)
    if push_rows:
        hdr = ("sku_id,node_id,push_qty_per_week,buffer_lots,mode_only,mom_ref_node_id,"
               "pre_build_qty_per_week,pre_build_end_week,push_lead_time_weeks\n")
        (dst / "push_config.csv").write_text(hdr + "\n".join(push_rows) + "\n", encoding="utf-8")
    return str(dst)


def _headless(model_dir, tmp_path, **kw):
    from tools.run_headless_from_folder import run
    return run(model_dir, output_ppc_dir=str(tmp_path / "ppc"), verbose=False, **kw)


def test_10c_legacy_stops(tmp_path):
    md = _cookie_copy(tmp_path, {"Factory_DP_JP": "0.9"})
    with pytest.raises(YieldRateError) as e:
        _headless(md, tmp_path, lot_flow_mode="legacy")
    assert "lot_flow_mode=legacy" in str(e.value) and "line 15" in str(e.value)


def test_10d_rice_seasonal_on_stops(tmp_path):
    md = _cookie_copy(tmp_path, {"Factory_DP_JP": "0.9"})
    with pytest.raises(YieldRateError) as e:
        _headless(md, tmp_path, plugins_spec="RiceSeasonalPlugin")
    assert "RiceSeasonalPlugin" in str(e.value) and "rice_recipe.csv" in str(e.value)


def test_10e_push_mom_stops(tmp_path):
    md = _cookie_copy(tmp_path, {"Factory_DP_JP": "0.9"},
                      push_rows=["Cookie_Local,Factory_DP_JP,0,0,true,,0,,0"])
    with pytest.raises(YieldRateError) as e:
        _headless(md, tmp_path)
    msg = str(e.value)
    assert "push decoupling" in msg and "push_config.csv" in msg and "line 15" in msg


def test_10f_forward_guard_unit():
    t = _tree()
    mom = t.get_in_root(SKU)
    mom.yield_rate = 0.9
    check_yield_rate_context(t, lot_flow_mode="identity", plugin_names=["HolidayCalendarPlugin"])
    with pytest.raises(YieldRateError):
        check_forward_yield(t, SKU, lot_flow_mode="legacy")
    mom.plan_mode = "push"
    with pytest.raises(YieldRateError):
        check_forward_yield(t, SKU, lot_flow_mode="identity")
