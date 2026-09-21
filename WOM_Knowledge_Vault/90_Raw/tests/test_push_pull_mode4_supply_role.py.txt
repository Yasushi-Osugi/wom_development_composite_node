# -*- coding: utf-8 -*-
"""
tests/test_push_pull_mode4_supply_role.py
============================================
Regression test for Mode4 (LT-shifted PUSH) ignoring `supply_role` recipient
membership decided by BackwardPlanner.

Request Letter: requests/request_fix_mode4_supply_role_semantics.md
Prior investigation: requests/request_fix_mode4_supply_role.md
Discovered via: requests/request_kitting_stage1.md (Kitting Stage 1, 45d6eac)

Canonical rule this test enforces
----------------------------------
    Backward Planner determines WHO supplies each Demand Anchored Lot.
    Mode4 determines WHEN those already-assigned suppliers produce it.

Root cause (pre-fix)
---------------------
`PushProductionPlanner.setup()`'s Mode4 branch (`is_lt_shifted_mode()`) took
`decoupling_node.walk_preorder()`'s leaf_in nodes and re-allocated the
reference week's demand lots into disjoint contiguous 1/n slices --
appropriate for `confluence` siblings, wrong for `assembly` siblings (each of
which BackwardPlanner already gave the FULL demand-lot list, per
`request_fix_a1_supply_role_rev2.md`). Measured on ev-europe-2026 /
Factory_Import_HU (Battery_HU / Motor_HU / ECU_HU, all default/assembly):
Kitting Stage 1 showed `complete = 0 / 7,945` -- every lot missing exactly
2 of its 3 required components, because each component only ever received
~1/3 of the lots it was actually responsible for.

Fix
---
Mode4 no longer re-derives WHO. It reads each leaf_in's own
horizon-wide `psi4demand[*][S]` (BackwardPlanner's already-decided
recipient membership -- confluence siblings hold a disjoint subset,
assembly siblings each hold the full set) and uses it purely as a filter
on WHEN to produce, preserving `future_lots` order. No second
`supply_role` router is added in push_pull.py -- the branching already
happened in BackwardPlanner and is read back here as a fact, not
recomputed as a policy.
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from wom.model.plan_node import (   # noqa: E402
    PlanNode, S, P,
    NODE_TYPE_SUPPLY_POINT, NODE_TYPE_MOM, NODE_TYPE_LEAF_IN,
)
from wom.model.sc_tree import SCTree                      # noqa: E402
from wom.engine.push_pull import PushConfig, PushProductionPlanner  # noqa: E402

WEEKS = [f"2024-W{i:02d}" for i in range(1, 31)]  # 30-week horizon
PROD  = "SKU-A"


# ---------------------------------------------------------------------------
# Tree builders
# ---------------------------------------------------------------------------

def _mk_node(node_id, name, node_type, lt_wks=1, supply_role="assembly", tier=1):
    return PlanNode(
        node_id=node_id, node_name=name, product=PROD, side="inbound",
        node_type=node_type, tier=tier, lt_wks=lt_wks, transit_lt_wks=lt_wks,
        supply_role=supply_role,
    )


def _build_flat_tree(children_specs, decoupling_lt_wks=0):
    """
    One MOM decoupling root ("MOM") with flat children, one per
    (name, supply_role, lt_wks) tuple in `children_specs`.
    A trivial childless OutBound supply_point root is registered too
    (SCTree.register() requires one; PushProductionPlanner never touches it).
    """
    tree = SCTree(WEEKS)
    ot_root = PlanNode(
        node_id="SP:" + PROD, node_name="SP", product=PROD,
        side="outbound", node_type=NODE_TYPE_SUPPLY_POINT, tier=0, lt_wks=0,
    )
    mom = _mk_node("MOM:" + PROD, "MOM", NODE_TYPE_MOM, lt_wks=decoupling_lt_wks, tier=0)
    children = []
    for name, role, lt in children_specs:
        child = _mk_node(f"{name}:{PROD}", name, NODE_TYPE_LEAF_IN, lt_wks=lt, supply_role=role)
        mom.add_child(child)
        children.append(child)
    tree.register(PROD, ot_root=ot_root, in_root=mom)
    tree.init_all_psi()
    return tree, mom, children


def _build_mixed_tree():
    """
    Final_Assy (MOM, decoupling)
      +-- Component_X (mom, intermediate -- NOT itself leaf_in)
      |     +-- Supplier_X1 (leaf_in, confluence)
      |     +-- Supplier_X2 (leaf_in, confluence)
      +-- Component_Y_leaf (leaf_in, assembly)
      +-- Component_Z_leaf (leaf_in, assembly)

    Mirrors Letter U3: Mode4 must use each FINAL leaf's own horizon-wide
    membership, without needing to know about the intermediate mom node or
    re-derive tree semantics itself.
    """
    tree = SCTree(WEEKS)
    ot_root = PlanNode(
        node_id="SP:" + PROD, node_name="SP", product=PROD,
        side="outbound", node_type=NODE_TYPE_SUPPLY_POINT, tier=0, lt_wks=0,
    )
    mom = _mk_node("Final_Assy:" + PROD, "Final_Assy", NODE_TYPE_MOM, lt_wks=0, tier=0)
    comp_x = _mk_node("Component_X:" + PROD, "Component_X", NODE_TYPE_MOM,
                       lt_wks=1, supply_role="assembly", tier=1)
    sup_x1 = _mk_node("Supplier_X1:" + PROD, "Supplier_X1", NODE_TYPE_LEAF_IN,
                       lt_wks=1, supply_role="confluence", tier=2)
    sup_x2 = _mk_node("Supplier_X2:" + PROD, "Supplier_X2", NODE_TYPE_LEAF_IN,
                       lt_wks=1, supply_role="confluence", tier=2)
    comp_y = _mk_node("Component_Y_leaf:" + PROD, "Component_Y_leaf", NODE_TYPE_LEAF_IN,
                       lt_wks=1, supply_role="assembly", tier=1)
    comp_z = _mk_node("Component_Z_leaf:" + PROD, "Component_Z_leaf", NODE_TYPE_LEAF_IN,
                       lt_wks=1, supply_role="assembly", tier=1)
    comp_x.add_child(sup_x1)
    comp_x.add_child(sup_x2)
    mom.add_child(comp_x)
    mom.add_child(comp_y)
    mom.add_child(comp_z)
    tree.register(PROD, ot_root=ot_root, in_root=mom)
    tree.init_all_psi()
    return tree, mom, {"Supplier_X1": sup_x1, "Supplier_X2": sup_x2,
                        "Component_Y_leaf": comp_y, "Component_Z_leaf": comp_z}


def _seed_membership(node, week_to_lots: dict) -> None:
    """Directly seed node.psi4demand[w][S] -- simulates what BackwardPlanner
    would have already decided (this is a Unit test: push_pull.py's Mode4
    consumes this as read-only fact, so we seed the fact directly rather
    than running the full BackwardPlanner pass)."""
    for w, lots in week_to_lots.items():
        for lot_id in lots:
            node.add_lot_demand(w, S, lot_id)


def _p_map(node, n_weeks):
    return {w: list(node.psi4supply[w][P]) for w in range(n_weeks)
            if node.psi4supply[w][P]}


# ---------------------------------------------------------------------------
# U1 -- assembly: full recipient preservation
# ---------------------------------------------------------------------------

def test_u1_assembly_children_each_receive_full_recipient_set():
    """Battery/Motor/ECU-style assembly siblings: BackwardPlanner already
    gave each of them the FULL demand lot list (as membership). Mode4 must
    reproduce that full list at the re-timed production week for EVERY
    child -- not a 1/n slice. This is the test that is RED before the fix
    (pre-fix: each child gets only its contiguous slice)."""
    tree, mom, (battery, motor, ecu) = _build_flat_tree(
        [("Battery", "assembly", 2), ("Motor", "assembly", 2), ("ECU", "assembly", 3)])
    lots = ["A", "B", "C", "D"]
    d = 10  # reference demand week
    mom.add_lot_demand(d, S, "A")
    mom.add_lot_demand(d, S, "B")
    mom.add_lot_demand(d, S, "C")
    mom.add_lot_demand(d, S, "D")
    # Backward already decided: every assembly child's own demand IS the
    # full set (this is what backward_planner._propagate_to_children does
    # for supply_role != "confluence" today -- seeded directly here).
    for child in (battery, motor, ecu):
        _seed_membership(child, {d: lots})

    lt = 4  # push_lead_time_weeks
    result = PushProductionPlanner(tree).setup(
        PROD, PushConfig(node_id="MOM", push_lead_time_weeks=lt, sku_id=PROD))

    production_week = d - lt
    for child, name in ((battery, "Battery"), (motor, "Motor"), (ecu, "ECU")):
        got = list(child.psi4supply[production_week][P])
        assert got == lots, (
            f"{name}.psi4supply[{production_week}][P] = {got}, expected the FULL "
            f"recipient set {lots} (assembly semantics) -- got a 1/n slice instead")


# ---------------------------------------------------------------------------
# U2 -- confluence: recipient membership preserved, not re-split
# ---------------------------------------------------------------------------

def test_u2_confluence_children_keep_backward_assigned_membership():
    """Confluence siblings: Backward assigned a NON-contiguous split
    (Supplier_A={A,C}, Supplier_B={B,D}). Mode4 must reproduce exactly that
    split -- not its own contiguous divmod([A,B,C,D], 2) -> ([A,B],[C,D])."""
    tree, mom, (sup_a, sup_b) = _build_flat_tree(
        [("Supplier_A", "confluence", 1), ("Supplier_B", "confluence", 1)])
    d = 10
    for lot_id in ("A", "B", "C", "D"):
        mom.add_lot_demand(d, S, lot_id)
    _seed_membership(sup_a, {d: ["A", "C"]})
    _seed_membership(sup_b, {d: ["B", "D"]})

    lt = 3
    PushProductionPlanner(tree).setup(
        PROD, PushConfig(node_id="MOM", push_lead_time_weeks=lt, sku_id=PROD))

    production_week = d - lt
    assert list(sup_a.psi4supply[production_week][P]) == ["A", "C"], (
        "Supplier_A must keep its Backward-assigned {A,C} membership, "
        "not a re-split contiguous slice")
    assert list(sup_b.psi4supply[production_week][P]) == ["B", "D"]


# ---------------------------------------------------------------------------
# U3 -- mixed / multi-level: final-leaf membership, no tree re-derivation
# ---------------------------------------------------------------------------

def test_u3_mixed_multilevel_uses_final_leaf_membership_only():
    tree, mom, leaves = _build_mixed_tree()
    d = 10
    for lot_id in ("A", "B", "C", "D"):
        mom.add_lot_demand(d, S, lot_id)
    _seed_membership(leaves["Supplier_X1"], {d: ["A", "C"]})
    _seed_membership(leaves["Supplier_X2"], {d: ["B", "D"]})
    _seed_membership(leaves["Component_Y_leaf"], {d: ["A", "B", "C", "D"]})
    _seed_membership(leaves["Component_Z_leaf"], {d: ["A", "B", "C", "D"]})

    lt = 2
    PushProductionPlanner(tree).setup(
        PROD, PushConfig(node_id="Final_Assy", push_lead_time_weeks=lt, sku_id=PROD))

    production_week = d - lt
    assert list(leaves["Supplier_X1"].psi4supply[production_week][P]) == ["A", "C"]
    assert list(leaves["Supplier_X2"].psi4supply[production_week][P]) == ["B", "D"]
    assert list(leaves["Component_Y_leaf"].psi4supply[production_week][P]) == ["A", "B", "C", "D"]
    assert list(leaves["Component_Z_leaf"].psi4supply[production_week][P]) == ["A", "B", "C", "D"]


# ---------------------------------------------------------------------------
# U4 -- horizon-wide membership (leaf demand week != reference demand week)
# ---------------------------------------------------------------------------

def test_u4_membership_lookup_is_horizon_wide_not_same_week_only():
    """The Letter's own NG example: `lot_id in leaf.psi4demand[future_w][S]`
    (same-week-only) must fail here, because the supplier's own Backward
    demand week (W07, offset by its own lt_wks/ss_wks) differs from the
    reference node's demand week (W10)."""
    tree, mom, (supplier,) = _build_flat_tree([("Supplier", "assembly", 3)])
    ref_week = 10
    mom.add_lot_demand(ref_week, S, "A")
    # Backward placed this SAME lot in the supplier's OWN demand at a
    # DIFFERENT week (W07) -- its own lt_wks/ss_wks offset back from W10.
    supplier_week = 7
    _seed_membership(supplier, {supplier_week: ["A"]})

    lt = 2
    PushProductionPlanner(tree).setup(
        PROD, PushConfig(node_id="MOM", push_lead_time_weeks=lt, sku_id=PROD))

    production_week = ref_week - lt  # = 8
    got = list(supplier.psi4supply[production_week][P])
    assert got == ["A"], (
        f"Supplier.psi4supply[{production_week}][P] = {got}; expected ['A'] -- "
        "a same-week-only membership lookup (checking only "
        "leaf.psi4demand[future_w][S], future_w == ref_week here) would miss "
        "this lot entirely since the supplier's own demand lives at week "
        f"{supplier_week}, not {ref_week}")


# ---------------------------------------------------------------------------
# U5 -- no new Lot_ID is minted
# ---------------------------------------------------------------------------

def test_u5_no_new_lot_id_is_minted():
    tree, mom, (battery, motor) = _build_flat_tree(
        [("Battery", "assembly", 1), ("Motor", "assembly", 1)])
    d = 10
    lots = ["A", "B", "C"]
    for lot_id in lots:
        mom.add_lot_demand(d, S, lot_id)
    for child in (battery, motor):
        _seed_membership(child, {d: lots})

    PushProductionPlanner(tree).setup(
        PROD, PushConfig(node_id="MOM", push_lead_time_weeks=2, sku_id=PROD))

    universe = set(lots)
    for child in (battery, motor):
        for w in range(len(WEEKS)):
            for lot_id in child.psi4supply[w][P]:
                assert lot_id in universe, (
                    f"{child.node_name}.psi4supply[{w}][P] contains {lot_id!r}, "
                    f"which is not in the original Demand Anchored Lot_ID universe "
                    f"{universe} -- Mode4 must never mint new Lot_IDs")


# ---------------------------------------------------------------------------
# U7 -- EOL / horizon boundary
# ---------------------------------------------------------------------------

def test_u7_future_week_beyond_horizon_produces_nothing():
    tree, mom, (battery,) = _build_flat_tree([("Battery", "assembly", 1)])
    last_week = len(WEEKS) - 1
    mom.add_lot_demand(last_week, S, "A")
    _seed_membership(battery, {last_week: ["A"]})

    # push_lead_time_weeks large enough that (w + lt) exceeds the horizon
    # for every w except negative ones -- so production should be all-zero.
    PushProductionPlanner(tree).setup(
        PROD, PushConfig(node_id="MOM", push_lead_time_weeks=len(WEEKS) + 5, sku_id=PROD))

    total = sum(len(battery.psi4supply[w][P]) for w in range(len(WEEKS)))
    assert total == 0, f"Expected 0 production (all future_w >= horizon), got {total}"


# ---------------------------------------------------------------------------
# U8 -- no duplicate lot within one leaf/week
# ---------------------------------------------------------------------------

def test_u8_no_duplicate_lot_within_leaf_week():
    tree, mom, (battery,) = _build_flat_tree([("Battery", "assembly", 1)])
    d = 10
    lots = ["A", "B", "C"]
    for lot_id in lots:
        mom.add_lot_demand(d, S, lot_id)
    _seed_membership(battery, {d: lots})

    PushProductionPlanner(tree).setup(
        PROD, PushConfig(node_id="MOM", push_lead_time_weeks=1, sku_id=PROD))

    for w in range(len(WEEKS)):
        p_lots = battery.psi4supply[w][P]
        assert len(p_lots) == len(set(p_lots)), (
            f"Battery.psi4supply[{w}][P] = {p_lots} contains a duplicate Lot_ID")


# ---------------------------------------------------------------------------
# Mode1-3 / mode_only untouched (spot check; full regression lives in
# test_step8_push_pull.py and test_push_pull_mode4_double_count.py)
# ---------------------------------------------------------------------------

def test_mode1_fixed_qty_unaffected_by_this_change():
    tree, mom, (leaf,) = _build_flat_tree([("Leaf", "assembly", 1)])
    result = PushProductionPlanner(tree).setup(
        PROD, PushConfig(node_id="MOM", push_qty_per_week=5, sku_id=PROD))
    assert len(leaf.psi4supply[5][P]) == 5
    assert result.mode == "fixed"
