---
tags: [wom, code]
---
# wom/data/loader.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/data/loader.py) · [原文テキスト](../../../90_Raw/wom/data/loader.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/01_Data_Building|Data Building]]

## モジュール説明（docstring原文）

```text
WOM data loader – reads CSV/Excel input files into validated DataFrames.
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_read` | 16 | docstringなし（下のコード参照） |
| FunctionDef | `_coerce_float` | 23 | docstringなし（下のコード参照） |
| FunctionDef | `_coerce_int` | 30 | docstringなし（下のコード参照） |
| FunctionDef | `_coerce_bool` | 37 | docstringなし（下のコード参照） |
| FunctionDef | `_require_cols` | 47 | docstringなし（下のコード参照） |
| FunctionDef | `load_sku_master` | 53 | docstringなし（下のコード参照） |
| FunctionDef | `load_demand_forecast` | 82 | docstringなし（下のコード参照） |
| FunctionDef | `load_inventory_master` | 101 | docstringなし（下のコード参照） |
| FunctionDef | `load_capacity_plan` | 119 | docstringなし（下のコード参照） |
| ClassDef | `WOMInputs` | 138 | docstringなし（下のコード参照） |
| FunctionDef | `__init__` | 139 | docstringなし（下のコード参照） |
| FunctionDef | `from_files` | 146 | docstringなし（下のコード参照） |
| FunctionDef | `summary` | 155 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/wom/data/schema.py|wom/data/schema.py]]

## 全文（コメント・原文を省略せず収録）

````python
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

````
