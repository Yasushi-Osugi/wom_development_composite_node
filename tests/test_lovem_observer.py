# -*- coding: utf-8 -*-
"""
tests/test_lovem_observer.py — LOVEM stage A on ev-thailand-2026 (request A4).

  A4-1  Q12: observation ON / OFF give identical PSI (every list, in order),
        _actual_s, planner result records, _push_shortfall, headless snapshot
        (golden fields) and PPC output files.
  A4-2  every (snapshot, node, layer, bucket, week) of the decoded intervals
        matches state_digests.
  A4-5  se2_case.json reproduces 168 for 2026-W38/W39 at Factory_Import_CN.
  plus  the observation wrappers are removed after the run; the model folder
        is not written.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL = os.path.join(REPO, "data", "sample", "ev-thailand-2026")
PLUGINS = "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"


@pytest.fixture(scope="module")
def q12(tmp_path_factory):
    from wom.lovem.q12 import compare_on_off
    out = str(tmp_path_factory.mktemp("lovem") / "run")
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        # stage A expectations (SE2 = 168 etc.) are those of the legacy solver
        res = compare_on_off(MODEL, PLUGINS, observe_out=out, lot_flow_mode="legacy")
    finally:
        os.chdir(cwd)
    return res, out


def test_q12_observation_does_not_change_the_plan(q12):
    res, _out = q12
    assert res["identical"], (res["top_level_diffs"], res["cell_diffs"][:10])
    assert res["n_cells"] == 14 * 4          # 14 nodes x (demand, supply, push_shortfall, plan_mode)
    assert res["ppc_files"], "PPC output files were compared"


def test_intervals_restore_every_digest(q12):
    from wom.lovem.verify import verify_run
    _res, out = q12
    v = verify_run(out)
    assert v["all_match"], v
    assert v["digest_rows"] == v["digest_rows_matched"] > 0
    assert v["duplicate_interval_ids"] == 0


def test_se2_168_is_reproduced(q12):
    from wom.lovem.se2 import build_se2_case
    _res, out = q12
    case = build_se2_case(out)
    rows = {r["week"]: r for r in case["target_week_rows"]}
    assert (rows["2026-W38"]["planned_s"], rows["2026-W38"]["actual_s"]) == (150, 132)
    assert (rows["2026-W39"]["planned_s"], rows["2026-W39"]["actual_s"]) == (150, 0)
    assert case["sum_shortfall_target_weeks"] == 168
    assert case["sum_push_shortfall_target_weeks"] == 168
    assert case["horizon_totals"]["actual_s"] == 9370
    assert case["horizon_totals"]["push_shortfall"] == 400
    assert case["classification"].startswith("not performed")


def test_run_folder_contents_and_model_untouched(q12):
    from wom.lovem.io import iter_jsonl, load_manifest
    _res, out = q12
    man = load_manifest(out)
    assert man["model_unchanged_by_run"] is True
    assert man["coverage"]["kitting"].startswith("not_applicable")
    assert man["coverage"]["arrival_unlinked"] == 0
    for fn in ("nodes.csv", "weeks.csv", "capacity.csv", "state_digests.jsonl",
               "events.jsonl.gz", "relations.jsonl.gz", "source_evidence.jsonl.gz",
               "demand_anchors.jsonl.gz"):
        assert os.path.exists(os.path.join(out, fn)), fn
    assert man["weeks"]["w53_weeks"] == ["2026-W53"]
    assert man["weeks"]["non_7day_steps_at_index"] == []
    # anchors = every lot generated from demand_forecast (before any plugin)
    n_anchor = sum(1 for _ in iter_jsonl(os.path.join(out, "demand_anchors.jsonl.gz")))
    assert n_anchor == man["counts"]["anchors"] > 0
    # capacity: closed weeks keep the raw physical ceiling, effective limit 0
    import csv
    with open(os.path.join(out, "capacity.csv"), encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if r["node_id"].endswith("Factory_Import_CN:EVmaker_Import") and r["is_open"] == "0"]
    assert rows and all(r["effective_limit"] == "0.0" and r["planned_capacity"] == "0.0" for r in rows)
    assert all(float(r["raw_hard"]) > 0 for r in rows)


def test_wrappers_are_removed_after_observation(q12):
    import wom.engine.forward_planner as fpm
    import wom.engine.backward_planner as bp
    import wom.engine.push_pull as ppm
    import wom.engine.plan_copy as pc
    import wom.engine.hook_bus as hb
    import wom.model.lot_generator as lg
    import tools.run_headless_from_folder as rh
    for fn in (fpm.ForwardPlanner.run, fpm.ForwardPlanner._propagate_to_parent,
               fpm.ForwardPlanner._propagate_to_child, fpm.ForwardPlanner._run_ot_push_pull,
               bp.BackwardPlanner.run, ppm.PushProductionPlanner.setup_all,
               pc.copy_demand_to_supply, hb.HookBus.fire, lg.assign_demand_lots_from_dict,
               rh._psi_signature):
        assert "wom.lovem" not in (fn.__module__ or ""), fn
        assert "observer" not in fn.__qualname__ and "installed" not in fn.__qualname__, fn


def test_ship_to_arrival_relations_are_consistent(q12):
    """Every relation joins an existing ship event to an arrival of the same
    lot, and the arrival week = ship week + a non-negative lead time."""
    from wom.lovem.io import iter_jsonl
    _res, out = q12
    ev = {e["event_id"]: e for e in iter_jsonl(os.path.join(out, "events.jsonl.gz"))
          if e["event_type"] in ("actual_ship", "arrival", "bridge_arrival")}
    n = 0
    for r in iter_jsonl(os.path.join(out, "relations.jsonl.gz")):
        a, b = ev[r["from_ref"]], ev[r["to_ref"]]
        assert a["lot_id"] == b["lot_id"]
        assert b["week_index"] >= a["week_index"]
        if r["relation_type"] == "ship_to_bridge":
            assert b["week_index"] == a["week_index"]
        n += 1
    assert n > 0
