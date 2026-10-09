# -*- coding: utf-8 -*-
"""tools/lovem_interval_check.py — cell-by-cell interval check, independent of the observer.

On a small observed run (the one-ID Rice fixture with a few IDs), the new
check and the existing week-by-week check (wom.lovem.verify.verify_run) must
agree: both pass on the run as written, both fail on a tampered interval file
(a changed multiplicity, a duplicated record). Duplicates of one ID in a week
are counted, never removed by a set.
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import sys
from collections import Counter

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
from test_rice_seasonal_layer import make_model  # noqa: E402

from tools.lovem_interval_check import Checker, replay, runs_from_psi  # noqa: E402

PLUGINS = "RiceSeasonalPlugin"


def test_runs_from_psi_counts_duplicates_and_splits_on_multiplicity():
    weekly = [[], ["a"], ["a", "a"], ["a", "a"], ["a"], [], ["a", "b"]]
    runs, occ = runs_from_psi(weekly, "I")
    assert runs == Counter({("a", 1, 1, 1): 1, ("a", 2, 3, 2): 1, ("a", 4, 4, 1): 1,
                            ("a", 6, 6, 1): 1, ("b", 6, 6, 1): 1})
    assert occ == Counter({"a": 7, "b": 1})
    runs_p, occ_p = runs_from_psi(weekly, "P")             # flow bucket: one interval per week
    assert runs_p[("a", 2, 2, 2)] == 1 and runs_p[("a", 3, 3, 2)] == 1 and occ_p == occ


@pytest.fixture(scope="module")
def observed(tmp_path_factory):
    from wom.lovem.observer import observe_run
    tmp = tmp_path_factory.mktemp("ivchk")
    model = make_model(tmp, demand={"2027-W01": 3, "2026-W53": 2},
                       storage="1000", other="1000", white="1000", crop="100")
    run_dir = str(tmp / "run")
    observe_run(model, run_dir, plugins=PLUGINS, label="ivchk")
    return model, run_dir


def check(model, run_dir, out):
    ck = Checker(run_dir, str(out))
    replay(model, PLUGINS, ck)
    snaps = {p["snapshot_id"] for p in json.load(open(os.path.join(run_dir, "manifest.json"),
                                                       encoding="utf-8"))["snapshots"]}
    ok = (snaps == {s["snapshot"] for s in ck.snap_summary}
          and all(r["result"] == "match" for r in ck.rows)
          and all(not s.get("bad") and not s.get("anomalies") for s in ck.snap_summary))
    return ok, ck


def test_new_check_and_week_expansion_agree_on_the_run(observed, tmp_path):
    from wom.lovem.verify import verify_run
    model, run_dir = observed
    ok, ck = check(model, run_dir, tmp_path)
    assert ok and ck.rows and sum(r.get("occurrences", 0) for r in ck.rows) > 0
    assert any(r["bucket"] == "I" and r["intervals"] for r in ck.rows)
    assert verify_run(run_dir)["all_match"] is True


@pytest.mark.parametrize("tamper", ["multiplicity", "duplicate_record"])
def test_both_checks_catch_a_tampered_interval_file(observed, tmp_path, tamper):
    from wom.lovem.verify import verify_run
    model, run_dir = observed
    bad = str(tmp_path / "run")
    shutil.copytree(run_dir, bad)
    path = os.path.join(bad, "psi_intervals", "Koshihikari__final.jsonl.gz")
    lines = gzip.open(path, "rt", encoding="utf-8").read().splitlines()
    i = next(k for k, l in enumerate(lines) if json.loads(l)["bucket"] == "I")
    if tamper == "multiplicity":
        r = json.loads(lines[i])
        r["multiplicity"] += 1
        lines[i] = json.dumps(r)
    else:
        lines.insert(i + 1, lines[i])
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    ok, ck = check(model, bad, tmp_path / "out")
    assert not ok and any(r["result"] == "MISMATCH" for r in ck.rows)
    assert verify_run(bad)["all_match"] is False
