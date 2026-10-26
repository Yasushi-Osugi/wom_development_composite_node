# Request Letter：PPC・Value Chain の黙った見本への切り替えを止める（D8）

- 宛先：Code君（Claude Code、Windows）
- 依頼者：大杉（WOM Project Owner）
- 起草：Claude君（2026-10-26）
- 版：v0.1
- 作業フォルダ：`C:\Users\ohsug\WOM_V0R2M1_new_cockpit\wom-v1r5m1_cap_trial`（起草時の根拠 `516d158`。この依頼書は大杉さんが先に commit する。着手時の SHA を報告書に記録する）
- 出どころ：化粧品設計書 v0.3〜v0.5 の決定 D8（「PPC の黙った見本への切り替えを止める依頼書を起こす。金額の段階の前に入れる」）、判断 J4 の (3)、試行 1 の報告書 `docs/development/WOM_BSSEAF_Cosmetics_Trial_Report.md` §4.2・§5.2 の 3
- 種別：**コードの変更を含む**。保護対象のコア（`AGENTS.md` §10 の 6 ファイル）は**変えない**（PPC・Value Chain・headless・GUI の側の変更）。golden（通常 15 件・legacy 3 件）は**変わらないこと**。変わるなら、変える前に止めて報告する

---

## 0. 目的と原則

**金額の結果は、この計画の数量を、このモデルが使うと決めた規則で評価したものだけを出す。** 評価できない所は「未評価」と書き、0 や見本の値で埋めない（Start Here R12「価格を 0 で埋めない、未評価として扱う」と同じ考え方）。

今は、次の 5 か所で、金額の計算が黙って（または目立たずに）別のデータへ切り替わる。

| # | 所 | 今の動き | 根拠 |
|---|---|---|---|
| S1 | 規則のフォルダの選択（headless `_run_ppc()`、GUI の PPC の実行） | モデルに `ppc_market_price.csv` が無いと、規則を丸ごと `data/ppc`（見本）から読む。この判定が headless と GUI の 2 か所に別々に書かれている | `tools/run_headless_from_folder.py` `_run_ppc()`、`wom/gui/app.py`（PPC の実行、「モデルフォルダ内に ppc_market_price.csv があれば…」） |
| S2 | 規則のファイルごとの切り替え | モデルにある規則のフォルダで、一部のファイルが無いと、そのファイルだけ `data/ppc` から読む（標準出力に 1 行出るだけ） | `wom/ppc/ppc_rules.py` `PPCRuleSet.load()` の `fallback_dir` |
| S3 | 規則に無い製品・市場の販売記録 | 計画の販売記録のうち、規則に無い製品・市場の行を**黙って落とす**。一部だけ落ちても何も出ない | `wom/ppc/ppc_runner.py` Step 3 |
| S4 | 全部落ちたとき | 見本の販売データ（モデルに無い `SMARTPHONE` の lot）を作って計算する。GUI は警告を出すが、headless の snapshot・`planning_state` には出ない | `ppc_runner.py` Step 4（「Falling back to sample data」） |
| S5 | Value Chain の為替 | モデルに `ppc_fx_rate.csv` が無いと `data/ppc` の為替を読む（記録には `data/ppc (fallback)` と残る） | `wom/valuechain/fx.py` `FxTable.load()`、`wom/valuechain/run.py` |

化粧品の試行で起きたこと：規則のファイルは見出しの行だけ（製品が規則に無い）→ S4 で見本の 2,595 lot を計算し、snapshot の `ppc.total_lots` に化粧品と無関係な数が入った。規則のファイルを消すと S1 で、見本の規則 × 見本の販売の「粗利率 30.4%」が出た（試行 1 の報告書 §4.2）。

## 1. 大杉さんに決めてほしいこと（この依頼書を Code君に渡す前に）

| # | 事項 | Claude君の推奨 |
|---|---|---|
| K1 | モデルが共有の規則（`data/ppc`）を使うことを、**明示の宣言**にするか | **宣言にする**。`planning_config.csv` の `ppc_shared_rules_dir`（例：`data/ppc`）。宣言があれば、モデルに無い規則のファイルをそこから読み、読んだことを記録する。宣言が無ければ読まない |
| K2 | 宣言の無いモデルで、規則が足りないとき | 計画は止めない。**金額の結果を「未評価」にし、足りないファイル・製品・市場を並べる**。PPC の失敗で数量の計画まで失わないため |
| K3 | 一部の製品・市場だけ規則に無いとき（S3） | 評価できた範囲で計算し、**「一部未評価」**とする。評価できなかった製品・市場と lot 数を並べる。合計の金額は「評価できた範囲の値」と明示する |
| K4 | 見本の販売データ（S4） | 計画からの PPC では**作らない**。`python -m wom.ppc` を販売の CSV なしで呼ぶ見本の実演（`wom/ppc/__main__.py`）だけに残す |
| K5 | 既存のサンプルで、共有の規則を使っているもの | 宣言を足して、今の数値を保つ。rice（規則を全部 `data/ppc` から）、Cookie・smartphone（`ppc_fx_rate.csv` だけ `data/ppc` から）。値は変わらない |

以下は、推奨どおりに決まったものとして書く。違う判断になったら、Claude君が直してから渡す。

## A. 先に確かめること（コードを読み、既存のモデルで回して。違えば止めて報告）

| # | 確かめること |
|---|---|
| A1 | §0 の S1〜S5 が、上に書いたとおりのコードであること |
| A2 | `data/sample/` の各モデル（golden の 15 件と legacy 3 件で使うもの）で、S1〜S5 のどれが起きているか。モデルごとに表にする：規則のフォルダ、`data/ppc` から読んだファイル、S3 で落ちた製品・市場と lot 数、S4 の有無、Value Chain の為替の出どころ。Claude君がファイルの有無だけ見た所では、rice は規則が全部無く、Cookie・smartphone は `ppc_fx_rate.csv` だけ無い（ほかのモデルは 9 ファイルとも有る）。`data/sample/rice-japan-2027-2028_BK260613_1515` は表に入れて報告するだけ（扱いは大杉さん） |
| A3 | **golden のモデルで S3 か S4 が起きていたら、実装の前に止めて報告する**（今の golden の金額が、評価できなかった部分を黙って落とした値だったことになる。扱いは大杉さんが決める） |
| A4 | `snap["ppc"]`・`ppc_kpi_summary.json`・`run_ppc_from_psi()` の返り値を読む所をすべて並べる（Claude君の grep：`wom/planning_state/__init__.py` `attach_realized()`、`wom/valuechain/run.py`、`wom/gui/app.py` の PPC の表示、`tools/run_headless_from_folder.py` の CLI の表示、`tools/analyze_smartx_bottleneck.py`、`tools/generation_line_compare.py` ほか）。それぞれが「未評価」で値の無い結果を受けたとき、0 として読まないかを確かめる |

## B. 直すこと

### B.1 規則の出どころを 1 か所で決める

- 新しい関数（例：`wom/ppc/ppc_rules.py` の `resolve_ppc_rules(model_dir)`）で、規則のフォルダ・共有の規則の宣言（K1）・各ファイルの出どころを決める。返り値に、ファイルごとの出どころ（`model`／`shared:<dir>`）と、足りないファイルを持たせる。
- headless の `_run_ppc()`、GUI の PPC の実行、Value Chain の為替（`FxTable.load()` の呼び出し）、`run_ppc_from_psi()` は、すべてこの関数を使う。S1 の判定を 2 か所に書かない。
- `PPCRuleSet.load()` の黙ったファイルごとの切り替え（S2）は、宣言のあるときだけ行う。宣言の無いときに足りないファイルがあれば、未評価の理由として返す（例外で計画を止めない）。

### B.2 評価の状態を持たせる

PPC の結果に `valuation_status` を持たせる。

| 値 | いつ | 金額の値 |
|---|---|---|
| `評価済み` | 全ての販売記録が規則で評価できた | 今までどおり |
| `一部未評価` | 規則に無い製品・市場があり、その記録を除いて評価した（S3） | 評価できた範囲の値。**除いた製品・市場ごとの lot 数**を持たせる |
| `未評価` | 規則のファイルが足りない（宣言なし）、または評価できる記録が 1 件も無い（S4） | **持たない**（0 も入れない）。理由を持たせる |

- `ppc_kpi_summary.json`・`ppc_run_info.json` に、状態・理由・除いた製品と市場・規則の出どころを書く。
- **snapshot の `ppc`**：状態が `評価済み` のときは、**今のキーと値を 1 バイトも変えない**（golden）。`一部未評価`・`未評価` のときだけ、`valuation_status`・`reason` などのキーを足す。`未評価` のときは金額のキーを入れない。
- S4 の見本の販売データの生成を `run_ppc_from_psi()` から外す（K4）。`wom/ppc/__main__.py` の実演はそのまま。

### B.3 読む側

- `attach_realized()`（金額の経路）：PPC が `未評価` なら、`realized.ppc` を `{"valuation_status": "未評価", ...}` にし、`gap_decomposition` などの金額の比較を作らない。0 として計算しない。`一部未評価` なら、そのことを `realized` に残す。
- GUI：PPC の状態の表示（今の「サンプルの販売データ」の警告の所）を、`未評価`（理由）・`一部未評価`（除いた製品・市場）に置き換える。見本で計算した、という表示は無くなる。
- headless の CLI の 1 行の表示（`GM=… trust=…`）：`未評価` なら「財務：未評価（理由）」と出す。
- §A4 で見つけたほかの読む所も、値が無いときに 0 として扱わないようにする。

### B.4 既存のサンプルに宣言を足す（K5）

§A2 の表で共有の規則を使っていたモデルの `planning_config.csv` に `ppc_shared_rules_dir,data/ppc` を足す（rice、Cookie、smartphone の見込み）。**金額の値が変わらないこと**を golden で確かめる。`planning_config.csv` の知らないキーで止まる読み込みが無いかも確かめる。

## C. テスト

| # | 確かめること |
|---|---|
| T01 | golden（通常 15・legacy 3）が変わらない |
| T02 | 宣言のあるモデル：規則のファイルが足りなくても、宣言の場所から読み、出どころが記録される。値は今までと同じ |
| T03 | 宣言の無いモデルで規則のファイルが足りない：計画は最後まで動き、PPC は `未評価`、足りないファイルが並ぶ。`data/ppc` を読んでいない |
| T04 | 規則が見出しの行だけ（化粧品と同じ）：`未評価`（理由：製品が規則に無い）。見本の lot（`SMARTPHONE`）が作られない。`total_lots` が化粧品と無関係な数にならない |
| T05 | 一部の製品だけ規則に無い：`一部未評価`、除いた製品と lot 数が出る。評価した範囲の値は、その製品だけのモデルで計算した値と同じ |
| T06 | `未評価` の snapshot を `attach_realized()` に渡しても、利益が 0 として計算されない |
| T07 | Value Chain：宣言の無いモデルでモデルに為替が無い → `data/ppc` の為替を読まず、他通貨の金額は未評価になる。宣言があれば今までどおり |
| T08 | `python -m wom.ppc`（販売の CSV なし）の見本の実演は今までどおり動く |

既存のテスト（`tests/test_ppc_run_info.py`・`tests/test_sim_mgmt_display.py` ほか、見本の切り替えを前提にしたもの）は、意味が変わるものだけ直し、どれをなぜ直したかを報告書に書く。全体の件数と時間は実行した後に書く。

## D. 化粧品での確かめ（作業用の写しで）

`output/bsseaf_cosmetics/C3a` の新しい写しを、headless（`run_headless_from_folder.run`）と Value Chain（`python -m tools.valuechain_run`）で回す。

| # | 確かめること |
|---|---|
| V1 | PPC が `未評価`（理由：製品が規則に無い、為替のファイルが無い）。snapshot に見本の lot 数・粗利率が出ない |
| V2 | 規則のファイルを消した写しでも、`data/ppc` の見本の規則に切り替わらず `未評価`（前回の「粗利率 30.4%」が出ない） |
| V3 | Value Chain の為替が `data/ppc` に切り替わらない |
| V4 | 数量の結果（Flow Check 表2、①〜⑤）は変わらない |

## E. 止める理由と申し送り

報告では、**止める理由**（動き・数字・誤読に関わる。先に直す）と**申し送り**（記録して進む）を分ける。些細なものは往復させずに直して報告だけにする。

止める理由に当たるもの：§A の事実が違う、golden のモデルで S3・S4 が起きていた（§A3）、golden が変わる、既存のモデルに宣言を足しても値が変わる。

## F. 報告書と commit

- 報告書：`docs/development/WOM_PPC_NoSilentFallback_Report.md`。着手時の SHA、§A2 の表、変えたファイル、テストの結果（実行した後の数）、§D の結果、止める理由と申し送り。
- 文書：`docs/WOM_Start_Here.md` の R12（未評価）と R 表・落とし穴に、共有の規則の宣言と `valuation_status` の要点を足す案を報告書に書く（Start Here の本文は Claude君が直す）。
- commit メッセージの下書きを、使われていない次の番号の `commit_msg<N>.txt` に書く。git の操作は大杉さんが行う。

## G. この依頼の後（金額の段階）

この依頼では金額の値を置かない。化粧品の価格・原価・為替・関税（設計書 A11）は、大杉さんが業務の仮定を決めた後に、Data として置く。その前に、歩留まり Part B（良品 1 lot 当たりの原価）が要るかを決める。

| 版 | 日付 | 内容 |
|---|---|---|
| v0.1 | 2026-10-26 | 初版 |
