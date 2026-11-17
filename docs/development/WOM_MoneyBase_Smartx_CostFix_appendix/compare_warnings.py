# -*- coding: utf-8 -*-
"""Warnings (ppc_warnings.csv, unused_rule_row*) vs. the survey of 2026-11-15 (minus the rows removed in part A)."""
import os, sys
import pandas as pd
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
run = sys.argv[1] if len(sys.argv) > 1 else "run1"
OUT = os.path.join(REPO, "output", "moneybase_costfix", run)
u = pd.read_csv(os.path.join(REPO, "output", "moneybase_unapplied", "unapplied_rows.csv"))
z = pd.read_csv(os.path.join(REPO, "output", "moneybase_unapplied", "zero_rows_not_applied.csv"))
gone = {"apparel-us-2026", "ev-europe-2026", "ev-thailand-2026", "ev-thailand-2026_update"}
rows = []
for m in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, m, "ppc", "ppc_warnings.csv")
    if not os.path.exists(p):
        continue
    w = pd.read_csv(p, dtype=str, keep_default_na=False)
    for kind, src in (("unused_rule_row", u), ("unused_rule_row_zero", z)):
        got = {x.split(" ")[0] for x in w.loc[w["kind"] == kind, "location"]}
        s = src[(src["model"] == m) & (src["ledger"] == "PPC")]
        if kind == "unused_rule_row" and m in gone:
            s = s[s["file"] != "ppc_supplier_cost.csv"]
        want = {f"{r.file}:{r.line}" for r in s.itertuples()}
        rows.append({"model": m, "kind": kind, "warnings": len(got), "survey": len(want), "same": got == want,
                     "only_warning": ";".join(sorted(got - want)), "only_survey": ";".join(sorted(want - got))})
    rr = w[w["kind"] == "unused_rule_row"]
    for reason in ("ppc_unused_edge", "no_shipment", "key_or_place"):
        rows[-2][reason] = int(rr["detail"].str.contains(f"（{reason}）").sum())
r = pd.DataFrame(rows)
r.to_csv(os.path.join(OUT, "..", f"warnings_vs_survey_{run}.csv"), index=False, encoding="utf-8-sig")
pd.set_option("display.width", 250, "display.max_colwidth", 80)
print(r.to_string(index=False))
print("ALL SAME" if r["same"].all() else "DIFFERENT")
