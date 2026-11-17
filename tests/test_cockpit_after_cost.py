# -*- coding: utf-8 -*-
"""wom/cockpit/after_cost.py and `tools.cockpit_cases after-cost`
(RequestLetter_Cockpit_AfterCost_ThreeCases §4): the weekly amount scenarios, full vs narrowed, the after-cost
profit by hand, the GPT-MC worked values (F3) and the CLI on a small synthetic workspace."""
import os

import pandas as pd
import pytest

from wom.cockpit import after_cost as AC
from wom.cockpit import cases as C

from test_cockpit_cases import _model, PLAN

SCEN = """scenario,level,premium_pct,weekly_amount_full,weekly_amount_narrowed,status,note
低・割増0%,低,0,10000,10000,仮置き,
低・割増15%,低,15,10000,11500,仮置き,
中・割増0%,中,0,40000,40000,仮置き,
中・割増15%,中,15,40000,46000,仮置き,
高・割増0%,高,0,132000,132000,仮置き,
高・割増15%,高,15,132000,151800,仮置き,
"""


def _scen(ws, text=SCEN):
    os.makedirs(os.path.join(ws, "inputs"), exist_ok=True)
    with open(AC.scenario_path(ws), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ── 週額の表 ───────────────────────────────────────────────────────────
def test_no_table_means_unset(tmp_path):
    assert AC.read_raise_scenarios(str(tmp_path)) is None
    facts = [{"case": "A", "P0": 100.0, "paid_start": "", "paid_end": "", "W": 0, "kind": AC.KIND_NONE,
              "B_report": 0.0, "B_warmup": 0.0},
             {"case": "B", "P0": 150.0, "paid_start": "2027-W01", "paid_end": "2027-W03", "W": 3,
              "kind": AC.KIND_FULL, "B_report": 0.0, "B_warmup": 0.0}]
    r = AC.after_cost_rows(None, facts, rates=(None,)).set_index("case")
    assert r.loc["A", "raise_cost"] == 0 and r.loc["A", "P_after"] == 100.0       # no raise: 0, not unset
    assert r.loc["B", "weekly_amount"] == AC.UNSET and r.loc["B", "P_after"] == AC.NOT_COMPUTED
    assert r.loc["B", "scenario"] == AC.NO_TABLE


@pytest.mark.parametrize("text,msg", [
    ("scenario,level,premium_pct,weekly_amount_full,status,note\nx,低,0,1,仮置き,\n", "列が足りません"),
    (SCEN.replace("10000,10000", "10000,", 1), "数ではない"),
    (SCEN.replace("10000,10000", "-1,10000", 1), "0 以上"),
    (SCEN + "中・割増0%,中,0,1,1,仮置き,\n", "重複"),
    (SCEN.splitlines()[0] + "\n", "行がありません"),
])
def test_bad_tables_stop(tmp_path, text, msg):
    _scen(str(tmp_path), text)
    with pytest.raises(AC.AfterCostError, match=msg):
        AC.read_raise_scenarios(str(tmp_path))


def test_full_and_narrowed_are_told_by_the_paid_range():
    assert AC.raise_kind("", "", "2026-W37", "2029-W52") == AC.KIND_NONE
    assert AC.raise_kind("2026-W37", "2029-W52", "2026-W37", "2029-W52") == AC.KIND_FULL
    assert AC.raise_kind("2028-W11", "2029-W46", "2026-W37", "2029-W52") == AC.KIND_NARROWED


# ── 控除後の利益 ────────────────────────────────────────────────────────
def test_after_cost_by_hand(tmp_path):
    _scen(str(tmp_path))
    scen = AC.read_raise_scenarios(str(tmp_path))
    facts = [{"case": "N", "P0": 1000.0, "paid_start": "", "paid_end": "", "W": 0, "kind": AC.KIND_NONE,
              "B_report": 5200.0, "B_warmup": 0.0},
             {"case": "R", "P0": 500_000.0, "paid_start": "2027-W01", "paid_end": "2027-W02", "W": 2,
              "kind": AC.KIND_NARROWED, "B_report": 10400.0, "B_warmup": 5200.0}]
    r = AC.after_cost_rows(scen, facts)
    x = r[(r["scenario"] == "中・割増15%") & (r["holding_rate_text"] == "10%")].set_index("case")
    # R: 2 weeks x 46,000 = 92,000; holding 0.10/52 x (10,400 + 5,200) = 30; 500,000 − 92,000 − 30
    assert x.loc["R", "raise_cost"] == 92_000.0
    assert abs(x.loc["R", "H_total"] - 30.0) < 1e-9 and abs(x.loc["R", "H_warmup"] - 10.0) < 1e-9
    assert abs(x.loc["R", "P_after"] - 407_970.0) < 1e-9
    assert abs(x.loc["N", "P_after"] - (1000.0 - 10.0)) < 1e-9                  # no raise: holding only
    assert abs(x.loc["R", "diff_vs_first"] - (407_970.0 - 990.0)) < 1e-9
    assert len(r) == 6 * 4 * 2 and set(r["holding_rate_text"]) == {"なし", "5%", "10%", "15%"}
    p = AC.pair_diffs(r, "N", "R")
    assert len(p) == 24 and abs(p[(p["scenario"] == "中・割増15%") & (p["holding_rate_text"] == "10%")]
                                 ["diff"].iloc[0] - 406_980.0) < 1e-9


def test_gpt_mc_worked_values_f3(tmp_path):
    """The estimate v0.1 (checked by Claude君): mid, 15 %, 10 % a year."""
    _scen(str(tmp_path))
    scen = AC.read_raise_scenarios(str(tmp_path))

    def f(cid, p0, ps, pe, w, kind, br, bw):
        return {"case": cid, "P0": p0, "paid_start": ps, "paid_end": pe, "W": w, "kind": kind,
                "B_report": br, "B_warmup": bw}
    now = [f("C01", 606_871_080.0, "", "", 0, AC.KIND_NONE, 2_956_507_296.0, 168_447_264.0),
           f("C02", 616_860_840.0, "2026-W37", "2029-W52", 173, AC.KIND_FULL, 3_005_080_896.0, 126_689_664.0),
           f("C03", 616_860_840.0, "2028-W11", "2029-W46", 88, AC.KIND_NARROWED, 3_089_407_296.0, 168_447_264.0)]
    strong = [f("C06", 618_336_600.0, "2026-W37", "2029-W52", 173, AC.KIND_FULL, 3_038_932_896.0, 133_023_264.0),
              f("C07", 618_336_600.0, "2027-W50", "2029-W46", 101, AC.KIND_NARROWED, 3_091_060_896.0, 168_447_264.0)]
    r = AC.after_cost_rows(scen, now).set_index(["scenario", "holding_rate_text", "case"])["P_after"]
    s = AC.after_cost_rows(scen, strong).set_index(["scenario", "holding_rate_text", "case"])["P_after"]
    m = ("中・割増15%", "10%")
    assert round(r[m + ("C03",)] - r[m + ("C01",)], 2) == 5_686_183.08
    assert round(r[m + ("C03",)] - r[m + ("C02",)], 2) == 2_629_530.77
    assert round(s[m + ("C07",)] - s[m + ("C06",)], 2) == 2_105_630.77
    lo, hi = ("低・割増15%", "10%"), ("高・割増15%", "10%")
    assert round(r[lo + ("C03",)] - r[lo + ("C01",)], 2) == round(8_977_760 - 255_576.923077, 2)
    assert round(r[hi + ("C03",)] - r[hi + ("C01",)], 2) == round(-3_368_640 - 255_576.923077, 2)


# ── CLI（案の実行の出力から） ─────────────────────────────────────────────
WEEKS = ["2027-W01", "2027-W02", "2027-W03", "2027-W04"]   # W01 = warm-up


def _fake_run(ws, cid, p0_per_week, inv_per_week, raise_range=None):
    cdir = C.case_dir(ws, cid)
    vc = os.path.join(cdir, "run", "vc")
    os.makedirs(vc, exist_ok=True)
    pd.DataFrame([{"group_key": "GROUP", "week_index": i, "week": w, "in_report": i >= 1,
                   "profit_r2_hq_wk": p0_per_week, "inv_group_hq": inv_per_week, "n_unvalued_wk": 0,
                   "lots_unvalued": 0} for i, w in enumerate(WEEKS)]).to_csv(
        os.path.join(vc, "vc_v3_weekly.csv"), index=False)
    pd.DataFrame([{"week_index": i, "week": w, "owner": "E", "location_kind": "node", "location": "Fac_A",
                   "product": "PA", "item": "finished", "valued": 1, "external": 0, "lots": 1,
                   "group_hq": inv_per_week} for i, w in enumerate(WEEKS)]
                 + [{"week_index": 1, "week": WEEKS[1], "owner": "X", "location_kind": "node", "location": "Shop_X",
                     "product": "PA", "item": "finished", "valued": 1, "external": 1, "lots": 9, "group_hq": 999.0}]
                 ).to_csv(os.path.join(vc, "vc_inventory_weekly.csv"), index=False)
    if raise_range:
        C.set_fixed_cost(ws, cid, rows=[{"cost_item": AC.RAISE_ITEM, "entity": "E", "paid_start_week": raise_range[0],
                                         "paid_end_week": raise_range[1], "weekly_amount": "", "currency": "JPY",
                                         "note": "", "count_outside_report": "1"}])
    case = C.read_case(ws, cid)
    case["run"] = {"state": C.ST_DONE, "input_hashes": C.input_hashes(ws, cid), "stages": [], "money_model": "model",
                   "summary": {"P0_report": 3 * p0_per_week}}
    C.write_case(ws, cid, case)


@pytest.fixture
def ws(tmp_path):
    src = _model(tmp_path)
    (tmp_path / "src_model" / "vc_entity.csv").write_text(
        "entity_id,entity_name,kind,functional_currency,consolidated\nE,本社,group,JPY,1\n"
        "X,代理店,external_channel,JPY,0\n", encoding="utf-8")
    w = str(tmp_path / "ws")
    C.create_workspace(w, src, max_age_weeks=52)
    plan = tmp_path / "plan.csv"
    plan.write_text(PLAN, encoding="utf-8", newline="\n")
    C.set_entry_plan(w, "C01", str(plan))
    C.copy_case(w, "C01", "全期間")
    C.copy_case(w, "C01", "絞った")
    _fake_run(w, "C01", 100.0, 520.0)
    _fake_run(w, "C02", 200.0, 1040.0, (WEEKS[0], WEEKS[-1]))
    _fake_run(w, "C03", 200.0, 1560.0, (WEEKS[2], WEEKS[3]))
    return w


def test_cli_writes_the_three_case_table(ws):
    from tools import cockpit_cases
    assert cockpit_cases.main(["after-cost", "--ws", ws, "--cases", "C01,C02,C03", "--name", "t"]) == 0
    d = os.path.join(ws, "after_cost", "t")
    t = pd.read_csv(os.path.join(d, "after_cost_table.csv"))
    assert (t["scenario"] == AC.NO_TABLE).all()                                    # no table yet: 未設定
    assert set(t.loc[t["case"] == "C02", "P_after"]) == {AC.NOT_COMPUTED}
    _scen(ws)
    assert cockpit_cases.main(["after-cost", "--ws", ws, "--cases", "C01,C02,C03", "--name", "t"]) == 0
    t = pd.read_csv(os.path.join(d, "after_cost_table.csv"))
    x = t[(t["scenario"] == "中・割増15%") & (t["holding_rate_text"] == "10%")].set_index("case")
    assert (x.loc["C02", "raise_kind"], x.loc["C02", "W"], x.loc["C02", "weekly_amount"]) == (AC.KIND_FULL, 4, 40000)
    assert (x.loc["C03", "raise_kind"], x.loc["C03", "W"], x.loc["C03", "weekly_amount"]) == (AC.KIND_NARROWED, 2, 46000)
    assert x.loc["C01", "P0"] == 300.0 and x.loc["C01", "raise_cost"] == 0
    # holding: group-owned only (the external 999 is left out); warm-up W01 apart from the report period
    assert abs(x.loc["C03", "H_warmup"] - 0.10 / 52 * 1560.0) < 1e-9
    assert abs(x.loc["C03", "H_report"] - 0.10 / 52 * 1560.0 * 3) < 1e-9
    assert abs(x.loc["C03", "P_after"] - (600.0 - 92_000.0 - 0.10 / 52 * 1560.0 * 4)) < 1e-6
    md = open(os.path.join(d, "after_cost_summary.md"), encoding="utf-8").read()
    assert "仮置き" in md and "1 個 600 円" in md and "C03 − C01" in md
    disclaimer = "（数字を並べただけ。どの案が良いかは書かない）"
    assert disclaimer in md
    for word in ("良い", "上回る", "推奨", "最も大きい"):
        assert word not in md.replace(disclaimer, "")


def test_cli_stops_on_a_case_not_done(ws):
    from tools import cockpit_cases
    C.copy_case(ws, "C01", "未実行")
    assert cockpit_cases.main(["after-cost", "--ws", ws, "--cases", "C01,C04"]) == 2
    assert cockpit_cases.main(["after-cost", "--ws", ws, "--cases", "C01"]) == 2
