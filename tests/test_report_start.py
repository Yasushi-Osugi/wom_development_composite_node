# -*- coding: utf-8 -*-
"""RequestLetter_RiceSeasonal_PolishAdvance1 work 5・6 — one report start, Flow Check table 2.

work 5: the reporting period starts at vc_config.csv report_start, read in one
place (wom/engine/report_start.py) by the World Map and the Rice layer; a second
copy in rice_seasonal_config.csv stops.
work 6: Flow Check table 2 counts the report period only when the model sets it;
otherwise the table is exactly as before.
"""
from __future__ import annotations

import csv
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
from test_rice_seasonal_layer import _w, headless, make_model  # noqa: E402

from wom.engine.report_start import configured_report_start, read_report_start  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, ".."))
MIG = os.path.join(REPO, "data", "trial", "rice-japan-2027-2028-seasonal")


def test_vc_config_is_the_one_place(tmp_path):
    model = make_model(tmp_path)
    assert read_report_start(model) == ("2027-W01", "vc_config.csv")
    os.remove(os.path.join(model, "vc_config.csv"))
    rs, src = read_report_start(model)
    assert src == "最初の非ゼロ需要週" and rs == "2027-W01"      # the fixture's first demand week
    assert configured_report_start(model, ["2026-W53", "2027-W01"]) is None


@pytest.mark.skipif(not os.path.isdir(MIG), reason="migration copy not generated")
def test_world_map_band_reads_2027_w01_for_the_migration_copy():
    from wom.worldmap_ne.flows import report_start_index
    weeks = ["2026-W52", "2026-W53", "2027-W01", "2027-W02"]
    assert report_start_index(MIG, weeks) == (2, "vc_config.csv")


def test_report_start_in_rice_config_stops(tmp_path):
    from wom.capacity_layer import rice_seasonal as rs
    model = make_model(tmp_path)
    path = os.path.join(model, "rice_seasonal_config.csv")
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    _w(path, ["key", "value"], rows + [{"key": "report_start", "value": "2027-W01"}])
    with pytest.raises(rs.RiceInputError, match="vc_config.csv"):
        headless(model)


def test_rice_layer_uses_the_vc_config_report_start(tmp_path):
    model = make_model(tmp_path)
    _s, tree, _f = headless(model)
    assert tree.rice_seasonal_results["_joint"]["report_start"] == "2027-W01"


def test_flow_check_table_2_report_columns_only_with_a_report_start(tmp_path):
    from wom.engine.flow_check import MARKET_REPORT_COLUMNS, compute_flow_check
    model = make_model(tmp_path, demand={"2026-W53": 1, "2027-W01": 1},
                       storage="1000", other="1000", white="1000", crop="100")
    _s, tree, fres = headless(model)
    plain = compute_flow_check(tree, fres)
    assert not any(c in r for r in plain["market"] for c in MARKET_REPORT_COLUMNS)
    assert "report_start" not in plain["summary"]
    idx = tree.week_labels.index("2027-W01")
    fc = compute_flow_check(tree, fres, report_start_index=idx)
    tot = fc["market"][-1]
    assert fc["summary"]["report_start"] == "2027-W01"
    assert tot["demand"] == 2 and tot["demand_report"] == 1
    assert tot["on_time_report"] + tot["backlog_end_report"] == 1
    assert tot["on_time_report"] <= tot["on_time"] and tot["backlog_end_report"] <= tot["backlog_end"]
    # every other column is unchanged by the report period
    for a, b in zip(plain["market"], fc["market"]):
        assert {k: a[k] for k in a} == {k: b[k] for k in a}
