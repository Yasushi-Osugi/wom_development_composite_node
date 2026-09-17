# -*- coding: utf-8 -*-
"""
wom/cockpit/frame.py — 経営コックピットの骨格（Phase 8-3a）
================================================================================
設計書 §3.1 の7ブロックを組み立てる。本 Phase では **S1 だけが中身を持ち**、
他（S0/S2/S3/S4/S5）は Navigator 上に `○` として存在するだけ（枠だけ）。

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3 §3.1/§8.2
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md

【8-3b 以降への申し送り】S3 を足すとき、骨格側（本ファイル・navigator.py・
state_header.py・ops_bar.py）に手を入れずに済むことを狙って作った：
- 画面の実体は `self._body` に1枚だけ pack する（`_s1` のように）。S3 を足す
  ときは同じ形の画面クラス（`commit()` を持つ・`on_view_changed` を受け取る）を
  作り、`_current_step` に応じて `_body` の中身を差し替える形にする
- Navigator の `enabled` / `passed` は `_render_nav()` が1箇所で組む。S3 を
  有効にするのはこの関数の中身を直すだけで足りるはず
- ⑦ ops_bar の `on_commit` は「いま `_body` にある画面の `commit()` を呼ぶ」
  という間接呼び出しにしてあるので、画面が増えてもボタンの配線は変えずに済む

手を入れる必要が実際に出たら、それは骨格の切り方が足りない合図なので報告する。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Optional

from wom.cockpit.navigator import PlanningNavigator
from wom.cockpit.ops_bar import OpsBar
from wom.cockpit.s1_allocate import AllocationPanel, BG_DARK
from wom.cockpit.state_header import PlanningStateHeader

NEXT_LABEL_JA = {
    "S0": "▶ 次へ：S1 Allocate", "S1": "▶ 次へ：S2 Place", "S2": "▶ 次へ：S3 Run",
    "S3": "▶ 次へ：S4 Evaluate", "S4": "▶ 次へ：S5 Review", "S5": "▶ 次へ",
}


class CockpitFrame(tk.Frame):
    """コックピットの骨格。現状 `_body` には S1（`AllocationPanel`）だけが載る。"""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._current_step = "S1"
        self._state: Optional[dict] = None    # ⚑ で保存した Planning State（None=未保存）
        self._loaded: Optional[dict] = None   # {"model_dir","scenario_id"}

        # ① Planning Navigator
        self._nav = PlanningNavigator(self, on_navigate=self._on_navigate)
        self._nav.pack(fill="x")

        # ② Planning State ヘッダ
        self._header = PlanningStateHeader(self)
        self._header.pack(fill="x")

        # ⑦ 操作（③〜⑥＝_body より先に確保。Phase 8-2a・D3 と同じ理由で
        # side="bottom" を先に pack し、縮むのは常に _body 側にする）
        self._ops = OpsBar(self, on_back=self._on_back, on_commit=self._on_commit,
                           on_next=self._on_next,
                           next_label=NEXT_LABEL_JA[self._current_step])
        self._ops.pack(fill="x", side="bottom")

        # ③〜⑥（本 Phase では S1 の中身がそのまま入る）
        self._body = tk.Frame(self, bg=BG_DARK)
        self._body.pack(fill="both", expand=True)

        self._s1 = AllocationPanel(self._body, on_view_changed=self._on_s1_view_changed)
        self._s1.pack(fill="both", expand=True)

        self._render_nav()

    # ------------------------------------------------------------------
    # 現在の画面（本 Phase では常に S1）
    # ------------------------------------------------------------------
    def _current_screen(self):
        return self._s1

    def _render_nav(self) -> None:
        passed = {"S1"} if self._state is not None else set()
        self._nav.render(current=self._current_step, enabled=("S1",), passed=passed)

    # ------------------------------------------------------------------
    # コールバック
    # ------------------------------------------------------------------
    def _on_s1_view_changed(self, model_dir: str, scenario_id: str, view: dict) -> None:
        self._loaded = {"model_dir": model_dir, "scenario_id": scenario_id}
        self._header.render(loaded=self._loaded, state=self._state)

    def _on_commit(self) -> None:
        try:
            state = self._current_screen().commit()
        except Exception as e:   # noqa: BLE001 — 入力ミスをダイアログで見せる
            messagebox.showerror("S1 Allocate", f"計画案の保存に失敗しました:\n{e}")
            return
        self._state = state
        self._header.render(loaded=self._loaded, state=self._state)
        self._ops.set_status(f"保存: {state['allocation_id']}")
        self._render_nav()

    def _on_back(self) -> None:
        pass   # S1 が最初の画面なので常に disabled（押されることはない）

    def _on_next(self) -> None:
        pass   # 次の画面（S2）がまだ無いので常に disabled（押されることはない）

    def _on_navigate(self, step: str) -> None:
        pass   # 本 Phase では S1 のみ enabled なので実質 no-op（同じ画面に留まる）
