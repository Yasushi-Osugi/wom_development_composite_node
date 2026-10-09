# -*- coding: utf-8 -*-
"""
tools/gui_generation_line_check.py — 実アプリの窓で、smartx を計画して Network の図と PSI List を確かめる
（RequestLetter_GenerationLine_UpperLayer の GUI の確認）

    python -m tools.gui_generation_line_check --model-dir <smartx のコピー> --out <dir> [--layer on|off]

`wom.gui.app.WOMApp`（`python -m main` と同じ窓）で、モデルを読み込み、Plugins の
Capacity Layer を ON／OFF にして Run Planning Engine を実行する。PPC の完了を待ってから
Network タブを開き、**計画の木の全ノード**を PSI List で順に描かせる（行の色の判定など、
描画の途中の例外を拾う）。窓の画像は Win32 の PrintWindow で取る。

出力：<out>/result.json（状態・例外・各ノードの CapHard の表示）、<out>/*.png。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--layer", choices=("on", "off"), default="off")
    ap.add_argument("--plugins", default="holiday_calendar,capacity_override,buffering_stock_optimizer",
                    help="ON にするプラグイン（name、カンマ区切り。既定は smartx の golden と同じ 3 つ）。"
                         "auto＝モデルの読み込みで決まったまま（変えない）")
    ap.add_argument("--nodes", default="AssemblyCN_g1,AssemblyCN_g3,AssemblyCN",
                    help="画像を取るノード（node_name、カンマ区切り）")
    a = ap.parse_args(argv)
    os.chdir(REPO)
    sys.path.insert(0, REPO)
    os.makedirs(a.out, exist_ok=True)
    from tkinter import filedialog, ttk
    import wom.gui.app as A
    from wom.lovem.viewer import _print_window

    folder = os.path.abspath(a.model_dir)
    filedialog.askdirectory = lambda **k: folder
    errors, st, cells = [], {"plan": False, "ppc": False, "plan_err": None}, {}
    app = A.WOMApp()
    app.geometry("1536x824+0+0")
    app.report_callback_exception = lambda et, ev, tb: errors.append(
        "".join(traceback.format_exception(et, ev, tb)))
    o_pd, o_ppc, o_pe = app._on_planning_done, app._on_ppc_done, app._on_planning_error

    def pd_(*x, **k):
        try:
            o_pd(*x, **k)
        except Exception:
            errors.append(traceback.format_exc())
        st["plan"] = True

    def ppc_(*x, **k):
        try:
            o_ppc(*x, **k)
        finally:
            st["ppc"] = True

    def pe_(*x, **k):
        st["plan_err"] = repr(x)
        st["plan"] = True
        o_pe(*x, **k)

    app._on_planning_done, app._on_ppc_done, app._on_planning_error = pd_, ppc_, pe_

    def shot(name):
        app.update()
        app.update_idletasks()
        _print_window(int(app.wm_frame(), 16)).save(os.path.join(a.out, name + ".png"))

    def find_nb(widget):
        out = []
        for c in widget.winfo_children():
            if isinstance(c, ttk.Notebook):
                out.append(c)
            out += find_nb(c)
        return out

    net = app._network_panel

    def check_network():
        try:
            main_nb = [nb for nb in find_nb(app)
                       if str(net) in [str(nb.nametowidget(t)) for t in nb.tabs()]][0]
            main_nb.select(net)
            shot("network")
            sub_nb = [nb for nb in find_nb(net)
                      if any("PSI List" in nb.tab(t, "text") for t in nb.tabs())][0]
            sub_nb.select([t for t in sub_nb.tabs() if "PSI List" in sub_nb.tab(t, "text")][0])
            tree = net._sc_tree
            want = set(a.nodes.split(","))
            for prod in tree.products:
                for nd in tree.iter_all_nodes(prod):
                    try:
                        net._psi_node_var.set(nd.node_id)
                        net._on_psi_node_select(None)
                        app.update()
                    except Exception:
                        errors.append(f"PSI List {nd.node_id}:\n" + traceback.format_exc())
                        continue
                    if nd.node_name in want:
                        shot(f"psi_list__{prod}__{nd.node_name}")
                        from wom.gui.app import psi_list_capacity_cells
                        cells[nd.node_id] = {tree.week_labels[w]: psi_list_capacity_cells(nd, w)[0]
                                             for w in range(tree.num_weeks())}
            st["psi_list_nodes"] = sum(1 for p in tree.products for _ in tree.iter_all_nodes(p))
            res = getattr(tree, "capacity_layer_results", None)
            st["capacity_layer"] = ({p: {k: v for k, v in r.items()
                                         if k not in ("assignments", "unallocated_lots")}
                                     for p, r in res.items()} if res else None)
            # Rice Seasonal (RequestLetter_RiceSeasonal_Implementation): the joint
            # result and the market outcome of the GUI plan, for the GUI/headless match
            rice = getattr(tree, "rice_seasonal_results", None)
            if rice and "_joint" in rice:
                st["rice_seasonal"] = {k: v for k, v in rice["_joint"].items() if k != "stats"}
                out = {"on_time": 0, "late": 0, "early": 0, "backlog_end": 0}
                for p in tree.products:
                    for nd in tree.iter_all_nodes(p):
                        if nd.node_type != "leaf_out":
                            continue
                        ship = {l: w for w, ls in nd._actual_ship.items() for l in ls}
                        for d in range(tree.num_weeks()):
                            for l in nd.psi4demand[d][0]:
                                s = ship.get(l)
                                out["on_time" if s == d else "late" if s is not None and s > d
                                    else "early" if s is not None else "backlog_end"] += 1
                st["market_outcome"] = out
            # Flow Check table 2 as the GUI shows it (RequestLetter_RiceSeasonal_PolishAdvance1
            # work 6): the summary line, the visible columns and the model total row
            fcp = net._flow_check_panel
            sub_nb.select([t for t in sub_nb.tabs() if "Flow Check" in sub_nb.tab(t, "text")][0])
            st["flow_check_summary"] = fcp._summary_var.get()
            st["flow_check_columns"] = list(fcp._market_tree.cget("displaycolumns"))
            if fcp._fc:
                st["flow_check_total"] = {k: v for k, v in fcp._fc["market"][-1].items()
                                          if not k.endswith("_qty")}
            shot("flow_check")
        except Exception:
            errors.append(traceback.format_exc())
        app.after(500, check_worldmap)

    def check_worldmap(n=[0]):
        # World Map band (work 5): wait until the plan's flows are drawn
        try:
            wm = app._worldmap_panel
            main_nb = [nb for nb in find_nb(app)
                       if str(wm) in [str(nb.nametowidget(t)) for t in nb.tabs()]][0]
            main_nb.select(wm)
            app.update()
            band = wm._band_var.get()
            n[0] += 1
            if "報告の開始週" not in band and n[0] < 120:
                app.after(500, check_worldmap)
                return
            st["worldmap_band"] = band
            shot("worldmap")
        except Exception:
            errors.append(traceback.format_exc())
        finish()

    def finish():
        with open(os.path.join(a.out, "result.json"), "w", encoding="utf-8") as f:
            json.dump({"state": st, "errors": errors, "capacity_cells": cells}, f,
                      ensure_ascii=False, indent=1, default=str)
        app.destroy()

    def poll(n=[0]):
        n[0] += 1
        if st["plan_err"] or n[0] > 1500:
            finish()
            return
        if st["plan"] and st["ppc"]:
            app.after(1500, check_network)
            return
        app.after(400, poll)

    def start():
        app._load_model_folder()
        app.update()
        app.update()
        st["plugins_after_load"] = sorted(k for k, v in app._plugin_vars.items() if v.get())
        st["status_after_load"] = app._status_var.get() if hasattr(app, "_status_var") else ""
        names = [x for x in a.plugins.split(",") if x]
        if "auto" in names:
            # "auto[,name...]": keep what the model load set (RequestLetter_RiceLegacyRetire
            # 1.4) and switch the named plugins ON in addition
            for name in names:
                if name != "auto":
                    app._plugin_vars[name].set(True)
        else:
            for name, var in app._plugin_vars.items():
                var.set(name in names)
            app._plugin_vars["capacity_layer"].set(a.layer == "on")
        st["plugins_on"] = sorted(k for k, v in app._plugin_vars.items() if v.get())
        shot("loaded")
        app.after(1500, lambda: (app._run_planning_engine(), poll()))

    app.after(1500, start)
    app.mainloop()
    print(json.dumps({"state": {k: v for k, v in st.items() if k not in ("capacity_layer", "rice_seasonal")},
                      "errors": len(errors)}, ensure_ascii=False))
    for e in errors:
        print(e)
    return 1 if errors or st["plan_err"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
