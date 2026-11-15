---
handoff:
  case_id: MONEYBASE-002
  task_id: unapplied-rule-rows-survey
  role_from: implement         # Code君
  role_to: owner               # 大杉さん
  start_commit: 30cdd17        # 着手時（2026-11-15 09:56）。依頼書の基準 5fa18f3 の後の commit は文書と段 1 の cockpit だけで、wom/ppc・wom/valuechain・サンプル・golden は同じ
  request: requests/RequestLetter_MoneyBase_UnappliedRules_Survey_to_CodeKun.md
  acceptance:
    table_per_model_and_file: pass   # 16 モデル、golden の snapshot と一致した実行から
    q1_q2_for_every_row: pass        # 96 行。決められないものは §6 の問い
    q3_q4: pass
    nothing_changed: pass
  stop_reasons: []
  next: owner
---

# 報告書：全サンプルで「一度も引かれていない金額の規則の行」を洗い出す（調査だけ）

- 依頼書：`requests/RequestLetter_MoneyBase_UnappliedRules_Survey_to_CodeKun.md`（v0.1）
- 調査：Code君、2026-11-15。着手時の SHA `30cdd17`
- **調査だけ。コード・サンプル・golden は変えていない。** 作業の出力は `output/moneybase_unapplied/`（git の対象外）
- 付録：`docs/development/WOM_MoneyBase_UnappliedRules_Survey_appendix/`（全行の一覧、表、集計の道具の写し）

## 一言で

**16 モデル・1,400 行（0 でない行）のうち、一度も引かれていない行は 96 行で、6 モデルにありました。鍵が合わずに抜けている（smartx と同じ型）のは smartx の 12 行だけでした。** 残りは、(1) 工場（MOM）のノードに置いた仕入値で、PPC が読まない行（4 モデル。多くは部材＋組立費で同じ額を計上済みで、足すと二重）、(2) smartphone の PPC が固定の経路で計算していて、計画の木の DC・インドの工場・台湾の工場を通らないための行、(3) 需要が 0 の市場の行（問題なし）、(4) Value Chain だけが使う区間の行（設計どおり）です。

**一番大きいのは smartx の工場の仕入値（450 USD など）**です。PPC はこれを読まず、部材（ウェーハ 5 USD）と組立費だけで原価を作るので、粗利率が 90.4% になっています。足せば粗利率は 45% 前後になります。これは「鍵が合わない」型ではなく、原価をどう持つかの決めごとなので、大杉さんに決めてもらいます（§6 の D2）。

Value Chain（3 モデル）の規則の行は、すべて引かれていました。

### モデル × 型（0 でない行。型は §2）

| モデル | 0 でない行 | 引かれた | 引かれていない | (a) 鍵が合わない | (b) 木に無い | (c) 実出荷が無い | (d) 先に当たる | (e) その他 | 0 の行で引かれていない |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cookie-jp-2026 | 32 | 32 | 0 | — | — | — | — | — | — |
| apparel-global-2028-2029 | 44 | 44 | 0 | — | — | — | — | — | — |
| apparel-us-2026 | 152 | 136 | 16 | — | — | — | — | 16 | — |
| bom-test-2026 | 7 | 7 | 0 | — | — | — | — | — | — |
| cosmetics-sg-th-2027-2029 | 68 | 66 | 2 | — | — | — | — | 2 | 8 |
| ev-europe-2026 | 23 | 21 | 2 | — | — | — | — | 2 | — |
| ev-thailand-2026 | 20 | 18 | 2 | — | — | — | — | 2 | — |
| ev-thailand-2026_update | 21 | 19 | 2 | — | — | — | — | 2 | — |
| oil-global-2027 | 71 | 71 | 0 | — | — | — | — | — | — |
| rice-japan-2027-2028 | 638 | 638 | 0 | — | — | — | — | — | — |
| smartphone-global-2026-2029 | 77 | 39 | 38 | — | — | — | — | 38 | — |
| smartx-2027-2029 | 78 | 56 | 22 | 12 | — | — | — | 10 | 4 |
| soysauce-eu-2027 | 36 | 36 | 0 | — | — | — | — | — | — |
| soysauce-jpy-2027 | 38 | 38 | 0 | — | — | — | — | — | — |
| soysauce-jpy-2027-alloc | 59 | 59 | 0 | — | — | — | — | — | — |
| soysauce-us-2027 | 36 | 24 | 12 | — | — | 12 | — | — | — |
| **計** | 1400 | 1304 | 96 | 12 | — | 12 | — | 72 | 12 |

## 1. 数え方

- 16 モデルを golden と同じプラグインの組で headless 実行し、**16 モデルとも snapshot が golden と完全に一致**した（付録 `run_all.json`）。Value Chain のある 3 モデル（cosmetics・Cookie・soysauce-jpy-2027-alloc）は Value Chain も回した（未評価の明細 0、問題 0）。
- PPC の規則の行は、PPC の明細（`ppc_event_ledger.csv`）と次の鍵で突き合わせた：区間の費用 `edge_id × product_id × cost_type`、関税 `edge_id × product_id`、ノードの費用 `node_id × product_id × cost_type`、仕入値 `supplier_node × product_id`、市場価格 `market_node × product_id`、移転価格 `mom_node × product_id`（どれも `source_rule` で規則のファイルを分ける）。
- 共有の規則（`data/ppc`）は、宣言したモデル（Cookie・rice・smartphone）について、PPC が実際にそのファイルを共有から読んだときだけ、そのモデルの製品の行を数えた。Cookie と smartphone が共有から読むのは為替だけ、rice は 9 ファイルとも共有。
- Value Chain は、`vc_price_rule.csv`・`ppc_edge_cost_rule.csv`・`ppc_tariff_rule.csv` の行を、Value Chain の明細（`vc_money_lines.csv.gz`）と出荷の区間（`vc_shipments.csv.gz`）で突き合わせた。市場の消費者への販売の区間（`<leaf>->CONSUMER`）は、Value Chain が leaf のノードで計上する（`wom/valuechain/ledger.py` 679 行）ので、そのノードの明細と照合した。
- 0 の行（率も額も 0）は別に数えた。
- 集計の道具：付録 `run_all.py`（実行）、`survey.py`（突き合わせ）、`amounts.py`（額）、`tables.py`（表と判定）。

### 規則のファイルごとの表（16 モデル）

| モデル | 規則のファイル | 出どころ | 行の数 | 0 の行 | 0 でない行 | 引かれた | 引かれていない | 0 の行で引かれていない |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Cookie-jp-2026 | ppc_edge_cost_rule.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| Cookie-jp-2026 | ppc_tariff_rule.csv | モデル | 2 | 1 | 1 | 1 | 0 | 0 |
| Cookie-jp-2026 | ppc_node_cost_rule.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| Cookie-jp-2026 | ppc_supplier_cost.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| Cookie-jp-2026 | ppc_market_price.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| Cookie-jp-2026 | ppc_transfer_price_rule.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| Cookie-jp-2026 | VC: vc_price_rule.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| Cookie-jp-2026 | VC: ppc_edge_cost_rule.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| Cookie-jp-2026 | VC: ppc_tariff_rule.csv | モデル | 2 | 1 | 1 | 1 | 0 | 0 |
| apparel-global-2028-2029 | ppc_edge_cost_rule.csv | モデル | 16 | 0 | 16 | 16 | 0 | 0 |
| apparel-global-2028-2029 | ppc_tariff_rule.csv | モデル | 4 | 0 | 4 | 4 | 0 | 0 |
| apparel-global-2028-2029 | ppc_node_cost_rule.csv | モデル | 16 | 0 | 16 | 16 | 0 | 0 |
| apparel-global-2028-2029 | ppc_supplier_cost.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| apparel-global-2028-2029 | ppc_market_price.csv | モデル | 4 | 0 | 4 | 4 | 0 | 0 |
| apparel-global-2028-2029 | ppc_transfer_price_rule.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| apparel-us-2026 | ppc_edge_cost_rule.csv | モデル | 16 | 0 | 16 | 16 | 0 | 0 |
| apparel-us-2026 | ppc_tariff_rule.csv | モデル | 16 | 0 | 16 | 16 | 0 | 0 |
| apparel-us-2026 | ppc_node_cost_rule.csv | モデル | 32 | 0 | 32 | 32 | 0 | 0 |
| apparel-us-2026 | ppc_supplier_cost.csv | モデル | 32 | 8 | 24 | 8 | **16** | 0 |
| apparel-us-2026 | ppc_market_price.csv | モデル | 48 | 0 | 48 | 48 | 0 | 0 |
| apparel-us-2026 | ppc_transfer_price_rule.csv | モデル | 16 | 0 | 16 | 16 | 0 | 0 |
| bom-test-2026 | ppc_edge_cost_rule.csv | モデル | 0 | 0 | 0 | 0 | 0 | 0 |
| bom-test-2026 | ppc_tariff_rule.csv | モデル | 1 | 1 | 0 | 0 | 0 | 0 |
| bom-test-2026 | ppc_node_cost_rule.csv | モデル | 3 | 0 | 3 | 3 | 0 | 0 |
| bom-test-2026 | ppc_supplier_cost.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| bom-test-2026 | ppc_market_price.csv | モデル | 1 | 0 | 1 | 1 | 0 | 0 |
| bom-test-2026 | ppc_transfer_price_rule.csv | モデル | 1 | 0 | 1 | 1 | 0 | 0 |
| cosmetics-sg-th-2027-2029 | ppc_edge_cost_rule.csv | モデル | 18 | 2 | 16 | 14 | **2** | 2 |
| cosmetics-sg-th-2027-2029 | ppc_tariff_rule.csv | モデル | 16 | 16 | 0 | 0 | 0 | 2 |
| cosmetics-sg-th-2027-2029 | ppc_node_cost_rule.csv | モデル | 20 | 2 | 18 | 18 | 0 | 2 |
| cosmetics-sg-th-2027-2029 | ppc_supplier_cost.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| cosmetics-sg-th-2027-2029 | ppc_market_price.csv | モデル | 8 | 0 | 8 | 8 | 0 | 0 |
| cosmetics-sg-th-2027-2029 | ppc_transfer_price_rule.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| cosmetics-sg-th-2027-2029 | VC: vc_price_rule.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| cosmetics-sg-th-2027-2029 | VC: ppc_edge_cost_rule.csv | モデル | 18 | 2 | 16 | 16 | 0 | 0 |
| cosmetics-sg-th-2027-2029 | VC: ppc_tariff_rule.csv | モデル | 16 | 16 | 0 | 0 | 0 | 2 |
| ev-europe-2026 | ppc_edge_cost_rule.csv | モデル | 0 | 0 | 0 | 0 | 0 | 0 |
| ev-europe-2026 | ppc_tariff_rule.csv | モデル | 2 | 1 | 1 | 1 | 0 | 0 |
| ev-europe-2026 | ppc_node_cost_rule.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| ev-europe-2026 | ppc_supplier_cost.csv | モデル | 8 | 0 | 8 | 6 | **2** | 0 |
| ev-europe-2026 | ppc_market_price.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| ev-europe-2026 | ppc_transfer_price_rule.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| ev-thailand-2026 | ppc_edge_cost_rule.csv | モデル | 0 | 0 | 0 | 0 | 0 | 0 |
| ev-thailand-2026 | ppc_tariff_rule.csv | モデル | 2 | 1 | 1 | 1 | 0 | 0 |
| ev-thailand-2026 | ppc_node_cost_rule.csv | モデル | 7 | 0 | 7 | 7 | 0 | 0 |
| ev-thailand-2026 | ppc_supplier_cost.csv | モデル | 4 | 0 | 4 | 2 | **2** | 0 |
| ev-thailand-2026 | ppc_market_price.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| ev-thailand-2026 | ppc_transfer_price_rule.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| ev-thailand-2026_update | ppc_edge_cost_rule.csv | モデル | 0 | 0 | 0 | 0 | 0 | 0 |
| ev-thailand-2026_update | ppc_tariff_rule.csv | モデル | 2 | 1 | 1 | 1 | 0 | 0 |
| ev-thailand-2026_update | ppc_node_cost_rule.csv | モデル | 7 | 0 | 7 | 7 | 0 | 0 |
| ev-thailand-2026_update | ppc_supplier_cost.csv | モデル | 5 | 0 | 5 | 3 | **2** | 0 |
| ev-thailand-2026_update | ppc_market_price.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| ev-thailand-2026_update | ppc_transfer_price_rule.csv | モデル | 2 | 0 | 2 | 2 | 0 | 0 |
| oil-global-2027 | ppc_edge_cost_rule.csv | モデル | 0 | 0 | 0 | 0 | 0 | 0 |
| oil-global-2027 | ppc_tariff_rule.csv | モデル | 8 | 6 | 2 | 2 | 0 | 0 |
| oil-global-2027 | ppc_node_cost_rule.csv | モデル | 24 | 0 | 24 | 24 | 0 | 0 |
| oil-global-2027 | ppc_supplier_cost.csv | モデル | 16 | 0 | 16 | 16 | 0 | 0 |
| oil-global-2027 | ppc_market_price.csv | モデル | 21 | 0 | 21 | 21 | 0 | 0 |
| oil-global-2027 | ppc_transfer_price_rule.csv | モデル | 8 | 0 | 8 | 8 | 0 | 0 |
| rice-japan-2027-2028 | ppc_edge_cost_rule.csv | 共有 data/ppc | 6（ファイル全体 11） | 0 | 6 | 6 | 0 | 0 |
| rice-japan-2027-2028 | ppc_tariff_rule.csv | 共有 data/ppc | 0（ファイル全体 2） | 0 | 0 | 0 | 0 | 0 |
| rice-japan-2027-2028 | ppc_node_cost_rule.csv | 共有 data/ppc | 6（ファイル全体 13） | 0 | 6 | 6 | 0 | 0 |
| rice-japan-2027-2028 | ppc_supplier_cost.csv | 共有 data/ppc | 312（ファイル全体 468） | 0 | 312 | 312 | 0 | 0 |
| rice-japan-2027-2028 | ppc_market_price.csv | 共有 data/ppc | 312（ファイル全体 624） | 0 | 312 | 312 | 0 | 0 |
| rice-japan-2027-2028 | ppc_transfer_price_rule.csv | 共有 data/ppc | 2（ファイル全体 3） | 0 | 2 | 2 | 0 | 0 |
| smartphone-global-2026-2029 | ppc_edge_cost_rule.csv | モデル | 12 | 0 | 12 | 12 | 0 | 0 |
| smartphone-global-2026-2029 | ppc_tariff_rule.csv | モデル | 12 | 6 | 6 | 6 | 0 | 0 |
| smartphone-global-2026-2029 | ppc_node_cost_rule.csv | モデル | 32 | 0 | 32 | 6 | **26** | 0 |
| smartphone-global-2026-2029 | ppc_supplier_cost.csv | モデル | 11 | 0 | 11 | 3 | **8** | 0 |
| smartphone-global-2026-2029 | ppc_market_price.csv | モデル | 9 | 0 | 9 | 9 | 0 | 0 |
| smartphone-global-2026-2029 | ppc_transfer_price_rule.csv | モデル | 7 | 0 | 7 | 3 | **4** | 0 |
| smartx-2027-2029 | ppc_edge_cost_rule.csv | モデル | 14 | 1 | 13 | 5 | **8** | 0 |
| smartx-2027-2029 | ppc_tariff_rule.csv | モデル | 14 | 8 | 6 | 2 | **4** | 4 |
| smartx-2027-2029 | ppc_node_cost_rule.csv | モデル | 32 | 0 | 32 | 32 | 0 | 0 |
| smartx-2027-2029 | ppc_supplier_cost.csv | モデル | 11 | 0 | 11 | 4 | **7** | 0 |
| smartx-2027-2029 | ppc_market_price.csv | モデル | 9 | 0 | 9 | 9 | 0 | 0 |
| smartx-2027-2029 | ppc_transfer_price_rule.csv | モデル | 7 | 0 | 7 | 4 | **3** | 0 |
| soysauce-eu-2027 | ppc_edge_cost_rule.csv | モデル | 13 | 0 | 13 | 13 | 0 | 0 |
| soysauce-eu-2027 | ppc_tariff_rule.csv | モデル | 6 | 1 | 5 | 5 | 0 | 0 |
| soysauce-eu-2027 | ppc_node_cost_rule.csv | モデル | 10 | 0 | 10 | 10 | 0 | 0 |
| soysauce-eu-2027 | ppc_supplier_cost.csv | モデル | 1 | 0 | 1 | 1 | 0 | 0 |
| soysauce-eu-2027 | ppc_market_price.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| soysauce-eu-2027 | ppc_transfer_price_rule.csv | モデル | 1 | 0 | 1 | 1 | 0 | 0 |
| soysauce-jpy-2027 | ppc_edge_cost_rule.csv | モデル | 13 | 0 | 13 | 13 | 0 | 0 |
| soysauce-jpy-2027 | ppc_tariff_rule.csv | モデル | 6 | 1 | 5 | 5 | 0 | 0 |
| soysauce-jpy-2027 | ppc_node_cost_rule.csv | モデル | 10 | 0 | 10 | 10 | 0 | 0 |
| soysauce-jpy-2027 | ppc_supplier_cost.csv | モデル | 3 | 0 | 3 | 3 | 0 | 0 |
| soysauce-jpy-2027 | ppc_market_price.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| soysauce-jpy-2027 | ppc_transfer_price_rule.csv | モデル | 1 | 0 | 1 | 1 | 0 | 0 |
| soysauce-jpy-2027-alloc | ppc_edge_cost_rule.csv | モデル | 13 | 0 | 13 | 13 | 0 | 0 |
| soysauce-jpy-2027-alloc | ppc_tariff_rule.csv | モデル | 4 | 1 | 3 | 3 | 0 | 0 |
| soysauce-jpy-2027-alloc | ppc_node_cost_rule.csv | モデル | 10 | 0 | 10 | 10 | 0 | 0 |
| soysauce-jpy-2027-alloc | ppc_supplier_cost.csv | モデル | 3 | 0 | 3 | 3 | 0 | 0 |
| soysauce-jpy-2027-alloc | ppc_market_price.csv | モデル | 6 | 0 | 6 | 6 | 0 | 0 |
| soysauce-jpy-2027-alloc | ppc_transfer_price_rule.csv | モデル | 1 | 0 | 1 | 1 | 0 | 0 |
| soysauce-jpy-2027-alloc | VC: vc_price_rule.csv | モデル | 7 | 0 | 7 | 7 | 0 | 0 |
| soysauce-jpy-2027-alloc | VC: ppc_edge_cost_rule.csv | モデル | 13 | 0 | 13 | 13 | 0 | 0 |
| soysauce-jpy-2027-alloc | VC: ppc_tariff_rule.csv | モデル | 4 | 1 | 3 | 3 | 0 | 0 |
| soysauce-us-2027 | ppc_edge_cost_rule.csv | モデル | 13 | 0 | 13 | 9 | **4** | 0 |
| soysauce-us-2027 | ppc_tariff_rule.csv | モデル | 6 | 1 | 5 | 2 | **3** | 0 |
| soysauce-us-2027 | ppc_node_cost_rule.csv | モデル | 10 | 0 | 10 | 8 | **2** | 0 |
| soysauce-us-2027 | ppc_supplier_cost.csv | モデル | 1 | 0 | 1 | 1 | 0 | 0 |
| soysauce-us-2027 | ppc_market_price.csv | モデル | 6 | 0 | 6 | 3 | **3** | 0 |
| soysauce-us-2027 | ppc_transfer_price_rule.csv | モデル | 1 | 0 | 1 | 1 | 0 | 0 |

## 2. 引かれていない行ごとの答え（Q1・Q2）

全 96 行の一覧（行番号・中身・型・判定）：付録 `unapplied_rows.csv`。6 つの群に分かれた。

| 群 | モデル・ファイル | 行 | Q1 なぜ引かれないか | Q2 引かれるべきか |
|---|---|---:|---|---|
| G1 | smartx：区間の費用 8・関税 4（SmartX・SmartXNext） | 12 | **(a)** 鍵が supply point 経由（`SP_SmartX->Retail_AMER_g1` など）。PPC は「工場 → 最初の DC」「DC → 市場」の鍵を作る | **引かれるべき**（大杉さんの判断どおり。§3） |
| G2 | 工場（MOM）のノードに置いた仕入値：apparel-us 16、ev-europe 2、ev-thailand 2、ev-thailand_update 2、smartx 7 | 29 | **(e)** PPC は仕入値を leaf_in（部材の供給元）のノードでだけ読む。工場のノードの行は読まない | apparel・ev：**引かない**（Q4：部材の仕入値＋組立費で同じ額が計上済み）。smartx：**決められない**（§6 の D2） |
| G3 | smartphone：ノードの費用 26、仕入値 8、移転価格 4 | 38 | **(e)** smartphone の PPC は、計画の木ではなく固定の経路（`wom/ppc/ppc_engine.py` の `build_smartphone_global_vs_paths`：EMS_A_CN → SP_Phone16 → 市場）で計算する。supply point を DC として扱い、木の DC（DC_AMER など）・台湾の工場・インドの工場（EMS_A_IN）を通らない | DC の作業費（9 行）は**引かれるべき**。DC の運賃（9 行）は**引かない**（Q4）。台湾の工場・ウェーハ・センサー（17 行）とインドの工場（3 行）は**決められない**（§6 の D3） |
| G4 | smartx：移転価格 3（FoundryTW・FoundryTW_g1・_g3） | 3 | **(e)** 今の PPC は、製品ごとに最後の工場（AssemblyCN など）の移転価格 1 つだけを使う。途中の工場の移転価格は読まない | **決められない**（途中の工場を別の法人として見るなら Value Chain の題材。今の PPC の作りでは引かない） |
| G5 | soysauce-us：区間 4・関税 3・ノード 2・市場価格 3（欧州） | 12 | **(c)** このケース（米国集中）は欧州の需要が全週 0（`demand_forecast.csv` の FR・BE・NL が 0）。規則は soysauce-eu と同じで正しい | **問題なし** |
| G6 | cosmetics：区間 2（`SG_EC->CONSUMER` の配送梱包 SGD 3） | 2 | **(e)** 消費者への販売の区間は PPC に無い（Value Chain だけが使う区間） | **PPC では引かない**。PPC は同じ SGD 3 を `SG_EC` の `sga_cost` の固定額で計上し、Value Chain は区間で計上して、両者が一致することを読み込みで確かめている（`wom/valuechain/masters.py` の C4）。設計どおり |

- 型 (b)（木に無い）と (d)（ほかの行に先に当たる）は 0 行だった。
- G2 の判定の根拠（付録 `q3_mom_supplier_rows.csv`）：apparel-us の外注品は、工場の行 19 USD ＝ 組立費として計上済みの 19 USD（布地の仕入値は 0）。内製品は工場の行 17 USD ＝ 布地 7 ＋ 組立費 10。ev-europe は工場の行 19,900 EUR ≒ 電池・モーター・ECU 15,700 ＋ 組立費（SKU の単位原価 20,100）。ev-thailand は工場の行 ＝ SKU の単位原価（780,000・950,000 THB）で、部材と組立費で計上済み。どれも、昔の「完成品を 1 つの仕入値で持つ」形の名残に見える。
- smartphone の G3 は、smartx と逆の形：smartphone では supply point 経由の鍵が**引かれている**（PPC の固定の経路が supply point を DC として扱うため）。棚卸し表の「smartphone の関税 6 行も supply point 起点」は、PPC では計上されている（Value Chain では評価できない、という棚卸し #4 の指摘は残る）。

### 0 の行で引かれていない 12 行

付録 `zero_rows_not_applied.csv`。どれも額が 0 なので、金額に影響は無い。

- smartx 4 行：G1 と同じ supply point 経由の関税で、税率 0（国内の区間・APAC）。直すときに一緒に付け替える。
- cosmetics 6 行：`Materials_JP->Factory_JP` の運賃 0・関税 0（PPC は 0 の運賃の明細を作らず、部材 → 工場の区間の関税は読まない）、`Materials_JP` の組立費 0（PPC は leaf_in のノードの費用を読まない。備考に「仕入値で計上」とある）。
- cosmetics 2 行（Value Chain）：`WH_JP_Released->DC_TH` の関税 0。Value Chain は計上の明細を作らない（0 なので）。

## 3. 抜けている額（Q3）と、直すと二重になるもの（Q4）

| モデル | 引かれるべき行の抜けている額（概算） | 仮定 | 直すと二重になるもの（Q4） |
|---|---|---|---|
| smartx | 運賃 ＋8,069,860 USD、関税 ＋4,084,007 USD | 区間を Pro と同じ形に付け替えたとき、明細の物量 × 規則の額。関税は明細の移転価格 × 税率 | SmartX・SmartXNext の DC のノードの運賃 4,431,542 USD と、Pro の DC のノードの運賃 2,647,672 USD（大杉さんの判断で消す）。差し引き §3.1 |
| smartphone | DC の作業費 約 3,233 億円（費用の 0.86%） | DC を通る物量 ＝ その DC の市場の物量 × 規則の額 × 為替（明細の加重平均 153.65 円／USD） | DC の運賃（約 6,489 億円）は supply point → 市場の区間の運賃と同じ輸送なので足さない。台湾の工場・ウェーハ・センサーは EMS の仕入値 450 USD に含まれるなら二重 |
| smartphone（インド） | 決められない。参考：米州の Phone16 1 億 31 万個を中国組立からインド組立に替えると、仕入値 ＋20・組立費 ＋2・運賃 ＋1 USD で約 3,545 億円。関税はインド発の規則が無いので計算できない（今は中国発 25% で 2 兆 1,395 億円を計上） | 計画の振り分け（`lane_assignment.csv`：米州はインド組立） | 中国組立の行は米州の分で既に計上されている（置き換えになる） |
| smartx（工場の仕入値 G2） | 決められない。参考：組立工場の 4 行を足すと 313,287,000 USD（粗利率 90.4% → 約 45.7%）。台湾の工場の 3 行を足すと さらに 22,546,000 USD | 明細の物量 × 行の額 | 組立費（50 USD など）とウェーハ（5 USD）は 450 USD の中に含まれていると読むのが自然（smartphone は 450 を EMS の仕入値として使い、部材・組立費は足していない）。足すなら組立費・ウェーハを外すかを決める |
| apparel-us・ev 3 モデル（G2） | 抜けていない | — | 足すと二重（§2） |
| soysauce-us・cosmetics | 抜けていない | — | cosmetics の CONSUMER の行を PPC に足すと二重 |

### 3.1 smartx を直すときの材料

大杉さんの判断（国際輸送の運賃は区間だけ／DC のノードの運賃は消す／SmartX・SmartXNext も Pro と同じ書き方）による、行の対応表の案（付録 `smartx_fix_plan.csv`）：

| 製品 | 今の行 | 直した後の行 |
|---|---|---|
| SmartX | `SP_SmartX->Retail_AMER_g1` 16.1 ＋ `AssemblyCN_g1->SP_SmartX` 0.9 | `AssemblyCN_g1->DC_AMER_g1` 16.1、`DC_AMER_g1->Retail_AMER_g1` 0.9 |
| SmartX | `SP_SmartX->Retail_EMEA_g1` 18.2 ＋ 0.9 | `AssemblyCN_g1->DC_EMEA_g1` 18.2、`DC_EMEA_g1->Retail_EMEA_g1` 0.9 |
| SmartX | `SP_SmartX->Retail_APAC_g1` 13.3 ＋ 0.9 | `AssemblyCN_g1->DC_APAC_g1` 13.3、`DC_APAC_g1->Retail_APAC_g1` 0.9 |
| SmartXNext | `SP_SmartXNext->Retail_*_g3` 17.9／20.8／15.3 ＋ `AssemblyCN_g3->SP_SmartXNext` 1.2 | `AssemblyCN_g3->DC_*_g3` 17.9／20.8／15.3、`DC_*_g3->Retail_*_g3` 1.2 |
| SmartX・SmartXNext の関税 | `SP_…->Retail_…`（米州 25%・欧州 7.5%・APAC 0%）、`AssemblyCN_g?->SP_…` 0% | `AssemblyCN_g?->DC_…`（同じ税率）、`DC_…->Retail_…` 0%（Pro と同じ形） |
| 6 つの DC × SmartX・SmartXNext、3 つの DC × Pro | DC のノードの `logistics_cost`（9.5／11／7.5、10.5／12.5／8.5、10／12／8） | 消す |

- 国内の 0.9・1.2 を DC → 市場の区間に寄せるのは、Pro の移行（`tools/split_smartx_sku.py`）と同じ扱い。
- **PPC の費用の変化の概算**：費用 67,503,726 USD に、運賃 ＋8,069,860・関税 ＋4,084,007、DC のノードの運賃 −4,431,542（SmartX・SmartXNext）−2,647,672（Pro）＝ **＋5,074,654 USD**。粗利率 **90.368% → 89.644%**。工場の仕入値（D2）を足すかどうかで、これよりずっと大きく変わる。
- **DC 以外のノードの `logistics_cost`**（付録 `smartx_node_logistics_booked.csv`、すべて計上されている）：
  - 組立工場 `AssemblyCN`（5.0）・`AssemblyCN_g1`（4.5）・`AssemblyCN_g3`（5.5）：備考「Inbound logistics CN domestic」。中国国内の部材の入荷の運賃。計画の木に中国国内の部材の供給元のノードは無く、組立工場へ入る区間は台湾の工場から（台湾 → 中国）なので、**どの区間に当たるか決められない**。区間の行とは重ならない（入荷側の区間の規則は 1 行も無い）。
  - `AssemblyIN`（6.0）：「Inbound logistics India domestic」。インドのセンサー → 組立の区間（`SensorIN->AssemblyIN`）に当たる。
  - 台湾の工場 `FoundryTW`（2.0）・`_g1`（1.8）・`_g3`（2.2）：「Wafer logistics TW→CN」。台湾の工場 → 中国の組立の区間（`FoundryTW->AssemblyCN` など）に当たる。
  - どれも区間とは重ならないが、運賃がノードにあるので Value Chain の読み込みでは止まる（Start Here R8）。区間へ寄せるなら golden が変わる。

### 3.2 smartx の PPC の金額を期待値に持つテスト・文書（golden 以外）

- **テスト：無い。** smartx を使うテスト（`test_capacity_layer_trial.py`・`test_capacity_zero_blank.py`・`test_generation_line_upper_layer.py`・`test_smartx_evidence_ranges.py`）は、PPC の金額を検査していない（計画の結果・能力・ID・証拠の範囲だけ）。
- **文書**（記録として残っている値。直したら古い値になる）：`docs/development/WOM_GenerationLine_UpperLayer_Report.md`（137・138・198 行）、`docs/development/WOM_MoneyBase_Smartx_FreightCheck_Report.md`（67 行）、`docs/development/generation_line/compare/compare.json`、`docs/development/public_readiness/p1.csv`・`p1.json`、`docs/development/capacity_zero_blank/*_data.json`（関税の合計）、`docs/development/stage_d_survey/stage_d_measure.json`。

## 4. PPC が「鍵の合わない規則の行」を知る方法の案（実装はしない）

| 案 | どこで | 要る情報 | 分かること |
|---|---|---|---|
| A. 使った行の記録 | `wom/ppc/ppc_rules.py` の `get_edge_costs`・`get_tariff`・`get_node_costs`・`get_transfer_price_rule`（今は無ければ黙って空を返す）と、仕入値・市場価格の検索 | 引いた鍵の集合（`lookup_log` と同じ作り。今は仕入値・市場価格の「無い」「最初の週より前」だけを記録） | 実行の後、読み込んだ行のうち一度も引かれなかった行。`ppc_warnings.csv` と `ppc_kpi_summary.json` に件数と一覧を出す（この調査の `survey.py` と同じ結果） |
| B. 読み込みの時の形の検査 | `wom/ppc/ppc_runner.py`（計画の木があるので、PPC の前に） | 計画の木 | 区間の行の両端が木に無い、supply point を含む、PPC が作る区間の形と違う（G1 の型）。ノードの行が木に無い。仕入値の行が leaf_in でないノードにある（G2 の型） |
| C. 引かれない理由の区別 | A の結果に、市場の売上の明細を突き合わせる | 製品 × 市場の実出荷 | 「実出荷が無いので引かれない」（G5、問題なし）と「鍵が合わない」を分ける |

- 推奨は A ＋ C を警告として出し、B は止めずに警告（今の PPC の作法：規則の無い組合せは止めずに件数を残す。R12）。B だけでは smartphone の固定の経路（G3）は分からない（木とは別の経路で計算しているため）ので、A が要る。
- smartphone の固定の経路そのものは、`detect_scenario` が smartphone の製品名を見て選ぶ。木の経路で計算する GENERIC に寄せるかは、別の判断（D3）。

## 5. 申し送り

1. 判定（Q2）は、資料（規則の備考、SKU の単位原価、移行の経緯、計画の木）から読んだもの。請求・積算の根拠はリポジトリに無い。
2. smartphone の額は明細の為替の加重平均（153.65 円／USD）で換算した概算。
3. 着手時の HEAD は `30cdd17`。作業中に、依頼書に無い未追跡のファイル（`requests/RequestLetter_Cockpit_Stage3_Step2_CompareScreen_to_CodeKun.md`）が増えた（私の作業ではない）。

## 6. 大杉さんに決めてほしいこと

| # | 一言で | 中身 | 推奨 |
|---|---|---|---|
| D1 | smartx の運賃・関税をいつ直すか | §3.1 の対応表で、SmartX・SmartXNext の区間と関税を付け替え、9 つの DC のノードの運賃を消す。費用 ＋507 万 USD、粗利率 −0.72 ポイント | **D2 と一緒に直す**（どちらも smartx の golden の `ppc` を変える。1 回で作り直す） |
| D2 | smartx の原価を「完成品の仕入値」で持つか「部材の積み上げ」で持つか | 組立工場の仕入値（450・320・490・470 USD ＝ SKU の単位原価）を PPC は読んでいない。今の原価は ウェーハ 4〜16 USD ＋ 組立費などで、粗利率 90.4%。仕入値を使うなら、組立費・ウェーハ・台湾の工場の費用を外すか（smartphone と同じ形）、部材を全部書くかを決める | **完成品の仕入値で持つ**（smartphone と同じ。SKU の単位原価・`node_cost_master.csv` とも合う）。工場の仕入値を leaf_in にあたる行として読める形に直す方法は、別の依頼書で |
| D3 | smartphone の固定の経路をどうするか | PPC が木の DC・インドの工場を通らない。DC の作業費 約 3,233 億円（費用の 0.86%）が抜け、米州の Phone16 を中国組立・中国発の関税で計上している | **今は直さない**。smartx が smartphone を木の経路（GENERIC）に分けた後継なので、smartphone は記録として扱い、必要なら smartx で見る。直すなら、インド発の関税の規則から作る必要がある |
| D4 | apparel-us・ev 3 モデルの工場の仕入値の行 | 読まれず、足すと二重 | **消す**（名残）。金額は変わらず、golden も変わらない |
| D5 | PPC に警告を足すか | §4 の A ＋ C（実行の後に、一度も引かれなかった行を件数と一覧で出す。止めない） | **足す**。今回の 96 行のうち、本当に抜けていたのは 12 行（＋決められない行）だけで、残りは理由のある行。警告を出すときは「実出荷が無い」「Value Chain だけの区間」を分けて出す |
| D6 | golden の作り直しの単位 | 直すと変わるのは smartx だけ（D1・D2）。D4 は golden を変えない。smartphone（D3）は直さないなら変わらない | **smartx を 1 回で作り直す**（D1 と D2 を同じ commit で） |

## 7. 記録

- 時刻：始め 2026-11-15 09:56、終わり 10:15 ごろ（Windows の時計）。
- 人の橋渡し：なし。
- 再利用した知識：smartx の運賃の調査の報告書（`b7a2ed1`）、金額基盤の棚卸し表 v0.1、PPC の規則の読み方（`wom/ppc/ppc_rules.py`・`ppc_tariff.py`・`ppc_engine.py`）、Value Chain の読み込み（`wom/valuechain/masters.py`・`ledger.py`）。
- 迷った所：
  1. 共有の規則の「モデルが読んだ行」：モデルの計画の木にある製品の行とした。
  2. Value Chain の明細には区間の列が無いので、出荷の記録の区間と結んだ。消費者への販売の区間は leaf のノードで照合した（最初、この照合が無く cosmetics の 2 行を「引かれていない」と数えた。直した）。
  3. smartphone の「supply point 起点」の行は、棚卸しでは問題の候補だったが、PPC では引かれていた（固定の経路のため）。引かれていない行は、逆に木の DC・工場の行だった。
