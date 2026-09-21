# -*- coding: utf-8 -*-
"""
tests/test_cpu_size_plan_wide.py
===================================
Regression test for Request Letter A (request_letter_a_cpu_size_to_plan.md):
`cpu_size` moved from a per-node PlanNode field to a plan-wide SCTree
attribute, read from planning_config.csv's `cpu_size` key (default 1).

This Letter is a pure refactor -- it does not implement BOM quantity N
("1 set rule", Letter B). Lot generation is untouched; only the KPI/display
conversion layer (sc_tree_to_df.py, GUI chart panels) reads the new
plan-wide value.
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pandas as pd  # noqa: E402

from wom.model.plan_node import PlanNode, NODE_TYPE_MOM  # noqa: E402
from wom.model.sc_tree import SCTree, build_demo_sc_tree  # noqa: E402
from wom.engine.sc_tree_builder import build_sc_tree_from_master  # noqa: E402
from wom.engine.warmup import read_cpu_size  # noqa: E402
from wom.engine.sc_tree_to_df import sc_tree_to_planning_df  # noqa: E402

WEEKS = [f"2024-W{i:02d}" for i in range(1, 6)]
PROD = "SKU-A"


# ---------------------------------------------------------------------------
# planning_config.csv reading / default
# ---------------------------------------------------------------------------

def test_read_cpu_size_from_planning_config(tmp_path):
    (tmp_path / "planning_config.csv").write_text(
        "key,value\nwarmup_lt,52\nplanning_start,\ncpu_size,12\n", encoding="utf-8")
    assert read_cpu_size(str(tmp_path)) == 12


def test_read_cpu_size_defaults_to_1_when_key_missing(tmp_path):
    (tmp_path / "planning_config.csv").write_text(
        "key,value\nwarmup_lt,52\nplanning_start,\n", encoding="utf-8")
    assert read_cpu_size(str(tmp_path)) == 1


def test_read_cpu_size_defaults_to_1_when_file_missing(tmp_path):
    assert read_cpu_size(str(tmp_path)) == 1


# ---------------------------------------------------------------------------
# SCTree.cpu_size always present
# ---------------------------------------------------------------------------

def test_sctree_cpu_size_defaults_to_1():
    tree = SCTree(WEEKS)
    assert tree.cpu_size == 1


def test_sctree_cpu_size_settable():
    tree = SCTree(WEEKS)
    tree.cpu_size = 12
    assert tree.cpu_size == 12


def test_build_sc_tree_from_master_leaves_cpu_size_at_default():
    df = pd.DataFrame([
        {"node_name": "SP", "parent_node": "", "product_name": PROD,
         "node_type": "supply_point", "side": "outbound", "lt_wks": 0},
        {"node_name": "MOM", "parent_node": "", "product_name": PROD,
         "node_type": "mom", "side": "inbound", "lt_wks": 1},
    ])
    tree = build_sc_tree_from_master(df, WEEKS)
    assert tree.cpu_size == 1  # nothing sets it here -- the pipeline entry
                               # point (app.py / headless / sweep_flags) does


def test_build_demo_sc_tree_sets_tree_cpu_size_not_per_node():
    sku_df = pd.DataFrame([
        {"sku_id": PROD, "sku_name": "A", "region": "JP", "lead_time_wks": 1},
    ])
    tree = build_demo_sc_tree(sku_df, WEEKS, cpu_size=12)
    assert tree.cpu_size == 12


# ---------------------------------------------------------------------------
# PlanNode no longer has a cpu_size attribute
# ---------------------------------------------------------------------------

def test_plan_node_has_no_cpu_size_attribute():
    node = PlanNode(node_id="X", node_name="X", product=PROD, side="inbound",
                     node_type=NODE_TYPE_MOM, tier=0)
    assert not hasattr(node, "cpu_size")


def test_plan_node_rejects_cpu_size_kwarg():
    import pytest
    with pytest.raises(TypeError):
        PlanNode(node_id="X", node_name="X", product=PROD, side="inbound",
                 node_type=NODE_TYPE_MOM, tier=0, cpu_size=12)


# ---------------------------------------------------------------------------
# sc_tree_to_planning_df uses the plan-wide value
# ---------------------------------------------------------------------------

def _demo_tree_with_demand(cpu_size: int):
    sku_df = pd.DataFrame([
        {"sku_id": PROD, "sku_name": "A", "region": "JP", "lead_time_wks": 1},
    ])
    tree = build_demo_sc_tree(sku_df, WEEKS, cpu_size=cpu_size)
    leaf = next(nd for nd in tree.get_ot_root(PROD).walk_preorder()
                if not nd.children)
    from wom.model.plan_node import S, P
    for w in range(len(WEEKS)):
        for lot in [f"L{w}-{i}" for i in range(3)]:
            leaf.psi4demand[w][S].append(lot)
            leaf.psi4supply[w][S].append(lot)
            leaf.psi4supply[w][P].append(lot)
    return tree


def test_kpi_dataframe_uses_plan_wide_cpu_size():
    tree1 = _demo_tree_with_demand(cpu_size=1)
    df1 = sc_tree_to_planning_df(tree1)
    tree12 = _demo_tree_with_demand(cpu_size=12)
    df12 = sc_tree_to_planning_df(tree12)

    # same lot count (3 lots/week) but cpu_size=12 -> quantity is 12x
    assert (df12["demand_fcst"] == df1["demand_fcst"] * 12).all()
    assert (df12["demand_fulfilled"] == df1["demand_fulfilled"] * 12).all()
    assert (df12["supply_receipt"] == df1["supply_receipt"] * 12).all()
