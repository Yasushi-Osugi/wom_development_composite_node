# Oil Global 2027 Scenario

## Purpose

This document describes the WOM Global Oil Supply Chain scenario.

The scenario is an educational model for comparing supply chain resilience across multiple markets and sourcing structures.
It focuses on geopolitical risk, labor disruption, natural disaster, long-distance import buffering, crack spread compression, and external strategic supply-management scenarios.

## Educational disclaimer

This model is fictional and educational.

Company names, product names, locations, prices, capacities, routes, and strategic behaviors are simplified or fictionalized.
The scenario should not be interpreted as a factual statement about actual OPEC+ members, oil majors, producing countries, refineries, ports, or energy-market strategies.

## Model folder

Recommended model folder:

```text
data/sample/oil-global-2027/
```

Planning horizon:

```text
2027-W01 to 2028-W26
78 weeks
```

## Business question

The scenario explores the following question:

```text
How do different sourcing structures and disruption types affect weekly supply feasibility,
buffer behavior, margin compression, landed cost, and management KPI?
```

The scenario compares:

- Japan
- Europe
- Americas

It also compares:

- local refining
- cross-border import
- normal route
- emergency alternative route
- external supply-management overlay

## SKU structure

The scenario uses three market regions and Local/Import structures.

Conceptual SKU groups:

```text
Japan:
- Gasoline_Local
- Gasoline_Import
- Gasoline_Local_Hormuz
- Gasoline_Local_RedSea

Europe:
- Gasoline_EU_Local
- Gasoline_EU_Import

Americas:
- Gasoline_US_Local
- Gasoline_US_Import
```

The exact SKU names should be verified against `sku_master.csv`.

## Physical network

### Japan local route

Conceptual structure:

```text
Inbound:
Crude_ME -> Refinery_Local -> SP_Oil_Local

Outbound:
SP_Oil_Local -> Tank_Local -> Retail_Local_KANTO
                           -> Retail_Local_KANSAI
                           -> Retail_Local_CHUBU
```

Interpretation:

- `Crude_ME` represents Middle East crude supply.
- `Refinery_Local` represents a fictional local refinery.
- `Tank_Local` represents local tank storage.
- retail nodes represent demand channels.

### Japan import route

Conceptual structure:

```text
Inbound:
Refinery_SG -> Import_Hub -> SP_Oil_Import

Outbound:
SP_Oil_Import -> Tank_Import -> Retail_Import_*
```

Interpretation:

- import route has longer lead time.
- `Tank_Import` is a decoupling point with larger safety stock.
- the import buffer represents time purchased in advance.

### Emergency route comparison

The scenario may represent route-switching comparison by defining alternative route SKUs.

Conceptual comparison:

```text
Normal route:
Hormuz route

Emergency route:
Red Sea alternative route
```

The route comparison is expressed as scenario data rather than by changing the canonical engine.

## Demand assumptions

Demand is defined weekly by product, region or channel, and week.

The scenario may include:

- normal weekly demand
- route-specific demand switching
- delayed demand destruction after price shock
- seasonal demand recovery

Demand destruction should be documented as an external economic scenario assumption rather than as a hidden Planning Engine behavior.

## Capacity assumptions

Capacity is used to model:

- refinery capacity
- pipeline or emergency route capacity
- temporary reduction
- strategic supply restriction
- natural disaster or labor-disruption effects

Examples of modeled shock types:

```text
geopolitical disruption
labor strike
hurricane or natural disaster
coordinated supply reduction
non-OPEC swing supply
```

Capacity changes should be visible in `capacity_plan.csv`, `holiday_calendar.csv`, `cap_override.csv`, or scenario generator output.

## Buffer and decoupling assumptions

The scenario emphasizes tank storage and import buffering.

Typical interpretation:

```text
longer transport lead time -> larger buffer requirement
```

Local storage may have shorter safety stock.
Import storage may have larger safety stock and explicit decoupling behavior.

A key model message is:

```text
Buffer stock is time purchased in advance.
```

## PPC assumptions

The scenario uses PPC to evaluate:

- crude or supplier cost
- refinery or node cost
- market price
- FX
- crack spread compression
- margin behavior
- landed cost
- node-level P&L
- strategic KPI

The scenario deliberately separates physical flow from financial assumptions.

Example financial behavior:

```text
supplier cost rises
market price remains sticky
margin compresses
```

This should be implemented through PPC rule files and scenario inputs, not by altering physical PSI logic.

## Scenario shocks

### Crack spread compression

A crude price spike and FX movement can raise input cost while retail price remains sticky.

Expected interpretation:

```text
input cost floor rises faster than market price
refinery margin compresses
margin may not return to the original level after the shock
```

### Long-distance import buffer

A long import lead time requires larger tank inventory.

Expected interpretation:

```text
Tank_Import inventory remains non-zero for most of the horizon
```

### Hormuz versus Red Sea route comparison

A normal route may be phased down after disruption.
An emergency route may start later or have lower capacity.

Expected interpretation:

```text
alternative route may reduce the shock but cannot fully restore normal supply if its capacity is lower
```

### Regional shock comparison

Different markets may face different shock patterns:

- acute short natural disaster
- medium labor disruption
- long geopolitical closure

The scenario should compare both shock depth and shock duration.

### External strategic supply-management overlay

The OPEC-like scenario should be modeled outside the canonical engine.

Recommended pattern:

```text
external scenario generator or plugin
  -> modifies demand, capacity, price, or cost inputs
  -> WOM runs canonical PSI planning
  -> PPC evaluates financial impact
```

## Expected outputs

Users should inspect:

- World Map SKU filter
- Network tree
- weekly PSI charts
- tank inventory
- CO or service-level behavior
- PPC event ledger
- Node P&L
- Management KPI
- Landed Cost / Tariff & FX panel if available

Expected observations:

- import route has more buffer inventory
- route disruption creates visible supply gap
- sticky retail price compresses margin
- alternative route capacity limits recovery
- regional supply structures produce different resilience

## Execution

Typical GUI execution:

```text
python -m main
```

Typical CLI execution:

```text
python -m main --cli --start-week 2027-W01 --num-weeks 78
```

In GUI:

```text
1. Select oil-global-2027
2. Run Planning Engine
3. Use SKU filter in World Map and other panels
4. Inspect Network, Charts, Management, and PPC tabs
```

## Known limitations

- The scenario is educational and fictional.
- Some economic feedback loops are represented as external scenario assumptions.
- Some true market mechanisms, such as endogenous price formation, are not part of the canonical engine.
- If actual shipment traces are internal only, some shortage effects may require diagnostic export or future GUI enhancement.
- The distinction between `cap_hard = 0.0` as "unspecified" versus "intentional full closure" remains an open design issue.
- Route-switching may be represented by SKU switching rather than dynamic in-engine rerouting.

## Open questions

1. Should route-switching become a standard plugin pattern?

2. Should external supply-management overlays be formalized under a scenario generator framework?

3. Should actual shipment traces be exported for oil shock diagnosis?

4. Should strategic reserve behavior be represented as a special buffer type?

5. Should price elasticity and demand destruction become a standard economic plugin?

6. Should oil route names remain route-level SKU names, or should dynamic route assignment be introduced?

7. Should this scenario include China, India, Africa, and other global markets in a future expansion?

## Maintenance rule

When changing the oil scenario, update this document with:

- changed SKU names
- changed node structure
- changed shock timing
- changed financial assumptions
- changed reproducibility commands
- changed known limitations
