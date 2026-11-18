# -*- coding: utf-8 -*-
"""R0 (read only): where the BE/NL lots planned in Backward but never shipped sit (demand and supply buckets per
node), and the Forward deferrals at the factories."""
import collections, os, sys
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO); os.chdir(REPO)
from wom.engine import backward_planner as BPm
from wom.engine import forward_planner as FPm
from wom.model.plan_node import S, CO, I, P
cap = {}
_bw, _fw = BPm.BackwardPlanner.run, FPm.ForwardPlanner.run
def bw(self, prod):
    r = _bw(self, prod); cap["tree"], cap["bres"] = self.sc_tree, r; return r
def fw(self, prod, *a, **k):
    r = _fw(self, prod, *a, **k); cap["fres"] = r; return r
BPm.BackwardPlanner.run, FPm.ForwardPlanner.run = bw, fw
from tools import run_headless_from_folder as H
from wom.plugins.selection import read_recommended_plugins
model = sys.argv[1]
H.run(model, plugins_spec=",".join(read_recommended_plugins(model)), output_ppc_dir=os.path.join(sys.argv[2], "ppc"),
      verbose=False, ppc=False)
t = cap["tree"]; L = list(t.week_labels); f = cap["fres"]
print("forward deferred lots", f.cap_hard_deferred_lots, "lot-weeks", f.cap_hard_deferred_lot_weeks)
print("closure_p_deferred", f.closure_p_deferred[:10])
dpd = collections.Counter()
for n, l, w in cap["bres"].past_due_lots:
    dpd[(n.split(":")[2], l.split(":")[1])] += 1
nodes = list(t.iter_all_nodes(t.products[0]))
for lot in ("Soy_Sauce:BE:2027-W50:00001", "Soy_Sauce:NL:2027-W50:00001"):
    print("==", lot)
    for nd in nodes:
        for side, arr in (("demand", nd.psi4demand), ("supply", nd.psi4supply)):
            hits = [(L[w], b) for w in range(len(arr)) for b, nm in ((S, "S"), (CO, "CO"), (I, "I"), (P, "P")) if lot in arr[w][b]]
            if hits:
                names = {S: "S", CO: "CO", I: "I", P: "P"}
                print(f"  {nd.node_name:14s} {side:6s}", [(w, names[b]) for w, b in hits][:6], "…" if len(hits) > 6 else "")
# the request weeks of BE lots never shipped and not past-due in Backward
pdl = {l for _n, l, _w in cap["bres"].past_due_lots}
ship = set()
for nd in nodes:
    if nd.node_type == "leaf_out":
        for i, d in (getattr(nd, "_actual_ship", None) or {}).items():
            ship |= set(d)
for r in ("BE", "NL"):
    allr = [l for nd in nodes if nd.node_type == "leaf_out" for w in range(len(L)) for l in nd.psi4demand[w][S] if l.split(":")[1] == r]
    lost = sorted(l for l in allr if l not in ship and l not in pdl)
    wk = collections.Counter(l.split(":")[2] for l in lost)
    print(r, "not shipped, not past-due in Backward:", len(lost), dict(sorted(wk.items())))
