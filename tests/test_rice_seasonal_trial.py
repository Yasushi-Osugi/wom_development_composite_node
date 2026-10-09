"""Hand calculation, physical-resource allocation, CSV -> identity Forward.

Original Rice / HarvestBatch / goldens untouched. Physical masses are checked
independently of PSI counts. Hypothetical quantities are not sample-data facts.
"""
from dataclasses import replace
from fractions import Fraction

import pytest

from wom.capacity_layer.rice_trial import (
    RiceDemand, RicePolicy, build_problem, solve, assignments,
    physical_ledger, apply_to_tree,
)
from tools.probe_rice_seasonal_definition import (
    fixture_problem, fixture_tree, run_forward_variant, verify_forward,
)


def test_one_id_hand_calculation_and_exact_material_balance():
    rice, _ = fixture_problem()
    sol = solve(rice)
    t = next(iter(assignments(rice, sol).values()))
    assert [rice.weeks[getattr(t, n)] for n in
            ("harvest", "collection", "store_arrival", "store_departure", "polish", "dc", "due")] == [
        "2026-W43", "2026-W44", "2026-W45", "2026-W50", "2026-W52", "2026-W53", "2027-W01"]
    rows = physical_ledger(rice, sol)
    assert [r["week"] for r in rows if r["stage"] == "brown_inventory"] == [
        "2026-W45", "2026-W46", "2026-W47", "2026-W48", "2026-W49"]
    assert [r["week"] for r in rows if r["node_or_lane"].startswith("Genmai_Souko_Niigata->")] == [
        "2026-W50", "2026-W51"]
    for row in rows:
        assert Fraction(row["mass_kg_exact"]) + Fraction(row["other_output_kg_exact"]) == Fraction(100, 9)
    assert rows[-1]["mass_kg_exact"] == "10" and rows[-1]["other_output_kg_exact"] == "10/9"
    assert sol.diagnostics["brown_storage_kg_weeks"] == pytest.approx(500 / 9)
    assert sol.diagnostics["white_prebuild_lot_weeks"] == 0


def test_real_csv_route_and_independent_forward_put_inventory_in_brown_store():
    rice, _ = fixture_problem()
    tree, result, check = run_forward_variant("seasonal", rice, solve(rice))
    nodes = {n.node_name: n for n in tree.iter_all_nodes("Koshihikari")}
    lot = "Koshihikari:KANSAI:2027-W01:00001"
    store = nodes["Genmai_Souko_Niigata"]
    assert [tree.week_labels[w] for w, row in enumerate(store.psi4supply) if row[2]] == [
        "2026-W45", "2026-W46", "2026-W47", "2026-W48", "2026-W49"]
    assert all(row[2] in ([], [lot]) for row in store.psi4supply)
    assert nodes["Seihaku_W"]._actual_ship[tree.week_labels.index("2026-W52")] == [lot]
    assert nodes["Retail_KANSAI"]._actual_ship[tree.week_labels.index("2027-W01")] == [lot]
    assert sum(len(row[2]) for row in nodes["Retail_KANSAI"].psi4supply) == 0
    assert check["on_time_IDs"] == 1 and check["early_IDs"] == check["late_IDs"] == 0
    assert check["actual_ship_events"] == 7
    assert not any(check[k] for k in ("inventory_errors", "CO_errors",
                                     "receipt_from_actual_errors", "duplicate_supply", "end_unmet_IDs"))
    assert result.cap_hard_deferred_lots == 0 and result.opening_inv_counts == {}


def test_current_plain_backward_cannot_assign_past_harvest():
    rice, _ = fixture_problem()
    _, _, check = run_forward_variant("plain", rice)
    assert check["on_time_IDs"] == 0 and len(check["end_unmet_IDs"]) == 1


def test_current_serial_adapter_serves_id_but_holds_white_rice_at_market():
    rice, _ = fixture_problem()
    tree, _, check = run_forward_variant("serial", rice)
    nodes = {n.node_name: n for n in tree.iter_all_nodes("Koshihikari")}
    assert check["on_time_IDs"] == 1 and check["early_IDs"] == 0
    assert sum(len(row[2]) for row in nodes["Genmai_Souko_Niigata"].psi4supply) == 0
    assert [tree.week_labels[w] for w, row in enumerate(nodes["Retail_KANSAI"].psi4supply) if row[2]] == [
        "2026-W49", "2026-W50", "2026-W51", "2026-W52", "2026-W53"]


def test_zero_harvest_capacity_keeps_original_request_as_backlog():
    def zero(caps, budgets, route, weeks):
        for w in range(len(weeks)):
            caps[route.resources["harvest"], w] = 0
    rice, _ = fixture_problem(mutate=zero)
    sol = solve(rice)
    assert sol.served == 0 and sum(sol.unmet.values()) == 1
    tree, _, check = run_forward_variant("seasonal", rice, sol)
    market = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_type == "leaf_out")
    assert market.psi4demand[-1][0] == ["Koshihikari:KANSAI:2027-W01:00001"]
    assert len(check["end_unmet_IDs"]) == 1


def test_crop_yield_is_independent_of_sum_of_weekly_harvest_capacities():
    def crop(caps, budgets, route, weeks):
        for k in caps:
            if k[0] != route.resources["harvest"]:
                caps[k] = 100
        budgets[route.resources["harvest"], "2026_crop"] = float(route.raw_kg_per_lot)
    rice, _ = fixture_problem(demand_count=2, mutate=crop)
    sol = solve(rice)
    assert sol.served == 1 and sum(sol.unmet.values()) == 1


def test_storage_limit_is_physical_raw_kg_and_never_fractional_lot_shipping():
    def storage(caps, budgets, route, weeks):
        for w in range(len(weeks)):
            caps[route.resources["storage"], w] = 10
    rice, _ = fixture_problem(mutate=storage)
    assert solve(rice).served == 0  # 10 kg cannot hold 100/9 kg for one demand ID
    relaxation = solve(rice, "lp")
    assert relaxation.relaxation_upper_bound == pytest.approx(0.9)
    assert relaxation.served == 0 and relaxation.fractional_cells > 0


def test_polishing_capacity_unavailable_differs_from_harvest_shortage():
    def milling(caps, budgets, route, weeks):
        caps[route.resources["polish"], weeks.index("2026-W52")] = 0
    rice, _ = fixture_problem(mutate=milling)
    assert solve(rice).served == 0
    earlier, _ = fixture_problem(policy=RicePolicy(13, 10, 1), mutate=milling)
    sol = solve(earlier)
    t = next(iter(assignments(earlier, sol).values()))
    assert sol.served == 1 and earlier.weeks[t.polish] == "2026-W51"
    assert sol.diagnostics["white_prebuild_lot_weeks"] == 1


@pytest.mark.parametrize("policy", [RicePolicy(10, 10, 0), RicePolicy(13, 4, 0)])
def test_harvest_window_and_brown_age_are_separate_limits(policy):
    rice, _ = fixture_problem(policy=policy)
    assert solve(rice).served == 0


def test_missing_capacity_is_error_and_explicit_none_is_distinct():
    def unset(caps, budgets, route, weeks):
        for w in range(len(weeks)):
            caps[route.resources["storage"], w] = None
    rice, _ = fixture_problem(mutate=unset)
    assert solve(rice).served == 1
    def missing(caps, budgets, route, weeks):
        del caps[route.resources["storage"], 0]
    with pytest.raises(ValueError, match="Missing explicit capacity"):
        fixture_problem(mutate=missing)


def test_shared_milling_resource_is_one_constraint_across_products():
    rice, _ = fixture_problem()
    r1 = next(iter(rice.routes.values()))
    r2 = replace(r1, key="second", product="OTHER", market="OtherMarket")
    caps = {k: 1000.0 for k in rice.problem.capacities if not k[0].startswith("crop:")}
    for w in range(len(rice.weeks)):
        caps[r1.resources["polish"], w] = float(r1.raw_kg_per_lot)
    harvest = {(r1.resources["harvest"], rice.weeks.index(w)): "2026_crop"
               for w in ("2026-W41", "2026-W42", "2026-W43")}
    demands = [RiceDemand("original_K", r1.key, 13), RiceDemand("original_OTHER", r2.key, 13)]
    shared = build_problem(demands, [r1, r2], rice.weeks, RicePolicy(13, 10, 0), caps,
                           harvest, {(r1.resources["harvest"], "2026_crop"): 1000})
    sol = solve(shared)
    assert sol.served == 1 and sum(sol.unmet.values()) == 1


def test_lp_relaxation_upper_bound_does_not_imply_one_whole_id_is_feasible():
    def half(caps, budgets, route, weeks):
        for label in ("2026-W41", "2026-W42", "2026-W43"):
            caps[route.resources["harvest"], weeks.index(label)] = float(route.raw_kg_per_lot) / 2
    rice, _ = fixture_problem(mutate=half)
    lp = solve(rice, "lp")
    assert lp.relaxation_upper_bound == pytest.approx(1)
    assert lp.fractional_cells > 0 and lp.served == 0
    assert solve(rice).served == 0


@pytest.mark.parametrize("yield_value", [Fraction(0), Fraction(-1), Fraction(11, 10)])
def test_invalid_yield_is_error(yield_value):
    rice, _ = fixture_problem()
    route = replace(next(iter(rice.routes.values())), milling_yield=yield_value)
    with pytest.raises(ValueError, match="yield"):
        build_problem([], [route], rice.weeks, RicePolicy(13, 10, 0), {}, {}, {})


def test_market_id_mismatch_is_rejected_before_internal_plan_is_changed():
    rice, _ = fixture_problem()
    tree = fixture_tree()
    market = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_type == "leaf_out")
    market.psi4demand[-1][0] = ["other_ID"]
    original = [row[:] for row in tree.get_in_root("Koshihikari").psi4demand]
    with pytest.raises(ValueError, match="Market requests"):
        apply_to_tree(rice, solve(rice), tree)
    assert tree.get_in_root("Koshihikari").psi4demand == original


def test_forward_is_an_independent_gate_if_capacity_changes_after_allocation():
    from wom.engine.plan_copy import copy_demand_to_supply
    from wom.engine.forward_planner import ForwardPlanner
    rice, _ = fixture_problem()
    tree = fixture_tree()
    market = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_type == "leaf_out")
    original = [list(c[0]) for c in market.psi4demand]
    apply_to_tree(rice, solve(rice), tree)
    mill = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_name == "Seihaku_W")
    mill.set_capacity(tree.week_labels.index("2026-W52"), cap_hard=0)
    copy_demand_to_supply(tree, "Koshihikari")
    result = ForwardPlanner(tree, lot_flow_mode="identity").run("Koshihikari")
    check = verify_forward(tree, original)
    assert result.cap_hard_deferred_lots == 1
    assert check["on_time_IDs"] == 0 and len(check["end_unmet_IDs"]) == 1
    assert check["market_S_unchanged"]


def test_undeclared_closure_is_refused_by_trial_engine_bridge():
    rice, _ = fixture_problem()
    tree = fixture_tree()
    tree.get_in_root("Koshihikari").set_operating_shifts(0, 0)
    with pytest.raises(ValueError, match="closure"):
        apply_to_tree(rice, solve(rice), tree)


def test_storage_stock_and_throughput_cannot_share_one_resource_unit():
    rice, _ = fixture_problem()
    route = next(iter(rice.routes.values()))
    resources = dict(route.resources)
    resources["storage"] = resources["polish"]
    bad = replace(route, resources=resources)
    with pytest.raises(ValueError, match="Mixed physical resource"):
        build_problem([], [bad], rice.weeks, RicePolicy(13, 10, 0), {}, {}, {})


def test_cpu_size_physical_conversion_does_not_change_demand_id_count():
    from tools.probe_rice_seasonal_definition import FIXTURE
    import pandas as pd
    demand = pd.read_csv(FIXTURE / "demand_forecast.csv")
    assert demand.quantity.sum() == 1
    tree = fixture_tree()
    market = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_type == "leaf_out")
    assert sum(len(row[0]) for row in market.psi4demand) == 1


def test_storage_checks_receipt_peak_before_withdrawal_not_just_end_stock():
    def departing_week_full(caps, budgets, route, weeks):
        caps[route.resources["storage"], weeks.index("2026-W50")] = 0
    rice, _ = fixture_problem(mutate=departing_week_full)
    # All feasible harvests withdraw in W50; end I there would be zero.
    # That does not justify loading a zero-capacity warehouse that week.
    assert solve(rice).served == 0
