# -*- coding: utf-8 -*-
"""
wom/allocation/merit_order.py — 生産配分のメリットオーダー曲線（Phase 4 ①）
================================================================================
Phase 3（B系統・週次「どのサプライヤーから調達するか」）のメリットオーダー曲線を、
A系統（`ask_global_allocation`・年次「どの市場に何個供給するか」）向けに再構成する。

対象問題の違い（設計正典 §1.1）:
    Phase 3: サプライヤーを単価**昇順**に積み、需要線との交点＝限界サプライヤーの単価
    Phase 4: 市場を単位マージン**降順**に積み、能力線との交点＝**能力のシャドープライス λ**

正典: requests/Phase4_DesignMD_AllocationMeritRegime.md §2-3
参照: wom/allocation/grid.py（MARKETS, evaluate_point, scan_surface, best_point）

このモジュールは純関数のみ（描画コードは tools/plot_allocation_merit_regime.py）。
既存 A系統モジュール（transmission.py / cost_block.py / grid.py / analytics.py）は無変更。
"""
from __future__ import annotations

import itertools
from dataclasses import replace
from typing import Dict, List, Optional

from wom.allocation.transmission import (
    CostBlock, DEFAULT_TRANSFER_PRICE_USD, Scenario, unit_pnl, unit_pnl_at_quantity,
)
from wom.allocation.grid import MARKETS, WEEKS, best_point


def build_allocation_merit_order(
    blocks: Dict[str, CostBlock],
    sc: Scenario,
    cap_wk: float,
    *,
    transfer_price_usd: float = DEFAULT_TRANSFER_PRICE_USD,
    weeks: int = WEEKS,
) -> dict:
    """市場を単位マージン降順に積んだメリットオーダーを組む。

    設計書 §3.2（R1）: マージンが負の市場は「供給すべきでない」ため、
    積み上げ対象から除外する（`excluded` に列挙）。`evaluate_point()` は
    符号を見ずに配分するため、この非対称は意図的（格子スキャンは面を出す
    ためのものであり、①は「あるべき配分」を示す図であるため）。

    Phase 5（数量依存の関税・cliff型、requests/Phase5_DesignMD_NonConcaveTariff.md §3.5）:
    ①は**意図的に近視眼的**なままにする。順位付けと利益計算で使う単価を分ける：
      - 順位付け：配分量0における単価（cb.tariff_rate、特恵なし）＝貪欲法が
        決定時点で見えている値。これが「近視眼的」の実体
      - 利益計算：実際の配分量に応じた単価（tariff_at(allocated) 適用後）。
        現実に発生する損益は実配分量で決まるため、閾値をたまたま超えていれば
        特恵は実際に効く
    cliff未設定の CostBlock では両者は常に一致するため、Phase 4 の回帰値
    （135,529,822.5 等）は1円も変わらない。

    Args:
        blocks: 市場 -> CostBlock（derive_cost_blocks() の戻り値）
        sc: 外部環境シナリオ
        cap_wk: 週次能力（lot/週）
        transfer_price_usd: 移転価格（USD）
        weeks: 計画期間（週数、既定 104）

    Returns:
        {
            "cap": 83200.0,
            "blocks": [                       # 単位マージン降順
                {"market": "EU", "margin": 1831.5, "width": 35175,
                 "allocated": 35175, "cumulative": 35175, "served": "full"},
                ...
                {"market": "JP", "margin": 750.0, "width": 30150,
                 "allocated": 12849, "cumulative": 83200, "served": "partial"},
            ],
            "excluded": [],                   # margin <= 0 で対象外にした市場
            "lambda": 750.0,                  # 能力のシャドープライス（余力ありなら 0.0）
            "marginal_market": "JP",          # None なら能力が余っている
            "x": {"JP": 0.1544, "US": 0.4228, "EU": 0.4228},
            "profit": 135529822.5,            # margin_effective ベース（Phase 5）
            "idle": 0.0,                      # 遊休能力
            "unmet": {"JP": 17301, "US": 0, "EU": 0},
            "preferential": None,             # cliff の発動状況（設定市場が無ければ None）
        }
    """
    cap = cap_wk * weeks

    margins = {m: unit_pnl(blocks[m], sc, transfer_price_usd)["margin"] for m in MARKETS}
    included = sorted((m for m in MARKETS if margins[m] > 0), key=lambda m: -margins[m])
    excluded = [m for m in MARKETS if margins[m] <= 0]

    merit_blocks: List[dict] = []
    x: Dict[str, float] = {m: 0.0 for m in MARKETS}
    unmet: Dict[str, float] = {}
    preferential: Dict[str, dict] = {}

    cum = 0.0
    lam = 0.0
    marginal_market: Optional[str] = None

    for m in included:
        width = blocks[m].demand_qty
        remaining = max(cap - cum, 0.0)
        allocated = min(float(width), remaining)

        if allocated <= 0.0:
            served = "none"
        elif allocated >= width:
            served = "full"
        else:
            served = "partial"

        cum = cum + allocated

        # 利益計算は実配分量に応じた単価（cliff が実際に発動していれば効く）
        margin_effective = unit_pnl_at_quantity(
            blocks[m], sc, allocated, transfer_price_usd
        )["margin"]

        merit_blocks.append({
            "market": m, "margin": margins[m], "width": width,
            "allocated": allocated, "cumulative": cum, "served": served,
            "margin_effective": margin_effective,
        })

        cb = blocks[m]
        if cb.tariff_rate_preferential is not None and cb.preferential_threshold_lot is not None:
            preferential[m] = {
                "threshold": cb.preferential_threshold_lot,
                "allocated": allocated,
                "triggered": allocated >= cb.preferential_threshold_lot,
                "rate_base": cb.tariff_rate,
                "rate_preferential": cb.tariff_rate_preferential,
                "margin_ranking": margins[m],
                "margin_effective": margin_effective,
            }

        if served == "partial" and marginal_market is None:
            lam = margins[m]
            marginal_market = m

        x[m] = allocated / cap if cap else 0.0
        unmet[m] = width - allocated

    # 端点ケース: 能力がちょうど市場境界で尽きる（partial が一度も出ない）が
    # 能力は完全に消費されている場合、最後に供給された市場が実質的な限界市場。
    idle = max(cap - cum, 0.0)
    if marginal_market is None and idle <= 1e-6 and merit_blocks:
        last = merit_blocks[-1]
        marginal_market = last["market"]
        lam = last["margin"]

    for m in excluded:
        unmet[m] = float(blocks[m].demand_qty)
        x[m] = 0.0

    # 実配分量に応じた単価（margin_effective）で利益を計算する。
    # cliff未設定・未発動なら margin_effective == margin（ランキング用単価）なので
    # Phase 4 の回帰値は変わらない。
    profit = sum(b["allocated"] * b["margin_effective"] for b in merit_blocks)

    return {
        "cap": cap,
        "blocks": merit_blocks,
        "excluded": excluded,
        "excluded_margins": {m: margins[m] for m in excluded},
        "lambda": lam,
        "marginal_market": marginal_market,
        "x": x,
        "profit": profit,
        "idle": idle,
        "unmet": unmet,
        "preferential": preferential if preferential else None,
    }


def true_continuous_optimum(
    blocks: Dict[str, CostBlock],
    sc: Scenario,
    cap_wk: float,
    *,
    transfer_price_usd: float = DEFAULT_TRANSFER_PRICE_USD,
    weeks: int = WEEKS,
    _return_all_cases: bool = False,
) -> dict:
    """cliff（数量依存関税）の on/off を全列挙し、各ケースを線形問題として
    厳密に解いて、真の連続最適解を返す（Phase 6-1）。

    利益関数は cliff の on/off を固定すれば区間ごとに線形・分離可能になる。
    したがって「どの市場が特恵を発動しているか」の組合せを全列挙し、各組合せ
    の中で厳密解を求め、その最大値が真の連続最適である。

    正典: requests/Phase6-1_RequestLetter_to_CodeKun.md V1（設計書
    requests/Phase6_DesignMD_NMarketHierarchy.md §3 の実装仕様）。

    **§3.3 との相違（重要）**: 設計書 §3.3 は「税率を固定して解いてから、
    結果が閾値と矛盾しないか事後チェックする」方式を示していたが、この方式は
    閾値が binding な解（＝ちょうど閾値まで積むのが最適な解）を取り逃す欠陥が
    ある。本実装は Request Letter V1.2 の方式（**閾値を配分量の下限/上限として
    先に制約に持たせてから解く**）に従う。この方式では `S` の仮定と解の間に
    構造的な矛盾が起こり得ないため、事後の整合性チェックは不要（かつ存在しない）。
    大杉さん確認済み：「§3.3 は Request Letter V1.2 が優先」（2026-09-11）。

    Args:
        blocks: 市場 -> CostBlock
        sc: 外部環境シナリオ
        cap_wk: 週次能力（lot/週）
        transfer_price_usd: 移転価格（USD）
        weeks: 計画期間（週数、既定 104）
        _return_all_cases: テスト用の内部引数（既定 False）。True のとき
            戻り値に "_all_cases"（全ケースの active_cliffs/profit/feasible の
            リスト）を追加する。公開 API の一部ではない。

    Returns:
        {
            "profit": 103881758.0,              # 真の連続最適利益（P_opt）
            "x": {"JP": 0.0001, "US": 0.6763, "EU": 0.3236},  # 配分比率（q / cap）
            "q": {"JP": 7.0, "US": 35168.0, "EU": 16825.0},   # 配分量（lot）
            "active_cliffs": ["US"],             # 最適ケースで発動している特恵（MARKETS 順）
            "cases_evaluated": 2,                # 列挙したケース数（= 2^|K|）
            "cases_feasible": 2,                 # 手順4(a) を通ったケース数
            "idle": 0.0,                         # cap − Σq
        }

    Raises:
        ValueError: cliff を持つ市場が12を超える場合（2^13 通り以上は実務ケースとして
            想定しない）。
    """
    cap = cap_wk * weeks

    # 手順1: cliff を持つ市場の集合 K（MARKETS の順序を維持）
    K = [m for m in MARKETS
         if blocks[m].tariff_rate_preferential is not None
         and blocks[m].preferential_threshold_lot is not None]

    if len(K) > 12:
        raise ValueError(
            f"true_continuous_optimum(): cliff を持つ市場が多すぎます "
            f"(len(K)={len(K)} > 12)。2^{len(K)} 通りの列挙は実務時間で終わりません。"
        )

    cases_evaluated = 0
    cases_feasible = 0
    best_case: Optional[dict] = None
    all_cases: List[dict] = []

    # 手順2: 部分集合 S ⊆ K を |S|=0,1,...,|K| の順に全列挙する（決定的な順序）
    for r in range(len(K) + 1):
        for S in itertools.combinations(K, r):
            cases_evaluated += 1
            in_s = set(S)

            # 手順3: 下界・上界・税率を固定する（設計の要。§3.3 ではなく
            # Request Letter V1.2 に従う——事後チェックではなく先に制約として持たせる）
            rate: Dict[str, float] = {}
            lower: Dict[str, float] = {}
            upper: Dict[str, float] = {}
            for m in MARKETS:
                cb = blocks[m]
                if m in in_s:                        # 特恵を発動していると仮定
                    rate[m] = cb.tariff_rate_preferential
                    lower[m] = cb.preferential_threshold_lot
                    upper[m] = float(cb.demand_qty)
                elif m in K:                          # cliff を持つが未発動と仮定
                    rate[m] = cb.tariff_rate
                    lower[m] = 0.0
                    upper[m] = min(float(cb.demand_qty), cb.preferential_threshold_lot)
                else:                                 # cliff を持たない市場
                    rate[m] = cb.tariff_rate
                    lower[m] = 0.0
                    upper[m] = float(cb.demand_qty)

            # 単位マージン（税率固定済みの一時 CostBlock 経由・既存 unit_pnl() を再利用）
            margins: Dict[str, float] = {}
            for m in MARKETS:
                fixed_cb = replace(blocks[m], tariff_rate=rate[m],
                                   tariff_rate_preferential=None,
                                   preferential_threshold_lot=None)
                margins[m] = unit_pnl(fixed_cb, sc, transfer_price_usd)["margin"]

            # 手順4(a): 下界を先に確保する
            floor_total = sum(lower.values())
            if floor_total > cap + 1e-9:
                if _return_all_cases:
                    all_cases.append({
                        "active_cliffs": tuple(m for m in MARKETS if m in in_s),
                        "profit": None, "feasible": False,
                    })
                continue    # このケースは実行不可能

            q = dict(lower)
            remaining = cap - floor_total

            # 手順4(b): 残余容量を単位マージン降順に、上界まで詰める
            order = sorted(MARKETS, key=lambda m: -margins[m])
            for m in order:
                if margins[m] <= 0:
                    continue
                headroom = upper[m] - q[m]
                if headroom <= 0:
                    continue
                add = min(headroom, remaining)
                q[m] += add
                remaining -= add
                if remaining <= 1e-9:
                    break

            # 手順4(c): 利益を計算する
            profit = sum(q[m] * margins[m] for m in MARKETS)
            cases_feasible += 1

            active_cliffs = tuple(m for m in MARKETS if m in in_s)
            if _return_all_cases:
                all_cases.append({
                    "active_cliffs": active_cliffs, "profit": profit, "feasible": True,
                })

            if best_case is None or profit > best_case["profit"]:
                best_case = {"profit": profit, "q": dict(q), "active_cliffs": active_cliffs}

    # 手順5: 実行可能なケースの最大値を返す
    if best_case is None:
        # 全ケースが実行不可能（閾値の合計が能力を超える等）——全市場0配分で返す
        best_case = {"profit": 0.0, "q": {m: 0.0 for m in MARKETS}, "active_cliffs": ()}

    q_best = best_case["q"]
    x = {m: (q_best[m] / cap if cap else 0.0) for m in MARKETS}
    idle = cap - sum(q_best.values())

    result = {
        "profit": best_case["profit"],
        "x": x,
        "q": q_best,
        "active_cliffs": list(best_case["active_cliffs"]),
        "cases_evaluated": cases_evaluated,
        "cases_feasible": cases_feasible,
        "idle": idle,
    }
    if _return_all_cases:
        result["_all_cases"] = all_cases
    return result


def compare_with_grid(
    mo: dict,
    surface: List[dict],
    *,
    abs_tol: float = 1.0,
    true_optimum: Optional[dict] = None,
) -> dict:
    """メリットオーダー連続解と格子最適の乖離を定量化し、
    格子解像度で説明できる分と、構造由来の残差とに分解する（設計書 §3.5 rev.2）。

    判定式:
        expected_gap = grid_idle × lambda
        structural_residual = gap_amt − expected_gap
        attributable_to_grid_resolution =
            absorbable and abs(structural_residual) <= abs_tol

    理屈: 格子最適点では `grid_idle` だけ能力が遊んでいる。その能力を限界市場
    （マージン λ）に回せば `grid_idle × λ` だけ利益が増える——メリットオーダー
    連続解はまさにそれをしている。したがって限界市場が `grid_idle` 以上の
    未充足需要を格子最適点で残している（`absorbable`）限り、両者の差は
    `grid_idle × λ` に厳密に一致するはずである。一致しない残差
    （`structural_residual`）は、格子解像度では説明できない構造由来の乖離
    （非凹性・関税階段等）を意味する。

    旧実装（x_mo の各成分を δ に丸めた組合せと比較する方式）は、単体制約
    Σx=1 による「押し出し」（US/EU を需要天井超へ丸めると JP が押し出される
    効果）を成分ごとの独立な丸めでは表現できず、格子最適点が候補に入らない
    ケースがあった（soysauce で相対誤差 0.146%、恣意的な閾値でしか救えなかった）。
    本方式はその欠陥を解消し、閾値を数値誤差の許容（既定 1.0 JPY）だけにする。

    Phase 6-1（requests/Phase6-1_RequestLetter_to_CodeKun.md V2）: `true_optimum`
    （`true_continuous_optimum()` の戻り値）を渡すと、真の連続最適 `P_opt` を
    基準にした4フィールドを追加で返す。既定 `None`（渡さない）のときは
    Phase 5 までの返却と完全に同一——4フィールドは追加されるが値は全て `None`。

    Args:
        mo: build_allocation_merit_order() の戻り値
        surface: scan_surface() の戻り値（mo と同じ blocks/sc/cap_wk で評価したもの）
        abs_tol: structural_residual をゼロ（=格子解像度で完全に説明できる）と
            みなす絶対誤差の許容幅（JPY、既定 1.0＝浮動小数の数値誤差のみ許容）
        true_optimum: true_continuous_optimum() の戻り値（既定 None）。渡すと
            true_optimum/structural_optimality_gap/grid_resolution_error/
            residual_coverage の4キーに実値が入る

    Returns:
        {
            "merit_order_profit": 135529822.5,
            "grid_best_profit": 132133072.5,
            "grid_best_x": (0.10, 0.45, 0.45),
            "gap_amt": 3396750.0,
            "gap_pct": 0.0257,
            "grid_idle": 4529.0,
            "lambda": 750.0,
            "marginal_market": "JP",
            "marginal_unmet_at_grid_best": 21830.0,
            "absorbable": True,                       # 限界市場が idle を吸収できるか
            "expected_gap_from_grid_resolution": 3396750.0,
            "structural_residual": 0.0,                # ★ Phase 5 で使う主要な出力
            "structural_residual_pct": 0.0,
            "attributable_to_grid_resolution": True,
            "true_optimum": None,                      # ★ Phase 6-1 で追加（P_opt）
            "structural_optimality_gap": None,          # P_opt − merit_order_profit
            "grid_resolution_error": None,              # P_opt − grid_best_profit
            "residual_coverage": None,                  # |structural_residual| / structural_optimality_gap
        }
    """
    best, plateau = best_point(surface)
    grid_pt = plateau[0]
    grid_x, grid_idle = grid_pt["x"], grid_pt["idle"]

    gap_amt = mo["profit"] - best
    gap_pct = (gap_amt / best) if best else float("nan")

    lam = mo["lambda"]
    marginal = mo["marginal_market"]

    # 限界市場が格子最適点で残している未充足需要（そこへ idle 分を回せるか）
    marginal_unmet = 0.0 if marginal is None else grid_pt["unmet"][marginal]

    absorbable = (marginal is not None) and (marginal_unmet >= grid_idle)

    expected_gap = grid_idle * lam
    structural_residual = gap_amt - expected_gap
    structural_residual_pct = (structural_residual / best) if best else float("nan")

    attributable = absorbable and (abs(structural_residual) <= abs_tol)

    # Phase 6-1: 真の連続最適が渡されたときだけ実値を入れる（既定 None）
    true_opt_profit: Optional[float] = None
    structural_optimality_gap: Optional[float] = None
    grid_resolution_error: Optional[float] = None
    residual_coverage: Optional[float] = None
    if true_optimum is not None:
        true_opt_profit = true_optimum["profit"]
        structural_optimality_gap = true_opt_profit - mo["profit"]
        grid_resolution_error = true_opt_profit - best
        if structural_optimality_gap == 0:
            residual_coverage = None    # ゼロ除算ではなく「定義できない」を意味する None
        else:
            residual_coverage = abs(structural_residual) / structural_optimality_gap

    return {
        "merit_order_profit": mo["profit"],
        "grid_best_profit": best,
        "grid_best_x": grid_x,
        "gap_amt": gap_amt,
        "gap_pct": gap_pct,
        "grid_idle": grid_idle,
        "lambda": lam,
        "marginal_market": marginal,
        "marginal_unmet_at_grid_best": marginal_unmet,
        "absorbable": absorbable,
        "expected_gap_from_grid_resolution": expected_gap,
        "structural_residual": structural_residual,
        "structural_residual_pct": structural_residual_pct,
        "attributable_to_grid_resolution": attributable,
        "true_optimum": true_opt_profit,
        "structural_optimality_gap": structural_optimality_gap,
        "grid_resolution_error": grid_resolution_error,
        "residual_coverage": residual_coverage,
    }
