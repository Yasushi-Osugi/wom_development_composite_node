"""Rice seasonal supply on the upper capacity layer (RequestLetter_RiceSeasonal_Implementation B).

Future market demand IDs are allocated to a past, feasible harvest, carried to
the brown-rice warehouse, and milled close to the request week. The market
request (Lot_ID, request week) is never changed; only the internal plan
positions (psi4demand of the non-market nodes) are written, and Forward
(identity) then checks the plan on its own.

Two independent dates per lot (Sol's prototype, wom/capacity_layer/rice_trial.py):
the harvest week ``h`` and the milling week ``p``. Generalised here to
  * the plan tree (routes are read from it; any serial market route
    SP -> warehouse -> mill -> DC -> market, inbound root -> one paddy),
  * explicit input CSVs (recipe, resources, resource map, weekly capacities
    with the harvest calendar, crop limits, policy) -- see load_inputs(),
  * closed weeks (a receipt in a closed week is processed in the next open
    week, exactly as ForwardPlanner Step 0-closure does),
  * aggregation: one request per (product, market, request week) with the
    original IDs in market order; integer quantities are solved, then
    expanded back to the original IDs (no ID is minted, dropped or moved),
  * ONE joint problem for all products, so a resource shared by products
    (a mill) is limited once.

Solve order (lexicographic, each stage proven optimal by HiGHS MILP):
  1. lots allocated by their original request week          (maximise)
  2. earliest request week first                           (min sum x*due)
  3. within one product and request week, proportional to the market
     demand (largest-remainder targets, L1 deviation)       (min deviation)
  4. milling advance lot-weeks                              (min)
  5. brown-rice kg-weeks in the warehouse                  (min)
Unallocated IDs stay in the market request as backlog and are listed.

Units: harvest / collection / warehouse receipt / milling are raw (brown)
kg per week, DC / market are white kg per week, the warehouse stock is raw
kg, a crop season limit is raw kg. One final-demand lot = white_kg_per_lot
of white rice = white_kg_per_lot / milling_yield of brown rice. The PSI count
stays one ID per final-demand lot (cpu_size is not used to divide IDs).
None = explicitly unlimited, 0 = zero, a missing value is an error.
"""
from __future__ import annotations

import csv
import math
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional, Tuple

ROLES = ("harvest", "collection", "store_receipt", "storage", "polish", "dc", "market")
ROLE_KIND = {"harvest": "raw_kg_week", "collection": "raw_kg_week", "store_receipt": "raw_kg_week",
             "storage": "brown_stock_kg", "polish": "raw_kg_week",
             "dc": "white_kg_week", "market": "white_kg_week"}
KINDS = ("raw_kg_week", "white_kg_week", "brown_stock_kg")
CONFIG_FILES = ("rice_seasonal_config.csv", "rice_recipe.csv", "rice_resources.csv",
                "rice_resource_map.csv", "rice_resource_capacity.csv", "rice_crop_limit.csv")


class RiceInputError(ValueError):
    """An input CSV is missing, unreadable or inconsistent."""


class RiceTreeError(ValueError):
    """The product tree is outside what the Rice adapter represents."""


# ── inputs ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Recipe:
    product: str
    white_kg_per_lot: Fraction
    milling_yield: Fraction

    @property
    def raw_kg_per_lot(self) -> Fraction:
        return self.white_kg_per_lot / self.milling_yield


@dataclass(frozen=True)
class Policy:
    harvest_lookback_weeks: int      # beyond the route lead time
    max_brown_storage_weeks: int
    max_polish_advance_weeks: int
    report_start: Optional[str]


@dataclass
class RiceInputs:
    policy: Policy
    recipes: Dict[str, Recipe]
    resource_kind: Dict[str, str]
    resource_map: Dict[Tuple[str, str], Dict[str, str]]     # (product, node_name) -> {role: rid}
    capacity: Dict[Tuple[str, int], Optional[float]]        # (rid, w) -> kg or None
    harvest_season: Dict[Tuple[str, int], str]              # (harvest rid, w) -> crop season
    crop_limit: Dict[Tuple[str, str], Optional[float]]      # (harvest rid, season) -> raw kg
    weeks: List[str]
    notes: Dict[str, str] = field(default_factory=dict)


def _read(path):
    if not os.path.exists(path):
        raise RiceInputError(f"missing input file: {path}")
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _frac(text, where):
    try:
        v = Fraction(str(text).strip())
    except (ValueError, ZeroDivisionError):
        raise RiceInputError(f"{where}: not a number: {text!r}") from None
    return v


def _whole(text, where):
    v = _frac(text, where)
    if v.denominator != 1 or v < 0:
        raise RiceInputError(f"{where}: a whole number >= 0 is required: {text!r}")
    return int(v)


def load_inputs(model_dir: str, weeks: List[str]) -> RiceInputs:
    """Read the six Rice input CSVs (see the module doc and the model README).

    rice_seasonal_config.csv : key,value -- harvest_lookback_weeks,
        max_brown_storage_weeks, max_polish_advance_weeks
    (the report start is vc_config.csv report_start, see wom/engine/report_start.py)
    rice_recipe.csv          : product, white_kg_per_lot, milling_yield
    rice_resources.csv       : resource_id, kind, capacity_unit, default_capacity
        kind = raw_kg_week | white_kg_week | brown_stock_kg
        capacity_unit = raw_kg | white_kg | lot | unlimited
        default_capacity applies to every week without a row in
        rice_resource_capacity.csv ("unlimited" needs it blank)
    rice_resource_map.csv    : product, node_name, role, resource_id
    rice_resource_capacity.csv : resource_id, week, capacity, crop_season
        a non-blank crop_season marks a harvest opportunity of that resource
    rice_crop_limit.csv      : resource_id, crop_season, limit, unit (raw_kg|lot|unlimited)
    """
    widx = {w: i for i, w in enumerate(weeks)}
    j = lambda n: os.path.join(model_dir, n)
    cfg = {r["key"].strip(): (r.get("value") or "").strip() for r in _read(j("rice_seasonal_config.csv"))}
    for k in ("harvest_lookback_weeks", "max_brown_storage_weeks", "max_polish_advance_weeks"):
        if k not in cfg:
            raise RiceInputError(f"rice_seasonal_config.csv: {k} is required")
    # The reporting period starts at vc_config.csv report_start (one place for the
    # World Map, Value Chain, Flow Check and this layer; RequestLetter_RiceSeasonal_
    # PolishAdvance1 work 5). A second copy here would drift, so it stops.
    if "report_start" in cfg:
        raise RiceInputError("rice_seasonal_config.csv: report_start is read from vc_config.csv "
                             "(key report_start); remove it here and put it in vc_config.csv")
    from wom.engine.report_start import read_report_start
    rs, rs_src = read_report_start(model_dir)
    if rs is not None and rs not in widx:
        raise RiceInputError(f"{rs_src}: report_start {rs} is outside the plan")
    policy = Policy(_whole(cfg["harvest_lookback_weeks"], "harvest_lookback_weeks"),
                    _whole(cfg["max_brown_storage_weeks"], "max_brown_storage_weeks"),
                    _whole(cfg["max_polish_advance_weeks"], "max_polish_advance_weeks"), rs)
    recipes = {}
    for i, r in enumerate(_read(j("rice_recipe.csv")), start=2):
        p = r["product"].strip()
        white = _frac(r["white_kg_per_lot"], f"rice_recipe.csv line {i} white_kg_per_lot")
        yld = _frac(r["milling_yield"], f"rice_recipe.csv line {i} milling_yield")
        if white <= 0 or not 0 < yld <= 1:
            raise RiceInputError(f"rice_recipe.csv line {i}: white_kg_per_lot > 0 and yield in (0, 1] required")
        if p in recipes:
            raise RiceInputError(f"rice_recipe.csv: duplicate product {p}")
        recipes[p] = Recipe(p, white, yld)
    res_def = {}
    for i, r in enumerate(_read(j("rice_resources.csv")), start=2):
        rid, kind, unit = r["resource_id"].strip(), r["kind"].strip(), r["capacity_unit"].strip()
        if kind not in KINDS:
            raise RiceInputError(f"rice_resources.csv line {i}: unknown kind {kind!r}")
        if unit not in ("raw_kg", "white_kg", "lot", "unlimited"):
            raise RiceInputError(f"rice_resources.csv line {i}: unknown capacity_unit {unit!r}")
        dflt = (r.get("default_capacity") or "").strip()
        if unit == "unlimited":
            if dflt:
                raise RiceInputError(f"rice_resources.csv line {i}: an unlimited resource has no default_capacity")
        elif dflt == "":
            raise RiceInputError(f"rice_resources.csv line {i}: default_capacity is required "
                                 "(write 0 for none; use capacity_unit=unlimited for no ceiling)")
        if rid in res_def:
            raise RiceInputError(f"rice_resources.csv: duplicate resource_id {rid}")
        res_def[rid] = (kind, unit, dflt, i)
    rmap = defaultdict(dict)
    users = defaultdict(set)
    for i, r in enumerate(_read(j("rice_resource_map.csv")), start=2):
        p, n, role, rid = (r[k].strip() for k in ("product", "node_name", "role", "resource_id"))
        if role not in ROLES:
            raise RiceInputError(f"rice_resource_map.csv line {i}: unknown role {role!r}")
        if rid not in res_def:
            raise RiceInputError(f"rice_resource_map.csv line {i}: resource {rid!r} is not in rice_resources.csv")
        if res_def[rid][0] != ROLE_KIND[role]:
            raise RiceInputError(f"rice_resource_map.csv line {i}: role {role} needs a {ROLE_KIND[role]} "
                                 f"resource, {rid} is {res_def[rid][0]}")
        if p not in recipes:
            raise RiceInputError(f"rice_resource_map.csv line {i}: product {p} has no recipe")
        if role in rmap[(p, n)]:
            raise RiceInputError(f"rice_resource_map.csv line {i}: duplicate role {role} for {p}/{n}")
        rmap[(p, n)][role] = rid
        users[rid].add(p)

    def to_kg(rid, text, where):
        kind, unit, _d, _i = res_def[rid]
        if unit == "unlimited":
            raise RiceInputError(f"{where}: {rid} is unlimited; it has no weekly value")
        v = _frac(text, where)
        if v < 0:
            raise RiceInputError(f"{where}: negative capacity {text!r}")
        if unit == "lot":
            per = {(recipes[p].raw_kg_per_lot if kind != "white_kg_week" else recipes[p].white_kg_per_lot)
                   for p in users[rid]}
            if len(per) != 1:
                raise RiceInputError(f"{where}: {rid} is given in lots but its products have different "
                                     "kg per lot; give it in kg")
            v = v * per.pop()
        elif (unit == "white_kg") != (kind == "white_kg_week"):
            raise RiceInputError(f"{where}: {rid} is {kind} but the unit is {unit}")
        return float(v)

    capacity = {}
    for rid, (kind, unit, dflt, i) in res_def.items():
        for w in range(len(weeks)):
            capacity[rid, w] = None if unit == "unlimited" else to_kg(rid, dflt, f"rice_resources.csv line {i}")
    harvest_season = {}
    seen = set()
    for i, r in enumerate(_read(j("rice_resource_capacity.csv")), start=2):
        rid, wk = r["resource_id"].strip(), r["week"].strip()
        where = f"rice_resource_capacity.csv line {i}"
        if rid not in res_def:
            raise RiceInputError(f"{where}: unknown resource {rid!r}")
        if wk not in widx:
            continue                                   # outside the plan: not used
        if (rid, wk) in seen:
            raise RiceInputError(f"{where}: duplicate {rid} {wk}")
        seen.add((rid, wk))
        capacity[rid, widx[wk]] = to_kg(rid, r["capacity"], where)
        season = (r.get("crop_season") or "").strip()
        if season:
            harvest_season[rid, widx[wk]] = season
    crop_limit = {}
    for i, r in enumerate(_read(j("rice_crop_limit.csv")), start=2):
        rid, season, unit = r["resource_id"].strip(), r["crop_season"].strip(), r["unit"].strip()
        where = f"rice_crop_limit.csv line {i}"
        if rid not in res_def:
            raise RiceInputError(f"{where}: unknown resource {rid!r}")
        if unit == "unlimited":
            crop_limit[rid, season] = None
        elif unit == "raw_kg":
            crop_limit[rid, season] = float(_frac(r["limit"], where))
        elif unit == "lot":
            per = {recipes[p].raw_kg_per_lot for p in users[rid]}
            if len(per) != 1:
                raise RiceInputError(f"{where}: lots are ambiguous for {rid}")
            crop_limit[rid, season] = float(_frac(r["limit"], where) * per.pop())
        else:
            raise RiceInputError(f"{where}: unit must be raw_kg, lot or unlimited")
    for (rid, w), season in harvest_season.items():
        if (rid, season) not in crop_limit:
            raise RiceInputError(f"rice_crop_limit.csv: no limit for {rid} crop season {season}")
    return RiceInputs(policy, recipes, {k: v[0] for k, v in res_def.items()}, dict(rmap),
                      capacity, harvest_season, crop_limit, list(weeks))


# ── routes from the plan tree ──────────────────────────────────────────────
@dataclass(frozen=True)
class Route:
    product: str
    market: str                   # leaf_out node_name
    node_ids: Dict[str, str]      # field, collection, supply_point, warehouse, mill, dc, market
    names: Dict[str, str]
    lt: Dict[str, int]            # field (paddy -> collection), warehouse, mill, dc, market
    resources: Dict[str, str]     # role -> resource_id

    @property
    def lead_time(self) -> int:
        return sum(self.lt.values())


def routes_from_tree(tree, products, inputs: RiceInputs) -> Dict[Tuple[str, str], Route]:
    out = {}
    for prod in products:
        nodes = list(tree.iter_all_nodes(prod))
        in_root = tree.get_in_root(prod)
        kids = list(in_root.children)
        if len(kids) != 1 or kids[0].node_type != "leaf_in" or kids[0].children:
            raise RiceTreeError(f"{prod}: inbound must be one collection root with one paddy (leaf_in)")
        field_n = kids[0]
        for nd in (in_root, field_n):
            if int(nd.bom_qty) != 1:
                raise RiceTreeError(f"{prod}/{nd.node_name}: bom_qty must be 1")
        for leaf in (n for n in nodes if n.node_type == "leaf_out"):
            chain = [leaf]
            while chain[-1].parent is not None:
                chain.append(chain[-1].parent)
            if len(chain) != 5 or chain[-1].node_type != "supply_point":
                raise RiceTreeError(f"{prod}/{leaf.node_name}: the market route must be "
                                    "SP -> warehouse -> mill -> DC -> market")
            mkt, dc, mill, wh, sp = chain
            names = {"field": field_n.node_name, "collection": in_root.node_name, "supply_point": sp.node_name,
                     "warehouse": wh.node_name, "mill": mill.node_name, "dc": dc.node_name,
                     "market": mkt.node_name}
            ids = {"field": field_n.node_id, "collection": in_root.node_id, "supply_point": sp.node_id,
                   "warehouse": wh.node_id, "mill": mill.node_id, "dc": dc.node_id, "market": mkt.node_id}
            for nd in (mkt, dc, mill, wh):
                if nd.ss_wks:
                    raise RiceTreeError(f"{prod}/{nd.node_name}: ss_days must be 0 on a Rice route")
            tlt = field_n.transit_lt_wks if field_n.transit_lt_wks > 0 else field_n.lt_wks
            lt = {"field": int(tlt), "warehouse": int(wh.lt_wks), "mill": int(mill.lt_wks),
                  "dc": int(dc.lt_wks), "market": int(mkt.lt_wks)}
            role_node = {"harvest": "field", "collection": "collection", "store_receipt": "warehouse",
                         "storage": "warehouse", "polish": "mill", "dc": "dc", "market": "market"}
            res = {}
            for role, key in role_node.items():
                m = inputs.resource_map.get((prod, names[key]), {})
                if role not in m:
                    raise RiceInputError(f"rice_resource_map.csv: no {role} resource for {prod}/{names[key]}")
                res[role] = m[role]
            out[(prod, mkt.node_name)] = Route(prod, mkt.node_name, ids, names, lt, res)
    return out


# ── timing of one lot ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class Timing:
    harvest: int        # paddy P / ship
    collection: int     # collection P / ship = supply point
    store_arrival: int  # warehouse P (processing week)
    store_departure: int
    polish: int         # mill P / ship
    dc: int             # DC P / ship
    market_arrival: int
    season: str


class _Calendar:
    def __init__(self, tree, products):
        self.n = tree.num_weeks()
        self.open = {}
        for p in products:
            for nd in tree.iter_all_nodes(p):
                self.open[nd.node_id] = [bool(nd.is_open(w)) for w in range(self.n)]

    def next_open(self, nid, w):
        o = self.open[nid]
        for x in range(max(w, 0), self.n):
            if o[x]:
                return x
        return None


def downstream(route: Route, cal: _Calendar, p: int):
    """Mill week p (open) -> (DC week, market arrival week) or None."""
    ids, lt = route.node_ids, route.lt
    dcw = cal.next_open(ids["dc"], p + lt["dc"])
    if dcw is None:
        return None
    arr = cal.next_open(ids["market"], dcw + lt["market"])
    if arr is None:
        return None
    return dcw, arr


def upstream(route: Route, cal: _Calendar, h: int):
    """Harvest week h -> (collection week, warehouse arrival week) or None."""
    ids, lt = route.node_ids, route.lt
    if not cal.open[ids["field"]][h]:
        return None
    c = cal.next_open(ids["collection"], h + lt["field"])
    if c is None or not cal.open[ids["supply_point"]][c]:
        return None
    a = cal.next_open(ids["warehouse"], c + lt["warehouse"])
    if a is None:
        return None
    return c, a


# ── the problem ────────────────────────────────────────────────────────────
@dataclass
class RiceRequest:
    key: str
    product: str
    market: str
    due: int
    lots: List[str]


@dataclass
class RiceOption:
    key: str
    request: str
    timing: Timing
    uses: Tuple[Tuple[str, int, float], ...]      # (rid, w, kg per lot)


@dataclass
class RiceProblem:
    inputs: RiceInputs
    routes: Dict[Tuple[str, str], Route]
    requests: Dict[str, RiceRequest]
    options: List[RiceOption]
    capacity: Dict[Tuple[str, int], Optional[float]]
    no_option: List[str]
    weeks: List[str]
    stats: dict = field(default_factory=dict)


def build_problem(tree, products, inputs: RiceInputs) -> RiceProblem:
    t0 = time.perf_counter()
    weeks = list(tree.week_labels)
    if weeks != inputs.weeks:
        raise RiceInputError("the inputs were read for another plan horizon")
    routes = routes_from_tree(tree, products, inputs)
    cal = _Calendar(tree, products)
    pol = inputs.policy
    harvest_weeks = defaultdict(list)
    for (rid, w), season in sorted(inputs.harvest_season.items(), key=lambda x: x[0][1]):
        harvest_weeks[rid].append((w, season))
    capacity = dict(inputs.capacity)
    for (rid, season), lim in inputs.crop_limit.items():
        capacity[f"crop:{rid}:{season}", 0] = lim
    requests, options, no_option = {}, [], []
    for prod in products:
        for nd in tree.iter_all_nodes(prod):
            if nd.node_type != "leaf_out":
                continue
            route = routes[(prod, nd.node_name)]
            recipe = inputs.recipes[prod]
            raw, white = float(recipe.raw_kg_per_lot), float(recipe.white_kg_per_lot)
            # latest milling week whose market arrival is not after the request week
            mill_ok = [w for w in range(len(weeks)) if cal.open[route.node_ids["mill"]][w]]
            arrivals = {}
            for p in mill_ok:
                ds = downstream(route, cal, p)
                if ds is not None:
                    arrivals[p] = ds
            for d in range(len(weeks)):
                lots = list(nd.psi4demand[d][0])
                if not lots:
                    continue
                key = f"{prod}|{nd.node_name}|{weeks[d]}"
                requests[key] = RiceRequest(key, prod, nd.node_name, d, lots)
                feas = [p for p, (dcw, arr) in arrivals.items() if arr <= d]
                if not feas:
                    no_option.append(key)
                    continue
                p_star = max(feas)
                n_before = len(options)
                for p in feas:
                    if p < p_star - pol.max_polish_advance_weeks:
                        continue
                    dcw, arr = arrivals[p]
                    b = p - route.lt["mill"]
                    for h, season in harvest_weeks[route.resources["harvest"]]:
                        if d - h > pol.harvest_lookback_weeks + route.lead_time:
                            continue
                        if h > b:
                            break
                        up = upstream(route, cal, h)
                        if up is None:
                            continue
                        c, a = up
                        if a > b or b - a > pol.max_brown_storage_weeks:
                            continue
                        uses = defaultdict(float)
                        r = route.resources
                        for role, w, q in (("harvest", h, raw), ("collection", c, raw),
                                           ("store_receipt", a, raw), ("polish", p, raw),
                                           ("dc", dcw, white), ("market", arr, white)):
                            uses[r[role], w] += q
                        for w in range(a, b + 1):          # conservative weekly peak [a, b]
                            uses[r["storage"], w] += raw
                        uses[f"crop:{r['harvest']}:{season}", 0] += raw
                        for (rid, w) in uses:
                            if (rid, w) not in capacity:
                                raise RiceInputError(f"no capacity for {rid} week {weeks[w]}")
                        options.append(RiceOption(
                            f"{key}@h{h}:p{p}", key,
                            Timing(h, c, a, b, p, dcw, arr, season),
                            tuple((rid, w, q) for (rid, w), q in sorted(uses.items()))))
                if len(options) == n_before:
                    no_option.append(key)
    nnz = sum(len(o.uses) for o in options)
    stats = {"requests": len(requests), "lots": sum(len(r.lots) for r in requests.values()),
             "options": len(options), "nonzeros": nnz + len(options),
             "requests_without_option": len(no_option),
             "build_seconds": round(time.perf_counter() - t0, 3)}
    return RiceProblem(inputs, routes, requests, options, capacity, no_option, weeks, stats)


# ── solving ────────────────────────────────────────────────────────────────
@dataclass
class RiceSolution:
    quantities: Dict[str, int]                    # option key -> lots
    served: int
    unallocated: Dict[str, int]                   # request key -> lots
    objective: dict
    lp_upper_bound: float
    stats: dict


def largest_remainder(total: int, demands: Dict[str, int]) -> Dict[str, int]:
    """Split ``total`` over the markets in proportion to their demand.

    Hamilton (largest remainder): floor of the exact share first; the lots left
    go one each to the largest fractional parts; ties -> larger demand, then
    the market name. Never more than a market's demand.
    """
    q = sum(demands.values())
    if total >= q:
        return dict(demands)
    out, rem = {}, []
    for m, d in demands.items():
        share = Fraction(total * d, q)
        out[m] = math.floor(share)
        rem.append((share - out[m], d, m))
    left = total - sum(out.values())
    for _f, _d, m in sorted(rem, key=lambda x: (-x[0], -x[1], x[2]))[:left]:
        out[m] += 1
    return out


def solve(rp: RiceProblem, time_limit: float = 600.0, advance_first: bool = False) -> RiceSolution:
    """advance_first (default False = the order in the module doc): minimise the milling
    advance right after the lots served, before the earliest-due and proportional
    rules (a comparison for the Owner, RequestLetter_RiceSeasonal_PolishAdvance1)."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, linprog, milp
    from scipy.sparse import coo_matrix, csr_matrix, vstack

    t0 = time.perf_counter()
    reqs = list(rp.requests.values())
    ridx = {r.key: i for i, r in enumerate(reqs)}
    n = len(rp.options)
    if n == 0:
        return RiceSolution({}, 0, {r.key: len(r.lots) for r in reqs}, {}, 0.0, {"variables": 0})
    finite = {}
    for o in rp.options:
        for rid, w, _q in o.uses:
            if rp.capacity[rid, w] is not None and (rid, w) not in finite:
                finite[rid, w] = len(reqs) + len(finite)
    rows, cols, data = [], [], []
    for j, o in enumerate(rp.options):
        rows.append(ridx[o.request]); cols.append(j); data.append(1.0)
        for rid, w, q in o.uses:
            if (rid, w) in finite:
                rows.append(finite[rid, w]); cols.append(j); data.append(q)
    A = coo_matrix((data, (rows, cols)), shape=(len(reqs) + len(finite), n)).tocsr()
    ub = np.zeros(A.shape[0])
    for r in reqs:
        ub[ridx[r.key]] = len(r.lots)
    for k, i in finite.items():
        ub[i] = rp.capacity[k]
    lo = np.full(A.shape[0], -np.inf)
    opt_req = np.array([ridx[o.request] for o in rp.options])
    due = np.array([reqs[i].due for i in opt_req], dtype=float)
    white_adv = np.array([rp.requests[o.request].due - o.timing.market_arrival for o in rp.options], dtype=float)
    brown = np.array([float(rp.inputs.recipes[rp.requests[o.request].product].raw_kg_per_lot)
                      * (o.timing.store_departure - o.timing.store_arrival) for o in rp.options])
    # LP relaxation (upper bound of stage 1), reported next to the integer result
    lp = linprog(-np.ones(n), A_ub=A, b_ub=ub, bounds=(0, None), method="highs")
    lp_ub = float(-lp.fun) if lp.success else float("nan")

    cons = [(A, lo, ub)]
    nvar = n
    extra_int = []

    def run(cost, label):
        c = np.zeros(nvar)
        c[:len(cost)] = cost
        mats = []
        for M, l, u in cons:
            if M.shape[1] < nvar:
                M = csr_matrix((M.data, M.indices, M.indptr), shape=(M.shape[0], nvar))
            mats.append((M, l, u))
        M = vstack([m[0] for m in mats], format="csr")
        L = np.concatenate([m[1] for m in mats])
        U = np.concatenate([m[2] for m in mats])
        integ = np.r_[np.ones(n), np.zeros(nvar - n)]
        upper = np.r_[np.array([len(reqs[i].lots) for i in opt_req], dtype=float), np.full(nvar - n, np.inf)]
        res = milp(c, integrality=integ, bounds=Bounds(np.zeros(nvar), upper),
                   constraints=LinearConstraint(M, L, U),
                   options={"time_limit": time_limit, "mip_rel_gap": 0.0, "disp": False})
        if res.status != 0:
            raise RuntimeError(f"Rice allocation stage '{label}' not proven optimal: {res.message}")
        x = res.x[:n]
        if np.any(np.abs(x - np.round(x)) > 1e-6):
            raise RuntimeError(f"fractional lot in stage '{label}'")
        return res

    def fix(cost, value, slack=0.0):
        c = np.zeros(nvar)
        c[:len(cost)] = cost
        cons.append((csr_matrix(c.reshape(1, -1)), np.array([value - slack]), np.array([value + slack])))

    timings = {}
    s1 = run(-np.ones(n), "served"); served = int(round(-s1.fun)); fix(np.ones(n), served)
    timings["served"] = round(time.perf_counter() - t0, 2)
    if advance_first:
        s4 = run(white_adv, "milling_advance"); v4 = float(round(s4.fun)); fix(white_adv, v4)
        timings["milling_advance"] = round(time.perf_counter() - t0, 2)
    s2 = run(due, "earliest_due"); v2 = float(round(s2.fun)); fix(due, v2)
    timings["earliest_due"] = round(time.perf_counter() - t0, 2)
    # stage 3: per (product, request week) totals from stage 2 are fixed, then the
    # split over the markets is pulled towards largest-remainder targets
    x2 = np.round(s2.x[:n]).astype(int)
    week_tot = Counter()
    for j, o in enumerate(rp.options):
        r = rp.requests[o.request]
        week_tot[r.product, r.due] += x2[j]
    groups = defaultdict(dict)
    for r in reqs:
        groups[r.product, r.due][r.key] = len(r.lots)
    targets = {}
    short_groups = [g for g, dem in groups.items() if week_tot[g] < sum(dem.values())]
    for g in short_groups:
        targets.update(largest_remainder(int(week_tot[g]), groups[g]))
    tkeys = list(targets)
    if tkeys:
        k = len(tkeys)
        base = n
        nvar = n + 2 * k
        rows, cols, data, lo3, hi3 = [], [], [], [], []
        opt_by_req = defaultdict(list)
        for j, o in enumerate(rp.options):
            opt_by_req[o.request].append(j)
        for i, key in enumerate(tkeys):
            for j in opt_by_req[key]:
                rows.append(i); cols.append(j); data.append(1.0)
            rows.append(i); cols.append(base + i); data.append(-1.0)        # dev+
            rows.append(i); cols.append(base + k + i); data.append(1.0)     # dev-
            lo3.append(targets[key]); hi3.append(targets[key])
        cons.append((coo_matrix((data, (rows, cols)), shape=(k, nvar)).tocsr(), np.array(lo3, float), np.array(hi3, float)))
        for g in short_groups:                                              # keep the week totals
            c = np.zeros(nvar)
            for key in groups[g]:
                for j in opt_by_req[key]:
                    c[j] = 1.0
            cons.append((csr_matrix(c.reshape(1, -1)), np.array([week_tot[g]], float), np.array([week_tot[g]], float)))
        cost3 = np.r_[np.zeros(n), np.ones(2 * k)]
        s3 = run(cost3, "proportional"); v3 = float(s3.fun); fix(cost3, v3, 1e-6)
    else:
        s3, v3 = s2, 0.0
    timings["proportional"] = round(time.perf_counter() - t0, 2)
    if not advance_first:
        s4 = run(white_adv, "milling_advance"); v4 = float(round(s4.fun)); fix(white_adv, v4)
        timings["milling_advance"] = round(time.perf_counter() - t0, 2)
    s5 = run(brown, "brown_kg_weeks")
    timings["brown_kg_weeks"] = round(time.perf_counter() - t0, 2)
    x = np.round(s5.x[:n]).astype(int)
    q = {rp.options[j].key: int(x[j]) for j in range(n) if x[j]}
    got = Counter()
    for j, o in enumerate(rp.options):
        got[o.request] += int(x[j])
    unalloc = {r.key: len(r.lots) - got[r.key] for r in reqs}
    if sum(got.values()) != served:
        raise RuntimeError("stage results disagree")
    return RiceSolution(q, served, unalloc,
                        {"served": served, "sum_due_of_served": v2, "proportional_deviation": v3,
                         "milling_advance_lot_weeks": v4, "brown_kg_weeks": float(s5.fun),
                         "proportional_targets": targets},
                        lp_ub, {"variables": n, "capacity_rows": len(finite), "stage_seconds": timings,
                                "proportional_groups": len(short_groups)})


# ── expansion to the original IDs, placement, ledgers ─────────────────────
def expand(rp: RiceProblem, sol: RiceSolution) -> List[dict]:
    """Original IDs of each request, in market order, get the allocated options
    in (harvest, milling) order; the remaining IDs are unallocated."""
    by_req = defaultdict(list)
    for o in rp.options:
        if sol.quantities.get(o.key):
            by_req[o.request].append(o)
    rows = []
    for r in rp.requests.values():
        lots = iter(r.lots)
        for o in sorted(by_req[r.key], key=lambda o: (o.timing.harvest, o.timing.polish)):
            for _ in range(sol.quantities[o.key]):
                rows.append({"lot_id": next(lots), "product": r.product, "market": r.market,
                             "due": r.due, "status": "assigned", "timing": o.timing})
        for lot in lots:
            rows.append({"lot_id": lot, "product": r.product, "market": r.market, "due": r.due,
                         "status": "unallocated", "timing": None,
                         "reason": "no_feasible_option" if r.key in rp.no_option else "capacity_or_crop"})
    ids = [x["lot_id"] for x in rows]
    if len(ids) != len(set(ids)) or len(ids) != sum(len(r.lots) for r in rp.requests.values()):
        raise RuntimeError("expansion lost or duplicated an original ID")
    return rows


def apply_positions(tree, product: str, rp: RiceProblem, rows: List[dict]) -> int:
    """Rewrite the internal demand positions of one product; market S untouched."""
    from wom.model.plan_node import S, P
    nodes = {n.node_id: n for n in tree.iter_all_nodes(product)}
    for nd in nodes.values():
        if nd.node_type != "leaf_out":
            for w in range(tree.num_weeks()):
                nd.psi4demand[w] = [[], [], [], []]
    placed = 0
    for r in rows:
        if r["product"] != product or r["status"] != "assigned":
            continue
        t, ids = r["timing"], rp.routes[(product, r["market"])].node_ids
        for key, pw, sw in (("field", t.harvest, t.harvest), ("collection", t.collection, t.collection),
                            ("supply_point", t.collection, t.collection),
                            ("warehouse", t.store_arrival, t.store_departure),
                            ("mill", t.polish, t.polish), ("dc", t.dc, t.dc)):
            nodes[ids[key]].psi4demand[pw][P].append(r["lot_id"])
            nodes[ids[key]].psi4demand[sw][S].append(r["lot_id"])
        placed += 1
    return placed


def resource_usage(rp: RiceProblem, sol: RiceSolution) -> Dict[Tuple[str, int], float]:
    load = defaultdict(float)
    for o in rp.options:
        q = sol.quantities.get(o.key, 0)
        if q:
            for rid, w, kg in o.uses:
                load[rid, w] += kg * q
    return dict(load)


def physical_ledger(rp: RiceProblem, rows: List[dict]) -> List[dict]:
    """Weekly stage masses (exact) by product: brown in transit / in the warehouse,
    white in transit / at the market, and the cumulative other output of milling.
    Brown rice leaves the ledger at milling; white rice never repeats its mass."""
    agg = defaultdict(lambda: defaultdict(Fraction))
    for r in rows:
        if r["status"] != "assigned":
            continue
        t, rec = r["timing"], rp.inputs.recipes[r["product"]]
        raw, white = rec.raw_kg_per_lot, rec.white_kg_per_lot
        for w in range(t.harvest, r["due"] + 1):
            if w < t.store_arrival:
                stage, qty = "brown_transit", raw
            elif w < t.store_departure:
                stage, qty = "brown_warehouse", raw
            elif w < t.polish:
                stage, qty = "brown_transit", raw
            elif w < r["due"]:
                stage, qty = "white_transit_or_market", white
            else:
                stage, qty = "sold", white
            other = raw - white if w >= t.polish else Fraction(0)
            if qty + other != raw:
                raise RuntimeError("mass balance failed")
            agg[(r["product"], w)][stage] += qty
            agg[(r["product"], w)]["other_output_cumulative"] += other
    out = []
    for (p, w), st in sorted(agg.items(), key=lambda x: (x[0][0], x[0][1])):
        out.append({"product": p, "week": rp.weeks[w], **{k: float(v) for k, v in st.items()}})
    return out
