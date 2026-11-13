# smartxの運賃3組｜業務調査 v0.1

2026-11-13 ・ GPT-MC ・ 原本読取と判定案

`smartx-2027-2029` のPPCで、工場からDCに入る区間と到着DCに置かれた費用を調べた。3組とも入力規則を確認した。**同一役務かどうかは資料、実際に計上されたかは実行明細で判定する。** 今回の計上状況は3組とも実行確認待ち。[金額基盤の棚卸し表 v0.1 #1][inventory] ・ [Start Here R8・R12][start]

## 1. 3組の役務と判定案

金額はすべて入力の `fixed_amount`（USD）。ノード・区間とも `cost_type=logistics_cost`、`basis=per_lot`、`rate=0`。区間側に個別の役務備考はない。区間は組立工場から最初のDCまでで、経緯資料では国際輸送費として移された。[ノード費用CSV L8–12][node] ・ [区間費用CSV L10–14][edge] ・ [SKU分割と区間の移行記録][migration]

| SKU・到着ノード | ノード側の金額と備考 | 区間側の金額と経路 | 役務の判定案・確定に必要な資料 |
| --- | --- | --- | --- |
| `SmartXPro_IN`・`DC_AMER` | **10.0 USD**。中国→米州の海上運賃＋港湾取扱。 | **17.0 USD**。`AssemblyIN->DC_AMER`、インド・プネからロサンゼルスDC。 | **判定保留**。SKU分割時に中国発の備考が引き継がれた。インド発の運賃へ読み替える意図か、別の輸送・港湾取扱を含むのかを、当時の積算根拠と出発地・対象役務を特定できる内訳で確認する。 |
| `SmartXPro_CN`・`DC_APAC` | **8.0 USD**。中国→シンガポールの海上運賃。 | **14.3 USD**。`AssemblyCN->DC_APAC`、中国・鄭州からシンガポールDC。 | **一部重複の可能性**。同じ方向の運賃で、同一輸送を優先して照合する組。区間側の輸送手段、出発・到着地点、海上運賃と集配費の範囲を確認すれば、全部・一部・別役務を判断できる。 |
| `SmartXPro_CN`・`DC_EMEA` | **12.0 USD**。中国→欧州の航空／海上運賃＋通関関連費用。 | **19.7 USD**。`AssemblyCN->DC_EMEA`、中国・鄭州からアムステルダムDC。 | **一部重複の可能性**。輸送部分が重なる候補。12.0 USDの輸送・通関の内訳、通関の役務か税額か、区間側が含む役務と請求範囲を確認する。 |

3組とも契約上の負担者・支払者は未確認。ノードはPPCの費用の帰属先として読める。港湾取扱、通関手数料、関税、DC内の作業は、運賃と別の費目になり得る。請求番号・明細、輸送区間、役務、負担者、運賃への包含を突き合わせて、同一または別の役務を判定する。関税の入力には別の規則がある。ノード備考の `customs` の実体は内訳で確かめる。[smartx README「別のライン」][readme] ・ [拠点と経路][tree] ・ [地域別の起終点][route] ・ [関税のモデル入力][tariffinput]

### 生成・変更履歴から分かったこと

- `55ae30c` の差分では、ノード3行を `SmartXPro` からCN系・IN系へ付け替え、金額の桁を調整した。AMERの `CN→AMER` を含め、各ノード行の役務備考は引き継がれた。移行スクリプトもノード名からSKUを割り当てる処理になっている。[SKU分割の差分 `55ae30c`][splitcommit] ・ [ノード規則の移行][splitnode]
- 区間側は、旧サプライポイント経由の規則を工場→DCの国際輸送とDC→販売先の区間に移す過程で生成された。費用の桁補正では、`basis=per_lot` の表記を持つ行を含め、1個当たりの金額水準に換算したと記録されている。金額のスケール調整と経路の付け替えは追える。役務を照合できる請求・積算内訳は未確認。[修正依頼書 Step 4・§12][migration] ・ [区間移行の処理][splitedge] ・ [金額補正の根拠][scale]

## 2. Code君が確かめる代表ロットの明細

指定版の同じsmartxサンプルで現行PPCを実行し、入力・期間・プラグイン・実行の識別情報を記録する。goldenの設定に合わせる場合、READMEではCapacity LayerはOFF。出力の `ppc_event_ledger.csv` から次の3組を照合する。[smartx README「上位の層」][readme] ・ [PPC出力][export]

| 代表として追う実ロット | ノード側の抽出キー | 区間側の抽出キー |
| --- | --- | --- |
| `SmartXPro_IN`・`Retail_AMER` 向け1ロット | `DC_AMER`、`edge_id` 空欄、`ppc_node_cost_rule.csv` | `DC_AMER`、`AssemblyIN->DC_AMER`、`ppc_edge_cost_rule.csv` |
| `SmartXPro_CN`・`Retail_APAC` 向け1ロット | `DC_APAC`、`edge_id` 空欄、`ppc_node_cost_rule.csv` | `DC_APAC`、`AssemblyCN->DC_APAC`、`ppc_edge_cost_rule.csv` |
| `SmartXPro_CN`・`Retail_EMEA` 向け1ロット | `DC_EMEA`、`edge_id` 空欄、`ppc_node_cost_rule.csv` | `DC_EMEA`、`AssemblyCN->DC_EMEA`、`ppc_edge_cost_rule.csv` |

1. **実ロットとPPCのIDを対応させる。** SKU・販売先ごとに実出荷記録から代表のWOM `Lot_ID` を1件選び、工場→DCの区間、DC受入・販売先出荷の週を追う。現行PPCの `lot_id` は `PSI-<SKU>-<販売先>-<週>` で、販売先の実出荷を週単位でまとめる。可能なら実出荷1ロットだけの週を選ぶ。同じPPC行に複数ロットが含まれる場合は、対象 `Lot_ID` の属する実出荷集合と集約行を照合し、集約金額の対象数量を明示する。[PSIからPPCへの変換 L164–198][bridge]
2. **元規則ごとに明細を照合する。** `product_id`、PPC `lot_id`、`week`、`node_id`、`edge_id`、`source_rule`、`ppc_event_type=logistics_cost`、`direction=forward` で抽出する。`event_id`、`qty`、`amount_local`、`currency`、`fx_rate`、`amount_base` を記録する。PPCの計上週と元の出荷・受入の週は併記する。明細の区分には `source_rule` と `edge_id` を使う。ソース上、区間とDCにそれぞれの費用明細を生成する経路がある。[費用生成 L129–142・L181–216・L250–274][ppctariff] ・ [出力項目][exportcols]
3. **費用額と行数を確かめる。** 明細の `amount_local` と `amount_base` は1物量単位当たり。正の `qty` を照合し、明細総額をそれぞれ `単価 × qty` で求める。`amount_base` は換算済み単価なので、換算は1回。たとえば `qty=1`、USD→USD 1.0、両規則が当たる場合は、各明細が上表の入力額と個別に一致することを確認する。`landed_cost_total` などの集約行は明細額の照合に使い、原価の再加算は0件とする。[PPC金額・数量の定義][models] ・ [PPC集計の費目・数量倍率][kpi] ・ [モデルの為替入力][fx]

**出力の判定**。各組で、同じ集約IDと計上週に該当の費用明細が両方出る、片方だけ出る、両方0件のいずれかを記録する。該当なしは、実出荷の有無、実際に引いた規則、評価状態を調べる。R12では費用規則に該当行が無いと費用なしとして処理され、欠落は件数で残る。明示0と判定保留を記録上区別する。両方が計上され、さらに役務の重なりと金額を証憑で追えた場合に、重複分を特定できる。[Start Here R12][start] ・ [D8報告書 §6.1][d8]

## 3. 3組の期間集計と引き継ぎ

- **共通期間・通貨**。実需要のある入力の範囲は2026-W01〜2030-W52で、入力には2025-W36からの助走も含まれる。期間集計は同じ実行の評価対象週を明記し、両側に同じ週フィルタを適用する。推奨集計は2026-W01〜2030-W52のUSD。実際の基準通貨・評価状態・換算の注記は `ppc_kpi_summary.json` と明細で確認する。[週別需要CSV][demand] ・ [モデルの為替入力][fx]
- **集計単位**。3組ごとに、ノード側・区間側それぞれの `event_id` 件数、正額件数、`qty`、`Σ(amount_base × qty)` を出す。同一PPC `lot_id`・週で両側がそろう組数も併記する。実ロット数とPPCの集約行数は明記する。集計結果は `ppc_node_week_summary.csv` の該当費用の内数として照合する。同じ明細の再集計、関税・保険、別区間の費用、計算済みの総額の加算を避ける。[PPC出力][export] ・ [PPC集計][kpi]
- **設計への受け渡し**。Claude君に、3組の判定案と未確定の役務・負担者、上の実行で確認する項目を渡す。Code君の出力を受け、運賃と港湾取扱・通関等の内訳に基づき、物理区間の運賃と拠点の役務を分ける範囲を大杉さんが判断する。金額未確定の段階ではノード側の全額削除は保留。[金額基盤の棚卸し表 #1][inventory]

## 読取・確認の範囲

参照版は `wom-v1r6m0_BS-SEAF` の `78d29987388e79101a71b10ec8e1fca35b4b68bb`。依頼書 v0.1 §§1・3・4、Start Here §3、棚卸し表 #1、指定版のsmartx README、費用と経路のCSV、移行資料とPPCの処理を読んだ。過去の変更経緯は `55ae30c` の原本差分で確認した。3組の現行PPCの再実行・出力再集計、運送・港湾・通関の原票は未確認。計上件数・合計・重複額は実行および役務照合の結果待ち。[指定版][revision]

[revision]: https://github.com/Yasushi-Osugi/wom_development_composite_node/tree/78d29987388e79101a71b10ec8e1fca35b4b68bb
[start]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/docs/WOM_Start_Here.md#L88-L92
[inventory]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/requests/WOM_MoneyBase_Inventory_v0.1.md#L37-L44
[readme]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/data/sample/smartx-2027-2029/README.md#L36-L50
[node]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/data/sample/smartx-2027-2029/ppc_node_cost_rule.csv#L8-L12
[edge]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/data/sample/smartx-2027-2029/ppc_edge_cost_rule.csv#L10-L14
[tree]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/data/sample/smartx-2027-2029/sc_tree_master.csv#L24-L35
[route]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/data/sample/smartx-2027-2029/route_master.csv#L2-L4
[tariffinput]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/data/sample/smartx-2027-2029/ppc_tariff_rule.csv#L10-L15
[demand]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/data/sample/smartx-2027-2029/demand_forecast.csv
[fx]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/data/sample/smartx-2027-2029/ppc_fx_rate.csv
[migration]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/requests/smartx-2027-2029-fix-request-letter.md#L252-L318
[splitcommit]: https://github.com/Yasushi-Osugi/wom_development_composite_node/commit/55ae30c9db97873b5dd91bc70d8837b588a34100
[splitnode]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/tools/split_smartx_sku.py#L125-L143
[splitedge]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/tools/split_smartx_sku.py#L227-L304
[scale]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/tools/fix_smartx_price_scale.py#L8-L32
[bridge]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/wom/ppc/ppc_psi_bridge.py#L164-L198
[ppctariff]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/wom/ppc/ppc_tariff.py#L129-L274
[export]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/wom/ppc/ppc_export.py#L90-L108
[exportcols]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/wom/ppc/ppc_export.py#L143-L167
[models]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/wom/ppc/ppc_models.py#L60-L95
[kpi]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/wom/ppc/ppc_kpi.py#L23-L80
[d8]: https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/78d29987388e79101a71b10ec8e1fca35b4b68bb/docs/development/WOM_PPC_NoSilentFallback_Report.md#L167-L191
