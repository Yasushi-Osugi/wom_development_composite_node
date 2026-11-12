# -*- coding: utf-8 -*-
"""
G5：シンガポール向けの CIF の海上運賃（RequestLetter_BSSEAF_Cosmetics_G5_CIF_Freight §4）

Unit（合成の木、test_valuechain_customs_value.py の作りに倣う）：
  D2  seller・1（CIF 型）の法人間の区間：運賃は売り手の法人間売上に対応する原価（v1・entity）。
      受け手の法人の取得に足さない。グループの原価には 1 回入る。未実現利益の eliminated は運賃の分小さい。
      buyer・0、表なしは今のまま。保存の検査・未実現利益の照合が合う
Integration（CSV → 実際のローダ）：
  D1  vc_trade_terms.csv の止める条件
E2E：化粧品のサンプルの写し（CIF）で代表の lot と全期間の合計。
     正式なサンプルは段階 6（2026-11-12）で表の 2 行を持つ。表を除いた写しは G5 の前のまま
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
from wom.valuechain.views import build_views, check_conservation, check_unrealized

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COS = os.path.join(REPO, "data", "sample", "cosmetics-sg-th-2027-2029")
COS_TM = {"COS_Serum": ["Factory_JP"], "COS_Cream": ["Factory_JP"]}
PLUGINS = "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"
EDGE_SG = "WH_JP_Released->DC_SG"
LOT = "COS_Cream:SG_Store:2028-W30:00001"
SHIP = "ship:COS_Cream:OUT:dad:WH_JP_Released:COS_Cream:93:0"

W = ["2026-W01", "2026-W02", "2026-W03", "2026-W04", "2026-W05", "2026-W06"]
P = "P"


# ── Unit: a small synthetic tree ───────────────────────────────────────
# supplier A (external) -> factory F (E1, terminal MOM) -> DC D (E2) -> own shop X (E2) -> consumer
# the intercompany edge F->D: transfer price 50/unit, freight 3/unit; ship week 1, receipt week 3, sale week 5
def _nodes():
    spec = [("A", "leaf_in", "F", [], 0), ("F", "mom", None, ["A"], 1),
            ("SP", "supply_point", None, ["D"], 2), ("D", "dad", "SP", ["X"], 3),
            ("X", "leaf_out", "D", [], 4)]
    return {(P, n): NodeInfo(P, n, f"id:{n}", t, par, ch, 0, 0, 1, "in" if r < 2 else "out", r)
            for n, t, par, ch, r in spec}


def _ships(units=2):
    return [Shipment("s:A", P, "L1", "A", "id:A", 0, 0, K_PURCHASE, "A", "F", "A->F", 1, True, units, "material:A"),
            Shipment("s:SP", P, "L1", "SP", "id:SP", 1, 0, K_OUTBOUND, "F", "D", "F->D", 3, True, units, "finished"),
            Shipment("s:D", P, "L1", "D", "id:D", 3, 0, K_OUTBOUND, "D", "X", "D->X", 4, True, units, "finished"),
            Shipment("s:X", P, "L1", "X", "id:X", 5, 0, K_CONSUMER, "X", "CONSUMER:X", "", None, False, units,
                     "finished")]


def _terms(by="seller", inp=True):
    return {("F->D", P): {"incoterm": "CIF", "freight_borne_by": by, "freight_in_price": inp, "note": ""}}


def _masters(terms=None):
    ents = {"EXT_A": Entity("EXT_A", "", "external_supplier", "C", False),
            "E1": Entity("E1", "", "group", "C", True),
            "E2": Entity("E2", "", "group", "C", True)}
    asg = {(n, P): Assignment(n, P, e) for n, e in [("A", "EXT_A"), ("F", "E1"), ("SP", "E1"), ("D", "E2"),
                                                     ("X", "E2")]}
    asg[("X", P)].channel_type = "own"
    return VCMasters(model_dir="", hq_currency="C", common_currency="C", report_start=None,
                     holding_rate_weekly=None, entities=ents, assignment=asg, price_rules={},
                     market_price={("X", P): [(W[0], 99.0, "C")]},
                     supplier_cost={("A", P): [(W[0], 10.0, "C")]},
                     node_cost={},
                     edge_cost={("F->D", P): [{"cost_type": "logistics_cost", "basis": "qty", "rate": 0.0,
                                               "fixed": 3.0, "currency": "C"}]},
                     tariff={},
                     transfer_price={("F", P): {"method": "fixed", "margin_rate": 0.0, "fixed_price": 50.0,
                                                "currency": "C"}},
                     trade_terms=terms or {})


def _fx():
    return FxTable(pd.DataFrame([{"week": w, "currency": "C", "base_currency": "C", "rate": 1.0} for w in W]),
                   "test")


def _run(m):
    recs = PlanRecords("plan:test", W, 1.0, _nodes(), _ships())
    lines = []
    led = Ledger(recs, m, _fx(), sink=lines.append).run()
    return led, pd.DataFrame(lines, columns=LINE_COLS).drop(columns=["line_id"])


def _freight(df):
    return df[(df.family == "freight") & (df.src_id == "s:SP")]


def test_no_table_freight_is_the_receivers_inventory_cost():
    led, df = _run(_masters())
    f = _freight(df)
    assert len(f) == 1 and (f.iloc[0].entity, f.iloc[0].kind, f.iloc[0].basis) == ("E2", "acquisition",
                                                                                    "v1,entity,group")
    sale = df[(df.kind == "cogs") & (df.src_id == "s:X")].set_index("basis").amt_hq
    assert sale["entity"] == pytest.approx(106) and sale["group"] == pytest.approx(26)


def test_cif_freight_is_the_sellers_cost_of_the_intercompany_sale():
    led, df = _run(_masters(_terms()))
    f = _freight(df)
    assert set(f.entity) == {"E1"} and (f.week_index == 1).all() and (f.amt_hq == 6.0).all()
    cg = f[f.kind == "cogs"]
    assert sorted(cg.basis) == ["entity", "v1"] and (cg.scope == "intercompany").all()
    assert (cg.node == "F").all() and (cg.counterparty == "E2").all()
    acq = f[f.kind == "acquisition"]
    assert len(acq) == 1 and acq.iloc[0].basis == "v1,entity,group"
    # the receiver acquires the price only, at the ship week
    e2 = df[(df.entity == "E2") & (df.kind == "acquisition")]
    assert list(e2.family) == ["purchase"] and e2.iloc[0].amt_hq == pytest.approx(100)
    # the IC cost of the seller: C 20 + freight 6
    ic = df[(df.entity == "E1") & (df.kind == "cogs") & (df.scope == "intercompany") & (df.basis == "entity")]
    assert ic.amt_hq.sum() == pytest.approx(26)
    # the sale: entity cost 100 (price only), group cost 26 (C + freight once)
    sale = df[(df.kind == "cogs") & (df.src_id == "s:X")].set_index("basis").amt_hq
    assert sale["entity"] == pytest.approx(100) and sale["group"] == pytest.approx(26)
    assert sale["v1"] == pytest.approx(100)


def test_cif_unrealized_profit_and_checks():
    led, _ = _run(_masters(_terms()))
    elim = sum(v[0] for k, v in led.unreal.items() if k[5] == "eliminated")
    real = sum(v[0] for k, v in led.unreal.items() if k[5] == "realized")
    assert elim == pytest.approx(100 - 26) and real == pytest.approx(74)
    views = build_views(led, 0)
    assert check_conservation(led, views)["ok"].all()
    assert check_unrealized(led, views)["ok"]
    # entity profits move by the freight; the consolidated (round 2) profit does not
    led0, _ = _run(_masters())
    v0 = build_views(led0, 0)
    p = views["v2"].groupby("entity").profit_hq_wk.sum() - v0["v2"].groupby("entity").profit_hq_wk.sum()
    assert p["E1"] == pytest.approx(-6) and p["E2"] == pytest.approx(6)
    assert views["v3"]["profit_r2_hq_wk"].tolist() == v0["v3"]["profit_r2_hq_wk"].tolist()


def test_buyer_terms_are_todays_behaviour():
    _, df0 = _run(_masters())
    _, dfb = _run(_masters(_terms("buyer", False)))
    assert df0.equals(dfb)


# ── Integration: CSV -> load_masters ───────────────────────────────────
HDR = "edge_id,product_id,incoterm,freight_borne_by,freight_in_price,note\n"
ROWS = (f"{EDGE_SG},COS_Cream,CIF,seller,1,x\n"
        f"{EDGE_SG},COS_Serum,CIF,seller,1,x\n")
PHYS = {p: set(e for e in pd.read_csv(os.path.join(COS, "ppc_edge_cost_rule.csv"), dtype=str)
               .query("product_id == @p")["edge_id"] if not e.endswith("->CONSUMER")) for p in COS_TM}


def _cos(tmp_path, rows=ROWS, header=HDR, edge_cost=None):
    d = tmp_path / "cos"
    shutil.copytree(COS, d)
    (d / "vc_trade_terms.csv").write_text(header + rows, encoding="utf-8")
    if edge_cost is not None:
        edge_cost(d / "ppc_edge_cost_rule.csv")
    return str(d)


def _load(d):
    return load_masters(d, COS_TM, PHYS)


def _cos_without_table(tmp_path):
    """A copy of the official sample with vc_trade_terms.csv removed (behaviour before G5)."""
    d = tmp_path / "cos_no_terms"
    shutil.copytree(COS, d)
    os.remove(d / "vc_trade_terms.csv")
    return str(d)


def test_d1_rows_load(tmp_path):
    m = _load(_cos(tmp_path))
    assert sorted(m.trade_terms) == [(EDGE_SG, "COS_Cream"), (EDGE_SG, "COS_Serum")]
    assert m.cif_freight(EDGE_SG, "COS_Cream") and not m.cif_freight("WH_JP_Released->DC_TH", "COS_Cream")


def test_d1_no_file_is_empty(tmp_path):
    assert load_masters(_cos_without_table(tmp_path), COS_TM, PHYS).trade_terms == {}


def test_d1_official_sample_rows():
    """Stage 6: the official sample declares CIF (seller / 1) on the Singapore edge for both SKUs."""
    m = load_masters(COS, COS_TM, PHYS)
    assert sorted(m.trade_terms) == [(EDGE_SG, "COS_Cream"), (EDGE_SG, "COS_Serum")]
    assert all(m.cif_freight(EDGE_SG, p) for p in COS_TM)
    assert not m.cif_freight("WH_JP_Released->DC_TH", "COS_Cream")


@pytest.mark.parametrize("rows,match", [
    (ROWS + f"{EDGE_SG},COS_Cream,CIF,seller,1,x\n", "written twice"),
    (f"WH_JP_Released->DC_XX,COS_Cream,CIF,seller,1,x\n", "not a physical edge"),
    (f"{EDGE_SG},COS_Cream,CIF,seller,0,x\n", "cannot be expressed now"),
    (f"{EDGE_SG},COS_Cream,FOB,buyer,1,x\n", "cannot be expressed now"),
    (f"{EDGE_SG},COS_Cream,CIF,both,1,x\n", "cannot be expressed now"),
    (f"WH_JP_Released->DC_TH,COS_Cream,CIF,seller,1,x\n", "not an intercompany edge"),
    (f"DC_SG->SG_Distributor,COS_Cream,CIF,seller,1,x\n", "not an intercompany edge"),
    (f"COS_Cream,CIF,seller,1,x,y\n", "is not '<from node>-><to node>'"),
])
def test_d1_stops(tmp_path, rows, match):
    with pytest.raises(MasterError, match=match):
        _load(_cos(tmp_path, rows=rows))


def test_d1_missing_column_stops(tmp_path):
    with pytest.raises(MasterError, match="missing columns"):
        _load(_cos(tmp_path, header=HDR.replace(",freight_in_price", ""), rows=f"{EDGE_SG},COS_Cream,CIF,seller,x\n"))


def _edit(drop=None, add=None):
    def f(p):
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        if drop:
            lines = [l for l in lines if not l.startswith(drop)]
        if add:
            lines.append(add)
        p.write_text("".join(lines), encoding="utf-8")
    return f


def test_d1_no_freight_row_stops(tmp_path):
    with pytest.raises(MasterError, match="no logistics_cost row"):
        _load(_cos(tmp_path, edge_cost=_edit(drop=f"{EDGE_SG},COS_Cream,logistics_cost")))


def test_d1_insurance_row_stops(tmp_path):
    with pytest.raises(MasterError, match="insurance_cost row"):
        _load(_cos(tmp_path, edge_cost=_edit(add=f"{EDGE_SG},COS_Cream,insurance_cost,qty,0,1,JPY\n")))


# ── E2E: the cosmetics sample copy with CIF ────────────────────────────
def test_e2e_cosmetics_copy_cif(tmp_path):
    from wom.valuechain.run import run_valuechain
    out = str(tmp_path / "out")
    r = run_valuechain(_cos(tmp_path), out, plugins=PLUGINS)
    c = r["checks"]
    assert c["conservation_ok"] and c["unrealized"]["ok"] and c["issues"] == []
    assert c["unrealized"]["period"]["profit_round2_hq"] == pytest.approx(631_119_240)
    m = pd.read_csv(os.path.join(out, "vc_money_lines.csv.gz"), low_memory=False)
    sh = pd.read_csv(os.path.join(out, "vc_shipments.csv.gz"), dtype=str)
    ids = set(sh.loc[sh.edge == EDGE_SG, "ship_id"])
    f = m[(m.family == "freight") & m.src_id.isin(ids)]
    jc = f[(f.entity == "E_JP") & (f.kind == "cogs") & (f.basis == "entity")]
    assert len(jc) == 3367 and jc.amt_hq.sum() == pytest.approx(4_848_480)
    assert f[(f.entity == "E_SG")].empty
    lot = m[m.lot_id == LOT]
    lj = lot[(lot.src_id == SHIP) & (lot.family == "freight") & (lot.kind == "cogs")]
    assert sorted(lj.basis) == ["entity", "v1"] and (lj.week == "2028-W25").all() and (lj.amt_hq == 1440).all()
    sale = lot[(lot.kind == "cogs") & (lot.week == "2028-W30")].set_index("basis").amt_hq
    assert sale["entity"] == pytest.approx(122_208) and sale["group"] == pytest.approx(49_728)
    v2 = pd.read_csv(os.path.join(out, "vc_v2_weekly.csv")).groupby("entity").profit_hq_wk.sum()
    assert v2.sum() == pytest.approx(631_849_608)
    assert r["checks"]["trade_terms"]["edges"][0]["freight_borne_by"] == "seller"


def test_official_sample_cif(tmp_path):
    """Stage 6: the official sample books the Singapore freight on E_JP (same as the CIF copy)."""
    from wom.valuechain.run import run_valuechain
    out = str(tmp_path / "out")
    r = run_valuechain(COS, out, plugins=PLUGINS)
    c = r["checks"]
    assert c["conservation_ok"] and c["unrealized"]["ok"] and c["issues"] == []
    assert c["unrealized"]["period"]["profit_round2_hq"] == pytest.approx(631_119_240)
    m = pd.read_csv(os.path.join(out, "vc_money_lines.csv.gz"), low_memory=False)
    sh = pd.read_csv(os.path.join(out, "vc_shipments.csv.gz"), dtype=str)
    ids = set(sh.loc[sh.edge == EDGE_SG, "ship_id"])
    f = m[(m.family == "freight") & m.src_id.isin(ids)]
    jc = f[(f.entity == "E_JP") & (f.kind == "cogs") & (f.basis == "entity")]
    assert len(jc) == 3367 and jc.amt_hq.sum() == pytest.approx(4_848_480)
    assert f[(f.entity == "E_SG")].empty
    assert [e["freight_borne_by"] for e in c["trade_terms"]["edges"]] == ["seller", "seller"]


def test_copy_without_the_table_is_unchanged(tmp_path):
    from wom.valuechain.run import run_valuechain
    out = str(tmp_path / "out")
    r = run_valuechain(_cos_without_table(tmp_path), out, plugins=PLUGINS)
    assert "trade_terms" not in r["checks"]
    m = pd.read_csv(os.path.join(out, "vc_money_lines.csv.gz"), low_memory=False)
    sh = pd.read_csv(os.path.join(out, "vc_shipments.csv.gz"), dtype=str)
    ids = set(sh.loc[sh.edge == EDGE_SG, "ship_id"])
    f = m[(m.family == "freight") & m.src_id.isin(ids)]
    assert len(f) == 3367 and set(f.entity) == {"E_SG"} and f.amt_hq.sum() == pytest.approx(4_848_480)
