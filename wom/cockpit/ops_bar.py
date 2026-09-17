# -*- coding: utf-8 -*-
"""
wom/cockpit/ops_bar.py — ⑦ 操作（Phase 8-3a）
================================================================================
◀ 戻る ／ ⚑ この計画案を保存 ／ ▶ 次へ：{次の画面}（設計書 §3.1）。

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3 §3.1
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md

本 Phase では S1 だけが実在する画面なので、◀・▶ とも常に disabled——
**ボタンは出す**（次に何が来るかが見えていることに意味がある。Request Letter §2 F3）。
`⚑` だけが実際に動く（`AllocationPanel.commit()` を呼ぶ）。
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

        self._commit_btn = tk.Button(self, text="⚑ この計画案を保存", command=on_commit,
                                     bg="#4CAF50", fg="#0B1F14", relief="flat",
                                     font=_JA_FONT_BOLD)
        self._commit_btn.pack(side="left", padx=4, pady=6)

        # Phase 8-2・C1.3 由来の注記をそのまま踏襲——⚑ が計画するのは結論行
        # （P_opt、または手入力を選んでいればその値）であって、ドリルダウン先の
        # 子ノードの走査結果ではないことを明示する。
        tk.Label(self, text="（計画するのは上の推奨配分です）", bg=BG_MID, fg=_FG_MUTED,
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
