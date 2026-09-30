# -*- coding: utf-8 -*-
"""
World Map 試作の計測（RequestLetter_SimMgmt_WorldMapTrial 2.3）

    python -m wom.worldmap_ne.bench [--out docs/development/sim_mgmt_worldmap] [--models ...]

測るもの（ms は、matplotlib の描画＋Tk の画面への反映まで。`canvas.draw()`＋`update_idletasks()`）：

  1  起動から地図が出るまで（110m・50m・10m・auto、モデルごと）：別のプロセスで冷えた状態から。
     Python の起動 → import → 地図データの読み込み → 窓を作って全体表示を 1 回描く、までの時間。
  2  全体表示の描画（細かさごと）：同じ表示を 5 回描いた中央値。
  3  ズーム・移動（1 回あたり、auto）：世界全体・アジア全体・国（タイ）・都市（バンコクの周り）。
     その範囲へ移る 1 回（ズーム）と、幅の 10 % ずつの移動 6 回・1.5 倍のズーム 4 回の中央値。
     比較として、細かさを 10m に固定したときの世界全体・アジア全体も測る。
  4  週の再生（1 週あたり）：blitting あり・なし。拠点の範囲と世界全体で、各 40 週の中央値と 95 %。
  5  メモリ（プロセスの RSS）：import の後（地図データの前）、3 段階を読み込んだ後、操作の後。
  6  案 B の確認：tkintermapview を use_database_only=True・max_zoom=4 で、手元の
     data/worldmap_cache.db だけから表示する。ネットワークに出ようとした回数を数える
     （requests.get を差し替えて記録。実際には出さない）。表示に要る画像の数と、手元に
     無かった数を、ズーム 1〜4 で数える。

出力：<out>/bench.json、<out>/screens/*.png（窓の画像）
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time

T_START = time.perf_counter()

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODELS = ["ev-thailand-2026", "iphone_global", "oil-global-2027"]
WINDOW = "1400x860+20+20"


def _rss_mb():
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1e6, 1)
    except Exception:
        return None


def _proc_age_s():
    """seconds since this Python process was created (includes interpreter start)."""
    try:
        import psutil
        return time.time() - psutil.Process().create_time()
    except Exception:
        return None


def screen_info() -> dict:
    import ctypes
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    hdc = u.GetDC(0)
    phys = (g.GetDeviceCaps(hdc, 118), g.GetDeviceCaps(hdc, 117))        # DESKTOPHORZRES / VERTRES
    logical = (u.GetSystemMetrics(0), u.GetSystemMetrics(1))
    u.ReleaseDC(0, hdc)
    return {"physical_px": phys, "logical_px_seen_by_wom": logical,
            "scaling_percent": round(100.0 * phys[0] / logical[0]) if logical[0] else None,
            "dpi_awareness": "unaware (same as python -m main)", "window": WINDOW}


def _stats(xs):
    xs = sorted(xs)
    if not xs:
        return {}
    p95 = xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]
    return {"median_ms": round(statistics.median(xs), 1), "p95_ms": round(p95, 1),
            "min_ms": round(xs[0], 1), "max_ms": round(xs[-1], 1), "n": len(xs)}


# ── 1+2: cold start in a fresh process ──────────────────────────────────

def startup_child(model: str, lod: str, out: str) -> None:
    t_py = _proc_age_s()
    rss0 = _rss_mb()
    import tkinter as tk
    from wom.worldmap_ne.data import NEMap, SCALES
    from wom.worldmap_ne.model import load_model
    from wom.worldmap_ne.viewer import MapView, VIEWS, view_to_xy
    t_import = time.perf_counter() - T_START
    rss_import = _rss_mb()
    t0 = time.perf_counter()
    nemap = NEMap().load(list(SCALES) if lod == "auto" else [lod])
    t_data = time.perf_counter() - t0
    t0 = time.perf_counter()
    mm = load_model(model)
    t_model = time.perf_counter() - t0
    res = {}
    root = tk.Tk()
    root.geometry(WINDOW)

    def go():
        t1 = time.perf_counter()
        v = MapView(root, nemap, mm, lod=lod, blit=True)
        v.pack(fill="both", expand=True)
        root.update()
        r = v.set_view(*view_to_xy(VIEWS["World"]))
        root.update()
        t_first = time.perf_counter() - t1
        t_shown = time.perf_counter() - T_START        # the map is on the screen here
        draws = [v.set_view(*view_to_xy(VIEWS["World"]))["draw_ms"] for _ in range(5)]
        res.update({
            "model": model, "lod": lod,
            "python_start_to_script_s": round(t_py, 3) if t_py is not None else None,
            "import_s": round(t_import, 3), "data_load_s": round(t_data, 3),
            "model_load_s": round(t_model, 3), "window_and_first_draw_s": round(t_first, 3),
            "to_map_shown_s": round(t_shown, 3),
            "to_map_shown_incl_python_s": round(t_shown + (t_py or 0), 3),
            "first_view": {k: (round(x, 1) if isinstance(x, float) else x) for k, x in r.items()},
            "world_draw": _stats(draws), "world_lod": r["lod"],
            "rss_mb": {"process_start": rss0, "after_import": rss_import, "after_first_draw": _rss_mb()},
            "points_loaded": nemap.points(),
        })
        root.destroy()

    root.after(10, go)
    root.mainloop()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)


def run_startups(models, tmp_dir) -> list:
    out = []
    for model in models:
        for lod in ("110m", "50m", "10m", "auto"):
            p = os.path.join(tmp_dir, f"startup_{model}_{lod}.json")
            t0 = time.perf_counter()
            subprocess.run([sys.executable, "-m", "wom.worldmap_ne.bench", "--startup-child",
                            model, lod, p], cwd=REPO, check=True)
            wall = time.perf_counter() - t0
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            d["wall_incl_process_start_and_exit_s"] = round(wall, 3)
            out.append(d)
            print(f"startup {model:<18} {lod:<5} shown {d['to_map_shown_incl_python_s']:.2f}s "
                  f"(data {d['data_load_s']:.3f}s) world draw {d['world_draw']['median_ms']} ms", flush=True)
    return out


# ── 3+4+5: interactive, in this process ─────────────────────────────────

def run_interactive(models, shots_dir) -> dict:
    import tkinter as tk
    from wom.worldmap_ne.data import NEMap, SCALES
    from wom.worldmap_ne.model import load_model
    from wom.worldmap_ne.viewer import MapView, VIEWS, view_to_xy
    from wom.lovem.viewer import _print_window
    os.makedirs(shots_dir, exist_ok=True)
    mem = {"after_import": _rss_mb()}
    t0 = time.perf_counter()
    nemap = NEMap().load(SCALES)
    mem["after_loading_110m_50m_10m"] = _rss_mb()
    load_s = time.perf_counter() - t0
    root = tk.Tk()
    root.geometry(WINDOW)
    v = MapView(root, nemap, None, lod="auto", blit=True)
    v.pack(fill="both", expand=True)
    res = {"data_load_all_s": round(load_s, 3), "models": {}}

    def shot(name):
        root.update()
        _print_window(int(root.wm_frame(), 16)).save(os.path.join(shots_dir, name + ".png"))

    def bench_model(model):
        mm = load_model(model)
        v.lod_mode = "auto"
        v.set_blit(True)
        v.set_model(mm, draw=False)
        root.update()
        r = {"nodes": len(mm.node_ids), "edges": len(mm.edges), "weeks": len(mm.weeks), "views": {}}
        order = ["World", "Asia", "Thailand", "Bangkok"]
        v.set_view(*view_to_xy(VIEWS["World"]))
        for name in order:
            box = view_to_xy(VIEWS[name])
            z = v.set_view(*box)                        # the zoom into this view
            root.update()
            shot(f"{model}__{name}")
            x0, x1 = v.ax.get_xlim()
            y0, y1 = v.ax.get_ylim()
            w = x1 - x0
            pans, zooms, lods = [], [], set()
            for k in range(6):                          # pan by 10 % of the width
                d = 0.1 * w * (1 if k % 2 == 0 else -1)
                x0, x1 = x0 + d, x1 + d
                t = v.set_view(x0, y0, x1, y1)
                pans.append(t["cull_ms"] + t["draw_ms"])
                lods.add(t["lod"])
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            for k in range(4):                          # zoom x1.5 in, out, in, out
                f = 1 / 1.5 if k % 2 == 0 else 1.5
                hw, hh = (x1 - x0) / 2 * f, (y1 - y0) / 2 * f
                x0, x1, y0, y1 = cx - hw, cx + hw, cy - hh, cy + hh
                t = v.set_view(x0, y0, x1, y1)
                zooms.append(t["cull_ms"] + t["draw_ms"])
                lods.add(t["lod"])
            v.set_view(*box)
            r["views"][name] = {
                "lod": z["lod"], "parts_drawn": z["segments"],
                "zoom_into_view_ms": round(z["cull_ms"] + z["draw_ms"], 1),
                "pan": _stats(pans), "zoom_x1_5": _stats(zooms), "lods_used": sorted(lods)}
        # fixed 10m (no LOD switching) for comparison
        v.lod_mode = "10m"
        fixed = {}
        for name in ("World", "Asia"):
            ts = [v.set_view(*view_to_xy(VIEWS[name])) for _ in range(3)]
            fixed[name] = {"parts_drawn": ts[-1]["segments"],
                           "draw": _stats([t["cull_ms"] + t["draw_ms"] for t in ts])}
        r["fixed_10m"] = fixed
        v.lod_mode = "auto"
        # weekly playback
        play = {}
        for vname, box in (("nodes", mm.extent()), ("World", view_to_xy(VIEWS["World"]))):
            for blit in (True, False):
                v.set_blit(blit)
                v.set_view(*box)
                root.update()
                n = min(40, len(mm.weeks))
                ts = [v.set_week(w) for w in range(n)]
                play[f"{vname}__{'blit' if blit else 'no_blit'}"] = _stats(ts)
            v.set_blit(True)
        v.set_view(*mm.extent())
        v.set_week(len(mm.weeks) // 2)
        shot(f"{model}__nodes_week")
        r["weekly_playback"] = play
        return r

    def go():
        try:
            for m in models:
                res["models"][m] = bench_model(m)
                print(f"interactive {m} done", flush=True)
            mem["after_all_operations"] = _rss_mb()
        finally:
            root.destroy()

    root.after(200, go)
    root.mainloop()
    res["rss_mb"] = mem
    return res


# ── 6: Plan B probe (tkintermapview, local tiles only) ─────────────────

def run_planb(shots_dir) -> dict:
    import sqlite3
    import tkinter as tk
    import requests
    import tkintermapview
    from tkintermapview import TkinterMapView
    from wom.lovem.viewer import _print_window
    db = os.path.join(REPO, "data", "worldmap_cache.db")
    url = "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
    calls = []
    real_get = requests.get

    def trap(*a, **k):                                  # never let it go out
        calls.append(a[0] if a else k.get("url"))
        raise requests.exceptions.ConnectionError("blocked by bench (plan B probe)")

    requests.get = trap
    have = {}
    con = sqlite3.connect(db)
    for z, x, y in con.execute("SELECT zoom, x, y FROM tiles WHERE server=?", (url,)):
        have.setdefault(z, set()).add((x, y))
    con.close()
    coverage = {z: {"tiles_in_db": len(have.get(z, ())), "tiles_of_whole_world": 4 ** z}
                for z in range(1, 7)}
    res = {"tkintermapview_version": getattr(tkintermapview, "__version__", None),
           "db_bytes": os.path.getsize(db), "coverage_by_zoom": coverage}
    root = tk.Tk()
    root.geometry(WINDOW)
    t0 = time.perf_counter()
    mw = TkinterMapView(root, width=1400, height=820, corner_radius=0, database_path=db,
                        use_database_only=True, max_zoom=4)
    mw.pack(fill="both", expand=True)
    mw.set_tile_server(url, max_zoom=4)

    def settle(limit=10.0):
        t = time.perf_counter()
        idle_since = None
        while time.perf_counter() - t < limit:
            root.update()
            busy = mw.image_load_queue_tasks or mw.image_load_queue_results
            if busy:
                idle_since = None
            elif idle_since is None:
                idle_since = time.perf_counter()
            elif time.perf_counter() - idle_since > 0.15:
                break
            time.sleep(0.005)
        return (time.perf_counter() - t) * 1000.0

    views = {"World": (20.0, 10.0, 2), "Asia": (22.0, 105.0, 3), "Thailand": (13.5, 101.0, 4),
             "Bangkok": (13.75, 100.5, 6)}
    out = {}

    def go():
        try:
            mw.set_position(20.0, 10.0)
            mw.set_zoom(2)
            res["startup_to_tiles_shown_s"] = round(time.perf_counter() - t0 + settle() / 1000.0, 3)
            for name, (lat, lon, z) in views.items():
                t = time.perf_counter()
                mw.set_position(lat, lon)
                mw.set_zoom(z)
                ms = (time.perf_counter() - t) * 1000.0 + settle()
                zoom_now = round(mw.zoom)
                need = set()
                for row in mw.canvas_tile_array:
                    for tile in row:
                        tx, ty = tile.tile_name_position
                        if 0 <= tx < 2 ** zoom_now and 0 <= ty < 2 ** zoom_now:
                            need.add((tx, ty))
                missing = len([p for p in need if p not in have.get(zoom_now, set())])
                root.update()
                _print_window(int(root.wm_frame(), 16)).save(os.path.join(shots_dir, f"planB__{name}.png"))
                out[name] = {"requested_zoom": z, "zoom_used": zoom_now, "tiles_needed": len(need),
                             "tiles_missing_in_db": missing, "zoom_and_settle_ms": round(ms, 1)}
        finally:
            mw.running = False
            root.after(300, root.destroy)

    root.after(300, go)
    root.mainloop()
    requests.get = real_get
    res["views"] = out
    res["network_attempts"] = len(calls)
    res["network_attempt_urls_sample"] = calls[:5]
    res["zoom_is_capped_at_4"] = all(v["zoom_used"] <= 4 for v in out.values())
    return res


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "--startup-child":
        startup_child(argv[1], argv[2], argv[3])
        return 0
    ap = argparse.ArgumentParser(description="World Map trial benchmark")
    ap.add_argument("--out", default=os.path.join("docs", "development", "sim_mgmt_worldmap"))
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--skip", default="", help="comma list of: startup,interactive,planb")
    a = ap.parse_args(argv)
    os.chdir(REPO)
    os.makedirs(a.out, exist_ok=True)
    shots = os.path.join(a.out, "screens")
    os.makedirs(shots, exist_ok=True)
    models = a.models.split(",")
    skip = set(filter(None, a.skip.split(",")))
    import tempfile
    tmp = tempfile.mkdtemp(prefix="wom_wm_bench_")
    res = {"screen": screen_info(), "python": sys.version.split()[0]}
    try:
        import matplotlib, numpy
        res["matplotlib"], res["numpy"] = matplotlib.__version__, numpy.__version__
    except Exception:
        pass
    data_dir = os.path.join(REPO, "data", "worldmap_ne")
    res["data_files_bytes"] = {f: os.path.getsize(os.path.join(data_dir, f))
                               for f in sorted(os.listdir(data_dir)) if f.endswith(".npz")}
    if "startup" not in skip:
        res["startup"] = run_startups(models, tmp)
    if "interactive" not in skip:
        res["interactive"] = run_interactive(models, shots)
    if "planb" not in skip:
        res["plan_b"] = run_planb(shots)
    p = os.path.join(a.out, "bench.json")
    if skip and os.path.exists(p):          # a partial run updates the parts it ran
        with open(p, encoding="utf-8") as f:
            old = json.load(f)
        old.update(res)
        res = old
    with open(p, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("->", p)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
