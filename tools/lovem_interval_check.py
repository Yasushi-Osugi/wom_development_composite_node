# -*- coding: utf-8 -*-
"""
tools/lovem_interval_check.py — LOVEM の区間データを、元の PSI と独立に、セル（snapshot→node→層→バケット）ごとに照合する
（RequestLetter_RiceSeasonal_Implementation K-R8 の追加指示、2026-10-09）

    python -m tools.lovem_interval_check --model-dir <model> --run-dir <LOVEM の run フォルダ> \
        --plugins <run と同じプラグイン> --out <dir>

やり方：
  1. モデルのコピーを、観測なしで、run と同じプラグインでもう一度計画する。observer と同じ時点
     （Backward の前・後、POST_BACKWARD のフックの後、copy の後、push の設定の後、最後）で、
     この道具自身のコードで、元の PSI から Lot_ID ごとの連続区間と出現数を求める。
  2. その時点の snapshot の区間ファイル（psi_intervals/<product>__<phase>.jsonl.gz）を、セルの塊ごとに
     読みながら（observer はセルごとに続けて書く）、同じセルの区間と照合する。
  3. 照合が済んだセルは捨てる。全 snapshot の「ID×週」をメモリに展開しない（1 セル分だけ持つ）。

区間の求め方（observer の規則と同じ意味、コードは別）：
  * I・CO：同じ Lot_ID が同じ出現数で続く週を一つの区間 [開始, 終了]（両端を含む）
  * P・S：週ごとに一つの区間
  * 出現数は週の中の同じ ID の個数（set で重複を消さない）
照合：区間の多重集合 (Lot_ID, 開始, 終了, 出現数) が一致すること、ID ごとの出現数の合計
（Σ 週数×出現数）が一致すること、区間の役割・数量が既定値であること、同じセルの塊が
ファイルの中で二度出ないこと、ファイルにあって元の PSI に無いセルが無いこと。

出力：<out>/cells.csv（セルごとの開始・終了・区間数・ID 数・出現数・経過時間・結果）、
      <out>/summary.json、標準出力に snapshot ごとの経過。
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO)
from wom.lovem.digest import QTY_PER_OCCURRENCE, ROLE_NONE  # noqa: E402  (the defaults, not the encoder)
BUCKETS = (("S", 0), ("CO", 1), ("I", 2), ("P", 3))
STATE = {"I", "CO"}


def runs_from_psi(weekly, bucket):
    """Lot_ID runs of one cell from the original per-week lists (independent code).

    Returns Counter{(lot, start, end, multiplicity): n} and Counter{lot: occurrences}.
    """
    per_lot = defaultdict(list)                 # lot -> [(week, count)]
    occ = Counter()
    for w, lots in enumerate(weekly):
        if not lots:
            continue
        c = Counter(lots)                       # keeps duplicates as a count
        for lot, k in c.items():
            per_lot[lot].append((w, k))
            occ[lot] += k
    runs = Counter()
    for lot, seq in per_lot.items():
        if bucket not in STATE:
            for w, k in seq:
                runs[(lot, w, w, k)] += 1
            continue
        s, prev_w, prev_k = seq[0][0], seq[0][0], seq[0][1]
        for w, k in seq[1:]:
            if w == prev_w + 1 and k == prev_k:
                prev_w = w
                continue
            runs[(lot, s, prev_w, prev_k)] += 1
            s, prev_w, prev_k = w, w, k
        runs[(lot, s, prev_w, prev_k)] += 1
    return runs, occ


class CellStream:
    """Reads one snapshot file cell block by cell block."""

    def __init__(self, path):
        self.f = gzip.open(path, "rt", encoding="utf-8")
        self.pending = None
        self.seen = set()
        self.anomalies = Counter()

    def _next_rec(self):
        if self.pending is not None:
            r, self.pending = self.pending, None
            return r
        line = self.f.readline()
        return json.loads(line) if line else None

    def blocks(self):
        while True:
            r = self._next_rec()
            if r is None:
                return
            key = (r["node_id"], r["layer"], r["bucket"])
            if key in self.seen:
                self.anomalies["cell_block_repeated"] += 1
            self.seen.add(key)
            runs, occ, n = Counter(), Counter(), 0
            while r is not None and (r["node_id"], r["layer"], r["bucket"]) == key:
                if r.get("role_id") != ROLE_NONE or r.get("quantity") != QTY_PER_OCCURRENCE:
                    self.anomalies["non_default_role_or_quantity"] += 1
                s, e, m = r["start_week_index"], r["end_week_index"], r["multiplicity"]
                runs[(r["lot_id"], s, e, m)] += 1
                occ[r["lot_id"]] += (e - s + 1) * m
                n += 1
                r = self._next_rec()
            self.pending = r
            yield key, runs, occ, n

    def close(self):
        self.f.close()


class Checker:
    def __init__(self, run_dir, out_dir, only=None):
        self.run_dir, self.out = run_dir, out_dir
        self.only = only                        # optional (node_name, layer, bucket) filter for timing
        self.rows, self.snap_summary = [], []
        self.timing = Counter()

    def capture(self, tree, phase, prod, layers):
        snap = f"{prod}/{phase}"
        path = os.path.join(self.run_dir, "psi_intervals", f"{prod}__{phase}.jsonl.gz")
        t0 = time.perf_counter()
        start = datetime.now().isoformat(timespec="seconds")
        if not os.path.exists(path):
            self.snap_summary.append({"snapshot": snap, "error": "no interval file"})
            return
        expected = {}
        for nd in tree.iter_all_nodes(prod):
            for layer in layers:
                for b, _i in BUCKETS:
                    expected[(nd.node_id, layer, b)] = nd
        names = {nd.node_id: nd.node_name for nd in tree.iter_all_nodes(prod)}
        stream = CellStream(path)
        seen = set()
        bad = 0
        for key, iv_runs, iv_occ, n_iv in stream.blocks():
            nid, layer, b = key
            if self.only and (names.get(nid), layer, b) != self.only:
                continue
            c0 = time.perf_counter()
            nd = expected.get(key)
            if nd is None:
                self.rows.append({"snapshot": snap, "node": nid, "layer": layer, "bucket": b,
                                  "result": "cell_not_in_psi", "intervals": n_iv})
                bad += 1
                continue
            seen.add(key)
            psi = nd.psi4demand if layer == "demand" else nd.psi4supply
            idx = dict(BUCKETS)[b]
            r0 = time.perf_counter()
            weekly = [psi[w][idx] for w in range(tree.num_weeks())]
            ps_runs, ps_occ = runs_from_psi(weekly, b)
            r1 = time.perf_counter()
            ok_runs = ps_runs == iv_runs
            ok_occ = ps_occ == iv_occ
            r2 = time.perf_counter()
            self.timing["psi_runs_s"] += r1 - r0
            self.timing["compare_s"] += r2 - r1
            res = "match" if ok_runs and ok_occ else "MISMATCH"
            if res != "match":
                bad += 1
            diff = (ps_runs - iv_runs) + (iv_runs - ps_runs)
            self.rows.append({"snapshot": snap, "node": names[nid], "layer": layer, "bucket": b,
                              "intervals": n_iv, "lots": len(iv_occ), "occurrences": sum(iv_occ.values()),
                              "psi_occurrences": sum(ps_occ.values()),
                              "elapsed_ms": round((time.perf_counter() - c0) * 1000, 1),
                              "result": res, "diff_runs": sum(diff.values()),
                              "diff_example": str(next(iter(diff), ""))[:160]})
        stream.close()
        missing = [k for k in expected if k not in seen and not self.only]
        # a cell with no interval in the file must be empty in the PSI
        for k in missing:
            nd = expected[k]
            psi = nd.psi4demand if k[1] == "demand" else nd.psi4supply
            idx = dict(BUCKETS)[k[2]]
            if any(psi[w][idx] for w in range(tree.num_weeks())):
                bad += 1
                self.rows.append({"snapshot": snap, "node": nd.node_name, "layer": k[1], "bucket": k[2],
                                  "result": "psi_cell_missing_in_file"})
        el = time.perf_counter() - t0
        self.snap_summary.append({"snapshot": snap, "start": start,
                                  "end": datetime.now().isoformat(timespec="seconds"),
                                  "cells": sum(1 for r in self.rows if r["snapshot"] == snap),
                                  "empty_cells_checked": len(missing), "bad": bad,
                                  "anomalies": dict(stream.anomalies), "seconds": round(el, 1)})
        print(f"[interval-check] {snap}: cells {self.snap_summary[-1]['cells']}, bad {bad}, "
              f"{round(el, 1)} s ({start} -> {self.snap_summary[-1]['end']})", flush=True)


def replay(model_dir, plugins, checker):
    """Unobserved plan of a COPY, with checks at the observer's snapshot points."""
    import tools.run_headless_from_folder as rh
    import wom.engine.backward_planner as bp
    import wom.engine.hook_bus as hb
    import wom.engine.plan_copy as pc
    import wom.engine.push_pull as ppm
    st = {}
    saved = []

    def patch(owner, name, new):
        saved.append((owner, name, getattr(owner, name)))
        setattr(owner, name, new)

    o_brun = bp.BackwardPlanner.run

    def brun(self, prod):
        checker.capture(st["tree"], "pre_backward", prod, ["demand"])
        r = o_brun(self, prod)
        checker.capture(st["tree"], "post_backward", prod, ["demand"])
        return r

    o_fire = hb.HookBus.fire

    def fire(self, hook, **ctx):
        o_fire(self, hook, **ctx)
        if hook == hb.HOOK_PRE_PLAN:
            st["tree"] = ctx["sc_tree"]
        if hook == hb.HOOK_POST_BACKWARD and ctx.get("prod_nm"):
            checker.capture(ctx["sc_tree"], "post_backward_hooks", ctx["prod_nm"], ["demand"])

    o_copy = pc.copy_demand_to_supply

    def copy(tree, prod, *a, **k):
        r = o_copy(tree, prod, *a, **k)
        checker.capture(tree, "post_copy", prod, ["supply"])
        return r

    o_setup = ppm.PushProductionPlanner.setup_all

    def setup_all(self, cfgs):
        r = o_setup(self, cfgs)
        for prod in cfgs:
            checker.capture(st["tree"], "post_push_setup", prod, ["supply"])
        return r

    o_sig = rh._psi_signature

    def sig(tree, n):
        for prod in tree.products:
            checker.capture(tree, "final", prod, ["demand", "supply"])
        return o_sig(tree, n)

    patch(bp.BackwardPlanner, "run", brun)
    patch(hb.HookBus, "fire", fire)
    patch(pc, "copy_demand_to_supply", copy)
    patch(ppm.PushProductionPlanner, "setup_all", setup_all)
    patch(rh, "_psi_signature", sig)
    tmp = tempfile.mkdtemp(prefix="iv_chk_")
    try:
        work = os.path.join(tmp, os.path.basename(model_dir.rstrip("/\\")))
        shutil.copytree(model_dir, work)
        return rh.run(work, plugins_spec=plugins, output_ppc_dir=os.path.join(work, "_ppc"), verbose=False)
    finally:
        for owner, name, orig in reversed(saved):
            setattr(owner, name, orig)
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--plugins", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", help="node_name,layer,bucket -- check one cell only (timing)")
    a = ap.parse_args(argv)
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    os.makedirs(a.out, exist_ok=True)
    only = tuple(a.only.split(",")) if a.only else None
    ck = Checker(os.path.abspath(a.run_dir), a.out, only)
    t0 = time.perf_counter()
    started = datetime.now().isoformat(timespec="seconds")
    replay(a.model_dir, a.plugins, ck)
    observed = {p["snapshot_id"] for p in json.load(open(os.path.join(a.run_dir, "manifest.json"),
                                                         encoding="utf-8"))["snapshots"]}
    checked = {s["snapshot"] for s in ck.snap_summary}
    summary = {"started": started, "ended": datetime.now().isoformat(timespec="seconds"),
               "seconds": round(time.perf_counter() - t0, 1), "only": only,
               "snapshots_in_run": sorted(observed), "snapshots_checked": sorted(checked),
               "snapshots_not_checked": sorted(observed - checked),
               "cells": len(ck.rows), "bad_cells": sum(r["result"] != "match" for r in ck.rows),
               "intervals": sum(r.get("intervals", 0) for r in ck.rows),
               "occurrences": sum(r.get("occurrences", 0) for r in ck.rows),
               "timing": {k: round(v, 2) for k, v in ck.timing.items()},
               "snapshots": ck.snap_summary,
               "all_match": (not only and observed == checked and
                             all(r["result"] == "match" for r in ck.rows) and
                             all(not s.get("bad") and not s.get("anomalies") and not s.get("error")
                                 for s in ck.snap_summary))}
    with open(os.path.join(a.out, "cells.csv"), "w", encoding="utf-8", newline="") as f:
        keys = list(dict.fromkeys(k for r in ck.rows for k in r))
        w = csv.DictWriter(f, keys, lineterminator="\n")
        w.writeheader()
        w.writerows(ck.rows)
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "snapshots"}, ensure_ascii=False, indent=1))
    return 0 if summary["all_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
