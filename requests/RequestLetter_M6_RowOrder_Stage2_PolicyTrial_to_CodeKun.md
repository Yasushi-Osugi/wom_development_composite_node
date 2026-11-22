---
handoff:
  case_id: COCKPIT-M6-005
  task_id: row-order-bias-stage2-policy-trial
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "この依頼書の commit 以降の HEAD（着手時の SHA を記録）"
  knowledge_used:
    - id: 行の順の偏りの直し方の設計
      version: "v0.3（Q1〜Q7 採用）"
      applicability: "requests/WOM_M6_RowOrderBias_FixOptions_DesignMD_v0.3.md §5・§6 段 2"
    - id: 段 0 の影響調査・段 1 の報告
      version: "8b8f181・1a59804"
      applicability: "変わる見込みの 13 モデル、醤油 T1〜T6 の結果、測り方（overflow_by_node）"
    - id: 販促の変換の最初の縦の一本
      version: "WOM_Promo_Convert_Slice1_Report.md"
      applicability: "MID・HIGH の押し戻し（tail と proportional_week）"
  acceptance:
    ref: "この依頼書 §6"
  status: "試行可能"
  open_items: []
  stop_reasons: []
  next: implement
---

# Request Letter：行の順の偏りの直し方 — 段 2：二つの新しい押し戻し方を比べ、既定を決める材料をそろえる（試すだけ）

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉（WOM Project Owner）／起草：Claude君（2026-11-22）／版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`
- 範囲：**試すだけ。** 写しのモデル（`output/` の下）で `planning_config.csv` に `overflow_policy` を 1 行足して回し、表にする。スクリプトは `output/` か付録に置く。**コード・エンジン・正式なサンプル・golden は変えない**
- 出力：`output/roworder_stage2/`（git の対象外）

---

## 一言で

**`tail`（今の動き）・`proportional_week`（その週の数に比例）・`balance_cut_ratio`（累積押戻負担率をそろえる）の 3 方式を、次の三つの場で比べてください。** 結果は表にするだけで、どれが良いかは書かないでください（既定は段 3 で大杉さんが決めます）。

1. **販売開始のずれがあるモデル**：化粧品の能力不足の案（C3a）。二つの新方式の差が出ると見込んでいる場です。
2. **醤油**：同順位の配分（R1、C03）と、正式なサンプル `soysauce-jpy-2027-alloc` そのもの。
3. **golden の 13 モデル全部**：既定を替えたとき、何がどれだけ変わるかの一覧。

## 1. 化粧品の能力不足の案（C3a）

- 写し：`data/sample/cosmetics-sg-th-2027-2029` を `output/roworder_stage2/cos_c3a/<方式>/model` に写し、`docs/scenarios/cosmetics.md` の C3a のとおり `capacity_plan.csv` の全行（助走の行も）を COS_Serum 17／14、COS_Cream 13／11 にする。
- `tail` が C3a の記録（期末の注文残 192 lot、すべてタイの代理店：美容液 104・クリーム 88。売上 1,119,737,280 円、試算利益 607,601,448 円）を再現することを先に確かめる。再現しなければ止める。
- 3 方式で回す。**`balance_cut_ratio` だけ、木の行の順を入れ替えた写しでも 1 回回し**、結果が同じことを確かめる（販売開始のずれがある場での不変性）。
- 表：市場（8 鍵：2 製品 × 4 チャネル）ごとの ①・④（当週・遅配）・⑤、④ ÷ ①、年別の ④ ÷ ①（2027・2028・2029）、工場 × 市場の延べの押し戻しと累積押戻負担率、計画の前に落ちた lot、在庫の lot・週、製品の年齢の最大（先入れ先出し、`tools/shelf_life_check.py --max-age-weeks 52`）、52 週超の納品、P0（報告期間）。

## 2. 醤油

### 2.1 同順位の配分（R1、到達点 6 の C03）

- 写し：`output/cockpit_m6/soy/C03` のモデルと供給の方針（数量枠・`proportional_even`）をそのまま使い、`overflow_policy` だけを替える（3 方式）。
- 表：6 市場の ①〜⑤、④ ÷ ①、④ ÷ ②、同順位の 5 市場の ④ ÷ ① の開き（C03 の `tail` は 4.55 ポイント）、⑤ の要求週、総納品、在庫、P0。

### 2.2 正式なサンプル `soysauce-jpy-2027-alloc`（能力 800、配分なし）

- 段 0 で、計画の前に落ちた lot が 20,408（BE 6,096・FR 6,912・NL 6,100・JP 600・US 各 350）。写しで 3 方式。
- 表：6 市場の ①・④・⑤、④ ÷ ①、開き、落ちた lot の市場別、総納品、在庫、P0。

（21 シフトの R0 の 3 方式は段 1 の T1・T2・T4 にある。回し直さず、段 1 の付録の数を表に並べる。）

## 3. golden の 13 モデル全部（既定を替えたときの影響の一覧）

- 対象：段 0 の「変わる見込み」の 13 モデル（Cookie、apparel-global、apparel-us、ev-europe、ev-thailand、ev-thailand_update、oil、smartphone、smartx、soysauce の 4 つ）。legacy の 3 つは対象外。
- 各モデルを写し、golden と同じプラグインの組で、`proportional_week` と `balance_cut_ratio` を 1 回ずつ回す（26 回）。`tail` は golden の snapshot を使う（回し直さなくてよい。念のため 1 モデルだけ回して golden と一致を確かめる）。
- モデル × 製品ごとに、golden（`tail`）との差：市場の当週出荷・遅配・期末の注文残、④ ÷ ① の市場の間の開き、計画の前に落ちた lot、工場の P・I の合計、PPC の売上・粗利・粗利率、snapshot の `series_md5` が変わったノードの数。
- **休業だけで変わる工場**（ev-europe のドイツ工場、ev-thailand のタイ工場）は、休業の週の lot がどの市場に分かれたかを別に書く。
- 1 モデル終わるごとに結果を `output/roworder_stage2/golden/<モデル>_<方式>.json` に書いてから次へ（途中で止まっても残るように）。書き終えたものは飛ばしてよい。重いもの（smartphone・smartx）は最後に。

## 4. 書き方の注意

- **どれが良いかは書かない**。事実（数・差・どこで差が出たか）だけ。
- 総納品が変わったら、その理由を書く（落ちる lot・生産の時期が変わるため、変わりうる）。
- 市場の間の差は「④ ÷ ① の開き」と「累積押戻負担率」を**別の欄**で書く（負担率は未充足の率ではない）。
- 金額は試算。保有費が未設定のモデルでは、在庫の増減は P0 に入っていないと書く。

## 5. しないこと

既定の変更、golden の作り直し、エンジン・比較の道具の変更、Forward の扱い、優先の表、新しい方式の追加。

## 6. 合格の条件

| # | 条件 |
|---|---|
| S1 | 化粧品 C3a：`tail` が記録を再現。3 方式の表。`balance_cut_ratio` の行の順の入れ替えで結果が同じ |
| S2 | 醤油：C03 の 3 方式と、`soysauce-jpy-2027-alloc` の 3 方式の表。R0 は段 1 の数を並べた |
| S3 | golden の 13 モデル × 2 方式の差の一覧（回せなかったものは理由） |
| S4 | コード・エンジン・正式なサンプル・golden が変わっていない |

**止める理由**：C3a の `tail` が記録を再現しない、`tail` で回したモデルが golden と一致しない、入れ替えで `balance_cut_ratio` の結果が変わる（どの週・どの市場かを書いて止める）。

**止める理由ではないもの**：二つの新方式の差が小さい、総納品が変わる、あるモデルで新方式の方が未充足が増える（どれも事実として書く）。

## 7. 報告書

- `docs/development/WOM_M6_RowOrder_Stage2_PolicyTrial_Report.md`、付録（表・スクリプト・明細の JSON）。冒頭に引き継ぎの欄（YAML、`next: owner`）。着手時の SHA、S1〜S4、§1〜§3 の表、気づいたこと、作り直す手順。
- commit メッセージの下書きを 1 つ（`commit_msg234.txt`）。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-22 | 初版 |
