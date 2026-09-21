# 動作検証スクリプト

`tools/gen_apparel_global_model.py`で生成したCSV一式が、WOMの実エンジン(GUIと同じコードパス)で正しく動作することを検証するスクリプト群。apparel-us-2026のexercises/と同じ考え方(実際にエンジンコードを再実行し、数値で確認する)を踏襲。

## verify_pipeline.py
PSI(Backward/Forward Planning) → PPCエンジン → Management engine(narrow GM) → Landed Cost / Tariffシナリオ比較、をフルパイプラインで実行。

```bash
cd wom-v1r1m8
python3 data/sample/apparel-global-2028-2029/verify/verify_pipeline.py
```

確認内容:
- 多階層InBound(Fabric→Dyeing→Trim→Garment)・多階層OutBound(SP→FG_WH→DC_US/DC_JP→Retail)が破綻なく計画されること
- PPCエンジンのTrust Event(異常検知)が0件であること
- Management engineとLanded Cost engineがそれぞれ妥当な粗利率を出力すること

## verify_fx_scenarios.py
`ppc_fx_rate.csv`にはシナリオ列がないため(週次の単一レート表のみ)、Base/StrongYen/WeakYenの3通りのJPY/USDレート前提でPPCエンジンをそれぞれ再実行し、JP市場売上のUSD換算額・粗利率への影響を検証する。モデルの実CSVは書き換えず、`tempfile`の隔離コピー上でのみ操作する。

```bash
cd wom-v1r1m8
python3 data/sample/apparel-global-2028-2029/verify/verify_fx_scenarios.py
```

### 検証結果(2028-07-13)
| シナリオ | JPY/USD | JP売上(USD換算) | Base比 | JP粗利率 |
|---|---:|---:|---:|---:|
| Base | 150.0 | $3,837,856 | ±0.0% | 41.7% |
| StrongYen | 130.0 | $4,427,897 | +15.4% | 49.5% |
| WeakYen | 170.0 | $3,385,971 | -11.8% | 33.9% |

US市場売上(USD建て)はFXシナリオに関わらず完全に不変であることも確認済み(アサーションで自動検証)。円高でJP売上のUSD換算額・粗利率が上がり、円安で下がるという経済的に自然な方向性が再現されている。

## 発見・修正したエンジンバグ

検証中に、`wom/ppc/ppc_tariff.py`のOutBound多階層DAD chain(chain長2以上)処理で、2段目以降のinter-DAD edge(例: `FG_WH_BD->DC_US_Offshore`)の輸送費が`acc.logistics_in_base`に混入し、`ppc_reconcile.py`のMOM_PROFIT_TOO_LOWチェックを誤発火させるバグを発見・修正した(全416lotで誤発火 → 修正後0件)。

これは2026-07-10に修正済みの`mom_to_dad_freight_base`分離と全く同じ種類のバグで、今回新たに`inter_dad_freight_base`フィールドを追加して同様に分離した。`Cookie-jp-2026`(`DC_import_Buffer->DC_Import_Main`)も同じ2階層DAD構造を持ち、`ppc_edge_cost_rule.csv`に非ゼロの費用が設定されているため、このバグの影響を受けていた可能性がある(本セッションでは未検証、別途確認を推奨)。

修正ファイル: `wom/ppc/ppc_models.py`, `wom/ppc/ppc_tariff.py`, `wom/ppc/ppc_reconcile.py`

## MOM節点(Garment)のCarry-Over(CO)急増について(2028-07-13)

GUI上のPSIグラフで、Garment_BD/Garment_PT(終端MOM)にCOロットが多数・恒久的に蓄積して見える現象を調査した。

### 原因

本ケースの需要は「年間通して途切れない(BASELINE_FRAC=0.3で最低需要が継続)」設計だが、Garment自身のInBound上流チェーン(Fabric→Dyeing→Trim)がGarmentに最初の資材を届けるまでには`upstream_lt`週(Offshore:3+3+2=8週、Vertical:1+1+1=3週)かかる。シミュレーション開始時点で中間工程(Dyeing/Trim/Garment)に仕掛在庫(WIP)を一切保持していない(`inventory_master.csv`は`sku_id`/`region`のみをキーとする設計上、末端以外のノードにWIPを事前投入できない)ため、Garmentは週0から販売目標(S)を負いながら、資材が届く週`upstream_lt`まで生産(P)を一切開始できない。この間の未達分がCOとして積み上がり、その後はP=Sで推移するため、一度積み上がったCOは解消されずに恒久的に残る。数値的にはCO ≈ weekly_demand × upstream_lt で説明でき、実測値(旧CSV、Offshore CO=5520=690×8、Vertical CO=2070×690×3)と正確に一致した。これはWOMエンジンのバグではなく、「初日から需要がある」という本ケースの需要設計と、中間ノードWIPを事前投入できないCSVスキーマ制約の組み合わせによって生じる、仮想立ち上げ期の一時的な現象である。

### 対応

`tools/gen_apparel_global_model.py`に`ramp_factor()`を追加し、`demand_forecast.csv`の需要を「立ち上げ猶予期間」付きで生成するよう変更した。市場ごとのダウンストリーム輸送リードタイム(`downstream_lt` = FG_WH→DC→Retail)だけ需要を完全ゼロに据え置き、その後`upstream_lt`週かけて0→フルベースラインへ線形ランプさせる(BackwardPlannerがGarment自身の必要出荷日を、この市場別ダウンストリームのリードタイム分だけ過去へシフトして計算するため、単純に週0からランプさせるだけでは、そのシフトによってGarment側では既にフルランプ後の値として現れてしまい、効果が相殺されることが直接検証で判明した — 詳細は`ramp_factor()`のdocstring参照)。

あわせて、`demand_forecast.csv`はqty=0の週も明示的に行として出力するよう変更した(`verify_pipeline.py`やGUIのPlanning実行は`sorted(demand_df["week"].unique())`でシミュレーション対象週を決定するため、需要ゼロの立ち上げ猶予週の行を省略すると、その週がシミュレーション範囲から丸ごと消え、同じ問題が別の週にずれて再発することが判明したため)。

### 結果(需要ランプ導入時点、暫定)

| ブランド | 修正前CO最大値 | 需要ランプ後CO最大値 | 削減率 |
|---|---:|---:|---:|
| Apparel_Offshore (Garment_BD) | 5,520 | 4,657 | -15.6% |
| Apparel_Vertical (Garment_PT) | 2,070 | 1,840 | -11.1% |

この時点ではCOはゼロにはならず、一定量が残存していた。これは`FG_WH`の安全在庫日数(`ss_days_fg_wh`)がBackwardPlannerの必要出荷日計算にさらなる前倒しバッファを加えており、需要ランプ(単純な区間リードタイムの合計)がこのバッファ分を厳密には織り込めていなかったため。この時点では「データ側の工夫による近似的な緩和策」であり、根本解決ではないことをユーザーに説明した。

## Step 8 PushProductionPlanner(InBound decoupling)によるCO完全解消(2028-07-13、追加対応)

ユーザーから、PSIグラフでCOロットがInBound laneを流れていく様子を見た上で「PULL方式のバッファリング在庫を置くか、InBound全体で生産能力をバランスさせるか」という設計上の提案があった。

コードを直接確認した結果、②の能力バランスは今回のCOには効かないと判明した(Fabric/Dyeing/Trimは`cap_unconstrained=50000`で意図的に無制約にしてあり、今回のCOは能力不足ではなく物理的なリードタイムそのものが原因のため)。一方、①のPULL/バッファリングの発想は正しく、`wom/engine/push_pull.py`にDBR(Drum-Buffer-Rope)方式の本格的な仕組み(Step 8, `PushProductionPlanner`)が既に実装されていることを確認した。これは`smartx-2027-2029`ケースの`Buffer_Chip_TW`節点(`push_config.csv`、Mode 4「LT-shifted demand」)で既に実運用されている仕組みで、OutBound専用の`buffering_stock_flag`(GUIの「Buffering Stock Optimized Allocation」プラグイン)とは別物であり、InBound側のdecoupling(生産分離点)を指定できる。

### 実装

`Garment_BD`/`Garment_PT`(終端MOM、まさにCOが発生していた節点)自体をdecoupling nodeに指定し、Mode 4(LT-shifted demand、`push_lead_time_weeks` = upstream_lt = Fabric+Dyeing+Trimの合計リードタイム)で構成した(`push_config.csv`)。

```csv
sku_id,node_id,push_qty_per_week,buffer_lots,mode_only,mom_ref_node_id,pre_build_qty_per_week,pre_build_end_week,push_lead_time_weeks,push_eol_week
Apparel_Offshore,Garment_BD,0,0,False,,0,,8,
Apparel_Vertical,Garment_PT,0,0,False,,0,,3,
```

コード上の効果: decoupling node配下(Fabric→Dyeing→Trim)は`push_sub`(無条件でバッファへ流し込むパススルー)になり、Fabricの生産量は`Garment.psi4demand[week+LT][S]`(Garment自身のLT週先の必要量)で駆動される。node間の物理輸送リードタイム(`_propagate_to_parent`)は通常通り適用されるため、Fabricがweek `w`に生産した分は、Dyeing→Trimを経てちょうど`w+upstream_lt`週にGarmentへ到着する。これはGarment自身の`psi4demand[w+upstream_lt][S]`と数学的に完全一致するため、定常状態(week >= upstream_lt)ではP=Sが厳密に成立し、需要ランプ近似で生じていた誤差(ss_days_fg_wh起因)も解消される。

さらに、decoupling node(plan_mode="push")ではCOカスケードそのものが無効化される設計になっている(`forward_planner.py`: "no CO cascade... CO caused exponential snowball and is not meaningful for PUSH nodes")。物理的に不可避な立ち上げ期の供給ギャップは、恒久的に蓄積するCOではなく、週ごとに独立した「shortfall」信号(`node._push_shortfall`)として記録される。

### 結果(需要ランプ + Step 8 PUSH決定点、最終)

| ブランド | 修正前CO最大値 | 最終CO最大値 | 立ち上げ期shortfall |
|---|---:|---:|---|
| Apparel_Offshore (Garment_BD) | 5,520 | **0** | week 0〜7に345〜690lots/週(非累積) |
| Apparel_Vertical (Garment_PT) | 2,070 | **0** | week 0〜2に460〜690lots/週(非累積) |

CO(Garmentの`psi4supply[CO]`)は全104週にわたって完全にゼロになることを直接検証済み。PPC(trust_events=0)、Management engine、Landed Cost / Tariffシナリオ、FXシナリオの結果は需要ランプ導入時点と完全に同一(総数量・総売上は変わらないため)で、全項目パス。

### 副作用・既知の制約

- `FG_WH_BD`/`FG_WH_PT`の最大在庫lot数が0になった(需要ランプのみの時点では6,629/2,300だった)。これはMode 4のPUSHスケジュールが「必要な分だけを必要なタイミングで」供給するため、Garmentからの出荷(actual_s)が需要をぴったり追従し、サージ的な在庫の山ができなくなったため。設計上は望ましい挙動だが、需要変動リスクに対する現実的なクッション(バッファ)がゼロになっている点には注意。`buffer_lots`をゼロ以外に設定する(Mode 2/3)ことで意図的な安全在庫を持たせることも可能。
- GUIのPSI Chartパネルは現状、`_push_shortfall`(週次shortfall信号)を専用の可視化要素として表示していない(コード確認済み、`wom/gui/app.py`にshortfall関連の参照なし)。COバーは表示されなくなるが、立ち上げ期の需要未達自体は現状のチャートでは明示的には見えない(内部データとしては保持されている)。将来的な拡張候補。
- Step 8のPUSH設定はCSV(`push_config.csv`)経由でGUIが自動検出・適用する(`wom/gui/app.py`の`_try_load_sample_paths`/`_f_push`ロジック、既存の汎用機能)。今回、GUIコード自体の変更は不要だった。

再検証コマンド:
```bash
cd wom-v1r1m8
python3 tools/gen_apparel_global_model.py
python3 data/sample/apparel-global-2028-2029/verify/verify_pipeline.py
python3 data/sample/apparel-global-2028-2029/verify/verify_fx_scenarios.py
```

修正ファイル: `tools/gen_apparel_global_model.py`(需要ランプ)、`data/sample/apparel-global-2028-2029/push_config.csv`(新規、Step 8設定)、`data/sample/apparel-global-2028-2029/verify/verify_pipeline.py`・`verify_fx_scenarios.py`(Step 8配線を追加)。`wom/gui/app.py`・エンジンコードの変更は不要(既存機能の活用のみ)。

## 解決済み: OutBound側(FG_WH/DC)でCOが恒久的に積み上がる問題(2028-07-13、発見・修正)

Step 8導入後にGUIで確認したところ、InBound側(Garment)のCOは解消された一方、OutBound側の`FG_WH_BD`/`FG_WH_PT`(DAD節点)でCOが全期間にわたり単調に積み上がっていく現象が見つかった(週が進むほど増加し、シミュレーション終了時点で総需要とほぼ同量に達する)。

**原因はエンジン内部の直接検証により特定済み**: これは需要と供給の「総量アンバランス」ではない(総量はほぼ一致していた)。実際には、Step 8 `PushProductionPlanner`が生成する新規Lot_IDと、OutBound側(SP/FG_WH/DC/Retail)が保持する既存の需要紐付けLot_IDが一致しないための「ロット識別子の不一致」が原因だった。

検証手順と根拠:
1. `FG_WH_PT.psi4supply[P]`(受け取った供給)が全104週にわたって**完全にゼロ**であることを直接確認(`ForwardPlanner`内部状態を直接インスペクトして確認)。
2. Phase 2ブリッジ(MOM→supply_point)自体は正常に機能しており、`SP.psi4supply[P]`には総量90,696lotsが正しく渡っていることを確認(バグはブリッジそのものではない)。
3. `SP`から`FG_WH`への伝播(`_propagate_to_child`)はPULLモードの`_process_node`内で`_match_by_identity()`によるLot_ID完全一致マッチングを経由するが、PUSH起源のlot_id(例: `Apparel_Vertical:US:2028-W01:00001`、生産週ベース)と、OutBound側が元々保持する需要紐付けlot_id(例: `Apparel_Vertical:US:2028-W06:00001`、需要週ベース)は、同じ物理的な注文であっても文字列として一致しないため、マッチが一切成立しない。
4. 総量ベースでは、PUSH側の実出荷総量90,696lotsに対し、SP側の需要総量92,536lotsとほぼ一致(差分約2%、Mode 4の自然EOL停止によるシミュレーション終端側での軽微な取りこぼしが要因)。**アンバランスは軽微であり、CO急増の主因ではなかった。**

### 根本原因(ユーザー指摘): WOMのLot_ID原則違反

ユーザーから「新規Lot_IDの生成とPSI Listへの初期セットは、計画の初期状態で一回のみ行われるべきで、計画の途中で新規Lot_IDを発生させることはWOMの原則にない」との指摘があり、これが根本原因の正確な特定につながった。

`wom/engine/push_pull.py`の`PushProductionPlanner.setup()`は、Mode 4(LT-shifted demand)において`demand_ref_node.psi4demand[w+LT][S]`という**既存のLot_IDリスト**に既にアクセスしていたにもかかわらず、`_lt_shifted_schedule()`が個数(`len(...)`)だけを取り出してLot_IDリスト自体を破棄し、`_generate_regional_lots()`経由で`LotIDGenerator`により生産週ベースの**全く新しいLot_ID**を鋳造し直していた。これがWOMの「Lot_IDは初期計画時に一度だけ生成される」という原則への違反であり、OutBound側の完全一致マッチングが機能しなくなっていた真因だった。

### 修正内容

`wom/engine/push_pull.py`の`PushProductionPlanner.setup()`で、Mode 4のみ新規Lot_ID鋳造を廃止し、`demand_ref_node.psi4demand[w+LT][S]`の**既存Lot_IDリストをそのまま**leaf_in(Fabric)のPに割り当てる(生産タイミングだけ前倒しする、Lot_ID自体は不変)よう変更した。複数leaf_inノードがある場合は既存lotを連続スライスで分配し、新規ID生成は行わない。

Mode 1〜3(fixed/replenishment/time-phased)は、特定の未来需要lotとの一対一対応がない匿名のPUSH-to-stockスケジュールであるため、今回は対象外とし、同種の下流マッチングギャップが起き得る既知の限界として記録するにとどめた。

### 結果(最終)

| ブランド | 修正前(Mode4新規lot生成時) FG_WH最大CO | 修正後 FG_WH最大CO | 修正後 total_P到達 |
|---|---:|---:|---|
| Apparel_Offshore (FG_WH_BD) | 88,760(全期間で単調増加) | 5,174(有界、通常の立ち上げ移行と同水準) | 83,586/83,586(100%到達) |
| Apparel_Vertical (FG_WH_PT) | 92,766(全期間で単調増加) | 2,070(有界) | 90,696/90,696(100%到達) |

Garment(InBound)のCOは引き続き全期間ゼロを維持。PPC(trust_events=0)・Management engine・Landed Cost/Tariffシナリオ・FXシナリオの数値は総量が変わらないため修正前後で完全一致し、全項目パス。

### 回帰確認: 既存テスト・他ケースへの影響

- `tests/test_step8_push_pull.py`(既存8テスト): 全てパス。Mode 4を使うテストは元々存在しなかったため、今回の変更範囲は未カバーだったが、既存のMode 1/2の挙動に影響がないことを確認
- `push_config.csv`を使う他ケースをヘッドレスで直接再実行し、DAD節点のtotal_P/CO/在庫を確認:
  - `smartx-2027-2029`(Buffer_Chip_TW、InBound中間tierがdecoupling): DC_EMEA/DC_APAC ともtotal_P正常到達、max_CO=0
  - `ev-europe-2026`(Factory_Import_HU): DC_EV_Import total_P=7,929(push_lots 7,945とほぼ一致)、max_CO=732(有界)
  - `ev-thailand-2026`(Factory_Import_CN): DC_EV_Import total_P=9,370(push_lotsと一致)、max_CO=1,016(有界)
  - `Cookie-jp-2026`: `push_config.csv`が空(行なし)のためStep 8は非アクティブ、影響なし
  - いずれも同種のLot_ID不一致バグが潜在していた可能性が高く、今回の修正で副次的に解消されたとみられる(これらのケースについては「修正前」の詳細な数値は取得していないため、正確なbefore/after比較はしていない)
  - `ev-europe-2026/capacity_plan.csv`に本セッションと無関係な既存データ不備(末尾に`sku_id='EVm'`のみで他列が全てNaNの壊れた行が1行)を発見。今回は対象外としてスキップ、修正は行っていない

修正ファイル: `wom/engine/push_pull.py`(Mode 4のLot再利用ロジック)。他ケースのCSV・コードは変更していない。

## GUI: PPC Financial KPIパネルがデータ0件になるバグ(2028-07-13)

GUI検証中、PPC Financial KPIパネルの表示が全項目0になる不具合が報告された。原因は`wom/gui/app.py`の`_run_ppc_from_planning(self, sc_tree)`で、PPCエンジンに渡す週リストをPlanning設定パネルの2つの独立したテキスト入力欄(週数・開始週)から正規表現で再構築していたこと。これらの欄が別ケースを開いた際の古い値のまま残っていると、実際にPlanningが使った週範囲と無関係な週レンジでPPCエンジンが実行され、ロット0件・売上0円のまま何のエラーも出さずに完了してしまう。

修正は、既にPlanningが使用した正しい週リストを保持している`sc_tree.week_labels`をそのまま使うよう変更しただけ(週数・開始週の再構築ロジックを削除)。ケース固有のバグではなく、Planning設定欄が手動でリフレッシュされていない状態でどのケースをロードしても起こり得る、汎用的なGUIバグ修正。

修正ファイル: `wom/gui/app.py`
