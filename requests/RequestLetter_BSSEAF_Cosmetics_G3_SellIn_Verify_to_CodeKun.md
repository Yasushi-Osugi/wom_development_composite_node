---
handoff:
  case_id: BSSEAF-COS-G3
  task_id: G3-T1-verify-sellin-recognition
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: 7777b2a
  knowledge_used:
    - id: G3 業務定義（GPT-MC）
      version: v0.1
      applicability: "§4 期待結果、§5 重複防止の条件。シンガポール販社 → 外部代理店のクリームの卸売、代表 Lot 1 件"
    - id: WOM-SEM-SUPPLY-ALLOCATION-001
      version: "0.7"
      applicability: "受渡点・実納品の意味（§2・§3）"
  acceptance:
    ref: "この依頼書 §5"
  evidence:
    - docs/design/drafts/WOM_G3_SellIn_Business_Definition_v0.1.md
    - "コード確認（7777b2a）：wom/valuechain/ledger.py の _transfer・_receipt・_consumer、LINE_COLS"
    - "docs/development/WOM_BSSEAF_Cosmetics_Money_M0_Report.md §6 T13"
  status: "試行可能"
  open_items: []
  stop_reasons: []
  handover_notes:
    - "コードの変更は要らない見込み。Value Chain は既に DC の実出荷の週に卸売の売上を 1 件立て、代理店の leaf の出荷は観測（グループの売上に足さない）として記録している"
  next: implement
---

# Request Letter：G3 業務定義（sell-in の売上の計上週）を、今の WOM で満たすかの検証

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-11-08）
- 版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`（ブランチ `wom-v1r6m0_BS-SEAF`。この依頼書は大杉さんが先に commit する。着手時の SHA を報告書に記録する）
- 前提：**G3 業務定義書 v0.1**（`docs/design/drafts/WOM_G3_SellIn_Business_Definition_v0.1.md`、GPT-MC 作成、大杉さんの採用判断を反映、2026-11-08）
- 種別：**検証だけ**。コード・正式なサンプル・golden・保護対象のコアは変えない。実行の出力は `output/` の下（git の対象外）

---

## 一言で

**G3 業務定義（出荷した週に、シンガポール販社が卸売の売上を 1 件だけ計上する）を、今の Value Chain が改修なしで満たしていることを、実行して確かめてください。**

## 0. 背景

金額の試行 M0 で、代理店向けの売上の週が、Value Chain と PPC で 1 週ずれていた（G3）。Value Chain は DC の出荷の週、PPC は代理店の leaf の出荷の週に売上を立てる。

経営コンサルタントの役（GPT-MC）が、この卸売の計上の業務定義を書き、大杉さんが「出荷時に支配が移る」（段階 D の D-2、出荷時の認識）を採用した。代表の Lot `COS_Cream:SG_Distributor:2028-W29:00002` で、**2028-W28 に 1 件・税抜 1,488 SGD（24 個 × 62 SGD）、2028-W29 は 0 件**が期待の結果である。

この検証は、**業務の専門家の役が書いた定義を、別の担当が WOM の入力・処理・出力に対応付けて確かめる**最初の試行でもある。

## 1. 業務定義と、今の WOM の対応（設計担当の見立て。コード確認、`7777b2a`）

### 1.1 §4 期待結果

| 業務定義 | 今の WOM（Value Chain） | 見立て |
|---|---|---|
| 2028-W28：DC の実出荷で、シンガポール販社が卸売の売上を 1 件・1,488 SGD | `wom/valuechain/ledger.py` の `_transfer()`：`DC_SG → SG_Distributor` の出荷で、売り手（`DC_SG` の法人＝シンガポール販社）に、`kind=revenue`・`scope=external`・`family=sale`・`price_type=wholesale` の明細を 1 件立てる。単価は `vc_price_rule.csv` の `wholesale`（クリーム SGD 62）、数量は出荷の個数（1 lot ＝ 24 個）。M0 の T13 で、この Lot の売上の週は 2028-W28 と記録されている | 満たす見込み（M0 で実行確認済みの観測あり） |
| 2028-W29：代理店の受入（P）・代理店の leaf の実出荷（S）で、売上は 0 件 | 受入は `_receipt()`：在庫の所在を移すだけで、売上の明細を立てない（外部の代理店の lot はノードの費用も立てない）。leaf の出荷は `_consumer()`：外部の在庫なので `kind=observation_sale`・`scope=observation` の観測の明細になり、グループの売上に足さない | 満たす見込み |
| 出荷が未発生の間は 0 件 | 明細は出荷の記録から作るので、出荷が無ければ明細も無い | 満たす（作りによる） |
| 記録の欠落で出荷を確かめられないときは「未確認」として保留 | WOM の出荷は計画から作られ、「記録の欠落」という状態が無い | **対象外**（実績の記録を取り込むときの論点。申し送り） |

### 1.2 §5 重複を防ぐ条件

| 業務定義 | 今の WOM | 見立て |
|---|---|---|
| 1. 売り手・買い手・卸売の区間・Lot_ID の組で、出荷・受入・leaf の実出荷を同じ卸売として照らす | 明細（`vc_money_lines.csv.gz`）は `lot_id`・`entity`（売り手）・`counterparty`（買い手）・`node`（出荷元）・`src_id`（出荷の ID）を持つ。`vc_shipments.csv.gz` の出荷の ID と区間で、出荷・受入・leaf の出荷を Lot_ID で突き合わせられる | 満たす（照合は検証のスクリプトで行う） |
| 2. 一つの試算で、同じ卸売の有効な売上の明細は最大 1 件。ほかの事象・PPC は照合に使い、加算しない | 卸売の売上は出荷 1 回につき 1 件。leaf の出荷は観測の明細（売上に足さない）。PPC は別の出力（`ppc/`）で、Value Chain の売上に入らない | 満たす見込み。**PPC は leaf の出荷の週（W29）に売上を立てる別の方式のまま**（申し送り） |
| 3. 同じ記録の再取込・再計算でも 1 件 | Value Chain は実行のたびに計画から明細を全部作り直し、出力のファイルを書き直す（追記しない） | 満たす見込み（同じ出力の場所に 2 回実行して確かめる） |

**結論の見立て：コードの変更は要らない。** 改修なしの検証を行う。差分は「記録の欠落」の扱い（対象外）と、PPC の計上の週（別の方式として残る）の 2 点で、どちらも申し送り。

## 2. 先に確かめること

| # | 確かめること |
|---|---|
| B1 | 正式なサンプル `data/sample/cosmetics-sg-th-2027-2029` が、M0（金額の規則を持つモデル）であること。Value Chain の実行が、サンプルのフォルダを書き換えないこと（実行の前後でハッシュが同じ） |
| B2 | `tools/valuechain_run.py` の引数（`--model-dir`、`--out`、`--plugins`）と、出力（`vc_money_lines.csv.gz`、`vc_shipments.csv.gz`、`vc_v*_weekly.csv`、`vc_observation_weekly.csv`、`ppc/`） |
| B3 | 代表の Lot `COS_Cream:SG_Distributor:2028-W29:00002` が、今の計画でも同じ週（DC の出荷 2028-W28、受入・leaf の出荷 2028-W29）であること。違えば止めて報告する（業務定義の前提が変わるため） |

## 3. 再現の手順

1. `python -m tools.valuechain_run --model-dir data/sample/cosmetics-sg-th-2027-2029 --out output/g3_verify/run_1`（`--plugins` は既定＝golden の組）。
2. 同じコマンドを、**同じ出力の場所にもう一度**実行する（再計算でも 1 件の確認）。2 回目の前に 1 回目の出力を `output/g3_verify/run_1_first/` に写しておく。
3. 別の出力の場所 `output/g3_verify/run_2` にも 1 回実行する（再現の確認）。
4. 検証のスクリプト（付録 `scripts/verify_g3.py`）で、§4 の明細を照らす。スクリプトは出力を読むだけで、WOM のコードを呼び出して計算し直さない。

## 4. 照らす明細

### 4.1 代表の Lot（業務定義 §4 そのもの）

`vc_money_lines.csv.gz` から `lot_id = COS_Cream:SG_Distributor:2028-W29:00002` の行を全部取り出し、表にする（列：`week`、`kind`、`scope`、`family`、`price_type`、`entity`、`counterparty`、`node`、`amount_orig`、`currency_orig`、`src_id`）。

| # | 照らすこと | 期待 |
|---|---|---|
| L1 | `kind=revenue`・`scope=external` の行 | **1 行**。`week=2028-W28`、`node=DC_SG`、`entity`＝シンガポール販社、`counterparty`＝外部代理店の法人、`price_type=wholesale`、`amount_orig=1488`、`currency_orig=SGD` |
| L2 | 2028-W29 の `kind=revenue` の行 | **0 行** |
| L3 | `kind=observation_sale` の行 | 1 行（2028-W29、`node=SG_Distributor`）。グループの売上の集計に入らない |
| L4 | 出荷・受入・leaf の出荷の対応 | `vc_shipments.csv.gz` で、この Lot の `DC_SG → SG_Distributor` の出荷（2028-W28）、受入（2028-W29）、leaf の出荷（2028-W29）が、同じ Lot_ID でたどれる。L1 の `src_id` が、その出荷の ID と一致する |

### 4.2 全部の卸売（§5 の条件を全体で）

| # | 照らすこと | 期待 |
|---|---|---|
| A1 | 外部代理店への出荷（`DC_SG → SG_Distributor`、`DC_TH → TH_Distributor`）1 件ごとに、`kind=revenue`・`scope=external` の行の数 | **すべて 1 行**（0 行・2 行以上が無い） |
| A2 | その行の週 ＝ その出荷の週 | すべて一致 |
| A3 | 外部代理店の Lot で、受入の週・leaf の出荷の週に `kind=revenue` の行 | 0 行 |
| A4 | 金額 ＝ 個数 × `vc_price_rule.csv` の卸価格（SKU・区間ごと） | すべて一致 |
| A5 | 代理店の卸売の売上の全期間の合計 | M0 報告書 T13 の Value Chain の値（443,922,960 円）と一致 |

### 4.3 再取込・再計算（§5 の 3）

| # | 照らすこと | 期待 |
|---|---|---|
| R1 | 同じ場所への 2 回目の実行の後の `vc_money_lines.csv.gz` | 1 回目と行の数・中身が同じ（2 倍にならない） |
| R2 | 別の場所の実行（`run_2`）と比べる | 明細が同じ（ハッシュ、または `line_id` を除いた全列が一致） |

### 4.4 参考（照合だけ。合否に使わない）

- PPC の出力で、同じ Lot の売上の週（2028-W29 の見込み）と金額。Value Chain の売上には加算されていないこと。
- `vc_ppc_comparison.csv` の、代理店の売上の週の差（全 Lot で 1 週の見込み）。

## 5. 合格の条件

| # | 条件 |
|---|---|
| S1 | B1〜B3 の結果（サンプルが書き換わらない、代表の Lot の週が業務定義の前提と同じ） |
| S2 | L1〜L4 がすべて期待どおり（業務定義 §4） |
| S3 | A1〜A5 がすべて期待どおり（業務定義 §5 の 1・2 を全部の卸売で） |
| S4 | R1・R2 がすべて期待どおり（業務定義 §5 の 3） |
| S5 | コード・正式なサンプル・golden・保護対象のコアに変更が無い（`git status` で、追加は報告書・付録・commit の下書きだけ） |

**止める理由**：B3 で代表の Lot の週が違う。L1・A1 で売上の行が 0 件か 2 件以上ある。R1 で 2 回目の実行の後に行が増える。どれかに当たったら、**コードを直さずに**止めて報告する（その場合は、差分に絞った実装の仕様を設計担当が書く）。

**止める理由ではないもの**：PPC が 2028-W29 に売上を立てていること（別の方式。§4.4 の参考）。「記録の欠落」の扱いが無いこと（対象外）。

## 6. 報告書と記録

- 報告書：`docs/development/WOM_BSSEAF_Cosmetics_G3_SellIn_Verify_Report.md`（付録 `..._appendix/`：検証のスクリプト、代表の Lot の明細の表、全体の照合の結果）。冒頭に引き継ぎの欄（YAML、`next: owner`）。
- 中身：着手時の SHA、B1〜B3、§4 の表、S1〜S5 の結果、止める理由と申し送り、大杉さんに決めてほしいこと（一言の決定と中身を並べて書く）。
- 申し送りの候補として、少なくとも次を書く：
  1. PPC は代理店の leaf の出荷の週に売上を立てる（業務定義の D-2 と違う方式）。PPC をそろえるかは別の判断。
  2. 「記録の欠落で未確認」は、計画から作る出荷には無い。実績の取り込みを扱うときの論点。
- BS-SEAF の記録：始めと終わりの時刻、人の橋渡し、再利用した知識。**業務の専門家の役（GPT-MC）が書いた定義を、そのまま検証の条件に使えたか**（足りない情報、読み違えやすい所があったか）も書く。
- commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-08 | 初版 |
