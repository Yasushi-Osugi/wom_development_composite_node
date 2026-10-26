# -*- coding: utf-8 -*-
"""
tests/test_quantity_allocation.py — RequestLetter_QuantityAllocationMode v0.2 §D
==================================================================================
数量配分モード：人が lot の数量で決めた配分を、金額なしで 配分 → Backward → Forward →
記録 まで一巡させる（tools/run_quantity_allocation.py、wom/allocation/handoff.py）。

合成のモデル：2 SKU（A・B）が同じ地域名（X・Y）を使う。工場 1 つ（直列の InBound）。
cpu_size 6。ppc_*・ga_* のファイルは置かない。
"""
import csv
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.allocation.handoff import (QuantityAllocationError, write_demand_for_allocation,
                                    write_demand_for_quantity_allocation)
from tools.run_quantity_allocation import observed_quantities, run_quantity_allocation, _leaf_region

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEEKS = [f"2027-W{i:02d}" for i in range(1, 13)]
# (sku, region): weekly lots for W01..W12
BASE_DEMAND = {("A", "X"): [2] * 12, ("A", "Y"): [1] * 12,
               ("B", "X"): [1] * 12, ("B", "Y"): [2] * 12}


def _w(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(header)
        wr.writerows(rows)


def make_model(d, *, cap=10, cap_by_week=None, demand=None, mode="identity", layer=False):
    os.makedirs(d, exist_ok=True)
    demand = demand or BASE_DEMAND
    tree = []
    for s in ("A", "B"):
        tree += [[f"SP_{s}", "", s, "supply_point", "outbound", 0, "", 0, 0],
                 ["DC", f"SP_{s}", s, "dad", "outbound", 1, "", 0, 0]]
        for (sk, reg) in demand:
            if sk == s:
                tree.append([f"Shop_{reg}", "DC", s, "leaf_out", "outbound", 1, reg, 0, 0])
        tree += [["Factory", "", s, "mom", "inbound", "", "", 0, 0],
                 ["Mat", "Factory", s, "leaf_in", "inbound", 1, "", 0, 0]]
    _w(os.path.join(d, "sc_tree_master.csv"),
       ["node_name", "parent_node", "product_name", "node_type", "side", "lt_wks", "region",
        "ss_days", "buffering_stock_flag"], tree)
    _w(os.path.join(d, "demand_forecast.csv"), ["sku_id", "region", "week", "quantity"],
       [[s, r, wk, q] for (s, r), qs in demand.items() for wk, q in zip(WEEKS, qs)])
    _w(os.path.join(d, "capacity_plan.csv"), ["sku_id", "node_name", "week", "max_supply", "source"],
       [[s, "Factory", wk, (cap_by_week or {}).get(wk, cap), "plan"] for s in ("A", "B") for wk in WEEKS])
    _w(os.path.join(d, "planning_config.csv"), ["key", "value"],
       [["warmup_lt", 3], ["lot_flow_mode", mode], ["cpu_size", 6],
        ["recommended_plugins", "CapacityLayerPlugin" if layer else ""]])
    if layer:
        _w(os.path.join(d, "capacity_layer_config.csv"), ["key", "value"], [["max_advance_weeks", 3]])
    return d


def make_alloc(path, alloc):
    _w(path, ["sku_id", "region", "alloc_lots"], [[s, r, v] for (s, r), v in alloc.items()])
    return path


def full_alloc(demand=None):
    return {k: sum(v) for k, v in (demand or BASE_DEMAND).items()}


def _run(tmp_path, model, alloc, **kw):
    os.makedirs(str(tmp_path), exist_ok=True)
    a = make_alloc(str(tmp_path / "allocation_qty_t.csv"), alloc)
    out = str(tmp_path / "ps")
    return run_quantity_allocation(model, a, out_dir=out, **kw), out


def _keys(state):
    return {(r["sku_id"], r["region"]): r for r in state["quantities"]["by_key"]}


# ---------------------------------------------------------------------------

def test_t01_t02_runs_without_money_and_without_ppc(tmp_path, monkeypatch):
    import tools.run_headless_from_folder as H

    def _boom(*a, **k):
        raise AssertionError("PPC must not be called in the quantity mode")
    monkeypatch.setattr(H, "_run_ppc", _boom)
    m = make_model(str(tmp_path / "m"))
    assert not any(f.startswith(("ppc_", "ga_")) for f in os.listdir(m))
    r, out = _run(tmp_path, m, full_alloc())
    assert r["status"] == "ok" and os.path.exists(r["path"])
    st = r["state"]
    assert st["valuation"] == "未評価" and st["mode"] == "quantity"
    assert st["allocation_id"] == "Q01" and st["unit"] == "lot" and st["cpu_size"] == 6
    for bad in ("profit", "revenue", "cost", "unallocated"):
        assert bad not in json.dumps(st["quantities"])
        assert bad not in st
    assert st["evidence"]["ppc"] == {"status": "未評価", "reason": "quantity allocation mode"}
    assert st["evidence"]["ppc_output_created"] is False
    assert st["state"] == "plan_computed" and st["unallocated_treatment"] == "未決（U1）"


def test_t03_identities_and_no_double_count(tmp_path):
    m = make_model(str(tmp_path / "m"))
    alloc = {("A", "X"): 12, ("A", "Y"): 12, ("B", "X"): 5, ("B", "Y"): 24}
    r, _ = _run(tmp_path, m, alloc)
    assert r["status"] == "ok"
    for k, v in _keys(r["state"]).items():
        assert v["q1_original"] == v["q2_in_supply_scope"] + v["q3_not_in_supply_scope"]
        assert v["q2_in_supply_scope"] == v["q4_delivered"]["total"] + v["q5_backlog_end"]
        assert v["q2_in_supply_scope"] == alloc[k]          # not doubled by the shared region name
    with open(os.path.join(m, "demand_forecast_Q01.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert sum(int(x["quantity"]) for x in rows if (x["sku_id"], x["region"]) == ("B", "X")) == 5


def test_t04_full_allocation_rows_are_verbatim(tmp_path):
    m = make_model(str(tmp_path / "m"))
    alloc = full_alloc(); alloc[("B", "Y")] = 10
    a = make_alloc(str(tmp_path / "a.csv"), alloc)
    write_demand_for_quantity_allocation(m, a, "Z1")
    with open(os.path.join(m, "demand_forecast.csv"), encoding="utf-8") as f:
        orig = f.read().splitlines()
    with open(os.path.join(m, "demand_forecast_Z1.csv"), encoding="utf-8") as f:
        gen = f.read().splitlines()
    assert len(orig) == len(gen) and orig[0] == gen[0]
    for o, g in zip(orig[1:], gen[1:]):
        if not o.startswith("B,Y,"):
            assert o == g                                  # alloc == q1 -> verbatim


def test_t05_enough_capacity_all_delivered(tmp_path):
    r, _ = _run(tmp_path, make_model(str(tmp_path / "m"), cap=10), full_alloc())
    t = r["state"]["quantities"]["total"]
    assert t["q5_backlog_end"] == 0 and t["q4_delivered"]["total"] == t["q2_in_supply_scope"] == 72
    assert r["state"]["outcome"] == "配分した量を期間内に全て引渡し"


def test_t06_short_capacity_saved_with_backlog(tmp_path):
    r, out = _run(tmp_path, make_model(str(tmp_path / "m"), cap=2), full_alloc())
    assert r["status"] == "ok"
    t = r["state"]["quantities"]["total"]
    assert t["q5_backlog_end"] > 0 and r["state"]["outcome"] == "配分後の未充足あり"
    with open(os.path.join(out, "m", "Q01_flow_check", "flow_check_market.csv"),
              encoding="utf-8-sig") as f:
        assert all(int(x["check"]) == 0 for x in csv.DictReader(f))


@pytest.mark.parametrize("alloc, needle", [
    ({**full_alloc(), ("A", "X"): 25}, "alloc_lots 25 > original demand 24"),       # 1
    ({k: v for k, v in full_alloc().items() if k != ("B", "Y")}, "no row in the allocation file"),  # 2
    ({**full_alloc(), ("A", "Q"): 1}, "not in demand_forecast.csv"),                 # 3
])
def test_t07_stop_conditions_write_nothing(tmp_path, alloc, needle):
    m = make_model(str(tmp_path / "m"))
    with pytest.raises(QuantityAllocationError) as e:
        _run(tmp_path, m, alloc)
    assert needle in str(e.value)
    assert not any(f.startswith("demand_forecast_Q") for f in os.listdir(m))
    assert not os.path.exists(str(tmp_path / "ps" / "m" / "Q01.json"))


@pytest.mark.parametrize("cell", ["-1", "2.5", "x"])
def test_t07_bad_values_and_duplicates(tmp_path, cell):
    m = make_model(str(tmp_path / "m"))
    a = str(tmp_path / "a.csv")
    _w(a, ["sku_id", "region", "alloc_lots"],
       [["A", "X", cell], ["A", "Y", 12], ["B", "X", 12], ["B", "Y", 24], ["B", "Y", 24]])
    with pytest.raises(QuantityAllocationError) as e:
        write_demand_for_quantity_allocation(m, a, "Z9")
    assert "not an integer >= 0" in str(e.value) and "duplicate key" in str(e.value)
    assert not os.path.exists(os.path.join(m, "demand_forecast_Z9.csv"))


def _tamper(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    i = next(i for i, l in enumerate(lines) if l.startswith("A,X,2027-W05,"))
    lines[i] = "A,X,2027-W05,9"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def test_t08_t15_inconsistency_not_saved_and_numbers_not_skipped(tmp_path):
    m = make_model(str(tmp_path / "m"))
    a = make_alloc(str(tmp_path / "allocation_qty_t.csv"), full_alloc())
    out = str(tmp_path / "ps")
    ok1 = run_quantity_allocation(m, a, out_dir=out)
    assert ok1["status"] == "ok" and ok1["state"]["allocation_id"] == "Q01"
    bad = run_quantity_allocation(m, a, out_dir=out, _after_handoff=_tamper)
    assert bad["status"] == "inconsistent"
    assert not bad["checks"]["q2_observed_equals_handoff"]["ok"]
    assert os.path.exists(bad["diagnostics"])
    with open(bad["diagnostics"], encoding="utf-8") as f:
        assert json.load(f)["message"] == "入力・記録の不整合"
    assert not os.path.exists(os.path.join(out, "m", "Q02.json"))
    assert not os.path.exists(os.path.join(m, "demand_forecast_Q02.csv"))
    ok2 = run_quantity_allocation(m, a, out_dir=out)
    assert ok2["state"]["allocation_id"] == "Q02"                 # Q02 not skipped


def test_t08_cli_exit_code_and_message(tmp_path, capsys):
    from tools import run_quantity_allocation as T
    m = make_model(str(tmp_path / "m"), mode="legacy")
    a = make_alloc(str(tmp_path / "allocation_qty_t.csv"), full_alloc())
    assert T.main(["--model-dir", m, "--allocation-file", a, "--out-dir", str(tmp_path / "ps")]) == 1
    assert "入力・記録の不整合" in capsys.readouterr().out


def test_t09_ratio_route_stops_on_shared_region(tmp_path):
    src = os.path.join(REPO, "data", "sample", "soysauce-jpy-2027-alloc")
    d = str(tmp_path / "alloc")
    shutil.copytree(src, d)
    with open(os.path.join(d, "demand_forecast.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    reg = next(r["region"] for r in rows if float(r["quantity"]) > 0)
    with open(os.path.join(d, "demand_forecast.csv"), "a", encoding="utf-8", newline="") as f:
        f.write(f"Other_SKU,{reg},{rows[0]['week']},3\n")
    with pytest.raises(ValueError) as e:
        write_demand_for_allocation(d, {"JP": 0.4, "US": 0.3, "EU": 0.3}, "A99", cap_wk=800)
    assert reg in str(e.value) and "Other_SKU" in str(e.value)
    assert not os.path.exists(os.path.join(d, "demand_forecast_A99.csv"))


def test_t10_backlog_is_first_shipment_not_last_week_co():
    """A Lot_ID in the last week's CO that ships that week is NOT backlog; a Lot_ID
    requested in the last week that never ships IS backlog."""
    import pandas as pd
    from wom.model.sc_tree import build_demo_sc_tree
    from wom.engine.flow_check import compute_flow_check
    from wom.model.plan_node import S, CO
    t = build_demo_sc_tree(pd.DataFrame([{"sku_id": "A", "sku_name": "A", "region": "JP",
                                          "lead_time_wks": 1}]), WEEKS[:4], lt_wks_ot=1, lt_wks_in=1)
    leaf = next(n for n in t.iter_all_nodes("A") if n.node_type == "leaf_out")
    for n in t.iter_all_nodes("A"):
        n._actual_ship = {}
    late, last, ontime = "A:JP:2027-W02:00001", "A:JP:2027-W04:00001", "A:JP:2027-W01:00001"
    leaf.psi4supply[0][S] = [ontime]
    leaf.psi4supply[1][S] = [late]
    leaf.psi4supply[3][S] = [last]
    leaf.psi4supply[3][CO] = [late]                 # late lot is in the last week's CO ...
    leaf._actual_ship = {0: [ontime], 3: [late]}    # ... and ships in the last week
    fc = compute_flow_check(t, {})
    obs = observed_quantities(fc["market"], _leaf_region(t))
    (k, v), = obs.items()
    assert v["demand"] == 3 and v["on_time"] == 1 and v["late"] == 1
    assert v["backlog_end"] == 1                    # = the W04 request, not the CO lot


def test_t11_capacity_layer_on(tmp_path):
    m = make_model(str(tmp_path / "m"), cap=2, layer=True)
    alloc = full_alloc(); alloc[("A", "X")] = 20
    r, _ = _run(tmp_path, m, alloc)
    assert r["status"] == "ok"
    assert "CapacityLayerPlugin" in r["state"]["evidence"]["plugins"]
    k = _keys(r["state"])
    assert k[("A", "X")]["q3_not_in_supply_scope"] == 4                  # from the file only
    for v in k.values():
        assert v["q2_in_supply_scope"] == v["q4_delivered"]["total"] + v["q5_backlog_end"]


def _period_files(m):
    with open(os.path.join(m, "capacity_plan.csv"), encoding="utf-8") as f:
        return f.read()


def test_t12_t13_period_and_capacity_fixed(tmp_path):
    dem = {**BASE_DEMAND,
           ("A", "Z"): [5, 5, 5] + [0] * 9}                       # only W01-W03
    dem = {k: ([0, 0, 0] + v[3:] if k != ("A", "Z") else v) for k, v in dem.items()}
    m = make_model(str(tmp_path / "m"), demand=dem, cap_by_week={"2027-W01": 7})
    base, _ = _run(tmp_path / "b", m, full_alloc(dem))
    cap_after_base = _period_files(m)
    zero_head = full_alloc(dem); zero_head[("A", "Z")] = 0          # the first 3 weeks -> 0
    r12, _ = _run(tmp_path / "c", m, zero_head)
    assert r12["status"] == "ok"
    assert r12["state"]["period"] == base["state"]["period"]
    assert _period_files(m) == cap_after_base
    assert ",2027-W01,7," in cap_after_base                         # the W01 capacity kept
    none = {k: 0 for k in full_alloc(dem)}
    r13, _ = _run(tmp_path / "d", m, none)
    assert r13["status"] == "ok" and r13["state"]["period"] == base["state"]["period"]
    t = r13["state"]["quantities"]["total"]
    assert t["q3_not_in_supply_scope"] == t["q1_original"] > 0
    assert t["q4_delivered"]["total"] == t["q5_backlog_end"] == 0
    assert _period_files(m) == cap_after_base


def test_t14_legacy_stops_before_planning(tmp_path):
    m = make_model(str(tmp_path / "m"), mode="legacy")
    r, out = _run(tmp_path, m, full_alloc())
    assert r["status"] == "inconsistent" and not r["checks"]["lot_flow_mode"]["ok"]
    assert not any(f.startswith("demand_forecast_Q") for f in os.listdir(m))
    assert not os.path.exists(os.path.join(out, "m", "Q01.json"))


def test_t16_load_reads_old_unmet_lots(tmp_path):
    import wom.planning_state as ps
    d = tmp_path / "ps" / "case"
    d.mkdir(parents=True)
    (d / "A01.json").write_text(json.dumps({"case": "case", "allocation_id": "A01",
                                            "realized": {"unmet_lots": 37.0}}), encoding="utf-8")
    (d / "A02.json").write_text(json.dumps({"case": "case", "allocation_id": "A02",
                                            "realized": {"unmet_lots": 5, "backlog_lot_weeks": 9}}),
                                encoding="utf-8")
    s1 = ps.load("case", "A01", str(tmp_path / "ps"))
    assert s1["realized"]["backlog_lot_weeks"] == 37.0 and "unmet_lots" not in s1["realized"]
    assert ps.load("case", "A02", str(tmp_path / "ps"))["realized"]["backlog_lot_weeks"] == 9
    assert '"unmet_lots": 37.0' in (d / "A01.json").read_text(encoding="utf-8")   # file not rewritten
