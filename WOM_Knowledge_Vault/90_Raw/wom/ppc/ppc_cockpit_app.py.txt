"""
wom/ppc/ppc_cockpit_app.py
==========================
PPC Evaluation Cockpit — Interactive Tkinter Application (B0).

Filter controls:
  - SKU (product_id) dropdown
  - Channel dropdown (All channels in data)
  - Period: Start week / End week spinboxes
  - Aggregation: Weekly / Monthly / Quarterly radio buttons

Usage:
    python -m wom.ppc --app [--output-dir output/ppc]

Architecture note:
    PPCCockpitApp is a tk.Frame subclass so it can later be
    embedded in the WOM GUI Management tab (B1 integration).
"""

from __future__ import annotations

import json
import os
from typing import Optional, List

import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import pandas as pd


# ── Color palette ──────────────────────────────────────────────────────────────
C_REVENUE  = "#2196F3"
C_COST     = "#F44336"
C_PROFIT   = "#4CAF50"
C_TARIFF   = "#FF9800"
C_BACKWARD = "#00BCD4"
C_PANEL_BG = "#FAFAFA"
C_HEADER   = "#37474F"
C_SIDEBAR  = "#ECEFF1"

# Dynamic color palette for multiple channels
CHANNEL_COLORS = [
    "#1565C0", "#6A1B9A", "#00695C", "#E65100",
    "#4527A0", "#558B2F", "#AD1457", "#37474F",
]

# The 5 PPC trust-event types (see wom/ppc/ppc_reconcile.py, run_reconciliation()).
# Order here drives both the breakdown bar chart's row order and severity
# color choice (dark red = most severe/direct, purple = market-comparison).
TRUST_EVENT_TYPES = [
    "NEGATIVE_MARGIN",
    "CHANNEL_MARGIN_TOO_LOW",
    "MOM_PROFIT_TOO_LOW",
    "TARIFF_SHOCK",
    "LANDED_COST_EXCEEDS_MARKET",
]
TRUST_EVENT_COLORS = {
    "NEGATIVE_MARGIN":            "#B71C1C",
    "CHANNEL_MARGIN_TOO_LOW":     "#E65100",
    "MOM_PROFIT_TOO_LOW":         "#F9A825",
    "TARIFF_SHOCK":               "#FF9800",
    "LANDED_COST_EXCEEDS_MARKET": "#6A1B9A",
}
TRUST_EVENT_LABELS = {
    "NEGATIVE_MARGIN":            "Negative Margin",
    "CHANNEL_MARGIN_TOO_LOW":     "Channel Margin < 5%",
    "MOM_PROFIT_TOO_LOW":         "MOM Profit < 0",
    "TARIFF_SHOCK":               "Tariff Shock > 20%",
    "LANDED_COST_EXCEEDS_MARKET": "Landed Cost > Market",
}


def _channel_short(ch: str) -> str:
    """'Retail_AMER' → 'AMER', 'JP_Channel' → 'JP'"""
    return ch.replace("Retail_", "").replace("_Channel", "")


def _fmt(v: float) -> str:
    if abs(v) >= 1_000_000_000_000:
        return f"{v/1_000_000_000_000:.2f}T"
    elif abs(v) >= 1_000_000_000:
        return f"{v/1_000_000_000:.2f}B"
    elif abs(v) >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    elif abs(v) >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:.0f}"


def _week_to_order(week: str) -> int:
    """'2026-W03' -> 202603"""
    try:
        year, wk = week.split("-W")
        return int(year) * 100 + int(wk)
    except Exception:
        return 0


def _short_period(p: str) -> str:
    """Remove year prefix for axis labels: '2027-W03' → 'W03', 'M01' → 'M01'"""
    if "-W" in p:
        parts = p.split("-W")
        return f"W{parts[1]}"
    return p


def _aggregate_weekly(df_nw: pd.DataFrame, df_rec: pd.DataFrame,
                      granularity: str) -> tuple:
    if granularity == "weekly":
        weeks = sorted(df_nw["week"].unique(), key=_week_to_order)
        return df_nw.copy(), df_rec.copy(), weeks

    weeks_sorted = sorted(df_nw["week"].unique(), key=_week_to_order)
    n = len(weeks_sorted)

    if granularity == "monthly":
        chunk = 4
        label_fmt = "M{:02d}"
    else:  # quarterly
        chunk = 13
        label_fmt = "Q{:02d}"

    week_to_period: dict = {}
    period_idx = 1
    for i, w in enumerate(weeks_sorted):
        week_to_period[w] = label_fmt.format(period_idx)
        if (i + 1) % chunk == 0:
            period_idx += 1

    df_nw  = df_nw.copy()
    df_rec = df_rec.copy()
    df_nw["period"]  = df_nw["week"].map(week_to_period)
    df_rec["period"] = df_rec["week"].map(week_to_period)

    nw_agg = (
        df_nw.groupby(["node_id", "period", "product_id"])[
            ["revenue_base", "cost_base", "tariff_base", "gross_profit_base"]
        ].sum().reset_index().rename(columns={"period": "week"})
    )
    rec_agg = df_rec.copy()
    rec_agg["week"] = rec_agg["period"]

    periods = sorted(set(week_to_period.values()))
    return nw_agg, rec_agg, periods


# ── Chart drawing helpers ─────────────────────────────────────────────────────

def _draw_kpi_text(ax, kpi: dict, rec_filtered: pd.DataFrame, cur: str) -> None:
    ax.set_facecolor(C_PANEL_BG)
    ax.axis("off")

    # rec_filtered's *_base columns are PER-UNIT amounts; "qty" (added to
    # ppc_lot_reconciliation.csv alongside the qty-aggregation fix) carries
    # the real physical quantity of each aggregated weekly lot-record, so
    # true absolute totals require multiplying by it. Falls back to 1 if
    # the qty column is missing (older output/ppc/ from before this fix).
    _qty = rec_filtered["qty"] if "qty" in rec_filtered.columns else 1
    total_rev    = (rec_filtered["market_revenue_base"] * _qty).sum()
    total_cost   = (rec_filtered["forward_cost_base"] * _qty).sum()
    gross_profit = total_rev - total_cost
    gross_margin = gross_profit / total_rev if total_rev > 0 else 0.0
    n_lots       = len(rec_filtered.dropna(subset=["forward_cost_base"]))
    tariff       = ((rec_filtered["tariff_in_base"] + rec_filtered["tariff_out_base"]) * _qty).sum()

    # Value lines use a short right-aligned label (<=11 chars) + _fmt()'s
    # compact K/M/B/T suffix so the panel stays readable even for cases
    # with very large absolute currency values (see Open Question 6 in
    # requests/smartx-2027-2029-fix-request-letter.md).
    lines = [
        ("PPC KPI Summary", 0.95, 11, C_HEADER, "bold"),
        (f"Base currency: {cur}", 0.87, 7.5, "#607D8B", "normal"),
        (f"Lots: {n_lots}", 0.80, 7.5, "#607D8B", "normal"),
        ("", 0.74, 8, "black", "normal"),
        (f"Revenue     {_fmt(total_rev)} {cur}", 0.68, 8.5, C_REVENUE, "bold"),
        (f"Total Cost  {_fmt(total_cost)} {cur}", 0.60, 8.5, C_COST, "bold"),
        (f"Gross Prft  {_fmt(gross_profit)} {cur}", 0.52, 8.5, C_PROFIT, "bold"),
        (f"Gross Marg  {gross_margin:.1%}", 0.44, 8.5, C_PROFIT, "bold"),
        ("", 0.37, 8, "black", "normal"),
        (f"Tariff Cost {_fmt(tariff)} {cur}", 0.31, 8, C_TARIFF, "normal"),
    ]

    # Dynamic channel revenue breakdown (top 3 channels -- capped at 3, not
    # 4, so the block always clears the trust-event badge below it; SKU=All
    # views with many channels were previously overlapping the badge).
    MAX_CHANNELS = 3
    if "channel_node" in rec_filtered.columns:
        _rev_totaled = rec_filtered["market_revenue_base"] * _qty
        ch_rev = (
            _rev_totaled.groupby(rec_filtered["channel_node"])
            .sum().sort_values(ascending=False)
        )
        y_pos = 0.17
        lines += [("", 0.22, 8, "black", "normal")]
        for i, (ch_name, ch_val) in enumerate(ch_rev.head(MAX_CHANNELS).items()):
            color = CHANNEL_COLORS[i % len(CHANNEL_COLORS)]
            label = _channel_short(ch_name)
            lines += [(f"{label:<7} {_fmt(ch_val)} {cur}", y_pos, 7, color, "normal")]
            y_pos -= 0.05

    # clip_on=True: text is confined to this subplot's own bounding box, so
    # unusually long value strings are clipped rather than bleeding
    # visually into the neighboring "Profit Zone Breakdown" panel.
    for text, y, fs, color, weight in lines:
        ax.text(0.04, y, text, transform=ax.transAxes,
                fontsize=fs, color=color, fontweight=weight,
                va="top", fontfamily="monospace", clip_on=True)

    # Badge sits well below the (fixed-length, MAX_CHANNELS-capped) text
    # block above -- with MAX_CHANNELS=3 the lowest text line is at
    # y=0.17-2*0.05=0.07, so y=-0.12 leaves a clear gap for the badge's
    # own font+padding box, regardless of how many channels are shown.
    #
    # NOTE (2026-07-11 fix): previously this badge always showed
    # kpi["trust_event_count"] -- a single number pre-computed over the
    # FULL dataset (all weeks/SKUs/channels) at engine-run time, ignoring
    # the sidebar's Start/End Week, SKU and Channel filters. That was
    # inconsistent with every other figure in this same panel (Revenue,
    # Total Cost, Gross Profit, Gross Margin, and the channel breakdown
    # below), which are all computed from rec_filtered and DO respect the
    # sidebar filters -- and inconsistent with the new Trust Event Type
    # Breakdown panel (_draw_trust_breakdown), which also uses
    # rec_filtered. Recomputing from rec_filtered here makes all three
    # (badge / breakdown panel / underlying filtered data) agree.
    if "trust_events_fired" in rec_filtered.columns:
        trust = sum(_count_trust_events(rec_filtered).values())
    else:
        # Backward-compat fallback for older output/ppc/ dirs generated
        # before trust_events_fired was added to ppc_lot_reconciliation.csv.
        trust = kpi.get("trust_event_count", 0)
    badge_color = "#F44336" if trust > 0 else "#4CAF50"
    badge_text  = f"! {trust} trust event(s)" if trust > 0 else "OK  No trust events"
    ax.text(0.5, -0.12, badge_text, transform=ax.transAxes,
            fontsize=7.5, color="white", fontweight="bold", ha="center", va="bottom",
            bbox=dict(boxstyle="round,pad=0.35", fc=badge_color, ec="none"),
            clip_on=False)


def _draw_profit_zone(ax, ev_filtered: pd.DataFrame, cur: str) -> None:
    ax.set_facecolor(C_PANEL_BG)
    COST_TYPES = {
        "supplier_cost", "conversion_cost", "logistics_cost",
        "insurance_cost", "tariff_cost", "warehouse_cost",
        "sga_cost", "marketing_cost",
    }
    zone_order = [
        "SUPPLIER_COST_BASE", "MOM_PLANT_PROFIT",
        "OPERATION_NODE_COST_BASE", "OUTBOUND_CHANNEL_PROFIT",
    ]
    labels = {
        "SUPPLIER_COST_BASE":        "Supplier",
        "MOM_PLANT_PROFIT":          "MOM Plant",
        "OPERATION_NODE_COST_BASE":  "DAD/Operation",
        "OUTBOUND_CHANNEL_PROFIT":   "Channel (All)",
    }
    ev_f = ev_filtered.dropna(subset=["profit_zone"]).copy()
    # ev_f["amount_base"] is PER-UNIT (see ppc_models.PPCEvent docstring);
    # ev_f["qty"] carries the real quantity of the underlying aggregated
    # weekly lot-record. Multiply to get an absolute-currency total.
    _ev_qty = ev_f["qty"] if "qty" in ev_f.columns else 1
    ev_f["_amount_total"] = ev_f["amount_base"] * _ev_qty

    def _zone_sum(zone, is_rev):
        mask = ev_f["profit_zone"] == zone
        if is_rev:
            return ev_f.loc[mask & (ev_f["ppc_event_type"] == "market_revenue"), "_amount_total"].sum()
        return ev_f.loc[mask & (ev_f["ppc_event_type"].isin(COST_TYPES)), "_amount_total"].sum()

    costs    = [_zone_sum(z, False) / 1e6 for z in zone_order]
    revenues = [_zone_sum(z, True)  / 1e6 for z in zone_order]
    tariffs  = [
        ev_f.loc[(ev_f["profit_zone"] == z) & (ev_f["ppc_event_type"] == "tariff_cost"),
                 "_amount_total"].sum() / 1e6
        for z in zone_order
    ]

    y = np.arange(len(zone_order))
    bh = 0.35
    ax.barh(y, costs,    bh, color=C_COST,   label="Cost",    alpha=0.85)
    ax.barh(y, revenues, bh, color=C_REVENUE, label="Revenue", alpha=0.85)
    ax.barh(y - bh, tariffs, bh * 0.7, color=C_TARIFF, label="Tariff", alpha=0.75)
    ax.set_yticks(y)
    ax.set_yticklabels([labels.get(z, z) for z in zone_order], fontsize=9)
    ax.set_xlabel(f"Amount ({cur}, M)", fontsize=8)
    ax.set_title("Profit Zone Breakdown", fontsize=10, fontweight="bold", color=C_HEADER)
    ax.legend(fontsize=7, loc="lower right")
    ax.axvline(0, color="gray", linewidth=0.8)
    ax.grid(axis="x", alpha=0.3)


def _draw_weekly_revenue(ax, nw: pd.DataFrame, periods: list, cur: str) -> None:
    """Revenue trend — dynamically use all channel nodes with revenue > 0."""
    ax.set_facecolor(C_PANEL_BG)

    # Find channel-like nodes: nodes that have revenue (not zero)
    node_rev = nw.groupby("node_id")["revenue_base"].sum()
    channel_nodes = node_rev[node_rev > 0].sort_values(ascending=False).index.tolist()

    if not channel_nodes:
        ax.text(0.5, 0.5, "No revenue data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Revenue Trend", fontsize=10, fontweight="bold", color=C_HEADER)
        return

    # Limit to top 6 channels
    top_channels = channel_nodes[:6]
    weekly = nw[nw["node_id"].isin(top_channels)].pivot_table(
        index="week", columns="node_id", values="revenue_base", aggfunc="sum"
    ).reindex(periods).fillna(0.0)

    x = np.arange(len(periods))
    xlabels = [_short_period(p) for p in periods]

    cumulative = np.zeros(len(periods))
    for i, ch in enumerate(top_channels):
        if ch not in weekly.columns:
            continue
        vals = weekly[ch].values / 1e6
        color = CHANNEL_COLORS[i % len(CHANNEL_COLORS)]
        ax.fill_between(x, cumulative, cumulative + vals, alpha=0.25, color=color)
        ax.plot(x, cumulative + vals, color=color, linewidth=1.6,
                label=_channel_short(ch))
        cumulative = cumulative + vals

    step = max(1, len(periods) // 8)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(xlabels[::step], fontsize=7, rotation=30)
    ax.set_ylabel(f"{cur} (M)", fontsize=8)
    ax.set_title("Revenue Trend (by Channel)", fontsize=10, fontweight="bold", color=C_HEADER)
    ax.legend(fontsize=6, loc="upper left", ncol=2)
    ax.grid(alpha=0.3)


def _draw_weekly_cost(ax, nw: pd.DataFrame, periods: list, cur: str) -> None:
    ax.set_facecolor(C_PANEL_BG)
    weekly = nw.groupby("week")[["cost_base", "tariff_base"]].sum().reindex(periods).fillna(0.0)
    x = np.arange(len(periods))
    xlabels = [_short_period(p) for p in periods]

    cost   = weekly["cost_base"].values   / 1e6
    tariff = weekly["tariff_base"].values / 1e6
    op     = cost - tariff

    ax.bar(x, op,     color=C_COST,   alpha=0.75, label="Op Cost")
    ax.bar(x, tariff, bottom=op, color=C_TARIFF, alpha=0.85, label="Tariff")

    step = max(1, len(periods) // 8)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(xlabels[::step], fontsize=7, rotation=30)
    ax.set_ylabel(f"{cur} (M)", fontsize=8)
    ax.set_title("Total Cost & Tariff", fontsize=10, fontweight="bold", color=C_HEADER)
    ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.3)


def _draw_margin_dist(ax, rec: pd.DataFrame, selected_channels: list) -> None:
    """Lot Gross Margin boxplot — uses actual channels from data."""
    ax.set_facecolor(C_PANEL_BG)

    # Determine which channels to show
    available = sorted(rec["channel_node"].dropna().unique().tolist())
    if not available:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Lot Gross Margin by Channel", fontsize=10, fontweight="bold", color=C_HEADER)
        return

    if len(selected_channels) == 1 and selected_channels[0] != "Both":
        use_channels = [ch for ch in selected_channels if ch in available]
    else:
        use_channels = available

    data, xlabels, colors = [], [], []
    for i, ch in enumerate(use_channels[:8]):
        vals = rec.loc[rec["channel_node"] == ch, "gross_margin_pct"].dropna() * 100
        if len(vals) > 0:
            data.append(vals.values)
            xlabels.append(_channel_short(ch))
            colors.append(CHANNEL_COLORS[i % len(CHANNEL_COLORS)])

    if not data:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Lot Gross Margin by Channel", fontsize=10, fontweight="bold", color=C_HEADER)
        return

    bp = ax.boxplot(data, labels=xlabels, patch_artist=True,
                    medianprops=dict(color="white", linewidth=2),
                    whiskerprops=dict(linewidth=1.2),
                    boxprops=dict(linewidth=1.2))
    for box, color in zip(bp["boxes"], colors):
        box.set_facecolor(color)
        box.set_alpha(0.7)

    for i, (vals, color) in enumerate(zip(data, colors)):
        jitter = np.random.uniform(-0.08, 0.08, len(vals))
        ax.scatter(np.full(len(vals), i + 1) + jitter, vals,
                   color=color, alpha=0.25, s=10, zorder=3)

    ax.set_ylabel("Gross Margin (%)", fontsize=8)
    ax.set_title("Lot Gross Margin by Channel", fontsize=10, fontweight="bold", color=C_HEADER)
    ax.grid(axis="y", alpha=0.3)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.1f%%"))
    if len(xlabels) > 4:
        ax.tick_params(axis="x", labelsize=7, rotation=20)


def _draw_fwd_bwd(ax, rec: pd.DataFrame, periods: list, cur: str) -> None:
    """Forward vs Backward vs Revenue — top 2 channels, dynamic."""
    ax.set_facecolor(C_PANEL_BG)

    # Find top 2 channels by revenue
    if rec.empty or "channel_node" not in rec.columns:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Forward vs Backward vs Revenue", fontsize=9, fontweight="bold", color=C_HEADER)
        return

    # Rank channels by real total revenue (market_revenue_base is per-unit;
    # weight by qty so a channel with fewer, larger lots isn't under-ranked).
    _rank_qty = rec["qty"] if "qty" in rec.columns else 1
    top_channels = (
        (rec["market_revenue_base"] * _rank_qty).groupby(rec["channel_node"]).sum()
        .sort_values(ascending=False).index.tolist()
    )
    if not top_channels:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Forward vs Backward vs Revenue", fontsize=9, fontweight="bold", color=C_HEADER)
        return

    ch1 = top_channels[0]
    ch2 = top_channels[1] if len(top_channels) > 1 else None

    agg = (
        rec.dropna(subset=["forward_cost_base"])
        .groupby(["week", "channel_node"])[
            ["forward_cost_base", "backward_allowable_base", "market_revenue_base"]
        ].mean().reset_index()
    )

    def _get_ch(ch):
        return agg[agg["channel_node"] == ch].set_index("week").reindex(periods).fillna(0.0)

    d1 = _get_ch(ch1)
    x = np.arange(len(periods))
    xlabels = [_short_period(p) for p in periods]
    color1 = CHANNEL_COLORS[0]

    w = 0.28
    ax.bar(x - w, d1["forward_cost_base"].values / 1e3,       w, color=C_COST,     alpha=0.8,
           label=f"{_channel_short(ch1)} Fwd Cost")
    ax.bar(x,     d1["backward_allowable_base"].values / 1e3, w, color=C_BACKWARD, alpha=0.8,
           label=f"{_channel_short(ch1)} Bwd Allow.")
    ax.bar(x + w, d1["market_revenue_base"].values / 1e3,     w, color=color1,     alpha=0.8,
           label=f"{_channel_short(ch1)} Revenue")

    if ch2:
        d2 = _get_ch(ch2)
        color2 = CHANNEL_COLORS[1]
        ax2 = ax.twinx()
        ax2.plot(x, d2["forward_cost_base"].values / 1e3,       color=C_COST,     linewidth=1.5, linestyle="--")
        ax2.plot(x, d2["backward_allowable_base"].values / 1e3, color=C_BACKWARD, linewidth=1.5, linestyle="--")
        ax2.plot(x, d2["market_revenue_base"].values / 1e3,     color=color2,      linewidth=1.5, linestyle="--")
        ax2.set_ylabel(f"{_channel_short(ch2)} (K {cur}) --", fontsize=7, color="#888")
        ax2.tick_params(axis="y", labelsize=7)

    step = max(1, len(periods) // 8)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(xlabels[::step], fontsize=7, rotation=30)
    ax.set_ylabel(f"{_channel_short(ch1)} (K {cur})", fontsize=8)
    ax.set_title("Forward vs Backward vs Revenue (avg/lot)", fontsize=9, fontweight="bold", color=C_HEADER)
    ax.legend(fontsize=6, loc="upper left")
    ax.grid(axis="y", alpha=0.3)


def _draw_waterfall(ax, ev_filtered: pd.DataFrame, cur: str) -> None:
    """
    Phase 3: Cost Waterfall — FOB/CIF/DAD Incoterm 区別付き。
    cost_phase 列（EXW / MOM / FOB / CIF / TARIFF / DAD / SGA）で費用を分類。
    後方互換: cost_phase 列が存在しない場合は Phase 2 フォールバック（全 logistics を "Logistics" に集約）。

    Descending waterfall:
      Revenue     → anchored at 0 (positive, full-height bar)
      Supplier    → EXW 原材料調達費
      Mfg Conv    → MOM 製造転換費（Factory conversion のみ）
      CIF Freight → 国際輸送＋輸入港費用（保税倉庫コストを含む）※輸入品のみ
      Tariff      → 関税（輸入品のみ）
      DAD Ops     → 国内流通費（保税後陸送＋DC費用）
      SGA         → 販管費
      Marketing   → マーケティング費（ゼロ時スキップ）
      Gross Profit → anchored at 0 (green if positive, red if negative)
    """
    ax.set_facecolor(C_PANEL_BG)
    n_lots = ev_filtered[ev_filtered["ppc_event_type"] == "market_revenue"]["lot_id"].nunique()
    if n_lots == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Cost Waterfall (avg / lot)", fontsize=10, fontweight="bold", color=C_HEADER)
        return

    has_phase = "cost_phase" in ev_filtered.columns

    def _avg(*types):
        return ev_filtered[ev_filtered["ppc_event_type"].isin(types)]["amount_base"].sum() / n_lots

    def _avg_phase(phase):
        if not has_phase:
            return 0.0
        return ev_filtered[ev_filtered["cost_phase"] == phase]["amount_base"].sum() / n_lots

    revenue  = _avg("market_revenue")
    supplier = _avg("supplier_cost")
    tariff   = _avg("tariff_cost")
    sga      = _avg("sga_cost")
    marketing = _avg("marketing_cost")

    if has_phase:
        # Phase 3: FOB/CIF/DAD 分類
        fob_cost  = _avg_phase("FOB")    # FOB 国内輸送（工場→輸出港）
        mfg_conv  = _avg_phase("MOM")    # 製造転換費（Factory conversion）
        cif_cost  = _avg_phase("CIF")    # CIF 国際輸送＋保税倉庫費
        dad_ops   = _avg_phase("DAD")    # 国内 DAD 流通費
        # Build steps with FOB/CIF/DAD breakdown
        deductions = [
            ("Supplier",     supplier,  C_COST,     False),
            ("FOB\nFreight", fob_cost,  "#43A047",  False),  # green (domestic to port)
            ("Mfg\nConv",   mfg_conv,  "#EF5350",  False),
            ("CIF\nFreight", cif_cost,  "#0288D1",  False),  # ocean blue
            ("Tariff",       tariff,    C_TARIFF,   False),
            ("DAD\nOps",     dad_ops,   "#78909C",  False),  # slate gray
            ("SGA",          sga,       "#AB47BC",  False),
            ("Marketing",    marketing, "#EC407A",  False),
        ]
        title = "Cost Waterfall — FOB / CIF / DAD (avg / lot)"
    else:
        # Phase 2 フォールバック（cost_phase 列なし）
        mfg_conv  = _avg("conversion_cost")
        logistics = _avg("logistics_cost", "insurance_cost")
        deductions = [
            ("Supplier",   supplier,   C_COST,    False),
            ("Conversion", mfg_conv,   "#EF5350", False),
            ("Logistics",  logistics,  "#FF7043", False),
            ("Tariff",     tariff,     C_TARIFF,  False),
            ("SGA",        sga,        "#AB47BC", False),
            ("Marketing",  marketing, "#EC407A", False),
        ]
        title = "Cost Waterfall — avg / lot"

    # Build steps: (label, amount, bar_color, is_total)
    # Zero-value deductions are skipped to keep the chart clean
    steps = [("Revenue", revenue, C_REVENUE, True)]
    steps += [(lbl, val, col, tot) for lbl, val, col, tot in deductions if val > 0.1]
    gross_profit = revenue - sum(v for _, v, _, t in steps if not t)
    gp_color = C_PROFIT if gross_profit >= 0 else C_COST
    steps.append(("Gross\nProfit", abs(gross_profit), gp_color, True))

    labels   = [s[0] for s in steps]
    amounts  = [s[1] for s in steps]
    colors   = [s[2] for s in steps]
    is_total = [s[3] for s in steps]

    # Waterfall bottoms:
    #   total bars (Revenue / Gross Profit) → bottom = 0
    #   cost bars → float from (running - cost) to running; running decreases
    running = revenue
    bottoms: list = []
    for amt, tot in zip(amounts, is_total):
        if tot:
            bottoms.append(0.0)
        else:
            bottoms.append(running - amt)
            running -= amt

    x = np.arange(len(labels))

    ax.bar(x, amounts, bottom=bottoms, color=colors, alpha=0.85, width=0.65,
           edgecolor="white", linewidth=0.5)

    # Connector dashes between adjacent cost bars (at the running level)
    for i in range(len(steps)):
        if not is_total[i] and i < len(steps) - 1:
            ax.plot([x[i] + 0.325, x[i + 1] - 0.325],
                    [bottoms[i], bottoms[i]],
                    color="#90A4AE", linewidth=0.8, linestyle="--")

    # Value labels inside bars
    for xi, (amt, bot) in enumerate(zip(amounts, bottoms)):
        ax.text(xi, bot + amt / 2, _fmt(amt),
                ha="center", va="center",
                fontsize=8, fontweight="bold", color="black")

    # GM% badge
    gm_pct = gross_profit / revenue * 100 if revenue > 0 else 0.0
    ax.text(0.99, 0.97, f"GM: {gm_pct:.1f}%",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=10, fontweight="bold", color=gp_color,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=gp_color, alpha=0.85))

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel(f"{cur} / lot", fontsize=8)
    ax.set_title(title, fontsize=10, fontweight="bold", color=C_HEADER)
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(-revenue * 0.05, revenue * 1.08)


def _count_trust_events(rec: pd.DataFrame) -> dict:
    """
    Tally lot_reconciliation's pipe-separated 'trust_events_fired' column
    into per-type lot counts (a lot with 2 events fires contributes to 2
    type counts). Returns a dict keyed by every TRUST_EVENT_TYPES entry
    (0 if absent), so callers can rely on a stable key set.
    """
    counts = {t: 0 for t in TRUST_EVENT_TYPES}
    if "trust_events_fired" not in rec.columns:
        return counts
    for s in rec["trust_events_fired"].dropna():
        s = str(s).strip()
        if not s:
            continue
        for t in s.split("|"):
            t = t.strip()
            if t in counts:
                counts[t] += 1
    return counts


def _draw_trust_breakdown(ax, rec_filtered: pd.DataFrame) -> list:
    """
    Trust Event Type Breakdown — horizontal bar chart of lot counts per
    trust-event type (5 types), for the currently-filtered
    lot_reconciliation data.

    Returns a list of (bar_patch, event_type, count) tuples so
    PPCCockpitApp._on_canvas_click can hit-test a mouse click against a
    specific bar and open the matching Lot/Node/Week drill-down window.
    """
    ax.set_facecolor(C_PANEL_BG)
    counts = _count_trust_events(rec_filtered)
    values = [counts[t] for t in TRUST_EVENT_TYPES]
    colors = [TRUST_EVENT_COLORS[t] for t in TRUST_EVENT_TYPES]
    labels = [TRUST_EVENT_LABELS[t] for t in TRUST_EVENT_TYPES]
    total = sum(values)

    y = np.arange(len(TRUST_EVENT_TYPES))
    bars = ax.barh(y, values, color=colors, alpha=0.85, height=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Lot count", fontsize=8)
    ax.set_title(
        f"Trust Event Type Breakdown  (total: {total} — click a bar to drill down)",
        fontsize=10, fontweight="bold", color=C_HEADER,
    )
    ax.grid(axis="x", alpha=0.3)

    max_v = max(values) if values else 0
    for bar, v in zip(bars, values):
        if v == 0:
            continue
        ax.text(bar.get_width() + max(max_v, 1) * 0.015,
                 bar.get_y() + bar.get_height() / 2, str(v),
                 va="center", fontsize=8, fontweight="bold", color=C_HEADER)

    if total == 0:
        ax.text(0.5, 0.5, "No trust events in current filter",
                ha="center", va="center", transform=ax.transAxes,
                fontsize=9, color="#78909C")

    return list(zip(bars, TRUST_EVENT_TYPES, values))


# ── Main App Class ────────────────────────────────────────────────────────────

class PPCCockpitApp(tk.Frame):
    """
    Interactive PPC Cockpit as a Tk Frame.
    Can be embedded in the WOM GUI Management tab (B1 integration).
    """

    def __init__(self, parent: tk.Widget, output_dir: str = "output/ppc"):
        super().__init__(parent, bg=C_SIDEBAR)
        self.output_dir = output_dir
        self._load_data()
        self._build_ui()
        self._redraw()

    # ── Data loading ──────────────────────────────────────────────────────
    def _load_data(self) -> None:
        kpi_path = os.path.join(self.output_dir, "ppc_kpi_summary.json")
        if not os.path.exists(kpi_path):
            raise FileNotFoundError(
                f"PPC output not found at '{self.output_dir}'. "
                "Run  python -m wom.ppc  first."
            )
        with open(kpi_path, encoding="utf-8") as f:
            self._kpi = json.load(f)
        self._cur = self._kpi["base_currency"]
        self._nw  = pd.read_csv(os.path.join(self.output_dir, "ppc_node_week_summary.csv"))
        self._rec = pd.read_csv(os.path.join(self.output_dir, "ppc_lot_reconciliation.csv"))
        self._ev  = pd.read_csv(os.path.join(self.output_dir, "ppc_event_ledger.csv"), low_memory=False)

        # Clean rows
        self._nw  = self._nw.dropna(subset=["week"])
        self._rec = self._rec.dropna(subset=["week", "channel_node"])
        self._ev  = self._ev.dropna(subset=["week"])

        all_weeks = sorted(self._nw["week"].unique().tolist(), key=_week_to_order)
        self._all_weeks = all_weeks
        self._skus      = sorted(self._rec["product_id"].dropna().unique().tolist())
        self._channels  = sorted(self._rec["channel_node"].dropna().unique().tolist())

    # ── UI Construction ───────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # Left sidebar
        sidebar = tk.Frame(self, bg=C_SIDEBAR, width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="PPC Filters", font=("Helvetica", 12, "bold"),
                 bg=C_SIDEBAR, fg=C_HEADER).pack(pady=(8, 4))
        ttk.Separator(sidebar, orient="horizontal").pack(fill=tk.X, padx=4, pady=4)

        # SKU
        tk.Label(sidebar, text="SKU", font=("Helvetica", 9, "bold"),
                 bg=C_SIDEBAR, fg=C_HEADER).pack(anchor="w", padx=8)
        self._sku_var = tk.StringVar(value="All")
        ttk.Combobox(sidebar, textvariable=self._sku_var,
                     values=["All"] + self._skus,
                     state="readonly", width=18).pack(padx=8, pady=(0, 8))

        # Channel
        tk.Label(sidebar, text="Channel", font=("Helvetica", 9, "bold"),
                 bg=C_SIDEBAR, fg=C_HEADER).pack(anchor="w", padx=8)
        self._channel_var = tk.StringVar(value="All")
        ttk.Combobox(sidebar, textvariable=self._channel_var,
                     values=["All"] + self._channels,
                     state="readonly", width=18).pack(padx=8, pady=(0, 8))

        ttk.Separator(sidebar, orient="horizontal").pack(fill=tk.X, padx=4, pady=4)

        # Start / End week
        tk.Label(sidebar, text="Start Week", font=("Helvetica", 9, "bold"),
                 bg=C_SIDEBAR, fg=C_HEADER).pack(anchor="w", padx=8)
        self._start_var = tk.StringVar(value=self._all_weeks[0])
        ttk.Combobox(sidebar, textvariable=self._start_var,
                     values=self._all_weeks, state="readonly", width=18).pack(padx=8, pady=(0, 6))

        tk.Label(sidebar, text="End Week", font=("Helvetica", 9, "bold"),
                 bg=C_SIDEBAR, fg=C_HEADER).pack(anchor="w", padx=8)
        self._end_var = tk.StringVar(value=self._all_weeks[-1])
        ttk.Combobox(sidebar, textvariable=self._end_var,
                     values=self._all_weeks, state="readonly", width=18).pack(padx=8, pady=(0, 8))

        ttk.Separator(sidebar, orient="horizontal").pack(fill=tk.X, padx=4, pady=4)

        # Aggregation
        tk.Label(sidebar, text="Aggregation", font=("Helvetica", 9, "bold"),
                 bg=C_SIDEBAR, fg=C_HEADER).pack(anchor="w", padx=8)
        self._agg_var = tk.StringVar(value="Weekly")
        for val in ("Weekly", "Monthly", "Quarterly"):
            tk.Radiobutton(sidebar, text=val, variable=self._agg_var, value=val,
                           bg=C_SIDEBAR, fg=C_HEADER, selectcolor="#B0BEC5",
                           font=("Helvetica", 9)).pack(anchor="w", padx=16)

        ttk.Separator(sidebar, orient="horizontal").pack(fill=tk.X, padx=4, pady=8)

        # Buttons
        tk.Button(sidebar, text="Apply Filters",
                  font=("Helvetica", 10, "bold"),
                  bg="#1565C0", fg="white",
                  activebackground="#1976D2", activeforeground="white",
                  relief=tk.FLAT, padx=10, pady=6,
                  command=self._redraw).pack(fill=tk.X, padx=8, pady=4)

        tk.Button(sidebar, text="Save PNG",
                  font=("Helvetica", 9),
                  bg="#455A64", fg="white",
                  activebackground="#546E7A", activeforeground="white",
                  relief=tk.FLAT, padx=8, pady=4,
                  command=self._save_png).pack(fill=tk.X, padx=8, pady=2)

        self._status_var = tk.StringVar(value="")
        tk.Label(sidebar, textvariable=self._status_var, bg=C_SIDEBAR,
                 fg="#78909C", font=("Helvetica", 8), wraplength=180,
                 justify=tk.LEFT).pack(padx=8, pady=(8, 0))

        # Right chart area
        chart_frame = tk.Frame(self, bg="white")
        chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._fig = plt.Figure(figsize=(15, 12), facecolor="white")
        self._canvas = FigureCanvasTkAgg(self._fig, master=chart_frame)
        self._canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # Trust Event Type Breakdown drill-down: click handling is bound
        # once here; _on_canvas_click() hit-tests against self._trust_bar_info
        # (rebuilt on every _redraw()) to find which bar/event-type was clicked.
        self._canvas.mpl_connect("button_press_event", self._on_canvas_click)

        toolbar_frame = tk.Frame(chart_frame, bg="white")
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        NavigationToolbar2Tk(self._canvas, toolbar_frame)

    # ── Filter & Redraw ───────────────────────────────────────────────────
    def _get_filtered_weeks(self) -> list:
        start = self._start_var.get()
        end   = self._end_var.get()
        s_ord = _week_to_order(start)
        e_ord = _week_to_order(end)
        if s_ord > e_ord:
            s_ord, e_ord = e_ord, s_ord
        return [w for w in self._all_weeks if s_ord <= _week_to_order(w) <= e_ord]

    def _filter_data(self):
        sku     = self._sku_var.get()
        channel = self._channel_var.get()
        weeks   = self._get_filtered_weeks()

        nw  = self._nw[self._nw["week"].isin(weeks)].copy()
        rec = self._rec[self._rec["week"].isin(weeks)].copy()
        ev  = self._ev[self._ev["week"].isin(weeks)].copy()

        if sku != "All":
            nw  = nw[nw["product_id"] == sku]
            rec = rec[rec["product_id"] == sku]
            ev  = ev[ev["product_id"] == sku]

        if channel != "All":
            rec = rec[rec["channel_node"] == channel]
            ev  = ev[ev["lot_id"].isin(rec["lot_id"])]
            # Keep supply-chain nodes + selected channel for cost chart
            supply_nodes = nw[nw["revenue_base"] == 0]["node_id"].unique().tolist()
            nw = nw[nw["node_id"].isin(supply_nodes + [channel])]

        return nw, rec, ev, weeks

    def _redraw(self) -> None:
        nw_raw, rec_raw, ev_raw, weeks = self._filter_data()
        granularity = self._agg_var.get().lower()
        nw, rec, periods = _aggregate_weekly(nw_raw, rec_raw, granularity)

        selected_channels = (
            [self._channel_var.get()]
            if self._channel_var.get() != "All"
            else ["Both"]
        )

        n_lots = len(rec_raw.dropna(subset=["forward_cost_base"]))
        self._status_var.set(
            f"{len(weeks)} weeks | {n_lots} lots\n"
            f"SKU: {self._sku_var.get()}\n"
            f"Ch: {self._channel_var.get()}"
        )

        self._fig.clear()
        # 4th row added for the Trust Event Type Breakdown panel (full
        # width, spans gs[3, :]); existing 3 rows shrunk slightly to fit
        # within the same figure (figsize bumped 10→12in tall in _build_ui).
        gs = gridspec.GridSpec(
            4, 3, figure=self._fig,
            height_ratios=[0.30, 0.17, 0.33, 0.15],
            hspace=0.65, wspace=0.40,
        )
        ax1  = self._fig.add_subplot(gs[0, 0])
        ax2  = self._fig.add_subplot(gs[0, 1])
        ax3  = self._fig.add_subplot(gs[0, 2])
        ax_wf = self._fig.add_subplot(gs[1, :])   # waterfall — full width
        ax4  = self._fig.add_subplot(gs[2, 0])
        ax5  = self._fig.add_subplot(gs[2, 1])
        ax6  = self._fig.add_subplot(gs[2, 2])
        ax_trust = self._fig.add_subplot(gs[3, :])  # trust breakdown — full width

        cur = self._cur
        _draw_kpi_text(ax1, self._kpi, rec_raw, cur)
        _draw_profit_zone(ax2, ev_raw, cur)
        _draw_weekly_revenue(ax3, nw, periods, cur)
        _draw_waterfall(ax_wf, ev_raw, cur)          # ← Phase 2
        _draw_weekly_cost(ax4, nw, periods, cur)
        _draw_margin_dist(ax5, rec_raw, selected_channels)
        _draw_fwd_bwd(ax6, rec, periods, cur)

        # Trust Event Type Breakdown + drill-down: rec_raw is the
        # currently-filtered (SKU/Channel/period), un-aggregated
        # lot_reconciliation slice — same granularity as the badge/count
        # shown in the KPI panel above. self._ax_trust / _trust_bar_info /
        # _rec_raw_current are consumed by _on_canvas_click()/_show_drilldown().
        self._ax_trust = ax_trust
        self._trust_bar_info = _draw_trust_breakdown(ax_trust, rec_raw)
        self._rec_raw_current = rec_raw

        sku_tag = self._sku_var.get()
        ch_tag  = self._channel_var.get()
        w_tag   = (f"{weeks[0]}~{weeks[-1]}" if weeks else "—")
        self._fig.suptitle(
            f"WOM PPC Evaluation Cockpit  |  SKU: {sku_tag}  Channel: {ch_tag}  "
            f"Period: {w_tag}  [{granularity.capitalize()}]",
            fontsize=11, fontweight="bold", color=C_HEADER, y=0.99,
        )
        self._canvas.draw()

    # ── Trust Event drill-down ───────────────────────────────────────────
    def _on_canvas_click(self, event) -> None:
        """
        Click handler for the Trust Event Type Breakdown bar chart
        (bound once in _build_ui via canvas.mpl_connect). Ignores clicks
        outside that subplot; otherwise hit-tests against the bar patches
        stored by the most recent _redraw() and opens the drill-down
        window for the clicked type (no-op if that bar's count is 0).
        """
        ax_trust = getattr(self, "_ax_trust", None)
        if ax_trust is None or event.inaxes is not ax_trust:
            return
        for patch, event_type, count in getattr(self, "_trust_bar_info", []):
            contains, _ = patch.contains(event)
            if contains:
                if count > 0:
                    self._show_drilldown(event_type, count)
                return

    def _show_drilldown(self, event_type: str, count: int) -> None:
        """
        Opens a Toplevel window listing every Lot/Node/Week row (from the
        currently-filtered lot_reconciliation slice, self._rec_raw_current)
        whose trust_events_fired contains `event_type`.
        """
        rec = getattr(self, "_rec_raw_current", None)
        if rec is None or rec.empty or "trust_events_fired" not in rec.columns:
            return
        mask = rec["trust_events_fired"].fillna("").apply(
            lambda s: event_type in [t.strip() for t in str(s).split("|")]
        )
        sub = rec[mask].copy()
        if sub.empty:
            return
        sub = sub.sort_values(["week", "channel_node", "lot_id"])

        label = TRUST_EVENT_LABELS.get(event_type, event_type)
        win = tk.Toplevel(self)
        win.title(f"Trust Event Drill-down: {label} ({len(sub)} lots)")
        win.geometry("1000x480")
        win.configure(bg=C_SIDEBAR)

        tk.Label(
            win,
            text=f"{label}  —  {len(sub)} lot(s)   "
                 f"[SKU: {self._sku_var.get()}  Channel: {self._channel_var.get()}  "
                 f"Period: {self._start_var.get()}~{self._end_var.get()}]",
            font=("Helvetica", 10, "bold"), bg=C_SIDEBAR, fg=C_HEADER,
        ).pack(anchor="w", padx=10, pady=(10, 6))

        tree_frame = tk.Frame(win, bg=C_SIDEBAR)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ("lot_id", "week", "channel_node", "product_id",
                   "gross_profit_base", "gross_margin_pct",
                   "forward_cost_base", "market_revenue_base",
                   "trust_events_fired")
        headers = {
            "lot_id": "Lot ID", "week": "Week", "channel_node": "Node",
            "product_id": "Product", "gross_profit_base": f"Gross Profit/u ({self._cur})",
            "gross_margin_pct": "Margin %",
            "forward_cost_base": f"Fwd Cost/u ({self._cur})",
            "market_revenue_base": f"Mkt Rev/u ({self._cur})",
            "trust_events_fired": "Events Fired",
        }
        widths = {
            "lot_id": 110, "week": 90, "channel_node": 150, "product_id": 110,
            "gross_profit_base": 130, "gross_margin_pct": 90,
            "forward_cost_base": 120, "market_revenue_base": 120,
            "trust_events_fired": 220,
        }

        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=16)
        for col in columns:
            tree.heading(col, text=headers[col])
            tree.column(col, width=widths[col], anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        for _, row in sub.iterrows():
            margin = row.get("gross_margin_pct")
            margin_str = f"{margin:.1%}" if pd.notna(margin) else ""
            tree.insert("", tk.END, values=(
                row.get("lot_id", ""),
                row.get("week", ""),
                row.get("channel_node", ""),
                row.get("product_id", ""),
                f"{row.get('gross_profit_base', 0):,.2f}",
                margin_str,
                f"{row.get('forward_cost_base', 0):,.2f}",
                f"{row.get('market_revenue_base', 0):,.2f}",
                row.get("trust_events_fired", ""),
            ))

        tk.Button(win, text="Close", font=("Helvetica", 9),
                  bg="#455A64", fg="white", activebackground="#546E7A",
                  activeforeground="white", relief=tk.FLAT, padx=10, pady=4,
                  command=win.destroy).pack(pady=(0, 10))

    def _save_png(self) -> None:
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG image", "*.png"), ("PDF", "*.pdf")],
            initialfile="ppc_cockpit_filtered.png",
        )
        if path:
            self._fig.savefig(path, dpi=150, bbox_inches="tight")
            self._status_var.set(f"Saved:\n{os.path.basename(path)}")


# ── Standalone launcher ───────────────────────────────────────────────────────

def run_app(output_dir: str = "output/ppc") -> None:
    """Launch the PPC Cockpit as a standalone Tk window."""
    root = tk.Tk()
    root.title("WOM PPC Evaluation Cockpit")
    root.geometry("1280x760")
    root.configure(bg=C_SIDEBAR)
    app = PPCCockpitApp(root, output_dir=output_dir)
    app.pack(fill=tk.BOTH, expand=True)
    root.mainloop()
