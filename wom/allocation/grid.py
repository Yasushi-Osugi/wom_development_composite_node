# -*- coding: utf-8 -*-
"""
wom/allocation/grid.py — Simplex 格子生成・231 点スキャン（Step 6〜11 の粗利版）
==============================================================================
配分比率単体 (x_JP, x_US, x_EU) を δ=0.05 刻みで全数評価（231 点）し、各点の
Demand Anchored 損益と FX エクスポージャーを返す。**最適化は行わない**（Request
Letter §1.1 / §6.1）――面（利益地形）を出すためのスキャナである。

正典：docs/design/ask_global_allocation_spec.md §6 / §5 Step 7〜11
参照：tools/proto_terrain2.py（evaluate と一致すること）

【利益の定義】本 Rev は **粗利（revenue − cost）** を profit とする。
  受け入れ基準 #11/#14/#16（付録 A の回帰値）が粗利ベースで与えられているため。
  仕様書 Step 9-10 の運転資本費用（wc_cost・金利 i）＋SGA を引いた営業利益は
  **設計逸脱として未実装**（grid には未反映）。扱いは Claude 君に確認（Request Letter §8）。
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from wom.allocation.transmission import CostBlock, Scenario, unit_pnl_at_quantity

# x の並び（proto_terrain2.py と同一。地図座標は X=x_US, Y=x_EU, x_JP=残余）
MARKETS: Tuple[str, str, str] = ("JP", "US", "EU")

WEEKS = 104


def simplex_grid(delta: float = 0.05) -> List[Tuple[float, float, float]]:
    """(x_JP, x_US, x_EU) の格子。i+j<=n を満たす整数格子で 231 点（δ=0.05）。"""
    n = int(round(1.0 / delta))
    pts: List[Tuple[float, float, float]] = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            pts.append(((n - i - j) / n, i / n, j / n))
    return pts


def evaluate_point(x: Sequence[float], blocks: Dict[str, CostBlock],
                   transfer_price_usd: float, sc: Scenario,
                   cap_wk: float, weeks: int = WEEKS) -> dict:
    """1 配分点の Demand Anchored 損益（Step 7〜11・粗利）。

    Phase 5（数量依存の関税・cliff型）: 単価は数量 q が決まってから解決する
    （unit_pnl_at_quantity()）。「A系統4モジュール無変更」の唯一の例外
    （requests/Phase5_DesignMD_NonConcaveTariff.md §3.4）。cliff未設定の
    CostBlock では unit_pnl_at_quantity() は unit_pnl() と完全に一致するため、
    既存の231点評価・Phase 4 の回帰値は1円も変わらない。
    """
    cap = cap_wk * weeks
    q = {m: min(xi * cap, blocks[m].demand_qty) for m, xi in zip(MARKETS, x)}   # ← 数量を先に
    ue = {m: unit_pnl_at_quantity(blocks[m], sc, q[m], transfer_price_usd) for m in MARKETS}
    rev = sum(q[m] * ue[m]["rev"] for m in MARKETS)
    cost = sum(q[m] * ue[m]["cost"] for m in MARKETS)
    fcost = sum(q[m] * ue[m]["fcost"] for m in MARKETS)
    frev = sum(q[m] * ue[m]["frev"] for m in MARKETS)
    used = sum(q.values())
    FCR = fcost / cost if cost else 0.0
    FRR = frev / rev if rev else 0.0
    return {
        "x": tuple(round(xi, 10) for xi in x),
        "profit": rev - cost, "rev": rev, "cost": cost,
        "q": q, "used": used, "idle": cap - used,
        "unmet": {m: blocks[m].demand_qty - q[m] for m in MARKETS},
        "FCR": FCR, "FRR": FRR,
        "FXB": (FCR / FRR if FRR > 0 else float("inf")),
    }


def scan_surface(blocks: Dict[str, CostBlock], transfer_price_usd: float,
                 sc: Scenario, cap_wk: float, weeks: int = WEEKS,
                 delta: float = 0.05) -> List[dict]:
    """全格子点を評価して結果リストを返す（グリッド順を保持）。"""
    return [evaluate_point(x, blocks, transfer_price_usd, sc, cap_wk, weeks)
            for x in simplex_grid(delta)]


def demand_ceilings(blocks: Dict[str, CostBlock], cap_wk: float,
                    weeks: int = WEEKS) -> Dict[str, float]:
    """尾根線（需要天井）の位置 x[m] = D[m] / Cap。合計>1 なら配給が必要。"""
    cap = cap_wk * weeks
    return {m: blocks[m].demand_qty / cap for m in MARKETS}


def best_point(surface: List[dict], plateau_tol: float = 0.001) -> Tuple[float, List[dict]]:
    """(最大利益, 台地[最大値の plateau_tol 以内の点群・グリッド順]) を返す。

    台地サイズ = len(plateau)。台地が 1 なら意思決定が一意。
    """
    best = max(r["profit"] for r in surface)
    plateau = [r for r in surface if r["profit"] >= best - abs(best) * plateau_tol]
    return best, plateau
