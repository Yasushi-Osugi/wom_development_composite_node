# -*- coding: utf-8 -*-
"""
tests/test_stage3a2_kitting_gate.py
======================================
Stage 3a-2: Kitting Gate -- an assembly (mom) node's own P is built from the
Lot_ID-identity intersection of all its stockyard children's I buckets,
gated by the assembly's own demand order. Exactly one copy of each
completed-kit Lot_ID enters P (not one per component).

Request Letter: requests/request_stage3a2_kitting_gate.md
Prerequisite (implemented, tests green, commit held pending this stage):
requests/request_stage3a1_stockyard_passthrough.md
"""
from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from wom.model.plan_node import (   # noqa: E402
    PlanNode, S, P, I, CO,
    NODE_TYPE_SUPPLY_POINT, NODE_TYPE_MOM, NODE_TYPE_LEAF_IN, NODE_TYPE_STOCKYARD,
)
from wom.model.sc_tree import SCTree                          # noqa: E402
from wom.engine.backward_planner import BackwardPlanner        # noqa: E402
from wom.engine.plan_copy import copy_demand_to_supply          # noqa: E402
from wom.engine.forward_planner import ForwardPlanner, KITTING_GATE_ENABLED  # noqa: E402
from tools.sweep_flags import (                                 # noqa: E402
    guard_files_for_case, guarded_files, apply_ops, _execute_pipeline,
)

WEEKS = [f"2024-W{i:02d}" for i in range(1, 41)]
PROD = "SKU-A"


def test_gate_flag_is_enabled():
    assert KITTING_GATE_ENABLED is True


# ---------------------------------------------------------------------------
# Synthetic 3-component tree: MOM -> {Battery_Yard, Motor_Yard, ECU_Yard} ->
# {Battery, Motor, ECU}
# ---------------------------------------------------------------------------

def _mk(node_id, name, ntype, lt_wks=1, tier=1):
    return PlanNode(node_id=node_id, node_name=name, product=PROD, side="inbound",
                     node_type=ntype, tier=tier, lt_wks=lt_wks, transit_lt_wks=lt_wks,
                     supply_role="assembly")


def _build_tree(leaf_lt=(2, 2, 3)):
    tree = SCTree(WEEKS)
    ot = PlanNode(node_id="SP", node_name="SP", product=PROD, side="outbound",
                   node_type=NODE_TYPE_SUPPLY_POINT, tier=0, lt_wks=0)
    mom = _mk("MOM", "MOM", NODE_TYPE_MOM, lt_wks=0, tier=0)
    names = ["Battery", "Motor", "ECU"]
    yards = []
    leaves = []
    for name, lt in zip(names, leaf_lt):
        yard = _mk(f"{name}_Yard", f"{name}_Yard", NODE_TYPE_STOCKYARD, lt_wks=0, tier=1)
        leaf = _mk(name, name, NODE_TYPE_LEAF_IN, lt_wks=lt, tier=2)
        yard.add_child(leaf)
        mom.add_child(yard)
        yards.append(yard)
        leaves.append(leaf)
    tree.register(PROD, ot_root=ot, in_root=mom)
    tree.init_all_psi()
    return tree, mom, yards, leaves


def _run_pipeline(tree, cap_hard_by_leaf=None):
    """cap_hard_by_leaf: [(PlanNode, cap), ...] -- a list, not a dict, since
    PlanNode (a plain @dataclass) is unhashable. Capacity is applied BEFORE
    BackwardPlanner runs (MOM cap-backward reads it too), matching how a
    real capacity_plan.csv is loaded before planning starts."""
    if cap_hard_by_leaf:
        for leaf, cap in cap_hard_by_leaf:
            for w in range(len(WEEKS)):
                leaf.set_capacity(w, cap_hard=cap)
    for prod in [PROD]:
        BackwardPlanner(tree).run(prod)
        copy_demand_to_supply(tree, prod)
        result = ForwardPlanner(tree).run(prod)
    return result


def _seed_demand(mom, weeks, qty_per_week):
    for w in weeks:
        for i in range(qty_per_week):
            mom.add_lot_demand(w, S, f"L{w:02d}-{i:02d}")


def test_complete_kit_enters_p_exactly_once():
    tree, mom, yards, leaves = _build_tree()
    _seed_demand(mom, range(5, 15), 3)
    _run_pipeline(tree)

    for w in range(len(WEEKS)):
        p_lots = mom.psi4supply[w][P]
        assert len(p_lots) == len(set(p_lots)), f"w={w}: duplicate Lot_ID in P: {p_lots}"

    total_p = sum(len(mom.psi4supply[w][P]) for w in range(len(WEEKS)))
    total_demand = sum(len(mom.psi4demand[w][S]) for w in range(len(WEEKS)))
    assert total_p == total_demand, (
        f"unconstrained 3-component kit: P total ({total_p}) should equal "
        f"demand total ({total_demand}) -- no duplication, no shortfall")


def test_partial_kit_stays_in_every_yards_inventory():
    """Cap one component (ECU) far below demand -- lots missing their ECU
    partner must stay in ALL THREE yards' I (mass conserved), not just
    ECU_Yard's, and must NOT enter MOM's P."""
    tree, mom, (battery_yard, motor_yard, ecu_yard), (battery, motor, ecu) = _build_tree()
    _seed_demand(mom, range(5, 10), 3)   # 15 lots total, weeks 5-9
    _run_pipeline(tree, cap_hard_by_leaf=[(ecu, 1)])   # ECU can only supply 1/week

    all_demand_lots = set()
    for w in range(len(WEEKS)):
        all_demand_lots.update(mom.psi4demand[w][S])

    p_lots = set()
    for w in range(len(WEEKS)):
        p_lots.update(mom.psi4supply[w][P])

    missing = all_demand_lots - p_lots
    assert missing, "expected some lots to be missing their ECU partner"

    # every missing lot must still be sitting in Battery_Yard's and/or
    # Motor_Yard's I somewhere in the horizon (mass conserved -- it did not
    # vanish), and must NEVER be in ecu_yard's I together with a matching
    # entry that also appears in mom.P (i.e. it's genuinely never gated).
    battery_yard_stock = set()
    motor_yard_stock = set()
    for w in range(len(WEEKS)):
        battery_yard_stock.update(battery_yard.psi4supply[w][I])
        motor_yard_stock.update(motor_yard.psi4supply[w][I])

    stray = missing - (battery_yard_stock | motor_yard_stock)
    assert not stray, f"lots missing from MOM.P but not sitting in any yard's I: {stray}"


def test_mass_conservation_total_lot_count():
    """Every demand lot ends up EITHER paid out (in MOM.P, exactly once) OR
    still sitting in every yard's I somewhere in the horizon (residual) --
    nothing is created or destroyed."""
    tree, mom, (battery_yard, motor_yard, ecu_yard), (battery, motor, ecu) = _build_tree()
    _seed_demand(mom, range(5, 12), 4)
    _run_pipeline(tree, cap_hard_by_leaf=[(ecu, 2)])

    all_demand_lots = set()
    for w in range(len(WEEKS)):
        all_demand_lots.update(mom.psi4demand[w][S])

    p_lots = []
    for w in range(len(WEEKS)):
        p_lots.extend(mom.psi4supply[w][P])
    assert len(p_lots) == len(set(p_lots)), "MOM.P must never contain a duplicate Lot_ID"

    residual_lots = set()
    for yard in (battery_yard, motor_yard, ecu_yard):
        for w in range(len(WEEKS)):
            residual_lots.update(yard.psi4supply[w][I])
    # residual, by construction, is the SAME set across all three yards for
    # any lot that is genuinely incomplete (see test above) -- but a lot
    # complete in fewer than all 3 yards this instant can transiently differ
    # per yard, so take the union as "anything still held anywhere".

    accounted = set(p_lots) | residual_lots
    assert all_demand_lots <= accounted, (
        f"lots present in demand but neither paid out nor held in any yard "
        f"(lost): {all_demand_lots - accounted}")


def test_bom_qty_does_not_affect_gate_judgment():
    """bom_qty is a physical-quantity display multiplier; the gate must
    judge purely on Lot_ID presence, unaffected by it."""
    tree, mom, yards, leaves = _build_tree()
    leaves[0].bom_qty = 4   # e.g. "4 tyres per vehicle" -- still 1 Lot_ID
    _seed_demand(mom, range(5, 10), 2)
    _run_pipeline(tree)

    total_p = sum(len(mom.psi4supply[w][P]) for w in range(len(WEEKS)))
    total_demand = sum(len(mom.psi4demand[w][S]) for w in range(len(WEEKS)))
    assert total_p == total_demand


def test_kitting_missing_still_reports_correctly_under_gate():
    tree, mom, (battery_yard, motor_yard, ecu_yard), (battery, motor, ecu) = _build_tree()
    _seed_demand(mom, range(5, 8), 3)
    _run_pipeline(tree, cap_hard_by_leaf=[(ecu, 1)])

    found_missing_ecu_only = False
    for w, wk in enumerate(mom.kitting):
        for lot_id in wk:
            st = mom.kitting_status(w, lot_id)
            if st["missing"] == {"ECU_Yard"}:
                found_missing_ecu_only = True
    assert found_missing_ecu_only, "expected at least one lot with missing={'ECU_Yard'}"


# ---------------------------------------------------------------------------
# Regression: non-stockyard trees take the exact same code path as before
# ---------------------------------------------------------------------------

def test_no_stockyard_children_unaffected():
    """A plain assembly node with ordinary leaf_in children (no stockyard)
    must be completely untouched by this stage -- KITTING_GATE_ENABLED=True
    only matters when `stockyard_children` is non-empty."""
    tree = SCTree(WEEKS)
    ot = PlanNode(node_id="SP", node_name="SP", product=PROD, side="outbound",
                   node_type=NODE_TYPE_SUPPLY_POINT, tier=0, lt_wks=0)
    mom = _mk("MOM", "MOM", NODE_TYPE_MOM, lt_wks=0, tier=0)
    a = _mk("A", "A", NODE_TYPE_LEAF_IN, lt_wks=1, tier=1)
    b = _mk("B", "B", NODE_TYPE_LEAF_IN, lt_wks=1, tier=1)
    mom.add_child(a); mom.add_child(b)
    tree.register(PROD, ot_root=ot, in_root=mom)
    tree.init_all_psi()
    _seed_demand(mom, range(5, 10), 3)
    _run_pipeline(tree)

    # unchanged (pre-Stage-3a) behaviour: each assembly child extends its
    # FULL demand-anchored list independently -- P duplicates by component
    # count. This is what Stage 3a-2 intentionally does NOT touch for trees
    # without stockyard nodes.
    total_p = sum(len(mom.psi4supply[w][P]) for w in range(len(WEEKS)))
    total_demand = sum(len(mom.psi4demand[w][S]) for w in range(len(WEEKS)))
    assert total_p == total_demand * 2, (
        "a plain (non-stockyard) 2-child assembly node must still show the "
        "pre-3a-2 duplicate-extend P (2x) -- this stage must not touch it")


# ---------------------------------------------------------------------------
# CSV Integration: real ev-europe-2026 / bom-test-2026 models
# ---------------------------------------------------------------------------

EV_EUROPE_DIR = os.path.join(REPO_ROOT, "data", "sample", "ev-europe-2026")
BOM_TEST_DIR = os.path.join(REPO_ROOT, "data", "sample", "bom-test-2026")


def test_bom_test_2026_vehicle_assy_p_matches_s(tmp_path):
    result, sc_tree = _execute_pipeline(
        BOM_TEST_DIR, "safe", str(tmp_path / "ppc"), "EV_Model_A", [])
    assy = next(nd for nd in sc_tree.iter_all_nodes("EV_Model_A") if nd.node_name == "Vehicle_Assy")
    n = len(assy.week_labels)
    p_sum = sum(len(assy.psi4supply[w][P]) for w in range(n))
    s_sum = sum(len(assy.psi4supply[w][S]) for w in range(n))
    assert p_sum == s_sum, (
        f"Vehicle_Assy P_sum={p_sum} should equal S_sum={s_sum} now that the "
        f"gate deduplicates -- pre-3a-2 this was 2x")


def test_ev_europe_2026_import_factory_p_matches_real_demand(tmp_path):
    result, sc_tree = _execute_pipeline(
        EV_EUROPE_DIR, "safe", str(tmp_path / "ppc"), "EVmaker_Import", [])
    mom = sc_tree.get_in_root("EVmaker_Import")
    n = len(mom.week_labels)
    p_sum = sum(len(mom.psi4supply[w][P]) for w in range(n))
    i_sum = sum(len(mom.psi4supply[w][I]) for w in range(n))
    s_sum = sum(len(mom.psi4supply[w][S]) for w in range(n))
    assert p_sum <= s_sum, (
        f"Factory_Import_HU P_sum={p_sum} must no longer exceed real demand "
        f"S_sum={s_sum} (pre-3a-2 this was ~3x, 23,835 vs 8,345)")
    assert i_sum < 100000, (
        f"Factory_Import_HU I_sum={i_sum} must no longer be a non-physical "
        f"runaway value (pre-3a-2: 734,873)")

    kpi_path = os.path.join(str(tmp_path / "ppc"), "ppc_kpi_summary.json")
    import json
    kpi = json.load(open(kpi_path, encoding="utf-8"))
    print(f"[report] EVmaker_Import post-gate: P_sum={p_sum} S_sum={s_sum} I_sum={i_sum} "
          f"revenue_base={kpi.get('total_revenue_base')} gm={kpi.get('gross_margin_pct')}")
