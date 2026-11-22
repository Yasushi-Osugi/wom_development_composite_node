---
handoff:
  case_id: COCKPIT-M6-006
  task_id: row-order-bias-stage3-default-proportional-week
  role_from: implement         # Code君
  role_to: owner               # 大杉さん（diff を見てから commit）
  start_sha: b5c0d3f
  request: requests/RequestLetter_M6_RowOrder_Stage3_DefaultProportional_to_CodeKun.md（v0.1）
  design: requests/WOM_M6_RowOrderBias_FixOptions_DesignMD_v0.3.md §5・§6 段 3
  acceptance: "S1〜S6（§1）"
  status: "既定を proportional_week に替えた。golden 3 件を意図して作り直した。commit はしていない"
  open_items:
    - "設計の下書き（docs/design/drafts/ の Roadmap・Upper Demand Plan・Demand Priority など 8 件）に、tail のときの C3a の値（注文残はすべてタイ）が残っている。下書きは当時の記録として直していない（§5.2）"
  stop_reasons: []
  next: owner
---

# 報告：行の順の偏りの直し方 — 段 3：押し戻し方の既定を `proportional_week` にした

- 依頼：`requests/RequestLetter_M6_RowOrder_Stage3_DefaultProportional_to_CodeKun.md`（v0.1）
- 着手時の SHA：`b5c0d3f`
- Windows 11、Python 3.12.3（`C:\Users\ohsug\anaconda3\python.exe`）
- 作業の出力：`output/roworder_stage3/`（git の対象外）
- 付録：`docs/development/WOM_M6_RowOrder_Stage3_DefaultProportional_appendix/`（golden の差 `golden/golden_diff3.md`・`.json`、モデルごとの市場別の数〔snapshot を除いた JSON〕、年齢の検査の要約、醤油 T1 の照合、化粧品の配分の案の照合、`grep_tail.txt`、スクリプト 6 本）

## 0. 一言で

- **既定は `proportional_week` で、書いてあるのは 1 か所だけ**：`wom/engine/overflow_policy.py` の `DEFAULT_POLICY`。
  - `tail`・`balance_cut_ratio` は、これまでどおり `planning_config.csv` の `overflow_policy` で選べます。
  - `tail` を明示すると、段 1 の醤油 T1 を再現しました。
- **golden**：新しい既定で回すと、16 件のうち変わったのは段 2 の見込みどおり 3 件（oil・soysauce-jpy-2027-alloc・smartphone）だけでした。
  - legacy の 3 件は変わりませんでした。
  - 3 件とも、総納品と期末の注文残の合計は同じで、市場への分かれ方だけが変わりました。
  - この 3 件の golden だけを作り直し、`test_golden.py` は全件通ります。
- **年齢の検査**（`tools/shelf_life_check.py`）が木の行の順に依らなくなりました。
  - 同じ所・同じ週・同じ SKU の出庫には、行き先のノード名 → Lot_ID の順に古い札を渡します。
  - 化粧品 C3a の `balance_cut_ratio` は、元の木と入れ替えた木で、要約・納品ごとの明細ともバイト単位で一致しました。
- **既定の変更で通らなくなったテスト**は 15 件です（§4）。
  - 6 件は期待値を直しました。
  - 8 件は、Lot_ID の形でない合成の lot を使う単体テストなので、`tail` を明示しました。
  - 1 件は golden と比べるテストで、golden を作り直して通りました。
- `--full`：1,369 passed・3 skipped・失敗 0（§6）。

## 1. 合格の条件

| # | 条件 | 結果 |
|---|---|---|
| S1 | 既定が 1 か所の定数で `proportional_week`。3 つとも選べ、知らない値で止まる。`TAIL` を既定として書いた所が残らない | **合格**。§2 |
| S2 | `tail` を明示すると段 1 の結果を再現（醤油 T1） | **合格**。§2.3 |
| S3 | 年齢の検査が行の順に依らない（C3a の入れ替えで一致） | **合格**。§3 |
| S4 | 変わるモデルの一覧と差を報告し、そのモデルだけ作り直した。`test_golden.py` が全件通る。legacy 3 件も報告 | **合格**。§5 |
| S5 | 期待値が変わったテストの一覧と扱い | **合格**。§4 |
| S6 | `--full` が通る。正式なサンプルの CSV・PPC・Value Chain・Forward は変わっていない | **合格**。1,369 passed・3 skipped（§6） |

止める理由（見込みの外の golden の変化、総納品・期末の注文残の合計の変化、golden 以外のテストの大量の失敗）には、どれも当たりませんでした。

## 2. 既定の変更

### 2.1 変えた所

| ファイル | 変更 |
|---|---|
| `wom/engine/overflow_policy.py` | `DEFAULT_POLICY = PROPORTIONAL_WEEK` を追加し、`__all__` に入れた。`resolve_overflow_policy` は空欄・None で `DEFAULT_POLICY` を返す。止めるときの文言も「空欄・キーなし＝proportional_week」にした。`OverflowTracker(policy=None)` は既定になる。docstring も直した |
| `wom/engine/backward_planner.py`（保護対象のコア。既定の参照だけ） | `BackwardPlanResult.overflow_policy` の既定を `DEFAULT_POLICY` にした。コメントも直した。押し戻しの処理は変えていない（`== _OVERFLOW_TAIL` の分岐はそのまま） |
| `wom/engine/warmup.py` | `read_overflow_policy` は、ファイルやキーが無いときに `DEFAULT_POLICY` を返す |
| `tools/run_headless_from_folder.py` | snapshot の `config.overflow_policy` は、**既定（`DEFAULT_POLICY`）と違う方式のときだけ**記録する。メッセージを出す条件も同じにした |
| `wom/gui/app.py` | メッセージを出す条件を「既定と違うとき」にした（`"tail"` との比較をやめた） |
| `tools/sweep_flags.py` | コメントだけ |

### 2.2 `TAIL` が残っている所（`grep`、付録 `grep_tail.txt`）

- `overflow_policy.py`：定数 `TAIL` の定義、`POLICIES`、`__all__`。もう 1 か所は `observe()` の `if self.policy != TAIL`（tail は Lot_ID が読めなくても数えるのをやめて続ける、という分岐）。
- `backward_planner.py`：import、`if self._overflow_policy == _OVERFLOW_TAIL:`（元の経路へ分ける）、コメント 2 か所。
- **既定として `TAIL` を書いている所は無い**。テスト `test_default_is_proportional_week_in_one_place` でも確かめた（`DEFAULT_POLICY =` が 1 行だけで、ほかのファイルに `return TAIL`・`== "tail"`・`!= "tail"` が無い）。

### 2.3 `tail` を明示したときの再現（S2）

- 段 1 の醤油 T1 の写し（C02、21 シフト）に `overflow_policy,tail` を書いて回した。市場別の ①・当週・早出し・遅配・注文残、計画の前に落ちた lot（12,326）、工場 × 市場の延べの押し戻し・母数が、段 1 の `result.json` と全部一致した。
- 同じ写しをキーなし（新しい既定）で回すと、段 1 の T2（`proportional_week`）と全部一致した。
- 付録 `soy_t1/`。

## 3. 年齢の検査（`tools/shelf_life_check.py`）

### 3.1 規則

- `compute_fifo()` の中で、同じ所・同じ週の出庫（同じ SKU）を `_exit_order`（行き先 `to` の文字の順 → Lot_ID の順）に並べてから、古い札を渡すようにした。市場の販売の行き先は `CONSUMER:<leaf>` になる。
- 前は、出荷の記録の並び（木の行の順に従う）のまま渡していた。
- あわせて、納品ごとの明細の行を（製品・チャネル・納品週・Lot_ID）の順に並べた。前は処理の順で、木の順によって行の並びが変わっていた。中身は変えていない。

### 3.2 確かめ

| 案（段 2 の写し） | 前の規則：最小・最大・52 週超 | 新しい規則 |
|---|---|---|
| C3a `proportional_week`（C02） | 4・28・0 | 4・27・0 |
| C3a `balance_cut_ratio` 元の木（C03） | 4・28・0 | 4・27・0 |
| C3a `balance_cut_ratio` 入れ替えた木（C04） | 4・27・0 | 4・27・0 |
| 化粧品の正式なサンプル（golden） | 4・6・0 | 4・6・0（分布も同じ） |

- C03 と C04 は、新しい規則で `shelf_life_summary.csv`・`shelf_life_deliveries.csv` がともにバイト単位で一致した。
- 化粧品の正式なサンプルの年齢は変わらない。最大は 6 週で、`tail` を明示しても同じ。
  - 依頼書 §2 の「最大 21 週」は B3（作り置きの案）の値で、正式なサンプルの値ではない。
- 既存の年齢のテスト（`test_warmup_soft_blank_attrs_fifo.py`・`test_shelf_life_demand_file.py`・`test_compare_scenarios.py`・`test_cockpit_compare_view_model.py`）は、期待値を変えずに通った。
- 新しいテスト `tests/test_shelf_life_row_order.py`：小さな入力で、出荷の記録の並びと木の順を入れ替えても、納品ごとの年齢が同じ。

## 4. 期待値が変わったテストと扱い（S5）

golden を除いて 1 回通したところ（`output/roworder_stage3/pytest_nogolden.txt`：1,332 passed・16 failed・3 skipped）、失敗は次の 16 件だった。

| テスト | 原因 | 扱い |
|---|---|---|
| `test_overflow_policy.py` の 3 件（空欄＝tail、`read_overflow_policy`、headless の config） | 段 1 の既定（tail）を確かめるテスト | **期待値を直した**。空欄・キーなし・ファイルなし・config なしで `proportional_week`。headless は、キーなしと既定の明示では config が golden と同じ、`tail`・`balance_cut_ratio` を書いたときは記録する。単体テスト `test_default_is_proportional_week_in_one_place` を足した |
| `test_test_areas.py::test_every_test_file_has_an_area` | 新しいテストのファイルが、`conftest.py` に足す前に見つかった | `conftest.py` に 1 行足した（期待値の変化ではない） |
| `test_backward_holiday_carryback.py` の 3 件 | 合成の lot（`A0`・`A1` など、Lot_ID の形でない）を使う。新しい方式は Lot_ID が読めないと止まる（段 1 の設計） | **`tail` を明示した**。休業の繰り越し・能力のテストで、押し戻しの分け方のテストではないため |
| `test_demand_envelope_soft.py` の 3 件 | 同上 | **`tail` を明示した** |
| `test_holiday_explicit_closure.py` の t4・t12 | 同上（`L1` など） | **`tail` を明示した**（`config={"mom_constrained": True}` の 2 か所） |
| `test_cockpit_case_runner.py::test_cosmetics_base_late_case_end_to_end` | 化粧品の基準・後期の案（C3a と同じ能力）の P0 と、期末の注文残の鍵 | **期待値を直した**。P0 606,871,080 → 600,719,196（段 2 の C02 と同じ）。注文残は、タイの 2 鍵から 8 市場（クリーム 47・18・19・4、美容液 50・27・22・5）へ。クリームの納品 1,680 は同じ |
| `test_stage_d_part0.py::test_alloc_tariff_on_border_edges` | alloc の関税の合計 | **期待値を直した**。15,670,707.4425 → 15,921,024.9825（作り直した golden の `tariff_base` と同じ） |
| `test_valuechain_integration.py::test_alloc_conservation_and_external_sales` | alloc の V3 の外部売上（Rest_JP ＋ Rest_US_West） | **期待値を直した**。231,673,000 → 180,971,560（日本・米国西の当週の納品が減ったため。§5.2）。同じファイルの記録の件数（527,037、各種 75,291）は変わらない |
| `test_ppc_unused_rule_rows.py::test_warning_does_not_touch_trust_events` | smartphone の PPC を golden と比べる | golden を作り直して通った（テストは変えていない） |

- 直したテストは、コメントに `tail` のときの値を残した。
- 「`tail` を明示」した 8 件はどれも、Lot_ID の形でない合成の lot を使う単体テスト。

## 5. golden

### 5.1 19 件を新しい既定で回した結果

- 写し（`overflow_policy` の行なし）で、golden と同じプラグインの組・`lot_flow_mode` で回し、golden と全部のキー（config を含む）を比べた。
- legacy の 3 件は `lot_flow_mode=legacy` で回した。

| | 一致 | 違う |
|---|---|---|
| golden 16 件 | 13 件（Cookie・apparel 2・bom-test・cosmetics・ev 3・rice・smartx・soysauce eu・jpy・us） | **3 件**：oil-global-2027・smartphone-global-2026-2029・soysauce-jpy-2027-alloc（どれも `ppc`・`psi`） |
| legacy 3 件（Cookie・ev-thailand・soysauce-jpy） | 3 件 | 0 件 |

- 違った 3 件は、段 2 の `proportional_week` の snapshot とも一致した。
- 一致した 13 件の config には `overflow_policy` が付かない。既定のときは何も足さないので、golden の config と同じ。

### 5.2 変わった 3 件の差（`tail` を明示した写し → 新しい既定）

`tail` を明示した写しは、3 件とも今までの golden と一致した（config を除く全部のキー）。

| モデル | 総納品 | 期末の注文残 | 計画の前に落ちた lot（うち工場の能力） | 変わったノード（series_md5 など） |
|---|---|---|---|---|
| oil-global-2027 | 191,029 → 191,029 | 29 → 29 | 29 → 29（4 → 4） | 3：Gasoline_Local_RedSea の市場 3 つ |
| smartphone-global-2026-2029 | 414,090 → 414,090 | 56,834 → 56,834 | 56,834 → 56,834（44,134 → 44,134） | 12：Phone16 の SP・DC_EMEA・Retail_EMEA・DC_APAC・Retail_APAC、Phone15 の SP と DC・市場 3 組 |
| soysauce-jpy-2027-alloc | 75,291 → 75,291 | 25,210 → 25,210 | 24,524 → 24,524（20,408 → 20,408） | 12：SP・FG_WH_Noda・DC 4・市場 6 |

市場別（当週の納品／期末の注文残。遅配は全部 0）：

| モデル | 市場 | 需要 | 当週 | 注文残 |
|---|---|---|---|---|
| oil | Retail_Local_R_KANTO | 246 | 246 → 232 | 0 → 14 |
| oil | Retail_Local_R_KANSAI | 124 | 115 → 116 | 9 → 8 |
| oil | Retail_Local_R_CHUBU | 124 | 104 → 117 | 20 → 7 |
| smartphone | Phone16 Retail_EMEA | 70,736 | 70,736 → 55,626 | 0 → 15,110 |
| smartphone | Phone16 Retail_APAC | 80,184 | 48,397 → 63,507 | 31,787 → 16,677 |
| smartphone | Phone15 Retail_AMER_i15 | 34,580 | 34,580 → 24,644 | 0 → 9,936 |
| smartphone | Phone15 Retail_EMEA_i15 | 24,204 | 18,926 → 17,041 | 5,278 → 7,163 |
| smartphone | Phone15 Retail_APAC_i15 | 27,664 | 7,895 → 19,716 | 19,769 → 7,948 |
| alloc | Rest_US_West | 17,588 | 17,063 → 12,981 | 525 → 4,607 |
| alloc | Rest_US_East | 17,588 | 17,063 → 12,842 | 525 → 4,746 |
| alloc | Rest_JP | 30,150 | 29,250 → 23,784 | 900 → 6,366 |
| alloc | Rest_FR | 15,075 | 6,615 → 11,007 | 8,460 → 4,068 |
| alloc | Rest_BE | 10,050 | 2,650 → 7,339 | 7,400 → 2,711 |
| alloc | Rest_NL | 10,050 | 2,650 → 7,338 | 7,400 → 2,712 |

PPC（`tail` → 既定）：

| モデル | 売上 | 粗利 | 粗利率 | その他 |
|---|---|---|---|---|
| oil | 1,571,097,940,180 → 1,571,457,940,180 | 552,339,674,893 → 552,699,674,893 | 0.351563 → 0.351711 | total_lots 1,399 → 1,408、trust_event_count 733 → 742 |
| smartphone | 64,101,413,473,420 → 63,634,388,846,970 | 26,406,289,089,502.25 → 26,215,172,438,470.68 | 0.411946 → 0.411965 | 関税 4,720,497,327,977.75 → 4,462,834,176,730.33、total_lots 1,127 → 1,170 |
| alloc | 427,957,532 → 451,673,778 | 111,639,241.96 → 125,312,891.87 | 0.260865 → 0.277441 | 関税 15,670,707.44 → 15,921,024.98、total_lots 464 → 607 |

- 総納品の lot 数は同じでも、PPC の金額は変わる。どの市場（価格・関税）に納品するかが変わるため。
- oil の工場は `Refinery_Local_R` で、変わったのは市場のノードだけ。工場・DC の行は変わらない。

### 5.3 作り直し

- CLAUDE.md の手順で、`--plugins` を明示して作った。3 件とも `recommended_plugins`＝`HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin`。
- 作り直したファイルは `tests/golden/oil-global-2027.json`・`soysauce-jpy-2027-alloc.json`・`smartphone-global-2026-2029.json` の 3 つで、ほかの golden には触れていない。
- 作り直した 3 件は、§5.1 で回した結果と一致した（違うのは `case` の欄だけで、§5.1 は写しのフォルダ名だから）。
- diff の要約：3 ファイル、112 行の入れ替え。欄は `ppc`（金額・件数）と `psi`（変わったノードの P・S・I・CO の合計と series_md5）だけ。`period`・`products`・`config`・`forward`・`backward` は変わらない。
- `test_golden.py`（16 件＋legacy 3 件）と `test_ppc_unused_rule_rows.py` は、作り直した後に単独で回して 22 件通った。

## 6. `quick_check --full`

- 結果：`[quick_check] tier=full | passed=1369 failed=0 skipped=3 error=0 | 1247 s | OK`（`output/roworder_stage3/quick_full.txt`）。golden を作り直し、テストを直した後に回した。
- 前回の記録（1,346 件）からの増加分 23 件：段 1・段 2 で足したテストと、今回の 2 件（`test_default_is_proportional_week_in_one_place`、`test_shelf_life_row_order.py`）。
- 正式なサンプルは変わっていない：`git status` で `data/` に変更なし。
- PPC・Value Chain・Forward のコードは変えていない：変えたコードは §2.1 の表と `tools/shelf_life_check.py` だけ。

## 7. 文書の直し

### 7.1 直したもの

| 文書 | 直し |
|---|---|
| `docs/WOM_Start_Here.md` | §3 に R25 を足した（既定は `proportional_week`、`tail`・`balance_cut_ratio` は `overflow_policy` で選ぶ、年齢の検査の規則）。§4.3 の落とし穴 13・14 に「2026-11 から既定は比例。`tail` を選んだときだけ行の順で決まる」と足した |
| `CLAUDE.md` | 「能力の値の意味」の節に規則を 1 行足した。末尾に段 3 の短い節を足した |
| `docs/scenarios/cosmetics.md` | C3a の期待値：新しい既定の値（注文残 192 が 8 市場に分かれ、売上 1,100,849,400、試算の粗利 601,449,564。段 2 の C02）を書き、`tail` の値には「`overflow_policy=tail` のとき」と書いた。P1・P2-a1・P2-a2 の合計と採用した配分の案は、新しい既定で回し直して同じことを確かめたので、その一文を足した（§7.3） |
| `docs/semantics/supply_allocation.md` | C3a の事例の行に「当時の既定（`tail`）での結果。今の既定では 8 市場に分かれる」と足した |
| `docs/design/WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.2.md` | C3a の行に同じ注記 |

### 7.2 直していないもの

- 報告書・依頼書：当時の記録なので直していない。
- 設計書 v0.3（Claude君が直す）。
- `docs/design/drafts/` の下書き 8 件に、C3a（注文残はすべてタイ）の値が残っている。下書きは作った時点の記録として直していない。正式な設計書（v0.2）だけ直した。直すかどうかは大杉さんの判断。

### 7.3 化粧品の配分の案を新しい既定で回し直した結果

C3a の写しで `tools/run_quantity_allocation` を回した（付録 `cos_alloc/`）。

| 案 | ① | 供給の対象 | 対象の外 | 当週の納品 | 注文残 |
|---|---|---|---|---|---|
| P1 | 4,056 | 3,864 | 192 | 3,860 | 4 |
| P2-a1 | 4,056 | 3,864 | 192 | 3,860 | 4 |
| P2-a2 | 4,056 | 3,864 | 192 | 3,856 | 8 |
| 採用した案（TH70・最低供給量） | 4,056 | 3,864 | 192 | 3,864 | 0 |

- 合計は、`cosmetics.md` に書いてある値と同じ。
- 採用した案は、配分済みの需要で `tail` と新しい既定の計画を比べ、snapshot（period・products・forward・backward・ppc・psi）が一致した。比較の値 607,776,840 はそのまま使える。

## 8. 大杉さんが diff で見る所

1. **既定の定数**：`wom/engine/overflow_policy.py` の `DEFAULT_POLICY = PROPORTIONAL_WEEK` と、それを使う所（`resolve_overflow_policy`・`read_overflow_policy`・`BackwardPlanResult`・`OverflowTracker`）。`backward_planner.py` の差分は、import・既定の値・コメントだけ。
2. **snapshot の記録の条件**：`tools/run_headless_from_folder.py` の `{} if overflow_policy == DEFAULT_OVERFLOW_POLICY else {...}`。
3. **作り直した golden の 3 件**：`tests/golden/oil-global-2027.json`・`soysauce-jpy-2027-alloc.json`・`smartphone-global-2026-2029.json`（§5.2 の差）。
4. **年齢の検査**：`tools/shelf_life_check.py` の `_exit_order` と、明細の並べ替え。
5. **テストの期待値**：§4 の表。

## 9. commit メッセージの下書き

- `commit_msg235.txt`：コード・テスト・golden
- `commit_msg236.txt`：報告書・文書・付録

git の操作は大杉さんが行う。golden と既定の変更を含むので、diff を見てから commit する。
