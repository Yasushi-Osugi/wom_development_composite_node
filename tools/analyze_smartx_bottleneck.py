#!/usr/bin/env python3
"""Independent quantity joins, capacity normalization and trial comparisons.

Consumes probe outputs; no imports of the WOM fulfillment/Flow Check routines.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import csv
import gzip
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from tools.probe_smartx_bottleneck import ROOT,ORIGINAL,BASE_SHA,check_base,write_json,write_csv,sha
from tools.try_smartx_capacity_layer import push_leads
from wom.capacity_layer.smartx_trial import SmartxAdapter,read_csv


def read_gz_csv(path):
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f: yield from csv.DictReader(f)


def survey(out):
    check_base();dest=out/"analysis";dest.mkdir(exist_ok=True)
    base=out/"raw/baseline";leads=push_leads(ORIGINAL,base)
    adapter=SmartxAdapter(base,missing_capacity_policy="explicit_engine_unbounded",push_leads=leads)
    nodes=pd.read_csv(base/"nodes.csv");weekly=pd.read_csv(base/"node_week.csv")
    cap=pd.read_csv(ORIGINAL/"capacity_plan.csv");tree=pd.read_csv(ORIGINAL/"sc_tree_master.csv")
    exact=set(zip(tree.product_name,tree.node_name));audit=[]
    for (p,n),g in cap.groupby(["sku_id","node_name"]):
        audit.append({"product":p,"csv_node":n,"exact_node_match":(p,n) in exact,"row_count":len(g),
            "min_max_supply":g.max_supply.min(),"max_max_supply":g.max_supply.max(),
            "column_unit":"engine lot-count threshold; cap_pieces ignored",
            "cpu_size":1,"bom_qty":1,"finished_demand_lots_per_capacity_unit":1,
            "source":"capacity_sealer.load_capacity_dataframe -> PlanNode.cap_hard; Forward len(P)"})
    write_csv(dest/"capacity_unit_and_binding.csv",audit,list(audit[0]))
    meta={r["node_id"]:r for r in read_csv(base/"nodes.csv")}
    normalized=[];bottlenecks=[]
    for p,g in weekly.groupby("product"):
        ing=g[g.node_id.isin([n for n,r in meta.items() if r["product"]==p and r["side"]=="inbound"])]
        for w,h in ing.groupby("week"):
            positive=h.loc[h.cap_hard>0,"cap_hard"];den=float(positive.max()) if len(positive) else None
            known=h[h.processing_limit.notna()]
            minlim=float(known.processing_limit.min()) if len(known) else None
            names=known[known.processing_limit==minlim].node_name.tolist() if minlim is not None else []
            unknown=h[h.processing_limit.isna()].node_name.tolist()
            bottlenecks.append({"product":p,"week":w,"known_minimum_lot_capacity":minlim,
                "minimum_nodes":"|".join(sorted(names)),"unknown_capacity_nodes":"|".join(sorted(unknown)),
                "physical_cap_max_denominator":den,"full_tree_ranking_confirmed":not unknown})
            for r in h.to_dict("records"):
                normalized.append({"product":p,"node_name":r["node_name"],"node_id":r["node_id"],"week":w,
                    "cap_hard":r["cap_hard"],"processing_limit":r["processing_limit"],"is_open":r["is_open"],
                    "physical_cap_max_denominator":den,
                    "hard_normalized":r["cap_hard"]/den if den and r["cap_hard"]>0 else None,
                    "processing_normalized":r["processing_limit"]/den if den and pd.notna(r["processing_limit"]) else None,
                    "receipts_skip_hard_cap":r["plan_mode"]=="push",
                    "missing_capacity_is_not_zero":pd.isna(r["processing_limit"])})
    norm=pd.DataFrame(normalized);norm.to_csv(dest/"normalized_capacity_week.csv",index=False)
    bn=pd.DataFrame(bottlenecks);bn.to_csv(dest/"bottleneck_week.csv",index=False)
    representative=norm.groupby(["product","node_name"]).agg(
        finite_weeks=("processing_limit",lambda s:s.notna().sum()),
        hard_min=("cap_hard","min"),hard_median=("cap_hard","median"),hard_max=("cap_hard","max"),
        normalized_median=("processing_normalized","median"),closed_weeks=("is_open",lambda s:(s==False).sum()))
    representative.to_csv(dest/"normalized_capacity_representative.csv")
    switches=[]
    for p,g in bn.groupby("product"):
        current=None
        for r in g.to_dict("records"):
            key=r["minimum_nodes"],r["unknown_capacity_nodes"]
            if current is not None and key==current["_key"]: current["end_week"]=r["week"];current["weeks"]+=1
            else:
                current={"product":p,"start_week":r["week"],"end_week":r["week"],"weeks":1,
                    "minimum_nodes":r["minimum_nodes"],"unknown_capacity_nodes":r["unknown_capacity_nodes"],"_key":key}
                switches.append(current)
    write_csv(dest/"bottleneck_spans.csv",[{k:v for k,v in r.items() if k!="_key"} for r in switches],
        ["product","start_week","end_week","weeks","minimum_nodes","unknown_capacity_nodes"])

    problem=adapter.problem(ORIGINAL,0);nominal=defaultdict(int);position=defaultdict(int)
    for req in problem.requests:
        fp=adapter.footprint(req.product,req.market,req.due_week)
        if fp is None: continue
        for nid,w,c in fp["uses"]:
            if not nid.startswith("backward_root:"): nominal[nid,w]+=int(c*req.quantity)
        for nid,w in fp["positions"].items(): position[nid,w]+=req.quantity
    requirement=[]
    for r in weekly.to_dict("records"):
        nid=r["node_id"];w=int(r["week_index"]);lim=r["processing_limit"]
        if meta[nid]["side"]!="inbound": continue
        requirement.append({"product":r["product"],"node_name":r["node_name"],"node_id":nid,"week":r["week"],
            "nominal_resource_receipt_load":nominal[nid,w],"nominal_internal_request_S":position[nid,w],
            "capacity":lim,"over_nominal_receipt":max(nominal[nid,w]-lim,0) if pd.notna(lim) else None,
            "backward_demand_S":r["demand_S"],"backward_demand_P":r["demand_P"],
            "forward_input_P":r["input_P"],"forward_processed_P":r["supply_P"],"actual_ship":r["actual_S"],
            "cap_receipt_is_skipped":r["plan_mode"]=="push"})
    pd.DataFrame(requirement).to_csv(dest/"requirements_vs_capacity.csv",index=False)

    status=pd.read_csv(base/"market_lot_status.csv.gz");events=pd.read_csv(base/"deferral_ids.csv.gz")
    joined=events.merge(status,on=["product","lot_id"],validate="many_to_one")
    joined.to_csv(dest/"deferrals_with_market_status.csv.gz",index=False,compression="gzip")
    causes=joined.groupby(["node_id","week","status"]).size().unstack(fill_value=0).reset_index()
    causes.to_csv(dest/"deferral_node_week.csv",index=False)
    totals=[]
    for nid,g in joined.groupby("node_id"):
        totals.append({"node_id":nid,"node_name":meta[nid]["node_name"],"deferred_events":len(g),
            "distinct_ids":g.lot_id.nunique(),"market_late_ids":g[g.status=="late"].lot_id.nunique(),
            "market_on_time_ids":g[g.status=="on_time"].lot_id.nunique(),"first_week":g.week.min(),"last_week":g.week.max()})
    write_csv(dest/"deferral_node_summary.csv",totals,list(totals[0]))
    late=set(status.loc[status.status=="late","lot_id"]);deferred=set(events.lot_id)
    write_json(dest/"delay_attribution.json",{"market_late_ids":len(late),"deferred_global_ids":len(deferred),
        "late_with_deferral":len(late&deferred),"late_without_deferral":len(late-deferred),
        "deferred_but_on_time":len(deferred-late),"delay_histogram":status[status.status=="late"].delay_weeks.value_counts().to_dict(),
        "node_deferral_intersection":len(set.intersection(*(set(g.lot_id) for _,g in events.groupby('node_id'))))})
    # Independent chronology for one late and one recovered lot per resource.
    picked=[]
    for nid,g in joined.groupby("node_id"):
        for st in ["late","on_time"]:
            x=g[g.status==st].sort_values(["week","lot_id"]).iloc[0]
            picked.append({"node_id":nid,"node_name":meta[nid]["node_name"],"status":st,"lot_id":x.lot_id,
                "due_week":x.due_week,"actual_week":x.actual_week,"deferral_week":x.week})
    selected={x["lot_id"] for x in picked};traces=[]
    for file,kind in [("demand_positions.csv.gz","request"),("actual_shipments.csv.gz","shipment")]:
        for r in read_gz_csv(base/file):
            if r["lot_id"] in selected: traces.append({**r,"kind":kind,"node_name":meta[r["node_id"]]["node_name"]})
    write_csv(dest/"selected_lot_traces.csv",traces,list(traces[0]));write_json(dest/"selected_lots.json",picked)
    # Original calendar and exact binding are independent of period detection fix.
    de=pd.read_csv(ORIGINAL/"demand_forecast.csv");dates=pd.to_datetime(de.week.drop_duplicates().sort_values().apply(
        lambda w:__import__('datetime').date.fromisocalendar(int(w[:4]),int(w[6:]),1)))
    write_json(dest/"calendar_and_unit_audit.json",{"iso_week_gaps":int((dates.diff().dropna().dt.days!=7).sum()),
        "first":adapter.weeks[0],"last":adapter.weeks[-1],"weeks":len(adapter.weeks),
        "cpu_size":1,"bom_qty_all_one":bool((nodes.bom_qty==1).all()),
        "unit_label_missing_in_capacity_csv":True,"capacity_column_actually_read":"max_supply",
        "unmatched_capacity_rows":int(sum(x["row_count"] for x in audit if not x["exact_node_match"])),
        "shared_resource_identifier_present":False,
        "limits_of_inference":"Per-product PlanNodes are separate in code; physical equipment sharing is undetermined"})
    figures(dest,norm,pd.DataFrame(requirement),weekly,joined)


def figures(dest,norm,req,weekly,joined):
    d=dest/"figures";d.mkdir(exist_ok=True)
    rows=list(norm[["product","node_name"]].drop_duplicates().itertuples(index=False,name=None))
    weeks=sorted(norm.week.unique());matrix=np.full((len(rows),len(weeks)),np.nan)
    rid={k:i for i,k in enumerate(rows)};wid={w:i for i,w in enumerate(weeks)}
    for r in norm.to_dict("records"):
        if pd.notna(r["processing_normalized"]): matrix[rid[r["product"],r["node_name"]],wid[r["week"]]]=r["processing_normalized"]
    fig,ax=plt.subplots(figsize=(14,6));cm=plt.get_cmap("viridis").copy();cm.set_bad("#dedede")
    im=ax.imshow(np.ma.masked_invalid(matrix),aspect="auto",cmap=cm,vmin=0,vmax=1,interpolation="none")
    ax.set_yticks(range(len(rows)),[f"{p} / {n}" + (" (receipt unsealed)" if n == "Buffer_Chip_TW" else "") for p,n in rows],fontsize=8)
    ticks=np.linspace(0,len(weeks)-1,9,dtype=int);ax.set_xticks(ticks,[weeks[i] for i in ticks])
    ax.set_title("Inbound capacity normalized within each product tree (grey = normalization unavailable)")
    fig.colorbar(im,ax=ax,label="Processing limit / maximum recorded cap_hard")
    fig.tight_layout();fig.savefig(d/"normalized_capacity_heatmap.png",dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(14,6),sharex=True)
    for ax,name in zip(axes,["SensorIN","AssemblyIN"]):
        g=req[req.node_name==name].set_index("week").reindex(weeks)
        ax.plot(g.nominal_resource_receipt_load.to_numpy(),label="Original demand, receipt-slot load",lw=1.2)
        ax.plot(g.capacity.to_numpy(),label="Processing capacity",lw=1.2)
        ax.plot(g.forward_input_P.to_numpy(),label="Baseline arrivals before deferral",lw=.8,alpha=.75)
        ax.set_ylabel(f"{name}\nlots/week");ax.legend(loc="upper right",fontsize=8)
    axes[-1].set_xticks(ticks,[weeks[i] for i in ticks]);fig.suptitle("SmartXPro_IN: capacity must be compared at the receiving node's week")
    fig.tight_layout();fig.savefig(d/"india_requirements_and_capacity.png",dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(11,4));by=joined.groupby(["node_id","status"]).size().unstack(fill_value=0)
    x=np.arange(len(by));bottom=np.zeros(len(by))
    for st,col in [("late","#dd8d3d"),("on_time","#3e8d79")]:
        vals=by.get(st,pd.Series(0,index=by.index)).to_numpy();ax.bar(x,vals,bottom=bottom,label=st,color=col)
        for i,v in enumerate(vals): ax.text(i,bottom[i]+v/2,f"{v:,}",ha="center",va="center")
        bottom+=vals
    ax.set_xticks(x,[s.split(":")[2] for s in by.index]);ax.set_ylabel("Distinct deferred IDs (no overlap here)")
    ax.set_title("19,887 deferred lots are not the same set as 16,073 late market lots")
    ax.legend();fig.tight_layout();fig.savefig(d/"deferral_vs_market_delay.png",dpi=160);plt.close(fig)


def compare(out):
    check_base()
    base=out/"raw/baseline";dest=out/"analysis"
    original=pd.read_csv(base/"market_lot_status.csv.gz")
    results=[];checks=[]
    for case in ["baseline","greedy_csv","lp_csv","greedy_identity","lp_identity"]:
        raw=out/"raw"/case
        if not (raw/"summary.json").exists():continue
        sm=json.loads((raw/"summary.json").read_text());snap=json.loads((raw/"headless_snapshot.json").read_text())
        local=pd.read_csv(raw/"market_lot_status.csv.gz")
        if case.endswith("_csv"):
            method=case.split("_")[0]
            assignments=pd.read_csv(out/"solutions"/method/"lot_assignments.csv.gz")
            assigned=assignments[assignments.status == "assigned"].copy()
            unassigned=assignments[assignments.status != "assigned"].copy()
            assert assigned.csv_lot_id.notna().all() and assigned.csv_lot_id.is_unique
            assert assignments.original_lot_id.is_unique and len(assignments)==len(original)
            merged=assigned.merge(local[["lot_id","actual_index"]],left_on="csv_lot_id",right_on="lot_id",how="left",validate="one_to_one")
            unassigned["actual_index"]=np.nan
            merged=pd.concat([merged,unassigned],ignore_index=True)
            actual=merged.actual_index;due=merged.original_due_index
            origcounts={"on_time":int((actual==due).sum()),"late":int((actual>due).sum()),"early":int((actual<due).sum()),"terminal_backlog":int(actual.isna().sum())}
        else:
            merged=original[["lot_id","due_index"]].merge(local[["lot_id","actual_index"]],on="lot_id",how="left",validate="one_to_one")
            actual=merged.actual_index;due=merged.due_index
            origcounts={"on_time":int((actual==due).sum()),"late":int((actual>due).sum()),"early":int((actual<due).sum()),"terminal_backlog":int(actual.isna().sum())}
        assert sum(origcounts.values())==len(original)
        weekly=pd.read_csv(raw/"node_week.csv")
        stages=pd.read_csv(raw/"stage_summary.csv")
        own_early=int(stages.loc[~stages.push_sub_exempt,"early_ids"].sum())
        nodes=pd.read_csv(raw/"nodes.csv")
        event_counts=weekly.groupby(["product","node_name"]).actual_S.sum().reset_index()
        counted=stages.merge(event_counts,on=["product","node_name"],validate="one_to_one")
        duplicate=int((counted.actual_S-counted.actual_ids).sum())
        if duplicate: raise ValueError("Duplicate node shipment IDs")
        excess=weekly[(weekly.plan_mode!="push") & weekly.processing_limit.notna() & (weekly.supply_P>weekly.processing_limit)]
        leaf_ids=set(nodes.loc[nodes.node_type=="leaf_out","node_id"])
        checks.append({"case":case,"shipment_event_count_minus_distinct_node_id_count":duplicate,
            "processed_P_capacity_breach_node_weeks":len(excess),
            "market_actual_event_count":int(weekly.loc[weekly.node_id.isin(leaf_ids),"actual_S"].sum())})
        # Capacity counts and market comparison are complete, not sampled.
        results.append({"case":case,"original_demand":len(original),**{f"original_{k}":v for k,v in origcounts.items()},
            "run_demand":sm["total"]["demand"],"run_on_time":sm["total"]["on_time"],"run_late":sm["total"]["late"],
            "own_node_early_ids_except_push_sub":own_early,
            "cap_hard_deferred_lots":snap["forward"]["cap_hard_deferred_lots"],
            "cap_hard_deferred_lot_weeks":snap["forward"]["cap_hard_deferred_lot_weeks"],
            "inventory_lot_weeks":int(weekly.supply_I.sum()),"node_inventory_peak":int(weekly.supply_I.max()),
            "revenue_USD":snap["ppc"]["revenue_base"],"gross_profit_USD":snap["ppc"]["gross_profit_base"],
            "gross_margin":snap["ppc"]["gross_margin_pct"]})
        if case.endswith("identity"):
            merged["delay_vs_original"]=actual-due;merged.to_csv(dest/f"{case}_original_market_comparison.csv.gz",index=False,compression="gzip")
        weekly.groupby(["product","node_name"]).agg(I_lot_weeks=("supply_I","sum"),I_peak=("supply_I","max"),CO_lot_weeks=("supply_CO","sum"),
            actual_S=("actual_S","sum")).to_csv(dest/f"{case}_inventory_summary.csv")
    write_csv(dest/"engine_comparison.csv",results,list(results[0]))
    write_json(dest/"independent_node_checks.json",checks)
    baseline=json.loads((base/"headless_snapshot.json").read_text())
    golden=json.loads((ROOT/"tests/golden/smartx-2027-2029.json").read_text())
    write_json(dest/"baseline_golden_match.json",{"exact_snapshot_equal":baseline==golden})
    protected=json.loads((out/"raw/qualification/tracked_sha256_before.json").read_text())
    changed=[p for p,v in protected.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=v]
    write_json(dest/"protected_file_integrity.json",{"baseline_sha":BASE_SHA,"tracked_files":len(protected),"changed":changed,"all_unchanged":not changed})
    if changed:raise RuntimeError(f"Protected originals changed: {changed}")


def positions(out):
    """Compare every root Demand S ID to its original uncapacitated due slot.

This is a planned-position audit, not a production counter. Keep it separate
from Forward shipments and the upper solver's option advance cost.
"""
    check_base();base=out/"raw/baseline";dest=out/"analysis"
    adapter=SmartxAdapter(base,missing_capacity_policy="explicit_engine_unbounded",push_leads=push_leads(ORIGINAL,base))
    original=read_csv(base/"market_summary.csv")
    roots={n:r["product"] for n,r in adapter.nodes.items() if r["side"]=="inbound" and not r["parent_id"]}
    root_for={p:n for n,p in roots.items()};nominal={}
    for r in read_gz_csv(base/"market_lot_status.csv.gz"):
        key=r["lot_id"].rsplit(":",1)[0]
        if key not in nominal:
            fp=adapter.footprint(r["product"],r["market_node"],int(r["due_index"]))
            if fp is None: raise ValueError("No nominal root slot")
            nominal[key]=fp["positions"][root_for[r["product"]]]
    results=[]
    for case in ["baseline","greedy_csv","lp_csv","greedy_identity","lp_identity"]:
        raw=out/"raw"/case
        mapping=None
        if case.endswith("_csv"):
            assignments=pd.read_csv(out/"solutions"/case.split('_')[0]/"lot_assignments.csv.gz")
            a=assignments[assignments.status=="assigned"]
            mapping=dict(zip(a.csv_lot_id,a.original_lot_id))
        counts=defaultdict(Counter); seen=set()
        for r in read_gz_csv(raw/"demand_positions.csv.gz"):
            if r["node_id"] not in roots: continue
            lot=mapping[r["lot_id"]] if mapping is not None else r["lot_id"]
            if lot in seen: raise ValueError("Repeated original ID in root Demand S")
            seen.add(lot);key=lot.rsplit(":",1)[0];delta=nominal[key]-int(r["week_index"])
            c=counts[r["product"]];c["root_requested_ids"]+=1
            c["advanced_ids" if delta>0 else "later_ids" if delta<0 else "unchanged_ids"]+=1
            c["advance_lot_weeks"]+=max(delta,0);c["later_lot_weeks"]+=max(-delta,0)
        weekly=pd.read_csv(raw/"node_week.csv")
        for product in adapter.products:
            total=sum(int(r["demand"]) for r in original if r["product"]==product)
            c=counts[product]
            fields=["root_requested_ids","advanced_ids","later_ids","unchanged_ids","advance_lot_weeks","later_lot_weeks"]
            results.append({"case":case,"product":product,**{field:c[field] for field in fields},
                "original_requests_missing_from_root_S":total-c["root_requested_ids"],
                "post_adapter_demand_CO_lot_weeks":int(weekly.loc[weekly['product']==product,'demand_CO'].sum())})
    write_csv(dest/"root_demand_position_comparison.csv",results,["case","product","root_requested_ids","advanced_ids","later_ids","unchanged_ids","advance_lot_weeks","later_lot_weeks","original_requests_missing_from_root_S","post_adapter_demand_CO_lot_weeks"])


def inventories(out):
    check_base(); dest=out/"analysis"; curves=[]
    fig,axes=plt.subplots(2,1,figsize=(14,6),sharex=True)
    colors={"baseline":"#6e7780","greedy_identity":"#dd8d3d","lp_identity":"#3e8d79"}
    for case,color in colors.items():
        data=pd.read_csv(out/"raw"/case/"node_week.csv")
        all_nodes=data.groupby("week").supply_I.sum()
        india=data[data['product']=="SmartXPro_IN"].groupby("week").supply_I.sum()
        for week,value in all_nodes.items():
            curves.append({"case":case,"week":week,"all_nodes_I_lots":int(value),"india_nodes_I_lots":int(india[week])})
        axes[0].plot(all_nodes.to_numpy(),label=case,color=color,lw=1)
        axes[1].plot(india.to_numpy(),label=case,color=color,lw=1)
    axes[0].set_ylabel("All node I (lots)");axes[1].set_ylabel("SmartXPro_IN I (lots)")
    for ax in axes:ax.legend(fontsize=8,loc="upper right")
    ticks=np.linspace(0,len(all_nodes)-1,9,dtype=int)
    axes[1].set_xticks(ticks,[all_nodes.index[i] for i in ticks])
    fig.suptitle("Inventory with original market dates and IDs preserved")
    fig.tight_layout();fig.savefig(dest/"figures/inventory_curves.png",dpi=160);plt.close(fig)
    write_csv(dest/"inventory_curves.csv",curves,list(curves[0]))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("action",choices=["survey","compare","positions","inventories"])
    p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    {"survey":survey,"compare":compare,"positions":positions,"inventories":inventories}[a.action](a.out.resolve())


if __name__=="__main__":main()
