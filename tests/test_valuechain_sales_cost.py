# -*- coding: utf-8 -*-
"""
G1：直販の売上比率の費用（RequestLetter_BSSEAF_Cosmetics_G1_SalesBasedCosts §4）

Unit（合成の木、test_valuechain_handcalc.py の作りに倣う）：
  C2  販売の週に、費目ごとに「率 × その販売の売上」を売り手の販売費として 1 行。価格が無ければ NaN
  C3  vc_sales_cost_rule.csv のあるノードでは ppc_node_cost_rule.csv の basis=revenue の行を使わず、
      issues も出さない。無いノードは今のまま（issues を出す）
  C5  delivery_packing_cost は運賃と同じ扱い（グループから外部へ＝売り手の販売費）
Integration（CSV → 実際のローダ）：
  C1  vc_sales_cost_rule.csv の読み込みの検査
  C4  ppc_node_cost_rule.csv・ppc_edge_cost_rule.csv とのずれで止める
E2E：化粧品のサンプルの写しに表を足して台帳を作り、代表の 2 lot の行を確かめる
"""
from __future__ import annotations

import math
import os
import shutil

import pandas as pd
import pytest

from wom.valuechain.fx import FxTable
from wom.valuechain.ledger import LINE_COLS, Ledger
from wom.valuechain.masters import Assignment, Entity, MasterError, VCMasters, load_masters
from wom.valuechain.records import K_CONSUMER, K_OUTBOUND, K_PURCHASE, NodeInfo, PlanRecords, Shipment

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COS = os.path.join(REPO, "data", "sample", "cosmetics-sg-th-2027-2029")
COS_TM = {"COS_Serum": ["Factory_JP"], "COS_Cream": ["Factory_JP"]}

W = ["2026-W01", "2026-W02", "2026-W03", "2026-W04"]
P = "P"

SALES_COST_CSV = """node_id,product_id,cost_item,ppc_cost_type,basis,rate,currency,note
SG_EC,COS_Serum,hq_sga_allocation,sga_cost,revenue,0.10,SGD,a
SG_EC,COS_Serum,payment_platform_fee,sga_cost,revenue,0.05,SGD,b
SG_EC,COS_Serum,digital_ad,marketing_cost,revenue,0.15,SGD,c
SG_EC,COS_Cream,hq_sga_allocation,sga_cost,revenue,0.10,SGD,a
SG_EC,COS_Cream,payment_platform_fee,sga_cost,revenue,0.05,SGD,b
SG_EC,COS_Cream,digital_ad,marketing_cost,revenue,0.15,SGD,c
SG_Store,COS_Serum,store_operating,sga_cost,revenue,0.35,SGD,d
SG_Store,COS_Serum,hq_sga_allocation,sga_cost,revenue,0.10,SGD,a
SG_Store,COS_Cream,store_operating,sga_cost,revenue,0.35,SGD,d
SG_Store,COS_Cream,hq_sga_allocation,sga_cost,revenue,0.10,SGD,a
"""
DELIVERY_ROWS = ("SG_EC->CONSUMER,COS_Serum,delivery_packing_cost,qty,0,3,SGD\n"
                 "SG_EC->CONSUMER,COS_Cream,delivery_packing_cost,qty,0,3,SGD\n")


# ── Unit: a small synthetic tree ───────────────────────────────────────
# supplier A (external) -> D-centre F (E1, group) -> leaf D (E1, own channel) -> consumer
def _nodes():
    spec = [("A", "leaf_in", "F", [], 0), ("F", "mom", None, ["A"], 1),
            ("SP", "supply_point", None, ["D"], 2), ("D", "leaf_out", "SP", [], 3)]
    return {(P, n): NodeInfo(P, n, f"id:{n}", t, par, ch, 0, 0, 1, "in" if r < 2 else "out", r)
            for n, t, par, ch, r in spec}


def _ships():
    return [Shipment("s:A", P, "L1", "A", "id:A", 0, 0, K_PURCHASE, "A", "F", "A->F", 1, True, 2, "material:A"),
            Shipment("s:SP", P, "L1", "SP", "id:SP", 1, 0, K_OUTBOUND, "F", "D", "F->D", 2, True, 2, "finished"),
            Shipment("s:D", P, "L1", "D", "id:D", 3, 0, K_CONSUMER, "D", "CONSUMER:D", "", None, False, 2,
                     "finished")]


def _masters(sales_cost=None, node_cost_d=None, price=150.0, delivery=3.0):
    ents = {"EXT_A": Entity("EXT_A", "", "external_supplier", "C", False),
            "E1": Entity("E1", "", "group", "C", True)}
    asg = {(n, P): Assignment(n, P, e) for n, e in [("A", "EXT_A"), ("F", "E1"), ("SP", "E1"), ("D", "E1")]}
    asg[("D", P)].channel_type = "own"
    node_cost = {}
    if node_cost_d is not None:
        node_cost[("D", P)] = node_cost_d
    edge_cost = {}
    if delivery is not None:
        edge_cost[("D->CONSUMER", P)] = [{"cost_type": "delivery_packing_cost", "basis": "qty", "rate": 0.0,
                                          "fixed": delivery, "currency": "C"}]
    return VCMasters(model_dir="", hq_currency="C", common_currency="C", report_start=None,
                     holding_rate_weekly=None, entities=ents, assignment=asg, price_rules={},
                     market_price={} if price is None else {("D", P): [(W[0], price, "C")]},
                     supplier_cost={("A", P): [(W[0], 40.0, "C")]},
                     node_cost=node_cost, edge_cost=edge_cost, tariff={}, transfer_price={},
                     sales_cost=sales_cost or {})


def _fx():
    return FxTable(pd.DataFrame([{"week": w, "currency": "C", "base_currency": "C", "rate": 1.0} for w in W]),
                   "test")


def _run(m):
    recs = PlanRecords("plan:test", W, 1.0, _nodes(), _ships())
    lines = []
    led = Ledger(recs, m, _fx(), sink=lines.append).run()
    return led, pd.DataFrame(lines, columns=LINE_COLS)


SC = {("D", P): [{"cost_item": "hq_sga_allocation", "ppc_cost_type": "sga_cost", "rate": 0.10, "currency": "C",
                  "note": ""},
                 {"cost_item": "digital_ad", "ppc_cost_type": "marketing_cost", "rate": 0.15, "currency": "C",
                  "note": ""}]}
PPC_ROWS_D = [{"cost_type": "sga_cost", "basis": "revenue", "rate": 0.10, "fixed": 3.0, "currency": "C", "note": ""},
              {"cost_type": "marketing_cost", "basis": "revenue", "rate": 0.15, "fixed": 0.0, "currency": "C",
               "note": ""}]


def _g1(df):
    return df[(df.kind == "expense") & (df.scope == "selling") & (df.node == "D")]


def test_c2_lines_at_the_sale_week_one_per_item():
    led, df = _run(_masters(sales_cost=SC))
    g = _g1(df).set_index("price_type")
    # revenue 2 units x 150 = 300; 10 % and 15 %; delivery 2 x 3
    assert sorted(g.index) == ["delivery_packing_cost", "digital_ad", "hq_sga_allocation"]
    assert g.loc["hq_sga_allocation", "amount_orig"] == pytest.approx(30.0)
    assert g.loc["digital_ad", "amount_orig"] == pytest.approx(45.0)
    assert g.loc["delivery_packing_cost", "amount_orig"] == pytest.approx(6.0)
    for it, fam in (("hq_sga_allocation", "sga_cost"), ("digital_ad", "marketing_cost"),
                    ("delivery_packing_cost", "freight")):
        r = g.loc[it]
        assert r.family == fam and r.week_index == 3 and r.entity == "E1"
        assert r.counterparty == "CONSUMER:D" and r.src_id == "s:D" and r.lot_id == "L1"
        assert r.basis == "v1,entity,group" and r.currency_orig == "C" and r.valued == 1
    assert led.issues == []
    # the expense is part of the group's profit of the sale week (V3)
    from wom.valuechain.views import build_views
    v3 = build_views(led, 0)["v3"]
    # revenue 300 - cogs (2 units x 40) - expenses (30 + 45 + 6)
    assert float(v3["profit_hq_wk"].sum()) == pytest.approx(300 - 80 - 81)


def test_c2_no_price_gives_unvalued_lines():
    led, df = _run(_masters(sales_cost=SC, price=None))
    g = _g1(df)
    sc = g[g.price_type.isin(["hq_sga_allocation", "digital_ad"])]
    assert len(sc) == 2
    assert sc.amount_orig.isna().all() and (sc.valued == 0).all()


def test_c3_ppc_rows_not_used_and_no_issue_when_the_table_exists():
    led, df = _run(_masters(sales_cost=SC, node_cost_d=PPC_ROWS_D))
    assert led.issues == []
    assert dict(led.ppc_only_node_cost) == {("D", P, "sga_cost"): 1, ("D", P, "marketing_cost"): 1}
    # no node-cost line at the receipt (week 2) for D
    assert df[(df.node == "D") & (df.week_index == 2) & (df.kind == "expense")].empty
    assert len(_g1(df)) == 3


def test_c3_without_the_table_behaves_as_before():
    led, df = _run(_masters(sales_cost=None, node_cost_d=PPC_ROWS_D))
    iss = [i for i in led.issues if i["issue"] == "revenue_based_node_cost_not_supported"]
    assert sorted(i["cost_type"] for i in iss) == ["marketing_cost", "sga_cost"]
    assert dict(led.ppc_only_node_cost) == {}
    g = _g1(df)
    assert list(g.price_type) == ["delivery_packing_cost"]     # only the delivery edge


# ── Integration: CSV -> load_masters ───────────────────────────────────
def _cos(tmp_path, sales=SALES_COST_CSV, delivery=DELIVERY_ROWS):
    """A copy of the cosmetics sample with the given table / delivery rows. The official sample has
    both since stage 6 (G1 sample adoption); they are taken out first, so each test sets its own."""
    d = tmp_path / "cos"
    shutil.copytree(COS, d)
    (d / "vc_sales_cost_rule.csv").unlink(missing_ok=True)
    ec = d / "ppc_edge_cost_rule.csv"
    lines = ec.read_text(encoding="utf-8").splitlines(keepends=True)
    ec.write_text("".join(l for l in lines if "->CONSUMER," not in l), encoding="utf-8")
    if delivery:
        with open(d / "ppc_edge_cost_rule.csv", "a", encoding="utf-8") as f:
            f.write(delivery)
    if sales is not None:
        (d / "vc_sales_cost_rule.csv").write_text(sales, encoding="utf-8")
    return str(d)


def _load(d):
    return load_masters(d, COS_TM, {})


def test_c1_loads_and_absent_file_is_empty(tmp_path):
    m = _load(_cos(tmp_path))
    assert sorted(m.sales_cost) == [("SG_EC", "COS_Cream"), ("SG_EC", "COS_Serum"),
                                    ("SG_Store", "COS_Cream"), ("SG_Store", "COS_Serum")]
    assert sum(len(v) for v in m.sales_cost.values()) == 10
    assert _load(_cos(tmp_path / "none", sales=None, delivery="")).sales_cost == {}
    # the official sample carries the table since stage 6 (same 10 rows)
    assert {k: [(r["cost_item"], r["rate"]) for r in v] for k, v in _load(COS).sales_cost.items()} == \
        {k: [(r["cost_item"], r["rate"]) for r in v] for k, v in m.sales_cost.items()}


@pytest.mark.parametrize("old,new,match", [
    ("SG_EC,COS_Cream,digital_ad,marketing_cost,revenue,0.15,SGD,c",
     "SG_EC,COS_Cream,digital_ad,marketing_cost,revenue,0.15,SGD,c\n"
     "SG_EC,COS_Cream,digital_ad,marketing_cost,revenue,0.15,SGD,c", "twice"),
    ("SG_EC,COS_Cream,digital_ad,", "SG_EC,COS_Cream,tv_ad,", "cost_item"),
    ("digital_ad,marketing_cost,revenue,0.15,SGD,c\nSG_Store,COS_Serum",
     "digital_ad,warehouse_cost,revenue,0.15,SGD,c\nSG_Store,COS_Serum", "ppc_cost_type"),
    ("SG_Store,COS_Cream,store_operating,sga_cost,revenue,", "SG_Store,COS_Cream,store_operating,sga_cost,qty,",
     "only 'revenue'"),
    ("SG_Store,COS_Cream,store_operating,sga_cost,revenue,0.35", "SG_Store,COS_Cream,store_operating,sga_cost,revenue,1.35",
     "between 0 and 1"),
    ("SG_Store,COS_Cream,store_operating,sga_cost,revenue,0.35", "SG_Store,COS_Cream,store_operating,sga_cost,revenue,x",
     "not a number"),
    ("SG_Store,COS_Cream,store_operating", "SG_Distributor,COS_Cream,store_operating", "direct-sales leaf"),
    ("SG_Store,COS_Cream,store_operating,sga_cost,revenue,0.35,SGD", "SG_Store,COS_Cream,store_operating,sga_cost,revenue,0.35,JPY",
     "market price currency"),
    ("node_id,product_id,cost_item,ppc_cost_type,basis,rate,currency,note",
     "node_id,product_id,cost_item,ppc_cost_type,rate,currency,note", "missing columns"),
])
def test_c1_load_checks_stop(tmp_path, old, new, match):
    assert old in SALES_COST_CSV
    text = SALES_COST_CSV.replace(old, new, 1)
    if match == "missing columns":   # drop the basis value from every row as well
        text = "\n".join([text.splitlines()[0]] + [",".join(l.split(",")[:4] + l.split(",")[5:])
                                                   for l in text.splitlines()[1:]]) + "\n"
    with pytest.raises(MasterError, match=match):
        _load(_cos(tmp_path, sales=text))


def test_c4_rate_sum_must_match_ppc(tmp_path):
    text = SALES_COST_CSV.replace("SG_EC,COS_Cream,hq_sga_allocation,sga_cost,revenue,0.10",
                                  "SG_EC,COS_Cream,hq_sga_allocation,sga_cost,revenue,0.12")
    with pytest.raises(MasterError, match=r"sga_cost: the items sum to 0.17 but .* says 0.15"):
        _load(_cos(tmp_path, sales=text))


def test_c4_fixed_amount_must_be_on_the_consumer_edge(tmp_path):
    with pytest.raises(MasterError, match=r"fixed amount of 3 per unit.*add up to 0"):
        _load(_cos(tmp_path, delivery=""))


def test_c4_ppc_type_without_items_stops(tmp_path):
    text = SALES_COST_CSV.replace("SG_EC,COS_Cream,digital_ad,marketing_cost,revenue,0.15,SGD,c\n", "")
    with pytest.raises(MasterError, match="has no marketing_cost item"):
        _load(_cos(tmp_path, sales=text))


# ── E2E: the cosmetics sample copy with the table ──────────────────────
def test_e2e_cosmetics_copy_books_g1_at_the_sale(tmp_path):
    from wom.valuechain.run import run_valuechain
    d = _cos(tmp_path)
    out = str(tmp_path / "out")
    r = run_valuechain(d, out, plugins="HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin")
    assert not [i for i in r["checks"]["issues"] if i["issue"] == "revenue_based_node_cost_not_supported"]
    m = pd.read_csv(os.path.join(out, "vc_money_lines.csv.gz"), low_memory=False)
    g = m[(m.kind == "expense") & (m.scope == "selling") & m.node.isin(["SG_EC", "SG_Store"])
          & m.counterparty.astype(str).str.startswith("CONSUMER:")]
    ec = g[g.lot_id == "COS_Cream:SG_EC:2028-W28:00001"]
    assert len(ec) == 4 and set(ec.week) == {"2028-W28"}
    assert ec.amount_orig.sum() == pytest.approx(1015.20)
    st = g[g.lot_id == "COS_Cream:SG_Store:2028-W30:00001"]
    assert len(st) == 2 and set(st.week) == {"2028-W30"}
    assert st.amount_orig.sum() == pytest.approx(1490.40)
    assert g.amt_hq.sum() == pytest.approx(281_015_748, abs=0.5)
    assert r["checks"]["sales_cost_rule"]["rows"] == 10
