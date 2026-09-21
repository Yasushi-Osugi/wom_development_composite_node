---
tags: [wom, code]
---
# wom/cockpit/plateau_band.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/cockpit/plateau_band.py) · [原文テキスト](../../../90_Raw/wom/cockpit/plateau_band.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/06_Management_Cockpit|Management Cockpit]]

## モジュール説明（docstring原文）

```text
wom/cockpit/plateau_band.py — 台地の帯（絶対額・Phase 8-3a・R4）
================================================================================
`best_point()` の `plateau_tol`（相対値）は、地形が同じでも利益水準が変わると
台地サイズが変わってしまう問題を持っていた（実測: SP_Oil_Local・総量固定なのに
`mat=6` で3点、`mat=500` で1点。Request Letter §F4）。

正典: requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md §F4
      Phase 8-3a 追補（大杉さん・Claude君の実機検証、2026-09-18・chat経由。
      既定値 0.05% への訂正・帯の編集可能化。ファイルとしては未着手）

**`wom.allocation.grid.best_point()` / `plateau_tol` はここでは触らない**
（Phase 6-5 で決着済み）。本モジュールは「台地の**報告**」だけに効く別の集計で、
`chosen_point()` が選ぶ実際の採用点（Phase 6-5・E1）には影響しない——
`view` 側（`wom/cockpit/s1_view_model.py`）が `plateau` を帯で数え直すだけ。

設計（Request Letter §F4 の3点セット）:
  1. 帯を画面に出す（問いと答えを同時に読める形。例:「最良から ¥500万以内に 15 点」）。
     さらに Addendum で**編集可能**にする——「帯は技術定数ではなく経営パラメータ」
     （§F4-1 の原文どおり）なら、読むだけでなく動かせるべきだった
  2. 既定値は **モデルを読み込んだとき1回だけ** `P_opt` の 0.05% あたりから作る
     （Addendum: 当初 0.01% は判別力を落としすぎていた。§Addendum 参照）
  3. **シナリオを切り替えても帯は固定**（作り直さない）——同一モデル内の比較を
     厳密にするための唯一の理由。呼び出し側（`s1_view_model.py`/`s1_allocate.py`）
     が「モデルを読み込んだとき」だけ `default_band_yen()` を呼び、以降は
     その値を保持し続けること（**手入力で上書きした帯も同じ扱い**——モデルが
     変わるまで固定）

【Addendum: 既定 0.01% は10倍きつすぎた】
実測（oil-global-2027）: 0.01%（¥100万）だと SP_Oil_Local 等ほぼ全ノードが
「1点」に潰れ、相対値時代の `plateau_tol` が拾えていた判別力（例: SP_Oil_EU_Import
で2点）まで失っていた。R4 が目指したのは「情報を保ったまま不安定さを取る」ことで
あり、安定させた代わりに情報を消しては目的を半分しか達成していない。
0.05%（oil で ¥625万 → ¥500万に丸め）なら SP_Oil_Local が `mat=6`/`mat=500` の
両方で厳密に 15/15 と安定しつつ、判別力も残ることを実測で確認済み。
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_floor_to_nice` | 53 | docstringなし（下のコード参照） |
| FunctionDef | `default_band_yen` | 65 | `P_opt` から既定の帯（円）を作る。 |
| FunctionDef | `plateau_by_band` | 76 | 台地を絶対額の帯で数え直す（グリッド順を保持）。 |
| FunctionDef | `format_band_ja` | 89 | 帯の額を読める日本語表記にする（見出し用）。 |

## 関連する知識源

- [[80_Sources/requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md|requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md]]
- [[80_Sources/wom/cockpit/s1_view_model.py|wom/cockpit/s1_view_model.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
wom/cockpit/plateau_band.py — 台地の帯（絶対額・Phase 8-3a・R4）
================================================================================
`best_point()` の `plateau_tol`（相対値）は、地形が同じでも利益水準が変わると
台地サイズが変わってしまう問題を持っていた（実測: SP_Oil_Local・総量固定なのに
`mat=6` で3点、`mat=500` で1点。Request Letter §F4）。

正典: requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md §F4
      Phase 8-3a 追補（大杉さん・Claude君の実機検証、2026-09-18・chat経由。
      既定値 0.05% への訂正・帯の編集可能化。ファイルとしては未着手）

**`wom.allocation.grid.best_point()` / `plateau_tol` はここでは触らない**
（Phase 6-5 で決着済み）。本モジュールは「台地の**報告**」だけに効く別の集計で、
`chosen_point()` が選ぶ実際の採用点（Phase 6-5・E1）には影響しない——
`view` 側（`wom/cockpit/s1_view_model.py`）が `plateau` を帯で数え直すだけ。

設計（Request Letter §F4 の3点セット）:
  1. 帯を画面に出す（問いと答えを同時に読める形。例:「最良から ¥500万以内に 15 点」）。
     さらに Addendum で**編集可能**にする——「帯は技術定数ではなく経営パラメータ」
     （§F4-1 の原文どおり）なら、読むだけでなく動かせるべきだった
  2. 既定値は **モデルを読み込んだとき1回だけ** `P_opt` の 0.05% あたりから作る
     （Addendum: 当初 0.01% は判別力を落としすぎていた。§Addendum 参照）
  3. **シナリオを切り替えても帯は固定**（作り直さない）——同一モデル内の比較を
     厳密にするための唯一の理由。呼び出し側（`s1_view_model.py`/`s1_allocate.py`）
     が「モデルを読み込んだとき」だけ `default_band_yen()` を呼び、以降は
     その値を保持し続けること（**手入力で上書きした帯も同じ扱い**——モデルが
     変わるまで固定）

【Addendum: 既定 0.01% は10倍きつすぎた】
実測（oil-global-2027）: 0.01%（¥100万）だと SP_Oil_Local 等ほぼ全ノードが
「1点」に潰れ、相対値時代の `plateau_tol` が拾えていた判別力（例: SP_Oil_EU_Import
で2点）まで失っていた。R4 が目指したのは「情報を保ったまま不安定さを取る」ことで
あり、安定させた代わりに情報を消しては目的を半分しか達成していない。
0.05%（oil で ¥625万 → ¥500万に丸め）なら SP_Oil_Local が `mat=6`/`mat=500` の
両方で厳密に 15/15 と安定しつつ、判別力も残ることを実測で確認済み。
"""
from __future__ import annotations

import math
from typing import List

# 既定帯の作り方: P_opt の 0.05% を「読める額」に丸める（Addendum: 0.01% → 0.05%）。
_DEFAULT_BAND_FRACTION = 0.0005   # 0.05%

# 丸め幅は 1-2-5 の対数刻み（1, 2, 5, 10, 20, 50, 100, ...）で、raw 以下の
# 最大値に**切り下げる**——「round(raw / 100万) × 100万」のような単純な最近傍
# 丸めだと、¥625万 が ¥600万 に丸まってしまい「情報を保つ」狙いに合わない
# （Addendum で実測: ¥625万 は 1-2-5 刻みでは ¥500万 が正しい切り下げ先）。
_NICE_MULTIPLIERS = (5, 2, 1)   # 降順（同じ桁の中で raw に近い側から試す）


def _floor_to_nice(raw: float) -> float:
    if raw <= 0:
        return 0.0
    exp = math.floor(math.log10(raw))
    base = 10 ** exp
    for m in _NICE_MULTIPLIERS:
        candidate = m * base
        if candidate <= raw + 1e-9:   # 浮動小数の際どい等値判定を吸収
            return candidate
    return base   # 理論上ここには来ない（m=1 が必ず raw 以下になるため）の保険


def default_band_yen(p_opt: float) -> float:
    """`P_opt` から既定の帯（円）を作る。

    呼び出しはモデルを読み込んだときの**1回だけ**にすること（シナリオ切替の
    たびに呼ぶと、シナリオごとに帯が動いてしまい R4 の狙い——同一モデル内の
    比較を厳密にする——が崩れる）。
    """
    raw = abs(p_opt) * _DEFAULT_BAND_FRACTION
    return _floor_to_nice(raw)


def plateau_by_band(surface: List[dict], band_yen: float) -> List[dict]:
    """台地を絶対額の帯で数え直す（グリッド順を保持）。

    格子が同一利益水準でも変わらないよう、`surface` 自身の最大値
    （`chosen_point()` の argmax と同じ値）を基準にする——`best_point()` の
    `plateau_tol` は使わない。
    """
    if not surface:
        return []
    best = max(r["profit"] for r in surface)
    return [r for r in surface if best - r["profit"] <= band_yen]


def format_band_ja(band_yen: float) -> str:
    """帯の額を読める日本語表記にする（見出し用）。"""
    if band_yen >= 1e8:
        return f"¥{band_yen / 1e8:.3g}億"
    if band_yen >= 1e4:
        return f"¥{band_yen / 1e4:.0f}万"
    return f"¥{band_yen:,.0f}"

````
