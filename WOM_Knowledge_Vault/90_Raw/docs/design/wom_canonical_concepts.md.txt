# WOM Canonical Concepts

## Purpose

This document defines the canonical concepts of WOM.

WOM stands for Weekly Operation Model.
WOM is a weekly, end-to-end supply chain planning and simulation model.
It uses weekly PSI buckets, supply chain trees, demand-anchored lots, capacity constraints,
and financial evaluation layers to make supply chain behavior visible and explainable.

This document is intended to be AI-neutral.
It should be read by Claude Code, ChatGPT Codex, and any future AI development agent before modifying WOM.

This document is not a feature specification for one scenario.
It is the design constitution of WOM.

## Source basis

This document is derived from:

- `CLAUDE.md`
- `AGENTS.md`
- implementation-derived architecture documents under `docs/architecture/`
- current development status under `docs/development/current_status.md`
- owner decisions accumulated through WOM development discussions

`CLAUDE.md` may contain Claude-specific guidance and historical release notes.
Those notes are useful context, but the canonical WOM knowledge should be maintained under `docs/`.

If this document and implementation-derived documents differ, the difference should be recorded as an open question or a refactoring item.

## Design intent

WOM is designed to connect three levels of supply chain understanding.

```text
Physical Layer  <->  Planning Layer  <->  Management Layer

real nodes/maps      SCTree + PSI          KPI / PPC / P&L
```

The design intent is not merely to calculate inventory.
The design intent is to make the causal chain of global supply chain operations visible on a weekly time axis.

WOM should answer questions such as:

- Where is demand generated?
- Which supply nodes must respond?
- Which lots move through which nodes and weeks?
- Where does capacity become binding?
- Where does inventory accumulate?
- Where does shortage or carry-over occur?
- How do physical flow changes affect price, cost, profit, landed cost, and KPI?
- Which scenario assumptions caused the observed business result?

WOM should remain a general planning engine.
Scenario-specific behavior should be expressed through input data, scenario files, plugins, or documented assumptions,
not by hard-coding one business case into the canonical engine.

## Canonical concept 1: Weekly planning bucket

WOM uses week as the primary time bucket.

The week is the bridge between:

- monthly or quarterly management planning
- daily or transactional execution
- long-horizon supply chain simulation

A WOM model should be able to run across multiple years using consistent weekly buckets.

Canonical rule:

```text
All planning behavior should be explainable as weekly movement of PSI state.
```

If a model requires daily or hourly behavior, that behavior should be aggregated, approximated, or documented before being introduced into the canonical engine.

## Canonical concept 2: PSI as the operational state

WOM represents operational state using PSI buckets.

```text
S  = Sales / Shipment
CO = Carry Over
I  = Inventory
P  = Purchase / Production / Planned arrival
```

In implementation terms, each PlanNode holds PSI buckets for both demand-side planning and supply-side planning.

```text
psi4demand[week][bucket]
psi4supply[week][bucket]
```

Design interpretation:

- `psi4demand` expresses the demand-requesting view.
- `psi4supply` expresses the supply-responding view.
- Backward planning writes demand-side requirements.
- Forward planning writes supply-side feasibility and resulting inventory or carry-over.

Canonical rule:

```text
Do not change the meaning of S, CO, I, or P casually.
```

If a future change requires a new interpretation of these buckets, it must be documented before code changes are made.

## Canonical concept 3: Demand Anchored Lot

The core economic object in WOM is the demand-anchored lot.

A demand-anchored lot begins from market demand at an outbound leaf node.
It is then propagated backward through the supply chain to determine when and where upstream operations must respond.

Design interpretation:

```text
Market demand creates lots.
Lots create time-phased requirements.
Requirements propagate backward.
Supply feasibility is tested forward.
```

The lot is not just a quantity.
It is the traceable identity of a demand requirement across time, node, and product.

Canonical rule:

```text
Demand should remain traceable from leaf_out demand to upstream supply response.
```

This traceability is the foundation for PSI explanation, shortage explanation, PPC evaluation, and future AI-assisted diagnosis.

## Canonical concept 4: Inbound Tree and Outbound Tree

WOM models the supply chain as two connected trees.

```text
Inbound Tree                         Outbound Tree

leaf_in                              supply_point
  -> MOM                               -> DAD
      -> supply_point bridge              -> leaf_out
```

Canonical node roles:

| node_type | Side | Canonical role |
|---|---|---|
| `leaf_in` | Inbound | supplier, material source, farm, component source |
| `mom` | Inbound | Mother of Manufacturing, main supply node, factory, refinery, aggregation point |
| `supply_point` | Bridge / Outbound root | bridge between inbound and outbound planning |
| `dad` | Outbound | demand allocation, distribution, decoupling, warehouse, DC |
| `leaf_out` | Outbound | market, sales channel, regional demand leaf |

Design interpretation:

- Inbound Tree explains how supply is created.
- Outbound Tree explains how demand is served.
- `supply_point` connects both worlds.
- `MOM` is usually the main constrained supply node.
- `DAD` is usually the allocation or decoupling node.
- `leaf_out` is where demand is anchored.

Canonical rule:

```text
Do not collapse inbound and outbound logic into one undifferentiated network.
```

The two-tree structure is a key modeling language of WOM.

## Canonical concept 5: Backward then Forward planning

The canonical WOM planning sequence is:

```text
1. Load demand forecast
2. Generate demand lots
3. Build SCTree
4. Run pre-plan plugins
5. Run BackwardPlanner
6. Copy demand-side PSI to supply-side PSI
7. Run post-copy plugins
8. Run ForwardPlanner
9. Derive planning DataFrame and KPI
10. Run PPC engine
```

Design interpretation:

- Backward planning asks: What would be required to satisfy market demand?
- Forward planning asks: What can actually be supplied under physical and capacity constraints?
- CO is the trace of unmet demand or delayed fulfillment.
- Inventory is the trace of supply arriving before demand consumption.

Canonical rule:

```text
Backward planning defines requirements.
Forward planning tests feasibility.
```

The two should not be mixed without explicit design documentation.

## Canonical concept 6: Capacity-aware planning

WOM accepts demand and capacity as externally given model inputs.

Capacity is not merely a parameter.
Capacity is the boundary between requested plan and feasible plan.

Typical capacity inputs include:

- hard capacity
- soft capacity
- closure periods
- holiday calendars
- temporary override rules
- bottleneck constraints
- disruption scenarios

Design interpretation:

```text
Demand creates pressure.
Capacity creates constraint.
Inventory and CO reveal the gap.
```

Canonical rule:

```text
Capacity effects should be visible in PSI, not hidden inside scenario-specific code.
```

## Terminology note: MEO and CPU

WOM uses a common lot-sizing concept to express the minimum unit of flow that the planning engine processes.

```text
CPU = Common Planning Unit
MEO = Minimum Economic Object
```

CPU and MEO are synonyms referring to the same underlying concept: the minimum size of a processed flow unit in a WOM model.

Design interpretation:

- **CPU** is the term used when WOM models a specific company's supply chain (the typical case in current sample scenarios such as `rice-japan-2027-2028`, `Cookie-jp-2026`, `ev-thailand-2026`, `oil-global-2027`). In implementation terms, CPU corresponds to the `cpu_size` column in `sc_tree_master.csv`.
- **MEO** is the term used when WOM modeling is extended beyond a single company's business activity to broader economic activity, including government agencies or other non-corporate actors. In that broader context, MEO defines the minimum unit and size of the processed flow being modeled.

Canonical rule:

```text
CPU and MEO refer to the same lot-sizing concept at different modeling scopes.
Use CPU for company-scoped supply chain models.
Use MEO when the modeling scope extends to general economic activity beyond a single company.
```

No separate engine implementation is required to move between the two terms; the existing `cpu_size` field in `sc_tree_master.csv` remains the implementation-level representation regardless of which term is used in scenario documentation.

## Canonical concept 7: Decoupling and buffering stock

WOM supports decoupling points and buffering stock.

A decoupling point is a node where inventory may intentionally accumulate to absorb variability, lead time, or disruption.

Typical examples:

- MOM safety stock
- DAD buffer stock
- import buffer warehouse
- tank storage
- strategic inventory point

Design interpretation:

```text
Buffer stock is time purchased in advance.
```

A long-distance or high-risk supply chain may require more buffering than a short and stable supply chain.

Canonical rule:

```text
Buffering behavior should be represented through node attributes, lead time, safety stock settings, and planning logic.
```

Do not treat buffer stock as merely a chart label.
It is part of the physical and economic model.

## Canonical concept 8: Plugin layer

WOM uses plugins to express scenario-specific interventions without changing the canonical engine.

Plugin hooks may be used before or after major planning steps.

Examples of plugin responsibilities:

- harvest batch behavior
- holiday calendar behavior
- capacity override
- demand smoothing
- buffering stock optimization
- future route-switching or disruption overlays

Design interpretation:

```text
The engine should remain canonical.
Scenario behavior should live outside the engine when possible.
```

Canonical rule:

```text
If a behavior is scenario-specific, prefer CSV, plugin, generator script, or documented assumption.
```

Only promote scenario behavior into the engine when it is clearly general across WOM.

## Canonical concept 9: PSI and PPC separation

WOM separates physical flow simulation from financial evaluation.

PSI answers:

```text
What moves, when, where, and how much?
```

PPC answers:

```text
At what price, at what cost, and with what profit?
```

PPC means:

```text
Price
Profit
Cost
```

Design interpretation:

- PSI should establish physical flow and weekly quantities.
- PPC should evaluate revenue, supplier cost, node cost, tariff, transfer price, profit zone, and node-level P&L.
- Landed Cost and Tariff & FX analysis belong to the Management Layer and should consume physical and financial assumptions.

Canonical rule:

```text
Do not mix physical planning logic and financial assumptions unnecessarily.
```

Physical feasibility should be explainable even before money is calculated.
Financial impact should be traceable back to physical flow.

## Canonical concept 10: Scenario as model, not code

WOM scenarios should be expressed primarily by data.

A scenario folder typically contains CSV files such as:

- `sku_master.csv`
- `demand_forecast.csv`
- `node_master.csv`
- `sc_tree_master.csv`
- `capacity_plan.csv`
- `lane_assignment.csv`
- `inventory_master.csv`
- `holiday_calendar.csv`
- `edge_cost_master.csv`
- `route_master.csv`
- `ppc_market_price.csv`
- `ppc_supplier_cost.csv`
- `ppc_node_cost_rule.csv`
- `ppc_tariff_rule.csv`
- `ppc_transfer_price_rule.csv`

Design interpretation:

```text
A WOM scenario is an executable supply chain hypothesis.
```

It should be possible to compare business cases by changing model data and assumptions,
without rewriting the planning engine.

Canonical rule:

```text
New business cases should start as scenario data, not as engine modifications.
```

## Canonical concept 11: Educational and fictional modeling

Many WOM sample scenarios are educational models.

They may use fictional companies, fictional prices, fictional locations, fictional capacities, and simplified assumptions.

Design interpretation:

```text
Educational scenarios are not forecasts.
They are model-based thought experiments.
```

Canonical rule:

```text
When using real-world themes, clearly separate fictional model assumptions from real-world facts.
```

This is especially important for articles, public examples, and geopolitical or company strategy scenarios.

## Canonical concept 12: Management Layer and living KPI

WOM is not limited to operational charts.

The Management Layer connects PSI behavior to business evaluation.

Typical management views include:

- revenue
- cost
- gross profit
- inventory value
- fill rate
- landed cost
- tariff and FX impact
- node-level P&L
- strategic KPI
- profit zone

Design interpretation:

```text
WOM should show how supply chain causes business results over time.
```

A KPI should not be only a static report number.
It should be explainable as the result of weekly node-level operational behavior.

Canonical rule:

```text
KPI should be connected back to node, product, week, and scenario assumption whenever possible.
```

## Canonical concept 13: AI-assisted development

WOM is developed with AI assistance, but the repository is the source of truth.

AI agents may help:

- inspect code
- draft documentation
- propose refactoring
- generate tests
- create scenario data
- identify inconsistencies
- explain current behavior

However, AI agents should not silently redefine WOM.

Canonical rule:

```text
AI may assist implementation.
The owner confirms design intent.
The repository records the result.
```

Important design decisions should be stored under `docs/`, not only in chat logs or AI-specific context files.

## Non-goals

The following are not canonical goals of WOM at this stage:

- replacing all ERP, APS, WMS, TMS, or financial systems
- simulating every transaction at daily or hourly precision
- embedding every industry-specific rule directly into the engine
- treating one sample scenario as the universal planning model
- making AI the final judge of supply chain correctness

WOM should remain a compact, explainable, extensible weekly planning and simulation model.

## Relationship to current implementation

The current implementation already reflects many canonical concepts:

- GUI and CLI entrypoints exist.
- Planning uses BackwardPlanner and ForwardPlanner.
- PlanNode holds PSI buckets.
- SCTree represents inbound and outbound structures.
- Plugin hooks exist around the planning sequence.
- PPC runs after planning and produces financial outputs.
- Management and PPC tabs visualize business results.
- Scenario folders define executable model assumptions.

Known implementation boundaries should remain visible:

- Some GUI charts may not yet expose all internal planning states.
- Some KPI DataFrames may focus on leaf_out nodes.
- Some scenario-specific PPC paths may still exist.
- Some historical release notes may refer to older branch names or behavior.
- AI-specific files such as `CLAUDE.md` may contain useful but non-canonical context.

These boundaries should be resolved by documentation, tests, and incremental refactoring.

## Open questions

1. Which WOM concepts should be treated as permanent kernel concepts, and which should remain scenario-layer conventions?

2. How should `actual_s` or equivalent actual-shipment traces be exposed to GUI, CSV export, and KPI calculation?

3. Should DAD-side buffer stock be displayed in the same standard chart family as MOM buffer stock?

4. Should `cap_hard = 0.0` mean "no capacity specified" or "intentional full closure"?
   If both meanings are needed, a separate explicit closure flag may be required.

5. How far should node-level P&L go?
   Current node-level P&L is useful for cost concentration visibility, but full internal transfer-price accounting across all nodes may require a larger PPC design.

6. Which scenario behaviors should be promoted from plugin or CSV logic into the canonical engine?

7. How should the repository distinguish between:
   - implementation fact
   - design intent
   - scenario assumption
   - article narrative
   - open research question

8. Should `sc_tree_master.csv` introduce a distinct `meo_size` field for non-corporate / general economic activity scenarios, or should `cpu_size` remain the single implementation field for both CPU and MEO scopes?

## Maintenance rule

When changing WOM behavior, update this document if the change affects a canonical concept.

When adding a new scenario, update scenario documentation instead of changing this document,
unless the scenario reveals a new general WOM concept.

When an AI agent proposes a change to this file, the owner should review whether the proposed change is:

```text
canonical WOM knowledge
or
scenario-specific knowledge
or
temporary implementation detail
```

Only the first category belongs here.
