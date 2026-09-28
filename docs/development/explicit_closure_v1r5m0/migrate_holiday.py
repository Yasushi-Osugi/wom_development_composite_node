"""Data migration for Explicit Closure v1r5m0 (Request Letter §4.8).

- supply_closure value 0.1 -> 0 (soysauce 4 models)
- supply_closure with value not in {0, 0.1} -> effect partial_capacity (value kept)
- value 0.0 rows untouched

Edits ONLY the effect / value field text of matching lines; every other byte
(BOM, line endings, quoting, other rows) is preserved.

usage: python migrate_holiday.py <repo> [--apply]
"""
import csv
import glob
import io
import os
import sys

repo = sys.argv[1]
apply = "--apply" in sys.argv
files = sorted(glob.glob(os.path.join(repo, "data", "sample", "holiday_calendar.csv"))
               + glob.glob(os.path.join(repo, "data", "sample", "*", "holiday_calendar.csv")))
totals = {}
for path in files:
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    header = next(csv.reader([lines[0]]))
    try:
        i_eff = header.index("effect"); i_val = header.index("value")
    except ValueError:
        continue
    changed = []
    out = [lines[0]]
    for ln in lines[1:]:
        body = ln.rstrip("\r\n"); eol = ln[len(body):]
        if not body.strip():
            out.append(ln); continue
        row = next(csv.reader([body]))
        if len(row) <= max(i_eff, i_val) or row[i_eff].strip() != "supply_closure":
            out.append(ln); continue
        vtxt = row[i_val].strip()
        v = float(vtxt) if vtxt else 0.0
        # Re-serialise only this row: fields are simple (no quoting) in all
        # sample files -- verified by the round-trip assertion below.
        assert ",".join(row) == body, (path, body)
        if v == 0.1:
            row[i_val] = "0"; kind = "0.1->0"
        elif v == 0.0:
            out.append(ln); continue
        else:
            row[i_eff] = "partial_capacity"; kind = "->partial_capacity"
        new = ",".join(row)
        changed.append((kind, body, new))
        out.append(new + eol)
    if not changed:
        continue
    rel = os.path.relpath(path, repo)
    for kind, _o, _n in changed:
        totals[(rel, kind)] = totals.get((rel, kind), 0) + 1
    print(f"## {rel}")
    for kind, o, n in changed:
        print(f"  [{kind}] {o}\n     -> {n}")
    if apply:
        data = "".join(out).encode("utf-8")
        open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + data)
print("\nSUMMARY")
for (rel, kind), n in sorted(totals.items()):
    print(f"  {n:3d}  {kind:20s} {rel}")
print("  total", sum(totals.values()))
