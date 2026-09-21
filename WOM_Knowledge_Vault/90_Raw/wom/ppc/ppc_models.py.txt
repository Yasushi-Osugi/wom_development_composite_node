"""
wom/ppc/ppc_models.py
=====================
Data classes for PPC (Profit / Price / Cost) Simulation Engine.

Design:
    - PPCEvent: single financial event on the supply chain (immutable record)
    - PPCTrustEvent: reconciliation alert for a lot
    - LotCostAccumulator: mutable per-lot cost state during computation
    - PPCSimulationResult: final output bundle

PPC Event types:
    Forward:
        supplier_cost          - material purchase at Supplier node
        conversion_cost        - production cost at MOM node
        transfer_price_set     - transfer price determined at MOM (informational)
        logistics_cost         - freight cost on an edge
        insurance_cost         - insurance on an edge
        tariff_cost            - import duty on cross-border edge
        landed_cost_total      - sum of transfer + logistics + insurance + tariff (informational)
        warehouse_cost         - storage cost at DAD/Operation node
        sga_cost               - selling/general/admin cost at a node
        marketing_cost         - marketing cost at a node
        hq_royalty             - global HQ brand royalty (future)
    Revenue:
        market_revenue         - sale revenue at leaf_out (market channel)
    Backward:
        backward_allowable     - allowable cost computed backward from market price

cost_phase values (Phase 3: FOB/CIF/DAD breakdown):
    EXW    : ex-works supplier cost (raw material purchase)
    FOB    : factory-to-origin-port logistics (Supplier->MOM edge)
    MOM    : manufacturing conversion cost at MOM node
    CIF    : ocean freight + insurance + bonded-warehouse handling at first DAD
    TARIFF : import duty (inbound or outbound)
    DAD    : domestic distribution (inter-DAD edges + subsequent DAD node costs)
    SGA    : selling/general/admin cost at any node
    REVENUE: market revenue event
    ""     : informational / reconciliation events (landed_cost_total, backward_allowable, etc.)

Trust Event types (reconciliation):
    NEGATIVE_MARGIN                - forward cost > backward allowable at leaf_out
    TARIFF_SHOCK                   - tariff cost > 20% of transfer price
    LANDED_COST_EXCEEDS_MARKET     - landed cost at DAD > market price
    MOM_PROFIT_TOO_LOW             - MOM gross profit < 0
    CHANNEL_MARGIN_TOO_LOW         - channel gross margin < 5%
    HQ_ROYALTY_BURDEN_TOO_HIGH     - royalty > 10% of market price
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# PPCEvent
# ---------------------------------------------------------------------------
@dataclass
class PPCEvent:
    """
    A single financial event in the PPC Simulation Engine.

    All amounts are in both local currency and base currency (JPY by default).

    IMPORTANT convention (added when the qty-aggregation bug was fixed):
    amount_local / amount_base / amount_per_unit_base are all PER-UNIT
    amounts (the master-rate value for one physical unit, converted to base
    currency). qty carries the real physical quantity represented by the
    underlying aggregated weekly PSI record (one accumulator/event set can
    represent many units — see ppc_psi_bridge.psi_to_sales_records). Do NOT
    multiply amount_base by qty when reasoning about a single event's cost
    propagation (tariff %, margin checks, backward_allowable, etc. all
    correctly operate on a per-unit basis). Only multiply by qty when
    producing an absolute-currency TOTAL for reporting — this is done
    centrally in ppc_kpi.py's build_* functions, which is the single place
    responsible for converting per-unit amounts into real totals.
    """
    event_id:            str
    week:                str         # ISO week, e.g. "2026-W01"
    lot_id:              str
    node_id:             str
    edge_id:             str         # "" if pure node event
    product_id:          str
    qty:                 int         # real physical quantity of this lot-record (see LotCostAccumulator.qty)
    ppc_event_type:      str         # see module docstring
    amount_local:        float       # PER-UNIT amount in local (transaction) currency
    currency:            str         # local currency code
    fx_rate:             float       # local -> base_currency conversion rate
    amount_base:         float       # PER-UNIT amount in base currency (multiply by qty for a total; see class docstring)
    amount_per_unit_base: float      # same as amount_base (kept for backward-compat field naming)
    source_rule:         str         # which master rule triggered this event
    direction:           str         # "forward" | "backward" | "revenue"
    profit_zone:         str         # OUTBOUND_CHANNEL_PROFIT / MOM_PLANT_PROFIT / etc.
    cost_phase:          str = ""    # EXW / FOB / MOM / CIF / TARIFF / DAD / SGA / REVENUE / ""


# ---------------------------------------------------------------------------
# PPCTrustEvent  (Reconciliation alert)
# ---------------------------------------------------------------------------
@dataclass
class PPCTrustEvent:
    """
    Generated when reconciliation detects an unresolvable gap.
    Named after WOM's general Trust-Event concept.
    """
    lot_id:                     str
    week:                       str
    channel_node:               str
    product_id:                 str
    trust_event_type:           str    # see module docstring
    forward_cost_base:          float  # total forward cost in base currency
    backward_allowable_base:    float  # backward allowable cost in base currency
    gap_base:                   float  # forward_cost - backward_allowable (>0 = deficit)
    message:                    str


# ---------------------------------------------------------------------------
# LotCostAccumulator  (mutable, internal use during computation)
# ---------------------------------------------------------------------------
@dataclass
class LotCostAccumulator:
    """
    Mutable per-lot state accumulated during forward propagation.
    Converted to PPCEvents when each cost item is finalized.
    """
    lot_id:             str
    week:               str
    product_id:         str
    channel_node:       str         # leaf_out node_id (destination channel)

    # Real physical quantity represented by this lot-record. WOM's PSI bridge
    # (ppc_psi_bridge.py, psi_to_sales_records) aggregates one weekly
    # (product, channel, week) row per accumulator, so a single "lot" here
    # can represent many physical units (e.g. a week's worth of shipments).
    # All per-lot cost/revenue rates in the master CSVs (ppc_supplier_cost.csv,
    # ppc_market_price.csv, ppc_node_cost_rule.csv basis="qty", etc.) are
    # per-UNIT rates, so downstream KPI aggregation (ppc_kpi.py) must multiply
    # by qty to get true totals. Defaults to 1.0 for backward compatibility
    # with any caller that does not set it explicitly.
    qty:                float = 1.0

    # Forward costs (in base currency)
    supplier_cost_base:     float = 0.0
    conversion_cost_base:   float = 0.0
    logistics_in_base:      float = 0.0   # inbound logistics (Supplier->MOM edge only)
    # MOM->first_DAD freight (e.g. ocean/air freight from factory to the
    # importing DC). Kept SEPARATE from logistics_in_base (added 2026-07-10):
    # under FOB-style terms this cost is borne by the buyer/DAD side, not by
    # MOM, so it must NOT be counted against MOM's own margin in
    # ppc_reconcile.py's MOM_PROFIT_TOO_LOW check. Previously this was
    # (incorrectly) added into logistics_in_base by ppc_tariff.py, which
    # caused MOM_PROFIT_TOO_LOW to fire on every lot as soon as any
    # MOM->DAD freight cost was configured (found while verifying
    # apparel-us-2026 Phase 2). Still included in total_forward_cost_base()
    # so overall cost totals are unaffected -- only the MOM-profit
    # attribution changes.
    mom_to_dad_freight_base: float = 0.0
    # Freight on inter-DAD edges (chain[i]->chain[i+1] for i>=1, e.g. a
    # regional FG warehouse -> market-specific DC leg in a multi-tier
    # OutBound DAD chain). Kept SEPARATE from logistics_in_base for the
    # SAME reason as mom_to_dad_freight_base above (added 2028-07-13,
    # apparel-global-2028-2029 verification): ppc_tariff.py's inter-DAD
    # walk (Step 3, section b/c) previously added this straight into
    # logistics_in_base, which ppc_reconcile.py's MOM_PROFIT_TOO_LOW check
    # and ppc_profit_zone.py's MOM-profit event both read as "MOM's own
    # inbound supply cost" -- so any inter-DAD freight silently inflated
    # mom_supply_cost and fired MOM_PROFIT_TOO_LOW on every lot, even
    # though the freight has nothing to do with MOM's own margin (it is a
    # downstream, market-side distribution cost). This never surfaced on
    # any earlier case because none of them had a 2+-tier DAD chain (the
    # inter-DAD loop was dead code for a single-DAD topology). Still
    # included in total_forward_cost_base() / landed cost, so overall
    # totals are unaffected -- only the MOM-profit attribution changes.
    inter_dad_freight_base: float = 0.0
    tariff_in_base:         float = 0.0   # import duty CN->JP
    insurance_in_base:      float = 0.0   # insurance on CN->JP edge
    logistics_out_base:     float = 0.0   # outbound logistics (DAD->Channel edge)
    tariff_out_base:        float = 0.0   # import duty JP->US (if applicable)
    warehouse_base:         float = 0.0   # DAD warehouse cost
    dad_sga_base:           float = 0.0   # DAD SGA
    channel_sga_base:       float = 0.0   # Channel SGA
    channel_marketing_base: float = 0.0   # Channel marketing

    # Transfer price (in base currency, for reference)
    transfer_price_local:   float = 0.0   # CNY
    transfer_price_base:    float = 0.0   # JPY

    # Revenue (in base currency)
    market_revenue_base:    float = 0.0

    # Backward allowable (in base currency)
    backward_allowable_base: float = 0.0

    def total_forward_cost_base(self) -> float:
        return (
            self.supplier_cost_base
            + self.conversion_cost_base
            + self.logistics_in_base
            + self.mom_to_dad_freight_base
            + self.inter_dad_freight_base
            + self.tariff_in_base
            + self.insurance_in_base
            + self.logistics_out_base
            + self.tariff_out_base
            + self.warehouse_base
            + self.dad_sga_base
            + self.channel_sga_base
            + self.channel_marketing_base
        )

    def gross_profit_base(self) -> float:
        return self.market_revenue_base - self.total_forward_cost_base()

    def gross_margin_pct(self) -> float:
        if self.market_revenue_base <= 0:
            return 0.0
        return self.gross_profit_base() / self.market_revenue_base


# ---------------------------------------------------------------------------
# PPCSimulationResult
# ---------------------------------------------------------------------------
@dataclass
class PPCSimulationResult:
    """
    Complete output of one PPC simulation run.
    """
    base_currency:          str
    lot_accumulators:       List[LotCostAccumulator]
    ppc_events:             List[PPCEvent]
    trust_events:           List[PPCTrustEvent]
    node_week_summary:      "pd.DataFrame"   # type: ignore
    profit_zone_summary:    "pd.DataFrame"   # type: ignore
    lot_reconciliation:     "pd.DataFrame"   # type: ignore
    kpi_summary:            Dict
    node_pl_summary:        "pd.DataFrame" = None   # type: ignore  # 拠点別P/L評価 (full-horizon, per node x product)
