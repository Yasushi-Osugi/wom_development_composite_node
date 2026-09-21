# WOM Knowledge Vault v0.2

**業務・アプリケーション機能から読むWOM。**

v0.1で不足していた機能展開を中心に再構成した。コードファイルはグラフのノードにしない。

読む順序は **L0 全体 → L1 主要機能 → L2 概要機能 → L3 詳細機能 → L4 機能設計**。
L4から固定SHAのコード・設計書・テストへ外部リンクで進める。主要6機能の分解は編集案であり、正式設計の置換ではない。

[[01_Functions/L0/WOM WOM アプリケーション機能全体|WOM アプリケーション機能全体]]

| 主要機能 | 業務上の役割 |
|---|---|
| [[01_Functions/L1/D Data Building|Data Building]] | 業務前提とネットワークを作る |
| [[01_Functions/L1/A Optimization on Demand Allocation|Optimization on Demand Allocation]] | 限られた能力をどの需要に振り向けるか決める |
| [[01_Functions/L1/P Planning|Planning]] | 需要を週次の供給・在庫・出荷計画に変換する |
| [[01_Functions/L1/E Evaluation|Evaluation]] | 計画を数量・利益・資金の面から評価する |
| [[01_Functions/L1/V Presentation|Presentation]] | 構造と計画結果を人が理解できる形で示す |
| [[01_Functions/L1/M Management Cockpit|Management Cockpit]] | 前提変更から実行・評価までの判断を支える |

## 見方

- [[02_Maps/全体機能展開.canvas|全体機能展開：L0〜L2]]：階層の全体像。
- 02_Mapsの各機能Canvas：L1〜L4を左から右へ展開。ノートを開いて内容を読む。
- [[00_Start/業務フローとインターフェース]]：データの流れ。階層図の親子関係とは別。
- [[03_Context/記事と機能の対応表]]：12記事の背景と、現行機能への対応。
- [[03_Context/戦略視点と業務例]]：5視点、米・EV・多市場の利用例。
- [[03_Context/制約と未確定事項]]：実装範囲と注意点。
- [[00_Start/出典と更新方針]]：基準コミットと更新手順。
- [[00_Start/検証記録]]：リンク・構造・ZIPの検査範囲。

## 開き方

ZIPを新しいフォルダへ展開し、Obsidianの「保管庫としてフォルダを開く」で `WOM_Knowledge_Vault_v0.2` を選ぶ。まずこのREADMEを開く。

**v0.1へ上書き混在させない。** 古い80_Sources等が残ると、コード中心のグラフも残る。元のVaultは保持し、個人メモだけを必要に応じて移す。

グラフ初期設定は `path:01_Functions`。さらに `path:01_Functions -path:01_Functions/L4` で設計ノートを隠すと、詳細機能までの展開を見やすくできる。
全体グラフの配置はObsidianの自動配置であり、必ず木の形に整列するわけではない。階層を固定配置で見るにはCanvasを使う。

追加のコミュニティプラグインは不要。原文コード・原文記事・CSV・測定JSONは同梱せず、参照リンクで示す。機能ノートはオフラインで読めるが、原本を開くにはネット接続が必要。
