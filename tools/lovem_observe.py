# -*- coding: utf-8 -*-
"""
tools/lovem_observe.py — LOVEM stage A: observe one model run into a run folder.

    python -m tools.lovem_observe --model-dir data/sample/ev-thailand-2026 \
        --out output/lovem/ev-thailand-2026/run_A --q12 --se2-compare-sha 4ed2f14

Steps
  1. observe_run(): headless planning + PPC with read-only observation wrappers
     -> manifest.json, nodes.csv, weeks.csv, capacity.csv, demand_anchors.jsonl,
        psi_intervals.jsonl, state_digests.jsonl, events.jsonl, relations.jsonl,
        source_evidence.jsonl, headless_snapshot.json, ppc/
  2. verify_run(): decode intervals and compare with state_digests -> verify.json
  3. --q12: fingerprint the same model with observation OFF and ON -> q12.json
  4. se2_case.json (definition + weekly counts; no classification).
     --se2-compare-sha: also run the pre-Explicit-Closure code (git archive of
     that SHA into a temp dir; the repository is not touched) for the comparison
     column.

The model folder is copied to a temp dir before running; originals are not written.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

_COMPARE_SCRIPT = r'''
import json, sys, os
sys.path.insert(0, os.getcwd())
import tools.run_headless_from_folder as rh
import wom.engine.forward_planner as fpm
store = {}
o = fpm.ForwardPlanner.run
def run(self, prod):
    r = o(self, prod)
    store[prod] = {k: {w: len(v) for w, v in d.items()} for k, d in self._actual_s.items()}
    return r
fpm.ForwardPlanner.run = run
os_ = rh._psi_signature
def sig(t, n):
    store["_tree"] = t
    return os_(t, n)
rh._psi_signature = sig
snap = rh.run(sys.argv[1], plugins_spec=sys.argv[2], output_ppc_dir=sys.argv[3], verbose=False)
t = store["_tree"]; prod, name = sys.argv[4], sys.argv[5]
nd = next(n for n in t.iter_all_nodes(prod) if n.node_name == name)
act = store[prod].get(nd.node_id, {})
sf = getattr(nd, "_push_shortfall", None) or {}
rows = []
for w, lbl in enumerate(t.week_labels):
    p = len(nd.psi4supply[w][0]); a = act.get(w, 0)
    rows.append({"week_index": w, "week": lbl, "planned_s": p, "actual_s": a,
                 "signed_gap": p - a, "shortfall": max(0, p - a), "excess": max(0, a - p),
                 "push_shortfall": int(sf.get(w, 0))})
print("@@JSON@@" + json.dumps({"rows": rows, "ppc": snap["ppc"]}))
'''


def run_comparison(repo: str, sha: str, model_rel: str, plugins: str, product: str, node_name: str) -> dict:
    from wom.lovem.se2 import SE2
    tmp = tempfile.mkdtemp(prefix="lovem_cmp_")
    try:
        full = subprocess.run(["git", "rev-parse", sha], cwd=repo, capture_output=True,
                              text=True, check=True).stdout.strip()
        tar = subprocess.run(["git", "archive", "--format=tar", full, "wom", "tools", model_rel],
                             cwd=repo, capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(tar)) as tf:
            tf.extractall(tmp)
        out = subprocess.run([sys.executable, "-c", _COMPARE_SCRIPT, model_rel, plugins,
                              os.path.join(tmp, "_ppc"), product, node_name],
                             cwd=tmp, capture_output=True, text=True,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        line = next((l for l in out.stdout.splitlines() if l.startswith("@@JSON@@")), None)
        if line is None:
            raise RuntimeError(f"comparison run failed:\n{out.stdout[-2000:]}\n{out.stderr[-4000:]}")
        data = json.loads(line[len("@@JSON@@"):])
        rows = data["rows"]
        tw = [r for r in rows if r["week"] in SE2["target_weeks"]]
        return {"code_sha": full, "method": "git archive <sha> wom tools <model> into a temp dir; same plugins; headless run",
                "target_week_rows": tw,
                "horizon_totals": {"actual_s": sum(r["actual_s"] for r in rows),
                                   "planned_s": sum(r["planned_s"] for r in rows),
                                   "push_shortfall": sum(r["push_shortfall"] for r in rows)},
                "ppc": data["ppc"]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    from wom.lovem.observer import GOLDEN_PLUGINS, observe_run
    from wom.lovem.verify import verify_run
    from wom.lovem.se2 import SE2, build_se2_case

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--plugins", default=GOLDEN_PLUGINS)
    ap.add_argument("--label", default="obs")
    ap.add_argument("--q12", action="store_true")
    ap.add_argument("--se2-compare-sha", default=None)
    a = ap.parse_args(argv)
    repo = os.getcwd()

    if os.path.exists(a.out) and os.listdir(a.out):
        print(f"[lovem] output folder not empty: {a.out}", file=sys.stderr)
        return 2
    t0 = time.perf_counter()
    observe_run(a.model_dir, a.out, plugins=a.plugins, repo=repo, label=a.label)
    t_obs = time.perf_counter() - t0
    t0 = time.perf_counter()
    v = verify_run(a.out)
    t_ver = time.perf_counter() - t0
    json.dump(v, open(os.path.join(a.out, "verify.json"), "w", encoding="utf-8"), indent=2)
    print(f"[lovem] observe {t_obs:.1f}s  verify {t_ver:.1f}s  digests {v['digest_rows_matched']}/{v['digest_rows']}"
          f"  all_match={v['all_match']}")

    if a.q12:
        from wom.lovem.q12 import compare_on_off
        tmp = tempfile.mkdtemp(prefix="lovem_q12obs_")
        try:
            r = compare_on_off(a.model_dir, a.plugins, observe_out=tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        json.dump(r, open(os.path.join(a.out, "q12.json"), "w", encoding="utf-8"), indent=2)
        print(f"[lovem] Q12 identical={r['identical']}  cells={r['n_cells']}  diffs={r['top_level_diffs']} {r['cell_diffs'][:5]}")

    comparison = None
    if a.se2_compare_sha and os.path.basename(os.path.abspath(a.model_dir)) == "ev-thailand-2026":
        comparison = run_comparison(repo, a.se2_compare_sha, SE2["model_dir"], a.plugins,
                                    SE2["product_id"], SE2["node_name"])
    if os.path.basename(os.path.abspath(a.model_dir)) == "ev-thailand-2026":
        case = build_se2_case(a.out, comparison)
        print(f"[lovem] SE2 rows={case['target_week_rows']}  which_is_168={case['which_is_168']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
