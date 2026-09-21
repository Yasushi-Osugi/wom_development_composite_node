---
tags: [wom, code]
---
# wom/engine/plugin_base.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/plugin_base.py) · [原文テキスト](../../../90_Raw/wom/engine/plugin_base.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## モジュール説明（docstring原文）

```text
wom/engine/plugin_base.py
──────────────────────────
Base class for WOM planning plugins.

To create a plugin, subclass WOMPlugin and override the hook methods you care about.
Then register it with PluginManager or directly with HookBus.

Example
-------
class MyPlugin(WOMPlugin):
    name = "my_plugin"
    label = "My Plugin"
    description = "Does something useful after backward pass."

    def on_post_backward(self, sc_tree, prod_nm, weeks, config):
        # Modify sc_tree.get_leaf_out_nodes(prod_nm) demand here
        pass
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| ClassDef | `WOMPlugin` | 29 | Abstract base for WOM planning pipeline plugins. |
| FunctionDef | `on_pre_plan` | 48 | Called once before the per-product planning loop. |
| FunctionDef | `on_post_backward` | 51 | Called after BackwardPlanner.run(prod_nm). |
| FunctionDef | `on_post_copy` | 55 | Called after copy_demand_to_supply(sc_tree, prod_nm). |
| FunctionDef | `on_post_forward` | 59 | Called after ForwardPlanner.run(prod_nm). |
| FunctionDef | `on_post_plan` | 63 | Called once after all products are planned. |
| FunctionDef | `register` | 68 | Register all non-trivial hooks with *bus*. |
| FunctionDef | `__repr__` | 80 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/wom/model/sc_tree.py|wom/model/sc_tree.py]]
- [[80_Sources/wom/engine/hook_bus.py|wom/engine/hook_bus.py]]

## 全文（コメント・原文を省略せず収録）

````python
"""
wom/engine/plugin_base.py
──────────────────────────
Base class for WOM planning plugins.

To create a plugin, subclass WOMPlugin and override the hook methods you care about.
Then register it with PluginManager or directly with HookBus.

Example
-------
class MyPlugin(WOMPlugin):
    name = "my_plugin"
    label = "My Plugin"
    description = "Does something useful after backward pass."

    def on_post_backward(self, sc_tree, prod_nm, weeks, config):
        # Modify sc_tree.get_leaf_out_nodes(prod_nm) demand here
        pass
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wom.model.sc_tree import SCTree
    from wom.engine.hook_bus import HookBus


class WOMPlugin:
    """
    Abstract base for WOM planning pipeline plugins.

    Subclass and override the on_* methods you need.
    All on_* methods default to no-op so you only override what you use.
    """

    #: Machine-readable identifier (must be unique across plugins)
    name: str = "unnamed_plugin"

    #: Human-readable label shown in the GUI
    label: str = "Unnamed Plugin"

    #: Short description shown as tooltip in GUI
    description: str = ""

    # ── Hook callbacks (override as needed) ───────────────────────────────────

    def on_pre_plan(self, sc_tree, weeks: list, config: dict, **kw) -> None:
        """Called once before the per-product planning loop."""

    def on_post_backward(self, sc_tree, prod_nm: str,
                         weeks: list, config: dict, **kw) -> None:
        """Called after BackwardPlanner.run(prod_nm)."""

    def on_post_copy(self, sc_tree, prod_nm: str,
                     weeks: list, config: dict, **kw) -> None:
        """Called after copy_demand_to_supply(sc_tree, prod_nm)."""

    def on_post_forward(self, sc_tree, prod_nm: str,
                        weeks: list, config: dict, **kw) -> None:
        """Called after ForwardPlanner.run(prod_nm)."""

    def on_post_plan(self, sc_tree, weeks: list, config: dict, **kw) -> None:
        """Called once after all products are planned."""

    # ── Registration helper ───────────────────────────────────────────────────

    def register(self, bus: "HookBus") -> None:
        """Register all non-trivial hooks with *bus*."""
        from wom.engine.hook_bus import (
            HOOK_PRE_PLAN, HOOK_POST_BACKWARD, HOOK_POST_COPY,
            HOOK_POST_FORWARD, HOOK_POST_PLAN,
        )
        bus.register(HOOK_PRE_PLAN,      self.on_pre_plan)
        bus.register(HOOK_POST_BACKWARD, self.on_post_backward)
        bus.register(HOOK_POST_COPY,     self.on_post_copy)
        bus.register(HOOK_POST_FORWARD,  self.on_post_forward)
        bus.register(HOOK_POST_PLAN,     self.on_post_plan)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"

````
