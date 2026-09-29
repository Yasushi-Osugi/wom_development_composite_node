#!/usr/bin/env python3
"""Read-only PPC entry measurement, pinned e747936. No source/golden writes.

Usage: python tools/probe_ppc_entry.py --repo PATH --out NEW_OUTPUT_DIR
P1 runs all 16 cases first; detailed P2/P3/P4 follow for the two main cases.
Model files are copied; warmup and allocation handoff write only to copies.
Monkeypatches observe/capture results and are restored by ExitStack.
"""
from __future__ import annotations
import argparse
import collections
import contextlib
import copy
import csv
import dataclasses
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import traceback
from unittest.mock import patch

BASE = 'e74793699834483c9c7cad8337b4b0d464517e01'
MAIN = {'Cookie-jp-2026', 'soysauce-jpy-2027-alloc__P_opt800'}

def serializable(obj):
    if isinstance(obj, dict):
        return {repr(k) if isinstance(k, tuple) else k:serializable(v) for k,v in obj.items()}
    if isinstance(obj, (list,tuple)):
        return [serializable(v) for v in obj]
    return obj

def dump(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(serializable(obj), ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')

def jsonl(path, rows):
    with Path(path).open('w', encoding='utf-8', newline='\n') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str)+'\n')

def csvout(path, rows):
    rows = list(rows)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        if keys:
            w=csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)

def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob('*')) if p.is_file()}

def sales_map(tree, weeks, kwargs):
    """Independent source-row mapping; asserted against observed bridge output."""
    from wom.ppc.ppc_psi_bridge import _DEFAULT_CHANNEL_MAP, _region_to_channel
    mapping=dict(_DEFAULT_CHANNEL_MAP)
    mapping.update({k.upper():v for k,v in (kwargs.get('channel_map') or {}).items()})
    prods=kwargs.get('product_id_map') or {}
    sources=[]; mappings=[]
    for product in tree.products:
        for n in tree.iter_all_nodes(product):
            if n.node_type!='leaf_out': continue
            channel=n.node_name if kwargs.get('use_node_name') else _region_to_channel(n.node_id.split(':')[2],mapping)
            mappings.append({'source_product':product,'product_id':prods.get(product,product),
                             'node_id':n.node_id,'channel':channel})
            for wi,w in enumerate(weeks):
                if n.psi4supply[wi][0]:
                    sources.append((product,n,wi,channel,prods.get(product,product)))
    return sources,mappings

def run_case(repo, out, case, plugins, popt=False, golden=None):
    import pandas as pd
    import wom.engine.forward_planner as fp
    import wom.engine.backward_planner as bp
    import wom.ppc.ppc_runner as runner
    import wom.ppc.__main__ as ppcmain
    from wom.ppc.ppc_engine import PPCSimulationEngine
    from tools import run_headless_from_folder as headless
    target=out/case; target.mkdir(parents=True,exist_ok=True)
    cap={'actual':{},'opening':{},'ot_pull':{},'bwd':{}}
    srcname='soysauce-jpy-2027-alloc' if popt else case
    tmp=tempfile.TemporaryDirectory(prefix='wom_ppc_entry_')
    model=Path(tmp.name)/srcname
    shutil.copytree(repo/'data/sample'/srcname,model)
    dump(target/'input_hashes_before.json',hashes(model))
    demand_file='demand_forecast.csv'
    if popt:
        from tools.run_planning_loop import _scenario_blocks
        from wom.allocation.merit_order import true_continuous_optimum
        from wom.allocation.handoff import write_demand_for_allocation
        blocks,tp,sc=_scenario_blocks(str(model),'s1_base',None)
        opt=true_continuous_optimum(blocks,sc,800.0,transfer_price_usd=tp)
        h=write_demand_for_allocation(str(model),dict(opt['x']),'POPT',cap_wk=800.0,uom=None)
        demand_file=Path(h['path']).name
        shutil.copy2(model/demand_file,target/demand_file)
        dump(target/'allocation.json',{'optimum':opt,'handoff':h})
    origf,origb,origpull=fp.ForwardPlanner.run,bp.BackwardPlanner.run,fp.ForwardPlanner._push_pull_node
    origbridge,origdetect=runner.psi_to_sales_records,runner.detect_scenario
    origsample=ppcmain.generate_sample_sales
    def fwd(self,prod):
        result=origf(self,prod)
        cap['actual'].update(copy.deepcopy(self._actual_s))
        cap['opening'].update(copy.deepcopy(self.opening_inv))
        return result
    def bwd(self,prod):
        result=origb(self,prod)
        cap['bwd'][prod]={'past_due_lots':list(result.past_due_lots)}
        return result
    def pull(self,node,decouple_ids,n_weeks,result,pull_mode=False):
        cap['ot_pull'][node.node_id]={'pull_mode':pull_mode,'is_decouple':node.node_id in decouple_ids,
                                    'P_before':[list(w[3]) for w in node.psi4supply]}
        return origpull(self,node,decouple_ids,n_weeks,result,pull_mode=pull_mode)
    def bridge(tree,weeks,**kwargs):
        sales=origbridge(tree,weeks,**kwargs)
        cap.update(tree=tree,weeks=list(weeks),bridge=sales.copy(),bridge_kwargs=kwargs)
        cap['sources'],cap['mappings']=sales_map(tree,weeks,kwargs)
        assert len(cap['sources'])==len(sales)
        for (_,n,wi,ch,prod),r in zip(cap['sources'],sales.to_dict('records')):
            assert r['qty']==len(n.psi4supply[wi][0])*tree.cpu_size
            assert (r['channel_node'],r['product_id'],r['week'])==(ch,prod,weeks[wi])
        return sales
    def detect(sales):
        scenario=origdetect(sales);cap['scenario']=scenario;return scenario
    def sample(*a,**kw):
        cap['fallback']=True;return origsample(*a,**kw)
    class CaptureEngine(PPCSimulationEngine):
        def __init__(self,*a,**kw):
            assert not a
            caller=inspect.currentframe().f_back.f_locals
            label=caller.get('scenario')
            cap['scenario_branch']=label if label in ('rice','cookie','iphone_global') else ('GENERIC_tree' if caller.get('_mom_map') else 'legacy_iphone_fallback')
            cap['engine_kwargs']=kw.copy()
            super().__init__(**kw)
        def run(self):
            result=super().run();cap['existing']=result;return result
    try:
        with contextlib.ExitStack() as stack:
            for obj,name,repl in [(fp.ForwardPlanner,'run',fwd),(bp.BackwardPlanner,'run',bwd),
                                  (fp.ForwardPlanner,'_push_pull_node',pull),
                                  (runner,'psi_to_sales_records',bridge),(runner,'detect_scenario',detect),
                                  (runner,'PPCSimulationEngine',CaptureEngine),(ppcmain,'generate_sample_sales',sample)]:
                stack.enter_context(patch.object(obj,name,repl))
            snap=headless.run(str(model),plugins_spec=plugins,output_ppc_dir=str(target/'existing_ppc'),
                              verbose=False,demand_file=demand_file)
        dump(target/'snapshot.json',snap)
        dump(target/'input_hashes_after.json',hashes(model))
        if golden:
            expected=json.loads(golden.read_text(encoding='utf-8'))
            cap['golden_equal']={k:snap[k]==expected[k] for k in ('period','products','config','forward','backward','ppc','psi')}
        rules=cap['engine_kwargs']['rules']; sales=cap['bridge']
        mask=sales.product_id.isin(rules.supplier_cost.product_id.dropna()) & sales.channel_node.isin(rules.market_price.market_node.dropna())
        accepted=sales[mask]; rejected=sales[~mask]
        cpu=cap['tree'].cpu_size
        mapped=collections.defaultdict(list)
        for m in cap['mappings']: mapped[(m['product_id'],m['channel'])].append(m['node_id'])
        collision={str(k):v for k,v in mapped.items() if len(v)>1}
        p1={'case':case,'call_path':'headless.run -> _run_ppc -> run_ppc_from_psi',
            'plugins':plugins,'scenario':cap['scenario'],'scenario_branch':cap['scenario_branch'],'cpu_size':cpu,
            'bridge_rows':len(sales),'bridge_units':float(sales.qty.sum()),'bridge_lots':float(sales.qty.sum()/cpu),
            'accepted_rows':len(accepted),'accepted_units':float(accepted.qty.sum()),'accepted_lots':float(accepted.qty.sum()/cpu),
            'excluded_rows':len(rejected),'excluded_units':float(rejected.qty.sum()),'excluded_lots':float(rejected.qty.sum()/cpu),
            'excluded_pairs':rejected[['product_id','channel_node']].drop_duplicates().to_dict('records'),
            'psi_mode':not cap.get('fallback',False),'fallback':cap.get('fallback',False),
            'mapping_collisions':collision,'duplicate_synthetic_id_rows':int(sales.lot_id.duplicated(keep=False).sum()),
            'golden_equal':cap.get('golden_equal'),'engine_input_rows':len(cap['engine_kwargs']['sales_records'])}
        dump(target/'p1.json',p1)
        sales.to_csv(target/'bridge.csv',index=False)
        rejected.to_csv(target/'excluded.csv',index=False)
        cap['engine_kwargs']['sales_records'].to_csv(target/'engine_input.csv',index=False)
        dump(target/'channel_mapping.json',cap['mappings'])
        dump(target/'backward.json',cap['bwd'])
        if case in MAIN:
            dump_detail(target,case,cap,mask)
        print(case, 'P1',p1['bridge_lots'],'excluded',p1['excluded_rows'],'fallback',p1['fallback'],flush=True)
        return p1
    finally:
        tmp.cleanup()

def dump_detail(target,case,c,mask):
    """Retain direct observations for P2-P4; monetary comparison occurs after P1."""
    tree=c['tree'];weeks=c['weeks'];actual=c['actual'];cpu=tree.cpu_size
    nodes=[]
    for prod in tree.products:
        for n in tree.iter_all_nodes(prod):
            nodes.append({'product':prod,'node_id':n.node_id,'name':n.node_name,'node_type':n.node_type,
                          'plan_mode':n.plan_mode,'parent_id':n.parent.node_id if n.parent else None,
                          'children':[ch.node_id for ch in n.children],'is_decoupling':n.is_decoupling,
                          'ot_control':c['ot_pull'].get(n.node_id),'opening':c['opening'].get(n.node_id,[]),
                          'S':[list(w[0]) for w in n.psi4supply], 'P':[list(w[3]) for w in n.psi4supply],
                          'I_count':[len(w[2]) for w in n.psi4supply], 'CO_count':[len(w[1]) for w in n.psi4supply],
                          'dP':[list(w[3]) for w in n.psi4demand],
                          'actual':[actual.get(n.node_id,{}).get(w,[]) for w in range(len(weeks))],
                          'actual_observed':n.node_id in actual})
    dump(target/'node_observations.json',{'weeks':weeks,'cpu_size':cpu,'nodes':nodes})
    records=[]; links=[]; weekly=[]; differences=[]
    for i,(source,row) in enumerate(zip(c['sources'],c['bridge'].to_dict('records'))):
        prod,n,wi,ch,pprod=source; eid=f'{case}:entry:{i}'
        records.append({'run_id':case,'entry_record_id':eid,'call_path':'headless',
                        'input_row_index':i,'source_node_id':n.node_id,'product_id':pprod,'channel':ch,
                        'week_index':wi,'week':weeks[wi],'synthetic_lot_id':row['lot_id'],
                        'planned_s_lots':len(n.psi4supply[wi][0]),'cpu_size':cpu,'qty':row['qty'],'unit':'unit',
                        'accepted':bool(mask.iloc[i]),'fallback':c.get('fallback',False),
                        'evidence_level':'observed','evidence_ref':'node_observations.json'})
        for lid,m in collections.Counter(n.psi4supply[wi][0]).items():
            links.append({'run_id':case,'entry_record_id':eid,'source_node_id':n.node_id,'product_id':prod,
                          'week_index':wi,'bucket':'S','layer':'supply','lot_id':lid,'multiplicity':m,
                          'linked_quantity_lots':m,'linked_quantity_units':m*cpu,
                          'mapping_method':'captured original PSI at bridge call, before aggregation',
                          'evidence_level':'observed','evidence_ref':'node_observations.json'})
    for n in nodes:
        if n['node_type']!='leaf_out': continue
        for w,week in enumerate(weeks):
            plan=collections.Counter(n['S'][w]);act=collections.Counter(n['actual'][w])
            weekly.append({'run_id':case,'product_id':n['product'],'node_id':n['node_id'],'week':week,
                           'planned_s':sum(plan.values()),'actual_s':sum(act.values()),
                           'gap':sum(plan.values())-sum(act.values()),'CO':n['CO_count'][w],
                           'planned_only_count':sum((plan-act).values()),'actual_only_count':sum((act-plan).values()),
                           'multiset_equal':plan==act,'actual_observed':n['actual_observed'],
                           'opening_lots':len(n['opening'])})
            if plan!=act:
                differences.append({'node_id':n['node_id'],'week':week,'planned_only':dict(plan-act),'actual_only':dict(act-plan)})
    jsonl(target/'ppc_entry_records.jsonl',records)
    jsonl(target/'ppc_entry_links.jsonl',links)
    csvout(target/'leaf_weekly.csv',weekly)
    jsonl(target/'leaf_id_differences.jsonl',differences)
    # Serialize exact engine configuration and observations for replay without pickle.
    kw=c['engine_kwargs']
    dump(target/'engine_parameters.json',{k:str(v) if k=='rules' else v for k,v in kw.items() if k not in ('sales_records','rules')})
    # Result objects retained only in-process, immediately used after P1 all cases.
    c['nodes_serialized']=nodes

def monetary(target,case,c):
    import pandas as pd
    from wom.ppc.ppc_engine import PPCSimulationEngine
    from wom.ppc.ppc_kpi import COST_EVENT_TYPES, REVENUE_EVENT_TYPES
    tree=c['tree']; weeks=c['weeks'];cpu=tree.cpu_size
    mappings=c['mappings']; nodes={n['node_id']:n for n in c['nodes_serialized']}
    rows=[]
    for m in mappings:
        n=nodes[m['node_id']]
        if not n['actual_observed']: raise RuntimeError('Missing actual_s: '+n['node_id'])
        for w,ids in enumerate(n['actual']):
            if ids: rows.append({'lot_id':f"PSI-{m['product_id']}-{m['channel']}-{weeks[w]}",
                                 'week':weeks[w],'channel_node':m['channel'],'product_id':m['product_id'],'qty':len(ids)*cpu})
    actual_sales=pd.DataFrame(rows,columns=['lot_id','week','channel_node','product_id','qty'])
    kw=c['engine_kwargs'].copy();rules=kw['rules']
    valid=actual_sales.product_id.isin(rules.supplier_cost.product_id.dropna()) & actual_sales.channel_node.isin(rules.market_price.market_node.dropna())
    actual_sales=actual_sales[valid].copy()
    actual_sales.to_csv(target/'supplied_sales.csv',index=False)
    # Same captured resolved paths, rules, currency; only sales_records replaced.
    kw['sales_records']=actual_sales
    supplied=PPCSimulationEngine(**kw).run()
    existing=c['existing']
    groups={}; accmaps={}
    for basis,res in [('existing_ppc',existing),('supplied',supplied)]:
        dump(target/(basis+'_kpi.json'),res.kpi_summary)
        jsonl(target/(basis+'_events.jsonl'),(dataclasses.asdict(e) for e in res.ppc_events))
        accrows=[]; accmaps[basis]={}
        for a in res.lot_accumulators:
            rec={'lot_id':a.lot_id,'product_id':a.product_id,'channel':a.channel_node,'week':a.week,'units':a.qty,
                 'revenue_per_unit':a.market_revenue_base,'cost_per_unit':a.total_forward_cost_base(),
                 'revenue':a.market_revenue_base*a.qty,'cost':a.total_forward_cost_base()*a.qty,
                 'gross_profit':a.gross_profit_base()*a.qty}
            accrows.append(rec);accmaps[basis][a.lot_id]=rec
        csvout(target/(basis+'_accumulators.csv'),accrows)
        res.node_pl_summary.to_csv(target/(basis+'_node_pl.csv'),index=False)
        for keys in [(),('product_id','channel'),('week',),('product_id','channel','week')]:
            for r in accrows:
                key=(keys,tuple(r[k] for k in keys));g=groups.setdefault(key,{'existing_ppc':collections.Counter(),'supplied':collections.Counter()})
                for metric in ['units','revenue','cost','gross_profit']:g[basis][metric]+=r[metric]
    diffs=[]
    for (keys,vals),g in groups.items():
        row={'run_id':case,'scope':'all' if not keys else 'x'.join(keys),**dict(zip(keys,vals)),
             'currency':existing.base_currency,'category':'quantity/timing','id_aggregation_amount_effect':'not changed',
             'method':'same resolved PPC engine configuration, replace only sales_records quantities/weeks'}
        for metric in ['units','revenue','cost','gross_profit']:
            for basis in g:row[basis+'_'+metric]=g[basis][metric]
            row['delta_supplied_minus_existing_'+metric]=g['supplied'][metric]-g['existing_ppc'][metric]
        diffs.append(row)
    csvout(target/'ppc_basis_differences.csv',diffs)
    # Timing/never-shipped classification is exact ID multiset matching, node-local.
    classification=[]
    for m in mappings:
        n=nodes[m['node_id']]; shipments=collections.defaultdict(list)
        for w,ids in enumerate(n['actual']):
            for lid in ids: shipments[lid].append(w)
        for w,ids in enumerate(n['S']):
            for lid in ids:
                times=shipments[lid]
                aw=times.pop(0) if times else None
                cl='not_shipped_in_horizon' if aw is None else 'early' if aw<w else 'late' if aw>w else 'on_time'
                classification.append({'node_id':n['node_id'],'product':m['product_id'],'lot_id':lid,
                                       'planned_week':weeks[w],'actual_week':None if aw is None else weeks[aw],
                                       'classification':cl,'lots':1,'unit_qty':cpu})
        for lid,times in shipments.items():
            for w in times: classification.append({'node_id':n['node_id'],'lot_id':lid,'actual_week':weeks[w],
                                                   'classification':'actual_without_S_occurrence','lots':1,'unit_qty':cpu})
    jsonl(target/'leaf_id_timing.jsonl',classification)
    dump(target/'leaf_id_timing_summary.json',dict(collections.Counter(r['classification'] for r in classification)))
    # Trial02 comparison: IDs missing at Bottling, NOT missing market shipments.
    reference={}
    bottle=next((n for n in nodes.values() if n['name']=='Bottling_Noda'),None)
    if bottle:
        actual_ids=collections.Counter(x for ids in bottle['actual'] for x in ids)
        missing=[]; rev=gp=0.0
        for m in mappings:
            n=nodes[m['node_id']]
            market_actual=collections.Counter(x for ids in n['actual'] for x in ids)
            for w,ids in enumerate(n['S']):
                key=f"PSI-{m['product_id']}-{m['channel']}-{weeks[w]}"
                acc=accmaps['existing_ppc'].get(key)
                for lid in ids:
                    if lid not in actual_ids:
                        r={'lot_id':lid,'market_node':n['node_id'],'market_week':weeks[w],
                           'bottling_actual_occurrences':0,'market_actual_occurrences':market_actual[lid],
                           'revenue_attributed':None if acc is None else acc['revenue_per_unit']*cpu,
                           'gross_profit_attributed':None if acc is None else (acc['revenue_per_unit']-acc['cost_per_unit'])*cpu,
                           'mapping_method':'derived using observed bridge membership and same aggregate per-unit rate'}
                        missing.append(r)
                        if acc:rev+=r['revenue_attributed'];gp+=r['gross_profit_attributed']
        jsonl(target/'trial02_missing_bottling_ids.jsonl',missing)
        reference={'missing_bottling_occurrences':len(missing),'unique_ids':len({r['lot_id'] for r in missing}),
                   'attributed_revenue':rev,'attributed_gross_profit':gp,
                   'market_actual_present':sum(r['market_actual_occurrences']>0 for r in missing)}
        dump(target/'trial02_reproduction.json',reference)
    # Per-event observed quantity basis, retain unique record coverage (not sums of repeated events).
    bynode=collections.defaultdict(list)
    for e in existing.ppc_events:bynode[(e.product_id,e.node_id)].append(e)
    basisrows=[]
    for n in nodes.values():
        if n['node_type']=='leaf_out':continue
        evs=bynode.get((n['product'],n['name']),[])
        unique={e.lot_id for e in evs}; input_qty=sum(accmaps['existing_ppc'][lid]['units'] for lid in unique if lid in accmaps['existing_ppc'])
        mismatch=sum(abs(e.qty-accmaps['existing_ppc'].get(e.lot_id,{}).get('units',-1))>1e-9 for e in evs)
        row={'run_id':case,'product_id':n['product'],'node_id':n['node_id'],'node_name':n['name'],'node_type':n['node_type'],
             'scenario':c['scenario'],'own_actual_lots':sum(map(len,n['actual'])),'own_actual_units':sum(map(len,n['actual']))*cpu,
             'planned_s_lots':sum(map(len,n['S'])),'opening_lots':len(n['opening']),
             'ppc_event_count':len(evs),'unique_ppc_records':len(unique),'source_sales_units':input_qty,
             'event_qty_mismatches':mismatch,
             'quantity_basis':'leaf_out_sales_derived' if evs and mismatch==0 else 'unconfirmed' if evs else 'no_ppc_event',
             'event_types':';'.join(sorted({e.ppc_event_type for e in evs})),
             'revenue_base':sum(e.amount_base*e.qty for e in evs if e.ppc_event_type in REVENUE_EVENT_TYPES),
             'cost_base':sum(e.amount_base*e.qty for e in evs if e.ppc_event_type in COST_EVENT_TYPES),
             'evidence_ref':'existing_ppc_events.jsonl;existing_ppc_accumulators.csv;node_observations.json',
             'note':'No node price inferred; event qty derives from captured sales accumulator; absent events are not zero-valued full-node sales.'}
        basisrows.append(row)
    csvout(target/'ppc_node_basis.csv',basisrows)
    boundaries=[]
    for n in nodes.values():
        ctrl=n['ot_control']
        if ctrl is None:continue
        par=nodes.get(n['parent_id'])
        receipts=collections.Counter(x for ids in n['P'] for x in ids)
        upstream=collections.Counter(x for ids in par['actual'] for x in ids) if par else collections.Counter()
        absent=receipts-upstream if par else collections.Counter()
        boundaries.append({'node_id':n['node_id'],'node_name':n['name'],'product':n['product'],
                           'parent':None if par is None else par['name'],
                           'pull_mode_observed':ctrl['pull_mode'],'is_decouple_observed':ctrl['is_decouple'],
                           'p_before_lots':sum(map(len,ctrl['P_before'])),'p_final_lots':sum(map(len,n['P'])),
                           'p_equals_demand_p_weekly':n['P']==n['dP'],'actual_lots':sum(map(len,n['actual'])),
                           'parent_actual_lots':None if par is None else sum(map(len,par['actual'])),
                           'receipt_ids_absent_parent_actual_in_horizon':sum(absent.values()),
                           'note':'Horizon-wide ID comparison, not a standalone proof of infeasibility; opening recorded separately.'})
        if absent:jsonl(target/('boundary_ids_'+n['node_id'].replace(':','_')+'.jsonl'),
                        ({'lot_id':lid,'multiplicity':m,'node_id':n['node_id']} for lid,m in absent.items()))
    csvout(target/'outbound_boundaries.csv',boundaries)
    dump(target/'main_summary.json',{'existing':existing.kpi_summary,'supplied':supplied.kpi_summary,'trial02':reference,
                                    'leaf_timing':dict(collections.Counter(r['classification'] for r in classification))})
    print(case,'P3',existing.kpi_summary['gross_profit_base'],supplied.kpi_summary['gross_profit_base'],reference,flush=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--repo',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--cases',nargs='*',help='Optional case subset; use a new output folder')
    args=ap.parse_args();repo=Path(args.repo).resolve();out=Path(args.out).resolve()
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    if sha!=BASE:raise SystemExit(f'Wrong SHA {sha}; expected {BASE}')
    if subprocess.check_output(['git','diff','HEAD','--name-only'],cwd=repo,text=True).strip():raise SystemExit('Tracked files dirty')
    if out.exists() and any(out.iterdir()):raise SystemExit('Use empty output folder')
    out.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(repo));os.chdir(repo)
    versions={}
    for name in ['pandas','numpy','pytest','networkx','matplotlib','openpyxl']:
        try:versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:versions[name]=None
    dump(out/'manifest.json',{'code_sha':sha,'python':sys.version,'platform':platform.platform(),'versions':versions,
                              'schema_version':'ppc-entry-probe-1','call_path':'headless','GUI_measured':False,
                              'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    jobs=[]
    for g in sorted((repo/'tests/golden').glob('*.json')):
        pl=','.join(json.loads(g.read_text())['config']['plugins']) or 'none';jobs.append((g.stem,pl,False,g))
    jobs.extend([('soysauce-jpy-2027-alloc','safe',False,None),('soysauce-jpy-2027-alloc__P_opt800','safe',True,None),
                 ('ev-thailand-2026_update','safe',False,None)])
    p1=[]; errors=[]; captures={}
    # Capture main models without serializing live rules/engine objects. Restore after each case.
    global dump_detail
    orig_detail=dump_detail
    def remember(target,case,c,mask):orig_detail(target,case,c,mask);captures[case]=c
    dump_detail=remember
    for case,pl,opt,g in jobs:
        if args.cases and case not in args.cases:continue
        try:
            with (out/(case+'.log')).open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
                row=run_case(repo,out,case,pl,opt,g)
            p1.append(row);print('P1 finished',case,row['fallback'],row['excluded_rows'],flush=True)
        except Exception as exc:
            errors.append({'case':case,'stage':'P1','error':repr(exc),'traceback':traceback.format_exc()});print('ERROR',case,exc,flush=True)
        csvout(out/'p1_all_cases.csv',p1);dump(out/'errors.json',errors)
    for case,c in captures.items():
        try:monetary(out/case,case,c)
        except Exception as exc:errors.append({'case':case,'stage':'P2-P4','error':repr(exc),'traceback':traceback.format_exc()})
        dump(out/'errors.json',errors)
    dump(out/'tracked_diff_after.json',{'diff':subprocess.check_output(['git','diff','HEAD','--name-only'],text=True,cwd=repo)})
    dump(out/'sha256.json',hashes(out))
    if errors:raise SystemExit('Some measurements failed; see errors.json')

if __name__=='__main__':main()
