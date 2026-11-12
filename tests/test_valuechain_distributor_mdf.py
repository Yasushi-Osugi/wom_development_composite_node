# -*- coding: utf-8 -*-
"""
G2：外部の代理店向けの販促協賛金（MDF）（RequestLetter_BSSEAF_Cosmetics_G2_MDF §4）

Unit（合成の木、test_valuechain_sales_cost.py の作りに倣う）：
  D3  外部の代理店への卸売の週に、表の行ごとに「率 × 卸売の売上」（取引通貨で小数第 2 位に四捨五入）を
      売り手の販売費として 1 行。卸価格が無ければ NaN。代理店の受入・観測の販売では立たない
  D4  外部チャネルの leaf の ppc_node_cost_rule.csv の basis=revenue の行に表の行が無ければ issues
Integration（CSV → 実際のローダ）：
  D2  external の leaf は distributor_mdf だけ・卸価格の通貨と同じ・卸価格が無ければ止める。
      直販の leaf で distributor_mdf は止める
E2E：化粧品のサンプルの写しに表の 4 行を足し、代表の 2 lot と全期間の合計を確かめる
"""
from __future__ import annotations

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
D4 = "revenue_based_cost_on_external_channel_not_booked"

W = ["2026-W01", "2026-W02", "2026-W03", "2026-W04", "2026-W05"]
P = "P"

MDF_ROWS = (
    "SG_Distributor,COS_Serum,distributor_mdf,marketing_cost,revenue,0.05,SGD,mdf\n"
    "SG_Distributor,COS_Cream,distributor_mdf,marketing_cost,revenue,0.05,SGD,mdf\n"
    "TH_Distributor,COS_Serum,distributor_mdf,marketing_cost,revenue,0.05,THB,mdf\n"
    "TH_Distributor,COS_Cream,distributor_mdf,marketing_cost,revenue,0.05,THB,mdf\n")


# ── Unit: a small synthetic tree ───────────────────────────────────────
# supplier A (external) -> factory F (E1) -> DC D (E1) -> distributor X (EXT, external channel) -> consumer
def _nodes():
    spec = [("A", "leaf_in", "F", [], 0), ("F", "mom", None, ["A"], 1),
            ("SP", "supply_point", None, ["D"], 2), ("D", "dad", "SP", ["X"], 3),
            ("X", "leaf_out", "D", [], 4)]
    return {(P, n): NodeInfo(P, n, f"id:{n}", t, par, ch, 0, 0, 1, "in" if r < 2 else "out", r)
            for n, t, par, ch, r in spec}


def _ships(units=2):
    return [Shipment("s:A", P, "L1", "A", "id:A", 0, 0, K_PURCHASE, "A", "F", "A->F", 1, True, units, "material:A"),
            Shipment("s:SP", P, "L1", "SP", "id:SP", 1, 0, K_OUTBOUND, "F", "D", "F->D", 2, True, units,
                     "finished"),
            Shipment("s:D", P, "L1", "D", "id:D", 2, 0, K_OUTBOUND, "D", "X", "D->X", 3, True, units, "finished"),
            Shipment("s:X", P, "L1", "X", "id:X", 4, 0, K_CONSUMER, "X", "CONSUMER:X", "", None, False, units,
                     "finished")]


def _masters(sales_cost=None, wholesale=62.0, node_cost_x=None):
    ents = {"EXT_A": Entity("EXT_A", "", "external_supplier", "C", False),
            "E1": Entity("E1", "", "group", "C", True),
            "EXT_X": Entity("EXT_X", "", "external_channel", "C", False)}
    asg = {(n, P): Assignment(n, P, e) for n, e in [("A", "EXT_A"), ("F", "E1"), ("SP", "E1"), ("D", "E1"),
                                                     ("X", "EXT_X")]}
    asg[("X", P)].channel_type = "external"
    pr = {} if wholesale is None else {("D->X", P, "wholesale"): [(W[0], wholesale, "C")]}
    node_cost = {} if node_cost_x is None else {("X", P): node_cost_x}
    return VCMasters(model_dir="", hq_currency="C", common_currency="C", report_start=None,
                     holding_rate_weekly=None, entities=ents, assignment=asg, price_rules=pr,
                     market_price={("X", P): [(W[0], 99.0, "C")]},
                     supplier_cost={("A", P): [(W[0], 40.0, "C")]},
                     node_cost=node_cost, edge_cost={}, tariff={}, transfer_price={},
                     sales_cost=sales_cost or {})


def _fx():
    return FxTable(pd.DataFrame([{"week": w, "currency": "C", "base_currency": "C", "rate": 1.0} for w in W]),
                   "test")


def _run(m, units=2):
    recs = PlanRecords("plan:test", W, 1.0, _nodes(), _ships(units))
    lines = []
    led = Ledger(recs, m, _fx(), sink=lines.append).run()
    return led, pd.DataFrame(lines, columns=LINE_COLS)


SC = {("X", P): [{"cost_item": "distributor_mdf", "ppc_cost_type": "marketing_cost", "rate": 0.05,
                  "currency": "C", "note": "", "external": True}]}
PPC_X = [{"cost_type": "marketing_cost", "basis": "revenue", "rate": 0.05, "fixed": 0.0, "currency": "C",
          "note": ""}]


def _mdf(df):
    return df[df.price_type == "distributor_mdf"]


def test_d3_one_line_at_the_wholesale_week():
    led, df = _run(_masters(sales_cost=SC))
    g = _mdf(df)
    assert len(g) == 1
    r = g.iloc[0]
    # wholesale 2 units x 62 = 124; 5 % = 6.20
    assert r.amount_orig == pytest.approx(6.20) and r.currency_orig == "C"
    assert r.week_index == 2 and r.src_id == "s:D" and r.lot_id == "L1"
    assert (r.kind, r.scope, r.basis, r.family) == ("expense", "selling", "v1,entity,group", "marketing_cost")
    assert (r.entity, r.node, r.counterparty) == ("E1", "D", "EXT_X")
    assert r.note == "販促の対象：X" and r.valued == 1
    ws = df[(df.kind == "revenue") & (df.price_type == "wholesale")]
    assert len(ws) == 1 and ws.iloc[0].week_index == r.week_index and ws.iloc[0].src_id == r.src_id
    assert led.issues == []
    # the expense lowers the group's profit of the wholesale week (V3)
    from wom.valuechain.views import build_views
    v3 = build_views(led, 0)["v3"]
    assert float(v3["profit_hq_wk"].sum()) == pytest.approx(124 - 80 - 6.20)


def test_d3_not_at_the_receipt_nor_the_observation_sale():
    led, df = _run(_masters(sales_cost=SC))
    g = _mdf(df)
    assert set(g.week_index) == {2}          # receipt at X is week 3, the consumer sale week 4
    assert df[(df.node == "X") & (df.kind == "expense")].empty
    obs = df[df.kind == "observation_sale"]
    assert len(obs) == 1 and obs.iloc[0].week_index == 4
    assert df[df.week_index.isin([3, 4]) & (df.kind == "expense")].empty


def test_d3_no_wholesale_price_gives_nan():
    led, df = _run(_masters(sales_cost=SC, wholesale=None))
    g = _mdf(df)
    assert len(g) == 1 and g.amount_orig.isna().all() and (g.valued == 0).all()


@pytest.mark.parametrize("price,units,expect", [
    (0.13, 1, 0.01),       # 0.0065 -> 0.01 (half up)
    (0.25, 1, 0.01),       # 0.0125 -> 0.01
    (0.3, 1, 0.02),        # 0.015 -> 0.02 (half up, not banker's)
    (1.7, 3, 0.26),        # 5.1 x 0.05 = 0.255 -> 0.26
    (62.0, 24, 74.40),
])
def test_d3_rounding_half_up_to_2_decimals(price, units, expect):
    led, df = _run(_masters(sales_cost=SC, wholesale=price), units=units)
    assert _mdf(df).iloc[0].amount_orig == expect


def test_d3_direct_rows_are_not_used_at_the_wholesale():
    # a row without the external flag (a direct-sales row keyed on X by hand) is not booked at the wholesale
    sc = {("X", P): [dict(SC[("X", P)][0], external=False, cost_item="digital_ad")]}
    led, df = _run(_masters(sales_cost=sc))
    assert df[df.price_type.isin(["digital_ad", "distributor_mdf"])].empty


def test_d4_issue_without_the_table_and_none_with_it():
    led, df = _run(_masters(sales_cost=None, node_cost_x=PPC_X))
    iss = [i for i in led.issues if i["issue"] == D4]
    assert len(iss) == 1
    assert (iss[0]["node"], iss[0]["product"], iss[0]["cost_type"], iss[0]["receipts"]) == \
        ("X", P, "marketing_cost", 1)
    assert _mdf(df).empty
    led, df = _run(_masters(sales_cost=SC, node_cost_x=PPC_X))
    assert [i for i in led.issues if i["issue"] == D4] == []


# ── Integration: CSV -> load_masters ───────────────────────────────────
def _cos(tmp_path, extra=MDF_ROWS, price_rule=None):
    """A copy of the cosmetics sample with the given distributor rows. The official sample has the 4
    distributor_mdf rows since stage 6 (G2 sample adoption); they are taken out first, so each test
    sets its own."""
    d = tmp_path / "cos"
    shutil.copytree(COS, d)
    sc = d / "vc_sales_cost_rule.csv"
    lines = sc.read_text(encoding="utf-8").splitlines(keepends=True)
    sc.write_text("".join(l for l in lines if ",distributor_mdf," not in l), encoding="utf-8")
    if extra:
        with open(d / "vc_sales_cost_rule.csv", "a", encoding="utf-8") as f:
            f.write(extra)
    if price_rule is not None:
        price_rule(d / "vc_price_rule.csv")
    return str(d)


def _load(d):
    return load_masters(d, COS_TM, {})


def test_d2_external_rows_load(tmp_path):
    m = _load(_cos(tmp_path))
    ext = {k: v for k, v in m.sales_cost.items() if k[0].endswith("_Distributor")}
    assert sorted(ext) == [("SG_Distributor", "COS_Cream"), ("SG_Distributor", "COS_Serum"),
                           ("TH_Distributor", "COS_Cream"), ("TH_Distributor", "COS_Serum")]
    assert all(len(v) == 1 and v[0]["external"] and v[0]["cost_item"] == "distributor_mdf" for v in ext.values())
    assert sum(len(v) for v in m.sales_cost.values()) == 14
    assert not any(r["external"] for k, v in m.sales_cost.items() if k not in ext for r in v)


def test_d2_external_leaf_other_item_stops(tmp_path):
    extra = MDF_ROWS.replace("SG_Distributor,COS_Cream,distributor_mdf", "SG_Distributor,COS_Cream,digital_ad")
    with pytest.raises(MasterError, match="external distributor leaf"):
        _load(_cos(tmp_path, extra=extra))


def test_d2_direct_leaf_distributor_mdf_stops(tmp_path):
    extra = MDF_ROWS + "SG_EC,COS_Cream,distributor_mdf,marketing_cost,revenue,0.05,SGD,x\n"
    with pytest.raises(MasterError, match="only for an external distributor leaf"):
        _load(_cos(tmp_path, extra=extra))


def test_d2_currency_must_be_the_wholesale_currency(tmp_path):
    extra = MDF_ROWS.replace("TH_Distributor,COS_Cream,distributor_mdf,marketing_cost,revenue,0.05,THB",
                             "TH_Distributor,COS_Cream,distributor_mdf,marketing_cost,revenue,0.05,SGD")
    with pytest.raises(MasterError, match="wholesale price currency"):
        _load(_cos(tmp_path, extra=extra))


def test_d2_no_wholesale_price_stops(tmp_path):
    def drop(p):
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        p.write_text("".join(l for l in lines if not l.startswith("DC_TH->TH_Distributor,COS_Serum,")),
                     encoding="utf-8")
    with pytest.raises(MasterError, match="no wholesale price"):
        _load(_cos(tmp_path, price_rule=drop))


def test_d2_c4_rate_must_match_ppc(tmp_path):
    extra = MDF_ROWS.replace("SG_Distributor,COS_Serum,distributor_mdf,marketing_cost,revenue,0.05",
                             "SG_Distributor,COS_Serum,distributor_mdf,marketing_cost,revenue,0.06")
    with pytest.raises(MasterError, match="marketing_cost: the items sum to 0.06"):
        _load(_cos(tmp_path, extra=extra))


# ── E2E: the cosmetics sample copy with the 4 rows ─────────────────────
def test_e2e_cosmetics_copy_books_mdf_at_the_wholesale(tmp_path):
    from wom.valuechain.run import run_valuechain
    d = _cos(tmp_path)
    out = str(tmp_path / "out")
    r = run_valuechain(d, out, plugins="HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin")
    assert not [i for i in r["checks"]["issues"] if i["issue"] == D4]
    m = pd.read_csv(os.path.join(out, "vc_money_lines.csv.gz"), low_memory=False)
    g = _mdf(m)
    sg = g[g.lot_id == "COS_Cream:SG_Distributor:2028-W29:00002"]
    assert len(sg) == 1 and sg.iloc[0].week == "2028-W28" and sg.iloc[0].amount_orig == pytest.approx(74.40)
    assert (sg.iloc[0].entity, sg.iloc[0].node, sg.iloc[0].counterparty) == ("E_SG", "DC_SG", "EXT_CH_SG_DIST")
    assert sg.iloc[0].src_id == "ship:COS_Cream:OUT:dad:DC_SG:COS_Cream:96:6"
    th = g[g.lot_id == "COS_Cream:TH_Distributor:2029-W03:00003"]
    assert len(th) == 1 and th.iloc[0].week == "2029-W02" and th.iloc[0].amount_orig == pytest.approx(1920.0)
    assert (th.iloc[0].entity, th.iloc[0].counterparty) == ("E_JP", "EXT_CH_TH_DIST")
    assert len(g) == 2340
    assert g.amt_hq.sum() == pytest.approx(22_196_148, abs=0.5)
    cmp_ = pd.read_csv(os.path.join(out, "vc_ppc_comparison.csv"))
    diff = cmp_[cmp_["item"].str.startswith("利益 合計")].iloc[0]["difference_ledger_minus_ppc"]
    assert abs(float(diff)) < 0.5


def test_official_sample_books_the_mdf(tmp_path):
    """Stage 6: the official sample carries the 4 distributor_mdf rows, so nothing is left unbooked
    and the Value Chain profit equals PPC's. Without the rows, the 4 D4 issues come back."""
    from wom.valuechain.run import run_valuechain
    plugins = "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"
    out = str(tmp_path / "out")
    r = run_valuechain(COS, out, plugins=plugins)
    assert [i for i in r["checks"]["issues"] if i["issue"] == D4] == []
    assert r["checks"]["sales_cost_rule"]["rows"] == 14
    m = pd.read_csv(os.path.join(out, "vc_money_lines.csv.gz"), low_memory=False)
    g = _mdf(m)
    assert len(g) == 2340 and g.amt_hq.sum() == pytest.approx(22_196_148, abs=0.5)
    cmp_ = pd.read_csv(os.path.join(out, "vc_ppc_comparison.csv"))
    diff = cmp_[cmp_["item"].str.startswith("利益 合計")].iloc[0]["difference_ledger_minus_ppc"]
    assert abs(float(diff)) < 0.5
    out2 = str(tmp_path / "out_norule")
    r2 = run_valuechain(_cos(tmp_path, extra=""), out2, plugins=plugins)
    iss = sorted((i["node"], i["product"], i["cost_type"]) for i in r2["checks"]["issues"] if i["issue"] == D4)
    assert iss == [("SG_Distributor", "COS_Cream", "marketing_cost"), ("SG_Distributor", "COS_Serum", "marketing_cost"),
                   ("TH_Distributor", "COS_Cream", "marketing_cost"), ("TH_Distributor", "COS_Serum", "marketing_cost")]
