# Cost Master・Price Simulation

状態: **出典に基づく編集要約。正式設計変更ではない。**

入力定義と原価伝播・金額評価を分ける。supplier/node/edge原価、販売価格、関税、FX、移転価格をPPC経路で確認する。A系統のシナリオ原料価格とPPC原料価格の整合は別途検査する。

機能: [[10_Functions/04_Evaluation|Evaluation]]

## 根拠・実装・検証

- [[80_Sources/wom/allocation/cost_block.py|wom/allocation/cost_block.py]]
- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]
- [[80_Sources/wom/ppc/ppc_rules.py|wom/ppc/ppc_rules.py]]
- [[80_Sources/wom/ppc/ppc_transfer.py|wom/ppc/ppc_transfer.py]]
- [[80_Sources/requests/Phase8-1b_Addendum_MaterialPrice_to_CodeKun.md|requests/Phase8-1b_Addendum_MaterialPrice_to_CodeKun.md]]
- [[80_Sources/tests/test_allocation_material_invariant.py|tests/test_allocation_material_invariant.py]]
