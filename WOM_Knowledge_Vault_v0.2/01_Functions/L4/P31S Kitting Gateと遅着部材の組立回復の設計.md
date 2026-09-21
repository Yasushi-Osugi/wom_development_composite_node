---
function_id: P31S
level: 4
tags: [wom, function, L4]
---
# Kitting Gateと遅着部材の組立回復の設計

**役割：** 部材が揃った需要だけを組み立て、遅着分を後続週で回復する。

**状態：** 限定実装・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

部材Yard在庫、需要ID、未完了kit、組立能力、完成品在庫。

## 処理規則と責任境界

通常pull・全直下子stockyardの対象で、未完了kitを保持する。部材集合と能力を確認して払出・完成を対応させる。既存完成品で満たせるIDを再生産しない。

## 出力と利用先

部材払出とAssembly P、未完了kit、完成品出荷とCO。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

一部材を1週遅らせ、到着後の組立・CO解消と部材保存を確認する。能力不足時に部材だけが消費されない。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

限定実装。混在子構造・加工中WIP・任意BOM数量・汎用Compositeエディタの完成を意味しない。

## 設計・コードの根拠

- [wom/engine/forward_planner.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/forward_planner.py)
- [tests/test_composite_kitting_recovery.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tests/test_composite_kitting_recovery.py)
- [docs/development/composite_kitting_implementation_2026-09-20.md](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/development/composite_kitting_implementation_2026-09-20.md)
- [docs/design/drafts/WOM_Composite_Node_Design_Draft_v0.1.md](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/design/drafts/WOM_Composite_Node_Design_Draft_v0.1.md)

## 業務思想・沿革の参考

- [記事09：Weekly Operation Model（WOM）をPythonで実装した——週次サプライチェーン教材の最小構成](https://note.com/osuosu1123/n/n37e8b53c5b07)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/P31 Kitting Gateと遅着部材の組立回復|Kitting Gateと遅着部材の組立回復]]
