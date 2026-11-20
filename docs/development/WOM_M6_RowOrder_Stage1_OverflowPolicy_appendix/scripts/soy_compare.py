# -*- coding: utf-8 -*-
"""段 1 §3：醤油 C02（21 シフト、配分なし）の写しで T1〜T6 を回す。

    python output/roworder_stage1/soy_compare.py [T1 ...]

写し：output/roworder_stage1/soy/<T>/model（C02 または行の順を入れ替えた木 ＋ planning_config.csv の
overflow_policy）。1 つずつ回し、結果を output/roworder_stage1/soy/<T>/result.json に書く（あればとばす）。
"""
import json
import os
import shutil
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)
OUT = os.path.join(REPO, "output", "roworder_stage1", "soy")

from wom.engine import backward_planner as BPm  # noqa: E402
from wom.model.plan_node import S, P  # noqa: E402

CAP = {"orig": "output/cockpit_m6/soy/C02/model", "swap": "output/cockpit_m6/r0_order_test/model"}
CASES = {"T1": ("tail", "orig"), "T2": ("proportional_week", "orig"), "T3": ("proportional_week", "swap"),
         "T4": ("balance_cut_ratio", "orig"), "T5": ("balance_cut_ratio", "swap"), "T6": ("tail", "swap")}

GRAB = {}
_init, _run = BPm.BackwardPlanner.__init__, BPm.BackwardPlanner.run


def init(self, sc_tree, *a, **k):
    GRAB["tree"] = sc_tree
    _init(self, sc_tree, *a, **k)


def run_(self, prod_nm, *a, **k):
    r = _run(self, prod_nm, *a, **k)
    GRAB.setdefault("bres", []).append(r)
    return r


BPm.BackwardPlanner.__init__ = init
BPm.BackwardPlanner.run = run_
from tools import run_headless_from_folder as H  # noqa: E402
from wom.plugins.selection import read_recommended_plugins  # noqa: E402


def make_copy(tag, policy, src):
    d = os.path.join(OUT, tag, "model")
    if not os.path.exists(d):
        shutil.copytree(os.path.join(REPO, CAP[src]), d)
        pc = os.path.join(d, "planning_config.csv")
        text = open(pc, encoding="utf-8-sig").read()
        if not text.endswith("\n"):
            text += "\n"
        if policy != "tail":
            text += f"overflow_policy,{policy}\n"
        open(pc, "w", encoding="utf-8", newline="").write(text)
    return d


def one(tag):
    policy, src = CASES[tag]
    res_path = os.path.join(OUT, tag, "result.json")
    if os.path.exists(res_path):
        print("[skip]", tag)
        return
    m = make_copy(tag, policy, src)
    GRAB.clear()
    t0 = time.time()
    snap = H.run(m, plugins_spec=",".join(read_recommended_plugins(m)),
                 output_ppc_dir=os.path.join(OUT, tag, "ppc"), verbose=False,
                 flow_check_dir=os.path.join(OUT, tag, "flow_check"))
    sec = round(time.time() - t0, 1)
    tree = GRAB["tree"]
    weeks = tree.week_labels if hasattr(tree, "week_labels") else None
    n = tree.num_weeks()
    ships, mom_info = {}, {}
    for prod in tree.products:
        for node in tree.get_ot_root(prod).walk_preorder():
            if node.node_type == "leaf_out":
                act = getattr(node, "_actual_ship", {}) or {}
                for w, lots in act.items():
                    for l in lots:
                        ships[l] = int(w)
        for mom in tree.get_in_roots(prod).values():
            viol = []
            for w in range(n):
                cap = mom.cap_hard(w)
                cnt = len(mom.psi4demand[w][P]) if mom.psi4demand[w][P] else len(mom.psi4demand[w][S])
                sup = len(mom.psi4supply[w][P])
                lim = 0 if not mom.is_open(w) else (None if cap is None else int(cap))
                if lim is not None and (cnt > lim or sup > lim):
                    viol.append([w, cnt, sup, lim])
            mom_info[mom.node_id] = {"cap_violations": viol}
    fc = {}
    import csv
    with open(os.path.join(OUT, tag, "flow_check", "flow_check_market.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            fc[r["leaf"]] = {k: int(r[k]) for k in ("demand", "on_time", "early", "late", "backlog_end")}
    burden = {}
    for b in GRAB["bres"]:
        for nid, mk in b.overflow_by_node.items():
            burden[nid] = mk
    res = {"tag": tag, "policy": policy, "tree": src, "seconds": sec, "config": snap["config"],
           "market": fc, "burden": burden, "mom": mom_info,
           "past_due": sum(len(b.past_due_lots) for b in GRAB["bres"]),
           "ship_week_by_lot": dict(sorted(ships.items())), "n_ships": len(ships)}
    json.dump(res, open(res_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[done] {tag} {policy}/{src} {sec}s ships={len(ships)} "
          f"backlog={ {k: v['backlog_end'] for k, v in fc.items()} }")


if __name__ == "__main__":
    for t in (sys.argv[1:] or list(CASES)):
        one(t)
