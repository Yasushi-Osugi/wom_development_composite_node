# -*- coding: utf-8 -*-
"""
wom/cockpit/ — 経営コックピット（Phase 8）
================================================================================
`wom/gui/app.py`（既存9タブ・機能中心）とは別の起動経路。`python -m main --cockpit`
で起動する意思決定中心の画面群。

正典: requests/Phase8_DesignMD_CockpitGUI.md rev.3 §3 / §8.2
      Phase 8-3a 追補（大杉さん・Claude君の実機検証、2026-09-18・chat経由。
      日本語フォント設定が移設で失われていた欠陥の修正）

【日本語フォント設定はここで行う】 `wom/gui/app.py` は
`matplotlib.rcParams["font.family"] = ["Yu Gothic", "DejaVu Sans"]` を import 時に
設定しているが、コックピットは設計書の「`app.py` は1行も変えない」を守るため
`app.py` を import しない——だから9タブ版の設定はコックピット側には効かず、
グラフ中の日本語が豆腐（`Glyph ... missing from font(s) DejaVu Sans`）になる。
`wom/cockpit/s1_allocate.py` 等の docstring には移設前の「app.py で設定済み」
という記述が残っていたが、移設した時点で誤りになっていた（Phase 8-1b の
`Scenario.material_usd` と同型の欠陥——ある入口の設定を、そこから離れたコードが
当てにしていた）。`wom.cockpit` パッケージの `__init__.py` は
`wom/cockpit/` 配下のどのモジュールをインポートしても最初に実行されるので、
ここに置けば9タブ版の実装から独立して確実に効く。
"""
from __future__ import annotations

import matplotlib

# 現状 wom/cockpit/ 配下は pyplot を経由せず Figure() + FigureCanvasTkAgg を
# 直接使っている（s1_allocate.py）ため matplotlib.use("TkAgg") 自体は必須では
# ないが、app.py と同じ前提を揃えておく（将来 pyplot を使う画面が増えても
# 挙動が変わらないようにするため）。フォント設定は必須——これが無いと
# 日本語ラベルを含む図がすべて豆腐化する。
matplotlib.use("TkAgg")
matplotlib.rcParams["font.family"] = ["Yu Gothic", "DejaVu Sans"]
