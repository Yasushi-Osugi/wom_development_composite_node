# 報告書：PPC・Value Chain の黙った見本への切り替えを止める（D8）

- 依頼書：`requests/RequestLetter_PPC_NoSilentFallback_to_CodeKun.md` v0.2（`2c3db5c`）
- 実施：Code君（Claude Code、Windows）、2026-10-26
- 経緯：§A を終えたところで一度止め、smartx の「規則の最初の週より前の週」の扱いを仰いだ（§3）。大杉さんの判断（2026-10-26）は **(a)**。その後 §B〜§D を実装した（§4 以降）。

---

## 1. 着手時の SHA

- **着手時**：`2c3db5c`（依頼書 v0.2 の commit）。**完了時**：未 commit（下書き `commit_msg139.txt`）。保護対象のコアは変えていない。
- §A の調査はリポジトリの外の道具（`survey_ppc_fallback.py`、各 golden のモデルを一時フォルダに写し、golden と同じプラグイン・方式で headless を回し、PPC の入口を包んで記録）で行った。`data/sample/` は書き換わっていない。

## 2. §A の結果

### A1：S1〜S5 はコードのとおり

| # | 確かめた所 | 結果 |
|---|---|---|
| S1 | `tools/run_headless_from_folder.py` `_run_ppc()`、`wom/gui/app.py` 5971〜6015 行付近 | そのとおり。どちらも「モデルに `ppc_market_price.csv` があればモデル、無ければ `data/ppc`」を別々に書き、同時に `use_node_name` も切り替える（headless：`use_node_name = True` をモデルの時だけ、GUI：`_ppc_data_dir != "data/ppc"`） |
| S2 | `wom/ppc/ppc_rules.py` `PPCRuleSet.load(data_dir, fallback_dir="data/ppc")` | そのとおり。ファイルごとに `data/ppc` へ切り替え、標準出力に 1 行 |
| S3 | `wom/ppc/ppc_runner.py` Step 3 | そのとおり。製品は `ppc_supplier_cost.csv` の `product_id`、市場は `ppc_market_price.csv` の `market_node` で**別々に**照合して落とす。`get_market_price()` は規則が無いと `(0.0, "JPY")`、`get_supplier_cost()` は `(0.0, "CNY")` |
| S4 | `ppc_runner.py` Step 4 | そのとおり。`wom.ppc.__main__.generate_sample_sales()` で見本の販売を作る |
| S5 | `wom/valuechain/fx.py` `FxTable.load(model_dir, fallback_dir)`、`wom/valuechain/run.py` 111・142 行 | そのとおり。記録は `data/ppc (fallback)` |

補足：PPC の為替（`wom/ppc/ppc_fx.py` `FXConverter.get_rate()`）は、ある週の為替が無ければ前の週の値を使い（`fx_fallback_prior_week` として記録）、前の週にも無ければ `ValueError` で止まる。為替は 0 で埋めない。

### A2：golden のモデルごとの表

golden の 15 件・legacy 3 件と、参考に `rice-japan-2027-2028_BK260613_1515`。「価格・原価の規則に無い組合せ」は、`get_market_price()`・`get_supplier_cost()` の呼び出しを包み、規則の行が 1 つも無かった (市場, 製品)・(仕入れ先, 製品) を数えた（＝今 0 円で計算されているもの）。

| モデル | 規則のフォルダ | `data/ppc` から読んだファイル | `use_node_name` | S3 で落ちた記録 | 価格・原価が規則に無い組合せ（0 円） | S4 | Value Chain の為替 | 販売記録（件） |
|---|---|---|---|---|---|---|---|---|
| Cookie-jp-2026 | モデル | `ppc_fx_rate.csv` | True | 0 | 0 | 無し | `data/ppc`（fallback） | 624 |
| apparel-global-2028-2029 | モデル | 無し | True | 0 | 0 | 無し | モデル | 394 |
| apparel-us-2026 | モデル | 無し | True | 0 | 0 | 無し | モデル | 444 |
| bom-test-2026 | モデル | 無し | True | 0 | 0 | 無し | モデル | 20 |
| ev-europe-2026 | モデル | 無し | True | 0 | 0 | 無し | モデル | 526 |
| ev-thailand-2026 | モデル | 無し | True | 0 | 0 | 無し | モデル | 624 |
| ev-thailand-2026_update | モデル | 無し | True | 0 | 0 | 無し | モデル | 624 |
| oil-global-2027 | モデル | 無し | True | 0 | 0 | 無し | モデル | 1,399 |
| rice-japan-2027-2028 | **`data/ppc`（S1）** | 全部 | **False** | 0 | 0 | 無し | `data/ppc`（fallback） | 1,163 |
| smartphone-global-2026-2029 | モデル | `ppc_fx_rate.csv` | True | 0 | 0 | 無し | `data/ppc`（fallback） | 1,127 |
| **smartx-2027-2029** | モデル | 無し | True | 0 | 0 | 無し | モデル | 1,697 |
| soysauce-eu-2027 | モデル | 無し | True | 0 | 0 | 無し | モデル | 624 |
| soysauce-jpy-2027-alloc | モデル | 無し | True | 0 | 0 | 無し | モデル | 464 |
| soysauce-jpy-2027 | モデル | 無し | True | 0 | 0 | 無し | モデル | 624 |
| soysauce-us-2027 | モデル | 無し | True | 0 | 0 | 無し | モデル | 312 |
| Cookie-jp-2026［legacy］ | モデル | `ppc_fx_rate.csv` | True | 0 | 0 | 無し | `data/ppc`（fallback） | 624 |
| ev-thailand-2026［legacy］ | モデル | 無し | True | 0 | 0 | 無し | モデル | 624 |
| soysauce-jpy-2027［legacy］ | モデル | 無し | True | 0 | 0 | 無し | モデル | 624 |
| rice-…_BK260613_1515（参考、golden 外） | `data/ppc`（S1） | 全部 | False | 0 | 0 | 無し | `data/ppc`（fallback） | 472 |

K5 の見込み（rice は規則を全部 `data/ppc` から、Cookie・smartphone は `ppc_fx_rate.csv` だけ）とモデル単位で一致した。

### A3：golden のモデルで S3・S4・0 円は起きていない

**S3（落ちた記録）・S4（見本の販売）・価格／原価が規則に無い組合せ（0 円）は、golden の 18 件とも 0 だった。** 今の golden の金額は、評価できなかった部分を黙って落とした値でも、0 円で埋めた値でもない。

### A3 で見つけた別の事実（止める理由）：smartx は「規則の最初の週より前」の価格・原価を使っている

`smartx-2027-2029` の規則は、価格（`ppc_market_price.csv` の `SmartX` × `Retail_AMER_g1`／`Retail_EMEA_g1`／`Retail_APAC_g1`）と仕入れの原価（`ppc_supplier_cost.csv` の `WaferFab_TW_g1` × `SmartX`）が **2027-W01 から**しかない。一方、`SmartX` の需要（`demand_forecast.csv`）は **2026-W01 から**ある（warmup の助走ではなく、需要が 0 でない週）。

- `get_market_price()`・`get_supplier_cost()` は、要る週より前の規則の行が無いとき、**最初の行の値**を返す（`ppc_rules.py` 164〜167・180〜183 行）。0 円ではないが、**その週の値として規則に書かれていない値**を使っている。
- 測った呼び出しの数：価格は 3 チャネルとも 106 回、仕入れの原価は 159 回。
- 依頼書 B.2 の `評価済み` の定義「製品 × 市場 × **適用の週の組合せごとに**、要る価格・仕入れの原価・為替が規則から取れた」を字面どおりに当てると、smartx は `一部未評価` になり、**golden の金額と snapshot の項目が変わる**（§E の止める理由）。

ほかの 17 件では、この「最初の行より前」の呼び出しは 0 だった。

### A4：PPC の結果を読む所

| 所 | 読むもの |
|---|---|
| `tools/run_headless_from_folder.py` `_run_ppc()`・CLI の表示（630 行付近） | `ppc_kpi_summary.json`、`snap["ppc"]["gross_margin_pct"]`・`["trust_event_count"]` |
| `wom/planning_state/__init__.py` `attach_realized()` | `snapshot["ppc"]` の `gross_profit_base`・`revenue_base`・`cost_base`・`total_lots` |
| `tools/run_planning_loop.py` 257 行 | `realized.ppc` |
| `wom/valuechain/run.py` 216・244 行 | `snap.get("ppc")`、PPC の出力の `ppc_kpi_summary.json`（`compare_with_ppc`） |
| `wom/gui/app.py` 1330・1459・1770 行、6008 行 | 通貨記号・台帳の P&L の上書き・PPC タブ（`ppc_kpi_summary.json`）、`run_ppc_from_psi()` の返り値 |
| `wom/ppc/ppc_cockpit.py` 275 行、`wom/ppc/ppc_cockpit_app.py` 826 行 | `ppc_kpi_summary.json` |
| `tools/analyze_smartx_bottleneck.py` 226 行、`tools/s2_eval_compare.py` 141 行 | `snap["ppc"]["revenue_base"]` 等を直接（キーが無いと KeyError） |
| `tools/generation_line_compare.py`・`lot_identity_checks.py`・`lovem_observe.py`・`smartx_capacity_compare.py`・`probe_smartx_bottleneck.py`・`warmup_trial.py`・`plugin_defaults_check.py`・`run_quantity_allocation.py` | `snap["ppc"]` を丸ごと記録 |

`tools/gui_*_check.py` の `st["ppc"]` は GUI の確認の道具の状態の変数で、PPC の結果ではない。

## 3. 判断を仰いだこと（実装の前に）と、その決定

smartx の「規則の最初の週より前の週」の価格・原価を、`valuation_status` の判定でどう扱うか。

| 案 | 中身 | golden |
|---|---|---|
| **(a) 推奨** | 「その製品 × 市場（仕入れ先）の規則がある」なら評価済みとし、最初の行より前の週に最初の行の値を使ったことは**記録だけ**する（`ppc_kpi_summary.json` に件数、`ppc_warnings.csv` に `price_before_first_rule_week`）。0 円の未設定（規則の行が 1 つも無い）だけを未評価の対象にする | 変わらない（smartx の金額・既存の snapshot の項目は同じ。記録の項目が JSON に増えるだけ） |
| (b) | 字面どおり、適用の週に規則の行が無ければ未評価として除く | smartx が `一部未評価` になり、金額と snapshot が変わる（golden の再生成が要る） |
| (c) | (a) に加えて、smartx の規則に 2026-W01 の行（2027-W01 と同じ値）を足す（Data） | 金額は変わらない見込み（同じ値が同じ週に使われる）。規則が需要の期間を覆うようになる |

(a) を推す理由：Value Chain は同じ場面で既に「最初の行より前の週は最初の行の価格を使い、`price_log` に記録する」と決めている（`wom/valuechain/masters.py` の冒頭の説明、為替の判断 d と同じ扱い）。PPC も同じ規則にそろえれば、二つの経路で扱いが分かれない。依頼書の原則「0 や見本の値で埋めない」には反しない（使うのはそのモデルの規則の値）。

**大杉さんの判断（2026-10-26）：(a)。** 規則の行があれば評価済みとし、最初の行より前の週に最初の行の値を使ったことは件数を記録する（`ppc_kpi_summary.json` の `price_before_first_rule_week`、`ppc_warnings.csv` の `price_before_first_rule_week`）。smartx の golden は変わらない（§6）。

## 4. 変えたファイル

保護対象のコア（`AGENTS.md` §10 の 6 ファイル）は変えていない。

| ファイル | 内容 |
|---|---|
| `wom/ppc/ppc_rules.py` | B.1：`PPC_RULE_FILES`、`read_shared_rules_dir()`・`resolve_shared_dir()`・`PPCRuleSources`・`resolve_ppc_rules()`・`channel_uses_node_name()`・`base_currency_of()`。`PPCRuleSet.load_from_sources()`。`PPCRuleSet.load()` の既定の切り替え先（`fallback_dir="data/ppc"`）を無くした（明示したときだけ）。`get_market_price()`・`get_supplier_cost()` に `lookup_log`（規則の行が無い＝今まで 0 円／最初の行より前の週）と `has_market_price()` |
| `wom/ppc/ppc_runner.py` | B.2：`valuation_status`（評価済み／一部未評価／未評価）、製品 × 市場の組合せでの照合、エンジンの後に原価・価格の規則が無かった製品を除いてもう一度評価、見本の販売データの生成を外した（K4）、実行の最初に前回の出力を消す（`clear_ppc_outputs`）、未評価は状態だけの `ppc_kpi_summary.json`、`ppc_run_info.json` に状態・理由・規則の出どころ |
| `wom/ppc/ppc_run_info.py` | `check_ppc_output()`：評価済み以外は今の計画の金額として使わない（印に `valuation_status` が無い古い印は評価済みとして読む） |
| `tools/run_headless_from_folder.py` | `_run_ppc()` を resolver に（引数は 5 つのまま。Value Chain が差し替えて使う）。snapshot の `ppc`：評価済みは今までのキーと値のまま、一部未評価はキーを足す、未評価は金額のキー無し。CLI の 1 行の表示 |
| `wom/gui/app.py` | PPC の実行を resolver に（規則の出どころ・チャネルの対応・基準通貨）。完了の表示を評価の状態で（「サンプルの販売データ」の警告を置き換え）。「未確認の出力を表示」の釦は、金額の出力（台帳）があるときだけ |
| `wom/planning_state/__init__.py` | B.3：`attach_realized()`：評価済みでなければ `realized.ppc` に状態・理由を入れ、金額を 0 として読まず、計画の利益との比較（`gap_decomposition`）を作らない（`comparison: 保留`）。一部未評価は評価できた範囲の値を `*_valued_part` に |
| `tools/run_planning_loop.py` | 評価済みでないときの表示（財務：…、比較：保留） |
| `wom/valuechain/fx.py`・`wom/valuechain/run.py` | `FxTable.load(model_dir, base_currency)`：為替のファイルだけを同じ resolver で（モデル → 宣言 → 無ければ空の表＝他通貨は未評価）。PPC が評価済みでなければ `compare_with_ppc()` を実行せず「比較不可（理由）」と記録して最後まで終える（`vc_checks.json` の `ppc_comparison`） |
| `data/sample/Cookie-jp-2026`・`rice-japan-2027-2028`・`smartphone-global-2026-2029` の `planning_config.csv` | B.4（K5）：`ppc_shared_rules_dir,data/ppc` を 1 行足した |
| `tests/test_ppc_no_silent_fallback.py`（新規、14 件）・`tests/test_ppc_run_info.py`（1 件を書き換え）・`tests/conftest.py`（1 行） | §C |

### 4.1 実装の要点

- **規則の出どころは 1 か所**（`resolve_ppc_rules(model_dir)`）。headless・GUI・`run_ppc_from_psi()`・Value Chain の為替がこれを使う。宣言の相対パスはリポジトリの根から解決する。宣言の場所にも無ければ、ほかへ切り替えずに未評価。
- **チャネルの対応方式は別の関数**（`channel_uses_node_name`）：市場価格がモデルにあれば `use_node_name=True`、共有の規則から読んだなら False。§A2 の表のモデルごとの方式（rice だけ False、ほか True）は変わらない。
- **経路ごとに要るファイルだけを見る**：PPC は 9 ファイル、Value Chain は `ppc_fx_rate.csv` だけ。
- **評価済みの判定**：販売記録ごとに (市場, 製品) の価格の行があること、製品に仕入れの原価の行があること、エンジンが問い合わせた (仕入れ先, 製品) の原価に行があること。規則に明示の 0 円が書いてあるものは評価済み（T10）。規則の最初の週より前の週は、判断 (a) のとおり評価済みで、件数を記録。
- **費用の規則**（ノード・区間・関税・振替価格・利益ゾーン）は評価済みの判定に使っていない。当たらない組合せの数は §6.1。
- **除いた量の単位**：除いた製品 × 市場ごとに、PPC の記録の件数（`ppc_records`）・WOM の lot 数（`wom_lots`＝物量 ÷ `cpu_size`）・物量（`qty`）を分けて持つ。
- **前回の出力**：実行の最初に PPC の出力ファイル（台帳・P&L・KPI・警告）と印を消す。未評価で終えたときは、状態だけの `ppc_kpi_summary.json` しか残らない（T11、V5）。

## 5. テストの結果

| 段 | 結果 |
|---|---|
| 新規 `tests/test_ppc_no_silent_fallback.py` ＋ `tests/test_ppc_run_info.py` | 24 passed（112 秒） |
| `quick_check --smoke` | 505 passed（76 秒） |
| `quick_check --full`（1 回目） | 986 passed・**1 failed**・3 skipped（1,125 秒）。失敗は `tests/test_lovem_observer.py::test_q12_observation_does_not_change_the_plan`（下） |
| `quick_check --full`（直した後） | 987 passed・3 skipped・failed 0（1,077 秒＝17 分 50 秒） |

golden：通常 15 ケース・legacy 3 ケースすべて緑（不変、再生成なし）。`data/sample/` で変わったのは、意図した 3 つの `planning_config.csv`（`ppc_shared_rules_dir,data/ppc` の宣言）だけ。

**1 回目の full の失敗と直したこと**：LOVEM の Q12（観測の ON・OFF で計画が変わらないこと）は、2 回の実行をそれぞれ別の一時フォルダの写しで行い、PPC の出力ファイルの hash を比べる。私が `ppc_kpi_summary.json` に足した規則の出どころの記録（`rule_sources`）にモデルのフォルダの絶対パスが入っていたので、hash が実行の場所で変わった。PPC の結果のファイルは置き場所に依存してはいけないので、記録からモデルのフォルダを外した（モデルのフォルダは `ppc_run_info.json` が持つ）。直した後、`tests/test_lovem_observer.py` と本件のテストは 30 passed。

§C の対応：

| # | テスト | 確かめたこと |
|---|---|---|
| T01 | `tests/test_golden.py` | §5 |
| T02 | `test_t02_…` | 宣言（絶対パス）のある bom-test の写しで `ppc_fx_rate.csv` を共有の場所へ移す：出どころが `shared:` と記録され、snapshot の `ppc` が元と完全に同じ |
| T03 | `test_t03_…` | 宣言なしで `ppc_tariff_rule.csv` が無い：計画は最後まで動き、`未評価`、足りないファイルが並ぶ。共有の場所は読んでいない |
| T04 | `test_t04_…` | 規則が見出しの行だけ：`未評価`（評価できる販売記録が無い）、出力は状態だけの JSON、`SMARTPHONE` が出ない、`total_lots` が無い |
| T05 | `test_t05_…` | Cookie の写しで `Cookie_Import` の仕入れの原価を消す：`一部未評価`、除いた 3 市場ごとに件数・lot・物量。評価した範囲の売上が、全部ある Cookie の台帳の `Cookie_Local` の売上と一致 |
| T06・T14 | `test_t06_t14_…` | 未評価・一部未評価の snapshot を `attach_realized()` に渡す：`profit` のキーが無く、`gap_decomposition` が None、比較は「保留」 |
| T07 | `test_t07_…` | 宣言なしでモデルに為替が無い：Value Chain の為替は「未設定」で、USD→JPY は NaN（`data/ppc` を読まない）。宣言すると共有の為替 |
| T08 | `test_t08_…` | `python -m wom.ppc`（販売の CSV なし）の見本の実演は今までどおり動く |
| T09 | `test_t09_…` | `Cookie_Import × Retail_JP_CVS` の価格の行だけを消す：その組合せだけが除かれ `一部未評価`、台帳にその組合せの事象が無い（0 円で評価されない） |
| T10 | `test_t10_…` | 価格に明示の 0 を書く：評価済み（snapshot は今までどおり） |
| T11 | `test_t11_…` | 同じ出力のフォルダで、評価済みの Cookie → 価格のファイルが無い bom-test：台帳などが残らず、JSON に金額が無い。GUI の門番も「未評価」で読まない |
| T12 | `test_t12_…` | PPC が未評価（宣言を外した Cookie）で Value Chain：出力が保存され、比較は「比較不可」、保存の検査は OK |
| T13 | `test_t13_…` | 相対の宣言 `data/ppc` は作業のフォルダを変えてもリポジトリの根の `data/ppc` に解決。宣言の場所に無ければ未評価（ほかへ切り替えない） |
| （判断 a） | `test_price_before_first_rule_week_…` | 価格の行をすべて計画より後の週にする：評価済みで、件数が `price_before_first_rule_week` と `ppc_warnings.csv` に記録される |
| （S2） | `test_load_without_fallback_…` | `PPCRuleSet.load()` は、ファイルが無ければ止まる（黙って `data/ppc` を読まない） |

**書き換えた既存のテスト**：`tests/test_ppc_run_info.py::test_sample_fallback_is_recorded_and_not_used_as_the_plans_result` → `test_unknown_products_are_not_valued_and_no_sample_is_used`。製品が規則に無いとサンプルに差し替わることを確かめていたが、K4 でその動きを止めたので、「未評価で金額を書かず、今の計画の結果として読まない」を確かめる内容に変えた。`tests/test_sim_mgmt_display.py` は変更不要だった。

## 6. golden と既存のモデル

- golden（通常 15・legacy 3）：§5 のとおり。
- 宣言を足した 3 モデル（Cookie・rice・smartphone）：規則の出どころ・チャネルの対応方式（rice False、ほか True）・基準通貨（JPY）は §A2 と同じで、golden の金額も同じ。
- smartx：判断 (a) のとおり評価済みのまま、`price_before_first_rule_week` に件数が記録される（価格 3 チャネル × 106、仕入れの原価 159）。

### 6.1 費用の規則の当たらない組合せ（B.2：今は評価済みの判定に使わない）

リポジトリの外の道具（`survey_cost_rules.py`）で数えた。§A と同じく、各 golden のモデルを一時フォルダに写して回している。数えたのは、費用の規則を引いて行が無かった回数。括弧内は、そのうちの異なる組合せの数。空欄は 0。

| case | node_costs | edge_costs | tariff | profit_zone |
| :--- | ---: | ---: | ---: | ---: |
| Cookie-jp-2026 | 1,248（6） | 1,248（5） | 1,872（7） | |
| apparel-global-2028-2029 | 788（4） | | 1,576（6） | |
| apparel-us-2026 | 888（48） | 1,332（64） | 888（48） | |
| bom-test-2026 | 40（1） | 120（4） | 40（1） | |
| ev-europe-2026 | 1,052（6） | 3,682（14） | 1,052（6） | |
| ev-thailand-2026 | 1,248（6） | 3,120（10） | 1,248（6） | |
| ev-thailand-2026_update | 1,248（6） | 3,432（11） | 1,248（6） | |
| oil-global-2027 | 2,798（21） | 6,995（37） | 2,798（21） | |
| rice-japan-2027-2028 | | | 4,652（4） | |
| smartphone-global-2026-2029 | 4,508（12） | 1,127（3） | | |
| smartx-2027-2029 | 3,808（10） | 7,905（20） | 4,304（12） | 414（1） |
| soysauce-eu-2027 | 1,248（6） | | 2,496（5） | |
| soysauce-jpy-2027-alloc | 928（6） | | 1,856（7） | |
| soysauce-jpy-2027 | 1,248（6） | | 2,496（5） | |
| soysauce-us-2027 | 624（3） | | 1,248（4） | |

読み方：全ケースに、行の無い組合せがある。多くは「その経路にその費用が無い」ことを、行を置かずに表しているものと見られる（関税の無い国内の区間、費用を持たない中継のノード等）。ただ、今のファイルでは、行が無いことと「0 円と決めた」ことを区別できない。依頼書 B.2 のとおり、今回はこれを評価済みの判定に使わず、数えるだけにした。費用の規則にも「0 と明示する行」を求めるかどうかは、次に決めること。

**大杉さんの判断（2026-10-26）**：今は件数を数えるだけにする（評価済みの判定に使わない）。明示の 0 の行を求めるかは、化粧品の費用を置く段階で、費用の種類ごとに決める。

## 7. 化粧品での確かめ（§D、`output/bsseaf_cosmetics/D8/` の写し）

| # | 結果 |
|---|---|
| V1 | `未評価`。理由：「規則のファイルが無い（共有の規則の宣言も無い）: ppc_fx_rate.csv；製品が規則に無い: COS_Serum, COS_Cream」。snapshot の `ppc` は `base_currency`・`valuation_status`・`reason`・`excluded` だけで、lot 数・粗利率は無い。出力のフォルダには状態だけの JSON |
| V2 | 規則のファイルを全部消した写し：`未評価`（9 ファイルが無い）。前回の「粗利率 30.4%」は出ない |
| V3 | Value Chain：為替の表は「未設定（モデルに ppc_fx_rate.csv が無く、共有の規則の宣言も無い）」。`vc_fx_log.csv` に `data/ppc` は 0 件。他通貨は未評価（173 件）、保存の検査 OK、PPC との比較は「比較不可（PPC が未評価：…）」 |
| V4 | Flow Check 表2：全体 demand 4,056・当週 3,864・遅配 0・注文残 192、タイの代理店 Serum 390／286／104・Cream 299／211／88。変更課題①②③の報告書の C3a と同じ |
| V5 | 同じ出力のフォルダで Cookie（評価済み、粗利率 17.96%）→ 化粧品：化粧品の結果は `未評価`、フォルダには状態だけの JSON（キーは `base_currency`・`excluded`・`reason`・`rule_sources`・`valuation_status`）。Cookie の台帳・金額は残らない |

## 8. 止める理由と申し送り

**止める理由**：§3 の smartx の件だけ（判断 (a) で解決）。§A の事実はコードのとおり、golden のモデルで S3・S4・0 円は無かった、宣言を足しても値とチャネルの対応方式は変わらなかった。

**申し送り**：

1. **GUI でモデルのフォルダが無いとき**（Demo tree）は、規則が見つからず `未評価` になる（以前は `data/ppc` の見本の規則で計算した）。
2. **GUI の「一部未評価」**：今の計画の金額として P&L の上書き・Landed Cost に使わない（`check_ppc_output()` が評価済みだけを通す）。評価できた範囲の値を画面に出す表示は作っていない。
3. **`snap["ppc"]["revenue_base"]` などを直接読む道具**（`tools/analyze_smartx_bottleneck.py`・`tools/s2_eval_compare.py`）は、未評価のモデルでは KeyError で止まる（0 として読まない）。どちらも評価済みのモデル用。
4. **費用の規則の「無い＝費用なし」**（§6.1）：未設定と区別できない。区別するなら規則のファイルに「費用なし」を明示する書き方を決める必要がある（大杉さん）。
5. **Start Here への追記の案**（本文は Claude君）：R12（未評価）に「PPC の `valuation_status`（評価済み／一部未評価／未評価）。未評価は金額のキーを持たない」、R 表に「共有の規則は `planning_config.csv` の `ppc_shared_rules_dir` で宣言する。宣言が無ければ `data/ppc` は読まない」、落とし穴に「規則に無い製品・市場は黙って落ちず、除いた量が `excluded` に出る。全計画の金額と比べない」。
