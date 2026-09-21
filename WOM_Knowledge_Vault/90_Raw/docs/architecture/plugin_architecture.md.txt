# Plugin Architecture

## Purpose

Document the current plugin and hook mechanisms visible in the WOM implementation, including hook points, plugin registration shape, built-in plugins, and GUI planning integration.

## Source basis

This document is implementation-derived from plugin base classes, hook bus code, built-in plugin modules, GUI orchestration, and tests named for hook behavior.

## Key files inspected

- wom/engine/plugin_base.py
- wom/engine/hook_bus.py
- wom/engine/holiday_calendar_plugin.py
- wom/plugins/capacity_override.py
- wom/plugins/demand_smoothing.py
- wom/plugins/buffering_stock_optimizer.py
- wom/engine/decouple_optimizer.py
- wom/gui/app.py
- tests/test_step10_hooks.py
- tests/test_buffering_stock_optimizer_plugin.py

## Observed current behavior

`WOMPlugin` is the base class for planning plugins. It defines metadata fields `name`, `label`, and `description`, and no-op hook methods that subclasses override as needed.

The visible hook methods are:

- `on_pre_plan(sc_tree, weeks, config, **kw)`
- `on_post_backward(sc_tree, prod_nm, weeks, config, **kw)`
- `on_post_copy(sc_tree, prod_nm, weeks, config, **kw)`
- `on_post_forward(sc_tree, prod_nm, weeks, config, **kw)`
- `on_post_plan(sc_tree, weeks, config, **kw)`

`WOMPlugin.register(bus)` registers all five methods with a `HookBus`. Because default methods are no-ops, subclasses can override only the hook methods they need.

`HookBus` is a lightweight publish-subscribe mechanism with named hook constants:

- `HOOK_PRE_PLAN`
- `HOOK_POST_BACKWARD`
- `HOOK_POST_COPY`
- `HOOK_POST_FORWARD`
- `HOOK_POST_PLAN`

`HookBus.fire()` calls registered listeners with keyword context and catches exceptions, printing a traceback rather than stopping the pipeline.

The GUI Planning Engine path fires hooks in a fixed order:

1. `HOOK_PRE_PLAN` once after planning context is built.
2. For each product:
   - `HOOK_POST_BACKWARD` after `BackwardPlanner.run(prod_nm)`.
   - `HOOK_POST_COPY` after `copy_demand_to_supply(sc_tree, prod_nm)`.
   - `HOOK_POST_FORWARD` after `ForwardPlanner.run(prod_nm)`.
3. `HOOK_POST_PLAN` once after all products are planned.

`HolidayCalendarPlugin` is implemented under `wom/engine`, not `wom/plugins`. On `on_pre_plan`, it loads a holiday CSV, applies supply closures and demand multipliers, and writes `config["explicit_closures"]` so `BackwardPlanner` can skip closed weeks during lead-time offset calculation. On `on_post_backward`, it moves leaf-in P lots away from explicitly closed weeks to open weeks when possible.

`CapacityOverridePlugin` reads an optional `cap_override.csv` next to the capacity plan path, or under `data/sample` if no capacity path is set. On `on_pre_plan`, it applies per-SKU/week `cap_hard` and `cap_soft` overrides to MOM nodes.

`DemandSmoothingPlugin` runs on `on_post_backward`. It reads MOM `psi4demand[w][S]` lot counts, computes a 3-week moving average, pools lots across the horizon, and reassigns them to weeks according to smoothed target quantities.

`BufferingStockOptimizerPlugin` runs on `on_post_backward`. If `decouple_optimizer_config.csv` exists and enables the current SKU, it calls `find_optimal_decouple_placement()`, updates OutBound `is_decoupling` flags to the winning candidate, clears supply-side PSI buckets, and relies on the main pipeline's subsequent copy step to rebuild supply state.

`decouple_optimizer.py` evaluates OutBound decoupling candidates by resetting the supply layer, copying demand to supply, running `ForwardPlanner` for each candidate, and comparing inventory lots/cost against shortfall constraints.

## Important assumptions

- GUI plugin registration details were inferred from the visible planning hook firing and plugin class implementations; a complete GUI widget/plugin registry pass was not performed.
- This document treats plugin modules under both `wom/engine` and `wom/plugins` as part of the current plugin architecture because they use `WOMPlugin` and `HookBus`.
- Hook exception handling is described as observed in `HookBus.fire()`: exceptions are printed and the loop continues.

## Open questions

- Where is the canonical list of default GUI-enabled plugins maintained?
- Should built-in plugins live consistently under `wom/plugins`, or is `wom/engine/holiday_calendar_plugin.py` intentionally separate?
- Should plugin failures remain non-fatal, or should some hook failures stop planning?
- Should plugin metadata include configuration schema so GUI controls and docs can be generated consistently?
