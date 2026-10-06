# -*- coding: utf-8 -*-
"""
🗺 World Map タブ（RequestLetter_WorldMap_ActualFlows）

地図は手元の Natural Earth のデータ（data/worldmap_ne/ne_*.npz）を matplotlib で描く。
実行時にネットワークへ出ない（tkintermapview も地図の画像も使わない）。

- 拠点：node_master.csv の緯度・経度。supply point は仮想のノード（中抜きのひし形）。
- 区間：物理の区間だけ（supply point を通さない）。計画の前は sc_tree_master.csv から静止した線。
- 流れ：Run Planning Engine の後、その計画の**実出荷**（段階 D の出荷の記録）から。
  表示は「出荷」（その週に出た lot 数）と「輸送中」（週の終わりに区間の上にある lot 数）。
  線の太さの基準は計画の全期間の最大で固定。
- 表示しているのは今のモデル・今の計画の流れだけ（計画 ID が違う結果は出さない）。

流れの計算は wom/worldmap_ne/flows.py、地図データは wom/worldmap_ne/data.py。
"""
from __future__ import annotations

import os
import time
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Tuple

import numpy as np
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from wom.worldmap_ne.data import NEMap, choose_lod, merc_y
from wom.worldmap_ne.flows import MapLayout, FlowData, NODE_STYLE, report_start_index

BG_DARK, BG_MID, BG_LIGHT = "#1E2A38", "#253347", "#2E3F55"
FG_WHITE, FG_ACC = "#ECEFF1", "#64B5F6"

C_OCEAN = "#D6E6EE"
C_LAND = "#F4F1EA"
C_COAST = "#8FA9B8"
C_BORDER = "#B8AFA0"
C_EDGE_STATIC = "#78909C"
C_FLOW_OUT = np.array([0.118, 0.533, 0.898])      # #1E88E5  OutBound
C_FLOW_IN = np.array([0.263, 0.627, 0.278])       # #43A047  InBound
C_CO = "#E53935"

WORLD = (-180.0, -58.0, 180.0, 78.0)
# Japanese names on the map (the same family as app.py's rcParams, given here so the panel
# does not depend on the app having set it)
FONT = ["Yu Gothic", "Meiryo", "MS Gothic", "DejaVu Sans"]
SPEEDS = ("250", "500", "1000", "2000")
MODE_SHIP, MODE_TRANSIT = "ship", "transit"
ALL = "All"

# label priority (lower = placed first when labels would overlap)
_LABEL_RANK = {"mom": 0, "dad": 1, "leaf_out": 2, "leaf_in": 3, "stockyard": 4, "supply_point": 5}


def _xy_box(lon0, lat0, lon1, lat1):
    return lon0, float(merc_y(lat0)), lon1, float(merc_y(lat1))


def _split_dateline(x0, y0, x1, y1) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """A straight segment, or two when the short way crosses the 180 deg line (e.g. Asia ->
    America across the Pacific): each part runs to the map's edge."""
    dx = x1 - x0
    if abs(dx) <= 180.0:
        return [((x0, y0), (x1, y1))]
    x1u = x1 - 360.0 if dx > 0 else x1 + 360.0      # x1 moved next to x0
    edge = -180.0 if dx > 0 else 180.0
    t = (edge - x0) / (x1u - x0)
    ym = y0 + t * (y1 - y0)
    return [((x0, y0), (edge, ym)), ((-edge, ym), (x1, y1))]


class WorldMapPanel(tk.Frame):
    """The World Map tab. The app calls load_default / set_current_plan / begin_flows /
    set_flows / clear_flows."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self.nemap = NEMap()
        self.layout: Optional[MapLayout] = None
        self.flows: Optional[FlowData] = None
        self.model_dir = ""
        self._current_run_id = ""
        self._report_idx = 0
        self._report_src = ""
        self._week = 0
        self._playing = False
        self._after = None
        self._bg = None
        self._view = None
        self._cull_view = None
        self._lod = None
        self._drag = None
        self._pick = None                  # ("node", id) / ("edge", k)
        self._week_ms: List[float] = []
        self._slider_lock = False
        self._resize_after = None
        self._sel = None                   # the arrays of the current SKU selection
        self._segs: list = []
        self._seg_edge = np.zeros(0, dtype=int)
        self._seg_base = np.zeros((0, 3))
        self._geo: list = []
        self._geo_members: list = []
        self._node_ids: List[str] = []
        self._node_idx: Dict[str, int] = {}
        self._plain_ids: List[str] = []
        self._build()
        self._set_band("モデルを読み込むと拠点と区間を描きます")

    # ══ UI ═══════════════════════════════════════════════════════════
    def _build(self):
        self._band_var = tk.StringVar()
        band = tk.Label(self, textvariable=self._band_var, bg=BG_DARK, fg="#FFD740", anchor="w",
                        justify="left", font=("Segoe UI", 9, "bold"), wraplength=1000)
        band.pack(fill="x", padx=8, pady=(4, 0))
        self.bind("<Configure>", lambda e: band.configure(wraplength=max(400, e.width - 24)), add="+")

        bar = tk.Frame(self, bg=BG_MID, pady=3)
        bar.pack(fill="x")
        lab = dict(bg=BG_MID, fg=FG_WHITE, font=("Segoe UI", 9))
        tk.Label(bar, text="SKU:", **lab).pack(side="left", padx=(8, 2))
        self._sku_var = tk.StringVar(value=ALL)
        self._sku_cb = ttk.Combobox(bar, textvariable=self._sku_var, values=[ALL], width=18,
                                    state="readonly", font=("Segoe UI", 8))
        self._sku_cb.pack(side="left")
        self._sku_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_selection())
        tk.Label(bar, text="  表示:", **lab).pack(side="left")
        self._mode_var = tk.StringVar(value=MODE_SHIP)
        for v, t in ((MODE_SHIP, "出荷"), (MODE_TRANSIT, "輸送中")):
            tk.Radiobutton(bar, text=t, value=v, variable=self._mode_var, command=self._on_mode,
                           bg=BG_MID, fg=FG_WHITE, selectcolor=BG_LIGHT, activebackground=BG_MID,
                           font=("Segoe UI", 9)).pack(side="left")
        self._handoff_var = tk.BooleanVar(value=False)
        tk.Checkbutton(bar, text="MOM→supply point（仮想の受け渡し）", variable=self._handoff_var,
                       command=self._on_selection, bg=BG_MID, fg=FG_WHITE, selectcolor=BG_LIGHT,
                       activebackground=BG_MID, font=("Segoe UI", 8)).pack(side="left", padx=6)
        btn = dict(bg=BG_LIGHT, fg=FG_WHITE, relief="flat", font=("Segoe UI", 8))
        tk.Button(bar, text="World", command=lambda: self.go("World"), **btn).pack(side="left", padx=2)
        tk.Button(bar, text="拠点の範囲", command=lambda: self.go("Nodes"), **btn).pack(side="left", padx=2)
        self._btn_missing = tk.Button(bar, text="座標なし —", command=self._show_missing,
                                      bg=BG_LIGHT, fg="#FFAB91", relief="flat", font=("Segoe UI", 8))
        self._btn_missing.pack(side="right", padx=6)

        wk = tk.Frame(self, bg=BG_MID, pady=2)
        wk.pack(fill="x")
        b = dict(width=3, relief="flat", font=("Segoe UI", 9), state="disabled")
        self._btn_play = tk.Button(wk, text="▶", command=self.play, bg="#1B5E20", fg="white", **b)
        self._btn_pause = tk.Button(wk, text="⏸", command=self.pause, bg=BG_LIGHT, fg=FG_WHITE, **b)
        self._btn_stop = tk.Button(wk, text="⏹", command=self.stop, bg=BG_LIGHT, fg=FG_WHITE, **b)
        for x in (self._btn_play, self._btn_pause, self._btn_stop):
            x.pack(side="left", padx=(6 if x is self._btn_play else 2, 2))
        self._slider_var = tk.DoubleVar(value=0)
        self._slider = ttk.Scale(wk, from_=0, to=1, orient="horizontal", variable=self._slider_var,
                                 command=self._on_slider, length=420, state="disabled")
        self._slider.pack(side="left", padx=8)
        self._week_var = tk.StringVar(value="—")
        tk.Label(wk, textvariable=self._week_var, bg=BG_MID, fg=FG_ACC, width=26, anchor="w",
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(wk, text="1 週 =", **lab).pack(side="left", padx=(8, 2))
        self._speed_var = tk.StringVar(value="1000")
        ttk.Combobox(wk, textvariable=self._speed_var, values=SPEEDS, width=5, state="readonly",
                     font=("Segoe UI", 8)).pack(side="left")
        tk.Label(wk, text="ms", **lab).pack(side="left", padx=(2, 8))
        self._perf_var = tk.StringVar(value="")
        tk.Label(wk, textvariable=self._perf_var, bg=BG_MID, fg="#90A4AE",
                 font=("Segoe UI", 8)).pack(side="left")

        paned = tk.PanedWindow(self, orient="horizontal", bg=BG_DARK, sashwidth=5)
        paned.pack(fill="both", expand=True)
        mapf = tk.Frame(paned, bg=BG_DARK)
        paned.add(mapf, minsize=640, stretch="always")
        side = tk.Frame(paned, bg=BG_DARK)
        paned.add(side, minsize=230)

        self.fig = Figure(facecolor=C_OCEAN)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        ax = self.ax
        ax.set_facecolor(C_OCEAN)
        ax.set_axis_off()
        ax.set_aspect("equal", adjustable="datalim")
        self.a_land = PolyCollection([], facecolors=C_LAND, edgecolors="none", zorder=1)
        self.a_coast = LineCollection([], colors=C_COAST, linewidths=0.6, zorder=2)
        self.a_border = LineCollection([], colors=C_BORDER, linewidths=0.5, linestyles="--", zorder=2)
        self.a_static = LineCollection([], colors=C_EDGE_STATIC, linewidths=1.2, alpha=0.55, zorder=3)
        self.a_handoff = LineCollection([], colors="#7E57C2", linewidths=0.9, linestyles=":", zorder=3)
        self.a_flow = LineCollection([], linewidths=0, zorder=4, capstyle="round")
        for a in (self.a_land, self.a_coast, self.a_border, self.a_static, self.a_handoff, self.a_flow):
            ax.add_collection(a)
        self.a_sp = ax.scatter([], [], s=70, marker="D", facecolors="none", edgecolors="#4527A0",
                               linewidths=1.6, zorder=5)
        self.a_nodes = ax.scatter([], [], s=30, zorder=6, edgecolors="white", linewidths=0.8)
        self.a_co = ax.scatter([], [], s=200, facecolors="none", edgecolors=C_CO, linewidths=2.0, zorder=7)
        self.a_week = ax.text(0.01, 0.99, "", transform=ax.transAxes, va="top", ha="left", fontsize=10, fontfamily=FONT,
                              color="#263238", zorder=9,
                              bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.85))
        self._labels: Dict[str, object] = {}
        self._sales_txt: Dict[str, object] = {}
        self._animated = [self.a_flow, self.a_nodes, self.a_co, self.a_week]
        for a in self._animated:
            a.set_animated(True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=mapf)
        w = self.canvas.get_tk_widget()
        w.pack(fill="both", expand=True)
        self.canvas.mpl_connect("draw_event", self._on_draw)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        w.bind("<Configure>", self._on_resize, add="+")

        tk.Label(side, text="拠点・区間の情報（押すと出ます）", bg=BG_DARK, fg=FG_ACC,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
        self._info = tk.Text(side, bg=BG_MID, fg=FG_WHITE, font=("Segoe UI", 9), relief="flat",
                             wrap="word", state="disabled", width=34)
        self._info.pack(fill="both", expand=True, padx=6, pady=4)
        leg = tk.LabelFrame(side, text=" 凡例 ", bg=BG_DARK, fg=FG_ACC, font=("Segoe UI", 8, "bold"))
        leg.pack(fill="x", padx=6, pady=4)
        for key, txt in (("procurement", "Procurement"), ("mother_plant", "Mother plant (MOM)"),
                         ("sku_supplier", "Supplier"), ("region_dc", "DC"), ("marketing", "Market")):
            r = tk.Frame(leg, bg=BG_DARK)
            r.pack(fill="x", padx=4)
            tk.Label(r, text="●", fg=NODE_STYLE[key][0], bg=BG_DARK).pack(side="left")
            tk.Label(r, text=txt, bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 8)).pack(side="left")
        for sym, col, txt in (("◇", "#B39DDB", "supply point（仮想のノード）"),
                              ("━", "#1E88E5", "OutBound の流れ"), ("━", "#43A047", "InBound の流れ"),
                              ("○", C_CO, "注文残（CO）のある市場")):
            r = tk.Frame(leg, bg=BG_DARK)
            r.pack(fill="x", padx=4)
            tk.Label(r, text=sym, fg=col, bg=BG_DARK).pack(side="left")
            tk.Label(r, text=txt, bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 8)).pack(side="left")
        tk.Label(side, text="線の太さ：計画の全期間の最大を基準に固定\n拠点の大きさ：その週の在庫（I）\n"
                            "市場の数字：その週の販売の lot 数", bg=BG_DARK, fg="#90A4AE", justify="left",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(0, 6))

    def _set_band(self, msg: str) -> None:
        self._band_var.set(f"World Map（Natural Earth・手元のデータだけ）　｜　{msg}")

    def _set_info(self, text: str) -> None:
        self._info.config(state="normal")
        self._info.delete("1.0", "end")
        self._info.insert("end", text)
        self._info.config(state="disabled")

    def _controls(self, enabled: bool) -> None:
        st = "normal" if enabled else "disabled"
        for x in (self._btn_play, self._btn_pause, self._btn_stop):
            x.config(state=st)
        self._slider.config(state=st)

    # ══ app API ══════════════════════════════════════════════════════
    def load_default(self, csv_path: str, sc_tree_path: str = "") -> None:
        """Load the model's node_master.csv (+ sc_tree_master.csv from the same folder)."""
        model_dir = os.path.dirname(os.path.abspath(csv_path))
        same = model_dir == self.model_dir and self.layout is not None
        self.model_dir = model_dir
        try:
            self.layout = MapLayout.load(model_dir)
        except Exception as exc:
            self.layout = None
            self._set_band(f"拠点を読めませんでした：{exc}")
            return
        values = [ALL] + self.layout.products
        self._sku_cb["values"] = values
        if self._sku_var.get() not in values:
            self._sku_var.set(ALL)
        nm = len(self.layout.missing_coords)
        npl = len(self.layout.placed_at_parent)
        self._btn_missing.config(text=f"座標なし {nm}" + (f"・描けない区間 {len(self.layout.undrawable_edges)}"
                                                          if self.layout.undrawable_edges else "")
                                 + (f"・親の位置 {npl}" if npl else ""))
        if self.flows is None:
            self._set_band(f"{os.path.basename(model_dir)}：拠点 {len(self.layout.nodes)}・区間 "
                           f"{len(self.layout.edges)}　｜　Run Planning Engine の後、その計画の実出荷で流れを動かします")
        self.nemap.load(["110m"])
        self._on_selection(fit=not same)

    def set_current_plan(self, run_id: str) -> None:
        """The plan on the screen. Flows of another plan are never shown."""
        self._current_run_id = run_id or ""
        if self.flows is not None and self.flows.plan_id != self._current_run_id:
            self.clear_flows("今の計画の流れではありません（作り直しています）")

    def begin_flows(self, run_id: str) -> None:
        self.set_current_plan(run_id)
        self.clear_flows("出荷の記録を作成中…（今の計画の実出荷から。地図と静止した線は使えます）")

    def set_flows(self, run_id: str, flows: Optional[FlowData], problem: Optional[str] = None) -> bool:
        if run_id != self._current_run_id:
            print(f"[WorldMap] flows of an older plan ignored ({run_id})")
            return False
        if flows is None or problem:
            self.clear_flows(f"流れを出しません：{problem or '出荷の記録がありません'}")
            return False
        self.flows = flows
        n = len(flows.week_labels)
        self._report_idx, self._report_src = report_start_index(self.model_dir, flows.week_labels)
        self._slider.config(to=max(n - 1, 1))
        mode = f"　｜　lot_flow_mode {flows.lot_flow_mode}" if flows.lot_flow_mode else ""
        self._set_band(f"計画 ID：{flows.plan_id}　｜　流れ：実出荷（出荷の記録 {flows.n_shipments:,} 件）"
                       f"　｜　報告の開始週 {flows.week_labels[self._report_idx]}（{self._report_src}）{mode}")
        self._controls(True)
        self._btn_pause.config(state="disabled")
        self._week = self._report_idx
        self._on_selection(fit=False)
        return True

    def clear_flows(self, message: str = "") -> None:
        self.pause()
        self.flows = None
        self._sel = None
        self._week = 0
        self._controls(False)
        self._week_var.set("—")
        self._perf_var.set("")
        self._pick = None
        if message:
            self._set_band(message)
        if self.layout is not None:
            self._on_selection(fit=False)

    # compatibility with the app's model-change hook
    def clear_timeline(self) -> None:
        self._current_run_id = ""
        self.clear_flows("モデルを読み込みました → Run Planning Engine の後、その計画の実出荷で流れを動かします")

    # ══ selection (SKU) → static artists + the arrays to animate ═════
    def _selected_products(self) -> List[str]:
        v = self._sku_var.get()
        return list(self.layout.products) if v == ALL else [v]

    def _on_selection(self, fit: bool = False) -> None:
        L = self.layout
        if L is None:
            return
        prods = set(self._selected_products())
        sku = self._sku_var.get()
        if sku == ALL:
            node_ids = list(L.nodes)
        else:
            node_ids = [n for n in L.nodes if n in L.tree_nodes.get(sku, set())]
        self._node_ids = node_ids
        self._node_idx = {n: i for i, n in enumerate(node_ids)}
        nodes = [L.nodes[n] for n in node_ids]
        # geographic edges of the selection (one line per A->B; products summed)
        geo: Dict[Tuple[str, str], int] = {}
        geo_side: List[str] = []
        geo_members: List[List[Tuple[str, str]]] = []
        for e in L.edges:
            if e.product not in prods:
                continue
            k = geo.setdefault((e.a, e.b), len(geo))
            if k == len(geo_side):
                geo_side.append(e.side)
                geo_members.append([])
            geo_members[k].append((e.product, e.edge))
        self._geo = list(geo)
        self._geo_members = geo_members
        segs, seg_edge = [], []
        for k, (a, b) in enumerate(self._geo):
            na, nb = L.nodes[a], L.nodes[b]
            for s in _split_dateline(na.x, na.y, nb.x, nb.y):
                segs.append(s)
                seg_edge.append(k)
        self._seg_edge = np.array(seg_edge, dtype=int)
        self._segs = segs
        self._seg_base = np.array([C_FLOW_IN if geo_side[k] == "in" else C_FLOW_OUT for k in seg_edge]) \
            if seg_edge else np.zeros((0, 3))
        self.a_static.set_segments(segs)
        self.a_flow.set_segments(segs)
        hsegs = []
        if self._handoff_var.get():
            for e in L.handoff:
                if e.product in prods:
                    na, nb = L.nodes[e.a], L.nodes[e.b]
                    hsegs += _split_dateline(na.x, na.y, nb.x, nb.y)
        self.a_handoff.set_segments(hsegs)

        plain = [n for n in nodes if not n.is_supply_point]
        sps = [n for n in nodes if n.is_supply_point]
        self._plain_ids = [n.node_id for n in plain]
        self.a_nodes.set_offsets(np.array([[n.x, n.y] for n in plain]) if plain else np.zeros((0, 2)))
        self.a_nodes.set_facecolors([n.colour for n in plain] or ["#000"])
        self.a_nodes.set_sizes(np.full(len(plain), 34.0))
        self.a_sp.set_offsets(np.array([[n.x, n.y] for n in sps]) if sps else np.zeros((0, 2)))
        self.a_co.set_offsets(np.zeros((0, 2)))

        for t in list(self._labels.values()) + list(self._sales_txt.values()):
            t.remove()
        self._labels, self._sales_txt = {}, {}
        for n in nodes:
            self._labels[n.node_id] = self.ax.text(
                n.x, n.y, f"  {n.name}", fontsize=7.5, fontfamily=FONT, color="#263238", va="center", ha="left",
                zorder=8, clip_on=True)
            if n.is_market:
                t = self.ax.text(n.x, n.y, "", fontsize=8, fontfamily=FONT, color="#B71C1C", fontweight="bold",
                                 va="top", ha="center", zorder=9, clip_on=True)
                t.set_animated(True)
                self._sales_txt[n.node_id] = t
        self._animated = [self.a_flow, self.a_nodes, self.a_co, self.a_week] + list(self._sales_txt.values())

        self._prepare_arrays(prods)
        if fit or self._view is None:
            self.go("Nodes", draw=False)
        else:
            x0, y0, x1, y1 = self._view
            self.set_view(x0, y0, x1, y1, draw=False)
        self._apply_week(self._week)
        self.full_draw()

    def _prepare_arrays(self, prods) -> None:
        F = self.flows
        if F is None:
            self._sel = None
            self.a_static.set_linewidths(1.4)
            self.a_static.set_alpha(0.75)
            return
        self.a_static.set_linewidths(0.8)
        self.a_static.set_alpha(0.45)
        col = {k: i for i, k in enumerate(F.edge_keys)}
        n_w, n_g = len(F.week_labels), len(self._geo)
        ship = np.zeros((n_w, n_g), dtype=np.int64)
        trans = np.zeros((n_w, n_g), dtype=np.int64)
        for g, members in enumerate(self._geo_members):
            for m in members:
                i = col.get(m)
                if i is not None:
                    ship[:, g] += F.ship[:, i]
                    trans[:, g] += F.transit[:, i]
        nidx = {k: i for i, k in enumerate(F.node_keys)}
        n_n = len(self._node_ids)
        psi = np.zeros((n_w, n_n, 4), dtype=np.int64)
        sales = np.zeros((n_w, n_n), dtype=np.int64)
        for j, nid in enumerate(self._node_ids):
            for p in prods:
                i = nidx.get((p, nid))
                if i is not None:
                    psi[:, j] += F.psi[:, i]
                    sales[:, j] += F.sales[:, i]
        plain_j = [self._node_idx[n] for n in self._plain_ids]
        self._sel = {"ship": ship, "transit": trans, "psi": psi, "sales": sales, "plain_j": plain_j,
                     "max": {MODE_SHIP: max(int(ship.max()) if ship.size else 0, 1),
                             MODE_TRANSIT: max(int(trans.max()) if trans.size else 0, 1)},
                     "imax": max(int(psi[:, plain_j, 2].max()) if psi.size and plain_j else 0, 1)}

    # ══ weeks ════════════════════════════════════════════════════════
    def _apply_week(self, w: int) -> None:
        S = self._sel
        F = self.flows
        if S is None or F is None:
            self.a_flow.set_linewidths(np.zeros(len(self._segs)))
            self.a_co.set_offsets(np.zeros((0, 2)))
            for t in self._sales_txt.values():
                t.set_text("")
            self.a_week.set_text(os.path.basename(self.model_dir) if self.model_dir else "")
            return
        n = len(F.week_labels)
        w = max(0, min(int(w), n - 1))
        self._week = w
        mode = self._mode_var.get()
        vals = S[mode][w].astype(float)
        r = vals / S["max"][mode]
        rs = r[self._seg_edge] if len(self._seg_edge) else r[:0]
        on = rs > 0
        self.a_flow.set_linewidths(np.where(on, 1.0 + 8.0 * rs, 0.0))
        rgba = np.zeros((len(rs), 4))
        if len(rs):
            rgba[:, :3] = self._seg_base
            rgba[:, 3] = np.where(on, 0.35 + 0.65 * rs, 0.0)
        self.a_flow.set_color(rgba)
        pj = S["plain_j"]
        inv = S["psi"][w, pj, 2].astype(float) if pj else np.zeros(0)
        self.a_nodes.set_sizes(28.0 + 320.0 * inv / S["imax"])
        co_xy = []
        for nid, t in self._sales_txt.items():
            j = self._node_idx[nid]
            s = int(S["sales"][w, j])
            t.set_text(f"{s:,}" if s else "")
            if S["psi"][w, j, 1] > 0:
                nd = self.layout.nodes[nid]
                co_xy.append((nd.x, nd.y))
        self.a_co.set_offsets(np.array(co_xy) if co_xy else np.zeros((0, 2)))
        phase = "報告" if w >= self._report_idx else "助走"
        label = f"{F.week_labels[w]}（{phase}）"
        self.a_week.set_text(f"{label}  {w + 1}/{n}　{'出荷' if mode == MODE_SHIP else '輸送中'}")
        self._week_var.set(f"{label}  {w + 1}/{n}")
        if not self._slider_lock:
            self._slider_lock = True
            self._slider_var.set(w)
            self._slider_lock = False
        if self._pick is not None:
            self._show_pick()

    def set_week(self, w: int) -> float:
        """Show week w; returns the ms it took (update + drawing on the screen)."""
        t0 = time.perf_counter()
        self._apply_week(w)
        if self._bg is not None:
            self.canvas.restore_region(self._bg)
            for a in self._animated:
                self.ax.draw_artist(a)
            self.canvas.blit(self.fig.bbox)
        else:
            self.canvas.draw()
        self.update_idletasks()
        ms = (time.perf_counter() - t0) * 1000.0
        self._week_ms = (self._week_ms + [ms])[-50:]
        self._perf_var.set(f"描画 {np.median(self._week_ms):.1f} ms/週（中央値）")
        return ms

    def _on_slider(self, _v=None):
        if self._slider_lock or self.flows is None:
            return
        w = int(round(self._slider_var.get()))
        if w != self._week:
            self._slider_lock = True
            self.set_week(w)
            self._slider_lock = False

    def _on_mode(self):
        if self.flows is not None:
            self.set_week(self._week)

    def play(self):
        if self.flows is None or self._playing:
            return
        self._playing = True
        self._btn_play.config(state="disabled")
        self._btn_pause.config(state="normal")
        self._tick()

    def pause(self):
        self._playing = False
        if self._after:
            try:
                self.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        if self.flows is not None:
            self._btn_play.config(state="normal")
            self._btn_pause.config(state="disabled")

    def stop(self):
        self.pause()
        if self.flows is not None:
            self.set_week(self._report_idx)

    def _tick(self):
        if not self._playing or self.flows is None:
            return
        n = len(self.flows.week_labels)
        self.set_week((self._week + 1) % n)
        try:
            ms = int(self._speed_var.get())
        except ValueError:
            ms = 1000
        self._after = self.after(ms, self._tick)

    # ══ view ═════════════════════════════════════════════════════════
    def go(self, name: str, draw: bool = True) -> None:
        if name == "World" or self.layout is None:
            box = _xy_box(*WORLD)
        else:
            box = self.layout.extent(getattr(self, "_node_ids", None))
        self.set_view(*box, draw=draw)

    def set_view(self, x0, y0, x1, y1, draw: bool = True) -> dict:
        t0 = time.perf_counter()
        ax = self.ax
        bb = ax.bbox
        if bb.width > 1 and bb.height > 1:
            pa = bb.height / bb.width
            w, h = x1 - x0, y1 - y0
            if h < w * pa:
                cy = (y0 + y1) / 2
                y0, y1 = cy - w * pa / 2, cy + w * pa / 2
            else:
                cx = (x0 + x1) / 2
                x0, x1 = cx - h / pa / 2, cx + h / pa / 2
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.apply_aspect()
        vx0, vx1 = ax.get_xlim()
        vy0, vy1 = ax.get_ylim()
        self._view = (vx0, vy0, vx1, vy1)
        lod = choose_lod(vx1 - vx0, ax.bbox.width)
        self._recull(lod, force=True)
        self._declutter_labels()
        out = {"lod": lod, "cull_ms": (time.perf_counter() - t0) * 1000.0}
        if draw:
            out["draw_ms"] = self.full_draw()
        return out

    def _recull(self, lod: str, force: bool = False) -> None:
        vx0, vy0, vx1, vy1 = self._view
        w, h = vx1 - vx0, vy1 - vy0
        if not force and self._cull_view is not None and self._lod == lod:
            cx0, cy0, cx1, cy1 = self._cull_view
            if cx0 <= vx0 and cy0 <= vy0 and cx1 >= vx1 and cy1 >= vy1:
                return
        if not self.nemap.has(lod):
            self.nemap.load([lod])
        cull = (vx0 - w / 2, vy0 - h / 2, vx1 + w / 2, vy1 + h / 2)
        view = None if w >= 300 else cull
        self.a_coast.set_segments(self.nemap.lines(lod, "coast", view))
        self.a_border.set_segments(self.nemap.lines(lod, "border", view))
        self.a_land.set_verts(self.nemap.land(lod, view))
        self._cull_view, self._lod = cull, lod

    def _declutter_labels(self) -> None:
        """Show as many names as fit without overlapping (MOM and DC first)."""
        if not self._labels or self.layout is None:
            return
        tr = self.ax.transData
        x0, y0, x1, y1 = self._view
        placed: List[Tuple[float, float, float, float]] = []
        order = sorted(self._labels, key=lambda n: (min((_LABEL_RANK.get(t, 9) for t in
                                                         self.layout.nodes[n].tree_types), default=9), n))
        for nid in order:
            nd = self.layout.nodes[nid]
            t = self._labels[nid]
            if not (x0 <= nd.x <= x1 and y0 <= nd.y <= y1):
                t.set_visible(False)
                continue
            px, py = tr.transform((nd.x, nd.y))
            wpx = sum(11.0 if ord(c) > 0x2E7F else 5.6 for c in t.get_text()) + 4
            box = (px + 2, py - 7, px + 2 + wpx, py + 7)
            hit = any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in placed)
            t.set_visible(not hit)
            if not hit:
                placed.append(box)

    def full_draw(self) -> float:
        t0 = time.perf_counter()
        self.canvas.draw()
        self.update_idletasks()
        return (time.perf_counter() - t0) * 1000.0

    def _on_draw(self, _e=None):
        self._bg = self.canvas.copy_from_bbox(self.fig.bbox)
        for a in self._animated:
            self.ax.draw_artist(a)
        self.canvas.blit(self.fig.bbox)

    def _on_resize(self, _e=None):
        if self._resize_after:
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(150, self._after_resize)

    def _after_resize(self):
        self._resize_after = None
        if self._view is not None:
            x0, y0, x1, y1 = self._view
            self.set_view(x0, y0, x1, y1)

    # ── mouse ────────────────────────────────────────────────────────
    def _on_scroll(self, e):
        if e.xdata is None:
            return
        f = 1 / 1.5 if e.button == "up" else 1.5
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        cx, cy = e.xdata, e.ydata
        self.set_view(cx - (cx - x0) * f, cy - (cy - y0) * f, cx + (x1 - cx) * f, cy + (y1 - cy) * f)

    def _on_press(self, e):
        if e.button == 1 and e.x is not None:
            self._drag = (e.x, e.y, self.ax.get_xlim(), self.ax.get_ylim(), False)

    def _on_motion(self, e):
        if not self._drag or e.x is None:
            return
        px, py, (x0, x1), (y0, y1), _moved = self._drag
        if abs(e.x - px) + abs(e.y - py) < 4:
            return
        self._drag = (px, py, (x0, x1), (y0, y1), True)
        bb = self.ax.bbox
        dx = (e.x - px) * (x1 - x0) / bb.width
        dy = (e.y - py) * (y1 - y0) / bb.height
        self.ax.set_xlim(x0 - dx, x1 - dx)
        self.ax.set_ylim(y0 - dy, y1 - dy)
        self._view = (x0 - dx, y0 - dy, x1 - dx, y1 - dy)
        self._recull(self._lod or "110m")
        self.canvas.draw_idle()

    def _on_release(self, e):
        if not self._drag:
            return
        moved = self._drag[4]
        self._drag = None
        if moved:
            x0, x1 = self.ax.get_xlim()
            y0, y1 = self.ax.get_ylim()
            self.set_view(x0, y0, x1, y1)
        elif e.x is not None:
            self.pick_at(e.x, e.y)

    # ── picking ──────────────────────────────────────────────────────
    def pick_at(self, px: float, py: float) -> Optional[tuple]:
        if self.layout is None:
            return None
        tr = self.ax.transData
        best, bd = None, 10.0
        for nid in self._node_ids:
            nd = self.layout.nodes[nid]
            qx, qy = tr.transform((nd.x, nd.y))
            d = ((qx - px) ** 2 + (qy - py) ** 2) ** 0.5
            if d < bd:
                best, bd = ("node", nid), d
        if best is None:
            bd = 6.0
            for s, k in zip(self._segs, self._seg_edge):
                (ax_, ay_), (bx_, by_) = tr.transform(s[0]), tr.transform(s[1])
                vx, vy = bx_ - ax_, by_ - ay_
                L2 = vx * vx + vy * vy
                t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax_) * vx + (py - ay_) * vy) / L2))
                d = ((ax_ + t * vx - px) ** 2 + (ay_ + t * vy - py) ** 2) ** 0.5
                if d < bd:
                    best, bd = ("edge", int(k)), d
        self._pick = best
        self._show_pick()
        return best

    def _show_pick(self) -> None:
        if self._pick is None:
            return
        kind, key = self._pick
        F, S, w = self.flows, self._sel, self._week
        lines = []
        if kind == "node":
            nd = self.layout.nodes[key]
            lines += [f"🏷  {nd.name}", f"node_id：{nd.node_id}",
                      f"種類：{nd.master_type or '—'}（計画の木：{'/'.join(sorted(nd.tree_types)) or '計画に無い'}）",
                      f"緯度 {nd.lat:.4f}・経度 {nd.lon:.4f}"]
            if nd.products:
                lines.append(f"製品：{', '.join(sorted(nd.products))}")
            if nd.info.get("placed_at_parent"):
                lines.append(f"（位置：座標が無いので、親の {nd.info['placed_at_parent']} の位置に合わせた）")
            elif nd.colour_source == "sc_tree":
                lines.append("（色：node_master の種類が色の表に無いので、計画の木の役割の色）")
            if nd.info.get("description"):
                lines.append(f"\n{nd.info['description']}")
            if F is not None and S is not None:
                j = self._node_idx.get(key)
                lines.append(f"\n{F.week_labels[w]} の lot 数（{self._sku_var.get()}）")
                if j is not None:
                    s, co, i, p = (int(x) for x in S["psi"][w, j])
                    lines.append(f"P {p:,}　S {s:,}　I {i:,}　CO {co:,}")
                    if nd.is_market:
                        lines.append(f"販売（消費者への出荷）{int(S['sales'][w, j]):,}")
                    if nd.is_supply_point:
                        lines.append("supply point は仮想のノード：物はここに来ない")
        else:
            a, b = self._geo[key]
            lines += [f"区間：{a} → {b}"]
            for prod, edge in self._geo_members[key]:
                lines.append(f"\n[{prod}]")
                if F is not None:
                    lt = F.lt_master.get((prod, edge))
                    obs = F.lt_observed.get((prod, edge))
                    lines.append(f"LT：{lt if lt is not None else '—'} 週（マスター）"
                                 + (f"・実測 {obs:g} 週（到着週−出荷週の中央値）" if obs is not None else ""))
                    try:
                        i = F.edge_keys.index((prod, edge))
                        lines.append(f"{F.week_labels[w]}：出荷 {int(F.ship[w, i]):,} lot・"
                                     f"輸送中 {int(F.transit[w, i]):,} lot")
                    except ValueError:
                        lines.append("この計画では、この区間に実出荷がありません")
        self._set_info("\n".join(lines))

    # ── lists ────────────────────────────────────────────────────────
    def _show_missing(self):
        if self.layout is None:
            return
        top = tk.Toplevel(self)
        top.title("座標の無い拠点・描けない区間")
        top.geometry("900x420")
        txt = tk.Text(top, font=("Segoe UI", 9))
        txt.pack(fill="both", expand=True)
        L = self.layout
        out = [f"座標の無い拠点（描かない）：{len(L.missing_coords)}"]
        out += [f"  {m['node_id']}　{m['reason']}　{'（計画の木にある）' if m['in_plan_tree'] else ''}"
                for m in L.missing_coords]
        out += ["", f"描けない区間（端の拠点に座標が無い）：{len(L.undrawable_edges)}"]
        out += [f"  [{u['product']}] {u['edge']}　座標の無い拠点：{u['missing']}" for u in L.undrawable_edges]
        out += ["", f"親の位置に合わせた拠点（Stock Yard）：{len(L.placed_at_parent)}"]
        out += [f"  {x['node_id']} → {x['parent']} の位置　{x['reason']}" for x in L.placed_at_parent]
        if L.colour_notes:
            out += ["", "色の注記："] + [f"  {c}" for c in L.colour_notes]
        txt.insert("end", "\n".join(out))
        txt.config(state="disabled")
        return top

    # ── for the checks (tools / tests) ───────────────────────────────
    def edge_lots(self, mode: str = MODE_SHIP) -> Dict[Tuple[str, str], np.ndarray]:
        """The per-(product, edge) weekly lots the map draws (before summing products)."""
        F = self.flows
        if F is None:
            return {}
        arr = F.ship if mode == MODE_SHIP else F.transit
        return {k: arr[:, i] for i, k in enumerate(F.edge_keys)}
