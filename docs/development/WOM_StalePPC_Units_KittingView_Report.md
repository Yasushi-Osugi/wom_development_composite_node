# Management の古い PPC 値・モデルのフォルダの表示・ステータス行・units・Kitting の表　報告

- 依頼書：`requests/RequestLetter_StalePPC_Units_KittingView_to_CodeKun.md`
- 前提：`docs/development/WOM_SmartphoneWarmup_EVUpdateKitting_S2_Report.md`
- 実装：Code君（Claude Code, Windows）、2026-09-30
- ブランチ：`wom-v1r5m1_cap_trial`。**着手時の HEAD：`e575042`**（依頼書の起草時の先頭 `5c58cfb` ＋依頼書 1 ファイル）
- **commit・push はしていない。**
- **改訂（2026-10-01）**：初版の報告への大杉さんの判断 3 点を反映した。(1) PPC の結果が無い間は、P&L Summary・Landed Cost・チャートを空欄にして状態だけを出す（money の値は出さない）。(2) モデルを読み込み直したら、Charts・KPI Table・Network・Flow Check も消す。(3) 2 つの計画を PPC が終わる前に続けて実行したときのテストを加える。反映した箇所は §0・§1.2〜1.4・§6・§7・§8。
- 計画（Forward／Backward）のコードは変えていない。保護対象の 6 ファイルには触れていない。
- 付表：`docs/development/stale_ppc/`（P4 の比較表、GUI の自動確認で読んだ値、基準の版での再現）

本書は「観測結果／コードで確かめたこと／推定／未確認」を分けて書く。

---

## 0. 受入のまとめ

| 区分 | 合否 | 要点 |
|---|---|---|
| P1　Management・PPC の表示が、今のモデル・今の計画の結果であること | **合** | 原因は、競合や失敗ではなく、**Management の P&L Summary・Landed Cost・GP チャートが、いつも「1 つ前の計画」の PPC の値を出していた**こと（§1.1）。基準の版で再現し、直した版で、ev-thailand → smartphone の順に操作して確かめた |
| P2　どのフォルダのモデルかを画面から分かるようにする | **合** | ウィンドウのタイトルと上の帯にフルパス。作業フォルダの外は赤字。「Load Model Folder」は、フォルダに無いファイルの欄を空にする（前は、前のモデルのファイルが残っていた。§2.1） |
| P3　「PPC complete (sample data)」 | **合** | PPC の入口が、PSI の販売記録を使ったか、サンプルに差し替えたかを記録する。差し替えのときは赤字の警告 |
| P4　money の units の二重計上 | **合** | units は市場 leaf の行だけを合計する。全 15 モデル×2 方式で、Freight（とそれを使う列）以外は 1 つも変わらない（§4） |
| P5　Kitting の照合を Flow Check のタブに表として出す | **合** | 「表 3：Kitting の照合」。ev_update で、置場 2 行、完成した ID 52,700 ＝ Factory_Local_TH の P Σ 52,700 |
| 全テスト | **636 passed／3 skipped、失敗 0**（1 回の実行、12 分 43 秒） | 621 → 639 件 |
| golden | **1 つも変わっていない**（13 件＋legacy の 3 件） | money の値は golden の項目に入っていない。PPC の出力ファイルも前と同じ |

大杉さんの判断（2026-10-01）を反映済み：

1. PPC の結果が無い間（計算中・未実行・失敗）は、P&L Summary・Node P&L・Landed Cost・チャートを**空欄**にし、状態だけを出す。money の値は出さない。
2. モデルを読み込み直したら、**すべての結果のタブ**を消す（「画面に出ているものは、すべて今のモデル・今の計画の結果」）。
3. 2 つの計画を PPC が終わる前に続けて実行しても、前の計画の PPC は画面に出ない（テストと、実アプリの窓での確認）。

残ること（§6）：P4 で、Landed Cost の Freight が 1/2〜1/4 になる（正しい値になる）。

---

## 1. P1：Management に前のモデルの PPC 値が出る件

### 1.1 原因

**コードで確かめたこと**（基準 `e575042` の `wom/gui/app.py`）：

1. 計画が終わると `_on_planning_done` が動く。その中で `self._mgmt_panel.load(self._mgr)` が呼ばれ、P&L Summary・Landed Cost・GP チャートが `output/ppc` のファイルを読む。
2. **その後で** `_run_ppc_from_planning` が PPC を別スレッドで始める。つまり、1. の時点で `output/ppc` にあるのは、**1 つ前の計画**の PPC の出力である。
3. PPC が終わると `_on_ppc_done` が動くが、更新するのは **PPC タブと Node P&L だけ**（`self._ppc_panel.refresh`、`self._mgmt_panel.refresh_node_pl`）。P&L Summary・Landed Cost・GP チャートは更新しない。
4. `output/ppc` のファイルには、どのモデル・どの計画の結果かの情報が無く、読む側も確かめていなかった。

このため、**P&L Summary・Landed Cost・GP チャートは、いつも 1 つ前の計画の PPC の値を出していた**。同じモデルを続けて計画すると同じ値なので気づかない。モデルを替えると、前のモデルの値が出る。Node P&L だけは今の計画の値になるので、1 枚の画面に 2 つのモデルの数字が混ざる。

依頼書の推定（PPC が終わる前、または失敗したときに読まれた）は、半分だけ当たっている。終わる前に読むのはそのとおりだが、**PPC が正常に終わっても直らない**（3. のため）。競合や失敗は要らない。

**観測結果（基準の版での再現）**：基準 `e575042` を別のフォルダに取り出し、実アプリの窓で ev-thailand-2026 → smartphone-global-2026-2029 の順に操作した（`docs/development/stale_ppc/base_e575042_reproduction.json`）。

| 時点 | P&L Summary の Revenue／GM | Node P&L の先頭 |
|---|---|---|
| ev-thailand の PPC の完了後 | 75,086,960,000／31.9%（money の値。取り出した直後で `output/ppc` が空だったため） | Components_CN（ev-thailand） |
| smartphone を計画した直後 | **319,119,580,000／56.5%**（ev-thailand の PPC の値） | Components_CN（ev-thailand） |
| smartphone の PPC の完了後 | **319,119,580,000／56.5%**（そのまま） | EMS_A_CN_i15（smartphone） |

大杉さんの画面（Revenue 319,119,580,000、GM 56.5%、Node P&L は smartphone）と同じになった。

### 1.2 直し方

| # | 内容 | 場所 |
|---|---|---|
| 1 | 計画の実行ごとに**識別子（run_id）**を作る：時刻（ミリ秒）＋乱数 6 桁＋モデルのフォルダ名。例 `20260930-225144.365-2a9d47__smartphone-global-2026-2029` | `wom/ppc/ppc_run_info.py`（新規）、`WOMApp._run_planning_engine` |
| 2 | PPC の入口は、実行の**最初に**出力フォルダの印（`ppc_run_info.json`）を消し、全部の出力を書き終えた**最後に**印を書く。印の中身：run_id、モデルのフォルダ、販売記録の出所（psi／sample）、マスターのフォルダ、基準通貨、週、方式、時刻 | `wom/ppc/ppc_runner.py`・`ppc_export.py` |
| 3 | 画面は、読む前に、印の run_id とモデルのフォルダが今の計画と一致するかを確かめる（`check_ppc_output`）。一致しなければ読まない | `ManagementCockpitPanel._ppc_check`、`PPCTabPanel._try_load` |
| 4 | PPC が終わったとき、**Management 全体**を更新する（P&L Summary・Node P&L・Landed Cost・チャート） | `WOMApp._on_ppc_done` |
| 5 | 古い計画の PPC のスレッドが遅れて終わっても、無視する（run_id が今の計画と違う） | `WOMApp._on_ppc_done`・`_on_ppc_error` |
| 6 | モデルを読み込み直したとき、**すべての結果のタブ**を消す：Charts・KPI Table・At-Risk・Scenario Delta・Management・PPC（「PPC 未実行」）・Network（図・PSI Chart・Cost/Revenue・PSI List・Flow Check）・World Map のアニメーション・Debug。計画の結果（`_mgr`）も手放す | `WOMApp._on_model_changed`・`_clear_result_tabs`、各パネルの `clear()` |
| 7 | **PPC の実行と受け取りの門番**（`PPCRunGate`）：(a) PPC の実行は 1 つずつ（出力フォルダは 1 つなので、同時に書かない）、(b) 順番が来たときに、もう今の計画でない PPC は**始めない**、(c) 今の計画でない PPC の結果は**受け取らない**。新しい計画を実行した時点・モデルを読み込み直した時点で、前の計画は「今の計画」でなくなる | `wom/ppc/ppc_run_info.py`、`WOMApp._run_planning_engine`・`_run_ppc_from_planning`・`_on_ppc_done` |

印について：

- **headless（`tools/run_headless_from_folder.py`）・テスト・`python -m wom.ppc` は、印を書かない**（消すだけ）。PPC の出力ファイル（CSV 5 本と JSON）は、前と 1 バイトも変わらない（テストで比べた）。
- 依頼書は「`ppc_kpi_summary.json` など」に書き込むとしている。JSON に書くと、headless の出力や LOVEM の on／off の比較（PPC の出力ファイルのハッシュを比べる）に時刻が混ざるので、**別のファイル**にした。印があるのは「そのフォルダの全ファイルが、その 1 回の実行で書かれた」ときだけ、という性質も、別ファイルの方が保ちやすい。

### 1.3 画面の表示

Management の上に 1 行の帯を加えた。P&L Summary には列「出所（Revenue〜GM）」を加えた。
**今の計画の PPC の結果が無い間は、数字を出さない**（大杉さんの判断。money の値では代用しない）。

| 状態 | 帯 | P&L Summary | Node P&L | Landed Cost | CCC・GP のチャート | PPC タブ |
|---|---|---|---|---|---|---|
| 今の計画の PPC の結果がある | 緑「PPC：PPC 台帳（今の計画）｜計画のモデル：…｜計画 ID：…」 | PPC の値。出所「PPC 台帳（今の計画）」 | PPC の値 | PPC の台帳の値 | 表示 | コックピット。状態行にモデルと計画 ID |
| PPC 計算中 | 黄「PPC：PPC 計算中 → P&L Summary・Node P&L・Landed Cost・チャートは、今の計画の PPC の結果が出るまで表示しません」 | シナリオ名だけの行。数字は**空欄**、出所の欄に「PPC 計算中」 | 1 行「（PPC 計算中）」 | 表は**空**。説明に「PPC 計算中（今の計画の PPC の結果が出るまで、Landed Cost は表示しません）」 | 図は空で、中央に「PPC 計算中」 | 「PPC 計算中」と、出力フォルダにあるのがどのモデル・計画のものか |
| PPC 失敗 | 赤「PPC：PPC 失敗 → …」 | 同じ形で「PPC 失敗」 | 「（PPC 失敗）」 | 空。「PPC 失敗…」 | 「PPC 失敗」 | 「PPC 失敗」 |
| PPC 未実行（Run Simulation だけのとき） | 黄「PPC：PPC 未実行 → …」 | 同じ形で「PPC 未実行」 | 「（PPC 未実行）」 | 空 | 「PPC 未実行」 | 「PPC 未実行」 |
| 出力が別の計画・別のモデルのもの | 赤「PPC の出力が今の計画のものではない（…）」 | 同じ形で理由 | 1 行で理由 | 空 | 理由 | 理由 |
| PPC がサンプルの販売データ（P3） | 赤「PPC はサンプルの販売データ（計画の数量と対応していない）」 | 同じ形で理由 | 1 行で理由 | 空 | 理由 | 理由 |
| モデルを読み込んだ直後（まだ計画していない） | 黄「モデルを読み込みました：<フルパス> → Planning Engine を実行してください（前の計画の表は消しました）」 | 空 | 空 | 空 | 空 | 「PPC 未実行」 |

- Strategic KPI のカード（充足率など）は、計画そのもの（sc_tree）から計算するので、PPC の状態によらず表示する。
- 運転資本の列（Inv Value・CCC・AR・AP）は money の値だが、PPC の結果が無い間は、これらも空欄にした（同じ行に出所の違う数字を混ぜないため）。
- PPC タブで、出力が今の計画のものでないときは、ボタン「確認なしで表示（出力フォルダにあるもの。今の計画の結果とは限りません）」で、わざと開くことはできる。そのときは、状態行に「⚠ 未確認の出力」と、どのモデル・計画のものかを出す。

モデルを読み込み直したときに消すもの：

| タブ | 消した後の表示 |
|---|---|
| Charts | 図は空で「モデルを読み込みました。Planning Engine を実行してください」。SKU・地域の選択肢は ALL だけ |
| KPI Table・At-Risk SKUs・Scenario Delta | 行なし・図は空 |
| Management | 表・図は空。帯に「モデルを読み込みました：… → Planning Engine を実行してください」。Strategic KPI は「Planning Engine 未実行」 |
| PPC | 「PPC 未実行」 |
| Network | 図は空で同じ案内。製品の選択肢なし。PSI Chart・Cost/Revenue は空。PSI List は「No node loaded」。Flow Check は 3 つの表とも空、見出し「モデル：—」 |
| World Map | 新しいモデルのノードを描く（前から）。前の計画の lot の流れのアニメーションは使えなくする |
| Debug | Reset と同じ状態 |

### 1.4 受入（観測結果）

`python -m tools.gui_two_model_check`：実アプリの窓（`WOMApp`）を起動し、フォルダの読み込みと Run Planning Engine を、画面のボタンと同じ処理で動かして、部品の値を読んだ。エラー 0 件。値は `docs/development/stale_ppc/gui_two_model_steps.json`、窓の画像は `output/stale_ppc/gui/`。

| 段階 | P&L Summary の Revenue／GM／出所 | Node P&L | 帯 |
|---|---|---|---|
| 1　起動直後 | 空 | 空 | モデルを読み込みました：…\smartx-2027-2029 |
| 2　ev-thailand-2026 を計画、PPC の完了後 | 319,119,580,000／56.5%／PPC 台帳（今の計画） | 12 行（ev-thailand のノード） | 緑。計画 ID …__ev-thailand-2026 |
| 3　smartphone-global-2026-2029 を読み込んだ直後 | **空** | **空** | モデルを読み込みました：…\smartphone-global-2026-2029 |
| 4　smartphone を計画した直後（smartphone の PPC は計算中） | **空欄／空欄／「PPC 計算中」** | 1 行「（PPC 計算中）」 | 黄。PPC 計算中 |
| 5　smartphone の PPC の完了後 | **641,014,134,734,200／41.2%／PPC 台帳（今の計画）** | 15 行（smartphone のノード） | 緑。計画 ID …__smartphone-global-2026-2029 |
| 6　PPC を失敗させて、もう一度計画 | 空欄／空欄／「PPC 失敗」 | 1 行「（PPC 失敗）」 | 赤。PPC 失敗 |

- smartphone の PPC が終わるまで、ev-thailand の値（319,119,580,000）は出ない。money の値（416,331,210）も出ない。終わった後は smartphone の値（641.0 兆円。前の報告書 A の値）が出る。
- 段階 4・6 では、Landed Cost の表は空、CCC・GP のチャートは「PPC 計算中」「PPC 失敗」だけを出す。
- 段階 4 の時点で、出力フォルダにあるのは ev-thailand の出力である。PPC タブは、それを開かずに「出力フォルダにあるのは：…\ev-thailand-2026（計画 ID …、販売記録 psi）」と出す。
- PPC が終わったとき、Management の P&L Summary・Landed Cost も更新されることを確かめた（段階 5。依頼書の「確かめて報告する」：**基準の版では、PPC タブと Node P&L だけが更新されていた**）。

**段階 3：モデルを読み込み直した直後に、ほかのタブも消えること**（部品から読んだ値）：

| タブ | 値 |
|---|---|
| Charts | 計画なし。図の文字「モデルを読み込みました。Planning Engine を実行してください」 |
| KPI Table／At-Risk | 0 行／0 行 |
| Network | 計画なし。製品の選択肢 0。PSI List「No node loaded — …」・0 行 |
| Flow Check | 表 1・表 2・表 3 とも 0 行。見出し「モデル：—」 |
| 計画の結果（`app._mgr`） | なし |

計画した後（段階 4）は、どのタブも smartphone の計画の内容になる（KPI Table 18 行、Network の製品 Phone16・15・17、Flow Check 表 1 が 32 行、見出しは smartphone のフォルダ）。

**段階 8：2 つの計画を、PPC が終わる前に続けて実行する**

操作：ev-thailand-2026 を計画する。その PPC を、わざと 12 秒遅らせる。ev-thailand の計画が終わった瞬間（PPC は実行中）に、smartphone-global-2026-2029 を読み込んで計画する。その間、画面の P&L Summary の Revenue・Node P&L の先頭・PPC タブの状態を 0.2 秒ごとに記録した。

| 経過 | P&L Summary の Revenue | Node P&L の先頭 | PPC タブ | 表示中の計画 |
|---|---|---|---|---|
| 0.9 秒〜 | （行なし） | （行なし） | PPC 未実行 | なし |
| 35.7 秒〜（smartphone の計画の完了） | 空欄 | （PPC 計算中） | PPC 計算中 | …__smartphone-global-2026-2029 |
| 49.5 秒〜（smartphone の PPC の完了） | 641,014,134,734,200 | EMS_A_CN_i15 | コックピット（smartphone） | …__smartphone-global-2026-2029 |

- 画面の変化は、この 3 つだけ。**ev-thailand の PPC の値（319,119,580,000）は、一度も画面に出なかった。**
- 主スレッドに届いた PPC の結果は 2 つ：ev-thailand（売上 319,119,580,000、**受け取らない**）、smartphone（売上 641,014,134,734,200、受け取る）。ログに `[PPC B2] result of an older plan ignored (run_id=…__ev-thailand-2026; current=…__smartphone-global-2026-2029)`。
- smartphone の PPC は、ev-thailand の PPC が書き終わるまで待ってから実行した（同時に書かない）。最後に出力フォルダに残るのは smartphone の結果と印である。

テスト（`tests/test_ppc_run_info.py`、10 件）：

- 識別子、状態ごとの判定（未実行・計算中・失敗・印なし・別の計画・別のモデル・サンプル・壊れた印）。
- PPC の入口が印を消して書くこと、headless の出力と 1 バイトも変わらないこと。
- Management のパネル（Tk）：一致しない出力を読まない。**PPC の結果が無い間（計算中・失敗・未実行）は、P&L Summary の数字が空欄で出所の欄に状態だけ、Landed Cost の表は空、2 つのチャートは状態の文字だけ。money の値（416…）も前の計画の値（319…）も出ない。**
- **2 つの計画を続けて実行**（`PPCRunGate`。実際のスレッドで確かめる）：計画 A の PPC が実行中に計画 B を実行する。B の PPC は A が書き終わるまで書かない。A が後から終わっても、画面が受け取るのは B だけ。出力フォルダには B の結果と印が残る。
- 順番が来たときに今の計画でない PPC は、実行しない（フォルダに書かない）。モデルを読み込み直した後は、どの PPC も始めない・受け取らない。

---

## 2. P2：どのフォルダのモデルを読み込んでいるか

### 2.1 見つけたこと（コードで確かめたこと）

「Load Model Folder」は、フォルダにある標準の名前のファイルだけを欄に入れ、**フォルダに無いファイルの欄は、前の値のまま残していた**。たとえば、`edge_cost_master.csv` や `push_config.csv` の無いモデルを読み込むと、前のモデルのファイルが、そのまま新しいモデルの計画・Landed Cost に使われる。大杉さんの件（別のフォルダの古いコピー）とは別の経路だが、同じ種類の見誤り（別のモデルの入力が混ざる）を起こす。

### 2.2 直し方

| 内容 | 場所 |
|---|---|
| フォルダ → 欄の対応を、Tk に依存しない関数にした（`model_folder_file_map`）。**フォルダに無いファイルの欄は空にする** | `wom/gui/app.py` |
| ウィンドウのタイトルに、モデルのフォルダのフルパス | `WOMApp._update_model_display` |
| 上の帯に 2 行：「モデル：<フルパス>」と「表示中の計画：<計画 ID>」 | 同上 |
| 作業フォルダ（リポジトリの根）の外のモデルは、「⚠ 作業フォルダの外：<フルパス>」と赤字。ステータス行も赤字 | `is_outside_work_root`・`describe_model_dir` |
| 読み込んだモデルと、表示中の計画のモデルが違うとき、赤字で「⚠ 表示中の計画は別のモデル：…」（今は、モデルを読み込み直すと計画の表示をすべて消すので、「Load Model Folder」ではこの状態にならない。SC Tree Master の欄を手で別のフォルダのファイルに替えて計画した場合の備え） | 同上 |
| Flow Check の見出しに「モデル：<計画に使ったフォルダのフルパス>」。Management の帯と PPC タブの状態行にも、計画のモデルと計画 ID | `FlowCheckPanel.load` ほか |
| 計画の実行のとき、実際に使う `sc_tree_master.csv` のフルパスを、ステータス行とログに出す（`[Planning] run_id=… sc_tree_master=…`） | `WOMApp._run_planning_engine` |
| 読み込みのステータス行：「📂 <フルパス>: N files loaded (not found → 欄を空にしました: …)」 | `WOMApp._load_model_folder` |

補足：計画が使うモデルのフォルダは、SC Tree Master の欄のファイルのフォルダである（欄を手で書き換えた場合も、そのフォルダになる）。計画 ID とモデルのフォルダは、この値から作る。

### 2.3 受入（観測結果）

- 自動の GUI 操作（§1.4 の続き、段階 7）：一時フォルダに置いた ev-thailand-2026_update のコピーを読み込むと、タイトルと帯が「⚠ 作業フォルダの外：C:\Users\…\Temp\wom_old_copy_…\data\sample\ev-thailand-2026_update」（赤字）になる。SC Tree Master・Edge Cost Master・Route Master・Push Config の欄は、どれもそのフォルダのファイルになる。Flow Check の見出しも同じフォルダを出す。
- テスト（`tests/test_ppc_run_info.py`）：A を読み込み、B に読み込み直すと、SC Tree Master は B のファイル、B に無い Edge Cost Master・Route Master・Push Config は空になる。どの欄も B のフォルダのファイルか空である。作業フォルダの外の判定（名前が作業フォルダで始まるだけの別のフォルダ `…_old` も外）。

---

## 3. P3：「PPC complete (sample data)」

- **コードで確かめたこと**：ステータス行は PPC の結果の `_psi_mode` を読むが、どこも書いていなかったので、いつも「sample data」だった。一方 `ppc_runner.py` は、PSI の販売記録の製品・市場が PPC のマスターに 1 つも無いとき、実際にサンプルの販売データに差し替える（ログに `WARNING: Results based on SAMPLE data` を出すだけだった）。
- **直し方**：`run_ppc_from_psi` の返り値に `_psi_mode`（True／False）と `sales_source`（`psi`／`sample`）を入れる。印（`ppc_run_info.json`）にも `sales_source` を書く。JSON（`ppc_kpi_summary.json`）には入れない。
- 表示：
  - PSI の販売記録：「💰 PPC complete (PSI-linked) — Lots: … Margin: … | PPC・Management tabs refreshed」。
  - サンプルに差し替え：**赤字**で「⚠ PPC はサンプルの販売データで計算されました（計画の製品・市場が PPC のマスターに見つからないため）。PPC の数字は、この計画の数量と対応していません」。Management・PPC タブは、その出力を今の計画の値として使わない（§1.3 の表）。
- 受入：自動の GUI 操作で、ev-thailand・smartphone・ev_update とも「PPC complete (PSI-linked)」。サンプルへの差し替えは、テストで確かめた（bom-test の計画に、既定のマスター `data/ppc` を当てる → `_psi_mode=False`、印は `sample`、判定は「PPC はサンプルの販売データ」）。
- 見つけたこと：既定のマスター（`data/ppc`）の為替表は 2026-W01 から始まる。計画の週がそれより前だと、サンプルへの差し替えそのものが為替の欠落で失敗する（＝「PPC 失敗」の表示になる）。今回の前からの動きで、変えていない。

---

## 4. P4：money の units の二重計上

### 4.1 どの行を数えるべきか（根拠）

- `wom/engine/landed_cost.py` の設計の記述：`freight_total = freight_usd_per_lot × lot_count × blended_fx_rate`、`lot_count` は「Actual lot count, supplied by build_scenario_money_kpi() as "units"」。`compute_landed_cost_kpi` の説明は「units = total demand_fulfilled lots for the scenario」。`CLAUDE.md`（2026-07-06 の修正の記録）も「`total_units`（`demand_fulfilled` の合計＝実 lot 数）」。つまり、**そのシナリオで市場へ売った lot 数**である。
- units を入れたのは 2026-07-06（Landed Cost の異常値の修正）。計画の DataFrame に DAD の行（地域が `DAD:…`）が入ったのは v1r0m2 で、それより前からあった。units は「全行の合計」と書かれたので、DAD の行も数えてしまった。
- DAD の行は、同じ lot が DC を通るたびにもう一度現れる行（在庫・通過量）で、販売ではない。`sku_master` に価格が無いので、売上・原価は 0 になり、units だけが増えていた。

**直し方**：`money.py` の `total_units` を、市場の行（地域が `DAD:` で始まらない行）だけの合計にした。方式（legacy／identity）によらない数え方の誤りなので、両方を直した。シミュレーターのシナリオには DAD の行が無いので、変わらない。

### 4.2 比較（観測結果）

`python -m tools.units_freight_compare`：15 モデル（13 golden ＋ ev_update ＋ alloc）×2 方式で、同じ計画結果に、基準の money と今の money を当てた。Landed Cost のシナリオごとの全 108 行は `docs/development/stale_ppc/units_freight_compare.csv`、units だけの表は `units_compare.csv`。

Base のシナリオ（Freight は基準通貨、Landed GM% は money の値）：

| モデル | 方式 | 市場の数量 | units 前 → 後 | 倍率 | Freight 前 → 後 | Landed GM%（money）前 → 後 |
|---|---|---:|---|---:|---|---|
| Cookie-jp-2026 | identity／legacy | 141,990 | 362,910 → 141,990 | 2.56 | 225,185,655 → 88,104,795 | 29.02% → 32.24% |
| apparel-global-2028-2029 | identity／legacy | 181,526 | 544,578 → 181,526 | 3.00 | 3,812,046 → 1,270,682 | 21.36% → 45.87% |
| apparel-us-2026 | identity／legacy | 249,172 | 498,344 → 249,172 | 2.00 | 2,940,230 → 1,470,115 | 34.65% → 46.69% |
| bom-test-2026 | identity／legacy | 100 | 200 → 100 | 2.00 | 0 → 0 | 37.50% → 37.50% |
| ev-europe-2026 | identity／legacy | 53,140 | 106,280 → 53,140 | 2.00 | 17,580,040 → 8,790,020 | 50.30% → 50.69% |
| ev-thailand-2026 | identity／legacy | 63,240 | 126,480 → 63,240 | 2.00 | 1,309,068,000 → 654,534,000 | 27.45% → 28.33% |
| ev-thailand-2026_update | identity／legacy | 63,240 | 126,480 → 63,240 | 2.00 | 1,309,068,000 → 654,534,000 | 27.45% → 28.33% |
| smartphone-global-2026-2029 | identity | 414,090 | 828,180 → 414,090 | 2.00 | 30,794,493 → 15,397,247 | 48.48% → 52.18% |
| smartphone-global-2026-2029 | legacy | 470,924 | 941,848 → 470,924 | 2.00 | 35,021,048 → 17,510,524 | 48.00% → 51.78% |
| oil-global-2027 | identity | 191,029 | 382,058 → 191,029 | 2.00 | 240,335,707 → 120,167,854 | 96.68% → 96.69% |
| oil-global-2027 | legacy | 191,058 | 382,116 → 191,058 | 2.00 | 240,372,193 → 120,186,096 | 96.70% → 96.71% |
| rice-japan-2027-2028 | legacy（このモデルの方式） | 235,316 | 928,819 → 235,316 | 3.95 | 61,534,258,750 → 15,589,685,000 | 35.39% → 41.72% |
| rice-japan-2027-2028 | identity（参考） | 142,914 | 627,802 → 142,914 | 4.39 | 41,591,882,500 → 9,468,052,500 | 34.58% → 41.92% |
| smartx-2027-2029 | identity／legacy | 709,811 | 1,419,622 → 709,811 | 2.00 | 57,241,821 → 28,620,910 | 47.45% → 51.53% |
| soysauce-eu-2027 | identity／legacy | 100,501 | 301,503 → 100,501 | 3.00 | 473,360 → 157,787 | 39.28% → 47.99% |
| soysauce-jpy-2027 | identity／legacy | 100,501 | 301,503 → 100,501 | 3.00 | 473,360 → 157,787 | 52.28% → 52.34% |
| soysauce-us-2027 | identity／legacy | 100,500 | 301,500 → 100,500 | 3.00 | 473,355 → 157,785 | 38.68% → 47.48% |
| soysauce-jpy-2027-alloc | identity | 75,291 | 225,873 → 75,291 | 3.00 | 354,621 → 118,207 | 50.25% → 50.31% |
| soysauce-jpy-2027-alloc | legacy | 100,501 | 301,503 → 100,501 | 3.00 | 473,360 → 157,787 | 52.28% → 52.34% |

- **後の units は、どのモデル・方式でも、市場の数量と一致する**（30 行とも）。
- **Freight 以外は変わらない**：
  - money の表は、`total_units`／`units` 以外の全列が一致（30 行とも）。
  - Landed Cost は、Freight と、それを使う列（landed_cogs・landed_gross_profit・landed_gross_margin・margin_impact_pp）以外の列（revenue・cogs・customs_duty・tariff_burden_pct など）が一致（108 行とも）。
  - KD 組立費（`assembly_total`）も units を使うが、どのモデルも 0 だったので、今回は値の変化が無い。
- **画面での見え方**：Management の Landed Cost の表では、PPC の結果があるとき、Revenue・Customs Duty・Landed GM%・ΔMargin・Tariff% は PPC の台帳の値で上書きされる（v1r2m0）。そのため、画面で変わるのは **Freight の列だけ**である（例：smartphone ¥30,794,493 → ¥15,397,247）。上の表の Landed GM%（money）は、money の側の計算値で、画面には出ない（PPC の結果が無い間は、Landed Cost の表を空にするため。§1.3）。
- **golden は変わらない**：golden の項目（period／products／config／forward／backward／ppc／psi）に、money の値は入っていない。13 件＋legacy の 3 件とも、テストで一致を確かめた。

テスト（`tests/test_money_units.py`、5 件）：DAD の行の判定、units は市場の行だけ（legacy と identity）、units 以外の値は変わらない、シミュレーターの行は全部数える、Landed Cost の Freight ＝ 1 lot あたりの運賃 × 市場の lot 数 × 為替。

---

## 5. P5：Kitting の照合を Flow Check のタブに表として出す

- Flow Check のタブに「表 3：Kitting の照合（部材の消費と完成。差（完成−P）は 0 が正）」を加えた。
- 列：製品、組立ノード、行（完成品（組立）／部材（置場））、置場／組立、入庫 Σ、払出 Σ、期末残、部材の保存差、**完成した ID**、**組立の P Σ**、**差（完成−P）**、二重生成、未そろい完成、到着前完成、期末に待つ部材、判定、理由。
  - 完成した ID ＝ すべての置場から払い出された Lot_ID の数（置場の払出の記録から数える。組立の P とは別に数える）。
  - 差（完成−P）が 0 でなければ、その組立ノードは NG（表 1 も NG になる）。
- Kitting の無いモデルでは、1 行「組立の置場なし」を出す。
- CSV（`flow_check_kitting.csv`）にも、同じ 3 列（`completed_ids`・`assembly_p_sum`・`completed_minus_p`）が増える。
- 要約行に「Kitting の照合 N 組立（NG n）」（前の依頼で追加済み）。

受入（観測結果。自動の GUI 操作、段階 7）：ev-thailand-2026_update の表 3：

| 行 | 置場／組立 | 入庫 Σ | 払出 Σ | 期末残 | 部材の保存差 | 完成した ID | 組立の P Σ | 差 | 判定 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 完成品（組立） | Factory_Local_TH | 52,700 | | | | **52,700** | **52,700** | **0** | OK |
| 部材（置場） | Platform_Unit_Assy_Yard | 52,700 | 52,700 | 0 | 0 | | | | OK |
| 部材（置場） | Motor_Unit_Assy_Yard | 52,700 | 52,700 | 0 | 0 | | | | OK |

smartphone-global-2026-2029・ev-thailand-2026 では「組立の置場なし」。

テスト（`tests/test_ev_update_kitting.py` に 3 件追加）：完成した ID ＝ 組立の P Σ ＝ 52,700、置場 2 行。組立の P から 1 件を抜くと、差が 1 で NG になる（表 1 も NG）。Kitting の無いツリーでは行が無い。

---

## 6. 副作用・判断を仰ぎたいこと

### 6.1 今回の変更によるもの

| # | どこで | 何が | 実機での見方 | 期待との差 |
|---|---|---|---|---|
| S1 | Management | PPC の結果が無い間（計算中・失敗・未実行）は、P&L Summary・Node P&L・Landed Cost・2 つのチャートが空欄で、状態だけが出る | 計画の直後の数秒。帯が黄色 | 大杉さんの判断どおり |
| S2 | **Run Simulation だけを実行したとき** | Management の P&L Summary は、シナリオ名（Base・Upside・Downside）だけの行で、数字は空欄、出所の欄に「PPC 未実行」。CCC・GP のチャートも「PPC 未実行」 | 起動 → フォルダを読み込む → Run Simulation → Management | 判断 1（PPC 未実行は空欄）をそのまま当てはめた結果。前は、`output/ppc` に残っていた前の回の PPC の値で、全シナリオの行が上書きされていた。シミュレーションのシナリオ比較（money の P&L）を Management で見たい場合は、別の扱いが要る（**確認をお願いしたい**） |
| S3 | PPC タブ | 起動直後に、前の回の PPC の出力を自動では開かない（「PPC 未実行」）。`python -m wom.ppc` で作った出力も同じ | PPC タブ。ボタン「確認なしで表示」で開ける（未確認と表示） | 前は、起動すると前の回の出力を無条件で表示していた |
| S4 | モデルを読み込み直したとき | すべての結果のタブが消える（§1.3 の表）。Export to Excel／CSV は「Run the simulation first」になる | 「Load Model Folder…」の直後に、各タブを開く | 大杉さんの判断どおり。起動直後（既定のサンプルを読み込んだ状態）も同じ扱い |
| S5 | 「Load Model Folder」 | フォルダに無いファイルの欄が空になる | 左の「詳細」を開く。ステータス行に「not found → 欄を空にしました: …」 | Run Simulation は、4 つの入力（SKU・需要・在庫・能力）のどれかが空だと「Please select all 4 input files」と出る（前は、前のモデルのファイルで動いてしまっていた） |
| S6 | Landed Cost の Freight | 1/2〜1/4 になる（§4） | Management → Tariff & FX | 正しい値になる |
| S7 | Flow Check のタブ | 表が 3 つになり、表 1 の高さが小さくなる（1,020 px の窓で 4 行ほど） | 仕切りをドラッグすると広がる | 高さの配分は調整できる |
| S8 | `output/ppc` | GUI で計画すると `ppc_run_info.json` が増える | — | git の対象外 |
| S9 | `WOMApp._status` | 同じ名前のメソッドが 2 つ定義されていた（後ろのものが使われる）。両方に `warn` の引数を足した | — | 今回の前からの重複。片方を消すのは見送った |
| S10 | 計画を続けて実行したとき | 後の計画の PPC は、前の計画の PPC が書き終わるまで待つ。前の PPC が長いと、その分「PPC 計算中」が長くなる | — | 出力フォルダが 1 つのため。前の PPC を途中で止める仕組みは無い |

### 6.2 前からあって、今回見つけたもの（変えていない）

| # | 何が | 影響 |
|---|---|---|
| P-a | ev-thailand（THB 建て）の Landed Cost の金額に「¥」が付く。PPC の基準通貨が `ppc_fx_rate.csv` の列から決まり、このモデルでは JPY と判定されるため（`CLAUDE.md` に既出） | 表示だけ |
| P-b | ev-thailand の Landed Cost は、5 つのシナリオ（Base・EV30・EV35 ほか）の行が同じ値になる | 関税の再計算（v1r2m0 の台帳の上書き）が、国ごとのレートの対応を取れていない可能性。未調査 |
| P-c | 既定のマスター（`data/ppc`）でサンプルへ差し替えると、2026-W01 より前の週で為替が無く、PPC が失敗する | §3 |

### 6.3 未確認

- マウス操作による確認（§7）。
- Scenario Delta・At-Risk のタブ。

---

## 7. `python -m main` で確かめる手順

### 7.1 モデルを 2 つ続けて読み込む（P1）

1. `python -m main` を起動する。上の帯に「モデル：…\data\sample\smartx-2027-2029」「表示中の計画：なし（Planning Engine 未実行）」。Management の帯は「モデルを読み込みました：… → Planning Engine を実行してください」。P&L Summary は空。PPC タブは「PPC 未実行」。
2. 「Load Model Folder…」で `data\sample\ev-thailand-2026` を選ぶ。ウィンドウのタイトルと上の帯が、そのフルパスになる。
3. 「Run Planning Engine」を押す。ステータス行に「Running Planning Engine … SC Tree Master: …\ev-thailand-2026\sc_tree_master.csv」。
4. 完了後、Management を開く。帯が緑「PPC：PPC 台帳（今の計画）｜計画のモデル：…\ev-thailand-2026｜計画 ID：…__ev-thailand-2026」。P&L Summary の Revenue 319,119,580,000、GM 56.5%、出所「PPC 台帳（今の計画）」。
5. **再起動せずに**「Load Model Folder…」で `data\sample\smartphone-global-2026-2029` を選ぶ。Management の表とチャートが**空になる**。PPC タブは「PPC 未実行 … 出力フォルダにあるのは：…\ev-thailand-2026」。上の帯の 2 行目は「表示中の計画：なし（Planning Engine 未実行）」。**Charts・KPI Table・Network・Flow Check も空になる**（Charts と Network の図に「モデルを読み込みました。Planning Engine を実行してください」、Flow Check の見出しは「モデル：—」）。
6. 「Run Planning Engine」を押し、Management を見ている。計画の直後の数秒は、帯が黄色「PPC：PPC 計算中 → … 今の計画の PPC の結果が出るまで表示しません」、P&L Summary は「Planning」の行の数字が空欄で、出所の欄に「PPC 計算中」、Node P&L は「（PPC 計算中）」、Landed Cost の表は空、下の 2 つのチャートは「PPC 計算中」。**319,119,580,000 も 416,331,210 も出ない。**
7. PPC が終わると、帯が緑になり、P&L Summary は Revenue **641,014,134,734,200**、GM 41.2%、出所「PPC 台帳（今の計画）」。Node P&L は smartphone のノード（EMS_A_CN_i15 など）15 行。Landed Cost の Revenue も 641,014,134,734,200。ステータス行は「💰 PPC complete (PSI-linked) — Lots: 1,127 Margin: 41.2%」。

### 7.2 そのほか

| # | 操作 | 期待する表示 |
|---|---|---|
| 8 | 別の場所にあるモデルのフォルダ（古いコピーなど）を読み込む | タイトルと上の帯が赤字「⚠ 作業フォルダの外：<フルパス>」。ステータス行も赤字 |
| 9 | 左の「▼ 詳細」を開く（`edge_cost_master.csv` の無いモデルを読み込んだ後） | Edge Cost Master の欄が空（前のモデルのファイルが残っていない） |
| 10 | ev-thailand-2026_update を計画 → Network → ✔ Flow Check | 見出しに「モデル：<フルパス>」。表 3 に 3 行（§5 の表）。差（完成−P）が 0 |
| 11 | smartphone-global-2026-2029 を計画 → Flow Check | 表 3 に「組立の置場なし」 |
| 12 | smartphone-global-2026-2029 を計画 → Management → Tariff & FX | Freight が ¥15,397,247（Base）。前は ¥30,794,493 |
| 13 | PPC タブで、PPC 未実行のときにボタン「確認なしで表示」 | コックピットが開き、状態行に「⚠ 未確認の出力（PPC 未実行）：出力フォルダにあるのは …」 |
| 14 | ev-thailand-2026 を計画し、PPC が終わる前に（計画の完了の直後に）smartphone-global-2026-2029 を読み込んで計画する | ev-thailand の値（319,119,580,000）が、Management・PPC タブに一度も出ない。最後に smartphone の値になる。コンソールに `[PPC B2] result of an older plan ignored …` が出ることがある（PPC は数秒で終わるので、手では間に合わないことが多い。自動の確認は §1.4 の段階 8） |
| 15 | 起動 → フォルダを読み込む → Run Simulation → Management | P&L Summary は Base・Upside・Downside の行で数字が空欄、出所の欄に「PPC 未実行」（§6.1 S2。これでよいかの確認をお願いしたい） |

---

## 8. 変更したもの・テスト

| 種類 | ファイル |
|---|---|
| 新規（コード） | `wom/ppc/ppc_run_info.py`（識別子・印・判定・門番 `PPCRunGate`。Tk に依存しない） |
| 変更（PPC） | `wom/ppc/ppc_runner.py`（引数 `run_info`、印、`_psi_mode`・`sales_source`）、`wom/ppc/ppc_export.py`（書く前に印を消す） |
| 変更（GUI） | `wom/gui/app.py`（Management の帯・出所の列・PPC の確認・空欄の表示、PPC タブ、タイトルと上の帯、フォルダの読み込み、各パネルの `clear()`、Flow Check の見出しと表 3、ステータス行、PPC の門番） |
| 変更（評価） | `wom/engine/money.py`（units）、`wom/engine/sc_tree_to_df.py`（`DAD:` の定数）、`wom/engine/flow_check.py`（表 3 の 3 列） |
| 新規（テスト） | `tests/test_ppc_run_info.py`（10 件）、`tests/test_money_units.py`（5 件）。`tests/test_ev_update_kitting.py` に 3 件追加 |
| 新規（測定） | `tools/gui_two_model_check.py`（2 モデルを続けて操作する自動の GUI 確認）、`tools/units_freight_compare.py`（P4 の比較） |
| 文書 | 本書、`docs/development/stale_ppc/`、`CLAUDE.md`（GUI の古い値の注記を更新、units の注記を更新） |

変えていないもの：計画（Forward／Backward）、保護対象の 6 ファイル、サンプルの入力、golden。

| 項目 | 結果 |
|---|---|
| 全テスト | **636 passed／3 skipped、失敗 0**（639 件、12 分 43 秒、1 回の実行） |
| golden | 13 件＋legacy の 3 件とも一致（ファイルは変えていない） |
| PPC の出力ファイル | headless の出力は前と同じ（印を書かない）。GUI と同じ呼び方でも、CSV 5 本と JSON は 1 バイトも変わらない（印のファイルが 1 つ増えるだけ） |
