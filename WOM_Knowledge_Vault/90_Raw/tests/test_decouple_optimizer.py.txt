"""
tests/test_decouple_optimizer.py
Buffering stock placement optimizer (wom/engine/decouple_optimizer.py)
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from wom.model.sc_tree       import build_demo_sc_tree
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner
from wom.engine.sc_tree_builder   import build_sc_tree_from_master
from wom.engine.decouple_optimizer import (
    build_decouple_candidates,
    evaluate_decouple_placement,
    find_optimal_decouple_placement,
)


def get_node(sc_tree, prod_nm, node_id):
    for node in sc_tree.iter_all_nodes(prod_nm):
        if node.node_id == node_id:
            return node
    raise ValueError(f"{node_id!r} not found")


def _build_single_lane(ss_days_dad=0, ss_days_leaf=0):
    """
    supply_point -> DAD(JP) -> leaf_out(JP), single SKU/region.
    Mirrors tests/test_step8_push_pull.py's build_base() helper.
    """
    sku_id = "SKU-A"
    n_weeks = 26
    weeks = [f"2024-W{i:02d}" for i in range(1, n_weeks + 1)]
    rows = [{"sku_id": sku_id, "sku_name": "A", "region": "JP", "lead_time_wks": 1}]
    sc_tree = build_demo_sc_tree(pd.DataFrame(rows), weeks, lt_wks_ot=1, lt_wks_in=2)

    dad  = get_node(sc_tree, sku_id, f"OUT:DC:JP:{sku_id}")
    leaf = get_node(sc_tree, sku_id, f"OUT:Sales:JP:{sku_id}")
    dad.ss_days  = ss_days_dad
    leaf.ss_days = ss_days_leaf

    demand_dict = {(sku_id, "JP", "2024-W15"): 6}
    assign_demand_lots_from_dict(sc_tree, demand_dict, cpu_size=1)
    BackwardPlanner(sc_tree).run(sku_id)
    return sc_tree, sku_id, dad, leaf


# ---------------------------------------------------------------------------
# 1. Candidate generation
# ---------------------------------------------------------------------------

def test_build_decouple_candidates_excludes_supply_point():
    sc_tree, sku_id, dad, leaf = _build_single_lane()
    ot_root = sc_tree.get_ot_root(sku_id)
    candidates = build_decouple_candidates(ot_root)

    # Finest (leaf_out alone) -> coarsest (DAD, directly below supply_point).
    assert candidates == [[leaf.node_id], [dad.node_id]]

    # supply_point itself must never appear in any candidate.
    sp_id = ot_root.node_id
    for cand in candidates:
        assert sp_id not in cand
    print("PASS: test_build_decouple_candidates_excludes_supply_point")


# ---------------------------------------------------------------------------
# 2. Evaluation arithmetic: I only accumulates where the ss_days-configured
#    node is NOT pull-mode-overridden (i.e. at/above the chosen decouple
#    point), and inventory cost = sum(lots_at_node * unit_cost[node]).
# ---------------------------------------------------------------------------

def test_evaluate_decouple_placement_ss_days_only_visible_when_not_pulled():
    # ss_days configured on leaf_out only. Choosing DAD as the decouple
    # point forces leaf_out into PULL mode (P overwritten with its own
    # demand.P), which discards leaf_out's ss_days-driven early-arrival
    # signal entirely -> DAD-decouple should show zero inventory anywhere.
    # Choosing leaf_out itself as decouple point keeps its own ss_days
    # signal intact -> nonzero inventory at leaf_out.
    sc_tree, sku_id, dad, leaf = _build_single_lane(ss_days_dad=0, ss_days_leaf=14)

    cost_lookup = {dad.node_name: 5.0, leaf.node_name: 5.0}

    dad_result  = evaluate_decouple_placement(sc_tree, sku_id, [dad.node_id],  cost_lookup)
    leaf_result = evaluate_decouple_placement(sc_tree, sku_id, [leaf.node_id], cost_lookup)

    assert dad_result.total_inventory_lots == 0
    assert dad_result.total_inventory_cost == 0
    assert dad_result.total_shortfall_lots == 0

    assert leaf_result.total_inventory_lots > 0
    assert leaf_result.per_node_inventory == {leaf.node_name: leaf_result.total_inventory_lots}
    assert leaf_result.total_inventory_cost == leaf_result.total_inventory_lots * 5.0
    assert leaf_result.total_shortfall_lots == 0
    print("PASS: test_evaluate_decouple_placement_ss_days_only_visible_when_not_pulled")


# ---------------------------------------------------------------------------
# 3. find_optimal_decouple_placement: service-level-constrained ranking,
#    verified against the real Cookie-jp-2026 sample model (both SKUs have
#    a genuine capacity constraint upstream, so candidates differ in both
#    shortfall and inventory cost -- this is the scenario the service-level
#    constraint exists to handle correctly).
# ---------------------------------------------------------------------------

_COOKIE_MODEL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "data", "sample", "Cookie-jp-2026")


def _load_cookie_sc_tree():
    weeks = [f"2026-W{i:02d}" for i in range(1, 53)]
    sc_df = pd.read_csv(os.path.join(_COOKIE_MODEL_DIR, "sc_tree_master.csv"))
    sc_tree = build_sc_tree_from_master(sc_df, weeks)

    dem_df = pd.read_csv(os.path.join(_COOKIE_MODEL_DIR, "demand_forecast.csv"))
    demand_dict = {}
    for _, row in dem_df.iterrows():
        key = (str(row["sku_id"]), str(row["region"]), str(row["week"]))
        demand_dict[key] = demand_dict.get(key, 0) + int(row["quantity"])
    assign_demand_lots_from_dict(sc_tree, demand_dict, cpu_size=1)

    for prod in sc_tree.products:
        BackwardPlanner(sc_tree).run(prod)
    return sc_tree


def test_find_optimal_decouple_placement_cookie_import():
    sc_tree = _load_cookie_sc_tree()
    result = find_optimal_decouple_placement(
        sc_tree, "Cookie_Import",
        node_cost_master_path=os.path.join(_COOKIE_MODEL_DIR, "node_cost_master.csv"),
    )

    # supply_point never a candidate.
    for e in result["ranked"]:
        assert "SP_Cookie_Import" not in e.decouple_node_names

    assert result["best"] is not None
    assert result["best"].decouple_node_names == ["DC_Import_Buffer"]
    # DC_Import_Buffer is also the min-shortfall candidate, so it's
    # eligible under the service-level constraint (not just cost-cheapest).
    assert result["best"] in result["eligible"]
    assert result["best"].total_shortfall_lots == result["min_shortfall"]
    print("PASS: test_find_optimal_decouple_placement_cookie_import")


def test_find_optimal_decouple_placement_cookie_local():
    sc_tree = _load_cookie_sc_tree()
    result = find_optimal_decouple_placement(
        sc_tree, "Cookie_Local",
        node_cost_master_path=os.path.join(_COOKIE_MODEL_DIR, "node_cost_master.csv"),
    )

    assert result["best"] is not None
    assert result["best"].decouple_node_names == ["DC_Local_JP"]
    assert result["best"] in result["eligible"]
    print("PASS: test_find_optimal_decouple_placement_cookie_local")
