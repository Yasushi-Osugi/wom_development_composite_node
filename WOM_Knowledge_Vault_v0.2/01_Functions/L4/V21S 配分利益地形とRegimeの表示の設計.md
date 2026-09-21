---
function_id: V21S
level: 4
tags: [wom, function, L4]
---
# 配分利益地形とRegimeの表示の設計

**役割：** 利益の高い領域や最適配分の切替を理解する。

**状態：** 関連実装あり・静的確認。以下は固定SHAの関連実装と設計資料を業務機能単位に再編集した設計読解ノート。新しいcore仕様の承認ではない。

## 入力と前提

配分候補・利益・条件軸・市場階層。

## 処理規則と責任境界

利益地形、順位、条件領域を用途別に示す。表示点の前提と探索粒度を保持する。

## 出力と利用先

配分図・条件別比較図。 上位の詳細機能へ戻り、その機能が属する業務領域から利用先を確認する。機能間の受渡し全体は「業務フローとインターフェース」に別記する。

## 確認例

同じ最良点でも、周辺が平坦か急峻かを判断材料にできる。

この例は仕様理解・今後の確認に使う観点であり、本Vault作成時に新しく実行したテスト結果ではない。

## 例外・限界・未確定事項

描画が示す最良点は評価モデル内の候補。経営上の唯一解ではない。

## 設計・コードの根拠

- [wom/cockpit/s1_allocate.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/cockpit/s1_allocate.py)
- [wom/allocation/regime_map.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/allocation/regime_map.py)
- [requests/Phase3_DesignMD_Visualization.md](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/requests/Phase3_DesignMD_Visualization.md)

## 業務思想・沿革の参考

- [記事12：AIでサプライチェーンを可視化（第８回：「利益の空白」を埋める）](https://note.com/osuosu1123/n/nde1d9b686a6e)

記事は業務背景の参考。現行実装の存在は上のコード・設計と区別して判断する。記事の短い要約と適用上の注意は「記事と機能の対応表」を参照。

## 上位機能

[[01_Functions/L3/V21 配分利益地形とRegimeの表示|配分利益地形とRegimeの表示]]
