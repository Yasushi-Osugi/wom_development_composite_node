# -*- coding: utf-8 -*-
"""
wom/gui/allocation_panel.py — S1 Allocate タブ（Phase 8-1）
================================================================================
`wom/gui/s1_view_model.py` が作った `view` dict を**並べるだけ**（C9）。
このファイルの中で `scan_surface()` / `true_continuous_optimum()` /
`scan_hierarchical()` を呼ばない——すべて view model が計算済みの値を渡す。

正典: requests/Phase8-1_RequestLetter_to_CodeKun.md V2

【GUI 内の matplotlib は日本語可】（C4）: `app.py` が
`matplotlib.rcParams["font.family"] = ["Yu Gothic", "DejaVu Sans"]` を設定済み。
「図中テキストは全て英語」は `tools/` の PNG 出力に対する制約であり、GUI には
及ばない。このパネルの軸ラベル・凡例・注記は日本語でよい。
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from wom.gui.s1_view_model import build_s1_view, evaluate_allocation, format_market_name

# app.py と同じ配色（新しい定数を増やさない）
BG_DARK  = "#1E2A38"
BG_MID   = "#253347"
BG_LIGHT = "#2E3F55"
FG_WHITE = "#ECEFF1"
FG_ACC   = "#64B5F6"

_JA_FONT = ("Yu Gothic UI", 9)
_JA_FONT_BOLD = ("Yu Gothic UI", 10, "bold")


class AllocationPanel(tk.Frame):
    """S1 Allocate タブ。`load()` でモデルを読み、`view` を並べて描くだけ。"""

    def __init__(self, parent, app_ref=None, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self.app_ref = app_ref
        self._view: Optional[dict] = None
        self._model_dir = ""
        self._scenario_id = ""
        self._cap_wk = 800.0
        self._uom: Optional[str] = None
        self._node_path: tuple = ()
        self._build()

    # ------------------------------------------------------------------
    # レイアウト（ウィジェットの配置のみ）
    # ------------------------------------------------------------------
    def _build(self):
        # --- 入力行（S0 が無いので暫定的にここへ置く。Phase 8-2 で S0 へ移す） ---
        top = tk.Frame(self, bg=BG_MID)
        top.pack(fill="x", padx=6, pady=(6, 2))

        tk.Label(top, text="モデルフォルダ:", bg=BG_MID, fg=FG_WHITE,
                 font=_JA_FONT).pack(side="left", padx=(4, 2))
        self._model_dir_var = tk.StringVar(value="data/sample/soysauce-jpy-2027-alloc")
        tk.Entry(top, textvariable=self._model_dir_var, bg=BG_DARK, fg=FG_WHITE,
                 insertbackground=FG_WHITE, relief="flat", font=("Segoe UI", 9),
                 width=36).pack(side="left")
        tk.Button(top, text="参照…", command=self._on_browse, bg=BG_LIGHT, fg=FG_WHITE,
                  relief="flat", font=_JA_FONT).pack(side="left", padx=(2, 8))

        tk.Label(top, text="シナリオ:", bg=BG_MID, fg=FG_WHITE,
                 font=_JA_FONT).pack(side="left", padx=(4, 2))
        self._scenario_var = tk.StringVar(value="s1_base")
        tk.Entry(top, textvariable=self._scenario_var, bg=BG_DARK, fg=FG_WHITE,
                 insertbackground=FG_WHITE, relief="flat", font=("Segoe UI", 9),
                 width=14).pack(side="left")

        tk.Label(top, text="能力/週:", bg=BG_MID, fg=FG_WHITE,
                 font=_JA_FONT).pack(side="left", padx=(8, 2))
        self._cap_wk_var = tk.StringVar(value="800")
        tk.Entry(top, textvariable=self._cap_wk_var, bg=BG_DARK, fg=FG_WHITE,
                 insertbackground=FG_WHITE, relief="flat", font=("Segoe UI", 9),
                 width=8).pack(side="left")

        tk.Label(top, text="uom(任意):", bg=BG_MID, fg=FG_WHITE,
                 font=_JA_FONT).pack(side="left", padx=(8, 2))
        self._uom_var = tk.StringVar(value="")
        tk.Entry(top, textvariable=self._uom_var, bg=BG_DARK, fg=FG_WHITE,
                 insertbackground=FG_WHITE, relief="flat", font=("Segoe UI", 9),
                 width=10).pack(side="left")

        tk.Button(top, text="▶ 読み込み", command=self._on_load, bg=FG_ACC, fg=BG_DARK,
                  relief="flat", font=(_JA_FONT_BOLD)).pack(side="left", padx=(8, 4))

        # --- 結論行（3行） ---
        headline_frame = tk.Frame(self, bg=BG_DARK)
        headline_frame.pack(fill="x", padx=8, pady=(6, 2))
        self._headline_labels = []
        for i in range(3):
            lbl = tk.Label(headline_frame, text="", bg=BG_DARK, fg=FG_WHITE,
                           font=_JA_FONT_BOLD, anchor="w", justify="left")
            lbl.pack(fill="x")
            self._headline_labels.append(lbl)

        # --- 全市場の配分（省略なし・折り返し可）（Phase 8-2・C3.3） ---
        # 結論行は上位4市場+要約に畳むため、答えを画面外に落とさないための控え。
        # Phase 8-2a・D2: wraplength は窓幅に追従させる（固定ピクセルだと、窓が
        # 狭いとき右端の市場が折り返されずに切られ、C3 で潰したはずの「答えが
        # 画面外に落ちる」が一段下で再発する）。
        self._full_allocation_label = tk.Label(
            self, text="", bg=BG_DARK, fg="#90A4AE", font=("Segoe UI", 8),
            anchor="w", justify="left", wraplength=1000)
        self._full_allocation_label.pack(fill="x", padx=10, pady=(0, 4))
        self.bind("<Configure>", self._on_panel_resize)

        # --- パンくず（hierarchy モードのときだけ表示。triangle モードでは
        #     pack_forget() で隠す。再表示時は before=self._mid_frame で
        #     headline と根拠パネルの間という正しい位置に戻す） ---
        self._breadcrumb_frame = tk.Frame(self, bg=BG_MID)
        self._breadcrumb_inner = tk.Frame(self._breadcrumb_frame, bg=BG_MID)
        self._breadcrumb_inner.pack(side="left", padx=6, pady=2)
        self._up_btn = tk.Button(self._breadcrumb_frame, text="▲ 1つ上へ",
                                 command=self._on_up_click, bg=BG_LIGHT, fg=FG_WHITE,
                                 relief="flat", font=_JA_FONT)
        self._up_btn.pack(side="right", padx=6)
        self._breadcrumb_frame.pack(fill="x", padx=8, pady=(0, 2))
        self._breadcrumb_visible = True

        # --- 操作行・Drill-down（先に確保）（Phase 8-2a・D3） ---
        # mid（Figure・aux）を fill="both", expand=True で先に pack すると、
        # 窓が縮んだとき一番下の操作行から真っ先に切り取られる（1280x820の
        # 既定サイズでも ⚑ ボタンの行が半分欠ける事故が実機で確認された）。
        # ops → drill の順に side="bottom" で先に確保し、縮むのは常に図の
        # ほうになるようにする（tkinter の定石。mid は最後に pack する）。
        ops = tk.Frame(self, bg=BG_MID)
        ops.pack(side="bottom", fill="x", padx=8, pady=(0, 6))
        tk.Label(ops, text="配分:", bg=BG_MID, fg=FG_WHITE, font=_JA_FONT).pack(
            side="left", padx=(6, 2))
        self._alloc_choice = tk.StringVar(value="recommended")
        tk.Radiobutton(ops, text="推奨配分（真の最適 P_opt）", variable=self._alloc_choice,
                       value="recommended", bg=BG_MID, fg=FG_WHITE, selectcolor=BG_DARK,
                       activebackground=BG_MID, font=_JA_FONT).pack(side="left")
        self._manual_radio = tk.Radiobutton(
            ops, text="手入力(N=3のみ)", variable=self._alloc_choice, value="manual",
            bg=BG_MID, fg=FG_WHITE, selectcolor=BG_DARK, activebackground=BG_MID,
            font=_JA_FONT)
        self._manual_radio.pack(side="left", padx=(8, 2))
        self._manual_var = tk.StringVar(value="")
        tk.Entry(ops, textvariable=self._manual_var, bg=BG_DARK, fg=FG_WHITE,
                 insertbackground=FG_WHITE, relief="flat", font=("Segoe UI", 9),
                 width=20).pack(side="left")
        tk.Label(ops, text="(例 0.10,0.45,0.45)", bg=BG_MID, fg="#78909C",
                 font=("Segoe UI", 8)).pack(side="left", padx=(2, 12))

        tk.Button(ops, text="⚑ この配分で計画する", command=self._on_commit,
                  bg="#4CAF50", fg="#0B1F14", relief="flat",
                  font=_JA_FONT_BOLD).pack(side="left", padx=(4, 4))
        # Phase 8-2・C1.3: ⚑ が計画するのは結論行（P_opt）であって、子パネルの
        # 走査結果（階層格子の点）ではないことを明示する。
        tk.Label(ops, text="（計画するのは上の推奨配分です）", bg=BG_MID, fg="#78909C",
                 font=("Segoe UI", 8)).pack(side="left", padx=(0, 8))

        self._status_var = tk.StringVar(value="")
        tk.Label(ops, textvariable=self._status_var, bg=BG_MID, fg=FG_ACC,
                 font=("Segoe UI", 8)).pack(side="left")

        # --- Drill-down（ops の直上・side="bottom" で ops より先に確保） ---
        drill = tk.Frame(self, bg=BG_DARK)
        drill.pack(side="bottom", fill="x", padx=8, pady=(0, 4))
        tk.Button(drill, text="[ メリットオーダー曲線 ]", command=self._on_merit_order,
                  bg=BG_LIGHT, fg=FG_WHITE, relief="flat",
                  font=_JA_FONT).pack(side="left")

        # --- 根拠（matplotlib）＋ 補助パネル（残り全部。最後に pack する） ---
        mid = tk.Frame(self, bg=BG_DARK)
        mid.pack(fill="both", expand=True, padx=8, pady=4)
        self._mid_frame = mid

        plot_frame = tk.Frame(mid, bg=BG_DARK)
        plot_frame.pack(side="left", fill="both", expand=True)
        self._fig = Figure(figsize=(6.4, 5.2), dpi=95, facecolor=BG_DARK)
        self._canvas = FigureCanvasTkAgg(self._fig, master=plot_frame)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        aux = tk.Frame(mid, bg=BG_MID, width=260)
        aux.pack(side="left", fill="y", padx=(6, 0))
        aux.pack_propagate(False)

        tk.Label(aux, text="利益水準", bg=BG_MID, fg=FG_ACC, font=_JA_FONT_BOLD,
                 anchor="w").pack(fill="x", padx=6, pady=(6, 2))
        self._levels_frame = tk.Frame(aux, bg=BG_MID)
        self._levels_frame.pack(fill="x", padx=6)

        self._notes_label = tk.Label(aux, text="", bg=BG_MID, fg=FG_WHITE, font=_JA_FONT,
                                     anchor="w", justify="left", wraplength=240)
        self._notes_label.pack(fill="x", padx=6, pady=(4, 6))

        self._children_header_label = tk.Label(
            aux, text="子ノード", bg=BG_MID, fg=FG_ACC,
            font=_JA_FONT_BOLD, anchor="w", justify="left", wraplength=240)
        self._children_header_label.pack(fill="x", padx=6, pady=(6, 2))
        self._children_frame = tk.Frame(aux, bg=BG_MID)
        self._children_frame.pack(fill="x", padx=6)

        self._node_info_label = tk.Label(aux, text="", bg=BG_MID, fg=FG_WHITE,
                                         font=_JA_FONT, anchor="w", justify="left",
                                         wraplength=240)
        self._node_info_label.pack(fill="x", padx=6, pady=(8, 6))

    # ------------------------------------------------------------------
    # データ読み込み・再描画
    # ------------------------------------------------------------------
    def _on_panel_resize(self, event):
        """Phase 8-2a・D2: 「全市場の配分」控え欄の折返し幅を窓幅に追従させる。"""
        if event.widget is not self:
            return
        new_wrap = max(event.width - 24, 200)   # padx=10×2 + 余白
        if new_wrap != self._full_allocation_label.cget("wraplength"):
            self._full_allocation_label.config(wraplength=new_wrap)

    def _on_browse(self):
        d = filedialog.askdirectory(title="モデルフォルダを選択")
        if d:
            self._model_dir_var.set(d)

    def _on_load(self):
        model_dir = self._model_dir_var.get().strip()
        scenario_id = self._scenario_var.get().strip()
        uom = self._uom_var.get().strip() or None
        try:
            cap_wk = float(self._cap_wk_var.get())
        except ValueError:
            messagebox.showerror("S1 Allocate", "能力/週は数値で入力してください")
            return
        self._node_path = ()
        self.load(model_dir, scenario_id, cap_wk, uom=uom)

    def load(self, model_dir: str, scenario_id: str, cap_wk: float, *,
            uom: Optional[str] = None):
        """モデルを読み、view を作って描く（公開 API・V2）。"""
        self._model_dir = model_dir
        self._scenario_id = scenario_id
        self._cap_wk = cap_wk
        self._uom = uom
        self._reload_view()

    def _reload_view(self):
        try:
            view = build_s1_view(self._model_dir, scenario_id=self._scenario_id,
                                 cap_wk=self._cap_wk, uom=self._uom,
                                 node_path=self._node_path)
        except Exception as e:   # noqa: BLE001 — GUI の入力ミスをダイアログで見せる
            messagebox.showerror("S1 Allocate", f"読み込みに失敗しました:\n{e}")
            return
        self._view = view
        self._render(view)

    def _render(self, view: dict):
        for i, line in enumerate(view["headline"]["lines_ja"][:3]):
            self._headline_labels[i].config(text=line)
        for i in range(len(view["headline"]["lines_ja"]), 3):
            self._headline_labels[i].config(text="")

        # Phase 8-2・C3.3: 結論行で畳んだ配分の全文を、根拠パネルの上に控えとして出す
        self._full_allocation_label.config(
            text=f"全市場の配分（連続最適）: {view['headline']['full_allocation_ja']}")

        if view["mode"] == "hierarchy":
            if not self._breadcrumb_visible:
                self._breadcrumb_frame.pack(fill="x", padx=8, pady=(0, 2),
                                            before=self._mid_frame)
                self._breadcrumb_visible = True
            self._render_breadcrumb(view["breadcrumb"])
            # Phase 8-2・C1.2: 「推奨配分（連続最適）」とは別物であることを見出しに書く
            self._children_header_label.config(
                text="このノードの走査結果（階層格子 δ=0.05・クリックで降りる）")
        else:
            if self._breadcrumb_visible:
                self._breadcrumb_frame.pack_forget()
                self._breadcrumb_visible = False
            self._children_header_label.config(text="この配分の走査結果（格子 δ=0.05）")

        self._render_levels(view["levels"])
        self._notes_label.config(text="\n".join(view["level_notes_ja"]))
        self._render_children(view["node"])
        self._render_node_info(view["node"], view["plateau_size"])
        self._render_plot(view["node"])

        # 手入力は N=3（triangle）のときだけ意味を持つ
        state = "normal" if view["mode"] == "triangle" else "disabled"
        self._manual_radio.config(state=state)

    def _render_breadcrumb(self, breadcrumb):
        for w in self._breadcrumb_inner.winfo_children():
            w.destroy()
        for i, name in enumerate(breadcrumb):
            if i > 0:
                tk.Label(self._breadcrumb_inner, text="▸", bg=BG_MID, fg="#78909C",
                        font=_JA_FONT).pack(side="left")
            is_last = (i == len(breadcrumb) - 1)
            btn = tk.Label(self._breadcrumb_inner, text=format_market_name(name), bg=BG_MID,
                          fg=(FG_WHITE if is_last else FG_ACC), font=_JA_FONT,
                          cursor="" if is_last else "hand2")
            btn.pack(side="left", padx=2)
            if not is_last:
                btn.bind("<Button-1>", lambda _e, depth=i: self._on_breadcrumb_click(depth))

    def _render_levels(self, levels):
        for w in self._levels_frame.winfo_children():
            w.destroy()
        for entry in levels:
            color = "#EF5350" if entry["highlight"] else FG_WHITE
            row = tk.Frame(self._levels_frame, bg=BG_MID)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=entry["name"], bg=BG_MID, fg=color, font=_JA_FONT,
                    width=10, anchor="w").pack(side="left")
            tk.Label(row, text=f"{entry['value'] / 1e8:.3f} 億", bg=BG_MID, fg=color,
                    font=_JA_FONT, anchor="e").pack(side="left")

    def _render_children(self, node):
        for w in self._children_frame.winfo_children():
            w.destroy()

        # Phase 8-2a・D1: 「比率を出す/出さない」と「降りられる/降りられない」を
        # 別の軸にする。C2 の意図は前者（意味の無い比率を出さない）だけであり、
        # 子ノードへ降りる手段まで塞ぐべきではなかった——「なぜこの枝がゼロ
        # なのか」を最もよく説明する画面（C4 の葉の単位経済）が、その先にある。
        # 判定は view 側の is_unallocated を読むだけ（cap_lots == 0 をここで書かない）。
        if node["is_unallocated"]:
            tk.Label(self._children_frame, text=node["unallocated_message"], bg=BG_MID,
                    fg="#78909C", font=_JA_FONT, wraplength=240, justify="left",
                    anchor="w").pack(fill="x", anchor="w", pady=(0, 4))
        elif node["plot_kind"] == "none":
            tk.Label(self._children_frame, text="（配分が一意・下記の単位経済を参照）",
                    bg=BG_MID, fg="#78909C", font=_JA_FONT, wraplength=240,
                    justify="left").pack(anchor="w")
            return

        for child in node["children"]:
            row = tk.Frame(self._children_frame, bg=BG_MID)
            row.pack(fill="x", pady=1)
            if node["is_unallocated"]:
                label_text = f"{format_market_name(child)}　配分なし"
            else:
                x = node["child_x"].get(child, 0.0)
                label_text = f"{format_market_name(child)}  {x * 100:.0f}%"
            lbl = tk.Label(row, text=label_text, bg=BG_MID, fg=FG_ACC,
                          font=_JA_FONT, cursor="hand2", anchor="w")
            lbl.pack(fill="x")
            if self._view and self._view["mode"] == "hierarchy":
                lbl.bind("<Button-1>", lambda _e, c=child: self._on_child_click(c))

    def _render_node_info(self, node, plateau_size):
        le = node["leaf_economics"]
        if le is not None:
            # Phase 8-2・C4: 葉ノード（ドリルダウンの終点）は空白ではなく単位経済を出す。
            # マージン・売上は JPY 建て、price_local は現地通貨——混ぜない（§C4）。
            lines = [
                f"需要 {le['demand_qty']:,.0f} lot　能力 {le['cap_lots']:,.0f} lot"
                f"　出荷 {le['shipped']:,.0f} lot",
                f"現地売価: {le['price_local']:,.0f} {le['ccy']}",
                f"売上: {le['rev']:,.0f} 円/lot　原価: {le['cost']:,.0f} 円/lot",
                f"単位マージン: {le['margin']:,.0f} 円/lot（{le['margin_pct'] * 100:.1f}%）",
                f"全市場中の順位: {le['n_markets']}市場中 {le['rank']}位",
                f"関税率: {le['tariff_rate'] * 100:.1f}%",
            ]
            if le["shipped"] <= 0.0 and le["marginal_market"]:
                lines.append(
                    f"（能力が{le['marginal_rank']}位（{le['marginal_market']}）で"
                    f"尽きたため出荷 0）")
            self._node_info_label.config(text="\n".join(lines))
            return

        lines = [f"このノードの能力: {node['cap_lots']:,.0f} lot"]
        # Phase 8-2・C2: 配分ゼロの枝は台地サイズを出さない（意味を持たない）
        if not node["is_unallocated"] and plateau_size is not None:
            lines.append(f"台地サイズ: {plateau_size} 点")
        self._node_info_label.config(text="\n".join(lines))

    def _render_plot(self, node):
        self._fig.clear()
        ax = self._fig.add_subplot(111, facecolor=BG_DARK)
        for spine in ax.spines.values():
            spine.set_color("#546E7A")
        ax.tick_params(colors=FG_WHITE, labelsize=8)
        ax.title.set_color(FG_WHITE)
        ax.xaxis.label.set_color(FG_WHITE)
        ax.yaxis.label.set_color(FG_WHITE)

        surface = node["surface"]
        children = node["children"]
        le = node["leaf_economics"]
        if node["is_unallocated"]:
            # Phase 8-2・C2: 平坦な0円の面を描いても意味が無い。図は描かない。
            ax.text(0.5, 0.5, node["unallocated_message"], ha="center", va="center",
                    color=FG_WHITE, fontsize=10, wrap=True, transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
        elif le is not None:
            # Phase 8-2・C4: 葉ノードは 売上→原価→マージン の横棒1本
            ax.barh(["マージン", "原価", "売上"],
                   [le["margin"], le["cost"], le["rev"]],
                   color=["#66BB6A", "#EF5350", FG_ACC])
            ax.set_xlabel("円/lot")
            ax.set_title(f"{format_market_name(node['name'])}"
                        f"（{le['n_markets']}市場中 {le['rank']}位）", fontsize=10)
        elif node["plot_kind"] == "triangle" and surface:
            xus = [pt["x"][1] for pt in surface]
            xeu = [pt["x"][2] for pt in surface]
            z = [pt["profit"] / 1e6 for pt in surface]
            tcf = ax.tricontourf(xus, xeu, z, levels=14, cmap="RdYlGn")
            self._fig.colorbar(tcf, ax=ax, fraction=0.046, pad=0.04,
                               label="利益（百万円）")
            ax.plot([0, 1], [1, 0], color="#90A4AE", lw=1.0)
            cx = node["child_x"].get(children[1], 0.0)
            cy = node["child_x"].get(children[2], 0.0)
            ax.plot(cx, cy, marker="*", ms=16, mfc="#111", mec="w", mew=0.8, zorder=5)
            ax.set_xlabel(format_market_name(children[1]))
            ax.set_ylabel(format_market_name(children[2]))
            ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
            ax.set_aspect("equal")
            ax.set_title(f"{format_market_name(node['name'])}", fontsize=10)
        elif node["plot_kind"] == "line" and surface:
            pts = sorted(surface, key=lambda pt: pt["x"][1])
            xs = [pt["x"][1] for pt in pts]
            ys = [pt["profit"] / 1e6 for pt in pts]
            ax.plot(xs, ys, color=FG_ACC, lw=1.6)
            cx = node["child_x"].get(children[1], 0.0)
            best_y = max(ys) if ys else 0.0
            ax.axvline(cx, color="#EF5350", ls="--", lw=1.0)
            ax.set_xlabel(f"{format_market_name(children[1])} の比率")
            ax.set_ylabel("利益（百万円）")
            ax.set_title(f"{format_market_name(node['name'])}"
                        f"（{format_market_name(children[0])} ⇄ {format_market_name(children[1])}）",
                        fontsize=10)
        else:
            ax.text(0.5, 0.5, "配分が一意（描画なし）", ha="center", va="center",
                    color=FG_WHITE, fontsize=11, transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])

        self._fig.tight_layout()
        self._canvas.draw()

    # ------------------------------------------------------------------
    # 操作
    # ------------------------------------------------------------------
    def _on_breadcrumb_click(self, depth: int):
        # depth==0 は ALL（ルート）を意味する。breadcrumb[0] は木の root 名なので
        # node_path は breadcrumb[1:depth+1] に対応する。
        self._node_path = tuple(self._view["breadcrumb"][1:depth + 1])
        self._reload_view()

    def _on_up_click(self):
        if self._node_path:
            self._node_path = self._node_path[:-1]
            self._reload_view()

    def _on_child_click(self, child: str):
        self._node_path = self._node_path + (child,)
        self._reload_view()

    def _on_commit(self):
        if self._view is None:
            return
        try:
            if self._alloc_choice.get() == "manual":
                markets = self._view["node"]["children"] \
                    if self._view["mode"] == "triangle" else None
                if markets is None:
                    messagebox.showerror("S1 Allocate", "手入力は N=3 のときだけ使えます")
                    return
                vals = [float(v) for v in self._manual_var.get().split(",")]
                if len(vals) != len(markets):
                    messagebox.showerror(
                        "S1 Allocate", f"{len(markets)}個の値をカンマ区切りで入力してください")
                    return
                allocation = dict(zip(markets, vals))
                source = "manual"
            else:
                allocation = dict(self._view["headline"]["recommended"])
                source = "P_opt"

            plan_eval = evaluate_allocation(self._model_dir, self._scenario_id,
                                            self._cap_wk, allocation, uom=self._uom)
            profit_levels = dict(self._view["profit_levels"])
            profit_levels["source"] = source

            import wom.planning_state as planning_state
            case = os.path.basename(self._model_dir.rstrip("/\\"))
            state = planning_state.new_state(
                case, self._scenario_id, allocation, profit_levels, plan_eval,
                reversal=self._view["reversal"])
            path = planning_state.save(state)
            allocation_id = os.path.splitext(os.path.basename(path))[0]
            self._status_var.set(f"保存: {path}（{allocation_id}）")
        except Exception as e:   # noqa: BLE001
            messagebox.showerror("S1 Allocate", f"計画案の保存に失敗しました:\n{e}")

    def _on_merit_order(self):
        if self._view is None:
            return
        mo = self._view.get("merit_order")
        if not mo:
            return
        win = tk.Toplevel(self)
        win.title("メリットオーダー曲線")
        win.configure(bg=BG_DARK)
        fig = Figure(figsize=(7.5, 5), dpi=95, facecolor=BG_DARK)
        ax = fig.add_subplot(111, facecolor=BG_DARK)
        for spine in ax.spines.values():
            spine.set_color("#546E7A")
        ax.tick_params(colors=FG_WHITE, labelsize=9)
        ax.xaxis.label.set_color(FG_WHITE); ax.yaxis.label.set_color(FG_WHITE)
        ax.title.set_color(FG_WHITE)

        cum = 0.0
        for b in mo["blocks"]:
            width = b["allocated"]
            if width <= 0:
                continue
            ax.bar(cum + width / 2, b["margin_effective"], width=width,
                  color=FG_ACC, edgecolor=BG_DARK, alpha=0.85)
            ax.text(cum + width / 2, b["margin_effective"], b["market"],
                   ha="center", va="bottom", color=FG_WHITE, fontsize=8)
            cum += width
        if mo.get("marginal_market"):
            ax.axhline(mo["lambda"], color="#EF5350", ls="--", lw=1.2,
                      label=f"λ={mo['lambda']:,.0f}")
            ax.legend(facecolor=BG_MID, labelcolor=FG_WHITE, fontsize=8)
        ax.set_xlabel("累積配分量（lot）")
        ax.set_ylabel("単位マージン（円/lot）")
        ax.set_title("メリットオーダー曲線")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.get_tk_widget().pack(fill="both", expand=True)
        canvas.draw()
