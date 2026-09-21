"""
WOM Money PSI Evaluator  –  Management Layer (financial view)

Converts quantity PSI simulation output into money PSI:
  Revenue        = demand_fulfilled × selling_price
  COGS           = demand_fulfilled × unit_cost
  Gross Profit   = Revenue - COGS
  Gross Margin%  = Gross Profit / Revenue
  Inventory Value= closing_inv × unit_cost
  AR             = Revenue × (DSO_wks / horizon_wks)    (point-in-time proxy)
  AP             = COGS    × (DPO_wks / horizon_wks)
  DIO            = Inventory Value / (COGS / horizon_wks)
  CCC            = DSO_wks + DIO - DPO_wks              (in weeks)

Returns
-------
weekly_df   : DataFrame with one row per scenario × sku × region × week
summary_df  : DataFrame with one row per scenario × sku × region (totals + CCC)
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np

from wom.data.schema import Cols


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def evaluate_money(
    sim_df: pd.DataFrame,
    sku_master: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Parameters
    ----------
    sim_df      : Full simulation output (combined across scenarios).
                  Must contain Cols.SCENARIO, SKU_ID, REGION, WEEK,
                  DEMAND_FULFILLED, CLOSING_INV.
    sku_master  : SKU master with selling_price, unit_cost, dso_wks, dpo_wks.

    Returns
    -------
    (weekly_df, summary_df)
    """
    # ── Merge price/cost into simulation rows ──────────────────────
    price_cols = [Cols.SKU_ID, Cols.REGION,
                  Cols.SELLING_PRICE, Cols.UNIT_COST,
                  Cols.DSO_WKS, Cols.DPO_WKS]
    price_df = sku_master[price_cols].copy()

    merged = sim_df.merge(price_df, on=[Cols.SKU_ID, Cols.REGION], how="left")

    # Fill missing prices gracefully
    merged[Cols.SELLING_PRICE] = merged[Cols.SELLING_PRICE].fillna(0.0)
    merged[Cols.UNIT_COST]     = merged[Cols.UNIT_COST].fillna(0.0)
    merged[Cols.DSO_WKS]       = merged[Cols.DSO_WKS].fillna(6).astype(float)
    merged[Cols.DPO_WKS]       = merged[Cols.DPO_WKS].fillna(8).astype(float)

    # ── Weekly money columns ───────────────────────────────────────
    merged[Cols.REVENUE]       = merged[Cols.DEMAND_FULFILLED] * merged[Cols.SELLING_PRICE]
    merged[Cols.COGS]          = merged[Cols.DEMAND_FULFILLED] * merged[Cols.UNIT_COST]
    merged[Cols.GROSS_PROFIT]  = merged[Cols.REVENUE] - merged[Cols.COGS]
    merged[Cols.GROSS_MARGIN]  = np.where(
        merged[Cols.REVENUE] > 0,
        merged[Cols.GROSS_PROFIT] / merged[Cols.REVENUE],
        0.0,
    )
    merged[Cols.INV_VALUE_COST] = merged[Cols.CLOSING_INV] * merged[Cols.UNIT_COST]

    weekly_df = merged[[
        Cols.SCENARIO, Cols.SKU_ID, Cols.REGION, Cols.WEEK,
        Cols.DEMAND_FULFILLED, Cols.CLOSING_INV,
        Cols.SELLING_PRICE, Cols.UNIT_COST,
        Cols.REVENUE, Cols.COGS, Cols.GROSS_PROFIT, Cols.GROSS_MARGIN,
        Cols.INV_VALUE_COST, Cols.DSO_WKS, Cols.DPO_WKS,
    ]].copy()

    # ── Per-SKU×Region×Scenario summary + CCC ─────────────────────
    group_keys = [Cols.SCENARIO, Cols.SKU_ID, Cols.REGION]

    # Count non-zero weeks to use as horizon denominator per group
    horizon_wks = (
        sim_df.groupby(group_keys)[Cols.WEEK].count()
        .rename("horizon_wks")
        .reset_index()
    )

    agg = (
        weekly_df.groupby(group_keys)
        .agg(
            total_revenue   =(Cols.REVENUE,        "sum"),
            total_cogs      =(Cols.COGS,            "sum"),
            total_gp        =(Cols.GROSS_PROFIT,    "sum"),
            avg_margin      =(Cols.GROSS_MARGIN,    "mean"),
            avg_inv_value   =(Cols.INV_VALUE_COST,  "mean"),
            total_units     =(Cols.DEMAND_FULFILLED,"sum"),   # lot count, for Landed Cost engine
            dso_wks         =(Cols.DSO_WKS,         "first"),   # from price_df
            dpo_wks         =(Cols.DPO_WKS,         "first"),
        )
        .reset_index()
    )

    # Merge DSO/DPO from price_df (already in agg via "first")
    agg = agg.merge(horizon_wks, on=group_keys, how="left")
    agg["horizon_wks"] = agg["horizon_wks"].fillna(1)

    # DIO = avg_inv_value / (total_cogs / horizon_wks) in weeks
    weekly_cogs_rate = agg["total_cogs"] / agg["horizon_wks"]
    agg["dio_wks"] = np.where(
        weekly_cogs_rate > 0,
        agg["avg_inv_value"] / weekly_cogs_rate,
        0.0,
    )

    # CCC = DSO + DIO - DPO
    agg[Cols.CCC_WKS] = agg["dso_wks"] + agg["dio_wks"] - agg["dpo_wks"]

    # AR / AP (point-in-time balance proxy)
    agg[Cols.AR_VALUE] = agg["total_revenue"] * (agg["dso_wks"] / agg["horizon_wks"])
    agg[Cols.AP_VALUE] = agg["total_cogs"]    * (agg["dpo_wks"] / agg["horizon_wks"])

    # Rename totals to match Cols conventions
    summary_df = agg.rename(columns={
        "total_revenue": Cols.REVENUE,
        "total_cogs":    Cols.COGS,
        "total_gp":      Cols.GROSS_PROFIT,
        "avg_margin":    Cols.GROSS_MARGIN,
        "avg_inv_value": Cols.INV_VALUE_COST,
    })

    return weekly_df, summary_df


def build_scenario_money_kpi(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate money summary to scenario level (total across all SKUs/Regions).

    Returns one row per scenario with:
      revenue, cogs, gross_profit, gross_margin, ccc_wks, ar_value, ap_value
    """
    grp = summary_df.groupby(Cols.SCENARIO)
    out = grp.agg(
        revenue         =(Cols.REVENUE,        "sum"),
        cogs            =(Cols.COGS,           "sum"),
        gross_profit    =(Cols.GROSS_PROFIT,   "sum"),
        # NOTE: keyword must equal Cols.INV_VALUE_COST ("inv_value_cost") —
        # every consumer (app.py P&L table, management.py delta analysis)
        # looks this column up via that constant. It was previously named
        # "inv_value" here (a *different* constant, Cols.INV_VALUE), so Inv
        # Value silently always read back as 0.
        inv_value_cost  =(Cols.INV_VALUE_COST, "mean"),
        ar_value        =(Cols.AR_VALUE,       "sum"),
        ap_value        =(Cols.AP_VALUE,       "sum"),
        units           =("total_units",       "sum"),  # lot count, for Landed Cost engine
    ).reset_index()

    out[Cols.GROSS_MARGIN] = np.where(
        out["revenue"] > 0,
        out["gross_profit"] / out["revenue"],
        0.0,
    )

    # Weighted-average CCC across SKUs (weighted by revenue)
    ccc_weighted = (
        summary_df.assign(
            _rev_ccc=summary_df[Cols.REVENUE] * summary_df[Cols.CCC_WKS]
        )
        .groupby(Cols.SCENARIO)
        .agg(
            rev_sum   =(Cols.REVENUE, "sum"),
            rev_ccc   =("_rev_ccc",  "sum"),
        )
        .assign(ccc_wks=lambda x: np.where(x["rev_sum"] > 0,
                                            x["rev_ccc"] / x["rev_sum"], 0.0))
        .reset_index()[[Cols.SCENARIO, "ccc_wks"]]
    )

    out = out.merge(ccc_weighted, on=Cols.SCENARIO, how="left")
    return out
