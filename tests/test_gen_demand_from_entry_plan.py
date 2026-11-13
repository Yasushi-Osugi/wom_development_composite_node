# -*- coding: utf-8 -*-
"""tools/gen_demand_from_entry_plan.py（RequestLetter_Cockpit_FirstComparison_Observe §2・S4）"""
import os
import shutil
from decimal import Decimal

import pytest

from tools import gen_demand_from_entry_plan as G

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SAMPLE = os.path.join(REPO, "data", "sample", "cosmetics-sg-th-2027-2029")
HEADER = "sku_id,region,launch_week,steady_lots_per_week,ramp_weeks,ramp_ratio,price,currency,promotion_note,basis_note\n"

# F2 of the request letter, in the row order of the sample's demand CSV
F2_ROWS = [
    "COS_Serum,SG_Store,2027-W14,4,13,0.5,165,SGD,,",
    "COS_Serum,SG_EC,2027-W01,3,13,0.5,157,SGD,,",
    "COS_Serum,SG_Distributor,2027-W01,6,13,0.5,74,SGD,,",
    "COS_Cream,SG_Store,2027-W14,3,13,0.5,138,SGD,,",
    "COS_Cream,SG_EC,2027-W01,2,13,0.5,131,SGD,,",
    "COS_Cream,SG_Distributor,2027-W01,5,13,0.5,62,SGD,,",
    "COS_Serum,TH_Distributor,2028-W01,4,13,0.5,1900,THB,,",
    "COS_Cream,TH_Distributor,2028-W01,3,13,0.5,1600,THB,,",
]


def _model(tmp_path, rows):
    """A copy of the sample's tree and prices with the given entry plan rows."""
    d = tmp_path / "m"
    d.mkdir()
    for f in ("sc_tree_master.csv", "ppc_market_price.csv"):
        shutil.copy(os.path.join(SAMPLE, f), d / f)
    (d / "market_entry_plan.csv").write_text(HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    return str(d)


def _read(path):
    return [ln.split(",") for ln in open(path, encoding="utf-8").read().splitlines()[1:]]


# ── 規則 ─────────────────────────────────────────────────────────────
def test_rule_before_ramp_steady():
    r = Decimal("0.5")
    assert G.demand_for_week(-1, 3, 13, r) == 0
    assert G.demand_for_week(0, 3, 13, r) == 2      # 1.5 -> 2 (0.5 rounds up)
    assert G.demand_for_week(12, 5, 13, r) == 3     # 2.5 -> 3
    assert G.demand_for_week(0, 4, 13, r) == 2
    assert G.demand_for_week(13, 3, 13, r) == 3
    assert G.demand_for_week(0, 3, 0, r) == 3       # no ramp


def test_week_range_crosses_w53():
    w = G.week_range("2026-W52", "2027-W02")
    assert w == ["2026-W52", "2026-W53", "2027-W01", "2027-W02"]


def test_generated_values_and_order(tmp_path):
    m = _model(tmp_path, ["COS_Cream,TH_Distributor,2027-W02,3,2,0.5,,,,",
                          "COS_Cream,SG_EC,2027-W01,2,1,0.5,,,,"])
    out = str(tmp_path / "d.csv")
    log = G.run(m, "2026-W53", "2027-W04", out)
    rows = _read(out)
    # before real_start (2027-W01): week-major, keys sorted
    assert rows[0] == ["COS_Cream", "SG_EC", "2026-W53", "0"]
    assert rows[1] == ["COS_Cream", "TH_Distributor", "2026-W53", "0"]
    # from real_start on: key by key in the plan's row order
    assert [r[0:2] for r in rows[2:6]] == [["COS_Cream", "TH_Distributor"]] * 4
    assert [int(r[3]) for r in rows[2:6]] == [0, 2, 2, 3]
    assert [int(r[3]) for r in rows[6:10]] == [1, 2, 2, 2]
    assert log["rows_written"] == 10
    assert log["totals_by_key"] == {"COS_Cream:SG_EC": 7, "COS_Cream:TH_Distributor": 7}
    assert os.path.exists(tmp_path / "demand_generation_log.json")


def test_reproduces_the_official_sample_byte_for_byte(tmp_path):
    m = _model(tmp_path, F2_ROWS)
    out = str(tmp_path / "demand_forecast.csv")
    G.run(m, "2026-W37", "2029-W52", out)
    assert open(out, "rb").read() == open(os.path.join(SAMPLE, "demand_forecast.csv"), "rb").read()


def test_early_thai_cream_adds_78_lots(tmp_path):
    rows = [r.replace("COS_Cream,TH_Distributor,2028-W01", "COS_Cream,TH_Distributor,2027-W27") for r in F2_ROWS]
    m = _model(tmp_path, rows)
    log = G.run(m, "2026-W37", "2029-W52", str(tmp_path / "d.csv"))
    assert log["totals_by_key"]["COS_Cream:TH_Distributor"] == 299 + 78
    assert log["total_lots"] == 4056 + 78


# ── 止める条件 ────────────────────────────────────────────────────────
@pytest.mark.parametrize("rows,needle", [
    (["COS_Cream,SG_EC,2027-W01,2,13,0.5,,,,", "COS_Cream,SG_EC,2027-W05,2,13,0.5,,,,"], "重複"),
    (["COS_Cream,JP_Store,2027-W01,2,13,0.5,,,,"], "計画の木の市場にありません"),
    (["COS_Cream,SG_EC,2027-W54,2,13,0.5,,,,"], "launch_week が不正"),
    (["COS_Cream,SG_EC,2027-1,2,13,0.5,,,,"], "launch_week が不正"),
    (["COS_Cream,SG_EC,2027-W01,-2,13,0.5,,,,"], "0 以上の整数"),
    (["COS_Cream,SG_EC,2027-W01,abc,13,0.5,,,,"], "数値ではありません"),
    (["COS_Cream,SG_EC,2027-W01,2,,0.5,,,,"], "空欄"),
    (["COS_Cream,SG_EC,2027-W01,2,13,,,,,"], "空欄"),
    (["COS_Cream,SG_EC,2027-W01,2,13,-0.5,,,,"], "負"),
    (["COS_Cream,SG_EC,2027-W01,2,13,0.5,130,SGD,,"], "ppc_market_price.csv"),
    (["COS_Cream,SG_EC,2027-W01,2,13,0.5,131,THB,,"], "ppc_market_price.csv"),
    (["COS_Cream,SG_EC,2027-W01,2,13,0.5,131,,,"], "両方"),
    (["COS_Cream,SG_EC,2030-W01,2,13,0.5,,,,"], "期間"),
])
def test_stops(tmp_path, rows, needle):
    m = _model(tmp_path, rows)
    with pytest.raises(G.EntryPlanError) as e:
        G.run(m, "2026-W37", "2029-W52", str(tmp_path / "d.csv"))
    assert needle in str(e.value)
    assert not os.path.exists(tmp_path / "d.csv")


def test_stops_on_missing_column(tmp_path):
    m = _model(tmp_path, [])
    with open(os.path.join(m, "market_entry_plan.csv"), "w", encoding="utf-8") as f:
        f.write("sku_id,region,launch_week,steady_lots_per_week\nCOS_Cream,SG_EC,2027-W01,2\n")
    with pytest.raises(G.EntryPlanError, match="列が足りません"):
        G.run(m, "2026-W37", "2029-W52", str(tmp_path / "d.csv"))


def test_stops_on_bad_period(tmp_path):
    m = _model(tmp_path, ["COS_Cream,SG_EC,2027-W01,2,13,0.5,,,,"])
    with pytest.raises(G.EntryPlanError, match="--plan-end"):
        G.run(m, "2026-W37", "2025-W01", str(tmp_path / "d.csv"))
    with pytest.raises(G.EntryPlanError, match="--plan-start"):
        G.run(m, "2026-W99", "2029-W52", str(tmp_path / "d.csv"))


def test_cli_exit_code(tmp_path):
    m = _model(tmp_path, ["COS_Cream,JP_Store,2027-W01,2,13,0.5,,,,"])
    assert G.main(["--model-dir", m, "--plan-start", "2026-W37", "--plan-end", "2029-W52",
                   "--out", str(tmp_path / "d.csv")]) == 2
