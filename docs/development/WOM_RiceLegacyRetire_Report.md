# Rice の置き換え：legacy を過去の記録にする　報告

- 依頼書：`requests/RequestLetter_RiceLegacyRetire_to_CodeKun.md`
- 実装：Code君（Claude Code, Windows）、2026-10-09
- リポジトリ：`Yasushi-Osugi/wom_development_composite_node`、ブランチ `wom-v1r5m1_cap_trial`
- **着手時の SHA：`5361206`**（依頼書の基準と同じ。作業ツリーは依頼書 1 本の追加だけ）
- **保護対象のコア・legacy の方式のコード・`tests/golden/legacy/` は変えていない。** rice の値（§8.1・§8.2）も変えていない。
- **commit・push はしていない。** 削除・追加したファイルの一覧は §9。
- 付表：`docs/development/rice_retire/`

---

## 0. 受入のまとめ

| ID | 検査 | 結果 |
|---|---|---|
| L-1 | `data/sample/rice-japan-2027-2028/` の CSV が、5361206 の移行用コピーと一致（README を除く） | **合**。行末（CRLF/LF）を除いて全ファイル一致、違いは README だけ（§1） |
| L-2 | 新しい golden の当週出荷 141,210・注文残 95,727（助走 67,169、報告期間 28,558）、遅配・早出し 0 | **合**（§5） |
| L-3 | ほかの canonical 12 件・legacy 3 件の golden が不変 | **合**。全テストで golden 16 件が緑、作り直したのは rice だけ（§5・§8） |
| L-4 | `data/sample/` の全モデルが identity（新しいテスト） | **合**。`tests/test_rice_retire.py::test_every_sample_model_is_identity`（17 モデル） |
| L-5 | HarvestBatch の参照がコード・テスト・道具に残っていない | **合**。使う所は 0。残るのは削除を説明するコメントと、Sol 君の記録の中の言葉だけ（§3 の一覧） |
| L-6 | GUI：rice で Rice Seasonal が ON、Cookie で OFF。どちらもエラーなく計画。rice は報告書 §10 の手順 1・4・4b と同じ値 | **合**（§4） |
| L-7 | rice の LOVEM：観測 ON/OFF 一致、actual_ship と 1 対 1、区間の照合（`verify_run` は使わない） | **合**（§6） |
| L-8 | 全テストを単独で実行して緑 | **合**。843 passed／3 skipped（§8） |

---

## 1. rice のサンプルを置き換えた（1.1）

- `data/sample/rice-japan-2027-2028/` の中身を `data/trial/rice-japan-2027-2028-seasonal/` と同じにした（フォルダ名はそのまま）。
  - 元にあって移行用コピーに無いファイルは**無かった**（何も消していない）。
  - 上書き：`capacity_plan.csv`・`node_cost_master.csv`・`planning_config.csv`・`sku_master.csv`。追加：`rice_*.csv` 6 本・`vc_config.csv`・`README.md`。ほかの CSV は移行用コピーと元が同じ内容だった。
  - L-1：5361206 の移行用コピーと比べ、行末（作業ツリーと `git archive` で CRLF/LF が違う）を除いて全ファイル一致。違いは README だけ。
- README を正式なサンプルの説明に書き直した（季節供給の仕組み、Rice Seasonal が要ること〔GUI は自動で ON〕、§8.1・§8.2 の値、助走の年と報告期間、コシヒカリの不足は収穫量による、結果の数字）。
- `data/trial/rice-japan-2027-2028-seasonal/` と `tools/gen_rice_seasonal_migration.py` を削除した。**移行用コピーは 5361206 の時点で、この道具で元の legacy の rice から作った**（道具も 5361206 の git の履歴で見られる）。これからは `data/sample/rice-japan-2027-2028/` の CSV が正本。
- 移行用コピーのパスを使っていた所を `data/sample/rice-japan-2027-2028` に替えた：`tests/test_rice_seasonal_layer.py`・`tests/test_report_start.py`（skip の理由の文言も）、`tools/rice_seasonal_check.py`・`tools/rice_seasonal_lovem_check.py`（使い方の説明）。
- 文書（過去の報告書・依頼書・コミットメッセージの下書き）の中の古いパスは、記録なので書き換えていない。

## 2. 試行のフォルダを片づけた（1.2）

- `data/sample/rice-japan-2027-2028-dal/`（14 ファイル）、`tools/probe_rice_dal_trial.py`・`tools/analyze_rice_dal_trial.py` を削除。
- `docs/development/WOM_RiceDAL_Trial_Report.md` の先頭に「試行のデータと道具は 5361206 まで。git の履歴で見られる」と 1 行足した。
- `data/sample/rice-japan-2027-2028_BK260613_1515/`（`.gitignore` の対象）は触っていない。
- `data/trial/rice-seasonal-one-id/`（Sol 君の 1 ID の検算、テストの入力）は残した。

## 3. HarvestBatch を外した（1.3）

| 場所 | 変更 |
|---|---|
| `wom/plugins/__init__.py` | `ALL_BUILTIN_PLUGINS` から外した（GUI の Plugins の一覧からも消える） |
| `wom/engine/harvest_batch_plugin.py` | 削除 |
| `wom/gui/app.py` | 期首在庫を HarvestBatch から集める 2 か所を外し、期首在庫は空（`{}`）に。Debug のステップの説明の文言から HarvestBatch を外した。ほかに期首在庫を渡すプラグインは無かった |
| `tools/run_headless_from_folder.py` | `_select_plugins` の 2 つ目の戻り値（HarvestBatch の実体）は常に None（呼び出し側の形を保つため残した）。Forward の期首在庫は空。説明の「rice は HarvestBatch を含める」を新しい組に直した |
| `tools/sweep_flags.py` | 同上（期首在庫は空） |
| `tests/test_golden.py` | 説明を新しい作り方に直した |
| `wom/plugins/rice_seasonal.py` | 説明の文を直した |

**`OI_` を許す照合（消さずにコメントだけ直した）と、消した場合の影響**（判断は Owner）：

| 場所 | 今の扱い | 消した場合 |
|---|---|---|
| `wom/engine/flow_check.py` の `non_demand`（表 1） | 需要に無い ID（`OI_` に限らない）を受け取った・持った・出荷したノードの行を「対象外（需要に無い ID）」にする | そのような行は到着差で判定され、NG になりうる。今のサンプルでは需要に無い ID を作るものが無いので結果は変わらない。**消すと照合が厳しくなる（将来、需要に無い ID が紛れ込んだら NG で見える）**。消すことを勧める |
| `tools/lot_identity_checks.py` の K3 | `OI_` の ID を `rice_harvest_like` として別に数え、「需要に無い ID」に入れない | `OI_` の ID も「需要に無い ID」として数えられる。今は作るものが無いので 0。古い run を読み直すときだけ違いが出る |

**L-5 の一覧**（コード・テスト・道具の中で "HarvestBatch" の文字が残る所。使う所は 0）：

| ファイル | 中身 |
|---|---|
| `wom/engine/flow_check.py`・`tools/lot_identity_checks.py` | 上の照合のコメント（「旧 HarvestBatch の期首在庫。今は作るものが無い」の趣旨） |
| `wom/gui/app.py`・`tools/run_headless_from_folder.py`・`tools/sweep_flags.py`・`tests/test_golden.py`・`wom/plugins/rice_seasonal.py` | 削除したことの説明のコメント・文 |
| `tools/probe_rice_seasonal_definition.py` | Sol 君の検算の manifest の項目 `"HarvestBatch": False`（記録として残した） |
| `tests/test_rice_seasonal_trial.py` | Sol 君の試作のテストの説明文（同上） |

> 気づいたこと（未対応、報告だけ）：headless の `--plugins` に知らないクラス名を書くと、黙って無視される（`_select_plugins`）。例えば古いコマンド `--plugins …,HarvestBatchPlugin` はエラーにならず、そのプラグイン無しで計画する。止めるようにするかは別の判断。

## 4. GUI：モデルを読み込んだら Rice Seasonal を合わせる（1.4）

- Load Model Folder のとき、`rice_seasonal_config.csv` があれば Rice Seasonal のチェックを ON、無ければ OFF にする。ステータスの行に「Rice Seasonal：このモデルの設定（rice_seasonal_config.csv）があるので ON」／「…設定が無いので OFF」と出す（rice は計画期間の確認の警告〔2026-W53 を需要 0 で含めた〕が直後に出るので、その後ろに続けて出す）。読み込んだ後に手で OFF にできる。ほかのプラグインは自動で変えない。
- `rice_seasonal_config.csv` の無いモデルで Rice Seasonal を ON にして計画すると、`fatal_errors` で止まる。メッセージを「このモデルには Rice の設定（rice_seasonal_config.csv）がありません。Plugins の Rice Seasonal を OFF にして計画してください」にした（前は「missing input file: …」）。テスト `tests/test_rice_retire.py::test_rice_seasonal_on_a_model_without_rice_inputs_says_so`。

GUI での確認（`python -m main` と同じ窓、`tools/gui_generation_line_check.py`、モデルのコピー）：

| | rice（読み込み＋Holiday Calendar・Buffering Stock・Capacity Override を ON＝§10 の手順 1） | Cookie（読み込みのまま） |
|---|---|---|
| 読み込み直後の Rice Seasonal | **ON** | **OFF** |
| ステータスの行 | 「⚠ 需要 CSV に無い週 1 週を…：2026-W53　｜　Rice Seasonal：このモデルの設定（rice_seasonal_config.csv）があるので ON」 | 「… 11 files loaded　｜　Rice Seasonal：このモデルの設定が無いので OFF」 |
| Run Planning Engine | エラーなし | エラーなし |
| 当週出荷・注文残 | **141,210・95,727**（遅配・早出し 0） | 141,990・0 |
| Flow Check 表 2「うち報告期間」 | 当週出荷 130,536・期末注文残 28,558 | 列なし（前と同じ） |
| World Map の帯 | 報告の開始週 2027-W01（vc_config.csv） | 報告の開始週 2026-W02（最初の非ゼロ需要週） |
| PSI List（全ノード） | 24 ノード、例外なし | 15 ノード、例外なし |

> 注意（Owner の実機確認のため）：自動で ON になるのは Rice Seasonal だけ。GUI の既定では Holiday Calendar などは OFF のままなので、読み込んだだけで計画すると、需要の倍率（GW・お盆・年末）が入らず、当週出荷 139,554・注文残 93,975（需要 233,529）になる。§10 の手順 1 のとおり Holiday Calendar も ON にすると、上の表の値になる。

画像：`docs/development/rice_retire/gui_rice/`・`gui_cookie/`。

## 5. golden を作り直した（1.5）

`tests/golden/rice-japan-2027-2028.json` を `--plugins HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,RiceSeasonalPlugin`（identity）で作り直した。

| 項目 | 前（legacy・HarvestBatch） | 後（identity・Rice Seasonal） |
|---|---:|---:|
| プラグイン | BufferingStock・CapacityOverride・HarvestBatch・HolidayCalendar | BufferingStock・CapacityOverride・HolidayCalendar・RiceSeasonal |
| lot_flow_mode | legacy | identity |
| 当週出荷 | 236,937 | **141,210** |
| 期末注文残 | 0 | **95,727**（助走 67,169、報告期間 28,558） |
| 遅配・早出し | 0・0 | 0・0 |
| Forward | cap_hard_sealed 8,658 | 能力による繰り延べ 0 |
| PPC 売上 | 1,841,995,800 円 | 1,103,303,400 円 |
| PPC 原価 | 1,132,460,983 円 | 676,123,819 円 |
| PPC 粗利（粗利率） | 709,534,817 円（38.52%） | 427,179,581 円（38.72%） |
| PPC の lot | 1,248 | 791 |

- 前の値は、5361206 のコードと元の rice を `git archive` で取り出し、同じ headless で計画して出した（golden の前の版と完全に一致：差 0 行）。当週出荷・注文残は、その計画の Flow Check の表 2（`docs/development/rice_retire/before_flow_check_market.csv`）。
- **前は全需要が当週出荷だった**：HarvestBatch が需要に紐づかない期首在庫（`OI_`）を置いていたため、2026 年の助走の不足（2025 年産が計画期間の外）もコシヒカリの収穫量の不足も見えていなかった。後は、それが注文残として見える（報告書 `WOM_RiceSeasonal_Implementation_Report.md` §5）。
- 後の当週出荷・注文残は、報告書 §13 の移行用コピーの結果と同じ。照合（§6）は `tools/rice_seasonal_check.py` の実出荷からの数え直し：flow identity の誤り 0、経路の不一致 0、資源の超過 0、需要に無い ID・合成 ID 0、早出し 0。
- PPC の値は、rice に PPC の価格表が無いため `data/ppc` の見本の規則で計算されている（Claude 君の申し送り。§8.2 の新しい価格は PPC には入っていない。置き換えの後の課題）。
- ほかの canonical 12 件と legacy 3 件は作り直していない。全テストで緑（§8）。

## 6. rice の LOVEM（L-7）

| 照合 | 結果 |
|---|---|
| 観測 ON／OFF の snapshot（psi・ppc・forward・products・period） | すべて一致 |
| LOVEM の actual_ship と観測なしの計画の木の実出荷（全ノード、(ノード, 週, ID) の多重集合） | 988,470 件で 1 対 1（市場 141,210 件も） |
| 区間の照合（`tools/lovem_interval_check.py`、セルごと、元の PSI と独立） | 全 10 snapshot・264 セル・区間 12,069,376・出現数 24,417,855、**不一致 0**（318 秒） |

`wom.lovem.verify.verify_run` は使っていない（Rice の run ではメモリが足りない）。付表 `docs/development/rice_retire/lovem/`。

## 7. 文書（1.6）

- **決定記録** `docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md`：D5 に「2026-10-09 に解消。rice は Rice Seasonal で identity に移った。`data/sample/` に legacy で動くモデルは無い。legacy の方式と `tests/golden/legacy/` は D3 のとおり残す」と追記（元の文は残した）。§4 の事実（期首在庫に lot を入れるのは rice の収穫プラグインだけ）、§6 の「Buffering Stock の詳細」「rice の合成 ID の重複」「legacy の Step 0a の CO の重複（rice を含む）」の行にも、解消したことを書き足した。
- **CLAUDE.md**：Planning Engine の手順の HOOK_PRE_PLAN の例、組み込みプラグインの一覧（HarvestBatch に取り消し線と削除の注記）、golden の作り直しの手順（rice のプラグインの組）、Rice の節（移行用コピー → サンプル、GUI の自動 ON、Rice の設定が無いモデルで止まること）を直した。古い経緯の節は書き換えていない。
- **`data/sample/rice-japan-2027-2028/README.md`**：§1。
- **`docs/WOM_Start_Here.md`** は触っていない（Claude 君が直す）。

## 8. テスト

- 新しいテスト `tests/test_rice_retire.py`（20 件）：`data/sample/` の 17 モデルがすべて identity（L-4）、rice のサンプルが identity で DAL の試行フォルダが無いこと、HarvestBatch の登録とモジュールが無いこと、Rice の設定の無いモデルで Rice Seasonal を ON にすると「Rice の設定」が無いと分かる文言で止まること。
- 全テスト：`python -m pytest tests/ -q -p no:cacheprovider` を単独で実行して **843 passed／3 skipped、失敗 0**（2026-10-09、15 分 4 秒）。golden は canonical 13 件（rice は作り直したもの）＋legacy 3 件がすべて緑。実行の後、`tests/golden/` で変わっているのは `rice-japan-2027-2028.json` だけ、`tests/golden/legacy/` と保護対象のコアに変更が無いことを確かめた。

## 9. 削除したファイル・追加したファイル（`git add -A` の前の確認用）

### 削除（39 ファイル）

```
data/trial/rice-japan-2027-2028-seasonal/ （21 ファイル）
  README.md, capacity_plan.csv, demand_forecast.csv, edge_cost_master.csv, holiday_calendar.csv,
  inventory_master.csv, lane_assignment.csv, node_cost_master.csv, node_master.csv,
  planning_config.csv, push_config.csv, rice_crop_limit.csv, rice_recipe.csv,
  rice_resource_capacity.csv, rice_resource_map.csv, rice_resources.csv,
  rice_seasonal_config.csv, route_master.csv, sc_tree_master.csv, sku_master.csv, vc_config.csv
data/sample/rice-japan-2027-2028-dal/ （14 ファイル）
tools/gen_rice_seasonal_migration.py
tools/probe_rice_dal_trial.py
tools/analyze_rice_dal_trial.py
wom/engine/harvest_batch_plugin.py
```

（`data/sample/rice-japan-2027-2028-dal/` の 14 ファイルの名前は §10 の付表 `deleted_files.txt`）

### 追加

```
data/sample/rice-japan-2027-2028/README.md
data/sample/rice-japan-2027-2028/rice_crop_limit.csv
data/sample/rice-japan-2027-2028/rice_recipe.csv
data/sample/rice-japan-2027-2028/rice_resource_capacity.csv
data/sample/rice-japan-2027-2028/rice_resource_map.csv
data/sample/rice-japan-2027-2028/rice_resources.csv
data/sample/rice-japan-2027-2028/rice_seasonal_config.csv
data/sample/rice-japan-2027-2028/vc_config.csv
tests/test_rice_retire.py
docs/development/WOM_RiceLegacyRetire_Report.md
docs/development/rice_retire/ （付表・画像）
```

（`requests/RequestLetter_RiceLegacyRetire_to_CodeKun.md` は Claude 君の追加で、着手前から未追跡）

### 変更

```
data/sample/rice-japan-2027-2028/capacity_plan.csv, node_cost_master.csv, planning_config.csv, sku_master.csv
tests/golden/rice-japan-2027-2028.json
wom/plugins/__init__.py, wom/plugins/rice_seasonal.py, wom/gui/app.py, wom/engine/flow_check.py
tools/run_headless_from_folder.py, tools/sweep_flags.py, tools/lot_identity_checks.py,
tools/rice_seasonal_check.py, tools/rice_seasonal_lovem_check.py, tools/gui_generation_line_check.py
tests/test_golden.py, tests/test_rice_seasonal_layer.py, tests/test_report_start.py
docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md, docs/development/WOM_RiceDAL_Trial_Report.md, CLAUDE.md
```

## 10. 付表

`docs/development/rice_retire/`：`deleted_files.txt`（削除した追跡ファイルの一覧）、`golden_before.json`（前の golden）、`before_flow_check_market.csv`（前の計画の表 2）、`check_summary.json`（後の照合）、`lovem/`（LOVEM の照合）、`gui_rice/`・`gui_cookie/`（GUI の結果と画像）。
