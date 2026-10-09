# -*- coding: utf-8 -*-
"""
tools/ppc_kpi_summary_check.py — PPC タブの「PPC KPI Summary」の文字の重なりを確かめる
（RequestLetter_SimMgmt_WorldMapTrial 1.2 の受入）

    python -m tools.ppc_kpi_summary_check --out output/sim_mgmt/ppc_kpi

モデルごとに headless（`tools/run_headless_from_folder.run`、golden と同じ plugins）で PPC の
出力を `<out>/ppc/<model>` に作り、`PPCCockpitApp`（PPC タブの中身と同じ Frame）を窓に置いて、
いくつかの窓の大きさ・SKU の選択で描く。Panel 1 の文字の箱（描いた後の実際の範囲）を
取り出し、2 つずつ重なりを数える。窓の画像は PrintWindow で取る。

比較のため、`--before` を付けると、HEAD の版の `_draw_kpi_text`（直す前）でも同じことを行う。

出力：<out>/kpi_summary_check.json と <out>/*.png
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import traceback

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

MODELS = ["ev-thailand-2026", "smartphone-global-2026-2029", "apparel-global-2028-2029", "oil-global-2027"]
# the owner's screen: 1920x1080 at 125 % -> 1536x864 logical (python -m main is DPI-unaware)
SIZES = [(1536, 824), (1280, 720), (1100, 640)]


def _plugins(model: str) -> str:
    p = os.path.join(REPO, "tests", "golden", model + ".json")
    if not os.path.exists(p):
        return "none"
    with open(p, encoding="utf-8") as f:
        return ",".join(json.load(f).get("config", {}).get("plugins", [])) or "none"


def _old_draw_kpi_text():
    """_draw_kpi_text of the committed version (HEAD), for the before/after pictures."""
    src = subprocess.run(["git", "show", "HEAD:wom/ppc/ppc_cockpit_app.py"], cwd=REPO,
                         capture_output=True, check=True).stdout.decode("utf-8")
    tmp = os.path.join(tempfile.mkdtemp(prefix="wom_ppc_old_"), "ppc_cockpit_app_head.py")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    spec = importlib.util.spec_from_file_location("ppc_cockpit_app_head", tmp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._draw_kpi_text


def text_boxes(ax, renderer):
    out = []
    for t in ax.texts:
        if not t.get_text().strip():
            continue
        bb = t.get_window_extent(renderer)
        patch = t.get_bbox_patch()
        if patch is not None:
            bb = patch.get_window_extent(renderer)
        out.append((t.get_text(), bb))
    return out


def overlaps(boxes, ax_bbox):
    """Pairs of text boxes that overlap (more than 0.5 px), and boxes that stick
    out of the panel (below its bottom edge)."""
    pairs = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i][1], boxes[j][1]
            ix = min(a.x1, b.x1) - max(a.x0, b.x0)
            iy = min(a.y1, b.y1) - max(a.y0, b.y0)
            if ix > 0.5 and iy > 0.5:
                pairs.append([boxes[i][0], boxes[j][0], round(iy, 1)])
    outside = [t for t, bb in boxes if bb.y0 < ax_bbox.y0 - 0.5]
    return pairs, outside


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join("output", "sim_mgmt", "ppc_kpi"))
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--before", action="store_true", help="also draw with HEAD's _draw_kpi_text")
    ap.add_argument("--reuse", action="store_true",
                    help="reuse <out>/ppc/<model> from a previous run (skip the headless PPC)")
    a = ap.parse_args(argv)
    os.chdir(REPO)
    os.makedirs(a.out, exist_ok=True)
    # DPI-unaware, like `python -m main` (the window is what the owner sees).
    import tkinter as tk
    from tools.run_headless_from_folder import run
    import wom.ppc.ppc_cockpit_app as C
    from wom.lovem.viewer import _print_window

    new_fn = C._draw_kpi_text
    variants = [("after", new_fn)] + ([("before", _old_draw_kpi_text())] if a.before else [])
    result, errors = {"sizes": SIZES, "models": {}}, []
    for model in a.models.split(","):
        out_dir = os.path.join(a.out, "ppc", model)
        try:
            if not (a.reuse and os.path.exists(os.path.join(out_dir, "ppc_kpi_summary.json"))):
                run(os.path.join("data", "sample", model), plugins_spec=_plugins(model),
                    output_ppc_dir=out_dir, verbose=False)
        except Exception:
            errors.append(f"{model}: headless " + traceback.format_exc()[-1500:])
            continue
        mres = result["models"][model] = {}
        root = tk.Tk()
        try:
            app = C.PPCCockpitApp(root, output_dir=out_dir)
            app.pack(fill="both", expand=True)
            # SKU views: All + the SKU with the most channels
            rec = app._rec
            by_sku = rec.groupby("product_id")["channel_node"].nunique().sort_values(ascending=False)
            skus = ["All"] + ([by_sku.index[0]] if len(by_sku) else [])
            if model == "ev-thailand-2026" and "EVmaker_Import" in app._skus:
                skus = ["All", "EVmaker_Import"]
            mres["channels_per_sku"] = {str(k): int(v) for k, v in by_sku.items()}
            mres["channels_all"] = int(rec["channel_node"].nunique())
            for variant, fn in variants:
                C._draw_kpi_text = fn
                for (w, h) in SIZES:
                    root.geometry(f"{w}x{h}+10+10")
                    for sku in skus:
                        app._sku_var.set(sku)
                        root.update(); root.update_idletasks()
                        app._redraw()
                        root.update(); root.update_idletasks()
                        fig = app._fig
                        renderer = fig.canvas.get_renderer()
                        ax1 = fig.axes[0]
                        boxes = text_boxes(ax1, renderer)
                        pairs, outside = overlaps(boxes, ax1.bbox)
                        lay = getattr(ax1, "_wom_kpi_layout", None) or {}
                        key = f"{variant}__{w}x{h}__{sku}"
                        mres[key] = {
                            "panel_px": [round(ax1.bbox.width), round(ax1.bbox.height)],
                            "n_text": len(boxes), "overlapping_pairs": pairs,
                            "below_panel": outside,
                            "font_scale": lay.get("scale"), "columns": lay.get("columns"), "mode": lay.get("mode"),
                            "shown_channels": lay.get("shown_channels"),
                            "hidden_channels": lay.get("hidden_channels"),
                        }
                        name = f"{model}__{key}.png".replace("/", "_")
                        _print_window(int(root.wm_frame(), 16)).save(os.path.join(a.out, name))
                        print(f"{model} {key}: overlaps={len(pairs)} below={len(outside)} "
                              f"scale={lay.get('scale')} mode={lay.get('mode')} ch={lay.get('shown_channels')}+{lay.get('hidden_channels')}",
                              flush=True)
        except Exception:
            errors.append(f"{model}: " + traceback.format_exc()[-2500:])
        finally:
            C._draw_kpi_text = new_fn
            root.destroy()
    result["errors"] = errors
    with open(os.path.join(a.out, "kpi_summary_check.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print("errors:", errors)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
