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

# 【重要・実測で判明】ここで matplotlib.use("TkAgg") を呼んではいけない。
# 一度でも呼ぶと、その後同一プロセス内で実行される他のテスト・ツール
# （`tools/plot_allocation_map.py` 等、`matplotlib.use("Agg")` で headless 出力
# するはずのもの）まで含めて matplotlib の**グローバル**バックエンドが TkAgg に
# 汚染される。このマシンの Tcl 初期化は tk.Tk() を作るたびにレースを持つ
# （tests/test_gui_panel_invariants.py の docstring 参照）ため、無関係な Agg
# 専用テスト（`tests/test_allocation_plot.py`）が pytest フルスイートの中で
# 間欠的に `TclError: Can't find a usable init.tcl` で落ちる事故を実際に
# 引き起こした（2026-09-18 実測・全体テスト2回中2回とも別の Agg テストが落ちた）。
# `wom/cockpit/` 配下は pyplot を経由せず Figure() + FigureCanvasTkAgg を
# 直接使っている（s1_allocate.py）ため、バックエンド指定は元々不要だった。
# フォント設定だけが必須——これが無いと日本語ラベルを含む図がすべて豆腐化する。
matplotlib.rcParams["font.family"] = ["Yu Gothic", "DejaVu Sans"]
