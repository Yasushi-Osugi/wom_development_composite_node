---
function_id: E21S
level: 4
tags: [wom, function, L4]
---
# E2E原価と移転価格の計算の設計

**役割：** 調達から販売までの費用構造を可視化する。

**状態：** 関連実装あり・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

PPC規則、ノード・経路、供給数量、通貨。

## 処理規則と責任境界

調達費・加工費・物流等を積み上げ、移転価格を決めて関税等へ渡す。費用積上げと内部価格を区別する。

## 出力と利用先

lot別原価、移転価格、金額イベント。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

同一lotの原料・加工・物流を追い、費用の二重計上を検討できる。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

ppc_transferの冒頭はcost_plusのみと記すが、コードにはfixedもある。文章とコードの差を残す。

## 設計・コードの根拠

- [wom/ppc/ppc_forward.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/ppc/ppc_forward.py)
- [wom/ppc/ppc_transfer.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/ppc/ppc_transfer.py)
- [wom/ppc/ppc_rules.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/ppc/ppc_rules.py)

## 業務思想・沿革の参考

- [記事02：サプライチェーン計画の評価機能（ネットワーク構造と製品別原価計算）](https://note.com/osuosu1123/n/nf7c4fd03b3c9)
- [記事04：グローバル・サプライチェーン計画の数量編と金額編を統合する評価モデル](https://note.com/osuosu1123/n/n6be7137a8491)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/E21 E2E原価と移転価格の計算|E2E原価と移転価格の計算]]
