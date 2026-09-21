# Demand Anchored Lot

## Purpose

This document defines the design intent of the Demand Anchored Lot concept in WOM.

The Demand Anchored Lot is the core traceable planning object in WOM.
It connects market demand to upstream supply requirements, weekly PSI state, capacity feasibility, carry-over, inventory, and financial evaluation.

## Source basis

This document is derived from:

- `CLAUDE.md`
- `AGENTS.md`
- `docs/design/wom_canonical_concepts.md`
- implementation-derived documents under `docs/architecture/`
- owner decisions accumulated through WOM development discussions

## Design intent

WOM starts planning from market demand.

The design intent is:

```text
Demand creates lots.
Lots create requirements.
Requirements propagate backward.
Supply feasibility is tested forward.
Business impact is evaluated afterward.
```

The lot is not only a quantity.
It is an identity that allows WOM to explain where a demand requirement came from, where it moved, where it was delayed, and how it contributed to business results.

## Canonical definition

A Demand Anchored Lot is a planning unit generated from demand at an outbound leaf node.

It should normally carry or imply:

- product or SKU
- demand region or channel
- demand week
- quantity unit
- lot identity
- originating `leaf_out`
- path through Outbound Tree and Inbound Tree
- timing offsets from lead time and safety stock
- relationship to PSI buckets
- relationship to PPC evaluation when shipped or sold

A lot should be traceable even when it is delayed, carried over, buffered, or matched against supply.

## Why demand anchoring matters

Demand anchoring makes WOM market-driven.

Without demand anchoring, a supply chain simulator may become a push-flow animation that does not explain which market requirement caused which upstream action.

With demand anchoring, WOM can answer:

- Which market demand created this upstream production requirement?
- Which week did the requirement originate?
- Which node is responsible for fulfilling it?
- Which lots were delayed by capacity?
- Which lots remained as inventory?
- Which lots became carry-over?
- Which lots generated revenue or profit?

## Relationship to PSI

Demand Anchored Lots are the objects that populate PSI buckets.

A simplified interpretation is:

```text
S  = lots requested or shipped
CO = lots not yet fulfilled
I  = lots physically available but not consumed
P  = lots planned to arrive, be produced, or be purchased
```

In WOM, the same lot identity may appear in different PSI buckets as planning proceeds.

Backward planning and forward planning should preserve enough identity to explain lot movement and mismatch.

## Backward planning interpretation

Backward planning starts from `leaf_out` demand.

It asks:

```text
What upstream requirement must exist, and when, to satisfy this demand?
```

Backward propagation uses:

- node path
- lead time
- safety stock timing
- tree relationships
- product or SKU
- demand lot identity

The result is a time-phased requirement view.

This is represented as demand-side PSI.

## Forward planning interpretation

Forward planning starts from the supply-side feasibility problem.

It asks:

```text
Given capacity and physical movement, which demand lots can actually be fulfilled?
```

Forward planning should compare demand lots and supply lots using identity whenever possible.

The preferred interpretation is:

```text
I1  = physically available lots not consumed by demand
CO1 = demanded lots not found in physically available supply
```

This identity-based matching is important because a simple count-based comparison can hide which demand lots were delayed.

## Lot identity matching

Lot identity matching means WOM should compare actual lot IDs, not only quantities.

A conceptual rule is:

```text
matched demand = demand lots that exist in available supply
unmatched demand = demand lots that do not exist in available supply
unmatched supply = supply lots that are not consumed by demand
```

This supports:

- honest carry-over
- visible inventory
- better shortage diagnosis
- future lot-level event tracing
- PPC linkage to actual shipments

## S, CO, I, and P with lot identity

A canonical interpretation is:

```text
Available supply = beginning inventory + planned arrival
Demand to satisfy = carry-over + current demand
Inventory = available supply - demand to satisfy
Carry-over = demand to satisfy - available supply
```

The subtraction should be interpreted by lot identity, not merely by count, when lot identities are available.

## Plan versus actual shipment

A key design distinction is:

```text
planned S
actual shipped lots
```

In demand-anchored planning, `S` may represent the market request or planned shipment requirement.
Actual shipped lots may need to be held separately when supply is constrained.

This distinction avoids corrupting demand identity.

The model can then preserve:

- the original requested demand
- the actual fulfilled lots
- the carry-over lots
- the inventory lots

## Relationship to Inbound and Outbound Trees

Demand Anchored Lots are created at the Outbound Tree leaves.

```text
leaf_out
  -> DAD
  -> supply_point
  -> MOM
  -> leaf_in
```

The lot gives a common thread across the two-tree structure.

Outbound Tree explains demand allocation and distribution.
Inbound Tree explains supply generation and capacity response.

The same market demand can therefore be viewed as both:

- a downstream customer requirement
- an upstream production or procurement requirement

## Relationship to capacity

Capacity determines whether demand-anchored requirements can be fulfilled in time.

When capacity is sufficient:

```text
demand lots flow through the planned path and timing
```

When capacity is insufficient:

```text
some demand lots become carry-over or are delayed
```

This is why lot identity matters.
The model should be able to explain not only how many lots were short, but which demand lots were short.

## Relationship to buffering stock

Buffering stock can be interpreted as pre-positioned time.

When safety stock or decoupling behavior causes inventory to accumulate, the inventory should still be explainable in lot terms.

A buffer is not only an amount.
It is a set of lots held at a node before downstream demand consumes them.

## Relationship to PPC

PPC should ideally evaluate financial results from lots or lot-derived events.

For example:

- a shipped demand lot may generate revenue
- an upstream supplier lot may generate supplier cost
- a node conversion event may generate node cost
- a cross-border event may generate tariff or landed cost
- a delayed lot may affect service level or lost-sales assumptions

Demand anchoring allows these financial effects to be traced back to the original market requirement.

## Canonical rules

### Rule 1: Market demand creates the lot

A WOM lot should normally originate from demand, not from arbitrary supply push.

Supply-push behavior may exist, but it should be represented explicitly through planning mode, plugin behavior, or scenario assumption.

### Rule 2: Lot identity should be preserved

Do not discard lot identity unless the aggregation is explicitly documented.

### Rule 3: Quantity aggregation is allowed, but explanation should remain possible

Dashboards may show totals.
The model should still preserve enough structure to diagnose why totals changed.

### Rule 4: CO should represent unmet or delayed demand

Carry-over should not be treated as a random balancing bucket.
It should be explainable as specific demand lots that were not fulfilled in the current week.

### Rule 5: Inventory should represent unused physical supply

Inventory should be explainable as lots that arrived or existed but were not consumed by demand in that week.

## Relationship to current implementation

The current WOM implementation already reflects this concept in several ways.

- Demand forecast data creates demand lots.
- Planning uses BackwardPlanner and ForwardPlanner.
- PlanNode stores demand-side and supply-side PSI.
- The tree structure connects `leaf_out`, `DAD`, `supply_point`, `MOM`, and `leaf_in`.
- Forward planning has evolved toward identity-based matching for lot feasibility.
- PPC can evaluate lot-level or event-level financial consequences.

Known implementation boundaries:

- Some GUI views may still show aggregated values rather than lot identities.
- Some exports may not yet expose actual shipment traces.
- Some KPI calculations may focus on `leaf_out` views.
- Some legacy comments or scenario notes may still reflect older pass-through assumptions.

These boundaries should be documented rather than hidden.

## Open questions

1. Should `actual_s` or equivalent actual-shipment traces become a formal exported data structure?

2. Should every lot have a stable canonical ID format across all scenarios?

3. How should lot identity be preserved when demand is aggregated, split, substituted, or reallocated?

4. How should lost sales be distinguished from backorder carry-over?

5. Should emergency procurement create new lot identities, or should it fulfill existing demand lot identities?

6. How should PPC reference lots:
   - directly by lot ID
   - indirectly by event ID
   - by aggregated product-node-week records

7. How much lot-level detail should be visible in the GUI versus kept in diagnostic exports?

## Maintenance rule

When modifying planning logic, verify whether demand lot identity is preserved.

When adding a new scenario, document how demand lots are generated and how lot identity should be interpreted.

When changing export or KPI behavior, consider whether lot traceability is improved or weakened.
