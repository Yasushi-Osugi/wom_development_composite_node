---
tags: [wom, code]
---
# wom/cockpit/ops_bar.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/cockpit/ops_bar.py) · [原文テキスト](../../../90_Raw/wom/cockpit/ops_bar.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/06_Management_Cockpit|Management Cockpit]]

## モジュール説明（docstring原文）

```text
wom/cockpit/ops_bar.py — ⑦ 操作（Phase 8-3a・Phase 8-3c で N7 拡張）
================================================================================
◀ 戻る ／ ⚑ {画面ごとの意味} ／ ▶ 次へ：{次の画面}（設計書 §3.1）。

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3 §3.1
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md
      requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md §N7

`⚑` の意味は画面ごとに違う——S1 は「この配分で計画する」、S3 は「この実行結果を
記録する」。**その語（ラベル・注記）を `ops_bar.py` は持たない**（N7・K1と同じ
「語は1箇所にだけ定義する」原則）。持つのは画面側（`s1_allocate.COMMIT_LABEL_JA`
等）で、`frame.py` が画面を差し替えるときに `set_commit_label()` /
`set_commit_note()` で読み替えさせる。**このファイルには文言の初期値すら
置かない**（空文字列で始め、`frame.py` の初期化直後に必ず設定させる）。
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| ClassDef | `OpsBar` | 31 | ⑦。`on_commit` だけが本 Phase で実際に動く。 |
| FunctionDef | `__init__` | 34 | docstringなし（下のコード参照） |
| FunctionDef | `set_status` | 65 | docstringなし（下のコード参照） |
| FunctionDef | `set_next_label` | 68 | docstringなし（下のコード参照） |
| FunctionDef | `set_commit_label` | 71 | N7: `⚑` ボタンのラベルを画面ごとに差し替える。 |
| FunctionDef | `set_commit_note` | 75 | N7: `⚑` 横の注記を画面ごとに差し替える。 |
| FunctionDef | `set_back_enabled` | 79 | Phase 8-3c・N1: 画面が2枚になったので「◀ 戻る」を実際に使う画面が |

## 関連する知識源

- [[80_Sources/requests/Phase8_DesignMD_CockpitGUI.md|requests/Phase8_DesignMD_CockpitGUI.md]]
- [[80_Sources/requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md|requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md]]
- [[80_Sources/requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md|requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md]]
- [[80_Sources/wom/cockpit/s1_allocate.py|wom/cockpit/s1_allocate.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
wom/cockpit/ops_bar.py — ⑦ 操作（Phase 8-3a・Phase 8-3c で N7 拡張）
================================================================================
◀ 戻る ／ ⚑ {画面ごとの意味} ／ ▶ 次へ：{次の画面}（設計書 §3.1）。

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3 §3.1
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md
      requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md §N7

`⚑` の意味は画面ごとに違う——S1 は「この配分で計画する」、S3 は「この実行結果を
記録する」。**その語（ラベル・注記）を `ops_bar.py` は持たない**（N7・K1と同じ
「語は1箇所にだけ定義する」原則）。持つのは画面側（`s1_allocate.COMMIT_LABEL_JA`
等）で、`frame.py` が画面を差し替えるときに `set_commit_label()` /
`set_commit_note()` で読み替えさせる。**このファイルには文言の初期値すら
置かない**（空文字列で始め、`frame.py` の初期化直後に必ず設定させる）。
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from wom.cockpit.s1_allocate import BG_DARK, BG_LIGHT, BG_MID, FG_WHITE

_JA_FONT = ("Yu Gothic UI", 9)
_JA_FONT_BOLD = ("Yu Gothic UI", 10, "bold")
_FG_MUTED = "#78909C"
_FG_STATUS = "#64B5F6"


class OpsBar(tk.Frame):
    """⑦。`on_commit` だけが本 Phase で実際に動く。"""

    def __init__(self, parent, *, on_back: Callable[[], None],
                on_commit: Callable[[], None], on_next: Callable[[], None],
                next_label: str = "▶ 次へ", **kw):
        super().__init__(parent, bg=BG_MID, **kw)

        self._back_btn = tk.Button(self, text="◀ 戻る", command=on_back,
                                   bg=BG_LIGHT, fg=FG_WHITE, relief="flat",
                                   font=_JA_FONT, state="disabled")
        self._back_btn.pack(side="left", padx=(8, 4), pady=6)

        # 文言は空で始める——初期値も画面側（s1_allocate.COMMIT_LABEL_JA 等）に
        # 持たせ、frame.py の初期化直後に set_commit_label()/set_commit_note()
        # で必ず設定させる（ここに文言を1文字も書かない）。
        self._commit_btn = tk.Button(self, text="", command=on_commit,
                                     bg="#4CAF50", fg="#0B1F14", relief="flat",
                                     font=_JA_FONT_BOLD)
        self._commit_btn.pack(side="left", padx=4, pady=6)

        self._commit_note_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._commit_note_var, bg=BG_MID, fg=_FG_MUTED,
                font=("Segoe UI", 8)).pack(side="left", padx=(0, 12))

        self._status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._status_var, bg=BG_MID, fg=_FG_STATUS,
                font=("Segoe UI", 8)).pack(side="left", padx=(0, 12))

        self._next_btn = tk.Button(self, text=next_label, command=on_next,
                                   bg=BG_LIGHT, fg=FG_WHITE, relief="flat",
                                   font=_JA_FONT, state="disabled")
        self._next_btn.pack(side="right", padx=(4, 8), pady=6)

    def set_status(self, text: str) -> None:
        self._status_var.set(text)

    def set_next_label(self, text: str) -> None:
        self._next_btn.config(text=text)

    def set_commit_label(self, text: str) -> None:
        """N7: `⚑` ボタンのラベルを画面ごとに差し替える。"""
        self._commit_btn.config(text=text)

    def set_commit_note(self, text: str) -> None:
        """N7: `⚑` 横の注記を画面ごとに差し替える。"""
        self._commit_note_var.set(text)

    def set_back_enabled(self, enabled: bool) -> None:
        """Phase 8-3c・N1: 画面が2枚になったので「◀ 戻る」を実際に使う画面が
        出てきた（S3 -> S1）。S1 のように前の画面が無いときは disabled のまま。
        """
        self._back_btn.config(state=("normal" if enabled else "disabled"))

````
