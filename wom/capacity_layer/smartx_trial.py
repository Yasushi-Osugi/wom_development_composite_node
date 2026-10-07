"""Explicit, bounded smartx adapter for the experimental resource solver.

Only serial, single-source trees are supported by this adapter. The generic
solver itself accepts multi-resource and seasonal profiles. No engine writes.
CSV retiming proposes service dates; the optional POST_BACKWARD adapter keeps
the original market demands/IDs while scheduling internal demand positions.
"""
from __future__ import annotations
import csv
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from .solver import Request, Option, Problem, validate_solution
from .serial_adapter import SerialLineAdapter


def read_csv(path):
    with open(path,encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))


class SmartxAdapter(SerialLineAdapter):
    """CSV-backed loader of the measured baseline (nodes.csv, node_week.csv).

    The footprint logic lives in serial_adapter.SerialLineAdapter (production
    version, RequestLetter_GenerationLine_UpperLayer); this class only reads
    the exported files of Astra's measurement and keeps its problem/expand/
    apply_positions signatures for the trial tools.
    """
    def __init__(self, baseline_dir, *, missing_capacity_policy, push_leads):
        if missing_capacity_policy!="explicit_engine_unbounded":
            raise ValueError("This adapter requires explicit acknowledgement of current unset capacities")
        self.baseline=Path(baseline_dir)
        rows={r["node_id"]:r for r in read_csv(self.baseline/"nodes.csv")}
        weekly=read_csv(self.baseline/"node_week.csv")
        weeks=sorted({r["week"] for r in weekly})
        nodes={nid:{**r,"lt_wks":int(r["lt_wks"]),"transit_lt_wks":int(r["transit_lt_wks"] or 0),
                    "ss_wks":int(r["ss_wks"]),"bom_qty":int(r["bom_qty"])} for nid,r in rows.items()}
        state={(r["node_id"],int(r["week_index"])):{
                   "processing_limit":None if r["processing_limit"]=="" else int(float(r["processing_limit"])),
                   "is_open":r["is_open"]!="False"} for r in weekly}
        super().__init__(nodes,state,weeks,push_leads=push_leads)
        self.warnings=[{"node_id":n,"kind":"unset_capacity_not_physical_unlimited",
                        "trial_policy":"explicit_engine_unbounded"}
                       for n in self.unset_nodes if self.nodes[n]["side"]=="inbound"]

    def problem(self,model_dir,max_advance):
        demand=defaultdict(int)
        for r in read_csv(Path(model_dir)/"demand_forecast.csv"):
            demand[r["sku_id"],r["region"],r["week"]]+=int(r["quantity"])
        leafs={}
        for nid,r in self.nodes.items():
            if r["node_type"]=="leaf_out":
                # IDs encode the region; this is the builder's documented format.
                leafs[r["product"],nid.split(":")[2]]=r["node_name"]
        requests=[]; options=[]
        for (prod,region,week),q in sorted(demand.items()):
            if not q: continue
            if (prod,region) not in leafs: raise ValueError("Demand has no market")
            dw=self.widx[week]; market=leafs[prod,region]; key=f"{prod}:{region}:{week}"
            req=Request(key,prod,market,dw,q); requests.append(req)
            for pw in range(max(0,dw-max_advance),dw+1):
                fp=self.footprint(prod,market,pw)
                if fp is None or fp["market_week"]>dw: continue
                options.append(Option(f"{key}@{pw}",key,pw,fp["uses"]))
        return Problem(requests,options,dict(self.capacities),metadata={
            "adapter":"smartx_serial_receipt_slots_v0.1","max_advance_weeks":max_advance,
            "original_market_due_preserved_by_id_adapter":True,"warnings":self.warnings,
            "resource_unit":"one demand-set lot; cpu_size=1 and bom_qty=1",
            "shared_capacity":"per-product, as implemented; not a claim of independent physical equipment"})

    def expand(self,problem,solution):
        """Allocate original deterministic demand IDs to plan slots; never mint IDs."""
        validate_solution(problem,solution)
        reqs={r.key:r for r in problem.requests}; opts={o.key:o for o in problem.options}
        grouped=defaultdict(list)
        for a in solution.allocations: grouped[opts[a.option_key].request_key].append(a)
        rows=[]
        for key,r in reqs.items():
            seq=1
            for a in sorted(grouped[key],key=lambda x:(-opts[x.option_key].plan_week,x.option_key)):
                o=opts[a.option_key]
                for _ in range(a.quantity):
                    rows.append({"original_lot_id":f"{key}:{seq:05d}","product":r.product,"market":r.market,
                        "original_due_week":self.weeks[r.due_week],"original_due_index":r.due_week,
                        "plan_week":self.weeks[o.plan_week],"plan_index":o.plan_week,"status":"assigned"})
                    seq+=1
            for _ in range(solution.unmet[key]):
                rows.append({"original_lot_id":f"{key}:{seq:05d}","product":r.product,"market":r.market,
                    "original_due_week":self.weeks[r.due_week],"original_due_index":r.due_week,
                    "plan_week":"","plan_index":"","status":"unallocated"}); seq+=1
        return rows

    def apply_positions(self,tree,product,assignments):
        """Opt-in trial hook after Backward; market S and IDs remain untouched.

        Runs only in an isolated measurement process, never registered by WOM.
        Does not alter capacities, modes or Forward logic. The generic engine
        must still independently verify the offered schedule.
        """
        from wom.model.plan_node import S,CO,I,P
        by_id={n.node_id:n for n in tree.iter_all_nodes(product)}
        for nd in by_id.values():
            if nd.node_type=="leaf_out": continue
            for w in range(len(self.weeks)): nd.psi4demand[w]=[[],[],[],[]]
        rows=(r for r in assignments if r["product"]==product and r["status"]=="assigned")
        for r in rows:
            fp=self.footprint(product,r["market"],int(r["plan_index"]))
            if fp is None: raise RuntimeError("Invalid allocated footprint")
            for nid,w in fp["positions"].items():
                nd=by_id[nid]
                if nd.node_type=="leaf_out": continue
                nd.psi4demand[w][S].append(r["original_lot_id"])
                nd.psi4demand[w][P].append(r["original_lot_id"])
