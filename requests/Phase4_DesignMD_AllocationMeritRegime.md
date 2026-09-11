# Phase 4 実装設計 — 生産配分の利益地形図：メリットオーダー曲線とレジーム地図

**作成日**: 2026年9月8日
**設計責任**: Claude君
**対象**: 大杉さんレビュー → Code君実装
**優先度**: MEDIUM（2-3週間）
**ブランチ**: `wom-v1r4m0`
**前提**: Phase 3 完了（commit `b5128e8`、339件全PASS）

---

## 1. Phase 4 全体像

### 1.1 位置づけ — Phase 3 との決定的な違い

Phase 3 と Phase 4 は、**図法は似ているが対象問題が違う**。

| | Phase 3（済） | Phase 4（本文書） |
|---|---|---|
| 系統 | B系統 `wom/visualization/` | **A系統 `wom/allocation/`** |
| 対象問題 | 週次：どのサプライヤーからいくら調達するか | **年次：どの市場に何個供給するか** |
| 希少資源 | （なし。需要量が所与） | **醸造能力**（cap_wk × weeks） |
| ブロックの実体 | サプライヤー | **市場**（将来は市場×供給ルート） |
| 並び順 | 単価**昇順**（コスト最小化） | **単位マージン降順**（利益最大化） |
| 交点の意味 | 限界サプライヤーの単価 | **能力のシャドープライス λ** |

**描画コードの型は流用できるが、軸の意味はすべて入れ替わる。** Phase 3 の `plot_merit_order_curve()` をそのまま呼ぶのではなく、A系統用に別関数を起こす（§5.2）。

### 1.2 本 Phase のスコープ

- **① メリットオーダー曲線（配分版）** — 市場を単位マージン降順に積み、能力線との交点で λ を読む
- **② レジーム地図** — 外部環境パラメータ空間（例 USD/JPY × 原料USD価格）の相図。**市場数 N に依存しない**
- **検証台**: `data/sample/soysauce-jpy-2027-alloc`

### 1.3 スコープ外（Phase 5 以降）

- ③ Pareto ＋ 平行座標の配分版（利益 × ロバストネス）
- ④ 階層化三角図（`oil-global-2027` が適用先候補、設計書 Phase 3 §11.1）
- N≥4 市場への拡張（本 Phase は既存3市場で「三角図と結論が一致する」ことの確認まで）
- `AllocationMapPanel` の GUI 組込（A系統の積み残し、CLAUDE.md L1318）

### 1.4 なぜ soysauce から始めるか

**三角図で答えが出ている唯一のケース**であり、231点スキャンの回帰値（最大利益・尾根・台地・切替点117/119円・FXB）が CLAUDE.md L1310-1315 に確定記録されている。①②が同じ結論を返すかの**回帰テスト**に使える。ここが通らないと、他ケースへの展開も N 拡張も信用できない。

---

## 2. 事前調査：メリットオーダーは既存の地形図に何を足すか

**設計に着手する前に、実データで①の価値を検証した。** 以下は推定ではなく計算結果である。

### 2.1 `soysauce-jpy-2027-alloc` の素性

| 項目 | 値 | 出典 |
|---|---|---|
| 能力 cap | 800 lot/週 × 104週 = **83,200 lot** | `capacity_plan.csv`（1500→800 に絞った版） |
| 需要 JP / US / EU | 30,150 / 35,176 / 35,175 lot | `ga_market_aggregation.csv` の `base_qty_lot` 合計 |
| 需要合計 | 100,501 lot | |
| 充足率 | **82.8%**（配給が必要） | CLAUDE.md L1300 の記述と一致 |
| 需要天井 x | JP 0.3624 / US 0.4228 / EU 0.4228（合計 **1.2079**） | CLAUDE.md L1312「0.362/0.423/0.423・合計1.208」と一致 |
| 単位マージン（FX150・$6） | JP 750.0 / US 1747.5 / EU 1831.5 JPY/lot | `transmission.py` docstring 付録A.1 |

### 2.2 メリットオーダーの連続解

単位マージン降順に能力を割り当てる：

| 順位 | 市場 | 単位マージン | 幅（需要） | 割当 | 累積 |
|---|---|---|---|---|---|
| 1 | EU | 1,831.5 | 35,175 | 35,175 | 35,175 |
| 2 | US | 1,747.5 | 35,176 | 35,176 | 70,351 |
| 3 | **JP** | **750.0** | 30,150 | **12,849** | **83,200** ← 能力線が横切る |

- **λ（能力のシャドープライス）= 750 JPY/lot** — 限界市場は JP
- 配分 x = (JP **0.1544**, US 0.4228, EU 0.4228)
- 利益 = **135,529,822 JPY**

### 2.3 231点グリッド最適との乖離

| | 配分 x (JP, US, EU) | 利益 | 遊休能力 |
|---|---|---|---|
| ① メリットオーダー連続解 | (0.1544, 0.4228, 0.4228) | **135.53M** | 0 lot |
| 231点グリッド最適（δ=0.05） | (0.10, 0.45, 0.45) | 132.13M | 4,529 lot |

グリッド側は **CLAUDE.md L1311 の回帰値 `s1 = 132.1M` と一致**した（利益関数モデルの妥当性が確認できた）。δ=0.05 の全数探索でも最大は同じ (0.10, 0.45, 0.45) である。

**乖離 = +3,396,750 JPY（+2.57%）**

**原因**: 需要天井が 0.4228 なのに対し、δ=0.05 の格子は 0.45 までしか刻めない。US と EU をフルに供給しようとすると x を 0.45 に切り上げるしかなく、超過分（`q = min(x·cap, D)` で切り捨てられる）が **US 2,264 + EU 2,265 = 4,529 lot** の遊休能力になる。その能力を JP に回せば 4,529 × 750 = 3.40M の利益が取れる。

### 2.4 この乖離の解釈（**重要・設計の根拠**）

chatlog は「メリットオーダーの素朴解と grid_scan 実解の乖離こそが構造的発見」と予想していたが、**soysauce で観測された乖離は非凹性ではなく、格子解像度の誤差である。** ここを取り違えないことが重要なので明記する。

soysauce の利益関数は **分離可能かつ区分線形**（各市場の利益が `min(x·cap, D) × margin` で、需要上限で頭打ちするだけ）であり、関税割当の階段・ルート固定費・MOQ・ローカルコンテンツ要件のいずれも持たない。したがって**均等限界原理が厳密に成立し、メリットオーダーは連続最適の厳密解**である。乖離の全量が格子誤差に帰着する。

**これはむしろ好都合である。** soysauce で「格子誤差だけの状態」を較正しておけば、非凹なケース（`ev-thailand-2026`：LC率閾値で関税が跳ぶ）に移したとき、**観測された乖離から格子誤差分を差し引いた残りが、純粋に構造由来の発見**として切り出せる。soysauce を先に置く順序には、回帰テスト以上の意味がある。

### 2.5 既存の回帰値への含意

CLAUDE.md L1311 の「最大利益：s1=132.1M」は **δ=0.05 格子上の最大**であって連続最適ではない。

**回帰値を変更する必要はない**（格子スキャンの定義として正しく、golden 的な役割を果たしている）。ただしドキュメント上「格子上の最大」であることを明記し、①が出す連続最適と混同されないようにする。§9 の成功基準に含める。

---

## 3. ① メリットオーダー曲線（配分版）

### 3.1 図の仕様

- **X軸**: `Cumulative allocated quantity (lots)`
- **Y軸**: `Unit margin (JPY/lot)`
- **各市場** = 幅 `demand_qty` ／ 高さ `unit_pnl()["margin"]` の矩形。**単位マージン降順**に左から積む
- **縦線**: `cap = cap_wk × weeks`（能力線、黒破線）
- **交点の高さ** = **λ（能力のシャドープライス）**。水平補助線＋注記
- **塗り分け**: 能力線の左（供給される）は濃色、右は淡色。**能力線をまたぐ市場は2分割**（Phase 3 §3.1 と同じ）
- **注記**: 遊休能力（`cap − Σq`）と未充足需要（`Σ(D − q)`）を図中に明示

Phase 3 との実装上の差分は「並び順が降順」「幅が需要量」「λ が能力の価値」の3点。**矩形分割と λ 注記のロジックは Phase 3 の考え方をそのまま踏襲する。**

### 3.2 マージンが負の市場の扱い（**レビュー事項 R1**）

FX200・原料$8 のシナリオでは JP のマージンが **−105.0 JPY/lot** になる（`transmission.py` docstring 付録A.1）。

負マージンの市場は**能力があっても供給すべきでない**（供給するほど損をする）。したがって：

- メリットオーダーの積み上げは **マージン > 0 の市場のみ**を対象とする
- 負マージンの市場は矩形をY軸の負側に描き、**斜線ハッチで「供給対象外」**であることを示す
- この場合、能力線に到達する前に正マージン市場が尽きることがある。そのときは **λ = 0**（能力が余っている＝希少でない）とし、その旨を注記する

**現行の `evaluate_point()` はマージンの符号を見ずに `min(x·cap, D)` で配分するため、負マージン市場に配分した点も評価対象に含まれる。** これは格子スキャンの仕様として正しい（面を出すのが目的で最適化はしない）ので変更しないが、①は「あるべき配分」を示す図なので、負マージンを除外する扱いにする。**この非対称は意図的であり、図の注記に明示する。**

### 3.3 データ構造（純関数・テスト対象）

描画から独立させ、単体テストの対象にする。

```python
# wom/allocation/merit_order.py（新規）

def build_allocation_merit_order(
    blocks: Dict[str, CostBlock],
    sc: Scenario,
    cap_wk: float,
    *,
    transfer_price_usd: float = DEFAULT_TRANSFER_PRICE_USD,
    weeks: int = WEEKS,
) -> dict:
    """市場を単位マージン降順に積んだメリットオーダーを組む。

    Returns:
        {
            "cap": 83200.0,
            "blocks": [                       # 単位マージン降順
                {"market": "EU", "margin": 1831.5, "width": 35175,
                 "allocated": 35175, "cumulative": 35175, "served": "full"},
                {"market": "US", ..., "served": "full"},
                {"market": "JP", "margin": 750.0, "width": 30150,
                 "allocated": 12849, "cumulative": 83200, "served": "partial"},
            ],
            "excluded": [],                   # margin <= 0 で対象外にした市場
            "lambda": 750.0,                  # 能力のシャドープライス（余力ありなら 0.0）
            "marginal_market": "JP",          # None なら能力が余っている
            "x": {"JP": 0.1544, "US": 0.4228, "EU": 0.4228},
            "profit": 135529822.0,
            "idle": 0.0,                      # 遊休能力
            "unmet": {"JP": 17301, "US": 0, "EU": 0},
        }
    """
```

**`x` と `profit` を返すのが要点。** これにより §3.4 のグリッド比較が単なる引き算で書ける。

### 3.4 グリッド最適との比較（**①の主要な出力**）

```python
def compare_with_grid(
    mo: dict,                    # build_allocation_merit_order() の戻り値
    surface: List[dict],         # scan_surface() の戻り値
) -> dict:
    """メリットオーダー連続解と格子最適の乖離を定量化する。

    Returns:
        {
            "merit_order_profit": 135529822.0,
            "grid_best_profit": 132133072.0,   # best_point(surface)[0]
            "grid_best_x": (0.10, 0.45, 0.45),
            "gap_amt": 3396750.0,
            "gap_pct": 0.0257,
            "grid_idle": 4529.0,               # 格子最適点の遊休能力
            "attributable_to_grid_resolution": True,   # §3.5 の判定
        }
    """
```

### 3.5 乖離の帰属判定（**設計の肝**・rev.2 で全面差し替え）

乖離が「格子解像度」由来か「構造（非凹性）」由来かを機械的に切り分ける。

#### 3.5.1 初版のロジックとその欠陥（記録）

初版は「メリットオーダー解 `x_mo` の各成分を δ の倍数に切り上げ・切り捨てした全組合せのうち、単体制約 Σx=1 を満たすものの最大」を格子最適と比較する方式を指定していた。**これは誤りだった。**

soysauce での丸め候補は以下の3点にしかならない。

| 丸め候補 | 利益 |
|---|---|
| (0.15, 0.40, 0.45) | 131,939,812.5 |
| (0.15, 0.45, 0.40) | 131,782,380.0 |
| (0.20, 0.40, 0.40) | 131,589,120.0 |
| **格子最適 (0.10, 0.45, 0.45)** | **132,133,072.5** |

**格子最適点が候補に入らない。** `x_mo["JP"] = 0.1544` の切り捨ては 0.15、切り上げは 0.20 であり、0.10 はそのどちらでもないからである。US と EU を需要天井（0.4228）より上の 0.45 に切り上げると、**単体制約 Σx=1 により JP が 0.10 へ押し出される** — この押し出しは成分ごとの独立な丸めでは表現できない。

結果として相対誤差 0.146% が残り、実装側は許容誤差 `tol=0.005` を置いて回避せざるを得なかった。**閾値で症状を隠す形になり、非凹ケースで構造由来の乖離が閾値未満だった場合に False Negative になる。**

#### 3.5.2 採用する判定方法

**乖離は「格子最適点で遊んでいる能力を限界市場に回したときの利益増分」に等しい。**

```
expected_gap        = grid_idle × λ
structural_residual = gap_amt − expected_gap
```

**用語の意味**（rev.4 で追記）

| 記号 | 日本語 | 意味 | 単位 |
|---|---|---|---|
| `grid_idle` | **遊休能力** | 格子最適点で使われずに余っている生産能力。`evaluate_point()` が返す `idle`（= `cap − Σq`） | lot |
| `λ` | **シャドープライス**（能力の限界価値） | 能力をあと1 lot 増やせたら利益がいくら増えるか。メリットオーダー曲線で能力線と階段が交わる高さ＝**限界市場の単位マージン** | JPY/lot |
| `expected_gap` | **格子解像度で説明できる乖離** | 遊んでいる能力を限界市場に回したときの増益 | JPY |

**なぜ `grid_idle` が生じるのか**: 需要天井が `x = 0.4228` なのに δ=0.05 の格子は 0.45 までしか刻めない。US/EU をフル供給するには 0.45 に切り上げるしかなく、超過分は `q = min(x·cap, D)` で切り捨てられる。その捨てられた能力（US 2,264 + EU 2,265 = 4,529 lot）が `grid_idle` である。**格子の目が粗いせいで、使えたはずなのに使えなかった能力**、という意味を持つ。

**なぜ `λ` が限界市場の単価になるのか**: 能力が1 lot 増えたら、その1 lot は「まだ需要が残っている市場のうち最も儲かるところ」＝限界市場に回る。soysauce では EU も US も既に需要を満たしているので、増えた分は JP へ行く。だから λ = JP の単価 750 JPY/lot となる。

**掛け算になる理由**: メリットオーダーの連続解は、まさに**その遊休能力を限界市場に回している解**である。刻みの制約がないので `x_JP = 0.1544` のような中途半端な値が取れ、能力を1 lot も余らせない。格子最適点との違いはそこだけなので、利益の差もちょうど「余った能力 × その能力の価値」になる。

soysauce での検証：

| | 値 |
|---|---|
| 格子最適点の遊休能力 `grid_idle` | 4,529 lot |
| λ（限界市場 JP の単位マージン） | 750 JPY/lot |
| 予測乖離 `grid_idle × λ` | 3,396,750.0 JPY |
| 実測乖離 `merit_order_profit − grid_best_profit` | 3,396,750.0 JPY |
| **構造由来の残差** | **0.000000 JPY（厳密一致）** |

**理屈**: 格子最適点では `idle` だけ能力が遊んでいる。その能力を限界市場（マージン λ）に回せば `idle × λ` だけ利益が増える。メリットオーダー連続解はまさにそれをしている。したがって両者の差は `idle × λ` に厳密に一致する。

**成立条件（`absorbable`）**: 限界市場が格子最適点で `idle` 以上の未充足需要を残していること。soysauce では 21,830 ≥ 4,529 で成立。

#### 3.5.3 この方式の利点と、`residual` の解釈（**rev.3 で訂正**）

**利点**

- **恣意的な閾値が要らない。** 許容誤差は浮動小数の数値誤差分（`abs_tol = 1.0` JPY）のみ
- **`structural_residual` が非凹性の指標になる。** 線形・凹なケースではゼロ、非凹なケースでは非ゼロに振れる

**`residual` の符号別の意味づけ**

| `residual` | 意味 |
|---|---|
| ≈ 0 | 乖離は格子解像度で説明できる（線形・凹なケース。soysauce s1_base がこれ） |
| **< 0** | **メリットオーダーが真の最適を外している ＝ 非凹性の証拠。絶対値は取りこぼし量の下界** |
| > 0 | 想定外（要調査） |

**⚠️ 初版の記述の訂正**

初版は「非凹ケースでは `gap_amt > expected_gap` となり、超過分が定量値として切り出せる」と書いていたが、**符号が逆だった。**

理屈は単純である。非凹だとメリットオーダーが最適を外すので `mo_profit` が**下がる**。`gap_amt = mo_profit − grid_best` は縮み、多くの場合は負になる。一方 `expected_gap = grid_idle × λ` は格子最適点の性質だけで決まるので影響を受けない。よって `residual` は**負**に振れる。

判定式 `abs(structural_residual) <= abs_tol` は符号によらず False を返すので**実装の動作は正しかった**。訂正するのは意味づけのみであり、`compare_with_grid()` の変更は不要。

**⚠️ 非凹ケースでは分解の精度が落ちる**

Phase 5 の合成シナリオ `s9_fta_cliff`（soysauce・cap_wk=500・US 関税 0.125→0.000 が 25,000 lot で発動）で実測した内訳：

| | 金額 |
|---|---|
| 構造由来の取りこぼし（真の連続最適 − 貪欲） | **10,066,596** |
| 格子解像度の誤差（真の連続最適 − 格子最適） | 338,496 |
| `residual` = −9,728,100 → `\|residual\|` は構造由来の **96.6%** | （**下界**） |

非凹だと格子最適点が能力を使い切る（`grid_idle = 0`）ため `expected_gap = 0` となり、格子誤差の分だけ `|residual|` が構造由来を**過小評価**する。

**したがって `residual` は「厳密な分解」ではなく、符号を非凹性の指標として、絶対値を取りこぼし量の下界として使う。** 詳細は `requests/Phase5_DesignMD_NonConcaveTariff.md` §2.4 を参照。

**「下界」（lower bound）とは何か**（rev.4 で追記）

**「本当の値は、少なくともこれ以上ある」と保証できる数**のことである。

本来測りたいのは `構造由来の取りこぼし（structural optimality gap）= P_opt − P_greedy`（真の最適との差）だが、**真の最適 `P_opt` は普通わからない**。刻みなしで全配分を試す必要があり、市場数が増えれば計算できなくなる。実際に計算できるのは格子最適どまりなので、実装が返すのは `P_greedy − P_grid` である。

格子（231点）は連続な配分空間から点を抜き出したものなので、**部分集合の最大値が全体の最大値を超えることはない**。

```
        格子最適  ≤  真の最適
  ⇒  |structural_residual| = 格子最適 − 貪欲
                           ≤ 真の最適 − 貪欲 = structural_optimality_gap
```

したがって `|structural_residual|` は**必ず本当の取りこぼし以下**になる。過小に出ることはあっても、**過大に出ることは原理的にない**。これが「下界」と呼べる理由である。

そして両者の差は、格子自身の誤差にちょうど一致する。

```
|structural_residual|  +  格子解像度の誤差  =  structural_optimality_gap
      9,728,100         +      338,496       =      10,066,596
```

`|residual|` が 96.6% にしかならなかったのは、真の最適の代わりに格子最適を引き算の相手に使っている以上、格子自身の誤差 338,496 の分だけ必ず少なく出るためである。

**実務上これは良い性質である。** 「構造要因で**少なくとも 973万円**を取りこぼしている」と報告できる。実際は 1,006万円かもしれないが、973万を下回ることはないと保証できる。逆に過大に出る指標（上界、upper bound）だと、報告した後に実額がそれを下回る事故が起きる。**安全側に外れる指標のほうが、意思決定の材料としては使いやすい。**

#### 3.5.4 API

```python
def compare_with_grid(
    mo: dict,
    surface: List[dict],
    *,
    abs_tol: float = 1.0,      # JPY。数値誤差の許容のみ
) -> dict:
    """Returns:
        {
            "merit_order_profit", "grid_best_profit", "grid_best_x",
            "gap_amt", "gap_pct",
            "grid_idle", "lambda", "marginal_market",
            "marginal_unmet_at_grid_best",
            "absorbable": bool,
            "expected_gap_from_grid_resolution",
            "structural_residual",           # ★ Phase 5 で使う主要な出力
            "structural_residual_pct",
            "attributable_to_grid_resolution": bool,
        }
    """
```

判定：

```python
attributable = absorbable and abs(structural_residual) <= abs_tol
```

**能力が制約にならない場合**（`marginal_market is None`、λ=0）は `expected_gap = 0` / `absorbable = False` / `attributable = False` とする。この場合そもそも乖離がほぼゼロになる（連続解も格子解も全需要を満たせる）ため、False で差し支えない。

### 3.6 Before/After 重ね描き

FX を動かすと市場の順位が入れ替わる。既存の `switching_points()` が **117円 / 119円** を切替点として記録しているので、その前後（例 FX=115 と FX=125）を Before/After に取れば順位入替が図に出る。

Phase 3 の `plot_merit_order_shift()` と同じ構成（2本の階段重畳・λ 水平線・需要線・交点マーカー・順位入替の注記）。

### 3.7 描画関数

```python
# tools/plot_allocation_merit_regime.py（新規）

def plot_allocation_merit_order(mo: dict, out: str, *,
                                comparison: Optional[dict] = None,
                                title: Optional[str] = None) -> str
def plot_allocation_merit_shift(mo_before: dict, mo_after: dict, out: str, *,
                                labels: Tuple[str, str] = ("Before", "After"),
                                title: Optional[str] = None) -> str
```

`comparison` が渡されたら、グリッド最適の利益水準と乖離額を図中に注記する。

---

## 4. ② レジーム地図

### 4.1 何を描くか

**配分空間ではなく、外部環境パラメータ空間の2次元平面**を描き、各点を「そこで最適となる配分パターン」で塗り分ける。境界線が決定反転面である。

描く平面はこちらが選ぶので**常に2次元＝市場数 N に依存しない**。これが chatlog の言う「汎用の主力」の理由である。

### 4.2 レジームの定義（**既存資産との接続**）

レジーム = **`market_ranking()` が返す市場の優先順位**（3市場なら最大 3! = 6 通り）。

これは既存の `switching_points()` が1次元（FX軸）で走査しているものと**同じ数学的対象**である。②はその2次元一般化にすぎない。したがって：

- 実装は `market_ranking()` を2次元グリッドで呼ぶだけで、新しい数学は要らない
- **`mat = 6.0` の水平断面が `switching_points()` の 117円/119円 を再現する**ことが回帰テストになる（§7.2）
- 決定反転テストという既存の V&V 方法論にそのまま接続する

**優先順位を採り、格子スキャンの argmax を採らない理由**: (a) 順位は連続量から決まるので境界が滑らかで、格子誤差（§2.3）の影響を受けない。(b) `market_ranking()` は O(N log N) なので、231点スキャンを各パラメータ点で回すのに比べて3桁速い。(c) 「どの市場を優先するか」という経営判断の単位と一致する。

### 4.3 軸の選択

`Scenario` は `fx_usd` / `material_usd` / `eur_per_usd` を持ち、`CostBlock` は市場別の `tariff_rate` を持つ。軸は以下から2つを選べる設計にする。

| 軸 | 実体 | 既定範囲 | 備考 |
|---|---|---|---|
| `fx_usd` | `Scenario.fx_usd` | 100〜220 | `switching_points()` の走査範囲に合わせる |
| `material_usd` | `Scenario.material_usd` | 4.0〜10.0 | 交互作用分析の基準 (6.0) とショック (8.0) を含む |
| `tariff_rate:<市場>` | `CostBlock.tariff_rate` の上書き | 0.00〜0.30 | s6 の US 25% を含む |

**既定は `(fx_usd, material_usd)`。** 交互作用分析（`interaction()`、基準 150/6・ショック 200/8）と同じ平面であり、確定済みの回帰値（base −8.3M / −40.2%）と直接照合できるため。

chatlog が挙げた「USD/JPY × 関税率」は `(fx_usd, tariff_rate:US)` で描ける。

### 4.4 データ構造（純関数・テスト対象）

```python
# wom/allocation/regime_map.py（新規）

def scan_regime_grid(
    blocks: Dict[str, CostBlock],
    axis_x: str, x_values: Sequence[float],
    axis_y: str, y_values: Sequence[float],
    *,
    transfer_price_usd: float = DEFAULT_TRANSFER_PRICE_USD,
    base_scenario: Optional[Scenario] = None,
) -> dict:
    """外部環境パラメータ平面を走査し、各点の市場優先順位を返す。

    axis_x / axis_y: "fx_usd" | "material_usd" | "tariff_rate:<市場>"

    Returns:
        {
            "axis_x": "fx_usd", "x_values": [...],
            "axis_y": "material_usd", "y_values": [...],
            "regimes": [["EU>US>JP", ...], ...],   # [y][x] の順序ラベル
            "regime_ids": [[0, 0, 1, ...], ...],   # 描画用の整数ID
            "regime_labels": ["EU>US>JP", "US>EU>JP", ...],  # ID → ラベル
            "margins": [[{"JP":..,"US":..,"EU":..}, ...], ...],
            "negative_margin_mask": [[["JP"], [], ...], ...],  # §3.2 と整合
        }
    """
```

**`negative_margin_mask` を持たせる**のは、①でマージンが負の市場を除外する扱い（§3.2）と地図側の見え方を一致させるため。負マージン市場を含む領域は、地図上でも別扱いにする。

### 4.5 図の仕様

- 2次元ヒートマップ（`pcolormesh` または `imshow`）。各セルを **regime_id** で塗り分け、`ListedColormap` で離散色にする
- **境界線**（決定反転面）を `contour` で重ね描き
- **凡例**は色 → 順位ラベル（`EU>US>JP` 等）の対応
- **基準点**（150, 6.0）に ● 、**ショック点**（200, 8.0）に ★ を打つ
- 負マージン市場が存在する領域は**斜線ハッチ**を重ね、「この領域ではその市場に供給すべきでない」ことを示す
- 軸ラベルは実値（`USD/JPY`、`Material price (USD/lot)` 等）

### 4.6 描画関数

```python
def plot_regime_map(grid: dict, out: str, *,
                    mark_points: Optional[List[Tuple[float, float, str]]] = None,
                    title: Optional[str] = None) -> str
```

---

## 5. 共通仕様

### 5.1 技術制約（Phase 3 §6.1 を全面的に継承）

1. **matplotlib のみ。** plotly / bokeh / dash / streamlit / seaborn 禁止（情報セキュリティ／スタンドアロン Windows PC 運用）
2. **新規依存パッケージを追加しない**
3. `matplotlib.use("Agg")` を pyplot import の前
4. **図中のテキストはすべて英語**（日本語は本文書とソースコメントのみ）
5. **各描画関数は出力パスを返す**、`plt.close(fig)` する
6. **凡例をデータの上に重ねない。** 軸レンジを緩めて凡例のための余白を作らない

### 5.2 ファイル配置

| 対象 | パス | 扱い |
|---|---|---|
| ① ロジック | `wom/allocation/merit_order.py` | **新規** |
| ② ロジック | `wom/allocation/regime_map.py` | **新規** |
| 描画＋CLI | `tools/plot_allocation_merit_regime.py` | **新規** |
| 既存 A系統 | `wom/allocation/{transmission,cost_block,grid,analytics}.py` | **無変更** |
| 既存 B系統 | `wom/visualization/*` | **無変更** |
| 出力先 | `output/allocation_p4/` | `.gitignore` の `output/` 配下（rev.2 で `output/allocation/` から変更。A系統の既存出力 `ga_*.csv` / `tile.png` / `layers.png` と混ざらないよう分ける） |
| テスト | `tests/test_allocation_merit_order.py` / `tests/test_allocation_regime_map.py` | **新規** |

**Phase 3 の `tools/plot_merit_order_suite.py` は流用せず別ファイルにする。** 対象問題が違い、軸の意味も並び順も異なるため、同居させると読み手が混乱する（§1.1）。

### 5.3 CLI

```bash
python -m tools.plot_allocation_merit_regime \
    --model-dir data/sample/soysauce-jpy-2027-alloc \
    --cap-wk 800 --scenario s1_base \
    --out output/allocation_p4/

python -m tools.plot_allocation_merit_regime --model-dir <dir> --demo
```

**`.gitignore` について（rev.2 で追記）**: `.gitignore` には `output/` はあるが **`out/` が無い**。既存 A系統の `tools/plot_allocation_map.py` は既定出力先が `out/` のため、引数なしで実行すると PNG がコミット対象に入る。**`out/` を `.gitignore` に追加すること**（Phase 4 以前からの潜在漏れ）。

生成物：

| ファイル名 | 内容 |
|---|---|
| `alloc_merit_order.png` | ① 基準シナリオのメリットオーダー曲線（グリッド比較注記つき） |
| `alloc_merit_shift.png` | ① FX切替点前後の Before/After |
| `alloc_regime_map.png` | ② fx × material の相図 |
| `alloc_regime_map_tariff.png` | ② fx × US関税率の相図 |

### 5.4 禁足ルールとの関係

Planning Engine 保護対象コアには**一切触れない**。golden 13ケースにも影響しない。A系統は `ask_global_allocation` として既に Management 層に位置づけられている（CLAUDE.md L1297）。

---

## 6. 実装スケジュール

| Timeline | Task | Owner | Deliverable |
|---|---|---|---|
| **Week 8-1** | ① ロジック（`merit_order.py`）＋テスト | Code君 | 3関数 + 8テスト |
| **Week 8-2** | 大杉さんレビュー | 大杉さん | 乖離の帰属判定（§3.5）の妥当性確認 |
| **Week 9-1** | ② ロジック（`regime_map.py`）＋テスト | Code君 | 1関数 + 5テスト |
| **Week 9-2** | 描画・CLI・統合 | Code君 | 3描画関数 + 4テスト |
| **Week 10** | 大杉さん目視QA・ドキュメント | 両者 | `docs/development/wom-v1r4m0_phase4_allocation.md` |

---

## 7. テスト計画

### 7.1 ① メリットオーダー（`tests/test_allocation_merit_order.py`、9件）

1. `test_merit_order_descending` — ブロックが単位マージン**降順**（昇順でない）
2. `test_merit_order_lambda_is_marginal_market_margin` — λ が限界市場のマージンと一致
3. `test_merit_order_soysauce_regression` — **soysauce 実データで λ=750、x=(0.1544, 0.4228, 0.4228)、利益 135,529,822 JPY**（§2.2 の値を固定）
4. `test_merit_order_capacity_surplus` — 需要合計 < 能力のとき λ=0、`marginal_market` が None、`idle` > 0
5. `test_merit_order_excludes_negative_margin` — FX200/$8 で JP（−105）が `excluded` に入り、配分されない
6. `test_compare_with_grid_soysauce` — **グリッド最適 132,133,072 JPY、乖離 3,396,750 JPY（+2.57%）**（§2.3 の値を固定）
7. `test_gap_attributable_to_grid_resolution` — soysauce で `structural_residual` が 1 JPY 未満、`absorbable` / `attributable_to_grid_resolution` がともに True
8. `test_merit_order_x_sums_to_one_when_capacity_binding` — 能力が制約になるとき Σx = 1.0
9. `test_expected_gap_equals_idle_times_lambda`（rev.2 で追加）— **恒等式 `gap_amt == grid_idle × λ`**（4,529 × 750 = 3,396,750）と、限界市場が idle を吸収できること（21,830 ≥ 4,529）を固定。§3.5.2 の判定の根拠そのもの

### 7.2 ② レジーム地図（`tests/test_allocation_regime_map.py`、5件）

10. `test_regime_map_reproduces_switching_points` — **`material_usd=6.0` の水平断面が `switching_points()` の切替点（117円 / 119円）を再現する**（②が既存 V&V と同じ対象を見ていることの証明。**最重要**）
11. `test_regime_map_axis_tariff` — `tariff_rate:US` を軸に取れること
12. `test_regime_map_regime_ids_consistent` — `regime_ids` と `regime_labels` の対応が全点で整合
13. `test_regime_map_negative_margin_mask` — 高FX・高原料の隅で JP が `negative_margin_mask` に入る
14. `test_regime_map_invalid_axis` — 不正な軸名は `ValueError`

### 7.3 描画スモーク（同ファイルに追記、4件）

`tests/test_allocation_plot.py` と同じ方式（例外なく画像が生成されること。見た目は人手 QA）。

15. `test_plot_allocation_merit_order`
16. `test_plot_allocation_merit_shift`
17. `test_plot_regime_map`
18. `test_cli_demo_generates_all`

### 7.4 合計

| | 件数 |
|---|---|
| Phase 3 完了時点 | 339 |
| Phase 4 初版 | 17 |
| rev.2 で追加（§7.1-9） | 1 |
| **合計** | **357 件 全PASS** |

既存 339 件に回帰なし、golden 13ケース不変を維持すること。

---

## 8. 成功基準

- [ ] `build_allocation_merit_order()` が soysauce で λ=750 / x=(0.1544, 0.4228, 0.4228) / 利益 135,529,822 JPY を返す
- [ ] `compare_with_grid()` がグリッド最適 132,133,072 JPY と乖離 +2.57% を返し、**CLAUDE.md L1311 の回帰値 s1=132.1M と整合する**
- [ ] **`gap_amt == grid_idle × λ`（4,529 × 750 = 3,396,750 JPY）が厳密に成立し、`structural_residual` が 1 JPY 未満**
- [ ] `attributable_to_grid_resolution` が soysauce で True（恣意的な閾値に依存せずに）
- [ ] **`scan_regime_grid()` の mat=6.0 断面が `switching_points()` の 117円/119円 を再現する**
- [ ] 負マージン市場が①で除外され、②でハッチ表示される
- [ ] 4枚の図が `--demo` で一発生成され、目視 QA を通過
- [ ] **①の注記が軸の下にあり判読できる**（降順に積む以上、左上は構造的に埋まる。rev.2）
- [ ] **Before/After の凡例が `lower left` にあり After 曲線と重なっていない**（rev.2）
- [ ] **`.gitignore` に `out/` があり、`git status` に `out/` が現れない**（rev.2）
- [ ] 357件全PASS（既存339件に回帰なし、golden 13ケース不変）
- [ ] 既存 `wom/allocation/` の4モジュールが**無変更**
- [ ] Web系GUIライブラリを導入していない／図中テキストが全て英語
- [ ] **CLAUDE.md L1311 の「最大利益 s1=132.1M」に「δ=0.05 格子上の最大」である旨を追記**（§2.5）

---

## 9. レビュー事項と決定（2026-09-08）

| # | 箇所 | 内容 | 決定 |
|---|---|---|---|
| **R1** | §3.2 | 負マージン市場を①から除外し、負側にハッチ矩形で描くか | ✅ **確定（除外する）** — `evaluate_point()` との非対称は意図的。図の注記で明示 |
| **R2** | §3.5 | 乖離の帰属判定の方法 | ⚠️ **初版のロジックに欠陥。rev.2 で `idle × λ` 方式に差し替え**（§3.5.1-3.5.2）。成分ごとの独立な丸めでは単体制約による押し出しを表現できず、格子最適点が候補に入らなかった |
| **R3** | §4.3 | レジーム地図の既定軸 | ✅ **確定** — `(fx_usd, material_usd)`。`tariff_rate:<市場>` も軸に取れる設計 |
| **R4** | §2.5 / §8 | CLAUDE.md L1311 の回帰値への注記 | ✅ **確定（追記する。値は変更しない）** — 実装時に追記済み |

**R1 / R3 / R4 は Code君が設計書の推奨どおりに実装で確定させた。** R2 のみ、実装後の検証で初版の欠陥が判明したため rev.2 で差し替える（修正依頼 `requests/request_fix_phase4_gap_attribution.md` G2）。

---

## 10. Phase 5 への引き継ぎ

| Phase 5 の候補 | 本 Phase の土台 | 必要な差分 |
|---|---|---|
| ③ Pareto ＋ 平行座標（配分版） | Phase 3 の `plot_pareto_scatter` / `plot_parallel_coordinates` ＋ A系統 `robust_point()` | 目的軸を Cost/Quality/LT から**利益 × ロバストネス（minimax）**へ。share 軸は市場配分比率になる（Phase 3 §5.2.1 の和集合方式がそのまま使える） |
| ④ 階層化三角図 | 既存 `tools/plot_allocation_map.py` の三角図 | `oil-global-2027`（日本／欧州／米州 × Local/Import）を適用先に。束ね方の感度分析が要る |
| N≥4 市場への拡張 | ① と ② | ①は N 非依存、②も N 非依存。**③④より先に N を拡げられる**のはこの2つだけ |
| 非凹ケースでの構造的発見 | §3.5 の帰属判定が返す **`structural_residual`** | soysauce では 0（線形）であることを確認済みなので、**負に振れれば非凹性と断定できる**（rev.3 で符号を訂正）。ただし `ev-thailand-2026` に直接は適用できない — 現行の伝達式は関税率が固定スカラーで構造的に線形であり、LC率閾値がモデルに存在しないため residual は必ずゼロになる。**先に伝達式へ数量依存の関税を導入する必要がある**（Phase 5 で対応、`requests/Phase5_DesignMD_NonConcaveTariff.md` §1.2） |

---

**次のステップ**: `requests/request_fix_phase4_gap_attribution.md` に基づき Code君が修正（G1-G4）

**改訂履歴**
- 2026-09-08 初版
- 2026-09-08 rev.2 — 実装完了（356件全PASS）後の検証・目視QAを反映。
  **§3.5 の帰属判定ロジックを全面差し替え**（初版の「成分ごとの丸め」は単体制約による押し出しを表現できず、格子最適点が候補に入らなかった。`idle × λ` 方式に変更し soysauce で厳密一致を確認）。
  §5.2/§5.3 出力先を `output/allocation_p4/` に追認、`.gitignore` への `out/` 追加を追記。
  §7 にテスト1件追加（357件）。§8 に注記・凡例・`.gitignore` の確認項目を追加。§9 を決定表に更新。§10 の Phase 5 引き継ぎを `structural_residual` ベースに具体化。
  修正依頼は `requests/request_fix_phase4_gap_attribution.md`
- 2026-09-08 rev.3 — **§3.5.3 の `residual` の符号を訂正**。初版・rev.2 は「非凹ケースでは `gap_amt > expected_gap`」と書いていたが逆で、実際には `residual` が**負**に振れる（非凹だとメリットオーダーが最適を外して `mo_profit` が下がるため）。符号別の意味づけ表を追加し、非凹ケースでは `grid_idle = 0` となって分解精度が落ちるため **`|residual|` は取りこぼし量の下界**であることを明記。§10 の引き継ぎに「ev-thailand には現行の伝達式では適用できない（関税率が固定スカラーで線形）」ことを追記。**実装（`compare_with_grid()`）の変更は不要** — 判定式は符号によらず正しく働いていた。検証の詳細は `requests/Phase5_DesignMD_NonConcaveTariff.md` §2
- 2026-09-09 rev.4 — **用語の平易な説明を追記**（読み手が詰まった箇所の解消）。§3.5.2 に `grid_idle`（遊休能力）/ `λ`（シャドープライス）/ `expected_gap`（格子解像度で説明できる乖離）の意味・単位・なぜその値になるのか・なぜ掛け算なのかを追記。§3.5.3 に「**下界（lower bound）とは何か**」を追記 — 格子は連続空間の部分集合なので `格子最適 ≤ 真の最適`、したがって `|structural_residual|` は必ず本当の取りこぼし以下になる（過大に出ることは原理的にない）こと、恒等式 `|residual| + 格子誤差 = structural_optimality_gap`（9,728,100 + 338,496 = 10,066,596）、および「安全側に外れる指標のほうが意思決定に使いやすい」という実務上の含意。内容の変更はなく説明の追加のみ。`gap_abs` → `gap_amt` の改名は commit `5f46ffc` で反映済み
- 2026-09-11 rev.5 — Phase 6-1（`true_optimum` の実計算化）の実装により、§3.5.3 の恒等式の例を実測値に更新（`9,728,100 + 338,496 = 10,066,596`、`|residual|` は構造由来の **96.6%**）。旧値 `10,057,058 / 328,958 / 96.7%` は Phase 5 設計書 rev.1 の手計算に基づくもので、**その手計算は最適化を誤っていた**（差 +9,538.5 の分解は Phase 6 設計書 §3.5 に記録）。下界であるという主張と説明そのものは変わらない
