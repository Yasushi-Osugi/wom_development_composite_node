# Smartphone Global Scenario

## Purpose

This document describes the Smartphone Global WOM scenario.

The scenario is an educational model for explaining global manufacturing, component supply, regional demand, capacity constraints, holiday effects, lead time, global distribution, and management KPI using weekly PSI.

## Educational disclaimer

This model is fictional and educational.

It should not be interpreted as a factual statement about any actual smartphone manufacturer, supplier, region, or product strategy.
Any similarity to real global electronics supply chains is used only as a simplified teaching analogy.

## Model folder

Representative model folder:

```text
data/sample/iphone-2027-2029/
```

The folder name and SKU names should be verified against the repository.

## Business question

The scenario explores the following question:

```text
How does a global electronics supply chain translate regional market demand into upstream
component and assembly requirements under lead time, capacity, and disruption constraints?
```

It is useful for explaining the global nature of WOM.

## Physical network

A typical smartphone WOM structure is:

```text
Inbound:
component suppliers
  -> component buffer or tier nodes
  -> final assembly MOM
  -> supply_point

Outbound:
supply_point
  -> global or regional DAD
  -> regional retail channels
```

Possible upstream components include:

- display
- battery
- semiconductor
- camera module
- casing
- memory
- assembly materials

The exact nodes should be verified against `node_master.csv` and `sc_tree_master.csv`.

## Demand assumptions

Demand is generated at regional or channel `leaf_out` nodes.

Typical demand characteristics:

- regional launch demand
- product lifecycle curve
- channel seasonality
- promotional peaks
- market-specific demand levels
- possible demand smoothing

Demand should be represented by weekly `demand_forecast.csv`.

## Capacity assumptions

Capacity may exist at:

- final assembly MOM
- component suppliers
- wafer or semiconductor buffer
- logistics nodes
- regional DCs

A smartphone scenario is useful for capacity-aware planning because the MOM or component tier may become a bottleneck.

Capacity changes should be modeled through:

- `capacity_plan.csv`
- holiday calendar
- cap override
- plugin behavior
- scenario generator output

## Lead time assumptions

Global electronics supply chains often have long and layered lead times.

Lead time may appear in:

- inbound component movement
- assembly response time
- ocean or air transport
- regional distribution
- channel replenishment

The scenario should document whether lead time is physical movement, planning offset, safety-stock timing, or a simplified modeling parameter.

## Buffer and decoupling assumptions

Buffers may appear at:

- component buffers
- assembly output
- regional DCs
- strategic stock points
- launch inventory

A buffer should be explained by:

- long lead time
- capacity bottleneck
- launch risk
- regional demand variability
- supplier uncertainty

## PPC assumptions

Smartphone PPC can evaluate:

- market price
- supplier cost
- component cost
- assembly cost
- logistics cost
- tariff
- FX
- gross profit
- regional margin
- node-level P&L

PPC assumptions should remain separate from physical PSI.

## Expected outputs

Users should inspect:

- World Map for global node distribution
- Network tab for inbound/outbound tree
- PSI charts for capacity and inventory behavior
- Management dashboard for KPI
- PPC tab for profit and cost evaluation
- Fill rate or shortage behavior during constrained weeks

Expected observations:

- regional demand pulls upstream requirements backward
- capacity constraints create CO or delayed fulfillment
- buffers absorb some timing mismatch
- PPC shows business impact of supply constraints and cost structure
- global lead time creates visible planning offsets

## Execution

Typical GUI execution:

```text
python -m main
```

Typical CLI execution:

```text
python -m main --cli --start-week 2027-W01 --num-weeks 156
```

The exact planning horizon should be verified against the scenario data.

## Scenario modeling notes

A smartphone scenario should be careful about real brand names.

Recommended public-facing pattern:

```text
Smartphone_Global
Smartphone_Local
Smartphone_Import
Global_Phone
```

When using familiar names internally for education, public article text should clarify that the model is fictional.

## Relationship to canonical WOM concepts

This scenario demonstrates:

- global E2E planning
- Demand Anchored Lot
- Backward and Forward planning
- multi-region leaf_out demand
- MOM capacity constraint
- inbound component dependency
- holiday calendar plugin
- PPC after planning
- management KPI from physical flow

## Known limitations

- Real smartphone BOMs and supplier networks are far more complex.
- Product launch behavior may require special demand-generation assumptions.
- Some supplier tiers may be simplified.
- Some route and allocation policies may be approximated.
- True optimization of allocation priorities may require future policy modules.

## Open questions

1. Should launch curves be standardized as a demand-generation pattern?

2. Should multi-tier BOM be represented explicitly or simplified through leaf_in suppliers?

3. Should regional allocation priority become a standard Demand Allocation Policy?

4. Should product lifecycle state be a formal SKU attribute?

5. Should expedited logistics be a PPC-only cost scenario or a physical route scenario?

6. Should component substitution be represented by alternate inbound trees?

## Maintenance rule

When the smartphone scenario is changed, update this document with:

- folder path
- SKU names
- global region definitions
- capacity assumptions
- lead time assumptions
- PPC assumptions
- known limitations
