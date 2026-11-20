---
handoff:
  case_id: STRATEGY-CONVERT-001
  task_id: promo-convert-slice1-cosmetics-sgec-cream
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "M6 段 1 の commit 以降の HEAD（着手時の SHA を記録）"
  knowledge_used:
    - id: 翻訳・変換の定義
      version: "v0.2"
      applicability: "requests/WOM_Convert_Strategic_Issue2WOM_Parameters_Definition_v0.2.md §2〜§6"
    - id: 販促の業務定義（GPT-MC君）
      version: "v0.1"
      applicability: "docs/design/drafts/WOM_4P_Promotion_Business_Definition_v0.1.md §2〜§9（数値・期待値・受け入れ A01〜A10）"
    - id: 4P 翻訳表（Code君）
      version: "v0.1"
      applicability: "Promotion の行、§2"
  acceptance:
    ref: "この依頼書 §7"
  status: "M6 段 1 の commit の後に渡す"
  open_items: []
  stop_reasons: []
  next: implement
---

# Request Letter：経営施策の変換 — 最初の縦の一本：化粧品の SG の EC のクリームで「追加販促なし／あり」を変換して比べる

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉（WOM Project Owner）／起草：Claude君（2026-11-20）／版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`
- 範囲：新しいパッケージ `wom/strategy/`、新しい CLI `tools/strategy_convert.py`・`tools/strategy_compare.py`、比較の道具 `tools/compare_scenarios.py` の小さな直し（§3.4）、テスト、報告書。**エンジン・PPC・Value Chain・正式なサンプル・golden は変えない**
- 出力：`output/strategy_slice1/`（git の対象外）
- **最後のテストは `--changed` だけ**

---

## 一言で

**施策シート（CSV）を読んで、コックピットの案の需要と「案の費用の前提」を書き換える道具を作ってください。** 最初は二つの型だけです：需要の増減（`promo_demand_delta`）と、案の外の期間費用（`promo_external_cost`）。化粧品の `COS_Cream × SG_EC` で 4 案（追加販促なし、あり × 反応 0%・25%・50%）を作って回し、業務定義の期待値と照合し、P0・追加費用・控除後の比較値を並べてください。

## 0. 決まっていること

- 定義 v0.2 の Q1〜Q6（翻訳と変換を分ける、最初は化粧品の 1 製品・1 市場、期間予算は案の外、シートは CSV、翻訳表を型カタログの素材に、M6 と並行）。
- Q7〜Q9（業務定義 v0.1 の仮置きで回す、追加の販促費は `fixed_cost.csv` に円で、M6 の既定が決まるまで `tail` で回し押し戻しを記録）は**大杉さんの判断を受けて、この依頼書を渡す時に §0 を埋める**。
- **数値と期待値は業務定義 v0.1 を正とする**（この依頼書に写した数は便宜）。食い違ったら業務定義に従い、違いを報告する。

## 1. 入力のシート（`output/strategy_slice1/sheets/` に置く。形をこの依頼書で決める）

### 1.1 施策シート `measures.csv`

| 列 | 意味 |
|---|---|
| `measure_id`・`measure_version` | 施策の ID と版（例 `CMP_CREAM_SGEC_2028`・`v01`） |
| `p4` | Product／Price／Place／Promotion |
| `measure_type` | 型カタログの型（初版は `promo_demand_delta`・`promo_external_cost`） |
| `sku_id`・`market` | 対象（`market` は需要の `region`＝leaf_out の識別子） |
| `start_week`・`end_week` | 施策の実施の週（両端を含む） |
| `value`・`unit`・`currency` | 型ごと。`promo_external_cost` は 200・`amount_per_week`・SGD。`promo_demand_delta` は空（量は仮説から） |
| `entity`・`cost_item` | `promo_external_cost` の負担法人（`E_SG`）と費目名（例 `promo_campaign_add`） |
| `hypothesis_id` | `promo_demand_delta` で必須 |
| `rationale` | 狙い・根拠（計算に使わない） |

### 1.2 仮説シート `hypotheses.csv`

| 列 | 意味 |
|---|---|
| `hypothesis_id`・`version`・`level` | 例 `H_PROMO_CREAM_SGEC`・`v01`・`low`／`base`／`high` |
| `kind` | `promotion_response`（初版はこれだけ） |
| `rate` | 反応週の基準需要に掛ける率（0・0.25・0.50） |
| `lag_weeks` | 反応の遅れ（2） |
| `rebound_rate`・`rebound_weeks` | 反動減（主たる 4 案は 0・0） |
| `basis`・`evidence` | `validation_placeholder` と根拠の文（空欄は止める） |

### 1.3 外部環境シート `external_conditions.csv`

初版は `ENV_BASE_v01` の 1 行だけ（「元のモデルの為替・関税・LT のまま」）。行の形だけ決めて、変換では何も書き換えない。

### 1.4 案の組み立て `plans.csv`

| 列 | 意味 |
|---|---|
| `plan_id`・`case_name` | 例 `P_PROMO_MID`・「追加販促 反応 25%」 |
| `measure_ids` | 使う施策（`;` 区切り。P_BASE は空） |
| `hypothesis_level` | `low`／`base`／`high`（P_BASE は空） |
| `env_id` | `ENV_BASE_v01` |

4 案：P_BASE（施策なし）、P_PROMO_LOW（low）、P_PROMO_MID（base）、P_PROMO_HIGH（high）。3 つの販促案は同じ施策・同じ予算で、反応の仮説だけが違う。

## 2. 型カタログ `wom/strategy/measure_type_catalog.csv`（初版の 2 行）

| 型 | 入力 | 書く先 | 規則 | 印 |
|---|---|---|---|---|
| `promo_demand_delta` | 施策の期間・対象、仮説 | 案の `model/demand_forecast.csv`（対象のキーの行だけ） | §3.1 | H → W |
| `promo_external_cost` | 週額・通貨・法人・費目・期間 | 案の `inputs/fixed_cost.csv`（比較だけが読む） | §3.2 | 案の外の費用 |

列：`measure_type, p4, input_unit, target, rule, mark, stop_conditions, note`。翻訳表 v0.1 の Promotion の行と食い違わないこと（食い違いは報告に書く。翻訳表を直すのは Claude君）。

## 3. 変換の規則

### 3.1 `promo_demand_delta`（業務定義 §3）

1. 基準需要 B は**凍結した元のモデル**（`--base-model data/sample/cosmetics-sg-th-2027-2029`）の `demand_forecast.csv` から読む。案の写しの需要を基準にしない（二重の上乗せを防ぐ）。元のモデルの `demand_forecast.csv` の sha256 と、着手時の SHA を記録する。
2. 反応週 ＝ 実施の週を `lag_weeks` だけ後ろへ移した区間。`x(w) = B(w) × rate`（**反応週の B を掛ける**。広告の週の B ではない）。反動減は反応の区間の翌週から `rebound_weeks` 週、`x(w) = −B(w) × rebound_rate`。
3. 整数化：正の区間と負の区間を別々に、区間ごとに累積を切り捨て、前の週の累積との差をその週の d(w) にする（業務定義 §3.3）。区間の終わりの端数は「未反映の端数」として記録し、後の週・別の施策・別の水準へ移さない。
4. D(w) ＝ B(w) ＋ d(w) を、案の `model/demand_forecast.csv` の対象のキーの行に書く。**対象外のキーの行は 1 つも変えない**。
5. 止める（書き込みの前に）：D が負になる、反応週・反動の週が計画の期間の外、仮説の行が無い・水準が無い・根拠が空、対象の `(sku_id, market)` が木の leaf_out・`ppc_market_price.csv` の `market_node` で解決できない、案のモデルに `market_entry_plan.csv` がある（初版は扱わない）、案の写しの対象外の需要が元のモデルと違う（基準がずれている）。

### 3.2 `promo_external_cost`（業務定義 §2.2・§4）

1. 案の `inputs/fixed_cost.csv` に 1 行：`cost_item=promo_campaign_add, entity=E_SG, paid_start_week=2028-W10, paid_end_week=2028-W21, weekly_amount=<円>, currency=JPY, note=<元の 200 SGD・レート・施策 ID・版>`。既存の `set_fixed_cost`（`wom/cockpit/cases.py`）を使って書く。
2. 円への換算：費用発生の各週の `ppc_fx_rate.csv`（元のモデル）の SGD→JPY。**期間内でレートが 1 つでなければ止める**（初版。週ごとの費目に分けるのは次の版）。現在は 115 → 週 23,000 円・計 276,000 円。
3. 案に既に同じ `cost_item` があれば、上書きせず止める（施策の重複）。P_BASE には書かない。
4. PPC・Value Chain の規則（`ppc_node_cost_rule.csv`・`vc_sales_cost_rule.csv`）には書かない。既存の 15% はそのまま。

### 3.3 変更記録 `inputs/strategy_change_log.csv`（案ごと）

列：`plan_id, measure_id, measure_version, hypothesis_id, hypothesis_version, level, env_id, catalog_version, base_model, base_demand_sha256, start_sha, file, key, column, week, before, after, rule, note`。需要は行ごと（before＝B、after＝D）、費用は 1 行。未反映の端数も 1 行（`rule=residual`）。案の `case.json` の `changes` にも、変換したこと（plan_id と記録のファイル）を 1 件足す。

**冪等**：同じシートで同じ案にもう一度変換したら、需要・費用の前提・変更記録が同じになる（2 回目は「変更なし」と出す）。費用の前提に同じ費目があって中身も同じなら、止めずに「変更なし」。

### 3.4 比較の道具の直し（`tools/compare_scenarios.py`、小さく）

今は `fixed_cost.csv` の週額を、通貨によらず `P0 − 週額 × 週数` に使う（円以外は境目の判定だけ「条件外」と出す）。**円以外（報告通貨以外）の週額は控除後の計算に使わず、未評価として表示する**（または止める）。どちらにしたかと理由を報告に書く。

## 4. CLI

```bash
# 案を作る（既存）：P_BASE を作り、写して 3 案
python -m tools.cockpit_cases new  --ws output/strategy_slice1/ws --model data/sample/cosmetics-sg-th-2027-2029 --max-age-weeks 52 --name P_BASE
python -m tools.cockpit_cases copy --ws output/strategy_slice1/ws --from C01 --name P_PROMO_LOW   # MID・HIGH も

# 変換（新しい）
python -m tools.strategy_convert --ws output/strategy_slice1/ws --case C02 --plan P_PROMO_LOW \
    --sheets output/strategy_slice1/sheets --base-model data/sample/cosmetics-sg-th-2027-2029 [--dry-run]

# 実行（既存）と 4 案の要約（新しい）
python -m tools.cockpit_cases run --ws output/strategy_slice1/ws --case C01 C02 C03 C04
python -m tools.strategy_compare --ws output/strategy_slice1/ws --base C01 --cases C02,C03,C04
```

`--dry-run` は書かずに、書く予定の変更（変更記録と同じ形）を出す。`strategy_compare` は、案ごとに：P0（報告期間 2027-W01〜2029-W52）、追加費用（円）、控除後の比較値 A、基準との差 ΔA、対象 `(COS_Cream, SG_EC)` の B・d・①〜⑤、他の市場の ④・⑤ の差、在庫・製品の年齢の最大、工場の押し戻しの有無（§5）。計算は比較の道具の関数（`compare_scenarios`・`period_fulfillment`）を使い、二重に作らない。

## 5. 押し戻しの記録（Q9）

元のモデルの化粧品では押し戻しが 1 週も起きない（段 0）。販促で需要が増えて `Factory_JP` の能力を超えると押し戻しが起き、どの市場が後回しになるかが `overflow_policy` で変わる。

- 4 案とも `tail`（モデルの既定）で回す。
- 押し戻しの有無と量を、工場 × 市場で記録する（`BackwardPlanResult.overflow_by_node` か、段 0 の調査のスクリプトの包み方で）。
- **押し戻しが起きた案があれば**、その案を `overflow_policy=proportional_week` でも 1 回回し（写しで）、他の市場の ④・⑤ の差を並べる。起きなければ「起きなかった」と書く。

## 6. テスト

| 層 | 中身 |
|---|---|
| 単体 | 業務定義 §6.1 の週別の表（4 案、W09〜W28）、§6.2 の合計（追加 0・0・6・12 lot、2028 年 104・104・110・116）。§6.3 の小例（負の差分 `0,-1,0,-1`、端数 0.75 の未反映、非定常の基準で反応週の B を掛ける、費用と反応のずれ、負の需要で止める、計画の外で止める）。円換算（2,400 SGD → 276,000 円）とレートが変わる期間で止める |
| 単体 | 冪等（2 回変換して同じ）、別の水準の端数を引き継がない、同じ費目の重複で止める、対象外のキーの行が変わらない |
| 結合 | シートの CSV → 案の `demand_forecast.csv`・`fixed_cost.csv`・変更記録。シートの列の不足・知らない型・× の型・解決できない対象で止まる |
| 結合 | 比較の道具の §3.4 の直し（円以外の週額） |
| E2E | 4 案を回し、§7 の照合 |

新しいテストのファイルは `tests/conftest.py` の領域の表に足す。最後は `python -m tools.quick_check --changed`。

## 7. 合格の条件（業務定義 §9 の A01〜A10 を、この依頼書の形にしたもの）

| # | 条件 |
|---|---|
| S1 | 対象と単位：`(COS_Cream, SG_EC)` を既存の対応で解決。1 lot＝24 個・131 SGD／個を区別（A01） |
| S2 | 期間：費用 W10〜W21、反応 W12〜W23、観測 W10〜W27 を別に扱う（A02） |
| S3 | 需要：§6.1・§6.2 の期待値と一致。対象外の需要の入力は同じ（A03） |
| S4 | 費用：販促の 3 案で 276,000 円（週 23,000 円 × 12）、P_BASE は 0。既存の 15% は全案で同じ（A04） |
| S5 | 冪等・二重の加算なし（A05） |
| S6 | ①＝②＋③、②＝④＋⑤ を対象の鍵で照合（A06） |
| S7 | **LOW はエンジンの結果が P_BASE と同じで、控除後の比較値だけ 276,000 円低い**（A07。計画のハッシュも同じはず） |
| S8 | MID・HIGH の実納品・売上・費用・在庫・年齢・他の市場への波及を記録（A08。業務定義 §7.2 の条件つきの参考値との一致は合格の条件にしない。違えば理由） |
| S9 | 小例と止める条件（A09） |
| S10 | 追跡：着手時の SHA、元のモデルの需要の sha256、型カタログの版、施策・仮説・外部環境の ID と版、変更の前後、費用の所在から再現できる（A10） |
| S11 | エンジン・正式なサンプル・golden が変わっていない。`--changed` が通る |

**止める理由**：S3・S4・S7 が合わない（変換か比較の誤り）、変換の道具がエンジンや正式なサンプルを変えないと作れない（理由を報告）。

**止める理由ではないもの**：MID・HIGH の結果が §7.2 の参考値と違う（供給の制約・他の市場の減少などの理由を書く）、押し戻しが起きる（§5 のとおり記録）。

## 8. 重い処理の注意

案は 4 つ（押し戻しが起きたら追加で最大 3 つ）。1 つ回すごとに結果がファイルに残る（コックピットの仕組みのとおり）。最後の画面の報告は短く、表は報告書に。

## 9. しないこと

Price・Place・Product の型、期間内でレートが変わる費用の分割、`market_entry_plan.csv` のある案、施策シートを画面で入力すること、探索、PPC・Value Chain に週別の費用の規則を作ること、M6 の既定の変更。

## 10. 報告書と記録

- 報告書：`docs/development/WOM_Promo_Convert_Slice1_Report.md`、付録（シート 4 本・型カタログ・変更記録・要約の表）。冒頭に引き継ぎの欄（YAML、`next: owner`）。中身：着手時の SHA、S1〜S11、4 案の要約の表、期待値と観測値と差の理由（分けて）、押し戻しの記録、§3.4 の直し方、翻訳表 v0.1 との食い違い、大杉さんが実機で確かめる手順、申し送り。
- commit メッセージの下書き 2 つ（道具とテスト／報告書）。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-20 | 初版 |
