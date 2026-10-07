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


def read_csv(path):
    with open(path,encoding="utf-8-sig",newline="") as f: return list(csv.DictReader(f))


class SmartxAdapter:
    def __init__(self, baseline_dir, *, missing_capacity_policy, push_leads):
        if missing_capacity_policy!="explicit_engine_unbounded":
            raise ValueError("This adapter requires explicit acknowledgement of current unset capacities")
        self.baseline=Path(baseline_dir)
        self.push_leads=dict(push_leads)
        self.nodes={r["node_id"]:r for r in read_csv(self.baseline/"nodes.csv")}
        weekly=read_csv(self.baseline/"node_week.csv")
        self.weeks=sorted({r["week"] for r in weekly})
        self.widx={w:i for i,w in enumerate(self.weeks)}
        self.state={(r["node_id"],int(r["week_index"])):r for r in weekly}
        self.products=sorted({r["product"] for r in self.nodes.values()})
        self.by_product={p:[n for n,r in self.nodes.items() if r["product"]==p] for p in self.products}
        self.closed={n:{w for w in range(len(self.weeks)) if self.state[n,w]["is_open"]=="False"} for n in self.nodes}
        self.children=defaultdict(list)
        for nid,r in self.nodes.items():
            if r["parent_id"]: self.children[r["parent_id"]].append(nid)
        for p in self.products:
            ins=[n for n in self.by_product[p] if self.nodes[n]["side"]=="inbound"]
            if any(len(self.children[n])>1 for n in ins): raise ValueError("Branched inbound needs a BOM/Kitting adapter")
            if sum(self.nodes[n]["node_type"]=="leaf_in" for n in ins)!=1: raise ValueError("Exactly one inbound source required")
            if any(int(self.nodes[n]["bom_qty"])!=1 for n in ins): raise ValueError("Physical-unit BOM conversion must be explicit")
        self.capacities={}
        self.warnings=[]
        for nid,r in self.nodes.items():
            if r["plan_mode"]=="push": continue # receipt is unsealed in the current engine
            for w in range(len(self.weeks)):
                text=self.state[nid,w]["processing_limit"]
                self.capacities[nid,w]=None if text=="" else int(float(text))
            if r["side"]=="inbound" and all(self.capacities[nid,w] is None for w in range(len(self.weeks))):
                self.warnings.append({"node_id":nid,"kind":"unset_capacity_not_physical_unlimited",
                    "trial_policy":"explicit_engine_unbounded"})
            if r["side"]=="inbound" and not r["parent_id"]:
                # Backward also clips the root S at that week. This extra
                # envelope constraint is the SAME machine, not extra capacity.
                for w in range(len(self.weeks)):
                    self.capacities["backward_root:"+nid,w]=self.capacities[nid,w]

    def _back(self,w,lt,nid):
        if not self.closed[nid]: return w-lt
        left=lt; v=w-1
        while left>0:
            if v not in self.closed[nid]: left-=1
            v-=1
        return v+1

    def _open(self,nid,w):
        return next((x for x in range(max(w,0),len(self.weeks)) if x not in self.closed[nid]),len(self.weeks))

    def footprint(self,product,market,plan_week,market_due=None):
        """Unit internal demand positions and no-contention receipt/ship weeks.

        Physical capacity is reserved on processing/receipt P, not on planned
        S. This matters when holiday-skipping Backward offsets move arrivals.
        """
        ids=self.by_product[product]
        leaf=next(n for n in ids if self.nodes[n]["node_name"]==market)
        due={leaf:plan_week}; n=leaf
        while self.nodes[n]["parent_id"]:
            parent=self.nodes[n]["parent_id"]; r=self.nodes[n]
            due[parent]=self._back(due[n],int(r["lt_wks"])+int(r["ss_wks"]),parent); n=parent
        ot_root=n
        root=next(n for n in ids if self.nodes[n]["side"]=="inbound" and not self.nodes[n]["parent_id"])
        due[root]=due[ot_root]
        n=root
        chain=[n]
        while self.children[n]:
            child=self.children[n][0]; r=self.nodes[child]
            due[child]=self._back(due[n],int(r["lt_wks"])+int(r["ss_wks"]),child)
            n=child; chain.append(n)
        if min(due.values())<0: return None
        source=chain[-1]
        pushed=next((n for n in chain if self.nodes[n]["plan_mode"]=="push"),None)
        source_p=due[source]
        if pushed:
            if pushed not in self.push_leads: raise ValueError("Missing Mode 4 lead-time definition")
            source_p=due[pushed]-self.push_leads[pushed]
            if source_p<0: return None
            if source_p in self.closed[source]:
                prev=next((w for w in range(source_p-1,-1,-1) if w not in self.closed[source]),None)
                source_p=prev if prev is not None else self._open(source,source_p+1)
        actual={}; processed={}; uses=[]; p_w=source_p
        for nid in reversed(chain):
            r=self.nodes[nid]
            if nid!=source:
                child=self.children[nid][0]; cr=self.nodes[child]
                # Push-buffer handoff uses its lt; normal handoff uses transit.
                transit=int(cr["lt_wks"]) if cr["plan_mode"]=="push" else int(cr["transit_lt_wks"])
                if transit<=0: transit=int(cr["lt_wks"])
                p_w=actual[child]+transit
            if r["plan_mode"]=="push":
                processed[nid]=p_w; actual[nid]=self._open(nid,max(p_w,due[nid]))
            else:
                processed[nid]=self._open(nid,p_w)
                uses.append((nid,processed[nid],1.))
                actual[nid]=processed[nid] if r["plan_mode"]=="push_sub" else self._open(nid,max(processed[nid],due[nid]))
            if not r["parent_id"]: uses.append(("backward_root:"+nid,due[nid],1.))
        actual[ot_root]=max(actual[root],due[ot_root]); processed[ot_root]=actual[root]
        uses.append((ot_root,processed[ot_root],1.))
        path=[]; n=leaf
        while n!=ot_root: path.append(n); n=self.nodes[n]["parent_id"]
        for nid in reversed(path):
            r=self.nodes[nid]; parent=r["parent_id"]
            processed[nid]=self._open(nid,actual[parent]+int(r["lt_wks"]))
            requested=market_due if nid==leaf and market_due is not None else due[nid]
            actual[nid]=self._open(nid,max(processed[nid],requested))
            uses.append((nid,processed[nid],1.))
        if max(max(due.values()),max(processed.values()),max(actual.values()))>=len(self.weeks): return None
        return {"positions":due,"processed":processed,"actual":actual,
            "uses":tuple(uses),"market_week":actual[leaf]}

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
