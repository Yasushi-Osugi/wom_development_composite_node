---
tags: [wom, source]
---
# docs/design/drafts/WOM_Composite_Node_Session_Record_2026-09-20.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/design/drafts/WOM_Composite_Node_Session_Record_2026-09-20.md) · [原文テキスト](../../../../90_Raw/docs/design/drafts/WOM_Composite_Node_Session_Record_2026-09-20.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- WOM Composite Node検討セッション記録
- 1. セッションの目的
- 2. WOMの基準とGitの状態
- 3. Capacity問題の発見と訂正
- 3.1 最初の誤読
- 3.2 S3表示の修正
- 3.3 残った課題
- 4. Composite Nodeの検討
- 4.1 Factoryの構想
- 4.2 参照モデルの訂正
- 5. Lot_ID、Kitting、注文残
- 5.1 Lot_IDの意味
- 5.2 現行Kitting Gate
- 5.3 遅延需要に対する合意
- 5.4 現行実装への検証課題
- 6. TW Buffer、DBR、Kanban
- 6.1 TW Bufferの現行方式
- 6.2 Kanbanの業務的位置づけ
- 7. 独立レビューの実施
- 8. 作成済み文書
- 9. 後続作業のGate
- Gate A：wom-v1r5m0への移行と基準固定
- Gate B：現行照合と測定
- Gate C：詳細設計と独立レビュー
- Gate D：実装承認
- 10. 最終的な設計上の要点
- 11. 利用上の注意

## 関連する知識源

- [[80_Sources/docs/design/drafts/WOM_Composite_Node_Architecture.md|docs/design/drafts/WOM_Composite_Node_Architecture.md]]
- [[80_Sources/requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md|requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md]]

## 全文（コメント・原文を省略せず収録）

````markdown
# WOM Composite Node検討セッション記録

作成日：2026-09-20  
対象：Global Weekly PSI Planner / WOM  
記録の種類：会話内容にもとづく検討経緯・設計判断・成果物一覧  
注意：これは画面の逐語的な生ログではない。会話で確認した事実、仮説、判断、未決事項を後続開発で参照できる形に再構成した記録である。

## 1. セッションの目的

本セッションでは、WOMのCapacity-aware PSI、S3 Run表示、Composite Node、Stock Yard / Kitting、TW半導体Buffer、Kanban / DBRの位置づけを整理した。

中心課題は、P/S/I/COの文字だけから業務意味を推定したことで生じた誤読を正し、既存WOMの構造を壊さずに設計言語を整えることだった。

主な検討目標は以下である。

- P/S/I/COの予定・実行・物理状態・要求状態の違い
- Factoryを複数PSIと組立処理からなるCompositeとして説明できるか
- Bufferにおける先読み供給、補充要求、Kanbanの境界
- 新属性を十分な根拠なしにcoreへ入れないこと
- 次の実測・詳細設計・実装へ進むためのGateを定めること

## 2. WOMの基準とGitの状態

会話開始時に共有された最新版の基準は、公開リポジトリ Yasushi-Osugi/wom_v1r0m0 の wom-v1r4m0 ブランチだった。

大杉さんのWindows環境では、次の3コミットが順に作成・pushされた。

| SHA | 内容 |
|---|---|
| e4b0363 | Phase 8-3c-4依頼書。能力表示の誤読を訂正し、S3の案5を定義 |
| 1bd6c44 | S3で実スループットをCapacityと比較する表示修正 |
| bc470b2 | Composite Node Architectureのドラフトメモ追加 |

Windows環境で確認されたテスト結果は以下だった。

- GUI不変条件：69 passed、3 skipped
- golden：13 passed
- 全体：511 passed、3 skipped
- 作業ツリー：clean
- wom-v1r4m0は両remoteへpush済み

この成功は表示変更が既存テストを通過したことを示す。ただし、業務意味の正しさや将来のComposite設計を自動的に保証するものではない。

その後、実測・改修は wom-v1r5m0 へのrelease up後に進める方針となった。移行先SHA、適用AGENTS.md、実行環境の確認が次の開始条件である。

## 3. Capacity問題の発見と訂正

### 3.1 最初の誤読

醤油モデルのBottling_Nodaでは、工場閉鎖週に次の状態が観察された。

- P = 1000
- S = 0
- actual_s = 0
- I = 1000
- cap_hard = 0.1

最初は「能力0.1の週に1,000 lotを生産している」と読まれた。しかし追跡すると、Pは当該ノードの生産完了ではなく上流からの入庫として扱われていた。閉鎖週の処理量と実出荷は0であり、閉鎖自体は守られていた。

この訂正により、能力制約を強制的に変更する案1〜案4は、当初想定した根拠を失った。

### 3.2 S3表示の修正

問題の主因は、S3がPをCapacity線と比較していたことだった。Pの業務上の意味はノードやモードにより異なり、入庫量を処理能力と比べると能力超過に見える。

案5として、S3の表示契約を次のように変更した。

| 条件 | 表示する系列 | 表示名 |
|---|---|---|
| plan_mode が push | 実出荷量 | 処理量（lot） |
| それ以外 | supply P | 生産量（lot） |

変更は表示側に限定し、Forward PlannerのLot操作を変えなかった。Seriesの意味をcapacity_seriesで一箇所に宣言し、画面側でplan_modeを再解釈しない方針を採った。

### 3.3 残った課題

表示を修正しても、Capacity一般の意味は確定していない。

- 通常ForwardはPをhard封印する
- pushはP封印をskipする
- push_subは全量を上流へ通す
- Yardは専用gateで扱われる
- Backwardのcapacity適用範囲にも限定がある

よって、cap_hardを一律にP、I、Sへ再割当てることはしない。Buffer_Chip_TWの1350も、保管容量・入出庫能力・下流投入能力等のいずれかを断定せず、由来未確認とする。

## 4. Composite Nodeの検討

### 4.1 Factoryの構想

大杉さんから、Factoryは一つのPSIではなく、少なくとも二つのPSIを接続するCompositeとして説明できるという構想が示された。

| PSI | P | I | S |
|---|---|---|---|
| 部材Stocker PSI | 受入れ／Purchase | 部材・仕掛在庫 | Picking／払出 |
| Production PSI | 生産完了 | 完成品在庫 | Ship |

間にPicking、Kitting、Transformation / Assemblyの処理がある。

検討の結果、これは将来のFactory TemplateやConstruction Kitに有効な概念である一方、直ちに新しいnode_characterをcore分岐へ入れる根拠にはならないと整理した。施設名、Capability、Planning Mode、Control Policy、Constraint Scope、Event、PSI Stateを一つの属性へ押し込めないことが重要である。

### 4.2 参照モデルの訂正

最初はSmartPhoneの組立モデルがStocker / Picking / Kitting / Assemblyの参照例と認識されていた。しかし、静的レビューで確認できたStock Yard＋Kitting Gateの具体例はSmartPhoneではなく、次のモデルだった。

- data/sample/bom-test-2026
- data/sample/ev-europe-2026

後続設計の組立参照モデルはEV / BOMテストとする。SmartPhone / SmartXは、TW Bufferと多段Inboundの参照例ではあるが、複数Yardのkit積集合処理を確認した例ではない。

## 5. Lot_ID、Kitting、注文残

### 5.1 Lot_IDの意味

WOMのDemand Anchored Lotは市場需要から生成され、Backwardで必要量・必要週として上流へ伝播する。

組立では、同じ需要Lot_IDを複数部材の1 setに共用する。例えば、車両需要の同じLot_IDがタイヤYardとバッテリーYardの双方に存在し得る。これは同一の物理部品が二重存在することを意味しない。

大杉さんは、部材の区別をLot_ID + node_nameで行う考え方を確認した。kitting記録も、組立週・Lot_ID・子ノード名・到着週を持つ形で設計されている。

このため、「同じ物理Lot_IDは同時に一つの物理場所にしか存在しない」という単純な不変条件は、既存の1 set ruleにそのまま適用できない。検証では、需要ID、部材ノード、商品、週、状態を組み合わせる必要がある。

### 5.2 現行Kitting Gate

現行のStock Yard / Kitting Gateは、各YardのIに共通して存在するLot_IDの積集合を取り、組立ノードが当週必要とするLotだけを扱う。

- 各YardからLot_IDを一回ずつ払い出す
- 組立ノードのPへLot_IDを一回だけ入れる
- 不足部材があるLotはYardのIに残す
- 到着情報をkitting記録へ残す

BOM数量はLot_IDを複製せず、数量表示・原価換算等で別途扱う1 set ruleである。

### 5.3 遅延需要に対する合意

大杉さんは、必要週に部材が揃わなかったkitは失注ではなく、後日履行対象と明確にした。

合意した業務意味は次の通り。

1. 必要週にkitが揃わなければ生産できない。
2. 出荷できない要求はCOとして翌週へ繰り越す。
3. 同じ需要Lot_IDの未履行要求を保持する。
4. 後日部材が揃えば組立対象に含める。
5. 生産完了した供給を注文残へ引き当て、実出荷する。
6. 履行済み要求を再度組立・出荷しない。

ここで「需要回復」は新しい需要を発行することではなく、注文残の継続保持と履行である。

### 5.4 現行実装への検証課題

静的レビューから、次の懸念が整理された。いずれも実測済みの不具合として断定していない。

- Gateは当週のdemand Sだけを候補にしており、遅れて揃った未完了kitの再処理経路が見当たらない。
- Gateが部材を払い出しAssembly Pを作った後に、通常ForwardがAssembly Pをhard封印し得る。
- Yardと非Yardの子が混在するトポロジーの扱いが明確でない。
- Yardは通常のForward処理をskipするため、Yard自身のcapacityや期首在庫の扱いが未確認。
- 完成品IにあるLotとCOに残る要求をどの順序で引き当てるか、詳細設計が必要。

重要なのは、単純にCOを当週の組立需要に追加するだけでは不十分なことである。既に完成品Iがある注文残を、再度部材払出・組立してはいけない。

## 6. TW Buffer、DBR、Kanban

### 6.1 TW Bufferの現行方式

SmartXの経路は、おおむね以下の多段Inboundとして確認された。

WaferFab_TW → Buffer_Chip_TW → FoundryTW → AssemblyCN

Buffer_Chip_TWにはMode 4のpush設定があり、push_lead_time_weeksは39である。Mode 4は、Backwardで既に割り当てられた需要Lot_IDを保持し、leaf_inのPを将来需要に対して39週前へ配置する。

この方式は需要を先読みして供給を置く方式である。Buffer払出しの実績を観測し、上流へ独立の補充要求イベントを返す閉ループは、現行経路には確認されていない。

従って、TW BufferをKanban／消費連動Buffer Pullの実装例とは扱わない。需要先読みとBuffer保有の参照例として記述する。

### 6.2 Kanbanの業務的位置づけ

大杉さんは、Kanbanそのものは日・時・分・秒の現場オペレーションであり、Weekly PSI Plannerが詳細を直接モデル化する対象ではないと整理した。

ただし、WOMはKanbanを無関係なものとして切り離すのではなく、現場Kanban運用を支える週次の部材供給・生産・在庫余裕を計画するものと位置づける。

合意した表現は次の通り。

> WOMはKanbanの詳細な現場制御を直接モデル化しない。設定した供給・能力・リードタイム・在庫余裕の前提の下で、Kanban運用を支える週次の部材供給と生産計画の成立性を評価する。

「Kanban operationを内包する／保証する」という語は、この週次前提の範囲に限定する。週内の到着順序、突発停止、Kanbanカード枚数の十分性まで検証したという意味にはしない。

1週間分の部材Bufferは欠品を防ぐ余裕の候補である。ただし全ノード共通の必須値にはせず、設定場所、在庫の所在、計上量をモデルごとに確認する。

## 7. 独立レビューの実施

Composite Nodeのドラフトを既存実装と照合する独立レビューを行った。基準SHAは次だった。

bc470b29d56e12db486e82aab7b011afe7a822f5

レビューでは、コードで確認できること、既存文書の記述、業務仮説、矛盾・未確認、実測すべき事項を分けた。

主な結論は次の通り。

- Compositeという整理の方向は維持できる。
- 既存実装の説明と、新機能の提案がドラフトに混在していた。
- TW方式を消費連動補充と扱わない。
- Kanbanは週次計画を支える概念として位置づけ直す。
- 新しいnode属性、P/I/S別capacity、Event基盤を先走ってcoreへ導入しない。
- 現行意味契約と境界ケースを先に文書化・測定する。

レビュー環境ではAGENTS.mdの制約に従い、WOM・pytest・Gitの再実行は行わなかった。既存のWindows実行結果を今回の実測と偽らず、静的レビューであることを明記した。

## 8. 作成済み文書

| 文書 | 役割 | 状態 |
|---|---|---|
| RequestLetter_WOM_Composite_Node_4_GPT-6_Astra.md | Astraによる独立レビューの依頼書 | 作成済み |
| WOM_Composite_Node_Independent_Review_bc470b2.md | 基準SHAに対する静的独立レビュー | 作成済み |
| WOM_Composite_Node_Design_Draft_v0.1.md | 後続の詳細設計・実装提案の共通基盤 | 作成済み |
| docs/design/drafts/WOM_Composite_Node_Architecture.md | 初期のComposite Node Architecture検討メモ | リポジトリへ追加・push済み |
| requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md | S3の処理量表示に関する訂正と実装依頼 | リポジトリへ反映済み |

設計ドラフトv0.1は、合意済み方針、現行確認、設計案、未確認事項を明示的に分離している。これを単独で実装許可として扱わず、詳細設計・測定・Request Letter・大杉さんの承認を経て実装へ進む。

## 9. 後続作業のGate

### Gate A：wom-v1r5m0への移行と基準固定

- 移行先URL、ブランチ、完全SHA、作業ツリー状態を確定
- 適用AGENTS.mdと実行可能な環境を確認
- v1r4m0基準との差分を確認
- ここまでは移行確認であり、Composite改修は開始しない

### Gate B：現行照合と測定

以下を原本CSV・goldenを変更しない作業用コピーで測定する。

| ID | ケース | 目的 |
|---|---|---|
| T01 | EV／BOM無制約 | 各部材1 set→完成需要1件、同週生産、重複なし |
| T02 | 一部材が必要週の翌週以降に到着 | 注文残保持と後日組立・出荷 |
| T03 | 完成品Iと同IDの注文残 | 再組立せず完成品を引当 |
| T04 | 組立能力だけをForwardで制限 | 部材・注文残・完成品の保存 |
| T05 | Yard＋非Yard混在、Yard期首在庫 | 許容範囲・診断の設計 |
| T06 | TW Mode 4 baseline | 39週前倒し、LT、払出順のtrace |
| T07 | BufferとFoundryの能力を独立変更 | どの処理が何を制限するか |
| T08 | OT decouple前後の不足 | actual、下流Pの出所、PPC入力の区別 |
| T09 | 1週間分の部材余裕 | 想定Yardの在庫、二重先行配置の有無 |
| T10 | 期間末未完了kit | 部材残と未履行注文を別々に報告 |

記録では、数量とlot-週、期末値と期間和、単一ノードとチェーン全体、予定とactualを別の列にする。

### Gate C：詳細設計と独立レビュー

測定で仕様との差分が確認された場合、対象を限定して次を定義する。

- 未完了kitの保持・導出方法
- 未完了生産要求と、既生産品を待つ出荷注文残の区別
- 部材払出、能力判定、完成計上、注文引当、実出荷の順序
- 予定Sとactual_sを保ちながら、重複履行を防ぐ方法
- Yard混在、期首在庫、期末残の扱い
- 外部診断に必要な公開データ

設計案には、変更関数、入出力、週次状態遷移、既存互換性、反例、試験範囲を含める。

### Gate D：実装承認

実装前にRequest Letterを作成し、対象ファイル、業務挙動、受入テスト、影響モデル、golden変更見込みを明記する。大杉さんの承認後にのみ、保護対象coreへの変更を行う。

## 10. 最終的な設計上の要点

> WOMは週次のDemand Anchored LotとPSIを用いて、部材供給・組立・在庫・出荷要求を一貫して扱う。Factoryは部材Yard群とAssembly PSIの協調として説明できる。必要週に部材が揃わない場合、要求はCOとして保持され、後日同じLot_IDで履行されるべきである。kit成立と生産完了は週次では同一週とする。Kanbanの詳細な現場制御は直接モデル化せず、その運用を支える週次の供給・能力・在庫余裕を評価する。TW Mode 4の先読み供給は、消費実績からの補充制御と混同しない。

この整理は、WOMに大規模な仕組みを直ちに追加するためではない。既存のPSI、Demand Anchored Lot、Kitting、Push / Pull、Buffer、Capacityを同じ言葉で誤解なく扱い、実測にもとづいて安全に改良するための基盤である。

## 11. 利用上の注意

- このファイルはセッションの要約・判断記録であり、逐語的なチャットログではない。
- 数値・Git SHA・テスト結果は、会話中に共有されたものと静的レビューで確認されたものを区別して扱う。
- 新しい実測結果が得られた場合、既存の推測・静的所見を更新する。
- WOM_Composite_Node_Design_Draft_v0.1.mdが後続設計の主たる参照文書であり、本記録はその背景と意思決定の履歴を残す補助文書である。

| 版 | 日付 | 内容 |
|---|---|---|
| v1.0 | 2026-09-20 | Composite Node、Capacity表示、Lot_ID、Kanban、独立レビュー、後続Gateを記録 |

````
