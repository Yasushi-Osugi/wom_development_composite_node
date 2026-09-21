# Repository Map

## Purpose

Map the current WOM repository layout from files observed in the checkout so a new contributor can locate runtime entrypoints, planning code, PPC code, plugins, sample data, tests, and documentation.

## Source basis

This document is implementation-derived. It is based on repository file listing, source files, README material, AGENTS.md, and the v1r1m5 documentation generation plan. It does not describe design intent beyond what is visible in the current files.

## Key files inspected

- AGENTS.md
- README.md
- requirements.txt
- main.py
- wom/config.py
- wom/data/loader.py
- wom/data/schema.py
- wom/engine/*.py
- wom/model/*.py
- wom/plugins/*.py
- wom/ppc/*.py
- wom/gui/app.py
- wom/reports/output.py
- docs/development/v1r1m5_doc_generation_plan.md
- data/sample/* file names
- data/ppc/* file names
- tests/* file names

## Observed current behavior

The repository is a Python project centered on the `wom` package, with a top-level `main.py` entrypoint. The root also contains README and AI-agent guidance files including AGENTS.md and CLAUDE*.md files.

The `wom/data` package contains CSV/Excel loading and schema constants. `WOMInputs.from_files()` loads SKU, demand, inventory, and capacity inputs into DataFrames used by the DataFrame-based simulator.

The `wom/engine` package contains multiple planning-related subsystems:

- `simulator.py`, `demand.py`, `capacity.py`, `inventory.py`, `money.py`, `management.py`, and `scenario.py` implement a DataFrame-style scenario simulation path.
- `backward_planner.py`, `forward_planner.py`, `push_pull.py`, `plan_copy.py`, `sc_tree_builder.py`, `capacity_sealer.py`, `lane_assignment.py`, `decouple_optimizer.py`, and related helpers implement an SCTree/PlanNode lot-based planning path.
- `plugin_base.py`, `hook_bus.py`, `holiday_calendar_plugin.py`, and other plugin-facing modules provide hookable planning behavior.

The `wom/model` package defines planning data structures:

- `plan_node.py` defines `PlanNode`, PSI bucket constants, capacity bucket constants, and node type constants.
- `sc_tree.py` defines `SCTree` and bridge operations between OutBound and InBound trees.
- `lot_generator.py` creates and assigns lot IDs to leaf-out demand.

The `wom/plugins` package contains optional planning plugins, including capacity override, demand smoothing, and buffering stock optimization.

The `wom/ppc` package contains PPC financial simulation code. It has its own CLI entrypoint in `wom/ppc/__main__.py`, data models, rule loading, forward/backward propagation, transfer price, tariff, FX, profit-zone, reconciliation, export, and PSI bridge modules.

The `wom/gui` package contains the Tkinter GUI application. `wom/gui/app.py` includes the GUI launcher, simulation screens, planning pipeline invocation, and PPC auto-run after planning.

The `wom/reports` package writes console, CSV, and Excel reports for the scenario manager results.

The `data/sample` directory contains root sample CSVs plus multiple model folders such as `oil-global-2027`, `rice-japan-2027-2028`, `smartx-2027-2029`, `iphone`, `iphone_global`, `Cookie-jp-2026`, `ev-thailand-2026`, and `ev-europe-2026`. Many model folders include planning CSVs and PPC rule CSVs.

The `data/ppc` directory contains fallback PPC rule CSVs used by PPC rule loading when model-local files are not present.

The `tests` directory contains pytest files covering capacity, push/pull, hooks, PPC vertical slice, PPC multi-supplier, decouple optimizer, and buffering stock optimizer behavior.

The `docs` directory currently has README placeholders and the v1r1m5 documentation generation plan. The six architecture/status documents listed in Track A did not exist before this documentation task.

## Important assumptions

- The repository map is based on files visible in the current checkout on branch `wom-v1r1m5-agents`.
- File names under `data/sample` and `data/ppc` were inspected by listing, not by reading every CSV row.
- The README contains mojibake in some Japanese text as read from the shell; English summaries and source code were used for implementation-derived facts.

## Open questions

- Which of the two planning paths, DataFrame simulator vs SCTree lot-based planner, should be considered canonical for future user-facing documentation?
- Are CLAUDE*.md historical context files intended to remain in the root after v1r1m5, or should docs become the only maintained knowledge surface?
- Should generated output directories such as `output/` and pytest cache artifacts be ignored or cleaned in repository policy?
