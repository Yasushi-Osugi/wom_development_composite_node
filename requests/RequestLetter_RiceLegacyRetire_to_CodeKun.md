# Request Letter — Rice の置き換え：legacy を過去の記録にする

- 宛先：Claude Code君
- 依頼者：大杉（WOM Project Owner）／起草：Claude君、2026-10-09
- 基準：`wom-v1r5m1_cap_trial`、**5361206**（feat(rice): seasonal supply …）
- 前提：`requests/RequestLetter_RiceSeasonal_Implementation_to_CodeKun.md`（§1 C・§8）、`requests/RequestLetter_RiceSeasonal_PolishAdvance1_to_CodeKun.md`、報告 `docs/development/WOM_RiceSeasonal_Implementation_Report.md`
- 種別：データ・プラグイン登録・GUI・テスト・文書。**保護対象のコアは変えない。**

## 0. 目的

移行用コピー `data/trial/rice-japan-2027-2028-seasonal/` は、Owner の実機確認で受け入れられた（2026-10-09）。
これを正式な rice のサンプルにして、golden を作り直す。

終わった時点で、次の状態にする。

- `data/sample/` のどのモデルも `lot_flow_mode = identity`。legacy で動くモデルは無い。
- legacy の方式そのものは、決定記録 D3 のとおり残す。`tests/golden/legacy/`（Cookie・ev-thailand・soysauce-jpy の 3 件）が守る網のまま。**今回、legacy の方式のコードと legacy の golden には触らない。**
- 匿名の期首在庫（`OI_`）を作る HarvestBatch は使われなくなるので、登録から外して削除する。

WOM の公開の前の整理。公開するサンプルに「旧方式の rice」と「試行のフォルダ」が並ばないようにする。

## 1. 作業

### 1.1 rice のサンプルを置き換える

1. `data/sample/rice-japan-2027-2028/` の中身を、`data/trial/rice-japan-2027-2028-seasonal/` と同じにする（フォルダ名は変えない。参照が多いため）。
   - 移行用コピーにだけあるファイル（`rice_*.csv` 6 本、`vc_config.csv`、`README.md`）を足し、元のファイルは移行用コピーの内容で上書きする。元にあって移行用コピーに無いファイルがあれば、一覧にして報告する（黙って消さない）。
   - README は「移行用コピー」の書き方を、正式なサンプルの説明に直す（季節供給の仕組み、Rice Seasonal の ON が必要なこと、Owner の決定 §8.1・§8.2 の値、助走の年と報告期間、コシヒカリの不足は収穫量によること）。
2. `data/trial/rice-japan-2027-2028-seasonal/` を削除する。
3. `tools/gen_rice_seasonal_migration.py` を削除する。元の legacy のサンプルが無くなり、生成元が無いため。これからは `data/sample/rice-japan-2027-2028/` の CSV が正本。報告書に「5361206 の時点でこの道具で作った」と記録する。
4. `tools/rice_seasonal_check.py`・`tools/rice_seasonal_lovem_check.py`・テストなどで移行用コピーのパスを使っているところを、`data/sample/rice-japan-2027-2028` に替える。

### 1.2 試行のフォルダを片づける

1. `data/sample/rice-japan-2027-2028-dal/`（Rice DAL の試行、追跡されている）を削除する。結果は `docs/development/WOM_RiceDAL_Trial_Report.md` に残っている。
2. それに依存する `tools/probe_rice_dal_trial.py`・`tools/analyze_rice_dal_trial.py` を削除する。DAL の報告書の先頭に「試行のデータと道具は 5361206 まで。git の履歴で見られる」と 1 行足す。
3. `data/sample/rice-japan-2027-2028_BK260613_1515/` は `.gitignore` の対象で追跡されていない。触らない（Owner が手元で消す）。
4. `data/trial/rice-seasonal-one-id/`（Sol 君の 1 ID の検算）は、テストの入力なので残す。

### 1.3 HarvestBatch を外す

1. `wom/plugins/__init__.py` の `ALL_BUILTIN_PLUGINS` から `HarvestBatchPlugin` を外し、`wom/engine/harvest_batch_plugin.py` を削除する。
2. GUI（`wom/gui/app.py`）の HarvestBatch 専用の処理（期首在庫を HarvestBatch から集める部分、Plugins の一覧の項目、説明の文言）を外す。ほかのプラグインの期首在庫の扱いがあれば変えない。
3. `OI_` の ID を許す照合（`wom/engine/flow_check.py`、`tools/lot_identity_checks.py` など）は、HarvestBatch が無くなっても害は無い。**消さずに、コメントを「旧 HarvestBatch の期首在庫。今は作るものが無い」に直す**。消すかどうかは、副作用を調べて報告に書く（判断は Owner）。
4. `tests/test_golden.py`・`tools/run_headless_from_folder.py` の説明にある「rice は HarvestBatch を含める」を、新しい作り方に直す。

### 1.4 モデルを読み込んだら Rice Seasonal を自動で合わせる（GUI）

rice は Rice Seasonal が OFF だと、ほとんどの需要が注文残になる（報告書 §10 手順 5）。公開のサンプルとして、ON にし忘れると誤読される。

- Load Model Folder のとき、モデルのフォルダに `rice_seasonal_config.csv` があれば Rice Seasonal のチェックを ON、無ければ OFF にする。ステータスの行に「Rice Seasonal：このモデルの設定があるので ON」のように出す。
- 利用者は、読み込んだ後で手で OFF にできる（比較のため）。
- `rice_seasonal_config.csv` が無いモデルで Rice Seasonal を ON にして実行したときの動きを確かめて報告する（今は `fatal_errors` で止まるはず）。止まるなら、メッセージが「このモデルには Rice の設定が無い」と分かる文言であること。
- Capacity Layer など、ほかのプラグインの自動化は今回しない。

### 1.5 golden を作り直す

1. `tests/golden/rice-japan-2027-2028.json` を作り直す。プラグインは、移行用コピーの照合と同じ組（`HolidayCalendarPlugin, BufferingStockOptimizerPlugin, CapacityOverridePlugin, RiceSeasonalPlugin`）。方式は identity。
2. 作り直しの前と後の主な値を報告に並べる（当週出荷・注文残・PPC の値）。後の値は、報告書 §13 の移行用コピーの結果（当週出荷 141,210・注文残 95,727）と同じであること。
3. ほかの canonical 12 件と legacy 3 件は変わらないこと。
4. 新しいテストを 1 本足す：**`data/sample/` のすべてのモデルの `planning_config.csv` が identity であること**（legacy に戻るモデルが出たら赤くなる網）。

### 1.6 文書

- **決定記録** `docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md`：D5（rice は legacy で動かす暫定措置）に、「2026-10-09 に解消。rice は Rice Seasonal（収穫週と精米週を選ぶ上位の層）で identity に移った」と追記する。元の文は消さない（記録として残す）。§6 の「rice の合成 ID」の行と、既知の課題の表の rice の行（P1 の合成 ID の重複など）にも、解消したことを書き足す。
- **CLAUDE.md**：rice の golden の作り方（HarvestBatch を含める、の記述）、Rice の節の「移行用コピー」のパス、HarvestBatch の記述を新しい状態に直す。古い経緯の節は書き換えず、必要なら「（2026-10-09 に置き換え済み）」と注記する。
- **報告書**：新しい報告 `docs/development/WOM_RiceLegacyRetire_Report.md` に、作業と結果をまとめる。
- **`docs/WOM_Start_Here.md` は触らない**（Claude 君が直す）。

## 2. 受入条件

| ID | 検査 |
|---|---|
| L-1 | `data/sample/rice-japan-2027-2028/` の CSV が、5361206 の `data/trial/rice-japan-2027-2028-seasonal/` と一致（README を除く）。差があれば理由 |
| L-2 | rice の新しい golden の当週出荷 141,210・注文残 95,727（助走 67,169、報告期間 28,558）。遅配・早出し 0 |
| L-3 | ほかの canonical 12 件・legacy 3 件の golden が不変 |
| L-4 | `data/sample/` の全モデルが identity（新しいテスト） |
| L-5 | `HarvestBatch` の参照がコード・テスト・道具に残っていない（`docs/development/` などの記録は除く）。一覧で示す |
| L-6 | GUI：rice を読み込むと Rice Seasonal が ON、Cookie を読み込むと OFF。どちらも Run Planning Engine がエラーなく終わる。rice は報告書 §10 の手順 1・4・4b と同じ値 |
| L-7 | rice の LOVEM：観測 ON/OFF 一致、actual_ship と 1 対 1（`tools/rice_seasonal_lovem_check.py`）。区間の照合（`tools/lovem_interval_check.py`）。`verify_run` は使わない |
| L-8 | 全テストを単独で実行して緑。件数を報告 |

## 3. 禁止・範囲

- 保護対象のコア（`plan_node.py`・`forward_planner.py`・`backward_planner.py`）を変えない。legacy の方式のコードと `tests/golden/legacy/` は変えない。
- rice の値（§8.1・§8.2）を変えない。結果に合わせて golden 以外の期待値を書き換えない。
- commit・push はしない。終わったら、削除したファイルと追加したファイルの一覧を報告の最後に付ける（Owner が `git add -A` の前に確かめるため）。
