# -*- coding: utf-8 -*-
"""
wom/lovem/intervals.py — PSI cell series  <->  interval records (design §8.5).

encode_series() turns the per-week Lot_ID lists of ONE (node, layer, bucket)
into interval records; decode_intervals() expands them back to per-week
multisets. The round trip preserves, for every observed week, the multiset
of (lot_id, role_id, quantity, multiplicity). The original list ORDER is not
reconstructible from intervals (design §8.6); ordered_sha256 in
state_digests keeps an order fingerprint separately.

Compression rule (design §8.5):
  * state buckets (I, CO -- both layers): consecutive observed weeks in which
    the same lot_id has the same multiplicity (and same role/quantity/unit/
    evidence) form one interval [start, end] (both ends inclusive).
    A change of multiplicity, or a week not observed, splits the interval.
  * flow buckets (P, S): always single-week intervals (start == end), so a
    receipt/request in consecutive weeks is never drawn as one dwelling line.

The caller supplies the lists; this module never mutates them.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

from wom.lovem.digest import QTY_PER_OCCURRENCE, ROLE_NONE, UNIT_LOT

STATE_BUCKETS = frozenset({"I", "CO"})
FLOW_BUCKETS = frozenset({"P", "S"})


def encode_series(weekly: Sequence[Optional[Sequence[str]]], *, bucket: str,
                  base: dict, role_id: str = ROLE_NONE,
                  quantity=QTY_PER_OCCURRENCE, unit: str = UNIT_LOT,
                  week_offset: int = 0) -> List[dict]:
    """Encode one cell series.

    weekly[i] is the lot list of week (week_offset + i), or None when that
    week was NOT observed (a gap -- never bridged).
    base: fields copied into every record (run_id, snapshot_id, phase,
    product_id, node_id, layer, evidence_level, evidence_ref ...).
    Returns records WITHOUT interval_id (the writer assigns it).
    """
    compress = bucket in STATE_BUCKETS
    out: List[dict] = []

    def rec(lot, start, end, mult):
        r = dict(base)
        r.update(bucket=bucket, lot_id=lot, role_id=role_id,
                 start_week_index=start, end_week_index=end,
                 quantity=quantity, unit=unit, multiplicity=mult)
        return r

    open_: Dict[str, List[int]] = {}      # lot -> [start, mult]
    for i, lots in enumerate(weekly):
        w = week_offset + i
        if lots is None:                    # unobserved week: close everything
            for lot, (s, m) in open_.items():
                out.append(rec(lot, s, w - 1, m))
            open_ = {}
            continue
        cnt = Counter(lots)
        if not compress:
            for lot in _first_seen_order(lots):
                out.append(rec(lot, w, w, cnt[lot]))
            continue
        for lot in list(open_):
            s, m = open_[lot]
            if cnt.get(lot, 0) != m:
                out.append(rec(lot, s, w - 1, m))
                del open_[lot]
        for lot in _first_seen_order(lots):
            if lot not in open_:
                open_[lot] = [w, cnt[lot]]
    last = week_offset + len(weekly) - 1
    for lot, (s, m) in open_.items():
        out.append(rec(lot, s, last, m))
    out.sort(key=lambda r: (r["start_week_index"], r["lot_id"], r["end_week_index"]))
    return out


def _first_seen_order(lots: Iterable[str]) -> List[str]:
    seen, order = set(), []
    for x in lots:
        if x not in seen:
            seen.add(x)
            order.append(x)
    return order


def decode_intervals(intervals: Iterable[dict]) -> Dict[tuple, Dict[int, Counter]]:
    """Expand intervals to {cell_key: {week_index: Counter}}.

    cell_key = (snapshot_id, product_id, node_id, layer, bucket).
    Counter key = (lot_id, role_id, quantity) -> multiplicity.
    """
    cells: Dict[tuple, Dict[int, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for r in intervals:
        key = (r["snapshot_id"], r["product_id"], r["node_id"], r["layer"], r["bucket"])
        k2 = (r["lot_id"], r["role_id"], r["quantity"])
        for w in range(r["start_week_index"], r["end_week_index"] + 1):
            cells[key][w][k2] += r["multiplicity"]
    return cells


def expanded_occurrences(intervals: Iterable[dict]) -> int:
    """Σ (end-start+1) × multiplicity (design §8.5)."""
    return sum((r["end_week_index"] - r["start_week_index"] + 1) * r["multiplicity"]
               for r in intervals)


def validate_intervals(intervals: Iterable[dict], n_weeks: int) -> List[str]:
    """Structural checks (design §8.6-5): start<=end, range, multiplicity,
    quantity, and overlapping intervals of the same key."""
    errs: List[str] = []
    seen: Dict[tuple, List[tuple]] = defaultdict(list)
    for r in intervals:
        s, e = r["start_week_index"], r["end_week_index"]
        if s > e:
            errs.append(f"start>end: {r}")
        if s < 0 or e >= n_weeks:
            errs.append(f"week out of range: {r}")
        if not isinstance(r["multiplicity"], int) or r["multiplicity"] < 1:
            errs.append(f"bad multiplicity: {r}")
        if r["quantity"] is None or r["quantity"] < 0:
            errs.append(f"bad quantity: {r}")
        key = (r["snapshot_id"], r["product_id"], r["node_id"], r["layer"],
               r["bucket"], r["lot_id"], r["role_id"])
        seen[key].append((s, e))
    for key, spans in seen.items():
        spans.sort()
        for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
            if s2 <= e1:
                errs.append(f"overlap {key}: {(s1, e1)} {(s2, e2)}")
    return errs
