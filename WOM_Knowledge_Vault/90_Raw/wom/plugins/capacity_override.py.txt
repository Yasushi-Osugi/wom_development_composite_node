"""
wom/plugins/capacity_override.py
──────────────────────────────────
CapacityOverridePlugin
  Hook: PRE_PLAN

  Reads an optional "cap_override.csv" from the same directory as
  capacity_plan.csv and applies per-SKU/week cap_hard / cap_soft overrides
  BEFORE the planning loop starts.

  CSV format (all columns optional except sku_id + week):
    sku_id, week, cap_hard, cap_soft

  Use case: quick what-if adjustments to capacity limits without editing
  the base capacity_plan.csv (e.g. "what if we add a shift in W20?").

  If cap_override.csv does not exist the plugin is silently skipped.
"""

from __future__ import annotations
import os
import pandas as pd
from wom.engine.plugin_base import WOMPlugin


class CapacityOverridePlugin(WOMPlugin):
    name        = "capacity_override"
    label       = "Capacity Override (cap_override.csv)"
    description = ("Reads data/sample/cap_override.csv and applies "
                   "per-SKU/week CapHard/CapSoft overrides before planning.")

    # Path is resolved relative to capacity_plan.csv dir, or data/sample/
    OVERRIDE_FILENAME = "cap_override.csv"

    def on_pre_plan(self, sc_tree, weeks: list, config: dict, **kw) -> None:
        """Apply cap_hard / cap_soft overrides from cap_override.csv."""
        cap_path: str = config.get("cap_path", "")
        if cap_path:
            override_path = os.path.join(
                os.path.dirname(cap_path), self.OVERRIDE_FILENAME)
        else:
            override_path = os.path.join(
                "data", "sample", self.OVERRIDE_FILENAME)

        if not os.path.exists(override_path):
            return   # no override file → skip silently

        try:
            df = pd.read_csv(override_path)
        except Exception as exc:
            print(f"[CapacityOverridePlugin] Could not read {override_path}: {exc}")
            return

        week_idx_map = {wk: i for i, wk in enumerate(weeks)}

        for _, row in df.iterrows():
            sku_id = str(row.get("sku_id", ""))
            week   = str(row.get("week", ""))
            w_idx  = week_idx_map.get(week)
            if not sku_id or w_idx is None:
                continue
            try:
                mom = sc_tree.get_in_root(sku_id)
            except Exception:
                continue

            kw_cap: dict = {}
            if "cap_hard" in df.columns and pd.notna(row["cap_hard"]):
                kw_cap["cap_hard"] = float(row["cap_hard"])
            if "cap_soft" in df.columns and pd.notna(row["cap_soft"]):
                kw_cap["cap_soft"] = float(row["cap_soft"])
            if kw_cap:
                mom.set_capacity(w_idx, **kw_cap)
                print(f"[CapacityOverridePlugin] {sku_id} {week} → {kw_cap}")
