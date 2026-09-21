# 配分から週次PSIへのハンドオフ

状態: **出典に基づく編集要約。正式設計変更ではない。**

write_demand_for_allocationは市場配分を地域・週へ展開し、最大剰余法で整数lot合計を保つ。元需要ゼロ週を維持し、uom対象外の地域は素通しする。Planning Stateは採用した案の評価と最適利益水準を区別する。

機能: [[10_Functions/02_Demand_Allocation|Optimization on Demand Allocation]]

## 根拠・実装・検証

- [[80_Sources/wom/allocation/handoff.py|wom/allocation/handoff.py]]
- [[80_Sources/wom/planning_state/__init__.py|wom/planning_state/__init__.py]]
- [[80_Sources/tools/run_planning_loop.py|tools/run_planning_loop.py]]
- [[80_Sources/requests/Phase7_RequestLetter_to_CodeKun.md|requests/Phase7_RequestLetter_to_CodeKun.md]]
- [[80_Sources/tests/test_planning_state.py|tests/test_planning_state.py]]
