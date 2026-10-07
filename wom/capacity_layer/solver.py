"""Sparse time-indexed resource allocation; no WOM engine imports.

An option reserves explicitly supplied resource/week coefficients for one
request. Zero capacity really means zero; None is explicitly unbounded.
Missing resource/week keys raise, rather than acquiring silent defaults.
LP maximizes fulfilled quantity then minimizes advance-production lot-weeks.
Integer lots are floored, validated, and any fractional remainder is reported.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
import math

Slot = tuple[str, int]


@dataclass(frozen=True)
class Request:
    key: str
    product: str
    market: str
    due_week: int
    quantity: int


@dataclass(frozen=True)
class Option:
    key: str
    request_key: str
    plan_week: int
    uses: tuple[tuple[str, int, float], ...]


@dataclass
class Problem:
    requests: list[Request]
    options: list[Option]
    capacities: dict[Slot, float | None]
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Allocation:
    option_key: str
    quantity: int


@dataclass
class Solution:
    method: str
    allocations: list[Allocation]
    unmet: dict[str, int]
    served: int
    advance_lot_weeks: int
    relaxation_upper_bound: float | None = None
    fractional_cells: int = 0
    fractional_remainder: float = 0.0
    diagnostics: dict = field(default_factory=dict)


def validate_problem(problem):
    req = {r.key:r for r in problem.requests}
    if len(req)!=len(problem.requests): raise ValueError("Duplicate request key")
    if len({o.key for o in problem.options})!=len(problem.options): raise ValueError("Duplicate option key")
    for r in req.values():
        if r.quantity<0 or int(r.quantity)!=r.quantity: raise ValueError("Whole nonnegative lots required")
    for slot,cap in problem.capacities.items():
        if cap is not None and (not math.isfinite(cap) or cap<0): raise ValueError(f"Invalid capacity {slot}: {cap}")
    for o in problem.options:
        if o.request_key not in req: raise ValueError("Unknown request")
        if o.plan_week>req[o.request_key].due_week: raise ValueError("This trial only proposes on-time/prebuild options")
        if len({(r,w) for r,w,c in o.uses})!=len(o.uses): raise ValueError("Duplicate resource/week in option")
        for r,w,c in o.uses:
            if w<0 or w>req[o.request_key].due_week:
                raise ValueError("Resource use must occur within the horizon and by the original due week")
            if (r,w) not in problem.capacities: raise ValueError(f"Missing capacity {(r,w)}")
            if not math.isfinite(c) or c<=0: raise ValueError("Positive resource coefficients required")
    return req


def _make_solution(problem, method, allocations, **kw):
    req=validate_problem(problem); opts={o.key:o for o in problem.options}; done=defaultdict(int)
    advance=0
    for a in allocations:
        o=opts[a.option_key]; done[o.request_key]+=a.quantity
        advance+=(req[o.request_key].due_week-o.plan_week)*a.quantity
    sol=Solution(method,allocations,{k:r.quantity-done[k] for k,r in req.items()},sum(done.values()),advance,**kw)
    validate_solution(problem,sol); return sol


def validate_solution(problem, solution, tolerance=1e-7):
    req=validate_problem(problem); opts={o.key:o for o in problem.options}
    load=defaultdict(float); served=defaultdict(int)
    for a in solution.allocations:
        if a.option_key not in opts: raise ValueError("Unknown allocation option")
        if a.quantity<=0 or int(a.quantity)!=a.quantity: raise ValueError("Invalid integer allocation")
        o=opts[a.option_key]; served[o.request_key]+=a.quantity
        for r,w,c in o.uses: load[(r,w)]+=c*a.quantity
    for k,r in req.items():
        if served[k]>r.quantity: raise ValueError(f"Overserved request {k}")
        if solution.unmet.get(k)!=r.quantity-served[k]: raise ValueError("Lost demand in unmet table")
    for slot,value in load.items():
        cap=problem.capacities[slot]
        if cap is not None and value>cap+tolerance: raise ValueError(f"Capacity breach {slot}: {value}>{cap}")
    if sum(served.values())!=solution.served: raise ValueError("Inconsistent served count")
    return {"resource_load":dict(load),"demand_balance":True,"capacity_valid":True}


def solve_greedy(problem):
    req=validate_problem(problem); residual=dict(problem.capacities); by_request=defaultdict(list)
    for o in problem.options: by_request[o.request_key].append(o)
    alloc=[]
    # Earliest demand first; latest feasible preceding slot first.
    for r in sorted(req.values(),key=lambda x:(x.due_week,x.product,x.market,x.key)):
        remaining=r.quantity
        for o in sorted(by_request[r.key],key=lambda x:(-x.plan_week,x.key)):
            amount=remaining
            for rid,w,c in o.uses:
                cap=residual[(rid,w)]
                if cap is not None: amount=min(amount,max(0,math.floor((cap+1e-9)/c)))
            if amount:
                alloc.append(Allocation(o.key,amount)); remaining-=amount
                for rid,w,c in o.uses:
                    if residual[(rid,w)] is not None: residual[(rid,w)]-=c*amount
            if not remaining: break
    return _make_solution(problem,"greedy",alloc)


def solve_lp(problem):
    """SciPy/HiGHS LP relaxation, followed by safe whole-lot extraction.

Floored fractional cells are never hidden or labelled an integer optimum.
"""
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import coo_matrix, vstack
    req=validate_problem(problem)
    if not problem.options:
        return _make_solution(problem,"lp",[],relaxation_upper_bound=0.0)
    req_rows={k:i for i,k in enumerate(req)}
    finite={k:len(req_rows)+i for i,(k,c) in enumerate((x for x in problem.capacities.items() if x[1] is not None))}
    rows=[]; cols=[]; data=[]
    for j,o in enumerate(problem.options):
        rows.append(req_rows[o.request_key]); cols.append(j); data.append(1.)
        for r,w,c in o.uses:
            if (r,w) in finite: rows.append(finite[(r,w)]); cols.append(j); data.append(c)
    n=len(problem.options)
    A=coo_matrix((data,(rows,cols)),shape=(len(req_rows)+len(finite),n)).tocsr()
    b=np.zeros(A.shape[0])
    for k,i in req_rows.items(): b[i]=req[k].quantity
    for k,i in finite.items(): b[i]=problem.capacities[k]
    settings={"primal_feasibility_tolerance":1e-8,"dual_feasibility_tolerance":1e-8}
    first=linprog(-np.ones(n),A_ub=A,b_ub=b,bounds=(0,None),method="highs",options=settings)
    if not first.success: raise RuntimeError(f"LP throughput failed: {first.message}")
    best=float(first.x.sum())
    costs=np.array([req[o.request_key].due_week-o.plan_week for o in problem.options],dtype=float)
    second=linprog(costs,A_ub=A,b_ub=b,A_eq=coo_matrix(np.ones((1,n))).tocsr(),
        b_eq=np.array([best]),bounds=(0,None),method="highs",options=settings)
    if not second.success: raise RuntimeError(f"LP advance-production failed: {second.message}")
    vector=second.x; alloc=[]; fractions=0; remainder=0.
    for j,x in enumerate(vector):
        nearest=round(float(x)); q=nearest if abs(float(x)-nearest)<1e-7 else math.floor(float(x))
        if abs(float(x)-q)>1e-7: fractions+=1; remainder+=float(x)-q
        if q: alloc.append(Allocation(problem.options[j].key,q))
    return _make_solution(problem,"lp",alloc,relaxation_upper_bound=best,
        fractional_cells=fractions,fractional_remainder=remainder,
        diagnostics={"first_status":first.message,"second_status":second.message,
            "continuous_advance_lot_weeks":float(second.fun),"variable_count":n,"constraint_count":A.shape[0]})
