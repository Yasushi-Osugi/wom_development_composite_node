# Request Letter — 確認用のテスト一式（smoke・領域別・全テスト）を作る

- 宛先：Claude Code君
- 依頼者：大杉（WOM Project Owner）／起草：Claude君、2026-10-15
- 基準：`wom-v1r5m1_cap_trial` の最新（この依頼書を入れた commit。5907b28 の次）。着手時の SHA を報告する
- 種別：テストの選び方の仕組み（`tests/conftest.py`・`pytest.ini`・道具）と文書。**テストの中身・golden・保護対象のコア・`wom/` のコードは変えない。commit はしない**

## 0. 目的

全テストは単独の実行で約 15〜16 分（直近 885 passed・3 skipped）。依頼のたびに何度も全テストを回すと、Code君の時間と利用の上限を大きく使う。並行して回すと、golden の warm-up の書き込みが競合して落ちることもある（CLAUDE.md の注意）。

そこで、**確かめる範囲に合わせて回すテストを選べる一式**を作る：

| 段 | 使う場面 | 目安の時間 |
|---|---|---|
| **smoke** | 作業の途中に何度でも。壊れていないかの最低限の確認 | 3 分以内 |
| **領域別**（area） | 直した所に関係する領域だけ。作業の途中・終わりの前 | 1 領域 5 分程度まで（目安） |
| **全テスト**（full） | 依頼書ごとに最後に 1 回だけ。保護対象のコアを直したときは必須 | 約 16 分 |

これからの依頼書は「途中は smoke と領域 rice、最後に full を 1 回」のように、回す段を書く。

## 1. 守ること

1. **テストを消さない・弱めない・飛ばさない。** assert・期待値・パラメータは変えない。選び方（印・一覧）を足すだけ。
2. **全テストの結果が今と同じ。** 作業の前後で `pytest --collect-only -q` のテストの ID の一覧が一致し、全テストの件数（passed・skipped）が同じであること。
3. golden（`tests/golden/`）と保護対象のコア（CLAUDE.md「禁足ルール」の 6 ファイル）は触らない。
4. **新しい依存を足さない**（pytest-xdist なども入れない。オフライン）。pytest の標準の機能（marker・`-m`・`-k`・conftest）で作る。
5. テストのファイルの一つ一つに印を書き込む方法は避け、**一か所の対応表**（ファイル → 領域）で印を付ける（例：`tests/conftest.py` の `pytest_collection_modifyitems`）。新しいテストのファイルを足すとき、直すのは対応表だけにする。

## 2. 作業

### 2.1 時間を測る（最初に 1 回だけ）

1. 全テストを**単独で**（ほかの pytest を同時に回さない）1 回実行し、テストごとの時間を取る：
   ```
   set PYTHONDONTWRITEBYTECODE=1
   python -m pytest tests/ -q -p no:cacheprovider --durations=0
   ```
2. 結果を `output/test_timing/`（git の対象外）に保存し、**ファイルごとの合計の時間**の表を作る（件数・合計秒・最も重いテストとその秒）。
3. 重いテストが何に時間を使っているか（同じモデルの計画を何度も回している・LOVEM の照合・GUI の描画など）を、分かる範囲で 1 行ずつ書く。**速くする変更はしない**（提案として報告するだけ）。

### 2.2 領域と印

印（marker）を `pytest.ini`（無ければ作る）に登録し、未登録の印を誤りにする（`--strict-markers`）。

**領域の印**（下は案。ファイルの中身と時間を見て直してよい。一つのファイルが複数の領域に入ってよい）：

| 領域 | 主なテストのファイル（案） |
|---|---|
| `core` | Planning Engine と 3 層テストの Unit・Integration：`test_lot_identity_flow`・`test_backward_*`・`test_push_pull_*`・`test_step7_capacity`・`test_step8_push_pull`・`test_capacity_soft*`・`test_capacity_zero_blank`・`test_bom_qty`・`test_plan_period`・`test_planning_state`・`test_holiday_*`・`test_operating_calendar`・`test_shift_cap_soft`・`test_demand_envelope_soft`・`test_kitting_stage1`・`test_composite_kitting_recovery`・`test_stage3a*`・`test_stage_d_part0`・`test_warmup_materialize`・`test_init_stock_days_wiring`・`test_flow_check`・`test_report_start` |
| `capacity` | 上位の層：`test_capacity_layer_trial`・`test_generation_line_upper_layer`・`test_cpu_size_plan_wide` |
| `rice` | `test_rice_*`・`test_report_start` |
| `plugins` | `test_step10_hooks`・`test_buffering_stock_optimizer_plugin`・`test_decouple_optimizer`・推奨プラグインの組のテスト |
| `ppc` | `test_ppc_*`・`test_valuechain_*`・`test_money_units` |
| `allocation` | `test_allocation_*`・`test_merit_order*`・`test_pareto_front`・`test_regime_map` |
| `lovem` | `test_lovem_*` |
| `gui` | tkinter を使うテスト（`test_gui_panel_invariants`・`test_sim_mgmt_display`・`test_lovem_viewer`・`test_ppc_run_info` の GUI の部分・`test_s1_view_model`・`test_s2_actual_shipment_eval` など） |
| `worldmap` | `test_worldmap_*` |
| `golden` | `test_golden`（モデルごとに `-k <モデル名>` で 1 件だけ回せることも確かめる） |
| `public` | `test_no_real_names`・`test_public_readiness`・`test_smartx_evidence_ranges` |

**重さの印**：
- `slow`：1 件で 20 秒以上かかるテスト（2.1 の実測で決める。境は報告で調整してよい）。
- `gui`・`lovem`・`golden` は、領域の印をそのまま「外す」ためにも使う（例：`-m "not gui and not lovem"`）。

**smoke の印**：各領域から速くて代表になるテストを選ぶ。必ず入れるもの：
- `core` の 3 層テストの Unit と Integration（速いもの）
- golden は小さいモデル 1〜2 件（例：`bom-test-2026`・`Cookie-jp-2026`。実測で選ぶ）
- `test_no_real_names`
- 下の 2.4 の「対応表の漏れ」のテスト

合計 3 分以内（Owner の Windows で）。入らなければ、何を外したかと理由を報告する。

### 2.3 実行の道具 `tools/quick_check.py`

```
python -m tools.quick_check --smoke
python -m tools.quick_check --area rice,capacity
python -m tools.quick_check --golden rice-japan-2027-2028
python -m tools.quick_check --changed          # 変更したファイルから領域を選ぶ
python -m tools.quick_check --full
python -m tools.quick_check --area rice --dry-run   # 回す pytest のコマンドを表示するだけ
```

- 中では pytest を**一つのプロセスで順に**回す（並行させない）。`PYTHONDONTWRITEBYTECODE=1`・`-p no:cacheprovider` を付ける。
- 最後に 1 行で「段・領域・passed/failed/skipped・かかった時間」を表示する。
- **`--changed`**：`git --no-optional-locks status --porcelain` と `git diff --name-only HEAD` の変更したファイルから、領域を選ぶ。対応の例：
  - 保護対象のコアの 6 ファイル → **「full と 3 層テストが必要」と表示**し、smoke と `core`・`golden` を回す（full は自動では回さない）
  - `wom/capacity_layer/rice_*`・`wom/plugins/rice_*` → `rice`・`capacity`
  - `wom/ppc/`・Value Chain → `ppc`
  - `wom/gui/` → `gui`
  - `data/sample/<モデル>/` → そのモデルの golden 1 件と、関係する領域
  - `docs/`・`requests/`・`*.md` だけ → `public` だけ
  - 対応の無いパス → smoke ＋「対応の無いパス」の警告
  - 対応はパスの規則の表（一か所）にまとめ、`tests/README.md` に同じ表を載せる。

### 2.4 漏れを防ぐテスト

`tests/test_test_areas.py`（名前は任せる）を足す：
- `tests/test_*.py` のすべてが、どれか一つ以上の領域に入っている（新しいファイルが対応表から漏れると落ちる）。
- smoke に入っているテストが 1 件以上ある。
- 登録していない印が使われていない。

このテストは smoke に入れる。

## 3. 受入条件

| ID | 検査 |
|---|---|
| Q-1 | 2.1 の時間の表（ファイルごと）と、重いテストの上位 10 件 |
| Q-2 | 作業の前後で `--collect-only` のテストの ID が一致し、全テストの件数が同じ（passed・skipped。直近 885・3） |
| Q-3 | `--smoke` の件数と時間（3 分以内） |
| Q-4 | 各領域の件数と時間の表（`--area <領域>` を一つずつ。時間は `--durations` の合計からの見積もりでもよい。実際に回すのは smoke・rice・core だけで足りる） |
| Q-5 | `--changed` の例：rice の上位の層のファイル・保護対象のコア・`data/sample/` の 1 モデル・文書だけ、の 4 つで、選ばれた領域を `--dry-run` で示す（ファイルを実際に変えずに、パスを引数で渡す仕組みがあればそれで） |
| Q-6 | 2.4 のテストが緑。わざと対応表から 1 ファイル外すと落ちることを一度確かめる（確かめた後は戻す） |
| Q-7 | `git diff --stat`：既存の `tests/test_*.py` の中身に変更が無い（変更は conftest・pytest.ini・新しいテスト・道具・文書だけ） |

**全テストの実行は 2 回まで**（2.1 の測定と、最後の Q-2 の確認）。途中は smoke と領域で確かめる。

## 4. 文書

- **CLAUDE.md**：冒頭の「テスト実行」を、段の表（smoke・領域・full）と `tools/quick_check.py` の使い方に書き換える。「golden は並行させない」の注意もここに寄せる（今の注意の節は残し、ここへの参照を足す）。
- **`tests/README.md`**（新しく）：段・領域の一覧・印・パスと領域の対応表・新しいテストを足すときの手順（対応表に 1 行足す）。
- **依頼書の種類ごとの段の提案**（報告に書く。Owner と Claude 君が決める）：

| 依頼の種類 | 途中 | 最後 |
|---|---|---|
| 文書・依頼書だけ | — | `public` |
| サンプルのデータだけ | そのモデルの golden | smoke ＋ そのモデルの golden |
| プラグイン・上位の層・PPC・GUI | smoke ＋ 関係する領域 | full 1 回 |
| 保護対象のコア | smoke ＋ `core` ＋ `golden` | full 1 回 ＋ 3 層テストの明示 |

  実測を見て、この表を直してよい。
- `docs/WOM_Start_Here.md` は触らない（Claude 君が直す）。

## 5. 報告

- 報告書：`docs/development/WOM_QuickCheckTests_Report.md`。着手の SHA、Q-1〜Q-7、領域の対応表、速くできそうなテストの提案（実施はしない）。
- 判断に迷った分類（どの領域に入れるか）は、決めた分類と理由を 1 行で書く。止める必要は無い。
- 最後に、追加・変更のファイルの一覧。
- commit・push はしない（Owner が commit する）。
