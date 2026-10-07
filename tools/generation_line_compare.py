# -*- coding: utf-8 -*-
"""
tools/generation_line_compare.py — 上位の層 OFF／ON の比較と、元の要求の照合
（RequestLetter_GenerationLine_UpperLayer 受入 2・4・5）

    python -m tools.generation_line_compare --model-dir data/sample/smartx-2027-2029 \
        --out output/generation_line/compare

モデルのコピーを、LOVEM の観測つき（wom/lovem/observer.observe_run）で 2 回計画する：
  OFF : smartx の golden と同じプラグイン
  ON  : それに CapacityLayerPlugin を足す（窓は capacity_layer_config.csv）

製品ごとに：需要・元の要求週に出荷・遅配・早出し・期末の注文残・上位の層で割り当てられない lot・
能力による繰り延べ（Forward、identity）・在庫の lot・週（全ノードの I の合計）・PPC の売上と粗利。
照合：
  受入 2  混流しない — ラインの 2 ノードの P が同じ週に両方正にならない、空き期間は両方 0
  受入 5  ON と OFF で市場の要求（Lot_ID と要求週）が同じ。市場の出荷の記録（木の _actual_ship）と
          LOVEM の観測の actual_ship イベント（市場ノード）が 1 対 1 で一致する
出力：<out>/compare.json、<out>/compare_products.csv、<out>/lovem_off|lovem_on（観測の run フォルダ）。
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
from collections import Counter, defaultdict

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PLUGINS = "BufferingStockOptimizerPlugin,CapacityOverridePlugin,HolidayCalendarPlugin"


def run_case(model_dir, out_dir, plugins):
    """Observed headless run on a copy; returns (snapshot, tree, forward results)."""
    import tools.run_headless_from_folder as rh
    import wom.engine.forward_planner as fpm
    from wom.lovem.observer import observe_run
    store = {"fres": {}}
    o_sig, o_run = rh._psi_signature, fpm.ForwardPlanner.run

    def sig(t, n):
        store["tree"] = t
        return o_sig(t, n)

    def frun(self, prod):
        r = o_run(self, prod)
        store["fres"][prod] = r
        return r

    rh._psi_signature, fpm.ForwardPlanner.run = sig, frun
    try:
        snap = observe_run(model_dir, out_dir, plugins=plugins, repo=REPO, label=os.path.basename(out_dir))
    finally:
        rh._psi_signature, fpm.ForwardPlanner.run = o_sig, o_run
    return snap, store["tree"], store["fres"]


def market(tree):
    """{product: {leaf_id: (due {lot: w}, ship {lot: w})}}"""
    out = defaultdict(dict)
    for p in tree.products:
        for nd in tree.iter_all_nodes(p):
            if nd.node_type != "leaf_out":
                continue
            due = {lot: w for w in range(tree.num_weeks()) for lot in nd.psi4demand[w][0]}
            ship = {}
            for w, lots in nd._actual_ship.items():
                for lot in lots:
                    ship.setdefault(lot, w)
            out[p][nd.node_id] = (due, ship)
    return out


def lovem_market_ships(run_dir, leaf_ids):
    c = Counter()
    with gzip.open(os.path.join(run_dir, "events.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("event_type") == "actual_ship" and e.get("node_id") in leaf_ids:
                c[(e["node_id"], e["week_index"], e["lot_id"])] += 1
    return c


def tree_market_ships(tree):
    c = Counter()
    for p in tree.products:
        for nd in tree.iter_all_nodes(p):
            if nd.node_type == "leaf_out":
                for w, lots in nd._actual_ship.items():
                    for lot in lots:
                        c[(nd.node_id, w, lot)] += 1
    return c


def ppc_by_product(run_dir):
    path = os.path.join(run_dir, "ppc", "ppc_node_pl_summary.csv")
    out = defaultdict(lambda: {"revenue": 0.0, "gross_profit": 0.0})
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out[r["product_id"]]["revenue"] += float(r["revenue_base"] or 0)
            out[r["product_id"]]["gross_profit"] += float(r["gross_profit_base"] or 0)
    return out


def summarise(tag, tree, fres, run_dir, layer):
    from wom.model.plan_node import I
    mk = market(tree)
    ppc = ppc_by_product(run_dir)
    rows = []
    for p in tree.products:
        d = Counter()
        for due, ship in mk[p].values():
            for lot, dw in due.items():
                aw = ship.get(lot)
                d["demand"] += 1
                d["on_time" if aw == dw else "late" if aw is not None and aw > dw
                  else "early" if aw is not None else "backlog_end"] += 1
        inv = sum(len(nd.psi4supply[w][I]) for nd in tree.iter_all_nodes(p) for w in range(tree.num_weeks()))
        f = fres[p]
        lr = (layer or {}).get(p)
        rows.append({"case": tag, "product": p, **{k: d[k] for k in ("demand", "on_time", "late", "early", "backlog_end")},
                     "unallocated_by_layer": lr["unallocated"] if lr else "",
                     "layer_advance_lot_weeks": lr["advance_lot_weeks"] if lr else "",
                     "cap_deferred_lots": int(getattr(f, "cap_hard_deferred_lots", 0) or 0),
                     "cap_deferred_lot_weeks": int(getattr(f, "cap_hard_deferred_lot_weeks", 0) or 0),
                     "inventory_lot_weeks": inv,
                     "ppc_revenue": round(ppc[p]["revenue"], 2), "ppc_gross_profit": round(ppc[p]["gross_profit"], 2)})
    return rows


def no_mixed_flow(tree, old=("SmartX", "AssemblyCN_g1"), new=("SmartXNext", "AssemblyCN_g3")):
    """Weeks where both lines produce (must be none) and production in the changeover weeks."""
    from wom.model.plan_node import P
    a = next(n for n in tree.iter_all_nodes(old[0]) if n.node_name == old[1])
    b = next(n for n in tree.iter_all_nodes(new[0]) if n.node_name == new[1])
    wl, n = tree.week_labels, tree.num_weeks()
    pa = [len(a.psi4supply[w][P]) for w in range(n)]
    pb = [len(b.psi4supply[w][P]) for w in range(n)]
    last_cap_old = max(w for w in range(n) if (a.cap_hard(w) or 0) > 0)
    first_cap_new = min(w for w in range(n) if (b.cap_hard(w) or 0) > 0)
    gap = range(last_cap_old + 1, first_cap_new)
    return {"weeks_both_positive": [wl[w] for w in range(n) if pa[w] > 0 and pb[w] > 0],
            "changeover_weeks": [wl[w] for w in gap],
            "changeover_production": sum(pa[w] + pb[w] for w in gap),
            "last_old_production_week": max((wl[w] for w in range(n) if pa[w]), default=None),
            "first_new_production_week": min((wl[w] for w in range(n) if pb[w]), default=None),
            "old_production_after_line_stop": sum(pa[w] for w in range(last_cap_old + 1, n)),
            "new_production_before_line_start": sum(pb[w] for w in range(first_cap_new))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    os.makedirs(a.out, exist_ok=True)
    res, trees, rows = {}, {}, []
    for tag, plugins in (("off", PLUGINS), ("on", PLUGINS + ",CapacityLayerPlugin")):
        run_dir = os.path.abspath(os.path.join(a.out, f"lovem_{tag}"))
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir)
        snap, tree, fres = run_case(a.model_dir, run_dir, plugins)
        trees[tag] = tree
        layer = getattr(tree, "capacity_layer_results", None) if tag == "on" else None
        rows += summarise(tag, tree, fres, run_dir, layer)
        leaf_ids = {nd.node_id for p in tree.products for nd in tree.iter_all_nodes(p) if nd.node_type == "leaf_out"}
        lv, tr = lovem_market_ships(run_dir, leaf_ids), tree_market_ships(tree)
        res[tag] = {"forward": snap["forward"], "ppc": snap["ppc"],
                    "lovem_market_ship_events": sum(lv.values()), "tree_market_ships": sum(tr.values()),
                    "lovem_matches_tree_one_to_one": lv == tr,
                    "no_mixed_flow": no_mixed_flow(tree)}
        if layer:
            res[tag]["layer"] = {p: {k: v for k, v in r.items() if k not in ("assignments", "unallocated_lots")}
                                 for p, r in layer.items()}
            with open(os.path.join(a.out, "unallocated_lots.csv"), "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["product", "lot_id", "market", "request_week"])
                for p, r in layer.items():
                    for lot, m, wk in r["unallocated_lots"]:
                        w.writerow([p, lot, m, wk])
        print(tag, res[tag]["forward"], "LOVEM 1:1", res[tag]["lovem_matches_tree_one_to_one"], flush=True)
    m_off, m_on = market(trees["off"]), market(trees["on"])
    res["market_request_identical"] = all(
        {k: v[0] for k, v in m_off[p].items()} == {k: v[0] for k, v in m_on[p].items()} for p in m_off)
    with open(os.path.join(a.out, "compare_products.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    res["products"] = rows
    with open(os.path.join(a.out, "compare.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    for r in rows:
        print(r)
    print("market request identical:", res["market_request_identical"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
