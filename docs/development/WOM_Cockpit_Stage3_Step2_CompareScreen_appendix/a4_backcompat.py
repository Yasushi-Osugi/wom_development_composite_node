# -*- coding: utf-8 -*-
"""A4-1: the new comparison tool on the old fixed-cost tables gives the old outputs (stage-1 workspace)."""
import filecmp
import json
import os
import sys

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)
from tools import compare_scenarios as CS  # noqa: E402

WS = os.path.join("output", "cockpit_cases", "stage1")
OUT = os.path.join("output", "cockpit_step2", "a4_backcompat")
rows = []
for pair in ("C01__C02", "C03__C04", "C05__C06", "C01__C05", "C02__C04"):
    b, a = pair.split("__")
    old = os.path.join(WS, "compare", pair)
    new = os.path.join(OUT, pair)
    cb = json.load(open(os.path.join(WS, b, "case.json"), encoding="utf-8"))["run"]
    ca = json.load(open(os.path.join(WS, a, "case.json"), encoding="utf-8"))["run"]
    fcp = os.path.join(old, "fixed_cost_plan.csv")
    CS.compare(os.path.join(WS, b, "run"), os.path.join(WS, a, "run"), os.path.join(WS, b, cb["money_model"]),
               os.path.join(WS, a, ca["money_model"]), new, fixed_cost_plan=fcp if os.path.exists(fcp) else None,
               base_name=b, alt_name=a,
               base_udp=os.path.join(WS, b, cb["udp_dir"]) if cb.get("udp_dir") else None,
               alt_udp=os.path.join(WS, a, ca["udp_dir"]) if ca.get("udp_dir") else None)
    for f in sorted(os.listdir(old)):
        if not f.endswith(".csv") or f == "fixed_cost_plan.csv":
            continue
        same = filecmp.cmp(os.path.join(old, f), os.path.join(new, f), shallow=False)
        note = ""
        if not same:
            o = pd.read_csv(os.path.join(old, f), dtype=str, keep_default_na=False)
            n = pd.read_csv(os.path.join(new, f), dtype=str, keep_default_na=False)
            common = [c for c in o.columns if c in n.columns]
            added = [c for c in n.columns if c not in o.columns]
            removed = [c for c in o.columns if c not in n.columns]
            eq = o[common].equals(n[common])
            same_values = eq and not removed
            note = f"common columns equal={eq}; added={added}; removed={removed}"
            same = "values" if same_values else False
        rows.append({"pair": pair, "file": f, "same": same, "note": note})
    rows.append({"pair": pair, "file": "planned_output_weeks.csv (new)", "same": "new", "note": ""})
r = pd.DataFrame(rows)
r.to_csv(os.path.join(OUT, "backcompat.csv"), index=False, encoding="utf-8-sig")
pd.set_option("display.width", 250, "display.max_colwidth", 200)
print(r.to_string(index=False))
print("ALL OK" if all(x in (True, "values", "new") for x in r["same"]) else "DIFFERENCE")
