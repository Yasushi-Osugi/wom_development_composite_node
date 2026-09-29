# -*- coding: utf-8 -*-
"""
wom/lovem/digest.py — canonical multiset / ordered hashes of one PSI cell.

A "cell" is the list psi4demand[w][b] or psi4supply[w][b] of one node.
The normalisation rules below are the contract used by state_digests.jsonl
and by any independent checker (DATA_DICTIONARY.md §3). Keep them in sync.

  entry            : (lot_id, role_id, quantity, multiplicity)
  quantity text    : integral -> "1" (no decimal point); else repr(float)
  multiset line    : f"{lot_id}\t{role_id}\t{quantity}\t{multiplicity}"
  multiset order   : sorted by (lot_id, role_id) in Python str order
                     (Unicode code point order)
  multiset_sha256  : sha256("\n".join(lines).encode("utf-8")); empty -> sha256(b"")
  ordered_sha256   : sha256("\n".join(original lot_id list).encode("utf-8"))
"""
from __future__ import annotations

import hashlib
from collections import Counter
from typing import Dict, Iterable, List, Tuple

ROLE_NONE = "-"          # node-level cell: no component role distinguished
UNIT_LOT = "lot"
QTY_PER_OCCURRENCE = 1   # one occurrence of a Lot_ID in a PSI list = 1 lot


def fmt_quantity(q) -> str:
    qf = float(q)
    return str(int(qf)) if qf.is_integer() else repr(qf)


def multiset_entries(lots: Iterable[str], role_id: str = ROLE_NONE,
                     quantity=QTY_PER_OCCURRENCE) -> List[Tuple[str, str, object, int]]:
    """[(lot_id, role_id, quantity, multiplicity)] sorted canonically."""
    c = Counter(lots)
    return sorted(((lot, role_id, quantity, m) for lot, m in c.items()),
                  key=lambda e: (e[0], e[1]))


def multiset_sha256_from_counter(counter: Dict[Tuple[str, str, object], int]) -> str:
    """counter: {(lot_id, role_id, quantity): multiplicity}."""
    lines = [f"{lot}\t{role}\t{fmt_quantity(q)}\t{m}"
             for (lot, role, q), m in sorted(counter.items(), key=lambda kv: (kv[0][0], kv[0][1]))
             if m]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def multiset_sha256(lots: Iterable[str], role_id: str = ROLE_NONE,
                    quantity=QTY_PER_OCCURRENCE) -> str:
    c: Dict[Tuple[str, str, object], int] = {}
    for lot, m in Counter(lots).items():
        c[(lot, role_id, quantity)] = m
    return multiset_sha256_from_counter(c)


def ordered_sha256(lots: List[str]) -> str:
    return hashlib.sha256("\n".join(lots).encode("utf-8")).hexdigest()


def payload_sha256(obj) -> str:
    """Hash of a JSON payload (source_evidence.source_hash): canonical JSON,
    sort_keys=True, separators=(',', ':'), ensure_ascii=False, UTF-8."""
    import json
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
