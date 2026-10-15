# -*- coding: utf-8 -*-
"""
tests/test_lesson000_variants.py — Lesson 000 comparison models (RequestLetter_Lesson000_Public §4)

Fast: builds the 3 models in a temp folder; does not plan.
  1  each model differs from the base only in the rows / column of CHANGES (and the note column)
  2  every changed value is the base value x 1.3 (15,500 -> 20,150 etc.)
  3  every CHANGES condition matches the expected number of rows in the base model
     (when the base model changes, this fails and the tool stops)
"""
import csv
import filecmp
import os
import shutil
from fractions import Fraction

import pytest

from tools import lesson000_variants as L

GROUPS = {name: groups for name, _t, groups in L.VARIANTS}


def _rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("lesson000")
    return L.build(str(out))


def _changed_cells(base_rows, var_rows):
    assert len(base_rows) == len(var_rows)
    head = base_rows[0]
    assert var_rows[0] == head
    out = []
    for i, (b, v) in enumerate(zip(base_rows[1:], var_rows[1:]), start=1):
        for j, (x, y) in enumerate(zip(b, v)):
            if x != y:
                out.append((i, head[j], x, y))
    return out


@pytest.mark.parametrize("name", list(GROUPS))
def test_only_the_table_rows_and_columns_change(built, name):
    vdir = built[name]
    changes = [c for c in L.CHANGES if c[0] in GROUPS[name] and c[4]]
    files = {c[1] for c in changes}
    cmp = filecmp.dircmp(L.BASE_DIR, vdir, ignore=["__pycache__", "_ppc"])
    assert not cmp.left_only and not cmp.right_only
    for f in os.listdir(L.BASE_DIR):
        if f in ("__pycache__", "_ppc") or f == "README.md":
            continue
        same = filecmp.cmp(os.path.join(L.BASE_DIR, f), os.path.join(vdir, f), shallow=False)
        assert same == (f not in files), f
    for f in files:
        base_rows = _rows(os.path.join(L.BASE_DIR, f))
        head = base_rows[0]
        allowed = set()
        for g, fname, cond, base, expected, note_col, _label in changes:
            if fname != f:
                continue
            for i, r in enumerate(base_rows[1:], start=1):
                if L._matches(dict(zip(head, r)), cond, base):
                    allowed |= {(i, base[0]), (i, note_col)}
        cells = _changed_cells(base_rows, _rows(os.path.join(vdir, f)))
        assert cells
        assert {(i, c) for i, c, _x, _y in cells} <= allowed, f


@pytest.mark.parametrize("name", list(GROUPS))
def test_changed_values_are_base_times_1_3(built, name):
    for g, fname, cond, base, expected, note_col, _label in L.CHANGES:
        if g not in GROUPS[name] or not expected:
            continue
        b = _rows(os.path.join(L.BASE_DIR, fname))
        v = _rows(os.path.join(built[name], fname))
        head = b[0]
        col = head.index(base[0])
        n = 0
        for rb, rv in zip(b[1:], v[1:]):
            if L._matches(dict(zip(head, rb)), cond, base):
                assert Fraction(rv[col]) == Fraction(rb[col]) * Fraction(13, 10), (fname, rb, rv)
                assert rv[head.index(note_col)] == L.NOTE
                n += 1
        assert n == expected
    assert int(Fraction(15500) * Fraction(13, 10)) == 20150
    assert int(Fraction(46500) * Fraction(13, 10)) == 60450


def test_conditions_match_the_expected_rows_in_the_base():
    for g, fname, cond, base, expected, _n, _label in L.CHANGES:
        rows = _rows(os.path.join(L.BASE_DIR, fname))
        head = rows[0]
        hits = sum(1 for r in rows[1:] if r and L._matches(dict(zip(head, r)), cond, base))
        assert hits == expected, (fname, cond, base, hits, expected)


def test_a_changed_base_model_stops_the_tool(tmp_path):
    base = tmp_path / "base"
    shutil.copytree(L.BASE_DIR, base, ignore=shutil.ignore_patterns("__pycache__", "_ppc"))
    p = base / "rice_crop_limit.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("FIELD_NIIGATA,2027,46500", "FIELD_NIIGATA,2027,47000", 1),
                 encoding="utf-8")
    with pytest.raises(SystemExit, match="matched 2 rows, expected 3"):
        L.build(str(tmp_path / "out"), base_dir=str(base))
