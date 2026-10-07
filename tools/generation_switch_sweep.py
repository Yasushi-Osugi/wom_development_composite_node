# -*- coding: utf-8 -*-
"""
tools/generation_switch_sweep.py — 世代の切り替えの週 s を並べ、候補ごとに上位の層の LP を解く
（RequestLetter_GenerationLine_UpperLayer §4.1、受入 1・3）

    python -m tools.generation_switch_sweep --model-dir data/sample/smartx-2027-2029 \
        --out output/generation_line/sweep_w17 --window 17 --from 2027-W27 --to 2030-W27

1. モデルのコピーを headless で計画し、Backward の直後の木から、旧世代・新世代の上位の問題を作る
   （CapacityLayerPlugin を apply=False・capture で動かす。計画には触れない）。
2. ラインの能力 ＝ 各世代のピークの週の需要（全市場の合計）× factor（切り上げ）。
3. 候補 s ごとに、ラインの能力の並び（wom/capacity_layer/generation_line.line_schedule）で LP を解く。
4. 出力：sweep.csv（候補ごとの表）、capacity.json（能力の値と計算）、best.json（s* と理由）、
   sweep.png（横軸 s、縦軸に未割当と在庫の lot・週）。

元のモデルは変えない（コピーで実行）。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SMARTX_PLUGINS = "BufferingStockOptimizerPlugin,CapacityOverridePlugin,HolidayCalendarPlugin"


def capture_problems(model_dir, window, plugins=SMARTX_PLUGINS):
    """{product: (adapter, problem)} from a headless run of a COPY of the model."""
    import tools.run_headless_from_folder as rh
    from wom.plugins.capacity_layer import CapacityLayerPlugin
    cap = {}
    tmp = tempfile.mkdtemp(prefix="gl_sweep_")
    try:
        work = os.path.join(tmp, os.path.basename(model_dir.rstrip("/\\")))
        shutil.copytree(model_dir, work)
        pl = CapacityLayerPlugin(max_advance_weeks=window, apply=False, capture=cap)
        rh.run(work, plugins_spec=plugins, output_ppc_dir=os.path.join(work, "_ppc"),
               verbose=False, extra_plugins=[pl])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return cap


def plot_sweep(rows, best, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs = [r["s_index"] for r in rows]
    labels = [r["s_week"] for r in rows]
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.plot(xs, [r["old_unallocated"] for r in rows], color="#1f77b4", lw=1.4,
            label="Unallocated: old generation")
    ax.plot(xs, [r["new_unallocated"] for r in rows], color="#ff7f0e", lw=1.4,
            label="Unallocated: new generation")
    ax.plot(xs, [r["unallocated_total"] for r in rows], color="black", lw=2.0,
            label="Unallocated: total")
    ax.set_ylabel("Unallocated lots (not by the original request week)")
    ax2 = ax.twinx()
    ax2.plot(xs, [r["advance_lot_weeks_total"] for r in rows], color="#2ca02c", lw=1.2, ls="--",
             label="Inventory lot-weeks (advance, both generations)")
    ax2.set_ylabel("Inventory lot-weeks (prebuild)")
    if best:
        ax.axvline(best["s_index"], color="crimson", lw=1.2, ls=":")
        ax.annotate(f"s* = {best['s_week']}\nunallocated {best['unallocated_total']:,}",
                    xy=(best["s_index"], best["unallocated_total"]), xytext=(10, 30),
                    textcoords="offset points", color="crimson", fontsize=9,
                    arrowprops=dict(arrowstyle="->", color="crimson"))
    step = max(1, len(xs) // 12)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels(labels[::step], rotation=45, ha="right", fontsize=8)
    ax.set_xlabel("Switch week s (last old-generation line week = s-1)")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", fontsize=8, ncol=2)
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--old", default="SmartX:AssemblyCN_g1", help="旧世代 product:line_node")
    ap.add_argument("--new", default="SmartXNext:AssemblyCN_g3", help="新世代 product:line_node")
    ap.add_argument("--gap", type=int, default=4, help="切り替えの空き期間（週）")
    ap.add_argument("--factor", type=float, default=1.1, help="ラインの能力 = ピークの週の需要 × factor")
    ap.add_argument("--window", type=int, default=17, help="前倒しの窓（週）")
    ap.add_argument("--from", dest="s_from", default="2027-W27")
    ap.add_argument("--to", dest="s_to", default="2030-W27")
    ap.add_argument("--step", type=int, default=1)
    a = ap.parse_args(argv)
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    from wom.capacity_layer.generation_line import (line_capacity_from_demand, sweep_switch_weeks,
                                                    best_switch)
    os.makedirs(a.out, exist_ok=True)
    old_p, old_n = a.old.split(":")
    new_p, new_n = a.new.split(":")
    with open(os.path.join(a.model_dir, "demand_forecast.csv"), encoding="utf-8-sig", newline="") as f:
        demand = list(csv.DictReader(f))
    c_old = line_capacity_from_demand(demand, old_p, a.factor)
    c_new = line_capacity_from_demand(demand, new_p, a.factor)
    t0 = time.perf_counter()
    cap = capture_problems(a.model_dir, a.window)
    old = (*cap[old_p], old_n)
    new = (*cap[new_p], new_n)
    weeks = old[0].weeks
    i0, i1 = weeks.index(a.s_from), weeks.index(a.s_to)
    cands = list(range(i0, i1 + 1, a.step))
    if cands[-1] != i1:
        cands.append(i1)
    with open(os.path.join(a.out, "capacity.json"), "w", encoding="utf-8") as f:
        json.dump({"factor": a.factor, "rule": "ceil(peak weekly demand over all markets x factor)",
                   "lines": [dict(vars(c_old), line_node=old_n), dict(vars(c_new), line_node=new_n)],
                   "gap_weeks": a.gap, "window_weeks": a.window,
                   "candidates": [weeks[i] for i in cands],
                   "unset_capacity_nodes": {p: cap[p][1].metadata["unset_capacity_nodes"]
                                            for p in (old_p, new_p)},
                   "options": {p: len(cap[p][1].options) for p in (old_p, new_p)}},
                  f, ensure_ascii=False, indent=1)
    print(f"capacity: {old_n}={c_old.capacity} ({c_old.peak_demand}@{c_old.peak_week}), "
          f"{new_n}={c_new.capacity} ({c_new.peak_demand}@{c_new.peak_week}); "
          f"{len(cands)} candidates, window {a.window}", flush=True)

    def prog(r):
        print(f"  s={r['s_week']} unalloc old={r['old_unallocated']} new={r['new_unallocated']} "
              f"adv={r['advance_lot_weeks_total']} ({r['elapsed_seconds']}s)", flush=True)

    rows = sweep_switch_weeks(old, new, cands, a.gap, c_old.capacity, c_new.capacity, progress=prog)
    with open(os.path.join(a.out, "sweep.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    best = best_switch(rows)
    tied = [r["s_week"] for r in rows if r["unallocated_total"] == best["unallocated_total"]]
    with open(os.path.join(a.out, "best.json"), "w", encoding="utf-8") as f:
        json.dump({"best": best,
                   "rule": "min unallocated_total, then min advance_lot_weeks_total, then earliest s",
                   "candidates_with_same_unallocated": tied,
                   "elapsed_seconds": round(time.perf_counter() - t0, 1)}, f, ensure_ascii=False, indent=1)
    plot_sweep(rows, best, os.path.join(a.out, "sweep.png"),
               f"Switch week vs result ({old_n} {c_old.capacity}/wk -> {a.gap}-week gap -> "
               f"{new_n} {c_new.capacity}/wk, prebuild window {a.window} wks)")
    print("best:", best["s_week"], best["unallocated_total"], best["advance_lot_weeks_total"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
