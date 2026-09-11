# wom-v1r4m0 Phase 5: 数量依存関税（cliff型）の導入と構造的乖離の検証 実装ガイド

**設計正典**: `requests/Phase5_DesignMD_NonConcaveTariff.md`
**実装責任**: Code君　**設計責任**: Claude君（Code君の実装者レビューを反映）
**実装日**: 2026年9月9日

---

## 1. 概要

Phase 4で定義した`structural_residual`（メリットオーダー連続解と231点格子最適の乖離のうち、
格子解像度で説明できない分）が、**非凹な利益関数のもとでは非ゼロになる**ことを実証した。
soysauceの実データに合成シナリオを重ねる形で検証し、`ev-thailand-2026`への直接適用は
Phase 6に送った（§1.2、下記）。

既存A系統4モジュールのうち、`transmission.py`は**追加のみ**（`unit_pnl()`本体無変更）、
`grid.py`の`evaluate_point()`のみ**改修**（「A系統無変更」原則の唯一の例外、設計書§3.4で
明示的にスコープイン）。`cost_block.py`・`analytics.py`・B系統は無変更。

- `wom/allocation/transmission.py`：`CostBlock`拡張 + `unit_pnl_at_quantity()`（新規）
- `wom/allocation/grid.py`：`evaluate_point()`の計算順序改修
- `wom/allocation/merit_order.py`：①を近視眼的なまま新機構に追随
- `tools/run_allocation_map.py`：`load_scenarios()`/`_blocks_for()`の配線
- `data/sample/soysauce-jpy-2027-alloc/ga_scenario_master.csv`：2列追加 + `s9_fta_cliff`シナリオ
- `tests/test_allocation_nonconcave.py`（新規、13テスト）

---

## 2. なぜ`ev-thailand-2026`を直接やらないか

3つの障害があった（設計書§1.2）：

1. `MARKETS`のハードコード（`grid.py`の定数を4モジュールが import）
2. `ga_*.csv`を持つのは`soysauce-jpy-2027-alloc`ただ1つ
3. **LC率閾値が現行モデルに存在しない**——`ev-thailand-2026`の`tariff_rate`は固定スカラーで、
   現行の伝達式は構造的に線形。residualは必ずゼロになり検証にならない

障害3が本丸。データ整備（障害1・2）を先にやっても、伝達式が線形のままではresidualが
ゼロで終わる。**Phase 5では障害3だけを先に片付け、検証台は既存のsoysauceを使う。**

---

## 3. cliff型で確定（TRQ型を不採用）

**cliff型**（配分量が閾値以上なら税率が丸ごと切り替わる）はFTA原産地規則そのもの——
「域内付加価値比率がX%を超えれば特恵税率、届かなければMFN税率」という実際の制度と構造が
一致する。

**TRQ型**（関税割当・超過分だけ税率が変わる）は農産物輸入枠のような別の制度で、通常
「枠内は低税率、枠を超えた分は高税率」＝量を増やすほど限界的に不利＝**凹方向**に効く。
検証したい非凹性（量を増やすほど有利）とは**逆方向**の現象であり、導入すると検証したい
ものを再現しない。cliff型一本で確定（TRQ型はスコープ外）。

---

## 4. `CostBlock`の後方互換な拡張

新しい概念を持ち込まず、既存の関税メカニズム（Step 3：`cb.tariff_rate × transfer_price_usd`）
をそのまま伸ばす。

```python
@dataclass(frozen=True)
class CostBlock:
    # ... 既存フィールドは無変更 ...
    tariff_rate: float
    tariff_rate_preferential: Optional[float] = None   # 閾値到達時の特恵税率
    preferential_threshold_lot: Optional[float] = None # 発動閾値（lot）

    def tariff_at(self, qty: float) -> float:
        if self.tariff_rate_preferential is None or self.preferential_threshold_lot is None:
            return self.tariff_rate
        return (self.tariff_rate_preferential
                if qty >= self.preferential_threshold_lot else self.tariff_rate)
```

両フィールドとも既定`None`なので、既存の呼び出し（soysauceの231点評価・Phase 4の回帰値・
golden）は一切影響を受けない。

`unit_pnl_at_quantity()`は`unit_pnl()`本体に手を入れず、薄いラッパーとして追加：

```python
def unit_pnl_at_quantity(cb, sc, qty, transfer_price_usd=DEFAULT_TRANSFER_PRICE_USD):
    rate = cb.tariff_at(qty)
    if rate == cb.tariff_rate:
        return unit_pnl(cb, sc, transfer_price_usd)       # 従来経路そのまま
    return unit_pnl(replace(cb, tariff_rate=rate), sc, transfer_price_usd)
```

`dataclasses.replace()`で税率だけ差し替えて既存`unit_pnl()`を呼ぶため、計算式を二重に
持たない。`unit_pnl()`の仕様が変わっても自動的に追随する。

---

## 5. `evaluate_point()`の改修 —「A系統無変更」の唯一の例外

現行実装（改修前）は「単価を数量より先に確定させる」順序だった：

```python
ue = {m: unit_pnl(blocks[m], sc, transfer_price_usd) for m in MARKETS}   # ← 単価が先
q  = {m: min(xi * cap, blocks[m].demand_qty) for m, xi in zip(MARKETS, x)}
```

**この計算順序そのものが非凹性を扱えない構造の根**であり、ここを触らずに実現するのは
原理的に不可能。改修は2行の順序入れ替えと単価取得関数の差し替えに限定した：

```python
q  = {m: min(xi * cap, blocks[m].demand_qty) for m, xi in zip(MARKETS, x)}   # ← 数量を先に
ue = {m: unit_pnl_at_quantity(blocks[m], sc, q[m], transfer_price_usd) for m in MARKETS}
```

**「A系統無変更」原則からの逸脱は`grid.py`の`evaluate_point()`内の数行に限定**。
`transmission.py`本体・`cost_block.py`・`analytics.py`は無変更を維持。

**確認**: cliff未設定のCostBlockでは、改修後の`evaluate_point()`が231点全点で
「数量に依存しない従来の`unit_pnl()`だけで独立に再計算した値」と厳密一致することを
`test_evaluate_point_unchanged_without_cliff`で固定した。Phase 4の回帰値
（格子最適132,133,072.5等）も1円も変わらないことを確認済み。

---

## 6. ①メリットオーダーは意図的に近視眼的なまま

①が「後で閾値を超えることを知っている」ような賢い計算をしてしまうと、検証したい
「貪欲法の限界」そのものが再現できなくなる。①は近視眼的でなければならない。

ただし「近視眼的」の意味には実装上の曖昧さがある。貪欲法は順位を決める時点ではその
市場への配分量は0だが、積んだ後に閾値を超えると事後的に単価が変わる。**順位付けに
使う単価と、利益計算に使う単価が食い違いうる。**

| 段階 | 使う単価 | 根拠 |
|---|---|---|
| **順位付け** | 配分量0における単価（`cb.tariff_rate`、特恵なし） | 貪欲法は決定時点で見えている値しか使えない。これが「近視眼的」の実体 |
| **配分量の決定** | （単価を使わない）`min(残能力, 需要)` | 従来どおり |
| **利益計算** | 実際の配分量に応じた単価（`tariff_at(allocated)`適用後） | 現実に発生する損益は実配分量で決まる。閾値をたまたま超えていれば特恵は実際に効く |

`build_allocation_merit_order()`の戻り値に`preferential`フィールドを追加：

```python
"preferential": {                     # cliff の発動状況（None なら cliff 設定なし）
    "US": {"threshold": 25000.0, "allocated": 16825.0,
           "triggered": False,        # 閾値に届いたか
           "rate_base": 0.125, "rate_preferential": 0.0,
           "margin_ranking": 1747.5,  # 順位付けに使った単価（図の高さ、R2）
           "margin_effective": 1747.5},  # 実配分量に応じた単価（利益計算）
},
```

**利益は`margin_effective`ベースで計算する**（`margin`＝ランキング単価ではない）。
cliff未設定・未発動なら両者は常に一致するため、Phase 4の回帰値は変わらない。

`test_merit_order_profit_uses_effective_margin`で、意図的に構成した合成データ
（近視眼的な配分がたまたま閾値を超えるケース）を使い、利益計算が実際に
`margin_effective`を使っていること（`margin`ではなく）を固定した。

---

## 7. シナリオ読込の配線（設計書との小さな乖離）

設計書§6.2は「`cost_block.py`の`derive_cost_blocks()`と`tools/run_allocation_map.py`の
`load_scenarios()`が2列を読む」としていたが、実際には**`derive_cost_blocks()`は
`ga_scenario_master.csv`を一切読まない**（シナリオ別の関税上書きは元々
`run_allocation_map.py`側の役割）。したがって**`cost_block.py`は無変更のまま、
`tools/run_allocation_map.py`のみ改修**した——設計書との差分だが、既存コード構造に
忠実な実装であり、動作・検証結果に影響はない。

```python
def load_scenarios(model_dir: str) -> List[dict]:
    ...
    tariff_preferential: Dict[str, float] = {}
    preferential_threshold: Dict[str, float] = {}
    for r in rs:
        if r["quarter"] != q0:
            continue
        rate_str = (r.get("tariff_rate_preferential") or "").strip()
        thr_str = (r.get("preferential_threshold_lot") or "").strip()
        if rate_str and thr_str:
            tariff_preferential[r["market"]] = float(rate_str)
            preferential_threshold[r["market"]] = float(thr_str)
    ...
```

`r.get(...)`を使うため、**2列が存在しない古いCSVでも例外にならない**
（`test_scenario_csv_missing_columns_ok`で固定）。

`_blocks_for()`は2つの新規オプション引数（既定`None`）を追加し、既存呼び出し
（`tools/plot_allocation_map.py`の2引数呼び出し等）は無変更で動作する。

---

## 8. 合成シナリオ`s9_fta_cliff`とcap_wk=500（R1・R3）

### 8.1 cap_wk=800では成立しない（設計の要）

`EU+US = 70,351 < cap(800) = 83,200`のため、上位2市場（EU・US）は必ずフル供給される。
閾値を置いても葛藤が生まれない。限界市場はJPだが、JPの関税は既に0.0で下げ代がない。

**関税の効き幅**: transfer_price 17.6 USD × fx 150 = 関税率1.0あたり2,640 JPY/lot。
現実的な優遇幅（US 0.125→0.000 = +330.0 JPY/lot）ではこの構造を動かせない。

### 8.2 cap_wk=500に絞って解決

`soysauce-jpy-2027-alloc`を作った際の前例（CLAUDE.md：能力1500では最適点が台地28点で
不定になるため800に絞った）と同型の操作。`cap_wk=500`（cap=52,000、充足率51.7%）で
US が限界市場になり、特恵が発動するとUSの単価2,077.5がEUの1,831.5を上回り優先順位が
逆転する条件が成立する。

`cap_wk`は`ga_scenario_master.csv`に持ち込まず、**CLI/テストで明示的に渡す方式**とした
（R1確定）。CSVに列を足すと既存シナリオ全行を触ることになり、「既存行を変更しない」
（設計書§4.2）と衝突するため。

### 8.3 閾値T=25,000（R3）

貪欲解16,825の約1.5倍・US需要35,176の約71%という「明確に届かない」水準として選定。
T=20,000/30,000でも結果の性質は同じ（設計書§9のR3で確認済み）。

---

## 9. 検証結果（実データ・設計書§2の値と完全一致）

```python
# s1_base / cap_wk=800（Phase 4回帰、1円も変わらないことを確認）
mo["lambda"] == 750.0
mo["x"] == {"JP": 0.1544, "US": 0.4228, "EU": 0.4228}
mo["profit"] == 135_529_822.5
mo["preferential"] is None
grid_best == 132_133_072.5

# s9_fta_cliff / cap_wk=500（非凹性の検証）
mo["profit"] == 93_824_700.0          # US=16,825(triggered=False), EU=35,175
mo["lambda"] == 1747.5                # marginal_market = US
grid_best == 103_552_800.0            # x=(0.00, 0.65, 0.35), idle=0.0

cmp["gap_amt"] == -9_728_100.0
cmp["expected_gap_from_grid_resolution"] == 0.0     # grid_idle=0 のため
cmp["structural_residual"] == -9_728_100.0           # 負
cmp["attributable_to_grid_resolution"] is False
```

手計算による真の連続最適（設計書§2.3）：US 35,176 / EU 16,824 / JP 0、
profit=103,891,296。構造由来の取りこぼし＝10,066,596に対し、
`|structural_residual|`（9,728,100）は**96.6%**を捉える——下界として機能する。

---

## 10. `residual`の符号別の意味づけ（Phase 4設計書§3.5.3 rev.3で訂正）

Phase 4初版は「非凹ケースでは`gap_amt > expected_gap`となり、超過分が構造由来として
切り出せる」としていたが、**符号が逆だった**。

理屈：非凹だと貪欲法（メリットオーダー）が最適を外すので`mo_profit`が**下がる**。
`gap_amt = mo_profit − grid_best`は縮み、多くの場合は負になる。一方
`expected_gap = grid_idle × λ`は格子最適点の性質だけで決まるので影響を受けない。
よって`residual`は**負**に振れる。

| `residual` | 意味 |
|---|---|
| ≈ 0 | 乖離は格子解像度で説明できる（線形・凹なケース。soysauce s1_base） |
| **< 0** | **メリットオーダーが真の最適を外している＝非凹性の証拠。絶対値は取りこぼし量の下界** |
| > 0 | 想定外（要調査） |

判定式`abs(structural_residual) <= abs_tol`は符号によらずFalseを返すため
**実装の動作は正しかった**。訂正するのは意味づけのみであり、
**`compare_with_grid()`の実装変更は不要**だった。

**分解の精度が非凹ケースで落ちる**ことも判明：非凹だと格子最適点が能力を使い切る
（`grid_idle=0`）ため`expected_gap=0`となり、格子誤差の分だけ`|residual|`が
構造由来を過小評価する（この例では96.6%）。したがって`residual`は「厳密な分解」
ではなく、**符号を非凹性の指標、絶対値を取りこぼし量の下界**として使う設計。

---

## 11. テスト結果

```
tests/test_allocation_nonconcave.py（新規）: 13 passed
  - 後方互換（4件）: tariff_at() / unit_pnl_at_quantity() / Phase4回帰 / evaluate_point()不変
  - cliffの動作（4件）: 閾値切替 / 順位逆転の機序 / ①の近視眼性 / 利益計算のeffective margin使用
  - 構造的乖離の検出（3件）: s9回帰値 / residual負 / 下界としての精度
  - シナリオ読込（2件）: cliff列の読込 / 古いCSVでの後方互換

A系統関連テスト全体: 75 passed（既存62 + 新規13）
リポジトリ全体: 370 passed（既存357 + 新規13、設計書の目標値と一致）
golden 13ケース: 全PASS（不変）
```

**副次的な修正**：`s9_fta_cliff`追加で定常シナリオ数が7→8になったため、
`tests/test_allocation_plot.py::test_plot_each_scenario`（7→8）と
`tests/test_allocation_cli.py::test_profit_surface_row_count`（7×231→8×231）の
ハードコード値を更新した——設計変更ではなく、シナリオ追加の自然な帰結。

---

## 12. レビュー事項R1-R4（設計書§9）

いずれも設計書の推奨どおり確定・実装した。

| # | 内容 | 決定 |
|---|---|---|
| R1 | `cap_wk=500`をCSVでなくCLI/テストで渡す方式 | ✅ 確定・実装 |
| R2 | ①の図のブロック高さを「順位付けに使った単価」で描く | ✅ 確定（本Phaseはロジックのみ、描画自体はPhase 4のまま） |
| R3 | 閾値T=25,000 | ✅ 確定・実装 |
| R4 | `evaluate_point()`改修を「A系統無変更の例外」として容認 | ✅ 確定・実装 |

---

## 13. 未対応・Phase 6送り

- `MARKETS`のハードコード解除（`grid.py`の定数を外部から与える形に。`analytics.py`/
  `merit_order.py`/`regime_map.py`の4モジュールが import しているため影響範囲の確認が要る）
- `ev-thailand-2026`用`ga_*.csv`3本（`ga_market_aggregation`/`ga_scenario_master`/
  `ga_fx_policy_master`）の新規作成と、実ケースでの`structural_residual`検証
  （LC率閾値のモデル化はPhase 5で解決済み——`tariff_rate_preferential` +
  `preferential_threshold_lot`をそのまま使える）
- ③Pareto＋平行座標（配分版）、④階層化三角図（Phase 4からの持ち越し）
