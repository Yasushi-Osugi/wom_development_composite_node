---
function_id: V12S
level: 4
tags: [wom, function, L4]
---
# 週次PSIと能力の表示の設計

**役割：** 週ごとの供給・出荷・在庫・制約を読み取る。

**状態：** 関連実装あり・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

週次PSI、能力系列、shortfall、選択ノード。

## 処理規則と責任境界

凡例にquantityの意味を示す。S3のpushでは実出荷に対応する系列を使い、需要階段Sと区別する。

## 出力と利用先

PSIチャート・リスト・能力比較。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

閉鎖週のPが非ゼロでも実出荷ゼロなら、その違いを説明できる。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

従来PSI Chartと新S3は同一画面ではない。全図で同じ系列定義と決めない。

## 設計・コードの根拠

- [wom/gui/app.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/gui/app.py)
- [wom/cockpit/s3_run.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/cockpit/s3_run.py)
- [wom/cockpit/s3_view_model.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/cockpit/s3_view_model.py)

## 業務思想・沿革の参考

- [記事03：サプライチェーン計画ツール：Global Weekly PSI Plannerのご紹介（関税シミュレーションなど）](https://note.com/osuosu1123/n/nf88257a36788)
- [記事09：Weekly Operation Model（WOM）をPythonで実装した——週次サプライチェーン教材の最小構成](https://note.com/osuosu1123/n/n37e8b53c5b07)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/V12 週次PSIと能力の表示|週次PSIと能力の表示]]
