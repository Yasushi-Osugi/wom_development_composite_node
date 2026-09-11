# Phase 5 実装設計 — 数量依存関税の導入と、構造的乖離の検証

**作成日**: 2026年9月8日
**設計責任**: Claude君（Code君の実装者レビューを反映）
**対象**: 大杉さんレビュー → Code君実装
**優先度**: MEDIUM（2-3週間）
**ブランチ**: `wom-v1r4m0`
**前提**: Phase 4 完了（commit `4468298`、357件全PASS）

---

## 1. Phase 5 全体像

### 1.1 目的

Phase 4 で `structural_residual`（メリットオーダー連続解と格子最適の乖離のうち、格子解像度で説明できない分）という量を定義した。soysauce ではこれが **0** になることを確認済みである。

Phase 5 の目的は、**「非凹な利益関数のもとでは `structural_residual` が非ゼロになる」ことを実証する**ことである。これが通れば、Phase 4 で立てた「乖離の帰属判定」という枠組みが、chatlog の言う「構造的発見」を定量的に切り出す道具として機能することが示される。

### 1.2 なぜ `ev-thailand-2026` を直接やらないか（**記録**）

当初は「Phase 4 の `structural_residual` を `ev-thailand-2026` に当てるだけ」と見積もったが、調査の結果**この見積もりは誤りだった**。3つの障害がある。

| # | 障害 | 内容 |
|---|---|---|
| 1 | `MARKETS` のハードコード | `grid.py` L24 の `MARKETS = ("JP","US","EU")` を `analytics.py` / `merit_order.py` / `regime_map.py` の**4モジュール全部が import** している。ev-thailand の市場（BKK/PRO/ONL）に差し替えるには A系統コアの改修が要る |
| 2 | `ga_*.csv` の不在 | `ga_*.csv` を持つのは `soysauce-jpy-2027-alloc` **ただ1つ**。`derive_cost_blocks()` は `ga_market_aggregation.csv` を必須で読む |
| 3 | **LC率閾値がモデルに存在しない** | `ev-thailand-2026/ppc_tariff_rule.csv` の `tariff_rate` は固定スカラー（Local 0.0 / Import 0.08）。`unit_pnl()` の関税項も配分量と無関係。**現在の伝達式は構造的に線形で、ev-thailand に当てても residual は必ずゼロになる** |

**障害3 が本丸である。** データ整備（障害1・2）を先にやっても、伝達式が線形のままでは residual がゼロで終わる。

したがって Phase 5 では **障害3 だけを先に片付け、検証台は既存の soysauce を使う**。ev-thailand への適用は Phase 6 に送る（§10）。

### 1.3 本 Phase のスコープ

- **数量依存の関税（cliff 型）を伝達式に導入する** — `CostBlock` に特恵税率と閾値を持たせ、配分量で切り替える
- **`evaluate_point()` の計算順序を改修する** — 単価を数量より先に決める現在の構造では非凹性を扱えない
- **① メリットオーダーを「近視眼的」なまま新機構に追随させる**
- **合成シナリオ `s9_fta_cliff` を soysauce に追加**し、`structural_residual` が非ゼロ（負）になることを回帰テストで固定する
- **Phase 4 設計書 §3.5.3 の符号の記述を訂正する**（rev.3）

### 1.4 スコープ外（Phase 6 以降）

- `MARKETS` のハードコード解除（障害1）
- `ev-thailand-2026` 用の `ga_*.csv` 整備（障害2）と実ケースでの検証
- ③ Pareto ＋ 平行座標の配分版、④ 階層化三角図
- TRQ（関税割当）型の数量依存（§3.1 で不採用と決定）

---

## 2. 事前検証（実データ・推定ではなく計算結果）

### 2.1 非凹性を入れると貪欲法は最適を明確に外す

まず現象そのものを確認した。JP（限界市場）に「配分が T 以上なら単価が跳ね上がる」cliff を置いた場合：

| 閾値 T / 優遇幅 | 貪欲（メリットオーダー） | 真の最適 | 取りこぼし |
|---|---|---|---|
| 20,000 / +800 | JP **12,849**（閾値に届かず）135.53M | JP **20,041** 144.39M | **+8.86M** |
| 20,000 / +1,150 | 同上 135.53M | JP 30,073 152.93M | +17.40M |
| 25,000 / +1,400 | 同上 135.53M | JP 30,073 160.45M | +24.92M |

貪欲法は「現在の単価」で並べるため JP を最劣後に置き、残りカスの 12,849 しか配らない。**閾値の存在を先読みしないので優遇を丸ごと逃す。** これが「均等限界原理が成立しない」ことの具体である。

### 2.2 現行の cap_wk=800 では cliff が成立しない（**重要**）

上記は margin に直接ボーナスを足した即席実験である。**実装で使う「関税率の切り替え」機構で、かつ現実的な優遇幅で成立するか**を確かめたところ、現行設定では成立しないことが分かった。

**関税の効き幅**: transfer_price 17.6 USD × fx 150 = **関税率 1.0 あたり 2,640 JPY/lot**

| 優遇 | margin の変化 |
|---|---|
| US 0.125 → 0.000（FTA特恵） | 1,747.5 → **2,077.5**（+330.0） |
| EU 0.080 → 0.000 | 1,831.5 → 2,042.7（+211.2） |

ところが **cap_wk=800（cap=83,200）では EU+US = 70,351 < 83,200 なので、上位2市場が必ずフル供給される。** 閾値を置いても葛藤が生まれない。限界市場は JP だが、JP の関税は既に 0.0 で下げ代がない。

**したがって cliff シナリオは能力を絞る必要がある。** これは `soysauce-jpy-2027-alloc` を作ったときの前例（CLAUDE.md L1300：能力1500では最適点が台地28点で不定になるため800に絞った）と同型の操作である。

### 2.3 採用するシナリオ `s9_fta_cliff` の確定値

**設定**: `cap_wk = 500`（cap = 52,000、充足率 51.7%）／ **US の関税 0.125 → 0.000（FTA特恵）／ 閾値 T = 25,000 lot**

特恵が発動すると US の単価 2,077.5 が EU の 1,831.5 を上回り、**優先順位が逆転する**。

| | US | EU | JP | 利益 |
|---|---|---|---|---|
| **① 近視眼的メリットオーダー** | 16,825 | 35,175 | 0 | **93,824,700** |
| δ=0.05 格子最適 `x=(0.00, 0.65, 0.35)` | 33,800 | 18,200 | 0 | **103,552,800** |
| 真の連続最適 | 35,176 | 16,824 | 0 | **103,891,296** |

- ①の λ = 1,747.5（限界市場は US。cap を EU 35,175 + US 16,825 で使い切るため JP には届かない）
- 格子最適点の `idle` = 0

Phase 4 の判定式を当てると：

```
gap_amt      =  -9,728,100
expected_gap =           0     (grid_idle 0 × λ 1,747.5)
residual     =  -9,728,100     ← 負
```

**`residual` が大きく負に振れる。** soysauce の線形ケースでは 0.000000 JPY だったので、符号と桁で明確に区別できる。

### 2.4 `residual` の符号と、分解の限界（**Phase 4 §3.5.3 の訂正**）

Phase 4 設計書には「非凹ケースでは `gap_amt > expected_gap` となり、超過分が構造由来として切り出せる」と書いたが、**符号が逆だった。**

理屈は単純である。非凹だとメリットオーダーが最適を外すので `mo_profit` が**下がる**。`gap_amt = mo_profit − grid_best` は縮み、この例では負になる。一方 `expected_gap = grid_idle × λ` は格子最適点の性質だけで決まるので影響を受けない。よって residual は負に振れる。

判定式 `abs(residual) <= abs_tol` は False を返すので**動作としては正しく働いていた**が、意味づけが逆だった。

さらに、**非凹ケースでは分解の精度が落ちる**ことも分かった。正しい内訳は：

| | 金額 |
|---|---|
| 構造由来の取りこぼし（真の最適 − 貪欲、= structural optimality gap） | **10,066,596** |
| 格子解像度の誤差（真の最適 − 格子最適） | 338,496 |
| `\|residual\|` = 9,728,100 は構造由来の **96.6%** | （**下界**） |

非凹だと格子最適点が能力を使い切る（`grid_idle = 0`）ため `expected_gap = 0` となり、格子誤差の分だけ `|residual|` が構造由来を**過小評価**する。

**したがって `residual` は「厳密な分解」ではなく、以下のように解釈する。**

| `residual` | 意味 |
|---|---|
| ≈ 0 | 乖離は格子解像度で説明できる（線形・凹なケース） |
| **< 0** | **メリットオーダーが真の最適を外している ＝ 非凹性の証拠。絶対値は取りこぼし量の下界** |
| > 0 | 想定外（要調査） |

### 2.5 用語と式の全体像（rev.2 で追記）

これまでに出てきた量を1箇所に整理する。**用語の平易な説明は Phase 4 設計書 §3.5.2 / §3.5.3 にある**ので、そちらも併せて読むこと。

#### 3つの利益水準

| 記号 | 内容 | s1_base（線形） | s9_fta_cliff（非凹） |
|---|---|---|---|
| `P_greedy` | ①近視眼的メリットオーダー（貪欲法）の利益 | 135,529,822.5 | 93,824,700 |
| `P_grid` | δ=0.05 格子（231点）の最適 | 132,133,072.5 | 103,552,800 |
| `P_opt` | 真の連続最適（刻みなし） | **`P_greedy` と同じ** | 103,891,296 |

**線形なら `P_greedy = P_opt`**（均等限界原理が厳密に成立し、貪欲法が厳密解になる）。**非凹だと `P_greedy < P_opt`**（貪欲法が閾値を先読みできず最適を外す）。この1行の違いが Phase 4 と Phase 5 の関係そのものである。

#### 式

```
gap_amt                    = P_greedy − P_grid        ← 引き算のみ。絶対値ではない
expected_gap               = grid_idle × λ            ← 引き算ではなく掛け算
structural_residual        = gap_amt − expected_gap
structural_optimality_gap  = P_opt − P_greedy         ← P_grid ではなく P_greedy
格子解像度の誤差            = P_opt − P_grid
```

**`gap_amt` の "amt" は amount（金額ベース）の意味で、`gap_pct`（率）と対になる。** 絶対値ではないので符号が正にも負にもなり、**その符号こそが非凹性の指標**である（初版は `gap_abs` という名前だったが、絶対値と誤読されるため rev.2 で改名した）。

#### 数値で見る

| | s1_base（線形） | s9_fta_cliff（非凹） |
|---|---|---|
| `grid_idle` | 4,529 lot | **0 lot** |
| `λ` | 750 JPY/lot | 1,747.5 JPY/lot |
| `gap_amt` | **+3,396,750** | **−9,728,100** |
| `expected_gap` | 3,396,750 | **0** |
| `structural_residual` | **0** | **−9,728,100** |
| `structural_optimality_gap` | 0 | 10,066,596 |
| 格子解像度の誤差 | 3,396,750 | 338,496 |

**s1_base では乖離が全額説明でき（residual = 0）、s9_fta_cliff では1円も説明できない（expected_gap = 0）。** 非凹だと格子最適点が能力を使い切って遊休能力がゼロになるため、「余った能力を回す」という説明の余地が消える。結果として乖離の全額が `structural_residual` に落ちる。

#### 恒等式

```
|structural_residual|  +  格子解像度の誤差  =  structural_optimality_gap
      9,728,100         +      338,496       =      10,066,596
```

`|residual|` が 96.6% にしかならない理由がここにある。真の最適の代わりに格子最適を引き算の相手に使っている以上、格子自身の誤差の分だけ必ず少なく出る。**だから下界（lower bound）になる**（詳細は Phase 4 設計書 §3.5.3）。

---

## 3. 伝達式の拡張（数量依存の関税）

### 3.1 cliff 型で確定（TRQ 型を採らない理由）

**cliff 型**（配分量が閾値以上なら税率が丸ごと切り替わる）は **FTA 原産地規則そのもの**である。「域内付加価値比率が X% を超えれば特恵税率、届かなければ MFN 税率」という実際の制度と構造が一致する。`ev-thailand-2026` の LC率閾値もこれである。

**TRQ 型**（関税割当・超過分だけ税率が変わる）は農産物輸入枠のような別の制度で、通常「枠内は低税率、枠を超えた分は高税率」＝**量を増やすほど限界的に不利＝凹方向**に効く。§2.1 で確認した非凹性（量を増やすほど有利）とは**逆方向の現象**であり、導入すると検証したいものを再現しない。

**cliff 型一本で確定する。** TRQ 型は本 Phase のスコープ外とする。

### 3.2 `CostBlock` の後方互換な拡張

**新しい概念を持ち込まず、既存の関税メカニズム（Step 3）をそのまま伸ばす。** `unit_pnl()` は既に `cb.tariff_rate × transfer_price_usd` という関税項を持っているので、**「どちらの税率を使うか」を数量で切り替えるだけ**で済む。

```python
@dataclass(frozen=True)
class CostBlock:
    # ... 既存フィールドは無変更 ...
    tariff_rate: float

    # --- Phase 5 で追加（いずれも既定 None ＝ 従来動作） ---
    tariff_rate_preferential: Optional[float] = None   # 閾値到達時に適用する特恵税率
    preferential_threshold_lot: Optional[float] = None # 発動閾値（lot）

    def tariff_at(self, qty: float) -> float:
        """配分量 qty のときに適用される関税率を返す（Step 3 用）。

        cliff 型: qty >= preferential_threshold_lot なら
                  tariff_rate_preferential、そうでなければ tariff_rate。
        どちらかが None なら常に tariff_rate（従来動作）。
        """
        if self.tariff_rate_preferential is None or self.preferential_threshold_lot is None:
            return self.tariff_rate
        return (self.tariff_rate_preferential
                if qty >= self.preferential_threshold_lot else self.tariff_rate)
```

**両フィールドとも既定 `None` なので、既存の呼び出し（soysauce の231点評価・Phase 4 の回帰値・golden）は一切影響を受けない。**

### 3.3 `unit_pnl_at_quantity()`（新規・`unit_pnl()` は無変更）

`transmission.py` 本体の `unit_pnl()` には手を入れず、**薄いラッパー関数を追加**する。

```python
def unit_pnl_at_quantity(
    cb: CostBlock, sc: Scenario, qty: float,
    transfer_price_usd: float = DEFAULT_TRANSFER_PRICE_USD,
) -> Dict[str, float]:
    """配分量 qty のときの per-lot 損益。

    cb.tariff_at(qty) で税率を解決し、その税率を持つ CostBlock の複製に対して
    既存の unit_pnl() を呼ぶ。計算式そのものは unit_pnl() のまま（重複実装しない）。
    """
    rate = cb.tariff_at(qty)
    if rate == cb.tariff_rate:
        return unit_pnl(cb, sc, transfer_price_usd)       # 従来経路そのまま
    return unit_pnl(replace(cb, tariff_rate=rate), sc, transfer_price_usd)
```

`dataclasses.replace` を使うことで、**計算式を二重に持たない**。`unit_pnl()` の仕様が変わっても自動的に追随する。

### 3.4 `evaluate_point()` の改修 —「A系統無変更」の例外（**明示的にスコープイン**）

Phase 3・Phase 4 では「A系統4モジュール無変更」を守ってきたが、**Phase 5 の目的そのものが「単価が配分量に依存する」モデルへの拡張である。**

現在の `evaluate_point()`（`grid.py` L43-46）は

```python
ue = {m: unit_pnl(blocks[m], sc, transfer_price_usd) for m in MARKETS}   # ← 単価が先
q  = {m: min(xi * cap, blocks[m].demand_qty) for m, xi in zip(MARKETS, x)}
```

という順序で、**単価を数量より先に確定させている。この計算順序そのものが非凹性を扱えない構造の根**であり、ここを触らずに実現するのは原理的に不可能である。

**改修は2行の順序入れ替えと、単価取得関数の差し替えに限定する。**

```python
q  = {m: min(xi * cap, blocks[m].demand_qty) for m, xi in zip(MARKETS, x)}   # ← 数量を先に
ue = {m: unit_pnl_at_quantity(blocks[m], sc, q[m], transfer_price_usd) for m in MARKETS}
```

**「A系統無変更」原則からの逸脱は `grid.py` の `evaluate_point()` 内の数行に限定される。** `transmission.py` / `cost_block.py` / `analytics.py` は無変更を維持する。この逸脱は Phase 3/4 の制約とは別枠であることを設計書に明記し、CLAUDE.md にも記録する。

**後方互換**: `tariff_rate_preferential` が `None` の既存 CostBlock では `unit_pnl_at_quantity()` が `unit_pnl()` をそのまま呼ぶため、**Phase 4 の回帰値（135,529,822.5 / 132,133,072.5）は1円も変わらない。** これを回帰テストで固定する（§7.1-3）。

### 3.5 ① メリットオーダーは**意図的に近視眼的**なままにする（**最重要**）

①が「後で閾値を超えることを知っている」ような賢い計算をしてしまうと、**検証したい「貪欲法の限界」そのものが再現できなくなる。** ①は近視眼的でなければならない。

ただし「近視眼的」の意味には実装上の曖昧さがある。貪欲法では順位を決める時点でその市場への配分量は 0 だが、積んだ後に閾値を超えると事後的に単価が変わる。**順位付けに使う単価と、利益計算に使う単価が食い違う。** 3つに分けて明示する。

| 段階 | 使う単価 | 根拠 |
|---|---|---|
| **順位付け** | **配分量 0 における単価**（＝`cb.tariff_rate`、特恵なし） | 貪欲法は決定時点で見えている値しか使えない。これが「近視眼的」の実体 |
| **配分量の決定** | （単価を使わない）`min(残能力, 需要)` | 従来どおり |
| **利益計算** | **実際の配分量に応じた単価**（`tariff_at(q)` 適用後） | 現実に発生する損益は実配分量で決まる。閾値を超えたなら特恵は実際に効く |

**図のブロックの高さは「順位付けに使った単価」で描く。** 実際の単価で描くと矩形が階段になり、「なぜこの順位なのか」が図から読めなくなる。①の図は「貪欲法が何を見て、何をしたか」を示すものなので、貪欲法が見ていた値で描くのが誠実である。**cliff が実際に発動したかどうかは注記で示す。**

`build_allocation_merit_order()` の戻り値に以下を追加する。

```python
"preferential": {                     # cliff の発動状況（None なら cliff 設定なし）
    "US": {"threshold": 25000.0, "allocated": 16825.0,
           "triggered": False,        # 閾値に届いたか
           "rate_base": 0.125, "rate_preferential": 0.0,
           "margin_ranking": 1747.5,  # 順位付けに使った単価（図の高さ）
           "margin_effective": 1747.5},  # 実配分量に応じた単価（利益計算）
},
```

---

## 4. 合成シナリオ `s9_fta_cliff`

### 4.1 CSV スキーマの拡張

`ga_scenario_master.csv` は既に `scenario_id, quarter, market, currency, tariff_rate, fx_spot_jpy, material_price_usd, interest_rate_annual, note` を持つ。**列を2本追加する。**

```
scenario_id,quarter,market,currency,tariff_rate,tariff_rate_preferential,preferential_threshold_lot,fx_spot_jpy,material_price_usd,interest_rate_annual,note
```

- 既存行はこの2列を**空欄**にする。空欄 → `None` → 従来動作
- `s9_fta_cliff` の US 行のみ `tariff_rate_preferential=0.000` / `preferential_threshold_lot=25000` を設定

`cost_block.py` の `derive_cost_blocks()` と `tools/run_allocation_map.py` の `load_scenarios()` が、この2列を読んで `CostBlock` に渡すよう配線する。**列が存在しない古い CSV でも動くこと**（`row.get(...)` で欠損を許容）。

### 4.2 既存シナリオへの非影響（**必須**）

**`s1_base` 〜 `s8_actual_path` の行は1文字も変更しない。** Phase 4 の回帰値（最大利益 s1=132.1M 等、CLAUDE.md L1311）と `ga_switching_point.csv` の 117/119円 を守る。

新シナリオは `s9_fta_cliff` として**行を追加するだけ**とする。

### 4.3 `cap_wk` の扱い（**レビュー事項 R1**）

§2.2 のとおり、cliff が効くには `cap_wk = 500` が必要である。しかし `ga_scenario_master.csv` は能力の列を持たない（`cap_wk` は CLI 引数 `--cap-wk` / `capacity_plan.csv` 由来）。

**本設計では `cap_wk` をシナリオ CSV に持ち込まず、CLI とテストで明示的に 500 を渡す方式とする。** 理由は、`cap_wk` を CSV に入れると既存シナリオ全行に列を足すことになり §4.2 の「既存行を変更しない」と衝突するため。

`s9_fta_cliff` の `note` 列に「本シナリオは cap_wk=500 での使用を前提とする（cap_wk=800 では US/EU が常にフル供給され cliff が発動しない）」と明記する。

---

## 5. Phase 4 設計書 §3.5.3 の訂正（rev.3）

§2.4 の内容を Phase 4 設計書に反映する。

- 「非凹ケースでは `gap_amt > expected_gap` となり」→ **符号が逆。`residual` は負に振れる**
- `residual` の符号別の意味づけ表を追加
- 非凹ケースでは `expected_gap` の推定精度が落ちるため、**`|residual|` は取りこぼし量の下界**であることを明記（厳密な分解を主張しない）

**`compare_with_grid()` の実装は変更不要。** 判定式 `abs(structural_residual) <= abs_tol` は符号によらず正しく働く。訂正するのはドキュメントの意味づけのみ。

---

## 6. 共通仕様

### 6.1 技術制約（Phase 3/4 を継承）

1. **matplotlib のみ**（plotly / bokeh / dash / streamlit / seaborn 禁止）
2. **新規依存パッケージを追加しない**
3. `matplotlib.use("Agg")` を pyplot import の前
4. **図中のテキストはすべて英語**
5. **各描画関数は出力パスを返す**、`plt.close(fig)` する
6. **凡例・注記をデータの上に重ねない。** 軸レンジを緩めて余白を作らない
7. **乱数を使わない**

### 6.2 ファイル配置

| 対象 | パス | 扱い |
|---|---|---|
| `CostBlock` 拡張・`unit_pnl_at_quantity()` | `wom/allocation/transmission.py` | **追加のみ**（`unit_pnl()` は無変更） |
| `evaluate_point()` の計算順序 | `wom/allocation/grid.py` | **改修**（§3.4・A系統無変更の例外） |
| ① の近視眼的単価取得 | `wom/allocation/merit_order.py` | **改修** |
| シナリオ読込の配線 | `wom/allocation/cost_block.py` / `tools/run_allocation_map.py` | **改修**（列の欠損を許容） |
| `analytics.py` / `regime_map.py` | — | **無変更** |
| B系統 `wom/visualization/*` | — | **無変更** |
| 合成シナリオ | `data/sample/soysauce-jpy-2027-alloc/ga_scenario_master.csv` | **行と列の追加のみ** |
| テスト | `tests/test_allocation_nonconcave.py` | **新規** |

### 6.3 禁足ルールとの関係

Planning Engine 保護対象コアには**一切触れない**。golden 13ケースにも影響しない。

---

## 7. テスト計画

### 7.1 後方互換（`tests/test_allocation_nonconcave.py`、4件）

**Phase 4 の回帰値が1円も変わらないことを最優先で固定する。**

1. `test_tariff_at_returns_base_when_no_cliff` — `tariff_rate_preferential=None` なら `tariff_at(qty)` が常に `tariff_rate`
2. `test_unit_pnl_at_quantity_matches_unit_pnl_without_cliff` — cliff なしで両者が完全一致
3. `test_phase4_regression_unchanged` — **soysauce s1_base / cap_wk=800 で λ=750、x=(0.1544, 0.4228, 0.4228)、利益 135,529,822.5、格子最適 132,133,072.5 が不変**
4. `test_evaluate_point_unchanged_without_cliff` — `evaluate_point()` の改修後も cliff なしの結果が全231点で不変

### 7.2 cliff の動作（4件）

5. `test_tariff_at_switches_at_threshold` — `qty` が閾値の前後で税率が切り替わる（境界値 `qty == T` は特恵側）
6. `test_preferential_flips_ranking` — US に特恵が発動すると単価 2,077.5 > EU 1,831.5 で順位が逆転する
7. `test_merit_order_is_myopic` — **①が閾値を先読みしない**（`s9_fta_cliff` で US=16,825 に留まり `triggered=False`）
8. `test_merit_order_profit_uses_effective_margin` — 利益計算は実配分量に応じた単価を使う（順位付けの単価ではない）

### 7.3 構造的乖離の検出（3件）

9. `test_s9_cliff_regression` — **`s9_fta_cliff` / cap_wk=500 で ① 93,824,700 JPY、格子最適 103,552,800 JPY、`x=(0.00,0.65,0.35)`**（§2.3 の値を固定）
10. `test_structural_residual_is_negative` — **`residual` ≈ −9,728,100 で負、`attributable_to_grid_resolution` が False**（§2.3）
11. `test_residual_underestimates_true_gap` — 真の連続最適 103,891,296 に対し、`|residual|` が構造由来の取りこぼし 10,066,596 の下界であること（96.6%）

### 7.4 シナリオ読込（2件）

12. `test_scenario_csv_loads_cliff_columns` — `s9_fta_cliff` の US 行から特恵税率と閾値が読める
13. `test_scenario_csv_missing_columns_ok` — 2列が存在しない古い CSV でも例外にならない

### 7.5 合計

| | 件数 |
|---|---|
| Phase 4 完了時点 | 357 |
| Phase 5 新規 | 13 |
| **合計** | **370 件 全PASS** |

既存357件に回帰なし、golden 13ケース不変を維持すること。

---

## 8. 成功基準

- [ ] **Phase 4 の回帰値が1円も変わらない**（135,529,822.5 / 132,133,072.5 / λ=750 / x=(0.1544,0.4228,0.4228)）
- [ ] `ga_switching_point.csv` の 117円/119円 が不変
- [ ] `tariff_at()` が cliff 未設定時に従来動作、閾値の前後で正しく切り替わる
- [ ] `unit_pnl()` が**無変更**であること（`unit_pnl_at_quantity()` は `replace()` 経由で呼ぶだけ）
- [ ] `evaluate_point()` の改修が計算順序の入れ替えと単価取得の差し替えに限定されていること
- [ ] **①が近視眼的であること**（`s9_fta_cliff` で US=16,825、`triggered=False`）
- [ ] **`structural_residual` ≈ −9,728,100（負）**、`attributable_to_grid_resolution` が False
- [ ] `s9_fta_cliff` 追加後も既存シナリオ `s1_base`〜`s8_actual_path` の行が1文字も変わっていないこと
- [ ] 370件全PASS（既存357件に回帰なし、golden 13ケース不変）
- [ ] `analytics.py` / `regime_map.py` / B系統が無変更
- [ ] Phase 4 設計書が rev.3 に更新され、§3.5.3 の符号が訂正されていること

---

## 9. レビュー事項（大杉さんへ）

| # | 箇所 | 内容 |
|---|---|---|
| **R1** | §4.3 | `cap_wk=500` を CSV に持たせず CLI/テストで渡す方式でよいか。CSV に列を足すと既存シナリオ全行を触ることになり §4.2 と衝突する |
| **R2** | §3.5 | ①の図のブロック高さを「順位付けに使った単価」で描く方針でよいか。実際の単価で描くと矩形が階段になり順位の根拠が読めなくなる |
| **R3** | §2.3 | 閾値 T=25,000 でよいか。T=20,000 / 30,000 でも結果は同じだったので、US 需要 35,176 の約71%・貪欲解 16,825 の約1.5倍という「明確に届かない」水準として選んだ |
| **R4** | §3.4 | `evaluate_point()` の改修を「A系統無変更の例外」として認めるか。Phase 5 の目的そのものがこの構造の拡張なので不可避と判断した |

---

## 10. Phase 6 への引き継ぎ（`ev-thailand-2026` への適用）

Phase 5 が通れば、ev-thailand への適用に残る障害は**データ整備だけ**になる。

| 残課題 | 内容 | 規模 |
|---|---|---|
| `MARKETS` のハードコード解除 | `grid.py` の定数を外部から与える形に。4モジュールが import しているので影響範囲の確認が要る | 中 |
| `ga_*.csv` 3本の新規作成 | ev-thailand 用（`ga_market_aggregation` / `ga_scenario_master` / `ga_fx_policy_master`） | 中 |
| LC率閾値のモデル化 | **Phase 5 で解決済み。** `tariff_rate_preferential` + `preferential_threshold_lot` をそのまま使う | — |
| 検証 | `structural_residual` が負になるか。soysauce の合成シナリオで「負になること」を確認済みなので、実ケースで再現するかを見る | 小 |

**Phase 5 で「非凹なら residual が負に振れる」ことを実データで固定しておけば、Phase 6 は純粋にデータ整備の作業になり、失敗リスクが小さくなる。** これが soysauce を先に置く理由である。

---

**次のステップ**: 大杉さんのレビュー（特に §9 の R1-R4）→ Code君への Request Letter 作成 → 実装開始

**改訂履歴**
- 2026-09-08 初版（Code君の実装者レビュー (a)(b)(c) を §3.2 / §3.4 / §3.5 に反映）
- 2026-09-09 rev.2 — `gap_abs` → `gap_amt` の改名を反映（commit `5f46ffc`。"abs" が絶対値と誤読されるため。この値は符号が正負どちらにもなり、**その符号こそが非凹性の指標**である）。「構造由来の取りこぼし」の英語名を **`structural_optimality_gap`** に確定（OR の標準用語 optimality gap に、原因が問題の構造にあることを示す structural を冠したもの。`structural_residual` はその**下界**、という対の関係が名前から読める）。**§2.5「用語と式の全体像」を新設** — 3つの利益水準（`P_greedy` / `P_grid` / `P_opt`）、5本の式、線形ケースと非凹ケースの数値対比、恒等式 `|residual| + 格子誤差 = structural_optimality_gap` を1箇所に整理。用語の平易な説明は Phase 4 設計書 §3.5.2 / §3.5.3（rev.4）に置いた
- 2026-09-11 rev.3 — Phase 6-1 の実装により、§2.3 の真の連続最適を実測値へ訂正。**旧値は誤りだった**：配分 `JP=7 / US=35,168 / EU=16,825`（profit 103,881,757.5）は最適点ではなく、単位マージン 2,077.5 の US 需要を 8 lot 残して最低マージンの JP に 7 lot 配る劣った点だった。正しくは `JP=0 / US=35,176 / EU=16,824`（profit **103,891,296.0**）。これに伴い `structural_optimality_gap = 10,066,596`、格子解像度の誤差 `338,496`、`|residual|` の被覆率 **96.6%** に更新。`gap_amt = −9,728,100`・`expected_gap = 0`・`structural_residual = −9,728,100` は `P_greedy` と `P_grid` から決まるため**変わらない**。差 +9,538.5 の1円までの分解は Phase 6 設計書 §3.5 に記録
