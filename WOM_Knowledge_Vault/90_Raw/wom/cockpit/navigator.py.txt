# -*- coding: utf-8 -*-
"""
wom/cockpit/navigator.py — ① Planning Navigator（Phase 8-3a）
================================================================================
S0 Case ▸ S1 Allocate ▸ S2 Place ▸ S3 Run ▸ S4 Evaluate ▸ S5 Review。
`●` = 通過済み（Planning State に欄あり）、`○` = 未通過（設計書 §3.2）。

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3 §3.1/§3.2
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md

本 Phase では S1 だけが中身を持つ画面なので、S1 以外は常に `○`・クリック不可の
グレーアウトのまま（Request Letter §2 F3）。8-3b 以降で S2〜S5 を足すときは、
`render()` の `enabled` / `passed` に足すだけで済む（このファイル自体は無変更で
よいはず——手を入れる必要が出たら、それは骨格の切り方が足りない合図）。
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, Sequence

from wom.cockpit.s1_allocate import BG_MID, FG_ACC, FG_WHITE

STEP_ORDER = ("S0", "S1", "S2", "S3", "S4", "S5")

STEP_LABEL_JA = {
    "S0": "S0 Case", "S1": "S1 Allocate", "S2": "S2 Place",
    "S3": "S3 Run", "S4": "S4 Evaluate", "S5": "S5 Review",
}

_JA_FONT = ("Yu Gothic UI", 9)
_JA_FONT_CURRENT = ("Yu Gothic UI", 9, "bold")
_FG_DISABLED = "#546E7A"


class PlanningNavigator(tk.Frame):
    """①。`render(current=, enabled=, passed=)` で描き直す。"""

    def __init__(self, parent, *, on_navigate: Optional[Callable[[str], None]] = None, **kw):
        super().__init__(parent, bg=BG_MID, **kw)
        self._on_navigate = on_navigate
        self._row = tk.Frame(self, bg=BG_MID)
        self._row.pack(fill="x", padx=8, pady=4)
        self.render(current="S1", enabled=("S1",), passed=())

    def render(self, *, current: str, enabled: Sequence[str], passed: Sequence[str]) -> None:
        for w in self._row.winfo_children():
            w.destroy()
        enabled_set = frozenset(enabled)
        passed_set = frozenset(passed)
        for i, step in enumerate(STEP_ORDER):
            if i > 0:
                tk.Label(self._row, text="  ▸  ", bg=BG_MID, fg=_FG_DISABLED,
                        font=_JA_FONT).pack(side="left")
            marker = "●" if step in passed_set else "○"
            is_current = (step == current)
            is_enabled = step in enabled_set
            color = FG_ACC if is_current else (FG_WHITE if is_enabled else _FG_DISABLED)
            font = _JA_FONT_CURRENT if is_current else _JA_FONT
            lbl = tk.Label(self._row, text=f"{marker} {STEP_LABEL_JA[step]}", bg=BG_MID,
                          fg=color, font=font, cursor=("hand2" if is_enabled else ""))
            lbl.pack(side="left")
            if is_enabled and self._on_navigate is not None:
                lbl.bind("<Button-1>", lambda _e, s=step: self._on_navigate(s))
