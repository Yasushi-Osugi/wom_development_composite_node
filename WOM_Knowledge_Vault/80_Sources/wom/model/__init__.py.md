---
tags: [wom, code]
---
# wom/model/__init__.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/model/__init__.py) · [原文テキスト](../../../90_Raw/wom/model/__init__.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/01_Data_Building|Data Building]]

## モジュール説明（docstring原文）

```text
wom.model — WOM Planning Layer
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|

## 関連する知識源

- [[80_Sources/wom/model/plan_node.py|wom/model/plan_node.py]]
- [[80_Sources/wom/model/sc_tree.py|wom/model/sc_tree.py]]
- [[80_Sources/wom/model/lot_generator.py|wom/model/lot_generator.py]]

## 全文（コメント・原文を省略せず収録）

````python
"""
wom.model — WOM Planning Layer
"""
from wom.model.plan_node import (
    PlanNode,
    S, CO, I, P,
    PSI_BUCKETS, PSI_BUCKET_NAMES,
    CAP_HARD, CAP_SOFT,
    NODE_TYPE_LEAF_OUT,
    NODE_TYPE_DAD,
    NODE_TYPE_SUPPLY_POINT,
    NODE_TYPE_MOM,
    NODE_TYPE_LEAF_IN,
)
from wom.model.sc_tree import (
    SCTree,
    BridgeTransfer,
    build_demo_sc_tree,
)
from wom.model.lot_generator import (
    LotIDGenerator,
    LotAssignmentResult,
    assign_demand_lots_from_df,
    assign_demand_lots_from_dict,
    lots_to_qty,
    qty_to_lot_count,
)

__all__ = [
    # plan_node
    "PlanNode",
    "S", "CO", "I", "P",
    "PSI_BUCKETS", "PSI_BUCKET_NAMES",
    "CAP_HARD", "CAP_SOFT",
    "NODE_TYPE_LEAF_OUT", "NODE_TYPE_DAD", "NODE_TYPE_SUPPLY_POINT",
    "NODE_TYPE_MOM", "NODE_TYPE_LEAF_IN",
    # sc_tree
    "SCTree", "BridgeTransfer", "build_demo_sc_tree",
    # lot_generator
    "LotIDGenerator", "LotAssignmentResult",
    "assign_demand_lots_from_df", "assign_demand_lots_from_dict",
    "lots_to_qty", "qty_to_lot_count",
]

````
