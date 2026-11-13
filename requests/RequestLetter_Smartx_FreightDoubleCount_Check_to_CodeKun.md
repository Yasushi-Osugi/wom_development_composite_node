---
handoff:
  case_id: MONEYBASE-001
  task_id: smartx-freight-double-count-check
  role_from: design            # Claude君
  role_to: implement           # Code君
  target_commit: 78d2998
  knowledge_used:
    - id: 金額基盤の棚卸し表 v0.1
      version: "2026-11-13"
      applicability: "§2 の #1（smartx の運賃の二重計上の疑い）"
  acceptance:
    ref: "この依頼書 §3"
  status: "試行可能（大杉さん 2026-11-13：確かめる）"
  open_items: []
  stop_reasons: []
  next: implement
---

# Request Letter：smartx の運賃の 3 か所が二重計上かを確かめる（調査だけ）

- 宛先：Code君（Claude Code、Windows）／依頼者：大杉／起草：Claude君（2026-11-13）／版：v0.1
- 基準：`78d2998`（着手時の SHA を記録）
- 範囲：**調査だけ。コード・サンプル・golden を変えない。** 出力は `output/moneybase_smartx/`（git の対象外）
- 最初の事業計画比較の依頼書（`RequestLetter_Cockpit_FirstComparison_Observe_to_CodeKun.md`）とは独立。どちらを先にしてもよい

## 一言で

**smartx-2027-2029 で、同じノード × 製品に「ノードの運賃」と「そこへ入る区間の運賃」の両方が書かれている 3 組について、(1) PPC が両方を計上しているか、(2) 両方が同じ輸送を指すか、を分けて調べてください。直すのは、結果を見て大杉さんが決めてからです。**

## 1. 対象（`data/sample/smartx-2027-2029/`）

| ノード × 製品 | `ppc_node_cost_rule.csv` の運賃（`fixed_amount`、USD。`basis` の表記は `per_lot` だが、PPC の集計は換算済みの単価 `amount_base` × 物量 `qty`） | 備考の列 | `ppc_edge_cost_rule.csv` の区間の運賃 |
|---|---:|---|---|
| `DC_AMER` × `SmartXPro_IN` | 10.0 | Ocean freight CN→AMER + port handling | `AssemblyIN->DC_AMER` 17.0 |
| `DC_APAC` × `SmartXPro_CN` | 8.0 | Ocean freight CN→APAC Singapore | `AssemblyCN->DC_APAC` 14.3 |
| `DC_EMEA` × `SmartXPro_CN` | 12.0 | Air/ocean freight CN→EMEA + customs | `AssemblyCN->DC_EMEA` 19.7 |

気になる点：1 行目は製品がインド組立（`SmartXPro_IN`、区間は `AssemblyIN->`）なのに、ノードの備考は「CN→AMER」。備考には港湾取扱・通関を含むと書いた行もある。

## 2. 調べること

手順の詳細（代表の lot と PPC の集約行の対応、抽出の鍵、期間の集計）は、GPT-MC君の業務調査 `docs/design/drafts/WOM_Smartx_Freight_Business_Review_v0.1.md` §2・§3 に従う。役務の判定案は同 §1（AMER：保留、APAC・EMEA：一部重複の可能性）。**両方の明細が出ても、同じ役務と確認できた範囲だけを重複と呼ぶ。**

| # | 問い | 調べ方 |
|---|---|---|
| Q1 | PPC は 3 組で、ノードの運賃と区間の運賃の**両方**を計上しているか。全期間でそれぞれいくらか（`ppc_event_ledger.csv` の `ppc_event_type=logistics_cost`、合計は `amount_base × qty`、`node_id`・`edge_id` で分ける） | headless を正式なサンプルで実行（golden と同じプラグインの組）し、PPC の明細を集計 |
| Q2 | 二つは同じ輸送を指すか、別の費用（港湾取扱・通関・DC の取扱など）か | モデルの README、`ppc_node_cost_rule.csv`・`ppc_edge_cost_rule.csv` のほかの行との並び（同じ製品のほかの DC、兄弟の製品 `SmartX`・`SmartXNext` ではどう書いてあるか）、生成・変更の経緯（`tools/split_smartx_sku.py`・`tools/fix_smartx_price_scale.py`、git の履歴、過去の報告書） |
| Q3 | 同じ型がほかにないか | 全サンプルで「ノードの運賃があり、そのノードへ入る区間にも運賃がある」組を数える（棚卸しでは smartx の 3 組だけ。数え直して確かめる） |
| Q4 | もし二重なら、PPC の費用・試算利益はいくら過大・過小か。単位（1 lot 当たりと 1 個当たり、`cpu_size`）の取り違えは無いか | Q1 の額から。直した場合に変わる golden はどれか（smartx だけの見込み） |

## 3. 合格の条件

- Q1〜Q4 に、根拠（ファイル・行・金額）つきで答えている。**「両方が計上されているか」と「同じ輸送か」を分けて書く。** 資料から決められない所は「決められない」と書き、大杉さんに尋ねる問いにする
- コード・サンプル・golden を変えていない
- 報告書 `docs/development/WOM_MoneyBase_Smartx_FreightCheck_Report.md`（短くてよい）。大杉さんに決めてほしいこと：二重だった場合の直し方（ノードの行を消す／区間へ寄せる／費目を分ける）と、golden を作り直すか
