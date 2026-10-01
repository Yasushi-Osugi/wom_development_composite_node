# Cookie-jp-2026

日本市場のクッキー：輸入品（Cookie_Import、中国の工場）と国産品（Cookie_Local、日本の工場）が、
日本の 3 つのチャネル（Retail_JP_SM・Retail_JP_CVS・Retail_JP_EC）で並ぶモデル。

## 運賃は物理の区間に置く（RequestLetter_StageD_Phase1 Part 0-2、2026-10-01）

運賃（`logistics_cost`）は `ppc_edge_cost_rule.csv` の**物理の区間だけ**に書く。
`ppc_node_cost_rule.csv` には運賃を書かない（同じ輸送を区間とノードの両方に書くと二重に計上される）。
supply point（`SP_Cookie_*`）は inbound と outbound をつなぐ仮想のノードで、物理の区間に入らない。

| 物理の区間 | 金額（JPY/lot） | 内訳 |
|---|---:|---|
| `Factory_GP_CN->DC_Import_Buffer` | 2,500 | 中国国内輸送（工場→輸出港 FOB）500 ＋ 海上運賃 CIF（横浜港着）2,000 |
| `DC_Import_Buffer->DC_Import_Main` | 1,000 | 国内陸送費（保税倉庫→国内DC） |
| `Factory_DP_JP->DC_Local_JP` | 200 | 工場→DC 短距離輸送 |
| `DC_Local_JP->Retail_JP_SM`・`_CVS`・`_EC` | 300 | パン便相乗り 限界輸送費（DC→店舗） |

変更前は、`Factory_GP_CN`（500）・`DC_Import_Buffer`（2,000）・`DC_Import_Main`（1,000）・
`Factory_DP_JP`（200）・`DC_Local_JP`（300）のノード費用に運賃があり、`DC_Import_Buffer->DC_Import_Main`
の 1,000 は区間とノードの両方に書かれていた（二重計上）。`Factory_GP_CN->SP_Cookie_Import` などの
supply point を通る 4 行は、ノード費用の写しで、PPC は読んでいなかった。

## vc_price_rule.csv の仮の値（Claude君、2026-10-01。大杉さんの確認待ち）

段階 D 第 1 回で未設定だった CVS（② 外部の販売チャネル）への卸価格。

- 規則：**卸価格 ＝ 市場価格 × (1 − チャネルの粗利率)**。CVS の粗利率は、日本のコンビニの一般的な水準として **30%** を仮に置いた。
- 値：30,000 × (1 − 0.30) ＝ **21,000 JPY/lot**（Cookie_Import・Cookie_Local とも）。

1 lot 当たりの損益（V3、グループ）。原価はマスターの値から計算：

| | Cookie_Import | Cookie_Local |
|---|---:|---:|
| グループの原価（在庫原価） | 23,200（原料 8,000 ＋ 加工 8,000 ＋ 運賃 2,500 ＋ 関税 2,700 ＋ 取扱 500 ＋ 陸送 1,000 ＋ DC 500） | 20,200（原料 11,000 ＋ 加工 9,000 ＋ 運賃 200） |
| その週の費用 | SGA 1,500 | SGA 4,000 ＋ 店舗への配送 300（売り手の販売費） |
| 自社のチャネル（SM・EC、30,000） | **＋5,300** | **＋5,500** |
| CVS（卸 21,000、粗利率 30%） | **−3,700** | **−3,500** |
| 損益分岐の粗利率 | 17.7%（卸 24,700） | 18.3%（卸 24,500） |

粗利率を変えたとき（CVS、1 lot 当たり、グループ）：

| CVS の粗利率 | 卸価格（JPY） | Cookie_Import | Cookie_Local |
|---:|---:|---:|---:|
| 15% | 25,500 | ＋800 | ＋1,000 |
| 20% | 24,000 | −700 | −500 |
| 25% | 22,500 | −2,200 | −2,000 |
| 30% | 21,000 | −3,700 | −3,500 |
| 35% | 19,500 | −5,200 | −5,000 |

**今の原価の構造では、CVS の一般的な粗利率（30%）だと、CVS 向けは 1 lot ごとに赤字になる。** 値を変えるときは、このファイルの表を見て `vc_price_rule.csv` の `price` を書き換える。
