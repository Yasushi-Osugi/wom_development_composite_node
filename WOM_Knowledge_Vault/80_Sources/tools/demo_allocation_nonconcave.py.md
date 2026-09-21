---
tags: [wom, code]
---
# tools/demo_allocation_nonconcave.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tools/demo_allocation_nonconcave.py) · [原文テキスト](../../90_Raw/tools/demo_allocation_nonconcave.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## モジュール説明（docstring原文）

```text
tools/demo_allocation_nonconcave.py — Phase 5/6-1（数量依存関税・cliff型 + 真の連続最適）動作確認デモ
========================================================================================================
`wom/allocation/` の Phase 5 拡張（cliff 型の数量依存関税・`structural_residual`）と
Phase 6-1 拡張（`true_continuous_optimum()` による `structural_optimality_gap` の実計算）が
正しく動作していることを、実データで示す確認用スクリプト。GUI/matplotlib 画像は
一切出力しない（純粋なバックエンドロジック拡張のため）。

使い方（リポジトリ直下）:
  python -m tools.demo_allocation_nonconcave

出力内容:
  1. s1_base / cap_wk=800 — Phase 4 の回帰値が1円も変わらないことの確認（線形ケース）
  2. s9_fta_cliff / cap_wk=500 — 非凹性の検証（本Phaseの核心）
     ①近視眼的メリットオーダー（貪欲法）が特恵閾値を逃す様子
     ②δ=0.05 格子最適が特恵を掴む様子
     ③structural_residual による乖離の帰属判定（負＝非凹性の証拠）
     ④真の連続最適（実計算）との比較：structural_optimality_gap / grid_resolution_error

設計正典: requests/Phase5_DesignMD_NonConcaveTariff.md、
         requests/Phase6-1_RequestLetter_to_CodeKun.md（設計書 Phase6_DesignMD_NMarketHierarchy.md §3）
実装記録: docs/development/wom-v1r4m0_phase5_nonconcave.md（CLAUDE.md 該当節）
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_section` | 39 | docstringなし（下のコード参照） |
| FunctionDef | `_print_true_optimum_block` | 45 | 真の連続最適との比較ブロックを表示する（線形・非凹の両ケース共通）。 |
| FunctionDef | `main` | 66 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/requests/Phase5_DesignMD_NonConcaveTariff.md|requests/Phase5_DesignMD_NonConcaveTariff.md]]
- [[80_Sources/requests/Phase6-1_RequestLetter_to_CodeKun.md|requests/Phase6-1_RequestLetter_to_CodeKun.md]]
- [[80_Sources/docs/development/wom-v1r4m0_phase5_nonconcave.md|docs/development/wom-v1r4m0_phase5_nonconcave.md]]
- [[80_Sources/wom/allocation/cost_block.py|wom/allocation/cost_block.py]]
- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]
- [[80_Sources/wom/allocation/grid.py|wom/allocation/grid.py]]
- [[80_Sources/wom/allocation/merit_order.py|wom/allocation/merit_order.py]]
- [[80_Sources/tools/run_allocation_map.py|tools/run_allocation_map.py]]

## 全文（コメント・原文を省略せず収録）

````python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/demo_allocation_nonconcave.py — Phase 5/6-1（数量依存関税・cliff型 + 真の連続最適）動作確認デモ
========================================================================================================
`wom/allocation/` の Phase 5 拡張（cliff 型の数量依存関税・`structural_residual`）と
Phase 6-1 拡張（`true_continuous_optimum()` による `structural_optimality_gap` の実計算）が
正しく動作していることを、実データで示す確認用スクリプト。GUI/matplotlib 画像は
一切出力しない（純粋なバックエンドロジック拡張のため）。

使い方（リポジトリ直下）:
  python -m tools.demo_allocation_nonconcave

出力内容:
  1. s1_base / cap_wk=800 — Phase 4 の回帰値が1円も変わらないことの確認（線形ケース）
  2. s9_fta_cliff / cap_wk=500 — 非凹性の検証（本Phaseの核心）
     ①近視眼的メリットオーダー（貪欲法）が特恵閾値を逃す様子
     ②δ=0.05 格子最適が特恵を掴む様子
     ③structural_residual による乖離の帰属判定（負＝非凹性の証拠）
     ④真の連続最適（実計算）との比較：structural_optimality_gap / grid_resolution_error

設計正典: requests/Phase5_DesignMD_NonConcaveTariff.md、
         requests/Phase6-1_RequestLetter_to_CodeKun.md（設計書 Phase6_DesignMD_NMarketHierarchy.md §3）
実装記録: docs/development/wom-v1r4m0_phase5_nonconcave.md（CLAUDE.md 該当節）
"""
from __future__ import annotations

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.transmission import Scenario
from wom.allocation.grid import scan_surface, best_point
from wom.allocation.merit_order import (
    build_allocation_merit_order, compare_with_grid, true_continuous_optimum,
)
from tools.run_allocation_map import load_scenarios, _blocks_for

MODEL_DIR = "data/sample/soysauce-jpy-2027-alloc"


def _section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _print_true_optimum_block(mo: dict, cmp_result: dict, true_opt: dict) -> None:
    """真の連続最適との比較ブロックを表示する（線形・非凹の両ケース共通）。"""
    print("\n  --- 真の連続最適との比較（実計算） ---")
    print(f"  真の連続最適 profit: {true_opt['profit']:,.1f}")
    alloc = "  ".join(f"{m}={q:,.0f}" for m, q in true_opt["q"].items())
    print(f"    配分: {alloc}")
    print(f"    発動している特恵: {true_opt['active_cliffs']}")
    print(f"    評価したケース数: {true_opt['cases_evaluated']} "
          f"（実行可能: {true_opt['cases_feasible']}）")

    gap = cmp_result["structural_optimality_gap"]
    err = cmp_result["grid_resolution_error"]
    cov = cmp_result["residual_coverage"]
    cov_str = "—" if cov is None else f"{cov * 100:.1f}%"

    print(f"  構造由来の取りこぼし (structural_optimality_gap): {gap:,.1f}")
    print(f"  格子解像度の誤差 (grid_resolution_error):            {err:,.1f}")
    print(f"  |structural_residual| / 取りこぼし = {cov_str}"
          "  （residual は下界として機能）")


def main() -> None:
    base_blocks, tp = derive_cost_blocks(MODEL_DIR)
    scens = {s["id"]: s for s in load_scenarios(MODEL_DIR)}

    # -----------------------------------------------------------------
    _section("1. s1_base / cap_wk=800 — Phase 4 の回帰値が1円も変わらないこと（線形ケース）")
    # -----------------------------------------------------------------
    sc1 = Scenario(fx_usd=150.0, material_usd=6.0)
    mo1 = build_allocation_merit_order(base_blocks, sc1, 800.0, transfer_price_usd=tp)
    surf1 = scan_surface(base_blocks, tp, sc1, 800.0)
    true_opt1 = true_continuous_optimum(base_blocks, sc1, 800.0, transfer_price_usd=tp)
    cmp1 = compare_with_grid(mo1, surf1, true_optimum=true_opt1)

    print(f"  lambda           : {mo1['lambda']}")
    print(f"  x                : {mo1['x']}")
    print(f"  profit (merit)   : {mo1['profit']:,.1f}")
    print(f"  profit (grid best): {cmp1['grid_best_profit']:,.1f}")
    print(f"  structural_residual: {cmp1['structural_residual']:,.4f}  (期待値 0.0 = 完全一致)")
    print(f"  preferential     : {mo1['preferential']}  (cliff未設定なので None)")

    _print_true_optimum_block(mo1, cmp1, true_opt1)

    # -----------------------------------------------------------------
    _section("2. s9_fta_cliff / cap_wk=500 — 非凹性の検証（本Phaseの核心）")
    # -----------------------------------------------------------------
    s9 = scens["s9_fta_cliff"]
    print(f"  US特恵税率       : {s9['tariff']['US']} -> {s9['tariff_preferential']['US']}")
    print(f"  発動閾値         : {s9['preferential_threshold']['US']:,.0f} lot")

    blocks9 = _blocks_for(base_blocks, s9["tariff"], s9["tariff_preferential"],
                           s9["preferential_threshold"])
    sc9 = Scenario(fx_usd=s9["fx_usd"], material_usd=s9["material_usd"])
    cap_wk9 = 500.0

    mo9 = build_allocation_merit_order(blocks9, sc9, cap_wk9, transfer_price_usd=tp)
    print("\n  --- ①近視眼的メリットオーダー（貪欲法） ---")
    for b in mo9["blocks"]:
        print(f"    {b['market']}: allocated={b['allocated']:>10,.0f}"
              f"  margin(ranking)={b['margin']:>8,.1f}  served={b['served']}")
    print(f"  lambda（限界市場の単価）: {mo9['lambda']}  marginal_market={mo9['marginal_market']}")
    print(f"  profit: {mo9['profit']:,.1f}")
    print(f"  preferential (US): {mo9['preferential']['US']}")
    print("  → US は閾値 25,000 に届かず特恵が発動しない（triggered=False）"
          " = 貪欲法は優遇を丸ごと逃す")

    surf9 = scan_surface(blocks9, tp, sc9, cap_wk9)
    best9, plateau9 = best_point(surf9)
    print("\n  --- δ=0.05 格子最適（231点全数評価） ---")
    print(f"  x (JP,US,EU): {plateau9[0]['x']}")
    print(f"  profit: {best9:,.1f}")
    print(f"  idle capacity: {plateau9[0]['idle']}")
    print("  → 格子は US=0.65 まで踏み込んで特恵を掴む（貪欲法にはできない先読み）")

    true_opt9 = true_continuous_optimum(blocks9, sc9, cap_wk9, transfer_price_usd=tp)
    cmp9 = compare_with_grid(mo9, surf9, true_optimum=true_opt9)
    print("\n  --- 乖離の帰属判定 ---")
    print(f"  gap_amt (merit - grid_best): {cmp9['gap_amt']:,.1f}")
    print(f"  expected_gap (grid_idle x lambda): {cmp9['expected_gap_from_grid_resolution']:,.1f}")
    print(f"  structural_residual: {cmp9['structural_residual']:,.1f}  (負 = 非凹性の証拠)")
    print(f"  attributable_to_grid_resolution: {cmp9['attributable_to_grid_resolution']}"
          "  (False = 格子誤差では説明できない)")

    _print_true_optimum_block(mo9, cmp9, true_opt9)

    print("\n完了。Phase 5/6-1（非凹関税・structural_residual・structural_optimality_gap）"
          "の実際の挙動です。")


if __name__ == "__main__":
    main()

````
