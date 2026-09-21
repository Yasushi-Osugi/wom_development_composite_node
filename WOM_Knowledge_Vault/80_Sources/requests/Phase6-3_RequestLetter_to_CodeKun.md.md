---
tags: [wom, source]
---
# requests/Phase6-3_RequestLetter_to_CodeKun.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/requests/Phase6-3_RequestLetter_to_CodeKun.md) · [原文テキスト](../../90_Raw/requests/Phase6-3_RequestLetter_to_CodeKun.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Phase 6-3 実装 Request Letter — 階層化単体格子（`hierarchical_simplex`）
- 概要
- ⚠️ 実測で分かったこと — 設計書を書いた時点の想定と違う点が4つある
- (1) 誤差の基準は `P_flat` ではなく `P_opt` である（**最重要**）
- (2) 内部比率を解放して得られる利益は「能力の切れ目がグループの内側に落ちたとき」だけ生じる
- (3) `simplex_grid()` は `n_dim >= 2` しか作れない
- (4) `cost_block.py` に、`oil-global-2027` で顕在化する**サイレントなデータ欠落**がある
- wom/allocation/cost_block.py:79-80
- ⚠️ 絶対制約
- V1: `build_hierarchy()` — 木を組む
- V2: `aggregate_block()` — グループノードの CostBlock
- V3: `scan_hierarchical()` — 木を降りながら走査（案B）
- V4: `hierarchy_gap()` — 誤差を金額で出す
- V5: `derive_cost_blocks()` に地域レベルの取り出しを足す
- V6（6-3b）: `oil-global-2027` を A系統に接続する
- V6.1 まず `cost_block.py` の `region` 重複を検出する
- 1) region -> leaf の写像を作るとき、重複を検出する
- 2) 解決は market_node 列 > region の順。重複 region を market_node 無しで
- 引こうとしたら、黙って上書きせず例外にする
- V6.2 `data/sample/oil-global-2027/ga_market_aggregation.csv` を作る
- V6.3 21市場で走らせる
- V7: テスト仕様（新規8件）
- V7.1 `test_aggregate_block_reproduces_market_blocks`（**最重要**）
- V7.2 `test_build_hierarchy_reproduces_market_group`
- V7.3 `test_hierarchy_split_invariance`（**最重要**）
- JP -> JP_a/JP_b, US -> US_a/US_b, EU -> EU_a/EU_b（需要は半分ずつ）
- 木は {JP_a,JP_b} / {US_a,US_b} / {EU_a,EU_b} の3グループ
- V7.4 `test_hierarchy_gap_is_nonnegative`
- V7.5 `test_hierarchy_gap_regression_cap500`
- V7.6 `test_hier_minus_flat_has_no_fixed_sign`
- cap_wk=500  -> P_hier > P_flat（+428,880.0）
- cap_wk=1200 -> P_hier < P_flat（−1,840,657.5）
- V7.7 `test_internal_ratio_freedom_only_when_cut_is_inside_group`
- V7.8 `test_hierarchy_errors`
- V7.9（6-3b・テストではなく確認事項）
- 成功基準
- 実装者への申し送り

## 関連する知識源

- [[80_Sources/requests/Phase6_DesignMD_NMarketHierarchy.md|requests/Phase6_DesignMD_NMarketHierarchy.md]]
- [[80_Sources/docs/design/ask_global_allocation_spec.md|docs/design/ask_global_allocation_spec.md]]
- [[80_Sources/wom/allocation/hierarchical_simplex.py|wom/allocation/hierarchical_simplex.py]]
- [[80_Sources/wom/allocation/cost_block.py|wom/allocation/cost_block.py]]
- [[80_Sources/tools/gen_oil_ga_aggregation.py|tools/gen_oil_ga_aggregation.py]]
- [[80_Sources/tests/test_allocation_hierarchical.py|tests/test_allocation_hierarchical.py]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Phase 6-3 実装 Request Letter — 階層化単体格子（`hierarchical_simplex`）

**宛先**: Code君
**作成日**: 2026年9月11日
**担当**: Claude君（設計・仕様）→ 大杉さん（レビュー）→ Code君（実装）
**優先度**: HIGH（N市場化の完成。A系統を実ケースに接続する最後のステップ）
**ブランチ**: `wom-v1r4m0`
**設計正典**: `requests/Phase6_DesignMD_NMarketHierarchy.md` §5（rev.6）／`docs/design/ask_global_allocation_spec.md` v0r4
**前提**: Phase 6-2a 完了（`b41581a`、388件全PASS）

---

## 概要

平坦な単体格子は N=6（53,130点）で頭打ちになる。`oil-global-2027` の21市場は 1,378億点で、原理的に走らない。**市場を木にまとめ、各ノードで3市場以下の単体を走査する**ことで、21市場を **13ノード・1,743点**で扱えるようにする。

本 Phase は2つの小ステップからなる。

| ステップ | 内容 |
|---|---|
| **6-3a** | `wom/allocation/hierarchical_simplex.py` の新規実装（木の構築・階層走査・誤差測定） |
| **6-3b** | `oil-global-2027` を A系統に接続する（`ga_market_aggregation.csv` の作成と、その前提となる `cost_block.py` の修正） |

---

## ⚠️ 実測で分かったこと — 設計書を書いた時点の想定と違う点が4つある

**すべて Claude君が実装済みコードで実測した。** 設計書 rev.6 にも反映済みだが、実装に直接効くので本書にも書く。

### (1) 誤差の基準は `P_flat` ではなく `P_opt` である（**最重要**）

設計書 rev.4 までは「階層化の誤差 = `P_flat − P_hier`、0 以上」としていた。**これは誤りだった。符号が定まらない。**

soysauce の地域6件で、シナリオ×能力を15通り実測した結果:

```
階層化が平坦格子に勝った   6 回
同じ                       3 回
負けた                     6 回
```

理由は、階層化が**単なる間引きではなく多重解像度**だからである。誤差の源が2つあり、向きが逆を向いている。

| 誤差の源 | 向き |
|---|---|
| 上位で確定した配分が下位の事情を見ていない（案B の近似） | 悪くなる |
| グループ内は `cap_g` に対する5%刻み＝**絶対量では細かい** | 良くなる |

**これは Phase 4/5 の `gap_amt = P_greedy − P_grid` と同じ落とし穴である。** あのときも「貪欲法と格子のどちらが上か」に決まった順序はなく、その反転自体が指標だった。**次元でも同じことが起きる。**

したがって誤差の基準は、格子を経由しない `P_opt`（`true_continuous_optimum()`）とする。

```
階層化の誤差 = P_opt − P_hier      ← 常に 0 以上
参考値       = P_flat − P_hier     ← 符号が定まらない。両方返すが、基準にしない
```

実測（soysauce 6地域・`fx=150 / mat=6.0`）:

| `cap_wk` | `P_opt` | `P_flat`（53,130点） | `P_hier`（483点） | `P_opt−P_flat` | `P_opt−P_hier` |
|---:|---:|---:|---:|---:|---:|
| 400 | 75,891,637.5 | 75,706,800 | 75,803,520 | 184,837.5 | **88,117.5** |
| 500 | 94,455,637.5 | 93,564,900 | 93,993,780 | 890,737.5 | **461,857.5** |
| 650 | 121,188,862.5 | 120,640,530 | 120,640,530 | 548,332.5 | 548,332.5 |
| 800 | 135,529,822.5 | 128,819,812.5 | 130,292,415 | 6,710,010 | **5,237,407.5** |
| 1200 | 148,505,572.5 | 148,505,572.5 | 146,664,915 | 0 | 1,840,657.5 |

`cap_wk=1200`（能力が需要を上回る）では平坦格子が `P_opt` にちょうど届き、階層化が負ける。**能力が拘束していないときは階層化の旨味がない**ことも、そのまま示されている。

### (2) 内部比率を解放して得られる利益は「能力の切れ目がグループの内側に落ちたとき」だけ生じる

仕様書 v0r4 §2.4 で「階層モードでは内部配分が各ノードの決定変数になる」と定めた。その経済的な値打ちを実測した（貪欲法ベース・格子を経由しない厳密値）。

| `cap_wk` | 3市場（内部比率固定） | 6地域（内部比率も自由） | 差 | 限界市場 |
|---:|---:|---:|---:|---|
| 300 | 57,142,800.0 | 57,142,800.0 | **0** | EU / NL |
| 400 | 75,650,700.0 | 75,891,637.5 | **+240,937.5** | US / US_W |
| 500 | 93,824,700.0 | 94,455,637.5 | **+630,937.5** | US / US_W |
| 550 | 102,911,700.0 | 103,404,862.5 | +493,162.5 | US / US_E |
| 650 | 121,085,700.0 | 121,188,862.5 | +103,162.5 | US / US_E |
| **800（既定）** | 135,529,822.5 | 135,529,822.5 | **0** | JP / JP |
| 1000 | 148,505,572.5 | 148,505,572.5 | **0** | なし |

**`cap_wk=400〜650` の帯域でだけ正になる。** 限界市場がグループの内側（US_W / US_E）に落ちている帯域である。既定の `cap_wk=800` では限界市場が JP（単独グループ）なので、内部比率を解放しても**1円も増えない**。

**実装上の帰結: テストは `cap_wk=500` で書くこと。** `cap_wk=800` では階層化の効果が退化して 0 になり、テストが「何も検証していない」状態になる。既存の回帰値が `cap_wk=800` なのは、この意味では運が悪い。

### (3) `simplex_grid()` は `n_dim >= 2` しか作れない

子が1つのノード（soysauce の JP グループ）で `scan_surface()` を呼ぶと `ValueError: n_dim must be >= 2` になる。**子1のノードは走査せず、`evaluate_point((1.0,), ...)` で直接評価する。** 点数にも数えない（§5.2 の 483点・1,743点はこの前提で計算されている）。

### (4) `cost_block.py` に、`oil-global-2027` で顕在化する**サイレントなデータ欠落**がある

```python
# wom/allocation/cost_block.py:79-80
leaf_of_region = {r["region"]: r["node_name"]
                  for r in sct_rows if r["node_type"] == "leaf_out"}
```

**`region` が一意であることを暗黙に仮定している。** soysauce では6地域が一意なので問題にならないが、`oil-global-2027` は **21の `leaf_out` に対して `region` が15種類しかない**。`KANTO` / `KANSAI` / `CHUBU` が3本の供給ライン（`Local` / `Local_H` / `Local_R`）で重複しており、**後の行が前の行を黙って上書きする**。

このまま `ga_market_aggregation.csv` を書くと、**6市場ぶんの原価ブロックが別の市場のものにすり替わる。例外も警告も出ない。** 6-3b はここから直す（V6）。

---

## ⚠️ 絶対制約

- **C1**: matplotlib のみ。**C2**: 新規依存なし（標準ライブラリのみ）
- **C3**: 図の保存は `output/` 配下。**C4**: 図中テキストは英語
- **C5**: 返却は Dict。**C6**: 禁足コア6ファイルに一切触れない
- **C7**: **乱数を使わない。** 木の構築・走査順・返却順はすべて決定的であること
- **C8**: `grid.py` / `merit_order.py` / `analytics.py` / `regime_map.py` の**既存の返却値を1円も変えない**。`hierarchical_simplex.py` は新規ファイルであり、既存モジュールは**読むだけ**
- **C9**: 「走らせたら帰ってこない」を作らない。木の各ノードで `grid_point_count()` を先に確認する
- **C10（本 Phase 固有）**: **グループは通貨が同一であること。** 異なる通貨のブロックを集約すると `price_local` の平均が無意味になる。混在したら**明示エラー**（§5.4 の第二原則がこれを保証するが、実装でも検査する）

---

## V1: `build_hierarchy()` — 木を組む

`wom/allocation/hierarchical_simplex.py`（新規）。

```python
def build_hierarchy(blocks: Dict[str, CostBlock], model_dir: str,
                    max_children: int = 3) -> dict:
    """市場を「各ノードの子が max_children 以下」の木に組む（設計書 §5.4）。

    返却: {"name": str, "children": [...] , "markets": (...)}  の再帰構造。
          葉は {"name": market, "children": [], "markets": (market,)}。
    """
```

**3つの原則を、この順に適用する**（設計書 §5.4・順序は固定）。

1. **第一原則: 供給元 Mother Plant** — `sc_tree_master.csv` の `leaf_out` から `parent_node` を遡り、`supply_point`（＝供給ライン）でまとめる
2. **第二原則: 通貨圏** — 第一原則のグループが `max_children` を超えたら、その**上に**通貨（`CostBlock.ccy`）でまとめる段を足す
3. **第三原則: 供給モード** — それでも超えたら、供給ライン名で国産／輸入に割る（`Import` を含むかどうか）

**それでも `max_children` を超える場合は `ValueError` を投げる。** 黙って適当に割らない（恣意的なグループ分けは誤差の源であり、静かに入り込ませてはいけない）。

**実測での期待値**:

| ケース | 木の形 | 走査ノード |
|---|---|---:|
| soysauce 地域6件 | `ALL{JP, US{US_W,US_E}, EU{FR,BE,NL}}` | 3 |
| `oil-global-2027` 21市場 | 地域3 → 供給ライン8 → 市場21（§5.2 の図） | 13 |

**soysauce では第一原則が効かない**（`leaf_out` 6件すべてが `SP_Soy` 1本にぶら下がっており、1グループになる）。**効くのは第二原則（通貨圏）で、これが `ga_market_aggregation.csv` の `market_group` と完全に一致する**（JPY→JP、USD→US_W/US_E、EUR→FR/BE/NL）。これが V7.2 の検証根拠である。

---

## V2: `aggregate_block()` — グループノードの CostBlock

親ノードを走査するには、グループを1つの `CostBlock` で代表させる必要がある。

```python
def aggregate_block(children: Sequence[CostBlock]) -> CostBlock:
    """子ブロックを需要加重平均で1つに集約する。

    - usd / eur / jpy / tariff_rate : 需要加重平均
    - demand_qty                    : 単純合計
    - price_local / ccy             : 子で同一であること（違えば ValueError・C10）
    - material_usd_base             : 子で同一であること
    """
```

**この集約規則が正しいことは実測で確認済み。** soysauce の地域6件をこの規則で3グループに集約すると、**既存の `derive_cost_blocks()` が返す3市場ブロックと完全に一致する**（`usd` / `eur` / `jpy` / `tariff_rate` / `price_local` / `ccy` / `demand_qty` のすべて）。

```
JP : agg(usd=9.1000  jpy=1725.00 tar=0.00000 D=30150) == orig
US : agg(usd=15.6500 jpy=1575.00 tar=0.12500 D=35176) == orig
EU : agg(usd=14.6000 jpy=1575.00 tar=0.08000 D=35175) == orig
```

つまり **`ga_market_aggregation.csv` の `internal_ratio` は需要シェアそのもの**であり（`US_W:US_E = 17588:17588 = 0.5:0.5`、`FR:BE:NL = 15075:10050:10050 = 0.4286:0.2857:0.2857`）、集約は需要から導出できる。**CSV の列を新しく読む必要はない。**

**cliff（数量依存関税）を持つ市場が混ざるグループは、本 Phase では非対応とし `ValueError` を投げる。** 閾値は数量に対して定義されており、加重平均に意味がないためである。Phase 6-4 以降の課題として申し送る。

---

## V3: `scan_hierarchical()` — 木を降りながら走査（案B）

```python
def scan_hierarchical(blocks: Dict[str, CostBlock], tree: dict,
                      transfer_price_usd: float, sc: Scenario, cap_wk: float,
                      weeks: int = WEEKS, delta: float = 0.05) -> dict:
    """案B（逐次確定型）。上位を確定してから、その配分のもとで下位へ降りる。

    返却:
      {"profit": float,              # P_hier
       "q": {market: qty},           # 葉まで降りた最終配分
       "points": int,                # 実際に評価した格子点の総数
       "nodes": int,                 # 走査したノード数（子1は数えない）
       "surfaces": {node_name: [...]}}  # 各ノードの走査結果（ドリルダウン描画用）
    """
```

**アルゴリズム**（実測済み。soysauce 6地域・`cap_wk=800` での動きを併記）:

```
1. ルートの子を aggregate_block() で代表ブロックにする
2. ルートを scan_surface(代表ブロック, cap_wk) で走査 → best_point()
     -> 231点  x=(0.10, 0.45, 0.45)  q={JP:8,320, US:35,176, EU:35,175}
3. 各子ノード g について、上位が確定した数量 q[g] を「その枝の能力」として降りる
     JP  子1  走査なし          cap=8,320   profit= 6,240,000.0
     US  子2   21点  x=(0.5,0.5) cap=35,176  profit=61,470,060.0
     EU  子3  231点  x=(0.4,0.3,0.3) cap=35,175 profit=62,582,355.0
4. 葉の利益を合計する
     -> P_hier = 130,292,415.0     points = 231+21+231 = 483   nodes = 3
```

**重要な実装点**:

- 子ノードに渡す能力は、上位の `q[g]`（**需要で頭打ちされた後の実現量**）であって `x[g] × cap` ではない
- `cap_wk` 換算で渡す（`scan_surface(..., cap_wk=q[g]/weeks)`）
- **子が1つのノードは `scan_surface()` を呼ばない**（(3) の `n_dim>=2` 制約）。`evaluate_point((1.0,), ...)` で直接評価し、`points` にも `nodes` にも数えない
- `surfaces` は各ノードの走査結果をそのまま保持する。**これが将来のドリルダウン GUI の入力になる**（Phase 8）。捨てないこと

---

## V4: `hierarchy_gap()` — 誤差を金額で出す

```python
def hierarchy_gap(blocks, tree, transfer_price_usd, sc, cap_wk,
                  weeks=WEEKS, delta=0.05, max_flat_points=MAX_GRID_POINTS) -> dict:
    """階層化の誤差を測る。N が小さく平坦全数が計算できるときだけ P_flat も返す。

    返却:
      {"P_opt":  float,          # true_continuous_optimum()（格子を経由しない）
       "P_hier": float,
       "P_flat": float | None,   # 平坦全数。max_flat_points 超過なら None
       "hierarchy_gap":     P_opt − P_hier,   # ← 誤差の基準。常に 0 以上
       "flat_grid_gap":     P_opt − P_flat,   # P_flat が None なら None
       "hier_minus_flat":   P_hier − P_flat,  # 符号は定まらない（参考値）
       "points_hier": int, "points_flat": int | None}
    """
```

**`hierarchy_gap` は 0 以上であることを assert してよい**（理論上そうなる）。**`hier_minus_flat` に符号の仮定を置かないこと。** (1) の実測どおり、勝つことも負けることもある。

---

## V5: `derive_cost_blocks()` に地域レベルの取り出しを足す

検証には「同じモデルを6地域として読む」ことが要る。

```python
def derive_cost_blocks(model_dir: str, base_week: str = BASE_WEEK,
                       base_fx: float = BASE_FX,
                       level: str = "market") -> Tuple[Dict[str, CostBlock], float]:
    """level="market"（既定・従来どおり market_group で集約）
       level="region"（集約せず region を1市場として返す）"""
```

**`level="market"` の返却は1円も変えないこと（C8）。** 既定引数なので、既存の全呼び出しは無変更で通る。

`level="region"` は `by_market[r["market_group"]]` を `by_market[r["region"]]` に替えるだけで足りる（`internal_ratio` は同一グループ内での重みなので、1市場1行になれば重み1になる）。**実測で、この方法で得た6ブロックを V2 の規則で集約すると3市場ブロックに一致することを確認済み。**

---

## V6（6-3b）: `oil-global-2027` を A系統に接続する

### V6.1 まず `cost_block.py` の `region` 重複を検出する

(4) のサイレント欠落を直す。`ga_market_aggregation.csv` に **`market_node` 列（任意）** を足し、あれば `leaf_out` を直接指定できるようにする。

```python
# 1) region -> leaf の写像を作るとき、重複を検出する
leaf_of_region: Dict[str, str] = {}
dup_regions: set = set()
for r in sct_rows:
    if r["node_type"] != "leaf_out":
        continue
    if r["region"] in leaf_of_region:
        dup_regions.add(r["region"])
    leaf_of_region[r["region"]] = r["node_name"]

# 2) 解決は market_node 列 > region の順。重複 region を market_node 無しで
#    引こうとしたら、黙って上書きせず例外にする
def resolve_leaf(row: dict) -> str:
    node = (row.get("market_node") or "").strip()
    if node:
        if node not in leaf_names:
            raise ValueError(f"market_node {node!r} is not a leaf_out node")
        return node
    if row["region"] in dup_regions:
        raise ValueError(
            f"region {row['region']!r} maps to multiple leaf_out nodes "
            f"({sorted(n for n in ...)}). Add a market_node column to "
            f"ga_market_aggregation.csv to disambiguate."
        )
    return leaf_of_region[row["region"]]
```

**soysauce には `market_node` 列が無いので、この変更で挙動が変わってはいけない**（重複が無いため `region` 解決に落ちる）。C8 の対象である。

### V6.2 `data/sample/oil-global-2027/ga_market_aggregation.csv` を作る

21行。`market_group` は `leaf_out` のノード名（1市場1グループ）、`market_node` で葉を明示する。

```
market_group,region,market_node,internal_ratio,base_qty_lot,note
Retail_Local_KANTO,KANTO,Retail_Local_KANTO,1.0000,<需要>,国産ライン 関東
Retail_Local_KANSAI,KANSAI,Retail_Local_KANSAI,1.0000,<需要>,
...（21行）
```

- `base_qty_lot` は `demand_forecast.csv` を `sku_id` × `region` で年間合計する。**`region` が重複するので、`sku_id` と併せて葉に割り当てること**（`sku_id` は供給ラインごとに異なる：`Gasoline_Local` / `Gasoline_Import` / …）。ここも (4) と同根の落とし穴なので、**割り当てが一意に決まらなければ例外にして報告すること。数字を作らない**
- **生成はスクリプトで行い、`tools/gen_oil_ga_aggregation.py` として残す**こと。手書きの21行をコミットすると、次のケースでまた手書きになる

### V6.3 21市場で走らせる

```
build_hierarchy()  -> 13ノード（地域3 → 供給ライン8 → 市場21）
scan_hierarchical() -> 1,743点で完走
```

---

## V7: テスト仕様（新規8件）

**新規ファイル `tests/test_allocation_hierarchical.py`**（`test_allocation_nmarket.py` は6-2a の平坦N市場用。階層は別ファイルにする）。

### V7.1 `test_aggregate_block_reproduces_market_blocks`（**最重要**）

`derive_cost_blocks(ALLOC_DIR, level="region")` の6ブロックを `market_group` どおりに `aggregate_block()` で集約すると、`derive_cost_blocks(ALLOC_DIR)` の3ブロックと**全フィールド一致**すること。

```python
assert agg.usd == pytest.approx(orig.usd, abs=1e-9)      # JP 9.1 / US 15.65 / EU 14.6
assert agg.jpy == pytest.approx(orig.jpy, abs=1e-9)      # JP 1725 / US 1575 / EU 1575
assert agg.tariff_rate == pytest.approx(orig.tariff_rate, abs=1e-12)  # 0 / 0.125 / 0.08
assert agg.demand_qty == orig.demand_qty                 # 30150 / 35176 / 35175
assert agg.ccy == orig.ccy and agg.price_local == orig.price_local
```

### V7.2 `test_build_hierarchy_reproduces_market_group`

soysauce 6地域で `build_hierarchy()` が `{JP} / {US_W,US_E} / {FR,BE,NL}` を返すこと（`ga_market_aggregation.csv` の `market_group` と一致）。走査ノードは3。

### V7.3 `test_hierarchy_split_invariance`（**最重要**）

3市場を**双子分割**した6市場で、階層化の結果が3市場と一致すること。双子は経済条件が完全に同一なので、分割は情報を増やしていない。

```python
# JP -> JP_a/JP_b, US -> US_a/US_b, EU -> EU_a/EU_b（需要は半分ずつ）
# 木は {JP_a,JP_b} / {US_a,US_b} / {EU_a,EU_b} の3グループ
assert hier["profit"] == pytest.approx(flat3_best, abs=1.0)
```

### V7.4 `test_hierarchy_gap_is_nonnegative`

`hierarchy_gap()["hierarchy_gap"] >= 0` が、`cap_wk = 400 / 500 / 650 / 800 / 1200` のすべてで成立すること。

### V7.5 `test_hierarchy_gap_regression_cap500`

**`cap_wk=500`** での実測値を固定する（`cap_wk=800` では内部比率の効果が退化するため (2) の理由でこちらを使う）。

```
P_opt  = 94,455,637.5
P_flat = 93,564,900.0      （53,130点）
P_hier = 93,993,780.0      （483点）
hierarchy_gap = P_opt − P_hier =   461,857.5
flat_grid_gap = P_opt − P_flat =   890,737.5
hier_minus_flat = P_hier − P_flat = +428,880.0   ← この符号を仮定しない（V7.6 参照）
```

許容差 ±1 JPY。点数は `points_hier == 483` / `points_flat == 53_130` / `nodes == 3`。

### V7.6 `test_hier_minus_flat_has_no_fixed_sign`

**階層化が平坦格子に勝つケースと負けるケースが両方あること**を固定する。

```python
# cap_wk=500  -> P_hier > P_flat（+428,880.0）
# cap_wk=1200 -> P_hier < P_flat（−1,840,657.5）
```

これは「符号を仮定した実装・テストを将来書かせない」ための杭である。Phase 4/5 で `gap_amt` に対して同じことをしたのと同じ意図。

### V7.7 `test_internal_ratio_freedom_only_when_cut_is_inside_group`

内部比率を解放して得られる利益（貪欲法ベース・格子を経由しない）が、限界市場の位置で決まることを固定する。

```
cap_wk=500 : 6地域 94,455,637.5 − 3市場 93,824,700.0 = +630,937.5   限界市場 US_W
cap_wk=800 : 6地域 135,529,822.5 − 3市場 135,529,822.5 =        0   限界市場 JP（単独グループ）
```

### V7.8 `test_hierarchy_errors`

- 通貨が混在するグループを `aggregate_block()` に渡すと `ValueError`（C10）
- cliff を持つブロックが混ざるグループで `ValueError`
- `max_children` に収まらない木を要求すると `ValueError`（黙って割らない）
- 子1のノードで `scan_surface()` を呼んでいないこと（`n_dim>=2` 制約・(3)）

### V7.9（6-3b・テストではなく確認事項）

- `derive_cost_blocks("oil-global-2027")` が21市場を返し、**重複 `region` による取り違えが起きていない**こと
- `build_hierarchy()` が13ノードを返し、`scan_hierarchical()` が **1,743点**で完走すること
- soysauce に `market_node` 列を足していないのに挙動が変わっていないこと（C8）

---

## 成功基準

- [ ] `aggregate_block()` の集約が既存3市場ブロックと**全フィールド一致**
- [ ] `build_hierarchy()` が soysauce で `market_group` を再現（3ノード）
- [ ] 双子分割の不変性が**階層経由で**成立
- [ ] `hierarchy_gap >= 0` が全シナリオで成立
- [ ] `cap_wk=500` の回帰値が ±1 JPY で一致（483点 / 53,130点）
- [ ] `P_hier − P_flat` に**符号の仮定が入っていない**
- [ ] `oil-global-2027` が21市場で読め、**13ノード・1,743点**で完走する
- [ ] soysauce の全回帰値・Phase 4/5/6 の全分解値・golden 13ケースが不変
- [ ] **396件全PASS**（既存388 + 新規8）

---

## 実装者への申し送り

**1. `cap_wk=800` でテストを書かないこと。**
既定値だが、階層化の効果が 0 に退化する帯域である（限界市場が単独グループの JP に落ちるため）。**`cap_wk=500` を使う。** 800 で書くと「通っているが何も検証していない」テストになる。

**2. `P_hier − P_flat` の符号を仮定しないこと。**
実装でもテストでも。15通りの実測で 勝ち6・分け3・負け6 だった。`gap_amt` のときと同じ落とし穴である。

**3. 数値が合わなかったら、合わせにいかず報告すること。**
本書の数値はすべて Claude君が `b41581a` の実装で実測したものである。ただし**階層走査そのものはプロトタイプであり、Code君の実装と細部が違えば値も変わりうる**——特に「上位の `q[g]` を子の能力として渡す」「台地の先頭を採る（`best_point()` の返す `plateau[0]`）」の2点。**違いが出たら、どちらが正しいかを先に相談すること。**

**4. `surfaces` を捨てないこと（V3）。**
いまは使わないが、Phase 8 のドリルダウン GUI はこれを入力にする。各ノードの走査結果を保持したまま返すこと。

**5. 6-3b の CSV は必ずスクリプトで生成すること（V6.2）。**
手書きの21行をコミットすると、次のケースでまた手書きになる。`ev-thailand-2026` など他の13ケースも同じ1本が足りないだけなので、生成器は使い回せる。

**6. `region` 重複は「直す」のであって「回避する」のではない（V6.1）。**
`oil-global-2027` だけの問題に見えるが、**同じ地域に複数の販路を持つモデルはすべて踏む**。黙って上書きする現状が危険なのであって、例外にすること自体が価値である。

````
