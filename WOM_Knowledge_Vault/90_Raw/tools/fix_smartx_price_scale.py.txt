#!/usr/bin/env python3
"""
tools/fix_smartx_price_scale.py
================================
One-time data-fix script (smartx-2027-2029-fix-request-letter.md, Open
Question 6 / "revenue-cost scale" issue).

Root cause: sc_tree_master.csv's cpu_size column is 1 for every
SmartX/SmartXNext/SmartXPro_CN/SmartXPro_IN node, i.e. "1 lot = 1 unit"
in this model's simulation. But the PPC cost/price CSVs were populated
assuming a much larger lot size -- empirically exactly 10,000 units/lot
(e.g. ppc_market_price.csv's Retail_AMER row for SmartXPro_IN is
9,990,000 USD, and sku_master.csv's matching per-unit selling_price is
999 USD; 9,990,000 / 999 == 10,000 -- confirmed identical for all 9
market_price rows across SmartX/SmartXNext/SmartXPro). Several node_cost
comments literally say "$999/unit x 100 units/lot" while the actual
number reflects 10,000, not 100 -- the comment itself has the bug.

Fix (per owner decision, option B): scale down the $/lot figures by
10,000 so they become genuine $/unit figures consistent with cpu_size=1
and with sku_master.csv's already-correct per-unit prices. This is
applied uniformly to all three products (SmartX, SmartXNext,
SmartXPro_CN, SmartXPro_IN) since the same generation bug affected all
of them identically, not just SmartXPro.

Files touched (all $-denominated columns feeding the live PPC engine or
the buffering-stock-optimizer plugin):
  - ppc_market_price.csv        (market_price)
  - ppc_supplier_cost.csv       (purchase_price)
  - ppc_node_cost_rule.csv      (fixed_amount, basis=per_lot rows)
  - ppc_edge_cost_rule.csv      (fixed_amount)
  - node_cost_master.csv        (selling_price_per_lot, unit_cost_per_lot)

NOT touched (already correct, or not $-denominated):
  - sku_master.csv              (already per-unit)
  - ppc_tariff_rule.csv         (tariff_rate is a %, not $)
  - ppc_profit_zone_rule.csv    (rate is a %; fixed_amount already 0)
  - ppc_transfer_price_rule.csv (margin_rate is a %; fixed_price blank)
  - demand_forecast.csv / capacity_plan.csv / inventory_master.csv
    (physical unit quantities, not $ amounts)

Idempotent guard: skipped if ppc_market_price.csv's first SmartX-family
market_price row is already below 1_000_000 USD (i.e. already fixed).
"""
from __future__ import annotations

import os
import sys
import pandas as pd

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "data/sample/smartx-2027-2029"
SCALE = 10_000

SMARTX_PRODUCTS = {"SmartX", "SmartXNext", "SmartXPro_CN", "SmartXPro_IN"}


def path(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def already_fixed() -> bool:
    df = pd.read_csv(path("ppc_market_price.csv"))
    rows = df[df["product_id"].isin(SMARTX_PRODUCTS)]
    if rows.empty:
        return True
    return float(rows["market_price"].iloc[0]) < 1_000_000


def fix_market_price():
    fp = path("ppc_market_price.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    mask = df["product_id"].isin(SMARTX_PRODUCTS)
    df.loc[mask, "market_price"] = (df.loc[mask, "market_price"] / SCALE).round(2)
    df.to_csv(fp, index=False)
    print(f"[ppc_market_price.csv] scaled {int(mask.sum())} rows by 1/{SCALE}")


def fix_supplier_cost():
    fp = path("ppc_supplier_cost.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    mask = df["product_id"].isin(SMARTX_PRODUCTS)
    df.loc[mask, "purchase_price"] = (df.loc[mask, "purchase_price"] / SCALE).round(2)
    df.to_csv(fp, index=False)
    print(f"[ppc_supplier_cost.csv] scaled {int(mask.sum())} rows by 1/{SCALE}")


def fix_node_cost_rule():
    fp = path("ppc_node_cost_rule.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    mask = df["product_id"].isin(SMARTX_PRODUCTS)
    df.loc[mask, "fixed_amount"] = (df.loc[mask, "fixed_amount"] / SCALE).round(2)
    df.to_csv(fp, index=False)
    print(f"[ppc_node_cost_rule.csv] scaled {int(mask.sum())} rows by 1/{SCALE}")


def fix_edge_cost_rule():
    fp = path("ppc_edge_cost_rule.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    mask = df["product_id"].isin(SMARTX_PRODUCTS)
    df.loc[mask, "fixed_amount"] = (df.loc[mask, "fixed_amount"] / SCALE).round(2)
    df.to_csv(fp, index=False)
    print(f"[ppc_edge_cost_rule.csv] scaled {int(mask.sum())} rows by 1/{SCALE}")


def fix_node_cost_master():
    fp = path("node_cost_master.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    mask = df["sku_id"].isin(SMARTX_PRODUCTS)
    df.loc[mask, "selling_price_per_lot"] = (df.loc[mask, "selling_price_per_lot"] / SCALE).round(2)
    df.loc[mask, "unit_cost_per_lot"] = (df.loc[mask, "unit_cost_per_lot"] / SCALE).round(2)
    # The "x 100 units/lot" phrase in retail-node notes was factually wrong
    # (actual ratio was 10,000, not 100) and is now moot post-fix (1 lot =
    # 1 unit); strip it so the note doesn't keep misleading future readers.
    df.loc[mask, "note"] = df.loc[mask, "note"].str.replace(
        r"\s*—\s*\$[\d,]+/unit x 100 units/lot", "", regex=True
    )
    df.to_csv(fp, index=False)
    print(f"[node_cost_master.csv] scaled {int(mask.sum())} rows by 1/{SCALE}")


def main():
    if already_fixed():
        print("Already fixed (SmartX-family market_price already < 1,000,000). No-op.")
        return
    fix_market_price()
    fix_supplier_cost()
    fix_node_cost_rule()
    fix_edge_cost_rule()
    fix_node_cost_master()
    print("\nDone. SmartX/SmartXNext/SmartXPro_CN/SmartXPro_IN $/lot figures rescaled to genuine $/unit (cpu_size=1).")


if __name__ == "__main__":
    main()
