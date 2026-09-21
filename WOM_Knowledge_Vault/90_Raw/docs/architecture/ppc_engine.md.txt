# PPC Engine

## Purpose

Document the current PPC implementation visible in source code: rule loading, CLI entrypoints, PSI bridging, lot-level propagation, transfer price, tariff, profit-zone summaries, reconciliation, and exports.

## Source basis

This document is implementation-derived from the `wom/ppc` package, PPC CLI module, GUI-triggered PPC runner, fallback rule CSV names, README summary, and PPC-related tests.

## Key files inspected

- wom/ppc/__main__.py
- wom/ppc/ppc_models.py
- wom/ppc/ppc_rules.py
- wom/ppc/ppc_engine.py
- wom/ppc/ppc_runner.py
- wom/ppc/ppc_forward.py
- wom/ppc/ppc_transfer.py
- wom/ppc/ppc_tariff.py
- wom/ppc/ppc_backward.py
- wom/ppc/ppc_profit_zone.py
- wom/ppc/ppc_kpi.py
- wom/ppc/ppc_export.py
- wom/ppc/ppc_psi_bridge.py
- wom/ppc/ppc_reconcile.py
- data/ppc/* file names
- tests/test_ppc_vertical_slice.py
- tests/test_ppc_multi_supplier.py

## Observed current behavior

PPC means Price, Profit, and Cost in AGENTS.md. The implementation models PPC as lot-level financial events and summaries.

`python -m wom.ppc` is the standalone PPC CLI entrypoint. It accepts a PPC rule data directory, optional sales CSV, output directory, base currency, sample-generation options, verbosity, chart/save-chart options, and an interactive app flag.

`PPCRuleSet.load(data_dir, fallback_dir="data/ppc")` reads PPC master CSV files. If a rule file is absent in the model-local data directory, it falls back to `data/ppc` unless the fallback is the same directory. The required PPC rule files visible in code are:

- `ppc_market_price.csv`
- `ppc_supplier_cost.csv`
- `ppc_node_cost_rule.csv`
- `ppc_edge_cost_rule.csv`
- `ppc_tariff_rule.csv`
- `ppc_transfer_price_rule.csv`
- `ppc_profit_zone_rule.csv`
- `ppc_fx_rate.csv`
- `ppc_node_profit_zone.csv`

`PPCSimulationEngine` is the top-level orchestrator. Its docstring lists the current processing flow:

1. Load sales records.
2. Run supplier offering cost forward propagation.
3. Determine transfer price.
4. Calculate tariff and landed cost.
5. Allocate profit zones and market revenue.
6. Run market requesting price backward propagation.
7. Reconcile forward cost against backward allowable cost.
8. Build KPI summary.

The engine input is a `sales_records` DataFrame with visible columns `lot_id`, `week`, `channel_node`, `product_id`, and `qty`. The CLI can read this from CSV or generate synthetic sample sales.

`PPCEvent` records financial events with local/base amounts, currency, FX rate, event type, direction, profit zone, and cost phase. `LotCostAccumulator` stores mutable per-lot state during computation. `PPCSimulationResult` bundles accumulators, events, trust events, node-week summary, profit-zone summary, lot reconciliation, KPI summary, and node P&L summary.

`ppc_forward.py` accumulates supplier costs, inbound edge logistics, and MOM node costs. It supports single supplier, list of suppliers, product-to-supplier maps, and product-to-list maps.

`ppc_transfer.py` determines transfer price from MOM accumulated cost using a cost-plus rule visible in the module docstring.

`ppc_tariff.py` and related modules compute tariff/landed cost using fixed transfer price and rule lookups.

`ppc_backward.py` computes backward allowable cost from market price by subtracting channel, edge, DAD-chain, inbound edge, and tariff costs. It supports product-specific DAD chains.

`ppc_reconcile.py` generates `PPCTrustEvent` records and lot reconciliation rows. Visible trust checks include negative margin, channel margin below 5%, MOM profit below zero, tariff ratio above 20% of transfer price, and landed cost exceeding market revenue.

`ppc_psi_bridge.py` converts post-forward-planning SCTree leaf-out supply quantities into PPC `sales_records`. By default it maps regions to `JP_Channel` or `US_Channel` where possible; with `use_node_name=True`, it uses leaf-out node names directly.

`ppc_runner.py` is the GUI/planning bridge. It loads rules, converts PSI to sales records, filters to PPC-known products/channels, falls back to sample sales if no compatible PSI records exist, detects scenario type, builds engine parameters, runs `PPCSimulationEngine`, and exports results.

Scenario detection is implemented in `detect_scenario()` with visible branches for rice, iPhone global, cookie, and legacy iPhone. Generic mode in `ppc_runner.py` can infer MOM, supplier, DAD, and DAD chain from an SCTree when the scenario is not one of the named cases.

PPC export writes:

- `ppc_event_ledger.csv`
- `ppc_node_week_summary.csv`
- `ppc_profit_zone_summary.csv`
- `ppc_lot_reconciliation.csv`
- `ppc_node_pl_summary.csv`
- `ppc_kpi_summary.json`

## Important assumptions

- The PPC flow is documented from source inspection only; no PPC command was run during this documentation task.
- The complete bodies of some PPC modules were truncated in shell output, so this document emphasizes module-level behavior and clearly visible orchestration.
- File names under `data/ppc` and sample model PPC files were inspected by listing rather than reading every CSV row.

## Open questions

- Should `qty` in `sales_records` be treated as aggregate quantity or one lot per row in all PPC paths? Some code comments say one lot, while PSI bridge creates aggregated records.
- Should scenario-specific path builders remain in `ppc_engine.py`, or should they be generated from `SCTree`/model CSVs consistently?
- Should PPC trust-event thresholds be configurable instead of constants in `ppc_reconcile.py`?
- Should fallback to sample PPC sales be surfaced more prominently in GUI status and exported KPI metadata?
