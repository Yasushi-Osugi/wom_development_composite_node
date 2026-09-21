"""
tests/test_ppc_bom_qty.py
==========================
Request Letter B (requests/request_letter_b_bom_qty.md): PPC-side reflection
of the per-node BOM quantity N ("1 set rule").

bom_qty_map scales ONLY the Step 1a supplier_cost line (ppc_supplier_cost.csv
is priced per physical component unit, e.g. $/tyre). It must NOT touch:
  - Step 1b (edge logistics_cost, ppc_edge_cost_rule.csv)
  - Step 1c (MOM/tier node's own conversion_cost/logistics_cost,
    ppc_node_cost_rule.csv)
because those rates are already expressed per FINAL ASSEMBLED UNIT.

These tests use small, in-memory PPCRuleSet fixtures (no CSV files), mirroring
tests/test_ppc_multi_supplier.py's fixture style.
"""

from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from wom.ppc.ppc_forward import run_forward_propagation
from wom.ppc.ppc_fx import FXConverter
from wom.ppc.ppc_models import LotCostAccumulator
from wom.ppc.ppc_rules import PPCRuleSet


# ---------------------------------------------------------------------------
# Minimal in-memory rule set: 1 MOM ("Vehicle_Assy"), 2 Tier-1 suppliers
# (Tire priced per-tyre, Battery priced per-pack), 1 product ("EV"), 1 week.
# MOM has both a conversion_cost and a logistics_cost of its own (Step 1c),
# and the Tire->Vehicle_Assy edge has its own logistics_cost (Step 1b) --
# both are needed to prove bom_qty_map leaves them untouched.
# ---------------------------------------------------------------------------

@pytest.fixture
def rules() -> PPCRuleSet:
    supplier_cost = pd.DataFrame([
        {"supplier_node": "Tire", "product_id": "EV", "week": "2026-W01",
         "purchase_price": 80.0, "currency": "USD"},
        {"supplier_node": "Battery", "product_id": "EV", "week": "2026-W01",
         "purchase_price": 6000.0, "currency": "USD"},
    ])
    node_cost_rule = pd.DataFrame([
        {"node_id": "Vehicle_Assy", "product_id": "EV", "cost_type": "conversion_cost",
         "basis": "per_lot", "rate": 0.0, "fixed_amount": 1500.0, "currency": "USD"},
    ])
    edge_cost_rule = pd.DataFrame([
        {"edge_id": "Tire->Vehicle_Assy", "product_id": "EV", "cost_type": "logistics_cost",
         "basis": "per_lot", "rate": 0.0, "fixed_amount": 10.0, "currency": "USD"},
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
        {"week": "2026-W01", "currency": "USD", "base_currency": "USD", "rate": 1.0},
    ])
    node_profit_zone = pd.DataFrame([
        {"node_id": "Tire",          "product_id": "EV", "profit_zone_role": "SUPPLIER", "country": "US"},
        {"node_id": "Battery",       "product_id": "EV", "profit_zone_role": "SUPPLIER", "country": "US"},
        {"node_id": "Vehicle_Assy",  "product_id": "EV", "profit_zone_role": "MOM_PLANT", "country": "US"},
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
    return FXConverter(rules.fx_rate, base_currency="USD")


def _acc(lot_id="L-001") -> LotCostAccumulator:
    return LotCostAccumulator(
        lot_id=lot_id, week="2026-W01", product_id="EV", channel_node="Dealer_Sales",
    )


def _run(rules, fx, acc, bom_qty_map=None):
    return run_forward_propagation(
        [acc], rules, fx, sc_paths={},
        mom_node="Vehicle_Assy",
        supplier_node=["Tire", "Battery"],
        bom_qty_map=bom_qty_map,
    )


class TestBomQtyMapDefault:

    def test_none_map_is_unscaled(self, rules, fx):
        acc = _acc()
        _run(rules, fx, acc, bom_qty_map=None)
        # 80 (Tire) + 6000 (Battery), no scaling
        assert acc.supplier_cost_base == pytest.approx(6080.0, rel=1e-9)

    def test_missing_entry_in_map_defaults_to_1(self, rules, fx):
        acc = _acc()
        # map present but has no entry for either supplier
        _run(rules, fx, acc, bom_qty_map={("EV", "Other"): 4})
        assert acc.supplier_cost_base == pytest.approx(6080.0, rel=1e-9)


class TestBomQtyMapScalesStep1aOnly:

    def test_tire_scaled_by_4_battery_unscaled(self, rules, fx):
        acc = _acc()
        _run(rules, fx, acc, bom_qty_map={("EV", "Tire"): 4})
        # 80*4 (Tire) + 6000 (Battery)
        assert acc.supplier_cost_base == pytest.approx(320.0 + 6000.0, rel=1e-9)

    def test_supplier_cost_event_amount_reflects_scaling(self, rules, fx):
        acc = _acc()
        events = _run(rules, fx, acc, bom_qty_map={("EV", "Tire"): 4})
        tire_ev = next(e for e in events
                        if e.ppc_event_type == "supplier_cost" and e.node_id == "Tire")
        battery_ev = next(e for e in events
                           if e.ppc_event_type == "supplier_cost" and e.node_id == "Battery")
        assert tire_ev.amount_local == pytest.approx(320.0, rel=1e-9)
        assert battery_ev.amount_local == pytest.approx(6000.0, rel=1e-9)

    def test_both_suppliers_scaled_independently(self, rules, fx):
        acc = _acc()
        _run(rules, fx, acc, bom_qty_map={("EV", "Tire"): 4, ("EV", "Battery"): 2})
        assert acc.supplier_cost_base == pytest.approx(80.0 * 4 + 6000.0 * 2, rel=1e-9)

    def test_bom_qty_1_explicit_is_noop(self, rules, fx):
        acc = _acc()
        _run(rules, fx, acc, bom_qty_map={("EV", "Tire"): 1})
        assert acc.supplier_cost_base == pytest.approx(6080.0, rel=1e-9)

    def test_map_keyed_by_wrong_product_id_has_no_effect(self, rules, fx):
        # (product_id, node_id) keying -- an entry for a different product
        # must not leak into this product's scaling.
        acc = _acc()
        _run(rules, fx, acc, bom_qty_map={("OTHER_SKU", "Tire"): 4})
        assert acc.supplier_cost_base == pytest.approx(6080.0, rel=1e-9)


class TestBomQtyMapDoesNotTouchStep1bOr1c:
    """
    Step 1b (edge logistics) and Step 1c (MOM's own node costs) rates are
    already per FINAL ASSEMBLED UNIT -- bom_qty_map must leave them
    completely unscaled, regardless of what it does to Step 1a.
    """

    def test_edge_logistics_cost_unaffected_by_bom_qty(self, rules, fx):
        acc_unscaled = _acc("L-A")
        _run(rules, fx, acc_unscaled, bom_qty_map=None)

        acc_scaled = _acc("L-B")
        _run(rules, fx, acc_scaled, bom_qty_map={("EV", "Tire"): 4})

        assert acc_unscaled.logistics_in_base == pytest.approx(acc_scaled.logistics_in_base, rel=1e-9)
        # sanity: the fixture's edge logistics_cost fixed_amount is $10
        assert acc_unscaled.logistics_in_base == pytest.approx(10.0, rel=1e-9)

    def test_mom_conversion_cost_unaffected_by_bom_qty(self, rules, fx):
        acc_unscaled = _acc("L-A")
        _run(rules, fx, acc_unscaled, bom_qty_map=None)

        acc_scaled = _acc("L-B")
        _run(rules, fx, acc_scaled, bom_qty_map={("EV", "Tire"): 4, ("EV", "Battery"): 4})

        assert acc_unscaled.conversion_cost_base == pytest.approx(acc_scaled.conversion_cost_base, rel=1e-9)
        # sanity: the fixture's MOM conversion_cost fixed_amount is $1500
        assert acc_unscaled.conversion_cost_base == pytest.approx(1500.0, rel=1e-9)

    def test_only_supplier_cost_base_differs_between_scaled_and_unscaled(self, rules, fx):
        acc_unscaled = _acc("L-A")
        _run(rules, fx, acc_unscaled, bom_qty_map=None)

        acc_scaled = _acc("L-B")
        _run(rules, fx, acc_scaled, bom_qty_map={("EV", "Tire"): 4})

        assert acc_scaled.supplier_cost_base != acc_unscaled.supplier_cost_base
        assert acc_scaled.logistics_in_base == acc_unscaled.logistics_in_base
        assert acc_scaled.conversion_cost_base == acc_unscaled.conversion_cost_base
