"""
wom/ppc/ppc_kpi.py
==================
Step 7: KPI Summary in base currency.

Builds three summary DataFrames + one KPI dict:
    1. node_week_summary     - Revenue / Cost / Profit per (node, week)
    2. profit_zone_summary   - Revenue / Cost / Profit per profit_zone_role
    3. kpi_summary (dict)    - Top-level KPIs for Management Cockpit

All amounts are in base currency.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .ppc_models import LotCostAccumulator, PPCEvent, PPCTrustEvent


# Cost event types for aggregation
COST_EVENT_TYPES = {
    "supplier_cost",
    "conversion_cost",
    "logistics_cost",
    "insurance_cost",
    "tariff_cost",
    "warehouse_cost",
    "sga_cost",
    "marketing_cost",
    "hq_royalty",
}

REVENUE_EVENT_TYPES = {"market_revenue"}


def build_node_week_summary(events: List[PPCEvent]) -> pd.DataFrame:
    """
    Aggregate PPCEvents by (node_id, week).

    Columns: node_id, week, revenue_base, cost_base, gross_profit_base,
             tariff_base, landed_cost_base

    Note: ev.amount_base is a PER-UNIT amount (per_lot/per-unit master rate
    converted to base currency); ev.qty carries the real physical quantity
    represented by the underlying aggregated weekly PSI record (see
    ppc_psi_bridge.psi_to_sales_records / ppc_engine._build_accumulators).
    Multiplying by ev.qty here converts per-unit amounts into true totals.
    """
    rows = []
    for ev in events:
        if ev.ppc_event_type in ("transfer_price_set", "backward_allowable", "landed_cost_total"):
            continue
        rows.append({
            "node_id":     ev.node_id,
            "week":        ev.week,
            "product_id":  ev.product_id,
            "profit_zone": ev.profit_zone,
            "is_revenue":  ev.ppc_event_type in REVENUE_EVENT_TYPES,
            "is_cost":     ev.ppc_event_type in COST_EVENT_TYPES,
            "is_tariff":   ev.ppc_event_type == "tariff_cost",
            "amount_base": ev.amount_base * (ev.qty or 1),
        })
    if not rows:
        return pd.DataFrame(columns=[
            "node_id", "week", "product_id",
            "revenue_base", "cost_base", "gross_profit_base", "tariff_base"
        ])
    df = pd.DataFrame(rows)
    agg = (
        df.groupby(["node_id", "week", "product_id"])
        .apply(lambda g: pd.Series({
            "revenue_base":      g.loc[g["is_revenue"],  "amount_base"].sum(),
            "cost_base":         g.loc[g["is_cost"],     "amount_base"].sum(),
            "tariff_base":       g.loc[g["is_tariff"],   "amount_base"].sum(),
        }), include_groups=False)
        .reset_index()
    )
    agg["gross_profit_base"] = agg["revenue_base"] - agg["cost_base"]
    return agg


def build_profit_zone_summary(events: List[PPCEvent]) -> pd.DataFrame:
    """
    Aggregate by profit_zone_role.

    Columns: profit_zone, revenue_base, cost_base, gross_profit_base,
             tariff_base, gross_margin_pct
    """
    rows = []
    for ev in events:
        if ev.ppc_event_type in ("transfer_price_set", "backward_allowable", "landed_cost_total"):
            continue
        rows.append({
            "profit_zone": ev.profit_zone,
            "is_revenue":  ev.ppc_event_type in REVENUE_EVENT_TYPES,
            "is_cost":     ev.ppc_event_type in COST_EVENT_TYPES,
            "is_tariff":   ev.ppc_event_type == "tariff_cost",
            "is_mom_profit": ev.ppc_event_type == "mom_profit",
            "amount_base": ev.amount_base * (ev.qty or 1),
        })
    if not rows:
        return pd.DataFrame(columns=[
            "profit_zone", "revenue_base", "cost_base",
            "gross_profit_base", "tariff_base", "gross_margin_pct"
        ])
    df = pd.DataFrame(rows)
    agg = (
        df.groupby("profit_zone")
        .apply(lambda g: pd.Series({
            "revenue_base":    g.loc[g["is_revenue"],    "amount_base"].sum(),
            "cost_base":       g.loc[g["is_cost"],       "amount_base"].sum(),
            "tariff_base":     g.loc[g["is_tariff"],     "amount_base"].sum(),
            "mom_profit_base": g.loc[g["is_mom_profit"], "amount_base"].sum(),
        }), include_groups=False)
        .reset_index()
    )
    agg["gross_profit_base"] = agg["revenue_base"] - agg["cost_base"] + agg["mom_profit_base"]
    agg["gross_margin_pct"] = agg.apply(
        lambda r: r["gross_profit_base"] / r["revenue_base"]
        if r["revenue_base"] > 0 else 0.0,
        axis=1
    )
    return agg


def build_node_pl_summary(events: List[PPCEvent]) -> pd.DataFrame:
    """
    Full-horizon (all weeks combined) per-node P&L table -- "拠点別P/L評価".

    Unlike build_node_week_summary(), this collapses the week dimension so
    each SC Node (leaf_in supplier / MOM / DAD / leaf_out channel) appears
    exactly once per product with its total Revenue / Cost / Gross Profit
    across the whole simulation horizon. Intended for the Management tab's
    per-node P&L table (node-level granularity, as opposed to the existing
    SKU-level P&L Summary table).

    Node attribution relies on every PPCEvent carrying the node_id where the
    cost/revenue actually occurred -- see ppc_forward.py's per-supplier event
    emission (Battery/Motor/ECU etc. each get their own supplier_cost event)
    for why this is now accurate even for multi-Tier-1-supplier BOMs.

    Columns: node_id, product_id, revenue_base, cost_base, tariff_base,
             gross_profit_base, gross_margin_pct, lot_events
    """
    rows = []
    for ev in events:
        if ev.ppc_event_type in ("transfer_price_set", "backward_allowable", "landed_cost_total"):
            continue
        rows.append({
            "node_id":     ev.node_id,
            "product_id":  ev.product_id,
            "is_revenue":  ev.ppc_event_type in REVENUE_EVENT_TYPES,
            "is_cost":     ev.ppc_event_type in COST_EVENT_TYPES,
            "is_tariff":   ev.ppc_event_type == "tariff_cost",
            "amount_base": ev.amount_base * (ev.qty or 1),
        })
    if not rows:
        return pd.DataFrame(columns=[
            "node_id", "product_id", "revenue_base", "cost_base",
            "tariff_base", "gross_profit_base", "gross_margin_pct", "lot_events",
        ])
    df = pd.DataFrame(rows)
    agg = (
        df.groupby(["node_id", "product_id"])
        .apply(lambda g: pd.Series({
            "revenue_base": g.loc[g["is_revenue"], "amount_base"].sum(),
            "cost_base":    g.loc[g["is_cost"],    "amount_base"].sum(),
            "tariff_base":  g.loc[g["is_tariff"],  "amount_base"].sum(),
            "lot_events":   len(g),
        }), include_groups=False)
        .reset_index()
    )
    agg["gross_profit_base"] = agg["revenue_base"] - agg["cost_base"]
    agg["gross_margin_pct"] = agg.apply(
        lambda r: r["gross_profit_base"] / r["revenue_base"] if r["revenue_base"] > 0 else 0.0,
        axis=1,
    )
    return agg.sort_values(["product_id", "node_id"]).reset_index(drop=True)


def build_kpi_summary(
    accumulators: List[LotCostAccumulator],
    trust_events: List[PPCTrustEvent],
    base_currency: str = "JPY",
) -> Dict:
    """
    Top-level KPI dict.

    Keys:
        base_currency, total_lots, total_qty_units, total_revenue_base,
        total_cost_base, gross_profit_base, gross_margin_pct,
        total_tariff_base, mom_profit_base, channel_jp_revenue_base,
        channel_us_revenue_base, trust_event_count, trust_event_types

    Note: LotCostAccumulator fields (market_revenue_base, total_forward_cost_base(),
    etc.) hold PER-UNIT amounts; a.qty carries the real physical quantity of the
    underlying aggregated weekly PSI record. Every total below is multiplied by
    a.qty so that "total_lots" (count of accumulator/lot-records, e.g. distinct
    weekly shipments) stays a separate, meaningful metric from the real unit count.
    """
    total_revenue  = sum(a.market_revenue_base * a.qty         for a in accumulators)
    total_cost     = sum(a.total_forward_cost_base() * a.qty   for a in accumulators)
    total_tariff   = sum((a.tariff_in_base + a.tariff_out_base) * a.qty for a in accumulators)
    mom_supply_all = sum(
        (a.supplier_cost_base + a.conversion_cost_base + a.logistics_in_base) * a.qty
        for a in accumulators
    )
    mom_tp_all     = sum(a.transfer_price_base * a.qty for a in accumulators)
    mom_profit     = mom_tp_all - mom_supply_all

    jp_rev = sum(
        a.market_revenue_base * a.qty for a in accumulators if a.channel_node == "JP_Channel"
    )
    us_rev = sum(
        a.market_revenue_base * a.qty for a in accumulators if a.channel_node == "US_Channel"
    )

    gross_profit = total_revenue - total_cost
    gross_margin = gross_profit / total_revenue if total_revenue > 0 else 0.0

    trust_types = list({t.trust_event_type for t in trust_events})

    return {
        "base_currency":            base_currency,
        "total_lots":               len(accumulators),
        "total_qty_units":          sum(a.qty for a in accumulators),
        "total_revenue_base":       total_revenue,
        "total_cost_base":          total_cost,
        "gross_profit_base":        gross_profit,
        "gross_margin_pct":         gross_margin,
        "total_tariff_base":        total_tariff,
        "mom_profit_base":          mom_profit,
        "channel_jp_revenue_base":  jp_rev,
        "channel_us_revenue_base":  us_rev,
        "trust_event_count":        len(trust_events),
        "trust_event_types":        trust_types,
    }
