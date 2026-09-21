# PSI and PPC Separation

## Purpose

This document defines the design intent for separating PSI and PPC in WOM.

PSI represents the physical planning layer.
PPC represents the financial evaluation layer.

The separation is a canonical WOM principle because it keeps supply chain feasibility and business impact explainable independently, while still allowing them to be connected through traceable quantities, lots, nodes, weeks, and scenarios.

## Source basis

This document is derived from:

- `CLAUDE.md`
- `AGENTS.md`
- `docs/design/wom_canonical_concepts.md`
- implementation-derived documents under `docs/architecture/`
- owner decisions accumulated through WOM development discussions

`CLAUDE.md` describes WOM as a weekly PSI-based E2E supply chain planning and simulation tool and identifies PPC as the Profit Price Cost engine executed after Planning Engine completion.

## Design intent

WOM should answer two different but connected questions.

PSI asks:

```text
What moves, when, where, and how much?
```

PPC asks:

```text
At what price, at what cost, and with what profit?
```

These two questions must be connected, but they should not be collapsed into one opaque calculation.

The design intent is:

```text
Physical flow first.
Financial evaluation second.
Business explanation always traceable back to the physical scenario.
```

PSI should remain understandable even when no financial assumptions are provided.
PPC should remain traceable to physical flow even when financial assumptions are complex.

## Canonical definitions

### PSI

PSI means:

```text
P  = Production, Purchase, or planned arrival
S  = Sales or Shipment
I  = Inventory
CO = Carry Over
```

In WOM, PSI is the operational state of each node by product and week.

PSI expresses:

- demand requirements
- supply feasibility
- lead-time effects
- capacity constraints
- inventory accumulation
- shortage or carry-over
- timing difference between requested and feasible flow

### PPC

PPC means:

```text
Price
Profit
Cost
```

In WOM, PPC is the financial evaluation layer that consumes physical flow and financial rules.

PPC may evaluate:

- market price
- supplier cost
- node cost
- conversion cost
- SGA and logistics cost
- tariff
- FX effect
- transfer price
- landed cost
- revenue
- gross profit
- profit zone
- node-level P&L

## Canonical separation principle

The canonical separation is:

```text
PSI determines physical quantities and timing.
PPC determines monetary consequences.
```

A physical planning result should not depend on market price unless an explicit scenario layer or feedback model is introduced.

A PPC result should not invent physical supply unless the PSI layer already produced it.

## Handoff from PSI to PPC

The normal handoff from PSI to PPC should include:

- product or SKU
- node
- week
- physical quantity
- lot identity when available
- sales or shipment event
- inventory or carry-over state where needed
- scenario identifier
- relevant node path or lane

PPC should use this handoff to calculate financial events.

A typical handoff flow is:

```text
Demand forecast
  -> demand-anchored lots
  -> BackwardPlanner
  -> ForwardPlanner
  -> PSI state
  -> PPC event generation
  -> financial ledger
  -> KPI / P&L / dashboard
```

## Why the separation matters

### 1. Explainability

When PSI and PPC are separated, a user can distinguish between:

- a physical shortage caused by capacity or lead time
- a margin decline caused by cost increase
- a landed cost increase caused by tariff or FX
- a revenue decline caused by lower shipment quantity
- a profit decline caused by price stickiness

Without separation, the model may produce a financial result that is difficult to diagnose.

### 2. Reusability

The same physical model can be evaluated under different financial assumptions.

For example:

- same oil supply chain, different crude price and FX assumptions
- same cookie supply chain, different import tariff assumptions
- same EV network, different supplier cost structures
- same rice distribution model, different channel margin rules

### 3. Scenario discipline

Scenario behavior should be expressed at the right layer.

Physical disruptions belong primarily to PSI inputs or plugins.
Financial shocks belong primarily to PPC rule files or economic scenario patches.
Feedback loops should be explicitly documented before they modify either layer.

### 4. Testing

PSI tests can verify movement, capacity, inventory, and carry-over.
PPC tests can verify price, cost, profit, tariff, and ledger output.

This allows smaller, safer tests.

## Canonical PPC event interpretation

PPC should preferably produce explicit events or ledger rows.

A financial ledger row should be traceable to:

- product
- node
- week
- event type
- quantity
- price or cost basis
- currency or base currency
- scenario assumption
- source rule file or rule type

This allows management reports to be explained as the sum of underlying events rather than as a black-box table.

## Physical flow should not be hidden inside PPC

PPC must not silently correct, replace, or override the PSI result.

For example, PPC should not silently assume that unmet demand was shipped.
If a business rule wants to treat lost sales, backorders, substitutions, or emergency procurement differently, that behavior should be represented as:

- a documented PPC assumption, or
- a plugin/scenario layer change, or
- an explicit extension of the planning model

## Financial assumptions should not be hidden inside PSI

PSI should not silently embed financial assumptions such as:

- price elasticity
- margin target
- transfer price
- tariff policy
- currency conversion
- profit-zone allocation

If such assumptions affect demand or capacity, they should be represented through an external scenario generator or plugin that produces updated input data.

## Feedback loops

Some business cases require feedback loops.

Examples:

- price increase causes demand destruction
- OPEC-like supply restriction causes price spike
- tariff increase changes route choice
- shortage causes channel allocation changes
- high inventory triggers production reduction

These feedback loops are valid WOM extensions, but they should not be hidden inside the canonical engine.

Preferred pattern:

```text
External scenario layer
  -> modifies demand, capacity, route, price, or cost assumptions
  -> WOM Planning Engine runs
  -> PPC evaluates financial result
  -> scenario comparison explains the effect
```

## Relationship to current implementation

The current implementation reflects this separation in several ways.

- Planning Engine runs BackwardPlanner and ForwardPlanner before PPC.
- PlanNode PSI buckets hold physical planning state.
- PPC modules under `wom/ppc/` create financial events and summaries.
- Management and PPC GUI panels display business results after planning.
- Scenario folders provide both physical CSV files and PPC rule CSV files.
- Landed Cost and Tariff & FX analysis consume scenario assumptions after or alongside planning.

Known implementation boundaries:

- Some financial paths may still contain scenario-specific helper logic.
- Some node-level P&L views currently emphasize cost concentration rather than full internal transfer-price accounting.
- Some GUI views may not expose all internal physical states such as actual shipment traces.
- Some scenario feedback loops are implemented as external patches rather than generalized closed-loop optimization.

These boundaries should remain visible and should be addressed incrementally.

## Recommended file ownership

Physical planning behavior belongs mainly in:

- `wom/engine/`
- `wom/model/`
- scenario CSV files such as `demand_forecast.csv`, `capacity_plan.csv`, `sc_tree_master.csv`
- planning plugins

Financial evaluation behavior belongs mainly in:

- `wom/ppc/`
- `wom/engine/landed_cost.py`
- PPC rule CSV files
- Management/PPC reporting code

Scenario narratives belong mainly in:

- `docs/scenarios/`
- article drafts
- scenario generator scripts
- documented assumptions

## Open questions

1. Should actual shipment traces be made a formal handoff from PSI to PPC?

2. Should all PPC calculations be event-ledger based, or should some summary calculations remain direct table operations?

3. How should node-level P&L evolve from cost concentration visibility to full internal transaction accounting?

4. Should price elasticity and demand destruction become a standard plugin pattern or remain scenario-specific generator logic?

5. How should PPC handle unmet demand:
   - lost sales
   - backorder
   - substitution
   - emergency procurement
   - allocation priority

6. How should multi-currency reporting distinguish transaction currency, functional currency, and management reporting currency?

7. Which financial effects belong in Landed Cost versus PPC core?

## Maintenance rule

When modifying PSI logic, verify that PPC still consumes the physical result correctly.

When modifying PPC logic, verify that physical planning behavior has not been silently changed.

When adding a scenario, document which assumptions belong to PSI and which assumptions belong to PPC.
