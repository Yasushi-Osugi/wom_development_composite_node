# -*- coding: utf-8 -*-
"""
tools/rice_seasonal_check.py — Rice の移行用コピーを上位の層つきで計画し、実出荷から独立に照合する
（RequestLetter_RiceSeasonal_Implementation 受入 K-R2・K-R3・K-R6・K-R8・K-R10）

    python -m tools.rice_seasonal_check --model-dir data/trial/rice-japan-2027-2028-seasonal \
        --out output/rice_seasonal/C [--lovem]

計画（headless、モデルのコピー）の後、上位の層の「割当」ではなく Forward の**実出荷**から数え直す：

  市場      元の要求 ID ごとの結果（当週・遅配・早出し・期末注文残）、上位の層の未割当との一致
  出荷      全ノードの I・CO・P の恒等式（休業の週の受入れの移動を含む）、P＝上流の実出荷＋LT、
            同じ ID の不正な重複、期首の合成 ID（OI_ 等）、需要に無い ID
  経路      割り当てた ID の収穫・精米・市場の実出荷の週が計画と一致
  資源      収穫（週・年産）、精米（品目共用）、玄米倉庫の在庫（期末 I と週内のピーク）を
            実出荷・実際の P から kg で数え直し、上限と比べる
  年産      作期ごとの収穫・報告期間／助走期間への払出し・期末の残り
  期首      報告の開始の前週末にある物（玄米倉庫・輸送中・精米側）を、作期つきで数える
  物量      歩留まりで 玄米＝精米＋その他の産出 が保存される（Fraction で検算）
  LOVEM     --lovem：観測つきで同じ計画を実行し、観測なしと結果が同じこと、actual_ship イベントと
            木の実出荷が 1 対 1。区間の照合は tools/lovem_interval_check.py（セルごと。Rice では
            wom.lovem.verify.verify_run は全セルを一度に展開してメモリが足りない）

出力：<out>/summary.json、market_ids.csv.gz、resource_usage.csv、crop_year.csv、
      opening_stock.csv、physical_ledger.csv、weekly_market.csv。
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
from fractions import Fraction

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PLUGINS = "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,RiceSeasonalPlugin"


def plan(model_dir, plugins=PLUGINS, observe_dir=None):
    """Headless plan of a COPY; returns (snapshot, tree, forward results)."""
    import tools.run_headless_from_folder as rh
    import wom.engine.forward_planner as fpm
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
    tmp = tempfile.mkdtemp(prefix="rice_chk_")
    try:
        if observe_dir:
            from wom.lovem.observer import observe_run
            snap = observe_run(model_dir, observe_dir, plugins=plugins, repo=REPO, label="rice_seasonal")
        else:
            work = os.path.join(tmp, os.path.basename(model_dir.rstrip("/\\")))
            shutil.copytree(model_dir, work)
            snap = rh.run(work, plugins_spec=plugins, output_ppc_dir=os.path.join(work, "_ppc"), verbose=False)
    finally:
        rh._psi_signature, fpm.ForwardPlanner.run = o_sig, o_run
        shutil.rmtree(tmp, ignore_errors=True)
    return snap, store["tree"], store["fres"]


def leaf_of_lots(tree):
    out = {}
    for p in tree.products:
        for nd in tree.iter_all_nodes(p):
            if nd.node_type == "leaf_out":
                for w in range(tree.num_weeks()):
                    for lot in nd.psi4demand[w][0]:
                        out[lot] = nd
    return out


def flow_identities(tree, fres):
    """Per node and week: I, CO and P recomputed from the actual shipments."""
    from wom.model.plan_node import S, CO, I, P
    leaf = leaf_of_lots(tree)
    n = tree.num_weeks()
    errs = Counter()
    examples = defaultdict(list)

    def bad(kind, *x):
        errs[kind] += 1
        if len(examples[kind]) < 5:
            examples[kind].append(x)

    for p in tree.products:
        nodes = list(tree.iter_all_nodes(p))
        for nd in nodes:
            prev_i, prev_co = Counter(), Counter()
            for w in range(n):
                shipped = Counter(nd._actual_ship.get(w, []))
                avail = prev_i + Counter(nd.psi4supply[w][P])
                if any(v > 1 for v in avail.values()):
                    bad("duplicate_supply", nd.node_name, p, w)
                if shipped - avail:
                    bad("shipped_without_supply", nd.node_name, p, w)
                if avail - shipped != Counter(nd.psi4supply[w][I]):
                    bad("inventory", nd.node_name, p, w)
                if nd.plan_mode not in ("push_sub",) and nd.node_type != "leaf_in":
                    dem = prev_co + Counter(nd.psi4supply[w][S])
                    if shipped - dem:
                        bad("shipped_without_request", nd.node_name, p, w)
                    if w + 1 < n and dem - shipped != Counter(nd.psi4supply[w + 1][CO]):
                        bad("carry_over", nd.node_name, p, w)
                    prev_co = dem - shipped
                prev_i = Counter(nd.psi4supply[w][I])
        # receipts: P == upstream actual shipments + LT, moved out of closed weeks
        in_root = tree.get_in_root(p)
        ot_root = tree.get_ot_root(p)
        for nd in nodes:
            if nd.node_type == "leaf_in":
                continue
            arr = defaultdict(list)
            if nd is ot_root:
                for w, lots in in_root._actual_ship.items():
                    arr[w] += lots
            elif nd.side == "inbound":
                for ch in nd.children:
                    t = ch.transit_lt_wks if ch.transit_lt_wks > 0 else ch.lt_wks
                    for w, lots in ch._actual_ship.items():
                        if w + t < n:
                            arr[w + t] += lots
            else:
                par = nd.parent
                for w, lots in par._actual_ship.items():
                    mine = [l for l in lots if _through(leaf[l], nd)]
                    if mine and w + nd.lt_wks < n:
                        arr[w + nd.lt_wks] += mine
            exp = defaultdict(Counter)
            for w in sorted(arr):
                tw = w
                if nd is not ot_root and not nd.is_open(w):
                    tw = next((x for x in range(w + 1, n) if nd.is_open(x)), None)
                    if tw is None:
                        continue
                exp[tw] += Counter(arr[w])
            for w in range(n):
                if exp.get(w, Counter()) != Counter(nd.psi4supply[w][P]):
                    bad("receipt_not_upstream_actual", nd.node_name, p, w)
    return dict(errs), {k: v for k, v in examples.items()}


def _through(leaf, node):
    x = leaf
    while x is not None:
        if x is node:
            return True
        x = x.parent
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lovem", action="store_true")
    a = ap.parse_args(argv)
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    from wom.capacity_layer import rice_seasonal as rs
    from wom.model.plan_node import P, I
    os.makedirs(a.out, exist_ok=True)
    snap, tree, fres = plan(a.model_dir)
    res = tree.rice_seasonal_results
    weeks = list(tree.week_labels)
    inputs = rs.load_inputs(a.model_dir, weeks)
    rstart = inputs.policy.report_start
    ri = weeks.index(rstart) if rstart else 0
    rows = [r for p in tree.products for r in res[p]["rows"]]
    by_lot = {r["lot_id"]: r for r in rows}
    S = {}

    # ── market ───────────────────────────────────────────────────────
    mk = Counter()
    lot_rows = []
    nodes_by = {p: {n.node_name: n for n in tree.iter_all_nodes(p)} for p in tree.products}
    route_trace_err = Counter()
    for p in tree.products:
        for nd in tree.iter_all_nodes(p):
            if nd.node_type != "leaf_out":
                continue
            ship = {}
            for w, lots in nd._actual_ship.items():
                for lot in lots:
                    ship.setdefault(lot, w)
            for d in range(len(weeks)):
                for lot in nd.psi4demand[d][0]:
                    s = ship.get(lot)
                    st = ("on_time" if s == d else "late" if s is not None and s > d
                          else "early" if s is not None else "backlog_end")
                    per = "report" if d >= ri else "warmup"
                    mk[(p, per, st)] += 1
                    r = by_lot.get(lot)
                    if r is None:
                        mk[("missing_in_layer",)] += 1
                    elif (r["status"] == "assigned") != (st == "on_time"):
                        mk[("layer_vs_actual_mismatch",)] += 1
                    t = r["timing"] if r else None
                    if t is not None:
                        ns = nodes_by[p]
                        rt = next(v for (pp, m), v in _routes(tree, inputs).items() if pp == p and m == nd.node_name)
                        for key, wk in (("field", t.harvest), ("mill", t.polish)):
                            if lot not in ns[rt.names[key]]._actual_ship.get(wk, []):
                                route_trace_err[key] += 1
                    lot_rows.append({"product": p, "market": nd.node_name, "lot_id": lot, "request_week": weeks[d],
                                     "period": per, "status": st, "ship_week": weeks[s] if s is not None else "",
                                     "layer": r["status"] if r else "",
                                     "harvest_week": weeks[t.harvest] if t else "",
                                     "crop_season": t.season if t else "",
                                     "warehouse_in": weeks[t.store_arrival] if t else "",
                                     "warehouse_out": weeks[t.store_departure] if t else "",
                                     "milling_week": weeks[t.polish] if t else "",
                                     "reason": r.get("reason", "") if r else ""})
    S["market"] = {"|".join(k): v for k, v in sorted(mk.items())}
    S["route_trace_mismatch"] = dict(route_trace_err)

    # ── shipments ────────────────────────────────────────────────────
    errs, ex = flow_identities(tree, fres)
    S["flow_identity_errors"] = errs
    S["flow_identity_examples"] = {k: [list(map(str, x)) for x in v] for k, v in ex.items()}
    demand_ids = set(by_lot)
    shipped_ids = {l for p in tree.products for nd in tree.iter_all_nodes(p)
                   for lots in nd._actual_ship.values() for l in lots}
    S["ids_shipped_not_in_demand"] = len(shipped_ids - demand_ids)
    S["synthetic_opening_ids"] = sum(1 for l in shipped_ids if l.startswith("OI_"))
    S["opening_inv"] = {p: dict(getattr(f, "opening_inv_counts", {}) or {}) for p, f in fres.items()}
    S["forward"] = snap["forward"]
    S["supply_duplicate_ids"] = {p: len(getattr(f, "supply_duplicate_ids", []) or []) for p, f in fres.items()}
    S["early_ids"] = sum(v for k, v in mk.items() if len(k) == 3 and k[2] == "early")

    # ── resources recounted from the actual flows ────────────────────
    routes = _routes(tree, inputs)
    raw = {p: inputs.recipes[p].raw_kg_per_lot for p in inputs.recipes}
    load = defaultdict(Fraction)
    crop_used = defaultdict(Fraction)
    season_of = {lot: r["timing"].season for lot, r in by_lot.items() if r["timing"] is not None}
    seen_field, seen_mill, seen_wh = set(), set(), set()
    for (p, m), rt in routes.items():
        f = nodes_by[p][rt.names["field"]]
        if f.node_id not in seen_field:
            seen_field.add(f.node_id)
            for w, lots in f._actual_ship.items():
                load[rt.resources["harvest"], w] += raw[p] * len(lots)
                for l in lots:
                    crop_used[rt.resources["harvest"], season_of.get(l, "?")] += raw[p]
        mill = nodes_by[p][rt.names["mill"]]
        if mill.node_id not in seen_mill:
            seen_mill.add(mill.node_id)
            for w in range(len(weeks)):
                load[rt.resources["polish"], w] += raw[p] * len(mill.psi4supply[w][P])
        wh = nodes_by[p][rt.names["warehouse"]]
        if wh.node_id not in seen_wh:
            seen_wh.add(wh.node_id)
            for w in range(len(weeks)):
                prev = len(wh.psi4supply[w - 1][I]) if w else 0
                load[rt.resources["storage"] + "|peak", w] += raw[p] * (prev + len(wh.psi4supply[w][P]))
                load[rt.resources["storage"] + "|end", w] += raw[p] * len(wh.psi4supply[w][I])
    over = []
    usage_rows = []
    for (rid, w), kg in sorted(load.items(), key=lambda x: (x[0][0], x[0][1])):
        base = rid.split("|")[0]
        cap = inputs.capacity.get((base, w))
        if kg and cap is not None and float(kg) > cap + 1e-6:
            over.append((rid, weeks[w], float(kg), cap))
        if kg:
            usage_rows.append({"resource_id": rid, "week": weeks[w], "kg_actual": float(kg),
                               "capacity_kg": "" if cap is None else cap})
    S["resource_over_capacity"] = over
    plan_load = rs.resource_usage(*_rp_sol(tree))
    crop_rows = []
    for (rid, season), lim in sorted(inputs.crop_limit.items()):
        used = crop_used.get((rid, season), Fraction(0))
        if lim is not None and float(used) > lim + 1e-6:
            over.append((f"crop:{rid}:{season}", "", float(used), lim))
        prod = next(p for (p, m), rt in routes.items() if rt.resources["harvest"] == rid)
        lots = [l for l, s in season_of.items() if s == season and by_lot[l]["product"] == prod]
        rep = sum(1 for l in lots if by_lot[l]["due"] >= ri)
        crop_rows.append({"resource_id": rid, "product": prod, "crop_season": season,
                          "limit_raw_kg": lim, "limit_lots": lim / float(raw[prod]) if lim else "",
                          "harvested_lots": len(lots), "harvested_raw_kg": float(used),
                          "to_warmup_demand_lots": len(lots) - rep, "to_report_demand_lots": rep,
                          "unharvested_lots": (lim / float(raw[prod]) - len(lots)) if lim else ""})
    S["crop_year"] = crop_rows

    # ── opening stock at report_start, from the harvest history ──────
    op = Counter()
    if ri > 0:
        w0 = ri - 1
        for lot, r in by_lot.items():
            t = r["timing"]
            if t is None or not (t.harvest <= w0 < r["due"]):
                continue
            if w0 < t.store_arrival:
                where = "brown_in_transit_to_warehouse"
            elif w0 < t.store_departure:
                where = "brown_in_warehouse"
            elif w0 < t.polish:
                where = "brown_in_transit_to_mill"
            else:
                where = "white_after_milling"
            op[(r["product"], t.season, where)] += 1
    open_rows = [{"product": p, "crop_season": s, "state": wh, "lots": n,
                  "kg": float(n * (raw[p] if wh.startswith("brown") else inputs.recipes[p].white_kg_per_lot))}
                 for (p, s, wh), n in sorted(op.items())]
    S["opening_stock_week"] = weeks[ri - 1] if ri else None
    S["opening_stock"] = open_rows

    # ── physical ledger / mass balance ───────────────────────────────
    rp, sol = _rp_sol(tree)
    led = rs.physical_ledger(rp, rows)
    harvested = sum(raw[r["product"]] for r in rows if r["status"] == "assigned")
    white = sum(inputs.recipes[r["product"]].white_kg_per_lot for r in rows if r["status"] == "assigned")
    S["mass_balance"] = {"harvested_raw_kg": float(harvested), "white_kg": float(white),
                         "other_output_kg": float(harvested - white),
                         "balanced": harvested == white + (harvested - white) and
                         all(raw[p] == inputs.recipes[p].white_kg_per_lot / inputs.recipes[p].milling_yield
                             for p in raw)}
    S["layer"] = res["_joint"]

    # ── LOVEM ─────────────────────────────────────────────────────────
    if a.lovem:
        run_dir = os.path.abspath(os.path.join(a.out, "lovem_on"))
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir)
        snap2, tree2, _f2 = plan(a.model_dir, observe_dir=run_dir)
        leaf_ids = {nd.node_id for p in tree2.products for nd in tree2.iter_all_nodes(p) if nd.node_type == "leaf_out"}
        ev = Counter()
        with gzip.open(os.path.join(run_dir, "events.jsonl.gz"), "rt", encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                if e.get("event_type") == "actual_ship":
                    ev[(e["node_id"], e["week_index"], e["lot_id"])] += 1
        tr = Counter((nd.node_id, w, l) for p in tree2.products for nd in tree2.iter_all_nodes(p)
                     for w, lots in nd._actual_ship.items() for l in lots)
        mev = Counter({k: v for k, v in ev.items() if k[0] in leaf_ids})
        mtr = Counter({k: v for k, v in tr.items() if k[0] in leaf_ids})
        # The week-by-week restore (wom.lovem.verify.verify_run) expands every cell of a
        # snapshot to week x ID counters at once; for Rice (24.7 M occurrences) it ran out of
        # memory. The interval restore is checked cell by cell by tools/lovem_interval_check.py.
        S["lovem"] = {"snapshot_equal_to_unobserved": {k: snap2[k] == snap[k] for k in ("psi", "ppc", "forward")},
                      "actual_ship_events_all_nodes": sum(ev.values()), "tree_actual_ships_all_nodes": sum(tr.values()),
                      "all_nodes_one_to_one": ev == tr, "market_one_to_one": mev == mtr,
                      "market_actual_ship_events": sum(mev.values()),
                      "interval_restore": "not run here -- use tools/lovem_interval_check.py (cell by cell)"}

    # ── outputs ───────────────────────────────────────────────────────
    with gzip.open(os.path.join(a.out, "market_ids.csv.gz"), "wt", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, list(lot_rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(lot_rows)
    for name, data in (("resource_usage.csv", usage_rows), ("crop_year.csv", crop_rows),
                       ("opening_stock.csv", open_rows), ("physical_ledger.csv", led)):
        if data:
            keys = list(dict.fromkeys(k for r in data for k in r))
            with open(os.path.join(a.out, name), "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, keys, lineterminator="\n")
                w.writeheader(); w.writerows(data)
    wk = Counter()
    for r in lot_rows:
        wk[(r["product"], r["request_week"], r["status"])] += 1
    with open(os.path.join(a.out, "weekly_market.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["product", "request_week", "on_time", "late", "early", "backlog_end"])
        for p in tree.products:
            for wl in weeks:
                vals = [wk[(p, wl, s)] for s in ("on_time", "late", "early", "backlog_end")]
                if any(vals):
                    w.writerow([p, wl, *vals])
    S["plan_vs_actual_resource_load"] = {
        "planned_mill_kg": sum(v for (rid, _w), v in plan_load.items() if rid.startswith("MILL")),
        "actual_mill_kg": float(sum(v for (rid, _w), v in load.items() if rid.startswith("MILL")))}
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(S, f, ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: S[k] for k in ("market", "flow_identity_errors", "route_trace_mismatch",
                                         "resource_over_capacity", "ids_shipped_not_in_demand",
                                         "synthetic_opening_ids", "early_ids")}, ensure_ascii=False, indent=1))
    if "lovem" in S:
        print(json.dumps(S["lovem"], indent=1))
    return 0


_ROUTES = {}


def _routes(tree, inputs):
    from wom.capacity_layer.rice_seasonal import routes_from_tree
    k = id(tree)
    if k not in _ROUTES:
        _ROUTES[k] = routes_from_tree(tree, list(tree.products), inputs)
    return _ROUTES[k]


def _rp_sol(tree):
    import wom.plugins.rice_seasonal  # noqa: F401
    st = tree.rice_seasonal_results
    return st["_problem"], st["_solution"]


if __name__ == "__main__":
    raise SystemExit(main())
