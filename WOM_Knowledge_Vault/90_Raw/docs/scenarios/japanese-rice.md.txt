# Japanese Rice Scenario

## Purpose

This document describes the Japanese Rice WOM scenario.

The scenario is an educational model for explaining domestic seasonal supply, agricultural aggregation, storage, polishing and packaging, regional distribution, retail channels, and household consumption behavior using weekly PSI.

## Educational disclaimer

This model is fictional and educational.

It should not be interpreted as a factual statement about any specific agricultural cooperative, rice producer, distributor, retailer, or government policy.
Real-world Japanese rice supply chains are more diverse and detailed than this simplified WOM model.

## Model folder

Representative model folder:

```text
data/sample/rice-japan-2027-2028/
```

Exact folder names should be verified against the repository.

## Business question

The scenario explores the following question:

```text
How does seasonal agricultural supply flow through storage, processing, distribution,
retail demand, and household consumption on a weekly PSI basis?
```

It is intended as a first understandable example of WOM because the physical supply chain is familiar and the need for seasonal buffering is intuitive.

## Physical network

Canonical physical layers:

```text
Inbound / Supply side:
rice field
  -> production-area collection center

Outbound / Demand side:
brown rice storage
  -> rice polishing and packaging center
  -> east/west distribution centers
  -> regional retail channels
  -> household inventory
  -> consumption
```

WOM node interpretation:

```text
leaf_in:
rice field or paddy source

MOM:
production-area collection center

DAD:
brown rice storage or allocation point

leaf_out:
retail channel or regional demand node
```

The exact node names should be verified against `node_master.csv` and `sc_tree_master.csv`.

## Demand assumptions

Demand is generated at retail or household-facing outbound leaves.

Typical demand characteristics:

- stable staple-food demand
- regional channel structure
- weekly consumption rhythm
- household inventory residence time

The model should not assume inappropriate holiday-driven demand spikes unless they are explicitly justified by data or scenario intent.

## Capacity assumptions

Capacity may appear at:

- production-area collection center
- storage capacity
- polishing and packaging center
- distribution center
- retail channel handling

Seasonal harvest or batch supply should be represented through scenario data or plugin behavior rather than hard-coded engine logic.

## Buffer and decoupling assumptions

Rice is a natural example of buffering.

Important buffers may include:

- brown rice storage
- distribution inventory
- household inventory

Household inventory may be modeled as a downstream residence time, often several weeks.

Design interpretation:

```text
seasonal supply is transformed into stable consumption through storage and distribution buffers
```

## PPC assumptions

Rice PPC can evaluate:

- retail price
- procurement cost
- polishing and packaging cost
- logistics cost
- channel margin
- inventory value
- gross profit
- management KPI

The scenario should keep physical PSI separate from financial evaluation.

## Expected outputs

Users should inspect:

- Network tab for physical tree structure
- PSI chart for storage and distribution behavior
- World Map if geographic nodes are defined
- Management dashboard for revenue, cost, and inventory value
- PPC tab if rice PPC rules are available

Expected observations:

- harvest or upstream supply is seasonal
- downstream demand is smoother than upstream supply
- storage buffers bridge timing mismatch
- household inventory adds a final consumption delay
- weekly PSI can explain why stock exists even when consumption is stable

## Execution

Typical GUI execution:

```text
python -m main
```

Typical CLI execution, if supported by the current release:

```text
python -m main --cli --start-week 2027-W01 --num-weeks 104
```

Actual start week and duration should be checked against the scenario data.

## Scenario modeling notes

Recommended naming:

- use generic descriptions rather than specific real organization names
- use "production-area collection center" rather than a specific cooperative name
- use "rice polishing and packaging center" for downstream processing
- use "brown rice storage" for storage before polishing where appropriate

The model should distinguish:

```text
brown rice storage
rice polishing and packaging
retail distribution
household inventory
actual consumption
```

## Relationship to canonical WOM concepts

This scenario demonstrates:

- weekly planning bucket
- Demand Anchored Lot
- Inbound and Outbound Tree
- MOM as agricultural aggregation
- DAD as storage or decoupling point
- buffer stock as time-based smoothing
- PSI-to-management KPI connection

## Known limitations

- The model is simplified and educational.
- Real rice distribution has many more actors, varieties, quality grades, contracts, and policy factors.
- Household consumption may be approximated rather than measured.
- If GUI charts focus on selected node types, some downstream household inventory behavior may require additional visualization.

## Open questions

1. Should household inventory be a standard downstream modeling pattern in WOM?

2. Should agricultural harvest timing be modeled by a standard harvest plugin?

3. Should rice grades or quality classes be modeled as separate SKUs?

4. Should brown-rice and polished-rice conversion be modeled as separate products or as node processing attributes?

5. How should household consumption be represented in PPC, if at all?

6. Should food-security or social KPI be added for staple-food scenarios?

## Maintenance rule

When the rice scenario is changed, update this document with:

- folder path
- node naming
- demand assumptions
- buffer assumptions
- start and end week
- execution method
- known limitations
