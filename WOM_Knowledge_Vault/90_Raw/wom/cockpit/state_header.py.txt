# -*- coding: utf-8 -*-
"""
wom/cockpit/state_header.py — ② Planning State ヘッダ（Phase 8-3a）
================================================================================
設計書 §3.1 のモックアップ:

    soysauce-jpy-2027-alloc │ s4_compound (FX150 / US tariff 12.5%)
    A03  JP10 / US45 / EU45 │ ● Pre-Plan │ P_greedy 135.5M  P_grid 132.1M  P_opt —

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3 §3.1
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md

Planning State が無い（モデルを読み込んだ直後、まだ ⚑ で保存していない）ときは
**「未保存」を出す。空欄にしない**（Phase 8-2・C4「空白の箱」の教訓、
Request Letter §2 F3）。
"""
from __future__ import annotations

import os
import tkinter as tk
from typing import Optional, Sequence

from wom.cockpit.s1_allocate import BG_DARK, FG_WHITE
from wom.cockpit.s1_view_model import format_market_name

_JA_FONT = ("Yu Gothic UI", 9)
_JA_FONT_BOLD = ("Yu Gothic UI", 9, "bold")
_FG_MUTED = "#78909C"

_STATE_LABEL_JA = {"pre_plan": "Pre-Plan", "feasible_plan": "Feasible Plan"}
_PROFIT_LEVEL_KEYS: Sequence[str] = ("P_opt", "P_greedy", "P_grid", "P_hier")


def _format_allocation_ja(allocation: dict) -> str:
    sorted_m = sorted(allocation, key=lambda m: -allocation.get(m, 0.0))
    return " / ".join(f"{format_market_name(m)}{allocation[m] * 100:.0f}" for m in sorted_m)


def _format_profit_levels_ja(profit_levels: dict) -> str:
    parts = []
    for key in _PROFIT_LEVEL_KEYS:
        v = profit_levels.get(key)
        parts.append(f"{key} {v / 1e6:.1f}M" if v is not None else f"{key} —")
    return "  ".join(parts)


class PlanningStateHeader(tk.Frame):
    """②。`render(loaded=, state=)` で描き直す。"""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._line1 = tk.Label(self, text="", bg=BG_DARK, fg=FG_WHITE,
                               font=_JA_FONT, anchor="w")
        self._line1.pack(fill="x", padx=8, pady=(4, 0))
        self._line2 = tk.Label(self, text="", bg=BG_DARK, fg=FG_WHITE,
                               font=_JA_FONT_BOLD, anchor="w")
        self._line2.pack(fill="x", padx=8, pady=(0, 4))
        self.render(loaded=None, state=None)

    def render(self, *, loaded: Optional[dict], state: Optional[dict]) -> None:
        """
        Args:
            loaded: `{"model_dir": str, "scenario_id": str}` | None
                （S1 が現在読み込んでいるモデル。まだ何も読み込んでいなければ None）
            state: `wom.planning_state` の state dict | None
                （⚑ でまだ保存していなければ None——このとき「未保存」を出す）
        """
        if loaded is None:
            self._line1.config(text="（モデル未読み込み）", fg=_FG_MUTED)
        else:
            case = os.path.basename(loaded["model_dir"].rstrip("/\\"))
            self._line1.config(text=f"{case} │ {loaded['scenario_id']}", fg=FG_WHITE)

        if state is None:
            self._line2.config(text="未保存", fg=_FG_MUTED)
            return

        alloc_ja = _format_allocation_ja(state.get("allocation", {}))
        state_label = _STATE_LABEL_JA.get(state.get("state"), state.get("state") or "?")
        levels_ja = _format_profit_levels_ja(state.get("profit_levels", {}))
        self._line2.config(
            fg=FG_WHITE,
            text=(f"{state.get('allocation_id', '?')}  {alloc_ja} │ "
                 f"● {state_label} │ {levels_ja}"))
