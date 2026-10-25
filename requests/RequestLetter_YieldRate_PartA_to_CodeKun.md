# Request Letter：完成品の出荷時点の歩留まり（yield_rate）— Part A：計画の数量

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-10-25）
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（起草時の先頭 `0ef44e4`。着手時の SHA を報告書に記録する）
- 前提：`requests/BSSEAF_Cosmetics_SG_Stage1-3_DesignMD_v0.2.md` §3.2・§6 D1・§7（化粧品の BS-SEAF 適用実験で見つかった差分）
- 種別：**保護対象のコアの変更を含む**（`AGENTS.md` §10）。本書がその依頼書である。3 層のテスト（単体・CSV からの結合・golden）を緑にし、大杉さんが diff を確かめてから commit する。**golden は 1 件も変わらないこと**（どのモデルも新しい列を持たないため）。
- 範囲：**計画の数量（lot をどの週に置くか・封じるか）だけ。** 投入の物量の解釈と金額（PPC・Value Chain）は Part B で別に依頼する。

---

## 0. 大杉さんの決定（2026-10-25）

品質は「**完成品の出荷時点の歩留まり（yield rate）**」として定義し、WOM の標準にする。ある週について、

- 設備の物理的な能力の上限 ＝ Capacity Hard ＝ **Sealing_Qty**（`cap_hard`）
- 生産操業計画（人のシフト体制） ＝ Capacity Soft ＝ **Production_Qty**（`cap_soft`）
- 当週の出荷量（当週の引当て可能な製品数）：**Ship_Qty ＝ Production_Qty × yield rate**

不良がどの工程で起きたかは見ず、完成品の出荷時点に一本化した歩留まりを、生産投入の計画に対する製造品質の実力として使う。**歩留まりを考慮した完成品の引当て可能出荷数量を、当週の生産計画 lot 数として扱う。** WOM Core に実装してよい。

## 1. 今の動き（コードで確かめたこと、`0ef44e4`）

- `PlanNode.cap_hard()`・`cap_soft()` は CSV の値をそのまま返す（None ＝ 未設定、0 ＝ 能力ゼロ）。`processing_limit()`・`planned_capacity()` は休業の週を 0 にした値を返す。
- MOM の能力を使って lot を置く・封じる箇所は次のとおり：

| ファイル | 箇所 | 使う値 | 中身 |
|---|---|---|---|
| `wom/engine/backward_planner.py` | `_apply_mom_cap_backward`（520〜540 行付近） | `cap_hard(w)`、`cap_soft(w)` | 充填の目標 `cap_int`（hard／soft の 2 モード）、cap_soft 超過の記録、超過分の前の週への押し戻し |
| `wom/engine/forward_planner.py` | Step 0a（702 行付近） | `cap_hard(w)` | 能力を超えた P を翌週の先頭へ繰り延べ（identity） |
| `wom/engine/forward_planner.py` | Step 0b（731 行付近） | `planned_capacity(w)` | cap_soft 超過の記録 |
| `wom/engine/forward_planner.py` | Kitting Gate の回復（975 行付近） | `processing_limit(w)` | 組立の成立数の上限 |
| `wom/engine/holiday_calendar_plugin.py` | `on_post_backward` の再配置（233 行付近） | `cap_hard(w)` | 閉鎖週から追い出した lot を開いている週の空きに入れる |
| `wom/capacity_layer/serial_adapter.py` | 状態の取り込み（136 行付近） | `processing_limit(w)` | 上位の層（既定 OFF）の能力 |
| `wom/engine/capacity_sealer.py` | 能力の負荷の報告（250 行付近） | `processing_limit`・`planned_capacity` | 稼働率と超過の判定（報告だけ） |
| `wom/engine/strategic_kpi.py` | 稼働率（265 行付近） | `processing_limit(w)` | 設備の稼働率（報告だけ） |
| `wom/lovem/observer.py` | `capacity.csv`（608 行付近） | `processing_limit`・`planned_capacity` | 列 `effective_limit`・`planned_capacity`（観測の記録） |

- 画面（`wom/gui/app.py` の 1878・2142・2263・4427 行付近）と headless の snapshot（`tools/run_headless_from_folder.py` 485 行付近）は、物理の能力（`cap_hard`）を表示・記録している。

## 2. 直すこと

### 2.1 属性と読み込み（`sc_tree_master.csv` → `sc_tree_builder.py` → `PlanNode`）

- `sc_tree_master.csv` に列 **`yield_rate`** を足す（MOM の行に書く）。`PlanNode.yield_rate: float`（既定 1.0）。
- 列が無い・空欄 ＝ **1.0**（不良なし。今の意味のまま）。
- 次は**読み込みで止める**（ファイル・行・ノード名・製品・値を出し、直し方を書く）：
  - 数値でない値、0 以下、1 を超える値
  - **MOM 以外のノード**（leaf_in・stockyard・supply_point・dad・leaf_out）の行に 1.0 以外の値がある（完成品の出荷時点に一本化する。決定 0）
  - **push の MOM**（`push_config.csv` で push になる MOM）に 1.0 以外の値がある。push の P は入庫で、Step 0a で封じないため、歩留まりが効かない（Part A の対象外。黙って効かないことを防ぐ）
  - **`lot_flow_mode=legacy`** で 1.0 以外の値がある（legacy は変えない。決定記録 D3）
  - **Rice Seasonal のプラグインが ON** で 1.0 以外の値がある（Rice は `rice_recipe.csv` の歩留まりを自分の層で持つ。二重にしない）
- `bom_qty` の `_parse_bom_qty` は不正な値を黙って 1 にするが、**`yield_rate` はこれに倣わない**（黙った既定値を作らない。Start Here §6）。

### 2.2 読み出し（`wom/model/plan_node.py`）

物理の値を返す今の読み出しは**変えない**（`cap_hard()`・`cap_soft()`・`processing_limit()`・`planned_capacity()` は物理の能力のまま）。引当て可能な完成品の lot 数を返す読み出しを足す：

| 新しい読み出し（名前は案） | 返す値 |
|---|---|
| `shippable_limit(w)` | `processing_limit(w)` が None なら None、そうでなければ **floor（`processing_limit(w)` × `yield_rate`）** |
| `shippable_planned(w)` | `planned_capacity(w)` について同じ |
| `shippable_of(value)`（内部の補助） | None → None、数 → floor（value × `yield_rate` ＋ 1e-9） |

- **端数は切り捨て**（作れない分を作れたことにしない）。浮動小数の誤差（例：100 × 0.29 ＝ 28.999…）で 1 lot 減らないように、`1e-9` を足してから切り捨てる。
- 0（能力ゼロ・休業）× y ＝ 0、None（未設定）は None のまま。**値の意味（None／0／正）は変わらない。**
- `yield_rate` ＝ 1.0 のときは、新しい読み出しが今の読み出しと**完全に同じ値**を返す（int に切り捨てる前の値も含めて、今の `int(ch)` と同じ結果になること）。
- 名前は案。もっと誤読しにくい名前があれば報告書に書いて変えてよい（例：`capacity` と書かない、`limit` が物理か良品かを名前で分ける）。

### 2.3 使う場所を切り替える

§1 の表のうち、**lot を置く・封じる箇所は、新しい読み出しに切り替える**：

| 箇所 | 切り替え |
|---|---|
| Backward `_apply_mom_cap_backward` | `cap_int` を `shippable_of(cap_hard(w))`／`shippable_of(cap_soft(w))` から作る。cap_soft 超過の記録も、良品の上限（`shippable_of(cap_soft(w))`）と比べる。閉鎖週 0 の扱いは不変 |
| Forward Step 0a | `ch` の代わりに `shippable_of(cap_hard(w))`（push を飛ばす条件は不変） |
| Forward Step 0b | `shippable_planned(w)` |
| Kitting Gate の回復 | `shippable_limit(w)` |
| HolidayCalendar の再配置 | 空き ＝ `shippable_of(cap_hard(w))` − 置かれている P |
| `serial_adapter` | `shippable_limit(w)`（上位の層が良品の上限で解く） |

報告・観測の箇所：

| 箇所 | 扱い |
|---|---|
| `capacity_sealer` の負荷の報告 | 稼働率と超過の判定は**良品の上限**で計算する。物理の `cap_hard`・`cap_soft` は今までどおり別の列で報告する |
| `strategic_kpi` の稼働率 | 良品の上限で計算する |
| LOVEM `capacity.csv` | `effective_limit`・`planned_capacity` は**エンジンが実際に使った上限（良品）**にする。`raw_hard`・`raw_soft` は物理の値のまま。列は増やさない（`yield_rate` を記録する列を足すかは報告書で提案） |
| 画面の能力の線、headless の snapshot | **変えない**（物理の能力のまま。golden を守る）。良品の上限の線を足すかは Part A の後に大杉さんが決める（設計書 §7.6） |

### 2.4 変えないもの

- lot のリスト（不良の分の Lot_ID は**作らない・消さない**）。Lot_ID はすべて良品の完成品。
- 能力の CSV（`capacity_plan.csv`・`cap_override.csv`・`operating_calendar.csv`）の意味。操業カレンダーから cap_soft を導く処理（shift × cap_hard ÷ 21）は物理の能力を作るので、そのまま。歩留まりはその後に掛かる。
- 休業・能力ゼロ・未設定の振る舞い。
- `sc_tree_to_df.py`・money・PPC・Value Chain・画面の数量（物量の解釈は Part B）。
- legacy の方式。

## 3. 受入条件

### 3.1 3 層のテスト

**単体**（合成の木。CSV を通さなくてよい）：

1. `yield_rate`＝0.97、`cap_hard`＝100 の MOM、需要 120 lot／週：Backward の MOM の P が各週 97 以下、超過は前の週へ押し戻される。Forward の P も各週 97 以下。
2. `demand_envelope`＝soft、`cap_soft`＝80、`yield_rate`＝0.9：充填の目標が 72。
3. cap_soft 超過の記録（Backward・Forward）が、良品の上限（floor（cap_soft × y））との比較で出る。
4. 能力ゼロ（0）・未設定（None）・休業の週：歩留まりがあっても 0／None／休業の振る舞いが今と同じ。
5. 端数：`cap_hard`＝100、`yield_rate`＝0.29 で上限 29（28 にならない）。
6. `yield_rate`＝1.0 と属性を付けない場合で、PSI（全ノード・全週・全バケットの Lot_ID の並び）が完全に一致する。
7. Kitting Gate の回復で、組立の成立数が floor（`processing_limit` × y）以下。
8. HolidayCalendar の再配置が、良品の上限を超えて lot を入れない。

**結合**（CSV → 実ローダ → ノード。cap_soft・`init_stock_days` の休眠と同じ型の事故を防ぐ）：

9. `sc_tree_master.csv` の `yield_rate` 列が `PlanNode.yield_rate` に入る（列なし・空欄は 1.0）。
10. §2.1 の止める条件（不正な値、MOM 以外、push の MOM、legacy、Rice Seasonal ON）がそれぞれ止まり、メッセージにファイル・行・値と直し方が出る。

**golden**：

11. `tests/golden/*.json`（15 件）と `tests/golden/legacy/`（3 件）が**すべて不変**。

新しいテストのファイルは `tests/conftest.py` の対応表に 1 行足す（領域は `core`、必要なら `capacity`）。

### 3.2 試行（写しで確かめる。リポジトリには入れない）

`output/yield_trial/` に Cookie-jp-2026 の写しを作り、比べる：

| | 条件 |
|---|---|
| T0 | そのまま |
| T1 | 両 SKU の MOM に `yield_rate`＝1.0 を明示 |
| T2 | `Factory_DP_JP` に `yield_rate`＝0.90。能力が効くように、必要なら写しの `capacity_plan.csv` の値を下げる（下げた値を報告に書く） |

- T0 と T1 の snapshot が一致する。
- T2 で、`Factory_DP_JP` の週の P の最大が floor（能力 × 0.90）以下。T0 と比べた当週出荷・遅配・期末注文残（Flow Check の表 2）の変化を表にする。
- T2 の Flow Check の数量の保存が成り立つ（不良で lot が消えていない）。

### 3.3 テストの段

- 途中：`python -m tools.quick_check --smoke`、`--area core,capacity`。
- 最後に 1 回：`python -m tools.quick_check --full`（保護対象のコアを変えたので必須）。golden を含む pytest は並行させない。

## 4. 文書

- `CLAUDE.md` の末尾に節を 1 つ足す（何を変えたか・報告書の場所・`yield_rate` の規則）。
- `CLAUDE.md` の「Master CSV スキーマ」の近くに、`yield_rate` の列の意味を短く書く。
- Start Here の R 表（業務ルール）への追記は、報告書を見て Claude君が行う。

## 5. 報告書

`docs/development/WOM_YieldRate_PartA_Report.md` に次を書く：

1. 着手時と完了時の SHA、変えたファイルの一覧。
2. §1 の表の各箇所を、どう切り替えたか（切り替えなかった箇所とその理由を含む）。§1 の表に**漏れていた箇所**があれば挙げる。
3. 新しい読み出しの名前と、その名前にした理由。
4. テストの結果（件数、full の時間）、golden 不変の確認。
5. §3.2 の試行の表。
6. Part B（投入の物量の解釈 1／y、良品 1 lot 当たりの原価）へ渡すこと。

## 6. commit

- 依頼書（`docs(request): …`）と実装を**別の commit** にする。git は大杉さんが Windows で行う。commit メッセージの下書きは `commit_msg*.txt`。
