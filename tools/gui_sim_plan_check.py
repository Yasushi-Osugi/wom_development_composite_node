# -*- coding: utf-8 -*-
"""
tools/gui_sim_plan_check.py — Run Simulation と Run Planning Engine を続けて実行したときの
Management の表示を、実アプリの窓で自動で確かめる（RequestLetter_SimMgmt_WorldMapTrial 1.1 の受入）

    python -m tools.gui_sim_plan_check --out output/sim_mgmt/gui

`wom.gui.app.WOMApp`（`python -m main` と同じ窓）を起動し、次の順に操作して、画面の部品の値を
読む。窓の画像は Win32 の PrintWindow で取る。

  1  モデルを読み込む → Run Simulation の完了後
  2  続けて Run Planning Engine → 計画が終わった直後（PPC 計算中）
  3  PPC の完了後（PPC の結果だけ。Simulation の数字が残らないこと）
  4  続けて Run Simulation（Planning の後の Simulation）
  5  Run Planning Engine の PPC が終わる前に Run Simulation を実行する（PPC を 8 秒遅らせる）。
     遅れて終わった PPC の結果が、画面に出ないこと

出力：<out>/steps.json（各段階で読んだ値）と、<out>/*.png（窓の画像）。
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
    ap.add_argument("--out", default=os.path.join("output", "sim_mgmt", "gui"))
    ap.add_argument("--model", default="iphone_global")   # Run Simulation needs a region-keyed capacity_plan
    a = ap.parse_args(argv)
    os.chdir(REPO)
    os.makedirs(a.out, exist_ok=True)
    # DPI-unaware, like `python -m main` (the window is what the owner sees).
    from tkinter import filedialog, ttk
    import wom.gui.app as A
    import wom.ppc.ppc_runner as runner
    from wom.lovem.viewer import _print_window

    folder = os.path.join(REPO, "data", "sample", a.model)
    steps, errors = {}, []
    st = {"sim": False, "ppc": None, "t0": time.time()}
    filedialog.askdirectory = lambda **k: folder
    app = A.WOMApp()
    app.geometry("1536x824+0+0")          # the owner's screen, maximized (1920x1080 at 125 %)
    mg, ppc_tab = app._mgmt_panel, app._ppc_panel

    def find_nb(widget):
        out = []
        for c in widget.winfo_children():
            if isinstance(c, ttk.Notebook):
                out.append(c)
            out += find_nb(c)
        return out

    # the main notebook (holds the PPC tab); Management is a container with its own
    # notebook (Overview = mg, Value Chain) since RequestLetter_StageD_Phase1 Part 2
    _main = [nb for nb in find_nb(app) if app._ppc_panel in [nb.nametowidget(t) for t in nb.tabs()]][0]

    class _Top:
        def select(self, tab):
            if tab is mg or tab is getattr(app, '_vc_panel', None):
                _main.select(app._mgmt_outer)
                app._mgmt_nb.select(tab)
            else:
                _main.select(tab)
    top = _Top()

    def rows(tree):
        return [[str(v) for v in tree.item(i)["values"]] for i in tree.get_children()]

    def snap(name, extra=None):
        top.select(mg)
        app.update(); app.update_idletasks()
        d = {
            "model_label": app._model_path_var.get(),
            "status_line": app._status_var.get(),
            "shown_result": getattr(app, "_shown_result", None),
            "display_source": mg._display_source,
            "ppc_ctx": dict(app._ppc_ctx),
            "mgmt_banner": mg._ppc_banner_var.get(),
            "pl_summary": rows(mg._pl_tree),
            "node_pl": rows(mg._node_pl_tree)[:3],
            "landed_cost": rows(mg._lc_tree),
            "lc_narrative_head": mg._lc_narrative.get("1.0", "3.0").strip(),
            "ccc_chart": {"title": [ax.get_title() for ax in mg._ccc_fig.axes],
                          "xticks": [t.get_text() for ax in mg._ccc_fig.axes for t in ax.get_xticklabels()],
                          "texts": [t.get_text() for ax in mg._ccc_fig.axes for t in ax.texts][:6]},
            "gp_chart": {"title": [ax.get_title() for ax in mg._gp_fig.axes],
                         "xticks": [t.get_text() for ax in mg._gp_fig.axes for t in ax.get_xticklabels()],
                         "texts": [t.get_text() for ax in mg._gp_fig.axes for t in ax.texts][:6]},
            "ppc_tab_status": ppc_tab._status_var.get(),
            "ppc_tab_shows_cockpit": ppc_tab._cockpit is not None,
            "mgr_scenarios": (app._mgr.scenarios() if app._mgr is not None else []),
        }
        if extra:
            d.update(extra)
        steps[name] = d
        _print_window(int(app.wm_frame(), 16)).save(os.path.join(a.out, name + ".png"))
        print(f"[{name}] src={d['display_source']} PL={[r[:2] + r[-1:] for r in d['pl_summary']]}", flush=True)

    o_sim_done, o_plan_done, o_ppc_done, o_ppc_err = (app._on_simulation_done, app._on_planning_done,
                                                     app._on_ppc_done, app._on_ppc_error)
    hooks = {"after_plan": None}
    ppc_callbacks = []

    def sim_done():
        r = o_sim_done()
        st["sim"] = True
        return r

    def plan_done(tree):
        r = o_plan_done(tree)
        if hooks["after_plan"]:
            try:
                hooks["after_plan"]()
            except Exception:
                errors.append("after_plan: " + traceback.format_exc()[-1500:])
        return r

    def ppc_done(kpi, run_id=""):
        accepted = (run_id == app._plan_run.get("run_id", "") and app._ppc_gate.is_current(run_id))
        ppc_callbacks.append({"run_id": run_id, "accepted": accepted,
                              "revenue": kpi.get("total_revenue_base")})
        r = o_ppc_done(kpi, run_id)
        st["ppc"] = "done"
        return r

    def ppc_err(msg, run_id=""):
        r = o_ppc_err(msg, run_id)
        st["ppc"] = "failed"
        return r

    def sim_err(tb):
        errors.append("simulation: " + str(tb)[-1500:]); st["sim"] = True
        app._progress.stop()

    def plan_err(tb):
        errors.append("planning: " + str(tb)[-1500:]); st["ppc"] = "failed"
        app._progress.stop()

    app._on_simulation_done, app._on_planning_done = sim_done, plan_done
    app._on_ppc_done, app._on_ppc_error = ppc_done, ppc_err
    app._on_simulation_error, app._on_planning_error = sim_err, plan_err

    def wait(cond, then, limit=480):
        t0 = time.time()

        def poll():
            if cond() or time.time() - t0 > limit:
                if not cond():
                    errors.append(f"timeout: {then.__name__}")
                app.after(800, guard(then))
            else:
                app.after(300, poll)
        app.after(300, poll)

    def guard(fn):
        def g():
            try:
                fn()
            except Exception:
                errors.append(fn.__name__ + ": " + traceback.format_exc()[-2500:])
                finish()
        g.__name__ = fn.__name__
        return g

    def run_sim(then):
        st["sim"] = False
        app._run_simulation()
        wait(lambda: st["sim"], then)

    def run_plan(then, after_plan=None):
        st["ppc"] = None
        hooks["after_plan"] = after_plan
        app._run_planning_engine()
        wait(lambda: st["ppc"] is not None, then)

    def s0():
        app._load_model_folder()
        app.update()
        run_sim(s1)

    def s1():
        snap("1_simulation_done")
        run_plan(s3, after_plan=lambda: snap("2_planning_done_ppc_running"))

    def s3():
        snap("3_planning_ppc_done")
        top.select(ppc_tab)                          # 1.2: the PPC tab inside the app
        app.update(); app.update_idletasks()
        _print_window(int(app.wm_frame(), 16)).save(os.path.join(a.out, "3_planning_ppc_done__ppc_tab.png"))
        run_sim(s4)

    def s4():
        snap("4_simulation_after_planning")
        # 5: a PPC that is still running when a simulation replaces the plan
        orig = runner.run_ppc_from_psi

        def slow(*args, **kw):
            time.sleep(8)
            return orig(*args, **kw)

        runner.run_ppc_from_psi = slow
        del ppc_callbacks[:]
        seen = []
        watching = {"on": True}
        t0 = time.time()

        def watch():
            if not watching["on"]:
                return
            cur = (mg._display_source, [r[1] for r in rows(mg._pl_tree)][:3],
                   mg._ppc_banner_var.get()[:30])
            if not seen or seen[-1][1:] != cur:
                seen.append((round(time.time() - t0, 1),) + cur)
            app.after(200, watch)

        def sim_now():
            hooks["after_plan"] = None
            st["sim"] = False
            app._run_simulation()

        def after5():
            def done5():
                watching["on"] = False
                runner.run_ppc_from_psi = orig
                snap("5_simulation_while_ppc_running__ppc_finished_late",
                     extra={"ppc_callbacks": list(ppc_callbacks), "screen_history": seen})
                finish()
            wait(lambda: st["sim"], done5)

        app.after(200, watch)
        st["ppc"] = None
        hooks["after_plan"] = sim_now
        app._run_planning_engine()
        wait(lambda: st["ppc"] is not None, after5, limit=120)

    def finish():
        try:
            with open(os.path.join(a.out, "steps.json"), "w", encoding="utf-8") as f:
                json.dump({"errors": errors, "steps": steps}, f, ensure_ascii=False, indent=1, default=str)
        finally:
            app.destroy()

    app.after(2000, guard(s0))
    app.mainloop()
    print("errors:", errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
