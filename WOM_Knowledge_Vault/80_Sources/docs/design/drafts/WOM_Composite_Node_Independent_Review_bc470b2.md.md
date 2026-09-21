---
tags: [wom, source]
---
# docs/design/drafts/WOM_Composite_Node_Independent_Review_bc470b2.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/design/drafts/WOM_Composite_Node_Independent_Review_bc470b2.md) · [原文テキスト](../../../../90_Raw/docs/design/drafts/WOM_Composite_Node_Independent_Review_bc470b2.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- WOM Composite Node Architecture 独立レビュー
- 0. 調査条件と証拠の扱い
- 1. 総括
- 結論
- 維持できる部分
- 判断保留
- 2. 主張と証拠の対応表
- 3. PSIの意味と時間軸
- 3.1 書込主体と順序
- 3.2 COとIは「期限だけで一意に分類」できない
- 3.3 Lot保存の検査対象
- 4. 参照事例のTrace
- 4.1 SmartPhone：確認できた構造と、参照モデルの訂正
- 現行Factoryの具体例：Vehicle_Assy
- コード手追跡例：実測値ではない
- 設計昇格前に必要な境界テスト
- 4.2 TW Buffer：Mode 4のTrace
- データと制御設定
- 制御側：下流要求からleaf_inのPまで
- 供給側：条件付きのLot手追跡
- Bufferの1350
- 5. ドラフトへの修正提案（本文は変更しない）
- 既存設計書の側にも修正対象がある
- 6. Core変更の必要性
- S4／PPCへの関連注意
- 7. 大杉さんへの確認事項
- 優先度1：今回の設計範囲
- 優先度2：遅延需要の扱い
- 優先度3：生産の時間・状態
- 優先度4：IDの意味
- 優先度5：Kanban／Buffer Pullの対象範囲
- 優先度6：1350の業務的な意図
- 別枠：資料と実行環境の確認
- 8. 実測追補の最小セット
- 9. 根拠ファイル索引

## 関連する知識源

- [[80_Sources/docs/design/drafts/WOM_Composite_Node_Architecture.md|docs/design/drafts/WOM_Composite_Node_Architecture.md]]
- [[80_Sources/wom/engine/forward_planner.py|wom/engine/forward_planner.py]]
- [[80_Sources/wom/engine/backward_planner.py|wom/engine/backward_planner.py]]
- [[80_Sources/wom/engine/push_pull.py|wom/engine/push_pull.py]]
- [[80_Sources/tests/test_stage3a2_kitting_gate.py|tests/test_stage3a2_kitting_gate.py]]
- [[80_Sources/requests/request_stage3a2_kitting_gate.md|requests/request_stage3a2_kitting_gate.md]]
- [[80_Sources/docs/design/kitting_list_assembly.md|docs/design/kitting_list_assembly.md]]
- [[80_Sources/wom/model/plan_node.py|wom/model/plan_node.py]]
- [[80_Sources/wom/engine/sc_tree_builder.py|wom/engine/sc_tree_builder.py]]
- [[80_Sources/wom/model/lot_generator.py|wom/model/lot_generator.py]]
- [[80_Sources/wom/engine/capacity_sealer.py|wom/engine/capacity_sealer.py]]
- [[80_Sources/tools/run_headless_from_folder.py|tools/run_headless_from_folder.py]]
- [[80_Sources/wom/engine/plan_copy.py|wom/engine/plan_copy.py]]
- [[80_Sources/docs/design/demand_anchored_lot.md|docs/design/demand_anchored_lot.md]]
- [[80_Sources/wom/ppc/ppc_psi_bridge.py|wom/ppc/ppc_psi_bridge.py]]
- [[80_Sources/wom/engine/event_timeline.py|wom/engine/event_timeline.py]]
- [[80_Sources/requests/Phase8-3c-2_RequestLetter_CapHardSealing_to_CodeKun.md|requests/Phase8-3c-2_RequestLetter_CapHardSealing_to_CodeKun.md]]
- [[80_Sources/requests/Phase8-3c-3_RequestLetter_Option4_to_CodeKun.md|requests/Phase8-3c-3_RequestLetter_Option4_to_CodeKun.md]]
- [[80_Sources/requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md|requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md]]

## 全文（コメント・原文を省略せず収録）

````markdown
# WOM Composite Node Architecture 独立レビュー

レビュー日：2026-09-20  
依頼者：大杉／WOM Project Owner  
対象：`docs/design/drafts/WOM_Composite_Node_Architecture.md`  
基準SHA：`bc470b29d56e12db486e82aab7b011afe7a822f5`  
ステータス：**静的レビュー完了・実測追補待ち。設計承認・実装承認ではない。**

## 0. 調査条件と証拠の扱い

依頼書に従い、設計ドラフト、既存の設計文書、実装、モデルCSV、テストの期待値を照合した。リポジトリのコード、CSV、テスト、golden、設計本文は変更していない。commit、push、PR作成もしていない。

- 開始時のローカルコピーは `dac68870242ee9d1867c3edd6bd0fd7f0ecd64ca`。`git status --short` の出力は空だった。指定SHAのオブジェクトは手元に存在しなかった。
- 続いて読んだ `AGENTS.md` §10に、Linux bash環境でGit・WOMを実行しないという記載を確認した。以後、Git CLI・WOM・pytestの実行は行っていない。
- GitHubの読み取り専用比較で、旧コピーから基準SHAまでの変更が3コミット・6ファイルであることを確認した。エンジン、モデルCSV、以下で参照する既存の組立テスト・設計文書は差分対象ではない。
- 新しいCompositeドラフト、Phase 8-3c-4依頼書、変更されたヘッドレス出力処理は、GitHubで基準SHAを指定して参照した。最新ブランチとの混用はしていない。
- 開始後はリポジトリを読み取る操作のみ。終了時のGit status再実行は上記制約に従い省略したため、「終了時もGitでclean確認済み」とは記載しない。
- 本報告書はリポジトリ外に作成した。

**本レビューによる実測結果はない。** ユーザー提示の511 passed／3 skipped、既存文書の測定表、goldenの数値を、今回再実行した結果として扱っていない。以下の週次例は明示した条件下のコード手追跡である。

基準差分：[dac6887 → bc470b2](https://github.com/Yasushi-Osugi/wom_v1r0m0/compare/dac68870242ee9d1867c3edd6bd0fd7f0ecd64ca...bc470b29d56e12db486e82aab7b011afe7a822f5)

## 1. 総括

### 結論

**Compositeという整理の方向は維持できる。ただし「既存実装をそのまま言語化した設計」として、このドラフトを昇格させるのはまだ早い。** 実装済みの構造、将来の拡張案、既存設計判断を変更する提案が混在している。

特に、以下の四点は設計着手前に訂正したい。

1. **Stock Yard＋Kitting Gateの具体的な参照モデルは、確認した基準ではSmartPhoneではなく `bom-test-2026` と `ev-europe-2026`。** SmartX／iPhoneには組立という名称のMOMがあるが、それだけでYard連携の実装例とはいえない。
2. **TW Bufferの現在の方式はMode 4による需要Lotの39週前倒し配置。** 払出結果を観測して上流へ補充イベントを返す閉ループ制御とは異なる。
3. **Lot_IDは必ずしも一つの物理部材を識別しない。** 組立では同じ需要Lot_IDがタイヤ側・バッテリー側にそれぞれ存在する。裸のLot_IDに「物理場所は一つ」を課すと、既存の1 set ruleと衝突する。
4. **既存設計にはKanbanを対象外にした明示的な判断がある。** 新ドラフトのKanban導入は、単なる既存構造の文書化ではなく、スコープ変更の検討を含む。

### 維持できる部分

- 施設名、計画方式、PSI状態、実移動、制御指示、capacity適用操作を区別すること。
- `node_character`という単一属性にすべての挙動を集中させないこと。
- 複数Yardと組立ノードの協調処理を、GUIや設計上のCompositeとして説明すること。
- 仮説と現行仕様を分け、core変更前にLot／週次traceを確認すること。
- 表示修正とエンジン挙動変更を別案件とすること。

### 判断保留

- 新しいCompositeクラス、Event基盤、Policyインターフェースが必要か。
- Bufferの1350を何の能力と解釈するか。
- 工程開始・加工中WIP・生産完了を独立状態にするか。
- 週次の消費連動補充をWOMの対象へ加えるか。

**今回の結果だけでは、大規模なcore再設計の必要性は立証されていない。** 先に現行仕様と境界条件を文書化し、限定的な反例テストで不足を確定するのが妥当である。

## 2. 主張と証拠の対応表

分類は「コードで確認」「実測で確認」「業務上の仮説」「矛盾あり」「未確認」。CSV／テストの静的確認を含む場合、その内訳を記す。「実測で確認」に該当する新規結果はない。

| 主張 | 分類 | 根拠と適用範囲 |
|---|---|---|
| 通常経路の供給伝播は上流→下流 | コードで確認・範囲限定 | Forwardの `_propagate_to_parent`、MOM→SP bridge、`_propagate_to_child`。ただしDemand-Pを再コピーするPULL区間は、上流実出荷からの連続した物理伝播ではない。E1 |
| 下流需要が上流へ伝播する | コードで確認 | BackwardのOT伝播、bridge、IN伝播。これを消費後の補充イベントと同一視しない。E2 |
| TW Bufferが消費実績を契機に補充指示を返す | 矛盾あり：現行例への説明として | Mode 4はForward前に需要Sを参照し、leaf_inのPを前倒し設定する。実払出結果を入力としていない。E3、E4 |
| Market PullとBuffer Pullを分ける | 業務上の仮説として有用 | 現行OTのPULLはDemand-P copy、TWの方式は先読み配置。二つの閉ループが実装済みという説明は不可。E1、E3 |
| DBR／Kanbanは同じBuffer Pullの派生 | 未確認 | Mode 4にDBR lifecycleという説明はあるが、一般的なDBR／Kanban共通制御基盤は確認できない。名称で同等性を証明できない。E3 |
| Kanbanは既存WOMの機能として正典化できる | 矛盾あり | 既存設計の §6で明示的に対象外。方針再検討は可能だが承認が必要。E7 |
| Stocker＋Assemblyの協調PSIが存在する | コードで確認 | `stockyard`の在庫積集合から、各YardのSと組立Pへ記録する専用処理。E1、E5、E6 |
| その具体例がSmartPhoneである | 矛盾あり：確認した基準では | サンプルのstockyard行はEV Europeの6ノード、BOM testの2ノード。SmartX／iphone／iphone_globalには該当行なし。E4、E5 |
| Pはどこでも生産完了 | 矛盾あり | Pは入庫、計画供給、kit成立結果など、書込経路が違う。E1～E3 |
| Sはどこでも実出荷 | 矛盾あり | 通常／pushは予定Sと `_actual_s` が別。push_sub／YardはSを実出荷・実払出へ上書きする。E1 |
| COはどこでも需要週を過ぎた未充足 | 矛盾あり | Backward COは前倒し配置のoverflow記録。Forward通常は翌週CO、pushはCOを空にしてshortfallを別記録する。E1、E2 |
| 同じ物理Lot_IDは全ノードで一意の場所を持つ | 矛盾あり：既存IDへの適用として | assembly兄弟へ同一IDをフルコピーし、Yardごとに部材を表す。物理個体IDと需要キーの区別が必要。E2、E5、E8 |
| BOM数量はLot_ID数を増やす | 矛盾あり | `bom_qty`は1 set ruleの数量・一部原価換算。gateのID存在判定は変わらない。E6、E8 |
| Transformation開始からLT後にPが立つ | 業務上の仮説 | 現行Yard gateは同じ週にYard S→Assembly P。独立した加工開始・完了の時計はない。E1 |
| cap_hardは全ノードの実処理量を制限する | 矛盾あり | 通常ForwardはPを切り詰め、pushはhard封印をskip、Yardは通常処理をskipする。E1 |
| Bufferの1350は保管容量 | 未確認 | CSV→cap_hardの値の配線は確認できるが、保管容量を表す根拠はない。E4、E9 |
| S3修正によりすべての能力意味論が確定した | 矛盾あり | 修正は系列選択・表示。pushでactual量を出すが、他はPをproductionとする暫定分類。E10 |

## 3. PSIの意味と時間軸

### 3.1 書込主体と順序

| 段階／処理 | 主な読み取り | 主な書き込み | 読み方 |
|---|---|---|---|
| Demand lot生成 | 市場需要、cpu_size | leaf_outのdemand S | 需要キーを生成 |
| Backward | 下流demand S、LT、SS、capacity | 上流demand S/P、必要に応じdemand CO | 必要量・必要時期の配置 |
| Plan Copy | demand S/P | supply S/P | 別リストへ計画をコピー。物理到着の証拠ではない |
| Mode 4 setup | 基準ノードの将来demand S、leaf membership | leaf_inのsupply P、plan_mode | 誰が供給するかを維持して、いつ供給するかを変更 |
| Forward通常 | 前週I＋当週P、当週CO＋S | I、翌週CO、actual_s | Lot_ID一致で充足を判定 |
| Forward push | 前週I＋当週P、Sの件数 | I、actual_s、shortfall、CO=[] | 件数で払出し、ID照合はしない |
| Forward push_sub | 前週I＋P | S=actual_s=available、I=[] | 到着分を全量通過 |
| Yard gate | 各YardのI、組立当週demand S | Yard I/S、組立P、kitting、Yard actual_s | 部材存在を共通需要IDで判定 |
| OT PULL区間 | 当該ノードのdemand P | supply Pを上書き | 上流実績の伝播ではなく計画供給への切替 |

`copy_demand_to_supply()`は初期化済みの空I/COを前提としている。関数名だけから再実行時の完全リセットまで保証すると誤る。

### 3.2 COとIは「期限だけで一意に分類」できない

通常Forwardでは、現在のノードの `CO[w] + S[w]` にあるIDと、`I[w-1] + P[w]` のIDを照合する。未充足は `CO[w+1]` に記録される。Lot_ID内の市場需要週を毎回parseして期限判定する実装ではない。

一方、pushでは毎週COを空にし、当週shortfallを別に記録する。Backward COは能力による前倒し配置の履歴であり、顧客への遅延確定ではない。

したがって、少なくとも「Demand／Supply layer」「ノードのモード」「当週末状態／翌週繰越」「市場due／当該工程の必要週」を添えて解釈する必要がある。合計COを、そのまま顧客未充足数量と扱ってはならない。

### 3.3 Lot保存の検査対象

P/Sは期間内の流入・流出記録、Iは週末残高、COは要求状態である。これらを全週・全ノードにわたり単純加算して質量保存を判定できない。

Yardごとの候補検査は、境界を固定して次のようにする。

`当週末の部材残高 = 前週末の部材残高 + 当週部材入庫 − 当週部材払出`

そのうえで、ある需要IDのkit成立には各必須部材の1 setが必要で、完成側へは同じ需要IDを1回だけ渡す、と別に検査する。部材数から完成品数への単純なLot件数保存は要求しない。物理数量を比較する場合は部材種別・cpu_size・bom_qtyをそろえる。

## 4. 参照事例のTrace

### 4.1 SmartPhone：確認できた構造と、参照モデルの訂正

基準のSmartX `SmartXPro_CN` は次の物理経路を持つ。

`WaferFab_TW → Buffer_Chip_TW → FoundryTW → AssemblyCN → SP_SmartXPro_CN → DC → Retail`

`AssemblyCN`には、このSKUではFoundryTWが一つ接続されている。Stock Yard兄弟の積集合による複数部材の待合せは、この経路の実装例ではない。iphone／iphone_globalの該当組立経路にもstockyard行は確認できなかった。別の未公開モデル・別コミットにSmartPhoneのYard実装がある可能性は否定しない。

したがって、Factory Compositeの実装traceは、確認可能な `bom-test-2026` を補助参照として以下に示す。

#### 現行Factoryの具体例：Vehicle_Assy

- `Tire_Supply → Tire_Yard → Vehicle_Assy`
- `Battery_Supply → Battery_Yard → Vehicle_Assy`
- タイヤbom_qty=4、バッテリーbom_qty=1。両YardのLTは0、各供給元のLTは1。
- 同じ完成需要ID `L` を両部材系統へ伝播する。タイヤ独自IDを4個作る設計ではない。
- 各部材はYardのIで待つ。組立ノードがその週に要求するLが両Yardにあれば、両YardからLを1回ずつ払い出し、Vehicle_Assy.PへLを1回だけ追加する。
- `kitting[assembly_week][L][yard_name] = arrival_week` が到着情報を保持する。独立した部材ID→完成品ID変換表ではない。

#### コード手追跡例：実測値ではない

説明用Lの組立必要週をwとし、他需要、能力制約、閉鎖、期首在庫はない。タイヤはw−1、バッテリーはwにYardへ到着するものとする。

| 週 | Tire_Yard | Battery_Yard | GateとVehicle_Assy |
|---|---|---|---|
| w−1 | Lが到着しIに残る | 未着 | 組立当週需要にLがないので払出なし |
| w | 前週IにLあり | L到着 | 両者の積集合にLあり。各Yard SにL、組立PにLを1回記録 |
| wの通常Forward | 払出後IからLが消える | 同左 | 組立の需要LとPのLが一致すればactual_sにL |

現行gateは同一週の処理であり、`S_stock(w) → P_production(w+加工LT)`という独立したTransformation時計ではない。組立root自身のlt_wksを、そのまま加工時間として使うこともできない。MOM→SPのbridgeは同じ週である。

#### 設計昇格前に必要な境界テスト

**A. 遅着後の回復**

上記でバッテリーだけw+1に到着すると、wではgate不成立。w+1では部材が揃うが、ループは `node.psi4demand[w+1][S]` のみを走査する。Lがそこに再出現しなければ払出されない。さらに通常 `_process_node()` はgateの全期間構築後に呼ばれるため、そこで作られるCOがgateの翌週候補へ戻る経路もない。

これは**コードから導かれる再処理漏れの懸念**であり、今回実測した不具合ではない。既存Letter §2.2の当週需要ループにも同じ限定があるため、実装だけでなく仕様の補足が必要になり得る。

**B. 能力超過時の部材の行き先**

gateは先に各Yardから払い出して組立Pを作り、その後に組立の通常処理がPをhard封印する。組立が非pushでP超過が発生した場合、払い出した部材をYardへ戻す処理はこの経路にはない。部材消費と完成計上の境界を反例で確認する必要がある。Backwardで先に平準化される通常ケースだけでは、この経路を検証できない。

**C. 混在トポロジー・Yard属性**

コメントは「全直接子がstockyard」と説明するが、実条件はstockyard子が1個以上あるかである。非Yard子が混在すると、その寄与を含めたkit判定をしていない。Yardは通常 `_process_node()` をskipするため、Yard自身のcapacityと期首在庫も一般ノード同様に扱われるとは限らない。現行サンプルで発生済みとは判断しないが、Construction Kitの入力許容条件には必須の論点である。

既存 `test_stage3a2_kitting_gate.py` は、kit単一計上、不足部材、bom_qty不変、非Yard回帰、二つの実CSVを対象にする。一方、「全期間のどこかでIに現れたIDの集合」を使う保存テストだけでは、期末残高・部材別数量・遅着回復の証明にはならない。

### 4.2 TW Buffer：Mode 4のTrace

#### データと制御設定

| ノード | CSV上のtype | 親＝物理下流 | LT／transit | Mode 4 setup後 |
|---|---|---|---|---|
| WaferFab_TW | leaf_in | Buffer_Chip_TW | lt=26、transit=1 | push_sub |
| Buffer_Chip_TW | mom | FoundryTW | lt=0 | push、decoupling |
| FoundryTW | mom | AssemblyCN | lt=6 | push_sub |
| AssemblyCN | mom、IN root | SPへbridge | lt=4 | push_sub |

`push_config.csv`はBufferを指定し、固定数量0、buffer_lots=0、mode_only=False、push_lead_time_weeks=39。Mode 4が適用される構成である。FoundryTWとAssemblyCNもsetupでpush_subになる点が重要で、「momだから加工イベントを実行する」という実装ではない。

#### 制御側：下流要求からleaf_inのPまで

1. 市場需要LotがBackwardでAssembly、Foundry、Buffer、Waferへ伝播する。LT、SS、閉鎖、rootの能力配置が関与する。
2. Mode 4はBufferの `psi4demand[d][S]` を読む。
3. WaferにBackwardで割り当て済みのIDだけを選び、`Wafer.psi4supply[d−39][P]` へ配置する。
4. この処理はForwardの前に期間全体について終わる。Bufferのactual払出しを観測して発行する補充要求ではない。

指示元は `PushProductionPlanner.setup()`、宛先はBuffer配下のleaf_inの供給P、数量は選択された既存需要IDの件数、時期はBuffer需要週の39週前である。独立したpull_requestイベントIDはこの経路にはない。

#### 供給側：条件付きのLot手追跡

LがBuffer需要週dにあり、d−39が期間内、Wafer能力で封印されず、他設定による書換えがないとする。

| 時点 | 処理 |
|---|---|
| d−39 | Mode 4がWafer.PへLを設定。push_subは到着分を全量actual_sへ渡す |
| d−38 | transit=1によりBuffer.PへLが到着 |
| 各週r | Bufferは前週I＋Pの先頭から `len(S[r])` 件まで払出す。余りはI |
| Lが実際に払出された週r | Bufferのdecoupling専用伝播はlt=0でFoundry.PへLを追加 |
| r+6 | FoundryがLを封印せず通した場合、Assembly.Pへ到着 |
| 同じr+6 | Assemblyが通した場合、MOM→SP bridgeへactual_sで渡す |

**r=dとは断定しない。** BufferはID照合でなくFIFO相当の件数制御なので、他Lotの在庫順序・不足によって、当週予定SのIDと実払出IDが異なり得る。またAssembly rootのlt=4をこの表へ追加していないのは、現在のbridgeがそれを加工LTとして加算しないためである。

OTではDC_EMEAに明示的decoupling flagがある。そこより下流のRetail_EMEAはDemand-P copy経路に入る。一方、同じSKUの他枝を一律に同じ経路と見なしてはならない。

#### Bufferの1350

`capacity_plan.csv`のnode_name指定行で、Bufferのmax_supply=1350、Foundryも1350、Waferは20000。`load_capacity_dataframe()`が該当ノード・週のcap_hardに渡す。

ただし、現行標準経路では以下の限定がある。

- Backward `run()`の `_apply_mom_cap_backward()` 呼出対象はIN roots。Bufferは中間momであり、この呼出対象ではない。「mom型全件にBackward能力制約」というコメントだけで判断しない。
- ForwardのBufferはpushで、hardのP封印をskipする。
- Forward soft判定はpushでもPに対して行われるが、当該CSVにはcap_soft列がない。追加calendar等の設定がない場合、初期値は0。
- S3の比較線としては表示される。**表示されることと、同じ数量・週を実行時に制限していることは別。**

よって、データ配線と現行用途の一部は確認できるが、**1350を採用した業務上の由来、保管容量か代理能力か、Foundryから複写されたかは未確認**である。削除・I_cap移管・node_type変更の根拠にはできない。

## 5. ドラフトへの修正提案（本文は変更しない）

| 対象節 | 問題 | 修正方向 |
|---|---|---|
| §1、§17の5原則 | 仮説が上位の確定原則として読める | 「現行事実」「整理仮説」「将来構想」を分ける。DBR／Kanban同分類とTW消費連動補充は仮説へ戻す |
| §2 | P=1000／S=0の単一事例から広い原因へ飛躍する | 閉鎖週の過去測定と、一般的な制約意味論の未確定を分ける。S=actualは当該観測での一致に限定 |
| §3.2、§10.5 | I／COのdue基準を全経路へ一般化 | Demand CO、通常Supply CO、push shortfall、当該工程due、市場dueを区別 |
| §3.3、§6 | 要求の逆方向伝播と消費フィードバックを同一視 | Backward計画・Mode 4先読み・将来の消費連動要求を別項にする |
| §5.2、§10.3 | 正の加工LT・Yield変換が既存実装のように見える | 現行gateは同週kit成立。独立加工LT／Yield／工程内WIPは追加要件として記す |
| §5.3、§14 Step 4、§16 | SmartPhoneを実装済みYard参照例として固定 | EV／BOMを確認済み参照例とし、SmartPhoneの別資料があれば追加確認 |
| §6.1、§6.2 | TWにwithdrawal→pull_request→bindがあると読める | 現行Mode 4 traceと提案Event Chainを分離する |
| §7 | OT／INに二つの実装済み閉ループがあるように見える | 現行OT PULLのDemand-P copyと、IN Mode 4を正確に記す |
| §8 | Kanban対象外という既存判断と未調整 | 対象外を維持するか、週次集約policyとして再検討するかを大杉判断にする |
| §9 | cap名の追加だけで制約意味論が決まる印象 | 適用処理・参照系列・単位・週の意味・超過時の扱い・非適用条件まで契約に含める |
| §10.1 | physical location count per Lot ID=1 | 需要IDと部材実体の識別を分ける。既存1 set ruleを変更するかは別判断 |
| §10.2、§10.4 | 払出と加工投入・能力判定の順が未確定 | 遅着回復、払出後の能力不足、工程待機の境界ケースを先に規定 |
| §11 | series_kindの削除・導出が既定に見える | 表示契約としての存続／導出を保留。Constraintを持っても単位・集計粒度・週対応の契約は必要 |
| §12、付録A | 全Factory／Bufferが複数PSI必須に見える | Facility groupingの概念は採用候補。一つのBuffer PSI＋Controllerでもよいかを未決にする |

### 既存設計書の側にも修正対象がある

既存 `kitting_list_assembly.md` はgate未実装・Falseという古い状態説明を残しているが、コードはTrueで専用処理を持つ。ドラフトだけではなく、既存設計の「現在の実装状態」も整合させる必要がある。

また、同設計の「カンバンは遡及そのもの」「日・時・分の粒度だからWOM外」という説明は、対象外というプロジェクト判断と技術的根拠を分けたい。Lean Enterprise InstituteはKanbanを生産・引取りの許可／指示信号として説明している。この定義だけから、過去のシミュレーション状態を書き換える必要性は導けない。消費を観測して将来の補充を予定するモデルは、過去改変とは区別できる。ただし、週次モデルとして採用するかは別途判断が必要である。

外部参照：[Lean Enterprise Institute — Kanban](https://www.lean.org/lexicon-terms/kanban/)。DBR／Kanbanの一般分類について十分な一次資料照合は完了しておらず、本報告では共通Policy体系を確定しない。

## 6. Core変更の必要性

| 区分 | 今回の判断 | 候補 |
|---|---|---|
| 文書化だけ | 直ちに検討可能 | 現行PSI契約、Mode 4、組立参照例、Lot_ID／COの例外、LTの使われ方 |
| 表示・診断の変更 | 別依頼で限定的に検討可能 | 計画S／actual_sの区別、Pの業務ラベル、部材別残高・遅着回復trace、capacityの適用有無 |
| データ契約の変更 | 必要性を先に確認 | Facility grouping、許容トポロジー、constraintの操作・単位・週、需要IDと部材表現の対応 |
| エンジン変更が必要 | 追加要件を採用する場合に限る | 消費連動補充、独立加工LT／WIP、遅着kitの再処理、能力で停止した部材の保存など |

遅着kit・混在トポロジー・払出後の能力超過は、一般Compositeの導入とは独立に調査できる。`node_character`を先に追加しても、これらの操作順序・残高の問題は自動では解消しない。

### S4／PPCへの関連注意

`psi_to_sales_records()`はleaf_outのsupply S件数から販売数量を作り、元の需要Lot_IDではなく商品・チャネル・週の集約IDを発行する。OT PULLもDemand-P copyを持つ。したがって、PPCが変わらない理由を「中間COを費用計上していないから」だけで説明してはいけない。まず、販売入力が予定／実現のどちらかを確認する必要がある。

在庫保有費の追加と、物理的に実現した販売数量への接続は別課題である。本レビューではPPC全経路・会計方針の監査までは行っていない。

## 7. 大杉さんへの確認事項

### 優先度1：今回の設計範囲

**今回の基本設計は、現行構造の記述に限定しますか。それとも、消費連動補充・工程内WIP等の新機能まで含めますか。** 推奨は現行記述を先に確定し、追加要件を別章・別承認にすること。

### 優先度2：遅延需要の扱い

**必要週を過ぎて部材が揃ったkitは、後日組み立てて需要を回復させる対象ですか。それとも、その週に成立しなかった需要は失注・要再計画ですか。** ここが決まらないとgateの再処理の正解を定められない。

### 優先度3：生産の時間・状態

**週次粒度ではkit成立＝同週生産完了という近似を維持しますか。それとも、払出後の加工待ち／加工中／完成を分ける必要がありますか。** FactoryアイコンやComposite groupingの導入とは独立に決められる。

### 優先度4：IDの意味

**同じ需要IDを各部材の1 setに共用する方式を維持しますか。** 独立した物理個体IDの追跡が必要なら、需要キーとの対応が追加要件になる。新ID体系の導入を本レビューでは推奨・承認しない。

### 優先度5：Kanban／Buffer Pullの対象範囲

**従来のKanban対象外方針を維持しますか。それとも、週次に集約した補充policyの比較をWOMへ追加しますか。** 一般に実装できるかという問いと、WOMで扱う価値があるかという問いを分けたい。

### 優先度6：1350の業務的な意図

Bufferの1350は、保管量、入出庫能力、下流の投入許可量、あるいは旧モデル上の便宜的設定のどれを意図していたか。記録がなければ「由来未確認」と保持し、実測で挙動を示した後に新たな業務定義を決める。

### 別枠：資料と実行環境の確認

- SmartPhoneのStocker／Picking／Assemblyを実装した別モデル・コミットがあれば、参照先を提示してほしい。これは業務判断ではなく参照資料の不足である。
- 実測追補には、`AGENTS.md`に適合するWindows環境、または信頼済みと明示された別環境が必要。本環境でのWOM実行を無断で進めない。

## 8. 実測追補の最小セット

コード・CSV原本・goldenを書き換えず、承認された環境の作業用コピーで実施する。

| ケース | 記録するもの | 確かめること |
|---|---|---|
| BOM無制約 | 部材別P/S/I、Assembly P/S/CO/actual_s、同一IDの週履歴 | 1 set→1完成需要、同週gate |
| 1部材を需要週の翌週に納入 | 同上＋gate候補集合 | 揃った後の回復有無 |
| 組立能力だけをForwardで制限 | Yard払出、封印前後Assembly P、CO、期末部材残高 | 消費と完成の保存境界 |
| Yard＋非Yardの混在 | 全子の到着とgate対象 | 未対応構造の検出・拒否の必要性 |
| TW Mode 4 baseline | 元需要ID、Wafer P、Buffer P/I/S/actual_s、Foundry・Assembly到着 | 39週前倒しと各伝播LT |
| TW Buffer／Foundryのcapacityを別々に変更 | どの処理が反応したか、供給数と末端充足 | 1350の実効適用範囲 |
| OT decouple前後の不足 | 上流actual、子Pの出所、leaf S／actual、PPC販売入力 | 計画供給と実現供給の切替境界 |

期末I、週別I（lot）、Iの期間和（lot-週）、COの対象ノードとlayer、予定／actualを別列で出す。後追い処理を実装したり、goldenを更新したりすることは、この追補測定にも含めない。

## 9. 根拠ファイル索引

以下はすべて基準SHAへのリンク。本文の関数名を主な参照位置とする。

- E1 [forward_planner.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/wom/engine/forward_planner.py)：`run`、`_process_node`、`_process_assembly_with_yards`、`_push_pull_node`、伝播関数。重要位置は176–236、314–357、434–557、565–656、687–733行付近。
- E2 [backward_planner.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/wom/engine/backward_planner.py)：`run`、`_offset_week`、`_propagate_to_children`、`_apply_mom_cap_backward`。
- E3 [push_pull.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/wom/engine/push_pull.py)：`PushProductionPlanner.setup`、Mode 4、`_replenishment_schedule`。
- E4 SmartXデータ：[sc_tree_master.csv](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/data/sample/smartx-2027-2029/sc_tree_master.csv)、[push_config.csv](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/data/sample/smartx-2027-2029/push_config.csv)、[capacity_plan.csv](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/data/sample/smartx-2027-2029/capacity_plan.csv)。Bufferの1350は1698行、Foundryは1176行、Waferの20000は1437行から。
- E5 Yardモデル：[bom-test-2026/sc_tree_master.csv](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/data/sample/bom-test-2026/sc_tree_master.csv)、[ev-europe-2026/sc_tree_master.csv](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/data/sample/ev-europe-2026/sc_tree_master.csv)。
- E6 [test_stage3a2_kitting_gate.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/tests/test_stage3a2_kitting_gate.py)、[request_stage3a2_kitting_gate.md](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/requests/request_stage3a2_kitting_gate.md)。
- E7 [kitting_list_assembly.md](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/docs/design/kitting_list_assembly.md)：§6 Kanban対象外、§8の旧実装ステータス。
- E8 [plan_node.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/wom/model/plan_node.py)、[sc_tree_builder.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/wom/engine/sc_tree_builder.py)、[lot_generator.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/wom/model/lot_generator.py)。
- E9 [capacity_sealer.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/wom/engine/capacity_sealer.py)：`load_capacity_dataframe`、`build_capacity_load_report`。
- E10 [run_headless_from_folder.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/tools/run_headless_from_folder.py)：`_planning_state_extras`、401–419行付近。
- E11 [plan_copy.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/wom/engine/plan_copy.py)、[demand_anchored_lot.md](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/docs/design/demand_anchored_lot.md)。
- E12 [ppc_psi_bridge.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/wom/ppc/ppc_psi_bridge.py)：`psi_to_sales_records`。
- E13 [event_timeline.py](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/wom/engine/event_timeline.py)：計画後の表示用集計であり、pull要求の実行Controllerではない。
- E14 訂正履歴：[Phase 8-3c-2](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/requests/Phase8-3c-2_RequestLetter_CapHardSealing_to_CodeKun.md)、[Phase 8-3c-3](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/requests/Phase8-3c-3_RequestLetter_Option4_to_CodeKun.md)、[Phase 8-3c-4](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/requests/Phase8-3c-4_RequestLetter_ThroughputSeries_to_CodeKun.md)。前二件の結論を訂正後の事実として引用しない。
- E15 [レビュー対象ドラフト](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/docs/design/drafts/WOM_Composite_Node_Architecture.md)、[AGENTS.md](https://github.com/Yasushi-Osugi/wom_v1r0m0/blob/bc470b29d56e12db486e82aab7b011afe7a822f5/AGENTS.md)。

---

最初の設計成果として推奨するのは、新しいnode属性の一覧ではなく、**既存の「Lot_ID・PSI・モード・時間・制約」の意味契約と、例外／未対応条件の一覧**である。その契約で表現しきれない要求が確定したところから、Composite／Controllerの追加を個別に判断する。

````
