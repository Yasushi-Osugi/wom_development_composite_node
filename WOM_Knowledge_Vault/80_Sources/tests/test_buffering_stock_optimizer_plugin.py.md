---
tags: [wom, code]
---
# tests/test_buffering_stock_optimizer_plugin.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tests/test_buffering_stock_optimizer_plugin.py) · [原文テキスト](../../90_Raw/tests/test_buffering_stock_optimizer_plugin.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/01_Data_Building|Data Building]] / [[10_Functions/03_Planning|Planning]]

## モジュール説明（docstring原文）

```text
tests/test_buffering_stock_optimizer_plugin.py
BufferingStockOptimizerPlugin (wom/plugins/buffering_stock_optimizer.py)
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `get_node` | 18 | docstringなし（下のコード参照） |
| FunctionDef | `_build_single_lane` | 25 | supply_point -> DAD(JP) -> leaf_out(JP); ss_days on leaf_out only, |
| FunctionDef | `_write_config_csv` | 46 | docstringなし（下のコード参照） |
| FunctionDef | `_write_node_cost_csv` | 53 | docstringなし（下のコード参照） |
| FunctionDef | `_fake_cap_path` | 60 | docstringなし（下のコード参照） |
| FunctionDef | `test_plugin_noop_without_config_file` | 66 | docstringなし（下のコード参照） |
| FunctionDef | `test_plugin_noop_when_disabled` | 77 | docstringなし（下のコード参照） |
| FunctionDef | `test_plugin_applies_best_placement_when_enabled` | 90 | docstringなし（下のコード参照） |
| FunctionDef | `test_plugin_ignores_other_skus` | 116 | A config row for a different SKU must not affect this SKU. |

## 関連する知識源

- [[80_Sources/wom/plugins/buffering_stock_optimizer.py|wom/plugins/buffering_stock_optimizer.py]]
- [[80_Sources/wom/model/plan_node.py|wom/model/plan_node.py]]
- [[80_Sources/wom/model/sc_tree.py|wom/model/sc_tree.py]]
- [[80_Sources/wom/model/lot_generator.py|wom/model/lot_generator.py]]
- [[80_Sources/wom/engine/backward_planner.py|wom/engine/backward_planner.py]]

## 全文（コメント・原文を省略せず収録）

````python
"""
tests/test_buffering_stock_optimizer_plugin.py
BufferingStockOptimizerPlugin (wom/plugins/buffering_stock_optimizer.py)
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from wom.model.plan_node import S, CO, I, P
from wom.model.sc_tree       import build_demo_sc_tree
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner
from wom.plugins.buffering_stock_optimizer import BufferingStockOptimizerPlugin


def get_node(sc_tree, prod_nm, node_id):
    for node in sc_tree.iter_all_nodes(prod_nm):
        if node.node_id == node_id:
            return node
    raise ValueError(f"{node_id!r} not found")


def _build_single_lane():
    """supply_point -> DAD(JP) -> leaf_out(JP); ss_days on leaf_out only,
    so (per test_decouple_optimizer.py) DAD is the lower-cost / equal-
    shortfall placement -- i.e. the plugin should end up flagging DAD."""
    sku_id = "SKU-A"
    n_weeks = 26
    weeks = [f"2024-W{i:02d}" for i in range(1, n_weeks + 1)]
    rows = [{"sku_id": sku_id, "sku_name": "A", "region": "JP", "lead_time_wks": 1}]
    sc_tree = build_demo_sc_tree(pd.DataFrame(rows), weeks, lt_wks_ot=1, lt_wks_in=2)

    dad  = get_node(sc_tree, sku_id, f"OUT:DC:JP:{sku_id}")
    leaf = get_node(sc_tree, sku_id, f"OUT:Sales:JP:{sku_id}")
    dad.ss_days  = 0
    leaf.ss_days = 14

    demand_dict = {(sku_id, "JP", "2024-W15"): 6}
    assign_demand_lots_from_dict(sc_tree, demand_dict, cpu_size=1)
    BackwardPlanner(sc_tree).run(sku_id)
    return sc_tree, sku_id, weeks, dad, leaf


def _write_config_csv(tmp_path, sku_id, enabled, max_shortfall_ratio=None):
    row = {"sku_id": sku_id, "enabled": enabled}
    if max_shortfall_ratio is not None:
        row["max_shortfall_ratio"] = max_shortfall_ratio
    pd.DataFrame([row]).to_csv(tmp_path / "decouple_optimizer_config.csv", index=False)


def _write_node_cost_csv(tmp_path, sku_id, dad, leaf):
    pd.DataFrame([
        {"sku_id": sku_id, "node_name": dad.node_name,  "unit_cost_per_lot": 5.0},
        {"sku_id": sku_id, "node_name": leaf.node_name, "unit_cost_per_lot": 5.0},
    ]).to_csv(tmp_path / "node_cost_master.csv", index=False)


def _fake_cap_path(tmp_path):
    # BufferingStockOptimizerPlugin only ever calls os.path.dirname() on
    # cap_path -- the file need not actually exist.
    return str(tmp_path / "capacity_plan.csv")


def test_plugin_noop_without_config_file(tmp_path):
    sc_tree, sku_id, weeks, dad, leaf = _build_single_lane()
    config = {"cap_path": _fake_cap_path(tmp_path)}   # no decouple_optimizer_config.csv written

    BufferingStockOptimizerPlugin().on_post_backward(sc_tree, sku_id, weeks, config)

    assert dad.is_decoupling is False
    assert leaf.is_decoupling is False
    print("PASS: test_plugin_noop_without_config_file")


def test_plugin_noop_when_disabled(tmp_path):
    sc_tree, sku_id, weeks, dad, leaf = _build_single_lane()
    _write_config_csv(tmp_path, sku_id, enabled=0)
    _write_node_cost_csv(tmp_path, sku_id, dad, leaf)
    config = {"cap_path": _fake_cap_path(tmp_path)}

    BufferingStockOptimizerPlugin().on_post_backward(sc_tree, sku_id, weeks, config)

    assert dad.is_decoupling is False
    assert leaf.is_decoupling is False
    print("PASS: test_plugin_noop_when_disabled")


def test_plugin_applies_best_placement_when_enabled(tmp_path):
    sc_tree, sku_id, weeks, dad, leaf = _build_single_lane()
    _write_config_csv(tmp_path, sku_id, enabled=1, max_shortfall_ratio=1.10)
    _write_node_cost_csv(tmp_path, sku_id, dad, leaf)
    config = {"cap_path": _fake_cap_path(tmp_path)}

    BufferingStockOptimizerPlugin().on_post_backward(sc_tree, sku_id, weeks, config)

    # DAD is the cost-optimal / equal-shortfall placement here (see
    # test_decouple_optimizer.py::test_evaluate_decouple_placement_ss_days_only_visible_when_not_pulled).
    assert dad.is_decoupling is True
    assert leaf.is_decoupling is False

    # Supply layer must be left cleared -- the pipeline's official
    # copy_demand_to_supply (which fires immediately after this hook)
    # is responsible for rebuilding it for the real Forward Planning pass.
    n_weeks = len(weeks)
    for node in (dad, leaf):
        for w in range(n_weeks):
            assert node.psi4supply[w][S]  == []
            assert node.psi4supply[w][CO] == []
            assert node.psi4supply[w][I]  == []
            assert node.psi4supply[w][P]  == []
    print("PASS: test_plugin_applies_best_placement_when_enabled")


def test_plugin_ignores_other_skus(tmp_path):
    """A config row for a different SKU must not affect this SKU."""
    sc_tree, sku_id, weeks, dad, leaf = _build_single_lane()
    _write_config_csv(tmp_path, "SOME_OTHER_SKU", enabled=1)
    _write_node_cost_csv(tmp_path, sku_id, dad, leaf)
    config = {"cap_path": _fake_cap_path(tmp_path)}

    BufferingStockOptimizerPlugin().on_post_backward(sc_tree, sku_id, weeks, config)

    assert dad.is_decoupling is False
    assert leaf.is_decoupling is False
    print("PASS: test_plugin_ignores_other_skus")

````
