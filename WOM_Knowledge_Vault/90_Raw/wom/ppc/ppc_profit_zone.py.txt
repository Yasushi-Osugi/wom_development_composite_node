"""
wom/ppc/ppc_profit_zone.py
==========================
Step 4: Market Revenue and Channel Cost Events.

Generates:
    - market_revenue event (at leaf_out, for each lot sold)
    - channel sga_cost and marketing_cost events (at leaf_out node)

Also computes MOM profit (= transfer_price - accumulated_supply_cost)
as a forward event for the MOM_PLANT_PROFIT zone.

Note: "Profit Zone" assignment is done on ALL events via the
profit_zone field in PPCEvent, which is set from ppc_node_profit_zone.csv.
The ppc_profit_zone_summary is built later by ppc_kpi.py.
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Union

from .ppc_models import LotCostAccumulator, PPCEvent
from .ppc_fx import FXConverter
from .ppc_rules import PPCRuleSet


def _resolve_node(node: Union[str, Dict[str, str]], product_id: str) -> str:
    if isinstance(node, dict):
        return node.get(product_id, next(iter(node.values()), "MOM_China"))
    return node if node else "MOM_China"


def run_profit_zone_allocation(
    accumulators: List[LotCostAccumulator],
    rules: PPCRuleSet,
    fx: FXConverter,
    mom_node: Union[str, Dict[str, str]] = "MOM_China",
) -> List[PPCEvent]:
    """
    Step 4: Market revenue + channel costs.

    For each lot, generates:
        1. market_revenue event at the channel node
        2. channel sga_cost event (revenue-based)
        3. channel marketing_cost event (revenue-based)
        4. mom_profit event (transfer_price - supply_cost, at MOM zone)

    Parameters
    ----------
    accumulators : mutable; updates market_revenue_base, channel_sga_base,
                   channel_marketing_base
    rules        : PPCRuleSet
    fx           : FXConverter

    Returns
    -------
    List of PPCEvent
    """
    events: List[PPCEvent] = []
    _ctr = itertools.count(1)

    for acc in accumulators:
        product = acc.product_id
        week = acc.week
        channel = acc.channel_node
        channel_zone = rules.get_profit_zone(channel, product)

        # ── 1) Market Revenue ──────────────────────────────────────────
        market_price_local, market_currency = rules.get_market_price(
            channel, product, week
        )
        rev_fx_rate, rev_base = fx.convert(market_price_local, market_currency, week)
        acc.market_revenue_base = rev_base

        events.append(PPCEvent(
            event_id=f"REV-{next(_ctr):06d}",
            week=week,
            lot_id=acc.lot_id,
            node_id=channel,
            edge_id="",
            product_id=product,
            qty=int(round(acc.qty)),
            ppc_event_type="market_revenue",
            amount_local=market_price_local,
            currency=market_currency,
            fx_rate=rev_fx_rate,
            amount_base=rev_base,
            amount_per_unit_base=rev_base,
            source_rule="ppc_market_price.csv",
            direction="revenue",
            profit_zone=channel_zone,
        ))

        # ── 2 & 3) Channel SGA + Marketing costs ──────────────────────
        for _, row in rules.get_node_costs(channel, product).iterrows():
            ct = str(row["cost_type"])
            c_currency = str(row["currency"])
            basis = str(row["basis"])
            rate = float(row["rate"])
            fixed = float(row["fixed_amount"])

            if basis == "revenue":
                # Revenue in local channel currency
                c_local = rate * market_price_local + fixed
            elif basis == "qty":
                c_local = rate * 1 + fixed
            else:
                c_local = fixed

            c_fx_rate, c_base = fx.convert(c_local, c_currency, week)

            if ct == "sga_cost":
                acc.channel_sga_base += c_base
            elif ct == "marketing_cost":
                acc.channel_marketing_base += c_base

            events.append(PPCEvent(
                event_id=f"CH-{next(_ctr):06d}",
                week=week,
                lot_id=acc.lot_id,
                node_id=channel,
                edge_id="",
                product_id=product,
                qty=int(round(acc.qty)),
                ppc_event_type=ct,
                amount_local=c_local,
                currency=c_currency,
                fx_rate=c_fx_rate,
                amount_base=c_base,
                amount_per_unit_base=c_base,
                source_rule="ppc_node_cost_rule.csv",
                direction="forward",
                profit_zone=channel_zone,
            ))

        # ── 4) MOM plant profit ────────────────────────────────────────
        # MOM profit = transfer_price - (supplier_cost + conversion_cost + inbound_logistics)
        mom_supply_cost_base = (
            acc.supplier_cost_base
            + acc.conversion_cost_base
            + acc.logistics_in_base
        )
        mom_gross_profit_base = acc.transfer_price_base - mom_supply_cost_base
        m_node = _resolve_node(mom_node, product)
        mom_zone = rules.get_profit_zone(m_node, product)

        events.append(PPCEvent(
            event_id=f"MOM-{next(_ctr):06d}",
            week=week,
            lot_id=acc.lot_id,
            node_id=m_node,
            edge_id="",
            product_id=product,
            qty=int(round(acc.qty)),
            ppc_event_type="mom_profit",
            amount_local=mom_gross_profit_base,   # already in base currency
            currency=fx.base_currency,
            fx_rate=1.0,
            amount_base=mom_gross_profit_base,
            amount_per_unit_base=mom_gross_profit_base,
            source_rule="computed:transfer_price - supply_cost",
            direction="forward",
            profit_zone=mom_zone,
        ))

    return events
