---
handoff:
  case_id: STRATEGY-CONVERT-001
  task_id: promo-convert-slice1-cosmetics-sgec-cream
  role_from: implement         # Code君
  role_to: owner               # 大杉さん
  start_sha: 80fedf8c72151db73bdb90b77f06fbbd3eb48fce
  base_model: data/sample/cosmetics-sg-th-2027-2029
  base_demand_sha256: b9ae795e4a713cd880a5b35cb41035106b227b0e2b9d12c37b0c519c619d829e
  catalog_version: "v0.1 (sha256:325c39c8aaca)"
  knowledge_used:
    - id: 翻訳・変換の定義
      version: "v0.2"
    - id: 販促の業務定義（GPT-MC君）
      version: "v0.1"
    - id: 4P 翻訳表（Code君）
      version: "v0.1"
  acceptance:
    ref: "依頼書 §7 の S1〜S11 → 本書 §2"
  status: "S1〜S11 すべて合う。押し戻しが起きた（MID・HIGH、タイの代理店）。proportional_week でも 1 回ずつ回した"
  open_items:
    - "翻訳表 v0.1 の Promotion の行の書き方（§6。直すのは Claude君）"
    - "押し戻しで作り溜めが増える（在庫の最大 146 → 152・157 lot）。保有費が未設定なので A には入っていない"
  stop_reasons: []
  next: owner
---

# 報告：経営施策の変換 — 最初の縦の一本（化粧品の SG の EC のクリーム、追加販促なし／あり）

- 依頼書：`requests/RequestLetter_Promo_Convert_Slice1_to_CodeKun.md`（v0.1b）
- 期待値の正：`docs/design/drafts/WOM_4P_Promotion_Business_Definition_v0.1.md`（GPT-MC君）
- 着手時の SHA：`80fedf8c72151db73bdb90b77f06fbbd3eb48fce`（M6 段 1 の commit 1a59804 を含む）
- 実行：Windows 11、Python 3.12.3（`C:\Users\ohsug\anaconda3\python.exe` を明示。`python` は Windows のストアの別名で動かない）
- 出力：`output/strategy_slice1/`（git の対象外）。付録：`docs/development/WOM_Promo_Convert_Slice1_appendix/`

## 0. 一言で

施策シート（CSV 4 本）を読んで、コックピットの案の需要と「案の費用の前提」を書き換える道具を作り、
4 案（追加販促なし、あり × 反応 0%・25%・50%）を作って回した。**需要の入力・追加費用・P0 の差・控除後の比較値の差は、
業務定義の期待値（§6.1・§6.2・§2.2・§7.2）と 1 円・1 lot まで一致した。** LOW はエンジンの結果が基準と同じで、
控除後の比較値だけ 276,000 円低い。MID・HIGH では工場の押し戻しが起き（タイの代理店の分を前の週へ）、在庫が少し
増えたが、どの市場も全量を当週に納品した（他の市場の ④・⑤ の差は 0）。

## 1. 作ったもの

| ファイル | 中身 |
|---|---|
| `wom/strategy/__init__.py` | `StrategyError`、型カタログの版 `v0.1` |
| `wom/strategy/rules.py` | 純関数：週の計算、`demand_delta`（反応週・反動、正負の区間ごとの累積の切り捨て、未反映の端数）、`apply_delta`（負の需要で止める）、`fx_rate_for_weeks`（期間で 1 つのレート、無い・変わるで止める）。計算はすべて `Decimal` |
| `wom/strategy/sheets.py` | シート 4 本と型カタログを読む・検査する。`select_plan` がキャンペーンのそろい（需要と費用の行が 1 つずつ、対象・週・版が同じ）と仮説の水準を確かめる |
| `wom/strategy/convert.py` | 1 つの案へ変換（`plan_changes` で全部を検査してから書く）。需要の対象の行、`set_fixed_cost` で費用の前提、変更記録、`case.json` の `changes`。冪等 |
| `wom/strategy/overflow.py` | 工場 × 市場の押し戻しの記録。headless を 1 回（PPC なし）回し、`BackwardPlanner.run` の戻り値の `overflow_by_node` を受け取る（エンジンのファイルは変えない） |
| `wom/strategy/compare.py` | 4 案の要約。`case_runner.compare_cases`（比較の道具の固定費の表）、`period_fulfillment`（①〜⑤）、`compare_scenarios.load_run`（在庫・年齢）を使う |
| `wom/strategy/measure_type_catalog.csv` | 型カタログ（初版 2 行） |
| `tools/strategy_convert.py`・`tools/strategy_compare.py` | CLI（§4 のコマンドのとおり） |
| `tools/compare_scenarios.py` | §3.4 の直し（§5） |
| `tests/test_strategy_convert.py`・`tests/data/strategy_slice1/` | テスト 23 件と、テストが読むシート（`output/` のシートと同じもの） |
| `tests/test_compare_scenarios.py` | §3.4 の結合テストを 1 件足し、THB の行の期待（「条件外」→ 止める）を直した |
| `tests/conftest.py`・`tools/quick_check.py` | 領域の表に 1 行、`--changed` の対応に 3 行（`wom/strategy/*`・`tools/strategy_*` → allocation、`tools/compare_scenarios.py` → allocation・ppc） |

エンジン（保護対象のコアを含む）・PPC・Value Chain・正式なサンプル・golden は変えていない。

### 1.1 シートの形（付録 `sheets/`）

依頼書 §1 の列のとおり。`measures.csv` は 1 キャンペーン（`CMP_CREAM_SGEC_2028`）に 2 行
（`…_DEMAND` が `promo_demand_delta`、`…_COST` が `promo_external_cost`、版 `v01`）。`hypotheses.csv` は
`H_PROMO_CREAM_SGEC` の low・base・high（率 0・0.25・0.50、遅れ 2 週、反動 0、`validation_placeholder`）。
`external_conditions.csv` は `ENV_BASE_v01` の 1 行。`plans.csv` は 4 案（キャンペーンで選ぶ）。

### 1.2 変換で書いたもの（付録 `change_log/`）

| 案 | 需要（`COS_Cream × SG_EC`、反応週 2028-W12〜W23） | 費用の前提 `inputs/fixed_cost.csv` | 変更記録 |
|---|---|---|---|
| C01 P_BASE | 変えない | 作らない | `rule=no_measure` の 1 行 |
| C02 P_PROMO_LOW | 12 行とも 2 → 2（d 0） | `promo_campaign_add, E_SG, 2028-W10, 2028-W21, 23000, JPY` | 需要 12 行・端数 1 行・費用 1 行 |
| C03 P_PROMO_MID | W13・15・17・19・21・23 が 3（計 +6） | 同上 | 同上 |
| C04 P_PROMO_HIGH | 12 週とも 3（計 +12） | 同上 | 同上 |

費用の前提の `note`：`strategy_convert; campaign=…; measure=CMP_CREAM_SGEC_2028_COST; version=v01; 200 SGD/週 × 115 JPY/SGD（ppc_fx_rate.csv、元のモデル） = 23000 JPY/週 × 12 週 = 276000 JPY; paid_start_week・paid_end_week は費用の発生の週（現金の支払いの週を決めたものではない）`。

## 2. 合格の条件

| # | 条件 | 結果 |
|---|---|---|
| S1 | 対象と単位 | ○ `(COS_Cream, SG_EC)` を計画の木の leaf_out（region＝SG_EC → ノード SG_EC）、`ppc_market_price.csv`（131 SGD／個）、`vc_node_assignment.csv`（E_SG）で解決。量は lot（需要の CSV）、物量単価は PPC の台帳のまま（1 lot＝24 個は `cpu_size`）。変換は lot だけを書き、単価には触れない |
| S2 | 期間 | ○ 費用 W10〜W21（12 週、費用の前提の行）、反応 W12〜W23（12 週、変更記録の行）、観測 W10〜W27（18 週、テストで需要 36・42・48 を確認）を別に扱う |
| S3 | 需要 | ○ §6.1 の週別の表（W09〜W28、3 水準）と §6.2（追加 0・0・6・12、2028 年 104・104・110・116、報告期間 299・299・305・311）に一致（`test_cosmetics_four_plans`、E2E の ①）。対象外の需要の入力は全行同じ |
| S4 | 費用 | ○ 販促の 3 案で 276,000 円（週 23,000 円 × 12）、P_BASE は 0。既存の 15% は PPC・Value Chain の規則のまま（変換はそのファイルに触れない。LOW の P0 が基準と同じことで確かめた） |
| S5 | 冪等 | ○ 2 回目は「変更なし」で、需要・費用の前提・変更記録が同じ。MID を変換した案に HIGH を変換すると、新しく HIGH を変換した案と需要が同じ（端数を引き継がない） |
| S6 | ①〜⑤ | ○ `period_fulfillment.request_table` が要求週ごとに ①＝②＋③、②＝④＋⑤ を検査（成り立たなければ止める）。さらに対象の ① ＝ B ＋ d を検査した |
| S7 | LOW | ○ 計画の結果（snapshot.json の forward・backward・ppc・psi）が P_BASE と同じ、案のモデルの入力の hash も全部同じ。P0 同じ、A だけ −276,000 |
| S8 | MID・HIGH | ○ 記録した（§3・§4）。§7.2 の条件つきの参考値と一致（参考値の条件「増分をすべて販売・発送でき、他の市場を減らさない」が、この計画では成り立った） |
| S9 | 小例と止める条件 | ○ §6.3（負の差分 `0,-1,0,-1`、端数 0.75 の未反映、非定常の基準、負の需要、計画の外）、Decimal の小例（2 × 5% × 10 週 ＝ 1 lot。浮動小数点では 0 になることもテストで示した）、円換算とレートが変わる期間、シート・型・対象・キャンペーン・費用の前提の止める条件（§7） |
| S10 | 追跡 | ○ 変更記録の各行に plan_id・campaign_id・施策 ID と版・仮説 ID と版・水準・env_id・型カタログの版（sha256 の先頭つき）・元のモデル・元の需要の sha256・着手時の SHA・ファイル・鍵・週・前後・規則。`case.json` の `changes` にも同じ要点。費用の所在は案の `inputs/fixed_cost.csv`（比較だけが読む） |
| S11 | 変えていない | ○ `git status`：変更は §1 の表のファイルだけ。エンジン・正式なサンプル・golden は無変更。`--changed` は §8 |

## 3. 4 案の要約（報告期間 2027-W01〜2029-W52、付録 `summary/`）

| 案 | P0（円） | 追加費用 B_add | A ＝ P0 − B_add | ΔA（対 P_BASE） | 対象の B／d／① | ② | ③ | ④ | ⑤ | 他の市場の ④・⑤ の差 | 在庫の最大（lot） | 年齢の最大（週） | 押し戻し（延べ） |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---:|---:|---:|
| C01 P_BASE | 631,119,240 | 0 | 631,119,240 | 0 | 299／0／299 | 299 | 0 | 299 | 0 | — | 146 | 6 | 0 |
| C02 P_PROMO_LOW | 631,119,240 | 276,000 | 630,843,240 | −276,000 | 299／0／299 | 299 | 0 | 299 | 0 | 0・0 | 146 | 6 | 0 |
| C03 P_PROMO_MID | 632,285,424 | 276,000 | 632,009,424 | +890,184 | 299／+6／305 | 305 | 0 | 305 | 0 | 0・0 | 152 | 7 | 45 |
| C04 P_PROMO_HIGH | 633,451,608 | 276,000 | 633,175,608 | +2,056,368 | 299／+12／311 | 311 | 0 | 311 | 0 | 0・0 | 157 | 7 | 120 |

- ④ はすべて当週の納品（前倒し・遅配 0）。
- 在庫の最大は、グループの所有の在庫（全 SKU・全拠点）の週末の lot 数の、計画期間で最大の週。年齢は先入れ先出しの年齢の最大（全 SKU・全チャネル）。52 週超は全案 0。
- A は業務定義 §4 の費用範囲の比較値で、グループの営業利益や Net Cash ではない（本社固定費の欠落・歩留まり損の原価未反映・保有費の未設定は基準モデルのまま）。

## 4. 期待値と観測値

| 項目 | 期待値（業務定義） | 観測値 | 差 |
|---|---|---|---|
| 需要の入力（週別・合計） | §6.1・§6.2 | 同じ | 0 |
| 追加費用 | 276,000 円（各販促案） | 276,000 円 | 0 |
| LOW の P0 差・A の差 | 0・−276,000 | 0・−276,000 | 0 |
| MID の P0 差・A の差（§7.2、条件つきの参考値） | 1,166,184・890,184 | 1,166,184・890,184 | 0 |
| HIGH の P0 差・A の差（同） | 2,332,368・2,056,368 | 2,332,368・2,056,368 | 0 |
| 追加販売（lot） | 0・0・6・12（条件つき） | 0・0・6・12（④ の差） | 0 |
| 他の市場への波及 | 決めていない（記録する） | ④・⑤ とも 0 | — |

**条件つきの参考値と一致した理由**：工場の能力（`Factory_JP` の soft の計画）は、追加の 6・12 lot を作れるだけあった。
ただし反応の週には足りず、Backward が超えた分を前の週へ押し戻した（§5）。押し戻しは「前の週に作る」ことなので、
どの市場の納品も遅れず、増分は全部納品された。追加の 1 lot の P0 は 194,364 円（§7.2 の手計算）と同じ。
押し戻しの代わりに前の週に作った分は在庫として持つ（最大 146 → 152・157 lot）が、モデルの保有費が未設定
（`vc_config.csv` の `holding_rate_weekly` が空欄）なので、P0・A には入らない。

## 5. 押し戻しの記録（依頼書 §5、付録 `summary/overflow_by_factory_market.csv`・`summary_overflow_policy/`）

元のモデル（P_BASE）と LOW では押し戻しは 1 件も無い。MID・HIGH で起きた。工場はどちらも `Factory_JP`（クリーム）。

| 案 | overflow_policy | 押し戻し（延べ）の市場別 | 他の市場の ④・⑤ の差 | P0 | 計画の集計（snapshot） |
|---|---|---|---|---:|---|
| C03 MID | tail（既定） | TH_Distributor 45 | 0・0 | 632,285,424 | — |
| C05 MID | proportional_week（C03 の写し） | SG_Distributor 17、SG_EC 9、SG_Store 10、TH_Distributor 9（計 45） | 0・0 | 632,285,424 | C03 と同じ |
| C04 HIGH | tail | TH_Distributor 120 | 0・0 | 633,451,608 | — |
| C06 HIGH | proportional_week（C04 の写し） | SG_Distributor 46、SG_EC 24、SG_Store 27、TH_Distributor 23（計 120） | 0・0 | 633,451,608 | C04 と同じ |

- 延べは、押し戻した lot を、押し戻した回数だけ数える（同じ lot が 2 週押し戻されれば 2）。母数は処理した週に現れた lot の数。
- tail では、行の順（region の名前の順）で末尾のタイの代理店だけが押し戻される（M6 段 0 で調べた行の順の偏り）。
  proportional_week では 4 市場に比例で分かれる。
- どちらでも、押し戻しは「前の週に作る」だけで納品は全量当週なので、市場ごとの ①〜⑤、P0、計画の集計（lot 数の
  集計と週別の系列の hash）は同じ。違うのは、どの市場の lot を早く作るか（どの lot が長く在庫にいるか）だけ。
  在庫の最大・年齢の最大も同じ（152・157 lot、7 週）。
- proportional_week の写し（C05・C06）は、案のモデルの `planning_config.csv` に `overflow_policy,proportional_week`
  を 1 行足して作った（元のモデル・正式なサンプルは変えていない）。

## 6. 型カタログと翻訳表 v0.1 との食い違い

型カタログ（付録 `measure_type_catalog.csv`）は依頼書 §2 の 2 行。翻訳表 v0.1（`docs/design/WOM_4P_Parameter_Translation_Table.md`
の Promotion）と比べた食い違い（翻訳表を直すのは Claude君）：

1. **上乗せの週**：翻訳表の「販促の需要増」は「実施週の需要に上乗せ」と書く。業務定義 §3.2 と依頼書 §3.1 は、
   実施の週を遅れだけ後ろへ移した**反応週**に、**反応週の基準需要**を掛けて上乗せする。カタログは後者。
2. **需要の置き場**：翻訳表は `demand_forecast.csv`「または `market_entry_plan.csv` の数量」と書く。初版は
   `market_entry_plan.csv` のある案では止める（需要の正本が 2 つになるため。業務定義 §3.4）。
3. **期間を決めた予算**：翻訳表では ×（代わりに ①率に直す ②案の外の固定費として記録する）。`promo_external_cost` は
   ② を型にしたもの。翻訳表の × の行はそのまま正しいが、「② の型がある」ことを書き足す余地がある。
4. **単位の注**：翻訳表の欄「lot／週」は需要の行には合う。費用の型は「金額／週」（報告通貨に換算して書く）で、
   翻訳表の「金額／lot」とは別（業務定義 §10.1 の 5）。

## 7. 止める条件（すべて書き込みの前。テストのある所）

| 止める条件 | テスト |
|---|---|
| D が負（反動で −B を超える） | `test_negative_demand_stops`、`test_negative_demand_from_rebound_stops_before_writing`（ファイルが変わらない） |
| 反応・反動の週が計画の期間の外 | `test_reaction_outside_the_plan_stops` |
| 仮説の行・水準が無い、根拠が空、知らない水準・種類 | `test_sheet_stops` |
| 対象が leaf_out で 1 つに解決できない、価格が無い | `test_sheet_stops` |
| 案に `market_entry_plan.csv` がある | `test_entry_plan_and_base_drift_and_rate_change_stop` |
| 案の写しの、施策の対象の外の需要が元のモデルと違う（基準がずれている） | 同上 |
| 元のモデルが作業を作った時から変わった・`--base-model` が作業の元のモデルと違う | 同上 |
| 期間内でレートが 1 つでない・レートが無い | 同上、`test_yen_conversion_and_rate_change_stops` |
| シートの列の不足、知らない型、×の型、型カタログにあって規則が無い型 | `test_sheet_stops` |
| キャンペーンの需要と費用の片方が欠ける、対象・週・版が合わない | `test_campaign_must_have_matching_demand_and_cost`（4 例） |
| 費用の前提：同じ施策・版で中身が違う、同じ費目を別の出どころが使う、この案に無い施策から書いた行が残っている | `test_cost_premises_keep_other_rows_and_rerun_rules`、`test_cost_item_used_by_another_source_stops`、`test_converted_cost_row_left_by_another_plan_stops` |
| 同じ施策 ID・版の重複、同じ対象で週の重なる需要の施策 | `sheets.py`（`read_sheets`・`select_plan`） |

## 8. 比較の道具の直し（依頼書 §3.4）

`tools/compare_scenarios.py`：

- `check_report_currency(plan, hq_currency)` を足した。固定費の表に報告通貨以外の週額の行があれば、ファイル・行・
  case・cost_item・通貨と直し方（「週額を報告通貨に換算して書く。換算のレートと元の額は note に」）を出して止める。
- `compare()` の最初（計算を始める前）と `fixed_cost_table()` の最初で呼ぶ。だから控除後・合計の行・他の費目の境目の
  どれも計算しない（`fixed_cost_breakeven.csv` も書かない）。
- 報告通貨は、モデルの `vc_config.csv` の `hq_currency`（`report_currency()`）。無いモデルは前と同じ JPY。
- 前の「共通の円建て週額の条件外（通貨 …）」の分岐は消した（ここへ来る前に止まる）。
- 円だけの表は前と同じ結果（`test_foreign_currency_weekly_amount_stops_before_any_cost_computation` の後半、
  既存の固定費のテストはすべて通る）。

## 9. テスト

- `tests/test_strategy_convert.py`（23 件）、`tests/test_compare_scenarios.py`（+1 件）。
- `python -m pytest tests/test_strategy_convert.py tests/test_compare_scenarios.py tests/test_test_areas.py`：70 passed（18.5 秒）。
- `python -m tools.quick_check --changed`：§11 に結果。
- E2E は 4 案（＋押し戻しの 2 案）の実行そのもの（1 案 約 45〜52 秒）。テストには入れていない（実行が重いため）。

## 10. 大杉さんが実機で確かめる手順

```powershell
$PY="C:\Users\ohsug\anaconda3\python.exe"; $W="output/strategy_slice1/ws"; $M="data/sample/cosmetics-sg-th-2027-2029"; $S="output/strategy_slice1/sheets"
& $PY -m tools.cockpit_cases new  --ws $W --model $M --max-age-weeks 52 --name P_BASE
& $PY -m tools.cockpit_cases copy --ws $W --from C01 --name P_PROMO_LOW
& $PY -m tools.cockpit_cases copy --ws $W --from C01 --name P_PROMO_MID
& $PY -m tools.cockpit_cases copy --ws $W --from C01 --name P_PROMO_HIGH
& $PY -m tools.strategy_convert --ws $W --case C03 --plan P_PROMO_MID --sheets $S --base-model $M --dry-run
& $PY -m tools.strategy_convert --ws $W --case C01 --plan P_BASE       --sheets $S --base-model $M
& $PY -m tools.strategy_convert --ws $W --case C02 --plan P_PROMO_LOW  --sheets $S --base-model $M
& $PY -m tools.strategy_convert --ws $W --case C03 --plan P_PROMO_MID  --sheets $S --base-model $M
& $PY -m tools.strategy_convert --ws $W --case C04 --plan P_PROMO_HIGH --sheets $S --base-model $M
& $PY -m tools.cockpit_cases run --ws $W --case C01 C02 C03 C04
& $PY -m tools.strategy_compare --ws $W --base C01 --cases C02,C03,C04
```

- 作業のフォルダが既にあれば、`new` は止まる（中を片付けるか別の名前に）。シートは `tests/data/strategy_slice1/` と同じ。
- 見る所：`strategy_compare` の出力の P0・B_add・A・ΔA（§3 の表）、`<作業>/C03/inputs/strategy_change_log.csv`、
  `<作業>/C03/inputs/fixed_cost.csv`。変換をもう一度回すと「変更なし」。
- コックピットの画面（比較）で C01 と C02 を並べると、P0 は同じで、費用の前提の行 `promo_campaign_add` の分だけ控除後が下がる。

## 11. `--changed` の結果

`python -m tools.quick_check --changed`（2026-11-21、Windows）：領域 allocation・ppc・public・smoke、
**1,066 passed・0 failed**・304 deselected、962 秒（約 16 分）。保護対象のコアは変えていないので、full と 3 層テストの
要求は出ていない。

## 12. 申し送り

1. **押し戻しと作り溜め**：販促で反応の週の需要が工場の計画の能力を超え、前の週に作る。今のモデルは保有費が未設定なので、
   作り溜めの費用は A に出ない。保有費を置くと MID・HIGH の A は少し下がる（比較の道具の `holding_sensitivity.csv`
   は既にある）。
2. **M6 の既定**：tail と proportional_week でこの 4 案の結果（納品・金額）は同じ。違いはどの市場の lot を早く作るか
   だけ。M6 の既定を決める材料としては「この量では結果に差が出ない」例になる。
3. **翻訳表**：§6 の 4 点。
4. **次の版の候補**（依頼書 §9 のしないこと）：期間内でレートが変わる費用の分割、`market_entry_plan.csv` のある案、
   Price・Place・Product の型、反動減を入れた案（変換の規則とテストは既にある）。
5. **環境**：Git Bash・PowerShell の `python` は Windows のストアの別名で動かない。Anaconda を明示した。

## 付録

- `sheets/`：シート 4 本
- `measure_type_catalog.csv`：型カタログ
- `change_log/`：4 案の変更記録と費用の前提
- `summary/`：4 案の要約（`strategy_summary.csv`・`.md`、①〜⑤ の鍵別、押し戻し）
- `summary_overflow_policy/`：tail と proportional_week の比較（C01・C03〜C06）

## commit メッセージの下書き

1. 道具とテスト

```
feat(strategy): convert promotion measure sheets into cockpit cases (slice 1: COS_Cream x SG_EC)

- wom/strategy: sheets (measures/hypotheses/external conditions/plans), type catalog v0.1
  (promo_demand_delta, promo_external_cost), Decimal integer rule, converter (idempotent,
  checks before writing), push-back record (overflow_by_node), 4-case summary
- tools/strategy_convert.py, tools/strategy_compare.py
- tools/compare_scenarios.py: a weekly amount not in the report currency stops before the
  after-cost value, the total row and the boundaries are computed
- tests: test_strategy_convert.py (23), test_compare_scenarios.py (+1, THB row now stops)
- engine, PPC, Value Chain, samples and golden unchanged
```

2. 報告書

```
docs(strategy): report of promo convert slice 1 - 4 cases match the business definition v0.1
(demand, 276,000 yen, P0 and A); push-back at Factory_JP recorded (tail vs proportional_week)
```
