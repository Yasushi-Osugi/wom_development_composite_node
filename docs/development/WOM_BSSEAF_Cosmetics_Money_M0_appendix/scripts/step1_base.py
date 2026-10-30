# -*- coding: utf-8 -*-
"""Step 1 (letter §2.1): fix the base. Copy the inputs of C3a / C3b (the originals are
not run in place, so they are not touched), confirm the copies are byte-identical,
run the quantity plan with the same code and plugins, and record the conditions.

python output/bsseaf_cosmetics/money_m0_work/step1_base.py   (from the repository root)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m0_common as C   # noqa: E402

res = {}
for case in ("C3b", "C3a"):
    src = os.path.join(C.COS, case)
    md = os.path.join(C.HERE, "base", case)
    C.copy_inputs(src, md)
    h_src = C.input_hashes(src)
    h_copy = C.input_hashes(md)
    snap, tree = C.run_case(md, os.path.join(C.HERE, "base", case + "_result"))
    h_after = C.input_hashes(md)
    lots, wl = C.lot_record(tree)
    C.write_json(os.path.join(C.HERE, "base", case + "_result", "lots.json"), lots)
    cfg = {r["key"]: r["value"] for r in C.read_csv(os.path.join(md, "planning_config.csv"))}
    res[case] = {
        "source": os.path.relpath(src, C.REPO).replace("\\", "/"),
        "copy_equal_to_source": h_src == h_copy,
        "inputs_unchanged_by_run": h_copy == h_after,
        "changed_by_run": sorted(k for k in h_copy if h_copy[k] != h_after.get(k)),
        "quantity_input_sha256": h_copy,
        "period": snap["period"], "config": snap["config"],
        "week_first": wl[0], "week_last": wl[-1], "n_weeks": len(wl),
        "planning_config": cfg, "cpu_size": tree.cpu_size,
        "ppc_status": snap["ppc"].get("valuation_status"),
        "demand_lots": {p: {l: len(v["demand"]) for l, v in d.items()} for p, d in lots.items()},
        "ship_lots": {p: {l: sum(len(x) for x in v["ship"].values()) for l, v in d.items()}
                      for p, d in lots.items()},
    }
    C.write_json(os.path.join(C.HERE, "base", "week_labels.json"), wl)
    print(case, res[case]["copy_equal_to_source"], res[case]["inputs_unchanged_by_run"],
          res[case]["period"], res[case]["config"]["plugins"], res[case]["ship_lots"], flush=True)
C.write_json(os.path.join(C.HERE, "base", "base_record.json"), res)
