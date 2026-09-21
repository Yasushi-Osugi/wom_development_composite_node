"""
Demand engine – processes raw demand forecasts and exposes
per-SKU×Region weekly demand arrays ready for simulation.

Capabilities
------------
* Fill missing weeks with zero demand or simple projection
* Apply scenario demand_multiplier
* Compute rolling averages for safety stock calculation
* Validate forecast coverage against planning horizon
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from wom.config import WOMConfig, ScenarioSpec
from wom.data.schema import Cols


# ──────────────────────────────────────────────────────────────────────
# Key type: (sku_id, region)
# ──────────────────────────────────────────────────────────────────────
SKURegionKey = Tuple[str, str]


class DemandEngine:
    """
    Prepares demand arrays for each SKU×Region×Scenario.

    Usage
    -----
    engine = DemandEngine(config)
    engine.load(demand_df, sku_master_df)
    demand = engine.get_demand("SKU-001", "APAC", "Upside")  # np.ndarray length=num_weeks
    """

    def __init__(self, config: WOMConfig):
        self.config = config
        self._base_demand: Dict[SKURegionKey, np.ndarray] = {}
        self._avg_weekly_demand: Dict[SKURegionKey, float] = {}
        self._weeks = config.weeks

    # ------------------------------------------------------------------ #

    def load(self, demand_df: pd.DataFrame, sku_master_df: pd.DataFrame) -> None:
        """
        Build base demand arrays from the forecast DataFrame.

        Parameters
        ----------
        demand_df    : from loader.load_demand_forecast()
        sku_master_df: from loader.load_sku_master()
        """
        weeks = self._weeks

        # Build a pivot: index=(sku_id, region), columns=week, values=quantity
        pivot = (
            demand_df
            .groupby([Cols.SKU_ID, Cols.REGION, Cols.WEEK])[Cols.DEMAND_QTY]
            .sum()
            .unstack(Cols.WEEK)
            .reindex(columns=weeks, fill_value=0.0)
            .fillna(0.0)
        )

        for (sku, region), row in pivot.iterrows():
            arr = row.values.astype(float)
            self._base_demand[(sku, region)] = arr
            non_zero = arr[arr > 0]
            self._avg_weekly_demand[(sku, region)] = (
                float(non_zero.mean()) if len(non_zero) > 0 else 0.0
            )

        # Ensure every active SKU×Region has an entry (even if zero)
        for _, r in sku_master_df.iterrows():
            key = (r[Cols.SKU_ID], r[Cols.REGION])
            if key not in self._base_demand:
                self._base_demand[key] = np.zeros(len(weeks))
                self._avg_weekly_demand[key] = 0.0

    # ------------------------------------------------------------------ #

    def get_demand(
        self,
        sku_id: str,
        region: str,
        scenario: ScenarioSpec,
    ) -> np.ndarray:
        """
        Return demand array (length = num_weeks) for a given scenario.
        Applies the scenario demand_multiplier.
        """
        base = self._base_demand.get((sku_id, region), np.zeros(len(self._weeks)))
        return base * scenario.demand_multiplier

    def avg_weekly_demand(self, sku_id: str, region: str) -> float:
        """Average weekly demand across non-zero forecast weeks."""
        return self._avg_weekly_demand.get((sku_id, region), 0.0)

    def keys(self) -> List[SKURegionKey]:
        """All (sku_id, region) pairs with demand data."""
        return list(self._base_demand.keys())

    def coverage_report(self) -> pd.DataFrame:
        """
        Return a DataFrame showing forecast coverage per SKU×Region.
        Useful for validating input data quality.
        """
        rows = []
        for (sku, region), arr in self._base_demand.items():
            covered = int(np.sum(arr > 0))
            rows.append({
                Cols.SKU_ID: sku,
                Cols.REGION: region,
                "weeks_with_demand": covered,
                "total_weeks": len(self._weeks),
                "total_demand": float(arr.sum()),
                "avg_weekly": float(arr[arr > 0].mean()) if covered > 0 else 0.0,
            })
        return pd.DataFrame(rows).sort_values([Cols.SKU_ID, Cols.REGION])
