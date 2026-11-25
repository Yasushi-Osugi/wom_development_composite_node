# 4P 施策 → WOM の設定 翻訳表（v0.1c）

- 作成：Code君（2026-11-20）／依頼：大杉さん
- 目的：note 記事「戦略 WOM コックピット」のステップ 3 の表を、実際のファイル・列・単位・止める条件に落とす。Claude君の設計と、翻訳の道具の依頼書の材料。
- 根拠：作業ツリー `wom-v1r6m0_BS-SEAF`（HEAD 8b8f181 と、まだ commit していない段 1 の変更）の `data/sample/*` の CSV の見出しと、ローダのコードで確かめた。
- 対象外：エンジン・PPC・Value Chain のコードを変える提案は書かない。「今は表せない」と書いた所は、作るかどうかを決めるための材料。

## 0. 読み方

| 印 | 意味 |
|---|---|
| **W** | WOM が計算する（設定を置けば、生産・物流・在庫・損益への波及が出る） |
| **H** | 人が置く仮説（WOM は計算しない。外側で数に換算して、W の設定に入れる） |
| **×** | 今の WOM では表せない（道具は黙って捨てずに止める） |
| 止める（既存） | 今のローダ・エンジンがすでに止める条件 |
| 止める（道具） | 翻訳の道具が足すべき条件（今は止まらない、または別の所で気づく） |

共通の単位：
- **週**は ISO 週のラベル `YYYY-WNN`。
- **数量**は lot（`cpu_size` 倍で物の数。`planning_config.csv` の `cpu_size`、既定 1）。
- **金額**は行ごとの `currency`（`ppc_fx_rate.csv` で基準通貨に換算）。
- **単価は物量単位当たり**（PPC・Value Chain は lot 数 × `cpu_size` を掛ける。化粧品は `cpu_size`＝24 で、EC のクリームは 131 SGD／個 ＝ 1 lot 3,144 SGD）。v0.1 の「金額／lot」は誤りで、2026-11-21 に列ごとに直した（GPT君のレビュー）。確かめていない列は「要確認」と書いた。
- **市場**の鍵は `demand_forecast.csv` の `region`。これは地理ではなく、leaf_out ノードの識別子。`(sku_id, region)` と leaf_out は 1 対 1。

## 1. 翻訳表

### Product（製品）

| 施策の型 | 人が決める入力 | ファイル・列 | 単位 | 翻訳の規則 | 止める（既存） | 止める（道具） | 印・確かめる影響 |
|---|---|---|---|---|---|---|---|
| 新製品を足す | 製品 ID・名前・原価・荷姿 | `sku_master.csv`：`sku_id, sku_name, region, uom, unit_cost, selling_price, shelf_life_wks, active` | 要確認（`unit_cost`・`selling_price` の単位）、週 | 製品 × 販売先の行を足す | — | 同じ `sku_id` が計画の木に無い | W：製品別採算 |
| 供給の経路・工程 | 工場・倉庫・販売先、つながり | `sc_tree_master.csv`：`node_name, parent_node, product_name, node_type, side, lt_wks, region`。`node_master.csv`：`node_id, lat, lon, node_type` | 週 | 製品ごとに InBound（leaf_in → mom）と OutBound（supply_point → dad → leaf_out）の木を作る。leaf_out には `region` が要る | `yield_rate`・`ss_days`・`init_stock_days`・`demand_envelope` の不正値（`TreeAttributeError`） | 親の無いノード（mom・supply_point 以外）、leaf_out の `region` の重複、node_master に座標が無い | W：経路ごとの数量・LT |
| 材料・部材（BOM） | 部材の供給元と員数 | `sc_tree_master.csv`：leaf_in の行、`bom_qty`、`supply_role` | 個／完成品 1 lot | 部材ごとに leaf_in を 1 行 | — | `bom_qty` が正の整数でない | W：部材の調達量 |
| 歩留まり | 良品の割合 | `sc_tree_master.csv`：`yield_rate`（mom の行だけ） | 0 < y ≦ 1 | 能力 × y が良品の上限になる | 範囲外、mom 以外に 1.0 以外、legacy・push の mom（`YieldRateError`） | — | W：必要な投入能力 |
| 必要生産能力 | 工場の週の能力 | `capacity_plan.csv`：`sku_id, node_name, week, max_supply`、任意で `cap_soft` | lot／週 | 計画期間の全週に行を置く。**行が無い週は上限なし**。作れない週は 0 | 計画の木に無いノード名、負・数値でない値 | 計画期間内に行の無い週がある（発売前に作り溜めが起きる） | W：設備負荷、能力不足による未充足 |
| 操業の日程 | 休業・シフト | `operating_calendar.csv`：`sku_id, node_name, week, shifts`（0〜21）。`holiday_calendar.csv`：`start_week, end_week, node_name, effect, value` | shift／週 | 0 shift ＝ 休業。shift から cap_soft を導く | — | `effect` が既知の値でない | W：休業前の作り溜め |
| 投入週 | 発売の週・立ち上がり | `market_entry_plan.csv`：`sku_id, region, launch_week, steady_lots_per_week, ramp_weeks, ramp_ratio` → `tools.gen_demand_from_entry_plan` → `demand_forecast.csv` | 週、lot／週、比 | 発売前は 0、立ち上がり期は steady × ramp_ratio、その後は steady。**変換の道具の型 `product_launch_week`**（2026-11-25）：案の投入の表の対象の行の `launch_week` だけを施策の週に置き換え、道具 1 で需要を作り直す（需要の正本は投入の表のまま）。立ち上げの一時費用は型 `launch_one_time_cost`（発生の週の 1 週の行、週額＝総額）、販路の維持費は型 `launch_weekly_cost`（有償の週の週額）で、案の `inputs/fixed_cost.csv` に書く | 列の不足、鍵の重複、鍵が木に無い、週のラベルが不正、期間の外、負・空欄、価格・通貨が `ppc_market_price.csv` と違う | 投入の表が無い案、投入の表の対象の行が 1 行でない、作った需要が対象の外で凍結した元のモデルの需要と違う、同じ鍵の投入週が案に 2 つ、一時費用の週が 1 週でない、投入の費用の負担法人（対象の市場が外部なら、その市場へ売る親のノードの法人と一致） | W：既存製品と能力を取り合う量 |
| 原価 | 仕入値・加工費 | `ppc_supplier_cost.csv`：`supplier_node, product_id, week, purchase_price, currency`。`ppc_node_cost_rule.csv`：`node_id, product_id, cost_type, basis, rate, fixed_amount, currency` | 金額／物量単位（lot × `cpu_size` の 1 単位。Start Here R7） | 仕入値は週の段階（その週以前の最後の行）。拠点の費用は週によらない | 規則の無い製品の販売は評価から外す（`valuation_status=partial`） | 計画に出る工場・拠点に規則が無い | W：粗利 |

### Price（価格）

| 施策の型 | 人が決める入力 | ファイル・列 | 単位 | 翻訳の規則 | 止める（既存） | 止める（道具） | 印・確かめる影響 |
|---|---|---|---|---|---|---|---|
| 販売単価（市場・チャネル別） | 市場 × 製品 × 開始週の単価 | `ppc_market_price.csv`：`market_node, product_id, week, market_price, currency` | 金額／物量単位（lot × `cpu_size` の 1 単位。Start Here R7） | 値が変わる週だけ行を置く（その週以前の最後の行が効く）。`market_node` は leaf_out の名前 | 行の無い市場・製品は評価から外す。最初の行より前の週は最初の行で評価し、記録する | `market_node` が木の leaf_out に無い、通貨が `ppc_fx_rate.csv` に無い | W：売上・単位利益 |
| （同上、money の台帳） | 同上 | `sku_master.csv`：`selling_price`（製品 × `region` の行） | 要確認（money の台帳の単位。PPC と同じ物量単位当たりかを確かめる） | PPC と同じ値にそろえる | — | PPC の単価と食い違う（Management の P&L は PPC で上書きされる） | W |
| 値引き | 期間・率 | `ppc_market_price.csv` | 金額／物量単位（lot × `cpu_size` の 1 単位。Start Here R7） | 開始週に下げた単価の行、終了の翌週に元の単価の行 | 同上 | 終了の行を置き忘れる（値引きが計画の最後まで続く） | W：単位利益 |
| 卸値・振替価格 | 取引ごとの単価・方式 | `vc_price_rule.csv`：`edge_id, product_id, price_type, week, price, currency`。`ppc_transfer_price_rule.csv` | 金額／物量単位（lot × `cpu_size` の 1 単位。Start Here R7） | 区間（`親->子`）ごと | Value Chain のローダ（`MasterError`） | — | W：法人別の損益 |
| 価格弾力性 | 「単価 −x% で数量 +y%」の仮説 | （WOM に列は無い） | — | **外側で週別の需要に換算**し、`demand_forecast.csv` または `market_entry_plan.csv` の数量に入れる。換算の式と係数は案の記録に残す | — | 仮説の係数が書かれていないのに単価だけ変えた（数量は変わらない計算になる。黙って進めない） | **H** → W：販売量、供給不足 |

### Place（流通）

| 施策の型 | 人が決める入力 | ファイル・列 | 単位 | 翻訳の規則 | 止める（既存） | 止める（道具） | 印・確かめる影響 |
|---|---|---|---|---|---|---|---|
| 販売先を足す | 市場・チャネル | `sc_tree_master.csv`：leaf_out の行（`region`）。`demand_forecast.csv`：`region` | — | leaf_out を足し、需要の `region` をそろえる | — | 需要の `(sku_id, region)` に leaf_out が無い（今はその需要は lot にならず、`unmatched_keys` に記録されるだけで計画は進む）、leaf_out が重複する | W：届けられる量 |
| 供給経路の割り当て（工場が複数） | 市場 → 工場 | `lane_assignment.csv`：`sku_id, leaf_node_name, mom_node_id` | — | 1 市場 1 工場の固定表。`priority` 列は使われていない | — | 重複行（今は後の行が勝つ）、`priority` を書いた（効かない） | W |
| 輸送期間 | 区間の週数 | `sc_tree_master.csv`：`lt_wks`（子の行に、親 → 子の区間として書く） | 週 | 親の無い mom の `lt_wks` は使われない | — | 親の無い mom に 0 以外の `lt_wks` | W：届く時期 |
| 運賃・関税・為替 | シナリオ別の区間のコスト | `edge_cost_master.csv`：`scenario, src_region, dst_region, tariff_rate, fx_rate, freight_usd_per_lot`（任意で `product_id`）。`ppc_edge_cost_rule.csv`。`ppc_tariff_rule.csv`（`tools.gen_tariff_edges` で作る）。`route_master.csv` | 率、USD／lot | 関税の正典は `edge_cost_master.csv`、`ppc_tariff_rule.csv` は生成物（手で直さない） | `gen_tariff_edges --check` で食い違い | 生成物を手で直した | W：物流費・関税 |
| 在庫方針 | 安全在庫・立ち上げの在庫・置き場所 | `sc_tree_master.csv`：`ss_days`、`init_stock_days`、`buffering_stock_flag`。`push_config.csv`（push の工場） | 日（7 日で 1 週に切り上げ） | `ss_days` は在庫を持たせたい所の子に置く（InBound では供給元の leaf_in）。1 週未満は表せない | 0 以上の整数でない（`TreeAttributeError`） | InBound の mom 自身に `ss_days`（効かない） | W：在庫・資金負担 |
| 取引条件 | 売掛・買掛の期間 | `sku_master.csv`：`dso_wks`、`dpo_wks`。`vc_trade_terms.csv`：`incoterm, freight_borne_by` | 週 | — | Value Chain のローダ | — | W：CCC・資金 |
| 不足時の配分 | 市場の優先・公平 | 数量配分の表（コックピットの方針 `--allocation-file`、`--week-rule`）。`planning_config.csv`：`overflow_policy`（`tail`／`proportional_week`／`balance_cut_ratio`） | lot | 配分しないときの押し戻し方は `overflow_policy` | 知らない値（`OverflowPolicyError`） | — | W：市場別の充足 |

### Promotion（販促）

| 施策の型 | 人が決める入力 | ファイル・列 | 単位 | 翻訳の規則 | 止める（既存） | 止める（道具） | 印・確かめる影響 |
|---|---|---|---|---|---|---|---|
| 販促の需要増（対象市場・実施週） | 市場・開始週・終了週・増える量の仮説 | **H** の換算 → `demand_forecast.csv`：`sku_id, region, week, quantity`（`market_entry_plan.csv` のある案は、変換の初版〔`tools/strategy_convert.py`〕では止める。基準需要の生成 → 販促の差分 → 需要の確定の経路は次の版） | lot／週 | **反応週**（実施の週を反応の遅れの分だけ後ろへ移した週）の基準需要に率を掛けて上乗せ（広告の週の需要ではない）。反動減の仮説があれば反応の区間の後の週から引く。凍結した基準需要 B と増減分 d を分けて案に記録し、D ＝ B ＋ d を案の需要にする（型 `promo_demand_delta`） | 需要の CSV のローダ | 仮説の量が書かれていない、対象の `region` が木に無い、上乗せで需要が負になる | **H** → W：追加需要・欠品 |
| 販促費（売上に比例） | 売上に対する率 | `ppc_node_cost_rule.csv`：`cost_type=marketing_cost`、`basis=revenue`、`rate`（leaf_out の行）。Value Chain は `vc_sales_cost_rule.csv`：`cost_item=digital_ad` など、`ppc_cost_type=marketing_cost`、`basis=revenue` | 比 | PPC と Value Chain の両方に同じ率を置く | Value Chain：知らない費目、`basis` が revenue 以外 | 二つの率が食い違う | W：販促費を含めた利益 |
| 販促費（物量 1 単位当たりの定額） | 物量 1 単位当たりの額 | `ppc_node_cost_rule.csv`：`marketing_cost`、`basis=qty`、`rate`／`fixed_amount` | 金額／物量単位（lot × `cpu_size` の 1 単位。Start Here R7） | — | — | Value Chain 側に置き場所が無い（`basis` は revenue だけ） | W（PPC だけ） |
| 販促費（期間を決めた予算、総額） | 期間・総額 | — | — | **×** `ppc_node_cost_rule.csv` には週の列が無く、費用は lot ごとに付く。総額の予算や実施週だけの費用は表せない | — | 止める（「今は表せない」と出す）。代わりに、率 × 想定売上に直すか、案の外の固定費として記録する | **×** |
| 施策のメモ | 狙い・根拠 | `market_entry_plan.csv`：`promotion_note`、`basis_note` | 文字 | 計算には使わない（案の hash からも外れる） | — | — | 記録 |

## 2. 外側の仮説（H）の扱い

- WOM のエンジンは「与えた需要と能力で計画する」決定論の計算。価格 → 需要、販促 → 需要の反応は計算しない。
- 道具は、仮説を**式と係数として案に記録**し、換算した結果だけを W の設定に書く。
  - 例：「SG_EC、2027-W20〜W27、需要 +20%、反動 −5% を 4 週」。
- 換算の結果を比べられるように、元の需要（換算の前）と上乗せ分を分けて残す。比べる画面で「施策の効果」と「仮説の置き方」を分けて読めるようにするため。
- 前例：`oil-global-2027` の OPEC+ のシナリオ（`gen_oil_model_opec_patch.py`）。価格の段差と、遅れて来る需要減を、外側のスクリプトで CSV に書いた。

## 3. 今は表せないもの（作るかは別に決める）

| 項目 | 今の状態 | 選べる道 |
|---|---|---|
| 期間を決めた販促予算（総額） | 費用は lot ごとで、週の列が無い | ① 率に直す ② 案の外の固定費として記録する ③ 週別の費用の規則を新しく作る（PPC の変更） |
| 価格弾力性 | エンジンに無い | 外側の換算（§2）。エンジンに入れる案は採らない（WOM の設計の方針） |
| 工場の割り当ての優先（`priority`） | 列はあるが使われていない | 数量配分か `overflow_policy` で表す |
| 1 週未満の在庫・LT | 週の粒度 | 表せない（週の粒度の境界）。1 週に切り上げて計上する |

## 4. 翻訳の道具に向けた覚え書き（依頼書の材料）

1. 入力は「4P 施策シート」。1 行 ＝ 施策 × 対象（製品・市場・区間）× 期間 × 数値 × 仮説の式。
2. 出力は、コックピットの案（`cockpit_cases copy` で写したモデル）の CSV への書き込みと、何をどの列に書いたかの記録（変更前と変更後の値）。
3. **止める**：§1 の「止める（道具）」の列と、**×** の行。黙って既定値にしない、捨てない。
4. 書いたあと、同じ案で headless を一度回し、既存の止める条件（ローダ）にも通ることを確かめる。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-11-20 | 初版（Code君） |
| v0.1b | 2026-11-22 | Promotion の需要増の行を、変換の初版（型 `promo_demand_delta`）に合わせた：上乗せは反応週、投入の表のある案は止める（Code君の報告 §6 の食い違い） |
| v0.1a | 2026-11-21 | 単価の単位を「金額／lot」から「金額／物量単位」に直した（Claude君、GPT君のレビュー）。確かめていない 2 か所は「要確認」 |
| v0.1c | 2026-11-25 | Product の投入週の行に、変換の型（`product_launch_week`・`launch_one_time_cost`・`launch_weekly_cost`、型カタログ v0.2）と道具の止める条件を書き足した（RequestLetter_Launch_Convert_Slice1、Code君）。販促の型は、投入の表のある案では今も止める |
