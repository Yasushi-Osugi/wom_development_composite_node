"""
WOM data loader – reads CSV/Excel input files into validated DataFrames.
"""

from __future__ import annotations

import os
import warnings
from typing import Optional

import pandas as pd

from wom.data.schema import Cols


def _read(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str)
    return pd.read_csv(path, dtype=str)


def _coerce_float(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


def _coerce_int(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    return df


def _coerce_bool(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = df[c].str.strip().str.lower().map(
                {"true": True, "1": True, "yes": True,
                 "false": False, "0": False, "no": False}
            ).fillna(True)
    return df


def _require_cols(df: pd.DataFrame, required: list, source: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"[{source}] Missing required columns: {missing}")


def load_sku_master(path: str) -> pd.DataFrame:
    df = _read(path)
    df.columns = df.columns.str.strip().str.lower()
    _require_cols(df, [Cols.SKU_ID, Cols.SKU_NAME, Cols.REGION], "sku_master")

    if Cols.UOM not in df.columns:
        df[Cols.UOM] = "EA"
    for col, default in [
        (Cols.UNIT_COST, 0.0), (Cols.SELLING_PRICE, 0.0),
        (Cols.SS_WKS, 0.0), (Cols.ORDER_MULT, 0.0), (Cols.MAX_ORDER_QTY, 0.0),
    ]:
        if col not in df.columns:
            df[col] = default
    for col, default in [(Cols.LT_WKS, 0), (Cols.SHELF_LIFE_WKS, 0),
                         (Cols.DSO_WKS, 6), (Cols.DPO_WKS, 8)]:
        if col not in df.columns:
            df[col] = default

    df = _coerce_float(df, [Cols.UNIT_COST, Cols.SELLING_PRICE,
                             Cols.SS_WKS, Cols.ORDER_MULT, Cols.MAX_ORDER_QTY])
    df = _coerce_int(df, [Cols.LT_WKS, Cols.SHELF_LIFE_WKS, Cols.DSO_WKS, Cols.DPO_WKS])
    df = _coerce_bool(df, [Cols.ACTIVE])

    df = df[df[Cols.ACTIVE].astype(bool)].reset_index(drop=True)
    df[Cols.SKU_ID] = df[Cols.SKU_ID].str.strip()
    df[Cols.REGION]  = df[Cols.REGION].str.strip()
    return df


def load_demand_forecast(path: str, weeks=None) -> pd.DataFrame:
    df = _read(path)
    df.columns = df.columns.str.strip().str.lower()
    _require_cols(df, [Cols.SKU_ID, Cols.REGION, Cols.WEEK, Cols.DEMAND_QTY], "demand_forecast")

    if Cols.DEMAND_SOURCE not in df.columns:
        df[Cols.DEMAND_SOURCE] = "statistical"

    df = _coerce_float(df, [Cols.DEMAND_QTY])
    df[Cols.SKU_ID] = df[Cols.SKU_ID].str.strip()
    df[Cols.REGION]  = df[Cols.REGION].str.strip()
    df[Cols.WEEK]    = df[Cols.WEEK].str.strip()

    if weeks is not None:
        df = df[df[Cols.WEEK].isin(weeks)]

    return df.reset_index(drop=True)


def load_inventory_master(path: str) -> pd.DataFrame:
    df = _read(path)
    df.columns = df.columns.str.strip().str.lower()
    _require_cols(df, [Cols.SKU_ID, Cols.REGION], "inventory_master")

    for col, default in [(Cols.ON_HAND, 0.0), (Cols.ON_ORDER, 0.0)]:
        if col not in df.columns:
            df[col] = default
    if Cols.FIRST_RECEIPT not in df.columns:
        df[Cols.FIRST_RECEIPT] = ""

    df = _coerce_float(df, [Cols.ON_HAND, Cols.ON_ORDER])
    df[Cols.SKU_ID]        = df[Cols.SKU_ID].str.strip()
    df[Cols.REGION]         = df[Cols.REGION].str.strip()
    df[Cols.FIRST_RECEIPT]  = df[Cols.FIRST_RECEIPT].fillna("").str.strip()
    return df.reset_index(drop=True)


def load_capacity_plan(path: str, weeks=None) -> pd.DataFrame:
    df = _read(path)
    df.columns = df.columns.str.strip().str.lower()
    _require_cols(df, [Cols.SKU_ID, Cols.REGION, Cols.WEEK, Cols.MAX_SUPPLY], "capacity_plan")

    if Cols.CAP_SOURCE not in df.columns:
        df[Cols.CAP_SOURCE] = "procurement"

    df = _coerce_float(df, [Cols.MAX_SUPPLY])
    df[Cols.SKU_ID] = df[Cols.SKU_ID].str.strip()
    df[Cols.REGION]  = df[Cols.REGION].str.strip()
    df[Cols.WEEK]    = df[Cols.WEEK].str.strip()

    if weeks is not None:
        df = df[df[Cols.WEEK].isin(weeks)]

    return df.reset_index(drop=True)


class WOMInputs:
    def __init__(self, sku_master, demand_forecast, inventory_master, capacity_plan):
        self.sku_master = sku_master
        self.demand_forecast = demand_forecast
        self.inventory_master = inventory_master
        self.capacity_plan = capacity_plan

    @classmethod
    def from_files(cls, sku_master_path, demand_forecast_path,
                   inventory_master_path, capacity_plan_path, weeks=None):
        return cls(
            sku_master=load_sku_master(sku_master_path),
            demand_forecast=load_demand_forecast(demand_forecast_path, weeks),
            inventory_master=load_inventory_master(inventory_master_path),
            capacity_plan=load_capacity_plan(capacity_plan_path, weeks),
        )

    def summary(self) -> str:
        return (
            "SKUs/Regions : " + str(len(self.sku_master)) + " rows\n"
            "Demand rows  : " + str(len(self.demand_forecast)) + "\n"
            "Inventory    : " + str(len(self.inventory_master)) + " rows\n"
            "Capacity rows: " + str(len(self.capacity_plan))
        )
