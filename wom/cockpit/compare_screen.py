# -*- coding: utf-8 -*-
"""
wom/cockpit/compare_screen.py — 事業計画の比較の 1 画面（見るだけ。Tk ＋ matplotlib）
====================================================================================
RequestLetter_Cockpit_Stage3_Step2 B、設計書 §1・§2。起動：`python -m main --cockpit-compare [--ws <作業>]`。

4 つの区画：① 案の表（基準 ◎ と相手 ○ を選ぶ）、② 選んだ案の入力（読むだけ）、③ 比較（供給・工場・金額と境目）、
④ 読むときの注意。数字は `wom/cockpit/compare_view_model.py` が作り、この画面は描くだけ。
**ファイルを書かない。入力を変える・実行するボタンは無い（段 3）。**

`wom.cockpit` の下に置くのは、パッケージの `__init__.py` が日本語フォントを設定するため。
matplotlib は Figure ＋ FigureCanvasTkAgg を直接使う（pyplot・`matplotlib.use` を使わない。__init__.py の注意）。
"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from wom.cockpit import cases as C
from wom.cockpit import compare_view_model as V

TITLE = "どの製品を、どの市場に、いつ投入し、生産量をどう整えるか"
# supply cell categories (color): no demand / all on time / late / unallocated (③) / backlog after allocation (⑤)
CAT_COLORS = ["#ffffff", "#9fd49f", "#f2d16b", "#f4a259", "#d9534f"]
CAT_LABELS = ["需要なし", "当週に全量", "遅配あり", "未配分あり（③）", "配分後の未充足あり（⑤）"]
COL_WIDTH = {"ID": 44, "案の名前": 150, "親": 44, "供給の方針": 380, "未配分": 360, "未充足（期末）": 360,
             "P0（円、報告期間）": 130, "状態": 110}


class CompareScreen(ttk.Frame):
    def __init__(self, master, ws: Optional[str] = None, base: Optional[str] = None, alt: Optional[str] = None):
        super().__init__(master)
        self.master = master
        self.ws = ws
        self.base, self.alt = base, alt
        self.selected: Optional[str] = None
        self._build()
        if ws:
            self.open_workspace(ws)

    # ── layout ──────────────────────────────────────────────────────────
    def _build(self):
        self.pack(fill="both", expand=True)
        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=(6, 2))
        ttk.Label(top, text=TITLE, font=("Yu Gothic UI", 13, "bold")).pack(side="left")
        ttk.Button(top, text="開き直す", command=self.reopen).pack(side="right")
        ttk.Button(top, text="作業を開く…", command=self._choose).pack(side="right", padx=4)
        self.header = ttk.Label(self, text="", foreground="#444")
        self.header.pack(fill="x", padx=8)

        vp = ttk.PanedWindow(self, orient="vertical")
        vp.pack(fill="both", expand=True, padx=6, pady=4)
        # ① case table
        f1 = ttk.LabelFrame(vp, text="① 案の表（◎ 基準、○ 比べる相手）")
        self.tree = ttk.Treeview(f1, show="headings", height=7, selectmode="browse")
        sx = ttk.Scrollbar(f1, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=sx.set)
        self.tree.pack(fill="both", expand=True)
        sx.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        b = ttk.Frame(f1)
        b.pack(fill="x")
        ttk.Button(b, text="基準にする ◎", command=lambda: self._set_role("base")).pack(side="left", padx=2, pady=2)
        ttk.Button(b, text="比べる相手にする ○", command=lambda: self._set_role("alt")).pack(side="left", padx=2)
        self.pair_label = ttk.Label(b, text="")
        self.pair_label.pack(side="left", padx=10)
        vp.add(f1, weight=2)

        hp = ttk.PanedWindow(vp, orient="horizontal")
        # ② inputs
        f2 = ttk.LabelFrame(hp, text="② 選んだ案の入力（読むだけ）")
        self.inputs = tk.Text(f2, width=46, wrap="word", font=("Yu Gothic UI", 9))
        self.inputs.pack(fill="both", expand=True)
        hp.add(f2, weight=1)
        # ③ comparison
        f3 = ttk.LabelFrame(hp, text="③ 基準 ◎ と相手 ○ の比較")
        self.nb = ttk.Notebook(f3)
        self.nb.pack(fill="both", expand=True)
        self.tab_supply = ttk.Frame(self.nb)
        self.tab_factory = ttk.Frame(self.nb)
        self.tab_money = ttk.Frame(self.nb)
        self.nb.add(self.tab_supply, text="供給：鍵 × 要求週")
        self.nb.add(self.tab_factory, text="工場：生産と計画値")
        self.nb.add(self.tab_money, text="金額と境目")
        self.cmp_msg = ttk.Label(f3, text="", foreground="#a33")
        self.cmp_msg.pack(fill="x")
        self._build_supply_tab()
        self._build_factory_tab()
        self._build_money_tab()
        hp.add(f3, weight=4)
        vp.add(hp, weight=6)
        # ④ notes
        f4 = ttk.LabelFrame(vp, text="④ 読むときの注意")
        self.notes = tk.Text(f4, height=6, wrap="word", font=("Yu Gothic UI", 9))
        self.notes.pack(fill="both", expand=True)
        vp.add(f4, weight=1)

    def _table(self, parent, cols: List[str], height=6) -> ttk.Treeview:
        fr = ttk.Frame(parent)
        fr.pack(fill="x")
        t = ttk.Treeview(fr, columns=cols, show="headings", height=height)
        for c in cols:
            t.heading(c, text=c)
            w = {"鍵": 210, "費目": 170, "境目の置き方": 320, "読み方": 360}.get(c, max(70, min(220, 12 * len(c))))
            t.column(c, width=w, anchor="e" if c not in cols[:2] else "w")
        sx = ttk.Scrollbar(fr, orient="horizontal", command=t.xview)
        t.configure(xscrollcommand=sx.set)
        t.pack(fill="x")
        sx.pack(fill="x")
        return t

    def _build_supply_tab(self):
        bar = ttk.Frame(self.tab_supply)
        bar.pack(fill="x")
        ttk.Label(bar, text="SKU:").pack(side="left")
        self.supply_sku = ttk.Combobox(bar, state="readonly", width=16)
        self.supply_sku.pack(side="left")
        self.supply_sku.bind("<<ComboboxSelected>>", lambda e: self._draw_supply())
        ttk.Label(bar, text="  ● ＝ 最低供給量ちょうど（削って最低）  ○ ＝ 需要が最低供給量と同じ").pack(side="left")
        self.supply_fig = Figure(figsize=(9, 3.2), dpi=90)
        self.supply_canvas = FigureCanvasTkAgg(self.supply_fig, self.tab_supply)
        self.supply_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.supply_totals = self._table(self.tab_supply, ["案", "鍵", "需要", "供給の対象", "未配分（③）", "当週",
                                                           "早出し", "遅配", "配分後の未充足（⑤）", "最低ちょうどの週",
                                                           "うち削って最低"], height=7)

    def _build_factory_tab(self):
        bar = ttk.Frame(self.tab_factory)
        bar.pack(fill="x")
        ttk.Label(bar, text="SKU:").pack(side="left")
        self.factory_sku = ttk.Combobox(bar, state="readonly", width=16)
        self.factory_sku.pack(side="left")
        self.factory_sku.bind("<<ComboboxSelected>>", lambda e: self._draw_factory())
        self.factory_fig = Figure(figsize=(9, 3.2), dpi=90)
        self.factory_canvas = FigureCanvasTkAgg(self.factory_fig, self.tab_factory)
        self.factory_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.factory_weeks = self._table(self.tab_factory, ["案", "SKU", "計画の上限（良品）", "ちょうど作った最初の週",
                                                            "最後の週", "その間の週数", "うち報告期間", "うち助走",
                                                            "ちょうど作った週", "下回った週"], height=4)
        self.factory_inv = self._table(self.tab_factory, ["SKU", "在庫 lot・週 基準", "相手", "最大 基準", "相手",
                                                          "期末 基準", "相手"], height=2)
        self.factory_age = self._table(self.tab_factory, ["案", "SKU", "納品", "年齢の最大（週）", "52 週超"], height=4)

    def _build_money_tab(self):
        self.money_fig = Figure(figsize=(9, 2.4), dpi=90)
        self.money_canvas = FigureCanvasTkAgg(self.money_fig, self.tab_money)
        self.money_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.money_p0 = self._table(self.tab_money, ["期間", "SKU", "P0 基準", "P0 相手", "差"], height=4)
        self.money_fc = self._table(self.tab_money, [
            "費目", "有償の週 基準", "W 基準", "有償の週 相手", "W 相手", "週額 基準", "週額 相手", "費用 基準", "費用 相手",
            "控除後 基準", "控除後 相手", "ΔP0", "ΔW", "境目（円／週）", "境目の置き方", "読み方", "評価"], height=4)

    # ── workspace ───────────────────────────────────────────────────────
    def _choose(self):
        d = filedialog.askdirectory(title="作業の置き場（output/cockpit_cases/<作業>）を選ぶ")
        if d:
            self.base = self.alt = None
            self.open_workspace(d)

    def open_workspace(self, ws: str):
        self.ws = ws
        self.reopen()

    def reopen(self):
        """Read the workspace again (nothing is cached across reopen)."""
        if not self.ws:
            return
        info = C.open_workspace(self.ws)
        self.header.configure(text=f"作業：{info['dir']}　元のモデル：{os.path.basename(info['source_model'])}（写し）"
                                   f"　報告期間：{info['report_period']['start']}〜{info['report_period']['end']}　通貨：JPY")
        self.table = V.case_table(self.ws)
        ids = [r["id"] for r in self.table["rows"]]
        if self.base not in ids:
            self.base = None
        if self.alt not in ids:
            self.alt = None
        self._fill_case_table()
        if self.selected not in ids:
            self.selected = self.base or (ids[0] if ids else None)
        if self.selected:
            self.tree.selection_set(self.selected)
        self._show_inputs()
        self._show_comparison()

    def _fill_case_table(self):
        cols = ["role"] + self.table["columns"]
        self.tree.configure(columns=cols)
        for c in cols:
            self.tree.heading(c, text="" if c == "role" else c)
            w = 34 if c == "role" else COL_WIDTH.get(c, max(70, min(260, 13 * len(c))))
            self.tree.column(c, width=w, anchor="w", stretch=False)
        self.tree.delete(*self.tree.get_children())
        for r in self.table["rows"]:
            role = "◎" if r["id"] == self.base else ("○" if r["id"] == self.alt else "")
            tag = "ok" if r["state"] == C.ST_DONE else "warn"
            self.tree.insert("", "end", iid=r["id"], values=[role] + r["cells"], tags=(tag,))
        self.tree.tag_configure("warn", foreground="#b22")
        self.pair_label.configure(text=f"基準 ◎ {self.base or '—'}　相手 ○ {self.alt or '—'}")

    def _on_select(self, _e=None):
        sel = self.tree.selection()
        if sel:
            self.selected = sel[0]
            self._show_inputs()

    def _set_role(self, role: str):
        if not self.selected:
            return
        if role == "base":
            self.base = self.selected
            if self.alt == self.base:
                self.alt = None
        else:
            self.alt = self.selected
            if self.base == self.alt:
                self.base = None
        self._fill_case_table()
        self.tree.selection_set(self.selected)
        self._show_comparison()

    # ── ② ─────────────────────────────────────────────────────────────
    def _show_inputs(self):
        t = self.inputs
        t.configure(state="normal")
        t.delete("1.0", "end")
        if not self.selected:
            t.configure(state="disabled")
            return
        d = V.case_inputs(self.ws, self.selected)
        L = [f"{d['id']}　{d['name']}（親 {d['parent'] or '—'}）", f"状態：{d['state_display']}"]
        if d["state"] != C.ST_DONE and d["reason"]:
            L.append(f"理由：{d['reason']}")
        L += ["", "■ 投入の表"] + [f"  {r['sku_id']}:{r['region']}  投入 {r['launch_week']}  定常 {r['steady_lots_per_week']} lot／週"
                                   f"（立ち上がり {r['ramp_weeks']} 週 × {r['ramp_ratio']}）" for r in d["entry_plan"]]
        L += ["", "■ 計画の生産量（工場 × SKU、全期間で 1 つの値）"] + \
            [f"  {r['sku_id']} @ {r['node']}：max_supply {r['max_supply']}・cap_soft {r['cap_soft']}" for r in d["capacity"]]
        L += ["", "■ 供給の方針"]
        p = d["policy"]
        L += ["  なし"] if not p else [f"  数量枠 {os.path.basename(p['allocation_file'] or '')}",
                                     f"  最低供給量 {os.path.basename(p['policy_file'] or '') or '—'}",
                                     f"  週の規則 {p['week_rule']}"]
        L += ["", "■ 費用の前提"]
        if not d["fixed_cost"]:
            L.append("  なし")
        for f in d["fixed_cost"]:
            L.append(f"  {f['cost_item']}（{f['entity']}）：有償 {f['paid']}"
                     + ("（助走を含む）" if f["count_outside_report"] else "") + f"、週額 {f['weekly_amount']}")
        if d["fixed_cost_note"]:
            L.append(f"  ※ {d['fixed_cost_note']}")
        L += ["", f"※ {d['note']}"]
        t.insert("1.0", "\n".join(L))
        t.configure(state="disabled")

    # ── ③ ─────────────────────────────────────────────────────────────
    def _show_comparison(self):
        self.cmp = None
        for tv in (self.supply_totals, self.factory_weeks, self.factory_inv, self.factory_age, self.money_p0,
                   self.money_fc):
            tv.delete(*tv.get_children())
        for fig in (self.supply_fig, self.factory_fig, self.money_fig):
            fig.clear()
        msg = ""
        if not (self.base and self.alt):
            msg = "基準 ◎ と相手 ○ を選ぶと、比較を出す"
        else:
            self.cmp = V.comparison(self.ws, self.base, self.alt)
            if not self.cmp["available"]:
                msg = f"比較 {self.base} → {self.alt}：{self.cmp['state']}。{self.cmp['reason']}（数字は出さない）"
        self.cmp_msg.configure(text=msg)
        if self.cmp and self.cmp["available"]:
            skus = sorted({k[0] for k in self.cmp["supply"]["keys"]})
            for cb in (self.supply_sku, self.factory_sku):
                cb.configure(values=skus)
                if cb.get() not in skus:
                    cb.set(skus[0] if skus else "")
            self._draw_supply()
            self._draw_factory()
            self._draw_money()
        else:
            for cv in (self.supply_canvas, self.factory_canvas, self.money_canvas):
                cv.draw_idle()
        self._show_notes()

    def _draw_supply(self):
        if not (self.cmp and self.cmp["available"]):
            return
        sv = self.cmp["supply"]
        sku = self.supply_sku.get()
        cells = sv["cells"]
        keys = [k for k in sv["keys"] if k[0] == sku]
        weeks = sv["weeks"]
        widx = {w: i for i, w in enumerate(weeks)}
        fig = self.supply_fig
        fig.clear()
        cmap = ListedColormap(CAT_COLORS)
        for j, (cid, side) in enumerate(((self.base, "base"), (self.alt, "alt"))):
            ax = fig.add_subplot(2, 1, j + 1)
            mat = np.zeros((len(keys), len(weeks)))
            sub = cells[(cells["case"] == cid) & (cells["sku_id"] == sku)]
            for r in sub.itertuples():
                i = keys.index((r.sku_id, r.region))
                cat = 0 if r.demand == 0 else 1
                if r.late:
                    cat = 2
                if r.unallocated:
                    cat = 3
                if r.backlog:
                    cat = 4
                mat[i, widx[r.request_week]] = cat
            ax.imshow(mat, aspect="auto", cmap=cmap, vmin=-0.5, vmax=4.5, interpolation="nearest")
            mk = sub[sub["min_supply_exact"]]
            for r in mk.itertuples():
                ax.plot(widx[r.request_week], keys.index((r.sku_id, r.region)), "o", ms=2.6,
                        mfc="#222" if r.cut_to_minimum else "none", mec="#222", mew=0.5)
            ax.set_yticks(range(len(keys)))
            ax.set_yticklabels([k[1] for k in keys], fontsize=7)
            step = max(1, len(weeks) // 12)
            ax.set_xticks(range(0, len(weeks), step))
            if j == 1:
                ax.set_xticklabels(weeks[::step], fontsize=6)
            else:
                ax.set_xticklabels([])
            ax.set_title(f"{'◎' if side == 'base' else '○'} {cid}（{sku}、要求週）", fontsize=8, loc="left")
        handles = [Patch(color=c, label=l) for c, l in zip(CAT_COLORS[1:], CAT_LABELS[1:])]
        fig.legend(handles=handles, loc="upper right", fontsize=7, ncol=4, frameon=False)
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        self.supply_canvas.draw_idle()
        tv = self.supply_totals
        tv.delete(*tv.get_children())
        for r in sv["totals"].itertuples():
            tv.insert("", "end", values=[r.case, f"{r.sku_id}:{r.region}", r.demand, r.in_scope,
                                         r.unallocated if sv["allocation"] or r.unallocated else "—", r.on_time, r.early,
                                         r.late, r.backlog, r.min_supply_exact_weeks, r.cut_to_minimum_weeks])

    def _draw_factory(self):
        if not (self.cmp and self.cmp["available"]):
            return
        fv = self.cmp["factory"]
        sku = self.factory_sku.get()
        fw = fv["weekly"]
        labels = fv["labels"]
        fig = self.factory_fig
        fig.clear()
        ax = fig.add_subplot(1, 1, 1)
        x = np.arange(len(labels))
        for k, (cid, color, off) in enumerate(((self.base, "#4c72b0", -0.2), (self.alt, "#dd8452", 0.2))):
            g = fw[(fw["case"] == cid) & (fw["product"] == sku)].sort_values("week_index")
            ax.bar(x + off, g["production_lots"], width=0.4, color=color, alpha=0.7,
                   label=f"{'◎' if k == 0 else '○'} {cid} 良品の生産")
            ax.step(x, pd.to_numeric(g["shippable_soft"], errors="coerce"), where="mid", color=color, lw=1.4,
                    label=f"{cid} 計画の上限（soft）")
            ax.step(x, pd.to_numeric(g["shippable_hard"], errors="coerce"), where="mid", color=color, lw=0.6,
                    alpha=0.35, ls="--", label=f"{cid} 物理の上限（hard、計画に使わない）")
        for w in fv["boundary_weeks"]:
            i = labels.index(w)
            ax.axvspan(i - 0.5, i + 0.5, color="#bbbbbb", alpha=0.35, lw=0)
        step = max(1, len(labels) // 14)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(labels[::step], fontsize=6)
        ax.set_ylabel("lot／週", fontsize=8)
        ax.set_title(f"{sku}：工場の週別の良品の生産と計画の上限（灰色の帯 ＝ 計画の境界の週）", fontsize=8, loc="left")
        ax.legend(fontsize=6, ncol=3, loc="lower center")
        fig.tight_layout()
        self.factory_canvas.draw_idle()
        for tv in (self.factory_weeks, self.factory_inv, self.factory_age):
            tv.delete(*tv.get_children())
        pw = fv["planned_output_weeks"]
        if len(pw):
            for r in pw[pw["product"] == sku].itertuples():
                self.factory_weeks.insert("", "end", values=[r.case, r.product, r.shippable_soft_values,
                                                             r.first_week_at_cap, r.last_week_at_cap, r.span_weeks,
                                                             r.span_weeks_in_report, r.span_weeks_outside_report,
                                                             r.weeks_at_cap, r.weeks_below_cap])
        for r in fv["inventory_summary"].itertuples():
            if r.product == sku:
                self.factory_inv.insert("", "end", values=[r.product, r.lot_weeks_base, r.lot_weeks_alt, r.max_base,
                                                           r.max_alt, r.end_base, r.end_alt])
        for r in fv["age"].itertuples():
            if r.product == sku:
                self.factory_age.insert("", "end", values=[r.case, r.product, r.deliveries, r.fifo_age_max,
                                                           r.over_max_age])

    def _draw_money(self):
        mv = self.cmp["money"]
        fig = self.money_fig
        fig.clear()
        ax = fig.add_subplot(1, 1, 1)
        c = mv["cumulative_report"]
        x = np.arange(len(c))
        ax.plot(x, c["cum_base"] / 1e6, color="#4c72b0", label=f"◎ {self.base}")
        ax.plot(x, c["cum_alt"] / 1e6, color="#dd8452", label=f"○ {self.alt}")
        step = max(1, len(c) // 12)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(list(c["week"])[::step], fontsize=6)
        ax.set_ylabel("百万円", fontsize=8)
        ax.set_title("報告期間の P0（固定費の前、消去後の連結）の累積", fontsize=8, loc="left")
        ax.legend(fontsize=7)
        fig.tight_layout()
        self.money_canvas.draw_idle()
        for period, df in (("報告期間", mv["report_by_product"]), ("全計画期間（参考）", mv["full_by_product"])):
            for r in df.itertuples():
                self.money_p0.insert("", "end", values=[period, "合計" if r.product == "*" else r.product,
                                                        V.fmt_yen(r.profit_r2_base), V.fmt_yen(r.profit_r2_alt),
                                                        V.fmt_yen(r.profit_r2_diff)])
        for r in mv["fixed_cost"]:
            fs = r.get("f_star_per_week", "")
            self.money_fc.insert("", "end", values=[
                r.get("cost_item") or "（固定費の表なし）",
                f"{r.get('paid_start_base', '')}〜{r.get('paid_end_base', '')}" if r.get("paid_start_base") else "",
                r.get("W_base", ""),
                f"{r.get('paid_start_alt', '')}〜{r.get('paid_end_alt', '')}" if r.get("paid_start_alt") else "",
                r.get("W_alt", ""), r.get("weekly_amount_base", ""), r.get("weekly_amount_alt", ""),
                V.fmt_yen(r.get("cost_base", "")), V.fmt_yen(r.get("cost_alt", "")),
                V.fmt_yen(r.get("P_after_base", "")), V.fmt_yen(r.get("P_after_alt", "")),
                V.fmt_yen(r.get("delta_P0", "")), r.get("delta_W", ""), V.fmt_yen(fs) if fs != "" else "",
                r.get("boundary_assumption", ""), r.get("boundary", ""), r.get("valuation_status", "")])

    # ── ④ ─────────────────────────────────────────────────────────────
    def _show_notes(self):
        t = self.notes
        t.configure(state="normal")
        t.delete("1.0", "end")
        if self.ws:
            t.insert("1.0", "\n".join("・" + n for n in V.notes(self.ws, self.base, self.alt, self.cmp)))
        t.configure(state="disabled")

    # ── for checks (S2) ────────────────────────────────────────────────
    def displayed_tables(self) -> Dict[str, pd.DataFrame]:
        """The tables as the widgets hold them (for the machine reconciliation with tool 2's outputs)."""
        def tv(t):
            cols = list(t["columns"])
            return pd.DataFrame([t.item(i, "values") for i in t.get_children()], columns=cols)
        return {"cases": tv(self.tree), "supply_totals": tv(self.supply_totals),
                "factory_weeks": tv(self.factory_weeks), "factory_inventory": tv(self.factory_inv),
                "factory_age": tv(self.factory_age), "money_p0": tv(self.money_p0),
                "money_fixed_cost": tv(self.money_fc),
                "notes": pd.DataFrame({"note": self.notes.get("1.0", "end").strip().splitlines()}),
                "inputs": pd.DataFrame({"line": self.inputs.get("1.0", "end").strip().splitlines()}),
                "message": pd.DataFrame({"message": [self.cmp_msg.cget("text")]})}


def launch(ws: Optional[str] = None, base: Optional[str] = None, alt: Optional[str] = None) -> None:
    """Entry point of `python -m main --cockpit-compare`."""
    root = tk.Tk()
    root.title("経営コックピット — 事業計画の比較")
    root.geometry("1440x900")
    if not ws:
        ws = filedialog.askdirectory(title="作業の置き場（output/cockpit_cases/<作業>）を選ぶ") or None
    CompareScreen(root, ws, base, alt)
    root.mainloop()
