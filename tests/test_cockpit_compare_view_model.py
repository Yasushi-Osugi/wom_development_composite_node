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
    assert "未設定" in notes and "保留" in notes and "画面は言わない" in notes and "在庫の保有費" in notes


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
    assert "在庫の保有費は P0 に入っていない。感度は金額と境目の見出しに（年率は仮置き、採用する率は未設定）" in notes
    assert "PA 9 → 12" in notes
    assert "在庫の保有費：この比較には保有費の欄が無い（並べ直す）" in notes        # an older comparison
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


# ── 段 4 B0：週で違う能力は範囲で出す ─────────────────────────────────────
def test_capacity_by_week_ranges(ws):
    C.set_planned_output(ws, "C02", "PA", 9, from_week="2027-W02", to_week="2027-W03")
    cap = V.case_inputs(ws, "C02")["capacity"][0]
    assert cap["cap_soft"] == "2027-W02〜2027-W03 は 9、ほかは 8" and cap["cap_soft_main"] == "8"
    assert cap["max_supply"] == "10"
    t = V.case_table(ws)
    i = [k for k, c in enumerate(t["columns"]) if c.startswith("能力")][0]
    assert [r["cells"][i] for r in t["rows"]][:2] == ["10/8", "10/8・9（週で違う）"]


def test_range_text_lists_every_other_range():
    rows = [{"week": w, "cap_soft": v} for w, v in
            (("2027-W01", "8"), ("2027-W02", "9"), ("2027-W03", "8"), ("2027-W04", "9"), ("2027-W05", "8"))]
    assert V.range_text(rows, "cap_soft") == ("2027-W02・2027-W04 は 9、ほかは 8", "8")


def test_range_text_other_is_the_value_at_both_ends():
    rows = [{"week": f"2027-W{i:02d}", "cap_soft": "12" if 2 <= i <= 6 else "11"} for i in range(1, 9)]
    assert V.range_text(rows, "cap_soft") == ("2027-W02〜2027-W06 は 12、ほかは 11", "11")   # 12 has more weeks


# ── 段 4 A1・A3：シフトとエンジンが使った能力の表示 ────────────────────────
def _calendar(ws, cid):
    from test_cockpit_cases import CAL
    with open(os.path.join(ws, cid, "model", "operating_calendar.csv"), "w", encoding="utf-8", newline="") as f:
        f.write(CAL)


def _engine_capacity(ws, cid, soft):
    rows = []
    for i, w in enumerate(["2026-W52"] + WEEKS + ["2027-W04"]):
        closed = int(w == "2027-W02")
        rows.append({"product": "PA", "factory": "Fac_A", "week_index": i, "week": w, "cap_hard": 10,
                     "cap_soft": soft, "cap_soft_source": "closed" if closed else "calendar",
                     "shifts": 0 if closed else 18, "demand_envelope": "soft", "closed": closed, "yield_rate": 1.0,
                     "shippable_hard": 10, "shippable_soft": soft})
    os.makedirs(os.path.join(ws, cid, "run"), exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(ws, cid, "run", "capacity.csv"), index=False)


def test_calendar_inputs_before_and_after_a_run(ws):
    _calendar(ws, "C02")
    cap = V.case_inputs(ws, "C02")["capacity"][0]               # inputs changed -> not 済み: the inputs
    assert cap["calendar"] and cap["shifts"] == "18" and cap["closed_weeks"] == ["2027-W02"]
    assert "シフト 18" in cap["text"] and "実行するとエンジンの値" in cap["text"]
    _done(ws, "C02", 150.0)
    _engine_capacity(ws, "C02", 9)
    d = V.case_inputs(ws, "C02")
    cap = d["capacity"][0]
    assert d["capacity_source"] == "engine" and cap["source"] == "engine"
    assert cap["text"] == "18 シフト → 9 lot／週（設備 10 × 18 ÷ 21）、休業 1 週（2027-W02）（エンジンの値）"
    t = V.case_table(ws)
    i = [k for k, c in enumerate(t["columns"]) if c.startswith("能力")][0]
    assert [r["cells"][i] for r in t["rows"]][:2] == ["10/8", "10/9"]      # ① C02 from the engine


def test_engine_capacity_is_not_used_when_inputs_changed(ws):
    _engine_capacity(ws, "C01", 9)
    assert V.engine_capacity(ws, "C01") is not None
    C.set_planned_output(ws, "C01", "PA", 7)                          # inputs changed after the run
    assert V.engine_capacity(ws, "C01") is None


def test_market_labels_from_the_comparison(ws):
    d = V.compare_dir(ws, "C01", "C02")
    pd.DataFrame([{"sku_id": "PA", "region": "X", "market": "Shop_X"},
                  {"sku_id": "PA", "region": "Y", "market": "Y"}]).to_csv(os.path.join(d, "market_map.csv"), index=False)
    sv = V.supply_view(ws, "C01", "C02")
    assert V.key_text(sv, "PA", "X") == "PA:Shop_X（X）" and V.key_text(sv, "PA", "Y") == "PA:Y"


def test_factory_choices_one_or_several_factories(ws):
    d = V.compare_dir(ws, "C01", "C02")
    fv = V.factory_view(d, "C01", "C02")
    assert [c["label"] for c in fv["choices"]] == ["PA"]             # old comparison: no factory column
    fw = pd.read_csv(os.path.join(d, "factory_weekly.csv"))
    two = pd.concat([fw.assign(factory="Brew"), fw.assign(factory="Bottle")])
    two.to_csv(os.path.join(d, "factory_weekly.csv"), index=False)
    fv = V.factory_view(d, "C01", "C02")
    assert [c["label"] for c in fv["choices"]] == ["PA @ Brew", "PA @ Bottle"]


def test_case_table_labels_backlog_with_market_names(ws):
    p = os.path.join(ws, "C01", "model", "sc_tree_master.csv")
    t = pd.read_csv(p, dtype=str, keep_default_na=False)
    t.loc[t["node_name"] == "Shop_X", "region"] = "X"            # Shop_X <-> region X (names differ)
    t.to_csv(p, index=False)
    assert V.case_market_labels(ws, "C01") == {"PA:X": "PA:Shop_X（X）", "PA:Y": "PA:Shop_Y（Y）"}
    assert V._kv({"PA:X": 2}, V.case_market_labels(ws, "C01")) == "PA:Shop_X（X） 2"
    assert V._kv({"PA:X": 2}) == "PA:X 2"


# ── 到達点 5 B：需要の仮説の表・根拠の文・比べた後に変わった文 ─────────────────
def test_entry_matrix_and_basis_text(ws):
    C.set_demand_hypothesis(ws, "C02", "PA", "X", basis_note="強い", promotion_note="販促あり")
    m = V.entry_matrix(ws, "C02")
    assert m["products"] == ["PA"] and m["markets"] == ["X", "Y"]
    assert m["cells"][("PA", "X")]["text"] == "2027-W02・定常 4・×0.5（2 週）"
    ep = {r["region"]: r for r in V.case_inputs(ws, "C02")["entry_plan"]}
    assert (ep["X"]["basis_note"], ep["X"]["promotion_note"]) == ("強い", "販促あり")


def test_summary_lists_the_hypothesis_and_the_text(ws):
    C.set_demand_hypothesis(ws, "C02", "PA", "X", ramp_ratio="1.0", basis_note="強い立ち上がり")
    _done(ws, "C02", 150.0)
    p = os.path.join(V.compare_dir(ws, "C01", "C02"), "compare.json")     # compared after the change
    rec = json.load(open(p, encoding="utf-8"))
    rec["alt_input_hashes"] = C.read_case(ws, "C02")["run"]["input_hashes"]
    json.dump(rec, open(p, "w", encoding="utf-8"))
    cmp = V.comparison(ws, "C01", "C02")
    t = V.summary(ws, "C01", "C02", cmp)[0]["text"]
    assert "PA:X の立ち上がりの割合（基準 0.5、相手 1.0）" in t
    assert "PA:X の根拠（基準「なし」、相手「強い立ち上がり」）" in t


def test_text_changed_after_the_comparison_is_noted(ws):
    p = os.path.join(V.compare_dir(ws, "C01", "C02"), "compare.json")
    rec = json.load(open(p, encoding="utf-8"))
    rec["base_entry_notes"], rec["alt_entry_notes"] = C.entry_notes(ws, "C01"), C.entry_notes(ws, "C02")
    json.dump(rec, open(p, "w", encoding="utf-8"))
    assert V.notes_changed_after_compare(ws, "C01", "C02") == []
    C.set_demand_hypothesis(ws, "C02", "PA", "Y", basis_note="後から書いた")
    assert V.notes_changed_after_compare(ws, "C01", "C02") == ["C02 PA:Y"]
    assert any("根拠の文は比べた後に変わった" in n for n in V.notes(ws, "C01", "C02", V.comparison(ws, "C01", "C02")))
    rec.pop("base_entry_notes")
    rec.pop("alt_entry_notes")
    json.dump(rec, open(p, "w", encoding="utf-8"))
    assert V.notes_changed_after_compare(ws, "C01", "C02") == []        # an older comparison has no record


# ── 在庫の保有費（RequestLetter_Cockpit_HoldingCost_Sensitivity）──────────────────
def _holding(d, rows):
    base = {"weekly_rate": "", "display_name": "", "H_base_warmup": 0, "H_alt_warmup": 0, "dH_warmup": 0,
            "delta_P0": 50.0, "delta_P0_net": 50.0, "delta_W": 3, "boundary_report_only": "f*",
            "boundary_assumption": "", "valuation_status": "評価済み", "note": ""}
    pd.DataFrame([{**base, **r} for r in rows]).to_csv(os.path.join(d, "holding_sensitivity.csv"), index=False)


def test_holding_table_sentence_and_note(ws):
    d = V.compare_dir(ws, "C01", "C02")
    _holding(d, [{"annual_rate": r, "cost_item": "raise", "display_name": "増産の確保費", "H_base_report": 10 * k,
                  "H_alt_report": 13 * k, "H_base_total": 10 * k, "H_alt_total": 13 * k, "dH_report": 3 * k,
                  "dH_total": 3 * k, "f_star_incl_warmup": (50 - 3 * k) / 3, "f_star_report_only": (50 - 3 * k) / 3,
                  "boundary_incl_warmup": "f* = ΔP0 ÷ ΔW"} for r, k in ((0.05, 1), (0.10, 2), (0.15, 3))])
    c = V.comparison(ws, "C01", "C02")
    hv = c["money"]["holding"]
    assert hv["available"] and [r["rate_text"] for r in hv["rows"]] == ["5%", "10%", "15%"]
    assert hv["rows"][0]["label"] == "増産の確保費"
    judge = [p for p in c["summary"] if p["title"] == "判断に要るもの"][0]["text"]
    assert "在庫の保有費（年率 5〜15% の仮置き）を入れると、増産の確保費の境目は 13.67〜15.67 円／週" in judge
    assert "報告期間だけなら 13.67〜15.67 円／週" in judge
    notes = "\n".join(V.notes(ws, "C01", "C02", c))
    assert "在庫の保有費は P0 に入っていない" in notes and "この比較には保有費の欄が無い" not in notes


def test_holding_is_hidden_when_the_cost_premises_changed(ws):
    _holding(V.compare_dir(ws, "C01", "C02"), [{"annual_rate": 0.1, "cost_item": "fee", "H_base_report": 1,
                                                "H_alt_report": 2, "H_base_total": 1, "H_alt_total": 2, "dH_report": 1,
                                                "dH_total": 1, "f_star_incl_warmup": 1, "f_star_report_only": 1,
                                                "boundary_incl_warmup": "f*"}])
    _named_cost(ws, "C02", "2027-W01")
    c = V.comparison(ws, "C01", "C02")
    assert c["cost_stale"] and not c["money"]["holding"]["available"]
    assert not any("保有費" in p["text"] for p in c["summary"])


def test_raise_row_shows_the_weeks_made_at_cap_and_the_unused_weeks(ws, monkeypatch):
    from wom.cockpit import case_actions as A
    d = V.compare_dir(ws, "C01", "C02")
    fw = pd.read_csv(os.path.join(d, "factory_weekly.csv"))
    fw.loc[(fw["case"] == "C02") & (fw["week"] == "2027-W02"), "production_lots"] = 7     # below the raised output
    fw.to_csv(os.path.join(d, "factory_weekly.csv"), index=False)
    rows = [dict(FC[1], cost_item="planned_output_raise", display_name="増産の確保費", count_outside_report=1), FC[2]]
    pd.DataFrame(rows).to_csv(os.path.join(d, "fixed_cost_breakeven.csv"), index=False)
    monkeypatch.setattr(A, "raised_targets", lambda w, cid: [("PA", "Fac_A")])
    r = [x for x in V.comparison(ws, "C01", "C02")["money"]["fixed_cost"]
         if x["cost_item"] == "planned_output_raise"][0]
    assert (r["made_at_cap_alt"], r["unused_alt"]) == (2, 1)          # 3 paid weeks, made at the raised output in 2
    assert r["made_at_cap_base"] == "" and r["unused_base"] == ""      # the base case does not bear it
    monkeypatch.setattr(A, "raised_targets", lambda w, cid: [])
    r = [x for x in V.comparison(ws, "C01", "C02")["money"]["fixed_cost"]
         if x["cost_item"] == "planned_output_raise"][0]
    assert r["unused_alt"] == "" and r["use_note_alt"] == "引き上げた工場が見つからない"
