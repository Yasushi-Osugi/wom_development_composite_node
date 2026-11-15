# -*- coding: utf-8 -*-
"""wom/cockpit/case_runner.py — 段の順と止まったときの記録（道具を差し替えた単体）と、化粧品の写しでの通し
（RequestLetter_Cockpit_Stage3_Step1 §4）。"""
import json
import os

import pytest

from wom.cockpit import cases as C
from wom.cockpit import case_runner as R

from test_cockpit_cases import _model, PLAN   # the small synthetic model

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COS = os.path.join(REPO, "data", "sample", "cosmetics-sg-th-2027-2029")
APPX = os.path.join(REPO, "docs", "development", "WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix", "inputs")


@pytest.fixture
def ws(tmp_path):
    src = _model(tmp_path)
    (tmp_path / "src_model" / "planning_config.csv").write_text(
        'key,value\nrecommended_plugins,"HolidayCalendarPlugin"\n', encoding="utf-8")
    w = str(tmp_path / "ws")
    C.create_workspace(w, src, max_age_weeks=52)
    plan = tmp_path / "plan.csv"
    plan.write_text(PLAN, encoding="utf-8", newline="\n")
    C.set_entry_plan(w, "C01", str(plan))
    return w


def _recording(order, fail=None, exc=None):
    def make(name):
        def f(ctx):
            order.append(name)
            if name == fail:
                raise exc
            if name == "check":
                ctx["summary"] = {"P0_report": 123.0}
            return {"ok": name}
        return f
    return {n: make(n) for n in R.STAGE_FUNCS}


def test_stage_order_progress_and_record(ws):
    order, events = [], []
    rec = R.run_case(ws, "C01", on_progress=events.append, stage_funcs=_recording(order))
    assert order == R.STAGES_PLAIN
    assert rec["state"] == C.ST_DONE and rec["summary"] == {"P0_report": 123.0}
    assert rec["plugins"] == "HolidayCalendarPlugin"
    assert [s["stage"] for s in rec["stages"]] == R.STAGES_PLAIN
    assert all(s["seconds"] is not None for s in rec["stages"])
    assert [(e["stage"], e["event"]) for e in events][:2] == [("demand", "start"), ("demand", "end")]
    assert events[-1]["index"] == events[-1]["total"] == len(R.STAGES_PLAIN)
    assert C.status(ws, "C01")["state"] == C.ST_DONE
    assert C.read_case(ws, "C01")["run"]["state"] == C.ST_DONE


def test_policy_case_runs_the_allocation_stage(ws, tmp_path):
    a = tmp_path / "a.csv"
    a.write_text("sku_id,region,alloc_lots\nPA,X,1\n", encoding="utf-8")
    C.set_policy(ws, "C01", allocation_file=str(a), week_rule="earliest_first")
    order = []
    R.run_case(ws, "C01", stage_funcs=_recording(order))
    assert order == R.STAGES_POLICY


def test_a_stop_is_recorded_with_the_tool_message_and_later_stages_do_not_run(ws):
    order = []
    rec = R.run_case(ws, "C01", stage_funcs=_recording(order, "valuechain",
                                                        R.StageStop(C.ST_STOPPED, "道具の言葉そのまま")))
    assert order == ["demand", "plan_ppc", "valuechain"]
    assert rec["state"] == C.ST_STOPPED and rec["message"] == "道具の言葉そのまま"
    assert "Value Chain" in rec["reason"]
    assert C.status(ws, "C01")["state"] == C.ST_STOPPED
    # an unexpected error is a stop with its text, not a crash
    rec = R.run_case(ws, "C01", stage_funcs=_recording([], "check", KeyError("x")))
    assert rec["state"] == C.ST_STOPPED and "KeyError" in rec["message"]


@pytest.mark.parametrize("code,state", [(3, C.ST_CONFLICT), (4, C.ST_SHORT), (1, C.ST_INCONSISTENT),
                                        (2, C.ST_STOPPED)])
def test_allocation_exit_codes(ws, tmp_path, code, state):
    a = tmp_path / "a.csv"
    a.write_text("sku_id,region,alloc_lots\nPA,X,1\n", encoding="utf-8")
    C.set_policy(ws, "C01", allocation_file=str(a), week_rule="earliest_first")
    calls = []

    def tool(module, args, log):
        calls.append(module)
        return code, f"line1\n衝突の理由 {code}\n"

    funcs = {"demand": lambda ctx: {}}
    rec = R.run_case(ws, "C01", tool=tool, stage_funcs=funcs)
    assert calls == ["tools.run_quantity_allocation"]
    assert rec["state"] == state and f"衝突の理由 {code}" in rec["message"]
    assert rec["stages"][-1] == {"stage": "allocation", "seconds": None, "stopped": state}


def test_demand_stage_stops_on_a_hand_edited_demand(ws):
    p = os.path.join(ws, "C01", "model", "demand_forecast.csv")
    open(p, "a", encoding="utf-8").write("PA,X,2027-W04,1\n")
    rec = R.run_case(ws, "C01", tool=lambda *a: (0, ""))
    assert rec["state"] == C.ST_STOPPED and "投入の表から道具 1 で作った需要と違います" in rec["message"]


def test_no_recommended_plugins_stops(ws):
    os.remove(os.path.join(ws, "C01", "model", "planning_config.csv"))
    rec = R.run_case(ws, "C01", stage_funcs=_recording([]))
    assert rec["state"] == C.ST_STOPPED and "recommended_plugins" in rec["message"]


def test_compare_needs_done_cases(ws):
    C.copy_case(ws, "C01", "b")
    with pytest.raises(C.CaseError, match="済み"):
        R.compare_cases(ws, "C01", "C02")


def test_cosmetics_base_late_case_end_to_end(tmp_path):
    """The base late case built only by operations: P0 and cream deliveries as in the request letter §1."""
    w = str(tmp_path / "ws")
    C.create_workspace(w, COS, max_age_weeks=52, first_name="基準・後期")
    C.set_entry_plan(w, "C01", os.path.join(APPX, "market_entry_plan_A_late.csv"))
    C.set_capacity(w, "C01", "COS_Serum", 17, 14)
    C.set_capacity(w, "C01", "COS_Cream", 13, 11)
    rec = R.run_case(w, "C01")
    assert rec["state"] == C.ST_DONE, rec["message"]
    s = rec["summary"]
    assert s["P0_report"] == pytest.approx(606_871_080, abs=0.5)
    assert s["deliveries_by_sku"]["COS_Cream"] == 1680
    assert s["backlog_end_by_key"] == {"COS_Cream:TH_Distributor": 88, "COS_Serum:TH_Distributor": 104}
    assert s["valuation"] == "評価済み"
