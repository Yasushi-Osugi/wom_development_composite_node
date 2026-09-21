---
tags: [wom, code]
---
# wom/allocation/grid.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/allocation/grid.py) · [原文テキスト](../../../90_Raw/wom/allocation/grid.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/02_Demand_Allocation|Optimization on Demand Allocation]]

## モジュール説明（docstring原文）

```text
wom/allocation/grid.py — Simplex 格子生成・N市場スキャン（Step 6〜11 の粗利版）
==============================================================================
配分比率単体 (x_1, ..., x_N) を δ=0.05 刻みで全数評価し、各点の Demand Anchored
損益と FX エクスポージャーを返す。**最適化は行わない**（Request Letter §1.1 /
§6.1）――面（利益地形）を出すためのスキャナである。

正典：docs/design/ask_global_allocation_spec.md §6 / §5 Step 7〜11
参照：tools/proto_terrain2.py（evaluate と一致すること。soysauce=3市場のみ）

【利益の定義】本 Rev は **粗利（revenue − cost）** を profit とする。
  受け入れ基準 #11/#14/#16（付録 A の回帰値）が粗利ベースで与えられているため。
  仕様書 Step 9-10 の運転資本費用（wc_cost・金利 i）＋SGA を引いた営業利益は
  **設計逸脱として未実装**（grid には未反映）。扱いは Claude 君に確認（Request Letter §8）。

【Phase 6-2】市場数を3に固定していた2箇所（MARKETS 定数・simplex_grid() の
二重ループ）を外し、N市場に一般化した（requests/Phase6-2_RequestLetter_to_CodeKun.md）。
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `markets_of` | 40 | CostBlock の辞書から市場の並びを決める。 |
| FunctionDef | `grid_point_count` | 59 | 格子点数 C(n + n_dim − 1, n_dim − 1) を、点を生成せずに返す（C9）。 |
| FunctionDef | `simplex_grid` | 65 | n_dim 次元の単体格子。点数は C(n + n_dim − 1, n_dim − 1)（n = 1/delta）。 |
| FunctionDef | `evaluate_point` | 99 | 1 配分点の Demand Anchored 損益（Step 7〜11・粗利）。 |
| FunctionDef | `scan_surface` | 140 | 全格子点を評価して結果リストを返す（グリッド順を保持）。 |
| FunctionDef | `demand_ceilings` | 161 | 尾根線（需要天井）の位置 x[m] = D[m] / Cap。合計>1 なら配給が必要。 |
| FunctionDef | `best_point` | 168 | (最大利益, 台地[最大値の plateau_tol 以内の点群・グリッド順]) を返す。 |
| FunctionDef | `chosen_point` | 186 | 『採用する1点』を明示的な規則(格子の真の最良点=profitのargmax)で選ぶ。 |
| FunctionDef | `rec` | 86 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/docs/design/ask_global_allocation_spec.md|docs/design/ask_global_allocation_spec.md]]
- [[80_Sources/tools/proto_terrain2.py|tools/proto_terrain2.py]]
- [[80_Sources/requests/Phase6-2_RequestLetter_to_CodeKun.md|requests/Phase6-2_RequestLetter_to_CodeKun.md]]
- [[80_Sources/requests/Phase5_DesignMD_NonConcaveTariff.md|requests/Phase5_DesignMD_NonConcaveTariff.md]]
- [[80_Sources/tests/test_allocation_grid.py|tests/test_allocation_grid.py]]
- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
wom/allocation/grid.py — Simplex 格子生成・N市場スキャン（Step 6〜11 の粗利版）
==============================================================================
配分比率単体 (x_1, ..., x_N) を δ=0.05 刻みで全数評価し、各点の Demand Anchored
損益と FX エクスポージャーを返す。**最適化は行わない**（Request Letter §1.1 /
§6.1）――面（利益地形）を出すためのスキャナである。

正典：docs/design/ask_global_allocation_spec.md §6 / §5 Step 7〜11
参照：tools/proto_terrain2.py（evaluate と一致すること。soysauce=3市場のみ）

【利益の定義】本 Rev は **粗利（revenue − cost）** を profit とする。
  受け入れ基準 #11/#14/#16（付録 A の回帰値）が粗利ベースで与えられているため。
  仕様書 Step 9-10 の運転資本費用（wc_cost・金利 i）＋SGA を引いた営業利益は
  **設計逸脱として未実装**（grid には未反映）。扱いは Claude 君に確認（Request Letter §8）。

【Phase 6-2】市場数を3に固定していた2箇所（MARKETS 定数・simplex_grid() の
二重ループ）を外し、N市場に一般化した（requests/Phase6-2_RequestLetter_to_CodeKun.md）。
"""
from __future__ import annotations

from math import comb
from typing import Dict, List, Sequence, Tuple

from wom.allocation.transmission import CostBlock, Scenario, unit_pnl_at_quantity

# 既定の市場（soysauce-jpy-2027-alloc の並び）。blocks が無い呼び出し元のための既定値。
DEFAULT_MARKETS: Tuple[str, ...] = ("JP", "US", "EU")

# 後方互換のため残す（既存の import・テストがそのまま動く）。新規コードでは
# markets_of(blocks) を使うこと——市場の並びは blocks（derive_cost_blocks() の
# 戻り値）から決まり、この定数は「blocks が無い場面の既定値」に過ぎない。
MARKETS: Tuple[str, ...] = DEFAULT_MARKETS

WEEKS = 104

MAX_GRID_POINTS = 100_000   # N=6（53,130点）は通り、N=7（230,230点）は止まる


def markets_of(blocks: Dict[str, CostBlock]) -> Tuple[str, ...]:
    """CostBlock の辞書から市場の並びを決める。

    順序は決定的でなければならない（格子点の並びが変わると回帰値が壊れる）。
    dict のキー順＝挿入順（Python 3.7+ の言語仕様）をそのまま採用する。
    `derive_cost_blocks()` は ga_market_aggregation.csv の行順をそのまま
    dict の挿入順として保存しているため、CSV の記載順と一致する
    （Phase6-2_RequestLetter_to_CodeKun.md V1.2 で実測確認済み）。

    **`sorted()` にしない**（アルファベット順は既存の全回帰値を壊す）。
    **`set` を経由しない**（順序が保証されない）。

    単位マージンが同値のときの tie-break（market_ranking() 等の並び順）は
    この関数が返す並び＝CSV の記載順に従う（仕様として妥当。CSV の並びは
    意図して書かれたもの）。
    """
    return tuple(blocks.keys())


def grid_point_count(delta: float = 0.05, n_dim: int = 3) -> int:
    """格子点数 C(n + n_dim − 1, n_dim − 1) を、点を生成せずに返す（C9）。"""
    n = int(round(1.0 / delta))
    return comb(n + n_dim - 1, n_dim - 1)


def simplex_grid(delta: float = 0.05, n_dim: int = 3) -> List[Tuple[float, ...]]:
    """n_dim 次元の単体格子。点数は C(n + n_dim − 1, n_dim − 1)（n = 1/delta）。

    第0成分が「残余」であることの意味：markets_of(blocks) の**先頭の市場が
    残余**になる（x[0] = 1 − sum(x[1:])）。soysauce では先頭が JP なので、
    現行の地図座標（X=x_US, Y=x_EU, x_JP=残余）と一致する。

    後方互換の絶対条件（C8）: n_dim=3 のとき、返る231点の**値と順序**が
    Phase 6-2 以前の実装と1点も違わないこと。地形図の描画順・Phase 4/5 の
    全回帰値が依存する。

    実装は再帰で書く（itertools.combinations_with_replacement は不可）。
    検証の結果、後者は点の集合は同じだが**順序が異なる**ため C8 を満たさない
    （Phase6-2_RequestLetter_to_CodeKun.md V2.2）。
    """
    if n_dim < 2:
        raise ValueError(f"n_dim must be >= 2, got {n_dim}")
    n = int(round(1.0 / delta))
    pts: List[Tuple[float, ...]] = []
    idx = [0] * (n_dim - 1)

    def rec(k: int, remaining: int) -> None:
        if k == n_dim - 1:
            # 第0成分は残余（現行実装で x_JP が残余であるのと同じ）
            pts.append(tuple([remaining / n] + [v / n for v in idx]))
            return
        for v in range(remaining + 1):
            idx[k] = v
            rec(k + 1, remaining - v)

    rec(0, n)
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

    Phase 6-2: `x` の並びは markets_of(blocks) の順であることが前提。
    長さが一致しない場合は `zip` が静かに切り捨てて利益が過小になるため、
    先頭で明示的に検査する。
    """
    markets = markets_of(blocks)
    if len(x) != len(markets):
        raise ValueError(
            f"x has {len(x)} components but blocks has {len(markets)} markets "
            f"{markets}. The order of x must match markets_of(blocks)."
        )
    cap = cap_wk * weeks
    q = {m: min(xi * cap, blocks[m].demand_qty) for m, xi in zip(markets, x)}   # ← 数量を先に
    ue = {m: unit_pnl_at_quantity(blocks[m], sc, q[m], transfer_price_usd) for m in markets}
    rev = sum(q[m] * ue[m]["rev"] for m in markets)
    cost = sum(q[m] * ue[m]["cost"] for m in markets)
    fcost = sum(q[m] * ue[m]["fcost"] for m in markets)
    frev = sum(q[m] * ue[m]["frev"] for m in markets)
    used = sum(q.values())
    FCR = fcost / cost if cost else 0.0
    FRR = frev / rev if rev else 0.0
    return {
        "x": tuple(round(xi, 10) for xi in x),
        "profit": rev - cost, "rev": rev, "cost": cost,
        "q": q, "used": used, "idle": cap - used,
        "unmet": {m: blocks[m].demand_qty - q[m] for m in markets},
        "FCR": FCR, "FRR": FRR,
        "FXB": (FCR / FRR if FRR > 0 else float("inf")),
    }


def scan_surface(blocks: Dict[str, CostBlock], transfer_price_usd: float,
                 sc: Scenario, cap_wk: float, weeks: int = WEEKS,
                 delta: float = 0.05, max_points: int = MAX_GRID_POINTS) -> List[dict]:
    """全格子点を評価して結果リストを返す（グリッド順を保持）。

    C9: 格子点数が `max_points` を超える場合は、**`simplex_grid()` を呼ぶ前に**
    ValueError を投げる（「生成してから len を見る」実装は N=21 のようなケースで
    1,378億点を生成しようとして帰ってこない）。既定では止める。
    """
    markets = markets_of(blocks)
    n_points = grid_point_count(delta, len(markets))
    if n_points > max_points:
        raise ValueError(
            f"simplex grid would have {n_points:,} points for N={len(markets)} "
            f"at delta={delta} (limit {max_points:,}). "
            f"Use hierarchical_simplex() instead (see Phase 6-3)."
        )
    return [evaluate_point(x, blocks, transfer_price_usd, sc, cap_wk, weeks)
            for x in simplex_grid(delta, len(markets))]


def demand_ceilings(blocks: Dict[str, CostBlock], cap_wk: float,
                    weeks: int = WEEKS) -> Dict[str, float]:
    """尾根線（需要天井）の位置 x[m] = D[m] / Cap。合計>1 なら配給が必要。"""
    cap = cap_wk * weeks
    return {m: blocks[m].demand_qty / cap for m in markets_of(blocks)}


def best_point(surface: List[dict], plateau_tol: float = 0.001) -> Tuple[float, List[dict]]:
    """(最大利益, 台地[最大値の plateau_tol 以内の点群・グリッド順]) を返す。

    台地サイズ = len(plateau)。台地が 1 なら意思決定が一意。市場数に依存しない
    ので Phase 6-2 の N市場化でも無変更。

    **シグネチャ・返り値は変えない**（Phase 6-5・E1）。台地の長さは意思決定の
    自由度の報告として正しく、`plateau` の長さを assert している既存テストが
    ある（`tests/test_allocation_grid.py`）。「採用する1点」を選ぶ用途には
    `chosen_point()` を使うこと——`plateau[0]`（グリッド順の先頭）は「格子順で
    たまたま最初に許容誤差内に入った点」であって、真の最良点（profit の
    argmax）とは限らない（Phase 6-5 Request Letter §E1）。
    """
    best = max(r["profit"] for r in surface)
    plateau = [r for r in surface if r["profit"] >= best - abs(best) * plateau_tol]
    return best, plateau


def chosen_point(surface: List[dict]) -> dict:
    """『採用する1点』を明示的な規則(格子の真の最良点=profitのargmax)で選ぶ。

    `best_point()` の `plateau[0]`（格子順の先頭）に替わる、点選択の一本化先
    （Phase 6-5・E1）。`plateau_tol` という相対許容誤差に依存しないため、
    シナリオ間で採用点が意味なく動くことも無い（`plateau_tol` はシナリオ間で
    台地サイズを比較できない問題を持つが、`chosen_point()` はその影響を受けない
    ——台地の報告用途と、実際に1点を選ぶ用途を分離したのが本関数の狙い）。

    同点（浮動小数の完全一致）が複数あるときは、格子順（`simplex_grid()` の
    生成順）で最初のものを採用する——`max()` の仕様どおり決定的だが、その順序
    自体に意味はない。
    """
    return max(surface, key=lambda r: r["profit"])

````
