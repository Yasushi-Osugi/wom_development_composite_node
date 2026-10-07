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

        # RequestLetter_CapacityZeroBlank: the same value rule as
        # capacity_plan.csv -- blank = this column is not overridden, 0 = zero
        # capacity, > 0 = the ceiling, negative / not a number = stop. A row
        # for a product that is not in the plan tree stops too; rows outside
        # the horizon are skipped with a warning.
        from wom.engine.capacity_sealer import (
            parse_capacity_value, _raise_not_found, _warn_out_of_range)
        src = os.path.basename(override_path)
        week_idx_map = {wk: i for i, wk in enumerate(weeks)}
        rows, missing, out_of_range = [], [], 0
        for i, row in enumerate(df.to_dict("records")):
            line = i + 2
            sku_id = str(row.get("sku_id", "") or "")
            week   = str(row.get("week", "") or "")
            kw_cap: dict = {}
            for col in ("cap_hard", "cap_soft"):
                if col in df.columns:
                    v = parse_capacity_value(row.get(col), source=src, line=line, column=col)
                    if v is not None:
                        kw_cap[col] = v
            try:
                mom = sc_tree.get_in_root(sku_id)
            except Exception:
                missing.append((line, sku_id, "(InBound root)"))
                continue
            w_idx = week_idx_map.get(week)
            if w_idx is None:
                out_of_range += 1
                continue
            rows.append((mom, w_idx, sku_id, week, kw_cap))
        if missing:
            _raise_not_found(src, missing, "製品")
        _warn_out_of_range(src, out_of_range)

        for mom, w_idx, sku_id, week, kw_cap in rows:
            if kw_cap:
                mom.set_capacity(w_idx, **kw_cap)
                print(f"[CapacityOverridePlugin] {sku_id} {week} → {kw_cap}")
