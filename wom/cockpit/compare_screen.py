# -*- coding: utf-8 -*-
"""
wom/cockpit/compare_screen.py — 事業計画の比較の 1 画面（Tk ＋ matplotlib）
==========================================================================
RequestLetter_Cockpit_Stage3_Step2 B・Step3、設計書 §1・§2。起動：`python -m main --cockpit-compare [--ws <作業>]`。

4 つの区画：① 案の表（基準 ◎ と相手 ○ を選ぶ・複製・実行・並べる）、② 選んだ案の入力（変えるボタン）、
③ 比較（要点・供給・工場・金額と境目）、④ 読むときの注意。数字は `compare_view_model.py` が作り、この画面は描くだけ。
操作は `case_actions.py` を通す（入力の検査、文で返す、裏の実行は 1 本ずつ）。書く操作・実行・並べるの後は
自動で開き直す。裏のスレッドからは Tk を触らない（`after()` で queue を読む）。

`wom.cockpit` の下に置くのは、パッケージの `__init__.py` が日本語フォントを設定するため。
matplotlib は Figure ＋ FigureCanvasTkAgg を直接使う（pyplot・`matplotlib.use` を使わない）。
"""
from __future__ import annotations

import gc
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from wom.cockpit import case_actions as A
from wom.cockpit import cases as C
from wom.cockpit import compare_view_model as V

TITLE = "どの製品を、どの市場に、いつ投入し、生産量をどう整えるか"
CAT_COLORS = ["#ffffff", "#9fd49f", "#f2d16b", "#f4a259", "#d9534f"]
CAT_LABELS = ["需要なし", "当週に全量", "遅配あり", "未配分あり（③）", "配分後の未充足あり（⑤）"]
COL_WIDTH = {"ID": 44, "案の名前": 150, "親": 44, "供給の方針": 200, "未配分": 360, "未充足（期末）": 360,
             "P0（円、報告期間）": 130, "状態": 110}
WIDE = {"鍵": 210, "費目": 170, "境目の置き方": 330, "評価": 90}
POLL_MS = 200


class CompareScreen(ttk.Frame):
    def __init__(self, master, ws: Optional[str] = None, base: Optional[str] = None, alt: Optional[str] = None):
        super().__init__(master)
        self.master = master
        self.ws = ws
        self.base, self.alt = base, alt
        self.selected: Optional[str] = None
        self.cmp = None
        self.worker = A.Worker()
        self._write_buttons: List[ttk.Button] = []
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
        # status bar (bottom): progress of the background job and the message of the last operation
        sb = ttk.Frame(self)
        sb.pack(side="bottom", fill="x", padx=6, pady=(0, 4))
        self.progress = ttk.Label(sb, text="", foreground="#245")
        self.progress.pack(side="left")
        self.op_msg = ttk.Label(sb, text="", foreground="#245")
        self.op_msg.pack(side="left", padx=12)

        vp = ttk.PanedWindow(self, orient="vertical")
        vp.pack(fill="both", expand=True, padx=6, pady=4)
        # ① case table
        f1 = ttk.LabelFrame(vp, text="① 案の表（◎ 基準、○ 比べる相手）")
        b = ttk.Frame(f1)                      # the buttons first: the table shrinks, the buttons stay visible
        b.pack(side="bottom", fill="x")
        self.tree = ttk.Treeview(f1, show="headings", height=6, selectmode="browse")
        sx = ttk.Scrollbar(f1, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=sx.set)
        sx.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        ttk.Button(b, text="基準にする ◎", command=lambda: self._set_role("base")).pack(side="left", padx=2, pady=2)
        ttk.Button(b, text="比べる相手にする ○", command=lambda: self._set_role("alt")).pack(side="left", padx=2)
        ttk.Separator(b, orient="vertical").pack(side="left", fill="y", padx=8)
        for text, cmd in (("複製…", self._dlg_copy), ("実行", self.do_run), ("並べる", self.do_compare)):
            w = ttk.Button(b, text=text, command=cmd)
            w.pack(side="left", padx=2)
            self._write_buttons.append(w)
        self.pair_label = ttk.Label(b, text="")
        self.pair_label.pack(side="left", padx=10)
        vp.add(f1, weight=2)

        hp = ttk.PanedWindow(vp, orient="horizontal")
        # ② inputs
        f2 = ttk.LabelFrame(hp, text="② 選んだ案の入力")
        bb = ttk.Frame(f2)
        bb.pack(side="bottom", fill="x")
        ttk.Label(bb, text="入力を変える（変えたら実行し直す）：").grid(row=0, column=0, columnspan=3, sticky="w")
        for i, (text, cmd) in enumerate((("投入週…", self._dlg_launch), ("生産量…", self._dlg_output),
                                         ("シフト…", self._dlg_shifts), ("供給の方針…", self._dlg_policy),
                                         ("費用の前提…", self._dlg_cost), ("増産の有償の週…", self._dlg_raise))):
            w = ttk.Button(bb, text=text, command=cmd)
            w.grid(row=1 + i // 3, column=i % 3, sticky="we", padx=1, pady=1)
            self._write_buttons.append(w)
        for c in range(3):
            bb.columnconfigure(c, weight=1)
        self.inputs = tk.Text(f2, width=46, wrap="word", font=("Yu Gothic UI", 9))
        self.inputs.pack(fill="both", expand=True)
        hp.add(f2, weight=2)
        # ③ comparison
        f3 = ttk.LabelFrame(hp, text="③ 基準 ◎ と相手 ○ の比較")
        self.cmp_msg = ttk.Label(f3, text="", foreground="#a33")
        self.cmp_msg.pack(fill="x")
        self.nb = ttk.Notebook(f3)
        self.nb.pack(fill="both", expand=True)
        # the tabs do not ask for the full width of their wide tables (they still fill the space they get),
        # so ② keeps a readable width
        self.tab_summary, self.tab_supply, self.tab_factory, self.tab_money = (
            ttk.Frame(self.nb, width=760, height=420) for _ in range(4))
        for tab in (self.tab_summary, self.tab_supply, self.tab_factory, self.tab_money):
            tab.pack_propagate(False)
        self.nb.add(self.tab_summary, text="要点")
        self.nb.add(self.tab_supply, text="供給：鍵 × 要求週")
        self.nb.add(self.tab_factory, text="工場：生産と計画値")
        self.nb.add(self.tab_money, text="金額と境目")
        self.summary = tk.Text(self.tab_summary, wrap="word", font=("Yu Gothic UI", 10))
        self.summary.tag_configure("h", font=("Yu Gothic UI", 10, "bold"))
        self.summary.pack(fill="both", expand=True)
        self._build_supply_tab()
        self._build_factory_tab()
        self._build_money_tab()
        hp.add(f3, weight=5)
        vp.add(hp, weight=6)
        self._hp = hp
        # ④ notes
        f4 = ttk.LabelFrame(vp, text="④ 読むときの注意")
        self.notes = tk.Text(f4, height=6, wrap="word", font=("Yu Gothic UI", 9))
        self.notes.pack(fill="both", expand=True)
        vp.add(f4, weight=1)
        self.master.protocol("WM_DELETE_WINDOW", self._on_close)

    def _table(self, parent, cols: List[str], height=6) -> ttk.Treeview:
        fr = ttk.Frame(parent)
        fr.pack(fill="x")
        t = ttk.Treeview(fr, columns=cols, show="headings", height=height)
        for c in cols:
            t.heading(c, text=c)
            t.column(c, width=WIDE.get(c, max(80, min(220, 12 * len(c)))), anchor="e" if c not in cols[:2] else "w",
                     stretch=False)
        sx = ttk.Scrollbar(fr, orient="horizontal", command=t.xview)
        t.configure(xscrollcommand=sx.set)
        t.pack(fill="x")
        sx.pack(fill="x")
        return t

    @staticmethod
    def _heads(t: ttk.Treeview, texts: Dict[str, str]) -> None:
        for col, text in texts.items():
            t.heading(col, text=text)
            t.column(col, width=max(t.column(col, "width"), 11 * len(text)))

    def _build_supply_tab(self):
        bar = ttk.Frame(self.tab_supply)
        bar.pack(fill="x")
        self.diff_label = ttk.Label(bar, text="差（相手 − 基準）", font=("Yu Gothic UI", 9, "bold"))
        self.diff_label.pack(side="left")
        self.supply_diff = self._table(self.tab_supply, ["鍵", "需要", "当週", "早出し", "遅配", "未配分", "配分後の未充足",
                                                         "最低ちょうどの週"], height=3)
        bar2 = ttk.Frame(self.tab_supply)
        bar2.pack(fill="x")
        ttk.Label(bar2, text="SKU:").pack(side="left")
        self.supply_sku = ttk.Combobox(bar2, state="readonly", width=16)
        self.supply_sku.pack(side="left")
        self.supply_sku.bind("<<ComboboxSelected>>", lambda e: self._draw_supply())
        ttk.Label(bar2, text="  ● ＝ 最低供給量ちょうど（削って最低）  ○ ＝ 需要が最低供給量と同じ").pack(side="left")
        self.supply_fig = Figure(figsize=(9, 2.8), dpi=90)
        self.supply_canvas = FigureCanvasTkAgg(self.supply_fig, self.tab_supply)
        self.supply_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.supply_totals = self._table(self.tab_supply, ["案", "鍵", "需要", "供給の対象", "未配分（③）", "当週",
                                                           "早出し", "遅配", "配分後の未充足（⑤）", "最低ちょうどの週",
                                                           "うち削って最低"], height=6)

    def _build_factory_tab(self):
        bar = ttk.Frame(self.tab_factory)
        bar.pack(fill="x")
        ttk.Label(bar, text="工場（SKU）:").pack(side="left")
        self.factory_sku = ttk.Combobox(bar, state="readonly", width=30)
        self.factory_sku.pack(side="left")
        self.factory_sku.bind("<<ComboboxSelected>>", lambda e: self._draw_factory())
        self.factory_fig = Figure(figsize=(9, 2.8), dpi=90)
        self.factory_canvas = FigureCanvasTkAgg(self.factory_fig, self.tab_factory)
        self.factory_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.factory_weeks = self._table(self.tab_factory, [
            "案", "SKU", "計画の上限（良品）", "ちょうど作った最初の週", "最後の週", "その間の週数", "うち報告期間", "うち助走",
            "ちょうど作った週", "報告期間で上限を下回った週", "全計画で上限を下回った週（作らない週を含む）"], height=4)
        self.factory_inv = self._table(self.tab_factory, ["SKU", "inv_b", "inv_a", "max_b", "max_a", "end_b", "end_a"],
                                       height=2)
        self.factory_age = self._table(self.tab_factory, ["案", "SKU", "納品", "年齢の最大（週）", "52 週超"], height=2)
        self._heads(self.factory_inv, {"inv_b": "在庫 lot・週 基準", "inv_a": "在庫 lot・週 相手", "max_b": "最大 基準",
                                       "max_a": "最大 相手", "end_b": "期末 基準", "end_a": "期末 相手"})

    def _build_money_tab(self):
        self.money_fig = Figure(figsize=(9, 2.0), dpi=90)
        self.money_canvas = FigureCanvasTkAgg(self.money_fig, self.tab_money)
        self.money_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.money_p0 = self._table(self.tab_money, ["期間", "SKU", "p0_b", "p0_a", "差（相手 − 基準）"], height=4)
        self.money_fc = self._table(self.tab_money, [
            "費目", "ΔP0", "ΔW", "境目（円／週）", "境目の置き方", "評価", "paid_b", "w_b", "paid_a", "w_a", "wa_b", "wa_a",
            "cost_b", "cost_a", "after_b", "after_a", "控除後の差"], height=4)
        self._heads(self.money_p0, {"p0_b": "P0 基準", "p0_a": "P0 相手"})
        self._heads(self.money_fc, {"paid_b": "有償の週 基準", "w_b": "W 基準", "paid_a": "有償の週 相手", "w_a": "W 相手",
                                    "wa_b": "週額 基準", "wa_a": "週額 相手", "cost_b": "費用 基準", "cost_a": "費用 相手",
                                    "after_b": "控除後 基準（合計の行だけ）", "after_a": "控除後 相手（合計の行だけ）"})

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

    def select(self, cid: str) -> None:
        """Select a case (as a click on its row)."""
        self.selected = cid
        self.tree.selection_set(cid)
        self._show_inputs()

    # ── ② ─────────────────────────────────────────────────────────────
    def _show_inputs(self):
        t = self.inputs
        t.configure(state="normal")
        t.delete("1.0", "end")
        if not self.selected:
            t.configure(state="disabled")
            return
        d = V.case_inputs(self.ws, self.selected)
        self._inputs = d
        L = [f"{d['id']}　{d['name']}（親 {d['parent'] or '—'}）", f"状態：{d['state_display']}"]
        if d["state"] != C.ST_DONE and d["reason"]:
            L.append(f"理由：{d['reason']}")
        if d["run_message"]:
            L.append(f"道具の言葉：{V.message_gist(d['run_message'])}")
            L.append(f"ログ：{d['log_dir']}")
        L += ["", "■ 投入の表"] + [f"  {r['sku_id']}:{r['region']}  投入 {r['launch_week']}  定常 {r['steady_lots_per_week']} lot／週"
                                   f"（立ち上がり {r['ramp_weeks']} 週 × {r['ramp_ratio']}）" for r in d["entry_plan"]]
        L += ["", "■ 計画の生産量（工場 × SKU）"] + \
            [f"  {r['sku_id']} @ {r['node']}：{r['text']}" for r in d["capacity"]]
        L += ["", "■ 供給の方針"]
        p = d["policy"]
        L += ["  なし"] if not p else [f"  {p['short']}", f"  数量枠 {os.path.basename(p['allocation_file'] or '')}",
                                     f"  最低供給量 {os.path.basename(p['policy_file'] or '') or '—'}",
                                     f"  週の規則 {p['week_rule']}"]
        L += ["", "■ 費用の前提"]
        if not d["fixed_cost"]:
            L.append("  なし")
        for f in d["fixed_cost"]:
            L.append(f"  {f['label']}（{f['cost_item']}、{f['entity']}）：有償 {f['paid']}"
                     + ("（助走を含む）" if f["count_outside_report"] else "") + f"、週額 {f['weekly_amount']}")
        L += ["", f"※ {d['note']}"]
        t.insert("1.0", "\n".join(L))
        t.configure(state="disabled")

    # ── ③ ─────────────────────────────────────────────────────────────
    def _show_comparison(self):
        self.cmp = None
        for tv in (self.supply_diff, self.supply_totals, self.factory_weeks, self.factory_inv, self.factory_age,
                   self.money_p0, self.money_fc):
            tv.delete(*tv.get_children())
        for fig in (self.supply_fig, self.factory_fig, self.money_fig):
            fig.clear()
        self._set_text(self.summary, "")
        msg = ""
        if not (self.base and self.alt):
            msg = "基準 ◎ と相手 ○ を選ぶと、比較を出す"
        else:
            self.cmp = V.comparison(self.ws, self.base, self.alt)
            if not self.cmp["available"]:
                msg = f"比較 {self.base} → {self.alt}：{self.cmp['state']}。{self.cmp['reason']}（数字は出さない）"
            elif self.cmp["cost_stale"]:
                msg = f"比較 {self.base} → {self.alt}：{self.cmp['reason']}"
        self.cmp_msg.configure(text=msg)
        if self.cmp and self.cmp["available"]:
            self._heads_for_pair()
            skus = sorted({k[0] for k in self.cmp["supply"]["keys"]})
            facs = [c["label"] for c in self.cmp["factory"]["choices"]]
            for cb, vals in ((self.supply_sku, skus), (self.factory_sku, facs)):
                cb.configure(values=vals)
                if cb.get() not in vals:
                    cb.set(vals[0] if vals else "")
            self._draw_summary()
            self._draw_supply()
            self._draw_factory()
            self._draw_money()
        else:
            for cv in (self.supply_canvas, self.factory_canvas, self.money_canvas):
                cv.draw_idle()
        self._show_notes()

    def _heads_for_pair(self):
        b, a = f"基準（{self.base}）", f"相手（{self.alt}）"
        self.diff_label.configure(text=f"差（相手 {self.alt} − 基準 {self.base}）。差のある鍵だけ")
        self._heads(self.factory_inv, {"inv_b": f"在庫 lot・週 {b}", "inv_a": f"在庫 lot・週 {a}", "max_b": f"最大 {b}",
                                       "max_a": f"最大 {a}", "end_b": f"期末 {b}", "end_a": f"期末 {a}"})
        self._heads(self.money_p0, {"p0_b": f"P0 {b}", "p0_a": f"P0 {a}"})
        self._heads(self.money_fc, {"paid_b": f"有償の週 {b}", "w_b": f"W {b}", "paid_a": f"有償の週 {a}",
                                    "w_a": f"W {a}", "wa_b": f"週額 {b}", "wa_a": f"週額 {a}", "cost_b": f"費用 {b}",
                                    "cost_a": f"費用 {a}", "after_b": f"控除後 {b}（合計の行だけ）",
                                    "after_a": f"控除後 {a}（合計の行だけ）"})

    @staticmethod
    def _set_text(t: tk.Text, text: str, paragraphs: Optional[list] = None):
        t.configure(state="normal")
        t.delete("1.0", "end")
        if paragraphs:
            for p in paragraphs:
                t.insert("end", f"■ {p['title']}\n", "h")
                t.insert("end", p["text"] + "\n\n")
        else:
            t.insert("1.0", text)
        t.configure(state="disabled")

    def _draw_summary(self):
        paras = self.cmp["summary"]
        head = [{"title": f"基準 ◎ {self.base} → 相手 ○ {self.alt}",
                 "text": "今の数字を文章に並べたもの（どちらの案が上かは書かない）"}]
        self._set_text(self.summary, "", head + paras)

    def _draw_supply(self):
        if not (self.cmp and self.cmp["available"]):
            return
        sv = self.cmp["supply"]
        tv = self.supply_diff
        tv.delete(*tv.get_children())
        sd = self.cmp["supply_diff"]
        if sd.empty:
            tv.insert("", "end", values=["供給の差なし"] + [""] * 7)
        for r in sd.itertuples():
            tv.insert("", "end", values=[V.key_text(sv, r.sku_id, r.region), f"{r.demand:+,}", f"{r.on_time:+,}", f"{r.early:+,}",
                                         f"{r.late:+,}", f"{r.unallocated:+,}", f"{r.backlog:+,}",
                                         f"{r.min_supply_exact_weeks:+,}"])
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
            ax.set_yticklabels([V.key_text(sv, *k).split(":", 1)[1] for k in keys], fontsize=7)
            step = max(1, len(weeks) // 12)
            ax.set_xticks(range(0, len(weeks), step))
            if j == 1:
                ax.set_xticklabels(weeks[::step], fontsize=6)
            else:
                ax.set_xticklabels([])
            ax.set_title(f"{'◎ 基準' if side == 'base' else '○ 相手'} {cid}（{sku}、要求週）", fontsize=8, loc="left")
        handles = [Patch(color=c, label=l) for c, l in zip(CAT_COLORS[1:], CAT_LABELS[1:])]
        fig.legend(handles=handles, loc="upper right", fontsize=7, ncol=4, frameon=False)
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        self.supply_canvas.draw_idle()
        tv = self.supply_totals
        tv.delete(*tv.get_children())
        for r in sv["totals"].itertuples():
            tv.insert("", "end", values=[f"{'基準' if r.side == 'base' else '相手'} {r.case}", V.key_text(sv, r.sku_id, r.region),
                                         r.demand, r.in_scope, r.unallocated if sv["allocation"] or r.unallocated else "—",
                                         r.on_time, r.early, r.late, r.backlog, r.min_supply_exact_weeks,
                                         r.cut_to_minimum_weeks])

    def _draw_factory(self):
        if not (self.cmp and self.cmp["available"]):
            return
        fv = self.cmp["factory"]
        ch = {c["label"]: c for c in fv["choices"]}.get(self.factory_sku.get(), {})
        sku, fac = ch.get("sku", self.factory_sku.get()), ch.get("factory")
        fw = fv["weekly"]
        if fac is not None and "factory" in fw.columns:
            fw = fw[fw["factory"] == fac]
        labels = fv["labels"]
        fig = self.factory_fig
        fig.clear()
        ax = fig.add_subplot(1, 1, 1)
        x = np.arange(len(labels))
        for k, (cid, color, off) in enumerate(((self.base, "#4c72b0", -0.2), (self.alt, "#dd8452", 0.2))):
            g = fw[(fw["case"] == cid) & (fw["product"] == sku)].sort_values("week_index")
            who = "◎ 基準" if k == 0 else "○ 相手"
            ax.bar(x + off, g["production_lots"], width=0.4, color=color, alpha=0.7, label=f"{who} {cid} 良品の生産")
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
        src = "エンジンの値" if fv.get("capacity_from_engine") else "capacity_plan.csv の値（エンジンの値ではない）"
        ax.set_title(f"{self.factory_sku.get()}：工場の週別の良品の生産と計画の上限（{src}。灰色の帯 ＝ {V.EDGE_WEEKS_TEXT}）",
                     fontsize=8, loc="left")
        ax.legend(fontsize=6, ncol=3, loc="lower center")
        fig.tight_layout()
        self.factory_canvas.draw_idle()
        for tv in (self.factory_weeks, self.factory_inv, self.factory_age):
            tv.delete(*tv.get_children())
        pw = fv["planned_output_weeks"]
        if len(pw):
            sel = pw[(pw["product"] == sku) & ((pw["factory"] == fac) if fac is not None else True)]
            for r in sel.itertuples():
                who = "基準" if r.case == self.base else "相手"
                if getattr(r, "row", "全体") == "値ごと":
                    who = f"　うち {r.planned_first_week}〜{r.planned_last_week}（{r.planned_weeks} 週）"
                self.factory_weeks.insert("", "end", values=[
                    f"{who} {r.case}", r.product, r.shippable_soft_values, r.first_week_at_cap, r.last_week_at_cap,
                    r.span_weeks, r.span_weeks_in_report, r.span_weeks_outside_report, r.weeks_at_cap,
                    r.weeks_below_cap_in_report, r.weeks_below_cap])
        for r in fv["inventory_summary"].itertuples():
            if r.product == sku:
                self.factory_inv.insert("", "end", values=[r.product, f"{r.lot_weeks_base:,}", f"{r.lot_weeks_alt:,}",
                                                           r.max_base, r.max_alt, r.end_base, r.end_alt])
        for r in fv["age"].itertuples():
            if r.product == sku:
                who = "基準" if r.case == self.base else "相手"
                self.factory_age.insert("", "end", values=[f"{who} {r.case}", r.product, r.deliveries, r.fifo_age_max,
                                                           r.over_max_age])

    def _draw_money(self):
        mv = self.cmp["money"]
        fig = self.money_fig
        fig.clear()
        ax = fig.add_subplot(1, 1, 1)
        c = mv["cumulative_report"]
        x = np.arange(len(c))
        ax.plot(x, c["cum_base"] / 1e6, color="#4c72b0", label=f"◎ 基準 {self.base}")
        ax.plot(x, c["cum_alt"] / 1e6, color="#dd8452", label=f"○ 相手 {self.alt}")
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
        if mv["hidden"]:
            self.money_fc.insert("", "end", values=[f"費用の前提が変わった：{V.RECOMPARE}"] + [""] * 16)
            return
        if mv["no_fixed_cost_table"] and not mv["fixed_cost"]:
            self.money_fc.insert("", "end", values=["（費用の前提なし：採算の順位は保留）"] + [""] * 16)
        for r in mv["fixed_cost"]:
            fs = r.get("f_star_per_week", "")
            paid = lambda s: f"{r.get(f'paid_start_{s}', '')}〜{r.get(f'paid_end_{s}', '')}" if r.get(f"paid_start_{s}") else ""
            self.money_fc.insert("", "end", values=[
                r["label"], V.fmt_yen(r.get("delta_P0", "")), r.get("delta_W", ""), V.fmt_yen(fs) if fs != "" else "",
                r.get("boundary_assumption", ""), r.get("valuation_status", ""),
                paid("base"), r.get("W_base", ""), paid("alt"), r.get("W_alt", ""),
                r.get("weekly_amount_base", ""), r.get("weekly_amount_alt", ""),
                V.fmt_yen(r.get("cost_base", "")), V.fmt_yen(r.get("cost_alt", "")),
                V.fmt_yen(r.get("P_after_base", "")), V.fmt_yen(r.get("P_after_alt", "")),
                V.fmt_yen(r.get("delta_P_after", ""))], tags=("total",) if r.get("cost_item") == "合計" else ())
        self.money_fc.tag_configure("total", background="#eef3fb")

    # ── ④ ─────────────────────────────────────────────────────────────
    def _show_notes(self):
        self._set_text(self.notes, "\n".join("・" + n for n in V.notes(self.ws, self.base, self.alt, self.cmp))
                       if self.ws else "")

    # ── 操作（ボタンとダイアログはこれを呼ぶ。テストもこれを呼ぶ） ─────────────────
    def _report(self, r: A.Result, refresh: bool = True) -> A.Result:
        self.op_msg.configure(text=r.message, foreground="#245" if r.ok else "#b22")
        if refresh and r.ok:
            self.reopen()
        return r

    def _need_selected(self) -> Optional[A.Result]:
        if not self.selected:
            return self._report(A.Result(False, "案が選ばれていない。① で案を選ぶ"), refresh=False)
        return None

    def do_copy(self, name: str) -> A.Result:
        n = self._need_selected()
        if n:
            return n
        r = A.copy(self.ws, self.selected, name)
        if r.ok:
            self.selected = r.data["id"]
        return self._report(r)

    def do_set_launch_week(self, sku: str, region: str, week: str) -> A.Result:
        return self._need_selected() or self._report(A.set_launch_week(self.ws, self.selected, sku, region, week))

    def do_set_planned_output(self, sku: str, node: Optional[str], value: str, from_week: str = "",
                              to_week: str = "") -> A.Result:
        return self._need_selected() or self._report(
            A.set_planned_output(self.ws, self.selected, sku, node, value, from_week, to_week))

    def do_set_shifts(self, sku: str, node: str, value: str, from_week: str = "", to_week: str = "") -> A.Result:
        return self._need_selected() or self._report(
            A.set_shifts(self.ws, self.selected, sku, node, value, from_week, to_week))

    def do_set_policy(self, **kw) -> A.Result:
        return self._need_selected() or self._report(A.set_policy(self.ws, self.selected, **kw))

    def do_set_fixed_cost(self, rows: List[dict]) -> A.Result:
        return self._need_selected() or self._report(A.set_fixed_cost(self.ws, self.selected, rows))

    def do_apply_raise_weeks(self, candidate: dict, entity: str, currency: str) -> A.Result:
        return self._need_selected() or self._report(
            A.apply_raise_weeks(self.ws, self.selected, candidate, entity, currency))

    def do_run(self) -> A.Result:
        n = self._need_selected()
        if n:
            return n
        gc.collect()   # Tk images no longer used are freed here, not later from the background thread
        r = self.worker.start_run(self.ws, self.selected)
        self._report(r, refresh=False)
        if r.ok:
            self._busy(True)
            self.after(POLL_MS, self._poll)
        return r

    def do_compare(self) -> A.Result:
        gc.collect()   # Tk images no longer used are freed here, not later from the background thread
        r = self.worker.start_compare(self.ws, self.base, self.alt)
        self._report(r, refresh=False)
        if r.ok:
            self._busy(True)
            self.after(POLL_MS, self._poll)
        return r

    def _busy(self, on: bool):
        for w in self._write_buttons:
            w.state(["disabled"] if on else ["!disabled"])

    def _poll(self):
        last = None
        for e in self.worker.poll():
            last = e
            if e["kind"] == "progress" and e.get("event") in ("start", "end"):
                self.progress.configure(text=f"{e['label'] if 'label' in e else ''}：{e.get('index')}/{e.get('total')} 段目"
                                             f"{'' if e['event'] == 'start' else ' 済み'}（{e.get('elapsed', 0):.0f} 秒）")
            elif e["kind"] == "start":
                self.progress.configure(text=e["message"])
            elif e["kind"] in ("done", "error"):
                self.progress.configure(text="")
                self._busy(False)
                self.reopen()
                if e["kind"] == "done" and e["job"] == "compare":
                    self.nb.select(self.tab_summary)
                self._report(A.Result(e["kind"] == "done", e["message"]), refresh=False)
        if self.worker.busy or (last and last["kind"] not in ("done", "error")) or not self.worker.q.empty():
            self.after(POLL_MS, self._poll)

    def wait_idle(self, timeout: float = 600.0) -> None:
        """For checks: let the background job finish and the screen read its events."""
        import time
        t0 = time.time()
        while (self.worker.busy or not self.worker.q.empty()) and time.time() - t0 < timeout:
            self.update()
            time.sleep(0.1)
        self._poll()
        self.update()

    def _on_close(self):
        if self.worker.busy:
            if not messagebox.askyesno("実行中", "案の実行（または比較）が動いています。閉じますか？\n"
                                       "閉じると、その案に「実行中」の記録が残ります（直し方は ④ に出ます）。"):
                return
        self.master.destroy()

    # ── ダイアログ ────────────────────────────────────────────────────
    def _dialog(self, title: str) -> tk.Toplevel:
        d = tk.Toplevel(self)
        d.title(title)
        d.transient(self.master)
        return d

    def _dlg_copy(self):
        if self._need_selected():
            return
        d = self._dialog(f"{self.selected} を複製する")
        ttk.Label(d, text="新しい案の名前").grid(row=0, column=0, padx=6, pady=6)
        e = ttk.Entry(d, width=30)
        e.grid(row=0, column=1, padx=6)
        ttk.Button(d, text="複製", command=lambda: (self.do_copy(e.get()).ok and d.destroy())).grid(row=1, column=1, pady=6)

    def _dlg_launch(self):
        if self._need_selected():
            return
        d = self._dialog(f"{self.selected}：投入週を変える")
        rows = self._inputs["entry_plan"]
        ttk.Label(d, text="鍵（製品:販売先）").grid(row=0, column=0, padx=6, pady=4)
        cb = ttk.Combobox(d, state="readonly", width=34, values=[f"{r['sku_id']}:{r['region']}" for r in rows])
        cb.grid(row=0, column=1, padx=6)
        ttk.Label(d, text="投入週（例 2027-W27）").grid(row=1, column=0, padx=6, pady=4)
        e = ttk.Entry(d, width=12)
        e.grid(row=1, column=1, sticky="w", padx=6)

        def fill(_e=None):
            r = rows[cb.current()]
            e.delete(0, "end")
            e.insert(0, r["launch_week"])
        cb.bind("<<ComboboxSelected>>", fill)

        def ok():
            if cb.current() < 0:
                return self._report(A.Result(False, "鍵を選ぶ"), refresh=False)
            r = rows[cb.current()]
            if self.do_set_launch_week(r["sku_id"], r["region"], e.get()).ok:
                d.destroy()
        ttk.Button(d, text="変える", command=ok).grid(row=2, column=1, pady=6, sticky="e")

    def _dlg_output(self):
        if self._need_selected():
            return
        d = self._dialog(f"{self.selected}：計画の生産量を変える")
        rows = self._inputs["capacity"]
        ttk.Label(d, text="工場 × SKU").grid(row=0, column=0, padx=6, pady=4)
        cb = ttk.Combobox(d, state="readonly", width=34,
                          values=[f"{r['sku_id']} @ {r['node']}（max_supply {r['max_supply']}）" for r in rows])
        cb.grid(row=0, column=1, padx=6)
        ttk.Label(d, text="cap_soft").grid(row=1, column=0, padx=6, pady=4)
        e = ttk.Entry(d, width=10)
        e.grid(row=1, column=1, sticky="w", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda _e: (e.delete(0, "end"), e.insert(0, rows[cb.current()]["cap_soft_main"])))
        fw_, tw_ = self._range_fields(d, 2)

        def ok():
            if cb.current() < 0:
                return self._report(A.Result(False, "工場 × SKU を選ぶ"), refresh=False)
            r = rows[cb.current()]
            if self.do_set_planned_output(r["sku_id"], r["node"], e.get(), fw_.get(), tw_.get()).ok:
                d.destroy()
        ttk.Button(d, text="変える", command=ok).grid(row=4, column=1, pady=6, sticky="e")

    def _range_fields(self, d, row: int):
        """始まり・終わり（両端を含む。両方空欄なら全週）。段 4 A5."""
        ttk.Label(d, text="始まりの週（空欄＝全週）").grid(row=row, column=0, padx=6, pady=2, sticky="w")
        a = ttk.Entry(d, width=10)
        a.grid(row=row, column=1, sticky="w", padx=6)
        ttk.Label(d, text="終わりの週（両端を含む）").grid(row=row + 1, column=0, padx=6, pady=2, sticky="w")
        b = ttk.Entry(d, width=10)
        b.grid(row=row + 1, column=1, sticky="w", padx=6)
        return a, b

    def _dlg_shifts(self):
        if self._need_selected():
            return
        if not self._inputs.get("has_calendar"):
            return self._report(A.Result(False, "このモデルには操業カレンダー（operating_calendar.csv）が無い。"
                                                "計画の生産量は「生産量…」で変える"), refresh=False)
        d = self._dialog(f"{self.selected}：シフトの数を変える（休業の週は変えない）")
        rows = [r for r in self._inputs["capacity"] if r.get("calendar")]
        ttk.Label(d, text="工場 × SKU").grid(row=0, column=0, padx=6, pady=4)
        cb = ttk.Combobox(d, state="readonly", width=40,
                          values=[f"{r['sku_id']} @ {r['node']}（今 {r['shifts']} シフト）" for r in rows])
        cb.grid(row=0, column=1, padx=6)
        ttk.Label(d, text=f"シフトの数（1〜{C.MAX_SHIFTS}）").grid(row=1, column=0, padx=6, pady=4)
        e = ttk.Entry(d, width=10)
        e.grid(row=1, column=1, sticky="w", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda _e: (e.delete(0, "end"), e.insert(0, rows[cb.current()]["shifts_main"])))
        fw_, tw_ = self._range_fields(d, 2)

        def ok():
            if cb.current() < 0:
                return self._report(A.Result(False, "工場 × SKU を選ぶ"), refresh=False)
            r = rows[cb.current()]
            if self.do_set_shifts(r["sku_id"], r["node"], e.get(), fw_.get(), tw_.get()).ok:
                d.destroy()
        ttk.Button(d, text="変える", command=ok).grid(row=4, column=1, pady=6, sticky="e")

    def _dlg_policy(self):
        if self._need_selected():
            return
        d = self._dialog(f"{self.selected}：供給の方針を変える")
        mode = tk.StringVar(value="files" if self._inputs["policy"] else "none")
        ttk.Radiobutton(d, text="なし", variable=mode, value="none").grid(row=0, column=0, sticky="w", padx=6)
        ttk.Radiobutton(d, text="ファイルで渡した方針", variable=mode, value="files").grid(row=0, column=1, sticky="w")
        ents = {}
        p = self._inputs["policy"] or {}
        case_dir = C.case_dir(self.ws, self.selected)
        for i, (k, label) in enumerate((("allocation_file", "数量枠"), ("policy_file", "最低供給量"),
                                        ("knowledge_file", "知識（任意）")), start=1):
            ttk.Label(d, text=label).grid(row=i, column=0, sticky="w", padx=6)
            e = ttk.Entry(d, width=52)
            if p.get(k):
                e.insert(0, os.path.join(case_dir, p[k]))
            e.grid(row=i, column=1, padx=4)
            ttk.Button(d, text="選ぶ…", command=lambda e=e: (e.delete(0, "end"), e.insert(0, filedialog.askopenfilename(
                filetypes=[("CSV / JSON", "*.csv *.json"), ("すべて", "*.*")])))).grid(row=i, column=2, padx=4)
            ents[k] = e
        ttk.Label(d, text="週の規則").grid(row=4, column=0, sticky="w", padx=6)
        rule = ttk.Combobox(d, state="readonly", width=30, values=list(V.WEEK_RULE_SHORT))
        rule.set(p.get("week_rule") or "trim_to_capacity_latest")
        rule.grid(row=4, column=1, sticky="w", padx=4)
        ttk.Label(d, text="未配分の扱いの注記（任意）").grid(row=5, column=0, sticky="w", padx=6)
        note = ttk.Entry(d, width=52)
        note.insert(0, p.get("unallocated_note") or "")
        note.grid(row=5, column=1, padx=4)

        def ok():
            if mode.get() == "none":
                r = self.do_set_policy(none=True)
            else:
                r = self.do_set_policy(allocation_file=ents["allocation_file"].get().strip(),
                                       policy_file=ents["policy_file"].get().strip(), week_rule=rule.get(),
                                       knowledge_file=ents["knowledge_file"].get().strip(),
                                       unallocated_note=note.get().strip())
            if r.ok:
                d.destroy()
        ttk.Button(d, text="変える", command=ok).grid(row=6, column=1, pady=6, sticky="e")

    def _dlg_cost(self):
        if self._need_selected():
            return
        d = self._dialog(f"{self.selected}：費用の前提を変える（週額が空欄 ＝ 未設定）")
        cols = ["cost_item", "display_name", "entity", "paid_start_week", "paid_end_week", "weekly_amount", "currency",
                "count_outside_report", "note"]
        heads = ["コード", "表示名", "法人", "有償の最初の週", "有償の最後の週", "週額", "通貨", "助走を含む", "備考"]
        rows = [{"cost_item": f["cost_item"], "display_name": f["display_name"], "entity": f["entity"],
                 "paid_start_week": f["paid_start_week"], "paid_end_week": f["paid_end_week"],
                 "weekly_amount": f["weekly_amount_raw"], "currency": f["currency"],
                 "count_outside_report": "1" if f["count_outside_report"] else "", "note": f["note"]}
                for f in self._inputs["fixed_cost"]]
        tv = ttk.Treeview(d, columns=cols, show="headings", height=5)
        for c, h in zip(cols, heads):
            tv.heading(c, text=h)
            tv.column(c, width=110 if c != "note" else 260)
        tv.grid(row=0, column=0, columnspan=4, padx=6, pady=6)
        form = ttk.Frame(d)
        form.grid(row=1, column=0, columnspan=4, sticky="w", padx=6)
        ents = {}
        for i, (c, h) in enumerate(zip(cols, heads)):
            ttk.Label(form, text=h).grid(row=i // 3, column=(i % 3) * 2, sticky="e", padx=3, pady=2)
            if c == "count_outside_report":
                v = tk.BooleanVar()
                w = ttk.Checkbutton(form, variable=v)
                w.var = v
            else:
                w = ttk.Entry(form, width=18 if c != "note" else 40)
            w.grid(row=i // 3, column=(i % 3) * 2 + 1, sticky="w", padx=3)
            ents[c] = w

        def refresh():
            tv.delete(*tv.get_children())
            for r in rows:
                tv.insert("", "end", values=[r[c] for c in cols])

        def pick(_e=None):
            s = tv.selection()
            if not s:
                return
            r = rows[tv.index(s[0])]
            for c in cols:
                if c == "count_outside_report":
                    ents[c].var.set(r[c] == "1")
                else:
                    ents[c].delete(0, "end")
                    ents[c].insert(0, r[c])
        tv.bind("<<TreeviewSelect>>", pick)

        def form_row():
            return {c: ("1" if ents[c].var.get() else "") if c == "count_outside_report" else ents[c].get().strip()
                    for c in cols}

        def add():
            rows.append(form_row())
            refresh()

        def update():
            s = tv.selection()
            if s:
                rows[tv.index(s[0])] = form_row()
                refresh()

        def remove():
            s = tv.selection()
            if s:
                rows.pop(tv.index(s[0]))
                refresh()

        def save():
            if self.do_set_fixed_cost(rows).ok:
                d.destroy()
        bf = ttk.Frame(d)
        bf.grid(row=2, column=0, columnspan=4, pady=6)
        for text, cmd in (("行を足す", add), ("選んだ行を直す", update), ("選んだ行を消す", remove), ("保存する", save)):
            ttk.Button(bf, text=text, command=cmd).pack(side="left", padx=4)
        refresh()

    def _dlg_raise(self):
        if self._need_selected():
            return
        cands = A.raise_week_candidates(self.ws, self.selected)
        d = self._dialog(f"{self.selected}：増産の有償の週を入れる（確かめてから「入れる」）")
        if not cands:
            ttk.Label(d, text="親の案より計画の生産量を上げた週が無く、この案を含む比較も無い。"
                              "生産量を上げるか、先に「並べる」で比べると候補に出る",
                      wraplength=420).pack(padx=10, pady=10)
            return
        lb = tk.Listbox(d, width=100, height=min(8, len(cands)))
        for c in cands:
            if c.get("kind") == "raised":
                act = ("工場が上限ちょうど作った週は比べると出る" if c["at_cap"] is None
                       else f"そのうち工場が上限ちょうど作った週 {c['at_cap']}")
                cl = f"、うち休業 {len(c['closed_inside'])} 週" if c.get("closed_inside") else ""
                lb.insert("end", f"親より上げた週　{c['sku']} @ {c['factory']}（{c['cap']}）：{c['first']}〜{c['last']}　"
                                 f"{c['span']} 週（報告期間 {c['in_report']}・外 {c['outside']}{cl}）、{act}")
                continue
            lb.insert("end", f"ちょうど作った週　{c['sku']} @ {c['factory']}（上限 {c['cap']}）：{c['first']}〜{c['last']}　"
                             f"{c['span']} 週（報告期間 {c['in_report']}・助走 {c['outside']}、途中で下回った週 {c['gaps']}）"
                             f"　比較 {c['compare']}")
        lb.pack(padx=6, pady=6)
        f = ttk.Frame(d)
        f.pack()
        ex = self._inputs["fixed_cost"]
        ttk.Label(f, text="法人").pack(side="left")
        ent = ttk.Entry(f, width=10)
        ent.insert(0, ex[0]["entity"] if ex else "")
        ent.pack(side="left", padx=4)
        ttk.Label(f, text="通貨").pack(side="left")
        cur = ttk.Entry(f, width=6)
        cur.insert(0, ex[0]["currency"] if ex else "")
        cur.pack(side="left", padx=4)

        def ok():
            s = lb.curselection()
            if not s:
                return self._report(A.Result(False, "候補を 1 つ選ぶ"), refresh=False)
            if self.do_apply_raise_weeks(cands[s[0]], ent.get().strip(), cur.get().strip()).ok:
                d.destroy()
        ttk.Button(d, text="入れる（週額は未設定のまま）", command=ok).pack(pady=6)

    # ── for checks (S2・S4) ─────────────────────────────────────────────
    def displayed_tables(self) -> Dict[str, pd.DataFrame]:
        """The tables as the widgets hold them (for the machine reconciliation with tool 2's outputs).
        Column names are the headings shown on the screen."""
        def tv(t):
            cols = list(t["columns"])
            heads = [t.heading(c, "text") or c for c in cols]
            return pd.DataFrame([t.item(i, "values") for i in t.get_children()], columns=heads)
        return {"cases": tv(self.tree), "supply_diff": tv(self.supply_diff), "supply_totals": tv(self.supply_totals),
                "factory_weeks": tv(self.factory_weeks), "factory_inventory": tv(self.factory_inv),
                "factory_age": tv(self.factory_age), "money_p0": tv(self.money_p0),
                "money_fixed_cost": tv(self.money_fc),
                "summary": pd.DataFrame({"line": self.summary.get("1.0", "end").strip().splitlines()}),
                "notes": pd.DataFrame({"note": self.notes.get("1.0", "end").strip().splitlines()}),
                "inputs": pd.DataFrame({"line": self.inputs.get("1.0", "end").strip().splitlines()}),
                "message": pd.DataFrame({"message": [self.cmp_msg.cget("text")]}),
                "operation": pd.DataFrame({"message": [self.op_msg.cget("text")]})}


def launch(ws: Optional[str] = None, base: Optional[str] = None, alt: Optional[str] = None) -> None:
    """Entry point of `python -m main --cockpit-compare`."""
    root = tk.Tk()
    root.title("経営コックピット — 事業計画の比較")
    root.geometry("1440x900")
    if not ws:
        ws = filedialog.askdirectory(title="作業の置き場（output/cockpit_cases/<作業>）を選ぶ") or None
    CompareScreen(root, ws, base, alt)
    root.mainloop()
