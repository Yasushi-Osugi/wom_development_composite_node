# -*- coding: utf-8 -*-
"""
tools/lot_identity_checks.py — acceptance checks K1-K6 and difference metrics
for RequestLetter_LotIdentityFlow (read only; the plan is not changed).

    python -m tools.lot_identity_checks --out output/lot_identity \
        [--models all|<case>,<case>] [--modes identity,legacy]

For every model (13 golden + soysauce-jpy-2027-alloc P_opt/800 +
ev-thailand-2026_update) and every mode it runs the headless pipeline on a
COPY of the model folder and writes <out>/<mode>/<case>.json with

  K1 OutBound parent->child movement (arrival records captured around
     ForwardPlanner._propagate_to_child) + per parent/week conservation
     actual = arrivals + in-transit-at-end + unrouted
  K2 same Lot_ID in I and CO of one node/week (split: closed push week vs other)
     and "leaves both at once" when it later ships
  K3 Lot_IDs in the PSI that are no demand Lot_ID (rice harvest listed apart)
  K4 duplicate Lot_IDs in a CO cell; CO larger than the outstanding demand IDs
  K5 shipped Lot_ID not in the node's own S or CO of that week (push buffers
     and all OutBound nodes); push_sub counted separately
  K6 actual shipment in a week with processing_limit(w) == 0
  C6 InBound nodes on the demand-P copy path and the P Lot_IDs that no child
     shipped
  metrics: market leaf shipments, end-of-plan backlog, late shipments, PPC,
     runtime, SE2 / Cookie / soysauce-9,293 specifics
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict

S, CO, I, P = 0, 1, 2, 3
EXAMPLES = 5


def _jobs(repo):
    gdir = os.path.join(repo, "tests", "golden")
    jobs = []
    for fn in sorted(os.listdir(gdir)):
        if fn.endswith(".json"):
            g = json.load(open(os.path.join(gdir, fn), encoding="utf-8"))
            jobs.append((fn[:-5], ",".join(g["config"]["plugins"]) or "none", None))
    jobs.append(("soysauce-jpy-2027-alloc__P_opt800", "safe", "popt"))
    jobs.append(("ev-thailand-2026_update", "safe", None))
    return jobs


def run_case(repo, case, plugins, special, mode):
    import tools.run_headless_from_folder as rh
    import wom.engine.forward_planner as fpm
    store = {"arrivals": [], "fp": {}, "fres": {}}
    o_run, o_child, o_sig = fpm.ForwardPlanner.run, fpm.ForwardPlanner._propagate_to_child, rh._psi_signature

    def frun(self, prod):
        r = o_run(self, prod)
        store["fp"][prod] = copy.deepcopy(self._actual_s)
        store["fres"][prod] = r
        return r

    def child(self, parent, ch, n_weeks, *a, **k):
        before = [len(ch.psi4supply[w][P]) for w in range(n_weeks)]
        r = o_child(self, parent, ch, n_weeks, *a, **k)
        for w in range(n_weeks):
            tail = list(ch.psi4supply[w][P][before[w]:])
            if tail:
                store["arrivals"].append((parent.node_id, ch.node_id, w - ch.lt_wks, w, tail))
        return r

    def sig(t, n):
        store["tree"] = t
        return o_sig(t, n)

    fpm.ForwardPlanner.run, fpm.ForwardPlanner._propagate_to_child, rh._psi_signature = frun, child, sig
    tmp = tempfile.mkdtemp(prefix="lotid_")
    try:
        src = os.path.join(repo, "data", "sample", case.split("__")[0])
        mdir = os.path.join(tmp, os.path.basename(src))
        shutil.copytree(src, mdir)
        kw = {"lot_flow_mode": mode}
        if special == "popt":
            from tools.run_planning_loop import _scenario_blocks
            from wom.allocation.merit_order import true_continuous_optimum
            from wom.allocation.handoff import write_demand_for_allocation
            blocks, tp, sc = _scenario_blocks(mdir, "s1_base", None)
            to = true_continuous_optimum(blocks, sc, 800.0, transfer_price_usd=tp)
            h = write_demand_for_allocation(mdir, dict(to["x"]), "POPT", cap_wk=800.0, uom=None)
            kw["demand_file"] = os.path.basename(h["path"])
        t0 = time.perf_counter()
        snap = rh.run(mdir, plugins_spec=plugins, output_ppc_dir=os.path.join(tmp, "ppc"),
                      verbose=False, **kw)
        runtime = time.perf_counter() - t0
        return analyse(store, snap, runtime)
    finally:
        fpm.ForwardPlanner.run, fpm.ForwardPlanner._propagate_to_child, rh._psi_signature = o_run, o_child, o_sig
        shutil.rmtree(tmp, ignore_errors=True)


def _ex(lst, item):
    if len(lst) < EXAMPLES:
        lst.append(item)


def analyse(store, snap, runtime):
    t = store["tree"]
    n = t.num_weeks()
    wl = list(t.week_labels)
    out = {"runtime_s": round(runtime, 2), "ppc": snap["ppc"], "config": snap["config"],
           "forward": snap["forward"], "products": {}}
    by_id = {}
    for prod in t.products:
        for nd in t.iter_all_nodes(prod):
            by_id[nd.node_id] = nd
    actual_all = {}
    for prod, a in store["fp"].items():
        actual_all.update(a)

    def act(nid, w):
        return actual_all.get(nid, {}).get(w, [])

    # ---------------- K1 -------------------------------------------------
    k1 = {"arrivals": 0, "a_not_in_parent_actual": 0, "b_week_mismatch": 0,
          "c_duplicate_delivery": 0, "conservation_breaks": 0, "examples": []}
    delivered = defaultdict(Counter)       # (parent, ship_w) -> Counter(lot)
    for (pid, cid, ws, wa, lots) in store["arrivals"]:
        k1["arrivals"] += len(lots)
        child_nd = by_id[cid]
        if wa != ws + child_nd.lt_wks:
            k1["b_week_mismatch"] += len(lots)
            _ex(k1["examples"], {"b": [pid, cid, wl[ws] if 0 <= ws < n else ws, wl[wa]]})
        delivered[(pid, ws)].update(lots)
    for (pid, ws), cnt in delivered.items():
        ac = Counter(act(pid, ws))
        for lot, c in cnt.items():
            if lot not in ac:
                k1["a_not_in_parent_actual"] += c
                _ex(k1["examples"], {"a": [pid, wl[ws] if 0 <= ws < n else ws, lot]})
            elif c > ac[lot]:
                k1["c_duplicate_delivery"] += c - ac[lot]
                _ex(k1["examples"], {"c": [pid, wl[ws], lot, c, ac[lot]]})
    in_transit = defaultdict(int)
    unrouted = defaultdict(int)
    for prod, r in store["fres"].items():
        for pid, cid, wlab, c in getattr(r, "ot_in_transit_at_end", []):
            in_transit[(pid, wl.index(wlab))] += c
        for pid, wlab, c in getattr(r, "ot_unrouted", []):
            unrouted[(pid, wl.index(wlab))] += c
    k1["in_transit_at_end"] = sum(in_transit.values())
    k1["unrouted"] = sum(unrouted.values())
    for prod in t.products:
        for nd in t.get_ot_root(prod).walk_preorder():
            if not nd.children:
                continue
            for w in range(n):
                a_n = len(act(nd.node_id, w))
                d_n = sum(delivered.get((nd.node_id, w), Counter()).values())
                if a_n != d_n + in_transit.get((nd.node_id, w), 0) + unrouted.get((nd.node_id, w), 0):
                    k1["conservation_breaks"] += 1
                    _ex(k1["examples"], {"conservation": [nd.node_name, prod, wl[w], a_n, d_n,
                                                          in_transit.get((nd.node_id, w), 0)]})
    out["K1"] = k1

    # ---------------- K2 / K4 / K5 / K6 ----------------------------------
    k2 = {"overlap_closed_push": 0, "overlap_other": 0, "leave_one_side_only": 0,
          "examples_closed": [], "examples_other": [], "examples_leave": []}
    k4 = {"co_duplicate_occurrences": 0, "co_over_outstanding_cells": 0,
          "co_ids_not_outstanding": 0, "examples": []}
    k5 = {"early_shipments": 0, "push_sub_shipments_without_request": 0, "examples": []}
    k6 = {"shipments_in_closed_weeks": 0, "examples": []}
    for prod in t.products:
        ot_ids = {nd.node_id for nd in t.get_ot_root(prod).walk_preorder()}
        for nd in t.iter_all_nodes(prod):
            sup = nd.psi4supply
            is_push = nd.plan_mode == "push"
            shipped_cum = Counter()
            requested_cum = Counter()
            for w in range(n):
                a = act(nd.node_id, w)
                # K6
                lim = nd.processing_limit(w)
                if lim == 0 and a:
                    k6["shipments_in_closed_weeks"] += len(a)
                    _ex(k6["examples"], [nd.node_name, prod, wl[w], len(a)])
                # K2
                ov = set(sup[w][I]) & set(sup[w][CO])
                if ov:
                    closed_push = is_push and not nd.is_open(w)
                    key = "overlap_closed_push" if closed_push else "overlap_other"
                    k2[key] += len(ov)
                    _ex(k2["examples_closed" if closed_push else "examples_other"],
                        [nd.node_name, prod, wl[w], sorted(ov)[:3], len(ov)])
                    for lot in ov:
                        s = next((ww for ww in range(w + 1, n) if lot in act(nd.node_id, ww)), None)
                        if s is None:
                            continue
                        in_i = lot in sup[s][I]
                        in_co = (s + 1 < n) and lot in sup[s + 1][CO]
                        if in_i or in_co:
                            k2["leave_one_side_only"] += 1
                            _ex(k2["examples_leave"], [nd.node_name, prod, lot, wl[s], in_i, in_co])
                # K4
                co = Counter(sup[w][CO])
                dup = sum(c - 1 for c in co.values() if c > 1)
                outstanding = requested_cum - shipped_cum
                if dup:
                    k4["co_duplicate_occurrences"] += dup
                    _ex(k4["examples"], ["dup", nd.node_name, prod, wl[w], dup])
                n_out = sum(outstanding.values())
                if sum(co.values()) > n_out:
                    k4["co_over_outstanding_cells"] += 1
                    _ex(k4["examples"], ["over", nd.node_name, prod, wl[w], sum(co.values()), n_out])
                k4["co_ids_not_outstanding"] += sum(1 for lot in co if lot not in outstanding)
                # K5
                if nd.plan_mode == "push_sub":
                    req = set(sup[w][S]) | set(sup[w][CO])
                    k5["push_sub_shipments_without_request"] += sum(1 for lot in a if lot not in req)
                elif is_push or nd.node_id in ot_ids:
                    req = Counter(sup[w][S]) + Counter(sup[w][CO])
                    for lot in a:
                        if req[lot] <= 0:
                            k5["early_shipments"] += 1
                            _ex(k5["examples"], [nd.node_name, prod, wl[w], lot])
                        else:
                            req[lot] -= 1
                requested_cum.update(sup[w][S])
                shipped_cum.update(a)
    out["K2"], out["K4"], out["K5"], out["K6"] = k2, k4, k5, k6

    # ---------------- K3 ---------------------------------------------------
    demand_ids = set()
    for prod in t.products:
        for nd in t.get_ot_root(prod).walk_preorder():
            if not nd.children:
                for w in range(n):
                    demand_ids.update(nd.psi4demand[w][S])
    k3 = {"ids_without_demand": 0, "rice_harvest_like": 0, "examples": []}
    seen = set()
    for prod in t.products:
        for nd in t.iter_all_nodes(prod):
            for layer in (nd.psi4supply, nd.psi4demand):
                for w in range(n):
                    for b in (S, CO, I, P):
                        for lot in layer[w][b]:
                            if lot in demand_ids or lot in seen:
                                continue
                            seen.add(lot)
                            # Opening inventory of the former HarvestBatchPlugin
                            # (f"OI_{node_id}_{i}"). Nothing creates OI_ lots now
                            # (removed 2026-10-09); kept so old runs are still read.
                            if lot.startswith("OI_"):
                                k3["rice_harvest_like"] += 1
                            else:
                                k3["ids_without_demand"] += 1
                                _ex(k3["examples"], [nd.node_name, prod, wl[w], lot])
    out["K3"] = k3

    # ---------------- C6: InBound demand-P copy path ----------------------
    c6 = []
    for prod in t.products:
        for mom in t.get_in_roots(prod).values():
            in_pull = False
            for nd in mom.walk_postorder():
                if nd.node_type == "stockyard":
                    continue
                copies = ((nd.is_decoupling or in_pull) and nd.node_type != "leaf_in"
                          and nd.plan_mode != "push")
                if copies:
                    child_ship = set()
                    for ch in nd.children:
                        for w in range(n):
                            child_ship.update(act(ch.node_id, w))
                    p_ids = [lot for w in range(n) for lot in nd.psi4supply[w][P]]
                    missing = sum(1 for lot in p_ids if lot not in child_ship)
                    c6.append({"product": prod, "node": nd.node_name, "node_type": nd.node_type,
                               "is_decoupling": bool(nd.is_decoupling), "via_in_pull_mode": bool(in_pull),
                               "P_occurrences": len(p_ids), "P_ids_not_shipped_by_any_child": missing,
                               "n_children": len(nd.children)})
                if nd.is_decoupling and nd.plan_mode == "push":
                    pass
                elif nd.is_decoupling:
                    in_pull = True
    out["C6"] = c6

    # ---------------- market metrics ---------------------------------------
    mk = {"leaf_demand": 0, "leaf_actual": 0, "end_backlog": 0, "late_shipments": 0,
          "on_time_shipments": 0, "leaf_CO_last_week": 0}
    for prod in t.products:
        for nd in t.get_ot_root(prod).walk_preorder():
            if nd.children:
                continue
            sweek = {}
            dem = Counter()
            for w in range(n):
                for lot in nd.psi4supply[w][S]:
                    sweek.setdefault(lot, w)
                dem.update(nd.psi4supply[w][S])
            shipped = Counter()
            for w in range(n):
                for lot in act(nd.node_id, w):
                    shipped[lot] += 1
                    if w > sweek.get(lot, w):
                        mk["late_shipments"] += 1
                    else:
                        mk["on_time_shipments"] += 1
            mk["leaf_demand"] += sum(dem.values())
            mk["leaf_actual"] += sum(shipped.values())
            mk["end_backlog"] += sum((dem - shipped).values())
            mk["leaf_CO_last_week"] += len(nd.psi4supply[n - 1][CO])
    out["market"] = mk
    store["_tree"] = t
    store["_actual"] = actual_all
    return out, store


def specifics(case, store, mode):
    """SE2, Cookie SE1 and soysauce 9,293 details."""
    t, actual = store["_tree"], store["_actual"]
    n, wl = t.num_weeks(), list(t.week_labels)
    res = {}

    def node(prod, name):
        return next(x for x in t.iter_all_nodes(prod) if x.node_name == name)

    def tot(nd):
        return sum(len(v) for v in actual.get(nd.node_id, {}).values())

    if case == "ev-thailand-2026":
        nd = node("EVmaker_Import", "Factory_Import_CN")
        rows = []
        for lbl in ("2026-W36", "2026-W37", "2026-W38", "2026-W39", "2026-W40", "2026-W41", "2026-W42", "2026-W43"):
            w = wl.index(lbl)
            rows.append({"week": lbl, "S": len(nd.psi4supply[w][S]), "actual": len(actual[nd.node_id].get(w, [])),
                         "CO": len(nd.psi4supply[w][CO]), "I": len(nd.psi4supply[w][I]),
                         "P": len(nd.psi4supply[w][P]), "push_shortfall": nd._push_shortfall.get(w, 0),
                         "open": nd.is_open(w)})
        res["SE2_Factory_Import_CN"] = rows
        res["SE2_totals"] = {"actual": tot(nd), "S": sum(len(nd.psi4supply[w][S]) for w in range(n)),
                             "push_shortfall": sum(nd._push_shortfall.values())}
    if case == "Cookie-jp-2026":
        out = {}
        for name in ("Factory_GP_CN", "SP_Cookie_Import", "DC_Import_Buffer", "DC_Import_Main"):
            nd = node("Cookie_Import", name)
            out[name] = {"actual": tot(nd), "CO_last": len(nd.psi4supply[n - 1][CO])}
        leaves = [x for x in t.get_ot_root("Cookie_Import").walk_preorder() if not x.children]
        dem = sum(len(x.psi4supply[w][S]) for x in leaves for w in range(n))
        act_ = sum(tot(x) for x in leaves)
        out["market_leaves"] = {"demand": dem, "actual": act_, "unshipped_at_end": dem - act_}
        res["Cookie_Import"] = out
    if case == "soysauce-jpy-2027-alloc__P_opt800":
        bot = node("Soy_Sauce", "Bottling_Noda")
        bot_ids = set(l for v in actual.get(bot.node_id, {}).values() for l in v)
        leaves = [x for x in t.get_ot_root("Soy_Sauce").walk_preorder() if not x.children]
        leaf_dem = {}
        for x in leaves:
            for w in range(n):
                for lot in x.psi4supply[w][S]:
                    leaf_dem.setdefault(lot, (x, w))
        ids = sorted(l for l in leaf_dem if l not in bot_ids)
        on_time = late = backlog = 0
        for lot in ids:
            x, sw = leaf_dem[lot]
            s = next((w for w, v in actual.get(x.node_id, {}).items() if lot in v), None)
            if s is None:
                backlog += 1
            elif s > sw:
                late += 1
            else:
                on_time += 1
        res["soysauce_ids_not_shipped_by_Bottling"] = {
            "count": len(ids), "market_on_time": on_time, "market_late": late,
            "market_backlog_at_end": backlog, "Bottling_actual_total": tot(bot)}
        res["_ids_not_shipped_by_Bottling"] = ids
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", default="all")
    ap.add_argument("--modes", default="identity,legacy")
    a = ap.parse_args(argv)
    repo = os.getcwd()
    jobs = _jobs(repo)
    if a.models != "all":
        want = set(a.models.split(","))
        jobs = [j for j in jobs if j[0] in want]
    for mode in a.modes.split(","):
        od = os.path.join(a.out, mode)
        os.makedirs(od, exist_ok=True)
        for case, plugins, special in jobs:
            res, store = run_case(repo, case, plugins, special, mode)
            res["specifics"] = specifics(case, store, mode)
            res["case"], res["mode"] = case, mode
            with open(os.path.join(od, case + ".json"), "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=1, default=str)
            k = {kk: {x: y for x, y in res[kk].items() if not str(x).startswith("examples")}
                 for kk in ("K1", "K2", "K4", "K5", "K6")}
            print(f"[{mode}] {case} runtime={res['runtime_s']}s K={json.dumps(k, ensure_ascii=False)} "
                  f"K3={res['K3']['ids_without_demand']}/{res['K3']['rice_harvest_like']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
