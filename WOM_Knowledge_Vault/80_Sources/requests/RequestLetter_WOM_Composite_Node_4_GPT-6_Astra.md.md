---
tags: [wom, source]
---
# requests/RequestLetter_WOM_Composite_Node_4_GPT-6_Astra.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/requests/RequestLetter_WOM_Composite_Node_4_GPT-6_Astra.md) · [原文テキスト](../../90_Raw/requests/RequestLetter_WOM_Composite_Node_4_GPT-6_Astra.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Request Letter：WOM Composite Node基本設計に向けた独立レビュー
- 1. 最初にお願いしたいこと
- 2. 対象と基準点
- 3. 背景
- 4. 検証してほしい仮説
- 5. 調査内容
- A. PSIの意味と時間軸
- B. SmartPhone Assembly
- C. TW Buffering
- D. CapacityとLot保存
- 6. 成果物
- 7. 作業上の制約
- 8. 最も重視すること

## 関連する知識源

- [[80_Sources/docs/design/drafts/WOM_Composite_Node_Architecture.md|docs/design/drafts/WOM_Composite_Node_Architecture.md]]
- [[80_Sources/requests/Phase8-3c-2_RequestLetter_CapHardSealing_to_CodeKun.md|requests/Phase8-3c-2_RequestLetter_CapHardSealing_to_CodeKun.md]]
- [[80_Sources/requests/Phase8-3c-3_RequestLetter_Option4_to_CodeKun.md|requests/Phase8-3c-3_RequestLetter_Option4_to_CodeKun.md]]
- [[80_Sources/requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md|requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Request Letter：WOM Composite Node基本設計に向けた独立レビュー

宛先：GPT-6 Astra君
依頼者：大杉（WOM Project Owner）
種別：設計前提の検証・既存実装の調査
実装：本依頼では行わない

## 1. 最初にお願いしたいこと

Astra君、WOM Projectへの最初の参加として、Composite Nodeに関する設計ドラフトを、既存実装と照合してレビューしてください。

今回の問いは、

**「この設計を実装できますか」ではなく、「この設計のどこが既存WOMの実態と一致し、どこが仮説・誤解・不足になっていますか」です。**

ドラフトを正しいものとして扱う必要はありません。コードの現状も、業務上の正しさを自動的に保証するものではありません。両方を検証対象としてください。

## 2. 対象と基準点

リポジトリ：
https://github.com/Yasushi-Osugi/wom_v1r0m0

対象ブランチ：`wom-v1r4m0`

今回のレビュー基準コミット：`bc470b2`

対象ドラフト：

`docs/design/drafts/WOM_Composite_Node_Architecture.md`

関連する経緯：

* `requests/Phase8-3c-2_RequestLetter_CapHardSealing_to_CodeKun.md`
* `requests/Phase8-3c-3_RequestLetter_Option4_to_CodeKun.md`
* `requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md`

最初に`AGENTS.md`と関連する設計索引を読み、作業上の制約を確認してください。

レビュー開始時に、実際に参照したコミットの完全なSHAを報告してください。ブランチが先へ進んでいる場合も、基準コミットと最新状態を混ぜないでください。

過去のRequest Letterには、後続の検証で訂正された説明が含まれます。記述の強さや文書名だけで正典と判断せず、訂正の履歴を確認してください。

## 3. 背景

WOMは、週次のP/S/I/COのLot List操作を基礎とするサプライチェーン計画・シミュレーションツールです。

最近、TWのBufferノードや工場ノードの扱いを検討する中で、次の概念が十分に分離されていない可能性が見えてきました。

* 施設としての工場・倉庫・販売拠点
* PSIの各Lot Listが表す状態
* 物理的なLot移動
* 下流から上流への要求・補充指示
* Backward／Forwardの計算方向
* Push／Pullなどの制御方式
* Capacityが拘束する操作と週

私の構想では、工場は例えば次の二つのPSIを接続して表現できます。

| PSI            | P     | I       | S           |
| -------------- | ----- | ------- | ----------- |
| Stocker PSI    | 部材受入れ | 部材・仕掛在庫 | Picking／払出し |
| Production PSI | 生産完了  | 完成品在庫   | 出荷          |

SmartPhone組立のStocker／Picking／Kitting／Assembly、およびTW半導体のBufferingには、このような複合構造の原型があると考えています。ただし、具体的なモデル・関数との対応は実装から確認してください。

## 4. 検証してほしい仮説

以下は議論の出発点であり、証明済みの仕様ではありません。

1. 通常の供給経路では、物理Lotは上流から下流へ移動する。
2. 補充・投入要求は、下流から上流へ伝播する。
3. OutboundのMarket PullとInboundのBuffer Pullは、区別すべき制御ループである。
4. DBRとKanbanは共通の制御枠組みで整理できる可能性がある。ただし、両者を単純にBuffer Pullの派生として扱ってよいかは検証が必要である。
5. FactoryやBufferは、複数PSIとEvent／ControllerからなるComposite Nodeとして表現できる可能性がある。

各仮説について、一致する実装、反例、適用範囲、未確認事項を示してください。新しい構造の導入より、既存概念の文書化だけで解決できる可能性も検討してください。

## 5. 調査内容

### A. PSIの意味と時間軸

参照事例ごとに、次を確認してください。

* P/S/I/COへ書き込む関数と処理順序
* 予定量と実移動量の違い
* 需要週、払出週、入庫週、生産開始週、完成週の関係
* Lot IDが物理的実体を表す場合と、計画上の要求を表す場合
* Demand側とSupply側で同じLot IDが現れる意味

特に、`S`と実出荷量が常に同じとは仮定しないでください。

### B. SmartPhone Assembly

該当モデルを特定し、Stocker、Picking、Kitting、Assemblyの接続を追跡してください。

* 部材はどこで待機するか
* 何が払出し・組立を許可するか
* 部材Lotと完成品Lotの対応をどう記録するか
* BOM数量とリードタイムをどこで適用するか
* 二つのPSIによるFactory表現と、どこが一致・不一致か

### C. TW Buffering

`Buffer_Chip_TW`を中心に、次を確認してください。

* 入庫と払出しを誰が決めるか
* 後工程から上流への指示が存在するか
* 指示の発生条件、数量、時期、宛先
* 実際にはどの方式が実装されているか
* `node_type=mom`とdecoupling設定の役割
* `cap_hard=1350`の由来と用途

名前にBufferがあること、原価行がないこと、他ノードと能力値が一致することだけで、業務上の意味を断定しないでください。由来が分からない場合は「未確認」と報告してください。

### D. CapacityとLot保存

Capacityについて、次を分けてください。

* 現行コードが制限している対象
* モデルデータが意図していると読める対象
* ドラフトが提案している対象

また、在庫Iと未充足COについて、物理状態と需要状態の関係を確認してください。

Lot Listの合計が変わったことだけで、物理Lotの消失や滞留期間を断定しないでください。数量、lot-週、ノード単体、チェーン全体、予定値、実績値を明示してください。

## 6. 成果物

次の構成で、レビュー結果を報告してください。

1. **総括**
   ドラフトのうち維持できる部分、修正すべき部分、判断保留の部分。

2. **主張と証拠の対応表**
   各主張を「コードで確認」「実測で確認」「業務上の仮説」「矛盾あり」「未確認」に分類。根拠となるファイル・関数・データを示す。

3. **二つの参照事例のTrace**
   SmartPhone AssemblyとTW Bufferingについて、物理Lotと制御信号を分けて説明する。必要な範囲で週次表とLot ID例を示す。

4. **ドラフトへの修正提案**
   該当節、問題点、修正理由を列挙する。本文はまだ書き換えない。

5. **Core変更の必要性**
   「文書化だけ」「表示・診断の変更」「データ契約の変更」「エンジン変更が必要」に分ける。変更不要という結論も歓迎する。

6. **大杉への確認事項**
   コードや測定では決まらない業務上の判断だけを、優先度順に挙げる。

## 7. 作業上の制約

* リポジトリ内のコード、CSV、テスト、golden、設計文書を変更しない。
* commit、push、PR作成を行わない。
* 新しい属性やPolicyを採用済みとして扱わない。
* 測定スクリプトや出力はリポジトリ外の作業領域へ置く。
* 実行処理がモデルCSVなどを書き換える場合は、作業用コピーで測定する。
* 実測した結果と、既存文書・コミットに記載された結果を区別する。
* アクセスできないファイルや実行できないテストを、確認済みとしない。
* 開始時と終了時に作業ツリーの状態を確認し、既存変更を保全する。

## 8. 最も重視すること

今回は、きれいな分類表や新しいアーキテクチャを早く完成させることを求めていません。

**既存WOMで何が起きているのかを、根拠を示して説明し、私たちの仮説が間違っていれば訂正すること**を重視します。

まず調査方針と参照対象を簡潔に示したうえで、読み取り・測定によるレビューを進めてください。実装判断が必要になった時点で止め、私へ報告してください。

````
