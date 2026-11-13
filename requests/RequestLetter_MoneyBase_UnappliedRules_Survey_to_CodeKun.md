---
handoff:
  case_id: MONEYBASE-002
  task_id: unapplied-rule-rows-survey
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: 5fa18f3
  knowledge_used:
    - id: smartx の運賃の調査の報告書（Code君）
      version: "2026-11-13（b7a2ed1）"
      applicability: "§依頼の外で見つけたこと：SmartX・SmartXNext の区間の運賃と関税 16 行が、鍵が supply point 経由のため一度も引かれていない。PPC は警告を出さない"
    - id: 金額基盤の棚卸し表 v0.1
      version: "2026-11-13"
      applicability: "§1 の表（smartphone の関税 6 行も supply point 起点）、§2 の #1〜#4"
  acceptance:
    ref: "この依頼書 §4"
  status: "試行可能（GUI の段 1 の報告の後に着手）"
  open_items: []
  stop_reasons: []
  handover_notes:
    - "大杉さんの判断（2026-11-13）：国際輸送の運賃は区間だけ（DC のノードの運賃は消す）／SmartX・SmartXNext も Pro と同じ書き方にそろえる／直す前に全サンプルで洗い出す／PPC に警告を足すかは洗い出しの結果を見て決める"
  next: implement
---

# Request Letter：全サンプルで「一度も引かれていない金額の規則の行」を洗い出す（調査だけ）

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉／起草：Claude君（2026-11-13）／版：v0.1
- 基準：`5fa18f3`（着手時の SHA を記録）
- 範囲：**調査だけ。コード・サンプル・golden を変えない。** 集計の道具と出力は `output/moneybase_unapplied/`（git の対象外）。報告書の付録に道具の写しを置く
- 順番：**GUI の段 1（`RequestLetter_Cockpit_Stage3_Step1_CasesAndRunner_to_CodeKun.md`）の報告が終わってから**着手する。golden を含むテストや headless の実行を、段 1 の作業と同時に走らせない（助走の CSV の書き込みが競合する。CLAUDE.md「テスト実行時の注意」）

## 一言で

**smartx で、金額の規則の行（区間の運賃・関税）が、鍵が合わないために一度も使われず、関税が 0 で計上されていました。PPC は警告を出しません。同じことがほかのサンプルで起きていないか、全サンプルで洗い出してください。直すのは、結果を見て大杉さんが決めてからです。**

## 1. 対象と数え方

対象：`data/sample/` の golden のある 16 モデル（`rice-japan-2027-2028_BK260613_1515` は対象外）。golden と同じプラグインの組で headless を実行し、PPC の明細と突き合わせる。golden の snapshot と一致することを確かめてから使う。

| 規則のファイル | 「引かれていない行」の定義 |
|---|---|
| `ppc_edge_cost_rule.csv`、`ppc_tariff_rule.csv` | 率か額が 0 でない行のうち、その `edge_id` × `product_id` が、PPC の明細（`ppc_event_ledger.csv`）に 1 件も出ないもの |
| `ppc_node_cost_rule.csv` | 同じく、`node_id` × `product_id` × `cost_type` が明細に 1 件も出ないもの |
| `ppc_supplier_cost.csv`、`ppc_market_price.csv`、`ppc_transfer_price_rule.csv` | その鍵が明細に 1 件も出ないもの |
| 共有の規則（`data/ppc`、宣言したモデルだけ） | モデルが読んだ行について同じ |
| Value Chain のあるモデル（cosmetics・Cookie・soysauce-jpy-2027-alloc） | `vc_price_rule.csv`・区間の費用・関税の行のうち、Value Chain の明細（`vc_money_lines.csv`）に 1 件も出ないもの |

明細との対応は、`source_rule`・`edge_id`・`node_id`・`product_id`・`ppc_event_type` で取る。0 の行（明示の 0）は別に数える（「引かれていない」と「0 を引いた」を分ける）。

## 2. 引かれていない行ごとに調べること

| # | 問い |
|---|---|
| Q1 | なぜ引かれないか。型に分ける：(a) 鍵が supply point 経由など、PPC・Value Chain が作る区間の鍵と合わない／(b) その製品 × ノード・区間が計画の木に無い／(c) 実出荷が無い（需要 0 など。規則は正しい）／(d) ほかの行に先に当たって使われない／(e) その他（説明を書く） |
| Q2 | 業務として引かれるべき行か（(a)・(b) は多くが「引かれるべき」。(c) は問題なし） |
| Q3 | 引かれるべきなら、抜けている額の概算（その区間・ノードを実際に通った数量 × 率・額。関税は基礎の額 × 率）。何を仮定したかを書く |
| Q4 | 逆向きの確認：同じ輸送・同じ費用が、別の鍵の行で既に計上されていないか（smartx の DC のノードの運賃のように、直すと二重になるもの） |

## 3. あわせて報告すること

- **smartx を直すときの材料**（大杉さんの判断は handover_notes のとおり）：SmartX・SmartXNext・SmartXPro（CN・IN）について、国際輸送の運賃を区間だけにし、関税を実在の国境の区間に付け替えたときの、行の対応表の案（今の行 → 直した後の行）と、PPC の費用・粗利率の変化の概算。DC のノードの運賃以外の、ノードの `logistics_cost` の行（組立工場のノードなど）は何の費用か、区間と重なるか。
- smartx の PPC の金額を期待値に持つテスト・文書（golden 以外）の一覧。
- PPC が「鍵の合わない規則の行」を知る方法の案（どこで、どの情報があれば警告できるか）。**実装はしない**。

## 4. 合格の条件

- 16 モデルすべてについて、規則のファイルごとの「行の数／0 でない行／引かれた行／引かれていない行」の表がある。golden の snapshot と一致した実行から数えている
- 引かれていない行のすべてに、Q1 の型と Q2 の判定がある。決められないものは「決められない」と書き、大杉さんへの問いにする
- 引かれるべき行について、モデルごとの抜けている額の概算（Q3）と、直すと二重になるものの指摘（Q4）がある
- コード・サンプル・golden を変えていない
- 報告書 `docs/development/WOM_MoneyBase_UnappliedRules_Survey_Report.md`。冒頭に、モデル × 型の 1 枚の表。大杉さんに決めてほしいこと（一言の決定と中身、推奨）：どのモデルをいつ直すか、PPC に警告を足すか、golden の作り直しの単位

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-13 | 初版 |
