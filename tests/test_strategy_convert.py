# -*- coding: utf-8 -*-
"""wom/strategy — converting a promotion measure sheet into cockpit cases
(RequestLetter_Promo_Convert_Slice1 §6; expected values: promotion business definition v0.1 §6・§2.2).

Unit: the integer rule (§6.1・§6.2・§6.3 small examples, Decimal), the yen conversion.
Unit/Integration: the converter on the cosmetics model and on a small synthetic model (idempotent, no carry-over,
other keys and other cost rows untouched, the stop conditions). No planning run here (the E2E is in the report)."""
import csv
import os
import shutil
from decimal import Decimal

import pytest

from wom.cockpit import cases as CC
from wom.strategy import StrategyError
from wom.strategy import convert as CV
from wom.strategy import rules as RU
from wom.strategy import sheets as SH

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COSMETICS = os.path.join(REPO, "data", "sample", "cosmetics-sg-th-2027-2029")
SHEETS = os.path.join(REPO, "tests", "data", "strategy_slice1")
D2 = {f"2028-W{w:02d}": Decimal(2) for w in range(1, 53)}


# ── 単体：整数化の規則 ─────────────────────────────────────────────────
EXPECTED_61 = {  # business definition §6.1: week -> (LOW, MID, HIGH) demand D
    9: (2, 2, 2), 10: (2, 2, 2), 11: (2, 2, 2), 12: (2, 2, 3), 13: (2, 3, 3), 14: (2, 2, 3), 15: (2, 3, 3),
    16: (2, 2, 3), 17: (2, 3, 3), 18: (2, 2, 3), 19: (2, 3, 3), 20: (2, 2, 3), 21: (2, 3, 3), 22: (2, 2, 3),
    23: (2, 3, 3), 24: (2, 2, 2), 25: (2, 2, 2), 26: (2, 2, 2), 27: (2, 2, 2), 28: (2, 2, 2)}


@pytest.mark.parametrize("i,rate,added", [(0, "0", 0), (1, "0.25", 6), (2, "0.50", 12)])
def test_weekly_table_and_totals_of_the_definition(i, rate, added):
    r = RU.demand_delta(D2, "2028-W10", "2028-W21", Decimal(rate), 2)
    D = {**D2, **RU.apply_delta(D2, r["d"])}
    for w, exp in EXPECTED_61.items():
        assert D[f"2028-W{w:02d}"] == exp[i], w
    assert r["response_weeks"][0] == "2028-W12" and r["response_weeks"][-1] == "2028-W23"
    assert len(r["response_weeks"]) == 12 and sum(r["d"].values()) == added
    assert r["intervals"][0]["residual"] == 0
    assert sum(D.values()) == 104 + added                         # §6.2: the 2028 demand 104 / 110 / 116
    assert sum(D[f"2028-W{w:02d}"] for w in range(10, 28)) == 36 + added   # local window W10..W27: 36 / 42 / 48


def test_negative_interval_and_net_with_mid():
    r = RU.demand_delta(D2, "2028-W12", "2028-W23", 0, 0, rebound_rate="0.25", rebound_weeks=4)
    assert [r["d"][f"2028-W{w}"] for w in range(24, 28)] == [0, -1, 0, -1]
    assert [D2[f"2028-W{w}"] + r["d"][f"2028-W{w}"] for w in range(24, 28)] == [2, 1, 2, 1]
    m = RU.demand_delta(D2, "2028-W10", "2028-W21", "0.25", 2, rebound_rate="0.25", rebound_weeks=4)
    assert sum(m["d"].values()) == 4                               # +6 - 2
    assert [iv["kind"] for iv in m["intervals"]] == ["response", "rebound"]


def test_residual_is_recorded_not_carried():
    r = RU.demand_delta(D2, "2028-W12", "2028-W14", "0.125", 0)
    assert [r["d"][w] for w in ("2028-W12", "2028-W13", "2028-W14")] == [0, 0, 0]
    assert r["intervals"][0]["residual"] == Decimal("0.75")
    assert set(r["d"]) == {"2028-W12", "2028-W13", "2028-W14"}     # nothing moved to later weeks


def test_reaction_week_base_is_multiplied():
    b = dict(D2, **{"2028-W12": Decimal(4)})
    r = RU.demand_delta(b, "2028-W10", "2028-W10", "0.5", 2)
    assert r["d"] == {"2028-W12": 2}                               # 4 x 50%, not the ad week's 2 x 50%


def test_negative_demand_stops():
    with pytest.raises(StrategyError, match="負になります"):
        RU.apply_delta(D2, {"2028-W10": -3})


def test_reaction_outside_the_plan_stops():
    with pytest.raises(StrategyError, match="計画の期間の外"):
        RU.demand_delta(D2, "2028-W45", "2028-W51", "0.25", 2)      # W47..2029-W01 (2028 has 52 ISO weeks)
    with pytest.raises(StrategyError, match="計画の期間の外"):
        RU.demand_delta(D2, "2028-W40", "2028-W48", 0, 0, rebound_rate="0.1", rebound_weeks=8)


def test_decimal_small_example_two_lots_five_percent_ten_weeks():
    r = RU.demand_delta(D2, "2028-W01", "2028-W10", "0.05", 0)
    assert sum(r["d"].values()) == 1 and r["d"]["2028-W10"] == 1
    # with floats the running sum stays just below 1 and the floor gives 0 (why Decimal is used)
    a = 0.0
    for _ in range(10):
        a += 2 * 0.05
    assert int(a // 1) == 0


def test_yen_conversion_and_rate_change_stops():
    weeks = RU.week_range("2028-W10", "2028-W21")
    fx = [{"week": "2026-W37", "currency": "SGD", "base_currency": "JPY", "rate": "115"}]
    rate = RU.fx_rate_for_weeks(fx, "SGD", "JPY", weeks)
    assert Decimal("200") * rate == 23000 and Decimal("200") * rate * len(weeks) == 276000   # 2,400 SGD
    fx2 = fx + [{"week": "2028-W15", "currency": "SGD", "base_currency": "JPY", "rate": "120"}]
    with pytest.raises(StrategyError, match="レートが 1 つではありません"):
        RU.fx_rate_for_weeks(fx2, "SGD", "JPY", weeks)
    with pytest.raises(StrategyError, match="以前のレートがありません"):
        RU.fx_rate_for_weeks([], "SGD", "JPY", weeks)


# ── 化粧品のモデルで変換（実行はしない）─────────────────────────────────
@pytest.fixture(scope="module")
def cos_ws(tmp_path_factory):
    ws = str(tmp_path_factory.mktemp("cos") / "ws")
    CC.create_workspace(ws, COSMETICS, max_age_weeks=52, first_name="P_BASE")
    for n in ("P_PROMO_LOW", "P_PROMO_MID", "P_PROMO_HIGH", "MID_THEN_HIGH"):
        CC.copy_case(ws, "C01", n)
    return ws


def _demand(ws, cid):
    with open(os.path.join(ws, cid, "model", "demand_forecast.csv"), encoding="utf-8-sig", newline="") as f:
        return {(r["sku_id"], r["region"], r["week"]): r["quantity"] for r in csv.DictReader(f)}


def test_cosmetics_four_plans(cos_ws):
    ws = cos_ws
    base = _demand(ws, "C01")
    res = {}
    for cid, plan in (("C01", "P_BASE"), ("C02", "P_PROMO_LOW"), ("C03", "P_PROMO_MID"), ("C04", "P_PROMO_HIGH")):
        res[cid] = CV.convert(ws, cid, plan, SHEETS, COSMETICS)
        assert res[cid]["state"] == "変換した"
    key = ("COS_Cream", "SG_EC")
    for cid, i, add in (("C02", 0, 0), ("C03", 1, 6), ("C04", 2, 12)):
        d = _demand(ws, cid)
        for w, exp in EXPECTED_61.items():
            assert int(d[key + (f"2028-W{w:02d}",)]) == exp[i]
        assert sum(int(v) for k, v in d.items() if k[:2] == key and k[2].startswith("2028")) == 104 + add
        assert sum(int(v) for k, v in d.items() if k[:2] == key and "2027-W01" <= k[2] <= "2029-W52") == 299 + add
        other = [k for k in d if k[:2] != key and d[k] != base[k]]
        assert not other                                          # other keys' inputs are the same
        with open(os.path.join(ws, cid, "inputs", "fixed_cost.csv"), encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1 and rows[0]["weekly_amount"] == "23000" and rows[0]["currency"] == "JPY"
        assert (rows[0]["paid_start_week"], rows[0]["paid_end_week"], rows[0]["entity"]) == ("2028-W10", "2028-W21", "E_SG")
        assert "measure=CMP_CREAM_SGEC_2028_COST; version=v01" in rows[0]["note"] and "200 SGD" in rows[0]["note"]
        assert any(c["what"] == "strategy_convert" and c["plan_id"] for c in CC.read_case(ws, cid)["changes"])
    assert _demand(ws, "C01") == base                              # P_BASE: no change, no cost premises
    assert CC.read_case(ws, "C01")["inputs"]["fixed_cost"] is None
    # the change log: traceability columns, the residual row, one cost row
    with open(os.path.join(ws, "C03", "inputs", CV.LOG_FILE), encoding="utf-8") as f:
        log = list(csv.DictReader(f))
    assert list(log[0]) == CV.LOG_COLS
    assert {r["base_demand_sha256"] for r in log} == {SH.sha256_file(os.path.join(COSMETICS, "demand_forecast.csv"))}
    assert {r["env_id"] for r in log} == {"ENV_BASE_v01"} and all(r["catalog_version"].startswith("v0.1") for r in log)
    assert [r["after"] for r in log if r["rule"] == "residual"] == ["0"]
    assert sum(int(r["after"]) - int(r["before"]) for r in log if r["column"] == "quantity" and r["rule"] != "residual") == 6
    assert [r["after"] for r in log if r["rule"] == "promo_external_cost"] == ["23000"]
    # idempotent: again -> 変更なし, same files
    snap = {c: (_demand(ws, c), open(os.path.join(ws, c, "inputs", CV.LOG_FILE), encoding="utf-8").read())
            for c in ("C02", "C03", "C04")}
    for cid, plan in (("C02", "P_PROMO_LOW"), ("C03", "P_PROMO_MID"), ("C04", "P_PROMO_HIGH")):
        assert CV.convert(ws, cid, plan, SHEETS, COSMETICS)["state"] == "変更なし"
        assert (_demand(ws, cid), open(os.path.join(ws, cid, "inputs", CV.LOG_FILE), encoding="utf-8").read()) == snap[cid]


def test_another_level_does_not_inherit(cos_ws):
    ws = cos_ws
    CV.convert(ws, "C05", "P_PROMO_MID", SHEETS, COSMETICS)
    CV.convert(ws, "C05", "P_PROMO_HIGH", SHEETS, COSMETICS)
    CV.convert(ws, "C04", "P_PROMO_HIGH", SHEETS, COSMETICS)      # a fresh HIGH (or 変更なし if already done)
    assert _demand(ws, "C05") == _demand(ws, "C04")              # rebuilt from the frozen base, MID not carried
    with open(os.path.join(ws, "C05", "inputs", CV.LOG_FILE), encoding="utf-8") as f:
        log = list(csv.DictReader(f))
    assert {r["level"] for r in log} == {"high"}                   # the log is the HIGH conversion only


def test_dry_run_writes_nothing(tmp_path):
    ws = str(tmp_path / "ws")
    CC.create_workspace(ws, COSMETICS, max_age_weeks=52)
    CC.copy_case(ws, "C01", "x")
    before = _demand(ws, "C02")
    pc = CV.convert(ws, "C02", "P_PROMO_HIGH", SHEETS, COSMETICS, dry_run=True)
    assert pc["state"].startswith("書かない") and "promo_external_cost" in pc["log_text"]
    assert _demand(ws, "C02") == before
    assert not os.path.exists(os.path.join(ws, "C02", "inputs", CV.LOG_FILE))
    assert CC.read_case(ws, "C02")["inputs"]["fixed_cost"] is None


# ── 小さなモデル：費用の前提・キャンペーン・止める条件 ─────────────────────
def _w(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(header)
        wr.writerows(rows)


def make_model(root, fx_change=False):
    m = os.path.join(root, "model")
    os.makedirs(m)
    weeks = [f"2028-W{w:02d}" for w in range(1, 31)]
    _w(os.path.join(m, "demand_forecast.csv"), ["sku_id", "region", "week", "quantity"],
       [[s, r, w, 2] for s, r in (("P", "MK"), ("P", "OT")) for w in weeks])
    _w(os.path.join(m, "sc_tree_master.csv"), ["node_name", "parent_node", "product_name", "node_type", "region"],
       [["DC", "", "P", "dad", ""], ["MK", "DC", "P", "leaf_out", "MK"], ["OT", "DC", "P", "leaf_out", "OT"]])
    _w(os.path.join(m, "ppc_market_price.csv"), ["market_node", "product_id", "week", "market_price", "currency"],
       [["MK", "P", "2028-W01", 10, "SGD"], ["OT", "P", "2028-W01", 10, "SGD"]])
    fx = [["2028-W01", "SGD", "JPY", 100]] + ([["2028-W06", "SGD", "JPY", 110]] if fx_change else [])
    _w(os.path.join(m, "ppc_fx_rate.csv"), ["week", "currency", "base_currency", "rate"], fx)
    _w(os.path.join(m, "vc_config.csv"), ["key", "value"], [["hq_currency", "JPY"], ["report_start", "2028-W01"]])
    _w(os.path.join(m, "vc_node_assignment.csv"), ["node_id", "product_id", "entity_id"],
       [["MK", "P", "E_SG"], ["OT", "P", "E_SG"]])
    return m


MEAS_H = SH.MEASURE_COLS


def make_sheets(root, measures=None, hyps=None, plans=None, envs=None):
    s = os.path.join(root, "sheets")
    os.makedirs(s, exist_ok=True)
    measures = measures if measures is not None else [
        ["CMP", "CMP_D", "v01", "Promotion", "promo_demand_delta", "P", "MK", "2028-W03", "2028-W08", "", "", "", "", "",
         "H", "r"],
        ["CMP", "CMP_C", "v01", "Promotion", "promo_external_cost", "P", "MK", "2028-W03", "2028-W08", "200",
         "amount_per_week", "SGD", "E_SG", "promo_add", "", "r"]]
    _w(os.path.join(s, "measures.csv"), MEAS_H, measures)
    _w(os.path.join(s, "hypotheses.csv"), SH.HYPOTHESIS_COLS, hyps if hyps is not None else
       [["H", "v01", "base", "promotion_response", "0.5", "2", "0", "0", "validation_placeholder", "test"]])
    _w(os.path.join(s, "external_conditions.csv"), SH.ENV_COLS, envs if envs is not None else [["ENV", "v01", "base"]])
    _w(os.path.join(s, "plans.csv"), SH.PLAN_COLS, plans if plans is not None else
       [["P0", "none", "", "", "ENV"], ["P1", "promo", "CMP", "base", "ENV"]])
    return s


@pytest.fixture
def small(tmp_path):
    m = make_model(str(tmp_path))
    ws = str(tmp_path / "ws")
    CC.create_workspace(ws, m, max_age_weeks=52)
    CC.copy_case(ws, "C01", "promo")
    return {"root": str(tmp_path), "model": m, "ws": ws, "sheets": make_sheets(str(tmp_path))}


def _fc(ws, cid):
    with open(os.path.join(ws, cid, "inputs", "fixed_cost.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_cost_premises_keep_other_rows_and_rerun_rules(small):
    ws, s, m = small["ws"], small["sheets"], small["model"]
    CC.set_fixed_cost(ws, "C02", rows=[{"cost_item": "wh_fee", "entity": "E_JP", "paid_start_week": "2028-W01",
                                        "paid_end_week": "2028-W30", "weekly_amount": "5", "currency": "JPY",
                                        "note": "既存"}])
    assert CV.convert(ws, "C02", "P1", s, m)["state"] == "変換した"
    rows = {r["cost_item"]: r for r in _fc(ws, "C02")}
    assert set(rows) == {"wh_fee", "promo_add"} and rows["wh_fee"]["weekly_amount"] == "5"
    assert rows["promo_add"]["weekly_amount"] == "20000"            # 200 SGD x 100
    assert CV.convert(ws, "C02", "P1", s, m)["state"] == "変更なし"
    # content differs for the same measure and version -> stop
    p = os.path.join(ws, "C02", "inputs", "fixed_cost.csv")
    txt = open(p, encoding="utf-8").read().replace(",20000,", ",21000,")
    open(p, "w", encoding="utf-8", newline="").write(txt)
    with pytest.raises(StrategyError, match="中身が違います"):
        CV.convert(ws, "C02", "P1", s, m)


def test_cost_item_used_by_another_source_stops(small):
    ws, s, m = small["ws"], small["sheets"], small["model"]
    CC.set_fixed_cost(ws, "C02", rows=[{"cost_item": "promo_add", "entity": "E_SG", "paid_start_week": "2028-W01",
                                        "paid_end_week": "2028-W02", "weekly_amount": "1", "currency": "JPY",
                                        "note": "手で書いた行"}])
    with pytest.raises(StrategyError, match="別の出どころ"):
        CV.convert(ws, "C02", "P1", s, m)


def test_converted_cost_row_left_by_another_plan_stops(small):
    ws, s, m = small["ws"], small["sheets"], small["model"]
    CV.convert(ws, "C02", "P1", s, m)
    shutil.copyfile(os.path.join(small["model"], "demand_forecast.csv"),
                    os.path.join(ws, "C02", "model", "demand_forecast.csv"))
    with pytest.raises(StrategyError, match="この案（P0）に無い施策"):
        CV.convert(ws, "C02", "P0", s, m)


@pytest.mark.parametrize("measures,match", [
    ([["CMP", "CMP_D", "v01", "Promotion", "promo_demand_delta", "P", "MK", "2028-W03", "2028-W08", "", "", "", "", "",
       "H", "r"]], "1 つずつ要ります"),
    ([["CMP", "CMP_C", "v01", "Promotion", "promo_external_cost", "P", "MK", "2028-W03", "2028-W08", "200",
       "amount_per_week", "SGD", "E_SG", "promo_add", "", "r"]], "1 つずつ要ります"),
    ([["CMP", "CMP_D", "v01", "Promotion", "promo_demand_delta", "P", "MK", "2028-W03", "2028-W08", "", "", "", "", "",
       "H", "r"],
      ["CMP", "CMP_C", "v01", "Promotion", "promo_external_cost", "P", "OT", "2028-W03", "2028-W08", "200",
       "amount_per_week", "SGD", "E_SG", "promo_add", "", "r"]], "market が違います"),
    ([["CMP", "CMP_D", "v01", "Promotion", "promo_demand_delta", "P", "MK", "2028-W03", "2028-W08", "", "", "", "", "",
       "H", "r"],
      ["CMP", "CMP_C", "v01", "Promotion", "promo_external_cost", "P", "MK", "2028-W04", "2028-W08", "200",
       "amount_per_week", "SGD", "E_SG", "promo_add", "", "r"]], "start_week が違います"),
])
def test_campaign_must_have_matching_demand_and_cost(small, measures, match):
    s = make_sheets(small["root"], measures=measures)
    with pytest.raises(StrategyError, match=match):
        CV.convert(small["ws"], "C02", "P1", s, small["model"])
    assert not os.path.exists(os.path.join(small["ws"], "C02", "inputs", CV.LOG_FILE))


def test_sheet_stops(small, tmp_path):
    ws, m = small["ws"], small["model"]
    s = make_sheets(small["root"])
    _w(os.path.join(s, "plans.csv"), ["plan_id", "case_name", "campaign_ids", "env_id"], [["P1", "x", "CMP", "ENV"]])
    with pytest.raises(StrategyError, match="列が足りません"):
        CV.convert(ws, "C02", "P1", s, m)
    bad = [["CMP", "CMP_D", "v01", "Promotion", "promo_magic", "P", "MK", "2028-W03", "2028-W08", "", "", "", "", "",
            "H", "r"]]
    with pytest.raises(StrategyError, match="知らない型"):
        CV.convert(ws, "C02", "P1", make_sheets(small["root"], measures=bad), m)
    cat = str(tmp_path / "cat.csv")
    shutil.copyfile(SH.CATALOG_FILE, cat)
    with open(cat, "a", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerow(["promo_period_budget", "Promotion", "", "", "", "×", "", "表せない"])
    bad[0][4] = "promo_period_budget"
    with pytest.raises(StrategyError, match="（×）型"):
        CV.convert(ws, "C02", "P1", make_sheets(small["root"], measures=bad), m, catalog_path=cat)
    unres = [["CMP", "CMP_D", "v01", "Promotion", "promo_demand_delta", "P", "NOWHERE", "2028-W03", "2028-W08", "", "",
              "", "", "", "H", "r"],
             ["CMP", "CMP_C", "v01", "Promotion", "promo_external_cost", "P", "NOWHERE", "2028-W03", "2028-W08", "200",
              "amount_per_week", "SGD", "E_SG", "promo_add", "", "r"]]
    with pytest.raises(StrategyError, match="leaf_out で 1 つに解決できません"):
        CV.convert(ws, "C02", "P1", make_sheets(small["root"], measures=unres), m)
    with pytest.raises(StrategyError, match="水準 base が hypotheses.csv にありません"):
        CV.convert(ws, "C02", "P1", make_sheets(small["root"], hyps=[["H", "v01", "low", "promotion_response", "0", "2",
                                                                        "0", "0", "validation_placeholder", "t"]]), m)
    with pytest.raises(StrategyError, match="evidence が空欄"):
        CV.convert(ws, "C02", "P1", make_sheets(small["root"], hyps=[["H", "v01", "base", "promotion_response", "0.5",
                                                                        "2", "0", "0", "validation_placeholder", ""]]), m)


def test_entry_plan_and_base_drift_and_rate_change_stop(small, tmp_path):
    ws, s, m = small["ws"], small["sheets"], small["model"]
    ep = os.path.join(ws, "C02", "model", "market_entry_plan.csv")
    open(ep, "w").write("sku_id,region\n")
    with pytest.raises(StrategyError, match="market_entry_plan.csv"):
        CV.convert(ws, "C02", "P1", s, m)
    os.remove(ep)
    p = os.path.join(ws, "C02", "model", "demand_forecast.csv")
    txt = open(p, encoding="utf-8").read().replace("P,OT,2028-W20,2", "P,OT,2028-W20,5")
    open(p, "w", encoding="utf-8", newline="").write(txt)
    with pytest.raises(StrategyError, match="基準がずれています"):
        CV.convert(ws, "C02", "P1", s, m)
    m2 = make_model(str(tmp_path / "fxc"), fx_change=True)
    ws2 = str(tmp_path / "ws2")
    CC.create_workspace(ws2, m2, max_age_weeks=52)
    with pytest.raises(StrategyError, match="レートが 1 つではありません"):
        CV.convert(ws2, "C01", "P1", s, m2)
    with pytest.raises(StrategyError, match="作業の元のモデル"):
        CV.convert(ws2, "C01", "P1", s, m)


def test_negative_demand_from_rebound_stops_before_writing(small):
    hyps = [["H", "v01", "base", "promotion_response", "0", "2", "1.5", "2", "validation_placeholder", "t"]]
    s = make_sheets(small["root"], hyps=hyps)
    before = open(os.path.join(small["ws"], "C02", "model", "demand_forecast.csv"), encoding="utf-8").read()
    with pytest.raises(StrategyError, match="負になります"):
        CV.convert(small["ws"], "C02", "P1", s, small["model"])
    assert open(os.path.join(small["ws"], "C02", "model", "demand_forecast.csv"), encoding="utf-8").read() == before
