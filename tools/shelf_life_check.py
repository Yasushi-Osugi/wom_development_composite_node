# -*- coding: utf-8 -*-
"""
tools/shelf_life_check.py — 残存期間の判定（先入れ先出しの年齢）
==============================================================
RequestLetter_WarmupSoft_BlankAttrs_ShelfLifeFIFO Part C（大杉さんの決定 b・f、2026-10-25）。

    python -m tools.shelf_life_check --model-dir <モデル> --max-age-weeks 52 [--plugins …] [--out <フォルダ>]
        [--demand-file demand_forecast_Q01.csv --warmup-real-start 2027-W01]

数量配分モード（tools/run_quantity_allocation.py）で作った計画の年齢は、配分済みの需要 CSV と、
その実行の warmup の基準の週（Q<nn>.json の fixed.warmup_real_start）を渡して測る
（RequestLetter_BSSEAF_Cosmetics_AllocationP2a Part A）。既定の呼び方の動きは変えない。

市場への納品（leaf_out の実出荷）ごとに、**先入れ先出しで出荷したと考えたときの製品の年齢**を数える。
エンジンは変えない（Lot_ID は需要の単位のまま。Lot_ID は物理の個体ではない：決定記録 §1.1）。

- 製造週：工場（MOM）の実出荷週。MOM → supply point の受け渡しは仮想で、作り置きが supply point の
  I にいる間は、物理的には工場の完成品倉庫にいる（Start Here §2.1）。
- 物の在る所（supply point＝工場の完成品倉庫、DAD、leaf_out の店頭）ごと・SKU ごとに待ち行列を持つ。
  入ってきた物に「製造週」の札を付けて並べ、出ていく物は**一番古い札**から出す。区間を移動中の物は
  札を持ったまま運ばれ、着いた週に着いた所の列に入る。
- 年齢 ＝ 納品週 − 製造週（計画の週の番号。ISO の週ラベルを引き算しない）。単位は lot。
- 入力は段階 D の出荷の記録（`wom/valuechain/records.py` の `build_records`）。週の中は上流から
  （`NodeInfo.rank`）処理するので、同じ週の受け渡し（MOM → supply point）も正しく並ぶ。
- 参考の列：Lot_ID で数えた滞留 ＝ max（需要週、市場の実出荷週）− その Lot_ID の工場の出荷週。
- 期末注文残（市場の実出荷が無い需要）は納品ではないので数えない。件数だけ出す。

止める条件（黙って 0 や負の年齢にしない）：ある所から出ていく数がその週にある数を超える、
市場への納品の総数が市場の実出荷の総数と合わない、着く週が出る週より前。
"""
from __future__ import annotations

import argparse
import csv
import heapq
import os
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

K_HANDOFF = "handoff_to_sp"
K_OUTBOUND = "outbound_move"
K_CONSUMER = "consumer_sale"


class ShelfLifeError(ValueError):
    """The shipment records do not add up (a place ships more than it holds, ...)."""


def compute_fifo(shipments, ranks: Dict[Tuple[str, str], int], week_labels: List[str]) -> dict:
    """FIFO ages from shipment records (wom.valuechain.records.Shipment-like objects).

    ranks: (product, node_name) -> processing order inside a week (upstream first).
    Returns {"deliveries": [row, ...], "in_transit_end": n, "left_in_place": {place: n}}.
    """
    n = len(week_labels)
    exits = defaultdict(list)          # (week, rank, product, place) -> [shipment]
    factory_week: Dict[Tuple[str, str], int] = {}
    for s in shipments:
        if s.kind == K_HANDOFF:
            # production: the lot enters the factory's finished goods (the supply point)
            factory_week.setdefault((s.product, s.lot_id), s.week)
            if s.arrival_week is None or not s.arrival_in_horizon:
                raise ShelfLifeError(f"{s.product}: hand-off of {s.lot_id} at week "
                                     f"{week_labels[s.week]} did not reach the supply point")
            exits[(s.week, -1, s.product, "<production>")].append(s)
        elif s.kind in (K_OUTBOUND, K_CONSUMER):
            exits[(s.week, ranks[(s.product, s.node)], s.product, s.node)].append(s)
    arrivals = defaultdict(list)       # (product, place, week) -> [tag]
    pending = defaultdict(set)         # week -> {(rank, product, place)} with arrivals
    queues = defaultdict(list)         # (product, place) -> heap of tags (manufacture weeks)
    deliveries, in_transit_end = [], 0
    places_by_week = defaultdict(set)  # week -> {(rank, product, place)} with exits
    for (w, r, prod, place) in exits:
        places_by_week[w].add((r, prod, place))

    for w in range(n):
        # every place with arrivals or exits this week, upstream first (a same-week
        # arrival from an upstream place is added to `todo` while processing)
        todo = places_by_week.get(w, set()) | pending.pop(w, set())
        done = set()
        while todo:
            r, prod, place = min(todo)
            todo.discard((r, prod, place))
            for tag in arrivals.pop((prod, place, w), []):
                heapq.heappush(queues[(prod, place)], tag)
            # a place's exits run once per week (a later same-week arrival only queues)
            out = [] if (r, prod, place) in done else exits.get((w, r, prod, place), [])
            done.add((r, prod, place))
            for i, s in enumerate(out):
                if s.kind == K_HANDOFF:
                    tag = s.week
                else:
                    q = queues[(prod, place)]
                    if not q:
                        raise ShelfLifeError(
                            f"{prod}: {place} ships {len(out)} lot(s) in week {week_labels[w]} "
                            f"but has only {i} at that point (the shipment records do not add up)")
                    tag = heapq.heappop(q)
                if s.kind == K_CONSUMER:
                    deliveries.append((s, tag))
                    continue
                dest = s.to
                aw = s.arrival_week
                if aw is None or not s.arrival_in_horizon or aw >= n:
                    in_transit_end += 1
                    continue
                if aw < w:
                    raise ShelfLifeError(f"{prod}: {s.ship_id} arrives at {dest} in week "
                                         f"{week_labels[aw]}, before it leaves ({week_labels[w]})")
                arrivals[(prod, dest, aw)].append(tag)
                key = (ranks.get((prod, dest), 10 ** 6), prod, dest)
                if aw == w:
                    todo.add(key)
                else:
                    pending[aw].add(key)
    left = {f"{p}/{pl}": len(q) for (p, pl), q in queues.items() if q}
    rows = []
    for s, tag in deliveries:
        rows.append({"product": s.product, "channel": s.node, "lot_id": s.lot_id,
                     "delivery_week": s.week, "manufacture_week": tag,
                     "fifo_age": s.week - tag,
                     "lot_factory_week": factory_week.get((s.product, s.lot_id))})
    return {"deliveries": rows, "in_transit_end": in_transit_end, "left_in_place": left}


def add_lot_dwell(rows, week_labels):
    """Reference column: max(demand week, market week) - factory week of that Lot_ID."""
    from wom.model.lot_generator import LotIDGenerator
    widx = {l: i for i, l in enumerate(week_labels)}
    for r in rows:
        fw = r["lot_factory_week"]
        try:
            dw = widx.get(LotIDGenerator.parse(r["lot_id"])[2])
        except ValueError:
            dw = None
        r["lot_dwell"] = (None if fw is None or dw is None
                          else max(dw, r["delivery_week"]) - fw)
    return rows


def summarise(rows, max_age):
    groups = defaultdict(list)
    for r in rows:
        groups[(r["product"], r["channel"])].append(r)
        groups[(r["product"], "*")].append(r)
        groups[("*", "*")].append(r)
    out = []
    for (p, ch), rs in sorted(groups.items()):
        ages = [r["fifo_age"] for r in rs]
        dw = [r["lot_dwell"] for r in rs if r.get("lot_dwell") is not None]
        out.append({"product": p, "channel": ch, "deliveries": len(rs),
                    "fifo_age_min": min(ages), "fifo_age_max": max(ages),
                    "over_max_age": sum(1 for a in ages if a > max_age),
                    "fifo_age_dist": ";".join(f"{a}:{c}" for a, c in sorted(Counter(ages).items())),
                    "lot_dwell_max": max(dw) if dw else "",
                    "lot_dwell_over_max_age": sum(1 for d in dw if d > max_age)})
    return out


def check_tree(sc_tree, max_age: int) -> dict:
    """Build the records from a planned tree and return deliveries + summary."""
    from wom.valuechain.records import build_records
    rec = build_records(sc_tree, "shelf_life")
    labels = list(sc_tree.week_labels)
    ranks = {k: v.rank for k, v in rec.nodes.items()}
    res = compute_fifo(rec.shipments, ranks, labels)
    rows = add_lot_dwell(res["deliveries"], labels)
    # the deliveries must equal the market's actual shipments (independent count)
    market, delivered_ids, demand_ids = 0, set(), set()
    for prod in sc_tree.products:
        for nd in sc_tree.iter_all_nodes(prod):
            if nd.node_type != "leaf_out":
                continue
            for lots in (getattr(nd, "_actual_ship", None) or {}).values():
                market += len(lots)
                delivered_ids.update((prod, l) for l in lots)
            for w in range(len(labels)):
                demand_ids.update((prod, l) for l in nd.psi4demand[w][0])
    if market != len(rows):
        raise ShelfLifeError(f"deliveries counted {len(rows)} but the market's actual "
                             f"shipments are {market}")
    return {"labels": labels, "rows": rows, "summary": summarise(rows, max_age),
            "backlog_end": len(demand_ids - delivered_ids),
            "in_transit_end": res["in_transit_end"], "left_in_place": res["left_in_place"],
            "record_issues": rec.issues}


def _capture_plugin():
    from wom.engine.plugin_base import WOMPlugin

    class _Capture(WOMPlugin):
        name = "shelf_life_capture"
        label = "shelf life capture"

        def on_post_plan(self, sc_tree, weeks, config, **kw):
            self.tree = sc_tree
    return _Capture()


def _write(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        wr.writerows(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Shelf-life check: FIFO age of every market delivery")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--max-age-weeks", required=True, type=int,
                    help="allowed age at delivery [weeks] (required: no silent default)")
    ap.add_argument("--plugins", default=None,
                    help="same rule as run_headless_from_folder (default: the model's recommended_plugins)")
    ap.add_argument("--out", default=None, help="default: output/shelf_life/<model folder name>")
    ap.add_argument("--demand-file", default="demand_forecast.csv",
                    help="demand CSV inside the model folder (default demand_forecast.csv). Give the "
                         "allocated demand CSV of a quantity allocation run (demand_forecast_<id>.csv) "
                         "to count the ages of that plan")
    ap.add_argument("--warmup-real-start", default=None,
                    help="warm-up base week passed to run() (default: none = from the demand CSV). "
                         "With an allocated demand CSV, give the week the allocation run used "
                         "(Q<nn>.json fixed.warmup_real_start) so that the plan period does not move")
    a = ap.parse_args(argv)
    sys.path.insert(0, REPO)
    from tools.run_headless_from_folder import run
    out = a.out or os.path.join("output", "shelf_life", os.path.basename(a.model_dir.rstrip("/\\")))
    os.makedirs(out, exist_ok=True)
    cap = _capture_plugin()
    run(a.model_dir, plugins_spec=a.plugins, output_ppc_dir=os.path.join(out, "ppc"),
        verbose=False, extra_plugins=[cap], demand_file=a.demand_file,
        warmup_real_start=a.warmup_real_start)
    r = check_tree(cap.tree, a.max_age_weeks)
    labels = r["labels"]
    rows = [dict(x, delivery_week=labels[x["delivery_week"]],
                 manufacture_week=labels[x["manufacture_week"]],
                 lot_factory_week="" if x["lot_factory_week"] is None else labels[x["lot_factory_week"]],
                 lot_dwell="" if x["lot_dwell"] is None else x["lot_dwell"])
            for x in r["rows"]]
    _write(os.path.join(out, "shelf_life_deliveries.csv"), rows,
           ["product", "channel", "delivery_week", "manufacture_week", "fifo_age",
            "lot_id", "lot_factory_week", "lot_dwell"])
    _write(os.path.join(out, "shelf_life_summary.csv"), r["summary"], list(r["summary"][0]))
    print(f"[shelf_life] {a.model_dir}  max age {a.max_age_weeks} weeks  deliveries {len(rows):,}  "
          f"backlog at end {r['backlog_end']:,} (not deliveries)  in transit at end {r['in_transit_end']:,}")
    print(f"{'product':<20}{'channel':<22}{'deliv':>8}{'min':>5}{'max':>5}{'over':>6}"
          f"{'lot_dwell_max':>15}{'lot_over':>10}")
    for s in r["summary"]:
        print(f"{s['product']:<20}{s['channel']:<22}{s['deliveries']:>8}{s['fifo_age_min']:>5}"
              f"{s['fifo_age_max']:>5}{s['over_max_age']:>6}{str(s['lot_dwell_max']):>15}"
              f"{s['lot_dwell_over_max_age']:>10}")
    over = [x for x in rows if x["fifo_age"] > a.max_age_weeks]
    if over:
        by = Counter((x["product"], x["delivery_week"]) for x in over)
        print(f"[shelf_life] OVER {a.max_age_weeks} weeks: {len(over)} deliveries")
        for (p, wk), c in sorted(by.items()):
            print(f"  {p}  {wk}  {c}")
    print(f"[shelf_life] -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
