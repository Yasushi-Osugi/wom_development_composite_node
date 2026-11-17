# -*- coding: utf-8 -*-
"""Rule rows never booked: a warning only (RequestLetter_MoneyBase_Smartx_CostFix B, §5)."""
import json
import os
import shutil
from types import SimpleNamespace as NS

import pandas as pd

from tools import run_headless_from_folder as rh
from wom.ppc.ppc_unused_rules import KIND, KIND_ZERO, find_unused_rule_rows

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PLUGINS = "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"


def _ev(src, node, prod, t, edge=""):
    return NS(source_rule=src, node_id=node, product_id=prod, ppc_event_type=t, edge_id=edge)


class _Node(NS):
    pass


class _Tree:
    """P: Fac(mom) ; SP(supply point) -> DC(dad) -> Shop_A, Shop_B(leaf_out)"""
    products = ["P"]

    def iter_all_nodes(self, prod):
        a, b = _Node(node_name="Shop_A", node_type="leaf_out", children=[]), _Node(node_name="Shop_B", node_type="leaf_out", children=[])
        dc_b = _Node(node_name="DC_B", node_type="dad", children=[b])
        dc = _Node(node_name="DC", node_type="dad", children=[a])
        return [_Node(node_name="Fac", node_type="mom", children=[]), _Node(node_name="SP", node_type="supply_point", children=[dc, dc_b]),
                dc, dc_b, a, b]


def _files(tmp_path):
    w = lambda n, t: (tmp_path / n).write_text(t, encoding="utf-8")
    w("ppc_edge_cost_rule.csv", "edge_id,product_id,cost_type,basis,rate,fixed_amount,currency\n"
      "Fac->DC,P,logistics_cost,per_lot,0,5,USD\n"          # booked
      "SP->Shop_A,P,logistics_cost,per_lot,0,7,USD\n"       # key does not match
      "DC_B->Shop_B,P,logistics_cost,per_lot,0,1,USD\n"     # no shipment to Shop_B
      "Shop_A->CONSUMER,P,delivery_packing_cost,qty,0,3,USD\n"   # Value Chain only
      "Fac->DC_B,P,logistics_cost,per_lot,0,0,USD\n")       # zero row, never booked
    w("ppc_tariff_rule.csv", "edge_id,from_country,to_country,product_id,hs_code,tariff_rate,tariff_basis\n")
    w("ppc_node_cost_rule.csv", "node_id,product_id,cost_type,basis,rate,fixed_amount,currency,note\n")
    w("ppc_supplier_cost.csv", "supplier_node,product_id,week,purchase_price,currency\nFac,P,2027-W01,9,USD\n")
    w("ppc_market_price.csv", "market_node,product_id,week,market_price,currency\nShop_A,P,2027-W01,20,USD\n")
    w("ppc_transfer_price_rule.csv", "mom_node,product_id,method,margin_rate,fixed_price,currency\n")
    return {n: str(tmp_path / n) for n in ("ppc_edge_cost_rule.csv", "ppc_tariff_rule.csv", "ppc_node_cost_rule.csv",
                                           "ppc_supplier_cost.csv", "ppc_market_price.csv", "ppc_transfer_price_rule.csv")}


def test_unused_rows_reasons_and_zero_kind(tmp_path):
    paths = _files(tmp_path)
    events = [_ev("ppc_edge_cost_rule.csv", "DC", "P", "logistics_cost", "Fac->DC"),
              _ev("ppc_supplier_cost.csv", "Fac", "P", "supplier_cost"),
              _ev("ppc_market_price.csv", "Shop_A", "P", "market_revenue")]
    r = find_unused_rule_rows(paths, {}, events, _Tree(), use_node_name=True)
    w = pd.DataFrame(r["warnings"])
    loc = dict(zip(w["location"].str.split(" ").str[0], w["detail"]))
    assert set(loc) == {"ppc_edge_cost_rule.csv:3", "ppc_edge_cost_rule.csv:4", "ppc_edge_cost_rule.csv:5",
                        "ppc_edge_cost_rule.csv:6"}
    assert "（key_or_place）" in loc["ppc_edge_cost_rule.csv:3"]
    assert "（no_shipment）" in loc["ppc_edge_cost_rule.csv:4"]
    assert "（ppc_unused_edge）" in loc["ppc_edge_cost_rule.csv:5"]
    assert set(w.loc[w["location"].str.startswith("ppc_edge_cost_rule.csv:6"), "kind"]) == {KIND_ZERO}
    assert r["summary"]["count"] == 3 and r["summary"]["zero_count"] == 1
    assert r["summary"]["by_reason"] == {"key_or_place": 1, "no_shipment": 1, "ppc_unused_edge": 1}


def test_shared_rules_only_count_the_models_products(tmp_path):
    paths = _files(tmp_path)
    (tmp_path / "ppc_market_price.csv").write_text(
        "market_node,product_id,week,market_price,currency\nShop_A,P,2027-W01,20,USD\nX,OTHER,2027-W01,1,USD\n",
        encoding="utf-8")
    events = [_ev("ppc_market_price.csv", "Shop_A", "P", "market_revenue")]
    r = find_unused_rule_rows({"ppc_market_price.csv": paths["ppc_market_price.csv"]},
                              {"ppc_market_price.csv": "shared:data/ppc"}, events, _Tree())
    assert r["warnings"] == []


def test_warning_does_not_touch_trust_events(tmp_path):
    """smartphone keeps its 38 never-used rows as warnings; the golden (incl. trust_event_count) is unchanged."""
    m = tmp_path / "smartphone-global-2026-2029"
    shutil.copytree(os.path.join(REPO, "data", "sample", "smartphone-global-2026-2029"), m,
                    ignore=shutil.ignore_patterns("output", "__pycache__"))
    snap = rh.run(str(m), plugins_spec=PLUGINS, output_ppc_dir=str(tmp_path / "ppc"), verbose=False)
    gold = json.load(open(os.path.join(REPO, "tests", "golden", "smartphone-global-2026-2029.json"), encoding="utf-8"))
    assert snap["ppc"] == gold["ppc"]
    k = json.load(open(tmp_path / "ppc" / "ppc_kpi_summary.json", encoding="utf-8"))
    assert k["unused_rule_rows"]["count"] == 38 and k["trust_event_count"] == gold["ppc"]["trust_event_count"]
    w = pd.read_csv(tmp_path / "ppc" / "ppc_warnings.csv")
    assert (w["kind"] == KIND).sum() == 38
