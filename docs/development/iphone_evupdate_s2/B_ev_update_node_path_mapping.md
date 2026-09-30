# B：ev-thailand-2026_update　置場を入れる前後の対応表

対象は製品 EVmaker_Local の InBound（部材 → 工場）。EVmaker_Import と OutBound は変えていない。

## 1. ノードと経路

| 前（基準） | 後（今回） |
|---|---|
| `Platform_Unit_Assy`（leaf_in、LT 4、CN）→ `Factory_Local_TH` | `Platform_Unit_Assy`（leaf_in、LT 4、CN）→ **`Platform_Unit_Assy_Yard`（stockyard、LT 0、TH）** → `Factory_Local_TH` |
| `Motor_Unit_Assy`（leaf_in、LT 1、TH）→ `Factory_Local_TH` | `Motor_Unit_Assy`（leaf_in、LT 1、TH）→ **`Motor_Unit_Assy_Yard`（stockyard、LT 0、TH）** → `Factory_Local_TH` |
| `Factory_Local_TH`（mom、LT 2、ss_days 7） | 同じ |

`sc_tree_master.csv` の差分は、置場 2 行の追加と、部材 2 行の `parent_node` の付け替えだけ。

## 2. 意味を保っていること

| 項目 | 前 | 後 | 確かめ方 |
|---|---|---|---|
| 経路の LT の合計（部材 → 工場） | プラットフォーム 4、モーター 1 | 4＋0、1＋0（同じ） | `tests/test_ev_update_kitting.py::test_tree_uses_the_standard_stockyard_layout` |
| 部材の出荷週（Backward の配置） | — | 前と同じ（部材の P・実出荷の合計 52,700 は同じ） | `B_ev_update_psi_nodes.csv` |
| 休業・能力 | `holiday_calendar.csv`：Factory_Local_TH の 2026-W32・2027-W32 は能力 150 | 同じ（ファイルは変えていない） | — |
| 需要 | 63,240（Local 52,700＋Import 10,540） | 同じ | 表 2 |
| BOM の意味 | 2 部材とも `supply_role` は空（＝assembly）、`bom_qty` は空（＝1） | 同じ。置場も `supply_role` は空 | — |
| 原価・能力の二重計上 | — | 無い。置場は `sc_tree_master.csv` だけにあり、原価・能力・地図の行を持たない | 下の表 |

## 3. 参照する CSV と、置場の扱い

既存の置場モデル（ev-europe-2026、bom-test-2026）と同じ規則：置場は `sc_tree_master.csv` だけに書く。

| CSV | 部材・工場の行 | 置場の行 | 理由 |
|---|---|---|---|
| `sc_tree_master.csv` | あり（部材の親を置場に変更） | **追加（2 行）** | 構造の定義 |
| `capacity_plan.csv` | 部材 2・工場（変えていない） | なし | 置場は能力を持たない（払い出しは組立の能力で決まる） |
| `node_cost_master.csv` | 部材 2・工場（変えていない） | なし | 置場に原価を持たせると二重計上になる |
| `ppc_supplier_cost.csv` | 部材 2・工場（変えていない） | なし | 同上。PPC は leaf_in を供給者として数える（置場は数えない） |
| `ppc_node_profit_zone.csv` | 部材 2・工場（変えていない） | なし | 同上 |
| `ppc_node_cost_rule.csv` | 工場（変えていない） | なし | 同上 |
| `node_master.csv`（地図） | 部材 2・工場（変えていない） | なし | ev-europe・bom-test と同じ。地図には置場の点を出さない |
| `lane_assignment.csv`・`holiday_calendar.csv`・`push_config.csv` | 変えていない | なし | — |

PPC の結果（売上 3,191.2 億 THB、原価 1,388.3 億 THB、粗利率 56.50%）は、前後で同じ。

## 4. 置場と Kitting Gate の動き（既存のエンジン。今回コードは変えていない）

- 組立ノードの子がすべて置場のとき、`ForwardPlanner._process_assembly_with_yards` が働く。
- 週ごとに、各置場の在庫（前週の残り＋今週の到着）の Lot_ID の**共通部分**を取り、工場の要求にある ID だけを払い出す。
- 払い出した ID は、各置場から 1 件ずつ減り、工場の P に **1 回だけ**入る。
- 共通部分に無い ID（片方の部材しか届いていない）は、届いている部材が置場の在庫に残り、工場の P には入らない。工場の出荷要求は CO に回る。
- 組立の能力（`processing_limit`）を超える分は、部材を消費する前に待たせる（`kitting_capacity_deferred`）。

## 5. 前後の数量（identity、EVmaker_Local）

| ノード | 前：P のべ／異なる ID | 前：実出荷／期末 I | 後：P のべ／異なる ID | 後：実出荷／期末 I |
|---|---|---|---|---|
| Platform_Unit_Assy | 52,700／52,700 | 52,700／0 | 52,700／52,700 | 52,700／0 |
| Motor_Unit_Assy | 52,700／52,700 | 52,700／0 | 52,700／52,700 | 52,700／0 |
| Platform_Unit_Assy_Yard | — | — | 52,700／52,700 | 52,700／0 |
| Motor_Unit_Assy_Yard | — | — | 52,700／52,700 | 52,700／0 |
| Factory_Local_TH | **105,400**／52,700 | 52,700／**300** | **52,700**／52,700 | 52,700／**0** |

- 前：工場の P に同じ ID が 2 件ずつ入る（のべ 105,400）。保存差 105,400 − 52,700 − 300 ＝ 52,400。
- 前の期末 I の 300 件は、重複の片方が残ったもの（のべ 13,950 lot 週の、実在しない在庫）。
- 後：工場の P は完成品の数（52,700）。保存差 0。
