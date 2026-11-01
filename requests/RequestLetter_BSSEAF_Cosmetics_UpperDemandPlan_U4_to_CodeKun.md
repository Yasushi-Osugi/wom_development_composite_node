---
handoff:
  case_id: BSSEAF-COS-U4
  task_id: U4-T1-upper-demand-plan-mode1
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: c6c2994
  knowledge_used:
    - id: WOM-SEM-SUPPLY-ALLOCATION-001
      version: v0.3
      applicability: "①〜⑤ の定義と関係、U4"
    - id: WOM-KB-ALLOCATION-001
      version: v0.2
      applicability: "数量配分モード §3.1"
    - id: 上位 Demand Plan 詳細設計
      version: v0.2
      applicability: "モード 1（数量枠を固定）、段階 1・2"
    - id: WOM-KB-BSSEAF-001
      version: v0.3
      applicability: "止める理由と申し送り、記録 §4"
  acceptance:
    ref: "この依頼書 §6"
  evidence: []
  status: "試行可能"
  open_items: []
  stop_reasons: []
  handover_notes: []
  next: implement
---

# Request Letter：BS-SEAF 化粧品 U4 — 上位 Demand Plan（モード 1）の実装と、週への当て方の 3 案の試行

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-11-01）
- 版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（起草時の先頭 `c6c2994`。この依頼書は大杉さんが先に commit する。着手時の SHA を報告書に記録する）
- 出どころ：
  - 判断：`requests/BSSEAF_Cosmetics_AllocationWeekRule_U4_v0.1.md`（v0.3）§7（大杉さん、2026-11-01、全項目決定）
  - 設計：`docs/design/drafts/WOM_Upper_Demand_Plan_DetailDesign_v0.1.md`（ファイル内の版 v0.2。以下「詳細設計」）。GPT君の設計ドラフト `docs/design/drafts/WOM_Upper_Demand_Plan_U4_Design_Draft_v0.1.md`
  - 基準：配分の試行 P2-a の報告書と付録、`docs/scenarios/cosmetics.md`（C3a と P2-a の再現）
- 種別：
  - **Part A は道具のコードの追加と変更**（`wom/allocation/`、`tools/`）。**保護対象のコア**（`backward_planner.py`、`forward_planner.py`、`plan_copy.py`、`plan_node.py`、`sc_tree.py`、`push_pull.py`）**は変えない**。`wom/engine/flow_check.py` も変えない。既存の golden は変わらないこと
  - **Part B は試行**。正式サンプルは変えない。写しは `output/bsseaf_cosmetics/`（git の対象外）

---

## 0. 目的

従来の Demand Plan（需要 CSV）の**上位にある計画の機能**（上位 Demand Plan）の、最初のモード（数量枠を固定）を作る。元の需要を台帳に残し、決めた規則で供給の対象を選び、外した理由を記録し、実行の後に納品と未充足を元の要求週へ戻して照合できるようにする。

そのうえで、化粧品の P2-a2 の数量枠のまま、**代理店の需要をどの週から減らすか**の 3 案を比べる。

| 案 | 規則の名前 | 中身 |
|---|---|---|
| A0 | `proportional_early_tie` | 今のやり方の再現：需要に比例、端数が同じなら要求週の早い順に +1（結果として、減らす 1 lot は遅い週に並ぶ） |
| A0e | `proportional_even` | 需要に比例、最後に一部だけ選ぶ集団では等間隔に +1（減らす lot が期間に均等に散る） |
| A1 | `earliest_first` | 早い要求週から残し、遅い週を丸ごと減らす |

## 1. 決まっていること（U4 資料 §7）

- モード 1：SKU × チャネルの数量枠は P2-a2 のまま固定。チャネル間の数は変えない。
- 化粧品の需要は予測。対象から外した需要は繰り越さないが、台帳に残す。
- 同順位は**要求週の早い順**。CSV の行の順に頼らない。
- 納品の評価：要求週の当週と、期末までの受渡しを並べる。Window は使わない。
- 期末の未充足は結果として残し、原因を観測する。「次の計画で救える」は前提にしない。
- 変えてよいのは道具の層だけ。試行の途中で規則・固定条件を変えない。**差し戻し・修正の往復は 3 回まで**、超えたら止めて大杉さんへ戻す。
- 3 案の比較は「試すこと」の採用。業務で使う規則は結果を見て大杉さんが決める。採用の範囲は化粧品の事例。

## 2. 先に確かめること（コードを読んで。違えば止めて報告）

| # | 確かめること |
|---|---|
| B1 | `handoff.py` の `write_demand_for_quantity_allocation()` が、P2-a2 の配分で、鍵ごとに減らす 1 lot を期間の後ろの週に並べること（U4 資料 §2.1 の表：美容液 SG 2028-W33〜2029-W52 など）。鍵の中の行が週の順であること |
| B2 | 需要 CSV の `region` が leaf_out のノードの名前と一致し、identity の計画で、leaf の lot の S の週（Flow Check の表2 の `s_week`）が元の需要の要求週と一致すること。これで `source_demand_ref ＝ sku_id｜region｜request_week` に戻せる |
| B3 | `PlanNode.shippable_*` の良品の換算（C3a の開放の週：美容液 13・クリーム 10）と、leaf から工場の出荷までの LT の和（化粧品は 4 週）の読み方 |
| B4 | **Forward が、押し戻せなかった lot を後の週で作って遅配（表2 の `late`）にすることがあるか**。P2-a2 の結果の `late` の数も確かめる。これで、時間の可否の参考値と期末の未充足の関係が分かる（詳細設計 §4） |
| B5 | `tools/run_quantity_allocation.py` のどこで需要 CSV を書き、どこで計画と Flow Check を走らせているか（新しい出力を差し込む所） |

## 3. Part A：上位 Demand Plan のモード 1（詳細設計 §2〜§5・§7）

### 3.1 新しいモジュール `wom/allocation/upper_demand_plan.py`

| 関数（名前は目安） | 中身 |
|---|---|
| `build_demand_ledger(model_dir, demand_file)` | 元の需要の台帳。鍵 `source_demand_ref ＝ sku_id｜region｜request_week`（`segment` の列は空で持つ）。需要 0 の週も行を持つ。`demand_nature` は引数（化粧品は `forecast`） |
| `select_mode1(ledger, quota, week_rule, tie_key="request_week")` | 鍵ごとに s(w) を決め、選択の台帳（`q1, q2, q3, week_rule, tie_key, reason_code, quota_ref`）を返す。規則は詳細設計 §3 の 3 つ。数量枠が元の需要を超える、鍵が無いなどは今の `handoff.py` と同じ理由で止める |
| `write_engine_demand(selection, model_dir, out_path)` | 選択の台帳から、今と同じ形の需要 CSV を書く（列と行の順は元のまま）。読み戻して鍵ごとの合計を照合 |
| `time_phased_check(model_dir, selection)` | 詳細設計 §4。SKU ごと・週ごとの `need_good_lots, cap_good_lots, cum_need, cum_cap, cum_excess` と、`ontime_short_ref`、近似の条件の文字列。**名前と出力に「参考値」と分かるようにし、期末の未充足の予測として表示しない** |
| `reconcile_by_request(sc_tree, selection, flow_check_market)` | 詳細設計 §5。leaf の lot ごとに `s_week` と最初の実出荷の週を照合し（表2 と同じ方法を木から行う。`flow_check.py` は変えない）、`source_demand_ref` ごとの `q2, on_time, early, late, q5` を出す。**leaf ごとの合計が表2 と一致しなければ止める** |
| `supply_runs(sc_tree, ...)` | 実出荷の週で、leaf ごとの供給 0 の週の数・最長の連続とその開始の週。数えない週（最初の需要の週より前、元の需要が 0 の週、休業）を明示 |
| `write_plan_json(...)` | 詳細設計 §2.2 の `udp_plan.json`。`input_hashes` は入力のファイルだけ。状態は `calc_status`・`consistency_status`・`target_status`・`owner_status` を別々に（`target_status`・`owner_status` は「未判定」「未判断」のまま） |

出力の置き場所：`<out-dir>/udp/<plan_id>/`（`udp_demand_ledger.csv`、`udp_selection_ledger.csv`、`udp_capacity_check.csv`、`udp_result_by_request.csv`、`udp_supply_runs.csv`、`udp_plan.json`）。

### 3.2 既存の変更

- `wom/allocation/handoff.py`：`_largest_remainder()` の同順位の鍵を、行の番号から**呼び出し側が渡す鍵**（要求週）に変えられるようにする。既定の呼び方の結果は今と同じ。`write_demand_for_quantity_allocation()` は、新しいモジュールの `proportional_early_tie` と**全行一致**すること。
- `tools/run_quantity_allocation.py`：引数 `--week-rule {proportional_early_tie, proportional_even, earliest_first}`（既定 `proportional_early_tie`）と `--udp-out`（上位 Demand Plan の出力の場所。省略時は出さない）。省略時の動きと出力は今と同じ。`Q<nn>.json` に `week_rule` を記録。
- 配分のファイル：任意の列 `quota_source` を受け付ける（無くてもよい）。

### 3.3 テスト（新しいファイルは `tests/conftest.py` の対応表に 1 行足す）

| テスト | 中身 |
|---|---|
| 一致 | P2-a2 の配分で、`proportional_early_tie` の需要 CSV が今の `write_demand_for_quantity_allocation()` と全行一致 |
| 行の順 | 需要 CSV の行の順を入れ替えても、3 つの規則とも選択の台帳が同じ（UP-V05） |
| 規則 | 小さな合成の例で、3 規則の s(w) を手計算と照合。`proportional_even` は「端数の大きい集団から、最後の集団だけ等間隔」（詳細設計 §3）。U4 資料 §3 の A1 の減らし方（美容液 SG 2029-W41〜W52 を 0 など）を化粧品の需要で照合 |
| 台帳 | 鍵ごと・元の需要ごとに q1 ＝ q2 ＋ q3、Σq2 ＝ 数量枠（UP-V01・V02） |
| 診断 | GPT君の例：能力 5・5、需要 10・0 → 参考値 5。能力 5・5、需要 W1 8・W2 2 → 参考値 3（UP-V04）。出力に近似の条件が書かれている |
| 照合 | 小さな合成のモデルで、`reconcile_by_request` の leaf ごとの合計が表2 と一致。わざと 1 lot ずらしたら止まる |
| 再現 | 同じ入力で 2 回走らせ、`input_hashes` と出力が同じ（UP-V10） |

回す段：途中は `python -m tools.quick_check --smoke` と `--area allocation`（無ければ `tests/test_quantity_allocation.py` と新しいテスト）。**最後に `--full` を 1 回**。既存の golden（通常 15・legacy 3、化粧品を含む）が変わらないこと。

## 4. Part B：化粧品の試行（段階 2）

### 4.1 写しと入力

- 写し：正式サンプル `data/sample/cosmetics-sg-th-2027-2029` から、シナリオの文書の手順で **C3a**（`capacity_plan.csv` の全行を美容液 17／14、クリーム 13／11）を作る。**案ごとに別々の写し** `output/bsseaf_cosmetics/U4_A0`・`U4_A0e`・`U4_A1`（数量配分モードは warmup で写しのファイルを書き換えるため）。
- 数量枠：`docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/allocation/allocation_qty_P2a2.csv`（`quota_source` は「P2-a2（U3 の基準、僅差の代理店は需要に比例）」）。
- 実行：`python -m tools.run_quantity_allocation --model-dir <写し> --allocation-file <P2-a2> --week-rule <規則> --udp-out output/bsseaf_cosmetics/udp --out-dir output/bsseaf_cosmetics/_planning_state --unallocated-note "当該期間は供給の対象にしない予測需要（仮定、化粧品設計書 v0.5 D18）"`

### 4.2 見込み

| | A0 | A0e | A1 |
|---|---|---|---|
| ①②③ | 4,056・3,864・192（鍵ごとも P2-a2 と同じ） | 同じ | 同じ |
| 週ごとの ② | U4 資料 §2.1 の表 | 期間に均等 | U4 資料 §3 の A1 の減らし方 |
| ④⑤ | **P2-a2 と同じ：④ 3,856・⑤ 8（各 SKU 4）** | A0 と同じ程度か少ない（方向だけ） | 大きく増える（方向だけ。数は置かない） |
| 年齢 | 4〜28 週、52 週超 0 | 測る | 測る |
| 評価の額 | 606,739,260 円 | 測る | 測る |

A0 が P2-a2 と一致しなければ止める。

### 4.3 測ること

| # | 測ること | 出どころ |
|---|---|---|
| T1 | 案ごと・鍵ごとの ①〜⑤、④ の内訳（当週・前倒し・遅配） | 選択の台帳、`udp_result_by_request.csv`、Q json |
| T2 | 要求週ごとの ②・当週・遅配・⑤ と、**当週の充足率（元の需要が分母。分母 0 は「対象なし」）**。代理店 4 鍵は期間の終わりの 26 週を表に、全期間は付録の CSV に | `udp_result_by_request.csv` |
| T3 | **時間の可否の参考値・期末の未充足 ⑤・遅配の 3 つを並べた表**（SKU ごと、案ごと）と、差の説明 | `udp_capacity_check.csv`、T1 |
| T4 | 代理店ごとの供給 0 の週の数・最長の連続とその開始の週 | `udp_supply_runs.csv` |
| T5 | 工場の週ごとの能力の余り（期間の終わりの 20 週） | 工場の PSI、`udp_capacity_check.csv` |
| T6 | 先入れ先出しの年齢 最小／最大、52 週超 | `tools/shelf_life_check.py --demand-file <生成した需要 CSV> --warmup-real-start <元の需要の基準>` |
| T7 | 評価の額と、③・⑤ の逸失（P2-a と同じ式・単価・固定費の相当額 213,719,220 円） | P2-a の付録の `evaluate.py` |
| T8 | 期間・能力・元の需要の固定が守られた | 数量配分モードの検査 |
| T9 | ⑤ になった lot の鍵・要求週の内訳（どのチャネルのどの週の需要が届かなかったか） | `udp_result_by_request.csv` |

**まとめの表**（報告書 §3）：案 × {②③④⑤、当週の充足率（全体・代理店）、参考値、遅配、供給 0 の最長の連続、年齢の最大、評価の額、P2-a2 との差}。

## 5. 止める理由と申し送り

報告では、**止める理由**（動き・数字・誤読に関わる。先に直す）と**申し送り**（記録して進む）を分ける。些細なものは往復させずに直して報告だけにする。

止める理由に当たるもの：

- §2 の確かめが設計と違う（とくに B2：要求週に戻せない）
- `proportional_early_tie` が今の結果と全行一致しない、既定の動きが変わる、既存の golden が変わる
- A0 が P2-a2（④ 3,856・⑤ 8）を再現しない
- 要求週ごとの照合が表2 と合わない、①＝②＋③・②＝④＋⑤ が成り立たない
- 期間・能力・元の需要の固定が破れる
- 保護対象のコアか `flow_check.py` を変えないと実装できない
- 差し戻し・修正の往復が 3 回を超える

**⑤ が増えること・業務の目標に届かないことは、止める理由ではない**（結果として残す）。

申し送りの例：時間の可否の参考値とエンジンの ⑤ の差の原因、遅配の扱い、モード 2・優先度の方針（段階 3）に要るもの。

## 6. 受入条件

| # | 条件 | 詳細設計 |
|---|---|---|
| S1 | §2 の B1〜B5 の結果が報告書にある | — |
| S2 | 台帳と選択：全部の元の需要が台帳にあり、選択の台帳の全行に規則と理由がある。鍵・元の需要ごとに ①＝②＋③ | UP-V01・V02 |
| S3 | 一致と再現：`proportional_early_tie` が今と全行一致。A0 が P2-a2 を再現 | UP-V03 |
| S4 | 規則と診断の手計算の照合 | UP-V04 |
| S5 | 行の順への非依存 | UP-V05 |
| S6 | 生成後の Lot の重複・消失なし、要求週ごとの ④⑤ が表2 と leaf ごとに一致、②＝④＋⑤ | UP-V06・V07 |
| S7 | `udp_plan.json` の入力のハッシュと 4 つの状態、同じ入力の再実行で同じ結果 | UP-V10 |
| S8 | Part B の T1〜T9 とまとめの表 | — |
| S9 | 回帰：既存の golden が変わらない。`--full` が通る | — |

## 7. 報告書と記録

- 報告書：`docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_Report.md`（付録 `..._appendix/`：選択の台帳・要求週ごとの結果・診断の CSV、試行のスクリプト）。**冒頭に引き継ぎの欄（YAML）**を付ける（`docs/design/WOM_BSSEAF_MultiAI_Loop_Design_v0.1.md` §2 の形。`status` は結果に合わせて、`next: owner`）。
- 中身：着手時の SHA、§2 の結果、作ったもの、§6 の S1〜S9、§4.3 の表、止める理由と申し送り、大杉さんに決めてほしいこと（あれば）。
- **BS-SEAF の記録**（`docs/bsseaf/WOM_BSSEAF_Process_Knowledge.md` §4 の形）：変えたもの（手段：道具）、再利用した知識（どの文書から辿ったか）、誤りの型、往復の回数、**実作業の時間と待ち時間**、**人の橋渡し**（転記・連絡／git の操作／業務の判断／レビューへの対応）、見込みどおりか。
- commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に書く。依頼書・実装・報告書の commit の分け方は今までどおり。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-01 | 初版 |
