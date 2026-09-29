# -*- coding: utf-8 -*-
"""
tests/test_lovem_viewer.py — LOVEM stage B (request B4-1 / B4-2 / B4-3).

Uses a small model (bom-test-2026, which has Stockyard / Kitting nodes) so the
test stays fast; the same code draws ev-thailand-2026 (see the report).

  * every saved interval / drawable event / relation becomes exactly one
    segment, and every saved Lot_ID is drawn (counts match the run folder)
  * the full view draws every segment; the header says "全件描画 完了"
  * selecting a Lot_ID highlights all its segments on all nodes, evidence of
    that lot can be opened and the "back to figure" position is its node/week
  * closed weeks are taken from capacity.csv
  * the viewer never writes into the run folder
"""
import csv
import hashlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL = os.path.join(REPO, "data", "sample", "bom-test-2026")


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    import json
    from wom.lovem.observer import observe_run
    out = str(tmp_path_factory.mktemp("lovem_b") / "run")
    with open(os.path.join(REPO, "tests", "golden", "bom-test-2026.json"), encoding="utf-8") as f:
        plugins = ",".join(json.load(f)["config"]["plugins"]) or "none"
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        observe_run(MODEL, out, plugins=plugins, label="viewer-test")
    finally:
        os.chdir(cwd)
    return out


def _folder_hash(d):
    h = hashlib.sha256()
    for root, _dirs, files in os.walk(d):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            h.update(p.encode()); h.update(open(p, "rb").read())
    return h.hexdigest()


def test_every_saved_record_becomes_one_segment(run_dir):
    from wom.lovem.io import iter_jsonl, load_manifest, run_file
    from wom.lovem.viewdata import load_view_data
    vd = load_view_data(run_dir)
    man = load_manifest(run_dir)
    n_final = sum(s["n_intervals"] for s in man["snapshots"] if s["phase"] == "final")
    iv_cats = ("D_S", "D_P", "D_I", "D_CO", "P_rcv", "P_unk", "P_src", "I", "S_PLN", "CO")
    assert sum(len(vd.cats[k]) for k in iv_cats) == n_final
    n_ship = sum(1 for e in iter_jsonl(run_file(run_dir, "events.jsonl"))
                 if e["event_type"] == "actual_ship")
    assert len(vd.cats["SHIP"]) == n_ship
    n_rel = sum(1 for _ in iter_jsonl(run_file(run_dir, "relations.jsonl")))
    assert len(vd.cats["REL"]) == n_rel
    assert vd.saved_counts.get("relation_unresolved", 0) == 0
    # every saved Lot_ID (final intervals + events) is drawn at least once
    saved_ids = set()
    for s in man["snapshots"]:
        if s["phase"] == "final":
            saved_ids |= {r["lot_id"] for r in iter_jsonl(os.path.join(run_dir, s["intervals_file"]))}
    drawn = {vd.lots[i] for i in vd.unique_lots_in()}
    assert saved_ids <= drawn
    # P receipts are split exactly into recorded / unconfirmed / leaf_in source
    n_p = sum(1 for s in man["snapshots"] if s["phase"] == "final"
              for r in iter_jsonl(os.path.join(run_dir, s["intervals_file"]))
              if r["layer"] == "supply" and r["bucket"] == "P")
    assert len(vd.cats["P_rcv"]) + len(vd.cats["P_unk"]) + len(vd.cats["P_src"]) == n_p


def test_selection_history_and_closed_weeks(run_dir):
    from wom.lovem.viewdata import evidence_for_lot, load_view_data, lot_history
    vd = load_view_data(run_dir)
    lot = vd.lots[int(vd.cats["SHIP"].lot[0])]
    hist = lot_history(vd, lot)
    assert hist and any(r["cat"] == "SHIP" for recs in hist.values() for r in recs)
    ev = evidence_for_lot(vd, lot)
    assert ev and all(e["evidence_ref"] for e in ev if e["event_type"] == "actual_ship")
    with open(os.path.join(run_dir, "capacity.csv"), encoding="utf-8") as f:
        closed = sum(1 for r in csv.DictReader(f) if r["is_open"] == "0")
    assert len(vd.closed) == closed


def test_pick_returns_candidates_not_a_silent_choice(run_dir):
    from wom.lovem.viewdata import load_view_data, pick
    vd = load_view_data(run_dir)
    c = vd.cats["S_PLN"]
    x = float((c.x0[0] + c.x1[0]) / 2)
    y = float(c.y0[0])
    hits = pick(vd, x, y, tol_x=0.5, tol_y=0.5)
    assert any(h["lot"] == vd.lots[int(c.lot[0])] and h["cat"] == "S_PLN" for h in hits)
    assert hits == sorted(hits, key=lambda h: h["d2"])
    wide = pick(vd, x, y, tol_x=3.0, tol_y=3.0)
    assert len({h["lot"] for h in wide}) >= len({h["lot"] for h in hits})


def test_tk_viewer_draws_everything_and_selects(run_dir):
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk(); root.destroy()
    except tk.TclError:
        pytest.skip("no display")
    before = _folder_hash(run_dir)
    from wom.lovem.viewer import LovemViewer
    app = LovemViewer(run_dir)
    import time
    t0 = time.time()
    while app.vd is None and time.time() - t0 < 120:
        app.update()
        time.sleep(0.05)
    assert app.vd is not None, "viewer did not finish loading"
    app.update()
    vd = app.vd
    assert sum(int(m.sum()) for m in app.masks.values()) == vd.total_segments()
    assert "全件描画 完了" in app.counts.get()
    assert f"総 ID {len(vd.lots):,}" in app.counts.get()
    lot = vd.lots[int(vd.cats["SHIP"].lot[0])]
    app.select_lot(lot)
    n_expected = sum(int((c.lot == vd.lot_index[lot]).sum()) for c in vd.cats.values())
    assert len(app.hi_coll.get_segments()) == n_expected
    assert lot in app.detail.get("1.0", "end")
    from wom.lovem.viewdata import evidence_for_lot
    ev = next(e for e in evidence_for_lot(vd, lot) if e["event_type"] == "actual_ship")
    app.show_evidence(ev)
    assert ev["evidence_ref"] in app.ev_text.get("1.0", "end")
    app.goto_evidence_pos()
    x0, x1 = app.ax.get_xlim()
    assert x0 <= ev["week_index"] <= x1
    # zooming culls: fewer segments drawn, counts say so
    app.zoom_to(vd.node_row[ev["node_id"]], ev["week_index"] - 2, ev["week_index"] + 3, pad_rows=0)
    assert sum(int(m.sum()) for m in app.masks.values()) < vd.total_segments()
    assert "表示範囲外" in app.counts.get()
    app.destroy()
    assert _folder_hash(run_dir) == before, "viewer must not write into the run folder"
