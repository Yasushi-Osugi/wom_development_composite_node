# -*- coding: utf-8 -*-
"""
wom/lovem/viewer.py — LOVEM stage B: Windows stand-alone viewer (Tk + matplotlib).

    python -m wom.lovem.viewer output/lovem/ev-thailand-2026/run_A

Read only: the viewer never re-plans and never writes into the run folder.
All IDs are drawn (no thinning). Lines are drawn with one LineCollection per
drawing category (design §5.5); segments outside the current view are culled
with numpy masks, and the header always shows total / drawn / not drawn /
filtered counts.

Threading: the run folder is loaded in a worker thread (no Tk calls there);
progress reaches the UI through a queue polled with `after`. All Tk and
matplotlib updates happen on the UI thread.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
import numpy as np  # noqa: E402

from wom.lovem.viewdata import (BO_H, CATEGORIES, LANE_H, NODE_H, Cancelled, EvidenceIndex,  # noqa: E402
                                lot_history, evidence_for_lot, load_view_data, pick,
                                se2_view, visible_mask)

matplotlib.rcParams["font.family"] = ["Yu Gothic", "Meiryo", "MS Gothic", "DejaVu Sans"]

# category -> (color, linestyle, linewidth, zorder)
STYLE = {
    "D_S":   ("#5C6BC0", (0, (3, 2)), 0.6, 2),
    "D_P":   ("#7986CB", (0, (1, 1.5)), 0.6, 2),
    "D_I":   ("#3949AB", (0, (5, 2)), 0.7, 2),
    "D_CO":  ("#8E24AA", (0, (5, 2)), 0.7, 2),
    "P_rcv": ("#1E88E5", "solid", 0.9, 4),
    "P_unk": ("#9E9E9E", (0, (1, 1)), 0.9, 4),
    "P_src": ("#6D4C41", "solid", 0.9, 4),
    "I":     ("#43A047", "solid", 0.8, 3),
    "SHIP":  ("#E53935", "solid", 1.1, 5),
    "S_PLN": ("#8D6E63", (0, (4, 1.5, 1, 1.5)), 0.6, 2),
    "CO":    ("#FB8C00", "solid", 0.8, 3),
    "REL":   ("#607D8B", "solid", 0.35, 1),
}
REL_ALPHA = 0.25
HILITE = "#FFD600"


class LovemViewer(tk.Tk):
    def __init__(self, run_dir: str, snapshot: str = "final"):
        super().__init__()
        self.run_dir, self.snapshot = run_dir, snapshot
        self.title(f"LOVEM viewer — {os.path.basename(os.path.abspath(run_dir))}")
        self.geometry("1600x960")
        self.vd = None
        self.masks = {}
        self.colls = {}
        self.hi_coll = None
        self.selected = None
        self.cat_vars = {}
        self._q: "queue.Queue" = queue.Queue()
        self._cancel = threading.Event()
        self._cull_job = None
        self._full_done = False
        self.evidence = EvidenceIndex(run_dir)
        self.bench: dict = {}
        self._build()
        self.after(50, self.start_load)

    # ------------------------------------------------------------------ layout
    def _build(self):
        top = ttk.Frame(self, padding=4)
        top.pack(fill="x")
        self.info = tk.StringVar(value="読み込み前")
        ttk.Label(top, textvariable=self.info, font=("Yu Gothic UI", 9)).pack(anchor="w")
        self.counts = tk.StringVar(value="")
        ttk.Label(top, textvariable=self.counts, font=("Yu Gothic UI", 10, "bold")).pack(anchor="w")
        bar = ttk.Frame(top)
        bar.pack(fill="x", pady=2)
        self.prog = ttk.Progressbar(bar, length=240, maximum=1.0)
        self.prog.pack(side="left")
        self.prog_lbl = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.prog_lbl, width=26).pack(side="left", padx=4)
        self.btn_cancel = ttk.Button(bar, text="中止", command=self._cancel.set)
        self.btn_cancel.pack(side="left")
        ttk.Button(bar, text="全体表示", command=self.view_all).pack(side="left", padx=(12, 2))
        ttk.Button(bar, text="SE2 へ移動", command=self.goto_se2).pack(side="left", padx=2)
        ttk.Button(bar, text="checks.csv を読む", command=self.load_checks).pack(side="left", padx=2)
        ttk.Label(bar, text="  Lot_ID:").pack(side="left")
        self.search = tk.StringVar()
        e = ttk.Entry(bar, textvariable=self.search, width=36)
        e.pack(side="left")
        e.bind("<Return>", lambda _e: self.select_lot(self.search.get().strip(), zoom=True))
        ttk.Button(bar, text="選択", command=lambda: self.select_lot(self.search.get().strip(), zoom=True)).pack(side="left", padx=2)
        ttk.Button(bar, text="選択解除", command=self.clear_selection).pack(side="left", padx=2)
        self.mode = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.mode, foreground="#1565C0").pack(side="left", padx=10)

        flt = ttk.Frame(top)
        flt.pack(fill="x")
        ttk.Label(flt, text="表示する区分：").pack(side="left")
        for k, lbl in CATEGORIES.items():
            v = tk.BooleanVar(value=True)
            self.cat_vars[k] = v
            ttk.Checkbutton(flt, text=k, variable=v, command=self.schedule_cull).pack(side="left")

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        body.add(left, weight=4)
        # small requested size: the Tk widget then expands to the free space and the
        # figure is resized to it (a large figsize would be clipped at high DPI scaling)
        self.fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = self.fig.add_axes([0.21, 0.15, 0.77, 0.8])
        self.canvas = FigureCanvasTkAgg(self.fig, master=left)
        self.toolbar = NavigationToolbar2Tk(self.canvas, left, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        # HiDPI: matplotlib multiplies the figure dpi by the Tk device pixel ratio
        # AFTER sizing it to the widget, so the figure ended up larger than the
        # widget (bottom clipped). Re-fit the figure to the widget's real pixel
        # size whenever the widget is mapped or resized.
        self._fit_job = None
        for seq in ("<Configure>", "<Map>"):
            self.canvas.get_tk_widget().bind(seq, self._schedule_fit, add="+")
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.canvas.mpl_connect("scroll_event", self.on_scroll)

        right = ttk.Frame(body, width=460)
        body.add(right, weight=2)
        ttk.Label(right, text="候補（重なった線は全部出す。ダブルクリックで選択）").pack(anchor="w")
        self.cand = tk.Listbox(right, height=5, font=("Consolas", 9))
        self.cand.pack(fill="x")
        self.cand.bind("<Double-Button-1>", self.on_cand)
        self._cand_items = []
        ttk.Label(right, text="選択 ID の詳細（全ノードの履歴・予定と実出荷・元の記録）").pack(anchor="w")
        dfr = ttk.Frame(right)
        dfr.pack(fill="both", expand=True)
        self.detail = tk.Text(dfr, height=10, wrap="none", font=("Consolas", 9))
        dsx = ttk.Scrollbar(dfr, orient="horizontal", command=self.detail.xview)
        dsy = ttk.Scrollbar(dfr, orient="vertical", command=self.detail.yview)
        self.detail.configure(xscrollcommand=dsx.set, yscrollcommand=dsy.set)
        dsy.pack(side="right", fill="y")
        dsx.pack(side="bottom", fill="x")
        self.detail.pack(fill="both", expand=True)
        ttk.Label(right, text="元の記録（source_evidence）").pack(anchor="w")
        evf = ttk.Frame(right)
        evf.pack(fill="x")
        self.ev_text = tk.Text(evf, height=6, wrap="word", font=("Consolas", 9))
        self.ev_text.pack(side="left", fill="both", expand=True)
        self.btn_back = ttk.Button(right, text="この記録の図の位置へ戻る", command=self.goto_evidence_pos,
                                   state="disabled")
        self.btn_back.pack(anchor="w", pady=2)
        self._ev_pos = None

    def _schedule_fit(self, _ev=None):
        if self._fit_job is not None:
            self.after_cancel(self._fit_job)
        self._fit_job = self.after(80, self._fit_figure)

    def _fit_figure(self):
        self._fit_job = None
        w = self.canvas.get_tk_widget()
        pw, ph = w.winfo_width(), w.winfo_height()
        if pw < 10 or ph < 10:
            return
        fw, fh = self.fig.get_size_inches() * self.fig.dpi
        if abs(fw - pw) > 1 or abs(fh - ph) > 1:
            self.fig.set_size_inches(pw / self.fig.dpi, ph / self.fig.dpi, forward=False)
            self.canvas.draw_idle()

    # ------------------------------------------------------------------ loading
    def start_load(self):
        self._t_load0 = time.perf_counter()

        def work():
            try:
                vd = load_view_data(self.run_dir, self.snapshot,
                                    progress=lambda s, f: self._q.put(("prog", s, f)),
                                    cancel=self._cancel)
                self._q.put(("done", vd))
            except Cancelled:
                self._q.put(("cancelled",))
            except Exception as exc:  # noqa: BLE001
                import traceback
                self._q.put(("error", f"{exc}\n{traceback.format_exc()}"))
        threading.Thread(target=work, daemon=True).start()
        self.after(100, self._poll)

    def _poll(self):
        try:
            while True:
                msg = self._q.get_nowait()
                if msg[0] == "prog":
                    self.prog["value"] = msg[2]
                    self.prog_lbl.set(f"読み込み中：{msg[1]} {msg[2]*100:.0f}%")
                elif msg[0] == "done":
                    self.bench["load_s"] = time.perf_counter() - self._t_load0
                    self.on_loaded(msg[1])
                    return
                elif msg[0] == "cancelled":
                    self.prog_lbl.set("中止しました（未読込）")
                    self.counts.set("未読込：読み込みを中止したため図はありません")
                    return
                elif msg[0] == "error":
                    self.prog_lbl.set("読み込みエラー")
                    self.detail.insert("end", msg[1])
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def on_loaded(self, vd):
        self.vd = vd
        self.btn_cancel.state(["disabled"])
        man = vd.manifest
        self.info.set(
            f"run {man['run_id']}  |  snapshot {self.snapshot}  |  model {man['model_dir']}  |  "
            f"code {man['code_sha'][:7]}{' +dirty' if man['dirty'] else ''}  |  "
            f"期間 {man['weeks']['first_week']}〜{man['weeks']['last_week']}（{vd.n_weeks}週）  |  "
            f"観測の完全性：未取得 {len(man['coverage']['known_gaps'])} 項目（DATA_DICTIONARY §4）、"
            f"出荷と結べない到着 {man['coverage']['arrival_unlinked']}"
            + ("" if self.snapshot == "final" else
               "  |  Forward 前の段階：実出荷・到着・関係はこの段階に無いので描かない"))
        t0 = time.perf_counter()
        self._draw_static()
        for k, c in vd.cats.items():
            color, ls, lw, z = STYLE[k]
            # created empty: the first cull (view_all) sets every segment once
            lc = LineCollection([], colors=color, linestyles=ls, linewidths=lw, zorder=z,
                                alpha=REL_ALPHA if k == "REL" else 1.0)
            self.ax.add_collection(lc)
            self.colls[k] = lc
            self.masks[k] = np.ones(len(c), dtype=bool)
        self.bench["build_collections_s"] = time.perf_counter() - t0
        self.view_all(initial=True)
        self.ax.callbacks.connect("xlim_changed", lambda _a: self.schedule_cull())
        self.ax.callbacks.connect("ylim_changed", lambda _a: self.schedule_cull())
        self.prog["value"] = 1.0
        self.prog_lbl.set(f"読み込み完了（{self.bench.get('load_s', 0):.0f} 秒）")

    def _draw_static(self):
        vd, ax = self.vd, self.ax
        n = vd.n_weeks
        ax.set_facecolor("#FAFAFA")
        # Business Owner lane
        ax.add_patch(matplotlib.patches.Rectangle((-9, 0.1), n + 18, BO_H - 0.3, color="#ECEFF1", zorder=0))
        ax.text(n / 2, BO_H / 2, "Business Owner の経営意思決定レーン（段階 E で接続）",
                ha="center", va="center", fontsize=9, color="#607D8B")
        # product blocks
        for prod, y0, y1 in vd.product_spans:
            ax.axhline(y0 - 0.1, color="#90A4AE", lw=0.8, zorder=1)
            ax.text(-8.8, y0 - 0.25, f"製品 {prod}", fontsize=9, fontweight="bold", va="bottom")
        # node bands + lane separators
        polys = []
        for (row, w) in vd.closed:
            y0 = vd.node_y0[row]
            polys.append([(w, y0), (w + 1, y0), (w + 1, y0 + NODE_H), (w, y0 + NODE_H)])
        if polys:
            ax.add_collection(PolyCollection(polys, facecolors="#9E9E9E", alpha=0.35, zorder=0,
                                             edgecolors="none"))
        yt, yl = [], []
        for i, r in enumerate(vd.nodes):
            y0 = vd.node_y0[i]
            ax.add_patch(matplotlib.patches.Rectangle((0, y0), n, NODE_H, fill=False,
                                                      edgecolor="#CFD8DC", lw=0.5, zorder=1))
            for lane in (1, 2):
                ax.plot([0, n], [y0 + lane * LANE_H] * 2, color="#ECEFF1", lw=0.5, zorder=1)
            yt += [y0 + 0.5, y0 + 1.5, y0 + 2.5]
            ab = {"leaf_out": "LO", "dad": "DAD", "supply_point": "SP", "mom": "MOM",
                  "leaf_in": "LI", "stockyard": "YD"}.get(r["node_type"], r["node_type"])
            yl += [f"{r['node_name']}  Demand", f"[{ab}/{r['plan_mode']}]  Supply・物", "Supply・要求"]
            b = vd.before_horizon.get(i, [])
            a = vd.after_horizon.get(i, [])
            ax.text(-0.3, y0 + 1.5, f"期間前 {len(b)}" if b else "", ha="right", va="center",
                    fontsize=7, color="#6A1B9A")
            ax.text(n + 0.3, y0 + 1.5, f"期間後 {len(a)}" if a else "", ha="left", va="center",
                    fontsize=7, color="#6A1B9A")
        ax.set_yticks(yt)
        ax.set_yticklabels(yl, fontsize=6)
        labels = [w["engine_week_label"] for w in vd.weeks]
        from matplotlib.ticker import FuncFormatter, MaxNLocator
        # tick at integer x = start of week x; label = that week (works at any zoom)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=7, integer=True))
        ax.xaxis.set_major_formatter(FuncFormatter(
            lambda x, _p: labels[int(x)] if 0 <= int(x) < len(labels) and x == int(x) else ""))
        ax.tick_params(axis="x", top=True, labeltop=True, labelsize=7)
        handles = [Line2D([], [], color=STYLE[k][0], linestyle=STYLE[k][1], lw=1.5, label=f"{k}: {v}")
                   for k, v in CATEGORIES.items()]
        handles.append(Patch(facecolor="#9E9E9E", alpha=0.35, label="灰色背景：休業週"))
        handles.append(Line2D([], [], color=HILITE, lw=3, label="選択中の Lot_ID"))
        self.fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.01, 0.0),
                        fontsize=5.5, ncol=4, frameon=True)

    # ------------------------------------------------------------------ view
    def view_all(self, initial=False):
        if self.vd is None:
            return
        self.ax.set_xlim(-9, self.vd.n_weeks + 9)
        self.ax.set_ylim(self.vd.y_max + 0.5, 0)
        self.mode.set("モード：全体図")
        self._cull(now=True)
        if initial:
            t0 = time.perf_counter()
            self.canvas.draw()
            self.bench["full_draw_s"] = time.perf_counter() - t0
            self._full_done = True
            self._update_counts()

    def schedule_cull(self):
        if self.vd is None:
            return
        if self._cull_job is not None:
            self.after_cancel(self._cull_job)
        self._cull_job = self.after(120, self._cull)

    def _cull(self, now=False):
        self._cull_job = None
        vd = self.vd
        x0, x1 = sorted(self.ax.get_xlim())
        y0, y1 = sorted(self.ax.get_ylim())
        t0 = time.perf_counter()
        for k, c in vd.cats.items():
            if not self.cat_vars[k].get():
                m = np.zeros(len(c), dtype=bool)
            else:
                m = visible_mask(c, x0, x1, y0, y1)
            self.masks[k] = m
            self.colls[k].set_segments(c.segments(m))
        self.bench.setdefault("cull_s", []).append(time.perf_counter() - t0)
        full = x0 <= -1 and x1 >= vd.n_weeks + 1 and y0 <= 0.5 and y1 >= vd.y_max
        if not full and self.selected is None:
            self.mode.set("モード：範囲拡大")
        elif full and self.selected is None:
            self.mode.set("モード：全体図")
        self._update_counts()
        if not now:
            self.canvas.draw_idle()

    def _update_counts(self):
        vd = self.vd
        total_ids = len(vd.lots)
        filtered_cats = [k for k, v in self.cat_vars.items() if not v.get()]
        ids_on = vd.unique_lots_in(cats=[k for k in vd.cats if k not in filtered_cats])
        ids_drawn = vd.unique_lots_in(masks=self.masks)
        ids_filtered = total_ids - len(ids_on)
        seg_total = vd.total_segments()
        seg_drawn = sum(int(m.sum()) for m in self.masks.values())
        state = "全件描画 完了" if (self._full_done and not filtered_cats and seg_drawn == seg_total) else \
            ("全件を描画対象とし、表示範囲外・フィルタ分を除いて描画" if self._full_done else "描画未完了")
        self.counts.set(
            f"総 ID {total_ids:,}  |  描画済み ID {len(ids_drawn):,}  |  未描画 ID "
            f"{total_ids - len(ids_drawn) - ids_filtered:,}（表示範囲外）  |  フィルタで除外 {ids_filtered:,}  |  "
            f"線分 {seg_drawn:,} / {seg_total:,}  |  {state}")

    def on_scroll(self, ev):
        if self.vd is None:
            return
        y0, y1 = self.ax.get_ylim()
        step = (y0 - y1) * 0.15 * (-1 if ev.button == "up" else 1)
        self.ax.set_ylim(y0 + step, y1 + step)
        self.schedule_cull()

    def zoom_to(self, row, w0, w1, pad_rows=1):
        vd = self.vd
        y0 = vd.node_y0[max(0, row - pad_rows)] - 0.3
        y1 = vd.node_y0[min(len(vd.nodes) - 1, row + pad_rows)] + NODE_H + 0.3
        self.ax.set_xlim(w0, w1)
        self.ax.set_ylim(y1, y0)
        self.mode.set("モード：範囲拡大")
        self._cull()

    # ------------------------------------------------------------------ selection
    def on_click(self, ev):
        if self.vd is None or ev.inaxes is not self.ax or ev.button != 1:
            return
        if self.toolbar.mode:          # zoom / pan tool active
            return
        vd = self.vd
        if ev.xdata < 0 or ev.xdata > vd.n_weeks:
            row, _lane = vd.row_at(ev.ydata)
            if row is not None:
                ids = vd.before_horizon.get(row, []) if ev.xdata < 0 else vd.after_horizon.get(row, [])
                side = "期間前（Backward で期間内に置けなかった需要）" if ev.xdata < 0 else "期間後（到着が期間外）"
                self._set_candidates([(lot, f"{side} {vd.nodes[row]['node_name']}") for lot in ids])
            return
        bb = self.ax.get_window_extent()
        (xa, xb), (ya, yb) = self.ax.get_xlim(), self.ax.get_ylim()
        tol_x = 4 * abs(xb - xa) / bb.width
        tol_y = 4 * abs(yb - ya) / bb.height
        hits = pick(vd, ev.xdata, ev.ydata, tol_x, tol_y,
                    cats=[k for k, v in self.cat_vars.items() if v.get()], masks=self.masks)
        labels = [w["engine_week_label"] for w in vd.weeks]
        items = [(h["lot"], f"{h['cat']:<6} {vd.nodes[h['row']]['node_name']:<18} {labels[h['week']]}")
                 for h in hits]
        uniq = {i[0] for i in items}
        if len(uniq) == 1:
            self._set_candidates(items)
            self.select_lot(items[0][0])
        else:
            self._set_candidates(items)

    def _set_candidates(self, items):
        self.cand.delete(0, "end")
        self._cand_items = items
        for lot, desc in items:
            self.cand.insert("end", f"{lot}  | {desc}")
        if not items:
            self.cand.insert("end", "（この位置に線はありません）")

    def on_cand(self, _ev):
        sel = self.cand.curselection()
        if sel and sel[0] < len(self._cand_items):
            self.select_lot(self._cand_items[sel[0]][0])

    def clear_selection(self):
        self.selected = None
        if self.hi_coll is not None:
            self.hi_coll.remove()
            self.hi_coll = None
        self.detail.delete("1.0", "end")
        self.mode.set("モード：全体図")
        self.canvas.draw_idle()

    def select_lot(self, lot, zoom=False):
        vd = self.vd
        if vd is None or not lot:
            return
        t0 = time.perf_counter()
        li = vd.lot_index.get(lot)
        self.detail.delete("1.0", "end")
        if li is None:
            self.detail.insert("end", f"{lot} はこの run の保存データにありません。\n")
            return
        self.selected = lot
        segs = [c.segments(c.lot == li) for c in vd.cats.values()]
        segs = np.concatenate([s for s in segs if len(s)]) if any(len(s) for s in segs) else np.zeros((0, 2, 2))
        if self.hi_coll is not None:
            self.hi_coll.remove()
        self.hi_coll = LineCollection(segs, colors=HILITE, linewidths=2.6, zorder=20)
        self.ax.add_collection(self.hi_coll)
        self.mode.set(f"モード：選択 ID  {lot}（全ノードで強調）")
        self._write_detail(lot)
        self.bench.setdefault("select_s", []).append(time.perf_counter() - t0)
        if zoom and len(segs):
            xs, ys = segs[:, :, 0], segs[:, :, 1]
            self.ax.set_xlim(float(xs.min()) - 2, float(xs.max()) + 2)
            self.ax.set_ylim(float(ys.max()) + 2, float(ys.min()) - 2)
            self._cull()
        self.canvas.draw_idle()

    def _write_detail(self, lot):
        vd = self.vd
        labels = [w["engine_week_label"] for w in vd.weeks]
        T = self.detail
        T.insert("end", f"Lot_ID  {lot}\n", "h")
        T.insert("end", "（分類はしていません。予定 S と実出荷は別の記録です）\n\n")
        hist = lot_history(vd, lot)
        for row in sorted(hist):
            r = vd.nodes[row]
            T.insert("end", f"■ {r['node_name']}  [{r['product_id']} / {r['node_type']} / {r['plan_mode']}]\n", "h")
            for rec in hist[row]:
                wl = labels[rec["week"]] if rec["week"] is not None else "—"
                cat = rec["cat"]
                if cat in ("I", "CO", "D_I", "D_CO"):
                    end = int(rec["x1"]) - 1
                    wl = f"{labels[rec['week']]}〜{labels[end]}"
                note = ""
                if cat == "P_unk":
                    note = "  ← 入庫の出所：記録なし（未確認）"
                elif cat == "SHIP":
                    note = f"  event {rec['event_id']}  seq {rec['seq']}"
                elif cat == "REL":
                    note = f"  {rec['relation_id']}  {rec['from_ref']} → {rec['to_ref']}"
                elif cat == "BEFORE_HORIZON":
                    note = "  期間前：Backward で期間内に置けなかった需要（backward_past_due）"
                elif cat == "AFTER_HORIZON":
                    note = "  期間後：出荷したが到着週が期間外"
                label = CATEGORIES.get(cat, cat)
                T.insert("end", f"   {wl:<20} {cat:<6} {label}{note}\n")
        T.insert("end", "\n元の記録（クリックで下に表示）：\n", "h")
        for ev in evidence_for_lot(vd, lot):
            tag = f"ev_{ev['event_id']}"
            wl = labels[ev["week_index"]] if isinstance(ev["week_index"], int) and 0 <= ev["week_index"] < len(labels) else ev["week_index"]
            nd = vd.nodes[vd.node_row[ev["node_id"]]]["node_name"] if ev["node_id"] in vd.node_row else ev["node_id"]
            T.insert("end", f"   {ev['event_type']:<18} {nd:<18} {wl}  → {ev['evidence_ref']}\n", (tag,))
            T.tag_bind(tag, "<Button-1>", lambda _e, ev=ev: self.show_evidence(ev))
            T.tag_config(tag, foreground="#1565C0", underline=True)
        T.tag_config("h", font=("Consolas", 9, "bold"))

    def show_evidence(self, ev):
        rec = self.evidence.get(ev["evidence_ref"]) if ev.get("evidence_ref") else None
        self.ev_text.delete("1.0", "end")
        if rec is None:
            self.ev_text.insert("end", f"{ev['evidence_ref']}：source_evidence に該当なし")
            return
        payload = rec["payload"]
        pl = json.dumps(payload, ensure_ascii=False)
        self.ev_text.insert("end", f"{rec['evidence_id']}  {rec['source_kind']}\n{rec['source_locator']}\n"
                                   f"source_hash {rec['source_hash']}\n"
                                   f"payload（{len(pl):,} 文字）: {pl[:1500]}{' …' if len(pl) > 1500 else ''}\n")
        row = self.vd.node_row.get(ev["node_id"])
        self._ev_pos = (row, ev["week_index"]) if row is not None and isinstance(ev["week_index"], int) else None
        self.btn_back.state(["!disabled"] if self._ev_pos else ["disabled"])

    def goto_evidence_pos(self):
        if self._ev_pos:
            row, w = self._ev_pos
            self.zoom_to(row, w - 4, w + 5, pad_rows=0)
            self.canvas.draw_idle()

    # ------------------------------------------------------------------ SE2 / checks
    def goto_se2(self):
        vd = self.vd
        p = os.path.join(self.run_dir, "se2_case.json")
        if vd is None or not os.path.exists(p):
            return
        se2 = json.load(open(p, encoding="utf-8"))
        view = se2_view(vd, se2)
        labels = [w["engine_week_label"] for w in vd.weeks]
        w0 = labels.index(se2["target_weeks"][0])
        self.zoom_to(view["row"], w0 - 4, w0 + 7, pad_rows=0)
        T = self.detail
        T.delete("1.0", "end")
        T.insert("end", f"SE2：{se2['product_id']} / {se2['node_name']}  対象週 {', '.join(se2['target_weeks'])}\n")
        T.insert("end", "（予定 S・実出荷・I・CO の Lot_ID をそのまま並べる。分類はしない：段階 C）\n\n")
        for r in se2["target_week_rows"]:
            T.insert("end", f"{r['week']}: 予定S {r['planned_s']}  実出荷 {r['actual_s']}  差 {r['signed_gap']}  "
                            f"push_shortfall {r['push_shortfall']}\n")
        for wl, cell in view["weeks"].items():
            T.insert("end", f"\n■ {wl}\n")
            for k, ids in cell.items():
                T.insert("end", f"  {k} ({len(ids)}): {' '.join(ids[:400])}{' …' if len(ids) > 400 else ''}\n")
        self.canvas.draw_idle()

    def load_checks(self):
        p = filedialog.askopenfilename(title="checks.csv（段階 C の checker 出力）",
                                       filetypes=[("CSV", "*.csv")], initialdir=self.run_dir)
        if not p:
            return
        with open(p, encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        top = tk.Toplevel(self)
        top.title(f"checks.csv — {p}")
        if not rows:
            ttk.Label(top, text="空のファイル").pack()
            return
        tv = ttk.Treeview(top, columns=rows[0], show="headings")
        for c in rows[0]:
            tv.heading(c, text=c)
            tv.column(c, width=120)
        for r in rows[1:]:
            tv.insert("", "end", values=r)
        tv.pack(fill="both", expand=True)


# ----------------------------------------------------------------------------
# bench / screenshots (run scripted steps on the real window)
# ----------------------------------------------------------------------------

def _grab(win, path):
    """Save (1) the figure via matplotlib and (2) the viewer window rendered by
    Win32 PrintWindow into an off-screen bitmap. PrintWindow draws ONLY this
    window (even when other windows cover it), so no other application can
    appear in the image. Never uses a screen grab."""
    win.fig.savefig(path.replace(".png", "_figure.png"), dpi=110)
    win.update()
    try:
        img = _print_window(int(win.wm_frame(), 16))
        img.save(path)
    except Exception as exc:  # noqa: BLE001
        print(f"[lovem] window capture skipped ({exc}); figure saved only")


def _print_window(hwnd):
    import ctypes
    from ctypes import wintypes
    from PIL import Image
    u32, g32 = ctypes.windll.user32, ctypes.windll.gdi32
    r = wintypes.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = u32.GetWindowDC(hwnd)
    mdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, h)
    g32.SelectObject(mdc, bmp)
    ok = u32.PrintWindow(hwnd, mdc, 2)          # PW_RENDERFULLCONTENT
    if not ok:
        raise RuntimeError("PrintWindow failed")

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
    bih = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    g32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
    g32.DeleteObject(bmp); g32.DeleteDC(mdc); u32.ReleaseDC(hwnd, hdc)
    return Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)


def run_bench(run_dir, out_json, shots_dir, select_lot=None):
    import psutil
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    proc = psutil.Process(os.getpid())
    rss0 = proc.memory_info().rss
    app = LovemViewer(run_dir)
    os.makedirs(shots_dir, exist_ok=True)
    res = {"rss_before_mb": rss0 / 1e6}

    def step1():
        if app.vd is None:
            app.after(300, step1)
            return
        app.update()
        app._fit_figure()
        t0 = time.perf_counter()
        app.canvas.draw()
        res["full_draw_fitted_s"] = time.perf_counter() - t0
        res["load_s"] = app.bench.get("load_s")
        res["load_detail_s"] = app.vd.timing
        res["build_collections_s"] = app.bench.get("build_collections_s")
        res["full_draw_s"] = app.bench.get("full_draw_s")
        res["segments_total"] = app.vd.total_segments()
        res["segments_drawn_full"] = int(sum(m.sum() for m in app.masks.values()))
        res["ids_total"] = len(app.vd.lots)
        res["ids_drawn_full"] = len(app.vd.unique_lots_in(masks=app.masks))
        res["counts_label_full"] = app.counts.get()
        wdg = app.canvas.get_tk_widget()
        res["canvas_widget_px"] = [wdg.winfo_width(), wdg.winfo_height()]
        res["figure_px"] = [float(v) for v in app.fig.get_size_inches() * app.fig.dpi]
        res["figure_dpi"] = app.fig.dpi
        res["device_pixel_ratio"] = getattr(app.canvas, "device_pixel_ratio", None)
        _grab(app, os.path.join(shots_dir, "01_overall.png"))
        t0 = time.perf_counter()
        app.goto_se2()
        app.canvas.draw()
        res["zoom_se2_s"] = time.perf_counter() - t0
        res["counts_label_se2"] = app.counts.get()
        _grab(app, os.path.join(shots_dir, "02_se2_zoom.png"))
        lot = select_lot
        if lot is None:
            se2 = json.load(open(os.path.join(run_dir, "se2_case.json"), encoding="utf-8"))
            lot = se2_view(app.vd, se2)["weeks"][se2["target_weeks"][1]]["planned_S"][0]
        t0 = time.perf_counter()
        app.select_lot(lot, zoom=False)
        app.canvas.draw()
        res["select_s"] = time.perf_counter() - t0
        res["selected_lot"] = lot
        evs = evidence_for_lot(app.vd, lot)
        if evs:
            app.show_evidence(evs[0])
        _grab(app, os.path.join(shots_dir, "03_id_selected.png"))
        # evidence -> back to the figure position of that record
        t0 = time.perf_counter()
        app.goto_evidence_pos()
        app.canvas.draw()
        res["evidence_back_s"] = time.perf_counter() - t0
        res["evidence_back_pos"] = app._ev_pos
        _grab(app, os.path.join(shots_dir, "05_evidence_back.png"))
        app.view_all()
        app.select_lot(lot, zoom=False)
        app.canvas.draw()
        _grab(app, os.path.join(shots_dir, "04_id_selected_overall.png"))
        mi = proc.memory_info()
        res["rss_after_mb"] = mi.rss / 1e6
        res["peak_wset_mb"] = getattr(mi, "peak_wset", 0) / 1e6
        res["screen"] = {"w": app.winfo_screenwidth(), "h": app.winfo_screenheight(),
                         "tk_scaling": float(app.tk.call("tk", "scaling")),
                         "window": [app.winfo_width(), app.winfo_height()]}
        res["versions"] = {"python": sys.version.split()[0], "matplotlib": matplotlib.__version__,
                           "backend": matplotlib.get_backend(), "tk": app.tk.call("info", "patchlevel")}
        json.dump(res, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        app.destroy()

    app.after(500, step1)
    app.mainloop()
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--snapshot", default="final")
    ap.add_argument("--bench", default=None, help="scripted steps; write timings JSON here")
    ap.add_argument("--shots", default=None, help="screenshot folder for --bench")
    a = ap.parse_args(argv)
    if a.bench:
        run_bench(a.run_dir, a.bench, a.shots or os.path.dirname(os.path.abspath(a.bench)))
        return 0
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    LovemViewer(a.run_dir, a.snapshot).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
