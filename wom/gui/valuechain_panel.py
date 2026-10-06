# -*- coding: utf-8 -*-
"""
Management の中の「Value Chain」（RequestLetter_StageD_Phase1 Part 2）

段階 D 第 1 回の台帳（wom/valuechain）を、今の計画（Planning Engine の結果）から作って表示する。
計画をやり直さない（GUI が持っている計画の木から作る。計算は別のスレッド）。

- 上の帯：V3 の「消去前（第 1 回）／消去後（第 2 回）」の切り替えに合わせた文言と、計画 ID・報告の開始週・
  為替の表（RequestLetter_StageD_Phase2。既定は消去後。消去後の表には「内部の未実現利益の増減」の列を出し、
  消去前の利益 − この列 ＝ 消去後の利益）
- 隅のボタン：未実現利益（週末残高）。押すと法人・ノード別の一覧
- 切り替え：V1（ノード）・V2（法人）・V3（連結）、法人・ノード（チャネル）の絞り込み、単週／累計、
  通貨（HQ の報告通貨／国際共通の評価通貨／現地通貨）。**元の金額は書き換えない**（表示の換算だけ）。
  「現地の法人の利益を換算した値」は、取得原価を引き継ぐ管理評価とは別の列にだけ出す（設計 §5.5）
- 隅のボタン：未評価の件数・未設定価格の件数・為替（最初の週のレートを使った件数）。押すと一覧
- 外部チャネル（②）：「グループの外部売上（卸）」「外部チャネルの消費者への販売（観測）」
  「外部チャネルの在庫（観測）」を別の行で出す
- 今の計画の台帳でなければ数字を出さない（計画 ID で確かめる。PPC の表示と同じ規則）
"""
from __future__ import annotations

import math
import os
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

BG_DARK, BG_MID, BG_LIGHT = "#1E2A38", "#253347", "#2E3F55"
FG_WHITE, FG_ACC = "#ECEFF1", "#64B5F6"
ROUND_LABEL = "内部の未実現利益の消去前（第 1 回）"
ROUND2_LABEL = "内部の未実現利益の消去後（第 2 回）"

CUR_KEYS = {"HQ": "hq", "共通": "common", "現地": "func"}


def _fmt(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:,.0f}"


class ValueChainPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._current_run_id = ""
        self._result = None          # the ledger shown (dict from build_ledger + extras)
        self._building_for = ""
        self._round_var = None
        self._build_ui()
        self.clear("Planning Engine を実行すると、今の計画から台帳を作って表示します")

    # ── UI ────────────────────────────────────────────────────────
    def _build_ui(self):
        self._band_var = tk.StringVar(value=ROUND_LABEL)
        self._band = tk.Label(self, textvariable=self._band_var, bg=BG_DARK, fg="#FFD740", anchor="w",
                              justify="left", font=("Segoe UI", 9, "bold"), wraplength=1400)
        self._band.pack(fill="x", padx=8, pady=(6, 2))
        # wrap the band (and the note) to the panel's width, so nothing is cut off on the right
        self.bind("<Configure>", lambda e: (self._band.configure(wraplength=max(400, e.width - 24)),
                                            self._note.configure(wraplength=max(300, e.width - 420))))

        bar = tk.Frame(self, bg=BG_DARK)
        bar.pack(fill="x", padx=8, pady=2)
        self._view_var = tk.StringVar(value="V3")
        for v, txt in (("V1", "V1 ノード・区間"), ("V2", "V2 法人"), ("V3", "V3 連結")):
            tk.Radiobutton(bar, text=txt, value=v, variable=self._view_var, command=self._refresh,
                           bg=BG_DARK, fg=FG_WHITE, selectcolor=BG_LIGHT, activebackground=BG_DARK,
                           font=("Segoe UI", 9)).pack(side="left", padx=2)
        # V3 only: before / after the elimination of the internal unrealized profit
        self._round_var = tk.StringVar(value="r2")
        self._round_rbs = []
        tk.Label(bar, text=" (", bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 9)).pack(side="left")
        for v, txt in (("r2", "消去後"), ("r1", "消去前")):
            rb = tk.Radiobutton(bar, text=txt, value=v, variable=self._round_var, command=self._refresh,
                                bg=BG_DARK, fg="#FFD740", selectcolor=BG_LIGHT, activebackground=BG_DARK,
                                font=("Segoe UI", 9))
            rb.pack(side="left")
            self._round_rbs.append(rb)
        tk.Label(bar, text=")", bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(bar, text="  法人:", bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 9)).pack(side="left")
        self._ent_var = tk.StringVar(value="（すべて）")
        self._ent_cb = ttk.Combobox(bar, textvariable=self._ent_var, width=16, state="readonly")
        self._ent_cb.pack(side="left")
        self._ent_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_entity())
        tk.Label(bar, text="  ノード／チャネル:", bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 9)).pack(side="left")
        self._node_var = tk.StringVar(value="（すべて）")
        self._node_cb = ttk.Combobox(bar, textvariable=self._node_var, width=30, state="readonly")
        self._node_cb.pack(side="left")
        self._node_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh())
        self._period_var = tk.StringVar(value="wk")
        tk.Label(bar, text="  期間:", bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 9)).pack(side="left")
        for v, txt in (("wk", "単週"), ("cum", "累計")):
            tk.Radiobutton(bar, text=txt, value=v, variable=self._period_var, command=self._refresh,
                           bg=BG_DARK, fg=FG_WHITE, selectcolor=BG_LIGHT, activebackground=BG_DARK,
                           font=("Segoe UI", 9)).pack(side="left")
        self._cur_var = tk.StringVar(value="HQ")
        tk.Label(bar, text="  通貨:", bg=BG_DARK, fg=FG_WHITE, font=("Segoe UI", 9)).pack(side="left")
        for v in ("HQ", "共通", "現地"):
            tk.Radiobutton(bar, text=v, value=v, variable=self._cur_var, command=self._refresh,
                           bg=BG_DARK, fg=FG_WHITE, selectcolor=BG_LIGHT, activebackground=BG_DARK,
                           font=("Segoe UI", 9)).pack(side="left")
        # corner buttons (their own row, right-aligned, beside the note)
        row2 = tk.Frame(self, bg=BG_DARK)
        row2.pack(fill="x", padx=8)
        corner = tk.Frame(row2, bg=BG_DARK)
        corner.pack(side="right")
        self._btn_unvalued = tk.Button(corner, text="未評価 —", command=self._show_unvalued,
                                       bg=BG_LIGHT, fg="#FF8A80", relief="flat", font=("Segoe UI", 8))
        self._btn_missing = tk.Button(corner, text="未設定価格 —", command=self._show_missing,
                                      bg=BG_LIGHT, fg="#FFD740", relief="flat", font=("Segoe UI", 8))
        self._btn_fx = tk.Button(corner, text="為替：最初の週 —", command=self._show_fx,
                                 bg=BG_LIGHT, fg="#81D4FA", relief="flat", font=("Segoe UI", 8))
        self._btn_unreal = tk.Button(corner, text="未実現利益 —", command=self._show_unrealized,
                                     bg=BG_LIGHT, fg="#CE93D8", relief="flat", font=("Segoe UI", 8))
        for b in (self._btn_unreal, self._btn_unvalued, self._btn_missing, self._btn_fx):
            b.pack(side="left", padx=2)

        self._note_var = tk.StringVar(value="")
        self._note = tk.Label(row2, textvariable=self._note_var, bg=BG_DARK, fg="#90A4AE", anchor="w",
                              justify="left", font=("Segoe UI", 8), wraplength=900)
        self._note.pack(side="left", fill="x", expand=True)

        body = tk.PanedWindow(self, orient="horizontal", bg=BG_DARK, sashwidth=4)
        body.pack(fill="both", expand=True, padx=8, pady=4)
        left = tk.Frame(body, bg=BG_DARK)
        body.add(left, minsize=640, width=900)
        self._tree = ttk.Treeview(left, show="headings", height=16)
        vsb = ttk.Scrollbar(left, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(left, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        right = tk.Frame(body, bg=BG_DARK)
        body.add(right, minsize=380)
        self._fig = Figure(figsize=(5, 3), dpi=90, facecolor=BG_DARK)
        self._canvas = FigureCanvasTkAgg(self._fig, master=right)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        ch = tk.LabelFrame(self, text="  外部の販売チャネル（②）：グループの外部売上（卸）と、その先の観測  ",
                           bg=BG_MID, fg=FG_ACC, font=("Segoe UI", 9, "bold"))
        ch.pack(fill="x", padx=8, pady=(0, 6))
        cols = ["channel", "row", "value", "unvalued", "note"]
        self._ch_tree = ttk.Treeview(ch, columns=cols, show="headings", height=7)
        for c, w, t in (("channel", 200, "チャネル"), ("row", 260, "行"), ("value", 160, "値"),
                        ("unvalued", 90, "未評価"), ("note", 520, "説明")):
            self._ch_tree.heading(c, text=t)
            self._ch_tree.column(c, width=w, anchor="w" if c in ("channel", "row", "note") else "e")
        self._ch_tree.pack(fill="x")

    # ── state ─────────────────────────────────────────────────────
    def set_current_plan(self, run_id: str) -> None:
        """The plan on the screen. A ledger of another plan is never shown."""
        self._current_run_id = run_id or ""
        if self._result is not None and self._result["plan_id"] != self._current_run_id:
            self.clear("今の計画の台帳ではありません（作り直しています）")

    def _round_label(self) -> str:
        if self._view_var.get() != "V3":
            return ROUND_LABEL + "（V1・V2 は法人の帳簿の評価）"
        return ROUND2_LABEL if self._round_var.get() == "r2" else ROUND_LABEL

    def clear(self, message: str) -> None:
        self._result = None
        self._band_msg = message
        self._band_var.set(f"{self._round_label()}　｜　{message}")
        self._note_var.set("")
        self._tree.delete(*self._tree.get_children())
        self._tree.configure(columns=[])
        self._ch_tree.delete(*self._ch_tree.get_children())
        # the filters belonged to the previous ledger (its entities and nodes)
        self._ent_cb["values"] = []
        self._ent_var.set("（すべて）")
        self._node_cb["values"] = []
        self._node_var.set("（すべて）")
        self._fig.clf()
        self._canvas.draw()
        for b, t in ((self._btn_unvalued, "未評価 —"), (self._btn_missing, "未設定価格 —"),
                     (self._btn_fx, "為替：最初の週 —"), (self._btn_unreal, "未実現利益 —")):
            b.configure(text=t)

    def start_build(self, sc_tree, model_dir: str, run_id: str, on_done=None, records=None) -> bool:
        """Build the ledger of the plan `run_id` in a thread (False: this model has no masters).
        `records`: the plan's shipment records when the app already built them (shared with the
        World Map, so they are not built twice)."""
        from wom.valuechain.run import has_ledger_masters
        self.set_current_plan(run_id)
        if not model_dir or not has_ledger_masters(model_dir):
            self.clear("このモデルには台帳のマスター（vc_config.csv・vc_entity.csv・vc_node_assignment.csv・"
                       "vc_price_rule.csv）がありません")
            return False
        self.clear("台帳を作成中…（今の計画から。計画はやり直しません）")
        self._building_for = run_id

        def work():
            try:
                from wom.valuechain.run import build_ledger
                res = build_ledger(sc_tree, model_dir, run_id, records=records)
                err = None
            except Exception as exc:          # shown on the panel, not swallowed
                import traceback
                res, err = None, f"{exc}\n{traceback.format_exc()[-1500:]}"
            self.after(0, lambda: self._built(run_id, res, err, on_done))
        threading.Thread(target=work, daemon=True).start()
        return True

    def _built(self, run_id, res, err, on_done):
        if run_id != self._current_run_id:
            print(f"[ValueChain] ledger of an older plan ignored ({run_id})")
            return
        if err is not None:
            self.clear(f"台帳を作れませんでした：{err.splitlines()[0]}")
            print(f"[ValueChain] build failed:\n{err}")
        else:
            self.show(res)
        if on_done:
            on_done(res, err)

    def show(self, res: dict) -> None:
        if res["plan_id"] != self._current_run_id:
            self.clear("今の計画の台帳ではありません（表示しません）")
            return
        self._result = res
        m, led = res["masters"], res["ledger"]
        labels = res["records"].week_labels
        self._band_tail = (f"計画 ID：{res['plan_id']}　｜　報告の開始週：{labels[res['report_idx']]}"
                           f"　｜　HQ の報告通貨 {m.hq_currency}・国際共通の評価通貨 {m.common_currency}"
                           f"　｜　為替の表：{res['fx'].source}")
        self._set_band()
        ents = ["（すべて）"] + sorted(m.entities)
        self._ent_cb["values"] = ents
        self._ent_var.set("（すべて）")
        self._fill_nodes()
        n_unv = int(res["views"]["agg"]["n_unvalued"].sum())
        self._btn_unvalued.configure(text=f"未評価 {n_unv:,}")
        self._btn_missing.configure(text=f"未設定価格 {len(led.missing)}")
        n_first = sum(r["count"] for r in res["fx"].log_rows() if r["method"] == "first_week_rate_before_table")
        self._btn_fx.configure(text=f"為替：最初の週 {n_first:,}")
        uw = res["views"]["unrealized_week"]
        last = uw[uw["week_index"] == uw["week_index"].max()]
        bal = float(last["balance_hq"].sum()) if len(last) else 0.0
        nunv = int(last["lots_unvalued"].sum()) if len(last) else 0
        lw = labels[int(uw["week_index"].max())] if len(uw) else "—"
        self._btn_unreal.configure(text=f"未実現利益（{lw} 末）{bal:,.0f} {m.hq_currency}"
                                        + (f"・未評価 {nunv:,} lot" if nunv else ""))
        self._refresh()

    def _set_band(self):
        if self._result is None:
            self._band_var.set(f"{self._round_label()}　｜　{getattr(self, '_band_msg', '')}")
        else:
            self._band_var.set(f"{self._round_label()}　｜　{self._band_tail}")

    def _fill_nodes(self):
        res = self._result
        if res is None:
            return
        m = res["masters"]
        ent = self._ent_var.get()
        items = []
        for (node, prod), a in sorted(m.assignment.items()):
            if ent != "（すべて）" and a.entity_id != ent:
                continue
            if a.channel_type == "external":
                # ② channels are owned outside the group: the group's ledger has no rows at the
                # channel node (the wholesale sale is booked at the DC). They are in the ② table.
                continue
            tag = {"own": "①", "external": "②", "online": "③"}.get(a.channel_type, "")
            items.append(f"{node}{' ' + tag if tag else ''}")
        self._node_cb["values"] = ["（すべて）"] + sorted(set(items))
        self._node_var.set("（すべて）")

    def _on_entity(self):
        self._fill_nodes()
        self._refresh()

    # ── tables ────────────────────────────────────────────────────
    def _refresh(self):
        res = self._result
        if res is None:
            return
        view = self._view_var.get()
        per = self._period_var.get()
        cur = CUR_KEYS[self._cur_var.get()]
        v = res["views"]
        m = res["masters"]
        note = []
        self._unit = ""
        self._set_band()
        for rb in self._round_rbs:
            rb.configure(state="normal" if view == "V3" else "disabled")
        profit_col = "profit"
        if view == "V3":
            tab = v["v3"]
            if self._round_var.get() == "r2":
                items = [("external_revenue", "外部売上"), ("external_cogs_r2", "外部売上の原価（グループの原価）"),
                         ("expense", "費用")]
                profit_col = "profit_r2"
                extra = [("unrealized_change", "内部の未実現利益の増減"), ("profit", "利益（消去前）")]
                note.append("消去後の利益 ＝ 消去前の利益 − 内部の未実現利益の増減（週末残高の増減 ＋ 未評価へ移った分）")
            else:
                items = [("external_revenue", "外部売上"), ("external_cogs", "外部売上の原価（法人の原価）"),
                         ("expense", "費用"), ("ic_profit", "内部取引の利益（消去前）")]
                extra = []
            if cur == "func":
                note.append("連結（V3）には現地通貨がありません。HQ の報告通貨で表示しています")
                cur = "hq"
        else:
            extra = []
            tab = v["v1"] if view == "V1" else v["v2"]
            items = [("revenue", "売上"), ("cogs", "売上原価"), ("expense", "費用")]
            ent = self._ent_var.get()
            if ent != "（すべて）":
                tab = tab[tab["entity"] == ent]
            if view == "V1":
                node = self._node_var.get().split(" ")[0]
                if node != "（すべて）":
                    tab = tab[tab["node"] == node]
            if cur == "func":
                fc = sorted({m.entities[e].functional_currency for e in tab["entity"].unique()}) if len(tab) else []
                if len(fc) > 1:
                    note.append(f"現地通貨が複数（{', '.join(fc)}）なので合計できません。法人を 1 つ選んでください")
                    self._fill_rows(None, items, cur, per, view, extra, profit_col, "")
                    self._note_var.set("　".join(note))
                    return
                note.append(f"現地通貨：{fc[0] if fc else '—'}（法人の機能通貨）")
                self._unit = fc[0] if fc else ""
        note.append("金額は、評価できた明細の合計。未評価の明細は 0 として足さず、件数を右の列に出す")
        if view == "V2" and cur == "func":
            note.append("右端の「現地の利益を HQ に換算」は、現地の法人の利益をその週の為替で換算した値。"
                        "取得原価を引き継ぐ管理評価（通貨 HQ のときの利益）とは別の評価")
        unit = {"hq": m.hq_currency, "common": m.common_currency}.get(cur, getattr(self, "_unit", ""))
        self._note_var.set("　｜　".join(note))
        self._fill_rows(tab, items, cur, per, view, extra, profit_col, unit)
        self._draw(tab, cur, per, profit_col, unit)
        self._fill_channels()

    def _fill_rows(self, tab, items, cur, per, view, extra=(), profit_col="profit", unit=""):
        profit_head = "利益（消去後）" if profit_col == "profit_r2" else "利益"
        cols = (["week", "phase"] + [k for k, _ in items] + ["profit_main"] + [k for k, _ in extra]
                + ["unvalued"])
        u = f"（{unit}）" if unit else ""
        heads = (["週", "区分"] + [t + u for _, t in items] + [profit_head + u] + [t + u for _, t in extra]
                 + ["未評価（件）"])
        if view == "V2" and cur == "func":
            cols.append("translated")
            heads.append(f"現地の利益を HQ に換算（{self._result['masters'].hq_currency}）")
        self._tree.configure(columns=cols)
        for c, h in zip(cols, heads):
            self._tree.heading(c, text=h)
            fixed = c in ("week", "phase")
            # wide enough for the whole heading (CJK ~13 px, others ~7 px at 9 pt)
            need = sum(13 if ord(ch) > 0x2E7F else 7 for ch in h) + 16
            w = {"week": 82, "phase": 44}.get(c, max(112, need))
            self._tree.column(c, width=w, minwidth=w if not fixed else (82 if c == "week" else 44),
                              stretch=False, anchor="w" if fixed else "e")
        self._tree.delete(*self._tree.get_children())
        if tab is None or len(tab) == 0:
            return
        g = tab.groupby(["week_index", "week", "in_report"], as_index=False).sum(numeric_only=True)
        for _, r in g.sort_values("week_index").iterrows():
            vals = [r["week"], "報告" if r["in_report"] else "助走"]
            for k, _ in items:
                vals.append(_fmt(r.get(f"{k}_{cur}_{per}", float("nan"))))
            vals.append(_fmt(r.get(f"{profit_col}_{cur}_{per}", float("nan"))))
            for k, _ in extra:
                vals.append(_fmt(r.get(f"{k}_{cur}_{per}", float("nan"))))
            vals.append(f"{int(r.get(f'n_unvalued_{per}', 0)):,}")
            if view == "V2" and cur == "func":
                vals.append(_fmt(r.get(f"profit_local_translated_hq_{per}", float("nan"))))
            self._tree.insert("", "end", values=vals)

    def _draw(self, tab, cur, per, profit_col="profit", unit=""):
        self._fig.clf()
        ax = self._fig.add_subplot(111)
        ax.set_facecolor(BG_MID)
        self._fig.patch.set_facecolor(BG_DARK)
        if tab is not None and len(tab):
            g = tab.groupby("week_index").sum(numeric_only=True)
            y = g.get(f"{profit_col}_{cur}_{per}")
            if y is not None:
                ax.plot(g.index, y.values, color="#69F0AE", lw=1.5,
                        label="消去後（第 2 回）" if profit_col == "profit_r2" else "利益")
            if profit_col == "profit_r2":     # the round-1 line for comparison
                y1 = g.get(f"profit_{cur}_{per}")
                if y1 is not None:
                    ax.plot(g.index, y1.values, color="#FFB74D", lw=1.0, ls="--", label="消去前（第 1 回）")
                ax.legend(fontsize=7, facecolor=BG_MID, labelcolor=FG_WHITE, edgecolor=BG_LIGHT)
            rep = self._result["report_idx"]
            ax.axvline(rep, color="#FFD740", lw=0.8, ls="--")
            labels = self._result["records"].week_labels
            ticks = list(range(0, len(labels), max(1, len(labels) // 6)))
            ax.set_xticks(ticks)
            ax.set_xticklabels([labels[i] for i in ticks], fontsize=7, color=FG_WHITE, rotation=30)
        ax.set_title(f"利益（{'単週' if per == 'wk' else '累計'}、{self._round_label()}）"
                     + (f"［{unit}］" if unit else ""), color=FG_WHITE, fontsize=8)
        ax.tick_params(colors=FG_WHITE, labelsize=7)
        self._fig.tight_layout()
        self._canvas.draw()

    def _fill_channels(self):
        self._ch_tree.delete(*self._ch_tree.get_children())
        res = self._result
        m, v = res["masters"], res["views"]
        a = v["agg"]
        cur = CUR_KEYS[self._cur_var.get()]
        inv = v["inventory"]
        last = res["records"].week_labels[-1]
        for (node, prod), asg in sorted(m.assignment.items()):
            if asg.channel_type != "external":
                continue
            ent = asg.entity_id
            ws = a[(a["kind"] == "revenue") & (a["scope"] == "external") & (a["product"] == prod) &
                   (a["counterparty"] == ent)]
            known = float(ws["hq_known"].sum())
            obs = a[(a["kind"] == "observation_sale") & (a["product"] == prod) & (a["node"] == node)]
            ext_inv = inv[(inv["external"] == 1) & (inv["owner"] == ent) & (inv["product"] == prod)]
            peak = ext_inv.groupby("week_index")["lots"].sum()
            ch = f"{node} ②（{prod}）"
            self._ch_tree.insert("", "end", values=[
                ch, "グループの外部売上（卸）", _fmt(known) if known else "—",
                f"{int(ws['n_unvalued'].sum()):,}",
                "DC → このチャネルへの出荷 × 卸価格。卸価格が未設定なら未評価（未設定価格の一覧）"])
            self._ch_tree.insert("", "end", values=[
                ch, "外部チャネルの消費者への販売（観測）", _fmt(float(obs["local"].sum())) +
                f" {asg.local_currency}" if len(obs) else "—", f"{int(obs['n_unvalued'].sum()):,}",
                "市場価格 × このチャネルの実出荷。グループの売上に足さない"])
            self._ch_tree.insert("", "end", values=[
                ch, "外部チャネルの在庫（観測）", f"最大 {int(peak.max()) if len(peak) else 0:,} lot", "",
                "輸送中を含む。グループの在庫に足さない（週ごとの値は vc_inventory_weekly）"])

    # ── lists ─────────────────────────────────────────────────────
    def _popup(self, title, df):
        top = tk.Toplevel(self)
        top.title(title)
        top.geometry("1100x420")
        cols = list(df.columns)
        tv = ttk.Treeview(top, columns=cols, show="headings")

        def px(t):
            return sum(13 if ord(ch) > 0x2E7F else 7 for ch in str(t)) + 14
        for c in cols:
            tv.heading(c, text=c)
            data_w = max([px(v) for v in df[c].head(200)] or [0])
            tv.column(c, width=max(70, min(380, max(px(c), data_w))), anchor="w", stretch=False)
        top.geometry(f"{min(1500, 40 + sum(int(tv.column(c, 'width')) for c in cols))}x420")
        hsb = ttk.Scrollbar(top, orient="horizontal", command=tv.xview)
        tv.configure(xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        for r in df.itertuples(index=False):
            tv.insert("", "end", values=[str(x) for x in r])
        tv.pack(fill="both", expand=True)
        return top

    def _show_missing(self):
        if self._result is None:
            return
        df = pd.DataFrame(list(self._result["ledger"].missing.values()))
        self._popup("未設定価格の一覧（vc_price_rule.csv に書き入れる）", df)

    def _show_fx(self):
        if self._result is None:
            return
        self._popup("為替の記録（最初の週のレート・未評価）", pd.DataFrame(self._result["fx"].log_rows()))

    def _show_unrealized(self):
        if self._result is None:
            return
        res = self._result
        d = res["views"]["unrealized"]
        if d.empty:
            return self._popup("内部の未実現利益（週末残高）", pd.DataFrame({"note": ["内部の未実現利益はありません"]}))
        last = int(res["views"]["unrealized_week"]["week_index"].max())
        rep = res["report_idx"]
        cols = ["owner", "product", "location_kind", "location", "lots", "entity_hq", "group_hq",
                "unrealized_hq", "unrealized_common", "lots_unvalued"]
        x = d[d["week_index"] == last][cols]
        x = x[(x[["lots", "unrealized_hq", "lots_unvalued"]].abs().sum(axis=1) > 0)]
        o = d[d["week_index"] == rep - 1][["owner", "product", "location_kind", "location", "unrealized_hq"]] \
            if rep > 0 else d.iloc[0:0][["owner", "product", "location_kind", "location", "unrealized_hq"]]
        o = o.rename(columns={"unrealized_hq": "opening_unrealized_hq"})
        t = x.merge(o, on=["owner", "product", "location_kind", "location"], how="outer").fillna(0)
        t = t[(t[["lots", "unrealized_hq", "opening_unrealized_hq", "lots_unvalued"]].abs().sum(axis=1) > 0)]
        labels = res["records"].week_labels
        hq = res["masters"].hq_currency
        t = t.rename(columns={"owner": "法人", "product": "製品", "location_kind": "所在", "location": "ノード／区間",
                              "lots": "lot", "entity_hq": f"法人の原価（{hq}）", "group_hq": f"グループの原価（{hq}）",
                              "unrealized_hq": f"未実現利益 {labels[last]} 末（{hq}）",
                              "unrealized_common": f"同（{res['masters'].common_currency}）",
                              "opening_unrealized_hq": f"期首 {labels[rep - 1] if rep > 0 else '—'} 末（{hq}）",
                              "lots_unvalued": "未評価の lot"})
        for c in t.columns:
            if t[c].dtype.kind == "f":
                t[c] = t[c].map(lambda v: f"{v:,.0f}")
        return self._popup("内部の未実現利益（週末残高。法人・ノード別。輸送中を含む。未評価の lot は 0 として足さない）", t)

    def _show_unvalued(self):
        if self._result is None:
            return
        a = self._result["views"]["agg"]
        u = (a[a["n_unvalued"] > 0].groupby(["entity", "kind", "scope", "family", "price_type"])["n_unvalued"]
             .sum().reset_index().sort_values("n_unvalued", ascending=False))
        self._popup("未評価の明細（件数）", u)
