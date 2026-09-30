# Request Letter：Management の古い PPC 値の表示、units の二重計上、Kitting の照合の表示、ステータス行

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`
- ブランチ：`wom-v1r5m1_cap_trial`（起草時の先頭 `5c58cfb`。着手時の SHA を報告書に記録する）
- 種別：GUI・評価（money）の修正と表示の追加。計画（Forward／Backward）は変えない。
- 前提：`docs/development/WOM_iPhoneWarmup_EVUpdateKitting_S2_Report.md`（途中で見つけたこと、判断を仰いだ点）

---

## 0. 背景

大杉さんが `python -m main` で確かめた画面（2026-09-30）で、次の 2 つが見つかりました。

1. **Management の P&L Summary と Landed Cost の Revenue が、iphone_global を読み込んでいるのに、前に読み込んだモデルの PPC の値を出していた。**
   - 画面の値：Revenue 319,119,580,000、Gross Margin 56.5%。これは ev-thailand（または ev_update）の PPC の値（3,191.2 億、56.50%）と一致する。iphone の PPC の売上は 641.0 兆円（報告書 A）。
   - 同じ画面の Node P&L（拠点別損益）は iphone のノードを出している。1 枚の画面に、2 つのモデルの数字が混ざっていた。
   - コードの読み（Claude君）：`wom/gui/app.py` の P&L Summary は、`output/ppc/ppc_kpi_summary.json` があればその値で上書きする（l.1205 付近）。このファイルには、どのモデル・どの計画の結果かを確かめる仕組みが無い。PPC は計画の後に別スレッドで動く（l.5930 付近）ので、iphone の PPC が終わる前、または失敗したときに、前のモデルのファイルが読まれた可能性がある。
2. **ev-thailand-2026_update の Flow Check が、置場（Stockyard）の無い古い構成で表示された。** 原因は、大杉さんが別のフォルダ（古いコピー）のモデルを読み込んでいたことで、最新のフォルダを読み込み直すと NG は消えた（2026-09-30 確認）。コードの不具合ではないが、**どのフォルダのモデルを読み込んでいるかが画面から分かりにくい**ことは、同じ見誤りを招く。

どちらも「画面の数字を見誤る」種類の問題なので、先に直します。

## 1. 依頼の内容

### P1　Management と PPC の表示が、今のモデル・今の計画の結果であることを保証する（最優先）

- PPC の出力（`ppc_kpi_summary.json` など）に、どのモデル（モデルのフォルダ）・どの計画（計画の実行ごとの識別子。例：時刻＋モデル名）の結果かを書き込む。
- Management・PPC タブ・Landed Cost が PPC の出力を読むときは、今読み込んでいるモデルと今の計画の識別子に一致するかを確かめる。一致しない場合は、**前の値を出さずに**、「PPC 計算中」「PPC 未実行」「PPC 失敗」のどれかを表示する。money の値で代用する場合は、「money による値（PPC ではない）」と分かるように表示する。
- モデルを読み込み直したとき、前のモデルの PPC の表示を消す。
- PPC が別スレッドで終わったとき、Management の P&L Summary と Landed Cost も更新する（今は PPC タブと Node P&L だけが更新されている可能性がある。確かめて報告する）。
- 受入：ev-thailand-2026 を読み込んで計画 → iphone_global を読み込んで計画、の順に操作したとき、iphone の PPC が終わるまで ev-thailand の値が出ない。終わった後は iphone の値（報告書 A の 641.0 兆円）が出る。自動の GUI 操作で確かめ、手順を報告書に書く。

### P2　どのフォルダのモデルを読み込んでいるかを、画面から分かるようにする

- 今は、左の欄に `ev-thailand-2026_update/` のようにフォルダ名の末尾だけが出る。同じ名前のモデルが別のフォルダ（古いコピーなど）にあると、見分けられない。
- 次のどれか（組み合わせでもよい。判断は任せる）で、読み込んだモデルのフォルダの**フルパス**が分かるようにする。
  - ウィンドウのタイトルか、ステータス行に、フルパスを出す。
  - Flow Check・Management の見出しに、モデル名とフォルダを出す。
  - 作業フォルダ（`wom-v1r5m1_cap_trial`）の外のモデルを読み込んだときは、目立つ表示にする。
- 計画を実行するときに、実際に使った `sc_tree_master.csv` のパスを、ステータス行かログに 1 行出す。
- 「Load Model Folder」でモデルを読み込んだとき、SC Tree Master・Edge Cost Master・Route Master の欄が、そのモデルのフォルダのファイルに置き換わることを、テストで確かめる。

### P3　ステータス行の「PPC complete (sample data)」

- 今は、PPC の結果の `_psi_mode` を読んでいるが、どこも書いていないので、いつも「sample data」と表示される（前の報告書の「途中で見つけたこと」）。
- PPC の入口（`ppc_runner.py`）が、PSI から作った販売記録を使ったのか、サンプルの販売データに差し替えたのかを、実際に記録して表示する。差し替えた場合は、目立つ警告にする（PSI と PPC の数字が対応していないことを意味するため）。

### P4　money の units の二重計上

- money の `units`（Landed Cost の運賃に使う lot 数）が、市場 leaf の行だけでなく DAD の行も合計している（例：ev_update で市場 63,240 に対して 126,480）。
- 運賃の数量の起点を、設計どおりに直す（どの行を数えるべきかを、`money.py` と Landed Cost の設計の記述から確かめ、報告書に根拠を書く）。
- **これは方式（legacy／identity）の違いではなく計算の誤りなので、legacy も含めて直す。** 変わるのは Landed Cost の Freight（とそれを使う Landed GM%）だけのはずである。
- 受入：全モデルで、Freight の変更前・変更後の比較表（legacy と identity の両方）。Freight 以外の値が変わらないこと。golden の項目に money の値が入っていなければ golden は変わらない（変わる場合は理由を示す）。

### P5　Kitting の照合を Flow Check のタブに表として出す

- 今は CSV（表 3）と、表 1 の理由の欄だけで見えている。Flow Check のタブに「表 3：Kitting の照合」を加える。
- 列の例：組立ノード、置場、部材ごとの入庫 Σ・払出 Σ・期末残、完成した ID の数、組立ノードの P Σ、差（完成 ID − P Σ。0 が正）、判定。
- 受入：ev-thailand-2026_update で、2 つの置場の行が出て、完成 ID の数 ＝ Factory_Local_TH の P Σ（52,700）になる。Kitting の無いモデルでは「組立の置場なし」と表示する。

## 2. 守ること

- 計画（Forward／Backward）の結果は変えない。13 golden・legacy の golden 3 件が変わらないこと（P4 で golden が変わる場合は、理由と項目を示す）。
- P4 以外で legacy の値を変えない。
- commit・push はしない。
- 副作用が出ても最後まで行い、報告書に書く。

## 3. 成果物

1. コードの変更とテスト（P1 の識別子の一致を確かめるテスト、P4 の数え方の単体テスト、P5 の表の計算のテスト）
2. 報告書 `docs/development/WOM_StalePPC_Units_KittingView_Report.md`
   - P1〜P5 の変更点と受入の結果、P4 の比較表
   - P1・P2 の原因（コードで確かめたこと／推定）
   - 大杉さんが `python -m main` で確かめる手順（モデルを 2 つ続けて読み込む操作を含む）
