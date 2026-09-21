# WOM Scenario Documents

This directory contains scenario-level documentation.

A WOM scenario is an executable supply chain hypothesis.
Scenario documents explain model assumptions, fictional disclaimers, physical network structure, demand, capacity, buffer behavior, PPC assumptions, expected outputs, and limitations.

## Documents

```text
japanese-rice.md
  Domestic seasonal food supply and household consumption.

smartphone.md
  Global electronics manufacturing and regional demand.

cookie.md
  Local versus import consumer packaged goods comparison.

ev.md
  Local/import EV supply chain, Tier-1 suppliers, tariff, FX, and landed cost.

oil-global-2027.md
  Global oil supply chain risk comparison across regions and route structures.
```

## Scenario documentation rule

Each scenario document should distinguish:

```text
model assumption
computed result
business interpretation
article narrative
open question
```

## Recommended scenario document structure

```text
Purpose
Educational disclaimer
Model folder
Business question
SKU structure
Physical network
Demand assumptions
Capacity assumptions
Buffer and decoupling assumptions
PPC assumptions
Expected outputs
Execution
Known limitations
Open questions
```

## Maintenance rule

When scenario CSV files are changed, update the corresponding scenario document.

When an article is published based on a scenario, check that the article narrative and scenario documentation remain consistent.
