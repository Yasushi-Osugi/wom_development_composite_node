# tests/ — テストの段（smoke・領域別・全テスト）

依頼書：`requests/RequestLetter_QuickCheckTests_to_CodeKun.md`。報告：`docs/development/WOM_QuickCheckTests_Report.md`。

## 段

| 段 | 使う場面 | コマンド | 実測（2026-10-15、Windows） |
|---|---|---|---|
| **smoke** | 作業の途中に何度でも | `python -m tools.quick_check --smoke` | 497 件・57 秒 |
| **領域別** | 直した所に関係する領域だけ | `python -m tools.quick_check --area rice,capacity` | 下の表 |
| | 変えたファイルから領域を選ぶ | `python -m tools.quick_check --changed`（または `--changed <パス> ...`） | |
| | 一つのモデルの golden | `python -m tools.quick_check --golden rice-japan-2027-2028` | 1 件 5〜20 秒 |
| **全テスト** | 依頼書ごとに最後に 1 回。保護対象のコアを直したときは必須 | `python -m tools.quick_check --full` | 892 件（889 passed・3 skipped）・15 分 24 秒〜17 分 49 秒 |

- `--dry-run` を付けると、回す pytest のコマンドを表示するだけ。
- `quick_check` は pytest を**一つずつ順に**回す（`PYTHONDONTWRITEBYTECODE=1`・`-p no:cacheprovider`）。最後の 1 行に「段・領域・passed/failed/skipped・時間」。
- **golden を含む pytest を並行させない**（golden の warm-up が CSV を書くので、並行すると落ちる）。
- pytest を直接使う場合：`python -m pytest tests/ -m "rice and not slow"`、golden を 1 件だけ：`python -m pytest tests/test_golden.py -k bom-test-2026`。

## 領域

一つのファイルが複数の領域に入ることがある。時間は全テストの実測（`--durations`）の合計（＋収集に約 6 秒）。

| 領域 | 中身 | 件数 | 時間の目安 |
|---|---|---:|---:|
| `core` | Planning Engine と 3 層テストの Unit・Integration | 289 | 2 分 10 秒（実測） |
| `capacity` | 上位の層（容量の層・世代ライン・Rice の層） | 79 | 約 2 分 |
| `rice` | Rice の季節のモデルと層 | 70 | 1 分 6 秒（実測） |
| `plugins` | プラグインと推奨の組 | 64 | 約 15 秒 |
| `ppc` | PPC・Value Chain・金額 | 113 | 約 2 分 40 秒 |
| `allocation` | Management 層の配分の分析 | 195 | 約 50 秒 |
| `lovem` | LOVEM の観測とビューア | 26 | 約 4 分 45 秒 |
| `gui` | tkinter の窓を開くテスト（と GUI の view model） | 142 | 約 1 分 30 秒 |
| `worldmap` | World Map | 20 | 約 35 秒 |
| `golden` | E2E の golden（`tests/golden/`、15＋legacy 3） | 18 | 約 2 分 |
| `public` | 公開の点検（実名・プラグインの組・証拠の範囲・この段の仕組み） | 49 | 約 30 秒 |

印：上の領域のほかに `smoke`、`slow`（1 件で 20 秒以上かかったテスト、7 件）。`-m "not slow"`・`-m "not gui and not lovem"` のように外すのにも使える。印は `pytest.ini` に登録（`--strict-markers`。未登録の印は誤り）。

## ファイルと領域の対応表

**一か所だけ**：`tests/conftest.py` の `AREAS`（ファイル → 領域）・`SMOKE`・`SLOW`。テストのファイル自体には印を書かない。

### 新しいテストのファイルを足すとき

1. `tests/conftest.py` の `AREAS` に 1 行足す（例：`"test_new_thing.py": ("ppc",),`）。
2. 速くて代表になるなら `SMOKE` にも足す（smoke は合計 3 分以内）。
3. 1 件で 20 秒以上かかるテストは `SLOW` に足す。

足し忘れると `tests/test_test_areas.py`（smoke に入っている）が落ちる。

## 変えたファイルと領域（`--changed`）

規則は `tools/quick_check.py` の `PATH_RULES`（上から順に最初に一致したもの）。

| 変えたパス | 回す領域 |
|---|---|
| 保護対象のコア 6 ファイル（`backward_planner.py`・`forward_planner.py`・`plan_copy.py`・`plan_node.py`・`sc_tree.py`・`push_pull.py`） | smoke・`core`・`golden`。**「full と 3 層テストが必要」と表示**（full は自動では回さない） |
| `wom/capacity_layer/rice_*`・`wom/plugins/rice_*` | `rice`・`capacity` |
| `tools/rice_*` | `rice` |
| `tools/lesson000_variants.py`・`docs/lessons/*` | `rice`・`public` |
| `wom/capacity_layer/*` | `capacity` |
| `wom/plugins/capacity_layer.py` | `capacity`・`plugins` |
| `wom/plugins/*` | `plugins` |
| `wom/engine/holiday_calendar_plugin.py` | `plugins`・`core` |
| `wom/engine/decouple_optimizer.py` | `plugins` |
| `wom/engine/money.py`・`landed_cost.py`・`wom/ppc/*`・`wom/valuechain/*`・`tools/valuechain_*` | `ppc` |
| `wom/allocation/*`・`wom/visualization/*`・`tools/*allocation*`・`tools/plot_merit_order_suite.py` | `allocation` |
| `wom/lovem/*`・`tools/lovem_*` | `lovem` |
| `wom/gui/*` | `gui` |
| `wom/cockpit/*` | `gui`・`allocation` |
| `wom/worldmap_ne/*`・`tools/*worldmap*` | `worldmap` |
| `wom/engine/*`（上以外）・`wom/model/*`（上以外）・`wom/data/*` | smoke・`core` |
| `wom/planning_state/*` | `core` |
| `tools/run_headless_from_folder.py` | smoke・`core`・`golden` |
| `tests/test_*.py` | そのファイルの領域（`AREAS`） |
| `tests/golden/*` | `golden` |
| `tools/quick_check.py`・`tests/conftest.py`・`pytest.ini` | `public` |
| `data/sample/<モデル>/...` | smoke ＋ そのモデルの golden（rice は `rice` も）。golden の無いモデルは smoke だけ |
| `docs/*`・`requests/*`・`*.md` | `public` |
| 対応の無いパス | smoke ＋「対応の無いパス」の表示 |
