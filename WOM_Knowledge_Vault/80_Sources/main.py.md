---
tags: [wom, code]
---
# main.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/main.py) · [原文テキスト](../90_Raw/main.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## モジュール説明（docstring原文）

```text
WOM – Weekly Operation Model  v1r0m0
Entry point: python -m main  (or  python main.py)

Usage modes
-----------
  python -m main                   # Launch GUI (default)
  python -m main --gui             # Launch GUI explicitly
  python -m main --cli             # Run headless CLI simulation
  python -m main --cli --help      # Show CLI options
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `run_cli` | 33 | docstringなし（下のコード参照） |
| FunctionDef | `run_gui` | 126 | docstringなし（下のコード参照） |
| FunctionDef | `run_cockpit` | 136 | 経営コックピット（Phase 8・`wom/cockpit/`）を起動する。 |
| FunctionDef | `build_parser` | 151 | docstringなし（下のコード参照） |
| FunctionDef | `main` | 195 | docstringなし（下のコード参照） |
| FunctionDef | `resolve` | 42 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/wom/config.py|wom/config.py]]
- [[80_Sources/wom/data/loader.py|wom/data/loader.py]]
- [[80_Sources/wom/engine/simulator.py|wom/engine/simulator.py]]
- [[80_Sources/wom/reports/output.py|wom/reports/output.py]]
- [[80_Sources/wom/gui/app.py|wom/gui/app.py]]
- [[80_Sources/wom/cockpit/cockpit_app.py|wom/cockpit/cockpit_app.py]]

## 全文（コメント・原文を省略せず収録）

````python
"""
WOM – Weekly Operation Model  v1r0m0
Entry point: python -m main  (or  python main.py)

Usage modes
-----------
  python -m main                   # Launch GUI (default)
  python -m main --gui             # Launch GUI explicitly
  python -m main --cli             # Run headless CLI simulation
  python -m main --cli --help      # Show CLI options
"""

from __future__ import annotations

import argparse
import os
import sys


# ──────────────────────────────────────────────────────────────────────
# Add project root to path so `wom` package is importable regardless
# of working directory
# ──────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ──────────────────────────────────────────────────────────────────────
# CLI mode
# ──────────────────────────────────────────────────────────────────────

def run_cli(args) -> None:
    from wom.config import WOMConfig, ScenarioSpec
    from wom.data.loader import WOMInputs
    from wom.engine.simulator import WOMSimulator
    from wom.reports.output import print_kpi_summary, print_at_risk, write_csv, write_excel

    # ── Locate sample data as fallback ────────────────────────────
    sample_dir = os.path.join(ROOT, "data", "sample")

    def resolve(path, filename):
        if path and os.path.exists(path):
            return path
        fallback = os.path.join(sample_dir, filename)
        if os.path.exists(fallback):
            print(f"  ℹ  Using sample data: {fallback}")
            return fallback
        raise FileNotFoundError(
            f"File not found: {path!r}. "
            f"Provide a path with --{filename.split('.')[0].replace('_','-')} "
            f"or ensure sample data exists in {sample_dir}"
        )

    sku_path = resolve(args.sku_master,        "sku_master.csv")
    dem_path = resolve(args.demand_forecast,   "demand_forecast.csv")
    inv_path = resolve(args.inventory_master,  "inventory_master.csv")
    cap_path = resolve(args.capacity_plan,     "capacity_plan.csv")

    # ── Build config ──────────────────────────────────────────────
    scenarios = []
    for spec in (args.scenarios or []):
        parts = spec.split(":")
        name = parts[0]
        dm   = float(parts[1]) if len(parts) > 1 else 1.0
        sm   = float(parts[2]) if len(parts) > 2 else 1.0
        scenarios.append(ScenarioSpec(name, dm, sm))

    config = WOMConfig(
        start_week=args.start_week,
        num_weeks=args.num_weeks,
        safety_stock_weeks=args.safety_stock_weeks,
        lead_time_weeks=args.lead_time_weeks,
        capacity_constrained=not args.unconstrained,
        scenarios=scenarios or None,
        output_dir=args.output_dir,
    )
    if not scenarios:
        # Use defaults
        config.scenarios = [
            ScenarioSpec("Base",     1.00, 1.00, "Base plan"),
            ScenarioSpec("Upside",   1.20, 1.00, "Demand +20%"),
            ScenarioSpec("Downside", 0.80, 1.00, "Demand -20%"),
        ]

    print("\n" + "═" * 60)
    print("  WOM – Weekly Operation Model  v1r0m0")
    print("═" * 60)
    print(f"  {config}")
    print()

    # ── Load inputs ───────────────────────────────────────────────
    inputs = WOMInputs.from_files(
        sku_master_path=sku_path,
        demand_forecast_path=dem_path,
        inventory_master_path=inv_path,
        capacity_plan_path=cap_path,
        weeks=config.weeks,
    )
    print(inputs.summary())
    print()

    # ── Run simulation ────────────────────────────────────────────
    sim = WOMSimulator(config)
    sim.load(inputs)
    mgr = sim.run(verbose=True)

    # ── Print results ─────────────────────────────────────────────
    print_kpi_summary(mgr)
    print_at_risk(mgr)

    # ── Export ────────────────────────────────────────────────────
    os.makedirs(args.output_dir, exist_ok=True)
    if args.excel:
        path = write_excel(mgr, args.output_dir)
        print(f"\n  ✔ Excel report: {path}")
    else:
        paths = write_csv(mgr, args.output_dir)
        print(f"\n  ✔ {len(paths)} CSV files written to: {args.output_dir}")


# ──────────────────────────────────────────────────────────────────────
# GUI mode
# ──────────────────────────────────────────────────────────────────────

def run_gui() -> None:
    try:
        from wom.gui.app import launch
        launch()
    except ImportError as e:
        print(f"GUI could not start: {e}")
        print("Install requirements: pip install -r requirements.txt")
        sys.exit(1)


def run_cockpit() -> None:
    """経営コックピット（Phase 8・`wom/cockpit/`）を起動する。"""
    try:
        from wom.cockpit.cockpit_app import launch
        launch()
    except ImportError as e:
        print(f"Cockpit could not start: {e}")
        print("Install requirements: pip install -r requirements.txt")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────
# Argument parser
# ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m main",
        description="WOM – Weekly Operation Model v1r0m0",
    )
    p.add_argument("--gui",  action="store_true", help="Launch GUI (default)")
    p.add_argument("--cli",  action="store_true", help="Run headless CLI simulation")
    p.add_argument("--cockpit", action="store_true",
                   help="Launch the management cockpit (wom/cockpit/, Phase 8)")

    # CLI-only options
    cli = p.add_argument_group("CLI options (only used with --cli)")
    cli.add_argument("--start-week",           default="2024-W01",
                     help="Planning start week (default: 2024-W01)")
    cli.add_argument("--num-weeks",            type=int,   default=26,
                     help="Number of planning weeks (default: 26)")
    cli.add_argument("--safety-stock-weeks",   type=float, default=2.0,
                     help="Global safety stock in weeks (default: 2.0)")
    cli.add_argument("--lead-time-weeks",      type=int,   default=4,
                     help="Global lead time in weeks (default: 4)")
    cli.add_argument("--unconstrained",        action="store_true",
                     help="Disable capacity constraints")
    cli.add_argument("--scenarios",            nargs="*",
                     metavar="NAME[:DEM_MULT[:SUP_MULT]]",
                     help="Scenarios e.g. Base:1.0 Upside:1.2 Downside:0.8")
    cli.add_argument("--sku-master",           default="",
                     help="Path to sku_master CSV/Excel")
    cli.add_argument("--demand-forecast",      default="",
                     help="Path to demand_forecast CSV/Excel")
    cli.add_argument("--inventory-master",     default="",
                     help="Path to inventory_master CSV/Excel")
    cli.add_argument("--capacity-plan",        default="",
                     help="Path to capacity_plan CSV/Excel")
    cli.add_argument("--output-dir",           default="output",
                     help="Output directory for reports (default: output/)")
    cli.add_argument("--excel",                action="store_true",
                     help="Export results as Excel workbook instead of CSV")
    return p


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = build_parser()
    args   = parser.parse_args()

    if args.cli:
        run_cli(args)
    elif args.cockpit:
        run_cockpit()
    else:
        # Default: GUI
        run_gui()


if __name__ == "__main__":
    main()

````
