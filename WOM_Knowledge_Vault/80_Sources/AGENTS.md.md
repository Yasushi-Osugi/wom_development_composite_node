---
tags: [wom, source]
---
# AGENTS.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/AGENTS.md) · [原文テキスト](../90_Raw/AGENTS.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- AGENTS.md
- WOM AI Development Guide
- 1. Read this first
- 2. Repository knowledge policy
- 3. Core WOM concepts
- 4. Development rules
- 5. Scenario rules
- 6. Planning Engine rule
- 7. PPC rule
- 8. AI agent behavior
- 9. Current release intent
- 10. Protected core (Anti-Degrade guardrail)
- 11. Experimental Linux qualification (owner-approved 2026-09-20)

## 関連する知識源

- [[80_Sources/docs/development/README.md|docs/development/README.md]]
- [[80_Sources/docs/architecture/README.md|docs/architecture/README.md]]
- [[80_Sources/docs/design/README.md|docs/design/README.md]]
- [[80_Sources/docs/scenarios/README.md|docs/scenarios/README.md]]
- [[80_Sources/requests/operating-constraint-layer-request-letter.md|requests/operating-constraint-layer-request-letter.md]]
- [[80_Sources/wom/engine/backward_planner.py|wom/engine/backward_planner.py]]
- [[80_Sources/wom/engine/forward_planner.py|wom/engine/forward_planner.py]]
- [[80_Sources/wom/engine/plan_copy.py|wom/engine/plan_copy.py]]
- [[80_Sources/wom/model/plan_node.py|wom/model/plan_node.py]]
- [[80_Sources/wom/model/sc_tree.py|wom/model/sc_tree.py]]
- [[80_Sources/wom/engine/push_pull.py|wom/engine/push_pull.py]]
- [[80_Sources/tools/run_headless_from_folder.py|tools/run_headless_from_folder.py]]
- [[80_Sources/tests/test_golden.py|tests/test_golden.py]]

## 全文（コメント・原文を省略せず収録）

````markdown
# AGENTS.md

# WOM AI Development Guide

This file is the common entry point for AI coding agents working on WOM.
It is intended for Claude Code, ChatGPT Codex, and other AI-assisted development environments.

WOM stands for Weekly Operation Model.
WOM is a weekly supply chain planning and simulation tool for PSI and PPC.

## 1. Read this first

Before editing code, read the following documents.

1. `README.md`
2. `docs/development/README.md`
3. `docs/architecture/README.md`
4. `docs/design/README.md`
5. `docs/scenarios/README.md`

If `CLAUDE.md` exists, it may contain Claude-specific context.
However, the canonical WOM knowledge should be maintained under `docs/`.

## 2. Repository knowledge policy

WOM development knowledge should be accumulated in the repository, not only in chat logs.

Important design decisions should be recorded as Markdown files under `docs/`.
Implementation changes should be traceable by Git commit.
Behavior changes should be validated by tests or reproducible sample scenarios.

Chat logs are useful for exploration.
Repository documents are the source of truth.

## 3. Core WOM concepts

WOM is based on the following core concepts.

- Weekly planning bucket
- PSI: Production or Purchase, Ship or Sales, Inventory
- Demand Anchored Lot
- Inbound Tree and Outbound Tree
- MOM node as Mother Plant or main supply node
- DAD node as distribution allocation or decoupling node
- Capacity-aware planning
- PPC: Price, Profit, Cost simulation
- Scenario-based supply chain modeling

Do not change these core concepts casually.
If a change is necessary, update the relevant design document first.

## 4. Development rules

When modifying code:

1. Keep existing sample models runnable.
2. Do not break `python -m main`.
3. Prefer small, reviewable changes.
4. Update documents when behavior or assumptions change.
5. Add or update tests when planning logic changes.
6. Do not mix unrelated refactoring with scenario changes.

## 5. Scenario rules

Sample scenarios under `data/sample/` are educational models.
They may use fictional companies, locations, prices, and capacities.

When adding or modifying a scenario:

1. Document the scenario intent.
2. Clearly separate fictional data from real-world references.
3. Keep CSV structure compatible with the existing engine.
4. Verify GUI and CLI execution where possible.

## 6. Planning Engine rule

The Planning Engine should remain as general and canonical as possible.

Scenario-specific behavior should be expressed by:

- input CSV files
- plugin layer
- scenario generator scripts
- parameter files
- documented assumptions

Avoid hard-coding scenario-specific logic inside the canonical engine.

## 7. PPC rule

PPC means Price, Profit, and Cost.

PPC changes should preserve the separation between:

- physical flow
- price propagation
- cost structure
- profit zone
- node-level P&L
- scenario-specific economic assumptions

## 8. AI agent behavior

AI agents should behave as careful development partners.

Before editing:

1. Inspect the existing files.
2. Understand the current branch and target release.
3. Propose the smallest safe change.
4. Explain assumptions.
5. Avoid destructive commands unless explicitly requested.

Never delete or rewrite large parts of the repository without clear instruction.

## 9. Current release intent

This branch prepares WOM v1r1m5 as an AI-neutral Vibe Coding Ready Release.

The goal is to make WOM development accessible from multiple AI coding environments by introducing:

- `AGENTS.md`
- structured `docs/`
- AI-neutral development guidance
- repository-based knowledge continuity

## 10. Protected core (Anti-Degrade guardrail)

The Planning Engine core must be protected from silent regressions. History: a
v1r0m3 refactor ("MOM Constrained Demand Allocation") unintentionally disconnected
the `cap_soft` wiring (loader column + sealer call) as a **side effect of an
approved change**, leaving it dormant. Procedural rules alone cannot catch such
side effects — only tests can. Rationale: `requests/operating-constraint-layer-request-letter.md` §11.

**Protected core files** (gated — not "never touch"):
- `wom/engine/backward_planner.py`
- `wom/engine/forward_planner.py`
- `wom/engine/plan_copy.py`
- `wom/model/plan_node.py`
- `wom/model/sc_tree.py`
- `wom/engine/push_pull.py`

**Rules:**
1. Do not modify the files above without an explicit instruction (reference a Request Letter).
2. Any change must keep a **3-layer test suite green**:
   - **Unit** — assert desired behavior on a synthetic tree with fixed values.
   - **Integration** — exercise the real CSV → loader → node data path
     (e.g. `wom/engine/capacity_sealer.load_capacity_dataframe`). This was the
     layer whose absence let `cap_soft` die.
   - **E2E golden** — `tools/run_headless_from_folder.py` + `tests/golden/*.json`
     must show the existing 12 sample cases unchanged (`period/products/config/
     forward/backward/ppc/psi`). Enforced by `tests/test_golden.py`.
3. The owner reviews the `git diff` before committing.
4. Intentional behavior changes must **regenerate and commit** the goldens
   (the diff is the audit trail).

**Dual layer is mandatory**: procedural guardrail (soft, intent) + 3-layer tests
(hard, machine-enforced). Markdown rules are followed only probabilistically by an
AI agent; tests are enforced by the machine.

**Golden harness**: `tools/run_headless_from_folder.py` runs Load→Planning→PPC
headlessly and emits a KPI snapshot (forward/backward capacity stats, PPC KPIs,
per-node PSI sums + weekly-series md5). Regenerate canonical goldens on the
owner's Windows shell. Final Windows GUI validation also remains required.

## 11. Experimental Linux qualification (owner-approved 2026-09-20)

This exception applies only to `Yasushi-Osugi/wom_development_composite_node`.
It must not be treated as permission for other WOM repositories.

Use an independent Linux checkout, never the owner's shared Windows working
directory. The historical Linux bash mount was reported to truncate large files;
do not assume either that every Linux environment has this fault or that a new
environment is already qualified.

During qualification, Git clone/read-only inspection, isolated dependency setup,
pytest and headless baseline runs are authorized. Record the full commit SHA,
file/object integrity, Python and dependency versions, test results and comparison
with committed golden snapshots. Keep source code, sample CSVs and canonical
goldens unchanged during these baseline runs. Missing dependencies, skipped tests
and discrepancies must be reported, not hidden by updating expected results.

After qualification for the recorded scope, Linux Git operations, code editing,
headless experiments and pytest are permitted within that scope. Qualification
does not certify Windows GUI behavior or untested workflows. Material environment
or dependency changes require the relevant checks again.

Protected-core rules in section 10, owner diff review, and existing approval rules
for commits, pushes, merges and releases remain in force. This environment
permission is not approval for a particular core implementation or publication.
Canonical golden updates and final GUI acceptance remain Windows responsibilities.

````
