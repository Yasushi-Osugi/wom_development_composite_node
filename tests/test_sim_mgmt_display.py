# -*- coding: utf-8 -*-
"""
RequestLetter_SimMgmt_WorldMapTrial Part 1 のテスト

1.1  Run Simulation だけのとき、Management は money の値を「money によるシナリオ比較
     （PPC ではない）」と明記して出す。Planning Engine の結果を出すときは、今の規則
     （今の計画の PPC だけ、無ければ空欄）のまま。2 つの出所の数字が同じ表に混ざらない。
1.2  PPC タブの「PPC KPI Summary」の文字が重ならない（行の位置を points で決める）。
"""
from __future__ import annotations

import json
import os

import pandas as pd
import pytest

from wom.data.schema import Cols
import wom.ppc.ppc_run_info as R

SIM = "money によるシナリオ比較（PPC ではない）"


def _new_tk_root(tk):
    last = None
    for _ in range(3):
        try:
            return tk.Tk()
        except Exception as exc:          # Tcl may fail transiently on CI
            last = exc
    pytest.skip(f"tk.Tk() could not be created on this machine: {last}")


def _money_row(scen, rev):
    return {Cols.SCENARIO: scen, Cols.REVENUE: rev, Cols.COGS: rev * 0.4,
            Cols.GROSS_PROFIT: rev * 0.6, Cols.GROSS_MARGIN: 0.6, Cols.INV_VALUE_COST: 5.0,
            Cols.CCC_WKS: -3.0, Cols.AR_VALUE: 1.0, Cols.AP_VALUE: 2.0, "units": 10.0}


class _Mgr:
    def __init__(self, scenarios):
        self.scenario_money_kpi = pd.DataFrame([_money_row(s, r) for s, r in scenarios])
        self.summary_money = None
        self.lc_comparison_df = pd.DataFrame([
            {"wom_scenario": s, "lc_scenario": "Base", "revenue": r, "customs_duty": 0.0,
             "freight_total": 1.0, "landed_gross_margin": 0.5, "margin_impact_pp": 0.0,
             "tariff_burden_pct": 0.0} for s, r in scenarios])
        self.lc_scens, self.route_idx, self.strategic_kpi, self.sc_tree = {}, {}, None, None
        self.model_dir = ""
        self.management_results = {}


def test_management_simulation_then_planning_never_mixes_sources(tmp_path):
    tk = pytest.importorskip("tkinter")
    import wom.gui.app as A
    out = str(tmp_path / "ppc")
    os.makedirs(out)
    with open(os.path.join(out, "ppc_kpi_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"base_currency": "JPY", "total_revenue_base": 640773326445600.0,
                   "total_cost_base": 3.0e14, "gross_profit_base": 3.4e14,
                   "gross_margin_pct": 0.412}, f)
    with open(os.path.join(out, "ppc_node_pl_summary.csv"), "w", encoding="utf-8") as f:
        f.write("node_id,product_id,revenue_base,cost_base,tariff_base,gross_profit_base,"
                "gross_margin_pct,lot_events\nRetail_AMER,iPhone16,100,40,0,60,0.6,1\n")
    R.write_run_info(out, {"run_id": "RUN-P", "model_dir": r"C:\m\iphone_global",
                           "sales_source": R.SALES_PSI})

    root = _new_tk_root(tk)
    try:
        root.geometry("900x600+-3000+-3000")
        panel = A.ManagementCockpitPanel(root)
        panel._node_pl_output_dir = out
        pl = lambda: [[str(v) for v in panel._pl_tree.item(i)["values"]] for i in panel._pl_tree.get_children()]
        lc = lambda: [[str(v) for v in panel._lc_tree.item(i)["values"]] for i in panel._lc_tree.get_children()]
        npl = lambda: [panel._node_pl_tree.item(i)["values"] for i in panel._node_pl_tree.get_children()]

        # ── Run Simulation：3 シナリオの money の値と出所 ──
        sim = _Mgr([("Base", 452663505.0), ("Upside", 499937882.0), ("Downside", 369928534.0)])
        panel.show_simulation(sim, r"C:\m\iphone_global")
        assert [r[0] for r in pl()] == ["Base", "Upside", "Downside"]
        assert pl()[0][1] == "452,663,505" and all(r[-1] == SIM for r in pl())
        assert "Run Simulation" in panel._ppc_banner_var.get() and SIM in panel._ppc_banner_var.get()
        assert [r[0] for r in lc()] == ["Base", "Upside", "Downside"]
        assert "¥" not in str(lc()) and "$" not in str(lc())           # sku_master currency, no symbol
        assert panel._lc_narrative.get("1.0", "end").startswith("出所：" + SIM)
        assert "Simulation" in str(npl()[0][0])
        assert "出所：" + SIM in [t.get_text() for t in panel._gp_fig.axes[0].texts]
        assert "出所：" + SIM in [t.get_text() for t in panel._ccc_fig.axes[0].texts]
        assert [t.get_text() for t in panel._gp_fig.axes[0].get_xticklabels()] == ["Base", "Upside", "Downside"]
        assert panel._ledger_pl_for_sku(None) is None                  # PPC is never read in sim mode

        # ── 続けて Run Planning Engine（Simulation のシナリオに Planning が足される）──
        plan = _Mgr([("Base", 452663505.0), ("Upside", 499937882.0), ("Downside", 369928534.0),
                     ("Planning", 416331210.0)])
        panel.set_ppc_context(R.make_context(R.STATE_RUNNING, "RUN-P", r"C:\m\iphone_global"))
        panel.load(plan)
        assert pl() == [["Planning"] + [""] * 8 + ["PPC 計算中"]]       # no simulation number stays
        assert lc() == []
        panel.set_ppc_context(R.make_context(R.STATE_DONE, "RUN-P", r"C:\m\iphone_global"))
        panel.load(plan)
        assert [r[0] for r in pl()] == ["Planning"]
        assert pl()[0][1] == "640,773,326,445,600" and pl()[0][-1] == "PPC 台帳（今の計画）"
        assert [r[0] for r in lc()] == ["Planning"]
        assert "452" not in str(pl()) and "416,331" not in str(pl())
        assert [t.get_text() for t in panel._gp_fig.axes[0].get_xticklabels()] == ["Planning"]
        assert not any(t.get_text().startswith("出所") for t in panel._gp_fig.axes[0].texts)

        # ── Planning の後に Run Simulation：money の値だけに戻る ──
        panel.show_simulation(sim, r"C:\m\iphone_global")
        assert [r[-1] for r in pl()] == [SIM] * 3 and "640" not in str(pl())
        # モデルを読み込み直すと、Simulation の表示も消えて計画の規則に戻る
        panel.on_model_loaded(r"C:\m\iphone_global")
        assert panel._display_source == panel.SOURCE_PLAN and pl() == []
    finally:
        root.destroy()


# ── 1.2 ─────────────────────────────────────────────────────────────────

def _fixed():
    return [("PPC KPI Summary", 11, "k", "bold", 0), ("Base currency: JPY", 7.5, "k", "normal", 2),
            ("Lots: 1,399", 7.5, "k", "normal", 0), ("Revenue     1.57T JPY", 8.5, "k", "bold", 5),
            ("Total Cost  1.02T JPY", 8.5, "k", "bold", 0), ("Gross Prft  552.34B JPY", 8.5, "k", "bold", 0),
            ("Gross Marg  35.2%", 8.5, "k", "bold", 0), ("Tariff Cost 53.62M JPY", 8, "k", "normal", 5)]


@pytest.mark.parametrize("w,h", [(430, 204), (300, 160), (250, 134), (180, 100)])
@pytest.mark.parametrize("n_ch", [0, 3, 21])
def test_kpi_text_layout_lines_never_overlap(w, h, n_ch):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import wom.ppc.ppc_cockpit_app as C
    fig = plt.figure(dpi=100)
    ax = fig.add_subplot(111)
    try:
        ch = [(i, f"Local_R_CH{i:02d}", 1e11 / (i + 1)) for i in range(n_ch)]
        L = C._kpi_text_layout(ax, _fixed(), ch, "JPY", height_pt=h * 0.72, width_pt=w * 0.72,
                               badge_text="! 733 trust event(s)")
        rows = {}
        for text, fs, _c, _w, x, y in L["lines"]:
            rows.setdefault(x, []).append((y, fs, text))
        for col in rows.values():                        # within a column: each line starts
            col.sort()                                   # below the previous one's height
            for (y0, fs0, _t0), (y1, _fs1, _t1) in zip(col, col[1:]):
                assert y1 >= y0 + fs0 * C.LINE_SPACING - 1e-6
        assert L["shown_channels"] + L["hidden_channels"] == n_ch
        texts = [t for t, *_ in L["lines"]]
        for t in ("Revenue     1.57T JPY", "Gross Prft  552.34B JPY"):
            assert t in texts                            # value lines are never shortened
        if L["hidden_channels"] and L["mode"] != "compact (clipped)":
            assert f"+{L['hidden_channels']} more channel(s)" in texts
        if L["mode"] != "compact (clipped)":
            assert L["badge_y"] + L["badge_fs"] * 1.9 <= L["height_pt"] + 1
        if L["columns"] == 2 and len(rows) == 2:
            xs = sorted(rows)
            left_w = max(len(t) * 0.6 * fs for _y, fs, t in rows[xs[0]])
            assert xs[0] * L["width_pt"] + left_w <= xs[1] * L["width_pt"] + 1   # columns apart
    finally:
        plt.close(fig)


def test_kpi_text_layout_keeps_the_end_of_long_channel_names():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import wom.ppc.ppc_cockpit_app as C
    fig = plt.figure(dpi=100)
    ax = fig.add_subplot(111)
    try:
        ch = [(0, "Sales_TH_BKK_i_Very_Long_Name", 3.7e10), (1, "Sales_TH_PRO_i_Very_Long_Name", 2.9e10)]
        L = C._kpi_text_layout(ax, _fixed(), ch, "JPY", height_pt=150, width_pt=200, badge_text="OK")
        ch_lines = [t for t, *_ in L["lines"] if "B JPY" in t and t.startswith(("~", "Sales"))]
        assert len(ch_lines) == 2 and ch_lines[0] != ch_lines[1]
        assert all(t.rstrip().endswith("JPY") for t in ch_lines)    # the value is kept
    finally:
        plt.close(fig)
