# Planning

選択された需要を週次PSIへ展開し、供給・能力・在庫・注文残を計算する。

**入出力:** 需要・SCTree・能力・カレンダー → demand/supply PSI・actual・診断

分類: オーナー合意の6分類。配置は知識ナビゲーション用であり、実装の単一責任や依存方向を保証しない。

## 最初に読む

- [[80_Sources/docs/architecture/planning_engine.md|docs/architecture/planning_engine.md]]
- [[80_Sources/docs/design/demand_anchored_lot.md|docs/design/demand_anchored_lot.md]]
- [[80_Sources/docs/design/kitting_list_assembly.md|docs/design/kitting_list_assembly.md]]

## 機能トピック

- [[20_Topics/01_PSI_Lot|PSI・Demand Anchored Lot]]
- [[20_Topics/02_Kitting|Composite Node・Kitting Gate]]
- [[20_Topics/03_Capacity|能力・カレンダー・週位置]]
- [[20_Topics/09_Buffer|Buffer・Push/Pull・TW]]
- [[20_Topics/10_Guardrails|開発規則・回帰テスト]]

## 実装モジュール

- [[80_Sources/wom/engine/backward_planner.py|wom/engine/backward_planner.py]]
- [[80_Sources/wom/engine/capacity_sealer.py|wom/engine/capacity_sealer.py]]
- [[80_Sources/wom/engine/forward_planner.py|wom/engine/forward_planner.py]]
- [[80_Sources/wom/engine/inventory.py|wom/engine/inventory.py]]
- [[80_Sources/wom/engine/plan_copy.py|wom/engine/plan_copy.py]]
- [[80_Sources/wom/engine/push_pull.py|wom/engine/push_pull.py]]
- [[80_Sources/wom/engine/simulator.py|wom/engine/simulator.py]]
- [[80_Sources/wom/engine/warmup.py|wom/engine/warmup.py]]
- [[80_Sources/wom/plugins/__init__.py|wom/plugins/__init__.py]]
- [[80_Sources/wom/plugins/buffering_stock_optimizer.py|wom/plugins/buffering_stock_optimizer.py]]
- [[80_Sources/wom/plugins/capacity_override.py|wom/plugins/capacity_override.py]]
- [[80_Sources/wom/plugins/demand_smoothing.py|wom/plugins/demand_smoothing.py]]

## 関連テスト候補（import文字列による分類）

網羅的なカバレッジ認定ではない。

- [[80_Sources/tests/test_allocation_cli.py|tests/test_allocation_cli.py]]
- [[80_Sources/tests/test_backward_holiday_carryback.py|tests/test_backward_holiday_carryback.py]]
- [[80_Sources/tests/test_backward_supply_role.py|tests/test_backward_supply_role.py]]
- [[80_Sources/tests/test_buffering_stock_optimizer_plugin.py|tests/test_buffering_stock_optimizer_plugin.py]]
- [[80_Sources/tests/test_capacity_soft.py|tests/test_capacity_soft.py]]
- [[80_Sources/tests/test_capacity_soft_backward.py|tests/test_capacity_soft_backward.py]]
- [[80_Sources/tests/test_composite_kitting_recovery.py|tests/test_composite_kitting_recovery.py]]
- [[80_Sources/tests/test_cpu_size_plan_wide.py|tests/test_cpu_size_plan_wide.py]]
- [[80_Sources/tests/test_decouple_optimizer.py|tests/test_decouple_optimizer.py]]
- [[80_Sources/tests/test_demand_envelope_soft.py|tests/test_demand_envelope_soft.py]]
- [[80_Sources/tests/test_golden.py|tests/test_golden.py]]
- [[80_Sources/tests/test_kitting_stage1.py|tests/test_kitting_stage1.py]]
- [[80_Sources/tests/test_operating_calendar.py|tests/test_operating_calendar.py]]
- [[80_Sources/tests/test_planning_state.py|tests/test_planning_state.py]]
- [[80_Sources/tests/test_ppc_vertical_slice.py|tests/test_ppc_vertical_slice.py]]
- [[80_Sources/tests/test_push_pull_mode4_supply_role.py|tests/test_push_pull_mode4_supply_role.py]]
- [[80_Sources/tests/test_shift_cap_soft.py|tests/test_shift_cap_soft.py]]
- [[80_Sources/tests/test_stage3a1_stockyard.py|tests/test_stage3a1_stockyard.py]]
- [[80_Sources/tests/test_stage3a2_kitting_gate.py|tests/test_stage3a2_kitting_gate.py]]
- [[80_Sources/tests/test_step10_hooks.py|tests/test_step10_hooks.py]]
- [[80_Sources/tests/test_step7_capacity.py|tests/test_step7_capacity.py]]
- [[80_Sources/tests/test_step8_push_pull.py|tests/test_step8_push_pull.py]]
- [[80_Sources/tests/test_warmup_materialize.py|tests/test_warmup_materialize.py]]

[[00_Start/Home|機能マップへ戻る]]
