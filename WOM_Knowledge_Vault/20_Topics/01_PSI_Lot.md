# PSI・Demand Anchored Lot

状態: **出典に基づく編集要約。正式設計変更ではない。**

S/CO/I/Pの順で週次リストを持つ。COは未履行要求であり物理在庫ではない。予定Sとactualを区別し、Pをノードの意味を確認せず一律に生産量と読まない。

機能: [[10_Functions/03_Planning|Planning]]

## 根拠・実装・検証

- [[80_Sources/docs/design/demand_anchored_lot.md|docs/design/demand_anchored_lot.md]]
- [[80_Sources/wom/model/plan_node.py|wom/model/plan_node.py]]
- [[80_Sources/wom/engine/plan_copy.py|wom/engine/plan_copy.py]]
