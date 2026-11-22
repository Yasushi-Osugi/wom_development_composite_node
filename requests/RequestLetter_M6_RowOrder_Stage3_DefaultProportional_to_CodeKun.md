---
handoff:
  case_id: COCKPIT-M6-006
  task_id: row-order-bias-stage3-default-proportional-week
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "この依頼書の commit 以降の HEAD（着手時の SHA を記録）"
  knowledge_used:
    - id: 行の順の偏りの直し方の設計
      version: "v0.3（Q1〜Q7 採用）"
      applicability: "requests/WOM_M6_RowOrderBias_FixOptions_DesignMD_v0.3.md §5・§6 段 3"
    - id: 段 2 の試行
      version: "WOM_M6_RowOrder_Stage2_PolicyTrial_Report.md"
      applicability: "golden が変わる見込みの 3 モデル（oil・soysauce-jpy-2027-alloc・smartphone）、年齢の検査の行の順"
  acceptance:
    ref: "この依頼書 §7"
  status: "試行可能"
  open_items: []
  stop_reasons: []
  next: implement
---

# Request Letter：行の順の偏りの直し方 — 段 3：押し戻し方の既定を `proportional_week` に替え、年齢の検査を行の順に依らないものにし、golden を作り直す

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉（WOM Project Owner）／起草：Claude君（2026-11-22）／版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`
- **計画の動きを変える変更**（Backward の既定）。保護対象のコアの手続き（3 層のテスト・golden の意図した作り直し・大杉さんの diff の確認）に従う。この依頼書が認可
- 範囲：`wom/engine/overflow_policy.py`・`wom/engine/warmup.py`（既定の値）、必要なら `wom/engine/backward_planner.py`（既定の参照だけ）、`tools/run_headless_from_folder.py`（snapshot の記録の条件）、`tools/shelf_life_check.py`、テスト、golden（意図した作り直し）、文書（§5）、報告書。**正式なサンプルの CSV・PPC・Value Chain・Forward は変えない**
- 出力：`output/roworder_stage3/`（git の対象外）

---

## 一言で

**押し戻し方の既定を `tail` から `proportional_week` に替えてください。** `tail`・`balance_cut_ratio` は `planning_config.csv` の `overflow_policy` で選べるまま残します。あわせて、製品の年齢の検査（`tools/shelf_life_check.py`）が兄弟の市場に古い在庫を木の行の順で渡している所を、行の順に依らない規則にしてください。golden は、変わるモデルを報告してから意図して作り直します。

## 0. 大杉さんの判断（2026-11-22、4 件とも推奨どおり採用）

| # | 一言で | 決定 |
|---|---|---|
| 1 | 既定は「その週の数に比例」 | `proportional_week` を既定に。`tail`・`balance_cut_ratio` は設定で選べるよう残す |
| 2 | 製品の年齢の検査も行の順に依らない | `shelf_life_check.py` の兄弟の市場への割り当ての順を、宣言した規則にする |
| 3 | golden は変わるモデルだけを意図して作り直す | 作り直す前に legacy の 3 件も新しい既定で回し、変わるかを確かめる。一覧と差を報告してから作り直す |
| 4 | 醤油の配分の比較を回し直すのは後で | 今回は回し直さない |

## 1. 既定の変更

1. **既定の値を 1 か所に**：`wom/engine/overflow_policy.py` に `DEFAULT_POLICY = PROPORTIONAL_WEEK` を置き、`resolve_overflow_policy` の空欄・None、`read_overflow_policy` のファイル・キーが無いとき、`OverflowTracker`・`BackwardPlanner` の config に無いとき、**すべてこの定数を使う**。`TAIL` を既定として書いている所が残らないこと（`grep` の結果を報告に）。
2. `BackwardPlanner(sc_tree)`（config なし）で作る既存のテスト・道具も、新しい既定になる。そのせいで期待値が変わるテストは、**一覧にして、意図した変化として期待値を直す**か、そのテストの目的が今の動きの確認なら `config={"overflow_policy": "tail"}` を明示する。どちらにしたかをテストごとに報告に書く。
3. headless の snapshot：段 1 では「`tail` のときは config に何も足さない」だった。これを「**既定（`DEFAULT_POLICY`）のときは何も足さず、既定と違う方式のときだけ `config.overflow_policy` を記録する**」に替える（golden の config の形を変えないため）。
4. 文言：画面・headless のメッセージで「既定＝tail」と書いている所を直す。

## 2. 年齢の検査（`tools/shelf_life_check.py`）

- 今は、同じ物の在る所（DC など）から同じ週に複数の市場へ出る納品に、古い札（製造週）を木の行の順で渡している。段 2 で、計画の結果が同じなのに年齢の最大が 28 週と 27 週に分かれた。
- **兄弟の納品への割り当ての順を、行の順に依らない規則にする**：同じ所・同じ週・同じ SKU の出庫は、（行き先のノード名の文字の順 → Lot_ID の順）で並べてから、古い札から渡す。どの規則にしたかを報告に書く。
- 確かめ：段 2 の化粧品の C3a の `balance_cut_ratio` の元の木と入れ替えた木で、年齢の結果（最小・最大・分布・52 週超）が一致する。
- 既存の年齢のテストの期待値が変わる場合は、一覧にして理由を書く。化粧品の正式なサンプル（golden）の年齢（段 1 以前に記録した最大 21 週など）が変わるかも書く。

## 3. golden の作り直し（意図した変化）

1. **先に回して、変わるモデルを報告**：新しい既定で、golden 16 件と legacy 3 件を回し、golden と比べる。段 2 の見込みは 16 件のうち 3 件（oil・soysauce-jpy-2027-alloc・smartphone）。legacy は段 2 で回していない。
2. 変わるモデルごとに：変わった欄（ppc・psi・forward・backward）、市場別の当週・注文残の差、PPC の売上・粗利の差、`series_md5` が変わったノード。見込みの 3 件以外が変わったら、理由を書く。
3. 作り直す（CLAUDE.md の手順。**`--plugins` を明示**）。変わらないモデルの golden は触らない。作り直した後に `tests/test_golden.py` が全件通る。
4. 作り直した golden の diff の要約（何件・どの欄）を報告に。

## 4. テスト

| 層 | 中身 |
|---|---|
| 単体 | 既定の定数が 1 か所であること。空欄・キー無し・ファイル無し・config 無しで `proportional_week` になる。`tail` を明示すると段 1 までと同じ結果（醤油 T1 の数） |
| 単体 | 年齢の検査：兄弟の納品の順を入れ替えた小さな入力で、結果が同じ |
| 結合 | `planning_config.csv` → 読み込み → `BackwardPlanner` の経路。headless の snapshot の config：既定のとき何も足さない、`tail`・`balance_cut_ratio` を書いたとき記録する |
| E2E | 作り直した golden で `tests/test_golden.py` が全件（16 件 ＋ legacy 3 件）通る |

最後は **`python -m tools.quick_check --full`**（約 36 分。出力を `output/roworder_stage3/quick_full.txt` に書き、末尾を読む）。

## 5. 文書

- `docs/WOM_Start_Here.md`：§3 に規則を 1 行足す（例 R25：能力を超えた週の押し戻しの既定は `proportional_week`。`tail`・`balance_cut_ratio` は `planning_config.csv` の `overflow_policy` で選べる。根拠は段 1〜3 の報告書）。§4.3 の落とし穴 13・14 に「2026-11 から既定は比例。`tail` を選んだときだけ行の順で決まる」と足す。
- `CLAUDE.md`：上の規則の 1 行と、段 3 の節（短く）。
- `docs/scenarios/cosmetics.md` の C3a の期待値（注文残 192 はすべてタイの代理店、など）は**今の動き（`tail`）での値**になる。新しい既定での値を足し、`tail` の値には「`overflow_policy=tail` のとき」と書く。ほかに、今の動きを前提にした期待値を書いた文書があれば、一覧にして同じように直す（報告書・依頼書は当時の記録なので直さない）。
- 設計書 v0.3（`requests/WOM_M6_RowOrderBias_FixOptions_DesignMD_v0.3.md`）は Claude君が直すので触らない。

## 6. 重い処理の注意

- 段ごとに結果をファイルに書いてから次へ（既定の変更とテスト → golden 19 件を回して比べる〔1 件ずつ書く〕→ 作り直し → 年齢の検査 → `--full`）。
- smartphone・smartx は golden の比べ方でも最後に。

## 7. 合格の条件

| # | 条件 |
|---|---|
| S1 | 既定が 1 か所の定数で `proportional_week`。`tail`・`balance_cut_ratio` は選べ、知らない値で止まる。`TAIL` を既定として書いた所が残らない |
| S2 | `tail` を明示すると段 1 までの結果を再現（醤油 T1） |
| S3 | 年齢の検査が行の順に依らない（C3a の入れ替えで一致） |
| S4 | golden：変わるモデルの一覧と差を報告し、そのモデルだけを作り直した。`test_golden.py` が全件通る。legacy 3 件の結果も報告 |
| S5 | 既定の変更で期待値が変わったテストの一覧と、それぞれの扱い（期待値を直した／`tail` を明示した） |
| S6 | `--full` が通る。正式なサンプルの CSV・PPC・Value Chain・Forward は変わっていない |

**止める理由**：見込みの 3 件以外の golden が変わり、理由が説明できない。総納品・期末の注文残の合計がモデルで変わる（段 2 では 26 回すべて同じだった）。golden を作り直さないと通らないテストが、golden 以外に多数出る（一覧を出して止める）。

## 8. 報告書と記録

- 報告書：`docs/development/WOM_M6_RowOrder_Stage3_DefaultProportional_Report.md`、付録。冒頭に引き継ぎの欄（YAML、`next: owner`）。着手時の SHA、S1〜S6、golden の差の表、テストの扱いの一覧、文書の直しの一覧、**大杉さんが diff で見る所**（既定の定数・snapshot の記録の条件・作り直した golden の一覧）。
- commit メッセージの下書き 2 つ（コード・テスト・golden／報告書・文書）。git の操作は大杉さんが行う（golden と既定の変更を含むので diff を見てから）。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-22 | 初版。§0 の 4 件は大杉さんが採用 |
