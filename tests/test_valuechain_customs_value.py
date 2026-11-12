# -*- coding: utf-8 -*-
"""
G4：タイ向けの関税の課税価格（RequestLetter_BSSEAF_Cosmetics_G4_TariffBase §4）

Unit（合成の木、test_valuechain_distributor_mdf.py の作りに倣う）：
  D2  表に載った区間：出荷の週に関税の行を立てず、受入の週に「課税価格 × 率」を受け手の在庫原価に 1 行。
      運賃別（transfer_price＋運賃）と運賃込み（explicit）で同じ課税価格。保険の空欄は未評価。
      0% は行を立てず課税価格の記録だけ。運賃の通貨が違えば出荷の週の為替で換算。期間の後に着く出荷は計上しない
      表の無い区間は今のまま（出荷の週に tariff_basis × 率）
Integration（CSV → 実際のローダ）：
  D1  vc_customs_valuation_rule.csv の止める条件
E2E：化粧品のサンプルの写し（30%）で代表の lot と全期間の合計。正式なサンプル（段階 6 で表の 2 行、0%）は
     関税の行 0 件・課税価格の記録 689 行。表を除いた写しは前のまま（出荷の週に 0 円の行）
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
PLUGINS = "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"
EDGE_TH = "WH_JP_Released->DC_TH"
LOT = "COS_Cream:TH_Distributor:2029-W03:00003"
SHIP = "ship:COS_Cream:OUT:dad:WH_JP_Released:COS_Cream:120:12"

W = ["2026-W01", "2026-W02", "2026-W03", "2026-W04", "2026-W05", "2026-W06"]
P = "P"


# ── Unit: a small synthetic tree ───────────────────────────────────────
# supplier A (external) -> factory F (E1, terminal MOM) -> DC D (E1) -> distributor X (external) -> consumer
# the table edge is F->D (same entity, like WH_JP_Released->DC_TH): ship week 1, receipt week 3
def _nodes():
    spec = [("A", "leaf_in", "F", [], 0), ("F", "mom", None, ["A"], 1),
            ("SP", "supply_point", None, ["D"], 2), ("D", "dad", "SP", ["X"], 3),
            ("X", "leaf_out", "D", [], 4)]
    return {(P, n): NodeInfo(P, n, f"id:{n}", t, par, ch, 0, 0, 1, "in" if r < 2 else "out", r)
            for n, t, par, ch, r in spec}


def _ships(units=2, in_horizon=True):
    s = [Shipment("s:A", P, "L1", "A", "id:A", 0, 0, K_PURCHASE, "A", "F", "A->F", 1, True, units, "material:A"),
         Shipment("s:SP", P, "L1", "SP", "id:SP", 1, 0, K_OUTBOUND, "F", "D", "F->D",
                  3 if in_horizon else None, in_horizon, units, "finished")]
    if in_horizon:
        s += [Shipment("s:D", P, "L1", "D", "id:D", 3, 0, K_OUTBOUND, "D", "X", "D->X", 4, True, units, "finished"),
              Shipment("s:X", P, "L1", "X", "id:X", 5, 0, K_CONSUMER, "X", "CONSUMER:X", "", None, False, units,
                       "finished")]
    return s


def _rule(basis="transfer_price", gv=None, ccy="", freight_in=False, ins=0.0):
    return {("F->D", P): {"goods_value_basis": basis, "goods_value_per_unit": gv, "currency": ccy,
                          "freight_in_goods_value": freight_in, "insurance_added_per_unit": ins,
                          "duty_week": "receipt", "note": ""}}


def _masters(rate=0.3, customs=None, freight_ccy="C", freight=3.0):
    ents = {"EXT_A": Entity("EXT_A", "", "external_supplier", "C", False),
            "E1": Entity("E1", "", "group", "C", True),
            "EXT_X": Entity("EXT_X", "", "external_channel", "C", False)}
    asg = {(n, P): Assignment(n, P, e) for n, e in [("A", "EXT_A"), ("F", "E1"), ("SP", "E1"), ("D", "E1"),
                                                     ("X", "EXT_X")]}
    asg[("X", P)].channel_type = "external"
    return VCMasters(model_dir="", hq_currency="C", common_currency="C", report_start=None,
                     holding_rate_weekly=None, entities=ents, assignment=asg,
                     price_rules={("D->X", P, "wholesale"): [(W[0], 90.0, "C")]},
                     market_price={("X", P): [(W[0], 99.0, "C")]},
                     supplier_cost={("A", P): [(W[0], 10.0, "C")]},
                     node_cost={},
                     edge_cost={("F->D", P): [{"cost_type": "logistics_cost", "basis": "qty", "rate": 0.0,
                                               "fixed": freight, "currency": freight_ccy}]},
                     tariff={("F->D", P): {"rate": rate, "basis": "transfer_price", "from": "", "to": ""}},
                     transfer_price={("F", P): {"method": "fixed", "margin_rate": 0.0, "fixed_price": 50.0,
                                                "currency": "C"}},
                     customs_valuation=customs or {})


def _fx(extra=None):
    rows = [{"week": w, "currency": "C", "base_currency": "C", "rate": 1.0} for w in W]
    for ccy, r in (extra or {}).items():
        rows += [{"week": w, "currency": ccy, "base_currency": "C", "rate": r} for w in W]
    return FxTable(pd.DataFrame(rows), "test")


def _run(m, fx=None, **kw):
    recs = PlanRecords("plan:test", W, 1.0, _nodes(), _ships(**kw))
    lines = []
    led = Ledger(recs, m, fx or _fx(), sink=lines.append).run()
    return led, pd.DataFrame(lines, columns=LINE_COLS)


def _tariff(df):
    return df[(df.family == "tariff") & (df.src_id == "s:SP")]


def test_no_table_keeps_the_ship_week_tariff():
    led, df = _run(_masters())
    t = _tariff(df)
    # transfer price 50 x 2 = 100; 30 % = 30 at the ship week (week 1); freight not added
    assert len(t) == 1 and t.iloc[0].week_index == 1 and t.iloc[0].amount_orig == pytest.approx(30.0)
    assert led.customs_rows == []


def test_table_books_at_the_receipt_week_with_freight():
    led, df = _run(_masters(customs=_rule()))
    t = _tariff(df)
    # customs value = 100 + freight 3 x 2 + insurance 0 = 106; duty 31.80
    assert len(t) == 1
    r = t.iloc[0]
    assert r.week_index == 3 and r.amount_orig == pytest.approx(31.80) and r.currency_orig == "C"
    assert (r.kind, r.scope, r.basis, r.price_type) == ("acquisition", "internal", "v1,entity,group", "tariff_cost")
    assert (r.entity, r.node, r.counterparty, r.lot_id) == ("E1", "D", "E1", "L1")
    assert "106.00 C" in r.note and "受入の週で代用" in r.note
    assert df[(df.family == "tariff") & (df.week_index.isin([1, 2]))].empty
    assert len(led.customs_rows) == 1
    c = led.customs_rows[0]
    assert (c["goods_value"], c["freight_added"], c["insurance_added"], c["customs_value"], c["duty"]) == \
        (100.0, 6.0, 0.0, 106.0, 31.8)
    assert (c["ship_week"], c["duty_week"], c["status"], c["duty_line_id"]) == (W[1], W[3], "valued", int(r.line_id))
    # the duty goes into the cost of the wholesale (week 3): supplier 20 + freight 6 + duty 31.8
    cg = df[(df.kind == "cogs") & (df.src_id == "s:D") & (df.basis == "group")]
    assert cg.iloc[0].amt_hq == pytest.approx(20 + 6 + 31.8)


def test_freight_excluded_and_included_give_the_same_customs_value():
    led_a, df_a = _run(_masters(customs=_rule()))
    led_b, df_b = _run(_masters(customs=_rule(basis="explicit", gv=53.0, ccy="C", freight_in=True)))
    a, b = led_a.customs_rows[0], led_b.customs_rows[0]
    assert a["customs_value"] == b["customs_value"] == 106.0 and a["duty"] == b["duty"] == 31.8
    assert b["freight_added"] == 0.0 and b["goods_value"] == 106.0
    # the error case: included value plus the freight again
    led_e, _ = _run(_masters(customs=_rule(basis="explicit", gv=53.0, ccy="C", freight_in=False)))
    assert led_e.customs_rows[0]["customs_value"] == 112.0


def test_insurance_blank_is_unvalued():
    led, df = _run(_masters(customs=_rule(ins=None)))
    t = _tariff(df)
    assert len(t) == 1 and t.amount_orig.isna().all() and (t.valued == 0).all() and t.iloc[0].week_index == 3
    c = led.customs_rows[0]
    assert c["status"] == "unvalued_insurance" and pd.isna(c["customs_value"]) and pd.isna(c["duty"])
    iss = [i for i in led.issues if i["issue"] == "customs_value_unvalued"]
    assert len(iss) == 1 and (iss[0]["edge"], iss[0]["product"], iss[0]["shipments"]) == ("F->D", P, 1)
    # the lot becomes unvalued from the receipt (its wholesale cost lines are unvalued)
    cg = df[(df.kind == "cogs") & (df.src_id == "s:D")]
    assert (cg.valued == 0).all()


def test_zero_rate_books_no_line_but_keeps_the_record():
    led, df = _run(_masters(rate=0.0, customs=_rule()))
    assert _tariff(df).empty
    c = led.customs_rows[0]
    assert c["customs_value"] == 106.0 and c["duty"] == 0.0 and c["duty_line_id"] == "" and c["duty_week"] == W[3]


def test_freight_in_another_currency_is_converted_at_the_ship_week():
    led, df = _run(_masters(customs=_rule(), freight_ccy="C2"), fx=_fx({"C2": 2.0}))
    c = led.customs_rows[0]
    # freight 3 C2 x 2 units = 6 C2 = 12 C; customs value 112 C; duty 33.60
    assert c["freight_added"] == pytest.approx(12.0) and c["customs_value"] == pytest.approx(112.0)
    assert c["duty"] == pytest.approx(33.6) and c["currency"] == "C"
    assert _tariff(df).iloc[0].amount_orig == pytest.approx(33.6)


def test_rounding_half_up():
    # transfer price 50 x 1 = 50, freight 0.05 -> customs value 50.05; x 0.3 = 15.015 -> 15.02
    led, _ = _run(_masters(customs=_rule(), freight=0.05), units=1)
    assert led.customs_rows[0]["duty"] == 15.02


def test_after_horizon_is_not_booked():
    led, df = _run(_masters(customs=_rule()), in_horizon=False)
    assert _tariff(df).empty
    c = led.customs_rows[0]
    assert c["status"] == "after_horizon" and c["duty_week"] == "" and c["duty_line_id"] == ""
    assert c["duty"] == 31.8          # the value is known; it is just not booked


# ── Integration: CSV -> load_masters ───────────────────────────────────
HDR = ("edge_id,product_id,goods_value_basis,goods_value_per_unit,currency,freight_in_goods_value,"
       "insurance_added_per_unit,duty_week,note\n")
ROWS = (f"{EDGE_TH},COS_Cream,transfer_price,,,0,0,receipt,x\n"
        f"{EDGE_TH},COS_Serum,transfer_price,,,0,0,receipt,x\n")
# the physical edges of the sample (every edge with a freight row, except the consumer deliveries)
PHYS = {p: set(e for e in pd.read_csv(os.path.join(COS, "ppc_edge_cost_rule.csv"), dtype=str)
               .query("product_id == @p")["edge_id"] if not e.endswith("->CONSUMER")) for p in COS_TM}


def _cos(tmp_path, rows=ROWS, header=HDR, rate=None):
    d = tmp_path / "cos"
    shutil.copytree(COS, d)
    (d / "vc_customs_valuation_rule.csv").write_text(header + rows, encoding="utf-8")
    if rate is not None:
        p = d / "ppc_tariff_rule.csv"
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        p.write_text("".join(l.replace(",3304,0,transfer_price", f",3304,{rate},transfer_price")
                             if l.startswith(EDGE_TH + ",") else l for l in lines), encoding="utf-8")
    return str(d)


def _load(d):
    return load_masters(d, COS_TM, PHYS)


def test_d1_rows_load(tmp_path):
    m = _load(_cos(tmp_path))
    assert sorted(m.customs_valuation) == [(EDGE_TH, "COS_Cream"), (EDGE_TH, "COS_Serum")]
    r = m.customs_valuation[(EDGE_TH, "COS_Cream")]
    assert r["goods_value_basis"] == "transfer_price" and r["goods_value_per_unit"] is None
    assert r["freight_in_goods_value"] is False and r["insurance_added_per_unit"] == 0.0


def _cos_no_table(tmp_path):
    d = tmp_path / "cos_notable"
    shutil.copytree(COS, d)
    os.remove(d / "vc_customs_valuation_rule.csv")
    return str(d)


def test_d1_no_file_is_empty(tmp_path):
    assert load_masters(_cos_no_table(tmp_path), COS_TM, PHYS).customs_valuation == {}


def test_d1_official_sample_has_the_two_rows():
    """Stage 6: the official sample carries the G4 table (Thailand, transfer price + freight, insurance 0)."""
    m = load_masters(COS, COS_TM, PHYS)
    assert sorted(m.customs_valuation) == [(EDGE_TH, "COS_Cream"), (EDGE_TH, "COS_Serum")]
    for r in m.customs_valuation.values():
        assert (r["goods_value_basis"], r["freight_in_goods_value"], r["insurance_added_per_unit"],
                r["duty_week"]) == ("transfer_price", False, 0.0, "receipt")


@pytest.mark.parametrize("rows,match", [
    (ROWS + f"{EDGE_TH},COS_Cream,transfer_price,,,0,0,receipt,x\n", "written twice"),
    (f"WH_JP_Released->DC_XX,COS_Cream,transfer_price,,,0,0,receipt,x\n", "not a physical edge"),
    (f"DC_SG->SG_Store,COS_Cream,transfer_price,,,0,0,receipt,x\n", "no row for"),          # no tariff row ... see below
    (f"{EDGE_TH},COS_Cream,invoice,,,0,0,receipt,x\n", "goods_value_basis"),
    (f"{EDGE_TH},COS_Cream,explicit,,JPY,1,0,receipt,x\n", "needs goods_value_per_unit and currency"),
    (f"{EDGE_TH},COS_Cream,explicit,5070,,1,0,receipt,x\n", "needs goods_value_per_unit and currency"),
    (f"{EDGE_TH},COS_Cream,transfer_price,5000,JPY,0,0,receipt,x\n", "leave goods_value_per_unit blank"),
    (f"{EDGE_TH},COS_Cream,transfer_price,,,2,0,receipt,x\n", "freight_in_goods_value"),
    (f"{EDGE_TH},COS_Cream,transfer_price,,,0,0,clearance,x\n", "duty_week"),
    (f"{EDGE_TH},COS_Cream,transfer_price,,,0,-1,receipt,x\n", "must be 0 or more"),
    (f"{EDGE_TH},COS_Cream,explicit,abc,JPY,1,0,receipt,x\n", "not a number"),
    (f"DC_TH->TH_Distributor,COS_Cream,transfer_price,,,1,0,receipt,x\n", "not held by a group entity"),
])
def test_d1_stops(tmp_path, rows, match):
    d = _cos(tmp_path, rows=rows)
    if "DC_SG->SG_Store" in rows:          # take the tariff row of that edge out
        p = os.path.join(d, "ppc_tariff_rule.csv")
        with open(p, encoding="utf-8") as f:
            lines = f.readlines()
        with open(p, "w", encoding="utf-8") as f:
            f.writelines(l for l in lines if not l.startswith("DC_SG->SG_Store,SG,SG,COS_Cream,"))
        match = "ppc_tariff_rule.csv has no row"
    with pytest.raises(MasterError, match=match):
        _load(d)


def test_d1_missing_column_stops(tmp_path):
    with pytest.raises(MasterError, match="missing columns"):
        _load(_cos(tmp_path, header=HDR.replace(",duty_week", ""),
                   rows=f"{EDGE_TH},COS_Cream,transfer_price,,,0,0,x\n"))


def test_d1_freight_excluded_needs_a_freight_row(tmp_path):
    d = _cos(tmp_path)
    p = os.path.join(d, "ppc_edge_cost_rule.csv")
    with open(p, encoding="utf-8") as f:
        lines = f.readlines()
    with open(p, "w", encoding="utf-8") as f:
        f.writelines(l for l in lines if not l.startswith(EDGE_TH + ",COS_Cream,logistics_cost"))
    with pytest.raises(MasterError, match="no logistics_cost row"):
        _load(d)


# ── E2E: the cosmetics sample copy at 30 % ─────────────────────────────
def test_e2e_cosmetics_copy_at_30_percent(tmp_path):
    from wom.valuechain.run import run_valuechain
    d = _cos(tmp_path, rate="0.3")
    out = str(tmp_path / "out")
    r = run_valuechain(d, out, plugins=PLUGINS)
    m = pd.read_csv(os.path.join(out, "vc_money_lines.csv.gz"), low_memory=False)
    sh = pd.read_csv(os.path.join(out, "vc_shipments.csv.gz"), dtype=str)
    cv = pd.read_csv(os.path.join(out, "vc_customs_valuation.csv"), dtype={"duty_line_id": str})
    ids = set(sh.loc[sh.edge == EDGE_TH, "ship_id"])
    t = m[(m.family == "tariff") & m.src_id.isin(ids)]
    lt = t[t.src_id == SHIP]
    assert len(lt) == 1 and lt.iloc[0].week == "2029-W02" and lt.iloc[0].amt_hq == pytest.approx(36_504)
    assert (lt.iloc[0].entity, lt.iloc[0].node) == ("E_JP", "DC_TH")
    c = cv[cv.ship_id == SHIP].iloc[0]
    assert c.customs_value == 121_680 and c.duty == 36_504 and c.duty_week == "2029-W02"
    assert c.duty_line_id == str(int(lt.iloc[0].line_id))
    cg = m[(m.lot_id == LOT) & (m.kind == "cogs") & (m.basis == "group") & (m.week == "2029-W02")]
    assert cg.amt_hq.sum() == pytest.approx(85_560)
    assert len(t) == 689 and t.amt_hq.sum() == pytest.approx(27_959_256)
    assert len(cv) == 689 and cv.customs_value.sum() == pytest.approx(93_197_520)
    assert r["checks"]["customs_valuation"]["after_horizon_not_booked"] == 0
    cmp_ = pd.read_csv(os.path.join(out, "vc_ppc_comparison.csv"))
    diff = cmp_[cmp_["item"].str.startswith("費用 関税")].iloc[0]["difference_ledger_minus_ppc"]
    assert float(diff) == pytest.approx(347_256)


def test_official_sample_records_the_customs_value(tmp_path):
    """Stage 6: the official sample (0 %) books no tariff line on the edge and records 689 customs values."""
    from wom.valuechain.run import run_valuechain
    out = str(tmp_path / "out")
    r = run_valuechain(COS, out, plugins=PLUGINS)
    m = pd.read_csv(os.path.join(out, "vc_money_lines.csv.gz"), low_memory=False)
    sh = pd.read_csv(os.path.join(out, "vc_shipments.csv.gz"), dtype=str)
    ids = set(sh.loc[sh.edge == EDGE_TH, "ship_id"])
    assert m[(m.family == "tariff") & m.src_id.isin(ids)].empty
    cv = pd.read_csv(os.path.join(out, "vc_customs_valuation.csv"), dtype={"duty_line_id": str})
    assert len(cv) == 689 and (cv.status == "valued").all() and (cv.duty == 0).all()
    assert cv.customs_value.sum() == pytest.approx(93_197_520)
    c = cv[cv.ship_id == SHIP].iloc[0]
    assert c.customs_value == 121_680 and c.duty_week == "2029-W02" and pd.isna(c.duty_line_id)
    assert r["checks"]["customs_valuation"]["rows"] == 689
    assert r["checks"]["issues"] == []


def test_copy_without_the_table_is_unchanged(tmp_path):
    """No vc_customs_valuation_rule.csv: no record file, the 689 zero tariff lines at the ship week."""
    from wom.valuechain.run import run_valuechain
    out = str(tmp_path / "out")
    r = run_valuechain(_cos_no_table(tmp_path), out, plugins=PLUGINS)
    assert not os.path.exists(os.path.join(out, "vc_customs_valuation.csv"))
    assert "customs_valuation" not in r["checks"]
    m = pd.read_csv(os.path.join(out, "vc_money_lines.csv.gz"), low_memory=False)
    sh = pd.read_csv(os.path.join(out, "vc_shipments.csv.gz"), dtype=str)
    e = sh[sh.edge == EDGE_TH][["ship_id", "ship_week"]]
    t = m[(m.family == "tariff")].merge(e, left_on="src_id", right_on="ship_id")
    assert len(t) == 689 and (t.amt_hq == 0).all() and (t.week == t.ship_week).all()
