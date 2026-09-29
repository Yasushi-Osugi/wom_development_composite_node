# -*- coding: utf-8 -*-
"""
tests/test_flow_check.py — RequestLetter_FlowCheck_CapNaming_WarmupTrial

  Unit        : Flow Check tables on a small synthetic tree (both modes),
                the PSI List rows (S = request, Ship = actual, Σ row),
                cap_hard naming (identity defers, legacy seals)
  Integration : headless runner -> Flow Check CSV; identity snapshot carries
                cap_hard_deferred_*; the legacy snapshot keeps cap_hard_sealed
  E2E golden  : tests/test_golden.py (legacy, unchanged)
"""
import csv
import os
import shutil
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from wom.model.plan_node import S, CO, I, P
from wom.model.sc_tree import build_demo_sc_tree
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner
from wom.engine.plan_copy import copy_demand_to_supply
from wom.engine.forward_planner import ForwardPlanner
from wom.engine.flow_check import compute_flow_check, write_flow_check_csv

SKU = "SKU-A"
N = 26
WEEKS = [f"2024-W{i:02d}" for i in range(1, N + 1)]
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _plan(mode, mom_cap=None, demand=None):
    rows = [{"sku_id": SKU, "sku_name": "A", "region": "JP", "lead_time_wks": 1}]
    t = build_demo_sc_tree(pd.DataFrame(rows), WEEKS, lt_wks_ot=1, lt_wks_in=2)
    assign_demand_lots_from_dict(t, demand or {(SKU, "JP", "2024-W10"): 4,
                                               (SKU, "JP", "2024-W12"): 4}, cpu_size=1)
    BackwardPlanner(t, config={"mom_constrained": False}).run(SKU)
    copy_demand_to_supply(t, SKU)
    mom = next(n for n in t.iter_all_nodes(SKU) if n.node_name.startswith("Mother Plant"))
    if mom_cap is not None:
        for w in range(N):
            mom.set_capacity(w, cap_hard=float(mom_cap))
    res = ForwardPlanner(t, lot_flow_mode=mode).run(SKU)
    return t, res


def _row(fc, name_prefix):
    return next(r for r in fc["nodes"] if r["node"].startswith(name_prefix))


# ---------------------------------------------------------------------------
# V3 Flow Check
# ---------------------------------------------------------------------------

def test_identity_all_nodes_ok_and_market_balances():
    t, res = _plan("identity", mom_cap=2)
    fc = compute_flow_check(t, {SKU: res})
    assert fc["summary"]["ng"] == 0
    for r in fc["nodes"]:
        assert r["conservation_diff"] == 0, r
        assert r["status"] in ("OK", "対象外"), r
    leaf, dc = _row(fc, "Sales JP"), _row(fc, "DC JP")
    # the leaf received exactly what the DC shipped towards it
    assert leaf["upstream_ship_sum"] == dc["ship_sum"] == leaf["receipt_sum"]
    assert leaf["arrival_diff"] == 0 and leaf["recorded_arrivals"] == leaf["receipt_sum"]
    tot = fc["market"][-1]
    assert tot["demand"] == 8
    assert tot["on_time"] + tot["early"] + tot["late"] + tot["backlog_end"] == 8
    assert tot["check"] == 0 and tot["early"] == 0


def test_legacy_below_decouple_is_na_with_visible_arrival_gap():
    t, res = _plan("legacy", mom_cap=2)
    fc = compute_flow_check(t, {SKU: res})
    leaf, dc = _row(fc, "Sales JP"), _row(fc, "DC JP")
    assert leaf["status"] == "対象外" and "コピー" in leaf["reason"]
    # the DC shipped less than the leaf received (legacy exception 2)
    assert dc["ship_sum"] < leaf["receipt_sum"]
    assert leaf["arrival_diff"] == dc["ship_sum"] - leaf["receipt_sum"] < 0
    # legacy sealing at the MOM is reported, and the MOM still reconciles
    mom = _row(fc, "Mother Plant")
    assert mom["sealed_legacy"] > 0 and mom["arrival_diff"] == 0 and mom["status"] == "OK"


def test_in_transit_at_end_is_reconciled():
    t, res = _plan("identity", demand={(SKU, "JP", "2024-W26"): 3})
    # a shipment from the DC in the last week arrives beyond the horizon
    fc = compute_flow_check(t, {SKU: res})
    assert fc["summary"]["ng"] == 0
    leaf = _row(fc, "Sales JP")
    assert leaf["upstream_ship_sum"] == leaf["receipt_sum"] + leaf["in_transit_end"]


def test_no_forward_result_marks_rows_not_applicable():
    t, _res = _plan("identity")
    fc = compute_flow_check(t, {})
    assert all(r["status"] in ("対象外", "NG") for r in fc["nodes"])
    assert any("記録なし" in r["reason"] for r in fc["nodes"])


def test_csv_written(tmp_path):
    t, res = _plan("identity", mom_cap=2)
    paths = write_flow_check_csv(compute_flow_check(t, {SKU: res}), str(tmp_path))
    assert [os.path.basename(p) for p in paths] == ["flow_check_nodes.csv", "flow_check_market.csv"]
    with open(paths[1], encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert rows[-1]["product"] == "Σ（モデル全体）" and "demand_qty" in rows[-1]


def test_edge_flows_are_record_only():
    """edge_flows / p_copied / opening counts do not change the plan."""
    t1, r1 = _plan("identity", mom_cap=2)
    assert r1.edge_flows and all(len(e) == 5 for e in r1.edge_flows)
    t2, r2 = _plan("legacy", mom_cap=2)
    assert r2.p_copied_node_ids            # legacy: the leaf below the DC
    assert not r1.p_copied_node_ids        # identity: no demand-P copy in OutBound


# ---------------------------------------------------------------------------
# V2 PSI List rows
# ---------------------------------------------------------------------------

def test_psi_list_table_ship_and_sum_row():
    from wom.gui.app import psi_list_table
    t, res = _plan("identity", mom_cap=2)
    leaf = next(n for n in t.iter_all_nodes(SKU) if n.node_name.startswith("Sales JP"))
    rows, total = psi_list_table(leaf, "supply")
    assert [r["Ship"] for r in rows] == [len(leaf._actual_ship.get(w, [])) for w in range(N)]
    assert total["S"] == sum(r["S"] for r in rows) and total["P"] == sum(r["P"] for r in rows)
    assert total["Ship"] == sum(r["Ship"] for r in rows)
    assert total["I"] == rows[-1]["I"] and total["CO"] == rows[-1]["CO"]   # 期末
    # identity: requests (S) and actual shipments differ in time
    assert [r["S"] for r in rows] != [r["Ship"] for r in rows]
    d_rows, d_total = psi_list_table(leaf, "demand")
    assert all(r["Ship"] is None for r in d_rows) and d_total["Ship"] is None


# ---------------------------------------------------------------------------
# Part 2 cap_hard naming
# ---------------------------------------------------------------------------

def test_cap_hard_identity_defers_legacy_seals():
    t, res = _plan("identity", mom_cap=2)
    assert res.cap_hard_sealed == 0
    assert res.cap_hard_deferred_lots > 0
    assert res.cap_hard_deferred_lot_weeks >= res.cap_hard_deferred_lots
    assert res.cap_hard_deferred_lot_weeks == sum(e[2] for e in res.cap_hard_events)
    t2, res2 = _plan("legacy", mom_cap=2)
    assert res2.cap_hard_sealed > 0
    assert res2.cap_hard_deferred_lots == 0 and res2.cap_hard_deferred_lot_weeks == 0


def test_headless_snapshot_forward_naming_and_flow_check_csv(tmp_path):
    import tools.run_headless_from_folder as rh
    src = os.path.join(REPO, "data", "sample", "bom-test-2026")
    for mode in ("identity", "legacy"):
        d = tmp_path / f"m_{mode}"
        shutil.copytree(src, d)
        snap = rh.run(str(d), plugins_spec="none", output_ppc_dir=str(tmp_path / f"ppc_{mode}"),
                      verbose=False, lot_flow_mode=mode, flow_check_dir=str(tmp_path / f"fc_{mode}"))
        fw = snap["forward"]
        if mode == "identity":
            assert set(fw) == {"cap_hard_deferred_lots", "cap_hard_deferred_lot_weeks",
                               "cap_soft_violation_count"}
        else:
            assert set(fw) == {"cap_hard_sealed", "cap_soft_violation_count"}
        assert os.path.exists(tmp_path / f"fc_{mode}" / "flow_check_nodes.csv")
