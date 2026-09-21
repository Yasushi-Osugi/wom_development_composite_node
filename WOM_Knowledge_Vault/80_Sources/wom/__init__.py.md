---
tags: [wom, code]
---
# wom/__init__.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/__init__.py) · [原文テキスト](../../90_Raw/wom/__init__.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## モジュール説明（docstring原文）

```text
WOM – Weekly Operation Model
Global Supply Chain Planning & Simulation Tool
Version: v1r0m0
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|

## 関連する知識源

- [[80_Sources/wom/config.py|wom/config.py]]
- [[80_Sources/wom/engine/simulator.py|wom/engine/simulator.py]]

## 全文（コメント・原文を省略せず収録）

````python
"""
WOM – Weekly Operation Model
Global Supply Chain Planning & Simulation Tool
Version: v1r0m0
"""

__version__ = "1.0.0"
__author__ = "WOM Team"

from wom.config import WOMConfig
from wom.engine.simulator import WOMSimulator

__all__ = ["WOMConfig", "WOMSimulator"]

````
