# Cookie Japan Scenario

## Purpose

This document describes the Cookie Japan WOM scenario.

The scenario is an educational model for comparing local production and import production in a consumer packaged goods supply chain.
It is useful for explaining landed cost, import buffering, local cost structure, channel margin, DAD safety stock, and PPC cost waterfall.

## Educational disclaimer

This model is fictional and educational.

Company names, brands, factories, distribution centers, prices, costs, and capacities are simplified or fictionalized.
The scenario should not be interpreted as a factual statement about any real food company or retail channel.

## Model folder

Representative model folder:

```text
data/sample/Cookie-jp-2026/
```

The exact capitalization should be verified against the repository.

## Business question

The scenario explores the following question:

```text
How do local production and import production differ in physical lead time, buffer inventory,
landed cost, channel economics, and profit structure?
```

It is designed as a compact teaching case for PSI plus PPC.

## SKU structure

Conceptual SKU comparison:

```text
Cookie_Local
Cookie_Import
```

The local SKU represents domestic production and distribution.
The import SKU represents overseas production, long-distance movement, import buffering, and domestic distribution.

## Physical network

### Local production path

Conceptual structure:

```text
Inbound:
domestic inputs -> local factory MOM -> supply_point

Outbound:
supply_point -> local DC/DAD -> retail channels
```

### Import production path

Conceptual structure:

```text
Inbound:
overseas inputs or factory -> import MOM or factory -> supply_point

Outbound:
supply_point -> import buffer DAD -> domestic main DC -> retail channels
```

The import path may include a two-stage DAD chain such as:

```text
import buffer -> main domestic DC
```

The exact nodes should be verified against `sc_tree_master.csv`.

## Demand assumptions

Demand is generated at retail channel `leaf_out` nodes.

Possible channels:

- mass retail
- convenience or specialty retail
- online retail
- regional retail channels

The local and import SKUs may share similar demand patterns so that physical and financial differences are easier to compare.

## Capacity assumptions

Capacity may exist at:

- local factory
- overseas factory
- import buffer
- domestic DC

The scenario can be used to test capacity limits, but its main educational value is the comparison of cost structure and buffer design.

## Buffer and decoupling assumptions

Import path buffering is a central feature.

The import SKU may require larger DAD buffer inventory due to:

- long lead time
- customs or port uncertainty
- import replenishment risk
- container transport timing

Local production may require less buffer if lead time is shorter.

Design interpretation:

```text
long-distance import buys resilience through buffer inventory
```

## PPC assumptions

Cookie PPC can evaluate:

- market price
- supplier cost
- factory conversion cost
- DC cost
- SGA cost
- import tariff
- freight cost
- landed cost
- profit zone
- cost waterfall
- node-level P&L

The scenario is useful for showing the difference between:

```text
local cost structure
import landed cost structure
```

## Expected outputs

Users should inspect:

- Network tab for local versus import path
- PSI chart for DAD buffer inventory
- PPC tab for cost waterfall
- Management dashboard for P&L
- Node P&L for cost concentration
- Landed Cost panel if tariff and route rules are active

Expected observations:

- import path has larger buffer inventory
- import path may have tariff and freight cost
- local path may have different conversion and SGA structure
- margin differences are visible in PPC
- DAD buffer inventory should be visible when `buffering_stock_flag` and `ss_days` are active

## Execution

Typical GUI execution:

```text
python -m main
```

Typical CLI execution depends on current repository support and should be verified.

## Scenario modeling notes

Historical note:

Earlier naming may have used "biscuit" or older SKU names.
The public scenario should use "cookie" consistently.

Important modeling rule:

```text
DAD-side buffer stock is valid WOM behavior when the node is a decoupling point and safety stock is configured.
```

Older notes that described DAD inventory as always zero should be treated as obsolete if they conflict with current identity-matching behavior.

## Relationship to canonical WOM concepts

This scenario demonstrates:

- local versus import scenario comparison
- DAD buffer stock
- import lead time
- landed cost
- tariff and freight assumptions
- PSI/PPC separation
- node-level P&L
- cost waterfall
- scenario as model data

## Known limitations

- The scenario is simplified and educational.
- Real cookie supply chains may include more ingredients, packaging suppliers, quality constraints, and channel programs.
- True brand economics may require more detailed transfer pricing.
- Some PPC paths may still contain scenario-specific helper logic and should be reviewed over time.

## Open questions

1. Should local/import comparison become a standard scenario template?

2. Should DAD buffer display be standardized in GUI charts?

3. Should import buffer optimization be exposed through the GUI?

4. Should tariff and freight sensitivity become a standard scenario exercise?

5. Should Cookie_Local and Cookie_Import share a common demand profile by default?

6. Should cost waterfall outputs be standardized across all PPC scenarios?

## Maintenance rule

When the cookie scenario is changed, update this document with:

- SKU names
- node names
- import buffer structure
- PPC rule changes
- tariff assumptions
- known limitations
