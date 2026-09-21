# Presentation

構造・時系列・利益地形・選択肢を説明可能にする。

**入出力:** ネットワーク・PSI・評価値 → グラフ／地図／帳票

分類: オーナー合意の6分類。配置は知識ナビゲーション用であり、実装の単一責任や依存方向を保証しない。

## 最初に読む

- [[80_Sources/requests/Phase3_DesignMD_Visualization.md|requests/Phase3_DesignMD_Visualization.md]]
- [[80_Sources/requests/Phase4_DesignMD_AllocationMeritRegime.md|requests/Phase4_DesignMD_AllocationMeritRegime.md]]
- [[80_Sources/docs/design/lot_id_traceability_and_coverage_views.md|docs/design/lot_id_traceability_and_coverage_views.md]]

## 機能トピック



## 実装モジュール

- [[80_Sources/wom/engine/event_timeline.py|wom/engine/event_timeline.py]]
- [[80_Sources/wom/engine/hammock_layout.py|wom/engine/hammock_layout.py]]
- [[80_Sources/wom/gui/__init__.py|wom/gui/__init__.py]]
- [[80_Sources/wom/gui/app.py|wom/gui/app.py]]
- [[80_Sources/wom/visualization/__init__.py|wom/visualization/__init__.py]]
- [[80_Sources/wom/visualization/merit_order.py|wom/visualization/merit_order.py]]
- [[80_Sources/wom/visualization/pareto_front.py|wom/visualization/pareto_front.py]]
- [[80_Sources/wom/visualization/regime_map.py|wom/visualization/regime_map.py]]

## 関連テスト候補（import文字列による分類）

網羅的なカバレッジ認定ではない。

- [[80_Sources/tests/test_merit_order.py|tests/test_merit_order.py]]
- [[80_Sources/tests/test_merit_order_plot.py|tests/test_merit_order_plot.py]]
- [[80_Sources/tests/test_pareto_front.py|tests/test_pareto_front.py]]
- [[80_Sources/tests/test_regime_map.py|tests/test_regime_map.py]]

[[00_Start/Home|機能マップへ戻る]]
