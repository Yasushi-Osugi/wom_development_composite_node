# -*- coding: utf-8 -*-
"""
段階 D 第 1 回：手計算の再現（RequestLetter_StageD_Phase1 受入 6、設計 §4・§5.5）

設計 §4 の設定：部材 A（外部 30）・B（外部 40）を W1 に仕入れ、工場 F（法人 E1）で W2 に組立
（加工費 10）→ 完成品 80。F から販売会社 D（法人 E2）へ法人間の価格 100 で W2 に出荷、運賃 5 は D の負担。
W3 に D に到着。W4 に D が外部の顧客へ 150 で販売、販売の運賃 3 は D の負担。保有費用 0。
在庫は週末の残高。

計画の木の形（合成）：A→置場 YA→F、B→置場 YB→F（組立は置場の払い出しの週＝F の P の週）、
F→supply point→D（leaf_out。D が消費者に売る）。

第 2 回（未実現利益の消去後）の期待値も持つ（RequestLetter_StageD_Phase2 で有効にした）。
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from wom.valuechain.fx import FxTable
from wom.valuechain.ledger import Ledger
from wom.valuechain.masters import Assignment, Entity, VCMasters
from wom.valuechain.records import (K_CONSUMER, K_HANDOFF, K_INBOUND, K_OUTBOUND, K_PURCHASE,
                                    NodeInfo, PlanRecords, Shipment)
from wom.valuechain.views import build_views, check_conservation, check_unrealized

W = ["2026-W01", "2026-W02", "2026-W03", "2026-W04"]
P = "P"


def _nodes(d_type="leaf_out"):
    spec = [("A", "leaf_in", "YA", [], 0), ("YA", "stockyard", "F", ["A"], 1),
            ("B", "leaf_in", "YB", [], 2), ("YB", "stockyard", "F", ["B"], 3),
            ("F", "mom", None, ["YA", "YB"], 4), ("SP", "supply_point", None, ["D"], 5),
            ("D", d_type, "SP", [], 6)]
    return {(P, n): NodeInfo(P, n, f"id:{n}", t, par, ch, 0, 0, 1, "in" if r < 5 else "out", r)
            for n, t, par, ch, r in spec}


def _ships(n_weeks=4):
    s = [Shipment("s:A", P, "L1", "A", "id:A", 0, 0, K_PURCHASE, "A", "YA", "A->YA", 0, True, 1, "material:A"),
         Shipment("s:B", P, "L1", "B", "id:B", 0, 0, K_PURCHASE, "B", "YB", "B->YB", 0, True, 1, "material:B"),
         Shipment("s:YA", P, "L1", "YA", "id:YA", 1, 0, K_INBOUND, "YA", "F", "YA->F", 1, True, 1, "material:A"),
         Shipment("s:YB", P, "L1", "YB", "id:YB", 1, 0, K_INBOUND, "YB", "F", "YB->F", 1, True, 1, "material:B"),
         Shipment("s:F", P, "L1", "F", "id:F", 1, 0, K_HANDOFF, "F", "SP", "", 1, True, 1, "finished"),
         Shipment("s:SP", P, "L1", "SP", "id:SP", 1, 0, K_OUTBOUND, "F", "D", "F->D", 2, n_weeks > 2, 1, "finished")]
    if n_weeks > 3:
        s.append(Shipment("s:D", P, "L1", "D", "id:D", 3, 0, K_CONSUMER, "D", "CONSUMER:D", "", None, False,
                          1, "finished"))
    return s


def _masters(d_entity="E2", d_kind="group", d_cons=True, hq="C", common="C", e1_ccy="C", e2_ccy="C",
             tp=100.0, tp_ccy="C", a=30.0, b=40.0, conv=10.0, freight=5.0, sell_freight=3.0, price=150.0,
             price_ccy="C"):
    ents = {"EXT_A": Entity("EXT_A", "", "external_supplier", "C", False),
            "EXT_B": Entity("EXT_B", "", "external_supplier", "C", False),
            "E1": Entity("E1", "", "group", e1_ccy, True)}
    if d_entity != "E1":
        ents[d_entity] = Entity(d_entity, "", d_kind, e2_ccy, d_cons)
    asg = {(n, P): Assignment(n, P, e) for n, e in
           [("A", "EXT_A"), ("B", "EXT_B"), ("YA", "E1"), ("YB", "E1"), ("F", "E1"), ("SP", "E1"),
            ("D", d_entity)]}
    asg[("D", P)].channel_type = "external" if d_kind == "external_channel" else "own"
    return VCMasters(model_dir="", hq_currency=hq, common_currency=common, report_start=None,
                     holding_rate_weekly=None, entities=ents, assignment=asg, price_rules={},
                     market_price={("D", P): [(W[0], price, price_ccy)]},
                     supplier_cost={("A", P): [(W[0], a, e1_ccy)], ("B", P): [(W[0], b, e1_ccy)]},
                     node_cost={("F", P): [{"cost_type": "conversion_cost", "basis": "per_lot", "rate": 0.0,
                                            "fixed": conv, "currency": e1_ccy, "note": ""}]},
                     edge_cost={("F->D", P): [{"cost_type": "logistics_cost", "basis": "per_lot", "rate": 0.0,
                                               "fixed": freight, "currency": e1_ccy}],
                                ("D->CONSUMER", P): [{"cost_type": "logistics_cost", "basis": "per_lot",
                                                      "rate": 0.0, "fixed": sell_freight, "currency": price_ccy}]},
                     tariff={}, transfer_price={("F", P): {"method": "fixed", "margin_rate": 0.0,
                                                           "fixed_price": tp, "currency": tp_ccy}})


def _fx(rows=None, base="C"):
    rows = rows or [(w, "C", 1.0) for w in W]
    return FxTable(pd.DataFrame([{"week": w, "currency": c, "base_currency": base, "rate": r}
                                 for w, c, r in rows]), "test")


def _run(masters, n_weeks=4, report_idx=0, fx=None, d_type="leaf_out"):
    recs = PlanRecords("plan:test", W[:n_weeks], 1.0, _nodes(d_type), _ships(n_weeks))
    lines = []
    led = Ledger(recs, masters, fx or _fx(), sink=lines.append).run()
    v = build_views(led, report_idx)
    return led, v, lines


def _row(tab, w, key=None, keycol=None):
    t = tab[tab["week_index"] == w]
    if key is not None:
        t = t[t[keycol] == key]
    assert len(t) == 1, t
    return t.iloc[0]


def _inv(v, w, owner=None, col="entity_hq", group=False):
    i = v["inventory"]
    i = i[(i["week_index"] == w) & (i["external"] == 0) & (i["valued"] == 1)]
    if owner is not None:
        i = i[i["owner"] == owner]
    return float(i[col].sum())


# ── §4 the basic table ────────────────────────────────────────────────
def test_basic_table():
    led, v, _ = _run(_masters())
    assert led.issues == []
    v2, v3 = v["v2"], v["v3"]
    # E1: W1 0 / inventory 70; W2 20 / 0
    assert _row(v2, 0, "E1", "entity")["profit_hq_wk"] == 0 and _inv(v, 0, "E1") == 70
    assert _row(v2, 1, "E1", "entity")["profit_hq_wk"] == pytest.approx(20)
    assert _inv(v, 1, "E1") == 0
    # E2: inventory 105 in transit (W2), 105 at D (W3), W4 profit 42
    inv = v["inventory"]
    w2 = inv[(inv["week_index"] == 1) & (inv["owner"] == "E2")]
    assert list(w2["location_kind"]) == ["transit"] and float(w2["entity_hq"].sum()) == pytest.approx(105)
    w3 = inv[(inv["week_index"] == 2) & (inv["owner"] == "E2")]
    assert list(w3["location"]) == ["D"] and float(w3["entity_hq"].sum()) == pytest.approx(105)
    assert _row(v2, 3, "E2", "entity")["profit_hq_wk"] == pytest.approx(42)
    # group (V3, first round): single week 20 / 0 / 42, cumulative 20 / 20 / 62, inventory 105 / 105 / 0
    assert [_row(v3, w)["profit_hq_wk"] for w in (1, 2, 3)] == pytest.approx([20, 0, 42])
    assert [_row(v3, w)["profit_hq_cum"] for w in (1, 2, 3)] == pytest.approx([20, 20, 62])
    assert [_inv(v, w) for w in (1, 2, 3)] == pytest.approx([105, 105, 0])
    # E1 cumulative 20 + E2 cumulative 42 = 62 = group
    assert _row(v2, 3, "E1", "entity")["profit_hq_cum"] + _row(v2, 3, "E2", "entity")["profit_hq_cum"] \
        == pytest.approx(_row(v3, 3)["profit_hq_cum"])
    # conservation (acceptance 3)
    assert check_conservation(led, v)["ok"].all()


def test_basic_table_round2():
    led, v, _ = _run(_masters())
    v3 = v["v3"]
    assert [_row(v3, w)["profit_r2_hq_wk"] for w in (1, 2, 3)] == pytest.approx([0, 0, 62])
    assert [_inv(v, w, col="group_hq") for w in (1, 2, 3)] == pytest.approx([85, 85, 0])
    # the internal profit of E1 (100 - 80 = 20) sits in E2's inventory until D sells (W4)
    assert [_row(v3, w)["unrealized_balance_hq_wk"] for w in (0, 1, 2, 3)] == pytest.approx([0, 20, 20, 0])
    assert [_row(v3, w)["unrealized_change_hq_wk"] for w in (1, 2, 3)] == pytest.approx([20, 0, -20])
    # round 1 - round 2 = the change of the balance, each week; cumulative both 62 at W4
    assert _row(v3, 3)["profit_r2_hq_cum"] == pytest.approx(_row(v3, 3)["profit_hq_cum"]) == pytest.approx(62)
    c = check_unrealized(led, v)
    assert c["ok"], c
    assert c["period"]["unrealized_opening_hq"] == 0 and c["period"]["unrealized_closing_hq"] == 0


# ── (1) F and D in the same entity E1 ─────────────────────────────────
def test_variation_1_same_entity():
    led, v, _ = _run(_masters(d_entity="E1"))
    v1, v2 = v["v1"], v["v2"]
    f = _row(v1, 1, "F", "node")
    assert f["revenue_hq_wk"] == pytest.approx(100) and f["profit_hq_wk"] == pytest.approx(20)
    assert _row(v1, 3, "D", "node")["profit_hq_wk"] == pytest.approx(42)       # 150 - 105 - 3
    assert [_row(v2, w, "E1", "entity")["profit_hq_wk"] for w in (1, 2, 3)] == pytest.approx([0, 0, 62])
    assert [_inv(v, w, "E1") for w in (1, 2, 3)] == pytest.approx([85, 85, 0])
    assert v["v3"][v["v3"]["week_index"] == 3]["profit_hq_cum"].iloc[0] == pytest.approx(62)
    assert v1["profit_hq_cum"][v1["week_index"] == 3].sum() == pytest.approx(62)   # V1 total 62
    assert check_conservation(led, v)["ok"].all()


# ── (2) D outside the consolidation ───────────────────────────────────
def test_variation_2_outside_consolidation():
    led, v, _ = _run(_masters(d_cons=False))
    v2, v3 = v["v2"], v["v3"]
    assert _row(v2, 1, "E1", "entity")["profit_hq_wk"] == pytest.approx(20)
    assert [_row(v3, w)["profit_hq_wk"] for w in (1, 3)] == pytest.approx([20, 0])
    cons = v["inventory"][v["inventory"]["owner"] == "E1"]
    assert float(cons[cons["week_index"] >= 1]["entity_hq"].sum()) == 0
    # freight 5 and D's sale 150 are not the group's
    a = v["agg"]
    assert float(a[a["consolidated"] & (a["kind"] == "revenue") & a["scope"].isin(["external", "intercompany"])]["hq"].sum()) == pytest.approx(100)


# ── (3) D is an external sales channel (②) ────────────────────────────
# The letter's (3) first said "数字は (2) と同じ" (E1 20), which contradicted its own cost
# table (§1-4, policy.py): freight on an edge from the group to an outside party is the
# SELLER's selling expense. Owner/Claude resolved it for the table (2026-10-01):
# E1 = 100 - 80 - 5 = 15. (2) stays 20 because D there is a group company (receiver pays).
def test_variation_3_external_channel():
    led, v, _ = _run(_masters(d_kind="external_channel", d_cons=False))
    v3 = v["v3"]
    assert [_row(v3, w)["profit_hq_wk"] for w in (1, 3)] == pytest.approx([15, 0])   # policy table
    a0 = v["agg"]
    sel = a0[(a0["kind"] == "expense") & (a0["scope"] == "selling") & (a0["entity"] == "E1")]
    assert float(sel["hq"].sum()) == pytest.approx(5)
    inv = v["inventory"]
    ext = inv[inv["external"] == 1].groupby("week_index")["lots"].sum()
    assert [int(ext.get(w, 0)) for w in (1, 2, 3)] == [1, 1, 0]          # in transit, at D, sold
    obs = v["observation"]
    assert float(obs[obs["week_index"] == 3]["sale_hq_wk"].sum()) == pytest.approx(150)
    a = v["agg"]
    assert float(a[a["consolidated"] & (a["kind"] == "revenue") & a["scope"].isin(["external", "intercompany"])]["hq"].sum()) == pytest.approx(100)


# ── (4) the period ends while in transit (W2) ─────────────────────────
def test_variation_4_end_in_transit():
    led, v, _ = _run(_masters(), n_weeks=2)
    v3 = v["v3"]
    assert _row(v3, 1)["profit_hq_cum"] == pytest.approx(20)
    inv = v["inventory"]
    e2 = inv[(inv["week_index"] == 1) & (inv["owner"] == "E2")]
    assert list(e2["location_kind"]) == ["transit"] and float(e2["entity_hq"].sum()) == pytest.approx(105)


def test_variation_4_round2():
    led, v, _ = _run(_masters(), n_weeks=2)
    assert _row(v["v3"], 1)["profit_r2_hq_cum"] == pytest.approx(0)
    assert _inv(v, 1, col="group_hq") == pytest.approx(85)
    # round 1 cumulative 20 - round 2 cumulative 0 = closing unrealized 20 - opening 0
    c = check_unrealized(led, v)
    assert c["ok"], c
    assert c["period"]["round1_minus_round2"] == pytest.approx(20)
    assert c["period"]["unrealized_closing_hq"] == pytest.approx(20)
    by = {x["entity"]: x for x in c["by_entity"]}
    assert by["E2"]["closing_hq"] == pytest.approx(20) and by["E2"]["eliminated_in_period_hq"] == pytest.approx(20)
    assert by["E1"]["closing_hq"] == pytest.approx(0)


# ── (5) purchase and assembly in the warmup weeks (report from W3) ────
def test_variation_5_warmup():
    led, v, _ = _run(_masters(), report_idx=2)
    v3 = v["v3"]
    opening = _inv(v, 1)                       # closing of W2 = opening of W3
    assert opening == pytest.approx(105)
    assert _row(v3, 3)["profit_hq_cum"] == pytest.approx(42)     # W3..W4 only
    assert _inv(v, 3) == pytest.approx(0)
    c = check_conservation(led, v)
    rep = c[c["week_index"] >= 2].groupby("entity")[["receipts", "issues"]].sum()
    assert rep["receipts"].sum() == pytest.approx(0) and rep["issues"].sum() == pytest.approx(105)


def test_variation_5_round2():
    led, v, _ = _run(_masters(), report_idx=2)
    assert _inv(v, 1, col="group_hq") == pytest.approx(85)
    assert _row(v["v3"], 3)["profit_r2_hq_cum"] == pytest.approx(62)
    # the opening unrealized profit (20, built in the warmup) is carried in and realized in W4
    c = check_unrealized(led, v)
    assert c["ok"], c
    p = c["period"]
    assert p["unrealized_opening_hq"] == pytest.approx(20) and p["unrealized_closing_hq"] == pytest.approx(0)
    assert p["profit_round1_hq"] == pytest.approx(42) and p["profit_round2_hq"] == pytest.approx(62)
    assert p["round1_minus_round2"] == pytest.approx(-20)          # = closing 0 - opening 20


# ── §5.5 currencies (USD and JPY) ─────────────────────────────────────
def test_currency_table_5_5():
    fx = _fx([("2026-W01", "USD", 150.0), ("2026-W02", "USD", 150.0), ("2026-W03", "USD", 145.0),
              ("2026-W04", "USD", 140.0)], base="JPY")
    m = _masters(d_entity="E_US", hq="JPY", common="USD", e1_ccy="JPY", e2_ccy="USD", tp=100.0,
                 tp_ccy="USD", a=8000.0, b=0.0, conv=0.0, freight=0.0, sell_freight=0.0, price=150.0,
                 price_ccy="USD")
    led, v, lines = _run(m, fx=fx)
    v2 = v["v2"]
    e1 = _row(v2, 1, "E1", "entity")                      # E_JP (named E1 here)
    assert e1["revenue_hq_wk"] == pytest.approx(15000) and e1["profit_hq_wk"] == pytest.approx(7000)
    us = _row(v2, 3, "E_US", "entity")
    assert us["revenue_hq_wk"] == pytest.approx(21000)          # 150 x 140
    assert us["cogs_hq_wk"] == pytest.approx(-15000)            # carried at the W2 rate
    assert us["profit_hq_wk"] == pytest.approx(6000)            # management evaluation
    assert us["profit_func_wk"] == pytest.approx(50)            # USD
    assert us["profit_local_translated_hq_wk"] == pytest.approx(7000)   # 50 x 140: kept apart
    assert _row(v["v3"], 3)["profit_hq_cum"] == pytest.approx(13000)
    # E_US's inventory: USD 100 / JPY 15,000 (W2 rate)
    inv = v["inventory"]
    i = inv[(inv["week_index"] == 2) & (inv["owner"] == "E_US")]
    assert float(i["entity_func"].sum()) == pytest.approx(100) and float(i["entity_hq"].sum()) == pytest.approx(15000)
    # original amounts are kept with their currency
    rev = [l for l in lines if l[9] == "revenue" and l[6] == "E_US"]
    assert rev[0][14] == pytest.approx(150) and rev[0][15] == "USD"
    # round 2 (design 5.5): group revenue 21,000, group cost 8,000 (carried at the purchase-week
    # rate), profit 13,000 JPY -- W2 0 and W4 13,000; round 1 W2 7,000 and W4 6,000
    v3 = v["v3"]
    assert [_row(v3, w)["profit_hq_wk"] for w in (1, 3)] == pytest.approx([7000, 6000])
    assert [_row(v3, w)["profit_r2_hq_wk"] for w in (1, 3)] == pytest.approx([0, 13000])
    assert _row(v3, 3)["external_cogs_r2_hq_wk"] == pytest.approx(-8000)
    assert _row(v3, 3)["profit_r2_hq_cum"] == pytest.approx(_row(v3, 3)["profit_hq_cum"]) == pytest.approx(13000)
    assert [_row(v3, w)["unrealized_balance_hq_wk"] for w in (1, 2, 3)] == pytest.approx([7000, 7000, 0])
    # the common currency (USD): the same identity holds week by week
    c = check_unrealized(led, v)
    assert c["ok"], c
    # kept apart from the local profit translated at the week's rate (V2, 7,000 above)
    assert "profit_local_translated_hq_wk" not in v3.columns


def test_fx_no_silent_one_or_prior_week():
    """受入 8：表の後の週・無い通貨は NaN（記録）。助走週は最初の週のレート（記録）。"""
    fx = _fx([("2026-W02", "USD", 150.0), ("2026-W03", "USD", 145.0)], base="JPY")
    r, m = fx.rate("USD", "JPY", "2026-W01")
    assert r == 150.0 and m == "first_week_rate_before_table"
    r, m = fx.rate("USD", "JPY", "2026-W04")
    assert math.isnan(r) and m == "missing_unvalued"            # after the table: no prior-week
    r, m = fx.rate("EUR", "JPY", "2026-W02")
    assert math.isnan(r) and m == "missing_unvalued"            # no such currency: not 1
    assert {x["method"] for x in fx.log_rows()} == {"first_week_rate_before_table", "missing_unvalued"}
    # cross rates through the base agree: EUR->USD->JPY == EUR->JPY
    fx2 = _fx([("2026-W02", "USD", 150.0), ("2026-W02", "EUR", 162.0)], base="JPY")
    eu_us, _ = fx2.rate("EUR", "USD", "2026-W02")
    us_jp, _ = fx2.rate("USD", "JPY", "2026-W02")
    eu_jp, _ = fx2.rate("EUR", "JPY", "2026-W02")
    assert eu_us * us_jp == pytest.approx(eu_jp)


def test_missing_price_is_unvalued_and_listed():
    m = _masters(d_entity="E2")
    m.transfer_price = {}                                  # no intercompany price F -> D
    led, v, _ = _run(m)
    assert ("F->D", P, "intercompany") in led.missing
    a = v["agg"]
    ic = a[(a["kind"] == "revenue") & (a["scope"] == "intercompany")]
    assert int(ic["n_unvalued"].sum()) == 1 and float(ic["hq"].sum()) == 0
    assert check_conservation(led, v)["ok"].all()
    # round 2: the lot without a price has an unvalued unrealized profit -- counted, never 0
    uw = v["unrealized_week"].set_index("week_index")
    assert [int(uw["lots_unvalued"][w]) for w in (1, 2)] == [1, 1]
    assert check_unrealized(led, v)["ok"]
