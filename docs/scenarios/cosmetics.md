# Cosmetics Scenario

## Purpose

This document describes the cosmetics WOM scenario.

The scenario is an educational model of a Japanese premium skincare brand selling into Singapore and Thailand.
It is useful for explaining launch and market-entry planning, factory capacity, smoothing, store stock,
shelf-life age, quantity allocation under shortage, and channel economics.

It is the model adopted in the BS-SEAF cosmetics verification (trial name M0).

## Educational disclaimer

This model is fictional and educational.

The brand, facilities, prices, costs, and capacities are assumptions, not values of any real company.
The money values exist to check that WOM carries money correctly. They are not accurate enough for business decisions.

## Model folder

```text
data/sample/cosmetics-sg-th-2027-2029/
```

The Japanese README in that folder lists every assumption. The CSV files in that folder are the source of truth.

## Business question

```text
When a store opens and a new market is added, is the Japanese factory's capacity enough?
If not, which demand should be supplied? Is the delivery age limit kept?
How much does each channel leave?
```

This folder is the baseline in which capacity is sufficient. Shortage and allocation cases are built from it (see Comparison cases).

## SKU structure

```text
COS_Serum
COS_Cream
```

1 lot = 1 case = 24 units. Demand and capacity are in lots. Prices and costs are per unit, excluding consumption tax.

## Physical network

```text
Materials_JP -> Factory_JP -> WH_JP_Released
  -> DC_SG -> SG_Store, SG_EC, SG_Distributor
  -> DC_TH -> TH_Distributor
```

- Japan HQ owns Factory_JP, WH_JP_Released, and DC_TH.
- The Singapore sales company owns DC_SG, SG_Store, and SG_EC.
- The supplier and the two distributors are external.

## Demand assumptions

Steady demand in lots per week:

| Channel | Start | COS_Serum | COS_Cream |
|---|---|---:|---:|
| SG_EC | 2027-W01 | 3 | 2 |
| SG_Distributor | 2027-W01 | 6 | 5 |
| SG_Store | 2027-W14 | 4 | 3 |
| TH_Distributor | 2028-W01 | 4 | 3 |

The first 13 weeks of each channel run at 50%. There is no seasonality.

## Capacity assumptions

Factory capacity is peak weekly demand / yield × 1.2, rounded up. Yield is 0.97.

| SKU | max_supply | cap_soft |
|---|---:|---:|
| COS_Serum | 22 | 18 |
| COS_Cream | 17 | 14 |

`demand_envelope=soft` at the factory: production is smoothed to cap_soft, and max_supply is the physical ceiling.
The holiday calendar is empty: all nodes run every week.

## Buffer and decoupling assumptions

- SG_Store has `ss_days=14`, so stock reaches the store before it opens and stays on the shelf.
- Warm-up is 17 weeks (`warmup_lt=17`). The plan starts at 2026-W37 and runs 173 weeks to 2029-W52. Reporting starts at 2027-W01.
- The decoupling optimizer is off for both SKUs.

## PPC assumptions

- FX is constant: SGD 115, THB 4.5, USD 150 yen.
- Thai tariff is 0% (assuming the EPA is used). The current rate has not been verified.
- Store operating cost is approximated as 35% of revenue.
- Yield loss is not in cost (cost is about 3% low).
- Japan HQ R&D and global brand cost are not included.
- All PPC rules are in the model folder. No shared rules are used.

The result is a PPC trial profit, after the costs in scope. It is not operating profit.

## Expected outputs

| Item | Value |
|---|---|
| Period | 2026-W37, 173 weeks |
| Flow Check | Demand of 4,056 lots fully met, on time. Backlog 0 |
| PPC | Valuation complete. Revenue 1,156,284,480 JPY, cost 524,434,872 JPY, trial profit 631,849,608 JPY |
| Delivery age | Maximum 6 weeks. None over 52 weeks |
| Value Chain | `vc_ppc_comparison.csv`, total profit before elimination, 2026-W37 to 2029-W52: PPC 631,849,608, ledger 935,061,504, difference 303,211,896 JPY (G1 + G2) |

The Value Chain figure reproduces a known difference. It does not show that entity or consolidated profit meets the business requirement.

## Execution

```bash
python -m tools.run_headless_from_folder --model-dir data/sample/cosmetics-sg-th-2027-2029
```

```bash
python -m tools.shelf_life_check --model-dir data/sample/cosmetics-sg-th-2027-2029 --max-age-weeks 52
```

```bash
python -m tools.valuechain_run --model-dir data/sample/cosmetics-sg-th-2027-2029 --out output/valuechain/cosmetics
```

GUI: run `python -m main`, load the folder, and run the Planning Engine.

## Comparison cases

These are not registered as sample models. Copy the model folder to a working folder and apply the change.
Do not change `data/sample/cosmetics-sg-th-2027-2029/`.

### C3a: capacity shortage

Set every row of `capacity_plan.csv` (warm-up rows included) to:

| SKU | max_supply | cap_soft |
|---|---:|---:|
| COS_Serum | 17 | 14 |
| COS_Cream | 13 | 11 |

Expected: backlog is 192 lots, all at TH_Distributor (COS_Serum 104, COS_Cream 88). Revenue 1,119,737,280 JPY, trial profit 607,601,448 JPY.

### P1, P2-a1, P2-a2: quantity allocation

Start from the C3a copy, then run:

```bash
python -m tools.run_quantity_allocation --model-dir <copy> --allocation-file <file> --out-dir output/planning_state --unallocated-note "Forecast demand out of supply scope for this period"
```

P2-a files:

```text
docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/allocation/allocation_qty_P2a1.csv
docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_appendix/allocation/allocation_qty_P2a2.csv
```

P1 file (the table in Appendix A of `docs/development/WOM_BSSEAF_Cosmetics_AllocationP0P1_Report.md`):

```text
sku_id,region,alloc_lots
COS_Cream,SG_Distributor,754
COS_Cream,SG_EC,299
COS_Cream,SG_Store,416
COS_Cream,TH_Distributor,211
COS_Serum,SG_Distributor,897
COS_Serum,SG_EC,455
COS_Serum,SG_Store,546
COS_Serum,TH_Distributor,286
```

Expected, in lots:

| Case | Original demand | In supply scope | Not in scope | Delivered | Backlog |
|---|---:|---:|---:|---:|---:|
| P1 | 4,056 | 3,864 | 192 | 3,860 | 4 |
| P2-a1 | 4,056 | 3,864 | 192 | 3,860 | 4 |
| P2-a2 | 4,056 | 3,864 | 192 | 3,856 | 8 |

The tool is a quantity path: its financial result is "not valued". The comparison values are in `docs/development/WOM_BSSEAF_Cosmetics_AllocationP2a_Report.md`.

### Adopted allocation plan: capacity-aware week rule, minimum supply 50% (Thai cream 70%)

This is the plan the Owner adopted for the cosmetics case (2026-11-02, 2026-11-03, and 2026-11-06 for the Thai cream). It is the baseline for later allocation work. It uses the upper Demand Plan (`docs/WOM_Start_Here.md` R23).

- Model: the C3a copy (capacity shortage, above).
- Quota: `docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_appendix/inputs/allocation_qty_TH70.csv` (P2-a2 with 25 cream lots moved from the SG distributor to the TH distributor: TH 299, SG 666). Two files named `allocation_qty_P2a2.csv` exist with the same numbers; the one in `docs/development/WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix/records/` has an extra `quota_source` column and is the one the later trials used.
- Week rule: `trim_to_capacity_latest` (trim each week's need down to capacity, from the latest week).
- Policy: `docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_appendix/inputs/udp_policy_MS50TH70.csv` (minimum supply 50% of original demand per distributor, product and request week, rounded up, required; Thai cream 70%, which equals its full demand at 2-3 lots a week). The earlier 50%-only plan used `docs/development/WOM_BSSEAF_Cosmetics_MinimumSupply_appendix/policy/udp_policy_MS50.csv` with the P2-a2 quota.

```bash
python -m tools.run_quantity_allocation --model-dir <C3a copy> --allocation-file <allocation_qty_TH70.csv> --week-rule trim_to_capacity_latest --policy-file <udp_policy_MS50TH70.csv> --udp-out <dir> --out-dir output/planning_state
```

Expected: original demand 4,056, in supply scope 3,864, not in scope 192, delivered on time 3,864, backlog 0; Thai cream delivered in full every week; no week below the minimum, at plan time or on actual delivery. SG cream cuts run 2029-W07 to W50. Comparison value 607,776,840 JPY (the 50%-only plan: 607,741,740). The meanings (minimum supply, its applicability when lots are coarse, conflict vs. error, exit codes) are in `docs/semantics/supply_allocation.md` §6.1 and Start Here R23. Evidence: `docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Report.md` and its independent check `docs/development/WOM_BSSEAF_Cosmetics_ThaiCream_Minimum70_Verify_Report.md`.

### M0t: Thai tariff 30%

In `ppc_tariff_rule.csv`, set `tariff_rate` to `0.30` on the two `WH_JP_Released->DC_TH` rows. Quantities do not change.

Expected: tariff 27,612,000 JPY, trial profit 604,237,608 JPY (27,612,000 lower).

## Known limitations

Planning:

- No holidays are set.
- Allocation is by SKU × channel lots. Without `--week-rule`, the tool spreads cuts over weeks in proportion to demand, and ties put the cut lots at the end of the horizon. Which weeks to cut can be chosen as a business rule with `--week-rule` (upper Demand Plan, Start Here R23); the adopted cosmetics plan uses `trim_to_capacity_latest`.
- Plan boundary effect: lots pushed back into the first plan week cannot be made, and the slack of the last 2 production weeks cannot be used.

Money:

- Yield loss is not in cost. Store cost is a revenue-rate approximation, which flatters profit when revenue falls. Japan HQ fixed cost is excluded.
- PPC taxes the transfer price, not CIF (G4).

Value Chain, business requirement not met:

- G1: revenue-based selling costs are not booked in the ledger.
- G2: MDF placed on external distributor nodes is not booked, and no issue is raised.
- G3: distributor revenue is booked at the DC ship week, which differs from the sell-in definition.
- G4: tariff base, as above.
- G5: CIF freight is borne by the receiver as inventory cost in the ledger.

Screens:

- The Management Tariff & FX panel stays empty, because `edge_cost_master.csv` has only its header.
- Management Inv Value, CCC, AR, and AP are 0, because `sku_master.csv` has no unit value or turnover days.
- The PPC Cost Waterfall GM (53.4%) is an average per lot, not the total 54.6%.

## Open questions

- The current Thai tariff rate and origin conditions are unverified.
- Yield cost awaits the yield Part B work.
- Whether fixed store cost should be modelled as a fixed cost.
