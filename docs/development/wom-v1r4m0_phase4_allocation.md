# wom-v1r4m0 Phase 4: 生産配分の利益地形図 — メリットオーダー曲線とレジーム地図 実装ガイド

**設計正典**: `requests/Phase4_DesignMD_AllocationMeritRegime.md`
**実装責任**: Code君　**設計責任**: Claude君
**実装日**: 2026年9月8日

---

## 1. 概要

Phase 1-3（B系統 `wom/visualization/`・週次「どのサプライヤーから調達するか」）とは
**対象問題が異なる**A系統（`wom/allocation/`・`ask_global_allocation`・年次「どの市場に
何個供給するか」）向けに、メリットオーダー曲線とレジーム地図を実装した。

| | Phase 3（済） | Phase 4（本文書） |
|---|---|---|
| 系統 | B系統 | **A系統** |
| 対象問題 | 週次：どのサプライヤーからいくら調達するか | **年次：どの市場に何個供給するか** |
| 希少資源 | （なし） | **醸造能力**（cap_wk × weeks） |
| 並び順 | 単価**昇順** | **単位マージン降順** |
| 交点の意味 | 限界サプライヤーの単価 | **能力のシャドープライス λ** |

既存 A系統4モジュール（`transmission.py`/`cost_block.py`/`grid.py`/`analytics.py`）・
B系統（`wom/visualization/*`）とも**無変更**。禁足コア無接触、golden 13ケース不変。

- `wom/allocation/merit_order.py`（新規）— `build_allocation_merit_order()` / `compare_with_grid()`
- `wom/allocation/regime_map.py`（新規）— `scan_regime_grid()`
- `tools/plot_allocation_merit_regime.py`（新規）— 3描画関数 + CLI
- `tests/test_allocation_merit_order.py`（新規、8テスト）
- `tests/test_allocation_regime_map.py`（新規、9テスト＝ロジック5＋描画スモーク4）

---

## 2. ① メリットオーダー曲線（配分版）

### 2.1 `build_allocation_merit_order(blocks, sc, cap_wk, *, transfer_price_usd, weeks) -> dict`

市場を単位マージン**降順**に積む。`unit_pnl()`で各市場のマージンを計算し、正のものだけを
対象に、能力（`cap = cap_wk × weeks`）が尽きるまで需要（`demand_qty`）を割り当てる。

```
soysauce-jpy-2027-alloc（FX150・原料$6・cap=800×104=83,200 lot）:
  EU (margin=1831.5, demand=35175) → full  → cumulative 35,175
  US (margin=1747.5, demand=35176) → full  → cumulative 70,351
  JP (margin=750.0,  demand=30150) → partial(12,849) → cumulative 83,200 ← 能力線

λ = 750.0 JPY/lot（限界市場 = JP）
x = (JP 0.1544, US 0.4228, EU 0.4228)
profit = 135,529,822.5 JPY
```

### 2.2 R1確定：負マージン市場の除外

FX200・原料$8シナリオではJPのマージンが−105.0 JPY/lotになる。負マージンの市場は
**能力があっても供給すべきでない**ため、メリットオーダーの積み上げ対象から除外する
（`excluded`リストに列挙、`excluded_margins`にマージン値も保持——描画で負側にハッチ矩形
を描くために追加したフィールド。設計書の`"excluded": []`の例には明示されていないが、
既存の`excluded`（市場名のリスト）とは別に追加した後方互換な拡張）。

**この非対称は意図的**：`evaluate_point()`（格子スキャン）は符号を見ずに`min(x·cap, D)`で
配分するため、負マージン市場に配分した格子点も評価対象に含まれる。これは格子スキャンの
仕様として正しい（面を出すのが目的で最適化はしない）ので変更しないが、①は「あるべき
配分」を示す図なので負マージンを除外する——両者の扱いが違うこと自体が設計意図。

### 2.3 `compare_with_grid(mo, surface, *, abs_tol=1.0) -> dict`

メリットオーダー連続解と231点格子最適（`best_point(surface)`）の乖離を定量化する。

```
soysauce: merit_order_profit=135,529,822.5 / grid_best_profit=132,133,072.5
          gap_amt=3,396,750.0 / gap_pct=+2.57%
```

**この乖離はsoysauceでは格子解像度の誤差であって、非凹性等の構造的発見ではない**
（設計書§2.4）。soysauceの利益関数は分離可能・区分線形（各市場の利益が
`min(x·cap, D) × margin`で需要上限に頭打ちするだけ、関税階段・ルート固定費・MOQ・
ローカルコンテンツ要件を持たない）ため、均等限界原理が厳密に成立し、メリットオーダーは
連続最適の厳密解になる。

**既存のCLAUDE.md回帰値「s1=132.1M」はδ=0.05格子上の最大であって連続最適ではない**
（R4、CLAUDE.md L1311に注記追加済み）。値そのものは変更していない。

### 2.4 R2確定 → **G2で全面差し替え（rev.2）**：乖離の帰属判定

**初版の方式（廃止済み）**：メリットオーダー解`x_mo`の各成分をδの倍数に切り上げ・
切り捨てした全組合せ（2^3=8通り、単体制約Σx=1を満たすもののみ）のうち、格子上に
実在する点の最良利益`rounded_best_profit`を求め、格子最適`grid_best_profit`と相対誤差
`tol`で比較する方式だった。soysauceで実測すると`rounded_best_profit=131,939,812.5`
vs `grid_best_profit=132,133,072.5`＝**相対誤差0.146%**で厳密一致せず、恣意的な
`tol=0.005`（0.5%）でしか"True"判定できなかった。

**原因（設計書§3.5の欠陥、`request_fix_phase4_gap_attribution.md` G2で特定）**：
格子最適点`x=(0.10, 0.45, 0.45)`のJP成分0.10は、`x_mo`のJP成分0.1544を独立に
丸めて到達できる範囲（{0.15, 0.20}）に含まれない。US/EUを需要天井（0.4228）超の
0.45へ切り上げると、単体制約Σx=1によりJPが0.10へ「押し出される」——この押し出しは
成分ごとの独立な丸めでは表現できなかった。

**新方式（idle×λ、現行）**：格子最適点の遊休能力`grid_idle`を限界市場（マージンλ）に
回したときの利益増分`expected_gap = grid_idle × lambda`と、実測乖離`gap_amt`を比較する。

```python
marginal_unmet = grid_pt["unmet"][marginal] if marginal is not None else 0.0
absorbable = (marginal is not None) and (marginal_unmet >= grid_idle)
expected_gap = grid_idle * lam
structural_residual = gap_amt - expected_gap
attributable = absorbable and (abs(structural_residual) <= abs_tol)
```

**実測結果**: soysauceで`grid_idle=4,529`・`lambda=750.0`・
`expected_gap=4,529×750.0=3,396,750.0`——実測乖離`gap_amt=3,396,750.0`と
**厳密一致（差0.000000 JPY）**。恣意的な閾値が不要になり、`abs_tol`は数値誤差
（既定1.0 JPY）のみを吸収する。

**Phase 5への意義**：`structural_residual`はそのまま「格子解像度では説明できない
構造由来の乖離量」になる。`ev-thailand-2026`（LC率閾値で非凹）に適用したとき、
`structural_residual`が有意に非ゼロであれば、それが「構造的発見」の定量値になる
——旧方式では相対誤差の閾値に埋もれて検出できなかったはずのシグナルが、新方式では
直接読み取れる設計になっている。

### 2.5 Before/After（`plot_allocation_merit_shift`）

既存`switching_points()`が記録する切替点（117円/119円）をまたぐFX=115→125で検証。

```
FX=115: order = JP > EU > US（λ_before=972.2, marginal=JP）
FX=125: order = EU > US > JP（λ_after=977.5,  marginal=JP）
Rank changes: EU(#2→#1), US(#3→#2), JP(#1→#3)
```

---

## 3. ② レジーム地図（配分版）

### 3.1 `scan_regime_grid(blocks, axis_x, x_values, axis_y, y_values, ...) -> dict`

配分空間ではなく**外部環境パラメータ空間の2次元平面**を走査し、各点を
`market_ranking()`が返す市場優先順位（3市場なら最大3!=6通り）で塗り分ける。
新しい数学は要らず、既存`market_ranking()`を2次元グリッドで呼ぶだけ。

軸は`"fx_usd"` / `"material_usd"` / `"tariff_rate:<市場>"`から選べる。後者は
`CostBlock.tariff_rate`を`dataclasses.replace()`で上書きして評価する。

### 3.2 最重要の回帰テスト：`switching_points()`との整合性

`material_usd=6.0`の水平断面が、既存`analytics.switching_points()`の切替点
（**117円/119円**）を完全再現することを確認した
（`test_regime_map_reproduces_switching_points`）。②が既存のV&V方法論
（決定反転テスト）と**同じ数学的対象**を見ていることの証明であり、設計書が
「新しい数学は要らない」と述べている通りであることが実測でも裏付けられた。

### 3.3 R3確定：既定軸

既定は`(fx_usd, material_usd)`——`interaction()`の基準（150, 6.0）・ショック
（200, 8.0）と同一平面であり、確定済みの回帰値（base −8.3M/−40.2%等）と直接照合
できるため。`(fx_usd, tariff_rate:US)`も同様に描ける（`alloc_regime_map_tariff.png`）。

### 3.4 負マージン領域のハッチ表示

`negative_margin_mask`（①の`excluded`と同じ判定基準＝margin<=0）を`contourf`で
斜線ハッチ表示。実データで確認：FX200・材料$8の「shock」点は`(fx_usd, material_usd)`
相図上でJPが負マージンになる領域内に正しく位置していた。

---

## 4. 描画層：`tools/plot_allocation_merit_regime.py`

Phase 3の`tools/plot_merit_order_suite.py`は**流用せず別ファイル**にした（設計書§5.2）。
対象問題・並び順・交点の意味が全て異なるため、同居させると読み手が混乱すると判断された。

### 4.1 CLI

```bash
python -m tools.plot_allocation_merit_regime \
    --model-dir data/sample/soysauce-jpy-2027-alloc --cap-wk 800 --scenario s1_base \
    --out output/allocation/

python -m tools.plot_allocation_merit_regime --model-dir <dir> --demo
```

`--demo`は`cap_wk=800`・`scenario=s1_base`に固定し、決定的に4枚を生成する
（`--model-dir`は必須のまま——A系統は実CSVから原価ブロックを導出する設計のため、
Phase 3の`DEMO_SUPPLIERS`のような純粋合成データは持たない）。

シナリオ読込は`tools/run_allocation_map.py`の`load_scenarios()` / `_blocks_for()`を
そのまま再利用し、ロジックの重複を避けた。

### 4.2 生成される図

| ファイル名 | 内容 |
|---|---|
| `alloc_merit_order.png` | ①基準シナリオのメリットオーダー曲線（グリッド比較注記つき） |
| `alloc_merit_shift.png` | ①FX=115→125（切替点117円をまたぐ）のBefore/After |
| `alloc_regime_map.png` | ②fx×materialの相図（既定軸） |
| `alloc_regime_map_tariff.png` | ②fx×US関税率の相図 |

---

## 5. テスト結果（初版・G1-G4修正前の時点。最新は §7 参照）

```
tests/test_allocation_merit_order.py  : 8 passed
tests/test_allocation_regime_map.py   : 9 passed
リポジトリ全体                         : 356 passed（既存339 + 新規17、回帰なし）
golden 13ケース                        : 全PASS（単独実行で確認）
```

`--demo`生成4枚を目視確認：①メリットオーダー曲線（EU/US濃色フル・JP能力線で分割・
λ=750水平線）、①Before/After（FX115→125でJP最優先→最劣後に反転）、②fx×material相図
（117/119円の境界線・shock点(200,8)が負マージン領域内）、②fx×tariff相図（US関税を
下げるほどUS優先になる境界）——いずれも設計意図通り。

---

## 6. 未対応・Phase 5送り

- **③ Pareto＋平行座標（配分版）**：目的軸をCost/Quality/LTから利益×ロバストネス
  （`robust_point()`）へ。share軸は市場配分比率（Phase 3 §5.2.1の和集合方式を流用可能）
- **④ 階層化三角図**：既存`tools/plot_allocation_map.py`の三角図を`oil-global-2027`
  （日本／欧州／米州×Local/Import）に適用
- **N≥4市場への拡張**：①②はN非依存なので③④より先に拡げられる
- **`ev-thailand-2026`（LC率閾値で関税が跳ぶ非凹ケース）への適用**：`compare_with_grid()`
  が返す`structural_residual`（idle×λ方式、G2で導入）がそのまま構造由来の乖離量になる
  はず（§2.4参照）
- **`AllocationMapPanel`のGUI組込**（A系統の積み残し）

---

## 7. Phase 4 修正（G1-G4、完了、2026-09-08）

**設計文書**: `requests/request_fix_phase4_gap_attribution.md`。`--demo`出力の目視QA後の
4点修正。詳細はCLAUDE.mdの「Phase 4 修正」節、および本文書§2.3/2.4の更新箇所を参照。

- **G1**：`.gitignore`に`out/`を追加（A系統`plot_allocation_map.py`の既定出力先がコミット
  対象に入る漏れがあった、Phase 4以前から潜在）
- **G2**：`compare_with_grid()`の帰属判定を「idle×λ」方式に全面差し替え（§2.4更新箇所参照）
- **G3**：`plot_allocation_merit_order()`の注記を軸の下へ移動（単位マージン降順のため左上が
  構造的に埋まる）。実装時に注記が図の右端からはみ出す表示崩れも追加で発見・修正
- **G4**：`plot_allocation_merit_shift()`の凡例を`lower left`へ（G3と同じ理由）

```
リポジトリ全体: 357 passed（既存356 + 新規1）
```

`--demo`再生成4枚を目視確認：①注記4行が全て軸下で判読可能、①Before/Afterの凡例が
After曲線と重ならず、②2枚はピクセル的に無変化——いずれも意図通り。
