---
tags: [wom, code]
---
# wom/visualization/__init__.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/visualization/__init__.py) · [原文テキスト](../../../90_Raw/wom/visualization/__init__.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/05_Presentation|Presentation]]

## モジュール説明（docstring原文）

```text
WOM Visualization Module
========================

利益ランドスケープの多次元可視化エンジン

Submodules:
- merit_order: Merit Order曲線生成
- regime_map: Regime map分類
- pareto_front: Pareto最適性分析
- hierarchical_triangulation: 階層的三角測量
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|

## 全文（コメント・原文を省略せず収録）

````python
"""
WOM Visualization Module
========================

利益ランドスケープの多次元可視化エンジン

Submodules:
- merit_order: Merit Order曲線生成
- regime_map: Regime map分類
- pareto_front: Pareto最適性分析
- hierarchical_triangulation: 階層的三角測量
"""

__version__ = "1.0.0"
__author__ = "Ohsugi (WOM Development Team)"

from .merit_order import MeritOrderAnalyzer

__all__ = [
    "MeritOrderAnalyzer",
]

````
