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
