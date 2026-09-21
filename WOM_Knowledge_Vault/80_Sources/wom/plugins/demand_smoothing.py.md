---
tags: [wom, code]
---
# wom/plugins/demand_smoothing.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/plugins/demand_smoothing.py) · [原文テキスト](../../../90_Raw/wom/plugins/demand_smoothing.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/03_Planning|Planning]]

## モジュール説明（docstring原文）

```text
wom/plugins/demand_smoothing.py
────────────────────────────────
DemandSmoothingPlugin
  Hook: POST_BACKWARD

  After BackwardPlanner propagates demand to all InBound nodes,
  this plugin applies a simple 3-week moving-average smoothing to the
  psi4demand[w][S] lot list of the MOM node.

  Purpose: reduces "lumpy demand" spikes that cause excessive CO carry-over
  and CapHard violations.

  Algorithm
  ---------
  For each MOM node of prod_nm:
    For each week w (with padding at edges):
      avg_qty = mean(len(psi4demand[w-1][S]), len(psi4demand[w][S]), len(psi4demand[w+1][S]))
      Redistribute lots in psi4demand[w][S] so total count ≈ round(avg_qty).
      (Lots are borrowed from / returned to adjacent weeks symmetrically.)
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| ClassDef | `DemandSmoothingPlugin` | 28 | docstringなし（下のコード参照） |
| FunctionDef | `on_post_backward` | 34 | Smooth psi4demand[w][S] on the MOM node with a 3-wk moving average. |

## 関連する知識源

- [[80_Sources/wom/engine/plugin_base.py|wom/engine/plugin_base.py]]
- [[80_Sources/wom/model/plan_node.py|wom/model/plan_node.py]]

## 全文（コメント・原文を省略せず収録）

````python
"""
wom/plugins/demand_smoothing.py
────────────────────────────────
DemandSmoothingPlugin
  Hook: POST_BACKWARD

  After BackwardPlanner propagates demand to all InBound nodes,
  this plugin applies a simple 3-week moving-average smoothing to the
  psi4demand[w][S] lot list of the MOM node.

  Purpose: reduces "lumpy demand" spikes that cause excessive CO carry-over
  and CapHard violations.

  Algorithm
  ---------
  For each MOM node of prod_nm:
    For each week w (with padding at edges):
      avg_qty = mean(len(psi4demand[w-1][S]), len(psi4demand[w][S]), len(psi4demand[w+1][S]))
      Redistribute lots in psi4demand[w][S] so total count ≈ round(avg_qty).
      (Lots are borrowed from / returned to adjacent weeks symmetrically.)
"""

from __future__ import annotations
from wom.engine.plugin_base import WOMPlugin
from wom.model.plan_node import S


class DemandSmoothingPlugin(WOMPlugin):
    name        = "demand_smoothing"
    label       = "Demand Smoothing (3-wk MA)"
    description = ("Applies a 3-week moving-average to MOM demand after "
                   "BackwardPlanner, reducing lumpy demand spikes.")

    def on_post_backward(self, sc_tree, prod_nm: str,
                         weeks: list, config: dict, **kw) -> None:
        """Smooth psi4demand[w][S] on the MOM node with a 3-wk moving average."""
        try:
            mom = sc_tree.get_in_root(prod_nm)
        except Exception:
            return

        n = len(weeks)
        demand = mom.psi4demand   # list of lists: [week][bucket] = [lot_id,...]

        # Compute smoothed target quantities (round to int)
        orig = [len(demand[w][S]) for w in range(n)]
        smoothed = []
        for w in range(n):
            neighbors = [orig[i] for i in (w - 1, w, w + 1) if 0 <= i < n]
            smoothed.append(round(sum(neighbors) / len(neighbors)))

        # Redistribute lots: we pool all S-lots across the horizon and
        # re-assign them week-by-week to match smoothed targets.
        all_lots: list = []
        for w in range(n):
            all_lots.extend(demand[w][S])
            demand[w][S] = []

        idx = 0
        for w in range(n):
            qty = smoothed[w]
            chunk = all_lots[idx: idx + qty]
            demand[w][S] = chunk
            idx += qty
        # Any remainder goes into the last week
        if idx < len(all_lots):
            demand[n - 1][S].extend(all_lots[idx:])

````
