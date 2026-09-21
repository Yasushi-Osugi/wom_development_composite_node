---
function_id: P32S
level: 4
tags: [wom, function, L4]
---
# Push・PullとBufferの計画制御の設計

**役割：** 押込み・需要引き・Buffer配置の違いを明確にする。

**状態：** 限定実装・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

plan_mode、decoupling点、需要週、LT、Buffer条件。

## 処理規則と責任境界

物理lotのForward移動と上流への指示を区別する。TW Mode4の前倒し計画と消費連動補充を同一視しない。

## 出力と利用先

供給配置・Buffer在庫・下流への供給。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

Bufferの週別P/I/Sと元需要IDを比較し、どの週のための前倒しか説明する。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

Kanban現場動作そのものは対象外。1週余裕だけで欠品ゼロを保証しない。TW1350の由来は未確認。

## 設計・コードの根拠

- [wom/engine/push_pull.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/push_pull.py)
- [docs/design/inbound_safety_stock.md](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/design/inbound_safety_stock.md)
- [docs/design/drafts/WOM_Composite_Node_Independent_Review_bc470b2.md](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/design/drafts/WOM_Composite_Node_Independent_Review_bc470b2.md)

## 業務思想・沿革の参考

- [記事01：グローバル・サプライチェーン計画と最適化のためのコンセプト検証 PoC:Proof of Concept](https://note.com/osuosu1123/n/n6e97b29049ca)
- [記事07：米のサプライチェーンを可視化する：5つの視座で描く未来戦略](https://note.com/osuosu1123/n/n89402e2c8ef8)
- [記事08：週次で動く世界＝経営とオペレーションをつなぐWeekly Operation Model（WOM）](https://note.com/osuosu1123/n/nc76451054220)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/P32 Push・PullとBufferの計画制御|Push・PullとBufferの計画制御]]
