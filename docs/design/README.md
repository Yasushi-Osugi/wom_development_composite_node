# WOM Design Documents

This directory contains canonical WOM design intent.

Design documents describe why WOM is structured as it is.
They are AI-neutral and should be usable by Claude Code, ChatGPT Codex, and future AI development agents.

## Production allocation and priority supply

Start with [WOM production allocation and priority supply](./WOM_Production_Allocation_ThreeLayer_BSSEAF_Design_v0.1.md)
(knowledge ID `WOM-KB-ALLOCATION-001`, 2026-10-26). It maps the existing
Management / Demand / Supply functions, allocation-to-demand CSV handoff,
planning-loop CLI, and the conditions to check before reusing them in a new case.
It distinguishes an implemented capability from activation and validation in a
particular model.

The older [three-layer design record](./three_layer_production_allocation.md)
records the 2026-08-20 investigation. Read its historical statements about
unconnected layers together with the later handoff and planning-loop implementation.

## Documents

```text
wom_canonical_concepts.md
  The design constitution of WOM.

demand_anchored_lot.md
  Demand Anchored Lot as the core traceable planning object.

psi_ppc_separation.md
  Separation between physical PSI planning and financial PPC evaluation.

scenario_modeling_principles.md
  How WOM scenarios should be modeled and documented.

holiday_calendar_push_lead_time_and_planning_horizon.md
  Integrated design for holiday capacity semantics, push production lead time,
  and planning/reporting horizons.

holiday_calendar_and_capacity_semantics.md
  Detailed design for explicit closures, zero/unlimited capacity semantics,
  partial-capacity overrides, and Backward/Forward Planner behavior.

push_production_lead_time.md
  Detailed design for push lead-time semantics, consistency with physical lead
  time, Demand Anchored Lot retiming, and future planning-node role separation.

planning_warmup_and_reporting_horizon.md
  Detailed design for planning warm-up periods and the separation of the
  Planning Horizon from the Management Reporting Horizon.

wom_model_typology.md
  How to classify a WOM allocation case by the structure of its profit function
  (linear / non-concave / fixed-charge), using structural_optimality_gap as the
  measuring instrument. Records measured results per case and the vocabulary of
  mechanisms that make the profit function non-linear in the allocation.
```

## Relationship among the planning design documents

`holiday_calendar_push_lead_time_and_planning_horizon.md` is the integrated
design that explains the relationship among three concerns:

```text
holiday and capacity state
push production timing
planning and reporting periods
```

The following documents provide focused views of those same concerns:

```text
holiday_calendar_and_capacity_semantics.md
push_production_lead_time.md
planning_warmup_and_reporting_horizon.md
```

These focused documents intentionally repeat some background, principles,
configuration examples, and acceptance criteria from the integrated design.
The duplication allows each document to be reviewed, implemented, and
maintained independently while preserving links to the overall design.

The initial use case is `data/sample/soysauce-us-2027`, but the concepts are
reusable WOM design rules rather than scenario-specific operating instructions.

## Canonical principle

WOM should remain:

```text
weekly
traceable
scenario-driven
capacity-aware
PSI/PPC-separated
AI-assisted but repository-grounded
```

## Maintenance rule

Design documents should not become scenario-specific manuals.

When a new scenario reveals a reusable WOM concept, update design documents.
When a detail belongs only to one scenario, update `docs/scenarios/`.

For the four related planning documents above:

```text
integrated design
  explains cross-topic intent and dependencies

focused design
  owns detailed rules, implementation requirements, and acceptance criteria
  for its specific design concern
```

When a focused document changes a shared design decision, review the integrated
document and the other related focused documents for consistency.
