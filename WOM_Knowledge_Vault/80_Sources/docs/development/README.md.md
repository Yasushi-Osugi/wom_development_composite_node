---
tags: [wom, source]
---
# docs/development/README.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/development/README.md) · [原文テキスト](../../../90_Raw/docs/development/README.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- WOM Development Documents
- Documents
- Development principle
- Git operation rule
- Maintenance rule

## 全文（コメント・原文を省略せず収録）

````markdown
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

````
