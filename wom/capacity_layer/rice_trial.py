"""Rice seasonal allocation prototype; not registered as a production plugin.

Two independent dates (harvest / milling), demand IDs unchanged. Resource
capacities carry explicit kg units; PSI keeps one ID per final-demand lot.
Reuses capacity_layer's resource model / validators. No protected-core edits.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from .solver import (
    Allocation, Option, Problem, Request, Solution,
    solve_greedy, solve_lp, validate_problem, validate_solution,
)


ROLES = ("harvest", "collection", "store_receipt", "storage", "polish", "dc", "market")


@dataclass(frozen=True)
class RiceRoute:
    key: str
    product: str
    market: str
    field: str
    collection: str
    supply_point: str
    warehouse: str
    polisher: str
    dc: str
    resources: dict[str, str]
    white_kg_per_lot: Fraction
    milling_yield: Fraction
    field_to_collection: int
    collection_to_store: int
    store_to_polish: int
    polish_to_dc: int
    dc_to_market: int

    @property
    def raw_kg_per_lot(self):
        return self.white_kg_per_lot / self.milling_yield


@dataclass(frozen=True)
class RicePolicy:
    max_harvest_advance_weeks: int
    max_brown_storage_weeks: int
    max_polish_advance_weeks: int


@dataclass(frozen=True)
class RiceDemand:
    lot_id: str
    route_key: str
    due_index: int


@dataclass(frozen=True)
class RiceTiming:
    lot_id: str
    route_key: str
    due: int
    harvest: int
    collection: int
    store_arrival: int
    store_departure: int
    polish: int
    dc: int
    market_arrival: int


@dataclass
class RiceProblem:
    problem: Problem
    routes: dict[str, RiceRoute]
    timings: dict[str, RiceTiming]
    weeks: list[str]


def _whole_nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name}: whole nonnegative weeks required")


def build_problem(demands, routes, weeks, policy, capacities, harvest_seasons, season_limits):
    """Dense role/resource-week capacity table; season limits use raw kg.

harvest_seasons[(harvest_resource, week_index)] = crop_season_id explicitly
marks a harvest opportunity. A missing ordinary capacity or season limit is
an error. None is permitted only as an explicitly provided unlimited value.
No late options, synthetic IDs, or anonymous opening stock are generated.
"""
    from datetime import date, timedelta

    weeks = list(weeks)
    dates = []
    for w in weeks:
        year, week = w.split("-W")
        dates.append(date.fromisocalendar(int(year), int(week), 1))
    if not dates or any(b - a != timedelta(weeks=1) for a, b in zip(dates, dates[1:])):
        raise ValueError("A contiguous ISO week horizon is required")
    for name, value in vars(policy).items():
        _whole_nonnegative(value, name)
    route_map = {r.key: r for r in routes}
    if len(route_map) != len(routes) or not route_map:
        raise ValueError("Unique nonempty route keys required")
    caps = dict(capacities)
    resource_kinds = {}
    for r in routes:
        if set(r.resources) != set(ROLES) or any(not v for v in r.resources.values()):
            raise ValueError("All seven explicit resource IDs are required")
        if not isinstance(r.white_kg_per_lot, Fraction) or not isinstance(r.milling_yield, Fraction):
            raise ValueError("Use Fraction for physical quantities / yield")
        if r.white_kg_per_lot <= 0 or not 0 < r.milling_yield <= 1:
            raise ValueError("Positive final quantity and yield in (0,1] required")
        for role, rid in r.resources.items():
            kind = ("white_kg_week" if role in ("dc", "market") else
                    "brown_stock_kg" if role == "storage" else "raw_kg_week")
            if rid in resource_kinds and resource_kinds[rid] != kind:
                raise ValueError(f"Mixed physical resource units / stock and throughput: {rid}")
            resource_kinds[rid] = kind
        for name in ("field_to_collection", "collection_to_store", "store_to_polish",
                     "polish_to_dc", "dc_to_market"):
            _whole_nonnegative(getattr(r, name), name)
        # Full horizon is required even where a resource is not used in a solution.
        for resource in r.resources.values():
            for w in range(len(weeks)):
                if (resource, w) not in caps:
                    raise ValueError(f"Missing explicit capacity {(resource, w)}")
    for (res, w), season in harvest_seasons.items():
        if res not in {r.resources["harvest"] for r in routes}:
            raise ValueError("Undeclared harvest resource")
        if not isinstance(w, int) or not 0 <= w < len(weeks) or not str(season):
            raise ValueError("Harvest season outside the horizon / empty crop season")
        if (res, season) not in season_limits:
            raise ValueError(f"Missing crop yield limit {(res, season)}")
        caps[(f"crop:{res}:{season}", 0)] = season_limits[res, season]
    requests, options, timings = [], [], {}
    for d in demands:
        if not d.lot_id or d.route_key not in route_map:
            raise ValueError("Original Lot_ID and known route required")
        _whole_nonnegative(d.due_index, "due_index")
        if d.due_index >= len(weeks):
            raise ValueError("Demand outside the horizon")
        r = route_map[d.route_key]
        requests.append(Request(d.lot_id, r.product, r.market, d.due_index, 1))
        latest_p = d.due_index - r.polish_to_dc - r.dc_to_market
        for p in range(max(0, latest_p - policy.max_polish_advance_weeks), latest_p + 1):
            b = p - r.store_to_polish
            for h in range(max(0, d.due_index - policy.max_harvest_advance_weeks), b + 1):
                season = harvest_seasons.get((r.resources["harvest"], h))
                if season is None:
                    continue
                c = h + r.field_to_collection
                a = c + r.collection_to_store
                if not 0 <= a <= b or b - a > policy.max_brown_storage_weeks:
                    continue
                dc_w = p + r.polish_to_dc
                arrival = dc_w + r.dc_to_market
                key = f"{d.lot_id}@h{h:06}:p{len(weeks)-p:06}"
                timing = RiceTiming(d.lot_id, r.key, d.due_index, h, c, a, b, p, dc_w, arrival)
                uses = defaultdict(float)
                raw, white = float(r.raw_kg_per_lot), float(r.white_kg_per_lot)
                for role, w, q in (("harvest", h, raw), ("collection", c, raw),
                                   ("store_receipt", a, raw), ("polish", p, raw),
                                   ("dc", dc_w, white), ("market", arrival, white)):
                    uses[r.resources[role], w] += q
                # Capacity is the conservative weekly peak: previous end stock
                # + this week's receipts, before this week's withdrawals.
                # Actual end-of-week I remains [a,b), not [a,b].
                for w in range(a, b + 1):
                    uses[r.resources["storage"], w] += raw
                uses[f"crop:{r.resources['harvest']}:{season}", 0] += raw
                options.append(Option(key, d.lot_id, h,
                                      tuple((rid, w, q) for (rid, w), q in sorted(uses.items()))))
                timings[key] = timing
    problem = Problem(requests, options, caps, metadata={
        "adapter": "rice_seasonal_trial_v0.1",
        "resource_units": "harvest/collection/store/polish: raw kg; DC/market: white kg",
        "policy": vars(policy), "market_demand_changed": False,
        "integer_unit": "one original final-demand Lot_ID",
    })
    validate_problem(problem)
    return RiceProblem(problem, route_map, timings, weeks)


def solve(rice, method="milp"):
    """MILP priority: whole IDs served -> milling freshness -> brown kg-weeks.

LP and greedy are comparisons. LP flooring diagnostics remain visible;
fractional relaxed throughput is not called the integer attainable result.
"""
    problem = rice.problem
    if method == "greedy":
        return solve_greedy(problem)
    if method == "lp":
        return solve_lp(problem)
    if method != "milp":
        raise ValueError("Use greedy, lp, or milp")
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix, vstack

    req = validate_problem(problem)
    n = len(problem.options)
    if not n:
        return Solution("rice_milp", [], {k: r.quantity for k, r in req.items()}, 0, 0,
                        diagnostics={"integer_optimal": True, "variables": 0})
    rr = {k: i for i, k in enumerate(req)}
    cr = {k: len(rr) + i for i, (k, c) in
          enumerate(x for x in problem.capacities.items() if x[1] is not None)}
    rows, cols, data = [], [], []
    for j, o in enumerate(problem.options):
        rows.append(rr[o.request_key]); cols.append(j); data.append(1.0)
        for res, w, coef in o.uses:
            if (res, w) in cr:
                rows.append(cr[res, w]); cols.append(j); data.append(coef)
    A = coo_matrix((data, (rows, cols)), shape=(len(rr) + len(cr), n)).tocsr()
    ub = np.zeros(A.shape[0])
    for k, i in rr.items():
        ub[i] = req[k].quantity
    for k, i in cr.items():
        ub[i] = problem.capacities[k]
    ones = coo_matrix(np.ones((1, n))).tocsr()
    white_advance = np.array([
        req[o.request_key].due_week - rice.timings[o.key].market_arrival
        for o in problem.options], dtype=float)
    brown = np.array([
        float(rice.routes[rice.timings[o.key].route_key].raw_kg_per_lot) *
        (rice.timings[o.key].store_departure - rice.timings[o.key].store_arrival)
        for o in problem.options], dtype=float)

    def optimize(cost, matrix, lower, upper):
        result = milp(cost, integrality=np.ones(n), bounds=Bounds(0, 1),
                      constraints=LinearConstraint(matrix, lower, upper),
                      options={"time_limit": 60.0, "mip_rel_gap": 0.0})
        if not result.success:
            raise RuntimeError(f"Rice integer allocation not proven optimal: {result.message}")
        if any(abs(x - round(float(x))) > 1e-7 for x in result.x):
            raise RuntimeError("Fractional original ID returned by MILP")
        return result

    first = optimize(-np.ones(n), A, np.full(len(ub), -np.inf), ub)
    served = int(round(float(first.x.sum())))
    A2 = vstack([A, ones], format="csr")
    lo2 = np.r_[np.full(len(ub), -np.inf), served]
    hi2 = np.r_[ub, served]
    second = optimize(white_advance, A2, lo2, hi2)
    freshness = int(round(float(white_advance @ second.x)))
    A3 = vstack([A2, coo_matrix(white_advance.reshape(1, -1))], format="csr")
    third = optimize(brown, A3, np.r_[lo2, freshness], np.r_[hi2, freshness])
    allocations = [Allocation(o.key, int(round(float(x))))
                   for o, x in zip(problem.options, third.x) if round(float(x))]
    assigned = {problem.options[j].request_key
                for j, x in enumerate(third.x) if round(float(x))}
    solution = Solution("rice_milp", allocations, {k: int(k not in assigned) for k in req},
                        served, sum(req[o.request_key].due_week - o.plan_week
                                    for o, x in zip(problem.options, third.x) if round(float(x))),
                        diagnostics={
                            "integer_optimal": True, "variables": n,
                            "white_prebuild_lot_weeks": freshness,
                            "brown_storage_kg_weeks": float(third.fun),
                            "objective_order": ["served_IDs", "white_prebuild_lot_weeks", "brown_kg_weeks"],
                        })
    validate_solution(problem, solution)
    return solution


def assignments(rice, solution):
    validate_solution(rice.problem, solution)
    allocated = {}
    for a in solution.allocations:
        t = rice.timings[a.option_key]
        if a.quantity != 1 or t.lot_id in allocated:
            raise ValueError("One assignment per original demand ID required")
        allocated[t.lot_id] = t
    return allocated


def physical_ledger(rice, solution):
    """Exact per-ID stage quantities; physical inventory / transit separately.

Milling residual is an unpriced other output, not an assumed loss or sale.
Raw rice is removed at milling; the finished rice never duplicates raw mass.
"""
    assigned = assignments(rice, solution)
    out = []
    for t in assigned.values():
        r = rice.routes[t.route_key]
        raw, white = r.raw_kg_per_lot, r.white_kg_per_lot
        for w in range(t.harvest, t.due + 1):
            if w < t.collection:
                stage, node, qty = "brown_transit", f"{r.field}->{r.collection}", raw
            elif w < t.store_arrival:
                stage, node, qty = "brown_transit", f"{r.collection}->{r.warehouse}", raw
            elif w < t.store_departure:
                stage, node, qty = "brown_inventory", r.warehouse, raw
            elif w < t.polish:
                stage, node, qty = "brown_transit", f"{r.warehouse}->{r.polisher}", raw
            elif w < t.dc:
                stage, node, qty = "white_transit", f"{r.polisher}->{r.dc}", white
            elif w < t.market_arrival:
                stage, node, qty = "white_transit", f"{r.dc}->{r.market}", white
            elif w < t.due:
                stage, node, qty = "white_inventory", r.market, white
            else:
                stage, node, qty = "sold", r.market, white
            residual = raw - white if w >= t.polish else Fraction(0)
            # One demand token's final mass + other output equals its harvested mass.
            if qty + residual != raw:
                raise RuntimeError("Physical mass balance failed")
            out.append({"lot_id": t.lot_id, "product": r.product, "week_index": w,
                        "week": rice.weeks[w], "stage": stage, "node_or_lane": node,
                        "mass_kg_exact": str(qty), "mass_kg": float(qty),
                        "other_output_kg_exact": str(residual),
                        "harvest_mass_kg_exact": str(raw)})
    return out


def apply_to_tree(rice, solution, tree):
    """Only internal demand positions on a compatible isolated identity tree.

No CSV, node capacity, mode, opening inventory, or market S/P is modified.
This bridge supports the declared serial field/collection route, a virtual
supply point, and warehouse/mill/DC/market with zero safety-stock weeks.
"""
    from wom.model.plan_node import S, P

    assigned = assignments(rice, solution)
    if list(tree.week_labels) != rice.weeks:
        raise ValueError("Tree and allocation horizon differ")
    by_product = {}
    for r in rice.routes.values():
        nodes = {n.node_name: n for n in tree.iter_all_nodes(r.product)}
        by_product[r.product] = nodes
        required = [r.field, r.collection, r.supply_point, r.warehouse, r.polisher, r.dc, r.market]
        if any(name not in nodes for name in required):
            raise ValueError("Route is missing a declared node")
        checks = [(r.field, r.collection, r.field_to_collection),
                  (r.warehouse, r.supply_point, r.collection_to_store),
                  (r.polisher, r.warehouse, r.store_to_polish),
                  (r.dc, r.polisher, r.polish_to_dc), (r.market, r.dc, r.dc_to_market)]
        for child, parent, lt in checks:
            nd = nodes[child]
            actual_lt = (int(nd.transit_lt_wks or nd.lt_wks)
                         if nd.side == "inbound" else int(nd.lt_wks))
            if nd.parent is not nodes[parent] or actual_lt != lt:
                raise ValueError(f"Declared path / LT differs at {child}")
        if nodes[r.collection].parent is not None or nodes[r.supply_point].parent is not None:
            raise ValueError("Expected one inbound root and an outbound virtual root")
        for name in required:
            nd = nodes[name]
            if nd.bom_qty != 1 or nd.ss_wks != 0 or nd.plan_mode != "pull":
                raise ValueError("Bridge only supports bom_qty=1, ss=0, pull nodes")
            if not all(nd.is_open(w) for w in range(len(rice.weeks))):
                raise ValueError("This bridge does not yet support closure/shift lead-time changes")
        if any(nd.is_decoupling for nd in nodes.values() if nd.side == "inbound"):
            raise ValueError("Inbound P-copy decoupling is outside this bridge")
    original = {}
    for product, nodes in by_product.items():
        original[product] = {n.node_name: [list(x[S]) for x in n.psi4demand]
                             for n in nodes.values() if n.node_type == "leaf_out"}
    expected = defaultdict(list)
    for req in rice.problem.requests:
        expected[(req.product, req.market, req.due_week)].append(req.key)
    for product, markets in original.items():
        for name, cells in markets.items():
            for w, cell in enumerate(cells):
                if sorted(cell) != sorted(expected[product, name, w]):
                    raise ValueError("Market requests are not exactly the original allocation inputs")
    for nodes in by_product.values():
        for nd in nodes.values():
            if nd.node_type != "leaf_out":
                for w in range(len(rice.weeks)):
                    nd.psi4demand[w] = [[], [], [], []]
    for t in assigned.values():
        r = rice.routes[t.route_key]
        nodes = by_product[r.product]
        for name, p, s in ((r.field, t.harvest, t.harvest),
                           (r.collection, t.collection, t.collection),
                           (r.supply_point, t.collection, t.collection),
                           (r.warehouse, t.store_arrival, t.store_departure),
                           (r.polisher, t.polish, t.polish), (r.dc, t.dc, t.dc)):
            nodes[name].psi4demand[p][P].append(t.lot_id)
            nodes[name].psi4demand[s][S].append(t.lot_id)
    return len(assigned)
