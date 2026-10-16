# Rice：2025 年産を正式なサンプルに入れた — 報告

- 依頼書：`requests/RequestLetter_RiceOpeningCrop2025_Apply_to_CodeKun.md`（試行：`requests/RequestLetter_RiceOpeningCrop2025_Trial_to_CodeKun.md`）
- 着手時の SHA：`06acab9`（branch `wom-v1r5m1_cap_trial`）
- 実行：Claude Code君、2026-10-16。**`wom/` と保護対象のコアは変えていない。commit はしていない**
- テストの段：途中は `--golden rice-japan-2027-2028` と `--area rice,public,core`、最後に `--smoke`・`--area rice,public,core`・`--golden rice-japan-2027-2028`（§A-5）。全テストは回していない（依頼書のとおり）。LOVEM の照合は実施していない（依頼書のとおり不要）。

## 1. 試行の要点と決定

試行では、基準の写しを `output/rice_crop2025_trial/` に 3 つ作り（計画は 2025-W33 から、2025 年産を行として足すだけ、コードは不変）、`tools.rice_seasonal_check` で実行した。4 つとも照合はすべて合格（flow identity の誤り・上限の超過・早出し・合成 ID が 0、物量の保存は成立）。

| | 基準 | T1 他の年と同じ | T2 十分に大きい | T3 T2 で使った量 |
|---|---:|---:|---:|---:|
| 新潟の 2025 年産（上限） | — | 46,500 | 139,500 | 55,785 |
| 2026 年の需要の届かない量（全品目） | 67,169 | 5,663 | 0 | 0 |
| 報告期間のコシヒカリ 届いた／届かなかった | 93,874／28,556 | 93,874／28,556 | 97,496／24,934 | 97,496／24,934 |
| 2025-W52 の新潟の玄米倉庫（lot） | 0 | 41,882 | 51,167 | 51,167 |

決定（Owner、2026-10-16）：T3 をサンプルに入れる。北海道の 2025 年産は他の年と同じ 18,200（使うのは 15,008 で上限に当たらない）。`report_start` は 2027-W01 のまま。コードは変えない（決定記録 D7：期首在庫は計画の中で作る）。

## 2. サンプルに足した行（既存の行は不変）

| ファイル | 足した行 | 中身 |
|---|---:|---|
| `demand_forecast.csv` | 160 | 2025-W33〜W52 × 2 品目 × 4 市場、数量 0（ヘッダの直後） |
| `capacity_plan.csv` | 120 | 2025-W33〜W52 × 6 行。精米は 2026-W01 と同じ（東 1,300・西 1,000）、田は 0、収穫週だけ新潟 18,595（W41〜W43）・北海道 2,600（W37〜W43） |
| `rice_resource_capacity.csv` | 10 | FIELD_NIIGATA 2025-W41〜W43（18,595）、FIELD_HOKKAIDO 2025-W37〜W43（2,600）、`crop_season` 2025 |
| `rice_crop_limit.csv` | 2 | FIELD_NIIGATA 2025：55,785、FIELD_HOKKAIDO 2025：18,200 |

note 列：新潟は「2025 年産（計画の最初の年産。前年産には余剰があった仮定、2026-10-16）。新潟は他の年 46,500 の 1.2 倍」、北海道は「2025 年産（計画の最初の年産。他の年と同じ量、2026-10-16）」。`holiday_calendar.csv`・`vc_config.csv`・`planning_config.csv` は不変。

## 3. 受入条件

| ID | 結果 |
|---|---|
| A-1 | **合**。`tools.rice_seasonal_check` でサンプルを実行（114 秒）：照合はすべて合格（flow identity の誤り 0、資源・年産上限の超過 0、早出し 0、需要に無い ID・合成 ID 0、経路の不一致 0、物量の保存 成立）。2026 年の届かない量 **0**、報告期間のコシヒカリ **97,496／24,934**、2025-W52 の玄米倉庫 **51,167 lot**。試行の T3 と、届いた／届かなかった・Leaf の CO・年産の使い道・玄米倉庫・切り替えの週・精米の上限に当たった週のすべてが同じ（北海道の上限を 18,200 にしても結果は同じ。§6 の 1 つ目） |
| A-2 | **合**。`tests/golden/rice-japan-2027-2028.json` だけを推奨の組（`--plugins HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,RiceSeasonalPlugin`）で作り直した。`--golden rice-japan-2027-2028` 緑。ほかの golden（`tests/golden/*.json`・`legacy/*.json`）のファイルに差分なし |
| A-3 | **合**。直した期待値は §4 の表。検査の中身は変えていない |
| A-4 | **合**。`--run` の照合は 4 つとも合格（558 秒）。表は §5 |
| A-5 | §7 |
| A-6 | §8 |

golden の主な変化：`period` 2026-W01・157 週 → **2025-W33・177 週**（filled は 2026-W53 のまま）。`forward`・`backward` は不変（0）。`ppc`：Revenue 1,103,303,400 → 1,645,703,800 JPY、GM 38.72% → 38.74%（2026 年の需要が届くようになったため）、trust event 0 のまま。

## 4. 直したテストの期待値

| テスト | 項目 | 前 → 後 | 理由 |
|---|---|---|---|
| `tests/test_rice_seasonal_layer.py::test_k_r10_migration_copy_regression` | `served`／`unallocated` | 141,210／95,727 → **212,003／24,934** | 2025 年産で 2026 年の需要が届く |
| 同 | `unallocated_by_product_period` | Koshihikari report 28,556・warmup 52,163、Yumepirika report 2・warmup 15,006 → **Koshihikari report 24,934 だけ** | 同上。2026 年産のうち 3,622 lot が 2027 年へ回り、報告期間の不足が減る |
| 同 | `market_outcome` | on_time 141,210・backlog_end 95,727 → **212,003・24,934**（late・early 0 のまま） | 同上 |
| `tests/test_plan_period.py::test_sample_models` | rice の計画期間 | 2026-W01〜2028-W52・157 週・filled [2026-W53] → **2025-W33〜2028-W52・177 週**・filled [2026-W53] | 計画を 2025-W33 から始める |
| 同 | docstring | 「rice: 2026-W53 (156 -> 157)」→「(176 -> 177; …starts at 2025-W33…)」 | 同上 |
| `tools/lesson000_variants.py`（`CHANGES`。`tests/test_lesson000_variants.py` はこの表を読む） | Seihaku_E・Seihaku_W の行数 | 314 → **354** | 2025 年の 20 週 × 2 品目が増えた |
| 同 | 収穫 +30% の条件 | `resource_id`（と `sku_id`・`node_name`）だけ → **`crop_season` が 2026〜2028**（`capacity_plan.csv` は週の年）を足した。行数は 9・3・9 のまま | 2025 年産は計画の前の事実なので変えない |

`tests/test_lesson000_variants.py` には行数を書いた期待値が無く（`CHANGES` から読む）、ファイルは変えていない。`--list`・README の表は同じ表から作り直した。道具の `_matches` に「タプル＝どれか」と「キー `year`＝`week` の先頭 4 文字」を足した（既存の条件の意味は不変）。

## 5. Lesson 000 の新旧（報告期間のコシヒカリ、要求 122,430 lot、届いた／届かなかった）

| | 基準 | 新潟の収穫 +30% | 精米 +30% | 両方 |
|---|---:|---:|---:|---:|
| 前（2026-W01 から、2026 年は助走） | 93,874／28,556 | 121,774／656 | 93,874／28,556 | 121,774／656 |
| **後（2025 年産を入れた、2025-W33 から）** | **97,496／24,934** | **122,118／312** | **97,496／24,934** | **122,430／0** |

ほかの主な数字（後）：収穫 +30% の届かない 312 はすべて東北。当週の出荷が 0 の要求週は基準で 2027 年 W38〜W45（8 週、前は W35〜W45 の 11 週）・2028 年 W35〜W45（11 週）。精米センターが上限に当たった週（2027〜2028）は東 21／25／9／11、西 12／14／5／6。新潟の 2025 年産の収穫は 55,785／52,507／55,785／52,819（収穫 +30% では 2025 年産を使い切らない）。新潟の玄米倉庫のピークは基準 55,785（2025-W45）。表の全体は `docs/lessons/lesson000/results/summary.md`。

`docs/lessons/lesson000/README.md` は、比較モデルの変える値の表（2025 年産を変えないこと、354 行）、所要時間（約 9〜10 分、558 秒）、主な数字の表（前の数字も併記）を直した。台本 `Lesson000_Rice.md` は触っていない。

## 6. 予想と違ったこと・気づいたこと

1. **北海道の上限を 18,200 にしても結果は T3 と同じ**（照合・届いた量・CO・年産の使い道・玄米倉庫が一致）。ただし `market_ids.csv.gz` の行では、ゆめぴりかの 2,849 ID で**2025 年産の中の収穫週**（と倉庫に入る週）が T3 と違う（週の能力が 2,144 → 2,600 になり、収穫を早い週に寄せられる）。年産・出荷の週・状態は同じ。
2. **「両方 +30%」で報告期間の不足が 0 になった**（前は 656）。収穫 +30% だけでは 312 残る（東北）。2025 年産で 2026 年の需要が満たされ、2026 年産を 2027 年に回せるようになったため。
3. **収穫 +30% では 2025 年産を使い切らない**（52,507／55,785）。2026 年産が増えたぶん、2026 年の後半の需要に 2026 年産が使われる。
4. 2026-W53 の「0 で埋めた週」の警告は前からある（2026 年は ISO で 53 週）。2025 年の週の警告は出ない。
5. pytest の出力を cp932 のまま流すと、テストの出力の文字で `UnicodeEncodeError` が出た（`quick_check` の表示だけ）。`PYTHONIOENCODING=utf-8` で回した。テストの結果には関係しない。

## 7. テスト（A-5）

| 段 | 結果 | 時間 |
|---|---|---:|
| `python -m tools.quick_check --smoke` | **505 passed**、failed 0 | 100 秒 |
| `python -m tools.quick_check --area rice,public,core` | **411 passed**、failed 0 | 366 秒 |
| `python -m tools.quick_check --golden rice-japan-2027-2028` | **1 passed** | 81 秒 |

途中の `--area rice,public,core`（期待値を直す前）では、§4 の 3 か所（`test_k_r10_migration_copy_regression`、`test_sample_models`、Lesson 000 の行数）が落ちた。直した後に上の結果。報告書を書いた後に `tests/test_no_real_names.py` も単独で回して緑。

## 8. 変更・追加のファイル（A-6）

| ファイル | 変更 |
|---|---|
| `data/sample/rice-japan-2027-2028/demand_forecast.csv`・`capacity_plan.csv`・`rice_resource_capacity.csv`・`rice_crop_limit.csv` | 2025 年の行を足した（§2） |
| `data/sample/rice-japan-2027-2028/README.md` | 計画期間、2025 年産（仮定と量）、結果の数字 |
| `tests/golden/rice-japan-2027-2028.json` | 作り直した（rice の 1 ファイルだけ） |
| `tests/test_rice_seasonal_layer.py`・`tests/test_plan_period.py` | 期待値（§4） |
| `tools/lesson000_variants.py` | `CHANGES`（2025 年産を除く条件・354 行）、`_matches` |
| `docs/lessons/lesson000/results/summary.md` | `--run` で作り直した |
| `docs/lessons/lesson000/README.md` | 変える値の表・所要時間・主な数字 |
| `CLAUDE.md` | 節を一つ足した |
| `docs/development/WOM_RiceOpeningCrop2025_Report.md` | この報告（新規） |

`wom/` に変更なし。試行の写しと結果は `output/`（git の対象外）。
