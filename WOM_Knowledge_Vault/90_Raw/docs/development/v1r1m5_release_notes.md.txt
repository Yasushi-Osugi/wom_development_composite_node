# WOM v1r1m5 Release Notes

## Release name

```text
WOM v1r1m5
AI-neutral Vibe Coding Ready Release
```

## Release purpose

v1r1m5 prepares WOM for AI-assisted development across multiple coding environments.

The release introduces an AI-neutral knowledge base so that Claude Code, ChatGPT Codex, and future AI agents can start from the same repository-based context.

## Branch

Working branch:

```text
wom-v1r1m5-agents
```

Base branch:

```text
wom-v1r0m5
```

## Main changes

### AGENTS.md

Added `AGENTS.md` as the common AI entry point.

Purpose:

```text
AI agents should read AGENTS.md first before modifying WOM.
```

### Documentation structure

Added structured documentation directories:

```text
docs/
  architecture/
  design/
  scenarios/
  development/
```

### Implementation-derived architecture docs

Added documents based on repository inspection:

```text
docs/architecture/repository_map.md
docs/architecture/runtime_entrypoints.md
docs/architecture/planning_engine.md
docs/architecture/plugin_architecture.md
docs/architecture/ppc_engine.md
docs/development/current_status.md
```

These documents describe what the current implementation appears to do.

### Design-intent docs

Added canonical design documents:

```text
docs/design/wom_canonical_concepts.md
docs/design/demand_anchored_lot.md
docs/design/psi_ppc_separation.md
docs/design/scenario_modeling_principles.md
docs/development/ai_vibe_coding_workflow.md
```

These documents describe why WOM is designed this way.

### Scenario docs

Added scenario documentation:

```text
docs/scenarios/japanese-rice.md
docs/scenarios/smartphone.md
docs/scenarios/cookie.md
docs/scenarios/ev.md
docs/scenarios/oil-global-2027.md
```

These documents describe model intent, assumptions, educational disclaimers, expected outputs, and open questions.

### Integration docs

Added or updated documentation index and release-management documents:

```text
docs/README.md
docs/architecture/README.md
docs/design/README.md
docs/scenarios/README.md
docs/development/README.md
docs/development/open_questions.md
docs/development/v1r1m5_release_notes.md
docs/development/v1r1m5_completion_checklist.md
```

## Knowledge policy

This release formalizes the following policy:

```text
Chat logs are useful for exploration.
Repository documents are the durable source of truth.
Git commits record knowledge increments.
The owner confirms design intent.
```

## AI-specific file policy

`CLAUDE.md` may remain useful as Claude-specific context and historical notes.

However, the canonical WOM knowledge should move to:

```text
AGENTS.md
docs/
tests/
Git history
```

## Git operation policy

For this release, state-changing Git operations should be performed by the owner in the Windows terminal.

AI agents may:

- inspect files
- draft Markdown
- propose changes
- identify open questions

The owner should execute:

- `git add`
- `git commit`
- `git push`
- branch merge
- release tagging

## Validation status

This is primarily a documentation release.

Expected validation:

```text
git status
git diff --name-only
Markdown file placement
heading structure
code fence sanity
repository path correctness
```

Automated tests are not required unless code behavior changes.

## Release impact

Expected impact:

- faster onboarding for AI coding agents
- less dependence on long chat sessions
- less dependence on one AI-specific context file
- clearer separation of implementation facts and design intent
- better scenario documentation for articles and demos
- improved continuity across Claude Code and ChatGPT Codex

## Known limitations

- Some historical context still exists only in `CLAUDE.md`.
- Some scenario details may still need verification against CSV files.
- Some implementation-derived docs may need updates after code refactoring.
- Some open questions remain intentionally unresolved.
- This release does not change Planning Engine behavior.

## Recommended next release candidates

Possible next release work:

```text
v1r1m6:
  CLAUDE.md reduction or wrapper update
  scenario manifest proposal
  open questions triage

v1r2m0:
  actual shipment export
  DAD buffer visualization
  route-switching plugin
```

## Release summary

v1r1m5 turns WOM from a codebase plus AI-specific context into a repository-grounded AI development environment.

The result is a more durable Vibe Coding foundation for WOM.
