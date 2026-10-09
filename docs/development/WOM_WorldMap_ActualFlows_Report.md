# World Map を案 A に置き換え、実出荷で動かす — 報告書

- 依頼：`requests/RequestLetter_WorldMap_ActualFlows_to_CodeKun.md`
- 前提：試作 `docs/development/WOM_SimMgmt_WorldMapTrial_Report.md`（案 A 採用）、段階 D 第 1 回 `docs/development/WOM_StageD_Phase1_Report.md`（出荷の記録）
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`、ブランチ `wom-v1r5m1_cap_trial`
- **着手時の SHA：`049ac59`**（`049ac593db27f023c2778b37960b97c86dd5f12e`。依頼の起草時は `008d127`、その後に依頼書のコミット）。
  作業中に大杉さんのコミット `308bd5d`（依頼書 3 通の追加のみ）が先頭に入った。後半の計測（受入 1 の vc・LOVEM の run）は `308bd5d`＋未コミットの変更で行った。
- commit・push はしていない。保護対象のコア 6 ファイル・計画・PPC・台帳の計算・golden は変えていない。
- Python 3.12（anaconda）、Windows 11。画面は DPI を意識しない窓 1536×824（`python -m main` と同じ）、画像は PrintWindow。

## 0. 要約

| | 結果 |
|---|---|
| World Map タブ | Natural Earth（手元のデータ）を matplotlib で描く新しいパネル `wom/gui/worldmap_panel.py` に置き換えた。app.py の旧パネル（tkintermapview・タイル、約 620 行）は削除 |
| 流れ | 計画の**実出荷**（段階 D の出荷の記録 `build_records()`）から。表示は「出荷」「輸送中」。EventTimeline・需要・計画の S は使わない |
| 記録の使い回し | 計画の後、app が出荷の記録を裏のスレッドで **1 回だけ**作り、World Map と Value Chain の台帳の両方に渡す |
| 受入 1〜7 | すべて満たした（§3） |
| 座標の無い拠点 | 設計担当の提案（§5）で解決：Stock Yard は親の組立工場の位置に置く規則、rice の node_master の ID を計画の木の名前に、smartphone の i15/i17 の 8 拠点の行を追加。**15 モデルすべてで「座標なし」0** |

---

## 1. 作ったもの

### 1.1 構成

| ファイル | 役割 |
|---|---|
| `wom/worldmap_ne/flows.py`（新規） | `MapLayout`：拠点（node_master の緯度・経度）と物理の区間（sc_tree_master。supply point を飛ばして MOM → supply point の子）。`FlowData`：出荷の記録から 区間 × 週 の「出荷」「輸送中」、拠点 × 週 の P・S・I・CO、市場の販売の lot 数。`records_problem()`：記録に食い違いがあれば流れを出さない理由 |
| `wom/gui/worldmap_panel.py`（新規） | World Map タブの画面。地図（`wom/worldmap_ne/data.py`、試作のもの）、拠点、区間、週の再生、押したときの情報 |
| `wom/gui/app.py` | 旧 `WorldMapPanel` と `_MAP_NODE_STYLE`・`_MAP_LINKS` を削除し、新しいパネルを読み込む。計画の後に `_start_records_job()`（出荷の記録 → 地図の流れ → 台帳）。Run Simulation の後は流れを消す |
| `wom/valuechain/run.py`・`wom/gui/valuechain_panel.py` | `build_ledger(…, records=)`・`start_build(…, records=)`：作ってある出荷の記録を受け取る（同じ計画 ID でなければ止める）。台帳の計算は変えていない |
| `wom/worldmap_ne/viewer.py`・`__init__.py` | 試作の窓に「需要の流れ（試作の計測用。計画の結果ではない）」の帯と、週の文字への注記 |
| `tools/worldmap_flow_check.py`（新規） | 受入 1 の照合（vc_edge_flows.csv・LOVEM） |
| `tools/gui_worldmap_check.py`（新規） | 受入 3・6 とスクリーンショット（実アプリの窓で、全モデルを読み込み → 計画 → 再生） |
| `tests/test_worldmap_actual_flows.py`（新規） | 11 件（§3-7） |
| `data/sample/smartphone-global-2026-2029/node_master.csv`・`README.md`（新規） | `Retail_*` 9 拠点の代表の地点（仮） |
| `CLAUDE.md` | World Map の節・依存の行・注意事項を書き換え、末尾に本件の節 |

### 1.2 描くもの（依頼 §1）

- **地図**：試作と同じ（陸地・海岸線・国境線、110m／50m／10m をズームで切り替え、表示範囲の分だけ）。実行時にネットワークへ出ない。
- **拠点**：`node_master.csv` の緯度・経度。色は旧パネルの `_MAP_NODE_STYLE` と同じ。node_master の種類が色の表に無い拠点（smartphone の `retail`、`supply_point` など）は、計画の木の役割（leaf_out → 市場の赤 など）の色にし、「座標なし」の一覧の「色の注記」に出す。名前は node_master の `node_name`。重なる名前は、MOM・DC を優先して出し、残りは隠す（ズームで変わる）。
- **supply point**：中抜きのひし形（仮想のノード）。物の流れの線は supply point を通らない。押すと「supply point は仮想のノード：物はここに来ない」と出る。
- **座標の無い拠点**：描かない。帯の右の「座標なし N・描けない区間 M」を押すと一覧が出る（§4.2）。
- **区間**：出荷の記録の物理の区間（`Shipment.edge`）だけ。MOM → supply point の仮想の受け渡しは、「MOM→supply point（仮想の受け渡し）」に印を付けたときだけ細い点線で出す（既定は出さない）。`leaf_out → 消費者` は線にせず、市場の拠点に販売の lot 数を数字で出す。
- **計画の前**：sc_tree_master から物理の区間を静止した線で描く。旧パネルの「MOM → supply point の合成の線」は使わない。
- **日付変更線**：太平洋をまたぐ区間（日本 → 米国など）は、180 度の線で 2 本に分けて描く（地図の上を逆回りに横切らない）。

### 1.3 週ごとの流れ

| 表示 | 意味 | 求め方（`FlowData`） |
|---|---|---|
| **出荷**（既定） | その週にその区間で出た lot 数 | `ship_week == w` |
| **輸送中** | その週の終わりに区間の上にある lot 数 | `ship_week <= w < arrival_week`。計画の期間の後に着く出荷は期間の終わりまで。LT 0 の出荷は数えない |

- 線の太さと色の濃さは lot 数による。基準（最大）は**計画の全期間の最大で固定**（表示ごと・SKU の絞り込みごと）。
- 拠点の印の大きさはその週の在庫（`psi4supply[w][I]` の lot 数）。市場はその週の販売の lot 数を数字で出し、注文残（CO）があれば赤い輪を付ける。
- 区間を押すと、その週の出荷・輸送中の lot 数、LT（マスター）、実測の LT（到着週 − 出荷週の中央値）を出す。拠点を押すと、拠点の情報に加えて、その週の P・S・I・CO の lot 数を出す。
- 操作：
  - SKU の絞り込み
  - World・拠点の範囲のボタン
  - ホイールでズーム、ドラッグで移動
  - ▶ ⏸ ⏹、週のスライダー（好きな週へ跳ぶ）
  - 1 週の速さ（250・500・1000・2000 ms、既定 1000）
  - 週の表示（例 `2027-W18（報告）`）は、助走と報告を区別する
- 報告の開始週は `vc_config.csv` の `report_start`、無ければ最初の非ゼロ需要週。⏹ はこの週へ戻る。
- 上の帯：表示中の計画 ID、流れの出どころ「実出荷（出荷の記録 N 件）」、報告の開始週、`lot_flow_mode`。

### 1.4 計算の時期と使い回し

- Run Planning Engine の完了後、app の `_start_records_job()` が裏のスレッドで出荷の記録と `FlowData` を作る。作り終わるまで、地図と静止した線は使え、再生の操作だけを使えなくしておく。
- できた記録を、そのまま Value Chain の台帳（`start_build(…, records=records)`）に渡す。**同じ計画で 2 回作らない**。
- 記録に食い違い（`records.issues`）があれば流れを出さず、帯に理由を出す。計画の S を代わりに使わない。

---

## 2. 今のタブと試作の扱い

- World Map タブの中身を新しいパネルに置き換えた。WOM の実行時に `tkintermapview` を読み込まない（受入 4）。CLAUDE.md の依存の行からも外した。
- `data/worldmap_cache.db` と `tools/download_worldmap_tiles.py` は消さずに残した（使われない）。`download_worldmap_tiles.py` は実行していない。
- 試作の窓 `python -m wom.worldmap_ne` は、描画の速さを測る道具として残した。窓の上に「需要の流れ（試作の計測用。計画の結果ではない）　｜　計画の実出荷の流れは WOM の World Map タブ（Run Planning Engine の後）で見る」の帯を出し、週の文字にも同じ注記を付けた。
- `wom/worldmap_ne/bench.py` の案 B の計測（6 番）だけは tkintermapview を読み込む。これは手で実行する計測の道具で、WOM の画面からは呼ばれない。
- Network タブのアニメーション（EventTimeline）は変えていない。

---

## 3. 受入条件

| # | 条件 | 結果 |
|---|---|---|
| 1 | 流れの照合 | **満たす**（§3-1） |
| 2 | 物理の区間 | **満たす**：supply point を通る線は 0 本（全モデル。テストで Cookie を確認）。Cookie_Import で北京の工場 `Factory_GP_CN` → `DC_Import_Buffer`（横浜）へ直接の線（画像 `cookie_import_beijing_japan.png`、区間を押した情報：LT 5 週・実測 5 週） |
| 3 | 全モデル | **満たす**：15 モデルで読み込み・計画・再生がエラー無く動いた（§3-3） |
| 4 | ネットワークに出ない | **満たす**（§3-4） |
| 5 | 計画が変わらない | **満たす**：golden 13 件が通った（§3-7）。計画・PPC・台帳のコードは変えていない |
| 6 | 古い結果を出さない | **満たす**（§3-6） |
| 7 | 全テスト緑 | **満たす（Tk の不安定な 1 件は再実行で緑）**（§3-7） |

### 3-1 流れの照合（受入 1）

`tools/worldmap_flow_check.py`。地図の数字は World Map と同じ関数（`build_records` → `FlowData`）で作り、計画は照合相手と同じプラグインで headless に立てた。

**Cookie と alloc：地図の 区間 × 週 の lot 数 ＝ `vc_edge_flows.csv`**（今のコードで `tools.valuechain_run` を作り直した run：`output/worldmap_check/vc/<model>`）

| モデル | vc の行 | 地図の行 | 食い違い | lot 数（vc ＝ 地図） |
|---|---:|---:|---:|---:|
| Cookie-jp-2026 | 1,142 | 1,142 | **0** | 504,900 |
| soysauce-jpy-2027-alloc | 1,205 | 1,205 | **0** | 376,455 |

**ev-thailand-2026：区間ごとの全期間の lot 数 ＝ LOVEM の観測の実出荷**

観測は依頼のとおり今のコードで作り直した（`python -m tools.lovem_observe --model-dir data\sample\ev-thailand-2026 --out output\lovem\ev-thailand-2026\run_worldmap`、identity）。LOVEM の側は出荷の記録を使わず、LOVEM の事象と関係だけから区間を作った。
- 受け手：`arrival` の事象（`detail.from_node_id` が送り手）
- supply point から出た lot の物理の送り手：`ship_to_bridge` の関係から、その lot を supply point に渡した MOM

| 製品 | 区間 | LOVEM | 地図 |
|---|---|---:|---:|
| EVmaker_Import | Components_CN → Factory_Import_CN | 10,540 | 10,540 |
| EVmaker_Import | Factory_Import_CN → DC_EV_Import | 10,540 | 10,540 |
| EVmaker_Import | DC_EV_Import → Sales_TH_BKK_i | 5,265 | 5,265 |
| EVmaker_Import | DC_EV_Import → Sales_TH_PRO_i | 4,216 | 4,216 |
| EVmaker_Import | DC_EV_Import → Sales_TH_ONL_i | 1,059 | 1,059 |
| EVmaker_Local | Battery_CN → Factory_Local_TH | 52,700 | 52,700 |
| EVmaker_Local | Factory_Local_TH → DC_EV_Local | 52,700 | 52,700 |
| EVmaker_Local | DC_EV_Local → Sales_TH_BKK | 26,355 | 26,355 |
| EVmaker_Local | DC_EV_Local → Sales_TH_PRO | 21,080 | 21,080 |
| EVmaker_Local | DC_EV_Local → Sales_TH_ONL | 5,265 | 5,265 |

10 区間すべて一致。計画の期間の後に着く出荷（LOVEM に `arrival` が無いもの）は、このモデルでは 0 件で、地図の側も 0 件。

### 3-3 全モデル（受入 3）

`python -m tools.gui_worldmap_check --shots`。実アプリの窓で、モデルごとに Load Model Folder → Run Planning Engine → 流れが出るまで待つ → PPC・台帳の完了を待つ → 報告の開始週から 40 週を `set_week` で描いて 1 週の時間を測る → ▶ で 3 週再生 → 拠点を押す。プラグインは GUI の既定（すべて OFF）。

| モデル | 拠点（描いた） | 座標なし | 区間（静止） | 区間（実出荷あり） | 描けない区間 | 出荷の記録 | 記録を作った時間 | 1 週の描画（中央値／95%） | 輸送中の表示 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cookie-jp-2026 | 12 | 0 | 11 | 11 | 0 | 788,880 | 5.5 s | 22.1／25.2 ms | 22.5 ms |
| apparel-global-2028-2029 | 20 | 0 | 16 | 16 | 0 | 1,452,208 | 13.2 s | 23.0／26.2 ms | 21.4 ms |
| apparel-us-2026 | 14 | 0 | 80 | 80 | 0 | 1,245,860 | 9.7 s | 22.2／25.8 ms | 24.1 ms |
| bom-test-2026 | 6 | 2 | 2 | 6 | 4 | 800 | 0.0 s | 17.2／22.4 ms | 18.7 ms |
| ev-europe-2026 | 18 | 6 | 8 | 20 | 12 | 531,400 | 4.8 s | 23.2／25.9 ms | 23.6 ms |
| ev-thailand-2026 | 14 | 0 | 10 | 10 | 0 | 316,200 | 2.8 s | 24.3／26.3 ms | 24.6 ms |
| smartphone-global-2026-2029 | 24 | 8 | 14 | 25 | 14 | 2,383,854 | 25.1 s | 26.9／30.4 ms | 28.0 ms |
| oil-global-2027 | 53 | 0 | 37 | 37 | 0 | 955,145 | 8.4 s | 28.4／31.7 ms | 27.7 ms |
| rice-japan-2027-2028（legacy） | 15 | 15 | 0 | 20 | 20 | 763,253 | 16.3 s | 16.2／23.4 ms | 19.7 ms |
| smartx-2027-2029 | 42 | 0 | 26 | 26 | 0 | 4,312,256 | 44.9 s | 21.0／25.3 ms | 20.3 ms |
| soysauce-eu-2027 | 15 | 0 | 13 | 13 | 0 | 703,507 | 7.6 s | 19.3／25.6 ms | 19.6 ms |
| soysauce-jpy-2027 | 15 | 0 | 13 | 13 | 0 | 703,507 | 8.3 s | 19.7／25.4 ms | 18.7 ms |
| soysauce-us-2027 | 15 | 0 | 13 | 9 | 0 | 703,500 | 6.2 s | 17.2／19.1 ms | 17.1 ms |
| soysauce-jpy-2027-alloc | 15 | 0 | 13 | 13 | 0 | 536,641 | 6.5 s | 16.6／18.2 ms | 16.5 ms |
| ev-thailand-2026_update | 15 | 2 | 9 | 13 | 4 | 474,300 | 4.7 s | 17.4／18.6 ms | 17.7 ms |

- 「区間（静止）」は計画の前に描く線（両端に座標がある物理の区間）。「区間（実出荷あり）」は計画の実出荷のある物理の区間。両者の差は、描けない区間と、実出荷の無い区間（soysauce-us は欧州の需要が 0 なので、欧州への 4 区間に出荷が無い）。
- 記録を作る時間は、計画の完了後の裏のスレッドの時間（PPC と並行）。その間も地図は動かせる。
- 1 週の描画は blitting で、どのモデルも 30 ms 前後（1 週 ＝ 1,000 ms の再生に対して十分に小さい）。
- alloc の出荷の記録が段階 D の CLI（527,037 件）と違うのは、GUI の既定のプラグイン（すべて OFF）で計画したため（段階 D 第 1 回の報告書 §8 と同じ）。

**rice（lot_flow_mode = legacy）の扱い**
- legacy の計画でも、出荷の記録は**食い違い 0 件で作れた**（763,253 件）。依頼 §1.5 の「作れない場合」には当たらないので、流れを出し、帯に `lot_flow_mode legacy` と出している。
- ただし rice の `node_master.csv` は node_id の体系が計画の木と違う（例：`OUT:leaf_out:KANTO:Retail` ⇔ 木の `Retail_KANTO`、`IN:mom:Sanchiku_Niigata:Koshihikari` ⇔ `Sanchiku_Niigata`）。そのため木の 15 拠点がすべて「座標なし」になり、区間は 1 本も描けない（拠点の印だけが出る、画像 `rice-japan-2027-2028__0_loaded.png`）。
- ID の対応を推測で作ることはしなかった（黙った既定値になるため）。→ §5 で node_master の ID を揃えて解決した。
- legacy の記録は LOVEM との照合をしていない（受入 1 の照合は identity の 3 モデル）。

### 3-4 ネットワークに出ない（受入 4）

`tests/test_worldmap_actual_flows.py::test_no_tkintermapview_and_no_network`。別のプロセスで次を確かめた。
- 準備：`socket.connect`・`create_connection`・`getaddrinfo`・`urllib.request.urlopen` を、呼ばれたら記録して失敗させるものに差し替える。
- 操作：WOM の画面（`WOMApp`）を作り、World Map で Cookie を読み込んで、World・拠点の範囲・東京湾の拡大（10m のデータ）まで表示する。
- 結果：`tkintermapview` は `sys.modules` に無い。ネットワークの呼び出しは 0 回。
- あわせて `test_app_source_has_no_tile_map` で、app.py と新しいパネルに tkintermapview の import、タイルのサーバーの設定、タイルの URL が無いことを確かめた。

### 3-6 古い結果を出さない（受入 6）

- **自動の GUI 操作**：`tools/gui_worldmap_check.py` で 15 モデルを順に読み込み・計画した。0.2 秒ごとに、帯・表示中の流れの計画 ID・画面の計画 ID・モデルを記録した（`output/worldmap_check/all/steps.json` の history、変化のあった 46 行）。
  - 流れの計画 ID が、そのときのモデル・画面の計画 ID と違う行は **0 行**。
  - どのモデルでも、読み込み直した直後は流れが無い（`flows_after_load = False`）。
- **テスト**：`test_panel_ignores_other_plans_and_clears_on_reload`。
  - 別の計画 ID の流れは表示しない。
  - 記録を作っている間は ▶ を押せない。
  - モデルを読み込み直す（`clear_timeline`）と流れが消える。
  - 記録に食い違いがあるときは、帯に「流れを出しません」と理由を出す。
- **Run Simulation の後**：流れを消し、帯に「Run Simulation の結果には実出荷の記録がありません」と出す。

### 3-7 テスト（受入 5・7）

- 新規 `tests/test_worldmap_actual_flows.py`：11 passed。
  - 区間 × 週の数え方（出荷・輸送中・LT 0・期間の後に着く出荷）
  - 受け渡しと販売を線にしないこと
  - 食い違いのある記録を描かないこと
  - 日付変更線
  - Cookie の物理の区間
  - 座標の無い拠点の一覧
  - smartphone の代表の地点
  - Cookie の計画 → 地図の数字 ＝ edge_flows
  - 受入 4・6
- 全体：`python -m pytest tests/ -q -p no:cacheprovider`（ほかの処理と並べずに 1 回で実行）

  ```
  1 failed, 697 passed, 6 skipped  (19 分 22 秒)
  FAILED tests/test_merit_order_plot.py::test_plot_parallel_coordinates
    _tkinter.TclError: Can't find a usable tk.tcl in the following directories: ...
  ```

  落ちた 1 件は Tk の初期化の失敗。段階 D 第 1 回と同じテストで、同じ不安定さ。**このファイルだけを再実行すると `10 passed`**。golden 13 件は通った（再生成していない）。

---

## 4. 記録と一覧

### 4.1 スクリーンショット（`docs/development/worldmap_actual_flows/`）

| 画像 | 内容 |
|---|---|
| `cookie_japan_all.png` | Cookie・日本全体・All・出荷。supply point（中抜きのひし形）を押した情報 |
| `cookie_import_beijing_japan.png` | Cookie_Import・北京 → 日本。北京の工場 → `DC_Import_Buffer` の直接の線を押した情報（LT 5 週、その週の出荷 675・輸送中 3,375 lot） |
| `alloc_world_ship.png`・`alloc_world_transit.png` | alloc・日本 → 米国（太平洋を渡る線）・欧州。同じ週の「出荷」と「輸送中」の比較。海上の長い区間は輸送中で太くなる |
| `smartphone_world.png` | smartphone・世界全体（中国・インド → 米州・欧州・アジアの DC → 代表の地点（仮）の販売） |
| `oil_middleeast_japan.png` | oil・Gasoline_Local・中東 → 日本・輸送中（タンカーの区間が最も太い） |
| `ev_thailand.png` | ev-thailand・タイ（中国の電池・部品の工場 → タイ） |
| `Cookie-jp-2026__0_loaded.png` | 計画の前（静止した線だけ。再生のボタンは押せない） |
| `rice_japan.png`・`ev_europe_yards.png`・`bom_test_yards.png` | §5 で直した後（rice の区間、親の位置に置いた Stock Yard） |

### 4.2 座標の無い拠点（最初の実装の時点。§5 で解決）

| モデル | 拠点 | 理由 |
|---|---|---|
| bom-test-2026 | Battery_Yard, Tire_Yard | node_master に行が無い（Stock Yard） |
| ev-europe-2026 | Battery/ECU/Motor の DE・HU の Yard（6） | 同上 |
| ev-thailand-2026_update | Motor_Unit_Assy_Yard, Platform_Unit_Assy_Yard | 同上 |
| smartphone-global-2026-2029 | DC_AMER/EMEA/APAC の _i15・_i17（6）、EMS_A_CN_i15・_i17 | 同上（`data/sample/smartphone-global-2026-2029/README.md`） |
| rice-japan-2027-2028 | 計画の木の 15 拠点すべて | node_master の node_id の体系が違う（§3-3） |

Stock Yard の区間（部材 → Yard → 組立）は、Yard に座標が無いので描けない。部材の工場 → 組立の工場の流れが地図から消える（ev-europe・bom-test・ev_update）。

---

## 5. 座標の無い拠点の解決（設計担当の提案、2026-10-06）

最初の実装（§3-3 の表）では、4 モデルに座標の無い拠点が残った。設計担当の Claude 君の「おすすめ」のとおりに直した。

| # | 論点 | 対応 |
|---|---|---|
| 1 | Stock Yard の座標 | **描画の規則**（`flows.py`）：計画の木で `node_type = stockyard` の拠点に座標が無ければ、親の組立工場の位置に置き、一覧の「親の位置に合わせた拠点」と、押したときの情報に「親の … の位置に合わせた」と出す。node_master に座標を書いた場合はそちらを使う。親が製品ごとに違う、または親にも座標が無い Yard は、今までどおり「座標なし」に残す。名前から推測しない（`_Yard` という名前ではなく `node_type` で判定）。対象：bom-test 2・ev-europe 6・ev_update 2 |
| 2 | rice の node_master の ID | `node_id` を計画の木の名前に揃えた（15 行。例 `OUT:leaf_out:KANTO:Retail` → `Retail_KANTO`、`IN:mom:Sanchiku_Niigata:Koshihikari` → `Sanchiku_Niigata`）。ほかの列は変えていない。**golden（rice）は変わらない**ことを確かめた（node_master を読むのは World Map だけ）。`lane_assignment.csv` の `IN:mom:…` は計画のエンジンの node_id で、node_master とは別の体系なので変えていない |
| 3 | smartphone の i15・i17 の拠点 | node_master に 8 行を追加（`DC_*_i15/_i17`・`EMS_A_CN_i15/_i17`）。座標は Phone16 の同じ名前の拠点と同じ。**golden（smartphone）は変わらない** |
| 4 | smartphone の Retail の代表都市 | New York・London・Tokyo のまま |

**直した後の 5 モデル**（`python -m tools.gui_worldmap_check --models rice-japan-2027-2028,smartphone-global-2026-2029,bom-test-2026,ev-europe-2026,ev-thailand-2026_update --shots`、エラー 0）

| モデル | 拠点（描いた） | 座標なし | 親の位置 | 区間（静止） | 区間（実出荷あり） | 描けない区間 | 出荷の記録 | 記録の時間 | 1 週の描画（中央値／95%） |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rice-japan-2027-2028 | 15 | 0 | 0 | 20 | 20 | 0 | 763,253 | 19.5 s | 29.4／36.0 ms |
| smartphone-global-2026-2029 | 32 | 0 | 0 | 28 | 25 | 0 | 2,383,854 | 32.4 s | 32.1／43.1 ms |
| bom-test-2026 | 8 | 0 | 2 | 6 | 6 | 0 | 800 | 0.0 s | 27.7／39.6 ms |
| ev-europe-2026 | 24 | 0 | 6 | 20 | 20 | 0 | 531,400 | 8.3 s | 35.8／51.5 ms |
| ev-thailand-2026_update | 17 | 0 | 2 | 13 | 13 | 0 | 474,300 | 7.3 s | 29.8／37.9 ms |

- smartphone の静止の区間 28 と実出荷のある区間 25 の差の 3 本は、この計画で実出荷の無い区間。
- この回の描画時間は、§3-3 の回より 5〜12 ms 長い。同じパソコンで別の処理が動いていた可能性があり、描画のコードは変えていない。いずれも 1 週 ＝ 1,000 ms の再生に対して十分に小さい。
- 画像：`rice_japan.png`（rice の区間が描けた）、`smartphone_world.png`（Phone15・17 の流れを含む）、`ev_europe_yards.png`（部材の工場 → 組立工場。Yard は組立工場の位置）、`bom_test_yards.png`。
- テスト：`test_stock_yard_is_drawn_at_its_plant`、`test_rice_and_smartphone_all_nodes_on_the_map` を追加。`test_missing_coordinates_are_listed_not_guessed` は、DC の座標を消したモデルで「推測せずに一覧に出す」を確かめる形に書き換えた。

## 6. 大杉さんが画面で確かめる手順

1. `python -m main`（起動時は World Map タブ。地図は手元のデータだけで出る）
2. Load Model Folder… で `data/sample/Cookie-jp-2026` を選ぶ。
   - 拠点と、計画の前の静止した線が出る。▶ は押せない。
   - 帯の右「座標なし 0」。
3. Run Planning Engine。帯が「出荷の記録を作成中…」になる。
4. 数秒後に、帯が「計画 ID：…　｜　流れ：実出荷（出荷の記録 N 件）」になる。▶ とスライダーが使えるようになる。
5. ▶ で再生する。スライダーで好きな週へ跳ぶ。「1 週 =」で速さを変える。
   - 週の表示の（助走）（報告）で期間を見分ける。⏹ は報告の開始週へ戻る。
6. 「表示」を「出荷」⇔「輸送中」に切り替える。中国 → 日本の線は、輸送中で太くなる。
7. SKU で `Cookie_Import` を選ぶ。北京の工場 → 横浜の DC（`DC_Import_Buffer`）への直接の線を押すと、その週の出荷・輸送中の lot 数と LT が出る。
8. 拠点を押すと、その週の P・S・I・CO の lot 数が出る。ひし形の supply point は「仮想のノード：物はここに来ない」。
9. 「MOM→supply point（仮想の受け渡し）」に印を付けると、受け渡しが細い点線で出る。
10. ホイールでズームし、ドラッグで移動する。寄ると海岸線が細かくなる。World・拠点の範囲のボタンで戻る。
11. 別のモデル（例 `soysauce-jpy-2027-alloc`）を読み込む。前の流れが消えて、静止した線に戻ることを確かめる。
12. Run Simulation を押す。帯が「Run Simulation の結果には実出荷の記録がありません」になる。

照合を自分で行うとき：

```powershell
python -m tools.valuechain_run --model-dir data/sample/Cookie-jp-2026 --out output/worldmap_check/vc/Cookie-jp-2026
python -m tools.worldmap_flow_check --model-dir data/sample/Cookie-jp-2026 --vc-run output/worldmap_check/vc/Cookie-jp-2026
python -m tools.gui_worldmap_check --models Cookie-jp-2026,soysauce-jpy-2027-alloc --shots
```

## 申し送り（依頼のとおり、今回は扱っていない）

- 国名・都市名の表示（Natural Earth の `admin_0_label_points`・`populated_places`）
- Network タブのアニメーションを実出荷に揃えること
- 区間の線に金額（台帳の運賃・関税など）を重ねること
