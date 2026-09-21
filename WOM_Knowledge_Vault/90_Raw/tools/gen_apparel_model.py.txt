#!/usr/bin/env python3
"""
gen_apparel_model.py

Generates ALL CSV files for data/sample/apparel-us-2026/
(Phase 1 + Phase 2, both brands, 8 seasonal SKUs each.)

Owner rationale (2026-07-10, multiple revisions same day):
  1. A real apparel business defines products per season (e.g. "fall coat",
     "spring pants"), each SKU's demand concentrated in its own multi-week
     window and near-zero outside it -- not one SKU with a mild year-round
     sinusoidal wobble. Expressed as 8 distinct product_name values per
     brand (S1..S8).
  2. While verifying Phase 1 (Apparel_Import / H&M-inspired, offshore
     fabless), a qty-scaling bug was found and fixed in the core PPC engine
     (wom/ppc/*.py) -- unrelated to this script, see git history / the
     Coding Request Letters for details.
  3. Also while verifying Phase 1, a cost double-count was found: the
     $19.0/unit Factory_Import_CN transfer price was documented as an
     all-in CIF price (fabric-inclusive), but Fabric_CN's $6.5/unit was
     ALSO billed as an independent PPC forward cost. Fixed by zeroing
     Fabric_CN's PPC-side cost and adding ppc_node_cost_rule.csv (which
     did not exist yet for this scenario) with Factory_Import_CN's full
     CIF value as a conversion_cost line + DC_Import_Buffer's warehouse fee.
  4. While designing Phase 2 (Apparel_Local / Zara-inspired), a further
     bug was found in THIS script's own Phase-1-era edge_cost_rule.csv:
     the inbound freight rows were keyed to edge_id
     "Factory_Import_CN->SP_Apparel_Import" / "SP_Apparel_Import->DC_Import_Buffer",
     but wom/ppc/ppc_tariff.py actually looks up costs on
     "{mom_node}->{first_dad_node}" (skipping the supply_point bridge node
     entirely, since supply_point is not a "dad"-type node and therefore
     never appears in dad_nodes_chain). Those two rows were consequently
     NEVER matched -- freight cost was silently $0 for the whole Phase 1
     verification. Fixed here for both brands by using the correct
     "{FACTORY}->{DC}" edge_id.
  5. Phase 2 (Apparel_Local) is modeled on Zara/Inditex's ACTUAL operating
     model (vertically-integrated Spain-based production, Arteixo
     distribution hub, twice-weekly air-freighted store replenishment) per
     owner instruction, NOT a fictional Western-Hemisphere nearshoring
     relocation (an earlier draft direction that was rejected -- see
     hm-apparel-research.md section 8 for the full research trail).

This script generates every CSV in the model folder programmatically (see
CLAUDE.md's documented "manual probe scripts keep disappearing" problem --
committing this generator to the repo avoids that).

Usage (run from the repository root):
    python tools/gen_apparel_model.py

This script is intentionally standalone: it does not import any wom.* engine
module, so it carries none of the large-file risk documented in CLAUDE.md for
reading app.py-scale files through a Linux/bash-mounted path.
"""

import csv
import datetime
import math
import os

OUT_DIR = os.path.join("data", "sample", "apparel-us-2026")

NUM_WEEKS = 105  # 2026 has 53 ISO weeks; 105 weeks reaches 2027-W52 from 2026-W01.
START_DATE = datetime.date.fromisocalendar(2026, 1, 1)

REGIONS = {
    "TX": 1200,
    "CA": 1100,
    "NY": 900,
}

# ---------------------------------------------------------------------------
# 8 seasons across a nominal 52-week year (2026's extra 53rd week folds into S8)
# (suffix, jp/en label, start_week_of_year, end_week_of_year)
# Identical calendar for both brands -- same market, same product cycle,
# only the supply chain differs.
# ---------------------------------------------------------------------------
SEASONS = [
    ("S1", "Pre-Spring / 初春物", 1, 7),
    ("S2", "Spring / 春物", 8, 14),
    ("S3", "Early Summer / 初夏物", 15, 20),
    ("S4", "High Summer / 盛夏物", 21, 27),
    ("S5", "Early Fall / 初秋物", 28, 33),
    ("S6", "Fall Coats / 秋物・コート", 34, 40),
    ("S7", "Early Winter / 初冬物", 41, 46),
    ("S8", "Winter Holiday / 真冬・ホリデー", 47, 53),
]

# ---------------------------------------------------------------------------
# Brand definitions -- one dict per brand, consumed by every gen_* function
# below via a loop. Adding a 3rd brand later only requires appending here.
# ---------------------------------------------------------------------------
BRANDS = [
    {
        "key": "Import",
        # NOTE (2026-07-11 rename): brand SKU/bridge-node names changed from
        # Apparel_Import/SP_Apparel_Import to Apparel_Outsourced/
        # SP_Apparel_Outsourced (clearer, non-Incoterm-confusing terminology
        # for readers of the note article). Node names below (factory/fabric/
        # dc, "Import"-suffixed) were intentionally left unchanged -- only the
        # brand-level SKU prefix and HQ bridge node were renamed.
        "prefix": "Apparel_Outsourced",
        "suffix": "I",                     # sales node suffix: Sales_US_TX_I
        "factory": "Factory_Import_CN",
        "fabric": "Fabric_CN",
        "dc": "DC_Import_Buffer",
        "sp": "SP_Apparel_Outsourced",
        "factory_country": "CN",
        "hs_code": 6109100000,
        # Lead times (weeks)
        "lt_fabric": 3, "lt_factory": 8, "lt_dc": 4,
        "lt_store": {"TX": 1, "CA": 1, "NY": 2},
        "sku_lead_time_wks": {"TX": 12, "CA": 12, "NY": 14},
        "ss_days": 21,
        # Capacity
        "cap_factory": 15000, "cap_factory_closure": 1500,
        "closure_weeks": {"2026-W07", "2026-W08", "2027-W06", "2027-W07"},
        "closure_id_prefix": "CN_NEWYEAR",
        "closure_name": "Chinese New Year",
        # Cost structure: fabric is a REAL PPC cost, but Factory's transfer
        # price is fixed at the all-in CIF value ($19.0, fabric-inclusive)
        # -- so Fabric's PPC-side cost is zeroed to avoid double-counting
        # (see rationale item 3 above). node_cost_master.csv (informational,
        # feeds Management P&L via wom/engine/money.py) still documents the
        # real $6.5 fabric component for readability.
        "fabric_unit_cost": 6.5,
        "fabric_ppc_cost": 0.0,
        "factory_cif_price": 19.0,          # all-in, fabric-inclusive
        "conversion_cost": 19.0,            # == factory_cif_price (Fabric zeroed)
        "transfer_method": "fixed",
        "transfer_margin_rate": 0.0,
        "mom_margin_rate": 0.08,
        "warehouse_cost": 1.0,
        "freight_total": 4.8,               # factory->port + ocean freight, combined
        "tariff_rate": 0.20,                # China, live simulation rate
        "market_price": 49.0,
        "channel_margin_rate": 0.35,
        "edge_scenarios": [
            ("Base", 0.147, "2025年1月時点の平均関税(14.7%)"),
            ("TariffShock2025", 0.20, "2025年後半〜2026年: 中国向け関税20%"),
            ("TariffRelief2026", 0.20, "恒久的に切り上がった床（部分緙和後も高止まり）"),
        ],
    },
    {
        "key": "Local",
        # NOTE (2026-07-11 rename): renamed from Apparel_Local/SP_Apparel_Local
        # to Apparel_Integrated/SP_Apparel_Integrated (see matching note on the
        # "Import" brand dict above).
        "prefix": "Apparel_Integrated",
        "suffix": "L",                     # sales node suffix: Sales_US_TX_L
        "factory": "Factory_Local_ES",
        "fabric": "Fabric_ES",
        "dc": "DC_Local_US",
        "sp": "SP_Apparel_Integrated",
        "factory_country": "ES",
        "hs_code": 6109100000,
        # Lead times (weeks) -- short and stable: vertically-integrated
        # Spain production + air freight (Arteixo hub, twice-weekly store
        # replenishment), per owner instruction (see rationale item 5).
        "lt_fabric": 1, "lt_factory": 1, "lt_dc": 1,
        "lt_store": {"TX": 1, "CA": 1, "NY": 1},
        "sku_lead_time_wks": {"TX": 3, "CA": 3, "NY": 3},
        "ss_days": 7,
        # Capacity
        "cap_factory": 15000, "cap_factory_closure": 1500,
        # European "agosto" summer factory shutdown -- a real, widely
        # documented practice, added as the geographic/cultural counterpart
        # to Apparel_Import's Chinese New Year closure.
        "closure_weeks": {"2026-W32", "2026-W33", "2027-W32", "2027-W33"},
        "closure_id_prefix": "ES_AGOSTO",
        "closure_name": "Spain August Factory Holiday (agosto)",
        # Cost structure: vertically-integrated, so fabric and conversion
        # are kept as two REAL, separate PPC cost lines from the start
        # (the Phase-1 double-count lesson -- see rationale item 3 -- is
        # applied here by construction, not as a later patch).
        "fabric_unit_cost": 7.0,
        "fabric_ppc_cost": 7.0,
        "factory_cif_price": None,          # not used; cost_plus derives it
        "conversion_cost": 10.0,            # conversion ONLY, fabric excluded
        "transfer_method": "cost_plus",
        "transfer_margin_rate": 0.10,
        "mom_margin_rate": 0.10,
        "warehouse_cost": 1.0,
        "freight_total": 7.0,               # domestic ES transport + AIR freight
        "tariff_rate": 0.15,                # EU-US trade deal ceiling, eff. 2026-07-01
        "market_price": 49.0,
        "channel_margin_rate": 0.40,
        "edge_scenarios": [
            ("Base", 0.10, "2025年時点のEU向け平均関税相当(参考値)"),
            ("TariffShock2025", 0.20, "2025年後半〜2026年2月: IEEPA相互関税適用時のピーク水準"),
            ("TariffRelief2026", 0.15, "2026年7月1日発効のEU-US通商合意による包括上限15%"),
        ],
    },
]


def sales_node(brand, region):
    return f"Sales_US_{region}_{brand['suffix']}"


def product_id(brand, suffix):
    return f"{brand['prefix']}_{suffix}"


# ---------------------------------------------------------------------------
# Week helpers
# ---------------------------------------------------------------------------
def week_infos(start_date, num_weeks):
    """Return list of (label, iso_week) for num_weeks consecutive weeks."""
    out = []
    d = start_date
    for _ in range(num_weeks):
        iso_year, iso_week, _ = d.isocalendar()
        out.append((f"{iso_year}-W{iso_week:02d}", iso_week))
        d += datetime.timedelta(days=7)
    return out


def season_weight(iso_week, start, end):
    """Raised-sine bump: 0 at the season edges, 1 at mid-season."""
    if not (start <= iso_week <= end):
        return 0.0
    span = max(end - start, 1)
    t = (iso_week - start) / span
    return math.sin(math.pi * t)


# ---------------------------------------------------------------------------
# CSV generators (each loops over BRANDS x SEASONS)
# ---------------------------------------------------------------------------
def gen_sku_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "sku_name", "region", "uom", "unit_cost",
                    "safety_stock_wks", "lead_time_wks", "order_multiple",
                    "max_order_qty", "shelf_life_wks", "active",
                    "selling_price", "dso_wks", "dpo_wks"])
        for brand in BRANDS:
            for suffix, label, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                for region in REGIONS:
                    lt = brand["sku_lead_time_wks"][region]
                    # unit_cost: the cost basis used by the (separate,
                    # simpler) Management P&L engine (wom/engine/money.py:
                    # COGS = demand_fulfilled x unit_cost). Must represent
                    # the SAME total acquisition cost the PPC engine uses at
                    # MOM, for consistency between the two engines:
                    #   - fixed method (Import): factory_cif_price already
                    #     IS that total cost (CIF-inclusive transfer price).
                    #   - cost_plus method (Local): the transfer price is
                    #     NOT a fixed CSV value, so we use the accumulated
                    #     fabric + conversion cost (matching ppc_transfer.py's
                    #     MOM_accumulated_unit_cost, pre-margin) instead of
                    #     conversion_cost alone. Using conversion_cost alone
                    #     silently dropped Fabric_ES from Management Cogs,
                    #     inflating Management Gross Margin% to 79.6% vs the
                    #     PPC engine's (correct, broader) 43.3% -- found while
                    #     verifying apparel-us-2026 Phase 2 (2026-07-11).
                    unit_cost = (
                        brand["factory_cif_price"]
                        if brand["factory_cif_price"] is not None
                        else brand["fabric_unit_cost"] + brand["conversion_cost"]
                    )
                    w.writerow([pid, f"{pid} ({label}, US Market)", region, "EA",
                                unit_cost,
                                3, lt, 100, 0, 8, "True",
                                brand["market_price"], 4, 90])


def gen_node_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "node_name", "node_type", "lat", "lon",
                    "sku_id", "region", "description"])
        coords = {
            "CN": (31.23, 121.47), "ES": (43.36, -8.41),  # Shanghai / A Coruna (Arteixo)
        }
        lats = {"TX": (32.78, -96.80), "CA": (34.05, -118.24), "NY": (40.71, -74.01)}
        for brand in BRANDS:
            country = brand["factory_country"]
            lat, lon = coords[country]
            first_pid = product_id(brand, SEASONS[0][0])
            brand_label = "H&M型 輸入調達" if brand["key"] == "Import" else "Zara型 垂直統合"
            w.writerow([brand["sp"], f"{brand['sp']}（{brand_label}本部）",
                        "procurement", lat, lon, "", country,
                        f"{brand_label}の調達本部"])
            w.writerow([brand["factory"],
                        "契約工場（中国）" if brand["key"] == "Import" else "自社工場（スペイン）",
                        "mother_plant", lat, lon, first_pid, country,
                        f"{'ファブレス契約工場' if brand['key'] == 'Import' else '垂直統合・自社工場'}（8季節共通）"])
            w.writerow([brand["fabric"],
                        "生地サプライヤー（中国）" if brand["key"] == "Import" else "生地サプライヤー（スペイン）",
                        "sku_supplier", lat, lon, first_pid, country,
                        "委託先向け生地調達（8季節共通）" if brand["key"] == "Import"
                        else "自社/系列向け生地調達（8季節共通）"])
            dc_desc = ("輸入バッファ倉庫 LT長め（8季節共通）" if brand["key"] == "Import"
                       else "航空輸送受入DC LT短め（8季節共通）")
            w.writerow([brand["dc"],
                        "輸入バッファDC（米国内）" if brand["key"] == "Import" else "航空輸送受入DC（米国内）",
                        "region_dc", 33.75, -118.19, "", "CA", dc_desc])
            for region, (lat2, lon2) in lats.items():
                label = "輸入品" if brand["key"] == "Import" else "直営店（航空便補充）"
                w.writerow([sales_node(brand, region), f"{region}店舗（{label}）",
                            "marketing", lat2, lon2, "", region, f"{label}小売（8季節共通）"])


def gen_sc_tree_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_name", "parent_node", "product_name", "node_type", "side",
                    "lt_wks", "cpu_size", "region", "ss_days",
                    "buffering_stock_flag", "description"])
        for brand in BRANDS:
            SP, FACTORY, FABRIC, DC = brand["sp"], brand["factory"], brand["fabric"], brand["dc"]
            for suffix, label, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                w.writerow([SP, "", pid, "supply_point", "outbound", 0, 1, "", 0, 0,
                            f"Supply Point bridge ({pid})"])
                w.writerow([DC, SP, pid, "dad", "outbound", brand["lt_dc"], 1, "US",
                            brand["ss_days"], 1, f"{'輸入バッファDC' if brand['key'] == 'Import' else '航空輸送受入DC'} ({label})"])
                for region in REGIONS:
                    lt = brand["lt_store"][region]
                    w.writerow([sales_node(brand, region), DC, pid, "leaf_out", "outbound",
                                lt, 1, region, 0, 0, f"{region}店舗 ({label})"])
                w.writerow([FACTORY, "", pid, "mom", "inbound", brand["lt_factory"], 1,
                            brand["factory_country"], 0, 0,
                            f"{'契約工場' if brand['key'] == 'Import' else '自社工場'} ({label})"])
                w.writerow([FABRIC, FACTORY, pid, "leaf_in", "inbound", brand["lt_fabric"], 1,
                            brand["factory_country"], 0, 0, f"生地調達 ({label})"])


def gen_lane_assignment(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "leaf_node_name", "mom_node_id", "priority"])
        for brand in BRANDS:
            for suffix, _, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                for region in REGIONS:
                    w.writerow([pid, sales_node(brand, region),
                                f"IN:mom:{brand['factory']}:{pid}", 1])


def gen_route_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "region", "src_region", "dst_region", "hs_code",
                    "product_type", "assembly_cost_usd_per_lot"])
        for brand in BRANDS:
            for suffix, _, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                for region in REGIONS:
                    w.writerow([pid, region, brand["factory_country"], "US",
                                brand["hs_code"], "finished_goods", 0])


def gen_edge_cost_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "src_region", "dst_region", "tariff_rate", "fx_rate",
                    "src_currency", "dst_currency", "freight_usd_per_lot", "notes"])
        for brand in BRANDS:
            for scenario, rate, note in brand["edge_scenarios"]:
                w.writerow([scenario, brand["factory_country"], "US", rate, 1.0,
                            "USD", "USD", brand["freight_total"], note])


def gen_ppc_tariff_rule(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["edge_id", "from_country", "to_country", "product_id", "hs_code",
                    "tariff_rate", "tariff_basis"])
        for brand in BRANDS:
            # NOTE (rationale item 4): edge_id must be "{FACTORY}->{DC}" -- the
            # actual dad-type node -- NOT routed through the supply_point
            # bridge node, which wom/ppc/ppc_tariff.py never sees as a "dad".
            for suffix, _, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                w.writerow([f"{brand['factory']}->{brand['dc']}", brand["factory_country"],
                            "US", pid, brand["hs_code"], brand["tariff_rate"], "transfer_price"])


def gen_ppc_transfer_price_rule(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mom_node", "product_id", "method", "margin_rate", "fixed_price", "currency"])
        for brand in BRANDS:
            for suffix, _, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                if brand["transfer_method"] == "fixed":
                    w.writerow([brand["factory"], pid, "fixed", 0.0,
                                brand["factory_cif_price"], "USD"])
                else:
                    w.writerow([brand["factory"], pid, "cost_plus",
                                brand["transfer_margin_rate"], 0.0, "USD"])


def gen_node_cost_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "node_name", "selling_price_per_lot", "unit_cost_per_lot", "note"])
        for brand in BRANDS:
            SP, FACTORY, FABRIC, DC = brand["sp"], brand["factory"], brand["fabric"], brand["dc"]
            fabric_cost = brand["fabric_unit_cost"]
            if brand["factory_cif_price"] is not None:
                factory_cost = brand["factory_cif_price"]
                factory_note_suffix = "CIF価格（生地込み）"
            else:
                # cost_plus: informational factory-gate cost = accumulated
                # (fabric + conversion) x (1 + margin_rate), matching what
                # ppc_transfer.py actually computes at runtime.
                accumulated = fabric_cost + brand["conversion_cost"]
                factory_cost = round(accumulated * (1.0 + brand["transfer_margin_rate"]), 2)
                factory_note_suffix = "工場出荷価格（生地+加工費+マージン、cost_plus方式）"
            dc_cost = round(
                factory_cost * (1.0 + brand["tariff_rate"]) + brand["freight_total"]
                + brand["warehouse_cost"], 2
            )
            for suffix, label, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                w.writerow([pid, FABRIC, round(fabric_cost * 1.15, 2), fabric_cost,
                            f"生地 USD/着 ({label})"])
                w.writerow([pid, FACTORY, round(factory_cost * 1.1, 2), factory_cost,
                            f"{factory_note_suffix} ({label})"])
                w.writerow([pid, SP, factory_cost, factory_cost, "Supply Point pass-through"])
                w.writerow([pid, DC, round(dc_cost * 1.1, 2), dc_cost,
                            f"{'輸入' if brand['key'] == 'Import' else '航空輸送受入'}バッファDC "
                            f"関税({brand['tariff_rate']:.0%})+輸送費込み ({label})"])
                for region in REGIONS:
                    extra = 0.3 if region == "NY" else 0.0
                    store_cost = round(dc_cost * 0.5 + extra, 1)
                    w.writerow([pid, sales_node(brand, region), brand["market_price"], store_cost,
                                f"{region}店舗販売価格（{'輸入品' if brand['key'] == 'Import' else '直営店'}、{label}）"])


def gen_ppc_edge_cost_rule(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["edge_id", "product_id", "cost_type", "basis", "rate", "fixed_amount", "currency"])
        for brand in BRANDS:
            for suffix, _, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                # Single edge, correctly keyed to {FACTORY}->{DC} (see
                # gen_ppc_tariff_rule note). Combines domestic transport to
                # port/airport + international freight into one fixed fee:
                # Import = ocean freight ($4.8/unit), Local = AIR freight
                # ($7.0/unit, deliberately higher -- the speed/cost tradeoff
                # this case is designed to show).
                w.writerow([f"{brand['factory']}->{brand['dc']}", pid, "logistics_cost",
                            "per_lot", 0.0, brand["freight_total"], "USD"])


def gen_ppc_node_cost_rule(path):
    """
    ppc_node_cost_rule.csv -- Factory conversion_cost + DC warehouse_cost
    for both brands. See module docstring rationale item 3.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "product_id", "cost_type", "basis", "rate", "fixed_amount", "currency", "note"])
        for brand in BRANDS:
            for suffix, label, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                if brand["factory_cif_price"] is not None:
                    conv_note = f"CIF価格（生地込み、fixed transfer priceと同額） ({label})"
                else:
                    conv_note = f"加工費のみ（生地代${brand['fabric_ppc_cost']}は別立て、cost_plus方式） ({label})"
                w.writerow([brand["factory"], pid, "conversion_cost", "per_lot", 0.0,
                            brand["conversion_cost"], "USD", conv_note])
                w.writerow([brand["dc"], pid, "warehouse_cost", "per_lot", 0.0,
                            brand["warehouse_cost"], "USD",
                            f"{'輸入' if brand['key'] == 'Import' else '航空輸送受入'}バッファDC 運営・ハンドリング費 ({label})"])


def gen_ppc_node_profit_zone(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "product_id", "profit_zone_role", "country"])
        for brand in BRANDS:
            for suffix, _, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                w.writerow([brand["fabric"], pid, "SUPPLIER_COST_BASE", brand["factory_country"]])
                w.writerow([brand["factory"], pid, "MOM_PLANT_PROFIT", brand["factory_country"]])
                w.writerow([brand["sp"], pid, "OPERATION_NODE_COST_BASE", brand["factory_country"]])
                w.writerow([brand["dc"], pid, "OPERATION_NODE_COST_BASE", "US"])
                for region in REGIONS:
                    w.writerow([sales_node(brand, region), pid, "OUTBOUND_CHANNEL_PROFIT", "US"])


def gen_ppc_profit_zone_rule(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["profit_zone_role", "product_id", "profit_type", "basis", "rate", "fixed_amount"])
        for brand in BRANDS:
            for suffix, _, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                w.writerow(["OUTBOUND_CHANNEL_PROFIT", pid, "channel_margin", "market_price",
                            brand["channel_margin_rate"], 0])
                w.writerow(["MOM_PLANT_PROFIT", pid, "mom_margin", "transfer_price",
                            brand["mom_margin_rate"], 0])
                w.writerow(["SUPPLIER_COST_BASE", pid, "supplier_cost", "transfer_price", 1.00, 0])


def gen_holiday_calendar(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["holiday_id", "holiday_name", "start_week", "end_week",
                    "node_name", "effect", "value"])
        for brand in BRANDS:
            weeks_sorted = sorted(brand["closure_weeks"])
            # Pair up consecutive weeks into (start, end) ranges per year.
            years = sorted(set(w_[:4] for w_ in weeks_sorted))
            for yr in years:
                yr_weeks = sorted(w_ for w_ in weeks_sorted if w_.startswith(yr))
                if not yr_weeks:
                    continue
                w.writerow([f"{brand['closure_id_prefix']}_{yr}",
                            f"{brand['closure_name']} {yr}",
                            yr_weeks[0], yr_weeks[-1], brand["factory"],
                            "supply_closure", 1500.0])


def gen_inventory_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "region", "on_hand_qty", "on_order_qty", "week"])
        # Only the season active at 2026-W01 (S1) starts with meaningful stock;
        # the other 7 seasonal SKUs have not launched yet at the simulation start.
        for brand in BRANDS:
            for suffix, _, start, _ in SEASONS:
                pid = product_id(brand, suffix)
                active_at_start = (start <= 1)
                for region, peak in REGIONS.items():
                    on_hand = round(peak * 0.4) if active_at_start else 0
                    on_order = round(peak * 0.2) if active_at_start else 0
                    w.writerow([pid, region, on_hand, on_order, "2026-W01"])


def gen_ppc_supplier_cost(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["supplier_node", "product_id", "week", "purchase_price", "currency"])
        for brand in BRANDS:
            for suffix, _, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                # Import: Fabric is zeroed on the PPC side (not removed) to
                # avoid double-counting against Factory's fabric-inclusive
                # CIF price (rationale item 3). Local: Fabric is a REAL,
                # separate cost from the start (conversion_cost excludes it).
                w.writerow([brand["fabric"], pid, "2026-W01", brand["fabric_ppc_cost"], "USD"])
                # Factory is not in either brand's PPC supplier list (mom_node,
                # not leaf_in) -- this row is informational only.
                w.writerow([brand["factory"], pid, "2026-W01",
                            brand["factory_cif_price"] if brand["factory_cif_price"] is not None
                            else brand["fabric_unit_cost"] + brand["conversion_cost"],
                            "USD"])


def gen_ppc_market_price(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["market_node", "product_id", "week", "market_price", "currency"])
        for brand in BRANDS:
            for suffix, _, _, _ in SEASONS:
                pid = product_id(brand, suffix)
                for region in REGIONS:
                    w.writerow([sales_node(brand, region), pid, "2026-W01",
                                brand["market_price"], "USD"])


def gen_demand_forecast(weeks, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "region", "week", "quantity"])
        for label, iso_week in weeks:
            for brand in BRANDS:
                for suffix, _, start, end in SEASONS:
                    weight = season_weight(iso_week, start, end)
                    if weight <= 0.0:
                        continue
                    pid = product_id(brand, suffix)
                    for region, peak in REGIONS.items():
                        qty = round(peak * weight)
                        if qty > 0:
                            w.writerow([pid, region, label, qty])


def gen_capacity_plan(weeks, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "node_name", "week", "max_supply", "source"])
        for label, iso_week in weeks:
            for brand in BRANDS:
                for suffix, _, start, end in SEASONS:
                    weight = season_weight(iso_week, start, end)
                    if weight <= 0.0:
                        continue
                    pid = product_id(brand, suffix)
                    if label in brand["closure_weeks"]:
                        factory_cap = brand["cap_factory_closure"]
                        factory_note = f"{brand['closure_name']} reduced capacity (10% of normal)"
                    else:
                        factory_cap = brand["cap_factory"]
                        factory_note = "Factory weekly capacity (shared across seasons)"
                    w.writerow([pid, brand["factory"], label, factory_cap, factory_note])
                    w.writerow([pid, brand["fabric"], label, 50000,
                                "Fabric supply, effectively unconstrained"])
                    w.writerow([pid, brand["dc"], label, 25000, "DC throughput"])


def gen_fx_rate(weeks, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["week", "currency", "base_currency", "rate"])
        for label, _ in weeks:
            w.writerow([label, "USD", "USD", 1.0])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    weeks = week_infos(START_DATE, NUM_WEEKS)
    all_products = [product_id(b, s[0]) for b in BRANDS for s in SEASONS]
    print(f"Generating {NUM_WEEKS} weeks: {weeks[0][0]} .. {weeks[-1][0]}")
    print(f"Brands: {[b['key'] for b in BRANDS]}")
    print(f"Products ({len(all_products)}): {all_products}")

    gen_sku_master(os.path.join(OUT_DIR, "sku_master.csv"))
    gen_node_master(os.path.join(OUT_DIR, "node_master.csv"))
    gen_sc_tree_master(os.path.join(OUT_DIR, "sc_tree_master.csv"))
    gen_lane_assignment(os.path.join(OUT_DIR, "lane_assignment.csv"))
    gen_route_master(os.path.join(OUT_DIR, "route_master.csv"))
    gen_edge_cost_master(os.path.join(OUT_DIR, "edge_cost_master.csv"))
    gen_ppc_tariff_rule(os.path.join(OUT_DIR, "ppc_tariff_rule.csv"))
    gen_ppc_transfer_price_rule(os.path.join(OUT_DIR, "ppc_transfer_price_rule.csv"))
    gen_node_cost_master(os.path.join(OUT_DIR, "node_cost_master.csv"))
    gen_ppc_edge_cost_rule(os.path.join(OUT_DIR, "ppc_edge_cost_rule.csv"))
    gen_ppc_node_cost_rule(os.path.join(OUT_DIR, "ppc_node_cost_rule.csv"))
    gen_ppc_node_profit_zone(os.path.join(OUT_DIR, "ppc_node_profit_zone.csv"))
    gen_ppc_profit_zone_rule(os.path.join(OUT_DIR, "ppc_profit_zone_rule.csv"))
    gen_holiday_calendar(os.path.join(OUT_DIR, "holiday_calendar.csv"))
    gen_inventory_master(os.path.join(OUT_DIR, "inventory_master.csv"))
    gen_ppc_supplier_cost(os.path.join(OUT_DIR, "ppc_supplier_cost.csv"))
    gen_ppc_market_price(os.path.join(OUT_DIR, "ppc_market_price.csv"))
    gen_demand_forecast(weeks, os.path.join(OUT_DIR, "demand_forecast.csv"))
    gen_capacity_plan(weeks, os.path.join(OUT_DIR, "capacity_plan.csv"))
    gen_fx_rate(weeks, os.path.join(OUT_DIR, "ppc_fx_rate.csv"))

    print("Done. Generated all 20 CSV files for apparel-us-2026 "
          f"({len(BRANDS)} brands x 8 seasons = {len(all_products)} SKUs).")


if __name__ == "__main__":
    main()
