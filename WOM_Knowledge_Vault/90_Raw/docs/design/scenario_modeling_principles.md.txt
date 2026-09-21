# Scenario Modeling Principles

## Purpose

This document defines how WOM scenarios should be modeled.

A WOM scenario is an executable supply chain hypothesis.
It combines physical network structure, demand, capacity, lead time, inventory policy, cost, price, tariff, and management assumptions into a reproducible model.

This document is intended to keep future WOM examples consistent across industries such as rice, smartphone, cookie, EV, oil, vaccine distribution, and other supply chain cases.

## Source basis

This document is derived from:

- `CLAUDE.md`
- `AGENTS.md`
- `docs/design/wom_canonical_concepts.md`
- implementation-derived architecture documents under `docs/architecture/`
- owner decisions accumulated through WOM development discussions
- public article drafting experience for WOM educational cases

## Design intent

The design intent is:

```text
Scenario behavior should be expressed by model data and documented assumptions before engine code is changed.
```

A scenario should be understandable as a supply chain model, not as an unexplained collection of CSV files.

A good WOM scenario should answer:

- What business question is being explored?
- What physical supply chain is represented?
- Where does demand originate?
- Where is supply constrained?
- Where are buffers located?
- Which risks or shocks are modeled?
- Which financial assumptions are applied?
- What output should the user inspect?

## Canonical principle 1: Scenario as model, not code

A new business case should normally start as a scenario folder.

Preferred expression layers are:

```text
CSV master data
scenario generator script
plugin configuration
documented assumption
```

Engine code should be changed only when the scenario reveals a general WOM capability gap.

Examples:

- A holiday closure should be a calendar or plugin input.
- A tariff shock should be a PPC or landed-cost rule input.
- A route change should be a scenario or plugin behavior.
- A price spike should be a PPC assumption.
- A capacity disruption should be a capacity plan or override.
- A new planning algorithm should be engine code only if it is general.

## Canonical principle 2: Separate physical assumptions and financial assumptions

Physical assumptions include:

- node structure
- lead time
- capacity
- safety stock
- inventory policy
- route or lane
- production mode
- demand quantity

Financial assumptions include:

- market price
- supplier cost
- node cost
- transfer price
- tariff
- FX
- landed cost
- profit-zone rule
- management reporting currency

A scenario document should make this separation explicit.

## Canonical principle 3: Use the Inbound and Outbound Tree language

WOM scenarios should describe the supply chain using the canonical tree language.

The typical pattern is:

```text
Inbound:
leaf_in -> MOM -> supply_point

Outbound:
supply_point -> DAD -> leaf_out
```

For complex networks, additional tiers may exist, but the scenario should still explain:

- which nodes create supply
- which nodes allocate demand
- which nodes buffer variability
- which nodes represent market demand
- where the bridge between inbound and outbound planning exists

## Canonical principle 4: Demand should be anchored at market leaves

Demand should normally be generated at `leaf_out` nodes.

A scenario should define:

- SKU or product
- region or channel
- week
- demand quantity
- demand seasonality
- demand shock or demand destruction if any

Demand should not be hidden as upstream production unless the scenario is intentionally supply-push.

## Canonical principle 5: Capacity should be explicit

Capacity is one of the main scenario levers.

A scenario should identify:

- where capacity exists
- whether capacity is hard or soft
- which weeks are constrained
- whether closure is planned or disruptive
- whether capacity is physical, labor-related, logistics-related, or policy-related

When possible, capacity changes should be visible in `capacity_plan.csv`, `holiday_calendar.csv`, `cap_override.csv`, or a documented plugin.

## Canonical principle 6: Buffering stock should have a reason

Buffering stock should not be arbitrary.

A buffer should be explained by at least one of the following:

- long lead time
- high demand variability
- supply disruption risk
- decoupling need
- service-level requirement
- strategic reserve
- transportation uncertainty
- capacity mismatch

Typical buffer nodes include:

- DAD warehouse
- import buffer
- tank storage
- MOM safety stock
- strategic inventory point

The scenario should identify which buffer is intentional and what risk it absorbs.

## Canonical principle 7: Plugins should express scenario interventions

Plugins are appropriate when a scenario needs behavior that is not a static CSV value but should still remain outside the canonical engine.

Examples:

- harvest batch timing
- holiday capacity closure
- demand smoothing
- capacity override
- buffering stock optimization
- route-switching overlay
- strategic supply restriction patch

A plugin should be documented with:

- hook timing
- input files
- affected products or nodes
- no-op behavior
- expected output effect
- open limitations

## Canonical principle 8: Fictional and educational assumptions must be clear

Many WOM scenarios are educational.

They may use real-world themes, but model data may be fictional.

A scenario document should state clearly:

```text
This model is for education and simulation.
Company names, locations, prices, capacities, and strategies may be fictional.
The model should not be interpreted as a factual statement about real organizations.
```

This is especially important for:

- geopolitical risk
- oil and energy markets
- company strategy
- national supply security
- labor disputes
- disasters
- tariffs and trade policy

## Canonical principle 9: Scenario comparison should be reproducible

A scenario should be reproducible by another user or AI agent.

The document should explain:

- model folder path
- start week
- number of weeks
- GUI execution path
- CLI execution path when available
- important filters or tabs to inspect
- expected high-level behavior
- known limitations

A user should be able to rerun the scenario and confirm the main claims.

## Canonical principle 10: Article narrative and model truth should be separated

WOM articles often explain scenario results in business language.

The scenario document should distinguish:

- model assumptions
- computed results
- business interpretation
- article narrative
- open questions

Do not turn article storytelling directly into engine logic.

## Recommended scenario document structure

Each scenario document under `docs/scenarios/` should use a structure similar to:

```text
# Scenario name

## Purpose
## Educational disclaimer
## Business question
## Model folder
## Execution
## SKU structure
## Physical network
## Demand assumptions
## Capacity assumptions
## Buffer and decoupling assumptions
## PPC assumptions
## Scenario shocks
## Expected outputs
## Known limitations
## Open questions
```

## Standard CSV groups

A WOM scenario may include the following groups.

### Physical and planning master

- `sku_master.csv`
- `node_master.csv`
- `sc_tree_master.csv`
- `demand_forecast.csv`
- `capacity_plan.csv`
- `lane_assignment.csv`
- `inventory_master.csv`
- `holiday_calendar.csv`

### Cost and route master

- `node_cost_master.csv`
- `edge_cost_master.csv`
- `route_master.csv`

### PPC master

- `ppc_market_price.csv`
- `ppc_supplier_cost.csv`
- `ppc_node_cost_rule.csv`
- `ppc_edge_cost_rule.csv`
- `ppc_tariff_rule.csv`
- `ppc_transfer_price_rule.csv`
- `ppc_profit_zone_rule.csv`
- `ppc_node_profit_zone.csv`
- `ppc_fx_rate.csv`

### Plugin configuration

- `cap_override.csv`
- `decouple_optimizer_config.csv`
- other plugin-specific configuration files

Not every scenario needs every file, but missing files should be intentional.

## Scenario archetypes

### Domestic seasonal supply scenario

Example pattern:

```text
seasonal supply -> aggregation/MOM -> storage/DAD -> retail channels -> household consumption
```

Useful for:

- rice
- agriculture
- seasonal food
- regional supply-demand balance

Key modeling issues:

- harvest batch
- storage
- household inventory
- seasonality
- local channel demand

### Global manufacturing scenario

Example pattern:

```text
component suppliers -> factory/MOM -> global DC/DAD -> regional channels
```

Useful for:

- smartphone
- electronics
- precision equipment

Key modeling issues:

- multi-tier supplier structure
- long lead time
- capacity bottleneck
- regional allocation
- holiday calendar

### Import versus local scenario

Example pattern:

```text
local production path versus import path
```

Useful for:

- cookie
- EV
- consumer goods
- tariff comparison

Key modeling issues:

- landed cost
- import buffer
- domestic cost structure
- channel price
- margin comparison

### Commodity and geopolitical risk scenario

Example pattern:

```text
multiple sourcing routes -> refinery or processing/MOM -> storage/DAD -> regional retail demand
```

Useful for:

- oil
- gas
- minerals
- energy supply

Key modeling issues:

- route risk
- price spike
- FX
- strategic reserve
- alternative route capacity
- demand destruction

### Public distribution scenario

Example pattern:

```text
central procurement -> national allocation -> regional distribution -> local consumption
```

Useful for:

- vaccine
- emergency supplies
- food security
- disaster response

Key modeling issues:

- push planning
- capacity-constrained allocation
- cold chain
- priority rules
- service level

## Relationship to current implementation

The current implementation supports scenario modeling through:

- sample folders under `data/sample/`
- CSV-driven planning inputs
- GUI model selector
- CLI execution path
- plugin hooks
- PPC rule files
- management dashboards
- map and network visualization

Known implementation boundaries:

- Some scenarios may still require generator scripts not yet formalized under `tools/`.
- Some open questions may be documented in `CLAUDE.md` before being migrated to `docs/`.
- Some scenario-specific PPC behavior may still exist in code and should be identified during refactoring.
- Some GUI views may not yet expose all internal planning states needed for advanced scenario diagnosis.

## Open questions

1. Should each sample scenario have a required `docs/scenarios/<scenario>.md` before release?

2. Should scenario folders include a machine-readable `scenario_manifest.yml` or `scenario_manifest.json`?

3. Should article-ready scenarios include a standard reproducibility checklist?

4. How should scenario generator scripts be stored and named?

5. Which scenario assumptions should be validated by automated tests?

6. Should scenario-specific plugins live under the general plugin system or under scenario folders?

7. How should fictional disclaimers be standardized for public examples?

## Maintenance rule

When adding or changing a scenario, update the corresponding scenario document.

When changing the canonical engine because of a scenario, document why the change is general rather than scenario-specific.

When publishing an article based on a scenario, ensure that the article narrative, scenario data, and scenario documentation remain consistent.
