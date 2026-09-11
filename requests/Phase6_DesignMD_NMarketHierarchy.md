# Phase 6 実装設計 — N市場化：真の最適の実計算、次元の一般化、階層化単体格子

**作成日**: 2026年9月9日
**設計責任**: Claude君
**対象**: 大杉さんレビュー → Code君実装
**優先度**: HIGH（Phase 5 完了により前提が揃ったため）
**ブランチ**: `wom-v1r4m0`
**前提**: Phase 5 完了（commit `a7011be` / `40736a8` / `5f46ffc` / `d9c3d25`、370件全PASS）

---

## 1. Phase 6 全体像

### 1.1 目的

**A系統（`ask_global_allocation`）を、3市場固定から N 市場へ解放する。**

Phase 4 / 5 で、配分問題を「メリットオーダー（貪欲）」「231点格子」「真の最適」の3水準で読み解く枠組みが完成した。ただしこの枠組みは、**すべて3市場固定の上に載っている**。

- `wom/allocation/grid.py:24` — `MARKETS: Tuple[str, str, str] = ("JP", "US", "EU")`
- `simplex_grid()` — 二重ループで3次元単体を生成（次元がコードに埋まっている）
- `tools/demo_allocation_nonconcave.py` — `true_optimum = 103_881_758.0`（手計算値のハードコード）**→ 6-1 で撤去済み**

Phase 6 は、この3つを順に外す。

### 1.2 なぜ「N市場化」を1つの Phase にまとめるか（**設計判断の記録**）

当初は Phase 6 のバックログを独立した5項目として並べていた（`MARKETS` ハードコード除去 / `true_optimum` 実計算化 / ev-thailand の `ga_*.csv` 作成 / パレート＋平行座標の配分版 / 階層的三角測量）。

大杉さんからの問い「**直角三角図のN階層化の優先度は低いのか**」を受けて再検討した結果、**この整理は誤りである**と判断した。理由は2つある。

**(1) 階層化は「4番目の可視化手法」ではなく、N市場化そのものの実現手段である。**

δ=0.05 の単体格子の点数は、市場数 N に対して `C(20+N−1, N−1)` で増える。

| N | 格子点数 | 備考 |
|---:|---:|---|
| 3 | **231** | 現行（soysauce-jpy-2027-alloc） |
| 4 | 1,771 | |
| 5 | 10,626 | |
| 6 | 53,130 | **全数評価が現実的な上限** |
| 8 | 888,030 | |
| 10 | 10,015,005 | |
| 12 | 84,672,315 | |
| **21** | **137,846,528,820** | **`oil-global-2027`（marketing ノード21件）** |

`oil-global-2027` は約 **1,378億点**。grid scan という方式そのものが N=10 前後で破綻し、実在ケースには到底届かない。

さらに重要なのは、**台地検出とロバスト点がこの `surface` の上に載っている**ことである。

```
wom/allocation/grid.py:85      best_point()   → 台地（最大値の plateau_tol 以内の点群）
wom/allocation/analytics.py:83  robust_point() → 台地上のミニマックス点
```

つまり N が増えると、**図が描けなくなるより先に、`plateau_size` も `robust_point` も計算できなくなる。** 階層化はこの爆発を回避する唯一の現実的手段であり、描画手法ではなく**探索手法**である。

**(2) 4枚の地図のうち、地形（台地・尾根・ロバストネス）を担うのは第1の地図だけである。**

Merit Order（Phase 4）は N 非依存で「どの順に積むか」を答える。Regime Map（Phase 4）は常に2次元平面なので N 非依存で「どこで判断が反転するか」を答える。この2つが N の問題を解いているように見えたのが、当初の誤った優先度づけの原因である。

しかし、この2枚は**「最適点の周りがどれだけ平らか」を答えない**。「最適解はどこか」ではなく「どこまで動かしても安全か」——WOM の中心的な主張を担っているのは地形だけであり、それが N=3 でしか出せないなら、主張自体が N=3 に限定される。

### 1.3 本 Phase のスコープ（3ステップ、この順序）

| ステップ | 内容 | なぜこの順序か |
|---|---|---|
| **6-1** | `true_optimum` の実計算化（`structural_optimality_gap`） | **誤差の物差しを先に作る。** 6-3 の階層化はそれ自体が近似なので、誤差を測れないまま導入してはならない |
| **6-2** | 次元の一般化（`MARKETS` / `simplex_grid()`） | N≥4 のケースが作れるようにする。6-3 の前提 |
| **6-3** | 階層化単体格子（`hierarchical_simplex`） | 爆発の回避。6-1 の物差しで誤差を測りながら導入する |

6-1 と 6-2 は互いに独立なので**並行実装可能**。6-3 は両方の完了後。

### 1.4 スコープ外（Phase 7 以降へ送る）

- パレート＋平行座標の**配分版**（B系統には Phase 3 で実装済み。A系統版は N市場化の後）
- `ev-thailand-2026` の `ga_*.csv` 作成と適用（Phase 5 で soysauce 合成シナリオによる検証は完了済みのため、急がない）
- GUI（Management Cockpit）への階層ドリルダウンの配線
- 週次 PSI（Planning Engine）との接続。**本 Phase は Management 層の分析に閉じる**

---

## 2. 用語の整理（**先に潰しておく落とし穴**）

現行文書には、**同じ英語名で違うものを指す記述が2つある**。

| 現行の記述 | 実際に指しているもの | 空間 |
|---|---|---|
| `docs/development/wom-v1r4m0_profit_landscape_dev_guide.md` §2.4<br>「Hierarchical Triangulation」 | 4つの目的関数（Cost / Lead Time / Quality / Flexibility）を層別に2D射影する | **目的空間** |
| `requests/Phase3_DesignMD_Visualization.md` §1.3<br>「階層化三角図（Hierarchical Triangulation）」 | 3市場の直角三角図を N 市場へ階層化する | **配分空間** |

`gap_abs` と同じ構造の落とし穴である。実装に入る前に名前を分ける。

**確定案:**

| 対象 | 日本語 | 英語 / 識別子 |
|---|---|---|
| **配分空間**の階層化（本 Phase 6-3） | **階層化単体格子** | `hierarchical_simplex` |
| **目的空間**の階層化（Phase 7 以降） | 階層化三角分割 | `hierarchical_triangulation`（現行名を維持） |

`Phase3_DesignMD_Visualization.md` §1.3 および `Phase3_RequestLetter_to_CodeKun.md` の該当行は、`hierarchical_simplex` へ表記を改める（**スコープ外項目の名称変更のみ。内容の変更なし**）。

---

## 3. ステップ 6-1 — `true_optimum` の実計算化

### 3.1 現状

```python
# tools/demo_allocation_nonconcave.py
true_optimum = 103_881_758.0   # 設計書 §2.3 の手計算値。実行時には計算していない
```

この値がハードコードである限り、`structural_optimality_gap`（= `P_opt − P_greedy`）は soysauce の `s9_fta_cliff` でしか出せない。他ケースへは1件ずつ手計算が要る。

### 3.2 方式（CLAUDE.md L1798-1816 で大杉さんと確定済み）

利益関数は、cliff の on/off を固定すれば**区間ごとに線形**になる。したがって：

1. cliff を持つ市場の集合を K とする（`preferential_threshold_lot` が非 None の市場）
2. **2^|K| 通り**の「どの市場が特恵関税を発動しているか」の場合分けを列挙する
3. 各ケースで関税率を固定 ⇒ 利益関数は線形・分離可能 ⇒ **メリットオーダー（連続版）が厳密解を与える**
4. **整合性チェック**（後述）を通ったケースだけを候補に残す
5. `true_optimum = max(候補ケースの利益)`

計算量は `2^|K| × O(N log N)`。実務ケースで |K| は高々2〜3なので、実質コストはゼロに近い。

### 3.3 閾値の扱い（**この設計の要**・rev.2 で全面改訂）

**rev.1 の記述は誤りだったため、全面的に差し替える。** rev.1 では「税率を固定して解いてから、結果が仮定と矛盾していないか検査する」としていたが、この方式は**閾値が binding になる解を取り逃す**。

「US が特恵を発動している」ケースの真の最適は、しばしば「**US をちょうど閾値まで積む**」点にある。税率だけ固定して素直に貪欲に解くと、US の順位によっては閾値未満で止まり、そのケースを「仮定と矛盾」として棄却してしまう。本来そのケースで最適だった解が候補から消える。

**正しい方式は、閾値を配分量の上下界として先に制約に持たせることである。**

```
ケース S（S に属する市場が特恵を発動していると仮定）について：

  m ∈ S       : rate  = 特恵税率
                lower = preferential_threshold_lot     ← 下界制約
                upper = demand_qty
  m ∈ K \ S   : rate  = 基本税率
                lower = 0
                upper = min(demand_qty, threshold)     ← 上界制約
  m ∉ K       : rate  = 基本税率, lower = 0, upper = demand_qty
```

こうすると、解いた結果は**構造的に仮定と矛盾し得ない**（`m ∈ S` なら `q[m] ≥ threshold`、`m ∈ K\S` なら `q[m] ≤ threshold` が制約により保証される）。事後の整合性チェックそのものが不要になる。棄却するのは `Σ lower > cap` で実行不可能なケースのみ。

**境界（`q == threshold`）の扱い**: 発動していないケースの上界に閉区間 `threshold` を使ってよい。ちょうど閾値の点は本来「発動する」側に属するが、その点は発動ケースでも評価され、特恵税率のほうが利益が高いため、最大値を取る段階で正しい側が選ばれる。取りこぼしは生じない。

実装仕様は `requests/Phase6-1_RequestLetter_to_CodeKun.md` V1.2 に、この方式で記述してある（Code君はそちらに従って実装済み）。

### 3.4 実装位置と返却フィールド

`wom/allocation/merit_order.py` に新規関数を追加し、`compare_with_grid()` から呼ぶ。

```python
def true_continuous_optimum(blocks, sc, cap, transfer_price_usd) -> dict:
    """cliff の on/off を全列挙し、各ケースを線形問題として厳密に解く。
    整合性チェックを通ったケースの最大値を返す。

    returns:
        {"profit": float,
         "x": {market: ratio},
         "q": {market: qty},
         "active_cliffs": [market, ...],   # 発動している特恵の一覧
         "cases_evaluated": int,
         "cases_feasible": int}
    """
```

`compare_with_grid()` の返却に以下を追加する（**既存フィールドは削除・改名しない**）。

| フィールド | 定義 | 備考 |
|---|---|---|
| `true_optimum` | `true_continuous_optimum()["profit"]` = `P_opt` | 新規 |
| `structural_optimality_gap` | `P_opt − P_greedy` | 新規。**構造由来の取りこぼし** |
| `grid_resolution_error` | `P_opt − P_grid` | 新規。**格子解像度の誤差** |
| `residual_coverage` | `abs(structural_residual) / structural_optimality_gap` | 新規。下界が本体を何%覆っているか |

### 3.5 回帰値（**実装で確定・rev.2 で更新**）

soysauce `s9_fta_cliff` の実測値。**2026-09-11 の実装（Code君）で確定した。**

```
true_optimum              = 103,891,296.0    配分 JP=0 / US=35,176 / EU=16,824
structural_optimality_gap =  10,066,596.0
grid_resolution_error      =     338,496.0
|structural_residual|      =   9,728,100.0   （実装済み・変更なし）
residual_coverage          =       0.966
恒等式: 9,728,100 + 338,496 = 10,066,596
```

**設計書 rev.1 が記載していた手計算値 103,881,758 は誤りだった（記録）。**

rev.1 は真の最適配分を `JP=7 / US=35,168 / EU=16,825` としていたが、これは最適点ではない。単位マージン 2,077.5 の US の需要を 8 lot 残したまま、最もマージンの低い JP（750）に 7 lot 配っており、厳密に劣る。差は1円まで分解できる。

```
US  +8 lot × 2,077.5 = +16,620.0
EU  −1 lot × 1,831.5 =  −1,831.5
JP  −7 lot ×   750.0 =  −5,250.0
                       ──────────
                        +9,538.5     ← 103,891,296.0 − 103,881,757.5
```

**丸め誤差ではなく、手計算側の最適化の誤りである。** 実装がそれを検出した。Request Letter の「手計算値に実装を合わせない」という指示が機能した事例として記録しておく。

ケースA（特恵 未発動）の `35,175 × 1,831.5 + 16,825 × 1,747.5 = 93,824,700.0` は正しく、①メリットオーダーの実測値と厳密一致する（V4.2 で厳密テスト済み）。

`s1_base`（線形）では `structural_optimality_gap = 0`、`residual_coverage` は 0/0 となるため **None を返す**（ゼロ除算を起こさない）。また cliff が無いため `true_optimum == P_greedy == 135,529,822.5` が厳密に成立する。

## 4. ステップ 6-2 — 次元の一般化

### 4.1 何が3次元に固定されているか

**(a) 市場名の定数**

```python
# wom/allocation/grid.py:24
MARKETS: Tuple[str, str, str] = ("JP", "US", "EU")
```

**(b) 単体格子の生成ロジック**（こちらが本丸）

```python
def simplex_grid(delta: float = 0.05) -> List[Tuple[float, float, float]]:
    n = int(round(1.0 / delta))
    pts = []
    for i in range(n + 1):
        for j in range(n + 1 - i):       # ← 二重ループ。次元がコードの形に埋まっている
            pts.append(((n - i - j) / n, i / n, j / n))
    return pts
```

### 4.2 依存箇所の全数（`grep -rn "MARKETS"` 実測）

| 区分 | ファイル | 件数 |
|---|---|---|
| **A系統コア** | `grid.py` / `analytics.py` / `merit_order.py` / `regime_map.py` | 4ファイル |
| **描画・CLI** | `plot_allocation_map.py` / `plot_allocation_merit_regime.py` / `run_allocation_map.py` | 3ファイル |
| **テスト** | `test_allocation_grid.py` / `test_allocation_merit_order.py` / `test_allocation_nonconcave.py` | 3ファイル |
| **無関係（別定義）** | `tools/gen_apparel_global_model.py`（独自の `MARKETS` dict）<br>`tools/proto_terrain2.py`（プロトタイプ、独自定義） | 触らない |

`tools/gen_apparel_global_model.py` と `tools/proto_terrain2.py` は**同名の別変数**を持っているだけで `grid.py` を import していない。**改修対象外**とする（誤って巻き込まないこと）。

### 4.3 改修方針

**(a) `MARKETS` はデータから導出する**

```python
# 廃止しない。後方互換のため既定値として残す。
DEFAULT_MARKETS: Tuple[str, ...] = ("JP", "US", "EU")

def markets_of(blocks: Dict[str, CostBlock]) -> Tuple[str, ...]:
    """CostBlock の辞書から市場の並びを決める。
    順序は決定的でなければならない（格子点の並びが変わると回帰値が壊れる）。
    """
```

**順序の決定則**は明示する。既定は `ga_market_aggregation.csv` の記載順、無い場合は辞書のキー順（Python 3.7+ の挿入順）。**アルファベット順にはしない**——現行の `("JP","US","EU")` がアルファベット順ではないため、既存の回帰値が壊れる。

**実装上の注記（rev.3・実測で確認）**: 上の2つ——「CSV の記載順」と「辞書のキー順」——は**元から同じもの**になる。`derive_cost_blocks()` が `by_market` を `defaultdict` に CSV の行順で積み、その `items()` 順で `result` を組んでいるため、返る dict のキー順が `ga_market_aggregation.csv` の `market_group` 初出順と一致する。

```
CSV 行順             : JP, US/US_W, US/US_E, EU/FR, EU/BE, EU/NL
market_group の初出順 : JP, US, EU
derive_cost_blocks() : list(blocks.keys()) == ['JP', 'US', 'EU']   ← MARKETS と完全一致
```

**したがって `markets_of()` は `tuple(blocks.keys())` の1行でよく、`grid.py` に CSV のファイル I/O を持ち込む必要はない。**

**副作用（rev.3 で追記）**: `markets_of()` 化により、**単位マージンが同値のときの並び順**が「`("JP","US","EU")` 固定」から「`blocks` のキー順」に変わる。影響するのは `analytics.py:33`（`market_ranking()`）・`merit_order.py:85,291`（Merit Order で積む順）・`regime_map.py:119`（レジームのラベル文字列）の3箇所である。soysauce では両者が一致するため**既存の回帰値は1つも変わらない**が、新しいケースで同値が起きたときに「CSV の記載順に従う」ことになる点を、**仕様として docstring に明記する**こと。暗黙にしない。

**(b) `simplex_grid()` を N 次元へ**（**rev.3 で実装方式を確定**）

```python
def simplex_grid(delta: float = 0.05, n_dim: int = 3) -> List[Tuple[float, ...]]:
    """n_dim 次元の単体格子。点数は C(n + n_dim − 1, n_dim − 1)。

    **後方互換の絶対条件**: n_dim=3 のとき、返る 231 点の順序が現行実装と
    1点も違わないこと。地形図の描画順・回帰値がこれに依存している。
    """
```

**実装は再帰で書く。`itertools.combinations_with_replacement` は使えない。**

rev.2 までは「再帰または `itertools.combinations_with_replacement` で実装する」としていたが、231点を実際に照合したところ、**後者は集合は同じで順序が異なる**ことが分かった。上の絶対条件を満たすのは再帰版だけである。

```
現行の二重ループ                          : 231点
itertools.combinations_with_replacement : 231点（集合は同じ、**順序が異なる**）
再帰版                                    : 231点（**値も順序も完全一致**）
```

確定した実装方式:

```python
def simplex_grid(delta: float = 0.05, n_dim: int = 3) -> List[Tuple[float, ...]]:
    if n_dim < 2:
        raise ValueError(f"n_dim must be >= 2, got {n_dim}")
    n = int(round(1.0 / delta))
    pts: List[Tuple[float, ...]] = []
    idx = [0] * (n_dim - 1)

    def rec(k: int, remaining: int) -> None:
        if k == n_dim - 1:
            # 第0成分は残余（現行実装で x_JP が残余であるのと同じ）
            pts.append(tuple([remaining / n] + [v / n for v in idx]))
            return
        for v in range(remaining + 1):
            idx[k] = v
            rec(k + 1, remaining - v)

    rec(0, n)
    return pts
```

`n_dim=3` のとき `idx = [i, j]` で外側ループが `i` 昇順・内側が `j` 昇順、第0成分が `(n − i − j)/n` となり、現行の二重ループと同じ走査になる。**全231点での完全一致を確認済み。**

**座標系の規約**: 現行は `x_JP` が残余（`1 − x_US − x_EU`）で、地図の軸は `X = x_US`, `Y = x_EU` である。N次元化してもこの規約を維持し、**`markets_of(blocks)` の先頭の市場が残余**になる。

**再帰深さ**は `n_dim − 1`（N=21 でも20）なので Python の再帰上限には当たらない。**点数のほうが先に破綻する**（→ (c)）。

いずれにせよ **n_dim=3 での点列一致がテストで担保**されること（§7.2 のテスト8）。

**(c) 爆発の防止（必須）**

`scan_surface()` に上限ガードを入れる。

```python
MAX_GRID_POINTS = 100_000   # N=6（53,130点）は通り、N=7（230,230点）は止まる

# 超過時は計算に入る前に例外を投げ、階層化（6-3）の使用を促す
raise ValueError(
    f"simplex grid would have {n_points:,} points for N={n_dim} at delta={delta}. "
    f"Use hierarchical_simplex() instead (see Phase 6-3)."
)
```

**「走らせたら帰ってこない」を絶対に作らない。** 上限は引数で上書き可能とするが、既定では止める。

**(d) 三角図（`plot_allocation_map.py`）は N=3 専用のまま**

直角三角図は2次元平面への射影なので、N≥4 では原理的に描けない。**N≥4 で呼ばれたら明示的なエラーを返す**（黙って3市場だけ描く、といった挙動は禁止）。N≥4 の地形は 6-3 の階層ドリルダウン経由で見る。

### 4.4 禁足ルールとの関係

`grid.py` は A系統4モジュールの1つであり、Phase 5 で既に1度、明示的なスコープインとして改修している（`evaluate_point()` の数量計算順の入替、Phase 5 設計書 §3.4）。

**本 Phase でも `grid.py` は明示的スコープイン**とする。ただし：

- Planning Engine（`backward_planner.py` / `forward_planner.py` 等の禁足コア6ファイル）には**一切触れない**
- golden 13ケースは**不変**であること（A系統は週次 PSI に接続していないので、そもそも影響し得ない。テストで確認する）

---

## 5. ステップ 6-3 — 階層化単体格子（`hierarchical_simplex`）

### 5.1 考え方

N 市場を木構造にまとめ、**各ノードで3つ以下の子に配分する**。各ノードは3市場以下の単体なので、現行の 231点スキャンがそのまま使える。

```
                 [全社]  ← 231点の三角図（3地域への配分）
                /   |   \
          [地域A] [地域B] [地域C]   ← 各231点（地域内の市場への配分）
           / | \
        m1  m2  m3
```

経営者から見ると、**上位の三角図をクリックすると下位の三角図に降りる**というドリルダウンになる。地域統括ごとの P&L という、実際の企業の意思決定構造とそのまま重なる。

### 5.2 削減効果（実測計算）

各ノード 231点、3分木として：

| 構成 | 市場数 | 三角図の枚数 | 評価点数 | 平坦全数 | 削減比 |
|---|---:|---:|---:|---:|---:|
| 深さ1 | 3 | 1 | 231 | 231 | 1× |
| 深さ2 | 9 | 4 | **924** | 3,108,105 | 3,363× |
| 深さ3 | 21〜27 | 13 | **3,003** | 137,846,528,820 | **4,590万×** |

`oil-global-2027`（21市場）が **1,378億点 → 3,003点**になる。

### 5.3 方式の選択（**レビュー事項 R3**）

階層化には2つの方式がある。

**案A：完全評価型** — 上位の各点について、下位を毎回解き直す。

- 訪問した格子点の上では**厳密**
- コストは乗算的。深さ2・N=9 で `231 × (3 × 231) = 160,083` 点。深さ3では再び破綻する

**案B：逐次確定型** — 上位を先に確定し、その配分のもとで下位へ降りる。

- コストは加算的（上表のとおり）
- ただし**これ自体が貪欲法である**。上位の判断が下位の事情を見ずに決まるため、真の最適を外しうる

**設計案は「案B ＋ 誤差測定」を採る。** 理由：

1. 案Aは結局スケールしない。実在ケース（N=21）に届かない方式を採る意味がない
2. 案Bの誤差は、**ステップ 6-1 で作る `structural_optimality_gap` でそのまま測れる**。階層化は貪欲法の一種なので、Phase 5 で用意した道具がそのまま当たる
3. 誤差が金額で出せるなら、階層化は「近似だから信用できない」ではなく **「誤差を保証した近似」**になる

**Phase 5 は寄り道ではなく、この布石だったことになる。**

### 5.4 グルーピングの原則（**レビュー事項 R1**）

グループ分けが恣意的だと誤差が大きくなる。原則を先に決める。

**非分離性の源は「能力の取り合い」である。** 同じ Mother Plant の能力を奪い合う市場どうしは分離できないが、別工場から供給される市場どうしはほぼ分離できる。したがって：

> **第一原則：市場を「供給元の Mother Plant」でグループ化する。**

`oil-global-2027` は `mother_plant` 8件・`marketing` 21件なので、この原則で自然に8グループ以下に割れる。これは偶然ではなく、企業が地域統括を工場の供給圏で切るのと同じ理由である。

第一原則で割り切れない場合（1市場が複数工場から供給される等）の第二原則は、**通貨圏**（為替感応度が近い市場をまとめる）とする。Regime Map の軸が `fx_usd` である以上、為替で一緒に動く市場は同じ枝にあるべきである。

### 5.5 検証方法（**この Phase の中核**）

階層化の誤差を、**測れる規模で実測する**。

N=6 は平坦全数（53,130点）が現実的に計算でき、かつ階層化（3グループ×2市場 = `231 + 3×21 = 294` 点）も走る。**両方が計算できる唯一の帯域**である。

したがって検証は次の2段構えとする。

**(1) 分割不変性テスト（安価・強力）**

soysauce の3市場を、**需要と単価が完全に同一な双子**へ分割して6市場ケースを合成する（JP → JP-a / JP-b、以下同様。需要は半分ずつ）。

このとき、**6市場の最適利益は3市場の最適利益と一致しなければならない**。分割は情報を増やしていないからである。

```
3市場 s1_base の最適利益  ==  6市場（双子分割）の最適利益     （許容差 ±1 JPY）
3市場 s1_base の最適利益  ==  6市場を階層化した最適利益        （同上）
```

Phase 4 で `switching_points()` の 117円/119円 を Regime Map が再現することを最重要テストに置いたのと同じ考え方——**新機能が既存の検証済み結果を再現する**ことで、新しい数学を持ち込んでいないことを示す。

**(2) 誤差の実測（非対称な6市場）**

双子ではなく、単価・需要が異なる6市場の合成ケースを作り、

```
平坦全数（53,130点）の最良点   =  P_flat
階層化（294点）の最良点        =  P_hier
階層化の誤差                   =  P_flat − P_hier     ← 金額で出る
```

さらに 6-1 の `true_continuous_optimum()` を当てて、`P_opt − P_hier`（階層化の構造由来の取りこぼし）まで出す。

**この2つの数字が、N=21 で平坦全数が計算できないぶんを補う。** 外挿ではなく、「N=6 では誤差がこれだけだった」という実測と、`structural_residual` という下界の両方で語れる。

### 5.6 実装位置

```
wom/allocation/hierarchical_simplex.py   ← 新規
    build_hierarchy()      市場をグループ木に組む（5.4 の原則を実装）
    scan_hierarchical()    木を降りながらスキャン（案B）
    hierarchy_gap()        平坦全数との差を測る（N が小さいときのみ）
```

`grid.py` の `scan_surface()` は**置き換えない**。N≤6 では従来どおり平坦全数を使う（誤差ゼロ）。階層化は N≥7 の手段であり、かつ N=6 では**校正用に両方走らせる**。

---

## 6. 共通仕様

### 6.1 技術制約（Phase 3/4/5 を継承）

- matplotlib のみ（plotly / bokeh / dash / streamlit / seaborn は不採用。スタンドアロン Windows PC 運用のため）
- 新規依存パッケージなし（`itertools` / `math` は標準ライブラリ）
- `matplotlib.use("Agg")` は `pyplot` import より前
- 図中のテキストは**すべて英語**（日本語フォント未導入環境での豆腐化防止）
- 各描画関数は生成した出力パスを返す。`plt.close(fig)` を必ず呼ぶ
- **乱数を使わない**。すべて決定的
- 禁足コア（`backward_planner.py` 等6ファイル）には一切触れない

### 6.2 ファイル配置

| 区分 | パス | 扱い |
|---|---|---|
| 新規 | `wom/allocation/hierarchical_simplex.py` | 6-3 |
| 改修（明示スコープイン） | `wom/allocation/grid.py` | 6-2 |
| 改修（追加のみ） | `wom/allocation/merit_order.py` | 6-1（`true_continuous_optimum()` 追加、`compare_with_grid()` にフィールド追加） |
| 改修（`MARKETS` 参照の差し替え） | `analytics.py` / `regime_map.py` / 描画3ツール | 6-2 |
| 新規データ | `data/sample/soysauce-jpy-2027-alloc/` の6市場合成 | 5.5 |
| 無変更 | B系統（`wom/visualization/*`）・禁足コア・`transmission.py` / `cost_block.py` | — |

### 6.3 後方互換の絶対条件

以下が1つでも崩れたら実装は不合格とする。

1. `simplex_grid(delta=0.05)` を引数なしで呼んだとき、**231点が現行と同一順序**で返る
2. soysauce `s1_base` の回帰値（最大利益・尾根・台地・切替点 117円/119円・FXB）が**すべて不変**
3. Phase 4 の `s1_base` 分解（`gap_amt = 3,396,750` / `expected_gap = 3,396,750` / `structural_residual = 0`）が**不変**
4. Phase 5 の `s9_fta_cliff` 分解が**不変**
5. golden 13ケースが**不変**
6. 既存370件が**全PASS**

---

## 7. テスト計画

### 7.1 ステップ 6-1（真の最適、7件）

1. `test_true_optimum_s9_matches_design_value` — `s9_fta_cliff` で `103,891,296.0`（±1 JPY・実装で確定した回帰値）
2. `test_true_optimum_case_a_matches_greedy` — 特恵未発動ケースが `93,824,700.0` と厳密一致
3. `test_true_optimum_rejects_infeasible_case` — 閾値を満たさない仮定のケースが棄却されること（**最重要**）
4. `test_structural_optimality_gap_identity` — `|structural_residual| + grid_resolution_error == structural_optimality_gap`
5. `test_residual_coverage_s9` — `0.967`（±0.001）
6. `test_linear_case_gap_is_zero` — `s1_base` で `structural_optimality_gap == 0`
7. `test_residual_coverage_none_when_gap_zero` — 線形ケースで `residual_coverage is None`（ゼロ除算しない）

### 7.2 ステップ 6-2（次元の一般化、8件）

8. `test_simplex_grid_3d_order_unchanged` — 231点の**順序まで**現行と一致（**最重要**）
9. `test_simplex_grid_point_counts` — N=2/3/4/5/6 で `C(20+N−1, N−1)` と一致（21 / 231 / 1,771 / 10,626 / 53,130）
10. `test_simplex_grid_sums_to_one` — 全点で成分和が 1.0（浮動小数の許容差込み）
11. `test_markets_order_is_deterministic` — 同じ入力から同じ並びが返る
12. `test_markets_order_not_alphabetical` — 既定が `("JP","US","EU")` のままであること
13. `test_scan_surface_guard_raises` — N=7 で `MAX_GRID_POINTS` 超過の例外が**計算に入る前に**投がること
14. `test_plot_allocation_map_rejects_n4` — 三角図が N≥4 で明示エラー
15. `test_regression_s1_base_unchanged` — soysauce の全回帰値が不変

### 7.3 ステップ 6-3（階層化、6件）

16. `test_hierarchy_split_invariance` — 双子分割した6市場の最適利益が3市場と一致（**最重要**）
17. `test_hierarchy_split_invariance_hierarchical` — 同上を階層化経由で
18. `test_hierarchy_gap_measured` — 非対称6市場で `P_flat − P_hier` が算出できること
19. `test_hierarchy_grouping_by_mother_plant` — グルーピングが 5.4 の第一原則どおりに構成される
20. `test_hierarchy_point_count` — 深さ2・9市場で 924点、深さ3で 3,003点
21. `test_hierarchy_depth1_equals_flat` — 深さ1（3市場）で平坦スキャンと完全一致

### 7.4 合計

新規 **21件**。既存370件と合わせて **391件全PASS** が完了条件。

---

## 8. 成功基準

- [x] `true_optimum` が実行時に計算され、`s9_fta_cliff` で `103,891,296.0`（±1 JPY）を返す
- [ ] 整合性チェックが機能し、実現不可能なケースを棄却する
- [ ] `simplex_grid(0.05)` の 231点が**順序まで**不変
- [ ] N=6（53,130点）が現実的な時間で走り、N=7 は**計算前に**止まる
- [ ] 双子分割した6市場の最適利益が3市場と一致する
- [ ] 非対称6市場で、階層化の誤差が**金額で**出る
- [ ] `oil-global-2027`（21市場）で階層化スキャンが 3,003点で完走する
- [ ] soysauce の全回帰値・Phase 4/5 の全分解値・golden 13ケースが不変
- [ ] 391件全PASS

---

## 9. レビュー事項（大杉さんへ）

**R1. グルーピングの第一原則を「供給元 Mother Plant」でよいか。**
非分離性の源が能力の取り合いである以上これが理屈に合うと考えていますが、実務では「地域統括の組織単位」や「通貨圏」で切るほうが経営者に説明しやすい可能性があります。**説明可能性と誤差の小ささのどちらを優先するか**、という選択です。

**R2. 6市場の合成ケースの作り方。**
5.5(1) の双子分割は V&V 用なので迷いがありません。5.5(2) の非対称6市場をどう作るか——soysauce の3市場を非対称に割るか、`oil-global-2027` から6市場を抜き出すか——をご指示ください。前者は既存の回帰値との連続性があり、後者は実在ケースに近い形になります。

**R3. 案B（逐次確定型）＋誤差測定でよいか。**
案A（完全評価型）は格子上では厳密ですが、深さ3で再び破綻します。近似を受け入れて誤差を測る方針を採りたいと考えていますが、「近似は使わない」という判断もありえます。

**R4. N≥4 で三角図が描けないとき、CLI と将来の GUI はどう振る舞うべきか。**
本設計では明示エラーとしました。代替として「上位3グループの三角図を既定で出す」という挙動もありえますが、**利用者が3市場の図を全体だと誤解する**リスクがあるため採りませんでした。

---

## 10. Phase 7 への引き継ぎ

- パレート＋平行座標の**配分版**（N市場化の完了後に着手すべき。B系統版は Phase 3 で実装済み）
- `ev-thailand-2026` の `ga_*.csv` 作成と、実ケースでの `structural_optimality_gap` 測定
- 目的空間の階層化（`hierarchical_triangulation`、dev guide §2.4）
- Management Cockpit GUI への階層ドリルダウンの配線
- `oil-global-2027` の Regime Map（21市場でも軸は2次元のままなので、N市場化の恩恵をそのまま受ける）

---

## 改版履歴

- 2026-09-11 rev.3 — **ステップ 6-2 の Request Letter 執筆時の実測**（`requests/Phase6-2_RequestLetter_to_CodeKun.md`、commit `1ecf769`）を受けた更新。§4.3(b) の実装方式を**再帰に確定**：rev.2 までの「再帰または `itertools.combinations_with_replacement`」という記述は誤りで、**後者は231点の集合は同じだが順序が異なる**ため、後方互換の絶対条件（231点の順序不変）を満たさない。確定した再帰実装を全文で記載し、現行の二重ループと全231点で一致することを確認した。§4.3(a) に2点追記：(1) 「CSV の記載順」と「辞書のキー順」は `derive_cost_blocks()` の構造上**元から同じもの**であり、`markets_of()` は `tuple(blocks.keys())` の1行でよい（`grid.py` に CSV の I/O を持ち込まない）、(2) `markets_of()` 化の**副作用として単位マージン同値時の tie-break が変わる**（soysauce では回帰値不変だが、仕様として docstring に明記する）
- 2026-09-11 rev.2 — **ステップ 6-1 実装完了**（377件全PASS）を受けた更新。§3.3 を全面改訂：rev.1 の「解いてから整合性チェック」方式は**閾値が binding な解を取り逃す**ため誤りで、閾値を**上下界の制約として先に持たせる**方式に差し替えた（実装仕様は Request Letter V1.2）。§3.5 の回帰値を実測値に更新：`true_optimum = 103,891,296.0`（配分 JP=0/US=35,176/EU=16,824）、`structural_optimality_gap = 10,066,596`、`grid_resolution_error = 338,496`、`residual_coverage = 0.966`。**rev.1 の手計算値 103,881,758 は丸め誤差ではなく最適化の誤りだった**ことを、差 +9,538.5 の1円までの分解とともに記録
- 2026-09-09 rev.1 — 初版。大杉さんからの問い「直角三角図のN階層化の優先度は低いのか」を受けて、Phase 6 バックログ5項目の整理を見直した。**階層化は4番目の可視化手法ではなく N市場化そのものの実現手段である**（`oil-global-2027` の21市場は平坦格子で1,378億点、階層化で3,003点）、および**4枚の地図のうち地形＝ロバストネスを担うのは第1の地図だけである**という2点から、優先度を HIGH に引き上げ、`true_optimum` 実計算・次元の一般化・階層化単体格子を「N市場化」という1つの Phase の3ステップとして再構成した。`true_optimum` の方式は CLAUDE.md L1798-1816 で確定済みのものを踏襲し、**整合性チェック**を設計の要として明記。用語の落とし穴（`hierarchical_triangulation` が配分空間と目的空間の両方を指している）を §2 で解消し、配分空間側を `hierarchical_simplex` に確定。
