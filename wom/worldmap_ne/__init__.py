# -*- coding: utf-8 -*-
"""
wom.worldmap_ne — World Map の試作：地図を WOM の中で描く方式（Natural Earth ＋ matplotlib）
（RequestLetter_SimMgmt_WorldMapTrial Part 2）

World Map タブは、この描き方（data.py）で置き換えた（RequestLetter_WorldMap_ActualFlows：
wom/gui/worldmap_panel.py、流れは計画の実出荷 flows.py）。この独立した窓（viewer.py）は描画の速さを
測る道具として残す。その流れは需要から作ったもので（model.py）、計画の結果ではない。

    python -m wom.worldmap_ne --model ev-thailand-2026      # 試作の画面
    python -m wom.worldmap_ne.bench                          # 計測（表と JSON）

- data.py   地図データ（data/worldmap_ne/ne_*.npz）の読み込み、投影、細かさの選択、切り出し
- model.py  試作の窓の拠点・線・週ごとの需要の流れ（demand_forecast から。計画の結果ではない）
- flows.py  World Map タブの拠点・物理の区間・計画の実出荷の流れ（出荷の記録から）
- viewer.py 画面（matplotlib ＋ Tk）。ズーム・移動・週の再生（blitting あり／なし）
- bench.py  計測

実行時に要るのは numpy・matplotlib・pandas・tkinter だけ（シェープファイルは読まない）。
"""
