# C：S2　要求（S）・実出荷を使う箇所の棚卸し

依頼書 C1。起点は `sc_tree_to_df.py`・`money.py`・Management／KPI・`_draw_cost_from_plan_node`・Harvest Input。
そこから利用先をたどった。

言葉：**要求**＝supply S（Demand Position）。**実出荷**＝`node._actual_ship`（ForwardPlanner が付ける）。
**当週充足**＝その週の要求の Lot_ID のうち、同じ週に実出荷されたもの。

方式の伝え方：計画の経路（GUI の `_build_planning_context`、headless の `run`）が、ツリーに
`sc_tree.lot_flow_mode` という印を付ける。評価の関数は「引数 `lot_flow_mode` → ツリーの印 → どちらも無ければ
要求ベース（これまでどおり）」の順に方式を決める。

## 1. 数量を作るところ

| 箇所 | 項目 | 前（両方式とも） | 後：identity | 後：legacy・方式の指定なし | 対象の期間 |
|---|---|---|---|---|---|
| `wom/engine/sc_tree_to_df.py` `sc_tree_to_planning_df`（leaf_out と DAD の行） | `demand_fulfilled` | 要求の件数 × cpu | **実出荷の件数 × cpu**（遅配分の出荷を含む） | 要求の件数 × cpu（同じ） | 計画期間の各週（助走週を含む） |
| 同上 | `ship_qty` | 実出荷 × cpu（記録なしは 0） | 実出荷 × cpu（**記録なしは NaN**） | 同じ | 同上 |
| 同上 | `stockout_qty` | max(0, 需要 − 要求)（ふつう 0） | **当週未充足**＝（要求 − 当週充足）× cpu | 同じ | 同上 |
| 同上 | `fill_rate` | 要求 ÷ 需要（需要 0 は 1.0） | **当週充足 ÷ 要求**（要求 0 は 1.0。100% を超えない） | 同じ | 同上 |
| 同上 | `co_qty` | CO の件数 × cpu | 同じ（**週初**の CO＝その週に持ち越された要求） | 同じ | 同上 |
| 同上（新しい列） | `qty_basis` | — | `actual_ship`（記録なしは `unknown`） | `request` | — |
| 同上（新しい列） | `request_qty` | — | 要求の件数 × cpu | 同じ | — |
| 同上（新しい列） | `on_time_qty` | — | 当週充足 × cpu | NaN（計算しない） | — |
| 同上（新しい列） | `co_end_qty` | — | **週末**の CO＝（CO＋S のうち、その週に出荷されなかった ID）× cpu | NaN | — |
| `wom/engine/strategic_kpi.py` `compute_strategic_kpi`（充足率） | `fill_rate` | Σ 要求 ÷ Σ 需要（市場 leaf） | **Σ 当週充足 ÷ Σ 要求**（市場 leaf、ID で判定。記録なしは NaN） | 同じ | 計画期間の合計 |
| `wom/ppc/ppc_psi_bridge.py` `psi_to_sales_records` | 販売数量 | 実出荷。記録なしは要求へ戻す | 実出荷。**記録なしは、売上の行を作らず警告**（要求へ戻さない） | 同じ（記録なしは要求へ戻す） | 計画期間の各週 |

## 2. 数量を金額にするところ

| 箇所 | 項目 | 計算式 | 数量の元 | 前 | 後：identity | 後：legacy |
|---|---|---|---|---|---|---|
| `wom/engine/money.py` `evaluate_money` | Revenue | `demand_fulfilled × selling_price`（`sku_master`） | 市場 leaf の行 | 要求ベース | **実出荷ベース**（式は同じ。数量が変わる） | 要求ベース（同じ値） |
| 同上 | COGS | `demand_fulfilled × unit_cost` | 同上 | 要求ベース | 実出荷ベース | 同じ値 |
| 同上 | `total_units`（→ `units`） | Σ `demand_fulfilled`（**DAD の行も合計**） | leaf＋DAD | 要求ベース | 実出荷ベース | 同じ値 |
| 同上（新しい列） | `qty_basis` | 行の基準をそのまま運ぶ | — | — | `actual_ship`／`unknown` | `request`。シミュレーターのシナリオは `simulated` |
| 同上 | 記録なしの扱い | — | — | — | Revenue・COGS は NaN（0 にしない） | — |
| `wom/engine/landed_cost.py` | 運賃（Freight） | 1 lot あたりの運賃 × `units` × 為替 | money の `units` | 要求ベース | 実出荷ベース | 同じ値 |
| `wom/ppc/*`（PPC の台帳） | 売上・原価・関税 | 市場の販売数量 × `ppc_market_price` × 為替、から経路のコストを引く | `psi_to_sales_records` | 実出荷（LotIdentityFlow C4 で対応済み） | 同じ | 同じ |

- DAD の行は、`sku_master` に価格が無い（地域が `DAD:…`）ので、money の売上・原価は 0。数量の列だけが出る。
- 価格・原価・通貨・`cpu_size`・`bom_qty` の換算は変えていない。

## 3. 画面

| 画面 | 表示 | 読む列・値 | 前のラベル | 後のラベル・動き |
|---|---|---|---|---|
| Charts → Fill Rate | 週ごとの充足率 | `fill_rate` | Average Fill Rate by Week | 同じ（identity では当週充足 ÷ 要求の値になる） |
| Charts → Stockout | 週ごとの欠品 | `stockout_qty` | Stockout Quantity by Week | 同じ（identity では当週未充足の値になる） |
| Charts → Harvest Input | 稲作田の週ごとの量 | **Demand レイヤーの S（要求）**。変えていない | 「週次収穫・出荷量」「Lots dispatched」 | **「週次の収穫要求量（需要：Demand レイヤーの S。実出荷ではない）」「Lots requested (demand)」** |
| KPI Table | `total_fulfilled`・`total_stockout`・`avg_fill_rate` | `ScenarioManager.kpi_summary` | — | 列名は同じ。identity では実出荷・当週未充足・当週充足率の値 |
| Management → P&L Summary | Revenue・COGS・GP・GM | PPC の台帳で上書き（v1r2m0）。運転資本は money | — | 変えていない（PPC はもともと実出荷） |
| Management → Strategic KPI「需要充足率」 | 充足率のカード | `compute_strategic_kpi`（SKU で絞るときも同じ） | 式の説明「出荷 / 需要」 | **「当週出荷 / 要求（市場）」**。記録なしは「—」と `N/A` |
| Management → Landed Cost | Freight（情報列） | money の `units` | — | 変えていない（値は identity では実出荷ベースになる） |
| Network → ノードを選ぶ → PSI チャート（シナリオの表示） | 青い棒「S: Request」 | 前は `demand_fulfilled` | S: Request (Demand Position) | 同じラベル。**`request_qty` を読む**（identity でも要求のまま）。紫の線は実出荷 |
| Network → ノードを選ぶ → Cost/Revenue チャート（`_draw_cost_from_plan_node`） | ノードの売上・原価・粗利 | 前は S（要求）× ノードの価格 | Cost / Revenue | identity：**そのノードの実出荷** × ノードの価格（市場 leaf に限らない）、題に「実出荷ベース」。記録なしは「実出荷の記録がありません（不明）」。legacy：S のまま、題に「要求 S ベース（legacy）」 |
| 計画の完了のステータス行 | fill・stockout | `plan_df` の平均・合計 | `Planning: fill …, stockout …` | 末尾に「（実出荷ベース）」か「（要求 S ベース（legacy））」。ただし、この行はすぐ後に PPC の完了の行で上書きされるので、ふつうは見えない |
| Network → PSI List | S・Ship の列、Σ 行 | S と `_actual_ship` | — | 変えていない（FlowCheck V2。記録なしは「—」） |
| Network → Flow Check | 表 1・表 2 | — | — | 表 1 に「同一ID重複」の列（B4）、Kitting の照合の結果（B3） |

Planning Engine を実行する前：Management の Strategic KPI は「Planning Engine 未実行」、Harvest Input は
「Planning Engine を実行してください」、PSI List の Ship は「—」。未計算を実出荷 0 とは表示しない（変えていない）。

## 4. 変えていないもの（理由）

| 箇所 | 理由 |
|---|---|
| Harvest Input の数量（Demand レイヤーの S） | 収穫の要求量（需要）を表す図。題と軸の言葉だけを「需要」に直した |
| `demand_fcst`（Demand レイヤーの S） | 需要そのもの |
| PSI チャートの「S: Request」の棒 | 要求を表す棒（`request_qty` を読むようにして、identity でも要求のままにした） |
| PPC の台帳の中間ノードの数量 | 市場の販売数量から経路をたどって導く、別の決まり（依頼書 C2）。今回は変えていない |
| money の `units` の DAD の二重計上 | 今回の変更の前からの動き。legacy の値を変えないために、そのままにした（報告書 §5） |
| シミュレーター（`inventory.py`）の `demand_fulfilled` | 別の計算（在庫シミュレーション）。`qty_basis` は `simulated` |
| サンプル内のスクリプト（`data/sample/*/verify`・`exercises`） | 方式を渡していないので、これまでどおり要求ベース（`qty_basis=request`） |
