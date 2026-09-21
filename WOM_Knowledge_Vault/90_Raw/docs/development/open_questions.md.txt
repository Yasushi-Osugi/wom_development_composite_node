# WOM Open Questions

## Purpose

This document collects cross-cutting open questions discovered during WOM v1r1m5 documentation work.

Open questions should be visible rather than hidden.
They may come from implementation-derived documents, design-intent documents, scenario documents, code inspection, article drafting, or owner decisions.

## Source basis

This document consolidates open questions from:

- `docs/design/wom_canonical_concepts.md`
- `docs/design/demand_anchored_lot.md`
- `docs/design/psi_ppc_separation.md`
- `docs/design/scenario_modeling_principles.md`
- `docs/architecture/*.md`
- `docs/scenarios/*.md`
- `CLAUDE.md`
- owner discussions

## Planning Engine questions

### Actual shipment trace

Question:

```text
Should actual shipment traces such as actual_s become a formal exported data structure?
```

Reason:

Demand-anchored planning may preserve planned `S` while actual fulfilled lots are tracked separately.
GUI, CSV export, KPI, and PPC may need access to actual shipment traces for better shortage diagnosis.

Possible future work:

- export actual shipment ledger
- display actual versus planned shipment
- connect actual shipment to Fill Rate
- connect actual shipment to PPC revenue recognition

### cap_hard = 0.0 semantics

Question:

```text
Should cap_hard = 0.0 mean "no capacity specified" or "intentional full closure"?
```

Reason:

Some implementations treat default zero capacity as unspecified, while scenario modeling may need explicit full closure.

Possible future work:

- introduce explicit closure flag
- distinguish missing capacity from zero capacity
- document default behavior in capacity design docs
- add tests for intentional full closure

### DAD buffer visualization

Question:

```text
Should DAD-side buffer stock be displayed in the same standard chart family as MOM buffer stock?
```

Reason:

DAD buffer stock is a valid WOM behavior when a node is a decoupling point with safety stock.
Some GUI chart views may still focus on MOM nodes.

Possible future work:

- add DAD buffer chart
- add node-type filter for buffer charts
- export buffer inventory by node type

## PPC questions

### Node-level P&L depth

Question:

```text
How far should node-level P&L go?
```

Reason:

Current node-level P&L is useful for cost concentration visibility, but full internal accounting would require transfer prices across more edges or nodes.

Possible future work:

- define node-level revenue rules
- define internal transfer-price model
- separate cost concentration report from formal P&L
- add edge-level financial ledger

### PSI-to-PPC handoff

Question:

```text
Should all PPC calculations be based on event ledger rows?
```

Reason:

Event-ledger based PPC improves traceability, but some summary calculations may remain simpler as table operations.

Possible future work:

- define canonical PPC event schema
- export PSI-to-PPC bridge table
- align revenue recognition with actual shipment traces

### Multi-currency reporting

Question:

```text
How should WOM distinguish transaction currency, functional currency, and management reporting currency?
```

Reason:

Landed cost and PPC scenarios may involve JPY, EUR, THB, USD, and other currencies.

Possible future work:

- define currency fields
- define base currency by scenario
- add FX rule documentation
- avoid double-counting FX effects

## Scenario questions

### Route switching

Question:

```text
Should route-switching become a standard plugin pattern?
```

Reason:

Oil and geopolitical risk scenarios may require normal route versus emergency route comparison.

Possible future work:

- route-switch plugin
- scenario generator for route substitution
- dynamic route assignment
- route capacity and cost comparison

### Demand destruction and price elasticity

Question:

```text
Should price elasticity and demand destruction become a standard economic plugin?
```

Reason:

Oil/OPEC-like scenarios use delayed demand destruction after price shock.
This is currently best modeled as an external scenario layer.

Possible future work:

- demand response generator
- price elasticity plugin
- feedback-loop scenario framework

### Scenario manifest

Question:

```text
Should each scenario folder include a machine-readable scenario manifest?
```

Reason:

A manifest could allow AI agents and GUI tools to understand scenario purpose, horizon, recommended tabs, disclaimers, and output expectations.

Possible future work:

- `scenario_manifest.yml`
- `scenario_manifest.json`
- scenario validation tool
- GUI scenario description panel

## AI workflow questions

### CLAUDE.md future role

Question:

```text
Should CLAUDE.md remain as a Claude-specific wrapper after docs migration?
```

Reason:

`CLAUDE.md` contains valuable historical context, but canonical AI-neutral knowledge should live under `docs/`.

Possible future work:

- keep minimal `CLAUDE.md` that points to `AGENTS.md`
- archive historical notes under docs
- split bug history into release notes
- remove duplicated or stale version references

### AI commit permissions

Question:

```text
Should AI agents ever commit directly in trusted environments?
```

Reason:

Owner-controlled Git is currently safer, especially on Windows due to environment-specific file reading risks.

Possible future work:

- define trusted environment criteria
- allow AI commits only in disposable branches
- require owner review before push
- keep current owner-only commit policy

## Documentation questions

### Central versus local open questions

Question:

```text
Should open questions live only in each document, or also in this central file?
```

Current recommendation:

```text
Keep local open questions in each document.
Mirror cross-cutting items here.
```

### Release checklist

Question:

```text
Should each release include a standard documentation checklist?
```

Current recommendation:

```text
Yes, for AI-assisted releases.
```

## Maintenance rule

When an open question is resolved:

1. Update the relevant design, architecture, scenario, or development document.
2. Mark the item in this file as resolved or remove it.
3. Add tests or scenario verification where appropriate.
4. Record the resolution in release notes.
