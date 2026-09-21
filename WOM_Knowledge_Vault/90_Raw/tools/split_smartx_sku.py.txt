#!/usr/bin/env python3
"""
tools/split_smartx_sku.py
==========================
One-time migration script (smartx-2027-2029-fix-request-letter.md, Step4).

Splits the single "SmartXPro" product (which had TWO independent parallel
final-assembly plants, AssemblyCN and AssemblyIN, feeding one shared
demand pool -- a "1 product = 2 MOM nodes" shape the user's SCM experience
flags as unrealistic / untraceable) into two fully independent products,
each satisfying "1 product = 1 MOM node":

  SmartXPro_CN : AssemblyCN chain (WaferFab_TW -> Buffer_Chip_TW ->
                 FoundryTW -> AssemblyCN) -> DC_EMEA / DC_APAC ->
                 Retail_EMEA / Retail_APAC   (2 channels)
  SmartXPro_IN : AssemblyIN chain (SensorIN -> AssemblyIN) -> DC_AMER ->
                 Retail_AMER                  (1 channel)

Also fixes the Problem C data-level bug: ppc_edge_cost_rule.csv /
ppc_tariff_rule.csv previously routed via the OutBound supply_point
bridge node ("AssemblyCN->SP_SmartXPro", "SP_SmartXPro->Retail_AMER")
instead of the real DAD nodes that ppc_tariff.py / ppc_backward.py
actually build edge_ids from (mom->first_dad, last_dad->channel). This
script re-keys those edges onto the real DAD nodes (DC_AMER / DC_EMEA /
DC_APAC), splitting the old two-hop $ total the same way apparel-us-2026
was fixed: the international-freight leg moves to mom->dad, the flat
domestic leg moves to dad->retail. Total $ amounts per (old) SP-routed
pair are preserved; only the edge_id keys are corrected.

lane_assignment.csv's 3 SmartXPro rows are dropped: post-split, every
product has exactly one MOM root, so the multi-MOM disambiguation
lane_assignment.csv exists for is no longer needed for this SKU family.

Idempotent: re-running on already-migrated data is a no-op (it looks for
"SmartXPro" tokens and does nothing if none remain).
"""
from __future__ import annotations

import os
import sys
import pandas as pd

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "data/sample/smartx-2027-2029"

CN_NODES = {"AssemblyCN", "FoundryTW", "Buffer_Chip_TW", "WaferFab_TW",
            "DC_EMEA", "Retail_EMEA", "DC_APAC", "Retail_APAC"}
IN_NODES = {"AssemblyIN", "SensorIN", "DC_AMER", "Retail_AMER"}

SKU_CN = "SmartXPro_CN"
SKU_IN = "SmartXPro_IN"
SP_CN = "SP_SmartXPro_CN"
SP_IN = "SP_SmartXPro_IN"


def side_of_node(node_name: str) -> str:
    if node_name in CN_NODES:
        return "CN"
    if node_name in IN_NODES:
        return "IN"
    return ""


def path(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def already_migrated() -> bool:
    df = pd.read_csv(path("sku_master.csv"))
    return "SmartXPro" not in set(df["sku_id"])


# ---------------------------------------------------------------------------
# 1. sc_tree_master.csv
# ---------------------------------------------------------------------------
def migrate_sc_tree_master():
    fp = path("sc_tree_master.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    keep = df[df["product_name"] != "SmartXPro"].copy()
    src = df[df["product_name"] == "SmartXPro"].copy()

    new_rows = []
    for _, r in src.iterrows():
        r = r.to_dict()
        node = r["node_name"]
        if node == "SP_SmartXPro":
            for sku, sp_name in ((SKU_CN, SP_CN), (SKU_IN, SP_IN)):
                nr = dict(r)
                nr["node_name"] = sp_name
                nr["product_name"] = sku
                new_rows.append(nr)
            continue
        side = side_of_node(node)
        if not side:
            raise ValueError(f"sc_tree_master.csv: unclassified SmartXPro node {node!r}")
        sku = SKU_CN if side == "CN" else SKU_IN
        nr = dict(r)
        nr["product_name"] = sku
        if nr["parent_node"] == "SP_SmartXPro":
            nr["parent_node"] = SP_CN if side == "CN" else SP_IN
        new_rows.append(nr)

    out = pd.concat([keep, pd.DataFrame(new_rows)], ignore_index=True)
    out.to_csv(fp, index=False)
    print(f"[sc_tree_master.csv] {len(df)} -> {len(out)} rows")


# ---------------------------------------------------------------------------
# 2. sku_master.csv  (region-keyed: AMER->IN, EMEA/APAC->CN)
# ---------------------------------------------------------------------------
def region_to_sku(region: str) -> str:
    return SKU_IN if region == "AMER" else SKU_CN


def migrate_region_keyed_sku(filename: str, sku_col: str = "sku_id", region_col: str = "region"):
    fp = path(filename)
    df = pd.read_csv(fp, keep_default_na=False)
    mask = df[sku_col] == "SmartXPro"
    df.loc[mask, sku_col] = df.loc[mask, region_col].map(region_to_sku)
    df.to_csv(fp, index=False)
    n = int(mask.sum())
    print(f"[{filename}] relabeled {n} SmartXPro rows by region (AMER->IN, EMEA/APAC->CN)")


# ---------------------------------------------------------------------------
# 3. capacity_plan.csv / node_cost_master.csv / ppc_supplier_cost.csv /
#    ppc_transfer_price_rule.csv / ppc_node_cost_rule.csv /
#    ppc_node_profit_zone.csv  -- node-keyed (sku_id + node col)
# ---------------------------------------------------------------------------
def migrate_node_keyed(filename: str, sku_col: str, node_col: str):
    fp = path(filename)
    df = pd.read_csv(fp, keep_default_na=False)
    mask = df[sku_col] == "SmartXPro"

    def resolve(node):
        side = side_of_node(node)
        if not side:
            raise ValueError(f"{filename}: unclassified SmartXPro node {node!r}")
        return SKU_CN if side == "CN" else SKU_IN

    df.loc[mask, sku_col] = df.loc[mask, node_col].map(resolve)
    df.to_csv(fp, index=False)
    n = int(mask.sum())
    print(f"[{filename}] relabeled {n} SmartXPro rows by node ({node_col})")


# ---------------------------------------------------------------------------
# 4. Generic helper for files that key a SmartXPro row on a node column
#    that MAY include the SP_SmartXPro bridge node itself (which must be
#    duplicated into SP_SmartXPro_CN / SP_SmartXPro_IN rather than
#    classified via CN_NODES/IN_NODES).
# ---------------------------------------------------------------------------
def migrate_node_keyed_with_sp(filename: str, sku_col: str, node_col: str):
    fp = path(filename)
    df = pd.read_csv(fp, keep_default_na=False)

    sp_mask = (df[sku_col] == "SmartXPro") & (df[node_col] == "SP_SmartXPro")
    other_mask = (df[sku_col] == "SmartXPro") & (df[node_col] != "SP_SmartXPro")

    keep = df[~(sp_mask | other_mask)].copy()
    sp_rows = df[sp_mask].copy()
    other_rows = df[other_mask].copy()

    def resolve(node):
        side = side_of_node(node)
        if not side:
            raise ValueError(f"{filename}: unclassified node {node!r}")
        return SKU_CN if side == "CN" else SKU_IN

    if len(other_rows):
        other_rows[sku_col] = other_rows[node_col].map(resolve)

    dup_rows = []
    for _, r in sp_rows.iterrows():
        for sku, sp_name in ((SKU_CN, SP_CN), (SKU_IN, SP_IN)):
            nr = r.to_dict()
            nr[node_col] = sp_name
            nr[sku_col] = sku
            dup_rows.append(nr)

    out = pd.concat([keep, other_rows, pd.DataFrame(dup_rows)], ignore_index=True)
    out.to_csv(fp, index=False)
    print(f"[{filename}] {len(df)} -> {len(out)} rows (SP_SmartXPro duplicated per side)")


# ---------------------------------------------------------------------------
# 5. ppc_profit_zone_rule.csv -- product_id-keyed only (role table), needs
#    duplicating (both new SKUs need the full rate set).
# ---------------------------------------------------------------------------
def migrate_ppc_profit_zone_rule():
    fp = path("ppc_profit_zone_rule.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    src = df[df["product_id"] == "SmartXPro"].copy()
    keep = df[df["product_id"] != "SmartXPro"].copy()

    dup_rows = []
    for _, r in src.iterrows():
        for sku in (SKU_CN, SKU_IN):
            nr = r.to_dict()
            nr["product_id"] = sku
            dup_rows.append(nr)

    out = pd.concat([keep, pd.DataFrame(dup_rows)], ignore_index=True)
    out.to_csv(fp, index=False)
    print(f"[ppc_profit_zone_rule.csv] {len(df)} -> {len(out)} rows (duplicated per new SKU)")


# ---------------------------------------------------------------------------
# 6. ppc_market_price.csv -- market_node-keyed (Retail_AMER->IN, EMEA/APAC->CN)
# ---------------------------------------------------------------------------
def migrate_ppc_market_price():
    fp = path("ppc_market_price.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    mask = df["product_id"] == "SmartXPro"

    def resolve(node):
        side = side_of_node(node)
        if not side:
            raise ValueError(f"ppc_market_price.csv: unclassified node {node!r}")
        return SKU_CN if side == "CN" else SKU_IN

    df.loc[mask, "product_id"] = df.loc[mask, "market_node"].map(resolve)
    df.to_csv(fp, index=False)
    print(f"[ppc_market_price.csv] relabeled {int(mask.sum())} SmartXPro rows by market_node")


# ---------------------------------------------------------------------------
# 7. ppc_tariff_rule.csv + ppc_edge_cost_rule.csv -- Problem C data fix:
#    re-key from SP-routed edges to real DAD-routed edges, split $ amounts.
# ---------------------------------------------------------------------------
# old edge -> (new_mom_to_dad_edge, new_dad_to_retail_edge)
OLD_TO_NEW_EDGES = {
    # (mom_side_old_edge): new mom->dad edge   (international leg, keeps old $/rate)
    "AssemblyCN->SP_SmartXPro": None,   # domestic CN hop; folded into dad->retail leg below
    "SP_SmartXPro->Retail_AMER": ("AssemblyIN->DC_AMER", "DC_AMER->Retail_AMER"),
    "SP_SmartXPro->Retail_EMEA": ("AssemblyCN->DC_EMEA", "DC_EMEA->Retail_EMEA"),
    "SP_SmartXPro->Retail_APAC": ("AssemblyCN->DC_APAC", "DC_APAC->Retail_APAC"),
}
# domestic-hop (AssemblyCN->SP_SmartXPro) $ amount is folded into the
# dad->retail (last-mile) leg of the CN-side channels; the IN side never
# had a domestic-hop row in the old data (already broken/zero -- see
# Coding Request Letter, Problem C), so DC_AMER->Retail_AMER gets 0.
DOMESTIC_HOP_SPLIT = {
    "DC_EMEA->Retail_EMEA": True,
    "DC_APAC->Retail_APAC": True,
    "DC_AMER->Retail_AMER": False,
}


def migrate_ppc_tariff_rule():
    fp = path("ppc_tariff_rule.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    src = df[df["product_id"] == "SmartXPro"].copy()
    keep = df[df["product_id"] != "SmartXPro"].copy()

    new_rows = []
    for _, r in src.iterrows():
        old_edge = r["edge_id"]
        mapping = OLD_TO_NEW_EDGES.get(old_edge)
        if mapping is None:
            continue  # domestic AssemblyCN->SP hop: no tariff row needed on either new leg
        mom_dad_edge, dad_retail_edge = mapping
        sku = SKU_IN if "AMER" in dad_retail_edge else SKU_CN
        nr = r.to_dict()
        nr["edge_id"] = mom_dad_edge
        nr["product_id"] = sku
        # from_country: mom's country (CN for AssemblyCN, IN for AssemblyIN)
        nr["from_country"] = "IN" if mom_dad_edge.startswith("AssemblyIN") else "CN"
        new_rows.append(nr)
        # dad->retail leg: same country in/out (domestic), tariff 0
        nr2 = r.to_dict()
        nr2["edge_id"] = dad_retail_edge
        nr2["product_id"] = sku
        nr2["from_country"] = nr["to_country"]
        nr2["tariff_rate"] = 0.0
        new_rows.append(nr2)

    out = pd.concat([keep, pd.DataFrame(new_rows)], ignore_index=True)
    out.to_csv(fp, index=False)
    print(f"[ppc_tariff_rule.csv] {len(df)} -> {len(out)} rows (re-keyed off SP_SmartXPro to real DAD nodes)")


def migrate_ppc_edge_cost_rule():
    fp = path("ppc_edge_cost_rule.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    src = df[df["product_id"] == "SmartXPro"].copy()
    keep = df[df["product_id"] != "SmartXPro"].copy()

    by_edge = {r["edge_id"]: r for _, r in src.iterrows()}
    domestic_amt = float(by_edge["AssemblyCN->SP_SmartXPro"]["fixed_amount"]) if "AssemblyCN->SP_SmartXPro" in by_edge else 0.0

    new_rows = []
    for old_edge, mapping in OLD_TO_NEW_EDGES.items():
        if mapping is None or old_edge not in by_edge:
            continue
        r = by_edge[old_edge]
        mom_dad_edge, dad_retail_edge = mapping
        sku = SKU_IN if "AMER" in dad_retail_edge else SKU_CN
        intl_amt = float(r["fixed_amount"])

        nr = r.to_dict()
        nr["edge_id"] = mom_dad_edge
        nr["product_id"] = sku
        nr["fixed_amount"] = intl_amt
        new_rows.append(nr)

        nr2 = r.to_dict()
        nr2["edge_id"] = dad_retail_edge
        nr2["product_id"] = sku
        nr2["fixed_amount"] = domestic_amt if DOMESTIC_HOP_SPLIT.get(dad_retail_edge, False) else 0.0
        new_rows.append(nr2)

    out = pd.concat([keep, pd.DataFrame(new_rows)], ignore_index=True)
    out.to_csv(fp, index=False)
    print(f"[ppc_edge_cost_rule.csv] {len(df)} -> {len(out)} rows (re-keyed off SP_SmartXPro to real DAD nodes)")


# ---------------------------------------------------------------------------
# 8. lane_assignment.csv -- drop SmartXPro rows (no longer multi-MOM)
# ---------------------------------------------------------------------------
def migrate_lane_assignment():
    fp = path("lane_assignment.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    before = len(df)
    df = df[df["sku_id"] != "SmartXPro"].copy()
    df.to_csv(fp, index=False)
    print(f"[lane_assignment.csv] {before} -> {len(df)} rows (dropped SmartXPro; no longer multi-MOM)")


# ---------------------------------------------------------------------------
# 9. route_master.csv -- region-keyed sku_id split + src_region fix for IN
# ---------------------------------------------------------------------------
def migrate_route_master():
    fp = path("route_master.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    mask = df["sku_id"] == "SmartXPro"
    new_sku = df.loc[mask, "region"].map(region_to_sku)
    df.loc[mask, "sku_id"] = new_sku
    # IN-side lane now originates in India, not China
    in_rows = mask & (new_sku == SKU_IN)
    df.loc[in_rows, "src_region"] = "IN"
    df.to_csv(fp, index=False)
    print(f"[route_master.csv] relabeled {int(mask.sum())} SmartXPro rows (AMER lane src_region CN->IN)")


# ---------------------------------------------------------------------------
# 10. edge_cost_master.csv -- add IN->AMER lane per scenario (route_master's
#     new SmartXPro_IN/AMER row needs a matching (src=IN,dst=AMER) profile).
# ---------------------------------------------------------------------------
def migrate_edge_cost_master():
    fp = path("edge_cost_master.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    cn_amer = df[(df["src_region"] == "CN") & (df["dst_region"] == "AMER")].copy()
    if cn_amer.empty:
        print("[edge_cost_master.csv] no CN->AMER baseline rows found; skipped")
        return
    already = ((df["src_region"] == "IN") & (df["dst_region"] == "AMER")).any()
    if already:
        print("[edge_cost_master.csv] IN->AMER rows already present; skipped")
        return
    in_amer = cn_amer.copy()
    in_amer["src_region"] = "IN"
    in_amer["src_currency"] = "USD"
    in_amer["notes"] = in_amer["notes"].astype(str) + " [SmartXPro_IN: AssemblyIN(India) origin, same $ magnitude as CN baseline pending real India-tariff-schedule review]"
    out = pd.concat([df, in_amer], ignore_index=True)
    out.to_csv(fp, index=False)
    print(f"[edge_cost_master.csv] {len(df)} -> {len(out)} rows (added IN->AMER lane per scenario, mirrors CN->AMER $ magnitude)")


# ---------------------------------------------------------------------------
# 11. node_master.csv -- light touch: FoundryTW's sku_id tag -> SmartXPro_CN
# ---------------------------------------------------------------------------
def migrate_node_master():
    fp = path("node_master.csv")
    df = pd.read_csv(fp, keep_default_na=False)
    mask = df["sku_id"] == "SmartXPro"
    df.loc[mask, "sku_id"] = SKU_CN  # FoundryTW row (CN-chain component)
    df.to_csv(fp, index=False)
    print(f"[node_master.csv] relabeled {int(mask.sum())} SmartXPro row(s) -> {SKU_CN}")


# ---------------------------------------------------------------------------
def main():
    if already_migrated():
        print("Already migrated (no 'SmartXPro' sku_id remaining in sku_master.csv). No-op.")
        return

    migrate_sc_tree_master()
    migrate_region_keyed_sku("sku_master.csv")
    migrate_region_keyed_sku("demand_forecast.csv")
    migrate_region_keyed_sku("inventory_master.csv")

    migrate_node_keyed("capacity_plan.csv", "sku_id", "node_name")
    migrate_node_keyed_with_sp("node_cost_master.csv", "sku_id", "node_name")
    migrate_node_keyed("ppc_supplier_cost.csv", "product_id", "supplier_node")
    migrate_node_keyed("ppc_transfer_price_rule.csv", "product_id", "mom_node")
    migrate_node_keyed("ppc_node_cost_rule.csv", "product_id", "node_id")

    migrate_node_keyed_with_sp("ppc_node_profit_zone.csv", "product_id", "node_id")
    migrate_ppc_profit_zone_rule()
    migrate_ppc_market_price()
    migrate_ppc_tariff_rule()
    migrate_ppc_edge_cost_rule()
    migrate_lane_assignment()

    migrate_route_master()
    migrate_edge_cost_master()
    migrate_node_master()

    print("\nDone. SmartXPro -> SmartXPro_CN / SmartXPro_IN split complete.")


if __name__ == "__main__":
    main()
