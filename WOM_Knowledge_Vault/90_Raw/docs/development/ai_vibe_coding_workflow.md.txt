# AI Vibe Coding Workflow

## Purpose

This document defines the AI-assisted development workflow for WOM.

The purpose is to make WOM development usable across multiple AI coding environments, including Claude Code, ChatGPT Codex, and future AI agents, without making WOM knowledge dependent on one AI-specific file.

## Source basis

This document is derived from:

- `CLAUDE.md`
- `AGENTS.md`
- `docs/development/v1r1m5_doc_generation_plan.md`
- `docs/design/wom_canonical_concepts.md`
- implementation-derived documents under `docs/architecture/`
- owner decisions accumulated through WOM development discussions

## Design intent

The design intent is:

```text
AI can help accelerate WOM development.
The repository remains the source of truth.
The owner confirms design intent.
Git records the knowledge increment.
```

AI-assisted development should produce durable repository artifacts:

- Markdown design documents
- implementation changes
- tests
- sample scenarios
- reproducible outputs
- commit history

Chat is useful for exploration.
The repository is the durable knowledge base.

## AI-neutral context structure

WOM should avoid depending on one AI-specific context file.

Recommended roles:

```text
AGENTS.md
  AI-neutral entry point

docs/
  canonical WOM knowledge and development documents

CLAUDE.md
  Claude-specific context and historical notes, if still useful

README.md
  human-facing project introduction

tests/
  executable behavior checks

Git commit history
  traceable knowledge increments
```

The long-term target is:

```text
WOM knowledge lives in docs/.
AI tools read docs/.
AI-specific files become wrappers, not the source of truth.
```

## Standard AI onboarding sequence

Before editing code or documentation, an AI agent should read:

```text
AGENTS.md
docs/development/current_status.md
docs/development/v1r1m5_doc_generation_plan.md
docs/design/wom_canonical_concepts.md
docs/architecture/repository_map.md
docs/architecture/runtime_entrypoints.md
```

Then the agent should read the relevant topic documents.

For Planning Engine work:

```text
docs/architecture/planning_engine.md
docs/design/demand_anchored_lot.md
```

For PPC work:

```text
docs/architecture/ppc_engine.md
docs/design/psi_ppc_separation.md
```

For plugins:

```text
docs/architecture/plugin_architecture.md
```

For scenario work:

```text
docs/design/scenario_modeling_principles.md
docs/scenarios/<scenario>.md
```

## Standard task classification

Every AI-assisted task should be classified before work begins.

### Documentation-only task

Allowed:

- read repository files
- create or update Markdown under `docs/`
- summarize implementation behavior
- identify open questions

Not allowed unless explicitly requested:

- modify Python code
- modify CSV data
- modify tests
- change GUI behavior

### Implementation task

Allowed after explicit instruction:

- modify Python code
- add tests
- update relevant docs
- run tests when environment allows

Required:

- small change scope
- clear behavior statement
- tests or reproducible scenario verification
- documentation update if assumptions change

### Scenario task

Allowed after explicit instruction:

- add or update scenario CSV files
- add scenario documentation
- add generator scripts
- verify GUI/CLI execution where possible

Required:

- fictional or real-world disclaimer as appropriate
- scenario intent
- assumptions
- expected outputs
- known limitations

### Git task

Recommended owner-controlled operations:

- `git add`
- `git commit`
- `git push`
- release tag creation
- branch creation or merge

AI may propose commands, but the owner should execute state-changing Git operations unless a trusted environment is explicitly established.

## Safe command policy

Read-only commands are generally safe when scoped to the approved repository path.

Examples:

```text
git status
git diff
git diff --stat
git diff --name-only
rg --files
Get-Content <repo-file>
```

State-changing commands require explicit owner approval.

Examples:

```text
git add
git commit
git push
git switch
git checkout
git reset
git restore
git clean
```

Destructive commands should be avoided unless the owner gives a precise instruction and the expected effect is clear.

## Windows-first Git policy

For WOM, state-changing Git operations should be performed from the owner's Windows terminal unless the environment has been explicitly verified.

Reason:

- large file reads and diffs may behave differently through some Linux/bash mounted environments
- a misleading diff may cause broken staging
- the owner-controlled Windows CLI is the safest release path

Canonical policy:

```text
AI may inspect and draft.
Owner commits and pushes from Windows CLI.
```

## Documentation generation workflow

For documentation work, use this flow.

```text
1. Confirm branch and clean status
2. Read AGENTS.md
3. Read the documentation generation plan
4. Read implementation-derived architecture docs
5. Read relevant design sources
6. Draft Markdown files
7. Verify headings and code fences
8. Confirm only docs/ files changed
9. Owner commits and pushes
```

Each generated document should distinguish:

- implementation fact
- design intent
- scenario assumption
- open question

## Implementation workflow

For code changes, use this flow.

```text
1. Confirm objective and target behavior
2. Inspect current implementation
3. Identify smallest safe change
4. Propose plan before editing
5. Edit only necessary files
6. Add or update tests
7. Run focused tests
8. Run broader tests when feasible
9. Update docs if assumptions changed
10. Owner reviews diff and commits
```

AI should avoid mixing unrelated work.

Do not combine:

- engine refactoring
- GUI redesign
- scenario data changes
- PPC changes
- documentation migration

unless the owner explicitly approves a combined release task.

## Scenario workflow

For scenario creation or modification, use this flow.

```text
1. Define business question
2. Define educational disclaimer
3. Define SKU structure
4. Define physical network
5. Define demand assumptions
6. Define capacity assumptions
7. Define buffer assumptions
8. Define PPC assumptions
9. Add or update scenario files
10. Run or describe reproducible verification
11. Add or update docs/scenarios/<scenario>.md
```

Scenario-specific behavior should be expressed through data, plugins, or generator scripts before engine changes are considered.

## AI roles

### Owner

The owner defines:

- business meaning
- design intent
- release priority
- acceptable model abstraction
- public article narrative
- final approval

### AI coding agent

An AI coding agent may:

- inspect repository structure
- identify implementation facts
- draft docs
- propose changes
- implement scoped changes
- add tests
- explain diffs
- surface open questions

### Reviewer AI

A reviewer AI may:

- compare documents against implementation
- identify contradictions
- improve wording
- check for scenario-specific leakage into canonical docs
- propose release notes

## Prompt pattern for implementation-derived documentation

A useful prompt pattern is:

```text
Read AGENTS.md first.

This is documentation-only work.
Do not modify Python code, CSV data, tests, or GUI behavior.

Create implementation-derived documentation by inspecting the current repository.

For each document, include:
- Purpose
- Source basis
- Key files inspected
- Observed current behavior
- Important assumptions
- Open questions

Do not describe design intent unless it is directly visible in code or existing repository documents.
If something is unclear, mark it as an open question.
```

## Prompt pattern for design-intent documentation

A useful prompt pattern is:

```text
Read AGENTS.md and the current design documents first.

This is documentation-only work.

Create design-intent documents from CLAUDE.md, existing docs, article context, and owner decisions.

For each document, include:
- Purpose
- Source basis
- Design intent
- Canonical concepts
- Relationship to current implementation
- Open questions

Do not treat AI-specific files as the source of truth.
Move durable WOM knowledge into docs/.
```

## Prompt pattern for code changes

A useful prompt pattern is:

```text
Read AGENTS.md first.

This is an implementation task.
Before editing, inspect the current code and propose the smallest safe change.

Do not modify unrelated files.
Update tests and docs if behavior changes.
After editing, summarize:
- files changed
- behavior changed
- tests run
- risks
- open questions
```

## Verification checklist

Before committing AI-assisted work, check:

```text
git status --short
git diff --name-only
git diff --stat
```

For documentation-only work:

```text
Only docs/ or approved Markdown files should be changed.
```

For implementation work:

```text
Relevant tests should be added or updated.
Focused tests should pass where executable.
Docs should be updated if behavior or assumptions changed.
```

For scenario work:

```text
CSV files should remain structurally valid.
Scenario assumptions should be documented.
GUI/CLI execution should be verified where feasible.
```

## Release workflow

For a documentation release such as v1r1m5:

```text
1. Create release branch
2. Add AGENTS.md
3. Add docs/ structure
4. Add implementation-derived docs
5. Add design-intent docs
6. Add scenario docs
7. Resolve open questions or document them
8. Review README and release notes
9. Commit and push
10. Create PR or release tag according to repository practice
```

## Relationship to current implementation

The current repository already supports this workflow through:

- `AGENTS.md`
- `docs/development/v1r1m5_doc_generation_plan.md`
- architecture documents under `docs/architecture/`
- design documents under `docs/design/`
- Git branch `wom-v1r1m5-agents`
- owner-controlled Windows CLI commits

Known workflow boundaries:

- Some historical context still exists only in `CLAUDE.md`.
- Some scenario details may exist only in article drafts or chat logs.
- Some temporary probe scripts may not yet be formalized under `tools/`.
- AI sandbox access may require careful path scoping.

## Open questions

1. Should `CLAUDE.md` remain in the repository as a Claude-specific wrapper after docs migration?

2. Should Codex-specific instructions be added, or should `AGENTS.md` remain sufficient?

3. Should a standard `docs/development/release_checklist.md` be created?

4. Should generated docs include a machine-readable front matter section?

5. Should AI agents be allowed to commit in trusted environments, or should owner-controlled Git remain the standard?

6. Should all AI-produced docs include a short provenance section?

7. How should open questions be tracked:
   - within each document
   - in a central `open_questions.md`
   - as GitHub issues

## Maintenance rule

When AI-assisted work produces durable knowledge, store it under `docs/`.

When AI-assisted work changes behavior, update tests and relevant design documents.

When AI produces uncertain conclusions, record them as open questions rather than converting them into silent assumptions.
