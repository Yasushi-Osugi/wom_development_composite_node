# -*- coding: utf-8 -*-
"""tools/compare_scenarios.py on small synthetic outputs
(RequestLetter_Cockpit_FirstComparison_Observe §3・S4, ..._PolicyAndCapacity §4)"""
import gzip
import json
import os

import pandas as pd
import pytest

from tools import compare_scenarios as C

WEEKS = ["2027-W01", "2027-W02", "2027-W03", "2027-W04"]
LEAF = "MK"
SKU = "P"
UNIT_REV, UNIT_COGS, UNIT_EXP = 100.0, 40.0, 10.0


def _write_gz(path, df):
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        df.to_csv(f, index=False)


def make_case(root, name, demand, sales, flow_override=None, v3_offset=0.0):
    """demand: {week: qty}; sales: {lot_seq_tuple (req_week, seq): ship_week} for consumer sales."""
    model = os.path.join(root, "model_" + name)
    run = os.path.join(root, "run_" + name)
    for d in (model, os.path.join(run, "vc"), os.path.join(run, "ppc"), os.path.join(run, "shelf"),
              os.path.join(run, "flow_check", "model_" + name)):
        os.makedirs(d, exist_ok=True)
    pd.DataFrame([{"sku_id": SKU, "region": LEAF, "week": w, "quantity": demand.get(w, 0)} for w in WEEKS]).to_csv(
        os.path.join(model, "demand_forecast.csv"), index=False)
    pd.DataFrame([{"entity_id": "E", "kind": "group", "consolidated": 1},
                  {"entity_id": "X", "kind": "external_channel", "consolidated": 0}]).to_csv(
        os.path.join(model, "vc_entity.csv"), index=False)
    pd.DataFrame([{"sku_id": SKU, "node_name": "F", "week": w, "max_supply": 3, "cap_soft": 2} for w in WEEKS]).to_csv(
        os.path.join(model, "capacity_plan.csv"), index=False)
    pd.DataFrame([{"node_name": "F", "product_name": SKU, "node_type": "mom", "yield_rate": ""},
                  {"node_name": LEAF, "product_name": SKU, "node_type": "leaf_out", "yield_rate": ""}]).to_csv(
        os.path.join(model, "sc_tree_master.csv"), index=False)
    ship, money = [], []
    lid = 0
    for (rw, seq), sw in sales.items():
        lot = f"{SKU}:{LEAF}:{rw}:{seq:05d}"
        wi = WEEKS.index(sw)
        ship.append({"lot_id": lot, "product": SKU, "node": LEAF, "kind": "consumer_sale", "edge": "",
                     "ship_week_index": wi, "ship_week": sw, "arrival_week": "", "lots": 1})
        ship.append({"lot_id": lot, "product": SKU, "node": "F", "kind": "handoff_to_sp", "edge": "",
                     "ship_week_index": wi, "ship_week": sw, "arrival_week": sw, "lots": 1})
        for kind, scope, basis, amt in (("revenue", "external", "all", UNIT_REV),
                                        ("cogs", "external", "group", UNIT_COGS),
                                        ("cogs", "external", "entity", 999.0),      # not group: ignored
                                        ("expense", "selling", "v1,entity,group", UNIT_EXP),
                                        ("observation_sale", "observation", "obs", 777.0)):
            lid += 1
            money.append({"line_id": lid, "week_index": wi, "week": sw, "product": SKU, "lot_id": lot,
                          "entity": "E" if kind != "observation_sale" else "X", "node": LEAF, "kind": kind,
                          "scope": scope, "basis": basis, "family": "sale", "amt_hq": amt, "valued": 1})
    _write_gz(os.path.join(run, "vc", "vc_shipments.csv.gz"), pd.DataFrame(ship))
    _write_gz(os.path.join(run, "vc", "vc_money_lines.csv.gz"), pd.DataFrame(money))
    m = pd.DataFrame(money)
    v3 = []
    for i, w in enumerate(WEEKS):
        n = int(((m["week_index"] == i) & (m["kind"] == "revenue")).sum()) if len(m) else 0
        v3.append({"group_key": "GROUP", "week_index": i, "week": w, "in_report": i >= 1,
                   "profit_r2_hq_wk": n * (UNIT_REV - UNIT_COGS - UNIT_EXP) + (v3_offset if i == 2 else 0.0)})
    pd.DataFrame(v3).to_csv(os.path.join(run, "vc", "vc_v3_weekly.csv"), index=False)
    pd.DataFrame([{"week_index": i, "week": w, "owner": "E", "location_kind": "node", "location": "F",
                   "product": SKU, "external": 0, "lots": 1, "group_hq": 40.0} for i, w in enumerate(WEEKS)]).to_csv(
        os.path.join(run, "vc", "vc_inventory_weekly.csv"), index=False)
    pd.DataFrame([{"product": "*", "channel": "*", "deliveries": len(sales), "fifo_age_max": 1,
                   "over_max_age": 0}]).to_csv(os.path.join(run, "shelf", "shelf_life_summary.csv"), index=False)
    json.dump({"total_revenue_base": 1.0, "gross_profit_base": 2.0},
              open(os.path.join(run, "ppc", "ppc_kpi_summary.json"), "w", encoding="utf-8"))
    dem = sum(demand.values())
    on = sum(1 for (rw, _), sw in sales.items() if rw == sw)
    late = sum(1 for (rw, _), sw in sales.items() if WEEKS.index(sw) > WEEKS.index(rw))
    early = sum(1 for (rw, _), sw in sales.items() if WEEKS.index(sw) < WEEKS.index(rw))
    fl = {"product": SKU, "leaf": LEAF, "demand": dem, "on_time": on, "early": early, "late": late,
          "backlog_end": dem - len(sales)}
    fl.update(flow_override or {})
    pd.DataFrame([fl, {"product": SKU, "leaf": "Σ（製品）", "demand": dem, "on_time": on, "early": early,
                       "late": late, "backlog_end": dem - len(sales)}]).to_csv(
        os.path.join(run, "flow_check", "model_" + name, "flow_check_market.csv"), index=False, encoding="utf-8-sig")
    return run, model


def _base(tmp_path, **kw):
    # base: demand 1 in W02, 2 in W03; ships W02 on time, one W03 lot late (W04), one unmet
    return make_case(str(tmp_path), "b", {"2027-W02": 1, "2027-W03": 2},
                     {("2027-W02", 1): "2027-W02", ("2027-W03", 1): "2027-W04"}, **kw)


def _alt(tmp_path, **kw):
    # alt: extra demand in W01, served on time; W03 both unmet
    return make_case(str(tmp_path), "a", {"2027-W01": 1, "2027-W02": 1, "2027-W03": 2},
                     {("2027-W01", 1): "2027-W01", ("2027-W02", 1): "2027-W02"}, **kw)


def test_supply_by_request_week_counts_by_lot_id(tmp_path):
    rb, mb = _base(tmp_path)
    run = C.load_run(rb, mb)
    s = C.supply_by_request_week(run).set_index("request_week")
    assert s.loc["2027-W02", ["demand", "on_time", "late", "backlog_end"]].tolist() == [1, 1, 0, 0]
    assert s.loc["2027-W03", ["demand", "on_time", "late", "backlog_end"]].tolist() == [2, 0, 1, 1]
    assert s.loc["2027-W01", "demand"] == 0
    C.check_against_flow(s.reset_index(), run, "b")   # matches


def test_flow_check_mismatch_stops(tmp_path):
    rb, mb = _base(tmp_path, flow_override={"backlog_end": 0})
    run = C.load_run(rb, mb)
    with pytest.raises(C.CompareError, match="Flow Check"):
        C.check_against_flow(C.supply_by_request_week(run), run, "b")


def test_money_sums_to_profit_r2_and_mismatch_stops(tmp_path):
    rb, mb = _base(tmp_path)
    run = C.load_run(rb, mb)
    m = C.money_by_week_sku(run, "b")
    w4 = m[m["week"] == "2027-W04"].iloc[0]
    assert (w4["external_revenue"], w4["external_cogs_group"], w4["expense"], w4["profit_r2"]) == (100, 40, 10, 50)
    t = C.money_totals(m, run, "b").set_index(["period", "product"])
    assert t.loc[("full", "*"), "profit_r2"] == 100.0
    assert t.loc[("report", "*"), "profit_r2"] == 100.0           # W01 has nothing; report starts W02
    assert t.loc[("full", "*"), "v3_profit_r2_hq"] == 100.0
    rb2, mb2 = make_case(str(tmp_path), "bad", {"2027-W03": 1}, {("2027-W03", 1): "2027-W03"}, v3_offset=5.0)
    with pytest.raises(C.CompareError, match="profit_r2_hq_wk"):
        C.money_by_week_sku(C.load_run(rb2, mb2), "bad")


def test_unknown_or_double_shipped_lot_stops(tmp_path):
    rb, mb = make_case(str(tmp_path), "x", {"2027-W02": 1}, {("2027-W02", 2): "2027-W02"})
    with pytest.raises(C.CompareError, match="需要"):
        C.supply_by_request_week(C.load_run(rb, mb))


def _fc_plan(path, base=("2028-W01", "2029-W52", ""), alt=("2027-W27", "2029-W52", ""), ccy="JPY"):
    pd.DataFrame([{"case": c, "cost_item": "TH_fee", "entity": "E_JP", "paid_start_week": v[0], "paid_end_week": v[1],
                   "weekly_amount": v[2], "currency": ccy, "note": ""} for c, v in (("base", base), ("alt", alt))]).to_csv(
        path, index=False)
    return path


def test_compare_end_to_end(tmp_path):
    rb, mb = _base(tmp_path)
    ra, ma = _alt(tmp_path)
    out = str(tmp_path / "out")
    plan = _fc_plan(str(tmp_path / "fc.csv"), base=("2027-W03", "2027-W04", ""), alt=("2027-W01", "2027-W04", ""))
    res = C.compare(rb, ra, mb, ma, out, fixed_cost_plan=plan, base_name="b", alt_name="a")
    for f in ("demand_diff.csv", "supply_by_request_week.csv", "supply_by_key.csv", "money_by_week_sku.csv",
              "money_totals.csv", "inventory_weekly.csv", "diff_weeks.csv", "representative_lots.csv",
              "boundary.csv", "fixed_cost_breakeven.csv", "factory_idle_weeks.csv", "comparison_summary.md"):
        assert os.path.exists(os.path.join(out, f)), f
    assert not os.path.exists(os.path.join(out, "supply_allocation_by_request_week.csv"))   # no udp: as before
    dd = res["demand_diff"].set_index("week")
    assert dd.loc["2027-W01", "diff"] == 1
    dw = res["diff_weeks"]
    first = dw[(dw["measure"] == "supply_by_request_week") & (dw["which"] == "first")].iloc[0]
    assert first["week"] == "2027-W01"
    assert any(lot == "P:MK:2027-W01:00001" for _r, lot in res["picks"])
    # profit: both sell 2 lots, all in the report period except alt's W01 sale
    t = res["totals"].set_index(["period", "product"])
    assert t.loc[("full", "*"), "profit_r2_diff"] == 0.0
    assert t.loc[("report", "*"), "profit_r2_diff"] == -50.0
    assert len(res["supply_check"]) == 2 and res["supply_check"]["flow_check_match"].all()
    fc = res["fixed_cost"].iloc[0]
    # report period W02..W04: base W03..W04 = 2, alt W01..W04 -> W02..W04 = 3; dP0 = -50 -> no positive boundary
    assert (fc["W_base"], fc["W_alt"], fc["delta_W"], fc["delta_P0"]) == (2, 3, 1, -50.0)
    assert fc["boundary"] == "正の境目なし（base が上）"


# ── 固定費（GPT-MC 業務定義 v0.1 §3・§4）────────────────────────────────
def test_paid_weeks_in_report():
    R = ("2027-W01", "2029-W52")
    assert C.paid_weeks_in_report("2027-W27", "2029-W52", *R) == 130
    assert C.paid_weeks_in_report("2028-W01", "2029-W52", *R) == 104
    assert C.paid_weeks_in_report("2030-W01", "2030-W10", *R) == 0          # outside the report period
    assert C.paid_weeks_in_report("2027-W27", "2030-W26", *R) == 130        # weeks after 2029-W52 count 0
    assert C.paid_weeks_in_report("2026-W40", "2027-W02", *R) == 2
    with pytest.raises(C.CompareError):
        C.paid_weeks_in_report("2029-W10", "2029-W01", *R)


def test_week_2027_w26_and_2030_w01_rows():
    """Definition §3: 2027-W26 is 0 for both cases (before either start); 2030-W01 adds 0."""
    R = ("2027-W01", "2029-W52")
    early = C.paid_weeks_in_report("2027-W27", "2029-W52", *R)
    assert C.paid_weeks_in_report("2027-W27", "2029-W52", "2027-W26", "2027-W26") == 0
    assert C.paid_weeks_in_report("2028-W01", "2029-W52", "2027-W26", "2027-W26") == 0
    assert C.paid_weeks_in_report("2027-W27", "2029-W52", "2027-W27", "2027-W27") == 1
    assert C.paid_weeks_in_report("2028-W01", "2029-W52", "2027-W27", "2027-W27") == 0
    assert C.paid_weeks_in_report("2027-W27", "2030-W01", *R) == early
    assert early - C.paid_weeks_in_report("2028-W01", "2029-W52", *R) == 26


def test_worked_example_boundary_and_amounts(tmp_path):
    R = ("2027-W01", "2029-W52")
    p0 = {"base": 100_000_000.0, "alt": 101_300_000.0}
    st = {"base": "評価済み", "alt": "評価済み"}
    r = C.fixed_cost_table(C.read_fixed_cost_plan(_fc_plan(str(tmp_path / "a.csv"))), p0, st, *R).iloc[0]
    assert (r["W_alt"], r["W_base"], r["delta_W"], r["delta_P0"]) == (130, 104, 26, 1_300_000.0)
    assert r["f_star_per_week"] == 50_000.0 and r["note"] == "週額が未設定：境目だけ"
    for amt, diff in ((40_000, 260_000.0), (50_000, 0.0), (60_000, -260_000.0)):
        p = _fc_plan(str(tmp_path / f"p{amt}.csv"), base=("2028-W01", "2029-W52", str(amt)),
                     alt=("2027-W27", "2029-W52", str(amt)))
        x = C.fixed_cost_table(C.read_fixed_cost_plan(p), p0, st, *R).iloc[0]
        assert x["cost_alt"] == amt * 130 and x["cost_base"] == amt * 104
        assert x["delta_P_after"] == diff


@pytest.mark.parametrize("dp0,dw,label,fstar", [
    (1_300_000.0, 26, "f* = ΔP0 ÷ ΔW", 50_000.0),
    (500.0, 0, "順位変化なし（発生週数が同じ）", None),
    (0.0, 0, "両案同額", None),
    (-100.0, 26, "正の境目なし（base が上）", None),
    (0.0, 26, "0円で同額", None),
    (-2600.0, -26, "f が境目を超えると alt が上", 100.0),
    (2600.0, -26, "正の境目なし（alt が上）", None),
    (None, 26, "未算出", None),
])
def test_six_cases(dp0, dw, label, fstar):
    lab, f = C.boundary_label(dp0, dw)
    assert label in lab and f == fstar


def test_undetermined_cases(tmp_path):
    R = ("2027-W01", "2029-W52")
    p0 = {"base": 0.0, "alt": 1_300_000.0}
    plan = C.read_fixed_cost_plan(_fc_plan(str(tmp_path / "a.csv")))
    x = C.fixed_cost_table(plan, p0, {"base": "評価済み", "alt": "一部未評価（未評価の明細 3）"}, *R).iloc[0]
    assert x["boundary"].startswith("未算出（連結利益未評価") and x["f_star_per_week"] == ""
    y = C.fixed_cost_table(C.read_fixed_cost_plan(_fc_plan(str(tmp_path / "b.csv"), ccy="THB")), p0,
                           {"base": "評価済み", "alt": "評価済み"}, *R).iloc[0]
    assert "共通の円建て週額の条件外" in y["boundary"]
    z = C.fixed_cost_table(None, p0, {"base": "評価済み", "alt": "評価済み"}, *R).iloc[0]
    assert z["boundary"].startswith("未算出（固定費の表なし")


def test_fixed_cost_plan_stops(tmp_path):
    p = str(tmp_path / "x.csv")
    pd.DataFrame([{"case": "late", "cost_item": "a", "entity": "E", "paid_start_week": "2028-W01",
                   "paid_end_week": "2029-W52", "weekly_amount": "", "currency": "JPY", "note": ""}]).to_csv(p, index=False)
    with pytest.raises(C.CompareError, match="case"):
        C.read_fixed_cost_plan(p)
    pd.DataFrame([{"case": "base", "cost_item": "a"}]).to_csv(p, index=False)
    with pytest.raises(C.CompareError, match="列が足りません"):
        C.read_fixed_cost_plan(p)


# ── 未配分と配分後の未充足 ─────────────────────────────────────────────
def _udp(path, rows):
    """rows: {week: (q1, q2, on_time, late, q5)} -> udp_selection_ledger.csv + udp_result_by_request.csv"""
    os.makedirs(path, exist_ok=True)
    led, res = [], []
    for w in WEEKS:
        q1, q2, on, late, q5 = rows.get(w, (0, 0, 0, 0, 0))
        ref = f"{SKU}|{LEAF}|{w}"
        led.append({"source_demand_ref": ref, "q1": q1, "q2": q2, "q3": q1 - q2})
        res.append({"source_demand_ref": ref, "q2": q2, "on_time": on, "early": 0, "late": late, "q5": q5})
    pd.DataFrame(led).to_csv(os.path.join(path, "udp_selection_ledger.csv"), index=False)
    pd.DataFrame(res).to_csv(os.path.join(path, "udp_result_by_request.csv"), index=False)
    return path


def test_allocation_split_matches_and_mismatch_stops(tmp_path):
    rb, mb = _base(tmp_path)          # money run demand (= allocated): W02 1, W03 2; W02 on time, W03 1 late + 1 unmet
    run = C.load_run(rb, mb)
    sup = C.supply_by_request_week(run)
    u = C.load_udp(_udp(str(tmp_path / "udp" / "case_rule"), {"2027-W02": (3, 1, 1, 0, 0), "2027-W03": (2, 2, 0, 1, 1)}))
    a = C.allocation_table(sup, u, "b").set_index("request_week")
    assert a.loc["2027-W02", ["q1_original", "q2_in_scope", "q3_unallocated", "on_time", "q5_backlog_end"]].tolist() == \
        [3, 1, 2, 1, 0]
    assert a.loc["2027-W03", ["q1_original", "q2_in_scope", "q3_unallocated", "late", "q5_backlog_end"]].tolist() == \
        [2, 2, 0, 1, 1]
    # the parent folder with a single sub-folder is accepted
    assert len(C.load_udp(str(tmp_path / "udp"))) == len(WEEKS)
    # no udp: q1 = q2 = demand, q3 = 0
    p = C.allocation_table(sup, None, "b").set_index("request_week")
    assert p.loc["2027-W03", ["q1_original", "q3_unallocated", "q5_backlog_end"]].tolist() == [2, 0, 1]
    bad = C.load_udp(_udp(str(tmp_path / "bad"), {"2027-W02": (3, 1, 1, 0, 0), "2027-W03": (2, 2, 1, 0, 1)}))
    with pytest.raises(C.CompareError, match="数量配分モードの結果と合いません"):
        C.allocation_table(sup, bad, "b")


def test_compare_with_udp_writes_split(tmp_path):
    rb, mb = _base(tmp_path)
    ra, ma = _alt(tmp_path)
    u = _udp(str(tmp_path / "udp_b"), {"2027-W02": (3, 1, 1, 0, 0), "2027-W03": (2, 2, 0, 1, 1)})
    out = str(tmp_path / "out")
    res = C.compare(rb, ra, mb, ma, out, base_udp=u)
    k = pd.read_csv(os.path.join(out, "supply_allocation_by_key.csv")).iloc[0]
    assert (k["q1_original_base"], k["q3_unallocated_base"], k["q1_original_alt"], k["q3_unallocated_alt"]) == (5, 2, 4, 0)
    assert res["fixed_cost"].iloc[0]["boundary"].startswith("未算出（固定費の表なし")


def test_udp_identity_violation_stops(tmp_path):
    d = _udp(str(tmp_path / "u"), {"2027-W02": (3, 1, 1, 0, 0)})
    r = pd.read_csv(os.path.join(d, "udp_result_by_request.csv"))
    r.loc[1, "q5"] = 1          # q2 = 1 but on_time + q5 = 2
    r.to_csv(os.path.join(d, "udp_result_by_request.csv"), index=False)
    with pytest.raises(C.CompareError, match="②＝④＋⑤"):
        C.load_udp(d)
