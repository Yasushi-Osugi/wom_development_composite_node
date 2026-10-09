# -*- coding: utf-8 -*-
"""
試作の画面：Natural Earth の地図を matplotlib で描き、拠点・拠点間の線・週の再生を重ねる。

    python -m wom.worldmap_ne [--model ev-thailand-2026] [--lod auto|110m|50m|10m] [--no-blit]

操作：マウスのホイールでズーム（カーソルの位置を中心に）、左ドラッグで移動。上の帯のボタンで
「World / Asia / Thailand / Bangkok / Nodes」の範囲へ。▶ ⏸ ⏹ で週の再生。「blit」を外すと、
週ごとに地図ごと描き直す（比較用）。帯の右に、直前の描画にかかった時間を出す。

速くするための工夫（依頼書 2.2-3）：
- 地図の線は、細かさ・層ごとに 1 つの LineCollection、陸地は 1 つの PolyCollection（線 1 本ずつ
  描かない）。投影は読み込み時に 1 回だけ（data.py）。
- 細かさはズームで切り替え、表示範囲（の少し外まで）に入る部分だけを渡す。
- 週の再生は blitting：地図と動かない線を一度描いて画像として取っておき（draw_event で
  copy_from_bbox）、週ごとには流れの線・拠点・週の文字だけを描き直す。
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional

import numpy as np
import matplotlib
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from wom.worldmap_ne.data import NEMap, choose_lod, merc_y, SCALES
from wom.worldmap_ne.model import MapModel, load_model

C_OCEAN = "#D6E6EE"
C_LAND = "#F4F1EA"
C_COAST = "#8FA9B8"
C_BORDER = "#B8AFA0"
C_EDGE_DIM = "#90A4AE"
C_FLOW_OUT = "#1E88E5"
C_FLOW_IN = "#43A047"

# Named views: (lon0, lat0, lon1, lat1)
VIEWS = {
    "World":    (-180.0, -58.0, 180.0, 78.0),
    "Asia":     (60.0, -12.0, 150.0, 55.0),
    "Thailand": (97.0, 5.0, 106.0, 21.0),
    "Bangkok":  (100.15, 13.45, 100.95, 14.05),
}
MODELS = ["ev-thailand-2026", "smartphone-global-2026-2029", "oil-global-2027"]
DEMAND_TAG = "需要の流れ（試作の計測用。計画の結果ではない）"
DEMAND_BANNER = ("  " + DEMAND_TAG + "　｜　計画の実出荷の流れは WOM の World Map タブ"
                 "（Run Planning Engine の後）で見る")


def view_to_xy(v):
    lon0, lat0, lon1, lat1 = v
    return lon0, float(merc_y(lat0)), lon1, float(merc_y(lat1))


class MapView(tk.Frame):
    """The map, the nodes and the weekly flows. Drives itself with set_view / set_week."""

    def __init__(self, master, nemap: NEMap, model: Optional[MapModel] = None,
                 lod: str = "auto", blit: bool = True, dpi: Optional[float] = None, **kw):
        super().__init__(master, **kw)
        self.nemap = nemap
        self.lod_mode = lod
        self.blit = blit
        self.model: Optional[MapModel] = None
        self.week = 0
        self.last: Dict[str, object] = {}
        self._bg = None
        self._view = None
        self._cull_view = None
        self._lod = None

        self.fig = Figure(facecolor=C_OCEAN, dpi=dpi) if dpi else Figure(facecolor=C_OCEAN)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        ax = self.ax
        ax.set_facecolor(C_OCEAN)
        ax.set_axis_off()
        ax.set_aspect("equal", adjustable="datalim")
        self.land = PolyCollection([], facecolors=C_LAND, edgecolors="none", zorder=1)
        self.coast = LineCollection([], colors=C_COAST, linewidths=0.6, zorder=2)
        self.border = LineCollection([], colors=C_BORDER, linewidths=0.5, linestyles="--", zorder=2)
        self.edges = LineCollection([], colors=C_EDGE_DIM, linewidths=0.8, alpha=0.6, zorder=3)
        self.flows = LineCollection([], linewidths=1.0, zorder=4, capstyle="round")
        self.nodes = ax.scatter([], [], s=30, zorder=5, edgecolors="white", linewidths=0.8)
        self.week_text = ax.text(0.01, 0.99, "", transform=ax.transAxes, va="top", ha="left",
                                 fontsize=10, color="#263238", zorder=6,
                                 bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.8))
        for a in (self.land, self.coast, self.border, self.edges, self.flows):
            ax.add_collection(a)
        self._animated = (self.flows, self.nodes, self.week_text)
        self.set_blit(blit)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.mpl_connect("draw_event", self._on_draw)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self._drag = None
        if model is not None:
            self.set_model(model, draw=False)

    # ── model / blit ────────────────────────────────────────────────
    def set_model(self, model: MapModel, draw: bool = True) -> None:
        self.model = model
        segs = [((model.x[c], model.y[c]), (model.x[p], model.y[p])) for c, p, _ in model.edges]
        self.edges.set_segments(segs)
        self.flows.set_segments(segs)
        self._flow_colours = [C_FLOW_OUT if model.edge_outbound[k] else C_FLOW_IN
                              for k in range(len(segs))]
        self.flows.set_color(self._flow_colours)
        self.nodes.set_offsets(np.column_stack([model.x, model.y]))
        self.nodes.set_facecolors(model.colours)
        self._ef_max = float(model.edge_flow.max()) or 1.0
        self._nf_max = float(model.node_flow.max()) or 1.0
        self.week = 0
        self._apply_week(0)
        if draw:
            self.set_view(*model.extent())

    def set_blit(self, on: bool) -> None:
        self.blit = bool(on)
        for a in self._animated:
            a.set_animated(self.blit)
        self._bg = None

    # ── view ────────────────────────────────────────────────────────
    def current_lod(self, width_deg: float) -> str:
        if self.lod_mode in SCALES:
            return self.lod_mode
        return choose_lod(width_deg, self.ax.bbox.width)

    def set_view(self, x0, y0, x1, y1, draw: bool = True) -> Dict[str, object]:
        """Show the projected box; pick the LOD; give the collections only the
        parts inside (a margin of half a view around it, for panning)."""
        t0 = time.perf_counter()
        ax = self.ax
        # grow the box to the window's aspect (1 deg lon = 1 unit y), so the whole
        # requested box is shown (matplotlib's own adjustment may also shrink it)
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
        width = vx1 - vx0
        lod = self.current_lod(width)
        n = self._recull(lod, force=True)
        t1 = time.perf_counter()
        out = {"lod": lod, "segments": n, "view_width_deg": round(width, 3),
               "cull_ms": (t1 - t0) * 1000.0}
        if draw:
            out["draw_ms"] = self.full_draw()
        self.last = out
        return out

    def _recull(self, lod: str, force: bool = False) -> int:
        vx0, vy0, vx1, vy1 = self._view
        w, h = vx1 - vx0, vy1 - vy0
        if not force and self._cull_view is not None and self._lod == lod:
            cx0, cy0, cx1, cy1 = self._cull_view
            if cx0 <= vx0 and cy0 <= vy0 and cx1 >= vx1 and cy1 >= vy1:
                return -1                                    # still inside the culled area
        if lod not in self.nemap.layers:
            self.nemap.load([lod])
        cull = (vx0 - w / 2, vy0 - h / 2, vx1 + w / 2, vy1 + h / 2)
        whole = w >= 300                                     # world: no culling needed
        view = None if whole else cull
        coast = self.nemap.lines(lod, "coast", view)
        border = self.nemap.lines(lod, "border", view)
        land = self.nemap.land(lod, view)
        self.coast.set_segments(coast)
        self.border.set_segments(border)
        self.land.set_verts(land)
        self._cull_view, self._lod = cull, lod
        return len(coast) + len(border) + len(land)

    def full_draw(self) -> float:
        t0 = time.perf_counter()
        self.canvas.draw()                                   # map + (blit) animated on top
        self.update_idletasks()
        return (time.perf_counter() - t0) * 1000.0

    def _on_draw(self, _event=None):
        if not self.blit:
            return
        self._bg = self.canvas.copy_from_bbox(self.fig.bbox)
        for a in self._animated:
            self.ax.draw_artist(a)
        self.canvas.blit(self.fig.bbox)

    # ── weeks ───────────────────────────────────────────────────────
    def _apply_week(self, w: int) -> None:
        m = self.model
        if m is None or not m.weeks:
            return
        w = max(0, min(w, len(m.weeks) - 1))
        self.week = w
        ef = m.edge_flow[w] / self._ef_max
        self.flows.set_linewidths(0.3 + 6.0 * ef)
        self.flows.set_alpha(None)
        nf = m.node_flow[w] / self._nf_max
        self.nodes.set_sizes(18 + 220 * nf)
        self.week_text.set_text(f"{m.name}   {m.weeks[w]}  ({w + 1}/{len(m.weeks)})  {DEMAND_TAG}")

    def set_week(self, w: int) -> float:
        """Show week w; returns the milliseconds it took (update + draw on screen)."""
        t0 = time.perf_counter()
        self._apply_week(w)
        if self.blit and self._bg is not None:
            self.canvas.restore_region(self._bg)
            for a in self._animated:
                self.ax.draw_artist(a)
            self.canvas.blit(self.fig.bbox)
            self.update_idletasks()
        else:
            self.canvas.draw()
            self.update_idletasks()
        return (time.perf_counter() - t0) * 1000.0

    # ── mouse ───────────────────────────────────────────────────────
    def _on_scroll(self, e):
        if e.xdata is None:
            return
        f = 1 / 1.5 if e.button == "up" else 1.5
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        cx, cy = e.xdata, e.ydata
        self.set_view(cx - (cx - x0) * f, cy - (cy - y0) * f, cx + (x1 - cx) * f, cy + (y1 - cy) * f)
        self.event_generate("<<ViewChanged>>")

    def _on_press(self, e):
        if e.button == 1 and e.x is not None:
            self._drag = (e.x, e.y, self.ax.get_xlim(), self.ax.get_ylim())

    def _on_motion(self, e):
        if not self._drag or e.x is None:
            return
        px, py, (x0, x1), (y0, y1) = self._drag
        bb = self.ax.bbox
        dx = (e.x - px) * (x1 - x0) / bb.width
        dy = (e.y - py) * (y1 - y0) / bb.height
        self.ax.set_xlim(x0 - dx, x1 - dx)
        self.ax.set_ylim(y0 - dy, y1 - dy)
        self._view = (x0 - dx, y0 - dy, x1 - dx, y1 - dy)
        self._recull(self._lod or "110m")
        self.canvas.draw_idle()

    def _on_release(self, e):
        if self._drag:
            self._drag = None
            x0, x1 = self.ax.get_xlim()
            y0, y1 = self.ax.get_ylim()
            self.set_view(x0, y0, x1, y1)
            self.event_generate("<<ViewChanged>>")


class TrialApp(tk.Tk):
    """The trial window: a bar of controls over MapView."""

    def __init__(self, model: str = MODELS[0], lod: str = "auto", blit: bool = True):
        super().__init__()
        self.title("WOM World Map trial — Natural Earth + matplotlib（描画の速さを測る試作の窓）")
        self.geometry("1400x860")
        self.nemap = NEMap().load(["110m"])
        # RequestLetter_WorldMap_ActualFlows §2: this window's flows are built from the
        # demand (model.py), not from the plan -- say so, so they are not read as shipments.
        tk.Label(self, text=DEMAND_BANNER, bg="#FFF3E0", fg="#BF360C", anchor="w",
                 font=("Segoe UI", 10, "bold")).pack(fill="x")
        bar = tk.Frame(self)
        bar.pack(fill="x")
        tk.Label(bar, text="Model:").pack(side="left", padx=(6, 2))
        self.model_var = tk.StringVar(value=model)
        cb = ttk.Combobox(bar, textvariable=self.model_var, values=MODELS, width=20, state="readonly")
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self.load_model(self.model_var.get()))
        tk.Label(bar, text="  LOD:").pack(side="left")
        self.lod_var = tk.StringVar(value=lod)
        lcb = ttk.Combobox(bar, textvariable=self.lod_var, values=["auto", *SCALES], width=6, state="readonly")
        lcb.pack(side="left")
        lcb.bind("<<ComboboxSelected>>", lambda _e: self._set_lod())
        for name in (*VIEWS, "Nodes"):
            tk.Button(bar, text=name, command=lambda n=name: self.go(n)).pack(side="left", padx=1)
        tk.Label(bar, text="  |").pack(side="left")
        tk.Button(bar, text="▶", width=3, command=self.play).pack(side="left")
        tk.Button(bar, text="⏸", width=3, command=self.pause).pack(side="left")
        tk.Button(bar, text="⏹", width=3, command=self.stop).pack(side="left")
        self.blit_var = tk.BooleanVar(value=blit)
        tk.Checkbutton(bar, text="blit", variable=self.blit_var,
                       command=lambda: self._set_blit()).pack(side="left", padx=4)
        self.info = tk.StringVar(value="")
        tk.Label(bar, textvariable=self.info, fg="#37474F").pack(side="left", padx=8)
        self.view = MapView(self, self.nemap, lod=lod, blit=blit)
        self.view.pack(fill="both", expand=True)
        self.view.bind("<<ViewChanged>>", lambda _e: self._show_info())
        self._playing = False
        self._week_ms = []
        self.after(50, lambda: self.load_model(model))

    def load_model(self, name: str) -> None:
        self.stop()
        self.view.set_model(load_model(name), draw=False)
        self.go("Nodes")

    def go(self, name: str) -> None:
        box = self.view.model.extent() if name == "Nodes" else view_to_xy(VIEWS[name])
        self.view.set_view(*box)
        self._show_info()

    def _set_lod(self):
        self.view.lod_mode = self.lod_var.get()
        x0, x1 = self.view.ax.get_xlim()
        y0, y1 = self.view.ax.get_ylim()
        self.view.set_view(x0, y0, x1, y1)
        self._show_info()

    def _set_blit(self):
        self.view.set_blit(self.blit_var.get())
        self.view.full_draw()

    def _show_info(self, extra: str = ""):
        L = self.view.last
        self.info.set(f"LOD {L.get('lod')}  parts {L.get('segments')}  "
                      f"cull {L.get('cull_ms', 0):.1f} ms  draw {L.get('draw_ms', 0):.1f} ms {extra}")

    def play(self):
        if not self._playing:
            self._playing = True
            self._tick()

    def pause(self):
        self._playing = False

    def stop(self):
        self._playing = False
        if self.view.model is not None:
            self.view.set_week(0)

    def _tick(self):
        if not self._playing:
            return
        m = self.view.model
        ms = self.view.set_week((self.view.week + 1) % len(m.weeks))
        self._week_ms = (self._week_ms + [ms])[-20:]
        self._show_info(f"| week {np.median(self._week_ms):.1f} ms ({'blit' if self.view.blit else 'full'})")
        self.after(150, self._tick)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="WOM World Map trial (Natural Earth + matplotlib)")
    ap.add_argument("--model", default=MODELS[0])
    ap.add_argument("--lod", default="auto", choices=["auto", *SCALES])
    ap.add_argument("--no-blit", action="store_true")
    a = ap.parse_args(argv)
    # No SetProcessDpiAwareness: the window runs DPI-unaware like `python -m main`
    # (with awareness on, matplotlib's TkAgg sized the figure larger than the widget
    # on a 125 % screen and the right part of the map was cut off).
    TrialApp(a.model, a.lod, not a.no_blit).mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
