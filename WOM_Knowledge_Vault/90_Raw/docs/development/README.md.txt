# WOM Development Documents

This directory contains release, workflow, status, and open-question documents for WOM development.

## Documents

```text
current_status.md
  Implementation-derived current status.

v1r1m5_doc_generation_plan.md
  Documentation generation plan for AI-neutral Vibe Coding readiness.

ai_vibe_coding_workflow.md
  Development workflow for Claude Code, ChatGPT Codex, and future AI agents.

open_questions.md
  Cross-document open questions and future work.

v1r1m5_release_notes.md
  Draft release notes for the v1r1m5 documentation release.

v1r1m5_completion_checklist.md
  Release readiness checklist.
```

## Development principle

```text
Chat explores.
Docs preserve.
Tests verify.
Git records.
Owner confirms.
```

## Git operation rule

State-changing Git operations should be performed by the owner in the Windows terminal unless a trusted environment is explicitly established.

AI agents may inspect, draft, and propose.
The owner should execute:

```text
git add
git commit
git push
release tagging
branch merge
```

## Maintenance rule

When development status changes, update `current_status.md` or release notes.
When unresolved design or implementation issues appear, record them in `open_questions.md`.
