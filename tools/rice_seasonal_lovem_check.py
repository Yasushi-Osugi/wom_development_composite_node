# -*- coding: utf-8 -*-
"""
tools/rice_seasonal_lovem_check.py — Rice の LOVEM の照合を、観測済みの run フォルダに対して段階ごとに行う
（RequestLetter_RiceSeasonal_Implementation K-R8）

    python -m tools.rice_seasonal_lovem_check --model-dir data/sample/rice-japan-2027-2028 \
        --run-dir output/rice_seasonal/C/lovem_on [--skip-restore]

run フォルダは `python -m tools.rice_seasonal_check ... --lovem` が作る（観測つきの計画）。
1. 観測なしで同じ計画をもう一度実行し、snapshot（psi・ppc・forward）が観測つきと同じこと
2. LOVEM の actual_ship イベントと、観測なしの計画の木の実出荷が、全ノードで (ノード, 週, ID) の多重集合として 1 対 1
3. 区間の復元（wom.lovem.verify.verify_run）。Rice は ID×週のセルが多く時間がかかる（所要時間を記録）
結果は <run-dir>/../lovem_check.json。
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from collections import Counter

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--skip-restore", action="store_true")
    a = ap.parse_args(argv)
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    from tools.rice_seasonal_check import plan
    out = {}
    t0 = time.perf_counter()
    snap, tree, _f = plan(a.model_dir)
    obs = json.load(open(os.path.join(a.run_dir, "headless_snapshot.json"), encoding="utf-8"))
    out["snapshot_equal"] = {k: obs.get(k) == snap.get(k) for k in ("psi", "ppc", "forward", "products", "period")}
    tr = Counter((nd.node_id, w, l) for p in tree.products for nd in tree.iter_all_nodes(p)
                 for w, lots in nd._actual_ship.items() for l in lots)
    leaf = {nd.node_id for p in tree.products for nd in tree.iter_all_nodes(p) if nd.node_type == "leaf_out"}
    del tree
    ev = Counter()
    with gzip.open(os.path.join(a.run_dir, "events.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("event_type") == "actual_ship":
                ev[(e["node_id"], e["week_index"], e["lot_id"])] += 1
    out["actual_ship"] = {"lovem_events": sum(ev.values()), "tree_shipments": sum(tr.values()),
                          "all_nodes_one_to_one": ev == tr,
                          "market_events": sum(v for k, v in ev.items() if k[0] in leaf),
                          "market_one_to_one": Counter({k: v for k, v in ev.items() if k[0] in leaf})
                          == Counter({k: v for k, v in tr.items() if k[0] in leaf})}
    out["seconds_1_2"] = round(time.perf_counter() - t0, 1)
    print(json.dumps(out, indent=1), flush=True)
    if not a.skip_restore:
        from wom.lovem.verify import verify_run
        t1 = time.perf_counter()
        vr = verify_run(a.run_dir)
        out["interval_restore"] = {k: vr.get(k) for k in ("digest_rows", "digest_rows_matched", "all_match")}
        out["interval_restore"]["seconds"] = round(time.perf_counter() - t1, 1)
        print(json.dumps(out["interval_restore"], indent=1), flush=True)
    with open(os.path.join(os.path.dirname(os.path.abspath(a.run_dir)), "lovem_check.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
