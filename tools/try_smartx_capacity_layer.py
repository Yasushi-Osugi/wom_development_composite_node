#!/usr/bin/env python3
"""Build upper-capacity options and two explicit solutions from measured smartx.

Writes new trial models only; requires the frozen baseline measurement first.
Does not launch WOM or change core/master/golden files.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import time

from wom.capacity_layer import Problem, Option, solve_greedy, solve_lp, validate_solution
from wom.capacity_layer.smartx_trial import SmartxAdapter,read_csv
from tools.probe_smartx_bottleneck import BASE_SHA,ROOT,ORIGINAL,check_base,write_json,write_csv,sha


def push_leads(model,baseline):
    nodes=read_csv(baseline/"nodes.csv"); result={}
    for r in read_csv(model/"push_config.csv"):
        nid=next(n["node_id"] for n in nodes if n["product"]==r["sku_id"] and n["node_name"]==r["node_id"])
        if any(int(r.get(k) or 0) for k in ("push_qty_per_week","buffer_lots","pre_build_qty_per_week")):
            raise ValueError("Only demand-anchored Mode 4 supported")
        result[nid]=int(r["push_lead_time_weeks"])
    return result


def declared_hypothesis(adapter,problem,model,shared):
    """Explicit hypothesis, NOT inferred physical capacity.

    CSV's three AssemblyCN SKU profiles are interpreted as product service
    rates. Independent: dedicated lines; shared: one machine-week, use 1/rate.
    Missing profiles exclude those proposed options, rather than defaulting.
    CSV zero here means no product service in THIS hypothesis (not core zero).
    """
    caps=defaultdict(dict)
    for r in read_csv(model/"capacity_plan.csv"):
        if r["node_name"]=="AssemblyCN": caps[r["sku_id"]][adapter.widx[r["week"]]]=float(r["max_supply"])
    newcaps=dict(problem.capacities); options=[]; excluded=defaultdict(int)
    for o in problem.options:
        req=next(r for r in problem.requests if r.key==o.request_key)
        if req.product not in caps: options.append(o); continue
        root=next(n for n in adapter.by_product[req.product] if adapter.nodes[n]["side"]=="inbound" and not adapter.nodes[n]["parent_id"])
        fp=adapter.footprint(req.product,req.market,o.plan_week); w=fp["processed"][root]
        rate=caps[req.product].get(w)
        if rate is None or rate<=0:
            excluded["unknown_profile" if rate is None else "zero_service_rate"]+=1; continue
        rid="hypothesis:AssemblyCN_shared" if shared else "hypothesis:AssemblyCN_line:"+req.product
        if shared:
            newcaps[rid,w]=1.0; coefficient=1.0/rate
        else:
            newcaps[rid,w]=rate; coefficient=1.0
        options.append(Option(o.key,o.request_key,o.plan_week,o.uses+((rid,w,coefficient),)))
    return Problem(problem.requests,options,newcaps,metadata={**problem.metadata,
        "hypothesis":"shared_machine_week" if shared else "dedicated_declared_lines",
        "owner_approval":False,"csv_aliases_only_in_upper_hypothesis":True,
        "zero_service_rate_policy":"explicit_hypothesis_no_production","excluded_options":dict(excluded)})


def export_solution(adapter,problem,solution,out,model,leads):
    dest=out/"solutions"/solution.method
    if dest.exists(): raise RuntimeError("Refusing to overwrite solution")
    dest.mkdir(parents=True); reqs={r.key:r for r in problem.requests}; opts={o.key:o for o in problem.options}
    allocations=[]
    for a in solution.allocations:
        o=opts[a.option_key]; r=reqs[o.request_key]
        allocations.append({"request_key":r.key,"product":r.product,"market":r.market,
            "original_due_week":adapter.weeks[r.due_week],"plan_week":adapter.weeks[o.plan_week],
            "advance_weeks":r.due_week-o.plan_week,"quantity":a.quantity})
    write_csv(dest/"allocations.csv",allocations,list(allocations[0]))
    unmet=[{"request_key":k,"product":reqs[k].product,"market":reqs[k].market,
        "original_due_week":adapter.weeks[reqs[k].due_week],"quantity":q,
        "reason":"not_assigned_within_explicit_prebuild_window"} for k,q in solution.unmet.items() if q]
    write_csv(dest/"unallocated_demand.csv",unmet,["request_key","product","market","original_due_week","quantity","reason"])
    expanded=adapter.expand(problem,solution)
    regenerated=defaultdict(int)
    for r in expanded:
        r["csv_lot_id"]=""
        if r["status"]=="assigned":
            region=r["original_lot_id"].split(":")[1]
            key=r["product"],region,r["plan_week"]; regenerated[key]+=1
            r["csv_lot_id"]=f"{key[0]}:{key[1]}:{key[2]}:{regenerated[key]:05d}"
    write_csv(dest/"lot_assignments.csv.gz",expanded,list(expanded[0]))
    adj=defaultdict(int)
    for a in allocations:
        region=a["request_key"].split(":")[1]; adj[a["product"],region,a["plan_week"]]+=a["quantity"]
    # Explicit zeros retain the complete original ISO horizon, including warmup.
    combinations=sorted({(r["sku_id"],r["region"]) for r in read_csv(model/"demand_forecast.csv")})
    adjusted=[{"sku_id":p,"region":r,"week":w,"quantity":adj[p,r,w]}
        for p,r in combinations for w in adapter.weeks]
    write_csv(dest/"demand_forecast_adjusted.csv",adjusted,["sku_id","region","week","quantity"])
    loads=validate_solution(problem,solution)["resource_load"]
    usage=[{"resource_id":rid,"week":adapter.weeks[w],"capacity":cap,"allocated_load":loads.get((rid,w),0.),
        "is_unbounded_by_explicit_engine_policy":cap is None} for (rid,w),cap in sorted(problem.capacities.items())]
    write_csv(dest/"resource_usage.csv",usage,list(usage[0]))
    write_json(dest/"manifest.json",{"baseline_sha":BASE_SHA,"method":solution.method,"push_leads":leads,
        "problem_metadata":problem.metadata,"solution":{k:v for k,v in asdict(solution).items() if k!="allocations"},
        "request_count":len(problem.requests),"option_count":len(problem.options),
        "original_demand_lots":sum(r.quantity for r in problem.requests),"allocated_original_ids":solution.served,
        "csv_changes_market_plan_dates_and_regenerates_ids":True,"id_adapter_preserves_original_due_dates_and_ids":True})
    # A standalone COPY for the requested CSV-only engine experiment.
    trial=out/"models"/solution.method/"smartx-2027-2029"; trial.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(model,trial); shutil.copy2(dest/"demand_forecast_adjusted.csv",trial/"demand_forecast.csv")
    return dest


def run(out,max_advance):
    check_base(); baseline=out/"raw/baseline"; leads=push_leads(ORIGINAL,baseline)
    adapter=SmartxAdapter(baseline,missing_capacity_policy="explicit_engine_unbounded",push_leads=leads)
    problem=adapter.problem(ORIGINAL,max_advance)
    write_json(out/"analysis/upper_problem_definition.json",{**problem.metadata,
        "baseline_sha":BASE_SHA,"request_count":len(problem.requests),"option_count":len(problem.options),
        "push_leads":leads,"horizon_start":adapter.weeks[0],"horizon_end":adapter.weeks[-1]})
    results=[]
    for name,prob in [("as_implemented",problem),
        ("declared_independent",declared_hypothesis(adapter,problem,ORIGINAL,False)),
        ("declared_shared",declared_hypothesis(adapter,problem,ORIGINAL,True))]:
        for solver in [solve_greedy,solve_lp]:
            start=time.perf_counter(); sol=solver(prob)
            results.append({"hypothesis":name,"method":sol.method,"demand":sum(r.quantity for r in prob.requests),
                "served_integer_lots":sol.served,"unallocated":sum(sol.unmet.values()),
                "advance_lot_weeks":sol.advance_lot_weeks,"relaxation_upper_bound":sol.relaxation_upper_bound,
                "fractional_cells":sol.fractional_cells,"fractional_remainder":sol.fractional_remainder,
                "elapsed_seconds":round(time.perf_counter()-start,3)})
            print("SOLVED",results[-1],flush=True)
            if name=="as_implemented": export_solution(adapter,prob,sol,out,ORIGINAL,leads)
            else:
                dest=out/"hypotheses"/name/sol.method
                write_json(dest/"solution.json",{**prob.metadata,"baseline_sha":BASE_SHA,"result":asdict(sol)})
                loads=validate_solution(prob,sol)["resource_load"]
                write_csv(dest/"shared_usage.csv",[{"resource":rid,"week":adapter.weeks[w],"load":v,"capacity":prob.capacities[rid,w]}
                    for (rid,w),v in sorted(loads.items()) if rid.startswith("hypothesis:")],["resource","week","load","capacity"])
    write_csv(out/"analysis/solver_comparison.csv",results,list(results[0]))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",required=True,type=Path)
    p.add_argument("--max-advance",type=int,default=17)
    a=p.parse_args();run(a.out.resolve(),a.max_advance)


if __name__=="__main__":main()
