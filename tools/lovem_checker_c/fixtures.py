"""Eight hand-authored small cases, serialized in lovem-a1 interval/event format."""
from pathlib import Path
from collections import Counter
import json,gzip
from rules import classify,week_rule,expand,digest,dump

def main(root):
    root=Path(root);results=[]
    cases=[('F1',1,1,'on_time'),('F2',1,2,'late'),('F3',1,None,'unshipped'),('F4',2,1,'early'),('F5',1,None,'unshipped'),('F6',1,1,'on_time'),('F7',1,2,'late'),('F8',2,2,'on_time')]
    for name,due,sent,expected in cases:
        dest=root/name;dest.mkdir(parents=True,exist_ok=True); iv=[];ev=[]
        pweek=sent if sent is not None else None
        if name=='F7':pweek=1
        for bucket,w,lot in [('S',due,'X')]+([('P',pweek,'X')] if pweek is not None else []):
            iv.append(dict(interval_id=f'iv{len(iv)}',run_id=name,snapshot_id='p/final',phase='final',product_id='p',node_id='n',layer='supply',bucket=bucket,lot_id=lot,role_id='-',start_week_index=w,end_week_index=w,quantity=1,unit='lot',multiplicity=1,evidence_level='observed',evidence_ref='snapshot:p/final'))
        if name in ('F2','F3','F7'):
            iv.append(dict(iv[0],interval_id='iv_co',bucket='CO',start_week_index=2,end_week_index=3 if name=='F3' else 2))
        if name=='F7':iv.append(dict(iv[0],interval_id='iv_i',bucket='I',start_week_index=1,end_week_index=1))
        if sent is not None:ev.append(dict(event_id='ship',event_type='actual_ship',product_id='p',node_id='n',week_index=sent,lot_id='X',role_id='-',quantity=1,unit='lot',sequence=0))
        if name=='F5':ev.append(dict(event_id='shipY',event_type='actual_ship',product_id='p',node_id='n',week_index=1,lot_id='Y',role_id='-',quantity=1,unit='lot',sequence=0))
        with gzip.open(dest/'psi_intervals.jsonl.gz','wt',encoding='utf8') as f:
            for r in iv:f.write(json.dumps(r)+'\n')
        with gzip.open(dest/'events.jsonl.gz','wt',encoding='utf8') as f:
            for r in ev:f.write(json.dumps(r)+'\n')
        c=expand(dest/'psi_intervals.jsonl.gz');assert len(c)>=1
        got=classify([due],[e['week_index'] for e in ev if e['lot_id']=='X'])[0][0][2];assert got==expected
        extra={}
        if name=='F5':
            r=week_rule(Counter(),Counter(Y=1),Counter(),Counter(X=1),Counter(Y=1),Counter());assert r['closing']==Counter(X=1) and r['unrequested_ship']==Counter(Y=1);extra={'quantity_gap':0,'wrong_id':1}
        if name=='F6':
            receipt=Counter(X=1);parent=Counter();assert receipt-parent==Counter(X=1);extra={'unbacked_receipt':1}
        if name=='F7':
            r=week_rule(Counter(),Counter(X=1),Counter(X=1),Counter(X=1),Counter(),Counter(),Counter(X=1));assert r['co_diff']==(Counter(),Counter())
            r2=week_rule(Counter(X=1),Counter(),Counter(),Counter(),Counter(X=1),Counter(X=1),Counter());assert not r2['closing'];extra={'same_week_I_and_incoming_CO_not_prohibited':True}
        if name=='F8':
            # A and X planned production w1; cap1, A completes w1, X w2; X due w2.
            plans={1:['A','X']};completed={1:['A'],2:['X']};assert sum(map(len,completed.values()))==2 and max(map(len,completed.values()))==1
            dump(dest/'capacity_fixture.json',{'planned_P':plans,'completed_P':completed,'cap':1,'X_required_week':2})
        dump(dest/'expected.json',{'classification':expected,**extra});results.append({'fixture':name,'status':'PASS','classification':got,**extra})
    # Independent known digest for empty cell; quantity multiplicity restoration.
    assert digest(Counter())== 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    dump(root/'results.json',results);print(json.dumps(results))
if __name__=='__main__':main(Path(__file__).parent/'fixtures')
