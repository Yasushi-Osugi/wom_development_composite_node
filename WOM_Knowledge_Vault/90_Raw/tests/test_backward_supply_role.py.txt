# -*- coding: utf-8 -*-
"""
tests/test_backward_supply_role.py
====================================
Regression test for the A1 fix: `supply_role`-based demand distribution in
BackwardPlanner._in_propagate / _propagate_to_children.

Request Letter: requests/request_fix_a1_supply_role_rev2.md
Investigation trail: requests/request_fix_a1_multi_child_duplication.md (Rev 1,
superseded), tools/sweep_specs/india_ghee_a1.yaml.

Background
----------
Before this fix, `_in_propagate` copied the FULL weekly demand-S lot list to
EVERY child of a node, unconditionally (`for lot_id in all_lots: for child in
node.children: child.psi4demand[child_w][S].append(lot_id)`). That is correct
for "assembly" semantics (a battery AND a motor AND an ECU per vehicle -- each
needs the full unit count) but wrong for "confluence" semantics (milk from
two collection routes -- the total need is SPLIT between them, not each
route independently sourcing the full amount). The Forward side then
`extend()`s each child's actual shipment into the parent's P, so a
confluence-typed MOM ended up with the same Lot_ID counted once per child --
inflating P_sum until cap_hard sealed the excess into phantom CO (see
india-ghee-2026 / Ghee_Plant_Anand, CO_sum 429,299-505,979 with two leaf_in
children and smooth demand -- CLAUDE.md's "demand step required" theory was
wrong).

The fix adds a `supply_role` column (edge attribute, read on the CHILD's
sc_tree_master.csv row): "confluence" siblings split the parent's demand
(equal + remainder, divmod-based, same idiom as push_pull.py's Mode4 leaf-in
distribution); "assembly" (or blank/unspecified, the default) siblings each
still get a full copy, multiplied by a `multiplier` variable fixed at 1 until
a future Request Letter implements real BOM qty-per-unit N ("1 set rule").
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from wom.model.plan_node import (   # noqa: E402
    PlanNode, S,
    NODE_TYPE_SUPPLY_POINT, NODE_TYPE_MOM, NODE_TYPE_LEAF_IN,
)
from wom.model.sc_tree import SCTree                      # noqa: E402
from wom.engine.backward_planner import BackwardPlanResult, BackwardPlanner  # noqa: E402
from wom.engine.sc_tree_builder import build_sc_tree_from_master             # noqa: E402
import pandas as pd                                        # noqa: E402

WEEKS = [f"2024-W{i:02d}" for i in range(1, 11)]  # 10-week horizon
PROD  = "SKU-A"


def _build_tree(children_roles):
    """
    Build a minimal InBound-only tree: one MOM root with children named
    child0, child1, ... whose supply_role is given by `children_roles`
    (a list of "confluence" / "assembly" / "" strings, one per child).
    Also registers a trivial (childless) OutBound supply_point root, since
    SCTree.register() requires one.
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
            supply_role=(role or "assembly"),
        )
        mom.add_child(child)
        children.append(child)

    tree.register(PROD, ot_root=ot_root, in_root=mom)
    tree.init_all_psi()
    return tree, mom, children


def _set_demand(mom, w, lot_ids):
    for lot_id in lot_ids:
        mom.add_lot_demand(w, S, lot_id)


def _run_in_propagate(tree, mom):
    result = BackwardPlanResult(prod_nm=PROD)
    planner = BackwardPlanner(tree)
    n_weeks = tree.num_weeks()
    planner._in_propagate(mom, n_weeks, result)
    return result


# ---------------------------------------------------------------------------
# supply_role reading / storage / default
# ---------------------------------------------------------------------------

_SP_ROW = {"node_name": "SP", "parent_node": "", "product_name": PROD,
           "node_type": "supply_point", "side": "outbound", "lt_wks": 0}


def test_supply_role_read_from_csv_and_stored_on_plan_node():
    df = pd.DataFrame([
        _SP_ROW,
        {"node_name": "MOM", "parent_node": "", "product_name": PROD,
         "node_type": "mom", "side": "inbound", "lt_wks": 1, "supply_role": ""},
        {"node_name": "A", "parent_node": "MOM", "product_name": PROD,
         "node_type": "leaf_in", "side": "inbound", "lt_wks": 1, "supply_role": "confluence"},
        {"node_name": "B", "parent_node": "MOM", "product_name": PROD,
         "node_type": "leaf_in", "side": "inbound", "lt_wks": 1, "supply_role": "assembly"},
    ])
    tree = build_sc_tree_from_master(df, WEEKS)
    mom = tree.get_in_root(PROD)
    by_name = {c.node_name: c for c in mom.children}
    assert hasattr(by_name["A"], "supply_role")
    assert by_name["A"].supply_role == "confluence"
    assert by_name["B"].supply_role == "assembly"


def test_supply_role_blank_defaults_to_assembly():
    df = pd.DataFrame([
        _SP_ROW,
        {"node_name": "MOM", "parent_node": "", "product_name": PROD,
         "node_type": "mom", "side": "inbound", "lt_wks": 1},
        {"node_name": "A", "parent_node": "MOM", "product_name": PROD,
         "node_type": "leaf_in", "side": "inbound", "lt_wks": 1},  # no supply_role column value at all
    ])
    tree = build_sc_tree_from_master(df, WEEKS)
    mom = tree.get_in_root(PROD)
    assert mom.children[0].supply_role == "assembly"


def test_supply_role_unknown_value_defaults_to_assembly():
    df = pd.DataFrame([
        _SP_ROW,
        {"node_name": "MOM", "parent_node": "", "product_name": PROD,
         "node_type": "mom", "side": "inbound", "lt_wks": 1, "supply_role": ""},
        {"node_name": "A", "parent_node": "MOM", "product_name": PROD,
         "node_type": "leaf_in", "side": "inbound", "lt_wks": 1, "supply_role": "typo_value"},
    ])
    tree = build_sc_tree_from_master(df, WEEKS)
    mom = tree.get_in_root(PROD)
    assert mom.children[0].supply_role == "assembly"


# ---------------------------------------------------------------------------
# distribution behaviour
# ---------------------------------------------------------------------------

def test_confluence_two_children_split_evenly_no_duplication_no_loss():
    tree, mom, (a, b) = _build_tree(["confluence", "confluence"])
    w = 3
    lots = [f"L{i:03d}" for i in range(10)]
    _set_demand(mom, w, lots)
    _run_in_propagate(tree, mom)

    child_w = w - 1  # lt_wks=1
    a_lots = list(a.psi4demand[child_w][S])
    b_lots = list(b.psi4demand[child_w][S])

    # no loss: union of both children == the original set
    assert set(a_lots) | set(b_lots) == set(lots)
    # no duplication: no lot in both children, and each child's own list has no repeats
    assert set(a_lots) & set(b_lots) == set()
    assert len(a_lots) == len(set(a_lots))
    assert len(b_lots) == len(set(b_lots))
    # equal split (10 lots / 2 children = 5 each, remainder 0)
    assert len(a_lots) == 5
    assert len(b_lots) == 5


def test_confluence_uneven_split_uses_remainder():
    tree, mom, (a, b, c) = _build_tree(["confluence", "confluence", "confluence"])
    w = 3
    lots = [f"L{i:03d}" for i in range(10)]  # 10 / 3 = base 3, remainder 1
    _set_demand(mom, w, lots)
    _run_in_propagate(tree, mom)

    child_w = w - 1
    sizes = sorted(len(c_.psi4demand[child_w][S]) for c_ in (a, b, c))
    assert sizes == [3, 3, 4]
    all_assigned = (list(a.psi4demand[child_w][S]) + list(b.psi4demand[child_w][S])
                    + list(c.psi4demand[child_w][S]))
    assert sorted(all_assigned) == sorted(lots)
    assert len(all_assigned) == len(set(all_assigned))  # no duplication


def test_assembly_two_children_each_get_full_copy():
    tree, mom, (a, b) = _build_tree(["assembly", "assembly"])
    w = 3
    lots = [f"L{i:03d}" for i in range(7)]
    _set_demand(mom, w, lots)
    _run_in_propagate(tree, mom)

    child_w = w - 1
    a_lots = list(a.psi4demand[child_w][S])
    b_lots = list(b.psi4demand[child_w][S])
    # this IS the existing (pre-fix) behaviour, preserved for assembly:
    assert sorted(a_lots) == sorted(lots)
    assert sorted(b_lots) == sorted(lots)


def test_mixed_confluence_and_assembly_siblings():
    tree, mom, (conf_a, conf_b, asm) = _build_tree(["confluence", "confluence", "assembly"])
    w = 3
    lots = [f"L{i:03d}" for i in range(8)]
    _set_demand(mom, w, lots)
    _run_in_propagate(tree, mom)

    child_w = w - 1
    conf_a_lots = list(conf_a.psi4demand[child_w][S])
    conf_b_lots = list(conf_b.psi4demand[child_w][S])
    asm_lots    = list(asm.psi4demand[child_w][S])

    # confluence pair splits the 8 lots between them (4/4), no overlap
    assert set(conf_a_lots) | set(conf_b_lots) == set(lots)
    assert set(conf_a_lots) & set(conf_b_lots) == set()
    assert len(conf_a_lots) == 4 and len(conf_b_lots) == 4
    # assembly sibling independently gets the FULL demand regardless of the
    # confluence split happening alongside it
    assert sorted(asm_lots) == sorted(lots)


def test_single_child_confluence_gets_full_demand():
    tree, mom, (a,) = _build_tree(["confluence"])
    w = 3
    lots = [f"L{i:03d}" for i in range(6)]
    _set_demand(mom, w, lots)
    _run_in_propagate(tree, mom)
    assert sorted(a.psi4demand[w - 1][S]) == sorted(lots)


def test_single_child_assembly_gets_full_demand():
    tree, mom, (a,) = _build_tree(["assembly"])
    w = 3
    lots = [f"L{i:03d}" for i in range(6)]
    _set_demand(mom, w, lots)
    _run_in_propagate(tree, mom)
    assert sorted(a.psi4demand[w - 1][S]) == sorted(lots)
