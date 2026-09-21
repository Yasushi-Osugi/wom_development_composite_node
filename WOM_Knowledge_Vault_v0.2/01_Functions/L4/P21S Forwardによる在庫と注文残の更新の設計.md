---
function_id: P21S
level: 4
tags: [wom, function, L4]
---
# Forwardによる在庫と注文残の更新の設計

**役割：** 供給が足りない週も出荷要求を保持し、後日充足する。

**状態：** 関連実装あり・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

週P、期首I、当週S、前週からのCO。

## 処理規則と責任境界

利用可能な完成供給を当週要求・繰越要求へ引当てる。未履行要求をCOとして保持し、未出荷の物理供給をIとして保持する。

## 出力と利用先

actual出荷、週末I、CO。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

必要週に未完成の需要が翌週完成したら、COが解消し、同一需要が重複出荷されない。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

COは物理lotの置き場所ではない。IとCOを足して物量保存を判定しない。

## 設計・コードの根拠

- [wom/engine/forward_planner.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/forward_planner.py)
- [docs/design/demand_anchored_lot.md](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/design/demand_anchored_lot.md)
- [tests/test_composite_kitting_recovery.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tests/test_composite_kitting_recovery.py)

## 業務思想・沿革の参考

- [記事04：グローバル・サプライチェーン計画の数量編と金額編を統合する評価モデル](https://note.com/osuosu1123/n/n6be7137a8491)
- [記事09：Weekly Operation Model（WOM）をPythonで実装した——週次サプライチェーン教材の最小構成](https://note.com/osuosu1123/n/n37e8b53c5b07)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/P21 Forwardによる在庫と注文残の更新|Forwardによる在庫と注文残の更新]]
