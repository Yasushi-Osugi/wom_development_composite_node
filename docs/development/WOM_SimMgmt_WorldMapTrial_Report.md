# Run Simulation のときの Management 表示、PPC KPI Summary の文字の重なり、World Map の試作　報告

- 依頼書：`requests/RequestLetter_SimMgmt_WorldMapTrial_to_CodeKun.md`
- 実装：Code君（Claude Code, Windows）、2026-10-01
- ブランチ：`wom-v1r5m1_cap_trial`。**着手時の HEAD：`c84e8ca`**（依頼書の起草時の先頭 `9204bba` ＋依頼書 1 ファイル）
- **commit・push はしていない。** `tools/download_worldmap_tiles.py` は実行していない。
- 計画（Forward／Backward）・PPC の計算・golden は変えていない。保護対象の 6 ファイルには触れていない。今の World Map タブ（`WorldMapPanel`）は変えていない。
- 付表：`docs/development/sim_mgmt_worldmap/`（`bench.json`・画面の画像・GUI の自動確認で読んだ値）

本書は「観測結果／コードで確かめたこと／推定／未確認」を分けて書く。

---

## 0. まとめ

| 区分 | 結果 | 要点 |
|---|---|---|
| 1.1　Run Simulation のときの Management | **合** | Simulation の結果は money の値を出し、出所の欄・上の帯・チャートに「money によるシナリオ比較（PPC ではない）」。Planning の結果は今の規則のまま（今の計画の PPC だけ）。**Simulation の後に Planning を実行すると、表は Planning の行だけになる**（Base/Upside/Downside の money の行は残らない） |
| 1.2　PPC KPI Summary の文字の重なり | **合** | 行の位置を「points」で決め、入らないときは 2 列・文字の縮小・「+N more channel(s)」。4 モデル×3 窓の大きさ×2 SKU の 24 通りで、**重なり 0**（直す前は 6〜11 組） |
| 2　World Map の試作と計測 | 完了（判断は大杉さん） | 案 A（Natural Earth を WOM の中で描く）：地図が出るまで 2.2〜2.6 秒、ズーム・移動 57〜115 ms、週の再生 31〜34 ms（blitting あり）。案 B（今のタイル、ズーム 4 まで、手元の画像だけ）：tkintermapview の設定でできる（ネットワークに出た回数 0）。比較表は §5 |
| 全テスト | **658 passed／3 skipped、失敗 0**（1 回の実行、9 分 54 秒） | 636 → 658 件（Part 1：14、Part 2：8） |
| golden | 変わっていない | 計画・PPC の計算に触れていない。全テストに含まれる golden が緑 |

副作用・気づいたこと（§6）：Run Simulation は、`capacity_plan.csv` に `region` 列のあるモデル（smartphone・smartphone-global-2026-2029・smartx）でしか動かない（前からの制約）。Simulation の失敗の詳細が「NoneType: None」になって消えていたのを直した。

---

## 1. Part 1.1　Run Simulation だけを実行したときの Management

### 1.1 直す前（コードで確かめたこと）

- `WOMApp._on_simulation_done` は `self._mgmt_panel.load(mgr)` を呼ぶだけで、PPC の状態（`_ppc_ctx`）は前のまま。Simulation の経路では PPC が走らないので、表は「PPC 未実行」で数字が空欄（前回の報告書 §1.3 のとおり）。
- さらに、**Planning の後に Simulation を実行すると**、Management の PPC の状態は「今の計画の PPC の結果あり」のまま残り、Simulation の Base/Upside/Downside の行に**前の計画の PPC の台帳の値**が入る経路があった（`_ledger_pl_for_sku` は SKU だけを見て、シナリオを見ない）。
- **Simulation の後に Planning を実行すると**、Planning Engine は Simulation の `ScenarioManager` に「Planning」シナリオを**足す**（`_on_planning_done`、「Merge into existing ScenarioManager」）。今の表示は、どの行にも同じ PPC の台帳の値を入れるので、Base/Upside/Downside の行に Planning の PPC の値が並び、運転資本の列は Simulation の money の値、という混ざった表になっていた。

### 1.2 直し方

| # | 内容 | 場所 |
|---|---|---|
| 1 | Management に「表示している結果」を持たせた（`_display_source`：`plan`／`sim`）。`show_simulation(mgr, model_dir)` で `sim`、`set_ppc_context()`（計画の PPC の状態が来たとき）と `on_model_loaded()` で `plan` | `ManagementCockpitPanel` |
| 2 | **Simulation の結果**：P&L Summary は money の値を出し、出所の欄に「money によるシナリオ比較（PPC ではない）」。Node P&L は 1 行「（Simulation：なし） PPC の台帳から作る表」。Landed Cost は money の値の表と、説明の先頭に出所と「金額は sku_master の価格の通貨（PPC の基準通貨への換算なし）」。CCC・GP のチャートは money の値と、図の中に「出所：money によるシナリオ比較（PPC ではない）」。通貨の記号は付けない（money の通貨は記録されていないため） | `_refresh_pl_table`・`_refresh_node_pl_table`・`_refresh_lc_table`・`_refresh_charts`・`_base_ccy` |
| 3 | **Planning の結果**：表・Landed Cost・チャートに出すのは **Planning のシナリオの行だけ**（`_shown_kpi`）。PPC の値の出し方（今の計画の PPC だけ、無ければ空欄）は変えていない。PPC の台帳を読む 2 つの関数は、`sim` のときは読まない | `_shown_kpi`・`_ledger_pl_for_sku`・`_ledger_lc_overrides` |
| 4 | 上の帯（Management）：`sim` のとき水色で「表示中：Run Simulation の結果｜出所：money によるシナリオ比較（PPC ではない）（Planning Engine・PPC は実行していません）｜モデル：…」 | `_refresh_ppc_banner` |
| 5 | 窓の上の帯：「表示中の結果：Run Simulation（money によるシナリオ比較。Planning Engine・PPC は未実行）」。Planning の結果のときは今までどおり「表示中の計画：<計画 ID>」 | `WOMApp._update_model_display`（`_shown_result`） |
| 6 | Simulation が終わったとき、表示中の計画を手放す（`PPCRunGate.set_current("")`）。**計画の PPC が計算中に Simulation を実行しても、その PPC の結果は後から画面に出ない**。PPC タブは「PPC 未実行」。ただし、Simulation より前に始めた Planning Engine がまだ計算中なら、その計画は「今の計画」のまま（それが終わると、その結果に替わる） | `WOMApp._on_simulation_done` |
| 7 | （副作用の修正）Simulation が失敗したとき、エラーの窓の中身が「NoneType: None」になっていた（`traceback.format_exc()` を `except` の外、後で呼ばれる lambda の中で呼んでいたため）。`except` の中で取るようにした | `WOMApp._simulate_thread` |

### 1.3 受入（観測結果）

`python -m tools.gui_sim_plan_check`：実アプリの窓（`WOMApp`、1536×824。大杉さんの画面で最大化したときの大きさ）で、smartphone-global-2026-2029 を読み込み、画面のボタンと同じ処理で動かして、部品の値を読んだ。エラー 0 件。値は `docs/development/sim_mgmt_worldmap/part1/gui_sim_plan_steps.json`、画像は同じフォルダ。

| 段階 | P&L Summary（シナリオ／Revenue／出所） | Landed Cost の WOM Scen | チャートの横軸 | 上の帯 |
|---|---|---|---|---|
| 1　Run Simulation の完了後 | Base 452,663,505／Downside 369,928,534／Upside 499,937,882、どれも「money によるシナリオ比較（PPC ではない）」 | Base・Downside・Upside（money） | Base・Downside・Upside、出所の文字あり | 水色。表示中：Run Simulation の結果 |
| 2　続けて Run Planning Engine、計画の直後（PPC 計算中） | **Planning の 1 行だけ**：空欄／「PPC 計算中」 | 空 | 「PPC 計算中」 | 黄。PPC 計算中 |
| 3　PPC の完了後 | **Planning の 1 行だけ**：640,773,326,445,600／「PPC 台帳（今の計画）」 | Planning だけ | Planning だけ | 緑。PPC 台帳（今の計画） |
| 4　続けて Run Simulation | 段階 1 と同じ 3 行（PPC の値は残らない） | 3 シナリオ | 3 シナリオ | 水色 |
| 5　Planning の PPC を 8 秒遅らせ、計画が終わった瞬間に Run Simulation | 段階 1 と同じ 3 行 | 3 シナリオ | 3 シナリオ | 水色 |

- 段階 2・3 で、Management に渡る `ScenarioManager` には Base・Upside・Downside・Planning の 4 シナリオがある（Simulation の後の Planning）。表に出るのは Planning だけであることを確かめた（受入の「Simulation の数字が残らない」）。
- 段階 5：画面の記録（0.2 秒ごと）は「Simulation の値 → PPC 計算中（Planning の結果）→ Simulation の値」の 3 つだけ。遅れて終わった PPC の結果（売上 640,773,326,445,600）は**受け取らない**（`accepted: False`）。
- 自動の確認は smartphone-global-2026-2029 で行った。依頼書の例の ev-thailand-2026 は、Run Simulation そのものが動かない（§6.1）。

テスト（`tests/test_sim_mgmt_display.py`）：Management のパネル（Tk）で、Simulation → Planning（PPC 計算中・完了）→ Simulation → モデルの読み込み直し、の順に、表・Landed Cost・Node P&L・チャート・帯の値を確かめる。前回のテスト（`tests/test_ppc_run_info.py`）も変えずに緑。

## 2. Part 1.2　PPC タブの「PPC KPI Summary」の文字の重なり

### 2.1 原因（コードで確かめたこと・観測結果）

`wom/ppc/ppc_cockpit_app.py` の `_draw_kpi_text` は、各行を**パネルの高さに対する割合**（0.95, 0.87, 0.80, … 0.17 − 0.05×i）で置いていた。文字の大きさは points（固定）で、パネルの高さ（ピクセル）は窓の大きさに合わせて縮む。大杉さんの画面（1920×1080・125 %、WOM は DPI を意識しない動作なので 1536×864 として描く）では、パネルは約 200 ピクセルの高さで、行の間隔が文字の高さより狭くなって重なる。バッジは軸の外（y = −0.12）に置かれ、下のパネルの領域にかかっていた。

直す前の版（HEAD の `_draw_kpi_text`）を同じ条件で描き、文字の箱（描いた後の実際の範囲）の重なりを数えた：どのモデル・大きさでも **6〜11 組**が重なる（「PPC KPI Summary」と「Base currency」、「Base currency」と「Lots」、Revenue と Total Cost、チャネルの行どうし）。大杉さんの画面（ev-thailand の EVmaker_Import）と同じ見た目を再現した（`part1/kpi__ev-thailand-2026__before__1536x824__EVmaker_Import.png`）。

### 2.2 直し方

- 各行を、上から **points で**積み上げる（行の高さ＝文字の大きさ×1.3）。パネルの高さに依らず、行どうしは重ならない。
- 入りきらないときの順番（`_kpi_text_layout`）：
  1. 1 列（文字 100〜80 %）
  2. 2 列：左に 8 行（見出し・通貨・Lots・4 つの値・関税）、右に Revenue の行の高さからチャネルの行とバッジ（文字 80 %〜65 %）。右の列の位置は、左の列の文字の幅から決める
  3. 詰めた 1 列：通貨と Lots を 1 行にまとめ、チャネルの行は入る分だけ
  4. それでも入らない（パネルがごく小さい）：パネルの縁で切る（ほかのパネルには描かない）
- 入らないチャネルは、最後の 1 行を「+N more channel(s)」にする（N＝出していない数）。
- **値の行（Revenue など）は縮めない・切らない。** チャネルの名前だけが長すぎるときは、**名前の前の方**を「~」で省く（`~BKK_i 37.12B JPY`。末尾がチャネルを見分ける部分のため）。
- バッジは、行の流れの中（最後の行の下、2 列のときは右の列）に置き、パネルの中で切る（`clip_on=True`）。
- 窓の大きさを変えたときに、この配置をやり直す（`PPCCockpitApp._on_fig_resize`）。
- 図の文字は英語のまま（依頼書の例「ほか N 件」は、このパネルの等幅の字体に日本語の字形が無いため「+N more channel(s)」とした）。

### 2.3 受入（観測結果）

`python -m tools.ppc_kpi_summary_check --before`：モデルごとに headless で PPC の出力を作り、`PPCCockpitApp`（PPC タブの中身と同じ Frame）を窓に置いて描き、Panel 1 の文字の箱の重なりを数えた。結果は `part1/kpi_summary_check.json`。

| モデル（チャネル数） | 窓 1536×824（大杉さんの最大化） | 1280×720 | 1100×640 | 直す前（同じ 3 通り） |
|---|---|---|---|---|
| ev-thailand-2026（6） | 重なり 0・2 列・6 行とも表示 | 0・2 列・6 行 | 0・詰めた 1 列 | 7〜8 組 |
| smartphone-global-2026-2029（9） | 0・2 列・5 行＋「+4 more」 | 0・詰めた 1 列 | 0・詰めた 1 列 | 7〜8 組 |
| apparel-global-2028-2029（4） | 0・2 列・4 行 | 0・2 列 | 0・詰めた 1 列 | 6〜8 組 |
| oil-global-2027（21） | 0・2 列・5 行＋「+16 more」 | 0・詰めた 1 列 | 0・詰めた 1 列 | 7〜8 組 |

- 各モデルで SKU＝All と 1 つの SKU の 2 通り、計 24 通り。**直した後は 24 通りとも重なり 0**。
- 1100×640 は、パネルが 1 つの窓の中で特に小さい場合の確認（最後の手段「縁で切る」が出る。重なりはない）。
- 実アプリの中の PPC タブ（`part1/3_planning_ppc_done__ppc_tab.png`、smartphone-global-2026-2029）は、左に WOM のサイドバーがある分パネルが小さく、「詰めた 1 列」で「+9 more channel(s)」になる。文字は小さいが重ならない。**未確認**：大杉さんの画面で、実際の ev-thailand の EVmaker_Import を開いたときの見え方（自動の確認は同じ大きさの窓で行った）。

テスト（`tests/test_sim_mgmt_display.py`）：4 つのパネルの大きさ×チャネル 0・3・21 本で、各列の行が前の行の高さより下から始まること、値の行が切られないこと、「+N more」があること、2 列のとき列どうしが離れていること。長いチャネル名は末尾が残ること。

## 3. Part 2　World Map の試作

### 3.1 地図データ

| 項目 | 内容 |
|---|---|
| 出典 | Natural Earth（パブリックドメイン）。https://www.naturalearthdata.com/downloads/ 。取得の URL の形は `https://naturalearth.s3.amazonaws.com/{scale}_{category}/ne_{scale}_{name}.zip`（cartopy が使う公式の置き場所） |
| 使ったもの | 海岸線 `ne_{110m,50m,10m}_coastline`、陸の国境線 `ne_{110m,50m,10m}_admin_0_boundary_lines_land`、陸地 `ne_{110m,50m}_land`（塗りつぶし。10m の陸地は使わない） |
| 取得 | **この PC に、cartopy が以前に Natural Earth から取ってきたキャッシュ**（`~/.local/share/cartopy/shapefiles/natural_earth`）があったので、それを使った。**本件でネットワークには出ていない。** 取得日（ファイルの日時）：110m 2025-08-24、50m・10m 2025-08-27 |
| 版 | **ファイルに版の記録が無い**（cartopy は zip の中の `.shp/.shx/.dbf/.prj/.cpg` だけを残し、`VERSION.txt` を残さない）。取得日の時点の Natural Earth の最新版である。ファイルの sha256 を `data/worldmap_ne/SOURCE.json` に記録した |
| 変換の道具 | `tools/build_worldmap_ne.py`（`python -m tools.build_worldmap_ne`）。シェープファイルを読むのは、この道具だけ（pyshp）。キャッシュの無い PC 用に `--download <dir>` を用意したが、**実行していない** |
| 実行時に読むもの | `data/worldmap_ne/ne_110m.npz`・`ne_50m.npz`・`ne_10m.npz`（numpy の配列。経度・緯度の float32、各部分の始まりの位置、範囲）。実行時の追加のライブラリは無い（numpy・matplotlib・pandas・tkinter だけ） |

リポジトリに入るファイルの大きさ：

| ファイル | 大きさ | 点の数（海岸線／国境線／陸地） |
|---|---|---|
| `ne_110m.npz` | 104 KB | 5,136／3,108／5,143 |
| `ne_50m.npz` | 952 KB | 60,538／19,866／60,669 |
| `ne_10m.npz` | 2.95 MB | 412,023／77,305／— |
| `SOURCE.json` | 4 KB | 出典・取得日・ハッシュ |
| 計 | **約 4.0 MB** | |

10m は 2.95 MB で、大きすぎるとまでは考えていない。**git の管理外にする案**：`.gitignore` に `data/worldmap_ne/ne_10m.npz` を足し、各 PC で `python -m tools.build_worldmap_ne` を 1 回実行して作る（Natural Earth のファイルが要る）。10m が無いときは 50m で寄れるところまで表示する作りにする（今の試作は 10m が必要）。**どちらにするかは大杉さんの判断。**

### 3.2 試作の画面

`python -m wom.worldmap_ne [--model ev-thailand-2026|smartphone-global-2026-2029|oil-global-2027] [--lod auto|110m|50m|10m] [--no-blit]`

- 独立した窓（今の World Map タブとは別）。上の帯：モデル、細かさ（auto／固定）、範囲のボタン（World・Asia・Thailand・Bangkok・Nodes）、▶ ⏸ ⏹、blit の切り替え、直前の描画の時間。ホイールでズーム、左ドラッグで移動。
- 地図：陸地の塗り、海岸線、国境線（破線）。投影は Web メルカトル（今のタイルの地図と同じ見え方）で、numpy で読み込み時に 1 回だけ計算する。cartopy などは使わない。
- 拠点：`node_master.csv` の緯度・経度（色は今の World Map タブと同じ）。拠点間の線：`sc_tree_master.csv` の親子と、MOM → supply_point のつなぎ（今のタブと同じ合成）。
- 週の再生：線の太さ（流れの量）と拠点の大きさが週ごとに変わる。**流れは `demand_forecast.csv` から作った需要の流れ**（leaf_out の需要を親へたどって足す。InBound の線には製品の週の需要の合計）。リードタイムのずれ・能力の制約は入っていない。描く速さを測るための試作なので、Planning Engine は動かしていない。計画の結果（lot の流れ）に差し替えるのは、案 A を採る場合の次の段階。
- 速くするための工夫：
  - 細かさはズームで切り替える。**画面 1 ピクセルあたりの経度**で決める（0.15 度より粗い＝110m、0.015〜0.15＝50m、それより細かい＝10m）。窓の形・大きさに依らない。
  - 線は、変換のときに最大 256 点ずつの部分に分けてあり、表示範囲（と、その周り半画面分）に入る部分だけを描く。
  - 地図は起動時に一度読み込み、層ごとに 1 つの LineCollection／PolyCollection で描く。
  - 週の再生は blitting（地図と動かない線を一度描いて画像として取っておき、週ごとには流れの線・拠点・週の文字だけを描き直す）。
- 画面の画像：`docs/development/sim_mgmt_worldmap/screens/`（smartphone の世界全体、oil のアジア、ev-thailand のタイ・バンコク・週の再生の途中、案 B の 3 枚）。

## 4. 計測（大杉さんの Windows PC）

`python -m wom.worldmap_ne.bench`（結果の全部は `docs/development/sim_mgmt_worldmap/bench.json`）。

**画面の条件**：1920×1080、表示倍率 125 %。WOM（`python -m main`）は DPI を意識しない動作なので、窓の中は 1536×864 として描かれ、Windows が拡大して表示する。試作も同じ動作にした。窓 1400×860（地図の部分 1400×約 820）。Python 3.12.3、matplotlib 3.9.2、numpy 1.26.4。

注意：試作で DPI を意識する動作（`SetProcessDpiAwareness(2)`）にすると、matplotlib の図の大きさが窓より大きくなり、地図の右が切れた（図の dpi が 125 になる）。WOM の本体と同じ、意識しない動作では起きない。

### 4.1 起動から地図が出るまで・全体表示の描画

別のプロセスで冷えた状態から、世界全体を表示するまで（3 モデルの範囲。モデルによる差はほぼ無い）。

| 細かさ | 地図が出るまで | うち Python の起動 | import（numpy・matplotlib・Tk） | 地図データの読み込み | 窓と最初の描画 | 全体表示の描画（5 回の中央値） |
|---|---|---|---|---|---|---|
| 110m 固定 | 2.23〜2.32 秒 | 1.23〜1.27 秒 | 0.61〜0.66 秒 | 0.005 秒 | 0.15 秒 | 49〜53 ms |
| 50m 固定 | 2.30〜2.35 秒 | 1.25〜1.28 秒 | 0.62〜0.65 秒 | 0.022 秒 | 0.19〜0.21 秒 | 78〜81 ms |
| 10m 固定 | 2.54〜2.64 秒 | 1.25〜1.29 秒 | 0.62〜0.64 秒 | 0.073〜0.091 秒 | 0.38〜0.40 秒 | **371〜385 ms** |
| auto（3 段階とも読み込む） | 2.34〜2.38 秒 | 1.25〜1.28 秒 | 0.62〜0.63 秒 | 0.10〜0.12 秒 | 0.14〜0.17 秒 | 46〜48 ms（世界は 110m） |

- 起動の時間の半分以上は Python の起動と import で、地図とは関係ない。WOM の本体に組み込む場合は、これらは既に済んでいるので、**地図のための時間は「読み込み 0.1 秒＋最初の描画 0.15 秒」程度**（推定）。
- 10m で世界全体を描くのは遅い（370〜540 ms、測った回によってばらつく。§4.2 の比較では 536〜542 ms）。細かさの切り替えが要る理由。

### 4.2 ズーム・移動（1 回あたり、auto）

その範囲へ移る 1 回（ズーム）と、幅の 10 % ずつの移動 6 回・1.5 倍のズーム 4 回の中央値（ms は描画して画面に出るまで）。3 モデルの範囲。

| 範囲 | 細かさ | 描く部分の数 | その範囲へのズーム | 移動（中央値／95 %） | 1.5 倍ズーム（中央値） |
|---|---|---|---|---|---|
| 世界全体 | 110m | 603 | 78〜84 ms | 79〜83／83〜86 ms | 78〜82 ms |
| アジア全体 | 50m | 1,887 | 108〜115 ms | 105〜109／109〜115 ms | 100〜103 ms |
| 国（タイ） | 50m（寄ると 10m） | 427 | 64〜72 ms | 69〜71／72〜79 ms | 72〜75 ms |
| 都市（バンコクの周り） | 10m | 3 | 57〜58 ms | 57〜67／58〜84 ms | 57〜62 ms |
| 比較：世界全体を 10m 固定 | 10m | 14,611 | — | 536〜542 ms | — |
| 比較：アジア全体を 10m 固定 | 10m | 10,084 | — | 256〜265 ms | — |

- タイの範囲は、窓の横長に合わせて広げると幅が約 28 度になり、1 ピクセルあたり 0.02 度なので 50m になる。1.5 倍寄ると 10m に替わる。
- どの範囲も 1 回 120 ms 以下。ホイールを続けて回すと、1 回ごとに描き直す（間引きはしていない）。

### 4.3 週の再生（1 週あたり）

各 40 週の中央値（95 %）。

| モデル | 拠点の範囲・blitting あり | 拠点の範囲・なし | 世界全体・あり | 世界全体・なし |
|---|---|---|---|---|
| ev-thailand-2026（拠点 14・線 12） | 32.7（34.1）ms | 46.8（50.6）ms | 30.8（33.0）ms | 51.6（55.8）ms |
| smartphone-global-2026-2029（拠点 15・線 10） | 32.9（38.1）ms | 51.9（55.7）ms | 30.7（32.5）ms | 52.1（54.2）ms |
| oil-global-2027（拠点 53・線 45） | 34.2（38.7）ms | 54.7（56.8）ms | 32.4（34.8）ms | 54.4（57.6）ms |

- blitting で 3〜4 割速くなる。どちらでも 1 秒に 15 週以上は描ける（今の World Map の▶の既定の間隔は 1,000 ms）。
- blitting ありでも約 30 ms かかるのは、窓全体（1400×820）の画像を Tk に渡す分（推定）。

### 4.4 メモリ（プロセスの RSS）

| 時点 | MB |
|---|---|
| Python の起動直後 | 88 |
| import の後（地図データの前） | 115〜116 |
| 3 段階を読み込んだ後 | 131 |
| 最初の描画の後（起動の計測、auto） | 158 |
| 3 モデルの全部の操作の後 | 167 |

地図データの分は約 15 MB（投影した float64 の配列）。

## 5. 判断の材料：案 A と案 B

### 5.1 案 B の確認（tkintermapview）

- **設定でできる。** `TkinterMapView(..., database_path=<data/worldmap_cache.db>, use_database_only=True, max_zoom=4)` と `set_tile_server(<CARTO の URL>, max_zoom=4)`。tkintermapview 1.29 のコードで確かめた：`use_database_only=True` のとき、手元に無い画像は空の画像にして、サーバーに取りに行かない。
- 計測：`requests.get` を差し替えて数えた（実際には出さない）。世界・アジア・タイ・バンコクと表示して、**ネットワークに出ようとした回数 0**。ズーム 6 を指定しても 4 で止まる。
- 手元の画像：ズーム 1＝4/4、2＝12/16、3＝40/64、4＝160/256。ズーム 3・4 は、北極・南極に近い行が無い（人の住む範囲は揃っている）。表示した 4 つの範囲では、要る画像はすべて手元にあった。
- 画面の幅 1400 では、tkintermapview の最小のズームが 3 になる（地図が窓を埋める最小のズーム）。**世界全体は一度に入らない**（世界は横 2,048 ピクセル）。
- 表示の時間（画像が揃うまで）：起動 0.6 秒、範囲の切り替え 160〜220 ms（画像は裏のスレッドで読む）。
- 注意（コードで確かめたこと）：`use_database_only=True` でも、データベースのファイルを開けなかったときは、手元を探す処理を飛ばしてサーバーに取りに行く（`request_image` で `db_cursor is None` の場合）。ファイルがあることを起動時に確かめる必要がある。
- 今のタブの手元の画像に、透かしが入っているかは、ズーム 4 の画像を並べて見た範囲では見当たらなかった（全部の画像は見ていない。**未確認**）。

### 5.2 比較表

| 観点 | 案 A：Natural Earth を WOM の中で描く（本試作） | 案 B：今のタイル、ズーム 4 まで、手元の画像だけ |
|---|---|---|
| 操作の速さ | ズーム・移動 57〜115 ms（描き終わってから画面に出る）。週の再生 31〜34 ms（blitting）。起動時の地図の分は約 0.25 秒（推定） | 範囲の切り替え 160〜220 ms（画像は裏で読む）。起動 0.6 秒。週の再生の線は今のタブと同じ仕組み（今回は測っていない） |
| 歯抜けの有無 | どの細かさ・範囲でも無い（データは全世界） | ズーム 1〜4 は人の住む範囲は揃っている。極に近い行は無い。**ズーム 5 以上に寄れない**（タイの国全体くらいまで）。窓の幅によっては世界全体が一度に入らない |
| ネットワークに出ないこと | 出ない（地図はファイルのみ。実行時にネットワークの処理が無い） | 設定で出ない（測って 0 回）。ただしデータベースを開けないときはサーバーに行くので、その確認が要る |
| 見た目 | 海岸線・国境線・陸地の塗りだけ。**国名・都市名・道路は無い**。寄っても線の細かさは 1:1,000 万まで（都市の周りでは、ほぼ何も描かれない） | CARTO の地図：国名・主な都市名がある（英語）。ズーム 4 までなので道路は見えない |
| 保守 | Natural Earth はパブリックドメインで、外部のサービス・料金に左右されない。データは約 4 MB をリポジトリに入れる（または 10m を管理外）。描画のコード（data・model・viewer で約 650 行）を WOM で持つ | 画像を足すには CARTO の API キーが要る（無いと透かし入り）。手元の 313 枚の範囲に固定される。CARTO の画像の利用条件（表示の条件など）は**未確認**。tkintermapview に依存 |
| 今のタブからの変更の量 | 新しい描画に置き換える（ノード・線・アニメーションの描き方を作り直す） | 2 か所の設定（`use_database_only=True`、`max_zoom=4`）と、データベースの有無の確認 |

**どちらにするかは大杉さんが決める。** 今の World Map タブは変えていない。

参考（推定）：案 A に国名を足すなら、Natural Earth の `admin_0_label_points`／`populated_places` から名前を取り、ズームに応じて出す数を絞る作りになる（今回はしていない）。

## 6. 副作用・気づいたこと

1. **Run Simulation は、ev-thailand-2026 など多くのモデルで動かない**（前からの制約）。`WOMInputs.from_files` の `load_capacity_plan` が `capacity_plan.csv` に `region` 列を求めるが、`region` 列があるのは smartphone・smartphone-global-2026-2029・smartx-2027-2029 だけ（ほかは `node_name`）。エラーは「[capacity_plan] Missing required columns: ['region']」。今回は直していない（Simulation の入力の形を決める話のため）。1.1 の自動の確認は smartphone-global-2026-2029 で行った。
2. Simulation の失敗の窓の中身が「NoneType: None」になっていたのを直した（§1.2 の 7）。
3. Planning Engine が Simulation の `ScenarioManager` にシナリオを**足す**作りは変えていない。Charts・KPI Table・Scenario Delta などのタブには、Simulation の後の Planning で、Base/Upside/Downside と Planning が並んで出る（Management だけ、Planning の行に絞った）。
4. Management の「Management Issues & Risks」（シナリオ間の比較の文章）は、依頼書の対象（P&L・Landed Cost・CCC・GP）に入っていないので変えていない。Simulation の後に Planning を実行すると、ここには Simulation の money の比較が残る。
5. 既存の GUI の自動確認の道具（`tools/gui_two_model_check.py` など）は DPI を意識する動作で窓を開く。WOM の本体（意識しない）とは窓の中の大きさが違う。今回の 2 つの道具（`tools/gui_sim_plan_check.py`・`tools/ppc_kpi_summary_check.py`）は本体と同じ、意識しない動作にした。
6. smartphone-global-2026-2029 の `node_master.csv` は、`Retail_*` の 9 拠点に緯度・経度が無い（今の World Map タブでも描かれない）。試作でも描かれない。

## 7. テスト

| 区分 | 件数 |
|---|---|
| 新しいテスト（`tests/test_sim_mgmt_display.py`） | 14（1.1 のパネル 1、1.2 の配置 12＋長い名前 1） |
| 新しいテスト（`tests/test_worldmap_ne.py`） | 8（投影・細かさの選択、データの形と切り出し、部分のつなぎ目、変換の再現性、3 モデルの流れ、画面） |
| 全テスト | **658 passed／3 skipped、失敗 0**（9 分 54 秒。golden を含む） |

途中の版で 1 回、テストの実行中にテストとコードを直したため 1 件が食い違って失敗した。最後の版で、全テストを 1 回通して実行し、上の結果になった。

## 8. 大杉さんが確かめる手順

### Part 1

1. `python -m main` → Load Model Folder で `data\sample\smartphone-global-2026-2029` を選ぶ（ev-thailand では Run Simulation が動かない。§6.1）。
2. **Run Simulation**。Management：帯が水色「表示中：Run Simulation の結果」。P&L Summary に Base・Downside・Upside の 3 行と数字、出所の欄に「money によるシナリオ比較（PPC ではない）」。Landed Cost・CCC・GP のチャートも 3 シナリオ。窓の上の帯に「表示中の結果：Run Simulation」。
3. **Run Planning Engine**。計画が終わると、P&L Summary は **Planning の 1 行だけ**（PPC 計算中は空欄）。PPC が終わると、PPC の台帳の値。
4. もう一度 **Run Simulation** → 3 シナリオの money の値だけに戻る。
5. PPC タブ（Planning の後）：左上の「PPC KPI Summary」の文字が重ならない。SKU を EVmaker_Import（ev-thailand）などに替えても同じ。窓の大きさを変えると、配置がやり直される。

### Part 2（試作）

```
python -m wom.worldmap_ne --model ev-thailand-2026
```

- 上の帯のボタンで World／Asia／Thailand／Bangkok／Nodes。ホイールでズーム、左ドラッグで移動。帯の右に「LOD・描いた部分の数・描画の時間」。
- ▶ で週の再生。「blit」を外すと、週ごとに地図ごと描き直す（遅くなるのを比べられる）。
- モデルは上の帯で smartphone-global-2026-2029・oil-global-2027 に替えられる。

計測をやり直す：`python -m wom.worldmap_ne.bench`（約 3 分。結果は `docs\development\sim_mgmt_worldmap\bench.json` を上書き）。地図データを作り直す：`python -m tools.build_worldmap_ne`（cartopy のキャッシュから。ネットワークに出ない）。

## 9. 変更したファイル・加えたファイル

| ファイル | 内容 |
|---|---|
| `wom/gui/app.py` | 1.1（`ManagementCockpitPanel` の表示の出所、`WOMApp` の Simulation の経路と上の帯）、Simulation の失敗の詳細 |
| `wom/ppc/ppc_cockpit_app.py` | 1.2（`_draw_kpi_text`・`_kpi_text_layout`・`PPCCockpitApp._on_fig_resize`） |
| `wom/worldmap_ne/`（新規） | 試作：`data.py`・`model.py`・`viewer.py`・`bench.py`・`__main__.py` |
| `tools/build_worldmap_ne.py`（新規） | 地図データの変換 |
| `tools/gui_sim_plan_check.py`（新規） | 1.1 の GUI の自動確認 |
| `tools/ppc_kpi_summary_check.py`（新規） | 1.2 の重なりの確認（直す前の版との比較つき） |
| `data/worldmap_ne/`（新規） | 変換したデータ（約 4.0 MB）と `SOURCE.json` |
| `tests/test_sim_mgmt_display.py`・`tests/test_worldmap_ne.py`（新規） | テスト |
| `docs/development/sim_mgmt_worldmap/`（新規） | 計測の結果・GUI の自動確認の値・画像（約 4 MB） |
