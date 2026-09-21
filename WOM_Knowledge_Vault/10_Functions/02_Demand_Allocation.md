# Optimization on Demand Allocation

限られた供給能力を市場・需要に配分し、利益構造と採用案を比較する。

**入出力:** 需要上限・能力・CostBlock・Scenario → 配分候補／採用配分／Planning State

分類: オーナー合意の6分類。配置は知識ナビゲーション用であり、実装の単一責任や依存方向を保証しない。

## 最初に読む

- [[80_Sources/docs/design/ask_global_allocation_spec.md|docs/design/ask_global_allocation_spec.md]]
- [[80_Sources/requests/Phase6_DesignMD_NMarketHierarchy.md|requests/Phase6_DesignMD_NMarketHierarchy.md]]
- [[80_Sources/requests/Phase6-5_RequestLetter_AllocationLeftovers_to_CodeKun.md|requests/Phase6-5_RequestLetter_AllocationLeftovers_to_CodeKun.md]]

## 機能トピック

- [[20_Topics/04_Allocation_AB|需要配分A系統と調達分析B系統]]
- [[20_Topics/05_Handoff|配分から週次PSIへのハンドオフ]]

## 実装モジュール

- [[80_Sources/wom/allocation/__init__.py|wom/allocation/__init__.py]]
- [[80_Sources/wom/allocation/analytics.py|wom/allocation/analytics.py]]
- [[80_Sources/wom/allocation/cost_block.py|wom/allocation/cost_block.py]]
- [[80_Sources/wom/allocation/grid.py|wom/allocation/grid.py]]
- [[80_Sources/wom/allocation/handoff.py|wom/allocation/handoff.py]]
- [[80_Sources/wom/allocation/hierarchical_simplex.py|wom/allocation/hierarchical_simplex.py]]
- [[80_Sources/wom/allocation/merit_order.py|wom/allocation/merit_order.py]]
- [[80_Sources/wom/allocation/regime_map.py|wom/allocation/regime_map.py]]
- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]

## 関連テスト候補（import文字列による分類）

網羅的なカバレッジ認定ではない。

- [[80_Sources/tests/test_allocation_analytics.py|tests/test_allocation_analytics.py]]
- [[80_Sources/tests/test_allocation_cost_block.py|tests/test_allocation_cost_block.py]]
- [[80_Sources/tests/test_allocation_grid.py|tests/test_allocation_grid.py]]
- [[80_Sources/tests/test_allocation_hierarchical.py|tests/test_allocation_hierarchical.py]]
- [[80_Sources/tests/test_allocation_material_invariant.py|tests/test_allocation_material_invariant.py]]
- [[80_Sources/tests/test_allocation_merit_order.py|tests/test_allocation_merit_order.py]]
- [[80_Sources/tests/test_allocation_nmarket.py|tests/test_allocation_nmarket.py]]
- [[80_Sources/tests/test_allocation_nonconcave.py|tests/test_allocation_nonconcave.py]]
- [[80_Sources/tests/test_allocation_plot.py|tests/test_allocation_plot.py]]
- [[80_Sources/tests/test_allocation_regime_map.py|tests/test_allocation_regime_map.py]]
- [[80_Sources/tests/test_allocation_transmission.py|tests/test_allocation_transmission.py]]
- [[80_Sources/tests/test_planning_state.py|tests/test_planning_state.py]]
- [[80_Sources/tests/test_s1_view_model.py|tests/test_s1_view_model.py]]

[[00_Start/Home|機能マップへ戻る]]
