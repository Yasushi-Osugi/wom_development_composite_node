# -*- coding: utf-8 -*-
"""
tests/test_shelf_life_demand_file.py — RequestLetter_BSSEAF_Cosmetics_AllocationP2a Part A
===========================================================================================
tools/shelf_life_check.py の `--demand-file`・`--warmup-real-start`：数量配分モードで作った計画
（配分済みの需要 CSV）の年齢を、木を作り直す迂回なしに測る。既定の呼び方の動きは変えない。

合成のモデル：1 SKU（A）、2 チャネル（X・Y）、工場 1 つ。cpu_size 6。能力は十分。
"""
import csv
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tools.run_headless_from_folder as H
from tools import shelf_life_check as SL
from tools.run_quantity_allocation import run_quantity_allocation

WEEKS = [f"2027-W{i:02d}" for i in range(1, 13)]
DEMAND = {"X": [2] * 12, "Y": [1] * 12}


def _w(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(header)
        wr.writerows(rows)


def _model(d):
    os.makedirs(d, exist_ok=True)
    tree = [["SP_A", "", "A", "supply_point", "outbound", 0, "", 0, 0],
            ["DC", "SP_A", "A", "dad", "outbound", 1, "", 0, 0]]
    tree += [[f"Shop_{r}", "DC", "A", "leaf_out", "outbound", 1, r, 0, 0] for r in DEMAND]
    tree += [["Factory", "", "A", "mom", "inbound", "", "", 0, 0],
             ["Mat", "Factory", "A", "leaf_in", "inbound", 1, "", 0, 0]]
    _w(os.path.join(d, "sc_tree_master.csv"),
       ["node_name", "parent_node", "product_name", "node_type", "side", "lt_wks", "region",
        "ss_days", "buffering_stock_flag"], tree)
    _w(os.path.join(d, "demand_forecast.csv"), ["sku_id", "region", "week", "quantity"],
       [["A", r, wk, q] for r, qs in DEMAND.items() for wk, q in zip(WEEKS, qs)])
    _w(os.path.join(d, "capacity_plan.csv"), ["sku_id", "node_name", "week", "max_supply", "source"],
       [["A", "Factory", wk, 10, "plan"] for wk in WEEKS])
    _w(os.path.join(d, "planning_config.csv"), ["key", "value"],
       [["warmup_lt", 3], ["lot_flow_mode", "identity"], ["cpu_size", 6], ["recommended_plugins", ""]])
    return d


def _summary(out):
    with open(os.path.join(out, "shelf_life_summary.csv"), encoding="utf-8") as f:
        return {(r["product"], r["channel"]): r for r in csv.DictReader(f)}


def _deliveries(out):
    with open(os.path.join(out, "shelf_life_deliveries.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _spy(monkeypatch):
    calls = []
    orig = H.run

    def spy(*a, **k):
        calls.append(k)
        return orig(*a, **k)
    monkeypatch.setattr(H, "run", spy)
    return calls


def test_default_call_passes_the_old_defaults(tmp_path, monkeypatch):
    """Default call: the same demand CSV and warm-up base as before (run()'s own defaults)."""
    m = _model(str(tmp_path / "m"))
    calls = _spy(monkeypatch)
    assert SL.main(["--model-dir", m, "--max-age-weeks", "52", "--out", str(tmp_path / "o")]) == 0
    assert calls[0]["demand_file"] == "demand_forecast.csv"
    assert calls[0]["warmup_real_start"] is None
    # every demand lot is delivered (capacity is enough): the full plan is counted
    assert int(_summary(str(tmp_path / "o"))[("*", "*")]["deliveries"]) == sum(map(sum, DEMAND.values()))


def test_allocated_demand_file_counts_that_plan(tmp_path, monkeypatch):
    """An allocated demand CSV: the ages are counted on that plan (same period as the run)."""
    m = _model(str(tmp_path / "m"))
    alloc = str(tmp_path / "allocation_qty_t.csv")
    _w(alloc, ["sku_id", "region", "alloc_lots"], [["A", "X", 24], ["A", "Y", 6]])   # Y: 6 of 12
    r = run_quantity_allocation(m, alloc, out_dir=str(tmp_path / "ps"))
    assert r["status"] == "ok"
    st = r["state"]
    gen, base = st["evidence"]["demand_csv"], st["period"]["warmup_real_start"]
    q4 = {k["region"]: k["q4_delivered"]["total"] for k in st["quantities"]["by_key"]}
    assert q4 == {"X": 24, "Y": 6}

    calls = _spy(monkeypatch)
    out = str(tmp_path / "o_alloc")
    assert SL.main(["--model-dir", m, "--max-age-weeks", "52", "--out", out,
                    "--demand-file", gen, "--warmup-real-start", base]) == 0
    assert calls[0]["demand_file"] == gen and calls[0]["warmup_real_start"] == base
    s = _summary(out)
    assert int(s[("A", "Shop_X")]["deliveries"]) == 24
    assert int(s[("A", "Shop_Y")]["deliveries"]) == 6          # not the 12 of the original demand
    rows = _deliveries(out)
    assert all(int(x["fifo_age"]) >= 0 for x in rows)
    # the plan period is the allocation run's (the first delivery week is inside it)
    assert min(x["delivery_week"] for x in rows) >= st["period"]["start"]
    assert max(x["delivery_week"] for x in rows) <= st["period"]["end"]

    # the default call on the same folder still counts the original demand
    out0 = str(tmp_path / "o_default")
    assert SL.main(["--model-dir", m, "--max-age-weeks", "52", "--out", out0]) == 0
    assert int(_summary(out0)[("A", "Shop_Y")]["deliveries"]) == 12
