# -*- coding: utf-8 -*-
"""
tools/gui_worldmap_check.py — World Map（実出荷の流れ）を実アプリの窓で確かめる
（RequestLetter_WorldMap_ActualFlows 受入 3・6、スクリーンショット）

    python -m tools.gui_worldmap_check --out output/worldmap_check [--models a,b,...] [--shots]

モデルごとに：Load Model Folder → World Map タブ → Run Planning Engine → 流れ（出荷の記録）が
出るまで待つ → PPC・台帳も終わるまで待つ → 報告の期間から 40 週を再生して 1 週の描画時間を測る。
0.2 秒ごとに、帯・表示中の流れの計画 ID・画面の計画 ID を記録する（受入 6：前のモデルの計画の
流れが残らないこと）。--shots で、依頼の §5 のスクリーンショットを撮る。
窓は DPI を意識しない（python -m main と同じ）1536×824。画像は PrintWindow。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import traceback

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLDEN = ["Cookie-jp-2026", "apparel-global-2028-2029", "apparel-us-2026", "bom-test-2026",
          "ev-europe-2026", "ev-thailand-2026", "iphone_global", "oil-global-2027",
          "rice-japan-2027-2028", "smartx-2027-2029", "soysauce-eu-2027", "soysauce-jpy-2027",
          "soysauce-us-2027"]
ALL_MODELS = GOLDEN + ["soysauce-jpy-2027-alloc", "ev-thailand-2026_update"]

# (model, file name, SKU, view box lon0, lat0, lon1, lat1 or None = node extent, mode, week offset)
SHOTS = [
    ("Cookie-jp-2026", "cookie_japan_all", "All", (128.0, 29.0, 147.0, 44.0), "ship", 20),
    ("Cookie-jp-2026", "cookie_import_beijing_japan", "Cookie_Import", (112.0, 28.0, 145.0, 44.0), "ship", 20),
    ("soysauce-jpy-2027-alloc", "alloc_world_ship", "All", (-130.0, 20.0, 150.0, 62.0), "ship", 30),
    ("soysauce-jpy-2027-alloc", "alloc_world_transit", "All", (-130.0, 20.0, 150.0, 62.0), "transit", 30),
    ("iphone_global", "iphone_world", "All", (-180.0, -40.0, 180.0, 70.0), "ship", 20),
    ("oil-global-2027", "oil_middleeast_japan", "Gasoline_Local", (40.0, 10.0, 148.0, 46.0), "transit", 20),
    ("ev-thailand-2026", "ev_thailand", "All", None, "ship", 20),
    ("rice-japan-2027-2028", "rice_japan", "All", None, "ship", 30),
    ("ev-europe-2026", "ev_europe_yards", "EVmaker_Local", None, "ship", 20),
    ("bom-test-2026", "bom_test_yards", "All", None, "ship", 5),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join("output", "worldmap_check"))
    ap.add_argument("--models", default=",".join(ALL_MODELS))
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--play-weeks", type=int, default=40)
    a = ap.parse_args(argv)
    os.chdir(REPO)
    os.makedirs(a.out, exist_ok=True)
    models = [m for m in a.models.split(",") if m]

    from tkinter import filedialog
    import wom.gui.app as A
    from wom.lovem.viewer import _print_window
    from wom.worldmap_ne.data import merc_y

    st = {"folder": None, "ppc": None, "vc": None}
    filedialog.askdirectory = lambda **k: st["folder"]
    app = A.WOMApp()
    app.geometry("1536x824+0+0")
    wm = app._worldmap_panel
    vc = getattr(app, "_vc_panel", None)
    results, errors, history = [], [], []

    o_ppc = app._on_ppc_done

    def ppc_done(kpi, run_id=""):
        r = o_ppc(kpi, run_id)
        st["ppc"] = run_id or "done"
        return r
    app._on_ppc_done = ppc_done
    if vc is not None:
        o_built = vc._built

        def built(run_id, res, err, on_done):
            r = o_built(run_id, res, err, on_done)
            st["vc"] = run_id
            return r
        vc._built = built

    def select_tab():
        for nb in _notebooks(app):
            if str(wm) in [str(nb.nametowidget(t)) for t in nb.tabs()]:
                nb.select(wm)

    def shot(name):
        app.update()
        app.update_idletasks()
        _print_window(int(app.wm_frame(), 16)).save(os.path.join(a.out, name + ".png"))

    t_watch = [time.time()]

    def watch():
        cur = (wm._band_var.get()[:90], wm.flows.plan_id if wm.flows else None,
               app._plan_run.get("run_id", ""), os.path.basename(wm.model_dir))
        if not history or history[-1][1:] != cur:
            history.append((round(time.time() - t_watch[0], 1),) + cur)
        app.after(200, watch)

    def wait(cond, then, limit=1800):
        t0 = time.time()

        def poll():
            done = False
            try:
                done = cond()
            except Exception:
                done = False
            if done or time.time() - t0 > limit:
                if not done:
                    errors.append(f"timeout before {then.__name__}")
                app.after(300, guard(then))
            else:
                app.after(300, poll)
        app.after(300, poll)

    def guard(fn):
        def g():
            try:
                fn()
            except Exception:
                errors.append(fn.__name__ + ": " + traceback.format_exc()[-2500:])
                next_model()
        g.__name__ = fn.__name__
        return g

    queue = list(models)
    cur = {}

    def next_model():
        if not queue:
            finish()
            return
        m = queue.pop(0)
        cur.clear()
        cur.update({"model": m})
        t0 = time.perf_counter()
        st["folder"] = os.path.join(REPO, "data", "sample", m)
        st["ppc"], st["vc"] = None, None
        app._load_model_folder()
        select_tab()
        app.update()
        L = wm.layout
        cur.update({"load_s": round(time.perf_counter() - t0, 2),
                    "flows_after_load": wm.flows is not None,
                    "nodes_drawn": len(L.nodes) if L else 0,
                    "missing_coords": [x["node_id"] for x in L.missing_coords] if L else [],
                    "undrawable_edges": [x["edge"] for x in L.undrawable_edges] if L else [],
                    "edges_static": len(L.edges) if L else 0,
                    "products": L.products if L else []})
        shot(f"{m}__0_loaded")
        cur["t_plan"] = time.perf_counter()
        app._run_planning_engine()
        wait(lambda: app._plan_run.get("run_id", "") and wm._current_run_id == app._plan_run["run_id"]
             and ("流れを出しません" in wm._band_var.get() or wm.flows is not None), flows_ready)

    def flows_ready():
        cur["plan_and_records_s"] = round(time.perf_counter() - cur["t_plan"], 1)
        cur["records_s"] = round(getattr(app, "_records_seconds", float("nan")), 2)
        cur["run_id"] = app._plan_run.get("run_id", "")
        cur["band"] = wm._band_var.get()
        F = wm.flows
        cur["flows"] = F is not None
        if F is not None:
            cur.update({"flows_plan_id_ok": F.plan_id == cur["run_id"], "shipments": F.n_shipments,
                        "edges_with_flow": len(F.edge_keys), "weeks": len(F.week_labels),
                        "lot_flow_mode": F.lot_flow_mode})
        has_vc = vc is not None and os.path.exists(os.path.join(st["folder"], "vc_config.csv"))
        wait(lambda: st["ppc"] is not None and (st["vc"] is not None or not has_vc), measure, 900)

    def measure():
        F = wm.flows
        if F is not None:
            wm.go("Nodes")
            ms = []
            w0 = wm._report_idx
            for i in range(a.play_weeks):
                ms.append(wm.set_week((w0 + i) % len(F.week_labels)))
            cur["week_ms_median"] = round(statistics.median(ms), 1)
            cur["week_ms_p95"] = round(sorted(ms)[int(0.95 * (len(ms) - 1))], 1)
            wm._mode_var.set("transit")
            ms2 = [wm.set_week((w0 + i) % len(F.week_labels)) for i in range(10)]
            cur["week_ms_transit_median"] = round(statistics.median(ms2), 1)
            wm._mode_var.set("ship")
            # the play button itself (3 ticks)
            wm._speed_var.set("250")
            wm.play()
            app.after(900, guard(after_play))
        else:
            after_play()

    def after_play():
        cur["played"] = wm._week
        wm.pause()
        wm._speed_var.set("1000")
        if wm.flows is not None and wm.flows.edge_keys:
            # a node and an edge click (info panel)
            nid = wm._node_ids[0]
            nd = wm.layout.nodes[nid]
            px, py = wm.ax.transData.transform((nd.x, nd.y))
            cur["click_node"] = wm.pick_at(px, py)
            cur["click_node_info"] = wm._info.get("1.0", "end")[:300]
        if a.shots:
            for (m, name, sku, box, mode, off) in SHOTS:
                if m != cur["model"] or wm.flows is None:
                    continue
                wm._sku_var.set(sku)
                wm._on_selection()
                wm._mode_var.set(mode)
                if box is None:
                    wm.go("Nodes")
                else:
                    lon0, lat0, lon1, lat1 = box
                    wm.set_view(lon0, float(merc_y(lat0)), lon1, float(merc_y(lat1)))
                wm.set_week(wm._report_idx + off)
                if name == "cookie_import_beijing_japan":
                    k = next((i for i, g in enumerate(wm._geo) if g == ("Factory_GP_CN", "DC_Import_Buffer")), None)
                    cur["beijing_to_buffer_edge"] = k is not None
                    if k is not None:
                        wm._pick = ("edge", k)
                        wm._show_pick()
                shot(name)
            wm._sku_var.set("All")
            wm._on_selection()
            wm._mode_var.set("ship")
        cur["errors_so_far"] = len(errors)
        results.append({k: v for k, v in cur.items() if k != "t_plan"})
        print(f"[{cur['model']}] flows={cur.get('flows')} ships={cur.get('shipments')} "
              f"records={cur.get('records_s')}s week_ms={cur.get('week_ms_median')} "
              f"missing={len(cur.get('missing_coords', []))}", flush=True)
        app.after(500, next_model)

    def finish():
        with open(os.path.join(a.out, "steps.json"), "w", encoding="utf-8") as f:
            json.dump({"errors": errors, "results": results, "history": history}, f,
                      ensure_ascii=False, indent=1, default=str)
        app.destroy()

    app.after(200, watch)
    app.after(1500, guard(next_model))
    app.mainloop()
    print("errors:", errors)
    return 1 if errors else 0


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
