"""
wom/plugins/buffering_stock_optimizer.py
──────────────────────────────────────────
BufferingStockOptimizerPlugin
  Hook: POST_BACKWARD

  Optional, opt-in plugin that replaces the manually-set OutBound
  `buffering_stock_flag` (is_decoupling) for a SKU with the cost-optimal
  placement found by wom/engine/decouple_optimizer.py.

  Why POST_BACKWARD (not PRE_PLAN)
  ---------------------------------
  decouple_optimizer.evaluate_decouple_placement() evaluates each
  candidate by resetting the supply layer and running one Forward
  Planning pass -- this requires psi4demand to already be fully
  populated. psi4demand is only complete after BackwardPlanner.run()
  (Planning Engine step 4), so this plugin must fire at POST_BACKWARD
  (step 5, before the official copy_demand_to_supply / step 6), not at
  PRE_PLAN (step 3, before BackwardPlanner has even run).

  CSV format (decouple_optimizer_config.csv, same directory as
  cap_override.csv / node_cost_master.csv):
    sku_id, enabled, max_shortfall_ratio
    Cookie_Import, 1, 1.10
    Cookie_Local,  0,

  - enabled: 1 to let this plugin override buffering_stock_flag for
    this SKU's OutBound lane; 0 (or missing row) leaves the SKU's
    manually-configured flags untouched (default, current behavior).
  - max_shortfall_ratio: optional per-SKU override of the service-level
    tolerance used by find_optimal_decouple_placement() (default 1.10
    if omitted -- see decouple_optimizer.py docstring for rationale).

  Effect when enabled for a SKU
  ------------------------------
  Every OutBound node (leaf_out / DAD / supply_point's direct children)
  for that SKU has `is_decoupling` reset to False, then set to True only
  on the winning candidate's node(s). The supply layer is left cleared
  (psi4supply[S/CO/I/P] = []) so the pipeline's official
  copy_demand_to_supply (which runs immediately after this hook) rebuilds
  it cleanly for the real Forward Planning pass.

  If decouple_optimizer_config.csv does not exist, or has no enabled row
  for this SKU, the plugin is a no-op and node_cost_master.csv-based
  manual buffering_stock_flag settings apply as before.
"""

from __future__ import annotations

import os
import pandas as pd

from wom.engine.plugin_base import WOMPlugin


class BufferingStockOptimizerPlugin(WOMPlugin):
    name        = "buffering_stock_optimizer"
    label       = "Buffering Stock Optimized Allocation"
    description = ("Reads decouple_optimizer_config.csv; when enabled for a "
                   "SKU, overrides that SKU's OutBound buffering_stock_flag "
                   "with the cost-optimal, service-level-constrained "
                   "placement found by decouple_optimizer.py.")

    CONFIG_FILENAME    = "decouple_optimizer_config.csv"
    NODE_COST_FILENAME = "node_cost_master.csv"

    def _resolve_sibling(self, config: dict, filename: str) -> str:
        cap_path: str = config.get("cap_path", "")
        base_dir = os.path.dirname(cap_path) if cap_path else os.path.join("data", "sample")
        return os.path.join(base_dir, filename)

    def on_post_backward(self, sc_tree, prod_nm: str,
                         weeks: list, config: dict, **kw) -> None:
        config_path = self._resolve_sibling(config, self.CONFIG_FILENAME)
        if not os.path.exists(config_path):
            return   # no config file -> plugin fully disabled, no-op

        try:
            cfg_df = pd.read_csv(config_path)
        except Exception as exc:
            print(f"[BufferingStockOptimizerPlugin] Could not read {config_path}: {exc}")
            return

        rows = cfg_df[cfg_df["sku_id"] == prod_nm]
        if rows.empty:
            return
        row = rows.iloc[0]
        if not bool(int(row.get("enabled", 0) or 0)):
            return

        max_shortfall_ratio = 1.10
        if "max_shortfall_ratio" in cfg_df.columns and pd.notna(row.get("max_shortfall_ratio")):
            try:
                max_shortfall_ratio = float(row["max_shortfall_ratio"])
            except (TypeError, ValueError):
                pass

        node_cost_master_path = self._resolve_sibling(config, self.NODE_COST_FILENAME)
        if not os.path.exists(node_cost_master_path):
            node_cost_master_path = None

        from wom.engine.decouple_optimizer import (
            find_optimal_decouple_placement, _reset_supply_layer,
        )

        result = find_optimal_decouple_placement(
            sc_tree, prod_nm,
            node_cost_master_path=node_cost_master_path,
            max_shortfall_ratio=max_shortfall_ratio,
        )
        best = result.get("best")
        if best is None:
            return

        winner_ids = set(best.decouple_node_ids)

        ot_root = sc_tree.get_ot_root(prod_nm)
        touched = []

        def _apply(node):
            was = node.is_decoupling
            node.is_decoupling = node.node_id in winner_ids
            if node.is_decoupling != was:
                touched.append((node.node_name, node.is_decoupling))
            for child in node.children:
                _apply(child)

        _apply(ot_root)

        # Leave the supply layer clean -- the pipeline's official
        # copy_demand_to_supply (step 6, runs right after this hook)
        # rebuilds psi4supply for the real Forward Planning pass.
        _reset_supply_layer_cleared_only(sc_tree, prod_nm, len(weeks))

        print(f"[BufferingStockOptimizerPlugin] {prod_nm}: "
              f"best={best.decouple_node_names} "
              f"inv_cost={best.total_inventory_cost:,.0f} "
              f"shortfall={best.total_shortfall_lots} "
              f"(candidates={result['candidates_evaluated']}, "
              f"min_shortfall={result['min_shortfall']}, "
              f"ratio={max_shortfall_ratio})")
        if touched:
            print(f"[BufferingStockOptimizerPlugin] {prod_nm}: flag changes -> {touched}")


def _reset_supply_layer_cleared_only(sc_tree, prod_nm: str, n_weeks: int) -> None:
    """
    Like decouple_optimizer._reset_supply_layer, but WITHOUT the
    re-copy_demand_to_supply step -- this plugin fires immediately
    before the pipeline's own official copy_demand_to_supply call, so
    re-populating here would be redundant (harmless, but wasteful).
    """
    from wom.model.plan_node import S, CO, I, P

    for node in sc_tree.iter_all_nodes(prod_nm):
        for w in range(n_weeks):
            node.psi4supply[w][S]  = []
            node.psi4supply[w][CO] = []
            node.psi4supply[w][I]  = []
            node.psi4supply[w][P]  = []
