# 能力・カレンダー・週位置

状態: **出典に基づく編集要約。正式設計変更ではない。**

Backwardの配置とForwardの供給制約を区別する。現行のcap=0と閉鎖を混同しない。S3の比較系列変更は表示改善であり、全ノードのP/S/I別capモデル導入ではない。

機能: [[10_Functions/03_Planning|Planning]]

## 根拠・実装・検証

- [[80_Sources/wom/engine/capacity_sealer.py|wom/engine/capacity_sealer.py]]
- [[80_Sources/wom/engine/backward_planner.py|wom/engine/backward_planner.py]]
- [[80_Sources/docs/design/holiday_calendar_and_capacity_semantics.md|docs/design/holiday_calendar_and_capacity_semantics.md]]
- [[80_Sources/requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md|requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md]]
