# -*- coding: utf-8 -*-
"""
tests/test_stage3a1_stockyard.py
===================================
Stage 3a-1: `stockyard` node_type as a pass-through intermediate node
between a leaf_in supplier and its assembly (mom) parent.

Request Letter: requests/request_stage3a1_stockyard_passthrough.md
Design conversation: docs/chat_memo/260904_0919Assemble_kitting_Stockyardのモデル化.docx
Prerequisite (implemented, approved, commit held): requests/request_fix_mode4_supply_role_semantics.md

Scope of this stage: introduce NODE_TYPE_STOCKYARD and insert Yard nodes
(ev-europe-2026, bom-test-2026) between existing leaf_in suppliers and
their mom parent, as PURE PASS-THROUGH nodes (lt_wks=0, no gate keeping).
Goal: behaviour must be byte-identical to the pre-Yard tree at every
downstream node. Gate keeping (Stage 3a-2) is a separate, later Letter.

Bug found and fixed during this stage (Sec 4 impact scan did not catch it;
confirmed only once real lt_wks=0 non-root rows existed):
`sc_tree_builder.py`'s `lt_wks = int(row.get("lt_wks", 1) or 1)` treated an
explicit lt_wks=0 as falsy and silently forced it to 1. Every existing
sample model's lt_wks=0 usage was on ROOT nodes (supply_point/mom), whose
own lt_wks is never read by `_offset_week` (only a CHILD's lt_wks is, when
propagating demand up to ITS parent) -- so the bug was latent until a
Stage 3a-1 Yard (a non-root node genuinely needing lt_wks=0) existed.
Left un-fixed, the double lt_wks=1 hop (Yard + leaf_in, instead of Yard
being lt=0) pushed boundary-week lots into negative (past-due) territory
and silently dropped 500 lots on ev-europe-2026 / Factory_Local_DE.
"""
from __future__ import annotations

import os
import sys

import pandas as pd
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from wom.model.plan_node import (   # noqa: E402
    PlanNode, S, P, I, CO,
    NODE_TYPE_SUPPLY_POINT, NODE_TYPE_MOM, NODE_TYPE_LEAF_IN, NODE_TYPE_STOCKYARD,
)
from wom.model.sc_tree import SCTree                          # noqa: E402
from wom.engine.sc_tree_builder import build_sc_tree_from_master  # noqa: E402
from wom.engine.backward_planner import BackwardPlanner       # noqa: E402
from wom.engine.plan_copy import copy_demand_to_supply         # noqa: E402
from wom.engine.forward_planner import ForwardPlanner          # noqa: E402
from wom.engine.push_pull import PushConfig, PushProductionPlanner  # noqa: E402
from tools.sweep_flags import (                                 # noqa: E402
    guard_files_for_case, guarded_files, apply_ops, _execute_pipeline,
)

WEEKS = [f"2024-W{i:02d}" for i in range(1, 41)]
PROD = "SKU-A"


# ---------------------------------------------------------------------------
# NODE_TYPE_STOCKYARD constant
# ---------------------------------------------------------------------------

def test_node_type_stockyard_constant_exists():
    assert NODE_TYPE_STOCKYARD == "stockyard"


# ---------------------------------------------------------------------------
# sc_tree_builder.py: explicit lt_wks=0 must be honoured, not forced to 1
# ---------------------------------------------------------------------------

def test_csv_lt_wks_zero_is_honoured_not_forced_to_one():
    """Regression for the bug this stage found: a non-root node with
    lt_wks=0 explicitly in the CSV must load as lt_wks==0."""
    df = pd.DataFrame([
        {"node_name": "SP", "parent_node": "", "product_name": PROD,
         "node_type": "supply_point", "side": "outbound", "lt_wks": 0},
        {"node_name": "MOM", "parent_node": "", "product_name": PROD,
         "node_type": "mom", "side": "inbound", "lt_wks": 0},
        {"node_name": "Yard", "parent_node": "MOM", "product_name": PROD,
         "node_type": "stockyard", "side": "inbound", "lt_wks": 0},
        {"node_name": "Leaf", "parent_node": "Yard", "product_name": PROD,
         "node_type": "leaf_in", "side": "inbound", "lt_wks": 2},
    ])
    tree = build_sc_tree_from_master(df, WEEKS)
    mom = tree.get_in_root(PROD)
    yard = mom.children[0]
    leaf = yard.children[0]
    assert yard.lt_wks == 0, f"Yard.lt_wks should be 0 (explicit CSV value), got {yard.lt_wks}"
    assert leaf.lt_wks == 2, f"Leaf.lt_wks should be 2 (unaffected), got {leaf.lt_wks}"


def test_csv_lt_wks_missing_column_still_defaults_to_1():
    """Unaffected-case regression: a row with NO lt_wks column at all must
    still default to 1 (unchanged behaviour)."""
    df = pd.DataFrame([
        {"node_name": "SP", "parent_node": "", "product_name": PROD,
         "node_type": "supply_point", "side": "outbound", "lt_wks": 0},
        {"node_name": "MOM", "parent_node": "", "product_name": PROD,
         "node_type": "mom", "side": "inbound"},  # no lt_wks column value
    ])
    tree = build_sc_tree_from_master(df, WEEKS)
    mom = tree.get_in_root(PROD)
    assert mom.lt_wks == 1


# ---------------------------------------------------------------------------
# Synthetic tree: Yard-inserted vs direct, full pipeline (Backward -> copy
# -> Mode4 -> Forward), byte-identical downstream results
# ---------------------------------------------------------------------------

def _mk(node_id, name, ntype, lt_wks=1, supply_role="assembly", tier=1):
    return PlanNode(node_id=node_id, node_name=name, product=PROD, side="inbound",
                     node_type=ntype, tier=tier, lt_wks=lt_wks, transit_lt_wks=lt_wks,
                     supply_role=supply_role)


def _build_without_yard():
    tree = SCTree(WEEKS)
    ot = PlanNode(node_id="SP", node_name="SP", product=PROD, side="outbound",
                   node_type=NODE_TYPE_SUPPLY_POINT, tier=0, lt_wks=0)
    mom = _mk("MOM", "MOM", NODE_TYPE_MOM, lt_wks=0, tier=0)
    battery = _mk("Battery", "Battery", NODE_TYPE_LEAF_IN, lt_wks=2)
    motor = _mk("Motor", "Motor", NODE_TYPE_LEAF_IN, lt_wks=2)
    ecu = _mk("ECU", "ECU", NODE_TYPE_LEAF_IN, lt_wks=3)
    mom.add_child(battery); mom.add_child(motor); mom.add_child(ecu)
    tree.register(PROD, ot_root=ot, in_root=mom)
    tree.init_all_psi()
    return tree, mom


def _build_with_yard():
    tree = SCTree(WEEKS)
    ot = PlanNode(node_id="SP", node_name="SP", product=PROD, side="outbound",
                   node_type=NODE_TYPE_SUPPLY_POINT, tier=0, lt_wks=0)
    mom = _mk("MOM", "MOM", NODE_TYPE_MOM, lt_wks=0, tier=0)
    by = _mk("Battery_Yard", "Battery_Yard", NODE_TYPE_STOCKYARD, lt_wks=0, tier=1)
    my = _mk("Motor_Yard", "Motor_Yard", NODE_TYPE_STOCKYARD, lt_wks=0, tier=1)
    ey = _mk("ECU_Yard", "ECU_Yard", NODE_TYPE_STOCKYARD, lt_wks=0, tier=1)
    battery = _mk("Battery", "Battery", NODE_TYPE_LEAF_IN, lt_wks=2, tier=2)
    motor = _mk("Motor", "Motor", NODE_TYPE_LEAF_IN, lt_wks=2, tier=2)
    ecu = _mk("ECU", "ECU", NODE_TYPE_LEAF_IN, lt_wks=3, tier=2)
    by.add_child(battery); my.add_child(motor); ey.add_child(ecu)
    mom.add_child(by); mom.add_child(my); mom.add_child(ey)
    tree.register(PROD, ot_root=ot, in_root=mom)
    tree.init_all_psi()
    return tree, mom


def _run_pipeline(tree, mom, lt_weeks=4, first_week=0):
    for w in range(first_week, len(WEEKS)):
        for i in range(3):
            mom.add_lot_demand(w, S, f"L{w:02d}-{i}")
    BackwardPlanner(tree).run(PROD)
    copy_demand_to_supply(tree, PROD)
    PushProductionPlanner(tree).setup(
        PROD, PushConfig(node_id="MOM", push_lead_time_weeks=lt_weeks, sku_id=PROD))
    return ForwardPlanner(tree).run(PROD)


def _summary(node):
    def total(bucket):
        return sum(len(node.psi4supply[w][bucket]) for w in range(len(WEEKS)))
    return {"P": total(P), "S": total(S), "I": total(I), "CO": total(CO)}


def _kitting_complete_total(node):
    total = complete = 0
    for w, wk in enumerate(node.kitting):
        for lot_id in wk:
            total += 1
            if node.kitting_status(w, lot_id)["is_complete"]:
                complete += 1
    return complete, total


def test_yard_insertion_now_deduplicates_mom_p_via_gate():
    """Historical note: at Stage 3a-1 (record-only, no gate keeping), this
    test asserted Yard insertion produced a BYTE-IDENTICAL mom.P/S/I/CO
    summary to the no-Yard baseline -- true at the time (KITTING_GATE_ENABLED
    was False), and that assertion is preserved verbatim as a regression
    guard in test_stage3a2_kitting_gate.py::test_no_stockyard_children_unaffected
    for trees that do NOT use stockyard nodes at all.

    Stage 3a-2 (request_stage3a2_kitting_gate.md) flipped KITTING_GATE_ENABLED
    to True, which is active precisely for trees LIKE this one (stockyard
    children present) -- so the correct, current expectation is the
    opposite: mom1 (with Yard, gated) must show mom.P deduplicated down to
    exactly the demand total, unlike mom0 (no Yard -- still duplicates by
    component count, since gate keeping never applies to plain multi-child
    assembly without stockyard nodes)."""
    tree0, mom0 = _build_without_yard()
    _run_pipeline(tree0, mom0)
    tree1, mom1 = _build_with_yard()
    _run_pipeline(tree1, mom1)

    s0 = _summary(mom0)
    s1 = _summary(mom1)
    demand_total = sum(len(mom1.psi4demand[w][S]) for w in range(len(WEEKS)))

    # Mode4's push_lead_time_weeks (used by _run_pipeline here) truncates a
    # few lots at the horizon boundary, so the no-Yard baseline is not
    # exactly demand_total * 3 -- but it must still clearly show the
    # pre-Stage-3a duplicate-extend pattern (each of the 3 plain assembly
    # children extending its own full copy independently; gate keeping
    # never applies to a tree with no stockyard nodes).
    assert s0["P"] > demand_total * 2, (
        f"no-Yard baseline P={s0['P']} should still show duplicate-extend "
        f"(roughly 3x demand_total={demand_total}) -- gate keeping never "
        f"applies here")
    # With Mode4's own horizon-boundary truncation in play (a handful of
    # lots near the end of the horizon never get a production week at all,
    # unrelated to the gate), P can legitimately be slightly BELOW
    # demand_total -- but it must never legitimately exceed it (no
    # duplication) and must never be a duplicate list.
    for w in range(len(WEEKS)):
        p_lots = mom1.psi4supply[w][P]
        assert len(p_lots) == len(set(p_lots)), f"w={w}: duplicate Lot_ID in mom1.P: {p_lots}"
    assert s1["P"] <= demand_total, (
        f"with-Yard tree P={s1['P']} must not exceed demand_total={demand_total} "
        f"(no duplication via the Kitting Gate)")
    complete, total = _kitting_complete_total(mom1)
    assert complete == s1["P"], "every gated (complete) kit must correspond to one P entry"


def test_yard_insertion_leaves_leaf_in_demand_and_supply_unchanged():
    tree0, mom0 = _build_without_yard()
    _run_pipeline(tree0, mom0)
    tree1, mom1 = _build_with_yard()
    _run_pipeline(tree1, mom1)

    def find(mom, name, one_hop=False):
        for c in mom.children:
            if c.node_name == name:
                return c
            for gc in c.children:
                if gc.node_name == name:
                    return gc
        return None

    for name in ("Battery", "Motor", "ECU"):
        leaf0 = find(mom0, name)
        leaf1 = find(mom1, name)
        d0 = [w for w, wk in enumerate(leaf0.psi4demand) if wk[S]]
        d1 = [w for w, wk in enumerate(leaf1.psi4demand) if wk[S]]
        assert d0 == d1, f"{name}: demand weeks differ {d0} != {d1}"
        assert _summary(leaf0) == _summary(leaf1), f"{name}: supply summary differs"


def test_kitting_required_reflects_yard_names_after_insertion():
    """The direct children of the assembly node are now the Yards, so
    kitting_required() correctly shifts to Yard names -- this is the
    intended, documented consequence (Sec 4.1 item 4 of the Letter),
    not a defect."""
    tree1, mom1 = _build_with_yard()
    _run_pipeline(tree1, mom1)
    assert mom1.kitting_required() == {"Battery_Yard", "Motor_Yard", "ECU_Yard"}


def test_yard_own_kitting_is_trivial_single_child():
    tree1, mom1 = _build_with_yard()
    _run_pipeline(tree1, mom1)
    by = next(c for c in mom1.children if c.node_name == "Battery_Yard")
    assert by.kitting_required() == {"Battery"}
    total = sum(len(wk) for wk in by.kitting)
    complete = sum(1 for w, wk in enumerate(by.kitting) for lot_id in wk
                   if by.kitting_status(w, lot_id)["is_complete"])
    assert total == complete, "Yard's own single-child kitting must always be trivially complete"


def test_boundary_week_lot_not_silently_dropped_through_yard():
    """Direct regression for the bug this stage found: a lot whose demand
    lands at MOM's very first non-warm-up week must NOT be lost when
    propagated through a lt_wks=0 Yard down to a leaf_in with its own
    lt_wks -- pre-fix, this landed at a negative (past-due) week and
    vanished from the leaf's psi4demand entirely."""
    tree0, mom0 = _build_without_yard()
    _run_pipeline(tree0, mom0, first_week=0)
    tree1, mom1 = _build_with_yard()
    _run_pipeline(tree1, mom1, first_week=0)

    def find_leaf(mom, name):
        for c in mom.children:
            for gc in getattr(c, "children", []) or [c]:
                if gc.node_name == name:
                    return gc
        return None

    leaf0 = next(c for c in mom0.children if c.node_name == "Battery")
    leaf1 = find_leaf(mom1, "Battery")
    d0 = sum(1 for wk in leaf0.psi4demand if wk[S])
    d1 = sum(1 for wk in leaf1.psi4demand if wk[S])
    assert d0 == d1 > 0, (
        f"Battery.psi4demand[S] non-empty-week count differs: without-yard={d0} "
        f"with-yard={d1} -- boundary-week lots were dropped by the Yard hop")


# ---------------------------------------------------------------------------
# CSV Integration: real ev-europe-2026 / bom-test-2026 models, byte-identical
# to the pre-Yard-insertion baseline captured after the Mode4 fix
# (request_fix_mode4_supply_role_semantics.md)
# ---------------------------------------------------------------------------

EV_EUROPE_DIR = os.path.join(REPO_ROOT, "data", "sample", "ev-europe-2026")
BOM_TEST_DIR = os.path.join(REPO_ROOT, "data", "sample", "bom-test-2026")


def test_ev_europe_2026_import_chain_matches_post_gate_baseline(tmp_path):
    """Historical note: at Stage 3a-1 (record-only), this asserted P=23,835 /
    I=734,873 -- byte-identical to the pre-Yard baseline, since gate keeping
    did not exist yet. Stage 3a-2 (request_stage3a2_kitting_gate.md) is the
    fix for exactly that non-physical duplication; the current, correct
    values are asserted here instead. PPC revenue/GM% must stay unchanged
    either way -- that invariant carries over verbatim."""
    result, sc_tree = _execute_pipeline(
        EV_EUROPE_DIR, "safe", str(tmp_path / "ppc"), "EVmaker_Import", [])
    mom = sc_tree.get_in_root("EVmaker_Import")

    def total(node, bucket):
        return sum(len(node.psi4supply[w][bucket]) for w in range(len(node.week_labels)))

    assert total(mom, P) == 7945, "P must equal real unique demand, not 3x-duplicated"
    assert total(mom, S) == 8345
    assert total(mom, I) == 0, "I must no longer be a non-physical runaway (was 734,873)"

    kpi_path = os.path.join(str(tmp_path / "ppc"), "ppc_kpi_summary.json")
    import json
    kpi = json.load(open(kpi_path, encoding="utf-8"))
    assert kpi["total_revenue_base"] == pytest.approx(366508230000.0)
    assert kpi["gross_margin_pct"] == pytest.approx(0.524776, abs=1e-5)


def test_ev_europe_2026_local_chain_matches_pre_yard_baseline(tmp_path):
    """Local chain has no push_config -- pure PULL. Same missing count
    (500, boundary-week ECU_DE_Yard shortfall) as before Yard insertion."""
    result, sc_tree = _execute_pipeline(
        EV_EUROPE_DIR, "safe", str(tmp_path / "ppc"), "EVmaker_Local", [])
    mom = sc_tree.get_in_root("EVmaker_Local")
    complete, tot = _kitting_complete_total(mom)
    assert (complete, tot) == (41475, 41975)


def test_bom_test_2026_three_cases_gate_deduplicates_vehicle_assy_p():
    """Historical note: at Stage 3a-1 (record-only), Vehicle_Assy_P was
    2x the complete count (200/140/120 -- Tire_Yard and Battery_Yard each
    independently extending their full demand list). Stage 3a-2's gate
    deduplicates it to exactly the complete-kit count (100/40/20).
    Battery_Supply's own P (a plain leaf_in, unaffected by the gate -- it
    is not itself gated, only its parent Yard's payout is) is unchanged."""
    import json as _json

    MODEL_DIR = BOM_TEST_DIR
    TARGET_SKU = "EV_Model_A"
    spec_path = os.path.join(REPO_ROOT, "tools", "sweep_specs", "bom_test_shortage.json")
    spec = _json.load(open(spec_path, encoding="utf-8"))

    expected = {
        "base": {"complete": 100, "Battery_Supply_P": 100, "Vehicle_Assy_P": 100},
        "battery_short": {"complete": 40, "Battery_Supply_P": 40, "Vehicle_Assy_P": 40},
        "battery_zero": {"complete": 20, "Battery_Supply_P": 20, "Vehicle_Assy_P": 20},
    }

    for case in spec["cases"]:
        name = case["name"]
        ops = case.get("ops", [])
        guard_set = guard_files_for_case(ops)
        with guarded_files(MODEL_DIR, guard_set):
            apply_ops(MODEL_DIR, ops)
            result, sc_tree = _execute_pipeline(
                MODEL_DIR, "safe", os.path.join(REPO_ROOT, "output", f"_test_stage3a1_{name}"),
                TARGET_SKU, [])
            mom = sc_tree.get_in_root(TARGET_SKU)
            complete, tot = _kitting_complete_total(mom)
            assert tot == 100, f"{name}: total kitting entries changed"
            assert complete == expected[name]["complete"], f"{name}: kitting complete changed"

            def find(sc_tree, name_):
                for nd in sc_tree.iter_all_nodes(TARGET_SKU):
                    if nd.node_name == name_:
                        return nd
                return None

            battery = find(sc_tree, "Battery_Supply")
            assy = find(sc_tree, "Vehicle_Assy")
            bp = sum(len(battery.psi4supply[w][P]) for w in range(len(battery.week_labels)))
            ap = sum(len(assy.psi4supply[w][P]) for w in range(len(assy.week_labels)))
            assert bp == expected[name]["Battery_Supply_P"], f"{name}: Battery_Supply P_sum changed"
            assert ap == expected[name]["Vehicle_Assy_P"], f"{name}: Vehicle_Assy P_sum changed"
