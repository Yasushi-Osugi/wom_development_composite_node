---
handoff:
  case_id: BSSEAF-COS-G4
  task_id: G4-T0-T1-customs-value-thailand
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: ccf2b40
  knowledge_used:
    - id: G4 業務定義案（GPT-MC）
      version: v0.1
      applicability: "§2 課税価格の決め方、§3 負担法人・計上週・件数、§4 代表 1 ロットの手計算、§6 採用判断と受入値"
    - id: G4・G5 共通照合表（GPT-MC）
      version: v0.1
      applicability: "§1 G4 の列、§2 比較ケースの受入値、§3 照合の手順"
    - id: G2 報告書
      version: "2026-11-12"
      applicability: "照合のスクリプト check_g2.py の作り（出力と CSV を読むだけ）、PPC の ppc_event_ledger.csv の amount_base は 1 個当たり（× qty）"
  acceptance:
    ref: "この依頼書 §7"
  evidence:
    - docs/design/drafts/WOM_G4_TariffBase_Business_Definition_v0.1.md
    - docs/design/drafts/WOM_G4_G5_TariffFreight_Reconciliation_v0.1.md
  status: "試行可能"
  open_items: []
  stop_reasons: []
  handover_notes:
    - "§0 の 4 件と業務定義 §6 の 3 件を、大杉さんが推奨どおり採用（2026-11-12）"
  next: implement
---

# Request Letter：G4（タイ向けの関税の課税価格）を Value Chain で計算する（確認 T0、実装 T1）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-11-12）
- 版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`（ブランチ `wom-v1r6m0_BS-SEAF`、基準 `ccf2b40`。着手時の SHA を報告書に記録する）
- 前提：G4 業務定義案 v0.1・共通照合表 v0.1（GPT-MC）、大杉さんの判断（§0、2026-11-12、すべて推奨どおり採用）
- 範囲：**Value Chain の改修**（`wom/valuechain/` と、そのテスト）。保護対象のコアには触れない。**PPC のコード、正式なサンプル、golden は変えない**。試行はモデルの写しで行う
- 出力：`output/g4_trial/` の下（git の対象外）
- 順番：G5（`RequestLetter_BSSEAF_Cosmetics_G5_CIF_Freight_to_CodeKun.md`）と同じ `ledger._edge_costs` を触る。**G4 を先に終えて報告し、G5 はその後に**行う（commit も分ける）

---

## 一言で

**タイ向けの区間 `WH_JP_Released → DC_TH` の関税を、「評価用の商品価額 ＋ 価額に含まれていない運賃・保険」に率を掛けて計算し、DC_TH の受入の週に日本本社の在庫原価として 1 件だけ計上できるようにしてください。課税価格は、税率が 0% でも 1 出荷ごとに記録に残します。PPC は変えず、照合の相手として使います。**

## 0. 大杉さんの判断（2026-11-12、すべて推奨どおり採用）

| 一言で | 中身 | 決定 |
|---|---|---|
| G4 の業務定義を採用する | 業務定義 §6 の 3 件：評価用の商品価額は振替価格 5,000 円／個（美容液 6,000）を運賃別として仮に使う／輸入地点までの運賃を一度だけ足し、保険・その他は明示の 0／`E_JP` の在庫原価に計上 | 採用（推奨どおり） |
| 関税の計上週は「受入の週」で代用する | WOM のデータに通関の記録は無く、表せるのは出荷の週と受入の週だけ（§1 の F4）。通関の確定と DC_TH の受入が同じ ISO 週だと置く（DC_TH は木の説明で「港の近く」）。週がずれる業務になったら、そのとき区間ごとの通関の遅れの週数を足す | 採用（推奨どおり） |
| PPC は今回変えない | PPC は振替価格 × 率のまま、照合の参考値として残す（G3 と同じ扱い）。0% では差 0、30% の試算では差 347,256 円が残り、内訳を説明できる | 変えない（推奨どおり） |
| 0 円の関税の行は立てない | この表に載せた区間では、税率 0% の出荷に 0 円の関税の明細を立てず、課税価格の記録（`vc_customs_valuation.csv`）に置き換える。表に載せない区間は今のまま | 採用（推奨どおり） |

4 件とも上の「決定」のとおり。この依頼書のとおり進めてください。

## 1. 現行 WOM との対応（`ccf2b40` で確認）

| # | 事実 | 根拠 |
|---|---|---|
| F1 | `WH_JP_Released → DC_TH` は両端とも `E_JP`。Value Chain では同じ法人の中の移動（`scope=management`、原価振替）で、法人間の売買は立たない | `vc_node_assignment.csv`、`ledger._transfer` |
| F2 | 関税は `ppc_tariff_rule.csv` の行（`tariff_rate`・`tariff_basis`）を読み、`tariff_basis=transfer_price` なら lot の振替価格 `rec.tp`（工場 `Factory_JP` を出るときに決まる 5,000 × 24 ＝ 120,000 円）に率を掛ける。**運賃は課税価格に足さない** | `ledger._edge_costs`（443〜485 行）、`masters.py` 241〜246 行 |
| F3 | 関税の行は**出荷の週**に、受け手（`E_JP`、`DC_TH`）の在庫原価（`kind=acquisition`、`basis=v1,entity,group`）として立つ。税率 0% でも 0 円の行が 1 出荷に 1 行立つ（クリーム 299 行・美容液 390 行、すべて 0 円） | `ledger._edge_costs`、G2 の T0 の出力 |
| F4 | 出荷の記録にあるのは出荷の週と受入の週（`vc_shipments.csv` の `ship_week`・`arrival_week`）だけ。受入の週は木の `lt_wks`（DC_TH は 2 週）で決まる。**通関の確定の週は表せない** | `records.py`、`sc_tree_master.csv` |
| F5 | 現行のサンプルでは、**DC_TH に着いた lot はその週のうちに代理店へ卸売される**（全 689 出荷で受入週 ＝ DC_TH の出荷週）。受入週に関税を計上すると、関税の入った在庫が週末に残る lot は無い。在庫に入ったことは、卸売の原価（`cogs`）で確かめる | G2 の T0 の `vc_shipments.csv` |
| F6 | 運賃 70 円／個（1 lot 1,680 円）は、今も出荷の週に `E_JP` の在庫原価として 1 行立つ（業務定義の「既に計上した運賃は引き継ぐ」と同じ）。**運賃の扱いは変えない** | `ledger._edge_costs`、`policy.py` |
| F7 | PPC の関税は `ppc_event_ledger.csv` の `ppc_event_type=tariff_cost`、`edge_id=WH_JP_Released->DC_TH`。**`amount_base` は 1 個当たりで、合計は `amount_base × qty`**。PPC の行は市場の leaf × 販売の週にまとめた単位（`lot_id` は `PSI-<製品>-<leaf>-<週>`）で、WOM の Lot_ID と 1 対 1 にならない | G2 報告書の申し送り 4、G2 の T0 の出力 |
| F8 | タイ向けの全出荷は計画期間の中で受け入れられる（689 出荷、`arrival_in_horizon` がすべて 1）。受入の週に移しても、計上されない関税は出ない | G2 の T0 の `vc_shipments.csv` |

**現行のデータ・設定で確かめられること**：今の課税価格（120,000 円）と出荷の週の計上（T0）、30% の写しでの合計 27,612,000 円（M0t と同じ）。

**改修が要ること**：課税価格に運賃・保険を足す規則、評価用の商品価額を振替価格と別に持てること、受入の週の計上、課税価格の記録。

**現行 WOM で表せない条件**（今回は扱わない）：通関の確定の週そのもの（受入の週で代用）、通関・運送・保険の証憑とその番号、納付の週（Value Chain は支払・資金を持たない）、実際の品目分類・原産地。

## 2. 業務の期待（業務定義 §4 の当てはめ）

代表の lot：`COS_Cream:TH_Distributor:2029-W03:00003`（G2・G3 と同じ lot）。区間の出荷 `ship:COS_Cream:OUT:dad:WH_JP_Released:COS_Cream:120:12`、**出荷 2028-W52 → DC_TH の受入 2029-W02**（業務定義の例の W28 → W30 は仮の週。週は実際の記録に読み替える。金額・件数は定義のまま）。同じ 2029-W02 に DC_TH から代理店へ卸売。

| ケース | 課税価格 | 0% | 30% |
|---|---:|---:|---:|
| 評価用の商品価額が運賃別（推奨・本番の設定）：5,000 × 24 ＋ 70 × 24 | **121,680 円** | 0 円 | **36,504 円** |
| 同じ価額を運賃込みで与える：5,070 × 24、運賃の追加 0 | **121,680 円** | 0 円 | **36,504 円** |
| 比較：今の計算（振替価格だけ）：5,000 × 24 | 120,000 円 | 0 円 | 36,000 円 |
| 誤りの検出：運賃込み 5,070 にさらに運賃 1,680 を足す | 123,360 円 | 0 円 | 37,008 円 |

美容液の 1 lot：課税価格 6,070 × 24 ＝ 145,680 円、30% で 43,704 円。

| 週・事象 | 期待（30%） | 期待（0%） |
|---|---|---|
| 2028-W52 出荷 | 関税の行 0 件（運賃 1,680 円の行は今のまま 1 件） | 同じ |
| 2029-W01 末 輸送中 | 関税の行 0 件 | 同じ |
| 2029-W02 受入 | `E_JP`・`DC_TH` の在庫原価に関税 36,504 円・1 件 | 関税の行 0 件。課税価格の記録 121,680 円・税額 0 |
| 2029-W02 卸売 | 卸売の原価（`basis=group`）が T0 の 49,056 円 ＋ 36,504 ＝ **85,560 円** | T0 と同じ 49,056 円 |

全期間（30% の写し）：クリーム 7,176 個 × 1,521 ＝ 10,914,696、美容液 9,360 個 × 1,821 ＝ 17,044,560、計 **27,959,256 円**。PPC（振替価格 × 30%）は 27,612,000 円、差 **347,256 円** ＝ 16,536 個 × 70 × 30%（M0 報告書 T14 と同じ）。

## 3. 先に確かめること（T0、コードを変えない）

正式なサンプル（`ccf2b40`）と、その写しで `ppc_tariff_rule.csv` の `WH_JP_Released->DC_TH` の 2 行の `tariff_rate` を 0.3 にしたもの（`output/g4_trial/model_t0_30/`）で、Value Chain を実行する（`python -m tools.valuechain_run --model-dir <モデル> --out output/g4_trial/<名前>`）。

| # | 確かめること | 違ったら |
|---|---|---|
| B1 | 代表の lot の区間の出荷が 2028-W52、受入が 2029-W02、同じ週に卸売（F5） | 止めて報告 |
| B2 | 0% の正式なサンプルで、その区間の関税の行が 689 行・すべて 0 円・出荷の週（F3） | 止めて報告 |
| B3 | 30% の写しで、代表の lot の関税が 2028-W52 に 36,000 円・1 件。全期間で Value Chain 27,612,000 円・PPC 27,612,000 円（F2） | 止めて報告 |
| B4 | 代表の lot の卸売の原価（`basis=group`）が 0% で 49,056 円 | 止めて報告 |

## 4. 実装（差分だけ）

### 4.1 D1：課税価格の規則の表（新しい任意のファイル）

`vc_customs_valuation_rule.csv`（無ければ今のまま）。1 行 ＝ 区間 × SKU：

| 列 | 意味 |
|---|---|
| `edge_id`, `product_id` | 物理の区間と SKU。`ppc_tariff_rule.csv` に同じ区間・SKU の行が必要（税率はそちらを使う） |
| `goods_value_basis` | `transfer_price`（lot の振替価格 `rec.tp`）か `explicit`（下の単価） |
| `goods_value_per_unit`, `currency` | `explicit` のときだけ書く（1 個当たり）。`transfer_price` のときは空欄 |
| `freight_in_goods_value` | `0`：価額は運賃別 → その区間の運賃（`ppc_edge_cost_rule.csv` の `logistics_cost` の行、1 個当たり `rate＋fixed`）を課税価格に 1 回足す。`1`：運賃込み → 足さない |
| `insurance_added_per_unit` | 課税価格に足す保険・その他（1 個当たり、`currency` と同じ通貨、`transfer_price` なら振替価格の通貨）。**明示の 0 を書く**。空欄は「未確認」 |
| `duty_week` | `receipt` だけを受け付ける（§0 の 2 件目。通関の記録ができたら値を足す） |
| `note` | 根拠 |

読み込みで止める（`MasterError`、ファイル・行・値と直し方）：列の不足、区間・SKU の重複、物理の区間でない、`ppc_tariff_rule.csv` に行が無い、`goods_value_basis` が二つ以外、`explicit` で単価・通貨が無い、`transfer_price` で単価を書いた、`freight_in_goods_value` が 0・1 以外、`duty_week` が `receipt` 以外。

**運賃・保険の通貨が課税価格の通貨と違うとき**は、出荷の週の為替（`ppc_fx_rate.csv`、`fx.py` の今の換算）で課税価格の通貨に直す。今回のサンプルはすべて JPY。

### 4.2 D2：計算と計上（`ledger.py`）

表に載った区間・SKU の出荷では、`_edge_costs` で関税の行を立てず、出荷 ID ごとに次を持っておく：

- 商品価額 ＝ `transfer_price` なら `rec.tp` の額、`explicit` なら単価 × 個数
- 運賃の加算 ＝ `freight_in_goods_value=0` なら区間の運賃（個数 × 1 個当たり）、`1` なら 0
- 保険の加算 ＝ `insurance_added_per_unit` × 個数。空欄なら課税価格は NaN（未評価）
- 課税価格 ＝ 三つの和。税額 ＝ 課税価格 × `tariff_rate`（取引通貨で小数第 2 位に四捨五入、`Decimal` の `ROUND_HALF_UP`）

**受入の週**（`_receipt`、その出荷の lot が着いたとき）に：

- 税額が 0 でなければ（NaN を含む）、関税の行を 1 行：`kind=acquisition`、`scope=internal`、`basis=v1,entity,group`、`family=tariff`、`price_type=tariff_cost`、`entity`＝受け手（輸入する法人、今回 `E_JP`）、`node`＝`s.to`（`DC_TH`）、`counterparty`＝売り手、`src_id`＝区間の出荷 ID、`lot_id`、`note`＝「課税価格 <額> × <率>（受入の週で代用）」。lot の原価に足す（`_add_cost`）
- 税額が 0 なら関税の行は立てない（§0 の 4 件目）
- どちらでも、課税価格の記録を 1 行出す（D3）

計画の期間の後に着く出荷は、関税を計上せず件数を `vc_checks.json` に出す（今のサンプルでは 0 件の見込み、F8）。

**変えないもの**：表に載らない区間の関税（今のまま出荷の週）、運賃・保険の行の計上（今のまま）、`ppc_tariff_rule.csv` の `tariff_basis` の意味（PPC が使う。表に載った区間では Value Chain はこの列を使わないことを `vc_checks.json` の注記に書く）。

### 4.3 D3：課税価格の記録 `vc_customs_valuation.csv`（出力）

表に載った区間の出荷ごとに 1 行：`ship_id`, `lot_id`, `product`, `edge`, `ship_week`, `duty_week`, `entity`, `units`, `goods_value_basis`, `goods_value`, `freight_added`, `insurance_added`, `customs_value`, `currency`, `tariff_rate`, `duty`, `duty_line_id`（行を立てたときの `line_id`、無ければ空欄）, `status`（`valued`／`unvalued_insurance`／`after_horizon`）。

`vc_checks.json` に件数と合計（課税価格・税額、通貨ごと）を出す。

### 4.4 テスト

新しいファイル `tests/test_valuechain_customs_value.py`（`tests/conftest.py` の領域の表に `ppc` で 1 行）。中身：D1 の止める条件、運賃別と運賃込みで同じ課税価格、保険の空欄で未評価、0% で行が立たず記録だけ、30% の額と週（受入の週）、為替の換算（通貨が違う合成のデータ）、表の無いモデルで出力が今と同じこと、化粧品の写しでの E2E（代表の lot と合計）。G1・G2 のテストが今のまま通ること。`python -m tools.quick_check --area ppc`、最後に `--full` を 1 回。golden は全件不変。

## 5. 写しのモデル（`output/g4_trial/`）

| 名前 | 正式なサンプルからの変更 |
|---|---|
| `model_a0` | `vc_customs_valuation_rule.csv` に 2 行（クリーム・美容液）：`WH_JP_Released->DC_TH`、`transfer_price`、空欄、空欄、`0`、`0`、`receipt` |
| `model_a30` | `model_a0` ＋ `ppc_tariff_rule.csv` の同じ区間の 2 行の `tariff_rate` を 0.3 |
| `model_b30` | `model_a30` の表を `explicit`・クリーム 5,070 JPY・美容液 6,070 JPY・`freight_in_goods_value=1` に |
| `model_err30` | `model_b30` の `freight_in_goods_value` を `0` に（誤りの検出の確認用） |
| `model_ins` | `model_a0` の `insurance_added_per_unit` を空欄に |

## 6. 照合（照合のスクリプトは出力とモデルの CSV を読むだけ。WOM を import しない。`check_g2.py` の作りに倣う）

| # | 照らすこと | 期待 |
|---|---|---|
| V1 | `model_a0` の代表の lot の課税価格の記録 | 121,680 円（商品価額 120,000 ＋ 運賃 1,680 ＋ 保険 0）、税額 0、`duty_week` 2029-W02、関税の行 0 件 |
| V2 | `model_a30` の代表の lot | 関税の行が 2029-W02 に 1 件・36,504 円・`E_JP`・`DC_TH`、`src_id` ＝ 区間の出荷 ID。2028-W52・2029-W01 には 0 件。課税価格の記録の `duty_line_id` がその行 |
| V3 | `model_a30` の代表の lot の卸売の原価 | 2029-W02 の `cogs`（`basis=group`・`entity`）が 85,560 円（T0 の 49,056 ＋ 36,504） |
| V4 | `model_b30` | 代表の lot の課税価格 121,680 円・税額 36,504 円（運賃の加算 0）。全出荷で `model_a30` と課税価格・税額が同じ |
| V5 | `model_err30` | 代表の lot の課税価格 123,360 円・税額 37,008 円。**照合のスクリプトが「期待（121,680）と違う」と判定すること**（誤りを見つけられることの確認） |
| V6 | 全期間（`model_a30`） | 関税 689 件、計 **27,959,256 円**（クリーム 10,914,696・美容液 17,044,560）。課税価格の合計 93,197,520 円（クリーム 7,176 × 5,070 ＋ 美容液 9,360 × 6,070）。全出荷で「税額 ＝ 課税価格 × 0.3」 |
| V7 | PPC との照合（`model_a30`） | PPC の関税（`ppc_event_ledger.csv` の `ppc_event_type=tariff_cost`・`edge_id=WH_JP_Released->DC_TH`、`amount_base × qty` の合計）＝ 27,612,000 円。`vc_ppc_comparison.csv` の「費用 関税」の差 ＝ **347,256 円**、利益の差もちょうどこの額だけ T0（30%）から動く。週ごとの一致は求めない（PPC は販売の週にまとめる） |
| V8 | 0% の全期間（`model_a0`） | 課税価格の記録 689 行・課税価格の合計 93,197,520 円・税額 0。その区間の関税の行 0 件。PPC の関税 0 円 |
| V9 | `model_ins` | 課税価格が未評価（NaN）、`status=unvalued_insurance`、関税の行は NaN で立ち未評価の扱い（今の未評価の決まりのとおり）。issues に区間・SKU ごとに 1 件 |
| V10 | 再計算 | `model_a30` を同じ場所で 2 回、別の場所で 1 回。明細が同じ |
| V11 | 変わってはいけないもの | (a) 正式なサンプル（表なし）での Value Chain の出力が T0 と同じ。(b) `model_a0` の明細から、その区間の関税の 0 円の行（689 行）を除き `line_id` の列を除くと、T0 と同じ。(c) PPC の出力は、同じ入力どうし（0% どうし・30% どうし）でバイト単位で同じ。(d) golden |

**明細の判定**：全期間の合計に加えて、法人 × 週 × 出荷 ID（区間の出荷）の単位で、関税の行と課税価格の記録を突き合わせる（共通照合表 §3）。PPC とは合計だけを比べる（F7）。

## 7. 合格の条件

| # | 条件 |
|---|---|
| S1 | B1〜B4 の記録。どれも見立てどおり |
| S2 | V1〜V11 |
| S3 | テスト：単体・結合の追加、`--area ppc`、`--full` が緑。golden 全件不変 |
| S4 | 変えたのは `wom/valuechain/`（`masters.py`・`ledger.py`・`run.py`、必要なら `policy.py`）とテスト、`tests/conftest.py` の 1 行、報告書と付録だけ。PPC のコード・正式なサンプル・保護対象のコアは変えない |

**止める理由**：B1〜B4 が違う、V1・V2・V4 の額か週が違う、V5 で照合のスクリプトが誤りを見つけない、V6 の合計が合わない、V7 で差が 347,256 円にならない、V11 (a)・(b)・(c) が合わない、golden が変わる。

**止める理由ではないもの**：PPC との週ごとの値の違い（PPC は販売の週にまとめる）。`vc_ppc_comparison.csv` の G1 から続く運賃・SGA の分け方の違い（合計が合えばよい）。

## 8. 報告書と記録

- 報告書：`docs/development/WOM_BSSEAF_Cosmetics_G4_TariffBase_Report.md`、付録 `..._appendix/`（照合のスクリプトと結果、代表の lot の明細、写しのモデルの表）。冒頭に引き継ぎの欄（YAML、`next: owner`）。
- 中身：着手時の SHA、B1〜B4、T0・T1 の結果、S1〜S4、止める理由と申し送り、大杉さんに決めてほしいこと（一言の決定と中身、推奨）。少なくとも次を決める事項として書く：**正式なサンプルに表の 2 行を入れるか**（段階 6。入れても 0% なので金額は変わらず、0 円の関税の行が課税価格の記録に置き換わる）。
- BS-SEAF の記録：始めと終わりの時刻（実作業と待ち時間を分ける）、人の橋渡し、再利用した知識。**業務定義・共通照合表・この依頼書の三つで、迷った所や足りない情報があったか**。
- commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に。git の操作は大杉さんが行う。
- Python は `C:\Users\ohsug\anaconda3\python.exe` を明示して使う（G2 の報告：PATH の `python` は Windows Store の起動用）。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-12 | 初版 |
