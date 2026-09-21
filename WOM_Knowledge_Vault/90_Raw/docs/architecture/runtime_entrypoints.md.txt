# Runtime Entrypoints

## Purpose

Document the runtime entrypoints that are visible in the current implementation, including GUI startup, CLI simulation, PPC CLI, and GUI-triggered planning/PPC execution.

## Source basis

This document is implementation-derived from `main.py`, `wom/gui/app.py`, `wom/ppc/__main__.py`, `wom/ppc/ppc_runner.py`, report/export code, README usage snippets, and AGENTS.md rules.

## Key files inspected

- main.py
- wom/gui/app.py
- wom/config.py
- wom/data/loader.py
- wom/engine/simulator.py
- wom/reports/output.py
- wom/ppc/__main__.py
- wom/ppc/ppc_runner.py
- wom/ppc/ppc_export.py
- README.md
- AGENTS.md

## Observed current behavior

`python -m main` and `python main.py` are supported by the top-level `main.py` module. The default behavior is GUI startup unless `--cli` is passed.

`main.py` inserts the repository root into `sys.path` before importing from the `wom` package.

`python -m main --gui` launches the same GUI path as the default mode. `run_gui()` imports `launch()` from `wom.gui.app` and exits with an install-hint message if imports fail.

`python -m main --cli` runs a headless DataFrame-style simulation path:

- Builds a `WOMConfig` from CLI arguments.
- Resolves SKU, demand, inventory, and capacity paths, falling back to files under `data/sample`.
- Loads inputs through `WOMInputs.from_files()`.
- Runs `WOMSimulator(config).load(inputs).run(verbose=True)`.
- Prints KPI and at-risk summaries.
- Writes CSV files by default or an Excel workbook when `--excel` is passed.

The CLI parser exposes these planning options: `--start-week`, `--num-weeks`, `--safety-stock-weeks`, `--lead-time-weeks`, `--unconstrained`, `--scenarios`, `--sku-master`, `--demand-forecast`, `--inventory-master`, `--capacity-plan`, `--output-dir`, and `--excel`.

`python -m wom.ppc` is a separate PPC runtime path through `wom/ppc/__main__.py`. It loads PPC rules, either reads a sales CSV or generates sample sales, detects a scenario, runs `PPCSimulationEngine`, exports PPC outputs, prints KPI summary, and can optionally show or save a PPC cockpit chart. It also has an `--app` flag that launches an interactive PPC cockpit app.

The GUI runtime in `wom/gui/app.py` includes several execution paths:

- A conventional simulation path based on `WOMSimulator`, scenario results, charts, KPI tables, and reports.
- A richer Planning Engine path that builds an `SCTree`, assigns lots, fires hooks, runs backward planning, copies demand to supply, optionally applies push configuration, runs forward planning, integrates planning results back into `ScenarioManager`, computes management and strategic KPI outputs, and refreshes GUI panels.
- After the Planning Engine completes, the GUI triggers PPC in a background thread via `run_ppc_from_psi()`, using model-local PPC rules if `ppc_market_price.csv` exists in the loaded model folder.

Report exports are visible in `wom/reports/output.py`, which writes per-scenario detail CSVs, combined results, KPI summary, weekly summary, optional at-risk CSV, and Excel sheets.

PPC exports are visible in `wom/ppc/ppc_export.py`, which writes `ppc_event_ledger.csv`, `ppc_node_week_summary.csv`, `ppc_profit_zone_summary.csv`, `ppc_lot_reconciliation.csv`, `ppc_node_pl_summary.csv`, and `ppc_kpi_summary.json`.

## Important assumptions

- Runtime behavior is described from source inspection only; no GUI or CLI run was executed during this documentation task.
- `python -m main` remains the canonical application entrypoint because AGENTS.md explicitly says not to break it.
- The GUI contains large amounts of behavior in one module, so this document only records entrypoint-level behavior rather than every panel-level callback.

## Open questions

- Should `python -m main --cli` be documented as a legacy/simple simulation path, while the GUI Planning Engine path is treated as the main planning path?
- Should `python -m wom.ppc --app` be documented as a supported user entrypoint or an internal/development convenience?
- The PPC GUI auto-run writes to `output/ppc`; should this output location be configurable from the GUI?
