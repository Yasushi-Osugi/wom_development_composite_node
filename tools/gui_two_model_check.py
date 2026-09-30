# -*- coding: utf-8 -*-
"""
tools/gui_two_model_check.py — 実アプリの窓で、モデルを続けて読み込む操作を自動で確かめる
（RequestLetter_StalePPC_Units_KittingView P1・P2・P3・P5 の受入）

    python -m tools.gui_two_model_check --out output/stale_ppc/gui

`wom.gui.app.WOMApp`（`python -m main` と同じ窓）を起動し、次の順に操作して、画面の部品の値を
読む。窓の画像は Win32 の PrintWindow で取る（画面全体の取り込みはしない）。
モデルのフォルダには書かない（warmup の生成行は、すでに入っていれば書き直さない）。

  1  起動直後（既定のサンプルが読み込まれた状態）
  2  ev-thailand-2026 を読み込む → Run Planning Engine → PPC の完了まで待つ
  3  iphone_global を読み込む（まだ計画しない）
  4  Run Planning Engine → 計画が終わった直後（iphone の PPC は計算中）
  5  iphone の PPC の完了後
  6  PPC を失敗させて（PPC の入口を一時的に差し替える）もう一度計画する
  7  作業フォルダの外に置いたコピー（ev-thailand-2026_update）を読み込んで計画する（表 3 の確認）
  8  2 つの計画を、PPC が終わる前に続けて実行する：ev-thailand-2026 を計画し、その PPC を
     わざと遅らせ（12 秒）、終わる前に iphone_global を読み込んで計画する。その間、画面の
     P&L Summary の Revenue・Node P&L の先頭・PPC タブの状態を 0.2 秒ごとに記録する
     （前の計画＝ev-thailand の PPC の値が、一度も画面に出ないことを確かめる）

出力：<out>/steps.json（各段階で読んだ値）と、<out>/*.png（窓の画像）。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import traceback

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join("output", "stale_ppc", "gui"))
    ap.add_argument("--first", default="ev-thailand-2026")
    ap.add_argument("--second", default="iphone_global")
    ap.add_argument("--kitting", default="ev-thailand-2026_update")
    a = ap.parse_args(argv)
    os.chdir(REPO)
    os.makedirs(a.out, exist_ok=True)
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    from tkinter import filedialog, ttk
    import wom.gui.app as A
    import wom.ppc.ppc_runner as runner
    from wom.lovem.viewer import _print_window

    sample = lambda m: os.path.join(REPO, "data", "sample", m)
    tmp = tempfile.mkdtemp(prefix="wom_old_copy_")
    outside = os.path.join(tmp, "data", "sample", a.kitting)       # a folder OUTSIDE the work root
    shutil.copytree(sample(a.kitting), outside)

    steps, errors = {}, []
    st = {"folder": None, "plan": False, "ppc": None, "t0": time.time()}
    filedialog.askdirectory = lambda **k: st["folder"]
    app = A.WOMApp()
    app.geometry("1900x1020+10+10")
    mg, ppc_tab, net = app._mgmt_panel, app._ppc_panel, app._network_panel
    fcp = net._flow_check_panel

    def find_nb(widget):
        out = []
        for c in widget.winfo_children():
            if isinstance(c, ttk.Notebook):
                out.append(c)
            out += find_nb(c)
        return out

    top = [nb for nb in find_nb(app) if mg in [nb.nametowidget(t) for t in nb.tabs()]][0]
    inner = [nb for nb in find_nb(net) if fcp in [nb.nametowidget(t) for t in nb.tabs()]][0]

    def rows(tree):
        return [[str(v) for v in tree.item(i)["values"]] for i in tree.get_children()]

    def shot(name, tab=None, sub=None):
        if tab is not None:
            top.select(tab)
        if sub is not None:
            inner.select(sub)
        app.update(); app.update_idletasks()
        _print_window(int(app.wm_frame(), 16)).save(os.path.join(a.out, name + ".png"))

    def snap(name, tab=None, sub=None, extra=None):
        d = {
            "window_title": app.title(),
            "model_label": app._model_path_var.get(),
            "status_line": app._status_var.get(),
            "ppc_ctx": dict(app._ppc_ctx),
            "plan_run": dict(app._plan_run),
            "entries": {k: getattr(app, k).get() for k in ("_f_sc_tree", "_f_edge_cost", "_f_route", "_f_push")},
            "mgmt_banner": mg._ppc_banner_var.get(),
            "pl_summary": rows(mg._pl_tree),
            "node_pl": rows(mg._node_pl_tree)[:6],
            "node_pl_count": len(mg._node_pl_tree.get_children()),
            "landed_cost": rows(mg._lc_tree),
            "lc_narrative_head": mg._lc_narrative.get("1.0", "2.0").strip(),
            "ppc_tab_status": ppc_tab._status_var.get(),
            "ppc_tab_shows_cockpit": ppc_tab._cockpit is not None,
            "ppc_tab_placeholder": (ppc_tab._placeholder_var.get() if ppc_tab._cockpit is None else ""),
            "flow_check_model": fcp._model_var.get(),
            "flow_check_summary": fcp._summary_var.get(),
            "flow_check_table3": rows(fcp._kitting_tree),
            "flow_check_table1_rows": len(fcp._node_tree.get_children()),
            "flow_check_table2_rows": len(fcp._market_tree.get_children()),
            "charts_has_plan": app._chart_panel._sc_tree is not None or app._chart_panel._mgr is not None,
            "charts_text": [t.get_text() for ax in app._chart_panel.fig.axes for t in ax.texts][:2],
            "kpi_table_rows": len(app._kpi_panel.tree.get_children()),
            "at_risk_rows": len(app._risk_tree.get_children()),
            "network_has_plan": net._sc_tree is not None,
            "network_products": list(net._prod_cb["values"]),
            "psi_list_node": net._psi_list_panel._node_var.get(),
            "psi_list_rows": len(net._psi_list_panel._tree.get_children()),
            "gp_chart_text": [t.get_text() for ax in mg._gp_fig.axes for t in ax.texts][:2],
            "ccc_chart_text": [t.get_text() for ax in mg._ccc_fig.axes for t in ax.texts][:2],
            "app_mgr_is_none": app._mgr is None,
            "run_info_file": None,
        }
        p = os.path.join("output", "ppc", "ppc_run_info.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                d["run_info_file"] = json.load(f)
        if extra:
            d.update(extra)
        steps[name] = d
        shot(name, tab, sub)
        print(f"[{name}] PL={d['pl_summary'][:1]} banner={d['mgmt_banner'][:60]}", flush=True)

    o_plan_done, o_ppc_done, o_ppc_err, o_plan_err = (app._on_planning_done, app._on_ppc_done,
                                                     app._on_ppc_error, app._on_planning_error)
    hooks = {"after_plan": None}

    def plan_done(tree):
        r = o_plan_done(tree)
        st["plan"] = True
        if hooks["after_plan"]:
            # still on the main thread: the PPC thread cannot have reported yet
            try:
                hooks["after_plan"]()
            except Exception:
                errors.append("after_plan: " + traceback.format_exc()[-1500:])
        return r

    ppc_callbacks = []          # every PPC result that reached the main thread

    def ppc_done(kpi, run_id=""):
        accepted = (run_id == app._plan_run.get("run_id", "") and app._ppc_gate.is_current(run_id))
        ppc_callbacks.append({"run_id": run_id, "accepted": accepted,
                              "revenue": kpi.get("total_revenue_base")})
        r = o_ppc_done(kpi, run_id)
        if accepted:
            st["ppc"] = "done"
        return r

    def ppc_err(msg, run_id=""):
        r = o_ppc_err(msg, run_id)
        if not run_id or run_id == app._plan_run.get("run_id", ""):
            st["ppc"] = "failed"
        return r

    def plan_err(tb):
        errors.append("planning: " + str(tb)[-1500:]); st["ppc"] = "failed"
        app._progress.stop()

    app._on_planning_done, app._on_ppc_done, app._on_ppc_error, app._on_planning_error = (
        plan_done, ppc_done, ppc_err, plan_err)

    def load(folder):
        st["folder"] = folder
        app._load_model_folder()
        app.update()

    def set_plugins(model):
        gp = os.path.join("tests", "golden", model + ".json")
        want = set()
        if os.path.exists(gp):
            with open(gp, encoding="utf-8") as f:
                want = set(json.load(f)["config"]["plugins"])
        for n, inst in app._plugin_instances.items():
            app._plugin_vars[n].set(type(inst).__name__ in want)

    def plan(after_plan, then):
        st["plan"], st["ppc"], st["t0"] = False, None, time.time()
        hooks["after_plan"] = after_plan
        app._run_planning_engine()

        def poll():
            if st["ppc"] is not None or time.time() - st["t0"] > 480:
                if st["ppc"] is None:
                    errors.append("timeout waiting for PPC")
                app.after(1500, then)
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
        return g

    def s1():
        snap("1_startup", mg)
        load(sample(a.first)); set_plugins(a.first)
        snap("2a_first_loaded", mg)
        plan(None, guard(s2))

    def s2():
        snap("2b_first_ppc_done", mg)
        load(sample(a.second)); set_plugins(a.second)
        snap("3_second_loaded_before_plan", mg)
        shot("3_second_loaded_before_plan__ppc_tab", ppc_tab)
        plan(lambda: snap("4_second_planned_ppc_running", mg), guard(s3))

    def s3():
        snap("5_second_ppc_done", mg)
        shot("5_second_ppc_done__ppc_tab", ppc_tab)
        shot("5_second_ppc_done__flow_check", net, fcp)
        steps["5_second_ppc_done"]["flow_check_table3_after"] = rows(fcp._kitting_tree)
        # 6: PPC fails
        orig = runner.run_ppc_from_psi

        def boom(*_a, **_k):
            raise RuntimeError("PPC を失敗させた（受入の確認用）")

        runner.run_ppc_from_psi = boom

        def after6():
            runner.run_ppc_from_psi = orig
            snap("6_second_ppc_failed", mg)
            shot("6_second_ppc_failed__ppc_tab", ppc_tab)
            load(outside); set_plugins(a.kitting)
            snap("7a_outside_copy_loaded", mg)
            plan(None, guard(s4))
        plan(None, guard(after6))

    def s4():
        snap("7b_outside_copy_ppc_done", net, fcp)
        shot("7b_outside_copy_ppc_done__management", mg)
        s8()

    def s8():
        """Two plans in a row; the first plan's PPC is slow and finishes later."""
        orig = runner.run_ppc_from_psi
        calls = {"n": 0}
        seen = []                     # (seconds, P&L revenue cells, first Node P&L cell, PPC tab status)
        t0 = time.time()
        watching = {"on": True}

        def slow(*args, **kw):
            calls["n"] += 1
            if calls["n"] == 1:       # the PPC of the FIRST plan
                time.sleep(12)
            return orig(*args, **kw)

        runner.run_ppc_from_psi = slow

        def watch():
            if not watching["on"]:
                return
            pl = [r[1] for r in rows(mg._pl_tree)]
            npl = rows(mg._node_pl_tree)
            cur = (pl, (npl[0][0] if npl else ""), ppc_tab._status_var.get()[:40],
                   app._plan_run.get("run_id", "")[-24:])
            if not seen or seen[-1][1:] != cur:
                seen.append((round(time.time() - t0, 1),) + cur)
            app.after(200, watch)

        def second_plan_now():
            # still inside _on_planning_done of the first plan: its PPC thread has
            # just started (and sleeps). Load the second model and plan it.
            hooks["after_plan"] = None
            first_run = dict(app._plan_run)
            steps["8_meta"] = {"first_run_id": first_run["run_id"]}
            load(sample(a.second)); set_plugins(a.second)
            snap("8a_second_loaded_while_first_ppc_runs", mg)
            st["plan"], st["ppc"], st["t0"] = False, None, time.time()
            app._run_planning_engine()

        def after8():
            def done8():
                watching["on"] = False
                runner.run_ppc_from_psi = orig
                snap("8b_second_ppc_done_first_ppc_finished_late", mg,
                     extra={"ppc_callbacks": list(ppc_callbacks), "screen_history": seen,
                            "ppc_calls": calls["n"]})
                finish()
            app.after(3000, done8)

        load(sample(a.first)); set_plugins(a.first)
        del ppc_callbacks[:]
        app.after(200, watch)
        st["plan"], st["ppc"], st["t0"] = False, None, time.time()
        hooks["after_plan"] = second_plan_now
        app._run_planning_engine()

        def poll():
            if st["ppc"] is not None or time.time() - st["t0"] > 480:
                if st["ppc"] is None:
                    errors.append("timeout waiting for PPC (step 8)")
                app.after(500, guard(after8))
            else:
                app.after(300, poll)
        app.after(300, poll)

    def finish():
        try:
            with open(os.path.join(a.out, "steps.json"), "w", encoding="utf-8") as f:
                json.dump({"errors": errors, "steps": steps}, f, ensure_ascii=False, indent=1, default=str)
        finally:
            app.destroy()

    app.after(2000, guard(s1))
    app.mainloop()
    shutil.rmtree(tmp, ignore_errors=True)
    print("errors:", errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
