# -*- coding: utf-8 -*-
"""
wom/cockpit/s3_view_model.py — S3 Run 画面が出す値を作る純関数（Phase 8-3c）
================================================================================
**tkinter に依存しない。** `run_s3()` が第2層・第3層（`write_demand_for_allocation()`
→ `run_headless()` → `attach_placement()` / `attach_realized()`）を実際に実行し、
`build_s3_view()` がその結果から画面に出す値を作る——`wom/cockpit/s3_run.py`
（tkinter 側）は並べるだけ（C9、S1 と同じ規律）。

正典: requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md §N3/§N4/§N5/§N6

`run_s3()` は9秒前後かかる（`tools/run_headless_from_folder.run()` が大半）ため、
**呼び出し側がワーカースレッドで呼ぶこと**。本関数自体は tkinter を一切参照しない
（スレッド安全性は「Tk に触らない」呼び出し側の責務であって、この関数の中身とは
無関係）。
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence

from wom.cockpit.s1_view_model import format_market_name


def run_s3(model_dir: str, scenario_id: str, cap_wk: float, pre_plan_state: dict, *,
          uom: Optional[str] = None, out_dir: str = "output/planning_state",
          ppc_out: str = "output/ppc") -> dict:
    """S3 の手順4〜6を実行する（`tools/run_planning_loop.py` の手順4〜6と同じ）。

    **保存はしない**——`pre_plan_state` に配置・実績を merge した「未保存の
    feasible_plan 相当」の state を返すだけ。実際にディスクへ書くのは
    `AllocationPanel.commit()` と対をなす `RunPanel.commit()`（呼び出し側）の
    役目（N7: `⚑` が「実行結果を記録する」の実体）。

    Returns:
        {"state": dict, "snap": dict}
        `state`: `attach_placement()` → `attach_realized()` を適用した state
            （`state["state"] == "feasible_plan"`。まだ保存されていない）
        `snap`: `run_headless()` の生の返却（`planning_state_extras` を含む。
            図・補助パネルが読む）
    """
    from wom.allocation.handoff import write_demand_for_allocation
    from tools.run_headless_from_folder import run as run_headless
    import wom.planning_state as planning_state

    allocation = pre_plan_state["allocation"]
    allocation_id = pre_plan_state["allocation_id"]

    handoff = write_demand_for_allocation(
        model_dir, allocation, allocation_id, cap_wk=cap_wk, uom=uom)
    demand_file = os.path.basename(handoff["path"])

    snap = run_headless(model_dir, demand_file=demand_file, planning_state=True,
                        output_ppc_dir=ppc_out, verbose=False)

    extras = snap.get("planning_state_extras", {}) or {}
    state = planning_state.attach_placement(
        pre_plan_state, earliest_start_week=snap["period"]["start"],
        backward_envelope_violation_weeks=extras.get("backward_envelope_weeks", []))
    state = planning_state.attach_realized(state, snap, model_dir=model_dir, cap_wk=cap_wk)

    return {"state": state, "snap": snap}


def _format_conclusion_ja(state: dict, snap: dict) -> List[str]:
    """N3: 結論行3行を組む。"""
    extras = snap.get("planning_state_extras", {}) or {}
    realized = state.get("realized") or {}

    total_weeks = snap["period"]["weeks"]
    cap_hard_weeks: Sequence[str] = extras.get("cap_hard_violation_weeks", []) or []
    cap_soft_weeks: Sequence[str] = extras.get("cap_soft_violation_weeks", []) or []
    violated_weeks = sorted(set(cap_hard_weeks) | set(cap_soft_weeks))
    ok_weeks = total_weeks - len(violated_weeks)
    pct = (ok_weeks / total_weeks * 100.0) if total_weeks else 0.0
    line1 = f"{total_weeks} 週中 {ok_weeks} 週は能力内（{pct:.0f}%）"

    # cap_hard は Forward Planner が P を封じる物理天井——「張り付き」（sealed）で
    # あって「超過」ではない（超過は定義上起こり得ない）。cap_soft は残業帯で
    # 実際に超えうる——こちらが「超過」。両者を「能力超過」に一括りにしない
    # （Claude君の検証で発見・訂正済み、正典 requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md）。
    unmet = realized.get("unmet_lots", 0.0) or 0.0
    if cap_hard_weeks or cap_soft_weeks:
        line2 = (f"cap_hard {len(cap_hard_weeks)}週で上限に張り付き（需要が溢れた） / "
                f"cap_soft {len(cap_soft_weeks)}週で超過（残業帯）、未充足 {unmet:.0f} lot")
    else:
        line2 = f"能力超過なし（cap_hard 0週 / cap_soft 0週）、未充足 {unmet:.0f} lot"

    plan_x: Dict[str, float] = state.get("allocation", {}) or {}
    real_x: Dict[str, float] = realized.get("allocation", {}) or {}
    markets = sorted(set(plan_x) | set(real_x), key=lambda m: -plan_x.get(m, 0.0))

    def _pct_row(x: Dict[str, float]) -> str:
        return " / ".join(f"{format_market_name(m)} {round(x.get(m, 0.0) * 100)}"
                          for m in markets)

    line3 = f"実際に供給できた配分 {_pct_row(real_x)}（計画 {_pct_row(plan_x)}）"
    return [line1, line2, line3]


def _capacity_nodes(snap: dict) -> List[dict]:
    """N5/N6: 能力を持つノードの一覧を、cap_hard 張り付き→cap_soft 超過の多い順に並べる。

    ノード名は製品をまたいで衝突しうる（実測: oil-global-2027 は8製品）ため、
    `(product, name)` を内部キーにする——`capacity_series` 自体が
    `{product: {node_name: {...}}}` と製品でネストされているのと同じ理由
    （Request Letter §N4「製品でネストして報告すること」への対応）。

    違反判定は `p[w] > cap_hard[w]` のような系列比較では**行わない**——
    ForwardPlanner は cap_hard で P を封じる（sealing）ため、この不等式は
    設計上ほぼ常に成立しない（Claude君の検証で発見）。`capacity_events`
    （`node.node_id` で記録された実イベントを node_name に解決したもの）を
    正とする。
    """
    extras = snap.get("planning_state_extras", {}) or {}
    series_by_product: Dict[str, Dict[str, dict]] = extras.get("capacity_series", {}) or {}
    events_by_product: Dict[str, Dict[str, dict]] = extras.get("capacity_events", {}) or {}
    multi_product = len(series_by_product) > 1

    nodes: List[dict] = []
    for product, by_node in series_by_product.items():
        events_for_prod = events_by_product.get(product, {}) or {}
        for name, series in by_node.items():
            events = events_for_prod.get(name, {}) or {}
            hard_weeks = list(events.get("cap_hard_weeks", []) or [])
            soft_weeks = list(events.get("cap_soft_weeks", []) or [])
            label = f"{name} [{product}]" if multi_product else name
            # 語は `series_label_ja`（データ側が宣言）にだけ置く。ここでも画面でも
            # series_kind を語に翻訳しない——タイトルは宣言された語から単位を除く
            # だけ（Phase 8-3c-4・X2）。
            series_label_ja = series["series_label_ja"]
            kind_word = series_label_ja.split("（", 1)[0]
            labels = series["week_labels"]
            shortfall_weeks = [labels[w] for w, v in enumerate(series["shortfall"]) if v > 0]
            nodes.append({
                "product": product, "name": name, "label": label,
                "series": series, "hard_weeks": hard_weeks, "soft_weeks": soft_weeks,
                "series_kind": series["series_kind"],
                "series_label_ja": series_label_ja,
                "title_ja": f"{label} — {kind_word} vs Capacity Limits",
                "shortfall_weeks": shortfall_weeks,
            })
    nodes.sort(key=lambda n: (-len(n["hard_weeks"]), -len(n["soft_weeks"]), n["label"]))
    return nodes


def build_s3_view(pre_plan_state: dict, run_result: Optional[dict]) -> dict:
    """S3 に出す値をすべて作る。tkinter に依存しない。

    Args:
        pre_plan_state: S1 の `commit()` が保存した state（`state="pre_plan"`）
        run_result: `run_s3()` の返却、または未実行なら None
    """
    if run_result is None:
        return {
            "has_run": False,
            "state": pre_plan_state,
            "conclusion_lines_ja": ["▶ 実行 を押してください。"],
            "capacity_nodes": [],
            "default_node_key": None,
        }

    state = run_result["state"]
    snap = run_result["snap"]
    nodes = _capacity_nodes(snap)
    default_key = (nodes[0]["product"], nodes[0]["name"]) if nodes else None

    return {
        "has_run": True,
        "state": state,
        "conclusion_lines_ja": _format_conclusion_ja(state, snap),
        "capacity_nodes": nodes,
        "default_node_key": default_key,
    }
