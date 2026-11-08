---
handoff:
  case_id: BSSEAF-COS-G1
  task_id: G1-T1-T2-sales-based-costs
  role_from: implement         # Code君
  role_to: owner               # 大杉さん
  target_commit: 5883674
  knowledge_used:
    - id: G1 業務定義案（GPT-MC）
      version: v0.1
      applicability: "§3 業務ルール、§4 手計算（代表 2 lot の期待値）、§5 照合"
    - id: G1 対応表（Claude君）
      version: v0.1
      applicability: "§1 F1〜F7（T0 で再確認）、§3 C1〜C5（実装）、§4 T0〜T2"
    - id: G3 検証報告
      version: "2026-11-08"
      applicability: "照合の作法：費目（price_type）を添えて、販売の出荷 ID × 費目で数える"
  acceptance:
    ref: "requests/RequestLetter_BSSEAF_Cosmetics_G1_SalesBasedCosts_to_CodeKun.md §6"
    result: "S1〜S5 すべて合格"
  evidence:
    - docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_appendix/check_g1.py
    - docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_appendix/check_g1_result.json
    - tests/test_valuechain_sales_cost.py
  status: "合格。Value Chain の改修は commit 待ち（git の操作は大杉さん）"
  open_items:
    - "正式なサンプルに C1 の表と配送の行を入れるか（段階 6）"
    - "PPC の sga_cost は Value Chain の policy.py では『その週の費用』。新しい G1 の行は販売費に置いた"
    - "vc_ppc_comparison.csv で、配送・梱包 6,243,120 円が台帳では『運賃』、PPC では『SGA』に入る"
  stop_reasons: []
  next: owner
---

# 報告書：G1（売上比率の費用）を Value Chain で計上する（検証 T0・T1、実装 T2）

- 依頼：`requests/RequestLetter_BSSEAF_Cosmetics_G1_SalesBasedCosts_to_CodeKun.md` v0.1（2026-11-08）
- 業務定義：`docs/design/drafts/WOM_G1_SalesBasedCosts_Business_Definition_v0.1.md`（GPT-MC）
- 対応表：`requests/BSSEAF_Cosmetics_G1_SalesBasedCosts_Mapping_v0.1.md`（Claude君、大杉さんの判断 4 件を反映）
- 実施：Code君（Claude Code、Windows）、2026-11-08
- 付録（git の追跡対象）：`docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_appendix/`

## 0. 結論

**シンガポール販社の直販（公式 EC・直営店）の売上比率の費用を、費目ごとに販売の週に 1 件ずつ、Value Chain で計上できるようにした。配送・梱包費も、発送（＝販売）の週に 1 件ずつ計上する。** 写しのモデル（`model_t2`）で、代表の 2 lot は業務定義の手計算と一致した。全期間の G1 の合計は 281,015,748 円で、M0 で未計上だった額と一致した。PPC のコード・正式なサンプル・golden は変えていない。

| # | 条件 | 結果 |
|---|---|---|
| S1 | B1〜B3 の記録。B1・B2 が見立てどおり | **合格** |
| S2 | T1 の (1)〜(4) | **合格** |
| S3 | V1〜V9 | **合格**（9 項目すべて） |
| S4 | テスト（単体の追加、領域、`--full`）、golden 全件不変 | **合格**：新しいテスト 18 件、領域 `ppc` 145 passed、full 1,080 passed・failed 0、golden 全件不変（§7） |
| S5 | 変えたのは `wom/valuechain/` 4 ファイルとテスト、`tests/conftest.py` の 1 行、報告書と付録だけ | **合格** |

止める理由には当たらなかった。

**代表の 2 lot（model_t2）**

| lot | 週 | 費目 | 金額（SGD） |
|---|---|---|---:|
| EC `COS_Cream:SG_EC:2028-W28:00001` | 2028-W28 | 販社販管費（`hq_sga_allocation`） | 314.40 |
| 同 | 2028-W28 | 決済・EC 基盤手数料（`payment_platform_fee`） | 157.20 |
| 同 | 2028-W28 | デジタル広告費（`digital_ad`） | 471.60 |
| 同 | 2028-W28 | 消費者向け配送・梱包費（`delivery_packing_cost`） | 72.00 |
| **同 計** | | **4 件** | **1,015.20** |
| 直営店 `COS_Cream:SG_Store:2028-W30:00001` | 2028-W28（入荷） | — | 0 件 |
| 同 | 2028-W30（販売） | 店舗運営費（`store_operating`、M5 の近似） | 1,159.20 |
| 同 | 2028-W30 | 販社販管費（`hq_sga_allocation`） | 331.20 |
| **同 計** | | **2 件** | **1,490.40** |

## 1. 着手時の記録

- **着手時の SHA**：`5883674`（依頼書の commit。依頼書の `target_commit` は `d918468`）。`d918468..5883674` は文書の追加だけで、`wom/`・`tools/`・`tests/`・`data/sample/` に差分は無い。
- **作業ツリー**：着手時 clean。
- **環境**：Windows 11、Python 3.12.3（Anaconda）、pandas 2.2.2、numpy 1.26.4。PATH の `python` は Windows Store の入口だけなので、Anaconda の python を PATH の先頭に置いて実行した。
- **plugins**：写しのモデル（フォルダ名が golden と違う）は `--plugins` を省略すると `safe` になる。そこで、golden と同じ組（`HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin`、サンプルの `recommended_plugins`）を明示した。正式なサンプルは省略で同じ組になる（`vc_run_info.json` で確認）。

## 2. 先に確かめたこと（B1〜B3）

| # | 結果 |
|---|---|
| B1 | EC `COS_Cream:SG_EC:2028-W28:00001`：DC の出荷 2028-W27、入荷・販売 2028-W28、売上 3,144 SGD（2028-W28）。直営店 `COS_Cream:SG_Store:2028-W30:00001`：入荷 2028-W28、販売 2028-W30、売上 3,312 SGD（2028-W30）。**見立てどおり** |
| B2 | `SG_EC->CONSUMER` の行を足しても、PPC の出力 7 ファイルは T0 と 1 バイトも違わない（T1・T2 の両方で sha256 一致）。PPC は区間を名前で引くだけで（`ppc_rules.get_edge_costs`）、木に無い区間の行は読まれない。`cost_type=delivery_packing_cost`（PPC が知らない名前）でも止まらない。モデルの検査の道具で `ppc_edge_cost_rule.csv` を読むものは、Value Chain の `masters.py` と PPC のほかに無い（`tools/` を検索）。**見立てどおり** |
| B3 | T0 の issues 2,470 件：`revenue_based_node_cost_not_supported` が SG_EC marketing_cost 754・SG_EC sga_cost 754・SG_Store sga_cost 962。代理店（G2）は 0（外部の法人の在庫ではノードの費用を計上しないため、警告も出ない）。直販の販売は EC 754・直営店 962 |

## 3. Part A：検証（コードを変えない）

### T0（正式なサンプル）

`python -m tools.valuechain_run --model-dir data\sample\cosmetics-sg-th-2027-2029 --out output\g1_trial\t0`。G3 検証と同じ結果（conservation OK、外部売上の照合 True、未評価 0、issues 2,470）。代表の 2 lot の明細は付録 `t0_ec_lot_money_lines.csv`・`t0_store_lot_money_lines.csv`。G1 の行は 0 件。

### T1（`model_t1`：`SG_EC->CONSUMER` の 2 行、`logistics_cost`・3 SGD/個）

| # | 期待 | 結果 |
|---|---|---|
| (1) | 代表の EC の lot に、2028-W28・expense・selling・E_SG・SG_EC・`CONSUMER:SG_EC`・72 SGD の行が 1 件、`src_id` ＝ 販売の出荷 ID | **1 件**（`src_id` ＝ `ship:COS_Cream:OUT:leaf_out:SG_EC:COS_Cream:96:0`、8,280 円） |
| (2) | EC の販売 754 件すべてに 1 件ずつ、合計 6,243,120 円 | 754 件、すべて 1 件、**6,243,120 円** |
| (3) | この行を除くと、明細は T0 と同じ | 98,436 行 − 754 行 ＝ T0 の 97,682 行と、`line_id` を除いた全列が一致 |
| (4) | PPC の出力は T0 と同じ | 7 ファイルとも一致 |

T1 の全期間の利益（第 1 回）は 932,520,912 → 926,277,792 円（差 6,243,120）。

## 4. Part B：実装

| # | 変更 | 場所 |
|---|---|---|
| C1 | `vc_sales_cost_rule.csv`（任意）の読み込み。無ければ `{}` で今の動き。検査：列、ノード・SKU・費目の重複、費目（`policy.SALES_COST_ITEMS`）、`ppc_cost_type`（sga_cost / marketing_cost）、`basis=revenue` だけ、`rate` は 0〜1 の数、ノードは直販の leaf（`channel_type` own / online、法人がグループ）、通貨＝その leaf の市場価格の通貨。違えば `MasterError`（ファイル・行・値を出す） | `masters.py` `load_sales_cost_rule`、`VCMasters.sales_cost`（既定は空。テストで直接作る `VCMasters` もそのまま動く） |
| C2 | `_consumer` のグループの販売で、売上と原価の行の後に、C1 の行ごとに 1 行：金額 ＝ `rate` × その販売の売上（市場価格 × 個数、価格が無ければ NaN）、`kind=expense`・`scope=selling`・`basis=v1,entity,group`・`family`＝`ppc_cost_type`・`price_type`＝`cost_item`、`entity`＝持ち主、`node`＝leaf、`counterparty`＝`CONSUMER:<leaf>`、`src_id`＝販売の出荷 ID、週＝販売の週 | `ledger.py` `_consumer` |
| C3 | C1 に行があるノード・SKU では、`ppc_node_cost_rule.csv` の `basis=revenue` の行を `_node_costs` で計上せず、issues も出さない。数は `vc_checks.json` の `sales_cost_rule.ppc_rows_not_used_by_value_chain`（ノード・SKU・種類・飛ばした入荷の数）。C1 に行の無いノード（代理店の MDF など）は今のまま | `ledger.py` `_node_costs`、`run.py` |
| C4 | 起動時に、C1 に行があるノード・SKU ごとに：(1) `ppc_cost_type` ごとの率の合計 ＝ PPC の同じ種類の `basis=revenue` の行の率、(2) その PPC の行の固定額の合計 ＝ `<leaf>->CONSUMER` の区間の行の 1 個当たりの額の合計（行が無ければ 0）、(3) PPC に `basis=revenue` の行がある種類に C1 の行が無い。合わなければ `MasterError` | `masters.py` `load_sales_cost_rule` |
| C5 | `EDGE_COST_FAMILY` に `delivery_packing_cost → freight`。費用の分け方の表の説明に 2 行 | `policy.py` |

**実装で決めたこと（依頼書に無い細部）**

- C4 (2) で比べる区間の額は、`rate ＋ fixed`（台帳の `_consumer` が 1 個当たりに計上する額）にした。依頼書の「固定額の合計」より広いが、台帳が実際に計上する額と比べるため。今のデータでは rate 0 なので同じ。PPC の固定額と区間の額の通貨が違えば止める。
- 費目の名前は `policy.py` の表 `SALES_COST_ITEMS` に置き、表に無い名前は止める（黙った既定値を作らない。費用の分け方の表を 1 か所に置く作りに合わせた）。
- C2 の行の `valued` は、ほかの販売費の行と同じく金額だけで決まる（金額が NaN なら未評価）。lot の原価が未評価でも、費用の額は分かるため。

**写しのモデル `model_t2`**：T1 の写しに、依頼書 §4.1 の `vc_sales_cost_rule.csv`（10 行）を足し、`SG_EC->CONSUMER` の 2 行の `cost_type` を `delivery_packing_cost` にした（付録 `model_t2_added/`）。

## 5. T2 の照合（V1〜V9）

`model_t2` で、同じ場所 `t2` に 2 回（1 回目を `t2_first` に写した）、別の場所 `t2_b` に 1 回実行した。改修後のコードで正式なサンプルも `t0_after` に実行した。照合は付録の `check_g1.py`（出力を読むだけ）。

| # | 期待 | 結果 |
|---|---|---|
| V1 | 代表の EC の lot：4 件・1,015.20 SGD、2028-W28、同じ販売の出荷 ID | **一致**（§0 の表） |
| V2 | 代表の直営店の lot：2028-W28 に 0 件、2028-W30 に 2 件・1,490.40 SGD | **一致** |
| V3 | 直販の販売（EC 754、直営店 962）× 費目で、すべてちょうど 1 行 | G1 の行 4,940（754 × 4 ＋ 962 × 2）。1 行でない組 0、直販の販売以外から立った行 0 |
| V4 | 金額 ＝ 率 × その販売の売上の行の金額、配送 ＝ 個数 × 3 | 4,940 行すべて一致（通貨も一致） |
| V5 | 全期間の G1 の合計 281,015,748 円、うち配送・梱包 6,243,120 円 | **281,015,748 円**（差 0）、配送・梱包 **6,243,120 円** |
| V6 | PPC との照合（参考） | 下の表。全期間の合計も、週ごとの値も一致 |
| V7 | 直販の `revenue_based_node_cost_not_supported` が 0、代理店は今のまま | issues 0 件（T0 2,470）。代理店は T0 も 0 で変わらない。PPC 用として使わなかった行：SG_EC クリーム sga・marketing 各 299 回、SG_EC 美容液 各 455 回、SG_Store クリーム 416 回、美容液 546 回（入荷の数） |
| V8 | 再計算で明細が同じ | `t2_first`・`t2`・`t2_b` の明細の中身の sha256 がすべて同じ（`dd3e0e21…`） |
| V9 | 正式なサンプルの Value Chain の出力、PPC の出力、golden が変わらない | 正式なサンプル（改修後）：明細は T0 と完全一致、出荷の記録は `plan_id` の列を除いて一致（`plan_id` は作業ツリーの dirty の印 `+dirty` だけが違う）、ほかの CSV 13 本・issues も一致。PPC の出力は T0・T1・T2・`t0_after` ですべて一致。サンプルのフォルダの 28 ファイルは前後で sha256 が同じ。golden は §7 |

**V6：PPC との照合（全期間、円）**

| PPC の種類 | Value Chain の費目 | PPC | Value Chain | 差 | 週ごとの差が 1 円を超える週 |
|---|---|---:|---:|---:|---:|
| SG_EC sga_cost | 販社販管費 ＋ 決済手数料 ＋ 配送・梱包 | 52,033,176 | 52,033,176 | 0 | 0 / 312 |
| SG_EC marketing_cost | デジタル広告費 | 45,790,056 | 45,790,056 | 0 | 0 / 312 |
| SG_Store sga_cost | 店舗運営費 ＋ 販社販管費 | 183,192,516 | 183,192,516 | 0 | 0 / 286 |

週は、Value Chain の販売の週と PPC の週が全部同じだった（PPC は leaf の販売の週に、販売の週の為替で計上する。Value Chain も同じ）。

**全期間の利益（第 1 回、消去前）**：T0 932,520,912 → T2 651,505,164（差 281,015,748）。`vc_ppc_comparison.csv` の「利益 合計」の差（Value Chain − PPC）は、T0 の 303,211,896 から T2 の **22,196,148** に縮み、残りは G2（代理店の MDF）だけになった。

## 6. 止める理由と申し送り

**止める理由**：無し。

**申し送り**：

1. **費用の種類の分類が違う**：`policy.py` では、ノードの費用の `sga_cost` は「その週の費用」（`scope=period`）である。新しい G1 の行は、業務定義どおり販売費（`scope=selling`）に置いた（`family` は `sga_cost`）。台帳で `family=sga_cost` を集計するときは、`scope` が 2 種類あることに注意。
2. **`vc_ppc_comparison.csv` の項目の分け方**：配送・梱包 6,243,120 円は、台帳では `family=freight` なので「運賃」の行に入る（差 +6,243,120）。PPC ではこの 3 SGD を `sga_cost` に含めるので、「SGA」の行の差が −6,243,120 になる。合計は合う。比較の表を費目に合わせて分けるかは、別の判断（`run.py` の `compare_with_ppc` は今回変えていない）。
3. **発送が先行する例**（業務定義 §4.1）は作っていない（大杉さんの判断）。実績の取り込みの設計で扱う。
4. 代理店の MDF（G2）は今のまま、Value Chain に入らない（issues も出ない）。

## 7. テスト

| 段 | 結果 |
|---|---|
| 単体・結合（新しいファイル `tests/test_valuechain_sales_cost.py`、18 件） | 18 passed。C2（行の属性・金額・販売の週・V3 の利益への算入）、C2 の価格なし（NaN・未評価）、C3（表があるとき issues なし・PPC の行を使わない、無いときは今のまま）、C1 の検査 9 種、C4 の 3 つの止め方、化粧品の写しでの E2E（代表 2 lot・合計 281,015,748） |
| `tests/conftest.py` | 領域の表に 1 行（`ppc`）。`tests/test_test_areas.py` 緑 |
| 領域 `python -m tools.quick_check --area ppc` | **145 passed**・failed 0（459 秒）。警告 1 件（下記） |
| full `python -m tools.quick_check --full` | **1,080 passed・3 skipped・failed 0**（1,547 秒）。冒頭の CLAUDE.md の表の 892 件から増えているのは、その後に足されたテストと今回の 18 件 |
| golden | full に含まれる `tests/test_golden.py` は全件 passed（**全件不変**）。golden のファイルは変えていない |

警告：スレッドの中の `UnicodeDecodeError: 'cp932' codec can't decode` が、`PytestUnhandledThreadExceptionWarning` として出た（`--area ppc` と full の両方で 1 件ずつ。テストは失敗していない）。出どころは `tests/test_ppc_no_silent_fallback.py::test_t08_demo_still_uses_sample_data` である。このテストは `python -m wom.ppc` を subprocess で `text=True`・encoding の指定なしで実行するので、UTF-8 の出力を Windows の既定（cp932）で読もうとして失敗する。Value Chain を通らないので、今回の改修とは関係ない。full のほかの警告 14 件（push の Mode 1/3、能力の表の期間外の週など）も、今回の改修と関係のない既存のもの。

## 8. BS-SEAF の記録

- **時刻**：始め 15:44、終わり 16:30 前後（2026-11-08、端末の時計）。うち full のテストが約 26 分。
- **作業中の失敗（記録）**：commit メッセージの下書きを書くとき、使われていない番号を確かめた一覧が古く、既にあった `commit_msg196.txt`（`8e6ad9d` の下書き）を上書きした。commit `8e6ad9d` のメッセージから元に戻した（同じ方法で `commit_msg197.txt` を作り直すと 1 バイトも違わないことで、方法を確かめた）。今回の下書きは `commit_msg200.txt`。
- **人の橋渡し**：大杉さんが依頼書を commit し、Code君に渡した 1 回。作業中の問い合わせは無し。
- **再利用した知識**：G1 業務定義 §4（代表 2 lot の手計算）、G1 対応表 §1（F1〜F7：T0 で再現）・§3（C1〜C5 をそのまま実装）、G3 検証報告 §6（販売の出荷 ID × 費目で数える。今回の V3 にそのまま使えた）、M0 報告書 T12（G1 の未計上額 281,015,748）。
- **業務定義（GPT-MC）・対応表（Claude君）・依頼書の三つで、迷った所・足りない情報**：
  1. **C4 (2) の「固定額」**：区間の行に率（rate）があった場合に、それを含めるかが書かれていない。台帳は区間の行を（rate ＋ fixed）× 個数で計上するので、それと比べた（§4）。
  2. **C4 (2) の比べる単位**：PPC の「その行の固定額」は種類ごとの行にある（EC は sga に 3、marketing に 0）。区間の額を種類ごとに比べると marketing が 0 ≠ 3 で止まるので、PPC の `basis=revenue` の行の固定額の合計と比べた。依頼書の例（EC の sga 3 SGD）から読み取れる意味に合わせた。
  3. **費目の名前の範囲**：依頼書は 4 つの費目を「今回」と書くが、表に無い名前を止めるかは書かれていない。止める方にした（費用の分け方の表に置いた）。
  4. **写しのモデルの plugins**：フォルダ名が golden と違うので、`--plugins` を省略すると golden と違う組（`safe`）になる。依頼書の手順には書かれていない。明示して実行した。
  5. 三つの文書のあいだで、数値・週・費目の食い違いは無かった。対応表の F6（EC は入荷と販売が同じ週、直営店は 2 週後）と、大杉さんの判断「代表の lot の週の読み替え」で、業務定義の例（W28 入荷・W29 売上）との違いが先に整理されていたので、判定に迷わなかった。

## 9. 大杉さんに決めてほしいこと

| 一言の決定 | 中身 | 推奨 |
|---|---|---|
| **正式なサンプルに C1 の表と配送の行を入れるか**（段階 6） | `data/sample/cosmetics-sg-th-2027-2029/` に `vc_sales_cost_rule.csv`（10 行）と `SG_EC->CONSUMER` の 2 行（`delivery_packing_cost`）を足す。正式なサンプルの Value Chain で G1 の未計上 281,015,748 円が解消し、Value Chain と PPC の利益の差は G2 の 22,196,148 円だけになる。PPC の出力は変わらない（B2・V9）。golden は Planning と PPC の snapshot なので変わらない見込み（足した後に確かめる） | 入れる。付録 `model_t2_added/` の 2 ファイルをそのまま使える |
| 比較の表の項目の分け方（申し送り 2） | `vc_ppc_comparison.csv` で配送・梱包を「SGA」に寄せて PPC に合わせるか、今のまま（運賃）で説明を足すか | 今のまま。費目は業務定義どおり台帳に持ち、比較の表の説明に一言足す程度でよい |
| G2（代理店の MDF）を次に扱うか | 外部の代理店の在庫で、売り手（SG 販社・日本本社）の負担の販売費をどの事象・週に置くかの業務定義が要る | GPT-MC に業務定義を依頼 |

## 10. 付録

`docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_appendix/`

| ファイル | 中身 |
|---|---|
| `check_g1.py` | 照合のスクリプト（出力とモデルの CSV を読むだけ。WOM を import しない） |
| `check_g1_result.json` | B1・B3・T1・V1〜V9 の結果 |
| `t0_ec_lot_money_lines.csv`、`t0_store_lot_money_lines.csv` | T0 の代表 2 lot の明細 |
| `t1_ec_lot_money_lines.csv` | T1 の代表の EC の lot の明細 |
| `t2_ec_lot_money_lines.csv`、`t2_store_lot_money_lines.csv` | T2 の代表 2 lot の明細 |
| `model_t2_added/vc_sales_cost_rule.csv`、`model_t2_added/ppc_edge_cost_rule.csv` | `model_t2` に足した・変えた 2 つのファイルの写し |

実行の出力（`output/g1_trial/`）は git の対象外。

## 11. 段階 6：正式なサンプルへの反映（2026-11-08）

- 依頼：`requests/RequestLetter_BSSEAF_Cosmetics_G1_SampleAdoption_to_CodeKun.md` v0.1。大杉さんの判断：正式なサンプルに新しい表と配送の行を入れる。G1 は直販について閉じる
- 着手時の SHA：`2bda934`（G1 の実装 `e822cc7` の後の先頭）。作業ツリーは clean
- 時刻：17:11〜17:22（端末の時計）
- 結果：**合格**（S1〜S3）。止める理由には当たらなかった

### 変えたファイル

| ファイル | 変更 |
|---|---|
| `data/sample/cosmetics-sg-th-2027-2029/vc_sales_cost_rule.csv` | 新しく置いた。付録 `model_t2_added/vc_sales_cost_rule.csv` とバイト単位で同じ（10 行） |
| `data/sample/cosmetics-sg-th-2027-2029/ppc_edge_cost_rule.csv` | 付録の同名のファイルとバイト単位で同じにした。`git diff` は `SG_EC->CONSUMER` の `delivery_packing_cost` の 2 行の追加だけで、ほかの行は前と同じ。改行は前と同じ LF |
| `data/sample/cosmetics-sg-th-2027-2029/README.md` | 「金額の規則」に `vc_sales_cost_rule.csv` と配送の行の説明。「期待する結果」の Value Chain の行（差 303,211,896 → 22,196,148 円、G2 だけ）と、G1 の行（281,015,748 円）を足した。「既知の限界」の G1 を解決済みにし、報告書へのリンクと、比較の表で配送・梱包が「運賃」と「SGA」に分かれる注意を書いた |
| `tests/test_valuechain_sales_cost.py` | テストの準備を直した（下の「直したテスト」） |

コード（`wom/`）・golden・PPC の規則のファイルは変えていない。

### 確かめたこと（依頼書 §2）

変更の前に、正式なサンプルを `output/g1_s6/before` に実行して基準を取り、変更の後に `output/g1_s6/after` に実行した。

| # | 期待 | 結果 |
|---|---|---|
| 1 | G1 の行の全期間の合計 281,015,748 円、直販の `revenue_based_node_cost_not_supported` 0、利益の差（Value Chain − PPC）22,196,148 円、報告書の T2 と同じ | G1 の行 4,940、合計 **281,015,748 円**（うち配送・梱包 6,243,120 円）。issues **0**（前 2,470）。`vc_ppc_comparison.csv` の利益の差 **22,196,148 円**（台帳 654,045,756、PPC 631,849,608）。明細（`vc_money_lines.csv.gz` を解凍した中身）の sha256 が T2 と同じ（`dd3e0e21…`） |
| 2 | PPC の出力が変更の前と同じ（バイト単位） | 7 ファイルとも `before` と同じ（T2 とも同じ） |
| 3 | `--changed` が選ぶ領域と golden | `python -m tools.quick_check --changed`：smoke・`ppc`（テストのファイルを変えたため）・化粧品の golden、**603 passed・failed 0**。`--area golden`：**19 passed**。golden のファイルは変えていない（不変） |

### 直したテスト

`tests/test_valuechain_sales_cost.py` の結合のテストは、化粧品のサンプルを写して `SG_EC->CONSUMER` の行を書き足し、表を置いていた。また、写していないサンプルには表が無いことを確かめていた。サンプルに表と配送の行が入ったので、前の版では 18 件のうち 13 件が落ちる（配送の行が二重になり、`written twice` で止まる。表が無い前提が外れる）。確かめた。

- 直し方：準備の関数 `_cos` で、写しから表と `->CONSUMER` の行をいったん取り除いてから、各テストの表・行を置くようにした（検査の中身・期待値は変えていない）。
- 「表が無ければ空」は、表を取り除いた写しで確かめるようにした。正式なサンプルの表は、テストで置く 10 行と同じ中身であることを確かめる assert を足した。
- 直した後：18 passed。

### 申し送り

- README の「既知の限界」の G3 の項（「代理店の売上は DC の出荷週に立つ。sell-in の業務定義と週が違う」）は、G3 の検証で Value Chain が業務定義（D-2）を満たすと判断された後の内容になっていない。今回の依頼の範囲（G1）の外なので変えていない。直すかは大杉さんが決める。
