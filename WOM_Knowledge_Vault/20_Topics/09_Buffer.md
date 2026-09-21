# Buffer・Push/Pull・TW

状態: **出典に基づく編集要約。正式設計変更ではない。**

物理lotの流れと補充指示の方向を区別する。Market PullとBuffer Pullは別の制御概念。TWのMode4を消費連動Kanban実装と認定しない。Buffer1350の業務由来は未確認として保持する。

機能: [[10_Functions/03_Planning|Planning]]

## 根拠・実装・検証

- [[80_Sources/wom/engine/push_pull.py|wom/engine/push_pull.py]]
- [[80_Sources/docs/design/inbound_safety_stock.md|docs/design/inbound_safety_stock.md]]
- [[80_Sources/requests/request_fix_mode4_supply_role_semantics.md|requests/request_fix_mode4_supply_role_semantics.md]]
- [[80_Sources/docs/design/drafts/WOM_Composite_Node_Independent_Review_bc470b2.md|docs/design/drafts/WOM_Composite_Node_Independent_Review_bc470b2.md]]
