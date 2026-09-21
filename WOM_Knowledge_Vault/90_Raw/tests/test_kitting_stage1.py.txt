# -*- coding: utf-8 -*-
"""
tests/test_kitting_stage1.py
=============================
Unit tests for Kitting List stage 1 (record-only).

Request Letter: requests/request_kitting_stage1.md
Design doc:     docs/design/kitting_list_assembly.md

Stage 1 adds a record-only structure --
    plan_node.kitting[assembly_week][lot_id] = {child_node_name: arrival_week}
-- populated by ForwardPlanner._propagate_to_parent, alongside (never instead
of) the existing unconditional `parent.psi4supply[target_w][P].extend(...)`.
It must NOT change any P/S/I/CO value (KITTING_GATE_ENABLED stays False).

`assembly_week` (the outer key) is the PARENT's own backward-planned demand
week for that lot (from parent.psi4demand[*][S] -- see
ForwardPlanner._get_demand_week_index), which is the single value shared by
every assembly sibling regardless of each child's own lt_wks/ss_wks or
forward-plan delay. `arrival_week` (the value) is each child's own actual
delivery week (target_w in _propagate_to_parent) -- this is allowed to
differ per child, which is exactly what lets `missing` answer "which part is
late" instead of just "something is late".

These tests drive `ForwardPlanner._propagate_to_parent` directly (bypassing
a full run()) so that each child's arrival week can be controlled precisely,
the way tests/test_backward_supply_role.py drives `_in_propagate` directly.
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
from wom.model.sc_tree import SCTree                          # noqa: E402
from wom.engine.forward_planner import (                      # noqa: E402
    ForwardPlanner, ForwardPlanResult, KITTING_GATE_ENABLED,
)

WEEKS = [f"2024-W{i:02d}" for i in range(1, 11)]  # 10-week horizon
PROD  = "SKU-A"


def _build_tree(children_roles):
    """
    One MOM root ("mom") with children child0, child1, ... whose
    supply_role is given by `children_roles` ("confluence" / "assembly").
    A trivial (childless) OutBound supply_point root is also registered,
    since SCTree.register() requires one -- mirrors
    tests/test_backward_supply_role.py's _build_tree.
    """
    tree = SCTree(WEEKS)

    ot_root = PlanNode(
        node_id="SP:" + PROD, node_name="SP", product=PROD,
        side="outbound", node_type=NODE_TYPE_SUPPLY_POINT, tier=0, lt_wks=0,
    )
    mom = PlanNode(
        node_id="MOM:" + PROD, node_name="MOM", product=PROD,
        side="inbound", node_type=NODE_TYPE_MOM, tier=0, lt_wks=1,
    )
    children = []
    for i, role in enumerate(children_roles):
        child = PlanNode(
            node_id=f"CHILD{i}:{PROD}", node_name=f"child{i}", product=PROD,
            side="inbound", node_type=NODE_TYPE_LEAF_IN, tier=1, lt_wks=1,
            transit_lt_wks=1,
            supply_role=(role or "assembly"),
        )
        mom.add_child(child)
        children.append(child)

    tree.register(PROD, ot_root=ot_root, in_root=mom)
    tree.init_all_psi()
    return tree, mom, ot_root, children


def _new_fp(tree: SCTree) -> ForwardPlanner:
    """ForwardPlanner with the per-run state that run() normally sets up
    (bypassed here so tests can drive _propagate_to_parent directly)."""
    fp = ForwardPlanner(tree)
    fp._actual_s = {}
    fp._kitting_week_index = {}
    return fp


def _propagate(fp: ForwardPlanner, child: PlanNode, week: int, lot_ids,
                result: ForwardPlanResult, n_weeks: int) -> None:
    """Simulate child's actual (physically matched) shipment of `lot_ids`
    at `week`, then run the real _propagate_to_parent for it."""
    fp._actual_s.setdefault(child.node_id, {})[week] = list(lot_ids)
    fp._propagate_to_parent(child, n_weeks, result)


# ---------------------------------------------------------------------------
# PlanNode-level: attribute default / judgement helpers (no engine needed)
# ---------------------------------------------------------------------------

def test_kitting_attribute_exists_and_defaults_empty():
    tree, mom, ot_root, (a,) = _build_tree(["assembly"])
    assert hasattr(mom, "kitting")
    assert len(mom.kitting) == len(WEEKS)
    assert all(wk == {} for wk in mom.kitting)
    # leaf_in / OutBound nodes also default empty
    assert all(wk == {} for wk in a.kitting)
    assert all(wk == {} for wk in ot_root.kitting)


def test_kitting_required_excludes_confluence():
    tree, mom, ot_root, (a, b, c) = _build_tree(["assembly", "assembly", "confluence"])
    required = mom.kitting_required()
    assert required == {"child0", "child1"}
    assert "child2" not in required


def test_kitting_required_single_assembly_child():
    tree, mom, ot_root, (a,) = _build_tree(["assembly"])
    assert mom.kitting_required() == {"child0"}


def test_kitting_status_missing_and_is_complete():
    tree, mom, ot_root, (a, b) = _build_tree(["assembly", "assembly"])
    w = 5
    lot = "LOT_X"
    # nothing recorded yet
    st = mom.kitting_status(w, lot)
    assert st["required"] == {"child0", "child1"}
    assert st["arrived"] == set()
    assert st["missing"] == {"child0", "child1"}
    assert st["is_complete"] is False

    mom.kitting[w][lot] = {"child0": w}
    st = mom.kitting_status(w, lot)
    assert st["arrived"] == {"child0"}
    assert st["missing"] == {"child1"}
    assert st["is_complete"] is False

    mom.kitting[w][lot]["child1"] = w
    st = mom.kitting_status(w, lot)
    assert st["missing"] == set()
    assert st["is_complete"] is True


# ---------------------------------------------------------------------------
# ForwardPlanner._propagate_to_parent: recording behaviour
# ---------------------------------------------------------------------------

def test_assembly_siblings_recorded_under_shared_assembly_week_even_when_arrival_weeks_differ():
    """The core scenario this design exists for: Battery arrives late,
    Tire arrives on time -- both must land under the SAME kitting key (the
    parent's own demand week), not under their own (different) arrival
    weeks, or `missing` would falsely flag a pure LT/delay difference."""
    tree, mom, ot_root, (tire, battery) = _build_tree(["assembly", "assembly"])
    n_weeks = tree.num_weeks()
    assembly_week = 5
    lot = f"{PROD}:US:2024-W06:00001"
    mom.add_lot_demand(assembly_week, S, lot)  # parent's own fixed demand week

    fp = _new_fp(tree)
    result = ForwardPlanResult(prod_nm=PROD)

    # Tire ships on time (target_w == assembly_week)
    _propagate(fp, tire, week=4, lot_ids=[lot], result=result, n_weeks=n_weeks)
    # Battery is delayed 3 weeks (target_w == assembly_week + 3)
    _propagate(fp, battery, week=7, lot_ids=[lot], result=result, n_weeks=n_weeks)

    # both recorded under the SAME outer key (assembly_week), not under
    # their own (different) target_w
    assert lot in mom.kitting[assembly_week]
    assert mom.kitting[assembly_week][lot] == {
        "child0": 5,   # tire:    week=4 + transit_lt_wks(1) = 5 == assembly_week
        "child1": 8,   # battery: week=7 + transit_lt_wks(1) = 8 (late)
    }
    st = mom.kitting_status(assembly_week, lot)
    assert st["required"] == {"child0", "child1"}
    assert st["arrived"] == {"child0", "child1"}
    assert st["is_complete"] is True

    # no fallback needed -- the lot was found in mom.psi4demand
    assert result.kitting_fallback_events == []


def test_partial_delivery_missing_reports_which_child_is_late():
    tree, mom, ot_root, (tire, battery) = _build_tree(["assembly", "assembly"])
    n_weeks = tree.num_weeks()
    assembly_week = 5
    lot = f"{PROD}:US:2024-W06:00001"
    mom.add_lot_demand(assembly_week, S, lot)

    fp = _new_fp(tree)
    result = ForwardPlanResult(prod_nm=PROD)

    # Only Tire has shipped so far; Battery has not shipped this lot at all.
    _propagate(fp, tire, week=4, lot_ids=[lot], result=result, n_weeks=n_weeks)

    st = mom.kitting_status(assembly_week, lot)
    assert st["arrived"] == {"child0"}
    assert st["missing"] == {"child1"}
    assert st["is_complete"] is False


def test_confluence_child_never_writes_kitting():
    tree, mom, ot_root, (a, b, c) = _build_tree(["assembly", "assembly", "confluence"])
    n_weeks = tree.num_weeks()
    assembly_week = 3
    lot = f"{PROD}:US:2024-W04:00001"
    mom.add_lot_demand(assembly_week, S, lot)

    fp = _new_fp(tree)
    result = ForwardPlanResult(prod_nm=PROD)
    _propagate(fp, c, week=2, lot_ids=[lot], result=result, n_weeks=n_weeks)

    # the confluence child's physical shipment still reaches the parent's P
    # (unchanged engine behaviour) ...
    assert lot in mom.psi4supply[3][P]
    # ... but kitting was NOT touched by it
    assert mom.kitting[assembly_week] == {}
    assert result.kitting_fallback_events == []


def test_confluence_only_parent_has_empty_kitting():
    tree, mom, ot_root, (a, b) = _build_tree(["confluence", "confluence"])
    n_weeks = tree.num_weeks()
    lot = f"{PROD}:US:2024-W04:00001"
    mom.add_lot_demand(3, S, lot)

    fp = _new_fp(tree)
    result = ForwardPlanResult(prod_nm=PROD)
    _propagate(fp, a, week=2, lot_ids=[lot], result=result, n_weeks=n_weeks)
    _propagate(fp, b, week=2, lot_ids=["other-lot"], result=result, n_weeks=n_weeks)

    assert all(wk == {} for wk in mom.kitting)
    assert mom.kitting_required() == set()


def test_kitting_fallback_when_lot_not_in_parent_demand():
    """A lot_id that never appears in parent.psi4demand[*][S] (e.g. it did
    not originate from BackwardPlanner demand propagation) must NOT be
    silently dropped or mis-filed -- it is recorded under its own
    arrival_week (target_w) as a documented fallback, and counted."""
    tree, mom, ot_root, (a,) = _build_tree(["assembly"])
    n_weeks = tree.num_weeks()
    stray_lot = "STRAY:NOT:IN:DEMAND"
    # deliberately do NOT add this lot to mom.psi4demand

    fp = _new_fp(tree)
    result = ForwardPlanResult(prod_nm=PROD)
    _propagate(fp, a, week=4, lot_ids=[stray_lot], result=result, n_weeks=n_weeks)

    target_w = 4 + a.transit_lt_wks  # == 5
    assert stray_lot in mom.kitting[target_w]
    assert mom.kitting[target_w][stray_lot] == {"child0": target_w}
    assert len(result.kitting_fallback_events) == 1
    assert result.kitting_fallback_events[0][0] == mom.node_id
    assert result.kitting_fallback_events[0][2] == stray_lot


# ---------------------------------------------------------------------------
# Stage 1 invariant: P extend stays unconditional (no gate keeping)
# ---------------------------------------------------------------------------

def test_gate_flag_is_false_and_incomplete_kit_still_enters_p():
    # Stage 3a-2 (request_stage3a2_kitting_gate.md) flipped this constant to
    # True, but gate keeping only activates for a node whose direct children
    # are ALL node_type=="stockyard" (checked in ForwardPlanner.run()'s main
    # loop, not in _propagate_to_parent itself). This test's tree uses plain
    # leaf_in children and calls _propagate_to_parent directly -- the code
    # path this stage added is never reached, so the original Stage 1
    # invariant (P extend stays unconditional) still holds unchanged here.
    assert KITTING_GATE_ENABLED is True

    tree, mom, ot_root, (tire, battery) = _build_tree(["assembly", "assembly"])
    n_weeks = tree.num_weeks()
    assembly_week = 5
    lot = f"{PROD}:US:2024-W06:00001"
    mom.add_lot_demand(assembly_week, S, lot)

    fp = _new_fp(tree)
    result = ForwardPlanResult(prod_nm=PROD)

    # Only Tire ships -- Battery never does. Kit is incomplete.
    _propagate(fp, tire, week=4, lot_ids=[lot], result=result, n_weeks=n_weeks)
    assert mom.kitting_status(assembly_week, lot)["is_complete"] is False

    # Yet the lot IS in the parent's P bucket -- stage 1 never withholds it.
    target_w = 4 + tire.transit_lt_wks
    assert lot in mom.psi4supply[target_w][P]
