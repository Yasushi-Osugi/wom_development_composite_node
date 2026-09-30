# -*- coding: utf-8 -*-
"""
RequestLetter_SimMgmt_WorldMapTrial Part 2：World Map の試作（Natural Earth ＋ matplotlib）

- 地図データ（data/worldmap_ne/*.npz）の形・投影・細かさの選択・表示範囲の切り出し
- 変換の道具（tools/build_worldmap_ne.py）が、同じ入力から同じ配列を作ること
- サンプルモデルの拠点・線・週ごとの流れ
- 画面（MapView）：表示範囲・細かさ・週の再生（blitting あり／なし）
今の World Map タブ（wom/gui/app.py WorldMapPanel）は変えていない。
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from wom.worldmap_ne import data as D
from wom.worldmap_ne.model import load_model

NEED = pytest.mark.skipif(not os.path.exists(os.path.join(D.DATA_DIR, "ne_110m.npz")),
                          reason="data/worldmap_ne not built (python -m tools.build_worldmap_ne)")


def test_projection_and_lod():
    lat = np.array([-80.0, -45.0, 0.0, 13.75, 60.0, 85.0])
    assert np.allclose(D.inv_merc_y(D.merc_y(lat)), lat)
    assert D.merc_y(0.0) == pytest.approx(0.0, abs=1e-9)
    assert D.merc_y(89.9) == pytest.approx(D.merc_y(D.LAT_MAX))
    # by degrees per pixel: the same view is coarser in a small window
    assert D.choose_lod(360, 1400) == "110m" and D.choose_lod(125, 1400) == "50m"
    assert D.choose_lod(15, 1400) == "10m" and D.choose_lod(0.8, 1400) == "10m"
    assert D.choose_lod(125, 600) == "110m" and D.choose_lod(15, 600) == "50m"


@NEED
def test_map_data_shapes_and_culling():
    m = D.NEMap().load()
    assert set(m.layers) == {"110m", "50m", "10m"}
    assert set(m.layers["110m"]) == {"coast", "border", "land"}
    assert set(m.layers["10m"]) == {"coast", "border"}              # no 10m land (uses 50m)
    for s in ("110m", "50m", "10m"):
        L = m.layers[s]["coast"]
        assert L.off[0] == 0 and L.off[-1] == len(L.xy) and len(L.parts) == len(L.off) - 1
        assert max(len(p) for p in L.parts) <= 256                   # chunked for culling
    pts = m.points()
    assert pts["110m/coast"] < pts["50m/coast"] < pts["10m/coast"]
    # culling: a Thailand box keeps only parts that touch it, and all of them
    L = m.layers["10m"]["coast"]
    box = (97.0, float(D.merc_y(5.0)), 106.0, float(D.merc_y(21.0)))
    sel = L.select(box)
    assert 0 < len(sel) < len(L.parts) / 10
    x0, y0, x1, y1 = box
    inside = [p for p in L.parts if ((p[:, 0] >= x0) & (p[:, 0] <= x1) & (p[:, 1] >= y0) & (p[:, 1] <= y1)).any()]
    ids = {id(p) for p in sel}
    assert all(id(p) in ids for p in inside)
    assert m.land("10m") and len(m.land("10m")) == len(m.land("50m"))


@NEED
def test_chunks_share_a_point_so_lines_do_not_break():
    with np.load(os.path.join(D.DATA_DIR, "ne_10m.npz")) as z:
        xy, off = z["coast_xy"], z["coast_off"]
    starts, ends = off[1:-1], off[1:-1] - 1
    shared = np.all(xy[starts] == xy[ends], axis=1)
    assert shared.sum() > 0          # continuation chunks start where the previous ended


def test_converter_is_deterministic(tmp_path):
    pytest.importorskip("shapefile")
    from tools.build_worldmap_ne import DEFAULT_SRC, main
    if not os.path.exists(os.path.join(DEFAULT_SRC, "physical", "ne_110m_coastline.shp")):
        pytest.skip("no Natural Earth source files on this PC")
    assert main(["--out", str(tmp_path)]) == 0
    for s in ("110m", "50m", "10m"):
        a = np.load(os.path.join(tmp_path, f"ne_{s}.npz"))
        b = np.load(os.path.join(D.DATA_DIR, f"ne_{s}.npz"))
        assert sorted(a.files) == sorted(b.files)
        for k in a.files:
            assert np.array_equal(a[k], b[k]), (s, k)


@pytest.mark.parametrize("model", ["ev-thailand-2026", "iphone_global", "oil-global-2027"])
def test_model_nodes_edges_and_weekly_flows(model):
    import pandas as pd
    mm = load_model(model)
    assert len(mm.node_ids) == len(mm.x) == len(mm.colours) > 5
    assert mm.edges and mm.edge_flow.shape == (len(mm.weeks), len(mm.edges))
    assert (mm.edge_flow >= 0).all() and mm.edge_flow.sum() > 0
    assert mm.edge_outbound.any() and (~mm.edge_outbound).any()      # both sides drawn
    # each market leaf on the map carries exactly its own demand
    # (iphone_global's Retail_* nodes have no lat/lon in node_master.csv, so they
    # are not on the map -- the same as in the World Map tab)
    d = os.path.join(D.REPO, "data", "sample", model)
    dem = pd.read_csv(os.path.join(d, "demand_forecast.csv"))
    st = pd.read_csv(os.path.join(d, "sc_tree_master.csv"))
    lv = st[st["node_type"] == "leaf_out"]
    checked = 0
    for _, r in lv.iterrows():
        leaf, prod, reg = str(r["node_name"]), str(r["product_name"]), str(r["region"])
        ks = [k for k, (c, _p, pr) in enumerate(mm.edges) if mm.node_ids[c] == leaf and pr == prod]
        if not ks:
            continue
        want = float(dem[(dem["sku_id"].astype(str) == prod) & (dem["region"].astype(str) == reg)]
                     ["quantity"].clip(lower=0).sum())
        assert mm.edge_flow[:, ks[0]].sum() == pytest.approx(want), leaf
        checked += 1
    assert checked > 0 or model == "iphone_global"


@NEED
def test_mapview_views_lod_and_weeks():
    tk = pytest.importorskip("tkinter")
    from wom.worldmap_ne.viewer import MapView, VIEWS, view_to_xy
    try:
        root = tk.Tk()
    except Exception as exc:
        pytest.skip(f"no Tk: {exc}")
    try:
        root.geometry("900x560+-3000+-3000")
        v = MapView(root, D.NEMap().load(["110m"]), load_model("ev-thailand-2026"), lod="auto")
        v.pack(fill="both", expand=True)
        root.update()
        r = v.set_view(*view_to_xy(VIEWS["World"]))
        assert r["lod"] == "110m" and r["draw_ms"] > 0
        x0, x1 = v.ax.get_xlim()
        assert x0 <= -179 and x1 >= 179                             # the whole world is shown
        assert v.set_view(*view_to_xy(VIEWS["Asia"]))["lod"] == "50m"
        r = v.set_view(*view_to_xy(VIEWS["Bangkok"]))
        assert r["lod"] == "10m" and v.nemap.has("10m")             # 10m loaded on demand
        v.set_view(*v.model.extent())
        assert v.set_week(3) > 0 and v.week == 3 and v._bg is not None   # blit path
        lw = np.array(v.flows.get_linewidths())
        ef = v.model.edge_flow
        other = next(w for w in range(len(ef)) if not np.array_equal(ef[w], ef[3]))
        v.set_week(other)
        assert not np.array_equal(lw, v.flows.get_linewidths())     # the flows change by week
        v.set_blit(False)
        assert v.set_week(5) > 0 and v.week == 5
        v.lod_mode = "10m"
        assert v.set_view(*view_to_xy(VIEWS["World"]))["lod"] == "10m"
    finally:
        root.destroy()
