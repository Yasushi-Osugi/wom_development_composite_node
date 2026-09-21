"""
Capacity engine – models supply availability and constrains replenishment orders.

Logic
-----
* Loads weekly max_supply per SKU×Region from the capacity plan.
* Tracks capacity consumed each week as orders are placed.
* When capacity_constrained=True, orders are capped at remaining capacity.
* Applies scenario supply_multiplier to all capacity figures.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from wom.config import WOMConfig, ScenarioSpec
from wom.data.schema import Cols

SKURegionKey = Tuple[str, str]


class CapacityEngine:
    """
    Per-scenario capacity tracker.

    Usage
    -----
    engine = CapacityEngine(config)
    engine.load(capacity_df)
    scenario_cap = engine.for_scenario(scenario_spec)  # returns CapacityState
    """

    def __init__(self, config: WOMConfig):
        self.config = config
        self._weeks = config.weeks
        # base capacity: key -> np.ndarray[num_weeks]
        self._base_capacity: Dict[SKURegionKey, np.ndarray] = {}

    def load(self, capacity_df: pd.DataFrame) -> None:
        """Build capacity arrays from the capacity plan DataFrame."""
        weeks = self._weeks
        pivot = (
            capacity_df
            .groupby([Cols.SKU_ID, Cols.REGION, Cols.WEEK])[Cols.MAX_SUPPLY]
            .sum()
            .unstack(Cols.WEEK)
            .reindex(columns=weeks, fill_value=0.0)
            .fillna(0.0)
        )
        for (sku, region), row in pivot.iterrows():
            self._base_capacity[(sku, region)] = row.values.astype(float)

    def for_scenario(self, scenario: ScenarioSpec) -> "CapacityState":
        """Return a mutable CapacityState for a single simulation run."""
        scaled = {
            key: arr * scenario.supply_multiplier
            for key, arr in self._base_capacity.items()
        }
        return CapacityState(self.config, scaled)

    def available_capacity(
        self, sku_id: str, region: str, week_idx: int, scenario: ScenarioSpec
    ) -> float:
        """
        Raw capacity for a single week (before any consumption).
        Returns float('inf') if unconstrained or key not found.
        """
        if not self.config.capacity_constrained:
            return float("inf")
        key = (sku_id, region)
        arr = self._base_capacity.get(key)
        if arr is None:
            return float("inf")
        return max(0.0, arr[week_idx] * scenario.supply_multiplier)


class CapacityState:
    """
    Mutable capacity state for ONE simulation run (one scenario).
    Tracks consumed capacity so the simulator can enforce limits week-by-week.
    """

    def __init__(
        self,
        config: WOMConfig,
        capacity_arrays: Dict[SKURegionKey, np.ndarray],
    ):
        self.config = config
        self._capacity = capacity_arrays          # max supply per week
        self._consumed: Dict[SKURegionKey, np.ndarray] = {
            key: np.zeros(len(config.weeks))
            for key in capacity_arrays
        }

    def available(self, sku_id: str, region: str, week_idx: int) -> float:
        """Remaining capacity in a given week after prior consumption."""
        if not self.config.capacity_constrained:
            return float("inf")
        key = (sku_id, region)
        if key not in self._capacity:
            return float("inf")                  # no cap defined → unlimited
        return max(0.0, self._capacity[key][week_idx] - self._consumed[key][week_idx])

    def consume(self, sku_id: str, region: str, week_idx: int, qty: float) -> float:
        """
        Record consumption of *qty* units of capacity in *week_idx*.
        Returns the actual quantity consumed (capped at available).
        """
        avail = self.available(sku_id, region, week_idx)
        actual = min(qty, avail)
        key = (sku_id, region)
        if key in self._consumed:
            self._consumed[key][week_idx] += actual
        return actual

    def utilisation_report(self) -> pd.DataFrame:
        """DataFrame of capacity utilisation for all SKU×Region×Week."""
        weeks = self.config.weeks
        rows = []
        for key in self._capacity:
            sku, region = key
            cap_arr  = self._capacity[key]
            used_arr = self._consumed.get(key, np.zeros(len(weeks)))
            for i, wk in enumerate(weeks):
                cap  = cap_arr[i]
                used = used_arr[i]
                rows.append({
                    Cols.SKU_ID: sku,
                    Cols.REGION: region,
                    Cols.WEEK: wk,
                    Cols.CAPACITY_AVAIL: cap,
                    Cols.CAPACITY_USED: used,
                    "utilisation_pct": (used / cap * 100) if cap > 0 else 0.0,
                })
        return pd.DataFrame(rows)
