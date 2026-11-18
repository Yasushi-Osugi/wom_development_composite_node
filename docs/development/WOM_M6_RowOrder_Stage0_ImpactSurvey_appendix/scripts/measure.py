# -*- coding: utf-8 -*-
"""Row-order bias stage 0 (read only), §1.2: the measured push-backs.

Runs the headless planning of each golden model with the golden's plugin set and lot flow mode, and wraps
BackwardPlanner._apply_mom_cap_backward inside this script (the engine file is not changed). The wrapper
calls the original and only reads the node before and after:

    overflow(w)   = the lots appended to psi4demand[w][CO] by the call
    week list(w)  = psi4demand[w][S] after the call + overflow(w)   (= the list the call clipped)
    closed(w)     = not node.is_open(w)
    dropped       = the entries the call added to result.past_due_lots (week 0 overflow)

Per factory x product: overflow weeks (n > 0, closed weeks excluded), of which weeks whose list holds >= 2
markets, closed weeks that pushed lots back (and of which with >= 2 markets), total pushed-back lots, dropped
lots by market. The snapshot is compared with tests/golden/<model>.json (period, products, config, forward,
backward, ppc, psi); a difference stops the survey (the wrapper would be changing the plan).

One model at a time; each result goes to output/roworder_stage0/<model>.json before the next. Existing
result files are skipped. rice is run last. The legacy golden (tests/golden/legacy) is run as <model>__legacy.

    python output/roworder_stage0/measure.py [model ...]
"""
import collections
import glob
import json
import os
import sys
import tempfile
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
os.chdir(REPO)

from wom.engine import backward_planner as BPm  # noqa: E402
from wom.model.plan_node import S, CO  # noqa: E402

KEYS = ("period", "products", "config", "forward", "backward", "ppc", "psi")


def region(lot):
    p = str(lot).split(":")
    return p[1] if len(p) >= 3 else "?"


REC = []          # one entry per call
_orig = BPm.BackwardPlanner._apply_mom_cap_backward


def wrapped(self, node, n_weeks, result):
    if node.node_type != "mom":
        return _orig(self, node, n_weeks, result)
    co_before = [len(node.psi4demand[w][CO]) for w in range(n_weeks)]
    pd_before = len(result.past_due_lots)
    _orig(self, node, n_weeks, result)
    labels = list(node.week_labels or [str(w) for w in range(n_weeks)])
    weeks = []
    for w in range(n_weeks):
        over = list(node.psi4demand[w][CO])[co_before[w]:]
        lst = list(node.psi4demand[w][S]) + over
        closed = not node.is_open(w)
        if not over and not (closed and lst):
            continue
        weeks.append({"w": labels[w], "closed": closed, "list_n": len(lst), "overflow": len(over),
                      "markets": len({region(l) for l in lst}),
                      "overflow_markets": dict(collections.Counter(region(l) for l in over))})
    drop = result.past_due_lots[pd_before:]
    REC.append({"product": CUR.get("product", ""), "factory": node.node_name,
                "weeks": weeks, "dropped": dict(collections.Counter(region(l) for _n, l, _w in drop))})


CUR = {}
_orig_run = BPm.BackwardPlanner.run


def wrapped_run(self, prod_nm, *a, **k):
    CUR["product"] = prod_nm        # only remembers which product the calls belong to
    return _orig_run(self, prod_nm, *a, **k)


BPm.BackwardPlanner._apply_mom_cap_backward = wrapped
BPm.BackwardPlanner.run = wrapped_run
from tools.run_headless_from_folder import run  # noqa: E402


def summarize(rec):
    wk = rec["weeks"]
    ov = [x for x in wk if x["overflow"] > 0 and not x["closed"]]
    cl = [x for x in wk if x["closed"] and x["list_n"] > 0]
    return {
        "product": rec["product"], "factory": rec["factory"],
        "overflow_weeks": len(ov),
        "overflow_weeks_multi_market": sum(1 for x in ov if x["markets"] >= 2),
        "closed_weeks_pushed": len(cl),
        "closed_weeks_pushed_multi_market": sum(1 for x in cl if x["markets"] >= 2),
        "pushed_back_lots": sum(x["overflow"] for x in wk),
        "dropped_by_market": rec["dropped"], "dropped_total": sum(rec["dropped"].values()),
        "first_overflow_week": wk[0]["w"] if wk else "", "last_overflow_week": wk[-1]["w"] if wk else "",
    }


def measure(model, legacy=False):
    tag = model + ("__legacy" if legacy else "")
    out = os.path.join(OUT, tag + ".json")
    if os.path.exists(out):
        print(f"[skip] {tag}")
        return
    gpath = os.path.join(REPO, "tests", "golden", *(("legacy",) if legacy else ()), model + ".json")
    golden = json.load(open(gpath, encoding="utf-8"))
    plugins = ",".join(golden.get("config", {}).get("plugins", [])) or "none"
    mode = "legacy" if legacy else golden.get("config", {}).get("lot_flow_mode", "legacy")
    REC.clear()
    t0 = time.time()
    with tempfile.TemporaryDirectory() as td:
        snap = run(os.path.join(REPO, "data", "sample", model), plugins_spec=plugins,
                   output_ppc_dir=os.path.join(td, "ppc"), verbose=False, lot_flow_mode=mode)
    diff = [k for k in KEYS if k in golden and snap.get(k) != golden[k]]
    res = {"model": model, "legacy_golden": legacy, "plugins": plugins, "lot_flow_mode": mode,
           "seconds": round(time.time() - t0, 1), "golden_match": not diff, "golden_diff_keys": diff,
           "factories": [summarize(r) for r in REC], "weeks_detail": REC}
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[done] {tag} {res['seconds']}s golden_match={res['golden_match']} "
          f"factories={[(f['factory'], f['overflow_weeks_multi_market'], f['closed_weeks_pushed_multi_market']) for f in res['factories']]}")
    if diff:
        print(f"STOP: {tag} differs from golden in {diff}")
        sys.exit(3)


if __name__ == "__main__":
    models = sys.argv[1:] or sorted(os.path.splitext(os.path.basename(p))[0]
                                    for p in glob.glob(os.path.join(REPO, "tests", "golden", "*.json")))
    models = [m for m in models if not m.startswith("rice")] + [m for m in models if m.startswith("rice")]
    for m in models:
        measure(m)
    if not sys.argv[1:]:
        for p in sorted(glob.glob(os.path.join(REPO, "tests", "golden", "legacy", "*.json"))):
            measure(os.path.splitext(os.path.basename(p))[0], legacy=True)
