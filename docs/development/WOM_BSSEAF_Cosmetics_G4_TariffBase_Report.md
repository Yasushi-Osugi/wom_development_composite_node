---
handoff:
  case_id: BSSEAF-COS-G4
  task_id: G4-T0-T1-customs-value-thailand
  role_from: implement         # Code君
  role_to: owner               # 大杉さん
  target_commit: ebde951
  request: requests/RequestLetter_BSSEAF_Cosmetics_G4_TariffBase_to_CodeKun.md
  acceptance:
    S1: pass
    S2: pass
    S3: pass
    S4: pass
  evidence:
    - docs/development/WOM_BSSEAF_Cosmetics_G4_TariffBase_appendix/check_g4.py
    - docs/development/WOM_BSSEAF_Cosmetics_G4_TariffBase_appendix/check_g4_result.json
  status: "実装済み。段階 6（正式なサンプルに表の 2 行）も済み（§9）。G5 には進んでいない"
  stop_reasons: []
  open_items: []
  next: owner
---

# 報告書：G4（タイ向けの関税の課税価格）を Value Chain で計算する（確認 T0、実装 T1）

- 依頼書：`requests/RequestLetter_BSSEAF_Cosmetics_G4_TariffBase_to_CodeKun.md`（v0.1）
- 業務定義：`docs/design/drafts/WOM_G4_TariffBase_Business_Definition_v0.1.md`、共通照合表：`docs/design/drafts/WOM_G4_G5_TariffFreight_Reconciliation_v0.1.md`
- 作業：Code君（Claude Code、Windows）、2026-11-12
- 着手時の SHA：`ebde951090950343a56744633b69a79d8ced3974`（ブランチ `wom-v1r6m0_BS-SEAF`、作業ツリーは clean）。依頼書の基準 `ccf2b40` の後の 1 コミット（`ebde951`：G4/G5 の決定の記録、文書だけ）を含む。コード・サンプルは `ccf2b40` と同じ
- 出力：`output/g4_trial/`（git の対象外）。付録：`docs/development/WOM_BSSEAF_Cosmetics_G4_TariffBase_appendix/`
- Python：`C:\Users\ohsug\anaconda3\python.exe` を明示して使った

## 一言で

**`vc_customs_valuation_rule.csv`（任意の新しい表）に載った区間では、関税を「評価用の商品価額 ＋ 価額に含まれない運賃 ＋ 保険・その他」×税率で計算し、受入の週に受け手（輸入する法人）の在庫原価として 1 件だけ計上するようにした。税率 0% の出荷には関税の行を立てず、課税価格の記録 `vc_customs_valuation.csv` に 1 行残す。化粧品の写し（30%）で代表の lot は 2029-W02 に 36,504 円・1 件、全期間 689 件・27,959,256 円、PPC との関税の差 347,256 円（＝16,536 個 × 70 円 × 30%）。表の無いモデル（正式なサンプルを含む）は前と 1 バイトも変わらない。PPC のコード・正式なサンプル・保護対象のコアは変えていない。**

**追記（段階 6、§9）：大杉さんの決定で、正式なサンプルに表の 2 行を入れた。税率 0% なので金額は変わらず、区間の 0 円の関税の行 689 行が課税価格の記録 689 行（課税価格の合計 93,197,520 円、税額 0）に置き換わった。PPC との利益の差は 0 円のまま、golden は不変。**

## 1. 先に確かめたこと（B1〜B4、T0、コードを変えない）

T0：`python -m tools.valuechain_run --model-dir data/sample/cosmetics-sg-th-2027-2029 --out output/g4_trial/t0_0`、同じく写し `output/g4_trial/model_t0_30`（`ppc_tariff_rule.csv` の `WH_JP_Released->DC_TH` の 2 行の `tariff_rate` を 0.3 にしただけ）→ `t0_30`。

| # | 見立て | 結果 | 判定 |
|---|---|---|---|
| B1 | 区間の出荷 2028-W52、受入 2029-W02、同じ週に卸売 | 出荷 `ship:COS_Cream:OUT:dad:WH_JP_Released:COS_Cream:120:12` 2028-W52 → 受入 2029-W02。DC_TH からの卸売の出荷 2029-W02。全 689 出荷で「受入の週 ＝ DC_TH の出荷の週」 | 合う |
| B2 | 0% で区間の関税の行 689 行・すべて 0 円・出荷の週 | 689 行・合計 0・すべて出荷の週（クリーム 299・美容液 390） | 合う |
| B3 | 30% で代表の lot 2028-W52 に 36,000 円・1 件。全期間 VC 27,612,000・PPC 27,612,000 | 2028-W52 に 36,000 円・1 件。VC 27,612,000、PPC 27,612,000（`amount_base × qty`、208 行・16,536 個） | 合う |
| B4 | 代表の lot の卸売の原価（`basis=group`）が 0% で 49,056 円 | 49,056 円 | 合う |

全 689 出荷が計画期間の中で受け入れられる（`arrival_in_horizon` がすべて 1、F8 のとおり）。

## 2. 実装（T1）

### 2.1 変えたもの

| ファイル | 中身 |
|---|---|
| `wom/valuechain/masters.py` | `load_customs_valuation_rule()` を新設（D1）。`VCMasters.customs_valuation`（無ければ空 → 今のまま） |
| `wom/valuechain/ledger.py` | 表に載った区間・SKU は `_edge_costs` で関税の行を立てず、出荷の週に課税価格を決めて持っておく（`_customs_value`）。受入（`_receipt`）で `_book_customs` が関税の行を 1 行（税額 0 なら立てない）と課税価格の記録を 1 行。期間の後に着く出荷は `run()` の最後に `after_horizon` で記録だけ（D2） |
| `wom/valuechain/run.py` | 表があるときだけ `vc_customs_valuation.csv` を出し、`vc_checks.json` に `customs_valuation`（件数・状態別・期間の後の件数・通貨ごとの合計・「`tariff_basis` を使わない」の注記）（D3） |
| `tests/test_valuechain_customs_value.py` | 新規 26 件（単体 8・結合 16〔止める条件 14 を含む〕・E2E 2、パラメータ込み） |
| `tests/conftest.py` | 領域の表に 1 行（`ppc`） |

`policy.py`・PPC のコード・正式なサンプル・保護対象のコア・golden は変えていない。

### 2.2 計算の規則（依頼書 §4 のとおり）

- 商品価額：`transfer_price` なら lot の振替価格 `rec.tp`（工場を出るときの額）、`explicit` なら単価 × 個数
- 運賃の加算：`freight_in_goods_value=0` なら、その区間の `ppc_edge_cost_rule.csv` の `logistics_cost` の行の 1 個当たり（`rate＋fixed`）× 個数。通貨が違えば**出荷の週**の為替で課税価格の通貨に直す。`1` なら 0
- 保険の加算：`insurance_added_per_unit` × 個数。空欄は未確認 → 課税価格 NaN
- 税額：課税価格 × `tariff_rate` を `Decimal` で掛け、取引通貨で小数第 2 位に四捨五入（`ROUND_HALF_UP`）
- 関税の行（受入の週）：`kind=acquisition`・`scope=internal`・`basis=v1,entity,group`・`family=tariff`・`price_type=tariff_cost`・`entity`＝受け手・`node`＝`DC_TH`・`counterparty`＝売り手・`src_id`＝区間の出荷 ID・`note`＝「課税価格 121,680.00 JPY × 0.3（受入の週で代用）」。lot の原価に足す

### 2.3 依頼書に無く、私が足したこと（確認してほしい）

| 足したこと | 理由 |
|---|---|
| 止める条件：受け手のノードの法人がグループの法人でない | 関税を輸入する法人の在庫原価に入れる規則なので、外部の法人が受ける区間には使えない |
| 止める条件：`freight_in_goods_value=0` なのに、その区間に `logistics_cost` の行が無い | 足す運賃が無いのに黙って 0 にしない（黙った既定値を作らない） |
| 止める条件：`goods_value_per_unit`・`insurance_added_per_unit` が負、`edge_id` に `->` が無い | 入力の誤りの検出 |
| 物理の区間の確かめは、ローダに渡された製品だけ | `vc_price_rule.csv` の今の確かめと同じ作り（既存のテストは物理の区間を `{}` で渡している） |
| `status` に `unvalued_goods_value`（振替価格が未評価）と `unvalued_fx`（運賃の為替が無い）を追加 | 依頼書の 3 つ（`valued`／`unvalued_insurance`／`after_horizon`）で表せない未評価の理由。今回のサンプルでは出ない |
| 未評価の issues は区間 × SKU × 理由ごとに 1 件（`customs_value_unvalued`、出荷の件数つき） | V9 の「区間・SKU ごとに 1 件」 |

## 3. 照合（V1〜V11）

照合のスクリプト：付録 `check_g4.py`（出力とモデルの CSV を読むだけ。WOM を import しない。`check_g2.py` に倣う）。結果：付録 `check_g4_result.json`。写しのモデルの表は付録 `trial_models/`。

```
python -I docs/development/WOM_BSSEAF_Cosmetics_G4_TariffBase_appendix/check_g4.py --g4-dir output/g4_trial --out docs/development/WOM_BSSEAF_Cosmetics_G4_TariffBase_appendix
```

| # | 期待 | 結果 | 判定 |
|---|---|---|---|
| V1 | `model_a0` 代表の lot：121,680（120,000 ＋ 1,680 ＋ 0）、税額 0、`duty_week` 2029-W02、関税の行 0 件 | そのとおり。`duty_line_id` 空欄 | 合う |
| V2 | `model_a30`：2029-W02 に 1 件・36,504・`E_JP`・`DC_TH`、`src_id`＝区間の出荷 ID。2028-W52・2029-W01 に 0 件。`duty_line_id` がその行 | そのとおり（`line_id` 68647） | 合う |
| V3 | 2029-W02 の卸売の原価（`group`・`entity`）85,560 | `entity` 85,560・`group` 85,560（`v1` は 159,960） | 合う |
| V4 | `model_b30`：121,680・36,504・運賃の加算 0。全出荷で `model_a30` と同じ | そのとおり（689 出荷すべて一致） | 合う |
| V5 | `model_err30`：123,360・37,008。スクリプトが「期待と違う」と判定 | 123,360・37,008。判定「期待（121,680）と違う」 | 合う（誤りを見つけられる） |
| V6 | 689 件・27,959,256（クリーム 10,914,696・美容液 17,044,560）。課税価格の合計 93,197,520。全出荷で「税額 ＝ 課税価格 × 0.3」 | そのとおり | 合う |
| V6 明細 | 法人 × 週 × 出荷 ID で関税の行と課税価格の記録を突き合わせる（共通照合表 §3） | 689 組すべて対応（片方だけ 0）。週 ＝ `duty_week` ＝ 出荷の記録の `arrival_week`、法人・額・`line_id` 一致 | 合う |
| V7 | PPC 27,612,000。「費用 関税」の差 347,256。利益の差がちょうどこの額だけ T0（30%）から動く | PPC 27,612,000。差 347,256.0。利益の差 0 → −347,256（台帳の利益 −347,256、PPC は不変） | 合う |
| V8 | `model_a0`：記録 689 行・課税価格 93,197,520・税額 0。区間の関税の行 0 件。PPC 0 円 | そのとおり | 合う |
| V9 | `model_ins`：課税価格 NaN、`status=unvalued_insurance`、関税の行は NaN で未評価。issues 区間・SKU ごとに 1 件 | 689 行すべて NaN・`unvalued_insurance`。関税の行 689（NaN・`valued=0`）。issues 2 件（クリーム 299・美容液 390） | 合う |
| V10 | `model_a30` を同じ場所で 2 回・別の場所で 1 回。明細が同じ | 明細・課税価格の記録・在庫の 3 つとも 3 回一致 | 合う |
| V11 (a) | 正式なサンプル（表なし）で出力が T0 と同じ | `vc_run_info.json` 以外の全ファイルがバイト一致（`vc_shipments.csv.gz` だけは `plan_id` の列に git の状態〔clean／`+dirty`〕が入るので、その列を除いて一致）。`vc_customs_valuation.csv` は出ない | 合う |
| V11 (b) | `model_a0` の明細 ＝ T0 から区間の 0 円の関税の行 689 行を除き `line_id` を除いたもの | 一致（T0 104,962 行 − 689 ＝ a0 104,273 行） | 合う |
| V11 (c) | PPC の出力は同じ入力どうしでバイト一致 | t0_0／t1_sample／t1_a0、t0_30／t1_a30／t1_b30 の `ppc/` 7 ファイルすべて一致 | 合う |
| V11 (d) | golden 全件不変 | `--full` の `test_golden.py` が全件緑。`tests/golden/`・`data/sample/` に差分なし | 合う |

### 代表の lot の明細（30%、区間の出荷 → 受入・卸売）

| 週 | 行 | T0（`model_t0_30`） | T1（`model_a30`） |
|---|---|---:|---:|
| 2028-W52 | 在庫原価 運賃（`E_JP`・`DC_TH`） | 1,680 | 1,680（変えていない） |
| 2028-W52 | 在庫原価 関税 | **36,000** | なし |
| 2029-W01 | （輸送中） | 関税の行なし | 関税の行なし |
| 2029-W02 | 在庫原価 関税（`E_JP`・`DC_TH`、受入の週） | なし | **36,504** |
| 2029-W02 | 在庫原価 加工・取扱（`DC_TH`） | 288 THB | 288 THB |
| 2029-W02 | 卸売の売上 | 38,400 THB | 38,400 THB |
| 2029-W02 | 卸売の原価（`entity`・`group`） | 85,056 | **85,560** |
| 2029-W02 | 販売費 関税（`DC_TH→TH_Distributor`、表に無い区間） | 0 | 0（今のまま） |

全行は付録 `t0_30_lot_money_lines.csv`・`t1_a30_lot_money_lines.csv`、課税価格の記録は `t1_a30_lot_customs_valuation.csv`・`t1_b30_lot_customs_valuation.csv`。

## 4. テスト

| 段 | 結果 |
|---|---|
| 新しいファイル `tests/test_valuechain_customs_value.py` | 26 passed（G1・G2・手計算のテストと合わせて 74 passed） |
| `python -m tools.quick_check --area ppc` | 189 passed・0 failed（308 秒） |
| `python -m tools.quick_check --full` | **1,124 passed・3 skipped・0 failed**（1,048 秒）。golden 全件緑 |

注：1 回目の `--full` は、出力をファイルに向けたため `quick_check` 自身が pytest の行を cp932 で書けず（`UnicodeEncodeError`）止まった。テストの失敗ではない。`PYTHONIOENCODING=utf-8` を付けてやり直し、上の結果を得た（ログ `output/g4_trial/quick_check_full.log`）。`quick_check` の出力の文字コードは今回直していない（範囲外。§6.2 の 6）。

## 5. 合格の条件

| # | 条件 | 判定 |
|---|---|---|
| S1 | B1〜B4 が見立てどおり | 合う（§1） |
| S2 | V1〜V11 | 合う（§3） |
| S3 | テストの追加、`--area ppc`、`--full` が緑、golden 全件不変 | 合う（§4） |
| S4 | 変えたのは `wom/valuechain/`（`masters.py`・`ledger.py`・`run.py`）とテスト、`tests/conftest.py` の 1 行、報告書と付録だけ | 合う（`policy.py` も変えていない） |

止める理由に当たるものは無かった。

## 6. 申し送りと、大杉さんに決めてほしいこと

### 6.1 決めてほしいこと

| 一言で | 中身 | 推奨 |
|---|---|---|
| 正式なサンプルに表の 2 行を入れるか（段階 6）→ **入れる（2026-11-12 決定、§9 で実施）** | `data/sample/cosmetics-sg-th-2027-2029/vc_customs_valuation_rule.csv` に `model_a0` と同じ 2 行（`transfer_price`、運賃別、保険 0、`receipt`）。税率は 0% のままなので金額は 1 円も変わらない。区間の 0 円の関税の行 689 行が消え、課税価格の記録 689 行（課税価格 93,197,520 円・税額 0）に置き換わる。golden は Value Chain を見ないので変わらない見込み | 入れる（課税価格が 0% でも記録に残り、税率を変えたときにそのまま正しい課税価格で計算される） |

### 6.2 申し送り

1. **通関の確定の週は受入の週で代用**している（§0 の 2 件目）。週がずれる業務になったら、`duty_week` に値を足す（区間ごとの遅れの週数など）。今は `receipt` 以外で止まる。
2. **G5 と同じ `ledger._edge_costs` を触った**。G4 の分岐は「関税の行」だけで、運賃・保険の行の計上は変えていない。G5（CIF の運賃の負担）はこの上に重ねる。課税価格に足す運賃は `ppc_edge_cost_rule.csv` の行を**読むだけ**で、帳簿の運賃の行とは独立（共通照合表 §1「一つの外部運賃を課税価格の算定と帳簿の両方で参照できる」のとおり）。G5 で運賃の負担法人を変えても、課税価格の加算は変わらない。
3. **`ppc_tariff_rule.csv` の `tariff_basis` は、表に載った区間では Value Chain が使わない**（PPC は今のまま使う）。`vc_checks.json` の `customs_valuation.note` に書いた。
4. `vc_ppc_comparison.csv` の「費用 関税」の差 347,256 円は、PPC が振替価格だけを課税価格にしていることによる（G3 と同じく PPC は照合の参考値のまま）。運賃・SGA の分け方の差（各 ±6,243,120 円）は G1 から続くもので、今回は変わっていない。
5. 期間の後に着く出荷は関税を計上せず、記録に `after_horizon`（課税価格・税額は分かる値を残す）。今回のサンプルでは 0 件。
6. `tools/quick_check.py` は、標準出力をファイルに向けると Windows の既定の文字コード（cp932）で pytest の行を書けずに止まることがある（§4）。`PYTHONIOENCODING=utf-8` で避けられる。直すなら別の小さな依頼で。

## 7. BS-SEAF の記録

| 項目 | 内容 |
|---|---|
| 始めと終わり | 始め 16:42（依頼書を読み始め）、終わり 17:40。実作業：読む 16:42〜16:43、T0 16:43〜16:45、実装・写し・照合・単体テスト 16:45〜16:57、報告書 16:57〜17:05、仕上げ 17:38〜17:40。待ち時間：`--area ppc`＋`--full` の実行 16:57〜17:37（文字コードで止まった 1 回目の `--full` 17:02〜17:20 を含む。その間に報告書を書いた）。人の橋渡し・待ちは無し |
| 人の橋渡し | 無し（依頼書の §0 で判断はすべて済んでいた） |
| 再利用した知識 | G2 の照合スクリプト `check_g2.py` の作り（出力と CSV だけを読む、段が無ければ飛ばす）、G2 の MDF の丸め（`Decimal` で掛けて `ROUND_HALF_UP`）、G2 の申し送り（PPC の `amount_base` は 1 個当たり）、G2 のテスト `test_valuechain_distributor_mdf.py` の合成の木 |
| 迷った所・足りなかった情報 | (1) 業務定義の週の例（W28 → W30）と実際の記録（W52 → W02）の違いは、依頼書 §2 に読み替えが書いてあったので迷わなかった。(2) 依頼書の止める条件に、受け手が外部の法人の区間と、運賃別なのに運賃の行が無い場合が無かった。黙った既定値を作らない方針で止めることにした（§2.3）。(3) 「物理の区間でない」の確かめで、既存のテストが物理の区間を `{}` で渡していることに後から気づき、`vc_price_rule.csv` と同じ「渡された製品だけ確かめる」にした。(4) V11 (a) の「出力が同じ」で、`vc_shipments.csv.gz` の `plan_id` に git の状態が入ることは依頼書に無かった（列を除いて比べた）。(5) 単体テストの丸めで、float で掛けてから丸めると 50.05 × 0.3 が 15.01 になる誤りに気づき、`Decimal` で掛けるように直した（化粧品の値は整数なので結果は変わらない）。三つの文書の間の食い違いは無かった |

## 8. commit

commit メッセージの下書き：`commit_msg207.txt`。git の操作は大杉さんが行う。

## 9. 段階 6（追記、2026-11-12）

大杉さんの決定（「Yes, add the rows」）で、正式なサンプルに表の 2 行を入れた。G5 には進んでいない。

### 9.1 変えたもの

| ファイル | 中身 |
|---|---|
| `data/sample/cosmetics-sg-th-2027-2029/vc_customs_valuation_rule.csv`（新規） | `model_a0` と同じ 2 行（`WH_JP_Released->DC_TH`、クリーム・美容液、`transfer_price`、運賃別〔`0`〕、保険 `0`、`receipt`）。`note` は根拠の文に直した（モデルの仮定で証憑では未確認） |
| `data/sample/cosmetics-sg-th-2027-2029/README.md` | 金額の規則の一覧に表を追加、表の説明の段落、既知の限界の「関税の課税価格」と「G4」を解決済みに |
| `tests/test_valuechain_customs_value.py` | 正式なサンプルに表がある前提に直した：表の無い写しを作るヘルパー、正式なサンプルの 2 行の読み込み、正式なサンプルの E2E（関税の行 0 件・記録 689 行・課税価格 93,197,520・issues 0）、表を除いた写しの E2E（前のまま）。28 件 |

コード・PPC・golden・保護対象のコアは変えていない。

### 9.2 確かめたこと

| 確かめたこと | 結果 |
|---|---|
| 正式なサンプルの Value Chain の出力 ＝ T1 の `model_a0` の出力 | `vc_run_info.json` 以外の全 17 ファイルがバイト一致（`vc_shipments.csv.gz` は `plan_id` の列を除いて一致）（`output/g4_trial/s6_sample`） |
| PPC の出力 ＝ T0 | `ppc/` の 7 ファイルすべてバイト一致 |
| PPC との利益の差（消去前） | 0 円のまま（PPC・台帳とも 631,849,608 円） |
| 区間の関税の行・記録 | 関税の行 0 件、課税価格の記録 689 行（`valued`）、税額 0。issues 0 |
| テスト | 新しいファイル 28 passed。`quick_check --area ppc,golden` 210 passed・0 failed。`tests/golden/` に差分なし |

### 9.3 気づいたこと

- 表の `note` に半角のカンマを書いたら列がずれ、読み込みが「`edge_id 'COS_Cream'` は区間でない」で止まった（黙って読み違えなかった）。カンマを除いて直した。表の `note` にカンマを書くときは `"…"` で囲む。
- README の「期待する結果」の Value Chain の行（差 22,196,148 円「下の G2 だけ」）と既知の限界の「G2」の行は、G2 の段階 6 の後も古いまま（今の差は 0 円）。G4 の範囲外なので直していない。
