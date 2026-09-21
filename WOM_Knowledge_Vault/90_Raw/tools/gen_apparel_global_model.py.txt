#!/usr/bin/env python3
"""
gen_apparel_global_model.py

Generates ALL CSV files for data/sample/apparel-global-2028-2029/
(both brands: Apparel_Offshore / Apparel_Vertical, single SKU each,
US + JP markets, 2028-2029.)

Origin / rationale:
    This case re-implements a concept originally sketched by a separate AI
    ("Grok") in a chat with the owner -- an offshore multi-tier sourcing
    brand (China fabric -> Bangladesh dyeing -> Vietnam trim -> Bangladesh
    garment assembly) vs. a near-shore vertically-integrated brand (Spain
    fabric -> Portugal dyeing -> Morocco trim -> Portugal garment assembly),
    both exporting to the SAME two markets (US + JP). Grok's own CSV output
    used column names/structures incompatible with WOM's real engine and was
    missing ~12 required files; this script rebuilds the concept from
    scratch against the actual schema. See
    requests/apparel-global-2028-2029-request-letter.md for the full design
    letter (Coding Request Letter format, per AGAPI project convention).

Key design decisions (see the request letter for full detail):
  1. Single SKU per brand (Apparel_Offshore / Apparel_Vertical), NOT
     apparel-us-2026's 8-seasonal-SKU split. AW (autumn/winter) demand peak,
     baseline demand outside the peak window (never zero -- year-round
     product, unlike apparel-us-2026's seasonal product-swap design).
  2. Multi-tier InBound MOM chain (Fabric[leaf_in] -> Dyeing[mom] ->
     Trim[mom] -> Garment[mom, terminal]), reusing the multi-tier InBound
     chain capability verified in data/sample/smartx-2027-2029 (WaferFab ->
     FoundryTW -> Buffer_Chip_TW -> AssemblyCN pattern). Confirmed via
     direct code reading (wom/ppc/ppc_forward.py Step 1b) that each
     intermediate "mom" tier contributes ONLY ppc_node_cost_rule.csv
     entries (conversion_cost) plus an inbound edge_cost_rule.csv entry for
     the hop into it -- NEVER a ppc_supplier_cost.csv or
     ppc_transfer_price_rule.csv entry (those are reserved for leaf_in and
     the terminal mom_node respectively). transfer_price_rule.csv rows seen
     on smartx's intermediate tiers (e.g. FoundryTW_g1) were confirmed dead/
     unused data by reading wom/ppc/ppc_transfer.py directly -- it only ever
     looks up the terminal mom_node's rule -- so this script does NOT emit
     transfer_price_rule rows for Dyeing/Trim tiers.
  3. Multi-tier OutBound DAD chain (supply_point -> FG_WH[regional bonded
     warehouse, dad] -> DC_US or DC_JP[market DC, dad] -> Retail[leaf_out]),
     reusing the multi-tier OutBound chain capability also verified on
     smartx (SP_SmartX -> DC_AMER/EMEA/APAC -> Retail_*). Read
     wom/ppc/ppc_tariff.py directly to confirm the exact edge_id/tariff
     placement rule for a 2-tier DAD chain:
       - Tariff can ONLY be registered on two edges: mom_node->chain[0]
         (inbound) or chain[-1]->channel (outbound). NOT on inter-DAD
         edges (chain[i]->chain[i+1]) -- ppc_tariff.py's inter-DAD loop
         only reads logistics_cost/insurance_cost, never tariff_rate.
       - Since our FG_WH tier is a domestic (same-country-as-garment-
         assembly) staging warehouse, NOT the cross-border edge, this
         script places the customs duty on the OUTBOUND edge
         (last_dad->channel, e.g. "DC_US_Offshore->Retail_US_Offshore"),
         not the inbound edge (unlike apparel-us-2026, which had only one
         DAD tier and therefore put its tariff on
         "{factory}->{single_dc}"). This is an equally realistic model of
         customs practice (duty collected at destination-market customs
         clearance, i.e. DDP-style) and was NOT a design choice available
         to apparel-us-2026's simpler 1-tier-DAD topology.
       - International ocean/air freight (the actual cross-border
         transport cost) is placed on the INTER-DAD edge
         (FG_WH_XX->DC_market_XX), which IS read for logistics_cost.
  4. FX: base_currency=USD throughout (money.py, the Management/narrow-GM
     engine, has NO currency-conversion logic at all -- confirmed by
     grepping wom/engine/money.py for "currency": zero matches. So every
     sku_master.csv selling_price/unit_cost value, including the JP-region
     row, must already be expressed in USD-equivalent terms for the
     Management panel to report sensibly; the Management panel is
     therefore, BY DESIGN, currency/FX-blind for this case -- a further,
     genuine demonstration of the project's recurring "dual-scope" theme
     (Management = narrow GM, currency-naive; PPC = broad GM, currency-
     aware). Real JP-market FX exposure appears ONLY in the PPC engine, via
     ppc_market_price.csv's JPY-denominated Retail_JP_* rows converted
     through ppc_fx_rate.csv (read by wom/ppc/ppc_fx.py's FXConverter).
     ppc_fx_rate.csv itself has NO scenario dimension (just week/currency/
     base_currency/rate) -- confirmed by reading ppc_fx.py directly -- so
     a Base/StrongYen/WeakYen comparison cannot be expressed as a single
     static table the way Tariff scenarios are (edge_cost_master.csv DOES
     have a scenario column, read by wom/engine/landed_cost.py, but its
     fx_rate field only converts USD-quoted freight/assembly costs -- it
     has no path to JP-market REVENUE conversion). This script therefore
     generates ppc_fx_rate.csv with a single Base-case JPY/USD assumption
     for the live simulation; the FX scenario comparison (Base/StrongYen/
     WeakYen) is instead demonstrated via a separate headless verification
     script that reruns the PPC engine with alternate fx_rate values (see
     data/sample/apparel-global-2028-2029/verify/verify_fx_scenarios.py),
     exactly mirroring the rigor already established by apparel-us-2026's
     exercises (data/sample/apparel-us-2026/exercises/) rather than
     inventing a fictitious "scenario" column on a file that doesn't
     structurally support one.
  5. Tariff scenario comparison (Base/TariffEscalation2028/
     TariffRelief2029) reuses edge_cost_master.csv's existing scenario
     column exactly as apparel-us-2026 did for its
     Base/TariffShock2025/TariffRelief2026 comparison -- zero new engine
     code required. Rates are grounded in real trade-policy asymmetries:
     Bangladesh has no US GSP benefit for apparel (historically ~15-17%
     average duty) but DOES receive Japan's LDC (Least Developed Country)
     duty preference (near-zero); the EU-Japan EPA has phased out most
     apparel tariffs, while EU-US apparel tariffs remain in the ~10-15%
     range absent a new trade deal.
  6. Demand ramp-up (added after first GUI verification pass, see
     ramp_factor() docstring below): demand is never zero (year-round
     product) but ramps from 0 to full baseline over each brand's own
     upstream InBound lead time, so the multi-tier pipeline has a
     realistic "launch runway" instead of an impossible day-1 backlog.

This script generates every CSV in the model folder programmatically,
following the same "commit a generator, don't hand-edit CSVs" convention
established by tools/gen_apparel_model.py.

Usage (run from the repository root):
    python tools/gen_apparel_global_model.py
"""

import csv
import datetime
import math
import os

OUT_DIR = os.path.join("data", "sample", "apparel-global-2028-2029")

NUM_WEEKS = 106  # 2028-W01 .. past 2029-W52, trimmed to exact weeks below.
START_DATE = datetime.date.fromisocalendar(2028, 1, 1)

MARKETS = {
    "US": 1500,
    "JP": 800,
}

# AW (autumn/winter) demand peak window, ISO week-of-year.
SEASON_START, SEASON_END = 36, 48
BASELINE_FRAC = 0.3  # demand outside the peak window never drops to zero

# ---------------------------------------------------------------------------
# Brand definitions
# ---------------------------------------------------------------------------
BRANDS = [
    {
        "key": "Offshore",
        "prefix": "Apparel_Offshore",
        "sp": "SP_Apparel_Offshore",
        # InBound multi-tier chain, leaf-side first
        "fabric": "Fabric_CN", "fabric_country": "CN",
        "dyeing": "Dyeing_BD", "dyeing_country": "BD",
        "trim": "Trim_VN", "trim_country": "VN",
        "garment": "Garment_BD", "garment_country": "BD",
        "lt_fabric": 3, "lt_dyeing": 3, "lt_trim": 2, "lt_garment": 4,
        # OutBound multi-tier chain
        "fg_wh": "FG_WH_BD",
        "dc": {"US": "DC_US_Offshore", "JP": "DC_JP_Offshore"},
        "retail": {"US": "Retail_US_Offshore", "JP": "Retail_JP_Offshore"},
        "lt_fg_wh": 1,
        "lt_dc": {"US": 6, "JP": 4},         # ocean freight BD->US / BD->JP
        "lt_retail": {"US": 1, "JP": 1},
        "ss_days_fg_wh": 21,
        # Capacity
        "cap_garment": 3500, "cap_unconstrained": 50000,
        "cap_fg_wh": 6000, "cap_dc": {"US": 5000, "JP": 3000},
        "closure_weeks": {"2028-W22", "2028-W23", "2029-W22", "2029-W23"},
        "closure_id_prefix": "BD_LABOR",
        "closure_name": "Bangladesh Garment Sector Labor Shortage (seasonal)",
        # Cost structure (USD unless noted)
        "fabric_purchase_price": 5.0,
        "dyeing_conversion_cost": 2.5,
        "trim_conversion_cost": 1.8,
        "garment_conversion_cost": 8.5,
        "transfer_method": "cost_plus", "transfer_margin_rate": 0.10,
        "mom_margin_rate": 0.08,
        "fg_wh_cost": 1.0,
        "dc_cost": {"US": 1.5, "JP": 1.3},
        "dc_sga": {"US": 0.8, "JP": 0.7},
        "intl_freight": {"US": 5.5, "JP": 3.5},   # FG_WH -> market DC (ocean)
        "domestic_freight_inbound": 0.4,           # Garment -> FG_WH (BD domestic)
        "last_mile_freight": {"US": 0.9, "JP": 0.9},  # DC -> Retail
        "tariff_rate": {"US": 0.165, "JP": 0.02},  # live-run rate (Base)
        "selling_price_usd": 52.0,                  # Management engine (USD, both regions)
        "market_price_local": {"US": (52.0, "USD"), "JP": (7900.0, "JPY")},
        "channel_margin_rate": 0.35,
        "edge_scenarios": {
            "US": [
                ("Base", 0.165, "Bangladeshは対米GSP適用外(繊維・アパレル)のため実勢平均関税水準"),
                ("TariffEscalation2028", 0.22, "保護主義的な追加関税シナリオ(仮想)"),
                ("TariffRelief2029", 0.18, "部分緩和シナリオ、恒久分は残存(仮想)"),
            ],
            "JP": [
                ("Base", 0.02, "日本のLDC(後発開発途上国)特恵関税によりBangladesh産はほぼ無税"),
                ("TariffEscalation2028", 0.04, "特恵見直しシナリオ(仮想)"),
                ("TariffRelief2029", 0.02, "特恵維持シナリオ"),
            ],
        },
        "hs_code": 6109100000,
    },
    {
        "key": "Vertical",
        "prefix": "Apparel_Vertical",
        "sp": "SP_Apparel_Vertical",
        "fabric": "Fabric_ES", "fabric_country": "ES",
        "dyeing": "Dyeing_PT", "dyeing_country": "PT",
        "trim": "Trim_MA", "trim_country": "MA",
        "garment": "Garment_PT", "garment_country": "PT",
        "lt_fabric": 1, "lt_dyeing": 1, "lt_trim": 1, "lt_garment": 1,
        "fg_wh": "FG_WH_PT",
        "dc": {"US": "DC_US_Vertical", "JP": "DC_JP_Vertical"},
        "retail": {"US": "Retail_US_Vertical", "JP": "Retail_JP_Vertical"},
        "lt_fg_wh": 1,
        "lt_dc": {"US": 2, "JP": 2},          # air freight PT->US / PT->JP
        "lt_retail": {"US": 1, "JP": 1},
        "ss_days_fg_wh": 7,
        "cap_garment": 2000, "cap_unconstrained": 50000,
        "cap_fg_wh": 4000, "cap_dc": {"US": 4000, "JP": 2500},
        "closure_weeks": {"2028-W32", "2028-W33", "2029-W32", "2029-W33"},
        "closure_id_prefix": "PT_AGOSTO",
        "closure_name": "Iberian August Factory Holiday (agosto)",
        "fabric_purchase_price": 7.5,
        "dyeing_conversion_cost": 2.0,
        "trim_conversion_cost": 1.5,
        "garment_conversion_cost": 11.0,
        "transfer_method": "cost_plus", "transfer_margin_rate": 0.12,
        "mom_margin_rate": 0.10,
        "fg_wh_cost": 1.2,
        "dc_cost": {"US": 1.8, "JP": 1.8},
        "dc_sga": {"US": 1.0, "JP": 1.0},
        "intl_freight": {"US": 8.0, "JP": 11.0},  # FG_WH -> market DC (air)
        "domestic_freight_inbound": 0.3,           # Garment -> FG_WH (PT domestic)
        "last_mile_freight": {"US": 0.9, "JP": 0.9},
        "tariff_rate": {"US": 0.12, "JP": 0.01},
        "selling_price_usd": 62.0,
        "market_price_local": {"US": (62.0, "USD"), "JP": (9300.0, "JPY")},
        "channel_margin_rate": 0.42,
        "edge_scenarios": {
            "US": [
                ("Base", 0.12, "EU-US通商関係、現行の実勢平均関税水準(仮想)"),
                ("TariffEscalation2028", 0.18, "保護主義的な追加関税シナリオ(仮想)"),
                ("TariffRelief2029", 0.14, "新通商合意による部分緩和シナリオ(仮想)"),
            ],
            "JP": [
                ("Base", 0.01, "EU-日EPAによりEU産アパレルの大半は関税撤廃済み(仮想水準)"),
                ("TariffEscalation2028", 0.02, "見直しシナリオ(仮想)"),
                ("TariffRelief2029", 0.01, "EPA維持シナリオ"),
            ],
        },
        "hs_code": 6109100000,
    },
]


def product_id(brand):
    return brand["prefix"]


# ---------------------------------------------------------------------------
# Week helpers
# ---------------------------------------------------------------------------
def week_infos(start_date, num_weeks):
    out = []
    d = start_date
    for _ in range(num_weeks):
        iso_year, iso_week, _ = d.isocalendar()
        out.append((f"{iso_year}-W{iso_week:02d}", iso_year, iso_week))
        d += datetime.timedelta(days=7)
    return out


def trim_weeks_to(weeks, end_label):
    """Trim the week list to stop right after end_label (inclusive)."""
    out = []
    for w in weeks:
        out.append(w)
        if w[0] == end_label:
            break
    return out


def demand_weight(iso_week, start, end, baseline=BASELINE_FRAC):
    """Baseline outside [start,end]; raised-sine bump 1.0 at mid-season."""
    if start <= iso_week <= end:
        span = max(end - start, 1)
        t = (iso_week - start) / span
        bump = math.sin(math.pi * t)
        return baseline + (1.0 - baseline) * bump
    return baseline


def ramp_factor(week_idx, ramp_weeks):
    """
    Linear 0->1 ramp over the simulation's first `ramp_weeks` weeks
    (week_idx is the ABSOLUTE index from simulation start, 0-based --
    NOT the iso-week-of-year used by demand_weight()).

    Rationale (added 2028-07-13, revised twice same day after direct PSI
    verification showed the first two versions of this fix were
    insufficient):

    This model's demand is deliberately never zero (BASELINE_FRAC,
    "year-round product" -- see module docstring), unlike apparel-us-2026's
    seasonal SKUs which start fully dormant and so give their supply chain
    a natural quiet runway before demand ramps up.

    Attempt 1 (WRONG, zero effect): ramped retail demand starting at week 0
    using only the InBound upstream leg (`lt_fabric + lt_dyeing + lt_trim`)
    as `ramp_weeks`. Verified via direct PSI-bucket inspection that this
    had ZERO effect on Garment's Carry-Over -- CO plateaus were bit-for-bit
    identical to the unramped run (5520 / 2070). Root cause: BackwardPlanner
    computes each node's own required-ship date by walking the downstream
    chain's lead time backward from the leaf demand date, so Garment's
    required S at absolute week w reflects retail demand at approximately
    week (w + downstream_lt). Since downstream_lt (lt_fg_wh + lt_dc[mkt] +
    lt_retail[mkt]) is, for this case's brands, >= the upstream-only ramp
    window, the ramp had already fully completed by the time it reached
    Garment via that backward shift.

    Attempt 2 (WRONG, partial effect only): ramped retail demand starting
    at week 0 over the FULL end-to-end lead time (upstream + lt_garment +
    downstream). This reduced Garment's CO plateau (5520->4228, 2070->1811)
    but did not eliminate it, because a ramp that starts at week 0 still
    has SOME nonzero value during weeks [0, upstream_lt) once backward-
    shifted -- a linear ramp is not zero except exactly at its own week 0.

    Correct version (this one): retail demand is held at literal ZERO
    (a genuine "product not yet launched in this market" delay) for the
    first `downstream_lt` weeks, THEN ramped from 0 to full baseline over
    the following `upstream_lt` weeks (this function's `ramp_weeks`
    argument), where `upstream_lt` = lt_fabric+lt_dyeing+lt_trim (the
    material-fill window Garment's own InBound chain needs from a cold
    start -- confirmed via direct PSI inspection that Garment's own P
    cannot start before this many weeks regardless of demand shape, since
    inventory_master.csv cannot seed WIP at intermediate/non-leaf nodes --
    see module docstring rationale item 4). Once backward-shifted by
    downstream_lt, this makes Garment's own required S genuinely zero for
    weeks [0, upstream_lt) and ramp in lockstep with Garment's own P as
    material starts arriving at week upstream_lt -- eliminating the
    startup-transient backlog almost entirely (see gen_demand_forecast()
    for the delay+ramp composition, and verify/README.md for final
    before/after CO numbers).
    """
    if ramp_weeks <= 0:
        return 1.0
    return min(1.0, (week_idx + 1) / ramp_weeks)


# ---------------------------------------------------------------------------
# CSV generators
# ---------------------------------------------------------------------------
def gen_sku_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "sku_name", "region", "uom", "unit_cost",
                    "safety_stock_wks", "lead_time_wks", "order_multiple",
                    "max_order_qty", "shelf_life_wks", "active",
                    "selling_price", "dso_wks", "dpo_wks"])
        for brand in BRANDS:
            pid = product_id(brand)
            # unit_cost: matches the SAME total acquisition cost the PPC
            # engine accumulates at the terminal mom (Garment) node, for
            # consistency between the two engines (see apparel-us-2026's
            # sku_master rationale, reused here): fabric + dyeing + trim +
            # garment conversion, all cost_plus (both brands use cost_plus
            # in this case -- neither uses a "fixed" all-in CIF price).
            accumulated = (brand["fabric_purchase_price"]
                           + brand["dyeing_conversion_cost"]
                           + brand["trim_conversion_cost"]
                           + brand["garment_conversion_cost"])
            unit_cost = round(accumulated * (1.0 + brand["transfer_margin_rate"]), 2)
            for region, lt in (("US", brand["lt_fabric"] + brand["lt_dyeing"]
                                 + brand["lt_trim"] + brand["lt_garment"]
                                 + brand["lt_fg_wh"] + brand["lt_dc"]["US"]
                                 + brand["lt_retail"]["US"]),
                                ("JP", brand["lt_fabric"] + brand["lt_dyeing"]
                                 + brand["lt_trim"] + brand["lt_garment"]
                                 + brand["lt_fg_wh"] + brand["lt_dc"]["JP"]
                                 + brand["lt_retail"]["JP"])):
                w.writerow([pid, f"{pid} ({region} Market)", region, "EA",
                            unit_cost, 3, lt, 100, 0, 8, "True",
                            brand["selling_price_usd"], 4, 90])


def gen_node_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "node_name", "node_type", "lat", "lon",
                    "sku_id", "region", "description"])
        coords = {
            "CN": (31.23, 121.47), "BD": (23.81, 90.41), "VN": (21.03, 105.85),
            "ES": (40.42, -3.70), "PT": (38.72, -9.14), "MA": (33.57, -7.59),
            "US": (38.90, -77.04), "JP": (35.68, 139.65),
        }
        for brand in BRANDS:
            pid = product_id(brand)
            label = "H&M型オフショア多階層" if brand["key"] == "Offshore" else "Zara型近接垂直統合"
            lat, lon = coords[brand["fabric_country"]]
            w.writerow([brand["sp"], f"{brand['sp']}（{label}本部）", "procurement",
                        lat, lon, "", brand["fabric_country"], f"{label}の調達本部"])
            w.writerow([brand["fabric"], f"生地サプライヤー（{brand['fabric_country']}）",
                        "sku_supplier", *coords[brand["fabric_country"]], pid,
                        brand["fabric_country"], "原料生地調達"])
            w.writerow([brand["dyeing"], f"染色工程（{brand['dyeing_country']}）",
                        "mother_plant", *coords[brand["dyeing_country"]], pid,
                        brand["dyeing_country"], "中間加工: 染色"])
            w.writerow([brand["trim"], f"トリム・縫製付帯工程（{brand['trim_country']}）",
                        "mother_plant", *coords[brand["trim_country"]], pid,
                        brand["trim_country"], "中間加工: トリム・付帯縫製"])
            w.writerow([brand["garment"], f"最終縫製工場（{brand['garment_country']}）",
                        "mother_plant", *coords[brand["garment_country"]], pid,
                        brand["garment_country"], "最終縫製・完成品組立"])
            w.writerow([brand["fg_wh"], f"完成品地域倉庫（{brand['garment_country']}）",
                        "region_dc", *coords[brand["garment_country"]], "",
                        brand["garment_country"], "完成品バッファ倉庫（輸出前ステージング）"])
            for mkt in MARKETS:
                w.writerow([brand["dc"][mkt], f"{mkt}向けDC", "region_dc",
                            *coords[mkt], "", mkt, f"{mkt}市場向け輸入DC"])
                w.writerow([brand["retail"][mkt], f"{mkt}店舗・EC", "marketing",
                            *coords[mkt], "", mkt, f"{mkt}市場向け小売"])


def gen_sc_tree_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_name", "parent_node", "product_name", "node_type", "side",
                    "lt_wks", "cpu_size", "region", "ss_days",
                    "buffering_stock_flag", "description"])
        for brand in BRANDS:
            pid = product_id(brand)
            SP = brand["sp"]
            # ---- InBound: Fabric(leaf_in) -> Dyeing(mom) -> Trim(mom) -> Garment(mom, terminal)
            w.writerow([brand["garment"], "", pid, "mom", "inbound",
                        brand["lt_garment"], 1, brand["garment_country"], 0, 0,
                        "最終縫製（終端MOM）"])
            w.writerow([brand["trim"], brand["garment"], pid, "mom", "inbound",
                        brand["lt_trim"], 1, brand["trim_country"], 0, 0,
                        "トリム・付帯加工（中間MOM）"])
            w.writerow([brand["dyeing"], brand["trim"], pid, "mom", "inbound",
                        brand["lt_dyeing"], 1, brand["dyeing_country"], 0, 0,
                        "染色（中間MOM）"])
            w.writerow([brand["fabric"], brand["dyeing"], pid, "leaf_in", "inbound",
                        brand["lt_fabric"], 1, brand["fabric_country"], 0, 0,
                        "原料生地調達"])
            # ---- OutBound: SP -> FG_WH(dad) -> DC_market(dad) -> Retail_market(leaf_out)
            w.writerow([SP, "", pid, "supply_point", "outbound", 0, 1, "", 0, 0,
                        f"Supply Point bridge ({pid})"])
            w.writerow([brand["fg_wh"], SP, pid, "dad", "outbound",
                        brand["lt_fg_wh"], 1, brand["garment_country"],
                        brand["ss_days_fg_wh"], 1, "完成品地域倉庫（輸出前バッファ）"])
            for mkt in MARKETS:
                w.writerow([brand["dc"][mkt], brand["fg_wh"], pid, "dad", "outbound",
                            brand["lt_dc"][mkt], 1, mkt, 0, 0, f"{mkt}向けDC（スループット）"])
                w.writerow([brand["retail"][mkt], brand["dc"][mkt], pid, "leaf_out",
                            "outbound", brand["lt_retail"][mkt], 1, mkt,
                            0, 0, f"{mkt}市場 店舗・EC"])


def gen_lane_assignment(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "leaf_node_name", "mom_node_id", "priority"])
        for brand in BRANDS:
            pid = product_id(brand)
            for mkt in MARKETS:
                w.writerow([pid, brand["retail"][mkt],
                            f"IN:mom:{brand['garment']}:{pid}", 1])


def gen_route_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "region", "src_region", "dst_region", "hs_code",
                    "product_type", "assembly_cost_usd_per_lot"])
        for brand in BRANDS:
            pid = product_id(brand)
            for mkt in MARKETS:
                w.writerow([pid, mkt, brand["garment_country"], mkt,
                            brand["hs_code"], "finished_goods", 0])


def gen_edge_cost_master(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "src_region", "dst_region", "tariff_rate", "fx_rate",
                    "src_currency", "dst_currency", "freight_usd_per_lot", "notes"])
        for brand in BRANDS:
            for mkt in MARKETS:
                for scenario, rate, note in brand["edge_scenarios"][mkt]:
                    w.writerow([scenario, brand["garment_country"], mkt, rate, 1.0,
                                "USD", "USD", brand["intl_freight"][mkt], note])


def gen_ppc_tariff_rule(path):
    """Outbound tariff: last_dad(DC_market) -> channel(Retail_market)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["edge_id", "from_country", "to_country", "product_id", "hs_code",
                    "tariff_rate", "tariff_basis"])
        for brand in BRANDS:
            pid = product_id(brand)
            for mkt in MARKETS:
                edge_id = f"{brand['dc'][mkt]}->{brand['retail'][mkt]}"
                w.writerow([edge_id, brand["garment_country"], mkt, pid,
                            brand["hs_code"], brand["tariff_rate"][mkt], "transfer_price"])


def gen_ppc_transfer_price_rule(path):
    """Only the TERMINAL mom (Garment) gets a transfer-price rule -- see
    module docstring rationale item 2 (confirmed via ppc_transfer.py: only
    the pipeline's mom_node is ever looked up)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mom_node", "product_id", "method", "margin_rate", "fixed_price", "currency"])
        for brand in BRANDS:
            pid = product_id(brand)
            w.writerow([brand["garment"], pid, "cost_plus",
                        brand["transfer_margin_rate"], 0.0, "USD"])


def gen_node_cost_master(path):
    """Informational (Management-panel display) cost breakdown."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "node_name", "selling_price_per_lot", "unit_cost_per_lot", "note"])
        for brand in BRANDS:
            pid = product_id(brand)
            fabric_cost = brand["fabric_purchase_price"]
            dyeing_cost = round(fabric_cost + brand["dyeing_conversion_cost"], 2)
            trim_cost = round(dyeing_cost + brand["trim_conversion_cost"], 2)
            accumulated = trim_cost + brand["garment_conversion_cost"]
            garment_cost = round(accumulated * (1.0 + brand["transfer_margin_rate"]), 2)
            w.writerow([pid, brand["fabric"], round(fabric_cost * 1.15, 2), fabric_cost,
                        "原料生地"])
            w.writerow([pid, brand["dyeing"], round(dyeing_cost * 1.1, 2), dyeing_cost,
                        "染色後累積コスト"])
            w.writerow([pid, brand["trim"], round(trim_cost * 1.1, 2), trim_cost,
                        "トリム後累積コスト"])
            w.writerow([pid, brand["garment"], round(garment_cost * 1.1, 2), garment_cost,
                        "工場出荷価格（cost_plus、マージン込み）"])
            w.writerow([pid, brand["sp"], garment_cost, garment_cost,
                        "Supply Point pass-through"])
            fg_wh_cost = round(garment_cost + brand["domestic_freight_inbound"]
                                + brand["fg_wh_cost"], 2)
            w.writerow([pid, brand["fg_wh"], round(fg_wh_cost * 1.05, 2), fg_wh_cost,
                        "完成品地域倉庫 保管・ハンドリング込み"])
            for mkt in MARKETS:
                dc_cost = round(
                    fg_wh_cost + brand["intl_freight"][mkt]
                    + garment_cost * brand["tariff_rate"][mkt]
                    + brand["dc_cost"][mkt] + brand["dc_sga"][mkt], 2
                )
                w.writerow([pid, brand["dc"][mkt], round(dc_cost * 1.1, 2), dc_cost,
                            f"{mkt}向けDC 関税({brand['tariff_rate'][mkt]:.1%})+国際輸送費込み"])
                store_cost = round(dc_cost + brand["last_mile_freight"][mkt], 2)
                w.writerow([pid, brand["retail"][mkt], brand["selling_price_usd"], store_cost,
                            f"{mkt}店舗・EC 販売原価"])


def gen_ppc_edge_cost_rule(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["edge_id", "product_id", "cost_type", "basis", "rate", "fixed_amount", "currency"])
        for brand in BRANDS:
            pid = product_id(brand)
            # InBound chain hops (each read by ppc_forward.py Step 1b)
            w.writerow([f"{brand['fabric']}->{brand['dyeing']}", pid, "logistics_cost",
                        "per_lot", 0.0, 0.3, "USD"])
            w.writerow([f"{brand['dyeing']}->{brand['trim']}", pid, "logistics_cost",
                        "per_lot", 0.0, 0.5, "USD"])
            w.writerow([f"{brand['trim']}->{brand['garment']}", pid, "logistics_cost",
                        "per_lot", 0.0, 0.4, "USD"])
            # MOM(Garment) -> chain[0](FG_WH): domestic transport, no tariff
            w.writerow([f"{brand['garment']}->{brand['fg_wh']}", pid, "logistics_cost",
                        "per_lot", 0.0, brand["domestic_freight_inbound"], "USD"])
            for mkt in MARKETS:
                # Inter-DAD edge: FG_WH -> DC_market (international freight)
                w.writerow([f"{brand['fg_wh']}->{brand['dc'][mkt]}", pid, "logistics_cost",
                            "per_lot", 0.0, brand["intl_freight"][mkt], "USD"])
                # Outbound edge: DC_market -> Retail_market (last-mile)
                w.writerow([f"{brand['dc'][mkt]}->{brand['retail'][mkt]}", pid, "logistics_cost",
                            "per_lot", 0.0, brand["last_mile_freight"][mkt], "USD"])


def gen_ppc_node_cost_rule(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "product_id", "cost_type", "basis", "rate", "fixed_amount", "currency", "note"])
        for brand in BRANDS:
            pid = product_id(brand)
            w.writerow([brand["dyeing"], pid, "conversion_cost", "per_lot", 0.0,
                        brand["dyeing_conversion_cost"], "USD", "染色加工費（中間MOM）"])
            w.writerow([brand["trim"], pid, "conversion_cost", "per_lot", 0.0,
                        brand["trim_conversion_cost"], "USD", "トリム加工費（中間MOM）"])
            w.writerow([brand["garment"], pid, "conversion_cost", "per_lot", 0.0,
                        brand["garment_conversion_cost"], "USD", "最終縫製加工費（終端MOM）"])
            w.writerow([brand["fg_wh"], pid, "warehouse_cost", "per_lot", 0.0,
                        brand["fg_wh_cost"], "USD", "完成品地域倉庫 運営費"])
            for mkt in MARKETS:
                w.writerow([brand["dc"][mkt], pid, "warehouse_cost", "per_lot", 0.0,
                            brand["dc_cost"][mkt], "USD", f"{mkt}向けDC 運営・ハンドリング費"])
                w.writerow([brand["dc"][mkt], pid, "sga_cost", "per_lot", 0.0,
                            brand["dc_sga"][mkt], "USD", f"{mkt}向けDC SGA配賦"])


def gen_ppc_node_profit_zone(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "product_id", "profit_zone_role", "country"])
        for brand in BRANDS:
            pid = product_id(brand)
            w.writerow([brand["fabric"], pid, "SUPPLIER_COST_BASE", brand["fabric_country"]])
            w.writerow([brand["dyeing"], pid, "MOM_PLANT_PROFIT", brand["dyeing_country"]])
            w.writerow([brand["trim"], pid, "MOM_PLANT_PROFIT", brand["trim_country"]])
            w.writerow([brand["garment"], pid, "MOM_PLANT_PROFIT", brand["garment_country"]])
            w.writerow([brand["sp"], pid, "OPERATION_NODE_COST_BASE", brand["garment_country"]])
            w.writerow([brand["fg_wh"], pid, "OPERATION_NODE_COST_BASE", brand["garment_country"]])
            for mkt in MARKETS:
                w.writerow([brand["dc"][mkt], pid, "OPERATION_NODE_COST_BASE", mkt])
                w.writerow([brand["retail"][mkt], pid, "OUTBOUND_CHANNEL_PROFIT", mkt])


def gen_ppc_profit_zone_rule(path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["profit_zone_role", "product_id", "profit_type", "basis", "rate", "fixed_amount"])
        for brand in BRANDS:
            pid = product_id(brand)
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
            years = sorted(set(wk[:4] for wk in weeks_sorted))
            for yr in years:
                yr_weeks = sorted(wk for wk in weeks_sorted if wk.startswith(yr))
                if not yr_weeks:
                    continue
                w.writerow([f"{brand['closure_id_prefix']}_{yr}",
                            f"{brand['closure_name']} {yr}",
                            yr_weeks[0], yr_weeks[-1], brand["garment"],
                            "supply_closure", brand["cap_garment"] * 0.2])


def gen_inventory_master(path, first_week_label):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "region", "on_hand_qty", "on_order_qty", "week"])
        for brand in BRANDS:
            pid = product_id(brand)
            for mkt, peak in MARKETS.items():
                on_hand = round(peak * BASELINE_FRAC * 0.6)
                on_order = round(peak * BASELINE_FRAC * 0.3)
                w.writerow([pid, mkt, on_hand, on_order, first_week_label])


def gen_ppc_supplier_cost(path, first_week_label):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["supplier_node", "product_id", "week", "purchase_price", "currency"])
        for brand in BRANDS:
            pid = product_id(brand)
            w.writerow([brand["fabric"], pid, first_week_label,
                        brand["fabric_purchase_price"], "USD"])


def gen_ppc_market_price(path, first_week_label):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["market_node", "product_id", "week", "market_price", "currency"])
        for brand in BRANDS:
            pid = product_id(brand)
            for mkt in MARKETS:
                price, currency = brand["market_price_local"][mkt]
                w.writerow([brand["retail"][mkt], pid, first_week_label, price, currency])


def gen_demand_forecast(weeks, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "region", "week", "quantity"])
        for week_idx, (label, _iso_year, iso_week) in enumerate(weeks):
            for brand in BRANDS:
                pid = product_id(brand)
                # Material-fill window: how long Garment must wait, from a
                # cold start, before its own InBound chain (Fabric->Dyeing
                # ->Trim) delivers the first unit. Empirically confirmed
                # (direct PSI inspection) that Garment's own P (production)
                # cannot start before this many weeks, REGARDLESS of the
                # demand-side ramp -- this is a hard material-availability
                # constraint, not a demand phenomenon.
                upstream_lt = brand["lt_fabric"] + brand["lt_dyeing"] + brand["lt_trim"]
                for mkt, peak in MARKETS.items():
                    # This market's downstream OutBound leg (FG_WH -> DC ->
                    # Retail). BackwardPlanner shifts each node's own
                    # required-ship date backward by its downstream lead
                    # time, so retail-level demand at week
                    # (garment_week + downstream_lt) becomes Garment's own
                    # required S at garment_week. See ramp_factor()
                    # docstring: a plain 0->1 ramp starting at week 0 gets
                    # this backward shift applied to it too, so by the time
                    # it reaches Garment the ramp has already partially (or
                    # fully) completed -- it does NOT null out Garment's
                    # demand during the weeks Garment is materially unable
                    # to produce. The fix is to hold retail demand at
                    # literal ZERO (no ramp at all) for the first
                    # downstream_lt weeks -- so that, once backward-shifted,
                    # Garment's own S is genuinely zero for weeks
                    # [0, upstream_lt) -- and only start the ramp once that
                    # delay has elapsed, over the following upstream_lt
                    # weeks (so Garment's S ramps in lockstep with Garment's
                    # own P as material starts arriving).
                    downstream_lt = (brand["lt_fg_wh"] + brand["lt_dc"][mkt]
                                      + brand["lt_retail"][mkt])
                    if week_idx < downstream_lt:
                        ramp = 0.0
                    else:
                        ramp = ramp_factor(week_idx - downstream_lt, upstream_lt)
                    weight = demand_weight(iso_week, SEASON_START, SEASON_END) * ramp
                    qty = round(peak * weight)
                    # IMPORTANT: always write a row, even when qty == 0.
                    # verify_pipeline.py (and the GUI's own Planning run)
                    # derive the simulation's week range via
                    # `sorted(demand_df["week"].unique())` -- if the
                    # pre-launch "ramp delay" weeks are omitted entirely
                    # (as a naive `if qty > 0` guard would do), those weeks
                    # simply vanish from the simulation's week list, and
                    # the backward planner's first INCLUDED week becomes
                    # its new "week 0" with full demand already active --
                    # silently recreating the exact startup-transient CO
                    # bug this ramp was written to fix, just shifted later
                    # in the calendar. Explicit qty=0 rows keep every week
                    # in the simulation's own week range.
                    w.writerow([pid, mkt, label, qty])


def gen_capacity_plan(weeks, path):
    """Cover ALL weeks for every capacity-bearing node (not just demand
    weeks) -- fixes the coverage gap documented as a known limitation of
    apparel-us-2026 (see exercises/ex3_capacity_overlap). Avoids the
    cap_hard=0-means-unconstrained silent-fallback trap during production
    weeks that fall outside the demand window (offset by lead time)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku_id", "node_name", "week", "max_supply", "source"])
        for label, _iso_year, _iso_week in weeks:
            for brand in BRANDS:
                pid = product_id(brand)
                closure = label in brand["closure_weeks"]
                garment_cap = brand["cap_garment"] * 0.2 if closure else brand["cap_garment"]
                garment_note = (f"{brand['closure_name']} reduced capacity (20% of normal)"
                                 if closure else "Garment weekly capacity")
                w.writerow([pid, brand["garment"], label, garment_cap, garment_note])
                w.writerow([pid, brand["dyeing"], label, brand["cap_unconstrained"],
                            "Dyeing tier, effectively unconstrained"])
                w.writerow([pid, brand["trim"], label, brand["cap_unconstrained"],
                            "Trim tier, effectively unconstrained"])
                w.writerow([pid, brand["fabric"], label, brand["cap_unconstrained"],
                            "Fabric supply, effectively unconstrained"])
                w.writerow([pid, brand["fg_wh"], label, brand["cap_fg_wh"],
                            "FG warehouse throughput"])
                for mkt in MARKETS:
                    w.writerow([pid, brand["dc"][mkt], label, brand["cap_dc"][mkt],
                                f"{mkt} DC throughput"])


def gen_fx_rate(weeks, path):
    """Base-case FX assumption for the live simulation. USD/JPY held flat
    at 150 (rate expressed as USD-per-JPY, i.e. 1/150, since FXConverter
    multiplies amount_local(JPY) by this rate to get amount_base(USD)).
    See module docstring rationale item 4 for why the Base/StrongYen/
    WeakYen scenario COMPARISON is not encoded here but in a separate
    verification script."""
    jpy_per_usd_base = 150.0
    rate = round(1.0 / jpy_per_usd_base, 6)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["week", "currency", "base_currency", "rate"])
        for label, _iso_year, _iso_week in weeks:
            w.writerow([label, "USD", "USD", 1.0])
            w.writerow([label, "JPY", "USD", rate])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    raw_weeks = week_infos(START_DATE, NUM_WEEKS)
    weeks = trim_weeks_to(raw_weeks, "2029-W52")
    first_week_label = weeks[0][0]
    print(f"Generating {len(weeks)} weeks: {weeks[0][0]} .. {weeks[-1][0]}")
    print(f"Brands: {[b['key'] for b in BRANDS]}")
    print(f"Products: {[product_id(b) for b in BRANDS]}")

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
    gen_inventory_master(os.path.join(OUT_DIR, "inventory_master.csv"), first_week_label)
    gen_ppc_supplier_cost(os.path.join(OUT_DIR, "ppc_supplier_cost.csv"), first_week_label)
    gen_ppc_market_price(os.path.join(OUT_DIR, "ppc_market_price.csv"), first_week_label)
    gen_demand_forecast(weeks, os.path.join(OUT_DIR, "demand_forecast.csv"))
    gen_capacity_plan(weeks, os.path.join(OUT_DIR, "capacity_plan.csv"))
    gen_fx_rate(weeks, os.path.join(OUT_DIR, "ppc_fx_rate.csv"))

    print(f"Done. Generated all 20 CSV files for apparel-global-2028-2029 "
          f"({len(BRANDS)} brands x {len(MARKETS)} markets, 1 SKU each).")


if __name__ == "__main__":
    main()
