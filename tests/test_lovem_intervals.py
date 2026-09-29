# -*- coding: utf-8 -*-
"""
tests/test_lovem_intervals.py — LOVEM stage A2: interval encoder / decoder.

Synthetic PSI series (early shipment, on-time, late, unmet, same count but
different IDs, the same ID appearing several times, unobserved weeks, year
crossing) are encoded and decoded; the per-week multiset must match exactly.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.lovem.digest import (multiset_sha256, multiset_sha256_from_counter,
                              ordered_sha256)
from wom.lovem.intervals import (decode_intervals, encode_series,
                                 expanded_occurrences, validate_intervals)

BASE = {"run_id": "t", "snapshot_id": "P/final", "phase": "final", "product_id": "P",
        "node_id": "N", "layer": "supply", "evidence_level": "observed", "evidence_ref": "t"}


def _roundtrip(weekly, bucket):
    recs = encode_series(weekly, bucket=bucket, base=BASE)
    for i, r in enumerate(recs):
        r["interval_id"] = f"iv{i}"
    cells = decode_intervals(recs)
    got = cells.get(("P/final", "P", "N", "supply", bucket), {})
    for w, lots in enumerate(weekly):
        if lots is None:
            assert not got.get(w), f"week {w} was not observed but decoded {got.get(w)}"
            continue
        want = Counter({(lot, "-", 1): m for lot, m in Counter(lots).items()})
        assert Counter(got.get(w, Counter())) == want, (bucket, w)
        assert multiset_sha256_from_counter(got.get(w, Counter())) == multiset_sha256(lots)
    assert validate_intervals(recs, len(weekly)) == []
    return recs


# early / on-time / late / unmet / same-count-different-ID, as they appear in
# the lists of one node (S = request, P = receipt, I = held, CO = carried request)
SERIES = {
    "S": [["A"], ["B"], ["C", "D"], [], ["E"], ["F"]],
    "P": [["A", "B"], [], ["C", "X"], [], ["E"], []],          # B early, X instead of D
    "I": [["B"], [], ["X"], ["X"], ["X"], ["X"]],               # X waits; B consumed
    "CO": [[], [], ["D"], ["D"], ["D"], ["D", "F"]],             # D late/unmet, F unmet
}


@pytest.mark.parametrize("bucket", ["S", "P", "I", "CO"])
def test_roundtrip_synthetic(bucket):
    _roundtrip(SERIES[bucket], bucket)


def test_state_bucket_is_compressed_flow_bucket_is_not():
    i_recs = _roundtrip(SERIES["I"], "I")
    x = [r for r in i_recs if r["lot_id"] == "X"]
    assert [(r["start_week_index"], r["end_week_index"]) for r in x] == [(2, 5)]
    s_recs = _roundtrip([["A"], ["A"], ["A"]], "S")
    assert all(r["start_week_index"] == r["end_week_index"] for r in s_recs)
    assert len(s_recs) == 3


def test_multiplicity_change_splits_interval():
    # design §8.5 example: W11 twice -> multiplicity 1,2,1 -> 3 intervals
    recs = _roundtrip([["K"], ["K", "K"], ["K"]], "I")
    assert [(r["start_week_index"], r["end_week_index"], r["multiplicity"]) for r in recs] == \
           [(0, 0, 1), (1, 1, 2), (2, 2, 1)]
    assert expanded_occurrences(recs) == 4


def test_unobserved_week_is_not_bridged():
    recs = _roundtrip([["K"], None, ["K"]], "I")
    assert [(r["start_week_index"], r["end_week_index"]) for r in recs] == [(0, 0), (2, 2)]


def test_same_count_different_ids_are_distinct():
    a = _roundtrip([["A"], ["A"]], "I")
    b = _roundtrip([["A"], ["B"]], "I")
    assert len(a) == 1 and len(b) == 2
    assert multiset_sha256(["A"]) != multiset_sha256(["B"])


def test_year_crossing_week_indices():
    # 2026 has ISO W53: indices are contiguous across W52 -> W53 -> 2027-W01
    labels = ["2026-W52", "2026-W53", "2027-W01", "2027-W02"]
    weekly = [["L"], ["L"], ["L"], []]
    recs = _roundtrip(weekly, "I")
    assert [(r["start_week_index"], r["end_week_index"]) for r in recs] == [(0, 2)]
    assert len(labels) == len(weekly)


def test_encoder_does_not_mutate_input():
    weekly = [["B", "A", "A"], ["A"]]
    snap = [list(x) for x in weekly]
    encode_series(weekly, bucket="I", base=BASE)
    encode_series(weekly, bucket="S", base=BASE)
    assert weekly == snap


def test_ordered_hash_keeps_order_multiset_hash_does_not():
    assert ordered_sha256(["A", "B"]) != ordered_sha256(["B", "A"])
    assert multiset_sha256(["A", "B"]) == multiset_sha256(["B", "A"])
    assert multiset_sha256([]) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_validate_detects_overlap_and_bad_values():
    bad = [dict(BASE, bucket="I", lot_id="A", role_id="-", start_week_index=0, end_week_index=2,
                quantity=1, unit="lot", multiplicity=1),
           dict(BASE, bucket="I", lot_id="A", role_id="-", start_week_index=2, end_week_index=3,
                quantity=1, unit="lot", multiplicity=1),
           dict(BASE, bucket="I", lot_id="B", role_id="-", start_week_index=3, end_week_index=1,
                quantity=1, unit="lot", multiplicity=0)]
    errs = validate_intervals(bad, 4)
    assert any("overlap" in e for e in errs)
    assert any("start>end" in e for e in errs)
    assert any("multiplicity" in e for e in errs)
