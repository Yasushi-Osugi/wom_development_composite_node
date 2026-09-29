"""Independent rules. Standard library only; no WOM/LOVEM imports.
CO[w] is incoming backlog; closing backlog is CO[w]+S[w]-matched_ship[w].
Identity matching is multiset matching within product/node/role, never across nodes.
"""
from collections import Counter
import hashlib,json,gzip
from pathlib import Path

def rows(path):
    p=Path(path)
    with (gzip.open(p,'rt',encoding='utf-8') if p.suffix=='.gz' else p.open(encoding='utf-8-sig')) as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def dump(path,obj):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def expand(path):
    cells={}
    for r in rows(path):
        a,b=r['start_week_index'],r['end_week_index']
        assert 0<=a<=b and r['multiplicity']>0
        assert r['bucket'] not in ('P','S') or a==b
        token=(r['lot_id'],r['role_id'],r['quantity'])
        for w in range(a,b+1):
            k=(r['snapshot_id'],r['node_id'],r['layer'],r['bucket'],w)
            c=cells.setdefault(k,Counter()); assert token not in c,'overlapping intervals'
            c[token]=r['multiplicity']
    return cells

def digest(c):
    def num(v):return str(int(v)) if float(v).is_integer() else repr(float(v))
    text='\n'.join(f'{lot}\t{role}\t{num(q)}\t{m}' for (lot,role,q),m in sorted(c.items()))
    return hashlib.sha256(text.encode()).hexdigest()

def classify(req_weeks,ship_weeks):
    """Chronological occurrence pairing; ambiguous repeated demand is labelled by caller.
    No match => unshipped; only caller can establish recorded closing CO.
    """
    req=sorted(req_weeks); ships=sorted(ship_weeks);out=[]
    for i,w in enumerate(req):
        s=ships[i] if i<len(ships) else None
        out.append((w,s,'unshipped' if s is None else 'early' if s<w else 'late' if s>w else 'on_time'))
    return out,ships[len(req):]

def week_rule(prev,p,i,s,ship,co,next_co=None):
    available=prev+p; requests=co+s
    return {'physical_missing':(i+ship)-available,'physical_excess':available-(i+ship),
            'unbacked_ship':ship-available,'unrequested_ship':ship-requests,
            'closing':requests-ship,'co_diff':None if next_co is None else ((requests-ship)-next_co,next_co-(requests-ship))}
