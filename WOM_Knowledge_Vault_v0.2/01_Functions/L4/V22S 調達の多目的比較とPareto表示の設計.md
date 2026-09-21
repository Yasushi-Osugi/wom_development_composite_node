---
function_id: V22S
level: 4
tags: [wom, function, L4]
---
# 調達の多目的比較とPareto表示の設計

**役割：** 原価だけでは決められない調達候補の利害を説明する。

**状態：** 関連実装あり・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

調達候補、コスト、品質、LT等の分析軸。

## 処理規則と責任境界

B系統のMerit Order・Regime・Pareto分析を、A系統の市場配分利益分析と区別する。

## 出力と利用先

支配・非支配候補と比較図。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

低コストだがLTが長い案を、単一順位だけで排除せず比較できる。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

同名分析でも入力・目的・APIは異なる。自動で一つの最適化器に統合されてはいない。

## 設計・コードの根拠

- [wom/visualization/merit_order.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/visualization/merit_order.py)
- [wom/visualization/regime_map.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/visualization/regime_map.py)
- [wom/visualization/pareto_front.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/visualization/pareto_front.py)

## 業務思想・沿革の参考

- [記事12：AIでサプライチェーンを可視化（第８回：「利益の空白」を埋める）](https://note.com/osuosu1123/n/nde1d9b686a6e)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/V22 調達の多目的比較とPareto表示|調達の多目的比較とPareto表示]]
