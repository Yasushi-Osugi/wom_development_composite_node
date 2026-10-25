# -*- coding: utf-8 -*-
"""
tests/test_warmup_soft_blank_attrs_fifo.py — RequestLetter_WarmupSoft_BlankAttrs_ShelfLifeFIFO
=============================================================================================
  Part A : warmup の行に cap_soft を写す（wom/engine/warmup.py）
  Part B : 木の属性の空欄・不正な値（wom/engine/tree_attrs.py ← sc_tree_builder.py）
           空欄＝未設定、0＝明示の 0、それ以外は止める（大杉さんの決定 d）
  Part C : 残存期間の判定（tools/shelf_life_check.py、先入れ先出しの年齢）
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from wom.engine.warmup import materialize_warmup
from wom.engine.sc_tree_builder import build_sc_tree_from_master
from wom.engine.tree_attrs import TreeAttributeError, parse_days, parse_envelope
from wom.engine.yield_rate import YieldRateError
from tools.shelf_life_check import (ShelfLifeError, compute_fifo, add_lot_dwell,
                                    summarise, check_tree)

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COOKIE = os.path.join(REPO, "data", "sample", "Cookie-jp-2026")
WEEKS = [f"2027-W{i:02d}" for i in range(1, 41)]


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _rows(path):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()[1:]


# ---------------------------------------------------------------------------
# Part A
# ---------------------------------------------------------------------------

def _warm_model(d, cap_text):
    _write(os.path.join(d, "demand_forecast.csv"), "sku_id,region,week,quantity\nA,JP,2027-W01,1\n")
    _write(os.path.join(d, "capacity_plan.csv"), cap_text)
    _write(os.path.join(d, "planning_config.csv"), "key,value\nwarmup_lt,2\n")
    materialize_warmup(d)
    return _rows(os.path.join(d, "capacity_plan.csv"))


def test_a_warmup_copies_cap_soft(tmp_path):
    rows = _warm_model(str(tmp_path), "sku_id,node_name,week,max_supply,cap_soft,source\n"
                                      "A,Plant,2027-W01,17,14,plan\nA,Sup,2027-W01,90,,plan\n")
    assert rows[:4] == ["A,Plant,2026-W52,17,14,warmup", "A,Sup,2026-W52,90,,warmup",
                        "A,Plant,2026-W53,17,14,warmup", "A,Sup,2026-W53,90,,warmup"]


def test_a_zero_cap_soft_stays_zero(tmp_path):
    rows = _warm_model(str(tmp_path), "sku_id,node_name,week,max_supply,cap_soft,source\n"
                                      "A,Plant,2027-W01,17,0,plan\n")
    assert rows[0] == "A,Plant,2026-W52,17,0,warmup"


def test_a_no_cap_soft_column_no_column(tmp_path):
    rows = _warm_model(str(tmp_path), "sku_id,node_name,week,max_supply,cap_pieces,source\n"
                                      "A,Plant,2027-W01,17,,plan\n")
    assert rows[0] == "A,Plant,2026-W52,17,,warmup"          # same as before the change
    with open(os.path.join(str(tmp_path), "capacity_plan.csv"), encoding="utf-8") as f:
        assert f.readline().strip() == "sku_id,node_name,week,max_supply,cap_pieces,source"


def test_a_warmup_cap_soft_reaches_node(tmp_path):
    """Integration: CSV -> materialize -> real loader -> node.cap_soft in a warm-up week."""
    from wom.engine.capacity_sealer import load_capacity_dataframe
    from wom.model.sc_tree import build_demo_sc_tree
    d = str(tmp_path)
    mom = "Mother Plant [A]"
    _warm_model(d, "sku_id,node_name,week,max_supply,cap_soft,source\n"
                   f"A,{mom},2027-W01,17,14,plan\n")
    weeks = ["2026-W52", "2026-W53", "2027-W01"]
    t = build_demo_sc_tree(pd.DataFrame([{"sku_id": "A", "sku_name": "A", "region": "JP",
                                          "lead_time_wks": 1}]), weeks, lt_wks_ot=1, lt_wks_in=1)
    load_capacity_dataframe(t, pd.read_csv(os.path.join(d, "capacity_plan.csv"),
                                           dtype={"max_supply": str}), weeks)
    node = t.get_in_root("A")
    assert [node.cap_soft(w) for w in range(3)] == [14.0, 14.0, 14.0]


# ---------------------------------------------------------------------------
# Part B
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expect", [
    (None, None), ("", None), ("  ", None), (float("nan"), None),   # blank = not set
    (0, 0), ("0", 0), (14, 14), ("14", 14), (14.0, 14), ("21.0", 21)])
def test_b_days_values(raw, expect):
    assert parse_days(raw, column="ss_days", node_name="N", product="P") == expect


@pytest.mark.parametrize("raw", [-1, "-7", 2.5, "3.5", "abc", "1w"])
def test_b_days_bad_values_stop(raw):
    with pytest.raises(TreeAttributeError) as e:
        parse_days(raw, column="init_stock_days", node_name="DC", product="P", line=7)
    m = str(e.value)
    assert "sc_tree_master.csv line 7" in m and "'DC'" in m and "init_stock_days=" in m
    assert "Write 0 or a positive integer" in m


@pytest.mark.parametrize("raw, expect", [
    (None, "hard"), ("", "hard"), (float("nan"), "hard"),
    ("hard", "hard"), ("soft", "soft"), ("Soft", "soft"), (" soft ", "soft"), ("HARD", "hard")])
def test_b_envelope_values(raw, expect):
    assert parse_envelope(raw, node_name="N", product="P") == expect


def test_b_envelope_misspelt_stops():
    with pytest.raises(TreeAttributeError) as e:
        parse_envelope("sfot", node_name="Factory", product="P", line=3)
    assert "demand_envelope='sfot'" in str(e.value) and "line 3" in str(e.value)


def test_b_yield_error_is_a_tree_attribute_error():
    assert issubclass(YieldRateError, TreeAttributeError)


def _cookie(tmp_path, edit):
    df = pd.read_csv(os.path.join(COOKIE, "sc_tree_master.csv"))
    edit(df)
    p = tmp_path / "sc_tree_master.csv"
    df.to_csv(p, index=False)
    return build_sc_tree_from_master(pd.read_csv(p), WEEKS)


def _node(t, prod, name):
    return next(n for n in t.iter_all_nodes(prod) if n.node_name == name)


def test_b_csv_blank_zero_positive_reach_node(tmp_path):
    def edit(df):
        df["ss_days"] = df["ss_days"].astype(object)
        df.loc[df["node_name"] == "DC_Local_JP", "ss_days"] = ""      # blank (was 3)
        df["init_stock_days"] = ""
        df.loc[df["node_name"] == "DC_Import_Main", "init_stock_days"] = 14
        df.loc[df["node_name"] == "DC_Import_Buffer", "init_stock_days"] = 0
        df["demand_envelope"] = ""
        df.loc[df["node_name"] == "Factory_DP_JP", "demand_envelope"] = " Soft "
    t = _cookie(tmp_path, edit)
    assert _node(t, "Cookie_Local", "DC_Local_JP").ss_days == 0              # not set -> plans as 0
    assert _node(t, "Cookie_Import", "DC_Import_Main").init_stock_days == 14
    assert _node(t, "Cookie_Import", "DC_Import_Buffer").init_stock_days == 0
    assert _node(t, "Cookie_Local", "Factory_DP_JP").demand_envelope == "soft"
    assert _node(t, "Cookie_Import", "Factory_GP_CN").demand_envelope == "hard"


@pytest.mark.parametrize("col, node, val, line", [
    ("ss_days", "DC_Local_JP", "-3", 11), ("init_stock_days", "DC_Import_Main", "2.5", 4),
    ("demand_envelope", "Factory_DP_JP", "sfot", 15)])
def test_b_csv_bad_values_stop_with_line(tmp_path, col, node, val, line):
    def edit(df):
        df[col] = df[col].astype(object) if col in df else ""
        df.loc[df["node_name"] == node, col] = val
    with pytest.raises(TreeAttributeError) as e:
        _cookie(tmp_path, edit)
    m = str(e.value)
    assert f"sc_tree_master.csv line {line}" in m and repr(node) in m and f"{col}=" in m


# ---------------------------------------------------------------------------
# Part C：合成の出荷の記録
# ---------------------------------------------------------------------------
LBL = [f"W{i:02d}" for i in range(30)]


def _s(kind, lot, node, week, to="", arrival=None, prod="X"):
    return SimpleNamespace(kind=kind, product=prod, lot_id=lot, node=node, week=week, to=to,
                           arrival_week=arrival, arrival_in_horizon=arrival is not None,
                           ship_id=f"{node}:{week}:{lot}")


RANK = {("X", "SP"): 0, ("X", "DC"): 1, ("X", "Shop"): 2, ("X", "Web"): 3}


def _flow(lot, make, sp_ship, dc_ship, sale, leaf="Shop"):
    """A lot made in `make`, shipped SP->DC (lt 1), DC->leaf (lt 1), sold in `sale`."""
    return [_s("handoff_to_sp", lot, "MOM", make, "SP", make),
            _s("outbound_move", lot, "SP", sp_ship, "DC", sp_ship + 1),
            _s("outbound_move", lot, "DC", dc_ship, leaf, dc_ship + 1),
            _s("consumer_sale", lot, leaf, sale)]


def test_c1_serial_no_build_ahead_equals_lead_time():
    recs = []
    for i, w in enumerate(range(5, 10)):
        recs += _flow(f"X:Shop:W{w + 2:02d}:{i:05d}", w, w, w + 1, w + 2)   # demand week = sale week
    rows = add_lot_dwell(compute_fifo(recs, RANK, LBL)["deliveries"],
                         [f"W{i:02d}" for i in range(30)])
    assert {r["fifo_age"] for r in rows} == {2}          # SP->DC 1 + DC->Shop 1
    assert all(r["lot_dwell"] == r["fifo_age"] for r in rows)


def test_c2_build_ahead_fifo_age_is_stock_depth():
    """Two lots built at W1 for late demand wait at SP while the weekly lots flow
    through. FIFO ships the old ones first, so the age is the stock depth, not the
    Lot_ID wait. Hand-computed SP queue: W3 {1,1,3} -> ships tag 1 (sold W5, age 4);
    W4 {1,3,4} -> tag 1 (sold W6, age 5); from W5 on the queue holds {w-2,w-1,w} and
    ships w-2 (age 4 = lead time 2 + stock depth 2), incl. W18 / W19."""
    recs = []
    # pre-built lots for demand W20 / W21 (their IDs wait until W18 / W19)
    recs += _flow("X:Shop:W20:00000", 1, 18, 19, 20)
    recs += _flow("X:Shop:W21:00001", 1, 19, 20, 21)
    # weekly production 1 lot (made w, its own demand w+2..)
    for i, w in enumerate(range(3, 18)):
        recs += _flow(f"X:Shop:W{w + 2:02d}:{i + 2:05d}", w, w, w + 1, w + 2)
    rows = add_lot_dwell(compute_fifo(recs, RANK, LBL)["deliveries"], LBL)
    by_week = {r["delivery_week"]: r for r in rows}
    assert [by_week[w]["fifo_age"] for w in range(5, 22)] == [4, 5] + [4] * 15
    # Lot_ID dwell of the pre-built IDs is long (W21 - W1 = 20 weeks), FIFO max age is short
    assert max(r["lot_dwell"] for r in rows) == 20
    assert max(r["fifo_age"] for r in rows) == 5
    assert sum(1 for r in rows if r["fifo_age"] > 10) == 0


def test_c3_one_place_two_channels():
    recs = _flow("X:Shop:W06:00000", 1, 3, 4, 5) + _flow("X:Web:W06:00001", 2, 3, 4, 5, leaf="Web")
    rows = compute_fifo(recs, RANK, LBL)["deliveries"]
    # both leave SP/DC in the same weeks; the oldest tag (W1) goes to whichever is first,
    # ages are 4 and 3 in total (order inside a week is free)
    assert sorted(r["fifo_age"] for r in rows) == [3, 4]
    assert {r["channel"] for r in rows} == {"Shop", "Web"}


def test_c4_ship_more_than_held_stops():
    recs = [_s("handoff_to_sp", "a", "MOM", 1, "SP", 1),
            _s("outbound_move", "a", "SP", 2, "DC", 3),
            _s("outbound_move", "b", "SP", 2, "DC", 3)]          # b was never made
    with pytest.raises(ShelfLifeError) as e:
        compute_fifo(recs, RANK, LBL)
    assert "SP ships 2 lot(s) in week W02 but has only 1" in str(e.value)


def test_c4_deliveries_must_match_market(tmp_path):
    """Integration: Cookie-jp-2026 runs, deliveries == market actual shipments."""
    import shutil
    from tools.run_headless_from_folder import run
    from tools.shelf_life_check import _capture_plugin
    md = tmp_path / "Cookie-jp-2026"
    shutil.copytree(COOKIE, md)
    cap = _capture_plugin()
    run(str(md), output_ppc_dir=str(tmp_path / "ppc"), verbose=False, extra_plugins=[cap])
    r = check_tree(cap.tree, 52)
    market = sum(len(l) for p in cap.tree.products for n in cap.tree.iter_all_nodes(p)
                 if n.node_type == "leaf_out" for l in (n._actual_ship or {}).values())
    assert len(r["rows"]) == market > 0
    assert all(x["fifo_age"] >= 0 for x in r["rows"])
    # a broken count stops
    leaf = next(n for p in cap.tree.products for n in cap.tree.iter_all_nodes(p)
                if n.node_type == "leaf_out" and n._actual_ship)
    w = next(w for w, l in leaf._actual_ship.items() if l)
    leaf._actual_ship[w] = list(leaf._actual_ship[w]) + ["ghost"]
    with pytest.raises(ShelfLifeError):
        check_tree(cap.tree, 52)
