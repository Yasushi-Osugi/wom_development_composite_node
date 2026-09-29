# -*- coding: utf-8 -*-
"""
wom/lovem/viewdata.py — LOVEM stage B: drawing model (no Tk).

Reads a saved run folder (read only) and turns every interval / event /
relation of one snapshot into line segments grouped by drawing category.
The Tk viewer (wom/lovem/viewer.py) only culls and draws these arrays; all
geometry and all counts live here so that they can be tested headless.

Geometry (y grows downwards; x = week index, week w occupies [w, w+1))
  row 0              Business Owner lane (empty until stage E)
  per product block  a title gap, then every node of the product in
                     nodes.csv display_order (Outbound post-order, Inbound
                     pre-order). One node band = 3 lanes:
                       lane 0  Demand            (dashed / dotted)
                       lane 1  Supply・物         P receipt tick, I line, actual-ship tick
                       lane 2  Supply・要求       planned S, CO line
  Inside a lane each Lot_ID has its own sub-row y = lane + 0.1 + 0.8*u(lot),
  u = crc32(lot_id)/2^32 (deterministic, same for every node, so a selected
  lot can be followed across nodes). The sub-row position means nothing about
  quantity or money (design §7).

Contract (design §6.2): P, I, CO and S are never joined into one polyline:
  P and actual shipment are vertical ticks, I and CO are horizontal lines in
  different lanes, planned S is a short dash-dot bar in the request lane and
  is never drawn as a shipment.
"""
from __future__ import annotations

import csv
import os
import threading
import time
import zlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from wom.lovem.io import iter_jsonl, load_manifest, run_file

LANE_H = 1.0
NODE_H = 3.0
NODE_GAP = 0.35
PRODUCT_GAP = 1.2
BO_H = 1.4
TICK = 0.09

# category -> (layer, meaning) ; drawing styles live in the viewer
CATEGORIES = {
    "D_S":   "Demand S（要求）",
    "D_P":   "Demand P（計画配置）",
    "D_I":   "Demand I（計画上の在庫）",
    "D_CO":  "Demand CO",
    "P_rcv": "入庫（伝播の記録あり）",
    "P_unk": "入庫（出所の記録なし＝未確認）",
    "P_src": "入庫（最上流 leaf_in：外部供給）",
    "I":     "Supply I（在庫の滞留）",
    "SHIP":  "Supply Simulation 実出荷",
    "S_PLN": "予定 S（要求。実出荷ではない）",
    "CO":    "Supply CO（持越し要求）",
    "REL":   "出荷→到着（記録のある対応）",
}
LANE_OF = {"D_S": 0, "D_P": 0, "D_I": 0, "D_CO": 0,
           "P_rcv": 1, "P_unk": 1, "P_src": 1, "I": 1, "SHIP": 1,
           "S_PLN": 2, "CO": 2}


def lot_u(lot_id: str) -> float:
    return zlib.crc32(lot_id.encode("utf-8")) / 4294967296.0


@dataclass
class Cat:
    x0: np.ndarray
    y0: np.ndarray
    x1: np.ndarray
    y1: np.ndarray
    lot: np.ndarray       # int32 index into ViewData.lots
    node: np.ndarray      # int16 row index (nodes list); REL: receiver row
    week: np.ndarray      # int16 week index (REL: arrival week)
    ref: np.ndarray       # int32: interval number / event row / relation row

    def __len__(self):
        return len(self.x0)

    def segments(self, mask=None) -> np.ndarray:
        if mask is None:
            return np.stack([np.stack([self.x0, self.y0], 1), np.stack([self.x1, self.y1], 1)], 1)
        return np.stack([np.stack([self.x0[mask], self.y0[mask]], 1),
                         np.stack([self.x1[mask], self.y1[mask]], 1)], 1)


@dataclass
class ViewData:
    run_dir: str
    manifest: dict
    snapshot_phase: str
    nodes: List[dict]                       # display order
    node_row: Dict[str, int]
    node_y0: np.ndarray                     # top y of each node band
    product_spans: List[Tuple[str, float, float]]
    weeks: List[dict]
    n_weeks: int
    lots: List[str] = field(default_factory=list)
    lot_index: Dict[str, int] = field(default_factory=dict)
    cats: Dict[str, Cat] = field(default_factory=dict)
    closed: List[Tuple[int, int]] = field(default_factory=list)      # (row, week)
    before_horizon: Dict[int, List[str]] = field(default_factory=dict)  # row -> lot ids
    after_horizon: Dict[int, List[str]] = field(default_factory=dict)
    event_ids: List[str] = field(default_factory=list)
    event_rows: List[tuple] = field(default_factory=list)   # (event_type, node_id, week, seq, lot, evidence_ref)
    relation_rows: List[tuple] = field(default_factory=list)  # (relation_id, type, from, to, method, evidence_ref)
    saved_counts: Dict[str, int] = field(default_factory=dict)
    timing: Dict[str, float] = field(default_factory=dict)
    y_max: float = 0.0

    # -- geometry helpers --------------------------------------------------
    def lane_y(self, row: int, lane: int, lot: str) -> float:
        return float(self.node_y0[row]) + lane * LANE_H + 0.1 + 0.8 * lot_u(lot)

    def row_at(self, y: float) -> Tuple[Optional[int], Optional[int]]:
        """(node row, lane) under y, or (None, None)."""
        i = int(np.searchsorted(self.node_y0, y, side="right")) - 1
        if 0 <= i < len(self.nodes) and y < self.node_y0[i] + NODE_H:
            return i, int((y - self.node_y0[i]) // LANE_H)
        return None, None

    def total_segments(self) -> int:
        return sum(len(c) for c in self.cats.values())

    def unique_lots_in(self, cats=None, masks=None) -> set:
        out = set()
        for k, c in self.cats.items():
            if cats is not None and k not in cats:
                continue
            m = None if masks is None else masks.get(k)
            arr = c.lot if m is None else c.lot[m]
            out.update(np.unique(arr).tolist())
        return out


class Cancelled(Exception):
    pass


def load_view_data(run_dir: str, snapshot_phase: str = "final",
                   progress: Optional[Callable[[str, float], None]] = None,
                   cancel: Optional[threading.Event] = None) -> ViewData:
    """Load one snapshot + events + relations of a run folder into segments.

    progress(stage, fraction) is called from the loading thread; it must not
    touch Tk (the viewer forwards it through a queue). `cancel` aborts."""
    t_all = time.perf_counter()
    man = load_manifest(run_dir)

    def tick(stage, frac):
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        if progress is not None:
            progress(stage, frac)

    tick("nodes/weeks", 0.0)
    with open(os.path.join(run_dir, "nodes.csv"), encoding="utf-8") as f:
        nodes = sorted(csv.DictReader(f), key=lambda r: int(r["display_order"]))
    with open(os.path.join(run_dir, "weeks.csv"), encoding="utf-8") as f:
        weeks = list(csv.DictReader(f))
    n_weeks = len(weeks)

    y = BO_H
    node_y0, spans, prev_prod = [], [], None
    for r in nodes:
        if r["product_id"] != prev_prod:
            if prev_prod is not None:
                spans[-1] = (spans[-1][0], spans[-1][1], y)
            y += PRODUCT_GAP
            spans.append((r["product_id"], y, y))
            prev_prod = r["product_id"]
        node_y0.append(y)
        y += NODE_H + NODE_GAP
    if spans:
        spans[-1] = (spans[-1][0], spans[-1][1], y)
    vd = ViewData(run_dir=run_dir, manifest=man, snapshot_phase=snapshot_phase, nodes=nodes,
                  node_row={r["node_id"]: i for i, r in enumerate(nodes)},
                  node_y0=np.array(node_y0, dtype=np.float64), product_spans=spans,
                  weeks=weeks, n_weeks=n_weeks, y_max=y)

    lot_index = vd.lot_index
    lots = vd.lots

    def lix(lot):
        i = lot_index.get(lot)
        if i is None:
            i = lot_index[lot] = len(lots)
            lots.append(lot)
        return i

    buf = {k: ([], [], [], [], [], [], [], []) for k in CATEGORIES}

    def add(cat, x0, y0, x1, y1, lot_i, row, week, ref):
        b = buf[cat]
        b[0].append(x0); b[1].append(y0); b[2].append(x1); b[3].append(y1)
        b[4].append(lot_i); b[5].append(row); b[6].append(week); b[7].append(ref)

    # --- events first: arrivals are needed to classify P receipts -------------
    # Events and relations are Forward records. They belong to the "final"
    # snapshot only; for an earlier snapshot (before Forward) nothing was
    # shipped or received yet, so they are NOT drawn and no P is classified as
    # a recorded receipt.
    forward_events = (snapshot_phase == "final")
    t0 = time.perf_counter()
    tick("events", 0.05)
    n_ev_total = max(1, man["counts"].get("events", 1))
    arrivals = set()                   # (row, week, lot)
    ship_pos: Dict[str, Tuple[int, int, int]] = {}   # event_id -> (row, week, lot_i)
    arr_pos: Dict[str, Tuple[int, int, int]] = {}
    saved = defaultdict(int)
    for k, e in enumerate(iter_jsonl(run_file(run_dir, "events.jsonl"))):
        if k % 20000 == 0:
            tick("events", 0.05 + 0.25 * k / n_ev_total)
        et = e["event_type"]
        saved[f"event:{et}"] += 1
        row = vd.node_row.get(e["node_id"])
        lot = e.get("lot_id")
        ev_row = len(vd.event_ids)
        vd.event_ids.append(e["event_id"])
        vd.event_rows.append((et, e["node_id"], e["week_index"], e["sequence"], lot,
                              e.get("evidence_ref")))
        if not forward_events and et in ("actual_ship", "arrival", "bridge_arrival",
                                         "arrival_beyond_horizon"):
            continue
        if et == "actual_ship" and row is not None:
            li = lix(lot)
            x = e["week_index"] + 0.75
            yy = vd.lane_y(row, 1, lot)
            add("SHIP", x, yy - TICK, x, yy + TICK, li, row, e["week_index"], ev_row)
            ship_pos[e["event_id"]] = (row, e["week_index"], li)
        elif et in ("arrival", "bridge_arrival") and row is not None:
            arrivals.add((row, e["week_index"], lot))
            arr_pos[e["event_id"]] = (row, e["week_index"], lix(lot))
        elif et == "backward_past_due" and row is not None:
            vd.before_horizon.setdefault(row, []).append(lot)
            lix(lot)
        elif et == "arrival_beyond_horizon" and row is not None:
            vd.after_horizon.setdefault(row, []).append(lot)
            lix(lot)
    vd.timing["load_events_s"] = time.perf_counter() - t0

    # --- relations -------------------------------------------------------------
    t0 = time.perf_counter()
    tick("relations", 0.30)
    for k, r in enumerate(iter_jsonl(run_file(run_dir, "relations.jsonl")) if forward_events else []):
        saved["relation:" + r["relation_type"]] += 1
        a, b = ship_pos.get(r["from_ref"]), arr_pos.get(r["to_ref"])
        rel_row = len(vd.relation_rows)
        vd.relation_rows.append((r["relation_id"], r["relation_type"], r["from_ref"], r["to_ref"],
                                 r.get("method"), r.get("evidence_ref")))
        if a is None or b is None:
            saved["relation_unresolved"] += 1
            continue
        lot = lots[a[2]]
        add("REL", a[1] + 0.75, vd.lane_y(a[0], 1, lot), b[1] + 0.25, vd.lane_y(b[0], 1, lot),
            a[2], b[0], b[1], rel_row)
    vd.timing["load_relations_s"] = time.perf_counter() - t0

    # --- intervals of the snapshot ----------------------------------------------
    t0 = time.perf_counter()
    snaps = [s for s in man["snapshots"] if s["phase"] == snapshot_phase]
    n_iv_total = max(1, sum(s["n_intervals"] for s in snaps))
    done = 0
    leaf_in_rows = {i for i, r in enumerate(nodes) if r["node_type"] == "leaf_in"}
    for s in snaps:
        for r in iter_jsonl(os.path.join(run_dir, s["intervals_file"])):
            done += 1
            if done % 20000 == 0:
                tick("intervals", 0.35 + 0.6 * done / n_iv_total)
            row = vd.node_row.get(r["node_id"])
            if row is None:
                saved["interval_unknown_node"] += 1
                continue
            saved[f"interval:{r['layer']}:{r['bucket']}"] += 1
            lot = r["lot_id"]
            li = lix(lot)
            s_w, e_w, b = r["start_week_index"], r["end_week_index"], r["bucket"]
            ivn = int(r["interval_id"][2:])
            if r["layer"] == "demand":
                cat = {"S": "D_S", "P": "D_P", "I": "D_I", "CO": "D_CO"}[b]
                yy = vd.lane_y(row, 0, lot)
                if b in ("S", "P"):
                    add(cat, s_w + 0.12, yy, s_w + 0.88, yy, li, row, s_w, ivn)
                else:
                    add(cat, s_w, yy, e_w + 1.0, yy, li, row, s_w, ivn)
                continue
            if b == "P":
                if row in leaf_in_rows:
                    cat = "P_src"
                elif (row, s_w, lot) in arrivals:
                    cat = "P_rcv"
                else:
                    cat = "P_unk"
                yy = vd.lane_y(row, 1, lot)
                x = s_w + 0.25
                add(cat, x, yy - TICK, x, yy + TICK, li, row, s_w, ivn)
            elif b == "I":
                yy = vd.lane_y(row, 1, lot)
                add("I", s_w, yy, e_w + 1.0, yy, li, row, s_w, ivn)
            elif b == "S":
                yy = vd.lane_y(row, 2, lot)
                add("S_PLN", s_w + 0.15, yy, s_w + 0.85, yy, li, row, s_w, ivn)
            else:
                yy = vd.lane_y(row, 2, lot)
                add("CO", s_w, yy, e_w + 1.0, yy, li, row, s_w, ivn)
    vd.timing["load_intervals_s"] = time.perf_counter() - t0

    # --- closed weeks ------------------------------------------------------------
    with open(os.path.join(run_dir, "capacity.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["is_open"] == "0":
                row = vd.node_row.get(r["node_id"])
                if row is not None:
                    vd.closed.append((row, int(r["week_index"])))

    t0 = time.perf_counter()
    tick("arrays", 0.97)
    for k, b in buf.items():
        vd.cats[k] = Cat(np.asarray(b[0], np.float32), np.asarray(b[1], np.float32),
                         np.asarray(b[2], np.float32), np.asarray(b[3], np.float32),
                         np.asarray(b[4], np.int32), np.asarray(b[5], np.int16),
                         np.asarray(b[6], np.int16), np.asarray(b[7], np.int32))
    vd.timing["build_arrays_s"] = time.perf_counter() - t0
    vd.saved_counts = dict(saved)
    vd.timing["load_total_s"] = time.perf_counter() - t_all
    tick("done", 1.0)
    return vd


# ----------------------------------------------------------------------------
# queries used by the viewer (and tests)
# ----------------------------------------------------------------------------

def visible_mask(c: Cat, x0: float, x1: float, y0: float, y1: float) -> np.ndarray:
    """Segments that intersect the view box (axis-aligned bounding test)."""
    lo_x = np.minimum(c.x0, c.x1); hi_x = np.maximum(c.x0, c.x1)
    lo_y = np.minimum(c.y0, c.y1); hi_y = np.maximum(c.y0, c.y1)
    return (hi_x >= x0) & (lo_x <= x1) & (hi_y >= y0) & (lo_y <= y1)


def pick(vd: ViewData, x: float, y: float, tol_x: float, tol_y: float,
         cats=None, masks=None, limit: int = 200) -> List[dict]:
    """All segments within the tolerance box around (x, y): candidates, not a
    single silent choice. Returns dicts sorted by distance."""
    out = []
    for k, c in vd.cats.items():
        if cats is not None and k not in cats:
            continue
        m = masks.get(k) if masks else None
        idx = np.nonzero(m)[0] if m is not None else np.arange(len(c))
        if len(idx) == 0:
            continue
        ax, ay, bx, by = c.x0[idx], c.y0[idx], c.x1[idx], c.y1[idx]
        # distance in "tolerance units" from point to segment
        px, py = (x - ax) / tol_x, (y - ay) / tol_y
        dx, dy = (bx - ax) / tol_x, (by - ay) / tol_y
        L = dx * dx + dy * dy
        t = np.where(L > 0, np.clip((px * dx + py * dy) / np.where(L > 0, L, 1), 0, 1), 0)
        d2 = (px - t * dx) ** 2 + (py - t * dy) ** 2
        hit = np.nonzero(d2 <= 1.0)[0]
        for h in hit[np.argsort(d2[hit])][:limit]:
            i = idx[h]
            out.append({"cat": k, "i": int(i), "lot": vd.lots[c.lot[i]], "row": int(c.node[i]),
                        "week": int(c.week[i]), "ref": int(c.ref[i]), "d2": float(d2[h])})
    out.sort(key=lambda r: r["d2"])
    return out[:limit]


def lot_history(vd: ViewData, lot: str) -> Dict[int, List[dict]]:
    """Every drawn record of one Lot_ID, by node row."""
    li = vd.lot_index.get(lot)
    hist: Dict[int, List[dict]] = defaultdict(list)
    if li is None:
        return hist
    for k, c in vd.cats.items():
        for i in np.nonzero(c.lot == li)[0]:
            rec = {"cat": k, "week": int(c.week[i]), "ref": int(c.ref[i]),
                   "x0": float(c.x0[i]), "x1": float(c.x1[i])}
            if k in ("SHIP",):
                ev = vd.event_rows[rec["ref"]]
                rec.update(event_id=vd.event_ids[rec["ref"]], evidence_ref=ev[5], seq=ev[3])
            if k == "REL":
                rel = vd.relation_rows[rec["ref"]]
                rec.update(relation_id=rel[0], from_ref=rel[2], to_ref=rel[3], evidence_ref=rel[5])
            hist[int(c.node[i])].append(rec)
    for row, lot_ids in vd.before_horizon.items():
        for _ in range(lot_ids.count(lot)):
            hist[row].append({"cat": "BEFORE_HORIZON", "week": None})
    for row, lot_ids in vd.after_horizon.items():
        for _ in range(lot_ids.count(lot)):
            hist[row].append({"cat": "AFTER_HORIZON", "week": None})
    for v in hist.values():
        v.sort(key=lambda r: (r["week"] if r["week"] is not None else -1, r["cat"]))
    return hist


def evidence_for_lot(vd: ViewData, lot: str) -> List[dict]:
    """Every event of this lot (all types) with its evidence_ref."""
    out = []
    for i, ev in enumerate(vd.event_rows):
        if ev[4] == lot:
            out.append({"event_id": vd.event_ids[i], "event_type": ev[0], "node_id": ev[1],
                        "week_index": ev[2], "sequence": ev[3], "evidence_ref": ev[5]})
    return out


class EvidenceIndex:
    """Lazy reader of source_evidence (loaded on first use)."""

    def __init__(self, run_dir: str):
        self.run_dir = run_dir
        self._idx: Optional[Dict[str, dict]] = None

    def get(self, evidence_id: str) -> Optional[dict]:
        if self._idx is None:
            self._idx = {r["evidence_id"]: r for r in iter_jsonl(run_file(self.run_dir, "source_evidence.jsonl"))}
        return self._idx.get(evidence_id)


def se2_view(vd: ViewData, se2: dict) -> dict:
    """Planned S / actual shipment / I / CO Lot_IDs of the SE2 node for its
    target weeks, straight from the drawn data (no classification)."""
    row = next(i for i, r in enumerate(vd.nodes)
               if r["product_id"] == se2["product_id"] and r["node_name"] == se2["node_name"])
    labels = [w["engine_week_label"] for w in vd.weeks]
    out = {"row": row, "weeks": {}}
    for wl in se2["target_weeks"]:
        w = labels.index(wl)
        cell = {}
        for cat, key in (("S_PLN", "planned_S"), ("SHIP", "actual_ship"),
                         ("P_rcv", "P_received"), ("P_unk", "P_unconfirmed"), ("P_src", "P_source")):
            c = vd.cats[cat]
            m = (c.node == row) & (c.week == w)
            cell[key] = sorted(vd.lots[i] for i in c.lot[m])
        for cat, key in (("I", "I"), ("CO", "CO")):
            c = vd.cats[cat]
            m = (c.node == row) & (c.x0 <= w) & (c.x1 >= w + 1)
            cell[key] = sorted(vd.lots[i] for i in c.lot[m])
        out["weeks"][wl] = cell
    return out
