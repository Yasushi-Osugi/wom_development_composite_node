# -*- coding: utf-8 -*-
"""wom/cockpit/compare_view_model.py and the screen (RequestLetter_Cockpit_Stage3_Step2 §5), on a small synthetic
workspace and synthetic tool-2 outputs."""
import json
import os
import time

import pandas as pd
import pytest

from wom.cockpit import cases as C
from wom.cockpit import compare_view_model as V

from test_cockpit_cases import _model, PLAN

WEEKS = ["2027-W01", "2027-W02", "2027-W03"]


def _done(ws, cid, p0, deliveries=None, udp_dir=None):
    case = C.read_case(ws, cid)
    case["run"] = {"state": C.ST_DONE, "input_hashes": C.input_hashes(ws, cid), "stages": [], "money_model": "model",
                   "udp_dir": udp_dir,
                   "summary": {"P0_report": p0, "deliveries_by_sku": deliveries or {"PA": 10},
                               "backlog_end_by_key": {"PA:X": 2}, "unallocated_by_key": None,
                               "unvalued_consolidated_lines": 0}}
    C.write_case(ws, cid, case)


def _compare_dir(ws, base, alt, fixed_cost_rows):
    d = os.path.join(ws, "compare", f"{base}__{alt}")
    os.makedirs(d, exist_ok=True)
    rows = []
    for w in WEEKS:
        for reg in ("X", "Y"):
            rows.append({"sku_id": "PA", "region": reg, "request_week": w, "demand_base": 2, "on_time_base": 1,
                         "early_base": 0, "late_base": 1 if reg == "X" else 0, "backlog_end_base": 0 if reg == "X" else 1,
                         "demand_alt": 2, "on_time_alt": 2, "early_alt": 0, "late_alt": 0, "backlog_end_alt": 0})
    pd.DataFrame(rows).to_csv(os.path.join(d, "supply_by_request_week.csv"), index=False)
    fw = []
    for c in (base, alt):
        for i, w in enumerate(WEEKS):
            fw.append({"case": c, "product": "PA", "week_index": i, "week": w, "production_lots": 8, "max_supply": 10,
                       "cap_soft": 8, "yield_rate": 1.0, "shippable_hard": 10, "shippable_soft": 8})
    pd.DataFrame(fw).to_csv(os.path.join(d, "factory_weekly.csv"), index=False)
    pd.DataFrame([{"week_index": i, "week": w, "product": "PA", "lots_base": 3, "group_hq_base": 1.0, "lots_alt": 4,
                   "group_hq_alt": 1.0, "lots_diff": 1, "group_hq_diff": 0.0} for i, w in enumerate(WEEKS)]).to_csv(
        os.path.join(d, "inventory_by_week_sku.csv"), index=False)
    pd.DataFrame([{"case": c, "product": "PA", "channel": "*", "deliveries": 6, "fifo_age_min": 1, "fifo_age_max": 3,
                   "over_max_age": 0} for c in (base, alt)]).to_csv(os.path.join(d, "age_summary.csv"), index=False)
    pd.DataFrame(columns=["case", "product", "week_index", "week", "production_lots", "shippable_soft",
                          "unused_vs_soft"]).to_csv(os.path.join(d, "factory_idle_weeks.csv"), index=False)
    pd.DataFrame([{"period": p, "product": prod, "profit_r2_base": v, "profit_r2_alt": v + 50,
                   "profit_r2_diff": 50} for p in ("report", "full") for prod, v in (("*", 100.0), ("PA", 100.0))]).to_csv(
        os.path.join(d, "money_totals.csv"), index=False)
    pd.DataFrame([{"week_index": i, "week": w, "product": "PA", "in_report": True, "profit_r2_base": 30.0,
                   "profit_r2_alt": 40.0} for i, w in enumerate(WEEKS)]).to_csv(
        os.path.join(d, "money_by_week_sku.csv"), index=False)
    pd.DataFrame(fixed_cost_rows).to_csv(os.path.join(d, "fixed_cost_breakeven.csv"), index=False)
    json.dump({"base": base, "alt": alt, "state": C.ST_DONE, "P0_base": 100.0, "P0_alt": 150.0, "delta_P0": 50.0,
               "base_input_hashes": C.read_case(ws, base)["run"]["input_hashes"],
               "alt_input_hashes": C.read_case(ws, alt)["run"]["input_hashes"], "fixed_cost": [],
               "base_fixed_cost_sha256": C.fixed_cost_hash(ws, base), "alt_fixed_cost_sha256": C.fixed_cost_hash(ws, alt)},
              open(os.path.join(d, "compare.json"), "w", encoding="utf-8"))
    return d


FC = [{"cost_item": "fee", "P0_base": 100.0, "P0_alt": 150.0, "paid_start_base": "2027-W02", "paid_end_base": "2027-W03",
       "W_base": 2, "paid_start_alt": "2027-W01", "paid_end_alt": "2027-W03", "W_alt": 3, "weekly_amount_base": "",
       "weekly_amount_alt": "", "cost_base": "", "cost_alt": "", "P_after_base": "", "P_after_alt": "",
       "delta_P0": 50.0, "delta_W": 1, "boundary": "f*", "f_star_per_week": 50.0, "boundary_assumption": "",
       "delta_P_after": "", "valuation_status": "評価済み"},
      {"cost_item": "raise", "P0_base": 100.0, "P0_alt": 150.0, "paid_start_base": "", "paid_end_base": "",
       "W_base": 0, "paid_start_alt": "2027-W01", "paid_end_alt": "2027-W03", "W_alt": 3,
       "weekly_amount_base": "対象外", "weekly_amount_alt": "", "cost_base": 0, "cost_alt": "", "P_after_base": 100.0,
       "P_after_alt": "", "delta_P0": 50.0, "delta_W": 3, "boundary": "f*", "f_star_per_week": 16.67,
       "boundary_assumption": "ほかの未設定の費用（fee）の案間の差を 0 と置いた場合", "delta_P_after": "",
       "valuation_status": "評価済み"},
      {"cost_item": "合計", "P0_base": 100.0, "P0_alt": 150.0, "cost_base": "未算出", "cost_alt": "未算出",
       "P_after_base": "未算出", "P_after_alt": "未算出", "delta_P0": 50.0, "delta_P_after": "未算出",
       "boundary": "合計", "valuation_status": "評価済み", "note": "保留"}]


@pytest.fixture
def ws(tmp_path):
    src = _model(tmp_path)
    w = str(tmp_path / "ws")
    C.create_workspace(w, src, max_age_weeks=52, first_name="late")
    plan = tmp_path / "plan.csv"
    plan.write_text(PLAN, encoding="utf-8", newline="\n")
    C.set_entry_plan(w, "C01", str(plan))
    C.copy_case(w, "C01", "early")
    C.set_launch_week(w, "C02", "PA", "Y", "2027-W01")
    C.copy_case(w, "C01", "stopped")
    _done(w, "C01", 100.0)
    _done(w, "C02", 150.0)
    case = C.read_case(w, "C03")
    case["run"] = {"state": C.ST_CONFLICT, "input_hashes": C.input_hashes(w, "C03"), "stages": [],
                   "reason": "数量配分 の段で止まった", "message": "置けない 3 lot"}
    C.write_case(w, "C03", case)
    _compare_dir(w, "C01", "C02", FC)
    return w


def test_case_table_varying_columns_and_results(ws):
    t = V.case_table(ws)
    assert "投入 PA:Y" in t["columns"] and "投入 PA:X" not in t["columns"]     # only the inputs that differ
    rows = {r["id"]: r for r in t["rows"]}
    assert rows["C01"]["show_result"] and rows["C01"]["cells"][t["columns"].index("P0（円、報告期間）")] == "100"
    assert not rows["C03"]["show_result"] and rows["C03"]["cells"][-1] == C.ST_CONFLICT
    assert rows["C03"]["cells"][t["columns"].index("P0（円、報告期間）")] == ""


def test_changed_inputs_show_rerun_and_no_numbers(ws):
    C.set_planned_output(ws, "C01", "PA", 9)
    t = V.case_table(ws)
    r = [x for x in t["rows"] if x["id"] == "C01"][0]
    assert r["cells"][-1] == V.RERUN and not r["show_result"]
    assert r["cells"][t["columns"].index("P0（円、報告期間）")] == ""
    cmp = V.comparison(ws, "C01", "C02")
    assert not cmp["available"] and cmp["state"] == C.ST_CHANGED and "supply" not in cmp
    notes = "\n".join(V.notes(ws, "C01", "C02"))
    assert V.RERUN in notes and "model/capacity_plan.csv" in notes and "数字は出さない" in notes
    C.set_planned_output(ws, "C01", "PA", 8)
    assert V.comparison(ws, "C01", "C02")["available"]


def test_comparison_not_run_and_inconsistent(ws):
    assert V.comparison(ws, "C02", "C01")["state"] == C.ST_NOT_RUN
    d = os.path.join(ws, "compare", "C01__C03")
    os.makedirs(d)
    json.dump({"state": C.ST_INCONSISTENT, "message": "道具 2：合わない"}, open(os.path.join(d, "compare.json"), "w",
                                                                              encoding="utf-8"))
    c = V.comparison(ws, "C01", "C03")
    assert not c["available"] and c["reason"] == "道具 2：合わない"


def test_unset_is_not_zero_and_ranking_is_pending(ws):
    mv = V.comparison(ws, "C01", "C02")["money"]
    tot, fee, rs = mv["fixed_cost"]                                         # the 合計 row on top
    assert (fee["weekly_amount_base"], fee["cost_base"], fee["P_after_base"]) == (V.UNSET, V.UNSET, "")
    assert fee["delta_P_after"] == "" and tot["P_after_base"] == "未算出"     # after-cost only on the 合計 row
    assert (rs["weekly_amount_base"], rs["cost_base"]) == (V.NOT_APPLICABLE, 0)            # not borne: 0, not 未設定
    assert rs["weekly_amount_alt"] == V.UNSET
    assert tot["cost_base"] == "未算出"
    assert mv["unset_costs"] == ["fee", "raise"] and mv["ranking"] == V.PENDING
    notes = "\n".join(V.notes(ws, "C01", "C02"))
    assert "未設定" in notes and "保留" in notes and "画面は言わない" in notes and "在庫の保管費" in notes


def test_supply_totals_and_min_supply_marks(ws):
    sv = V.comparison(ws, "C01", "C02")["supply"]
    t = sv["totals"].set_index(["case", "region"])
    assert t.loc[("C01", "X"), "late"] == 3 and t.loc[("C01", "Y"), "backlog"] == 3
    assert t.loc[("C02", "X"), "on_time"] == 6 and not sv["allocation"]
    # a policy case: the udp output marks the weeks where the supply in scope equals the minimum
    u = os.path.join(ws, "C02", "udp", "out", "x")
    os.makedirs(u)
    pd.DataFrame([{"source_demand_ref": "PA|X|2027-W02", "min_supply_lots": 2, "q2": 2, "on_time": 2,
                   "plan_ok": True, "delivered_ok": True},
                  {"source_demand_ref": "PA|Y|2027-W02", "min_supply_lots": 1, "q2": 2, "on_time": 2,
                   "plan_ok": True, "delivered_ok": True}]).to_csv(os.path.join(u, "udp_min_supply_check.csv"), index=False)
    pd.DataFrame([{"source_demand_ref": "PA|X|2027-W02", "q1": 3, "q2": 2, "q3": 1}]).to_csv(
        os.path.join(u, "udp_selection_ledger.csv"), index=False)
    case = C.read_case(ws, "C02")
    case["run"]["udp_dir"] = "udp/out/x"
    C.write_case(ws, "C02", case)
    sv = V.comparison(ws, "C01", "C02")["supply"]
    t = sv["totals"].set_index(["case", "region"])
    assert t.loc[("C02", "X"), "min_supply_exact_weeks"] == 1 and t.loc[("C02", "X"), "cut_to_minimum_weeks"] == 1
    assert t.loc[("C02", "Y"), "min_supply_exact_weeks"] == 0


def test_inputs_text(ws):
    d = V.case_inputs(ws, "C02")
    assert d["entry_plan"][1]["launch_week"] == "2027-W01" and "実行し直す" in d["note"]
    assert d["capacity"][0]["cap_soft"] == "8"


def test_view_model_does_not_write(ws):
    before = {os.path.join(r, f): os.path.getmtime(os.path.join(r, f)) for r, _d, fs in os.walk(ws) for f in fs}
    V.case_table(ws)
    V.comparison(ws, "C01", "C02")
    V.notes(ws, "C01", "C02")
    after = {os.path.join(r, f): os.path.getmtime(os.path.join(r, f)) for r, _d, fs in os.walk(ws) for f in fs}
    assert before == after


# ── the screen (a window is made and closed; skipped without a display) ──
def _tk_root():
    import tkinter as tk
    for _ in range(5):
        try:
            r = tk.Tk()
            r.geometry("1400x900+-3000+-3000")
            return r
        except tk.TclError:
            time.sleep(0.2)
    return None


def test_screen_opens_and_shows_the_tables(ws):
    root = _tk_root()
    if root is None:
        pytest.skip("no display available for tkinter")
    try:
        from wom.cockpit.compare_screen import CompareScreen
        s = CompareScreen(root, ws, "C01", "C02")
        root.update()
        t = s.displayed_tables()
        assert list(t["cases"]["role"]) == ["◎", "○", ""]
        assert len(t["supply_totals"]) == 4 and len(t["money_fixed_cost"]) == 3
        assert t["money_fixed_cost"].iloc[0]["費目"] == "合計"
        assert t["money_fixed_cost"].iloc[1]["週額 基準（C01）"] == V.UNSET
        s.reopen()
        root.update()
        assert s.displayed_tables()["money_fixed_cost"].equals(t["money_fixed_cost"])
        s.base = "C03"
        s._fill_case_table()
        s._show_comparison()
        root.update()
        assert len(s.displayed_tables()["money_fixed_cost"]) == 0             # no numbers for a pair not compared
    finally:
        root.destroy()



# ── 段 3 A：見出し・表示名・要点・差の表・④ の但し書き ────────────────────────
def _named_cost(ws, cid, start, amount=""):
    C.set_fixed_cost(ws, cid, rows=[{"cost_item": "fee", "display_name": "販路費", "entity": "E", "paid_start_week": start,
                                     "paid_end_week": "2027-W03", "weekly_amount": amount, "currency": "JPY", "note": ""}])


def test_summary_paragraphs_and_no_judgement_words(ws):
    c = V.comparison(ws, "C01", "C02")
    titles = [p["title"] for p in c["summary"]]
    assert titles == ["違い", "工場", "供給", "お金", "判断に要るもの"]
    text = "\n".join(p["text"] for p in c["summary"])
    assert "PA:Y の投入週（基準 2027-W03、相手 2027-W01）" in text
    assert "差 50 円" in text                                             # money_totals report diff
    for w in ("良い", "推奨", "有利"):
        assert w not in text


def test_supply_diff_only_keys_with_a_difference(ws):
    sd = V.comparison(ws, "C01", "C02")["supply_diff"]
    assert set(zip(sd["sku_id"], sd["region"])) == {("PA", "X"), ("PA", "Y")}
    x = sd.set_index("region").loc["X"]
    assert (x["late"], x["on_time"], x["backlog"]) == (-3, 3, 0)
    sv = V.comparison(ws, "C01", "C02")["supply"]
    t = sv["totals"].copy()
    t.loc[t["side"] == "alt", V.SUPPLY_KEYS] = t.loc[t["side"] == "base", V.SUPPLY_KEYS].values
    assert V.supply_diff(dict(sv, totals=t), "C01", "C02").empty         # no difference -> 供給の差なし


def test_common_shortage_and_storage_note(ws):
    c = V.comparison(ws, "C01", "C02")
    t = c["supply"]["totals"]
    t.loc[(t["side"] == "alt") & (t["region"] == "Y"), "backlog"] = 3      # the same backlog in both cases
    assert any("PA:Y の配分後の未充足 3 lot は 2 案に共通" in x for x in V.common_shortages(c["supply"]))
    notes = "\n".join(V.notes(ws, "C01", "C02", c))
    assert "在庫の保管費は金額に入っていない" in notes and "PA 9 → 12" in notes
    assert "計画の端の週（計画の最初の 1 週と最後の 4 週）" in notes


def test_policy_short_name():
    assert V.policy_short(None) == "なし"
    assert V.policy_short({"week_rule": "trim_to_capacity_latest", "policy_file": "x.csv"}) == "数量枠＋最低供給・削って最低"
    assert V.policy_short({"week_rule": "earliest_first"}) == "数量枠・早い週から"


def test_cost_only_change_hides_fixed_cost_and_judgement(ws):
    _named_cost(ws, "C01", "2027-W02")
    c = V.comparison(ws, "C01", "C02")
    assert c["available"] and c["cost_stale"] and c["money"]["fixed_cost"] == []
    assert "並べ直す" in c["summary"][-1]["text"] and c["supply"] is not None
    assert C.status(ws, "C01")["state"] == C.ST_DONE                       # the case stays 済み


def test_display_names_in_the_table_and_notes(ws):
    c = V.comparison(ws, "C01", "C02")
    labels = [r["label"] for r in c["money"]["fixed_cost"]]
    assert labels == ["合計", "fee", "raise"]                              # no display name -> the code


def test_message_gist_picks_the_reason():
    msg = "[quantity allocation] 衝突：止めた\n  P|X: 置けない 9 lot。最低供給量の合計が数量枠を超える\n  代わりの案：…\n  -> out/dir\n"
    g = V.message_gist(msg)
    assert "置けない 9 lot" in g and "out/dir" not in g
