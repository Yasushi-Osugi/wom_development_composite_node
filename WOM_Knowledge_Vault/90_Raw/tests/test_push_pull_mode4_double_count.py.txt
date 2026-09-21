# -*- coding: utf-8 -*-
"""
tests/test_push_pull_mode4_double_count.py
============================================
Regression test for the Mode4 (LT-shifted PUSH) double-counting bug.

Request Letter: requests/request_fix_mode4_double_count.md
Investigation trail (tools/sweep_specs/):
    apparel_s1_pushlt.yaml / apparel_s1_horizon.yaml /
    apparel_s1_holiday_lt8.yaml / apparel_s1_lt3.yaml

Root cause (see the Request Letter §1 for the full derivation)
----------------------------------------------------------------
Step 5 (copy_demand_to_supply) deep-copies psi4demand[P] -> psi4supply[P]
for EVERY week of every node, including the leaf_in nodes under a Mode4
decoupling node. Mode4 (push_pull.py, is_lt_shifted_mode() branch) then
overwrites psi4supply[w][P] only for the specific weeks w it re-times
(w = d - LT, where d is a real demand week at the decoupling node). Any
OTHER week -- in particular the leaf_in's own "natural" pull-copy week
(d - tau, where tau = that leaf_in's cumulative lt_wks + ss_wks back to
the decoupling node) -- was left holding the Step-5 copy. Whenever
LT != tau, those are two DIFFERENT weeks, so the same Lot_IDs end up
counted at both weeks, inflating P_sum and (downstream) generating
carry-over that never resolves.

Fixture: data/sample/apparel-us-2026 / Apparel_Outsourced_S1
    Factory_Import_CN (mom, decoupling) -> Fabric_CN (leaf_in)
    Fabric_CN.lt_wks=3, ss_days=0  =>  tau = 3

Before the fix, only push_lead_time_weeks == 3 (== tau) was a
coincidental no-op; every other tested value (1, 2, 4, 8) inflated
Fabric_CN's P_sum and left carry-over downstream (measured empirically
via the sweep specs above). After the fix, Mode4 is a true re-timing
for ANY push_lead_time_weeks value: Fabric_CN's P_sum equals the base
(no-Mode4) total of 23,884 lots for every LT tested here (2, 3, 4, 8)
-- confirmed empirically, this part of the Request Letter's prediction
holds unconditionally.

One refinement found while turning the fix green (NOT anticipated by
the Request Letter's literal wording, reported to the owner rather
than silently adjusted): downstream carry-over only goes to zero when
push_lead_time_weeks >= tau. Fabric_CN physically needs `tau` weeks to
ship to Factory_Import_CN; asking Mode4 to pre-build only 2 weeks
ahead (< tau=3) means the re-timed goods are, correctly, one week too
late no matter how faithfully Mode4 re-times the Lot_IDs -- this is a
genuine feasibility shortfall, not a duplication artifact. Pre-fix,
this genuine shortfall was masked/compounded by the duplication bug
(LT=2 downstream CO_sum went from 260,212 pre-fix to 248,512 post-fix
-- still large, because the real problem was never the duplication for
this particular LT, it was LT<tau itself). See
test_mode4_lt_below_tau_shows_genuine_shortage below.
"""
from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.sweep_flags import (  # noqa: E402
    guard_files_for_case, guarded_files, apply_ops, _execute_pipeline,
)

MODEL_DIR = os.path.join(REPO_ROOT, "data", "sample", "apparel-us-2026")
TARGET_SKU = "Apparel_Outsourced_S1"
TARGET_NODES = ["Fabric_CN", "Factory_Import_CN", "SP_Apparel_Outsourced", "DC_Import_Buffer"]

BASE_P_SUM = 23884   # Fabric_CN / Factory_Import_CN P_sum with buffering_stock_flag=1, no Mode4


def _push_config_content(lt_weeks: int) -> str:
    return (
        "sku_id,node_id,push_qty_per_week,buffer_lots,mode_only,mom_ref_node_id,"
        "pre_build_qty_per_week,pre_build_end_week,push_lead_time_weeks,push_eol_week\n"
        f"{TARGET_SKU},Factory_Import_CN,0,0,False,,0,,{lt_weeks},\n"
    )


def _ops_for_lt(lt_weeks: int) -> list:
    return [
        {"op": "set_cell", "file": "sc_tree_master.csv",
         "match": {"node_name": "Factory_Import_CN", "product_name": TARGET_SKU},
         "set": {"buffering_stock_flag": "1"}},
        {"op": "write_file", "file": "push_config.csv",
         "content": _push_config_content(lt_weeks)},
    ]


def _run_case(ops, ppc_out_dir) -> dict:
    """Apply `ops` to the real apparel-us-2026 folder under guard, run the
    pipeline, and restore the folder afterwards no matter what happens."""
    guard_set = guard_files_for_case(ops)
    with guarded_files(MODEL_DIR, guard_set):
        apply_ops(MODEL_DIR, ops)
        result, _sc_tree = _execute_pipeline(
            MODEL_DIR, "safe", ppc_out_dir, TARGET_SKU, TARGET_NODES)
    return result


# ---------------------------------------------------------------------------
# §4.1 Unit: Fabric_CN.P_sum must equal base, and downstream CO must be zero,
# for every push_lead_time_weeks value -- not just the LT==tau coincidence.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("lt_weeks", [2, 3, 4, 8])
def test_mode4_p_sum_matches_base(lt_weeks, tmp_path):
    result = _run_case(_ops_for_lt(lt_weeks), str(tmp_path / f"ppc_lt{lt_weeks}"))
    psi = result["psi"]

    fabric_p_sum = psi["Fabric_CN"]["P_sum"]
    factory_p_sum = psi["Factory_Import_CN"]["P_sum"]
    assert fabric_p_sum == BASE_P_SUM, (
        f"LT={lt_weeks}: Fabric_CN.P_sum={fabric_p_sum}, expected base={BASE_P_SUM} "
        f"(Mode4 double-counting -- see request_fix_mode4_double_count.md)")
    assert factory_p_sum == BASE_P_SUM, (
        f"LT={lt_weeks}: Factory_Import_CN.P_sum={factory_p_sum}, expected base={BASE_P_SUM}")


@pytest.mark.parametrize("lt_weeks", [3, 4, 8])  # LT >= tau=3; see module docstring for LT=2
def test_mode4_no_downstream_carry_over(lt_weeks, tmp_path):
    result = _run_case(_ops_for_lt(lt_weeks), str(tmp_path / f"ppc_lt{lt_weeks}"))
    psi = result["psi"]

    sp_co_sum = psi["SP_Apparel_Outsourced"]["CO_sum"]
    dc_co_sum = psi["DC_Import_Buffer"]["CO_sum"]
    assert sp_co_sum == 0, (
        f"LT={lt_weeks}: SP_Apparel_Outsourced.CO_sum={sp_co_sum}, expected 0 "
        f"(Mode4 double-counting causes unresolved downstream carry-over)")
    assert dc_co_sum == 0, (
        f"LT={lt_weeks}: DC_Import_Buffer.CO_sum={dc_co_sum}, expected 0")


def test_mode4_lt_below_tau_shows_genuine_shortage(tmp_path):
    """push_lead_time_weeks=2 < tau=3 (Fabric_CN's own transit lt_wks) is a
    genuinely infeasible schedule -- goods re-timed only 2 weeks ahead of
    Factory_Import_CN's own demand week cannot physically arrive by the
    3 weeks Fabric_CN needs to ship. After the fix (no more duplication
    padding the numbers), P_sum must still be exactly conserved -- but
    downstream carry-over is real and legitimate, not a symptom of the
    Mode4 bug this Request Letter targets. This documents the boundary
    the fix does NOT (and should not) paper over."""
    result = _run_case(_ops_for_lt(2), str(tmp_path / "ppc_lt2_shortage"))
    psi = result["psi"]

    assert psi["Fabric_CN"]["P_sum"] == BASE_P_SUM, (
        "LT=2 must still conserve total P_sum -- only the DOWNSTREAM timing "
        "is expected to suffer, not the lot count")
    assert psi["SP_Apparel_Outsourced"]["CO_sum"] > 0, (
        "LT=2 (< tau=3) is expected to show genuine, physically-justified "
        "carry-over -- a regression here would mean the test fixture itself "
        "has drifted, not that the Mode4 bug reappeared")


# ---------------------------------------------------------------------------
# §4.2 Integration: the fix must not leave any stale week outside Mode4's
# own write set, and must not touch mode_only / Mode1-3 behaviour.
# ---------------------------------------------------------------------------
def test_mode4_no_stale_weeks_outside_write_set(tmp_path):
    """Every week of Fabric_CN.psi4supply[P] must be explainable as either
    empty, or a re-timed copy of Factory_Import_CN's own demand -- i.e. no
    leftover Step-5 natural-copy week should survive once Mode4 has run."""
    from wom.model.plan_node import S, P  # noqa: E402

    lt_weeks = 8  # a value known (pre-fix) to trigger heavy duplication
    ops = _ops_for_lt(lt_weeks)
    guard_set = guard_files_for_case(ops)
    with guarded_files(MODEL_DIR, guard_set):
        apply_ops(MODEL_DIR, ops)
        _result, sc_tree = _execute_pipeline(
            MODEL_DIR, "safe", str(tmp_path / "ppc_stale"), TARGET_SKU, TARGET_NODES)

        fabric = next(nd for nd in sc_tree.iter_all_nodes(TARGET_SKU)
                      if nd.node_name == "Fabric_CN")
        factory = next(nd for nd in sc_tree.iter_all_nodes(TARGET_SKU)
                       if nd.node_name == "Factory_Import_CN")
        n_weeks = sc_tree.num_weeks()

        for w in range(n_weeks):
            fabric_p = list(fabric.psi4supply[w][P])
            if not fabric_p:
                continue
            future_w = w + lt_weeks
            expected = list(factory.psi4demand[future_w][S]) if future_w < n_weeks else []
            assert fabric_p == expected, (
                f"week idx {w}: Fabric_CN.psi4supply[P]={fabric_p} does not match "
                f"Mode4's own re-timed source Factory_Import_CN.psi4demand[{future_w}][S]="
                f"{expected} -- a stale natural-copy week survived the fix")


def test_mode4_only_flag_still_skips_p_schedule(tmp_path):
    """mode_only=True must still bypass Mode4's P-schedule entirely (and
    therefore also bypass the new clearing step) -- unchanged behaviour."""
    from wom.model.plan_node import P  # noqa: E402

    ops = [
        {"op": "set_cell", "file": "sc_tree_master.csv",
         "match": {"node_name": "Factory_Import_CN", "product_name": TARGET_SKU},
         "set": {"buffering_stock_flag": "1"}},
        {"op": "write_file", "file": "push_config.csv",
         "content": (
             "sku_id,node_id,push_qty_per_week,buffer_lots,mode_only,mom_ref_node_id,"
             "pre_build_qty_per_week,pre_build_end_week,push_lead_time_weeks,push_eol_week\n"
             f"{TARGET_SKU},Factory_Import_CN,0,0,True,,0,,,\n"
         )},
    ]
    guard_set = guard_files_for_case(ops)
    with guarded_files(MODEL_DIR, guard_set):
        apply_ops(MODEL_DIR, ops)
        result, _sc_tree = _execute_pipeline(
            MODEL_DIR, "safe", str(tmp_path / "ppc_mode_only"), TARGET_SKU, TARGET_NODES)

    psi = result["psi"]
    assert psi["Fabric_CN"]["P_sum"] == BASE_P_SUM, (
        "mode_only=True must leave the Step-5 natural copy untouched "
        f"(got P_sum={psi['Fabric_CN']['P_sum']}, expected {BASE_P_SUM})")
    assert psi["SP_Apparel_Outsourced"]["CO_sum"] == 0
    assert psi["DC_Import_Buffer"]["CO_sum"] == 0
