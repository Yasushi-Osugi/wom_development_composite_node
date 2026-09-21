"""
Inventory simulation engine.

Week-by-week simulation logic per SKU×Region:

  opening_inv     = prior week closing_inv  (week 0: on_hand from master)
  supply_receipt  = in-transit orders arriving this week
  gross_avail     = opening_inv + supply_receipt
  demand_fcst     = scenario-adjusted forecast
  demand_fulfilled= min(gross_avail, demand_fcst)
  stockout_qty    = max(0, demand_fcst - gross_avail)
  closing_inv     = gross_avail - demand_fulfilled
  safety_stock_qty= avg_demand * safety_stock_wks
  inv_cover_wks   = closing_inv / avg_demand  (weeks of cover remaining)
  reorder_qty     = replenishment order placed this week (arrives in lead_time weeks)
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from wom.config import WOMConfig
from wom.data.schema import Cols
from wom.engine.capacity import CapacityState

SKURegionKey = Tuple[str, str]


def _round_to_multiple(qty: float, multiple: float) -> float:
    """Round *qty* up to the nearest *multiple* (1.0 = no rounding)."""
    if multiple <= 0 or multiple == 1.0:
        return qty
    return math.ceil(qty / multiple) * multiple


class InventorySimulator:
    """
    Runs the week-by-week inventory simulation for a single scenario.

    Returns a 'simulation result' DataFrame with one row per
    SKU × Region × Week containing all planning KPIs.
    """

    def __init__(self, config: WOMConfig):
        self.config = config
        self._weeks = config.weeks
        self._n = config.num_weeks

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    def simulate(
        self,
        scenario_name: str,
        demand_arrays: Dict[SKURegionKey, np.ndarray],    # scenario-adjusted
        avg_demand: Dict[SKURegionKey, float],
        opening_inv: Dict[SKURegionKey, float],           # on_hand at start
        initial_on_order: Dict[SKURegionKey, Tuple[float, int]],  # (qty, arrival_wk_idx)
        sku_params: Dict[SKURegionKey, dict],             # SS wks, LT wks, order_mult, max_order
        capacity_state: CapacityState,
    ) -> pd.DataFrame:
        """
        Run simulation and return result DataFrame.

        Parameters
        ----------
        demand_arrays        : {(sku, region): np.ndarray[num_weeks]}
        avg_demand           : {(sku, region): float}  average weekly demand
        opening_inv          : {(sku, region): float}  on-hand at t=0
        initial_on_order     : {(sku, region): (qty, arrival_week_index)}
        sku_params           : {(sku, region): {ss_wks, lt_wks, order_mult, max_order_qty}}
        capacity_state       : mutable CapacityState for this scenario
        """
        rows: List[dict] = []

        for key, demand in demand_arrays.items():
            sku, region = key
            params = sku_params.get(key, {})

            ss_wks      = params.get("ss_wks", self.config.safety_stock_weeks)
            lt_wks      = params.get("lt_wks", self.config.lead_time_weeks)
            order_mult  = params.get("order_mult", self.config.order_multiple) or 1.0
            max_order   = params.get("max_order_qty", 0.0)

            avg_d       = avg_demand.get(key, 0.0)
            ss_qty      = avg_d * ss_wks

            # Pending orders: dict of {arrival_week_idx: qty}
            pending: Dict[int, float] = {}

            # Seed with existing on-order
            oo_info = initial_on_order.get(key)
            if oo_info:
                oo_qty, oo_arr_idx = oo_info
                if 0 <= oo_arr_idx < self._n:
                    pending[oo_arr_idx] = pending.get(oo_arr_idx, 0.0) + oo_qty

            inv = opening_inv.get(key, 0.0)

            for wk_idx, wk in enumerate(self._weeks):
                # ── Supply receipts ──────────────────────────────────
                receipt = pending.pop(wk_idx, 0.0)

                # ── Availability ─────────────────────────────────────
                gross = inv + receipt
                d     = demand[wk_idx]

                # ── Demand fulfilment ─────────────────────────────────
                fulfilled = min(gross, d)
                stockout  = max(0.0, d - gross)
                closing   = gross - fulfilled
                fill_rate = fulfilled / d if d > 0 else 1.0

                # ── Inventory cover ───────────────────────────────────
                cover_wks = (closing / avg_d) if avg_d > 0 else 999.0

                # ── Replenishment logic ───────────────────────────────
                # Project inventory at the receipt window (current closing +
                # already pending orders)
                arrival_idx = wk_idx + lt_wks
                pending_sum = sum(
                    v for k, v in pending.items()
                    if k <= arrival_idx
                )
                projected_at_arrival = closing + pending_sum

                # Reorder point = SS + demand during lead time
                reorder_point = ss_qty + avg_d * lt_wks

                order_qty = 0.0
                if projected_at_arrival < reorder_point and avg_d > 0:
                    # Order up to: SS + demand for one review period (1 week) + LT
                    order_up_to = ss_qty + avg_d * (lt_wks + 1)
                    raw_order = max(0.0, order_up_to - projected_at_arrival)
                    # Round to multiple
                    raw_order = _round_to_multiple(raw_order, order_mult)
                    # Cap at max_order_qty
                    if max_order > 0:
                        raw_order = min(raw_order, max_order)
                    # Cap at capacity
                    actual = capacity_state.consume(sku, region, wk_idx, raw_order)
                    order_qty = actual

                    if arrival_idx < self._n:
                        pending[arrival_idx] = pending.get(arrival_idx, 0.0) + order_qty

                # ── Record ────────────────────────────────────────────
                rows.append({
                    Cols.SCENARIO:          scenario_name,
                    Cols.SKU_ID:            sku,
                    Cols.REGION:            region,
                    Cols.WEEK:              wk,
                    Cols.OPENING_INV:       round(inv, 4),
                    Cols.SUPPLY_RECEIPT:    round(receipt, 4),
                    Cols.GROSS_AVAIL:       round(gross, 4),
                    Cols.DEMAND_FCST:       round(d, 4),
                    Cols.DEMAND_FULFILLED:  round(fulfilled, 4),
                    Cols.STOCKOUT_QTY:      round(stockout, 4),
                    Cols.CLOSING_INV:       round(closing, 4),
                    Cols.SAFETY_STOCK_QTY:  round(ss_qty, 4),
                    Cols.REORDER_QTY:       round(order_qty, 4),
                    Cols.FILL_RATE:         round(fill_rate, 4),
                    Cols.INV_COVER_WKS:     round(min(cover_wks, 999.0), 2),
                })

                inv = closing  # carry forward

        return pd.DataFrame(rows)
