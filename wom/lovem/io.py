# -*- coding: utf-8 -*-
"""wom/lovem/io.py — read a LOVEM run folder (JSON Lines, optionally gzip)."""
from __future__ import annotations

import gzip
import json
import os
from typing import Iterator


def iter_jsonl(path: str) -> Iterator[dict]:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def run_file(run_dir: str, name: str) -> str:
    """Resolve `name` (e.g. 'events.jsonl') to the stored file (.jsonl or .jsonl.gz)."""
    p = os.path.join(run_dir, name)
    if os.path.exists(p):
        return p
    if os.path.exists(p + ".gz"):
        return p + ".gz"
    raise FileNotFoundError(p)


def load_manifest(run_dir: str) -> dict:
    with open(os.path.join(run_dir, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def snapshot_files(run_dir: str) -> dict:
    """{snapshot_id: path} from manifest.snapshots[*].intervals_file."""
    man = load_manifest(run_dir)
    return {s["snapshot_id"]: os.path.join(run_dir, s["intervals_file"]) for s in man["snapshots"]}
