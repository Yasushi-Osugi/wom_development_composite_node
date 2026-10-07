# -*- coding: utf-8 -*-
"""RequestLetter_GenerationLine_UpperLayer — generation switch line and the upper capacity layer.

Unit        : line capacity from the peak demand, the line schedule (no mixed
              flow, the gap), the switch evaluation on a hand-calculated tree,
              the choice of s*, the tree adapter (push modes, unsupported trees).
Integration : the capacity row tool on a copy of smartx -> the real loader
              (0 is zero capacity, every week written); the plugin's settings.
E2E         : the plugin ON on a copy of smartx keeps every market Lot_ID and
              request week, ships nothing early and leaves no capacity deferral
              (about 1.5 minutes).
"""
from __future__ import annotations

import csv
import os
import shutil

import pandas as pd
import pytest

from wom.capacity_layer.generation_line import (LineCapacity, best_switch, evaluate_switch,
                                                line_capacity_from_demand, line_schedule)
from wom.capacity_layer.serial_adapter import (SerialLineAdapter, UnsupportedTreeError,
                                               push_modes)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SMARTX = os.path.join(REPO, "data", "sample", "smartx-2027-2029")
WEEKS = [f"2027-W{w:02d}" for w in range(1, 13)]


# ── unit: line capacity and schedule ────────────────────────────────────────
def test_line_capacity_is_peak_times_factor_rounded_up():
    rows = [{"sku_id": "A", "week": "W1", "quantity": 600}, {"sku_id": "A", "week": "W1", "quantity": 707},
            {"sku_id": "A", "week": "W2", "quantity": 1000}, {"sku_id": "B", "week": "W1", "quantity": 9999}]
    c = line_capacity_from_demand(rows, "A", 1.1)
    assert c == LineCapacity("A", "W1", 1307, 1.1, 1438)          # 1437.7 -> 1438
    assert line_capacity_from_demand([{"sku_id": "A", "week": "W1", "quantity": 1000}], "A", 1.1).capacity == 1100
    assert line_capacity_from_demand([{"sku_id": "A", "week": "W1", "quantity": 3375}], "A", 1.1).capacity == 3713
    with pytest.raises(ValueError):
        line_capacity_from_demand(rows, "C", 1.1)


def test_line_schedule_never_mixes_and_keeps_the_gap():
    old, new = line_schedule(12, 5, 4, 1438, 3713)
    assert old == [1438.0] * 5 + [0.0] * 7
    assert new == [0.0] * 9 + [3713.0] * 3
    assert all(not (o > 0 and n > 0) for o, n in zip(old, new))
    assert all(old[w] == 0 and new[w] == 0 for w in range(5, 9))  # the 4 changeover weeks
    old0, new0 = line_schedule(12, 5, 0, 1, 1)
    assert old0[4] == 1 and old0[5] == 0 and new0[5] == 1
    with pytest.raises(ValueError):
        line_schedule(12, 13, 4, 1, 1)
    with pytest.raises(ValueError):
        line_schedule(12, 5, -1, 1, 1)


def test_best_switch_quantity_first_then_inventory_then_earliest():
    rows = [{"s_index": 1, "unallocated_total": 5, "advance_lot_weeks_total": 1},
            {"s_index": 2, "unallocated_total": 3, "advance_lot_weeks_total": 50},
            {"s_index": 3, "unallocated_total": 3, "advance_lot_weeks_total": 40},
            {"s_index": 4, "unallocated_total": 3, "advance_lot_weeks_total": 40}]
    assert best_switch(rows)["s_index"] == 3
    assert best_switch([]) is None


# ── a hand-calculated two-generation tree ───────────────────────────────────
def _tree(old_demand, new_demand):
    """OLD and NEW: market <- SP (lt 0) | Line (mom root) <- Src (leaf_in, lt 0).

    All lead times are 0, so the line week equals the market week.
    """
    from wom.engine.sc_tree_builder import build_sc_tree_from_master
    from wom.model.lot_generator import assign_demand_lots_from_dict
    rows = []
    for p in ("OLD", "NEW"):
        rows += [
            {"node_name": f"SP_{p}", "parent_node": "", "product_name": p, "node_type": "supply_point",
             "side": "outbound", "lt_wks": 0, "region": ""},
            {"node_name": f"Mkt_{p}", "parent_node": f"SP_{p}", "product_name": p, "node_type": "leaf_out",
             "side": "outbound", "lt_wks": 0, "region": "JP"},
            {"node_name": f"Line_{p}", "parent_node": "", "product_name": p, "node_type": "mom",
             "side": "inbound", "lt_wks": 0, "region": ""},
            {"node_name": f"Src_{p}", "parent_node": f"Line_{p}", "product_name": p, "node_type": "leaf_in",
             "side": "inbound", "lt_wks": 0, "region": ""},
        ]
    tree = build_sc_tree_from_master(pd.DataFrame(rows), WEEKS)
    dem = {}
    for p, d in (("OLD", old_demand), ("NEW", new_demand)):
        for w, q in d.items():
            dem[(p, "JP", WEEKS[w])] = q
    assign_demand_lots_from_dict(tree, dem)
    return tree


def _gens(tree, window):
    out = []
    for p in ("OLD", "NEW"):
        ad = SerialLineAdapter.from_tree(tree, [p])
        out.append((ad, ad.problem_from_tree(tree, p, window), f"Line_{p}"))
    return out


def test_switch_hand_calculation():
    # OLD: 2 lots in weeks 1..9 (18). Line 3/wk in weeks 0..5 (s=6) -> 10 lots on time
    # in weeks 1..5, spare 3+1+1+1+1+1 = 8 = the 8 lots due in weeks 6..9, all
    # prebuilt: advance = (6+6+7+7+8+8+9+9) - (0+0+0+1+2+3+4+5) = 60 - 15 = 45.
    # NEW: 3 lots in weeks 6..11 (18). Gap 2 -> line from week 8 at 4/wk: the 6
    # lots due in weeks 6 and 7 cannot be made (no later production counts).
    tree = _tree({w: 2 for w in range(1, 10)}, {w: 3 for w in range(6, 12)})
    old, new = _gens(tree, window=17)
    r = evaluate_switch(old, new, 6, 2, 3, 4)
    assert (r["old_served"], r["old_unallocated"], r["old_advance_lot_weeks"]) == (18, 0, 45)
    assert (r["new_served"], r["new_unallocated"], r["new_advance_lot_weeks"]) == (12, 6, 0)
    assert r["unallocated_total"] == 6 and r["old_lots_due_after_s"] == 8
    assert r["old_fractional_cells"] == 0 and r["new_fractional_cells"] == 0


def test_switch_window_limits_the_prebuild():
    # Window 2: a lot due in week d can be made in d-2..d only. Due 6 -> weeks 4,5;
    # due 7 -> week 5; due 8, 9 -> nothing before s (4 lots lost). Weeks 4 and 5
    # (capacity 6) can take all 4 lots due 6 and 7, because their own lots (due
    # 4, 5) move to weeks 2..4 and those of weeks 2, 3 to weeks 0, 1 (chain of
    # 1-2 week advances, each inside the window) -> 14 served, 4 unallocated.
    tree = _tree({w: 2 for w in range(1, 10)}, {w: 3 for w in range(6, 12)})
    old, new = _gens(tree, window=2)
    r = evaluate_switch(old, new, 6, 2, 3, 4)
    assert (r["old_served"], r["old_unallocated"]) == (14, 4)
    assert r["old_lots_due_after_s"] == 4


def test_adapter_keeps_original_lots_and_lists_unallocated():
    from wom.capacity_layer.solver import solve_lp
    tree = _tree({1: 2}, {6: 3})
    ad = SerialLineAdapter.from_tree(tree, ["NEW"])
    prob = ad.problem_from_tree(tree, "NEW", 3)
    nid = next(n for n, r in ad.nodes.items() if r["node_name"] == "Line_NEW")
    for w in range(len(WEEKS)):
        prob.capacities[nid, w] = 1.0 if w == 5 else 0.0
        prob.capacities["backward_root:" + nid, w] = prob.capacities[nid, w]
    rows = ad.expand(prob, solve_lp(prob))
    mkt = next(n for n in tree.iter_all_nodes("NEW") if n.node_type == "leaf_out")
    original = list(mkt.psi4demand[6][0])
    assert [r["lot_id"] for r in rows] == original                   # same IDs, same order
    assert [r["status"] for r in rows] == ["assigned", "unallocated", "unallocated"]
    assert rows[0]["plan_week"] == WEEKS[5] and rows[0]["due_week"] == WEEKS[6]
    placed = ad.apply_positions(tree, "NEW", rows)
    assert placed == 1 and list(mkt.psi4demand[6][0]) == original       # market S untouched
    line = next(n for n in tree.iter_all_nodes("NEW") if n.node_name == "Line_NEW")
    assert line.psi4demand[5][3] == [original[0]] and not line.psi4demand[6][3]


def test_push_modes_follow_the_push_setup_rule():
    from wom.engine.sc_tree_builder import build_sc_tree_from_master
    rows = [{"node_name": "SP", "parent_node": "", "product_name": "A", "node_type": "supply_point", "side": "outbound", "lt_wks": 0, "region": ""},
            {"node_name": "M", "parent_node": "SP", "product_name": "A", "node_type": "leaf_out", "side": "outbound", "lt_wks": 1, "region": "JP"},
            {"node_name": "Asm", "parent_node": "", "product_name": "A", "node_type": "mom", "side": "inbound", "lt_wks": 0, "region": ""},
            {"node_name": "Fab", "parent_node": "Asm", "product_name": "A", "node_type": "mom", "side": "inbound", "lt_wks": 2, "region": ""},
            {"node_name": "Buf", "parent_node": "Fab", "product_name": "A", "node_type": "mom", "side": "inbound", "lt_wks": 0, "region": ""},
            {"node_name": "Raw", "parent_node": "Buf", "product_name": "A", "node_type": "leaf_in", "side": "inbound", "lt_wks": 3, "region": ""}]
    tree = build_sc_tree_from_master(pd.DataFrame(rows), WEEKS)
    m = push_modes(tree, "A", ["Buf"])
    by = {n.node_name: m[n.node_id] for n in tree.iter_all_nodes("A")}
    assert by["Buf"] == "push" and by["Raw"] == "push_sub"
    assert by["Fab"] == "push_sub" and by["Asm"] == "push_sub"
    assert by["M"] == "pull"
    with pytest.raises(UnsupportedTreeError):
        push_modes(tree, "A", ["Nope"])


def test_branched_inbound_is_refused():
    from wom.engine.sc_tree_builder import build_sc_tree_from_master
    rows = [{"node_name": "SP", "parent_node": "", "product_name": "A", "node_type": "supply_point", "side": "outbound", "lt_wks": 0, "region": ""},
            {"node_name": "M", "parent_node": "SP", "product_name": "A", "node_type": "leaf_out", "side": "outbound", "lt_wks": 1, "region": "JP"},
            {"node_name": "Asm", "parent_node": "", "product_name": "A", "node_type": "mom", "side": "inbound", "lt_wks": 0, "region": ""},
            {"node_name": "T", "parent_node": "Asm", "product_name": "A", "node_type": "leaf_in", "side": "inbound", "lt_wks": 1, "region": ""},
            {"node_name": "B", "parent_node": "Asm", "product_name": "A", "node_type": "leaf_in", "side": "inbound", "lt_wks": 1, "region": ""}]
    tree = build_sc_tree_from_master(pd.DataFrame(rows), WEEKS)
    with pytest.raises(UnsupportedTreeError, match="branched"):
        SerialLineAdapter.from_tree(tree, ["A"])


# ── integration: capacity rows -> real loader ──────────────────────────────
def test_generation_line_rows_load_as_zero_and_never_mix(tmp_path):
    from tools.gen_generation_line_capacity import build_rows, write_rows
    from wom.engine.warmup import materialize_warmup
    from wom.engine.capacity_sealer import load_capacity_dataframe
    from wom.engine.plan_period import detect_plan_period
    from wom.engine.sc_tree_builder import build_sc_tree_from_master
    work = tmp_path / "smartx"
    shutil.copytree(SMARTX, work)
    before = open(work / "capacity_plan.csv", encoding="utf-8").read().splitlines()
    header, rows, info = build_rows(str(work), ("SmartX", "AssemblyCN_g1"), ("SmartXNext", "AssemblyCN_g3"),
                                    "2028-W40", 4, 1438, 3713)
    write_rows(str(work / "capacity_plan.csv"), header, rows)
    materialize_warmup(str(work))
    after = open(work / "capacity_plan.csv", encoding="utf-8").read().splitlines()
    keep = lambda lines: [l for l in lines if "AssemblyCN_g1" not in l and "AssemblyCN_g3" not in l]
    assert keep(before) == keep(after)                                  # other rows untouched
    weeks = list(detect_plan_period(str(work / "demand_forecast.csv")).weeks)
    tree = build_sc_tree_from_master(pd.read_csv(work / "sc_tree_master.csv"), weeks)
    load_capacity_dataframe(tree, pd.read_csv(work / "capacity_plan.csv", dtype={"max_supply": str}), weeks)
    g1 = next(n for n in tree.iter_all_nodes("SmartX") if n.node_name == "AssemblyCN_g1")
    g3 = next(n for n in tree.iter_all_nodes("SmartXNext") if n.node_name == "AssemblyCN_g3")
    s = weeks.index("2028-W40")
    for w in range(len(weeks)):                                       # every week is set
        assert g1.cap_hard(w) is not None and g3.cap_hard(w) is not None
        assert not (g1.cap_hard(w) > 0 and g3.cap_hard(w) > 0)
    assert g1.cap_hard(0) == 1438 and g1.cap_hard(s - 1) == 1438 and g1.cap_hard(s) == 0
    assert all(g1.cap_hard(w) == 0 == g3.cap_hard(w) for w in range(s, s + 4))
    assert g3.cap_hard(s + 4) == 3713 and g3.cap_hard(0) == 0
    # idempotent: a second materialize leaves the file as it is
    assert materialize_warmup(str(work))["files"]["capacity_plan.csv"]["changed"] is False


# ── integration: plugin settings ────────────────────────────────────────────
def test_plugin_needs_its_settings_file(tmp_path):
    from wom.plugins.capacity_layer import (CapacityLayerConfigError, CapacityLayerPlugin,
                                            read_layer_config)
    cfg = {"cap_path": str(tmp_path / "capacity_plan.csv")}
    with pytest.raises(CapacityLayerConfigError, match="capacity_layer_config.csv"):
        CapacityLayerPlugin().on_pre_plan(_tree({1: 1}, {6: 1}), WEEKS, cfg)
    (tmp_path / "capacity_layer_config.csv").write_text("key,value\nmax_advance_weeks,x\n", encoding="utf-8")
    with pytest.raises(CapacityLayerConfigError, match="whole number"):
        read_layer_config(str(tmp_path))
    (tmp_path / "capacity_layer_config.csv").write_text("key,value\nmax_advance_weeks,17\n", encoding="utf-8")
    assert read_layer_config(str(tmp_path))["max_advance_weeks"] == 17


def test_plugin_is_off_by_default():
    import tools.run_headless_from_folder as rh
    from wom.plugins import ALL_BUILTIN_PLUGINS
    from wom.plugins.capacity_layer import CapacityLayerPlugin
    assert CapacityLayerPlugin in ALL_BUILTIN_PLUGINS
    assert "CapacityLayerPlugin" not in rh.SAFE_DEFAULT
    active, _ = rh._select_plugins("safe")
    assert not any(isinstance(p, CapacityLayerPlugin) for p in active)


# ── E2E: plugin ON keeps the market request ─────────────────────────────────
def _market_state(store):
    tree = store["tree"]
    out = {}
    for p in tree.products:
        for nd in tree.iter_all_nodes(p):
            if nd.node_type != "leaf_out":
                continue
            due = {lot: w for w in range(tree.num_weeks()) for lot in nd.psi4demand[w][0]}
            ship = {lot: w for w, lots in nd._actual_ship.items() for lot in lots}
            out[nd.node_id] = (due, ship)
    return out


def test_plugin_on_keeps_market_ids_and_ships_nothing_early(tmp_path):
    import tools.run_headless_from_folder as rh
    from wom.plugins.capacity_layer import CapacityLayerPlugin
    plugins = "BufferingStockOptimizerPlugin,CapacityOverridePlugin,HolidayCalendarPlugin"
    states, snaps = {}, {}
    orig = rh._psi_signature
    for tag, extra in (("off", []), ("on", [CapacityLayerPlugin(max_advance_weeks=17)])):
        work = tmp_path / tag / "smartx"
        shutil.copytree(SMARTX, work)
        store = {}

        def sig(t, n, _s=store):
            _s["tree"] = t
            return orig(t, n)
        rh._psi_signature = sig
        try:
            snaps[tag] = rh.run(str(work), plugins_spec=plugins, output_ppc_dir=str(work / "_ppc"),
                                verbose=False, extra_plugins=extra)
        finally:
            rh._psi_signature = orig
        states[tag] = _market_state(store)
        if extra:
            results = extra[0].results
    assert states["on"].keys() == states["off"].keys()
    early = unallocated_shipped = 0
    for nid in states["on"]:
        due_on, ship_on = states["on"][nid]
        assert due_on == states["off"][nid][0]                       # same IDs, same request weeks
        early += sum(1 for lot, w in ship_on.items() if w < due_on[lot])
    for p, r in results.items():
        for lot, market, _wk in r["unallocated_lots"]:
            for nid, (due, ship) in states["on"].items():
                if lot in due:
                    unallocated_shipped += lot in ship
    assert early == 0 and unallocated_shipped == 0
    assert snaps["on"]["forward"]["cap_hard_deferred_lots"] == 0
