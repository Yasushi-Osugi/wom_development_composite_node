---
tags: [wom, code]
---
# wom/cockpit/cockpit_app.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/cockpit/cockpit_app.py) · [原文テキスト](../../../90_Raw/wom/cockpit/cockpit_app.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/06_Management_Cockpit|Management Cockpit]]

## モジュール説明（docstring原文）

```text
wom/cockpit/cockpit_app.py — 経営コックピットの起動エントリ（Phase 8-3a）
================================================================================
`python main.py --cockpit` から呼ばれる。既存 `wom/gui/app.py`（`WOMApp`・9タブ・
機能中心）とは別のトップレベルウィンドウ——設計書 §8.2「`wom/cockpit/` 新設・
`python -m main --cockpit` で起動・既存 `app.py` は1行も変えない」の実装。

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3 §8.2
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| ClassDef | `CockpitApp` | 20 | 経営コックピットのトップレベルウィンドウ。 |
| FunctionDef | `launch` | 34 | Entry point called by main.py --cockpit. |
| FunctionDef | `__init__` | 23 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/wom/gui/app.py|wom/gui/app.py]]
- [[80_Sources/requests/Phase8_DesignMD_CockpitGUI.md|requests/Phase8_DesignMD_CockpitGUI.md]]
- [[80_Sources/requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md|requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md]]
- [[80_Sources/wom/cockpit/frame.py|wom/cockpit/frame.py]]
- [[80_Sources/wom/cockpit/s1_allocate.py|wom/cockpit/s1_allocate.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
wom/cockpit/cockpit_app.py — 経営コックピットの起動エントリ（Phase 8-3a）
================================================================================
`python main.py --cockpit` から呼ばれる。既存 `wom/gui/app.py`（`WOMApp`・9タブ・
機能中心）とは別のトップレベルウィンドウ——設計書 §8.2「`wom/cockpit/` 新設・
`python -m main --cockpit` で起動・既存 `app.py` は1行も変えない」の実装。

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3 §8.2
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md
"""
from __future__ import annotations

import tkinter as tk

from wom.cockpit.frame import CockpitFrame
from wom.cockpit.s1_allocate import BG_DARK


class CockpitApp(tk.Tk):
    """経営コックピットのトップレベルウィンドウ。"""

    def __init__(self):
        super().__init__()
        self.title("WOM 経営コックピット")
        self.configure(bg=BG_DARK)
        self.geometry("1280x820")
        self.minsize(900, 600)

        frame = CockpitFrame(self)
        frame.pack(fill="both", expand=True)


def launch() -> None:
    """Entry point called by main.py --cockpit."""
    CockpitApp().mainloop()

````
