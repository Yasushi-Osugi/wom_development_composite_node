"""Combine local Q05 with independently established upstream provenance.
Runs after check.py. No engine calls and no expectation-specific exemptions.
"""
import argparse,json
from pathlib import Path
from collections import Counter
from rules import rows,dump
from check import csvread,csvwrite

def main(base):
 for mode in ('legacy','identity'):
  p=Path(base)/f'run_C_{mode}';v=csvread(p/'violations.csv');v=[r for r in v if r['kind']!='shipment_with_unbacked_same_week_receipt']
  hist={(r['node_id'],r['lot_id']):r for r in rows(p/'supply_histories.jsonl.gz')}
  extra=[]
  for r in v:
   if r['kind']=='P_without_parent_shipment_at_LT' and int(r['week_index']) in hist.get((r['node_id'],r['lot_id']),{}).get('ship',[]):
    extra.append(dict(r,check_id='Q05',kind='shipment_with_unbacked_same_week_receipt',detail='Q04 unsupported receipt ID also shipped at the same node/week; local balance alone is insufficient'))
  v+=extra;csvwrite(p/'violations.csv',v,['check_id','kind','node_id','week_index','week_label','lot_id','quantity','detail'])
  checks=csvread(p/'checks.csv');s=json.loads((p/'summary.json').read_text())
  s['problem_counts']=dict(Counter(r['check_id']+'|'+r['kind'] for r in v));s['problem_quantities']={k:sum(int(r['quantity']) for r in v if r['check_id']+'|'+r['kind']==k) for k in s['problem_counts']}
  for r in checks:
   if r['check_id']=='Q05':
    r['rule']='local availability plus upstream provenance; unbacked same-week receipt is not physical evidence'
    r['status']='FAIL' if any(x['check_id']=='Q05' for x in v) else 'PASS';r['counts']=json.dumps({'violations':sum(x['check_id']=='Q05' for x in v),'local_balance_violations':sum(x['kind']=='unbacked_ship' for x in v)})
   if r['status']=='FAIL':r['classification']='WOM inconsistency: legacy exception 2' if r['check_id'] in ('Q04','Q05') else 'WOM inconsistency: legacy exception 1'
   if r['check_id']=='Q12':r['classification']='provided evidence only; independent rerun NOT_PERFORMED'
  csvwrite(p/'checks.csv',checks);dump(p/'summary.json',s)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',required=True);main(p.parse_args().base)
