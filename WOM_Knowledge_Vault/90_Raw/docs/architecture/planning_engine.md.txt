# Planning Engine

## Purpose

Describe the current planning behavior visible in implementation: DataFrame simulation, SCTree/lot-based planning, backward and forward passes, push/pull switching, capacity handling, and GUI orchestration.

## Source basis

This document is implementation-derived from current Python source. It avoids design intent unless the behavior is directly visible in code comments, docstrings, or executed control flow.

## Key files inspected

- wom/engine/simulator.py
- wom/engine/demand.py
- wom/engine/capacity.py
- wom/engine/inventory.py
- wom/engine/backward_planner.py
- wom/engine/forward_planner.py
- wom/engine/push_pull.py
- wom/engine/plan_copy.py
- wom/engine/sc_tree_builder.py
- wom/engine/capacity_sealer.py
- wom/engine/lane_assignment.py
- wom/model/plan_node.py
- wom/model/sc_tree.py
- wom/model/lot_generator.py
- wom/gui/app.py
- wom/engine/sc_tree_to_df.py
- tests/test_step7_capacity.py
- tests/test_step8_push_pull.py
- tests/test_step10_hooks.py

## Observed current behavior

There are two implementation-visible planning paths.

The DataFrame-style path is used by `main.py --cli` and parts of the GUI simulation workflow. It loads `sku_master`, `demand_forecast`, `inventory_master`, and `capacity_plan` into `WOMInputs`. `WOMSimulator` prepares demand arrays, capacity state, SKU parameters, opening inventory, and initial on-order quantities. For each configured scenario, it runs `InventorySimulator`, adds inventory value, stores results in `ScenarioManager`, then evaluates money PSI and management analysis.

`DemandEngine` groups demand by `(sku_id, region, week)`, fills the configured week horizon, and applies each scenario's `demand_multiplier`. `CapacityEngine` groups weekly `max_supply`, applies the scenario `supply_multiplier`, and returns mutable `CapacityState` instances. `InventorySimulator` runs week by week with opening inventory, supply receipts, fulfilled demand, stockout, closing inventory, safety stock, inventory cover, reorder quantity, lead-time arrival scheduling, order-multiple rounding, max-order capping, and capacity consumption.

The SCTree/lot-based path uses `PlanNode` and `SCTree`. `PlanNode` stores weekly `psi4demand` and `psi4supply` buckets indexed as `S`, `CO`, `I`, and `P`, plus hard/soft capacity. `SCTree` holds OutBound and InBound tree roots per product, supports multiple inbound MOM roots, and provides bridge methods between the OutBound supply point and InBound MOM.

`sc_tree_builder.py` builds arbitrary-depth supply chain trees from `sc_tree_master.csv`. Required columns include `node_name`, `parent_node`, `product_name`, `node_type`, `side`, and `lt_wks`; optional columns include `cpu_size`, `ss_days`, `region`, `transit_lt_wks`, and `buffering_stock_flag`. If no `sc_tree_master` is supplied, code paths in the repository can fall back to demo two-tier tree building.

`lot_generator.py` converts demand quantities into lot IDs and assigns them to leaf-out `psi4demand[week][S]`. Lot IDs use the visible format `{sku_id}:{region}:{week}:{seq}`.

`BackwardPlanner` runs demand propagation. Its visible phases are:

- OutBound postorder propagation from leaf-out through DAD nodes to the supply point.
- Bridge from supply point to one or more MOM nodes, using `LaneTable` when lane assignment is available.
- Optional MOM constrained allocation when `mom_constrained` is true.
- InBound preorder propagation from MOM toward supplier/leaf-in nodes.

Backward planning records past-due lots when lead-time offsets fall before the planning horizon. It also reads `explicit_closures` from config, which the holiday calendar plugin can write, to skip closed weeks during lead-time offset calculation.

`copy_demand_to_supply()` is the visible transition between backward and forward planning, copying demand-side PSI into supply-side PSI before the forward pass.

`PushProductionPlanner` modifies supply-side planning between copy and forward pass. It sets plan modes for push/pull behavior and can generate push production schedules using fixed quantity, replenishment-to-buffer, time-phased pre-build, or lead-time-shifted demand modes. The GUI reads `push_config.csv` and applies matching rows per SKU before `ForwardPlanner.run()`.

`ForwardPlanner` is invoked after copy and optional push setup. It propagates supply from InBound through the bridge and OutBound side, and the surrounding docs/comments indicate that CO is generated in forward planning when demand cannot be fulfilled.

`capacity_sealer.py` applies capacity profiles to `PlanNode` instances and can build capacity-load reports after forward planning. `capacity_override.py` can override MOM capacity before planning. `holiday_calendar_plugin.py` can set supply closures and demand multipliers. `buffering_stock_optimizer.py` can replace manual OutBound decoupling flags after backward planning.

The GUI Planning Engine path in `wom/gui/app.py` visibly orchestrates:

1. Build planning context, including `sc_tree`, `weeks`, `HookBus`, config, lane table, and optional opening inventory.
2. Fire `HOOK_PRE_PLAN`.
3. For each product, run `BackwardPlanner`.
4. Fire `HOOK_POST_BACKWARD`.
5. Copy demand to supply.
6. Fire `HOOK_POST_COPY`.
7. Apply `push_config.csv` if configured.
8. Run `ForwardPlanner`.
9. Fire `HOOK_POST_FORWARD`.
10. Fire `HOOK_POST_PLAN`.
11. Convert `SCTree` to a planning DataFrame, merge it into `ScenarioManager`, recompute money/management/strategic KPI outputs, update GUI panels, and trigger PPC from PSI.

## Important assumptions

- The DataFrame simulator and SCTree planner are both documented because both are active in current source.
- The exact internals of `ForwardPlanner` were partially truncated in shell output, so only behavior visible from adjacent source, docstrings, invocation order, and referenced tests is summarized.
- Scenario CSV rows were not read in detail; CSV schema facts are taken from loader/builder code and file names.

## Open questions

- Which planning path is the canonical "Planning Engine" for v1r1m5 documentation and future code changes?
- Should `ForwardPlanner` behavior be documented in more detail after a targeted source pass with line-level excerpts?
- Should capacity handling be unified between DataFrame `CapacityEngine` and SCTree `capacity_sealer`/node capacity behavior?
- Is demo-tree fallback intended for production use, or only for development and examples?
