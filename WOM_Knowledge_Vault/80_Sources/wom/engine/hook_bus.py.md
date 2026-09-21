---
tags: [wom, code]
---
# wom/engine/hook_bus.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/hook_bus.py) · [原文テキスト](../../../90_Raw/wom/engine/hook_bus.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## モジュール説明（docstring原文）

```text
wom/engine/hook_bus.py
──────────────────────
Planning pipeline hook bus.

Hook points (fired in order):
  HOOK_PRE_PLAN      – before per-product loop (sc_tree built, lots assigned)
  HOOK_POST_BACKWARD – after BackwardPlanner.run(prod_nm)
  HOOK_POST_COPY     – after copy_demand_to_supply(sc_tree, prod_nm)
  HOOK_POST_FORWARD  – after ForwardPlanner.run(prod_nm)
  HOOK_POST_PLAN     – after all products planned

Context dict keys available at each hook:
  sc_tree   : SCTree
  weeks     : list[str]
  config    : dict  (n_weeks, start_week, ...)
  prod_nm   : str | None  (None for PRE/POST_PLAN)
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| ClassDef | `HookBus` | 39 | Lightweight publish-subscribe bus for the planning pipeline. |
| FunctionDef | `__init__` | 50 | docstringなし（下のコード参照） |
| FunctionDef | `register` | 55 | Register *fn* to be called when *hook* fires. |
| FunctionDef | `unregister` | 61 | Remove a previously registered callback (no-op if not found). |
| FunctionDef | `clear` | 66 | Remove all registered callbacks. |
| FunctionDef | `fire` | 73 | Fire *hook*, calling each registered listener with **ctx as keyword args. |
| FunctionDef | `listener_count` | 88 | docstringなし（下のコード参照） |
| FunctionDef | `__repr__` | 91 | docstringなし（下のコード参照） |

## 全文（コメント・原文を省略せず収録）

````python
"""
wom/engine/hook_bus.py
──────────────────────
Planning pipeline hook bus.

Hook points (fired in order):
  HOOK_PRE_PLAN      – before per-product loop (sc_tree built, lots assigned)
  HOOK_POST_BACKWARD – after BackwardPlanner.run(prod_nm)
  HOOK_POST_COPY     – after copy_demand_to_supply(sc_tree, prod_nm)
  HOOK_POST_FORWARD  – after ForwardPlanner.run(prod_nm)
  HOOK_POST_PLAN     – after all products planned

Context dict keys available at each hook:
  sc_tree   : SCTree
  weeks     : list[str]
  config    : dict  (n_weeks, start_week, ...)
  prod_nm   : str | None  (None for PRE/POST_PLAN)
"""

from __future__ import annotations
from typing import Callable, Dict, List

# ── Hook name constants ────────────────────────────────────────────────────────
HOOK_PRE_PLAN      = "pre_plan"
HOOK_POST_BACKWARD = "post_backward"
HOOK_POST_COPY     = "post_copy"
HOOK_POST_FORWARD  = "post_forward"
HOOK_POST_PLAN     = "post_plan"

ALL_HOOKS = [
    HOOK_PRE_PLAN,
    HOOK_POST_BACKWARD,
    HOOK_POST_COPY,
    HOOK_POST_FORWARD,
    HOOK_POST_PLAN,
]


class HookBus:
    """
    Lightweight publish-subscribe bus for the planning pipeline.

    Usage
    -----
    bus = HookBus()
    bus.register(HOOK_POST_BACKWARD, my_fn)
    bus.fire(HOOK_POST_BACKWARD, sc_tree=sc_tree, prod_nm=prod, weeks=weeks, config=cfg)
    """

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable]] = {h: [] for h in ALL_HOOKS}

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, hook: str, fn: Callable) -> None:
        """Register *fn* to be called when *hook* fires."""
        if hook not in self._listeners:
            raise ValueError(f"Unknown hook: {hook!r}. Valid: {ALL_HOOKS}")
        self._listeners[hook].append(fn)

    def unregister(self, hook: str, fn: Callable) -> None:
        """Remove a previously registered callback (no-op if not found)."""
        if hook in self._listeners:
            self._listeners[hook] = [f for f in self._listeners[hook] if f is not fn]

    def clear(self) -> None:
        """Remove all registered callbacks."""
        for h in ALL_HOOKS:
            self._listeners[h] = []

    # ── Firing ────────────────────────────────────────────────────────────────

    def fire(self, hook: str, **ctx) -> None:
        """
        Fire *hook*, calling each registered listener with **ctx as keyword args.
        Exceptions in listeners are caught and printed (non-fatal).
        """
        for fn in list(self._listeners.get(hook, [])):
            try:
                fn(**ctx)
            except Exception as exc:  # noqa: BLE001
                import traceback
                print(f"[HookBus] Error in {hook!r} listener {fn!r}: {exc}")
                traceback.print_exc()

    # ── Introspection ─────────────────────────────────────────────────────────

    def listener_count(self, hook: str) -> int:
        return len(self._listeners.get(hook, []))

    def __repr__(self) -> str:
        parts = [f"{h}:{len(v)}" for h, v in self._listeners.items() if v]
        return f"HookBus({', '.join(parts)})"

````
