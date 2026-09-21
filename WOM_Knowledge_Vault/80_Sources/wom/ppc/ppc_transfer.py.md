---
tags: [wom, code]
---
# wom/ppc/ppc_transfer.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/ppc/ppc_transfer.py) · [原文テキスト](../../../90_Raw/wom/ppc/ppc_transfer.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/04_Evaluation|Evaluation]]

## モジュール説明（docstring原文）

```text
wom/ppc/ppc_transfer.py
=======================
Step 2: Transfer Price Determination.

Design Decision D2 (Rev.2):
    - Method: cost_plus (only method in this slice)
    - Formula: transfer_price = MOM_accumulated_unit_cost × (1 + margin_rate)
    - MOM accumulated cost = supplier_cost + conversion_cost + inbound_logistics
    - Transfer price is computed ONCE here and stored on LotCostAccumulator.
    - It MUST NOT be recomputed during backward pass.
    - All subsequent tariff/landed cost calculations use this fixed value.

mom_node accepts either str or dict[product_id -> node_id].
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_resolve_node` | 27 | docstringなし（下のコード参照） |
| FunctionDef | `run_transfer_price_determination` | 33 | Step 2: Set transfer_price on each accumulator. |

## 全文（コメント・原文を省略せず収録）

````python
"""
wom/ppc/ppc_transfer.py
=======================
Step 2: Transfer Price Determination.

Design Decision D2 (Rev.2):
    - Method: cost_plus (only method in this slice)
    - Formula: transfer_price = MOM_accumulated_unit_cost × (1 + margin_rate)
    - MOM accumulated cost = supplier_cost + conversion_cost + inbound_logistics
    - Transfer price is computed ONCE here and stored on LotCostAccumulator.
    - It MUST NOT be recomputed during backward pass.
    - All subsequent tariff/landed cost calculations use this fixed value.

mom_node accepts either str or dict[product_id -> node_id].
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Union

from .ppc_models import LotCostAccumulator, PPCEvent
from .ppc_fx import FXConverter
from .ppc_rules import PPCRuleSet


def _resolve_node(node: Union[str, Dict[str, str]], product_id: str) -> str:
    if isinstance(node, dict):
        return node.get(product_id, next(iter(node.values()), ""))
    return node


def run_transfer_price_determination(
    accumulators: List[LotCostAccumulator],
    rules: PPCRuleSet,
    fx: FXConverter,
    mom_node: Union[str, Dict[str, str]] = "MOM_China",
) -> List[PPCEvent]:
    """
    Step 2: Set transfer_price on each accumulator.

    mom_node : MOM node_id string OR dict[product_id -> node_id]
    """
    events: List[PPCEvent] = []
    _counter = itertools.count(1)

    for acc in accumulators:
        product = acc.product_id
        week = acc.week
        m_node = _resolve_node(mom_node, product)

        tp_rule = rules.get_transfer_price_rule(m_node, product)
        if tp_rule is None:
            tp_local = 0.0
            tp_currency = "JPY"
            tp_base = (
                acc.supplier_cost_base
                + acc.conversion_cost_base
                + acc.logistics_in_base
            )
            acc.transfer_price_local = 0.0
            acc.transfer_price_base = tp_base
        elif str(tp_rule["method"]) == "cost_plus":
            margin_rate = float(tp_rule["margin_rate"])
            tp_currency = str(tp_rule["currency"])

            mom_fx_rate, _ = fx.get_rate(week, tp_currency)
            if mom_fx_rate == 0:
                mom_fx_rate = 1.0

            accumulated_local = (
                acc.supplier_cost_base
                + acc.conversion_cost_base
                + acc.logistics_in_base
            ) / mom_fx_rate

            tp_local = accumulated_local * (1.0 + margin_rate)
            tp_fx_rate, tp_base = fx.convert(tp_local, tp_currency, week)

            acc.transfer_price_local = tp_local
            acc.transfer_price_base = tp_base
        elif str(tp_rule["method"]) == "fixed":
            tp_local = float(tp_rule.get("fixed_price", 0))
            tp_currency = str(tp_rule["currency"])
            tp_fx_rate, tp_base = fx.convert(tp_local, tp_currency, week)
            acc.transfer_price_local = tp_local
            acc.transfer_price_base = tp_base
        else:
            raise ValueError(f"Unknown transfer price method: {tp_rule['method']!r}")

        try:
            tp_fx_rate_val, _ = fx.get_rate(week, tp_currency)
        except Exception:
            tp_fx_rate_val = 1.0

        profit_zone = rules.get_profit_zone(m_node, product)
        events.append(PPCEvent(
            event_id=f"TP-{next(_counter):06d}",
            week=week,
            lot_id=acc.lot_id,
            node_id=m_node,
            edge_id="",
            product_id=product,
            qty=int(round(acc.qty)),
            ppc_event_type="transfer_price_set",
            amount_local=acc.transfer_price_local,
            currency=tp_currency,
            fx_rate=tp_fx_rate_val,
            amount_base=acc.transfer_price_base,
            amount_per_unit_base=acc.transfer_price_base,
            source_rule="ppc_transfer_price_rule.csv",
            direction="forward",
            profit_zone=profit_zone,
        ))

    return events

````
