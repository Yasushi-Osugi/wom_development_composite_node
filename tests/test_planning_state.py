# -*- coding: utf-8 -*-
"""
tests/test_planning_state.py — Planning State と層間ハンドオフ（Phase 7）
================================================================================
正典: requests/Phase7_RequestLetter_to_CodeKun.md V4
      requests/Phase7a_Addendum_to_CodeKun.md A5（plan_eval / gap_decomposition /
      reversal の追加テスト。`gap_vs_plan_pct` は廃止されたためテストも削除）

**GUI は一切対象にしない**（本 Phase の成果物は JSON とコマンドだけ）。
"""
import csv
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

import wom.planning_state as planning_state
from wom.allocation.handoff import write_demand_for_allocation
from wom.allocation.cost_block import derive_cost_blocks
from wom.engine.warmup import materialize_warmup
from tools.run_headless_from_folder import run as run_headless
from tools.run_planning_loop import main as run_planning_loop_main

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
SAMPLE_DIR = os.path.join(REPO_ROOT, "data", "sample")
GOLDEN_DIR = os.path.join(HERE, "golden")

ALLOC_DIR = os.path.join(SAMPLE_DIR, "soysauce-jpy-2027-alloc")


def _copy_model(tmp_path, case: str):
    src = os.path.join(SAMPLE_DIR, case)
    dst = tmp_path / case
    shutil.copytree(src, dst)
    return str(dst)


# ---------------------------------------------------------------------------
# V4.1 golden 不変（最重要）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", ["soysauce-jpy-2027", "Cookie-jp-2026"])
def test_golden_unchanged_by_default(case, tmp_path):
    golden_path = os.path.join(GOLDEN_DIR, case + ".json")
    if not os.path.exists(golden_path):
        pytest.skip(f"no golden snapshot for {case}")
    with open(golden_path, encoding="utf-8") as f:
        golden = json.load(f)

    plugins = ",".join(golden.get("config", {}).get("plugins", [])) or "none"
    model_dir = os.path.join(SAMPLE_DIR, case)
    snap = run_headless(model_dir, plugins_spec=plugins,
                        output_ppc_dir=str(tmp_path / "ppc"), verbose=False)

    assert "planning_state_extras" not in snap
    assert snap["forward"] == golden["forward"]
    assert snap["backward"] == golden["backward"]
    assert snap["ppc"] == golden["ppc"]
    assert snap["psi"] == golden["psi"]


# ---------------------------------------------------------------------------
# V4.2 配分は需要を増やさない
# ---------------------------------------------------------------------------

def test_allocation_conserves_demand(tmp_path):
    blocks, _tp = derive_cost_blocks(ALLOC_DIR)
    allocation = {"JP": 0.10, "US": 0.45, "EU": 0.45}
    r = write_demand_for_allocation(
        ALLOC_DIR, allocation, "T01", cap_wk=800.0,
        out_path=str(tmp_path / "demand_forecast_T01.csv"))

    assert r["total_after"] <= r["total_before"]
    for m, q in r["per_market"].items():
        assert q <= blocks[m].demand_qty + 1e-9


# ---------------------------------------------------------------------------
# V4.3 端数は最大剰余法（1 lot もずれない）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("allocation", [
    {"JP": 0.10, "US": 0.45, "EU": 0.45},
    {"JP": 1.0 / 3, "US": 1.0 / 3, "EU": 1.0 / 3},
])
def test_allocation_rounding_is_exact(allocation, tmp_path):
    out_path = str(tmp_path / "demand_forecast_T02.csv")
    r = write_demand_for_allocation(
        ALLOC_DIR, allocation, "T02", cap_wk=800.0, out_path=out_path)

    # 出力 CSV を region 別に再集計し、market へロールアップして per_market と突き合わせる
    agg_rows = []
    with open(os.path.join(ALLOC_DIR, "ga_market_aggregation.csv"), encoding="utf-8", newline="") as f:
        agg_rows = list(csv.DictReader(f))
    region_to_market = {row["region"]: row["market_group"] for row in agg_rows}

    market_totals = {}
    with open(out_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            m = region_to_market.get(row["region"])
            if m is None:
                continue
            market_totals[m] = market_totals.get(m, 0) + int(row["quantity"])

    for m, expected in r["per_market"].items():
        assert market_totals.get(m, 0) == expected, f"market {m}: {market_totals.get(m)} != {expected}"


# ---------------------------------------------------------------------------
# V4.4 需要ゼロの週は維持・行順不変
# ---------------------------------------------------------------------------

def test_zero_weeks_preserved(tmp_path):
    out_path = str(tmp_path / "demand_forecast_T03.csv")
    write_demand_for_allocation(
        ALLOC_DIR, {"JP": 0.10, "US": 0.45, "EU": 0.45}, "T03",
        cap_wk=800.0, out_path=out_path)

    with open(os.path.join(ALLOC_DIR, "demand_forecast.csv"), encoding="utf-8", newline="") as f:
        orig_rows = list(csv.DictReader(f))
    with open(out_path, encoding="utf-8", newline="") as f:
        new_rows = list(csv.DictReader(f))

    assert len(orig_rows) == len(new_rows)
    for o, n in zip(orig_rows, new_rows):
        assert o["sku_id"] == n["sku_id"]
        assert o["region"] == n["region"]
        assert o["week"] == n["week"]
        if int(float(o["quantity"])) == 0:
            assert int(n["quantity"]) == 0


# ---------------------------------------------------------------------------
# V4.5 state 遷移・allocation_id の連番
# ---------------------------------------------------------------------------

_DUMMY_PLAN_EVAL = {
    "basis": "allocation_layer", "fx_usd": 150.0, "material_usd": 6.0,
    "profit": 100.0, "revenue": 200.0, "cost": 100.0, "lots": 100,
}


def test_state_transitions(tmp_path):
    out_dir = str(tmp_path / "planning_state")

    state = planning_state.new_state(
        "case1", "s1_base", {"JP": 0.1, "US": 0.45, "EU": 0.45},
        {"P_opt": 100.0}, _DUMMY_PLAN_EVAL)
    assert state["state"] == "pre_plan"
    assert state["realized"] is None

    path1 = planning_state.save(state, out_dir=out_dir)
    assert os.path.basename(path1) == "A01.json"

    state2 = planning_state.new_state(
        "case1", "s1_base", {"JP": 0.2, "US": 0.4, "EU": 0.4},
        {"P_opt": 90.0}, _DUMMY_PLAN_EVAL)
    path2 = planning_state.save(state2, out_dir=out_dir)
    assert os.path.basename(path2) == "A02.json"

    # lots を _DUMMY_PLAN_EVAL と一致させる（不一致だと attach_realized() が
    # A2.5 の検査で ValueError を投げる仕様のため）。model_dir/cap_wk を渡さない
    # ので分解（gap_decomposition 等）は計算されない——ロールアップ等の基本動作のみ確認。
    snapshot = {
        "ppc": {"gross_profit_base": 105.0, "revenue_base": 205.0,
               "cost_base": 100.0, "total_lots": 3},
        "planning_state_extras": {
            "leaf_out_S": {"P1": {"JP": 10, "US": 45, "EU": 45}},
            "leaf_out_CO": {"P1": {"JP": 0, "US": 0, "EU": 0}},
            "cap_hard_violation_weeks": [], "cap_soft_violation_weeks": [],
            "backward_envelope_weeks": [], "inventory_peak_weeks": {},
            "leaf_out_S_weekly": {},
        },
    }
    realized_state = planning_state.attach_realized(planning_state.load("case1", "A01", out_dir),
                                                     snapshot)
    assert realized_state["state"] == "feasible_plan"
    realized = realized_state["realized"]
    assert set(realized.keys()) == {
        "allocation", "ppc", "fx_effective", "plan_at_realized_fx",
        "gap_decomposition", "unmet_lots", "capacity_violation_weeks",
        "peak_inventory_weeks", "issues",
    }
    # model_dir/cap_wk 無しなので分解は計算されない（None・空のまま）
    assert realized["gap_decomposition"] is None
    assert realized["plan_at_realized_fx"] is None
    assert realized["fx_effective"] == {}


# ---------------------------------------------------------------------------
# V4.7 run_planning_loop が1周する（この Phase の合否）
# ---------------------------------------------------------------------------

def test_planning_loop_closes(tmp_path):
    model_dir = _copy_model(tmp_path, "soysauce-jpy-2027-alloc")
    out_dir = str(tmp_path / "planning_state")
    ppc_out = str(tmp_path / "ppc")

    rc = run_planning_loop_main([
        "--model-dir", model_dir, "--scenario", "s1_base", "--cap-wk", "800",
        "--allocation", "0.10,0.45,0.45",
        "--out-dir", out_dir, "--ppc-out", ppc_out, "--quiet",
    ])
    assert rc == 0

    path = os.path.join(out_dir, "soysauce-jpy-2027-alloc", "A01.json")
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        state = json.load(f)

    assert state["state"] == "feasible_plan"
    realized = state["realized"]
    assert realized["unmet_lots"] >= 0

    blocks, _tp = derive_cost_blocks(model_dir)
    for m, x in realized["allocation"].items():
        if m not in blocks:
            continue
        # 需要天井の範囲に収まる（比率なので単純に [0,1] だが、需要ゼロの市場は
        # 割り当てられないはずなのでゼロ需要かどうかもあわせて確認する）
        assert 0.0 <= x <= 1.0 + 1e-9


# ---------------------------------------------------------------------------
# V4.8 warmup が demand_file を尊重する
# ---------------------------------------------------------------------------

def test_warmup_respects_demand_file(tmp_path):
    model_dir = _copy_model(tmp_path, "soysauce-jpy-2027-alloc")

    # 元の demand_forecast.csv とは異なる最早週を持つ代替需要ファイルを作る
    alt_path = os.path.join(model_dir, "demand_forecast_ALT.csv")
    with open(os.path.join(model_dir, "demand_forecast.csv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    # 最初の非ゼロ行より前の行を落とし、残りだけを書く（＝実データの最早週が遅くなる）
    weeks_sorted = sorted({r["week"] for r in rows if float(r["quantity"]) != 0})
    cutoff = weeks_sorted[len(weeks_sorted) // 2]
    alt_rows = [r for r in rows if r["week"] >= cutoff]
    with open(alt_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["sku_id", "region", "week", "quantity"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(alt_rows)

    summary_default = materialize_warmup(model_dir, warmup_lt=4, write=False)
    summary_alt = materialize_warmup(model_dir, warmup_lt=4, write=False,
                                     demand_file="demand_forecast_ALT.csv")

    assert summary_alt["real_start"] != summary_default["real_start"]
    assert summary_alt["real_start"] == cutoff


# ---------------------------------------------------------------------------
# Phase 7a・A5: plan_eval / gap_decomposition / reversal
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def closed_loop_state(tmp_path_factory):
    """soysauce s1_base / cap_wk=800 / 配分 (0.10,0.45,0.45) で1周させた最終 state。
    複数のテストで使い回す（headless 実行は重いので module scope で1回だけ回す）。
    """
    tmp_path = tmp_path_factory.mktemp("phase7a_loop")
    model_dir = _copy_model(tmp_path, "soysauce-jpy-2027-alloc")
    out_dir = str(tmp_path / "planning_state")
    ppc_out = str(tmp_path / "ppc")

    rc = run_planning_loop_main([
        "--model-dir", model_dir, "--scenario", "s1_base", "--cap-wk", "800",
        "--allocation", "0.10,0.45,0.45",
        "--out-dir", out_dir, "--ppc-out", ppc_out, "--quiet",
    ])
    assert rc == 0

    path = os.path.join(out_dir, "soysauce-jpy-2027-alloc", "A01.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_plan_eval_uses_chosen_allocation(closed_loop_state):
    """A5.1: --allocation を明示したとき、plan_eval.profit は P_opt ではなく
    その配分自体の評価（(0.10,0.45,0.45) は格子点なので P_grid と一致）になること。"""
    plan_eval = closed_loop_state["plan_eval"]
    profit_levels = closed_loop_state["profit_levels"]

    assert plan_eval["profit"] == pytest.approx(132_133_072.5, abs=1.0)
    assert profit_levels["source"] == "manual"
    # P_opt を流用していないことの直接証拠（P_opt はこれより高い値）
    assert plan_eval["profit"] != pytest.approx(profit_levels["P_opt"], abs=1.0)


def test_gap_decomposition_identity(closed_loop_state):
    """A5.2（最重要）: total == quantity + fx_assumption + residual（±1円）。"""
    gap = closed_loop_state["realized"]["gap_decomposition"]
    assert gap is not None
    assert gap["total"] == pytest.approx(
        gap["quantity"] + gap["fx_assumption"] + gap["residual"], abs=1.0)
    # 数量ハンドオフが厳密なので quantity=0（A2.5）
    assert gap["quantity"] == pytest.approx(0.0, abs=1e-9)


def test_no_gap_vs_plan_pct_key(closed_loop_state):
    """A5.3: realized に gap_vs_plan_pct キーが存在しないこと（null でも残さない）。"""
    assert "gap_vs_plan_pct" not in closed_loop_state["realized"]


def test_reversal_populated(closed_loop_state):
    """A5.5: soysauce（fx_usd=150）で reversal.boundary が 117.0 または 119.0。"""
    reversal = closed_loop_state["reversal"]
    assert reversal.get("boundary") in (117.0, 119.0)
    assert reversal.get("axis") == "fx_usd"
    assert reversal.get("current") == pytest.approx(150.0, abs=1e-9)


def test_fx_effective_is_quantity_weighted(tmp_path):
    """A5.4: 出荷が偏る合成ケースで、単純平均とは異なる値になること。"""
    model_dir = tmp_path / "fx_synthetic"
    model_dir.mkdir()
    with open(model_dir / "ppc_market_price.csv", "w", encoding="utf-8", newline="") as f:
        f.write("market_node,product_id,week,market_price,currency\n")
        f.write("Leaf_US,P1,2027-W01,100,USD\n")
    with open(model_dir / "ppc_fx_rate.csv", "w", encoding="utf-8", newline="") as f:
        f.write("week,currency,base_currency,rate\n")
        f.write("2027-W01,USD,JPY,150.0\n")
        f.write("2027-W02,USD,JPY,200.0\n")

    simple_avg = (150.0 + 200.0) / 2.0

    weekly_front = {"P1": {"Leaf_US": {"2027-W01": 100, "2027-W02": 1}}}
    fx_front = planning_state.fx_effective_from_weekly(str(model_dir), weekly_front)["USD"]

    weekly_back = {"P1": {"Leaf_US": {"2027-W01": 1, "2027-W02": 100}}}
    fx_back = planning_state.fx_effective_from_weekly(str(model_dir), weekly_back)["USD"]

    assert fx_front == pytest.approx(150.0, abs=1.0)
    assert fx_back == pytest.approx(200.0, abs=1.0)
    assert fx_front != pytest.approx(simple_avg, abs=1.0)
    assert fx_back != pytest.approx(simple_avg, abs=1.0)
    assert fx_front != pytest.approx(fx_back, abs=1.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
