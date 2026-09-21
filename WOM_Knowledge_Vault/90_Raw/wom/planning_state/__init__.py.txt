# -*- coding: utf-8 -*-
"""
wom/planning_state/ — 計画案の履歴書（Phase 7・Phase 7a で realized を分解に修正）
================================================================================
WOM の三層（① A系統: 配分 → ② Planning Engine: 配置 → ③ Forward+PPC: 実行・損益評価）
を貫く「計画案1件」の記録。地形図を見ていたときの計画（`pre_plan`）と、Weekly PSI を
通過した後の実績（`feasible_plan`）が別物であることを、データ自身に語らせる仕掛け。

正典: requests/Phase7_RequestLetter_to_CodeKun.md V1
      requests/Phase7a_Addendum_to_CodeKun.md（本書が V1.3 を上書きする）
      requests/Phase8_DesignMD_CockpitGUI.md §2 / §8.1（設計背景）

保存先: `<out_dir>/<case>/<allocation_id>.json`（既定 `output/planning_state/`）。

スキーマ:
    {
      "allocation_id": "A03",
      "case": "soysauce-jpy-2027-alloc",
      "scenario_id": "s1_base",
      "mode": "cockpit",
      "state": "pre_plan" | "feasible_plan",
      "created": "2026-09-12T10:00:00",
      "allocation": {"JP": 0.10, "US": 0.45, "EU": 0.45},
      "profit_levels": {...},        # 水準の一覧（P_opt/P_greedy/P_grid/P_hier）。
                                      # compare_with_grid() / hierarchy_gap() の生の返却
      "plan_eval": {...},            # 「選んだ配分」を地図の前提（シナリオ fx）で評価した値
                                      # （Phase 7a・A1。evaluate_point() の生の返却）
      "reversal": {...},
      "placement": {...},
      "realized": null | {...}       # attach_realized() が埋める（Phase 7a・A2 で分解に変更）
    }

【Phase 7a（A0）で訂正した設計ミス】旧 `realized.gap_vs_plan_pct` は2つの誤りを1つの
比率に混ぜていた: (1) 分母を `P_opt`（最善の水準）にしていたが、実際に評価すべきは
「選んだ配分」の利益＝`plan_eval`、(2) A系統（シナリオ fx の1点評価）と PPC（週次の
為替パスを積み上げた実現値）は**そもそも違う原価モデル**であり、単純な引き算は
「計画と実績の差」ではなく「為替前提の差」を測ってしまう。本版は単一の比率をやめ、
`realized.gap_decomposition` に `total = quantity + fx_assumption + residual` として
分解する（Phase 4/5 で `gap_amt` を `expected_gap` と `structural_residual` に
分けたのと同じ規律）。
"""
from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

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
             profit_levels: dict, plan_eval: dict, *,
             allocation_id: Optional[str] = None,
             mode: str = "cockpit", reversal: Optional[dict] = None) -> dict:
    """計画案1件を新規作成する（`state="pre_plan"`）。

    Args:
        plan_eval: 「選んだ配分」を評価した値（Phase 7a・A1）。`evaluate_point()`
            の返却をそのまま反映した dict（`basis`/`fx_usd`/`material_usd`/
            `profit`/`revenue`/`cost`/`lots`）。`profit_levels` は「どの水準を
            選べたか」の一覧であり、`plan_eval` は「実際に選んだものの評価」
            なので役割が違う——`profit_levels.source` が `"P_opt"` でも
            `"manual"` でも、`plan_eval` は常に `allocation` 自体を評価する。

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
        "plan_eval": dict(plan_eval),
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
                     backward_envelope_violation_weeks: List[str]) -> dict:
    """第2層（Backward配置）の結果を記録する（`state` は `pre_plan` のまま）。

    Phase 7a・A3.3: フィールド名を `backward_envelope_violations`（型は件数
    〔int〕想定だったが実装はリストだった）から `backward_envelope_violation_weeks`
    に変更し、スキーマを実装（リスト）に合わせた。件数が要る場面は呼び出し側で
    `len()` を取ること——`violations` という名前のままリストを持たせると、
    件数と誤読される。
    """
    state = dict(state)
    state["placement"] = {
        "earliest_start_week": earliest_start_week,
        "backward_envelope_violation_weeks": list(backward_envelope_violation_weeks),
    }
    return state


def _read_csv(model_dir: str, fname: str) -> List[dict]:
    with open(os.path.join(model_dir, fname), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _leaf_to_market(model_dir: str) -> Dict[str, str]:
    """leaf_out ノード名 -> market_group（`ga_market_aggregation.csv` 由来）。

    `cost_block.py` の `resolve_leaf()` と同じ優先順位（`market_node` 列 > `region`
    列）を軽量に再現する。`region` が複数の `leaf_out` を指す（かつ `market_node`
    が無い）行は、対応先が一意に決まらないため素通し（マッピングしない）に
    留める——`attach_realized()` は要約統計であり、ここで例外を投げて計画loopを
    止めるほどではないため（厳密な検査は `cost_block.py` 側の責務）。
    """
    sct = _read_csv(model_dir, "sc_tree_master.csv")
    leaf_of_region: Dict[str, str] = {}
    region_count: Dict[str, int] = {}
    for r in sct:
        if r.get("node_type") != "leaf_out":
            continue
        region_count[r["region"]] = region_count.get(r["region"], 0) + 1
        leaf_of_region[r["region"]] = r["node_name"]

    mapping: Dict[str, str] = {}
    for r in _read_csv(model_dir, "ga_market_aggregation.csv"):
        node = (r.get("market_node") or "").strip()
        if not node:
            region = r["region"]
            if region_count.get(region, 0) == 1:
                node = leaf_of_region.get(region, "")
        if node:
            mapping[node] = r["market_group"]
    return mapping


def _leaf_currency(model_dir: str) -> Dict[str, str]:
    """leaf_out ノード名（= `ppc_market_price.csv` の `market_node`）-> 販売通貨。"""
    return {r["market_node"]: r["currency"]
           for r in _read_csv(model_dir, "ppc_market_price.csv")}


def fx_effective_from_weekly(model_dir: str,
                             leaf_out_S_weekly: Dict[str, Dict[str, Dict[str, float]]]
                             ) -> Dict[str, float]:
    """出荷数量加重平均の実効為替（Phase 7a・A2.4）。

    fx_effective[ccy] = Σ_w( 出荷数量(w) × rate(ccy,w) ) / Σ_w 出荷数量(w)

    **単純平均にしないこと**——円安が進むモデルでは、出荷が前半に寄るか後半に
    寄るかで値が変わる。JPY（base_currency、rate は常に1.0）は対象外——例に
    合わせて USD/EUR 等の外貨だけを返す。
    """
    rate: Dict[Tuple[str, str], float] = {}
    for r in _read_csv(model_dir, "ppc_fx_rate.csv"):
        rate[(r["week"], r["currency"])] = float(r["rate"])
    leaf_ccy = _leaf_currency(model_dir)

    weighted_sum: Dict[str, float] = {}
    weight_total: Dict[str, float] = {}
    for _prod, nodes in (leaf_out_S_weekly or {}).items():
        for node, week_qty in nodes.items():
            ccy = leaf_ccy.get(node)
            if not ccy or ccy == "JPY":
                continue
            for week, qty in week_qty.items():
                if qty <= 0:
                    continue
                r = rate.get((week, ccy))
                if r is None:
                    continue
                weighted_sum[ccy] = weighted_sum.get(ccy, 0.0) + qty * r
                weight_total[ccy] = weight_total.get(ccy, 0.0) + qty
    return {ccy: weighted_sum[ccy] / weight_total[ccy]
           for ccy in weighted_sum if weight_total.get(ccy, 0.0) > 0}


def _evaluate_plan_at_fx(model_dir: str, allocation: Dict[str, float], plan_eval: dict,
                         fx_effective: Dict[str, float], cap_wk: float) -> dict:
    """A系統を `fx_effective` で再評価する（Phase 7a・A1 の `plan_at_realized_fx`）。

    `plan_eval` と同じ `allocation`・`material_usd` を使い、為替だけを実現値に
    差し替える——「同じ地図を、違う為替の前提で読み直す」操作である。
    """
    from wom.allocation.cost_block import derive_cost_blocks
    from wom.allocation.grid import WEEKS, evaluate_point, markets_of
    from wom.allocation.transmission import Scenario

    blocks, tp = derive_cost_blocks(model_dir)
    markets = markets_of(blocks)
    x = tuple(float(allocation.get(m, 0.0)) for m in markets)

    fx_usd = fx_effective.get("USD", plan_eval["fx_usd"])
    if "USD" in fx_effective and "EUR" in fx_effective:
        sc = Scenario(fx_usd=fx_usd, material_usd=plan_eval["material_usd"],
                      eur_per_usd=fx_effective["EUR"] / fx_effective["USD"])
    else:
        sc = Scenario(fx_usd=fx_usd, material_usd=plan_eval["material_usd"])

    ep = evaluate_point(x, blocks, tp, sc, cap_wk, weeks=WEEKS)
    return {"profit": ep["profit"], "revenue": ep["rev"], "cost": ep["cost"]}


def attach_realized(state: dict, snapshot: dict, mgmt_result=None,
                    model_dir: Optional[str] = None,
                    cap_wk: Optional[float] = None) -> dict:
    """第3層（Forward+PPC）の実績を `realized` に埋め、`state` を `feasible_plan` にする。

    `snapshot` は `tools.run_headless_from_folder.run(..., planning_state=True)` の
    戻り値を想定する（`ppc` / `planning_state_extras` を参照する）。
    `mgmt_result`（`wom.engine.management.ManagementAnalysisResult`、既定 None）を
    渡すとその `issues` を採用する。渡さない場合 `issues` は空リストのまま
    （base シナリオとの比較用の working-capital 指標〔ccc_wks 等〕が headless の
    スナップショットに無く、生成経路が無いため。Phase 8 送り・Request Letter A3.2）。

    `model_dir` と `cap_wk` の両方を渡すと（かつ `state["plan_eval"]` があれば）
    `realized.fx_effective` / `realized.plan_at_realized_fx` /
    `realized.gap_decomposition` を計算する（Phase 7a・A2）。片方でも欠けていれば
    これらは空のまま——旧来の `model_dir` だけ渡す呼び方（`realized.allocation`
    のロールアップのみ）も引き続き動く。

    Raises:
        ValueError: 分解を計算しようとした際、`plan_eval.lots` と
            `realized.ppc.lots` が一致しない場合（Request Letter A2.5：
            数量がずれるのはハンドオフが壊れているか、需要・能力・warmup の
            どこかに原因がある事象なので、ここで吸収せず止めて報告する）。
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

    ppc_block = {
        "basis": "ppc_ledger",
        "profit": float(ppc.get("gross_profit_base", 0.0) or 0.0),
        "revenue": float(ppc.get("revenue_base", 0.0) or 0.0),
        "cost": float(ppc.get("cost_base", 0.0) or 0.0),
        "lots": grand_total,                        # PSI bridge の数量（leaf_out_S 合計）
        "lot_records": int(ppc.get("total_lots", 0) or 0),
    }

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

    fx_effective: Dict[str, float] = {}
    plan_at_realized_fx: Optional[dict] = None
    gap_decomposition: Optional[dict] = None
    plan_eval = state.get("plan_eval")
    if model_dir and cap_wk and plan_eval:
        fx_effective = fx_effective_from_weekly(model_dir, extras.get("leaf_out_S_weekly", {}))
        plan_at_realized_fx = _evaluate_plan_at_fx(
            model_dir, state["allocation"], plan_eval, fx_effective, cap_wk)

        if abs(ppc_block["lots"] - plan_eval["lots"]) > 1e-6:
            raise ValueError(
                f"attach_realized(): quantity mismatch — plan_eval.lots="
                f"{plan_eval['lots']!r} but realized.ppc.lots={ppc_block['lots']!r}. "
                f"The A系統<->Planning Engine handoff appears broken (demand / "
                f"capacity / warmup?). Request Letter A2.5 says stop and report "
                f"here rather than absorb the difference into 'quantity'."
            )

        gap_decomposition = {
            "total": ppc_block["profit"] - plan_eval["profit"],
            "quantity": 0.0,     # lots が一致する限り 0（A2.5）
            "fx_assumption": plan_at_realized_fx["profit"] - plan_eval["profit"],
            "residual": ppc_block["profit"] - plan_at_realized_fx["profit"],
            "residual_revenue": ppc_block["revenue"] - plan_at_realized_fx["revenue"],
            "residual_cost": ppc_block["cost"] - plan_at_realized_fx["cost"],
        }

    state["realized"] = {
        "allocation": realized_allocation,
        "ppc": ppc_block,
        "fx_effective": fx_effective,
        "plan_at_realized_fx": plan_at_realized_fx,
        "gap_decomposition": gap_decomposition,
        "unmet_lots": unmet_lots,
        "capacity_violation_weeks": cap_violation_weeks,
        "peak_inventory_weeks": peak_inventory_weeks,
        "issues": issues,
    }
    state["state"] = "feasible_plan"
    return state
