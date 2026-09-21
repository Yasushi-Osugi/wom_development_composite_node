# Coding Request Letter: GUI改善 3件(2026-07-14、apparel-global-2028-2029のGUIレビューより)

作成日: 2026-07-14
作成者: Claude (Cowork)
ステータス: 実装完了。ユーザー側でのGUI実機確認(見た目・操作性)のみ残タスク。
対象: `wom/gui/app.py`(ケース非依存、GUI共通コード)

---

## 0. 背景

apparel-global-2028-2029のPlanning Engine動作確認(ユーザーがGUIスクリーンショット多数を確認)の過程で、ケース固有ではないGUI共通の改善点が3件見つかった。ユーザーの了承を得て、Coding Request Letterを起こした上でその場で実装した。

## 1. Node P&L テーブルの GM% = 0.0% 表示について

### 現象

Managementタブの「Node P&L(拠点別損益)」テーブルで、Garment/Fabric/Dyeing/FG_WH/DCなど大半のノードがGM%=0.0%と表示され、あたかも損失ノードであるかのように見えていた。

### 調査結果

`wom/ppc/ppc_kpi.py`の`build_node_pl_summary()`を確認したところ、`market_revenue`イベントは`ppc_profit_zone.py`で`channel_node`(最終販売のRetail/leaf_out)にのみ記録される仕様だった。つまり中間ノードは構造的にrevenue_base=0であり、GM%も`revenue_base>0 else 0.0`というガード式により機械的に0.0%表示になっていた(バグではなく「このノードでは売上計上がない」ことの表示だが、テーブル上は損失ノードと見分けがつかず紛らわしい)。

### 修正

`ManagementCockpitPanel._refresh_node_pl_table()`で、`revenue_base==0`の行はGM%列を`"0.0%"`ではなく`"--"`(N/A)表示にした。revenue_baseが実際に存在するRetail_*等のノードは、引き続き実数のGM%を表示する。

## 2. SC Networkタブのレイアウト(network graph / PSI graph / Revenue graphの横幅不統一)

### 現象

SC Networkタブが左右分割(PanedWindow, orient="horizontal")で、左ペインにネットワークグラフ、右ペインにPSI Chart(PSI graph + Cost/Revenue graphを縦積み)を配置する構成だった。結果としてネットワークグラフが画面の約半分の幅に圧縮され、ノード名ラベルが重なって読みにくくなっていた。

### 修正

`SCNetworkPanel._build()`のPanedWindowを`orient="vertical"`に変更し、上段: ネットワークグラフ(全幅)/ 下段: PSI Chartタブ(PSI graph縦積みCost・Revenue graph、既存構成を維持、全幅)という3段構成にした。各Figureの初期`figsize`もワイド化(5×7→9×4、5×3.5→9×3)。PSI Listタブは下段のサブノートブック内にそのまま残る。

## 3. World Mapのノードラベル重なり

### 現象

World Mapタブで、各ノードのマーカーに常時「アイコン+ノード名」のテキストラベルが表示される仕様だったため、地理的に近いノード(例: BangladeshとVietnam)が密集する箇所でラベルが重なって読めなくなっていた。

### 修正

`WorldMapPanel._draw_nodes()`から、マーカーの常時表示テキスト(`text=label`)を削除した。クリック時に発火する`_on_marker_click`は既存のまま維持されており、クリックすると右側のNode Infoパネルにノード名・Type・Lat/Lon・SKU・Region・descriptionが表示される。ユーザーの提案(「ノード名のみが分かれば、Click and Show detail panelで良い」)に沿い、常時ラベルをやめてクリック起点の詳細表示に一本化した。

## 4. バッファリング在庫ノードの可視化(stockerアイコン)

### 背景

apparel-global-2028-2029のGUI確認で、OutBound側の`FG_WH_BD`/`FG_WH_PT`(`buffering_stock_flag=1`)がCOを吸収するバッファ在庫拠点として機能していることが確認できたが、Network graph上ではどのノードがこの役割を持つのか区別できなかった(通常ノードと同じ丸マーカー)。これは`verify/README.md`に記載済みの既知の制約(「Step 8のPUSH/decoupling状態がGUI上に専用表示されない」)とも関連する。

### 修正

`SCNetworkPanel._draw_hammock()`で、`sc_tree_master.csv`の`buffering_stock_flag=1`から`wom/engine/sc_tree_builder.py`が設定する`PlanNode.is_decoupling`属性を参照し、`is_decoupling=True`のノードを通常の丸マーカーと分けて、Industrial Engineeringの慣習的な「stocker(在庫バッファ)」記号である**逆三角形マーカー**(`node_shape="v"`)で描画するようにした。凡例にも「▽ Buffering Stock (decoupling)」を追加した。

**スコープ**: 本修正は`buffering_stock_flag=1`(静的CSV設定、例: FG_WH_*)のみを対象とする。Step 8 `PushProductionPlanner`のInBound decoupling node(`push_config.csv`で動的に指定されるGarment_BD/PT等)は、実行時にのみ決まる別メカニズムであり、`PlanNode`の静的属性からは判別できないため、今回のスコープには含めていない(Known limitations参照)。

## 5. 動作確認

- `python3 -m py_compile wom/gui/app.py`および`ast.parse()`で構文エラーがないことを確認
- `git diff --stat wom/gui/app.py`で、意図した4箇所の差分(77 insertions / 19 deletions)のみが含まれ、他の意図しない変更がないことを確認
- Tkinter実描画(レイアウトの見た目、逆三角マーカーの表示、World Mapのクリック挙動)はサンドボックス環境にディスプレイがないため未検証。**ユーザー側での実機確認が必要**

## 6. 実装中に発生したインシデント: ファイル破損と復旧(重要、共有事項)

`wom/gui/app.py`への編集作業中、Claudeのサンドボックス(bash)側からファイルを読み書きする経路で、ファイル終端付近(5309行目、文字列リテラルの途中)が切り詰められる破損が発生した。これは編集内容そのものに起因するものではなく、大きめのファイル(約250KB)をこのセッションのFUSEマウント越しに読み書きする際の既知の不具合(過去のセッションでも複数回発生、`AGENTS.md`記載の`tools/gen_apparel_global_model.py`等での事例と同種)によるものと考えられる。

**復旧方法**: 直前にユーザーが`git commit`済みだった`wom/gui/app.py`のHEADバージョン(コミット`e8c45e8`、破損前のクリーンな状態)を`git show HEAD:wom/gui/app.py`で取得し、そこに本レター記載の4件の修正を機械的に再適用する形で、破損のない状態に復旧した。`git diff --stat`で意図した差分のみが残っていることを確認済みで、データ損失はない。

**教訓**: 今後`wom/gui/app.py`のような大きめのファイルを編集する際は、編集直後に`git diff --stat`で差分の妥当性(挿入/削除行数が意図した変更量と一致するか)を確認する運用とする。

## 7. Known limitations

- Step 8 `PushProductionPlanner`のInBound decoupling node(push_config.csv動的指定)はstockerアイコン非対応(4章参照)
- Event Flow Tracing(アニメーション再生、`WorldMapPanel`/`SCNetworkPanel`のアニメーション用の別描画コードパス)には今回のstockerアイコン・World Mapラベル削除の変更を適用していない。静止画表示(E2E Hammockビュー)のみ対象
- Tkinter実描画の見た目はユーザー側実機確認待ち

## 実装への申し送り

- 変更ファイル: `wom/gui/app.py`のみ(ケース非依存、全ケース共通)
- 次のステップ: `python -m main`でGUIを起動し、(a) Managementタブ Node P&Lの`--`表示、(b) SC Networkタブの3段レイアウト、(c) World Mapのラベル非表示+クリック詳細表示、(d) SC NetworkタブでFG_WH_BD/PTが逆三角マーカーで表示されること、をそれぞれ確認
- 確認後、`git add wom/gui/app.py && git commit && git push`
