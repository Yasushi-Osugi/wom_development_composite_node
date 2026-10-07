# -*- coding: utf-8 -*-
"""
tests/test_capacity_zero_blank.py — RequestLetter_CapacityZeroBlank（2026-10-07）

能力の値の意味：空欄 ＝ 未設定（上限なし）、0 ＝ 能力ゼロ、正の数 ＝ 上限。
負の数・数値でない値、計画の木に無いノード名の行は、読み込みで止める。

  Unit        : 値の 5 通り（空欄・0・正の数・負の数・数値でない値）、PlanNode の状態、
                能力ゼロの週に P が入らず繰り延べになること（Forward・Backward）、
                休業の週の振る舞いが変わらないこと
  Integration : CSV → 実ローダ（load_capacity_dataframe）→ ノード。空欄と 0 が別に読まれる。
                ノード名の誤りで止まる。計画期間の外の週は警告。旧書式（node_name なし）。
                cap_override.csv・holiday_calendar.csv（partial_capacity）も同じ規則。
                headless の実行（CSV からの経路全体）でも止まる。
  E2E golden  : tests/test_golden.py
"""
import os
import shutil
import sys
import warnings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from wom.model.plan_node import S, CO, I, P
from wom.model.sc_tree import build_demo_sc_tree
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner
from wom.engine.plan_copy import copy_demand_to_supply
from wom.engine.forward_planner import ForwardPlanner
from wom.engine.capacity_sealer import (
    CapacityDataError, parse_capacity_value, load_capacity_dataframe)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKU = "SKU-A"
N = 26
WEEKS = [f"2024-W{i:02d}" for i in range(1, N + 1)]
MOM = f"Mother Plant [{SKU}]"


def _tree():
    rows = [{"sku_id": SKU, "sku_name": "A", "region": "JP", "lead_time_wks": 1}]
    return build_demo_sc_tree(pd.DataFrame(rows), WEEKS, lt_wks_ot=1, lt_wks_in=2)


def _mom(t):
    return t.get_in_root(SKU)


def _plan(t, mode="identity", backward_cap=False, demand_week="2024-W10", qty=4):
    assign_demand_lots_from_dict(t, {(SKU, "JP", demand_week): qty}, cpu_size=1)
    BackwardPlanner(t, config={"mom_constrained": backward_cap}).run(SKU)
    copy_demand_to_supply(t, SKU)
    fp = ForwardPlanner(t, lot_flow_mode=mode)
    res = fp.run(SKU)
    return fp, res


# ---------------------------------------------------------------------------
# Unit：値の 5 通り
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    (None, None), ("", None), ("   ", None), (float("nan"), None),     # 空欄 → 未設定
    (0, 0.0), ("0", 0.0), ("0.0", 0.0),                                 # 0 → 能力ゼロ
    (5, 5.0), ("12.5", 12.5), (" 800 ", 800.0),                         # 正の数 → 上限
])
def test_parse_value_blank_zero_positive(raw, expected):
    assert parse_capacity_value(raw, source="x.csv", line=7, column="max_supply") == expected


@pytest.mark.parametrize("raw", ["-1", -0.5, "abc", "1,000", "inf?"])
def test_parse_value_negative_or_not_a_number_stops(raw):
    with pytest.raises(CapacityDataError) as e:
        parse_capacity_value(raw, source="capacity_plan.csv", line=12, column="max_supply")
    msg = str(e.value)
    assert "capacity_plan.csv 12 行目" in msg and "max_supply" in msg and repr(raw) in msg


def test_plan_node_keeps_unset_and_zero_apart():
    mom = _mom(_tree())
    assert mom.cap_hard(3) is None and mom.cap_soft(3) is None          # 既定は未設定
    assert mom.processing_limit(3) is None and mom.planned_capacity(3) is None
    mom.set_capacity(3, cap_hard=0.0)
    assert mom.cap_hard(3) == 0.0 and mom.cap_soft(3) is None
    assert mom.processing_limit(3) == 0.0 and mom.is_zero_capacity(3) and mom.is_open(3)
    mom.set_capacity(3, cap_soft=0.0)
    assert mom.planned_capacity(3) == 0.0
    mom.clear_capacity(3)
    assert mom.cap_hard(3) is None and mom.cap_soft(3) is None and not mom.is_zero_capacity(3)
    # 休業は別の状態：能力の値は変えない
    mom.set_capacity(4, cap_hard=7.0)
    mom.set_operating_shifts(4, 0)
    assert not mom.is_open(4) and mom.cap_hard(4) == 7.0
    assert mom.processing_limit(4) == 0.0 and not mom.is_zero_capacity(4)


# ---------------------------------------------------------------------------
# Unit：能力ゼロの週に P が入らず、繰り延べになる
# ---------------------------------------------------------------------------

def _mom_p_week(t):
    mom = _mom(t)
    return next(w for w in range(N) if mom.psi4supply[w][P])


def test_zero_capacity_week_defers_production_in_identity():
    # 能力を入れずに計画したときの、MOM の生産の週
    t0 = _tree()
    _plan(t0)
    w = _mom_p_week(t0)
    lots = list(_mom(t0).psi4supply[w][P])

    # 同じ週を能力ゼロにする（ほかの週は未設定＝上限なし）
    t = _tree()
    _mom(t).set_capacity(w, cap_hard=0.0)
    fp, res = _plan(t)
    mom = _mom(t)
    assert mom.psi4supply[w][P] == []                       # 能力ゼロの週には P が入らない
    assert mom.psi4supply[w + 1][P][:len(lots)] == lots     # 翌週の P の先頭へ繰り延べ（ID はそのまま）
    assert res.cap_hard_deferred_lots == len(lots)
    assert fp._actual_s[mom.node_id].get(w, []) == []       # その週は出荷しない
    assert sorted(x for v in fp._actual_s[mom.node_id].values() for x in v) == sorted(lots)


def test_unset_week_is_unlimited_as_before():
    t0 = _tree()
    _, res0 = _plan(t0)
    t = _tree()
    for w in range(N):
        _mom(t).clear_capacity(w)                            # 明示的に未設定
    _, res = _plan(t)
    assert res.cap_hard_deferred_lots == 0 == res0.cap_hard_deferred_lots
    assert [list(_mom(t).psi4supply[w][P]) for w in range(N)] == \
           [list(_mom(t0).psi4supply[w][P]) for w in range(N)]


def test_zero_capacity_week_is_sealed_in_legacy():
    t0 = _tree()
    _plan(t0, mode="legacy")
    w = _mom_p_week(t0)
    n = len(_mom(t0).psi4supply[w][P])
    t = _tree()
    _mom(t).set_capacity(w, cap_hard=0.0)
    _, res = _plan(t, mode="legacy")
    assert _mom(t).psi4supply[w][P] == [] and res.cap_hard_sealed == n


def test_backward_carries_everything_out_of_a_zero_capacity_week():
    """Backward（MOM の能力の押し戻し）：能力ゼロの週の要求は、すべて前の週へ。"""
    t0 = _tree()
    assign_demand_lots_from_dict(t0, {(SKU, "JP", "2024-W10"): 4}, cpu_size=1)
    BackwardPlanner(t0).run(SKU)
    w = next(x for x in range(N) if _mom(t0).psi4demand[x][S])   # MOM の要求の週
    assert len(_mom(t0).psi4demand[w][S]) == 4

    t = _tree()
    _mom(t).set_capacity(w, cap_hard=0.0)
    assign_demand_lots_from_dict(t, {(SKU, "JP", "2024-W10"): 4}, cpu_size=1)
    res = BackwardPlanner(t).run(SKU)
    mom = _mom(t)
    assert mom.psi4demand[w][S] == [] and mom.psi4demand[w][P] == []   # 能力ゼロの週には置かない
    assert len(mom.psi4demand[w - 1][S]) == 4               # 前の週の要求へ押し戻し（未設定＝上限なし）
    assert len(mom.psi4demand[w][CO]) == 4                  # 押し戻した分は CO に記録
    assert not res.past_due_lots


def test_closed_week_behaviour_is_unchanged_by_the_capacity_value():
    """休業の週（op_shifts=0）は、能力が未設定でも正の数でも同じに動く（休業が優先）。"""
    outs = []
    for cap in (None, 9.0):
        t = _tree()
        t0 = _tree()
        _plan(t0)
        w = _mom_p_week(t0)
        mom = _mom(t)
        if cap is not None:
            for x in range(N):
                mom.set_capacity(x, cap_hard=cap)
        mom.set_operating_shifts(w, 0)                       # 休業
        _, res = _plan(t)
        outs.append(([list(mom.psi4supply[x][P]) for x in range(N)],
                      [r[:2] for r in res.closure_p_deferred], res.cap_hard_deferred_lots))
        assert mom.psi4supply[w][P] == []
    assert outs[0] == outs[1]
    assert outs[0][1] and outs[0][2] == 0                   # 休業の移動（E2）で、能力の繰り延べではない


# ---------------------------------------------------------------------------
# Integration：CSV → 実ローダ → ノード
# ---------------------------------------------------------------------------

def _csv(tmp_path, text, name="capacity_plan.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_loader_reads_blank_and_zero_apart(tmp_path):
    t = _tree()
    p = _csv(tmp_path, "sku_id,node_name,week,max_supply,cap_soft\n"
                       f"{SKU},{MOM},2024-W03,,\n"            # 空欄 → 未設定
                       f"{SKU},{MOM},2024-W04,0,\n"           # 0 → 能力ゼロ
                       f"{SKU},{MOM},2024-W05,6,0\n"          # 上限 6、計画上の操業能力ゼロ
                       f"{SKU},{MOM},2024-W06,6,4\n")
    stats = load_capacity_dataframe(t, pd.read_csv(p, dtype={"max_supply": str}), WEEKS, source=p)
    mom = _mom(t)
    assert stats == {"applied": 4, "node_not_found": 0, "week_out_of_range": 0}
    assert (mom.cap_hard(2), mom.cap_soft(2)) == (None, None)
    assert (mom.cap_hard(3), mom.processing_limit(3)) == (0.0, 0.0) and mom.is_zero_capacity(3)
    assert (mom.cap_hard(4), mom.cap_soft(4)) == (6.0, 0.0)
    assert (mom.cap_hard(5), mom.cap_soft(5)) == (6.0, 4.0)
    assert mom.cap_hard(10) is None                          # 行の無い週も未設定


def test_loader_without_cap_soft_column_leaves_it_unset(tmp_path):
    t = _tree()
    p = _csv(tmp_path, "sku_id,node_name,week,max_supply\n"
                       f"{SKU},{MOM},2024-W03,5\n")
    load_capacity_dataframe(t, pd.read_csv(p), WEEKS, source=p)
    assert _mom(t).cap_hard(2) == 5.0 and _mom(t).cap_soft(2) is None


def test_loader_stops_on_a_wrong_node_name_and_lists_every_row(tmp_path):
    t = _tree()
    p = _csv(tmp_path, "sku_id,node_name,week,max_supply\n"
                       f"{SKU},{MOM},2024-W03,5\n"
                       f"{SKU},Mother Plnat [SKU-A],2024-W04,5\n"
                       f"SKU-B,{MOM},2024-W05,5\n")
    with pytest.raises(CapacityDataError) as e:
        load_capacity_dataframe(t, pd.read_csv(p), WEEKS, source=p)
    msg = str(e.value)
    assert "2 行あります" in msg and "3 行目" in msg and "4 行目" in msg
    assert "Mother Plnat [SKU-A]" in msg and "'SKU-B'" in msg
    assert "sc_tree_master.csv" in msg                       # 直し方
    assert _mom(t).cap_hard(2) is None                       # 止めたので、1 行も入れていない


def test_loader_stops_on_an_unreadable_value(tmp_path):
    t = _tree()
    p = _csv(tmp_path, "sku_id,node_name,week,max_supply\n"
                       f"{SKU},{MOM},2024-W03,5\n"
                       f"{SKU},{MOM},2024-W04,-3\n")
    with pytest.raises(CapacityDataError, match="3 行目"):
        load_capacity_dataframe(t, pd.read_csv(p, dtype={"max_supply": str}), WEEKS, source=p)


def test_loader_warns_but_does_not_stop_outside_the_horizon(tmp_path):
    t = _tree()
    p = _csv(tmp_path, "sku_id,node_name,week,max_supply\n"
                       f"{SKU},{MOM},2024-W03,5\n"
                       f"{SKU},{MOM},2030-W01,5\n")
    with pytest.warns(RuntimeWarning, match="計画期間の外の週の行 1 件"):
        stats = load_capacity_dataframe(t, pd.read_csv(p), WEEKS, source=p)
    assert stats["applied"] == 1 and stats["week_out_of_range"] == 1


def test_old_format_aggregates_and_blank_means_unset(tmp_path):
    t = _tree()
    p = _csv(tmp_path, "sku_id,region,week,max_supply\n"
                       f"{SKU},CN,2024-W03,5\n{SKU},IN,2024-W03,2\n"     # 合計 7
                       f"{SKU},CN,2024-W04,0\n{SKU},IN,2024-W04,0\n"     # 合計 0 → 能力ゼロ
                       f"{SKU},CN,2024-W05,5\n{SKU},IN,2024-W05,\n")     # 片方が空欄 → 上限なし
    load_capacity_dataframe(t, pd.read_csv(p, dtype={"max_supply": str}), WEEKS, source=p)
    mom = _mom(t)
    assert (mom.cap_hard(2), mom.cap_hard(3), mom.cap_hard(4)) == (7.0, 0.0, None)
    p2 = _csv(tmp_path, "sku_id,region,week,max_supply\nSKU-Z,CN,2024-W03,5\n", "cap2.csv")
    with pytest.raises(CapacityDataError, match="SKU-Z"):
        load_capacity_dataframe(_tree(), pd.read_csv(p2), WEEKS, source=p2)


def test_capacity_override_plugin_uses_the_same_rule(tmp_path):
    from wom.plugins.capacity_override import CapacityOverridePlugin
    t = _tree()
    cap = _csv(tmp_path, "sku_id,node_name,week,max_supply\n")
    _csv(tmp_path, "sku_id,week,cap_hard,cap_soft\n"
                   f"{SKU},2024-W03,0,\n"           # 能力ゼロ、cap_soft は上書きしない
                   f"{SKU},2024-W04,,3\n", "cap_override.csv")
    _mom(t).set_capacity(2, cap_soft=9.0)
    CapacityOverridePlugin().on_pre_plan(t, WEEKS, {"cap_path": cap})
    mom = _mom(t)
    assert (mom.cap_hard(2), mom.cap_soft(2)) == (0.0, 9.0)
    assert (mom.cap_hard(3), mom.cap_soft(3)) == (None, 3.0)
    _csv(tmp_path, "sku_id,week,cap_hard\n" f"{SKU},2024-W03,abc\n", "cap_override.csv")
    with pytest.raises(CapacityDataError, match="cap_override.csv 2 行目"):
        CapacityOverridePlugin().on_pre_plan(_tree(), WEEKS, {"cap_path": cap})
    _csv(tmp_path, "sku_id,week,cap_hard\nSKU-Q,2024-W03,4\n", "cap_override.csv")
    with pytest.raises(CapacityDataError, match="SKU-Q"):
        CapacityOverridePlugin().on_pre_plan(_tree(), WEEKS, {"cap_path": cap})


def test_holiday_partial_capacity_value_rule(tmp_path):
    from wom.engine.holiday_calendar_plugin import HolidayCalendarPlugin
    head = "holiday_id,holiday_name,start_week,end_week,node_name,effect,value\n"
    p = _csv(tmp_path, head + f"H1,h,2024-W05,2024-W06,{MOM},partial_capacity,0\n", "holiday_calendar.csv")
    rules = HolidayCalendarPlugin._load_rules(p, WEEKS)
    assert rules[0]["value"] == 0.0                           # 0 → 能力ゼロ
    for bad in ("", "-5", "x"):
        _csv(tmp_path, head + f"H1,h,2024-W05,2024-W06,{MOM},partial_capacity,{bad}\n",
             "holiday_calendar.csv")
        with pytest.raises(CapacityDataError):
            HolidayCalendarPlugin._load_rules(p, WEEKS)
    # 能力以外の効果（supply_closure）は、これまでどおり
    _csv(tmp_path, head + f"H2,h,2024-W05,2024-W06,{MOM},supply_closure,\n", "holiday_calendar.csv")
    assert HolidayCalendarPlugin._load_rules(p, WEEKS)[0]["value"] == 0.0


def test_headless_run_stops_on_a_wrong_node_name(tmp_path):
    """CSV からの経路全体（headless）：ノード名の誤りで止まる。"""
    import tools.run_headless_from_folder as rh
    model = str(tmp_path / "bom-test-2026")
    shutil.copytree(os.path.join(REPO, "data", "sample", "bom-test-2026"), model)
    path = os.path.join(model, "capacity_plan.csv")
    text = open(path, encoding="utf-8").read().splitlines()
    head = text[0].split(",")
    row = text[-1].split(",")                 # 実需要の期間の行（助走の生成行は作り直されるため）
    row[head.index("node_name")] = row[head.index("node_name")] + "_typo"
    text[-1] = ",".join(row)
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(text) + "\n")
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        with pytest.raises(CapacityDataError, match="_typo"):
            rh.run(model, plugins_spec="safe", output_ppc_dir=str(tmp_path / "ppc"), verbose=False)
    finally:
        os.chdir(cwd)


def test_smartx_assembly_rows_are_all_read(tmp_path):
    """受入 4：smartx の能力の行が、すべて計画の木のノードに入る（node_not_found 0）。"""
    from wom.engine.sc_tree_builder import build_sc_tree_from_master
    from tools.run_headless_from_folder import _detect_period
    from wom.engine.warmup import weeks_between
    d = os.path.join(REPO, "data", "sample", "smartx-2027-2029")
    start, n = _detect_period(os.path.join(d, "demand_forecast.csv"))
    cap = pd.read_csv(os.path.join(d, "capacity_plan.csv"), dtype={"max_supply": str})
    import datetime as _dt
    y, wk = start.split("-W")
    d0 = _dt.date.fromisocalendar(int(y), int(wk), 1)
    weeks = [f"{(d0 + _dt.timedelta(weeks=i)).isocalendar()[0]}-W{(d0 + _dt.timedelta(weeks=i)).isocalendar()[1]:02d}"
             for i in range(n)]
    tree = build_sc_tree_from_master(pd.read_csv(os.path.join(d, "sc_tree_master.csv")), weeks)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stats = load_capacity_dataframe(tree, cap, weeks, source="capacity_plan.csv")
    assert stats["node_not_found"] == 0
    assert stats["applied"] + stats["week_out_of_range"] == len(cap)
    g1 = next(nd for nd in tree.iter_all_nodes("SmartX") if nd.node_name == "AssemblyCN_g1")
    g3 = next(nd for nd in tree.iter_all_nodes("SmartXNext") if nd.node_name == "AssemblyCN_g3")
    assert any(g1.cap_hard(w) for w in range(n)) and any(g3.cap_hard(w) for w in range(n))
