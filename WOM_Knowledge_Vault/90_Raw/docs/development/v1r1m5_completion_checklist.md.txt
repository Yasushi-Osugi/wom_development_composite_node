# WOM v1r1m5 Completion Checklist

## Purpose

This checklist defines completion criteria for WOM v1r1m5 as an AI-neutral Vibe Coding Ready Release.

## Branch readiness

- [ ] Working branch is `wom-v1r1m5-agents`.
- [ ] Working tree is clean.
- [ ] Branch is pushed to GitHub.
- [ ] Branch is up to date with origin.

Recommended check:

```text
git status
git branch -vv
```

## Core files

- [ ] `AGENTS.md` exists.
- [ ] `docs/` exists.
- [ ] `docs/README.md` exists.
- [ ] `docs/architecture/README.md` exists.
- [ ] `docs/design/README.md` exists.
- [ ] `docs/scenarios/README.md` exists.
- [ ] `docs/development/README.md` exists.

## Architecture docs

- [ ] `docs/architecture/repository_map.md`
- [ ] `docs/architecture/runtime_entrypoints.md`
- [ ] `docs/architecture/planning_engine.md`
- [ ] `docs/architecture/plugin_architecture.md`
- [ ] `docs/architecture/ppc_engine.md`

## Design docs

- [ ] `docs/design/wom_canonical_concepts.md`
- [ ] `docs/design/demand_anchored_lot.md`
- [ ] `docs/design/psi_ppc_separation.md`
- [ ] `docs/design/scenario_modeling_principles.md`

## Scenario docs

- [ ] `docs/scenarios/japanese-rice.md`
- [ ] `docs/scenarios/smartphone.md`
- [ ] `docs/scenarios/cookie.md`
- [ ] `docs/scenarios/ev.md`
- [ ] `docs/scenarios/oil-global-2027.md`

## Development docs

- [ ] `docs/development/current_status.md`
- [ ] `docs/development/v1r1m5_doc_generation_plan.md`
- [ ] `docs/development/ai_vibe_coding_workflow.md`
- [ ] `docs/development/open_questions.md`
- [ ] `docs/development/v1r1m5_release_notes.md`
- [ ] `docs/development/v1r1m5_completion_checklist.md`

## Content checks

- [ ] Implementation-derived docs clearly describe current behavior.
- [ ] Design docs clearly describe design intent.
- [ ] Scenario docs clearly describe assumptions and disclaimers.
- [ ] Open questions are visible.
- [ ] AI-specific context is not the only source of WOM knowledge.
- [ ] `CLAUDE.md` is not treated as the sole source of truth.

## Markdown checks

Recommended simple checks:

```text
findstr /n /c:"# " docs\design\wom_canonical_concepts.md
findstr /n /c:"# " docs\development\ai_vibe_coding_workflow.md
findstr /n /c:"# " docs\scenarios\oil-global-2027.md
```

Optional checks:

- code fences are balanced
- headings render correctly in GitHub
- links are relative and valid where used

## Git checks

Before final commit:

```text
git status --short
git diff --name-only
git diff --stat
```

Expected documentation-only changes:

```text
AGENTS.md
docs/**/*.md
```

No Python, CSV, test, or GUI changes should appear unless explicitly planned.

## Release commit pattern

Suggested commit sequence:

```text
Add AI-neutral AGENTS guide and docs structure
Add v1r1m5 documentation generation plan
Add implementation-derived WOM architecture docs
Add WOM canonical concepts design document
Add WOM design-intent documentation
Add WOM scenario documentation
Add WOM documentation indexes and release notes
```

## Tagging candidate

After review or merge, the release tag candidate is:

```text
wom-v1r1m5
```

Suggested tag command after final release decision:

```text
git tag wom-v1r1m5
git push origin wom-v1r1m5
```

Use this only after the owner confirms that the branch content is release-ready.

## Done criteria

v1r1m5 is complete when:

- [ ] a new AI agent can start from `AGENTS.md`
- [ ] the agent can understand architecture from `docs/architecture/`
- [ ] the agent can understand design intent from `docs/design/`
- [ ] the agent can understand sample cases from `docs/scenarios/`
- [ ] the agent can understand workflow and status from `docs/development/`
- [ ] the repository no longer depends solely on chat logs or `CLAUDE.md`
- [ ] all documentation changes are committed and pushed
