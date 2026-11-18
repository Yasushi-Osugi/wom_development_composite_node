---
handoff:
  case_id: COCKPIT-M6-003
  task_id: row-order-bias-stage0-impact-survey
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "この依頼書の commit 以降の HEAD（着手時の SHA を記録）"
  knowledge_used:
    - id: 行の順の偏りの直し方の設計
      version: "v0.3"
      applicability: "requests/WOM_M6_RowOrderBias_FixOptions_DesignMD_v0.3.md §1（E1〜E3）・§6 段 0"
    - id: 到達点 6 の報告書
      version: "9c5ba48 ＋ 訂正"
      applicability: "§3 原因の調べ方（r0_probe の包み方）"
  acceptance:
    ref: "この依頼書 §5"
  status: "試行可能"
  open_items: []
  stop_reasons: []
  next: implement
---

# Request Letter：行の順の偏りの直し方 — 段 0：golden のどのモデルが変わりうるかを調べる（読むだけ）

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉（WOM Project Owner）／起草：Claude君（2026-11-18）／版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`
- 範囲：**読むだけ。** 小さな調査のスクリプト（`tools/` か `output/` の下）と報告書。エンジン・PPC・Value Chain・正式なサンプル・golden は変えない
- 出力：`output/roworder_stage0/`（git の対象外）

---

## 一言で

**Backward が工場の能力を超えた週に lot の並びの末尾を前の週へ押し戻す所（設計書 v0.3 の E2・E3）が、golden の 16 モデルのどこで働いているかを数えてください。** 後で押し戻し方を替えたとき、どのモデルの golden が変わりうるかの一覧を先に作るためです。

## 1. 数えること

### 1.1 影響の候補（CSV・コードから。計画は回さない）

モデル × 製品 × 工場（mom）ごとに：能力（`capacity_plan.csv` の cap_hard・cap_soft、`demand_envelope`）か休業（`holiday_calendar.csv` の supply_closure・`operating_calendar.csv` の 0 shift）がかかるか、その工場の下の市場（leaf_out）の数。**候補 ＝ 能力か休業がかかり、市場が 2 つ以上**。

### 1.2 実測（計画を回して）

golden と同じプラグインの組（各モデルの `recommended_plugins`）で headless の計画を回し、`_apply_mom_cap_backward` を**自分のスクリプトの中で包んで**読む（到達点 6 の `r0_probe.py` と同じやり方。エンジンのファイルは変えない）。工場 × 製品ごとに：

| 項目 | 中身 |
|---|---|
| 超過の週 | はみ出し n > 0 の週の数（休業の週を除く） |
| 複数の市場の超過の週 | そのうち、週の並びに市場が 2 つ以上ある週の数 |
| 休業の週 | 休業で lot がまるごと押し戻された週の数（E3） |
| はみ出しの延べ | 押し戻した lot の延べの数 |
| 落ちた lot | 計画の最初の週を超えて past_due になった lot の数（市場別） |

**判定**：「複数の市場の超過の週」か「休業の週（市場が 2 つ以上）」が 1 以上なら、**押し戻し方を替えると golden が変わる見込み**。0 なら変わらない見込み。

## 2. 重い処理の注意（前回、途中で止まったため）

- **モデルを 1 つずつ回し、1 つ終わるごとに結果を `output/roworder_stage0/<モデル>.json` に書いてから次へ**。途中で止まっても、終わったモデルの結果が残るように。
- 書き終えたモデルは、やり直すときに飛ばしてよい（ファイルがあれば読む）。
- rice は大きい（177 週）。最後に回す。時間がかかりすぎるなら、候補（§1.1）だけ書いて「実測は未」と報告してよい。
- 最後の報告は短く。表はファイルに書き、画面には要点だけ。

## 3. しないこと

エンジンの変更、押し戻し方の新しい方式の実装（段 1）、golden の作り直し、テストの全段の実行（コードを変えないので不要）。

## 4. 報告書

`docs/development/WOM_M6_RowOrder_Stage0_ImpactSurvey_Report.md`（短くてよい）、冒頭に引き継ぎの欄（YAML、`next: owner`）。着手時の SHA、§1.1 と §1.2 の表（**候補と実測を分ける**）、**変わる見込みのモデルの一覧**、気づいたこと（例：休業だけで効くモデル）。調査のスクリプトは付録に。commit メッセージの下書きを 1 つ（`commit_msg230.txt`）。git の操作は大杉さんが行う。

## 5. 合格の条件

| # | 条件 |
|---|---|
| S1 | 16 モデルすべてで §1.1 の候補を表にした |
| S2 | §1.2 の実測を表にした（回せなかったモデルは理由を書く） |
| S3 | 変わる見込みのモデルの一覧がある |
| S4 | エンジン・正式なサンプル・golden が変わっていない |

**止める理由**：包んだ計画の結果が golden と食い違う（包み方が計画を変えている疑い。どのモデルかを書いて止める）。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-18 | 初版 |
