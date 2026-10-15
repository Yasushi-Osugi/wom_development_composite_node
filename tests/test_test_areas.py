# -*- coding: utf-8 -*-
"""
tests/test_test_areas.py — the test tiers stay complete (RequestLetter_QuickCheckTests §2.4)

  1  every tests/test_*.py is in at least one area of tests/conftest.py AREAS
     (a new test file fails here until its line is added)
  2  AREAS names only existing files and known areas
  3  the smoke tier selects at least one test, and every SMOKE entry matches a file
  4  every marker the tiers use is registered in pytest.ini (--strict-markers)
"""
import configparser
import glob
import os

import conftest as tiers

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def _test_files():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(HERE, "test_*.py")))


def _registered_markers():
    cp = configparser.ConfigParser()
    cp.read(os.path.join(REPO, "pytest.ini"), encoding="utf-8")
    lines = cp.get("pytest", "markers").strip().splitlines()
    return {ln.split(":")[0].strip() for ln in lines if ln.strip()}


def test_every_test_file_has_an_area():
    missing = [f for f in _test_files() if not tiers.AREAS.get(f)]
    assert not missing, f"add these files to tests/conftest.py AREAS: {missing}"


def test_areas_table_names_real_files_and_known_areas():
    files = set(_test_files())
    stale = sorted(set(tiers.AREAS) - files)
    assert not stale, f"AREAS names files that do not exist: {stale}"
    bad = sorted({a for v in tiers.AREAS.values() for a in v} - set(tiers.AREA_NAMES))
    assert not bad, f"unknown areas in AREAS: {bad}"


def test_smoke_selects_tests():
    files = set(_test_files())
    assert tiers.SMOKE, "the smoke tier is empty"
    for s in tiers.SMOKE:
        assert s.split("::")[0].split("[")[0] in files, f"SMOKE entry {s!r} names no test file"


def test_markers_are_registered():
    used = set(tiers.AREA_NAMES) | {"smoke", "slow"}
    missing = sorted(used - _registered_markers())
    assert not missing, f"register these markers in pytest.ini: {missing}"
    with open(os.path.join(REPO, "pytest.ini"), encoding="utf-8") as f:
        assert "--strict-markers" in f.read()
