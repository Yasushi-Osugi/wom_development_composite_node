# -*- coding: utf-8 -*-
"""
tools/warmup_trial.py — warm-up の試行と、期末注文残の原因の分類（測定だけ。計画は変えない）

    python -m tools.warmup_trial --model smartphone-global-2026-2029 --weeks 0,17,26 \
        --out output/smartphone_evupdate_s2/A [--mode identity] [--plugins safe]

モデルのフォルダを <out>/<model>__w<N>/ へコピーし、コピーの planning_config.csv の
warmup_lt を N にして（ほかのキーは保つ。N=0 は助走行を取り除く）、headless で実行する。
**原本（data/sample/）には一切書かない。**

出力（<out>/ の下）:
  <model>__w<N>/                     コピーしたモデル（_out_ppc/・_out_flow_check/ を含む）
  <model>__w<N>__backlog_lots.csv    期末注文残の Lot_ID ごとの行（下の列）
  <model>__w<N>__leaf_lots.csv.gz    市場 leaf の全要求 ID と、その結果（当週出荷／遅配／期末注文残）
  <model>__summary.json              条件ごとの集計

期末注文残の分類（RequestLetter_SmartphoneWarmup_EVUpdateKitting_S2 A2）
------------------------------------------------------------------
市場 leaf で期末に出荷されていない要求 ID ごとに、供給の向きを上流へたどる
（OutBound の子→親→supply_point→InBound の MOM root→子）。「その ID を要求していて、
出荷していない」ノードが続くかぎり上流へ進み、最も上流のものを **止まったノード** とする。

**主因（排他。上から順に、最初に当てはまったもの 1 つ）**
  1 horizon_edge(end)   止まったノードの供給元は出荷したが、到着が計画期間の終わりを越える
  2 capacity            止まったノードで Forward の Step 0a（cap_hard）が、その ID を繰り延べた
  3 closure             休業週に、その ID が止まったノードの P／I にあった、または要求週が休業
  4 （供給元のどれも、その ID を要求していない場合）
      4a capacity            Backward の MOM の能力の押し戻しが第 0 週を越えた（past_due）
      4b horizon_edge(start) Backward の LT オフセットが第 0 週より前に出た（past_due）、
                             または、止まったノードに最初の供給が届く前の週の要求
      4c id_unmatched        供給は届いているが、その ID は届かない
  5 unknown             どれにも当てはまらない

**補足列 all_flags**：主因の順序によらず、その ID に当てはまった条件をすべて並べる
（arrive_after_end／deferred_step0a／closure／past_due_cap／past_due_lt／mom_cap_pushback／
before_first_supply）。mom_cap_pushback は「Backward が MOM の能力で、その ID の生産を前の週へ
押し戻した」こと（past_due にならず、計画期間の中に収まった場合も含む。週数は
mom_cap_pushback_weeks 列）。
複数の条件が当てはまる ID を、主因だけで言い切らないための列。

**first_fail_node／first_fail_week**：Backward が、その ID を最初に置けなかったノードと、
そのノードでの週（past_due の最初の記録）。past_due の記録が無い ID は、止まったノードと
その要求週。**min_missing_weeks**：past_due_lt の場合、(LT＋SS＋X2) − 週番号
（そのノード 1 段を置くのに足りなかった週数。それより上流の段の分は含まない＝下限）。
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import shutil
import sys
import time
from collections import Counter, defaultdict

S, CO, I, P = 0, 1, 2, 3
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ── 読むだけのフック ────────────────────────────────────────────────────
class _Hooks:
    def __init__(self):
        import tools.run_headless_from_folder as rh
        import wom.engine.backward_planner as bpm
        import wom.engine.forward_planner as fpm
        self.rh, self.bpm, self.fpm = rh, bpm, fpm
        self.store = {}
        self.deferred = defaultdict(set)      # node_id -> Step 0a で繰り延べた ID
        self.closure_hit = defaultdict(set)   # node_id -> 休業週に P／I にあった ID
        self.first_p = {}                     # node_id -> 最初に P があった週
        self.past_due = {}                    # lot -> (node_id, week, "cap"|"lt")  最初の記録
        self.pushback = {}                    # lot -> (MOM の node_id, 前へ動いた週数)  最大のもの
        self._in_cap = False
        self._orig = {}

    def install(self):
        rh, bpm, fpm, me = self.rh, self.bpm, self.fpm, self
        o = self._orig
        o["sig"], o["run"] = rh._psi_signature, fpm.ForwardPlanner.run
        o["proc"] = fpm.ForwardPlanner._process_node
        o["def"] = fpm.ForwardPlanResult.record_cap_hard_deferred
        o["pd"] = bpm.BackwardPlanResult.record_past_due
        o["momcap"] = bpm.BackwardPlanner._apply_mom_cap_backward

        def sig(t, n):
            me.store["tree"] = t
            return o["sig"](t, n)

        def frun(self_, prod):
            r = o["run"](self_, prod)
            me.store.setdefault("fres", {})[prod] = r
            return r

        def proc(self_, node, n_weeks, *a, **k):
            for w in range(n_weeks):
                if node.psi4supply[w][P] and node.node_id not in me.first_p:
                    me.first_p[node.node_id] = w
                if not node.is_open(w):
                    me.closure_hit[node.node_id].update(node.psi4supply[w][P])
            r = o["proc"](self_, node, n_weeks, *a, **k)
            if node.plan_mode == "push":
                for w in range(n_weeks):
                    if not node.is_open(w):
                        me.closure_hit[node.node_id].update(node.psi4supply[w][I])
            return r

        def dfr(self_, nid, wl, lots):
            if isinstance(lots, (list, tuple)):
                me.deferred[nid].update(lots)
            return o["def"](self_, nid, wl, lots)

        def pd_rec(self_, node_id, lot_id, week):
            me.past_due.setdefault(lot_id, (node_id, week, "cap" if me._in_cap else "lt"))
            return o["pd"](self_, node_id, lot_id, week)

        def momcap(self_, node, n_weeks, *a, **k):
            # MOM の能力で、要求が何週前へ押し戻されたか（前：押し戻す前の S の週、後：押し戻した後の S の週）
            before = {}
            if getattr(node, "node_type", "") == "mom":
                for w in range(n_weeks):
                    for x in node.psi4demand[w][S]:
                        before.setdefault(x, w)
            me._in_cap = True
            try:
                return o["momcap"](self_, node, n_weeks, *a, **k)
            finally:
                me._in_cap = False
                if before:
                    for w in range(n_weeks):
                        for x in node.psi4demand[w][S]:
                            d = before.get(x, w) - w
                            if d > 0 and d > me.pushback.get(x, (None, 0))[1]:
                                me.pushback[x] = (node.node_id, d)

        rh._psi_signature = sig
        fpm.ForwardPlanner.run = frun
        fpm.ForwardPlanner._process_node = proc
        fpm.ForwardPlanResult.record_cap_hard_deferred = dfr
        bpm.BackwardPlanResult.record_past_due = pd_rec
        bpm.BackwardPlanner._apply_mom_cap_backward = momcap

    def uninstall(self):
        rh, bpm, fpm, o = self.rh, self.bpm, self.fpm, self._orig
        rh._psi_signature = o["sig"]
        fpm.ForwardPlanner.run = o["run"]
        fpm.ForwardPlanner._process_node = o["proc"]
        fpm.ForwardPlanResult.record_cap_hard_deferred = o["def"]
        bpm.BackwardPlanResult.record_past_due = o["pd"]
        bpm.BackwardPlanner._apply_mom_cap_backward = o["momcap"]

    def reset(self):
        self.store.clear(); self.deferred.clear(); self.closure_hit.clear()
        self.first_p.clear(); self.past_due.clear(); self.pushback.clear()


# ── 分類 ────────────────────────────────────────────────────────────────
def classify_backlog(tree, hooks):
    """市場 leaf の全要求 ID の結果と、期末注文残の ID ごとの分類を返す。"""
    n = tree.num_weeks()
    wl = list(tree.week_labels)
    backlog_rows, leaf_rows = [], []
    for prod in tree.products:
        nodes = list(tree.iter_all_nodes(prod))
        by_id = {nd.node_id: nd for nd in nodes}
        shipped, req, got = {}, {}, {}
        for nd in nodes:
            sh = {}
            for w, v in (getattr(nd, "_actual_ship", None) or {}).items():
                for x in v:
                    sh.setdefault(x, w)
            rq, gt = {}, set()
            for w in range(n):
                for x in nd.psi4supply[w][S]:
                    rq.setdefault(x, w)
                gt.update(nd.psi4supply[w][P]); gt.update(nd.psi4supply[w][I])
            shipped[nd.node_id], req[nd.node_id], got[nd.node_id] = sh, rq, gt
        ot_root = tree.get_ot_root(prod)
        ot_ids = {nd.node_id for nd in ot_root.walk_preorder()}
        in_roots = [nd for nd in nodes if nd.node_id not in ot_ids and nd.parent is None]

        def suppliers(nd):
            if nd.node_id in ot_ids:
                return [nd.parent] if nd.parent is not None else in_roots
            return list(nd.children)

        for lf in (nd for nd in ot_root.walk_preorder() if not nd.children):
            for lot, sw in req[lf.node_id].items():
                shw = shipped[lf.node_id].get(lot)
                status = ("backlog_end" if shw is None else
                          "on_time" if shw == sw else "late" if shw > sw else "early")
                leaf_rows.append((prod, lf.node_name, lot, wl[sw], "" if shw is None else wl[shw], status))
                if shw is not None:
                    continue
                cur = lf
                while True:
                    ups = [u for u in suppliers(cur) if lot in req[u.node_id]]
                    stuck = [u for u in ups if lot not in shipped[u.node_id]]
                    if not stuck:
                        break
                    cur = stuck[0]
                rw = req[cur.node_id][lot]
                flags = []
                for u in ups:
                    arr = shipped[u.node_id][lot] + (cur.lt_wks if cur.parent is u else u.lt_wks)
                    if arr >= n:
                        flags.append("arrive_after_end")
                        break
                if lot in hooks.deferred.get(cur.node_id, ()):
                    flags.append("deferred_step0a")
                if lot in hooks.closure_hit.get(cur.node_id, ()) or not cur.is_open(rw):
                    flags.append("closure")
                pd = hooks.past_due.get(lot)
                if pd is not None:
                    flags.append("past_due_cap" if pd[2] == "cap" else "past_due_lt")
                pb = hooks.pushback.get(lot)
                if pb is not None:
                    flags.append("mom_cap_pushback")
                fs = hooks.first_p.get(cur.node_id)
                if fs is None or rw < fs:
                    flags.append("before_first_supply")
                # 主因（排他・順序つき）
                if "arrive_after_end" in flags:
                    cause = "horizon_edge(end)"
                elif "deferred_step0a" in flags:
                    cause = "capacity"
                elif "closure" in flags:
                    cause = "closure"
                elif not ups:
                    if "past_due_cap" in flags:
                        cause = "capacity"
                    elif "past_due_lt" in flags or "before_first_supply" in flags:
                        cause = "horizon_edge(start)"
                    else:
                        cause = "id_unmatched"
                else:
                    cause = "unknown"
                if pd is not None:
                    fnode = by_id.get(pd[0])
                    ff_node = fnode.node_name if fnode is not None else pd[0]
                    ff_week = wl[pd[1]] if 0 <= pd[1] < n else str(pd[1])
                    if pd[2] == "lt" and fnode is not None:
                        off = fnode.lt_wks + fnode.ss_wks + (
                            fnode.init_stock_wks if fnode.node_id in ot_ids else 0)
                        missing = off - pd[1]
                    else:
                        missing = ""
                else:
                    ff_node, ff_week, missing = cur.node_name, wl[rw], ""
                backlog_rows.append({
                    "product": prod, "leaf": lf.node_name, "lot_id": lot, "leaf_request_week": wl[sw],
                    "stuck_node": cur.node_name, "stuck_node_type": cur.node_type,
                    "stuck_plan_mode": cur.plan_mode, "stuck_request_week": wl[rw],
                    "cause": cause, "all_flags": "|".join(flags),
                    "first_fail_node": ff_node, "first_fail_week": ff_week,
                    "first_fail_kind": (pd[2] if pd is not None else "forward"),
                    "min_missing_weeks": missing,
                    "mom_cap_pushback_weeks": (pb[1] if pb is not None else ""),
                })
    return leaf_rows, backlog_rows


def _set_warmup(cfg_path, n):
    rows = []
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as f:
            rows = [r for r in csv.reader(f) if r]
    if not rows or rows[0][:2] != ["key", "value"]:
        rows = [["key", "value"]] + rows
    body = [r for r in rows[1:] if r[0] != "warmup_lt"]
    body.append(["warmup_lt", str(n)])
    with open(cfg_path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows([rows[0]] + body)


def _default_plugins(model):
    gp = os.path.join(REPO, "tests", "golden", f"{model}.json")
    if os.path.exists(gp):
        with open(gp, encoding="utf-8") as f:
            return ",".join(json.load(f)["config"]["plugins"]) or "none"
    return "safe"


def run_trial(model, n, out_dir, mode="identity", plugins=None, hooks=None, src_dir=None,
              prepare=None):
    """1 条件を実行して集計を返す。prepare(trial_dir) でコピーに手を加えられる（遅着の試験など）。"""
    from wom.engine.flow_check import compute_flow_check, write_flow_check_csv
    from wom.engine.warmup import first_nonzero_demand_week
    own = hooks is None
    if own:
        hooks = _Hooks(); hooks.install()
    try:
        hooks.reset()
        src = src_dir or os.path.join(REPO, "data", "sample", model)
        tag = f"{model}__w{n}"
        trial = os.path.join(out_dir, tag)
        if os.path.exists(trial):
            shutil.rmtree(trial)
        shutil.copytree(src, trial)
        if n is not None:
            _set_warmup(os.path.join(trial, "planning_config.csv"), n)
        if prepare is not None:
            prepare(trial)
        t0 = time.perf_counter()
        snap = hooks.rh.run(trial, plugins_spec=plugins or _default_plugins(model),
                            output_ppc_dir=os.path.join(trial, "_out_ppc"), verbose=False,
                            lot_flow_mode=mode)
        runtime = time.perf_counter() - t0
        tree, fres = hooks.store["tree"], hooks.store["fres"]
        fc = compute_flow_check(tree, fres)
        write_flow_check_csv(fc, os.path.join(trial, "_out_flow_check"))
        leaf_rows, backlog_rows = classify_backlog(tree, hooks)
        with gzip.open(os.path.join(out_dir, f"{tag}__leaf_lots.csv.gz"), "wt", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["product", "leaf", "lot_id", "request_week", "ship_week", "status"])
            w.writerows(leaf_rows)
        cols = ["product", "leaf", "lot_id", "leaf_request_week", "stuck_node", "stuck_node_type",
                "stuck_plan_mode", "stuck_request_week", "cause", "all_flags", "first_fail_node",
                "first_fail_week", "first_fail_kind", "min_missing_weeks", "mom_cap_pushback_weeks"]
        with open(os.path.join(out_dir, f"{tag}__backlog_lots.csv"), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader(); w.writerows(backlog_rows)
        wl = list(tree.week_labels)
        real_start = first_nonzero_demand_week(os.path.join(trial, "demand_forecast.csv"))
        warm_idx = wl.index(real_start) if real_start in wl else 0
        warm_events = tot_events = 0
        led = os.path.join(trial, "_out_ppc", "ppc_event_ledger.csv")
        if os.path.exists(led):
            warm_set = set(wl[:warm_idx])
            with open(led, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    tot_events += 1
                    warm_events += r["week"] in warm_set
        # 助走で作った量・実需要の開始時の在庫・報告期間の出荷（別々の列）
        warm_prod = warm_stock = rep_ship = 0
        warm_stock_nodes = {}
        for prod in tree.products:
            ot_ids = {nd.node_id for nd in tree.get_ot_root(prod).walk_preorder()}
            for nd in tree.iter_all_nodes(prod):
                if nd.node_type == "mom" and nd.parent is None:
                    warm_prod += sum(len(nd.psi4supply[w][P]) for w in range(warm_idx))
                if warm_idx > 0:
                    v = len(nd.psi4supply[warm_idx - 1][I])
                    if v:
                        warm_stock += v
                        warm_stock_nodes[f"{nd.node_name} [{prod}]"] = v
                if nd.node_id in ot_ids and not nd.children:
                    rep_ship += sum(len(v) for w, v in (getattr(nd, "_actual_ship", None) or {}).items()
                                    if w >= warm_idx)
        tot = fc["market"][-1]
        cc = Counter(r["cause"] for r in backlog_rows)
        multi = Counter(r["all_flags"] for r in backlog_rows)
        stuck = Counter(f'{r["cause"]}: {r["stuck_node"]} [{r["product"]}] {r["stuck_node_type"]}/{r["stuck_plan_mode"]}'
                        for r in backlog_rows)
        ff = Counter(f'{r["first_fail_kind"]}: {r["first_fail_node"]} [{r["product"]}]' for r in backlog_rows)
        miss = [r["min_missing_weeks"] for r in backlog_rows if r["min_missing_weeks"] != ""]
        return {
            "model": model, "warmup_lt": n, "mode": mode, "period": snap["period"], "real_start": real_start,
            "market": {k: tot[k] for k in ("demand", "on_time", "early", "late", "backlog_end", "check")},
            "market_by_product": [{k: r[k] for k in ("product", "demand", "on_time", "late", "backlog_end")}
                                  for r in fc["market"] if r["leaf"] == "Σ（製品）"],
            "causes": dict(cc.most_common()), "flag_combinations": dict(multi.most_common()),
            "stuck_nodes": dict(stuck.most_common(12)), "first_fail_nodes": dict(ff.most_common(12)),
            "min_missing_weeks": ({"n": len(miss), "min": min(miss), "max": max(miss),
                                   "hist": dict(sorted(Counter(miss).items()))} if miss else None),
            "flow_ng": fc["summary"]["ng"], "flow_na": fc["summary"]["not_applicable"],
            "ng_rows": [(r["product"], r["node"], r["reason"]) for r in fc["nodes"] if r["status"] == "NG"][:10],
            "ppc": snap["ppc"], "forward": snap["forward"], "backward": snap["backward"],
            "ppc_events": tot_events, "ppc_warmup_events": warm_events,
            "warmup_production_at_mom_roots": warm_prod, "stock_at_real_start": warm_stock,
            "stock_at_real_start_by_node": warm_stock_nodes, "report_period_leaf_shipments": rep_ship,
            "runtime_s": round(runtime, 2),
        }
    finally:
        if own:
            hooks.uninstall()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--weeks", default="0,17,26")
    ap.add_argument("--out", default=os.path.join("output", "warmup_trial"))
    ap.add_argument("--mode", default="identity")
    ap.add_argument("--plugins", default=None)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    hooks = _Hooks(); hooks.install()
    res = {}
    try:
        for n in [int(x) for x in a.weeks.split(",")]:
            r = run_trial(a.model, n, a.out, a.mode, a.plugins, hooks)
            res[f"w{n}"] = r
            print(f"{a.model} w{n} period={r['period']} market={r['market']} causes={r['causes']} "
                  f"flow_ng={r['flow_ng']} rev={r['ppc']['revenue_base']} gm={r['ppc']['gross_margin_pct']}",
                  flush=True)
    finally:
        hooks.uninstall()
    with open(os.path.join(a.out, f"{a.model}__summary.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
