# -*- coding: utf-8 -*-
"""
wom/cockpit/s3_run.py — S3 Run タブ（Phase 8-3c）
================================================================================
`wom/cockpit/s3_view_model.py` が作った値を**並べるだけ**（C9、S1 と同じ規律）。
このファイルの中で `run_headless()` を直接呼ばない——`_on_run_finished()` が
ワーカースレッドから受け取った結果を `build_s3_view()` に渡すだけ。

正典: requests/Phase8-3c_RequestLetter_S3Run_to_CodeKun.md
      requests/Phase8_DesignMD_CockpitGUI.md rev.5 §4「S3 Run」

【なぜワーカースレッドか】`run_s3()` は `run_headless()` 経由で9秒前後かかる
（N2）。tkinter は単一スレッドの GUI ツールキットなので、**ワーカースレッドから
ウィジェットへ直接触ってはいけない**——ここでは `queue.Queue` に結果を置き、
メインスレッドの `after(100ms)` ポーリングで取り出して描画する、という定石で
安全側に倒している。
"""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from wom.cockpit.s1_allocate import BG_DARK, BG_LIGHT, BG_MID, FG_ACC, FG_WHITE
from wom.cockpit.s3_view_model import build_s3_view, run_s3

_JA_FONT = ("Yu Gothic UI", 9)
_JA_FONT_BOLD = ("Yu Gothic UI", 10, "bold")
_FG_MUTED = "#78909C"

# ⑦ ops_bar の `⚑` に渡す、この画面固有の文言（N7・語はここ1箇所に置く）。
COMMIT_LABEL_JA = "⚑ この実行結果を記録する"
COMMIT_NOTE_JA = "（実行前は保存できません。まず ▶ 実行 を押してください）"


class RunPanel(tk.Frame):
    """S3 Run タブ。`load()` で pre_plan を受け取り、`▶ 実行` で第2層・第3層を回す。"""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG_DARK, **kw)
        self._model_dir = ""
        self._scenario_id = ""
        self._cap_wk = 800.0
        self._uom: Optional[str] = None
        self._pre_plan_state: Optional[dict] = None
        self._run_result: Optional[dict] = None   # run_s3() の返却（未実行なら None）
        self._view: Optional[dict] = None
        self._queue: "queue.Queue" = queue.Queue()
        self._running = False
        self._selected_node_key: Optional[tuple] = None
        self._build()

    # ------------------------------------------------------------------
    # レイアウト（ウィジェットの配置のみ）
    # ------------------------------------------------------------------
    def _build(self):
        # --- 実行行（先に確保・Phase 8-2a・D3 と同じ理由で side="bottom" ではなく
        #     常に上に固定。S3 では「実行する」が最初の・唯一の主要操作なので
        #     結論行より上に置く） ---
        top = tk.Frame(self, bg=BG_MID)
        top.pack(fill="x", padx=6, pady=(6, 2))
        self._run_btn = tk.Button(top, text="▶ 実行", command=self._on_run_clicked,
                                  bg=FG_ACC, fg=BG_DARK, relief="flat",
                                  font=_JA_FONT_BOLD)
        self._run_btn.pack(side="left", padx=(4, 8))
        self._run_status_var = tk.StringVar(value="")
        tk.Label(top, textvariable=self._run_status_var, bg=BG_MID, fg=FG_ACC,
                font=_JA_FONT).pack(side="left")
        tk.Label(top, text="実行するとディスクに書き込みます"
                         "（demand_forecast_<ID>.csv／output/ppc／output/planning_state）",
                bg=BG_MID, fg=_FG_MUTED, font=("Segoe UI", 8)).pack(side="left", padx=(12, 0))

        # --- 結論行（3行、S1 と同じ形） ---
        headline_frame = tk.Frame(self, bg=BG_DARK)
        headline_frame.pack(fill="x", padx=8, pady=(6, 2))
        self._headline_labels = []
        for _ in range(3):
            lbl = tk.Label(headline_frame, text="", bg=BG_DARK, fg=FG_WHITE,
                           font=_JA_FONT_BOLD, anchor="w", justify="left")
            lbl.pack(fill="x")
            self._headline_labels.append(lbl)

        # --- 根拠（matplotlib）＋ 補助パネル ---
        mid = tk.Frame(self, bg=BG_DARK)
        mid.pack(fill="both", expand=True, padx=8, pady=4)

        plot_frame = tk.Frame(mid, bg=BG_DARK)
        plot_frame.pack(side="left", fill="both", expand=True)
        self._fig = Figure(figsize=(6.4, 5.2), dpi=95, facecolor=BG_DARK)
        self._canvas = FigureCanvasTkAgg(self._fig, master=plot_frame)
        self._canvas.get_tk_widget().pack(fill="both", expand=True)

        aux = tk.Frame(mid, bg=BG_MID, width=260)
        aux.pack(side="left", fill="y", padx=(6, 0))
        aux.pack_propagate(False)

        # Phase 8-3b-3・M1 の並べ方をそのまま守る: 常に在るもの（能力ノード
        # 一覧・クリックで図を切替）を上、条件つき（実行結果）を下に置く。
        tk.Label(aux, text="能力ノード（クリックで図を切替）", bg=BG_MID, fg=FG_ACC,
                font=_JA_FONT_BOLD, anchor="w", wraplength=240).pack(
            fill="x", padx=6, pady=(6, 2))
        self._nodes_frame = tk.Frame(aux, bg=BG_MID)
        self._nodes_frame.pack(fill="x", padx=6)

        # K2 と同じ規律: 「実行の結果」ブロックは実行前は見出しごと隠す
        # （空のリストを見出しだけ出さない）。
        self._result_header_label = tk.Label(
            aux, text="実行の結果", bg=BG_MID, fg=FG_ACC, font=_JA_FONT_BOLD, anchor="w")
        self._result_header_label.pack(fill="x", padx=6, pady=(10, 2))
        self._result_header_visible = True
        self._result_info_label = tk.Label(aux, text="", bg=BG_MID, fg=FG_WHITE,
                                           font=_JA_FONT, anchor="w", justify="left",
                                           wraplength=240)
        self._result_info_label.pack(fill="x", padx=6, pady=(0, 6))

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------
    def load(self, model_dir: str, scenario_id: str, cap_wk: float, state: dict, *,
            uom: Optional[str] = None) -> None:
        """S1 の pre_plan を受け取り、「未実行」状態で描く（公開 API）。"""
        self._model_dir = model_dir
        self._scenario_id = scenario_id
        self._cap_wk = cap_wk
        self._uom = uom
        self._pre_plan_state = state
        self._run_result = None
        self._selected_node_key = None
        self._run_status_var.set("")
        self._render(build_s3_view(state, None))

    def commit(self) -> dict:
        """実行結果を保存する（公開 API・N7）。

        `AllocationPanel.commit()` と同じ契約——引数なし・Planning State を
        返す・失敗は例外（メッセージボックスは呼び出し側 = `CockpitFrame` の
        役目）。**`▶ 実行` がまだ済んでいなければ例外を送出する。**
        """
        if self._run_result is None:
            raise ValueError("先に ▶ 実行 を押してください")

        import wom.planning_state as planning_state

        state = self._run_result["state"]
        path = planning_state.save(state)
        state["allocation_id"] = state.get("allocation_id") or \
            os.path.splitext(os.path.basename(path))[0]
        return state

    # ------------------------------------------------------------------
    # 実行（ワーカースレッド + after ポーリング）
    # ------------------------------------------------------------------
    def _on_run_clicked(self):
        if self._running:
            return
        if self._pre_plan_state is None:
            messagebox.showerror("S3 Run", "先に S1 で計画案を保存してください")
            return
        self._running = True
        self._run_btn.config(state="disabled")
        self._run_status_var.set("実行中…（第2層・第3層を計算しています）")

        model_dir, scenario_id, cap_wk, uom = (
            self._model_dir, self._scenario_id, self._cap_wk, self._uom)
        pre_plan_state = self._pre_plan_state

        def _worker():
            # ワーカースレッドは run_s3() だけを呼ぶ——Tk には一切触らない。
            try:
                result = run_s3(model_dir, scenario_id, cap_wk, pre_plan_state, uom=uom)
                self._queue.put(("ok", result))
            except Exception as e:   # noqa: BLE001 — キュー経由でメインスレッドへ伝える
                self._queue.put(("error", e))

        threading.Thread(target=_worker, daemon=True).start()
        self.after(100, self._poll_queue)

    def _poll_queue(self):
        try:
            kind, payload = self._queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_queue)
            return

        self._running = False
        self._run_btn.config(state="normal")
        if kind == "error":
            self._run_status_var.set("実行に失敗しました")
            messagebox.showerror("S3 Run", f"実行に失敗しました:\n{payload}")
            return

        self._run_status_var.set("完了")
        self._run_result = payload
        self._selected_node_key = None
        self._render(build_s3_view(self._pre_plan_state, self._run_result))

    # ------------------------------------------------------------------
    # 描画
    # ------------------------------------------------------------------
    def _render(self, view: dict):
        self._view = view
        for i, line in enumerate(view["conclusion_lines_ja"][:3]):
            self._headline_labels[i].config(text=line)
        for i in range(len(view["conclusion_lines_ja"]), 3):
            self._headline_labels[i].config(text="")

        self._render_nodes(view["capacity_nodes"])

        if view["has_run"]:
            if not self._result_header_visible:
                self._result_header_label.pack(fill="x", padx=6, pady=(10, 2),
                                               before=self._result_info_label)
                self._result_header_visible = True
            self._render_result_info(view["state"])
        else:
            if self._result_header_visible:
                self._result_header_label.pack_forget()
                self._result_header_visible = False
            self._result_info_label.config(text="")

        if self._selected_node_key is None and view["default_node_key"] is not None:
            self._selected_node_key = view["default_node_key"]
        self._render_plot(view["capacity_nodes"])

    def _render_nodes(self, nodes):
        for w in self._nodes_frame.winfo_children():
            w.destroy()
        if not nodes:
            tk.Label(self._nodes_frame, text="（能力を持つノードがありません）",
                    bg=BG_MID, fg=_FG_MUTED, font=_JA_FONT, wraplength=240,
                    justify="left").pack(anchor="w")
            return
        for n in nodes:
            row = tk.Frame(self._nodes_frame, bg=BG_MID)
            row.pack(fill="x", pady=1)
            # cap_hard=張り付き（sealed・需要が溢れた）／cap_soft=超過（残業帯）を
            # 別々に数える——両方を「超過」に一括りにしない（terminology 修正）。
            hard_n = len(n["hard_weeks"]); soft_n = len(n["soft_weeks"])
            text = f"{n['label']}  張り付き{hard_n}週 / 超過{soft_n}週"
            key = (n["product"], n["name"])
            color = "#F44336" if hard_n > 0 else ("#FF9800" if soft_n > 0 else FG_ACC)
            lbl = tk.Label(row, text=text, bg=BG_MID, fg=color, font=_JA_FONT,
                          cursor="hand2", anchor="w")
            lbl.pack(fill="x")
            lbl.bind("<Button-1>", lambda _e, k=key: self._on_node_click(k))

    def _on_node_click(self, key: tuple):
        self._selected_node_key = key
        if self._view is not None:
            self._render_plot(self._view["capacity_nodes"])

    def _render_result_info(self, state: dict):
        realized = state.get("realized") or {}
        placement = state.get("placement") or {}
        unmet = realized.get("unmet_lots", 0.0) or 0.0
        peak_weeks = realized.get("peak_inventory_weeks", []) or []
        earliest = placement.get("earliest_start_week") or "—"
        lines = [
            f"未充足 {unmet:.0f} lot",
            f"在庫ピーク {len(peak_weeks)}週",
            f"最早着手週 {earliest}",
        ]
        self._result_info_label.config(text="\n".join(lines))

    def _render_plot(self, nodes):
        self._fig.clear()
        ax = self._fig.add_subplot(111, facecolor=BG_DARK)
        for spine in ax.spines.values():
            spine.set_color("#546E7A")
        ax.tick_params(colors=FG_WHITE, labelsize=7)
        ax.title.set_color(FG_WHITE)
        ax.xaxis.label.set_color(FG_WHITE)
        ax.yaxis.label.set_color(FG_WHITE)

        node = next((n for n in nodes
                    if (n["product"], n["name"]) == self._selected_node_key), None)
        if node is None:
            ax.text(0.5, 0.5, "▶ 実行 を押すと、ここに図が出ます", ha="center",
                    va="center", color=FG_WHITE, fontsize=11, transform=ax.transAxes)
            ax.set_xticks([]); ax.set_yticks([])
            self._fig.tight_layout()
            self._canvas.draw()
            return

        series = node["series"]
        labels = series["week_labels"]
        p = series["p"]; ch = series["cap_hard"]; cs = series["cap_soft"]
        n = len(p)
        x = list(range(n))

        # 色分けは系列比較（p[w] > cap_hard[w]）ではなく capacity_events
        # （node_id で記録された実イベントを node_name に解決したもの）で行う
        # ——cap_hard は ForwardPlanner が P を封じる天井のため p > cap_hard は
        # 設計上ほぼ成立せず、系列比較では赤棒が出なかった（terminology 修正）。
        hard_set = set(node["hard_weeks"])
        soft_set = set(node["soft_weeks"])
        bar_colors = []
        for w in range(n):
            label = labels[w] if w < len(labels) else None
            if label in hard_set:
                bar_colors.append("#F44336")
            elif label in soft_set:
                bar_colors.append("#FF9800")
            else:
                bar_colors.append("#4CAF50")
        ax.bar(x, p, color=bar_colors, alpha=0.85, width=0.8)

        if any(v > 0 for v in ch):
            ax.plot(x, ch, color="#F44336", linewidth=1.3, linestyle="-",
                    label="cap_hard")
        if any(v > 0 for v in cs):
            ax.plot(x, cs, color="#FF9800", linewidth=1.3, linestyle=":",
                    label="cap_soft")

        step = max(1, n // 8)
        ticks = list(range(0, n, step))
        ax.set_xticks(ticks)
        ax.set_xticklabels([labels[i] for i in ticks], rotation=30, ha="right", fontsize=6)
        ax.set_ylabel("P（lot）")
        ax.set_title(f"{node['label']} — P vs Capacity Limits", fontsize=10)
        if any(v > 0 for v in ch) or any(v > 0 for v in cs):
            ax.legend(loc="upper right", fontsize=7, facecolor=BG_MID,
                     labelcolor=FG_WHITE, framealpha=0.85)

        self._fig.tight_layout()
        self._canvas.draw()
