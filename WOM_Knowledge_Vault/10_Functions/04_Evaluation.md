# Evaluation

物量の実現性と金額上の結果を区別して評価する。

**入出力:** PSI・価格・原価・為替・関税 → PPC台帳／利益／KPI／差異分解

分類: オーナー合意の6分類。配置は知識ナビゲーション用であり、実装の単一責任や依存方向を保証しない。

## 最初に読む

- [[80_Sources/docs/design/psi_ppc_separation.md|docs/design/psi_ppc_separation.md]]
- [[80_Sources/docs/architecture/ppc_engine.md|docs/architecture/ppc_engine.md]]
- [[80_Sources/requests/Phase7a_Addendum_to_CodeKun.md|requests/Phase7a_Addendum_to_CodeKun.md]]

## 機能トピック

- [[20_Topics/06_Cost_Price|Cost Master・Price Simulation]]
- [[20_Topics/07_PSI_PPC|PSIとPPC・評価差異]]

## 実装モジュール

- [[80_Sources/wom/engine/landed_cost.py|wom/engine/landed_cost.py]]
- [[80_Sources/wom/engine/management.py|wom/engine/management.py]]
- [[80_Sources/wom/engine/money.py|wom/engine/money.py]]
- [[80_Sources/wom/engine/strategic_kpi.py|wom/engine/strategic_kpi.py]]
- [[80_Sources/wom/ppc/__init__.py|wom/ppc/__init__.py]]
- [[80_Sources/wom/ppc/__main__.py|wom/ppc/__main__.py]]
- [[80_Sources/wom/ppc/ppc_backward.py|wom/ppc/ppc_backward.py]]
- [[80_Sources/wom/ppc/ppc_cockpit.py|wom/ppc/ppc_cockpit.py]]
- [[80_Sources/wom/ppc/ppc_cockpit_app.py|wom/ppc/ppc_cockpit_app.py]]
- [[80_Sources/wom/ppc/ppc_engine.py|wom/ppc/ppc_engine.py]]
- [[80_Sources/wom/ppc/ppc_export.py|wom/ppc/ppc_export.py]]
- [[80_Sources/wom/ppc/ppc_forward.py|wom/ppc/ppc_forward.py]]
- [[80_Sources/wom/ppc/ppc_fx.py|wom/ppc/ppc_fx.py]]
- [[80_Sources/wom/ppc/ppc_kpi.py|wom/ppc/ppc_kpi.py]]
- [[80_Sources/wom/ppc/ppc_models.py|wom/ppc/ppc_models.py]]
- [[80_Sources/wom/ppc/ppc_profit_zone.py|wom/ppc/ppc_profit_zone.py]]
- [[80_Sources/wom/ppc/ppc_psi_bridge.py|wom/ppc/ppc_psi_bridge.py]]
- [[80_Sources/wom/ppc/ppc_reconcile.py|wom/ppc/ppc_reconcile.py]]
- [[80_Sources/wom/ppc/ppc_rules.py|wom/ppc/ppc_rules.py]]
- [[80_Sources/wom/ppc/ppc_runner.py|wom/ppc/ppc_runner.py]]
- [[80_Sources/wom/ppc/ppc_tariff.py|wom/ppc/ppc_tariff.py]]
- [[80_Sources/wom/ppc/ppc_transfer.py|wom/ppc/ppc_transfer.py]]

## 関連テスト候補（import文字列による分類）

網羅的なカバレッジ認定ではない。

- [[80_Sources/tests/test_ppc_bom_qty.py|tests/test_ppc_bom_qty.py]]
- [[80_Sources/tests/test_ppc_multi_supplier.py|tests/test_ppc_multi_supplier.py]]
- [[80_Sources/tests/test_ppc_vertical_slice.py|tests/test_ppc_vertical_slice.py]]

[[00_Start/Home|機能マップへ戻る]]
