# -*- coding: utf-8 -*-
"""tools/compare_scenarios.py on small synthetic outputs (RequestLetter_Cockpit_FirstComparison_Observe §3・S4)"""
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


def test_compare_end_to_end(tmp_path):
    rb, mb = _base(tmp_path)
    ra, ma = _alt(tmp_path)
    out = str(tmp_path / "out")
    res = C.compare(rb, ra, mb, ma, out, extra_fixed_cost_weeks=2, base_name="b", alt_name="a")
    for f in ("demand_diff.csv", "supply_by_request_week.csv", "supply_by_key.csv", "money_by_week_sku.csv",
              "money_totals.csv", "inventory_weekly.csv", "diff_weeks.csv", "representative_lots.csv",
              "boundary.csv", "fixed_cost_breakeven.csv", "factory_idle_weeks.csv", "comparison_summary.md"):
        assert os.path.exists(os.path.join(out, f)), f
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


def test_fixed_cost_breakeven():
    t = pd.DataFrame([{"period": "report", "product": "X", "profit_r2_diff": 260.0}])
    r = C.fixed_cost_breakeven(t, 26, "X").iloc[0]
    assert r["breakeven_fixed_cost_per_week_hq"] == 10.0 and r["status"] == "provisional"
    t = pd.DataFrame([{"period": "report", "product": "X", "profit_r2_diff": 0.0}])
    assert "上回らない" in C.fixed_cost_breakeven(t, 26, "X").iloc[0]["note"]
    assert C.fixed_cost_breakeven(t, None, "X").iloc[0]["extra_fixed_cost_weeks"] == ""
