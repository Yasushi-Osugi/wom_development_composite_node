---
handoff:
  case_id: KNOWLEDGE-CH1-RECONCILE
  task_id: knowledge-ch1-one-lot-reconcile
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "この依頼書の commit 以降の HEAD（着手時の SHA を記録）"
  knowledge_used:
    - id: 第 1 章の説明案
      version: "docs/knowledge/accounting_scsim/02_Ch1_OneLot_Draft_v0.2.md"
      applicability: "§3.5 の 1 ロットの表、§6 のタイ、§8 の照合の予定"
    - id: GPT-MC君の会計レビュー
      version: "docs/design/drafts/WOM_Knowledge_S1_Accounting_Review_v0.1.md §9.2（受入の条件）・§7.5（E2・E3）"
      applicability: "照合の条件と期待結果"
  acceptance:
    ref: "この依頼書 §4"
  status: "試行可能"
  stop_reasons: []
  next: implement
---

# Request Letter：知識体系 第 1 章 — 代表の 1 ロットを Value Chain の実際の出力と照合する

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉（WOM Project Owner）／起草：Claude君（2026-11-28）／版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`
- 範囲：**照合だけ。コード・エンジン・PPC・Value Chain・正式なサンプル・golden は変えない**（コードを変えないならテストは不要）。実行の出力は `output/knowledge_ch1/`（git の対象外）

---

## 一言で

知識体系の第 1 章（1 ロットの一生と金額）の数字は、モデルのマスターからの手計算です（GPT-MC君も独立に検算して一致）。**これを Value Chain の実際の出力と照合し、教材に載せてよい数字か確かめてください**（判断票 P4、2026-11-28）。合わなければ、どちらが正しいかを決めずに、違いの出どころを報告してください。

## 1. 実行

1. `python -m tools.valuechain_run --model-dir data/sample/cosmetics-sg-th-2027-2029 --out output/knowledge_ch1/base`（`--plugins` は既定）。
2. 確認問題 E2 の写し：`vc_price_rule.csv` の `WH_JP_Released->DC_SG`・`COS_Cream` の intercompany を 5,000 → 5,500 にした写しで実行（`output/knowledge_ch1/e2_tp5500`）。PPC の `ppc_transfer_price_rule.csv` の `Factory_JP`・`COS_Cream` の fixed_price も 5,500 にそろえる。
3. 確認問題 E3 の写し：`ppc_tariff_rule.csv` の `WH_JP_Released->DC_TH`・`COS_Cream` の `tariff_rate` を 0.3 にした写しで実行（`output/knowledge_ch1/e3_tariff30`。G4 の T0 と同じ置き方）。

## 2. 照合（出力：`vc_money_lines.csv.gz`・`vc_shipments.csv.gz`・`vc_inventory_weekly.csv`・`vc_unrealized_weekly.csv`）

### 2.1 代表の 1 ロット（公式 EC のクリーム）

- `COS_Cream`・`SG_EC` の Lot を 1 つ選ぶ。**できれば DC か EC で週末をまたいで未販売だった週がある Lot**（`vc_inventory_weekly.csv` で探す）。無ければ、実在する所在（輸送中など）の Lot を選び、その事実を書く（期末在庫の週を作らない）。
- その Lot の全部の明細を表にする（列：`week`・`kind`・`scope`・`family`・`price_type`・`entity`・`counterparty`・`node`・`amount_orig`・`currency_orig`・報告通貨の額・`src_id`）。Lot_ID・出荷の識別子・各週（製造・倉庫の受入・法人間の出荷・DC の受入・EC への移動・消費者への販売）を記録する。

照らす値（第 1 章 §3.5、1 ロット 24 個、円）：

| 確認 | 期待 |
|---|---|
| 原料・加工・各運賃 | 1 個あたりのマスター × 24。同じ費用を重ねない |
| 法人間の取引 | 日本本社の売上 120,000、対応する原価 47,520、粗利益 72,480。販社の取得原価に海上運賃 1,440 を再び足さない |
| 倉庫費 | 受入のときに 720 を 1 回。滞留の週数で再計上しない |
| 未販売の週末 | DC にあれば、販社の在庫 121,380・連結 48,900・内部の利益 72,480。EC 側なら 122,208・49,728・72,480。所在と積んだ原価に合う残高 |
| 外部売上 | 361,560 を 1 取引 |
| 外部販売の原価・粗利益 | 販社 122,208・239,352、連結 49,728・311,832 |
| 販売費 | 売上比率の 3 費目 108,468（販社共通管理費 36,156・決済 18,078・広告 54,234）＋ 配送・梱包 8,280 |
| 販売の週と全期間 | 倉庫費が以前の週なら、販売の週の連結の試算損益 195,084。ロットの費用を通算した採算 194,364。報告期間の外に落ちた費用があれば別欄 |
| 未実現利益 | 未販売の残高と、外部販売の週に実現する増減を分ける。二度消去・二度実現しない |
| 件数 | 外部売上 1 件、販売費 4 費目。評価の基準（V1・法人・グループ）ごとに立つ原価の行を、同じ売上の重複として数えない |
| 未評価 | 価格・為替などの欠けを 0 で補わない |

### 2.2 タイの代理店へのロット（第 1 章 §6）

- `COS_Cream`・`TH_Distributor` の Lot を 1 つ。日本本社 → タイの DC が法人間の売上にならないこと、代理店への卸売（1,600 バーツ × 24 個）、課税価格の記録（`vc_customs_valuation.csv`：5,000 ＋ 70 ＝ 5,070 円 × 24）。
- E3（税率 30%）：同じ Lot で関税 36,504 円が受入の週に在庫原価に 1 回入り、卸売の週の売上原価が 36,504 円増え、連結の試算利益が同じだけ減る。期間費用として重ねて引かれていない。

### 2.3 E2（法人間の価格を 5,500 円に）

同じ代表の Lot で：日本本社の粗利益 3,020 → 3,520 円／個、販社の粗利益 9,973 → 9,473 円／個、未販売の内部の利益が 1 ロット 12,000 円増える。連結の粗利益 311,832 と全期間の採算 194,364 は変わらない。モデル全体の連結の試算利益（P0）も変わらないことを確かめる（変わったら、どの費用が法人間の価格を基礎にしているかを報告する）。

## 3. 書き方の注意

- 手計算と出力のどちらが正しいかを決めない。違いがあれば、明細の行・週・費目・法人で出どころを示す。
- 第 1 章の「確認の状態」を書き換えるのは Claude君。報告書には照合の結果だけを書く。

## 4. 合格の条件

| # | 条件 |
|---|---|
| S1 | 代表の公式 EC の Lot の各金額が §2.1 の表と一致（または違いの出どころが明細で示されている） |
| S2 | 未販売の週末の残高（所在つき）が示されている。無ければその事実 |
| S3 | タイの Lot と E3 の関税の動きが §2.2 のとおり（または違いの出どころ） |
| S4 | E2 で連結の粗利益・全期間の採算・P0 が変わらない（または違いの出どころ） |
| S5 | コード・正式なサンプル・golden が変わっていない |

**止める理由**：正式なサンプルの実行が既存の記録（G1〜G5 の報告の合計）を再現しない。

## 5. 報告書

- `docs/development/WOM_Knowledge_Ch1_OneLot_Reconcile_Report.md` と付録（代表の Lot の明細の CSV、照合のスクリプト）。冒頭に引き継ぎの欄（YAML、`next: owner`）。
- commit メッセージの下書きを 1 つ（`commit_msg248.txt`）。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-28 | 初版 |
