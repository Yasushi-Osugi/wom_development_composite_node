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
