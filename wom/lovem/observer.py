# -*- coding: utf-8 -*-
"""
wom/lovem/observer.py — stage A observation adapter (design §8, request §4).

observe_run() runs the SAME orchestration as tools/run_headless_from_folder.run()
(it calls that function) while a set of read-only wrappers is installed on
planner call boundaries. The wrappers copy what they need and never sort,
remove, reassign or mutate any PSI list; all of them are removed when the run
ends (also on error). No protected core file is modified.

Capture points (design §8.3):
  1 anchor            assign_demand_lots_from_dict()        -> demand_anchors.jsonl
  2 pre_backward      BackwardPlanner.run() entry  (demand)  -> psi_intervals / state_digests
    post_backward     BackwardPlanner.run() exit   (demand)  + past_due events
    post_backward_hooks  HookBus.fire(post_backward) exit (demand)
  3 post_copy         copy_demand_to_supply() exit (supply)
  4 post_push_setup   PushProductionPlanner.setup_all() exit (supply) + Mode 4 diagnostics
  5 forward events    ForwardPlanner._propagate_to_parent / _propagate_to_child
                      (arrivals), _run_ot_push_pull entry (bridge receipts),
                      ForwardPlanner.run exit (_actual_s shipments, result records,
                      _push_shortfall)
  6 final             _psi_signature() entry (demand + supply) + capacity.csv
  7 PPC               not captured (stage D)
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Dict, List, Optional

from wom.lovem import OBSERVER_VERSION, SCHEMA_VERSION
from wom.lovem.digest import (QTY_PER_OCCURRENCE, ROLE_NONE, UNIT_LOT,
                              multiset_sha256, ordered_sha256, payload_sha256)
from wom.lovem.intervals import encode_series, expanded_occurrences

BUCKETS = (("S", 0), ("CO", 1), ("I", 2), ("P", 3))   # plan_node: S=0, CO=1, I=2, P=3
GOLDEN_PLUGINS = "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"


class _JsonlWriter:
    """UTF-8 JSON Lines writer; *.gz paths are gzip-compressed (level 6)."""

    def __init__(self, path: str, id_field: Optional[str] = None, prefix: str = "",
                 start: int = 0):
        self.path = path
        if path.endswith(".gz"):
            import gzip
            import io
            # mtime=0 and no file name in the header -> byte-identical output
            # for identical content (reproducible run folders).
            self._raw = open(path, "wb")
            gz = gzip.GzipFile(filename="", mode="wb", fileobj=self._raw,
                               compresslevel=6, mtime=0)
            self.f = io.TextIOWrapper(gz, encoding="utf-8", newline="\n")
        else:
            self.f = open(path, "w", encoding="utf-8", newline="\n")
        self.id_field, self.prefix, self.n = id_field, prefix, start

    def write(self, rec: dict) -> str:
        rid = None
        if self.id_field:
            rid = rec.get(self.id_field) or f"{self.prefix}{self.n:08d}"
            rec = {self.id_field: rid, **{k: v for k, v in rec.items() if k != self.id_field}}
        self.f.write(json.dumps(rec, ensure_ascii=False, sort_keys=False) + "\n")
        self.n += 1
        return rid

    def close(self):
        self.f.close()
        raw = getattr(self, "_raw", None)
        if raw is not None and not raw.closed:
            raw.close()


class Observer:
    """Collects observations of one run into out_dir (stream writers)."""

    def __init__(self, out_dir: str, run_id: str):
        os.makedirs(out_dir, exist_ok=True)
        self.out_dir, self.run_id = out_dir, run_id
        self.sc_tree = None
        self.n_weeks = 0
        # psi_intervals: one gzip JSONL file per snapshot (psi_intervals/<product>__<phase>.jsonl.gz)
        # so that a reader (viewer) can load one snapshot without parsing the others.
        # interval_id is unique across all files of the run (one running counter).
        os.makedirs(os.path.join(out_dir, "psi_intervals"), exist_ok=True)
        self._iv_counter = 0
        self.w_digests = _JsonlWriter(os.path.join(out_dir, "state_digests.jsonl"))
        self.w_events = _JsonlWriter(os.path.join(out_dir, "events.jsonl.gz"), "event_id", "ev")
        self.w_relations = _JsonlWriter(os.path.join(out_dir, "relations.jsonl.gz"), "relation_id", "rel")
        self.w_evidence = _JsonlWriter(os.path.join(out_dir, "source_evidence.jsonl.gz"), "evidence_id", "src")
        self.w_anchors = _JsonlWriter(os.path.join(out_dir, "demand_anchors.jsonl.gz"))
        self.phases: List[dict] = []                  # snapshot log
        self.counts = defaultdict(int)
        self.expanded = defaultdict(int)              # snapshot_id -> expanded occurrences
        self.coverage_notes: List[dict] = []
        self.arrival_log: Dict[str, list] = defaultdict(list)   # product -> [(to_id, w, lots, from_id, ship_w, seqs, via)]
        self.bridge_log: Dict[str, list] = {}
        self.forward_done: Dict[str, dict] = {}
        self.push_results: Dict[str, object] = {}
        self.timing: Dict[str, float] = defaultdict(float)
        self._product_of_node: Dict[str, str] = {}

    # ------------------------------------------------------------------
    def evidence(self, source_kind: str, locator: str, payload) -> str:
        return self.w_evidence.write({
            "evidence_id": None, "source_kind": source_kind, "source_locator": locator,
            "source_hash": payload_sha256(payload), "payload": payload})

    def event(self, **kw) -> str:
        base = {"event_id": kw.pop("event_id", None), "event_type": None, "product_id": None,
                "node_id": None, "week_index": None, "sequence": "unknown", "lot_id": None,
                "role_id": ROLE_NONE, "quantity": None, "unit": UNIT_LOT, "origin": None,
                "evidence_level": "observed", "evidence_ref": None}
        base.update(kw)
        self.counts["events"] += 1
        return self.w_events.write(base)

    def relation(self, **kw) -> str:
        base = {"relation_id": None, "relation_type": None, "from_ref": None, "to_ref": None,
                "demand_key": None, "quantity": QTY_PER_OCCURRENCE, "evidence_level": "derived",
                "method": None, "evidence_ref": None}
        base.update(kw)
        self.counts["relations"] += 1
        return self.w_relations.write(base)

    # ------------------------------------------------------------------
    def capture(self, phase: str, prod: str, layers: List[str]) -> None:
        """Snapshot every node of `prod` for `layers` (read-only list copies)."""
        t0 = time.perf_counter()
        snapshot_id = f"{prod}/{phase}"
        n = self.n_weeks
        fname = f"{_safe(prod)}__{phase}.jsonl.gz"
        w_iv = _JsonlWriter(os.path.join(self.out_dir, "psi_intervals", fname),
                            "interval_id", "iv", start=self._iv_counter)
        self.w_intervals = w_iv
        for nd in self.sc_tree.iter_all_nodes(prod):
            for layer in layers:
                psi = nd.psi4demand if layer == "demand" else nd.psi4supply
                for bname, bidx in BUCKETS:
                    weekly = [list(psi[w][bidx]) for w in range(n)]
                    for w, lots in enumerate(weekly):
                        self.w_digests.write({
                            "run_id": self.run_id, "snapshot_id": snapshot_id, "phase": phase,
                            "product_id": prod, "node_id": nd.node_id, "week_index": w,
                            "layer": layer, "bucket": bname, "entry_count": len(lots),
                            "total_quantity": len(lots) * QTY_PER_OCCURRENCE,
                            "multiset_sha256": multiset_sha256(lots),
                            "ordered_sha256": ordered_sha256(lots)})
                    self.counts["digests"] += n
                    base = {"run_id": self.run_id, "snapshot_id": snapshot_id, "phase": phase,
                            "product_id": prod, "node_id": nd.node_id, "layer": layer,
                            "evidence_level": "observed", "evidence_ref": f"snapshot:{snapshot_id}"}
                    recs = encode_series(weekly, bucket=bname, base=base)
                    for r in recs:
                        self.w_intervals.write({"interval_id": None, **r})
                    self.counts["intervals"] += len(recs)
                    self.expanded[f"{snapshot_id}|{layer}|{bname}"] += expanded_occurrences(recs)
        n_iv = w_iv.n - self._iv_counter
        self._iv_counter = w_iv.n
        w_iv.close()
        self.phases.append({"snapshot_id": snapshot_id, "phase": phase, "product_id": prod,
                            "layers": layers, "weeks": [0, n - 1] if n else None,
                            "complete": True, "intervals_file": f"psi_intervals/{fname}",
                            "n_intervals": n_iv})
        self.timing["capture_s"] += time.perf_counter() - t0

    # ------------------------------------------------------------------
    def on_assign(self, sc_tree) -> None:
        self.sc_tree = sc_tree
        self.n_weeks = sc_tree.num_weeks()
        for prod in sc_tree.products:
            for nd in sc_tree.iter_all_nodes(prod):
                self._product_of_node[nd.node_id] = prod
            ot = sc_tree.get_ot_root(prod)
            for nd in ot.walk_preorder():
                if nd.children:
                    continue
                for w in range(self.n_weeks):
                    occ = defaultdict(int)
                    for lot in list(nd.psi4demand[w][0]):
                        occ[lot] += 1
                        self.w_anchors.write({
                            "run_id": self.run_id,
                            "demand_key": f"{prod}|{nd.node_id}|{w}|{lot}|{occ[lot]}",
                            "lot_id": lot, "product_id": prod, "market_node_id": nd.node_id,
                            "required_week": w,
                            "required_week_label": sc_tree.week_labels[w],
                            "occurrence": occ[lot], "quantity": QTY_PER_OCCURRENCE,
                            "unit": UNIT_LOT, "allocation_id": None,
                            "evidence_level": "observed",
                            "evidence_ref": "assign_demand_lots_from_dict"})
                        self.counts["anchors"] += 1

    def on_backward_result(self, prod, res) -> None:
        pd_ = list(getattr(res, "past_due_lots", []) or [])
        ref = self.evidence("backward_result", f"{prod}",
                            {"past_due_lots": [list(x) for x in pd_]})
        for node_id, lot, w in pd_:
            self.event(event_type="backward_past_due", product_id=prod, node_id=node_id,
                       week_index=w, lot_id=lot, quantity=QTY_PER_OCCURRENCE,
                       origin="BackwardPlanResult.past_due_lots", evidence_ref=ref)

    def on_push_setup(self, results) -> None:
        for prod, r in results.items():
            self.push_results[prod] = r
            payload = {"mode": getattr(r, "mode", None),
                       "push_lots_total": getattr(r, "push_lots_total", None),
                       "push_events": [list(x) for x in getattr(r, "push_events", [])],
                       "mode4_closure_shifted": [list(x) for x in getattr(r, "mode4_closure_shifted", [])]}
            ref = self.evidence("push_setup_result", prod, payload)
            for node_id, wl, dst, cnt in getattr(r, "mode4_closure_shifted", []):
                self.event(event_type="mode4_closure_shifted", product_id=prod, node_id=node_id,
                           week_index=self._widx(wl), quantity=cnt,
                           origin="PushSetupResult.mode4_closure_shifted", evidence_ref=ref,
                           detail={"to_week_index": self._widx(dst) if dst else None})

    def _widx(self, label):
        try:
            return list(self.sc_tree.week_labels).index(label)
        except ValueError:
            return None

    # -- forward ---------------------------------------------------------
    def on_propagate(self, fp, via, from_node, to_node, before_len, lt, n_weeks) -> None:
        prod = self._product_of_node.get(to_node.node_id)
        actual = fp._actual_s.get(from_node.node_id, {})
        for w in range(n_weeks):
            tail = list(to_node.psi4supply[w][3][before_len[w]:])
            if tail:
                self.arrival_log[prod].append((to_node.node_id, w, tail, from_node.node_id,
                                               w - lt, list(actual.get(w - lt, [])), via))
        for w, lots in actual.items():
            if lots and w + lt >= n_weeks:
                routed = list(lots)
                if via.endswith("_propagate_to_child") and len(from_node.children) > 1:
                    routed = [lot for lot in lots
                              if _routes_to(fp._lot_leaf_index.get(lot), from_node, to_node)]
                if routed:
                    self.arrival_log[prod].append((None, w + lt, routed, from_node.node_id,
                                                   w, list(lots), via + ":beyond_horizon"))

    def on_bridge(self, fp, ot_root, n_weeks) -> None:
        prod = self._product_of_node.get(ot_root.node_id)
        in_roots = list(self.sc_tree.get_in_roots(prod).values())
        rows = []
        for w in range(n_weeks):
            p = list(ot_root.psi4supply[w][3])
            if p:
                srcs = []
                for mom in in_roots:
                    srcs.append((mom.node_id, list(fp._actual_s.get(mom.node_id, {}).get(w, []))))
                rows.append((w, p, srcs))
        self.bridge_log[prod] = (ot_root.node_id, rows)

    def on_forward_done(self, fp, prod, res) -> None:
        t0 = time.perf_counter()
        actual = {nid: {w: list(v) for w, v in byw.items()} for nid, byw in fp._actual_s.items()}
        ship_ids = {}
        for nid in sorted(actual):
            for w in sorted(actual[nid]):
                lots = actual[nid][w]
                if not lots:
                    continue
                ref = self.evidence("forward_actual_s", f"{prod}/{nid}/{w}", lots)
                for seq, lot in enumerate(lots):
                    eid = f"ship:{prod}:{nid}:{w}:{seq}"
                    self.event(event_id=eid, event_type="actual_ship", product_id=prod, node_id=nid,
                               week_index=w, sequence=seq, lot_id=lot, quantity=QTY_PER_OCCURRENCE,
                               origin="ForwardPlanner._actual_s", evidence_ref=ref)
                    ship_ids[(nid, w, seq)] = eid
        # arrivals (from propagation calls) + ship->arrival relations
        for (to_id, w, tail, from_id, ship_w, shipped, via) in self.arrival_log.get(prod, []):
            if to_id is None:       # shipped, arrival week beyond horizon: not added to any P
                ref = self.evidence("forward_ship_beyond_horizon", f"{prod}/{from_id}/{ship_w}",
                                    {"lots": tail, "arrival_week_index": w, "via": via})
                for seq, lot in enumerate(tail):
                    self.event(event_type="arrival_beyond_horizon", product_id=prod, node_id=from_id,
                               week_index=ship_w, sequence=seq, lot_id=lot,
                               quantity=QTY_PER_OCCURRENCE, origin=via, evidence_level="derived",
                               evidence_ref=ref, detail={"arrival_week_index": w})
                continue
            ref = self.evidence("forward_propagation_append", f"{prod}/{from_id}->{to_id}/{w}",
                                {"from_node_id": from_id, "to_node_id": to_id,
                                 "arrival_week_index": w, "ship_week_index": ship_w,
                                 "lots": tail, "via": via})
            seqs = _subsequence_positions(shipped, tail)
            for k, lot in enumerate(tail):
                aid = self.event(event_type="arrival", product_id=prod, node_id=to_id, week_index=w,
                                 sequence=k, lot_id=lot, quantity=QTY_PER_OCCURRENCE,
                                 origin=via, evidence_ref=ref,
                                 detail={"from_node_id": from_id, "ship_week_index": ship_w})
                sid = ship_ids.get((from_id, ship_w, seqs[k])) if seqs[k] is not None else None
                if sid:
                    self.relation(relation_type="ship_to_arrival", from_ref=sid, to_ref=aid,
                                  method=f"{via}: arrival week = ship week + LT; tail of the "
                                         f"propagation call matched as an ordered subsequence of "
                                         f"the sender's _actual_s list", evidence_ref=ref)
                else:
                    self.counts["arrival_unlinked"] += 1
        # bridge (Phase 2): SP receipts = concat of MOM roots' actual shipments of the same week
        if prod in self.bridge_log:
            sp_id, rows = self.bridge_log[prod]
            for w, p, srcs in rows:
                ref = self.evidence("forward_bridge_p", f"{prod}/{sp_id}/{w}",
                                    {"lots": p, "sources": [[s, l] for s, l in srcs]})
                flat = [(s, i, lot) for s, l in srcs for i, lot in enumerate(l)]
                for k, lot in enumerate(p):
                    aid = self.event(event_type="bridge_arrival", product_id=prod, node_id=sp_id,
                                     week_index=w, sequence=k, lot_id=lot,
                                     quantity=QTY_PER_OCCURRENCE,
                                     origin="ForwardPlanner.run Phase 2 bridge", evidence_ref=ref)
                    if k < len(flat) and flat[k][2] == lot:
                        sid = ship_ids.get((flat[k][0], w, flat[k][1]))
                        if sid:
                            self.relation(relation_type="ship_to_bridge", from_ref=sid, to_ref=aid,
                                          method="Phase 2: supply_point P[w] = concat(MOM roots "
                                                 "_actual_s[w]) in in_roots order", evidence_ref=ref)
                            continue
                    self.counts["arrival_unlinked"] += 1
        # result records
        def lst(name):
            return [list(x) if isinstance(x, tuple) else x for x in getattr(res, name, []) or []]
        payload = {k: lst(k) for k in ("shortfall_weeks", "cap_hard_events", "cap_soft_violations",
                                       "kitting_capacity_deferred", "kitting_fallback_events",
                                       "closure_p_deferred", "closure_p_unplaced",
                                       "closure_s_planned")}
        # RequestLetter_FlowCheck Part 2: legacy seals the lots over cap_hard
        # (into CO); identity defers them to the next week's P (Decision Record
        # D4) -- recorded under their own names, never as "sealed".
        if getattr(res, "lot_flow_mode", None) == "identity":
            payload["cap_hard_deferred_lots"] = getattr(res, "cap_hard_deferred_lots", None)
            payload["cap_hard_deferred_lot_weeks"] = getattr(res, "cap_hard_deferred_lot_weeks", None)
        else:
            payload["cap_hard_sealed"] = getattr(res, "cap_hard_sealed", None)
        payload["co_generated"] = getattr(res, "co_generated", None)
        # RequestLetter_LotIdentityFlow C3 / Addendum1 A1・A2 (D4/D5): the mode that
        # produced the plan, and the lots recorded instead of being dropped.
        payload["lot_flow_mode"] = getattr(res, "lot_flow_mode", None)
        for k in ("ot_in_transit_at_end", "ot_unrouted", "cap_hard_unplaced"):
            payload[k] = lst(k)
        rref = self.evidence("forward_result", prod, payload)
        for kind in ("shortfall_weeks", "cap_hard_events", "cap_soft_violations",
                     "closure_p_deferred", "closure_s_planned", "kitting_capacity_deferred"):
            for rec in payload[kind]:
                nid, wl, val = rec[0], rec[1], rec[2]
                self.event(event_type=f"forward_{kind}", product_id=prod, node_id=nid,
                           week_index=self._widx(wl), quantity=val, lot_id=None,
                           origin=f"ForwardPlanResult.{kind}", evidence_ref=rref)
        for nid, wl, lots in payload["closure_p_unplaced"]:
            for seq, lot in enumerate(lots):
                self.event(event_type="forward_closure_p_unplaced", product_id=prod, node_id=nid,
                           week_index=self._widx(wl), sequence=seq, lot_id=lot,
                           quantity=QTY_PER_OCCURRENCE, origin="ForwardPlanResult.closure_p_unplaced",
                           evidence_ref=rref)
        # push shortfall (count per week; lot identity not recorded by the engine)
        for nd in self.sc_tree.iter_all_nodes(prod):
            sf = getattr(nd, "_push_shortfall", None)
            if sf:
                nz = {int(w): int(v) for w, v in sf.items() if v}
                sref = self.evidence("push_shortfall", f"{prod}/{nd.node_id}",
                                     {str(w): v for w, v in sorted(nz.items())})
                for w, v in sorted(nz.items()):
                    self.event(event_type="push_shortfall", product_id=prod, node_id=nd.node_id,
                               week_index=w, quantity=v, lot_id=None,
                               origin="PlanNode._push_shortfall", evidence_ref=sref)
        self.forward_done[prod] = {"actual": actual}
        self.timing["forward_events_s"] += time.perf_counter() - t0

    def close(self):
        for w in (self.w_digests, self.w_events, self.w_relations,
                  self.w_evidence, self.w_anchors):
            w.close()


def _safe(s: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in s)


def _routes_to(leaf, parent, child) -> bool:
    """Same routing rule as ForwardPlanner._propagate_to_child (multi-child)."""
    node = leaf
    while node is not None and node.parent is not parent:
        node = node.parent
    return node is child


def _subsequence_positions(seq: List[str], sub: List[str]) -> List[Optional[int]]:
    """Positions of `sub` as an ordered subsequence of `seq` (greedy)."""
    out, j = [], 0
    for x in sub:
        while j < len(seq) and seq[j] != x:
            j += 1
        if j < len(seq):
            out.append(j)
            j += 1
        else:
            out.append(None)
    return out


# ----------------------------------------------------------------------
# Wrapper installation (read-only; always restored)
# ----------------------------------------------------------------------

@contextmanager
def installed(obs: Observer):
    import wom.model.lot_generator as lg
    import wom.engine.plan_copy as pc
    import wom.engine.backward_planner as bp
    import wom.engine.forward_planner as fpm
    import wom.engine.push_pull as ppm
    import wom.engine.hook_bus as hb
    import tools.run_headless_from_folder as rh

    saved = []

    def patch(owner, name, new):
        saved.append((owner, name, getattr(owner, name)))
        setattr(owner, name, new)

    o_assign = lg.assign_demand_lots_from_dict

    def assign(sc_tree, *a, **k):
        r = o_assign(sc_tree, *a, **k)
        obs.on_assign(sc_tree)
        return r
    patch(lg, "assign_demand_lots_from_dict", assign)

    o_brun = bp.BackwardPlanner.run

    def brun(self, prod_nm):
        obs.capture("pre_backward", prod_nm, ["demand"])
        res = o_brun(self, prod_nm)
        obs.capture("post_backward", prod_nm, ["demand"])
        obs.on_backward_result(prod_nm, res)
        return res
    patch(bp.BackwardPlanner, "run", brun)

    o_fire = hb.HookBus.fire

    def fire(self, hook, **ctx):
        o_fire(self, hook, **ctx)
        if hook == hb.HOOK_POST_BACKWARD and ctx.get("prod_nm"):
            obs.capture("post_backward_hooks", ctx["prod_nm"], ["demand"])
    patch(hb.HookBus, "fire", fire)

    o_copy = pc.copy_demand_to_supply

    def copy(sc_tree, prod_nm, *a, **k):
        r = o_copy(sc_tree, prod_nm, *a, **k)
        obs.capture("post_copy", prod_nm, ["supply"])
        return r
    patch(pc, "copy_demand_to_supply", copy)

    o_setup = ppm.PushProductionPlanner.setup_all

    def setup_all(self, cfgs):
        r = o_setup(self, cfgs)
        for prod in cfgs:
            obs.capture("post_push_setup", prod, ["supply"])
        obs.on_push_setup(r)
        return r
    patch(ppm.PushProductionPlanner, "setup_all", setup_all)

    o_par = fpm.ForwardPlanner._propagate_to_parent

    def to_parent(self, node, n_weeks, result=None):
        parent = node.parent
        before = [len(parent.psi4supply[w][3]) for w in range(n_weeks)] if parent is not None else None
        r = o_par(self, node, n_weeks, result)
        if parent is not None:
            lt = node.transit_lt_wks if node.transit_lt_wks > 0 else node.lt_wks
            obs.on_propagate(self, "ForwardPlanner._propagate_to_parent", node, parent, before, lt, n_weeks)
        return r
    patch(fpm.ForwardPlanner, "_propagate_to_parent", to_parent)

    o_child = fpm.ForwardPlanner._propagate_to_child

    def to_child(self, parent, child, n_weeks, *args, **kwargs):
        # *args/**kwargs: ForwardPlanner._propagate_to_child gained an optional
        # `result` argument (RequestLetter_LotIdentityFlow C3); pass it through.
        before = [len(child.psi4supply[w][3]) for w in range(n_weeks)]
        r = o_child(self, parent, child, n_weeks, *args, **kwargs)
        obs.on_propagate(self, "ForwardPlanner._propagate_to_child", parent, child, before,
                         child.lt_wks, n_weeks)
        return r
    patch(fpm.ForwardPlanner, "_propagate_to_child", to_child)

    o_ot = fpm.ForwardPlanner._run_ot_push_pull

    def run_ot(self, ot_root, decouple_ids, n_weeks, result):
        obs.on_bridge(self, ot_root, n_weeks)
        return o_ot(self, ot_root, decouple_ids, n_weeks, result)
    patch(fpm.ForwardPlanner, "_run_ot_push_pull", run_ot)

    o_frun = fpm.ForwardPlanner.run

    def frun(self, prod_nm):
        res = o_frun(self, prod_nm)
        obs.on_forward_done(self, prod_nm, res)
        return res
    patch(fpm.ForwardPlanner, "run", frun)

    o_sig = rh._psi_signature

    def sig(sc_tree, n_weeks):
        for prod in sc_tree.products:
            obs.capture("final", prod, ["demand", "supply"])
        return o_sig(sc_tree, n_weeks)
    patch(rh, "_psi_signature", sig)

    try:
        yield
    finally:
        for owner, name, orig in reversed(saved):
            setattr(owner, name, orig)


# ----------------------------------------------------------------------
# Run-level files
# ----------------------------------------------------------------------

def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_hashes(model_dir: str) -> Dict[str, str]:
    return {fn: _sha256_file(os.path.join(model_dir, fn))
            for fn in sorted(os.listdir(model_dir))
            if os.path.isfile(os.path.join(model_dir, fn))}


def git_state(repo: str) -> dict:
    def g(*args):
        return subprocess.run(["git", *args], cwd=repo, capture_output=True).stdout
    sha = g("rev-parse", "HEAD").decode().strip()
    diff = g("diff", "HEAD", "--binary", "--", "wom", "tools", "data")
    untracked = [p for p in g("ls-files", "--others", "--exclude-standard", "--",
                              "wom", "tools", "data").decode("utf-8").splitlines() if p]
    h = hashlib.sha256(diff)
    for p in sorted(untracked):
        h.update(p.encode("utf-8"))
        fp = os.path.join(repo, p)
        if os.path.isfile(fp):
            h.update(bytes.fromhex(_sha256_file(fp)))
    return {"code_sha": sha, "dirty": bool(diff) or bool(untracked),
            "dirty_diff_hash": h.hexdigest(), "dirty_scope": ["wom", "tools", "data"],
            "untracked_in_scope": sorted(untracked)}


def write_nodes_weeks_capacity(obs: Observer, model_dir: str) -> dict:
    t = obs.sc_tree
    order = 0
    with open(os.path.join(obs.out_dir, "nodes.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["product_id", "node_id", "node_name", "parent_id", "tree_side",
                     "display_order", "display_group", "node_type", "plan_mode",
                     "is_decoupling", "lt_wks", "transit_lt_wks", "supply_role"])
        for prod in t.products:
            seq = [("outbound_postorder", nd) for nd in t.get_ot_root(prod).walk_postorder()]
            for mom in t.get_in_roots(prod).values():
                seq += [("inbound_preorder", nd) for nd in mom.walk_preorder()]
            for grp, nd in seq:
                wr.writerow([prod, nd.node_id, nd.node_name,
                             nd.parent.node_id if nd.parent is not None else "",
                             nd.side, order, grp, nd.node_type, nd.plan_mode,
                             int(bool(nd.is_decoupling)), nd.lt_wks,
                             getattr(nd, "transit_lt_wks", ""), getattr(nd, "supply_role", "") or ""])
                order += 1
    # weeks
    labels = list(t.week_labels)
    starts = []
    for lbl in labels:
        y, w = lbl.split("-W")
        starts.append(datetime.date.fromisocalendar(int(y), int(w), 1))
    first_dem = _first_nonzero_demand_week(model_dir)
    gaps = [i for i in range(1, len(starts)) if (starts[i] - starts[i - 1]).days != 7]
    with open(os.path.join(obs.out_dir, "weeks.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["week_index", "engine_week_label", "iso_week_start", "period_role"])
        for i, (lbl, d) in enumerate(zip(labels, starts)):
            role = "warmup" if (first_dem and lbl < first_dem) else "plan"
            wr.writerow([i, lbl, d.isoformat(), role])
    # capacity (final state)
    with open(os.path.join(obs.out_dir, "capacity.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["product_id", "node_id", "week_index", "raw_hard", "raw_soft",
                     "effective_limit", "planned_capacity", "is_open", "op_shifts", "source_ref"])
        for prod in t.products:
            for nd in t.iter_all_nodes(prod):
                for w in range(obs.n_weeks):
                    lim, pc = nd.processing_limit(w), nd.planned_capacity(w)
                    sh = nd.operating_shifts(w)
                    wr.writerow([prod, nd.node_id, w, nd.cap_hard(w), nd.cap_soft(w),
                                 "" if lim is None else lim, "" if pc is None else pc,
                                 int(nd.is_open(w)), "" if sh is None else sh,
                                 "final_state"])
    return {"weeks": len(labels), "first_week": labels[0] if labels else None,
            "last_week": labels[-1] if labels else None,
            "w53_weeks": [l for l in labels if l.endswith("-W53")],
            "non_7day_steps_at_index": gaps, "first_nonzero_demand_week": first_dem}


def _first_nonzero_demand_week(model_dir, demand_file="demand_forecast.csv"):
    p = os.path.join(model_dir, demand_file)
    if not os.path.exists(p):
        return None
    best = None
    with open(p, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                if float(r.get("quantity") or 0) > 0:
                    wk = r["week"].strip()
                    best = wk if best is None or wk < best else best
            except ValueError:
                continue
    return best


def observe_run(model_dir: str, out_dir: str, *, plugins: str = GOLDEN_PLUGINS,
                repo: Optional[str] = None, label: str = "obs", copy_model: bool = True,
                lot_flow_mode: Optional[str] = None) -> dict:
    """Run the headless pipeline on `model_dir` with observation ON and write
    the run folder `out_dir`. Returns the headless snapshot (unchanged).

    lot_flow_mode: passed to the headless runner (None -> planning_config.csv,
    else the ForwardPlanner default "identity"); the resolved value is recorded
    in manifest.json."""
    from tools.run_headless_from_folder import run as run_headless
    from wom.engine.forward_planner import resolve_lot_flow_mode
    from wom.engine.warmup import read_lot_flow_mode
    lot_flow_mode = resolve_lot_flow_mode(lot_flow_mode or read_lot_flow_mode(model_dir))
    repo = repo or os.getcwd()
    case = os.path.basename(os.path.abspath(model_dir).rstrip("/\\"))
    gs = git_state(repo)
    run_id = f"{case}@{gs['code_sha'][:7]}{'+dirty' if gs['dirty'] else ''}:{label}"
    src_hashes = model_hashes(model_dir)

    tmp = None
    work = model_dir
    if copy_model:
        tmp = tempfile.mkdtemp(prefix="lovem_")
        work = os.path.join(tmp, case)
        shutil.copytree(model_dir, work)

    os.makedirs(out_dir, exist_ok=True)
    obs = Observer(out_dir, run_id)
    t0 = time.perf_counter()
    try:
        with installed(obs):
            snap = run_headless(work, plugins_spec=plugins,
                                output_ppc_dir=os.path.join(out_dir, "ppc"), verbose=False,
                                lot_flow_mode=lot_flow_mode)
    finally:
        obs.close()
    t_run = time.perf_counter() - t0
    wk = write_nodes_weeks_capacity(obs, work)
    after_hashes = model_hashes(model_dir)
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)

    with open(os.path.join(out_dir, "headless_snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2, sort_keys=True)

    has_yard = any(nd.node_type == "stockyard" for p in obs.sc_tree.products
                   for nd in obs.sc_tree.iter_all_nodes(p))
    manifest = {
        "schema_version": SCHEMA_VERSION, "observer_version": OBSERVER_VERSION,
        "run_id": run_id, "case": case, "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        **gs,
        "model_dir": os.path.relpath(os.path.abspath(model_dir), repo).replace("\\", "/"),
        "model_hashes": src_hashes, "model_unchanged_by_run": src_hashes == after_hashes,
        "environment": _environment(),
        "plugins": sorted(p for p in plugins.split(",") if p),
        "lot_flow_mode": lot_flow_mode,
        "products": list(obs.sc_tree.products),
        "weeks": wk,
        "snapshots": obs.phases,
        "counts": {**dict(obs.counts),
                   "expanded_occurrences_by_snapshot": dict(obs.expanded)},
        "timing_s": {"run_total": round(t_run, 3),
                     **{k: round(v, 3) for k, v in obs.timing.items()}},
        "coverage": _coverage(obs, has_yard, lot_flow_mode),
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return snap


def _environment():
    import numpy, pandas, matplotlib
    return {"python": sys.version.split()[0], "platform": platform.platform(),
            "numpy": numpy.__version__, "pandas": pandas.__version__,
            "matplotlib": matplotlib.__version__}


def _coverage(obs: Observer, has_yard: bool, lot_flow_mode: str = "legacy") -> dict:
    stages = {
        "1_anchor": "captured (demand_anchors.jsonl; leaf_out psi4demand S right after lot generation, before HOOK_PRE_PLAN)",
        "2_backward": "captured (pre_backward / post_backward / post_backward_hooks, demand layer)",
        "3_copy": "captured (post_copy, supply layer)",
        "4_push_setup": ("captured (post_push_setup, supply layer) for products with push_config rows: "
                         + ", ".join(sorted(obs.push_results)) if obs.push_results
                         else "not_applicable (no push_config rows)"),
        "5_forward_events": "captured (actual_ship, arrival, bridge_arrival, result records, push_shortfall)",
        "6_final": "captured (final, demand + supply)",
        "7_ppc": "not_captured (stage D)",
    }
    known_gaps = [
        {"item": "demand_fulfilment_link", "status": "unknown",
         "note": "The engine does not record which shipment satisfied which request (CO/S). No such relation is written."},
        ({"item": "pull_mode_receipts", "status": "no_physical_relation",
          "note": "Nodes below a decouple point (and InBound pull/decoupling copy) get P = psi4demand P copy, not a propagated shipment. No arrival event exists for these receipts."}
         if lot_flow_mode == "legacy" else
         {"item": "pull_mode_receipts", "status": "no_physical_relation (InBound only)",
          "note": "lot_flow_mode=identity: every OutBound child receives its parent's actual shipment (arrival events exist). Remaining: InBound non-push decoupling / in_pull_mode nodes still get P = psi4demand P copy (Decision Record §6)."}),
        ({"item": "cap_hard_sealed_lot_ids", "status": "unknown",
          "note": "ForwardPlanResult.cap_hard_events holds counts only; the sealed Lot_IDs are not recorded (legacy: they go to CO[w+1])."}
         if lot_flow_mode == "legacy" else
         {"item": "cap_hard_deferred_lot_ids", "status": "unknown",
          "note": "lot_flow_mode=identity (Decision Record D4): lots over cap_hard are deferred, identity kept, to the front of P[w+1], not to CO. ForwardPlanResult.cap_hard_events holds counts only; the deferred Lot_IDs are not recorded individually."}),
        ({"item": "push_shortfall_lot_ids", "status": "unknown",
          "note": "_push_shortfall holds counts only; which planned-S IDs were not shipped is not recorded."}
         if lot_flow_mode == "legacy" else
         {"item": "push_shortfall_lot_ids", "status": "observed_via_CO",
          "note": "lot_flow_mode=identity: _push_shortfall = count of requests not matched in the week; those Lot_IDs are in the push node's supply CO of the next week (psi_intervals bucket CO)."}),
        {"item": "inline_push_decoupling_propagation", "status": "not_observed",
         "note": "ForwardPlanner.run propagates a push decoupling node with a parent inline (not via _propagate_to_parent). Not wrapped; affects only models where such a node has a parent."},
        {"item": "within_week_order", "status": "partial",
         "note": "sequence = list position in the engine list (observed); cross-node processing order within a week is not an event sequence."},
    ]
    return {"stages": stages,
            "kitting": ("present: stockyard PSI (P/S/I/CO) is captured as intervals; "
                        "node.kitting records are NOT captured in schema lovem-a1"
                        if has_yard else "not_applicable (no stockyard node)"),
            "known_gaps": known_gaps,
            "arrival_unlinked": obs.counts.get("arrival_unlinked", 0),
            "missing_weeks": [], "period_edges": {
                "before_horizon": "backward_past_due events (demand that could not be placed before week 0)",
                "after_horizon": "arrival_beyond_horizon events (shipments whose arrival week >= n_weeks)"}}
