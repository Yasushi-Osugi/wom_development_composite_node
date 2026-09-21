---
tags: [wom, code]
---
# wom/cockpit/frame.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/cockpit/frame.py) · [原文テキスト](../../../90_Raw/wom/cockpit/frame.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/06_Management_Cockpit|Management Cockpit]]

## モジュール説明（docstring原文）

```text
wom/cockpit/frame.py — 経営コックピットの骨格（Phase 8-3a・Phase 8-3c で N1 拡張）
================================================================================
設計書 §3.1 の7ブロックを組み立てる。Phase 8-3c で S3 Run が入り、**画面が
2枚**になった——8-3a の完了条件「S3 を足すとき骨格側に手を入れずに済む」を
初めて検証できる回だった。

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3/5 §3.1/§8.2
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md
      requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md §N1/§N7

【8-3a の仮説の検証結果（正直に書く）】
  navigator.py     無変更で足りた（想定どおり）
  state_header.py  無変更で足りた（`pre_plan`/`feasible_plan` 両方を元々扱えた）
  frame.py         入った（想定どおり——画面差し替え機構を実装する場所）
  ops_bar.py       入った（想定外——`⚑` の文言を画面ごとの定数として扱う
                   set_commit_label()/set_commit_note() API が要った。K1と
                   同じ「語は1箇所にだけ定義する」原則をここにも適用した）

手を入れる必要がさらに出たら、それは骨格の切り方が足りない合図なので報告する。
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| ClassDef | `CockpitFrame` | 54 | コックピットの骨格。`_body` には S1（`AllocationPanel`）と |
| FunctionDef | `__init__` | 60 | docstringなし（下のコード参照） |
| FunctionDef | `_current_screen` | 99 | docstringなし（下のコード参照） |
| FunctionDef | `_render_nav` | 102 | docstringなし（下のコード参照） |
| FunctionDef | `_switch_to` | 110 | docstringなし（下のコード参照） |
| FunctionDef | `_on_s1_view_changed` | 133 | docstringなし（下のコード参照） |
| FunctionDef | `_on_commit` | 137 | docstringなし（下のコード参照） |
| FunctionDef | `_on_back` | 148 | docstringなし（下のコード参照） |
| FunctionDef | `_on_next` | 152 | docstringなし（下のコード参照） |
| FunctionDef | `_on_navigate` | 155 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/requests/Phase8_DesignMD_CockpitGUI.md|requests/Phase8_DesignMD_CockpitGUI.md]]
- [[80_Sources/requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md|requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md]]
- [[80_Sources/requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md|requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md]]
- [[80_Sources/wom/cockpit/navigator.py|wom/cockpit/navigator.py]]
- [[80_Sources/wom/cockpit/ops_bar.py|wom/cockpit/ops_bar.py]]
- [[80_Sources/wom/cockpit/s1_allocate.py|wom/cockpit/s1_allocate.py]]
- [[80_Sources/wom/cockpit/s3_run.py|wom/cockpit/s3_run.py]]
- [[80_Sources/wom/cockpit/state_header.py|wom/cockpit/state_header.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
wom/cockpit/frame.py — 経営コックピットの骨格（Phase 8-3a・Phase 8-3c で N1 拡張）
================================================================================
設計書 §3.1 の7ブロックを組み立てる。Phase 8-3c で S3 Run が入り、**画面が
2枚**になった——8-3a の完了条件「S3 を足すとき骨格側に手を入れずに済む」を
初めて検証できる回だった。

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3/5 §3.1/§8.2
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md
      requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md §N1/§N7

【8-3a の仮説の検証結果（正直に書く）】
  navigator.py     無変更で足りた（想定どおり）
  state_header.py  無変更で足りた（`pre_plan`/`feasible_plan` 両方を元々扱えた）
  frame.py         入った（想定どおり——画面差し替え機構を実装する場所）
  ops_bar.py       入った（想定外——`⚑` の文言を画面ごとの定数として扱う
                   set_commit_label()/set_commit_note() API が要った。K1と
                   同じ「語は1箇所にだけ定義する」原則をここにも適用した）

手を入れる必要がさらに出たら、それは骨格の切り方が足りない合図なので報告する。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Optional

from wom.cockpit.navigator import PlanningNavigator
from wom.cockpit.ops_bar import OpsBar
from wom.cockpit.s1_allocate import (
    COMMIT_LABEL_JA as S1_COMMIT_LABEL_JA, COMMIT_NOTE_JA as S1_COMMIT_NOTE_JA,
    AllocationPanel, BG_DARK,
)
from wom.cockpit.s3_run import (
    COMMIT_LABEL_JA as S3_COMMIT_LABEL_JA, COMMIT_NOTE_JA as S3_COMMIT_NOTE_JA,
    RunPanel,
)
from wom.cockpit.state_header import PlanningStateHeader

NEXT_LABEL_JA = {
    "S0": "▶ 次へ：S1 Allocate", "S1": "▶ 次へ：S2 Place", "S2": "▶ 次へ：S3 Run",
    "S3": "▶ 次へ：S4 Evaluate", "S4": "▶ 次へ：S5 Review", "S5": "▶ 次へ",
}

# 画面ごとの ⚑ 文言（N7）。ops_bar.py はこれを持たない——frame.py が画面を
# 差し替えるときにここを引いて set_commit_label()/set_commit_note() に渡す。
_COMMIT_TEXT_JA = {
    "S1": (S1_COMMIT_LABEL_JA, S1_COMMIT_NOTE_JA),
    "S3": (S3_COMMIT_LABEL_JA, S3_COMMIT_NOTE_JA),
}


class CockpitFrame(tk.Frame):
    """コックピットの骨格。`_body` には S1（`AllocationPanel`）と
    S3（`RunPanel`）が両方 pack されており、`_current_step` に応じて
    どちらか一方だけを見せる（もう一方は `pack_forget()`）。
    """

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
        label, note = _COMMIT_TEXT_JA["S1"]
        self._ops.set_commit_label(label)
        self._ops.set_commit_note(note)

        # ③〜⑥（画面の実体。両方作っておき、pack/pack_forget で切り替える）
        self._body = tk.Frame(self, bg=BG_DARK)
        self._body.pack(fill="both", expand=True)

        self._s1 = AllocationPanel(self._body, on_view_changed=self._on_s1_view_changed)
        self._s1.pack(fill="both", expand=True)

        self._s3 = RunPanel(self._body)
        # S3 は最初は隠す（pack しない）——S1 だけが見えている状態で開始する。

        self._render_nav()

    # ------------------------------------------------------------------
    # 現在の画面
    # ------------------------------------------------------------------
    def _current_screen(self):
        return self._s3 if self._current_step == "S3" else self._s1

    def _render_nav(self) -> None:
        passed = {"S1"} if self._state is not None else set()
        enabled = ("S1", "S3") if self._state is not None else ("S1",)
        self._nav.render(current=self._current_step, enabled=enabled, passed=passed)

    # ------------------------------------------------------------------
    # 画面の切り替え（N1）
    # ------------------------------------------------------------------
    def _switch_to(self, step: str) -> None:
        if step == self._current_step:
            return
        self._current_screen().pack_forget()
        self._current_step = step
        if step == "S3":
            # S3 は pre_plan（self._state）を持ち回る——S1 の読み込み文脈
            # （model_dir/scenario_id/cap_wk/uom）は S1 自身が既に持っている
            # ので、そこから読む（S1 -> S3 の唯一のハンドオフ経路）。
            self._s3.load(self._s1._model_dir, self._s1._scenario_id,
                         self._s1._cap_wk, self._state, uom=self._s1._uom)
        self._current_screen().pack(fill="both", expand=True)
        label, note = _COMMIT_TEXT_JA[step]
        self._ops.set_commit_label(label)
        self._ops.set_commit_note(note)
        self._ops.set_next_label(NEXT_LABEL_JA[step])
        self._ops.set_back_enabled(step != "S1")   # S1 の前に画面が無い
        self._ops.set_status("")
        self._render_nav()

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
            messagebox.showerror("Cockpit", f"保存に失敗しました:\n{e}")
            return
        self._state = state
        self._header.render(loaded=self._loaded, state=self._state)
        self._ops.set_status(f"保存: {state['allocation_id']}")
        self._render_nav()

    def _on_back(self) -> None:
        if self._current_step == "S3":
            self._switch_to("S1")

    def _on_next(self) -> None:
        pass   # 次の画面（S2/S4）がまだ無いので常に disabled（押されることはない）

    def _on_navigate(self, step: str) -> None:
        if step in ("S1", "S3"):
            self._switch_to(step)

````
