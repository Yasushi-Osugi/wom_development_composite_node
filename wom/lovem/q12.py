# -*- coding: utf-8 -*-
"""
wom/lovem/q12.py — Q12 (observation must not interfere) evidence.

fingerprint_run() runs the headless pipeline once and returns a fingerprint
of EVERYTHING the plan produced: every node / layer / bucket / week list in
its original order, every ForwardPlanner._actual_s list, every
ForwardPlanResult / BackwardPlanResult record, _push_shortfall, the headless
snapshot (golden fields) and the PPC output files. The same measurement
hooks are used whether the LOVEM observer is ON or OFF, so a difference can
only come from the observer.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
from contextlib import contextmanager


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


@contextmanager
def _measure(store: dict):
    import wom.engine.forward_planner as fpm
    import wom.engine.backward_planner as bp
    import tools.run_headless_from_folder as rh
    o_f, o_b, o_s = fpm.ForwardPlanner.run, bp.BackwardPlanner.run, rh._psi_signature

    def f(self, prod):
        r = o_f(self, prod)
        store.setdefault("actual", {})[prod] = copy.deepcopy(self._actual_s)
        store.setdefault("fres", {})[prod] = copy.deepcopy(vars(r))
        return r

    def b(self, prod):
        r = o_b(self, prod)
        store.setdefault("bres", {})[prod] = copy.deepcopy(vars(r))
        return r

    def s(sc_tree, n):
        store["tree"] = sc_tree
        return o_s(sc_tree, n)

    fpm.ForwardPlanner.run, bp.BackwardPlanner.run, rh._psi_signature = f, b, s
    try:
        yield
    finally:
        fpm.ForwardPlanner.run, bp.BackwardPlanner.run, rh._psi_signature = o_f, o_b, o_s


def fingerprint_run(model_dir: str, plugins: str, observe_out: str = None,
                    lot_flow_mode: str = None) -> dict:
    """Run once (observer ON when observe_out is given) and fingerprint it."""
    from tools.run_headless_from_folder import run as run_headless
    from wom.lovem.observer import observe_run

    tmp = tempfile.mkdtemp(prefix="lovem_q12_")
    work = os.path.join(tmp, os.path.basename(os.path.abspath(model_dir)))
    shutil.copytree(model_dir, work)
    store: dict = {}
    ppc_dir = os.path.join(tmp, "ppc")
    try:
        with _measure(store):
            if observe_out:
                # exactly the production observation path (observe_run)
                snap = observe_run(model_dir, observe_out, plugins=plugins, label="q12",
                                   lot_flow_mode=lot_flow_mode)
                ppc_dir = os.path.join(observe_out, "ppc")
            else:
                snap = run_headless(work, plugins_spec=plugins,
                                    output_ppc_dir=ppc_dir, verbose=False,
                                    lot_flow_mode=lot_flow_mode)
        tree = store["tree"]
        cells = {}
        for prod in tree.products:
            for nd in tree.iter_all_nodes(prod):
                for layer, psi in (("demand", nd.psi4demand), ("supply", nd.psi4supply)):
                    cells[f"{prod}|{nd.node_id}|{layer}"] = _h([[list(b) for b in wk] for wk in psi])
                cells[f"{prod}|{nd.node_id}|push_shortfall"] = _h(
                    {str(k): v for k, v in (getattr(nd, "_push_shortfall", None) or {}).items()})
                cells[f"{prod}|{nd.node_id}|plan_mode"] = nd.plan_mode
        ppc_files = {}
        for fn in sorted(os.listdir(ppc_dir)) if os.path.isdir(ppc_dir) else []:
            with open(os.path.join(ppc_dir, fn), "rb") as fh:
                ppc_files[fn] = hashlib.sha256(fh.read()).hexdigest()
        return {
            "snapshot": _h(snap),
            "snapshot_golden_fields": {k: snap[k] for k in ("forward", "backward", "ppc")},
            "cells": cells,
            "actual_s": {p: _h({str(n): {str(w): l for w, l in d.items()} for n, d in a.items()})
                         for p, a in store.get("actual", {}).items()},
            "forward_results": {p: _h(v) for p, v in store.get("fres", {}).items()},
            "backward_results": {p: _h(v) for p, v in store.get("bres", {}).items()},
            "ppc_files": ppc_files,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def compare_on_off(model_dir: str, plugins: str, observe_out: str,
                   lot_flow_mode: str = None) -> dict:
    off = fingerprint_run(model_dir, plugins, lot_flow_mode=lot_flow_mode)
    on = fingerprint_run(model_dir, plugins, observe_out=observe_out, lot_flow_mode=lot_flow_mode)
    diffs = []
    for key in ("snapshot", "actual_s", "forward_results", "backward_results", "ppc_files"):
        if off[key] != on[key]:
            diffs.append(key)
    cell_diffs = sorted(k for k in set(off["cells"]) | set(on["cells"])
                        if off["cells"].get(k) != on["cells"].get(k))
    return {"identical": not diffs and not cell_diffs, "top_level_diffs": diffs,
            "cell_diffs": cell_diffs, "n_cells": len(off["cells"]),
            "ppc_files": sorted(off["ppc_files"]), "off": off, "on": on}
