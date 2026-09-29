"""Independent cross-run comparison and start-boundary evidence, stdlib only."""
import argparse,csv,json,gzip,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from rules import rows,dump
from check import csvread,csvwrite

def main(base,inputs,model_dir):
 base=Path(base);inputs=Path(inputs);out=base/'comparison';out.mkdir(exist_ok=True)
 modes=('legacy','identity');s={m:json.loads((base/f'run_C_{m}'/'summary.json').read_text()) for m in modes}
 assert s['legacy']['anchor_file_sha256']==s['identity']['anchor_file_sha256']
 assert s['legacy']['anchor_canonical_sha256']==s['identity']['anchor_canonical_sha256']
 roots={m:inputs/m/f'handoff_ev-thailand-2026_C_{m}'/'run' for m in modes}
 manifests={m:json.loads((roots[m]/'manifest.json').read_text()) for m in modes}
 assert manifests['legacy']['model_hashes']==manifests['identity']['model_hashes']
 model_dir=Path(model_dir)
 for name,h in manifests['identity']['model_hashes'].items():
  raw=(model_dir/name).read_bytes()
  assert h in (hashlib.sha256(raw).hexdigest(),hashlib.sha256(raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')).hexdigest()),name
 master={(r['product_name'],r['node_name']):r for r in csvread(model_dir/'sc_tree_master.csv')}
 market={m:{r['lot_id']:r for r in csvread(base/f'run_C_{m}'/'market_states.csv')} for m in modes}
 assert set(market['legacy'])==set(market['identity'])
 trans=[]
 for lot,a in sorted(market['legacy'].items()):
  b=market['identity'][lot];assert (a['product_id'],a['market_node_id'],a['required_week'])==(b['product_id'],b['market_node_id'],b['required_week'])
  trans.append(dict(lot_id=lot,product_id=a['product_id'],market_node_id=a['market_node_id'],required_week=a['required_week'],legacy=a['classification'],identity=b['classification']))
 csvwrite(out/'market_transitions.csv',trans)
 hs={m:{(r['node_id'],r['lot_id']):r for r in rows(base/f'run_C_{m}'/'supply_histories.jsonl.gz')} for m in modes}
 changes=[]
 for n,lot in sorted(set(hs['legacy'])|set(hs['identity'])):
  a=hs['legacy'].get((n,lot),{'P':[],'ship':[]});b=hs['identity'].get((n,lot),{'P':[],'ship':[]})
  if a['P']==b['P'] and a['ship']==b['ship']:continue
  delta=[]
  for k in ('P','ship'):
   aa=Counter(a[k]);bb=Counter(b[k]);delta += list((aa-bb).keys())+list((bb-aa).keys())
  changes.append(dict(node_id=n,lot_id=lot,first_difference_week=min(delta),legacy_P=json.dumps(a['P']),identity_P=json.dumps(b['P']),legacy_ship=json.dumps(a['ship']),identity_ship=json.dumps(b['ship']),market_transition=market['legacy'][lot]['classification']+' -> '+market['identity'][lot]['classification']))
 csvwrite(out/'node_ID_differences.csv',changes)
 # Identify earliest TIME difference per ID, not an unsupported causal root claim.
 earliest={}
 for r in changes:
  lot=r['lot_id']
  if lot not in earliest or (r['first_difference_week'],r['node_id'])<(earliest[lot]['first_difference_week'],earliest[lot]['node_id']):earliest[lot]=r
 csvwrite(out/'earliest_observed_differences.csv',sorted(earliest.values(),key=lambda x:(x['first_difference_week'],x['node_id'],x['lot_id'])))
 nodes={r['node_id']:r for r in csvread(roots['identity']/'nodes.csv')}
 hist=csvread(base/'run_C_identity'/'backlog_histories.csv');bylot=defaultdict(list)
 for r in hist:bylot[r['lot_id']].append(r)
 backlog=[];factory=[]
 for lot,rr in sorted(bylot.items()):
  a=market['identity'][lot];past=[(r['node_id'],json.loads(r['past_due_weeks'])) for r in rr if json.loads(r['past_due_weeks'])]
  observed_P=sum(len(json.loads(r['supply_P_weeks'])) for r in rr)
  fr=next((r for r in rr if 'Factory_Import_CN' in r['node_id']),None)
  fw=json.loads(fr['required_weeks']) if fr else []
  needed=[w-2 for w in fw] # Components_CN transit LT=2 from nodes.csv; no capacity/shift inference.
  needed_past=[(n,[w-int(nodes[n]['lt_wks']) for w in ww]) for n,ww in past]
  needed_policy=[(n,[w-int(nodes[n]['lt_wks'])-(int(master[nodes[n]['product_id'],nodes[n]['node_name']]['ss_days'])+6)//7 for w in ww]) for n,ww in past]
  label='past_due_with_LT_implied_before_start' if past and all(w<0 for n,ww in needed_past for w in ww) else ('past_due_with_LT_SS_implied_before_start' if past and all(w<0 for n,ww in needed_policy for w in ww) else ('past_due_other' if past else ('in_horizon_component_dispatch_needed_but_no_supply' if needed and min(needed)>=0 and not observed_P else 'undetermined')))
  backlog.append(dict(lot_id=lot,product_id=a['product_id'],market_node_id=a['market_node_id'],market_required_week=a['required_week'],evidence_class=label,past_due_records=json.dumps(past),past_due_needed_upstream_week_LT_only=json.dumps(needed_past),past_due_needed_upstream_week_LT_SS=json.dumps(needed_policy),observed_supply_P_occurrences=observed_P,factory_required_weeks=json.dumps(fw),component_dispatch_needed_LT_only=json.dumps(needed)))
  if fw and json.loads(fr['CO_weeks']):factory.append(dict(backlog[-1],CO_first_week=min(json.loads(fr['CO_weeks'])),CO_last_week=max(json.loads(fr['CO_weeks']))))
 csvwrite(out/'backlog_boundary_evidence.csv',backlog);csvwrite(out/'factory_400_evidence.csv',factory)
 examples=[]
 for key in sorted({(r['evidence_class'],r['product_id']) for r in backlog}):examples.extend([r for r in backlog if (r['evidence_class'],r['product_id'])==key][:1])
 summary=dict(anchor_file_equal=True,anchor_canonical_equal=True,anchor_file_sha256=s['identity']['anchor_file_sha256'],transitions={str(k):v for k,v in Counter((r['legacy'],r['identity']) for r in trans).items()},changed_node_ID_pairs=len(changes),changed_unique_IDs=len(earliest),changed_by_node=dict(Counter(r['node_id'] for r in changes)),backlog_evidence=dict(Counter(r['evidence_class'] for r in backlog)),backlog_by_product=dict(Counter(r['product_id'] for r in backlog)),backlog_all_no_observed_supply_P=all(r['observed_supply_P_occurrences']==0 for r in backlog),factory_count=len(factory),factory_LT_needed_before_start=sum(min(json.loads(r['component_dispatch_needed_LT_only']))<0 for r in factory),factory_LT_needed_in_horizon=sum(min(json.loads(r['component_dispatch_needed_LT_only']))>=0 for r in factory),factory_CO_start_counts=dict(Counter(r['CO_first_week'] for r in factory)),examples=examples[:5],earliest_difference_examples=sorted(earliest.values(),key=lambda x:(x['first_difference_week'],x['node_id'],x['lot_id']))[:5])
 dump(out/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--base',required=True);a.add_argument('--inputs',required=True);a.add_argument('--model-dir',required=True);x=a.parse_args();main(x.base,x.inputs,x.model_dir)
