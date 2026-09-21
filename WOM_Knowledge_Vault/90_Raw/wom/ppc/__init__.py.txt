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
