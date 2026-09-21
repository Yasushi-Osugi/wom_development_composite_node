# -*- coding: utf-8 -*-
"""
tests/test_bom_qty.py
=======================
Unit tests for Request Letter B (requests/request_letter_b_bom_qty.md):
per-node BOM quantity N ("1 set rule").

Design principle (Letter B section 2, "MOST IMPORTANT"): N must NEVER touch
the Lot_ID list. The Planning Engine (backward_planner.py / forward_planner.py
/ push_pull.py / plan_copy.py / sc_tree.py) stays completely unaware of it;
N only scales the *interpretation* of a lot count downstream, per
    S_Qty[w] = len(psi[w]["S"]) x cpu_size x bom_qty

bom_qty is a per-node PlanNode attribute -- distinct from Letter A's cpu_size,
which is a plan-wide SCTree attribute (see test_cpu_size_plan_wide.py).
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from wom.model.plan_node import PlanNode, NODE_TYPE_MOM  # noqa: E402
from wom.model.sc_tree import SCTree, build_demo_sc_tree  # noqa: E402
from wom.engine.sc_tree_builder import (  # noqa: E402
    build_sc_tree_from_master, _parse_bom_qty,
)
from wom.engine.sc_tree_to_df import sc_tree_to_planning_df  # noqa: E402

WEEKS = [f"2024-W{i:02d}" for i in range(1, 6)]
PROD = "SKU-A"


# ---------------------------------------------------------------------------
# _parse_bom_qty: invalid-input behaviour (Letter B section 9.1 requirement:
# "define and test" what happens for 0 / negative / decimal / string)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("4",      4),
    ("1",      1),
    ("12",     12),
    ("",       1),      # blank -> default
    (None,     1),      # missing -> default
    ("0",      1),      # zero -> invalid, default
    ("-1",     1),      # negative -> invalid, default
    ("2.5",    1),      # non-integer -> invalid, default
    ("abc",    1),      # non-numeric -> invalid, default
    ("nan",    1),      # pandas-empty-cell sentinel -> default
    ("  4  ",  4),      # whitespace tolerated
    ("4.0",    4),      # integer-valued float string -> accepted as 4
])
def test_parse_bom_qty(raw, expected):
    assert _parse_bom_qty(raw) == expected


# ---------------------------------------------------------------------------
# sc_tree_master.csv -> PlanNode.bom_qty wiring
# ---------------------------------------------------------------------------

def _tire_battery_df(tire_bom_qty="4", battery_bom_qty="1",
                      tire_role="", battery_role=""):
    return pd.DataFrame([
        {"node_name": "SP", "parent_node": "", "product_name": PROD,
         "node_type": "supply_point", "side": "outbound", "lt_wks": 0},
        {"node_name": "DC", "parent_node": "SP", "product_name": PROD,
         "node_type": "dad", "side": "outbound", "lt_wks": 1, "region": "US"},
        {"node_name": "Retail", "parent_node": "DC", "product_name": PROD,
         "node_type": "leaf_out", "side": "outbound", "lt_wks": 1, "region": "US"},
        {"node_name": "Assy", "parent_node": "", "product_name": PROD,
         "node_type": "mom", "side": "inbound", "lt_wks": 0},
        {"node_name": "Tire", "parent_node": "Assy", "product_name": PROD,
         "node_type": "leaf_in", "side": "inbound", "lt_wks": 1,
         "supply_role": tire_role, "bom_qty": tire_bom_qty},
        {"node_name": "Battery", "parent_node": "Assy", "product_name": PROD,
         "node_type": "leaf_in", "side": "inbound", "lt_wks": 1,
         "supply_role": battery_role, "bom_qty": battery_bom_qty},
    ])


def _build(df):
    tree = build_sc_tree_from_master(df, WEEKS)
    in_root = tree.get_in_root(PROD)
    nodes = {nd.node_name: nd for nd in in_root.walk_preorder()}
    return tree, nodes


def test_bom_qty_read_and_stored_on_plan_node():
    _, nodes = _build(_tire_battery_df(tire_bom_qty="4", battery_bom_qty="1"))
    assert nodes["Tire"].bom_qty == 4
    assert nodes["Battery"].bom_qty == 1


def test_bom_qty_blank_defaults_to_1():
    _, nodes = _build(_tire_battery_df(tire_bom_qty="", battery_bom_qty="1"))
    assert nodes["Tire"].bom_qty == 1


def test_bom_qty_missing_column_defaults_to_1():
    df = _tire_battery_df()
    df = df.drop(columns=["bom_qty"])
    _, nodes = _build(df)
    assert nodes["Tire"].bom_qty == 1
    assert nodes["Battery"].bom_qty == 1


@pytest.mark.parametrize("bad_value", ["0", "-2", "2.5", "xyz"])
def test_bom_qty_invalid_values_default_to_1(bad_value):
    _, nodes = _build(_tire_battery_df(tire_bom_qty=bad_value))
    assert nodes["Tire"].bom_qty == 1


def test_bom_qty_confluence_children_forced_to_1():
    # supply_role=confluence siblings SPLIT demand rather than multiply it,
    # so bom_qty must be forced to 1 regardless of the CSV value
    # (request_fix_a1_supply_role_rev2.md section 3.2).
    _, nodes = _build(_tire_battery_df(tire_bom_qty="4", tire_role="confluence"))
    assert nodes["Tire"].supply_role == "confluence"
    assert nodes["Tire"].bom_qty == 1


def test_bom_qty_assembly_children_keep_declared_value():
    _, nodes = _build(_tire_battery_df(tire_bom_qty="4", tire_role="assembly"))
    assert nodes["Tire"].supply_role == "assembly"
    assert nodes["Tire"].bom_qty == 4


def test_bom_qty_default_role_is_assembly_and_keeps_value():
    # supply_role left blank -> defaults to "assembly" (A1 fix), bom_qty kept
    _, nodes = _build(_tire_battery_df(tire_bom_qty="4", tire_role=""))
    assert nodes["Tire"].supply_role == "assembly"
    assert nodes["Tire"].bom_qty == 4


# ---------------------------------------------------------------------------
# bom_qty is a PlanNode attribute, NOT an SCTree attribute
# (distinct storage from Letter A's plan-wide cpu_size -- must not be
# confused / merged with SCTree.cpu_size)
# ---------------------------------------------------------------------------

def test_bom_qty_is_plan_node_attribute_not_sctree():
    tree = SCTree(WEEKS)
    assert not hasattr(tree, "bom_qty")
    node = PlanNode(node_id="X", node_name="X", product=PROD, side="inbound",
                     node_type=NODE_TYPE_MOM, tier=0)
    assert hasattr(node, "bom_qty")
    assert node.bom_qty == 1  # default


def test_bom_qty_default_is_1_for_plain_plan_node():
    node = PlanNode(node_id="X", node_name="X", product=PROD, side="inbound",
                     node_type=NODE_TYPE_MOM, tier=0)
    assert node.bom_qty == 1


def test_bom_qty_settable_independent_of_cpu_size():
    tree = SCTree(WEEKS)
    tree.cpu_size = 12
    node = PlanNode(node_id="X", node_name="X", product=PROD, side="inbound",
                     node_type=NODE_TYPE_MOM, tier=0, bom_qty=4)
    # cpu_size lives on the tree, bom_qty lives on the node -- independent
    assert tree.cpu_size == 12
    assert node.bom_qty == 4


# ---------------------------------------------------------------------------
# sc_tree_to_planning_df: quantity = len(lots) x cpu_size x bom_qty
# ---------------------------------------------------------------------------

def _demo_tree_with_demand(cpu_size: int, bom_qty: int = 1):
    sku_df = pd.DataFrame([
        {"sku_id": PROD, "sku_name": "A", "region": "JP", "lead_time_wks": 1},
    ])
    tree = build_demo_sc_tree(sku_df, WEEKS, cpu_size=cpu_size)
    leaf = next(nd for nd in tree.get_ot_root(PROD).walk_preorder()
                if not nd.children)
    leaf.bom_qty = bom_qty
    from wom.model.plan_node import S, P
    for w in range(len(WEEKS)):
        for lot in [f"L{w}-{i}" for i in range(3)]:
            leaf.psi4demand[w][S].append(lot)
            leaf.psi4supply[w][S].append(lot)
            leaf.psi4supply[w][P].append(lot)
    return tree


def _leaf_out_rows(df):
    # sc_tree_to_planning_df also emits DAD rows (region prefixed "DAD:")
    # that this synthetic tree leaves unpopulated (all zero) -- restrict
    # assertions to the leaf_out rows actually exercised by the test.
    return df[~df["region"].astype(str).str.startswith("DAD:")]


def test_kpi_dataframe_bom_qty_1_is_unchanged_from_letter_a():
    # bom_qty=1 (default) must reproduce Letter A's exact behaviour
    # (regression guard against Letter B breaking Letter A).
    df = _leaf_out_rows(
        sc_tree_to_planning_df(_demo_tree_with_demand(cpu_size=12, bom_qty=1)))
    # 3 lots/week x cpu_size(12) x bom_qty(1) = 36
    assert (df["demand_fcst"] == 36).all()


def test_kpi_dataframe_scales_leaf_out_by_bom_qty():
    df1 = sc_tree_to_planning_df(_demo_tree_with_demand(cpu_size=1, bom_qty=1))
    df4 = sc_tree_to_planning_df(_demo_tree_with_demand(cpu_size=1, bom_qty=4))
    # same lot count (3 lots/week) but bom_qty=4 -> quantity is 4x
    assert (df4["demand_fcst"] == df1["demand_fcst"] * 4).all()
    assert (df4["demand_fulfilled"] == df1["demand_fulfilled"] * 4).all()
    assert (df4["supply_receipt"] == df1["supply_receipt"] * 4).all()


def test_kpi_dataframe_cpu_size_and_bom_qty_compound():
    # cpu_size=12 x bom_qty=4 = 48x multiplier on lot count (3/week)
    df = _leaf_out_rows(
        sc_tree_to_planning_df(_demo_tree_with_demand(cpu_size=12, bom_qty=4)))
    assert (df["demand_fcst"] == 3 * 12 * 4).all()
