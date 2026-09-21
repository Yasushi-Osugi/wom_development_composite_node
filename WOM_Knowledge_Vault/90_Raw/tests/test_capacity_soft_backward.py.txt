# -*- coding: utf-8 -*-
"""
tests/test_capacity_soft_backward.py — Phase 1b Slice 2（Backward cap_soft envelope）
==================================================================================
Request Letter §5.2 の「cap_soft で envelope → cap_hard まで増産余地 → 超過は CO」を、
**Fork A（配置は cap_hard で不変・残業帯をフラグするだけ）** で BackwardPlanner に実装した
振る舞いの test-first 仕様（Unit 層）。

検証する不変条件:
  1. cap_soft < cap_hard で、実生産(placed_P=min(demand,cap_hard)) が cap_soft を超える週は、
     `result.cap_soft_envelope_violations` に over_by=placed_P-cap_soft が記録される。
  2. **配置は一切変わらない**：cap_soft 有り/無しで psi4demand の P/S/CO が完全一致
     （Fork A ＝ cap_soft は lot を動かさない）。
  3. 後方互換：cap_soft=0（未設定）は no-op。cap_soft>=cap_hard は帯ゼロで no-op。

禁足コア（backward_planner.py）改変を伴うため、本テストが緑 ＋ 既存全テスト緑 ＋ golden 緑
を実装の受け入れ条件とする（オーナー差分レビュー必須）。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from wom.model.plan_node import S, CO, I, P
from wom.model.sc_tree import build_demo_sc_tree
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner


def _run_backward(cap_hard, cap_soft, demand_qty):
    """demo tree に cap を直接設定し、mom_constrained=True で Backward を走らせる。"""
    sku_id, region = "SKU-A", "JP"
    weeks = [f"2024-W{i:02d}" for i in range(1, 27)]
    sku_master = pd.DataFrame([
        {"sku_id": sku_id, "sku_name": "Product A", "region": region, "lead_time_wks": 1},
    ])
    sc_tree = build_demo_sc_tree(sku_master, weeks, lt_wks_ot=1, lt_wks_in=2)
    mom = sc_tree.get_in_root(sku_id)
    if cap_hard > 0 or cap_soft > 0:
        for w in range(len(weeks)):
            mom.set_capacity(w, cap_hard=cap_hard, cap_soft=cap_soft)
    assign_demand_lots_from_dict(sc_tree, {(sku_id, region, "2024-W10"): demand_qty}, cpu_size=1)
    result = BackwardPlanner(sc_tree, config={"mom_constrained": True}).run(sku_id)
    return sc_tree, mom, result


def _totals(mom, n=26):
    tp = sum(len(mom.psi4demand[w][P]) for w in range(n))
    ts = sum(len(mom.psi4demand[w][S]) for w in range(n))
    tc = sum(len(mom.psi4demand[w][CO]) for w in range(n))
    return tp, ts, tc


# ---------------------------------------------------------------------------
# 1. ソフト帯フラグ（cap_hard 未超過）：demand=3, cap_hard=4, cap_soft=2
# ---------------------------------------------------------------------------

def test_backward_cap_soft_envelope_flagged_within_hard():
    sc_tree, mom, result = _run_backward(cap_hard=4, cap_soft=2, demand_qty=3)
    tp, ts, tc = _totals(mom)
    # 配置：非オーバーフロー時、需要は psi4demand[S] に載る（P は clip 時のみ書かれる設計）。
    #       ここでは cap_hard を超えないので CO は出ない。
    assert tc == 0, f"no cap_hard overflow -> CO should be 0, got {tc}"
    assert ts == 3, f"demand (envelope basis) should sit in MOM S total=3, got {ts}"
    # ソフト帯：placed_P=min(demand 3, cap_hard 4)=3, 3 - cap_soft(2) = 1 を残業としてフラグ
    total_env = sum(over for (_nid, _wk, over) in result.cap_soft_envelope_violations)
    assert total_env == 1, (
        f"cap_soft envelope over_by should total 1 (placed 3 - soft 2); "
        f"violations={result.cap_soft_envelope_violations}")


# ---------------------------------------------------------------------------
# 2. cap_hard 超過 ＋ ソフト帯：demand=6, cap_hard=4, cap_soft=2
# ---------------------------------------------------------------------------

def test_backward_cap_soft_envelope_with_hard_overflow():
    sc_tree, mom, result = _run_backward(cap_hard=4, cap_soft=2, demand_qty=6)
    # 実生産週(cap_hard=4)の残業帯 4-2=2 がフラグされる（carry-back 先の週は placed<=soft で無し）
    total_env = sum(over for (_nid, _wk, over) in result.cap_soft_envelope_violations)
    assert total_env >= 2, (
        f"cap_soft envelope should flag the burst band (>=2); "
        f"violations={result.cap_soft_envelope_violations}")


# ---------------------------------------------------------------------------
# 3. Fork A 不変条件：cap_soft は lot を動かさない（有無で P/S/CO 完全一致）
# ---------------------------------------------------------------------------

def test_backward_cap_soft_does_not_move_lots():
    # cap_soft=0（無効）
    _t0, mom0, res0 = _run_backward(cap_hard=4, cap_soft=0, demand_qty=6)
    # cap_soft=2（有効）
    _t2, mom2, res2 = _run_backward(cap_hard=4, cap_soft=2, demand_qty=6)

    assert _totals(mom0) == _totals(mom2), (
        f"cap_soft must NOT change placement (Fork A); "
        f"soft=0 {_totals(mom0)} vs soft=2 {_totals(mom2)}")
    # soft=0 は envelope フラグ無し（後方互換）
    assert len(res0.cap_soft_envelope_violations) == 0
    # soft=2 は envelope フラグ有り
    assert len(res2.cap_soft_envelope_violations) > 0


# ---------------------------------------------------------------------------
# 4. 帯ゼロ（cap_soft >= cap_hard）は no-op
# ---------------------------------------------------------------------------

def test_backward_cap_soft_equal_hard_is_noop():
    sc_tree, mom, result = _run_backward(cap_hard=4, cap_soft=4, demand_qty=5)
    total_env = sum(over for (_nid, _wk, over) in result.cap_soft_envelope_violations)
    assert total_env == 0, (
        f"cap_soft==cap_hard -> empty overtime band -> no flag, got {total_env}")


if __name__ == "__main__":
    for t in [
        test_backward_cap_soft_envelope_flagged_within_hard,
        test_backward_cap_soft_envelope_with_hard_overflow,
        test_backward_cap_soft_does_not_move_lots,
        test_backward_cap_soft_equal_hard_is_noop,
    ]:
        print(f"\n=== {t.__name__} ===")
        t()
        print("PASS")
    print("\nAll backward cap_soft envelope tests passed.")
