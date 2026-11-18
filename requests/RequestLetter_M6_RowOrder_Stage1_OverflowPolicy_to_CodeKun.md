---
handoff:
  case_id: COCKPIT-M6-004
  task_id: row-order-bias-stage1-overflow-policy
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "この依頼書の commit 以降の HEAD（着手時の SHA を記録）"
  knowledge_used:
    - id: 行の順の偏りの直し方の設計
      version: "v0.3（Q1〜Q7 採用）"
      applicability: "requests/WOM_M6_RowOrderBias_FixOptions_DesignMD_v0.3.md §3（規則）・§4（小例）・§5（受け入れ）・§6 段 1"
    - id: 小例の参照計算
      version: "requests/WOM_M6_RowOrderBias_ref_examples.py"
      applicability: "単体テストの期待値"
  acceptance:
    ref: "この依頼書 §6"
  status: "試行可能"
  open_items: []
  stop_reasons: []
  next: implement
---

# Request Letter：行の順の偏りの直し方 — 段 1：能力を超えた分の押し戻し方を設定で選べるようにする（既定は今の動き）

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉（WOM Project Owner）／起草：Claude君（2026-11-18）／版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`
- **保護対象のコアの変更**（`wom/engine/backward_planner.py`）。この依頼書が認可。3 層のテストを緑にし、大杉さんが diff を確かめてから commit
- 範囲：`wom/engine/backward_planner.py`（呼び出しの差し替えだけ）、新しいモジュール `wom/engine/overflow_policy.py`（規則の本体）、`wom/engine/warmup.py`（設定の読み込み）、計画の入口（GUI・headless・sweep）、テスト、報告書。**Forward・PPC・Value Chain・正式なサンプル・golden は変えない**
- 出力：`output/roworder_stage1/`（git の対象外）

---

## 一言で

**Backward が工場の能力を超えた週に、どの市場のどの lot を前の週へ回すかを、`planning_config.csv` の `overflow_policy` で選べるようにしてください。`tail`（今の動き、既定）・`proportional_week`（その週の数に比例）・`balance_cut_ratio`（累積押戻負担率をそろえる）の 3 つです。既定は今の動きなので golden は変わりません。** 新しい二つの方式では、木の CSV の行の順を入れ替えても結果が変わらないことを確かめてください。

## 0. 決まっていること（大杉さん 2026-11-18、設計書 v0.3 §7）

Q1 案 C と案 C_a2 を試してから既定を決める／Q2 案 C は週ごとに比例し、端数は累積の丸め誤差で配る／Q3 優先の表は作らない／Q4 設定で選べる形、既定は今の動き／Q5 Forward は触らない／Q6 市場の中では要求週の遅い lot から／Q7 案 C_a2 の押し戻しは毎回数える（延べ）。

## 1. 作るもの

### 1.1 規則の本体 `wom/engine/overflow_policy.py`（新規、保護対象ではない）

- 設計書 §3 のとおり。入力：週の並びの lot の一覧、はみ出しの数 n、工場 × 製品の状態。出力：押し戻す lot の一覧と残す lot の一覧。
- 市場キーは Lot_ID の region（`LotIDGenerator.parse()` を使う。`split(":")` で取らない）。要求週は Lot_ID の週、連番は Lot_ID の連番。
- `proportional_week`：§3.1（累積の丸め前の割当 R_m、累積の不足 d_m ＝ R_m − A_m、floor の後に残りを d_m の大きい順。その週の lot の数を超えない。同点は丸め前の大きい順 → 市場キーの文字の順）。
- `balance_cut_ratio`：§3.2（母数＝処理済みの週に現れた lot〔同じ Lot_ID は 1 回〕、分子＝延べの押し戻し、1 lot ずつ負担率の小さい市場から、lot の無い市場は飛ばす、同点はその週の lot の多い順 → 市場キーの文字の順）。
- 市場の中の選び方（両方式）：§3.3（要求週の遅いものから、同じ週は連番の大きいものから）。
- **新しい二つの方式では、残す lot と押し戻す lot の並びを「要求週 → 市場キー → 連番」の順に並べ直して書く**（下流に CSV の行の順を持ち込まないため）。`tail` では並びを今のまま変えない。
- 状態は工場 × 製品ごと、Backward の実行ごとに新しく作る。

### 1.2 Backward（保護対象のコア、最小の変更）

- `_apply_mom_cap_backward` の `within_cap = s_lots[:cap_int]`／`overflow = s_lots[cap_int:]` を、方式が `tail` 以外のとき 1.1 の関数の結果に置き換える。`tail` のときは**今のコードの経路をそのまま通す**（並びも 1 つも変えない）。
- 押し戻した lot を前の週の S に入れること、CO に記録すること、最初の週で past_due にすること、cap_soft の記録は今と同じ。
- `BackwardPlanResult` に、方式と、工場 × 市場ごとの延べの押し戻し・母数を足す（追加だけ。報告と画面の比較に使う）。
- 方式は `BackwardPlanner(config={"overflow_policy": ...})` で受ける。

### 1.3 設定の読み込みと入口

- `wom/engine/warmup.py` に `read_overflow_policy(model_dir)` を足す（`read_lot_flow_mode` と同じ形）。ファイル・キーが無い、または空欄 ＝ `tail`。3 つ以外の値は**止める**（ファイル・値・使える値・直し方を出す。黙って `tail` にしない）。
- `BackwardPlanner(` を作るすべての入口で config に渡す：`wom/gui/app.py`（2 か所）、`tools/run_headless_from_folder.py`、`tools/sweep_flags.py`。ほかにもあれば全部（`grep` で一覧を報告に）。コックピットの案の実行は headless を通るので、モデルの `planning_config.csv` に書けば効くはず。確かめる。
- headless の snapshot：**キーが無い（`tail`）ときは config に何も足さない**（golden の config と一致させる）。`tail` 以外のときだけ `config.overflow_policy` を記録する。

## 2. テスト（3 層）

| 層 | 中身 |
|---|---|
| 単体 | 設計書 §4 の例 1〜6 を期待値どおりに（参照計算 `requests/WOM_M6_RowOrderBias_ref_examples.py` の出力。期待値はテストに数で書く）。合成の木（工場 1・市場 2〜3、能力の不足が続く・休業の週・少量の市場）で、行の順を入れ替えた 2 つの木の結果（押し戻す Lot_ID、各週の S・P・CO、past_due）が一致。`tail` は今のコードと同じ結果（既存のテストが守る） |
| 結合 | `planning_config.csv` → `read_overflow_policy` → `BackwardPlanner` の経路。空欄・無し ＝ `tail`、知らない値で止まる。headless の snapshot の config：キー無しで今と同じ、キーありで記録 |
| E2E | golden 16 件・legacy 3 件が**全件不変**（既定 `tail`） |

新しいテストのファイルは `tests/conftest.py` の領域の表に足す。**最後は `python -m tools.quick_check --full`**（保護対象のコアを変えたため必須）。

## 3. 醤油での受け入れの確かめ（設計書 §5 の 1）

到達点 6 の C02（21 シフト、配分なし）のモデルの写しを `output/roworder_stage1/` に作り、次の 6 つを headless で回す。

| 写し | 方式 | 木の行の順 |
|---|---|---|
| T1 | `tail` | 元 |
| T2 | `proportional_week` | 元 |
| T3 | `proportional_week` | 入れ替え（到達点 6 §3.3 と同じ：欧州の DC を先に、子を NL・BE・FR の順） |
| T4 | `balance_cut_ratio` | 元 |
| T5 | `balance_cut_ratio` | 入れ替え |
| T6 | `tail` | 入れ替え（今の動きでは変わることの確認。到達点 6 §3.3 の再現） |

- **T2 と T3、T4 と T5 で一致すること**：市場別の ④・⑤、供給する Lot_ID と納品の週、数量の保存、能力・休業の条件への適合。
- T1 が到達点 6 の C02 と一致（市場別の当週・未充足）。T6 が到達点 6 §3.3 の入れ替えの結果と一致。
- 市場別の ④ ÷ ① と、工場 × 市場の延べの押し戻し・累積押戻負担率を表に。**総納品は合格の条件ではない**（変わったら理由を書く）。

## 4. 重い処理の注意（前回、途中で止まったため）

- 段ごとに結果をファイルに書いてから次へ（実装 → 単体・結合 → 醤油の 6 つ〔1 つずつ書く〕→ `--full`）。
- `--full`（15〜18 分）は、出力をファイル（`output/roworder_stage1/quick_full.txt`）に書き、終わったら末尾の行を読む。
- 最後の画面の報告は短く。表は報告書と付録に。

## 5. しないこと

既定を替えること・golden の作り直し（段 3 の判断の後）、化粧品での比較（段 2）、Forward の変更、優先の表、画面の変更。

## 6. 合格の条件

| # | 条件 |
|---|---|
| S1 | `overflow_policy` の 3 方式が選べ、知らない値で止まる。全入口で渡る（一覧つき） |
| S2 | 単体で設計書 §4 の例 1〜6 が期待値どおり。合成の木で行の順の入れ替えに対して不変 |
| S3 | 醤油の T2＝T3、T4＝T5（§3 の項目すべて）。T1・T6 が到達点 6 を再現 |
| S4 | golden 16 件・legacy 3 件が全件不変。`--full` が通る |
| S5 | `tail` の経路で `backward_planner.py` の動きが 1 つも変わっていない（diff で説明できる） |

**止める理由**：既定 `tail` で golden が 1 件でも変わる。T2≠T3 か T4≠T5 で、原因が Forward など Backward の外にある（直さずに、どこで並びの順が効いたかを報告。Q5）。§4 の期待値と食い違う（規則の読み違いか、設計書の誤りか。どちらと判断したかを書いて止める）。

**止める理由ではないもの**：総納品が変わる、案 C と案 C_a2 の結果がほぼ同じ（醤油は市場の構成が毎週同じなので見込みどおり）。

## 7. 報告書と記録

- 報告書：`docs/development/WOM_M6_RowOrder_Stage1_OverflowPolicy_Report.md`、付録。冒頭に引き継ぎの欄（YAML、`next: owner`）。着手時の SHA、S1〜S5、§3 の表、`backward_planner.py` の diff の説明（何行・どこ・`tail` の経路が不変な理由）、大杉さんが diff で見るべき所、申し送り。
- commit メッセージの下書きを 1 つ（`commit_msg231.txt`）。git の操作は大杉さんが行う（保護対象のコアなので diff を見てから）。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-18 | 初版 |
