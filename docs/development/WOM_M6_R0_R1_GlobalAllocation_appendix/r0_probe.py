# -*- coding: utf-8 -*-
"""R0 cause (read only): run the headless planning on a case model, capture the tree and the Backward result
by wrapping BackwardPlanner.run in this script (the engine is not changed), and report
- the lots dropped as past-due by region, node and week,
- the order of regions inside the bottling factory's weekly lot list (where the cap clips the tail),
- for representative lots: request week, the week the bottling plan placed them (or dropped), the forward ship.

    python output/cockpit_m6/r0_probe.py <case model dir> <out dir>
"""
import collections
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)

from wom.engine import backward_planner as BPm  # noqa: E402
from wom.engine import forward_planner as FPm  # noqa: E402
from wom.model.plan_node import S, CO, P  # noqa: E402

model, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
cap = {}
_bw, _fw = BPm.BackwardPlanner.run, FPm.ForwardPlanner.run


def bw(self, prod):
    r = _bw(self, prod)
    cap["tree"], cap["bres"] = self.sc_tree, r
    # snapshot of the bottling node's demand-side lists right after Backward
    t = self.sc_tree
    b = t.get_in_root(prod)
    cap["bottling"] = b.node_name
    cap["b_S"] = [list(b.psi4demand[w][S]) for w in range(t.num_weeks())]
    cap["b_CO"] = [list(b.psi4demand[w][CO]) for w in range(t.num_weeks())]
    sp = t.get_ot_root(prod)
    cap["sp_S"] = [list(sp.psi4demand[w][S]) for w in range(t.num_weeks())]
    return r


def fw(self, prod, *a, **k):
    r = _fw(self, prod, *a, **k)
    cap["fres"] = r
    return r


BPm.BackwardPlanner.run, FPm.ForwardPlanner.run = bw, fw
from tools import run_headless_from_folder as H  # noqa: E402
from wom.plugins.selection import read_recommended_plugins  # noqa: E402

plugins = ",".join(read_recommended_plugins(model)) or "safe"
H.run(model, plugins_spec=plugins, output_ppc_dir=os.path.join(out, "ppc"), verbose=False, ppc=False)
t = cap["tree"]
labels = list(t.week_labels)
reg = lambda lot: lot.split(":")[1]
rq = lambda lot: lot.split(":")[2]

res = {"plugins": plugins, "bottling": cap["bottling"]}
# 1 past-due lots of Backward
pd_ = cap["bres"].past_due_lots
c = collections.Counter((n, reg(l)) for n, l, w in pd_)
res["past_due_by_node_region"] = {f"{n}|{r}": v for (n, r), v in sorted(c.items())}
res["past_due_weeks"] = sorted({labels[w] for _n, _l, w in pd_})
res["past_due_request_weeks_by_region"] = {}
for r in sorted({reg(l) for _n, l, _w in pd_}):
    ws = sorted(rq(l) for _n, l, _w in pd_ if reg(l) == r)
    res["past_due_request_weeks_by_region"][r] = {"n": len(ws), "first": ws[0], "last": ws[-1]}

# 2 the order of regions in the bottling list (after the cap clip: S = kept), and in the supply point list
# (before the clip = what the bottling node received from the outbound side)
def runs_of(lst):
    """compress a lot list into region runs: [(region, count), ...]"""
    o = []
    for l in lst:
        r = reg(l)
        if o and o[-1][0] == r:
            o[-1][1] += 1
        else:
            o.append([r, 1])
    return o


rows = []
for w, lst in enumerate(cap["sp_S"]):
    if lst:
        rows.append({"week": labels[w], "sp_lots": len(lst), "sp_region_runs": runs_of(lst),
                     "bottling_kept": len(cap["b_S"][w]), "bottling_overflow_CO": len(cap["b_CO"][w]),
                     "overflow_regions": dict(collections.Counter(reg(l) for l in cap["b_CO"][w]))})
json.dump(rows, open(os.path.join(out, "bottling_weekly_order.json"), "w", encoding="utf-8"), ensure_ascii=False,
          indent=1)
res["weeks_with_overflow"] = sum(1 for r in rows if r["bottling_overflow_CO"])

# 3 representative lots: where did the bottling plan place them (week of S after Backward), or drop them
placed = {}
for w, lst in enumerate(cap["b_S"]):
    for l in lst:
        placed[l] = labels[w]
dropped = {l: labels[w] for _n, l, w in pd_}
fr = cap["fres"]
ship = {}
leaves = {}
for nd in t.iter_all_nodes(t.products[0]):
    if not nd.children and nd.node_type == "leaf_out":
        for i, d in (getattr(nd, "_actual_ship", None) or {}).items():
            for l in d if isinstance(d, (list, set, tuple)) else []:
                ship[l] = labels[i]
res["actual_ship_found"] = len(ship)


def trace(lot):
    return {"lot": lot, "request_week": rq(lot), "bottling_planned_week": placed.get(lot, ""),
            "dropped_backward_at": dropped.get(lot, ""), "shipped_week": ship.get(lot, "")}


pick = []
for r_ in ("BE", "NL", "FR", "JP", "US_W", "US_E"):
    for wk in ("2027-W50", "2028-W20", "2028-W40"):
        for seq in (1, 60):
            pick.append(f"Soy_Sauce:{r_}:{wk}:{seq:05d}")
res["representative"] = [trace(l) for l in pick]
json.dump(res, open(os.path.join(out, "r0_probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "representative"}, ensure_ascii=False, indent=1)[:3000])
for x in res["representative"]:
    print(x)
