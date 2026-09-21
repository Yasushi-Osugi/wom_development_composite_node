---
tags: [wom, source]
---
# docs/development/current_status.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/development/current_status.md) · [原文テキスト](../../../90_Raw/docs/development/current_status.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- Current Status
- Purpose
- Source basis
- Key files inspected
- Observed current behavior
- Important assumptions
- Open questions

## 関連する知識源

- [[80_Sources/docs/development/v1r1m5_doc_generation_plan.md|docs/development/v1r1m5_doc_generation_plan.md]]
- [[80_Sources/wom/config.py|wom/config.py]]
- [[80_Sources/wom/data/loader.py|wom/data/loader.py]]
- [[80_Sources/wom/gui/app.py|wom/gui/app.py]]
- [[80_Sources/wom/reports/output.py|wom/reports/output.py]]
- [[80_Sources/docs/development/README.md|docs/development/README.md]]
- [[80_Sources/docs/architecture/README.md|docs/architecture/README.md]]
- [[80_Sources/docs/design/README.md|docs/design/README.md]]
- [[80_Sources/docs/scenarios/README.md|docs/scenarios/README.md]]
- [[80_Sources/docs/architecture/repository_map.md|docs/architecture/repository_map.md]]
- [[80_Sources/docs/architecture/runtime_entrypoints.md|docs/architecture/runtime_entrypoints.md]]
- [[80_Sources/docs/architecture/planning_engine.md|docs/architecture/planning_engine.md]]
- [[80_Sources/docs/architecture/plugin_architecture.md|docs/architecture/plugin_architecture.md]]
- [[80_Sources/docs/architecture/ppc_engine.md|docs/architecture/ppc_engine.md]]

## 全文（コメント・原文を省略せず収録）

````markdown
# Current Status

## Purpose

Record the current observed repository status for branch `wom-v1r1m5-agents` as implementation-derived documentation for the v1r1m5 documentation phase.

## Source basis

This document is based on `git status`, AGENTS.md, the v1r1m5 documentation generation plan, repository file listing, source inspection, README content, requirements, docs placeholders, and test file names. No source code, CSV data, tests, or GUI behavior were modified.

## Key files inspected

- AGENTS.md
- docs/development/v1r1m5_doc_generation_plan.md
- README.md
- requirements.txt
- main.py
- wom/config.py
- wom/data/loader.py
- wom/engine/*.py selected for planning/plugin behavior
- wom/model/*.py
- wom/plugins/*.py
- wom/ppc/*.py
- wom/gui/app.py
- wom/reports/output.py
- docs/development/README.md
- docs/architecture/README.md
- docs/design/README.md
- docs/scenarios/README.md
- tests/* file names

## Observed current behavior

The checkout is on branch `wom-v1r1m5-agents`. `git status` reported the branch up to date with `origin/wom-v1r1m5-agents` and a clean working tree before documentation edits began.

AGENTS.md exists at the repository root and identifies the branch/release intent as an AI-neutral Vibe Coding Ready Release. It instructs agents to use repository docs as source of truth, preserve core WOM concepts, keep `python -m main` working, and keep the Planning Engine general rather than hard-coding scenario behavior.

`docs/development/v1r1m5_doc_generation_plan.md` defines Track A implementation-derived documents and lists the six target files created by this task. It also distinguishes implementation-derived documents from design-intent and scenario documents.

The root README describes WOM as a Python/Tkinter desktop tool for weekly PSI and PPC simulation. Some Japanese text appears as mojibake when read through the shell, but the English summary and code paths are readable.

`requirements.txt` currently lists `pandas`, `numpy`, `openpyxl`, and `matplotlib`. Source files also import optional or additional libraries such as Tkinter, networkx, and GUI/PPC plotting-related modules, but those are not all listed in `requirements.txt` as inspected.

The codebase contains both a DataFrame-style simulation path and an SCTree/lot-based Planning Engine path. The GUI integrates the richer Planning Engine path and triggers PPC from planning results. The CLI path in `main.py --cli` uses the DataFrame-style simulator.

PPC has both standalone CLI support and GUI/planning bridge support. It reads PPC rule CSVs, produces lot-level event and reconciliation outputs, and writes CSV/JSON files under an output PPC directory.

The target documentation files did not exist before this task. They were created under:

- `docs/architecture/repository_map.md`
- `docs/architecture/runtime_entrypoints.md`
- `docs/architecture/planning_engine.md`
- `docs/architecture/plugin_architecture.md`
- `docs/architecture/ppc_engine.md`
- `docs/development/current_status.md`

Tests were not executed during this documentation task. Test file names indicate coverage around capacity, push/pull, hooks, PPC, decouple optimizer, and buffering stock optimizer behavior.

## Important assumptions

- Current status reflects the repository as inspected on branch `wom-v1r1m5-agents` during this documentation-only task.
- No runtime validation was performed; behavior statements are from source and repository documents.
- Because this task was documentation-only, no Python code, CSV data, tests, or GUI behavior were intentionally changed.

## Open questions

- Should v1r1m5 require running a smoke test such as `python -m main --cli` or a subset of pytest before documentation readiness is declared?
- Should `requirements.txt` be reconciled with GUI/PPC imports before release documentation is considered complete?
- Should existing mojibake in README/source comments be corrected in a separate documentation/encoding task?
- Should Track B design-intent and Track C scenario documents be generated after this Track A pass?

````
