---
tags: [wom, code]
---
# wom/allocation/analytics.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/allocation/analytics.py) · [原文テキスト](../../../90_Raw/wom/allocation/analytics.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/02_Demand_Allocation|Optimization on Demand Allocation]]

## モジュール説明（docstring原文）

```text
wom/allocation/analytics.py — 切替点・交互作用・robust_point・制約コスト
======================================================================
231 点スキャン結果と単位経済から、経営判断に使う派生量を算出する。

正典：docs/design/ask_global_allocation_spec.md §6.3/§6.4/§6.5・§7.7/§7.8、§9.3
参照：tools/proto_terrain2.py（切替点の走査・交互作用）

含む分析:
  market_ranking     市場を単位マージン降順に並べる
  switching_points   為替を走査して優先順位が反転する点（#14: 117円/119円）
  interaction        (s4−s1)−(s2−s1)−(s3−s1)（§3.2/§A.5・交互作用は主役）
  robust_point       台地上でミニマックス（全シナリオ最低利益の最大化）（#15/§5.6b）
  constraint_cost    非経済的制約（例 x_JP>=0.20）のコスト（§5.6b）
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `market_ranking` | 29 | 市場を単位マージン降順に並べた順序。 |
| FunctionDef | `switching_points` | 42 | 為替を fx_lo→fx_hi に走査し、市場優先順位が変わる点を列挙。 |
| FunctionDef | `interaction` | 64 | 為替単独・原料単独・複合・交互作用の分解（固定配分 x での利益差）。 |
| FunctionDef | `robust_point` | 89 | 台地上のミニマックス点（全シナリオでの最低利益が最大の配分）。§5.6b/#15。 |
| FunctionDef | `constraint_cost` | 105 | 非経済的制約のコスト = 制約なし最適 − 制約下最適（§5.6b）。 |
| FunctionDef | `p` | 76 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/docs/design/ask_global_allocation_spec.md|docs/design/ask_global_allocation_spec.md]]
- [[80_Sources/tools/proto_terrain2.py|tools/proto_terrain2.py]]
- [[80_Sources/requests/Phase6-2_RequestLetter_to_CodeKun.md|requests/Phase6-2_RequestLetter_to_CodeKun.md]]
- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]
- [[80_Sources/wom/allocation/grid.py|wom/allocation/grid.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
wom/allocation/analytics.py — 切替点・交互作用・robust_point・制約コスト
======================================================================
231 点スキャン結果と単位経済から、経営判断に使う派生量を算出する。

正典：docs/design/ask_global_allocation_spec.md §6.3/§6.4/§6.5・§7.7/§7.8、§9.3
参照：tools/proto_terrain2.py（切替点の走査・交互作用）

含む分析:
  market_ranking     市場を単位マージン降順に並べる
  switching_points   為替を走査して優先順位が反転する点（#14: 117円/119円）
  interaction        (s4−s1)−(s2−s1)−(s3−s1)（§3.2/§A.5・交互作用は主役）
  robust_point       台地上でミニマックス（全シナリオ最低利益の最大化）（#15/§5.6b）
  constraint_cost    非経済的制約（例 x_JP>=0.20）のコスト（§5.6b）
"""
from __future__ import annotations

from math import inf
from typing import Callable, Dict, List, Sequence, Tuple

from wom.allocation.transmission import CostBlock, Scenario, unit_pnl
from wom.allocation.grid import markets_of, evaluate_point, scan_surface

# 交互作用の基準（円安×原油の複合ショックの分解基準）
INTERACTION_BASE = (150.0, 6.0)


def market_ranking(blocks: Dict[str, CostBlock], transfer_price_usd: float,
                   fx: float, mat: float = 6.0) -> Tuple[str, ...]:
    """市場を単位マージン降順に並べた順序。

    同値時の並びは markets_of(blocks)（＝CSV の記載順）に従う
    （Phase 6-2、requests/Phase6-2_RequestLetter_to_CodeKun.md V1.4）。
    """
    sc = Scenario(fx_usd=fx, material_usd=mat)
    markets = markets_of(blocks)
    return tuple(sorted(markets,
                        key=lambda m: -unit_pnl(blocks[m], sc, transfer_price_usd)["margin"]))


def switching_points(blocks: Dict[str, CostBlock], transfer_price_usd: float,
                     fx_lo: int = 100, fx_hi: int = 220, step: int = 1,
                     mat: float = 6.0) -> List[dict]:
    """為替を fx_lo→fx_hi に走査し、市場優先順位が変わる点を列挙。

    各要素 {"fx", "order", "margins"}。最初の点は初期順序。
    昇順走査なので "fx" は「その順序に切り替わる下限」。
    """
    markets = markets_of(blocks)
    out: List[dict] = []
    prev: Tuple[str, ...] | None = None
    for fx in range(fx_lo, fx_hi + 1, step):
        order = market_ranking(blocks, transfer_price_usd, fx, mat)
        if order != prev:
            sc = Scenario(fx_usd=fx, material_usd=mat)
            out.append({"fx": fx, "order": order,
                        "margins": {m: unit_pnl(blocks[m], sc, transfer_price_usd)["margin"]
                                    for m in markets}})
            prev = order
    return out


def interaction(x: Sequence[float], blocks: Dict[str, CostBlock],
                transfer_price_usd: float, cap_wk: float,
                fx_shock: float = 200.0, mat_shock: float = 8.0,
                base: Tuple[float, float] = INTERACTION_BASE) -> dict:
    """為替単独・原料単独・複合・交互作用の分解（固定配分 x での利益差）。

    interaction = (s4−s1) − (s2−s1) − (s3−s1)
      s1=base, s2=為替のみ, s3=原料のみ, s4=複合
    |interaction| が総効果の 5% を超えると「層分解は説明として無効」（§3.2）。
    """
    fx0, mat0 = base

    def p(fx: float, mat: float) -> float:
        return evaluate_point(x, blocks, transfer_price_usd,
                              Scenario(fx_usd=fx, material_usd=mat), cap_wk)["profit"]

    s1, s2, s3, s4 = p(fx0, mat0), p(fx_shock, mat0), p(fx0, mat_shock), p(fx_shock, mat_shock)
    fx_only, mat_only, total = s2 - s1, s3 - s1, s4 - s1
    inter = total - fx_only - mat_only
    ratio = inter / total if total else float("nan")
    return {"fx_only": fx_only, "mat_only": mat_only, "total": total,
            "interaction": inter, "ratio": ratio,
            "layer_decomposition_valid": (total == 0) or (abs(ratio) <= 0.05)}


def robust_point(plateau: List[dict], blocks: Dict[str, CostBlock],
                 transfer_price_usd: float, scenarios: Sequence[Scenario],
                 cap_wk: float) -> dict:
    """台地上のミニマックス点（全シナリオでの最低利益が最大の配分）。§5.6b/#15。"""
    best_x: Tuple[float, ...] | None = None
    best_worst = -inf
    for r in plateau:
        x = r["x"]
        worst = min(evaluate_point(x, blocks, transfer_price_usd, sc, cap_wk)["profit"]
                    for sc in scenarios)
        if worst > best_worst:
            best_worst, best_x = worst, x
    return {"robust_point": best_x, "robust_worst_profit": best_worst,
            "plateau_size": len(plateau)}


def constraint_cost(blocks: Dict[str, CostBlock], transfer_price_usd: float,
                    scenario: Scenario, cap_wk: float,
                    constraint: Callable[[Tuple[float, float, float]], bool],
                    delta: float = 0.05) -> dict:
    """非経済的制約のコスト = 制約なし最適 − 制約下最適（§5.6b）。

    constraint(x) が True の点のみを許容領域とする（例 lambda x: x[0] >= 0.20）。
    """
    surf = scan_surface(blocks, transfer_price_usd, scenario, cap_wk, delta=delta)
    unc = max(r["profit"] for r in surf)
    feasible = [r for r in surf if constraint(tuple(r["x"]))]
    con = max((r["profit"] for r in feasible), default=float("nan"))
    return {"profit_unconstrained": unc, "profit_constrained": con,
            "cost_of_constraint": unc - con,
            "feasible_points": len(feasible)}

````
