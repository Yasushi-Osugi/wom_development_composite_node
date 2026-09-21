"""
tests/test_ppc_multi_supplier.py
=================================
WOM v1r0m5 — Multi-Tier-1-Supplier PPC forward propagation.

Background
----------
wom/ppc/ppc_forward.py's run_forward_propagation() historically accepted
supplier_node as a single node_id (str) or dict[product_id -> node_id]. In
the GENERIC scenario auto-detect path (wom/ppc/ppc_runner.py), this meant
only the FIRST leaf_in child of a MOM was ever used as "the" supplier --
e.g. for an EV BOM with 3 Tier-1 suppliers (Battery/Motor/ECU) feeding one
MOM, 2 of the 3 suppliers' costs were silently dropped and no PPCEvent was
ever created for them (found while building the ev-europe-2026 sample and
its multi-supplier InBound tree).

Fix: supplier_node now also accepts list[str] / dict[product_id -> list[str]].
run_forward_propagation() loops over every resolved supplier node, summing
into acc.supplier_cost_base and emitting one supplier_cost PPCEvent per
supplier (tagged with that supplier's own node_id) -- so per-node P&L
(build_node_pl_summary) can attribute cost to each Tier-1 supplier
correctly. Single-supplier scenarios (cookie/iphone/rice) are unaffected:
_resolve_node_list() wraps a bare str/dict[str,str] into a 1-item list.

These tests use small, in-memory PPCRuleSet fixtures (no CSV files) so
they exercise ppc_forward.py / ppc_kpi.py directly and independently of
any sample data folder.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from wom.ppc.ppc_forward import run_forward_propagation, _resolve_node_list
from wom.ppc.ppc_fx import FXConverter
from wom.ppc.ppc_kpi import build_node_pl_summary
from wom.ppc.ppc_models import LotCostAccumulator
from wom.ppc.ppc_rules import PPCRuleSet


# ---------------------------------------------------------------------------
# Minimal in-memory rule set: 1 MOM ("Factory"), 3 Tier-1 suppliers
# (Battery / Motor / ECU), 1 product ("EV"), 1 week.
# ---------------------------------------------------------------------------

@pytest.fixture
def rules() -> PPCRuleSet:
    supplier_cost = pd.DataFrame([
        {"supplier_node": "Battery", "product_id": "EV", "week": "2026-W01",
         "purchase_price": 10000.0, "currency": "EUR"},
        {"supplier_node": "Motor", "product_id": "EV", "week": "2026-W01",
         "purchase_price": 3000.0, "currency": "EUR"},
        {"supplier_node": "ECU", "product_id": "EV", "week": "2026-W01",
         "purchase_price": 1000.0, "currency": "EUR"},
    ])
    node_cost_rule = pd.DataFrame([
        {"node_id": "Factory", "product_id": "EV", "cost_type": "conversion_cost",
         "basis": "per_lot", "rate": 0.0, "fixed_amount": 2000.0, "currency": "EUR"},
    ])
    edge_cost_rule = pd.DataFrame(columns=[
        "edge_id", "product_id", "cost_type", "basis", "rate", "fixed_amount", "currency"
    ])
    tariff_rule = pd.DataFrame(columns=[
        "edge_id", "product_id", "tariff_rate", "tariff_basis"
    ])
    transfer_price_rule = pd.DataFrame(columns=[
        "mom_node", "product_id", "method", "margin_rate", "fixed_price", "currency"
    ])
    market_price = pd.DataFrame(columns=[
        "market_node", "product_id", "week", "market_price", "currency"
    ])
    profit_zone_rule = pd.DataFrame(columns=[
        "profit_zone_role", "product_id", "profit_type", "basis", "rate", "fixed_amount"
    ])
    fx_rate = pd.DataFrame([
        {"week": "2026-W01", "currency": "EUR", "base_currency": "JPY", "rate": 165.0},
    ])
    node_profit_zone = pd.DataFrame([
        {"node_id": "Battery", "product_id": "EV", "profit_zone_role": "SUPPLIER", "country": "DE"},
        {"node_id": "Motor",   "product_id": "EV", "profit_zone_role": "SUPPLIER", "country": "DE"},
        {"node_id": "ECU",     "product_id": "EV", "profit_zone_role": "SUPPLIER", "country": "DE"},
        {"node_id": "Factory", "product_id": "EV", "profit_zone_role": "MOM_PLANT", "country": "DE"},
    ])
    return PPCRuleSet(
        market_price=market_price,
        supplier_cost=supplier_cost,
        node_cost_rule=node_cost_rule,
        edge_cost_rule=edge_cost_rule,
        tariff_rule=tariff_rule,
        transfer_price_rule=transfer_price_rule,
        profit_zone_rule=profit_zone_rule,
        fx_rate=fx_rate,
        node_profit_zone=node_profit_zone,
    )


@pytest.fixture
def fx(rules) -> FXConverter:
    return FXConverter(rules.fx_rate, base_currency="JPY")


def _acc(lot_id="L-001") -> LotCostAccumulator:
    return LotCostAccumulator(
        lot_id=lot_id, week="2026-W01", product_id="EV", channel_node="Sales_DE",
    )


# ===========================================================================
# _resolve_node_list: backward-compatible resolution helper
# ===========================================================================
class TestResolveNodeList:

    def test_bare_string_wraps_to_single_item_list(self):
        assert _resolve_node_list("Supplier_CN", "EV") == ["Supplier_CN"]

    def test_dict_of_strings_legacy_single_supplier(self):
        node = {"EV": "Supplier_CN", "RICE": "Farm_JP"}
        assert _resolve_node_list(node, "EV") == ["Supplier_CN"]

    def test_bare_list_multi_supplier_same_for_all_products(self):
        node = ["Battery", "Motor", "ECU"]
        assert _resolve_node_list(node, "EV") == ["Battery", "Motor", "ECU"]

    def test_dict_of_lists_multi_supplier_per_product(self):
        node = {"EV": ["Battery", "Motor", "ECU"], "RICE": ["Farm_JP"]}
        assert _resolve_node_list(node, "EV") == ["Battery", "Motor", "ECU"]
        assert _resolve_node_list(node, "RICE") == ["Farm_JP"]


# ===========================================================================
# run_forward_propagation: multi-supplier cost accumulation + events
# ===========================================================================
class TestMultiSupplierForwardPropagation:

    def test_one_supplier_cost_event_per_tier1_supplier(self, rules, fx):
        acc = _acc()
        events = run_forward_propagation(
            [acc], rules, fx, sc_paths={},
            mom_node="Factory",
            supplier_node=["Battery", "Motor", "ECU"],
        )
        supplier_events = [e for e in events if e.ppc_event_type == "supplier_cost"]
        assert len(supplier_events) == 3, "One supplier_cost event per Tier-1 supplier"
        assert {e.node_id for e in supplier_events} == {"Battery", "Motor", "ECU"}

    def test_supplier_cost_base_sums_all_suppliers(self, rules, fx):
        acc = _acc()
        run_forward_propagation(
            [acc], rules, fx, sc_paths={},
            mom_node="Factory",
            supplier_node=["Battery", "Motor", "ECU"],
        )
        # (10000 + 3000 + 1000) EUR * 165.0 JPY/EUR
        expected = 14000.0 * 165.0
        assert acc.supplier_cost_base == pytest.approx(expected, rel=1e-6)

    def test_dict_of_lists_multi_product_form(self, rules, fx):
        """GENERIC scenario shape: dict[product_id -> list[node_id]]."""
        acc = _acc()
        supplier_node = {"EV": ["Battery", "Motor", "ECU"]}
        events = run_forward_propagation(
            [acc], rules, fx, sc_paths={},
            mom_node={"EV": "Factory"},
            supplier_node=supplier_node,
        )
        supplier_events = [e for e in events if e.ppc_event_type == "supplier_cost"]
        assert len(supplier_events) == 3
        assert acc.supplier_cost_base == pytest.approx(14000.0 * 165.0, rel=1e-6)

    def test_legacy_single_supplier_string_unaffected(self, rules, fx):
        """Cookie/iPhone/Rice-style single-supplier call still works as before."""
        acc = _acc()
        events = run_forward_propagation(
            [acc], rules, fx, sc_paths={},
            mom_node="Factory",
            supplier_node="Battery",
        )
        supplier_events = [e for e in events if e.ppc_event_type == "supplier_cost"]
        assert len(supplier_events) == 1
        assert supplier_events[0].node_id == "Battery"
        assert acc.supplier_cost_base == pytest.approx(10000.0 * 165.0, rel=1e-6)


# ===========================================================================
# build_node_pl_summary: per-node P&L attribution (拠点別P/L評価)
# ===========================================================================
class TestNodePLSummary:

    def test_each_supplier_gets_its_own_pl_row(self, rules, fx):
        acc = _acc()
        events = run_forward_propagation(
            [acc], rules, fx, sc_paths={},
            mom_node="Factory",
            supplier_node=["Battery", "Motor", "ECU"],
        )
        node_pl = build_node_pl_summary(events)
        node_ids = set(node_pl["node_id"])
        assert {"Battery", "Motor", "ECU", "Factory"}.issubset(node_ids)

        battery_row = node_pl[node_pl["node_id"] == "Battery"].iloc[0]
        motor_row   = node_pl[node_pl["node_id"] == "Motor"].iloc[0]
        ecu_row     = node_pl[node_pl["node_id"] == "ECU"].iloc[0]

        assert battery_row["cost_base"] == pytest.approx(10000.0 * 165.0, rel=1e-6)
        assert motor_row["cost_base"]   == pytest.approx(3000.0 * 165.0, rel=1e-6)
        assert ecu_row["cost_base"]     == pytest.approx(1000.0 * 165.0, rel=1e-6)

        # Before the fix, Motor/ECU would have had NO events at all and thus
        # would not appear in node_pl_summary -- this is the regression guard.
        assert motor_row["cost_base"] > 0
        assert ecu_row["cost_base"] > 0

    def test_empty_events_returns_empty_frame_with_expected_columns(self):
        node_pl = build_node_pl_summary([])
        assert list(node_pl.columns) == [
            "node_id", "product_id", "revenue_base", "cost_base",
            "tariff_base", "gross_profit_base", "gross_margin_pct", "lot_events",
        ]
        assert len(node_pl) == 0
