---
function_id: P12S
level: 4
tags: [wom, function, L4]
---
# DemandからSupplyへの計画準備の設計

**役割：** 変更しない需要要求と、供給計算結果を分ける。

**状態：** 関連実装あり・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

Demand PSI、初期在庫、計画期間。

## 処理規則と責任境界

需要の出荷要求をSupply計画へ準備する。Supply側の処理が元需要を破壊しない境界を維持する。

## 出力と利用先

Supply計算の初期状態。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

繰返し計算時、前回の在庫や未完了状態が意図せず混入しないことを確認する。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

Sが予定要求か実出荷かは経路依存。リスト名だけで実績と断定しない。

## 設計・コードの根拠

- [wom/engine/plan_copy.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/plan_copy.py)
- [wom/engine/forward_planner.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/forward_planner.py)
- [wom/model/plan_node.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/model/plan_node.py)

## 業務思想・沿革の参考

- [記事09：Weekly Operation Model（WOM）をPythonで実装した——週次サプライチェーン教材の最小構成](https://note.com/osuosu1123/n/n37e8b53c5b07)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/P12 DemandからSupplyへの計画準備|DemandからSupplyへの計画準備]]
