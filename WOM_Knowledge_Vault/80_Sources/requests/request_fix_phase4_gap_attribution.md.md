---
tags: [wom, source]
---
# requests/request_fix_phase4_gap_attribution.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/requests/request_fix_phase4_gap_attribution.md) · [原文テキスト](../../90_Raw/requests/request_fix_phase4_gap_attribution.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Phase 4 修正依頼 — 乖離の帰属判定・図の判読性・`.gitignore`
- 概要
- G1: `.gitignore` に `out/` を追加する
- 現状
- 実装仕様
- G2: 乖離の帰属判定を「idle × λ」方式に差し替える
- G2.1 現状の実装と、そこで起きたこと
- G2.2 なぜ厳密一致しなかったか（**設計書の欠陥**）
- G2.3 差し替える判定方法
- G2.4 実装仕様
- 実装手順
- 限界市場が格子最適点で残している未充足需要
- 削除するもの
- 能力が制約にならない場合の扱い
- G2.5 テスト仕様
- 既存テストの変更（1件）
- 新規テスト（1件）
- 影響を受ける既存テスト
- G3: メリットオーダー曲線の注記を軸の下へ移す
- 現状
- 問題
- 実装仕様
- 凡例について
- G4: Before/After の凡例を左下へ移す
- 現状
- 問題
- 実装仕様
- 実装チェックリスト
- `.gitignore`
- `wom/allocation/merit_order.py`
- `tools/plot_allocation_merit_regime.py`
- `tests/test_allocation_merit_order.py`
- テスト実行コマンド
- 実装後の確認事項
- 補足：今回の目視 QA で「問題なし」と確認できた項目
- 参考：`git status` に約200ファイルが出る件
- Git コミット情報

## 関連する知識源

- [[80_Sources/requests/Phase4_DesignMD_AllocationMeritRegime.md|requests/Phase4_DesignMD_AllocationMeritRegime.md]]
- [[80_Sources/wom/allocation/merit_order.py|wom/allocation/merit_order.py]]
- [[80_Sources/tools/plot_allocation_merit_regime.py|tools/plot_allocation_merit_regime.py]]
- [[80_Sources/tools/plot_allocation_map.py|tools/plot_allocation_map.py]]
- [[80_Sources/tests/test_allocation_merit_order.py|tests/test_allocation_merit_order.py]]
- [[80_Sources/tests/test_allocation_regime_map.py|tests/test_allocation_regime_map.py]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Phase 4 修正依頼 — 乖離の帰属判定・図の判読性・`.gitignore`

**宛先**: Code君
**作成日**: 2026年9月8日
**担当**: Claude君（指摘・仕様）→ 大杉さん（承認済）→ Code君（実装）
**優先度**: MEDIUM（2-3時間）
**ブランチ**: `wom-v1r4m0`
**関連**: `requests/Phase4_DesignMD_AllocationMeritRegime.md`（§3.5 を rev.2 で全面改訂）

---

## 概要

Phase 4 の実装（356件全PASS）を受領し、`--demo` 出力4枚を目視 QA した結果、**4点**の修正を依頼する。

**G2 は Claude君の設計書 §3.5 の欠陥が原因**であり、Code君の実装ミスではない。Code君が `tol=0.005` で回避した判断は状況に対して妥当だったが、根本を直す。設計書側も同時に rev.2 へ改訂する。

| # | 対象 | 内容 | 種別 |
|---|---|---|---|
| **G1** | `.gitignore` | `out/` が無視されておらず PNG がコミット対象に入る | 設定漏れ（Phase 4 以前から潜在） |
| **G2** | `wom/allocation/merit_order.py` | 乖離の帰属判定ロジックの差し替え | **設計書の欠陥** |
| **G3** | `tools/plot_allocation_merit_regime.py` | メリットオーダー曲線の注記がブロックに埋もれて読めない | 判読性 |
| **G4** | 同上 | Before/After の凡例が After 曲線と重なる | 判読性 |

**Phase 3/4 の絶対制約は引き続き全て適用される。** 特に matplotlib のみ・新規依存なし・図中テキストは全て英語・出力パスを返す・禁足コア無変更。

---

## G1: `.gitignore` に `out/` を追加する

### 現状

`.gitignore` には `output/` があるが **`out/` が無い**。

一方、既存 A系統の `tools/plot_allocation_map.py` は **既定の出力先が `out/`** である（docstring：「引数なしの `--out` 省略時は `out/` に tile.png / layers.png を生成」）。

このため、A系統のツールを引数なしで一度でも実行すると `out/` に PNG が残り、`git add -A` でコミット対象に入る。現に `out/{layers,s4,tile}.png`（計 528KB）が untracked で残っている。

**Phase 4 由来ではなく、A系統の実装時から潜在していた漏れである。**

### 実装仕様

`.gitignore` の `output/` の直後に1行追加する。

```
output/
out/
```

既に `out/` に生成済みの PNG は追跡されていないので、追加するだけで `git status` から消える。

**`output/allocation_p4/`（Phase 4 の出力先）は `output/` 配下なので既に無視されており、対応不要。** 設計書 §5.3 は `output/allocation/` と書いていたが、A系統の既存出力と混ざらないよう `output/allocation_p4/` に分けた Code君の判断は妥当なので、そのままでよい（設計書側を rev.2 で追認する）。

---

## G2: 乖離の帰属判定を「idle × λ」方式に差し替える

### G2.1 現状の実装と、そこで起きたこと

`compare_with_grid()` は設計書 §3.5 に従い、**メリットオーダー解の各成分を δ に切り上げ／切り捨てした全組合せ**のうち格子上に実在する点の最良値 `rounded_best_profit` を求め、格子最適 `grid_best_profit` との相対差が `tol` 以内なら「格子解像度で説明できる」と判定している。

soysauce での実測は**厳密一致ではなく相対誤差 0.146%** だったため、Code君は `tol=0.005`（0.5%）を導入して True と判定させた。

### G2.2 なぜ厳密一致しなかったか（**設計書の欠陥**）

検算した結果は以下のとおり。

| 丸め候補（Σx=1 を満たすもの） | 利益 |
|---|---|
| x = (0.15, 0.40, 0.45) | 131,939,812.5 |
| x = (0.15, 0.45, 0.40) | 131,782,380.0 |
| x = (0.20, 0.40, 0.40) | 131,589,120.0 |
| **格子最適 x = (0.10, 0.45, 0.45)** | **132,133,072.5** |

**格子最適点が丸め候補に入っていない。** `x_mo["JP"] = 0.1544` の切り捨ては 0.15、切り上げは 0.20 で、**0.10 はそのどちらでもない**からである。

US と EU を需要天井（0.4228）より上の 0.45 に切り上げると、単体制約 Σx=1 により JP が 0.10 へ「押し出される」。**この押し出しは成分ごとの独立な丸めでは表現できない。** 設計書 §3.5 のロジックは、単体上の制約を無視して各成分を独立に丸めていた点で誤っていた。

`tol` を大きくすれば通るが、それは症状を隠すだけである。**判定の向きが逆になる問題を閾値で埋めている**ため、非凹ケースで構造由来の乖離が 0.5% 未満だった場合に False Negative になる。

### G2.3 差し替える判定方法

**乖離は「格子最適点で遊んでいる能力を限界市場に回したときの利益増分」に等しい。**

```
expected_gap = grid_idle × λ
```

soysauce で検算した結果：

| | 値 |
|---|---|
| 格子最適点の遊休能力 `grid_idle` | 4,529 lot |
| λ（限界市場 JP の単位マージン） | 750 JPY/lot |
| 予測乖離 `grid_idle × λ` | 3,396,750.0 JPY |
| 実測乖離 `merit_order_profit − grid_best_profit` | 3,396,750.0 JPY |
| **差** | **0.000000 JPY（厳密一致）** |

**理屈**: 格子最適点で idle だけ能力が遊んでいる。その能力を限界市場（マージン λ）に回せば `idle × λ` だけ利益が増える。メリットオーダー連続解はまさにそれをしている。したがって両者の差は `idle × λ` に厳密に一致する。

**成立条件**: 限界市場が格子最適点で `idle` 以上の未充足需要を残していること（回せる先があること）。soysauce では 21,830 ≥ 4,529 で成立。

**この方式の利点**:
- **恣意的な閾値が要らない**（数値誤差分の許容のみ）
- 非凹ケースでは `gap_amt > expected_gap` になり、**超過分がそのまま構造由来の量として切り出せる**。Phase 5 で `ev-thailand-2026`（LC率閾値で非凹）に適用したときに、これが「構造的発見」の定量値になる

### G2.4 実装仕様

```python
def compare_with_grid(
    mo: dict,
    surface: List[dict],
    *,
    abs_tol: float = 1.0,      # JPY。数値誤差の許容（旧 tol=0.005 は廃止）
) -> dict:
    """メリットオーダー連続解と格子最適の乖離を定量化し、
    格子解像度で説明できる分と、構造由来の残差とに分解する。

    判定式（§3.5 rev.2）:
        expected_gap = grid_idle × lambda
        structural_residual = gap_amt − expected_gap
        attributable_to_grid_resolution =
            absorbable and abs(structural_residual) <= abs_tol

    Returns:
        {
            "merit_order_profit": 135529822.5,
            "grid_best_profit": 132133072.5,
            "grid_best_x": (0.10, 0.45, 0.45),
            "gap_amt": 3396750.0,
            "gap_pct": 0.0257,
            "grid_idle": 4529.0,
            "lambda": 750.0,
            "marginal_market": "JP",
            "marginal_unmet_at_grid_best": 21830.0,
            "absorbable": True,                       # 限界市場が idle を吸収できるか
            "expected_gap_from_grid_resolution": 3396750.0,
            "structural_residual": 0.0,               # ★ Phase 5 で使う主要な出力
            "structural_residual_pct": 0.0,
            "attributable_to_grid_resolution": True,
        }
    """
```

#### 実装手順

```python
best, plateau = best_point(surface)
grid_pt = plateau[0]
grid_x, grid_idle = grid_pt["x"], grid_pt["idle"]

gap_amt = mo["profit"] - best
gap_pct = (gap_amt / best) if best else float("nan")

lam = mo["lambda"]
marginal = mo["marginal_market"]

# 限界市場が格子最適点で残している未充足需要
if marginal is None:
    marginal_unmet = 0.0
else:
    marginal_unmet = grid_pt["unmet"][marginal]

absorbable = (marginal is not None) and (marginal_unmet >= grid_idle)

expected_gap = grid_idle * lam
structural_residual = gap_amt - expected_gap
structural_residual_pct = (structural_residual / best) if best else float("nan")

attributable = absorbable and (abs(structural_residual) <= abs_tol)
```

#### 削除するもの

- 引数 `tol`、`delta`
- 戻り値キー `rounded_best_profit`
- `itertools` / `math` の丸め候補生成ロジック一式（`_floor_ceil()` 等）

`delta` は判定に使わなくなるので引数から外す。**外部の呼び出し元は CLI と テストのみ**なので影響は閉じている。

#### 能力が制約にならない場合の扱い

`mo["marginal_market"]` が `None`（能力が余っている＝λ=0）のとき：

- `expected_gap = 0`
- `absorbable = False`
- `attributable_to_grid_resolution = False`

**この場合そもそも乖離がほぼゼロのはず**（連続解も格子解も全需要を満たせる）なので、False でよい。ただし `structural_residual` は `gap_amt` そのものになるため、値としては意味を持ち続ける。

### G2.5 テスト仕様

#### 既存テストの変更（1件）

`tests/test_allocation_merit_order.py` の `test_gap_attributable_to_grid_resolution` を書き換える。

```python
def test_gap_attributable_to_grid_resolution(soysauce_blocks):
    """soysauce では乖離が grid_idle × lambda で厳密に説明でき、構造由来の残差はゼロ"""
    ...
    cmp = compare_with_grid(mo, surface)

    assert cmp["absorbable"] is True
    assert cmp["marginal_market"] == "JP"
    # 予測乖離が実測乖離と厳密に一致する（1 JPY 未満）
    assert abs(cmp["expected_gap_from_grid_resolution"] - cmp["gap_amt"]) < 1.0
    assert abs(cmp["structural_residual"]) < 1.0
    assert cmp["attributable_to_grid_resolution"] is True
```

#### 新規テスト（1件）

```python
def test_expected_gap_equals_idle_times_lambda(soysauce_blocks):
    """乖離 = 格子最適点の遊休能力 × λ という恒等式（§3.5 rev.2 の判定の根拠）"""
    ...
    cmp = compare_with_grid(mo, surface)

    assert cmp["grid_idle"] == pytest.approx(4529.0)
    assert cmp["lambda"] == pytest.approx(750.0)
    assert cmp["expected_gap_from_grid_resolution"] == pytest.approx(4529.0 * 750.0)
    assert cmp["gap_amt"] == pytest.approx(3396750.0)
    # 限界市場に回せる余地があること
    assert cmp["marginal_unmet_at_grid_best"] >= cmp["grid_idle"]
```

#### 影響を受ける既存テスト

`test_compare_with_grid_soysauce` は `merit_order_profit` / `grid_best_profit` / `gap_amt` / `gap_pct` を見ているだけなら**無変更で通る**。`rounded_best_profit` を参照している場合は削除すること。

---

## G3: メリットオーダー曲線の注記を軸の下へ移す

### 現状

`plot_allocation_merit_order()` は3行の注記を `transAxes` の y = 0.96 / 0.90 / 0.84（＝軸の内側・左上）に置いている。

```python
ax.text(0.02, 0.96, f"lambda = ...", transform=ax.transAxes, ...)   # crimson
ax.text(0.02, 0.90, f"Idle capacity: ... | Unmet demand: ...", ...)  # dimgray
ax.text(0.02, 0.84, note, ...)                                       # 乖離の注記
```

### 問題

**3行とも矩形ブロックの上に重なり、下2行は完全に判読不能になっている。**

これは Phase 3 とは**逆向きの構造問題**である。Phase 3（サプライヤー版）は単価**昇順**なので左端が最も低く、左上が構造的に空いた。Phase 4（配分版）は単位マージン**降順**なので、**左端に必ず最も背の高いブロックが来る。左上は構造的に必ず埋まる。**

`loc` を変えて軸内で逃がす場所を探しても、市場数や margin の分布次第で再発する。

### 実装仕様

**3行の注記を軸の下に移す。** `plot_allocation_merit_shift()` が "Rank changes: ..." を `y=-0.14` に出しているのと同じ手法で、図法をまたいで一貫させる。

```python
notes = []
if lam is not None:
    notes.append(f"lambda = {lam:.1f} JPY/lot "
                 f"(shadow price of capacity, marginal market: {marginal})")
else:
    notes.append("lambda = 0 (capacity not binding, idle capacity remains)")
notes.append(f"Idle capacity: {idle:,.0f} lots   |   "
             f"Unmet demand: {total_unmet:,.0f} lots")
if comparison is not None:
    notes.append(<乖離の注記>)

ax.text(0.02, -0.14, "\n".join(notes), transform=ax.transAxes,
        ha="left", va="top", fontsize=8.5)
fig.tight_layout(rect=(0, 0.10, 1, 1))   # 下部に注記ぶんの余白を確保
```

- **λ の行は crimson を維持**する（赤の水平線と対応していることが読み取れるように）。他2行は既定色でよい
- `rect` の下端は注記の行数（最大3行）に合わせて調整すること。`plot_allocation_merit_shift()` は1行で `rect=(0, 0.06, 1, 1)` を使っているので、3行なら 0.10〜0.12 程度が目安
- **除外市場（負マージン）の注記**（現在 y=0.02 付近に描かれているもの）は、ハッチ矩形のすぐ近くにあるほうが対応が取れるので**現状のまま軸内に残してよい**

### 凡例について

右上の `capacity = 83,200 lots` の凡例は、能力線より右・λ より上の領域にあり**構造的に空く**（限界市場より右のブロックは必ず λ 以下の高さになるため）。**現状の `loc="upper right"` のままでよい。**

---

## G4: Before/After の凡例を左下へ移す

### 現状

`plot_allocation_merit_shift()` は `ax.legend(handles, labels_, fontsize=8, loc="upper left", framealpha=0.9)`。

### 問題

After 曲線の左端（最も高いブロック、FX125 で y≈1263）が凡例ボックスの下に入っている。G3 と同じ理由で、**降順に積む以上、左上は構造的に埋まる。**

Phase 3 では「階段は左端が最安（最も低い）ので upper left は構造的に空く」と設計したが、**配分版では前提が逆になる。**

### 実装仕様

```python
ax.legend(handles, labels_, fontsize=8, loc="lower left", framealpha=0.9)
```

λ の水平線（`lambda_before` / `lambda_after`）は階段の最下段の高さにあり、**それより下の領域は全面的に空く**ため、`lower left` は構造的に安全である。

---

## 実装チェックリスト

### `.gitignore`

- [ ] **G1**: `output/` の直後に `out/` を追加

### `wom/allocation/merit_order.py`

- [ ] **G2**: `compare_with_grid()` を idle × λ 方式に差し替え
- [ ] **G2**: 引数 `tol` / `delta` を削除し、`abs_tol: float = 1.0` を追加
- [ ] **G2**: 戻り値に `lambda` / `marginal_market` / `marginal_unmet_at_grid_best` / `absorbable` / `expected_gap_from_grid_resolution` / `structural_residual` / `structural_residual_pct` を追加
- [ ] **G2**: 戻り値から `rounded_best_profit` を削除
- [ ] **G2**: 丸め候補生成ロジック（`_floor_ceil()` 等）と不要になった `itertools` import を削除
- [ ] **G2**: `marginal_market is None`（能力が制約にならない）ときに例外を出さないこと
- [ ] **G2**: docstring を §3.5 rev.2 の判定式に合わせて更新

### `tools/plot_allocation_merit_regime.py`

- [ ] **G3**: メリットオーダー曲線の注記3行を軸下（`y=-0.14`）へ移し、`tight_layout(rect=...)` で余白を確保
- [ ] **G3**: λ の行の crimson を維持
- [ ] **G3**: 除外市場の注記は軸内のまま
- [ ] **G3**: `capacity = ...` の凡例は `upper right` のまま
- [ ] **G4**: Before/After の凡例を `loc="lower left"` に変更
- [ ] `compare_with_grid()` の戻り値キー変更（`rounded_best_profit` 削除）に追随している

### `tests/test_allocation_merit_order.py`

- [ ] **G2**: `test_gap_attributable_to_grid_resolution` を書き換え（構造残差ゼロを assert）
- [ ] **G2**: `test_expected_gap_equals_idle_times_lambda` を新規追加
- [ ] `test_compare_with_grid_soysauce` が `rounded_best_profit` を参照していれば削除

### テスト実行コマンド

```bash
python -m pytest tests/test_allocation_merit_order.py -v
python -m pytest tests/test_allocation_regime_map.py -v
python -m pytest tests/ -q
```

**期待結果: 357件 全PASS**（Phase 4 完了時点 356 + 新規1、既存に回帰なし）

---

## 実装後の確認事項

```bash
python -m tools.plot_allocation_merit_regime --model-dir data/sample/soysauce-jpy-2027-alloc --demo
```

- [ ] `alloc_merit_order.png` — **注記3行が軸の下にあり、すべて判読できる**
- [ ] `alloc_merit_order.png` — λ の行が赤で、赤い水平線との対応が読み取れる
- [ ] `alloc_merit_order.png` — 矩形・λ 水平線・能力線・`capacity` 凡例に変化がない
- [ ] `alloc_merit_shift.png` — **凡例が左下にあり、After 曲線と重なっていない**
- [ ] `alloc_regime_map.png` / `alloc_regime_map_tariff.png` — **ピクセル的に無変化**（G2/G3/G4 は②に触れないため）
- [ ] 4枚とも日本語の豆腐（□）が無い

```bash
git status
```

- [ ] **`out/` が untracked に現れない**

---

## 補足：今回の目視 QA で「問題なし」と確認できた項目

修正不要だが、記録として残す。Code君が不要な調査に時間を使わないように。

- **②レジーム地図の 117円 / 119円 境界**：`fx × material` の図で、既存 `switching_points()` の記録値どおりに境界が立っている。117〜119 の2円幅の細い帯（`EU>JP>US`）まで正しく描かれている。**最重要の回帰が図の上でも確認できた。**
- **負マージン領域**：shock 点 (200, 8) がハッチ領域の内側にあり、`transmission.py` docstring の「FX200 $8 → JP −105.0」と整合。`fx × tariff` の図でハッチが出ないのも、material=6.0 固定では JP が負にならない（FX200 $6 → JP +295.0）ため正しい。
- **`fx × tariff` で3市場の全順列6つが現れる**こと、関税 9.5% 付近で US と EU が入れ替わる境界が経済的に妥当であること。
- **base 点のレジームが両図で一致**（ともに `EU>US>JP`）。
- **Before/After の順位反転が論理的に整合**：FX115 で λ=972.2（限界市場 US、`transmission.py` の FX115 検証値 US 972.25 と一致）、FX125 で λ=977.5（限界市場 JP）。`Rank changes: EU (#2->#1), US (#3->#2), JP (#1->#3)` は 117円の切替点をまたいだ結果として正しい。
- **`output/allocation_p4/` への出力先変更**：設計書 §5.3 は `output/allocation/` と書いていたが、A系統の既存出力（`ga_*.csv` / `tile.png` / `layers.png`）と混ざらないよう分けた判断は妥当。`output/` 配下なので gitignore 済み。**設計書側を rev.2 で追認する。**

### 参考：`git status` に約200ファイルが出る件

Claude君が Linux 経由で見たときに禁足コア・golden を含む約200ファイルが modified に見えたが、`git diff --ignore-cr-at-eol` で調べたところ**実質差分は CLAUDE.md 1本のみ**で、残りは改行コード（LF↔CRLF）だけの差だった。Windows 側の git は `core.autocrlf=true` で動いているため、**Windows で `git status` を見れば clean に見えるはず**。Code君の変更とは無関係。

---

## Git コミット情報

**git 操作は大杉さんが Windows 側ターミナルで実施する**（CLAUDE.md L267）。Code君は実装とテストまでを行い、コミットメッセージ案を提示すること。

```
Phase 4 fix: 乖離の帰属判定・図の判読性・.gitignore

- G1: .gitignore に out/ を追加
  A系統 plot_allocation_map.py の既定出力先が out/ で、
  output/ しか無視されていなかった（Phase 4 以前からの潜在漏れ）

- G2: compare_with_grid() の帰属判定を idle × λ 方式へ差し替え
  旧: メリットオーダー解を成分ごとに δ へ丸めた候補の最良値と格子最適を比較
      → 単体制約による「押し出し」を表現できず格子最適点が候補に入らない
      → 相対誤差 0.146% が残り tol=0.005 で回避していた
  新: expected_gap = grid_idle × lambda
      soysauce で実測乖離と厳密一致（差 0.000000 JPY）、閾値が不要
      structural_residual = gap_amt − expected_gap を新たに返し、
      非凹ケースでの構造由来の乖離量を切り出せるようにした（Phase 5 で使用）
  ※ 設計書 §3.5 の欠陥に起因（実装ミスではない）

- G3: plot_allocation_merit_order() の注記3行を軸下へ
  単位マージン降順に積む以上、左上には必ず最も背の高いブロックが来るため
  軸内に安全な置き場所がない（Phase 3 の昇順とは前提が逆）

- G4: plot_allocation_merit_shift() の凡例を lower left へ（同じ理由）

新規テスト: 1個（test_expected_gap_equals_idle_times_lambda）
変更テスト: 1個（test_gap_attributable_to_grid_resolution）
既存テスト: 356個（全て PASS、回帰なし）
計: 357個テスト全て PASS

設計書 requests/Phase4_DesignMD_AllocationMeritRegime.md を rev.2 に改訂
（§3.5 判定方法の全面差し替え、§5.3 出力先の追認、§7 テスト構成）

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01EEihXkBiSxhPNk83Uw6CKB
```

---

**修正依頼 完成日**: 2026年9月8日
**指摘・仕様**: Claude君
**承認**: 大杉さん（2026-09-08）
**実装責任**: Code君

````
