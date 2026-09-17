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
