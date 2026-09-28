# -*- coding: utf-8 -*-
"""Before/after probe for the Explicit Closure v1r5m0 implementation.

Runs every golden case (+ soysauce-jpy-2027-alloc original and P_opt/800) on a
COPY of the model folder (originals untouched), and dumps per-node weekly
series + diagnostics + strategic KPI to <out>/<case>.json.

usage: python probe_closure.py <repo_root> <out_dir> [case ...]
"""
import copy
import gzip
import json
import os
import shutil
import sys
import tempfile

REPO = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
ONLY = set(sys.argv[3:])
sys.path.insert(0, REPO)
os.chdir(REPO)

from wom.model.plan_node import S, CO, I, P  # noqa: E402
import wom.engine.forward_planner as fpm  # noqa: E402
import wom.engine.backward_planner as bpm  # noqa: E402
import wom.engine.push_pull as ppm  # noqa: E402
import tools.run_headless_from_folder as rh  # noqa: E402

CAP = {}


def _wrap_fwd():
    orig = fpm.ForwardPlanner.run

    def run(self, prod_nm):
        res = orig(self, prod_nm)
        CAP.setdefault("fwd", []).append((prod_nm, res, copy.deepcopy(self._actual_s)))
        return res
    fpm.ForwardPlanner.run = run


def _wrap_bwd():
    orig = bpm.BackwardPlanner.run

    def run(self, prod_nm):
        res = orig(self, prod_nm)
        CAP.setdefault("bwd", []).append((prod_nm, res))
        return res
    bpm.BackwardPlanner.run = run


def _wrap_push():
    orig = ppm.PushProductionPlanner.setup_all

    def setup_all(self, cfgs):
        res = orig(self, cfgs)
        CAP.setdefault("push", []).append(res)
        return res
    ppm.PushProductionPlanner.setup_all = setup_all


def _wrap_sig():
    orig = rh._psi_signature

    def sig(sc_tree, n_weeks):
        CAP["sc_tree"] = sc_tree
        return orig(sc_tree, n_weeks)
    rh._psi_signature = sig


_wrap_fwd(); _wrap_bwd(); _wrap_push(); _wrap_sig()


def _diag(obj):
    """Collect list-valued diagnostics whose name hints closure/mode4."""
    out = {}
    for k, v in vars(obj).items():
        if isinstance(v, list) and any(t in k for t in ("closure", "mode4")):
            out[k] = [list(x) if isinstance(x, tuple) else x for x in v]
    return out


def dump(case, snap, n_weeks):
    t = CAP["sc_tree"]
    actual = {}
    for prod, _res, act in CAP.get("fwd", []):
        for nid, byw in act.items():
            actual[nid] = {int(w): len(v) for w, v in byw.items()}
    nodes = {}
    for prod in t.products:
        for nd in t.iter_all_nodes(prod):
            sup, dem = nd.psi4supply, nd.psi4demand
            a = actual.get(nd.node_id, {})
            sf = getattr(nd, "_push_shortfall", None) or {}
            nodes[f"{prod}|{nd.node_name}"] = {
                "node_type": nd.node_type, "plan_mode": nd.plan_mode,
                "P": [len(sup[w][P]) for w in range(n_weeks)],
                "S": [len(sup[w][S]) for w in range(n_weeks)],
                "I": [len(sup[w][I]) for w in range(n_weeks)],
                "CO": [len(sup[w][CO]) for w in range(n_weeks)],
                "dS": [len(dem[w][S]) for w in range(n_weeks)],
                "dP": [len(dem[w][P]) for w in range(n_weeks)],
                "actual": [a.get(w, 0) for w in range(n_weeks)],
                "shortfall": [sf.get(w, 0) for w in range(n_weeks)],
                "cap_hard": [nd.cap_hard(w) for w in range(n_weeks)],
                "cap_soft": [nd.cap_soft(w) for w in range(n_weeks)],
                "is_open": [nd.is_open(w) for w in range(n_weeks)],
                "P_ids": sorted({x for w in range(n_weeks) for x in sup[w][P]}) if nd.node_type == "leaf_in" else None,
            }
    diags = {"fwd": [], "push": [], "past_due": {}}
    for prod, bres in CAP.get("bwd", []):
        diags["past_due"][prod] = diags["past_due"].get(prod, 0) + len(getattr(bres, "past_due_lots", []) or [])
    for prod, res, _a in CAP.get("fwd", []):
        diags["fwd"].append({"prod": prod, **_diag(res)})
    for d in CAP.get("push", []):
        for prod, r in d.items():
            diags["push"].append({"prod": prod, **_diag(r)})
    from wom.engine.strategic_kpi import compute_strategic_kpi
    try:
        sk = vars(compute_strategic_kpi(t))
        sk = {k: (v if isinstance(v, (int, float, str, type(None))) else str(v)) for k, v in sk.items()}
    except Exception as e:  # noqa: BLE001
        sk = {"error": repr(e)}
    snap = {k: v for k, v in snap.items() if k != "planning_state_extras"}
    ex = snap.pop("_extras", None)
    rec = {"snap": snap, "weeks": list(t.week_labels), "nodes": nodes,
           "diags": diags, "strategic_kpi": sk, "extras": ex}
    with gzip.open(os.path.join(OUT, case + ".json.gz"), "wt", encoding="utf-8") as f:
        json.dump(rec, f)


def run_case(case, model_src, plugins, popt=False):
    CAP.clear()
    tmp = tempfile.mkdtemp(prefix="wom_probe_")
    mdir = os.path.join(tmp, os.path.basename(model_src))
    shutil.copytree(model_src, mdir)
    kw = {}
    if popt:
        from tools.run_planning_loop import _scenario_blocks
        from wom.allocation.merit_order import true_continuous_optimum
        from wom.allocation.handoff import write_demand_for_allocation
        blocks, tp, sc = _scenario_blocks(mdir, "s1_base", None)
        to = true_continuous_optimum(blocks, sc, 800.0, transfer_price_usd=tp)
        h = write_demand_for_allocation(mdir, dict(to["x"]), "POPT", cap_wk=800.0, uom=None)
        kw = {"demand_file": os.path.basename(h["path"]), "planning_state": True}
    snap = rh.run(mdir, plugins_spec=plugins, output_ppc_dir=os.path.join(tmp, "ppc"),
                  verbose=False, **kw)
    if popt:
        snap["_extras"] = {"capacity_series": snap.get("planning_state_extras", {}).get("capacity_series")}
    dump(case, snap, snap["period"]["weeks"])
    shutil.rmtree(tmp, ignore_errors=True)
    print(case, "ok", snap["ppc"]["gross_profit_base"], flush=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    gdir = os.path.join(REPO, "tests", "golden")
    jobs = []
    for fn in sorted(os.listdir(gdir)):
        if fn.endswith(".json"):
            case = fn[:-5]
            g = json.load(open(os.path.join(gdir, fn), encoding="utf-8"))
            pl = ",".join(g.get("config", {}).get("plugins", [])) or "none"
            jobs.append((case, os.path.join(REPO, "data", "sample", case), pl, False))
    alloc = os.path.join(REPO, "data", "sample", "soysauce-jpy-2027-alloc")
    jobs.append(("soysauce-jpy-2027-alloc", alloc, "safe", False))
    jobs.append(("soysauce-jpy-2027-alloc__P_opt800", alloc, "safe", True))
    jobs.append(("ev-thailand-2026_update", os.path.join(REPO, "data", "sample", "ev-thailand-2026_update"), "safe", False))
    jobs.append(("rice-japan-2027-2028_BK260613_1515", os.path.join(REPO, "data", "sample", "rice-japan-2027-2028_BK260613_1515"),
                 "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,HarvestBatchPlugin", False))
    for case, src, pl, popt in jobs:
        if ONLY and case not in ONLY:
            continue
        try:
            run_case(case, src, pl, popt)
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            print(case, "FAILED", e, flush=True)


if __name__ == "__main__":
    main()
