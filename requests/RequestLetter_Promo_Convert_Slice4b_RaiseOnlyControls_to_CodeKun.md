---
handoff:
  case_id: STRATEGY-CONVERT-004b
  task_id: promo-convert-slice4b-raise-only-controls
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "この依頼書の commit 以降の HEAD（着手時の SHA を記録）"
  knowledge_used:
    - id: 4 本目の報告
      version: "WOM_Promo_Convert_Slice4_ProtectAndCostSensitivity_Report.md（大杉さんの判断の節を含む）"
      applicability: "作業 output/strategy_slice3/ws の C01〜C10、道具の --avoidable・--protect・--holding-rates"
  acceptance:
    ref: "この依頼書 §4"
  status: "試行可能"
  open_items: []
  stop_reasons: []
  next: implement
---

# Request Letter：経営施策の変換 — 4 本目の補い：「増産だけ 18 週・24 週」の対照を足し、延ばした案の販促の効果を切り分ける

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉（WOM Project Owner）／起草：Claude君（2026-11-23）／版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`
- 範囲：**案を 2 つ足して回し、表を作り直すだけ。道具・エンジン・PPC・Value Chain・正式なサンプル・golden は変えない**（コードを変えないならテストは不要）
- 作業：`output/strategy_slice3/ws` に案を足す（C01〜C10 は回し直さない）。出力 `output/strategy_slice4b/`

---

## 一言で

**4 本目の C07（販促 25%＋増産 18 週）・C08（販促 50%＋増産 24 週）は、「増産だけ（12 週）」と比べると、増産を延ばした効果と販促の効果が混ざっていました。** 販促なしで増産だけを延ばした対照を 2 つ足し、同じ増産の下で販促を足す価値を切り分けてください（大杉さんの判断、2026-11-23）。どれが良いかは書かないでください。

## 1. 案

| 案 | 作り方 |
|---|---|
| C11 増産だけ 18 週 | C01 を複製 → `set planned-output --sku COS_Cream --cap-soft 12 --from-week 2028-W06 --to-week 2028-W23` → 確保費の行 `planned_output_raise`（2028-W06〜W23、低・中） |
| C12 増産だけ 24 週 | C01 を複製 → `set planned-output ... --from-week 2028-W06 --to-week 2028-W29` → 確保費の行（2028-W06〜W29） |

C11 は C07 から販促を除いた案、C12 は C08 から販促を除いた案になる（計画の生産量の設定・確保費の行が同じことを確かめる）。

## 2. 表

1. **同じ増産の下で販促を足す価値**：C07 − C11、C08 − C12（ΔP0・控除後の比較値〔低・中 × 保有費なし・10% × 店舗費用の割合 100%・50%・0%〕・対象の ④・他の市場の ④・⑤〔2029 年〕）。3 本目の C04 − C02・C06 − C02 と並べる（増産 12 週・18 週・24 週で、販促を足す価値がどう変わるか）。
2. **増産を延ばす価値**：C11 − C02、C12 − C02（販促なし）。増えた良品が、どの市場・年の不足を埋めたか。
3. **守る供給の判定**（4 本目と同じ下限）に C11・C12 を足す。
4. **経営者に示す 1 枚の表**を作り直す：列「増産の枠を何に使うか」は、**同じ増産の長さの「増産だけ」と比べた差**にする（C04・C06 は C02、C07 は C11、C08 は C12）。4 本目の表の「延ばした 6 週で販促を賄う」等の読みは使わない。

## 3. 書き方の注意

- どれが良いかは書かない。採用は保留（D6）。
- 週額は仮置き（GPT-MC君の確認：18 週・24 週も同じ週額を試行用に続けてよい。実見積は未確認）。

## 4. 合格の条件

| # | 条件 |
|---|---|
| S1 | C01〜C10 を回し直していない。C11・C12 の増産の設定が範囲の週だけで、C07・C08 と同じ |
| S2 | §2 の 1〜4 の表。①＝②＋③、②＝④＋⑤ が鍵ごとに合う |
| S3 | コード・エンジン・正式なサンプル・golden が変わっていない |

**止める理由**：C11・C12 の増産の設定・確保費の行が C07・C08 と一致しない。

## 5. 報告書

- 4 本目の報告書に節を足すのではなく、`docs/development/WOM_Promo_Convert_Slice4b_RaiseOnlyControls_Report.md`（短くてよい）と付録。冒頭に引き継ぎの欄（YAML、`next: owner`）。
- commit メッセージの下書きを 1 つ（`commit_msg243.txt`）。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-23 | 初版 |
