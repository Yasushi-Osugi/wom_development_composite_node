# WOM Documentation

This directory contains repository-based WOM knowledge.

The purpose of this documentation set is to make WOM development understandable from multiple AI coding environments without depending on a single AI-specific context file.

## Documentation map

```text
docs/
  architecture/   implementation-derived system structure
  design/         canonical WOM design intent
  scenarios/      scenario-level assumptions and usage notes
  development/    release, workflow, status, and open questions
```

## Recommended reading order

For a new human developer or AI agent:

```text
1. AGENTS.md
2. docs/development/current_status.md
3. docs/design/wom_canonical_concepts.md
4. docs/architecture/repository_map.md
5. docs/architecture/runtime_entrypoints.md
```

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

For scenario work:

```text
docs/design/scenario_modeling_principles.md
docs/scenarios/<scenario>.md
```

For AI-assisted development workflow:

```text
docs/development/ai_vibe_coding_workflow.md
```

## Knowledge policy

Chat logs are useful for exploration.
Repository documents are the durable source of truth.

When WOM behavior changes, update:

- implementation code
- relevant tests
- relevant design documents
- relevant scenario documents
- current status or open questions when needed

## Document types

### Architecture documents

Architecture documents describe what the current code does.

They should be grounded in:

- source files
- tests
- runtime entrypoints
- sample data
- observed behavior

### Design documents

Design documents describe why WOM is designed this way.

They should distinguish:

- canonical concepts
- design intent
- current implementation boundary
- future open questions

### Scenario documents

Scenario documents describe executable supply chain hypotheses.

They should distinguish:

- model assumptions
- fictional or educational disclaimers
- physical network
- demand and capacity assumptions
- PPC assumptions
- expected outputs
- limitations

### Development documents

Development documents describe how WOM is developed and released.

They should include:

- current status
- workflow
- release notes
- open questions
- documentation generation plans

## Maintenance rule

When an AI agent creates or modifies a document, the owner should check whether the content is:

```text
implementation fact
design intent
scenario assumption
article narrative
open question
```

Each category should be kept in the right document family.
