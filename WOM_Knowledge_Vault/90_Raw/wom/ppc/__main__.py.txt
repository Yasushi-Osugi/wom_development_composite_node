"""
wom/ppc/__main__.py
===================
PPC Simulation Engine — CLI Entry Point.

Usage:
    python -m wom.ppc [options]

Options:
    --data-dir      DIR     PPC master CSV directory  [default: data/ppc]
    --sales-csv     FILE    Lot sales records CSV (see format below).
                            If omitted, generates sample iphone-vs lots.
    --output-dir    DIR     Output directory          [default: output/ppc]
    --base-currency CUR     Base currency             [default: JPY]
    --weeks         N       Number of weeks for sample generation [default: 156]
    --start-week    WEEK    Start ISO week for sample  [default: 2026-W01]
    --jp-lots       N       JP_Channel lots/week in sample [default: 10]
    --us-lots       N       US_Channel lots/week in sample [default: 5]
    --verbose               Print step-by-step progress
    --chart                 Show PPC Cockpit dashboard after simulation
    --save-chart    FILE    Save cockpit figure to FILE (PNG/PDF)
    --help                  Show this help
"""

from __future__ import annotations

import argparse
import os
import sys
import json
import time
from typing import List, Tuple

import pandas as pd

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from wom.ppc.ppc_rules import PPCRuleSet
from wom.ppc.ppc_engine import (PPCSimulationEngine, build_iphone_vs_paths,
                                  build_cookie_vs_paths, detect_scenario)
from wom.ppc.ppc_export import export_results


def generate_sample_sales(
    start_week: str = "2026-W01",
    n_weeks: int = 156,
    jp_lots_per_week: int = 10,
    us_lots_per_week: int = 5,
    product_id: str = "IPHONE",
) -> pd.DataFrame:
    """
    Generate synthetic sales_records using correct ISO 8601 week arithmetic.

    Uses datetime.date.isocalendar() to handle years with 53 ISO weeks
    (e.g. 2026) and avoids duplicate lot_ids across years.

    Lot ID format: L-JP-{YYYY}W{WW}-{NNN}
    """
    import datetime

    # Parse start week → find its Monday
    start_year, start_wk = start_week.split("-W")
    start_year, start_wk = int(start_year), int(start_wk)
    jan4 = datetime.date(start_year, 1, 4)        # Jan 4 is always in ISO week 1
    week1_mon = jan4 - datetime.timedelta(days=jan4.weekday())
    start_mon = week1_mon + datetime.timedelta(weeks=start_wk - 1)

    rows = []
    for w in range(n_weeks):
        d = start_mon + datetime.timedelta(weeks=w)
        iso_year, iso_week, _ = d.isocalendar()
        week_label = f"{iso_year}-W{iso_week:02d}"
        yr_wk = f"{iso_year}W{iso_week:02d}"       # used in lot_id for uniqueness

        for i in range(1, jp_lots_per_week + 1):
            rows.append({
                "lot_id":       f"L-JP-{yr_wk}-{i:03d}",
                "week":         week_label,
                "channel_node": "JP_Channel",
                "product_id":   product_id,
                "qty":          1,
            })
        for i in range(1, us_lots_per_week + 1):
            rows.append({
                "lot_id":       f"L-US-{yr_wk}-{i:03d}",
                "week":         week_label,
                "channel_node": "US_Channel",
                "product_id":   product_id,
                "qty":          1,
            })

    return pd.DataFrame(rows)


def _generate_model_sales(
    products: list,
    channels: list,
    start_week: str = "2026-W01",
    n_weeks: int = 156,
    lots_per_week: int = 10,
) -> pd.DataFrame:
    """
    Generate sample lots using actual products and channels from loaded rules.
    Each product appears in each channel, lots_per_week per combination.
    """
    import datetime
    import itertools

    start_year, start_wk = start_week.split("-W")
    start_year, start_wk = int(start_year), int(start_wk)
    jan4 = datetime.date(start_year, 1, 4)
    week1_mon = jan4 - datetime.timedelta(days=jan4.weekday())
    start_mon = week1_mon + datetime.timedelta(weeks=start_wk - 1)

    rows = []
    ch_tag = {ch: f"C{ci:02d}" for ci, ch in enumerate(channels)}
    pr_tag = {pr: f"{pr[:6]}" for pr in products}
    for w in range(n_weeks):
        d = start_mon + datetime.timedelta(weeks=w)
        iso_year, iso_week, _ = d.isocalendar()
        week_label = f"{iso_year}-W{iso_week:02d}"
        yr_wk = f"{iso_year}W{iso_week:02d}"

        for prod, ch in itertools.product(products, channels):
            for i in range(1, lots_per_week + 1):
                rows.append({
                    "lot_id":       f"L-{pr_tag[prod]}-{ch_tag[ch]}-{yr_wk}-{i:03d}",
                    "week":         week_label,
                    "channel_node": ch,
                    "product_id":   prod,
                    "qty":          1,
                })
    return pd.DataFrame(rows)


def _fmt(val: float, unit: str = "") -> str:
    if abs(val) >= 1_000_000_000:
        return f"{val/1_000_000_000:.2f}B {unit}"
    elif abs(val) >= 1_000_000:
        return f"{val/1_000_000:.2f}M {unit}"
    elif abs(val) >= 1_000:
        return f"{val/1_000:.1f}K {unit}"
    else:
        return f"{val:.1f} {unit}"


def print_kpi_banner(kpi: dict, trust_count: int) -> None:
    cur = kpi["base_currency"]
    sep = "─" * 60
    print()
    print(sep)
    print("  WOM PPC Simulation — KPI Summary")
    print(sep)
    print(f"  Base currency  : {cur}")
    print(f"  Total lots     : {kpi['total_lots']:,}")
    print()
    print(f"  Revenue        : {_fmt(kpi['total_revenue_base'], cur)}")
    print(f"  Total Cost     : {_fmt(kpi['total_cost_base'], cur)}")
    print(f"  Gross Profit   : {_fmt(kpi['gross_profit_base'], cur)}")
    print(f"  Gross Margin   : {kpi['gross_margin_pct']:.1%}")
    print()
    print(f"  Tariff Cost    : {_fmt(kpi['total_tariff_base'], cur)}")
    print(f"  MOM Profit     : {_fmt(kpi['mom_profit_base'], cur)}")
    print()
    print(f"  JP Revenue     : {_fmt(kpi['channel_jp_revenue_base'], cur)}")
    print(f"  US Revenue     : {_fmt(kpi['channel_us_revenue_base'], cur)}")
    print()
    trust_label = f"!  {trust_count} trust event(s) fired" if trust_count else "OK  No trust events"
    print(f"  {trust_label}")
    print(sep)
    print()


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m wom.ppc",
        description="WOM PPC Simulation Engine - CLI Runner",
    )
    parser.add_argument("--data-dir",      default="data/ppc",   metavar="DIR")
    parser.add_argument("--sales-csv",     default=None,          metavar="FILE")
    parser.add_argument("--output-dir",    default="output/ppc",  metavar="DIR")
    parser.add_argument("--base-currency", default="JPY",          metavar="CUR")
    parser.add_argument("--weeks",         default=156, type=int,  metavar="N")
    parser.add_argument("--start-week",    default="2026-W01",    metavar="WEEK")
    parser.add_argument("--jp-lots",       default=10,  type=int,  metavar="N")
    parser.add_argument("--us-lots",       default=5,   type=int,  metavar="N")
    parser.add_argument("--verbose",       action="store_true")
    parser.add_argument("--chart",         action="store_true",
                        help="Show PPC Cockpit dashboard after simulation")
    parser.add_argument("--save-chart",    default=None, metavar="FILE",
                        help="Save cockpit figure to FILE (PNG/PDF)")
    parser.add_argument("--app",           action="store_true",
                        help="Launch interactive PPC Cockpit (Tkinter app)")

    args = parser.parse_args(argv)

    print(f"[PPC] Loading rules from: {args.data_dir}")
    try:
        rules = PPCRuleSet.load(args.data_dir)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return 1

    if args.sales_csv:
        print(f"[PPC] Loading sales from: {args.sales_csv}")
        sales = pd.read_csv(args.sales_csv)
        required = {"lot_id", "week", "channel_node", "product_id"}
        missing = required - set(sales.columns)
        if missing:
            print(f"[ERROR] sales CSV missing columns: {missing}")
            return 1
    else:
        # Auto-detect products and channels from loaded rules
        known_products = [p for p in rules.supplier_cost["product_id"].unique()
                          if isinstance(p, str) and p]
        known_channels = [c for c in rules.market_price["market_node"].unique()
                          if isinstance(c, str) and c]

        # Generate sample lots using model-specific products/channels when available
        if known_products and known_channels:
            print(
                f"[PPC] Generating sample sales: "
                f"{args.weeks} weeks x {len(known_channels)} channels "
                f"x {args.jp_lots}lots/wk from {args.start_week}"
            )
            sales = _generate_model_sales(
                products=known_products,
                channels=known_channels,
                start_week=args.start_week,
                n_weeks=args.weeks,
                lots_per_week=args.jp_lots,
            )
        else:
            print(
                f"[PPC] Generating sample sales: "
                f"{args.weeks} weeks x "
                f"JP:{args.jp_lots}lots/wk + US:{args.us_lots}lots/wk "
                f"from {args.start_week}"
            )
            sales = generate_sample_sales(
                start_week=args.start_week,
                n_weeks=args.weeks,
                jp_lots_per_week=args.jp_lots,
                us_lots_per_week=args.us_lots,
            )
    print(f"[PPC] {len(sales)} lot-records to process")

    # Select scenario-specific engine config
    scenario = detect_scenario(sales)
    if scenario == "cookie":
        sc_paths      = build_cookie_vs_paths()
        mom_node      = {"Cookie_Import": "Factory_GP_CN", "Cookie_Local": "Factory_DP_JP"}
        supplier_node = {"Cookie_Import": "Ingredients_CN", "Cookie_Local": "Ingredients_JP"}
        dad_node      = {"Cookie_Import": "DC_Import_Buffer", "Cookie_Local": "DC_Local_JP"}
        dad_nodes_chain = {
            "Cookie_Import": ["DC_Import_Buffer", "DC_Import_Main"],
            "Cookie_Local":  ["DC_Local_JP"],
        }
        print(f"[PPC] Scenario: COOKIE_JP")
    else:
        sc_paths        = build_iphone_vs_paths()
        mom_node        = "MOM_China"
        supplier_node   = "Supplier_CN"
        dad_node        = "DAD_Japan"
        dad_nodes_chain = None
        print(f"[PPC] Scenario: {scenario.upper()}")

    t0 = time.time()
    eng = PPCSimulationEngine(
        sales_records=sales,
        sc_paths=sc_paths,
        rules=rules,
        base_currency=args.base_currency,
        mom_node=mom_node,
        supplier_node=supplier_node,
        dad_node=dad_node,
        dad_nodes_chain=dad_nodes_chain,
        verbose=args.verbose,
    )
    result = eng.run()
    elapsed = time.time() - t0
    print(f"[PPC] Engine complete in {elapsed:.2f}s")

    export_results(result, args.output_dir)
    print_kpi_banner(result.kpi_summary, len(result.trust_events))

    if result.trust_events:
        print("  Trust Events:")
        for te in result.trust_events[:10]:
            msg = f"    [{te.trust_event_type}] lot={te.lot_id} week={te.week} channel={te.channel_node}"
            print(msg)
        if len(result.trust_events) > 10:
            print(f"    ... and {len(result.trust_events) - 10} more")
        print()

    if args.chart or args.save_chart:
        from wom.ppc.ppc_cockpit import show_cockpit
        show_cockpit(
            output_dir=args.output_dir,
            save_path=args.save_chart,
            show=args.chart,
        )

    if args.app:
        from wom.ppc.ppc_cockpit_app import run_app
        run_app(output_dir=args.output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
