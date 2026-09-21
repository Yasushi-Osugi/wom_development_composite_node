---
tags: [wom, code]
---
# tests/test_allocation_plot.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tests/test_allocation_plot.py) · [原文テキスト](../../90_Raw/tests/test_allocation_plot.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/02_Demand_Allocation|Optimization on Demand Allocation]]

## モジュール説明（docstring原文）

```text
tests/test_allocation_plot.py — 可視化のスモークテスト（Phase 2）
================================================================
`tools/plot_allocation_map` の各描画関数が例外なく画像を生成することを固定する。
（matplotlib Agg。中身の見た目は人手 QA。ここは "コード経路が壊れていない" ことの網。）
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_nonempty` | 29 | docstringなし（下のコード参照） |
| FunctionDef | `test_plot_tile` | 33 | docstringなし（下のコード参照） |
| FunctionDef | `test_plot_layers` | 38 | docstringなし（下のコード参照） |
| FunctionDef | `test_plot_single_with_point` | 43 | docstringなし（下のコード参照） |
| FunctionDef | `test_plot_terrain_only` | 48 | docstringなし（下のコード参照） |
| FunctionDef | `test_plot_each_scenario` | 53 | docstringなし（下のコード参照） |
| FunctionDef | `test_bx_s_format` | 61 | docstringなし（下のコード参照） |
| FunctionDef | `test_plot_allocation_map_rejects_n4` | 65 | 三角図は N=3 専用（Phase 6-2 V6）。N>=4 は明示エラー、N=3 は通る。 |

## 関連する知識源

- [[80_Sources/tools/plot_allocation_map.py|tools/plot_allocation_map.py]]
- [[80_Sources/wom/allocation/cost_block.py|wom/allocation/cost_block.py]]
- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
tests/test_allocation_plot.py — 可視化のスモークテスト（Phase 2）
================================================================
`tools/plot_allocation_map` の各描画関数が例外なく画像を生成することを固定する。
（matplotlib Agg。中身の見た目は人手 QA。ここは "コード経路が壊れていない" ことの網。）
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib
matplotlib.use("Agg")

import pytest

from tools.plot_allocation_map import (
    plot_tile, plot_layers, plot_single, plot_terrain_only, plot_each_scenario, bx_s,
    _require_three_markets,
)
from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.transmission import CostBlock

ALLOC_DIR = os.path.join(os.path.dirname(__file__), "..",
                         "data", "sample", "soysauce-jpy-2027-alloc")


def _nonempty(p):
    return os.path.exists(p) and os.path.getsize(p) > 1000


def test_plot_tile(tmp_path):
    out = str(tmp_path / "tile.png")
    assert _nonempty(plot_tile(ALLOC_DIR, 800, out))


def test_plot_layers(tmp_path):
    out = str(tmp_path / "layers.png")
    assert _nonempty(plot_layers(ALLOC_DIR, 800, out))


def test_plot_single_with_point(tmp_path):
    out = str(tmp_path / "s4.png")
    assert _nonempty(plot_single(ALLOC_DIR, "s4_compound", 800, out, point=(0.45, 0.55)))


def test_plot_terrain_only(tmp_path):
    out = str(tmp_path / "terrain_s1.png")
    assert _nonempty(plot_terrain_only(ALLOC_DIR, "s1_base", 800, out))


def test_plot_each_scenario(tmp_path):
    made = plot_each_scenario(ALLOC_DIR, 800, str(tmp_path / "terrains"))
    # s1-s7 + s9_fta_cliff（Phase 5、s8は時系列で対象外）。
    # s9 は cap_wk=500 前提の合成シナリオだが、本テストの cap_wk=800 では
    # cliff が発動しない条件（Phase5設計書§2.2）でも例外にはならず描画できる。
    assert len(made) == 8 and all(_nonempty(p) for p in made)


def test_bx_s_format():
    assert bx_s((0.1, 0.45, 0.45)) == "0.10/0.45/0.45"


def test_plot_allocation_map_rejects_n4():
    """三角図は N=3 専用（Phase 6-2 V6）。N>=4 は明示エラー、N=3 は通る。"""
    blocks4 = {f"M{i}": CostBlock(usd=0, eur=0, jpy=100, tariff_rate=0.0,
                                  price_local=200, ccy="JPY", demand_qty=100,
                     material_usd_base=6.0)
              for i in range(4)}
    with pytest.raises(ValueError, match="3 markets"):
        _require_three_markets(blocks4)

    blocks3, _tp = derive_cost_blocks(ALLOC_DIR)
    _require_three_markets(blocks3)   # 例外を投げないこと


if __name__ == "__main__":
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        test_plot_tile(p); test_plot_layers(p); test_plot_single_with_point(p)
    test_bx_s_format()
    print("All allocation plot smoke tests passed.")

````
