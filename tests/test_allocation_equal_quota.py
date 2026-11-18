# -*- coding: utf-8 -*-
"""tools/allocation_equal_quota.py (RequestLetter_M6_R0_R1_GlobalAllocation A2): the equal-priority quota by the
largest remainder, the tie order, the protected key, and the stops."""
import pandas as pd
import pytest

from tools import allocation_equal_quota as Q

SOY = {"JP": 30150, "US_W": 17588, "US_E": 17588, "FR": 15075, "BE": 10050, "NL": 10050}


def test_f7_is_reproduced():
    t = Q.equal_priority_quota(SOY, "Soy_Sauce", ["JP"], ["US_W", "US_E", "FR", "BE", "NL"], 57825).set_index("region")
    assert t["alloc_lots"].to_dict() == {"BE": 8261, "FR": 12391, "JP": 30150, "NL": 8261, "US_E": 14456, "US_W": 14456}
    assert int(t["alloc_lots"].sum()) == 87975
    assert set(t.index[t["remainder_lot"] == 1]) == {"FR", "BE", "NL"}     # the three largest fractional parts
    assert t.loc["JP", "group"] == "protect" and t.loc["JP", "alloc_lots"] == t.loc["JP", "q1_original"]
    assert abs(t.loc["FR", "raw_quota"] - 57825 * 15075 / 70351) < 1e-6
    assert t.loc["BE", "quota_source"].startswith("equal priority: Q_A=57825")


def test_tie_goes_to_the_region_key_order():
    t = Q.equal_priority_quota({"B": 1, "A": 1, "C": 1}, "S", [], ["B", "A", "C"], 1).set_index("region")
    assert t["alloc_lots"].to_dict() == {"A": 1, "B": 0, "C": 0}
    t = Q.equal_priority_quota({"B": 1, "A": 1, "C": 1}, "S", [], ["B", "A", "C"], 2).set_index("region")
    assert t["alloc_lots"].to_dict() == {"A": 1, "B": 1, "C": 0}


def test_whole_and_zero_amounts():
    t = Q.equal_priority_quota(SOY, "S", ["JP"], ["US_W", "US_E", "FR", "BE", "NL"], 70351).set_index("region")
    assert (t["alloc_lots"] == t["q1_original"]).all()
    t = Q.equal_priority_quota(SOY, "S", ["JP"], ["US_W", "US_E", "FR", "BE", "NL"], 0).set_index("region")
    assert t.loc["FR", "alloc_lots"] == 0 and t.loc["JP", "alloc_lots"] == 30150


@pytest.mark.parametrize("protect,equalize,total,msg", [
    (["JP"], ["US_W", "US_E", "FR", "BE", "NL"], 70352, "以下にする"),
    (["JP"], ["US_W", "US_E", "FR", "BE", "NL"], -1, "0 以上"),
    (["JP"], ["US_W", "US_E", "FR", "BE"], 100, "どちらの一覧にもありません"),
    (["JP", "FR"], ["US_W", "US_E", "FR", "BE", "NL"], 100, "両方"),
    (["JP"], ["US_W", "US_E", "FR", "BE", "NL", "DE"], 100, "需要に無い鍵"),
])
def test_stops(protect, equalize, total, msg):
    with pytest.raises(Q.QuotaError, match=msg):
        Q.equal_priority_quota(SOY, "S", protect, equalize, total)


def test_cli_writes_the_quota_file(tmp_path):
    m = tmp_path / "m"
    m.mkdir()
    rows = [{"sku_id": "S", "region": r, "week": w, "quantity": q / 2} for r, q in SOY.items()
            for w in ("2027-W01", "2027-W02")]
    pd.DataFrame(rows).to_csv(m / "demand_forecast.csv", index=False)
    out = tmp_path / "allocation_qty_R1.csv"
    assert Q.main(["--model-dir", str(m), "--sku", "S", "--protect", "JP", "--equalize", "US_W,US_E,FR,BE,NL",
                   "--total-a", "57825", "--out", str(out)]) == 0
    t = pd.read_csv(out)
    assert list(t.columns[:3]) == ["sku_id", "region", "alloc_lots"] and int(t["alloc_lots"].sum()) == 87975
    from wom.allocation.handoff import read_quantity_allocation
    assert read_quantity_allocation(str(out))[("S", "FR")] == 12391                 # the allocation stage reads it
    assert Q.main(["--model-dir", str(m), "--sku", "S", "--equalize", "FR", "--total-a", "1", "--out", str(out)]) == 2
