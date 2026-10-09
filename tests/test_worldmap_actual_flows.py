# -*- coding: utf-8 -*-
"""
World Map を実出荷で動かす（RequestLetter_WorldMap_ActualFlows）

- Unit：区間 × 週の「出荷」「輸送中」の数え方（合成の出荷の記録）、日付変更線の分割
- Layout：物理の区間だけ（supply point を通らない）、Cookie_Import の北京 → DC_Import_Buffer、
  座標の無い拠点は一覧に出す
- Integration：Cookie を計画 → 出荷の記録 → 地図の数字 ＝ edge_flows（vc_edge_flows.csv と同じ関数）
- 受入 4：WOM の画面を作って World Map を使っても tkintermapview を読み込まず、ネットワークに出ない
- 受入 6：別の計画の流れは表示しない、モデルを読み込み直すと流れが消える
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import numpy as np
import pytest

from wom.valuechain.records import NodeInfo, PlanRecords, Shipment
from wom.worldmap_ne.flows import FlowData, MapLayout, records_problem

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SAMPLE = os.path.join(REPO, "data", "sample")
COOKIE = os.path.join(SAMPLE, "Cookie-jp-2026")


def _records(ships, n=6):
    nodes = {("P", "A"): NodeInfo("P", "A", "id:A", "mom", None, [], 0, 0, 1, "in", 0),
             ("P", "D"): NodeInfo("P", "D", "id:D", "dad", "SP", [], 3, 3, 1, "out", 2)}
    return PlanRecords("plan:t", [f"2027-W{w + 1:02d}" for w in range(n)], 1.0, nodes, ships)


def _ship(i, w, aw, edge="A->D", in_h=True, kind="outbound_move"):
    return Shipment(f"s{i}", "P", f"L{i}", "SP", "id:SP", w, i, kind, "A", "D", edge, aw, in_h, 1, "finished")


# ── unit ────────────────────────────────────────────────────────────
def test_ship_and_transit_counts():
    rec = _records([_ship(0, 1, 4), _ship(1, 1, 4), _ship(2, 2, 2),          # LT 0: never in transit
                    _ship(3, 4, None, in_h=False)])                         # arrives after the horizon
    F = FlowData.from_records(rec)
    k = F.edge_keys.index(("P", "A->D"))
    assert F.ship[:, k].tolist() == [0, 2, 1, 0, 1, 0]
    # in transit at the end of week w: ship_week <= w < arrival_week
    assert F.transit[:, k].tolist() == [0, 2, 2, 2, 1, 1]
    assert F.lt_master[("P", "A->D")] == 3            # the receiving DAD's LT
    assert F.lt_observed[("P", "A->D")] == pytest.approx(3.0)   # median of 3, 3, 0
    t = F.edge_week_table()
    assert sorted(zip(t["ship_week_index"], t["lots"])) == [(1, 2), (2, 1), (4, 1)]


def test_handoff_and_sales_are_not_edges():
    rec = _records([_ship(0, 1, 1, edge="", kind="handoff_to_sp"),
                    Shipment("c", "P", "L9", "D", "id:D", 3, 0, "consumer_sale", "D", "CONSUMER:D", "", None,
                             False, 1, "finished")])
    F = FlowData.from_records(rec)
    assert F.edge_keys == [] and F.ship.shape[1] == 0
    assert int(F.handoff.sum()) == 1
    assert int(F.sales[3, F.node_keys.index(("P", "D"))]) == 1


def test_records_with_issues_are_not_drawn():
    rec = _records([_ship(0, 1, 2)])
    rec.issues.append({"issue": "receiver_not_found"})
    assert "receiver_not_found" in records_problem(rec)
    assert records_problem(_records([])) is not None
    assert records_problem(_records([_ship(0, 1, 2)])) is None


def test_dateline_split():
    from wom.gui.worldmap_panel import _split_dateline
    assert len(_split_dateline(100, 0, 120, 0)) == 1
    parts = _split_dateline(139.0, 10.0, -122.0, 10.0)          # Tokyo -> San Francisco
    assert len(parts) == 2
    assert parts[0][1][0] == 180.0 and parts[1][0][0] == -180.0


# ── layout ──────────────────────────────────────────────────────────
def test_cookie_layout_physical_edges_only():
    L = MapLayout.load(COOKIE)
    edges = {(e.product, e.edge) for e in L.edges}
    assert ("Cookie_Import", "Factory_GP_CN->DC_Import_Buffer") in edges     # Beijing -> Japan, direct
    assert ("Cookie_Local", "Factory_DP_JP->DC_Local_JP") in edges
    assert not any("SP_" in e.a or "SP_" in e.b for e in L.edges)          # no line through the SP
    assert {e.edge for e in L.handoff} == {"Factory_GP_CN->SP_Cookie_Import", "Factory_DP_JP->SP_Cookie_Local"}
    assert L.missing_coords == [] and L.undrawable_edges == []
    assert L.nodes["SP_Cookie_Import"].is_supply_point


def test_missing_coordinates_are_listed_not_guessed(tmp_path):
    import shutil
    d = tmp_path / "cookie"
    shutil.copytree(COOKIE, d)
    p = d / "node_master.csv"
    txt = p.read_text(encoding="utf-8").splitlines()
    i = next(k for k, ln in enumerate(txt) if ln.startswith("DC_Import_Buffer,"))
    f = txt[i].split(",")
    f[3] = f[4] = ""                                           # no lat / lon
    txt[i] = ",".join(f)
    p.write_text("\n".join(txt) + "\n", encoding="utf-8")
    L = MapLayout.load(str(d))
    assert [m["node_id"] for m in L.missing_coords] == ["DC_Import_Buffer"]     # a DC: never guessed
    assert "DC_Import_Buffer" not in L.nodes
    assert {u["edge"] for u in L.undrawable_edges} == {"Factory_GP_CN->DC_Import_Buffer",
                                                        "DC_Import_Buffer->DC_Import_Main"}


def test_stock_yard_is_drawn_at_its_plant():
    """Owner's decision (2026-10): a Yard without coordinates sits at its parent plant, listed."""
    L = MapLayout.load(os.path.join(SAMPLE, "bom-test-2026"))
    assert L.missing_coords == [] and L.undrawable_edges == []
    placed = {x["node_id"]: x["parent"] for x in L.placed_at_parent}
    assert placed == {"Battery_Yard": "Vehicle_Assy", "Tire_Yard": "Vehicle_Assy"}
    y, plant = L.nodes["Battery_Yard"], L.nodes["Vehicle_Assy"]
    assert (y.lat, y.lon) == (plant.lat, plant.lon)
    assert y.info["placed_at_parent"] == "Vehicle_Assy"
    edges = {e.edge for e in L.edges}
    assert {"Battery_Supply->Battery_Yard", "Battery_Yard->Vehicle_Assy"} <= edges
    E = MapLayout.load(os.path.join(SAMPLE, "ev-europe-2026"))
    assert len(E.placed_at_parent) == 6 and E.missing_coords == []


def test_rice_and_smartphone_all_nodes_on_the_map():
    R = MapLayout.load(os.path.join(SAMPLE, "rice-japan-2027-2028"))
    assert R.missing_coords == [] and R.undrawable_edges == []
    assert set().union(*R.tree_nodes.values()) <= set(R.nodes)
    I = MapLayout.load(os.path.join(SAMPLE, "smartphone-global-2026-2029"))
    assert I.missing_coords == [] and I.undrawable_edges == []
    for base in ("DC_AMER", "DC_EMEA", "DC_APAC", "EMS_A_CN"):
        for suf in ("_i15", "_i17"):
            assert (I.nodes[base + suf].lat, I.nodes[base + suf].lon) == (I.nodes[base].lat, I.nodes[base].lon)


# ── integration: Cookie plan -> records -> the map's numbers ────────
@pytest.fixture(scope="module")
def cookie_plan():
    from wom.valuechain.run import plan_model
    from wom.valuechain.records import build_records
    sc, _snap, _pl, _mode = plan_model(COOKIE, tempfile.mkdtemp(prefix="wm_t_"))
    return sc, build_records(sc, "plan:cookie")


def test_cookie_map_numbers_equal_edge_flows(cookie_plan):
    from wom.valuechain.records import edge_flows
    sc, rec = cookie_plan
    assert records_problem(rec) is None
    F = FlowData.from_records(rec, sc)
    ef = edge_flows(rec.shipments, rec.week_labels).groupby(
        ["product", "edge", "ship_week_index"], as_index=False)["lots"].sum()
    mt = F.edge_week_table()
    m = ef.merge(mt, on=["product", "edge", "ship_week_index"], how="outer", suffixes=("_vc", "_map"))
    assert len(ef) == len(mt) and (m["lots_vc"] == m["lots_map"]).all()
    L = MapLayout.load(COOKIE)
    assert {(e.product, e.edge) for e in L.edges} == set(F.edge_keys)    # static lines == actual edges
    # node PSI comes from the plan's supply buckets
    k = F.node_keys.index(("Cookie_Import", "DC_Import_Buffer"))
    nd = next(n for n in sc.iter_all_nodes("Cookie_Import") if n.node_name == "DC_Import_Buffer")
    w = 40
    assert int(F.psi[w, k, 2]) == len(nd.psi4supply[w][2])


# ── acceptance 4: no tkintermapview, no network ─────────────────────
_NO_NET = r"""
import os, socket, sys
calls = []
def deny(*a, **k):
    calls.append(a[:1]); raise OSError("network blocked by the test")
socket.socket.connect = deny
socket.create_connection = deny
socket.getaddrinfo = deny
try:
    import urllib.request
    urllib.request.urlopen = deny
except Exception:
    pass
sys.path.insert(0, sys.argv[1])
import wom.gui.app as A
app = A.WOMApp()
app.geometry("1200x800+0+0")
wm = app._worldmap_panel
wm.load_default(os.path.join(sys.argv[2], "node_master.csv"), os.path.join(sys.argv[2], "sc_tree_master.csv"))
app.update()
wm.go("World"); wm.go("Nodes")
from wom.worldmap_ne.data import merc_y
wm.set_view(139.5, float(merc_y(35.4)), 139.9, float(merc_y(35.8)))   # zoomed in: the 10m data
app.update()
print("LOD", wm._lod)
print("TKMV", "tkintermapview" in sys.modules)
print("NET", len(calls))
app.destroy()
"""


def test_no_tkintermapview_and_no_network(tmp_path):
    script = tmp_path / "no_net.py"
    script.write_text(_NO_NET, encoding="utf-8")
    r = subprocess.run([sys.executable, str(script), REPO, COOKIE], capture_output=True, text=True,
                       timeout=300, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-2000:]
    out = r.stdout
    assert "TKMV False" in out and "NET 0" in out and "LOD 10m" in out, out[-1500:]


def test_app_source_has_no_tile_map():
    src = open(os.path.join(REPO, "wom", "gui", "app.py"), encoding="utf-8").read()
    panel = open(os.path.join(REPO, "wom", "gui", "worldmap_panel.py"), encoding="utf-8").read()
    for s in (src, panel):
        assert "import tkintermapview" not in s and "from tkintermapview" not in s
        assert "set_tile_server" not in s and "cartocdn" not in s


# ── acceptance 6: never the flows of another plan ───────────────────
def test_panel_ignores_other_plans_and_clears_on_reload(cookie_plan):
    import tkinter as tk
    from wom.gui.worldmap_panel import WorldMapPanel
    sc, rec = cookie_plan
    F = FlowData.from_records(rec, sc)          # plan id "plan:cookie"
    root = tk.Tk()
    try:
        p = WorldMapPanel(root)
        p.pack(fill="both", expand=True)
        root.geometry("1000x700")
        p.load_default(os.path.join(COOKIE, "node_master.csv"))
        root.update()
        p.begin_flows("plan:other")
        assert p.set_flows("plan:cookie", F) is False and p.flows is None    # an older plan's result
        p.begin_flows("plan:cookie")
        assert str(p._btn_play["state"]) == "disabled"                       # records still building
        assert p.set_flows("plan:cookie", F) is True and p.flows is F
        assert str(p._btn_play["state"]) == "normal"
        p.set_week(50)
        assert p._week == 50
        p.clear_timeline()                                                   # model (re)loaded
        assert p.flows is None and p._current_run_id == ""
        assert str(p._btn_play["state"]) == "disabled"
        p.begin_flows("plan:new")
        assert p.set_flows("plan:new", None, "出荷の記録に食い違い") is False
        assert "流れを出しません" in p._band_var.get()
    finally:
        root.destroy()
