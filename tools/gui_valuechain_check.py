# -*- coding: utf-8 -*-
"""
tools/gui_valuechain_check.py — Management の「Value Chain」を実アプリの窓で確かめる
（RequestLetter_StageD_Phase1 Part 2・受入 7）

    python -m tools.gui_valuechain_check --out output/valuechain/gui

1  Cookie-jp-2026 を読み込み → Run Planning Engine → 台帳ができるまで待つ
2  V3（HQ・累計）、V2（E_CN・現地通貨・単週）、V1（Retail_JP_CVS）、通貨「共通」の画面を撮る
3  未設定価格・為替・未評価の一覧を開いて撮る
4  soysauce-jpy-2027-alloc を読み込み → 計画。台帳の作成中・作成後に、Cookie の台帳が出ないこと
   （0.2 秒ごとに帯と表の行数を記録）
5  Run Simulation の後は「台帳がありません」になること（iphone_global）
窓は DPI を意識しない（python -m main と同じ）。窓の画像は PrintWindow。
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
    ap.add_argument("--out", default=os.path.join("output", "valuechain", "gui"))
    a = ap.parse_args(argv)
    os.chdir(REPO)
    os.makedirs(a.out, exist_ok=True)
    from tkinter import filedialog
    import wom.gui.app as A
    from wom.lovem.viewer import _print_window

    st = {"folder": None, "ppc": None, "vc": None}
    filedialog.askdirectory = lambda **k: st["folder"]
    app = A.WOMApp()
    app.geometry("1536x824+0+0")
    vc = app._vc_panel
    steps, errors, history = {}, [], []
    sample = lambda m: os.path.join(REPO, "data", "sample", m)

    o_ppc, o_built = app._on_ppc_done, vc._built

    def ppc_done(kpi, run_id=""):
        r = o_ppc(kpi, run_id)
        st["ppc"] = "done"
        return r
    app._on_ppc_done = ppc_done

    def built(run_id, res, err, on_done):
        r = o_built(run_id, res, err, on_done)
        st["vc"] = ("err" if err else "ok", run_id)
        return r
    vc._built = built

    def select_vc():
        app._mgmt_nb.select(vc)
        for nb in _notebooks(app):
            if app._mgmt_outer in [nb.nametowidget(t) for t in nb.tabs()]:
                nb.select(app._mgmt_outer)

    def shot(name):
        app.update(); app.update_idletasks()
        _print_window(int(app.wm_frame(), 16)).save(os.path.join(a.out, name + ".png"))

    def rows():
        return [list(vc._tree.item(i)["values"]) for i in vc._tree.get_children()]

    def snap(name):
        select_vc()
        app.update()
        steps[name] = {"band": vc._band_var.get(), "note": vc._note_var.get(),
                       "view": vc._view_var.get(), "currency": vc._cur_var.get(),
                       "period": vc._period_var.get(), "entity": vc._ent_var.get(), "node": vc._node_var.get(),
                       "columns": list(vc._tree["columns"]), "n_rows": len(vc._tree.get_children()),
                       "last_row": rows()[-1] if rows() else None,
                       "channels": [list(vc._ch_tree.item(i)["values"]) for i in vc._ch_tree.get_children()][:6],
                       "buttons": [vc._btn_unvalued.cget("text"), vc._btn_missing.cget("text"),
                                   vc._btn_fx.cget("text")],
                       "plan_on_screen": app._plan_run.get("run_id", ""),
                       "ledger_plan": vc._result["plan_id"] if vc._result else None}
        shot(name)
        print(f"[{name}] {steps[name]['band'][:90]} | rows {steps[name]['n_rows']} | {steps[name]['last_row']}",
              flush=True)

    def wait(cond, then, limit=900):
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

    def load(model):
        st["folder"] = sample(model)
        app._load_model_folder()
        app.update()

    def plan():
        st["ppc"], st["vc"] = None, None
        app._run_planning_engine()

    def s1():
        load("Cookie-jp-2026")
        snap("0_cookie_loaded")
        plan()
        wait(lambda: st["vc"] is not None and st["ppc"] is not None, s2)

    def s2():
        vc._view_var.set("V3"); vc._period_var.set("cum"); vc._cur_var.set("HQ"); vc._refresh()
        snap("1_cookie_v3_hq_cum")
        vc._view_var.set("V2"); vc._ent_var.set("E_CN"); vc._on_entity()
        vc._cur_var.set("現地"); vc._period_var.set("cum"); vc._refresh()
        snap("2_cookie_v2_ECN_local_cum")
        vc._view_var.set("V1"); vc._ent_var.set("（すべて）"); vc._on_entity()
        vc._node_var.set("DC_Import_Main"); vc._cur_var.set("HQ"); vc._period_var.set("wk"); vc._refresh()
        snap("3_cookie_v1_DC_Import_Main_hq_wk")
        vc._view_var.set("V3"); vc._cur_var.set("共通"); vc._refresh()
        snap("4_cookie_v3_common_cum")
        for name, fn in (("5_missing", vc._show_missing), ("6_fx", vc._show_fx), ("7_unvalued", vc._show_unvalued)):
            fn()
            app.update()
            top = [w for w in _all(app) if w.winfo_class() == "Toplevel"][-1]
            top.update()
            _print_window(int(top.wm_frame(), 16)).save(os.path.join(a.out, name + ".png"))
            top.destroy()
        # 4: alloc, watch that Cookie's ledger never shows for the alloc plan
        load("soysauce-jpy-2027-alloc")
        snap("8_alloc_loaded")
        t0 = time.time()
        watching = {"on": True}

        def watch():
            if not watching["on"]:
                return
            cur = (vc._band_var.get()[:70], len(vc._tree.get_children()),
                   vc._result["plan_id"] if vc._result else None, app._plan_run.get("run_id", ""))
            if not history or history[-1][1:] != cur:
                history.append((round(time.time() - t0, 1),) + cur)
            app.after(200, watch)
        app.after(200, watch)
        plan()

        def after_alloc():
            watching["on"] = False
            vc._view_var.set("V3"); vc._cur_var.set("HQ"); vc._period_var.set("cum"); vc._refresh()
            snap("9_alloc_v3_hq_cum")
            vc._view_var.set("V2"); vc._ent_var.set("E_US"); vc._on_entity()
            vc._cur_var.set("現地"); vc._refresh()
            snap("10_alloc_v2_EUS_local_cum")
            load("iphone_global")
            app._run_simulation()
            wait(lambda: getattr(app, "_shown_result", "") == "sim", after_sim, 300)
        wait(lambda: st["vc"] is not None and st["ppc"] is not None, after_alloc)

    def after_sim():
        snap("11_after_simulation")
        finish()

    def finish():
        with open(os.path.join(a.out, "steps.json"), "w", encoding="utf-8") as f:
            json.dump({"errors": errors, "steps": steps, "history": history}, f, ensure_ascii=False,
                      indent=1, default=str)
        app.destroy()

    app.after(1500, guard(s1))
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
