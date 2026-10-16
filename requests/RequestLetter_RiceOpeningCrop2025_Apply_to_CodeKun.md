# Request Letter — Rice：2025 年産を正式なサンプルに入れる（試行の T3）

- 宛先：Claude Code君
- 依頼者：大杉（WOM Project Owner）／起草：Claude君、2026-10-16
- 基準：`wom-v1r5m1_cap_trial` の最新（この依頼書を入れた commit）。着手時の SHA を報告する
- 前提：試行 `requests/RequestLetter_RiceOpeningCrop2025_Trial_to_CodeKun.md` の結果（`output/rice_crop2025_trial/results/summary.md`）
- 種別：サンプルのデータ・golden（rice だけ、意図した変化）・Lesson 000 の道具と結果・テストの期待値・文書。**`wom/` と保護対象のコアは変えない。commit はしない**
- テストの段：途中は `--smoke` と `--golden rice-japan-2027-2028`。最後に `--smoke`、`--area rice,public,core`、`--golden rice-japan-2027-2028`。**全テストは不要**（`wom/` を変えないため）

## 0. 決定（Owner、2026-10-16）

1. 試行の **T3** を `data/sample/rice-japan-2027-2028` に入れる。計画は **2025-W33 から**。2025 年産を普通の年産として持つ。
   - 新潟（コシヒカリ）の 2025 年産：**18,595 lot/週 × 3 週（2025-W41〜W43）＝ 55,785**。前年産には余剰があったという仮定（他の年 46,500 の 1.2 倍）。
   - 北海道（ゆめぴりか）の 2025 年産：**他の年と同じ 2,600 lot/週 × 7 週（2025-W37〜W43）＝ 18,200**（試行の T3 は 15,008 にしたが、使うのは 15,008 で上限に当たらないので、他の年と揃える）。
2. **`report_start` は 2027-W01 のまま**（`vc_config.csv` は変えない）。
3. コードは変えない（試行で、データだけで動くことを確かめた）。決定記録 D7（期首在庫は計画の中で作る）に沿う。Sol君の設計ドラフトの「期首在庫の固定配置モード」は採らない（ドラフトへの注記は Claude 君がする）。

## 1. サンプルのデータ

試行の写し `output/rice_crop2025_trial/T3_enough` と同じ行を足す。ただし北海道の 2025 年は上の 1 の値（2,600・18,200）。

| ファイル | 足す行 |
|---|---|
| `demand_forecast.csv` | 2025-W33〜W52 × 2 品目 × 4 市場、数量 0（160 行） |
| `capacity_plan.csv` | 2025-W33〜W52 × 6 行（精米は 2026-W01 と同じ、田は 0、2025 年の収穫週だけ上の値） |
| `rice_resource_capacity.csv` | 新潟 2025-W41〜W43（18,595）、北海道 2025-W37〜W43（2,600）、`crop_season` 2025 |
| `rice_crop_limit.csv` | 新潟 2025：55,785、北海道 2025：18,200 |

- note 列：「2025 年産（計画の最初の年産。前年産には余剰があった仮定、2026-10-16）」のように、仮定であることが分かる文にする。
- 既存の行は変えない。`holiday_calendar.csv`（2026 年の休日が無いことは知っている。今回は足さない）・`vc_config.csv`・`planning_config.csv` も変えない。
- **北海道を 18,200 にしたので、試行の T3 と結果が同じかを最初に確かめる**（同じになる見込み。違えば止めて報告）。

## 2. golden と、rice の結果を持つテスト

1. `tests/golden/rice-japan-2027-2028.json` を作り直す（`--plugins` は推奨の組を明示。作り方は `tests/test_golden.py` の説明）。**変わるのは rice だけ**で、ほかの golden は変わらないこと。
2. rice の結果の数字を期待値に持つテスト（例：`tests/test_rice_seasonal_layer.py`）は、**rice のサンプルの結果を写した期待値だけ**を新しい値にする。検査の中身（何を確かめるか）は変えない。直した期待値は、報告に「テスト・項目・前 → 後・理由」の表で全部書く。
3. 計画期間を前提にしたテスト（157 週、2026-W01 開始など）があれば、同じように直して表に書く。

## 3. Lesson 000 の道具と結果

1. `tools/lesson000_variants.py` の表 `CHANGES`：
   - **収穫 +30% は 2026〜2028 年産だけ**に掛ける。2025 年産は計画の前の事実なので変えない（新潟の 2025 の行は値が 18,595 なので、条件に `crop_season` か年の範囲を入れて、当たる行の数を今までどおり 9・3・9 にする）。
   - **精米 +30% は全部の週**（2025 年の週を含む）。`Seihaku_E`・`Seihaku_W` の行の数は 314 → 354 になる。
   - 表の説明（`--list` と README の表）も合わせる。
2. `tests/test_lesson000_variants.py` の期待値（行の数）を合わせる。テストの中身は変えない。
3. `python -m tools.lesson000_variants --run` で 4 つを作り直し、`docs/lessons/lesson000/results/summary.md` を新しい表にする。`docs/lessons/lesson000/README.md` の数字（主な数字の表・実行の日付・所要時間）を直す。
4. **台本 `Lesson000_Rice.md` は触らない**（Claude 君が新しい数字で直す）。

## 4. 文書

- `data/sample/rice-japan-2027-2028/README.md`：計画期間（2025-W33〜2028-W52、177 週）、「2026 年は助走」の段落を「2025 年産を計画に入れた（仮定と量）」に書き換え、結果の数字を新しくする。
- CLAUDE.md：短い節を一つ（何を変えたか、試行と決定、golden を作り直したこと、Lesson 000 の数字が変わったこと）。
- `docs/WOM_Start_Here.md` は触らない（Claude 君が直す）。

## 5. 受入条件

| ID | 検査 |
|---|---|
| A-1 | `tools.rice_seasonal_check` でサンプルを実行し、照合（flow identity・上限の超過・早出し・物量の保存）がすべて合格。数字が試行の T3 と同じ（2026 年の届かない 0、報告期間のコシヒカリ 97,496／24,934、2025-W52 の玄米倉庫 51,167 lot） |
| A-2 | golden：rice だけ作り直し、`--golden rice-japan-2027-2028` が緑。ほかの golden のファイルに差分が無い |
| A-3 | 直したテストの期待値の表（§2.2・2.3）。中身を弱めた所が無い |
| A-4 | Lesson 000：`--run` の照合がすべて合格。新しい 4 つの表（基準・収穫 +30%・精米 +30%・両方） |
| A-5 | `--smoke`、`--area rice,public,core`、`--golden rice-japan-2027-2028` が緑。件数と時間 |
| A-6 | `git status`：`wom/` に変更が無い。golden は rice の 1 ファイルだけ |

GUI の確認は Owner がする（試行の T3 で、Leaf の CO と玄米倉庫の姿は確かめ済み）。LOVEM の照合は今回は不要（実施しなかったと報告に書く）。

## 6. 報告

- `docs/development/WOM_RiceOpeningCrop2025_Report.md`：着手の SHA、試行の要点（T1・T2・T3 の表の要約）と決定、A-1〜A-6、直した期待値の表、Lesson 000 の新旧の比較（基準・3 つの比較モデルの、報告期間のコシヒカリの届いた／届かなかった）、予想と違ったこと。
- 追加・変更のファイルの一覧。
- commit・push はしない。
