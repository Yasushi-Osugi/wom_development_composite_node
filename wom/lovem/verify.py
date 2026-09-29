# -*- coding: utf-8 -*-
"""
wom/lovem/verify.py — producer-side self check of a run folder (A4-2).

For every snapshot, decodes its psi_intervals file back to per-week
multisets and compares every (product, node, layer, bucket, week) with
state_digests.jsonl (entry_count, total_quantity, multiset_sha256). Also runs
the structural interval checks. This is Code君's self check; the independent
checker of stage C must not import this module (request §2).
"""
from __future__ import annotations

from collections import Counter, defaultdict

from wom.lovem.digest import multiset_sha256_from_counter
from wom.lovem.intervals import validate_intervals
from wom.lovem.io import iter_jsonl, load_manifest, run_file, snapshot_files


def verify_run(run_dir: str) -> dict:
    man = load_manifest(run_dir)
    n_weeks = man["weeks"]["weeks"]
    digests = defaultdict(list)
    for d in iter_jsonl(run_file(run_dir, "state_digests.jsonl")):
        digests[d["snapshot_id"]].append(d)

    n_rows = n_ok = n_iv = 0
    mismatches, struct_errs, orphan = [], [], []
    ids = set()
    dup_ids = 0
    for snap_id, path in snapshot_files(run_dir).items():
        intervals = list(iter_jsonl(path))
        n_iv += len(intervals)
        for r in intervals:
            if r["interval_id"] in ids:
                dup_ids += 1
            ids.add(r["interval_id"])
            if r["snapshot_id"] != snap_id:
                struct_errs.append(f"interval {r['interval_id']} in file of {snap_id} has snapshot {r['snapshot_id']}")
        struct_errs += validate_intervals(intervals, n_weeks)[:20]
        cells = defaultdict(lambda: defaultdict(Counter))
        for r in intervals:
            key = (r["product_id"], r["node_id"], r["layer"], r["bucket"])
            k2 = (r["lot_id"], r["role_id"], r["quantity"])
            for w in range(r["start_week_index"], r["end_week_index"] + 1):
                cells[key][w][k2] += r["multiplicity"]
        del intervals
        seen = set()
        for d in digests.pop(snap_id, []):
            n_rows += 1
            key = (d["product_id"], d["node_id"], d["layer"], d["bucket"])
            seen.add(key)
            c = cells.get(key, {}).get(d["week_index"], Counter())
            cnt = sum(c.values())
            qty = sum(q * m for (_l, _r, q), m in c.items())
            h = multiset_sha256_from_counter(c)
            if (cnt, qty, h) == (d["entry_count"], d["total_quantity"], d["multiset_sha256"]):
                n_ok += 1
            elif len(mismatches) < 50:
                mismatches.append({"snapshot_id": snap_id, "key": list(key), "week_index": d["week_index"],
                                   "digest": [d["entry_count"], d["total_quantity"], d["multiset_sha256"]],
                                   "decoded": [cnt, qty, h]})
        orphan += [[snap_id, *k] for k in sorted(set(cells) - seen)]
    leftover = sorted(digests)       # digests whose snapshot has no interval file
    ok = (n_ok == n_rows and not orphan and not struct_errs and not leftover and dup_ids == 0)
    return {"digest_rows": n_rows, "digest_rows_matched": n_ok, "all_match": ok,
            "n_intervals": n_iv, "duplicate_interval_ids": dup_ids,
            "mismatches": mismatches, "interval_keys_without_digest": orphan[:20],
            "digest_snapshots_without_intervals": leftover, "structural_errors": struct_errs[:20]}
