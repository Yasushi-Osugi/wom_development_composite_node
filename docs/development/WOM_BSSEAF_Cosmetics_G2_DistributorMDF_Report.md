---
handoff:
  case_id: BSSEAF-COS-G2
  task_id: G2-T1-T2-distributor-mdf
  role_from: implement         # Code君
  role_to: owner               # 大杉さん
  target_commit: 9eefff8
  request: requests/RequestLetter_BSSEAF_Cosmetics_G2_MDF_to_CodeKun.md
  acceptance:
    S1: pass
    S2: pass
    S3: pass
    S4: pass
    S5: pass
  evidence:
    - docs/development/WOM_BSSEAF_Cosmetics_G2_DistributorMDF_appendix/check_g2.py
    - docs/development/WOM_BSSEAF_Cosmetics_G2_DistributorMDF_appendix/check_g2_result.json
  status: "実装済み。段階 6（正式なサンプルに 4 行）と run.py の注記も済み（§8）"
  stop_reasons: []
  open_items: []
  next: owner
---

# 報告書：G2（代理店向けの販促協賛金、MDF）を Value Chain で計上する（T0・T1 検証、T2 実装）

- 依頼書：`requests/RequestLetter_BSSEAF_Cosmetics_G2_MDF_to_CodeKun.md`（v0.1）
- 作業：Code君（Claude Code、Windows）、2026-11-12
- 着手時の SHA：`9eefff8fee8d3807f6f5adffb254fd53b6f92e2d`（ブランチ `wom-v1r6m0_BS-SEAF`）。着手時点で `docs/design/WOM_BSSEAF_MultiAI_Loop_Design_v0.1.md` と `requests/BSSEAF_Roadmap_Loop_Ledger_v0.1.md` に未コミットの変更があった（私の変更ではない。触っていない）
- 出力：`output/g2_trial/`（git の対象外）。付録：`docs/development/WOM_BSSEAF_Cosmetics_G2_DistributorMDF_appendix/`

## 一言で

**外部の代理店への卸売の週に、卸売額の 5% を売り手の自社法人の販促費（`distributor_mdf`）として 1 件ずつ計上できるようにした。化粧品の写し（表に 4 行）で 2,340 件・22,196,148 円、PPC との利益の差は 22,196,148 円 → 0 円。正式なサンプルは変えていない（表に行が無いので、Value Chain の明細は前と同じで、issues に「計上されない PPC の行」が 4 件出るようになった）。**

**追記（段階 6、§8）：大杉さんの決定で、正式なサンプルに表の 4 行を入れた。正式なサンプルでも MDF が 2,340 件・22,196,148 円計上され、PPC との利益の差は 0 円、D4 の issue は 0 件。`vc_checks.json` の注記も直した。**

## 1. 先に確かめたこと（B1〜B3、T0）

T0：`python -m tools.valuechain_run --model-dir data/sample/cosmetics-sg-th-2027-2029 --out output/g2_trial/t0`（改修前のコード）。

| # | 見立て | 結果 | 判定 |
|---|---|---|---|
| B1 | SG：2028-W28・1,488.0 SGD・`src_id`＝`ship:COS_Cream:OUT:dad:DC_SG:COS_Cream:96:6`。TH：2029-W02・38,400 THB | SG：2028-W28・1,488.0 SGD・同じ `src_id`。TH：2029-W02・38,400.0 THB（`src_id`＝`ship:COS_Cream:OUT:dad:DC_TH:COS_Cream:122:2`） | 合う |
| B2 | MDF の行が明細に 0 件、issues にも出ていない | 代理店のノード・`marketing_cost` の行 0 件、issues `[]` | 合う（F4 の見立てどおり、黙って落ちていた） |
| B3 | 利益の差（Value Chain − PPC）が 22,196,148 円 | 22,196,148.0 円（`費用 販促` の行の差 −22,196,148 がそのまま利益の差） | 合う |

外部卸売は 2,340 件（`price_type=wholesale` の売上の行）。

### 代表の 2 lot（T0 の明細、卸売の週の行）

| lot | 週 | 行 | 金額 |
|---|---|---|---:|
| SG `COS_Cream:SG_Distributor:2028-W29:00002` | 2028-W28 | 売上（wholesale、E_SG → EXT_CH_SG_DIST） | 1,488.00 SGD（171,120 円） |
| 同 | 2028-W28 | 販売費 運賃（DC_SG→SG_Distributor） | 7.20 SGD |
| 同 | 2028-W29 | 観測の販売（代理店 → 消費者） | 1,488.00 SGD（グループの売上ではない） |
| TH `COS_Cream:TH_Distributor:2029-W03:00003` | 2029-W02 | 売上（wholesale、E_JP → EXT_CH_TH_DIST） | 38,400 THB（172,800 円） |
| 同 | 2029-W02 | 販売費 運賃（DC_TH→TH_Distributor） | 192 THB |
| 同 | 2029-W03 | 観測の販売 | 38,400 THB |

全行は付録 `t0_SG_Distributor_lot_money_lines.csv`・`t0_TH_Distributor_lot_money_lines.csv`。

## 2. T1（コードを変えない検証）

`output/g2_trial/model_t1/`：正式なサンプルの写しで、`ppc_edge_cost_rule.csv` の既存の 4 行の `fixed_amount` だけを書き換えた（SG クリーム 0.3→3.4、SG 美容液 0.3→4.0、TH クリーム 8→88、TH 美容液 8→103）。行は足していない。

| # | 合格の条件 | 結果 | 判定 |
|---|---|---|---|
| (1) | 代表の SG の lot +74.40 SGD、TH の lot +1,920 THB、どちらも卸売の週の 1 件のまま | SG 7.20 → 81.60 SGD（2028-W28、1 件）、TH 192 → 2,112 THB（2029-W02、1 件） | 合う |
| (2) | 全期間の増加 2,340 件・22,196,148 円 | 増えた行 2,340、増加 22,196,148.0 円 | 合う |
| (3) | その行の額を除くと明細は T0 と同じ | ほかの行はすべて同じ。運賃の行も額の列以外は同じ | 合う |

→ 業務の期待（卸売の週に 1 件、5%）は、今の台帳の作り（区間の販売費の行）で再現できることを確かめた。Part B へ進んだ。

## 3. T2（実装）

### 3.1 変えたもの

| D | ファイル | 中身 |
|---|---|---|
| D1 | `wom/valuechain/policy.py` | `SALES_COST_ITEMS` に `distributor_mdf`（代理店向け販促協賛費（MDF））。外部の代理店の leaf の費目の一覧 `EXTERNAL_SALES_COST_ITEMS = ("distributor_mdf",)`。docstring の表に 1 行 |
| D2 | `wom/valuechain/masters.py` | `load_sales_cost_rule` の検査を leaf の種類で分けた（下の表）。引数 `price_rules`（既定 None）を足した。各行の辞書に `external`（外部の代理店の leaf なら True）。C4 はどちらにも今の規則 |
| D3 | `wom/valuechain/ledger.py` | `_transfer` の外部への卸売（`scope=external`・`ptype=wholesale`）で、売上と原価の行の後に `_distributor_sales_costs` を呼ぶ。受け手の leaf の表の行（`external` の行）ごとに 1 行。`_consumer` は `external` の行を使わない |
| D4 | `wom/valuechain/ledger.py` | 外部チャネルの leaf（`channel_type=external`）に `ppc_node_cost_rule.csv` の `basis=revenue` の行があり、表の行が無いとき、`run()` の終わりに issues `revenue_based_cost_on_external_channel_not_booked` をノード・SKU・種類ごとに 1 件（`receipts`＝その leaf の入荷の数） |
| — | `tests/test_valuechain_distributor_mdf.py`（新規）、`tests/conftest.py`（`ppc` で 1 行） | 下の §3.3 |

`run.py`・PPC のコード・正式なサンプル・保護対象のコアは変えていない。

D2 の検査（違えば `MasterError`）：

| ノードの種類 | 受け付ける費目 | 通貨 |
|---|---|---|
| `own`・`online`（法人がグループ） | `distributor_mdf` 以外（`distributor_mdf` は「only for an external distributor leaf」で止める） | 市場価格の通貨（今のまま） |
| `external`（法人が `external_channel`） | `distributor_mdf` だけ（ほかは「is for a direct-sales leaf … external distributor leaf」で止める） | その leaf に入る区間の卸価格（`vc_price_rule.csv`、`wholesale`）の通貨。卸価格の行が無ければ止める |
| それ以外 | 止める（今の文言＋外部の代理店の leaf の説明） | — |

D3 の行：金額 ＝ `Decimal(rate) × Decimal(卸売額)` を `ROUND_HALF_UP` で小数第 2 位（取引通貨）。卸売額が NaN なら NaN（未評価）。`kind=expense`・`scope=selling`・`basis=v1,entity,group`・`family=marketing_cost`・`price_type=distributor_mdf`・`entity`＝売り手・`node`＝`s.phys_from`・`counterparty`＝代理店の法人・`src_id`＝卸売の出荷 ID・`note`＝`販促の対象：<leaf>`・週＝卸売の週。

### 3.2 照合（V1〜V9）

`output/g2_trial/model_t2/`＝正式なサンプルの写し ＋ `vc_sales_cost_rule.csv` に 4 行（付録 `model_t2_added/vc_sales_cost_rule.csv`）。`t2` に 2 回（1 回目を `t2_first` に写した）、別の場所 `other_place/t2_b` に 1 回。照合は付録 `check_g2.py`（出力とモデルの CSV を読むだけ、WOM を import しない）、結果は `check_g2_result.json`。

| # | 期待 | 結果 | 判定 |
|---|---|---|---|
| V1 | SG の lot：2028-W28 に 1 件、74.40 SGD、E_SG・DC_SG・EXT_CH_SG_DIST、`src_id`＝卸売の出荷 ID。2028-W29 に 0 件 | そのとおり | 合う |
| V2 | TH の lot：2029-W02 に 1 件、1,920.00 THB、E_JP・EXT_CH_TH_DIST。2029-W03 に 0 件 | そのとおり。円の額 8,640 円（node＝DC_TH） | 合う |
| V3 | 外部卸売 2,340 件にちょうど 1 行。卸売以外から立った MDF 0 | 卸売 2,340、MDF 2,340、ちょうど 1 行 2,340、卸売以外 0 | 合う |
| V4 | 金額＝卸売額 × 0.05（小数第 2 位）、通貨・週が卸売と同じ | 不一致 0・0・0 | 合う |
| V5 | 合計 22,196,148 円、内訳が §1 と一致 | 22,196,148.0 円。SG クリーム 6,451,224・SG 美容液 9,160,164・TH クリーム 2,583,360・TH 美容液 4,001,400 | 合う |
| V6 | 利益の差 0 円。PPC の代理店の `marketing_cost` の合計 ＝ MDF の合計 | 利益の差 0.0 円。PPC 22,196,148.0 円 ＝ Value Chain 22,196,148.0 円 | 合う |
| V7 | D4 の issue：model_t2 で 0 件、表の 4 行なしで 4 件、ほかの issues は T0 と同じ | 0 件／4 件（入荷 SG クリーム 754・SG 美容液 897・TH クリーム 299・TH 美容液 390、計 2,340）／ほかの issues はどちらも `[]`（T0 と同じ） | 合う |
| V8 | 同じ場所の 2 回目、別の場所とも明細が同じ | 明細（gz を解いた中身）の SHA-256 が 3 つとも一致 | 合う |
| V9 (a) | model_t2 の明細から MDF の行と `line_id` を除くと T0 と同じ | 同じ | 合う |
| V9 (b) | 正式なサンプル（改修後のコード、`t0_after`）の出力は issues の D4 の 4 件以外 T0 と同じ | 明細の SHA-256 一致、`vc_checks.json` は D4 の 4 件を除けば一致、ほかの 11 の出力ファイルはバイト単位で一致 | 合う |
| V9 (c) | PPC の出力は T0 とバイト単位で同じ | `ppc/` の 7 ファイルすべて一致 | 合う |
| V9 (d) | golden | `--full` の結果は §3.3 | §3.3 |

V6 の週：PPC は代理店の leaf の出荷の週（卸売の週の 1 週後）に立てる。Value Chain の MDF を 1 週後ろにずらすと、PPC の 520 のセル（ノード × SKU × 週）すべてで額が一致した（同じ週のままだと 512 セルが一致。一定の需要の週が続くため偶然一致する所がある）。止める理由ではない（依頼書 §6）。

正式なサンプルの CSV は、作業の前後で中身が同じ（改行を正規化した SHA-256 を `git show HEAD:` と比較、28 ファイル）。

### 3.3 テスト

- 新規 `tests/test_valuechain_distributor_mdf.py`（18 件）：D3 の行の属性・金額・週と V3 の利益への効き、代理店の受入と観測の販売では立たないこと、卸価格なしで NaN、四捨五入（0.0065→0.01、0.015→0.02、0.255→0.26 など 5 通り）、`external` でない行は卸売で使わない、D4（表なしで 1 件・`receipts`、表ありで 0 件）、D2 の検査（読み込める・外部の leaf でほかの費目・直販の leaf で `distributor_mdf`・通貨の違い・卸価格なし・C4 の率のずれ）、化粧品の写しの E2E（代表 2 lot・2,340 件・22,196,148 円・利益の差 0）、正式なサンプルで D4 の 4 件。
- G1 の `tests/test_valuechain_sales_cost.py`（18 件）は変えずに通る（合わせて 36 passed）。
- `python -m tools.quick_check --area ppc`：163 passed（273 秒）。
- `python -m tools.quick_check --full`：1,098 passed・3 skipped・0 failed（1,028 秒）。golden を含めて全件緑（golden は不変）

## 4. 合格の条件

| # | 条件 | 判定 |
|---|---|---|
| S1 | B1〜B3 が見立てどおり | 合格 |
| S2 | T1 の (1)〜(3) | 合格 |
| S3 | V1〜V9 | 合格（V9 (d) は S4） |
| S4 | テストの追加、`--area ppc`、`--full` が緑、golden 全件不変 | 合格 |
| S5 | 変えたのは `wom/valuechain/`（`policy.py`・`masters.py`・`ledger.py`）・テスト・`tests/conftest.py` の 1 行・報告書と付録だけ | 合格（`run.py` も変えていない） |

止める理由には当たらなかった。

## 5. 申し送り

1. **`vc_checks.json` の `sales_cost_rule` の注記**（`run.py`）は「販売の週に計上」のまま。表に外部の代理店の行が入ると `rows` は 14 になり、MDF は卸売の週に計上される。注記を直すかは段階 6 のときに（今回 `run.py` は変えない判断）。
2. **`vc_ppc_comparison.csv` の費目の分け方**：model_t2 では `費用 販促` の差が 0 になり、残る差は G1 から続く `運賃 +6,243,120`／`SGA −6,243,120`（配送・梱包の分け方の違い）だけ。合計は 0。
3. **D4 の issue の数え方**：`receipts` は、その leaf への入荷の数（lot の記録が届いた回数）。表がある leaf では出さない。外部チャネルの leaf の `basis=revenue` 以外（qty の行など）は、今までどおり観測の在庫として扱い、issues にも出さない（今回の範囲外）。
4. `check_g2.py` の作業メモ：PPC の `ppc_event_ledger.csv` の `amount_base` は 1 個当たり（`amount_per_unit_base` と同じ値）で、合計は × `qty`。最初に `amount_base` をそのまま足して 203,892 円となり、取り違えに気づいて直した。

## 6. 大杉さんに決めてほしいこと

| 一言で | 中身 | 推奨 |
|---|---|---|
| **正式なサンプルに表の 4 行を入れるか（段階 6）** | `data/sample/cosmetics-sg-th-2027-2029/vc_sales_cost_rule.csv` に §3.2 の 4 行を足す。入れると、正式なサンプルの Value Chain の利益が 22,196,148 円減り、PPC との利益の差が 0 円になる（model_t2 で確かめた）。D4 の 4 件の issue は消える。PPC・golden は変わらない（golden は Value Chain を見ていない） | 入れる。G1 の段階 6 と同じ手順（別の依頼書で、テスト `test_official_sample_reports_the_unbooked_ppc_rows` を「D4 が 0 件」に書き換える） |
| `run.py` の注記を直すか | 申し送り 1 | 段階 6 と一緒に直す |

## 7. BS-SEAF の記録

- 時刻：着手 09:56、T0 09:58（約 10 秒）、T1 10:00 ごろ（同）、T2 の実装・照合・テストの追加 〜10:10、`--area ppc` 約 4.5 分、`--full` 約 17 分（10:11〜10:28）。実作業のほとんどは読む・書く時間で、待ち時間は `--area ppc` と `--full` の約 20 分。
- 人の橋渡し：転記・連絡 0、git の操作 0（commit の下書きを `commit_msg206.txt` に置いた。git の操作は大杉さん）、業務の判断 0（依頼書の範囲で決められた）、レビューへの対応 0。
- 環境の手間：Git Bash と PowerShell の `python` が Windows Store の起動用の置き場所を指していて、`C:\Users\ohsug\anaconda3\python.exe` を明示して実行した。最初の hash の記録を自分のコマンドで上書きしてしまい、`git show HEAD:` から作り直した（サンプルは変わっていない）。
- 再利用した知識：G1 の報告書と `check_g1.py`（照合のスクリプトの作り、`run_valuechain` の E2E の呼び方）、G3 検証の付録（外部卸売 443,922,960 円 × 5%）、`ledger._edge_costs`（区間の販売費の行の属性。D3 の行をこれに合わせた）。
- **三つの文書で迷った所・足りなかった情報**：
  - 依頼書 §4.3 の「`basis`＝`ALL`」は定数 `ALL`（`"v1,entity,group"`）のことと読んだ。迷いは小さい。
  - 依頼書 §4.4 は「置き場所は今の issues の作りに合わせて決めてよい」で十分だった。`run()` の終わりにした（入荷の数を数え終えてから出すため）。
  - 依頼書 V6 の「PPC の代理店の `marketing_cost` の全期間の合計」は、PPC のどのファイル・どの列かの指定が無かった。`ppc_event_ledger.csv` の `amount_base` が 1 個当たりの額であることは文書のどこにも無く、取り違えかけた（申し送り 4）。次の依頼書では列の名前まで書くとよい。
  - 依頼書 V7 の「表の 4 行を取り除いた写し」は、正式なサンプルと同じ中身になる。別の写し `model_t2_norule` を作って実行した。
  - 業務定義（GPT-MC）・対応表（Claude君）の数字は、すべて実行の結果と一致した。足りない情報は無かった。

## 8. 段階 6（追記、2026-11-12）

大杉さんの決定（§6 の二つとも「進める」）で、次を行った。

### 8.1 変えたもの

- `data/sample/cosmetics-sg-th-2027-2029/vc_sales_cost_rule.csv`：§3.2 の 4 行を末尾に足した（付録の `model_t2_added/vc_sales_cost_rule.csv` と同じ中身。既存の 10 行は不変）。
- `wom/valuechain/run.py`：`vc_checks.json` の `sales_cost_rule.note` を書き直した。直販の leaf（自社 EC・店舗）は消費者への販売の週にその leaf の販売費、外部の代理店の leaf（`distributor_mdf`）は代理店への卸売の週に売り手の販売費、と書き分けた。あわせて、`ppc_rows_not_used_by_value_chain` が直販の leaf の受入だけを数えていること（代理店の leaf の在庫はグループの外なので数えない）を注記に入れた。値・キーは変えていない。
- テスト：
  - `tests/test_valuechain_distributor_mdf.py`：写しを作る `_cos` が、正式なサンプルの `distributor_mdf` の行を先に取り除いてから各テストの行を足すようにした（G1 の `_cos` と同じ作り）。`test_official_sample_reports_the_unbooked_ppc_rows` を `test_official_sample_books_the_mdf` に置き換えた：正式なサンプルで D4 が 0 件・`rows` 14・MDF 2,340 件・22,196,148 円・PPC との利益の差 0、4 行を取り除いた写しでは D4 の 4 件が戻る。
  - `tests/test_valuechain_sales_cost.py::test_c1_loads_and_absent_file_is_empty`：正式なサンプルの表を「直販の 10 行は写しと同じ」「代理店の 4 行は `distributor_mdf` 0.05」に分けて確かめるようにした。

### 8.2 確かめたこと

- 正式なサンプルの Value Chain：D4 の issue 0 件、`sales_cost_rule.rows` 14、MDF 2,340 件・22,196,148 円、PPC との利益の差 0 円（`test_official_sample_books_the_mdf`）。
- 新規と G1 のテスト：36 passed。
- `python -m tools.quick_check --area ppc`：163 passed（343 秒）
- `python -m tools.quick_check --golden cosmetics-sg-th-2027-2029`：1 passed（不変）（PPC・golden は `vc_sales_cost_rule.csv` を読まない）
- `python -m tools.quick_check --smoke`：507 passed（73 秒）
- `--full` は回していない（コードの変更は `run.py` の注記の文字列だけ。コアにも PPC にも触れていない）。

