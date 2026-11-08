---
handoff:
  case_id: BSSEAF-COS-G1
  task_id: G1-T1-T2-sales-based-costs
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: d918468
  knowledge_used:
    - id: G1 業務定義案（GPT-MC）
      version: v0.1
      applicability: "§3 業務ルール、§4 手計算、§5 照合、§7 推奨案。直販（SG_EC・SG_Store）だけ"
    - id: G1 対応表（Claude君）
      version: v0.1
      applicability: "§1 事実 F1〜F7、§3 最小の改修 C1〜C5、§4 試行 T0〜T2、§5 の判断（4 件とも推奨どおり採用）"
    - id: G3 検証報告
      version: "2026-11-08"
      applicability: "§6 の照合の作法（費目を添えて数える。Lot_ID だけで照らさない）"
  acceptance:
    ref: "この依頼書 §6"
  evidence:
    - docs/design/drafts/WOM_G1_SalesBasedCosts_Business_Definition_v0.1.md
    - requests/BSSEAF_Cosmetics_G1_SalesBasedCosts_Mapping_v0.1.md
  status: "試行可能"
  open_items: []
  stop_reasons: []
  handover_notes:
    - "発送が先行する例（業務定義 §4.1）は作らない。実績の取り込みの設計で扱う（大杉さん 2026-11-08）"
  next: implement
---

# Request Letter：G1（売上比率の費用）を Value Chain で計上する（検証 T0・T1、実装 T2）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-11-08）
- 版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`（ブランチ `wom-v1r6m0_BS-SEAF`。着手時の SHA を報告書に記録する）
- 前提：G1 業務定義案 v0.1（GPT-MC）と、G1 対応表 v0.1（Claude君）。大杉さんの判断（2026-11-08、4 件とも推奨どおり）
- 範囲：
  - Part A（T0・T1）：**検証だけ**。コードを変えない。モデルの写しで行う。
  - Part B（T2）：**Value Chain の改修**（`wom/valuechain/` と、そのテスト）。保護対象のコアには触れない。**PPC のコードと、正式なサンプル・golden は変えない**。試行はモデルの写しで行う
- 出力：`output/g1_trial/` の下（git の対象外）

---

## 一言で

**シンガポール販社の直販（公式 EC・直営店）で、売上比率の費用を費目ごとに売上の週に、配送・梱包費を発送の週に、それぞれ 1 件ずつ計上できるようにしてください。PPC は変えずに、照合の相手として使います。**

## 0. 大杉さんの判断（2026-11-08）

| 一言で | 中身 |
|---|---|
| 代表の EC の lot は週を読み替える | 代表は `COS_Cream:SG_EC:2028-W28:00001`（DC の出荷 2028-W27、入荷・販売 2028-W28）。期待は 2028-W28 に 4 件・1,015.20 SGD（金額と件数は業務定義のまま）。「入荷だけでは 0 件」は直営店の lot `COS_Cream:SG_Store:2028-W30:00001`（入荷 2028-W28、販売 2028-W30）で確かめる |
| 発送が先行する例は今は作らない | 業務定義 §4.1 は対象外 |
| 費目の内訳は Value Chain 用の表に置き、PPC は変えない | §3 の C1〜C5 |
| 直営店の基準は 138 SGD をそのまま使う | 直営店は店頭価格で売る（値引きなし）と置く |

## 1. 業務の期待（業務定義 §3・§4 の当てはめ）

| lot | 週 | 費目 | 計算 | 金額（SGD） |
|---|---|---|---|---:|
| EC `COS_Cream:SG_EC:2028-W28:00001` | 2028-W28 | 販社販管費 | 3,144.00 × 10％ | 314.40 |
| 同 | 2028-W28 | 決済・EC 基盤手数料 | 3,144.00 × 5％ | 157.20 |
| 同 | 2028-W28 | デジタル広告費 | 3,144.00 × 15％ | 471.60 |
| 同 | 2028-W28 | 消費者向け配送・梱包費 | 24 個 × 3.00 | 72.00 |
| **同 計** | | **4 件** | | **1,015.20** |
| 直営店 `COS_Cream:SG_Store:2028-W30:00001` | 2028-W28（入荷） | — | — | 0（0 件） |
| 同 | 2028-W30（販売） | 店舗運営費（M5 の近似） | 3,312.00 × 35％ | 1,159.20 |
| 同 | 2028-W30 | 販社販管費 | 3,312.00 × 10％ | 331.20 |
| **同 計** | | **2 件** | | **1,490.40** |

すべて `E_SG` の販売費。売上の基準は Value Chain の外部売上の行（`kind=revenue`・`scope=external`、市場価格 × 個数）。

## 2. 先に確かめること

| # | 確かめること | 違ったら |
|---|---|---|
| B1 | 代表の 2 lot の週と売上（EC：販売 2028-W28・3,144 SGD。直営店：入荷 2028-W28・販売 2028-W30・3,312 SGD） | 止めて報告 |
| B2 | `ppc_edge_cost_rule.csv` に `SG_EC->CONSUMER` の行を足しても、**PPC の出力が変わらない**こと（PPC は `<leaf>->CONSUMER` を読まない、という対応表 F5 の見立て）。PPC・モデルの検査の道具が、木に無い区間の ID で止まらないこと | 止めて報告（配送の行の置き場所を設計し直す） |
| B3 | Value Chain の issues の `revenue_based_node_cost_not_supported` の件数（M0：直営店 962、EC 754 × 2） | 記録だけ |

## 3. Part A：検証（コードを変えない）

| 段 | 中身 | 合格 |
|---|---|---|
| T0 | 正式なサンプルで Value Chain を実行（`python -m tools.valuechain_run --model-dir data/sample/cosmetics-sg-th-2027-2029 --out output/g1_trial/t0`）。PPC も既定どおり出す | B1・B3 を記録。代表の 2 lot の明細を表にする |
| T1 | サンプルを `output/g1_trial/model_t1/` に写し、`ppc_edge_cost_rule.csv` に 2 行を足す：`SG_EC->CONSUMER,COS_Serum,logistics_cost,qty,0,3,SGD` と `SG_EC->CONSUMER,COS_Cream,logistics_cost,qty,0,3,SGD`。Value Chain を実行 | (1) 代表の EC の lot に、2028-W28、`kind=expense`・`scope=selling`、`entity=E_SG`・`node=SG_EC`・`counterparty=CONSUMER:SG_EC`、72 SGD の行が 1 件。`src_id` ＝ その販売の出荷 ID。(2) EC の販売 754 件すべてに 1 件ずつ、合計 6,243,120 円。(3) この行を除くと、明細は T0 と同じ。(4) PPC の出力は T0 と同じ（B2） |

T1 が合格したら Part B に進む。止める理由に当たったら、Part B に進まずに報告する。

## 4. Part B：実装（差分だけ）

### 4.1 C1：Value Chain 用の費目の表（新しいファイル、任意）

`vc_sales_cost_rule.csv`（モデルのフォルダ。**無ければ今の動き**）

| 列 | 中身 |
|---|---|
| `node_id` | 直販の leaf（`vc_node_assignment.csv` で `channel_type` が `own` か `online`、法人がグループ） |
| `product_id` | SKU |
| `cost_item` | 費目。今回：`hq_sga_allocation`（販社販管費）、`payment_platform_fee`（決済・EC 基盤手数料）、`digital_ad`（デジタル広告費）、`store_operating`（店舗運営費、M5 の近似） |
| `ppc_cost_type` | PPC で合計する種類：`sga_cost` か `marketing_cost` |
| `basis` | `revenue` だけ（ほかは止める） |
| `rate` | 率 |
| `currency` | その leaf の市場価格の通貨と同じ（違えば止める） |
| `note` | 説明 |

読み込みの検査（`masters.py`、違えば `MasterError`）：ノード・SKU・費目の重複、上の各列の値、ノードが直販の leaf であること。

写しのモデル（`output/g1_trial/model_t2/`）に置く中身：

```
node_id,product_id,cost_item,ppc_cost_type,basis,rate,currency,note
SG_EC,COS_Serum,hq_sga_allocation,sga_cost,revenue,0.10,SGD,販社販管費 10%
SG_EC,COS_Serum,payment_platform_fee,sga_cost,revenue,0.05,SGD,決済・EC 基盤手数料 5%
SG_EC,COS_Serum,digital_ad,marketing_cost,revenue,0.15,SGD,デジタル広告費 15%
SG_EC,COS_Cream,hq_sga_allocation,sga_cost,revenue,0.10,SGD,販社販管費 10%
SG_EC,COS_Cream,payment_platform_fee,sga_cost,revenue,0.05,SGD,決済・EC 基盤手数料 5%
SG_EC,COS_Cream,digital_ad,marketing_cost,revenue,0.15,SGD,デジタル広告費 15%
SG_Store,COS_Serum,store_operating,sga_cost,revenue,0.35,SGD,店舗運営費 35%（M5 の近似）
SG_Store,COS_Serum,hq_sga_allocation,sga_cost,revenue,0.10,SGD,販社販管費 10%
SG_Store,COS_Cream,store_operating,sga_cost,revenue,0.35,SGD,店舗運営費 35%（M5 の近似）
SG_Store,COS_Cream,hq_sga_allocation,sga_cost,revenue,0.10,SGD,販社販管費 10%
```

### 4.2 C2：売上の週に計上する

`ledger.py` の `_consumer`、グループの販売の分岐で、売上と原価の行の後に、C1 の行ごとに 1 行：

- 金額 ＝ `rate` × その販売の売上の金額（市場価格 × 個数）。価格が無ければ NaN（今の売上の行と同じ扱い）
- `kind=expense`、`scope=selling`、`basis`＝`ALL`、`family`＝`ppc_cost_type`、`price_type`＝`cost_item`
- `entity`＝持ち主（E_SG）、`node`＝leaf、`counterparty`＝`CONSUMER:<leaf>`、`src_id`＝販売の出荷 ID、`lot_id`＝その lot
- 週 ＝ 販売の週

### 4.3 C3：二重計上と警告を止める

C1 に行があるノード・SKU では、`ppc_node_cost_rule.csv` の `basis=revenue` の行を PPC 用として扱い、`_node_costs` で計上も issues も出さない（件数は `vc_checks.json` に「PPC 用として Value Chain では使わなかった行」として記録）。C1 に行が無いノード（代理店の MDF＝G2 など）は今のまま。

### 4.4 C4：二つのファイルのずれを止める

起動時に、C1 に行があるノード・SKU ごとに確かめ、合わなければ `MasterError`：

1. `ppc_cost_type` ごとの C1 の率の合計 ＝ `ppc_node_cost_rule.csv` の同じ種類の `basis=revenue` の行の率（EC：sga 0.15・marketing 0.15。直営店：sga 0.45）
2. その PPC の行の固定額（EC の sga 3 SGD）＝ `<leaf>->CONSUMER` の区間の費用の行の固定額の合計（無ければ 0 と比べる）
3. PPC の行に `basis=revenue` があるのに、C1 にその種類の行が無い

### 4.5 C5：配送・梱包の名前

`policy.py` の `EDGE_COST_FAMILY` に `"delivery_packing_cost": "freight"` を足す（グループから外部へは売り手の販売費。表は `policy.py` の 1 か所のまま）。写しのモデル `model_t2` の `SG_EC->CONSUMER` の 2 行は、`cost_type` を `delivery_packing_cost` にする。

### 4.6 テスト

- 単体：C1 の読み込みの検査、C2 の金額と行の属性、C3（C1 があるとき issues が出ない、無いときは今のまま）、C4 の 3 つの止め方。小さな合成のモデルで（`tests/test_valuechain_handcalc.py` の作りに倣う）。新しいテストのファイルは `tests/conftest.py` の領域の表に 1 行足す。
- `python -m tools.quick_check --area <Value Chain の領域>`、最後に `--full` を 1 回。golden は全件不変。

## 5. T2 の照合

`model_t2`（T1 の写し ＋ C1 の表 ＋ 配送の行の名前を `delivery_packing_cost` に）で Value Chain を同じ場所に 2 回、別の場所に 1 回実行する。

| # | 照らすこと | 期待 |
|---|---|---|
| V1 | 代表の EC の lot の G1 の行（`kind=expense`・`scope=selling`、`node=SG_EC`） | §1 の 4 件・計 1,015.20 SGD、すべて 2028-W28、`src_id` は同じ販売の出荷 ID |
| V2 | 代表の直営店の lot | 2028-W28 に G1 の行 0。2028-W30 に 2 件・計 1,490.40 SGD |
| V3 | 全部の直販の販売（EC 754、直営店 962） | 販売の出荷 ID × 費目で、すべてちょうど 1 行。EC は 4 費目、直営店は 2 費目 |
| V4 | 金額 | すべて「率 × その販売の売上の行の金額」、配送は「個数 × 3」と一致 |
| V5 | 全期間の G1 の合計 | **281,015,748 円**（M0 の G1 未計上額）。うち配送・梱包 6,243,120 円 |
| V6 | PPC との照合（参考の合計） | 全期間で、EC の `sga_cost` ＝ 販社販管費 ＋ 決済手数料 ＋ 配送・梱包、EC の `marketing_cost` ＝ デジタル広告費、直営店の `sga_cost` ＝ 店舗運営費 ＋ 販社販管費（円）。週は Value Chain の販売の週と PPC の週が同じ見込み。違えば差と理由を書く |
| V7 | issues | 直販の `revenue_based_node_cost_not_supported` が 0。代理店の行（G2）は今のまま |
| V8 | 再計算 | 同じ場所の 2 回目、別の場所の実行とも、明細が同じ |
| V9 | 変わってはいけないもの | 正式なサンプルでの Value Chain の出力（C1 が無いので T0 と同じ）、PPC の出力、golden |

## 6. 合格の条件

| # | 条件 |
|---|---|
| S1 | B1〜B3 の記録。B1・B2 が見立てどおり |
| S2 | T1 の (1)〜(4) |
| S3 | V1〜V9 |
| S4 | テスト：単体の追加、領域のテスト、`--full` が緑。golden 全件不変 |
| S5 | 変えたのは `wom/valuechain/`（`masters.py`・`ledger.py`・`policy.py`、必要なら `run.py`）とテスト、`tests/conftest.py` の 1 行、報告書と付録だけ。PPC のコード・正式なサンプル・保護対象のコアは変えない |

**止める理由**：B1 の週・売上が違う、B2 で PPC の出力が変わる、T1 で 72 SGD の行が 0 件か 2 件以上、V3 で 1 行でない費目がある、V5 の合計が合わない、golden が変わる。

**止める理由ではないもの**：V6 で週のまとめ方の違いによる週ごとの差（全期間の合計が合えばよい）。PPC の `sga_cost` の分類が Value Chain の `policy.py` では「その週の費用」であること（新しい G1 の行は業務定義どおり販売費。申し送りに書く）。

## 7. 報告書と記録

- 報告書：`docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_Report.md`、付録 `..._appendix/`（照合のスクリプト、代表の 2 lot の明細、全体の照合の結果、`model_t2` に足した 2 つのファイルの写し）。冒頭に引き継ぎの欄（YAML、`next: owner`）。
- 中身：着手時の SHA、B1〜B3、T0・T1・T2 の結果、S1〜S5、止める理由と申し送り、大杉さんに決めてほしいこと（一言の決定と中身、推奨）。少なくとも次を決める事項として書く：**正式なサンプルに C1 の表と配送の行を入れるか**（段階 6。入れると、正式なサンプルの Value Chain の G1 の未計上が解消し、PPC は変わらない）。
- BS-SEAF の記録：始めと終わりの時刻、人の橋渡し、再利用した知識。**業務定義（GPT-MC）・対応表（Claude君）・この依頼書の三つで、迷った所や足りない情報があったか**。
- commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-08 | 初版 |
