# Phase 6-2 実装 Request Letter — 次元の一般化（3市場固定 → N市場）

**宛先**: Code君
**作成日**: 2026年9月11日
**担当**: Claude君（設計・仕様）→ 大杉さん（レビュー）→ Code君（実装）
**優先度**: HIGH（Phase 6-3「階層化単体格子」の前提）
**ブランチ**: `wom-v1r4m0`
**設計正典**: `requests/Phase6_DesignMD_NMarketHierarchy.md` §4（本書は §4 を実装仕様まで落としたもの）
**前提**: Phase 6-1 完了（`64e7757` + テスト締め `8a8eb1f`、377件全PASS）

---

## 概要

A系統（`wom/allocation/`）は現在、市場が **3つに固定**されている。固定している実体は2つだけである。

```python
# wom/allocation/grid.py:24
MARKETS: Tuple[str, str, str] = ("JP", "US", "EU")      # (a) 市場名の定数

# wom/allocation/grid.py:29-36
def simplex_grid(delta: float = 0.05) -> List[Tuple[float, float, float]]:
    n = int(round(1.0 / delta))
    pts = []
    for i in range(n + 1):
        for j in range(n + 1 - i):     # ← (b) 二重ループ。次元がコードの形に埋まっている
            pts.append(((n - i - j) / n, i / n, j / n))
    return pts
```

本 Phase でこの2つを外す。**`oil-global-2027` は marketing ノードが21ある。** 3市場固定のままでは、A系統は soysauce 以外の実ケースに接続できない。

### 先に朗報 — 依存は見た目ほど深くない

`grep -rn "MARKETS"` の結果（A系統4モジュール＋tools 3本＋テスト3本、計37箇所）を1件ずつ確認した。そのうち **36箇所は `for m in MARKETS` 形の「市場名を順に舐める」用法**であり、次元そのものには依存していない。位置で `x` ベクトルと突き合わせているのは **たった2箇所**である。

```python
wom/allocation/grid.py:51                 q = {m: min(xi*cap, ...) for m, xi in zip(MARKETS, x)}
tests/test_allocation_nonconcave.py:96    q = {m: min(xi*cap, ...) for m, xi in zip(MARKETS, x)}
```

つまり本 Phase の作業の実体は「**`MARKETS` という定数参照を `blocks` から導出した並びに差し替える**」という機械的な置換であり、アルゴリズムの作り直しではない。難所は `simplex_grid()` のN次元化と、**231点の順序を1点も変えないこと**の2点に集中している。

### 対象ファイル

| ファイル | 扱い |
|---|---|
| `wom/allocation/grid.py` | **明示的スコープイン**。`DEFAULT_MARKETS` / `markets_of()` 追加、`simplex_grid()` のN次元化、上限ガード |
| `wom/allocation/analytics.py` | `MARKETS` 参照を `markets_of(blocks)` に差し替え（3箇所） |
| `wom/allocation/merit_order.py` | 同上（13箇所）。`_validate` 系は引数追加 |
| `wom/allocation/regime_map.py` | 同上（5箇所）。`_validate_axis_name()` に `markets` 引数を追加 |
| `tools/run_allocation_map.py` | 同上（3箇所）。1箇所は CSV の行から導出に変更 |
| `tools/plot_allocation_map.py` | **N≥4 で明示エラー**（三角図は2次元射影なので原理的に描けない） |
| `tools/plot_allocation_merit_regime.py` | 未使用 import の整理のみ |
| `tests/test_allocation_*.py` | テスト追記（既存は原則不変。V4.8 参照） |
| 上記以外 | **無変更**（`transmission.py` / `cost_block.py` / B系統 / 禁足コア6ファイル） |

**`tools/gen_apparel_global_model.py` と `tools/proto_terrain2.py` は改修対象外。** 同名の `MARKETS` を持っているが `grid.py` を import していない**別変数**である。誤って巻き込まないこと。

---

## ⚠️ 実装前に必ず読むこと — 絶対制約

Phase 3/4/5/6-1 から継承。

- **C1**: matplotlib のみ（plotly 等の Web 系 GUI は情報セキュリティ上ありえない）
- **C2**: 新規依存パッケージなし（標準ライブラリ `math.comb` のみ追加で足りる）
- **C3**: 図の保存は `output/` 配下。**C4**: 図中テキストは英語
- **C5**: 返却は Dict。**C6**: 禁足コア6ファイル（`backward_planner.py` / `forward_planner.py` / `plan_copy.py` / `plan_node.py` / `sc_tree.py` / `push_pull.py`）に一切触れない
- **C7**: **乱数を使わない。** 列挙順・返却順は決定的であること
- **C8（本 Phase 固有・最重要）**: **`simplex_grid(0.05)` が返す231点は、値も順序も現行と1点も変わらないこと。** 地形図の描画順・Phase 4/5 の全回帰値がこれに依存している
- **C9（本 Phase 固有）**: **「走らせたら帰ってこない」を作らない。** 格子点数が上限を超える場合は、**点の生成に入る前に**例外を投げる

---

## V1: 市場の並びをデータから導出する

### V1.1 `DEFAULT_MARKETS` と `markets_of()`

`wom/allocation/grid.py` に追加する。

```python
# 既定の市場（soysauce-jpy-2027-alloc の並び）。blocks が無い呼び出し元のための既定値。
DEFAULT_MARKETS: Tuple[str, ...] = ("JP", "US", "EU")

# 後方互換のため残す。新規コードでは markets_of(blocks) を使うこと。
MARKETS: Tuple[str, ...] = DEFAULT_MARKETS


def markets_of(blocks: Dict[str, CostBlock]) -> Tuple[str, ...]:
    """CostBlock の辞書から市場の並びを決める。

    順序は決定的でなければならない（格子点の並びが変わると回帰値が壊れる）。
    dict のキー順＝挿入順（Python 3.7+ の言語仕様）をそのまま採用する。
    """
    return tuple(blocks.keys())
```

### V1.2 「dict のキー順でよい」根拠 — 確認済み

設計書 §4.3(a) は「既定は `ga_market_aggregation.csv` の記載順、無い場合は辞書のキー順」と書いている。**実装では CSV を読み直す必要はない。`derive_cost_blocks()` が既に CSV の行順を dict の挿入順として保存しているため、両者は同じものになる。**

確認した経路（`wom/allocation/cost_block.py:116-121`）:

```python
by_market: Dict[str, List[dict]] = defaultdict(list)
for r in agg:                              # ← CSV の行順で走査
    by_market[r["market_group"]].append(r) # ← defaultdict も挿入順を保つ

result: Dict[str, CostBlock] = {}
for market, regs in by_market.items():     # ← 初出順で result に入る
    ...
```

実測（`data/sample/soysauce-jpy-2027-alloc/ga_market_aggregation.csv`）:

```
CSV 行順            : JP, US/US_W, US/US_E, EU/FR, EU/BE, EU/NL
market_group の初出順: JP, US, EU
derive_cost_blocks() : list(blocks.keys()) == ['JP', 'US', 'EU']   ← MARKETS と完全一致
```

**したがって `markets_of()` の実装は `tuple(blocks.keys())` の1行でよい。** CSV パスを引数に取る必要はなく、取るべきでもない（`grid.py` にファイル I/O を持ち込まない）。

### V1.3 やってはいけないこと

- **`sorted(blocks.keys())` にしない。** アルファベット順は `('EU','JP','US')` となり、現行の `('JP','US','EU')` と異なる。**Phase 4/5 の全回帰値が壊れる。** 設計書 §4.3(a) の明示事項
- **`set` を経由しない。** 順序が保証されない（C7 違反）

### V1.4 副作用として変わること — 同順位の tie-break（申し送り事項）

`markets_of()` 化により、**単位マージンが同値のときの並び順**が「`('JP','US','EU')` 固定」から「`blocks` のキー順」に変わる。影響するのは以下3箇所である。

| 箇所 | 内容 |
|---|---|
| `analytics.py:33` | `market_ranking()` の同値時の並び |
| `merit_order.py:85,291` | Merit Order で積む順序の同値時 |
| `regime_map.py:119` | レジームのラベル文字列（`"US>EU>JP"` 等）の同値時 |

**soysauce では `markets_of(blocks) == ('JP','US','EU') == MARKETS` なので、既存の回帰値は1つも変わらない。** ただし新しいケースで同値が起きたときの挙動が「CSV の記載順に従う」ことになる点を、docstring に明記しておくこと。これは**仕様として妥当**（CSV の並びは大杉さんが意図して書いたもの）だが、暗黙にしない。

---

## V2: `simplex_grid()` の N 次元化

### V2.1 シグネチャ

```python
def simplex_grid(delta: float = 0.05, n_dim: int = 3) -> List[Tuple[float, ...]]:
    """n_dim 次元の単体格子。点数は C(n + n_dim − 1, n_dim − 1)（n = 1/delta）。

    後方互換の絶対条件: n_dim=3 のとき、返る231点の**値と順序**が現行実装と
    1点も違わないこと（C8）。地形図の描画順・Phase 4/5 の全回帰値が依存する。
    """
```

`n_dim` は**キーワードでもポジションでも渡せる第2引数**とし、既定を 3 とする。既存呼び出し `simplex_grid(0.05)` はそのまま通ること。

### V2.2 実装は再帰で書くこと（`combinations_with_replacement` は不可）

設計書 §4.3(b) は「再帰または `itertools.combinations_with_replacement` で実装する」と書いているが、**検証した結果、後者では順序が一致しない。** 点の集合は同じだが並びが違う。

```
現行の二重ループ                    : 231点
itertools.combinations_with_replacement: 231点（集合は同じ、**順序が異なる**）
再帰版                               : 231点（**値も順序も完全一致**）
```

したがって **C8 を満たすのは再帰版だけ**である。設計書のこの記述は**本 Request Letter で上書きする**。

推奨実装:

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

**なぜこれが現行と一致するか**: `n_dim=3` のとき `idx=[i,j]` で、外側ループが `i` 昇順、内側が `j` 昇順、第0成分が `(n−i−j)/n`。現行の二重ループと同じ走査である。実際に `simplex_grid(0.05) == 現行実装の出力` を全231点で照合し、**完全一致を確認済み**。

**再帰深さ**は `n_dim − 1`（N=21 でも20）なので、Python の再帰上限には当たらない。点数のほうが先に破綻する（→ V3）。

### V2.3 第0成分が「残余」であることの意味

現行の座標系では `x_JP` が残余（`1 − x_US − x_EU`）で、地図の軸は `X = x_US`, `Y = x_EU` である。N次元化しても**この規約は維持する**：`markets_of(blocks)` の**先頭の市場が残余**になる。soysauce では先頭が `JP` なので、現行と同じ。docstring に明記すること。

---

## V3: 爆発の防止（C9）

### V3.1 定数とガード

`wom/allocation/grid.py`:

```python
from math import comb

MAX_GRID_POINTS = 100_000   # N=6（53,130点）は通り、N=7（230,230点）は止まる


def grid_point_count(delta: float = 0.05, n_dim: int = 3) -> int:
    """格子点数 C(n + n_dim − 1, n_dim − 1) を、点を生成せずに返す。"""
    n = int(round(1.0 / delta))
    return comb(n + n_dim - 1, n_dim - 1)
```

### V3.2 ガードを入れる場所

**`scan_surface()` に入れる**（設計書 §4.3(c)）。`simplex_grid()` 自体には入れない——格子の生成だけなら安いし、Phase 6-3 の階層化が内部で高次元の小さな格子を作る可能性があるため。

```python
def scan_surface(blocks, transfer_price_usd, sc, cap_wk, weeks=WEEKS,
                 delta: float = 0.05, max_points: int = MAX_GRID_POINTS) -> List[dict]:
    markets = markets_of(blocks)
    n_points = grid_point_count(delta, len(markets))
    if n_points > max_points:
        raise ValueError(
            f"simplex grid would have {n_points:,} points for N={len(markets)} "
            f"at delta={delta} (limit {max_points:,}). "
            f"Use hierarchical_simplex() instead (see Phase 6-3)."
        )
    return [evaluate_point(x, blocks, transfer_price_usd, sc, cap_wk, weeks)
            for x in simplex_grid(delta, len(markets))]
```

**必ず `simplex_grid()` を呼ぶ前に判定すること。** 「生成してから len を見る」実装は C9 違反である（N=21 で1,378億点を生成しようとして帰ってこない）。

`max_points` は引数で上書き可能とするが、**既定では止める**。

### V3.3 参考 — δ=0.05 での点数

| N | 点数 | 判定 |
|---:|---:|---|
| 2 | 21 | 通る |
| 3 | 231 | 通る（現行） |
| 4 | 1,771 | 通る |
| 5 | 10,626 | 通る |
| 6 | 53,130 | 通る |
| 7 | 230,230 | **止まる** |
| 10 | 10,015,005 | 止まる |
| 21 | 137,846,528,820（約1,378億） | 止まる ← `oil-global-2027` |

---

## V4: `grid.py` 内の `MARKETS` 参照の差し替え

`evaluate_point()` と `demand_ceilings()` は `blocks` を受け取っているので、ローカルで導出する。

```python
def evaluate_point(x, blocks, transfer_price_usd, sc, cap_wk, weeks=WEEKS) -> dict:
    markets = markets_of(blocks)
    cap = cap_wk * weeks
    q = {m: min(xi * cap, blocks[m].demand_qty) for m, xi in zip(markets, x)}
    ue = {m: unit_pnl_at_quantity(blocks[m], sc, q[m], transfer_price_usd) for m in markets}
    ...
```

**`zip(markets, x)` の長さ不一致を黙って捨てないこと。** `zip` は短いほうに合わせて静かに切り捨てるため、`x` の次元と市場数がずれていても例外が出ず、**利益が過小に計算される**。先頭で明示的に検査する:

```python
    if len(x) != len(markets):
        raise ValueError(
            f"x has {len(x)} components but blocks has {len(markets)} markets "
            f"{markets}. The order of x must match markets_of(blocks)."
        )
```

`demand_ceilings()` も同様に `markets_of(blocks)` を使う。`best_point()` は市場に依存しないので**無変更**。

---

## V5: 呼び出し元の差し替え

### V5.1 `wom/allocation/analytics.py`（3箇所）

| 行 | 現行 | 変更後 |
|---|---|---|
| 23 | `from ...grid import MARKETS, evaluate_point, scan_surface` | `MARKETS` → `markets_of` |
| 33 | `tuple(sorted(MARKETS, key=...))` | `tuple(sorted(markets_of(blocks), key=...))` |
| 53 | `for m in MARKETS` | `for m in markets_of(blocks)` |

`switching_points()` は内部で `market_ranking()` を呼んでいるので、L53 だけ直せばよい。

### V5.2 `wom/allocation/merit_order.py`（13箇所）

いずれも `blocks` がスコープ内にあるので、**関数の先頭で `markets = markets_of(blocks)` を一度だけ求め**、以降の `MARKETS` を `markets` に置換する。

| 関数 | 行 |
|---|---|
| `build_allocation_merit_order()` | 84, 85, 86, 89 |
| `true_continuous_optimum()` | 228, 254, 271, 282, 291, 305, 308, 320, 323 |

**注意**: L215 と L227 はコメント/docstring 内の「MARKETS 順」という記述である。**文言も「`markets_of(blocks)` 順」に直すこと**（コメントだけ古い、を作らない）。

**`true_continuous_optimum()` の `len(K) > 12` ガードは無変更。** cliff を持つ市場の数の上限であって市場数の上限ではないので、N市場化とは独立である。

### V5.3 `wom/allocation/regime_map.py`（5箇所）

`_validate_axis_name()` だけが `blocks` を持っていない。**引数を追加する。**

```python
def _validate_axis_name(axis_name: str, markets: Tuple[str, ...]) -> None:
    ...
    if market in markets:
        return
    raise ValueError(
        f"Unknown market in axis {axis_name!r}: {market!r} (must be one of {markets})"
    )
```

呼び出し元（`scan_regime_grid()` の L93-94）で:

```python
    markets = markets_of(blocks)
    _validate_axis_name(axis_x, markets)
    _validate_axis_name(axis_y, markets)
```

L118 / L119 / L129 は `markets` に置換。**L119 のレジームラベル（`">".join(order)`）は N 市場でそのまま動く**（`"JP>US>EU"` が `"A>B>C>D>E>F"` になるだけ）。ただし N が大きいとラベルが長大になり凡例が破綻するので、**申し送り**に回す（本 Phase では対応不要、V7 参照）。

### V5.4 `tools/run_allocation_map.py`（3箇所）

| 行 | 文脈 | 変更 |
|---|---|---|
| 90 | `load_scenarios()` 内。**`blocks` が無い** | CSV の行から導出する（下記） |
| 112 | `_blocks_for()` 内。`base_blocks` がある | `for m in markets_of(base_blocks)` |
| 242 | `ceil` が既に市場をキーに持つ | `for m in ceil` |

L90 の `time_series` 判定は、シナリオ CSV の行 `rs` を舐めている。`MARKETS` ではなく**行に現れた市場**を使う:

```python
        scen_markets = tuple(dict.fromkeys(r["market"] for r in rs))   # 初出順・重複除去
        time_series = any(
            len({(float(r["fx_spot_jpy"]), float(r["material_price_usd"]), float(r["tariff_rate"]))
                 for r in rs if r["market"] == m}) > 1
            for m in scen_markets)
```

`dict.fromkeys` を使うのは順序を保つため（`set` は C7 違反）。

### V5.5 `tools/plot_allocation_merit_regime.py`（1箇所）

L44 の `MARKETS` は **import しているだけで使っていない**。import から外すだけでよい。

---

## V6: 三角図は N=3 専用（設計書 §4.3(d)）

直角三角図は単体を2次元平面に射影したものなので、**N≥4 では原理的に描けない**。「黙って上位3市場だけ描く」という挙動は**禁止**する——利用者が3市場の図を全体だと誤解するリスクがあるため（設計書 §9 R4 で大杉さん確認済み）。

`tools/plot_allocation_map.py` に検査関数を置く:

```python
def _require_three_markets(blocks) -> None:
    """三角図は単体の2次元射影なので N=3 専用。N≥4 は明示エラーで止める。"""
    markets = markets_of(blocks)
    if len(markets) != 3:
        raise ValueError(
            f"Triangle plot supports exactly 3 markets, got {len(markets)}: {markets}. "
            f"For N>=4, use the hierarchical drill-down (Phase 6-3)."
        )
```

**呼び出す場所**: `_draw_terrain()` の先頭。`plot_single` / `plot_terrain_only` / `plot_each_scenario` / `plot_tile` はすべてここを通るため、1箇所で全経路をふさげる。`plot_layers()` は棒グラフで三角図ではないが、**`_draw_layers_bar()` は N 市場でそのまま動く**ので**ガードを入れない**（入れると N市場化の意味がなくなる）。

---

## V7: テスト仕様（新規8件）

`tests/test_allocation_grid.py` に追記する（V4.7 のみ `tests/test_allocation_plot.py`）。設計書 §7.2 に対応。

### V7.1 `test_simplex_grid_3d_order_unchanged`（**最重要**）

231点が**順序まで**現行と一致すること。参照列は**テスト内に現行ロジックを書き下ろして生成**する（別ファイルへの golden 化は不要）。

```python
def _legacy_simplex_grid(delta=0.05):
    """Phase 6-2 以前の実装（順序の参照用・改変禁止）。"""
    n = int(round(1.0 / delta))
    return [((n - i - j) / n, i / n, j / n)
            for i in range(n + 1) for j in range(n + 1 - i)]


def test_simplex_grid_3d_order_unchanged():
    assert simplex_grid(0.05) == _legacy_simplex_grid(0.05)
    assert simplex_grid(0.05, 3) == _legacy_simplex_grid(0.05)
    assert simplex_grid(0.05, n_dim=3) == _legacy_simplex_grid(0.05)
```

**`==` で厳密比較すること**（`set` 比較や `sorted()` 比較にしない。それでは順序が検証できない）。

### V7.2 `test_simplex_grid_point_counts`

| n_dim | 期待点数 |
|---:|---:|
| 2 | 21 |
| 3 | 231 |
| 4 | 1,771 |
| 5 | 10,626 |
| 6 | 53,130 |

`len(simplex_grid(0.05, N)) == grid_point_count(0.05, N) == 期待値` の3者一致を見ること。

### V7.3 `test_simplex_grid_sums_to_one`

`n_dim = 2..6` の全点で成分和が 1.0（`abs=1e-9`）、かつ全成分が `>= -1e-12`。

### V7.4 `test_markets_order_is_deterministic`

同じ `blocks` から `markets_of()` を10回呼んで全て同一。`derive_cost_blocks()` を2回呼んでも同じ並びが返ること。

### V7.5 `test_markets_order_not_alphabetical`

```python
def test_markets_order_not_alphabetical():
    assert markets_of(BLOCKS) == ("JP", "US", "EU")
    assert markets_of(BLOCKS) != tuple(sorted(markets_of(BLOCKS)))   # ('EU','JP','US')
    assert DEFAULT_MARKETS == ("JP", "US", "EU")
    assert MARKETS == DEFAULT_MARKETS                                 # 後方互換
```

### V7.6 `test_scan_surface_guard_raises`

N=7 のダミー blocks を作り、`scan_surface()` が **`simplex_grid()` を呼ぶ前に** `ValueError` を投げること。

```python
def _dummy_blocks(n: int):
    return {f"M{i}": CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                               price_local=200, ccy="JPY", demand_qty=100)
            for i in range(n)}


def test_scan_surface_guard_raises():
    with pytest.raises(ValueError, match="230,230"):
        scan_surface(_dummy_blocks(7), 0.0, Scenario(fx_usd=150.0, material_usd=6.0), cap_wk=100)

    # N=6 は通る（53,130点）
    surf = scan_surface(_dummy_blocks(6), 0.0, Scenario(fx_usd=150.0, material_usd=6.0), cap_wk=100)
    assert len(surf) == 53_130

    # max_points で上書きすれば N=7 も通せる（既定で止まるだけであること）
    surf7 = scan_surface(_dummy_blocks(7), 0.0, Scenario(fx_usd=150.0, material_usd=6.0),
                         cap_wk=100, max_points=300_000)
    assert len(surf7) == 230_230
```

**N=6 の 53,130点と N=7 の 230,230点は実際に評価が走る**ので、このテストは数秒〜十数秒かかる。それが**許容時間内であること自体が確認事項**である（C9 の「現実的な時間で走る」）。所要時間が1分を超えるようなら報告すること。

### V7.7 `test_plot_allocation_map_rejects_n4`

`tests/test_allocation_plot.py` に追記。`_require_three_markets(_dummy_blocks(4))` が `ValueError` を投げ、`_require_three_markets(BLOCKS)` は投げないこと。

### V7.8 `test_regression_s1_base_unchanged`

**既存の回帰が1つも動いていないことの総点検。** 新しく書くのではなく、以下がすべて PASS のままであることを確認する（テストファイルの追加は不要）。

- `tests/test_allocation_grid.py` の付録A回帰5件（`148.5 / 132.1 / 207.2 / 176.7 / 85.8`）
- `tests/test_allocation_analytics.py` の切替点 `117円 / 119円`
- `tests/test_allocation_merit_order.py` の `135,529,822.5`
- `tests/test_allocation_nonconcave.py` の `93,824,700.0` / `103,891,296.0` / `103,552,800.0` / `9,728,100.0` / `0.966`
- `tests/test_golden.py` の golden 13ケース

### V7.9 既存テストの扱い

既存テストは**原則として書き換えない**。ただし `tests/test_allocation_nonconcave.py:96` は `zip(MARKETS, x)` を使っているため、`MARKETS` が `DEFAULT_MARKETS` のエイリアスとして残る限り**そのまま動く**。**書き換えなくてよい**。

`tests/test_allocation_merit_order.py:70` は blocks を `JP/US/EU` の順、`tests/test_allocation_nonconcave.py:151` は **`JP/EU/US` の順**で構築している。後者は `markets_of()` 化で反復順が変わるが、当該テストは `next(b for b in mo["blocks"] if b["market"] == "US")` と**名前で引いて**おり、かつ JP/EU は両方とも負マージンで `excluded` に落ちるため、**結果は変わらない**。確認のうえ、変わらないことを報告すること。

---

## 成功基準

- [ ] `simplex_grid(0.05)` の231点が**値も順序も**現行と完全一致（`==` で照合）
- [ ] `simplex_grid(0.05, N)` の点数が N=2/3/4/5/6 で 21 / 231 / 1,771 / 10,626 / 53,130
- [ ] N=6（53,130点）が現実的な時間で走り、N=7 は**点の生成前に**止まる
- [ ] `markets_of(blocks)` が soysauce で `("JP","US","EU")` を返す（アルファベット順にならない）
- [ ] 三角図が N≥4 で明示エラー。N=3 では従来どおり描ける
- [ ] `MARKETS` の import が引き続き通る（後方互換）
- [ ] A系統の全回帰値（付録A 5件・切替点・Phase 4/5 の全分解値）が不変
- [ ] golden 13ケースが不変
- [ ] **385件全PASS**（既存377 + 新規8）

---

## 実装者への申し送り

**1. 設計書 §4.3(b) を1点だけ上書きしている。**
「再帰または `itertools.combinations_with_replacement`」とあるが、**後者では順序が一致しない**ことを検証済み。再帰版で実装すること（V2.2）。

**2. 「動いた」ではなく「1点も変わっていない」を確認すること。**
本 Phase の失敗モードは「N市場で動くようになったが、3市場の答えが微妙に変わった」である。`len()` が合っているだけでは不十分で、**231点を順序ごと `==` で照合**すること。

**3. `zip` の静かな切り捨てに注意（V4）。**
`zip(markets, x)` は長さが違っても例外を出さない。この経路で壊れると、テストが落ちずに**利益だけが過小になる**。明示検査を必ず入れること。

**4. コメント内の「MARKETS 順」も直すこと（V5.2）。**
`merit_order.py` L215 / L227 は文字列・コメントである。コードだけ直してコメントが古いままになると、次に読む人が誤解する。誤読を招く記述は関連箇所ごと潰すのが本プロジェクトの方針。

**5. 本 Phase では「N市場で動く」までを完成とする。**
N市場で**意味のある結果が出る**のは Phase 6-3（階層化）の役目である。N=6 の 53,130点スキャンは「通ること」の確認であって、実務で使う想定ではない。レジームラベルが N 市場で長大になる件（V5.3）も 6-3 以降。

**6. `grid.py` は禁足コアではないが、A系統の土台である。**
Phase 5 に続く2度目の明示的スコープインである。関数の**追加**と `MARKETS` 参照の**置換**に留め、`evaluate_point()` の計算順（数量を先に決めてから単価を解決する）には**触れないこと**。これは Phase 5 で非凹ケースのために意図的に入れた順序である。

---

## 参考 — 本 Phase の位置づけ

```
Phase 6-1  true_optimum の実計算化          ✅ 完了（64e7757 + 8a8eb1f）
Phase 6-2  次元の一般化（3市場 → N市場）    ← 本書
Phase 6-3  階層化単体格子（hierarchical_simplex）
             oil-global-2027（21市場）を
             1,378億点 → 三角図13枚 × 231点 = 3,003点 で扱えるようにする
```

6-2 は**それ自体では実務価値を生まない**（N=7 で止まるため）。6-3 の土台として必要な、純粋に構造的な作業である。逆に言えば**6-2 が正しく入れば 6-3 は格子生成の組み替えだけで済む**ので、ここで順序と点数を厳密に固めておく意味は大きい。
