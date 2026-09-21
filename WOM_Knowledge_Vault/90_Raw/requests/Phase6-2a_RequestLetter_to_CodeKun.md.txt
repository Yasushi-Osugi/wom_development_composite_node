# Phase 6-2a 追加依頼 Request Letter — N市場経路の End-to-End テスト

**宛先**: Code君
**作成日**: 2026年9月11日
**担当**: Claude君（設計・仕様）→ 大杉さん（レビュー）→ Code君（実装）
**優先度**: MEDIUM（小規模・テストのみ。Phase 6-3 の前に入れておきたい）
**ブランチ**: `wom-v1r4m0`
**前提**: Phase 6-2 完了（`32b2544`、384件全PASS）
**設計正典**: `requests/Phase6_DesignMD_NMarketHierarchy.md` §4（rev.3）／`requests/Phase6-2_RequestLetter_to_CodeKun.md`

---

## 概要 — 何が足りないか

Phase 6-2 の実装は指示どおりで、回帰も出ていません。**依頼した側（Claude君）のテスト仕様に穴がありました。**

V7 の7件は次のものを見ています。

- 格子点の**順序**（V7.1）と**点数**（V7.2）と**成分和**（V7.3）
- `markets_of()` の**決定性**と**非アルファベット順**（V7.4 / V7.5）
- 上限ガード（V7.6）と三角図の N=3 制限（V7.7）

見ていないものが1つあります。**「N市場で A系統が端から端まで動くこと」そのものです。** `simplex_grid()` が正しい点数を返すことと、`scan_surface()` → `merit_order` → `true_optimum` → `regime_map` → `analytics` の一連が N=4 で正しい値を出すことは、別の話です。Phase 6-2 の目的は後者であって、前者はその材料にすぎません。

本追加依頼で、**双子分割による不変性テスト**を入れます。テスト2件のみで、**実装コードの変更はありません。**

---

## なぜ「双子分割」で測るのか

N市場の正解を独立に手計算するのは現実的ではありません。しかし、**経済条件が完全に同一の2市場に1市場を割る**と、答えが変わらないことは理屈から確定します。需要 D の市場を D/2 ずつの双子に割っても、貪欲法は同じ順位で同じ総量を積むだけなので、**最適利益も λ も配分比率の合計も一切変わらない**はずです。

これは正解表を用意せずに N市場経路の正しさを固定できる、ほぼ唯一の手段です。設計書 §7.3 のテスト16（Phase 6-3 の最重要テスト）と同じ考え方を、**平坦格子の N=4 で先に適用する**ことになります。

---

## 実測値（Claude君が実行して確定済み）

`data/sample/soysauce-jpy-2027-alloc` の `EU`（`demand_qty = 35175`）を、`dataclasses.replace` で `demand_qty` だけ半分にした `EU_A` / `EU_B` に割った場合。`cap_wk = 800.0`、`Scenario(fx_usd=150.0, material_usd=6.0)`、`transfer_price_usd = 17.6`（`derive_cost_blocks()` の戻り値）。

| | N=3 | N=4（双子分割） | 判定 |
|---|---:|---:|---|
| `markets_of()` | `('JP','US','EU')` | `('JP','US','EU_A','EU_B')` | — |
| 格子点数 | 231 | 1,771 | — |
| `merit_order` profit | 135,529,822.5 | **135,529,822.5** | **不変** |
| `lambda` | 750.0 | **750.0** | **不変** |
| `marginal_market` | `'JP'` | **`'JP'`** | **不変** |
| `idle` | 0.0 | **0.0** | **不変** |
| `true_optimum` | 135,529,822.5 | **135,529,822.5** | **不変** |
| `x_EU` | 0.4227764423076923 | `EU_A` + `EU_B` = **同値** | **不変** |
| `market_ranking` | `('EU','US','JP')` | `('EU_A','EU_B','US','JP')` | EU が双子に展開 |
| 需要天井 `EU` | 0.4228 | `EU_A` = `EU_B` = 0.2114 | 折半 |
| **格子の最良点** | **132,133,072.5** | **131,782,380.0** | **−350,692.5** |
| 格子の最良 x | `(0.10, 0.45, 0.45)` | `(0.15, 0.45, 0.20, 0.20)` | — |

**貪欲法と真の最適は分割不変ですが、δ=0.05 の格子だけが劣化します。** 市場を増やしたわけでもなく、同一条件の双子に割っただけで格子の最良点が 350,692.5 JPY 悪化しました。これは次元の呪いが**金額として現れた**もので、Phase 6-3（階層化）が必要な理由そのものです。テストではこれも「劣化すること」として固定します（改善したらどこかがおかしい）。

---

## V8.1 `test_four_market_twin_split_invariance`（**本依頼の主目的**）

**新規ファイル** `tests/test_allocation_nmarket.py` を作る。N市場経路専用のテストファイルとし、Phase 6-3 の階層化テストもここに追記していく。

```python
# -*- coding: utf-8 -*-
"""
tests/test_allocation_nmarket.py — N市場経路の End-to-End 回帰
================================================================
Phase 6-2（次元の一般化）で A系統が3市場固定を外したことを、
「双子分割の不変性」で固定する。経済条件が完全に同一の2市場に1市場を
割っても、貪欲法の解と真の連続最適は変わらないはずである——これにより
N市場の正解表を用意せずに N市場経路の正しさを検証できる。

正典: requests/Phase6_DesignMD_NMarketHierarchy.md §4（rev.3）
依頼: requests/Phase6-2a_RequestLetter_to_CodeKun.md
"""
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.grid import scan_surface, best_point, markets_of, demand_ceilings
from wom.allocation.merit_order import build_allocation_merit_order, true_continuous_optimum
from wom.allocation.analytics import market_ranking
from wom.allocation.regime_map import scan_regime_grid
from wom.allocation.transmission import Scenario

ALLOC_DIR = os.path.join(os.path.dirname(__file__), "..",
                         "data", "sample", "soysauce-jpy-2027-alloc")

BLOCKS, TP = derive_cost_blocks(ALLOC_DIR)
SC = Scenario(fx_usd=150.0, material_usd=6.0)
CAP_WK = 800.0


def _twin_split(blocks, market, name_a, name_b):
    """market を、経済条件が同一・需要を折半した双子 (name_a, name_b) に割る。

    需要以外は一切変えない（`dataclasses.replace` で demand_qty のみ差し替え）。
    元の市場の位置に双子を並べる——markets_of() は dict のキー順なので、
    並び順が結果に影響しないことも同時に確認できる。
    """
    src = blocks[market]
    half = src.demand_qty / 2
    out = {}
    for m, cb in blocks.items():
        if m == market:
            out[name_a] = replace(src, demand_qty=half)
            out[name_b] = replace(src, demand_qty=half)
        else:
            out[m] = cb
    return out


BLOCKS4 = _twin_split(BLOCKS, "EU", "EU_A", "EU_B")


def test_markets_of_after_twin_split():
    assert markets_of(BLOCKS) == ("JP", "US", "EU")
    assert markets_of(BLOCKS4) == ("JP", "US", "EU_A", "EU_B")


def test_four_market_twin_split_invariance():
    """双子分割しても貪欲法の解と真の連続最適は1円も変わらないこと（最重要）。"""
    mo3 = build_allocation_merit_order(BLOCKS,  SC, cap_wk=CAP_WK, transfer_price_usd=TP)
    mo4 = build_allocation_merit_order(BLOCKS4, SC, cap_wk=CAP_WK, transfer_price_usd=TP)

    assert mo4["profit"] == mo3["profit"] == pytest.approx(135_529_822.5, abs=1e-6)
    assert mo4["lambda"] == mo3["lambda"] == pytest.approx(750.0, abs=1e-9)
    assert mo4["marginal_market"] == mo3["marginal_market"] == "JP"
    assert mo4["idle"] == mo3["idle"] == pytest.approx(0.0, abs=1e-6)
    assert mo4["excluded"] == mo3["excluded"] == []

    # 分割されていない市場の配分比率は不変
    assert mo4["x"]["JP"] == pytest.approx(mo3["x"]["JP"], abs=1e-12)
    assert mo4["x"]["US"] == pytest.approx(mo3["x"]["US"], abs=1e-12)
    # 双子は等分され、合計は元の EU と一致する
    assert mo4["x"]["EU_A"] == pytest.approx(mo4["x"]["EU_B"], abs=1e-12)
    assert mo4["x"]["EU_A"] + mo4["x"]["EU_B"] == pytest.approx(mo3["x"]["EU"], abs=1e-12)

    # 真の連続最適も同じく不変（cliff が無いので 2^0 = 1 ケース）
    to3 = true_continuous_optimum(BLOCKS,  SC, cap_wk=CAP_WK, transfer_price_usd=TP)
    to4 = true_continuous_optimum(BLOCKS4, SC, cap_wk=CAP_WK, transfer_price_usd=TP)
    assert to4["profit"] == to3["profit"] == pytest.approx(135_529_822.5, abs=1e-6)
    assert to4["cases_evaluated"] == to3["cases_evaluated"] == 1


def test_four_market_grid_degrades_with_dimension():
    """格子だけは次元の増加で劣化すること（Phase 6-3 が必要な理由を金額で固定）。"""
    s3 = scan_surface(BLOCKS,  TP, SC, cap_wk=CAP_WK)
    s4 = scan_surface(BLOCKS4, TP, SC, cap_wk=CAP_WK)
    assert len(s3) == 231 and len(s4) == 1_771

    b3, p3 = best_point(s3)
    b4, p4 = best_point(s4)
    assert b3 == pytest.approx(132_133_072.5, abs=1.0)
    assert b4 == pytest.approx(131_782_380.0, abs=1.0)
    assert b3 - b4 == pytest.approx(350_692.5, abs=1.0)

    # 格子は貪欲法の解に届かない（劣化の向きが逆転しないこと）
    assert b4 < b3 < 135_529_822.5
    assert len(p3) == 1 and len(p4) == 1
```

**許容差の方針**: 分割不変性は理屈から厳密に成立するので `abs=1e-6`（実質は厳密一致）で締める。格子の回帰値は `abs=1.0`（1円）とする。

---

## V8.2 `test_four_market_pipeline_runs`

A系統の残りのモジュールが N=4 でも動き、市場名を正しく扱うこと。**値の正しさよりも「3市場を前提にした箇所が残っていないこと」の確認**である。

```python
def test_four_market_pipeline_runs():
    """A系統の各モジュールが N=4 で動き、4市場すべてを扱うこと。"""
    # 需要天井: 双子は折半され、他は不変
    c3 = demand_ceilings(BLOCKS,  CAP_WK)
    c4 = demand_ceilings(BLOCKS4, CAP_WK)
    assert set(c4) == {"JP", "US", "EU_A", "EU_B"}
    assert c4["JP"] == pytest.approx(c3["JP"], abs=1e-12)
    assert c4["EU_A"] == c4["EU_B"] == pytest.approx(c3["EU"] / 2, abs=1e-12)

    # 単位マージン順位: EU が双子に展開されるだけで相対順位は変わらない
    assert market_ranking(BLOCKS,  TP, 150.0) == ("EU", "US", "JP")
    assert market_ranking(BLOCKS4, TP, 150.0) == ("EU_A", "EU_B", "US", "JP")

    # レジーム地図: ラベルが4市場ぶんになること＋双子の一方だけを軸にできること
    rg = scan_regime_grid(BLOCKS4, x_values=[115.0, 150.0, 200.0], y_values=[0.0, 0.125],
                          axis_x="fx_usd", axis_y="tariff_rate:EU_B",
                          transfer_price_usd=TP)
    for row in rg["regimes"]:
        for label in row:
            assert len(label.split(">")) == 4
            assert set(label.split(">")) == {"JP", "US", "EU_A", "EU_B"}
    # EU_B にだけ関税を掛けると、双子の順位が入れ替わること
    #（y=0.0 では EU_B が EU_A より上、y=0.125 では下）
    def _pos(label, mkt):
        return label.split(">").index(mkt)
    lo, hi = rg["regimes"][0][1], rg["regimes"][1][1]      # fx=150 の列
    assert _pos(lo, "EU_B") < _pos(lo, "EU_A")
    assert _pos(hi, "EU_B") > _pos(hi, "EU_A")

    # 存在しない市場を軸に指定したら、4市場すべてを挙げてエラーになること
    with pytest.raises(ValueError, match="EU_A"):
        scan_regime_grid(BLOCKS4, x_values=[150.0], y_values=[0.0],
                         axis_x="fx_usd", axis_y="tariff_rate:ZZ",
                         transfer_price_usd=TP)
```

**`_pos()` の向きが実測と合わない場合は、テストを合わせるのではなく理屈を確認してから報告すること。** `EU_B` にだけ関税を掛ければ `EU_B` のマージンは下がるので、`y=0.125` で `EU_B` が `EU_A` より下に来るのが正しい。

---

## 成功基準

- [ ] 新規ファイル `tests/test_allocation_nmarket.py` に4件（`test_markets_of_after_twin_split` / `test_four_market_twin_split_invariance` / `test_four_market_grid_degrades_with_dimension` / `test_four_market_pipeline_runs`）
- [ ] 双子分割で `merit_order` / `true_optimum` が**厳密に不変**
- [ ] 格子の最良点の劣化が **350,692.5 JPY**（±1 JPY）
- [ ] **388件全PASS**（既存384 + 新規4）
- [ ] **実装コードは1行も変更しないこと。** テストだけで通ること自体が Phase 6-2 の正しさの証明である

---

## 実装者への申し送り

**1. テストが落ちたら、テストではなく実装を疑うこと。**
本書のテストコードは、**Claude君が `32b2544` の実装に対して実際に走らせ、4件すべて PASS することを確認済み**である（`pytest` が入っていない環境のため、`pytest.approx` 相当を自作した素の assert で実行）。数値は手計算ではなく実測値なので、転記すればそのまま通るはずである。もし落ちたら、こちらの転記ミスか、何かを見落としている。**数値を合わせにいかず、まず報告すること**（Phase 6-1 の手計算値の件と同じ）。

**2. 双子は「需要だけ半分」であること。**
`dataclasses.replace(src, demand_qty=src.demand_qty / 2)` 以外の項目を触ると、経済条件が同一でなくなり不変性が成立しなくなる。`EU` の `demand_qty` は 35,175（奇数）なので、半分は 17,587.5 の float になる。**int に丸めないこと。**

**3. 新規ファイルにする理由。**
`test_allocation_grid.py` は格子そのものの単体テスト、`test_allocation_nmarket.py` は A系統を貫く End-to-End という切り分けである。Phase 6-3 の階層化テスト（設計書 §7.3 の6件）も後者に入る。

**4. この依頼は Claude君のテスト仕様の穴を埋めるものである。**
Phase 6-2 の実装自体には問題がない。V7 が「格子の性質」だけを見て「N市場で A系統が動くこと」を見ていなかった、という設計側の不足を補うものであり、実装のやり直しではない。
