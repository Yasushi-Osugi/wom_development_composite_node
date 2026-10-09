# Request Letter：World Map を案 A に置き換え、実出荷で動かす

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-10-01）
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`
- ブランチ：`wom-v1r5m1_cap_trial`（起草時の先頭 `008d127`。着手時の SHA を報告書に記録する）
- 前提：
  - 試作の報告書 `docs/development/WOM_SimMgmt_WorldMapTrial_Report.md`（大杉さんは**案 A** を採用：Natural Earth を WOM の中で描く）
  - 段階 D 第 1 回 `docs/development/WOM_StageD_Phase1_Report.md`（出荷の記録 `wom/valuechain/records.py`）
- 種別：GUI の置き換え。**計画（Forward／Backward）・PPC・台帳の計算・golden は変えない。保護対象のコアは変えない。**

---

## 0. 目的と方針

- 今の World Map タブ（tkintermapview の地図画像）を、試作の案 A（`wom/worldmap_ne/`）の描き方に置き換える。地図は手元のファイルだけで描き、**実行時にネットワークへ出ない**。
- 流れは、**計画の実出荷**（段階 D の出荷の記録、LOVEM の実出荷と 1 対 1 で一致を確かめたもの）で動かす。今のタブの流れ（EventTimeline の粗い区分）と、試作の流れ（需要から作った流れ）は使わない。
- 出荷の記録を作る関数は `wom/valuechain/records.py` の `build_records()`・`edge_flows()` を**そのまま使う**（同じ流れを 2 か所で作らない）。この関数は台帳のマスター（`vc_*`）が無くても動くので、全モデルで使える。

## 1. 描くもの

### 1.1 地図と拠点

- 地図：試作と同じ（陸地の塗り、海岸線、国境線。細かさはズームで 110m・50m・10m を切り替え。表示範囲の分だけ描く）。
- 拠点：`node_master.csv` の緯度・経度。色は今の `_MAP_NODE_STYLE` と同じ。名前は `node_master` の名前を出す（ズームに応じて重ならないように数を絞ってよい）。
- **supply point は仮想のノード**（グローバル需給センター）として、ほかの拠点と見分けのつく印（例：中抜きのひし形）で描く。物の流れの線は supply point を通さない（下の 1.2）。
- 緯度・経度の無い拠点は描かず、その一覧を画面の隅（押すと一覧）と報告書に出す。smartphone-global-2026-2029 の `Retail_*` 9 拠点は今は座標が無い。代表の地点（例：各地域の代表都市）を案として `node_master.csv` に入れ、どの地点にしたかを `data/sample/smartphone-global-2026-2029/README.md`（無ければ作る）に書く。**代表の地点（仮）**と明記する。

### 1.2 区間（物理の区間だけ）

- 区間は、出荷の記録の**物理の区間**（`Shipment.edge`）だけを描く。MOM → supply point の仮想の受け渡し（`handoff_to_sp`）は物の移動ではないので、流れの線にしない（表示の切り替えで、細い点線として出せるようにしてよい。既定は出さない）。
- `leaf_out → 消費者` の販売は区間の線ではなく、市場の拠点の表示（下の 1.3）に出す。
- 計画を実行する前（モデルを読み込んだだけ）は、`sc_tree_master.csv` から物理の区間（supply point を飛ばして MOM → 最初の DAD を結ぶ）を静止した線で描く。今のタブにある「MOM → supply point の合成の線」は使わない。

### 1.3 週ごとの流れ（Run Planning Engine の後）

区間の線の太さ（と色の濃さ）を、週ごとの lot 数で変える。表示を 2 つ用意し、切り替えられるようにする。

| 表示 | 意味 | 求め方 |
|---|---|---|
| **出荷**（既定） | その週にその区間で出た lot 数 | `ship_week == w` の lot 数 |
| **輸送中** | その週の終わりに、その区間の上にある lot 数 | `ship_week <= w < arrival_week` の lot 数 |

- 「輸送中」は、リードタイムの長い区間（海上輸送など）が太く見え、どこに在庫が乗っているかが分かる。
- 拠点の印の大きさ：その週の在庫（I の lot 数）。市場の拠点（leaf_out）には、その週の販売（消費者への出荷）の lot 数を数字で出す。注文残（CO）がある市場は、赤い輪などで分かるようにする。
- 線の太さの基準（最大の lot 数）は、**計画の全期間の最大**で固定する（週ごとに基準が変わると、太さの比較ができないため）。
- 区間を押すと、その週の lot 数（出荷・輸送中）と、区間の LT を出す。拠点を押すと、今の情報に加えて、その週の P・S・I・CO の lot 数を出す。

### 1.4 操作

- 今のタブにある機能は残す：SKU（製品）の絞り込み、拠点の範囲への自動のズーム、拠点を押したときの情報。
- 試作の機能を入れる：ホイールでズーム、ドラッグで移動、範囲のボタン（World・拠点の範囲）。
- 週の操作：▶ ⏸ ⏹、**週のスライダー**（好きな週へ跳ぶ）、再生の速さ（既定 1 週 ＝ 1,000 ms、選べるようにする）。週の表示は計画の週の名前（例 `2027-W18`）。助走週と報告の期間を区別して表示する。
- 上の帯に、表示している計画 ID と流れの出どころ（「実出荷（出荷の記録）」）を出す。モデルを読み込み直したら流れを消す（今の P1 の規則：表示は今のモデル・今の計画だけ）。

### 1.5 計算の時期

- 出荷の記録は、Run Planning Engine が終わった後に**裏のスレッドで**作る（Cookie で 79 万件ある）。作り終わるまで、地図と静止した線は使え、再生のボタンだけを使えなくしておく。
- Value Chain の台帳と同じ計画のときは、同じ出荷の記録を**使い回す**（2 回作らない）。
- lot_flow_mode が `legacy` のモデル（rice）で実出荷の記録が作れない場合は、流れを出さずに、その理由を帯に出す（計画の S を代わりに使わない。出どころの違う数字を混ぜないため）。作れるかどうかを報告書に書く。

## 2. 今のタブと試作の扱い

- World Map タブの中身を新しい描画に置き換える。WOM の実行時に `tkintermapview` を読み込まないようにする（CLAUDE.md の依存の行からも外す）。
- `data/worldmap_cache.db` と `tools/download_worldmap_tiles.py` は、今回は消さずに残す（使われなくなる。消すかは後で大杉さんが決める）。`tools/download_worldmap_tiles.py` は実行しない。
- 試作の窓 `python -m wom.worldmap_ne` は、描画の速さを測る道具として残す。ただし、その流れは需要から作ったものなので、窓の帯に**「需要の流れ（試作の計測用。計画の結果ではない）」**と出して、実出荷と誤読されないようにする。
- Network タブのアニメーション（EventTimeline）は今回は変えない。

## 3. 受入条件

1. **流れの照合**：Cookie と alloc で、地図が使う区間 × 週の lot 数が、`tools/valuechain_run.py` の `vc_edge_flows.csv` と全行一致する。ev-thailand-2026 では、区間ごとの全期間の lot 数が、LOVEM の観測の実出荷の合計と一致する（観測は今のコードで作り直す：`python -m tools.lovem_observe --model-dir data\sample\ev-thailand-2026 --out output\lovem\ev-thailand-2026\run_worldmap`。前の run は古いコードで作ったため使わない）。
2. **物理の区間**：supply point を通る線が無い。Cookie_Import で、北京の工場から日本の DC（`DC_Import_Buffer`）へ直接の線が出る。
3. **全モデル**：13 の golden のモデル ＋ alloc ＋ ev_update で、読み込み・計画・再生がエラー無く動く。モデルごとに、拠点の数・座標の無い拠点・区間の数・出荷の記録を作った時間・再生 1 週あたりの描画の時間（中央値）を表にする。rice（legacy）の扱いを書く。
4. **ネットワークに出ない**：WOM を起動して World Map を使っても、`tkintermapview` が読み込まれず、地図の画像を取りに行く処理が無いことをテストで確かめる。
5. **計画が変わらない**：golden がすべて変わらない。
6. **古い結果を出さない**：モデルを読み込み直すと流れが消える。別のモデルの計画の流れが残らない（自動の GUI 操作で確かめる）。
7. **全テスト緑**（Tk の不安定なテストは再実行の結果も書く）。

## 4. 守ること

- 保護対象のコア（`backward_planner.py`、`forward_planner.py`、`plan_copy.py`、`plan_node.py`、`sc_tree.py`、`push_pull.py`）を変えない。
- 計画・PPC・台帳の計算を変えない。golden を再生成しない。
- 描画は Tk ＋ matplotlib（Web 系の GUI は使わない）。
- 黙った既定値を作らない（座標が無い、記録が作れない、などは一覧と帯に出す）。
- commit・push はしない。副作用が出ても最後まで行い、報告書に書く。

## 5. 成果物

1. World Map タブの置き換え（コード）とテスト
2. smartphone-global-2026-2029 の `Retail_*` の代表の地点（`node_master.csv`）と README
3. CLAUDE.md の World Map の節の更新（tkintermapview の記述を新しい描画に置き換える）
4. 報告書 `docs/development/WOM_WorldMap_ActualFlows_Report.md`
   - 着手時の SHA、条件
   - 受入 1〜7 の結果、モデルごとの表（§3 の 3）
   - スクリーンショット：Cookie（日本全体と、北京→日本の線）、alloc（日本→米国・欧州、「出荷」と「輸送中」の比較）、smartphone-global-2026-2029（世界全体）、oil-global-2027（中東→日本）、ev-thailand-2026（タイ）。置き場所 `docs/development/worldmap_actual_flows/`
   - 大杉さんが画面で確かめる手順

## 申し送り（今回は扱わない）

- 国名・都市名の表示（Natural Earth の `admin_0_label_points`・`populated_places` を使う案。試作の報告書 §5.2）
- Network タブのアニメーションも実出荷に揃えること
- 区間の線に金額（台帳の運賃・関税など）を重ねて出すこと
