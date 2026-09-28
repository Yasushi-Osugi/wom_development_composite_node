# WOM Capacity Trial-02 報告書

- 文書ID：WOM-CAPACITY-TRIAL-02
- 作成日：2026-09-27
- 測定基準：`4ed2f145dfb30b95058c0d274665eca64e4fc4c4`
- 対象：`Yasushi-Osugi/wom_development_composite_node`
- 種別：読み取り・測定のみ。core、サンプルCSV原本、goldenの変更、commit/push/PRなし。
- 目的：既存の休業修正依頼が現行コードへそのまま適用可能か、その差分を確定する。実装案は本書に含めない。

## 1. 結果の要約

1. **H1は支持。** 休業適用時にsoft=686を保持すると、2027/2028-W18ともBackward S/P=686、Forward実出荷=686になる。現状のW18=0はexplicit closureを充填目標に適用した結果ではなく、softを0に上書きし、hard=0.1を整数化する経路に依存する。
2. **H2は一部支持、全モデルへの一般化は不可。** Cookie・EVのvalue=0休業週で処理が残る。SmartXのWaferFab_TWでもPが残る。iPhone等は対象週に処理・需要自体がなく、休業の効力を判定できない。
3. **H3は数値の混在を確認。** エンジンはsupply_closure.valueをcap_hardの絶対数値として読む。割合として解釈する分岐はない。各行の業務意図は未分類のまま保持した。
4. **H4の「全Lotがd−1出荷」は不成立。** -alloc/P_optでは観測された73,907 IDは全件d−1入庫だが、出荷は24,696 IDがd−1、49,211 IDがd。文書の7=6+1は「物理LT＋Bottlingバッファ」という説明であり、own ltを機械的に足す汎用契約ではない。
5. PPCの83,200 lotのうちBottling実出荷に一度も現れないIDは**9,293**。対応する計上売上は**73,461,824.00円**、粗利は**24,625,145.04円**。金額の評価変更提案は行わない。
6. 既存修正依頼は、方向性の再議論ではなく**現行差分の反映が必要な状態**。特にop_shifts/soft-envelope、Kittingの払出前判定、pushの入庫と処理の違い、診断・表示の0解釈が旧§3の記述を超えている。

## 2. 基準・方法・検証範囲

独立したLinux作業コピーを固定SHAで用いた。Python 3.12.14、依存バージョンは`raw/dependencies.txt`。Git object確認と追跡ファイル1,332件のblob一致を確認。環境・SHAは`raw/environment.json`に保存。

既存テスト：`tests/test_golden.py tests/test_step7_capacity.py tests/test_operating_calendar.py`を隔離コピーで実行し、**24 passed、skipなし**。このうちgoldenは13モデル。さらに今回の計測フック付きbaselineを同じgoldenの7区分と照合し、**91比較すべて一致**した。GUI操作とcanonical golden再生成は実施していない。

計測は**23 run、測定例外0件**。通常モデルはgolden記載のpluginセット（goldenがないモデルはsafe）、P_optはS3の実経路を使用した。需要のないケースも、結果を変えるために仮想需要を追加していない。

全runでモデルフォルダを一時コピーし、warmup生成等はコピー内だけで実行。原本の実行前後ハッシュ一致を確認。`source_hashes.json`と`copy_hashes.json`は原本とmaterialize後コピーを区別する。計測スクリプトは新規ファイルだけであり、coreへのmonkeypatchはrun終了時に復元される。

### 読み方と限界

- `backward_S/P`：BackwardPlanner.run直後、holiday post_backwardより前。
- `posthook_S/P`：post_backward後のDemand Layer。
- `forward_S/P/I/CO`：Forward終了後のSupply Layer。Sは予定列であり、actualと同義ではない。
- `actual`：ForwardPlannerの実出荷ID記録から数えた値。push baselineについてS−shortfallとの一致も確認済み。
- `fill_targets.csv`：実際のBackward局所変数cap_intをtraceで採取。判定を通らない週は空欄、skipped=True。
- `I_sum`はlot-週、P/実出荷合計はlot。COは当該ノードのSupply Layer。全チェーンCOとの混同をしない。
- 反事実は指定条件の比較であり、修正実装の受入テストではない。
- Trial-01の消失した生データを再現したと称さず、今回得たデータで独立に再測定した。

## 3. T2-1：H1反事実

### 観測

対象はsoysauce-jpy-2027-alloc。原需要とP_opt/800の両条件で、以下のW18結果は一致した。2027-W18と2028-W18の両方が同値である。

| 条件 | cap_hard | cap_soft | op_shifts | explicit | is_closed | cap_int | Backward S/P | Forward P/実出荷/I |
|---|---:|---:|---:|---|---|---:|---|---|
| baseline | 0.1 | 0 | 18 | True | False | 0 | 0 / 0 | 686 / 0 / 686 |
| soft保持 | 0.1 | 686 | 18 | True | False | 686 | 686 / 686 | 686 / 686 / 0 |

P_opt/800 baselineの近傍は、W17=P0/S686/actual0/I0、W18=P686/S0/actual0/I686、W19=P686/S686/actual686/I686。soft保持ではW17〜W19はいずれもP/S/actual=686、I=0となる。

### 原因の確認

`holiday_calendar_plugin._apply_supply_closure`の`set_capacity(..., cap_hard=val)`は、既定引数によってsoftを0へ戻す。Backwardの閉鎖判定はop_shifts==0だけで、W18の18直は閉鎖判定にならない。soft-envelopeかつcs>0が偽になり、int(0.1)=0が充填目標となる。soft保持の1変更でこの経路が変わったため、H1を支持する。

ここで「soft=0＝無制限」は厳密には**soft目標を採用せずhardへfallback**という意味。hardまで無制限になったわけではない。

全週のS/P/capacityは各runの`weekly.csv`、局所目標は`fill_targets.csv`、合計は`raw/summary/T2_1_T2_3_totals.csv`。実測値を都合のよい2週だけに限定していない。

## 4. T2-3：能力参照と既存依頼との差分

### 4.1 能力アクセサの全読取箇所

追跡対象の本番PythonからASTでcap_hard()/cap_soft()呼出を抽出。tests、.claude、Vault複製資料を除外し**22呼出**。1行ずつ以下に示す。Claudeの概数に対し、GUIは5呼出、headlessは2呼出、plan_node.summaryの2呼出も含まれる。

| ファイル:行／読取 | 0の意味 | 休業認識 | push skip | 利用先 |
|---|---|---|---|---|
| tools/run_headless_from_folder.py:385 cap_hard | 数値を保持。0の閾値判定は後段 | 知らない | pushはactual系列に切替 | planning_state_extras.capacity_series |
| tools/run_headless_from_folder.py:386 cap_soft | 同上 | 知らない | 同上 | 同上 |
| wom/engine/backward_planner.py:520 cap_hard | <=0は未設定／無制約。ただしop_shifts=0なら閉鎖 | op_shifts。explicitはこの判定では参照せず | しない | MOM Sの前倒し・P生成 |
| wom/engine/backward_planner.py:527 cap_soft | soft=0はsoft目標を使わずhardへfallback | op_shifts。epsilonはhard整数化で0 | しない | soft envelope目標と超過診断 |
| wom/engine/capacity_sealer.py:247 cap_hard | <=0は負荷率0／hard超過非判定 | 知らない | しない | Pベースの能力負荷・診断 |
| wom/engine/capacity_sealer.py:248 cap_soft | <=0はsoft超過非判定 | 知らない | しない | 同上 |
| wom/engine/capacity_sealer.py:434 cap_hard | hard<=0ではsoftを導出しない | op_shiftsに0を記録。ただしshifts=0時soft=0設定は行わない | しない | 操業直数からsoft能力導出 |
| wom/engine/forward_planner.py:475 cap_hard | hard<=0は通常P封印なし | explicit/op_shiftsを知らない。epsilonは正値としてint=0 | する | Pを切り詰め超過をCO等へ記録 |
| wom/engine/forward_planner.py:484 cap_soft | soft<=0は超過診断なし | 知らない | しない | P対softの診断 |
| wom/engine/forward_planner.py:654 cap_hard | hard<=0は候補kit数を残能力とする | 知らない | pullかつ全子Yardの分岐のみ | Kitting払出前の残能力 |
| wom/engine/harvest_batch_plugin.py:78 cap_hard | int(hard)<=0は収穫可能週から除外 | 正の整数化能力だけを見る | しない | 収穫週集合 |
| wom/engine/harvest_batch_plugin.py:94 cap_hard | 0は割当可能量0 | 同上 | しない | 収穫週割当量 |
| wom/engine/harvest_batch_plugin.py:100 cap_hard | 0は割当可能量0 | 同上 | しない | 次収穫週割当量 |
| wom/engine/holiday_calendar_plugin.py:187 cap_hard | hard<=0はdisplaced全量を置ける | explicit_closures／自身の休業rule | しない。leaf_inだけ | 休業Pを開いている週へ移動 |
| wom/engine/strategic_kpi.py:249 cap_hard | <=0はutilization対象外 | 知らない | しない | P／hard比率のKPI |
| wom/gui/app.py:1690 cap_hard | <=0は—表示。正値は小数0桁 | 知らない | しない | PSI表cap_hard／P超過色 |
| wom/gui/app.py:1691 cap_soft | <=0は—表示 | 知らない | しない | PSI表cap_soft／P超過色 |
| wom/gui/app.py:1781 cap_hard | 正値があればmaxを能力線に使用 | 知らない | しない | 旧GUI能力チャート |
| wom/gui/app.py:1782 cap_soft | 同上 | 知らない | しない | 旧GUI能力チャート |
| wom/gui/app.py:4207 cap_hard | 後段描画は<=0をNaNの隙間にする | 知らない | しない | Debugger能力線 |
| wom/model/plan_node.py:456 cap_hard | 0をそのまま返す | 知らない | しない | node.summary表示用辞書 |
| wom/model/plan_node.py:457 cap_soft | 同上 | 知らない | しない | 同上 |

0を「未設定」「診断対象外」「収穫不可」「非表示」として扱う箇所が共存している。cap_softを数値0にするだけでは、現行コードの全箇所に休業の意味が伝わるとは言えない。

PSI表でhardが0に見え、softが—になる経路も確認した。`gui/app.py:1690–1691`付近は**0.1を小数0桁で0表示**し、実値0は—表示する。したがって画面の0と内部hard=0は区別が必要。今回はGUIを起動しておらず、コードの書式と測定した0.1/0の対応を確認した。

### 4.2 旧依頼§3の項目別照合

対象：`holiday_explicit_closure_engine_request.md`（旧基準2169bf6）。

| 項目 | 判定 | 4ed2f14での状態 |
|---|---|---|
| §3.1-1 CSVを読む | 成立 | on_pre_planで読み込む。期間端が双方week mapにないruleは読込段階で除外 |
| §3.1-2 supply_closureで_apply_supply_closure | 成立 | 同経路 |
| §3.1-3 valueをhardへ書込 | 成立 | 加えてsoft既定0への上書きがH1に作用 |
| §3.1-4 config.explicit_closures構築 | 成立 | node_name→週index集合を構築 |
| §3.2 explicit_closures参照と_offset_week回避 | 成立 | offsetでは利用される |
| §3.2 MOM充填はcap<=0だけでcontinue | 変化あり | op_shifts閉鎖例外・soft-envelope分岐・soft診断が追加済み |
| §3.2 explicit MOM closureを充填0としない | 成立 | 充填内のis_closedはop_shiftsだけ |
| §3.3 post-hookはleaf_inのPだけ | 成立 | Bottling MOMを直接補正しない |
| §3.4 Forward constructorにexplicit入力なし | 成立 | calendar状態を独立に受け取らない |
| §3.4 hard>0でP封印、pushはskip | 成立 | ただしKitting残能力読取が別の箇所に追加済み |

旧依頼§5.2の概念コードをそのまま置くと、現在のsoft-envelope/op_shifts条件を表現し切れない。Kitting回復では、Assemblyの通常_process_nodeより前に部材払出の可否をhardから判定する（forward_planner.py:654）。通常P処理だけを見た旧説明では、この新たな判定境界が抜ける。

S3の処理量表示はpushをactual=S−shortfallへ変更済み。一方、旧PSI表、能力チャート、sealer/KPIにP比較が残る。表示全体が同じ系列へ統一されたという意味ではない。

### 4.3 Decision D：P停止とS停止の反事実

**観測条件を明示する。** P停止は、休業週の入庫IDを消さず、外部待ち行列として次の非休業週Pへ全量延期した。S停止は、休業週の出荷要求枠を処理時だけ空にし、処理後に予定Sを復元した。容量再平準化や後追い出荷の新機能は追加していない。

baselineは休業週S=0なので、S停止はもともと通すLotがない**非活性の比較**である。これを「将来のS封印実装も検証済み」とは扱わない。

P_opt/800、各年W18/W19：

| 条件 | W18 P/S/actual/I | W19 P/S/actual/I | Bottling全期間P・actual | I_sum | soft診断 |
|---|---|---|---:|---:|---:|
| baseline | 686/0/0/686 | 686/686/686/686 | 73,907 | 49,211 | 0 |
| P停止＋翌開週へ延期 | 0/0/0/0 | 1,372/686/686/686 | 73,907 | 47,839 | 2 |
| Sのみ停止 | 686/0/0/686 | 686/686/686/686 | 73,907 | 49,211 | 0 |

Bottlingの期末I/COは全条件0。shortfall期間合計4,802も変わらない。原需要条件でも延期によりI_sumは50,595→49,223（−1,372 lot-週）、P・actual総量75,291は不変。W19にP=1,372を集めてもpushはhard封印をskipし、soft診断だけが2件増える。

**業務判断が必要：** 休業が瓶詰・出荷処理だけを止めるのか、受入も止めるのかは、この数量差からは決めない。旧Decision Dのproduction/receipt禁止をpushへそのまま当てると、入庫時点と在庫が変わることを確認した。

さらに旧依頼§6 Test6の「closed nodeのactual shipment禁止」と、§7手動確認の「SはIで支えられる可能性」は、P停止だけから同じ期待値としては導けない。対象操作の確定が必要な文言差として残す。

## 5. T2-2：全数調査

### 5.1 カバレッジと判定規則

`supply_closure`は**91入力行**。うちモデル配下85行、旧`data/sample/holiday_calendar.csv`6行。モデルの全行を一覧へ収録し、対応週があるものを289のrule×node×week実測レコードへ展開し、週・node未一致の3記録を加えて週別CSVは292行とした。旧root sampleはHeadlessが要求するsc_tree_master.csvを持たず、独自のモデル変換を行わず**未確認**とした。

指定に合わせ、pushは実出荷、それ以外はPを処理系列とした。非ゼロがあれば「効いていない」、同一rule内でゼロ・非ゼロが混在すれば「部分的」。ゼロだけで需要・入庫・移動の機会も観測できなければ「判定不能」。活動があり処理ゼロなら数値上「効いている」。最後の判定もholidayを外した因果実験ではなく、閉鎖週のゼロという観測基準である。

入力行単位：**効いている8／効いていない28／部分的3／判定不能52**。「効いていない」は完全休業の0基準との比較であり、その行が意図する部分操業等の業務仕様を否定する分類ではない。

完全な週別表：`raw/summary/T2_2_all_weeks.csv`。holiday_name、数値原文、node_type、plan_mode、適用後hard/soft、Backward S/P、Forward P/actual、post-hook差分を保存した。以下は入力行別の期間合計であり、週値はCSVを参照する。

| モデル／holiday_id | node／type／mode | name／value | hard／soft | BW S/P合計 | FW P/actual合計 | post shift | 判定 |
|---|---|---|---|---|---|---|---|
| Cookie-jp-2026/CNY2026_Import | Factory_GP_CN/mom/pull | Chinese New Year 2026 / 0.0 | 0.0/0.0 | 1500/0 | 1500/1500 | False | 効いていない |
| Cookie-jp-2026/CNY2027_Import | Factory_GP_CN/mom/pull | Chinese New Year 2027 / 0.0 | 0.0/0.0 | 1538/0 | 1538/1538 | False | 効いていない |
| apparel-global-2028-2029/BD_LABOR_2028 | Garment_BD/mom/push | Bangladesh Garment Sector Labor Shortage (seasonal) 2028 / 700.0 | 700.0/0.0 | 1380/0 | 1380/1380 | False | 効いていない |
| apparel-global-2028-2029/BD_LABOR_2029 | Garment_BD/mom/push | Bangladesh Garment Sector Labor Shortage (seasonal) 2029 / 700.0 | 700.0/0.0 | 1380/0 | 1380/1380 | False | 効いていない |
| apparel-global-2028-2029/PT_AGOSTO_2028 | Garment_PT/mom/push | Iberian August Factory Holiday (agosto) 2028 / 400.0 | 400.0/0.0 | 800/800 | 800/800 | False | 効いていない |
| apparel-global-2028-2029/PT_AGOSTO_2029 | Garment_PT/mom/push | Iberian August Factory Holiday (agosto) 2029 / 400.0 | 400.0/0.0 | 800/800 | 800/800 | False | 効いていない |
| apparel-us-2026/CN_NEWYEAR_2026 | Factory_Import_CN/mom/pull | Chinese New Year 2026 / 1500.0 | 1500.0/0.0 | 2737/1500 | 2737/2737 | False | 部分的 |
| apparel-us-2026/CN_NEWYEAR_2027 | Factory_Import_CN/mom/pull | Chinese New Year 2027 / 1500.0 | 1500.0/0.0 | 529/0 | 529/529 | False | 部分的 |
| apparel-us-2026/ES_AGOSTO_2026 | Factory_Local_ES/mom/pull | Spain August Factory Holiday (agosto) 2026 / 1500.0 | 1500.0/0.0 | 3000/3000 | 3000/3000 | False | 部分的 |
| apparel-us-2026/ES_AGOSTO_2027 | Factory_Local_ES// | Spain August Factory Holiday (agosto) 2027 / 1500.0 | / | 未測定 | 未測定 | 未確認 | 判定不能 |
| ev-europe-2026/KASSEL_MAINT_2026 | Factory_Local_DE/mom/pull | Kassel Factory Maintenance 2026 / 0.0 | 0.0/0.0 | 500/0 | 500/500 | False | 効いていない |
| ev-europe-2026/KASSEL_MAINT_2027 | Factory_Local_DE/mom/pull | Kassel Factory Maintenance 2027 / 0.0 | 0.0/0.0 | 500/0 | 500/500 | False | 効いていない |
| ev-europe-2026/HU_SUMMER_2026 | Factory_Import_HU/mom/push | Hungary Summer Shutdown 2026 / 0.0 | 0.0/0.0 | 200/0 | 200/200 | False | 効いていない |
| ev-europe-2026/HU_SUMMER_2027 | Factory_Import_HU/mom/push | Hungary Summer Shutdown 2027 / 0.0 | 0.0/0.0 | 110/0 | 110/110 | False | 効いていない |
| ev-thailand-2026/RAYONG_MAINT_2026 | Factory_Local_TH/mom/pull | Rayong Factory Maintenance 2026 / 0.0 | 0.0/0.0 | 500/0 | 500/500 | False | 効いていない |
| ev-thailand-2026/RAYONG_MAINT_2027 | Factory_Local_TH/mom/pull | Rayong Factory Maintenance 2027 / 0.0 | 0.0/0.0 | 500/0 | 500/500 | False | 効いていない |
| ev-thailand-2026/GOLDEN_WEEK_2026 | Factory_Import_CN/mom/push | Shanghai Golden Week 2026 / 0.0 | 0.0/0.0 | 221/0 | 230/221 | False | 効いていない |
| ev-thailand-2026/GOLDEN_WEEK_2027 | Factory_Import_CN/mom/push | Shanghai Golden Week 2027 / 0.0 | 0.0/0.0 | 221/0 | 230/221 | False | 効いていない |
| ev-thailand-2026_update/RAYONG_MAINT_2026 | Factory_Local_TH/mom/pull | Rayong Factory Maintenance 2026 / 150 | 150.0/0.0 | 150/150 | 150/150 | False | 効いていない |
| ev-thailand-2026_update/RAYONG_MAINT_2027 | Factory_Local_TH/mom/pull | Rayong Factory Maintenance 2027 / 150 | 150.0/0.0 | 150/150 | 150/150 | False | 効いていない |
| ev-thailand-2026_update/GOLDEN_WEEK_2026 | Factory_Import_CN/mom/push | Shanghai Golden Week 2026 / 5 | 5.0/0.0 | 10/10 | 210/10 | False | 効いていない |
| ev-thailand-2026_update/GOLDEN_WEEK_2027 | Factory_Import_CN/mom/push | Shanghai Golden Week 2027 / 5 | 5.0/0.0 | 10/10 | 210/10 | False | 効いていない |
| sample/CNY_2027 | MOM_China// | 春節2027（工場閉鎖） / 0.0 | / | 未測定 | 未測定 | 未確認 | 判定不能 |
| sample/CNY_2027 | Supplier_CN// | 春節2027（工場閉鎖） / 0.0 | / | 未測定 | 未測定 | 未確認 | 判定不能 |
| sample/GW_2027 | DAD_Japan// | GW2027（物流停滞） / 0.3 | / | 未測定 | 未測定 | 未確認 | 判定不能 |
| sample/CNY_2028 | MOM_China// | 春節2028（工場閉鎖） / 0.0 | / | 未測定 | 未測定 | 未確認 | 判定不能 |
| sample/CNY_2028 | Supplier_CN// | 春節2028（工場閉鎖） / 0.0 | / | 未測定 | 未測定 | 未確認 | 判定不能 |
| sample/GW_2028 | DAD_Japan// | GW2028（物流停滞） / 0.3 | / | 未測定 | 未測定 | 未確認 | 判定不能 |
| iphone_global/CNY_2027 | SiliconWafer_TW/leaf_in/pull | 春節2027（TSMC工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/CNY_2027 | SiliconWafer_TW_i15/leaf_in/pull | 春節2027（TSMC工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/CNY_2027 | SiliconWafer_TW_i17/leaf_in/pull | 春節2027（TSMC工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/CNY_2028 | SiliconWafer_TW/leaf_in/pull | 春節2028（TSMC工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/CNY_2028 | SiliconWafer_TW_i15/leaf_in/pull | 春節2028（TSMC工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/CNY_2028 | SiliconWafer_TW_i17/leaf_in/pull | 春節2028（TSMC工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/CNY_2029 | SiliconWafer_TW/leaf_in/pull | 春節2029（TSMC工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/CNY_2029 | SiliconWafer_TW_i15/leaf_in/pull | 春節2029（TSMC工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/CNY_2029 | SiliconWafer_TW_i17/leaf_in/pull | 春節2029（TSMC工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/DIWALI_2027 | BoschSensor_IN/leaf_in/pull | ディワリ2027（インド工場閉鎖） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/DIWALI_2028 | BoschSensor_IN/leaf_in/pull | ディワリ2028（インド工場閉鎖） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| iphone_global/DIWALI_2029 | BoschSensor_IN/leaf_in/pull | ディワリ2029（インド工場閉鎖） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| oil-global-2027/Refinery_Local_Maint_2027 | Refinery_Local/mom/pull | Refinery Local Scheduled Maintenance 2027 / 30.0 | 30.0/0.0 | 60/60 | 60/60 | False | 効いていない |
| oil-global-2027/Hormuz_Strait_Closure_2027 | Refinery_Local_H/mom/pull | Hormuz Strait Closure - Permanent Route Diversion / 1.0 | 1.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| oil-global-2027/Refinery_EU_Strike_2027 | Refinery_EU/mom/pull | Refinery EU Labor Strike 2027 / 25.0 | 25.0/0.0 | 75/75 | 75/75 | False | 効いていない |
| oil-global-2027/Refinery_USGulf_Hurricane_2027 | Refinery_USGulf/mom/pull | Gulf Coast Hurricane Shutdown 2027 / 45.0 | 45.0/0.0 | 90/90 | 90/90 | False | 効いていない |
| oil-global-2027/OPEC_Plus_Cut_2027_Local | Refinery_Local/mom/pull | OPEC+ Coordinated Production Cut (Local crude feed) / 500.0 | 500.0/0.0 | 3000/3000 | 3000/3000 | False | 効いていない |
| oil-global-2027/OPEC_Plus_Cut_2027_EU | Refinery_EU/mom/pull | OPEC+ Coordinated Production Cut (EU crude feed) / 500.0 | 500.0/0.0 | 3000/3000 | 3000/3000 | False | 効いていない |
| oil-global-2027/US_Shale_Swing_2027 | Refinery_USGulf/mom/pull | Non-OPEC+ Shale Swing Producer Response (ramp-up) / 1000.0 | 1000.0/0.0 | 7873/7000 | 7873/7873 | False | 効いていない |
| rice-japan-2027-2028/GW_2027_supply | DC_Higashi/dad/pull | GW2027（物流停滞） / 0.3 | 0.3/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/GW_2027_supply | DC_Nishi/dad/pull | GW2027（物流停滞） / 0.3 | 0.3/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/GW_2027_supply | Seihaku_E/dad/pull | GW2027（物流停滞） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/GW_2027_supply | Seihaku_W/dad/pull | GW2027（物流停滞） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/OBON_2027_supply | DC_Higashi/dad/pull | お盆2027（物流停滞） / 0.4 | 0.4/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/OBON_2027_supply | DC_Nishi/dad/pull | お盆2027（物流停滞） / 0.4 | 0.4/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/NEWYEAR_2027_supply | DC_Higashi/dad/pull | 年末年始2027（停滞） / 0.2 | 0.2/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/NEWYEAR_2027_supply | DC_Nishi/dad/pull | 年末年始2027（停滞） / 0.2 | 0.2/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/GW_2028_supply | DC_Higashi/dad/pull | GW2028（物流停滞） / 0.3 | 0.3/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/GW_2028_supply | DC_Nishi/dad/pull | GW2028（物流停滞） / 0.3 | 0.3/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/GW_2028_supply | Seihaku_E/dad/pull | GW2028（物流停滞） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/GW_2028_supply | Seihaku_W/dad/pull | GW2028（物流停滞） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/OBON_2028_supply | DC_Higashi/dad/pull | お盆2028（物流停滞） / 0.4 | 0.4/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/OBON_2028_supply | DC_Nishi/dad/pull | お盆2028（物流停滞） / 0.4 | 0.4/0.0 | 0/0 | 0/0 | False | 判定不能 |
| rice-japan-2027-2028/NEWYEAR_2028_supply | DC_Higashi// | 年末年始2028（停滞） / 0.2 | / | 未測定 | 未測定 | 未確認 | 判定不能 |
| rice-japan-2027-2028/NEWYEAR_2028_supply | DC_Nishi// | 年末年始2028（停滞） / 0.2 | / | 未測定 | 未測定 | 未確認 | 判定不能 |
| smartx-2027-2029/CNY_2027 | WaferFab_TW/leaf_in/push_sub | 春節2027（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 2298/2298 | False | 効いていない |
| smartx-2027-2029/CNY_2027 | WaferFab_TW_g1/leaf_in/pull | 春節2027（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/CNY_2027 | WaferFab_TW_g3/leaf_in/pull | 春節2027（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/CNY_2028 | WaferFab_TW/leaf_in/push_sub | 春節2028（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 1802/1802 | False | 効いていない |
| smartx-2027-2029/CNY_2028 | WaferFab_TW_g1/leaf_in/pull | 春節2028（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/CNY_2028 | WaferFab_TW_g3/leaf_in/pull | 春節2028（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/CNY_2029 | WaferFab_TW/leaf_in/push_sub | 春節2029（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 755/755 | False | 効いていない |
| smartx-2027-2029/CNY_2029 | WaferFab_TW_g1/leaf_in/pull | 春節2029（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/CNY_2029 | WaferFab_TW_g3/leaf_in/pull | 春節2029（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/DIWALI_2027 | SensorIN/leaf_in/pull | ディワリ2027（インド工場閉鎖） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/DIWALI_2028 | SensorIN/leaf_in/pull | ディワリ2028（インド工場閉鎖） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/DIWALI_2029 | SensorIN/leaf_in/pull | ディワリ2029（インド工場閉鎖） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/CNY_2026 | WaferFab_TW/leaf_in/push_sub | 春節2026（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 2700/2700 | False | 効いていない |
| smartx-2027-2029/CNY_2026 | WaferFab_TW_g1/leaf_in/pull | 春節2026（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/CNY_2026 | WaferFab_TW_g3/leaf_in/pull | 春節2026（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/DIWALI_2026 | SensorIN/leaf_in/pull | ディワリ2026（インド工場閉鎖） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/CNY_2030 | WaferFab_TW/leaf_in/push_sub | 春節2030（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/CNY_2030 | WaferFab_TW_g1/leaf_in/pull | 春節2030（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/CNY_2030 | WaferFab_TW_g3/leaf_in/pull | 春節2030（FoundryTW工場閉鎖） / 0.0 | 0.0/0.0 | 0/0 | 0/0 | False | 判定不能 |
| smartx-2027-2029/DIWALI_2030 | SensorIN/leaf_in/pull | ディワリ2030（インド工場閉鎖） / 0.5 | 0.5/0.0 | 0/0 | 0/0 | False | 判定不能 |
| soysauce-eu-2027/GW_2027 | Bottling_Noda/mom/push | Japan Golden Week factory closure 2027 / 0.1 | 0.1/0.0 | 0/0 | 1000/0 | False | 効いている |
| soysauce-eu-2027/GW_2028 | Bottling_Noda/mom/push | Japan Golden Week factory closure 2028 / 0.1 | 0.1/0.0 | 0/0 | 1000/0 | False | 効いている |
| soysauce-jpy-2027/GW_2027 | Bottling_Noda/mom/push | Japan Golden Week factory closure 2027 / 0.1 | 0.1/0.0 | 0/0 | 1000/0 | False | 効いている |
| soysauce-jpy-2027/GW_2028 | Bottling_Noda/mom/push | Japan Golden Week factory closure 2028 / 0.1 | 0.1/0.0 | 0/0 | 1000/0 | False | 効いている |
| soysauce-jpy-2027-alloc/GW_2027 | Bottling_Noda/mom/push | Japan Golden Week factory closure 2027 / 0.1 | 0.1/0.0 | 0/0 | 686/0 | False | 効いている |
| soysauce-jpy-2027-alloc/GW_2028 | Bottling_Noda/mom/push | Japan Golden Week factory closure 2028 / 0.1 | 0.1/0.0 | 0/0 | 686/0 | False | 効いている |
| soysauce-us-2027/GW_2027 | Bottling_Noda/mom/push | Japan Golden Week factory closure 2027 / 0.1 | 0.1/0.0 | 0/0 | 1000/0 | False | 効いている |
| soysauce-us-2027/GW_2028 | Bottling_Noda/mom/push | Japan Golden Week factory closure 2028 / 0.1 | 0.1/0.0 | 0/0 | 1000/0 | False | 効いている |

### 5.2 H2/H3の観測と限界

- CookieのFactory_GP_CNはvalue=0でも対象期間P=1,500 / 1,538。EV Europe・Thailandにも0値のMOM休業週で非ゼロ処理が残る。
- SmartXのWaferFab_TW（leaf_in）はvalue=0でも、2026/2027/2028/2029春節対象期間P=2,700 / 2,298 / 1,802 / 755。対応するBackward Pは0でpost-hook移動差分も0。`push_pull.py:304–355`でpost-copy後にMode4がleaf Pを作り直す経路と整合する。post_backwardのP処理だけで最終Forward Pの閉鎖を保証できない。
- iPhoneの対象leaf等はP=0だが当該週に活動がなく、閉鎖による効果とは認定しない。今回対象行でpost_backwardの非ゼロP移動は観測されなかった。「leafなら一部効く」は静的に可能でも、この測定で実証したとはしない。
- Riceの0.3等は浮動小数の絶対hardとして入り、通常P封印ならintで0になる。ただし対象週の実測処理がもともと0であるため、数値だけから「0.3倍操業」を実装している／正しく機能しているとは判定しない。
- H3で列挙された以外に0.2、0.4、0.5、5、25、45、400、500、1000も存在する。値の全一覧は入力CSVの列挙を保持し、用途の分類はしていない。

**履歴の訂正：** 依頼文の「2fc7f4bで4モデルを1500から0.1へ」は正確には3モデル（EU、JPY、alloc）。USは同commit以前から0.1。現在4モデル×2行が0.1であることは確認。実際のdiffを`raw/reference_documents/2fc7f4b_data_diff.txt`に保存した。

## 6. T2-4：Mode4の週位置

### 観測

push_configを持つ14モデルフォルダのうち、5フォルダはヘッダのみ。設定行がある9フォルダ10ノードを全て測定。下表は原需要baseline、-alloc/P_optは追記行。経路LTはleafから対象pushノードへの**対象自身を除く**transit（0の場合lt代用）の合計。EV Europeは3部材経路なので範囲表示。own_ltは別列に置いた。

| モデル | product/node | push LT | 経路LT | own lt | 入庫 offset:件数 | 出荷 offset:件数 |
|---|---|---|---|---|---|---|
| apparel-global-2028-2029 | Apparel_Offshore/Garment_BD | 8 | 8 | 4 | 0:83,586, not_observed:4,657 | 0:83,586, not_observed:4,657 |
| apparel-global-2028-2029 | Apparel_Vertical/Garment_PT | 3 | 3 | 1 | 0:90,696, not_observed:1,840 | 0:90,696, not_observed:1,840 |
| ev-europe-2026 | EVmaker_Import/Factory_Import_HU | 4 | 2,3 | 3 | 0:7,945, not_observed:400 | 0:7,945, not_observed:400 |
| ev-thailand-2026 | EVmaker_Import/Factory_Import_CN | 4 | 2 | 3 | -2:9,370, not_observed:400 | -1:3,119, -2:6,251, not_observed:400 |
| ev-thailand-2026_update | EVmaker_Import/Factory_Import_CN | 4 | 2 | 3 | -2:10,540 | 0:10,540 |
| smartx-2027-2029 | SmartXPro_CN/Buffer_Chip_TW | 39 | 1 | 0 | -38:160,146 | 0:160,146 |
| soysauce-eu-2027 | Soy_Sauce/Bottling_Noda | 7 | 6 | 1 | -1:85,575, not_observed:6,962 | -1:10,000, 0:75,575, not_observed:6,962 |
| soysauce-jpy-2027-alloc | Soy_Sauce/Bottling_Noda | 7 | 6 | 1 | -1:75,291, not_observed:4,802 | -1:24,696, 0:50,595, not_observed:4,802 |
| soysauce-jpy-2027 | Soy_Sauce/Bottling_Noda | 7 | 6 | 1 | -1:100,501 | 0:100,501 |
| soysauce-us-2027 | Soy_Sauce/Bottling_Noda | 7 | 6 | 1 | -1:85,750, not_observed:6,962 | -1:10,000, 0:75,750, not_observed:6,962 |
| soysauce-jpy-2027-alloc / P_opt | Soy_Sauce/Bottling_Noda | 7 | 6 | 1 | -1:73,907, not_observed:4,802 | -1:24,696, 0:49,211, not_observed:4,802 |

`not_observed`はその対象ノードのDemand SにあるIDが、全観測期間のPまたはactualに現れないこと。全体需要の欠落数とは同義ではない。各経路のlt/transit/ssは`T2_4_paths.json`、ID別週位置は各runの`lot_timing.csv`にある。

- -alloc/P_opt：入庫d−1=73,907、未観測4,802。出荷d−1=24,696、d=49,211、未観測4,802。
- -alloc原需要：入庫d−1=75,291、未観測4,802。出荷d−1=24,696、d=50,595。
- JPY非alloc：出荷100,501全件がd。LT差が1でも出荷が全件d−1とはならない。

### 文書の引用とH4

`docs/design/push_production_lead_time.md` §3は「供給側が、将来需要Lotを何週前から準備するか」と定義。§4は以下の解釈を記す。

```text
Physical LT 6 weeks
＋ Bottling_Noda buffer 1 week
＝ Push Lead Time 7 weeks
```

`holiday_calendar_push_lead_time_and_planning_horizon.md`の§9.2にも上記と同じ6＋1＝7の説明がある。両資料とも、今回参照範囲では**push_lead_time_weeksへnode自身のltフィールドを必ず含めるという汎用定義はない**。

**原因解釈：** Bottlingで7−6=1は早期入庫と整合する。ただしown_lt=1とbuffer=1の数値一致だけで、own_ltを合算する仕様とは断定できない。pushのForwardは到着した物を当週出荷可能だが、週の出荷量枠によりIへ残ることがある。H4の前半はこのケースの数値関係として整合、後半の「全Lot」は観測に反する。

## 7. T2-5：E2E未供給とPPC（数値）

### 7.1 期間

planning_config.csvは`warmup_lt=26`、`planning_start`空欄。独立したreport_start/report_end設定はない。計画期間は2026-W28〜2028-W52の130週。PPC計上の実際の市場週範囲は2027-W01〜2028-W52（104週）。本節の「報告期間」は後者の**実際の計上範囲**を指し、独立した設定値があるとはしない。

| 集合 | 件数 | Bottling側の位置 | 対応する市場週 | 報告範囲内／外 |
|---|---:|---|---|---|
| Backward past_due | 4,491 | 2026-W28より前へ繰戻せず記録 | 2028-W24〜W52 | 4,491／0 |
| Mode4境界 | 4,802 | Demand Sが2026-W28〜W34、対応P/actual未観測 | 2027-W49〜2028-W30 | 4,802／0 |
| 合計 | 9,293 | 前二集合はIDで排他的 | 上記 | 9,293／0 |

Mode4の4,802はBottling要求週で見ればwarmup内だが、そのLot_IDが表す市場要求は報告期間内。Backwardの4,491も「期間前で起きたから市場報告の対象外」とはならない。ID別対応を`unshipped_market_ids.csv`に保存した。

### 7.2 金額

PPCは市場のproduct×channel×weekを624レコードへ集約し、qty合計83,200（このモデルcpu_size=1）を計上。83,200はPSI Lot数と同じだが、PPCの`total_lots`フィールドそのものは624である。

| 集合 | PSI Lot_ID件数 | 売上 JPY | 粗利 JPY |
|---|---:|---:|---:|
| Backward past_due由来 | 4,491 | 35,598,320.00 | 12,180,770.80 |
| Mode4境界由来 | 4,802 | 37,863,504.00 | 12,444,374.24 |
| Bottling実出荷なし計 | **9,293** | **73,461,824.00** | **24,625,145.04** |
| PPC計上全体 | 83,200 | 548,550,508.00 | 165,007,343.19 |

算定：元IDを市場product/channel/weekへ結び、`ppc_lot_reconciliation.csv`の同一集約行の単位売上・単位粗利を適用した。PPC台帳が元IDごとのイベントを保持しているわけではない。同一集約行は同一単価であり、数量比例の対応額である。全624行のqty×単位額の合計をKPI全体へ照合し、浮動小数丸めの範囲で一致。上表は小数2桁、未丸め数値とID別金額はJSON/CSVに保存した。

金額の正否の評価、利益の補正提案、実装提案は行わない。

## 8. 未確認・業務判断・終了

### 未確認として残す項目

- 旧root sampleの6行はモデル定義不足で未実行。期間外・存在しないnode・活動がない行の因果的な休業効果も未確認。入力と理由は全数表へ記載。
- S停止は今回の自然baselineでは非活性。処理が正の週へS停止を追加する別ストレステストは実施していない。
- 休業なし対照を全モデルへ追加する因果検査、Windows GUI、修正後engineの検証は今回の範囲外。
- raw CSVにあるvalueの業務分類は実施していない。表示名だけを根拠に「割合」「部分操業」を確定していない。

### 大杉さんの判断を必要とする境界

合意済みのhard/softの意味、休業を状態で表す方針、epsilonを本番仕様にしない方針は再議論しない。そのうえで、旧Decision Dが対象とする操作をpushの受入にも適用するか、当該ノードの処理・出荷だけかは未確定として残す。その他モデルのholiday.valueの業務分類も測定では決めない。

T2-1〜T2-5の検査はここで終了する。修正Request Letterや実装は作成しない。

## 9. 再実行・成果物

同じリポジトリの固定SHA独立コピーへ`tools/probe_capacity_trial02.py`を配置し、適合確認済みの環境で実行する。別SHAならスクリプトは停止する。既存成果物を混ぜないよう、新しい出力先を指定する。

```bash
python -m tools.probe_capacity_trial02 --out ../trial02_raw_new --phase priority
python -m tools.probe_capacity_trial02 --out ../trial02_raw_new --phase survey
python -m tools.probe_capacity_trial02 --out ../trial02_raw_new --phase summarize
```

priority=8 run、survey=15 run。summarizeは保存済み出力から集計・金額照合・完全性検査を行い、モデルを再実行しない。本書の読取箇所への解説・旧設計との比較は静的レビューで追記したもの。環境適合pytestログは測定スクリプト外の手順として保存した。最終スクリプトには測定後に追加した集計phaseが含まれるが、測定処理本体は同一である。

各runにはsnapshot、週別PSI、fill target、実出荷IDの時点対応、PPC出力、介入記録、原本ハッシュを収録。巨大な全文をチャットへ貼らずZIPへ集約した。

## 10. ファイルハッシュ（SHA-256）

以下は本書自身を除く同梱ファイルのハッシュ。自己参照を避け、本書と全ファイルの検証値は別添`SHA256SUMS.txt`にも記載する（manifest自身は対象外）。ZIPのCRC検査とmanifest照合も実施した。

| ファイル | SHA-256 |
|---|---|
| raw/Cookie-jp-2026__original__baseline/closure_weeks.csv | 655b116954e694f82dbf068609d6ac1f5f9ee0361b8d52109aa1f496155e613b |
| raw/Cookie-jp-2026__original__baseline/completion.json | fd9de4b982184c8a8f1872f209a9178776e1cc405112b49d8122c9f2c5a1d39b |
| raw/Cookie-jp-2026__original__baseline/copy_hashes.json | 02d616d2f56fbaf14e3cef438adecf89fc2679451f31cd4304894a069edc1a63 |
| raw/Cookie-jp-2026__original__baseline/events.json | 03cd34b3d0480871c5710c333a6fc6b0792c5c0870fa81bfff3ca7104a0ec88d |
| raw/Cookie-jp-2026__original__baseline/fill_targets.csv | 5d39b9004f9e78b09f0294781f837b91a3a5184dc907859aea1ab6dba1c2a3e9 |
| raw/Cookie-jp-2026__original__baseline/holiday_calendar.csv | bacb71bb412cee34c3807edbb3b46c8f78cf30a14006256ec6b7f301f7687ca8 |
| raw/Cookie-jp-2026__original__baseline/lot_timing.csv | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| raw/Cookie-jp-2026__original__baseline/paths.json | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
| raw/Cookie-jp-2026__original__baseline/ppc/ppc_event_ledger.csv | 59c672695be8dd67159a76336ca83bdfe1ffb1cf3b92b25ddda3f74d91e7bf98 |
| raw/Cookie-jp-2026__original__baseline/ppc/ppc_kpi_summary.json | e66410182e0ebb7b53bd700f3f1239db9acc0a13f6add4591afcbdb8a429dce5 |
| raw/Cookie-jp-2026__original__baseline/ppc/ppc_lot_reconciliation.csv | 97590b068380e9dd600b9fdbc85f842bc4ba5dc2f272e38de8043635b0f0745a |
| raw/Cookie-jp-2026__original__baseline/ppc/ppc_node_pl_summary.csv | a1c19276e543cfba7115090ea2e55290005b0924486fdc01ca693e2542ea8faf |
| raw/Cookie-jp-2026__original__baseline/ppc/ppc_node_week_summary.csv | 25dd2dbe5503896f09099403809d293f28a2f9f53e49bec3d82d764733f30e6d |
| raw/Cookie-jp-2026__original__baseline/ppc/ppc_profit_zone_summary.csv | ab26db93e3910539f6fda45e17871d8996d01afbf3566e1c36dfced5aaec9950 |
| raw/Cookie-jp-2026__original__baseline/push_config.csv | bdeb581e04b54f3d769963fffde6b78280535ec72c0e28485153acc4159b7871 |
| raw/Cookie-jp-2026__original__baseline/run.log | 3852e29d9a61240b30f3c78ebfb48fe7256660bfa91fd10412c724322f962b1f |
| raw/Cookie-jp-2026__original__baseline/sc_tree_master.csv | 11b25041257b7d06547d99b77530cc7089f32ce63cc6ca668400571d3bceb31e |
| raw/Cookie-jp-2026__original__baseline/snapshot.json | a65ea7f8c4fc9c9d0ef25ff9dd0bf956819d123c7939573efd189cb8353be208 |
| raw/Cookie-jp-2026__original__baseline/source_hashes.json | 02d616d2f56fbaf14e3cef438adecf89fc2679451f31cd4304894a069edc1a63 |
| raw/Cookie-jp-2026__original__baseline/weekly.csv | 341c18bccfa577c7d447bd61671d5ef5ecdb4271a0c71f40d3dee1123459e623 |
| raw/all_closure_input_rows.csv | 73a882a0da8091677ae01a7e1993370e3417310cfa6f6989380758db188490fd |
| raw/apparel-global-2028-2029__original__baseline/closure_weeks.csv | 504b2a381076f058e70a047567f32e66447b061cf78cc2db98dd26ddf7887b9e |
| raw/apparel-global-2028-2029__original__baseline/completion.json | a84ca94ba5f626baf4b224c2213e52337002475183976a6bdde61c259b65b8dd |
| raw/apparel-global-2028-2029__original__baseline/copy_hashes.json | 66c63a7bd4f68ea04f09e5a31968daa56073eb31cec3f23fa07e0a0ad1d69574 |
| raw/apparel-global-2028-2029__original__baseline/events.json | 8c046114744bf553e879dfd4f3dc47d20b2c9ed21197310094b2518096aed341 |
| raw/apparel-global-2028-2029__original__baseline/fill_targets.csv | 1b9d84d16f23e7c3a251b79738852eeb70aef28e98d105380e4d0fd855ed299f |
| raw/apparel-global-2028-2029__original__baseline/holiday_calendar.csv | 6c52fc47aaed2b239c211473bf04f6df367d7692aa07509b75e0ba4d1a9a4155 |
| raw/apparel-global-2028-2029__original__baseline/lot_timing.csv | dbd2f3a5eacc519913a508cb188524b6ec7f6ee3631e5afae419f46905dd385d |
| raw/apparel-global-2028-2029__original__baseline/paths.json | 554b235e3432840ffbe6a4062131004ada1a7f4ab482752e9dda237e9f5633b6 |
| raw/apparel-global-2028-2029__original__baseline/ppc/ppc_event_ledger.csv | 298952b02664dc1a2ccd4f704705c53ecf85fe9fa7660c5735498aefbce18acf |
| raw/apparel-global-2028-2029__original__baseline/ppc/ppc_kpi_summary.json | c98fd306ca844e23513a080d17f2e3d72ad6f855a96c05d3b11dc0224f93ec28 |
| raw/apparel-global-2028-2029__original__baseline/ppc/ppc_lot_reconciliation.csv | c4b6591f6ad5abe2b89d8ed2041ef6155cebfda1cf6f8a53eb8faa7ca48c2e8b |
| raw/apparel-global-2028-2029__original__baseline/ppc/ppc_node_pl_summary.csv | 8c06a8b762bfb1265314207beae1a112edc7302f00dc776264175b806c67d7b9 |
| raw/apparel-global-2028-2029__original__baseline/ppc/ppc_node_week_summary.csv | 567cd4e2c9862812f2ff51d57a0d2342bc57d90f5eb5c7d936e156841f7aff42 |
| raw/apparel-global-2028-2029__original__baseline/ppc/ppc_profit_zone_summary.csv | 2079131f977e02d9ab9d73bcf035a1acba51168b131015f1073f2faa35edbea4 |
| raw/apparel-global-2028-2029__original__baseline/push_config.csv | e005f430d3ed1598a2d9775994182ab0bff409dec0f64cf533c9a8f85e6ba7c9 |
| raw/apparel-global-2028-2029__original__baseline/run.log | 198f6aba9c7465205bdd283b4dcbec97a4be3c2987eedfca779743e472db454d |
| raw/apparel-global-2028-2029__original__baseline/sc_tree_master.csv | 2cd018d3ce20d7515a1fb2a2ae479d031c4a4841b3666511165e5edbd50ecf2e |
| raw/apparel-global-2028-2029__original__baseline/snapshot.json | 6d999568f6fb03e7a599a8bd03324da002a21d65f84023ad96b45f988d50da8d |
| raw/apparel-global-2028-2029__original__baseline/source_hashes.json | 66c63a7bd4f68ea04f09e5a31968daa56073eb31cec3f23fa07e0a0ad1d69574 |
| raw/apparel-global-2028-2029__original__baseline/weekly.csv | 7cd787158bf52d378e528f853d9aaf4a9347a6d55d7bde057d8cfac38e14674f |
| raw/apparel-us-2026__original__baseline/closure_weeks.csv | 5b64bcc43bc21663278424c09c153d545cc706da784d8b2a566927a79646860e |
| raw/apparel-us-2026__original__baseline/completion.json | 6675b32c0bcc59ea691b428831394df0cb507da354e2aaae4d73cf566c339c69 |
| raw/apparel-us-2026__original__baseline/copy_hashes.json | a225de11738d896b0c64f3bebc36bea4fe70c1e916b42486cfa1dd642f7cc004 |
| raw/apparel-us-2026__original__baseline/events.json | ade54d102de0fadd48b6456b38bcffad8144bb4776e64c921b5f5cd5b03c6042 |
| raw/apparel-us-2026__original__baseline/fill_targets.csv | 437d84fc93ea689e08330712155a223c31b6e27cee864237fa7de7fd5aa95015 |
| raw/apparel-us-2026__original__baseline/holiday_calendar.csv | 30c1ce2f2d945253d0172dee6d6374d6033c122456a5f6169aba4120efcc24af |
| raw/apparel-us-2026__original__baseline/lot_timing.csv | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| raw/apparel-us-2026__original__baseline/paths.json | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
| raw/apparel-us-2026__original__baseline/planning_config.csv | 2af342970585e91f480b562183ffa66139efdd19d12a33e8710dfd947cda055a |
| raw/apparel-us-2026__original__baseline/ppc/ppc_event_ledger.csv | 1e9c36a168d5870a2fa0e4130fda40dddc14d8c52568063d93b84239f6f155c9 |
| raw/apparel-us-2026__original__baseline/ppc/ppc_kpi_summary.json | dac4ab82f3e8592e9480c8dbe4564c302dfefd9dd39beed675518c518f5df599 |
| raw/apparel-us-2026__original__baseline/ppc/ppc_lot_reconciliation.csv | 1b2f5125f09a9534a2346250e5a541fe1561d4eb4c3232ec15c20800d4eeccc0 |
| raw/apparel-us-2026__original__baseline/ppc/ppc_node_pl_summary.csv | 8402a51e83eb7f3a48502229f3ad293e549fa92257d0fb06980aaa31b19cf5e3 |
| raw/apparel-us-2026__original__baseline/ppc/ppc_node_week_summary.csv | 8776e4ca5dde66c1ce920bbd3aade0df8844775af840edd22f88649631623ed8 |
| raw/apparel-us-2026__original__baseline/ppc/ppc_profit_zone_summary.csv | abdaaf7b85c3b6a575805d195aa320875b49ef48b05390bcc9640ead69c63ad4 |
| raw/apparel-us-2026__original__baseline/run.log | 5fe9ead1a6e6a853ab0b3c78590f7776e8fda9a249f91e3a12e9b9589d39fbf0 |
| raw/apparel-us-2026__original__baseline/sc_tree_master.csv | b79ba6fee398edd73266a885590b5bcf0130a6edc9446b0aab80ceca6cee0e49 |
| raw/apparel-us-2026__original__baseline/snapshot.json | 7fd484bfb0de6950fabea95565c3d5319f601d2d044b52a59a1bd6b097201b1f |
| raw/apparel-us-2026__original__baseline/source_hashes.json | a225de11738d896b0c64f3bebc36bea4fe70c1e916b42486cfa1dd642f7cc004 |
| raw/apparel-us-2026__original__baseline/weekly.csv | e49bf12a874cd463556f0b8c1ead896babe15dd2d6d91a3997459d89d8ccd4d6 |
| raw/bom-test-2026__original__baseline/closure_weeks.csv | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| raw/bom-test-2026__original__baseline/completion.json | bfd451978aa7ce00eee12c082baf7839b225407242af281aec0d17318a4296c2 |
| raw/bom-test-2026__original__baseline/copy_hashes.json | 62ca627b01be1742837f0df4f2b7a4863a61bce0336835c3721462595a6edaae |
| raw/bom-test-2026__original__baseline/events.json | e4198bacca53cf01258bfd42ed711ab98e273f07da5fc43373dce0a0050eaf44 |
| raw/bom-test-2026__original__baseline/fill_targets.csv | 771f72f9cb2b4c113f3655e1340abadf3381a4ec6ea5395103ba361a7ed16391 |
| raw/bom-test-2026__original__baseline/holiday_calendar.csv | c565da43fa129415316f3d4011675799222b7fc45c461355096c7dc1ae06f87b |
| raw/bom-test-2026__original__baseline/lot_timing.csv | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| raw/bom-test-2026__original__baseline/paths.json | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
| raw/bom-test-2026__original__baseline/planning_config.csv | ef77d3da6ab22ae9c4dece296a6333d2a7bc56746fed3b3d1d6c6fd39aa82d06 |
| raw/bom-test-2026__original__baseline/ppc/ppc_event_ledger.csv | f94e7dfe2ace5474cd44f5ece7f19f3e0ab13d6f2c656fd36b6bb27f282a4006 |
| raw/bom-test-2026__original__baseline/ppc/ppc_kpi_summary.json | ecbe26c4d4335d96b57fd545939043a8a8cc320db5f01e74b34c59dd2de68440 |
| raw/bom-test-2026__original__baseline/ppc/ppc_lot_reconciliation.csv | 2febf5edaafe0641649d234275e943dfb07888bbbcf3406027eb4378c26d6956 |
| raw/bom-test-2026__original__baseline/ppc/ppc_node_pl_summary.csv | ac72f74fc5374a83ce69b9e14720664d8a1b9ac8060c5d541a9423c951a7c914 |
| raw/bom-test-2026__original__baseline/ppc/ppc_node_week_summary.csv | 5378d4fd442e8ffbaf32e9980f3709f62d55c5fc06b6078dd60716465b4b27e7 |
| raw/bom-test-2026__original__baseline/ppc/ppc_profit_zone_summary.csv | 0a614aada04732862c10ee48b79fe81283ea319d5f95329d2445ae4ed6743827 |
| raw/bom-test-2026__original__baseline/push_config.csv | bdeb581e04b54f3d769963fffde6b78280535ec72c0e28485153acc4159b7871 |
| raw/bom-test-2026__original__baseline/run.log | afc11504d1728ee8ed0ed843b867ae6e6055183a5d594592770973b8377bba5d |
| raw/bom-test-2026__original__baseline/sc_tree_master.csv | eaed4a1fd713a36e81073e1799760defc2c76c2e7c23b09f335d73856ceb7185 |
| raw/bom-test-2026__original__baseline/snapshot.json | b6dab88c1c18de2fc63cb751192acefb76800ca4c1f5b866e37b7157c13ade3a |
| raw/bom-test-2026__original__baseline/source_hashes.json | 62ca627b01be1742837f0df4f2b7a4863a61bce0336835c3721462595a6edaae |
| raw/bom-test-2026__original__baseline/weekly.csv | 87beaa6641578acb36d114603cb61bdd7996cfe4c3f751f6d4a406ed82455c9f |
| raw/capacity_read_sites.csv | aece754b0eae933950cae477718f7b1be1eb480aae614f01684fa2e1cecdfd61 |
| raw/dependencies.txt | 0cfd0e2df376180b3090ba7027636432437a23359abb36c944ca0356262f1359 |
| raw/environment.json | b23a0a84d68a006466585c4d9418bcfee7cabb24461e91c74a6308efcd60af28 |
| raw/ev-europe-2026__original__baseline/closure_weeks.csv | 15193b5f001caf8f155bfef7dc626bbc30b3580aa975cd3db4ce50cef8f9a7c4 |
| raw/ev-europe-2026__original__baseline/completion.json | 319530078ce40d198d5faae448436b1943cca4e6e372cc26b61836dd0028652b |
| raw/ev-europe-2026__original__baseline/copy_hashes.json | aaa5550c47a4318d14c1b852ce5ecf57a82f13f598c29494784ac2440518ca0a |
| raw/ev-europe-2026__original__baseline/events.json | 8a4465c0e7720ebe01c6ae88997cdb90c12b24c64f1d62bb10053426f257a025 |
| raw/ev-europe-2026__original__baseline/fill_targets.csv | 1c1d353748f141a5c5051de716f3af26d9d6fc5952baf5ec895560e62c245661 |
| raw/ev-europe-2026__original__baseline/holiday_calendar.csv | 2df8969738559521653a8706e24b01a0a1f6df66053776c53d99bd7e088ce234 |
| raw/ev-europe-2026__original__baseline/lot_timing.csv | 6f252e97f52e9aaa6bf81b3ca6eb7528d13ef005350f522137df0d77f235ee51 |
| raw/ev-europe-2026__original__baseline/paths.json | d2f39bd125cbe45f81145f4d7071d06ae6397e777707fb33aed247f292de2711 |
| raw/ev-europe-2026__original__baseline/ppc/ppc_event_ledger.csv | c54fc5b07f0fe0139ddf60cbfebd90e3e43fd5e78de0b02f0b00c43a7e5423f8 |
| raw/ev-europe-2026__original__baseline/ppc/ppc_kpi_summary.json | 0755572951502a8b20565227e05225fa91ae98262ba18bd4bf8d3f6bd98cd9b4 |
| raw/ev-europe-2026__original__baseline/ppc/ppc_lot_reconciliation.csv | 40630105403f07e23cb0b7c8dff5a433f2baccdba1ff6ce71d299522d7cbd022 |
| raw/ev-europe-2026__original__baseline/ppc/ppc_node_pl_summary.csv | bc12f578d2ce10849ebf6b771206ef2be96be8a7d6aee3427e9ff623e6623589 |
| raw/ev-europe-2026__original__baseline/ppc/ppc_node_week_summary.csv | bb542851177a6fdce6ace1d255679419565c5b45d3dbe30e1bc34de0e268a546 |
| raw/ev-europe-2026__original__baseline/ppc/ppc_profit_zone_summary.csv | 58ab222614ed9a03f6217899880458274c0b1b2590f601d2cda285b60c25d6f0 |
| raw/ev-europe-2026__original__baseline/push_config.csv | ef129fb30a1dbaf75289558ace4521bece4e974e054258bb468a9f55b99a5759 |
| raw/ev-europe-2026__original__baseline/run.log | e871bd3ec16f1b32bce28762222ad22d871fac5e62f393c1616bae90ffe98557 |
| raw/ev-europe-2026__original__baseline/sc_tree_master.csv | 9cdb0f22f7deeea61e390a5a9cdcda67cbdf702cff8c2cba1889ba9d5260ac3f |
| raw/ev-europe-2026__original__baseline/snapshot.json | a4c3d2ac5797548040b9a7040fa430b36bf89a46f4cec14e1b64f2b8f123f43e |
| raw/ev-europe-2026__original__baseline/source_hashes.json | aaa5550c47a4318d14c1b852ce5ecf57a82f13f598c29494784ac2440518ca0a |
| raw/ev-europe-2026__original__baseline/weekly.csv | b9cc6e204eb4e11a330e67621ba48b5262f023c967368f472b75ef1b521d8dd7 |
| raw/ev-thailand-2026__original__baseline/closure_weeks.csv | 3c70c97a6b08dc4feec6f830a5be53067bef677bf394dc0ec3bd70eecd6a8ffa |
| raw/ev-thailand-2026__original__baseline/completion.json | fd9de4b982184c8a8f1872f209a9178776e1cc405112b49d8122c9f2c5a1d39b |
| raw/ev-thailand-2026__original__baseline/copy_hashes.json | 963206b9df7c41734a638f3d3c4cf5741a6b0e97e2795a89e43e84b042042b26 |
| raw/ev-thailand-2026__original__baseline/events.json | cd39cfb47f2df9365541d9550748472c6360cfc970f0527b04542028b4ccd572 |
| raw/ev-thailand-2026__original__baseline/fill_targets.csv | 8bcc27fb5712fea77e273d0e6a4e9c9a35a07e5a7ca48d8d04a2d1bc7eaa42f1 |
| raw/ev-thailand-2026__original__baseline/holiday_calendar.csv | e57059bfee4f307cdb1221e88896d5b97c03636917ebeafe16ccb974b0947a4e |
| raw/ev-thailand-2026__original__baseline/lot_timing.csv | 50fd01cb269b8d2939fc7764dc56818beabe0109420ff267a7622d8eb9d2ea9b |
| raw/ev-thailand-2026__original__baseline/paths.json | 4ec39aee73fb0e8b04e989bb28d0160a09d9b52b178afb809c3a417c350b3db8 |
| raw/ev-thailand-2026__original__baseline/ppc/ppc_event_ledger.csv | f13b39ad41a79c7b3605618290952abeb427cd95849ff6d7557c24f9a0827a95 |
| raw/ev-thailand-2026__original__baseline/ppc/ppc_kpi_summary.json | fdd4c054b8044478b4596a25c5257c53852b44115a6c30acff8f466fe4d2ecb6 |
| raw/ev-thailand-2026__original__baseline/ppc/ppc_lot_reconciliation.csv | 053ebf8e1eef57236bc3317e7e21bf80f4ec516cb038fab5bf533c6c05e93e53 |
| raw/ev-thailand-2026__original__baseline/ppc/ppc_node_pl_summary.csv | ba785494a1c4b4cd43c7e6c5a5ca4094594d3aaaf4845315dbc90d9d9bda613b |
| raw/ev-thailand-2026__original__baseline/ppc/ppc_node_week_summary.csv | af1c1301b8926db251b13882f7548fd5fa76f274ef5c9231be22baf6d90db1a9 |
| raw/ev-thailand-2026__original__baseline/ppc/ppc_profit_zone_summary.csv | 629bbc1f72acdb86864e03fe2eff60d245f5d7d3b8129eabc97f5f3a8c973da7 |
| raw/ev-thailand-2026__original__baseline/push_config.csv | 1c434d1d71c4d47387cd531b7613c63f13ca9bafb845c484f7c530996bc5f560 |
| raw/ev-thailand-2026__original__baseline/run.log | edd7692eeb19a38dc87be2b25d415f469bcdd375f64ffaf36421fd96ab15c92b |
| raw/ev-thailand-2026__original__baseline/sc_tree_master.csv | db7e6acdfd3b1c6d49f0c7f4fc845f4e8e3c62f06dd65163a7443b461d288cd9 |
| raw/ev-thailand-2026__original__baseline/snapshot.json | dc00d74dcc69411cfff8dc41ee79f6637ab320d063774f65bf9cfde98e3631c6 |
| raw/ev-thailand-2026__original__baseline/source_hashes.json | 963206b9df7c41734a638f3d3c4cf5741a6b0e97e2795a89e43e84b042042b26 |
| raw/ev-thailand-2026__original__baseline/weekly.csv | ef66b429d41fdc99e41f9d29c08f84e22261f94ee739eb55647ab61bf4866d59 |
| raw/ev-thailand-2026_update__original__baseline/closure_weeks.csv | 74c274447560789aceb66ab31fc4d31e32ba55beb53962cbabb6f3a8682b1a1f |
| raw/ev-thailand-2026_update__original__baseline/completion.json | 186bd4598860ef466a0ad1fc2f51d08305b5c5b69386c644d6bedb2d99ab500e |
| raw/ev-thailand-2026_update__original__baseline/copy_hashes.json | d5accedb661d760666de0fdf0cba1047182f65343c9d1423313e07254e218d37 |
| raw/ev-thailand-2026_update__original__baseline/events.json | 2e70470759341a4babf9670ef0a0cb9d2b9faf0f4a884f786c9d45adbc47e736 |
| raw/ev-thailand-2026_update__original__baseline/fill_targets.csv | 4cef9af5413e29433f01f361f532ac65dd8718f5c3421c3709d863c9ad2258a8 |
| raw/ev-thailand-2026_update__original__baseline/holiday_calendar.csv | 2dc4411de5b5ff75203c05b9344d6e86c27ce389a6b58c9106e3b857f4c9f158 |
| raw/ev-thailand-2026_update__original__baseline/lot_timing.csv | 97d98f04654e483822199ebe7366c9a9281e3e5cb1cfd3246fa3e7e759d63e85 |
| raw/ev-thailand-2026_update__original__baseline/paths.json | 4ec39aee73fb0e8b04e989bb28d0160a09d9b52b178afb809c3a417c350b3db8 |
| raw/ev-thailand-2026_update__original__baseline/planning_config.csv | d8c4fd33b57998a6db5513af44578c5c38d918815ae677c7dc72abc16864993c |
| raw/ev-thailand-2026_update__original__baseline/ppc/ppc_event_ledger.csv | bf05bcf80d4df791cc2d90f9b81ea9895f52ec26dac0408a55450240e9af4ecf |
| raw/ev-thailand-2026_update__original__baseline/ppc/ppc_kpi_summary.json | fdd4c054b8044478b4596a25c5257c53852b44115a6c30acff8f466fe4d2ecb6 |
| raw/ev-thailand-2026_update__original__baseline/ppc/ppc_lot_reconciliation.csv | 053ebf8e1eef57236bc3317e7e21bf80f4ec516cb038fab5bf533c6c05e93e53 |
| raw/ev-thailand-2026_update__original__baseline/ppc/ppc_node_pl_summary.csv | 2ebc0cb8e92f5413794b8d73041aa99329cf68448b2cad1ef8abf13e3dd4aa13 |
| raw/ev-thailand-2026_update__original__baseline/ppc/ppc_node_week_summary.csv | 8d0aba2eec96a3a24e8d84cd71391dee62f59da584b1a37fb4d0d4860c4d18d2 |
| raw/ev-thailand-2026_update__original__baseline/ppc/ppc_profit_zone_summary.csv | 629bbc1f72acdb86864e03fe2eff60d245f5d7d3b8129eabc97f5f3a8c973da7 |
| raw/ev-thailand-2026_update__original__baseline/push_config.csv | 1c434d1d71c4d47387cd531b7613c63f13ca9bafb845c484f7c530996bc5f560 |
| raw/ev-thailand-2026_update__original__baseline/run.log | 48d552caed47499e936a3bd427e263f4559e38ba32588fe15cd4cc8de1a3fdff |
| raw/ev-thailand-2026_update__original__baseline/sc_tree_master.csv | cab5d48c472c8361d0704559f8ac5fdcca0360f0040cefea1221e86bffb9cb98 |
| raw/ev-thailand-2026_update__original__baseline/snapshot.json | 0559abe88c01c27bcaebb553261ed8a36e7572c5bc1d424446684cb1c7396720 |
| raw/ev-thailand-2026_update__original__baseline/source_hashes.json | d5accedb661d760666de0fdf0cba1047182f65343c9d1423313e07254e218d37 |
| raw/ev-thailand-2026_update__original__baseline/weekly.csv | 892071fdfe731be8d6556b876cf0c5b2ab5844f381b45364c316add9e8e89b33 |
| raw/final_repository_checks.json | 653a72a63e9a4a7d2eb7e51b1fa8c3021a59656bec31b5906228c259f1cbe207 |
| raw/git_fsck.txt | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| raw/india-ghee-2026__original__baseline/closure_weeks.csv | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| raw/india-ghee-2026__original__baseline/completion.json | ef5a66ecad1877ae8cc6531e2fbc816c7ce09d1a6a63bf34a06efbc90227eaee |
| raw/india-ghee-2026__original__baseline/copy_hashes.json | 6dbb0242b302cc37278126c2880e4ccc4dc14b68578256fb816280b5ffad74f3 |
| raw/india-ghee-2026__original__baseline/events.json | 4d37cac8acf16b9d2ea09f8a76d856b7fb7a3386c5b501c2f674c6928fed9ac5 |
| raw/india-ghee-2026__original__baseline/fill_targets.csv | e6e559ed495f95f3d7d613d5ce3dc429268bb1ed5986657584c20d52233a89e7 |
| raw/india-ghee-2026__original__baseline/holiday_calendar.csv | 7767bd04341a6aa46444c94f7114a5d4b3f29d570fc6edec521e1c1a205bf3c2 |
| raw/india-ghee-2026__original__baseline/lot_timing.csv | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| raw/india-ghee-2026__original__baseline/paths.json | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
| raw/india-ghee-2026__original__baseline/planning_config.csv | bd82db314584db96dc3f0258cbdef8a72dc38dba46b06823428b0c0f983a9469 |
| raw/india-ghee-2026__original__baseline/ppc/ppc_event_ledger.csv | 6fa7b34270af7e671cde834f6fe2402fe9ce5887adec3fa4906006552142b38f |
| raw/india-ghee-2026__original__baseline/ppc/ppc_kpi_summary.json | 228c4733efbd2ada8d51c2ecb5fa3fad37202a27c5c239b89b009a18016417db |
| raw/india-ghee-2026__original__baseline/ppc/ppc_lot_reconciliation.csv | cdf75504413c7bd439c38ae89311cb2e531c3136f0fbd904c11061584fb0ca7c |
| raw/india-ghee-2026__original__baseline/ppc/ppc_node_pl_summary.csv | 4c402e2b8673b539142c9d2ab47d6b3fe39d30d9007517e51017d27453d019df |
| raw/india-ghee-2026__original__baseline/ppc/ppc_node_week_summary.csv | 2082f5d03bf7a576e5b04250db5d0bbdb1bb19332cf268f5353c845c31bbe4ad |
| raw/india-ghee-2026__original__baseline/ppc/ppc_profit_zone_summary.csv | 957765b73db27e3ad0093b10de4865c94188346c74f1ed4c085ffde7cfbc5364 |
| raw/india-ghee-2026__original__baseline/push_config.csv | bdeb581e04b54f3d769963fffde6b78280535ec72c0e28485153acc4159b7871 |
| raw/india-ghee-2026__original__baseline/run.log | 1da3c8a5ed6178db8dbd3b0c77c18dbb56c205b3ab992b6839e73983f021e75c |
| raw/india-ghee-2026__original__baseline/sc_tree_master.csv | 0aa461d9f690e9a45e38e628165500fd404df0a01c681c1792ec3418dabec54c |
| raw/india-ghee-2026__original__baseline/snapshot.json | ef7378bf3e722d76dde5850875b5d8db5a6fe04063dbfc939cd5bb6eed0a1e91 |
| raw/india-ghee-2026__original__baseline/source_hashes.json | 6dbb0242b302cc37278126c2880e4ccc4dc14b68578256fb816280b5ffad74f3 |
| raw/india-ghee-2026__original__baseline/weekly.csv | 4472a2a65f7c12c16e787c6263306bc404e13a55898e9a4f6152c8966dff76dc |
| raw/iphone_global__original__baseline/closure_weeks.csv | fbfd576f6610adb12a49785f24867dd8fb8a285051041387cfdf571148808d1b |
| raw/iphone_global__original__baseline/completion.json | 9b06c526d045552fdfba4ca4a560b571fd94ce92fb6f9c7bd5a1eebf2d96ff72 |
| raw/iphone_global__original__baseline/copy_hashes.json | 189402947c567abb68caf6897502a495e722f850712a6c4a494fc7cb549048c2 |
| raw/iphone_global__original__baseline/events.json | 17aa33625af1f8dbdc07523319bb90e8f04641740e9c380801b934c22f2d8c3c |
| raw/iphone_global__original__baseline/fill_targets.csv | 3753580c5aebddd2d9cd7f28ed603d7ec7f6a9e344ffbc758b257a72c8b4d100 |
| raw/iphone_global__original__baseline/holiday_calendar.csv | 58eb77452a79931d149b76276e3d82ff4a90c843fbcbc951d3fb0672d55899e7 |
| raw/iphone_global__original__baseline/lot_timing.csv | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| raw/iphone_global__original__baseline/paths.json | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
| raw/iphone_global__original__baseline/ppc/ppc_event_ledger.csv | de56ca352898f1ce64be42164266dcece9a0894fe7c8a0d67094b39fee2f4b3b |
| raw/iphone_global__original__baseline/ppc/ppc_kpi_summary.json | 18bcc59bec92e6934588c9f033d148d044e057c3fdeb72bd51cf1f119a4ad964 |
| raw/iphone_global__original__baseline/ppc/ppc_lot_reconciliation.csv | 4e66ad9fa3a96d4765d52e891468d5f70ec4812fe90cfc0dd0954447cf5042ed |
| raw/iphone_global__original__baseline/ppc/ppc_node_pl_summary.csv | 2b4e16048de120034d33b973b8c9abc64a1e4093e21e84bb982a38f68836afce |
| raw/iphone_global__original__baseline/ppc/ppc_node_week_summary.csv | 47f876c8376971e7a334f7696650a81ce488469e623e102cb51cb59a2a35e24a |
| raw/iphone_global__original__baseline/ppc/ppc_profit_zone_summary.csv | a7b1fc4397175753e00a290f13b38651665515a0e29f41cfdd7f12e95dbe8246 |
| raw/iphone_global__original__baseline/push_config.csv | f9bb5b6296792c822fc5dbf4484aa6037be613c36103dcd0921ae355227db621 |
| raw/iphone_global__original__baseline/run.log | dcb96f6eb6e89928151c7c8924be1d8ebef1eba8cdd3c37dd57206a0f4e73771 |
| raw/iphone_global__original__baseline/sc_tree_master.csv | 4954ff1dd5db99eda317782a6b4630b6c82817f8cb88427ce6bad58ff657630a |
| raw/iphone_global__original__baseline/snapshot.json | 06ee89cfc1069a34c87e90d5f060fa8985007a200ef412fd42b8c49988410893 |
| raw/iphone_global__original__baseline/source_hashes.json | 189402947c567abb68caf6897502a495e722f850712a6c4a494fc7cb549048c2 |
| raw/iphone_global__original__baseline/weekly.csv | f3f99051f50226f14c8a0a919fa0eb99976e38144fff6ea1be6ac91ba2702966 |
| raw/oil-global-2027__original__baseline/closure_weeks.csv | 3a0204af31ae018e0b0b05684013d0aee9f346a76fed899d00af0431d1e3891b |
| raw/oil-global-2027__original__baseline/completion.json | 1ac16a2194994766a4fa717eb83d56df7b5ca2122b03922d36a8f66bbcac6fdd |
| raw/oil-global-2027__original__baseline/copy_hashes.json | 49d5d89328ac07f5de6c4061b46030254e8b6e78450c85acf366c805932949ff |
| raw/oil-global-2027__original__baseline/events.json | e1d67395e3069a636a35e2bb3af7a080c485303d87559a6aa842bcb902683f26 |
| raw/oil-global-2027__original__baseline/fill_targets.csv | d1a122a3986d33c0505bb49f69e8145a9d8b0acb6a44f8a65796859a6157d593 |
| raw/oil-global-2027__original__baseline/holiday_calendar.csv | 3b1992f7e4266ec3148ef131ed67a36e73f7242da7d4d9068afb30900cf24444 |
| raw/oil-global-2027__original__baseline/lot_timing.csv | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| raw/oil-global-2027__original__baseline/paths.json | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
| raw/oil-global-2027__original__baseline/ppc/ppc_event_ledger.csv | 9dd8a14e379c8c4767469a9c1956ffe2b231bd99440b79de25ac183f20afe7bf |
| raw/oil-global-2027__original__baseline/ppc/ppc_kpi_summary.json | 7d1a74fd0280f084e6e802be110a785a9cfcd2c1ee151cf679a214841cf55c3f |
| raw/oil-global-2027__original__baseline/ppc/ppc_lot_reconciliation.csv | 04059b4701ad8dc2ecc8fa23338271efeeb6c6d4452d080f8334e50ce75c0415 |
| raw/oil-global-2027__original__baseline/ppc/ppc_node_pl_summary.csv | 4eda86266aa5dc2a216dc1a25c8b9dfa4bb3c17c05ef4485ed014d413218a238 |
| raw/oil-global-2027__original__baseline/ppc/ppc_node_week_summary.csv | 333541164bb5da7d65866108a6936a95cd1174f70758043f064c6df273e13158 |
| raw/oil-global-2027__original__baseline/ppc/ppc_profit_zone_summary.csv | 7f7af7c9e8feb2eff46164e740be0090918ab00b894e3818f3c82b1281d4ab78 |
| raw/oil-global-2027__original__baseline/run.log | 6f280b2fc23ced1d27b2603d50b35f7a4b5ba9b754608447d9a17d8c4abf48ef |
| raw/oil-global-2027__original__baseline/sc_tree_master.csv | 4d953012be13ea0add9929013144041dceb0abb15850f2e2518f095252dafdf9 |
| raw/oil-global-2027__original__baseline/snapshot.json | 04635bf7172be0fd22798372e48ad9b690fd79b27c8f6cdfa86b43f5f872b7fe |
| raw/oil-global-2027__original__baseline/source_hashes.json | 49d5d89328ac07f5de6c4061b46030254e8b6e78450c85acf366c805932949ff |
| raw/oil-global-2027__original__baseline/weekly.csv | fc2a6a7943882f5b8b4cacc1cffc7f83a0a28f4f0b1f8d6b1620adf38d887ca0 |
| raw/priority_execution.log | e5acefdae3017c61b92d59adca757faf312923c5ef58b4bcd87355c5413e5de5 |
| raw/qualification_pytest.txt | e703e43480898a361b0a68d0abefba92b943e218d237123938a4bf434d688779 |
| raw/reference_documents/2fc7f4b_data_diff.txt | 285a3dbd7d427c1bfc8ed122976358e0fed7a2a7c35eff4529901a418bce7cd8 |
| raw/reference_documents/docs/codex_requests/holiday_explicit_closure_engine_request.md | 87e2f0a35468770a1bfe1ed36764f1648f780ea1c4a7411b690a5e3c42238b7f |
| raw/reference_documents/docs/design/holiday_calendar_and_capacity_semantics.md | c670c28caa05c1bf01e7ccee68ae6f34ce3fdb70548cab1a06cd2871d22e21d1 |
| raw/reference_documents/docs/design/holiday_calendar_push_lead_time_and_planning_horizon.md | 27321785bda4907a5ba16950d00d2c2a48ee81d7ce601502c4665a1698f4cd5a |
| raw/reference_documents/docs/design/planning_warmup_and_reporting_horizon.md | a307783c7417c839a78f6eded0a66b379085a1fa40520c763137574c3d1acbc0 |
| raw/reference_documents/docs/design/push_production_lead_time.md | 955b539bc9e46ea3ceee00757f02618f396fd1c81cfa5d437fe843eb0d2fb474 |
| raw/rice-japan-2027-2028__original__baseline/closure_weeks.csv | f68373b400c66230a0d5ac3f5bd1664e649a90185ff2e19d9448dd44c9e39664 |
| raw/rice-japan-2027-2028__original__baseline/completion.json | de9f71f0b5418d3d41c621763df83e473c5adf45061b3fd419b4fac2bf20bde1 |
| raw/rice-japan-2027-2028__original__baseline/copy_hashes.json | 80116102977cee673e83cfdaa1c2675cb149ca1e534a5cdcc33b2e17a364e093 |
| raw/rice-japan-2027-2028__original__baseline/events.json | 606782c988d001b13abeb6b097e962d2c87866268f73119d5a07067b0d318efa |
| raw/rice-japan-2027-2028__original__baseline/fill_targets.csv | 075445f5bec5334c28ce4f2f60a1831fff8b5e8134bbb66ef75a2d16d6a2b35d |
| raw/rice-japan-2027-2028__original__baseline/holiday_calendar.csv | 286971528e0ae884db4a8930a49a5325fb535aa1360b56d6170915e842be994b |
| raw/rice-japan-2027-2028__original__baseline/lot_timing.csv | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| raw/rice-japan-2027-2028__original__baseline/paths.json | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
| raw/rice-japan-2027-2028__original__baseline/ppc/ppc_event_ledger.csv | a5a4424e87a37f9d0826693fa9272a093104ae9e5f7bd60b5a32bbcfbc08b4a2 |
| raw/rice-japan-2027-2028__original__baseline/ppc/ppc_kpi_summary.json | 078f766608c705975f28c5c946f5f9cb09fb1f151eafa85591365b7961f182aa |
| raw/rice-japan-2027-2028__original__baseline/ppc/ppc_lot_reconciliation.csv | 35185a0ec184030fef4a03ecf6d2247d6fa8a07a8e4635415858c8b9eb20be57 |
| raw/rice-japan-2027-2028__original__baseline/ppc/ppc_node_pl_summary.csv | c65a59225264deced0a2c222b3e5e0076a8ccdfbf673e26f9142ffc155e5e327 |
| raw/rice-japan-2027-2028__original__baseline/ppc/ppc_node_week_summary.csv | d1204042ab7d5e6b3eed0a73d7ed38c327030c7cb25c6fd30b36d2f81bb7876c |
| raw/rice-japan-2027-2028__original__baseline/ppc/ppc_profit_zone_summary.csv | 19b864f069646a85239aff8e2b9418e37a2a633d747649a619ac2289246ffd94 |
| raw/rice-japan-2027-2028__original__baseline/push_config.csv | 70e906cf52e03e6f026475f4d8bd01594f455125a9022afb218705df082d0b96 |
| raw/rice-japan-2027-2028__original__baseline/run.log | 1b9a1ed91dce43c50d2f1080db8e587f815fff97c4f157eb3c92bf78596fe05b |
| raw/rice-japan-2027-2028__original__baseline/sc_tree_master.csv | 28db54651a2bb4e985cd549ce5af6e3b614e5f5168eade6947e71dfbf11688e3 |
| raw/rice-japan-2027-2028__original__baseline/snapshot.json | be1b6a3e35fa43e565cb8df9687c4ee3ce17a946f93feecce4b48cf87b6ac0c3 |
| raw/rice-japan-2027-2028__original__baseline/source_hashes.json | 80116102977cee673e83cfdaa1c2675cb149ca1e534a5cdcc33b2e17a364e093 |
| raw/rice-japan-2027-2028__original__baseline/weekly.csv | 2f4d3cc097d9c45950951b56c06caeb731f0c644afd804116f94cba134d3d452 |
| raw/smartx-2027-2029__original__baseline/closure_weeks.csv | 59e65fa48756a3d032d69cc0f88e18208cefd887ca1537d2df3165f6059f64d3 |
| raw/smartx-2027-2029__original__baseline/completion.json | 5ece66aa0580a39c90ec8a61492375910a7c9f9f628a4f682f78f7c95fdbfbdb |
| raw/smartx-2027-2029__original__baseline/copy_hashes.json | 502cd3d17f6e7e01badf6131fe12b4dbb3383064c1027d75ac275d945d0bef3b |
| raw/smartx-2027-2029__original__baseline/events.json | 2944542a7bb0c755932cb19b995c5cb2cfda906eb7265c2324afb49874d2c1f2 |
| raw/smartx-2027-2029__original__baseline/fill_targets.csv | 1db3df4dbd15bbac9bfe52c8ad7841357bbee1b223771de3663665cdcb0db6e3 |
| raw/smartx-2027-2029__original__baseline/holiday_calendar.csv | 3eb5eba4d7c21759eadda6ad691401fab7bf99c084920b757110541205c3bd43 |
| raw/smartx-2027-2029__original__baseline/lot_timing.csv | 620ec318ed02e67e3ad3b533a715d7e91e34893751436a98d262caef2319d045 |
| raw/smartx-2027-2029__original__baseline/paths.json | 2332e23d54ce3246b347d0b6c6c2b4344328289a1d59d728d1b3509d0c936c87 |
| raw/smartx-2027-2029__original__baseline/ppc/ppc_event_ledger.csv | 8c006cb1f75da07ea129a3c0fe0a63321ab3b18724eb882830814aa1613c9be6 |
| raw/smartx-2027-2029__original__baseline/ppc/ppc_kpi_summary.json | 76d028028eb6738d70c93eca821c361566405afe7519288f9584a88441ec8353 |
| raw/smartx-2027-2029__original__baseline/ppc/ppc_lot_reconciliation.csv | a95f609b2fbe5ff45d69a96c549affa0695900e05939d2f6272ef5406046e508 |
| raw/smartx-2027-2029__original__baseline/ppc/ppc_node_pl_summary.csv | bb2968cbfc40ba694a40d9bdfe170d8d743b5de45e8ff0dd401fff53f2e1f1e0 |
| raw/smartx-2027-2029__original__baseline/ppc/ppc_node_week_summary.csv | c978a2cd07a71c637d3ca5dadaeb19c1b83a5cfc1d53dbe5e3d40d5432e16c15 |
| raw/smartx-2027-2029__original__baseline/ppc/ppc_profit_zone_summary.csv | abd5d6cfa923256d35e3afe35d7ad6126ae311d461fddc5a946760ec2e457090 |
| raw/smartx-2027-2029__original__baseline/push_config.csv | 7389d94bb8976f2df3ecd528d7f535e574b1ba9733153e35c6b6a90ad2d9e193 |
| raw/smartx-2027-2029__original__baseline/run.log | 1368b9757077505e371555b82ab334407c32cbe5547af20eaba5fcc33d1cfc6f |
| raw/smartx-2027-2029__original__baseline/sc_tree_master.csv | 8e67725508031157bf06c560e9900f310886567e79ccd68ce59783d869707e55 |
| raw/smartx-2027-2029__original__baseline/snapshot.json | 259a0ca12f0df59463e74687f3bd8d1a2bff4cfcfdf23772900e19ec3a1f4263 |
| raw/smartx-2027-2029__original__baseline/source_hashes.json | 502cd3d17f6e7e01badf6131fe12b4dbb3383064c1027d75ac275d945d0bef3b |
| raw/smartx-2027-2029__original__baseline/weekly.csv | c13ad4e5fbe88f335403de2cb82518b50fe6cf7c9c44a3a1a9cabcd2d69cb3f2 |
| raw/soysauce-eu-2027__original__baseline/closure_weeks.csv | 29030a8d836f12b0f4c32948b3969cc4b6d95d62c2d99f8b708b33735e9fbc9d |
| raw/soysauce-eu-2027__original__baseline/completion.json | 45285f3949ed4d8ebc093d0a07a5e59caea4b38c79a9e9a997369407f7f72421 |
| raw/soysauce-eu-2027__original__baseline/copy_hashes.json | 9d010abac90ad680616e1d2aca674e9b533752794a03017b37580f78a85e83e9 |
| raw/soysauce-eu-2027__original__baseline/events.json | 6acc8a7353d66dfcc7fa42c6bd482fdecb46a94e4f22a68e4439acfbbe3b7d11 |
| raw/soysauce-eu-2027__original__baseline/fill_targets.csv | 8f329202b571a3f90b29b0ae1babdbc9a3b51b4d94f1ef769f8d73618faca6fe |
| raw/soysauce-eu-2027__original__baseline/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-eu-2027__original__baseline/lot_timing.csv | 3865e937cc2342a4a2d7c84f7f58c587c7a7d5989e0c8f364f678fed9792c824 |
| raw/soysauce-eu-2027__original__baseline/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-eu-2027__original__baseline/ppc/ppc_event_ledger.csv | c68444508b518ee7c41fc1889ab311e88a1cc21d198e6c0f8bcb514a256a877e |
| raw/soysauce-eu-2027__original__baseline/ppc/ppc_kpi_summary.json | 49b7f84ac6b07d5978bbd9c0f85f87e2724e3c99ac6b3b444a20568ff113bf36 |
| raw/soysauce-eu-2027__original__baseline/ppc/ppc_lot_reconciliation.csv | 81c3c081a451fe5c4d95e8fd0b0cdc52d6526537db80037cdc058262642db76c |
| raw/soysauce-eu-2027__original__baseline/ppc/ppc_node_pl_summary.csv | ace9cada447f6f7ba0c2ffbcc453ff163bf3542061230109b4599b9542d87eae |
| raw/soysauce-eu-2027__original__baseline/ppc/ppc_node_week_summary.csv | e0d0fdd5134ab41de2c4e82b3739ad0746eb09ba9b74975223c19918f22b683f |
| raw/soysauce-eu-2027__original__baseline/ppc/ppc_profit_zone_summary.csv | f30f7d29777f32b6943f90a3d1f2750d76aabe4b7b4678c02f40b3abc0cd11e6 |
| raw/soysauce-eu-2027__original__baseline/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-eu-2027__original__baseline/run.log | 9e9666d3eb915e5af5d6636ab95969e315d49722c2b03a66ec3716265aaeb780 |
| raw/soysauce-eu-2027__original__baseline/sc_tree_master.csv | 29cfd89a48ec927d759ef74cd1fa593b7f3823bd5f2c1d9babd4e3788fd710ff |
| raw/soysauce-eu-2027__original__baseline/snapshot.json | 187db396804936eaaa09b590fdfa2b9241df001bd24958e2c5fe964d2453ec99 |
| raw/soysauce-eu-2027__original__baseline/source_hashes.json | 9d010abac90ad680616e1d2aca674e9b533752794a03017b37580f78a85e83e9 |
| raw/soysauce-eu-2027__original__baseline/weekly.csv | 9ed5cec95da95c6f8d1284fa3b43a6995917e3e6eca3e6251feb7ff701b22501 |
| raw/soysauce-jpy-2027-alloc__original__baseline/closure_weeks.csv | 096bd6049c62c7d701e0ea4aa2b7a7a5f1b1867f7ff9bab9d1dcc72b9b2833c5 |
| raw/soysauce-jpy-2027-alloc__original__baseline/completion.json | 44f04b636ed0e03525a39e0ca2926a144f94dd5b7fde5e224235ec54f4b43f4a |
| raw/soysauce-jpy-2027-alloc__original__baseline/copy_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__original__baseline/events.json | e033ae53079749ff6c8417e0e63f29d02df3b4cec3255a69f7f4795caf7f963a |
| raw/soysauce-jpy-2027-alloc__original__baseline/fill_targets.csv | 185a2b6da6fb128a83089ecbc13a73e27fd262f29b5b900dd51a6d5b83d9bbd5 |
| raw/soysauce-jpy-2027-alloc__original__baseline/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-jpy-2027-alloc__original__baseline/lot_timing.csv | 4c98fa079c504825564b31160a44a539a23697eed374069ea33e01cbefbab8d7 |
| raw/soysauce-jpy-2027-alloc__original__baseline/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-jpy-2027-alloc__original__baseline/planning_config.csv | 86e75fce3b22494b15107e9b535f89c4358bfc553b3adaee525cd3167e5ae2ae |
| raw/soysauce-jpy-2027-alloc__original__baseline/ppc/ppc_event_ledger.csv | 7b1a397f7ddc97e387f84f768a27c3143eef3a7701769b3b8f20873f757c9289 |
| raw/soysauce-jpy-2027-alloc__original__baseline/ppc/ppc_kpi_summary.json | 51fa0c26d153524e20ee560b62d66552e6ab9fca28bcb2466e5d911b7da0b61a |
| raw/soysauce-jpy-2027-alloc__original__baseline/ppc/ppc_lot_reconciliation.csv | eb78aa2bab6f760e8b9073205822407df09c012bd6f82d49c5a3a12cff977476 |
| raw/soysauce-jpy-2027-alloc__original__baseline/ppc/ppc_node_pl_summary.csv | 8009526f7deec2e667673a5c2e115bc2c196cba581f025578d08af9ace23d755 |
| raw/soysauce-jpy-2027-alloc__original__baseline/ppc/ppc_node_week_summary.csv | 1910b94ebbe5ae70307aea9cf382cb0add9cbe57b907f612ecc6ce3ca6fc4533 |
| raw/soysauce-jpy-2027-alloc__original__baseline/ppc/ppc_profit_zone_summary.csv | ad3b2e3bd2ec0193009a3a4fe430eb2c618b6998b2a0b7f144c6c658186160b1 |
| raw/soysauce-jpy-2027-alloc__original__baseline/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-jpy-2027-alloc__original__baseline/run.log | 46081f7d7a475fc2ad4ca7c1f4b614535f49736f93459d1ac266b51d91db457a |
| raw/soysauce-jpy-2027-alloc__original__baseline/sc_tree_master.csv | 21a834ccc0eb00a684803cbf2ee8472733ed2e4779c378403636aeafaba01416 |
| raw/soysauce-jpy-2027-alloc__original__baseline/snapshot.json | d41355fef2766aa750f9f2eb139112b5cc0182bc28da3118f7fb1a49fbb83186 |
| raw/soysauce-jpy-2027-alloc__original__baseline/source_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__original__baseline/weekly.csv | eeab4cccce559335fbbdf7c95cf0f1657544103eeaa2595bab1976e788a6ab58 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/closure_weeks.csv | a59bbcbead4746190cd3fcd01b7a627c83555c1a80b5a954a2ad26e2fdb35a51 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/completion.json | dd431311305cb6f4494c3070e96131236d993a08fd8076a907cd3416721b00bf |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/copy_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/events.json | 11dc551d3ddae482c1405e68db408ea1b8d661063a01794417d709e2fe821a70 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/fill_targets.csv | 2a0c8711196f4e3c8b04053e9743ed31b98876d0ea17da74415e0d9abc054bce |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/lot_timing.csv | cc6f86ad47f3779f530b0735f10d4f2f39ef3b849522dc76a8362d2fc4a635bf |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/planning_config.csv | 86e75fce3b22494b15107e9b535f89c4358bfc553b3adaee525cd3167e5ae2ae |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/ppc/ppc_event_ledger.csv | 7b1a397f7ddc97e387f84f768a27c3143eef3a7701769b3b8f20873f757c9289 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/ppc/ppc_kpi_summary.json | 51fa0c26d153524e20ee560b62d66552e6ab9fca28bcb2466e5d911b7da0b61a |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/ppc/ppc_lot_reconciliation.csv | eb78aa2bab6f760e8b9073205822407df09c012bd6f82d49c5a3a12cff977476 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/ppc/ppc_node_pl_summary.csv | 8009526f7deec2e667673a5c2e115bc2c196cba581f025578d08af9ace23d755 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/ppc/ppc_node_week_summary.csv | 1910b94ebbe5ae70307aea9cf382cb0add9cbe57b907f612ecc6ce3ca6fc4533 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/ppc/ppc_profit_zone_summary.csv | ad3b2e3bd2ec0193009a3a4fe430eb2c618b6998b2a0b7f144c6c658186160b1 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/run.log | 1f25412b4dfbbf5ba9d40b7821888c511b7ff2b13877b44e5150969d5e2d5c71 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/sc_tree_master.csv | 21a834ccc0eb00a684803cbf2ee8472733ed2e4779c378403636aeafaba01416 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/snapshot.json | df2450e99b4e68f9eb82711981ce4a0b4bc5d298abaaceb65633fb22135caa6e |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/source_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__original__preserve_soft/weekly.csv | f545b4b25464be424ba489e397688196b1440fb57ffca4fa1786ed3657542c74 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/closure_weeks.csv | b2584092ae26a47b062ab395bc45bff9bfa440f7060e4607ec52ec54aa4ecd35 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/completion.json | 4bd4e28d24108975807bffdf101936ea77ba0b49f3a08410a36c1aee8ad23cbb |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/copy_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/events.json | a59d0cdc872b8df1d6ef1503cb5961a6b300b45ffada4b083cc6da466f7fd425 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/fill_targets.csv | 185a2b6da6fb128a83089ecbc13a73e27fd262f29b5b900dd51a6d5b83d9bbd5 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/lot_timing.csv | 8d7b19e778427419a1ce53e3e281a0a8948292be60271ed1bc9b903315b8f3d2 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/planning_config.csv | 86e75fce3b22494b15107e9b535f89c4358bfc553b3adaee525cd3167e5ae2ae |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/ppc/ppc_event_ledger.csv | 7b1a397f7ddc97e387f84f768a27c3143eef3a7701769b3b8f20873f757c9289 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/ppc/ppc_kpi_summary.json | 51fa0c26d153524e20ee560b62d66552e6ab9fca28bcb2466e5d911b7da0b61a |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/ppc/ppc_lot_reconciliation.csv | eb78aa2bab6f760e8b9073205822407df09c012bd6f82d49c5a3a12cff977476 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/ppc/ppc_node_pl_summary.csv | 8009526f7deec2e667673a5c2e115bc2c196cba581f025578d08af9ace23d755 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/ppc/ppc_node_week_summary.csv | 1910b94ebbe5ae70307aea9cf382cb0add9cbe57b907f612ecc6ce3ca6fc4533 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/ppc/ppc_profit_zone_summary.csv | ad3b2e3bd2ec0193009a3a4fe430eb2c618b6998b2a0b7f144c6c658186160b1 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/run.log | 0b6f8312d5cd3bbd57c637df00e172538096384c7dc522a7bd2d82727fcc6baa |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/sc_tree_master.csv | 21a834ccc0eb00a684803cbf2ee8472733ed2e4779c378403636aeafaba01416 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/snapshot.json | 9b9afebfec3d36968b2da3c76c7bcc9f1fc5585db83fd08178586233ef0d36ab |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/source_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__original__receipt_defer/weekly.csv | a66380ed655db2acf47de5315ce3a2f8f66cfee10b32ff66ff1d9b4a599815cd |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/closure_weeks.csv | 096bd6049c62c7d701e0ea4aa2b7a7a5f1b1867f7ff9bab9d1dcc72b9b2833c5 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/completion.json | 6dab1ecf96e6433e729159236c6c8cb13fa8bcaea4e6d875f0345c20086e410c |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/copy_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/events.json | e033ae53079749ff6c8417e0e63f29d02df3b4cec3255a69f7f4795caf7f963a |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/fill_targets.csv | 185a2b6da6fb128a83089ecbc13a73e27fd262f29b5b900dd51a6d5b83d9bbd5 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/lot_timing.csv | 4c98fa079c504825564b31160a44a539a23697eed374069ea33e01cbefbab8d7 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/planning_config.csv | 86e75fce3b22494b15107e9b535f89c4358bfc553b3adaee525cd3167e5ae2ae |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/ppc/ppc_event_ledger.csv | 7b1a397f7ddc97e387f84f768a27c3143eef3a7701769b3b8f20873f757c9289 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/ppc/ppc_kpi_summary.json | 51fa0c26d153524e20ee560b62d66552e6ab9fca28bcb2466e5d911b7da0b61a |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/ppc/ppc_lot_reconciliation.csv | eb78aa2bab6f760e8b9073205822407df09c012bd6f82d49c5a3a12cff977476 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/ppc/ppc_node_pl_summary.csv | 8009526f7deec2e667673a5c2e115bc2c196cba581f025578d08af9ace23d755 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/ppc/ppc_node_week_summary.csv | 1910b94ebbe5ae70307aea9cf382cb0add9cbe57b907f612ecc6ce3ca6fc4533 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/ppc/ppc_profit_zone_summary.csv | ad3b2e3bd2ec0193009a3a4fe430eb2c618b6998b2a0b7f144c6c658186160b1 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/run.log | 218372508b7c44cbfd846543a6c7719f5de4e4fa5da6212c4605657f5f2fc461 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/sc_tree_master.csv | 21a834ccc0eb00a684803cbf2ee8472733ed2e4779c378403636aeafaba01416 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/snapshot.json | d41355fef2766aa750f9f2eb139112b5cc0182bc28da3118f7fb1a49fbb83186 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/source_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__original__ship_stop/weekly.csv | eeab4cccce559335fbbdf7c95cf0f1657544103eeaa2595bab1976e788a6ab58 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/closure_weeks.csv | 096bd6049c62c7d701e0ea4aa2b7a7a5f1b1867f7ff9bab9d1dcc72b9b2833c5 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/completion.json | 3c9f80f711569d838cdda3e310218c5268bea0ab792227cbfda7cbc60dd76393 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/copy_hashes.json | bf77aad35b4692a62ac54de9395af4a3795041a2e6ae2f4e0bbd8ed59ed70c82 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/events.json | 65b5b78a6cb281711bb140a5f47fe9d50c6bc854d50460d77212539020892f64 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/fill_targets.csv | 838d2cde492e704cb4e54165526856c68c31fd99f21df6c8b099eb6260f82766 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/lot_timing.csv | e2aaa15b57e547a4f97089c222a679743c6215e0ac68895eaa375377573fce85 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/planning_config.csv | 86e75fce3b22494b15107e9b535f89c4358bfc553b3adaee525cd3167e5ae2ae |
| raw/soysauce-jpy-2027-alloc__popt__baseline/ppc/ppc_event_ledger.csv | 4d4e54af63c22d09c19f08d025771c1283ff99078f4cfd6a4537e211efe47cc4 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/ppc/ppc_kpi_summary.json | 2377c3c283013ae585d693d43501988fc7716977b305206aabaed4bf27b4a1c8 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/ppc/ppc_lot_reconciliation.csv | ce27b68e474130f67fc31728cb195572e12d5d6041bceff891be2c0c9b1c6ed1 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/ppc/ppc_node_pl_summary.csv | d0cb312acc4f566a4360e49504010be585a14082140ad2976b1af097cb459044 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/ppc/ppc_node_week_summary.csv | 5eaf4ffc965c45a31ba2fed97417ef574b4d926a5199582aa46d2e402848b6cc |
| raw/soysauce-jpy-2027-alloc__popt__baseline/ppc/ppc_profit_zone_summary.csv | be45ce806689bba4276973099f644ebd9b604947bfc7a2750eac717117b5a10a |
| raw/soysauce-jpy-2027-alloc__popt__baseline/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-jpy-2027-alloc__popt__baseline/run.log | c30ad425bc76016fddf9b6d52fd96a68167540e3bb4c9e07f78d3f0e573f635e |
| raw/soysauce-jpy-2027-alloc__popt__baseline/s3_view.json | cb9a3c174754f5dcee459c68eca40f4766c3afe7d84863ee70a9a6531b24c875 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/sc_tree_master.csv | 21a834ccc0eb00a684803cbf2ee8472733ed2e4779c378403636aeafaba01416 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/snapshot.json | 5537ef84ead1608795166a6298eb5a5f3d5f2fe74639ecc4adf151292b79443f |
| raw/soysauce-jpy-2027-alloc__popt__baseline/source_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/unshipped_market_ids.csv | 75bb142a71bc3bedd1b3c5c271483ed9ce9d8b939756085c918d7fd22bc62471 |
| raw/soysauce-jpy-2027-alloc__popt__baseline/weekly.csv | fbd6a46bacfb180edfd47396d1d9384395fb8202e035604e5b3b46cb05a2a63f |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/closure_weeks.csv | a59bbcbead4746190cd3fcd01b7a627c83555c1a80b5a954a2ad26e2fdb35a51 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/completion.json | cdd7325fa25d8d1bc5531c32816b090ad431c3502594ce58f8835020dfa5295f |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/copy_hashes.json | bf77aad35b4692a62ac54de9395af4a3795041a2e6ae2f4e0bbd8ed59ed70c82 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/events.json | 19fb7fecf409f713d00bd3530b057e48c948a2ebaaf6d2fb2ea40fac900141eb |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/fill_targets.csv | 77ac7edacf0205695535086c32a9276c22f9bf1c34161418bc75444a7306f6f1 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/lot_timing.csv | 4d7215c1951a30cf0a1c004d49565b47754483c9cf8328c09242044eb953ceda |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/planning_config.csv | 86e75fce3b22494b15107e9b535f89c4358bfc553b3adaee525cd3167e5ae2ae |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/ppc/ppc_event_ledger.csv | 4d4e54af63c22d09c19f08d025771c1283ff99078f4cfd6a4537e211efe47cc4 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/ppc/ppc_kpi_summary.json | 2377c3c283013ae585d693d43501988fc7716977b305206aabaed4bf27b4a1c8 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/ppc/ppc_lot_reconciliation.csv | ce27b68e474130f67fc31728cb195572e12d5d6041bceff891be2c0c9b1c6ed1 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/ppc/ppc_node_pl_summary.csv | d0cb312acc4f566a4360e49504010be585a14082140ad2976b1af097cb459044 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/ppc/ppc_node_week_summary.csv | 5eaf4ffc965c45a31ba2fed97417ef574b4d926a5199582aa46d2e402848b6cc |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/ppc/ppc_profit_zone_summary.csv | be45ce806689bba4276973099f644ebd9b604947bfc7a2750eac717117b5a10a |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/run.log | fee624d60a2cdcf79cc697f7982726e8111b8035b1a2e419f4c9a837aa721426 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/s3_view.json | 11b1ae2a7625943a829711e89fb40b51bed03a4cbc84167a66466bf3f056574d |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/sc_tree_master.csv | 21a834ccc0eb00a684803cbf2ee8472733ed2e4779c378403636aeafaba01416 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/snapshot.json | 72158e2e05af70e374e8976c47e386ae115c383d3d2bb28c746f5a6a56f6e6bd |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/source_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__popt__preserve_soft/weekly.csv | 5d2bc738ad1d26d85dd40c402a9288c250265453753da694dc5582f01579398c |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/closure_weeks.csv | b2584092ae26a47b062ab395bc45bff9bfa440f7060e4607ec52ec54aa4ecd35 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/completion.json | 4701f7da35c25eb5c33b2b6624776509f0a8baf6711fe6904263e2e0ea34b26e |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/copy_hashes.json | bf77aad35b4692a62ac54de9395af4a3795041a2e6ae2f4e0bbd8ed59ed70c82 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/events.json | 48fbc4e3aeda1ebe745392a783b5b48c1f62e2f5e86ac7c1babef8ee40dd8178 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/fill_targets.csv | 838d2cde492e704cb4e54165526856c68c31fd99f21df6c8b099eb6260f82766 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/lot_timing.csv | 18aa54cdf14dda1d815b35ccb9f9b34b19157eb0ea1f26127ee8858bfd89d3c5 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/planning_config.csv | 86e75fce3b22494b15107e9b535f89c4358bfc553b3adaee525cd3167e5ae2ae |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/ppc/ppc_event_ledger.csv | 4d4e54af63c22d09c19f08d025771c1283ff99078f4cfd6a4537e211efe47cc4 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/ppc/ppc_kpi_summary.json | 2377c3c283013ae585d693d43501988fc7716977b305206aabaed4bf27b4a1c8 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/ppc/ppc_lot_reconciliation.csv | ce27b68e474130f67fc31728cb195572e12d5d6041bceff891be2c0c9b1c6ed1 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/ppc/ppc_node_pl_summary.csv | d0cb312acc4f566a4360e49504010be585a14082140ad2976b1af097cb459044 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/ppc/ppc_node_week_summary.csv | 5eaf4ffc965c45a31ba2fed97417ef574b4d926a5199582aa46d2e402848b6cc |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/ppc/ppc_profit_zone_summary.csv | be45ce806689bba4276973099f644ebd9b604947bfc7a2750eac717117b5a10a |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/run.log | f288290f2d37b6a50c09e6e8c04374213962445d1880296c765ec0467e9e0e3d |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/s3_view.json | 913ac3f2ebba41bb0bace5a90f4d399b505be9b93063652a32bf39b8663af0e5 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/sc_tree_master.csv | 21a834ccc0eb00a684803cbf2ee8472733ed2e4779c378403636aeafaba01416 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/snapshot.json | c6d9d7dfe9cf92dacdffb4acf091bde3005596dbe430980e186eb564d7e7e39d |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/source_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__popt__receipt_defer/weekly.csv | 7e528b127ba0bb85506c25b72e3460ca2ac70d0f0b098b6bfaa5cc65ef78fcc2 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/closure_weeks.csv | 096bd6049c62c7d701e0ea4aa2b7a7a5f1b1867f7ff9bab9d1dcc72b9b2833c5 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/completion.json | b1ada7191af65d87a8648b3795a9109c7cdefb82feed26c9010a86e620534f02 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/copy_hashes.json | bf77aad35b4692a62ac54de9395af4a3795041a2e6ae2f4e0bbd8ed59ed70c82 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/events.json | 65b5b78a6cb281711bb140a5f47fe9d50c6bc854d50460d77212539020892f64 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/fill_targets.csv | 838d2cde492e704cb4e54165526856c68c31fd99f21df6c8b099eb6260f82766 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/lot_timing.csv | e2aaa15b57e547a4f97089c222a679743c6215e0ac68895eaa375377573fce85 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/planning_config.csv | 86e75fce3b22494b15107e9b535f89c4358bfc553b3adaee525cd3167e5ae2ae |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/ppc/ppc_event_ledger.csv | 4d4e54af63c22d09c19f08d025771c1283ff99078f4cfd6a4537e211efe47cc4 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/ppc/ppc_kpi_summary.json | 2377c3c283013ae585d693d43501988fc7716977b305206aabaed4bf27b4a1c8 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/ppc/ppc_lot_reconciliation.csv | ce27b68e474130f67fc31728cb195572e12d5d6041bceff891be2c0c9b1c6ed1 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/ppc/ppc_node_pl_summary.csv | d0cb312acc4f566a4360e49504010be585a14082140ad2976b1af097cb459044 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/ppc/ppc_node_week_summary.csv | 5eaf4ffc965c45a31ba2fed97417ef574b4d926a5199582aa46d2e402848b6cc |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/ppc/ppc_profit_zone_summary.csv | be45ce806689bba4276973099f644ebd9b604947bfc7a2750eac717117b5a10a |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/run.log | 07530cbffeb3b37978aad428e12a1bb2a3cc365901971c93ad8ac8fd8d0a1744 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/s3_view.json | 1da4bdfb37486344fe7c1847dd9953e27b6959e123168a698d7a8014b3f4a4e0 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/sc_tree_master.csv | 21a834ccc0eb00a684803cbf2ee8472733ed2e4779c378403636aeafaba01416 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/snapshot.json | 5537ef84ead1608795166a6298eb5a5f3d5f2fe74639ecc4adf151292b79443f |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/source_hashes.json | 44a2166077e84d0f5b8649ada6cac16e860f15f24b6fe16cec986e114d2fd702 |
| raw/soysauce-jpy-2027-alloc__popt__ship_stop/weekly.csv | fbd6a46bacfb180edfd47396d1d9384395fb8202e035604e5b3b46cb05a2a63f |
| raw/soysauce-jpy-2027__original__baseline/closure_weeks.csv | 8d46cb77f22d237b464572784ddaa130ab7435eeb1bd45ff1b8e5baff6111813 |
| raw/soysauce-jpy-2027__original__baseline/completion.json | 44f04b636ed0e03525a39e0ca2926a144f94dd5b7fde5e224235ec54f4b43f4a |
| raw/soysauce-jpy-2027__original__baseline/copy_hashes.json | 584c382199513977e0c6c89491a1ba13f337741d1709f6a9cb69908016fcbbc4 |
| raw/soysauce-jpy-2027__original__baseline/events.json | 1c67d0bbf0879642badcbb5d41fd8cf38a2df8a94270c1418222612c62303317 |
| raw/soysauce-jpy-2027__original__baseline/fill_targets.csv | 3f21b2b7e6eb4c06938217b10850ceea7980ad336376ae8210b7c836172ad3dc |
| raw/soysauce-jpy-2027__original__baseline/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-jpy-2027__original__baseline/lot_timing.csv | f916b283a6ccee6a8269c283483a36f4a14d71a9988ab81f0a4ca27639759dbb |
| raw/soysauce-jpy-2027__original__baseline/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-jpy-2027__original__baseline/planning_config.csv | 86e75fce3b22494b15107e9b535f89c4358bfc553b3adaee525cd3167e5ae2ae |
| raw/soysauce-jpy-2027__original__baseline/ppc/ppc_event_ledger.csv | 7b1a397f7ddc97e387f84f768a27c3143eef3a7701769b3b8f20873f757c9289 |
| raw/soysauce-jpy-2027__original__baseline/ppc/ppc_kpi_summary.json | 51fa0c26d153524e20ee560b62d66552e6ab9fca28bcb2466e5d911b7da0b61a |
| raw/soysauce-jpy-2027__original__baseline/ppc/ppc_lot_reconciliation.csv | eb78aa2bab6f760e8b9073205822407df09c012bd6f82d49c5a3a12cff977476 |
| raw/soysauce-jpy-2027__original__baseline/ppc/ppc_node_pl_summary.csv | 8009526f7deec2e667673a5c2e115bc2c196cba581f025578d08af9ace23d755 |
| raw/soysauce-jpy-2027__original__baseline/ppc/ppc_node_week_summary.csv | 1910b94ebbe5ae70307aea9cf382cb0add9cbe57b907f612ecc6ce3ca6fc4533 |
| raw/soysauce-jpy-2027__original__baseline/ppc/ppc_profit_zone_summary.csv | ad3b2e3bd2ec0193009a3a4fe430eb2c618b6998b2a0b7f144c6c658186160b1 |
| raw/soysauce-jpy-2027__original__baseline/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-jpy-2027__original__baseline/run.log | d9258a4332b8eb526a57b8666e1cb0f33f4057d1498e88699f44cc1bf920971d |
| raw/soysauce-jpy-2027__original__baseline/sc_tree_master.csv | 21a834ccc0eb00a684803cbf2ee8472733ed2e4779c378403636aeafaba01416 |
| raw/soysauce-jpy-2027__original__baseline/snapshot.json | 1e316945220bbf44a6d130eb27b837d1b8a89d214a1706aa2a1442bd1ffa3740 |
| raw/soysauce-jpy-2027__original__baseline/source_hashes.json | 584c382199513977e0c6c89491a1ba13f337741d1709f6a9cb69908016fcbbc4 |
| raw/soysauce-jpy-2027__original__baseline/weekly.csv | 8c726ec621e0c87748f7e2a134df63626432c76c2ac74a18ac281e9452f2af6e |
| raw/soysauce-us-2027__original__baseline/closure_weeks.csv | 74fca5cddbf49898bee45e35504c0a6d0181818cee33bc9d83066d16a7fce587 |
| raw/soysauce-us-2027__original__baseline/completion.json | 45285f3949ed4d8ebc093d0a07a5e59caea4b38c79a9e9a997369407f7f72421 |
| raw/soysauce-us-2027__original__baseline/copy_hashes.json | a63096994d127ea95ca22f037104afc01e13abfcb1745b428bdfa9035632a294 |
| raw/soysauce-us-2027__original__baseline/events.json | 6fdd0fe761e143a0cfa685f270c05d1ecc60a3b6462b0d59e2c42915bd984f13 |
| raw/soysauce-us-2027__original__baseline/fill_targets.csv | a1046007375cdf36432ab43417dec8efa37af9c8b471702034b6ee39fef1bd33 |
| raw/soysauce-us-2027__original__baseline/holiday_calendar.csv | 50b7f1cb7bb561a0a35baacfa99fd29d9f7c272419cd680b2a0683ecfdb41152 |
| raw/soysauce-us-2027__original__baseline/lot_timing.csv | 4cb055b700344ae8c343a8498c81747b829b5cd720afbcea0f63c6497b240bb9 |
| raw/soysauce-us-2027__original__baseline/paths.json | 9f11eeeee7c65a256abf83e8632c5d8ae26f9622c640e3b0ed4eeb6d3592a034 |
| raw/soysauce-us-2027__original__baseline/ppc/ppc_event_ledger.csv | de7cd469a69ec0737b60da3a6ee35f05205a8c012daaa315836cfe3a1abdebb1 |
| raw/soysauce-us-2027__original__baseline/ppc/ppc_kpi_summary.json | 1b73564f02479008a5e8392c2ab14fe157e434d1766d1ff3573ea2b27ad2c092 |
| raw/soysauce-us-2027__original__baseline/ppc/ppc_lot_reconciliation.csv | fbea9f394fe1866c7baa20c43d78eefbc18c5b7311d4fc969864e0c16fd45b81 |
| raw/soysauce-us-2027__original__baseline/ppc/ppc_node_pl_summary.csv | 0f0f3e6d512bec9421d198e76f4799d0dd6097cc95918513f88bd18c5586fea6 |
| raw/soysauce-us-2027__original__baseline/ppc/ppc_node_week_summary.csv | 91b07704c36dd05eb7c3beabbafc8ee6239c79d2c6ad43297763804e3f8b9cf2 |
| raw/soysauce-us-2027__original__baseline/ppc/ppc_profit_zone_summary.csv | 850c6be024073b46051993dfe9d55ae185703aafed76f020622b031574fbc040 |
| raw/soysauce-us-2027__original__baseline/push_config.csv | 42236eed141c74a2dacbdbe0a81497429e1537ed462bb23a06789323e672da1d |
| raw/soysauce-us-2027__original__baseline/run.log | da49eaa9472a39cf3278f428d0949c8ab07f33ca2de6beb5d551bc67ea7535bb |
| raw/soysauce-us-2027__original__baseline/sc_tree_master.csv | 29cfd89a48ec927d759ef74cd1fa593b7f3823bd5f2c1d9babd4e3788fd710ff |
| raw/soysauce-us-2027__original__baseline/snapshot.json | 589a18c1811f9a9efba8da55827d5abc70313977772212206f26ec2f0a01a931 |
| raw/soysauce-us-2027__original__baseline/source_hashes.json | a63096994d127ea95ca22f037104afc01e13abfcb1745b428bdfa9035632a294 |
| raw/soysauce-us-2027__original__baseline/weekly.csv | 4ba671b44c6e85799969c00f553d1e3993103a3b9272dc937d7a13f20d5d13b4 |
| raw/summary/T2_1_T2_3_totals.csv | 3186558f237a9117b3f6b111b3369eda508954eaab452e972777dfa3ee3306af |
| raw/summary/T2_2_all_rows.csv | 59857859abfbd16f20187ef2c44e62c00aa80f18995900d9627534a6eef7beac |
| raw/summary/T2_2_all_weeks.csv | 38e33c3db6af98565ec1a3aff4ea4322b9ecb1f273a2ad4238c11d951990f239 |
| raw/summary/T2_3_annotated_read_sites.csv | 1ff85bc2f8d54623e841b05890c30cdddd07c3d95616ed14679215bc4b6a2c77 |
| raw/summary/T2_4_offset_distribution.csv | 5a6d566768f909a6bd8be2489a8326c84530491d0962d4b3525e36c4d3c9a166 |
| raw/summary/T2_4_paths.json | 78a9ee3571db95ae7a354da5c1166c31839c9aedc3aebeac9641a96dc70c61aa |
| raw/summary/T2_5_money_summary.json | ab9870c884b2176c32f7f5aa5020aadbc74686c2750dd4e376ae51b357e15367 |
| raw/summary/T2_5_unshipped_ID_money.csv | 551b291ca7253fedce4464eac00eec89f1c07b608349610b1f2e2a65ee0d72ae |
| raw/summary/instrumented_golden_comparison.csv | bccb59ef706c2da4dd4686e2859f4065eea697723e241af1c91b3355be64c96e |
| raw/summary/push_actual_crosscheck.json | 3906c8486840a812d1b8707dde8f5d21e4b0a3da155cb914a47df59400755108 |
| raw/summary/summary_checks.json | f54b534eb3bca6f5f892a6a676a94cc5504af8d4f03c4f034ab8ba99b82af4f1 |
| raw/summary/tracked_file_integrity.csv | 337d92cc5fd3fe2ebe5271109e0a9ebfe4ebc36d5452a0db440090dc4be8f59e |
| raw/survey_execution.log | 15d80a92917f692833efe8c25efa24f218681bb17b97758219990407ede7afdc |
| tools/probe_capacity_trial02.py | ace8c860c086b5116078330ca57da34b83960cb74635c6836325bb77b6138435 |
