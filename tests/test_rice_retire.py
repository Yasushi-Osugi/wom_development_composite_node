# -*- coding: utf-8 -*-
"""RequestLetter_RiceLegacyRetire — rice moved to identity, HarvestBatch removed.

L-4  every model in data/sample/ plans with lot_flow_mode = identity (a model that
     goes back to legacy turns this red). The untracked *_BK* backups
     (.gitignore) are not models of the repository and are skipped.
L-5  HarvestBatchPlugin is no longer registered and its module is gone.
1.4  Rice Seasonal ON for a model without Rice inputs stops with a message that
     says so.
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
REPO = os.path.abspath(os.path.join(HERE, ".."))
SAMPLE = os.path.join(REPO, "data", "sample")
sys.path.insert(0, HERE)


def _sample_models():
    out = []
    for d in sorted(os.listdir(SAMPLE)):
        p = os.path.join(SAMPLE, d)
        if "_BK" in d or not os.path.isfile(os.path.join(p, "sc_tree_master.csv")):
            continue
        out.append(d)
    return out


@pytest.mark.parametrize("model", _sample_models())
def test_every_sample_model_is_identity(model):
    from wom.engine.forward_planner import resolve_lot_flow_mode
    from wom.engine.warmup import read_lot_flow_mode
    assert resolve_lot_flow_mode(read_lot_flow_mode(os.path.join(SAMPLE, model))) == "identity"


def test_rice_sample_is_a_sample_model_and_identity():
    assert "rice-japan-2027-2028" in _sample_models()
    assert not os.path.exists(os.path.join(SAMPLE, "rice-japan-2027-2028-dal"))
    with open(os.path.join(SAMPLE, "rice-japan-2027-2028", "planning_config.csv"), encoding="utf-8") as f:
        assert "lot_flow_mode,identity" in f.read()


def test_harvest_batch_is_removed():
    from wom.plugins import ALL_BUILTIN_PLUGINS
    assert all(c.__name__ != "HarvestBatchPlugin" for c in ALL_BUILTIN_PLUGINS)
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("wom.engine.harvest_batch_plugin")


def test_rice_seasonal_on_a_model_without_rice_inputs_says_so(tmp_path):
    from test_rice_seasonal_layer import headless, make_model
    from wom.capacity_layer.rice_seasonal import RiceInputError
    model = make_model(tmp_path)
    os.remove(os.path.join(model, "rice_seasonal_config.csv"))
    with pytest.raises(RiceInputError, match="Rice の設定"):
        headless(model)
