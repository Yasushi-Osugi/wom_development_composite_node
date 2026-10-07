#!/usr/bin/env python3
"""Read-only smartx upper-capacity trial. Run models on temporary copies.

Instrumentation wraps calls and records events without changing their outcome.
Original core, CSVs and golden files are never written. No git mutation.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from unittest.mock import patch

BASE_SHA = "e355908b0a480b78d2d3a3f445fac38c27e93f43"
ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "data/sample/smartx-2027-2029"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1048576), b""): h.update(block)
    return h.hexdigest()


def check_base():
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if actual != BASE_SHA:
        raise RuntimeError(f"Wrong measurement SHA: {actual}; expected {BASE_SHA}")
    if subprocess.run(["git","diff","--quiet","HEAD","--"],cwd=ROOT).returncode:
        raise RuntimeError("Tracked baseline files have uncommitted changes; use an isolated clean checkout")


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, default=str)


def write_csv(path, rows, fields):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def public_result(r):
    return {k: v for k, v in vars(r).items() if not k.startswith("_")}


def measure(model: Path, out: Path, case: str, schedule_dir: Path | None = None):
    check_base()
    dest = out / "raw" / case
    if dest.exists(): raise RuntimeError(f"Refusing to overwrite {dest}")
    dest.mkdir(parents=True)
    before = {str(p.relative_to(model)): sha(p) for p in model.rglob("*") if p.is_file()}
    import tools.run_headless_from_folder as rh
    import wom.engine.backward_planner as bp
    import wom.engine.forward_planner as fp
    import wom.engine.capacity_sealer as cs
    import wom.engine.hook_bus as hb
    from wom.model.plan_node import S, CO, I, P
    old_b, old_f, old_s = bp.BackwardPlanner.run, fp.ForwardPlanner.run, rh._psi_signature
    old_d = fp.ForwardPlanResult.record_cap_hard_deferred
    old_c = fp.ForwardPlanner._process_node
    old_l = cs.load_capacity_dataframe
    old_h = hb.HookBus.fire
    store = {"bres": {}, "fres": {}, "capacity_loads": []}
    adapter=assignments=None
    if schedule_dir:
        from wom.capacity_layer.smartx_trial import SmartxAdapter
        settings=json.loads((schedule_dir/"manifest.json").read_text())
        if settings["baseline_sha"]!=BASE_SHA:
            raise ValueError("Upper schedule belongs to a different baseline SHA")
        adapter=SmartxAdapter(out/"raw/baseline",missing_capacity_policy="explicit_engine_unbounded",
            push_leads=settings["push_leads"])
        with gzip.open(schedule_dir/"lot_assignments.csv.gz","rt",encoding="utf-8",newline="") as gf:
            assignments=list(csv.DictReader(gf))

    def h(self, hook, **kw):
        r=old_h(self,hook,**kw)
        if adapter is not None and hook==hb.HOOK_POST_BACKWARD:
            adapter.apply_positions(kw["sc_tree"],kw["prod_nm"],assignments)
        return r

    def b(self, prod):
        r = old_b(self, prod); store["bres"][prod] = r; return r

    def f(self, prod):
        r = old_f(self, prod); store["fres"][prod] = r; return r

    def d(self, nid, week, lots):
        events = getattr(self, "_trial_deferrals", None)
        if events is None: self._trial_deferrals = events = []
        events.extend((nid, week, lot) for lot in lots)
        return old_d(self, nid, week, lots)

    def c(self, node, n, result, opening_lots):
        counts = getattr(result, "_trial_input_p", None)
        if counts is None: result._trial_input_p = counts = {}
        counts[node.node_id] = [len(node.psi4supply[w][P]) for w in range(n)]
        return old_c(self, node, n, result, opening_lots)

    def s(tree, n):
        store["tree"] = tree; return old_s(tree, n)

    def l(*a, **kw):
        r = old_l(*a, **kw); store["capacity_loads"].append(r); return r

    t = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="smartx_upper_") as tmp, \
         patch.object(bp.BackwardPlanner, "run", b), patch.object(fp.ForwardPlanner, "run", f), \
         patch.object(fp.ForwardPlanResult, "record_cap_hard_deferred", d), \
         patch.object(fp.ForwardPlanner, "_process_node", c), \
         patch.object(cs, "load_capacity_dataframe", l), patch.object(rh, "_psi_signature", s), \
         patch.object(hb.HookBus, "fire", h):
        work = Path(tmp) / model.name; shutil.copytree(model, work)
        snapshot = rh.run(str(work), plugins_spec="safe", output_ppc_dir=str(dest / "ppc"), verbose=True)
        tree = store["tree"]; labels = tree.week_labels
        nodes = []; weekly = []; market_rows = []; market_summary = []; global_summary = []
        stage_counts = []
        for prod in tree.products:
            fres = store["fres"][prod]
            early = late = ontime = unserved = qty = 0
            for node in tree.iter_all_nodes(prod):
                nid = node.node_id
                nodes.append({"product": prod, "node_id": nid, "node_name": node.node_name,
                    "node_type": node.node_type, "side": node.side, "plan_mode": node.plan_mode,
                    "parent_id": node.parent.node_id if node.parent else "",
                    "lt_wks": node.lt_wks, "transit_lt_wks": node.transit_lt_wks,
                    "ss_wks": node.ss_wks, "bom_qty": node.bom_qty, "cpu_size": tree.cpu_size,
                    "p_copied": nid in fres.p_copied_node_ids})
                actual = node._actual_ship
                due = {lot: w for w in range(len(labels)) for lot in node.psi4demand[w][S]}
                real = {lot: w for w in range(len(labels)) for lot in actual.get(w, [])}
                for w, week in enumerate(labels):
                    weekly.append({"product": prod, "node_id": nid, "node_name": node.node_name,
                        "week": week, "week_index": w, "cap_hard": node.cap_hard(w),
                        "cap_soft": node.cap_soft(w), "processing_limit": node.processing_limit(w),
                        "is_open": node.is_open(w), "plan_mode": node.plan_mode,
                        "demand_S": len(node.psi4demand[w][S]), "demand_P": len(node.psi4demand[w][P]),
                        "demand_CO": len(node.psi4demand[w][CO]),
                        "input_P": fres._trial_input_p.get(nid, [0] * len(labels))[w],
                        "supply_P": len(node.psi4supply[w][P]), "actual_S": len(actual.get(w, [])),
                        "supply_I": len(node.psi4supply[w][I]), "supply_CO": len(node.psi4supply[w][CO])})
                stage_counts.append({"product":prod,"node_name":node.node_name,"requested_ids":len(due),
                    "actual_ids":len(real),"late_ids":sum(real[x]>dw for x,dw in due.items() if x in real),
                    "early_ids":sum(real[x]<dw for x,dw in due.items() if x in real),
                    "missing_ids":sum(x not in real for x in due), "push_sub_exempt":node.plan_mode=="push_sub"})
                if node.node_type == "leaf_out":
                    counts = {"on_time":0,"late":0,"early":0,"terminal_backlog":0}
                    for lot, dw in due.items():
                        aw = real.get(lot)
                        status = "terminal_backlog" if aw is None else "on_time" if aw == dw else "late" if aw > dw else "early"
                        counts[status] += 1
                        market_rows.append({"product":prod,"market_node":node.node_name,"lot_id":lot,
                            "due_week":labels[dw],"due_index":dw,"actual_week":labels[aw] if aw is not None else "",
                            "actual_index":aw if aw is not None else "","status":status,
                            "delay_weeks":aw-dw if aw is not None else ""})
                    market_summary.append({"product":prod,"market":node.node_name,"demand":len(due),**counts})
                    qty+=len(due); ontime+=counts["on_time"]; late+=counts["late"]; early+=counts["early"]; unserved+=counts["terminal_backlog"]
            global_summary.append({"product":prod,"demand":qty,"on_time":ontime,"late":late,"early":early,"terminal_backlog":unserved})
        write_json(dest / "headless_snapshot.json", snapshot)
        write_json(dest / "backward_results.json.gz", {p:public_result(r) for p,r in store["bres"].items()})
        write_json(dest / "forward_results.json.gz", {p:public_result(r) for p,r in store["fres"].items()})
        write_csv(dest / "nodes.csv", nodes, list(nodes[0]))
        write_csv(dest / "node_week.csv", weekly, list(weekly[0]))
        write_csv(dest / "stage_summary.csv", stage_counts, list(stage_counts[0]))
        write_csv(dest / "market_lot_status.csv.gz", market_rows, list(market_rows[0]))
        write_csv(dest / "market_summary.csv", market_summary, list(market_summary[0]))
        write_csv(dest / "deferral_ids.csv.gz", ({"product":p,"node_id":nid,"week":week,"lot_id":lot}
            for p,r in store["fres"].items() for nid,week,lot in getattr(r,"_trial_deferrals",[])),
            ["product","node_id","week","lot_id"])
        write_csv(dest / "actual_shipments.csv.gz", ({"product":p,"node_id":nd.node_id,"week":labels[w],
            "week_index":w,"sequence":i,"lot_id":lot} for p in tree.products for nd in tree.iter_all_nodes(p)
            for w,lots in nd._actual_ship.items() for i,lot in enumerate(lots)),
            ["product","node_id","week","week_index","sequence","lot_id"])
        write_csv(dest / "demand_positions.csv.gz", ({"product":p,"node_id":nd.node_id,"week":labels[w],
            "week_index":w,"sequence":i,"lot_id":lot} for p in tree.products for nd in tree.iter_all_nodes(p)
            for w in range(len(labels)) for i,lot in enumerate(nd.psi4demand[w][S])),
            ["product","node_id","week","week_index","sequence","lot_id"])
        write_json(dest / "summary.json", {"case":case,"products":global_summary,
            "total":{k:sum(r[k] for r in global_summary) for k in ["demand","on_time","late","early","terminal_backlog"]},
            "period":snapshot["period"],"last_week":labels[-1],"capacity_loads":store["capacity_loads"],
            "ppc":snapshot["ppc"]})
    after = {str(p.relative_to(model)): sha(p) for p in model.rglob("*") if p.is_file()}
    if before != after: raise AssertionError("Source model mutated")
    write_json(dest / "manifest.json", {"baseline_sha":BASE_SHA,"case":case,"model":str(model),
        "model_sha256":before,"core_changed":False,"model_unchanged":True,"lot_flow_mode":"identity",
        "schedule_dir":str(schedule_dir) if schedule_dir else None,
        "internal_positions_adapter":schedule_dir is not None,
        "elapsed_seconds":round(time.perf_counter()-t,3)})
    print("COMPLETED",case,round(time.perf_counter()-t,2),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-dir",type=Path,default=ORIGINAL)
    p.add_argument("--out",type=Path,required=True); p.add_argument("--case",required=True)
    p.add_argument("--schedule-dir",type=Path)
    a=p.parse_args(); measure(a.model_dir.resolve(),a.out.resolve(),a.case,a.schedule_dir.resolve() if a.schedule_dir else None)


if __name__=="__main__": main()
