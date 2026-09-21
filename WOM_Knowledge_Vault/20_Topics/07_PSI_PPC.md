# PSIとPPC・評価差異

状態: **出典に基づく編集要約。正式設計変更ではない。**

物量上の実現性と金額上の評価は別。PPC bridgeがどのノードのどのSを入力するかを確認する。A系統とPPCの利益差をそのまま実行差異と呼ばず、数量・為替前提・残差に分ける。在庫期間や中間未充足への反応は残課題。

機能: [[10_Functions/04_Evaluation|Evaluation]]

## 根拠・実装・検証

- [[80_Sources/docs/design/psi_ppc_separation.md|docs/design/psi_ppc_separation.md]]
- [[80_Sources/wom/ppc/ppc_psi_bridge.py|wom/ppc/ppc_psi_bridge.py]]
- [[80_Sources/wom/planning_state/__init__.py|wom/planning_state/__init__.py]]
- [[80_Sources/requests/Phase7a_Addendum_to_CodeKun.md|requests/Phase7a_Addendum_to_CodeKun.md]]
- [[80_Sources/requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md|requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md]]
