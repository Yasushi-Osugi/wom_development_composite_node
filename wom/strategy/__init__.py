# -*- coding: utf-8 -*-
"""
wom/strategy — 経営施策を WOM の案の入力に変換する（画面に依存しない。エンジンを import しない）
=============================================================================================
RequestLetter_Promo_Convert_Slice1（2026-11-21）。定義 v0.2（翻訳と変換を分ける）、
販促の業務定義 v0.1（GPT-MC君）。

    rules.py                  型ごとの規則（純関数）：需要の増減の整数化、円への換算
    sheets.py                 施策・仮説・外部環境・案の組み立てのシートと型カタログを読む・検査する
    convert.py                1 つの案に変換する（需要・費用の前提・変更記録）。冪等
    compare.py                4 案の要約（比較の道具の関数を使う）
    measure_type_catalog.csv  型カタログ（初版は promo_demand_delta・promo_external_cost）

止めるときは StrategyError（ファイル・行・値・直し方を出す。黙った既定値を作らない）。
"""


class StrategyError(ValueError):
    """The conversion cannot be made: the message says the file, the row, the value and how to fix it."""


CATALOG_VERSION = "v0.2"   # v0.2 (2026-11-25): the three Product launch types (RequestLetter_Launch_Convert_Slice1)
