"""Compare before/after probe dumps. usage: compare.py <before> <after> [case...]"""
import gzip, json, os, sys

B, A = sys.argv[1], sys.argv[2]
only = set(sys.argv[3:])

def load(d, c):
    with gzip.open(os.path.join(d, c + ".json.gz"), "rt", encoding="utf-8") as f:
        return json.load(f)

cases = sorted(f[:-8] for f in os.listdir(B) if f.endswith(".json.gz"))
SER = ["P", "S", "actual", "I", "CO", "dS", "dP"]
for c in cases:
    if only and c not in only:
        continue
    b, a = load(B, c), load(A, c)
    sb, sa = b["snap"], a["snap"]
    top = [k for k in ("period", "products", "config", "forward", "backward", "ppc")
           if sb.get(k) != sa.get(k)]
    psi_nodes = []
    for prod in sb["psi"]:
        for nn, v in sb["psi"][prod].items():
            if sa["psi"].get(prod, {}).get(nn) != v:
                psi_nodes.append(f"{prod}|{nn}")
    diag = {k: v for k, v in (("fwd", a["diags"]["fwd"]), ("push", a["diags"]["push"]))}
    diag_counts = []
    for grp, lst in diag.items():
        for d in lst:
            for k, v in d.items():
                if k != "prod" and v:
                    diag_counts.append(f"{d['prod']}:{k}={len(v)}")
    sk = {k: (b["strategic_kpi"].get(k), a["strategic_kpi"].get(k))
          for k in a["strategic_kpi"] if b["strategic_kpi"].get(k) != a["strategic_kpi"].get(k)}
    print(f"\n######## {c}")
    for k in top:
        print(f"  {k}: before={sb.get(k)}\n  {' '*len(k)}  after ={sa.get(k)}")
    print(f"  psi-signature nodes changed: {len(psi_nodes)}")
    print(f"  diagnostics: {diag_counts or 'none'}")
    pdb, pda = b["diags"].get("past_due"), a["diags"].get("past_due")
    if pdb is not None or pda is not None:
        print(f"  backward past_due: before={pdb} after={pda}")
    print(f"  ppc revenue/GP: before={sb['ppc'].get('revenue_base')}/{sb['ppc'].get('gross_profit_base')} "
          f"after={sa['ppc'].get('revenue_base')}/{sa['ppc'].get('gross_profit_base')}")
    if sk:
        print(f"  strategic_kpi changed: {sk}")
    wk = a["weeks"]
    for key in sorted(set(b["nodes"]) | set(a["nodes"])):
        nb, na = b["nodes"].get(key), a["nodes"].get(key)
        if nb is None or na is None:
            print("   node missing", key); continue
        diffs = {}
        for s in SER + ["cap_hard", "cap_soft", "is_open"]:
            idx = [i for i, (x, y) in enumerate(zip(nb[s], na[s])) if x != y]
            if idx:
                diffs[s] = idx
        if not diffs:
            continue
        weeks = sorted({i for v in diffs.values() for i in v})
        print(f"   * {key} ({na['node_type']}/{na['plan_mode']}) series={sorted(diffs)} weeks={len(weeks)} "
              f"[{wk[weeks[0]]}..{wk[weeks[-1]]}]")
        if "--detail" in os.environ.get("CMPFLAGS", "") or len(weeks) <= 12:
            for i in weeks[:12]:
                row = " ".join(f"{s}:{nb[s][i]}->{na[s][i]}" for s in SER + ["cap_hard", "cap_soft", "is_open"]
                               if nb[s][i] != na[s][i])
                print(f"       {wk[i]} {row}")
        sb_ = {s: (sum(nb[s]), sum(na[s])) for s in ("P", "actual", "I", "CO") if sum(nb[s]) != sum(na[s])}
        if sb_:
            print(f"       totals(before,after): {sb_}")
