---
handoff:
  case_id: BSSEAF-COS-G1
  task_id: G1-S6-sample-adoption
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "commit_msg200 の commit（G1 の実装）の後の先頭"
  knowledge_used:
    - id: G1 の報告書（Code君）
      version: "2026-11-08"
      applicability: "T2 の結果、付録 model_t2_added の 2 ファイル"
  acceptance:
    ref: "この依頼書 §3"
  evidence:
    - docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_Report.md
  status: "試行可能"
  open_items: []
  stop_reasons: []
  handover_notes: []
  next: implement
---

# Request Letter：G1 を正式な化粧品のサンプルに反映する（段階 6）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-11-08）
- 版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`（着手時の SHA を記録する）
- 大杉さんの判断（2026-11-08）：**正式なサンプルに新しい表と配送の行を入れる**。G1 は直販について閉じる
- 範囲：正式なサンプル `data/sample/cosmetics-sg-th-2027-2029/` の 2 ファイルと README。**コードは変えない**

## 一言で

**G1 の試行で写しのモデルに足した 2 つのファイルを正式なサンプルに写し、サンプルで G1 が計上され、PPC が変わらないことを確かめてください。**

## 1. 変更

| ファイル | 変更 |
|---|---|
| `vc_sales_cost_rule.csv` | 新しく置く。中身は `docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_appendix/model_t2_added/vc_sales_cost_rule.csv` と同じ |
| `ppc_edge_cost_rule.csv` | 付録の同名のファイルと同じにする（`SG_EC->CONSUMER` の `delivery_packing_cost` の 2 行が増えるだけ。ほかの行は今と同じことを確かめる） |
| `README.md` | 「期待する結果」の Value Chain の行（利益の差 303,211,896 円 → 22,196,148 円、G2 だけ）と、「既知の限界」の G1 の項（解決済み、報告書へのリンク）。「金額の規則」の文に `vc_sales_cost_rule.csv` を足す。数字は実行の結果から書く |

## 2. 確かめること

1. 正式なサンプルで Value Chain を実行：G1 の行の全期間の合計 281,015,748 円、直販の `revenue_based_node_cost_not_supported` が 0、利益の差（Value Chain − PPC）が 22,196,148 円。結果は報告書の T2 と同じ。
2. PPC の出力が、変更の前と同じ（バイト単位）。
3. テスト：`python -m tools.quick_check --changed` が選ぶ領域と golden。サンプルの数字を固定しているテストが落ちたら、その期待値を新しい結果に直してよい（直した箇所と理由を報告に書く）。PPC や golden の期待値が変わったら止める。

## 3. 合格の条件

| # | 条件 |
|---|---|
| S1 | §2 の 1・2 が期待どおり |
| S2 | テストが緑。golden は不変 |
| S3 | 変えたのはサンプルの 2 ファイルと README（と、直したテストの期待値があればそれ）だけ |

**止める理由**：PPC の出力が変わる、golden が変わる、G1 の合計が 281,015,748 円にならない。

## 4. 報告

G1 の報告書 `docs/development/WOM_BSSEAF_Cosmetics_G1_SalesBasedCosts_Report.md` の末尾に「段階 6：正式なサンプルへの反映」の節を足す（着手時の SHA、§2 の結果、変えたファイル）。commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に（**既にある番号は上書きしない**）。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-08 | 初版 |
