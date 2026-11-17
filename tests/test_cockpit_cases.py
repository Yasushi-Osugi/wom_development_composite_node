# -*- coding: utf-8 -*-
"""wom/cockpit/cases.py — 案の置き場と記録（RequestLetter_Cockpit_Stage3_Step1 §4）。小さな合成のモデルで。"""
import hashlib
import json
import os
import shutil

import pytest

from wom.cockpit import cases as C

TREE = """node_name,parent_node,product_name,node_type,side,lt_wks,region
SP_A,,PA,supply_point,outbound,0,
DC_A,SP_A,PA,dad,outbound,1,X
Shop_X,DC_A,PA,leaf_out,outbound,1,X
Shop_Y,DC_A,PA,leaf_out,outbound,1,Y
Fac_A,,PA,mom,inbound,1,JP
"""
PLAN = """sku_id,region,launch_week,steady_lots_per_week,ramp_weeks,ramp_ratio,price,currency,promotion_note,basis_note
PA,X,2027-W02,4,2,0.5,,,,
PA,Y,2027-W03,2,0,0.5,,,,
"""
CAP = """sku_id,node_name,week,max_supply,cap_soft,source
PA,Fac_A,2026-W52,10,8,warmup
PA,Fac_A,2027-W01,10,8,plan
PA,Fac_A,2027-W02,10,8,plan
PA,Fac_A,2027-W03,10,8,plan
PA,Fac_A,2027-W04,10,8,plan
"""


def _model(tmp_path):
    m = tmp_path / "src_model"
    m.mkdir()
    (m / "sc_tree_master.csv").write_text(TREE, encoding="utf-8", newline="\n")
    (m / "capacity_plan.csv").write_text(CAP, encoding="utf-8", newline="\n")
    (m / "vc_config.csv").write_text("key,value\nreport_start,2027-W01\n", encoding="utf-8", newline="\n")
    rows = ["sku_id,region,week,quantity"] + [f"PA,{r},{w},0" for w in
                                              ("2026-W52", "2027-W01", "2027-W02", "2027-W03", "2027-W04")
                                              for r in ("X", "Y")]
    (m / "demand_forecast.csv").write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return str(m)


def _hashes(d):
    out = {}
    for root, _ds, fs in os.walk(d):
        for f in fs:
            p = os.path.join(root, f)
            out[os.path.relpath(p, d)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


@pytest.fixture
def ws(tmp_path):
    src = _model(tmp_path)
    before = _hashes(src)
    w = str(tmp_path / "ws")
    C.create_workspace(w, src, max_age_weeks=52, first_name="base")
    plan = tmp_path / "plan.csv"
    plan.write_text(PLAN, encoding="utf-8", newline="\n")
    C.set_entry_plan(w, "C01", str(plan))
    yield w, src, before


def _demand(w, cid):
    with open(os.path.join(w, cid, "model", "demand_forecast.csv"), encoding="utf-8") as f:
        return {(l.split(",")[0], l.split(",")[1], l.split(",")[2]): int(l.split(",")[3])
                for l in f.read().splitlines()[1:]}


def test_workspace_records_and_does_not_write_the_source(ws):
    w, src, before = ws
    info = json.load(open(os.path.join(w, "workspace.json"), encoding="utf-8"))
    assert info["demand_period"] == {"start": "2026-W52", "end": "2027-W04"}
    assert info["report_period"] == {"start": "2027-W01", "end": "2027-W04"}
    assert info["max_age_weeks"] == 52
    assert _hashes(src) == before                          # the source model is never written
    d = _demand(w, "C01")                                  # tool 1 made the demand from the entry plan
    assert d[("PA", "X", "2027-W01")] == 0 and d[("PA", "X", "2027-W02")] == 2 and d[("PA", "X", "2027-W04")] == 4
    assert d[("PA", "Y", "2027-W03")] == 2


def test_workspace_refuses_a_place_inside_the_model_or_not_empty(tmp_path):
    src = _model(tmp_path)
    with pytest.raises(C.CaseError, match="中にあります"):
        C.create_workspace(os.path.join(src, "ws"), src, max_age_weeks=52)
    w = tmp_path / "busy"
    w.mkdir()
    (w / "x.txt").write_text("x")
    with pytest.raises(C.CaseError, match="空ではありません"):
        C.create_workspace(str(w), src, max_age_weeks=52)


def test_copy_does_not_copy_run_and_records_the_parent(ws):
    w, _src, _b = ws
    os.makedirs(os.path.join(w, "C01", "run"))
    open(os.path.join(w, "C01", "run", "snapshot.json"), "w").write("{}")
    os.makedirs(os.path.join(w, "C01", "udp"))
    cid = C.copy_case(w, "C01", "early")
    assert cid == "C02"
    assert not os.path.exists(os.path.join(w, "C02", "run"))
    assert not os.path.exists(os.path.join(w, "C02", "udp"))
    case = C.read_case(w, "C02")
    assert case["parent"] == "C01" and case["name"] == "early" and case["run"] is None
    assert C.copy_case(w, "C02", "x") == "C03"
    assert C.read_case(w, "C03")["parent"] == "C02"
    assert C.case_ids(w) == ["C01", "C02", "C03"]


def test_launch_week_changes_one_key_and_regenerates_the_demand(ws):
    w, _src, _b = ws
    C.copy_case(w, "C01", "early")
    C.set_launch_week(w, "C02", "PA", "Y", "2027-W01")
    with open(os.path.join(w, "C02", "model", "market_entry_plan.csv"), encoding="utf-8") as f:
        text = f.read()
    assert text == PLAN.replace("PA,Y,2027-W03", "PA,Y,2027-W01")   # only that cell
    d = _demand(w, "C02")
    assert d[("PA", "Y", "2027-W01")] == 2 and d[("PA", "X", "2027-W02")] == 2
    assert _demand(w, "C01")[("PA", "Y", "2027-W01")] == 0          # the parent is untouched
    with pytest.raises(C.CaseError, match="1 行のはず"):
        C.set_launch_week(w, "C02", "PA", "Z", "2027-W01")
    with pytest.raises(C.CaseError, match="週のラベル"):
        C.set_launch_week(w, "C02", "PA", "Y", "2027-1")


def test_launch_week_outside_the_period_stops_and_keeps_the_files(ws):
    w, _src, _b = ws
    p = os.path.join(w, "C01", "model", "market_entry_plan.csv")
    before = open(p, "rb").read(), _demand(w, "C01")
    with pytest.raises(C.CaseError, match="道具 1"):
        C.set_launch_week(w, "C01", "PA", "X", "2028-W10")
    assert open(p, "rb").read() == before[0] and _demand(w, "C01") == before[1]


def _cap(w, cid):
    with open(os.path.join(w, cid, "model", "capacity_plan.csv"), encoding="utf-8") as f:
        return f.read()


def test_planned_output_writes_every_row_and_stops_above_max_supply(ws):
    w, _src, _b = ws
    C.set_planned_output(w, "C01", "PA", 9)
    assert _cap(w, "C01") == CAP.replace(",10,8,", ",10,9,")          # warm-up row too; nothing else
    with pytest.raises(C.CaseError, match="max_supply を超える"):
        C.set_planned_output(w, "C01", "PA", 11)
    assert _cap(w, "C01") == CAP.replace(",10,8,", ",10,9,")          # unchanged after the stop
    with pytest.raises(C.CaseError, match="行がありません"):
        C.set_planned_output(w, "C01", "PB", 5)


def test_capacity_pair_and_its_checks(ws):
    w, _src, _b = ws
    C.set_capacity(w, "C01", "PA", 13, 11)
    assert _cap(w, "C01") == CAP.replace(",10,8,", ",13,11,")
    with pytest.raises(C.CaseError, match="超えています"):
        C.set_capacity(w, "C01", "PA", 5, 6)
    with pytest.raises(C.CaseError, match="負"):
        C.set_capacity(w, "C01", "PA", -1, 0)


def test_policy_and_fixed_cost_files(ws, tmp_path):
    w, _src, _b = ws
    alloc = tmp_path / "alloc.csv"
    alloc.write_text("sku_id,region,alloc_lots\nPA,X,1\n", encoding="utf-8")
    with pytest.raises(C.CaseError, match="週の規則"):
        C.set_policy(w, "C01", allocation_file=str(alloc))
    pol = C.set_policy(w, "C01", allocation_file=str(alloc), week_rule="earliest_first")
    assert pol["allocation_file"] == "inputs/alloc.csv"
    assert os.path.exists(os.path.join(w, "C01", "inputs", "alloc.csv"))
    C.set_policy(w, "C01", none=True)
    assert C.read_case(w, "C01")["inputs"]["policy"] is None
    assert not os.path.exists(os.path.join(w, "C01", "inputs", "alloc.csv"))
    pair = tmp_path / "fc.csv"
    pair.write_text("case,cost_item,entity,paid_start_week,paid_end_week,weekly_amount,currency,note\n"
                    "base,F,E,2027-W02,2027-W04,,JPY,n\nalt,F,E,2027-W01,2027-W04,100,JPY,n\n", encoding="utf-8")
    with pytest.raises(C.CaseError, match="side"):
        C.set_fixed_cost(w, "C01", file=str(pair))
    C.set_fixed_cost(w, "C01", file=str(pair), side="alt")
    with open(os.path.join(w, "C01", "inputs", "fixed_cost.csv"), encoding="utf-8") as f:
        assert f.read() == ("cost_item,entity,paid_start_week,paid_end_week,weekly_amount,currency,note\n"
                            "F,E,2027-W01,2027-W04,100,JPY,n\n")
    C.set_fixed_cost(w, "C01", file=str(pair), side="base")
    assert C.input_summary(w, "C01")["fixed_cost"][0]["weekly_amount"] == "未設定"   # blank is not 0


def _fake_done(w, cid):
    case = C.read_case(w, cid)
    case["run"] = {"state": C.ST_DONE, "input_hashes": C.input_hashes(w, cid), "summary": {"P0_report": 1.0},
                   "stages": []}
    C.write_case(w, cid, case)


def test_hash_detects_changed_inputs_and_revert_returns_to_done(ws):
    w, _src, _b = ws
    assert C.status(w, "C01")["state"] == C.ST_NOT_RUN
    _fake_done(w, "C01")
    assert C.status(w, "C01")["state"] == C.ST_DONE
    C.set_planned_output(w, "C01", "PA", 9)
    st = C.status(w, "C01")
    assert st["state"] == C.ST_CHANGED and st["changed_files"] == ["model/capacity_plan.csv"]
    assert C.list_cases(w)[0]["result"] is None                    # no result for changed inputs
    C.set_planned_output(w, "C01", "PA", 8)
    assert C.status(w, "C01")["state"] == C.ST_DONE
    # a hand edit of a model file is caught too
    p = os.path.join(w, "C01", "model", "demand_forecast.csv")
    open(p, "a", encoding="utf-8").write("PA,X,2027-W04,1\n")
    assert C.status(w, "C01")["state"] == C.ST_CHANGED
    # the cost premises are read only by the comparison: changing them keeps 済み
    C.set_fixed_cost(w, "C01", rows=[{"cost_item": "F", "entity": "E", "paid_start_week": "2027-W01",
                                      "paid_end_week": "2027-W02", "weekly_amount": "", "currency": "JPY",
                                      "note": ""}])
    assert "inputs/fixed_cost.csv" not in C.input_hashes(w, "C01")


def test_reopen_elsewhere_gives_the_same_table(ws, tmp_path):
    w, _src, _b = ws
    C.copy_case(w, "C01", "early")
    C.set_launch_week(w, "C02", "PA", "Y", "2027-W01")
    _fake_done(w, "C01")
    a = C.format_list(C.list_cases(w))
    w2 = str(tmp_path / "moved")
    shutil.copytree(w, w2)
    assert C.format_list(C.list_cases(w2)) == a
    assert C.status(w2, "C01")["state"] == C.ST_DONE


# ── 段 4 B0：計画の生産量を週の範囲で変える ─────────────────────────────────
def test_planned_output_week_range_changes_only_the_range(ws):
    w, _src, _b = ws
    r = C.set_planned_output(w, "C01", "PA", 9, from_week="2027-W02", to_week="2027-W03")
    assert r["rows"] == 2 and r["weeks"] == ["2027-W02", "2027-W03"]
    want = CAP.replace("2027-W02,10,8,", "2027-W02,10,9,").replace("2027-W03,10,8,", "2027-W03,10,9,")
    assert _cap(w, "C01") == want                                      # rows outside the range untouched
    ch = C.read_case(w, "C01")["changes"][-1]
    assert ch["what"] == "planned_output" and ch["weeks"] == ["2027-W02", "2027-W03"]
    s = C.input_summary(w, "C01")["capacity"]["PA@Fac_A"]
    assert s == "10/8・9（週で違う）"                                    # never shown as one pair


def test_planned_output_week_range_checks(ws):
    w, _src, _b = ws
    with pytest.raises(C.CaseError, match="行に週"):
        C.set_planned_output(w, "C01", "PA", 9, from_week="2026-W40", to_week="2027-W02")
    with pytest.raises(C.CaseError, match="両方"):
        C.set_planned_output(w, "C01", "PA", 9, from_week="2027-W02")
    with pytest.raises(C.CaseError, match="より前"):
        C.set_planned_output(w, "C01", "PA", 9, from_week="2027-W03", to_week="2027-W02")
    with pytest.raises(C.CaseError, match="max_supply を超える"):
        C.set_planned_output(w, "C01", "PA", 11, from_week="2027-W02", to_week="2027-W02")
    assert _cap(w, "C01") == CAP                                       # nothing written after a stop


def test_capacity_runs_and_text():
    rows = [{"week": w, "max_supply": "13", "cap_soft": v} for w, v in
            (("2027-W01", "11"), ("2027-W02", "12"), ("2027-W03", "12"), ("2027-W04", "11"))]
    assert [(r["from"], r["to"], r["weeks"], r["cap_soft"]) for r in C.capacity_runs(rows)] == \
        [("2027-W01", "2027-W01", 1, "11"), ("2027-W02", "2027-W03", 2, "12"), ("2027-W04", "2027-W04", 1, "11")]
    assert C.capacity_text(rows) == "13/11・12（週で違う）"
    assert C.capacity_text(rows[:1]) == "13/11"


# ── 段 4 A1：シフトを案の入力にする ─────────────────────────────────────
CAL = """sku_id,node_name,week,shifts
PA,Fac_A,2026-W52,18
PA,Fac_A,2027-W01,18
PA,Fac_A,2027-W02,0
PA,Fac_A,2027-W03,18
PA,Fac_A,2027-W04,18
"""


def _cal(w, cid="C01"):
    with open(os.path.join(w, cid, "model", "operating_calendar.csv"), encoding="utf-8") as f:
        return f.read()


def _with_calendar(w):
    with open(os.path.join(w, "C01", "model", "operating_calendar.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(CAL)


def test_set_shifts_keeps_closed_weeks_and_records_the_range(ws):
    w, _src, _b = ws
    _with_calendar(w)
    r = C.set_shifts(w, "C01", "PA", "Fac_A", 21)
    assert r["rows"] == 4 and r["closed_kept"] == ["2027-W02"]
    assert _cal(w) == CAL.replace(",18\n", ",21\n")                  # 0 stays 0
    _with_calendar(w)
    r = C.set_shifts(w, "C01", "PA", "Fac_A", 20, from_week="2027-W03", to_week="2027-W04")
    assert r["weeks"] == ["2027-W03", "2027-W04"] and r["rows"] == 2
    assert _cal(w) == CAL.replace("2027-W03,18", "2027-W03,20").replace("2027-W04,18", "2027-W04,20")
    ch = C.read_case(w, "C01")["changes"][-1]
    assert ch["what"] == "shifts" and ch["weeks"] == ["2027-W03", "2027-W04"] and ch["shifts_to"] == "20"


def test_set_shifts_checks(ws):
    w, _src, _b = ws
    with pytest.raises(C.CaseError, match="操業カレンダー"):
        C.set_shifts(w, "C01", "PA", "Fac_A", 21)                      # no calendar: stop, no file created
    assert not os.path.exists(os.path.join(w, "C01", "model", "operating_calendar.csv"))
    _with_calendar(w)
    for bad in (0, 22, "x", "1.5"):
        with pytest.raises(C.CaseError):
            C.set_shifts(w, "C01", "PA", "Fac_A", bad)
    with pytest.raises(C.CaseError, match="行がありません"):
        C.set_shifts(w, "C01", "PA", "Fac_X", 21)
    assert _cal(w) == CAL


def test_planned_output_stops_where_the_calendar_decides(ws):
    w, _src, _b = ws
    _with_calendar(w)
    with pytest.raises(C.CaseError, match="シフトで決まります"):
        C.set_planned_output(w, "C01", "PA", 9)
    assert _cal(w) == CAL and _cap(w, "C01") == CAP
