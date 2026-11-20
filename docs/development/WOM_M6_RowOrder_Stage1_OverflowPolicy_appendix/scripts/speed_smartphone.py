# -*- coding: utf-8 -*-
"""段 1 §4：smartphone-global-2026-2029 の写しで 3 方式を 1 回ずつ回し、所要時間を測る（参考）。

    python output/roworder_stage1/speed_smartphone.py [tail ...]

結果は output/roworder_stage1/speed/<policy>.json（あればとばす）。Backward の時間は BackwardPlanner.run の合計。
"""
import json
import os
import shutil
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)
OUT = os.path.join(REPO, "output", "roworder_stage1", "speed")
MODEL = "smartphone-global-2026-2029"

from wom.engine import backward_planner as BPm  # noqa: E402

T = {"backward": 0.0, "bres": []}
_run = BPm.BackwardPlanner.run


def run_(self, prod_nm, *a, **k):
    t0 = time.time()
    r = _run(self, prod_nm, *a, **k)
    T["backward"] += time.time() - t0
    T["bres"].append(r)
    return r


BPm.BackwardPlanner.run = run_
from tools.run_headless_from_folder import run  # noqa: E402


def one(policy):
    out = os.path.join(OUT, policy + ".json")
    if os.path.exists(out):
        print("[skip]", policy)
        return
    d = os.path.join(OUT, policy, "model")
    if not os.path.exists(d):
        shutil.copytree(os.path.join(REPO, "data", "sample", MODEL), d)
        if policy != "tail":
            pc = os.path.join(d, "planning_config.csv")
            text = open(pc, encoding="utf-8-sig").read() if os.path.exists(pc) else "key,value\n"
            if not text.endswith("\n"):
                text += "\n"
            open(pc, "w", encoding="utf-8", newline="").write(text + f"overflow_policy,{policy}\n")
    golden = json.load(open(os.path.join(REPO, "tests", "golden", MODEL + ".json"), encoding="utf-8"))
    plugins = ",".join(golden["config"]["plugins"]) or "none"
    mode = golden["config"].get("lot_flow_mode")
    T["backward"], T["bres"] = 0.0, []
    t0 = time.time()
    snap = run(d, plugins_spec=plugins, output_ppc_dir=os.path.join(OUT, policy, "ppc"), verbose=False,
               lot_flow_mode=mode)
    total = time.time() - t0
    pushed = {nid: sum(v["pushed"] for v in mk.values()) for b in T["bres"] for nid, mk in getattr(b, "overflow_by_node", {}).items()}
    res = {"policy": policy, "total_seconds": round(total, 1), "backward_seconds": round(T["backward"], 1),
           "pushed_by_factory": pushed, "past_due": sum(len(b.past_due_lots) for b in T["bres"]),
           "golden_psi_match": snap.get("psi") == golden.get("psi"), "ppc": snap.get("ppc")}
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[done] {policy} total {res['total_seconds']}s backward {res['backward_seconds']}s "
          f"golden_psi_match={res['golden_psi_match']}")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for p in (sys.argv[1:] or ["tail", "proportional_week", "balance_cut_ratio"]):
        one(p)
