"""CapTrial work 2 (RequestLetter_CapTrial_Golden_and_ClosureRows §2.2):
partial_capacity rows whose business intent is a closure -> supply_closure, 0.

Selection is explicit per file (holiday_id + node_name), not by value, so the
16 rows that stay partial_capacity cannot be caught by accident. Only the
effect and value fields of matching lines are rewritten; every other byte
(BOM, line endings, other rows) is preserved.

usage: python migrate_closure_rows.py <repo> [--apply]
"""
import csv, os, sys

repo = sys.argv[1]
apply = "--apply" in sys.argv
S = os.path.join(repo, "data", "sample")
RICE = ([(h, n) for h in ("GW_2027_supply", "GW_2028_supply")
         for n in ("DC_Higashi", "DC_Nishi", "Seihaku_E", "Seihaku_W")]
        + [(h, n) for h in ("OBON_2027_supply", "OBON_2028_supply",
                            "NEWYEAR_2027_supply", "NEWYEAR_2028_supply")
           for n in ("DC_Higashi", "DC_Nishi")])
TARGETS = {
    os.path.join(S, "rice-japan-2027-2028", "holiday_calendar.csv"): RICE,
    os.path.join(S, "rice-japan-2027-2028_BK260613_1515", "holiday_calendar.csv"): RICE,
    os.path.join(S, "iphone_global", "holiday_calendar.csv"):
        [(f"DIWALI_{y}", "BoschSensor_IN") for y in (2027, 2028, 2029)],
    os.path.join(S, "smartx-2027-2029", "holiday_calendar.csv"):
        [(f"DIWALI_{y}", "SensorIN") for y in (2026, 2027, 2028, 2029, 2030)],
    os.path.join(S, "holiday_calendar.csv"):
        [("GW_2027", "DAD_Japan"), ("GW_2028", "DAD_Japan")],
    os.path.join(S, "oil-global-2027", "holiday_calendar.csv"):
        [("Hormuz_Strait_Closure_2027", "Refinery_Local_H")],
    os.path.join(S, "ev-thailand-2026_update", "holiday_calendar.csv"):
        [("GOLDEN_WEEK_2026", "Factory_Import_CN"), ("GOLDEN_WEEK_2027", "Factory_Import_CN")],
}

total = 0
for path, keys in TARGETS.items():
    raw = open(path, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = (raw[3:] if bom else raw).decode("utf-8")
    lines = text.splitlines(keepends=True)
    hdr = next(csv.reader([lines[0]]))
    ih, inode, ie, iv = (hdr.index(c) for c in ("holiday_id", "node_name", "effect", "value"))
    want = set(keys); hit = set(); out = [lines[0]]
    for ln in lines[1:]:
        body = ln.rstrip("\r\n"); eol = ln[len(body):]
        row = next(csv.reader([body])) if body.strip() else []
        key = (row[ih].strip(), row[inode].strip()) if len(row) > max(ih, inode, ie, iv) else None
        if key in want:
            assert ",".join(row) == body, (path, body)
            assert row[ie].strip() == "partial_capacity", (path, body)
            row[ie] = "supply_closure"; row[iv] = "0"
            new = ",".join(row)
            print(f"  {os.path.relpath(path, repo)}\n     {body}\n  -> {new}")
            out.append(new + eol); hit.add(key)
        else:
            out.append(ln)
    missing = want - hit
    assert not missing, (path, missing)
    total += len(hit)
    if apply:
        open(path, "wb").write((b"\xef\xbb\xbf" if bom else b"") + "".join(out).encode("utf-8"))
print("total rows:", total)
