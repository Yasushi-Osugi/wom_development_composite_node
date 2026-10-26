# -*- coding: utf-8 -*-
"""
tests/conftest.py — test tiers: area markers, smoke, slow (RequestLetter_QuickCheckTests)
=======================================================================================
The ONE place that says which area each test file belongs to. The test files
themselves carry no markers; this hook adds them at collection time.

  AREAS  file name -> areas (a file may belong to several)
  SMOKE  file names, or "file::test" prefixes, that make up the smoke tier
  SLOW   tests that took >= 20 s in the measured full run (2026-10-15, Windows)

Adding a new test file: add one line to AREAS (tests/test_test_areas.py fails
until you do). Markers are registered in pytest.ini (--strict-markers).
How to run the tiers: tools/quick_check.py and tests/README.md.
"""
import pytest

AREA_NAMES = ("core", "capacity", "rice", "plugins", "ppc", "allocation",
              "lovem", "gui", "worldmap", "golden", "public")

AREAS = {
    # core: Planning Engine and the Unit / Integration layers of the 3-layer tests
    "test_backward_holiday_carryback.py": ("core",),
    "test_backward_supply_role.py": ("core",),
    "test_bom_qty.py": ("core",),
    "test_capacity_soft.py": ("core",),
    "test_capacity_soft_backward.py": ("core",),
    "test_capacity_zero_blank.py": ("core",),
    "test_composite_kitting_recovery.py": ("core",),
    "test_demand_envelope_soft.py": ("core",),
    "test_ev_update_kitting.py": ("core",),
    "test_flow_check.py": ("core",),
    "test_holiday_explicit_closure.py": ("core", "plugins"),
    "test_init_stock_days_wiring.py": ("core",),
    "test_kitting_stage1.py": ("core",),
    "test_lot_identity_flow.py": ("core",),
    "test_operating_calendar.py": ("core",),
    "test_plan_period.py": ("core",),
    "test_planning_state.py": ("core",),
    "test_push_pull_mode4_double_count.py": ("core",),
    "test_push_pull_mode4_supply_role.py": ("core",),
    "test_report_start.py": ("core", "rice"),
    "test_s2_actual_shipment_eval.py": ("core", "ppc"),
    "test_shift_cap_soft.py": ("core",),
    "test_stage3a1_stockyard.py": ("core",),
    "test_stage3a2_kitting_gate.py": ("core",),
    "test_stage_d_part0.py": ("core", "ppc"),
    "test_step7_capacity.py": ("core",),
    "test_step8_push_pull.py": ("core",),
    "test_warmup_materialize.py": ("core",),
    "test_yield_rate_part_a.py": ("core", "capacity"),
    "test_warmup_soft_blank_attrs_fifo.py": ("core",),
    "test_quantity_allocation.py": ("allocation", "core"),
    # capacity: the upper (capacity) layer
    "test_capacity_layer_trial.py": ("capacity",),
    "test_cpu_size_plan_wide.py": ("capacity",),
    "test_generation_line_upper_layer.py": ("capacity",),
    # rice
    "test_rice_retire.py": ("rice",),
    "test_lesson000_variants.py": ("rice", "public"),
    "test_rice_seasonal_layer.py": ("rice", "capacity"),
    "test_rice_seasonal_trial.py": ("rice", "capacity"),
    # plugins
    "test_buffering_stock_optimizer_plugin.py": ("plugins",),
    "test_decouple_optimizer.py": ("plugins",),
    "test_step10_hooks.py": ("plugins",),
    # ppc / Value Chain / money
    "test_money_units.py": ("ppc",),
    "test_ppc_bom_qty.py": ("ppc",),
    "test_ppc_multi_supplier.py": ("ppc",),
    "test_ppc_no_silent_fallback.py": ("ppc",),
    "test_ppc_run_info.py": ("ppc", "gui"),
    "test_ppc_vertical_slice.py": ("ppc",),
    "test_valuechain_handcalc.py": ("ppc",),
    "test_valuechain_integration.py": ("ppc",),
    # allocation (Management layer)
    "test_allocation_analytics.py": ("allocation",),
    "test_allocation_cli.py": ("allocation",),
    "test_allocation_cost_block.py": ("allocation",),
    "test_allocation_grid.py": ("allocation",),
    "test_allocation_hierarchical.py": ("allocation",),
    "test_allocation_material_invariant.py": ("allocation",),
    "test_allocation_merit_order.py": ("allocation",),
    "test_allocation_nmarket.py": ("allocation",),
    "test_allocation_nonconcave.py": ("allocation",),
    "test_allocation_plot.py": ("allocation",),
    "test_allocation_regime_map.py": ("allocation",),
    "test_allocation_transmission.py": ("allocation",),
    "test_merit_order.py": ("allocation",),
    "test_merit_order_plot.py": ("allocation",),
    "test_pareto_front.py": ("allocation",),
    "test_regime_map.py": ("allocation",),
    "test_s1_view_model.py": ("allocation", "gui"),
    # lovem
    "test_lovem_interval_check.py": ("lovem",),
    "test_lovem_intervals.py": ("lovem",),
    "test_lovem_observer.py": ("lovem",),
    "test_lovem_viewer.py": ("lovem", "gui"),
    # gui (opens tkinter windows)
    "test_gui_panel_invariants.py": ("gui",),
    "test_sim_mgmt_display.py": ("gui",),
    # worldmap
    "test_worldmap_actual_flows.py": ("worldmap", "gui"),
    "test_worldmap_ne.py": ("worldmap", "gui"),
    # golden (E2E)
    "test_golden.py": ("golden",),
    # public
    "test_no_real_names.py": ("public",),
    "test_public_readiness.py": ("public", "plugins"),
    "test_smartx_evidence_ranges.py": ("public",),
    # the tiers themselves
    "test_test_areas.py": ("public",),
}

SMOKE = (
    # core: Unit / Integration layers of the 3-layer tests (each file < 3 s)
    "test_lot_identity_flow.py",
    "test_capacity_soft.py",
    "test_capacity_soft_backward.py",
    "test_capacity_zero_blank.py",
    "test_step7_capacity.py",
    "test_step8_push_pull.py",
    "test_backward_supply_role.py",
    "test_backward_holiday_carryback.py",
    "test_push_pull_mode4_supply_role.py",
    "test_operating_calendar.py",
    "test_shift_cap_soft.py",
    "test_demand_envelope_soft.py",
    "test_init_stock_days_wiring.py",
    "test_bom_qty.py",
    "test_kitting_stage1.py",
    "test_composite_kitting_recovery.py",
    "test_warmup_materialize.py",
    "test_plan_period.py",
    "test_flow_check.py",
    "test_report_start.py",
    # golden: the two smallest models
    "test_golden.py::test_golden_matches[bom-test-2026]",
    "test_golden.py::test_golden_matches[Cookie-jp-2026]",
    # one or more fast, representative files per other area
    "test_capacity_layer_trial.py",
    "test_cpu_size_plan_wide.py",
    "test_rice_seasonal_trial.py",
    "test_rice_retire.py",
    "test_lesson000_variants.py",
    "test_step10_hooks.py",
    "test_buffering_stock_optimizer_plugin.py",
    "test_decouple_optimizer.py",
    "test_ppc_vertical_slice.py",
    "test_valuechain_handcalc.py",
    "test_money_units.py",
    "test_merit_order.py",
    "test_allocation_transmission.py",
    "test_allocation_nonconcave.py",
    "test_pareto_front.py",
    "test_lovem_intervals.py",
    "test_s1_view_model.py",
    "test_sim_mgmt_display.py",
    "test_worldmap_ne.py",
    "test_public_readiness.py",
    "test_smartx_evidence_ranges.py",
    # always
    "test_no_real_names.py",
    "test_test_areas.py",
)

SLOW = frozenset((
    "test_lovem_observer.py::test_intervals_restore_every_digest",              # 89.6 s
    "test_lovem_observer.py::test_se2_168_is_reproduced",                       # 88.3 s
    "test_lovem_observer.py::test_q12_observation_does_not_change_the_plan",    # 86.6 s
    "test_generation_line_upper_layer.py::test_plugin_on_keeps_market_ids_and_ships_nothing_early",  # 67.2 s
    "test_valuechain_integration.py::test_alloc_sample_prices_leave_nothing_unvalued",  # 61.9 s
    "test_valuechain_integration.py::test_alloc_ledger_records_match_the_plan",         # 57.5 s
    "test_rice_seasonal_layer.py::test_k_r10_migration_copy_regression",       # 42.6 s
))


def _key(item):
    """'test_x.py::test_name[param]' -- independent of the rootdir."""
    path = item.nodeid.split("::")[0]
    return path.replace("\\", "/").split("/")[-1] + item.nodeid[len(path):]


def _in_smoke(key):
    return any(key == s or key.startswith(s + "::") or key.startswith(s + "[") for s in SMOKE)


def pytest_collection_modifyitems(config, items):
    for item in items:
        key = _key(item)
        fname = key.split("::")[0]
        for area in AREAS.get(fname, ()):
            item.add_marker(getattr(pytest.mark, area))
        if _in_smoke(key):
            item.add_marker(pytest.mark.smoke)
        if key in SLOW:
            item.add_marker(pytest.mark.slow)
