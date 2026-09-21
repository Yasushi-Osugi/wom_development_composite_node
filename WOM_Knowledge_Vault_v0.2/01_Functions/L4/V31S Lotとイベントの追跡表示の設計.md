---
function_id: V31S
level: 4
tags: [wom, function, L4]
---
# Lotとイベントの追跡表示の設計

**役割：** 計画結果の理由をlotの移動・必要週から調べる。

**状態：** 関連実装あり・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

Lot_ID、ノード、P/S/I/CO、イベント記録。

## 処理規則と責任境界

同一IDのノード別・週別履歴を比較する。部材と完成需要の対応を確認する。

## 出力と利用先

追跡情報と診断資料。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

遅れたkitの部材到着→組立→出荷までを確認できる。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

全ての測定情報がGUIに統合済みではない。probe出力による確認を含む。

## 設計・コードの根拠

- [wom/engine/event_timeline.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/event_timeline.py)
- [wom/engine/planning_debugger.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/planning_debugger.py)
- [tools/probe_composite_baseline.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tools/probe_composite_baseline.py)
- [docs/design/lot_id_traceability_and_coverage_views.md](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/design/lot_id_traceability_and_coverage_views.md)

## 業務思想・沿革の参考

- [記事01：グローバル・サプライチェーン計画と最適化のためのコンセプト検証 PoC:Proof of Concept](https://note.com/osuosu1123/n/n6e97b29049ca)
- [記事04：グローバル・サプライチェーン計画の数量編と金額編を統合する評価モデル](https://note.com/osuosu1123/n/n6be7137a8491)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/V31 Lotとイベントの追跡表示|Lotとイベントの追跡表示]]
