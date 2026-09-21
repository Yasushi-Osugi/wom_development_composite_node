---
function_id: D31S
level: 4
tags: [wom, function, L4]
---
# Cost Masterと価格前提の設定の設計

**役割：** 費用構造と市場価格を、物量計画とは独立した評価前提として管理する。

**状態：** 関連実装あり・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

supplier/node/edge費用、販売価格、移転価格規則、通貨。

## 処理規則と責任境界

費目・単位・適用ノード・製品・期間を区別する。原価積上げと価格仮定を分け、会計値と配分用CostBlockの対応を確認する。

## 出力と利用先

PPC規則と配分評価用の原価前提。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

原料価格だけを変えたケースで、その値が配分計算とPPCにどう渡るか追える。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

全サンプルが滞留期間別保有費を持つわけではない。原価行の欠落だけで倉庫と断定しない。

## 設計・コードの根拠

- [wom/ppc/ppc_rules.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/ppc/ppc_rules.py)
- [wom/allocation/cost_block.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/allocation/cost_block.py)
- [tests/test_allocation_material_invariant.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tests/test_allocation_material_invariant.py)

## 業務思想・沿革の参考

- [記事02：サプライチェーン計画の評価機能（ネットワーク構造と製品別原価計算）](https://note.com/osuosu1123/n/nf7c4fd03b3c9)
- [記事04：グローバル・サプライチェーン計画の数量編と金額編を統合する評価モデル](https://note.com/osuosu1123/n/n6be7137a8491)
- [記事05：価格=価値X制約、コスト=構造、利益=設計の成果](https://note.com/osuosu1123/n/nef9e485ce0be)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/D31 Cost Masterと価格前提の設定|Cost Masterと価格前提の設定]]
