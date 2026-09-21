"""
wom/ppc/ppc_cockpit.py
======================
PPC Evaluation Cockpit — standalone matplotlib dashboard.

Reads from output/ppc/ CSV/JSON files and renders a 2×3 figure:

  [Panel 1] KPI Summary (text)         [Panel 2] Profit Zone Breakdown (bar)
  [Panel 3] Weekly Revenue Trend       [Panel 4] Weekly Cost & Tariff
  [Panel 5] Lot Gross Margin by Channel [Panel 6] Forward vs Backward Gap

Usage:
    python -m wom.ppc --chart [--output-dir output/ppc] [--save path/out.png]
    # or directly:
    python -c "from wom.ppc.ppc_cockpit import show_cockpit; show_cockpit()"
"""

from __future__ import annotations

import json
import os
from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd


# ── Color palette ────────────────────────────────────────────────────────────
C_REVENUE  = "#2196F3"   # blue
C_COST     = "#F44336"   # red
C_PROFIT   = "#4CAF50"   # green
C_TARIFF   = "#FF9800"   # orange
C_JP       = "#1565C0"   # dark blue
C_US       = "#6A1B9A"   # purple
C_BACKWARD = "#00BCD4"   # teal
C_PANEL_BG = "#FAFAFA"
C_HEADER   = "#37474F"


def _fmt(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    elif abs(v) >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:.0f}"


# ── Panel 1: KPI Summary ─────────────────────────────────────────────────────
def _draw_kpi_text(ax: plt.Axes, kpi: dict) -> None:
    ax.set_facecolor(C_PANEL_BG)
    ax.axis("off")
    cur = kpi["base_currency"]

    lines = [
        ("PPC KPI Summary", 0.95, 14, C_HEADER, "bold"),
        (f"Base currency: {cur}", 0.85, 9, "#607D8B", "normal"),
        ("", 0.77, 9, "black", "normal"),
        (f"Revenue       {_fmt(kpi['total_revenue_base'])} {cur}", 0.72, 10, C_REVENUE, "bold"),
        (f"Total Cost    {_fmt(kpi['total_cost_base'])} {cur}", 0.63, 10, C_COST, "bold"),
        (f"Gross Profit  {_fmt(kpi['gross_profit_base'])} {cur}", 0.54, 10, C_PROFIT, "bold"),
        (f"Gross Margin  {kpi['gross_margin_pct']:.1%}", 0.46, 10, C_PROFIT, "bold"),
        ("", 0.38, 9, "black", "normal"),
        (f"Tariff Cost   {_fmt(kpi['total_tariff_base'])} {cur}", 0.33, 9, C_TARIFF, "normal"),
        (f"MOM Profit    {_fmt(kpi['mom_profit_base'])} {cur}", 0.25, 9, "#795548", "normal"),
        ("", 0.17, 9, "black", "normal"),
        (f"JP Revenue    {_fmt(kpi['channel_jp_revenue_base'])} {cur}", 0.12, 9, C_JP, "normal"),
        (f"US Revenue    {_fmt(kpi['channel_us_revenue_base'])} {cur}", 0.05, 9, C_US, "normal"),
    ]
    for text, y, fs, color, weight in lines:
        ax.text(
            0.08, y, text,
            transform=ax.transAxes,
            fontsize=fs, color=color, fontweight=weight,
            va="top", fontfamily="monospace",
        )

    # Trust events badge
    tc = kpi.get("trust_event_count", 0)
    badge_color = "#F44336" if tc > 0 else "#4CAF50"
    badge_text  = f"⚠ {tc} trust event(s)" if tc > 0 else "✓ No trust events"
    ax.text(
        0.5, -0.02, badge_text,
        transform=ax.transAxes,
        fontsize=9, color="white", fontweight="bold",
        ha="center", va="bottom",
        bbox=dict(boxstyle="round,pad=0.4", fc=badge_color, ec="none"),
    )


# ── Panel 2: Profit Zone Breakdown ───────────────────────────────────────────
def _draw_profit_zone(ax: plt.Axes, pz: pd.DataFrame, cur: str) -> None:
    ax.set_facecolor(C_PANEL_BG)
    # Order: SUPPLIER → MOM → OPERATION → OUTBOUND
    zone_order = [
        "SUPPLIER_COST_BASE",
        "MOM_PLANT_PROFIT",
        "OPERATION_NODE_COST_BASE",
        "OUTBOUND_CHANNEL_PROFIT",
    ]
    labels = {
        "SUPPLIER_COST_BASE":        "Supplier",
        "MOM_PLANT_PROFIT":          "MOM Plant",
        "OPERATION_NODE_COST_BASE":  "DAD/Operation",
        "OUTBOUND_CHANNEL_PROFIT":   "Channel (JP+US)",
    }
    pz_idx = pz.set_index("profit_zone").reindex(zone_order).fillna(0.0)

    costs    = [pz_idx.loc[z, "cost_base"]  / 1e6 for z in zone_order]
    revenues = [pz_idx.loc[z, "revenue_base"] / 1e6 for z in zone_order]
    tariffs  = [pz_idx.loc[z, "tariff_base"] / 1e6 for z in zone_order]

    y = np.arange(len(zone_order))
    bar_h = 0.35

    ax.barh(y, costs,    bar_h, color=C_COST,    label="Cost",   alpha=0.85)
    ax.barh(y, revenues, bar_h, color=C_REVENUE,  label="Revenue", alpha=0.85,
            left=0, linestyle="--", linewidth=1.2, edgecolor="white")
    ax.barh(y - bar_h, tariffs, bar_h * 0.7, color=C_TARIFF, label="Tariff", alpha=0.75)

    ax.set_yticks(y)
    ax.set_yticklabels([labels[z] for z in zone_order], fontsize=9)
    ax.set_xlabel(f"Amount ({cur}, M)", fontsize=8)
    ax.set_title("Profit Zone Breakdown", fontsize=10, fontweight="bold", color=C_HEADER)
    ax.legend(fontsize=7, loc="lower right")
    ax.axvline(0, color="gray", linewidth=0.8)
    ax.grid(axis="x", alpha=0.3)


# ── Panel 3: Weekly Revenue Trend ────────────────────────────────────────────
def _draw_weekly_revenue(ax: plt.Axes, nw: pd.DataFrame, cur: str) -> None:
    ax.set_facecolor(C_PANEL_BG)
    ch = nw[nw["node_id"].isin(["JP_Channel", "US_Channel"])]
    weekly = ch.pivot_table(
        index="week", columns="node_id", values="revenue_base", aggfunc="sum"
    ).fillna(0.0)
    weeks = [w.replace("2026-", "") for w in weekly.index.tolist()]

    x = np.arange(len(weeks))
    jp_rev = weekly.get("JP_Channel", pd.Series(0.0, index=weekly.index)) / 1e6
    us_rev = weekly.get("US_Channel", pd.Series(0.0, index=weekly.index)) / 1e6

    ax.fill_between(x, jp_rev.values, alpha=0.35, color=C_JP)
    ax.fill_between(x, jp_rev.values, jp_rev.values + us_rev.values, alpha=0.35, color=C_US)
    ax.plot(x, jp_rev.values, color=C_JP, linewidth=1.8, label="JP Channel")
    ax.plot(x, jp_rev.values + us_rev.values, color=C_US, linewidth=1.8, label="JP+US Total")

    ax.set_xticks(x[::2])
    ax.set_xticklabels(weeks[::2], fontsize=7, rotation=30)
    ax.set_ylabel(f"{cur} (M)", fontsize=8)
    ax.set_title("Weekly Revenue Trend", fontsize=10, fontweight="bold", color=C_HEADER)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)


# ── Panel 4: Weekly Cost & Tariff ────────────────────────────────────────────
def _draw_weekly_cost(ax: plt.Axes, nw: pd.DataFrame, cur: str) -> None:
    ax.set_facecolor(C_PANEL_BG)
    weekly = nw.groupby("week")[["cost_base", "tariff_base"]].sum().reset_index()
    weeks  = [w.replace("2026-", "") for w in weekly["week"].tolist()]
    x = np.arange(len(weeks))

    cost   = weekly["cost_base"].values   / 1e6
    tariff = weekly["tariff_base"].values / 1e6
    op_cost = cost - tariff

    ax.bar(x, op_cost, color=C_COST,   alpha=0.75, label="Op Cost")
    ax.bar(x, tariff,  bottom=op_cost, color=C_TARIFF, alpha=0.85, label="Tariff")

    ax.set_xticks(x[::2])
    ax.set_xticklabels(weeks[::2], fontsize=7, rotation=30)
    ax.set_ylabel(f"{cur} (M)", fontsize=8)
    ax.set_title("Weekly Total Cost & Tariff", fontsize=10, fontweight="bold", color=C_HEADER)
    ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.3)


# ── Panel 5: Lot Gross Margin Distribution ───────────────────────────────────
def _draw_margin_dist(ax: plt.Axes, rec: pd.DataFrame) -> None:
    ax.set_facecolor(C_PANEL_BG)
    jp_margin = rec.loc[rec["channel_node"] == "JP_Channel", "gross_margin_pct"] * 100
    us_margin = rec.loc[rec["channel_node"] == "US_Channel", "gross_margin_pct"] * 100

    bp = ax.boxplot(
        [jp_margin.values, us_margin.values],
        labels=["JP Channel", "US Channel"],
        patch_artist=True,
        medianprops=dict(color="white", linewidth=2),
        whiskerprops=dict(linewidth=1.2),
        boxprops=dict(linewidth=1.2),
    )
    bp["boxes"][0].set_facecolor(C_JP)
    bp["boxes"][0].set_alpha(0.7)
    if len(bp["boxes"]) > 1:
        bp["boxes"][1].set_facecolor(C_US)
        bp["boxes"][1].set_alpha(0.7)

    # Scatter overlay
    jitter = lambda n: np.random.uniform(-0.08, 0.08, n)
    ax.scatter(
        np.ones(len(jp_margin)) + jitter(len(jp_margin)),
        jp_margin.values, color=C_JP, alpha=0.25, s=10, zorder=3
    )
    ax.scatter(
        2 * np.ones(len(us_margin)) + jitter(len(us_margin)),
        us_margin.values, color=C_US, alpha=0.25, s=10, zorder=3
    )

    ax.set_ylabel("Gross Margin (%)", fontsize=8)
    ax.set_title("Lot Gross Margin by Channel", fontsize=10, fontweight="bold", color=C_HEADER)
    ax.grid(axis="y", alpha=0.3)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.1f%%"))


# ── Panel 6: Forward vs Backward (weekly avg) ────────────────────────────────
def _draw_fwd_bwd(ax: plt.Axes, rec: pd.DataFrame, cur: str) -> None:
    ax.set_facecolor(C_PANEL_BG)
    agg = (
        rec.groupby(["week", "channel_node"])[
            ["forward_cost_base", "backward_allowable_base", "market_revenue_base"]
        ].mean().reset_index()
    )
    jp = agg[agg["channel_node"] == "JP_Channel"].sort_values("week")
    us = agg[agg["channel_node"] == "US_Channel"].sort_values("week")
    weeks = jp["week"].str.replace("2026-", "").tolist()
    x = np.arange(len(weeks))

    w = 0.28
    ax.bar(x - w, jp["forward_cost_base"].values / 1e3,       w, color=C_COST,     alpha=0.8, label="JP Forward Cost")
    ax.bar(x,     jp["backward_allowable_base"].values / 1e3, w, color=C_BACKWARD, alpha=0.8, label="JP Backward Allow.")
    ax.bar(x + w, jp["market_revenue_base"].values / 1e3,     w, color=C_JP,       alpha=0.8, label="JP Market Rev.")

    # US as a line overlay (secondary)
    ax2 = ax.twinx()
    ax2.plot(x, us["forward_cost_base"].values / 1e3,       color=C_COST,     linewidth=1.5, linestyle="--")
    ax2.plot(x, us["backward_allowable_base"].values / 1e3, color=C_BACKWARD, linewidth=1.5, linestyle="--")
    ax2.plot(x, us["market_revenue_base"].values / 1e3,     color=C_US,       linewidth=1.5, linestyle="--")
    ax2.set_ylabel("US Channel (K JPY) --", fontsize=7, color="#888")
    ax2.tick_params(axis="y", labelsize=7)

    ax.set_xticks(x[::2])
    ax.set_xticklabels(weeks[::2], fontsize=7, rotation=30)
    ax.set_ylabel(f"JP Channel (K {cur})", fontsize=8)
    ax.set_title("Forward vs Backward vs Revenue (avg/lot)", fontsize=9, fontweight="bold", color=C_HEADER)
    ax.legend(fontsize=6, loc="upper left")
    ax.grid(axis="y", alpha=0.3)


# ── Main entry ───────────────────────────────────────────────────────────────
def show_cockpit(
    output_dir: str = "output/ppc",
    save_path: Optional[str] = None,
    show: bool = True,
) -> plt.Figure:
    """
    Load PPC output CSVs from `output_dir` and render the PPC Cockpit.

    Parameters
    ----------
    output_dir : str
        Directory containing ppc_*.csv and ppc_kpi_summary.json
    save_path : str, optional
        If given, save figure to this path (PNG/PDF)
    show : bool
        If True, call plt.show() (blocks until window closed)

    Returns
    -------
    matplotlib.figure.Figure
    """
    # ── Load ────────────────────────────────────────────────────────────
    kpi_path = os.path.join(output_dir, "ppc_kpi_summary.json")
    if not os.path.exists(kpi_path):
        raise FileNotFoundError(
            f"PPC output not found at '{output_dir}'. "
            "Run  python -m wom.ppc  first."
        )

    with open(kpi_path, encoding="utf-8") as f:
        kpi = json.load(f)

    pz  = pd.read_csv(os.path.join(output_dir, "ppc_profit_zone_summary.csv"))
    nw  = pd.read_csv(os.path.join(output_dir, "ppc_node_week_summary.csv"))
    rec = pd.read_csv(os.path.join(output_dir, "ppc_lot_reconciliation.csv"))
    cur = kpi["base_currency"]

    # ── Figure layout ────────────────────────────────────────────────────
    fig = plt.figure(figsize=(18, 10), facecolor="white")
    fig.suptitle(
        "WOM PPC Evaluation Cockpit",
        fontsize=14, fontweight="bold", color=C_HEADER, y=0.99,
    )

    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.42, wspace=0.38)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    ax4 = fig.add_subplot(gs[1, 0])
    ax5 = fig.add_subplot(gs[1, 1])
    ax6 = fig.add_subplot(gs[1, 2])

    # ── Draw panels ──────────────────────────────────────────────────────
    _draw_kpi_text(ax1, kpi)
    _draw_profit_zone(ax2, pz, cur)
    _draw_weekly_revenue(ax3, nw, cur)
    _draw_weekly_cost(ax4, nw, cur)
    _draw_margin_dist(ax5, rec)
    _draw_fwd_bwd(ax6, rec, cur)

    # ── Subtitle line ────────────────────────────────────────────────────
    subtitle = (
        f"Scenario: IPHONE  |  Supplier_CN(CNY) → MOM_China → DAD_Japan → JP/US_Channel  "
        f"|  CN→JP tariff 5%  JP→US tariff 10%  |  Base: {cur}"
    )
    fig.text(0.5, 0.965, subtitle, ha="center", fontsize=8, color="#78909C")

    # ── Save / Show ──────────────────────────────────────────────────────
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"[PPC Cockpit] Saved → {save_path}")

    if show:
        plt.show()

    return fig
