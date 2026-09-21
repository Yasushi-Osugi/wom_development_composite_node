# EV Scenario

## Purpose

This document describes the EV WOM scenario family.

The EV scenario is an educational model for comparing local and import EV supply chains, Tier-1 supplier cost structures, landed cost, tariff and FX impact, node-level P&L, and market profitability.

## Educational disclaimer

This model is fictional and educational.

Company names, vehicle names, supplier names, locations, prices, costs, capacities, and strategies are simplified or anonymized.
The scenario should not be interpreted as a factual statement about any actual EV maker, supplier, government, or market strategy.

## Model folders

Representative EV folders may include:

```text
data/sample/ev-europe-2026/
data/sample/ev-thailand-2026/
```

Exact folder names should be verified against the repository.

## Business question

The scenario explores the following question:

```text
How do local production, import production, Tier-1 supplier structure, tariff, FX,
and landed cost affect EV profitability and supply-chain resilience?
```

It is useful for showing how WOM can move beyond pure PSI into PPC and management evaluation.

## SKU structure

Typical conceptual SKU comparison:

```text
EVmaker_Local
EVmaker_Import
```

or equivalent anonymized local/import EV products.

The local SKU may represent regional production.
The import SKU may represent overseas production imported into the market.

## Physical network

### Local EV path

Conceptual structure:

```text
Inbound:
Tier-1 suppliers -> local factory MOM -> supply_point

Outbound:
supply_point -> local DC/DAD -> dealer or retail channels
```

### Import EV path

Conceptual structure:

```text
Inbound:
overseas Tier-1 suppliers -> overseas factory MOM -> supply_point

Outbound:
supply_point -> import DC/DAD -> market retail channels
```

Tier-1 suppliers may include:

- battery
- motor
- ECU or electronics
- other major components

The exact nodes should be verified against `sc_tree_master.csv`.

## Demand assumptions

Demand is generated at market or channel `leaf_out` nodes.

Possible demand channels:

- metropolitan retail
- provincial retail
- online or direct channel
- fleet or business channel

Demand may differ between local and import products depending on scenario intent.

## Capacity assumptions

Capacity may exist at:

- local EV factory
- overseas EV factory
- battery supplier
- motor supplier
- electronics supplier
- import logistics or DC
- market delivery channel

Capacity assumptions should be visible through scenario data or documented plugin behavior.

## Supplier assumptions

The EV scenario is useful for representing multiple Tier-1 suppliers.

Important design point:

```text
PPC should account for multiple supplier cost events, not only the first supplier found.
```

A good EV scenario should make supplier cost concentration visible.

## Buffer and decoupling assumptions

Possible buffer locations:

- component buffer
- factory output buffer
- import DC
- market DC
- dealer stock

Buffer design should be explained by:

- long lead time
- high unit value
- tariff or customs delay
- supplier risk
- market service requirement

## PPC assumptions

EV PPC can evaluate:

- vehicle selling price
- supplier cost
- component cost
- factory conversion cost
- logistics cost
- tariff
- FX
- landed cost
- node-level P&L
- gross margin
- profit zone

The scenario is especially useful for:

```text
Tier-1 supplier cost visibility
landed cost comparison
node-level P&L
tariff and FX sensitivity
```

## Expected outputs

Users should inspect:

- World Map for global/local network
- Network tab for local/import paths
- PPC tab for profit zone and cost waterfall
- Management dashboard for P&L and strategic KPI
- Node P&L for supplier cost concentration
- Landed Cost / Tariff & FX panel

Expected observations:

- local and import EVs have different cost structures
- multiple suppliers contribute separately to cost
- tariff and FX can materially change landed margin
- node-level P&L helps identify cost concentration
- local production may not automatically dominate import production without scenario assumptions

## Execution

Typical GUI execution:

```text
python -m main
```

Typical CLI execution should be verified against the current release and scenario folder.

## Scenario modeling notes

Public examples should use anonymized names.

Recommended style:

```text
EVmaker_Local
EVmaker_Import
Factory_Local
Factory_Import
Battery_Supplier
Motor_Supplier
ECU_Supplier
```

Avoid using real EV brand names in public educational datasets unless the scenario is clearly licensed and factual.

## Relationship to canonical WOM concepts

This scenario demonstrates:

- local/import comparison
- multi-supplier inbound cost
- PPC after PSI
- node-level P&L
- landed cost
- tariff and FX analysis
- scenario-based management evaluation
- fictional educational modeling

## Known limitations

- Real EV supply chains include many more components, suppliers, contracts, and regulatory details.
- Battery chemistry, incentives, warranty, and residual value may be outside the current model.
- Node-level P&L may currently emphasize cost concentration rather than complete transfer-price accounting.
- Some localized policy effects may need external scenario assumptions.

## Open questions

1. Should EV scenarios standardize a multi-Tier-1 supplier template?

2. Should battery, motor, ECU, and other components become canonical component categories?

3. Should tariff and local-content policy be represented as PPC rules or scenario plugins?

4. Should the EV scenario include demand incentives and subsidy phase-out?

5. Should full node-to-node transfer pricing be added for true internal P&L?

6. Should local/import comparison be generalized with Cookie and EV as templates?

## Maintenance rule

When an EV scenario is changed, update this document with:

- folder paths
- SKU names
- anonymization status
- supplier structure
- PPC assumptions
- landed cost assumptions
- known limitations
