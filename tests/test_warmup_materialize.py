# -*- coding: utf-8 -*-
"""
tests/test_warmup_materialize.py — Planning Warm-up materialize の3層テスト
==========================================================================
`wom/engine/warmup.py: materialize_warmup` の Anti-Degrade テスト。
設計：requests/planning-horizon-warmup-parameter-request-letter.md（D1–D3・§5.2 案B-safe・§9）。

- Unit        : ISO 週ユーティリティ（weeks_between / week_minus / resolve_effective_start）、
                first_nonzero_demand_week。年跨ぎ（2026 は W53 まで）を含む。
- Integration : 合成モデルに対し (a) demand=0、(b) capacity/opcal は最初の実週値を後方コピー、
                (c) idempotent（二度実行で不変）、(d) byte-stable、(e) write-if-needed（no-op）、
                (f) config 無しは完全 no-op（既存ケース保護）を assert。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wom.engine import warmup
from wom.engine.warmup import (
    materialize_warmup, weeks_between, week_minus, resolve_effective_start,
    first_nonzero_demand_week,
)


# ---------------------------------------------------------------------------
# 合成モデル生成
# ---------------------------------------------------------------------------
def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _make_model(dir_, warmup_lt="3", planning_start="", with_config=True):
    """実データ 2027-W01..W03（JP/US 需要、Bottling/Materials 能力、Bottling shift）。"""
    _write(os.path.join(dir_, "demand_forecast.csv"),
           "sku_id,region,week,quantity\n"
           "Soy,JP,2027-W01,38\nSoy,US,2027-W01,22\n"
           "Soy,JP,2027-W02,40\nSoy,US,2027-W02,24\n"
           "Soy,JP,2027-W03,42\nSoy,US,2027-W03,26\n")
    _write(os.path.join(dir_, "capacity_plan.csv"),
           "sku_id,node_name,week,max_supply,source\n"
           "Soy,Bottling,2027-W01,1500,plan\nSoy,Materials,2027-W01,50000,plan\n"
           "Soy,Bottling,2027-W02,1500,plan\nSoy,Materials,2027-W02,50000,plan\n"
           "Soy,Bottling,2027-W03,1500,plan\nSoy,Materials,2027-W03,50000,plan\n")
    _write(os.path.join(dir_, "operating_calendar.csv"),
           "sku_id,node_name,week,shifts\n"
           "Soy,Bottling,2027-W01,18\nSoy,Bottling,2027-W02,18\nSoy,Bottling,2027-W03,18\n")
    if with_config:
        _write(os.path.join(dir_, "planning_config.csv"),
               f"key,value\nwarmup_lt,{warmup_lt}\nplanning_start,{planning_start}\n")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _rows(path):
    return [ln for ln in _read(path).split("\n") if ln][1:]  # ヘッダ除く非空行


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------
def test_week_minus_and_weeks_between_cross_year():
    # 2027-W01 の3週前 → 2026-W51、助走週は [2026-W51, W52, W53]（2026 は W53 まで）
    assert week_minus("2027-W01", 3) == "2026-W51"
    assert weeks_between("2026-W51", "2027-W01") == ["2026-W51", "2026-W52", "2026-W53"]
    # 26週前は 2026-W28（本番 soysauce と同じ）
    assert week_minus("2027-W01", 26) == "2026-W28"
    assert len(weeks_between("2026-W28", "2027-W01")) == 26


def test_resolve_effective_start():
    assert resolve_effective_start("2027-W01", 0, "") == "2027-W01"          # 既定0＝助走なし
    assert resolve_effective_start("2027-W01", 3, "") == "2026-W51"          # warmup_lt
    assert resolve_effective_start("2027-W01", 0, "2026-W40") == "2026-W40"  # planning_start override
    # planning_start が demand より後ろでも min() で demand を採用（早いデータを失わない）
    assert resolve_effective_start("2026-W40", 0, "2027-W01") == "2026-W40"


def test_first_nonzero_demand_week(tmp_path):
    d = str(tmp_path)
    _make_model(d)
    assert first_nonzero_demand_week(os.path.join(d, "demand_forecast.csv")) == "2027-W01"


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------
def test_materialize_demand_zero_and_copy(tmp_path):
    d = str(tmp_path)
    _make_model(d, warmup_lt="3")
    s = materialize_warmup(d)

    assert s["skipped"] is False and s["changed"] is True
    assert s["real_start"] == "2027-W01"
    assert s["effective_start"] == "2026-W51"
    assert s["warm_weeks"] == 3

    # demand: 3週 × 2region = 6 行、すべて quantity 0、週は助走週
    dem_warm = [r for r in _rows(os.path.join(d, "demand_forecast.csv")) if r.split(",")[2] < "2027-W01"]
    assert len(dem_warm) == 6
    assert all(r.split(",")[3] == "0" for r in dem_warm)
    assert {r.split(",")[2] for r in dem_warm} == {"2026-W51", "2026-W52", "2026-W53"}

    # capacity: 3週 × 2node = 6 行、max_supply は最初の実週値コピー、source=warmup
    cap_warm = [r for r in _rows(os.path.join(d, "capacity_plan.csv")) if r.split(",")[2] < "2027-W01"]
    assert len(cap_warm) == 6
    vals = {(r.split(",")[1], r.split(",")[3]) for r in cap_warm}
    assert ("Bottling", "1500") in vals and ("Materials", "50000") in vals
    assert all(r.split(",")[4] == "warmup" for r in cap_warm)

    # opcal: 3週 × 1node = 3 行、shift コピー
    opc_warm = [r for r in _rows(os.path.join(d, "operating_calendar.csv")) if r.split(",")[2] < "2027-W01"]
    assert len(opc_warm) == 3
    assert all(r.split(",")[3] == "18" for r in opc_warm)

    # 実データ行は保持されている（strip されていない）
    assert any(r.startswith("Soy,JP,2027-W01,38") for r in _rows(os.path.join(d, "demand_forecast.csv")))


def test_idempotent_and_byte_stable(tmp_path):
    d = str(tmp_path)
    _make_model(d, warmup_lt="3")
    materialize_warmup(d)
    snap1 = {f: _read(os.path.join(d, f)) for f in
             ("demand_forecast.csv", "capacity_plan.csv", "operating_calendar.csv")}
    s2 = materialize_warmup(d)               # 2回目
    snap2 = {f: _read(os.path.join(d, f)) for f in snap1}

    assert s2["changed"] is False            # write-if-needed の no-op
    assert snap1 == snap2                     # byte-stable（バイト列一致）


def test_write_if_needed_dry_run_does_not_write(tmp_path):
    d = str(tmp_path)
    _make_model(d, warmup_lt="3")
    before = _read(os.path.join(d, "demand_forecast.csv"))
    s = materialize_warmup(d, write=False)   # dry-run
    after = _read(os.path.join(d, "demand_forecast.csv"))
    assert s["changed"] is True              # 差分は「ある」と報告
    assert before == after                   # だが書いていない


def test_no_config_is_noop(tmp_path):
    d = str(tmp_path)
    _make_model(d, with_config=False)        # planning_config.csv 無し
    before = {f: _read(os.path.join(d, f)) for f in
              ("demand_forecast.csv", "capacity_plan.csv", "operating_calendar.csv")}
    s = materialize_warmup(d)
    after = {f: _read(os.path.join(d, f)) for f in before}
    assert s["skipped"] is True and s["changed"] is False
    assert before == after                   # 完全 no-op（既存ケース保護）


def test_warmup_lt_zero_strips_existing_warmup(tmp_path):
    d = str(tmp_path)
    _make_model(d, warmup_lt="3")
    materialize_warmup(d)                     # 助走行あり
    # warmup_lt=0 にすると助走行は strip される（現在値でクリーン再生成）
    s = materialize_warmup(d, warmup_lt=0)
    assert s["changed"] is True
    dem_warm = [r for r in _rows(os.path.join(d, "demand_forecast.csv")) if r.split(",")[2] < "2027-W01"]
    assert dem_warm == []


# ---------------------------------------------------------------------------
# 旧書式の capacity_plan（node_name 列なし）
# RequestLetter_iPhoneWarmup_EVUpdateKitting_S2 A1・A3
# ---------------------------------------------------------------------------
_OLD_HEADER = "sku_id,region,week,max_supply,cap_pieces,source\n"


def _make_old_format_model(dir_, warmup_lt="3"):
    """旧書式：SKU-A は 2 地域（拠点が違う）、SKU-B は 1 地域、SKU-C は後から発売。"""
    _write(os.path.join(dir_, "demand_forecast.csv"),
           "sku_id,region,week,quantity\n"
           "SKU-A,JP,2027-W01,10\nSKU-B,JP,2027-W01,5\n"
           "SKU-A,JP,2027-W02,10\nSKU-B,JP,2027-W02,5\nSKU-C,JP,2027-W02,7\n")
    _write(os.path.join(dir_, "capacity_plan.csv"),
           _OLD_HEADER +
           "SKU-A,CN,2027-W01,800,,Plant_CN\nSKU-A,IN,2027-W01,300,,Plant_IN\n"
           "SKU-B,CN,2027-W01,500,12,\"Plant_CN, line 2\"\n"
           "SKU-A,CN,2027-W02,700,,Plant_CN\nSKU-A,IN,2027-W02,300,,Plant_IN\n"
           "SKU-B,CN,2027-W02,500,12,\"Plant_CN, line 2\"\nSKU-C,CN,2027-W02,50,,Plant_CN\n")
    _write(os.path.join(dir_, "planning_config.csv"), f"key,value\nwarmup_lt,{warmup_lt}\n")


def _csv_rows(path):
    import csv
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_old_format_capacity_rows_are_copied_per_row(tmp_path):
    """旧書式：最初の実週の各行を、week だけ替えてそのままコピーする。
    製品・地域を混ぜない。region・source・cap_pieces を保つ。node_name 列は足さない。"""
    d = str(tmp_path)
    _make_old_format_model(d)
    before = _read(os.path.join(d, "capacity_plan.csv"))
    s = materialize_warmup(d)
    assert s["files"]["capacity_plan.csv"] == {"warm_rows": 9, "changed": True}   # 3 週 × 3 行

    text = _read(os.path.join(d, "capacity_plan.csv"))
    assert text.split("\n")[0] == _OLD_HEADER.strip()          # 見出しは変えない（node_name を足さない）
    rows = _csv_rows(os.path.join(d, "capacity_plan.csv"))
    warm = [r for r in rows if r["week"] < "2027-W01"]
    assert {r["week"] for r in warm} == {"2026-W51", "2026-W52", "2026-W53"}
    for wk in ("2026-W51", "2026-W52", "2026-W53"):
        got = sorted((r["sku_id"], r["region"], r["max_supply"], r["cap_pieces"], r["source"])
                     for r in warm if r["week"] == wk)
        assert got == [("SKU-A", "CN", "800", "", "Plant_CN"),
                       ("SKU-A", "IN", "300", "", "Plant_IN"),
                       ("SKU-B", "CN", "500", "12", "Plant_CN, line 2")]
    # 後から発売される SKU-C（最初の実週に行が無い）には、助走行を作らない
    assert not [r for r in warm if r["sku_id"] == "SKU-C"]
    # 実需要期間の行は、1 バイトも変わらない（末尾にそのまま残る）
    assert text.endswith(before[len(_OLD_HEADER):])


def test_old_format_idempotent_and_strip(tmp_path):
    d = str(tmp_path)
    _make_old_format_model(d)
    original = _read(os.path.join(d, "capacity_plan.csv"))
    materialize_warmup(d)
    once = _read(os.path.join(d, "capacity_plan.csv"))
    s2 = materialize_warmup(d)
    assert s2["changed"] is False and _read(os.path.join(d, "capacity_plan.csv")) == once
    # 生成対象 0 行：warmup_lt=0 で助走行を取り除くと、元のファイルに戻る
    s0 = materialize_warmup(d, warmup_lt=0)
    assert s0["files"]["capacity_plan.csv"]["warm_rows"] == 0
    assert _read(os.path.join(d, "capacity_plan.csv")) == original


def test_new_format_multi_node_unchanged_behaviour(tmp_path):
    """新書式（node_name あり）の挙動は変えない：(sku, node) ごとに最初の実週値、source=warmup。"""
    d = str(tmp_path)
    _write(os.path.join(d, "demand_forecast.csv"),
           "sku_id,region,week,quantity\nA,JP,2027-W01,1\nB,JP,2027-W01,1\n")
    _write(os.path.join(d, "capacity_plan.csv"),
           "sku_id,node_name,week,max_supply,cap_soft,source\n"
           "A,Plant,2027-W01,100,80,plan\nA,Supplier,2027-W01,900,,plan\nB,Plant_B,2027-W01,50,,plan\n")
    _write(os.path.join(d, "planning_config.csv"), "key,value\nwarmup_lt,2\n")
    materialize_warmup(d)
    assert _rows(os.path.join(d, "capacity_plan.csv"))[:6] == [
        "A,Plant,2026-W52,100,,warmup", "A,Supplier,2026-W52,900,,warmup", "B,Plant_B,2026-W52,50,,warmup",
        "A,Plant,2026-W53,100,,warmup", "A,Supplier,2026-W53,900,,warmup", "B,Plant_B,2026-W53,50,,warmup"]


def test_capacity_missing_required_column_is_a_clear_error(tmp_path):
    import pytest
    d = str(tmp_path)
    _make_old_format_model(d)
    _write(os.path.join(d, "capacity_plan.csv"),
           "sku_id,region,week,cap_pieces\nSKU-A,CN,2027-W01,\n")          # max_supply が無い
    with pytest.raises(ValueError, match="max_supply"):
        materialize_warmup(d)


def test_old_format_csv_to_warmup_to_real_loader(tmp_path):
    """結合：CSV → materialize_warmup → 実ローダ（load_capacity_dataframe）。
    旧書式は (sku_id, week) の合計が MOM（InBound root）の能力になる。助走週の能力は
    最初の実週と同じ（800＋300）になり、実週の能力は変わらない。"""
    import pandas as pd
    from wom.model.sc_tree import build_demo_sc_tree
    from wom.engine.capacity_sealer import load_capacity_dataframe
    d = str(tmp_path)
    _make_old_format_model(d)
    materialize_warmup(d)
    weeks = ["2026-W51", "2026-W52", "2026-W53", "2027-W01", "2027-W02"]
    sku_master = pd.DataFrame([{"sku_id": k, "sku_name": k, "region": "JP", "lead_time_wks": 1}
                               for k in ("SKU-A", "SKU-B", "SKU-C")])
    tree = build_demo_sc_tree(sku_master, weeks, lt_wks_ot=1, lt_wks_in=1)
    stats = load_capacity_dataframe(tree, pd.read_csv(os.path.join(d, "capacity_plan.csv")), weeks)
    assert stats["week_out_of_range"] == 0 and stats["node_not_found"] == 0
    cap = lambda sku: [tree.get_in_root(sku).cap_hard(w) for w in range(len(weeks))]
    assert cap("SKU-A") == [1100.0, 1100.0, 1100.0, 1100.0, 1000.0]
    assert cap("SKU-B") == [500.0, 500.0, 500.0, 500.0, 500.0]
    assert cap("SKU-C") == [0.0, 0.0, 0.0, 0.0, 50.0]      # 発売前は能力の行なし（＝未設定）のまま


if __name__ == "__main__":
    import tempfile
    for name in list(globals()):
        if name.startswith("test_"):
            fn = globals()[name]
            with tempfile.TemporaryDirectory() as td:
                import inspect
                if "tmp_path" in inspect.signature(fn).parameters:
                    import pathlib
                    fn(pathlib.Path(td))
                else:
                    fn()
            print(f"PASS {name}")
    print("All warmup materialize tests passed.")
