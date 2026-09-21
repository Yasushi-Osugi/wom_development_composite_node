"""
WOM output module – writes simulation results to CSV, Excel, or console.
"""

from __future__ import annotations

import os
from typing import List, Optional

import pandas as pd

from wom.data.schema import Cols
from wom.engine.scenario import ScenarioManager


# ──────────────────────────────────────────────────────────────────────
# Console reporter
# ──────────────────────────────────────────────────────────────────────

def print_kpi_summary(mgr: ScenarioManager, top_n: int = 20) -> None:
    """Print a KPI summary table to stdout."""
    summary = mgr.kpi_summary()
    pd.set_option("display.max_rows", top_n)
    pd.set_option("display.float_format", "{:,.2f}".format)
    print("\n" + "═" * 80)
    print("  WOM KPI SUMMARY  –  by Scenario / SKU / Region")
    print("═" * 80)
    print(summary.to_string(index=False))
    print("═" * 80 + "\n")


def print_at_risk(mgr: ScenarioManager) -> None:
    """Print at-risk SKUs to stdout."""
    risk = mgr.at_risk_skus()
    if risk.empty:
        print("  ✔ No at-risk SKUs detected.")
        return
    print(f"\n  ⚠  {len(risk)} at-risk rows detected:")
    print(risk[[Cols.SCENARIO, Cols.SKU_ID, Cols.REGION, Cols.WEEK,
                Cols.FILL_RATE, Cols.INV_COVER_WKS, Cols.STOCKOUT_QTY]]
          .to_string(index=False))


# ──────────────────────────────────────────────────────────────────────
# CSV writer
# ──────────────────────────────────────────────────────────────────────

def write_csv(mgr: ScenarioManager, output_dir: str) -> List[str]:
    """
    Write one CSV per scenario plus summary files.
    Returns list of file paths written.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = []

    # Per-scenario detail
    for s in mgr.scenarios():
        path = os.path.join(output_dir, f"wom_{s.lower()}_detail.csv")
        mgr.get(s).to_csv(path, index=False)
        paths.append(path)

    # Combined
    combined_path = os.path.join(output_dir, "wom_combined.csv")
    mgr.combined().to_csv(combined_path, index=False)
    paths.append(combined_path)

    # KPI summary
    summary_path = os.path.join(output_dir, "wom_kpi_summary.csv")
    mgr.kpi_summary().to_csv(summary_path, index=False)
    paths.append(summary_path)

    # Weekly summary
    weekly_path = os.path.join(output_dir, "wom_weekly_summary.csv")
    mgr.weekly_summary().to_csv(weekly_path, index=False)
    paths.append(weekly_path)

    # At-risk
    risk = mgr.at_risk_skus()
    if not risk.empty:
        risk_path = os.path.join(output_dir, "wom_at_risk.csv")
        risk.to_csv(risk_path, index=False)
        paths.append(risk_path)

    return paths


# ──────────────────────────────────────────────────────────────────────
# Excel writer
# ──────────────────────────────────────────────────────────────────────

def write_excel(mgr: ScenarioManager, output_dir: str, filename: str = "wom_results.xlsx") -> str:
    """
    Write a multi-sheet Excel workbook with all results.
    Returns the file path.
    """
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        # KPI Summary (first sheet)
        mgr.kpi_summary().to_excel(writer, sheet_name="KPI Summary", index=False)

        # Weekly summary
        mgr.weekly_summary().to_excel(writer, sheet_name="Weekly Summary", index=False)

        # Per-scenario detail sheets
        for s in mgr.scenarios():
            sheet = f"{s[:25]}"  # Excel sheet name limit
            mgr.get(s).to_excel(writer, sheet_name=sheet, index=False)

        # At-risk
        risk = mgr.at_risk_skus()
        if not risk.empty:
            risk.to_excel(writer, sheet_name="At-Risk SKUs", index=False)

        # Scenario deltas vs Base
        scenarios = mgr.scenarios()
        if "Base" in scenarios:
            for s in scenarios:
                if s != "Base":
                    delta = mgr.delta_vs_base(s)
                    delta.to_excel(writer, sheet_name=f"Delta_{s[:18]}", index=False)

        # Auto-format column widths
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 30)

    return path
