# 公開の前のサンプルの見直し：実在の名前を一般名にする — 報告

- 依頼書：`requests/RequestLetter_SampleNames_PublicReview_to_CodeKun.md`
- 基準：`wom-v1r5m1_cap_trial` **de8e18d**。作業日 2026-10-09。commit・push はしていない。
- **この報告書には元の実名を書かない**（件数と、置き換えた後の名前だけ）。
- 対応表・棚卸し・照合の生データは git の対象外の **`output/sample_names/`** にある（下の §6）。

## 0. 結論

| ID | 検査 | 結果 |
|---|---|---|
| N-1 | `tests/test_no_real_names.py` が緑（公開の一覧） | **合**（20 件緑）。手元の一覧は Owner の実機で確かめる（仕組みは仮の一覧で確認済み、§4） |
| N-2 | 全サンプルを headless（`--plugins` 省略）で前後に実行し、名前を対応表で写して psi・ppc・forward が一致 | **合**：当時の 16 モデルすべて（いまは 15。§9）、psi・ppc・forward・backward・period・products・config が一致 |
| N-3 | smartphone の golden を新しい名前で作り直し、値は同じ。ほかの canonical・legacy は不変 | **合**：作り直した golden は、元の golden を対応表で写したものと**全キーで一致**。ほかの canonical 12 件・legacy 3 件は触っていない（全テストで緑） |
| N-4 | 新しい golden が緑 | **合**（作った 3 件のうち 1 件は §9 で削除。残る 2 件が緑） |
| N-5 | GUI：smartphone と Cookie を読み込んで計画、World Map・PSI List が描ける | **合**（例外 0、PSI は golden と一致） |
| N-6 | 全テストを単独で実行して緑 | **合**：**888 passed、3 skipped**（25 分 46 秒、単独で実行。うち名前のテスト 20 件、新しい golden 3 件） |
| N-7 | コミットに入るファイルに元の実名が無い | **合**（N-1 のテストが、追跡するファイルと新しく足すファイルの全部を検査。この報告書・依頼書も含む） |

## 1. 棚卸し

- 対象：git が追跡するテキストのファイル 1,127 件（地図のデータ `data/worldmap_ne/` と画像などのバイナリは除く）。中身と**ファイル名**の両方。
- 予備の一覧の語に加えて、企業・ブランド・団体の候補（自動車・電機・半導体・食品・小売・物流・石油・農業団体など、英語と日本語で約 200 語）を広く探し、ノード名・説明・note 列・コメント・ファイル名を文脈で確かめた。
- 誤検出として外したもの：都市名の中の部分一致（欧州の港の都市の日本語表記、スペインの都市名）、CSS のフォント指定、英単語の一部、日本語の識別子の接尾辞 `_JA`（日本語の意）など。
- 結果は `output/sample_names/inventory.csv`（ファイル・行・種類・実名・一般名）。

## 2. 置き換え

### 2.1 件数（種類別）

| 種類 | 置き換えの数 | ファイル数 | 置き換えた後の名前 |
|---|---:|---:|---|
| スマートフォン（製品・モデル・ブランド） | 3,827 | 145 | `Phone15`・`Phone16`・`Phone17`、`Smartphone`／`smartphone`、モデル `smartphone-global-2026-2029`、PPC のシナリオ名 `smartphone_global`・`smartphone_vs`、SoC は `Phone15 SoC` など |
| EMS（組立の受託） | 657 | 34 | `EMS_A`（`EMS_A_CN`・`EMS_A_IN` など） |
| 半導体 | 100 | 23 | `Foundry_A`（`Foundry_A_TW` など）、`Foundry_A Fab B`、`Supplier_TW_B`、`Supplier_US_A` |
| 電機・部品 | 29 | 18 | `Sensor_A`（`Sensor_A_IN`）、`Supplier_KR_A` |
| アパレル | 62 | 9 | `Retailer_A`（オフショア型）、`Retailer_B`（垂直統合型） |
| 農業団体・協同組合 | 19 | 9 | `産地の集荷団体（新潟）`・`産地の集荷団体（北海道）`、`Coop_Seihaku` |
| コンビニ | 1 | 1 | `大手チェーン等` |
| 自動車・電池・菓子・石油メジャー（CLAUDE.md の過去の記録） | 40 | 1 | 記述を一般化（`EVmaker_Local`／`EVmaker_Import` ほか、旧SKU名・旧ノード名、石油メジャーA・B） |
| **計** | **4,735** | **163** | |

- 同じ実名には全ファイルで同じ一般名を使った（規則は順序つきの一覧 1 つ。`output/sample_names/rename_rules.py`）。
- 過去の報告書・依頼書・測定の記録（json・csv）は**名前だけ**を置き換え、文は変えていない。
- CLAUDE.md の過去の記録（EV のブランド名の匿名化、Cookie の旧SKU名、石油のシナリオ）は、旧名と新名の対応そのものが書かれていたので、旧名を除いて「旧SKU名」「旧ノード名」と一般化した。
- コードの中の名前（PPC のシナリオの判定に製品名・チャネル名を使っている `wom/ppc/ppc_engine.py`・`ppc_runner.py`、関数名 `build_smartphone_global_vs_paths`・`build_smartphone_vs_paths`、テストの名前）も同じ規則でそろえた。値が変わらないことは N-2・N-3 で確かめた。
- **保護対象のコア**：`wom/engine/backward_planner.py`（1 行）・`forward_planner.py`（2 行）・`push_pull.py`（2 行）の**コメントだけ**に実名（ノード名の例と依頼書の名前）があったので、コメントを置き換えた。コードは変えていない（差分は 5 行、すべて `#` のコメントか docstring）。**Owner の差分レビューをお願いします。**

### 2.2 名前を変えたファイル・フォルダ（新しい名前）

- `data/sample/smartphone-global-2026-2029/`（golden のあるスマートフォンのモデル。22 ファイル）
- `tests/golden/smartphone-global-2026-2029.json`（作り直し、§3）
- `requests/RequestLetter_SmartphoneWarmup_EVUpdateKitting_S2_to_CodeKun.md`
- `docs/development/WOM_SmartphoneWarmup_EVUpdateKitting_S2_Report.md`
- `docs/development/smartphone_evupdate_s2/`（13 ファイル。うち `A_smartphone_backlog_nodes.csv`・`A_smartphone_warmup_trial.csv` はファイル名も変更）
- `requests/apparel-us-2026-retailer-a-request-letter.md`・`requests/apparel-us-2026-retailer-b-request-letter.md`
- 画像 3 件：`docs/development/worldmap_actual_flows/smartphone_world.png`、`docs/development/sim_mgmt_worldmap/screens/smartphone-global-2026-2029__World.png`、`docs/development/sim_mgmt_worldmap/part1/kpi__smartphone-global-2026-2029__after__1280x720__All.png`

参照しているところ（道具・テスト・文書）は §2.1 の規則で同時に直した。

### 2.3 削除したもの

- **スマートフォンのモデルの古い方**（golden 無し、PPC が CNY の為替で止まるモデル）のフォルダ 9 ファイル。文書では `smartphone-legacy` と呼び、過去の記録には「2026-10-09 削除済み」と注記した（CLAUDE.md・`docs/design/wom_model_typology.md`・過去の報告書 3 件）。`docs/architecture/repository_map.md` と README のモデルの一覧からは外した（README の「全18ケース」→「全16ケース」：`data/sample/` の計画できるモデルは 16）。

### 2.4 モデルの名前（主な文書）

- README のサンプルの表：スマートフォンの行を `smartphone-global-2026-2029` に。
- CLAUDE.md：モデル名・ノード名を一般名に。golden の再生成の注記、golden の無いモデルの記述（3 つは golden を作った、旧モデルは削除）を更新。
- `docs/WOM_Start_Here.md`：**名前の置き換えだけ**（4 行）。
- AGENTS.md・`docs/README.md`：実名もモデル名の一覧も無く、変更なし。

## 3. golden

| モデル | 何をしたか | 組（`--plugins` は明示） | period | 粗利率 |
|---|---|---|---|---:|
| smartphone-global-2026-2029 | 作り直し。元の golden を対応表で写したものと全キー（psi・ppc・forward・backward・period・products・config・case）が一致 | Holiday Calendar・Buffering Stock・Capacity Override | 2026-W28〜182 週 | 41.19% |
| ev-thailand-2026_update | **新規** | 同上（`recommended_plugins` の `safe`） | 2025-W37〜121 週 | 56.50% |
| soysauce-jpy-2027-alloc | **新規**（Value Chain の手本） | 同上 | 2026-W28〜130 週 | 26.09% |

- 新しい golden の組は、Owner の決定（golden の無いモデルは `safe`）と同じなので、`tests/test_public_readiness.py` の期待（`recommended_plugins`＝golden の組）はそのまま満たす。テストの変更は不要だった。
- これで golden の無いモデルは無くなった（canonical 15 件、legacy 3 件。§9 の削除の後）。

## 4. 再発を防ぐテスト

- `tests/test_no_real_names.py`（20 件）：
  - 追跡するテキストのファイル（`git ls-files --cached --others --exclude-standard`：まだ add していない新しいファイルも含む）の中身と**ファイル名**に、禁止の語が無いこと。地図のデータ・画像などのバイナリ・語の一覧のファイル自身は除く。
  - **公開の一覧** `tests/data/real_name_denylist.txt`：世間に広く知られた名前だけ（29 語）＋許す語句 2 つ（都市名の日本語表記、CSS のフォント指定）。
  - **手元だけの一覧** `private/real_name_denylist.txt`（`.gitignore` に `/private/` を追加）：あれば読み、無ければ黙って飛ばす。当たったときは「word No. n of the private list」と**番号だけ**を出す（語は出さない）。`private/` が git に無視されることもテストする。仮の一覧で、番号だけが出ること・git の対象外になることを確かめた（仮の一覧は削除済み）。
  - 一般名（`EMS_A_CN`・`Foundry_A_TW`・`Phone16`・`Retailer_B型`・`Coop_Seihaku`・`産地の集荷団体（新潟）` など）や、誤検出しやすい語（都市名・英単語）が禁止にならないこと。
  - 一覧の各語が、大文字・小文字・`_TW`・`16`・`型` を付けた形でも見つかること（このテストのファイル自身に実名を書かないため、一覧から作る）。
- 照合の規則：ASCII の英字で始まる・終わる語は、前後が英字のときは当たらない（長い英単語の一部は外す）。数字と `_` は付いていても当たる。
- **手元の一覧の候補**（世間に広く知られていないので公開の一覧に入れなかった実名）は `output/sample_names/private_list_suggestion.txt` に置いた。Owner が `private/real_name_denylist.txt` に写すかを決める。

## 5. Owner に判断をお願いすること

1. **画像の中の実名**：テキストの検査の対象外だが、スマートフォンのモデルの古い画面の画像 3 件（§2.2 の画像）は、画面の中に元の名前が写っている（目で確かめた）。ほかの画像（全 135 件）は 1 枚ずつは確かめていない。新しい名前の画面は今回の GUI の確認で撮った（`docs/development/sample_names/gui/`）。古い画像を差し替える・消す・残すのどれにするか。
2. **置き換えなかった実名の種類**（一覧は `output/sample_names/kept_names.txt`）：開発に使う AI・道具の名前、競合の計画ソフトの名前（市場の位置づけの文書）、政府間の機関・貿易協定、地名（工場・港の場所を含む）、原油の銘柄、米の品種名。サンプルが実在の企業に見えるという今回の問題とは別と判断したが、地名と工場の組み合わせ（例：組立拠点の都市）で元の企業が推測できる余地はある。
3. **git の履歴**：書き換えていない（依頼書の範囲外）。過去の commit には元の名前が残っている。
4. **保護対象のコアのコメント**（§2.1）の 5 行の差分。

## 6. `output/sample_names/`（git の対象外）

| ファイル | 内容 |
|---|---|
| `preliminary_terms.txt` | 予備の一覧（Claude 君） |
| `inventory.csv` | 棚卸し：ファイル・行・種類・実名・一般名（4,735 行） |
| `mapping.csv` | 対応表：種類・実名・一般名・件数 |
| `rename_rules.py`・`apply_rules.py` | 置き換えの規則と、それを当てる道具（再現用） |
| `before/`・`after/`・`compare_snaps.py`・`n2_compare.csv` | N-2 の照合（前後のスナップショットと比較の結果） |
| `golden_*_original.json` | N-3 の照合の元（元の golden の写し） |
| `kept_names.txt`・`private_list_suggestion.txt` | §5 の 2、手元の一覧の候補 |
| `full_suite.log` | N-6 |

## 7. GUI の確認（N-5）

`python -m tools.gui_generation_line_check --model-dir <コピー> --plugins auto`（実アプリの窓、PrintWindow で撮影）。モデルはコピーで実行した。

| モデル | 読み込みで ON の組 | 例外 | PSI List のノード | PSI＝golden | 画像 |
|---|---|---:|---:|---|---|
| smartphone-global-2026-2029 | 推奨の組（3 つ） | 0 | 32 | 一致 | World Map・Network・PSI List（`EMS_A_CN`・`Foundry_A_TW`・`DC_AMER`）・Flow Check |
| Cookie-jp-2026 | 推奨の組 | 0 | 15 | 一致 | World Map・Network・PSI List（`DC_Import_Main`・`Retail_JP_CVS`）・Flow Check |

画像と結果：`docs/development/sample_names/gui/<モデル>/`。

## 8. ファイルの一覧

### 追加
- `tests/test_no_real_names.py`
- `tests/data/real_name_denylist.txt`
- `tests/golden/ev-thailand-2026_update.json`・`tests/golden/soysauce-jpy-2027-alloc.json`
- `docs/development/WOM_SampleNames_PublicReview_Report.md`（この報告書）
- `docs/development/sample_names/gui/smartphone-global-2026-2029/`（画像 7・`result.json`）
- `docs/development/sample_names/gui/Cookie-jp-2026/`（画像 7・`result.json`）
- （Owner の依頼書 `requests/RequestLetter_SampleNames_PublicReview_to_CodeKun.md` は未追跡のまま。実名が無いことはテストで確認）

### 名前の変更（新しい名前。中身も置き換えたものを含む）
§2.2 のとおり（スマートフォンのモデルのフォルダ 22 ファイル、golden 1、依頼書 3、報告書 1、記録のフォルダ 13 ファイル、画像 3）。

### 削除
§2.3 のとおり（旧スマートフォンのモデルのフォルダ 9 ファイル）。

### 変更（中身の名前の置き換え、132 件）
- `.gitignore`
- `260612_0032rm_push.bat`
- `CLAUDE.md`
- `README.md`
- `data/ppc/ppc_edge_cost_rule.csv`
- `data/ppc/ppc_market_price.csv`
- `data/ppc/ppc_node_cost_rule.csv`
- `data/ppc/ppc_node_profit_zone.csv`
- `data/ppc/ppc_profit_zone_rule.csv`
- `data/ppc/ppc_supplier_cost.csv`
- `data/ppc/ppc_tariff_rule.csv`
- `data/ppc/ppc_transfer_price_rule.csv`
- `data/sample/Cookie-jp-2026/node_master.csv`
- `data/sample/apparel-global-2028-2029/node_master.csv`
- `data/sample/apparel-us-2026/exercises/ex1_margin_rate_sensitivity/README.md`
- `data/sample/apparel-us-2026/exercises/ex4_shared_store_design/README.md`
- `data/sample/apparel-us-2026/node_master.csv`
- `data/sample/rice-japan-2027-2028/node_master.csv`
- `docs/WOM_Start_Here.md`
- `docs/architecture/ppc_engine.md`
- `docs/architecture/repository_map.md`
- `docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md`
- `docs/design/drafts/GROK-WOM.md`
- `docs/design/drafts/WOM_Composite_Node_Independent_Review_bc470b2.md`
- `docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v0.1.md`
- `docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v0.2.md`
- `docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v0.3.md`
- `docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md`
- `docs/design/lot_id_traceability_and_coverage_views.md`
- `docs/design/wom_model_typology.md`
- `docs/development/WOM_CapTrial_ClosureRows_Report.md`
- `docs/development/WOM_CapacityZeroBlank_Report.md`
- `docs/development/WOM_Capacity_Trial02_Report.md`
- `docs/development/WOM_ExplicitClosure_v1r5m0_Report.md`
- `docs/development/WOM_FlowCheck_WarmupTrial_Report.md`
- `docs/development/WOM_GenerationLine_UpperLayer_Report.md`
- `docs/development/WOM_LotIdentityFlow_Report.md`
- `docs/development/WOM_PPC_Entry_Measurement_Report.md`
- `docs/development/WOM_PublicReadiness_Plugins_Report.md`
- `docs/development/WOM_RiceDAL_Trial_Report.md`
- `docs/development/WOM_SimMgmt_WorldMapTrial_Report.md`
- `docs/development/WOM_StageD_Phase1_Report.md`
- `docs/development/WOM_StageD_Survey_Report.md`
- `docs/development/WOM_StalePPC_Units_KittingView_Report.md`
- `docs/development/WOM_Warmup17_IdentityGolden_Report.md`
- `docs/development/WOM_WorldMap_ActualFlows_Report.md`
- `docs/development/archive/README_ai_neutral_draft.md`
- `docs/development/archive/README_before_ai_neutral_entrypoint.md`
- `docs/development/capacity_zero_blank/survey_before.json`
- `docs/development/captrial_closure_rows/migrate_closure_rows.py`
- `docs/development/captrial_closure_rows/probe_before_after_diff.txt`
- `docs/development/explicit_closure_v1r5m0/probe_before_after_diff.txt`
- `docs/development/public_readiness/p1.csv`
- `docs/development/public_readiness/p1.json`
- `docs/development/public_readiness/p4_flow_check.json`
- `docs/development/sim_mgmt_worldmap/bench.json`
- `docs/development/sim_mgmt_worldmap/part1/gui_sim_plan_steps.json`
- `docs/development/sim_mgmt_worldmap/part1/kpi_summary_check.json`
- `docs/development/stage_d_survey/s2_leaf_compare.csv`
- `docs/development/stage_d_survey/stage_d_measure.json`
- `docs/development/stage_d_survey/stage_d_measure.py.txt`
- `docs/development/stale_ppc/base_e575042_reproduction.json`
- `docs/development/stale_ppc/gui_two_model_steps.json`
- `docs/development/stale_ppc/units_compare.csv`
- `docs/development/stale_ppc/units_freight_compare.csv`
- `docs/development/wom-v1r4m0_phase1_merit_order.md`
- `docs/scenarios/smartphone.md`
- `index.html`
- `requests/Phase8-3c_Addendum_to_CodeKun.md`
- `requests/RequestLetter_CapTrial_Golden_and_ClosureRows_to_CodeKun.md`
- `requests/RequestLetter_Capacity_Trial02_to_Astra.md`
- `requests/RequestLetter_ExplicitClosure_v1r5m0_to_CodeKun.md`
- `requests/RequestLetter_LotIdentityFlow_Addendum1_to_CodeKun.md`
- `requests/RequestLetter_SimMgmt_WorldMapTrial_to_CodeKun.md`
- `requests/RequestLetter_StageD_Phase1_to_CodeKun.md`
- `requests/RequestLetter_StageD_Survey_to_CodeKun.md`
- `requests/RequestLetter_StalePPC_Units_KittingView_to_CodeKun.md`
- `requests/RequestLetter_Warmup17_IdentityGolden_to_CodeKun.md`
- `requests/RequestLetter_WorldMap_ActualFlows_to_CodeKun.md`
- `requests/apparel-global-2028-2029-request-letter.md`
- `requests/approval_mode4_fix.md`
- `requests/operating-constraint-layer-request-letter.md`
- `requests/smartx-2027-2029-fix-request-letter.md`
- `tests/test_ev_update_kitting.py`
- `tests/test_merit_order.py`
- `tests/test_ppc_multi_supplier.py`
- `tests/test_ppc_run_info.py`
- `tests/test_ppc_vertical_slice.py`
- `tests/test_s2_actual_shipment_eval.py`
- `tests/test_sim_mgmt_display.py`
- `tests/test_stage_d_part0.py`
- `tests/test_warmup_materialize.py`
- `tests/test_worldmap_actual_flows.py`
- `tests/test_worldmap_ne.py`
- `tools/capacity_csv_survey.py`
- `tools/ev_update_kitting_trial.py`
- `tools/gen_apparel_global_model.py`
- `tools/gen_apparel_model.py`
- `tools/gui_sim_plan_check.py`
- `tools/gui_two_model_check.py`
- `tools/gui_valuechain_check.py`
- `tools/gui_worldmap_check.py`
- `tools/ppc_kpi_summary_check.py`
- `tools/probe_ppc_entry.py`
- `tools/run_headless_from_folder.py`
- `tools/s2_eval_compare.py`
- `tools/warmup_trial.py`
- `wom/data/schema.py`
- `wom/engine/backward_planner.py`
- `wom/engine/flow_check.py`
- `wom/engine/forward_planner.py`
- `wom/engine/landed_cost.py`
- `wom/engine/lane_assignment.py`
- `wom/engine/money.py`
- `wom/engine/push_pull.py`
- `wom/engine/sc_tree_builder.py`
- `wom/engine/sc_tree_to_df.py`
- `wom/engine/strategic_kpi.py`
- `wom/engine/warmup.py`
- `wom/gui/app.py`
- `wom/ppc/__init__.py`
- `wom/ppc/__main__.py`
- `wom/ppc/ppc_backward.py`
- `wom/ppc/ppc_cockpit.py`
- `wom/ppc/ppc_engine.py`
- `wom/ppc/ppc_psi_bridge.py`
- `wom/ppc/ppc_runner.py`
- `wom/ppc/ppc_tariff.py`
- `wom/visualization/merit_order.py`
- `wom/worldmap_ne/bench.py`
- `wom/worldmap_ne/flows.py`
- `wom/worldmap_ne/viewer.py`

## 9. サンプルの 1 モデルの削除（Owner の判断）

- 依頼書：`requests/RequestLetter_RemoveSampleCase_to_CodeKun.md`。Owner の判断で削除（2026-10-09）。
- **棚卸し**：追跡するファイルと新しいファイルの中身・ファイル名を、このモデルの名前・品目・拠点・市場の語で検索（`output/remove_case/inventory.csv`、git の対象外）。削除の前は 51 ファイル・9,499 か所。画像はファイル名で確かめ、名前の似た smartx の図（`docs/development/smartx_bottleneck/figures/india_requirements_and_capacity.png`）は中身を見て smartx の図と判断し、残した。
- **削除**（24 ファイル。パスの一覧は `output/remove_case/deleted_files.txt`）：モデルのフォルダ全体（22 ファイル）、再現スイープの spec（1 件）、前の依頼で作った golden（1 件。まだ commit していなかった）。
- **テスト**：このモデルをデータとして使うテストは無かった。`tests/test_backward_supply_role.py` は前から小さな人工の木で `supply_role`（合流は分ける・組立は複製する）を守っており、モデルの名前は docstring にだけあった。docstring を一般の書き方に直した（テストの中身は変えていない）。
- **文書**：CLAUDE.md・README（サンプルの数 16 → 15）・設計メモ（このモデルの節を「（Owner の判断で削除。2026-10-09）」に）・型の一覧（数え直し 13 → 12）・過去の報告書 7 件・依頼書 6 件・記録の json／csv 5 件から、このモデルの文・表の行・節を削った。この節より前の数字のうち、当時の件数で書いたものは「当時」と書き添えた。
- **保護対象のコア**：`wom/engine/backward_planner.py`（docstring 2 行）・`wom/model/plan_node.py`（コメント 1 行）の例を一般の書き方に直した。コードは変えていない。
- **前の依頼の成果物**：`output/sample_names/` の対応表・棚卸し・`private_list_suggestion.txt`・`kept_names.txt`・比較の結果からこのモデルの行を削り、このモデルのスナップショットを消した（`image_review.html` には該当なし）。
- **依頼書の書き換え**：X-1（名前が 0 件）を満たすため、この依頼書自身の中のモデル名・パス・品目の語を「サンプルの 1 モデル」「このモデルのフォルダ」などに置き換えた。
- **残した 1 か所**：`Oil_Global_SC_design_draft.md` の原油の指標の名前（中東の指標の一つ）。このモデルの市場名と同じ地名だが、石油のモデルの話で関係が無いので残した。

| ID | 検査 | 結果 |
|---|---|---|
| X-1 | 名前・拠点名・製品名が残っていない（Start Here を除く） | **合**：再検索で上の 1 か所（無関係）だけ |
| X-2 | golden の件数・不変 | canonical **15**＋legacy **3**＝**18 件**（依頼書の「13＋3」は、前の依頼で 3 件を足す前の数え方。足した 3 件のうち 1 件をここで消した）。残りの golden は変えていない |
| X-3 | 置き換えたテストが同じことを守る | 置き換えの必要なテストは無かった（上記） |
| X-4 | 全テストを単独で実行して緑 | **合**：**885 passed、3 skipped**（15 分 38 秒、単独で実行。前の 888 から、消したモデルの golden とモデルごとのテストの 3 件が減った） |

変更したファイル（パスだけ）：
- `CLAUDE.md`
- `README.md`
- `requests/RequestLetter_RemoveSampleCase_to_CodeKun.md`
- `docs/development/WOM_SampleNames_PublicReview_Report.md`
- `docs/design/design_memo_confluence_assembly_autotuning.md`
- `docs/design/wom_model_typology.md`
- `docs/development/WOM_CapacityZeroBlank_Report.md`
- `docs/development/WOM_Capacity_Trial02_Report.md`
- `docs/development/WOM_PublicReadiness_Plugins_Report.md`
- `docs/development/WOM_SmartphoneWarmup_EVUpdateKitting_S2_Report.md`
- `docs/development/WOM_StageD_Phase1_Report.md`
- `docs/development/WOM_Warmup17_IdentityGolden_Report.md`
- `docs/development/capacity_zero_blank/survey_before.json`
- `docs/development/public_readiness/p1.csv`
- `docs/development/public_readiness/p1.json`
- `docs/development/public_readiness/p4_flow_check.json`
- `docs/development/smartphone_evupdate_s2/B4_duplicates_all_models.csv`
- `requests/RequestLetter_SampleNames_PublicReview_to_CodeKun.md`
- `requests/RequestLetter_StageD_Phase1_to_CodeKun.md`
- `requests/RequestLetter_Warmup17_IdentityGolden_to_CodeKun.md`
- `requests/request_fix_a1_multi_child_duplication.md`
- `requests/request_fix_a1_supply_role_rev2.md`
- `requests/request_fix_mode4_supply_role.md`
- `tests/test_backward_supply_role.py`
- `wom/engine/backward_planner.py`
- `wom/model/plan_node.py`
