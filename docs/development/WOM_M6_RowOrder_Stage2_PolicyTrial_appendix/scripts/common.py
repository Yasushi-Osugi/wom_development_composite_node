# -*- coding: utf-8 -*-
"""段 2 の共通：写しのモデルを headless で 1 回回し、エンジンの記録を受け取る（エンジンのファイルは変えない）。

- BackwardPlanner.run を包んで BackwardPlanResult（overflow_by_node・past_due_lots）を受け取る。
- BackwardPlanner._apply_mom_cap_backward を包んで、週ごとに CO に足された lot（押し戻した lot）を市場別に数え、
  休業の週（node.is_open(w) が False）の分を分けて記録する（段 0 の調査のスクリプトと同じ包み方）。
- 工場（MOM）の supply の P・I の合計、leaf_out の実出荷、Flow Check の表 2（市場別）、snapshot。
"""
import collections
import csv
import json
import os
import shutil
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
os.chdir(REPO)
OUT = os.path.join(REPO, "output", "roworder_stage2")

from wom.engine import backward_planner as BPm  # noqa: E402
from wom.model.plan_node import S, CO, P, I  # noqa: E402

POLICIES = ("tail", "proportional_week", "balance_cut_ratio")
GRAB = {}
_init, _run, _cap = BPm.BackwardPlanner.__init__, BPm.BackwardPlanner.run, BPm.BackwardPlanner._apply_mom_cap_backward


def region(lot):
    p = str(lot).split(":")
    return p[1] if len(p) >= 3 else "?"


def _init_w(self, sc_tree, *a, **k):
    GRAB["tree"] = sc_tree
    _init(self, sc_tree, *a, **k)


def _run_w(self, prod_nm, *a, **k):
    r = _run(self, prod_nm, *a, **k)
    GRAB.setdefault("bres", []).append((prod_nm, r))
    return r


def _cap_w(self, node, n_weeks, result):
    if node.node_type != "mom":
        return _cap(self, node, n_weeks, result)
    before = [len(node.psi4demand[w][CO]) for w in range(n_weeks)]
    pd0 = len(result.past_due_lots)
    _cap(self, node, n_weeks, result)
    dropped = GRAB.setdefault("cap_dropped", {}).setdefault(node.node_id, collections.Counter())
    dropped.update(region(lot) for _n, lot, _w in result.past_due_lots[pd0:])
    rec = GRAB.setdefault("pushed", {}).setdefault(node.node_id, {"open": collections.Counter(),
                                                                    "closed": collections.Counter(),
                                                                    "closed_weeks": {}})
    labels = list(node.week_labels or [str(w) for w in range(n_weeks)])
    for w in range(n_weeks):
        new = list(node.psi4demand[w][CO])[before[w]:]
        if not new:
            continue
        c = collections.Counter(region(l) for l in new)
        if node.is_open(w):
            rec["open"].update(c)
        else:
            rec["closed"].update(c)
            rec["closed_weeks"][labels[w]] = dict(c)


BPm.BackwardPlanner.__init__ = _init_w
BPm.BackwardPlanner.run = _run_w
BPm.BackwardPlanner._apply_mom_cap_backward = _cap_w

from tools import run_headless_from_folder as H  # noqa: E402
from wom.plugins.selection import read_recommended_plugins  # noqa: E402


def copy_model(src, dst, policy):
    """Copy src to dst (if dst does not exist) and add overflow_policy (not for tail)."""
    if not os.path.exists(dst):
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "output"))
    set_policy(dst, policy)
    return dst


def set_policy(model_dir, policy):
    pc = os.path.join(model_dir, "planning_config.csv")
    lines = [l for l in open(pc, encoding="utf-8-sig").read().splitlines() if l.strip()
             and not l.startswith("overflow_policy,")]
    if policy != "tail":
        lines.append(f"overflow_policy,{policy}")
    open(pc, "w", encoding="utf-8", newline="").write("\n".join(lines) + "\n")


def capture(model_dir, out_dir, plugins=None, lot_flow_mode=None, ppc=True):
    """One headless run. Returns a dict (JSON-able)."""
    os.makedirs(out_dir, exist_ok=True)
    GRAB.clear()
    plugins = plugins or ",".join(read_recommended_plugins(model_dir)) or "none"
    t0 = time.time()
    snap = H.run(model_dir, plugins_spec=plugins, output_ppc_dir=os.path.join(out_dir, "ppc"), verbose=False,
                 flow_check_dir=os.path.join(out_dir, "flow_check"), lot_flow_mode=lot_flow_mode, ppc=ppc)
    sec = round(time.time() - t0, 1)
    tree = GRAB["tree"]
    market = []
    with open(os.path.join(out_dir, "flow_check", "flow_check_market.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            market.append({"product": r["product"], "leaf": r["leaf"],
                           **{k: int(r[k]) for k in ("demand", "on_time", "early", "late", "backlog_end")}})
    burden, past_due, policy = {}, {}, set()
    for prod, b in GRAB.get("bres", []):
        policy.add(b.overflow_policy)
        for nid, mk in (b.overflow_by_node or {}).items():
            burden[nid] = {m: dict(v) for m, v in mk.items()}
        for nid, lot, _w in b.past_due_lots:
            past_due.setdefault(nid, collections.Counter())[region(lot)] += 1
    moms = {}
    n = tree.num_weeks()
    for prod in tree.products:
        for mom in tree.get_in_roots(prod).values():
            moms[mom.node_id] = {"product": prod, "name": mom.node_name,
                                 "P_supply": sum(len(mom.psi4supply[w][P]) for w in range(n)),
                                 "I_supply": sum(len(mom.psi4supply[w][I]) for w in range(n))}
    pushed = {k: {"open": dict(v["open"]), "closed": dict(v["closed"]), "closed_weeks": v["closed_weeks"]}
              for k, v in GRAB.get("pushed", {}).items()}
    return {"model_dir": os.path.relpath(model_dir, REPO).replace("\\", "/"), "plugins": plugins,
            "policy": sorted(policy), "seconds": sec, "snapshot": snap, "market": market, "burden": burden,
            "past_due": {k: dict(v) for k, v in past_due.items()},
            "past_due_total": sum(sum(v.values()) for v in past_due.values()),
            # the lots the factory capacity cut pushed before the first plan week (stage 0's "dropped")
            "cap_dropped": {k: dict(v) for k, v in GRAB.get("cap_dropped", {}).items() if v},
            "cap_dropped_total": sum(sum(v.values()) for v in GRAB.get("cap_dropped", {}).values()),
            "pushed": pushed, "moms": moms}


def save(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, path)
