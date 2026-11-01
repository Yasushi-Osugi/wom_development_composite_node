# -*- coding: utf-8 -*-
"""
tests/test_upper_demand_plan.py — RequestLetter_BSSEAF_Cosmetics_UpperDemandPlan_U4 §3.3
========================================================================================
上位 Demand Plan のモード 1（wom/allocation/upper_demand_plan.py）。
"""
import csv
import json
import os
import random
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import pytest

import wom.allocation.upper_demand_plan as U
from wom.allocation.handoff import QuantityAllocationError, write_demand_for_quantity_allocation
from wom.model.plan_node import S
from test_quantity_allocation import WEEKS, make_alloc, make_model, _w
from tools.run_quantity_allocation import run_quantity_allocation

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COSMETICS = os.path.join(REPO, "data", "sample", "cosmetics-sg-th-2027-2029")
P2A2 = os.path.join(REPO, "docs", "development", "WOM_BSSEAF_Cosmetics_AllocationP2a_appendix",
                    "allocation", "allocation_qty_P2a2.csv")
RULES = ["proportional_early_tie", "proportional_even", "earliest_first"]


def _ledger_of(tmp_path, d, sku="A", region="X"):
    """A hand ledger with one key (weeks W01..) and a quota file."""
    rows = [{"source_demand_ref": f"{sku}|{region}|2027-W{i + 1:02d}", "sku_id": sku, "region": region,
             "request_week": f"2027-W{i + 1:02d}", "segment": "", "q1": q, "demand_nature": "forecast"}
            for i, q in enumerate(d)]
    return rows


def _select(tmp_path, d, a, rule):
    q = make_alloc(str(tmp_path / "q.csv"), {("A", "X"): a})
    return [r["q2"] for r in U.select_mode1(_ledger_of(tmp_path, d), q, rule)]


# ── 一致：今の handoff と全行一致 ────────────────────────────────────────────
def test_early_tie_equals_the_current_handoff_on_p2a2(tmp_path):
    old = str(tmp_path / "old.csv")
    new = str(tmp_path / "new.csv")
    write_demand_for_quantity_allocation(COSMETICS, P2A2, "X", out_path=old)
    led = U.build_demand_ledger(COSMETICS)
    U.write_engine_demand(U.select_mode1(led, P2A2, "proportional_early_tie"), COSMETICS, new)
    assert open(old, "rb").read() == open(new, "rb").read()


def test_early_tie_equals_the_handoff_with_uneven_demand(tmp_path):
    """同じ端数と違う端数が混じる需要でも全行一致（浮動小数の扱いも同じ）。"""
    random.seed(7)
    d = {("A", "X"): [random.randint(0, 9) for _ in WEEKS], ("A", "Y"): [3, 6, 9, 3, 6, 9, 3, 6, 9, 3, 6, 9],
         ("B", "X"): [1] * 12, ("B", "Y"): [2] * 12}
    m = make_model(str(tmp_path / "m"), demand=d)
    q = make_alloc(str(tmp_path / "q.csv"), {k: sum(v) * 2 // 3 for k, v in d.items()})
    old, new = str(tmp_path / "old.csv"), str(tmp_path / "new.csv")
    write_demand_for_quantity_allocation(m, q, "X", out_path=old)
    U.write_engine_demand(U.select_mode1(U.build_demand_ledger(m), q, "proportional_early_tie"), m, new)
    assert open(old, "rb").read() == open(new, "rb").read()


# ── 行の順に頼らない（UP-V05） ────────────────────────────────────────────────
@pytest.mark.parametrize("rule", RULES)
def test_selection_does_not_depend_on_the_row_order(tmp_path, rule):
    m = str(tmp_path / "m")
    os.makedirs(m)
    src = list(csv.reader(open(os.path.join(COSMETICS, "demand_forecast.csv"), encoding="utf-8")))
    body = src[1:]
    random.Random(3).shuffle(body)
    _w(os.path.join(m, "demand_forecast.csv"), src[0], body)
    a = U.select_mode1(U.build_demand_ledger(COSMETICS), P2A2, rule)
    b = U.select_mode1(U.build_demand_ledger(m), P2A2, rule)
    assert a == b


# ── 規則の手計算 ──────────────────────────────────────────────────────────────
def test_rules_by_hand(tmp_path):
    # d = 4×6, a = 18: raw 3.0 -> every week 3
    assert _select(tmp_path, [4] * 6, 18, "proportional_even") == [3] * 6
    # d = 2×6, a = 8: raw 1.33; floor 1, R = 2, one group of 6: positions floor((j+.5)*6/2) = 1, 4
    assert _select(tmp_path, [2] * 6, 8, "proportional_early_tie") == [2, 2, 1, 1, 1, 1]
    assert _select(tmp_path, [2] * 6, 8, "proportional_even") == [1, 2, 1, 1, 2, 1]
    assert _select(tmp_path, [2] * 6, 8, "earliest_first") == [2, 2, 2, 2, 0, 0]


def test_even_fills_the_larger_remainders_first_and_spreads_only_the_last_group(tmp_path):
    # d = 3,3,1,1,1,1  Σ 10, a = 5: raw 1.5 ×2, 0.5 ×4 -- all remainders .5: one group of 6, R = 5 - 2 = 3, i = 1, 3, 5
    assert _select(tmp_path, [3, 3, 1, 1, 1, 1], 5, "proportional_even") == [1, 2, 0, 1, 0, 1]
    # d = 4,4,1,1,1,1,1,1  Σ 14, a = 7: raw 2.0 ×2, 0.5 ×6: floors 2,2,0.. R = 3, group of 6: i = 1, 3, 5
    assert _select(tmp_path, [4, 4, 1, 1, 1, 1, 1, 1], 7, "proportional_even") == [2, 2, 0, 1, 0, 1, 0, 1]
    # d = 3,1×6  Σ 9, a = 5: raw 1.667 (.667), .556 ×6: floors 1,0..; R = 4; the first group takes 1,
    # then the last group of 6 takes R' = 3 at i = 1, 3, 5
    assert _select(tmp_path, [3, 1, 1, 1, 1, 1, 1], 5, "proportional_even") == [2, 0, 1, 0, 1, 0, 1]


def test_zero_demand_weeks_stay_zero(tmp_path):
    for rule in RULES:
        s = _select(tmp_path, [0, 2, 0, 2, 2, 0], 4, rule)
        assert s[0] == s[2] == s[5] == 0 and sum(s) == 4


def test_earliest_first_on_the_cosmetics_demand():
    """U4 資料 §3 の A1 の減らし方。"""
    sel = U.select_mode1(U.build_demand_ledger(COSMETICS), P2A2, "earliest_first")
    cut = {}
    for x in sel:
        if x["q3"]:
            cut.setdefault((x["sku_id"], x["region"]), {})[x["request_week"]] = (x["q1"], x["q2"])
    w = lambda a, b: [f"2029-W{i:02d}" for i in range(a, b + 1)]
    ss = cut[("COS_Serum", "SG_Distributor")]
    assert sorted(ss) == w(41, 52) and all(v[1] == 0 for v in ss.values())
    st = cut[("COS_Serum", "TH_Distributor")]
    assert sorted(st) == w(45, 52) and all(v[1] == 0 for v in st.values())
    cs = cut[("COS_Cream", "SG_Distributor")]
    assert sorted(cs) == w(40, 52) and cs["2029-W40"] == (5, 2)
    ct = cut[("COS_Cream", "TH_Distributor")]
    assert sorted(ct) == w(44, 52) and ct["2029-W44"] == (3, 2)


# ── 台帳（UP-V01・V02） ───────────────────────────────────────────────────────
@pytest.mark.parametrize("rule", RULES)
def test_ledger_identities(rule):
    led = U.build_demand_ledger(COSMETICS)
    sel = U.select_mode1(led, P2A2, rule)
    assert [x["source_demand_ref"] for x in sel] == [x["source_demand_ref"] for x in led]
    assert sum(1 for r in led if r["q1"] == 0) > 0                  # 0 weeks are in the ledger
    assert all(x["q1"] == x["q2"] + x["q3"] for x in sel)
    assert all(x["week_rule"] == rule and x["reason_code"] and x["tie_key"] == "request_week" for x in sel)
    quota = {(r["sku_id"], r["region"]): int(r["alloc_lots"]) for r in csv.DictReader(open(P2A2, encoding="utf-8-sig"))}
    tot = {}
    for x in sel:
        tot[(x["sku_id"], x["region"])] = tot.get((x["sku_id"], x["region"]), 0) + x["q2"]
    assert {k: v for k, v in tot.items() if v} == quota


def test_quota_over_the_demand_stops_as_in_handoff(tmp_path):
    q = make_alloc(str(tmp_path / "q.csv"), {("A", "X"): 99})
    with pytest.raises(QuantityAllocationError, match="never adds demand"):
        U.select_mode1(_ledger_of(tmp_path, [1, 1]), q)
    q = make_alloc(str(tmp_path / "q2.csv"), {("A", "Z"): 1})
    with pytest.raises(QuantityAllocationError):
        U.select_mode1(_ledger_of(tmp_path, [1, 1]), q)


def test_quota_source_column_is_optional(tmp_path):
    p = str(tmp_path / "q.csv")
    _w(p, ["sku_id", "region", "alloc_lots", "quota_source"], [["A", "X", 1, "P2-a2"]])
    assert sum(x["q2"] for x in U.select_mode1(_ledger_of(tmp_path, [1, 1]), p)) == 1


def test_duplicate_ledger_key_stops(tmp_path):
    m = str(tmp_path / "m")
    os.makedirs(m)
    _w(os.path.join(m, "demand_forecast.csv"), ["sku_id", "region", "week", "quantity"],
       [["A", "X", "2027-W01", 1], ["A", "X", "2027-W01", 2]])
    with pytest.raises(QuantityAllocationError, match="twice"):
        U.build_demand_ledger(m)


# ── 診断（UP-V04） ────────────────────────────────────────────────────────────
def test_time_phased_examples_of_the_design():
    assert U.time_phased_rows([10, 0], [5, 5])[3] == 5
    assert U.time_phased_rows([8, 2], [5, 5])[3] == 3
    assert U.time_phased_rows([2, 2], [5, 5])[3] == 0


def _check_model(tmp_path, cap_by_week, demand):
    m = make_model(str(tmp_path / "m"), demand=demand, cap=5, cap_by_week=cap_by_week)
    q = make_alloc(str(tmp_path / "q.csv"), {k: sum(v) for k, v in demand.items()})
    return m, U.select_mode1(U.build_demand_ledger(m), q)


def test_time_phased_check_reads_lt_and_writes_its_conditions(tmp_path):
    d = {("A", "X"): [0, 0, 8, 2] + [0] * 8, ("A", "Y"): [0] * 12,
         ("B", "X"): [1] * 12, ("B", "Y"): [1] * 12}
    m, sel = _check_model(tmp_path, {}, d)
    rows = [r for r in U.time_phased_check(m, sel) if r["sku_id"] == "A"]
    # LT leaf 1 + DC 1 = 2: the 8 is needed at W01, capacity 5 per week -> reference 3
    assert rows[0]["need_good_lots"] == 8 and rows[1]["need_good_lots"] == 2
    assert rows[0]["ontime_short_ref"] == 3
    assert all("参考値" in r["note"] and "期末の未充足の予測値ではない" in r["note"] for r in rows)
    assert all("近似の条件" in r["approx_conditions"] and "ss_days" in r["approx_conditions"] for r in rows)


def test_time_phased_check_uses_good_lots_like_plan_node():
    """化粧品の C3a の開放の週：美容液 13、クリーム 10（能力 14・11、歩留まり 0.97）。"""
    assert int(14 * 0.97 + 1e-9) == 13 and int(11 * 0.97 + 1e-9) == 10


# ── 照合（UP-V06・V07） ───────────────────────────────────────────────────────
def _short_alloc():
    return {("A", "X"): 18, ("A", "Y"): 9, ("B", "X"): 9, ("B", "Y"): 18}


def _ps(tmp_path, m, **kw):
    a = make_alloc(str(tmp_path / "allocation_qty_t.csv"), _short_alloc())
    return run_quantity_allocation(m, a, out_dir=str(tmp_path / "ps"), **kw)


@pytest.mark.parametrize("rule", RULES)
def test_reconcile_matches_table_2(tmp_path, rule):
    m = make_model(str(tmp_path / "m"), cap=2)
    r = _ps(tmp_path, m, week_rule=rule, udp_out=str(tmp_path / "udp"))
    assert r["status"] == "ok"
    d = r["udp_dir"]
    rows = list(csv.DictReader(open(os.path.join(d, "udp_result_by_request.csv"), encoding="utf-8")))
    assert all(int(x["q2"]) == int(x["on_time"]) + int(x["early"]) + int(x["late"]) + int(x["q5"]) for x in rows)
    t = r["state"]["quantities"]["total"]
    assert sum(int(x["q5"]) for x in rows) == t["q5_backlog_end"]
    assert sum(int(x["on_time"]) for x in rows) == t["q4_delivered"]["on_time"]
    assert sum(int(x["q2"]) for x in rows) == t["q2_in_supply_scope"]
    assert r["state"]["week_rule"] == rule


def test_reconcile_stops_when_a_lot_is_moved(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)

    def shift(tree):
        for prod in tree.products:
            for nd in tree.iter_all_nodes(prod):
                if nd.node_type == "leaf_out":
                    w = next(i for i in range(len(tree.week_labels)) if nd.psi4supply[i][S])
                    lot = nd.psi4supply[w][S].pop()
                    nd.psi4supply[w + 1][S].append(lot)
                    return
    r = _ps(tmp_path, m, udp_out=str(tmp_path / "udp"), _after_plan=shift)
    assert r["status"] == "inconsistent"
    assert not r["checks"]["udp_reconcile_by_request"]["ok"]
    assert not os.path.exists(tmp_path / "udp")


def test_reconcile_raises_against_a_wrong_table_2(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    saved = {}

    def keep(tree):
        saved["tree"] = tree
    r = _ps(tmp_path, m, week_rule="earliest_first", _after_plan=keep)
    assert r["status"] == "ok"
    sel = U.select_mode1(U.build_demand_ledger(m), str(tmp_path / "allocation_qty_t.csv"), "earliest_first")
    fc = os.path.join(str(tmp_path / "ps"), os.path.basename(m), "Q01_flow_check", "flow_check_market.csv")
    rows = list(csv.DictReader(open(fc, encoding="utf-8-sig")))
    assert U.reconcile_by_request(saved["tree"], sel, rows)
    next(x for x in rows if x["leaf"] == "Shop_X")["on_time"] = "999"
    with pytest.raises(U.ReconcileError, match="table 2"):
        U.reconcile_by_request(saved["tree"], sel, rows)


def test_supply_runs_counts_actual_shipments_only_after_the_first_demand(tmp_path):
    d = {("A", "X"): [0, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1], ("A", "Y"): [1] * 12,
         ("B", "X"): [1] * 12, ("B", "Y"): [1] * 12}
    m = make_model(str(tmp_path / "m"), demand=d)
    a = make_alloc(str(tmp_path / "allocation_qty_t.csv"),
                   {("A", "X"): 6, ("A", "Y"): 12, ("B", "X"): 12, ("B", "Y"): 12})
    r = run_quantity_allocation(m, a, out_dir=str(tmp_path / "ps"), week_rule="earliest_first",
                                udp_out=str(tmp_path / "udp"))
    all_rows = list(csv.DictReader(open(os.path.join(r["udp_dir"], "udp_supply_runs.csv"), encoding="utf-8")))
    ax = next(z for z in all_rows if z["sku_id"] == "A" and z["region"] == "X")
    # kept W03-W05, W07-W09 (6 lots); W10-W12 are selected out; W06 has no demand and is not counted
    assert ax["zero_supply_weeks"] == "3" and ax["longest_zero_run"] == "3"
    assert ax["longest_zero_run_from"] == WEEKS[9] and "数えない週" in ax["excluded_weeks_rule"]


# ── 既定の動き・再現（UP-V10） ───────────────────────────────────────────────
def test_default_call_writes_no_udp_and_the_same_demand_csv(tmp_path):
    m1 = make_model(str(tmp_path / "m1"), cap=2)
    m2 = make_model(str(tmp_path / "m2"), cap=2)
    a = make_alloc(str(tmp_path / "allocation_qty_t.csv"), _short_alloc())
    r1 = run_quantity_allocation(m1, a, out_dir=str(tmp_path / "p1"))
    r2 = run_quantity_allocation(m2, a, out_dir=str(tmp_path / "p2"), udp_out=str(tmp_path / "udp"))
    assert "udp_dir" not in r1
    assert r1["state"]["week_rule"] == "proportional_early_tie"
    g = "demand_forecast_Q01.csv"
    assert open(os.path.join(m1, g), "rb").read() == open(os.path.join(m2, g), "rb").read()
    assert r1["state"]["quantities"] == r2["state"]["quantities"]


def test_plan_json_and_rerun_gives_the_same_result(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    udp = str(tmp_path / "udp")
    r = _ps(tmp_path, m, week_rule="proportional_even", udp_out=udp)
    d = r["udp_dir"]
    first = {f: open(os.path.join(d, f), "rb").read() for f in sorted(os.listdir(d))}
    assert sorted(first) == sorted(["udp_demand_ledger.csv", "udp_selection_ledger.csv", "udp_capacity_check.csv",
                                    "udp_result_by_request.csv", "udp_supply_runs.csv", "udp_plan.json"])
    r2 = _ps(tmp_path, m, week_rule="proportional_even", udp_out=udp)
    assert r2["state"]["allocation_id"] == "Q02"
    second = {f: open(os.path.join(d, f), "rb").read() for f in sorted(os.listdir(d))}
    assert first == second
    p = json.loads(first["udp_plan.json"].decode("utf-8"))
    assert (p["calc_status"], p["consistency_status"], p["target_status"], p["owner_status"]) == (
        "計算済み", "整合", "未判定", "未判断")
    assert "demand_forecast.csv" in p["input_hashes"] and "capacity_plan.csv" in p["input_hashes"]
    assert not any(k.startswith("demand_forecast_Q") for k in p["input_hashes"])
    assert any(k.startswith("quota:") for k in p["input_hashes"])
    assert p["mode"] == "mode1_fixed_quota" and p["week_rule"] == "proportional_even"


def test_changing_an_input_changes_its_hash(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    q = make_alloc(str(tmp_path / "q.csv"), _short_alloc())
    a = U.input_file_hashes(m, "demand_forecast.csv", q)
    with open(os.path.join(m, "capacity_plan.csv"), "a", encoding="utf-8") as f:
        f.write("\n")
    b = U.input_file_hashes(m, "demand_forecast.csv", q)
    assert a["capacity_plan.csv"] != b["capacity_plan.csv"] and a["demand_forecast.csv"] == b["demand_forecast.csv"]
