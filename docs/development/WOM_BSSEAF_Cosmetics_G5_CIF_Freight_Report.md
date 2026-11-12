---
handoff:
  case_id: BSSEAF-COS-G5
  task_id: G5-T0-T1-cif-freight-singapore
  role_from: implement         # Code君
  role_to: owner               # 大杉さん
  target_commit: 18301c5
  request: requests/RequestLetter_BSSEAF_Cosmetics_G5_CIF_Freight_to_CodeKun.md
  acceptance:
    S1: pass
    S2: pass
    S3: pass
    S4: pass
  evidence:
    - docs/development/WOM_BSSEAF_Cosmetics_G5_CIF_Freight_appendix/check_g5.py
    - docs/development/WOM_BSSEAF_Cosmetics_G5_CIF_Freight_appendix/check_g5_result.json
  status: "実装済み。段階 6（正式なサンプルに表の 2 行）も済み（§9）"
  stop_reasons: []
  open_items: []   # 段階 6・V8 の読み方は 2026-11-12 に大杉さんが決定（§6.1）
  next: owner
---

# 報告書：G5（シンガポール向けの CIF の海上運賃）を、負担法人と在庫原価で正しく分ける（確認 T0、実装 T1）

- 依頼書：`requests/RequestLetter_BSSEAF_Cosmetics_G5_CIF_Freight_to_CodeKun.md`（v0.1）
- 業務定義：`docs/design/drafts/WOM_G5_CIF_FreightResponsibility_Business_Definition_v0.1.md`、共通照合表：`docs/design/drafts/WOM_G4_G5_TariffFreight_Reconciliation_v0.1.md`
- 作業：Code君（Claude Code、Windows）、2026-11-12
- 着手時の SHA：`18301c5`（G4 の commit、ブランチ `wom-v1r6m0_BS-SEAF`、作業ツリーは clean）
- 出力：`output/g5_trial/`（git の対象外）。付録：`docs/development/WOM_BSSEAF_Cosmetics_G5_CIF_Freight_appendix/`
- Python：`C:\Users\ohsug\anaconda3\python.exe` を明示して使った

## 一言で

**`vc_trade_terms.csv`（任意の新しい表）で `seller`・`1`（CIF 型）を宣言した法人間の区間では、海上運賃を売り手の日本本社の「法人間売上に対応する原価」として出荷の週に 1 件計上し、シンガポール販社の取得は法人間価格だけ（運賃 0）にした。化粧品の写しで `E_JP` の運賃の原価 3,367 件・4,848,480 円、`E_SG` のその区間の運賃 0 件。法人別の利益は `E_JP` −4,848,480 円・`E_SG` ＋4,848,480 円（和は同じ）。連結（未実現利益の消去後）の利益とグループの在庫は 1 円も変わらない。表の無いモデル（正式なサンプルを含む）は前と同じ。PPC のコード・正式なサンプル・保護対象のコア・golden は変えていない。**

**追記（段階 6、§9）：大杉さんの決定で、正式なサンプルに表の 2 行を入れた。正式なサンプルの出力は `model_cif` と一致し、法人別の利益が上のとおりに動く。消去後の連結の利益・グループの在庫・PPC との利益の差（0 円）は変わらない。golden は不変。**

## 1. 先に確かめたこと（B1〜B4、T0、コードを変えない）

T0：`python -m tools.valuechain_run --model-dir data/sample/cosmetics-sg-th-2027-2029 --out output/g5_trial/t0`（`18301c5`）。

| # | 見立て | 結果 | 判定 |
|---|---|---|---|
| B1 | 区間の出荷 2028-W25、受入 W27、販売 W30。`E_JP` の法人間の原価（`basis=entity`）46,080 | 出荷 `ship:COS_Cream:OUT:dad:WH_JP_Released:COS_Cream:93:0` 2028-W25 → 受入 W27、店へ W27 → 着 W28、販売 W30。C の行 46,080 | 合う |
| B2 | 区間の運賃が `E_SG` の取得として W25 に 1,440・1 件（`v1,entity,group`） | そのとおり | 合う |
| B3 | 全期間 3,367 件・4,848,480 円、すべて `E_SG` | 3,367 件・4,848,480 円・すべて `E_SG`（1 出荷に 1 件）。全出荷で受入は 2 週後 | 合う |
| B4 | 販売の原価 `entity` 123,648、`group` 49,728 | 123,648・49,728 | 合う |

## 2. 実装（T1）

### 2.1 変えたもの

| ファイル | 中身 |
|---|---|
| `wom/valuechain/masters.py` | `load_trade_terms()` を新設（D1）。`VCMasters.trade_terms`（無ければ空 → 今のまま）と `cif_freight(edge, product)` |
| `wom/valuechain/ledger.py` | `_edge_costs` で CIF 型の区間の運賃（`freight`）だけを `_cif_freight` に回す（D2）。関税・保険・ほかの区間は今のまま |
| `wom/valuechain/policy.py` | docstring の表に 1 行、「第 1 回では扱わない」の注記を直した（`COST_POLICY` の値は変えていない） |
| `wom/valuechain/run.py` | 表があるときだけ `vc_checks.json` に `trade_terms`（宣言の内容と注記） |
| `tests/test_valuechain_trade_terms.py` | 新規 19 件（単体 4・結合 13〔止める条件 12 を含む〕・E2E 2） |
| `tests/conftest.py` | 領域の表に 1 行（`ppc`） |

`views.py`・PPC のコード・正式なサンプル・保護対象のコア・golden は変えていない。

### 2.2 計上のしかた（`_cif_freight`、出荷の週）

| 行 | `kind` | `scope` | `basis` | `entity`・`node`・`counterparty` | 意味 |
|---|---|---|---|---|---|
| 1 | `acquisition` | `internal` | `v1,entity,group` | `E_JP`・`WH_JP_Released`・`E_SG` | 売り手が外部の運賃を負担した（グループの在庫原価に入る） |
| 2 | `cogs` | `intercompany` | `v1` | 同上 | 法人間売上に対応する原価（管理評価） |
| 3 | `cogs` | `intercompany` | `entity` | 同上 | 法人間売上に対応する原価（法人の帳簿） |

- lot の**グループの原価にだけ** 1,440 を足す。受け手の V1・法人の原価には足さない（`E_SG` の取得は価格 120,000 だけ）
- 未実現利益：その出荷の `eliminated` を運賃の分だけ小さくする記録を足す（販社の在庫の U ＝ 120,000 − (C ＋ 1,440) ＝ 72,480）
- 3 行とも `src_id`＝区間の出荷 ID、`family=freight`、`price_type=logistics_cost`、週＝同じ出荷の法人間の売上原価の行と同じ

**依頼書との違い（確認してほしい）**：依頼書は「グループの原価を示す行を 1 行（`kind=acquisition`、`basis=group`）。`entity` などの列は、連結の集計と保存の検査が今と同じ結果になるように選ぶ」としていた。`basis=group` だけの行にすると、保存の検査（法人 × 週で「期首 ＋ 取得（`basis` に `entity`）− 払い出し（`cogs`・`entity`）＝ 期末」）で、`E_JP` に払い出し（行 3）だけがあって取得が無いので、毎週 1,440 円ずつ合わなくなる。そこで、その行を `entity=E_JP`・`basis=v1,entity,group` にした。

- `entity` の部分：`E_JP` の取得と払い出しが同じ週に打ち消し合い、`E_JP` の在庫は増えない。
- `group` の部分：依頼書の「グループの原価に足す」行に当たる。
- `v1` の部分：行 2 と打ち消し合う。

取得の行は V1・V2・V3 の損益の集計には使われない（保存の検査だけが読む）ので、損益への影響は行 2・3 だけになる。

### 2.3 依頼書に無く、私が足したこと

- 止める条件に「`edge_id` に `->` が無い」を足した（G4 と同じ）。物理の区間の確かめは、ローダに渡された製品だけで行う（G4 と同じ作り）。
- `freight_borne_by` が `seller`／`buyer` 以外のとき、`freight_in_price` が `0`／`1` 以外のときは、どちらも「今は表せない組合せ」と同じ止め方にした。

## 3. 照合（V1〜V11）

照合のスクリプト：付録 `check_g5.py`（出力とモデルの CSV を読むだけ。WOM を import しない）。結果：付録 `check_g5_result.json`。写しのモデルの表：付録 `trial_models/`。

```
python -I docs/development/WOM_BSSEAF_Cosmetics_G5_CIF_Freight_appendix/check_g5.py --g5-dir output/g5_trial --out docs/development/WOM_BSSEAF_Cosmetics_G5_CIF_Freight_appendix
```

### 3.1 結果

| # | 期待 | 結果 | 判定 |
|---|---|---|---|
| V1 | `E_JP` の運賃の原価：W25 に `entity` 1 件・1,440（`v1` にも 1 件）・`intercompany`、`src_id` ＝ 区間の出荷 ID。C の行と同じ週。C の `line_id` と内訳の `line_id` | 原価の行 `line_id` 49110（`v1`）・49111（`entity`）、取得の行 49109。C の行 49107（46,080、W25）。C の内訳 47122・47123・47124・47987・48088・48089（仕入 31,200 ＋ 運賃 0 ＋ 関税 0 ＋ 加工 14,400 ＋ 運賃 480 ＋ 関税 0 ＝ 46,080） | 合う |
| V2 | `E_SG` の W25 の取得は 120,000 の 1 件（ほかに関税 0 円の行）。その区間の運賃の取得 0 件。W27 の受入で運賃の追加 0 件 | 120,000（49108）と関税 0（49112）だけ。運賃 0 件・受入の追加 0 件 | 合う |
| V3 | グループの原価：W25 末・W26 末 47,520。W30 の販売の原価（`group`）49,728。運賃を含むのは 1 回 | 47,520・47,520。49,728。区間の運賃の行（`group` を含む）1 件 | 合う |
| V4 | 販売の原価（`entity`）122,208 | 122,208 | 合う |
| V5 | 輸送中の週末で U ＝ 72,480。`vc_unrealized_weekly.csv` の値が全 lot の U の合計と合う | W25 末・W26 末とも 72,480。`E_SG`・輸送中・この区間の 316 の週 × 製品で、全 lot の U（価格 − グループの原価）の合計と一致（ずれ 0） | 合う |
| V6 | `E_JP` の運賃の原価（`entity`）3,367 件・4,848,480。`E_SG` の運賃の取得 0 件。全出荷でちょうど 1 件 | そのとおり。全 3,367 出荷で `E_JP` の原価 `entity` 1・`v1` 1・グループに 1 回・`E_SG` の法人の取得 0。すべて出荷の週 | 合う |
| V7 | 法人別の利益（`vc_v2_weekly.csv` の合計）：`E_JP` −4,848,480、`E_SG` ＋4,848,480、和は同じ | −4,848,480・＋4,848,480。和 631,849,608 で T0 と同じ | 合う |
| V8 | 連結は変わらない（下の §3.2） | 消去後（第 2 回）の列とグループの在庫の列が完全に一致。`vc_ppc_comparison.csv` で動いたのは「原価 合計」と「内部取引の利益（消去前）」の 2 行だけで、どちらも −4,848,480。「費用 運賃」「利益 合計」は同じ。保存の検査はすべて合う | 合う（読み方は §3.2） |
| V9 | `model_buyer` の出力が T0 と同じ（`line_id` を含めて） | 明細（`line_id` を含む）を含む全ファイルが一致。`vc_checks.json` は、表の内容を書いた `trade_terms` の項目を除いて一致 | 合う |
| V10 | `model_cif` を同じ場所で 2 回・別の場所で 1 回、明細が同じ | 明細・在庫・未実現利益・V2 の 4 つとも 3 回一致 | 合う |
| V11 (a) | 正式なサンプル（表なし）で出力が T0 と同じ | `vc_run_info.json` 以外の全ファイルが一致（`vc_shipments.csv.gz` は `plan_id` の列を除いて） | 合う |
| V11 (b) | PPC の出力が T0 とバイト単位で同じ | t1_sample・t1_cif・t1_buyer の `ppc/` 7 ファイルすべて一致 | 合う |
| V11 (c) | golden 全件不変 | `--full` の `test_golden.py` が全件緑。`tests/golden/`・`data/sample/` に差分なし | 合う |

### 3.2 V8 の読み方（大杉さんに見てほしい）

依頼書の V8 は「`vc_v3_weekly.csv` と、`vc_inventory_weekly.csv` の `group_hq`・`group_common` の列が、T0 と完全に同じ」と書いている。一方で同じ V8 の中で「法人の帳簿を使う 2 行（原価 合計・内部取引の利益〔消去前〕）が 4,848,480 円小さくなる」とも書いている。

`vc_v3_weekly.csv` には二種類の列が入っている：

- **消去前（第 1 回）**：外部売上の原価と内部取引の利益を、法人の帳簿（`basis=entity`）で数える
- **消去後（第 2 回）**：グループの原価（`basis=group`）で数える

CIF にすると、運賃は `E_JP` の法人間の原価（出荷の週）に移り、`E_SG` の外部売上の原価（販売の週）から消える。そのため、消去前の列は週がずれる。

| `vc_v3_weekly.csv` の列 | T0 との差 |
|---|---|
| 消去後：`external_cogs_r2_*`・`profit_r2_*`、グループの在庫 `inv_group_*`、未評価 | **完全に同じ**（1 円も動かない） |
| `vc_inventory_weekly.csv` の `group_hq`・`group_common` | **完全に同じ** |
| 消去前：`ic_profit_*`・`external_cogs_*`・`profit_*`（第 1 回） | 18 の週で値が動く。全期間の合計の差は 0。報告の期間（2027-W01 から）の合計は ＋30,240 円：報告の開始の前に出荷し、開始の後に売った lot の運賃が、報告の期間の外の `E_JP` の原価に移ったため。期首の未実現利益の残高の差（1,753,920 → 1,723,680）と同じ額 |
| 未実現利益（`unrealized_*`・`eliminated_hq`・`realized_hq`）、法人の在庫 `inv_entity_*` | 運賃の分だけ小さくなる（依頼書 V5 の期待どおり） |

私は「連結の数字」を**消去後の利益とグループの在庫**と読み、そこが 1 円も動かないことを V8 の合格の条件にした。消去前の列の週のずれは、依頼書が動くと書いた 2 行と同じ原因で生じる。この読み方でよいか確認してほしい（§6.1）。

### 3.3 代表の lot の明細（`model_cif`、主な行）

| 週 | 行 | 法人 | T0 | T1 |
|---|---|---|---:|---:|
| 2028-W25 | 法人間売上 | `E_JP` | 120,000 | 120,000 |
| 2028-W25 | 法人間売上の原価（`entity`、C） | `E_JP` | 46,080 | 46,080 |
| 2028-W25 | 運賃の取得・法人間売上の原価（`v1`・`entity`） | `E_JP` | なし | 1,440・1,440・1,440 |
| 2028-W25 | 法人間の取得 | `E_SG` | 120,000 | 120,000 |
| 2028-W25 | 運賃の取得（`v1,entity,group`） | `E_SG` | **1,440** | **なし** |
| 2028-W27 | DC_SG の加工（受入） | `E_SG` | 1,380 | 1,380 |
| 2028-W27 | 店への運賃 | `E_SG` | 828 | 828 |
| 2028-W30 | 販売の原価 `entity`／`group` | `E_SG` | 123,648／49,728 | **122,208**／49,728 |

全行は付録 `t0_lot_money_lines.csv`・`t1_cif_lot_money_lines.csv`。

### 3.4 管理評価（V1）の変わり方（止める理由ではない）

`vc_v1_weekly.csv` の全期間の利益：`WH_JP_Released`（`E_JP`）−4,848,480 円、`DC_SG` ＋2,377,440 円・`SG_EC` ＋1,085,760 円・`SG_Store` ＋1,385,280 円（いずれも `E_SG`、計 ＋4,848,480 円）。全体の和は同じ。§0 の前提（V1 も法人と同じく、販社の取得は価格だけ）のとおり。

## 4. テスト

| 段 | 結果 |
|---|---|
| 新しいファイル `tests/test_valuechain_trade_terms.py` | 19 passed |
| `python -m tools.quick_check --area ppc` | 210 passed・0 failed（335 秒）。G1・G2・G4 のテストを含む |
| `python -m tools.quick_check --full` | **1,145 passed・3 skipped・0 failed**（1,068 秒）。golden 全件緑 |

G4 のときの文字コードの問題を避けるため、`PYTHONIOENCODING=utf-8` を付けて実行した（ログ `output/g5_trial/quick_check.log`）。

## 5. 合格の条件

| # | 条件 | 判定 |
|---|---|---|
| S1 | B1〜B4 が見立てどおり | 合う（§1） |
| S2 | V1〜V11 | 合う（§3。V8 は §3.2 の読み方で） |
| S3 | テストの追加、`--area ppc`、`--full` が緑、golden 全件不変 | 合う（§4） |
| S4 | 変えたのは `wom/valuechain/`（`policy.py`・`masters.py`・`ledger.py`・`run.py`）とテスト、`tests/conftest.py` の 1 行、報告書と付録だけ | 合う |

止める理由に当たるものは無かった（V8 の読み方は §3.2）。

## 6. 申し送りと、大杉さんに決めてほしいこと

### 6.1 決めてほしいこと

| 一言で | 中身 | 推奨 |
|---|---|---|
| 正式なサンプルに表の 2 行を入れるか（段階 6）→ **入れる（2026-11-12 決定、§9 で実施）** | `data/sample/cosmetics-sg-th-2027-2029/vc_trade_terms.csv` に `model_cif` と同じ 2 行（`WH_JP_Released->DC_SG`、クリーム・美容液、`CIF`・`seller`・`1`）。正式なサンプルの法人別の損益が CIF の前提どおりになる（`E_JP` −4,848,480 円・`E_SG` ＋4,848,480 円）。連結（消去後）の利益・グループの在庫・PPC との利益の差は変わらない。golden は Value Chain を見ないので変わらない見込み | 入れる（金額仮定書の CIF シンガポールと一致する） |
| V8 の読み方 → **この読み方で可（2026-11-12 決定）** | 「連結の数字が変わらない」を、消去後（第 2 回）の利益とグループの在庫で判定した。消去前（第 1 回）の列は法人の帳簿を使うので、週がずれる（全期間の差 0、報告の期間で ＋30,240 円）（§3.2） | この読み方で可とする |

### 6.2 申し送り

1. **取得の行（行 1）を `E_JP` に置いた理由**は §2.2。グループの原価の行を `basis=group` だけにすると、保存の検査が `E_JP` で合わない。
2. **G4 との関係**：同じ `_edge_costs` の中で、G4 は関税の行だけ、G5 は運賃の行だけを分岐する。G4 の課税価格に足す運賃は `ppc_edge_cost_rule.csv` を読むだけなので、G5 で運賃の負担法人を変えても課税価格は変わらない。今のサンプルでは二つの表の区間は重ならない（G4 はタイ、G5 はシンガポール）。
3. **表せない条件**：受入の時に支配が移る契約、売り手負担で価格に含めない別請求、保険。表に書くと読み込みで止まる。
4. PPC は法人を持たないので、照合は全期間の合計（「費用 運賃」4,848,480 円、`vc_ppc_comparison.csv` で同じ）だけ。
5. 運送業者への支払の週、外部請求書の番号は Value Chain では扱わない（計上の週と出荷 ID まで）。

## 7. BS-SEAF の記録

| 項目 | 内容 |
|---|---|
| 始めと終わり | 始め 18:42（依頼書を読み始め）、終わり 19:16。実作業：読む 18:42〜18:44、T0 18:44〜18:45、設計と実装 18:45〜18:47、写し・照合 18:47〜18:49、テスト 18:49〜18:50、報告書 18:50〜18:55、仕上げ 19:14〜19:16。待ち時間：`--area ppc`＋`--full` 18:50〜19:14（その間に報告書を書いた） |
| 人の橋渡し | 無し（依頼書の §0 で判断はすべて済んでいた） |
| 再利用した知識 | G4 の照合スクリプト `check_g4.py` と `vc_shipments.csv.gz` の `plan_id` の扱い、G4 のローダの作り（物理の区間の確かめ方、`->` の確かめ）、G4 で分かった `quick_check` の文字コードの対策（`PYTHONIOENCODING=utf-8`）、G2 の合成の木のテスト |
| 迷った所・足りなかった情報 | (1) **グループの原価を示す行の `entity`・`basis`**：依頼書は「`basis=group`、ほかの列は検査が今と同じになるように選ぶ」だったが、`basis=group` だけでは保存の検査が合わない。`E_JP`・`v1,entity,group` にした（§2.2）。(2) **V8**：「`vc_v3_weekly.csv` が T0 と完全に同じ」と「法人の帳簿を使う 2 行が動く」が、同じファイルの中で両立しない（第 1 回の列は法人の帳簿を使う）。消去後の列で判定した（§3.2）。業務定義・共通照合表は第 1 回と第 2 回の区別に触れていない。(3) 未実現利益の記録をどの事象で直すか（依頼書は「`transfer_out`・`transfer_in`・`eliminated` など」）：運賃は `E_JP` の法人間の利益を減らすので、`eliminated` を運賃の分だけ減らした。業務定義 §3 の「内部利益 120,000 − (C ＋ 1,440)」と同じ。(4) 業務定義の週の例（W28・W29・W31）と実際の記録（W25・W27・W30）の違いは、依頼書 §2 に読み替えが書いてあり迷わなかった |

## 8. commit

commit メッセージの下書き：`commit_msg208.txt`（段階 6 も含む）。git の操作は大杉さんが行う。

## 9. 段階 6（追記、2026-11-12）

大杉さんの決定（「Yes, accept it」＝ V8 の読み方を可、段階 6 を進める）で、正式なサンプルに表の 2 行を入れた。

### 9.1 変えたもの

| ファイル | 中身 |
|---|---|
| `data/sample/cosmetics-sg-th-2027-2029/vc_trade_terms.csv`（新規） | `model_cif` と同じ 2 行（`WH_JP_Released->DC_SG`、クリーム・美容液、`CIF`・`seller`・`1`）。`note` は根拠の文に直した（モデルの仮定で証憑では未確認）。カンマは使っていない（G4 段階 6 の教訓） |
| `data/sample/cosmetics-sg-th-2027-2029/README.md` | 金額の規則の一覧に表を追加、表の説明の段落、既知の限界の「G5」を解決済みに |
| `tests/test_valuechain_trade_terms.py` | 正式なサンプルに表がある前提に直した：表を除いた写しを作るヘルパー、`test_d1_no_file_is_empty` は写しで、正式なサンプルの 2 行の読み込み（新規）、正式なサンプルの E2E（新規：`E_JP` の運賃の原価 3,367 件・4,848,480 円、`E_SG` の運賃 0、消去後の利益 631,119,240 円）、表を除いた写しの E2E（前の「正式なサンプルは今のまま」）。21 件 |

コード・PPC・golden・保護対象のコアは変えていない。

### 9.2 確かめたこと

| 確かめたこと | 結果 |
|---|---|
| 正式なサンプルの Value Chain の出力 ＝ T1 の `model_cif` の出力 | `vc_run_info.json` 以外の全 17 ファイルが一致（`vc_shipments.csv.gz` は `plan_id` の列を除いて一致。`vc_checks.json` は `trade_terms` を含めて一致：記録は `note` を持たない）（`output/g5_trial/s6_sample`） |
| PPC の出力 ＝ T0 | `ppc/` の 7 ファイルすべてバイト一致 |
| PPC との利益の差（消去前） | 0 円のまま（PPC・台帳とも 631,849,608 円）。「費用 運賃」の差は G1 の配送・梱包 6,243,120 円だけ（前と同じ） |
| 保存の検査・未実現利益 | 合う。issues 0。消去前 629,395,560 円・消去後 631,119,240 円、期首の未実現利益 1,723,680 円（`model_cif` と同じ） |
| テスト | 新しいファイル 21 passed。`quick_check --area ppc,golden` 231 passed・0 failed（478 秒）。`tests/golden/` に差分なし |

### 9.3 気づいたこと

- README の「Value Chain（業務の要求は未完了）」の見出しと「法人別・連結の損益が業務の要求を満たしたとは判定していない」の文は、G1〜G5 がすべて解決済みになった今も残っている。判定は大杉さん・GPT 君の役割なので直していない。
- `--area ppc,golden` のログに、子プロセスの出力を cp932 で読めないという pytest の警告が 2 件出る（テストの結果には影響しない。G4 のときも同じ）。
