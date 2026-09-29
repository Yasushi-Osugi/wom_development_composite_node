"""Stage C independent file checker, stdlib only. See README for scope/limits."""
import argparse,csv,gzip,hashlib,json,sys
from pathlib import Path
from collections import Counter,defaultdict
from rules import rows,dump,expand,digest,classify,week_rule
VERSION='stagec-1.0'

def csvwrite(path,data,fields=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if not fields:fields=list(data[0]) if data else ['empty']
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
def csvread(p):
    with open(p,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def jhash(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def run(root,out):
    root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    m=json.loads((root/'manifest.json').read_text());N=m['weeks']['weeks']
    nodes={r['node_id']:r for r in csvread(root/'nodes.csv')};weeks={int(r['week_index']):r['engine_week_label'] for r in csvread(root/'weeks.csv')}
    caps={(r['node_id'],int(r['week_index'])):r for r in csvread(root/'capacity.csv')}
    problems=[];checks=[];summ={'mode':m['lot_flow_mode'],'manifest_sha':jhash(m),'code_sha':m['code_sha'],'dirty':m['dirty']}
    def issue(q,kind,n,w,lot='',qty=1,detail=''):
        problems.append(dict(check_id=q,kind=kind,node_id=n,week_index=w,week_label=weeks.get(w,str(w)),lot_id=lot,quantity=qty,detail=detail))
    def check(q,status,rule,counts,evidence,classification=''):
        checks.append(dict(check_id=q,status=status,rule=rule,scope=m['lot_flow_mode'],counts=json.dumps(counts,ensure_ascii=False),quantities='lot unless stated',evidence_refs=evidence,checker_version=VERSION,classification=classification))
    dgs={}
    for r in rows(root/'state_digests.jsonl'):
        k=(r['snapshot_id'],r['node_id'],r['layer'],r['bucket'],r['week_index']);assert k not in dgs;dgs[k]=r
    final={};q1n=0;ivs=0;dg_matches=0
    for snap in m['snapshots']:
        c=expand(root/snap['intervals_file']);ivs+=snap['n_intervals'];seen=set()
        # Enumerate required empty and nonempty cells from manifest scope, independently of digests.
        for n,nr in nodes.items():
            if nr['product_id']!=snap['product_id']:continue
            for layer in snap['layers']:
                for bucket in ('S','CO','I','P'):
                    for w in range(N):
                        k=(snap['snapshot_id'],n,layer,bucket,w);cc=c.get(k,Counter());r=dgs.get(k);seen.add(k);q1n+=1
                        if r is None or digest(cc)!=r['multiset_sha256'] or sum(cc.values())!=r['entry_count'] or sum(t[2]*v for t,v in cc.items())!=r['total_quantity']:issue('Q01','digest_mismatch',n,w,detail=str(k))
                        else:dg_matches+=1
                        if snap['phase']=='final':final[n,layer,bucket,w]=Counter({t[0]:v for t,v in cc.items()})
        for k in set(c)-seen:issue('Q01','unexpected_cell',k[1],k[-1],detail=str(k))
        del c
    print(m['lot_flow_mode'],'digests',dg_matches,q1n,flush=True)
    def cell(n,layer,b,w):return final.get((n,layer,b,w),Counter())
    events={};ships=defaultdict(Counter);shipweeks=defaultdict(list);evship=defaultdict(list);arrivals=defaultdict(Counter);past=defaultdict(list);beyond=[];event_counts=Counter()
    for e in rows(root/'events.jsonl.gz'):
        eid=e['event_id'];assert eid not in events;events[eid]=e;event_counts[e['event_type']]+=1
        n,w,lot=e['node_id'],e['week_index'],e['lot_id'];typ=e['event_type']
        if typ=='actual_ship':
            ships[n,w][lot]+=e['quantity'];shipweeks[n,lot].extend([w]*int(e['quantity']));evship[n,lot].append(eid)
        elif typ in ('arrival','bridge_arrival'):arrivals[n,w][lot]+=e['quantity']
        elif typ=='backward_past_due':past[n,lot].append(w)
        elif typ=='arrival_beyond_horizon':beyond.append(e)
    # Raw source payload hashes and actual-event lists (including order).
    source={};raw_ships=0
    for s in rows(root/'source_evidence.jsonl.gz'):
        source[s['evidence_id']]=s
        if jhash(s['payload'])!=s['source_hash']:issue('Q01','source_hash',s['source_locator'],-1)
    actual_lists=defaultdict(list)
    for e in events.values():
        if e['evidence_ref'] not in source:issue('Q01','missing_source',e['node_id'],e['week_index'],e.get('lot_id') or '',detail=e['event_id'])
        if e['event_type']=='actual_ship':actual_lists[e['evidence_ref']].append((e['sequence'],e['lot_id']))
    for ref,s in source.items():
        if s['source_kind']=='forward_actual_s':
            raw_ships+=len(s['payload'])
            if [lot for _,lot in sorted(actual_lists[ref])]!=s['payload']:issue('Q01','event_source_mismatch',s['source_locator'],-1)
    # Relations are audited, not used as the authority for independent pairing.
    used_from=Counter();used_to=Counter();relcount=0
    for r in rows(root/'relations.jsonl.gz'):
        relcount+=1;a=events.get(r['from_ref']);b=events.get(r['to_ref'])
        if not a or not b:issue('Q01','dangling_relation','',-1,detail=r['relation_id']);continue
        if a['event_type']!='actual_ship' or b['event_type'] not in ('arrival','bridge_arrival') or a['lot_id']!=b['lot_id'] or a['product_id']!=b['product_id'] or r['quantity']!=a['quantity'] or r['quantity']!=b['quantity']:issue('Q04','bad_relation',b['node_id'],b['week_index'],b['lot_id'],detail=r['relation_id'])
        used_from[r['from_ref']]+=1;used_to[r['to_ref']]+=1
    for eid,cnt in used_to.items():
        if cnt!=1:issue('Q04','multiple_relations_to_arrival',events[eid]['node_id'],events[eid]['week_index'],events[eid]['lot_id'],cnt)
    # Anchor equality before interpreting identical strings across runs.
    anchors=list(rows(root/'demand_anchors.jsonl.gz'));anchor_map={a['lot_id']:a for a in anchors};assert len(anchor_map)==len(anchors),'ambiguous anchors'
    anchcanon=[{k:a[k] for k in ('product_id','market_node_id','required_week','lot_id','occurrence','quantity')} for a in anchors]
    summ['anchor_canonical_sha256']=jhash(sorted(anchcanon,key=lambda x:(x['product_id'],x['market_node_id'],x['required_week'],x['lot_id'],x['occurrence'])))
    summ['anchor_file_sha256']=hashlib.sha256(gzip.decompress((root/'demand_anchors.jsonl.gz').read_bytes())).hexdigest()
    # Independent physical route: tree adjacency + anchor market route; bridge single inbound root per product.
    children=defaultdict(list)
    for n,nr in nodes.items():
        if nr['parent_id']:children[nr['parent_id']].append(n)
    def recipient(n,lot):
        nr=nodes[n]
        if nr['tree_side']=='inbound':
            if nr['parent_id']:return nr['parent_id'],int(nr['transit_lt_wks']) or int(nr['lt_wks'])
            sp=[i for i,x in nodes.items() if x['product_id']==nr['product_id'] and x['node_type']=='supply_point'];return (sp[0],0) if len(sp)==1 else (None,None)
        if nr['node_type']=='leaf_out':return None,None
        if lot not in anchor_map:return None,None
        c=anchor_map[lot]['market_node_id'];visited=set()
        while c in nodes and c not in visited:
            visited.add(c)
            if nodes[c]['parent_id']==n:return c,int(nodes[c]['lt_wks'])
            c=nodes[c]['parent_id']
        return None,None
    expected=defaultdict(Counter);route_by_event={};transit=Counter()
    for eid,e in events.items():
        if e['event_type']!='actual_ship':continue
        dest,lt=recipient(e['node_id'],e['lot_id'])
        if dest is None:
            if nodes[e['node_id']]['node_type']!='leaf_out':issue('Q04','unrouted_ship',e['node_id'],e['week_index'],e['lot_id'])
            continue
        w=e['week_index']+lt;route_by_event[eid]=(dest,w)
        if w<N:expected[dest,w][e['lot_id']]+=e['quantity']
        else:transit[dest,w,e['lot_id']]+=e['quantity']
    for r in rows(root/'relations.jsonl.gz'):
        if r['from_ref'] in route_by_event and r['to_ref'] in events:
            b=events[r['to_ref']]
            if route_by_event[r['from_ref']]!=(b['node_id'],b['week_index']):issue('Q04','relation_route_or_LT',b['node_id'],b['week_index'],b['lot_id'],detail=r['relation_id'])
    for eid,e in events.items():
        if e['event_type'] in ('arrival','bridge_arrival') and used_to[eid]!=1:issue('Q04','arrival_without_relation',e['node_id'],e['week_index'],e['lot_id'])
    # Per-node, per-week checks.
    reqweeks=defaultdict(list);statehist=defaultdict(lambda:defaultdict(list));timing=[];market=[];physical_cells=0
    for n,nr in nodes.items():
        for w in range(N):
            for layer,b in [('demand','S'),('demand','P'),('supply','P'),('supply','I'),('supply','CO')]:
                for lot,cnt in cell(n,layer,b,w).items():statehist[n,lot][layer+'_'+b].extend([w]*cnt)
            for lot,cnt in cell(n,'demand','S',w).items():reqweeks[n,lot].extend([w]*cnt)
            prev=cell(n,'supply','I',w-1) if w else Counter();p=cell(n,'supply','P',w);i=cell(n,'supply','I',w);s=cell(n,'supply','S',w);co=cell(n,'supply','CO',w);sh=ships[n,w]
            rr=week_rule(prev,p,i,s,sh,co,cell(n,'supply','CO',w+1) if w+1<N else None);physical_cells+=1
            for key in ('physical_missing','physical_excess','unbacked_ship'):
                for lot,cnt in rr[key].items():issue('Q05' if key=='unbacked_ship' else 'Q03',key,n,w,lot,cnt)
            if nr['plan_mode']!='push_sub':
                if rr['co_diff']:
                    for idx,c in enumerate(rr['co_diff']):
                        for lot,cnt in c.items():issue('Q07','missing_next_CO' if idx==0 else 'extra_next_CO',n,w+1,lot,cnt)
                for lot,cnt in co.items():
                    if cnt>1:issue('Q07','duplicate_CO',n,w,lot,cnt-1)
            if nr['node_type']!='leaf_in':
                for lot,cnt in (p-expected[n,w]).items():issue('Q04','P_without_parent_shipment_at_LT',n,w,lot,cnt)
                for lot,cnt in (expected[n,w]-p).items():issue('Q04','parent_shipment_missing_in_P',n,w,lot,cnt)
                for lot,cnt in (p-arrivals[n,w]).items():issue('Q04','P_without_arrival_record',n,w,lot,cnt)
                for lot,cnt in (arrivals[n,w]-p).items():issue('Q04','arrival_not_in_P_same_week',n,w,lot,cnt)
            cap=caps.get((n,w))
            if cap is None:issue('Q09','missing_capacity_row',n,w);continue
            if cap['is_open']=='0' and sh:issue('Q09','closed_week_ship',n,w,qty=sum(sh.values()))
            # Declared processing operation: push=actual shipment, otherwise P.
            limit=cap['effective_limit'];through=sum((sh if nr['plan_mode']=='push' else p).values())
            if limit!='' and through>float(limit):issue('Q09','processing_limit_exceeded',n,w,qty=through-float(limit),detail=f'limit={limit};operation={"ship" if nr["plan_mode"]=="push" else "P"}')
        if nr['plan_mode']=='push_sub':continue
        all_ids={lot for nn,lot in reqweeks if nn==n}|{lot for nn,lot in shipweeks if nn==n}
        for lot in sorted(all_ids):
            rw=reqweeks[n,lot];sw=shipweeks[n,lot];matched,extra=classify(rw,sw)
            for due,sent,cl in matched:
                if cl=='unshipped':
                    last=week_rule(cell(n,'supply','I',N-2),cell(n,'supply','P',N-1),cell(n,'supply','I',N-1),cell(n,'supply','S',N-1),ships[n,N-1],cell(n,'supply','CO',N-1))['closing']
                    cl='backlog' if last[lot]>0 else 'unshipped_without_CO'
                timing.append(dict(product_id=nr['product_id'],node_id=n,lot_id=lot,required_week=due,shipped_week='' if sent is None else sent,classification=cl,match_method='unique node-demand ID' if len(rw)==1 and len(sw)<=1 else 'chronological occurrence pairing; ambiguous',evidence_refs='final/demand/S; events/actual_ship; final/supply/CO'))
                if cl in ('early','unshipped_without_CO'):issue('Q06',cl,n,due,lot)
            for swx in extra:issue('Q06','shipment_without_request',n,swx,lot)
            if len(rw)>1 or len(sw)>1:issue('Q06','ambiguous_repeated_ID',n,rw[0] if rw else sw[0],lot,detail=f'requests={rw};shipments={sw}')
    for a in anchors:
        n,lot,w=a['market_node_id'],a['lot_id'],a['required_week']
        if cell(n,'demand','S',w)[lot]!=1:issue('Q02','anchor_not_preserved',n,w,lot)
        mm,ex=classify([w],shipweeks[n,lot]);_,sent,cl=mm[0]
        if cl=='unshipped':
            closing=(cell(n,'supply','CO',N-1)+cell(n,'supply','S',N-1))-ships[n,N-1]
            cl='backlog' if closing[lot] else 'unknown'
        if ex or cl in ('early','unknown'):issue('Q02','anchor_state_invalid',n,w,lot,detail=cl)
        market.append(dict(lot_id=lot,product_id=a['product_id'],market_node_id=n,required_week=w,shipped_week='' if sent is None else sent,classification=cl))
    # SE2 reconstruct both numeric gap and complete ID outcomes, including extra shipments.
    target=next(n for n,r in nodes.items() if r['node_name']=='Factory_Import_CN');targetweeks=[w for w,l in weeks.items() if l in ('2026-W38','2026-W39')]
    se2week=[];se2ids=[]
    for w in targetweeks:
        s=cell(target,'supply','S',w);sh=ships[target,w];common=s&sh;missing=s-sh;other=sh-s
        states=Counter()
        for lot,cnt in s.items():
            mat,_=classify([w]*cnt,shipweeks[target,lot]);a=anchor_map.get(lot,{})
            for due,sent,cl in mat:
                states[cl]+=1;se2ids.append(dict(demand_key=a.get('demand_key'),lot_id=lot,role_id='-',required_week=due,shipped_week=sent,quantity=1,classification=cl,match_method='node/product/ID unique occurrence across full horizon',evidence_refs=evship[target,lot],record_kind='target_requirement'))
        for lot,cnt in other.items():se2ids.append(dict(demand_key=anchor_map.get(lot,{}).get('demand_key'),lot_id=lot,role_id='-',required_week=reqweeks[target,lot],shipped_week=w,quantity=cnt,classification='other_ID_shipped_in_target_week',match_method='multiset difference',evidence_refs=evship[target,lot],record_kind='other_shipment'))
        ps=sum(s.values());ac=sum(sh.values());se2week.append(dict(run_id=m['run_id'],product_id=nodes[target]['product_id'],node_id=target,week_index=w,week_label=weeks[w],planned_s=ps,actual_s=ac,signed_gap=ps-ac,shortfall=max(0,ps-ac),excess=max(0,ac-ps),same_ID_same_week=sum(common.values()),required_ID_absent_this_week=sum(missing.values()),other_ID_shipped=sum(other.values()),requirement_classification=json.dumps(states),evidence_refs='psi_intervals/final supply S; events actual_ship'))
    csvwrite(out/'se2_weekly_reconciliation.csv',se2week)
    with (out/'se2_id_reconciliation.jsonl').open('w',encoding='utf8') as f:
        for r in se2ids:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    # Backlog histories (all market backlog + factory backlog), no causal label inference.
    history=[];factory_end=(cell(target,'supply','CO',N-1)+cell(target,'supply','S',N-1))-ships[target,N-1]
    relevant={r['lot_id'] for r in market if r['classification']=='backlog'}|set(factory_end)
    for lot in sorted(relevant):
        for n,nr in nodes.items():
            if nr['product_id']!=anchor_map[lot]['product_id']:continue
            h=statehist[n,lot]
            history.append(dict(lot_id=lot,node_id=n,product_id=nr['product_id'],node_type=nr['node_type'],plan_mode=nr['plan_mode'],required_weeks=json.dumps(reqweeks[n,lot]),demand_P_weeks=json.dumps(h['demand_P']),supply_P_weeks=json.dumps(h['supply_P']),actual_ship_weeks=json.dumps(shipweeks[n,lot]),I_weeks=json.dumps(h['supply_I']),CO_weeks=json.dumps(h['supply_CO']),past_due_weeks=json.dumps(past[n,lot]),own_required_minus_lt=json.dumps([w-int(nr['lt_wks']) for w in reqweeks[n,lot]])))
    csvwrite(out/'backlog_histories.csv',history)
    csvwrite(out/'market_states.csv',market);csvwrite(out/'node_ID_states.csv',timing)
    # Store concise all-ID supply histories to allow run comparison without encoder reuse.
    compact=[]
    for (n,lot),h in statehist.items():
        if h['supply_P'] or shipweeks[n,lot]:compact.append({'node_id':n,'lot_id':lot,'P':h['supply_P'],'ship':shipweeks[n,lot]})
    with gzip.open(out/'supply_histories.jsonl.gz','wt',encoding='utf8') as f:
        for r in compact:f.write(json.dumps(r)+'\n')
    q12=json.loads((root/'q12.json').read_text());q12_equal=q12.get('off')==q12.get('on')
    # Actual structure may use fingerprint objects; compare nested values rather than trust identical boolean.
    summ.update(digest_rows=q1n,digest_matches=dg_matches,physical_cells=physical_cells,anchors=len(anchors),event_counts=dict(event_counts),source_payloads=len(source),raw_ship_count=raw_ships,relations=relcount,market_states=dict(Counter(r['classification'] for r in market)),node_states=dict(Counter(r['classification'] for r in timing)),factory_states=dict(Counter(r['classification'] for r in timing if r['node_id']==target)),factory_closing_backlog=sum(factory_end.values()),se2=se2week,transit=sum(transit.values()),coverage=m['coverage'],q12_keys=list(q12),q12_off_on_equal=q12_equal)
    pcounts=Counter((p['check_id'],p['kind']) for p in problems);summ['problem_counts']={q+'|'+k:v for (q,k),v in pcounts.items()};summ['problem_quantities']={q+'|'+k:sum(p['quantity'] for p in problems if p['check_id']==q and p['kind']==k) for q,k in pcounts}
    for q,desc in [('Q01','all snapshot multiset restoration + source/reference audit'),('Q02','market anchor identity conservation'),('Q03','weekly local physical balance; opening=0 conditional'),('Q04','independent route/LT/ID/multiplicity vs actual P and events'),('Q05','local shipment availability; provenance assessed separately Q04'),('Q06','own-node required week vs actual ID shipment'),('Q07','incoming CO recurrence; closing derived'),('Q09','closure and operation-specific hard limit')]:
        pp=[p for p in problems if p['check_id']==q];check(q,'FAIL' if pp else 'PASS',desc,{'violations':len(pp)},'raw PSI intervals, events, nodes, capacity, sources','WOM inconsistency or observation mismatch; see detail' if pp else '')
    for q in ('Q08','Q10','Q11'):check(q,'NOT_APPLICABLE','no kitting' if q=='Q08' else 'Stage D excluded',{},'scope')
    check('Q12','PASS' if q12_equal else 'UNKNOWN','provided OFF/ON evidence only; not independently rerun',{'off_on_equal':q12_equal},'q12.json')
    csvwrite(out/'violations.csv',problems,['check_id','kind','node_id','week_index','week_label','lot_id','quantity','detail']);csvwrite(out/'checks.csv',sorted(checks,key=lambda r:r['check_id']));dump(out/'summary.json',summ)
    print(json.dumps({k:summ[k] for k in ['mode','digest_matches','market_states','factory_states','factory_closing_backlog','problem_counts','se2','q12_off_on_equal']},ensure_ascii=False),flush=True)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--run',required=True);a.add_argument('--out',required=True);x=a.parse_args();run(x.run,x.out)
