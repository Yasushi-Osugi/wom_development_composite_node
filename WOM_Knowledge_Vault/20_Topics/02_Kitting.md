# Composite Node・Kitting Gate

状態: **出典に基づく編集要約。正式設計変更ではない。**

実験版7d6c7d7では通常pull・全直下子stockyardに限定して未完了kitを持ち越す。能力確認後に部材を払い出す。同じ需要IDの各部材1 setを完成需要1件に対応させる。公開版4260494にはこの修正は含まれない。

機能: [[10_Functions/03_Planning|Planning]]

## 根拠・実装・検証

- [[80_Sources/requests/RequestLetter_Composite_Kitting_Backlog_v1.md|requests/RequestLetter_Composite_Kitting_Backlog_v1.md]]
- [[80_Sources/wom/engine/forward_planner.py|wom/engine/forward_planner.py]]
- [[80_Sources/tests/test_composite_kitting_recovery.py|tests/test_composite_kitting_recovery.py]]
- [[80_Sources/docs/development/composite_kitting_implementation_2026-09-20.md|docs/development/composite_kitting_implementation_2026-09-20.md]]
- [[80_Sources/docs/design/drafts/WOM_Composite_Node_Design_Draft_v0.1.md|docs/design/drafts/WOM_Composite_Node_Design_Draft_v0.1.md]]
