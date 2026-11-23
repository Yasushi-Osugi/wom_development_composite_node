---
handoff:
  case_id: STRATEGY-CONVERT-002
  task_id: promo-convert-slice2-capacity-short
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: "この依頼書の commit 以降の HEAD（着手時の SHA を記録）"
  knowledge_used:
    - id: 販促の業務定義（GPT-MC君）
      version: "v0.1"
      applicability: "docs/design/drafts/WOM_4P_Promotion_Business_Definition_v0.1.md（施策・仮説・費用は同じ。§1.3・§6.4 の供給不足の読み方）"
    - id: 変換の最初の縦の一本
      version: "WOM_Promo_Convert_Slice1_Report.md（bd6bc30・6ba3c26）"
      applicability: "道具（tools/strategy_convert.py・strategy_compare.py）とシート（tests/data/strategy_slice1/）"
    - id: 化粧品の能力不足の案 C3a
      version: "docs/scenarios/cosmetics.md（新しい既定 proportional_week の値）"
      applicability: "能力 COS_Serum 17／14、COS_Cream 13／11。注文残 192、売上 1,100,849,400 円、試算利益 601,449,564 円"
  acceptance:
    ref: "この依頼書 §6"
  status: "試行可能"
  open_items: []
  stop_reasons: []
  next: implement
---

# Request Letter：経営施策の変換 — 2 本目：供給がきつい条件（化粧品の能力不足 C3a）で、同じ追加販促を比べる

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉（WOM Project Owner）／起草：Claude君（2026-11-23）／版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r6m0_BS-SEAF`
- 範囲：既存の道具で案を作って回し、表にする。`tools/strategy_compare.py` に**週別の表と市場別の金額の差の出力**を足す（§3）。テスト、報告書。**エンジン・PPC・Value Chain・正式なサンプル・golden は変えない**
- 出力：`output/strategy_slice2/`（git の対象外）
- **最後のテストは `--changed` だけ**

---

## 一言で

**1 本目と同じ追加販促（SG の EC のクリーム、2028-W10〜W21、週 200 SGD、反応 0%・25%・50%）を、工場の能力が足りないモデル（C3a）で回してください。** 1 本目では工場が増えた需要を作り切れたので、販促の効果がそのまま利益に出ました。今回は、増えた需要が他の市場の供給を押しのけるのか、時期をまたいで後の需要を欠くのか、販促費だけが先に出るのかを、事実として並べます。どの案が良いかは書かないでください。

## 0. 決まっていること

- 施策・仮説・費用・シートは 1 本目と同じ（業務定義 v0.1、変換の定義 v0.2 の Q1〜Q9）。新しい業務の数値は置かない。
- 押し戻し方は新しい既定 `proportional_week`（Start Here R25）。

## 1. 案の作り方

作業：`output/strategy_slice2/ws`。

| 案 | 作り方 |
|---|---|
| C01 P_BASE_SHORT | `cockpit_cases new`（元：正式なサンプル `data/sample/cosmetics-sg-th-2027-2029`）→ `set capacity --sku COS_Serum --max-supply 17 --cap-soft 14`、`--sku COS_Cream --max-supply 13 --cap-soft 11`（全行。助走の行も） |
| C02 LOW・C03 MID・C04 HIGH | C01 を複製 → `tools/strategy_convert`（シート：`tests/data/strategy_slice1/`、`--base-model data/sample/cosmetics-sg-th-2027-2029`、plan は P_PROMO_LOW／MID／HIGH） |

- **先に C01 が C3a の記録を再現することを確かめる**（`docs/scenarios/cosmetics.md` の新しい既定の値：注文残 192〔市場別も〕、総納品 3,864、売上 1,100,849,400 円、試算利益 601,449,564 円）。再現しなければ止める。
- 変換の基準需要 B は正式なサンプルの需要（C3a は能力だけを変えた写しなので、需要は同じ）。変換の道具の「案の写しの対象外の需要が元のモデルと同じか」の検査が通ること。
- 変換は 1 本目と同じ期待値になる（需要の増分 0・0・6・12 lot、追加費用 276,000 円）。違えば止める。

## 2. 回して見ること

1. **LOW は C01 とエンジンの結果が同じで、控除後の比較値だけ 276,000 円低い**（1 本目と同じ確かめ）。
2. **MID・HIGH**（C01 との差）：
   - 対象 `(COS_Cream, SG_EC)` の ①〜⑤。増えた需要のうち、何 lot が当週に届いたか。
   - **他の市場の ④・⑤ の差**（市場 × 年）。増えた分が他の市場から回ったのか、後の年の需要を欠いたのか。クリームの総納品は変わったか（能力が決めるので変わらない見込み。変われば理由）。
   - 美容液への波及（工場は製品ごとに別の能力なので、無い見込み。あれば理由）。
   - 在庫の lot・週、製品の年齢の最大（先入れ先出し）・52 週超の納品。
   - P0 の差の**市場別の内訳**（売上・費用・試算利益）：SG の EC で増えた分と、他の市場で減った分。既存の 15% の広告費の増加。追加費用 276,000 円。控除後の比較値 A の差。
3. **週別の表**（2028-W08〜W30 と、⑤ が出た週）：追加費用（円）、対象の当週出荷の差、他の市場の当週出荷の差、工場の生産の差、在庫の差。「費用が先に出て、効果がどこに出たか（または出なかったか）」を週で読めるように。

## 3. 道具の追加（`tools/strategy_compare.py`）

- `--weekly <開始週> <終了週>`：§2.3 の週別の表を出す（CSV と md）。⑤ が出た週は範囲の外でも行を足す。
- 市場別の金額の差（PPC の台帳の売上・費用・試算利益を市場 × 案で）。比較の道具の既存の関数を使い、二重に作らない。
- テスト：小さな合成の 2 案で、週別の差・市場別の差の和が全体の差に合うこと。

## 4. しないこと

増産の案（販促と増産の組み合わせは次の候補）、新しい業務の数値、押し戻し方の変更、配分の方針（数量枠）を付けること、PPC・Value Chain・エンジンの変更。

## 5. 書き方の注意

- どれが良いかは書かない。
- **⑤ が増えた市場があれば、その量と年**を、対象の増えた ④ と並べて書く（「SG の EC が 6 増え、2029 年の SG の代理店が 6 欠けた」のように）。食い合いを販促の効果と書かない。
- 金額は試算。保有費は未設定なので、在庫の増減は P0 と A に入っていないと書く。
- 1 本目（能力に余裕）との対比を 1 つの表にする（同じ施策で、能力の条件だけが違う）。

## 6. 合格の条件

| # | 条件 |
|---|---|
| S1 | C01 が C3a の記録（新しい既定の値）を再現 |
| S2 | 変換が 1 本目と同じ期待値（需要の増分・追加費用） |
| S3 | LOW がエンジンの結果で C01 と同じ、A だけ −276,000 円 |
| S4 | MID・HIGH の §2.2・§2.3 の表。①＝②＋③、②＝④＋⑤ が鍵ごとに合う。市場別・週別の差の和が全体の差に合う |
| S5 | 1 本目との対比の表 |
| S6 | エンジン・正式なサンプル・golden が変わっていない。`--changed` が通る |

**止める理由**：S1・S2・S3 が合わない。

**止める理由ではないもの**：A が下がる、他の市場の ⑤ が増える、総納品が変わる（理由を書く）。

## 7. 報告書と記録

- 報告書：`docs/development/WOM_Promo_Convert_Slice2_CapacityShort_Report.md`、付録（要約・週別・市場別の表）。冒頭に引き継ぎの欄（YAML、`next: owner`）。着手時の SHA、S1〜S6、§2 の表、1 本目との対比、気づいたこと、大杉さんが実機で確かめる手順（比較の画面で C01 と C03 を並べる手順を含む）。
- commit メッセージの下書き 2 つ（道具とテスト／報告書）。git の操作は大杉さんが行う。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-23 | 初版 |
