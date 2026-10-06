# 計画期間の自動検出の修正（需要 CSV の週の抜け）— 報告書

- 依頼：`requests/RequestLetter_PeriodDetection_Fix_to_CodeKun.md`
- 発見：`docs/development/WOM_RiceDAL_Trial_Report.md` §1（Astra君）
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`、ブランチ `wom-v1r5m1_cap_trial`
- **着手時の SHA：`e355908`**（段階 D 第 2 回のコミット。作業ツリーはきれいな状態から着手）
- commit・push はしていない。保護対象のコアは変えていない（変える必要は無かった）。
- golden の再生成は apparel-us-2026 と rice-japan-2027-2028 だけ。CLAUDE.md の手順で、rice は HarvestBatch を含む 4 プラグイン、apparel-us は `safe`。
  - 再生成の前に `tests/test_golden.py` を実行し、落ちるのがこの 2 件だけで、ほかの 11 件と legacy の 3 件は変わらないことを確かめてから再生成した。

## 0. 要約

| | 結果 |
|---|---|
| 原因 | 計画期間を「需要 CSV の最初の週 ＋ 週の名前の種類の数」で決めていた（headless と GUI の 2 か所、同じ作り）。途中の週が CSV に無いと、その数だけ期間の終わりが切れる |
| 直したこと | 計画期間 ＝ 最初の週から最後の週までの連続した ISO の暦の週（`wom/engine/plan_period.py` の `detect_plan_period()`、headless と GUI が同じ関数を使う）。CSV に無い週は需要 0 として含め、どの週を埋めたかを警告とスナップショット・計画の木に出す |
| 変わったモデル | apparel-us-2026（91 → 121 週）、rice-japan-2027-2028（156 → 157 週）。ほかの 17 のサンプルは抜けが無く、期間は変わらない |
| 受入 1〜4 | すべて満たした（§3） |
| 依頼の数字との違い | apparel-us で計画に入っていなかった需要は、依頼の 102,302 lot ではなく **107,844 lot**（全需要 357,016 の 30.2%）。CSV から数え直すと、102,302 は 2027-W24 以降の合計で、2027-W23 の 5,542 lot が抜けている（§2.2） |

---

## 1. 直したこと

### 1.1 期間を決める関数（`wom/engine/plan_period.py`、新規）

- `detect_plan_period(demand_path)` → `PlanPeriod(start, end, weeks, filled_weeks)`
  - 需要 CSV の週の名前を ISO の週として読み、最初と最後を決める。
  - その間の**すべての暦の週**を `weeks` にする（年をまたぐ W53 も、その年に W53 があれば含む）。
  - CSV に無い週を `filled_weeks` に入れる。`warning()` は「需要 CSV に無い週 N 週を需要 0 として計画期間に含めた：…」の文。
- ISO の週でない名前（例 `2027-W53`。2027 年は 52 週まで）は、黙って飛ばさず `ValueError` で止める。
- `2027-W2` と `2027-W02` は同じ週として扱う。

### 1.2 使う側

| 場所 | 変更 |
|---|---|
| `tools/run_headless_from_folder.py` の `run()`・`_detect_period()` | `detect_plan_period()` を使う。抜けがあれば `[Headless] WARNING …` をログに出す（`--quiet` でも出す）。計画の木に `sc_tree.period_filled_weeks`。スナップショットの `period` には、抜けがあるときだけ `filled_weeks` を加える（抜けの無いモデルの golden は 1 文字も変わらない）。`tools/sweep_flags.py` は `_detect_period()` を呼んでいるので、同じく直る |
| `wom/gui/app.py` の `_auto_detect_planning_period()` | 同じ関数を使う。Start Week・# Weeks に入れ、抜けがあればログと画面の下の状態欄（警告の色）に出す。計画の木に `sc_tree.period_filled_weeks` |

需要 0 で埋める処理そのものは変えていない。計画の週の名前（`_build_week_labels`、GUI の WOMConfig の週）は、もともと暦の週で作られている。需要のロットは週の名前で置かれるので、CSV に無い週には需要が置かれない（＝需要 0）。直したのは、**期間の長さ**だけ。

### 1.3 ほかに「週の名前の数」を使っている箇所の調査（依頼 §2-4）

| 箇所 | 中身 | 判断 |
|---|---|---|
| warmup の生成（`wom/engine/warmup.py`） | `weeks_between()`・`week_minus()`（暦の週） | 問題なし |
| Planning Engine・プラグイン（Holiday・Harvest など）・Flow Check・LOVEM の観測・World Map（`flows.py`）・台帳（`wom/valuechain`） | 計画の木の `week_labels`／`num_weeks()` を使う | 期間の修正に従う。問題なし |
| Run Simulation（money、`wom/engine/demand.py`） | GUI の Start Week・# Weeks から作った週に、需要を `reindex(fill_value=0)` で置く | GUI の検出の修正に従う。問題なし |
| `wom/ppc/ppc_cockpit_app.py`（週・月の集計の表示） | PPC の結果にある週の名前を並べて、表示用にまとめる | 表示の集計で、計画期間を決めていない。変えていない |
| `wom/ppc/ppc_psi_bridge.py` `summarize_psi_records()` | ログの 1 行に「何週分の記録があるか」を出す | ログの文言だけ。変えていない |
| `wom/worldmap_ne/model.py`（試作の窓の需要の流れ） | 需要 CSV にある週を並べる | 計測用の試作（「計画の結果ではない」と表示済み）。計画期間と関係しない。変えていない |
| `wom/gui/app.py` 397 行（KPI の DataFrame の週） | 結果の表にある週を並べて描く | 表示。変えていない |

---

## 2. golden の変化（意図した変化として再生成）

再生成の前の `tests/test_golden.py`：`2 failed, 14 passed`。落ちたのは apparel-us-2026 と rice-japan-2027-2028 だけで、ほかの 11 件と legacy の 3 件（Cookie・ev-thailand・soysauce-jpy）は変わらなかった。legacy にこの 2 モデルは無い。

### 2.1 apparel-us-2026（プラグイン `safe`）

| 項目 | 前 | 後 | 理由 |
|---|---:|---:|---|
| `period` | 2025-W37 × 91 週（〜2027-W22） | 2025-W37 × **121 週**（〜2027-W52）、`filled_weeks` 30 週 | 需要 CSV に無い週（季節の切り替えの週 2026-W07・W08・W14・W15 …… 2027-W46・W47、2026-W53）が 30 週あった |
| 販売（leaf_out の S の合計、全製品） | 249,172 lot | **357,016 lot** | 2027-W23〜W52 の需要 107,844 lot が計画に入った。需要 CSV の全量 357,016 と一致 |
| PSI（製品ごとの P・S・I） | | | S1〜S3 は変わらない。S4〜S8（2027 年後半に販売のある季節）は、全ノードの P・S が増えた（例：Apparel_Outsourced_S4 の DC_Import_Buffer P 13,542 → 23,884、I の合計 40,626 → 71,652）。CO は全ノード 0 のまま |
| PPC の売上 `revenue_base` | 12,209,428 | 17,493,784 | 販売が増えた分 |
| PPC の原価 `cost_base` | 7,027,273.33 | 10,068,743.74 | 同上 |
| PPC の粗利 `gross_profit_base` | 5,182,154.67 | 7,425,040.26 | 同上（粗利率 42.4% は変わらず） |
| PPC の関税 `tariff_base` | 822,890.53 | 1,179,045.34 | 同上 |
| PPC の `total_lots` | 312 | 444 | 同上 |
| forward・backward・config・products | 変わらない | | |

### 2.2 依頼の「102,302 lot」について

需要 CSV（`apparel-us-2026/demand_forecast.csv`）を週ごとに合計すると、次のとおり。

- 前の期間の最後の週 2027-W22 より後（2027-W23〜W52）の需要は **107,844 lot**。
- 依頼の 102,302 は、これから 2027-W23 の 5,542 lot を除いた値（2027-W24 以降の合計）と一致する。数え始めが 1 週ずれていたと考えられる。
- 計画に入った販売の増分も 107,844 lot（249,172 → 357,016）で、CSV の全量と一致する。

### 2.3 rice-japan-2027-2028（HolidayCalendar・BufferingStockOptimizer・CapacityOverride・HarvestBatch）

| 項目 | 前 | 後 | 理由 |
|---|---:|---:|---|
| `period` | 2026-W01 × 156 週（〜2028-W51） | 2026-W01 × **157 週**（〜2028-W52）、`filled_weeks` ["2026-W53"] | 需要 CSV に 2026-W53 が無かった（年をまたぐ W53） |
| 販売（leaf_out の S の合計） | 235,316 lot | 236,937 lot | 2028-W52 の需要 1,621 lot が計画に入った |
| PSI | | | 2028-W52 の需要が上流へ伝わり、DC・精米・玄米倉庫・産地の S・P・CO が増えた（例：Koshihikari の Retail_KANTO S 72,510 → 73,009、Genmai_Souko_Niigata の CO 5,616,018 → 5,657,603）。Koshihikari の田（Tanbo_Niigata）の P・S は変わらない（HarvestBatch の収穫の枠が上限、shortfall 35,719 lot のまま） |
| forward `cap_hard_sealed` | 8,572 | 8,658 | 増えた需要のうち、能力の上限で止められた lot |
| PPC の売上 | 1,829,200,000 | 1,841,995,800 | 販売が増えた分 |
| PPC の原価 | 1,124,103,687 | 1,132,460,983 | 同上 |
| PPC の粗利・粗利率 | 705,096,313・38.5467% | 709,534,817・38.5199% | 同上 |
| PPC の `total_lots` | 1,240 | 1,248 | 同上 |
| backward・config・products | 変わらない | | |

rice の需要 CSV の合計（233,529）より販売の合計（236,937）が大きい。これは HolidayCalendar の需要の倍率（GW・お盆・年末年始の 1.15〜1.35 倍、GW 明けの 0.85 倍）による。今回の修正とは関係しない。

---

## 3. 受入条件

| # | 条件 | 結果 |
|---|---|---|
| 1 | apparel-us が 2025-W37〜2027-W52（121 週）、需要が計画に入る。rice に 2028-W52 | **満たす**：headless と GUI の両方で apparel-us 121 週（埋めた週 30）、rice 157 週（埋めた週 2026-W53）。apparel-us の需要 357,016 lot がすべて計画の販売に入った（増分 107,844、§2.2）。rice は 2028-W52 の 1,621 lot が入った |
| 2 | golden：変わるのは 2 件だけ | **満たす**：再生成の前に、落ちるのが 2 件だけであることを確かめた。2 件を再生成し、変わった項目を §2 に記した |
| 3 | 週の抜けの単体テスト | **満たす**：`tests/test_plan_period.py`（7 passed） |
| 4 | 全テスト緑 | **満たす**：710 passed・失敗 0（§4） |

**テスト `tests/test_plan_period.py`**：
- 途中の抜け：2027-W03・W04 を埋めて 6 週。
- 年をまたぐ W53 の抜け：2026-W52 → 2027-W01 のとき 2026-W53 を埋める。2027-W52 → 2028-W01 は 2027 年に W53 が無いので埋めない。
- 抜けが無いとき：前と同じ期間になり、警告も出ない（順番や重複にもよらない）。
- `2027-W2` と `2027-W02` を同じ週として扱う。
- ISO の週でない名前（`2027-W53`）は止まる。
- サンプル 2 モデルの期間・埋めた週。
- headless と GUI の両方がこの関数を使い、前の作り（`sorted(...unique())` の数）が残っていない。

**画面の確認**：GUI で Load Model Folder を行うと、次のとおりになった。
- apparel-us：Start Week 2025-W37・# Weeks 121、状態欄とログに 30 週の警告。
- rice：2026-W01・157、2026-W53 の警告。
- Cookie：2025-W37・121、警告なし。

---

## 4. 全テストの結果

`python -m pytest tests/ -q -p no:cacheprovider`（ほかの処理と並べずに 1 回で実行）：

```
710 passed, 3 skipped  (21 分 11 秒)
```

- **失敗 0**。Tk の不安定なテストも、この回は通った。
- skip の 3 件は、既存のテストの条件つきの skip（表示の環境などによる。今回の変更とは関係しない）。
- golden は 13 件と legacy 3 件がすべて通った（apparel-us・rice は再生成した値で）。
- 新しいテスト `tests/test_plan_period.py` は 7 件。

---

## 5. 大杉さんが確かめる手順

1. `python -m main` → Load Model Folder… で `data/sample/apparel-us-2026`。
   - 左の Planning Config が Start Week `2025-W37`・# Weeks `121` になる。
   - 下の状態欄に「⚠ 需要 CSV に無い週 30 週を需要 0 として計画期間に含めた：2026-W07, …」と出る。
2. Run Planning Engine。PPC タブの売上が 17,493,784（前は 12,209,428）になる。
3. `data/sample/rice-japan-2027-2028` を読み込むと 157 週になり、2026-W53 の警告が出る。
4. headless で確かめる場合は、次を実行する。最初に `[Headless] WARNING …` の行が出て、スナップショットの `period.filled_weeks` に埋めた週が入る。

   ```powershell
   python -m tools.run_headless_from_folder --model-dir data\sample\apparel-us-2026 --plugins safe --out output\period_check.json --quiet
   ```

5. 需要 0 の週を CSV に書き足せば、警告は消える。計画の結果は同じになるはずだが、これは確かめていない。
