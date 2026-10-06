# -*- coding: utf-8 -*-
"""
tools/gui_valuechain_r2_check.py — Value Chain の第 2 回（内部の未実現利益の消去後）を実アプリの窓で確かめる
（RequestLetter_StageD_Phase2 §2.2・受入 4）

    python -m tools.gui_valuechain_r2_check --out output/valuechain_r2/gui

Cookie-jp-2026 と soysauce-jpy-2027-alloc を、`tools/valuechain_run.py` と同じプラグイン
（BufferingStockOptimizer・CapacityOverride・HolidayCalendar）に印を付けて計画し、台帳ができたら、
V3 の消去後（既定）・消去前・単週・共通の評価通貨、未実現利益の一覧の画面を撮る。表の最後の行の値を
steps.json に残す（CLI の vc_checks.json の値と比べるため）。窓は DPI を意識しない 1536×824、画像は PrintWindow。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PLUGINS = {"BufferingStockOptimizerPlugin", "CapacityOverridePlugin", "HolidayCalendarPlugin"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join("output", "valuechain_r2", "gui"))
    a = ap.parse_args(argv)
    os.chdir(REPO)
    os.makedirs(a.out, exist_ok=True)
    from tkinter import filedialog
    import wom.gui.app as A
    from wom.lovem.viewer import _print_window

    st = {"folder": None, "vc": None}
    filedialog.askdirectory = lambda **k: st["folder"]
    app = A.WOMApp()
    app.geometry("1536x824+0+0")
    vc = app._vc_panel
    for name, inst in app._plugin_instances.items():          # the same plan as the CLI
        app._plugin_vars[name].set(type(inst).__name__ in PLUGINS)
    steps, errors = {}, []
    o_built = vc._built

    def built(run_id, res, err, on_done):
        r = o_built(run_id, res, err, on_done)
        st["vc"] = ("err" if err else "ok", run_id)
        return r
    vc._built = built

    def select_vc():
        app._mgmt_nb.select(vc)
        for nb in _notebooks(app):
            if str(app._mgmt_outer) in [str(nb.nametowidget(t)) for t in nb.tabs()]:
                nb.select(app._mgmt_outer)

    def shot(name):
        app.update()
        app.update_idletasks()
        _print_window(int(app.wm_frame(), 16)).save(os.path.join(a.out, name + ".png"))

    def rows():
        return [list(vc._tree.item(i)["values"]) for i in vc._tree.get_children()]

    def snap(name):
        select_vc()
        app.update()
        steps[name] = {"band": vc._band_var.get(), "note": vc._note_var.get(),
                       "headings": [vc._tree.heading(c)["text"] for c in vc._tree["columns"]],
                       "last_row": rows()[-1] if rows() else None, "n_rows": len(rows()),
                       "unreal_button": vc._btn_unreal.cget("text"),
                       "ledger_plan": vc._result["plan_id"] if vc._result else None}
        shot(name)
        print(f"[{name}] {steps[name]['last_row']}", flush=True)

    def popup(name, fn):
        fn()
        app.update()
        top = [w for w in _all(app) if w.winfo_class() == "Toplevel"][-1]
        top.update()
        tv = [c for c in top.winfo_children()][0]
        steps[name] = {"title": top.title(),
                       "rows": [list(tv.item(i)["values"]) for i in tv.get_children()][:20],
                       "columns": [tv.heading(c)["text"] for c in tv["columns"]]}
        _print_window(int(top.wm_frame(), 16)).save(os.path.join(a.out, name + ".png"))
        top.destroy()

    def wait(cond, then, limit=1200):
        t0 = time.time()

        def poll():
            if cond() or time.time() - t0 > limit:
                if not cond():
                    errors.append(f"timeout before {then.__name__}")
                app.after(500, guard(then))
            else:
                app.after(300, poll)
        app.after(300, poll)

    def guard(fn):
        def g():
            try:
                fn()
            except Exception:
                errors.append(fn.__name__ + ": " + traceback.format_exc()[-2000:])
                finish()
        g.__name__ = fn.__name__
        return g

    def plan(model, then):
        st["folder"] = os.path.join(REPO, "data", "sample", model)
        st["vc"] = None
        app._load_model_folder()
        app.update()
        app._run_planning_engine()
        wait(lambda: st["vc"] is not None, then)

    def cookie():
        plan("Cookie-jp-2026", cookie_shots)

    def cookie_shots():
        vc._view_var.set("V3"); vc._cur_var.set("HQ"); vc._period_var.set("cum")
        snap("1_cookie_v3_default")                      # the default: after elimination
        steps["1_cookie_v3_default"]["round"] = vc._round_var.get()
        vc._refresh()
        snap("2_cookie_v3_r2_hq_cum")
        vc._round_var.set("r1"); vc._refresh()
        snap("3_cookie_v3_r1_hq_cum")
        vc._round_var.set("r2"); vc._period_var.set("wk"); vc._refresh()
        snap("4_cookie_v3_r2_hq_wk")
        vc._cur_var.set("共通"); vc._period_var.set("cum"); vc._refresh()
        snap("5_cookie_v3_r2_common_cum")
        vc._view_var.set("V2"); vc._ent_var.set("E_CN"); vc._on_entity(); vc._cur_var.set("現地"); vc._refresh()
        snap("6_cookie_v2_ECN_local_cum")
        vc._view_var.set("V3"); vc._ent_var.set("（すべて）"); vc._on_entity(); vc._cur_var.set("HQ"); vc._refresh()
        popup("7_cookie_unrealized_list", vc._show_unrealized)
        plan("soysauce-jpy-2027-alloc", alloc_shots)

    def alloc_shots():
        vc._view_var.set("V3"); vc._cur_var.set("HQ"); vc._period_var.set("cum"); vc._round_var.set("r2")
        vc._refresh()
        snap("8_alloc_v3_r2_hq_cum")
        vc._round_var.set("r1"); vc._refresh()
        snap("9_alloc_v3_r1_hq_cum")
        vc._round_var.set("r2"); vc._refresh()
        popup("10_alloc_unrealized_list", vc._show_unrealized)
        finish()

    def finish():
        with open(os.path.join(a.out, "steps.json"), "w", encoding="utf-8") as f:
            json.dump({"errors": errors, "steps": steps}, f, ensure_ascii=False, indent=1, default=str)
        app.destroy()

    app.after(1500, guard(cookie))
    app.mainloop()
    print("errors:", errors)
    return 1 if errors else 0


def _all(widget):
    out = []
    for c in widget.winfo_children():
        out += [c] + _all(c)
    return out


def _notebooks(widget):
    from tkinter import ttk
    out = []
    for c in widget.winfo_children():
        if isinstance(c, ttk.Notebook):
            out.append(c)
        out += _notebooks(c)
    return out


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
