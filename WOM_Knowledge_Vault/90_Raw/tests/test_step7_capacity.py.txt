"""
tests/test_step7_capacity.py
============================
Step 7 — CapHard / CapSoft sealing at MOM nodes

Test scenarios:
  1. cap_hard_sealing  — CapHard=2, MOM demand=4 → 2 sealed, 2 deferred to CO[w+1]
  2. cap_soft_violation — CapSoft=2, CapHard=0, demand=4 → all 4 processed, 2 flagged
  3. combined          — CapHard=3, CapSoft=2, demand=5 → 2 hard-sealed, 1 soft-flag
  4. e2e_cap_propagation — CapHard sealing propagates through bridge → OT leaf shortfall
"""

import sys
import os

# ── path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from wom.model.plan_node import (
    PlanNode, S, CO, I, P,
    NODE_TYPE_SUPPLY_POINT, NODE_TYPE_DAD, NODE_TYPE_LEAF_OUT,
    NODE_TYPE_MOM, NODE_TYPE_LEAF_IN,
)
from wom.model.sc_tree       import SCTree, build_demo_sc_tree
from wom.model.lot_generator import LotIDGenerator, assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner
from wom.engine.plan_copy        import copy_demand_to_supply
from wom.engine.forward_planner  import ForwardPlanner
from wom.engine.capacity_sealer  import (
    CapacityProfile,
    apply_capacity_profile,
    build_mom_capacity_profile,
    build_capacity_load_report,
)


# ---------------------------------------------------------------------------
# Shared fixture builder
# ---------------------------------------------------------------------------

def build_tree_with_demand(cap_hard=0.0, cap_soft=0.0, demand_qty=4):
    """
    Single-region, single-SKU demo tree.
    Demand is set at leaf_out for week W10 (26-week horizon, W01..W26).
    Returns (sc_tree, weeks, sku_id, mom_node)
    """
    sku_id  = "SKU-A"
    region  = "JP"
    weeks   = [f"2024-W{i:02d}" for i in range(1, 27)]   # W01..W26

    sku_master = pd.DataFrame([
        {"sku_id": sku_id, "sku_name": "Product A", "region": region,
         "lead_time_wks": 1},
    ])

    sc_tree = build_demo_sc_tree(sku_master, weeks, lt_wks_ot=1, lt_wks_in=2)
    mom_node = sc_tree.get_in_root(sku_id)

    # Set capacity on MOM
    if cap_hard > 0 or cap_soft > 0:
        for w in range(len(weeks)):
            mom_node.set_capacity(w, cap_hard=cap_hard, cap_soft=cap_soft)

    # Assign demand at leaf_out
    demand_dict = {(sku_id, region, "2024-W10"): demand_qty}
    assign_demand_lots_from_dict(sc_tree, demand_dict, cpu_size=1)

    # Backward + copy
    # v1r0m3: use mom_constrained=False to preserve v1r0m2 test behaviour.
    # Existing tests in this file verify v1r0m2 semantics (cap_hard envelope only).
    # v1r0m3 MOM constrained allocation is tested in test_step7b_mom_constrained.py.
    BackwardPlanner(sc_tree, config={"mom_constrained": False}).run(sku_id)
    copy_demand_to_supply(sc_tree, sku_id)

    return sc_tree, weeks, sku_id, mom_node


# ---------------------------------------------------------------------------
# Test 1: CapHard sealing
# ---------------------------------------------------------------------------

def test_cap_hard_sealing():
    """
    CapHard=2, demand=4 at MOM week W06 (backward-propagated from leaf W10).

    v1r0m3 design: BackwardPlanner propagates full demand (no clipping in _in_propagate).
    ForwardPlanner enforces cap_hard at MOM -> 2 lots sealed (demand 4 - cap 2 = 2).

    Verified constraint: bridge_lots == cap_hard (2); ForwardPlanner seals excess.
    """
    sc_tree, weeks, sku_id, mom = build_tree_with_demand(
        cap_hard=2.0, cap_soft=0.0, demand_qty=4
    )

    fp     = ForwardPlanner(sc_tree)
    result = fp.run(sku_id)

    print(result)
    print(f"cap_hard_events  : {result.cap_hard_events}")
    print(f"cap_soft_violations: {result.cap_soft_violations}")

    # v1r0m3: BackwardPlanner propagates full demand; ForwardPlanner enforces cap_hard.
    # demand=4, cap_hard=2 -> ForwardPlanner seals 2 excess lots.
    assert result.cap_hard_sealed == 2, (
        f"v1r0m3: ForwardPlanner seals excess at MOM, expected 2 got {result.cap_hard_sealed}"
    )
    # Only cap_hard (2) lots crossed the bridge
    assert result.bridge_lots == 2, (
        f"Expected bridge_lots=2 (cap_hard constraint), got {result.bridge_lots}"
    )

    print("PASS: test_cap_hard_sealing")


# ---------------------------------------------------------------------------
# Test 2: CapSoft violation -- no lot movement
# ---------------------------------------------------------------------------

def test_cap_soft_violation_no_movement():
    """
    CapSoft=2 only (CapHard=0), demand=4.
    Expected:
      - NO lots deferred (no CapHard sealing)
      - cap_soft_violations list has entries
      - MOM P still has 4 lots (unchanged)
    """
    sc_tree, weeks, sku_id, mom = build_tree_with_demand(
        cap_hard=0.0, cap_soft=2.0, demand_qty=4
    )

    # Find the MOM P[W06] before forward planning (from copy)
    w06 = weeks.index("2024-W06")
    p_qty_before = len(mom.psi4supply[w06][P])
    print(f"MOM P[W06] before forward: {p_qty_before} lots")

    fp     = ForwardPlanner(sc_tree)
    result = fp.run(sku_id)

    print(result)
    print(f"cap_soft_violations: {result.cap_soft_violations}")

    assert result.cap_hard_sealed == 0, (
        "No CapHard sealing expected when cap_hard=0"
    )
    assert len(result.cap_soft_violations) > 0, (
        "Expected CapSoft violations to be recorded"
    )

    print("PASS: test_cap_soft_violation_no_movement")


# ---------------------------------------------------------------------------
# Test 3: Combined CapHard + CapSoft
# ---------------------------------------------------------------------------

def test_combined_cap_hard_soft():
    """
    CapHard=3, CapSoft=2, demand=5.

    v1r0m3 design: BackwardPlanner propagates full demand (5 lots, no clipping).
    ForwardPlanner enforces cap_hard=3 at MOM -> 2 lots sealed (demand 5 - cap 3 = 2).
    CapSoft=2 is violated (3 > 2).
    """
    sc_tree, weeks, sku_id, mom = build_tree_with_demand(
        cap_hard=3.0, cap_soft=2.0, demand_qty=5
    )

    fp     = ForwardPlanner(sc_tree)
    result = fp.run(sku_id)

    print(result)
    print(f"cap_hard_events  : {result.cap_hard_events}")
    print(f"cap_soft_violations: {result.cap_soft_violations}")

    # v1r0m3: ForwardPlanner enforces cap_hard; demand=5, cap=3 -> 2 sealed.
    assert result.cap_hard_sealed == 2, (
        f"v1r0m3: ForwardPlanner seals excess, expected 2 got {result.cap_hard_sealed}"
    )
    assert result.bridge_lots == 3, (
        f"Expected bridge_lots=3 (cap_hard=3), got {result.bridge_lots}"
    )
    assert len(result.cap_soft_violations) > 0, "Expected CapSoft violation"

    print("PASS: test_combined_cap_hard_soft")


# ---------------------------------------------------------------------------
# Test 4: CapacityProfile bulk-apply via apply_capacity_profile
# ---------------------------------------------------------------------------

def test_capacity_profile_apply():
    """
    Use CapacityProfile + apply_capacity_profile to set CapHard on MOM node.
    Verify that apply_capacity_profile correctly writes to the node.
    """
    sc_tree, weeks, sku_id, mom = build_tree_with_demand(
        cap_hard=0.0, cap_soft=0.0, demand_qty=4
    )

    profile = CapacityProfile()
    profile.add_flat(node_id=mom.node_id, weeks=weeks, cap_hard=2.0, cap_soft=3.0)

    stats = apply_capacity_profile(sc_tree, profile)
    print(f"Profile apply stats: {stats}")

    assert stats["applied"] == len(weeks), (
        f"Expected {len(weeks)} entries applied, got {stats['applied']}"
    )
    assert stats["node_not_found"] == 0

    # Verify the capacity was written
    w06 = weeks.index("2024-W06")
    assert mom.cap_hard(w06) == 2.0, (
        f"Expected cap_hard=2.0 at W06, got {mom.cap_hard(w06)}"
    )
    assert mom.cap_soft(w06) == 3.0, (
        f"Expected cap_soft=3.0 at W06, got {mom.cap_soft(w06)}"
    )

    print("PASS: test_capacity_profile_apply")


# ---------------------------------------------------------------------------
# Test 5: build_mom_capacity_profile convenience builder
# ---------------------------------------------------------------------------

def test_build_mom_capacity_profile():
    """
    build_mom_capacity_profile creates entries for all MOM nodes.
    For the demo tree (one MOM at tier=0), should cover all weeks.
    """
    sc_tree, weeks, sku_id, mom = build_tree_with_demand(
        cap_hard=0.0, demand_qty=4
    )

    profile = build_mom_capacity_profile(
        sc_tree, cap_hard_per_week=3.0, cap_soft_per_week=2.0, prod_nm=sku_id
    )
    stats = apply_capacity_profile(sc_tree, profile)
    print(f"Profile entries: {len(profile.entries)}  stats: {stats}")

    assert len(profile.entries) > 0
    assert stats["node_not_found"] == 0

    fp     = ForwardPlanner(sc_tree)
    result = fp.run(sku_id)
    print(result)

    # With CapHard=3 and demand=4, 1 lot sealed
    assert result.cap_hard_sealed == 1, (
        f"Expected 1 lot hard-sealed, got {result.cap_hard_sealed}"
    )

    print("PASS: test_build_mom_capacity_profile")


# ---------------------------------------------------------------------------
# Test 6: E2E propagation -- CapHard sealing causes leaf_out shortfall
# ---------------------------------------------------------------------------

def test_e2e_cap_hard_causes_leaf_shortfall():
    """
    Full E2E test: Lot_ID identity-matched decouple design.
      - demand=4 lots at leaf_out[JP]
      - CapHard=2 at MOM: BackwardPlanner clips to 2 lots

    Design (post identity-matching refactor -- see forward_planner.py
    ForwardPlanner._match_by_identity):
      psi4supply[w][S] is NEVER overwritten by the fulfillment outcome; it
      always stays the planned/demand-anchored record. Both leaf_out.S and
      DAD.S therefore read as the full demand (4) -- this is intentional,
      not a regression. The ACTUAL physical fulfillment, constrained by
      MOM cap_hard=2, is now visible via:
        - ForwardPlanner._actual_s[dad_node.node_id]  (Lot_IDs really shipped)
        - dad_node.psi4supply[w][CO]                  (unmatched demand, i.e.
                                                         the 2-lot shortfall)
      DAD as decouple point still absorbs supply variability; leaf_out still
      stays demand-anchored -- just verified through different buckets now.
    """
    sc_tree, weeks, sku_id, mom = build_tree_with_demand(
        cap_hard=2.0, cap_soft=0.0, demand_qty=4
    )

    fp     = ForwardPlanner(sc_tree)
    result = fp.run(sku_id)

    # Find leaf_out and DAD nodes
    leaf_node = None
    dad_node  = None
    from wom.model.plan_node import NODE_TYPE_DAD
    for node in sc_tree.iter_all_nodes(sku_id):
        if node.node_id == f"OUT:Sales:JP:{sku_id}":
            leaf_node = node
        if node.node_type == NODE_TYPE_DAD:
            dad_node = node

    assert leaf_node is not None, "Could not find leaf_out JP node"
    assert dad_node  is not None, "Could not find DAD node"

    weeks_n = sc_tree.num_weeks()
    total_leaf_s   = sum(len(leaf_node.psi4supply[w][S]) for w in range(weeks_n))
    total_dad_s    = sum(len(dad_node.psi4supply[w][S])  for w in range(weeks_n))
    dad_actual_s   = fp._actual_s.get(dad_node.node_id, {})
    total_dad_real = sum(len(dad_actual_s.get(w, []))    for w in range(weeks_n))
    total_dad_co   = sum(len(dad_node.psi4supply[w][CO]) for w in range(weeks_n))

    print(result)
    print(f"cap_hard_events: {result.cap_hard_events}")
    print(f"leaf_out total S(planned)={total_leaf_s}, "
          f"DAD total S(planned)={total_dad_s}, "
          f"DAD actual shipped={total_dad_real}, DAD CO(carried)={total_dad_co}  "
          f"(demand=4, cap_hard=2)")

    # Both leaf_out and DAD are demand-anchored in the planned/S bucket now.
    assert total_leaf_s == 4, (
        f"leaf_out.S (planned) should be 4 (demand-anchored), got {total_leaf_s}"
    )
    assert total_dad_s == 4, (
        f"DAD.S (planned) should be 4 (demand-anchored, no longer clipped "
        f"in-place), got {total_dad_s}"
    )
    # DAD's REAL physical shipment is what's actually capped at 2 by MOM cap_hard.
    assert total_dad_real <= 2, (
        f"DAD actual shipped should be <=2 (constrained by MOM cap_hard=2), "
        f"got {total_dad_real}"
    )
    # v1r0m3: ForwardPlanner enforces cap_hard; demand=4, cap=2 -> 2 sealed.
    assert result.cap_hard_sealed == 2, (
        f"v1r0m3: ForwardPlanner seals excess at MOM, expected 2 got {result.cap_hard_sealed}"
    )
    # decouple essence: shortfall is absorbed as CO at DAD, not passed to leaf.
    assert total_dad_co >= 2, (
        f"DAD.CO should reflect the >=2-lot shortfall absorbed at the "
        f"decouple point, got {total_dad_co}"
    )

    print("PASS: test_e2e_cap_hard_causes_leaf_shortfall (Lot_ID identity decouple)")


# ---------------------------------------------------------------------------
# Test 7: build_capacity_load_report
# ---------------------------------------------------------------------------

def test_capacity_load_report():
    """
    After forward planning, build_capacity_load_report returns
    utilisation summaries for all weeks with capacity set.
    """
    sc_tree, weeks, sku_id, mom = build_tree_with_demand(
        cap_hard=3.0, cap_soft=2.0, demand_qty=4
    )

    fp = ForwardPlanner(sc_tree)
    fp.run(sku_id)

    report = build_capacity_load_report(sc_tree, sku_id)
    print(f"Report entries: {len(report)}")
    for row in report:
        if row.p_qty > 0:
            print(f"  {row.node_id}  {row.week}  P={row.p_qty}  "
                  f"H={row.cap_hard}  S={row.cap_soft}  "
                  f"over_hard={row.over_hard}  over_soft={row.over_soft}")

    assert len(report) > 0, "Expected non-empty report when capacity is set"
    print("PASS: test_capacity_load_report")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_cap_hard_sealing,
        test_cap_soft_violation_no_movement,
        test_combined_cap_hard_soft,
        test_capacity_profile_apply,
        test_build_mom_capacity_profile,
        test_e2e_cap_hard_causes_leaf_shortfall,
        test_capacity_load_report,
    ]
    for t in tests:
        print(f"\n{'='*60}")
        print(f"Running {t.__name__} ...")
        t()
    print(f"\n{'='*60}")
    print("All Step 7 capacity tests passed.")
