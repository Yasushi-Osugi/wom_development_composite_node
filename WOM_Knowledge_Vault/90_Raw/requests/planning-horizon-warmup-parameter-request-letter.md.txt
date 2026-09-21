# Coding Request Letter: 計画期間パラメータ（`Warmup_LT` / `Planning_Start`）の外出しと warm-up 行の materialize

対象ブランチ: `wom-v1r2m2`
関連: `docs/design/holiday_calendar_push_lead_time_and_planning_horizon.md` §9.5 / §10–11、
      `docs/design/planning_warmup_and_reporting_horizon.md` §5–7・§13、
      CLAUDE.md「v1r2m2：先行生産の per-node パラメータ `init_stock_days`（X2）」、
      commit `eb8691e`（soysauce-jpy を手作業で26週 warm-up 化した暫定対応）

---

## 1. Business question / 解決したい問題

Buffer node の startup CO を解消するには「販売開始より前から供給準備（調達・生産・輸送・在庫形成）を計算する助走区間（Planning Warm-up Period）」を Planning Horizon に含める必要がある。これは §9.5 で確立した二層のうち**第1層（横軸＝必要条件）**である。

しかし現状の WOM には、この助走区間を制御する**明示的な計画パラメータが存在しない**。計画開始週は `demand_forecast.csv` の最早週から自動検出されるだけで、助走を作るには「手でゼロ需要行と能力行を CSV に足す」しかない（実際 `eb8691e` で soysauce-jpy に2026-W28〜W53の行を手作業追記して CO=0 を得た）。

本リクエストは、この手作業を**基本計画パラメータ `Warmup_LT` / `Planning_Start` として外出し**し、助走行の生成を**規約化された materialize 処理**に置き換える。§13.4 が将来設計として書く「Warm-up の自動算定」の、手前の Stage 1（人が週数を与える手動ノブ）にあたる。

---

## 2. 出自・背景

- 2026-08-02 のセッションで、soysauce-jpy の FG_WH_Noda（輸出前バッファDAD、ss_days=21）に大きな startup CO が出ることを確認。
- 横軸を延ばす（demand の手前にゼロ需要週を足す）と CO が激減、既存の X1（ss_days=21）が助走区間で安全在庫を積み、**20週で残差65/週、26週で CO=0** となった。26週＝最深レーン（輸出DC lt6+ss3＋leaf1、上流 Bottling/Brewing/Materials）の累積 B+X1 に対応。
- その際「`init_stock_days`（X2）で残差を潰せるか」を試したが、横軸を延ばさず X2 だけ足すと `past_due` が増えて**悪化**した。→ 残差は初期在庫不足ではなく**横軸の境界効果**であり、対処は横軸の前倒しであると確定（§9.5 の注意の実証）。
- 大杉さんの判断：計画状態の file load/save・read/write を素直にするため、助走行は **CSV に materialize** する方針とする。

---

## 3. 現状のコード考古学（事実・wom-v1r2m2）

- **期間の自動検出**：`tools/run_headless_from_folder.py` `_detect_period()`（L55付近）が `demand_forecast.csv` の週集合から `(start_week, n_weeks)` を決める。GUI（`wom/gui/app.py` `_build_planning_context`）も同じロジック（コメント「GUI と同じ」）。→ **計画開始週＝demand_forecast の最早週**。他の明示パラメータは無い。
- **週次CSV**：`demand_forecast.csv`（sku_id,region,week,quantity）／`capacity_plan.csv`（sku_id,node_name,week,max_supply,source）／`operating_calendar.csv`（sku_id,node_name,week,shifts）。いずれも週を主キーに持つ。
- **latest-prior-week 参照**：`ppc_market_price.csv` / `ppc_supplier_cost.csv` 等は「その週以前の直近行」を参照（`wom/ppc/ppc_rules.py`）。→ 助走行は不要。
- **holiday_calendar.csv**：日付固定イベント。助走週は通常営業＝行の不在で正しく表現される。→ 助走行は不要。
- **保護対象コア（禁足）との関係**：期間検出・CSVロードは orchestration 層（app.py / headless / loader）にあり、`backward_planner.py` / `forward_planner.py` / `plan_copy.py` / `plan_node.py` / `sc_tree.py` / `push_pull.py` には触れない。→ 本変更は**禁足コア非該当**（ただし golden で回帰を固定する）。

---

## 4. 設計の核（確定済みの判断）

セッションでの合意事項を確定仕様とする。

**D1. CSVごとに助走行の埋め方を分ける**
- `demand_forecast.csv` … 助走週は **quantity=0**（W1に存在する sku×region の全組をゼロで生成）。W1のコピーは禁止（実需要を捏造すると CO が再発するため）。
- `capacity_plan.csv` … 各 node の**最初の実週の値を後方コピー**（助走区間に生産能力が存在するように）。
- `operating_calendar.csv` … 各 node の**最初の実週の shift を後方コピー**。
- `holiday_calendar.csv` / `ppc_*` / `sku_master` / `inventory_master` … 変更不要。

**D2. パラメータの持ち方**
- 主キー **`Warmup_LT`（週数、既定 0）**。`Planning_Start`（週ラベル）は任意 override。
- 導出：
  ```
  demand_start    = min( demand_forecast の週 )
  effective_start =
      Planning_Start 指定あり : min( Planning_Start, demand_start )   # 既存の早いデータを失わない防御
      Warmup_LT > 0           : demand_start − Warmup_LT
      それ以外                : demand_start                          # 既定0＝現状動作
  ```
- 既定 `Warmup_LT=0` で挙動完全不変（golden 緑）。

**D3. CSV に materialize（in-memory 合成ではなく）**
- 助走行を実ファイルに書き出し、load/save の一貫性を保つ。
- **生成物と原本の区別**：助走行は「first-nonzero-demand-week より前の週の行」として一意に識別できる（別マーカー列を増やさずに済む）。`capacity_plan.csv` は既存 `source` 列に `warmup` を入れて可読性を上げてもよい。
- **idempotent**：再生成は「effective_start 更新 → 既存の助走行（=demand_start より前の週の行）を全 strip → 現行 `Warmup_LT` で再合成」。二重追記を構造的に防ぐ。

---

## 5. 提案する設計

### 5.1 config の置き場所（確定：per-model `planning_config.csv`）
per-model の小さな **`planning_config.csv`**（`key,value` 2列）を新設し、`warmup_lt` / `planning_start` を持たせる。モデルごとにCSVで完結する WOM の流儀に合致し、load/save でそのまま持ち回れる。
```
key,value
warmup_lt,26
planning_start,          # 空＝未指定（override しない）
```
（代替案：既存 cfg dict にコマンドライン/GUI から渡す。ただし「materialize＋load/save」方針とは per-model CSV の方が整合。）

### 5.2 materialize のトリガ（確定：案B-safe）

planning の初期処理（`python -m main` / headless の pipeline 起動前）に materialize を**内蔵**し、1回の起動で「助走行の生成 → planning」まで完結させる。案B の弱点（ロードの副作用・test との相性）は次の2条件で無害化する。

1. **決定的（byte-stable）**：同じ `warmup_lt` なら生成CSVのバイト列が毎回同一。→ materialize 済みモデルで再実行しても **git diff ゼロ**（working tree が汚れない）。
2. **write-if-needed**：初期処理でまず「現状の助走行が `warmup_lt` と整合するか」を判定し、**整合していれば書き込みをスキップ**（純粋 read、サマリーに `already up to date`）。不整合・未生成のときだけ strip→再生成して書く。→ golden ハーネス／headless の read-only 実行で余計な書き込みが起きない。

実装形：materialize ロジックは **import 可能な関数**（例 `wom/engine/warmup.py: materialize_warmup(model_dir, cfg)`）として実装し、planning 初期処理（app.py `_build_planning_context` / headless）がこれを呼ぶ。加えて同じ関数を叩く薄いCLI `python -m tools.gen_warmup_rows --model-dir <dir>` も提供（普段は1起動、明示的に作り直したいときはCLI、の両対応）。

**サマリー出力**：materialize の実行結果を stdout に1ブロック出力する（例：`effective_start=2026-W28 / warmup_lt=26 / demand:+156 rows=0 / capacity:+78 rows(copy) / opcal:+26 rows`、または `already up to date (no change)`）。実行時の**観測性**の層であり、冪等性の“機構”でも durable な監査記録でもない（§5.4）。

### 5.3 週ラベル生成（必須の実装規約）
助走週のラベルは必ずエンジンと同じ `datetime.date.fromisocalendar` / `isocalendar` で生成する。**2026 は ISO W53 まで存在**し、文字列演算だと年跨ぎでずれる（本セッションでも `week_list` 実出力で確認して回避した）。

### 5.4 冪等性・監査性が「どこから来るか」（役割分担）
- **冪等性**＝アルゴリズム（strip→再生成。strip 基準は「最初の“非ゼロ”需要週より前の行」）。サマリー出力ではなくこの手続きが担保する。毎起動で走らせても安全。
- **監査性（durable）**＝コミット済みの materialize 済みCSV＋golden。案B-safe でも materialize 先はCSVなので、案A と同じ監査担保が保たれる（git diff で「プランナが見る入力」が確認でき、golden が凍結）。
- **サマリー出力**＝上記2つを実行時に見える化する補助層（stdout は揮発性なので単体を監査記録にはしない）。

---

## 6. 影響ファイル（想定）

| ファイル | 変更 |
| :---- | :---- |
| `data/sample/<model>/planning_config.csv` | 新設（`warmup_lt` / `planning_start`） |
| `wom/engine/warmup.py` | 新設（`materialize_warmup(model_dir, cfg)`：strip→再合成→byte-stable 書き出し／write-if-needed／サマリー返却） |
| `tools/gen_warmup_rows.py` | 新設（上記関数を叩く薄いCLI） |
| `wom/gui/app.py`（`_build_planning_context`）/ `tools/run_headless_from_folder.py`（`_detect_period`/`cfg`） | planning 初期処理で `planning_config.csv` を読み `materialize_warmup` を呼ぶ（案B-safe）。以降は既存の自動検出が effective_start を拾う |
| `data/sample/soysauce-jpy-2027/planning_config.csv` | `warmup_lt=26`（既存の手作業助走行を規約に置換） |
| `tests/test_warmup_materialize.py` | 新設（下記 §9） |

※ 禁足コア（backward/forward/plan_copy/plan_node/sc_tree/push_pull）は無変更。

---

## 7. 段階実装（phased）

- **Phase 1**：`planning_config.csv` スキーマ＋`wom/engine/warmup.py`（`materialize_warmup`）＋薄いCLI。demand=0／capacity・opcal=copy-first-week／ISO週ラベル／idempotent strip（非ゼロ需要週基準）／byte-stable／write-if-needed／サマリー。単体・結合テスト。
- **Phase 2**：planning 初期処理（app.py `_build_planning_context` / headless）が `materialize_warmup` を呼び、`planning_start` override / `warmup_lt` を尊重。1起動で materialize→planning が完結。
- **Phase 3**：soysauce-jpy を `warmup_lt=26` に移行。`gen_warmup_rows.py` が `eb8691e` の手作業行と**同一の行集合**を生成することを確認（差分ゼロ）。golden 再生成（挙動不変のはず＝行が一致するため）。
- **Phase 4（将来・§13.4）**：`Warmup_LT` を最深レーンの累積 `B + X1 + X2` から自動算定（Stage 2）。`init_stock_days`（X2）を使う node があれば必要 warm-up はその分増える点を織り込む。

---

## 8. 後方互換・検証

- 既定 `warmup_lt=0` → materialize 何もしない → 既存11ケースの CSV・golden 不変。
- soysauce-jpy のみ `warmup_lt=26` を持ち、materialize 結果が現行コミット済み助走行と一致することを確認（Phase 3）。GM=28.0%・trust=32 が不変であることも確認（助走はゼロ需要ゆえ財務不変）。

---

## 9. 退行防止（Anti-Degrade）― 3層テスト

CLAUDE.md「禁足ルール＋3層テスト」に従う。

- **Unit**：`effective_start` 導出（`Warmup_LT` からの逆算、`Planning_Start` override、`min()` 防御、既定0）。
- **Integration**：`materialize_warmup` が合成モデルに対し、(a) demand=0 行を W1 の sku×region 分だけ生成、(b) capacity/opcal は各 node の最初の実週値を後方コピー、(c) ISO 週ラベルが年跨ぎ（W53）で正しい、(d) 二度実行しても行が増えない（idempotent）、(e) 同じ `warmup_lt` なら出力バイト列が同一（byte-stable）、(f) 既に整合済みなら書き込みをスキップ（write-if-needed の no-op）ことを assert。
- **E2E ゴールデン**：既定0で既存 golden 不変。soysauce-jpy は `warmup_lt=26` で再生成し、`eb8691e` の行と一致（差分が監査証跡）。

---

## 10. 設計判断メモ（open items）

1. ~~config 置き場所~~ → **確定：per-model `planning_config.csv`**（§5.1、2026-08-02 合意）。
2. ~~materialize トリガ~~ → **確定：案B-safe**（planning 初期処理に内蔵＋byte-stable＋write-if-needed＋サマリー、§5.2、2026-08-02 合意）。
3. **助走行の識別**：「最初の“非ゼロ”需要週より前の週の行」を助走とみなす規約（マーカー列不要）で十分か。`capacity_plan.source=warmup` は可読性のための任意付与。→ 実装で確定。
4. **X2 との相互作用と用語**：`Warmup_LT` は**運用者が与えるパラメータ**であり、その**取るべき最小値が「最深レーンの累積 `B + X1`」**（この例で26週）。`init_stock_days`（X2）を使う node があれば必要 warm-up はさらに増える（`required = Σ(B)+Σ(X1)+Σ(X2)`）。手動 `Warmup_LT` は X2 分も織り込むこと。自動算定は Phase 4（§13.4）。

---

## 11. ステータス行

- [ ] Phase 1：`planning_config.csv` ＋ `wom/engine/warmup.py`（`materialize_warmup`）＋薄いCLI ＋ Unit/Integration テスト（byte-stable / write-if-needed 含む）
- [ ] Phase 2：planning 初期処理が `materialize_warmup` を呼ぶ（案B-safe、1起動で materialize→planning 完結）
- [ ] Phase 3：soysauce-jpy を `warmup_lt=26` へ移行（`eb8691e` 行と一致確認）＋ golden 再生成
- [ ] Phase 4（将来）：`Warmup_LT` 自動算定（§13.4、X2込み）
