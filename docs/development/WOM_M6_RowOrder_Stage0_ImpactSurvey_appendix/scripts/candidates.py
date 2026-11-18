# -*- coding: utf-8 -*-
"""Row-order bias stage 0 (read only), §1.1: the candidates from the CSVs only (no planning).

For every golden model x product x factory where Backward clips (in-root MOM = node_type mom with no parent):
does capacity apply (capacity_plan max_supply / cap_soft, holiday partial_capacity), does a closure apply
(holiday supply_closure, operating_calendar 0 shifts), and how many markets (leaf_out) are under the factory.
candidate = (capacity or closure) and markets >= 2.

    python output/roworder_stage0/candidates.py
"""
import csv
import glob
import json
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.dirname(os.path.abspath(__file__))
MODELS = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(REPO, "tests", "golden", "*.json")))


def rows(model, name):
    p = os.path.join(REPO, "data", "sample", model, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(f)]


def survey(model):
    tree = rows(model, "sc_tree_master.csv")
    cap = rows(model, "capacity_plan.csv") or []
    hol = rows(model, "holiday_calendar.csv") or []
    opc = rows(model, "operating_calendar.csv") or []
    lane = rows(model, "lane_assignment.csv") or []
    env_col = "demand_envelope" in (tree[0] if tree else {})
    out = []
    for prod in sorted({r["product_name"] for r in tree}):
        tp = [r for r in tree if r["product_name"] == prod]
        moms = [r for r in tp if r["node_type"] == "mom" and not r["parent_node"]]
        leaves = [r["node_name"] for r in tp if r["node_type"] == "leaf_out"]
        for m in moms:
            mom = m["node_name"]
            # markets under the factory: with several in-root factories, the lane table routes the leaves
            if len(moms) > 1:
                mk = sorted({r["leaf_node_name"] for r in lane if r["sku_id"] == prod and r["mom_node_id"] == mom})
                mk_src = "lane_assignment" if mk else "all leaves (no lane row)"
                mk = mk or sorted(leaves)
            else:
                mk, mk_src = sorted(leaves), "all leaves of the product"
            new_fmt = bool(cap) and "node_name" in cap[0]
            crow = [r for r in cap if r.get("sku_id") == prod
                    and ((r.get("node_name") == mom) if new_fmt and r.get("node_name") else not new_fmt)]
            # old format (no node_name): the product's rows go to the factory
            ch = sum(1 for r in crow if r.get("max_supply", "") != "")
            cs = sum(1 for r in crow if r.get("cap_soft", "") != "")
            pc = [r for r in hol if r["node_name"] == mom and r["effect"] == "partial_capacity"]
            sc = [r for r in hol if r["node_name"] == mom and r["effect"] == "supply_closure"]
            oz = [r for r in opc if r.get("sku_id") == prod and r["node_name"] == mom and r["shifts"] != ""
                  and float(r["shifts"]) == 0]
            has_cap = ch > 0 or cs > 0 or bool(pc)
            has_closure = bool(sc) or bool(oz)
            out.append({
                "model": model, "product": prod, "factory": mom,
                "demand_envelope": (m.get("demand_envelope") or "hard") if env_col else "hard（列なし）",
                "cap_hard_rows": ch, "cap_soft_rows": cs, "partial_capacity_rows": len(pc),
                "supply_closure_rows": len(sc), "op_zero_shift_rows": len(oz),
                "markets": len(mk), "market_source": mk_src,
                "has_capacity": has_cap, "has_closure": has_closure,
                "candidate": (has_cap or has_closure) and len(mk) >= 2,
            })
    return out


allr = []
for m in MODELS:
    allr += survey(m)
with open(os.path.join(OUT, "candidates.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(allr[0].keys()))
    w.writeheader()
    w.writerows(allr)
json.dump(allr, open(os.path.join(OUT, "candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for m in MODELS:
    rs = [r for r in allr if r["model"] == m]
    print(f"{m}: factories {len(rs)}, candidates {sum(r['candidate'] for r in rs)}")
