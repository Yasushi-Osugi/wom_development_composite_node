# -*- coding: utf-8 -*-
"""tools/period_fulfillment.py (RequestLetter_M6_R0_R1_GlobalAllocation A1): ① ＝ ② ＋ ③ and ② ＝ ④ ＋ ⑤, the
ratios, ② ＝ ① without allocation, the year / quarter sums, the zero-supply weeks, and the rule / result apart."""
import pandas as pd
import pytest

from tools import compare_scenarios as CS
from tools import period_fulfillment as F

from test_compare_scenarios import make_case


def test_quarter_of():
    assert [F.quarter_of(w) for w in ("2027-W01", "2027-W13", "2027-W14", "2027-W40", "2026-W53")] == \
        ["2027-Q1", "2027-Q1", "2027-Q2", "2027-Q4", "2026-Q4"]


def _r0(tmp_path):
    # demand 1 in W02, 2 in W03, 1 in W04; ships: W02 on time, one W03 lot late in W04; W04 not served
    run, model = make_case(str(tmp_path), "b", {"2027-W02": 1, "2027-W03": 2, "2027-W04": 1},
                           {("2027-W02", 1): "2027-W02", ("2027-W03", 1): "2027-W04"})
    return CS.load_run(run, model)


def test_without_allocation_q2_equals_q1_and_identities_hold(tmp_path):
    run = _r0(tmp_path)
    req = F.request_table(run, None, "b")
    assert (req["q2"] == req["q1"]).all() and (req["q3"] == 0).all()
    assert (req["q1"] == req["q2"] + req["q3"]).all() and (req["q2"] == req["delivered"] + req["q5"]).all()
    ct = {"case": "b", "name": "R0", "req": req, "zero": F.zero_supply(run, req), "udp_runs": None,
          "market": CS.market_map(run), "allocation": False, "week_rule": "", "report_period": ("2027-W01", "2027-W04")}
    k = pd.DataFrame(F.key_rows(ct))
    r = k[k["region"] == "MK"].iloc[0]
    assert (r["q1"], r["q2"], r["q3"], r["on_time"], r["late"], r["delivered"], r["q5"]) == (4, 4, 0, 1, 1, 2, 2)
    assert (r["r21"], r["r41"], r["r42"]) == (1.0, 0.5, 0.5)
    # demand weeks W02, W03, W04; the market shipped in W02 and W04 -> W03 is the only zero week
    assert (r["zero_supply_weeks"], r["longest_zero_run"], r["longest_zero_run_from"]) == (1, 1, "2027-W03")
    assert k.iloc[-1]["market"] == "計" and k.iloc[-1]["q1"] == 4
    p = pd.DataFrame(F.period_rows(ct))
    y = p[p["period_kind"] == "year"].iloc[0]
    assert (y["period"], y["q1"], y["delivered"], y["r41"]) == ("2027", 4, 2, 0.5)
    assert set(p.loc[p["period_kind"] == "quarter", "period"]) == {"2027-Q1"}


def test_identity_mismatch_stops(tmp_path, monkeypatch):
    run = _r0(tmp_path)
    orig = CS.allocation_table

    def bad(sup, udp, name):
        t = orig(sup, None, name)
        t.loc[t.index[0], "q3_unallocated"] = 1                       # ① ≠ ② ＋ ③
        return t
    monkeypatch.setattr(CS, "allocation_table", bad)
    with pytest.raises(F.StopError, match="①＝②＋③"):
        F.request_table(run, None, "b")


def _keys(rows):
    base = {"case": "X", "case_name": "", "week_rule": "", "sku_id": "S", "market": "", "on_time": 0, "early": 0,
            "late": 0, "zero_supply_weeks": 0, "longest_zero_run": 0, "longest_zero_run_from": "", "zero_check": ""}
    out = []
    for reg, q1, q2, d in rows:
        out.append({**base, "region": reg, "q1": q1, "q2": q2, "q3": q1 - q2, "delivered": d, "q5": q2 - d,
                    "r21": q2 / q1, "r41": d / q1, "r42": d / q2})
    return pd.DataFrame(out)


def test_rule_and_result_are_kept_apart():
    k = _keys([("JP", 300, 300, 295), ("FR", 151, 124, 120), ("BE", 100, 82, 50), ("NL", 100, 83, 60)])
    j = F.judge(k, "X", True, ["JP"], ["FR", "BE", "NL"], {"JP": 295})
    # ②÷①: FR 82.12 %, BE 82 %, NL 83 % -> the spread 1 % is within one lot of the smallest key (1/100)
    assert j["rule_ok"] == "合う" and "保護 JP の ② ＝ ① ○" in j["rule"]
    assert j["result_ok"] == F.UNJUDGED and "最小 BE 50.00%" in j["result"]
    assert "JP の ④ 295 ≥ 295（暫定の条件、満たす）" in j["protect_min"]
    k2 = _keys([("JP", 300, 300, 290), ("FR", 151, 120, 120), ("BE", 100, 82, 50), ("NL", 100, 83, 60)])
    j2 = F.judge(k2, "X", True, ["JP"], ["FR", "BE", "NL"], {"JP": 295})
    assert j2["rule_ok"] == "合わない" and "満たさない" in j2["protect_min"]
    j3 = F.judge(k, "X", False, ["JP"], ["FR", "BE", "NL"], {})
    assert j3["rule"].startswith("配分なし") and j3["result_ok"] == F.UNJUDGED
