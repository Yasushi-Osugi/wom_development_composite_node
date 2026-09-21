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
