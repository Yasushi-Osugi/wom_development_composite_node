---
knowledge_id: WOM-KB-ALLOCATION-001
title: WOM 生産配分と優先供給の三層構造
version: "0.1"
updated: "2026-10-26"
evidence_commit: "b120fdb4679878005e94f2e2cffec94fcce65009"
verification_scope: "repository documents and static code inspection"
cosmetics_activation: "not yet verified"
keywords: [生産配分, 優先供給, 市場優先, 需給調整, 親心, Demand Allocation, Supply Allocation, Capacity Envelope, Backward PSI Planning, Forward PSI Planning, allocation_id, planning_state, BS-SEAF]
---

# WOM 生産配分と優先供給の三層構造

本書は、設計担当のClaude君と新しく参加するAIに、WOMに既存の生産配分機能を発見・再利用してもらうための設計MDである。Backwardで「供給したい配分計画」を作り、Forwardで「制約下で実際に供給できる計画」を求める、という大杉さんの役割分担を基本とする。

**生産配分を扱う三層と、その層間連携の実装はWOMの既存機能群に存在する。新しい事例で優先供給が実現していない場合は、既存機能の適用条件・設定・呼び出し・受け渡しを調べ、その結果から変更範囲を判断する。**

ここでいう「標準機能」は、リポジトリに実装がある既存機能群を指す。すべてのモデル・起動経路で自動的に有効になる、という意味ではない。今回の化粧品試行で各機能が使用され、意図した優先供給が実現したかは、別に検証する。

- 作成日：2026-10-26（日本時間）
- 作成：ChatGPT Codex。依頼・業務方針：大杉さん。引き継ぎ先：Claude君（設計）
- 確認対象：`Yasushi-Osugi/wom_development_composite_node`、`wom-v1r5m1_cap_trial`
- 根拠の固定版：`b120fdb4679878005e94f2e2cffec94fcce65009`
- 確認方法：資料・コード・既存テストの記述を静的に確認。今回、新たなシミュレーション・pytest・GUI検証は実施していない
- 文書の範囲：役割分担、既存機能へのポインタ、化粧品への適用調査、知識の記録方法。エンジン変更の依頼書や、化粧品の新しい採用決定そのものではない

## 1 最初に理解すること

| 段階 | 業務として決めること | 既存の仕組み | 主な出力 |
|---|---|---|---|
| Management | Global HQが、どの市場・販売チャネルに、どれだけ供給するかを判断する | `wom/allocation/`の利益評価・配分比較。選択した配分をハンドオフする | 市場別配分、選択根拠、配分済み需要CSV |
| Demand | 配分済み需要を、いつ・どの工場で生産・調達するかに展開する | Backward PSI Planning。LT offset、需要集約、MOM振り分け、能力を考慮した前倒し配置 | `psi4demand`のS・P、計画開始前に必要となる需要、能力関連の記録 |
| Supply | その計画に対し、制約下でいつ・何を実際に供給できるかを求める | Demand→SupplyコピーとForward PSI Planning。Lot_ID照合、実出荷の伝播、在庫・注文残の計算 | `psi4supply`、実出荷、遅配・注文残、評価結果 |

Global HQの「親心」は、利益やサービス方針を踏まえて、供給したい配分を選ぶ判断である。その意思を需要データや配置としてBackwardに渡す。Forwardは配置を受け取り、時間を遡らずに制約下の結果を計算する。結果を受けて再配分を選ぶ場合は、新しい計画案として記録する。

本書の三層は「生産配分の判断・配置・実現」の区別である。WOM全体のPhysical／Planning／Managementというアーキテクチャの三層とは、分類の目的が異なる。

## 2 既存機能を見つけるためのポインタ

以下の機能IDは本書で付ける知識索引であり、既存コードに同名のIDが実装されているという意味ではない。

| 知識上の機能ID | 機能 | 最初に読む実装 | 状態と適用上の注意 |
|---|---|---|---|
| WOM-ALLOC-01 | 利益に基づく市場配分の比較・候補生成 | [merit_order.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/wom/allocation/merit_order.py)、[grid.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/wom/allocation/grid.py) | 実装あり。単位マージン順、連続解、格子評価等の前提を区別する。化粧品での有効化は未確認 |
| WOM-ALLOC-02 | 選択配分から計画用需要を生成する | [handoff.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/wom/allocation/handoff.py)の`write_demand_for_allocation()` | 実装あり。`demand_forecast_<allocation_id>.csv`を生成する。期間・単位・SKUの適用確認が必要 |
| WOM-ALLOC-03 | 配分需要のLT調整・集約・生産配置 | [backward_planner.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/wom/engine/backward_planner.py) | 実装あり。`demand_envelope`等の設定で能力の扱いが変わる。標準の能力クリップ自体は利益順位を計算しない |
| WOM-ALLOC-04 | DemandからSupplyへの計画引き継ぎ | [plan_copy.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/wom/engine/plan_copy.py)の`copy_demand_to_supply()` | 実装あり。各ノード・各週のS・Pをコピーし、SupplyのI・COはForwardで計算する |
| WOM-ALLOC-05 | 供給制約下の実現結果の計算 | [forward_planner.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/wom/engine/forward_planner.py) | 実装あり。要求Sと実出荷を区別する。identityモードのLot_ID照合を確認する |
| WOM-ALLOC-06 | 三層連携の実行と計画案の記録 | [run_planning_loop.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/tools/run_planning_loop.py)、[planning_state](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/wom/planning_state/__init__.py) | 明示的に利用する既存CLI経路あり。すべての通常実行がこの経路を通るわけではない |

補助資料：

- [利益配分の仕様](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/docs/design/ask_global_allocation_spec.md)
- [Phase 7の層間連携依頼書](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/requests/Phase7_RequestLetter_to_CodeKun.md)
- [Phase 7aの評価・記録の訂正](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/requests/Phase7a_Addendum_to_CodeKun.md)
- [計画の正典](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md)
- [2026-08-20の三層設計記録](three_layer_production_allocation.md)。当時の調査として読む。「三層が未接続」という記述を、後に実装されたハンドオフやCLIにも適用しない

## 3 現行の層間連携経路

`tools/run_planning_loop.py`には、次の経路が実装されている。

1. 原価・市場需要・シナリオから、複数の配分候補と評価値を計算する。
2. `--allocation`による明示配分、または`--from`で指定した候補を選択する。
3. `allocation_id`を持つ`planning_state`を`pre_plan`として保存する。
4. `write_demand_for_allocation()`で配分済み需要CSVを生成する。
5. `run_headless(..., demand_file=<生成CSV>, planning_state=True)`に渡す。
6. この中でBackward→フック→Demand／Supplyコピー→フック→Forwardを実行し、PPC評価を行う。
7. 配置・評価結果を計画案に追記して保存する。

このCLIがあるため、「ManagementからPlanningへの受け渡し自体が存在しない」という一般化は正しくない。一方、通常の`run_headless()`が元の需要CSVを読むだけで、自動的に利益配分まで決めるわけでもない。

現行CLIは、配分を明示しない場合に`P_opt`を既定候補にする。人間が採用した配分を試すときは、採用元・市場の並び・比率を記録し、その選択が実行に使われたことを確認する。自動選択の結果を、人間が採用済みの方針として記録しない。

既存CLIの利用例を次に示す。これは対応済みの醤油モデルを作業用コピーに置いた場合の例であり、今回実行したコマンドではない。

```bash
python -m tools.run_planning_loop --model-dir output/allocation_review/soysauce-jpy-2027-alloc --scenario s1_base --cap-wk 800 --allocation 0.10,0.45,0.45 --out-dir output/allocation_review/states --ppc-out output/allocation_review/ppc
```

配分値の順は`markets_of(blocks)`の順である。実行前に市場名との対応を確認する。ハンドオフはモデルフォルダへ生成CSVを書き、warmupも作業用ファイルを扱うため、正式なサンプルを直接書き換える運用例にはしない。

## 4 業務の意味を保つためのルール

| ルールID | 定義 | 確認する証拠 |
|---|---|---|
| PA-R01 | Managementで選択した配分と、その採用理由を記録する | `allocation_id`、採用元、入力条件、人間の判断 |
| PA-R02 | Backwardは配分済み需要を生産・調達の位置へ展開する | LT offset、集約結果、MOMの配置、能力設定 |
| PA-R03 | ForwardはBackwardの配置を受け、時間を遡らず供給を計算する | コピー結果、部材・入荷・能力・休業、実出荷 |
| PA-R04 | 要求Sと実出荷は別の情報として扱う | `psi4supply[S]`と`_actual_ship`等の出荷記録の照合 |
| PA-R05 | 元需要、配分済み需要、実納品を分ける | 元需要の保存、配分前後の対応表、実納品の記録 |
| PA-R06 | 未配分需要と、配分したが供給できなかった需要を分ける | 配分時の数量差、計画末の未充足ID、遅配 |
| PA-R07 | 能力の定義と、制約を守る方式を明記する | hard／soft、投入／良品、歩留まり、`demand_envelope` |
| PA-R08 | 利益の評価基準を明記する | 利益率、単位マージン、資源当たり利益等のどれを採るか |
| PA-R09 | 機能の存在と、対象ケースでの有効化・接続・検証を別々に記録する | コード参照、設定、実行経路、試行結果 |
| PA-R10 | 既存機能の適用と接続を調べてから、必要な変更範囲を決める | Data／Parameter／Coreの根拠、アダプターの対応候補 |

### 4.1 実行可能性の意味

Forwardは、モデルに設定された制約の下で実現できる供給量・供給時期を計算し、配分計画を満たせない部分を明らかにする。すべての配分需要を納期どおり満たせること、利益が最大になること、現実の未設定の制約まで満たすことは、別の確認事項である。

現行`planning_state`の`feasible_plan`は、`attach_realized()`が結果を添付した際に設定する状態名である。この状態名だけを、全需要充足・違反ゼロ・人間の受入済みという判定に使わない。

### 4.2 能力と優先順位の意味

Backwardの`demand_envelope=soft`は、設定されたcap_softに対応する良品上限まで配置し、超過を前倒しする。既定のhardモードではcap_hardを基準にし、cap_soft超過は記録する。Forwardでもcap_hardによる制限とcap_soft超過の記録を区別する。cap_softは、設定しただけで常に強制上限として作用するわけではない。

`lane_assignment.csv`の優先欄、MOMへの振り分け、市場への供給順位は同じ意味ではない。どの入力が、どの処理で参照されるかを調べる。市場優先を持たせたいという要求に対し、列名だけを根拠に「対応済み」と判断しない。

既存メリットオーダーは単位マージンを使う。「利益率が高い市場を優先」という方針を適用する際は、率と金額のどちらを意味するかを大杉さんとそろえる。製品ごとに資源使用量が異なる場合は、何を1単位の能力とするかも定義する。

## 5 化粧品試行の位置づけ

変更課題①②③の報告書は、Coreを変えずに実行したデータ試行の記録である。金額は置かず、C3aでは能力不足によりタイ代理店の需要が注文残になったと報告している。

| ケース | 報告された観測 | 生産配分の検証として読む際の範囲 |
|---|---|---|
| C3a | 美容液104・クリーム88 lotの期末注文残。すべてタイ向け。FIFO年齢最大28週 | 不足時の実行挙動を調べる基準。タイを後回しにする経営方針が採用された証拠とはしない |
| C3a26 | warmupを26週にすると注文残0、FIFO年齢最大36週 | 同じ週当たり能力で、先行生産を深くした有限期間の案 |
| C3b | 必要能力を再計算し、注文残・工場完成品倉庫の作り置きが0 | 能力を増やした案。優先順位の効果を単独で測る試行にはならない |

根拠：[変更課題①②③の報告書](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/docs/development/WOM_BSSEAF_Cosmetics_ChangeTasks123_Report.md)、[化粧品設計v0.4](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.4.md)。数値は報告書の記録であり、今回独立に再実行した結果ではない。

報告書の「市場優先の規則はWOMに無くCoreの課題になる」という一般化は、既存配分・ハンドオフ・計画案記録を参照して再検討する。報告された試行結果は保存し、解釈の訂正を別に追記する。

warmupに関しても「能力不足には使用しない」を一般則として採用しない。必要な期間の先行生産が可能か、保管期間・量が許容されるか、需要と供給の累積で検討する。期間を延ばすと不足が再発するかは別に測る。本書はD7・D7aや大杉さんの採用決定を変更しない。

## 6 化粧品へ既存機能を適用する前の確認事項

| ID | 調査事項 | 現時点で分かっていることと確認する内容 |
|---|---|---|
| ALC-Q01 | 実行経路 | 実際の`gen_models.py`・`run_trial.py`、モデル設定、呼び出し引数を確認する。これらの試行用ファイルは`output/`にあり、今回のGit確認対象には含まれない |
| ALC-Q02 | 元需要と配分済み需要 | `demand_file`に何を渡したか、どの`allocation_id`・配分方針を採ったか。元需要を残したか |
| ALC-Q03 | 3年間の計画期間 | 既存配分コードは`WEEKS=104`を使う箇所があり、ハンドオフにも`weeks`の既定値がある。3年間とwarmup・報告期間に対して、能力総量と需要集計の期間をそろえる |
| ALC-Q04 | 2 SKUと能力プール | 化粧品はSKU別能力。既存ハンドオフはregion・weekで数量を扱う箇所があり、SKUをキーに含めない。同じregion・weekに複数SKU行がある場合の保持を確認する。単位が同じだけでSKU別能力を一つに合算しない。原価導出の単一SKU前提も仕様書で確認する |
| ALC-Q05 | 実納品の観測 | 現行`_planning_state_extras()`の`leaf_out_S`・週次Sは要求Sを集計し、`leaf_out_CO`は週次COを合計している。これを実出荷や計画末の未充足数量と同一視せず、実出荷記録・最終週COと照合する |
| ALC-Q06 | 利益基準と金額入力 | 利益率か単位マージンか、通貨・物量単位・歩留まりによる良品原価を定義する。D8と歩留まりPart Bの状態を確認し、未整備の金額で化粧品の利益優先を検証済みにしない |
| ALC-Q07 | 配置時の優先の保持 | Managementの配分数量が前倒し・能力クリップを通過した後も意図どおりか。配分CSVを作っただけで、すべての週の優先順も保証されるとしない |
| ALC-Q08 | 期限・在庫と再計画 | FIFOで測る製品年齢、店頭在庫、warmup、休業の影響を一緒に確認する。変える条件と固定する条件を記録する |

ALC-Q05は、静的確認で見つかった記録の意味を確認する課題である。実行結果の欠陥を今回再現したという主張ではない。`attach_realized()`には数量一致の検査もあるため、不足時にどこまで結果を記録できるかを確かめる。

ALC-Q03・04は、既存機能の適用範囲の差である。まず設定・データの分離や既存APIの引数で対応できるかを調べる。足りない場合も、ハンドオフや観測アダプターの変更とPSIエンジンCoreの変更を分けて設計する。

## 7 Claude君に引き継ぐ調査と試行の設計

### 7.1 最初に作る対応表

Claude君はALC-Q01〜08について、入力ファイル、設定、呼び出し、出力、根拠のcommit、確認状態を記録する。最初の成果物は「既存機能で対応できる範囲」「対象ケースへの接続に必要な作業」「なお不足する表現」の対応表とする。

現在の化粧品モデルへの適用状況を確認する前に、新しい優先供給機能をCoreへ追加する依頼書を作らない。必要性が分かった場合は、実装箇所・代替案・意味を保つ理由を示して次の依頼書にする。

### 7.2 試行の構成案

以下は設計案であり、未実行である。作業用コピーを使い、元需要、能力、期間、歩留まり、LT、在庫方針、プラグインを記録する。

| 試行 | 変えるもの | 確認すること |
|---|---|---|
| P0 | C3a相当を再現 | 元需要・能力不足・実出荷・期末注文残を再確認し、現在の処理順による結果を基準にする |
| P1 | 明示した市場別配分を、既存ハンドオフ経路で渡す | 元需要→採用配分→Backward配置→Forward納品の対応を追えるか |
| P2 | 配分方針を変える | 同じ能力と元需要の下で、意図した市場の配分量が変わり、その効果が実納品に現れるか |
| P3 | 入力の行順・ノード登録順だけを変える | 業務判断と無関係な順序が結果に影響するか。影響する場合、同順位の扱いを含めて説明できるか |
| P4 | 配分後に供給制約を厳しくする | 配分したが供給できない数量・遅配が残り、実出荷を過大計上しないか |
| P5 | 新しい条件へ再利用する | 知識索引から既存機能を見つけられ、追加質問・設定変更・差分分類を記録できるか |

利益順位を変える試行は、金額・歩留まり原価の前提が整った後に行う。先に明示配分で接続を確認する場合は、その試行で利益による選択まで検証したとは扱わない。能力を増やすC3bは対照として保存し、P1〜P4の不足条件を途中で解消しない。

### 7.3 数量と識別子の照合

各SKU・市場・報告期間について、以下を別々に記録する。

- 元需要数量と、配分済み需要数量
- 配分時点で供給対象にしなかった数量と理由
- 配分済み需要に対する納期内出荷、遅配出荷、計画末の未充足
- 能力制限による生産の繰延べ、在庫、製品年齢

同じ需要のCOを毎週足すと「lot×週」の滞留量になる場合がある。これを期末注文残のlot数として使わない。計画末の未充足は最終状態の需要IDと実出荷から照合する。

ハンドオフは需要CSVの数量を変えてから需要Lotを生成するため、配分前後のLot_IDがそのまま一致するとは仮定しない。SKU・leaf_out・要求週・元需要参照・数量対応を残し、生成後のDemand→SupplyではIDの同一性を確認する。

## 8 BS-SEAFの知識記録

### 8.1 機能の存在と適用状態を別に持つ

機能を発見したことと、その事例で動いたことを別々に記録する。最小の記録形式は次のとおりとする。これは記録仕様案であり、実行時スキーマを新規実装したものではない。

```yaml
knowledge_id: WOM-KB-ALLOCATION-001
capability_id: WOM-ALLOC-02
business_rule_ids: [PA-R05, PA-R06, PA-R09]
implementation_status: present
case_id: cosmetics_c3a_priority_trial
activation_status: unverified
connection_status: unverified
validation_status: not_run
evidence_commit: b120fdb4679878005e94f2e2cffec94fcce65009
evidence_paths:
  - wom/allocation/handoff.py
  - tools/run_planning_loop.py
applicability_questions: [ALC-Q02, ALC-Q03, ALC-Q04]
owner_decision: pending_case_application
```

確認が進んだら、推測で`verified`にせず、設定・実行ID・出力・検証条件・採否の根拠を添えて状態を更新する。Data／Parameter／Coreの差分分類に加え、変更対象が知識文書・ハンドオフ・観測・PSIエンジンのどこかも記録する。

### 8.2 今回、訂正して残す知識

1. 「WOMには市場優先の配分機能がない」という説明は訂正する。既存の配分・ハンドオフ・計画案記録へのポインタを付ける。
2. 「三層が未接続」は2026-08-20の調査時点の記述として保存する。後のCSVハンドオフとCLI実装があることを追記する。
3. 「タイの注文残が出た」から「新しい市場優先Coreが必要」と直結させない。今回のケースが既存機能を通ったかを先に調べる。
4. 「最大利益の配分候補」「人間が採用した配分」「制約下で実現した配分」を別々に保存する。
5. `feasible_plan`という名前やS・COという集計列名から、受入済み・実納品・期末未充足という意味を推測しない。

## 9 新しく参加するAIの読解手順

1. [WOM Start Here](../WOM_Start_Here.md)の生産配分の入口とR20から本書に進み、対象checkoutのブランチ・commitを確認する。
2. 本書§1〜3で三層の役割と既存のハンドオフを確認する。
3. 対象ケースについて、元需要・配分方針・実行経路を特定する。
4. 該当する機能IDとALC-Qを使い、実装の存在・有効化・接続・検証を分けて確認する。
5. 未対応という判断には、調べた既存機能、適用できない理由、根拠の固定版を添える。
6. 採用した判断と検証結果を、対象ケースの報告書と再利用可能な知識へ戻す。

読解確認では、新しいセッションのAIが、Start Hereから配分・ハンドオフ・Backward・Forward・計画案記録に辿り着き、各段階の役割、化粧品での未確認事項、要求と実出荷の違いを説明できるかを見る。手作業のリンク確認と、新規AIによる読解試行は別の検証として記録する。

根拠リンクは調査時点を再現する固定版である。再利用先のcommitが異なる場合は、該当する実装・設定・テストの差分を確認してから判断し、必要に応じて本書の確認日・根拠commit・適用状態を更新する。front matterのキーワードとIDは人とAIが検索するための索引であり、現行エンジンが自動解析する設定ではない。

## 10 完了条件と次の成果物

本書と知識索引の整備の完了条件は、Start Hereから本書を開け、根拠コード・設計・既存テストへ辿れること、履歴の記述と現行の実装を区別できることである。

化粧品への適用調査の完了条件は、ALC-Q01〜08の確認結果、試行P0〜P4の実施範囲、元需要・採用配分・配置・納品の対応、残った差分をClaude君が報告できることである。未実施項目は未実施として残す。

既存テストの参照先：

- [test_allocation_merit_order.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/tests/test_allocation_merit_order.py)：利益配分の評価
- [test_planning_state.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/tests/test_planning_state.py)：配分ハンドオフ、丸め、ゼロ週、状態遷移、既存CLIの一巡
- [test_demand_envelope_soft.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/tests/test_demand_envelope_soft.py)：softモードの前倒し配置
- [test_lot_identity_flow.py](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/tests/test_lot_identity_flow.py)：要求と供給のID照合

上記は既存テストの所在であり、本書作成時の実行結果ではない。実装変更が必要になった場合は[AGENTS.md](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/b120fdb4679878005e94f2e2cffec94fcce65009/AGENTS.md)と該当依頼書に従って、変更内容に対応する検証を行う。

| 版 | 日付 | 内容 |
|---|---|---|
| 0.1 | 2026-10-26 | 既存三層機能、CSVハンドオフ・CLI、適用条件、化粧品の接続調査、Start Hereからの知識索引を整理 |
