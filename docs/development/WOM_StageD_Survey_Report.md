# 段階 D（金額編）の設計のための調査　報告

- 依頼書：`requests/RequestLetter_StageD_Survey_to_CodeKun.md`
- 前提：`docs/design/drafts/WOM_ValueChain_Model_StageD_Design_v1.0.md`（以下「設計草案」）
- 実施：Code君（Claude Code, Windows）、2026-10-01
- 種別：**読み取り・計測だけ**。コード・データ・golden は変えていない。commit していない。直し方は書いていない。

本書は「観測結果（実行して測った）／コードで確かめたこと／推定／未確認」を分けて書く。

---

## 0. 測定の条件（固定）

| 項目 | 値 |
|---|---|
| SHA（着手時・測定時とも） | `7037bd369c1e652b9e41a987e199f69b156a08e7`（ブランチ `wom-v1r5m1_cap_trial`）。測定中にブランチは進んでいない |
| 実行の経路 | headless（`tools/run_headless_from_folder.run`）。GUI の経路は測っていない |
| 入力 | `data/sample/<model>` を**一時フォルダに複写**し、複写に対して実行（warmup の生成行が原本に書かれないように）。測定の前後で `git status` に変化なし |
| 対象 | 13 golden ＋ `soysauce-jpy-2027-alloc` ＋ `ev-thailand-2026_update`（S5 のため）＝15 条件 |
| プラグイン | 13 golden：各 `tests/golden/<model>.json` の `config.plugins`（全モデルとも `BufferingStockOptimizerPlugin, CapacityOverridePlugin, HolidayCalendarPlugin, …`）。alloc と ev_update：`safe` |
| lot_flow_mode | 各モデルの `planning_config.csv` に従う：rice だけ `legacy`、ほかの 14 条件は既定の `identity` |
| cpu_size | **15 条件すべて 1**（`planning_config.csv` に `cpu_size` があるのは bom-test の 1 だけ。ほかは既定 1） |
| alloc の需要 | 原需要（`demand_forecast.csv`）。配分から生成した需要ではない |
| 測定の道具 | `docs/development/stage_d_survey/stage_d_measure.py.txt`・`stage_d_kitting.py.txt`（参照用の写し。WOM からは読み込まない）。結果は同じフォルダの `stage_d_measure.json`・`stage_d_kitting.json`・`s2_leaf_compare.csv` |

---

## 1. S1　今の PPC の計算の経路

### 1.1 表

| 観点 | 今の PPC（コードで確かめたこと。観測結果は ◆） |
|---|---|
| 起点 | **市場 leaf（`leaf_out`）の実出荷だけ**。`ppc_psi_bridge.psi_to_sales_records` が、各 leaf_out の `_actual_ship[w]` の Lot 数を、(製品, チャネル, 週) ごとに 1 行へまとめる（lot_id は `PSI-<製品>-<チャネル>-<週>` の合成 ID）。実出荷の記録が無い leaf は、identity では販売記録を作らず警告、legacy では計画の S を使う。中間ノードの出荷は起点にしない。◆ 15 条件とも、販売記録の数量の合計 ＝ leaf の実出荷 Lot 数（rice は合成 ID 310 種類が各 4 回重複。4 地域が `JP_Channel` に写像されるため） |
| 数量 | `qty = Lot 数 × sc_tree.cpu_size`（`bom_qty` は leaf には掛けない）。事象（PPCEvent）の `amount_base` は **1 単位当たり**、集計（`ppc_kpi.py`）で `× qty`。◆ cpu_size ＝ 1 のため、どのモデルでも `qty ＝ Lot 数` |
| 週 | **すべての費用・売上を、その販売記録の週（leaf の出荷週）に計上する。** 部材の仕入・加工・輸送・関税も、実際にその工程があった週ではなく販売週。◆ 15 条件の全事象で「事象の週 ＝ その販売記録の週」（`all_at_sale_week=True`）。例：Cookie の Factory_GP_CN は、自分の最初の出荷が 2025-W41、PPC の最初の計上は 2026-W02 |
| ノード | 売上（`market_revenue`）は leaf_out にだけ立つ。中間ノードの費用は、**leaf の販売記録 1 行ごとに、経路をさかのぼって、そのノードの単価 × leaf の qty** で作る（中間ノード自身の出荷数量は使わない）。経路は、generic の場合 sc_tree の祖先をたどって作る。Cookie（`cookie`）・iphone_global（`iphone_global`）・rice（`rice`）は、`ppc_engine.py` に**固定で書かれた経路**を使う。◆ 数量の合計は、中間ノード自身の実出荷の合計と一致した（15 条件・全ノード）。**例外：iphone_global の Foxconn_CN**（PPC の qty 219,439、自身の出荷 119,133）。固定の経路が iPhone16 のすべてを Foxconn_CN に割り当て、Foxconn_IN（もう 1 つの MOM）を経路に持たないため |
| 区間 | ① 供給者 → MOM（中間の MOM を含む）：運賃（`ppc_edge_cost_rule`）。② MOM → 最初の DAD：関税・運賃・保険（ここが輸入の区間として扱われる）。③ DAD → DAD：運賃。④ 最後の DAD → チャネル：運賃と、関税の規則があれば関税。**supply_point は経路に入らない**（MOM から最初の DAD へ直接とぶ）。単価はすべて `rate × 1 + fixed_amount`（1 単位当たり）で、`× qty` は集計で行う。保険は `rate × 移転価格`（◆ 15 条件とも保険の事象は 0 件） |
| 移転価格 | `ppc_transfer_price_rule.csv` の**終端の MOM** の規則だけを使う（cost_plus：MOM までの原価 × (1＋率)、fixed：固定値）。使い道は 3 つ：(a) `mom_profit`（移転価格 − MOM までの原価。Profit Zone の集計だけに入り、ノード別 P&L・総原価には入らない）、(b) 関税の課税標準、(c) 保険の基準。**どのノードの売上にも、どのノードの仕入にもならない**（総原価は供給者・加工・運賃などの実費の合計で、移転価格を含まない）。◆ 使われない規則：iphone の Foxconn_IN・TSMC_TW 系（4 行）、smartx の FoundryTW 系（3 行）、rice の MOM_China |
| 通貨 | すべて**販売週の為替**で換算（部材の仕入も販売週の為替）。`ppc_fx_rate.csv` から、`base_currency` がこの実行の基準通貨の行だけを読み、「通貨 → 基準通貨」の 1 方向だけを持つ。その週が無ければ、それより前の最も近い週の為替を使う。基準通貨は、モデルの `ppc_fx_rate.csv` の `base_currency` 列が 1 種類ならそれ（無ければ JPY） |

### 1.2 そのほか、コードで確かめたこと

- **使われないマスターの行**（◆ 事象の台帳と照合）：計画の木の上で supply_point をはさんで書かれた区間（`MOM->SP_…`、`SP_…->DC_…`）の運賃の行は、Cookie・ev-europe・ev-thailand（2 条件）・oil・smartx で読まれていない（計 40 行）。supply_point は inbound と outbound をつなぐ仮想のノード（グローバル需給センター）で、物理の輸送は発生しない。Cookie・ev-europe・ev-thailand・oil では、これらの行は `ppc_node_cost_rule` の運賃（MOM と DAD のノード費用）と同じ輸送・同じ金額の二重表記で、PPC はノード費用の側で 1 回計上している（Claude 確認、2026-10-01）。smartx は金額が一致せず、未確認。iphone の DC_AMER などのノード費用（固定の経路が DC を通らない）。soysauce-us の欧州の行（需要が無いため）。
- **Cookie の同じ輸送の二重計上（推定）**：DC_Import_Main では、`DC_Import_Buffer->DC_Import_Main` の運賃 1,000 円（`ppc_edge_cost_rule`）と、DC_Import_Main のノード費用「国内陸送費（保税倉庫→国内DC）」1,000 円（`ppc_node_cost_rule`）の両方が、同じ 312 件の販売記録に計上されている（◆ 台帳で確認）。説明の文言からは同じ輸送に見える。
- **関税の区間はモデルで違う**：Cookie・ev・apparel-us・oil・bom-test は MOM → 最初の DAD。soysauce（4 条件）と apparel-global は **DC → leaf（最後の区間）**。smartx は両方。
- 中身が無いときの扱い（黙った既定値）：市場価格が無い → 0（通貨 "JPY"）。供給者の原価が無い → 0（通貨 "CNY"。CNY の為替が無いモデルでは止まる）。マスターの数値の欄が数値でない → 0（`pd.to_numeric(...).fillna(0.0)`、為替の `rate` も同じ）。移転価格の規則が無い → 移転価格＝MOM までの原価、通貨の表示は "JPY"。cost_plus で為替が 0 → 1.0 とみなす。最後の区間の関税の通貨は常に "USD"（規則の通貨を見ない）。

## 2. S2　money（`money.py`・`sc_tree_to_df.py`）の経路

### 2.1 表

| 観点 | money（コードで確かめたこと。◆ 観測結果） |
|---|---|
| 起点 | `sc_tree_to_planning_df` の行：**leaf_out の行**（地域は sc_tree の `region` 列）と、**DAD の行**（地域 `DAD:<ノード名>`）。それ以外のノード（MOM・leaf_in・supply_point）の行は無い。数量は identity なら実出荷（`_actual_ship`）、legacy なら計画の S |
| 数量 | Lot 数 × cpu_size × そのノードの bom_qty。◆ 14 条件は `qty_basis=actual_ship`、rice は `request`（legacy） |
| 週 | その行の週（leaf・DAD の出荷週）。売上と原価は同じ週 |
| ノード | 売上 ＝ 数量 × `sku_master.selling_price`、原価 ＝ 数量 × `sku_master.unit_cost`。価格は (sku_id, region) で結合。**DAD の地域 `DAD:…` は sku_master に無いので、DAD の行の売上・原価は 0**（◆ 15 条件とも、価格のある DAD の行は 0 行）。価格の見つからない行は黙って 0（◆ leaf では 0 行）。中間ノードの売上・原価は作らない |
| 区間 | 無い（運賃・関税の考え方が無い。Landed Cost パネルは別の仕組み、§6） |
| 移転価格 | 使わない |
| 通貨 | **換算しない。** `sku_master` の価格の数値をそのまま足す。sku_master に通貨の列は無い |

### 2.2 PPC と money の違い（leaf ごと。◆ `s2_leaf_compare.csv`）

| モデル | PPC 売上 ÷ money 売上（leaf ごと） | 理由 |
|---|---|---|
| Cookie・bom-test・apparel-us・smartx | 1.000 | 同じ数量、同じ価格、同じ通貨 |
| soysauce-eu・us、apparel-global | 1.000〜1.013 | JPY の価格を固定の換算で sku_master に入れてある。PPC は週の為替 |
| soysauce-jpy・alloc | 1.000〜1.167 | sku_master は 2027 年の為替（USD 150、EUR 162）で換算済みの JPY。PPC は週の為替で、2028 年は USD 200・EUR 216 |
| ev-thailand（2 条件） | 4.25 | sku_master は THB、PPC は JPY（THB→JPY 4.25）。money は換算しないので THB のまま |
| ev-europe | 165 | sku_master は EUR、PPC は JPY（EUR→JPY 165） |
| oil-global | 1〜163 | **同じモデルの中で sku_master の通貨が製品ごとに違う**（日本 JPY、欧州 EUR、米国 USD）。money はそれらを換算せずに足している |
| iphone_global | 1,534,025〜1,545,784 | 価格の桁が 1 万倍違い（§3.3）、PPC は USD→JPY 換算 |
| rice | 比べられない | PPC はチャネル `JP_Channel` 1 つ（地域の区別なし）、money は地域ごと。PPC の価格は `data/ppc` の見本（8,000 円）、money は sku_master（320 万円／lot） |

原価は、PPC ＝ 経路の実費の積み上げ、money ＝ `unit_cost` × 数量で、作り方が違う（例：Cookie の原価 PPC 35.7 億円、money 26.0 億円）。

## 3. S3　単位の検証

### 3.1 積のたどり方

```
実出荷 lot 数 × 物量／lot（cpu_size） × 物量当たり単価 × 通貨換算
```

今の PPC のコードでは「物量」＝ qty ＝ Lot 数 × cpu_size。**cpu_size は 15 条件すべて 1** なので、「物量当たり」と「lot 当たり」は数の上で同じになる。

### 3.2 モデルごとの表

「コードの読み」＝コードが使う単位。「明記」＝マスターの説明・列名・sku_master の `uom`・設計文書に書かれた単位。「推測」＝値の大きさからの推測（推測と明記）。

| モデル | 実出荷 lot（leaf） | cpu_size | 市場価格（例） | コードの読み | 明記 | 推測 | PPC の約束と |
|---|---:|---:|---|---|---|---|---|
| Cookie-jp-2026 | 141,990 | 1 | 30,000 JPY | 1 qty（＝1 lot）当たり | ノード費用 `per_lot`・「JPY/lot」。uom=CS。edge_cost_master「1lot≈$14運賃」 | 1 lot ＝ 1 ケース（推測） | 合う（cpu=1） |
| apparel-global | 181,526 | 1 | 52 USD、7,900 JPY | 同上 | `per_lot`。uom=EA | 1 lot ＝ 1 着（推測） | 合う |
| apparel-us | 249,172 | 1 | 49 USD | 同上 | `per_lot`。uom=EA | 1 lot ＝ 1 着（推測） | 合う |
| bom-test | 100 | 1 | 32,000 USD | 同上 | `per_lot`。uom=EA | 1 lot ＝ 1 台（推測） | 合う |
| ev-europe | 53,140 | 1 | 42,000 EUR | 同上 | 「EUR/台」。uom=EA | 1 lot ＝ 1 台 | 合う |
| ev-thailand（2） | 63,240 | 1 | 1,659,000 THB | 同上 | 「THB/台」。uom=EA | 1 lot ＝ 1 台 | 合う |
| iphone_global | 414,090 | 1 | **9,990,000 USD**（Retail_AMER） | 同上 | 市場価格に単位の記載なし。uom=EA。sku_master は 999 | 市場価格は 1 万台分の値、または桁の誤り（推測。どちらかは決められない） | **合わない**（§3.3） |
| oil-global（日本・輸入） | 191,029（全体） | 1 | 170,000 JPY | 同上 | ノード費用は `basis=per_lot` だが説明は「JPY/kL」。uom=KL | 1 lot ＝ 1 kL（推測） | 列（per_lot）と説明（/kL）が食い違う。cpu=1 なので数は合う |
| oil-global（Hormuz・RedSea） | （上に含む） | 1 | 2,700,000,000 JPY | 同上 | uom=`KL100KBBL`（そのままの表記） | 1 lot ＝ 10 万バレル（CLAUDE.md の記載） | 同じモデルの中で 1 lot の大きさが製品ごとに違う |
| rice | 235,316 | 1 | 8,000 JPY（`data/ppc`） | 同上 | sku_master の uom=`lot`、価格 3,200,000 JPY | PPC は見本のマスターで、rice 用ではない（推測） | 比べられない |
| smartx | 709,811 | 1 | 699 USD | 同上 | uom=EA | 1 lot ＝ 1 台 | 合う |
| soysauce（4 条件） | 75,291〜100,501 | 1 | 40 USD、38 EUR、3,840 JPY | 同上 | uom=CS（1CS=12x1L）。edge_cost_master「約4.5USD/ケース」 | 1 lot ＝ 1 ケース | 合う |

- 供給者の原価・ノード費用・区間の費用は、コードではすべて「1 qty 当たり」として `× qty` される（`rate × 1 + fixed_amount`）。`bom_qty` が 1 でない場合だけ、供給者の原価に `× bom_qty` が加わる（◆ 今のモデルに該当なし）。
- `basis` 列の値は、15 条件で `per_lot` だけ（チャネルの `revenue` 基準は、`ppc_profit_zone.py` のチャネル費用だけが読む）。

### 3.3 iphone_global の 641 兆円

◆ PPC の売上 641,014,134,734,200 円 ＝ Σ（qty × 市場価格 × その週の USD→JPY）。

| 例：Retail_AMER_i15 | 値 |
|---|---|
| 実出荷 lot（＝qty） | 34,580 |
| 市場価格 | 6,990,000 USD（`ppc_market_price.csv`） |
| 為替 | 150.92〜155.79 JPY/USD（`data/ppc/ppc_fx_rate.csv`。iphone_global に自分の為替の表は無く、見本の表を使う） |
| PPC 売上 | 37,079,557,882,200 円 |
| money 売上 | 34,580 × 699 ＝ 24,171,420（sku_master の `selling_price`、通貨の換算なし） |

- 9 つのチャネルすべてで、**PPC の市場価格 ＝ sku_master の `selling_price` × 10,000**（9,990,000／999 など）。
- したがって PPC ÷ money ＝ 10,000 × 為替（約 153〜155）＝ 約 153 万〜155 万倍（◆ leaf ごとに 1,534,025〜1,545,784）。
- money の 4.16 億（416,331,210）は、qty 414,090 × 平均 1,005（USD の数値、通貨の表示なし）。
- 1 台 1,000 USD 前後という sku_master の値は iPhone の実際の価格帯と合う。PPC の市場価格・供給者の原価（Foxconn_CN 4,500,000 USD など）は、同じ 1 万倍の桁にある（推測：PPC のマスターだけが 1 万倍の単位で書かれている）。どちらの単位が意図されたものかは、マスターにも文書にも書かれていない（**未確認**）。
- 為替の表が 2028-W51 までしか無く、計画は 2029-W52 まで。2029 年の 53 週は、2028-W51 の為替をそのまま使っている（前の週への退避。警告は外に出ない、§6）。

## 4. S4　設計草案の割当での、今の価格の位置づけ

### 4.1 Cookie-jp-2026（§7.1 の割当）

| 取引・区間 | 設計草案の区分 | 今のマスター | 今の PPC での使われ方 |
|---|---|---|---|
| EXT_SUP_CN → Factory_GP_CN | 外部からの仕入 | 供給者の原価 8,000 JPY | 仕入原価 |
| Factory_GP_CN（E_CN）→ DC_Import_Buffer（E_JP） | **法人間の価格** | 移転価格 fixed 18,000 JPY | 関税の課税標準（15％）と `mom_profit` だけ。売上・仕入としては計上されない。**JPY 建て**（設計草案では E_CN の機能通貨は CNY） |
| EXT_SUP_JP → Factory_DP_JP | 外部からの仕入 | 供給者の原価 11,000 JPY | 仕入原価 |
| Factory_DP_JP → DC_Local_JP（どちらも E_JP） | **法人内の管理価格** | 移転価格 fixed 21,000 JPY | 同上（関税率 0） |
| DC → Retail_JP_SM（①）・Retail_JP_EC（③） | 最終市場の価格（グループの外部売上） | 市場価格 30,000 JPY | leaf の売上 |
| DC → Retail_JP_CVS（②） | **卸価格**（グループの外部売上） | **無い** | — |
| Retail_JP_CVS → 消費者（②、観測用） | 最終市場の価格 | 市場価格 30,000 JPY | 今は、これがグループの売上として計上されている |

- 設定が無いもの：**CVS への卸価格**（1 件）。法人間の区間（E_CN→E_JP）には価格がある。
- 3 つのチャネルの市場価格は同じ 30,000 JPY。
- Cookie の PPC は `ppc_engine.py` の固定の経路（`cookie`）で動く。関税の区間は `Factory_GP_CN->DC_Import_Buffer`（supply_point を飛ばす）。

### 4.2 soysauce-jpy-2027-alloc（§7.2 の割当）

| 取引・区間 | 設計草案の区分 | 今のマスター | 今の PPC での使われ方 |
|---|---|---|---|
| EXT_SUP_JP_MAT → Materials_JP → Brewing_Noda | 外部からの仕入 | 供給者の原価 6.0 USD（2028-W10 に 8.0、W26 に 6.5） | 仕入原価 |
| Bottling_Noda → FG_WH_Noda（どちらも E_JP） | **法人内の管理価格** | 移転価格 cost_plus 10％、USD | 関税の課税標準と `mom_profit` だけ |
| FG_WH_Noda（E_JP）→ DC_US_SF・DC_US_NY（E_US） | **法人間の価格** | **無い**（運賃 4.0／4.5 USD だけ） | — |
| FG_WH_Noda（E_JP）→ DC_EU_RTM（E_EU） | **法人間の価格** | **無い**（運賃 6.0 USD だけ） | — |
| FG_WH_Noda → DC_JP（どちらも E_JP） | 法人内 | 無い（運賃 1.0 USD） | — |
| DC_US_SF → Rest_US_West（①） | 最終市場の価格 | 市場価格 40 USD | leaf の売上 |
| DC_JP → Rest_JP（①） | 最終市場の価格 | 市場価格 3,840 JPY | leaf の売上 |
| DC_US_NY（E_US）→ Rest_US_East（②） | **卸価格** | **無い** | — |
| DC_EU_RTM（E_EU）→ Rest_FR・BE・NL（②） | **卸価格** | **無い**（3 件） | — |
| Rest_US_East・FR・BE・NL → 消費者（②、観測用） | 最終市場の価格 | 市場価格 40 USD、38 EUR | 今は、これがグループの売上として計上されている |

- 設定が無いもの：**法人間の価格 3 区間**（→ DC_US_SF、→ DC_US_NY、→ DC_EU_RTM）、**卸価格 4 件**（Rest_US_East、Rest_FR・BE・NL）。
- 関税（米国 12.5％、欧州 8％）は、今は **DC → Rest の区間**（最後の区間）に計上され、課税標準は Bottling_Noda の移転価格（USD）。国境を越える区間（FG_WH_Noda → DC）には関税の規則が無い。
- 中間の MOM（Brewing_Noda）には移転価格の規則が無い（終端の MOM の規則だけが使われる）。

## 5. S5　Kitting の「部材がそろった」と「組立の完了」

### 5.1 コードで確かめたこと（`forward_planner._process_assembly_with_yards`）

- 組立ノードの子がすべて `stockyard` のときに、Kitting Gate が働く。
- `node.kitting[需要週][lot_id] = {置場の名前: 到着週}`：**各置場への到着週を、その lot の需要週（Backward の S の週）をキーにして記録する**。組立を実行した週は、この記録には入らない。
- 完成品が組立ノードの P に入るのは、次の 3 つがそろった週：(a) その lot_id が、すべての置場の在庫（I）にある、(b) その lot の需要週が来ている（未完了の要求として保持されている）、(c) 能力が残っている（`processing_limit`：休みの週は 0、未設定なら上限なし）。
- 能力で待ったときは `ForwardPlanResult.kitting_capacity_deferred` に **(ノード, 週, 件数)** として残る（lot_id は残らない）。待っている間、部材は各置場の I に残り、置場の I の週ごとの記録として見える。
- 置場を持たない組立（`supply_role` が confluence でない親）では、`_propagate_to_parent` が到着を `kitting` に記録するが、ゲートは無い（部材がそろわなくても P に入る）。

### 5.2 観測結果（◆ `stage_d_kitting.json`）

「そろった週」＝ すべての置場への到着週の最大。「P の週」＝ 組立ノードの P に最初に入った週。

| 条件 | 組立ノード | そろった lot | P に入った lot | P の週 − そろった週 | 能力待ちの記録 |
|---|---|---:|---:|---|---:|
| ev-thailand-2026_update | Factory_Local_TH | 52,700 | 52,700 | すべて 0 週 | 0 |
| 同・**変形**（一時の複写で Factory_Local_TH の能力 2,900 → 400） | Factory_Local_TH | 45,045 | 45,045 | すべて 0 週 | 0 |
| bom-test-2026 | Vehicle_Assy | 100 | 100 | すべて 0 週 | 0 |
| 同・**変形**（一時の複写で Vehicle_Assy に能力 3／週を追加） | Vehicle_Assy | 100 | 100 | すべて 0 週 | 0 |
| ev-europe-2026（参考） | Factory_Local_DE | 44,325 | 44,325 | すべて 0 週 | 0 |
| ev-europe-2026（参考） | **Factory_Import_HU** | 8,815 | 8,815 | **すべて +1 週** | 0 |

- 依頼書の 2 モデル（ev_update・bom-test）では、「そろった週」と「P の週」は、すべての lot で同じ週だった。
- **能力待ちは再現しなかった。** 能力を下げた変形でも、Backward が能力に合わせて需要（＝部材の到着）を前へずらすため、ゲートで待つ lot は出なかった。能力を下げた影響は「そろう lot が減る」（52,700 → 45,045）として現れた。
- **違う週になる例は、能力ではなく需要週で起きた**：ev-europe の Factory_Import_HU では、全 8,815 lot で部材が需要週の 1 週前にそろい（例：そろった 2025-W48、需要週 2025-W49）、P に入ったのは需要週（2025-W49）。その 1 週の間、3 つの部材は各置場の I に残っていた。
- **未確認**：休みの週（`operating_calendar` の shifts=0）で待つ場合、能力待ちが実際に起きる条件、その記録の形。

## 6. S6　為替のデータと扱い

### 6.1 各モデルの為替の表（◆）

「計画の週で足りない」＝ PPC が実際に使った基準通貨以外の通貨について、計画の週ごとに「その週の為替あり／前の週へ退避／どの週にも無い（止まる）」を数えたもの。

| モデル | 表の出どころ | 基準通貨 | 通貨の組 | 表の週 | 計画の最初の週 | 計画の週で足りないもの |
|---|---|---|---|---|---|---|
| Cookie | **`data/ppc` の見本**（モデルに表が無い） | JPY | CNY→JPY、USD→JPY | 2026-W01〜2028-W51 | 2025-W37 | JPY だけを使うので影響なし |
| apparel-global | モデル | USD | JPY→USD（USD→USD） | 2028-W01〜2029-W52 | 2027-W40 | JPY：助走週 13 週が無い |
| apparel-us | モデル | USD | USD→USD | 2026-W01〜2027-W52 | 2025-W37 | — |
| bom-test | モデル | USD | USD→USD（1 行） | 2026-W01 | 2025-W36 | — |
| ev-europe | モデル | JPY | EUR・HUF・USD→JPY | 2026-W01〜2027-W51 | 2025-W37 | EUR：助走週 16 週が無い |
| ev-thailand（2） | モデル | JPY | CNY・THB・USD→JPY | 2026-W01〜2027-W51 | 2025-W37 | THB：助走週 16 週が無い、1 週は退避 |
| iphone_global | **`data/ppc` の見本** | JPY | CNY→JPY、USD→JPY | 2026-W01〜2028-W51 | 2026-W28 | USD：**2029 年の 53 週は退避** |
| oil-global | モデル | JPY | EUR・USD→JPY | **3 週だけ**（2027-W01、W20、W31） | 2026-W28 | EUR・USD：助走週 26 週が無い。ほか 75〜77 週は退避（段階状の時系列として書かれている） |
| rice | `data/ppc` の見本（全マスター） | JPY | CNY・USD→JPY | 2026-W01〜2028-W51 | 2026-W01 | JPY だけ |
| smartx | モデル | USD | USD→USD | 2026-W01〜2030-W52 | 2025-W36 | — |
| soysauce-eu・us | モデル | USD | EUR→USD、JPY→USD | 2027-W01〜2028-W52 | 2026-W28 | 助走週 26 週が無い |
| soysauce-jpy・alloc | モデル | JPY | EUR・USD→JPY（JPY→JPY） | 2027-W01〜2028-W52 | 2026-W28 | 助走週 26 週が無い |

- どのモデルも、表は「各通貨 → 基準通貨」の 1 方向だけ。
- **今は、助走週に販売が無いので、助走週の為替が無くても止まらない**（PPC はすべてを販売週に計上するため）。費用を発生週で記録する方式にすると、助走週に基準通貨以外の費用があるモデル（上の 9 条件）で「どの週にも無い」に当たる（推定）。

### 6.2 三つの役割（設計草案 §5）で表示するのに足りない組

- コード：`FXConverter` は「通貨 → 基準通貨」の方向だけを引く。基準通貨から他の通貨への換算（逆数）や、2 つの外貨の間の換算（EUR→USD など）の機能は無い。
- データ：同じ週に両方の通貨の「→ 基準通貨」の行があれば、割り算で別の組を作れる。その意味で、soysauce-jpy・alloc（USD と EUR → JPY）は、評価通貨 USD・現地通貨 EUR の換算に必要な値を持っている（◆ 2027 年は EUR/USD ＝ 162／150 ＝ 1.08、2028 年も 216／200 ＝ 1.08）。
- データに無いもの：
  - iphone_global・smartx：市場は AMER・EMEA・APAC だが、現地通貨（EUR など）の為替が無い（市場価格もすべて USD）。
  - apparel-global：JPY→USD だけ。
  - Cookie：E_CN の機能通貨とされる CNY の為替は見本の表にあるが、Cookie の価格・原価はすべて JPY 建て。
  - 助走週の為替（§6.1）。

### 6.3 為替が無いときの今の動き（コードで確かめたこと）

| 場所 | 為替が無いとき |
|---|---|
| `ppc_fx.py` | その週が無ければ前の週（◆ 実際に退避が起きている：iphone 53 週、oil 75〜77 週、ev-thailand 1 週）。どの週にも無ければ `ValueError` で止まる。**退避の警告は `FXConverter.fallback_warnings` に貯めるだけで、ファイルにもログにも出ない**（どこからも読まれていない） |
| `ppc_rules.py` | 為替の `rate` が数値でなければ 0 にする（`fillna(0.0)`） |
| `ppc_transfer.py` | cost_plus で為替が 0 → **1.0 とみなす**。移転価格の事象に書く為替の値が取れなければ 1.0 |
| `ppc_tariff.py` | 最後の区間の関税の通貨を常に "USD" として換算する |
| money（`money.py`） | **換算そのものが無い**（§2） |
| Landed Cost（`landed_cost.py`） | `ppc_fx_rate.csv` を使わない。`edge_cost_master.csv` の `fx_rate` 列（シナリオごとの固定値）を使い、**空欄や 0 は黙って 1.0**。全ルートの単純平均を使う。例：soysauce-jpy-alloc の `fx_rate` は 1.0（USD→USD）だが、money の値は JPY の数値 |
| GUI（Management） | 今の計画の PPC がある間は、Landed Cost の売上・関税を PPC の台帳の値で上書きする（money の値は運賃の列だけに残る） |

## 7. 設計草案と食い違う点・見落としている点

1. **§5.4 の 4 の括弧書き「前の週の為替を使い、警告を残す」**：警告はメモリに貯めるだけで、どこにも出ていない（§6.3）。退避は計画の終わりの側（iphone の 2029 年、53 週）でも黙って起きている。
2. **§6 warmup・§5.4**：今の為替の表の多く（9 条件）が助走週を含まない。今は販売週だけに計上するので表に出ないが、発生週で記録すると、助走週の外貨の費用で止まる（推定）。
3. **v0.1 §4 の「money：ノードごとの売上・原価」**：money が作るのは leaf_out と DAD の行だけで、DAD の行の金額は常に 0。**通貨の換算が無く**、sku_master の価格の通貨がモデルごと（ev-thailand は THB、ev-europe は EUR）、さらに同じモデルの中でも製品ごとに違う（oil）。money の合計は、一部のモデルでは通貨の違う数値の合計である。
4. **§3.6 の「PPC の約束（単価は物量当たり、集計で qty）」**：コードはそのとおりだが、cpu_size が全モデルで 1 なので、今のマスターは「lot 当たり」と「物量当たり」を区別していない。oil では `basis=per_lot` と説明「JPY/kL」が並び、同じモデルの中で 1 lot の大きさが製品ごとに違う。iphone_global は PPC のマスターだけが sku_master の 1 万倍。
5. **§7.1 の「今の移転価格 18,000 JPY は E_CN → E_JP の法人間の価格」**：今の PPC では、移転価格は売上・仕入として計上されず、関税の課税標準と Profit Zone（`mom_profit`）にだけ使われる。JPY 建て（E_CN の機能通貨とされる CNY ではない）。
6. **§7.2**：関税が、国境を越える区間（FG_WH_Noda → DC）ではなく、DC → 市場 leaf の区間に計上されている。§2.3（出荷時に支配が移転し、運賃・関税は在庫原価）で、どの区間の在庫原価に入れるかを決めるとき、今の区間とずれる。
7. **§3.3 の「② の場合：親（DC など）から leaf_out への出荷がグループの外部売上」**：今の PPC に、DC から leaf への出荷の記録は無い（leaf の実出荷＝販売だけ）。ただし数量の PSI では、DC 自身の実出荷（`_actual_ship`）は記録されており、合計は leaf の実出荷と一致した。
8. **§2.4 の Kitting**：「そろった週」と「P の週」は、今のモデルでは多くが同じだが、**需要週を待つために 1 週ずれる例がある**（ev-europe の Factory_Import_HU、全 8,815 lot）。能力待ちの記録は「件数」だけで lot_id を持たない。`kitting` の記録は需要週をキーにし、組立を実行した週を持たない。
9. **題材のモデルが、PPC の汎用の経路で動いていない**：Cookie と iphone_global は `ppc_engine.py` に固定で書かれた経路（`cookie`・`iphone_global`）で動く。iphone は固定の経路のため、2 つ目の MOM（Foxconn_IN）の原価・数量が PPC に入らない（§1.1）。rice はモデルに PPC のマスターが無く、`data/ppc` の見本で動く。
10. 設計草案が触れていない点：
    - Cookie の DC_Import_Buffer → DC_Import_Main の運賃が、区間の費用とノードの費用の両方に計上されている（同じ輸送の二重計上と推定。§1.2）。
    - 計画の木の上で supply_point をはさんで書かれた区間の運賃の行（40 行）が読まれていない。supply_point は仮想のノードで物理の輸送は無く、smartx 以外はノード費用と同じ輸送の二重表記（§1.2）。
    - PPC の lot_id は合成 ID（`PSI-<製品>-<チャネル>-<週>`）で、LOVEM の実出荷の Lot_ID とは 1 対 1 でない（1 行が 1 週分の多数の Lot をまとめる）。rice では合成 ID が 4 回ずつ重なる。§8 の受入条件 2（出荷の記録と LOVEM の実出荷を 1 対 1 で照合）は、今の PPC の記録単位とは違う。
    - Landed Cost が、`ppc_fx_rate.csv` とは別の為替（`edge_cost_master.csv` の固定値）を持つ。為替の体系が 2 つある（§5.4 の 5「為替の体系を 1 つに」に関係）。

## 8. 未確認の点

- GUI の経路の PPC（プラグインの組が golden と違う場合、値が変わる。前回の GUI 自動確認では iphone の売上 640,773,326,445,600、今回の headless では 641,014,134,734,200）。本調査は headless の値だけを使った。
- iphone_global の PPC のマスターの 1 万倍が、意図した単位（1 万台当たり）か、桁の誤りか。
- oil の 1 lot の大きさ（kL）と、`KL100KBBL` の意味。
- sku_master の価格が、どの通貨のつもりで書かれているか（列が無い）。
- Kitting の能力待ち・休みの週での待ちが、実際にどの条件で起きるか。
- `ppc_node_profit_zone.csv` の `country` と法人の割当の関係（今回は使っていない）。
- 保険（`insurance_cost`）が実際に使われるモデル（15 条件とも 0 件）。
