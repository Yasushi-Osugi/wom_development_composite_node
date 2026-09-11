# -*- coding: utf-8 -*-
"""
wom/planning_state/ — 計画案の履歴書（Phase 7）
================================================================================
WOM の三層（① A系統: 配分 → ② Planning Engine: 配置 → ③ Forward+PPC: 実行・損益評価）
を貫く「計画案1件」の記録。地形図を見ていたときの計画（`pre_plan`）と、Weekly PSI を
通過した後の実績（`feasible_plan`）が別物であることを、データ自身に語らせる仕掛け。

正典: requests/Phase7_RequestLetter_to_CodeKun.md V1
      requests/Phase8_DesignMD_CockpitGUI.md §2 / §8.1（設計背景）

保存先: `<out_dir>/<case>/<allocation_id>.json`（既定 `output/planning_state/`）。

スキーマ（V1.1）:
    {
      "allocation_id": "A03",
      "case": "soysauce-jpy-2027-alloc",
      "scenario_id": "s1_base",
      "mode": "cockpit",
      "state": "pre_plan" | "feasible_plan",
      "created": "2026-09-12T10:00:00",
      "allocation": {"JP": 0.10, "US": 0.45, "EU": 0.45},
      "profit_levels": {...},        # compare_with_grid() / hierarchy_gap() の生の返却
      "reversal": {...},
      "placement": {...},
      "realized": null | {...}       # attach_realized() が埋める
    }

`profit_levels.gap_vs_plan_pct`・`realized.gap_vs_plan_pct` の基準は **`P_opt`**
（`true_continuous_optimum()`）である。設計書 §2.3 は `P_grid` を分母にしていたが、
Phase 6-3 の実測で「格子の最良点は解像度と次元に依存し、`P_greedy` との大小すら
決まらない」ことが分かったため、本 Phase で訂正した（Request Letter V1.2）。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

# V1.3: 「在庫が安全在庫の N 倍を超えた週」の N。根拠は薄いので実ケースを見てから
# 調整する前提の暫定値——定数を1箇所に置いて名前を付ける（Request Letter 申し送り）。
PEAK_INVENTORY_MULTIPLE = 2.0

_ID_RE = re.compile(r"^A(\d+)\.json$")


def _case_dir(case: str, out_dir: str) -> str:
    return os.path.join(out_dir, case)


def _next_allocation_id(case: str, out_dir: str) -> str:
    """`out_dir/<case>/` の既存 `A\\d+.json` から次の連番を決める（乱数・UUID 不使用）。"""
    d = _case_dir(case, out_dir)
    if not os.path.isdir(d):
        return "A01"
    nums = []
    for fname in os.listdir(d):
        m = _ID_RE.match(fname)
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 1
    return f"A{nxt:02d}"


def new_state(case: str, scenario_id: str, allocation: Dict[str, float],
             profit_levels: dict, *, allocation_id: Optional[str] = None,
             mode: str = "cockpit", reversal: Optional[dict] = None) -> dict:
    """計画案1件を新規作成する（`state="pre_plan"`）。

    `allocation_id` を省略した場合は `save()` 呼び出し時に `out_dir` の既存ファイルを
    見て次の連番（`A01`, `A02`, …）を割り当てる（`new_state()` 自体は `out_dir` を
    知らないため、確定は `save()` 側で行う）。
    """
    return {
        "allocation_id": allocation_id,   # None のままなら save() で確定
        "case": case,
        "scenario_id": scenario_id,
        "mode": mode,
        "state": "pre_plan",
        "created": datetime.now().isoformat(timespec="seconds"),
        "allocation": dict(allocation),
        "profit_levels": dict(profit_levels),
        "reversal": dict(reversal) if reversal is not None else {},
        "placement": {},
        "realized": None,
    }


def save(state: dict, out_dir: str = "output/planning_state") -> str:
    """`state` を JSON として書き出し、書いたパスを返す。

    `allocation_id` が未確定（None）なら、ここで `out_dir/<case>/` の既存ファイルを
    見て次の連番を割り当てる（C7: 乱数・UUID は使わない・決定的）。
    """
    if state.get("allocation_id") is None:
        state = dict(state)
        state["allocation_id"] = _next_allocation_id(state["case"], out_dir)

    d = _case_dir(state["case"], out_dir)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{state['allocation_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")
    return path


def load(case: str, allocation_id: str, out_dir: str = "output/planning_state") -> dict:
    path = os.path.join(_case_dir(case, out_dir), f"{allocation_id}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_states(case: str, out_dir: str = "output/planning_state") -> List[dict]:
    """`case` の全計画案を `allocation_id` 昇順で返す（S5 の一覧用）。"""
    d = _case_dir(case, out_dir)
    if not os.path.isdir(d):
        return []
    ids = sorted(m.group(0)[:-5] for m in
                (_ID_RE.match(fn) for fn in os.listdir(d)) if m)
    return [load(case, aid, out_dir) for aid in ids]


def attach_placement(state: dict, *, earliest_start_week: Optional[str],
                     backward_envelope_violations: List[dict]) -> dict:
    """第2層（Backward配置）の結果を記録する（`state` は `pre_plan` のまま）。"""
    state = dict(state)
    state["placement"] = {
        "earliest_start_week": earliest_start_week,
        "backward_envelope_violations": list(backward_envelope_violations),
    }
    return state


def _leaf_to_market(model_dir: str) -> Dict[str, str]:
    """leaf_out ノード名 -> market_group（`ga_market_aggregation.csv` 由来）。

    `cost_block.py` の `resolve_leaf()` と同じ優先順位（`market_node` 列 > `region`
    列）を軽量に再現する。`region` が複数の `leaf_out` を指す（かつ `market_node`
    が無い）行は、対応先が一意に決まらないため素通し（マッピングしない）に
    留める——`attach_realized()` は要約統計であり、ここで例外を投げて計画loopを
    止めるほどではないため（厳密な検査は `cost_block.py` 側の責務）。
    """
    import csv as _csv

    def _rows(fname: str) -> List[dict]:
        with open(os.path.join(model_dir, fname), encoding="utf-8", newline="") as f:
            return list(_csv.DictReader(f))

    sct = _rows("sc_tree_master.csv")
    leaf_of_region: Dict[str, str] = {}
    region_count: Dict[str, int] = {}
    for r in sct:
        if r.get("node_type") != "leaf_out":
            continue
        region_count[r["region"]] = region_count.get(r["region"], 0) + 1
        leaf_of_region[r["region"]] = r["node_name"]

    mapping: Dict[str, str] = {}
    for r in _rows("ga_market_aggregation.csv"):
        node = (r.get("market_node") or "").strip()
        if not node:
            region = r["region"]
            if region_count.get(region, 0) == 1:
                node = leaf_of_region.get(region, "")
        if node:
            mapping[node] = r["market_group"]
    return mapping


def attach_realized(state: dict, snapshot: dict, mgmt_result=None,
                    model_dir: Optional[str] = None) -> dict:
    """第3層（Forward+PPC）の実績を `realized` に埋め、`state` を `feasible_plan` にする。

    `snapshot` は `tools.run_headless_from_folder.run(..., planning_state=True)` の
    戻り値を想定する（`ppc` / `psi` / `planning_state_extras` を参照する）。
    `mgmt_result`（`wom.engine.management.ManagementAnalysisResult`、既定 None）を
    渡すとその `issues` を採用する。渡さない場合 `issues` は空リストになる
    （base シナリオとの比較が要る分析であり、本 Phase の閉ループには必須ではない）。
    `model_dir` を渡すと `realized.allocation` を `leaf_out` ノード単位ではなく
    `ga_market_aggregation.csv` の `market_group`（= 計画時の `allocation` と同じ
    キー空間）に集約する。渡さない場合は `leaf_out` ノード名のまま返す
    （`state["allocation"]` のキーと一致しないため、計画比の比較には使えない）。
    """
    state = dict(state)
    ppc = snapshot.get("ppc", {}) or {}
    extras = snapshot.get("planning_state_extras", {}) or {}

    # realized.allocation: leaf_out の実供給（S）を市場（market_group）ごとに合計・正規化
    leaf_out_S: Dict[str, Dict[str, float]] = extras.get("leaf_out_S", {}) or {}
    leaf_to_market = _leaf_to_market(model_dir) if model_dir else {}
    totals: Dict[str, float] = {}
    for _prod, nodes in leaf_out_S.items():
        for node, s in nodes.items():
            key = leaf_to_market.get(node, node)
            totals[key] = totals.get(key, 0.0) + float(s)
    grand_total = sum(totals.values())
    realized_allocation = {m: (v / grand_total if grand_total else 0.0)
                           for m, v in totals.items()}

    profit_ppc = float(ppc.get("gross_profit_base", 0.0) or 0.0)
    p_opt = (state.get("profit_levels") or {}).get("P_opt")
    gap_vs_plan_pct = ((profit_ppc - p_opt) / p_opt * 100.0) if p_opt else None

    leaf_out_CO: Dict[str, Dict[str, float]] = extras.get("leaf_out_CO", {}) or {}
    unmet_lots = sum(v for nodes in leaf_out_CO.values() for v in nodes.values())

    cap_violation_weeks = sorted(
        set(extras.get("cap_hard_violation_weeks", []) or []) |
        set(extras.get("cap_soft_violation_weeks", []) or [])
    )
    inv_peaks: Dict[str, Dict[str, list]] = extras.get("inventory_peak_weeks", {}) or {}
    peak_inventory_weeks = sorted({
        wk for nodes in inv_peaks.values() for wks in nodes.values() for wk in wks
    })

    issues = []
    if mgmt_result is not None:
        for i in getattr(mgmt_result, "issues", []) or []:
            issues.append({
                "code": i.code, "severity": i.severity,
                "title_ja": i.title_ja, "detail_ja": i.detail_ja,
            })

    state["realized"] = {
        "allocation": realized_allocation,
        "profit_ppc": profit_ppc,
        "gap_vs_plan_pct": gap_vs_plan_pct,
        "unmet_lots": unmet_lots,
        "capacity_violation_weeks": cap_violation_weeks,
        "peak_inventory_weeks": peak_inventory_weeks,
        "issues": issues,
    }
    state["state"] = "feasible_plan"
    return state
