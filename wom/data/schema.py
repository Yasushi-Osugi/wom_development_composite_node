"""
WOM data schema – column name constants and master data dataclasses.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SKUMaster:
    sku_id: str
    sku_name: str
    region: str
    uom: str = "EA"
    unit_cost: float = 0.0
    selling_price: float = 0.0
    dso_wks: int = 6
    dpo_wks: int = 8
    safety_stock_wks: float = 0.0
    lead_time_wks: int = 0
    order_multiple: float = 0.0
    max_order_qty: float = 0.0
    shelf_life_wks: int = 0
    active: bool = True

    @property
    def key(self):
        return (self.sku_id, self.region)


@dataclass
class DemandForecast:
    sku_id: str
    region: str
    week: str
    quantity: float
    source: str = "statistical"


@dataclass
class InventoryMaster:
    sku_id: str
    region: str
    on_hand: float = 0.0
    on_order: float = 0.0
    first_receipt_wk: str = ""


@dataclass
class CapacityPlan:
    sku_id: str
    region: str
    week: str
    max_supply: float
    source: str = "procurement"


class Cols:
    """Canonical DataFrame column names used throughout WOM."""

    # Keys
    SKU_ID   = "sku_id"
    REGION   = "region"
    WEEK     = "week"

    # SKU master
    SKU_NAME        = "sku_name"
    UOM             = "uom"
    UNIT_COST       = "unit_cost"
    SELLING_PRICE   = "selling_price"
    DSO_WKS         = "dso_wks"
    DPO_WKS         = "dpo_wks"
    SS_WKS          = "safety_stock_wks"
    LT_WKS          = "lead_time_wks"
    ORDER_MULT      = "order_multiple"
    MAX_ORDER_QTY   = "max_order_qty"
    SHELF_LIFE_WKS  = "shelf_life_wks"
    ACTIVE          = "active"

    # Demand
    DEMAND_QTY      = "quantity"
    DEMAND_SOURCE   = "source"

    # Inventory master
    ON_HAND         = "on_hand"
    ON_ORDER        = "on_order"
    FIRST_RECEIPT   = "first_receipt_wk"

    # Capacity
    MAX_SUPPLY      = "max_supply"
    CAP_SOURCE      = "source"

    # Simulation output
    SCENARIO        = "scenario"
    OPENING_INV     = "opening_inv"
    SUPPLY_RECEIPT  = "supply_receipt"
    GROSS_AVAIL     = "gross_avail"
    DEMAND_FCST     = "demand_fcst"
    # Planning DataFrame (sc_tree_to_planning_df) -- the meaning of
    # demand_fulfilled depends on QTY_BASIS
    # (RequestLetter_SmartphoneWarmup_EVUpdateKitting_S2 C2):
    #   "request"      legacy / mode not given: len(supply S) x cpu, i.e. the
    #                  REQUEST (Demand Position). The old evaluation, unchanged.
    #   "actual_ship"  identity: the actual shipment of the week (= SHIP_QTY,
    #                  late shipments included). Revenue / COGS use this.
    #   "unknown"      identity, but the node has no shipment record: NaN
    #                  (never replaced by the request).
    DEMAND_FULFILLED= "demand_fulfilled"
    SHIP_QTY        = "ship_qty"         # actual shipment (node._actual_ship) x cpu
    QTY_BASIS       = "qty_basis"        # "request" / "actual_ship" / "unknown"
    REQUEST_QTY     = "request_qty"      # this week's request: len(supply S) x cpu
    ON_TIME_QTY     = "on_time_qty"      # this week's request IDs shipped this week
    CO_END_QTY      = "co_end_qty"       # requests still open at the END of the week
    STOCKOUT_QTY    = "stockout_qty"
    CLOSING_INV     = "closing_inv"
    SAFETY_STOCK_QTY= "safety_stock_qty"
    REORDER_QTY     = "reorder_qty"
    CAPACITY_USED   = "capacity_used"
    CAPACITY_AVAIL  = "capacity_avail"
    FILL_RATE       = "fill_rate"
    INV_COVER_WKS   = "inv_cover_wks"
    INV_VALUE       = "inv_value"

    # Money PSI (Management Layer)
    REVENUE         = "revenue"
    COGS            = "cogs"
    GROSS_PROFIT    = "gross_profit"
    GROSS_MARGIN    = "gross_margin"
    INV_VALUE_COST  = "inv_value_cost"
    AR_VALUE        = "ar_value"
    AP_VALUE        = "ap_value"
    CCC_WKS         = "ccc_wks"
