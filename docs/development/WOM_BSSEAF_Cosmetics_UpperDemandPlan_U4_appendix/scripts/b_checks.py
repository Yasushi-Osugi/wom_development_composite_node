# -*- coding: utf-8 -*-
"""Letter §2 B1-B4 on the existing P2-a2 copy (read only; plans again in memory)."""
import csv, json, os, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.getcwd())
import tools.run_quantity_allocation as RQ
from tools.run_headless_from_folder import run
from wom.allocation.handoff import write_demand_for_quantity_allocation as W
from wom.model.plan_node import S
C = "output/bsseaf_cosmetics"; MD = C + "/P2a2"; Wk = C + "/u4_work"
AF = "docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/allocation/allocation_qty_P2a2.csv"
res = {}
# B1
orig = list(csv.DictReader(open(MD + "/demand_forecast.csv", encoding="utf-8")))
W(MD, AF, "CHK", out_path=Wk + "/_b1.csv")
new = list(csv.DictReader(open(Wk + "/_b1.csv", encoding="utf-8")))
res["B1_same_as_Q01_csv"] = open(Wk + "/_b1.csv", "rb").read() == open(MD + "/demand_forecast_Q01.csv", "rb").read()
cut = defaultdict(list); weeks_sorted = {}
idx = defaultdict(list)
for o, n in zip(orig, new):
    idx[(o["sku_id"], o["region"])].append(o["week"])
    d = int(float(o["quantity"])) - int(float(n["quantity"]))
    if d: cut[(o["sku_id"], o["region"])].append((o["week"], d))
res["B1_rows_in_week_order"] = {str(k): v == sorted(v) for k, v in idx.items()}
res["B1_cut"] = {str(k): {"lots": sum(d for _, d in v), "from": v[0][0], "to": v[-1][0], "max_per_week": max(d for _, d in v), "weeks": len(v)} for k, v in cut.items()}
# B2
cap = RQ._capture_plugin()
run(MD, verbose=False, demand_file="demand_forecast_Q01.csv", ppc=False, warmup_real_start="2027-W01",
    extra_plugins=[cap], output_ppc_dir=Wk + "/_noppc")
t = cap.tree; wl = list(t.week_labels)
lr = RQ._leaf_region(t)
want = Counter()
for r in new:
    q = int(float(r["quantity"]))
    if q: want[(r["sku_id"], r["region"], r["week"])] += q
got = Counter(); late = Counter(); miss = Counter()
for p in t.products:
    for n in t.iter_all_nodes(p):
        if n.node_type != "leaf_out": continue
        res.setdefault("B2_region_is_node_name", {})[f"{p}|{n.node_name}"] = lr[(p, n.node_name)] == n.node_name
        fs = {}
        for w in sorted(n._actual_ship or {}):
            for l in n._actual_ship[w]: fs.setdefault(l, w)
        for w in range(len(wl)):
            for l in n.psi4supply[w][S]:
                got[(p, lr[(p, n.node_name)], wl[w])] += 1
                x = fs.get(l)
                if x is None: miss[(p, n.node_name, wl[w])] += 1
                elif x > w: late[(p, n.node_name)] += 1
res["B2_leaf_S_week_equals_request_week"] = got == want
res["B2_n"] = [sum(got.values()), sum(want.values())]
# B3
res["B3"] = {}
for p in t.products:
    f = [n for n in t.iter_all_nodes(p) if n.node_name == "Factory_JP"][0]
    w = wl.index("2028-W20")
    res["B3"][p] = {"yield": f.yield_rate, "cap_soft": f.cap_soft(w), "shippable_planned": f.shippable_planned(w), "cap_hard": f.cap_hard(w), "shippable_limit": f.shippable_limit(w), "envelope": f.demand_envelope}
    L = {}
    for n in t.iter_all_nodes(p):
        if n.node_type != "leaf_out": continue
        x, s = n, 0; path = []
        while x is not None and x.node_type != "supply_point":
            s += x.lt_wks; path.append((x.node_name, x.lt_wks, x.ss_wks)); x = x.parent
        L[n.node_name] = {"L": s, "path": path}
    res["B3"][p + "_L"] = L
# B4
q = json.load(open(C + "/_planning_state/P2a2/Q01.json", encoding="utf-8"))
res["B4_Q01_total"] = q["quantities"]["total"]; res["B4_late_tree"] = {str(k): v for k, v in late.items()}; res["B4_q5_lots"] = {str(k): v for k, v in miss.items()}
json.dump(res, open(Wk + "/b_checks.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False)[:3800])
