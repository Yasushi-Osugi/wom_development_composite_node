# -*- coding: utf-8 -*-
"""
tools/run_quantity_allocation.py — 数量配分モード（数量で配分を渡す経路）
======================================================================
RequestLetter_QuantityAllocationMode v0.2 C.3（判断 J1〜J4、2026-10-26）。

    python -m tools.run_quantity_allocation --model-dir <作業用のモデル> --allocation-file <allocation_qty_X.csv>
        [--out-dir output/planning_state] [--unallocated-note "<U1 の仮定>"] [--plugins …]

人が **lot の数量** で決めた配分（(sku_id, region) ごとの `alloc_lots`）を、価格・原価・為替を
一つも置かずに、配分 → Backward → Forward → 結果の記録まで一巡させる。財務は「未評価」。
`run_planning_loop.py`（金額の経路）とは分けてある。

数量（同じ需要の集合・同じ判定時点・同じ単位 lot、意味体系 docs/semantics/supply_allocation.md）：
    ① 元の需要 q1_original ＝ ② 供給対象 q2_in_supply_scope ＋ ③ 未配分 q3_not_in_supply_scope
    ② ＝ ④ 実納品 q4_delivered（on_time・early・late）＋ ⑤ 配分後の未充足 q5_backlog_end
③ は配分のファイルだけで決まる（能力の層の `unallocated` とは別物。⑤ とも別）。
④・⑤ は Forward の後の照合（Flow Check 表2：leaf_out の `_actual_ship`）で決まる。

比べる条件の固定：配分案の間で変えてよいのは配分（②・③）だけ。元の需要 CSV から求めた
warmup の基準の週・計画の開始週・週数で計画し（`warmup_real_start`）、能力・操業カレンダーの
ファイルが変わっていないことを確かめる。

保存：不整合が無ければ `<out-dir>/<case>/Q<nn>.json`（⑤ > 0 でも保存する）と
`Q<nn>_flow_check/`。不整合があれば Q の番号を使わず、
`<out-dir>/<case>/diagnostics/<配分のファイル名>_inconsistent.json` に診断を書いて終了コード 1。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

_Q_RE = re.compile(r"^Q(\d+)\.json$")
DETAIL_EXCLUDE = ("Σ（製品）", "")        # table-2 subtotal / model total rows (leaf column)
VALUATION = "未評価"
OBSERVED_AT = "leaf_out の _actual_ship（Flow Check 表2）"


class InconsistentRecord(Exception):
    """入力・記録の不整合（正常な結果として確定しない）。"""

    def __init__(self, checks: dict):
        self.checks = checks
        super().__init__("入力・記録の不整合: " + "; ".join(
            f"{k}: {v['detail']}" for k, v in checks.items() if not v["ok"]))


def next_q_id(case_dir: str) -> str:
    nums = [int(m.group(1)) for m in (_Q_RE.match(f) for f in
                                      (os.listdir(case_dir) if os.path.isdir(case_dir) else [])) if m]
    return f"Q{(max(nums) + 1) if nums else 1:02d}"


def _sha256(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _git_head() -> Optional[str]:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return None


def _read_csv(path: str) -> List[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _capture_plugin():
    from wom.engine.plugin_base import WOMPlugin

    class _Capture(WOMPlugin):
        name = "quantity_allocation_capture"
        label = "quantity allocation capture"

        def on_post_plan(self, sc_tree, weeks, config, **kw):
            self.tree = sc_tree
    return _Capture()


def _leaf_region(tree) -> Dict[tuple, str]:
    """(product, leaf node_name) -> demand-CSV region. A leaf_out node_id is
    OUT:leaf_out:<region>:<product> (sc_tree_builder._make_node_id); table 2's
    `leaf` column is the node NAME, which need not equal the region (Cookie:
    Retail_JP_CVS / CVS)."""
    out = {}
    for prod in tree.products:
        for nd in tree.iter_all_nodes(prod):
            if nd.node_type == "leaf_out":
                parts = nd.node_id.split(":")
                out[(prod, nd.node_name)] = parts[2] if len(parts) >= 4 else nd.node_name
    return out


def observed_quantities(market_rows, leaf_region: Dict[tuple, str]) -> Dict[tuple, dict]:
    """Flow Check table 2 -> {(sku_id, region): demand / on_time / early / late /
    backlog_end / check}. Detail rows only (the product subtotal and model total
    rows are not added). q2 observed = demand, q4 = on_time + early + late,
    q5 = backlog_end = the request Lot_IDs never shipped by the end of the
    horizon (table 2 matches each Lot_ID with its FIRST actual shipment) -- not
    the last week's CO."""
    obs = {}
    for r in market_rows:
        if r["leaf"] in DETAIL_EXCLUDE or r["product"] == "Σ（モデル全体）":
            continue
        key = (r["product"], leaf_region.get((r["product"], r["leaf"]), r["leaf"]))
        obs[key] = {c: int(r[c]) for c in ("demand", "on_time", "early", "late",
                                           "backlog_end", "check")}
    return obs


def run_quantity_allocation(model_dir: str, allocation_file: str, *,
                            out_dir: str = "output/planning_state",
                            unallocated_note: Optional[str] = None,
                            plugins: Optional[str] = None,
                            extra_plugins: Optional[list] = None,
                            demand_file: str = "demand_forecast.csv",
                            _after_handoff=None) -> dict:
    """Run one quantity allocation. Returns {"status": "ok"|"inconsistent", ...}.
    `_after_handoff(path)` is a test hook called after the demand CSV is written."""
    from wom.allocation.handoff import write_demand_for_quantity_allocation
    from wom.engine.warmup import (materialize_warmup, first_nonzero_demand_week,
                                   read_lot_flow_mode, read_cpu_size)
    from wom.engine.forward_planner import resolve_lot_flow_mode, LOT_FLOW_IDENTITY
    from wom.engine.plan_period import detect_plan_period
    from tools.run_headless_from_folder import run

    model_dir = os.path.normpath(model_dir)
    case = os.path.basename(model_dir)
    case_dir = os.path.join(out_dir, case)
    stem = os.path.splitext(os.path.basename(allocation_file))[0]
    diag_dir = os.path.join(case_dir, "diagnostics")
    commit = _git_head()

    def _fail(checks, extra=None):
        os.makedirs(diag_dir, exist_ok=True)
        path = os.path.join(diag_dir, f"{stem}_inconsistent.json")
        body = {"message": "入力・記録の不整合", "case": case,
                "allocation_file": os.path.abspath(allocation_file), "commit": commit,
                "checks": checks, **(extra or {})}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return {"status": "inconsistent", "diagnostics": path, "checks": checks}

    # 0. identity only -- stop BEFORE planning
    mode = resolve_lot_flow_mode(read_lot_flow_mode(model_dir))
    if mode != LOT_FLOW_IDENTITY:
        return _fail({"lot_flow_mode": {"ok": False, "detail":
                      f"lot_flow_mode={mode}; the quantity mode accepts identity only "
                      f"(stopped before planning)"}})

    # 1. fix the period / capacity from the ORIGINAL demand CSV (as a normal run would)
    materialize_warmup(model_dir, demand_file=demand_file)
    orig_path = os.path.join(model_dir, demand_file)
    base = first_nonzero_demand_week(orig_path)
    if base is None:
        raise ValueError(f"{orig_path}: no demand at all (nothing to allocate)")
    per = detect_plan_period(orig_path)
    fixed = {"warmup_real_start": base, "start": per.start, "end": per.weeks[-1],
             "weeks": per.n_weeks}
    hash_files = ["capacity_plan.csv", "operating_calendar.csv"]
    hashes = {f: _sha256(os.path.join(model_dir, f)) for f in hash_files}

    # 2. hand-off (no price / cost / FX / ga_* file is read)
    qid = next_q_id(case_dir)                 # tentative: used only on success
    gen_name = f"demand_forecast_{qid}.csv"
    gen_path = os.path.join(model_dir, gen_name)
    h = write_demand_for_quantity_allocation(model_dir, allocation_file, qid,
                                             demand_file=demand_file, out_path=gen_path)
    if _after_handoff is not None:
        _after_handoff(gen_path)

    work = os.path.join(case_dir, f"_work_{stem}")
    if os.path.exists(work):
        shutil.rmtree(work)
    fc_dir = os.path.join(work, "flow_check")
    ppc_dir = os.path.join(work, "ppc_not_run")
    cap = _capture_plugin()
    snap = run(model_dir, plugins_spec=plugins, output_ppc_dir=ppc_dir, verbose=False,
               demand_file=gen_name, flow_check_dir=fc_dir, ppc=False,
               warmup_real_start=base, extra_plugins=[cap] + list(extra_plugins or []))
    tree = cap.tree
    ppc_output_created = os.path.exists(ppc_dir)      # must stay False (no PPC run)

    # 3. table 2 detail rows -> per key q2 observed / q4 / q5
    nodes = _read_csv(os.path.join(fc_dir, "flow_check_nodes.csv"))
    obs = observed_quantities(_read_csv(os.path.join(fc_dir, "flow_check_market.csv")),
                              _leaf_region(tree))

    # 4. consistency checks
    hk = {(k["sku_id"], k["region"]): k for k in h["keys"]}
    checks = {}

    def chk(name, bad, detail_ok="OK"):
        checks[name] = {"ok": not bad, "detail": detail_ok if not bad else bad}

    extra_leaves = [f"{k}: demand {v['demand']}" for k, v in obs.items()
                    if k not in hk and v["demand"] != 0]
    missing = [str(k) for k in hk if k not in obs]
    chk("key_set", "; ".join(extra_leaves + [f"{m}: not in table 2" for m in missing]))
    chk("q2_observed_equals_handoff", "; ".join(
        f"{k}: observed {obs[k]['demand']} != handoff {v['q2_in_supply_scope']}"
        for k, v in hk.items() if k in obs and obs[k]["demand"] != v["q2_in_supply_scope"]))
    chk("table2_check_zero", "; ".join(f"{k}: check {v['check']}" for k, v in obs.items()
                                       if v["check"] != 0))
    ng = [f"{r['product']}/{r['node']}: {r['reason']}" for r in nodes if r["status"] == "NG"]
    dup = [f"{r['product']}/{r['node']}: {r['dup_supply_ids']}" for r in nodes
           if int(r.get("dup_supply_ids") or 0) > 0]
    chk("table1_no_ng_no_dup_supply", "; ".join(ng + dup))
    dship = []
    for prod in tree.products:
        for nd in tree.iter_all_nodes(prod):
            if nd.node_type == "leaf_out":
                c = Counter(l for lots in (getattr(nd, "_actual_ship", None) or {}).values()
                            for l in lots)
                n2 = sum(1 for v in c.values() if v > 1)
                if n2:
                    dship.append(f"{prod}/{nd.node_name}: {n2} Lot_ID(s) shipped twice or more")
    chk("leaf_out_no_duplicate_shipment", "; ".join(dship))
    chk("q1_equals_q2_plus_q3", "; ".join(
        f"{k}" for k, v in hk.items()
        if v["q1_original"] != v["q2_in_supply_scope"] + v["q3_not_in_supply_scope"]))
    new_hashes = {f: _sha256(os.path.join(model_dir, f)) for f in hash_files}
    per_bad = []
    if snap["period"]["start"] != fixed["start"] or snap["period"]["weeks"] != fixed["weeks"]:
        per_bad.append(f"period {snap['period']} != fixed {fixed['start']} x {fixed['weeks']}")
    per_bad += [f"{f} changed" for f in hash_files if new_hashes[f] != hashes[f]]
    chk("period_and_capacity_fixed", "; ".join(per_bad))

    if not all(v["ok"] for v in checks.values()):
        if os.path.exists(gen_path):
            os.remove(gen_path)               # the Q number is not used
        res = _fail(checks, {"fixed_period": fixed})
        shutil.rmtree(work, ignore_errors=True)
        return res

    # 5. the state record
    def _quant(rows):
        t = {"q1_original": 0, "q2_in_supply_scope": 0, "q3_not_in_supply_scope": 0,
             "q4_delivered": {"total": 0, "on_time": 0, "early": 0, "late": 0},
             "q5_backlog_end": 0}
        for k, v in rows:
            t["q1_original"] += v["q1_original"]
            t["q2_in_supply_scope"] += v["q2_in_supply_scope"]
            t["q3_not_in_supply_scope"] += v["q3_not_in_supply_scope"]
            o = obs.get(k, {"on_time": 0, "early": 0, "late": 0, "backlog_end": 0})
            for c in ("on_time", "early", "late"):
                t["q4_delivered"][c] += o[c]
            t["q4_delivered"]["total"] += o["on_time"] + o["early"] + o["late"]
            t["q5_backlog_end"] += o["backlog_end"]
        return t

    by_key = [dict(sku_id=k[0], region=k[1], **_quant([(k, v)])) for k, v in sorted(hk.items())]
    by_sku = {s: _quant([(k, v) for k, v in hk.items() if k[0] == s])
              for s in sorted({k[0] for k in hk})}
    total = _quant(list(hk.items()))
    q5 = total["q5_backlog_end"]
    alloc_rows = _read_csv(allocation_file)
    state = {
        "mode": "quantity",
        "allocation_id": qid,
        "case": case,
        "allocation_file": os.path.abspath(allocation_file),
        "allocation": [{"sku_id": r["sku_id"].strip(), "region": r["region"].strip(),
                        "alloc_lots": int(float(r["alloc_lots"]))} for r in alloc_rows],
        "period": {"start": fixed["start"], "end": fixed["end"], "weeks": fixed["weeks"],
                   "warmup_real_start": base},
        "unit": "lot",
        "cpu_size": read_cpu_size(model_dir),
        "valuation": VALUATION,
        "quantities": {"by_key": by_key, "by_sku": by_sku, "total": total},
        "observed_at": OBSERVED_AT,
        "judged_at": fixed["end"],
        "unallocated_treatment": unallocated_note if unallocated_note else "未決（U1）",
        "state": "plan_computed",
        "outcome": "配分した量を期間内に全て引渡し" if q5 == 0 else "配分後の未充足あり",
        "evidence": {"commit": commit, "demand_csv": gen_name, "original_demand_csv": demand_file,
                     "capacity_hashes": hashes, "lot_flow_mode": mode,
                     "plugins": snap.get("config", {}).get("plugins"),
                     "ppc": snap.get("ppc"), "ppc_output_created": ppc_output_created},
    }
    os.makedirs(case_dir, exist_ok=True)
    path = os.path.join(case_dir, f"{qid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    fc_final = os.path.join(case_dir, f"{qid}_flow_check")
    if os.path.exists(fc_final):
        shutil.rmtree(fc_final)
    shutil.move(fc_dir, fc_final)
    shutil.rmtree(work, ignore_errors=True)
    return {"status": "ok", "path": path, "state": state}


def format_block(state: dict) -> str:
    lines = [f"[quantity allocation] {state['case']} {state['allocation_id']}  "
             f"{state['period']['start']}..{state['period']['end']} ({state['period']['weeks']} weeks)  "
             f"unit lot (cpu_size {state['cpu_size']})",
             f"{'sku_id':<18}{'region':<20}{'q1':>7}{'q2':>7}{'q3':>7}{'q4':>7}"
             f"{'(on/early/late)':>18}{'q5':>7}"]
    for r in state["quantities"]["by_key"] + [dict(sku_id="TOTAL", region="",
                                                     **state["quantities"]["total"])]:
        d = r["q4_delivered"]
        split = f"{d['on_time']}/{d['early']}/{d['late']}"
        lines.append(f"{r['sku_id']:<18}{r['region']:<20}{r['q1_original']:>7}"
                     f"{r['q2_in_supply_scope']:>7}{r['q3_not_in_supply_scope']:>7}{d['total']:>7}"
                     f"{split:>18}{r['q5_backlog_end']:>7}")
    lines.append(f"財務：{state['valuation']}  |  {state['outcome']}  |  "
                 f"未配分の扱い：{state['unallocated_treatment']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Quantity allocation mode (no money)")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--allocation-file", required=True)
    ap.add_argument("--out-dir", default="output/planning_state")
    ap.add_argument("--unallocated-note", default=None)
    ap.add_argument("--plugins", default=None,
                    help="same rule as run_headless_from_folder (default: recommended_plugins)")
    a = ap.parse_args(argv)
    r = run_quantity_allocation(a.model_dir, a.allocation_file, out_dir=a.out_dir,
                                unallocated_note=a.unallocated_note, plugins=a.plugins)
    if r["status"] != "ok":
        print("[quantity allocation] 入力・記録の不整合")
        for k, v in r["checks"].items():
            if not v["ok"]:
                print(f"  {k}: {v['detail']}")
        print(f"  diagnostics -> {r['diagnostics']}")
        return 1
    print(format_block(r["state"]))
    print(f"[quantity allocation] -> {r['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
