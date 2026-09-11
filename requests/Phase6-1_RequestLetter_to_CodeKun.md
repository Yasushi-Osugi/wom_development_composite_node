# Phase 6-1 実装 Request Letter — `true_optimum` の実計算化（`structural_optimality_gap`）

**宛先**: Code君
**作成日**: 2026年9月11日
**担当**: Claude君（設計・仕様）→ 大杉さん（レビュー）→ Code君（実装）
**優先度**: HIGH（小規模・自己完結。Phase 6 の他ステップの前提）
**ブランチ**: `wom-v1r4m0`
**設計正典**: `requests/Phase6_DesignMD_NMarketHierarchy.md` §3（本書は §3 を実装仕様まで落としたもの）
**前提**: Phase 5 完了（`6936c05`、370件全PASS）

---

## 概要

`tools/demo_allocation_nonconcave.py:98` の

```python
true_optimum = 103_881_758.0  # 設計書の手計算値（コードでは計算しない参照値）
```

を**実行時計算に置き換える**。これにより `structural_optimality_gap`（真の最適 − 貪欲法の解＝構造由来の取りこぼし）が任意のケースで自動算出できるようになる。

現在 `compare_with_grid()` が返している `structural_residual` は、この取りこぼしの**下界**（s9 実測で 96.7% を覆う）であり、真の値そのものではない。本 Phase でその真の値が手に入る。

**対象ファイル**:

| ファイル | 扱い |
|---|---|
| `wom/allocation/merit_order.py` | **関数追加＋既存関数への返却フィールド追加のみ**（既存キーの削除・改名・値の変更は一切なし） |
| `tools/demo_allocation_nonconcave.py` | ハードコード撤去、実計算値の表示に変更 |
| `tests/test_allocation_nonconcave.py` | テスト**追記**（既存4件は不変） |
| 上記以外 | **無変更**（`grid.py` / `transmission.py` / `analytics.py` / `regime_map.py` / B系統 / 禁足コア） |

---

## ⚠️ 実装前に必ず読むこと — 絶対制約

Phase 3/4/5 から継承。内容は同一なので要点のみ。

- **C1**: matplotlib のみ（本 Phase では描画なし）。**C2**: 新規依存パッケージなし（標準ライブラリ `itertools` / `dataclasses` のみ）
- **C3**: （描画なしのため該当なし）。**C4**: 図中テキスト英語（該当なし）
- **C5**: 返却は Dict。**C6**: 禁足コア6ファイルに一切触れない
- **C7**: **乱数を使わない。** 列挙順・返却順は決定的であること
- **C8（本 Phase 固有）**: `compare_with_grid()` の**既存返却キーの値を1円たりとも変えない**。追加のみ

---

## V1: `true_continuous_optimum()` の新規実装

### V1.1 配置とシグネチャ

`wom/allocation/merit_order.py` に追加する。

```python
def true_continuous_optimum(
    blocks: Dict[str, CostBlock],
    sc: Scenario,
    cap_wk: float,
    *,
    transfer_price_usd: float = DEFAULT_TRANSFER_PRICE_USD,
    weeks: int = WEEKS,
) -> dict:
    """cliff（数量依存関税）の on/off を全列挙し、各ケースを線形問題として
    厳密に解いて、真の連続最適解を返す。

    利益関数は cliff の on/off を固定すれば区間ごとに線形・分離可能になる。
    したがって「どの市場が特恵を発動しているか」の組合せを全列挙し、各組合せ
    の中で厳密解を求め、その最大値が真の連続最適である。
    """
```

引数の並びは `build_allocation_merit_order()` と揃えること（呼び出し側の混乱を防ぐため）。

### V1.2 アルゴリズム（**この節が本 Phase の中核。厳密に従うこと**）

**手順1: cliff を持つ市場の集合 K を求める**

```python
K = [m for m in MARKETS
     if blocks[m].tariff_rate_preferential is not None
     and blocks[m].preferential_threshold_lot is not None]
```

`K` の順序は `MARKETS` の順序に従う（決定的であること）。

**手順2: 部分集合 S ⊆ K を全列挙する**

`itertools.combinations` を使い、`|S| = 0, 1, ..., |K|` の順に列挙する。`S` は「**その市場が特恵を発動していると仮定するケース**」を表す。ケース数は `2^|K|`。

**性能ガード**: `len(K) > 12` のときは計算に入る前に `ValueError` を投げること（`2^13 = 8192` ケース以上は実務ケースとして想定していない。「走らせたら帰ってこない」を作らない）。

**手順3: 各ケース S で、下界・上界・税率を固定する**

これが本設計の要である。**単に税率を固定して解いてから整合性を検査するのでは不十分**で、閾値そのものを制約として解かなければならない。

```
for m in MARKETS:
    if m in S:                      # 特恵を発動していると仮定
        rate[m]  = blocks[m].tariff_rate_preferential
        lower[m] = blocks[m].preferential_threshold_lot   # ← 下界制約
        upper[m] = blocks[m].demand_qty
    elif m in K:                    # cliff を持つが発動していないと仮定
        rate[m]  = blocks[m].tariff_rate
        lower[m] = 0.0
        upper[m] = min(blocks[m].demand_qty,
                       blocks[m].preferential_threshold_lot)   # ← 上界制約
    else:                           # cliff を持たない市場
        rate[m]  = blocks[m].tariff_rate
        lower[m] = 0.0
        upper[m] = blocks[m].demand_qty
```

**なぜ下界制約が必要か（実装者への説明）**: 「US が特恵を発動している」ケースの真の最適は、しばしば「US をちょうど閾値まで積む」点にある。税率だけ固定して素直に貪欲に解くと、US の順位によっては閾値未満で止まり、そのケースを「矛盾」として棄却してしまう。**本来そのケースで最適だった解を取り逃す。** 下界制約として持たせれば、この取りこぼしが構造的に起きない。

**境界（`q == threshold`）の扱い**: 発動していないケースの上界に閉区間 `threshold` を使ってよい。ちょうど閾値の点は本来「発動する」側に属するが、その点は発動ケースでも評価され、特恵税率のほうが利益が高いため、最大値を取る段階で正しい側が選ばれる。取りこぼしは生じない。

**手順4: ケース内を厳密に解く（線形・分離可能）**

税率が固定されているので単位マージンは配分量によらず一定。したがって「容量制約＋各市場の上下界」の下での線形計画になり、貪欲法が厳密解を与える。

```
cap = cap_wk * weeks

# (a) 下界を先に確保する
q = dict(lower)
if sum(q.values()) > cap + 1e-9:
    → このケースは実行不可能。棄却して次へ
remaining = cap - sum(q.values())

# (b) 残余容量を、単位マージン降順に、上界まで詰める
margins[m] = 固定税率 rate[m] のもとでの単位マージン
順序 = margins 降順（同値のときは MARKETS の順序で安定ソート）
for m in 順序:
    if margins[m] <= 0: continue          # 負マージンには自発的に配分しない
    add = min(upper[m] - q[m], remaining)
    q[m] += add; remaining -= add
    if remaining <= 1e-9: break

# (c) 利益を計算する
profit = Σ_m q[m] × margins[m]
```

**単位マージンの求め方**: `dataclasses.replace` で `tariff_rate=rate[m]`、`tariff_rate_preferential=None`、`preferential_threshold_lot=None` とした一時 `CostBlock` を作り、既存の `unit_pnl()` を呼ぶこと。**税率を反映した粗利の計算式を書き直さない**（Phase 5 で `unit_pnl_at_quantity()` を `replace` で実装したのと同じ方針。式の二重定義を作らない）。

cliff フィールドを `None` にするのは、`unit_pnl_at_quantity()` と `unit_pnl()` が一致する状態にして、税率が確実に `rate[m]` で固定されるようにするため。

**手順5: 実行可能なケースの最大値を返す**

手順3の上下界により、`S` の仮定と結果 `q` は構造的に矛盾しない（`m in S` なら `q[m] >= threshold`、`m in K\S` なら `q[m] <= threshold`）。したがって手順4を通ったケースはすべて有効。手順4(a) で棄却されたケースのみ除外する。

### V1.3 返却仕様

```python
{
    "profit": 103881758.0,              # 真の連続最適利益（P_opt）
    "x": {"JP": 0.000..., "US": 0.676..., "EU": 0.323...},   # 配分比率（q / cap）
    "q": {"JP": 7.0, "US": 35168.0, "EU": 16825.0},          # 配分量（lot）
    "active_cliffs": ["US"],            # 最適ケースで発動している特恵の一覧（MARKETS 順）
    "cases_evaluated": 2,               # 列挙したケース数（= 2^|K|）
    "cases_feasible": 2,                # 手順4(a) を通ったケース数
    "idle": 0.0,                        # cap − Σq
}
```

- `x` は `q[m] / cap`。`cap` が 0 のときは全て 0.0 とする
- cliff が1つも無いケース（`K` が空）では `cases_evaluated = 1`、`active_cliffs = []` となり、結果は連続メリットオーダー解と**厳密に一致**するはずである（V4.4 のテストで担保）

---

## V2: `compare_with_grid()` への返却フィールド追加

### V2.1 シグネチャの変更

```python
def compare_with_grid(
    mo: dict,
    surface: List[dict],
    *,
    abs_tol: float = 1.0,
    true_optimum: Optional[dict] = None,   # ← 追加。true_continuous_optimum() の戻り値
) -> dict:
```

**既定 `None`（＝渡さない）のとき、返却は現在と完全に同一であること。** 既存の呼び出し（`tools/plot_allocation_merit_regime.py` など）を一切壊さないため。

### V2.2 追加するキー

`true_optimum` が渡されたときのみ、以下の4キーを**追加**する（渡されないときは4キーとも `None`）。

| キー | 定義 | s9 での期待値 |
|---|---|---|
| `true_optimum` | `true_optimum["profit"]` = `P_opt` | 103,881,758 近傍（V4.1 参照） |
| `structural_optimality_gap` | `P_opt − mo["profit"]` = `P_opt − P_greedy` | 10,057,058 近傍 |
| `grid_resolution_error` | `P_opt − grid_best_profit` = `P_opt − P_grid` | 328,958 近傍 |
| `residual_coverage` | `abs(structural_residual) / structural_optimality_gap` | 0.967 |

**`residual_coverage` のゼロ除算**: `structural_optimality_gap` が 0（＝線形ケース）のときは **`None` を返す**。0.0 でも `nan` でもなく `None`。「割り算が定義できない」ことと「覆っている割合が 0」は意味が違うため。

**既存キーは1つも削除・改名・変更しないこと。**

---

## V3: `tools/demo_allocation_nonconcave.py` の更新

L98 のハードコードを撤去し、`true_continuous_optimum()` の呼び出しに置き換える。

出力例（この形に揃えること。数値は実行結果に従う）:

```
  --- 真の連続最適との比較（実計算） ---
  真の連続最適 profit: 103,881,758.0
    配分: JP=7  US=35,168  EU=16,825
    発動している特恵: ['US']
    評価したケース数: 2 （実行可能: 2）
  構造由来の取りこぼし (structural_optimality_gap): 10,057,058.0
  格子解像度の誤差 (grid_resolution_error):            328,958.0
  |structural_residual| / 取りこぼし = 96.7%  （residual は下界として機能）
```

**「設計書の手計算値」という文言はすべて削除すること。** 実計算になったので、その断り書きは誤りになる。

`s1_base`（線形）側の出力にも同じブロックを追加し、`structural_optimality_gap = 0`、`residual_coverage = None` が表示されること（`None` は `—` と表示してよい）。

---

## V4: テスト仕様（`tests/test_allocation_nonconcave.py` に**追記**、7件）

既存4件は**一切変更しない**。

### V4.1 `test_true_optimum_s9_matches_design_value`（**期待値の扱いに注意**）

`s9_fta_cliff` で `true_continuous_optimum()["profit"]` を求め、設計書 §2.3 の手計算値 **103,881,758.0** と比較する。

**許容差は ±10,000 JPY とすること。** 理由: 設計書の値は需要按分を概算で追った手計算であり（CLAUDE.md L1812 に経緯を記録済み）、`derive_cost_blocks()` が返す実際の需要量・単価とは末尾が一致しない可能性がある。厳密一致を要求すると、正しい実装が落ちる。

**実装後の申し送り（重要）**: 実行して得られた値を大杉さんに報告すること。その値を**新しい回帰値として確定**し、CLAUDE.md と設計書 §3.5 に記録したうえで、本テストの許容差を ±1 JPY に締める（この締め直しは Code君ではなく、大杉さん承認後に行う）。

### V4.2 `test_true_optimum_case_a_matches_greedy`（**厳密一致・最重要**）

ケース `S = {}`（US が特恵を発動していない）を単独で解いた利益が、**93,824,700.0 と ±1 JPY で一致**すること。

この値は①メリットオーダーの実測値と厳密一致することが Phase 5 で確認済みであり、**ケース内ソルバ（手順4）が正しいことの直接の証拠**になる。テストのために内部ケースを取り出せるよう、`true_continuous_optimum()` に `_return_all_cases: bool = False`（既定 False）の内部引数を設けてよい。公開 API には出さないこと。

### V4.3 `test_true_optimum_respects_threshold_lower_bound`（**設計の要**）

閾値制約が binding になる合成ケースを作り、下界制約を持たない素朴な解法では取り逃す解が、正しく拾えることを確認する。

作り方: `s9_fta_cliff` をベースに、US の特恵マージンを EU の基本マージンより**わずかに低く**設定する（例: 特恵税率を 0.000 ではなく EU マージンをわずかに下回る値にする）。こうすると「US が特恵を発動する」ケースでも US の順位が EU より下になり、下界制約が無ければ US は閾値未満で止まる。

このとき:
- `q[US] >= preferential_threshold_lot` が成立していること（下界が効いている）
- `active_cliffs` に `"US"` が含まれるケースが `cases_feasible` に数えられていること

### V4.4 `test_true_optimum_equals_greedy_when_linear`（**強いテスト**）

`s1_base`（cliff なし）で:

```
true_continuous_optimum()["profit"] == mo["profit"] == 135,529,822.5   （±1 JPY）
cases_evaluated == 1
active_cliffs == []
```

cliff が無ければ利益関数は線形・分離可能で、貪欲法が厳密解を与える。**この一致は、列挙・上下界・ソルバの全経路を既知の正確な値で検証する。**

### V4.5 `test_true_optimum_is_upper_bound`

`s1_base` と `s9_fta_cliff` の両方で:

```
true_optimum >= grid_best_profit      （格子は連続空間の部分集合）
true_optimum >= mo["profit"]          （貪欲法は最適を超えない）
```

この2本が `structural_residual` が下界であることの根拠であり、崩れたら実装が誤っている。

### V4.6 `test_compare_with_grid_backward_compatible`

`compare_with_grid(mo, surface)`（`true_optimum` を渡さない）の返却が、Phase 5 時点の全キー・全値と**厳密に一致**すること。追加4キーが `None` であること。

### V4.7 `test_residual_coverage_none_when_linear`

`s1_base` で `structural_optimality_gap == 0.0`（±1 JPY）かつ `residual_coverage is None` であること。ゼロ除算も `nan` も発生しないこと。

### 補足: 恒等式のテストを置かない理由

設計書 §3.5 に

```
|structural_residual| + grid_resolution_error = structural_optimality_gap
```

と書いたが、`grid_idle = 0`（＝`expected_gap = 0`）の場合、この式は両辺から `true_optimum` が相殺されて**代数的に恒真**になる。実装の誤りを検出できないため、テストとしては置かない。**V4.2 と V4.4 が、実際に値を検証する本体である。**

---

## 成功基準

- [ ] `true_continuous_optimum()` が実装され、`s9_fta_cliff` で 103,881,758 ± 10,000 JPY を返す
- [ ] ケースA（特恵未発動）が 93,824,700.0 と ±1 JPY で一致する
- [ ] 閾値の下界制約が効いており、binding なケースで解を取り逃さない
- [ ] `s1_base`（線形）で `true_optimum == P_greedy == 135,529,822.5`（±1 JPY）
- [ ] `compare_with_grid()` を `true_optimum` なしで呼んだとき、返却が Phase 5 と完全に同一
- [ ] `residual_coverage` が線形ケースで `None`（ゼロ除算なし）
- [ ] `len(K) > 12` で計算前に `ValueError`
- [ ] demo からハードコードと「手計算値」の文言が消えている
- [ ] soysauce の全回帰値・Phase 4/5 の全分解値・golden 13ケースが不変
- [ ] **377件全PASS**（既存370 + 新規7）

---

## 実装者への申し送り

**1. 実測値の報告をお願いします。** V4.1 のとおり、`true_optimum` の実計算値が設計書の手計算値と末尾まで一致するとは限りません。**実行して得られた値をそのまま報告してください。** 一致しない場合、それは実装の誤りではなく手計算側の概算誤差である可能性が高く、大杉さんの判断で新しい回帰値として確定します。**手計算値に合わせて実装を調整することは絶対にしないでください。**

**2. 式の二重定義を作らないこと。** 単位マージンは必ず `dataclasses.replace` ＋ 既存 `unit_pnl()` 経由で求めてください。Phase 5 で `unit_pnl_at_quantity()` をこの方針で実装しており、それに揃えます。

**3. 疑問があれば実装前に質問してください。** 特に手順3の上下界の扱いは本設計の中核です。「税率を固定して解いてから整合性を検査する」という素朴な方式との違いを理解したうえで着手してください。

---

## 本 Phase の位置づけ（背景）

`structural_optimality_gap` は、Operational Due Diligence で「提示された事業計画がどのバンドに落ちるか」を判定する**物差し**になります（`requests/Phase8_DesignMD_CockpitGUI.md` §4 の S1 画面）。また Phase 6-3（階層化単体格子）は、階層化そのものが貪欲法の一種であるため、**その近似誤差を測るのに本 Phase の出力を使います**。

つまり本 Phase は、後続2つの Phase が依存する測定器の実装です。小さいですが、順序として先に置く理由がここにあります。


---

# 実装結果（2026-09-11 追記・Claude君）

**本 letter 本文（V1〜V4）は Code君に渡した当時のまま残してある。** 期待値の一部が下記のとおり更新されたが、指示そのものは書き換えない（何を指示し、何が起きたかの記録として残す）。

## 結果

**377件全PASS**（既存370 + 新規7、目標値と一致）。golden 13ケース不変。§3.3 ではなく本 letter V1.2（上下界方式）で実装済み。

## 実測値と、設計書の手計算値との差（**申し送り1 が機能した事例**）

| | 設計書の手計算値 | 実計算値 | 差 |
|---|---|---|---|
| `true_optimum` | 103,881,758.0 | **103,891,296.0** | +9,538 |
| `structural_optimality_gap` | 10,057,058 | **10,066,596** | +9,538 |
| `grid_resolution_error` | 328,958 | **338,496** | +9,538 |
| `residual_coverage` | 96.7% | **96.6%** | −0.1pt |

配分は `JP=0 / US=35,176 / EU=16,824`（設計書は `JP=7 / US=35,168 / EU=16,825`）。

**差は許容差内に収まる丸め誤差ではなく、手計算側の最適化の誤りだった。** 1円まで分解できる。

```
US  +8 lot × 2,077.5 = +16,620.0
EU  −1 lot × 1,831.5 =  −1,831.5
JP  −7 lot ×   750.0 =  −5,250.0
                       ──────────
                        +9,538.5     ← 103,891,296.0 − 103,881,757.5
```

設計書の配分は、単位マージン 2,077.5 の US 需要を 8 lot 残したまま、最もマージンの低い JP（750）に 7 lot 配っていた。厳密に劣る点である。**実装がそれを検出した。** 申し送り1「手計算値に合わせて実装を調整することは絶対にしないでください」が意図どおり機能した。

## Code君への追加依頼（回帰値の確定に伴う締め直し）

大杉さんの承認を得たので、以下をお願いします。

1. **`tests/test_allocation_nonconcave.py` V4.1（`test_true_optimum_s9_matches_design_value`）の許容差を `abs=10_000.0` → `abs=1.0` に締め、期待値を `103_891_296.0` にする。** テスト名の `_matches_design_value` は実態と合わなくなったので `test_true_optimum_s9_regression` 等へ改名してよい（設計書側の記載も rev.2 で更新済み）。
2. **同ファイル L216 付近の Phase 5 既存テスト（`test_residual_underestimates_true_gap`）にある `true_optimum_profit = 103_881_758.0` を `103_891_296.0` に更新する。** 現状でも下界性のテストとしては PASS するが、値が古いままだと将来の読み手を誤らせる。コメントの「設計書§2.3の手計算値（本コードでは計算しない）」も、`true_continuous_optimum()` が実装済みである以上、実計算を呼ぶか、少なくとも「Phase 6-1 で確定した回帰値」という記述に改めること。
3. 上記2件の変更後、**377件全PASS を再確認**してください。

なお、設計書は以下のとおり更新済みです（Code君が参照する際はこちらが最新）。

- `requests/Phase6_DesignMD_NMarketHierarchy.md` rev.2（§3.3 全面改訂・§3.5 回帰値更新）
- `requests/Phase5_DesignMD_NonConcaveTariff.md` rev.3
- `requests/Phase4_DesignMD_AllocationMeritRegime.md` rev.5
