# Data Building

ネットワーク・需要・能力・原価・価格の前提を定義する。

**入出力:** CSV/Excel・モデル定義 → WOMInputs／SCTree／原価・価格規則

分類: オーナー合意の6分類。配置は知識ナビゲーション用であり、実装の単一責任や依存方向を保証しない。

## 最初に読む

- [[80_Sources/docs/design/scenario_modeling_principles.md|docs/design/scenario_modeling_principles.md]]
- [[80_Sources/docs/architecture/repository_map.md|docs/architecture/repository_map.md]]

## 機能トピック



## 実装モジュール

- [[80_Sources/wom/data/__init__.py|wom/data/__init__.py]]
- [[80_Sources/wom/data/loader.py|wom/data/loader.py]]
- [[80_Sources/wom/data/schema.py|wom/data/schema.py]]
- [[80_Sources/wom/engine/sc_tree_builder.py|wom/engine/sc_tree_builder.py]]
- [[80_Sources/wom/model/__init__.py|wom/model/__init__.py]]
- [[80_Sources/wom/model/lot_generator.py|wom/model/lot_generator.py]]
- [[80_Sources/wom/model/plan_node.py|wom/model/plan_node.py]]
- [[80_Sources/wom/model/sc_tree.py|wom/model/sc_tree.py]]

## 関連テスト候補（import文字列による分類）

網羅的なカバレッジ認定ではない。

- [[80_Sources/tests/test_backward_holiday_carryback.py|tests/test_backward_holiday_carryback.py]]
- [[80_Sources/tests/test_backward_supply_role.py|tests/test_backward_supply_role.py]]
- [[80_Sources/tests/test_bom_qty.py|tests/test_bom_qty.py]]
- [[80_Sources/tests/test_buffering_stock_optimizer_plugin.py|tests/test_buffering_stock_optimizer_plugin.py]]
- [[80_Sources/tests/test_capacity_soft.py|tests/test_capacity_soft.py]]
- [[80_Sources/tests/test_capacity_soft_backward.py|tests/test_capacity_soft_backward.py]]
- [[80_Sources/tests/test_composite_kitting_recovery.py|tests/test_composite_kitting_recovery.py]]
- [[80_Sources/tests/test_cpu_size_plan_wide.py|tests/test_cpu_size_plan_wide.py]]
- [[80_Sources/tests/test_decouple_optimizer.py|tests/test_decouple_optimizer.py]]
- [[80_Sources/tests/test_demand_envelope_soft.py|tests/test_demand_envelope_soft.py]]
- [[80_Sources/tests/test_init_stock_days_wiring.py|tests/test_init_stock_days_wiring.py]]
- [[80_Sources/tests/test_kitting_stage1.py|tests/test_kitting_stage1.py]]
- [[80_Sources/tests/test_operating_calendar.py|tests/test_operating_calendar.py]]
- [[80_Sources/tests/test_ppc_vertical_slice.py|tests/test_ppc_vertical_slice.py]]
- [[80_Sources/tests/test_push_pull_mode4_double_count.py|tests/test_push_pull_mode4_double_count.py]]
- [[80_Sources/tests/test_push_pull_mode4_supply_role.py|tests/test_push_pull_mode4_supply_role.py]]
- [[80_Sources/tests/test_shift_cap_soft.py|tests/test_shift_cap_soft.py]]
- [[80_Sources/tests/test_stage3a1_stockyard.py|tests/test_stage3a1_stockyard.py]]
- [[80_Sources/tests/test_stage3a2_kitting_gate.py|tests/test_stage3a2_kitting_gate.py]]
- [[80_Sources/tests/test_step10_hooks.py|tests/test_step10_hooks.py]]
- [[80_Sources/tests/test_step7_capacity.py|tests/test_step7_capacity.py]]
- [[80_Sources/tests/test_step8_push_pull.py|tests/test_step8_push_pull.py]]

[[00_Start/Home|機能マップへ戻る]]
