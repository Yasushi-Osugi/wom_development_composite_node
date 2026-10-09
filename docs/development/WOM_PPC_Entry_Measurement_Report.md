# WOM PPC入口 実測報告書

- 作成日：2026-09-28（JST）
- 依頼：requests/RequestLetter_PPCEntry_Measurement_to_Astra.md
- Repository：Yasushi-Osugi/wom_development_composite_node
- 対象branch：wom-v1r5m1_cap_trial
- 測定基準：e74793699834483c9c7cad8337b4b0d464517e01
- 依頼書収録コミット：5344816（測定コードへ混在させていない）
- 種別：Headlessによる観測・入力差替え測定のみ。core/原本CSV/goldenの変更、commit/push/PRなし。

## 最優先の結果：P1とP3

### P1：fallback・除外があったモデル

| 調査範囲 | fallbackあり | 除外あり |
|---|---:|---:|
| 13 golden＋alloc原需要/P_opt800＋ev-thailand更新版＝16条件 | 0 | 0 |

**該当モデルなし。** 全条件でpsi_mode=True、bridge生成行を全件採用。GUI/cockpitは測定せず、既存Headless runnerの呼出経路を測定した。

**別のP1検出事項：riceの合成ID衝突。** rice-japan-2027-2028は1,240行、310種類の合成IDが各4回。Koshihikari/Yumepirikaの各4地域（KANTO/TOHOKU/KANSAI/KYUSHU）がJP_Channelへ写像される。行や数量は除外されていないが、合成IDを一意キーとして地域を追跡することはできない。他15条件で衝突は0。途中コメントの「全条件で衝突0」は誤りであり、本結果へ訂正する。衝突の下流金額への影響は本依頼のrice対象範囲（P1のみ）を越えるため測定していない。

### P3：市場leafの実出荷への差替え結果

| 対象 | leaf予定S / 実出荷（lot） | existing売上（円） | supplied売上（円） | existing粗利（円） | supplied粗利（円） | 売上/粗利差 |
|---|---:|---:|---:|---:|---:|---:|
| soysauce-jpy-2027-alloc__P_opt800 | 83,200 / 83,200 | 548,550,508.00 | 548,550,508.00 | 165,007,343.1925 | 165,007,343.1925 | 0 / 0 |
| Cookie-jp-2026 | 141,990 / 141,990 | 4,259,700,000.00 | 4,259,700,000.00 | 686,229,000.0000 | 686,229,000.0000 | 0 / 0 |

**主結果：入口をleaf_outの_actual_sへ替えても、今回の2条件では金額は変わらない。** 全体だけでなく、product×channel、週、product×channel×週の全比較で数量・売上・原価・粗利の差は0。leafのSと_actual_sは各週のID多重集合まで一致した。

これは「上流からの供給が全数成立した」という結論ではない。実行時に、Outbound decoupleの下流はDemand PからSupply Pを再作成していた。市場leafの_actual_sはその供給状態に基づいて算定される。

## 1. 実行条件と検証範囲

- 独立Linuxコピーを固定SHAへdetached checkout。git fsckと全追跡ファイルのGit blob照合に異常なし。
- Python 3.12.14、pandas 2.2.3、numpy 2.3.5、pytest 9.1.1、networkx 3.7、matplotlib 3.10.8、openpyxl 3.1.5。独立venv（既存依存を参照）を使用。
- モデルをTemporaryDirectoryへ複写し、warmupと配分需要の生成は複写上だけで実行。原本データは保持。
- 原需要はdemand_forecast.csv。P_opt/800は既存の_scenario_blocks(s1_base)、true_continuous_optimum(cap_wk=800)、write_demand_for_allocationで生成。800は配分条件であり、観測器が設備CSVを一括800に書換えたものではない。生成需要と配分結果を同梱。
- golden13条件は各goldenのconfig.plugins。alloc2条件とEV更新版はsafe（HolidayCalendar/BufferingStockOptimizer/CapacityOverride）。rice BKは本依頼対象にないため含めない。
- 既存テスト：473 passed / 2 failed / 1 skipped（計476）。2失敗はtest_t14_capacity_view_cells_and_headless_series、test_t17_gui_load_orderのTkAgg/headless環境エラー。GUI群はモジュール単位skip。Windowsの544 passed /3 skippedと母集団が異なる。GUIの合格認定はしていない。
- golden単独：13 passed。加えて観測器を有効にした全13条件でperiod/products/config/forward/backward/ppc/psiがgoldenと一致。観測非干渉の根拠とする。
- 生データを別処理で再集計し、入口リンクの件数、leaf多重集合、全金額比較軸、明細→KPIの一致を確認。結果はindependent_output_checks.json。
- 初回プローブはGENERICのtuple辞書キーのJSON保存で停止したため、保存処理を直し、最終スクリプトで16条件を最初から再実行した。本添付のdataはエラーなしの最終実行のみ。

## 2. P1 全条件の入口表

下表の採用行数・数量はbridge行数・数量と同じ。全条件cpu_size=1なのでlotとunitの数値は一致するが、単位を同一概念としない。全行で除外0、fallback=False。各JSON/CSVに採用/除外の行数・lot/unit・対応先・重複件数を保存。

| 条件 | 実行分岐 | bridge=採用 行数 | bridge=採用 lot | unit | 衝突行数 |
|---|---|---:|---:|---:|---:|
| Cookie-jp-2026 | cookie | 624 | 141,990 | 141,990 | 0 |
| apparel-global-2028-2029 | GENERIC_tree | 394 | 181,526 | 181,526 | 0 |
| apparel-us-2026 | GENERIC_tree | 312 | 249,172 | 249,172 | 0 |
| bom-test-2026 | GENERIC_tree | 20 | 100 | 100 | 0 |
| ev-europe-2026 | GENERIC_tree | 526 | 53,140 | 53,140 | 0 |
| ev-thailand-2026 | GENERIC_tree | 624 | 63,240 | 63,240 | 0 |
| smartphone-global-2026-2029 | smartphone-global-2026-2029 | 1170 | 470,924 | 470,924 | 0 |
| oil-global-2027 | GENERIC_tree | 1408 | 191,058 | 191,058 | 0 |
| rice-japan-2027-2028 | rice | 1240 | 235,316 | 235,316 | 1240 |
| smartx-2027-2029 | GENERIC_tree | 1716 | 709,811 | 709,811 | 0 |
| soysauce-eu-2027 | GENERIC_tree | 624 | 100,501 | 100,501 | 0 |
| soysauce-jpy-2027 | GENERIC_tree | 624 | 100,501 | 100,501 | 0 |
| soysauce-us-2027 | GENERIC_tree | 312 | 100,500 | 100,500 | 0 |
| soysauce-jpy-2027-alloc | GENERIC_tree | 624 | 100,501 | 100,501 | 0 |
| soysauce-jpy-2027-alloc__P_opt800 | GENERIC_tree | 624 | 83,200 | 83,200 | 0 |
| ev-thailand-2026_update | GENERIC_tree | 624 | 63,240 | 63,240 | 0 |

runnerのdetect_scenarioが返すラベルsmartphoneと、実際に選ばれたGENERIC_tree分岐は区別した。CaptureEngine生成時のrunnerローカル変数を読んで分岐を記録している。全モデルを「smartphoneシナリオ」とは解釈しない。

riceの一対多写像はchannel_mapping.json、合成IDの4重出現はbridge.csvに保存。数量は235,316 unitを全件採用。P1で除外がないことは、上流供給のE2E成立や、合成ID追跡の完全性を保証しない。

## 3. P2 予定Sと実出荷

ForwardPlanner.run終了直後に_actual_sをnode別・週別に複写し、bridge呼出時に元のSupply Sを直接採取した。合成IDの文字列から元IDを推定していない。

| 対象 | leaf S | leaf actual | 週別多重集合差 | 早出し | 後週出荷 | 期間内未出荷 | leaf期首在庫 |
|---|---:|---:|---:|---:|---:|---:|---:|
| alloc P_opt800 | 83,200 | 83,200 | 全週0 | 0 | 0 | 0 | 0 |
| Cookie | 141,990 | 141,990 | 全週0 | 0 | 0 | 0 | 0 |

主対象のleafは全週でCOも0。ここでの要求週はPPCが読むleafのSupply S位置である。上流nodeの要求・移動の遅延分類までこの表から推定しない。

- ppc_entry_records.jsonl：集約行、元node、product、channel、週、予定S数、cpu_size、採否。
- ppc_entry_links.jsonl：元Lot_ID、多重度、元PSI位置から集約行への観測対応。
- leaf_weekly.csv：全leaf×全週のS/actual/CO/多重集合差。S=0の週も含む。
- leaf_id_timing.jsonl：全要求出現の週対応。leaf_id_differences.jsonlは差0のため空。

## 4. P3 金額比較とTrial-02の再現

### 4.1 比較方法

既存runnerが解決した経路、価格・原価・為替rules、通貨、BOM設定を捕捉。同じPPCSimulationEngineへ、leaf実出荷件数×cpu_sizeで組み立てたsales_recordsだけを差し替えた。既知product/channelの同じフィルタを適用し、空データからサンプルを生成する処理はこの比較へ持ち込んでいない。今回、差替え入力は非空かつ全件適合。

PPC accumulatorの単位額×qtyを再集計しKPIと一致を確認。qtyはunit、PPCのtotal_lotsは集約レコード数（両モデル624）であり物理Lot数とは違う。

### 4.2 差の分類

- 数量・時点：leafで予定と実出荷がID・週とも同じなので、期間内未出荷による差0、早出し/遅配の時点差0。
- 集約・ID追跡：両比較で同じ集約方式。今回観測側で元IDとの対応を保存できた。ID喪失に起因する金額差を測ったわけではなく、入口差替えによる差は0。
- その他：価格・原価・為替・経路を固定。fallback/除外は0、残差0。

このsuppliedは「現行シミュレーションのleaf actualに基づく額」であって、全上流nodeの供給成立を独立に保証した額ではない。

### 4.3 soysauce：9,293 IDと対応額

| 観測 | 結果 |
|---|---:|
| Bottling実出荷に一度も現れず、leaf Sに存在するID | 9,293 |
| そのうちleaf actualに存在するID | 9,293（全件） |
| その集約所属と単位額から導出した売上 | 73,461,824.00円 |
| 同じ方法で導出した粗利 | 24,625,145.04円 |
| leaf actualへ差替えたPPC粗利差 | 0円 |

Trial-02の数量・対応額は再現。粗利は浮動小数の最終桁差のみ（未丸め24,625,145.03999815）。対応額は観測した元ID→集約行の所属と、その行の単位額から導出したもの。PPCが元ID単位の台帳を持つという意味ではない。

Bottling/ SP_Soy / FG_WH_Nodaの実出荷は各73,907。一方、FG_WH_Nodaの下流4DCはpull_mode=Trueとなり、Supply PをDemand Pから作り、計83,200を実出荷する。親FG_WH_Nodaの全期間実出荷にない受入IDはUS_SF 350、US_NY 350、JP 256、EU_RTM 8,337、計9,293。期首在庫による説明ではなく、実行時のP上書きと一致した。

### 4.4 Cookie：減少の伝播境界

| node/集計 | 現基準の実出荷lot | 観測された供給入力 |
|---|---:|---|
| Factory_GP_CN | 67,274 | 現行計画・供給処理 |
| SP_Cookie_Import | 67,274 | 工場のactualを受ける |
| DC_Import_Buffer | 67,274 | SPからのactualを受ける |
| DC_Import_Main | 78,142 | pull_mode=True、Demand PをSupply Pへコピー |
| Import側3市場合計 | 78,930 | 下流PULL。各leaf S=actual |
| Local側市場合計 | 63,060 | 下流PULL。各leaf S=actual |

DC_Import_Mainは処理直前P総数0、処理後P総数78,142で、全週でDemand Pと一致。親DC_Import_Bufferの全期間actualにない受入IDが10,868存在する。この10,868は現基準の差であり、今回の変更による1,450と同一ではない。

SE1報告の変更前68,724→変更後67,274（−1,450）のうち、変更後値は今回再現。変更前コードを再実行して1,450の前後ID集合を取り直すことはしていない（基準固定の依頼範囲）。現基準の直接観測から、上流不足を受ける範囲はDC_Import_Bufferまで、以降のPULLで要求に基づく供給へ切り替わることを確認した。したがってleaf実出荷への入力変更だけでは、この不足をPPCへ伝えられない。

## 5. P4 中間node金額の数量起点

PPCイベントの合成IDを、実際に採用された販売入力accumulatorへ対応させ、各event.qtyがそのaccumulator.qtyと一致することを全イベントで確認した。コードのacc.qty使用とも照合。複数費用イベントのqtyを重ねて「供給数量」として合計せず、nodeに関係する販売レコードを一意に数えた。

PPCイベントのある中間nodeは、今回すべて「leaf_out販売数量から導出」。自node actualを直接読んで数量化するものは確認されなかった。経路選択はallocでGENERICの祖先列、Cookieで専用経路であり、CookieまでGENERIC ancestryと呼ばない。

| モデル | node | 自node actual unit | PPCが基礎とする販売unit | PPC費用（円） | 分類 |
|---|---|---:|---:|---:|---|
| alloc | SP_Soy | 73,907 | 0 | 対象イベントなし | その他：該当PPCイベントなし |
| alloc | FG_WH_Noda | 73,907 | 83,200 | 12,068,000.00 | 販売数量由来 |
| alloc | DC_US_SF | 17,588 | 17,588 | 19,404,472.50 | 販売数量由来 |
| alloc | DC_US_NY | 17,588 | 17,588 | 20,944,510.00 | 販売数量由来 |
| alloc | DC_JP | 12,849 | 12,849 | 4,177,250.00 | 販売数量由来 |
| alloc | DC_EU_RTM | 35,175 | 35,175 | 51,263,103.90 | 販売数量由来 |
| alloc | Bottling_Noda | 73,907 | 83,200 | 68,228,000.00 | 販売数量由来 |
| alloc | Brewing_Noda | 73,907 | 83,200 | 66,771,000.00 | 販売数量由来 |
| alloc | Materials_JP | 73,907 | 83,200 | 94,953,400.00 | 販売数量由来 |
| Cookie | SP_Cookie_Import | 67,274 | 0 | 対象イベントなし | その他：該当PPCイベントなし |
| Cookie | DC_Import_Buffer | 67,274 | 78,930 | 410,436,000.00 | 販売数量由来 |
| Cookie | DC_Import_Main | 78,142 | 78,930 | 315,720,000.00 | 販売数量由来 |
| Cookie | Factory_GP_CN | 67,274 | 78,930 | 670,905,000.00 | 販売数量由来 |
| Cookie | Ingredients_CN | 67,274 | 78,930 | 631,440,000.00 | 販売数量由来 |
| Cookie | SP_Cookie_Local | 60,544 | 0 | 対象イベントなし | その他：該当PPCイベントなし |
| Cookie | DC_Local_JP | 60,544 | 63,060 | 271,158,000.00 | 販売数量由来 |
| Cookie | Factory_DP_JP | 60,544 | 63,060 | 580,152,000.00 | 販売数量由来 |
| Cookie | Ingredients_JP | 60,544 | 63,060 | 693,660,000.00 | 販売数量由来 |

これらの中間nodeにmarket_revenueイベントはなく、node P&Lの売上欄は0。mom_profit等の情報・Profit Zoneイベントは別に存在し、売上イベントと混同しない。Supply Point等でイベントがないことを、実業務の売上・費用がゼロと認定しない。nodeごとの取引価格が未設定の箇所について、新たな全node売上を計算・補完していない。

ppc_node_basis.csvには各nodeの実出荷、元販売数量、イベント種別、費用、数量不一致数（全件0）、根拠を記録。これは大杉さんの「全node各自の出荷Lot×Lot単価」が、そのまま現行PPCに実装されているという状態とは異なる。

## 6. 観測・原因解釈・業務判断の区別

### 観測で確認できたこと

1. 対象16条件はfallback/除外なし。riceに合成ID衝突あり。
2. 主対象のleaf Sとactualは全ID・全週一致。差替えPPCの金額差は全軸0。
3. 9,293 IDと対応額は再現し、同じIDが下流leafのactualにも存在する。
4. Outbound PULLでDemand PをSupply Pへ上書きし、上流actualの不足を引き継がない境界がある。
5. 中間node PPCのquantityは当該nodeのactualではなく、販売集約レコードの数量から導出される。

### 原因解釈と留保

「PPCが予定Sを読むから、actualへ差し替えれば上流不足が金額へ届く」という仮説は、この2条件では支持されない。現行のleaf actualそのものが下流PULLの供給状態に基づくためである。これは現行処理を観測した結果で、PULLを不正な機能と断定したものではない。

「17ケースのPPCが不変だった」だけでは原因は確定できない。供給量が変わらずタイミング/在庫のみ変わる場合、原価規則に保有期間費がなければ不変となり得る。今回の限定測定を全ケースの原因説明へ拡張しない。

### 大杉さんの判断が必要なこと

- 下流PULLによる供給成立を、計画上の充足とE2E供給成立のどちらとして経営評価へ提示するか。
- 各nodeの金額を、自nodeの出荷取引として示す部分と、市場販売数量から導出した原価・利益配分として示す部分の業務上の区別。
- 上流未通過IDに対応する金額を、どの前提付きの指標として読むか。今回の24,625,145.04円を、そのまま損失額・PPC差替え差額とは扱えない。

本報告は判断材料であり、PPC修正案、Request Letter草案、golden更新の提案を含めない。

## 7. 成果物と再実行

- tools/probe_ppc_entry.py：基準SHAと追跡差分を検査し、P1全条件→主対象のP2/P3/P4を実行。新しい空の出力先が必要。
- data/p1_all_cases.csv：P1全数表。各case/p1.jsonに複雑な一覧も保存。
- 主対象各case/ppc_entry_records.jsonl、ppc_entry_links.jsonl、ppc_node_basis.csv、ppc_basis_differences.csv：LOVEM段階Dの接続資料。
- node_observations.json：全nodeのP/S/actual ID、週、I/CO件数、下流PULL入口の状態。Iの全IDリストは本依頼では採取しない。
- outbound_boundaries.csv、boundary_ids_*.jsonl：下流切替位置とID差。
- existing_ppc/suppliedのイベント、accumulator、KPI：同一規則での比較根拠。
- trial02_missing_bottling_ids.jsonl：9,293 ID全件と市場actualへの所属・按分額。
- qualification/：環境テスト結果。GUI失敗を成功に書き替えていない。

```sh
python tools/probe_ppc_entry.py --repo <e747936の独立checkout> --out <新しい空ディレクトリ>
```

Windowsでも同じ基準SHAと依存を用い、実測環境の違いを記録する。既存goldenやモデル原本へ出力しない。--casesで対象を限定できるが、その結果を全16条件完了と呼ばない。

## 8. 限界と終了

GUI/cockpitの実行、riceのID衝突による下流金額影響、Cookieの変更前ID集合の再測定、全nodeの新しい取引価格による売上計算は未実施。P1〜P4の指定Headless測定と根拠の受け渡しで本作業を終了し、追加調査・修正を自動で始めない。

## 付録：同梱ファイルSHA-256

以下はZIP内の報告書以外の全ファイルのSHA-256。自己参照を避けるため本報告書自身とZIP自身のハッシュは含めない。パスはZIPのルートからの相対パス。data/sha256.jsonは観測終了時のデータハッシュであり、その後追加した検証資料を含む最終一覧は以下を用いる。

| ファイル | SHA-256 |
|---|---|
| `data/Cookie-jp-2026/backward.json` | `9ea8ee74e3c5ac29333be0e48e23080d96f5455685cb935d23e05f57284cfdc3` |
| `data/Cookie-jp-2026/boundary_ids_OUT_dad_DC_Import_Main_Cookie_Import.jsonl` | `91cc9202b59f1330ea1fb5496427652f1d702419cbe6a668e755d79a0a7d1fe5` |
| `data/Cookie-jp-2026/boundary_ids_OUT_leaf_out_CVS_Cookie_Import.jsonl` | `cf8e0159da357ebae7929cf803cd8a0a8ed4722b3a0f6e129a32d69b2729e5ec` |
| `data/Cookie-jp-2026/boundary_ids_OUT_leaf_out_CVS_Cookie_Local.jsonl` | `67512bda71f3273280d35c34c10adbf7f0c8451ed6e90d65b232d1b529a9bd16` |
| `data/Cookie-jp-2026/boundary_ids_OUT_leaf_out_EC_Cookie_Import.jsonl` | `095425898c9f85febdd34f3b7158d6b168f791f0f993721370bc9285842fc96b` |
| `data/Cookie-jp-2026/boundary_ids_OUT_leaf_out_EC_Cookie_Local.jsonl` | `5b7b9a51b417c342a2b1f3f831905a8e92933d44017868e1b7c074e2dec45ff9` |
| `data/Cookie-jp-2026/boundary_ids_OUT_leaf_out_SM_Cookie_Import.jsonl` | `ee4c3b96f1733db6a2683245115ba0673e13f29c6001603f36293f3c767f57c4` |
| `data/Cookie-jp-2026/boundary_ids_OUT_leaf_out_SM_Cookie_Local.jsonl` | `e0a7c08bd0412f963daf007208afaa4e7f772a9cf9352851ebfaaf2d43a67f67` |
| `data/Cookie-jp-2026/bridge.csv` | `36e7dba2df057c999dfb5e7b641fb3d9c39c725e80a7fe0d4e4cbc401694b3c9` |
| `data/Cookie-jp-2026/channel_mapping.json` | `05ea6e3c328bdee62cdc1fc77702657127a3ee229c3ac5d8fb1effcf4811b697` |
| `data/Cookie-jp-2026/engine_input.csv` | `36e7dba2df057c999dfb5e7b641fb3d9c39c725e80a7fe0d4e4cbc401694b3c9` |
| `data/Cookie-jp-2026/engine_parameters.json` | `3e19d7465ea2cd8d9f9f80bf7d9da5138c4cac584ee20659f6bf892b634e63aa` |
| `data/Cookie-jp-2026/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/Cookie-jp-2026/existing_ppc/ppc_event_ledger.csv` | `59c672695be8dd67159a76336ca83bdfe1ffb1cf3b92b25ddda3f74d91e7bf98` |
| `data/Cookie-jp-2026/existing_ppc/ppc_kpi_summary.json` | `e66410182e0ebb7b53bd700f3f1239db9acc0a13f6add4591afcbdb8a429dce5` |
| `data/Cookie-jp-2026/existing_ppc/ppc_lot_reconciliation.csv` | `97590b068380e9dd600b9fdbc85f842bc4ba5dc2f272e38de8043635b0f0745a` |
| `data/Cookie-jp-2026/existing_ppc/ppc_node_pl_summary.csv` | `a1c19276e543cfba7115090ea2e55290005b0924486fdc01ca693e2542ea8faf` |
| `data/Cookie-jp-2026/existing_ppc/ppc_node_week_summary.csv` | `25dd2dbe5503896f09099403809d293f28a2f9f53e49bec3d82d764733f30e6d` |
| `data/Cookie-jp-2026/existing_ppc/ppc_profit_zone_summary.csv` | `ab26db93e3910539f6fda45e17871d8996d01afbf3566e1c36dfced5aaec9950` |
| `data/Cookie-jp-2026/existing_ppc_accumulators.csv` | `959f5f910ccb0704fd6eeb381e6b97b206023b775621b825ace5fd1ef09ef76d` |
| `data/Cookie-jp-2026/existing_ppc_events.jsonl` | `40f0b5d74be05feb4ba612cfae6bd1037b99347b8267dc446a6919a20a50f95b` |
| `data/Cookie-jp-2026/existing_ppc_kpi.json` | `21a98470ad6f147d04b60155025a52e197b7ce3aca79d0b90284005915682ece` |
| `data/Cookie-jp-2026/existing_ppc_node_pl.csv` | `a1c19276e543cfba7115090ea2e55290005b0924486fdc01ca693e2542ea8faf` |
| `data/Cookie-jp-2026/input_hashes_after.json` | `d9d6f9356c50b6f64de45be4db7f49fe01799a88acac28fef395155c838a5860` |
| `data/Cookie-jp-2026/input_hashes_before.json` | `d9d6f9356c50b6f64de45be4db7f49fe01799a88acac28fef395155c838a5860` |
| `data/Cookie-jp-2026/leaf_id_differences.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `data/Cookie-jp-2026/leaf_id_timing.jsonl` | `9fbedb1b7376e30b0e7c2b089d271f8f07c86fc7b30315b8384c7017ac48d05a` |
| `data/Cookie-jp-2026/leaf_id_timing_summary.json` | `00ef01a7b63706110882676bc1c770acc52da500bcf023c256b2e38d532f6207` |
| `data/Cookie-jp-2026/leaf_weekly.csv` | `dea2a1dc190bb779cd022cf5ee84fa3fb76145b1ce1969bc25162f1a9bb138cc` |
| `data/Cookie-jp-2026/main_summary.json` | `75b524b7340812cd0fb695b8b489865ad243d394732bddac3381eac88a9769df` |
| `data/Cookie-jp-2026/node_observations.json` | `aa0d03393e2dafed9e0c01a2affb6beae866cb9fd61e81266650ec843c03f12b` |
| `data/Cookie-jp-2026/outbound_boundaries.csv` | `f46d09364368fa150764517f6e0a19bbd4acd1e734b62e7edba5e3655a024c87` |
| `data/Cookie-jp-2026/p1.json` | `a58d236afb5eebb31645a124e41e1c5104478d48a7c4e666bd73bd206e8a864e` |
| `data/Cookie-jp-2026/ppc_basis_differences.csv` | `c5e7a7378d64bd3b77257612cf51b92d13972ced36fdc9e91673312efda240b1` |
| `data/Cookie-jp-2026/ppc_entry_links.jsonl` | `5f0749442e78b0e097aa75c0cabf518a84d6ef67b0999324b8387aa17b1d5f26` |
| `data/Cookie-jp-2026/ppc_entry_records.jsonl` | `20de821be1efa67c1234076650fc7ef8820d7401a8d933c77be4a2be8268e9d6` |
| `data/Cookie-jp-2026/ppc_node_basis.csv` | `70651a8c8b0fee9d6d0204de31d0d1dfc4143f76d2fc30582902e181e33c2cf8` |
| `data/Cookie-jp-2026/snapshot.json` | `1a41638de46ffd8a9ea48465b47dc7a26d31d00b5d1e7302ec4b4852d6e77989` |
| `data/Cookie-jp-2026/supplied_accumulators.csv` | `959f5f910ccb0704fd6eeb381e6b97b206023b775621b825ace5fd1ef09ef76d` |
| `data/Cookie-jp-2026/supplied_events.jsonl` | `40f0b5d74be05feb4ba612cfae6bd1037b99347b8267dc446a6919a20a50f95b` |
| `data/Cookie-jp-2026/supplied_kpi.json` | `21a98470ad6f147d04b60155025a52e197b7ce3aca79d0b90284005915682ece` |
| `data/Cookie-jp-2026/supplied_node_pl.csv` | `a1c19276e543cfba7115090ea2e55290005b0924486fdc01ca693e2542ea8faf` |
| `data/Cookie-jp-2026/supplied_sales.csv` | `36e7dba2df057c999dfb5e7b641fb3d9c39c725e80a7fe0d4e4cbc401694b3c9` |
| `data/Cookie-jp-2026.log` | `c35ea98ba6827a58f55b9f6ead7ffeffe692a0c7bd86243401f6058d55ddb5f4` |
| `data/apparel-global-2028-2029/backward.json` | `ef4cf96c3d044ac489c0fb9a42ae127f6e0a685c06ab234fc6240ce6b854ae58` |
| `data/apparel-global-2028-2029/bridge.csv` | `749b98ac44b26a6e8a423dba76291b1939f45d27564036fcb6e2a5ce192d40b8` |
| `data/apparel-global-2028-2029/channel_mapping.json` | `48475dad716b75c5bf14f09df79445a5e4a283493a303a77c6111e5e46e89d3c` |
| `data/apparel-global-2028-2029/engine_input.csv` | `749b98ac44b26a6e8a423dba76291b1939f45d27564036fcb6e2a5ce192d40b8` |
| `data/apparel-global-2028-2029/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/apparel-global-2028-2029/existing_ppc/ppc_event_ledger.csv` | `298952b02664dc1a2ccd4f704705c53ecf85fe9fa7660c5735498aefbce18acf` |
| `data/apparel-global-2028-2029/existing_ppc/ppc_kpi_summary.json` | `c98fd306ca844e23513a080d17f2e3d72ad6f855a96c05d3b11dc0224f93ec28` |
| `data/apparel-global-2028-2029/existing_ppc/ppc_lot_reconciliation.csv` | `c4b6591f6ad5abe2b89d8ed2041ef6155cebfda1cf6f8a53eb8faa7ca48c2e8b` |
| `data/apparel-global-2028-2029/existing_ppc/ppc_node_pl_summary.csv` | `8c06a8b762bfb1265314207beae1a112edc7302f00dc776264175b806c67d7b9` |
| `data/apparel-global-2028-2029/existing_ppc/ppc_node_week_summary.csv` | `567cd4e2c9862812f2ff51d57a0d2342bc57d90f5eb5c7d936e156841f7aff42` |
| `data/apparel-global-2028-2029/existing_ppc/ppc_profit_zone_summary.csv` | `2079131f977e02d9ab9d73bcf035a1acba51168b131015f1073f2faa35edbea4` |
| `data/apparel-global-2028-2029/input_hashes_after.json` | `dd98a90d9cfe9a5caaa31a91e80a95d3f4a0db213c1bfd1ec7bff79e2e2a24ab` |
| `data/apparel-global-2028-2029/input_hashes_before.json` | `dd98a90d9cfe9a5caaa31a91e80a95d3f4a0db213c1bfd1ec7bff79e2e2a24ab` |
| `data/apparel-global-2028-2029/p1.json` | `d1e3d83ffdc11db6d036b376e01152a825fcc7f7787daba3a305d0fa23791e45` |
| `data/apparel-global-2028-2029/snapshot.json` | `89e72ca5c304cda72e2d65e7dfded7cdbcc3bee4dcd63467523ae8788b3b045b` |
| `data/apparel-global-2028-2029.log` | `aa6d9b8e6d1dfc323f26557ebe59a3a4e61191dbd81329b692e4701526f18cba` |
| `data/apparel-us-2026/backward.json` | `a9b45490bb2b3239337ee1882c8388cb10b046ec57d53b2e7846ad3d82ae4025` |
| `data/apparel-us-2026/bridge.csv` | `7c29509d74a8584057c6d77b8c3edcb0cefcdcc90b393ec3efd00e4f32ea1c93` |
| `data/apparel-us-2026/channel_mapping.json` | `442d3410346ab68fee41e23db93cd8735930cd441080fbdf087f54f77f6c8b8e` |
| `data/apparel-us-2026/engine_input.csv` | `7c29509d74a8584057c6d77b8c3edcb0cefcdcc90b393ec3efd00e4f32ea1c93` |
| `data/apparel-us-2026/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/apparel-us-2026/existing_ppc/ppc_event_ledger.csv` | `1e9c36a168d5870a2fa0e4130fda40dddc14d8c52568063d93b84239f6f155c9` |
| `data/apparel-us-2026/existing_ppc/ppc_kpi_summary.json` | `dac4ab82f3e8592e9480c8dbe4564c302dfefd9dd39beed675518c518f5df599` |
| `data/apparel-us-2026/existing_ppc/ppc_lot_reconciliation.csv` | `1b2f5125f09a9534a2346250e5a541fe1561d4eb4c3232ec15c20800d4eeccc0` |
| `data/apparel-us-2026/existing_ppc/ppc_node_pl_summary.csv` | `8402a51e83eb7f3a48502229f3ad293e549fa92257d0fb06980aaa31b19cf5e3` |
| `data/apparel-us-2026/existing_ppc/ppc_node_week_summary.csv` | `8776e4ca5dde66c1ce920bbd3aade0df8844775af840edd22f88649631623ed8` |
| `data/apparel-us-2026/existing_ppc/ppc_profit_zone_summary.csv` | `abdaaf7b85c3b6a575805d195aa320875b49ef48b05390bcc9640ead69c63ad4` |
| `data/apparel-us-2026/input_hashes_after.json` | `e8f9d10ed74524d810dd73dc2cb198c56f277178e95bde9453178cf16824afbb` |
| `data/apparel-us-2026/input_hashes_before.json` | `e8f9d10ed74524d810dd73dc2cb198c56f277178e95bde9453178cf16824afbb` |
| `data/apparel-us-2026/p1.json` | `c84e7cadc9a26e0815fe44295c30dadb2fba8b214ecae721f4895533a54ee6c9` |
| `data/apparel-us-2026/snapshot.json` | `2d4733ac893a24e92e083a62cf7b34c8973f71b02219834e59cc8e8abdbafb42` |
| `data/apparel-us-2026.log` | `a7be9401b4e7957da010023a0dcb2cb0a9c96dcd7ed18fa44b7154645c59c9db` |
| `data/bom-test-2026/backward.json` | `8fafa09bf150b31d56d673c9f780946b1a2bfe8b7cf787bcb2d0fb4d4ea6577c` |
| `data/bom-test-2026/bridge.csv` | `f63e8da1fb7a02e0579904a4d55d53a501809d218978cb2704746b43adeb1314` |
| `data/bom-test-2026/channel_mapping.json` | `0f62f5f8da7ef2bd73635dfc1c41360919170517b8f46c4c0aa139f068c9ef1f` |
| `data/bom-test-2026/engine_input.csv` | `f63e8da1fb7a02e0579904a4d55d53a501809d218978cb2704746b43adeb1314` |
| `data/bom-test-2026/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/bom-test-2026/existing_ppc/ppc_event_ledger.csv` | `f94e7dfe2ace5474cd44f5ece7f19f3e0ab13d6f2c656fd36b6bb27f282a4006` |
| `data/bom-test-2026/existing_ppc/ppc_kpi_summary.json` | `ecbe26c4d4335d96b57fd545939043a8a8cc320db5f01e74b34c59dd2de68440` |
| `data/bom-test-2026/existing_ppc/ppc_lot_reconciliation.csv` | `2febf5edaafe0641649d234275e943dfb07888bbbcf3406027eb4378c26d6956` |
| `data/bom-test-2026/existing_ppc/ppc_node_pl_summary.csv` | `ac72f74fc5374a83ce69b9e14720664d8a1b9ac8060c5d541a9423c951a7c914` |
| `data/bom-test-2026/existing_ppc/ppc_node_week_summary.csv` | `5378d4fd442e8ffbaf32e9980f3709f62d55c5fc06b6078dd60716465b4b27e7` |
| `data/bom-test-2026/existing_ppc/ppc_profit_zone_summary.csv` | `0a614aada04732862c10ee48b79fe81283ea319d5f95329d2445ae4ed6743827` |
| `data/bom-test-2026/input_hashes_after.json` | `7644dcff882a851139674dd6fa39165718f3acb9433e0a88f91ede527e3ddb6b` |
| `data/bom-test-2026/input_hashes_before.json` | `7644dcff882a851139674dd6fa39165718f3acb9433e0a88f91ede527e3ddb6b` |
| `data/bom-test-2026/p1.json` | `02845f7932113e984b0c5b84ca43bdbf5bb5a8e2978e1ab021b5fc41515a24c9` |
| `data/bom-test-2026/snapshot.json` | `4d03eb77df6567af2ce7005366696699ab14c6b7bd1d991508c23e9b7a4db31a` |
| `data/bom-test-2026.log` | `33dd9b9d6b0ddf31adb216f057afde3dde0f0c9de2b9401ddc912517418ec2c6` |
| `data/errors.json` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| `data/ev-europe-2026/backward.json` | `bad86186c13e3147439c697cf0be69674d02ce18350d80ba8e929366e5ffe0ac` |
| `data/ev-europe-2026/bridge.csv` | `81e493cc206c0246703296d4206c5d6ee4bf7898af5103e34659f3261cdb7f1a` |
| `data/ev-europe-2026/channel_mapping.json` | `97031f33aef25d0682fb39dbb017ea4bf58f30fbb2ab1f666c0d7cd18fe1682c` |
| `data/ev-europe-2026/engine_input.csv` | `81e493cc206c0246703296d4206c5d6ee4bf7898af5103e34659f3261cdb7f1a` |
| `data/ev-europe-2026/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/ev-europe-2026/existing_ppc/ppc_event_ledger.csv` | `c54fc5b07f0fe0139ddf60cbfebd90e3e43fd5e78de0b02f0b00c43a7e5423f8` |
| `data/ev-europe-2026/existing_ppc/ppc_kpi_summary.json` | `0755572951502a8b20565227e05225fa91ae98262ba18bd4bf8d3f6bd98cd9b4` |
| `data/ev-europe-2026/existing_ppc/ppc_lot_reconciliation.csv` | `40630105403f07e23cb0b7c8dff5a433f2baccdba1ff6ce71d299522d7cbd022` |
| `data/ev-europe-2026/existing_ppc/ppc_node_pl_summary.csv` | `bc12f578d2ce10849ebf6b771206ef2be96be8a7d6aee3427e9ff623e6623589` |
| `data/ev-europe-2026/existing_ppc/ppc_node_week_summary.csv` | `bb542851177a6fdce6ace1d255679419565c5b45d3dbe30e1bc34de0e268a546` |
| `data/ev-europe-2026/existing_ppc/ppc_profit_zone_summary.csv` | `58ab222614ed9a03f6217899880458274c0b1b2590f601d2cda285b60c25d6f0` |
| `data/ev-europe-2026/input_hashes_after.json` | `5736e56c9e0a057d8b0c2fc3404e302a8ed28d335cff3efa5ae17dc8725d91df` |
| `data/ev-europe-2026/input_hashes_before.json` | `5736e56c9e0a057d8b0c2fc3404e302a8ed28d335cff3efa5ae17dc8725d91df` |
| `data/ev-europe-2026/p1.json` | `70aa4d3e671fb659fe2436e31fbbc09398e30cfb3691552e88b262c9e2d24073` |
| `data/ev-europe-2026/snapshot.json` | `d8b7534657ee711e43ff57cfb9ffbc15fe325a15ab522f6831b7609f59bf7db9` |
| `data/ev-europe-2026.log` | `c62eb313dab66c6f54b6a536ec050da19aa0519a366f34cb91e4227aade2425c` |
| `data/ev-thailand-2026/backward.json` | `bdec0113fdae5b349813398e6da0b4cb57f2b700d13fdb4d7592b901bc590683` |
| `data/ev-thailand-2026/bridge.csv` | `64bb4a11077aa0f0a1ab29529c558f58fdcf650058cb6ea0c3c997bf927df072` |
| `data/ev-thailand-2026/channel_mapping.json` | `bc764c81624f628131fdc2494876597a4bb2644dddb88b3ad08196372a606df8` |
| `data/ev-thailand-2026/engine_input.csv` | `64bb4a11077aa0f0a1ab29529c558f58fdcf650058cb6ea0c3c997bf927df072` |
| `data/ev-thailand-2026/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/ev-thailand-2026/existing_ppc/ppc_event_ledger.csv` | `f13b39ad41a79c7b3605618290952abeb427cd95849ff6d7557c24f9a0827a95` |
| `data/ev-thailand-2026/existing_ppc/ppc_kpi_summary.json` | `fdd4c054b8044478b4596a25c5257c53852b44115a6c30acff8f466fe4d2ecb6` |
| `data/ev-thailand-2026/existing_ppc/ppc_lot_reconciliation.csv` | `053ebf8e1eef57236bc3317e7e21bf80f4ec516cb038fab5bf533c6c05e93e53` |
| `data/ev-thailand-2026/existing_ppc/ppc_node_pl_summary.csv` | `ba785494a1c4b4cd43c7e6c5a5ca4094594d3aaaf4845315dbc90d9d9bda613b` |
| `data/ev-thailand-2026/existing_ppc/ppc_node_week_summary.csv` | `af1c1301b8926db251b13882f7548fd5fa76f274ef5c9231be22baf6d90db1a9` |
| `data/ev-thailand-2026/existing_ppc/ppc_profit_zone_summary.csv` | `629bbc1f72acdb86864e03fe2eff60d245f5d7d3b8129eabc97f5f3a8c973da7` |
| `data/ev-thailand-2026/input_hashes_after.json` | `7e2ff28e6bd1ae6c9543f436010fdaaba20de9055771035f1f4d5f9bdc707a36` |
| `data/ev-thailand-2026/input_hashes_before.json` | `7e2ff28e6bd1ae6c9543f436010fdaaba20de9055771035f1f4d5f9bdc707a36` |
| `data/ev-thailand-2026/p1.json` | `c992e03e797eb969a1f2670c91a4685a9fe828c78669894b66c97151fc114365` |
| `data/ev-thailand-2026/snapshot.json` | `af5039ddb0e2cff6e21c03b2b4916fe30b14acf52734f0ffc86f6de63c8f03a2` |
| `data/ev-thailand-2026.log` | `eca3366b4a104d71a152b408267c0e9208b146efc19b480a3345f22f5bd64869` |
| `data/ev-thailand-2026_update/backward.json` | `3ad6f9b812c4f5f60822c5eec90870a71372750d80e5b2bd3103746fa3c68f07` |
| `data/ev-thailand-2026_update/bridge.csv` | `64bb4a11077aa0f0a1ab29529c558f58fdcf650058cb6ea0c3c997bf927df072` |
| `data/ev-thailand-2026_update/channel_mapping.json` | `bc764c81624f628131fdc2494876597a4bb2644dddb88b3ad08196372a606df8` |
| `data/ev-thailand-2026_update/engine_input.csv` | `64bb4a11077aa0f0a1ab29529c558f58fdcf650058cb6ea0c3c997bf927df072` |
| `data/ev-thailand-2026_update/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/ev-thailand-2026_update/existing_ppc/ppc_event_ledger.csv` | `bf05bcf80d4df791cc2d90f9b81ea9895f52ec26dac0408a55450240e9af4ecf` |
| `data/ev-thailand-2026_update/existing_ppc/ppc_kpi_summary.json` | `fdd4c054b8044478b4596a25c5257c53852b44115a6c30acff8f466fe4d2ecb6` |
| `data/ev-thailand-2026_update/existing_ppc/ppc_lot_reconciliation.csv` | `053ebf8e1eef57236bc3317e7e21bf80f4ec516cb038fab5bf533c6c05e93e53` |
| `data/ev-thailand-2026_update/existing_ppc/ppc_node_pl_summary.csv` | `2ebc0cb8e92f5413794b8d73041aa99329cf68448b2cad1ef8abf13e3dd4aa13` |
| `data/ev-thailand-2026_update/existing_ppc/ppc_node_week_summary.csv` | `8d0aba2eec96a3a24e8d84cd71391dee62f59da584b1a37fb4d0d4860c4d18d2` |
| `data/ev-thailand-2026_update/existing_ppc/ppc_profit_zone_summary.csv` | `629bbc1f72acdb86864e03fe2eff60d245f5d7d3b8129eabc97f5f3a8c973da7` |
| `data/ev-thailand-2026_update/input_hashes_after.json` | `04c85611873075ffced6a0a7238512bd3c173a1e0a5af803eba711d05261171d` |
| `data/ev-thailand-2026_update/input_hashes_before.json` | `04c85611873075ffced6a0a7238512bd3c173a1e0a5af803eba711d05261171d` |
| `data/ev-thailand-2026_update/p1.json` | `3811c521dac3f842432ca9ae91d0be88ae8f3a8ad6a306781778412540379bba` |
| `data/ev-thailand-2026_update/snapshot.json` | `4e1db5e29ce38bbca21af38db6376c997af2d0079cfc83c8d8ebbd031f0b8b22` |
| `data/ev-thailand-2026_update.log` | `c58693e3def8188111b2fd8ce24279e292f9fda32c2f9f54ba6206ebd6a1a0ec` |
| `data/independent_output_checks.json` | `de90c58c82f6e4a49449b07f0f1309502d32db9e7a54a4ce37355246824f2521` |
| `data/smartphone-global-2026-2029/backward.json` | `b1638f389f130ae54ba1abbdd9e49dea19eaca9ddfa5917c880bbd2744e3ef0c` |
| `data/smartphone-global-2026-2029/bridge.csv` | `b9be34b79dfc748dd2704b32707694a748b3678bc2662bfa13d108727f162134` |
| `data/smartphone-global-2026-2029/channel_mapping.json` | `fddcee76172af6cb1f8b3eb671eefceb54eb5a3d648772b073bbeeaee5de64b4` |
| `data/smartphone-global-2026-2029/engine_input.csv` | `b9be34b79dfc748dd2704b32707694a748b3678bc2662bfa13d108727f162134` |
| `data/smartphone-global-2026-2029/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/smartphone-global-2026-2029/existing_ppc/ppc_event_ledger.csv` | `de56ca352898f1ce64be42164266dcece9a0894fe7c8a0d67094b39fee2f4b3b` |
| `data/smartphone-global-2026-2029/existing_ppc/ppc_kpi_summary.json` | `18bcc59bec92e6934588c9f033d148d044e057c3fdeb72bd51cf1f119a4ad964` |
| `data/smartphone-global-2026-2029/existing_ppc/ppc_lot_reconciliation.csv` | `4e66ad9fa3a96d4765d52e891468d5f70ec4812fe90cfc0dd0954447cf5042ed` |
| `data/smartphone-global-2026-2029/existing_ppc/ppc_node_pl_summary.csv` | `2b4e16048de120034d33b973b8c9abc64a1e4093e21e84bb982a38f68836afce` |
| `data/smartphone-global-2026-2029/existing_ppc/ppc_node_week_summary.csv` | `47f876c8376971e7a334f7696650a81ce488469e623e102cb51cb59a2a35e24a` |
| `data/smartphone-global-2026-2029/existing_ppc/ppc_profit_zone_summary.csv` | `a7b1fc4397175753e00a290f13b38651665515a0e29f41cfdd7f12e95dbe8246` |
| `data/smartphone-global-2026-2029/input_hashes_after.json` | `338beac69e32dcf86b68df9d0c4db6b5efb84d96fdca14b24e8e3e52618e8863` |
| `data/smartphone-global-2026-2029/input_hashes_before.json` | `338beac69e32dcf86b68df9d0c4db6b5efb84d96fdca14b24e8e3e52618e8863` |
| `data/smartphone-global-2026-2029/p1.json` | `4380ce5c02a562c0407a39c47b095f4776bf3e3bd1cc8906a151ec15a879474f` |
| `data/smartphone-global-2026-2029/snapshot.json` | `6a00f2449dc98eb9fc746ece2a5cc7fe8a24d14abbb8660c058df70eef74b53c` |
| `data/smartphone-global-2026-2029.log` | `5464e8f18582759b1205a44ecde7fb96686c78b5ce5af61bf5428a94d93f39f3` |
| `data/manifest.json` | `a04f7410645271ad14917c41b5bb774a9f6fe1dc51ffd32d2d7ca50c1f5256a1` |
| `data/oil-global-2027/backward.json` | `7f52c65b9a299ca5998b81656bcb17a1ca88b9a847d3fc51c512e1e06c49d298` |
| `data/oil-global-2027/bridge.csv` | `4fc6d0448d3e5f01aec3a4cf70b624a686ff1e53cad94bfaf697bfd204d46ba2` |
| `data/oil-global-2027/channel_mapping.json` | `fea4c5352c943cf93a44821ec383df99a33a9909ad87e9587f47c00cc7705257` |
| `data/oil-global-2027/engine_input.csv` | `4fc6d0448d3e5f01aec3a4cf70b624a686ff1e53cad94bfaf697bfd204d46ba2` |
| `data/oil-global-2027/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/oil-global-2027/existing_ppc/ppc_event_ledger.csv` | `9dd8a14e379c8c4767469a9c1956ffe2b231bd99440b79de25ac183f20afe7bf` |
| `data/oil-global-2027/existing_ppc/ppc_kpi_summary.json` | `7d1a74fd0280f084e6e802be110a785a9cfcd2c1ee151cf679a214841cf55c3f` |
| `data/oil-global-2027/existing_ppc/ppc_lot_reconciliation.csv` | `04059b4701ad8dc2ecc8fa23338271efeeb6c6d4452d080f8334e50ce75c0415` |
| `data/oil-global-2027/existing_ppc/ppc_node_pl_summary.csv` | `4eda86266aa5dc2a216dc1a25c8b9dfa4bb3c17c05ef4485ed014d413218a238` |
| `data/oil-global-2027/existing_ppc/ppc_node_week_summary.csv` | `333541164bb5da7d65866108a6936a95cd1174f70758043f064c6df273e13158` |
| `data/oil-global-2027/existing_ppc/ppc_profit_zone_summary.csv` | `7f7af7c9e8feb2eff46164e740be0090918ab00b894e3818f3c82b1281d4ab78` |
| `data/oil-global-2027/input_hashes_after.json` | `c7b9650983d22ee2b7d1a8ef7b0b159442d1c780e3b0c8dadbf50c8ebb8f7376` |
| `data/oil-global-2027/input_hashes_before.json` | `c7b9650983d22ee2b7d1a8ef7b0b159442d1c780e3b0c8dadbf50c8ebb8f7376` |
| `data/oil-global-2027/p1.json` | `f16caf2e6257e289c4c584eb53967f7a17463df82ea061193f0337e69f53d9f8` |
| `data/oil-global-2027/snapshot.json` | `7cc9d516d774463462fb1e7e87f695e1b7e0dc5eee64be5d4af3d2e0b58bf4b0` |
| `data/oil-global-2027.log` | `676f4edb479b3b7ce0ab60728ee20692dbb9b1c80c4236c062d854eba176f2fd` |
| `data/p1_all_cases.csv` | `0969d95e98b76fae4dfc53754f457aae621def8a88a0d96568299bd24b3773d6` |
| `data/probe_run.log` | `3404599fa555e74ab26f5949658f0cc8e214fcfe1d0cb474f79480c17830339b` |
| `data/qualification/pytest_full.xml` | `2f57bc8223310153202c2a5ed045d224cfa53e9bc85cf810b880d22390ec1d52` |
| `data/qualification/pytest_golden.log` | `0967bca0d1427cb1daa16ca7864273acac223c413cdfb0df022c86bcf26b5ffd` |
| `data/qualification/pytest_golden.xml` | `f155de44e3ba9803a0277eb7e382f827c9bbb01f9436096cb0033f4fdea430ff` |
| `data/rice-japan-2027-2028/backward.json` | `2c3785c487b9311b3a9d14e210448fcfbb10b22157def6cf07df600dea25d444` |
| `data/rice-japan-2027-2028/bridge.csv` | `cd1148e6c9d3438955329510262fb7854cba29a60b6da7ad848ac02b6584e938` |
| `data/rice-japan-2027-2028/channel_mapping.json` | `79e371b0a38e08b7fbfcd4a41e57b87f2599f59618089dd2b758e6cfca13040e` |
| `data/rice-japan-2027-2028/engine_input.csv` | `cd1148e6c9d3438955329510262fb7854cba29a60b6da7ad848ac02b6584e938` |
| `data/rice-japan-2027-2028/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/rice-japan-2027-2028/existing_ppc/ppc_event_ledger.csv` | `a5a4424e87a37f9d0826693fa9272a093104ae9e5f7bd60b5a32bbcfbc08b4a2` |
| `data/rice-japan-2027-2028/existing_ppc/ppc_kpi_summary.json` | `078f766608c705975f28c5c946f5f9cb09fb1f151eafa85591365b7961f182aa` |
| `data/rice-japan-2027-2028/existing_ppc/ppc_lot_reconciliation.csv` | `35185a0ec184030fef4a03ecf6d2247d6fa8a07a8e4635415858c8b9eb20be57` |
| `data/rice-japan-2027-2028/existing_ppc/ppc_node_pl_summary.csv` | `c65a59225264deced0a2c222b3e5e0076a8ccdfbf673e26f9142ffc155e5e327` |
| `data/rice-japan-2027-2028/existing_ppc/ppc_node_week_summary.csv` | `d1204042ab7d5e6b3eed0a73d7ed38c327030c7cb25c6fd30b36d2f81bb7876c` |
| `data/rice-japan-2027-2028/existing_ppc/ppc_profit_zone_summary.csv` | `19b864f069646a85239aff8e2b9418e37a2a633d747649a619ac2289246ffd94` |
| `data/rice-japan-2027-2028/input_hashes_after.json` | `0a797d6c5278b804ae239956266a7b39ad40f8ee96d4b7d0d0830c47cd7fee92` |
| `data/rice-japan-2027-2028/input_hashes_before.json` | `0a797d6c5278b804ae239956266a7b39ad40f8ee96d4b7d0d0830c47cd7fee92` |
| `data/rice-japan-2027-2028/p1.json` | `9c79169cc05be0073c888793b42e420c0c76c5f0f7da08dae2886153b8c2cad9` |
| `data/rice-japan-2027-2028/snapshot.json` | `4415752725d1bb7447858fd81285ac4729bfac36787ee87d21553cba62b47e34` |
| `data/rice-japan-2027-2028.log` | `013d94e8ab8e00cebacb1e4764b17ddf44f2ddc88640f62f44bbc748ba31dcb6` |
| `data/sha256.json` | `42a90a88701563c5622c470627c0f508641f91a2b31d06d256e5fbc7a838a6f0` |
| `data/smartx-2027-2029/backward.json` | `4a81df4c284213a97d89a83e785a9b7b7b10b128f7b832a231c455c8a8d04374` |
| `data/smartx-2027-2029/bridge.csv` | `5bde65c24e2fe9c08fb731781f26254432801ebedf98713c3c970179faa2a55e` |
| `data/smartx-2027-2029/channel_mapping.json` | `c8534423a990c8aabe68d4cd59e7df7d3a1f07eaa985919c9d6deb55e4ac4c2f` |
| `data/smartx-2027-2029/engine_input.csv` | `5bde65c24e2fe9c08fb731781f26254432801ebedf98713c3c970179faa2a55e` |
| `data/smartx-2027-2029/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/smartx-2027-2029/existing_ppc/ppc_event_ledger.csv` | `8c006cb1f75da07ea129a3c0fe0a63321ab3b18724eb882830814aa1613c9be6` |
| `data/smartx-2027-2029/existing_ppc/ppc_kpi_summary.json` | `76d028028eb6738d70c93eca821c361566405afe7519288f9584a88441ec8353` |
| `data/smartx-2027-2029/existing_ppc/ppc_lot_reconciliation.csv` | `a95f609b2fbe5ff45d69a96c549affa0695900e05939d2f6272ef5406046e508` |
| `data/smartx-2027-2029/existing_ppc/ppc_node_pl_summary.csv` | `bb2968cbfc40ba694a40d9bdfe170d8d743b5de45e8ff0dd401fff53f2e1f1e0` |
| `data/smartx-2027-2029/existing_ppc/ppc_node_week_summary.csv` | `c978a2cd07a71c637d3ca5dadaeb19c1b83a5cfc1d53dbe5e3d40d5432e16c15` |
| `data/smartx-2027-2029/existing_ppc/ppc_profit_zone_summary.csv` | `abd5d6cfa923256d35e3afe35d7ad6126ae311d461fddc5a946760ec2e457090` |
| `data/smartx-2027-2029/input_hashes_after.json` | `d3f80e157c74eb433bd460d9be4f162a2dc22545171e8b32211dfac039e3fd44` |
| `data/smartx-2027-2029/input_hashes_before.json` | `d3f80e157c74eb433bd460d9be4f162a2dc22545171e8b32211dfac039e3fd44` |
| `data/smartx-2027-2029/p1.json` | `ec8170e968e6c08b3dff2e83ba42c0215923cb5e929defada96004fcc1d6d5ba` |
| `data/smartx-2027-2029/snapshot.json` | `cd04b2f3f41c81876f35a766a6967a324b6b71986230cbfe28d48fd490c0cc63` |
| `data/smartx-2027-2029.log` | `88bead75d7467b1602ca81a1c389aacf1e28900e95fddc22b57ef8e6471671f5` |
| `data/soysauce-eu-2027/backward.json` | `aa4b22d7cf2ec9848a69fae58d8d0ab3481884234fd12741252388b97bc0ee77` |
| `data/soysauce-eu-2027/bridge.csv` | `e8db83fc2eeb50b0db8928a5e92f809c11c23a2c0b1659c1338aea6733c6cd96` |
| `data/soysauce-eu-2027/channel_mapping.json` | `b424a6570040ab83d0af865a89c2f9b6424fc47c0a90a43b38ca561121f46843` |
| `data/soysauce-eu-2027/engine_input.csv` | `e8db83fc2eeb50b0db8928a5e92f809c11c23a2c0b1659c1338aea6733c6cd96` |
| `data/soysauce-eu-2027/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/soysauce-eu-2027/existing_ppc/ppc_event_ledger.csv` | `c68444508b518ee7c41fc1889ab311e88a1cc21d198e6c0f8bcb514a256a877e` |
| `data/soysauce-eu-2027/existing_ppc/ppc_kpi_summary.json` | `49b7f84ac6b07d5978bbd9c0f85f87e2724e3c99ac6b3b444a20568ff113bf36` |
| `data/soysauce-eu-2027/existing_ppc/ppc_lot_reconciliation.csv` | `81c3c081a451fe5c4d95e8fd0b0cdc52d6526537db80037cdc058262642db76c` |
| `data/soysauce-eu-2027/existing_ppc/ppc_node_pl_summary.csv` | `ace9cada447f6f7ba0c2ffbcc453ff163bf3542061230109b4599b9542d87eae` |
| `data/soysauce-eu-2027/existing_ppc/ppc_node_week_summary.csv` | `e0d0fdd5134ab41de2c4e82b3739ad0746eb09ba9b74975223c19918f22b683f` |
| `data/soysauce-eu-2027/existing_ppc/ppc_profit_zone_summary.csv` | `f30f7d29777f32b6943f90a3d1f2750d76aabe4b7b4678c02f40b3abc0cd11e6` |
| `data/soysauce-eu-2027/input_hashes_after.json` | `87035054d6de025f329ebcfb5ef272cef557b4395c14e03f102b495264ed5f67` |
| `data/soysauce-eu-2027/input_hashes_before.json` | `87035054d6de025f329ebcfb5ef272cef557b4395c14e03f102b495264ed5f67` |
| `data/soysauce-eu-2027/p1.json` | `374b9cb474304b72d68da97496fb42fb2d02fa7f0ed758a4f792ec8b22727bb2` |
| `data/soysauce-eu-2027/snapshot.json` | `a64f23cad8ef3a48e48b33e3ca063cbceb7676c4a4a466d0ed133b40746d2fd0` |
| `data/soysauce-eu-2027.log` | `56b1da08015ac0c9de5838ae20bbd5245bf57b461303acf94bc18a149e32a8be` |
| `data/soysauce-jpy-2027/backward.json` | `3217ee637d444c89361b3a78b1f18cdf54e3c25d35c93b970781e5ea50d67ce0` |
| `data/soysauce-jpy-2027/bridge.csv` | `e8db83fc2eeb50b0db8928a5e92f809c11c23a2c0b1659c1338aea6733c6cd96` |
| `data/soysauce-jpy-2027/channel_mapping.json` | `b424a6570040ab83d0af865a89c2f9b6424fc47c0a90a43b38ca561121f46843` |
| `data/soysauce-jpy-2027/engine_input.csv` | `e8db83fc2eeb50b0db8928a5e92f809c11c23a2c0b1659c1338aea6733c6cd96` |
| `data/soysauce-jpy-2027/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/soysauce-jpy-2027/existing_ppc/ppc_event_ledger.csv` | `7b1a397f7ddc97e387f84f768a27c3143eef3a7701769b3b8f20873f757c9289` |
| `data/soysauce-jpy-2027/existing_ppc/ppc_kpi_summary.json` | `812ec9e0c58765d2c190bcb131017ae9c946212f8ba8627851be026f605f1da3` |
| `data/soysauce-jpy-2027/existing_ppc/ppc_lot_reconciliation.csv` | `eb78aa2bab6f760e8b9073205822407df09c012bd6f82d49c5a3a12cff977476` |
| `data/soysauce-jpy-2027/existing_ppc/ppc_node_pl_summary.csv` | `8009526f7deec2e667673a5c2e115bc2c196cba581f025578d08af9ace23d755` |
| `data/soysauce-jpy-2027/existing_ppc/ppc_node_week_summary.csv` | `1910b94ebbe5ae70307aea9cf382cb0add9cbe57b907f612ecc6ce3ca6fc4533` |
| `data/soysauce-jpy-2027/existing_ppc/ppc_profit_zone_summary.csv` | `ad3b2e3bd2ec0193009a3a4fe430eb2c618b6998b2a0b7f144c6c658186160b1` |
| `data/soysauce-jpy-2027/input_hashes_after.json` | `de179f428e2951ab12b886db74df50d9b760a84e1062ac30be8f25dcace28261` |
| `data/soysauce-jpy-2027/input_hashes_before.json` | `de179f428e2951ab12b886db74df50d9b760a84e1062ac30be8f25dcace28261` |
| `data/soysauce-jpy-2027/p1.json` | `70f68659e3c6031209295f3fb167504ac6e929022656a3169fafd6422b04847e` |
| `data/soysauce-jpy-2027/snapshot.json` | `246e502f8519e1a578281a5970672596535df4e033621d75bd65b30ce56e3fbd` |
| `data/soysauce-jpy-2027-alloc/backward.json` | `f799373556d391a50bc0c40de36d7b1417cf0d61a32dadfca182990e93123182` |
| `data/soysauce-jpy-2027-alloc/bridge.csv` | `e8db83fc2eeb50b0db8928a5e92f809c11c23a2c0b1659c1338aea6733c6cd96` |
| `data/soysauce-jpy-2027-alloc/channel_mapping.json` | `b424a6570040ab83d0af865a89c2f9b6424fc47c0a90a43b38ca561121f46843` |
| `data/soysauce-jpy-2027-alloc/engine_input.csv` | `e8db83fc2eeb50b0db8928a5e92f809c11c23a2c0b1659c1338aea6733c6cd96` |
| `data/soysauce-jpy-2027-alloc/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/soysauce-jpy-2027-alloc/existing_ppc/ppc_event_ledger.csv` | `7b1a397f7ddc97e387f84f768a27c3143eef3a7701769b3b8f20873f757c9289` |
| `data/soysauce-jpy-2027-alloc/existing_ppc/ppc_kpi_summary.json` | `812ec9e0c58765d2c190bcb131017ae9c946212f8ba8627851be026f605f1da3` |
| `data/soysauce-jpy-2027-alloc/existing_ppc/ppc_lot_reconciliation.csv` | `eb78aa2bab6f760e8b9073205822407df09c012bd6f82d49c5a3a12cff977476` |
| `data/soysauce-jpy-2027-alloc/existing_ppc/ppc_node_pl_summary.csv` | `8009526f7deec2e667673a5c2e115bc2c196cba581f025578d08af9ace23d755` |
| `data/soysauce-jpy-2027-alloc/existing_ppc/ppc_node_week_summary.csv` | `1910b94ebbe5ae70307aea9cf382cb0add9cbe57b907f612ecc6ce3ca6fc4533` |
| `data/soysauce-jpy-2027-alloc/existing_ppc/ppc_profit_zone_summary.csv` | `ad3b2e3bd2ec0193009a3a4fe430eb2c618b6998b2a0b7f144c6c658186160b1` |
| `data/soysauce-jpy-2027-alloc/input_hashes_after.json` | `83f89127ee8966f064450fb25650a18e4dee6984fa3d23ba3ea4bf097c8bc0d1` |
| `data/soysauce-jpy-2027-alloc/input_hashes_before.json` | `83f89127ee8966f064450fb25650a18e4dee6984fa3d23ba3ea4bf097c8bc0d1` |
| `data/soysauce-jpy-2027-alloc/p1.json` | `9d46ea9fbd72e06b5e798e467c02a46708bbc3985767a86a56df225d7ecafc54` |
| `data/soysauce-jpy-2027-alloc/snapshot.json` | `5e86188116ae939351fb29c1fba59989456908991541514d660276911ceb69f7` |
| `data/soysauce-jpy-2027-alloc.log` | `8ea0a4f93d6189258be6fd14e9e531a9331a96acba2a7b94ace73127f45b95ef` |
| `data/soysauce-jpy-2027-alloc__P_opt800/allocation.json` | `77b6fff2f15b86f51eeff1279ca05e2982b236e8fe0451c6ccdb7a96df241c50` |
| `data/soysauce-jpy-2027-alloc__P_opt800/backward.json` | `17405ed2ef61ae406e44dece73124a013c6a77a888164f9ceef08ce8c166f31d` |
| `data/soysauce-jpy-2027-alloc__P_opt800/boundary_ids_OUT_dad_DC_EU_RTM_Soy_Sauce.jsonl` | `367d2143e58f3145b9dc2c71d169a491d3a9e77adf5ceeb32da5ebc99bf4189e` |
| `data/soysauce-jpy-2027-alloc__P_opt800/boundary_ids_OUT_dad_DC_JP_Soy_Sauce.jsonl` | `dd9d272a70f4fd5e8275700fe287a4b61f4352e84de8732627aa831dc7b2dc7f` |
| `data/soysauce-jpy-2027-alloc__P_opt800/boundary_ids_OUT_dad_DC_US_NY_Soy_Sauce.jsonl` | `efc897ec92dc7ae124e88163e247b2f3ee84fb01f105e10585adf73c9ab9a979` |
| `data/soysauce-jpy-2027-alloc__P_opt800/boundary_ids_OUT_dad_DC_US_SF_Soy_Sauce.jsonl` | `9461e9524abbb94364683170935669a45063ae0e2169c79fff8320e609455c53` |
| `data/soysauce-jpy-2027-alloc__P_opt800/bridge.csv` | `592a3f22fe20228fb1991290b8fb698ef07c18439bc5b13b8bfff9457795e96a` |
| `data/soysauce-jpy-2027-alloc__P_opt800/channel_mapping.json` | `b424a6570040ab83d0af865a89c2f9b6424fc47c0a90a43b38ca561121f46843` |
| `data/soysauce-jpy-2027-alloc__P_opt800/demand_forecast_POPT.csv` | `c2b3f23f4023196327c3c25f8b410389926569cbf36a7c53e7362871703e6fee` |
| `data/soysauce-jpy-2027-alloc__P_opt800/engine_input.csv` | `592a3f22fe20228fb1991290b8fb698ef07c18439bc5b13b8bfff9457795e96a` |
| `data/soysauce-jpy-2027-alloc__P_opt800/engine_parameters.json` | `fcb58237b9f90c47de18db90b2f50adaf270b568f70fae967f73f6d16ce480ca` |
| `data/soysauce-jpy-2027-alloc__P_opt800/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/soysauce-jpy-2027-alloc__P_opt800/existing_ppc/ppc_event_ledger.csv` | `4d4e54af63c22d09c19f08d025771c1283ff99078f4cfd6a4537e211efe47cc4` |
| `data/soysauce-jpy-2027-alloc__P_opt800/existing_ppc/ppc_kpi_summary.json` | `705b05a6fc046a196486dc729584daaf75b78cb0c3b029d9c02f0bdaba7b30fd` |
| `data/soysauce-jpy-2027-alloc__P_opt800/existing_ppc/ppc_lot_reconciliation.csv` | `ce27b68e474130f67fc31728cb195572e12d5d6041bceff891be2c0c9b1c6ed1` |
| `data/soysauce-jpy-2027-alloc__P_opt800/existing_ppc/ppc_node_pl_summary.csv` | `d0cb312acc4f566a4360e49504010be585a14082140ad2976b1af097cb459044` |
| `data/soysauce-jpy-2027-alloc__P_opt800/existing_ppc/ppc_node_week_summary.csv` | `5eaf4ffc965c45a31ba2fed97417ef574b4d926a5199582aa46d2e402848b6cc` |
| `data/soysauce-jpy-2027-alloc__P_opt800/existing_ppc/ppc_profit_zone_summary.csv` | `be45ce806689bba4276973099f644ebd9b604947bfc7a2750eac717117b5a10a` |
| `data/soysauce-jpy-2027-alloc__P_opt800/existing_ppc_accumulators.csv` | `e758f601068579cc1deb6f36e70f6848ce3ea69453b4a2e87f8b83b90f34ac2b` |
| `data/soysauce-jpy-2027-alloc__P_opt800/existing_ppc_events.jsonl` | `8e7fa44b4cd5a81b5a779f69b2e27460cfe9b92f4bdb4e25e4c931f6f4931a62` |
| `data/soysauce-jpy-2027-alloc__P_opt800/existing_ppc_kpi.json` | `04100706fb64de400d23129c99140407967efb06c70886cb23a4230d95a6d792` |
| `data/soysauce-jpy-2027-alloc__P_opt800/existing_ppc_node_pl.csv` | `d0cb312acc4f566a4360e49504010be585a14082140ad2976b1af097cb459044` |
| `data/soysauce-jpy-2027-alloc__P_opt800/input_hashes_after.json` | `d23dc41c348298a3c442e2cf9f348149d3420ed5b4484a14bb67c1be62bca6bb` |
| `data/soysauce-jpy-2027-alloc__P_opt800/input_hashes_before.json` | `83f89127ee8966f064450fb25650a18e4dee6984fa3d23ba3ea4bf097c8bc0d1` |
| `data/soysauce-jpy-2027-alloc__P_opt800/leaf_id_differences.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `data/soysauce-jpy-2027-alloc__P_opt800/leaf_id_timing.jsonl` | `88b2b8b157d9bf3b963d6226034436cc71a3344777b9c94e6a6659900472278a` |
| `data/soysauce-jpy-2027-alloc__P_opt800/leaf_id_timing_summary.json` | `7eca42e42ee095c7191b17c27a8867e7819ce6b2c3cdaed633918bf41c66d6a5` |
| `data/soysauce-jpy-2027-alloc__P_opt800/leaf_weekly.csv` | `dd7d24a5a6c11e4cca4cbac819a800ac310389b6649c5ef499ded2c6f92665a2` |
| `data/soysauce-jpy-2027-alloc__P_opt800/main_summary.json` | `133ef01b11ab07d867b2f03dcb34e3c4057118eeaf49b4e10f083b45f85c840a` |
| `data/soysauce-jpy-2027-alloc__P_opt800/node_observations.json` | `d4bb24015d4cf349daf9ca46649da452632a16f90d99fbcfd7743276f2d713fa` |
| `data/soysauce-jpy-2027-alloc__P_opt800/outbound_boundaries.csv` | `2cdfe6859d7a772a2d61a7a2908d7de541f1af12ccfc08788bd17e689f1bb62a` |
| `data/soysauce-jpy-2027-alloc__P_opt800/p1.json` | `a8774c845e13b5f079d188c5c8547ededd49509e7c82c3ec5a7f56b961398b42` |
| `data/soysauce-jpy-2027-alloc__P_opt800/ppc_basis_differences.csv` | `7c4d1ba911658893f17db4a7aeede51b0bcc05274259c03bfffb75bb353c361e` |
| `data/soysauce-jpy-2027-alloc__P_opt800/ppc_entry_links.jsonl` | `5716d9f981d1c5b391192aa9eeeb721fe777896b7244ff3f0180cca45e458864` |
| `data/soysauce-jpy-2027-alloc__P_opt800/ppc_entry_records.jsonl` | `ada7166d33d59a7345c2e549a6915236fc8d0f555a165e3b93f6eea36d35da03` |
| `data/soysauce-jpy-2027-alloc__P_opt800/ppc_node_basis.csv` | `265489ee9728ed78cc2a8bed6378c33d93266e49b7ee17c4d403e6b0c4239eb4` |
| `data/soysauce-jpy-2027-alloc__P_opt800/snapshot.json` | `f10416a945ccd073378600c2e2fe5bad2a446f0a10f2024199e284920d1a8816` |
| `data/soysauce-jpy-2027-alloc__P_opt800/supplied_accumulators.csv` | `e758f601068579cc1deb6f36e70f6848ce3ea69453b4a2e87f8b83b90f34ac2b` |
| `data/soysauce-jpy-2027-alloc__P_opt800/supplied_events.jsonl` | `8e7fa44b4cd5a81b5a779f69b2e27460cfe9b92f4bdb4e25e4c931f6f4931a62` |
| `data/soysauce-jpy-2027-alloc__P_opt800/supplied_kpi.json` | `04100706fb64de400d23129c99140407967efb06c70886cb23a4230d95a6d792` |
| `data/soysauce-jpy-2027-alloc__P_opt800/supplied_node_pl.csv` | `d0cb312acc4f566a4360e49504010be585a14082140ad2976b1af097cb459044` |
| `data/soysauce-jpy-2027-alloc__P_opt800/supplied_sales.csv` | `592a3f22fe20228fb1991290b8fb698ef07c18439bc5b13b8bfff9457795e96a` |
| `data/soysauce-jpy-2027-alloc__P_opt800/trial02_missing_bottling_ids.jsonl` | `57ac3380bf87d42c2757b2bdfe7852d1a1bf5684cf25bba8993ee60ec3c2c3ef` |
| `data/soysauce-jpy-2027-alloc__P_opt800/trial02_reproduction.json` | `6e7937e44c85188a1a525c9e2b5eafc4e226ad5b20a635ec942533cfb5a02598` |
| `data/soysauce-jpy-2027-alloc__P_opt800.log` | `95eaeb56c9ec6210f06389932156794ea817fb6b881d4d9d62ae56a1c848107e` |
| `data/soysauce-jpy-2027.log` | `9d0e6d54fa6eab00bf76bdf4285530e69c6e59d47af448f96431a35b195f7e41` |
| `data/soysauce-us-2027/backward.json` | `fd369120cb2e5c89a937f618b5fcf35ee1a946031f16532d6a442acb71e700a0` |
| `data/soysauce-us-2027/bridge.csv` | `3b370488c2ecdd23d273b0c2daf76f5269c2a30e74b4ce8882605b8ebbd11216` |
| `data/soysauce-us-2027/channel_mapping.json` | `b424a6570040ab83d0af865a89c2f9b6424fc47c0a90a43b38ca561121f46843` |
| `data/soysauce-us-2027/engine_input.csv` | `3b370488c2ecdd23d273b0c2daf76f5269c2a30e74b4ce8882605b8ebbd11216` |
| `data/soysauce-us-2027/excluded.csv` | `8d679156996092e120d3d719dd10f93763e900f380d784927e0cebeb1f23dfc3` |
| `data/soysauce-us-2027/existing_ppc/ppc_event_ledger.csv` | `de7cd469a69ec0737b60da3a6ee35f05205a8c012daaa315836cfe3a1abdebb1` |
| `data/soysauce-us-2027/existing_ppc/ppc_kpi_summary.json` | `1b73564f02479008a5e8392c2ab14fe157e434d1766d1ff3573ea2b27ad2c092` |
| `data/soysauce-us-2027/existing_ppc/ppc_lot_reconciliation.csv` | `fbea9f394fe1866c7baa20c43d78eefbc18c5b7311d4fc969864e0c16fd45b81` |
| `data/soysauce-us-2027/existing_ppc/ppc_node_pl_summary.csv` | `0f0f3e6d512bec9421d198e76f4799d0dd6097cc95918513f88bd18c5586fea6` |
| `data/soysauce-us-2027/existing_ppc/ppc_node_week_summary.csv` | `91b07704c36dd05eb7c3beabbafc8ee6239c79d2c6ad43297763804e3f8b9cf2` |
| `data/soysauce-us-2027/existing_ppc/ppc_profit_zone_summary.csv` | `850c6be024073b46051993dfe9d55ae185703aafed76f020622b031574fbc040` |
| `data/soysauce-us-2027/input_hashes_after.json` | `7f27982d5b8708a7268b71bb9fec264a59e291c0b0f8cc0d2e74ba3c10a08da9` |
| `data/soysauce-us-2027/input_hashes_before.json` | `7f27982d5b8708a7268b71bb9fec264a59e291c0b0f8cc0d2e74ba3c10a08da9` |
| `data/soysauce-us-2027/p1.json` | `c8a779328731571e565174105dab4717864ebff2c927b77674fd44741c35f6ec` |
| `data/soysauce-us-2027/snapshot.json` | `3f6d29f6e4222d5c7be5336e07e76aa0357de719dca25f6e256c5cdaf91bd86c` |
| `data/soysauce-us-2027.log` | `99dae5b07170dd3280ead3704e99be675984d2c53cb01578a8a0c11e5acc2cc8` |
| `data/tracked_diff_after.json` | `0e3d3a955b3e7d3587f31e69fa727eb2dafa22efe0d58b49bb1b370af082ff22` |
| `tools/probe_ppc_entry.py` | `13af6e77f3d4514bc14b5d31a6b33ede43bc4a61f2de0fcf99873bb411ec1546` |
