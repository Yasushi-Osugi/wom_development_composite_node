# -*- coding: utf-8 -*-
"""RequestLetter_PublicReadiness_Plugins — plugin sets, unknown names, IDs without demand.

1  each sample model recommends its plugin set (planning_config.csv
   recommended_plugins) = the plugins of its golden; the headless runner uses it
   when --plugins is not given and records the source.
2  an unknown plugin name stops before the run, listing the valid names.
3  an ID that no market demand owns is NG in Flow Check and is counted by
   tools/lot_identity_checks.py, whatever its name (the OI_ exemption is gone).
"""
from __future__ import annotations

import json
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
REPO = os.path.abspath(os.path.join(HERE, ".."))
SAMPLE = os.path.join(REPO, "data", "sample")
sys.path.insert(0, HERE)
from test_rice_seasonal_layer import _w, make_model  # noqa: E402

from wom.plugins.selection import UnknownPluginError, read_recommended_plugins, to_class_names  # noqa: E402


def _models():
    return [d for d in sorted(os.listdir(SAMPLE))
            if "_BK" not in d and os.path.isfile(os.path.join(SAMPLE, d, "sc_tree_master.csv"))]


# ── 1: recommended set = golden set ─────────────────────────────────────────
@pytest.mark.parametrize("model", _models())
def test_every_sample_model_recommends_its_golden_plugins(model):
    rec = read_recommended_plugins(os.path.join(SAMPLE, model))
    assert rec is not None, f"{model}: planning_config.csv has no recommended_plugins"
    g = os.path.join(REPO, "tests", "golden", f"{model}.json")
    if os.path.exists(g):
        with open(g, encoding="utf-8") as f:
            assert sorted(rec) == sorted(json.load(f)["config"]["plugins"])
    else:   # no golden (Owner decision): the safe set
        assert sorted(rec) == sorted(["HolidayCalendarPlugin", "BufferingStockOptimizerPlugin",
                                      "CapacityOverridePlugin"])


def test_headless_without_plugins_uses_the_recommended_set_and_records_it(tmp_path):
    import tools.run_headless_from_folder as rh
    model = make_model(tmp_path)
    _w(os.path.join(model, "planning_config.csv"), ["key", "value"], [
        {"key": "lot_flow_mode", "value": "identity"},
        {"key": "recommended_plugins", "value": "RiceSeasonalPlugin"}])
    snap = rh.run(model, output_ppc_dir=os.path.join(model, "_ppc"), verbose=False)
    assert snap["config"]["plugins"] == ["RiceSeasonalPlugin"]
    assert snap["config"]["plugins_source"] == "recommended_plugins"
    explicit = rh.run(model, plugins_spec="none", output_ppc_dir=os.path.join(model, "_ppc"), verbose=False)
    assert explicit["config"]["plugins"] == [] and "plugins_source" not in explicit["config"]
    os.remove(os.path.join(model, "planning_config.csv"))
    safe = rh.run(model, output_ppc_dir=os.path.join(model, "_ppc"), verbose=False)
    assert safe["config"]["plugins_source"] == "safe"
    assert sorted(safe["config"]["plugins"]) == sorted(rh.SAFE_DEFAULT)


# ── 2: unknown names stop ───────────────────────────────────────────────────
def test_unknown_plugin_name_stops_with_the_valid_names():
    import tools.run_headless_from_folder as rh
    with pytest.raises(UnknownPluginError) as e:
        rh._select_plugins("HolidayCalendarPlugin,HarvestBatchPlugin")
    msg = str(e.value)
    assert "HarvestBatchPlugin" in msg and "RiceSeasonalPlugin (rice_seasonal)" in msg
    assert to_class_names(["holiday_calendar", "RiceSeasonalPlugin"], "x") == [
        "HolidayCalendarPlugin", "RiceSeasonalPlugin"]


def test_unknown_name_stops_the_headless_run_before_the_model_is_touched(tmp_path):
    import tools.run_headless_from_folder as rh
    model = make_model(tmp_path)
    before = {f: os.path.getmtime(os.path.join(model, f)) for f in os.listdir(model)}
    with pytest.raises(UnknownPluginError):
        rh.run(model, plugins_spec="HarvestBatchPlugin", output_ppc_dir=os.path.join(model, "_ppc"),
               verbose=False)
    assert {f: os.path.getmtime(os.path.join(model, f)) for f in os.listdir(model)} == before


def test_unknown_name_in_recommended_plugins_stops(tmp_path):
    model = make_model(tmp_path)
    _w(os.path.join(model, "planning_config.csv"), ["key", "value"], [
        {"key": "recommended_plugins", "value": "HolidayCalendarPlugin,HarvestBatchPlugin"}])
    with pytest.raises(UnknownPluginError, match="HarvestBatchPlugin"):
        read_recommended_plugins(model)


# ── 3: an ID without demand is NG ───────────────────────────────────────────
def _planned(tmp_path):
    import tools.run_headless_from_folder as rh
    import wom.engine.forward_planner as fpm
    st = {"fres": {}, "fp": {}}
    o_sig, o_run = rh._psi_signature, fpm.ForwardPlanner.run

    def sig(t, n):
        st["tree"] = t
        return o_sig(t, n)

    def frun(self, prod):
        r = o_run(self, prod)
        st["fres"][prod] = r
        st["fp"][prod] = {k: {w: list(v) for w, v in d.items()} for k, d in self._actual_s.items()}
        return r
    rh._psi_signature, fpm.ForwardPlanner.run = sig, frun
    try:
        snap = rh.run(make_model(tmp_path), plugins_spec="RiceSeasonalPlugin",
                      output_ppc_dir=str(tmp_path / "ppc"), verbose=False)
    finally:
        rh._psi_signature, fpm.ForwardPlanner.run = o_sig, o_run
    return st, snap


@pytest.mark.parametrize("stray", ["OI_IN:mom:Sanchiku_Niigata:Koshihikari_0", "STRAY-LOT-1"])
def test_id_without_demand_is_ng_in_flow_check(tmp_path, stray):
    from wom.engine.flow_check import compute_flow_check
    from wom.model.plan_node import I
    st, _snap = _planned(tmp_path)
    tree, fres = st["tree"], st["fres"]
    clean = compute_flow_check(tree, fres)
    assert clean["summary"]["ng"] == 0
    wh = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_name == "Genmai_Souko_Niigata")
    wh.psi4supply[tree.week_labels.index("2026-W46")][I].append(stray)   # a lot nobody demands
    fc = compute_flow_check(tree, fres)
    row = next(r for r in fc["nodes"] if r["node"] == "Genmai_Souko_Niigata")
    assert row["status"] == "NG" and "需要に無い ID" in row["reason"] and stray in row["reason"]


def test_id_without_demand_is_counted_by_lot_identity_checks(tmp_path):
    from tools.lot_identity_checks import analyse
    from wom.model.plan_node import I
    st, snap = _planned(tmp_path)
    st["arrivals"] = []
    base = analyse(st, snap, 0.0)[0]["K3"]["ids_without_demand"]
    tree = st["tree"]
    wh = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_name == "Genmai_Souko_Niigata")
    wh.psi4supply[tree.week_labels.index("2026-W46")][I].append("OI_old_style_0")
    k3 = analyse(st, snap, 0.0)[0]["K3"]
    assert k3["ids_without_demand"] == base + 1 and "rice_harvest_like" not in k3
