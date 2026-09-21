"""
wom/ppc/ppc_export.py
=====================
Export PPC Simulation results to CSV and JSON files.

Output files:
    ppc_event_ledger.csv        - all PPCEvents (full audit trail)
    ppc_node_week_summary.csv   - aggregated by node+week
    ppc_profit_zone_summary.csv - aggregated by profit_zone
    ppc_lot_reconciliation.csv  - lot-level forward vs backward comparison
    ppc_kpi_summary.json        - top-level KPI dict

Write strategy: atomic write via temp file + fsync.
  1. Write to <file>.tmp
  2. flush + fsync  (forces OS buffer -> disk)
  3. os.replace(.tmp -> final)  (atomic on POSIX and Windows)
This prevents partial files if the GUI thread is interrupted mid-write.
"""

from __future__ import annotations

import json
import os
from typing import List

import pandas as pd

from .ppc_models import PPCEvent, PPCSimulationResult


def _safe_write_csv(df: pd.DataFrame, path: str) -> None:
    """Write DataFrame to CSV atomically (temp + fsync + replace)."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            df.to_csv(f, index=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


def _safe_write_json(obj: dict, path: str) -> None:
    """Write JSON atomically (temp + fsync + replace)."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


def export_results(result: PPCSimulationResult, output_dir: str) -> None:
    """
    Write all PPC output files to `output_dir`.

    Parameters
    ----------
    result     : PPCSimulationResult
    output_dir : directory path (created if not exists)
    """
    os.makedirs(output_dir, exist_ok=True)

    # ── ppc_event_ledger.csv ───────────────────────────────────────────
    events_df = _events_to_df(result.ppc_events)
    _safe_write_csv(events_df,
                    os.path.join(output_dir, "ppc_event_ledger.csv"))

    # ── ppc_node_week_summary.csv ──────────────────────────────────────
    _safe_write_csv(result.node_week_summary,
                    os.path.join(output_dir, "ppc_node_week_summary.csv"))

    # ── ppc_profit_zone_summary.csv ────────────────────────────────────
    _safe_write_csv(result.profit_zone_summary,
                    os.path.join(output_dir, "ppc_profit_zone_summary.csv"))

    # ── ppc_lot_reconciliation.csv ─────────────────────────────────────
    _safe_write_csv(result.lot_reconciliation,
                    os.path.join(output_dir, "ppc_lot_reconciliation.csv"))

    # ── ppc_kpi_summary.json ───────────────────────────────────────────
    _safe_write_json(result.kpi_summary,
                     os.path.join(output_dir, "ppc_kpi_summary.json"))

    # ── ppc_node_pl_summary.csv (拠点別P/L評価, full-horizon per node) ──
    node_pl_df = result.node_pl_summary
    if node_pl_df is None:
        node_pl_df = pd.DataFrame(columns=[
            "node_id", "product_id", "revenue_base", "cost_base",
            "tariff_base", "gross_profit_base", "gross_margin_pct", "lot_events",
        ])
    _safe_write_csv(node_pl_df,
                    os.path.join(output_dir, "ppc_node_pl_summary.csv"))

    print(f"[PPC Export] Written to {output_dir}/")
    print(f"  ppc_event_ledger.csv        ({len(events_df)} events)")
    print(f"  ppc_node_week_summary.csv   ({len(result.node_week_summary)} rows)")
    print(f"  ppc_profit_zone_summary.csv ({len(result.profit_zone_summary)} rows)")
    print(f"  ppc_lot_reconciliation.csv  ({len(result.lot_reconciliation)} rows)")
    print(f"  ppc_node_pl_summary.csv     ({len(node_pl_df)} rows)")
    print(f"  ppc_kpi_summary.json")


def _events_to_df(events: List[PPCEvent]) -> pd.DataFrame:
    """Convert PPCEvent list to DataFrame with standard column order."""
    if not events:
        return pd.DataFrame(columns=[
            "event_id", "week", "lot_id", "node_id", "edge_id", "product_id",
            "qty", "ppc_event_type", "amount_local", "currency", "fx_rate",
            "amount_base", "amount_per_unit_base", "source_rule", "direction",
            "profit_zone", "cost_phase",
        ])
    return pd.DataFrame([
        {
            "event_id":             ev.event_id,
            "week":                 ev.week,
            "lot_id":               ev.lot_id,
            "node_id":              ev.node_id,
            "edge_id":              ev.edge_id,
            "product_id":           ev.product_id,
            "qty":                  ev.qty,
            "ppc_event_type":       ev.ppc_event_type,
            "amount_local":         ev.amount_local,
            "currency":             ev.currency,
            "fx_rate":              ev.fx_rate,
            "amount_base":          ev.amount_base,
            "amount_per_unit_base": ev.amount_per_unit_base,
            "source_rule":          ev.source_rule,
            "direction":            ev.direction,
            "profit_zone":          ev.profit_zone,
            "cost_phase":           ev.cost_phase,
        }
        for ev in events
    ])
