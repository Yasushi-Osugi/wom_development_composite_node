---
tags: [wom, code]
---
# wom/plugins/__init__.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/plugins/__init__.py) · [原文テキスト](../../../90_Raw/wom/plugins/__init__.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/03_Planning|Planning]]

## モジュール説明（docstring原文）

```text
WOM built-in plugins.
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|

## 関連する知識源

- [[80_Sources/wom/plugins/demand_smoothing.py|wom/plugins/demand_smoothing.py]]
- [[80_Sources/wom/plugins/capacity_override.py|wom/plugins/capacity_override.py]]
- [[80_Sources/wom/plugins/buffering_stock_optimizer.py|wom/plugins/buffering_stock_optimizer.py]]
- [[80_Sources/wom/engine/harvest_batch_plugin.py|wom/engine/harvest_batch_plugin.py]]
- [[80_Sources/wom/engine/holiday_calendar_plugin.py|wom/engine/holiday_calendar_plugin.py]]

## 全文（コメント・原文を省略せず収録）

````python
"""WOM built-in plugins."""
from wom.plugins.demand_smoothing         import DemandSmoothingPlugin
from wom.plugins.capacity_override        import CapacityOverridePlugin
from wom.plugins.buffering_stock_optimizer import BufferingStockOptimizerPlugin
from wom.engine.harvest_batch_plugin      import HarvestBatchPlugin
from wom.engine.holiday_calendar_plugin   import HolidayCalendarPlugin

ALL_BUILTIN_PLUGINS = [
    DemandSmoothingPlugin,
    CapacityOverridePlugin,
    BufferingStockOptimizerPlugin,
    HarvestBatchPlugin,
    HolidayCalendarPlugin,
]

````
