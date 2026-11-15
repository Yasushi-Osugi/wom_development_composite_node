# -*- coding: utf-8 -*-
"""Run every golden model with the golden's plugins (headless + PPC), check snapshot == golden,
and run Value Chain for the VC models. Outputs: output/moneybase_unapplied/<model>/ (git-ignored)."""
import json
import os
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)
from tools.run_headless_from_folder import run  # noqa: E402

OUT = os.path.join(REPO, "output", "moneybase_unapplied")
VC_MODELS = {"cosmetics-sg-th-2027-2029", "Cookie-jp-2026", "soysauce-jpy-2027-alloc"}
only = set(sys.argv[1:])
res = {}
for fn in sorted(os.listdir(os.path.join(REPO, "tests", "golden"))):
    if not fn.endswith(".json"):
        continue
    m = fn[:-5]
    if only and m not in only:
        continue
    gold = json.load(open(os.path.join(REPO, "tests", "golden", fn), encoding="utf-8"))
    plugins = ",".join(gold["config"]["plugins"]) or "none"
    md = os.path.join("data", "sample", m)
    od = os.path.join(OUT, m)
    t0 = time.perf_counter()
    snap = run(md, plugins_spec=plugins, output_ppc_dir=os.path.join(od, "ppc"), verbose=False,
               flow_check_dir=os.path.join(od, "flow_check"))
    snap = json.loads(json.dumps(snap, sort_keys=True))
    same = snap == gold
    with open(os.path.join(od, "snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2, sort_keys=True)
    r = {"plugins": plugins, "snapshot_equals_golden": same, "seconds": round(time.perf_counter() - t0, 1)}
    if m in VC_MODELS:
        from wom.valuechain.run import run_valuechain
        vc = run_valuechain(os.path.abspath(md), os.path.join(od, "vc"), plugins=plugins)
        r["vc_issues"] = len(vc["checks"]["issues"])
        r["vc_unvalued_lines"] = vc["checks"]["unvalued_lines"]
    res[m] = r
    print(m, r, flush=True)
prev = {}
p = os.path.join(OUT, "run_all.json")
if os.path.exists(p):
    prev = json.load(open(p, encoding="utf-8"))
prev.update(res)
json.dump(prev, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
