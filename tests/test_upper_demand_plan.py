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


KNOWLEDGE = [{"id": "WOM-X-001", "version": "v9.9", "applicability": "試験"}]
DECISIONS = ["requests/some_letter.md §5", "requests/other_letter.md §1"]
RECORD_KEYS = ("knowledge_used", "owner_decisions", "target_commit", "code_dirty")


def _plan(d):
    return json.load(open(os.path.join(d, "udp_plan.json"), encoding="utf-8"))


def test_unspecified_knowledge_and_decisions_say_so(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    p = _plan(_ps(tmp_path, m, week_rule="proportional_even", udp_out=str(tmp_path / "udp"))["udp_dir"])
    assert p["knowledge_used"] == U.NOT_SPECIFIED == "未指定"
    assert p["owner_decisions"] == "未指定"


def test_specified_knowledge_and_decisions_are_written_as_given(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    r = _ps(tmp_path, m, week_rule="proportional_even", udp_out=str(tmp_path / "udp"),
            knowledge_used=KNOWLEDGE, owner_decisions=DECISIONS)
    p = _plan(r["udp_dir"])
    assert p["knowledge_used"] == KNOWLEDGE and p["owner_decisions"] == DECISIONS


def test_specifying_them_changes_nothing_else(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    udp = str(tmp_path / "udp")
    d = _ps(tmp_path, m, week_rule="proportional_even", udp_out=udp)["udp_dir"]
    files = sorted(os.listdir(d))
    first = {f: open(os.path.join(d, f), "rb").read() for f in files}
    p1 = _plan(d)
    _ps(tmp_path, m, week_rule="proportional_even", udp_out=udp, knowledge_used=KNOWLEDGE, owner_decisions=DECISIONS)
    p2 = _plan(d)
    for f in files:
        if f != "udp_plan.json":
            assert open(os.path.join(d, f), "rb").read() == first[f]
    assert {k: v for k, v in p1.items() if k not in RECORD_KEYS} == {k: v for k, v in p2.items() if k not in RECORD_KEYS}


def test_cli_passes_the_knowledge_file_and_decision_refs(tmp_path):
    from tools.run_quantity_allocation import main
    m = make_model(str(tmp_path / "m"), cap=2)
    q = make_alloc(str(tmp_path / "q.csv"), _short_alloc())
    kf = tmp_path / "k.json"
    kf.write_text(json.dumps(KNOWLEDGE, ensure_ascii=False), encoding="utf-8")
    argv = ["--model-dir", m, "--allocation-file", q, "--out-dir", str(tmp_path / "ps"), "--week-rule",
            "proportional_even", "--udp-out", str(tmp_path / "udp"), "--knowledge-file", str(kf)]
    for x in DECISIONS:
        argv += ["--decision-ref", x]
    assert main(argv) == 0
    p = _plan(os.path.join(tmp_path / "udp", "m_proportional_even"))
    assert p["knowledge_used"] == KNOWLEDGE and p["owner_decisions"] == DECISIONS


@pytest.mark.parametrize("body", [{"id": "x"}, [{"id": "x", "version": "1"}], ["x"]])
def test_a_malformed_knowledge_file_is_refused(tmp_path, body):
    from tools.run_quantity_allocation import read_knowledge_file
    kf = tmp_path / "k.json"
    kf.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ValueError):
        read_knowledge_file(str(kf))


def test_changing_an_input_changes_its_hash(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    q = make_alloc(str(tmp_path / "q.csv"), _short_alloc())
    a = U.input_file_hashes(m, "demand_forecast.csv", q)
    with open(os.path.join(m, "capacity_plan.csv"), "a", encoding="utf-8") as f:
        f.write("\n")
    b = U.input_file_hashes(m, "demand_forecast.csv", q)
    assert a["capacity_plan.csv"] != b["capacity_plan.csv"] and a["demand_forecast.csv"] == b["demand_forecast.csv"]


# ── 能力に合わせて減らす週を選ぶ規則（RequestLetter_…_CapacityAwareWeekRule_U4 §3.3） ──────
HAND_WEEKS = [f"2027-W{i:02d}" for i in range(1, 9)]
TREE_COLS = ["node_name", "parent_node", "product_name", "node_type", "side", "lt_wks", "region", "ss_days"]


def _hand_model(tmp_path, cap, demand):
    """工場 1・代理店 2・直営店 1。LT 2 週、直営店は ss_days 14 日で 2 週早い。"""
    m = str(tmp_path / "hand")
    os.makedirs(m, exist_ok=True)
    tree = [["SP", "", "P", "supply_point", "outbound", 0, "", 0], ["DC", "SP", "P", "dad", "outbound", 1, "", 0],
            ["Store", "DC", "P", "leaf_out", "outbound", 1, "Store", 14], ["D1", "DC", "P", "leaf_out", "outbound", 1, "D1", 0],
            ["D2", "DC", "P", "leaf_out", "outbound", 1, "D2", 0], ["F", "", "P", "mom", "inbound", "", "", 0]]
    _w(os.path.join(m, "sc_tree_master.csv"), TREE_COLS, tree)
    _w(os.path.join(m, "capacity_plan.csv"), ["sku_id", "week", "max_supply"], [["P", w, cap] for w in HAND_WEEKS])
    _w(os.path.join(m, "demand_forecast.csv"), ["sku_id", "region", "week", "quantity"],
       [["P", r, w, q] for r, qs in demand.items() for w, q in zip(HAND_WEEKS, qs)])
    return m


HAND_DEMAND = {"Store": [0, 0, 0, 0, 1, 1, 1, 1], "D1": [0, 0, 4, 4, 4, 4, 6, 6], "D2": [0, 0, 2, 2, 2, 2, 2, 2]}


def _hand_select(tmp_path, cap, quota, **kw):
    m = _hand_model(tmp_path, cap, HAND_DEMAND)
    q = make_alloc(str(tmp_path / "q.csv"), {("P", r): v for r, v in quota.items()})
    sel = U.select_mode1_capacity(U.build_demand_ledger(m), q, m, **kw)
    return m, sel, {r: [x["q2"] for x in sel if x["region"] == r] for r in HAND_DEMAND}


def test_trim_by_hand(tmp_path):
    # need(p) = W03..W08 の代理店 p=0..5 に直営店 W05..W08 p=0..3：7 7 7 7 8 8、能力 5
    # p5 の超過 3 を残り 4:2 で分ける -> D1 2, D2 1。p4 も 3 -> D1 2, D2 1。ここで使い切る
    m, sel, q2 = _hand_select(tmp_path, 5, {"Store": 4, "D1": 24, "D2": 10})
    assert q2["Store"] == HAND_DEMAND["Store"]
    assert q2["D1"] == [0, 0, 4, 4, 4, 4, 4, 4]
    assert q2["D2"] == [0, 0, 2, 2, 2, 2, 1, 1]
    rows = [r for r in U.time_phased_check(m, sel, True, True)]
    assert [r["need_good_lots"] for r in rows][4:6] == [5, 5] and [r["cap_good_lots"] for r in rows][4:6] == [5, 5]
    assert rows[0]["cap_good_lots"] == 0
    assert all(x["reason_code"] == "quota_cut_trim_to_capacity" for x in sel if x["q3"])
    assert all(x["week_rule"] == "trim_to_capacity_latest" for x in sel)
    assert sel[0]["policy_ref"] == "capacity_check:first_week_unusable=1,ss_lead=1,rest_lots=0"


def test_trim_tie_goes_by_region_name(tmp_path):
    # 減らす量 1:1、p5 の超過を 1 にする（能力 7）。端数が同じなら region の名前の順で D1
    _, _, q2 = _hand_select(tmp_path, 7, {"Store": 4, "D1": 27, "D2": 11}, first_week_unusable=False)
    assert q2["D1"][7] == 5 and q2["D1"][6] == 6
    assert q2["D2"][6] == 1 and q2["D2"][7] == 2


def test_trim_rest_goes_even_and_is_recorded(tmp_path):
    # 能力 7：超える分は p5・p4 の 1 ずつ。減らす量 3・1。比率 .75／.67 で 2 回とも D1、残り 1・1 を均等
    m, sel, q2 = _hand_select(tmp_path, 7, {"Store": 4, "D1": 25, "D2": 11}, first_week_unusable=False)
    assert q2["D1"] == [0, 0, 4, 4, 4, 4, 4, 5]
    assert q2["D2"] == [0, 0, 2, 2, 1, 2, 2, 2]
    assert next(x for x in sel if x["region"] == "D1")["policy_ref"].endswith("rest_lots=1")
    d = U.capacity_rule_detail(m, sel, False, True)
    assert d["rest_lots_total"] == 2 and d["rest_lots_by_key"]["P|D2"] == 1


def test_trim_keys_without_a_cut_stay_whole_and_conserve(tmp_path):
    _, sel, _ = _hand_select(tmp_path, 3, {"Store": 4, "D1": 20, "D2": 8})
    tot = {}
    for x in sel:
        assert x["q1"] == x["q2"] + x["q3"] and 0 <= x["q2"] <= x["q1"]
        tot[x["region"]] = tot.get(x["region"], 0) + x["q3"]
    assert tot == {"Store": 0, "D1": 8, "D2": 4}


# ── 最低供給量（RequestLetter_…_MinimumSupply §3.5） ─────────────────────────────────
POLICY_COLS = U.POLICY_COLUMNS


def _policy(tmp_path, rows, name="pol.csv", pid="MS", ver="1"):
    """rows: (sku, region, ratio[, rounding[, kind]])"""
    p = str(tmp_path / name)
    full = [(r + ("ceil", "required"))[:5] if len(r) == 3 else (r + ("required",))[:5] if len(r) == 4 else r for r in rows]
    _w(p, POLICY_COLS, [[pid, ver, s, reg, ra, ro, k, "試験"] for s, reg, ra, ro, k in full])
    return p


def test_min_supply_lots_rounding():
    ceil_7 = {"ratio": U.Fraction("0.7"), "rounding": "ceil", "kind": "required"}
    assert [U.min_supply_lots(q, ceil_7) for q in (0, 1, 2, 3, 4, 5, 6, 10)] == [0, 1, 2, 3, 3, 4, 5, 7]
    half = {"ratio": U.Fraction("0.5"), "rounding": "ceil", "kind": "required"}
    assert [U.min_supply_lots(q, half) for q in (4, 5, 6)] == [2, 3, 3]
    assert U.min_supply_lots(5, {"ratio": U.Fraction("0.5"), "rounding": "floor", "kind": "required"}) == 2
    assert U.min_supply_lots(5, {"ratio": U.Fraction("0.5"), "rounding": "ceil", "kind": "target"}) == 0
    assert U.min_supply_lots(5, None) == 0


def test_no_policy_is_the_same_rule(tmp_path):
    m = _c3a_model(tmp_path)
    led = U.build_demand_ledger(m)
    assert U.select_mode1_capacity(led, P2A2, m) == U.select_mode1_capacity(led, P2A2, m, policy_file=None)


def test_a_minimum_that_does_not_bind_changes_nothing(tmp_path):
    m, sel, q2 = _hand_select(tmp_path, 5, {"Store": 4, "D1": 24, "D2": 10})
    pol = _policy(tmp_path, [("P", "D1", "0.25"), ("P", "D2", "0.25")])
    q = str(tmp_path / "q.csv")
    with_p = U.select_mode1_capacity(U.build_demand_ledger(m), q, m, policy_file=pol)
    assert [(x["source_demand_ref"], x["q2"], x["q3"]) for x in with_p] == [(x["source_demand_ref"], x["q2"], x["q3"]) for x in sel]
    assert with_p[0]["policy_ref"] == "capacity_check:first_week_unusable=1,ss_lead=1,policy=MS:1,rest_lots=0"


def test_tail_without_excess_is_not_cut_first(tmp_path):
    # 能力 5：W07・W08 の工場の週 p5・p4 だけ超える前に、末尾の超過が無いように D1 の末尾を小さくする
    dem = {"Store": [0] * 8, "D1": [0, 0, 5, 5, 5, 5, 1, 1], "D2": [0, 0, 2, 2, 2, 2, 1, 1]}
    m = _hand_model(tmp_path, 5, dem)
    q = make_alloc(str(tmp_path / "q.csv"), {("P", "Store"): 0, ("P", "D1"): 19, ("P", "D2"): 7})
    pol = _policy(tmp_path, [("P", "D1", "0.5"), ("P", "D2", "0.5")])
    sel = U.select_mode1_capacity(U.build_demand_ledger(m), q, m, policy_file=pol)
    v = {r: [x["q2"] for x in sel if x["region"] == r] for r in dem}
    assert v["D1"][6:] == [1, 1] and v["D2"][6:] == [1, 1]
    assert v["D1"][5] < 5 or v["D2"][5] < 2


def test_cut_stops_at_the_minimum_and_spreads_forward_by_hand(tmp_path):
    # 需要 D1 6（最低 3）、D2 2（最低 1）、能力 4（first_week_unusable なし）。全週 e=4。
    # W08：余地 3+1＝4 で 4 削れる。D1 は 8 週で週 3 まで、D2 は週 1 まで。
    # 比率を 0.9 にすると D1 最低 6・余地 0、D2 最低 2・余地 0 で全く削れず衝突になるので 0.7 で見る：
    # D1 最低 5 余地 1、D2 最低 2 余地 0。外す量 D1 3：W08・W07・W06 で 1 ずつ、繰越で前へ
    dem = {"Store": [0] * 8, "D1": [6] * 8, "D2": [2] * 8}
    m = _hand_model(tmp_path, 4, dem)
    q = make_alloc(str(tmp_path / "q.csv"), {("P", "Store"): 0, ("P", "D1"): 45, ("P", "D2"): 16})
    pol = _policy(tmp_path, [("P", "D1", "0.7"), ("P", "D2", "0.7")])
    sel = U.select_mode1_capacity(U.build_demand_ledger(m), q, m, policy_file=pol, first_week_unusable=False)
    v = [x["q2"] for x in sel if x["region"] == "D1"]
    assert v == [6, 6, 6, 6, 6, 5, 5, 5]
    assert all(x["q2"] >= U.min_supply_lots(x["q1"], {"ratio": U.Fraction("0.7"), "rounding": "ceil", "kind": "required"})
               for x in sel if x["region"] != "Store")


def test_carry_reaches_a_week_without_excess_by_hand(tmp_path):
    # W05〜W08 は超過 3（需要 8、能力 5）で、最低供給量 6 のため週 2 しか削れない。繰越が 1 ずつ増える。
    # W03・W04 は超過なしだが、繰越があるので最低供給量 3 まで削られる。外す量 10＝2×4＋1×2
    dem = {"Store": [0] * 8, "D1": [0, 0, 4, 4, 8, 8, 8, 8], "D2": [0] * 8}
    m = _hand_model(tmp_path, 5, dem)
    q = make_alloc(str(tmp_path / "q.csv"), {("P", "Store"): 0, ("P", "D1"): 30, ("P", "D2"): 0})
    pol = _policy(tmp_path, [("P", "D1", "0.75")])             # 8 → 6、4 → 3
    sel = U.select_mode1_capacity(U.build_demand_ledger(m), q, m, policy_file=pol, first_week_unusable=False)
    assert [x["q2"] for x in sel if x["region"] == "D1"] == [0, 0, 3, 3, 6, 6, 6, 6]


def test_conflict_detected_and_not_passed_to_the_engine(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    a = make_alloc(str(tmp_path / "q.csv"), _short_alloc())
    pol = _policy(tmp_path, [("A", "X", "1"), ("B", "Y", "0.5")])
    r = run_quantity_allocation(m, a, out_dir=str(tmp_path / "ps"), week_rule="trim_to_capacity_latest",
                                udp_out=str(tmp_path / "udp"), policy_file=pol)
    assert r["status"] == "conflict"
    assert [(c["sku_id"], c["region"], c["quota_cut_lots"], c["placeable_cut_lots"], c["unplaceable_lots"]) for c in r["conflicts"]] == [("A", "X", 6, 0, 6)]
    c = r["conflicts"][0]
    assert "能力を足すだけでは解消しない" in c["reason"] and "最低供給率を下げる" in c["alternatives"]
    assert not any(f.startswith("demand_forecast_Q") for f in os.listdir(m))
    assert not os.path.exists(tmp_path / "ps" / "m" / "Q01.json")
    p = _plan(r["udp_dir"])
    assert (p["calc_status"], p["consistency_status"], p["target_status"]) == ("計画の前に止めた（衝突）", "整合", "未達（衝突）")
    assert p["totals"]["q4_delivered"] == p["totals"]["q5_backlog_end"] == p["totals"]["evaluation"] == "未実行"
    ref = list(csv.DictReader(open(os.path.join(r["udp_dir"], "udp_selection_reference.csv"), encoding="utf-8")))
    assert ref and not any(x["source_demand_ref"].startswith("A|X|") for x in ref)
    assert sorted(os.listdir(r["udp_dir"])) == ["udp_conflicts.csv", "udp_demand_ledger.csv", "udp_plan.json", "udp_selection_reference.csv"]


def test_conflict_exit_code_differs_from_the_quantity_error(tmp_path):
    from tools.run_quantity_allocation import EXIT_CONFLICT, main
    m = make_model(str(tmp_path / "m"), cap=2)
    a = make_alloc(str(tmp_path / "q.csv"), _short_alloc())
    pol = _policy(tmp_path, [("A", "X", "1")])
    rc = main(["--model-dir", m, "--allocation-file", a, "--out-dir", str(tmp_path / "ps"), "--week-rule",
               "trim_to_capacity_latest", "--udp-out", str(tmp_path / "udp"), "--policy-file", pol])
    assert rc == EXIT_CONFLICT and rc not in (0, 1)


def test_select_refuses_a_conflict_unless_reference(tmp_path):
    m, _, _ = _hand_select(tmp_path, 5, {"Store": 4, "D1": 24, "D2": 10})
    pol = _policy(tmp_path, [("P", "D1", "1")])
    q = str(tmp_path / "q.csv")
    with pytest.raises(QuantityAllocationError):
        U.select_mode1_capacity(U.build_demand_ledger(m), q, m, policy_file=pol)
    ref = U.select_mode1_capacity(U.build_demand_ledger(m), q, m, policy_file=pol, reference_only=True)
    assert ref and {x["region"] for x in ref} == {"Store", "D2"}


def test_two_stage_check_selected_but_not_delivered():
    sel = [{"source_demand_ref": "A|X|W1", "sku_id": "A", "region": "X", "request_week": "2027-W01", "q1": 4, "q2": 2},
           {"source_demand_ref": "A|X|W2", "sku_id": "A", "region": "X", "request_week": "2027-W02", "q1": 4, "q2": 2},
           {"source_demand_ref": "A|X|W3", "sku_id": "A", "region": "X", "request_week": "2027-W03", "q1": 0, "q2": 0},
           {"source_demand_ref": "A|Y|W1", "sku_id": "A", "region": "Y", "request_week": "2027-W01", "q1": 4, "q2": 0}]
    res = [{"source_demand_ref": r["source_demand_ref"], "on_time": 2} for r in sel]
    res[1]["on_time"] = 1
    pol = {"keys": {("A", "X"): {"ratio": U.Fraction("0.5"), "rounding": "ceil", "kind": "required"}}}
    rows, summ = U.min_supply_check(sel, res, pol)
    assert [(r["min_supply_lots"], r["plan_ok"], r["delivered_ok"]) for r in rows] == [(2, True, True), (2, True, False)]
    assert summ == {"A|X": {"weeks": 2, "plan_below_weeks": [], "delivered_below_weeks": ["2027-W02"]}}


def test_delivered_shortfall_sets_the_status_and_keeps_the_results(tmp_path):
    from tools.run_quantity_allocation import EXIT_DELIVERED_SHORT, main
    import tools.run_quantity_allocation as RQ
    m = make_model(str(tmp_path / "m"), cap=2)
    a = make_alloc(str(tmp_path / "q.csv"), _short_alloc())
    pol = _policy(tmp_path, [("A", "X", "0.5")])
    r = run_quantity_allocation(m, a, out_dir=str(tmp_path / "ps"), week_rule="trim_to_capacity_latest",
                                udp_out=str(tmp_path / "udp"), policy_file=pol)
    assert r["status"] == "ok"
    p = _plan(r["udp_dir"])
    assert p["policy_id"] == "MS" and p["policy_version"] == "1" and len(p["policy_hash"]) == 64
    assert any(k.startswith("policy:") for k in p["input_hashes"])
    rows = list(csv.DictReader(open(os.path.join(r["udp_dir"], "udp_min_supply_check.csv"), encoding="utf-8")))
    assert rows and p["consistency_status"] == "整合"
    short = any(x["delivered_ok"] == "False" for x in rows)
    assert p["target_status"] == ("未達（実納品不足）" if short else "達成")
    assert EXIT_DELIVERED_SHORT not in (0, 1, RQ.EXIT_CONFLICT)


def test_write_plan_marks_the_shortfall(tmp_path, monkeypatch):
    m = make_model(str(tmp_path / "m"), cap=2)
    a = make_alloc(str(tmp_path / "q.csv"), _short_alloc())
    pol = _policy(tmp_path, [("A", "X", "0.5")])
    orig = U.min_supply_check

    def worse(selection, by_request, policy):
        rows, summ = orig(selection, by_request, policy)
        rows[0]["delivered_ok"] = False
        summ["A|X"]["delivered_below_weeks"].append("2027-W01")
        return rows, summ
    monkeypatch.setattr(U, "min_supply_check", worse)
    r = run_quantity_allocation(m, a, out_dir=str(tmp_path / "ps"), week_rule="trim_to_capacity_latest",
                                udp_out=str(tmp_path / "udp"), policy_file=pol)
    p = _plan(r["udp_dir"])
    assert p["target_status"] == "未達（実納品不足）" and p["adoption_status"].startswith("止めた")
    assert p["calc_status"] == "計算済み" and p["consistency_status"] == "整合"
    assert r["target_status"] == "未達（実納品不足）"


@pytest.mark.parametrize("rows, text", [
    ([("X", "D1", "0.5")], "not in the model"),
    ([("P", "D1", "0.5"), ("P", "D1", "0.7")], "twice"),
    ([("P", "D1", "1.5")], "ratio"),
    ([("P", "D1", "-0.1")], "ratio"),
    ([("P", "D1", "")], "min_supply_ratio"),
    ([("P", "D1", "abc")], "min_supply_ratio"),
    ([("P", "D1", "0.5", "round")], "rounding"),
    ([("P", "D1", "0.5", "ceil", "maybe")], "kind"),
])
def test_bad_policy_is_an_input_error(tmp_path, rows, text):
    m = _hand_model(tmp_path, 5, HAND_DEMAND)
    pol = _policy(tmp_path, rows)
    with pytest.raises(QuantityAllocationError, match=text):
        U.read_policy(pol, U.build_demand_ledger(m))


def test_policy_needs_the_capacity_rule(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    a = make_alloc(str(tmp_path / "q.csv"), _short_alloc())
    pol = _policy(tmp_path, [("A", "X", "0.5")])
    with pytest.raises(ValueError):
        run_quantity_allocation(m, a, out_dir=str(tmp_path / "ps"), week_rule="proportional_even",
                                udp_out=str(tmp_path / "udp"), policy_file=pol)


def test_unlisted_key_has_no_minimum(tmp_path):
    m = _hand_model(tmp_path, 5, HAND_DEMAND)
    led = U.build_demand_ledger(m)
    pol = U.read_policy(_policy(tmp_path, [("P", "D1", "0.5")]), led)
    assert ("P", "D2") not in pol["keys"] and pol["keys"][("P", "D1")]["ratio"] == U.Fraction(1, 2)


def test_cosmetics_ms50_keeps_every_minimum_and_ms70_conflicts_on_cream_th(tmp_path):
    m = _c3a_model(tmp_path)
    led = U.build_demand_ledger(m)
    rows = [(s, r, "0.5") for s in ("COS_Serum", "COS_Cream") for r in ("SG_Distributor", "TH_Distributor")]
    p50 = _policy(tmp_path, rows, "p50.csv")
    sel = U.select_mode1_capacity(led, P2A2, m, policy_file=p50)
    pol = U.read_policy(p50, led)
    assert all(x["q2"] >= U.min_supply_lots(x["q1"], pol["keys"].get((x["sku_id"], x["region"]))) for x in sel)
    assert sum(x["q2"] for x in sel) == 3864
    p70 = U.read_policy(_policy(tmp_path, [(a, b, "0.7") for a, b, _ in rows], "p70.csv"), led)
    c = U.min_supply_conflicts(led, P2A2, p70)
    assert [(x["sku_id"], x["region"], x["quota_cut_lots"], x["placeable_cut_lots"], x["unplaceable_lots"]) for x in c] == [
        ("COS_Cream", "TH_Distributor", 25, 0, 25)]


def test_trim_row_order_does_not_matter(tmp_path):
    m = _hand_model(tmp_path, 5, HAND_DEMAND)
    q = make_alloc(str(tmp_path / "q.csv"), {("P", "Store"): 4, ("P", "D1"): 24, ("P", "D2"): 10})
    a = U.select_mode1_capacity(U.build_demand_ledger(m), q, m)
    p = os.path.join(m, "demand_forecast.csv")
    src = list(csv.reader(open(p, encoding="utf-8")))
    body = src[1:]
    random.Random(5).shuffle(body)
    _w(p, src[0], body)
    assert U.select_mode1_capacity(U.build_demand_ledger(m), q, m) == a


def _c3a_model(tmp_path):
    """化粧品の C3a の能力の写し（資料 docs/scenarios/cosmetics.md の作り方）。"""
    m = str(tmp_path / "c3a")
    shutil.copytree(COSMETICS, m, ignore=shutil.ignore_patterns("README.md"))
    p = os.path.join(m, "capacity_plan.csv")
    rows = list(csv.DictReader(open(p, encoding="utf-8", newline="")))
    for r in rows:
        r["max_supply"], r["cap_soft"] = {"COS_Serum": (17, 14), "COS_Cream": (13, 11)}[r["sku_id"]]
    _w(p, list(rows[0]), [list(r.values()) for r in rows])
    return m


def test_trim_on_the_cosmetics_demand(tmp_path):
    m = _c3a_model(tmp_path)
    sel = U.select_mode1_capacity(U.build_demand_ledger(m), P2A2, m)
    quota = {(r["sku_id"], r["region"]): int(r["alloc_lots"]) for r in csv.DictReader(open(P2A2, encoding="utf-8-sig"))}
    tot = {}
    for x in sel:
        assert x["q1"] == x["q2"] + x["q3"] and 0 <= x["q2"] <= x["q1"]
        tot[(x["sku_id"], x["region"])] = tot.get((x["sku_id"], x["region"]), 0) + x["q2"]
    assert {k: v for k, v in tot.items() if v} == quota
    assert all(x["q3"] == 0 for x in sel if x["region"] in ("SG_Store", "SG_EC"))
    assert U.capacity_rule_detail(m, sel)["rest_lots_total"] == 0
    assert all(x["q2"] > 0 for x in sel if x["q1"] > 0)            # 代理店への供給を止めない


# ── 診断の条件の選択肢 ────────────────────────────────────────────────────────
APPX = os.path.join(REPO, "docs", "development", "WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix", "udp")


@pytest.mark.parametrize("case,serum,cream,plain_s,plain_c", [("U4_A0", 4, 4, 0, 0), ("U4_A0e", 2, 2, 0, 0),
                                                              ("U4_A1", 64, 55, 43, 39)])
def test_conditions_reproduce_the_u4_results(tmp_path, case, serum, cream, plain_s, plain_c):
    m = _c3a_model(tmp_path)
    sel = []
    for r in csv.DictReader(open(os.path.join(APPX, case, "udp_selection_ledger.csv"), encoding="utf-8")):
        sku, reg, wk = r["source_demand_ref"].split("|")
        sel.append({"sku_id": sku, "region": reg, "request_week": wk, "q2": int(r["q2"])})
    ref = lambda *f: {r["sku_id"]: r["ontime_short_ref"] for r in U.time_phased_check(m, sel, *f)}
    assert ref(True, True) == {"COS_Serum": serum, "COS_Cream": cream}
    assert ref() == {"COS_Serum": plain_s, "COS_Cream": plain_c}


def test_conditions_are_written_and_the_default_text_is_unchanged():
    assert U.APPROX_CONDITIONS == ("近似の条件：単一の資源（SKU ごとの工場）、固定の LT、作り置きに上限なし、遅れての生産をしない、"
                                   "店頭在庫（ss_days）・原料の区間（最初の週）・休業は入れない")
    t = U.approx_conditions(True, True)
    assert t.endswith("休業は入れない。入れた：店頭在庫（ss_days）・原料の区間（最初の週）")
    assert "入れた：原料の区間（最初の週）" in U.approx_conditions(True, False)


def test_select_mode1_refuses_the_capacity_rule(tmp_path):
    q = make_alloc(str(tmp_path / "q.csv"), {("A", "X"): 1})
    with pytest.raises(ValueError, match="select_mode1_capacity"):
        U.select_mode1(_ledger_of(tmp_path, [1, 1]), q, "trim_to_capacity_latest")


def test_trim_through_the_tool_records_its_conditions(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    r = _ps(tmp_path, m, week_rule="trim_to_capacity_latest", udp_out=str(tmp_path / "udp"))
    assert r["status"] == "ok" and r["state"]["week_rule"] == "trim_to_capacity_latest"
    d = r["udp_dir"]
    p = json.load(open(os.path.join(d, "udp_plan.json"), encoding="utf-8"))
    w = p["week_rule_detail"]
    assert w["first_week_unusable"] is True and w["ss_lead"] is True and "rest_lots_total" in w
    cc = list(csv.DictReader(open(os.path.join(d, "udp_capacity_check.csv"), encoding="utf-8")))
    assert all("入れた：" in x["approx_conditions"] for x in cc)
    rows = list(csv.DictReader(open(os.path.join(d, "udp_result_by_request.csv"), encoding="utf-8")))
    assert all(int(x["q2"]) == int(x["on_time"]) + int(x["early"]) + int(x["late"]) + int(x["q5"]) for x in rows)


def test_other_rules_have_no_rule_detail_in_the_plan_json(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2)
    r = _ps(tmp_path, m, week_rule="proportional_even", udp_out=str(tmp_path / "udp"))
    assert "week_rule_detail" not in json.load(open(os.path.join(r["udp_dir"], "udp_plan.json"), encoding="utf-8"))