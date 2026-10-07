"""Generation switch on one shared assembly line (RequestLetter_GenerationLine_UpperLayer).

The old generation and the new generation share ONE line and are not built in
mixed flow. With the switch week ``s`` (a line week) and the gap ``g``:

    week          old-generation node     new-generation node
    w < s         cap_old                 0
    s <= w < s+g  0 (changeover)          0 (changeover)
    w >= s+g      0                       cap_new

Every week of the horizon gets a value (0 is written, never left blank --
blank would mean "no ceiling", RequestLetter_CapacityZeroBlank).

``sweep_switch_weeks`` solves the upper LP (solver.solve_lp) once per
candidate ``s`` for the two generations and reports, per candidate, the lots
allocated by their original request week, the unallocated lots per
generation, and the prebuild (advance) lot-weeks. The best ``s*`` is the
candidate with the fewest unallocated lots, ties broken by the fewest advance
lot-weeks (decision d: quantity first).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from .solver import solve_lp


@dataclass(frozen=True)
class LineCapacity:
    product: str
    peak_week: str
    peak_demand: int
    factor: float
    capacity: int          # ceil(peak_demand * factor)


def line_capacity_from_demand(demand_rows: Sequence[dict], product: str,
                              factor: float) -> LineCapacity:
    """Peak weekly demand (all markets) x factor, rounded UP to a whole lot.

    ``demand_rows``: dicts with sku_id, week, quantity (demand_forecast.csv).
    The first week reaching the peak is reported.
    """
    if factor <= 0:
        raise ValueError("factor must be > 0")
    per_week: Dict[str, int] = {}
    for r in demand_rows:
        if str(r["sku_id"]) == product:
            per_week[str(r["week"])] = per_week.get(str(r["week"]), 0) + int(r["quantity"])
    if not per_week or max(per_week.values()) <= 0:
        raise ValueError(f"{product}: no positive demand")
    peak = max(per_week.values())
    week = min(w for w, q in per_week.items() if q == peak)
    # the tiny epsilon keeps an exact product (e.g. 1000 x 1.1 = 1100.0000000000002) from rounding up
    cap = math.ceil(peak * factor - 1e-9)
    return LineCapacity(product, week, peak, factor, cap)


def line_schedule(n_weeks: int, switch_index: int, gap: int,
                  cap_old: float, cap_new: float):
    """(old_caps, new_caps) per week index; see the module table."""
    if gap < 0:
        raise ValueError("gap must be >= 0")
    if not 0 <= switch_index <= n_weeks:
        raise ValueError("switch week outside the horizon")
    old = [float(cap_old) if w < switch_index else 0.0 for w in range(n_weeks)]
    new = [float(cap_new) if w >= switch_index + gap else 0.0 for w in range(n_weeks)]
    return old, new


def _with_line(problem, adapter, node_name, caps):
    nid = next(n for n, r in adapter.nodes.items() if r["node_name"] == node_name)
    out = dict(problem.capacities)
    for w, c in enumerate(caps):
        out[nid, w] = c
        if ("backward_root:" + nid, w) in out:
            out["backward_root:" + nid, w] = c
    from .solver import Problem
    return Problem(problem.requests, problem.options, out, dict(problem.metadata))


def evaluate_switch(old, new, s: int, gap: int, cap_old: float, cap_new: float) -> dict:
    """Solve both generations for one switch week.

    ``old`` / ``new``: (adapter, problem, line_node_name) of each generation.
    """
    n_weeks = len(old[0].weeks)
    caps_old, caps_new = line_schedule(n_weeks, s, gap, cap_old, cap_new)
    row = {"s_index": s, "s_week": old[0].weeks[s] if s < n_weeks else "",
           "resume_week": old[0].weeks[s + gap] if s + gap < n_weeks else ""}
    t0 = time.perf_counter()
    for tag, (adapter, problem, node), caps in (("old", old, caps_old), ("new", new, caps_new)):
        p = _with_line(problem, adapter, node, caps)
        sol = solve_lp(p)
        demand = sum(r.quantity for r in p.requests)
        opts = {o.key: o for o in p.options}
        reqs = {r.key: r for r in p.requests}
        advanced = sum(a.quantity for a in sol.allocations
                       if opts[a.option_key].plan_week < reqs[opts[a.option_key].request_key].due_week)
        # longest advance used, and the peak number of lots held ahead of their request
        # week (made in plan week p, requested in week d: held in weeks p..d-1)
        held = [0] * (n_weeks + 1)
        max_adv = 0
        for a in sol.allocations:
            o = opts[a.option_key]
            d = reqs[o.request_key].due_week
            if o.plan_week < d:
                held[o.plan_week] += a.quantity
                held[d] -= a.quantity
                max_adv = max(max_adv, d - o.plan_week)
        run, peak = 0, 0
        for v in held:
            run += v
            peak = max(peak, run)
        row.update({
            f"{tag}_demand": demand, f"{tag}_served": sol.served,
            f"{tag}_unallocated": demand - sol.served,
            f"{tag}_advance_lot_weeks": sol.advance_lot_weeks,
            f"{tag}_advanced_lots": advanced,
            f"{tag}_max_advance_weeks": max_adv,
            f"{tag}_peak_prebuild_lots": peak,
            f"{tag}_relaxation_upper_bound": sol.relaxation_upper_bound,
            f"{tag}_fractional_cells": sol.fractional_cells,
        })
        if tag == "old":
            # SmartX lots made on the line before s for market weeks after the switch
            prebuilt = 0
            for a in sol.allocations:
                o = opts[a.option_key]
                if reqs[o.request_key].due_week >= s:
                    prebuilt += a.quantity
            row["old_lots_due_after_s"] = prebuilt
            row["old_demand_due_after_s"] = sum(r.quantity for r in p.requests if r.due_week >= s)
    row["unallocated_total"] = row["old_unallocated"] + row["new_unallocated"]
    row["advance_lot_weeks_total"] = row["old_advance_lot_weeks"] + row["new_advance_lot_weeks"]
    row["elapsed_seconds"] = round(time.perf_counter() - t0, 2)
    return row


def best_switch(rows: List[dict]) -> Optional[dict]:
    """Fewest unallocated lots, then fewest advance lot-weeks, then earliest s."""
    if not rows:
        return None
    return min(rows, key=lambda r: (r["unallocated_total"], r["advance_lot_weeks_total"], r["s_index"]))


def sweep_switch_weeks(old, new, candidates: Sequence[int], gap: int,
                       cap_old: float, cap_new: float, progress=None) -> List[dict]:
    rows = []
    for s in candidates:
        rows.append(evaluate_switch(old, new, s, gap, cap_old, cap_new))
        if progress:
            progress(rows[-1])
    return rows
