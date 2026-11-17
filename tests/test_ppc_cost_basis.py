# -*- coding: utf-8 -*-
"""ppc_cost_basis.csv — the cost of a product held as the finished-goods purchase price at its last factory
(RequestLetter_MoneyBase_Smartx_CostFix C, §5). On a copy of the small bom-test-2026 model."""
import json
import os
import shutil

import pandas as pd
import pytest

from tools import run_headless_from_folder as rh
from wom.ppc.ppc_runner import PPCCostBasisError, read_cost_basis

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(REPO, "data", "sample", "bom-test-2026")
PLUGINS = "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"


def _copy(tmp_path):
    m = tmp_path / "bom-test-2026"
    shutil.copytree(SRC, m, ignore=shutil.ignore_patterns("output", "__pycache__"))
    return m


def _run(m, tmp_path, tag):
    out = tmp_path / f"ppc_{tag}"
    snap = rh.run(str(m), plugins_spec=PLUGINS, output_ppc_dir=str(out), verbose=False)
    led = pd.read_csv(out / "ppc_event_ledger.csv", dtype={"edge_id": str})
    led["edge_id"] = led["edge_id"].fillna("")
    return snap, led


def _finished(m, node="Vehicle_Assy", price="9000"):
    (m / "ppc_cost_basis.csv").write_text(f"product_id,cost_basis,purchase_node\nEV_Model_A,finished_goods,{node}\n",
                                          encoding="utf-8")
    p = m / "ppc_supplier_cost.csv"
    if price is not None:
        p.write_text(p.read_text(encoding="utf-8").rstrip("\n") + f"\nVehicle_Assy,EV_Model_A,2026-W01,{price},USD\n",
                     encoding="utf-8")


def test_without_the_table_nothing_changes(tmp_path):
    m = _copy(tmp_path)
    snap, _ = _run(m, tmp_path, "none")
    gold = json.load(open(os.path.join(REPO, "tests", "golden", "bom-test-2026.json"), encoding="utf-8"))
    assert snap["ppc"] == gold["ppc"] and snap["psi"] == gold["psi"]


def test_finished_goods_books_only_the_purchase_price_upstream(tmp_path):
    m = _copy(tmp_path)
    _, base = _run(m, tmp_path, "parts")
    _finished(m)
    snap, led = _run(m, tmp_path, "fg")
    fwd = led[led["direction"] == "forward"]
    sup = fwd[fwd["ppc_event_type"] == "supplier_cost"]
    assert set(sup["node_id"]) == {"Vehicle_Assy"} and (sup["amount_base"] == 9000).all()
    # no parts, no factory node costs
    assert not ((fwd["node_id"] == "Vehicle_Assy") & fwd["ppc_event_type"].isin(["conversion_cost", "logistics_cost"])).any()
    assert not fwd["node_id"].isin(["Tire_Supply", "Battery_Supply", "Tire_Yard", "Battery_Yard"]).any()
    # transfer price: the same rule (cost plus 10 %) on the purchase price
    tp = led[led["ppc_event_type"] == "transfer_price_set"]["amount_base"]
    assert (abs(tp - 9900.0) < 1e-6).all()
    # downstream unchanged: DC freight and market revenue per lot
    for t, node in (("logistics_cost", "DC_Vehicle"), ("market_revenue", "Dealer_Sales")):
        a = led[(led["ppc_event_type"] == t) & (led["node_id"] == node)]["amount_base"].tolist()
        b = base[(base["ppc_event_type"] == t) & (base["node_id"] == node)]["amount_base"].tolist()
        assert a == b and a
    k = json.load(open(tmp_path / "ppc_fg" / "ppc_kpi_summary.json", encoding="utf-8"))
    assert k["unused_rule_rows"]["count"] == 4        # the 2 part prices and the 2 factory node costs are now unused


def test_purchase_node_must_be_the_last_factory(tmp_path):
    m = _copy(tmp_path)
    _finished(m, node="Tire_Supply")
    with pytest.raises(PPCCostBasisError, match="最後の工場"):
        _run(m, tmp_path, "bad")


def test_purchase_price_row_is_required(tmp_path):
    m = _copy(tmp_path)
    _finished(m, price=None)
    with pytest.raises(PPCCostBasisError, match="仕入値の行"):
        _run(m, tmp_path, "missing")


def test_table_checks(tmp_path):
    p = tmp_path / "ppc_cost_basis.csv"
    for text, msg in (("product_id,cost_basis\nA,parts\n", "列が足りません"),
                      ("product_id,cost_basis,purchase_node\nA,whole,X\n", "parts か finished_goods"),
                      ("product_id,cost_basis,purchase_node\nA,finished_goods,\n", "purchase_node"),
                      ("product_id,cost_basis,purchase_node\nA,parts,X\n", "parts の行に purchase_node"),
                      ("product_id,cost_basis,purchase_node\nA,parts,\nA,parts,\n", "重複")):
        p.write_text(text, encoding="utf-8")
        with pytest.raises(PPCCostBasisError, match=msg):
            read_cost_basis(str(tmp_path))
    p.write_text("product_id,cost_basis,purchase_node\nA,finished_goods,F\nB,parts,\n", encoding="utf-8")
    assert read_cost_basis(str(tmp_path)) == {"A": "F"}
    os.remove(p)
    assert read_cost_basis(str(tmp_path)) == {}
