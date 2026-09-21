# Management Cockpit

前提・配分案・実行結果を一つの意思決定手順で扱う。

**入出力:** ユーザー判断・Planning State → 採用／実行／再評価

分類: オーナー合意の6分類。配置は知識ナビゲーション用であり、実装の単一責任や依存方向を保証しない。

## 最初に読む

- [[80_Sources/requests/Phase8_DesignMD_CockpitGUI.md|requests/Phase8_DesignMD_CockpitGUI.md]]
- [[80_Sources/requests/Phase7_RequestLetter_to_CodeKun.md|requests/Phase7_RequestLetter_to_CodeKun.md]]
- [[80_Sources/requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md|requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md]]

## 機能トピック

- [[20_Topics/08_Cockpit|S1・S3とManagement Cockpit]]

## 実装モジュール

- [[80_Sources/wom/cockpit/__init__.py|wom/cockpit/__init__.py]]
- [[80_Sources/wom/cockpit/cockpit_app.py|wom/cockpit/cockpit_app.py]]
- [[80_Sources/wom/cockpit/frame.py|wom/cockpit/frame.py]]
- [[80_Sources/wom/cockpit/navigator.py|wom/cockpit/navigator.py]]
- [[80_Sources/wom/cockpit/ops_bar.py|wom/cockpit/ops_bar.py]]
- [[80_Sources/wom/cockpit/plateau_band.py|wom/cockpit/plateau_band.py]]
- [[80_Sources/wom/cockpit/s1_allocate.py|wom/cockpit/s1_allocate.py]]
- [[80_Sources/wom/cockpit/s1_view_model.py|wom/cockpit/s1_view_model.py]]
- [[80_Sources/wom/cockpit/s3_run.py|wom/cockpit/s3_run.py]]
- [[80_Sources/wom/cockpit/s3_view_model.py|wom/cockpit/s3_view_model.py]]
- [[80_Sources/wom/cockpit/state_header.py|wom/cockpit/state_header.py]]
- [[80_Sources/wom/planning_state/__init__.py|wom/planning_state/__init__.py]]

## 関連テスト候補（import文字列による分類）

網羅的なカバレッジ認定ではない。

- [[80_Sources/tests/test_gui_panel_invariants.py|tests/test_gui_panel_invariants.py]]
- [[80_Sources/tests/test_s1_view_model.py|tests/test_s1_view_model.py]]

[[00_Start/Home|機能マップへ戻る]]
