---
tags: [wom, source]
---
# docs/architecture/README.md

原文資料（記載時点の状態を含む）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/docs/architecture/README.md) · [原文テキスト](../../../90_Raw/docs/architecture/README.md.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## 原文の見出し

- WOM Architecture Documents
- Documents
- Reading rule
- Maintenance rule

## 全文（コメント・原文を省略せず収録）

````markdown
# WOM Architecture Documents

This directory contains implementation-derived architecture documents.

These documents describe what the current WOM code appears to do by inspecting repository files.
They should not be used to redefine WOM design intent by themselves.

## Documents

```text
repository_map.md
  Repository layout and major code areas.

runtime_entrypoints.md
  GUI, CLI, PPC, tests, and execution entrypoints.

planning_engine.md
  Observed Planning Engine structure and execution sequence.

plugin_architecture.md
  HookBus, WOMPlugin, built-in plugins, and extension points.

ppc_engine.md
  PPC modules, financial event pipeline, and outputs.
```

## Reading rule

Architecture documents should be read together with design documents.

Example:

```text
architecture/planning_engine.md
  should be read with
design/demand_anchored_lot.md
```

```text
architecture/ppc_engine.md
  should be read with
design/psi_ppc_separation.md
```

## Maintenance rule

When code behavior changes, update the relevant architecture document.

When a design intention is not visible in code, record it in `docs/design/` rather than forcing it into architecture docs.

````
