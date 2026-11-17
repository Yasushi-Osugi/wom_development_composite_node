# -*- coding: utf-8 -*-
"""Stage 4 A1 reference (the cockpit's reconciliation stopped on the soy copy): run a model headless and count,
by market (the leaf_out whose region is the Lot_ID's region), demand / on-time / early / late / backlog by Lot_ID,
and the factories' weekly production. Writes <out>/soy_reference_<name>.csv and prints a summary.

    python output/cockpit_step4/soy_reference.py <name> <model_dir>
"""
import collections
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)
import pandas as pd  # noqa: E402
from tools.run_headless_from_folder import run  # noqa: E402
from tools.shelf_life_check import _capture_plugin, check_tree  # noqa: E402

name, model = sys.argv[1], sys.argv[2]
out = os.path.join("output", "cockpit_step4", "soy_reference", name)
os.makedirs(out, exist_ok=True)
cap = _capture_plugin()
snap = run(model, plugins_spec=None, output_ppc_dir=os.path.join(out, "ppc"), verbose=False, extra_plugins=[cap])
tree = cap.tree
labels = list(tree.week_labels)
rs = labels.index("2027-W01")
rows, fac = [], []
for prod in tree.products:
    nodes = list(tree.iter_all_nodes(prod))
    st = pd.read_csv(os.path.join(model, "sc_tree_master.csv"), dtype=str, keep_default_na=False)
    st = st[(st["product_name"] == prod) & (st["node_type"] == "leaf_out")]
    leaf_of = dict(zip(st["region"], st["node_name"]))     # demand region -> market leaf (sc_tree_master)
    shipped = {}
    for nd in nodes:
        if nd.node_type == "leaf_out":
            for w, lots in (getattr(nd, "_actual_ship", None) or {}).items():
                for l in lots:
                    shipped[l] = (nd.node_name, w)
    dem = pd.read_csv(os.path.join(model, "demand_forecast.csv"))
    agg = collections.defaultdict(lambda: collections.Counter())
    for s, g, wk, q in dem[["sku_id", "region", "week", "quantity"]].itertuples(index=False):
        for seq in range(1, int(q) + 1):
            lot = f"{s}:{g}:{wk}:{seq:05d}"
            a = agg[leaf_of[g]]
            a["demand"] += 1
            if lot not in shipped:
                a["backlog_end"] += 1
                continue
            assert shipped[lot][0] == leaf_of[g], (lot, shipped[lot])
            d = shipped[lot][1] - labels.index(wk)
            a["on_time" if d == 0 else ("early" if d < 0 else "late")] += 1
            a["late_weeks_total"] += max(d, 0)
    for leaf, a in sorted(agg.items()):
        rows.append({"market": leaf, **{k: a[k] for k in ("demand", "on_time", "early", "late", "backlog_end",
                                                          "late_weeks_total")}})
    for nd in nodes:
        if nd.node_type == "mom":
            for w in range(len(labels)):
                fac.append({"factory": nd.node_name, "week": labels[w],
                            "production_lots": len(nd.psi4supply[w][3]),
                            "cap_hard": nd.cap_hard(w), "cap_soft": nd.cap_soft(w)})
t = pd.DataFrame(rows)
t.to_csv(os.path.join(out, "by_market.csv"), index=False)
f = pd.DataFrame(fac)
f.to_csv(os.path.join(out, "factory_weekly.csv"), index=False)
age = check_tree(tree, 130)
pd.DataFrame(age["summary"]).to_csv(os.path.join(out, "age_summary.csv"), index=False)
print(f"== {name}  ({model})  GM {snap['ppc'].get('gross_margin_pct')}")
print(t.to_string(index=False))
print("total", t[["demand", "on_time", "early", "late", "backlog_end"]].sum().to_dict())
rep = f[f.week >= "2027-W01"]
for fn, g in rep.groupby("factory"):
    print(fn, "production (report period) most common:", collections.Counter(g.production_lots).most_common(4),
          "| cap_hard", sorted(set(g.cap_hard.dropna()))[:3], "cap_soft", sorted(set(g.cap_soft.dropna()))[:3],
          "| max", g.production_lots.max())
print("age:", [(r["channel"], r["fifo_age_max"]) for r in age["summary"] if r["channel"] == "*"])
