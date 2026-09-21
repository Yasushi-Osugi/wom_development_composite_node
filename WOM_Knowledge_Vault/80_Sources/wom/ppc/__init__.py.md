---
tags: [wom, code]
---
# wom/ppc/__init__.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/ppc/__init__.py) · [原文テキスト](../../../90_Raw/wom/ppc/__init__.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/04_Evaluation|Evaluation]]

## モジュール説明（docstring原文）

```text
wom/ppc — PPC (Profit / Price / Cost) Simulation Engine

Vertical Slice: iphone-vs scenario
    1 product (IPHONE)
    1 supplier (Supplier_CN, CNY)
    1 MOM (MOM_China, CN)
    1 DAD (DAD_Japan, JP)
    2 market channels (JP_Channel: JPY, US_Channel: USD)
    1 cross-border tariff edge CN→JP (5%) + JP→US (10%)
    12 weeks (2026-W01 to 2026-W12)

Processing order (D2 — no circular reference):
    Step 1. Forward propagation (Supplier → MOM costs)
    Step 2. Transfer price determination (cost_plus, fixed)
    Step 3. Tariff & landed cost (on fixed transfer price)
    Step 4. Market revenue + channel costs
    Step 5. Backward requesting price (lot-based, D3)
    Step 6. Reconciliation (lot-based trust events)
    Step 7. KPI summary (base currency, D1)
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|

## 全文（コメント・原文を省略せず収録）

````python
"""
wom/ppc — PPC (Profit / Price / Cost) Simulation Engine

Vertical Slice: iphone-vs scenario
    1 product (IPHONE)
    1 supplier (Supplier_CN, CNY)
    1 MOM (MOM_China, CN)
    1 DAD (DAD_Japan, JP)
    2 market channels (JP_Channel: JPY, US_Channel: USD)
    1 cross-border tariff edge CN→JP (5%) + JP→US (10%)
    12 weeks (2026-W01 to 2026-W12)

Processing order (D2 — no circular reference):
    Step 1. Forward propagation (Supplier → MOM costs)
    Step 2. Transfer price determination (cost_plus, fixed)
    Step 3. Tariff & landed cost (on fixed transfer price)
    Step 4. Market revenue + channel costs
    Step 5. Backward requesting price (lot-based, D3)
    Step 6. Reconciliation (lot-based trust events)
    Step 7. KPI summary (base currency, D1)
"""

from .ppc_engine import PPCSimulationEngine, build_iphone_vs_paths
from .ppc_models import PPCEvent, PPCTrustEvent, LotCostAccumulator, PPCSimulationResult
from .ppc_rules import PPCRuleSet
from .ppc_fx import FXConverter
from .ppc_export import export_results

__all__ = [
    "PPCSimulationEngine",
    "build_iphone_vs_paths",
    "PPCEvent",
    "PPCTrustEvent",
    "LotCostAccumulator",
    "PPCSimulationResult",
    "PPCRuleSet",
    "FXConverter",
    "export_results",
]

````
