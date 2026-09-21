---
tags: [wom, code]
---
# tests/test_allocation_transmission.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tests/test_allocation_transmission.py) · [原文テキスト](../../90_Raw/tests/test_allocation_transmission.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/02_Demand_Allocation|Optimization on Demand Allocation]]

## モジュール説明（docstring原文）

```text
tests/test_allocation_transmission.py — 伝達式 単体（Unit）テスト
================================================================
`wom/allocation/transmission.py` の Step 1〜5（単位 P&L）が、参照実装
`tools/proto_terrain2.py` と仕様書 §5 / 付録 A.1 の手計算値を再現することを固定する。

「231 点のループより前に、1 点が正しいことを確認する」（Request Letter §2.3）。
受け入れ基準 #1（Step ごとの一致）・#2（基準点還元）に対応。

チャネル原価ブロックは参照実装 proto_terrain2.py 由来の固定値（soysauce 導出結果）。
CSV からの導出（Step 0.5）は cost_block.py の役割で、別テストで担保する。
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `test_unit_margin_matches_appendix_a1` | 44 | docstringなし（下のコード参照） |
| FunctionDef | `test_appendix_a1_rounded_labels` | 52 | 付録表の丸め表記（1748 / 1832 等）とも整合すること。 |
| FunctionDef | `test_step4_cost_and_price_base` | 60 | Step 4/5：基準（FX150・原料$6）の原価・売価（仕様 §5 Step4 表）。 |
| FunctionDef | `test_base_point_reduction` | 74 | 受入 #2 基準点還元：cost = usd×fx + eur×(fx×1.08) + jpy が成立（FX 適用の健全性）。 |
| FunctionDef | `test_fx_exposure_components` | 86 | FCR/FRR 用の外貨建成分：JP は frev=0（円建売価）、輸出は frev=rev。 |

## 関連する知識源

- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]
- [[80_Sources/tools/proto_terrain2.py|tools/proto_terrain2.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
tests/test_allocation_transmission.py — 伝達式 単体（Unit）テスト
================================================================
`wom/allocation/transmission.py` の Step 1〜5（単位 P&L）が、参照実装
`tools/proto_terrain2.py` と仕様書 §5 / 付録 A.1 の手計算値を再現することを固定する。

「231 点のループより前に、1 点が正しいことを確認する」（Request Letter §2.3）。
受け入れ基準 #1（Step ごとの一致）・#2（基準点還元）に対応。

チャネル原価ブロックは参照実装 proto_terrain2.py 由来の固定値（soysauce 導出結果）。
CSV からの導出（Step 0.5）は cost_block.py の役割で、別テストで担保する。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.allocation.transmission import CostBlock, Scenario, rates, unit_pnl


# --- soysauce 3 チャネルの原価ブロック（proto_terrain2.py / 仕様 §5 Step0.5 導出表）---
JP = CostBlock(usd=9.10,  eur=0.00, jpy=1725, tariff_rate=0.00,  price_local=3840.0, ccy="JPY", demand_qty=30150,
                     material_usd_base=6.0)
US = CostBlock(usd=15.65, eur=0.00, jpy=1575, tariff_rate=0.125, price_local=40.0,   ccy="USD", demand_qty=35176,
                     material_usd_base=6.0)
EU = CostBlock(usd=14.60, eur=2.15, jpy=1575, tariff_rate=0.08,  price_local=38.0,   ccy="EUR", demand_qty=35175,
                     material_usd_base=6.0)
CH = {"JP": JP, "US": US, "EU": EU}

# 付録 A.1 の単位マージン期待値（JPY/lot、EUR=USD×1.08、transfer_price=17.6）
#   小数以下は proto の非丸め値（付録表は四捨五入表記）
EXPECTED_MARGIN = {
    (150, 6.0): {"JP": 750.0,   "US": 1747.5, "EU": 1831.5},
    (200, 6.0): {"JP": 295.0,   "US": 2855.0, "EU": 2967.0},
    (200, 8.0): {"JP": -105.0,  "US": 2455.0, "EU": 2567.0},
    (115, 6.0): {"JP": 1068.5,  "US": 972.25, "EU": 1036.65},
}


@pytest.mark.parametrize("fx,mat", list(EXPECTED_MARGIN.keys()))
def test_unit_margin_matches_appendix_a1(fx, mat):
    sc = Scenario(fx_usd=fx, material_usd=mat)
    for m, cb in CH.items():
        got = unit_pnl(cb, sc)["margin"]
        exp = EXPECTED_MARGIN[(fx, mat)][m]
        assert got == pytest.approx(exp, abs=1e-6), f"{m} @FX{fx}/${mat}: {got} != {exp}"


def test_appendix_a1_rounded_labels():
    """付録表の丸め表記（1748 / 1832 等）とも整合すること。"""
    sc = Scenario(fx_usd=150, material_usd=6.0)
    assert round(unit_pnl(US, sc)["margin"]) == 1748
    assert round(unit_pnl(EU, sc)["margin"]) == 1832
    assert round(unit_pnl(JP, sc)["margin"]) == 750


def test_step4_cost_and_price_base():
    """Step 4/5：基準（FX150・原料$6）の原価・売価（仕様 §5 Step4 表）。"""
    sc = Scenario(fx_usd=150, material_usd=6.0)
    exp = {
        "JP": {"cost": 3090.0, "rev": 3840.0},
        "US": {"cost": 4252.5, "rev": 6000.0},
        "EU": {"cost": 4324.5, "rev": 6156.0},
    }
    for m, cb in CH.items():
        u = unit_pnl(cb, sc)
        assert u["cost"] == pytest.approx(exp[m]["cost"], abs=1e-6), f"{m} cost"
        assert u["rev"] == pytest.approx(exp[m]["rev"], abs=1e-6), f"{m} rev"


def test_base_point_reduction():
    """受入 #2 基準点還元：cost = usd×fx + eur×(fx×1.08) + jpy が成立（FX 適用の健全性）。"""
    sc = Scenario(fx_usd=150, material_usd=6.0)
    r = rates(sc)
    assert r == {"JPY": 1.0, "USD": 150.0, "EUR": 150.0 * 1.08}
    for cb in CH.values():
        u = unit_pnl(cb, sc)
        usd_eff = cb.usd - cb.material_usd_base + sc.material_usd + cb.tariff_rate * (16.0 * 1.1)
        hand = usd_eff * r["USD"] + cb.eur * r["EUR"] + cb.jpy
        assert u["cost"] == pytest.approx(hand, abs=1e-9)


def test_fx_exposure_components():
    """FCR/FRR 用の外貨建成分：JP は frev=0（円建売価）、輸出は frev=rev。"""
    sc = Scenario(fx_usd=150, material_usd=6.0)
    assert unit_pnl(JP, sc)["frev"] == 0.0            # 国内は売価が円建て
    assert unit_pnl(US, sc)["frev"] == unit_pnl(US, sc)["rev"]
    assert unit_pnl(EU, sc)["frev"] == unit_pnl(EU, sc)["rev"]
    # 外貨建コスト（fcost）は円建ブロック jpy を含まない
    assert unit_pnl(JP, sc)["fcost"] == pytest.approx(9.10 * 150, abs=1e-6)


if __name__ == "__main__":
    for fx, mat in EXPECTED_MARGIN:
        test_unit_margin_matches_appendix_a1(fx, mat)
    test_appendix_a1_rounded_labels()
    test_step4_cost_and_price_base()
    test_base_point_reduction()
    test_fx_exposure_components()
    print("All allocation transmission (unit) tests passed.")

````
