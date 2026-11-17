# -*- coding: utf-8 -*-
"""wom/cockpit/case_actions.py — 画面の操作の検査・裏の実行・費用の前提だけを変えたとき・増産の有償の週の候補
（RequestLetter_Cockpit_Stage3_Step3 §5）。小さな合成のモデルで、道具は差し替えて速く。"""
import json
import os
import threading

import pandas as pd
import pytest

from wom.cockpit import case_actions as A
from wom.cockpit import case_runner as R
from wom.cockpit import cases as C

from test_cockpit_cases import _model, PLAN


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


def _fast(order):
    def make(n):
        def f(ctx):
            order.append(n)
            if n == "check":
                ctx["summary"] = {"P0_report": 1.0}
            return {}
        return f
    return {n: make(n) for n in R.STAGE_FUNCS}


def test_input_checks_return_messages_not_exceptions(ws):
    r = A.set_launch_week(ws, "C01", "PA", "X", "2027-1")
    assert not r.ok and "週のラベルではない" in r.message and "直し方" in r.message
    r = A.set_launch_week(ws, "C01", "PA", "Z", "2027-W02")
    assert not r.ok and "投入の表に無い" in r.message
    r = A.set_planned_output(ws, "C01", "PA", None, "abc")
    assert not r.ok and "数ではない" in r.message
    r = A.set_planned_output(ws, "C01", "PA", None, "11")                    # max_supply 10
    assert not r.ok and "max_supply を超える" in r.message
    r = A.copy(ws, "C01", "  ")
    assert not r.ok and "名前が空" in r.message
    r = A.set_fixed_cost(ws, "C01", [{"cost_item": "f", "entity": "E", "paid_start_week": "2027-W03",
                                      "paid_end_week": "2027-W01", "currency": "JPY"}])
    assert not r.ok and "最初の週より前" in r.message
    r = A.set_fixed_cost(ws, "C01", [{"cost_item": "f", "entity": "E", "paid_start_week": "2027-W01",
                                      "paid_end_week": "2027-W02", "weekly_amount": "-5", "currency": "JPY"}])
    assert not r.ok and "0 以上の数ではない" in r.message
    r = A.set_policy(ws, "C01", allocation_file="no_such.csv", week_rule="earliest_first")
    assert not r.ok and "数量枠のファイル" in r.message


def test_copy_and_changes(ws):
    r = A.copy(ws, "C01", "early")
    assert r.ok and r.data["id"] == "C02"
    assert A.set_launch_week(ws, "C02", "PA", "Y", "2027-W01").ok
    assert A.set_planned_output(ws, "C02", "PA", None, "9").ok
    assert A.set_fixed_cost(ws, "C02", [{"cost_item": "f", "display_name": "販路費", "entity": "E",
                                         "paid_start_week": "2027-W01", "paid_end_week": "2027-W02",
                                         "weekly_amount": "", "currency": "JPY", "count_outside_report": True}]).ok
    d = pd.read_csv(os.path.join(ws, "C02", "inputs", "fixed_cost.csv"), dtype=str, keep_default_na=False)
    assert (d.iloc[0]["display_name"], d.iloc[0]["count_outside_report"]) == ("販路費", "1")


def test_worker_runs_one_job_and_reports_progress(ws):
    w = A.Worker()
    order = []
    assert w.start_run(ws, "C01", stage_funcs=_fast(order)).ok
    w.wait(30)
    ev = w.poll()
    kinds = [e["kind"] for e in ev]
    assert kinds[0] == "start" and kinds[-1] == "done"
    prog = [e for e in ev if e["kind"] == "progress"]
    assert [e["stage"] for e in prog if e["event"] == "end"] == R.STAGES_PLAIN
    assert all("elapsed" in e for e in prog)
    assert C.status(ws, "C01")["state"] == C.ST_DONE


def test_worker_refuses_a_second_job_and_reports_a_stop(ws):
    gate = threading.Event()
    funcs = _fast([])
    funcs["demand"] = lambda ctx: gate.wait(10) and {}
    w = A.Worker()
    assert w.start_run(ws, "C01", stage_funcs=funcs).ok
    r = w.start_run(ws, "C01")
    assert not r.ok and ("ほかの実行が動いている" in r.message or "実行中" in r.message)
    gate.set()
    w.wait(30)
    w.poll()

    def stop(ctx):
        raise R.StageStop(C.ST_CONFLICT, "P|X: 置けない 3 lot\n  -> out")
    funcs = _fast([])
    funcs["plan_ppc"] = stop
    assert w.start_run(ws, "C01", stage_funcs=funcs).ok
    w.wait(30)
    ev = w.poll()
    assert ev[-1]["kind"] == "error" and ev[-1]["state"] == C.ST_CONFLICT and "置けない 3 lot" in ev[-1]["message"]


def test_can_compare_needs_two_done_cases(ws):
    A.copy(ws, "C01", "b")
    r = A.can_compare(ws, "C01", None)
    assert not r.ok and "選ばれていない" in r.message
    r = A.can_compare(ws, "C01", "C02")
    assert not r.ok and "実行してから" in r.message


def _fake_compare(ws, base, alt, pw_rows):
    d = os.path.join(ws, "compare", f"{base}__{alt}")
    os.makedirs(d, exist_ok=True)
    pd.DataFrame(pw_rows).to_csv(os.path.join(d, "planned_output_weeks.csv"), index=False)
    for cid in (base, alt):
        case = C.read_case(ws, cid)
        case["run"] = {"state": C.ST_DONE, "input_hashes": C.input_hashes(ws, cid), "stages": [], "summary": {}}
        C.write_case(ws, cid, case)
    json.dump({"base": base, "alt": alt, "state": C.ST_DONE,
               "base_input_hashes": C.read_case(ws, base)["run"]["input_hashes"],
               "alt_input_hashes": C.read_case(ws, alt)["run"]["input_hashes"],
               "base_fixed_cost_sha256": C.fixed_cost_hash(ws, base),
               "alt_fixed_cost_sha256": C.fixed_cost_hash(ws, alt)},
              open(os.path.join(d, "compare.json"), "w", encoding="utf-8"))


def test_raise_week_candidates_and_apply(ws):
    A.copy(ws, "C01", "raised")
    _fake_compare(ws, "C01", "C02", [
        {"case": "C02", "product": "PA", "factory": "Fac_A", "shippable_soft_values": "9", "first_week_at_cap": "2026-W53",
         "last_week_at_cap": "2027-W03", "span_weeks": 4, "span_weeks_in_report": 3, "span_weeks_outside_report": 1,
         "weeks_below_cap_inside_span": 0},
        {"case": "C01", "product": "PA", "factory": "Fac_A", "shippable_soft_values": "8", "first_week_at_cap": "2026-W52",
         "last_week_at_cap": "2027-W04", "span_weeks": 5, "span_weeks_in_report": 4, "span_weeks_outside_report": 1,
         "weeks_below_cap_inside_span": 0}])
    assert R.compare_status(ws, "C01", "C02") == C.ST_DONE
    c = A.raise_week_candidates(ws, "C02")
    assert [(x["first"], x["last"], x["span"]) for x in c] == [("2026-W53", "2027-W03", 4)]
    assert not os.path.exists(os.path.join(ws, "C02", "inputs", "fixed_cost.csv"))   # nothing written yet
    r = A.apply_raise_weeks(ws, "C02", c[0], "E", "JPY")
    assert r.ok
    d = pd.read_csv(os.path.join(ws, "C02", "inputs", "fixed_cost.csv"), dtype=str, keep_default_na=False).iloc[0]
    assert (d["cost_item"], d["paid_start_week"], d["paid_end_week"], d["weekly_amount"], d["count_outside_report"]) == \
        ("planned_output_raise", "2026-W53", "2027-W03", "", "1")
    assert R.compare_status(ws, "C01", "C02") == R.ST_COST_CHANGED           # cost premises changed -> compare again
    assert C.status(ws, "C02")["state"] == C.ST_DONE                         # the case stays 済み


def test_old_comparison_without_the_cost_record_asks_to_compare_again(ws):
    A.copy(ws, "C01", "b")
    _fake_compare(ws, "C01", "C02", [])
    p = os.path.join(ws, "compare", "C01__C02", "compare.json")
    rec = json.load(open(p, encoding="utf-8"))
    rec.pop("base_fixed_cost_sha256")
    json.dump(rec, open(p, "w", encoding="utf-8"))
    assert R.compare_status(ws, "C01", "C02") == R.ST_COST_CHANGED


# ── 段 4 B0：親より上げた週を候補に出す ──────────────────────────────────
def test_raised_range_versus_the_parent_is_offered_first(ws):
    A.copy(ws, "C01", "raised")
    r = A.set_planned_output(ws, "C02", "PA", None, "9", "2027-W02", "2027-W03")
    assert r.ok and "2027-W02〜2027-W03" in r.message
    c = A.raise_week_candidates(ws, "C02")
    assert c[0]["kind"] == "raised"
    assert (c[0]["first"], c[0]["last"], c[0]["span"], c[0]["in_report"], c[0]["at_cap"]) == \
        ("2027-W02", "2027-W03", 2, 2, None)                                 # no comparison yet: not known
    assert not os.path.exists(os.path.join(ws, "C02", "inputs", "fixed_cost.csv"))   # nothing written yet
    d = os.path.join(ws, "compare", "C01__C02")
    os.makedirs(d)
    pd.DataFrame([{"case": "C02", "product": "PA", "week": w, "production_lots": p, "shippable_soft": 9}
                  for w, p in (("2027-W02", 9), ("2027-W03", 8))]).to_csv(os.path.join(d, "factory_weekly.csv"),
                                                                         index=False)
    c = A.raise_week_candidates(ws, "C02")
    assert (c[0]["at_cap"], c[0]["gaps"]) == (1, 1)
    assert A.apply_raise_weeks(ws, "C02", c[0], "E", "JPY").ok
    f = pd.read_csv(os.path.join(ws, "C02", "inputs", "fixed_cost.csv"), dtype=str, keep_default_na=False).iloc[0]
    assert (f["paid_start_week"], f["paid_end_week"], f["count_outside_report"]) == ("2027-W02", "2027-W03", "1")
    assert "親の案より上げた週" in f["note"]
    assert A.raise_week_candidates(ws, "C01") == []                          # the first case has no parent


def test_measured_candidate_is_not_offered_for_a_mixed_plan(ws):
    A.copy(ws, "C01", "mixed")
    _fake_compare(ws, "C01", "C02", [
        {"case": "C02", "product": "PA", "factory": "Fac_A", "shippable_soft_values": "8,9",
         "first_week_at_cap": "2026-W52", "last_week_at_cap": "2027-W04", "span_weeks": 5, "span_weeks_in_report": 4,
         "span_weeks_outside_report": 1, "weeks_below_cap_inside_span": 0}])
    assert A.raise_week_candidates(ws, "C02") == []


# ── 段 4 A1・A5：シフト…・週の範囲の入力の検査 ─────────────────────────────
def test_shifts_action_and_range_checks(ws):
    from test_cockpit_cases import CAL
    r = A.set_shifts(ws, "C01", "PA", "Fac_A", "21")
    assert not r.ok and "操業カレンダーが無い" in r.message
    with open(os.path.join(ws, "C01", "model", "operating_calendar.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(CAL)
    assert A.has_calendar(ws, "C01")
    for bad in ("0", "22", "x", ""):
        assert not A.set_shifts(ws, "C01", "PA", "Fac_A", bad).ok
    r = A.set_shifts(ws, "C01", "PA", "Fac_A", "21", "2027-W03", "")
    assert not r.ok and "片方だけ" in r.message
    r = A.set_shifts(ws, "C01", "PA", "Fac_A", "21", "2027-W04", "2027-W03")
    assert not r.ok and "より前" in r.message
    r = A.set_shifts(ws, "C01", "PA", "Fac_A", "21", "2027-w3", "2027-W04")
    assert not r.ok and "週のラベル" in r.message
    r = A.set_shifts(ws, "C01", "PA", "Fac_A", "21")
    assert r.ok and "休業の 1 週（2027-W02）は休業のまま" in r.message
    r = A.set_planned_output(ws, "C01", "PA", None, "9", "", "")
    assert not r.ok and "シフト" in r.message                          # the calendar decides: use シフト…


def test_raised_shifts_versus_the_parent(ws):
    from test_cockpit_cases import CAL
    with open(os.path.join(ws, "C01", "model", "operating_calendar.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(CAL)
    A.copy(ws, "C01", "more shifts")
    assert A.set_shifts(ws, "C02", "PA", "Fac_A", "21").ok
    c = [x for x in A.raise_week_candidates(ws, "C02") if x["kind"] == "raised"]
    assert [(x["first"], x["last"], x["span"], x["cap"]) for x in c] == \
        [("2026-W52", "2027-W04", 5, "18→21（シフト）")]                 # the closed 2027-W02 does not split it
