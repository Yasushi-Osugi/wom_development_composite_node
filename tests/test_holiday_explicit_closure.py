# -*- coding: utf-8 -*-
"""
tests/test_holiday_explicit_closure.py — Explicit Closure v1r5m0
=================================================================
Request Letter: requests/RequestLetter_ExplicitClosure_v1r5m0_to_CodeKun.md

休業（supply_closure）は能力値の特殊値ではなく「週の状態」（op_shifts[w]==0）で表す。
cap_hard は物理天井のまま書き換えない（D1）。cap_soft は計画上の操業能力で、休業週は 0（D2）。

旧依頼（docs/codex_requests/holiday_explicit_closure_engine_request.md §6）の
Test 1〜8 を現行コードへ移植し（Test 3・6 は push／非push に分割）、T9〜T17 を追加する。

  Unit        : 合成ツリー（build_demo_sc_tree）＋ HolidayCalendarPlugin（tmp CSV）
  Integration : 実モデル（soysauce-jpy-2027-alloc の複写）を headless / GUI の
                読み込み経路に通す（T17）
  E2E golden  : tests/test_golden.py（本ファイルの対象外）
"""
import os
import shutil
import sys
import types

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from wom.model.plan_node import S, CO, I, P
from wom.model.sc_tree import build_demo_sc_tree
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner, BackwardPlanResult
from wom.engine.plan_copy import copy_demand_to_supply
from wom.engine.forward_planner import ForwardPlanner
from wom.engine.push_pull import PushConfig, PushProductionPlanner
from wom.engine.holiday_calendar_plugin import HolidayCalendarPlugin

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKU = "SKU-A"
MOM_NAME = f"Mother Plant [{SKU}]"
RAW_NAME = f"Raw Material [{SKU}]"
N_WEEKS = 26
WEEKS = [f"2024-W{i:02d}" for i in range(1, N_WEEKS + 1)]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _tree():
    rows = [{"sku_id": SKU, "sku_name": "A", "region": "JP", "lead_time_wks": 1}]
    return build_demo_sc_tree(pd.DataFrame(rows), WEEKS, lt_wks_ot=1, lt_wks_in=2)


def _node(tree, name):
    for nd in tree.iter_all_nodes(SKU):
        if nd.node_name == name:
            return nd
    raise KeyError(name)


def _holiday_csv(tmp_path, rows):
    """rows: [(node_name, start_week_label, end_week_label, effect, value)]"""
    path = tmp_path / "holiday_calendar.csv"
    lines = ["holiday_id,holiday_name,start_week,end_week,node_name,effect,value"]
    for i, (node, a, b, eff, val) in enumerate(rows):
        lines.append(f"H{i},Holiday {i},{a},{b},{node},{eff},{val}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _apply_plugin(tree, tmp_path, rows):
    plugin = HolidayCalendarPlugin()
    cfg = {"holiday_cal_path": _holiday_csv(tmp_path, rows)}
    plugin.on_pre_plan(tree, WEEKS, cfg)
    return plugin, cfg


def _plan(tmp_path, rows=(), demand=None, mom_cap=None, push=None, closure_hook=None,
          mom_constrained=True):
    """Full Backward -> post_backward -> copy -> (push) -> Forward on the demo tree."""
    tree = _tree()
    assign_demand_lots_from_dict(tree, demand or {(SKU, "JP", "2024-W12"): 4}, cpu_size=1)
    mom = _node(tree, MOM_NAME)
    if mom_cap is not None:
        for w in range(N_WEEKS):
            mom.set_capacity(w, cap_hard=mom_cap[0], cap_soft=mom_cap[1])
    plugin, cfg = (_apply_plugin(tree, tmp_path, list(rows)) if rows
                   else (HolidayCalendarPlugin(), {}))
    cfg["mom_constrained"] = mom_constrained
    bres = BackwardPlanner(tree, config=cfg).run(SKU)
    plugin.on_post_backward(tree, SKU, WEEKS, cfg)
    copy_demand_to_supply(tree, SKU)
    pres = None
    if push is not None:
        pres = PushProductionPlanner(tree).setup(SKU, push)
    if closure_hook is not None:
        closure_hook(tree)
    fp = ForwardPlanner(tree)
    fres = fp.run(SKU)
    return tree, bres, fres, fp, pres


def _dem_week_of(node, lot_id, bucket=S):
    for w in range(N_WEEKS):
        if lot_id in node.psi4demand[w][bucket]:
            return w
    return None


def _all_ids(node, bucket, layer="supply"):
    psi = node.psi4supply if layer == "supply" else node.psi4demand
    out = []
    for w in range(N_WEEKS):
        out.extend(psi[w][bucket])
    return out


# ===========================================================================
# Test 1 (旧 Test 1): closure registered independently of value
# ===========================================================================

@pytest.mark.parametrize("value", ["0", "0.1", "1500"])
def test_t1_supply_closure_is_week_state_independent_of_value(tmp_path, value, capsys):
    tree = _tree()
    mom = _node(tree, MOM_NAME)
    for w in range(N_WEEKS):
        mom.set_capacity(w, cap_hard=800.0, cap_soft=686.0)
    _, cfg = _apply_plugin(tree, tmp_path, [(MOM_NAME, "2024-W10", "2024-W10",
                                             "supply_closure", value)])
    w10 = WEEKS.index("2024-W10")
    assert cfg["explicit_closures"][MOM_NAME] == {w10}
    assert mom.is_open(w10) is False
    # capacity values are NOT rewritten (D1/D2)
    assert mom.cap_hard(w10) == 800.0
    assert mom.cap_soft(w10) == 686.0
    assert mom.processing_limit(w10) == 0.0
    assert mom.planned_capacity(w10) == 0.0
    out = capsys.readouterr().out
    if value == "1500":
        assert "supply_closure は value を使わない" in out
    else:
        assert "supply_closure は value を使わない" not in out


# ===========================================================================
# Test 2 (旧 Test 2): zero without closure remains unconstrained
# ===========================================================================

def test_t2_zero_without_closure_is_unset(tmp_path):
    tree, _b, fres, _fp, _ = _plan(tmp_path)
    mom = _node(tree, MOM_NAME)
    for w in range(N_WEEKS):
        assert mom.cap_hard(w) == 0.0 and mom.is_open(w)
        assert mom.processing_limit(w) is None
        assert mom.planned_capacity(w) is None
    assert fres.cap_hard_sealed == 0
    assert fres.closure_p_deferred == [] and fres.closure_p_unplaced == []


# ===========================================================================
# Test 3a (旧 Test 3, 非 push MOM) + T13: value=0.0 closure → fill target 0
# ===========================================================================

def _mom_demand_week(tmp_path):
    tree, *_ = _plan(tmp_path / "base", mom_cap=(800.0, 0.0))
    mom = _node(tree, MOM_NAME)
    weeks = [w for w in range(N_WEEKS) if mom.psi4demand[w][S]]
    assert len(weeks) == 1
    return weeks[0], list(mom.psi4demand[weeks[0]][S]), tree


@pytest.mark.parametrize("value", ["0", "0.0"])
def test_t3a_t13_mom_closure_moves_lots_earlier(tmp_path, value):
    (tmp_path / "base").mkdir()
    wc, lots, _ = _mom_demand_week(tmp_path)
    tree, *_ = _plan(tmp_path, rows=[(MOM_NAME, WEEKS[wc], WEEKS[wc], "supply_closure", value)],
                     mom_cap=(800.0, 0.0))
    mom = _node(tree, MOM_NAME)
    assert mom.cap_hard(wc) == 800.0, "cap_hard (physical) is not rewritten"
    assert mom.psi4demand[wc][P] == [], "closed week: fill target 0 (T13)"
    assert mom.psi4demand[wc][S] == []
    assert mom.psi4supply[wc][P] == [], "closed week: no production"
    # the SAME Lot_IDs moved to an earlier week (identity, not only quantity)
    moved_to = {_dem_week_of(mom, lot) for lot in lots}
    assert moved_to == {wc - 1}


# ===========================================================================
# Test 3b / T9 (旧 Test 3/6, push MOM): receipt accepted, nothing shipped
# ===========================================================================

def _push_cfg():
    return PushConfig(node_id=f"IN:MFG:{SKU}", push_qty_per_week=6, sku_id=SKU)


def test_t9_push_node_closed_week_accepts_p_ships_nothing(tmp_path):
    base_tree, *_ = _plan(tmp_path, push=_push_cfg(), mom_constrained=False)
    bmom = _node(base_tree, MOM_NAME)
    wc = next(w for w in range(1, N_WEEKS) if bmom.psi4supply[w][S] and bmom.psi4supply[w][P])

    def close(tree):
        _node(tree, MOM_NAME).set_operating_shifts(wc, 0)

    tree, _b, fres, fp, _ = _plan(tmp_path, push=_push_cfg(), closure_hook=close,
                                  mom_constrained=False)
    mom = _node(tree, MOM_NAME)
    assert mom.plan_mode == "push"
    assert len(mom.psi4supply[wc][P]) == len(bmom.psi4supply[wc][P]), "P (receipt) accepted"
    assert fp._actual_s[mom.node_id][wc] == [], "no shipment in the closed week"
    prev_i = list(mom.psi4supply[wc - 1][I])
    assert mom.psi4supply[wc][I] == prev_i + list(mom.psi4supply[wc][P]), "all stays in I"
    # S plan was non-zero here (Forward-only closure, Backward did not see it)
    assert fres.closure_s_planned == [(mom.node_id, WEEKS[wc], len(mom.psi4supply[wc][S]))]
    assert mom._push_shortfall[wc] == len(mom.psi4supply[wc][S]), "throughput view = 0"


# ===========================================================================
# Test 4 (旧 Test 4): consecutive closures carry to the nearest earlier open week
# ===========================================================================

def test_t4_consecutive_closures_carry_to_w04(tmp_path):
    tree = _tree()
    mom = _node(tree, MOM_NAME)
    for w in range(N_WEEKS):
        mom.set_capacity(w, cap_hard=10.0, cap_soft=0.0)
    _apply_plugin(tree, tmp_path, [(MOM_NAME, "2024-W05", "2024-W06", "supply_closure", "0")])
    w04, w05, w06 = (WEEKS.index(x) for x in ("2024-W04", "2024-W05", "2024-W06"))
    mom.psi4demand[w06][S] = ["L1", "L2", "L3"]
    bp = BackwardPlanner(tree, config={"mom_constrained": True})
    bp._apply_mom_cap_backward(mom, N_WEEKS, BackwardPlanResult(prod_nm=SKU))
    assert mom.psi4demand[w05][P] == [] and mom.psi4demand[w06][P] == []
    assert mom.psi4demand[w05][S] == [] and mom.psi4demand[w06][S] == []
    # carried to W04's production request (S). W04 has no overflow (3 <= cap 10),
    # so _apply_mom_cap_backward leaves its P untouched -- existing behaviour.
    assert sorted(mom.psi4demand[w04][S]) == ["L1", "L2", "L3"]
    ids = [x for w in range(N_WEEKS) for x in mom.psi4demand[w][S]]
    assert len(ids) == len(set(ids)), "no duplicate Lot_IDs"


# ===========================================================================
# Test 5 (旧 Test 5): MOM adjustment precedes upstream propagation
# ===========================================================================

def test_t5_upstream_follows_adjusted_mom_timing(tmp_path):
    (tmp_path / "base").mkdir()
    wc, lots, base_tree = _mom_demand_week(tmp_path)
    tree, *_ = _plan(tmp_path, rows=[(MOM_NAME, WEEKS[wc], WEEKS[wc], "supply_closure", "0")],
                     mom_cap=(800.0, 0.0))
    for name in (f"Tier-1 Supplier [{SKU}]", RAW_NAME):
        b, a = _node(base_tree, name), _node(tree, name)
        for lot in lots:
            wb, wa = _dem_week_of(b, lot), _dem_week_of(a, lot)
            assert wb is not None and wa == wb - 1, (name, lot, wb, wa)


# ===========================================================================
# T15 (旧 Test 6, 非 push): closed-week P is deferred, never dropped
# ===========================================================================

def test_t15_non_push_closed_week_p_is_deferred_not_lost(tmp_path):
    base_tree, *_ = _plan(tmp_path)
    bmom = _node(base_tree, MOM_NAME)
    wc = next(w for w in range(N_WEEKS) if bmom.psi4supply[w][P])
    base_ids = sorted(_all_ids(bmom, P))

    def close(tree):   # closure unknown to Backward: P lands in the closed week
        _node(tree, MOM_NAME).set_operating_shifts(wc, 0)

    tree, _b, fres, fp, _ = _plan(tmp_path, closure_hook=close)
    mom = _node(tree, MOM_NAME)
    assert mom.psi4supply[wc][P] == []
    assert fp._actual_s[mom.node_id].get(wc, []) == [], "no shipment from the closed week"
    assert sorted(_all_ids(mom, P)) == base_ids, "lot identity preserved over the horizon"
    moved = list(bmom.psi4supply[wc][P])
    assert mom.psi4supply[wc + 1][P][-len(moved):] == moved, "appended to the next open week"
    assert fres.closure_p_deferred == [(mom.node_id, WEEKS[wc], len(moved))]
    assert fres.closure_p_unplaced == []
    # the bridge carries nothing sourced from the closed week
    sp = base_tree.get_ot_root(SKU)
    sp2 = tree.get_ot_root(SKU)
    assert sp2.psi4supply[wc][P] == []
    assert len(_all_ids(sp2, P)) == len(_all_ids(sp, P))


def test_t15b_no_open_week_left_is_reported(tmp_path):
    base_tree, *_ = _plan(tmp_path)
    bmom = _node(base_tree, MOM_NAME)
    wc = next(w for w in range(N_WEEKS) if bmom.psi4supply[w][P])

    def close(tree):
        m = _node(tree, MOM_NAME)
        for w in range(wc, N_WEEKS):
            m.set_operating_shifts(w, 0)

    tree, _b, fres, _fp, _ = _plan(tmp_path, closure_hook=close)
    mom = _node(tree, MOM_NAME)
    assert fres.closure_p_deferred == []
    assert fres.closure_p_unplaced == [(mom.node_id, WEEKS[wc], list(bmom.psi4supply[wc][P]))]


# ===========================================================================
# Test 7 (旧 Test 7): no-closure regression (header-only CSV = no-op)
# ===========================================================================

def test_t7_empty_holiday_file_is_noop(tmp_path):
    base_tree, _b, bres, _fp, _ = _plan(tmp_path)
    tree = _tree()
    assign_demand_lots_from_dict(tree, {(SKU, "JP", "2024-W12"): 4}, cpu_size=1)
    cfg = {"holiday_cal_path": _holiday_csv(tmp_path, [])}
    HolidayCalendarPlugin().on_pre_plan(tree, WEEKS, cfg)
    for nd in tree.iter_all_nodes(SKU):
        assert all(nd.operating_shifts(w) is None for w in range(N_WEEKS))
    BackwardPlanner(tree, config=cfg).run(SKU)
    copy_demand_to_supply(tree, SKU)
    fres = ForwardPlanner(tree).run(SKU)
    for b, a in zip(base_tree.iter_all_nodes(SKU), tree.iter_all_nodes(SKU)):
        for bucket in (P, S, I, CO):
            assert [len(b.psi4supply[w][bucket]) for w in range(N_WEEKS)] == \
                   [len(a.psi4supply[w][bucket]) for w in range(N_WEEKS)]
    assert fres.closure_p_deferred == [] and fres.closure_s_planned == []


# ===========================================================================
# Test 8 (旧 Test 8): leaf_in closure still shifts P once (no double move)
# ===========================================================================

def test_t8_leaf_in_closure_shift_once(tmp_path):
    base_tree, *_ = _plan(tmp_path)
    braw = _node(base_tree, RAW_NAME)
    wc = next(w for w in range(N_WEEKS) if braw.psi4demand[w][P])
    lots = list(braw.psi4demand[wc][P])
    tree, _b, fres, _fp, _ = _plan(tmp_path, rows=[(RAW_NAME, WEEKS[wc], WEEKS[wc],
                                                    "supply_closure", "0")])
    raw = _node(tree, RAW_NAME)
    assert raw.psi4demand[wc][P] == [] and raw.psi4supply[wc][P] == []
    ids = _all_ids(raw, P, layer="demand")
    assert sorted(ids) == sorted(_all_ids(braw, P, layer="demand")), "moved, not duplicated"
    assert all(_dem_week_of(raw, lot, P) < wc for lot in lots), "pre-holiday buffer (earlier)"
    assert not any(n == raw.node_id for n, _w, _c in fres.closure_p_deferred), \
        "Forward has nothing left to defer at the leaf"


# ===========================================================================
# T10: set_capacity changes only what is passed
# ===========================================================================

def test_t10_set_capacity_keeps_the_other_value():
    tree = _tree()
    mom = _node(tree, MOM_NAME)
    mom.set_capacity(3, cap_hard=800.0, cap_soft=686.0)
    mom.set_capacity(3, cap_hard=0.1)
    assert mom.cap_hard(3) == 0.1 and mom.cap_soft(3) == 686.0
    mom.set_capacity(3, cap_soft=500.0)
    assert mom.cap_hard(3) == 0.1 and mom.cap_soft(3) == 500.0


# ===========================================================================
# T11: partial_capacity reproduces the pre-v1r5m0 supply_closure (transitional)
# ===========================================================================

def test_t11_partial_capacity_is_legacy_compatible(tmp_path):
    tree = _tree()
    mom = _node(tree, MOM_NAME)
    for w in range(N_WEEKS):
        mom.set_capacity(w, cap_hard=800.0, cap_soft=686.0)
    raw = _node(tree, RAW_NAME)
    w10 = WEEKS.index("2024-W10")
    raw.psi4demand[w10][P] = ["R1", "R2"]
    plugin, cfg = _apply_plugin(tree, tmp_path, [
        (MOM_NAME, "2024-W10", "2024-W10", "partial_capacity", "700"),
        (RAW_NAME, "2024-W10", "2024-W10", "partial_capacity", "0.3"),
    ])
    assert mom.cap_hard(w10) == 700.0 and mom.cap_soft(w10) == 686.0, "cap_soft kept"
    assert mom.is_open(w10) and raw.is_open(w10), "partial_capacity is not a closure"
    assert cfg["explicit_closures"] == {MOM_NAME: {w10}, RAW_NAME: {w10}}
    plugin.on_post_backward(tree, SKU, WEEKS, cfg)
    assert raw.psi4demand[w10][P] == []
    assert sorted(raw.psi4demand[w10 - 1][P]) == ["R1", "R2"], "leaf_in P shift kept"


# ===========================================================================
# T12: H1 regression -- W18 S=0 does NOT depend on cap_soft being wiped
# ===========================================================================

def test_t12_closure_zero_even_with_soft_envelope_and_cap_soft_kept(tmp_path):
    tree = _tree()
    mom = _node(tree, MOM_NAME)
    mom.demand_envelope = "soft"
    for w in range(N_WEEKS):
        mom.set_capacity(w, cap_hard=8.0, cap_soft=6.0)
        mom.set_operating_shifts(w, 18)           # operating calendar: open (18直)
    _apply_plugin(tree, tmp_path, [(MOM_NAME, "2024-W18", "2024-W18", "supply_closure", "0")])
    w18 = WEEKS.index("2024-W18")
    assert mom.cap_soft(w18) == 6.0, "cap_soft=686 analogue survives the closure"
    mom.psi4demand[w18][S] = [f"A{i}" for i in range(6)]
    mom.psi4demand[w18 - 1][S] = [f"B{i}" for i in range(6)]
    bp = BackwardPlanner(tree, config={"mom_constrained": True})
    bp._apply_mom_cap_backward(mom, N_WEEKS, BackwardPlanResult(prod_nm=SKU))
    assert mom.psi4demand[w18][S] == [] and mom.psi4demand[w18][P] == []
    for w in range(N_WEEKS):
        assert len(mom.psi4demand[w][P]) <= 6, "soft envelope target still applies"


# ===========================================================================
# T14: display view -- raw CapHard, CapSoft 0 in a closed week, "—" only unset
# ===========================================================================

def test_t14_capacity_view_cells_and_headless_series(tmp_path):
    from tools.run_headless_from_folder import _planning_state_extras
    from wom.gui.app import psi_list_capacity_cells, capacity_view_series

    tree = _tree()
    mom = _node(tree, MOM_NAME)
    for w in range(N_WEEKS):
        mom.set_capacity(w, cap_hard=800.0, cap_soft=686.0)
    mom.set_capacity(2, cap_soft=0.0)                       # open week, cap_soft unset
    _apply_plugin(tree, tmp_path, [(MOM_NAME, "2024-W18", "2024-W18", "supply_closure", "0")])
    w18 = WEEKS.index("2024-W18")

    assert psi_list_capacity_cells(mom, w18) == ("800", "0")
    assert psi_list_capacity_cells(mom, 2) == ("800", "—")
    assert psi_list_capacity_cells(mom, 3) == ("800", "686")
    raw = _node(tree, RAW_NAME)
    assert psi_list_capacity_cells(raw, 3) == ("—", "—")
    raw.set_capacity(3, cap_hard=0.3)
    assert psi_list_capacity_cells(raw, 3) == ("0.3", "—"), "no misleading '0'"

    ex = _planning_state_extras(tree, N_WEEKS, [], [])
    ser = ex["capacity_series"][SKU][MOM_NAME]
    assert ser["cap_hard"][w18] == 800.0
    assert ser["cap_soft"][w18] == 0.0 and ser["cap_soft"][3] == 686.0
    assert ser["closed_weeks"] == ["2024-W18"]
    assert capacity_view_series(mom, mom.psi4supply) == [0] * N_WEEKS


# ===========================================================================
# T16: Mode 4 -- a closed production week moves to the previous open week
# ===========================================================================

def _mode4_cfg():
    return PushConfig(node_id=f"IN:MFG:{SKU}", sku_id=SKU, push_lead_time_weeks=4)


def test_t16_mode4_closed_week_moves_earlier_identity_preserved(tmp_path):
    base_tree, *_r, base_pres = _plan(tmp_path, push=_mode4_cfg(), mom_constrained=False)
    braw = _node(base_tree, RAW_NAME)
    wc = next(w for w in range(1, N_WEEKS) if braw.psi4supply[w][P])
    lots = list(braw.psi4supply[wc][P])
    base_ids = sorted(_all_ids(braw, P))

    tree = _tree()
    assign_demand_lots_from_dict(tree, {(SKU, "JP", "2024-W12"): 4}, cpu_size=1)
    BackwardPlanner(tree, config={"mom_constrained": False}).run(SKU)
    copy_demand_to_supply(tree, SKU)
    raw = _node(tree, RAW_NAME)
    raw.set_operating_shifts(wc, 0)
    pres = PushProductionPlanner(tree).setup(SKU, _mode4_cfg())

    assert raw.psi4supply[wc][P] == []
    assert raw.psi4supply[wc - 1][P][-len(lots):] == lots
    assert sorted(_all_ids(raw, P)) == base_ids, "Lot_ID set unchanged"
    assert pres.mode4_closure_shifted == [(raw.node_id, WEEKS[wc], WEEKS[wc - 1], len(lots))]
    assert base_pres.mode4_closure_shifted == []


def test_t16b_mode4_first_week_closed_moves_later(tmp_path):
    tree = _tree()
    assign_demand_lots_from_dict(tree, {(SKU, "JP", "2024-W12"): 4}, cpu_size=1)
    BackwardPlanner(tree, config={"mom_constrained": False}).run(SKU)
    copy_demand_to_supply(tree, SKU)
    raw = _node(tree, RAW_NAME)
    ref_probe = _tree()
    assign_demand_lots_from_dict(ref_probe, {(SKU, "JP", "2024-W12"): 4}, cpu_size=1)
    BackwardPlanner(ref_probe, config={"mom_constrained": False}).run(SKU)
    copy_demand_to_supply(ref_probe, SKU)
    PushProductionPlanner(ref_probe).setup(SKU, _mode4_cfg())
    wc = next(w for w in range(N_WEEKS) if _node(ref_probe, RAW_NAME).psi4supply[w][P])
    for w in range(0, wc + 1):
        raw.set_operating_shifts(w, 0)
    pres = PushProductionPlanner(tree).setup(SKU, _mode4_cfg())
    assert raw.psi4supply[wc][P] == []
    assert pres.mode4_closure_shifted[0][2] == WEEKS[wc + 1]


# ===========================================================================
# T17: load order -- operating_calendar 18直 then supply_closure => closed,
#      on BOTH the headless and the GUI context-building path
# ===========================================================================

ALLOC = os.path.join(REPO_ROOT, "data", "sample", "soysauce-jpy-2027-alloc")


@pytest.fixture(scope="module")
def alloc_copy(tmp_path_factory):
    dst = tmp_path_factory.mktemp("alloc") / "soysauce-jpy-2027-alloc"
    shutil.copytree(ALLOC, dst)
    return str(dst)


def _bottling(sc_tree):
    for nd in sc_tree.iter_all_nodes("Soy_Sauce"):
        if nd.node_name == "Bottling_Noda":
            return nd
    raise KeyError("Bottling_Noda")


def _opcal_w18_shifts(model_dir):
    cal = pd.read_csv(os.path.join(model_dir, "operating_calendar.csv"))
    row = cal[(cal["node_name"] == "Bottling_Noda") & (cal["week"] == "2027-W18")]
    return int(row["shifts"].iloc[0])


def test_t17_headless_load_order(alloc_copy, monkeypatch, tmp_path):
    import tools.run_headless_from_folder as rh
    assert _opcal_w18_shifts(alloc_copy) == 18
    seen = {}
    orig = rh._psi_signature

    def spy(sc_tree, n_weeks):
        seen["tree"] = sc_tree
        return orig(sc_tree, n_weeks)

    monkeypatch.setattr(rh, "_psi_signature", spy)
    rh.run(alloc_copy, plugins_spec="safe", output_ppc_dir=str(tmp_path / "ppc"),
           verbose=False)
    bot = _bottling(seen["tree"])
    labels = seen["tree"].week_labels
    for lbl in ("2027-W18", "2028-W18"):
        w = labels.index(lbl)
        assert bot.is_open(w) is False, lbl
        assert bot.cap_hard(w) == 800.0, "physical ceiling kept"
    w17 = labels.index("2027-W17")
    assert bot.is_open(w17) and bot.operating_shifts(w17) == 18


def test_t17_gui_load_order(alloc_copy):
    from wom.gui.app import WOMApp
    from wom.engine.hook_bus import HOOK_PRE_PLAN
    from wom.engine.warmup import materialize_warmup
    from tools.run_headless_from_folder import _detect_period

    materialize_warmup(alloc_copy)
    start, n_weeks = _detect_period(os.path.join(alloc_copy, "demand_forecast.csv"))

    def var(v):
        return types.SimpleNamespace(get=lambda: v)

    p = lambda name: os.path.join(alloc_copy, name)  # noqa: E731
    stub = types.SimpleNamespace(
        _e_weeks=var(str(n_weeks)), _e_start=var(start),
        _f_sku=var(p("sku_master.csv")), _f_sc_tree=var(p("sc_tree_master.csv")),
        _f_dem=var(p("demand_forecast.csv")), _f_cap=var(p("capacity_plan.csv")),
        _f_holiday=var(p("holiday_calendar.csv")), _f_lane=var(p("lane_assignment.csv")),
        _f_push=var(p("push_config.csv")),
        _active_plugins=[HolidayCalendarPlugin()], _plugin_instances={}, _plugin_vars={},
    )
    ctx = WOMApp._build_planning_context(stub)
    # _planning_thread: context first (capacity + operating calendar), then PRE_PLAN
    ctx["bus"].fire(HOOK_PRE_PLAN, sc_tree=ctx["sc_tree"], weeks=ctx["weeks"],
                    config=ctx["cfg"])
    bot = _bottling(ctx["sc_tree"])
    for lbl in ("2027-W18", "2028-W18"):
        w = ctx["weeks"].index(lbl)
        assert bot.is_open(w) is False, lbl
        assert bot.cap_hard(w) == 800.0
    w17 = ctx["weeks"].index("2027-W17")
    assert bot.operating_shifts(w17) == 18
