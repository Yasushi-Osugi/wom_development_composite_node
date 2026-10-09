# Request Letter：Run Simulation のときの Management 表示、PPC KPI Summary の文字の重なり、World Map の試作

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`
- ブランチ：`wom-v1r5m1_cap_trial`（起草時の先頭 `9204bba`。着手時の SHA を報告書に記録する）
- 種別：GUI の修正（Part 1）と、World Map の試作・計測（Part 2）。計画（Forward／Backward）・PPC の計算・golden は変えない。

---

## Part 1　小さな修正

### 1.1　Run Simulation だけを実行したときの Management

- 今は、Run Simulation だけのとき、P&L Summary の Base・Upside・Downside の行は数字が空欄で、出所の欄は「PPC 未実行」になる（前回の報告書 §1.3）。
- Run Simulation の経路では PPC が走らず、money の値しか無い。1 つの画面に出所の違う数字が混ざる心配が無いので、**money の値を表示し、出所の欄に「money によるシナリオ比較（PPC ではない）」と明記する**。
- 守ること：
  - Planning Engine の結果（PPC）を表示しているときは、今の規則（今の計画の PPC だけ、無ければ空欄）を変えない。
  - Simulation の後に Planning を実行したとき、または Planning の後に Simulation を実行したときに、2 つの出所の数字が同じ表に混ざらないこと。どちらの結果を表示しているかを、上の帯と出所の欄で分かるようにする。
  - Landed Cost・CCC・GP のチャートも、Simulation のときは同じ出所の表示で money の値を出す。
- 受入：Run Simulation → Management で 3 シナリオの数字と出所が出る。続けて Run Planning Engine → PPC の結果だけになる（Simulation の数字が残らない）。自動の GUI 操作で確かめる。

### 1.2　PPC タブの「PPC KPI Summary」の文字の重なり

- PPC タブ（`wom/ppc/ppc_cockpit_app.py` の Panel 1）で、「Base currency」と「Lots」、チャネルごとの売上の行などの文字が重なって読めない（大杉さんの画面、2026-10-01。ev-thailand-2026 の EVmaker_Import）。
- 行数（チャネルの数など）が増えても重ならないように、行の高さ・文字の大きさ・行数に応じた配置を直す。行数が多すぎるときは、スクロールか「ほか N 件」で省略する。
- 受入：チャネルの多いモデル（ev-thailand、smartphone、apparel-global など）のスクリーンショットで、重なりが無いこと。

## Part 2　World Map の試作と計測

### 2.1　背景

- 今の World Map タブは、tkintermapview で CARTO の地図画像（タイル）をネットワークから取っている。2026 年 9 月から CARTO は API キーを必須にし、キーが無いと画像に「API KEY REQUIRED」の透かしが入る。
- WOM は機密情報を扱う Stand Alone の Windows PC で使う前提で、地図画像を取りに行くたびに「どの地域を見ているか」が外部に伝わるのは方針に合わない。
- 手元の `data/worldmap_cache.db` には、ズーム 1〜6 の一部（313 枚）しかなく、寄ると歯抜けになる。
- 本件は、**地図を WOM の中で描く方式**（Natural Earth の海岸線・国境を matplotlib で描く）が、操作に耐える速さかを測る試作である。**今の World Map タブは置き換えない。**

### 2.2　作るもの

1. **地図データ**：Natural Earth（パブリックドメイン）の 3 段階の細かさ（1:110m、1:50m、1:10m）の海岸線と国境線。
   - 取得は 1 回だけ、Windows でネットワークがある時に行う。出典の URL・版・取得日を記録する。
   - 実行時に読むのは、あらかじめ numpy の配列に変換した小さなファイル（例：`.npz`）とする。変換の道具（`tools/` の下）も作る。シェープファイルを読む追加のライブラリが要る場合は、変換の道具だけで使い、WOM の実行時には要らない形にする。
   - リポジトリに入れるファイルの大きさを報告する（10m が大きすぎる場合は、10m だけ git の管理外にする案を示す）。
2. **試作の画面**：独立したウィンドウ（または `python -m` で起動する小さなモジュール）で、次を描く。
   - 地図（投影は numpy で一度計算して終わりにする。cartopy などの重い追加ライブラリは使わない）
   - サンプルモデルの拠点（`node_master.csv` の緯度・経度）と、拠点間の線
   - 週の再生（今の World Map の▶と同じく、週ごとに線や点が変わる）
3. **速くするための工夫**（必須）
   - ズームに応じて細かさを切り替える（引いた画面は 110m、地域は 50m、寄ったときだけ 10m）。10m は表示範囲の分だけを切り出して描く。
   - 地図は起動時に一度読み込み、LineCollection などで**ひとまとめ**に描く（線 1 本ずつ描かない）。
   - 週の再生では、地図の背景を一度描いて画像として取っておき（blitting）、週ごとには拠点と線だけを描き直す。

### 2.3　測るもの（大杉さんの Windows PC で）

| 項目 | 条件 |
|---|---|
| 起動から地図が出るまで | 110m・50m・10m それぞれ |
| 全体表示の描画 | 同上 |
| ズーム・移動（1 回あたり） | 世界全体、アジア全体、国（タイなど）、都市の周り |
| 週の再生（1 週あたり） | blitting あり・なし |
| メモリ | 起動時、読み込み後 |

- 対象のモデル：ev-thailand-2026（拠点が近い）、smartphone-global-2026-2029（世界に広がる）、oil-global-2027。
- 画面の条件（解像度、表示倍率）を記録する。

### 2.4　判断の材料

- 測った結果から、次の 2 案を比べる表を作る。
  - **案 A**：Natural Earth を WOM の中で描く（本試作）
  - **案 B**：今のタイル方式のまま、ズームの上限を 4 にして、手元の画像だけで表示する（ネットワークに出ない設定）。案 B の設定が tkintermapview でできるかも確かめる。
- 比べる観点：操作の速さ、歯抜けの有無、ネットワークに出ないこと、見た目（道路・都市名の有無）、保守（外部のサービスの規約・料金に左右されないか）。
- **どちらにするかは大杉さんが決める。** 今の World Map タブは変えない。

## 守ること

- 計画・PPC の計算・golden を変えない。全テスト緑。
- `tools/download_worldmap_tiles.py` は実行しない（キーが無い今は、透かし入りの画像を保存してしまうため）。
- commit・push はしない。
- 副作用が出ても最後まで行い、報告書に書く。

## 成果物

1. Part 1 のコードの変更とテスト
2. Part 2 の試作のコード、地図データの変換の道具、変換したデータ（大きさ次第で一部を git の管理外に）
3. 報告書 `docs/development/WOM_SimMgmt_WorldMapTrial_Report.md`
   - Part 1 の変更点と画面（Simulation → Planning の切り替え、PPC KPI Summary）
   - Part 2 の計測表、案 A・案 B の比較表、試作の画面のスクリーンショット
   - 大杉さんが試作を起動する手順
