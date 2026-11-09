---
handoff:
  case_id: BSSEAF-COS-G2
  task_id: G2-T1-T2-distributor-mdf
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: a620191
  knowledge_used:
    - id: G2 業務定義案（GPT-MC）
      version: v0.1
      applicability: "§1 適用範囲、§3 算定と計上週（案 A）、§4 代表 1 ロットと判定の例、§5 照合。大杉さんが 2 件とも採用（2026-11-09）"
    - id: G2 対応表（Claude君）
      version: v0.1
      applicability: "§1 事実 F1〜F9、§3 最小の改修 D1〜D4、§4 試行 T0〜T2、§6 の判断（2 件とも推奨どおり採用）"
    - id: G1 報告書
      version: "2026-11-08"
      applicability: "vc_sales_cost_rule.csv の読み込み・計上・突き合わせ（C1〜C4）の作り、照合のスクリプト check_g1.py の作り"
  acceptance:
    ref: "この依頼書 §6"
  evidence:
    - docs/design/drafts/WOM_G2_Distributor_MDF_Business_Definition_v0.1.md
    - requests/BSSEAF_Cosmetics_G2_MDF_Mapping_v0.1.md
  status: "試行可能"
  open_items: []
  stop_reasons: []
  handover_notes:
    - "案 B（販促の実施・承認で確定）と、売上の割戻しとして扱う契約は作らない（大杉さん 2026-11-09）"
  next: implement
---

# Request Letter：G2（代理店向けの販促協賛金、MDF）を Value Chain で計上する（検証 T0・T1、実装 T2）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-11-09）
- 版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`（ブランチ `wom-v1r6m0_BS-SEAF`。着手時の SHA を報告書に記録する）
- 前提：G2 業務定義案 v0.1（GPT-MC）、G2 対応表 v0.1（Claude君）、大杉さんの判断（2026-11-09、業務定義の 2 件と対応表の 2 件をすべて採用）
- 範囲：
  - Part A（T0・T1）：**検証だけ**。コードを変えない。モデルの写しで行う。
  - Part B（T2）：**Value Chain の改修**（`wom/valuechain/` と、そのテスト）。保護対象のコアには触れない。**PPC のコードと、正式なサンプル・golden は変えない**。試行はモデルの写しで行う
- 出力：`output/g2_trial/` の下（git の対象外）

---

## 一言で

**外部の代理店への卸売の週に、その卸売額の 5% を、売り手の自社法人の販促費（MDF）として 1 件ずつ計上できるようにしてください。G1 の費目の表 `vc_sales_cost_rule.csv` を、外部の代理店の leaf にも使えるように広げます。PPC は変えずに、照合の相手として使います。**

## 0. 大杉さんの判断（2026-11-09）

| 一言で | 中身 |
|---|---|
| 初回は、卸売が成立した週に負担も確定すると置く | 業務定義の案 A。代表の lot は 2028-W28（DC の出荷の週）に 1 件 |
| 税抜の卸売額の 5% を販促費として試算する | 取引通貨で計算し、負担 1 件の金額を小数第 3 位で四捨五入して小数第 2 位まで |
| G2 の費目は G1 と同じ表に書く | `vc_sales_cost_rule.csv` に費目 `distributor_mdf` を足し、外部の代理店の leaf にも使えるようにする（§4 の D1〜D3） |
| 黙って落ちる売上比率の費用は、一覧に出す | 外部の代理店の leaf に PPC の売上比率の行があり、表に行が無いとき issues に出す（§4 の D4） |

## 1. 業務の期待（業務定義 §4 の当てはめ）

| lot | 週 | 負担法人 → 受取先 | 計算 | 金額 |
|---|---|---|---|---:|
| SG `COS_Cream:SG_Distributor:2028-W29:00002` | 2028-W28（DC_SG の出荷・卸売） | `E_SG` → `EXT_CH_SG_DIST` | 24 × 62 ＝ 1,488.00 SGD × 5% | **74.40 SGD**（1 件） |
| 同 | 2028-W29（代理店の受入・代理店の出荷） | — | — | 0（追加 0 件） |
| TH `COS_Cream:TH_Distributor:2029-W03:00003` | 2029-W02（DC_TH の出荷・卸売） | `E_JP` → `EXT_CH_TH_DIST` | 24 × 1,600 ＝ 38,400 THB × 5% | **1,920.00 THB**（1 件） |
| 同 | 2029-W03 | — | — | 0（追加 0 件） |

全期間：外部卸売 2,340 件（SG 1,651・TH 689）に 1 件ずつ、合計 **22,196,148 円**（SG クリーム 6,451,224・SG 美容液 9,160,164・TH クリーム 2,583,360・TH 美容液 4,001,400）。出どころ：G3 検証の付録 `verify_g3_result.json` の A1・A5（外部卸売 443,922,960 円）× 5%。

## 2. 先に確かめること

| # | 確かめること | 違ったら |
|---|---|---|
| B1 | 代表の 2 lot の卸売の週と金額（SG：2028-W28・1,488.0 SGD・`src_id`＝`ship:COS_Cream:OUT:dad:DC_SG:COS_Cream:96:6`。TH：2029-W02・38,400 THB） | 止めて報告 |
| B2 | 正式なサンプルで、MDF の行（`price_type` が MDF に当たる行）が Value Chain の明細に 0 件で、issues にも出ていないこと（対応表 F4 の見立て） | 止めて報告（F4 の見立てが違う） |
| B3 | `vc_ppc_comparison.csv` の利益の差（Value Chain − PPC）が 22,196,148 円 | 止めて報告 |

## 3. Part A：検証（コードを変えない）

| 段 | 中身 | 合格 |
|---|---|---|
| T0 | 正式なサンプルで Value Chain を実行（`python -m tools.valuechain_run --model-dir data/sample/cosmetics-sg-th-2027-2029 --out output/g2_trial/t0`）。PPC も既定どおり出す | B1〜B3 を記録。代表の 2 lot の明細を表にする |
| T1 | サンプルを `output/g2_trial/model_t1/` に写し、`ppc_edge_cost_rule.csv` の既存の 4 行の `fixed_amount` を書き換える：`DC_SG->SG_Distributor` の COS_Cream 0.3 → 3.4、COS_Serum 0.3 → 4.0、`DC_TH->TH_Distributor` の COS_Cream 8 → 88、COS_Serum 8 → 103（それぞれ卸価格の 5% を足した額）。**行は足さない**（同じ区間・同じ種類の行を 2 行書くと読み込みで止まる）。Value Chain を実行 | (1) その区間の販売費の行（`kind=expense`・`scope=selling`、`price_type=logistics_cost`）が、T0 より代表の SG の lot で 74.40 SGD、TH の lot で 1,920 THB 増え、どちらも卸売の週の 1 件のまま。(2) 全期間の増加は 2,340 件・22,196,148 円。(3) その行の額を除くと、明細は T0 と同じ。**PPC の出力は比べない**（PPC も区間の行を読むので変わる） |

T1 が合格したら Part B に進む。止める理由に当たったら、Part B に進まずに報告する。

## 4. Part B：実装（差分だけ）

### 4.1 D1：費目を一つ足す

`policy.py` の `SALES_COST_ITEMS` に `"distributor_mdf": "代理店向け販促協賛費（MDF）"` を足す。docstring の表に 1 行（「外部の代理店への卸売の売上比率の費用（vc_sales_cost_rule.csv の external の leaf）：売り手の、卸売の週の販売費」）。

### 4.2 D2：表を外部の代理店の leaf にも使えるようにする

`masters.load_sales_cost_rule` の検査を次のように分ける（違えば `MasterError`）：

| ノードの種類（`vc_node_assignment.csv`） | 受け付ける費目 | 通貨の検査 |
|---|---|---|
| `own`・`online`（法人がグループ）：今のまま | `distributor_mdf` 以外 | 市場価格（`ppc_market_price.csv`）の通貨と同じ（今のまま） |
| `external`（法人が `external_channel`）：**新しく受け付ける** | `distributor_mdf` だけ | その leaf に入る区間の卸価格（`vc_price_rule.csv`、`price_type=wholesale`）の通貨と同じ。卸価格の行が無ければ止める |

PPC の行との突き合わせ（C4）は、どちらにも今の規則をそのまま使う（外部の leaf では `marketing_cost` の率 0.05 ＝ 表の 0.05、固定額 0 ＝ `<leaf>->CONSUMER` の行なし）。docstring を直す。

写しのモデル（`output/g2_trial/model_t2/`）の `vc_sales_cost_rule.csv` に足す 4 行（G1 の 10 行はそのまま）：

```
SG_Distributor,COS_Serum,distributor_mdf,marketing_cost,revenue,0.05,SGD,代理店向け販促協賛費 5%（負担：シンガポール販社）
SG_Distributor,COS_Cream,distributor_mdf,marketing_cost,revenue,0.05,SGD,代理店向け販促協賛費 5%（負担：シンガポール販社）
TH_Distributor,COS_Serum,distributor_mdf,marketing_cost,revenue,0.05,THB,代理店向け販促協賛費 5%（負担：日本本社）
TH_Distributor,COS_Cream,distributor_mdf,marketing_cost,revenue,0.05,THB,代理店向け販促協賛費 5%（負担：日本本社）
```

### 4.3 D3：卸売の週に計上する

`ledger.py` の `_transfer`、外部への販売（`scope=external`）で `ptype == "wholesale"` の売上の行（と原価の行）の後に、受け手の leaf（`s.to`）の表の行ごとに 1 行：

- 金額 ＝ `rate` × その卸売の売上の金額（卸価格 × 個数）を、取引通貨で**小数第 2 位に四捨五入**（`Decimal` の `ROUND_HALF_UP`）。卸売額が未評価（NaN）なら NaN
- `kind=expense`、`scope=selling`、`basis`＝`ALL`、`family`＝`ppc_cost_type`（`marketing_cost`）、`price_type`＝`cost_item`（`distributor_mdf`）
- `entity`＝売り手（`E_SG`・`E_JP`）、`node`＝売り手の出荷ノード（`s.phys_from`：`DC_SG`・`DC_TH`。今の区間の販売費と同じ）、`counterparty`＝受け手の法人（代理店）、`src_id`＝卸売の出荷 ID、`lot_id`＝その lot
- `note`：`販促の対象：<leaf>`
- 週 ＝ 卸売の週（出荷の週）

代理店の受入（`_receipt`）と、代理店から消費者への観測の販売（`_consumer` の観測の分岐）では、この表の行を**使わない**（今の作りでそうなっていることを、テストで固定する）。

### 4.4 D4：黙って落ちないようにする

外部チャネルの leaf（`channel_type=external`）に、`ppc_node_cost_rule.csv` の `basis=revenue` の行があり、表に同じノード・SKU の行が無いときは、issues に `revenue_based_cost_on_external_channel_not_booked` を**ノード・SKU・種類ごとに 1 件**出す（`node`・`product`・`cost_type`・入荷の数を添える）。表があれば出さない。置き場所（読み込みの後か、実行の終わりか）は、今の issues の作りに合わせて決めてよい。

### 4.5 テスト

- 単体・結合：`tests/test_valuechain_sales_cost.py` に足すか、新しいファイル `tests/test_valuechain_distributor_mdf.py`（足すなら `tests/conftest.py` の領域の表に `ppc` で 1 行）。中身：D2 の検査（external の leaf で `distributor_mdf` 以外は止まる、直販の leaf で `distributor_mdf` は止まる、卸価格の通貨と違えば止まる、卸価格が無ければ止まる）、D3 の行の属性・金額・週、卸価格なしで NaN、丸め（端数の出る合成の値で四捨五入）、代理店の受入と観測の販売で行が立たないこと、D4（表なしで 4 件、表ありで 0 件）、化粧品の写しでの E2E（代表 2 lot・合計 22,196,148）。
- G1 のテストが今のまま通ること。
- `python -m tools.quick_check --area ppc`、最後に `--full` を 1 回。golden は全件不変。

## 5. T2 の照合

`model_t2`（正式なサンプルの写し ＋ 表に 4 行）で Value Chain を同じ場所に 2 回、別の場所に 1 回実行する。照合は付録の照合のスクリプト（出力とモデルの CSV を読むだけ。WOM を import しない。G1 の `check_g1.py` の作りに倣う）。

| # | 照らすこと | 期待 |
|---|---|---|
| V1 | 代表の SG の lot の MDF の行 | 2028-W28 に 1 件、74.40 SGD、`entity=E_SG`・`node=DC_SG`・`counterparty=EXT_CH_SG_DIST`、`src_id` ＝ 卸売の出荷 ID。2028-W29 に 0 件 |
| V2 | 代表の TH の lot の MDF の行 | 2029-W02 に 1 件、1,920.00 THB、`entity=E_JP`・`counterparty=EXT_CH_TH_DIST`。円の額も記録。2029-W03 に 0 件 |
| V3 | 全部の外部卸売（2,340 件） | 卸売の出荷 ID × `distributor_mdf` で、すべてちょうど 1 行。外部卸売以外から立った MDF の行 0 |
| V4 | 金額と週 | すべて「卸売の行の金額 × 0.05」（小数第 2 位）と一致、通貨も一致、週は卸売の行と同じ |
| V5 | 全期間の MDF の合計 | **22,196,148 円**（SKU・区間ごとの内訳も §1 と一致） |
| V6 | PPC との照合 | `vc_ppc_comparison.csv` の利益の差（Value Chain − PPC）が **0 円**。PPC の代理店の `marketing_cost` の全期間の合計 ＝ Value Chain の MDF の合計（円）。週は PPC が 1 週遅いので、週ごとの一致は求めない（差があれば週の対応を表にする） |
| V7 | issues | D4 の issue は model_t2 で 0 件。表の 4 行を取り除いた写しで 4 件。ほかの issues は T0 と同じ |
| V8 | 再計算 | 同じ場所の 2 回目、別の場所の実行とも、明細が同じ |
| V9 | 変わってはいけないもの | (a) model_t2 の明細から MDF の行を除き、`line_id` の列を除くと、T0 の明細と同じ（行が増えると `line_id` の番号がずれるため）。(b) 正式なサンプル（表に MDF の行が無い）での Value Chain の出力は、issues に D4 の 4 件が加わる以外は T0 と同じ。(c) PPC の出力は T0 とバイト単位で同じ。(d) golden |

## 6. 合格の条件

| # | 条件 |
|---|---|
| S1 | B1〜B3 の記録。どれも見立てどおり |
| S2 | T1 の (1)〜(3) |
| S3 | V1〜V9 |
| S4 | テスト：単体・結合の追加、`--area ppc`、`--full` が緑。golden 全件不変 |
| S5 | 変えたのは `wom/valuechain/`（`policy.py`・`masters.py`・`ledger.py`、必要なら `run.py`）とテスト、`tests/conftest.py` の 1 行（足したとき）、報告書と付録だけ。PPC のコード・正式なサンプル・保護対象のコアは変えない |

**止める理由**：B1〜B3 が違う、T1 で増える額か件数が合わない、V3 で 1 行でない卸売がある、V5 の合計が合わない、V6 で利益の差が 0 にならない、V9 (a)・(c) が合わない、golden が変わる。

**止める理由ではないもの**：V6 で週ごとの値が合わない（PPC は代理店の leaf の出荷の週＝1 週遅い週に立てる。全期間の合計が合えばよい）。`vc_ppc_comparison.csv` の費目の分け方の違い（G1 の申し送り 2 と同じ。合計が合えばよい）。

## 7. 報告書と記録

- 報告書：`docs/development/WOM_BSSEAF_Cosmetics_G2_DistributorMDF_Report.md`、付録 `..._appendix/`（照合のスクリプトと結果、代表の 2 lot の明細、`model_t2` に足した表の写し）。冒頭に引き継ぎの欄（YAML、`next: owner`）。
- 中身：着手時の SHA、B1〜B3、T0・T1・T2 の結果、S1〜S5、止める理由と申し送り、大杉さんに決めてほしいこと（一言の決定と中身、推奨）。少なくとも次を決める事項として書く：**正式なサンプルに表の 4 行を入れるか**（段階 6。入れると、正式なサンプルの Value Chain と PPC の利益の差が 0 円になる見込み）。
- BS-SEAF の記録：始めと終わりの時刻（実作業と待ち時間を分ける）、人の橋渡し（転記・連絡／git の操作／業務の判断／レビューへの対応）、再利用した知識。**業務定義（GPT-MC）・対応表（Claude君）・この依頼書の三つで、迷った所や足りない情報があったか**。
- commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-09 | 初版 |
