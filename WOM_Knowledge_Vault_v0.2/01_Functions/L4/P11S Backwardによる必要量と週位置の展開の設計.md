---
function_id: P11S
level: 4
tags: [wom, function, L4]
---
# Backwardによる必要量と週位置の展開の設計

**役割：** 顧客必要週から上流の必要な供給時期を導く。

**状態：** 関連実装あり・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

Demand S、経路LT、能力、休日。

## 処理規則と責任境界

必要量を上流へ展開し、利用可能な週への配置を検討する。需要アンカーを保存し、前倒しと必要週を区別する。

## 出力と利用先

Demand Layerと上流の必要量。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

閉鎖週の要求について、その前後の配置と元の必要週を追跡できる。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

Backwardで配置できたことは、Forwardで全部材が届く保証ではない。

## 設計・コードの根拠

- [wom/engine/backward_planner.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/backward_planner.py)
- [docs/design/demand_anchored_lot.md](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/design/demand_anchored_lot.md)

## 業務思想・沿革の参考

- [記事01：グローバル・サプライチェーン計画と最適化のためのコンセプト検証 PoC:Proof of Concept](https://note.com/osuosu1123/n/n6e97b29049ca)
- [記事03：サプライチェーン計画ツール：Global Weekly PSI Plannerのご紹介（関税シミュレーションなど）](https://note.com/osuosu1123/n/nf88257a36788)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/P11 Backwardによる必要量と週位置の展開|Backwardによる必要量と週位置の展開]]
