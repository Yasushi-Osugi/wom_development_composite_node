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
