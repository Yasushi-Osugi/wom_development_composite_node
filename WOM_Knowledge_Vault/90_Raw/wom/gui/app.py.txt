"""
WOM GUI – main application window.

Layout
------
┌────────────────────────────────────────────────────────────────┐
│  WOM – Weekly Operation Model                          v1r0m2  │
├──────────────┬─────────────────────────────────────────────────┤
│  Left panel  │  Right panel (notebook tabs)                    │
│  ─────────── │  ┌──────────────────────────────────────────┐  │
│  • Config    │  │ Charts  │ KPI Table │ At-Risk │ Scenario Δ│  │
│  • Files     │  └──────────────────────────────────────────┘  │
│  • [Run]     │                                                  │
│  • [Export]  │                                                  │
└──────────────┴─────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import pandas as pd

# Matplotlib embedded in Tkinter
import matplotlib
matplotlib.use("TkAgg")
matplotlib.rcParams["font.family"] = ["Yu Gothic", "DejaVu Sans"]
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from wom.config import WOMConfig, ScenarioSpec
from wom.data.loader import WOMInputs
from wom.data.schema import Cols
from wom.engine.simulator import WOMSimulator
from wom.engine.scenario import ScenarioManager
from wom.reports.output import write_csv, write_excel
from wom.engine.management import ManagementAnalysisResult

# NetworkX – optional (graceful fallback if not installed)
try:
    import networkx as nx
    HAS_NX = True
except ImportError:
    HAS_NX = False


# ──────────────────────────────────────────────────────────────────────
# Colour palette
# ──────────────────────────────────────────────────────────────────────
COLOURS = {
    "Base":      "#2196F3",
    "Upside":    "#4CAF50",
    "Downside":  "#F44336",
}
DEFAULT_COLOURS = ["#2196F3", "#4CAF50", "#F44336", "#FF9800", "#9C27B0"]

BG_DARK  = "#1E2A38"
BG_MID   = "#253347"
BG_LIGHT = "#2E3F55"
FG_WHITE = "#ECEFF1"
FG_ACC   = "#64B5F6"
BTN_RUN  = "#4CAF50"
BTN_EXP  = "#FF9800"


# ──────────────────────────────────────────────────────────────────────
# 4-4-5 Retail Calendar X-axis helper
# ──────────────────────────────────────────────────────────────────────
_445_MONTH_END_WEEKS = {4, 8, 13, 17, 21, 26, 30, 34, 39, 43, 47, 52}
_445_WEEK_TO_MONTH   = {
    4: 1, 8: 2, 13: 3, 17: 4, 21: 5, 26: 6,
    30: 7, 34: 8, 39: 9, 43: 10, 47: 11, 52: 12,
}
_445_MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _445_ticks(week_labels):
    """
    Return (tick_indices, tick_labels) for 4-4-5 quarterly X-axis display.

    Shows 4 ticks per year (~20 ticks for a 5-year model) to avoid overlap:
      Jan  → ''YY   (year label only, e.g. "'26")
      Mar  → "Mar"
      Jun  → "Jun"
      Sep  → "Sep"
      Other months → skipped entirely

    Returns ([], []) if week_labels are not in YYYY-Www format.
    """
    # Months to display and their labels
    _SHOW = {
        1:  lambda y: f"'{str(y)[2:]}",   # Jan  → year abbrev  e.g. '26
        3:  lambda y: "Mar",
        6:  lambda y: "Jun",
        9:  lambda y: "Sep",
    }
    indices = []
    labels  = []
    for i, lbl in enumerate(week_labels):
        try:
            year_str, wk_str = lbl.split("-W")
            wk = int(wk_str)
        except Exception:
            continue
        if wk in _445_MONTH_END_WEEKS:
            year  = int(year_str)
            month = _445_WEEK_TO_MONTH[wk]
            if month in _SHOW:
                indices.append(i)
                labels.append(_SHOW[month](year))
    return indices, labels


# ──────────────────────────────────────────────────────────────────────
# Helper widgets
# ──────────────────────────────────────────────────────────────────────

class LabeledEntry(tk.Frame):
    """A label + entry widget pair."""
    def __init__(self, parent, label: str, default: str = "", width: int = 18, **kw):
        super().__init__(parent, bg=BG_MID, **kw)
        tk.Label(self, text=label, bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9), width=22, anchor="w").pack(side="left")
        self.var = tk.StringVar(value=default)
        tk.Entry(self, textvariable=self.var, width=width,
                 bg=BG_LIGHT, fg=FG_WHITE, insertbackground=FG_WHITE,
                 relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=(4, 0))

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, v: str):
        self.var.set(v)


class FileEntry(tk.Frame):
    """Label + read-only entry + Browse button."""
    def __init__(self, parent, label: str, **kw):
        super().__init__(parent, bg=BG_MID, **kw)
        tk.Label(self, text=label, bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9), width=18, anchor="w").pack(side="left")
        self.var = tk.StringVar()
        # Pack button first (right-anchored) so it stays visible at any width
        tk.Button(self, text="…", command=self._browse,
                  bg="#37474F", fg=FG_WHITE, relief="flat",
                  font=("Segoe UI", 9, "bold"), width=3,
                  cursor="hand2").pack(side="right", padx=(2, 0))
        tk.Entry(self, textvariable=self.var,
                 bg=BG_LIGHT, fg=FG_ACC, state="readonly",
                 relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=(4, 0), fill="x", expand=True)

    def _browse(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV / Excel", "*.csv *.xlsx *.xls"), ("All files", "*.*")]
        )
        if path:
            self.var.set(path)

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, v: str):
        self.var.set(v)


# ──────────────────────────────────────────────────────────────────────
# Chart panel
# ──────────────────────────────────────────────────────────────────────

class ChartPanel(tk.Frame):
    """Holds a matplotlib Figure with a toolbar and SKU/chart-type selectors."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._mgr: Optional[ScenarioManager] = None
        self._sc_tree = None   # set via load_sc_tree() after Planning Engine run
        self._build()

    def _build(self):
        # Toolbar row
        bar = tk.Frame(self, bg=BG_MID, pady=4)
        bar.pack(fill="x", side="top")

        tk.Label(bar, text="Chart:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
        self.chart_var = tk.StringVar(value="Buffer Stock (DAD)")
        chart_cb = ttk.Combobox(bar, textvariable=self.chart_var, width=24,
                                values=["Buffer Stock (DAD)", "Harvest Input",
                                        "Fill Rate", "Weekly Demand vs Supply",
                                        "Capacity Utilisation",
                                        "Inventory Levels", "Stockout Qty",
                                        "Inv Cover (wks)"],
                                state="readonly", font=("Segoe UI", 9))
        chart_cb.pack(side="left", padx=2)

        tk.Label(bar, text="SKU:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 2))
        self.sku_var = tk.StringVar(value="ALL")
        self.sku_cb = ttk.Combobox(bar, textvariable=self.sku_var, width=14,
                                   values=["ALL"], state="readonly",
                                   font=("Segoe UI", 9))
        self.sku_cb.pack(side="left", padx=2)

        tk.Label(bar, text="Region:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
        self.reg_var = tk.StringVar(value="ALL")
        self.reg_cb = ttk.Combobox(bar, textvariable=self.reg_var, width=10,
                                   values=["ALL"], state="readonly",
                                   font=("Segoe UI", 9))
        self.reg_cb.pack(side="left", padx=2)

        tk.Button(bar, text="Refresh", command=self.refresh,
                  bg=FG_ACC, fg=BG_DARK, font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=8).pack(side="left", padx=(12, 0))

        # Figure
        self.fig = Figure(figsize=(9, 5), dpi=100, facecolor=BG_DARK)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        toolbar_frame = tk.Frame(self, bg=BG_MID)
        toolbar_frame.pack(fill="x")
        NavigationToolbar2Tk(self.canvas, toolbar_frame)

    def load(self, mgr: ScenarioManager) -> None:
        self._mgr = mgr
        df = mgr.combined()
        skus    = ["ALL"] + sorted(df[Cols.SKU_ID].unique().tolist())
        regions = ["ALL"] + sorted(df[Cols.REGION].unique().tolist())
        self.sku_cb["values"]  = skus
        self.reg_cb["values"]  = regions
        self.sku_var.set("ALL")
        self.reg_var.set("ALL")
        self.refresh()

    def refresh(self) -> None:
        if self._mgr is None:
            return
        chart = self.chart_var.get()
        sku    = self.sku_var.get()
        region = self.reg_var.get()
        self.fig.clf()
        try:
            if chart == "Buffer Stock (DAD)":
                self._plot_buffer_stock(sku)
            elif chart == "Harvest Input":
                self._plot_harvest_input(sku)
            elif chart == "Inventory Levels":
                self._plot_inventory(sku, region)
            elif chart == "Fill Rate":
                self._plot_fill_rate(sku, region)
            elif chart == "Stockout Qty":
                self._plot_stockout(sku, region)
            elif chart == "Weekly Demand vs Supply":
                self._plot_demand_supply(sku, region)
            elif chart == "Capacity Utilisation":
                self._plot_capacity(sku, region)
            elif chart == "Inv Cover (wks)":
                self._plot_cover(sku, region)
        except Exception as e:
            ax = self.fig.add_subplot(111)
            ax.set_facecolor(BG_DARK)
            ax.text(0.5, 0.5, str(e), ha="center", va="center",
                    color="red", transform=ax.transAxes)
        self.canvas.draw()

    def _filtered(self, sku: str, region: str) -> pd.DataFrame:
        df = self._mgr.combined()
        if sku    != "ALL": df = df[df[Cols.SKU_ID] == sku]
        if region != "ALL": df = df[df[Cols.REGION]  == region]
        return df

    def _ax_style(self, ax, title: str, ylabel: str):
        ax.set_facecolor(BG_MID)
        ax.set_title(title, color=FG_WHITE, fontsize=11, pad=8)
        ax.set_xlabel("Week", color=FG_ACC, fontsize=9)
        ax.set_ylabel(ylabel, color=FG_ACC, fontsize=9)
        ax.tick_params(colors=FG_WHITE, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(BG_LIGHT)
        ax.legend(facecolor=BG_LIGHT, labelcolor=FG_WHITE, fontsize=8)
        self.fig.patch.set_facecolor(BG_DARK)
        # Rotate x-tick labels
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=7)

    def _plot_inventory(self, sku, region):
        df = self._filtered(sku, region)
        ax = self.fig.add_subplot(111)
        for i, s in enumerate(self._mgr.scenarios()):
            sub = df[df[Cols.SCENARIO] == s].groupby(Cols.WEEK)[Cols.CLOSING_INV].sum()
            c = COLOURS.get(s, DEFAULT_COLOURS[i % len(DEFAULT_COLOURS)])
            ax.plot(sub.index, sub.values, label=s, color=c, linewidth=2, marker="o", markersize=3)
        # Safety stock line (Base scenario average)
        base_ss = df[df[Cols.SCENARIO] == self._mgr.scenarios()[0]].groupby(Cols.WEEK)[Cols.SAFETY_STOCK_QTY].sum()
        ax.fill_between(base_ss.index, base_ss.values, alpha=0.15, color="#FF9800", label="Safety Stock")
        self._ax_style(ax, "Closing Inventory by Week", "Units")

    def _plot_fill_rate(self, sku, region):
        ax = self.fig.add_subplot(111)
        df = self._filtered(sku, region)
        for i, s in enumerate(self._mgr.scenarios()):
            sub = df[df[Cols.SCENARIO] == s].groupby(Cols.WEEK)[Cols.FILL_RATE].mean()
            c = COLOURS.get(s, DEFAULT_COLOURS[i % len(DEFAULT_COLOURS)])
            ax.plot(sub.index, sub.values * 100, label=s, color=c, linewidth=2)
        ax.axhline(95, color="#FF9800", linestyle="--", linewidth=1, label="95% target")
        self._ax_style(ax, "Average Fill Rate by Week (%)", "Fill Rate (%)")
        ax.set_ylim(0, 105)

    def _plot_stockout(self, sku, region):
        ax = self.fig.add_subplot(111)
        df = self._filtered(sku, region)
        weeks = sorted(df[Cols.WEEK].unique())
        n_scenarios = len(self._mgr.scenarios())
        width = 0.8 / n_scenarios
        x = range(len(weeks))
        for i, s in enumerate(self._mgr.scenarios()):
            sub = df[df[Cols.SCENARIO] == s].groupby(Cols.WEEK)[Cols.STOCKOUT_QTY].sum().reindex(weeks, fill_value=0)
            offset = (i - n_scenarios / 2 + 0.5) * width
            c = COLOURS.get(s, DEFAULT_COLOURS[i % len(DEFAULT_COLOURS)])
            ax.bar([xi + offset for xi in x], sub.values, width=width, label=s, color=c, alpha=0.85)
        ax.set_xticks(list(x))
        ax.set_xticklabels(weeks, rotation=45, ha="right", fontsize=7)
        self._ax_style(ax, "Stockout Quantity by Week", "Units")

    def _plot_demand_supply(self, sku, region):
        ax = self.fig.add_subplot(111)
        df = self._filtered(sku, region)
        for i, s in enumerate(self._mgr.scenarios()):
            sub = df[df[Cols.SCENARIO] == s]
            demand  = sub.groupby(Cols.WEEK)[Cols.DEMAND_FCST].sum()
            receipt = sub.groupby(Cols.WEEK)[Cols.SUPPLY_RECEIPT].sum()
            c = COLOURS.get(s, DEFAULT_COLOURS[i % len(DEFAULT_COLOURS)])
            ax.plot(demand.index,  demand.values,  label=f"{s} Demand",  color=c, linewidth=2)
            ax.plot(receipt.index, receipt.values, label=f"{s} Receipt", color=c, linewidth=1.5, linestyle="--")
        self._ax_style(ax, "Weekly Demand vs Supply Receipts", "Units")

    def _plot_capacity(self, sku, region):
        ax = self.fig.add_subplot(111)
        df = self._filtered(sku, region)
        for i, s in enumerate(self._mgr.scenarios()):
            sub = df[df[Cols.SCENARIO] == s].groupby(Cols.WEEK)[Cols.REORDER_QTY].sum()
            c = COLOURS.get(s, DEFAULT_COLOURS[i % len(DEFAULT_COLOURS)])
            ax.bar(range(len(sub)), sub.values, label=f"{s} Orders", color=c, alpha=0.7)
            ax.set_xticks(range(len(sub)))
            ax.set_xticklabels(sub.index, rotation=45, ha="right", fontsize=7)
        self._ax_style(ax, "Replenishment Orders Placed by Week", "Units Ordered")

    def _plot_cover(self, sku, region):
        ax = self.fig.add_subplot(111)
        df = self._filtered(sku, region)
        for i, s in enumerate(self._mgr.scenarios()):
            sub = df[df[Cols.SCENARIO] == s].groupby(Cols.WEEK)[Cols.INV_COVER_WKS].mean()
            c = COLOURS.get(s, DEFAULT_COLOURS[i % len(DEFAULT_COLOURS)])
            ax.plot(sub.index, sub.values, label=s, color=c, linewidth=2)
        ax.axhline(2, color="#FF9800", linestyle="--", linewidth=1, label="2-wk SS floor")
        self._ax_style(ax, "Average Inventory Cover (weeks)", "Weeks of Cover")

    # ── Planning Engine sc_tree charts ──────────────────────────────────

    def load_sc_tree(self, sc_tree) -> None:
        """Store the post-planning SCTree for sc_tree-based charts."""
        self._sc_tree = sc_tree

    def _plot_buffer_stock(self, sku_filter: str) -> None:
        """
        Buffer Stock (MOM / Decoupling Point) — 産地集荷センター在庫推移

        Shows closing inventory lots at InBound MOM nodes per week.
        In demand-anchored lot-based planning, real buffer accumulates at
        MOM (push-mode decoupling nodes: Sanchiku_Niigata, Sanchiku_Hokkaido).
        OutBound DAD nodes are pass-through (I=0 by design).
        """
        if self._sc_tree is None:
            ax = self.fig.add_subplot(111)
            ax.set_facecolor(BG_MID)
            ax.text(0.5, 0.5, "Planning Engine を実行してください",
                    ha="center", va="center", color=FG_ACC,
                    transform=ax.transAxes, fontsize=11)
            self.fig.patch.set_facecolor(BG_DARK)
            return

        from wom.model.plan_node import NODE_TYPE_MOM, I as I_IDX
        sc = self._sc_tree
        weeks = sc.week_labels
        n = len(weeks)
        x = list(range(n))

        ax = self.fig.add_subplot(111)
        ax.set_facecolor(BG_MID)
        self.fig.patch.set_facecolor(BG_DARK)

        node_palette = [
            "#42A5F5", "#66BB6A", "#FFA726", "#AB47BC",
            "#26C6DA", "#EF5350", "#8D6E63", "#EC407A",
        ]
        colour_idx = 0
        plotted_any = False

        for prod_nm in sc.products:
            if sku_filter != "ALL" and prod_nm != sku_filter:
                continue
            try:
                in_root = sc.get_in_root(prod_nm)
            except Exception:
                continue
            for node in in_root.walk_preorder():
                if node.node_type != NODE_TYPE_MOM:
                    continue
                cpu = sc.cpu_size * node.bom_qty
                inv_vals = [len(node.psi4supply[w][I_IDX]) * cpu for w in range(n)]
                if all(v == 0 for v in inv_vals):
                    continue
                lbl = f"{node.node_name} ({prod_nm})"
                c = node_palette[colour_idx % len(node_palette)]
                colour_idx += 1
                ax.plot(x, inv_vals, label=lbl, color=c, linewidth=1.8)
                plotted_any = True

        if not plotted_any:
            ax.text(0.5, 0.5, "MOMノードのバッファ在庫データがありません\n(Planning Engine を実行後、Refreshしてください)",
                    ha="center", va="center", color=FG_ACC,
                    transform=ax.transAxes, fontsize=10)

        # x-axis tick labels — 4-4-5 retail calendar monthly ticks
        _t_idx, _t_lbl = _445_ticks(weeks)
        if _t_idx:
            ax.set_xticks(_t_idx)
            ax.set_xticklabels(_t_lbl, rotation=0, ha="center", fontsize=7)
        else:
            tick_step = max(1, n // 12)
            ax.set_xticks(x[::tick_step])
            ax.set_xticklabels(weeks[::tick_step], rotation=45, ha="right", fontsize=7)
        self._ax_style(ax, "Buffer Stock by Week — MOM Nodes (産地集荷センター玄米バッファ在庫)", "Lots (closing inventory)")

    def _plot_harvest_input(self, sku_filter: str) -> None:
        """
        Harvest Input — 稲作田→産地集荷センター 週次収穫・出荷量

        Shows lots dispatched from InBound leaf_in nodes (Tanbo) per week.
        Highlights harvest season peaks.
        """
        if self._sc_tree is None:
            ax = self.fig.add_subplot(111)
            ax.set_facecolor(BG_MID)
            ax.text(0.5, 0.5, "Planning Engine を実行してください",
                    ha="center", va="center", color=FG_ACC,
                    transform=ax.transAxes, fontsize=11)
            self.fig.patch.set_facecolor(BG_DARK)
            return

        from wom.model.plan_node import NODE_TYPE_LEAF_IN, S as S_IDX
        sc = self._sc_tree
        weeks = sc.week_labels
        n = len(weeks)
        x = list(range(n))

        ax = self.fig.add_subplot(111)
        ax.set_facecolor(BG_MID)
        self.fig.patch.set_facecolor(BG_DARK)

        harvest_colours = {0: "#66BB6A", 1: "#42A5F5"}
        prod_idx = 0
        plotted_any = False

        for prod_nm in sc.products:
            if sku_filter != "ALL" and prod_nm != sku_filter:
                prod_idx += 1
                continue
            try:
                in_root = sc.get_in_root(prod_nm)
            except Exception:
                prod_idx += 1
                continue
            for node in in_root.walk_preorder():
                if node.node_type != NODE_TYPE_LEAF_IN:
                    continue
                cpu = sc.cpu_size * node.bom_qty
                # S = sales/dispatched from farm = harvest output
                supply_vals = [len(node.psi4demand[w][S_IDX]) * cpu for w in range(n)]
                if all(v == 0 for v in supply_vals):
                    continue
                lbl = f"{node.node_name} ({prod_nm})"
                c = harvest_colours.get(prod_idx % 2, "#FFA726")
                ax.bar(x, supply_vals, label=lbl, color=c, alpha=0.75)
                plotted_any = True
                prod_idx += 1

        if not plotted_any:
            ax.text(0.5, 0.5, "収穫入荷データがありません\n(Planning Engine を実行してください)",
                    ha="center", va="center", color=FG_ACC,
                    transform=ax.transAxes, fontsize=10)

        # x-axis tick labels — 4-4-5 retail calendar monthly ticks
        _t_idx, _t_lbl = _445_ticks(weeks)
        if _t_idx:
            ax.set_xticks(_t_idx)
            ax.set_xticklabels(_t_lbl, rotation=0, ha="center", fontsize=7)
        else:
            tick_step = max(1, n // 12)
            ax.set_xticks(x[::tick_step])
            ax.set_xticklabels(weeks[::tick_step], rotation=45, ha="right", fontsize=7)
        self._ax_style(ax,
                       "Harvest Input by Week — 稲作田 週次収穫・出荷量 (leaf_in → 産地集荷センター)",
                       "Lots dispatched")


# ──────────────────────────────────────────────────────────────────────
# KPI Table panel
# ──────────────────────────────────────────────────────────────────────

class KPITablePanel(tk.Frame):
    """Treeview-based KPI summary table."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._build()

    def _build(self):
        # Filter bar
        bar = tk.Frame(self, bg=BG_MID, pady=4)
        bar.pack(fill="x")
        tk.Label(bar, text="Filter scenario:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9)).pack(side="left", padx=8)
        self.filter_var = tk.StringVar(value="ALL")
        self.filter_cb = ttk.Combobox(bar, textvariable=self.filter_var, width=14,
                                      values=["ALL"], state="readonly",
                                      font=("Segoe UI", 9))
        self.filter_cb.pack(side="left")
        self.filter_cb.bind("<<ComboboxSelected>>", lambda _: self._apply_filter())

        # Treeview
        cols = ["scenario", "sku_id", "region",
                "total_demand", "total_fulfilled", "total_stockout",
                "avg_fill_rate", "avg_closing_inv", "avg_inv_cover_wks",
                "total_reorder_qty"]
        self.tree = ttk.Treeview(self, columns=cols, show="headings")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=BG_LIGHT, foreground=FG_WHITE,
                        rowheight=22, fieldbackground=BG_LIGHT,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                        background=BG_MID, foreground=FG_ACC,
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#37474F")])

        col_widths = {"scenario": 80, "sku_id": 90, "region": 70,
                      "total_demand": 90, "total_fulfilled": 90,
                      "total_stockout": 90, "avg_fill_rate": 90,
                      "avg_closing_inv": 100, "avg_inv_cover_wks": 110,
                      "total_reorder_qty": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=col_widths.get(c, 90), anchor="center")

        vsb = ttk.Scrollbar(self, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.pack(fill="both", expand=True, side="left")
        vsb.pack(fill="y",  side="right")
        hsb.pack(fill="x",  side="bottom")

        self._df: Optional[pd.DataFrame] = None

    def load(self, mgr: ScenarioManager) -> None:
        self._df = mgr.kpi_summary()
        scenarios = ["ALL"] + sorted(self._df[Cols.SCENARIO].unique().tolist())
        self.filter_cb["values"] = scenarios
        self.filter_var.set("ALL")
        self._apply_filter()

    def _apply_filter(self):
        if self._df is None:
            return
        df = self._df
        sel = self.filter_var.get()
        if sel != "ALL":
            df = df[df[Cols.SCENARIO] == sel]
        self.tree.delete(*self.tree.get_children())
        for _, row in df.iterrows():
            vals = [
                row.get("scenario", ""),
                row.get("sku_id", ""),
                row.get("region", ""),
                f"{row.get('total_demand', 0):,.0f}",
                f"{row.get('total_fulfilled', 0):,.0f}",
                f"{row.get('total_stockout', 0):,.0f}",
                f"{row.get('avg_fill_rate', 0):.1%}",
                f"{row.get('avg_closing_inv', 0):,.1f}",
                f"{row.get('avg_inv_cover_wks', 0):.1f}",
                f"{row.get('total_reorder_qty', 0):,.0f}",
            ]
            self.tree.insert("", "end", values=vals)


# ──────────────────────────────────────────────────────────────────────
# Management Cockpit Panel
# ──────────────────────────────────────────────────────────────────────

class ManagementCockpitPanel(tk.Frame):
    """
    Management Layer cockpit tab.

    Layout (top to bottom):
      ┌─────────────────────────────────────────┐
      │  P&L Summary Table (scenario comparison) │
      ├─────────────────────────────────────────┤
      │  Strategic KPI Cards                     │
      ├─────────────────────────────────────────┤
      │  Tariff & FX (Landed Cost) comparison    │
      ├───────────────────────┬─────────────────┤
      │  CCC Chart            │  GP chart        │
      ├───────────────────────┴─────────────────┤
      │  Issues & Risks list  (Japanese text)    │
      └─────────────────────────────────────────┘
    """

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._mgr: Optional[ScenarioManager] = None
        self._lc_comparison_df = None
        self._build()

    def _build(self):
        # ── SKU filter (applies to P&L / Strategic KPI / Landed Cost) ──
        filt = tk.Frame(self, bg=BG_DARK)
        filt.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(filt, text="SKU:", bg=BG_DARK, fg=FG_WHITE,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        self._sku_var = tk.StringVar(value="All")
        self._sku_cb = ttk.Combobox(filt, textvariable=self._sku_var,
                                    values=["All"], width=18, state="readonly",
                                    font=("Segoe UI", 9))
        self._sku_cb.pack(side="left")
        self._sku_cb.bind("<<ComboboxSelected>>", lambda _: self._on_sku_filter_change())
        tk.Label(filt, text="  （P&L Summary / Strategic KPI / Landed Cost に適用）",
                 bg=BG_DARK, fg="#546E7A", font=("Segoe UI", 8)).pack(side="left")

        # ── P&L table ────────────────────────────────────────────────
        pl_frame = tk.LabelFrame(self, text="  P&L Summary (Scenario Comparison)  ",
                                 bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 9, "bold"),
                                 relief="groove", bd=1)
        pl_frame.pack(fill="x", padx=8, pady=(8, 4))

        pl_cols = ["scenario", "revenue", "cogs", "gross_profit",
                   "gross_margin%", "inv_value", "ccc_wks", "ar_value", "ap_value"]
        self._pl_tree = ttk.Treeview(pl_frame, columns=pl_cols,
                                     show="headings", height=5)
        pl_widths = {"scenario": 90, "revenue": 110, "cogs": 100,
                     "gross_profit": 110, "gross_margin%": 95,
                     "inv_value": 110, "ccc_wks": 80,
                     "ar_value": 110, "ap_value": 110}
        for c in pl_cols:
            self._pl_tree.heading(c, text=c.replace("_", " ").title())
            self._pl_tree.column(c, width=pl_widths.get(c, 100), anchor="center")

        pl_vsb = ttk.Scrollbar(pl_frame, orient="vertical", command=self._pl_tree.yview)
        self._pl_tree.configure(yscrollcommand=pl_vsb.set)
        self._pl_tree.pack(side="left", fill="x", expand=True)
        pl_vsb.pack(side="right", fill="y")

        # ── Node P&L table (拠点別P/L評価, v1r0m5) ────────────────────
        # Full-horizon Revenue/Cost/Gross Profit per SC Node (leaf_in supplier /
        # MOM / DAD / leaf_out channel), sourced from the PPC engine's
        # ppc_node_pl_summary.csv (see wom/ppc/ppc_kpi.py build_node_pl_summary).
        # Respects the same SKU filter as the P&L Summary table above.
        node_pl_frame = tk.LabelFrame(self, text="  \U0001f4cd Node P&L (拠点別損益)  ",
                                      bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 9, "bold"),
                                      relief="groove", bd=1)
        node_pl_frame.pack(fill="x", padx=8, pady=(0, 4))

        node_pl_cols = ["node_id", "product_id", "revenue", "cost",
                        "gross_profit", "gross_margin%", "tariff"]
        self._node_pl_tree = ttk.Treeview(node_pl_frame, columns=node_pl_cols,
                                          show="headings", height=6)
        node_pl_widths = {"node_id": 150, "product_id": 110, "revenue": 100,
                          "cost": 100, "gross_profit": 100,
                          "gross_margin%": 95, "tariff": 90}
        node_pl_heads = {"node_id": "Node", "product_id": "Product",
                         "gross_margin%": "GM%"}
        for c in node_pl_cols:
            self._node_pl_tree.heading(c, text=node_pl_heads.get(c, c.replace("_", " ").title()))
            self._node_pl_tree.column(c, width=node_pl_widths.get(c, 100), anchor="center")
        self._node_pl_tree.tag_configure("NEG", background="#4A1A1A", foreground="#FF6B6B")

        node_pl_vsb = ttk.Scrollbar(node_pl_frame, orient="vertical",
                                    command=self._node_pl_tree.yview)
        self._node_pl_tree.configure(yscrollcommand=node_pl_vsb.set)
        self._node_pl_tree.pack(side="left", fill="x", expand=True)
        node_pl_vsb.pack(side="right", fill="y")

        self._node_pl_output_dir = "output/ppc"

        # ── Strategic KPI Cards ──────────────────────────────────────
        skpi_frame = tk.LabelFrame(self,
                                   text="  \U0001f3ed Strategic KPI  (Planning Engine)",
                                   bg=BG_MID, fg=FG_ACC,
                                   font=("Segoe UI", 9, "bold"),
                                   relief="groove", bd=1)
        skpi_frame.pack(fill="x", padx=8, pady=(0, 4))

        # 5 KPI cards in a row
        self._skpi_cards: dict[str, dict] = {}
        card_defs = [
            ("fixed_cost_coverage", "固定費吸収率",    "≥ 75%",    "生産量 / CapHard"),
            ("production_leveling", "生産平準化指数",  "≥ 80%",    "1 - 変動係数"),
            ("buffer_retention",    "在庫滞留率",      "20–50%",   "バッファ保有率"),
            ("fill_rate",           "需要充足率",      "≥ 95%",    "出荷 / 需要"),
            ("avg_cap_utilization", "設備稼働率",      "70–90%",   "P / CapHard"),
        ]
        for key, label_ja, target, formula in card_defs:
            card = tk.Frame(skpi_frame, bg=BG_DARK, bd=1, relief="solid",
                            padx=10, pady=6)
            card.pack(side="left", fill="both", expand=True, padx=3, pady=4)

            tk.Label(card, text=label_ja,
                     bg=BG_DARK, fg="#90A4AE",
                     font=("Segoe UI", 8)).pack(anchor="w")

            val_var = tk.StringVar(value="--")
            val_lbl = tk.Label(card, textvariable=val_var,
                               bg=BG_DARK, fg=FG_WHITE,
                               font=("Segoe UI", 14, "bold"))
            val_lbl.pack(anchor="w")

            status_var = tk.StringVar(value="")
            status_lbl = tk.Label(card, textvariable=status_var,
                                  bg=BG_DARK, fg="#90A4AE",
                                  font=("Segoe UI", 8))
            status_lbl.pack(anchor="w")

            tk.Label(card, text=f"目標: {target}  ({formula})",
                     bg=BG_DARK, fg="#546E7A",
                     font=("Segoe UI", 7)).pack(anchor="w")

            self._skpi_cards[key] = {
                "val_var": val_var,
                "val_lbl": val_lbl,
                "status_var": status_var,
                "status_lbl": status_lbl,
            }

        # ── Tariff & FX (Landed Cost) ────────────────────────────────
        lc_frame = tk.LabelFrame(self, text="  🌐 Tariff & FX — Landed Cost Impact  ",
                                 bg=BG_MID, fg="#FFD54F",
                                 font=("Segoe UI", 9, "bold"),
                                 relief="groove", bd=1)
        lc_frame.pack(fill="x", padx=8, pady=(0, 4))

        lc_cols = ["wom_scenario", "lc_scenario", "revenue",
                   "customs_duty", "freight", "landed_gm%",
                   "margin_impact", "tariff_burden%"]
        self._lc_tree = ttk.Treeview(lc_frame, columns=lc_cols,
                                     show="headings", height=4)
        _lc_widths = {"wom_scenario": 80, "lc_scenario": 100, "revenue": 100,
                      "customs_duty": 100, "freight": 80,
                      "landed_gm%": 85, "margin_impact": 95, "tariff_burden%": 95}
        _lc_heads  = {"wom_scenario": "WOM Scen", "lc_scenario": "LC Scenario",
                      "revenue": "Revenue", "customs_duty": "Customs Duty",
                      "freight": "Freight", "landed_gm%": "Landed GM%",
                      "margin_impact": "ΔMargin pp", "tariff_burden%": "Tariff %"}
        for c in lc_cols:
            self._lc_tree.heading(c, text=_lc_heads.get(c, c))
            self._lc_tree.column(c, width=_lc_widths.get(c, 90), anchor="center")
        self._lc_tree.tag_configure("HIGH",   background="#4A1A1A", foreground="#FF6B6B")
        self._lc_tree.tag_configure("MEDIUM", background="#3A2A10", foreground="#FFD740")
        self._lc_tree.tag_configure("OK",     background=BG_LIGHT,  foreground="#69F0AE")

        lc_vsb = ttk.Scrollbar(lc_frame, orient="vertical", command=self._lc_tree.yview)
        self._lc_tree.configure(yscrollcommand=lc_vsb.set)
        self._lc_tree.pack(side="left", fill="x", expand=True)
        lc_vsb.pack(side="right", fill="y")

        # LC narrative text
        self._lc_narrative = tk.Text(
            lc_frame, height=4, width=45,
            bg="#0D1B2A", fg="#FFD54F",
            font=("Segoe UI", 8), relief="flat",
            wrap="word", state="disabled",
        )
        self._lc_narrative.pack(side="left", fill="both", expand=True,
                                padx=(8, 4), pady=2)

        # Charts row ──────────────────────────────────────────────────
        chart_row = tk.Frame(self, bg=BG_DARK)
        chart_row.pack(fill="both", expand=True, padx=8, pady=4)

        # CCC chart (left)
        ccc_frame = tk.LabelFrame(chart_row, text="  CCC (Cash to Cash Cycle, weeks)  ",
                                  bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 9, "bold"),
                                  relief="groove", bd=1)
        ccc_frame.pack(side="left", fill="both", expand=True, padx=(0, 4))

        self._ccc_fig = Figure(figsize=(5, 3), dpi=90, facecolor=BG_DARK)
        self._ccc_canvas = FigureCanvasTkAgg(self._ccc_fig, master=ccc_frame)
        self._ccc_canvas.get_tk_widget().pack(fill="both", expand=True)

        # Gross Profit by scenario chart (right)
        gp_frame = tk.LabelFrame(chart_row, text="  Gross Profit by Scenario  ",
                                 bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 9, "bold"),
                                 relief="groove", bd=1)
        gp_frame.pack(side="left", fill="both", expand=True, padx=(4, 0))

        self._gp_fig = Figure(figsize=(5, 3), dpi=90, facecolor=BG_DARK)
        self._gp_canvas = FigureCanvasTkAgg(self._gp_fig, master=gp_frame)
        self._gp_canvas.get_tk_widget().pack(fill="both", expand=True)

        # ── Issues & Risks ───────────────────────────────────────────
        issue_frame = tk.LabelFrame(self, text="  Management Issues & Risks  ",
                                    bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 9, "bold"),
                                    relief="groove", bd=1)
        issue_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # Scenario selector
        ctrl = tk.Frame(issue_frame, bg=BG_MID)
        ctrl.pack(fill="x", padx=4, pady=2)
        tk.Label(ctrl, text="Scenario:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9)).pack(side="left", padx=4)
        self._issue_scen_var = tk.StringVar(value="")
        self._issue_scen_cb = ttk.Combobox(ctrl, textvariable=self._issue_scen_var,
                                           width=14, state="readonly",
                                           font=("Segoe UI", 9))
        self._issue_scen_cb.pack(side="left")
        self._issue_scen_cb.bind("<<ComboboxSelected>>", lambda _: self._refresh_issues())

        # Issues treeview
        iss_cols = ["type", "severity", "scenario", "code", "title_ja"]
        self._issue_tree = ttk.Treeview(issue_frame, columns=iss_cols,
                                        show="headings", height=6)
        iss_widths = {"type": 60, "severity": 70, "scenario": 90,
                      "code": 160, "title_ja": 300}
        for c in iss_cols:
            self._issue_tree.heading(c, text=c.replace("_", " ").title())
            self._issue_tree.column(c, width=iss_widths.get(c, 100), anchor="w")
        self._issue_tree.tag_configure("HIGH",   background="#4A1A1A", foreground="#FF6B6B")
        self._issue_tree.tag_configure("MEDIUM", background="#3A2A10", foreground="#FFB74D")
        self._issue_tree.tag_configure("LOW",    background=BG_LIGHT,  foreground=FG_WHITE)
        self._issue_tree.tag_configure("RISK",   background="#1A2A3A",  foreground="#81D4FA")

        iss_vsb = ttk.Scrollbar(issue_frame, orient="vertical",
                                command=self._issue_tree.yview)
        self._issue_tree.configure(yscrollcommand=iss_vsb.set)
        self._issue_tree.pack(side="left", fill="both", expand=True, pady=(2, 0))
        iss_vsb.pack(side="right", fill="y")

        # Narrative text box
        self._narrative_text = tk.Text(
            issue_frame, height=7, width=60,
            bg="#0D1B2A", fg="#B0BEC5",
            font=("Segoe UI", 9), relief="flat",
            wrap="word", state="disabled",
        )
        self._narrative_text.pack(side="left", fill="both", expand=True,
                                  padx=(8, 0), pady=(2, 0))

        self._mgmt_data: dict = {}

    def load(self, mgr: ScenarioManager) -> None:
        self._mgr = mgr
        self._refresh_sku_filter()
        self._refresh_pl_table()
        self._refresh_node_pl_table()
        self._refresh_strategic_kpis()
        self._refresh_lc_table()
        self._refresh_charts()
        self._refresh_issue_selector()

    def refresh_node_pl(self, output_dir: Optional[str] = None) -> None:
        """Public API — call after the PPC engine finishes a run (B2 thread),
        so the Node P&L table picks up the freshly written
        output/ppc/ppc_node_pl_summary.csv without needing a full re-load."""
        if output_dir:
            self._node_pl_output_dir = output_dir
        self._refresh_node_pl_table()

    def _refresh_node_pl_table(self):
        """
        拠点別P/L評価 — populate the Node P&L table from
        <output_dir>/ppc_node_pl_summary.csv (written by
        wom/ppc/ppc_export.py, built by wom/ppc/ppc_kpi.py
        build_node_pl_summary()). Filtered by the SKU dropdown above.
        """
        self._node_pl_tree.delete(*self._node_pl_tree.get_children())
        path = os.path.join(getattr(self, "_node_pl_output_dir", "output/ppc"),
                             "ppc_node_pl_summary.csv")
        if not os.path.exists(path):
            return
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            print(f"[Management] Node P&L load error: {exc}")
            return
        if df.empty:
            return
        sku = self._current_sku()
        if sku and "product_id" in df.columns:
            df = df[df["product_id"] == sku]
        for _, row in df.iterrows():
            rev  = float(row.get("revenue_base", 0) or 0)
            cost = float(row.get("cost_base", 0) or 0)
            gp   = float(row.get("gross_profit_base", 0) or 0)
            gm   = float(row.get("gross_margin_pct", 0) or 0)
            tar  = float(row.get("tariff_base", 0) or 0)
            # rev == 0 means this node never recognizes market_revenue --
            # only the terminal channel/leaf_out node does (see
            # ppc_profit_zone.py, market_revenue is always emitted at
            # acc.channel_node). For upstream/pass-through nodes,
            # gross_margin_pct is a "0.0 / 0 -> 0.0" guard placeholder,
            # not a real zero margin, so show "--" (N/A) instead of a
            # misleading "0.0%" (2026-07-14 GUI review finding).
            gm_display = "--" if rev == 0 else f"{gm*100:.1f}%"
            tags = ("NEG",) if gp < 0 else ()
            self._node_pl_tree.insert("", "end", tags=tags, values=[
                row.get("node_id", ""),
                row.get("product_id", ""),
                f"{rev:,.0f}",
                f"{cost:,.0f}",
                f"{gp:,.0f}",
                gm_display,
                f"{tar:,.0f}",
            ])

    def _refresh_sku_filter(self):
        """(Re)populate the SKU dropdown from the latest summary_money."""
        skus = []
        sm = getattr(self._mgr, "summary_money", None) if self._mgr else None
        if sm is not None and Cols.SKU_ID in sm.columns:
            skus = sorted(sm[Cols.SKU_ID].dropna().unique().tolist())
        values = ["All"] + skus
        self._sku_cb["values"] = values
        if self._sku_var.get() not in values:
            self._sku_var.set("All")

    def _on_sku_filter_change(self):
        self._refresh_pl_table()
        self._refresh_node_pl_table()
        self._refresh_strategic_kpis()
        self._refresh_lc_table()
        self._refresh_charts()

    def _current_sku(self) -> Optional[str]:
        v = self._sku_var.get() if hasattr(self, "_sku_var") else "All"
        return None if (not v or v == "All") else v

    def _get_filtered_kpi(self):
        """
        scenario_money_kpi for the current SKU filter.

        "All" (or missing summary_money) returns the precomputed
        mgr.scenario_money_kpi as-is. A specific SKU filters
        mgr.summary_money to that sku_id and re-aggregates to scenario
        level with the same build_scenario_money_kpi() used for "All",
        so P&L / Landed Cost stay on one consistent code path.
        """
        sku = self._current_sku()
        if sku is None or self._mgr is None:
            return getattr(self._mgr, "scenario_money_kpi", None) if self._mgr else None
        sm = getattr(self._mgr, "summary_money", None)
        if sm is None or Cols.SKU_ID not in sm.columns:
            return self._mgr.scenario_money_kpi
        filtered = sm[sm[Cols.SKU_ID] == sku]
        if filtered.empty:
            return self._mgr.scenario_money_kpi
        from wom.engine.money import build_scenario_money_kpi
        return build_scenario_money_kpi(filtered)

    # ── Strategic KPI colours ────────────────────────────────────────
    _STATUS_FG = {"OK": "#69F0AE", "WARN": "#FFD740", "ISSUE": "#FF5252"}
    _STATUS_ICON = {"OK": "✅", "WARN": "⚠️", "ISSUE": "🔴"}

    def _refresh_strategic_kpis(self):
        """Update the 5 Strategic KPI card widgets."""
        sku = self._current_sku()
        sc_tree = getattr(self._mgr, "sc_tree", None) if self._mgr else None
        if sku is not None and sc_tree is not None:
            from wom.engine.strategic_kpi import compute_strategic_kpi
            skpi = compute_strategic_kpi(sc_tree, product_filter=sku)
        else:
            skpi = getattr(self._mgr, "strategic_kpi", None) if self._mgr else None
        if skpi is None:
            for card in self._skpi_cards.values():
                card["val_var"].set("--")
                card["status_var"].set("Planning Engine 未実行")
                card["val_lbl"].configure(fg=FG_WHITE)
                card["status_lbl"].configure(fg="#546E7A")
            return

        def _apply(key, value: float, status_fn):
            card = self._skpi_cards[key]
            card["val_var"].set(f"{value:.1%}")
            st = status_fn()
            icon = self._STATUS_ICON.get(st, "")
            card["status_var"].set(f"{icon} {st}")
            card["val_lbl"].configure(fg=self._STATUS_FG.get(st, FG_WHITE))
            card["status_lbl"].configure(fg=self._STATUS_FG.get(st, "#90A4AE"))

        _apply("fixed_cost_coverage", skpi.fixed_cost_coverage,
               skpi.status_fixed_cost_coverage)
        _apply("production_leveling", skpi.production_leveling,
               skpi.status_production_leveling)
        _apply("buffer_retention",    skpi.buffer_retention,
               skpi.status_buffer_retention)
        _apply("fill_rate",           skpi.fill_rate,
               skpi.status_fill_rate)
        _apply("avg_cap_utilization", skpi.avg_cap_utilization,
               skpi.status_cap_utilization)

    def _refresh_lc_table(self):
        """Update the Tariff & FX (Landed Cost) treeview and narrative."""
        sku = self._current_sku()
        lc_scens  = getattr(self._mgr, "lc_scens",  None) if self._mgr else None
        route_idx = getattr(self._mgr, "route_idx", None) if self._mgr else None
        if sku is not None and lc_scens:
            from wom.engine.landed_cost import compare_lc_scenarios
            kpi = self._get_filtered_kpi()
            lc_df = (compare_lc_scenarios(kpi, lc_scens, route_idx or {}, sku_id=sku)
                     if kpi is not None else None)
        else:
            lc_df = getattr(self._mgr, "lc_comparison_df", None) if self._mgr else None
        self._lc_tree.delete(*self._lc_tree.get_children())

        self._lc_narrative.configure(state="normal")
        self._lc_narrative.delete("1.0", "end")

        if lc_df is None or lc_df.empty:
            self._lc_narrative.insert("end",
                "（Edge Cost Master / Route Master を設定して\n"
                "Planning Engine を実行すると\nLanded Cost 分析が表示されます）")
            self._lc_narrative.configure(state="disabled")
            return

        # Phase 2 増分2 (v1r2m0): overlay ledger-sourced Landed Cost values so
        # the Base scenario's landed margin matches the PPC cockpit / P&L
        # Summary (no reconciliation gap), and the tariff sweep is lot-precise
        # rather than money-blended (see _ledger_lc_overrides). Freight is left
        # to the money engine (constant across the sweep, informational; it is
        # already embedded in the ledger cost cascade).
        _lc_ov = self._ledger_lc_overrides(sku)
        if _lc_ov:
            lc_df = lc_df.copy()
            for _i, _r in lc_df.iterrows():
                _o = _lc_ov.get(str(_r.get("lc_scenario", "")))
                if not _o:
                    continue
                for _k, _v in _o.items():
                    if _k in lc_df.columns:
                        lc_df.at[_i, _k] = _v

        _ccy_code, _sym = self._base_ccy()
        for _, row in lc_df.iterrows():
            delta = float(row.get("margin_impact_pp", 0) or 0)
            tag   = "HIGH" if delta < -0.02 else ("MEDIUM" if delta < 0 else "OK")
            self._lc_tree.insert("", "end", tags=(tag,), values=[
                row.get("wom_scenario", ""),
                row.get("lc_scenario",  ""),
                f"{_sym}{float(row.get('revenue', 0) or 0):,.0f}",
                f"{_sym}{float(row.get('customs_duty', 0) or 0):,.0f}",
                f"{_sym}{float(row.get('freight_total', 0) or 0):,.0f}",
                f"{float(row.get('landed_gross_margin', 0) or 0)*100:.1f}%",
                f"{delta*100:+.1f}pp",
                f"{float(row.get('tariff_burden_pct', 0) or 0)*100:.1f}%",
            ])

        # Build narrative
        try:
            from wom.engine.landed_cost import build_lc_narrative
            narrative = build_lc_narrative(lc_df, currency_symbol=_sym)
        except Exception:
            narrative = "（Landed Cost 分析完了）"
        self._lc_narrative.insert("end", narrative)
        self._lc_narrative.configure(state="disabled")

    def _base_ccy(self):
        """Return (code, symbol) of the PPC ledger's base currency for display
        (e.g. ("JPY","¥"), ("USD","$")). Read from ppc_kpi_summary.json's
        base_currency so labels match the reporting currency of the run.
        Falls back to ("USD","$") when unavailable."""
        import json
        base = getattr(self, "_node_pl_output_dir", "output/ppc")
        try:
            p = os.path.join(base, "ppc_kpi_summary.json")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    code = str(json.load(f).get("base_currency", "") or "").strip()
                if code:
                    sym = {"JPY": "¥", "USD": "$", "EUR": "€",
                           "GBP": "£", "CNY": "¥", "THB": "฿"}.get(code, code + " ")
                    return code, sym
        except Exception:
            pass
        return "USD", "$"

    def _ledger_lc_overrides(self, sku):
        """Phase 2 増分2 (v1r2m0): re-derive the Landed Cost table's
        Revenue / Customs Duty / Landed GM% / ΔMargin / Tariff% from the
        single PPC event ledger (ppc_node_pl_summary.csv), so the Base
        scenario's landed margin equals the PPC cockpit and the P&L Summary
        (closes the reconciliation gap), and the tariff sweep
        (Base/Tariff10/Tariff0) is lot-precise instead of money-blended.

        Each scenario's tariff is obtained by scaling every channel's
        Base-scenario tariff (from the ledger) by rate(scenario)/rate(Base)
        for that channel's destination country — exact while the tariff basis
        (transfer price) is unchanged across the sweep, which it is. Freight is
        left to the existing engine (constant across the sweep, informational;
        already embedded in the ledger cost cascade).

        Returns {lc_scenario_name: {revenue, customs_duty,
        landed_gross_margin, margin_impact_pp, tariff_burden_pct}} or None
        (caller then keeps the money-engine values).
        """
        base_dir  = getattr(self, "_node_pl_output_dir", "output/ppc")
        pl_path   = os.path.join(base_dir, "ppc_node_pl_summary.csv")
        lc_scens  = getattr(self._mgr, "lc_scens",  None) if self._mgr else None
        model_dir = getattr(self._mgr, "model_dir", "")   if self._mgr else ""
        if not (os.path.exists(pl_path) and lc_scens and model_dir):
            return None
        try:
            df = pd.read_csv(pl_path)
            if sku and sku != "All" and "product_id" in df.columns:
                df = df[df["product_id"] == sku]
            if df.empty:
                return None
            pz_path = os.path.join(model_dir, "ppc_node_profit_zone.csv")
            if not os.path.exists(pz_path):
                return None
            pz = pd.read_csv(pz_path)
            node_country = {str(r["node_id"]): str(r.get("country", "") or "").strip()
                            for _, r in pz.iterrows()}

            total_cost   = float(df["cost_base"].sum())
            total_tariff = float(df["tariff_base"].sum())
            chan = df[df["revenue_base"] > 0]              # leaf_out channels
            revenue = float(chan["revenue_base"].sum())
            if revenue <= 0:
                return None
            # Tariff may be attributed to the leaf_out channel (soysauce) OR to
            # the import DAD node (apparel: DC_Local_US). Aggregate EVERY
            # tariff-bearing row keyed by that node's country, so Customs is not
            # undercounted when the tariff sits on a non-channel node. Rows whose
            # country is unknown keep their tariff unchanged across the sweep
            # (rate factor 1) instead of being dropped.
            node_tariff = []                               # (country_or_"", base tariff)
            for _, r in df.iterrows():
                _t = r.get("tariff_base", 0)
                _t = float(_t) if pd.notna(_t) else 0.0
                if _t == 0:
                    continue
                node_tariff.append((node_country.get(str(r["node_id"]), ""), _t))

            def country_rate(scen):
                m = {}
                sc = lc_scens.get(scen)
                if sc:
                    for p in sc.profiles:
                        m[str(p.dst_region)] = float(p.tariff_rate)
                return m

            base_name = "Base" if "Base" in lc_scens else next(iter(lc_scens))
            base_rate = country_rate(base_name)

            def scen_tariff(scen):
                rate = country_rate(scen)
                tot = 0.0
                for c, t in node_tariff:
                    rb = base_rate.get(c, 0.0)
                    rs = rate.get(c, rb)
                    tot += t * (rs / rb) if rb > 0 else t
                return tot

            out, gm = {}, {}
            for scen in lc_scens:
                st = scen_tariff(scen)
                landed_cogs = total_cost - total_tariff + st
                g = (revenue - landed_cogs) / revenue if revenue else 0.0
                gm[scen] = g
                out[scen] = {
                    "revenue":             revenue,
                    "customs_duty":        st,
                    "landed_gross_margin": g,
                    "tariff_burden_pct":   (st / revenue) if revenue else 0.0,
                }
            base_g = gm.get(base_name, 0.0)
            for scen in out:
                out[scen]["margin_impact_pp"] = gm[scen] - base_g
            return out
        except Exception as exc:
            print(f"[Management] ledger Landed Cost override error: {exc}")
            return None

    def _ledger_pl_for_sku(self, sku):
        """Phase 2 (v1r2m0): single-source P&L top-line from the PPC event
        ledger, so the Management P&L Summary matches the PPC cockpit
        (no reconciliation gap). Returns (revenue, cogs, gross_profit,
        gross_margin) in base currency, or None if the ledger output is
        unavailable (falls back to the money engine).

        sku == "All"/None -> ppc_kpi_summary.json totals;
        a specific sku   -> aggregate ppc_node_pl_summary.csv for that product.
        Working-capital metrics (Inv/CCC/AR/AP) still come from money.py.
        """
        import json
        base = getattr(self, "_node_pl_output_dir", "output/ppc")
        try:
            if not sku or sku == "All":
                p = os.path.join(base, "ppc_kpi_summary.json")
                if not os.path.exists(p):
                    return None
                with open(p, encoding="utf-8") as f:
                    k = json.load(f)
                rev  = float(k.get("total_revenue_base", 0) or 0)
                cogs = float(k.get("total_cost_base", 0) or 0)
                gp   = float(k.get("gross_profit_base", rev - cogs) or 0)
                gm   = float(k.get("gross_margin_pct", 0) or 0)
                return (rev, cogs, gp, gm)
            p = os.path.join(base, "ppc_node_pl_summary.csv")
            if not os.path.exists(p):
                return None
            df = pd.read_csv(p)
            if "product_id" in df.columns:
                df = df[df["product_id"] == sku]
            if df.empty:
                return None
            rev  = float(df["revenue_base"].sum())
            cogs = float(df["cost_base"].sum())
            gp   = rev - cogs
            gm   = (gp / rev) if rev else 0.0
            return (rev, cogs, gp, gm)
        except Exception as exc:
            print(f"[Management] ledger P&L load error: {exc}")
            return None

    def _refresh_pl_table(self):
        if self._mgr is None:
            return
        kpi = self._get_filtered_kpi()
        if kpi is None:
            return
        # Phase 2: P&L top-line (Revenue/COGS/GP/GM) is sourced from the single
        # PPC event ledger; working capital stays from the money engine. PPC
        # currently evaluates the planning result only, so the same ledger
        # applies to the displayed (Planning) row(s). (Scenario-specific PPC
        # re-runs are future work.)
        _ledger = self._ledger_pl_for_sku(self._current_sku())
        self._pl_tree.delete(*self._pl_tree.get_children())
        for _, row in kpi.iterrows():
            rev  = float(row.get(Cols.REVENUE,      0) or 0)
            cogs = float(row.get(Cols.COGS,         0) or 0)
            gp   = float(row.get(Cols.GROSS_PROFIT, 0) or 0)
            gm   = float(row.get(Cols.GROSS_MARGIN, 0) or 0)
            inv  = float(row.get(Cols.INV_VALUE_COST,0) or 0)
            ccc  = float(row.get(Cols.CCC_WKS,      0) or 0)
            ar   = float(row.get(Cols.AR_VALUE,     0) or 0)
            ap   = float(row.get(Cols.AP_VALUE,     0) or 0)
            if _ledger is not None:
                rev, cogs, gp, gm = _ledger   # Phase 2: single-source from PPC ledger
            scen = row.get(Cols.SCENARIO, "")
            self._pl_tree.insert("", "end", values=[
                scen,
                f"{rev:,.0f}",
                f"{cogs:,.0f}",
                f"{gp:,.0f}",
                f"{gm*100:.1f}%",
                f"{inv:,.0f}",
                f"{ccc:.1f}",
                f"{ar:,.0f}",
                f"{ap:,.0f}",
            ])

    def _refresh_charts(self):
        if self._mgr is None:
            return
        kpi = self._get_filtered_kpi()
        if kpi is None:
            return
        scenarios = kpi[Cols.SCENARIO].tolist()
        colours = [COLOURS.get(s, DEFAULT_COLOURS[i % len(DEFAULT_COLOURS)])
                   for i, s in enumerate(scenarios)]

        # CCC chart
        self._ccc_fig.clf()
        ax = self._ccc_fig.add_subplot(111)
        ax.set_facecolor(BG_MID)
        self._ccc_fig.patch.set_facecolor(BG_DARK)
        ccc_vals = [float(kpi.loc[kpi[Cols.SCENARIO] == s, Cols.CCC_WKS].iloc[0])
                    if s in kpi[Cols.SCENARIO].values else 0 for s in scenarios]
        bars = ax.bar(range(len(scenarios)), ccc_vals, color=colours, alpha=0.85)
        ax.set_xticks(range(len(scenarios)))
        ax.set_xticklabels(scenarios, color=FG_WHITE, fontsize=9)
        ax.set_ylabel("Weeks", color=FG_ACC, fontsize=8)
        ax.tick_params(colors=FG_WHITE, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(BG_LIGHT)
        for bar, val in zip(bars, ccc_vals):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                    f"{val:.1f}w", ha="center", va="bottom",
                    color=FG_WHITE, fontsize=8)
        self._ccc_canvas.draw()

        # Gross Profit chart
        self._gp_fig.clf()
        ax2 = self._gp_fig.add_subplot(111)
        ax2.set_facecolor(BG_MID)
        self._gp_fig.patch.set_facecolor(BG_DARK)
        gp_vals  = [float(kpi.loc[kpi[Cols.SCENARIO] == s, Cols.GROSS_PROFIT].iloc[0])
                    if s in kpi[Cols.SCENARIO].values else 0 for s in scenarios]
        rev_vals = [float(kpi.loc[kpi[Cols.SCENARIO] == s, Cols.REVENUE].iloc[0])
                    if s in kpi[Cols.SCENARIO].values else 0 for s in scenarios]
        gm_vals  = [float(kpi.loc[kpi[Cols.SCENARIO] == s, Cols.GROSS_MARGIN].iloc[0])
                    if s in kpi[Cols.SCENARIO].values else 0 for s in scenarios]
        # Phase 2 (v1r2m0): single-source Revenue/GP/GM from the PPC ledger so
        # this chart matches the P&L Summary / PPC cockpit (the money summary is
        # a coarse aggregate; same overlay as _refresh_pl_table).
        _led = self._ledger_pl_for_sku(self._current_sku())
        if _led is not None:
            _lrev, _lcogs, _lgp, _lgm = _led
            rev_vals = [_lrev for _ in scenarios]
            gp_vals  = [_lgp  for _ in scenarios]
            gm_vals  = [_lgm  for _ in scenarios]
        x = range(len(scenarios))
        ax2.bar(x, rev_vals, color=colours, alpha=0.35, label="Revenue")
        ax2.bar(x, gp_vals,  color=colours, alpha=0.85, label="Gross Profit")
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(scenarios, color=FG_WHITE, fontsize=9)
        ax2.set_ylabel(f"Value ({self._base_ccy()[0]})", color=FG_ACC, fontsize=8)
        ax2.tick_params(colors=FG_WHITE, labelsize=8)
        ax2.legend(facecolor=BG_LIGHT, labelcolor=FG_WHITE, fontsize=8)
        for spine in ax2.spines.values():
            spine.set_edgecolor(BG_LIGHT)
        # Margin % annotations
        for xi, gm_val in enumerate(gm_vals):
            ax2.text(xi, gp_vals[xi] * 1.02, f"{gm_val*100:.1f}%",
                     ha="center", va="bottom", color=FG_WHITE, fontsize=8)
        self._gp_canvas.draw()

    def _refresh_issue_selector(self):
        if self._mgr is None:
            return
        self._mgmt_data = getattr(self._mgr, "management_results", {})
        scenarios = list(self._mgmt_data.keys())
        self._issue_scen_cb["values"] = scenarios
        if scenarios:
            self._issue_scen_var.set(scenarios[0])
            self._refresh_issues()
        else:
            self._narrative_text.configure(state="normal")
            self._narrative_text.delete("1.0", "end")
            self._narrative_text.insert("end", "（Base シナリオのみの場合、比較分析は表示されません）")
            self._narrative_text.configure(state="disabled")

    def _refresh_issues(self):
        scen = self._issue_scen_var.get()
        result: Optional[ManagementAnalysisResult] = self._mgmt_data.get(scen)
        self._issue_tree.delete(*self._issue_tree.get_children())
        if result is None:
            return
        for iss in result.issues:
            sev = iss.severity
            self._issue_tree.insert("", "end", tags=(sev,), values=[
                "ISSUE", sev, iss.scenario, iss.code, iss.title_ja
            ])
        for rsk in result.risks:
            self._issue_tree.insert("", "end", tags=("RISK",), values=[
                "RISK", rsk.severity, rsk.scenario, rsk.code, rsk.title_ja
            ])
        # Narrative (management analysis + strategic KPI)
        self._narrative_text.configure(state="normal")
        self._narrative_text.delete("1.0", "end")
        self._narrative_text.insert("end", result.narrative or "（分析結果なし）")
        # Append Strategic KPI narrative if available
        skpi = getattr(self._mgr, "strategic_kpi", None) if self._mgr else None
        if skpi is not None:
            self._narrative_text.insert("end", "\n\n" + skpi.to_narrative_ja())
        self._narrative_text.configure(state="disabled")


# ──────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────
# PPC Financial KPI Tab
# ──────────────────────────────────────────────────────────────────────

class PPCTabPanel(tk.Frame):
    """
    PPC Financial KPI tab — embeds PPCCockpitApp (B1 integration).

    Shows a placeholder if output/ppc/ has not been generated yet.
    Provides a Refresh button to reload after running python -m wom.ppc.
    """

    def __init__(self, parent, output_dir: str = "output/ppc", **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._output_dir = output_dir
        self._cockpit = None
        self._build_frame()
        self._try_load()

    def _build_frame(self) -> None:
        # Header bar
        hdr = tk.Frame(self, bg=BG_MID)
        hdr.pack(fill="x")

        tk.Label(hdr, text="  \U0001f4b0 PPC Financial KPI",
                 bg=BG_MID, fg=FG_ACC,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=6, pady=5)

        self._status_var = tk.StringVar(value="")
        tk.Label(hdr, textvariable=self._status_var,
                 bg=BG_MID, fg="#90A4AE",
                 font=("Segoe UI", 8)).pack(side="left", padx=10)

        tk.Button(
            hdr, text="\u27f3  Refresh",
            bg=BG_LIGHT, fg=FG_WHITE,
            font=("Segoe UI", 9), relief=tk.FLAT, padx=8, pady=3,
            activebackground=BG_MID, activeforeground=FG_ACC,
            command=self._try_load,
        ).pack(side="right", padx=8, pady=4)

        # Content area (cockpit goes here)
        self._content = tk.Frame(self, bg=BG_DARK)
        self._content.pack(fill="both", expand=True)

        # Placeholder shown until PPC output exists
        self._placeholder = tk.Frame(self._content, bg=BG_DARK)
        self._placeholder.pack(fill="both", expand=True)

        msg = (
            "PPC output not found.\n\n"
            "Run the PPC engine first:\n"
            "    python -m wom.ppc\n\n"
            "Then click  \u27f3 Refresh  above."
        )
        tk.Label(
            self._placeholder, text=msg,
            bg=BG_DARK, fg="#546E7A",
            font=("Segoe UI", 12), justify="center",
        ).pack(expand=True)

    def _try_load(self) -> None:
        """Load PPCCockpitApp from output_dir. Show placeholder if unavailable."""
        kpi_path = os.path.join(self._output_dir, "ppc_kpi_summary.json")

        if not os.path.exists(kpi_path):
            self._status_var.set(f"No PPC data — run  python -m wom.ppc  first")
            self._show_placeholder()
            return

        try:
            from wom.ppc.ppc_cockpit_app import PPCCockpitApp
        except Exception as exc:
            self._status_var.set(f"Import error: {exc}")
            self._show_placeholder()
            return

        # Save current filter state before destroying old cockpit
        _saved = {}
        if self._cockpit is not None:
            for _attr in ("_sku_var", "_channel_var", "_start_var", "_end_var", "_agg_var"):
                _v = getattr(self._cockpit, _attr, None)
                if _v is not None:
                    _saved[_attr] = _v.get()
            self._cockpit.destroy()
            self._cockpit = None

        self._placeholder.pack_forget()

        try:
            self._cockpit = PPCCockpitApp(
                self._content, output_dir=self._output_dir
            )
            # Restore filter selections after rebuild
            for _attr, _val in _saved.items():
                _v = getattr(self._cockpit, _attr, None)
                if _v is not None:
                    try:
                        _v.set(_val)
                    except Exception:
                        pass
            self._cockpit.pack(fill="both", expand=True)
            self._status_var.set(f"Loaded  {self._output_dir}/")
            # Re-apply filters so charts reflect restored SKU/channel selection
            if _saved and hasattr(self._cockpit, '_redraw'):
                try:
                    self._cockpit.after(50, self._cockpit._redraw)
                except Exception:
                    pass
        except Exception as exc:
            self._status_var.set(f"Load error: {exc}")
            self._show_placeholder()

    def _show_placeholder(self) -> None:
        if self._cockpit is not None:
            self._cockpit.pack_forget()
        self._placeholder.pack(fill="both", expand=True)

    def refresh(self, output_dir: Optional[str] = None) -> None:
        """Public API — call after running the PPC engine."""
        if output_dir:
            self._output_dir = output_dir
        self._try_load()


# PSI List Panel  (lot-ID based PSI, Steps 3-8)
# ──────────────────────────────────────────────────────────────────────

class PSIListPanel(tk.Frame):
    """
    Shows lot-ID based PSI data (psi4demand or psi4supply) for one PlanNode.

    Layout:
      ┌─ node header (node_id, plan_mode, lt, type) ── [Demand] [Supply] ─┐
      │  Treeview: Week | S | CO | I | P  (lot counts)                     │
      │  ──────────────────────────────────────────────────────────────    │
      │  Lot IDs text box  (shows lot strings for selected row)            │
      │  Summary: totals                                                   │
      └───────────────────────────────────────────────────────────────────┘
    """

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._node = None           # current PlanNode
        self._layer_var = tk.StringVar(value="supply")
        self._build()

    # ── Layout ──────────────────────────────────────────────────────────

    def _build(self):
        # ── Header: node info + layer toggle ─────────────────────────
        hdr = tk.Frame(self, bg=BG_MID, pady=4)
        hdr.pack(fill="x")

        self._node_var = tk.StringVar(value="No node loaded — use the node selector above")
        tk.Label(hdr, textvariable=self._node_var,
                 bg=BG_MID, fg=FG_ACC,
                 font=("Segoe UI", 8, "bold"),
                 anchor="w").pack(side="left", padx=8, fill="x", expand=True)

        tk.Label(hdr, text="Layer:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 8)).pack(side="right", padx=(0, 4))
        for val, txt in (("demand", "Demand"), ("supply", "Supply")):
            tk.Radiobutton(
                hdr, text=txt, variable=self._layer_var, value=val,
                bg=BG_MID, fg=FG_WHITE, selectcolor=BG_LIGHT,
                activebackground=BG_MID, font=("Segoe UI", 8),
                command=self._refresh,
            ).pack(side="right", padx=2)

        # ── Treeview ─────────────────────────────────────────────────
        tree_frame = tk.Frame(self, bg=BG_DARK)
        tree_frame.pack(fill="both", expand=True, padx=2, pady=2)

        cols = ("week", "S", "CO", "I", "P", "CapH", "CapS")
        self._tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings",
            height=12, selectmode="browse",
        )
        col_cfg = {"week": (90, "w",      True),
                   "S":    (50, "center", False),
                   "CO":   (50, "center", False),
                   "I":    (50, "center", False),
                   "P":    (50, "center", False),
                   "CapH": (52, "center", False),
                   "CapS": (52, "center", False)}
        cap_heads = {"CapH": "CapHard", "CapS": "CapSoft"}
        for col in cols:
            w, anchor, stretch = col_cfg[col]
            self._tree.heading(col, text=cap_heads.get(col, col))
            self._tree.column(col, width=w, anchor=anchor, stretch=stretch)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Apply dark-theme style
        style = ttk.Style()
        style.configure("PSI.Treeview",
                        background=BG_MID, foreground=FG_WHITE,
                        fieldbackground=BG_MID, rowheight=18,
                        font=("Segoe UI", 8))
        style.configure("PSI.Treeview.Heading",
                        background=BG_LIGHT, foreground=FG_ACC,
                        font=("Segoe UI", 8, "bold"))
        style.map("PSI.Treeview",
                  background=[("selected", "#37474F")],
                  foreground=[("selected", FG_WHITE)])
        self._tree.configure(style="PSI.Treeview")

        # ── Lot detail ───────────────────────────────────────────────
        # ── Capacity chart (always packed; content updated by _refresh) ──
        self._cap_chart_frame = tk.Frame(self, bg=BG_DARK, height=140)
        self._cap_chart_frame.pack_propagate(False)   # keep fixed height
        self._cap_chart_frame.pack(fill="x", padx=2, pady=(0, 2))

        self._cap_fig = Figure(figsize=(5, 1.55), dpi=88, facecolor=BG_DARK)
        self._cap_canvas = FigureCanvasTkAgg(
            self._cap_fig, master=self._cap_chart_frame)
        self._cap_canvas.get_tk_widget().pack(fill="both", expand=True)
        self._cap_chart_visible = True   # always visible

        self._det_frame = tk.LabelFrame(
            self, text="  Lot IDs  ",
            bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 8, "bold"),
            relief="groove", bd=1,
        )
        self._det_frame.pack(fill="x", padx=2, pady=(0, 2))

        inner = tk.Frame(self._det_frame, bg=BG_MID)
        inner.pack(fill="x", padx=4, pady=2)

        self._lot_text = tk.Text(
            inner, height=5, bg=BG_LIGHT, fg=FG_WHITE,
            font=("Consolas", 7), relief="flat", wrap="none",
            state="disabled",
        )
        lot_vsb = ttk.Scrollbar(inner, orient="vertical",
                                command=self._lot_text.yview)
        lot_hsb = ttk.Scrollbar(self._det_frame, orient="horizontal",
                                command=self._lot_text.xview)
        self._lot_text.configure(yscrollcommand=lot_vsb.set,
                                 xscrollcommand=lot_hsb.set)
        lot_vsb.pack(side="right", fill="y")
        self._lot_text.pack(side="left", fill="x", expand=True)
        lot_hsb.pack(fill="x", padx=4, pady=(0, 2))

        # ── Summary bar ──────────────────────────────────────────────
        self._summary_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._summary_var,
                 bg=BG_DARK, fg="#90A4AE",
                 font=("Segoe UI", 7), anchor="w",
                 ).pack(fill="x", padx=6, pady=(0, 2))

    # ── Data load ────────────────────────────────────────────────────

    def load_node(self, node) -> None:
        """Load a PlanNode and display its PSI data."""
        self._node = node
        self._refresh()

    # ── Internal helpers ─────────────────────────────────────────────

    def _refresh(self):
        if self._node is None:
            return
        node  = self._node
        layer = self._layer_var.get()           # "demand" | "supply"
        psi   = node.psi4demand if layer == "demand" else node.psi4supply

        # Node metadata header
        mode_badges = {
            "pull":     "PULL",
            "push":     "★ PUSH",
            "push_sub": "→ PUSH-SUB",
        }
        mode_str = mode_badges.get(node.plan_mode, node.plan_mode)
        decp_str = " · DECOUPLING" if node.is_decoupling else ""
        self._node_var.set(
            f"{node.node_id}  │  {mode_str}{decp_str}"
            f"  │  lt={node.lt_wks}w  │  {node.node_type}"
        )

        # Clear treeview
        for row_id in self._tree.get_children():
            self._tree.delete(row_id)

        if not node.week_labels or not psi:
            self._summary_var.set("(no PSI data)")
            return

        from wom.model.plan_node import S as S_, CO as CO_, I as I_, P as P_

        tot_s = tot_co = tot_i = tot_p = 0
        has_cap = False

        for w, wk_label in enumerate(node.week_labels):
            sq  = len(psi[w][S_])
            coq = len(psi[w][CO_])
            iq  = len(psi[w][I_])
            pq  = len(psi[w][P_])
            ch  = node.cap_hard(w)
            cs  = node.cap_soft(w)

            tot_s  += sq
            tot_co += coq
            tot_i  += iq
            tot_p  += pq
            if ch > 0 or cs > 0:
                has_cap = True

            # Row colour: capacity violation takes priority
            if ch > 0 and pq > ch:
                tag = "over_hard"
            elif cs > 0 and pq > cs:
                tag = "over_soft"
            elif any([sq, coq, iq, pq]):
                tag = "active"
            else:
                tag = "zero"

            self._tree.insert(
                "", "end", iid=str(w),
                values=(wk_label,
                        sq  if sq  else "—",
                        coq if coq else "—",
                        iq  if iq  else "—",
                        pq  if pq  else "—",
                        f"{ch:.0f}" if ch > 0 else "—",
                        f"{cs:.0f}" if cs > 0 else "—"),
                tags=(tag,),
            )

        self._tree.tag_configure("over_hard",
                                 foreground="#FFCDD2", background="#7B1212")
        self._tree.tag_configure("over_soft",
                                 foreground="#FFE0B2", background="#7B4500")
        self._tree.tag_configure("active",
                                 foreground=FG_WHITE,  background=BG_MID)
        self._tree.tag_configure("zero",
                                 foreground="#546E7A", background=BG_DARK)

        # Capacity chart: always draw (shows "no cap" placeholder if unset)
        self._draw_capacity_chart(node, psi)

        layer_str = "Demand" if layer == "demand" else "Supply"
        self._summary_var.set(
            f"Total {layer_str}:  "
            f"S={tot_s}  CO={tot_co}  I={tot_i}  P={tot_p}"
        )

        # Scroll to first active week
        for iid in self._tree.get_children():
            if self._tree.tag_has("active", iid):
                self._tree.see(iid)
                break

    def _on_select(self, event):
        """Show lot IDs for the selected week row."""
        sel = self._tree.selection()
        if not sel or self._node is None:
            return
        w     = int(sel[0])
        node  = self._node
        layer = self._layer_var.get()
        psi   = node.psi4demand if layer == "demand" else node.psi4supply

        from wom.model.plan_node import S as S_, CO as CO_, I as I_, P as P_

        lines = []
        for bidx, bname in [(S_, "S"), (CO_, "CO"), (I_, "I"), (P_, "P")]:
            lots = psi[w][bidx]
            if lots:
                lines.append(f"── {bname} ({len(lots)} lots) ──")
                lines.extend(f"  {lot}" for lot in lots)
        text = "\n".join(lines) if lines else "(all buckets empty this week)"

        self._lot_text.config(state="normal")
        self._lot_text.delete("1.0", "end")
        self._lot_text.insert("end", text)
        self._lot_text.config(state="disabled")


    def _draw_capacity_chart(self, node, psi):
        """
        Draw P-quantity bars with CapHard (red dashed) and CapSoft (orange
        dotted) reference lines.  Always called; shows placeholder if no cap.
        """
        from wom.model.plan_node import P as P_

        n     = len(node.week_labels)
        p_qty = [len(psi[w][P_]) for w in range(n)]
        ch_v  = [node.cap_hard(w) for w in range(n)]
        cs_v  = [node.cap_soft(w) for w in range(n)]

        max_ch = max(ch_v) if ch_v else 0
        max_cs = max(cs_v) if cs_v else 0

        self._cap_fig.clf()
        ax = self._cap_fig.add_subplot(111)
        ax.set_facecolor(BG_MID)
        self._cap_fig.patch.set_facecolor(BG_DARK)

        # Placeholder when no capacity data
        if max_ch == 0 and max_cs == 0:
            ax.text(0.5, 0.5, "No CapHard / CapSoft set on this node",
                    color="#546E7A", ha="center", va="center",
                    transform=ax.transAxes, fontsize=8)
            ax.set_title("Capacity Chart", color="#546E7A", fontsize=8, pad=3)
            ax.axis("off")
            self._cap_canvas.draw()
            return

        # Bar colours: red = over CapHard, orange = over CapSoft, green = OK
        bar_colors = []
        for w in range(n):
            ch = ch_v[w]; cs = cs_v[w]; p = p_qty[w]
            if ch > 0 and p > ch:
                bar_colors.append("#F44336")
            elif cs > 0 and p > cs:
                bar_colors.append("#FF9800")
            else:
                bar_colors.append("#4CAF50")

        x = list(range(n))
        ax.bar(x, p_qty, color=bar_colors, alpha=0.85, width=0.8)

        # Sealing lines
        if max_ch > 0:
            ax.axhline(max_ch, color="#F44336", linewidth=1.5,
                       linestyle="--", label=f"CapHard = {max_ch:.0f}")
        if max_cs > 0:
            ax.axhline(max_cs, color="#FF9800", linewidth=1.5,
                       linestyle=":",  label=f"CapSoft = {max_cs:.0f}")

        # X-axis ticks: 4-4-5 retail calendar monthly ticks
        _t_idx, _t_lbl = _445_ticks(node.week_labels)
        if _t_idx:
            ax.set_xticks(_t_idx)
            ax.set_xticklabels(_t_lbl, rotation=0, ha="center", fontsize=5)
        else:
            step = max(1, n // 6)
            ticks = list(range(0, n, step))
            ax.set_xticks(ticks)
            ax.set_xticklabels([node.week_labels[i] for i in ticks],
                               rotation=28, ha="right", fontsize=5)

        ax.set_ylabel("P (lots)", color=FG_ACC, fontsize=7)
        ax.set_title("P vs Capacity Limits", color=FG_WHITE, fontsize=8, pad=3)
        ax.tick_params(colors=FG_WHITE, labelsize=5)
        for spine in ax.spines.values():
            spine.set_edgecolor(BG_LIGHT)

        handles = []
        from matplotlib.patches import Patch
        handles.append(Patch(facecolor="#4CAF50", label="P (OK)"))
        if max_cs > 0:
            handles.append(Patch(facecolor="#FF9800", label=f"P > CapSoft"))
        if max_ch > 0:
            handles.append(Patch(facecolor="#F44336", label=f"P > CapHard"))

        import matplotlib.lines as mlines
        if max_ch > 0:
            handles.append(mlines.Line2D([], [], color="#F44336",
                linewidth=1.5, linestyle="--", label=f"CapHard={max_ch:.0f}"))
        if max_cs > 0:
            handles.append(mlines.Line2D([], [], color="#FF9800",
                linewidth=1.5, linestyle=":",  label=f"CapSoft={max_cs:.0f}"))

        ax.legend(handles=handles, facecolor=BG_LIGHT, labelcolor=FG_WHITE,
                  fontsize=6, loc="upper right", ncol=2)

        self._cap_canvas.draw()

# SC Network Cockpit Panel  (PySI-style hammock model)
# ──────────────────────────────────────────────────────────────────────

class SCNetworkPanel(tk.Frame):
    """
    🌐 SC Network tab — split panel inspired by PySI GUI design.

    Left:  NetworkX hammock-model graph (InBound green / OutBound blue)
           Click a node to select it.
    Right: PSI chart (P/S/I bars+line) + Cost/Revenue chart for selected node.
    """

    # Node colour palette
    _NCOLOUR = {
        "global":  "#FF9800",   # orange  – Global HQ nodes
        "mother":  "#9C27B0",   # purple  – Mother Plant
        "sku":     "#4CAF50",   # green   – SKU / production (InBound)
        "region":  "#2196F3",   # blue    – Region (OutBound)
    }
    _HIGHLIGHT = "#FFEB3B"      # yellow  – selected node

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._mgr: Optional[ScenarioManager] = None
        self._node_map: dict = {}      # node_label → {"sku": str|None, "region": str|None}
        self._selected_node: str = ""
        self._pos: dict = {}           # node_label → (x, y) data coords
        self._scenario_var = tk.StringVar(value="Base")
        self._sc_tree = None           # Step 9: lot-based planning tree (SCTree)
        # ── Event Flow Tracing state ──────────────────────────────────
        self._timeline       = None    # list[WeekSnapshot] after planning
        self._anim_running   = False
        self._anim_week      = 0
        self._anim_speed_ms  = 1000   # ms per week tick
        self._anim_after_id  = None
        self._build()

    # ── Layout ──────────────────────────────────────────────────────

    def _build(self):
        # Control bar
        bar = tk.Frame(self, bg=BG_MID, pady=4)
        bar.pack(fill="x", side="top")

        tk.Label(bar, text="Scenario:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
        self._scen_cb = ttk.Combobox(bar, textvariable=self._scenario_var,
                                     width=12, state="readonly",
                                     font=("Segoe UI", 9))
        self._scen_cb.pack(side="left", padx=2)
        self._scen_cb.bind("<<ComboboxSelected>>", lambda _: self._refresh_right())

        # Product selector (shown only in hammock mode after Planning Engine)
        tk.Label(bar, text="Product:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        self._prod_var = tk.StringVar(value="")
        self._prod_cb = ttk.Combobox(bar, textvariable=self._prod_var,
                                     width=14, state="readonly",
                                     font=("Segoe UI", 9))
        self._prod_cb.pack(side="left", padx=2)
        self._prod_cb.bind("<<ComboboxSelected>>",
                           lambda _: self._redraw_hammock())

        self._node_lbl_var = tk.StringVar(value="← Click a node to inspect its PSI / Cost")
        tk.Label(bar, textvariable=self._node_lbl_var,
                 bg=BG_MID, fg=FG_ACC,
                 font=("Segoe UI", 9, "italic")).pack(side="left", padx=16)

        if not HAS_NX:
            tk.Label(self,
                     text="networkx not installed.\nRun:  pip install networkx",
                     bg=BG_DARK, fg="#FF6B6B",
                     font=("Segoe UI", 11)).pack(expand=True)
            return

        # PanedWindow — stacked top-to-bottom (2026-07-14 layout revision,
        # GUI review finding): network graph / PSI graph / Revenue graph all
        # share the SAME full width instead of squeezing the network graph
        # into a half-width left pane. Top: network graph. Bottom: the PSI
        # Chart tab (which already stacks PSI over Cost/Revenue vertically)
        # plus the PSI List tab.
        paned = tk.PanedWindow(self, orient="vertical", bg=BG_DARK,
                               sashwidth=5, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # ── Top: NetworkX graph (full width) ────────────────────────────
        lf = tk.Frame(paned, bg=BG_DARK)
        paned.add(lf, minsize=260)

        self._net_fig = Figure(figsize=(9, 4), dpi=90, facecolor=BG_DARK)
        self._net_canvas = FigureCanvasTkAgg(self._net_fig, master=lf)
        self._net_canvas.get_tk_widget().pack(fill="both", expand=True)
        self._net_canvas.mpl_connect("button_press_event", self._on_node_click)

        # ── Event Flow animation controls ─────────────────────────────
        anim_bar = tk.Frame(lf, bg=BG_MID, pady=3)
        anim_bar.pack(fill="x", side="bottom")

        self._anim_play_btn = tk.Button(
            anim_bar, text="▶", width=3,
            command=self._anim_play,
            bg="#1B5E20", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", state="disabled")
        self._anim_play_btn.pack(side="left", padx=(6, 2))

        self._anim_pause_btn = tk.Button(
            anim_bar, text="⏸", width=3,
            command=self._anim_pause,
            bg=BG_LIGHT, fg=FG_WHITE, font=("Segoe UI", 9),
            relief="flat", state="disabled")
        self._anim_pause_btn.pack(side="left", padx=2)

        self._anim_stop_btn = tk.Button(
            anim_bar, text="⏹", width=3,
            command=self._anim_stop,
            bg=BG_LIGHT, fg=FG_WHITE, font=("Segoe UI", 9),
            relief="flat", state="disabled")
        self._anim_stop_btn.pack(side="left", padx=2)

        tk.Label(anim_bar, text="Speed:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 8)).pack(side="left", padx=(8, 2))
        self._speed_var = tk.StringVar(value="1×")
        speed_cb = ttk.Combobox(anim_bar, textvariable=self._speed_var,
                                values=["0.5×", "1×", "2×", "4×"],
                                width=5, state="readonly",
                                font=("Segoe UI", 8))
        speed_cb.pack(side="left", padx=2)
        speed_cb.bind("<<ComboboxSelected>>", self._on_speed_change)

        self._week_lbl_var = tk.StringVar(value="Event Flow Tracing  (Run Planning Engine first)")
        tk.Label(anim_bar, textvariable=self._week_lbl_var,
                 bg=BG_MID, fg=FG_ACC,
                 font=("Segoe UI", 8, "italic")).pack(side="left", padx=10)

        # ── Bottom: sub-notebook (PSI Chart | PSI List), full width ──────
        rf = tk.Frame(paned, bg=BG_DARK)
        paned.add(rf, minsize=380)

        right_nb = ttk.Notebook(rf)
        right_nb.pack(fill="both", expand=True)

        # Tab 1 – PSI Chart (existing matplotlib charts, PSI stacked over
        # Cost/Revenue -- middle/bottom rows of the 3-row layout)
        chart_frame = tk.Frame(right_nb, bg=BG_DARK)
        right_nb.add(chart_frame, text="  PSI Chart  ")

        self._psi_fig = Figure(figsize=(9, 3), dpi=90, facecolor=BG_DARK)
        self._psi_canvas = FigureCanvasTkAgg(self._psi_fig, master=chart_frame)
        self._psi_canvas.get_tk_widget().pack(fill="both", expand=True)

        self._cost_fig = Figure(figsize=(9, 3), dpi=90, facecolor=BG_DARK)
        self._cost_canvas = FigureCanvasTkAgg(self._cost_fig, master=chart_frame)
        self._cost_canvas.get_tk_widget().pack(fill="both", expand=True)

        # Tab 2 – PSI List (lot-ID based, Steps 3-8)
        psi_list_outer = tk.Frame(right_nb, bg=BG_DARK)
        right_nb.add(psi_list_outer, text="  📋 PSI List  ")

        # Node selector bar
        sel_bar = tk.Frame(psi_list_outer, bg=BG_MID, pady=3)
        sel_bar.pack(fill="x")
        tk.Label(sel_bar, text="Node:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 8)).pack(side="left", padx=(8, 2))
        self._psi_node_var = tk.StringVar(value="")
        self._psi_node_cb = ttk.Combobox(
            sel_bar, textvariable=self._psi_node_var,
            width=44, state="readonly", font=("Segoe UI", 8),
        )
        self._psi_node_cb.pack(side="left", padx=2, fill="x", expand=True)
        self._psi_node_cb.bind("<<ComboboxSelected>>",
                               self._on_psi_node_select)

        self._psi_list_panel = PSIListPanel(psi_list_outer)
        self._psi_list_panel.pack(fill="both", expand=True)

    # ── Data load ────────────────────────────────────────────────────

    def load(self, mgr: ScenarioManager) -> None:
        if not HAS_NX:
            return
        self._mgr = mgr
        scenarios = mgr.scenarios()
        self._scen_cb["values"] = scenarios
        if scenarios:
            self._scenario_var.set(scenarios[0])
        if getattr(self, "_hammock_mode", False):
            # Hammock mode: Planning Engine drew the tree — redraw to keep it
            self._redraw_hammock()
        else:
            self._build_graph()
            # Auto-select first Region node
            region_nodes = [k for k in self._node_map if k.startswith("Region:")]
            if region_nodes:
                self._select_node(region_nodes[0])

    # ── Graph construction ───────────────────────────────────────────

    def _build_graph(self):
        df       = self._mgr.combined()
        regions  = sorted(df[Cols.REGION].unique().tolist())
        skus     = sorted(df[Cols.SKU_ID].unique().tolist())

        G = nx.DiGraph()
        G_PROC   = "Global\nProcurement"
        MOTHER   = "Mother\nPlant"
        G_MKT    = "Global\nMarketing"

        # Fixed nodes
        G.add_node(G_PROC,  x=0, y=0,   kind="global",  side="inbound")
        G.add_node(MOTHER,  x=2, y=0,   kind="mother",  side="center")
        G.add_node(G_MKT,   x=4, y=0,   kind="global",  side="outbound")

        # InBound: one node per SKU
        n_s = len(skus)
        for i, sku in enumerate(skus):
            y = (i - (n_s - 1) / 2) * 1.6
            nid = f"SKU:{sku}"
            G.add_node(nid, x=1, y=y, kind="sku", side="inbound")
            G.add_edge(G_PROC, nid)
            G.add_edge(nid, MOTHER)

        # OutBound: one node per Region
        n_r = len(regions)
        for j, reg in enumerate(regions):
            y = (j - (n_r - 1) / 2) * 1.8
            nid = f"Region:{reg}"
            G.add_node(nid, x=3, y=y, kind="region", side="outbound")
            G.add_edge(MOTHER, nid)
            G.add_edge(nid, G_MKT)

        self._G      = G
        self._MOTHER = MOTHER
        self._pos    = {n: (G.nodes[n]["x"], G.nodes[n]["y"]) for n in G.nodes}

        # node_map: clickable nodes → filter
        self._node_map = {}
        for sku in skus:
            self._node_map[f"SKU:{sku}"]      = {"sku": sku,  "region": None}
        for reg in regions:
            self._node_map[f"Region:{reg}"]   = {"sku": None, "region": reg}
        self._node_map[MOTHER]                = {"sku": None, "region": None}

        self._draw_graph()

    # ── Network drawing ──────────────────────────────────────────────

    def _draw_graph(self, highlight: str = ""):
        if not hasattr(self, "_G"):
            return
        G = self._G

        self._net_fig.clf()
        ax = self._net_fig.add_subplot(111)
        ax.set_facecolor(BG_DARK)
        self._net_fig.patch.set_facecolor(BG_DARK)
        ax.axis("off")

        pos = self._pos

        node_colors, node_sizes = [], []
        for node in G.nodes:
            kind  = G.nodes[node].get("kind", "sku")
            is_hl = (node == highlight)
            node_colors.append(self._HIGHLIGHT if is_hl
                               else self._NCOLOUR.get(kind, "#607D8B"))
            node_sizes.append(2400 if is_hl else 1400)

        # Edges
        nx.draw_networkx_edges(G, pos, ax=ax,
                               edge_color="#546E7A",
                               arrows=True, arrowsize=14,
                               arrowstyle="-|>", width=1.5,
                               alpha=0.75,
                               connectionstyle="arc3,rad=0.08")
        # Nodes
        nx.draw_networkx_nodes(G, pos, ax=ax,
                               node_color=node_colors,
                               node_size=node_sizes,
                               alpha=0.92)
        # Labels
        labels = {}
        for node in G.nodes:
            if node.startswith("SKU:"):
                labels[node] = node[4:]
            elif node.startswith("Region:"):
                labels[node] = node[7:]
            else:
                labels[node] = node
        nx.draw_networkx_labels(G, pos, labels=labels, ax=ax,
                                font_color=FG_WHITE,
                                font_size=8, font_weight="bold")

        # InBound / OutBound zone labels
        ax.text(1, ax.get_ylim()[1] * 0.92 if ax.get_ylim()[1] != 0 else 3,
                "← InBound (Supply)",
                color="#4CAF50", fontsize=8, ha="center", style="italic")
        ax.text(3, ax.get_ylim()[1] * 0.92 if ax.get_ylim()[1] != 0 else 3,
                "OutBound (Demand) →",
                color="#2196F3", fontsize=8, ha="center", style="italic")

        # Legend
        from matplotlib.patches import Patch
        legend_elems = [
            Patch(facecolor=self._NCOLOUR["global"], label="Global HQ"),
            Patch(facecolor=self._NCOLOUR["mother"], label="Mother Plant"),
            Patch(facecolor=self._NCOLOUR["sku"],    label="SKU / Prod  [InBound]"),
            Patch(facecolor=self._NCOLOUR["region"], label="Region  [OutBound]"),
            Patch(facecolor=self._HIGHLIGHT,         label="Selected"),
        ]
        ax.legend(handles=legend_elems, loc="lower center",
                  facecolor=BG_MID, labelcolor=FG_WHITE,
                  fontsize=7, framealpha=0.85,
                  ncol=2)

        ax.set_title("SC Network  –  Hammock Model",
                     color=FG_WHITE, fontsize=9, pad=6)

        self._net_canvas.draw()

    # ── Node click ────────────────────────────────────────────────────

    def _on_node_click(self, event):
        if event.inaxes is None:
            return
        cx, cy = event.xdata, event.ydata
        if cx is None or cy is None:
            return

        # Choose position dict: hammock mode or simulation mode
        if getattr(self, "_hammock_mode", False) and hasattr(self, "_pos_hammock"):
            pos_dict = self._pos_hammock
        elif self._pos:
            pos_dict = self._pos
        else:
            return

        best, best_d = None, float("inf")
        for node, (nx_x, nx_y) in pos_dict.items():
            d = ((cx - nx_x) ** 2 + (cy - nx_y) ** 2) ** 0.5
            if d < best_d:
                best_d, best = d, node

        if best_d < 0.6:
            if getattr(self, "_hammock_mode", False):
                self._select_hammock_node(best)
            elif best in self._node_map:
                self._select_node(best)

    def _select_hammock_node(self, node_id: str):
        """Handle click on a hammock-mode node."""
        self._selected_node = node_id
        node_obj = getattr(self, "_node_map_hammock", {}).get(node_id)
        disp = node_obj.node_name if node_obj else node_id
        self._node_lbl_var.set(f"Selected: {disp}")
        self._draw_hammock(highlight=node_id)
        # Auto-select in PSI List
        if node_obj and hasattr(self, "_psi_node_cb"):
            self._psi_node_var.set(node_obj.node_id)
            self._on_psi_node_select(None)
        scen = self._scenario_var.get()
        # Draw PSI directly from psi4supply when plan node is available
        if node_obj:
            self._draw_psi_from_plan_node(node_obj, scen)
        elif self._mgr:
            flt = {}
            self._draw_psi(flt, scen)
        # Cost/Revenue chart: compute per-node from psi4supply × price
        if node_obj:
            self._draw_cost_from_plan_node(node_obj, scen)
        elif self._mgr:
            self._draw_cost({}, scen)

    def _select_node(self, node_label: str):
        self._selected_node = node_label
        disp = node_label.replace("SKU:", "SKU: ").replace("Region:", "Region: ")
        self._node_lbl_var.set(f"Selected: {disp}")
        self._draw_graph(highlight=node_label)
        self._refresh_right()
        self._try_update_psi_list(node_label)   # Step 9

    # ── Right panel: PSI + Cost ───────────────────────────────────────

    def _refresh_right(self):
        if self._mgr is None or not self._selected_node:
            return
        flt  = self._node_map.get(self._selected_node, {})
        scen = self._scenario_var.get()
        self._draw_psi(flt, scen)
        self._draw_cost(flt, scen)

    def _filter_sim(self, flt: dict, scen: str) -> pd.DataFrame:
        df = self._mgr.combined()
        df = df[df[Cols.SCENARIO] == scen]
        if flt.get("sku"):
            df = df[df[Cols.SKU_ID] == flt["sku"]]
        if flt.get("region"):
            df = df[df[Cols.REGION] == flt["region"]]
        return df

    def _ax_dark(self, ax, title: str):
        ax.set_facecolor(BG_MID)
        ax.set_title(title, color=FG_WHITE, fontsize=9, pad=6)
        ax.tick_params(colors=FG_WHITE, labelsize=6)
        ax.set_ylabel("", color=FG_ACC, fontsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(BG_LIGHT)

    def _draw_psi(self, flt: dict, scen: str):
        self._psi_fig.clf()
        ax = self._psi_fig.add_subplot(111)
        ax.set_facecolor(BG_MID)
        self._psi_fig.patch.set_facecolor(BG_DARK)

        df = self._filter_sim(flt, scen)
        if df.empty:
            ax.text(0.5, 0.5, "No data for selection",
                    color=FG_WHITE, ha="center", va="center",
                    transform=ax.transAxes)
            self._psi_canvas.draw()
            return

        wk = (df.groupby(Cols.WEEK)
              .agg(receipt=(Cols.SUPPLY_RECEIPT,   "sum"),
                   sales  =(Cols.DEMAND_FULFILLED, "sum"),
                   inv    =(Cols.CLOSING_INV,      "sum"))
              .reset_index())

        weeks = wk[Cols.WEEK].tolist()
        x = list(range(len(weeks)))
        w = 0.32

        ax.bar([xi - w / 2 for xi in x], wk["receipt"], width=w,
               label="P: Supply Receipt", color="#4CAF50", alpha=0.85)
        ax.bar([xi + w / 2 for xi in x], wk["sales"],   width=w,
               label="S: Sales/Fulfilled", color="#2196F3", alpha=0.85)

        ax2 = ax.twinx()
        ax2.fill_between(x, wk["inv"], alpha=0.18, color="#FF9800")
        ax2.plot(x, wk["inv"], color="#FF9800", linewidth=1.5,
                 marker="o", markersize=3, label="I: Inventory")
        # request_fix_b2_psi_chart_axis.md: pin the right axis (inventory)
        # zero-line to the same height as the left axis (P/S) zero-line.
        # Inventory is never negative, so the bottom is always 0; the top
        # is left to matplotlib's autoscale (confirmed not to collapse to
        # 0 even when inventory is all-zero for every week).
        ax2.set_ylim(bottom=0)
        ax2.set_ylabel("Inventory", color="#FF9800", fontsize=7)
        ax2.tick_params(colors=FG_WHITE, labelsize=6)
        ax2.set_facecolor(BG_MID)

        _t_idx, _t_lbl = _445_ticks(weeks)
        if _t_idx:
            ax.set_xticks(_t_idx)
            ax.set_xticklabels(_t_lbl, rotation=0, ha="center", fontsize=6)
        else:
            ax.set_xticks(x)
            ax.set_xticklabels(weeks, rotation=45, ha="right", fontsize=5)
        ax.set_ylabel("Units", color=FG_ACC, fontsize=7)
        ax.tick_params(colors=FG_WHITE, labelsize=6)
        for spine in ax.spines.values():
            spine.set_edgecolor(BG_LIGHT)

        node_d = self._selected_node.replace("SKU:", "").replace("Region:", "")
        ax.set_title(f"PSI  ─  {node_d}  [{scen}]", color=FG_WHITE, fontsize=9, pad=6)

        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2,
                  facecolor=BG_LIGHT, labelcolor=FG_WHITE,
                  fontsize=7, loc="upper right")

        self._psi_canvas.draw()

    def _draw_psi_from_plan_node(self, node_obj, scen: str):
        """
        Draw PSI chart directly from node_obj.psi4supply (lot-level data).
        Shows P (Supply Receipt), S (Sales/Fulfilled), CO (Carry-Over),
        and I (Inventory) for the selected PlanNode.
        """
        from wom.model.plan_node import S as S_, CO as CO_, I as I_, P as P_

        self._psi_fig.clf()
        ax = self._psi_fig.add_subplot(111)
        ax.set_facecolor(BG_MID)
        self._psi_fig.patch.set_facecolor(BG_DARK)

        psi     = node_obj.psi4supply
        n_weeks = len(psi)
        if n_weeks == 0:
            ax.text(0.5, 0.5, "No PSI data", color=FG_WHITE,
                    ha="center", va="center", transform=ax.transAxes)
            self._psi_canvas.draw()
            return

        week_labels = node_obj.week_labels or [str(w) for w in range(n_weeks)]

        p_vals  = [len(psi[w][P_])  for w in range(n_weeks)]
        s_vals  = [len(psi[w][S_])  for w in range(n_weeks)]
        co_vals = [len(psi[w][CO_]) for w in range(n_weeks)]
        i_vals  = [len(psi[w][I_])  for w in range(n_weeks)]

        x = list(range(n_weeks))
        w = 0.28

        ax.bar([xi - w     for xi in x], p_vals,  width=w, label="P: Supply Receipt",  color="#4CAF50", alpha=0.85)
        ax.bar([xi         for xi in x], s_vals,  width=w, label="S: Sales/Fulfilled", color="#2196F3", alpha=0.85)
        if any(v > 0 for v in co_vals):
            ax.bar([xi + w for xi in x], co_vals, width=w, label="CO: Carry-Over",     color="#F44336", alpha=0.85)

        ax2 = ax.twinx()
        ax2.fill_between(x, i_vals, alpha=0.18, color="#FF9800")
        ax2.plot(x, i_vals, color="#FF9800", linewidth=1.5,
                 marker="o", markersize=2, label="I: Inventory")
        # request_fix_b2_psi_chart_axis.md: pin the right axis (inventory)
        # zero-line to the same height as the left axis (P/S/CO) zero-line.
        # Inventory is never negative, so the bottom is always 0; the top
        # is left to matplotlib's autoscale (confirmed not to collapse to
        # 0 even when inventory is all-zero for every week).
        ax2.set_ylim(bottom=0)
        ax2.set_ylabel("Inventory", color="#FF9800", fontsize=7)
        ax2.tick_params(colors=FG_WHITE, labelsize=6)
        ax2.set_facecolor(BG_MID)

        _t_idx, _t_lbl = _445_ticks(week_labels)
        if _t_idx:
            ax.set_xticks(_t_idx)
            ax.set_xticklabels(_t_lbl, rotation=0, ha="center", fontsize=6)
        else:
            ax.set_xticks(x)
            ax.set_xticklabels(week_labels, rotation=45, ha="right", fontsize=5)
        ax.set_ylabel("Units", color=FG_ACC, fontsize=7)
        ax.tick_params(colors=FG_WHITE, labelsize=6)
        for spine in ax.spines.values():
            spine.set_edgecolor(BG_LIGHT)

        ax.set_title(f"PSI  ─  {node_obj.node_id}  [{scen}]",
                     color=FG_WHITE, fontsize=9, pad=6)

        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2,
                  facecolor=BG_LIGHT, labelcolor=FG_WHITE,
                  fontsize=7, loc="upper right")

        self._psi_canvas.draw()

    def _draw_cost_from_plan_node(self, node_obj, scen: str):
        """
        Cost/Revenue chart from psi4supply S counts x per-node lot price.
        Revenue      = len(psi4supply[w][S]) x selling_price_per_lot
        COGS         = len(psi4supply[w][S]) x unit_cost_per_lot
        Gross Profit = Revenue - COGS

        Price lookup order:
          1. node_cost_master.csv  (product x node_name, per-node price chain)
          2. sku_master.csv        (product x region, leaf_out only fallback)
        """
        from wom.model.plan_node import S as S_
        import pandas as _pd
        import os as _os

        self._cost_fig.clf()
        ax = self._cost_fig.add_subplot(111)
        ax.set_facecolor(BG_MID)
        self._cost_fig.patch.set_facecolor(BG_DARK)

        psi     = node_obj.psi4supply
        n_weeks = len(psi)

        if n_weeks == 0:
            ax.text(0.5, 0.5, "No PSI data", color=FG_WHITE,
                    ha="center", va="center", transform=ax.transAxes)
            self._cost_canvas.draw()
            return

        # ── derive model folder (multiple fallbacks) ─────────────────
        import glob as _glob
        model_dir = getattr(self, "_model_dir", "")
        if not model_dir and hasattr(self, "_f_sc_tree"):
            _scp = self._f_sc_tree.get()
            model_dir = _os.path.dirname(_scp) if _scp else ""
        if not model_dir:
            # Fallback: glob search in data/sample subdirectories
            _cands = _glob.glob(_os.path.join("data", "sample", "*", "node_cost_master.csv"))
            if _cands:
                model_dir = _os.path.dirname(_cands[0])

        selling_price = 0.0
        unit_cost     = 0.0

        # ── 1st: node_cost_master.csv (per-node price chain) ──────────
        if model_dir:
            nc_path = _os.path.join(model_dir, "node_cost_master.csv")
            if _os.path.exists(nc_path):
                nc_cache = getattr(self, "_node_cost_master", None)
                if nc_cache is None:
                    try:
                        nc_cache = _pd.read_csv(nc_path)
                        self._node_cost_master = nc_cache
                    except Exception:
                        nc_cache = _pd.DataFrame()
                if nc_cache is not None and not nc_cache.empty:
                    rows = nc_cache[
                        (nc_cache["sku_id"]    == node_obj.product) &
                        (nc_cache["node_name"] == node_obj.node_name)
                    ]
                    if not rows.empty:
                        selling_price = float(rows["selling_price_per_lot"].iloc[0])
                        unit_cost     = float(rows["unit_cost_per_lot"].iloc[0])

        # ── 2nd: sku_master.csv fallback (leaf_out region-based) ──────
        if selling_price == 0.0 and model_dir:
            sm_path = _os.path.join(model_dir, "sku_master.csv")
            if _os.path.exists(sm_path):
                sm = getattr(self, "_sku_master", None)
                if sm is None:
                    try:
                        sm = _pd.read_csv(sm_path)
                        self._sku_master = sm
                    except Exception:
                        sm = _pd.DataFrame()
                if sm is not None and not sm.empty:
                    rows = sm[sm["sku_id"] == node_obj.product]
                    # Extract region from leaf_out node_id
                    if ":" in node_obj.node_id:
                        parts = node_obj.node_id.split(":")
                        if len(parts) >= 4:
                            reg_rows = rows[rows["region"] == parts[2]]
                            if not reg_rows.empty:
                                rows = reg_rows
                    if not rows.empty:
                        selling_price = float(rows["selling_price"].mean())
                        unit_cost     = float(rows["unit_cost"].mean())

        week_labels = node_obj.week_labels or [str(w) for w in range(n_weeks)]
        s_qty       = [len(psi[w][S_]) for w in range(n_weeks)]

        rev_vals  = [q * selling_price for q in s_qty]
        cogs_vals = [q * unit_cost     for q in s_qty]
        gp_vals   = [r - c for r, c in zip(rev_vals, cogs_vals)]

        x = list(range(n_weeks))
        w = 0.32

        ax.bar([xi - w / 2 for xi in x], cogs_vals, width=w,
               label="COGS",         color="#F44336", alpha=0.80)
        ax.bar([xi + w / 2 for xi in x], gp_vals,   width=w,
               label="Gross Profit", color="#4CAF50", alpha=0.80)
        ax.plot(x, rev_vals, "o-",
                color="#FF9800", linewidth=1.8, markersize=4,
                label="Revenue")

        _t_idx, _t_lbl = _445_ticks(week_labels)
        if _t_idx:
            ax.set_xticks(_t_idx)
            ax.set_xticklabels(_t_lbl, rotation=0, ha="center", fontsize=6)
        else:
            ax.set_xticks(x)
            ax.set_xticklabels(week_labels, rotation=45, ha="right", fontsize=5)
        ax.set_ylabel("JPY", color=FG_ACC, fontsize=7)
        ax.tick_params(colors=FG_WHITE, labelsize=6)
        for spine in ax.spines.values():
            spine.set_edgecolor(BG_LIGHT)

        price_note = ""
        if selling_price == 0:
            price_note = "  (price=0: check sku_master)"
        ax.set_title(
            f"Cost / Revenue  ─  {node_obj.node_id}  [{scen}]{price_note}",
            color=FG_WHITE, fontsize=9, pad=6,
        )
        ax.legend(facecolor=BG_LIGHT, labelcolor=FG_WHITE, fontsize=7)
        self._cost_canvas.draw()

    def _draw_cost(self, flt: dict, scen: str):
        self._cost_fig.clf()
        ax = self._cost_fig.add_subplot(111)
        ax.set_facecolor(BG_MID)
        self._cost_fig.patch.set_facecolor(BG_DARK)

        if self._mgr.weekly_money is None:
            ax.text(0.5, 0.5, "Money PSI not available",
                    color=FG_WHITE, ha="center", va="center",
                    transform=ax.transAxes)
            self._cost_canvas.draw()
            return

        wm = self._mgr.weekly_money
        df = wm[wm[Cols.SCENARIO] == scen].copy()
        if flt.get("sku"):
            df = df[df[Cols.SKU_ID] == flt["sku"]]
        if flt.get("region"):
            df = df[df[Cols.REGION] == flt["region"]]

        if df.empty:
            ax.text(0.5, 0.5, "No data for selection",
                    color=FG_WHITE, ha="center", va="center",
                    transform=ax.transAxes)
            self._cost_canvas.draw()
            return

        wk = (df.groupby(Cols.WEEK)
              .agg(revenue     =(Cols.REVENUE,      "sum"),
                   cogs        =(Cols.COGS,         "sum"),
                   gross_profit=(Cols.GROSS_PROFIT, "sum"))
              .reset_index())

        weeks = wk[Cols.WEEK].tolist()
        x = list(range(len(weeks)))
        w = 0.32

        ax.bar([xi - w / 2 for xi in x], wk["cogs"],         width=w,
               label="COGS",         color="#F44336", alpha=0.80)
        ax.bar([xi + w / 2 for xi in x], wk["gross_profit"], width=w,
               label="Gross Profit", color="#4CAF50", alpha=0.80)
        ax.plot(x, wk["revenue"], "o-",
                color="#FF9800", linewidth=1.8, markersize=4,
                label="Revenue")

        _t_idx, _t_lbl = _445_ticks(weeks)
        if _t_idx:
            ax.set_xticks(_t_idx)
            ax.set_xticklabels(_t_lbl, rotation=0, ha="center", fontsize=5)
        else:
            ax.set_xticks(x)
            ax.set_xticklabels(weeks, rotation=45, ha="right", fontsize=5)
        ax.set_ylabel("USD", color=FG_ACC, fontsize=7)
        ax.tick_params(colors=FG_WHITE, labelsize=6)
        for spine in ax.spines.values():
            spine.set_edgecolor(BG_LIGHT)

        node_d = self._selected_node.replace("SKU:", "").replace("Region:", "")
        ax.set_title(f"Cost / Revenue  ─  {node_d}  [{scen}]",
                     color=FG_WHITE, fontsize=9, pad=6)
        ax.legend(facecolor=BG_LIGHT, labelcolor=FG_WHITE, fontsize=7)

        self._cost_canvas.draw()
    # ── Step 9: Planning tree (lot-based PSI) ────────────────────────

    # ── Event Flow Tracing ───────────────────────────────────────────

    def set_timeline(self, timeline) -> None:
        """Called after planning completes with the built EventTimeline."""
        from wom.engine.event_timeline import max_activity
        self._timeline      = timeline
        self._anim_week     = 0
        self._anim_max_act  = max_activity(timeline)
        self._anim_running  = False
        if hasattr(self, "_anim_play_btn"):
            self._anim_play_btn.config(state="normal")
            self._anim_stop_btn.config(state="normal")
        n = len(timeline)
        self._week_lbl_var.set(
            f"Week 0/{n}  ←  press ▶ to animate")

    def _anim_play(self):
        if not self._timeline:
            return
        self._anim_running = True
        self._anim_play_btn.config(state="disabled")
        self._anim_pause_btn.config(state="normal")
        self._anim_stop_btn.config(state="normal")
        self._anim_tick()

    def _anim_pause(self):
        self._anim_running = False
        self._anim_play_btn.config(state="normal")
        self._anim_pause_btn.config(state="disabled")

    def _anim_stop(self):
        self._anim_running = False
        self._anim_week    = 0
        if self._anim_after_id:
            self.after_cancel(self._anim_after_id)
            self._anim_after_id = None
        self._anim_play_btn.config(state="normal")
        self._anim_pause_btn.config(state="disabled")
        # Redraw static graph
        self._draw_graph(highlight=self._selected_node)
        n = len(self._timeline) if self._timeline else 0
        self._week_lbl_var.set(f"Week 0/{n}  ←  press ▶ to animate")

    def _on_speed_change(self, _event=None):
        speed_map = {"0.5×": 2000, "1×": 1000, "2×": 500, "4×": 250}
        self._anim_speed_ms = speed_map.get(self._speed_var.get(), 1000)

    def _anim_tick(self):
        if not self._anim_running or not self._timeline:
            return
        n = len(self._timeline)
        if self._anim_week >= n:
            # Loop back to start
            self._anim_week = 0
        snap = self._timeline[self._anim_week]
        self._draw_graph_animated(snap)
        self._week_lbl_var.set(
            f"Week {self._anim_week + 1}/{n}  |  {snap.week_label}")
        self._anim_week += 1
        self._anim_after_id = self.after(self._anim_speed_ms, self._anim_tick)

    def _draw_graph_animated(self, snap):
        """Redraw the network graph overlaid with one week's activity snapshot."""
        if not hasattr(self, "_G"):
            return
        from wom.engine.event_timeline import max_activity

        G   = self._G
        pos = self._pos
        max_act = self._anim_max_act or 1

        self._net_fig.clf()
        ax = self._net_fig.add_subplot(111)
        ax.set_facecolor(BG_DARK)
        self._net_fig.patch.set_facecolor(BG_DARK)
        ax.axis("off")

        # ── Node colours and sizes ────────────────────────────────────
        node_colors, node_sizes = [], []
        for node in G.nodes:
            kind = G.nodes[node].get("kind", "sku")
            na   = snap.node_activity.get(node)
            if na and na.flow > 0:
                # Active: brighten + scale size
                scale = 1.0 + 2.0 * (na.flow / max_act)
                node_colors.append("#FFEB3B")  # bright yellow when active
                node_sizes.append(int(1400 * min(scale, 3.0)))
            else:
                # Inactive: dim the base colour
                base = self._NCOLOUR.get(kind, "#607D8B")
                node_colors.append(base)
                node_sizes.append(1000)

        # ── Edge colours and widths from edge_flows ───────────────────
        # Build lookup: (src, dst) → EdgeFlow
        flow_map: dict = {}
        for ef in snap.edge_flows:
            key = (ef.src, ef.dst)
            flow_map[key] = flow_map.get(key, 0) + ef.lot_count

        max_flow = snap.max_flow or 1
        edge_colors, edge_widths = [], []
        for u, v in G.edges():
            cnt = flow_map.get((u, v), 0)
            if cnt > 0:
                # Supply: green, Demand: blue-ish
                # Determine direction from graph topology (inbound nodes left of mother)
                u_x = G.nodes[u].get("x", 0)
                v_x = G.nodes[v].get("x", 0)
                if v_x >= u_x:
                    edge_colors.append("#66BB6A")  # supply green
                else:
                    edge_colors.append("#42A5F5")  # demand blue
                edge_widths.append(1.5 + 6.0 * (cnt / max_flow))
            else:
                edge_colors.append("#37474F")  # dim grey
                edge_widths.append(0.8)

        # Draw edges
        edges = list(G.edges())
        for i, (u, v) in enumerate(edges):
            nx.draw_networkx_edges(
                G, pos, edgelist=[(u, v)], ax=ax,
                edge_color=[edge_colors[i]],
                width=edge_widths[i],
                arrows=True, arrowsize=12,
                arrowstyle="-|>", alpha=0.85,
                connectionstyle="arc3,rad=0.08")

        # Draw nodes
        nx.draw_networkx_nodes(G, pos, ax=ax,
                               node_color=node_colors,
                               node_size=node_sizes,
                               alpha=0.93)

        # Labels
        labels = {}
        for node in G.nodes:
            if node.startswith("SKU:"):   labels[node] = node[4:]
            elif node.startswith("Region:"): labels[node] = node[7:]
            else:                            labels[node] = node
        nx.draw_networkx_labels(G, pos, labels=labels, ax=ax,
                                font_color=FG_WHITE,
                                font_size=8, font_weight="bold")

        # Lot-count labels on active edges
        edge_labels = {(u, v): str(flow_map[(u, v)])
                       for u, v in G.edges() if (u, v) in flow_map}
        if edge_labels:
            nx.draw_networkx_edge_labels(
                G, pos, edge_labels=edge_labels, ax=ax,
                font_color="#FFEB3B", font_size=7,
                bbox=dict(boxstyle="round,pad=0.2",
                          fc=BG_MID, ec="none", alpha=0.75))

        # Week label overlay
        ax.set_title(
            f"SC Network  –  {snap.week_label}",
            color=FG_WHITE, fontsize=10, pad=6, fontweight="bold")

        # Inventory bar: show I-count as small text on active nodes
        for node in G.nodes:
            na = snap.node_activity.get(node)
            if na and na.i_count > 0:
                x, y = pos[node]
                ax.text(x, y - 0.28, f"I:{na.i_count}",
                        color="#B0BEC5", fontsize=6, ha="center", va="top")

        # CO warning
        co_nodes = [n for n in G.nodes
                    if snap.node_activity.get(n) and
                    snap.node_activity[n].co_count > 0]
        if co_nodes:
            for cn in co_nodes:
                x, y = pos[cn]
                ax.text(x, y + 0.3, f"CO:{snap.node_activity[cn].co_count}",
                        color="#FF9800", fontsize=6, ha="center", va="bottom",
                        fontweight="bold")

        self._net_canvas.draw()

    def load_planning_tree(self, sc_tree, model_dir: str = "") -> None:
        """
        Load a post-planning SCTree.
        • Populates PSI List node selector
        • Replaces the network graph with E2E hammock layout (Phase B)
        """
        if not hasattr(self, "_psi_list_panel"):
            return   # HAS_NX=False: panel was never built
        self._sc_tree   = sc_tree
        self._model_dir = model_dir   # store for lane_assignment lookup

        # ── Populate PSI List node selector ───────────────────────────
        node_ids = []
        for prod_nm in sc_tree.products:
            for node in sc_tree.iter_all_nodes(prod_nm):
                node_ids.append(node.node_id)
        self._psi_node_cb["values"] = node_ids
        if node_ids:
            self._psi_node_var.set(node_ids[0])
            self._on_psi_node_select(None)

        # ── Switch network view to E2E hammock ────────────────────────
        self._hammock_mode = True
        prods = sc_tree.products
        self._prod_cb["values"] = prods
        if prods:
            self._prod_var.set(prods[0])
        self._redraw_hammock()

    def _redraw_hammock(self):
        """Build and draw the E2E hammock graph for the selected product."""
        if not self._sc_tree or not getattr(self, "_hammock_mode", False):
            return
        prod_nm = self._prod_var.get() or self._sc_tree.products[0]
        try:
            import os as _os
            import pandas as _pd
            from wom.engine.hammock_layout import (
                build_hammock_graph, node_colour, node_size,
                NODE_COLOUR, NODE_SIZE)

            # Load lane_assignment.csv for lane edge overlay
            lane_df = None
            _mdir = getattr(self, "_model_dir", "")
            if _mdir:
                _lane_path = _os.path.join(_mdir, "lane_assignment.csv")
                if _os.path.exists(_lane_path):
                    try:
                        lane_df = _pd.read_csv(_lane_path)
                    except Exception:
                        pass

            G, pos = build_hammock_graph(self._sc_tree, prod_nm,
                                         lane_df=lane_df)
        except Exception as exc:
            print(f"[HammockLayout] build failed: {exc}")
            import traceback; traceback.print_exc()
            return

        self._G_hammock  = G
        self._pos_hammock = pos
        self._prod_selected = prod_nm

        # Build node_map for click handling
        self._node_map_hammock = {}
        for node_id, data in G.nodes(data=True):
            self._node_map_hammock[node_id] = data.get("node_obj")

        self._draw_hammock(highlight="")

    def _draw_hammock(self, highlight: str = ""):
        """Render the hammock graph (replaces _draw_graph in Planning mode).

        Rendering layers (bottom→top):
          1. Topology edges  — thin grey (logic wiring)
          2. SP node         — small, semi-transparent (HQ / invisible hub)
          3. Non-SP nodes    — normal size/colour
          4. Lane edges      — thick coloured arcs (physical logistics)
          5. Labels
        """
        if not hasattr(self, "_G_hammock"):
            return
        from wom.engine.hammock_layout import (
            node_colour, node_size, NODE_COLOUR, LANE_COLOURS, lane_colour_map)
        from matplotlib.patches import Patch, FancyArrow
        from matplotlib.lines import Line2D

        G   = self._G_hammock
        pos = self._pos_hammock

        self._net_fig.clf()
        # Bottom margin for legend placed below axes
        self._net_fig.subplots_adjust(bottom=0.22)
        ax = self._net_fig.add_subplot(111)
        ax.set_facecolor(BG_DARK)
        self._net_fig.patch.set_facecolor(BG_DARK)
        ax.axis("off")

        import networkx as nx

        # ── Separate edges by type ─────────────────────────────────────
        topo_edges = [(u, v) for u, v, d in G.edges(data=True)
                      if d.get("edge_type", "topology") != "lane"]
        lane_edges = [(u, v, d) for u, v, d in G.edges(data=True)
                      if d.get("edge_type") == "lane"]

        # ── Layer 1: topology edges (thin, faint) ─────────────────────
        nx.draw_networkx_edges(G, pos, ax=ax,
                               edgelist=topo_edges,
                               edge_color="#455A64",
                               arrows=True, arrowsize=10,
                               arrowstyle="-|>", width=1.0,
                               alpha=0.45,
                               connectionstyle="arc3,rad=0.05")

        # ── Layer 2 & 3: nodes (SP small/faint, others normal) ────────
        sp_nodes     = [n for n in G.nodes
                        if G.nodes[n].get("node_type") == "supply_point"]
        non_sp_nodes = [n for n in G.nodes
                        if G.nodes[n].get("node_type") != "supply_point"]

        # Split non-SP nodes into "stocker" (buffering_stock_flag=1 /
        # is_decoupling, e.g. FG_WH_*) vs normal nodes. Buffer-holding
        # decoupling nodes render with an inverted-triangle "stocker"
        # marker (classic Industrial Engineering symbol for an inventory
        # buffer), so users can see at a glance where PULL-side CO is
        # absorbed instead of accumulating (2026-07-14 GUI review finding
        # -- addresses the "PUSH/decoupling state isn't visualized" known
        # limitation for buffering_stock_flag=1 nodes; InBound Step 8
        # push_config.csv decoupling nodes are not yet covered here).
        stocker_nodes, normal_nodes = [], []
        for nid in non_sp_nodes:
            nobj = G.nodes[nid].get("node_obj")
            if nobj is not None and getattr(nobj, "is_decoupling", False):
                stocker_nodes.append(nid)
            else:
                normal_nodes.append(nid)

        # Normal nodes (circular marker)
        nc_normal, ns_normal = [], []
        for nid in normal_nodes:
            nt = G.nodes[nid].get("node_type", "virtual")
            hl = (nid == highlight)
            nc_normal.append(node_colour(nt, hl))
            ns_normal.append(node_size(nt, hl))

        if normal_nodes:
            nx.draw_networkx_nodes(G, pos, ax=ax,
                                   nodelist=normal_nodes,
                                   node_color=nc_normal,
                                   node_size=ns_normal,
                                   alpha=0.92)

        # Stocker nodes (inverted-triangle marker = buffering stock)
        nc_stocker, ns_stocker = [], []
        for nid in stocker_nodes:
            nt = G.nodes[nid].get("node_type", "virtual")
            hl = (nid == highlight)
            nc_stocker.append(node_colour(nt, hl))
            ns_stocker.append(node_size(nt, hl))

        if stocker_nodes:
            nx.draw_networkx_nodes(G, pos, ax=ax,
                                   nodelist=stocker_nodes,
                                   node_color=nc_stocker,
                                   node_size=ns_stocker,
                                   node_shape="v",
                                   edgecolors="#FFFFFF", linewidths=1.3,
                                   alpha=0.92)

        # SP node — small + semi-transparent
        if sp_nodes:
            nx.draw_networkx_nodes(G, pos, ax=ax,
                                   nodelist=sp_nodes,
                                   node_color=["#FFEB3B"],
                                   node_size=[500],
                                   alpha=0.30)

        # ── Layer 4: lane edges (thick coloured arcs) ─────────────────
        if lane_edges:
            # Collect unique mom_ids preserving order
            unique_moms = list(dict.fromkeys(
                d.get("mom_id", u) for u, v, d in lane_edges))
            mom_clr = {mid: LANE_COLOURS[i % len(LANE_COLOURS)]
                       for i, mid in enumerate(unique_moms)}

            for u, v, d in lane_edges:
                mid   = d.get("mom_id", u)
                clr   = mom_clr.get(mid, "#FF6F00")
                # rad=0.0 → straight line: arrowhead points exactly at DC node
                nx.draw_networkx_edges(G, pos, ax=ax,
                                       edgelist=[(u, v)],
                                       edge_color=clr,
                                       arrows=True, arrowsize=22,
                                       arrowstyle="-|>", width=4.5,
                                       alpha=0.88,
                                       connectionstyle="arc3,rad=0.0")
        else:
            unique_moms = []
            mom_clr     = {}

        # ── Labels ────────────────────────────────────────────────────
        labels = {nid: G.nodes[nid].get("label", nid) for nid in G.nodes}
        nx.draw_networkx_labels(G, pos, labels=labels, ax=ax,
                                font_color=FG_WHITE,
                                font_size=7, font_weight="bold")

        # ── Zone annotations ──────────────────────────────────────────
        xs    = [x for x, y in pos.values()]
        y_top = max(y for x, y in pos.values()) + 0.8
        if xs:
            ax.text(min(xs) * 0.6, y_top,
                    "← InBound (Supply)",
                    color="#66BB6A", fontsize=8, ha="center", style="italic")
            ax.text(max(xs) * 0.6, y_top,
                    "OutBound (Demand) →",
                    color="#42A5F5", fontsize=8, ha="center", style="italic")

        # ── Legend ────────────────────────────────────────────────────
        legend_elems = [
            Patch(facecolor=NODE_COLOUR["supply_point"], alpha=0.35,
                  label="Supply Point (HQ bridge)"),
            Patch(facecolor=NODE_COLOUR["mom"],   label="MOM  [InBound]"),
            Patch(facecolor=NODE_COLOUR["leaf_in"],  label="Leaf-In  [InBound]"),
            Patch(facecolor=NODE_COLOUR["dad"],   label="DAD  [OutBound]"),
            Patch(facecolor=NODE_COLOUR["leaf_out"], label="Leaf-Out  [OutBound]"),
            Patch(facecolor=NODE_COLOUR["virtual"],  label="Virtual office"),
            Patch(facecolor="#FFFF00",               label="Selected"),
            Line2D([0], [0], marker="v", linestyle="None",
                   markerfacecolor=NODE_COLOUR["dad"], markeredgecolor="#FFFFFF",
                   markersize=9, label="Buffering Stock (decoupling)"),
        ]
        # Lane colour entries (one per MOM)
        for mid, clr in mom_clr.items():
            short = mid.split(":")[-2] if ":" in mid else mid
            legend_elems.append(
                Line2D([0], [0], color=clr, linewidth=3,
                       label=f"Lane: {short}"))

        # Place legend BELOW the axes to avoid overlapping the graph
        ax.legend(handles=legend_elems,
                  loc="upper center",
                  bbox_to_anchor=(0.5, -0.02),
                  bbox_transform=ax.transAxes,
                  facecolor=BG_MID, labelcolor=FG_WHITE,
                  fontsize=6.5, framealpha=0.85, ncol=3)

        prod_nm = getattr(self, "_prod_selected", "")
        ax.set_title(f"SC Network  –  E2E Hammock  [{prod_nm}]",
                     color=FG_WHITE, fontsize=9, pad=6)

        self._net_canvas.draw()

    def _on_psi_node_select(self, event):
        """Called when user picks a node from the PSI List combobox."""
        node_id = self._psi_node_var.get()
        if not self._sc_tree or not node_id:
            return
        for prod_nm in self._sc_tree.products:
            for node in self._sc_tree.iter_all_nodes(prod_nm):
                if node.node_id == node_id:
                    self._psi_list_panel.load_node(node)
                    return

    def _try_update_psi_list(self, node_label: str):
        """
        When a network graph node is clicked, try to auto-select the
        corresponding PlanNode in the PSI List tab.

        Mapping:
          "SKU:{sku}"     → IN:MFG:{sku}          (InBound root / MOM)
          "Region:{reg}"  → first OUT:Sales:{reg}: leaf_out
          "Mother\nPlant" → first MOM node in the tree
        """
        if not hasattr(self, "_psi_list_panel"):
            return
        if self._sc_tree is None:
            return

        sc_tree   = self._sc_tree
        target_id = None

        if node_label.startswith("SKU:"):
            sku       = node_label[4:]
            target_id = f"IN:MFG:{sku}"

        elif node_label.startswith("Region:"):
            region = node_label[7:]
            for prod_nm in sc_tree.products:
                try:
                    ot_root = sc_tree.get_ot_root(prod_nm)
                except Exception:
                    continue
                for node in ot_root.walk_preorder():
                    if f":Sales:{region}:" in node.node_id:
                        target_id = node.node_id
                        break
                if target_id:
                    break

        else:
            # "Mother\nPlant" or other fixed node → pick first IN root
            prods = list(sc_tree.products)
            if prods:
                try:
                    root      = sc_tree.get_in_root(prods[0])
                    target_id = root.node_id
                except Exception:
                    pass

        if not target_id:
            return

        for prod_nm in sc_tree.products:
            for node in sc_tree.iter_all_nodes(prod_nm):
                if node.node_id == target_id:
                    self._psi_node_var.set(target_id)
                    self._psi_list_panel.load_node(node)
                    return



# ──────────────────────────────────────────────────────────────────────
# World Map Panel  (tkintermapview-based SC node visualizer)
# ──────────────────────────────────────────────────────────────────────

# Node type → (marker circle color, marker outside color, label prefix)
_MAP_NODE_STYLE = {
    "procurement":  ("#FF9800", "#E65100", "📦"),
    "mother_plant": ("#9C27B0", "#4A148C", "🏭"),
    "sku_supplier": ("#4CAF50", "#1B5E20", "🔩"),
    "region_dc":    ("#2196F3", "#0D47A1", "🏬"),
    "marketing":    ("#F44336", "#B71C1C", "🌎"),
}

# SC links to draw between node types (src_type → dst_type)
_MAP_LINKS = [
    ("procurement",  "sku_supplier"),   # procurement → each supplier
    ("sku_supplier", "mother_plant"),   # suppliers → mother plant
    ("mother_plant", "region_dc"),      # plant → each DC
    ("region_dc",    "marketing"),      # DCs → marketing HQ
]


class WorldMapPanel(tk.Frame):
    """
    🗺 World Map tab — interactive SC node map using tkintermapview.

    Shows SC nodes as coloured markers on a world map.
    After "Run Planning Engine", overlays lot-flow animation per week.
    """

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._nodes: list = []           # list of dicts from node_master.csv
        self._markers: list = []         # active TkinterMapView marker objects
        self._paths:   list = []         # active TkinterMapView path objects
        self._timeline = None            # EventTimeline (set after planning)
        self._anim_running  = False
        self._anim_week     = 0
        self._anim_speed_ms = 1000
        self._anim_after_id = None
        self._map_widget    = None
        self._sc_tree_path: str = ""     # sc_tree_master.csv path (optional)
        self._sc_edges: list = []        # [{"child":node_id,"parent":node_id,"product":str}, ...]
        self._product_nodes: dict = {}   # product_name -> set(node_id) incl. bridge/dad nodes
        self._build()

    # ── Layout ───────────────────────────────────────────────────────────

    def _build(self):
        try:
            from tkintermapview import TkinterMapView
            HAS_MAP = True
        except ImportError:
            HAS_MAP = False

        if not HAS_MAP:
            tk.Label(self,
                     text="tkintermapview not installed.\nRun:  pip install tkintermapview",
                     bg=BG_DARK, fg="#FF6B6B",
                     font=("Segoe UI", 11)).pack(expand=True)
            return

        # Control bar
        bar = tk.Frame(self, bg=BG_MID, pady=4)
        bar.pack(fill="x", side="top")

        tk.Label(bar, text="Node Master:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))
        self._file_var = tk.StringVar(value="")
        self._file_entry = tk.Entry(bar, textvariable=self._file_var,
                                    width=38, bg=BG_LIGHT, fg=FG_WHITE,
                                    font=("Segoe UI", 8), relief="flat")
        self._file_entry.pack(side="left", padx=2)
        tk.Button(bar, text="Browse…",
                  command=self._browse_node_master,
                  bg=BG_LIGHT, fg=FG_WHITE, font=("Segoe UI", 8),
                  relief="flat").pack(side="left", padx=2)
        tk.Button(bar, text="⟳ Reload",
                  command=self._reload,
                  bg="#1565C0", fg="white", font=("Segoe UI", 8),
                  relief="flat").pack(side="left", padx=(6, 2))

        # SKU/product filter — narrows markers + SC-tree edges to one product
        # so multi-SKU / multi-region models don't turn into an unreadable
        # tangle of overlapping pins and lines.
        tk.Label(bar, text="  SKU:", bg=BG_MID, fg=FG_WHITE,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        self._map_sku_var = tk.StringVar(value="All")
        self._map_sku_cb = ttk.Combobox(bar, textvariable=self._map_sku_var,
                                         values=["All"], width=16, state="readonly",
                                         font=("Segoe UI", 8))
        self._map_sku_cb.pack(side="left", padx=2)
        self._map_sku_cb.bind("<<ComboboxSelected>>", lambda _: self._on_map_sku_change())

        # Animation controls (enabled after planning)
        tk.Label(bar, text="  |", bg=BG_MID, fg="#546E7A").pack(side="left")
        self._map_play_btn = tk.Button(
            bar, text="▶", width=3, command=self._anim_play,
            bg="#1B5E20", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", state="disabled")
        self._map_play_btn.pack(side="left", padx=(6, 2))
        self._map_pause_btn = tk.Button(
            bar, text="⏸", width=3, command=self._anim_pause,
            bg=BG_LIGHT, fg=FG_WHITE, font=("Segoe UI", 9),
            relief="flat", state="disabled")
        self._map_pause_btn.pack(side="left", padx=2)
        self._map_stop_btn = tk.Button(
            bar, text="⏹", width=3, command=self._anim_stop,
            bg=BG_LIGHT, fg=FG_WHITE, font=("Segoe UI", 9),
            relief="flat", state="disabled")
        self._map_stop_btn.pack(side="left", padx=2)

        self._map_week_var = tk.StringVar(value="Run Planning Engine to enable animation")
        tk.Label(bar, textvariable=self._map_week_var,
                 bg=BG_MID, fg=FG_ACC,
                 font=("Segoe UI", 8, "italic")).pack(side="left", padx=10)

        # Main split: map (left) + info panel (right)
        paned = tk.PanedWindow(self, orient="horizontal", bg=BG_DARK,
                               sashwidth=5, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # Map widget
        map_frame = tk.Frame(paned, bg=BG_DARK)
        paned.add(map_frame, minsize=820)

        from tkintermapview import TkinterMapView
        # SQLite tile cache: <project>/data/worldmap_cache.db
        # Pre-populate offline: python tools/download_worldmap_tiles.py
        # If DB exists → served locally (works offline).
        # If DB missing → created automatically; tiles cache on first online use.
        _gui_dir  = os.path.dirname(os.path.abspath(__file__))   # wom/gui/
        _wom_dir  = os.path.dirname(_gui_dir)                     # wom/
        _proj_dir = os.path.dirname(_wom_dir)                     # project root
        _tile_db  = os.path.join(_proj_dir, "data", "worldmap_cache.db")
        self._map_widget = TkinterMapView(
            map_frame, width=700, height=520,
            corner_radius=0,
            database_path=_tile_db)
        self._map_widget.pack(fill="both", expand=True)
        # Use CARTO tiles — not blocked by usage policy unlike OSM default.
        # DB server key must match this URL exactly for offline cache lookup.
        # download_worldmap_tiles.py uses the same URL for pre-caching.
        _CARTO = "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
        try:
            self._map_widget.set_tile_server(_CARTO, max_zoom=19)
        except Exception:
            pass
        # Center on world view
        self._map_widget.set_position(20.0, 10.0)
        self._map_widget.set_zoom(2)

        # Info panel (right)
        info_frame = tk.Frame(paned, bg=BG_DARK)
        paned.add(info_frame, minsize=180)

        tk.Label(info_frame, text="Node Info",
                 bg=BG_DARK, fg=FG_ACC,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(8, 2))

        self._info_text = tk.Text(
            info_frame, bg=BG_MID, fg=FG_WHITE,
            font=("Segoe UI", 9), relief="flat",
            wrap="word", state="disabled", width=28)
        self._info_text.pack(fill="both", expand=True, padx=6, pady=4)

        # Legend
        leg = tk.LabelFrame(info_frame, text=" Legend ",
                            bg=BG_DARK, fg=FG_ACC,
                            font=("Segoe UI", 8, "bold"),
                            relief="groove", bd=1)
        leg.pack(fill="x", padx=6, pady=4)
        for ntype, (cc, co, icon) in _MAP_NODE_STYLE.items():
            row = tk.Frame(leg, bg=BG_DARK)
            row.pack(fill="x", padx=4, pady=1)
            tk.Label(row, text="●", fg=cc, bg=BG_DARK,
                     font=("Segoe UI", 10)).pack(side="left")
            tk.Label(row, text=f"{icon} {ntype.replace('_', ' ').title()}",
                     bg=BG_DARK, fg=FG_WHITE,
                     font=("Segoe UI", 8)).pack(side="left", padx=4)

    # ── File operations ───────────────────────────────────────────────────

    def _browse_node_master(self):
        path = filedialog.askopenfilename(
            title="Select node_master.csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if path:
            self._file_var.set(path)
            self._reload()

    def load_default(self, csv_path: str, sc_tree_path: str = "") -> None:
        """Load a node master CSV path without user interaction.

        sc_tree_path (optional): sc_tree_master.csv from the same model
        folder — used to derive real parent/child edges and the SKU filter
        list. Without it, the panel falls back to the old node_type
        all-pairs heuristic (_MAP_LINKS) and shows no SKU filter options.
        """
        self._file_var.set(csv_path)
        self._sc_tree_path = sc_tree_path or ""
        self._reload()

    def _reload(self):
        path = self._file_var.get()
        if not path or not os.path.exists(path):
            return
        try:
            df = pd.read_csv(path)
            self._nodes = df.to_dict("records")
            self._load_sc_tree_edges()
            self._draw_nodes()
        except Exception as exc:
            messagebox.showerror("World Map", f"Failed to load {path}:\n{exc}")

    def _load_sc_tree_edges(self):
        """
        Parse sc_tree_master.csv (if available) into real parent/child edges
        and a product_name -> {node_id} map, so the map can (a) draw only
        actually-linked nodes instead of a node_type all-pairs guess, and
        (b) offer a SKU/product filter dropdown.

        Note: sc_tree_master.csv's "node_name" column holds the same short
        identifier as node_master.csv's "node_id" column (node_master's own
        "node_name" is a separate, human-readable description) — matching
        must be done on that id, not on node_master's node_name.
        """
        self._sc_edges = []
        self._product_nodes = {}
        path = self._sc_tree_path
        if not path or not os.path.exists(path):
            self._map_sku_cb["values"] = ["All"]
            self._map_sku_var.set("All")
            return
        try:
            sc_df = pd.read_csv(path)
        except Exception as exc:
            print(f"[WorldMap] sc_tree_master load failed: {exc}")
            self._map_sku_cb["values"] = ["All"]
            self._map_sku_var.set("All")
            return

        # mom_root(s) / supply_point_root per product, for the synthetic
        # InBound<->OutBound bridge edge (see note below). A product can
        # have more than one mom root (Multi-MOM models, e.g. iphone-2027-2029).
        mom_roots: dict = {}   # product -> [node_id, ...]
        sp_root: dict = {}     # product -> node_id

        for _, row in sc_df.iterrows():
            node_id  = str(row.get("node_name", "")).strip()
            parent   = str(row.get("parent_node", "") or "").strip()
            product  = str(row.get("product_name", "")).strip()
            ntype    = str(row.get("node_type", "")).strip()
            if not node_id or not product:
                continue
            self._product_nodes.setdefault(product, set()).add(node_id)
            if parent and parent.lower() != "nan":
                self._product_nodes[product].add(parent)
                self._sc_edges.append(
                    {"child": node_id, "parent": parent, "product": product})
            elif ntype == "mom":
                mom_roots.setdefault(product, []).append(node_id)
            elif ntype == "supply_point":
                sp_root[product] = node_id

        # WOM's InBound (mom root) and OutBound (supply_point root) trees
        # are two independent roots in sc_tree_master.csv — the engine
        # bridges them at runtime by product_name match, not via a
        # parent_node cell (see CLAUDE.md's SCTree diagram: "Bridge").
        # Without this synthetic edge, the map shows the MOM/leaf_in side
        # (e.g. an overseas factory) as visually disconnected from its own
        # DC/leaf_out side, even though they're the same product's one lane.
        for product, mom_ids in mom_roots.items():
            sp_id = sp_root.get(product)
            if not sp_id:
                continue
            for mom_id in mom_ids:
                self._sc_edges.append(
                    {"child": sp_id, "parent": mom_id, "product": product})

        products = sorted(self._product_nodes.keys())
        values = ["All"] + products
        self._map_sku_cb["values"] = values
        if self._map_sku_var.get() not in values:
            self._map_sku_var.set("All")

    def _current_map_sku(self):
        v = self._map_sku_var.get() if hasattr(self, "_map_sku_var") else "All"
        return None if (not v or v == "All") else v

    def _on_map_sku_change(self):
        self._draw_nodes()

    # ── Map drawing ───────────────────────────────────────────────────────

    def _draw_nodes(self):
        if self._map_widget is None:
            return
        # Clear existing
        for m in self._markers:
            try: m.delete()
            except Exception: pass
        for p in self._paths:
            try: p.delete()
            except Exception: pass
        self._markers.clear()
        self._paths.clear()

        # ── SKU/product filter ────────────────────────────────────────────
        sku = self._current_map_sku()
        allowed_ids = self._product_nodes.get(sku) if sku else None
        if allowed_ids is not None:
            nodes_to_draw = [n for n in self._nodes
                             if str(n.get("node_id", "")) in allowed_ids]
        else:
            nodes_to_draw = list(self._nodes)

        # Lat/lon lookup by node_id (used for sc_tree-edge endpoints,
        # unfiltered so edges always resolve even if only one endpoint
        # happens to be shared infrastructure)
        pos_by_id = {}
        for n in self._nodes:
            try:
                pos_by_id[str(n.get("node_id", ""))] = (float(n["lat"]), float(n["lon"]))
            except (TypeError, ValueError, KeyError):
                pass

        # ── Draw SC link paths first (beneath markers) ───────────────────
        link_color = "#546E7A"
        if self._sc_edges:
            # Real parent/child edges from sc_tree_master.csv, optionally
            # narrowed to the selected product — no more all-pairs guessing.
            for edge in self._sc_edges:
                if sku and edge["product"] != sku:
                    continue
                p1 = pos_by_id.get(edge["child"])
                p2 = pos_by_id.get(edge["parent"])
                if p1 is None or p2 is None:
                    continue
                try:
                    path = self._map_widget.set_path(
                        [p1, p2], color=link_color, width=2)
                    self._paths.append(path)
                except Exception:
                    pass
        else:
            # Fallback: no sc_tree_master.csv available for this model —
            # use the old node_type all-pairs heuristic on the filtered set.
            by_type: dict = {}
            for node in nodes_to_draw:
                ntype = str(node.get("node_type", ""))
                by_type.setdefault(ntype, []).append(node)
            for src_type, dst_type in _MAP_LINKS:
                for src in by_type.get(src_type, []):
                    for dst in by_type.get(dst_type, []):
                        try:
                            path = self._map_widget.set_path(
                                [(float(src["lat"]), float(src["lon"])),
                                 (float(dst["lat"]), float(dst["lon"]))],
                                color=link_color, width=2)
                            self._paths.append(path)
                        except Exception:
                            pass

        # Draw node markers (filtered set only)
        #
        # 2026-07-14 GUI review finding: removing the label entirely (first
        # attempt) made nodes impossible to identify without clicking every
        # pin -- too aggressive. Reverted per user feedback: show the bare
        # node_name only (no icon prefix, no description) as a short,
        # single-line label -- this keeps most overlap cases readable while
        # still trimming label width versus the original "icon + name"
        # text. Full detail (type/lat/lon/SKU/region/description) remains
        # a click away via _on_marker_click / the Node Info panel.
        for node in nodes_to_draw:
            ntype  = str(node.get("node_type", ""))
            style  = _MAP_NODE_STYLE.get(ntype, ("#607D8B", "#455A64", "📍"))
            cc, co, icon = style
            label  = str(node.get("node_name", node.get("node_id", "")))
            try:
                marker = self._map_widget.set_marker(
                    float(node["lat"]), float(node["lon"]),
                    text=label,
                    marker_color_circle=cc,
                    marker_color_outside=co,
                    command=lambda m, n=node: self._on_marker_click(m, n),
                    text_color="#222222",
                    font=("Segoe UI", 8, "bold"))
                self._markers.append(marker)
            except Exception:
                pass

        # ── Auto-fit map view to node bounding box (filtered set) ─────────
        self._fit_nodes_cache = nodes_to_draw
        self.after(200, self._fit_to_nodes)

    def _fit_to_nodes(self):
        """Fit the map view to the bounding box of the currently-drawn
        (SKU-filtered) node set, with padding."""
        nodes = getattr(self, "_fit_nodes_cache", None) or self._nodes
        if not nodes or self._map_widget is None:
            return
        try:
            import math
            lats = [float(n["lat"]) for n in nodes
                    if n.get("lat") not in (None, "", "nan")]
            lons = [float(n["lon"]) for n in nodes
                    if n.get("lon") not in (None, "", "nan")]
            if not lats or not lons:
                return

            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)

            # 15% padding so markers don't sit at viewport edge
            pad_lat = max((max_lat - min_lat) * 0.15, 0.5)
            pad_lon = max((max_lon - min_lon) * 0.15, 0.5)

            top_left     = (max_lat + pad_lat, min_lon - pad_lon)
            bottom_right = (min_lat - pad_lat, max_lon + pad_lon)

            try:
                # tkintermapview >= 0.3 has fit_bounding_box
                self._map_widget.fit_bounding_box(top_left, bottom_right)
            except AttributeError:
                # Fallback: set_position + estimated zoom
                center_lat = (min_lat + max_lat) / 2
                center_lon = (min_lon + max_lon) / 2
                lat_span   = (max_lat - min_lat) + 2 * pad_lat
                lon_span   = (max_lon - min_lon) + 2 * pad_lon
                max_span   = max(lat_span, lon_span, 0.01)
                zoom = max(4, min(14, round(8.5 - math.log2(max_span))))
                self._map_widget.set_position(center_lat, center_lon)
                self._map_widget.set_zoom(zoom)
        except Exception as e:
            print(f"[WorldMap] fit_to_nodes failed: {e}")

    def _on_marker_click(self, marker, node: dict):
        """Show node info in the right panel."""
        info = []
        info.append(f"🏷  {node.get('node_name', node.get('node_id', ''))}")
        info.append(f"Type:  {node.get('node_type', '')}")
        info.append(f"Lat:   {node.get('lat', '')}")
        info.append(f"Lon:   {node.get('lon', '')}")
        if node.get("sku_id"):
            info.append(f"SKU:   {node['sku_id']}")
        if node.get("region"):
            info.append(f"Region: {node['region']}")
        if node.get("description"):
            info.append(f"\n{node['description']}")
        text = "\n".join(info)
        self._info_text.config(state="normal")
        self._info_text.delete("1.0", "end")
        self._info_text.insert("end", text)
        self._info_text.config(state="disabled")

    # ── EventTimeline animation ───────────────────────────────────────────

    def set_timeline(self, timeline) -> None:
        """Enable lot-flow animation once planning is complete."""
        self._timeline     = timeline
        self._anim_week    = 0
        self._anim_running = False
        if hasattr(self, "_map_play_btn"):
            self._map_play_btn.config(state="normal")
            self._map_stop_btn.config(state="normal")
        n = len(timeline)
        self._map_week_var.set(f"Week 0/{n}  ←  press ▶ to animate")

    def _anim_play(self):
        if not self._timeline:
            return
        self._anim_running = True
        self._map_play_btn.config(state="disabled")
        self._map_pause_btn.config(state="normal")
        self._map_stop_btn.config(state="normal")
        self._map_tick()

    def _anim_pause(self):
        self._anim_running = False
        self._map_play_btn.config(state="normal")
        self._map_pause_btn.config(state="disabled")

    def _anim_stop(self):
        self._anim_running = False
        self._anim_week    = 0
        if self._anim_after_id:
            self.after_cancel(self._anim_after_id)
            self._anim_after_id = None
        self._map_play_btn.config(state="normal")
        self._map_pause_btn.config(state="disabled")
        # Restore static paths
        self._draw_nodes()
        n = len(self._timeline) if self._timeline else 0
        self._map_week_var.set(f"Week 0/{n}  ←  press ▶ to animate")

    def _map_tick(self):
        if not self._anim_running or not self._timeline:
            return
        n = len(self._timeline)
        if self._anim_week >= n:
            self._anim_week = 0
        snap = self._timeline[self._anim_week]
        self._draw_animated_paths(snap)
        self._map_week_var.set(
            f"Week {self._anim_week + 1}/{n}  |  {snap.week_label}")
        self._anim_week += 1
        self._anim_after_id = self.after(self._anim_speed_ms, self._map_tick)

    def _draw_animated_paths(self, snap):
        """Redraw SC paths with widths proportional to this week's lot flows."""
        if self._map_widget is None or not self._nodes:
            return
        # Clear old paths only
        for p in self._paths:
            try: p.delete()
            except Exception: pass
        self._paths.clear()

        # Build lot-flow lookup from snapshot: gui_label -> flow count
        # GUI labels: "Region:{reg}", "Mother Plant", "SKU:{sku}"
        max_flow = snap.max_flow or 1

        # Node position lookup
        node_pos: dict = {}
        for node in self._nodes:
            ntype = str(node.get("node_type", ""))
            if ntype == "mother_plant":
                node_pos["Mother\nPlant"] = (float(node["lat"]), float(node["lon"]))
            elif ntype == "region_dc":
                reg = str(node.get("region", ""))
                node_pos[f"Region:{reg}"] = (float(node["lat"]), float(node["lon"]))
            elif ntype == "sku_supplier":
                sku = str(node.get("sku_id", ""))
                node_pos[f"SKU:{sku}"] = (float(node["lat"]), float(node["lon"]))
            elif ntype == "procurement":
                node_pos["Global\nProcurement"] = (float(node["lat"]), float(node["lon"]))

        # Draw flows
        for ef in snap.edge_flows:
            src_pos = node_pos.get(ef.src)
            dst_pos = node_pos.get(ef.dst)
            if src_pos is None or dst_pos is None:
                continue
            ratio = ef.lot_count / max_flow
            width = max(2, int(2 + 8 * ratio))
            color = "#66BB6A" if ef.direction == "supply" else "#42A5F5"
            if ef.bucket == "CO":
                color = "#FF9800"
            try:
                path = self._map_widget.set_path(
                    [src_pos, dst_pos],
                    color=color, width=width)
                self._paths.append(path)
            except Exception:
                pass

        # Static dim lines for inactive edges (respects the SKU filter)
        sku = self._current_map_sku()
        if self._sc_edges:
            pos_by_id = {}
            for n in self._nodes:
                try:
                    pos_by_id[str(n.get("node_id", ""))] = (float(n["lat"]), float(n["lon"]))
                except (TypeError, ValueError, KeyError):
                    pass
            for edge in self._sc_edges:
                if sku and edge["product"] != sku:
                    continue
                s_pos = pos_by_id.get(edge["child"])
                d_pos = pos_by_id.get(edge["parent"])
                if s_pos is None or d_pos is None:
                    continue
                try:
                    path = self._map_widget.set_path(
                        [s_pos, d_pos], color="#263238", width=1)
                    self._paths.insert(0, path)  # behind flow paths
                except Exception:
                    pass
        else:
            allowed_ids = self._product_nodes.get(sku) if sku else None
            nodes_scope = ([n for n in self._nodes
                            if str(n.get("node_id", "")) in allowed_ids]
                           if allowed_ids is not None else self._nodes)
            for src_type, dst_type in _MAP_LINKS:
                for src_node in nodes_scope:
                    if src_node.get("node_type") != src_type:
                        continue
                    for dst_node in nodes_scope:
                        if dst_node.get("node_type") != dst_type:
                            continue
                        # Check if this edge already has a flow path
                        s_pos = (float(src_node["lat"]), float(src_node["lon"]))
                        d_pos = (float(dst_node["lat"]), float(dst_node["lon"]))
                        # Add dim background line
                        try:
                            path = self._map_widget.set_path(
                                [s_pos, d_pos],
                                color="#263238", width=1)
                            self._paths.insert(0, path)  # behind flow paths
                        except Exception:
                            pass

# ──────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────
# Planning Operation Debugger panel
# ──────────────────────────────────────────────────────────────────────

class DebugPanel(tk.Frame):
    """
    Step-by-step Planning Operation Debugger.

    Layout:
      ┌── top bar ──────────────────────────────────────────────────────┐
      │  [⚙ Init Debugger]  Product: [▼]  Node: [▼]  Step: N / M       │
      ├── left (operator list) ──┬── right (PSI charts + delta) ────────┤
      │  ○ 1. LotGenerator       │  [DEMAND LAYER]  psi4demand           │
      │  ○ 2. HOOK_PRE_PLAN      │  ────────────────────────────────────  │
      │  ● 3. BackwardPlanner    │  [SUPPLY LAYER]  psi4supply           │
      │  ○ 4. copy_D→S           │  ────────────────────────────────────  │
      │  ○ 5. PushEngine         │  Delta (this step):                    │
      │  ○ 6. ForwardPlanner     │  Demand: P: +800 @ W28               │
      │  ○ 7. HOOK_POST_PLAN     │  Supply: no change                    │
      │  ──────────────────────  │                                        │
      │  [◀ Prev][▶ Next][▶▶ All]│                                        │
      │  [🔄 Reset]              │                                        │
      └──────────────────────────┴───────────────────────────────────────┘
    """

    _BUCKET_NAMES = ["S", "CO", "I", "P"]

    def __init__(self, parent, app_ref, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._app = app_ref           # reference to WOMApp
        self._debugger = None         # PlanningDebugger instance (set on init)
        self._product_var = tk.StringVar(value="")
        self._node_var    = tk.StringVar(value="")
        self._step_label_var = tk.StringVar(value="Step: — / —")
        self._status_var  = tk.StringVar(value="Click ⚙ Init to load the model and register operators.")
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self):
        # ── Top bar ───────────────────────────────────────────────────
        top = tk.Frame(self, bg=BG_MID, pady=4)
        top.pack(fill="x")

        tk.Button(
            top, text="⚙  Init Debugger",
            command=self._on_init,
            bg="#7B1FA2", fg="white", relief="flat",
            font=("Segoe UI", 9, "bold"), cursor="hand2", padx=8,
        ).pack(side="left", padx=(8, 4))

        tk.Button(
            top, text="🔄 Reset",
            command=self._on_reset,
            bg=BG_LIGHT, fg=FG_WHITE, relief="flat",
            font=("Segoe UI", 9), cursor="hand2", padx=6,
        ).pack(side="left", padx=2)

        tk.Label(top, text="Product:", bg=BG_MID, fg=FG_ACC,
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 2))
        self._product_om = tk.OptionMenu(top, self._product_var, "—",
                                         command=self._on_product_change)
        self._product_om.config(bg=BG_LIGHT, fg=FG_WHITE, relief="flat",
                                font=("Segoe UI", 9), highlightthickness=0,
                                activebackground=BG_MID)
        self._product_om["menu"].config(bg=BG_LIGHT, fg=FG_WHITE)
        self._product_om.pack(side="left")

        tk.Label(top, text="Node:", bg=BG_MID, fg=FG_ACC,
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 2))
        self._node_om = tk.OptionMenu(top, self._node_var, "—",
                                      command=self._on_node_change)
        self._node_om.config(bg=BG_LIGHT, fg=FG_WHITE, relief="flat",
                             font=("Segoe UI", 9), highlightthickness=0,
                             activebackground=BG_MID)
        self._node_om["menu"].config(bg=BG_LIGHT, fg=FG_WHITE)
        self._node_om.pack(side="left")

        tk.Label(top, textvariable=self._step_label_var,
                 bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 9)).pack(
            side="right", padx=12)

        # ── Status bar ────────────────────────────────────────────────
        tk.Label(self, textvariable=self._status_var,
                 bg="#0D1B2A", fg="#90A4AE",
                 font=("Segoe UI", 8), anchor="w", padx=8,
                 ).pack(fill="x", side="bottom", pady=(0, 0))

        # ── Main body: left list + right charts ───────────────────────
        body = tk.Frame(self, bg=BG_DARK)
        body.pack(fill="both", expand=True)

        # Left: operator list
        left = tk.Frame(body, bg=BG_MID, width=230)
        left.pack(side="left", fill="y", padx=(4, 0), pady=4)
        left.pack_propagate(False)

        tk.Label(left, text="Operator Sequence",
                 bg=BG_MID, fg=FG_ACC,
                 font=("Segoe UI", 9, "bold")).pack(pady=(6, 2))

        list_fr = tk.Frame(left, bg=BG_MID)
        list_fr.pack(fill="both", expand=True, padx=4)

        self._op_list = tk.Listbox(
            list_fr, bg=BG_DARK, fg=FG_WHITE,
            font=("Segoe UI", 9), selectmode="single",
            activestyle="none", highlightthickness=0, bd=0,
            width=26,
        )
        vsb = ttk.Scrollbar(list_fr, orient="vertical",
                            command=self._op_list.yview)
        self._op_list.configure(yscrollcommand=vsb.set)
        self._op_list.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Step control buttons
        btn_fr = tk.Frame(left, bg=BG_MID)
        btn_fr.pack(fill="x", padx=4, pady=6)

        self._btn_prev = tk.Button(
            btn_fr, text="◀ Prev",
            command=self._on_prev,
            bg=BG_LIGHT, fg=FG_WHITE, relief="flat",
            font=("Segoe UI", 9), cursor="hand2", state="disabled")
        self._btn_prev.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self._btn_next = tk.Button(
            btn_fr, text="Next ▶",
            command=self._on_next,
            bg="#1565C0", fg="white", relief="flat",
            font=("Segoe UI", 9, "bold"), cursor="hand2", state="disabled")
        self._btn_next.pack(side="left", fill="x", expand=True, padx=(2, 2))

        self._btn_all = tk.Button(
            btn_fr, text="▶▶ All",
            command=self._on_run_all,
            bg=BTN_RUN, fg="white", relief="flat",
            font=("Segoe UI", 9, "bold"), cursor="hand2", state="disabled")
        self._btn_all.pack(side="left", fill="x", expand=True, padx=(2, 0))

        # Right: charts + delta
        right = tk.Frame(body, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        # Two PSI charts (demand top / supply bottom) using subplot(2,1,*)
        chart_fr = tk.Frame(right, bg=BG_DARK)
        chart_fr.pack(fill="both", expand=True)

        self._fig = Figure(figsize=(9, 6), dpi=88, facecolor=BG_DARK)
        self._canvas = FigureCanvasTkAgg(self._fig, master=chart_fr)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        # Delta text
        delta_fr = tk.LabelFrame(
            right, text="  Delta (this step)  ",
            bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 8, "bold"),
            relief="groove", bd=1)
        delta_fr.pack(fill="x", pady=(2, 0))

        inner = tk.Frame(delta_fr, bg=BG_MID)
        inner.pack(fill="x", padx=4, pady=2)
        self._delta_text = tk.Text(
            inner, height=4, bg=BG_LIGHT, fg=FG_WHITE,
            font=("Consolas", 8), relief="flat", wrap="none", state="disabled")
        delta_vsb = ttk.Scrollbar(inner, orient="vertical",
                                  command=self._delta_text.yview)
        self._delta_text.configure(yscrollcommand=delta_vsb.set)
        delta_vsb.pack(side="right", fill="y")
        self._delta_text.pack(side="left", fill="x", expand=True)

        # Draw empty charts initially
        self._draw_empty()

    # ── Event handlers ────────────────────────────────────────────────

    def _on_init(self):
        """Build planning context and initialize debugger (runs in thread)."""
        import threading
        self._status_var.set("Initializing… (loading CSVs, building sc_tree)")
        self._set_buttons_enabled(False)
        threading.Thread(target=self._init_worker, daemon=True).start()

    def _init_worker(self):
        try:
            ctx = self._app._build_planning_context()
            self.after(0, lambda: self._on_init_done(ctx))
        except Exception:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda: self._on_init_error(tb))

    def _on_init_done(self, ctx):
        from wom.engine.planning_debugger import PlanningDebugger, OperatorStep

        sc_tree    = ctx["sc_tree"]
        weeks      = ctx["weeks"]
        bus        = ctx["bus"]
        cfg        = ctx["cfg"]
        lane_table = ctx["lane_table"]
        push_path  = ctx["push_path"]
        opening_inv = ctx["opening_inv"]
        prod_list  = list(sc_tree.products)

        # ── Build ordered operator steps + callables ───────────────────
        steps: list = []
        calls: list = []

        from wom.engine.hook_bus import (
            HOOK_PRE_PLAN, HOOK_POST_BACKWARD,
            HOOK_POST_COPY, HOOK_POST_FORWARD, HOOK_POST_PLAN)
        from wom.engine.backward_planner import BackwardPlanner
        from wom.engine.plan_copy import copy_demand_to_supply
        from wom.engine.forward_planner import ForwardPlanner
        from wom.engine.push_pull import PushProductionPlanner, PushConfig
        import csv as _csv
        import os as _os

        # Step 1: HOOK_PRE_PLAN
        steps.append(OperatorStep("HOOK_PRE_PLAN", "hook_pre_plan",
            "Plugins: HarvestBatch, HolidayCalendar cap_hard setup"))
        calls.append(lambda: bus.fire(HOOK_PRE_PLAN, sc_tree=sc_tree,
                                      weeks=weeks, config=cfg))

        # Per-product steps
        for prod_nm in prod_list:
            # BackwardPlanner
            pn = prod_nm  # capture
            steps.append(OperatorStep(
                f"BackwardPlanner [{pn}]", "backward_planner",
                f"Propagate demand lots from leaf_out upstream (LT offset, SS)"))
            calls.append(lambda p=pn:
                BackwardPlanner(sc_tree, lane_table=lane_table, config=cfg).run(p))

            # HOOK_POST_BACKWARD
            steps.append(OperatorStep(
                f"HOOK_POST_BACKWARD [{pn}]", "hook_post_backward",
                "Plugins: HolidayCalendar closure correction"))
            calls.append(lambda p=pn:
                bus.fire(HOOK_POST_BACKWARD, sc_tree=sc_tree,
                         prod_nm=p, weeks=weeks, config=cfg))

            # copy_demand_to_supply
            steps.append(OperatorStep(
                f"copy_D→S [{pn}]", "copy_demand_to_supply",
                "Copy psi4demand → psi4supply for all nodes"))
            calls.append(lambda p=pn: copy_demand_to_supply(sc_tree, p))

            # HOOK_POST_COPY
            steps.append(OperatorStep(
                f"HOOK_POST_COPY [{pn}]", "hook_post_copy",
                "Plugins post-copy hooks"))
            calls.append(lambda p=pn:
                bus.fire(HOOK_POST_COPY, sc_tree=sc_tree,
                         prod_nm=p, weeks=weeks, config=cfg))

            # PushEngine (if push_config.csv exists)
            if push_path and _os.path.exists(push_path):
                steps.append(OperatorStep(
                    f"PushEngine [{pn}]", "push_engine",
                    "Apply PUSH/PULL config (Mode4 LT-shifted pre-build)"))
                def _push_step(p=pn):
                    _push_cfgs = {}
                    with open(push_path, newline="", encoding="utf-8") as _pf:
                        for _pr in _csv.DictReader(_pf):
                            _pn2 = _pr.get("sku_id", "").strip()
                            if _pn2 == p:
                                _push_cfgs[_pn2] = PushConfig(
                                    node_id=_pr.get("node_id","").strip(),
                                    push_qty_per_week=int(_pr.get("push_qty_per_week") or 0),
                                    buffer_lots=int(_pr.get("buffer_lots") or 0),
                                    sku_id=_pn2,
                                    mode_only=_pr.get("mode_only","").strip().lower()=="true",
                                    mom_ref_node_id=_pr.get("mom_ref_node_id","").strip(),
                                    pre_build_qty_per_week=int(_pr.get("pre_build_qty_per_week") or 0),
                                    pre_build_end_week=_pr.get("pre_build_end_week","").strip(),
                                    push_lead_time_weeks=int(_pr.get("push_lead_time_weeks") or 0),
                                    push_eol_week=_pr.get("push_eol_week","").strip(),
                                )
                    if _push_cfgs:
                        PushProductionPlanner(sc_tree).setup_all(_push_cfgs)
                calls.append(_push_step)

            # ForwardPlanner
            steps.append(OperatorStep(
                f"ForwardPlanner [{pn}]", "forward_planner",
                "Apply capacity constraints, generate CO, PULL/PUSH supply"))
            calls.append(lambda p=pn:
                ForwardPlanner(sc_tree, opening_inv=opening_inv).run(p))

            # HOOK_POST_FORWARD
            steps.append(OperatorStep(
                f"HOOK_POST_FORWARD [{pn}]", "hook_post_forward",
                "Plugins post-forward hooks"))
            calls.append(lambda p=pn:
                bus.fire(HOOK_POST_FORWARD, sc_tree=sc_tree,
                         prod_nm=p, weeks=weeks, config=cfg))

        # HOOK_POST_PLAN
        steps.append(OperatorStep("HOOK_POST_PLAN", "hook_post_plan",
            "All products complete — final plugin hooks"))
        calls.append(lambda: bus.fire(HOOK_POST_PLAN, sc_tree=sc_tree,
                                      weeks=weeks, config=cfg))

        # ── Create debugger ────────────────────────────────────────────
        dbg = PlanningDebugger()
        dbg.initialize(sc_tree, weeks, steps, calls)
        self._debugger = dbg

        # ── Update product + node selectors ───────────────────────────
        self._update_product_menu(prod_list)
        if prod_list:
            self._product_var.set(prod_list[0])
            self._update_node_menu(prod_list[0])

        # ── Refresh operator list ──────────────────────────────────────
        self._refresh_op_list()

        # ── Enable buttons ─────────────────────────────────────────────
        self._set_buttons_enabled(True)
        self._step_label_var.set(f"Step: 0 / {dbg.total_steps}  (before any operator)")
        self._status_var.set(
            f"✅ Initialized: {len(prod_list)} product(s), "
            f"{len(dbg.all_node_names())} nodes, {dbg.total_steps} operator steps. "
            "Click ▶ Next to run the first operator."
        )
        # Draw initial (empty) PSI state
        self._refresh_charts()

    def _on_init_error(self, tb: str):
        self._status_var.set(f"❌ Init failed: {tb[:120]}")
        print(f"[DebugPanel] Init error:\n{tb}")

    def _on_reset(self):
        """Re-initialize from scratch (re-reads all CSVs)."""
        self._debugger = None
        self._op_list.delete(0, "end")
        self._draw_empty()
        self._set_buttons_enabled(False)
        self._step_label_var.set("Step: — / —")
        self._status_var.set("Reset. Click ⚙ Init to reload.")

    def _on_next(self):
        if self._debugger is None:
            return
        dbg = self._debugger
        if dbg.is_at_end:
            self._status_var.set("All operators complete.")
            return
        step_idx = dbg.current_step + 1
        step = dbg.steps[step_idx]
        self._status_var.set(f"Running: {step.name}…")
        self.update_idletasks()
        dbg.step_forward()
        self._on_step_done()

    def _on_prev(self):
        """Move back to view the previous step's snapshot (no re-execution)."""
        if self._debugger is None:
            return
        dbg = self._debugger
        if dbg.is_at_start:
            return
        # We don't re-execute; just move the view pointer
        dbg.current_step -= 1
        self._on_step_done(direction="back")

    def _on_run_all(self):
        if self._debugger is None:
            return
        import threading
        self._set_buttons_enabled(False)
        self._status_var.set("Running all remaining operators…")
        def _worker():
            self._debugger.run_all()
            self.after(0, lambda: self._on_step_done())
        threading.Thread(target=_worker, daemon=True).start()

    def _on_product_change(self, *_):
        self._update_node_menu(self._product_var.get())
        self._refresh_charts()

    def _on_node_change(self, *_):
        self._refresh_charts()

    def _on_step_done(self, direction="forward"):
        dbg = self._debugger
        if dbg is None:
            return
        self._refresh_op_list()
        self._refresh_charts()
        self._set_buttons_enabled(True)
        n = dbg.total_steps
        cur = dbg.current_step
        self._step_label_var.set(
            f"Step: {cur + 1} / {n}  ({dbg.steps[cur].name if cur >= 0 else 'initial'})")
        if dbg.is_at_end:
            self._status_var.set("✅ All operators complete.")
        elif cur == -1:
            self._status_var.set("Showing initial state (no operators run yet).")
        else:
            step = dbg.steps[cur]
            self._status_var.set(
                f"Step {cur + 1}/{n}: {step.name} — {step.description}")

    # ── UI helpers ────────────────────────────────────────────────────

    def _update_product_menu(self, products):
        menu = self._product_om["menu"]
        menu.delete(0, "end")
        for p in products:
            menu.add_command(label=p,
                             command=lambda v=p: self._product_var.set(v) or
                             self._on_product_change())
        if products:
            self._product_var.set(products[0])

    def _update_node_menu(self, product):
        if self._debugger is None:
            return
        dbg = self._debugger
        node_names = dbg.all_node_names()

        menu = self._node_om["menu"]
        menu.delete(0, "end")
        for nn in node_names:
            menu.add_command(label=nn,
                             command=lambda v=nn: self._node_var.set(v) or
                             self._on_node_change())
        if node_names:
            current = self._node_var.get()
            if current not in node_names:
                self._node_var.set(node_names[0])

    def _refresh_op_list(self):
        if self._debugger is None:
            return
        dbg = self._debugger
        self._op_list.delete(0, "end")
        for i, step in enumerate(dbg.steps):
            if i < dbg.current_step:
                marker = "✓"
                bg = "#1B5E20"  # completed: dark green
            elif i == dbg.current_step:
                marker = "●"
                bg = "#0D47A1"  # current: dark blue
            else:
                marker = "○"
                bg = BG_DARK   # pending: default
            label = f"  {marker} {i+1:02d}. {step.name}"
            self._op_list.insert("end", label)
            self._op_list.itemconfig(i, bg=bg, fg=FG_WHITE)

        # Scroll to current step
        if dbg.current_step >= 0:
            self._op_list.see(dbg.current_step)

    def _set_buttons_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self._btn_prev.config(state=state)
        self._btn_next.config(state=state)
        self._btn_all.config(state=state)

    # ── Chart drawing ─────────────────────────────────────────────────

    def _draw_empty(self):
        self._fig.clf()
        for i, title in enumerate(["DEMAND LAYER  (psi4demand)", "SUPPLY LAYER  (psi4supply)"], 1):
            ax = self._fig.add_subplot(2, 1, i)
            ax.set_facecolor(BG_MID)
            ax.text(0.5, 0.5, "No data — click ⚙ Init",
                    color="#546E7A", ha="center", va="center",
                    transform=ax.transAxes, fontsize=9)
            ax.set_title(title, color=FG_ACC, fontsize=9, pad=4)
            ax.axis("off")
        self._fig.patch.set_facecolor(BG_DARK)
        self._fig.tight_layout(pad=1.5)
        self._canvas.draw()
        self._set_delta_text("(no data)")

    def _refresh_charts(self):
        if self._debugger is None:
            self._draw_empty()
            return
        dbg = self._debugger
        node_name = self._node_var.get()
        product   = self._product_var.get()
        step_idx  = dbg.current_step

        # Get PSI arrays from snapshot
        demand_psi = dbg.get_psi_arrays(step_idx, node_name, "demand")
        supply_psi = dbg.get_psi_arrays(step_idx, node_name, "supply")
        weeks = dbg.weeks

        # Get cap_hard values for Capacity Line
        node_obj  = dbg.get_node(product, node_name)
        n_weeks   = len(weeks) if weeks else 0
        cap_values = ([node_obj.cap_hard(w) for w in range(n_weeks)]
                      if node_obj and n_weeks else None)

        self._fig.clf()
        self._fig.patch.set_facecolor(BG_DARK)

        shortfall = (dbg.get_shortfall(step_idx, node_name)
                     if hasattr(dbg, 'get_shortfall') else None)

        self._draw_psi_subplot(
            self._fig.add_subplot(2, 1, 1),
            demand_psi, weeks, node_name,
            title=f"DEMAND LAYER  (psi4demand)  │  {node_name}",
            layer_color="#64B5F6",
            cap_values=cap_values,
        )
        self._draw_psi_subplot(
            self._fig.add_subplot(2, 1, 2),
            supply_psi, weeks, node_name,
            title=f"SUPPLY LAYER  (psi4supply)  │  {node_name}",
            layer_color="#A5D6A7",
            cap_values=cap_values,
            shortfall=shortfall,
        )

        self._fig.tight_layout(pad=1.5)
        self._canvas.draw()

        # Delta
        if step_idx >= 0:
            delta = dbg.get_delta(step_idx, node_name)
            if delta and (delta["changes_demand"] or delta["changes_supply"]):
                text = "\n".join(delta["summary_lines"])
            else:
                text = "(no change in this step for selected node)"
        else:
            text = "(initial state — before any operator)"
        self._set_delta_text(text)

    def _draw_psi_subplot(self, ax, psi_data, weeks, node_name, title, layer_color,
                          cap_values=None, shortfall=None):
        """
        Draw a single PSI chart (P/S/CO bars + I line + Capacity Line) on ax.
        psi_data: [[S, CO, I, P] x n_weeks] or None
        cap_values: [cap_hard(w) for w in range(n_weeks)] or None
        shortfall: [shortage_count per week] for PUSH decoupling nodes, or None
        """
        ax.set_facecolor(BG_MID)
        ax.set_title(title, color=layer_color, fontsize=8, pad=4)

        if not psi_data or not weeks:
            ax.text(0.5, 0.5, "No PSI data",
                    color="#546E7A", ha="center", va="center",
                    transform=ax.transAxes, fontsize=8)
            ax.axis("off")
            return

        n = len(psi_data)
        s_vals  = [psi_data[w][0] for w in range(n)]
        co_vals = [psi_data[w][1] for w in range(n)]
        i_vals  = [psi_data[w][2] for w in range(n)]
        p_vals  = [psi_data[w][3] for w in range(n)]

        if not any(v > 0 for v in s_vals + co_vals + i_vals + p_vals):
            ax.text(0.5, 0.5, "All buckets empty",
                    color="#546E7A", ha="center", va="center",
                    transform=ax.transAxes, fontsize=8)
            ax.set_title(title, color=layer_color, fontsize=8, pad=4)
            for sp in ax.spines.values():
                sp.set_visible(False)
            ax.tick_params(left=False, bottom=False,
                           labelleft=False, labelbottom=False)
            return

        x = list(range(n))
        bw = 0.28

        ax.bar([xi - bw for xi in x], p_vals,  width=bw,
               label="P: Production/Receipt",  color="#4CAF50", alpha=0.85)
        ax.bar([xi       for xi in x], s_vals,  width=bw,
               label="S: Sales/Shipment",      color="#2196F3", alpha=0.85)
        if any(v > 0 for v in co_vals):
            ax.bar([xi + bw for xi in x], co_vals, width=bw,
                   label="CO: Carry-Over",     color="#F44336", alpha=0.85)

        # -- PUSH shortfall (Action-TODO signal) ----------------------------
        # Shown as red hatched bars when PUSH decoupling node has shortage.
        # shortage[w] = unmet demand in week w; S stays as demand_staircase.
        if shortfall and any(v > 0 for v in shortfall):
            sf_n = min(len(shortfall), n)
            sf_vals = list(shortfall[:sf_n]) + [0] * (n - sf_n)
            ax.bar([xi + bw for xi in x], sf_vals, width=bw,
                   label="Shortage (Action-TODO)", color="#FF1744",
                   alpha=0.90, hatch="//", edgecolor="#FF1744")

        # -- Capacity Line (step function) ----------------------------------
        # Draw cap_hard as an orange dashed step line on the main (left) axis.
        # Only draw where cap > 0 to avoid cluttering unconstrained nodes.
        if cap_values and any(v > 0 for v in cap_values):
            cap_n = min(len(cap_values), n)
            # Build step-line segments: draw horizontal segments for each week
            cap_x, cap_y = [], []
            for wi in range(cap_n):
                cv = cap_values[wi]
                if cv > 0:
                    cap_x += [wi - 0.5, wi + 0.5]
                    cap_y += [cv, cv]
                else:
                    # gap: push a NaN break so segments don't connect across 0
                    cap_x += [wi]
                    cap_y += [float("nan")]
            ax.plot(cap_x, cap_y, color="#FF9800", linestyle="--",
                    linewidth=1.2, label="Cap. Hard", zorder=5)

        ax2 = ax.twinx()
        ax2.fill_between(x, i_vals, alpha=0.15, color="#FF9800")
        ax2.plot(x, i_vals, color="#FF9800", linewidth=1.2,
                 marker=".", markersize=2, label="I: Inventory")
        ax2.set_ylabel("Inventory", color="#FF9800", fontsize=6)
        ax2.tick_params(colors=FG_WHITE, labelsize=5)
        ax2.set_facecolor(BG_MID)

        # X-axis ticks
        t_idx, t_lbl = _445_ticks(weeks)
        if t_idx:
            ax.set_xticks(t_idx)
            ax.set_xticklabels(t_lbl, rotation=0, ha="center", fontsize=5)
        else:
            ax.set_xticks(x[::4])
            ax.set_xticklabels(weeks[::4], rotation=45, ha="right", fontsize=5)

        ax.set_ylabel("Lots", color=FG_ACC, fontsize=6)
        ax.tick_params(colors=FG_WHITE, labelsize=5)
        for sp in ax.spines.values():
            sp.set_edgecolor(BG_LIGHT)
        ax.set_title(title, color=layer_color, fontsize=8, pad=4)

        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2,
                  facecolor=BG_LIGHT, labelcolor=FG_WHITE,
                  fontsize=6, loc="upper right",
                  framealpha=0.7, ncol=2)

    def _set_delta_text(self, text: str):
        self._delta_text.config(state="normal")
        self._delta_text.delete("1.0", "end")
        self._delta_text.insert("end", text)
        self._delta_text.config(state="disabled")


# Main application window
# ──────────────────────────────────────────────────────────────────────

def _detect_version_label(repo_root: str) -> str:
    """WOM のバージョン表記（例 'v1r2m3'）を自動検出する。

    優先順: (1) git ブランチ名 → (2) リポジトリフォルダ名 → (3) 既定 'dev'。
    'wom-' 接頭辞は除去する（`wom-v1r2m3` → `v1r2m3`）。
    毎リリースでタイトル文字列を手編集する作業を避けるための仕組み。
    """
    def _strip(name: str) -> str:
        name = (name or "").strip()
        return name[len("wom-"):] if name.startswith("wom-") else name

    # (1) git ブランチ（最も正確。ブランチを切り替えれば表示も追従）
    try:
        import subprocess
        br = subprocess.check_output(
            ["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True, timeout=3).strip()
        if br and br != "HEAD":
            return _strip(br)
    except Exception:
        pass
    # (2) フォルダ名（git 不在・detached HEAD でもフォールバック）
    base = _strip(os.path.basename(os.path.normpath(repo_root)))
    if base:
        return base
    # (3) 既定
    return "dev"


class WOMApp(tk.Tk):
    """Top-level WOM application window."""

    def __init__(self):
        super().__init__()
        # Version label auto-detected from git branch / folder name
        # (no manual edit of the title string per release).
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(here))
        self._version = _detect_version_label(root)
        self.title(f"WOM – Weekly Operation Model  {self._version}")
        self.configure(bg=BG_DARK)
        self.geometry("1280x820")
        self.minsize(900, 600)

        self._sim: Optional[WOMSimulator] = None
        self._mgr: Optional[ScenarioManager] = None

        # Detect sample data directory relative to this file
        # Default to smartx-2027-2029 subfolder (has sc_tree_master.csv)
        self._sample_dir = os.path.join(root, "data", "sample", "smartx-2027-2029")

        self._build_ui()
        self._try_load_sample_paths()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        # ── Title bar ────────────────────────────────────────────────
        title_bar = tk.Frame(self, bg="#0D1B2A", pady=6)
        title_bar.pack(fill="x")
        tk.Label(title_bar, text="WOM  –  Weekly Operation Model",
                 bg="#0D1B2A", fg=FG_WHITE,
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=16)
        tk.Label(title_bar, text=self._version,
                 bg="#0D1B2A", fg=FG_ACC,
                 font=("Segoe UI", 10)).pack(side="right", padx=16)

        # ── Main area ────────────────────────────────────────────
        main = tk.Frame(self, bg=BG_DARK)
        main.pack(fill="both", expand=True, padx=0, pady=0)

        # Left panel — scrollable canvas wrapper
        left_outer = tk.Frame(main, bg=BG_MID, width=284)
        left_outer.pack(side="left", fill="y")
        left_outer.pack_propagate(False)

        _lcanvas = tk.Canvas(left_outer, bg=BG_MID, highlightthickness=0, width=262)
        _lvsb = ttk.Scrollbar(left_outer, orient="vertical", command=_lcanvas.yview)
        _lcanvas.configure(yscrollcommand=_lvsb.set)
        _lvsb.pack(side="right", fill="y")
        _lcanvas.pack(side="left", fill="both", expand=True)

        left = tk.Frame(_lcanvas, bg=BG_MID)
        _lcwin = _lcanvas.create_window((0, 0), window=left, anchor="nw")

        def _left_frame_cfg(event, _c=_lcanvas, _w=_lcwin):
            _c.configure(scrollregion=_c.bbox("all"))
        def _left_canvas_cfg(event, _c=_lcanvas, _w=_lcwin):
            _c.itemconfig(_w, width=event.width)
        def _left_mousewheel(event, _c=_lcanvas):
            _c.yview_scroll(int(-1 * (event.delta / 120)), "units")

        left.bind("<Configure>", _left_frame_cfg)
        _lcanvas.bind("<Configure>", _left_canvas_cfg)
        _lcanvas.bind("<Enter>",
            lambda e, _c=_lcanvas: _c.bind_all("<MouseWheel>", _left_mousewheel))
        _lcanvas.bind("<Leave>",
            lambda e, _c=_lcanvas: _c.unbind_all("<MouseWheel>"))

        self._build_left_panel(left)

        # Right panel (notebook)
        right = tk.Frame(main, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        self._build_right_panel(right)

        # ── Status bar ────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready. Load data files and click Run.")
        status = tk.Label(self, textvariable=self._status_var,
                          bg="#0D1B2A", fg=FG_ACC,
                          font=("Segoe UI", 9), anchor="w", padx=12)
        status.pack(fill="x", side="bottom")

    def _status(self, msg: str) -> None:
        """Update the status bar text."""
        self._status_var.set(msg)

    def _build_left_panel(self, parent):
        # ── Config section ───────────────────────────────────────────
        sec = tk.LabelFrame(parent, text="  Planning Config  ",
                            bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 9, "bold"),
                            relief="groove", bd=1)
        sec.pack(fill="x", padx=8, pady=(12, 4))

        self._e_start = LabeledEntry(sec, "Start Week:", "2024-W01", width=12)
        self._e_start.pack(fill="x", padx=6, pady=2)

        self._e_weeks = LabeledEntry(sec, "# Weeks:", "26", width=6)
        self._e_weeks.pack(fill="x", padx=6, pady=2)

        self._e_ss = LabeledEntry(sec, "Safety Stock (wks):", "2.0", width=6)
        self._e_ss.pack(fill="x", padx=6, pady=2)

        self._e_lt = LabeledEntry(sec, "Lead Time (wks):", "4", width=6)
        self._e_lt.pack(fill="x", padx=6, pady=2)

        self._e_cap = tk.BooleanVar(value=True)
        tk.Checkbutton(sec, text="Capacity Constrained",
                       variable=self._e_cap, bg=BG_MID, fg=FG_WHITE,
                       selectcolor=BG_LIGHT, activebackground=BG_MID,
                       font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=2)

        # ── Files section ────────────────────────────────────────────
        fsec = tk.LabelFrame(parent, text="  Input Files  ",
                             bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 9, "bold"),
                             relief="groove", bd=1)
        fsec.pack(fill="x", padx=8, pady=4)

        # Load Model Folder button
        _folder_btn_fr = tk.Frame(fsec, bg=BG_MID)
        _folder_btn_fr.pack(fill="x", padx=6, pady=(4, 2))
        tk.Button(_folder_btn_fr, text="📂  Load Model Folder…",
                  command=self._load_model_folder,
                  bg="#1565C0", fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2",
                  pady=4).pack(fill="x")

        # Compact folder display (visible after folder is loaded)
        self._folder_disp_fr = tk.Frame(fsec, bg=BG_MID)
        self._folder_disp_var = tk.StringVar(value="")
        tk.Label(self._folder_disp_fr, textvariable=self._folder_disp_var,
                 bg=BG_MID, fg="#81D4FA",
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(6, 0))
        self._files_toggle_btn = tk.Button(
            self._folder_disp_fr, text="▼ 詳細",
            command=self._toggle_file_entries,
            bg=BG_DARK, fg="#78909C", relief="flat",
            font=("Segoe UI", 8), cursor="hand2", pady=0)
        self._files_toggle_btn.pack(side="right", padx=(0, 4))
        # hidden initially — shown when folder is loaded

        # Individual file entries frame (collapsible)
        self._file_entries_fr = tk.Frame(fsec, bg=BG_MID)
        self._file_entries_fr.pack(fill="x")

        self._f_sku  = FileEntry(self._file_entries_fr, "SKU Master:")
        self._f_sku.pack(fill="x", padx=6, pady=2)
        self._f_dem  = FileEntry(self._file_entries_fr, "Demand Forecast:")
        self._f_dem.pack(fill="x", padx=6, pady=2)
        self._f_inv  = FileEntry(self._file_entries_fr, "Inventory Master:")
        self._f_inv.pack(fill="x", padx=6, pady=2)
        self._f_cap  = FileEntry(self._file_entries_fr, "Capacity Plan:")
        self._f_cap.pack(fill="x", padx=6, pady=2)
        self._f_push    = FileEntry(self._file_entries_fr, "Push Config:")
        self._f_push.pack(fill="x", padx=6, pady=2)
        self._f_holiday = FileEntry(self._file_entries_fr, "Holiday Calendar:")
        self._f_holiday.pack(fill="x", padx=6, pady=2)
        self._f_lane = FileEntry(self._file_entries_fr, "Lane Assignment:")
        self._f_lane.pack(fill="x", padx=6, pady=2)
        self._f_node = FileEntry(self._file_entries_fr, "Node Master:")
        self._f_node.pack(fill="x", padx=6, pady=2)

        self._files_collapsed = False  # track state

        # ── SC Tree Master (Phase B multi-tier) ───────────────────────
        stsec = tk.LabelFrame(parent, text="  SC Tree Master (Multi-tier)  ",
                              bg=BG_MID, fg="#A5D6A7", font=("Segoe UI", 9, "bold"),
                              relief="groove", bd=1)
        stsec.pack(fill="x", padx=8, pady=4)
        self._f_sc_tree = FileEntry(stsec, "SC Tree Master:")
        self._f_sc_tree.pack(fill="x", padx=6, pady=2)
        self._sc_tree_hint_var = tk.StringVar(value="（省略時は Demo 2-tier tree を自動生成）")
        self._sc_tree_hint_lbl = tk.Label(
            stsec, textvariable=self._sc_tree_hint_var,
            bg=BG_MID, fg="#78909C", font=("Segoe UI", 8))
        self._sc_tree_hint_lbl.pack(anchor="w", padx=6)

        # ── Tariff & FX files ─────────────────────────────────────────
        lcsec = tk.LabelFrame(parent, text="  Tariff & FX (Landed Cost)  ",
                              bg=BG_MID, fg="#FFD54F", font=("Segoe UI", 9, "bold"),
                              relief="groove", bd=1)
        lcsec.pack(fill="x", padx=8, pady=4)
        self._f_edge_cost = FileEntry(lcsec, "Edge Cost Master:")
        self._f_edge_cost.pack(fill="x", padx=6, pady=2)
        self._f_route = FileEntry(lcsec, "Route Master:")
        self._f_route.pack(fill="x", padx=6, pady=2)

        # ── Scenarios ────────────────────────────────────────────────
        scsec = tk.LabelFrame(parent, text="  Scenarios  ",
                              bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 9, "bold"),
                              relief="groove", bd=1)
        scsec.pack(fill="x", padx=8, pady=4)

        headers = tk.Frame(scsec, bg=BG_MID)
        headers.pack(fill="x", padx=4)
        for txt, w in [("Name", 8), ("Dem×", 5), ("Sup×", 5)]:
            tk.Label(headers, text=txt, bg=BG_MID, fg=FG_ACC,
                     font=("Segoe UI", 8, "bold"), width=w).pack(side="left")

        self._scenario_rows: list = []
        defaults = [("Base", "1.00", "1.00"),
                    ("Upside", "1.20", "1.00"),
                    ("Downside", "0.80", "1.00")]
        for name, dm, sm in defaults:
            row = tk.Frame(scsec, bg=BG_MID)
            row.pack(fill="x", padx=4, pady=1)
            n_var = tk.StringVar(value=name)
            d_var = tk.StringVar(value=dm)
            s_var = tk.StringVar(value=sm)
            for var, w in [(n_var, 8), (d_var, 5), (s_var, 5)]:
                tk.Entry(row, textvariable=var, width=w,
                         bg=BG_LIGHT, fg=FG_WHITE, insertbackground=FG_WHITE,
                         relief="flat", font=("Segoe UI", 9)).pack(side="left", padx=1)
            self._scenario_rows.append((n_var, d_var, s_var))

        # ── Action buttons ───────────────────────────────────────────
        btns = tk.Frame(parent, bg=BG_MID)
        btns.pack(fill="x", padx=8, pady=8)

        tk.Button(btns, text="▶  Run Simulation",
                  command=self._run_simulation,
                  bg=BTN_RUN, fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", pady=6).pack(fill="x", pady=(0, 4))

        tk.Button(btns, text="⚙  Run Planning Engine",
                  command=self._run_planning_engine,
                  bg="#7B1FA2", fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", pady=6).pack(fill="x", pady=(0, 4))

        tk.Button(btns, text="⬇  Export to Excel",
                  command=self._export_excel,
                  bg=BTN_EXP, fg="white", font=("Segoe UI", 10, "bold"),
                  relief="flat", pady=6).pack(fill="x", pady=(0, 4))

        tk.Button(btns, text="⬇  Export to CSV",
                  command=self._export_csv,
                  bg=BG_LIGHT, fg=FG_WHITE, font=("Segoe UI", 9),
                  relief="flat", pady=5).pack(fill="x")

        # Progress bar
        self._progress = ttk.Progressbar(parent, mode="indeterminate")
        self._progress.pack(fill="x", padx=8, pady=(8, 0))

        # ── Plugin panel ──────────────────────────────────────────────
        self._build_plugin_panel(parent)

    def _build_plugin_panel(self, parent):
        """Build the Plugin ON/OFF checklist below the progress bar."""
        from wom.plugins import ALL_BUILTIN_PLUGINS

        sec = tk.LabelFrame(parent, text=" Plugins ",
                            bg=BG_DARK, fg="#CE93D8",
                            font=("Segoe UI", 9, "bold"),
                            relief="groove", bd=1)
        sec.pack(fill="x", padx=8, pady=(6, 4))

        self._plugin_vars: dict = {}   # name -> BooleanVar
        self._plugin_instances: dict = {}  # name -> WOMPlugin instance

        for cls in ALL_BUILTIN_PLUGINS:
            inst = cls()
            var  = tk.BooleanVar(value=False)
            self._plugin_vars[inst.name]     = var
            self._plugin_instances[inst.name] = inst

            row = tk.Frame(sec, bg=BG_DARK)
            row.pack(fill="x", padx=4, pady=1)
            tk.Checkbutton(row, variable=var, bg=BG_DARK,
                           fg=FG_WHITE, selectcolor=BG_MID,
                           activebackground=BG_DARK,
                           activeforeground=FG_WHITE).pack(side="left")
            tk.Label(row, text=inst.label, bg=BG_DARK, fg=FG_WHITE,
                     font=("Segoe UI", 8), anchor="w").pack(side="left", fill="x")

    def _build_right_panel(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("TNotebook",       background=BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab",   background=BG_MID,  foreground=FG_WHITE,
                        font=("Segoe UI", 9), padding=[10, 4])
        style.map("TNotebook.Tab", background=[("selected", BG_LIGHT)])

        self._chart_panel = ChartPanel(nb)
        nb.add(self._chart_panel, text="  \U0001f4c8 Charts  ")

        self._kpi_panel = KPITablePanel(nb)
        nb.add(self._kpi_panel, text="  \U0001f4ca KPI Table  ")

        # At-risk tab
        self._risk_frame = tk.Frame(nb, bg=BG_DARK)
        nb.add(self._risk_frame, text="  ⚠  At-Risk SKUs  ")
        self._build_risk_tab(self._risk_frame)

        # Scenario delta tab
        self._delta_frame = tk.Frame(nb, bg=BG_DARK)
        nb.add(self._delta_frame, text="  Δ  Scenario Delta  ")
        self._build_delta_tab(self._delta_frame)

        self._mgmt_panel = ManagementCockpitPanel(nb)
        nb.add(self._mgmt_panel, text="  \U0001f4b9 Management  ")

        self._ppc_panel = PPCTabPanel(nb, output_dir="output/ppc")
        nb.add(self._ppc_panel, text="  \U0001f4b0 PPC  ")

        self._network_panel = SCNetworkPanel(nb)
        nb.add(self._network_panel, text="  \U0001f310 Network  ")

        self._worldmap_panel = WorldMapPanel(nb)
        nb.add(self._worldmap_panel, text="  \U0001f5fa World Map  ")

        # ── Planning Debugger tab ──────────────────────────────────────
        self._debug_panel = DebugPanel(nb, app_ref=self)
        nb.add(self._debug_panel, text="  \U0001f50d Debug  ")

        # ── 初期表示タブ: World Map（計画対象の地理スコープを即座に把握）
        nb.select(self._worldmap_panel)

    def _build_risk_tab(self, parent):
        cols = [Cols.SCENARIO, Cols.SKU_ID, Cols.REGION, Cols.WEEK,
                Cols.FILL_RATE, Cols.INV_COVER_WKS, Cols.STOCKOUT_QTY]
        self._risk_tree = ttk.Treeview(parent, columns=cols, show="headings")
        for c in cols:
            self._risk_tree.heading(c, text=c.replace("_", " ").title())
            self._risk_tree.column(c, width=110, anchor="center")
        vsb = ttk.Scrollbar(parent, orient="vertical", command=self._risk_tree.yview)
        self._risk_tree.configure(yscrollcommand=vsb.set)
        self._risk_tree.pack(fill="both", expand=True, side="left")
        vsb.pack(fill="y", side="right")

    def _build_delta_tab(self, parent):
        # Chart: total stockout Base vs others
        self._delta_fig = Figure(figsize=(9, 5), dpi=100, facecolor=BG_DARK)
        self._delta_canvas = FigureCanvasTkAgg(self._delta_fig, master=parent)
        self._delta_canvas.get_tk_widget().pack(fill="both", expand=True)

    # ------------------------------------------------------------------ #
    # Sample data auto-load
    # ------------------------------------------------------------------ #

    def _try_load_sample_paths(self):
        sd = self._sample_dir
        for attr, fname in [
            ("_f_sku",       "sku_master.csv"),
            ("_f_dem",       "demand_forecast.csv"),
            ("_f_inv",       "inventory_master.csv"),
            ("_f_cap",       "capacity_plan.csv"),
            ("_f_push",      "push_config.csv"),
            ("_f_holiday",   "holiday_calendar.csv"),
            ("_f_lane",      "lane_assignment.csv"),
            ("_f_node",      "node_master.csv"),
            ("_f_edge_cost", "edge_cost_master.csv"),
            ("_f_route",     "route_master.csv"),
            ("_f_sc_tree",   "sc_tree_master.csv"),
        ]:
            path = os.path.join(sd, fname)
            if os.path.exists(path):
                getattr(self, attr).set(path)
        # Cache model_dir for cost chart lookup
        self._model_dir = sd
        self._node_cost_master = None  # invalidate cache

    # ------------------------------------------------------------------ #
    # Load Model Folder + Auto-detect Period
    # ------------------------------------------------------------------ #

    def _load_model_folder(self):
        """Open folder dialog; fill all 8 FileEntry fields from standard filenames."""
        folder = filedialog.askdirectory(title="モデルフォルダを選択 (CSVファイルが入ったフォルダ)")
        if not folder:
            return
        FILE_MAP = [
            ("_f_sku",       "sku_master.csv"),
            ("_f_dem",       "demand_forecast.csv"),
            ("_f_inv",       "inventory_master.csv"),
            ("_f_cap",       "capacity_plan.csv"),
            ("_f_push",      "push_config.csv"),
            ("_f_holiday",   "holiday_calendar.csv"),
            ("_f_lane",      "lane_assignment.csv"),
            ("_f_node",      "node_master.csv"),
            ("_f_edge_cost", "edge_cost_master.csv"),
            ("_f_route",     "route_master.csv"),
            ("_f_sc_tree",   "sc_tree_master.csv"),
        ]
        loaded, missing = [], []
        for attr, fname in FILE_MAP:
            path = os.path.join(folder, fname)
            if os.path.exists(path):
                getattr(self, attr).set(path)
                loaded.append(fname)
            else:
                missing.append(fname)
        # Auto-detect planning period from demand file
        self._auto_detect_planning_period()

        # Compact folder display: hide individual entries, show folder name
        base = os.path.basename(folder)
        self._folder_disp_var.set(f"📁  {base}/")
        self._folder_disp_fr.pack(fill="x", padx=6, pady=(0, 2))
        self._file_entries_fr.pack_forget()
        self._files_toggle_btn.config(text="▼ 詳細")
        self._files_collapsed = True

        # Cache model_dir for cost chart lookup
        self._model_dir = folder
        self._node_cost_master = None  # invalidate cache

        msg = f"📂 {base}: {len(loaded)} files loaded"
        if missing:
            msg += f"  (not found: {', '.join(missing)})"
        self._status(msg)

        # Load node_master into WorldMap immediately on folder selection
        node_path = os.path.join(folder, "node_master.csv")
        sc_tree_path_wm = os.path.join(folder, "sc_tree_master.csv")
        if not os.path.exists(sc_tree_path_wm):
            sc_tree_path_wm = ""
        if os.path.exists(node_path):
            try:
                self._worldmap_panel.load_default(node_path, sc_tree_path_wm)
            except Exception as _wm_exc:
                print(f"[WorldMap] node load on folder select failed: {_wm_exc}")

    def _toggle_file_entries(self):
        """Toggle collapse/expand of the 5 individual FileEntry widgets."""
        if getattr(self, "_files_collapsed", False):
            self._file_entries_fr.pack(fill="x", before=self._folder_disp_fr)
            self._files_toggle_btn.config(text="▲ 閉じる")
            self._files_collapsed = False
        else:
            self._file_entries_fr.pack_forget()
            self._files_toggle_btn.config(text="▼ 詳細")
            self._files_collapsed = True

    def _auto_detect_planning_period(self):
        """Read demand_forecast.csv and auto-set Start Week / # Weeks."""
        dem_path = self._f_dem.get() if hasattr(self, "_f_dem") else ""
        if not dem_path or not os.path.exists(dem_path):
            return
        # Planning warm-up (Phase 2, opt-in): materialize warm-up rows from
        # planning_config.csv BEFORE period detection so the earlier start weeks
        # are picked up. No planning_config.csv -> no-op (existing cases unchanged).
        try:
            from wom.engine.warmup import materialize_warmup, format_summary
            print(format_summary(materialize_warmup(os.path.dirname(dem_path))))
        except Exception as exc:
            print(f"[warmup] skipped: {exc}")
        try:
            dem_df = pd.read_csv(dem_path)
            if "week" not in dem_df.columns:
                return
            weeks_sorted = sorted(dem_df["week"].dropna().unique().tolist())
            if not weeks_sorted:
                return
            start_wk = weeks_sorted[0]
            n_weeks  = len(weeks_sorted)
            self._e_start.set(start_wk)
            self._e_weeks.set(str(n_weeks))
            print(f"[AutoDetect] period: {start_wk}  ×  {n_weeks} weeks")
        except Exception as exc:
            print(f"[AutoDetect] failed: {exc}")

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #

    def _build_config(self) -> WOMConfig:
        scenarios = []
        for n_var, d_var, s_var in self._scenario_rows:
            name = n_var.get().strip()
            if not name:
                continue
            try:
                dm = float(d_var.get())
                sm = float(s_var.get())
            except ValueError:
                dm, sm = 1.0, 1.0
            scenarios.append(ScenarioSpec(name, dm, sm))
        return WOMConfig(
            start_week=self._e_start.get() or "2024-W01",
            num_weeks=int(self._e_weeks.get() or 26),
            safety_stock_weeks=float(self._e_ss.get() or 2.0),
            lead_time_weeks=int(self._e_lt.get() or 4),
            capacity_constrained=self._e_cap.get(),
            scenarios=scenarios or [ScenarioSpec("Base")],
        )

    def _run_simulation(self):
        for attr in ("_f_sku", "_f_dem", "_f_inv", "_f_cap"):
            if not getattr(self, attr).get():
                messagebox.showwarning("Missing Files", f"Please select all 4 input files.")
                return
        self._progress.start(10)
        self._status("Running simulation…")
        t = threading.Thread(target=self._simulate_thread, daemon=True)
        t.start()

    def _simulate_thread(self):
        try:
            config = self._build_config()
            inputs = WOMInputs.from_files(
                sku_master_path=self._f_sku.get(),
                demand_forecast_path=self._f_dem.get(),
                inventory_master_path=self._f_inv.get(),
                capacity_plan_path=self._f_cap.get(),
                weeks=config.weeks,
            )
            self._sim = WOMSimulator(config)
            self._sim.load(inputs)
            self._mgr = self._sim.run(verbose=False)
            self.after(0, self._on_simulation_done)
        except Exception as e:
            import traceback
            self.after(0, lambda: self._on_simulation_error(traceback.format_exc()))

    def _on_simulation_done(self):
        self._progress.stop()
        mgr = self._mgr
        combined = mgr.combined()
        avg_fr = combined[Cols.FILL_RATE].mean()
        total_so = combined[Cols.STOCKOUT_QTY].sum()
        # Money KPI for Base scenario
        money_suffix = ""
        if mgr.scenario_money_kpi is not None:
            base_kpi = mgr.scenario_money_kpi
            base_row = base_kpi[base_kpi[Cols.SCENARIO] == mgr.scenarios()[0]]
            if not base_row.empty:
                rev = float(base_row.iloc[0].get(Cols.REVENUE, 0) or 0)
                gm  = float(base_row.iloc[0].get(Cols.GROSS_MARGIN, 0) or 0)
                ccc = float(base_row.iloc[0].get(Cols.CCC_WKS, 0) or 0)
                money_suffix = (f"  |  Revenue: ${rev:,.0f}  "
                                f"|  Margin: {gm*100:.1f}%  |  CCC: {ccc:.1f}w")
        self._status(
            f"✔ Simulation complete.  "
            f"Scenarios: {len(mgr.scenarios())}  |  "
            f"Avg fill rate: {avg_fr:.1%}  |  "
            f"Total stockout: {total_so:,.0f} units"
            + money_suffix
        )
        # Compute Landed Cost comparison (simulation path)
        try:
            from wom.engine.landed_cost import (
                load_edge_cost_master, load_route_master,
                build_route_index, compare_lc_scenarios)
            edge_path  = self._f_edge_cost.get() if hasattr(self, "_f_edge_cost") else ""
            route_path = self._f_route.get()     if hasattr(self, "_f_route")     else ""
            if (edge_path and os.path.exists(edge_path)
                    and mgr.scenario_money_kpi is not None):
                lc_scens  = load_edge_cost_master(edge_path)
                route_idx = {}
                if route_path and os.path.exists(route_path):
                    route_idx = build_route_index(load_route_master(route_path))
                mgr.lc_comparison_df = compare_lc_scenarios(
                    mgr.scenario_money_kpi, lc_scens, route_idx)
            else:
                mgr.lc_comparison_df = None
        except Exception as _lc_exc:
            print(f"[LandedCost] sim compute failed: {_lc_exc}")

        self._chart_panel.load(mgr)
        self._kpi_panel.load(mgr)
        self._load_risk_tab(mgr)
        self._load_delta_tab(mgr)
        self._mgmt_panel.load(mgr)
        self._network_panel.load(mgr)
        # Load node_master into World Map panel
        node_path = self._f_node.get() if hasattr(self, '_f_node') else ""
        if not node_path:
            # fallback to sample
            node_path = os.path.join(self._sample_dir, "node_master.csv")
        sc_tree_path_wm = self._f_sc_tree.get() if hasattr(self, '_f_sc_tree') else ""
        if not sc_tree_path_wm:
            sc_tree_path_wm = os.path.join(self._sample_dir, "sc_tree_master.csv")
        if not os.path.exists(sc_tree_path_wm):
            sc_tree_path_wm = ""
        if os.path.exists(node_path):
            self._worldmap_panel.load_default(node_path, sc_tree_path_wm)

    def _on_simulation_error(self, tb: str):
        self._progress.stop()
        self._status("Error – see details in dialog.")
        messagebox.showerror("Simulation Error", tb)

    def _load_risk_tab(self, mgr: ScenarioManager):
        risk = mgr.at_risk_skus()
        self._risk_tree.delete(*self._risk_tree.get_children())
        if risk.empty:
            self._risk_tree.insert("", "end",
                values=["No at-risk SKUs detected"] + [""] * 6)
            return
        for _, row in risk.iterrows():
            self._risk_tree.insert("", "end", values=[
                row.get(Cols.SCENARIO, ""),
                row.get(Cols.SKU_ID, ""),
                row.get(Cols.REGION, ""),
                row.get(Cols.WEEK, ""),
                f"{row.get(Cols.FILL_RATE, 0):.1%}",
                f"{row.get(Cols.INV_COVER_WKS, 0):.1f}",
                f"{row.get(Cols.STOCKOUT_QTY, 0):,.0f}",
            ])

    def _load_delta_tab(self, mgr: ScenarioManager):
        self._delta_fig.clf()
        ax = self._delta_fig.add_subplot(111)
        ax.set_facecolor(BG_MID)
        self._delta_fig.patch.set_facecolor(BG_DARK)

        summary = mgr.kpi_summary(by=[Cols.SCENARIO])
        scenarios = summary[Cols.SCENARIO].tolist()
        fill_rates = (summary["avg_fill_rate"] * 100).tolist()
        stockouts  = summary["total_stockout"].tolist()

        x = range(len(scenarios))
        bars = ax.bar(x, fill_rates, color=[
            COLOURS.get(s, DEFAULT_COLOURS[i % len(DEFAULT_COLOURS)])
            for i, s in enumerate(scenarios)
        ], alpha=0.85)
        ax.set_xticks(list(x))
        ax.set_xticklabels(scenarios, color=FG_WHITE)
        ax.set_ylabel("Avg Fill Rate (%)", color=FG_ACC)
        ax.set_title("Scenario Comparison – Fill Rate vs Stockout",
                     color=FG_WHITE, fontsize=11)
        ax.set_ylim(0, 105)
        ax.tick_params(colors=FG_WHITE)
        for spine in ax.spines.values():
            spine.set_edgecolor(BG_LIGHT)

        # Annotate with stockout on second axis
        ax2 = ax.twinx()
        ax2.plot(list(x), stockouts, "o--", color="#FF9800",
                 linewidth=2, markersize=8, label="Total Stockout")
        ax2.set_ylabel("Total Stockout (units)", color="#FF9800")
        ax2.tick_params(colors=FG_WHITE)
        ax2.set_facecolor(BG_MID)

        ax2.legend(facecolor=BG_LIGHT, labelcolor=FG_WHITE, fontsize=9,
                   loc="upper right")
        self._delta_canvas.draw()

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Planning Engine (lot-based PSI, Steps 3-8)
    # ------------------------------------------------------------------ #

    def _build_planning_context(self) -> dict:
        """
        Build the shared planning context (sc_tree, weeks, HookBus, etc.)
        without running any planning operators.

        Called by both _planning_thread (normal run) and DebugPanel (step-by-step).
        Returns a dict with keys:
          sc_tree, weeks, bus, cfg, lane_table, push_path, opening_inv, n_weeks
        """
        import re
        import datetime
        from wom.model.sc_tree       import build_demo_sc_tree
        from wom.model.lot_generator import assign_demand_lots_from_dict
        from wom.engine.lane_assignment import LaneTable
        from wom.engine.hook_bus import HookBus

        # ── Build week labels ───────────────────────────────────────
        n_weeks = int(self._e_weeks.get() or 26)
        start   = self._e_start.get() or "2024-W01"
        m = re.match(r"(\d{4})-W(\d+)", start)
        yr, wk = (int(m.group(1)), int(m.group(2))) if m else (2024, 1)
        weeks, d = [], datetime.date.fromisocalendar(yr, wk, 1)
        for _ in range(n_weeks):
            yr2, wk2, _ = d.isocalendar()
            weeks.append(f"{yr2}-W{wk2:02d}")
            d += datetime.timedelta(weeks=1)

        # ── SKU master ──────────────────────────────────────────────
        sku_path = self._f_sku.get()
        if sku_path and os.path.exists(sku_path):
            sku_df = pd.read_csv(sku_path)
        else:
            sku_df = pd.DataFrame([
                {"sku_id": "SKU-A", "sku_name": "Product A",
                 "region": "JP", "lead_time_wks": 2},
                {"sku_id": "SKU-A", "sku_name": "Product A",
                 "region": "US", "lead_time_wks": 2},
            ])
        if "lead_time_wks" not in sku_df.columns:
            sku_df["lead_time_wks"] = 2

        # ── SC Tree ─────────────────────────────────────────────────
        sc_tree_path = (self._f_sc_tree.get()
                        if hasattr(self, "_f_sc_tree") else "")
        if sc_tree_path:
            self._model_dir = os.path.dirname(sc_tree_path)
            self._node_cost_master = None
        if sc_tree_path and os.path.exists(sc_tree_path):
            try:
                from wom.engine.sc_tree_builder import build_sc_tree_from_master
                sc_tree_df = pd.read_csv(sc_tree_path)
                sc_tree = build_sc_tree_from_master(sc_tree_df, weeks)
                print(f"[SCTreeBuilder] Loaded multi-tier tree from {sc_tree_path}")
                print(f"  Products: {sc_tree.products}")
            except Exception as _stb_exc:
                import traceback
                print(f"[SCTreeBuilder] Failed: {_stb_exc}")
                traceback.print_exc()
                sc_tree = build_demo_sc_tree(sku_df, weeks, lt_wks_ot=1, lt_wks_in=2)
        else:
            sc_tree = build_demo_sc_tree(sku_df, weeks, lt_wks_ot=1, lt_wks_in=2)

        # Request Letter A (request_letter_a_cpu_size_to_plan.md): cpu_size is
        # a plan-wide value read from planning_config.csv, used by the
        # KPI/display conversion layer (sc_tree_to_df.py, chart panels below)
        # ONLY -- see the note by assign_demand_lots_from_dict() just below
        # for why it is deliberately NOT passed into lot generation.
        try:
            from wom.engine.warmup import read_cpu_size
            sc_tree.cpu_size = (read_cpu_size(self._model_dir)
                                if getattr(self, "_model_dir", "") else 1)
        except Exception as _cpu_exc:
            print(f"[cpu_size] read failed: {_cpu_exc}")

        # ── HookBus + active plugins ────────────────────────────────
        _bus = HookBus()
        _cfg = {"n_weeks": n_weeks, "start_week": start,
                "cap_path":         self._f_cap.get()     if hasattr(self, "_f_cap")     else "",
                "holiday_cal_path": self._f_holiday.get() if hasattr(self, "_f_holiday") else ""}
        for _plugin in getattr(self, "_active_plugins", []):
            _plugin.register(_bus)

        # ── Demand ──────────────────────────────────────────────────
        demand_dict = {}
        dem_path = self._f_dem.get()
        if dem_path and os.path.exists(dem_path):
            dem_df = pd.read_csv(dem_path)
            req = {"sku_id", "region", "week", "quantity"}
            if req.issubset(set(dem_df.columns)):
                for _, row in dem_df.iterrows():
                    key = (str(row["sku_id"]), str(row["region"]), str(row["week"]))
                    demand_dict[key] = demand_dict.get(key, 0) + int(row["quantity"])
        if not demand_dict:
            mid = weeks[len(weeks) // 2]
            for sku_id in sc_tree.products:
                for reg in set(sku_df.get("region", pd.Series(["JP"])).tolist()):
                    demand_dict[(sku_id, reg, mid)] = 5
        # cpu_size stays 1 here deliberately (not sc_tree.cpu_size): ceil(qty/cpu_size)
        # would change the LOT COUNT whenever cpu_size != 1, contradicting Letter A
        # section 4.2's requirement that lot count is unchanged when cpu_size goes
        # 1 -> 12 (request_letter_a_cpu_size_to_plan.md).
        assign_demand_lots_from_dict(sc_tree, demand_dict, cpu_size=1)

        # ── Capacity ────────────────────────────────────────────────
        #   単一の共有ローダ（wom/engine/capacity_sealer.load_capacity_dataframe）。
        #   headless runner と同一経路。cap_soft 列は opt-in（無ければ従来どおり
        #   cap_hard のみ設定）。
        cap_path = self._f_cap.get()
        if cap_path and os.path.exists(cap_path):
            try:
                from wom.engine.capacity_sealer import load_capacity_dataframe
                load_capacity_dataframe(sc_tree, pd.read_csv(cap_path), weeks)
            except Exception:
                pass

        # ── Operating calendar (per-node shift plan; Phase 2, opt-in) ─
        #   Set node.op_shifts before BackwardPlanner runs. Looked up in the
        #   same folder as capacity_plan.csv; no file => no-op (always open).
        if cap_path and os.path.exists(cap_path):
            _opcal = os.path.join(os.path.dirname(cap_path), "operating_calendar.csv")
            if os.path.exists(_opcal):
                try:
                    from wom.engine.capacity_sealer import load_operating_calendar
                    load_operating_calendar(sc_tree, pd.read_csv(_opcal), weeks)
                except Exception:
                    pass

        # ── Lane Assignment ─────────────────────────────────────────
        _lane_path = self._f_lane.get() if hasattr(self, "_f_lane") else ""
        _lane_table = (LaneTable.from_csv(_lane_path)
                       if _lane_path and os.path.exists(_lane_path)
                       else LaneTable.empty())

        # ── Push config path ────────────────────────────────────────
        _push_path = self._f_push.get() if hasattr(self, "_f_push") else ""

        # ── Opening inventory (from HarvestBatchPlugin if active) ───
        _harvest_plugin = getattr(self, "_plugin_instances", {}).get("harvest_batch")
        _opening_inv = (
            _harvest_plugin.opening_inv
            if _harvest_plugin is not None
            and self._plugin_vars.get(
                "harvest_batch", __import__("tkinter").BooleanVar(value=False)).get()
            else {}
        )

        return {
            "sc_tree":     sc_tree,
            "weeks":       weeks,
            "n_weeks":     n_weeks,
            "bus":         _bus,
            "cfg":         _cfg,
            "lane_table":  _lane_table,
            "push_path":   _push_path,
            "opening_inv": _opening_inv,
        }

    def _run_planning_engine(self):
        """Build SCTree from input files (or demo data) and run the lot-based planning pipeline."""
        self._progress.start(10)
        self._status("Running Planning Engine (lot-based PSI)…")
        # Build list of active (checked) plugin instances
        self._active_plugins = [
            inst for name, inst in getattr(self, '_plugin_instances', {}).items()
            if self._plugin_vars.get(name, tk.BooleanVar(value=False)).get()
        ]
        threading.Thread(target=self._planning_thread, daemon=True).start()

    def _planning_thread(self):
        try:
            from wom.engine.backward_planner import BackwardPlanner
            from wom.engine.plan_copy        import copy_demand_to_supply
            from wom.engine.forward_planner  import ForwardPlanner
            from wom.engine.hook_bus import (
                HOOK_PRE_PLAN, HOOK_POST_BACKWARD,
                HOOK_POST_COPY, HOOK_POST_FORWARD, HOOK_POST_PLAN)

            # ── Build planning context (sc_tree, weeks, bus, etc.) ─
            ctx        = self._build_planning_context()
            sc_tree    = ctx["sc_tree"]
            weeks      = ctx["weeks"]
            _bus       = ctx["bus"]
            _cfg       = ctx["cfg"]
            _lane_table = ctx["lane_table"]
            _push_path = ctx["push_path"]
            _opening_inv = ctx["opening_inv"]

            # Restore SC hint for planning thread run
            sc_tree_path = self._f_sc_tree.get() if hasattr(self, "_f_sc_tree") else ""
            if sc_tree_path and os.path.exists(sc_tree_path):
                def _reset_sc_hint():
                    if hasattr(self, "_sc_tree_hint_var"):
                        self._sc_tree_hint_var.set("✅ SC Tree Master 使用中")
                        self._sc_tree_hint_lbl.config(fg="#A5D6A7")
                self.after(0, _reset_sc_hint)
            else:
                def _warn_demo_tree():
                    self._status("⚠ SC Tree Master 未指定 — Demo 2-tier tree で実行")
                    if hasattr(self, "_sc_tree_hint_var"):
                        self._sc_tree_hint_var.set("⚠ Demo 2-tier tree 使用中（SC Tree Master 未指定）")
                        self._sc_tree_hint_lbl.config(fg="#FFA726")
                self.after(0, _warn_demo_tree)
            # ── Run planning pipeline ─────────────────────────────
            _bus.fire(HOOK_PRE_PLAN, sc_tree=sc_tree,
                      weeks=weeks, config=_cfg)
            for prod_nm in sc_tree.products:
                BackwardPlanner(sc_tree, lane_table=_lane_table, config=_cfg).run(prod_nm)
                _bus.fire(HOOK_POST_BACKWARD, sc_tree=sc_tree,
                          prod_nm=prod_nm, weeks=weeks, config=_cfg)
                copy_demand_to_supply(sc_tree, prod_nm)
                _bus.fire(HOOK_POST_COPY, sc_tree=sc_tree,
                          prod_nm=prod_nm, weeks=weeks, config=_cfg)
                # Step 8: PUSH/PULL — apply before ForwardPlanner if push_config.csv provided
                _push_path = self._f_push.get() if hasattr(self, "_f_push") else ""
                if not _push_path:
                    print(f"[PushPull] push_config.csv not configured (skip for {prod_nm})")
                elif not os.path.exists(_push_path):
                    print(f"[PushPull] push_config.csv not found: {_push_path}")
                else:
                    import csv as _csv
                    from wom.engine.push_pull import PushProductionPlanner, PushConfig
                    _push_cfgs = {}
                    with open(_push_path, newline="", encoding="utf-8") as _pf:
                        for _pr in _csv.DictReader(_pf):
                            _pn = _pr.get("sku_id", "").strip()
                            if _pn == prod_nm:
                                _push_cfgs[_pn] = PushConfig(
                                    node_id=_pr.get("node_id", "").strip(),
                                    push_qty_per_week=int(_pr.get("push_qty_per_week") or 0),
                                    buffer_lots=int(_pr.get("buffer_lots") or 0),
                                    sku_id=_pn,
                                    mode_only=_pr.get("mode_only", "").strip().lower() == "true",
                                    mom_ref_node_id=_pr.get("mom_ref_node_id", "").strip(),
                                    pre_build_qty_per_week=int(_pr.get("pre_build_qty_per_week") or 0),
                                    pre_build_end_week=_pr.get("pre_build_end_week", "").strip(),
                                    push_lead_time_weeks=int(_pr.get("push_lead_time_weeks") or 0),
                                )
                    if _push_cfgs:
                        print(f"[PushPull] Applying push config for {prod_nm}: {_push_cfgs}")
                        PushProductionPlanner(sc_tree).setup_all(_push_cfgs)
                    else:
                        print(f"[PushPull] push_config.csv loaded but no rows matched sku_id={prod_nm}")
                # Collect opening_inv from HarvestBatchPlugin if active
                _harvest_plugin = getattr(self, '_plugin_instances', {}).get('harvest_batch')
                _opening_inv = (
                    _harvest_plugin.opening_inv
                    if _harvest_plugin is not None
                    and self._plugin_vars.get('harvest_batch',
                        __import__('tkinter').BooleanVar(value=False)).get()
                    else {}
                )
                ForwardPlanner(sc_tree, opening_inv=_opening_inv).run(prod_nm)
                _bus.fire(HOOK_POST_FORWARD, sc_tree=sc_tree,
                          prod_nm=prod_nm, weeks=weeks, config=_cfg)

            _bus.fire(HOOK_POST_PLAN, sc_tree=sc_tree,
                      weeks=weeks, config=_cfg)
            self.after(0, lambda: self._on_planning_done(sc_tree))

        except Exception:
            import traceback
            tb = traceback.format_exc()
            self.after(0, lambda: self._on_planning_error(tb))

    def _on_planning_done(self, sc_tree):
        self._progress.stop()
        n_prods = len(sc_tree.products)
        n_nodes = sum(1 for p in sc_tree.products
                      for _ in sc_tree.iter_all_nodes(p))

        self._network_panel.load_planning_tree(
            sc_tree, model_dir=getattr(self, "_model_dir", ""))

        # -- Build EventTimeline for animation
        try:
            from wom.engine.event_timeline import build_event_timeline
            timeline = build_event_timeline(sc_tree)
            self._network_panel.set_timeline(timeline)
            self._worldmap_panel.set_timeline(timeline)
        except Exception as exc:
            import traceback
            print(f"[EventTimeline] build failed: {exc}")
            traceback.print_exc()

        # -- Load node_master into World Map (same logic as _on_simulation_done)
        try:
            node_path = self._f_node.get() if hasattr(self, "_f_node") else ""
            if not node_path:
                node_path = os.path.join(self._sample_dir, "node_master.csv")
            sc_tree_path_wm = self._f_sc_tree.get() if hasattr(self, "_f_sc_tree") else ""
            if not sc_tree_path_wm:
                sc_tree_path_wm = os.path.join(self._sample_dir, "sc_tree_master.csv")
            if not os.path.exists(sc_tree_path_wm):
                sc_tree_path_wm = ""
            if os.path.exists(node_path):
                self._worldmap_panel.load_default(node_path, sc_tree_path_wm)
        except Exception as _wm_exc:
            print(f"[WorldMap] node load failed: {_wm_exc}")

        # -- Integrate Planning results into KPI/Management tabs
        planning_status = ""
        try:
            from wom.engine.sc_tree_to_df import (
                sc_tree_to_planning_df, apply_inv_value, SCENARIO_PLANNING)
            from wom.engine.money import evaluate_money, build_scenario_money_kpi
            from wom.engine.management import analyze_all_scenarios
            from wom.engine.scenario import ScenarioManager

            # Load sku_master for pricing (cache on self for per-node cost chart)
            sku_path = self._f_sku.get() if hasattr(self, "_f_sku") else ""
            sku_master = (pd.read_csv(sku_path)
                          if sku_path and os.path.exists(sku_path)
                          else pd.DataFrame())
            self._sku_master = sku_master

            # Convert SCTree lots -> quantity DataFrame
            plan_df = sc_tree_to_planning_df(sc_tree,
                                             scenario_name=SCENARIO_PLANNING)
            apply_inv_value(plan_df, sku_master)

            # Merge into existing ScenarioManager (or create one)
            if self._mgr is None:
                self._mgr = ScenarioManager()

            # Remove stale Planning scenario if re-running
            self._mgr._results.pop(SCENARIO_PLANNING, None)
            self._mgr.add(SCENARIO_PLANNING, plan_df)

            # Re-evaluate money KPIs across ALL scenarios
            combined = self._mgr.combined()
            weekly_money, summary_money = evaluate_money(combined, sku_master)
            self._mgr.weekly_money  = weekly_money
            self._mgr.summary_money = summary_money
            scenario_money_kpi = build_scenario_money_kpi(summary_money)
            self._mgr.scenario_money_kpi = scenario_money_kpi

            # Re-run management analysis (only if Base scenario exists)
            if "Base" in self._mgr.scenarios():
                mgmt_results = analyze_all_scenarios(scenario_money_kpi,
                                                     base_scenario="Base")
                self._mgr.management_results = mgmt_results

            # Compute Strategic KPIs from SCTree lots
            try:
                from wom.engine.strategic_kpi import compute_strategic_kpi
                self._mgr.strategic_kpi = compute_strategic_kpi(sc_tree)
            except Exception as _skpi_exc:
                import traceback
                print(f"[StrategicKPI] compute failed: {_skpi_exc}")
                traceback.print_exc()

            # Compute Landed Cost comparison
            try:
                from wom.engine.landed_cost import (
                    load_edge_cost_master, load_route_master,
                    build_route_index, compare_lc_scenarios)
                # Derive model folder from sc_tree_master (ensures rice-japan files used)
                _sc_path = self._f_sc_tree.get() if hasattr(self, "_f_sc_tree") else ""
                _model_dir = os.path.dirname(_sc_path) if _sc_path else ""
                def _resolve_master(attr, fname):
                    if _model_dir:
                        cand = os.path.join(_model_dir, fname)
                        if os.path.exists(cand):
                            return cand
                    widget = getattr(self, attr, None)
                    return widget.get() if widget else ""
                edge_path  = _resolve_master("_f_edge_cost", "edge_cost_master.csv")
                route_path = _resolve_master("_f_route",     "route_master.csv")
                if edge_path and os.path.exists(edge_path):
                    lc_scens = load_edge_cost_master(edge_path)
                    route_idx = {}
                    if route_path and os.path.exists(route_path):
                        route_idx = build_route_index(load_route_master(route_path))
                    self._mgr.lc_comparison_df = compare_lc_scenarios(
                        scenario_money_kpi, lc_scens, route_idx)
                    # Kept so the Management tab's SKU filter can recompute
                    # a per-SKU Landed Cost view without re-running Planning.
                    self._mgr.lc_scens  = lc_scens
                    self._mgr.route_idx = route_idx
                else:
                    self._mgr.lc_comparison_df = None
                    self._mgr.lc_scens  = {}
                    self._mgr.route_idx = {}
            except Exception as _lc_exc:
                print(f"[LandedCost] compute failed: {_lc_exc}")

            # Kept so the Management tab's SKU filter can recompute
            # per-SKU Strategic KPI without re-running Planning.
            self._mgr.sc_tree = sc_tree
            # Phase 2 増分2 (v1r2m0): expose the model folder so the Management
            # tab can read ppc_node_profit_zone.csv (node -> country) for the
            # ledger-sourced Landed Cost tariff sweep.
            self._mgr.model_dir = getattr(self, "_model_dir", "")

            # Reload all KPI panels
            self._chart_panel.load_sc_tree(sc_tree)
            self._chart_panel.load(self._mgr)
            self._kpi_panel.load(self._mgr)
            self._load_risk_tab(self._mgr)
            self._load_delta_tab(self._mgr)
            self._mgmt_panel.load(self._mgr)
            self._network_panel.load(self._mgr)

            # Build status summary for Planning scenario
            p_rows = plan_df
            avg_fr = p_rows[Cols.FILL_RATE].mean() if not p_rows.empty else 0
            total_so = p_rows[Cols.STOCKOUT_QTY].sum() if not p_rows.empty else 0
            planning_status = (f"  |  Planning: fill {avg_fr:.1%}, "
                               f"stockout {total_so:,.0f}")

        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            print(f"[Planning->KPI] integration failed: {exc}")
            print(tb)
            planning_status = "  |  Warning: KPI integration error (see console)"

        self._status(
                        f"Planning Engine complete. "
            f"Products: {n_prods}  |  Nodes: {n_nodes}"
            + planning_status +
            f"  |  Check Charts/KPI/Management tabs for 'Planning' scenario"
        )

        # ── B2: PSI → PPC auto-run ────────────────────────────────────────
        # Launch PPC engine in background using the sc_tree just computed.
        # On completion, refresh the PPC tab automatically.
        self._run_ppc_from_planning(sc_tree)

    def _run_ppc_from_planning(self, sc_tree):
        """
        B2: Trigger PPC simulation from PSI output in a background thread.

        Uses sc_tree.week_labels (the exact week list Planning just used),
        runs run_ppc_from_psi(), then refreshes the PPC tab on the main
        thread.

        NOTE (2028-07-13 fix, found while verifying apparel-global-2028-2029):
        this used to reconstruct the week list from the Planning config
        widgets (self._e_start / self._e_weeks) instead of reading it off
        the sc_tree that was just planned. Those widgets are plain text
        entries the user edits by hand (or an "auto-detect from
        demand_forecast.csv" button elsewhere populates) -- if they still
        held a stale value from a PREVIOUSLY loaded case (e.g. "2026-W01"
        / 26 weeks left over from apparel-us-2026) when a new model with a
        different date range (e.g. apparel-global-2028-2029's 2028-2029)
        was loaded and planned, PPC would silently run against a week
        range that shares no overlap with the actual PSI data just
        computed -- producing 0 lots / 0 revenue with no error, since
        run_ppc_from_psi() just finds no matching records rather than
        raising. sc_tree.week_labels is the single source of truth for
        "which weeks did Planning actually just run" and was already
        available here (it's the same sc_tree used for the KPI panels
        immediately above), so there is no reason to re-derive it from a
        separate, independently-editable widget.
        """
        weeks = list(sc_tree.week_labels)
        if not weeks:
            print("[PPC B2] sc_tree.week_labels is empty; aborting PPC run")
            return

        self._status_var.set(
            self._status_var.get() + "  |  💰 Running PPC …"
        )

        # モデルフォルダ内に ppc_market_price.csv があればそちらを優先
        _model_ppc_dir = getattr(self, "_model_dir", "")
        _ppc_data_dir = "data/ppc"
        if _model_ppc_dir and os.path.exists(
            os.path.join(_model_ppc_dir, "ppc_market_price.csv")
        ):
            _ppc_data_dir = _model_ppc_dir
            print(f"[PPC B2] Using model-local PPC rules: {_ppc_data_dir}")

        # base_currency: auto-detected from the model-local ppc_fx_rate.csv's
        # own base_currency column, so each scenario can choose its reporting
        # currency (e.g. apparel-us-2026 = USD) via data, not code.
        # Falls back to "JPY" (previous hardcoded default) when the file is
        # absent, empty, or ambiguous, preserving existing Cookie/EV/oil
        # sample behavior unchanged.
        _base_currency = "JPY"
        try:
            _fx_path = os.path.join(_ppc_data_dir, "ppc_fx_rate.csv")
            if os.path.exists(_fx_path):
                import pandas as _pd
                _fx_df = _pd.read_csv(_fx_path, dtype=str)
                _bc_values = _fx_df["base_currency"].dropna().unique()
                if len(_bc_values) == 1:
                    _base_currency = str(_bc_values[0])
                elif len(_bc_values) > 1:
                    print(
                        f"[PPC B2] Multiple base_currency values in ppc_fx_rate.csv: "
                        f"{list(_bc_values)}; using '{_base_currency}' fallback"
                    )
        except Exception as _exc:
            print(f"[PPC B2] base_currency auto-detect failed: {_exc}; using '{_base_currency}' fallback")

        def _ppc_thread():
            try:
                from wom.ppc.ppc_runner import run_ppc_from_psi
                kpi = run_ppc_from_psi(
                    sc_tree=sc_tree,
                    weeks=weeks,
                    data_dir=_ppc_data_dir,
                    output_dir="output/ppc",
                    base_currency=_base_currency,
                    verbose=True,
                    use_node_name=(_ppc_data_dir != "data/ppc"),
                )
                self.after(0, lambda: self._on_ppc_done(kpi))
            except Exception as _exc:
                import traceback
                _tb = traceback.format_exc()
                print(f"[PPC B2] engine failed:\n{_tb}")
                self.after(0, lambda e=_exc: self._on_ppc_error(str(e)))

        threading.Thread(target=_ppc_thread, daemon=True).start()

    def _on_ppc_done(self, kpi: dict):
        """Called on main thread after PPC engine completes."""
        margin = kpi.get("gross_margin_pct", 0.0)
        lots   = kpi.get("total_lots", 0)
        psi_mode = kpi.get("_psi_mode", False)
        mode_label = "PSI-linked" if psi_mode else "sample data"
        self._status(
            f"💰 PPC complete ({mode_label}) — "
            f"Lots: {lots:,}  Margin: {margin:.1%}  "
            f"| PPC tab refreshed"
        )
        # Refresh the PPC tab with newly written output/ppc/ files
        if hasattr(self, "_ppc_panel"):
            self._ppc_panel.refresh(output_dir="output/ppc")
        # Node P&L (拠点別損益) table lives on the Management tab but is
        # sourced from the same output/ppc/ppc_node_pl_summary.csv file
        if hasattr(self, "_mgmt_panel"):
            self._mgmt_panel.refresh_node_pl(output_dir="output/ppc")

    def _on_ppc_error(self, msg: str):
        """Called on main thread if PPC engine fails (non-fatal)."""
        print(f"[PPC B2] Non-fatal error: {msg}")
        self._status(
            self._status_var.get().replace("  |  💰 Running PPC …", "") +
            "  |  ⚠ PPC engine error (see console)"
        )

    def _on_planning_error(self, tb: str):
        self._progress.stop()
        self._status_var.set("Planning Engine failed -- see console")
        import tkinter.messagebox as _mb
        _mb.showerror("Planning Engine Error",
                      f"Planning Engine failed:\n\n{tb[:1200]}")

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #

    def _export_csv(self):
        if not self._mgr:
            import tkinter.messagebox as _mb
            _mb.showinfo("No Results", "Run the simulation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Results to CSV",
        )
        if not path:
            return
        try:
            self._mgr.combined().to_csv(path, index=False)
            self._status_var.set(f"Exported: {path}")
        except Exception as exc:
            import tkinter.messagebox as _mb
            _mb.showerror("Export Error", str(exc))

    def _export_excel(self):
        if not self._mgr:
            import tkinter.messagebox as _mb
            _mb.showinfo("No Results", "Run the simulation first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            title="Export Results to Excel",
        )
        if not path:
            return
        try:
            from wom.reports.output import write_excel
            out_dir = os.path.dirname(path)
            out_path = write_excel(self._mgr, out_dir)
            self._status_var.set(f"Excel exported: {out_path}")
        except Exception as exc:
            import tkinter.messagebox as _mb
            _mb.showerror("Export Error", str(exc))

    # ------------------------------------------------------------------ #
    # Status helper
    # ------------------------------------------------------------------ #

    def _status(self, msg: str) -> None:
        self._status_var.set(msg)

# ======================================================================
# Entry point
# ======================================================================

def launch():
    """Entry point called by main.py."""
    WOMApp().mainloop()
