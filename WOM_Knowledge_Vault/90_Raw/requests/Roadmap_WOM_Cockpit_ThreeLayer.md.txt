# WOM 経営コックピットへの道筋 — 三層計画を渡り歩く GUI に至る設計・開発手順

**作成日**: 2026年9月9日
**設計責任**: Claude君（Fable 5.1）
**対象**: 大杉さんレビュー（方針決定用。Code君への Request Letter ではない）
**位置づけ**: Phase 6 以降の複数リリースにまたがるロードマップ。個々の Phase 設計書は本書の合意後に別途起こす
**入力**: note 記事 rev.2/rev.3、ChatGPT君との GUI 見直し議論（2026-09-08）、`wom-v1r4m0` の実装確認

---

## 0. 結論を先に

到達目標は大杉さんの言葉どおり——

> 計画の三層構造を行き来しながら、P_greedy / P_grid / P_opt とその誤差を確認して、サプライチェーン・オペレーションと事業経営の数字を構造的に見直す。そのようなシームレスな操作性。

これは高い目標ですが、**到達不能ではありません。** 理由は、WOM の下層に必要な機能がすでに揃っていて、足りないのは「機能」ではなく**「層と層をつなぐ契約」と「それを見せる枠組み」**だからです。

ただし、**順序を間違えると届きません。** ChatGPT君の提案（機能中心 → 意思決定中心、Planning State を中心概念に、画面名＝経営上の問い）は正しい。私が補うのは一点だけです——

> **画面の棚卸しより先に、層間のデータ契約を決める。**
> 存在しないものは見せられない。そして現在、第1層（利益地形図）から第2層（Backward Planning）へ渡るデータは**存在しません。**

以下、その根拠と手順です。

---

## 1. 現状の事実（実装を確認した結果）

設計の前に、いつもどおり実装を確認しました。

### 1.1 GUI の現状

| 項目 | 実測 |
|---|---|
| `wom/gui/app.py` | **5,650行**、単一ファイル、tkinter（CLAUDE.md の記載 ~3,900行から成長） |
| タブ構成 | Charts / KPI Table / At-Risk SKUs / Scenario Delta / Management / PPC / Network / World Map / Debug の **9タブ** |
| 画面の単位 | **機能別**（ChatGPT君の指摘どおり「機能別メニューの積み上げ」） |
| 実行フロー | Load → Planning Engine → `_on_planning_done` → PPC 自動実行（第2層→第3層→PPC は既に一直線） |

### 1.2 決定的に重要な既存資産

```
tools/run_headless_from_folder.py
    run(model_dir, plugins_spec) → KPI snapshot dict
```

**GUI 抜きで Load → Planning → PPC を実行し、GUI の実値と一致することが golden で担保されている。** つまり、エンジンは既に GUI から分離されており、その分離が機械的に検証されています。これが、これから作る全てのものの土台です。

### 1.3 決定的に欠けているもの

| 欠落 | 実測 |
|---|---|
| A系統（`ask_global_allocation`）→ GUI | `wom/gui/app.py` / `main.py` に `ask_global_allocation` / `allocation` への参照**なし**。A系統は CLI と PNG で完結しており、GUI に載っていない |
| 第1層 → 第2層のデータ経路 | `wom/allocation/` に `demand_forecast` を書き出す箇所**なし**。利益地形図で選んだ配分は、Planning Engine に**渡らない** |
| 識別子チェーン | `allocation_id` は**コード・CSV・設計書のどこにも存在しない**（`scenario_id` は `ga_scenario_master.csv` のデータとしてのみ存在） |
| Planning State の概念 | 「いま見ている数字は仮説値か、実行可能値か」を区別する仕組みが**ない** |

`backward_planner.py:24-25` には次のコメントが残っています。

```
(Full WOM: market-priority allocation happens here.
 BackwardPlanner v1: 1-to-1 copy, allocation deferred to future step.)
```

Planning Engine 側も、市場配分が将来つながることを最初から想定していました。**つながっていないだけ**です。

### 1.4 note 記事の図5との関係

記事の図5「探索 → 計画 → 実行可能性検証 → 利益評価 → 修正」は、ChatGPT君の指摘で「WOM が**目指す**」と修正しました。実装上、この閉ループのうち**実在するのは「計画 → 実行可能性検証 → 利益評価」の3矢印だけ**です。「探索 → 計画」と「利益評価 → 修正（地形図へ戻る）」の2矢印が欠けています。

**コックピットとは、この2本の矢印を実装したうえで、5本の矢印を1つの操作として体験させるもの**——と定義すると、やるべきことが明確になります。

---

## 2. 「シームレス」を3つの条件に分解する

到達目標を、検証可能な条件に分けます。

| 条件 | 内容 | 現状 |
|---|---|---|
| **S1. 渡るものがある** | 層間を移動するとき、前の層の決定が次の層の入力になっている | ✗ 第1→第2、PPC→第1 が欠落 |
| **S2. どこにいるか分かる** | 画面上の数字が、どのシナリオ・どの配分・どの計画状態（仮説／実行可能）のものか常に表示される | ✗ 概念がない |
| **S3. 画面が問いの単位** | 画面名がアルゴリズム名ではなく経営上の問いであり、結論 → 根拠 → Drill-down の順に読める | ✗ 機能別9タブ |

**S1 が満たされないまま S2・S3 に着手すると、画面は作れても中身が空になります。** これがロードマップの順序を決めます。

---

## 3. ChatGPT君の提案への評価

### 3.1 そのまま採用するもの

- **機能中心 GUI → 意思決定中心 GUI** への転換
- **Planning Navigator**（Scenario → ①Management → ②Backward → ③Weekly PSI → ④PPC → Review）の常設
- **Planning State**（Pre-Plan / Feasible Plan）を GUI の中心概念にする
- **画面名＝経営上の問い**（「Merit Order 画面」ではなく「限られた能力をどこへ優先配分するか？」）
- **一画面一メッセージ**（結論 → 根拠 → Drill-down）
- **経営コックピットは Opportunity / Best / Robust が主役、Operational DD は Gap / Violation / Break Point が主役**という表示優先度の反転
- **Engine は固定し、Presentation Layer を再設計する**

これらは全て、note 記事の rev.3「順方向＝行き先、逆方向＝物差し」と整合しています。

### 3.2 補うもの

**(a) 「棚卸しから始める」の前に「データ契約」を置く。**
ChatGPT君は「現行 GUI の全画面を一枚ずつ棚卸しして、誰の何の判断のためかを再定義する」ことから始めるよう勧めています。棚卸し自体は必要です。しかし棚卸しの結論は「この画面はこの Planning State のこの問いを見せる」という形になるはずで、**Planning State が定義されていなければ結論が宙に浮きます。** 順序を逆にします。

**(b) Planning State は「画面上の表示」ではなく「ファイルとして存在する成果物」にする。**
ChatGPT君の例——

```
Scenario : FX150 / US Tariff 12.5%
Allocation : JP30 / US40 / EU30
Planning State : Pre-Plan
Version : A03
```

——は、そのまま **1つの JSON レコードの仕様**です。GUI が計算するのではなく、headless パイプラインが生成し、GUI はそれを読んで表示するだけ。こうすると golden で固定でき、GUI の実値との一致を機械的に検証できます（`run_headless_from_folder.py` と同じ原則）。

**(c) P_greedy / P_grid / P_opt を Planning State の一級のフィールドにする。**
大杉さんが「行き来しながら確認したい」と言われた3つの利益水準は、A系統の `compare_with_grid()` が**既に返しています**（Phase 6-1 で `structural_optimality_gap` が加わる）。あとは Planning State に載せるだけです。ChatGPT君の提案にはこの3水準が出てきませんが、rev.3 の「順方向＝行き先、逆方向＝物差し」を GUI で成立させるには、これが**中央に**なければなりません。

**(d) 「Planning Engine は作り直さない」を、禁足ルールの言葉で言い直す。**
第1→第2 の接続は Planning Engine の**入力**（`demand_forecast`）を差し替えるだけ、PPC→第1 の書き戻しは Planning Engine の**出力**を読むだけ。**どちらも禁足コア6ファイルに触れません。** これは設計上の幸運ではなく、A系統を Management 層の分析として PSI から切り離して設計してきた帰結です。

---

## 4. ロードマップ

```
Phase 6   N市場化                        ← 設計済み（requests/Phase6_DesignMD_NMarketHierarchy.md）
   │        コックピットが実在ケース（oil-global 21市場）で動くための前提
   ▼
Phase 7   Planning State と層間ハンドオフ  ← S1 を満たす。GUI は作らない
   │        「探索→計画」「利益評価→修正」の2矢印を実装し、図5の閉ループを本物にする
   ▼
Phase 8   Cockpit v1（画面体系の再設計）   ← S2・S3 を満たす。縦1本を通す
   │        Planning Navigator ＋ Planning State ヘッダ ＋ 第1層・第3層・Review の3画面
   ▼
Phase 9   Operational DD モード           ← 同じ画面、表示優先度の反転
            赤信号優先・提示された計画を物差しに当てる
```

### Phase 6 — N市場化（設計済み）

本ロードマップの前提として位置づけ直します。コックピットの検証台が soysauce（3市場）だけでは、「シームレス」の価値が伝わりません。`oil-global-2027`（21市場・8工場）で階層ドリルダウンが動いてはじめて、Management Lens が経営者の見る画面になります。

Phase 6 の3ステップは変更しません。**6-1（`true_optimum` 実計算）が Phase 7 の Planning State に `P_opt` を供給する**、という依存関係だけ明記します。

### Phase 7 — Planning State と層間ハンドオフ（**本ロードマップの要**）

**目的**: 図5の欠けている2本の矢印を実装し、閉ループを headless で1周させる。**GUI は一切作らない。**

**成果物1: Planning State レコード**（JSON、`output/planning_state/<allocation_id>.json`）

```json
{
  "allocation_id": "A03",
  "scenario_id": "s4_compound",
  "state": "pre_plan",                       // pre_plan | feasible_plan
  "allocation": {"JP": 0.10, "US": 0.45, "EU": 0.45},
  "profit_levels": {                          // A系統 compare_with_grid() の出力をそのまま載せる
    "P_greedy": 135529822.5,
    "P_grid":   132133072.5,
    "P_opt":    135529822.5,                  // Phase 6-1 以降。それまでは null
    "gap_amt": 3396750.0,
    "expected_gap": 3396750.0,
    "structural_residual": 0.0,
    "structural_optimality_gap": 0.0
  },
  "realized": null                            // feasible_plan になったとき埋まる（下記）
}
```

**成果物2: 第1層 → 第2層の変換**（「探索 → 計画」の矢印）

```
allocation_id を受け取り、
  ga_market_aggregation.csv の市場定義に従って
  demand_forecast.csv を配分比率でスケールした demand_forecast_<allocation_id>.csv を生成する
```

これが note 記事で「生産配分の確定の意思入れ」と呼んでいた操作の**実体**です。Planning Engine は生成された CSV を通常どおり読むだけなので、**禁足コア無変更**。

**成果物3: PPC → 第1層の書き戻し**（「利益評価 → 修正」の矢印）

Weekly PSI と PPC の結果から、以下を Planning State の `realized` に書き戻す。

```json
"realized": {
  "allocation": {"JP": 0.12, "US": 0.43, "EU": 0.45},   // 実際に供給できた配分
  "profit_ppc": 128900000.0,                            // PPC 台帳の実現利益
  "co_lots": 240,
  "capacity_violation_weeks": ["2027-W32", "2027-W33"],
  "gap_vs_plan_pct": -4.8
}
```

`state` が `pre_plan` → `feasible_plan` に変わる。**これで「①の利益地形図を見ていたときの計画」と「③Weekly PSI を通過した後の計画」が別物であることを、データ自身が語れる**ようになります。

**成果物4: 閉ループの headless 実行**

```
python -m tools.run_planning_loop --model-dir <case> --scenario s4_compound --allocation 0.10,0.45,0.45
```

A系統 → 変換 → `run_headless_from_folder.run()` → 書き戻し、を1コマンドで回す。**golden に固定する。**

**検証（この Phase の合否）**:
- soysauce `s1_base` で、格子最適点 (0.10, 0.45, 0.45) を意思入れして1周し、`realized.allocation` が需要天井の範囲で計画配分と整合すること
- 意思入れした配分の `demand_forecast` 合計が元の合計と一致すること（配分は需要を増やさない）
- golden 13ケースが不変（既存ケースは `allocation_id` なしで従来どおり動く＝後方互換）

**この Phase が終わった時点で、GUI がなくても「三層を行き来する」ことが CLI で可能になっています。** コックピットは、それを画面にするだけです。

### Phase 8 — Cockpit v1（画面体系の再設計）

**目的**: S2・S3 を満たす。ただし**全画面を作らない**。縦1本を通す。

**8-0 棚卸し**（ChatGPT君の提案。ここで実施）
現行9タブを「誰の・何の判断のため・どの Planning State を見せるか」で分類し、以下の3つに振り分ける。

- **主画面に昇格**（経営上の問いを持つもの）
- **Drill-down の葉として温存**（Charts / Network / World Map / PSI List 等。作り直さない）
- **Debug 系に降格**

**8-1 骨格**
- `wom/cockpit/` を新設（`app.py` の5,650行を分割するのではなく、**新しい入口を作り、既存パネルを部品として import する**。既存 `python -m main` は残す）
- Planning Navigator（上部常設）
- Planning State ヘッダ（`allocation_id` / `scenario_id` / `state` / 3つの利益水準を常時表示）

**8-2 縦1本（3画面）**

| 画面 | 経営上の問い | 中身 | Drill-down 先 |
|---|---|---|---|
| Management Lens | **どこへ配分すべきか／現在計画はどの位置にあるか** | 結論行（推奨配分・現状比・反転条件）→ 利益地形図（N≥4 は階層ドリルダウン）→ P_greedy/P_grid/P_opt と誤差 | Merit Order / Regime Map |
| Weekly PSI | **この計画は、どの週で成立しなくなるか** | 結論行（能力内の週の割合 or 超過週）→ 既存 PSI Chart | PSI List / Network |
| Decision Review | **次に何を変えるか／何が起きると判断が反転するか** | Pre-Plan vs Feasible Plan の差分、`gap_vs_plan_pct`、Regime Map の境界までの距離 | 全画面 |

Backward Planning と PPC の画面は **Phase 8 では作らない**（既存 Management / PPC タブを葉として使う）。縦1本が通ってから横に広げます。

**8-3 設計原則（この Phase で固定し、以降変えない）**
1. **画面はゼロロジック。** すべての数値は Planning State JSON か headless 関数の返り値。画面内で計算しない
2. **画面1枚＝経営上の問い1つ。** 画面タイトルは問いの形で書く
3. **結論 → 根拠 → Drill-down** の3段。結論行はテキスト3行以内
4. **既存パネルは壊さない。** 葉として再利用し、`python -m main` の従来 GUI も動き続ける
5. **tkinter ＋ matplotlib のみ。** スタンドアロン Windows PC 運用の制約は不変

### Phase 9 — Operational DD モード

**目的**: 同じ3画面で、表示優先度を反転させる。

- 入口が違う：「提示された事業計画」を `allocation_id` として登録し、それを**現在地ではなく検証対象**として置く
- 結論行が違う：Opportunity / Best / Robust ではなく **Gap / Violation / Break Point / Evidence**
- Management Lens の3つの利益水準は「行き先」ではなく「物差し」として描く（rev.3 の図をそのまま画面にする）
- Weekly PSI は「94% の週で能力内」ではなく「**W32–W35 で超過、CO 1,240 lot、売上前提を 4.3% 下回る**」を最初に出す

エンジンもデータも Phase 7/8 と共通。**Phase 9 は表示ルールの追加だけ**であり、これが「同じエンジン」の実証になります。

---

## 5. 最初の一歩

ロードマップ全体を承認いただく前でも、**今すぐ着手して無駄にならないもの**が2つあります。

**(1) Planning State のスキーマを決める（Phase 7 の設計書に先立って）**
上記 JSON 案を叩き台に、フィールドを確定する。特に `realized` に何を載せるか（CO / 能力超過週 / 実現利益 / 在庫）は、Operational DD で「赤信号」になるものを逆算して決めるべきです。これは大杉さんの実務感覚が要る判断です。

**(2) 現行9タブの棚卸し表を作る（Phase 8-0 の先行実施）**
「タブ名 / 誰が見る / 何を判断する / どの Planning State / 主画面・葉・Debug のどれ」の5列。コードを触らないので回帰リスクがなく、Phase 8 の設計書がそのまま書けます。ChatGPT君の提案どおり、ここは大杉さんご自身が一枚ずつ見るのが最も速いと思います。

---

## 6. 正直に書いておくべきリスクと制約

**R1. 5,650行の `app.py` を「分割」しようとしない。**
分割は回帰リスクが極めて高く、得るものが少ない。新しい入口（`wom/cockpit/`）を作って既存パネルを import する方式なら、既存 GUI は1行も変えずに済みます。

**R2. tkinter でのドリルダウン。**
「クリックすると下位の三角図に降りる」は tkinter で実装可能ですが、matplotlib の `FigureCanvasTkAgg` 上のクリックイベント処理は素朴です。Phase 8 の設計時に、**ドリルダウンを「別画面へ遷移」で実装するか「同一画面で差し替え」で実装するか**を最初に決める必要があります。前者のほうが tkinter では堅牢です。

**R3. `realized` の書き戻しは Planning Engine の出力を読むだけだが、`ForwardPlanner._actual_s` は GUI に露出していない。**
CLAUDE.md L479 の既知事象。真の欠品は `_actual_s` を見ないと分からない。Phase 7 で `realized` に欠品を載せるなら、この内部 dict を headless 側で読む経路を作る必要があります。**禁足コアの改変ではなく読み出しの追加**ですが、コアに近い箇所なので明示的にスコープに入れて扱います。

**R4. Planning State を導入すると、既存の `output/ppc/` の扱いを決める必要がある。**
CLAUDE.md L1030 の「フォルダ切替で古い値が残る」問題は、`allocation_id` で出力を分ければ構造的に解消しますが、既存のパス依存（`output/ppc/ppc_node_pl_summary.csv` 等）を Phase 7 で一斉に変えるのは危険です。**既存パスは残し、`allocation_id` 付きの出力を追加で生成する**方式を取ります。

**R5. 高い目標であることは変わらない。**
Phase 7〜9 は、それぞれ Phase 4/5 と同程度の規模です。ただし各 Phase が単独で価値を持つ（Phase 7 は CLI で閉ループ、Phase 8 は縦1本の画面、Phase 9 は DD モード）ように切ってあるので、**途中で止まっても中間成果が残ります。**

---

## 7. レビュー事項（大杉さんへ）

**R1. 順序の承認。** Phase 6 → 7 → 8 → 9 の順でよいか。特に「GUI を作る前に Phase 7 でデータ契約を固める」という順序に同意いただけるか。

**R2. Planning State の `realized` に何を載せるか。** Operational DD で「赤信号」にすべきもの（CO / 能力超過週 / 在庫膨張 / 実現利益の乖離 / その他）を、実務の観点で挙げていただきたい。

**R3. Phase 8 の縦1本を Management Lens / Weekly PSI / Decision Review の3画面でよいか。** Backward Planning や PPC を先に画面化すべき理由があれば伺いたい。

**R4. 本ロードマップの位置づけ。** `requests/` に置いていますが、複数リリースにまたがる方針文書なので `docs/design/` のほうが適切かもしれません。ご判断ください。

---

## 改版履歴

- 2026-09-09 rev.1 — 初版。大杉さんの「三層構造を行き来しながら P_greedy/P_grid/P_opt とその誤差を確認できるシームレスな経営コックピット」という到達目標と、ChatGPT君の GUI 見直し提案を受けて作成。実装確認の結果、**第1層→第2層のデータ経路と `allocation_id` が存在しない**ことを起点に、「画面の棚卸しより先に層間のデータ契約（Planning State）を決める」を基本方針とし、Phase 6（N市場化）→ 7（Planning State と層間ハンドオフ、GUI なし）→ 8（Cockpit v1、縦1本）→ 9（Operational DD モード）の順序を提案。
