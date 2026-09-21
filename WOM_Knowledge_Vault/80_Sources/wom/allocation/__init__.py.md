---
tags: [wom, code]
---
# wom/allocation/__init__.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/allocation/__init__.py) · [原文テキスト](../../../90_Raw/wom/allocation/__init__.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/02_Demand_Allocation|Optimization on Demand Allocation]]

## モジュール説明（docstring原文）

```text
wom.allocation — ask_global_allocation（生産配分地形）モジュール

Planning Engine の外側で動作する Management 層の拡張。既存の保護コア
（backward_planner / forward_planner / plan_copy / plan_node / sc_tree /
push_pull）には一切触れない。配分比率空間を全数評価して利益地形を生成する。

設計正典：docs/design/ask_global_allocation_spec.md（v0r3）
実装依頼：requests/global-allocation-request-letter.md（Rev 3）
参照実装：tools/proto_terrain2.py（伝達式の解釈はこちらを優先）
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|

## 関連する知識源

- [[80_Sources/docs/design/ask_global_allocation_spec.md|docs/design/ask_global_allocation_spec.md]]
- [[80_Sources/requests/global-allocation-request-letter.md|requests/global-allocation-request-letter.md]]
- [[80_Sources/tools/proto_terrain2.py|tools/proto_terrain2.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
wom.allocation — ask_global_allocation（生産配分地形）モジュール

Planning Engine の外側で動作する Management 層の拡張。既存の保護コア
（backward_planner / forward_planner / plan_copy / plan_node / sc_tree /
push_pull）には一切触れない。配分比率空間を全数評価して利益地形を生成する。

設計正典：docs/design/ask_global_allocation_spec.md（v0r3）
実装依頼：requests/global-allocation-request-letter.md（Rev 3）
参照実装：tools/proto_terrain2.py（伝達式の解釈はこちらを優先）
"""

````
