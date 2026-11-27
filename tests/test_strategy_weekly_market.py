# -*- coding: utf-8 -*-
"""wom/strategy/compare — the weekly table and the market tables (RequestLetter_Promo_Convert_Slice2 §3).

Unit: two small synthetic cases. The weekly differences (with 「その他の週」) add up to 「計」 and 計 to the whole
difference; the market money rows add up to ΔP0; a week with backlog outside the range gets a row; the cost
premises spread over their paid weeks. Integration: tools.compare_scenarios.money_by_week_market on a small
synthetic run (the market sums equal profit_r2_hq_wk; a line without a Lot_ID goes to its own row)."""
import pandas as pd
import pytest

from tools import compare_scenarios as CS
from wom.strategy import StrategyError
from wom.strategy import compare as SC

LABELS = ["2028-W01", "2028-W02", "2028-W03", "2028-W04", "2028-W05"]
SKU, TGT, OTH = "P", "EC", "DIST"


def _frames(case, on_time, q5, money, prod, inv, cost):
    """on_time/q5: {(region, week): n}; money: {(region, week): profit}; prod: {week: lots}."""
    req = []
    for reg in (TGT, OTH):
        for w in LABELS:
            o, b = on_time.get((reg, w), 0), q5.get((reg, w), 0)
            req.append({"sku_id": SKU, "region": reg, "request_week": w, "q1": o + b, "on_time": o,
                        "delivered": o, "q5": b})
    mrows = [{"week": w, "sku_id": SKU, "region": reg, "market": reg, "external_revenue": v,
              "external_cogs_group": 0.0, "expense": 0.0, "profit_r2": v, "in_report": w != "2028-W05"}
             for (reg, w), v in money.items()]
    return {"case": case, "labels": LABELS, "req": pd.DataFrame(req),
            "money": pd.DataFrame(mrows, columns=["week", "sku_id", "region", "market"] + SC.MONEY + ["in_report"]),
            "prod": pd.DataFrame([{"week": w, "product": SKU, "production_lots": n} for w, n in prod.items()]),
            "inv": {w: inv.get(w, 0) for w in LABELS}, "cost": SC.cost_by_week(cost, LABELS)}


@pytest.fixture
def two():
    base = _frames("C01", on_time={(TGT, "2028-W02"): 2, (OTH, "2028-W02"): 3, (OTH, "2028-W05"): 2},
                   q5={}, money={(TGT, "2028-W02"): 200.0, (OTH, "2028-W02"): 300.0, (OTH, "2028-W05"): 200.0},
                   prod={"2028-W01": 5, "2028-W04": 2}, inv={"2028-W01": 5, "2028-W02": 0, "2028-W04": 2}, cost=[])
    # the promotion: the target gets one more lot in W02 out of the stock, the other market misses one in W05
    alt = _frames("C02", on_time={(TGT, "2028-W02"): 3, (OTH, "2028-W02"): 3, (OTH, "2028-W05"): 1},
                  q5={(OTH, "2028-W05"): 1},
                  money={(TGT, "2028-W02"): 300.0, (OTH, "2028-W02"): 300.0, (OTH, "2028-W05"): 100.0},
                  prod={"2028-W01": 5, "2028-W04": 2}, inv={"2028-W01": 5, "2028-W02": 0, "2028-W04": 1},
                  cost=[{"cost_item": "promo", "paid_start_week": "2028-W01", "paid_end_week": "2028-W02",
                         "weekly_amount": "10"}])
    return base, alt


def test_weekly_rows_add_up_and_backlog_week_gets_a_row(two):
    base, alt = two
    wt = SC.weekly_table(base, alt, SKU, TGT, "2028-W01", "2028-W02")
    assert list(wt["week"]) == ["2028-W01", "2028-W02", "2028-W05", "その他の週", "計"]   # W05: backlog
    tot = wt.set_index("week").loc["計"]
    assert tot["cost_add"] == 20 and tot["target_on_time"] == 1 and tot["other_on_time"] == -1
    assert tot["other_q5"] == 1 and tot["production_all"] == 0 and tot["inventory_lots"] == -1
    parts = wt[wt["week"] != "計"]
    for c in SC.WEEKLY_COLS:
        assert parts[c].sum() == pytest.approx(tot[c]), c
    assert wt.set_index("week").loc["その他の週", "inventory_lots"] == -1           # W04, not shown


def test_market_money_adds_up_to_the_whole_and_checks_pass(two):
    base, alt = two
    mm = SC.market_money(base, alt)
    t = mm.set_index("market")
    assert t.loc[TGT, "profit_r2_diff"] == 100 and t.loc[OTH, "profit_r2_diff"] == 0   # W05 is outside the report
    assert t.loc["計", "profit_r2_diff"] == 100
    wt = SC.weekly_table(base, alt, SKU, TGT, "2028-W01", "2028-W02")
    assert SC.check_weekly_sums(wt, mm, base, alt, SKU, TGT, 100.0, "2028-W01", "2028-W04") == []
    bad = SC.check_weekly_sums(wt, mm, base, alt, SKU, TGT, 90.0, "2028-W01", "2028-W04")
    assert any("ΔP0" in b for b in bad)
    my = SC.market_year(base, alt).set_index(["region", "year"])
    assert my.loc[(OTH, "2028"), "q5_diff"] == 1 and my.loc[(TGT, "2028"), "on_time_diff"] == 1


def test_cost_premises_and_weeks_stop():
    with pytest.raises(StrategyError):
        SC.cost_by_week([{"cost_item": "x", "paid_start_week": "2028-W01", "paid_end_week": "2028-W02",
                          "weekly_amount": ""}], LABELS)
    with pytest.raises(StrategyError):
        SC.cost_by_week([{"cost_item": "x", "paid_start_week": "2027-W52", "paid_end_week": "2028-W02",
                          "weekly_amount": "1"}], LABELS)


def test_money_by_week_market_matches_v3():
    labels = LABELS[:2]
    money = pd.DataFrame([
        {"week_index": 0, "lot_id": "P:EC:2028-W01:00001", "entity": "E1", "valued": 1, "kind": "revenue",
         "scope": "external", "basis": "group", "product": "P", "amt_hq": 100.0},
        {"week_index": 0, "lot_id": "P:EC:2028-W01:00001", "entity": "E1", "valued": 1, "kind": "cogs",
         "scope": "external", "basis": "v1,group", "product": "P", "amt_hq": 30.0},
        {"week_index": 1, "lot_id": "P:DIST:2028-W02:00001", "entity": "E1", "valued": 1, "kind": "revenue",
         "scope": "external", "basis": "group", "product": "P", "amt_hq": 50.0},
        {"week_index": 1, "lot_id": None, "entity": "E1", "valued": 1, "kind": "expense", "scope": "period",
         "basis": "group", "product": None, "amt_hq": 5.0},
        {"week_index": 1, "lot_id": "P:DIST:2028-W02:00001", "entity": "EXT", "valued": 1, "kind": "revenue",
         "scope": "external", "basis": "group", "product": "P", "amt_hq": 999.0},          # not consolidated
    ])
    run = {"model_dir": "x", "week_labels": labels, "money": money,
           "entity": pd.DataFrame([{"entity_id": "E1", "consolidated": "1"}, {"entity_id": "EXT", "consolidated": "0"}]),
           "tree": pd.DataFrame([{"product_name": "P", "node_type": "leaf_out", "region": "EC", "node_name": "Shop_EC"},
                                 {"product_name": "P", "node_type": "leaf_out", "region": "DIST", "node_name": "DIST"}]),
           "v3": pd.DataFrame([{"group_key": "GROUP", "week_index": 0, "week": labels[0], "in_report": True,
                                "profit_r2_hq_wk": 70.0},
                               {"group_key": "GROUP", "week_index": 1, "week": labels[1], "in_report": True,
                                "profit_r2_hq_wk": 45.0}])}
    df = CS.money_by_week_market(run, "C01")
    g = df.groupby("market")["profit_r2"].sum()
    assert g["Shop_EC"] == 70 and g["DIST"] == 50 and g[CS.NO_LOT_MARKET] == -5
    run["v3"].loc[1, "profit_r2_hq_wk"] = 46.0
    with pytest.raises(CS.CompareError):
        CS.money_by_week_market(run, "C01")


# ── Slice 3 §3: cost items and the holding-cost columns ───────────────────────────────────────────────
def test_item_costs_and_holding_columns():
    rows = [{"cost_item": "promo", "cost_base": 0.0, "cost_alt": 276000.0},
            {"cost_item": "raise", "cost_base": 0.0, "cost_alt": 138000.0},
            {"cost_item": "合計", "cost_base": 0.0, "cost_alt": 414000.0}]
    it = SC._item_costs(rows, "alt")
    assert it == {"promo": 276000.0, "raise": 138000.0} and sum(it.values()) == 414000.0
    assert SC._item_costs(rows, "base") == {"promo": 0.0, "raise": 0.0}
    with pytest.raises(StrategyError):
        SC._item_costs([{"cost_item": "raise", "cost_alt": ""}], "alt")
    h = SC.holding_columns(1000.0, 100.0, 52000.0, [0, 0.10])
    assert h["H_なし"] == 0 and h["A_なし"] == 900
    assert h["H_10%"] == pytest.approx(100.0) and h["A_10%"] == pytest.approx(800.0)


def test_weekly_cost_item_columns_add_up(two):
    base, alt = two
    rows = [{"cost_item": "promo", "paid_start_week": "2028-W01", "paid_end_week": "2028-W02", "weekly_amount": "10"},
            {"cost_item": "raise", "paid_start_week": "2028-W02", "paid_end_week": "2028-W03", "weekly_amount": "5"}]
    alt = {**alt, "cost": SC.cost_by_week(rows, LABELS),
           "cost_items": {r["cost_item"]: SC.cost_by_week([r], LABELS) for r in rows}}
    wt = SC.weekly_table(base, alt, SKU, TGT, "2028-W01", "2028-W02")
    tot = wt.set_index("week").loc["計"]
    assert tot["cost_promo"] == 20 and tot["cost_raise"] == 10 and tot["cost_add"] == 30
    assert wt.set_index("week").loc["その他の週", "cost_raise"] == 5            # W03 is outside the range
    mm = SC.market_money(base, alt)
    assert SC.check_weekly_sums(wt, mm, base, alt, SKU, TGT, 100.0, "2028-W01", "2028-W04") == []


# ── Slice 4 §2: avoidable ratio of a cost item, protected supply check ────────────────────────────────
def test_avoidable_ratio_one_keeps_A_and_zero_puts_the_whole_difference_back():
    row = {"A": 1000.0, "A_なし": 1000.0, "A_10%": 900.0}
    out = SC.avoidable_columns(row, "store_operating", item_alt=200.0, item_base=333.0, ratios=[1, 0.5, 0])
    assert out["A_avoid100%"] == 1000.0 and out["A_10%_avoid100%"] == 900.0          # ratio 1 = A as it is
    assert out["A_avoid0%"] == pytest.approx(1000.0 - 133.0)                       # the whole difference back
    assert out["A_なし_avoid50%"] == pytest.approx(1000.0 - 66.5)
    assert out["A_10%_avoid0%"] == pytest.approx(900.0 - 133.0)


def test_protect_check_met_short_2029_and_increment(tmp_path):
    p = tmp_path / "protect.csv"
    p.write_text("sku_id,market,floor_lots,floor_lots_2029,basis,note\n"
                 "P,DIST,5,3,C02,x\nP,Shop_EC,4,2,C02,existing part\n", encoding="utf-8")
    pt = SC.read_protect(str(p))
    req = pd.DataFrame([
        {"sku_id": "P", "region": "DIST", "request_week": "2028-W10", "q1": 2, "on_time": 2, "delivered": 2},
        {"sku_id": "P", "region": "DIST", "request_week": "2029-W10", "q1": 3, "on_time": 2, "delivered": 2},
        {"sku_id": "P", "region": "EC", "request_week": "2028-W12", "q1": 3, "on_time": 3, "delivered": 3},
        {"sku_id": "P", "region": "EC", "request_week": "2029-W12", "q1": 2, "on_time": 2, "delivered": 2},
    ])
    mm = {("P", "DIST"): "DIST", ("P", "EC"): "Shop_EC"}
    rows = {r["market"]: r for r in SC.protect_rows("C07", req, mm, pt, ("P", "EC"), {"2028-W12": 1})}
    d = rows["DIST"]
    assert (d["delivered"], d["diff"], d["status"]) == (4, -1, "未達")
    assert (d["existing_delivered_2029"], d["diff_2029"], d["status_2029"]) == (2, -1, "未達")
    e = rows["Shop_EC"]
    assert (e["delivered"], e["existing_delivered"], e["status"]) == (5, 4, "達成")   # 5 − increment 1
    assert e["status_2029"] == "達成" and e["demand_increment_delivered"] == "届いた"
    req.loc[2, "on_time"] = 2                                                        # one raised lot late
    e = {r["market"]: r for r in SC.protect_rows("C07", req, mm, pt, ("P", "EC"), {"2028-W12": 1})}["Shop_EC"]
    assert e["demand_increment_delivered"] == "一部届かない"
    p.write_text("sku_id,market,floor_lots,basis,note\nP,DIST,-1,x,y\n", encoding="utf-8")
    with pytest.raises(StrategyError):
        SC.read_protect(str(p))


# ── Launch Slice 2b: floor_case (the floor already contains that case's demand increment) ─────────────────
def test_net_increment_subtracts_the_floor_case_increment():
    assert SC.net_increment_by_week({"W1": 2, "W2": 1}, None) == {"W1": 2, "W2": 1}      # empty = as before
    assert SC.net_increment_by_week({"W1": 2, "W2": 1}, {"W1": 2, "W2": 1}) == {}
    assert SC.net_increment_by_week({"W1": 2}, {"W1": 1, "W3": 1}) == {"W1": 1, "W3": -1}
    assert SC.net_increment_by_week({"W1": 2}, {}) == {"W1": 2}                           # floor case unchanged


def test_protect_floor_case_met_with_zero_diff_and_empty_is_unchanged(tmp_path):
    req = pd.DataFrame([
        {"sku_id": "P", "region": "EC", "request_week": "2028-W12", "q1": 3, "on_time": 3, "delivered": 3},
        {"sku_id": "P", "region": "EC", "request_week": "2029-W12", "q1": 2, "on_time": 2, "delivered": 2},
    ])
    mm = {("P", "EC"): "Shop_EC"}
    inc = {"2028-W12": 1}                       # the case's increment = the floor case's increment
    p = tmp_path / "protect.csv"
    # the floor (5, 2 in 2029) is the floor case's deliveries, which include its increment of 1
    p.write_text("sku_id,market,floor_lots,floor_lots_2029,basis,note,floor_case\n"
                 "P,Shop_EC,5,2,C05_actual,x,C05\n", encoding="utf-8")
    pt = SC.read_protect(str(p), case_ids=["C05", "C07"])
    assert SC.target_floor_case(pt, mm, ("P", "EC")) == "C05"
    e = SC.protect_rows("C07", req, mm, pt, ("P", "EC"), SC.net_increment_by_week(inc, inc))[0]
    assert (e["delivered"], e["demand_increment_net"], e["existing_delivered"]) == (5, 0, 5)
    assert (e["diff"], e["status"], e["diff_2029"], e["status_2029"]) == (0, "達成", 0, "達成")
    assert e["floor_case"] == "C05" and e["demand_increment_delivered"] == "増分なし"
    # empty floor_case: the whole increment is subtracted, as before (the double subtraction shows as -1)
    p.write_text("sku_id,market,floor_lots,floor_lots_2029,basis,note,floor_case\n"
                 "P,Shop_EC,5,2,C05_actual,x,\n", encoding="utf-8")
    pt = SC.read_protect(str(p), case_ids=["C05", "C07"])
    assert SC.target_floor_case(pt, mm, ("P", "EC")) == ""
    e = SC.protect_rows("C07", req, mm, pt, ("P", "EC"), SC.net_increment_by_week(inc, None))[0]
    assert (e["existing_delivered"], e["diff"], e["status"]) == (4, -1, "未達")
    # an unknown floor case stops
    p.write_text("sku_id,market,floor_lots,basis,note,floor_case\nP,Shop_EC,5,x,y,C99\n", encoding="utf-8")
    with pytest.raises(StrategyError):
        SC.read_protect(str(p), case_ids=["C05", "C07"])
