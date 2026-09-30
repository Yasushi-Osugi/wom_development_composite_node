# -*- coding: utf-8 -*-
"""
wom.worldmap_ne — World Map の試作：地図を WOM の中で描く方式（Natural Earth ＋ matplotlib）
（RequestLetter_SimMgmt_WorldMapTrial Part 2）

今の World Map タブ（tkintermapview ＋ タイル）は置き換えない。独立した窓で動く試作である。

    python -m wom.worldmap_ne --model ev-thailand-2026      # 試作の画面
    python -m wom.worldmap_ne.bench                          # 計測（表と JSON）

- data.py   地図データ（data/worldmap_ne/ne_*.npz）の読み込み、投影、細かさの選択、切り出し
- model.py  サンプルモデルの拠点・拠点間の線・週ごとの流れ（demand_forecast から）
- viewer.py 画面（matplotlib ＋ Tk）。ズーム・移動・週の再生（blitting あり／なし）
- bench.py  計測

実行時に要るのは numpy・matplotlib・pandas・tkinter だけ（シェープファイルは読まない）。
"""
