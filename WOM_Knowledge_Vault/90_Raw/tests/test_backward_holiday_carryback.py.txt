# -*- coding: utf-8 -*-
"""
tests/test_backward_holiday_carryback.py — Phase 2 Slice 2-3b（DEMAND 層の holiday-aware 化）
==========================================================================================
`_apply_mom_cap_backward` で **閉鎖週(op_shifts==0)を cap=0 扱い**にし、既存の carry-back
機構で「各週の cap_hard を尊重しつつ手前へ前倒し分散」する（大杉さんと合意、2026-07-31）。

狙い（Forward だけが skip して DEMAND 層と食い違う問題の根本解決）:
  - 閉鎖週は生産0（psi4demand[P]/[S] を空に）。
  - その週の需要は前週へ carry-back され、**各週 cap_hard を超えない範囲で複数週に分散**
    （最寄り1週に山盛り＝cap 超過、を回避）。
  - DEMAND 層で閉鎖週に穴が開き、Forward はこの計画を追うだけで supply も自然に
    「穴＋なだらかな前倒し」になる。

opt-in：op_shifts に 0 が無い（操業カレンダー未設定含む）MOM は従来どおり
（既存全ケースの golden 不変）。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from wom.model.plan_node import S, CO, I, P
from wom.model.sc_tree import build_demo_sc_tree
from wom.engine.backward_planner import BackwardPlanner, BackwardPlanResult


def _demo_mom():
    sku_id, region = "SKU-A", "JP"
    weeks = [f"2024-W{i:02d}" for i in range(1, 27)]
    sku_master = pd.DataFrame([
        {"sku_id": sku_id, "sku_name": "Product A", "region": region, "lead_time_wks": 1},
    ])
    sc_tree = build_demo_sc_tree(sku_master, weeks, lt_wks_ot=1, lt_wks_in=2)
    mom = sc_tree.get_in_root(sku_id)
    return sc_tree, len(weeks), sku_id, mom


# ---------------------------------------------------------------------------
# 1. 閉鎖週の需要は cap を尊重して手前へ carry-back 分散（DEMAND 層に穴）
# ---------------------------------------------------------------------------

def test_closed_week_demand_carried_back_respecting_cap():
    sc_tree, n, sku_id, mom = _demo_mom()
    for w in range(n):
        mom.set_capacity(w, cap_hard=5.0, cap_soft=0.0)   # 物理天井 5/週
        mom.set_operating_shifts(w, 14)                    # 全週 open
    mom.set_operating_shifts(10, 0)                        # idx10 を閉鎖

    # 需要：idx10（閉鎖週）に4、idx9 に4
    mom.psi4demand[10][S] = ["A1", "A2", "A3", "A4"]
    mom.psi4demand[9][S]  = ["B1", "B2", "B3", "B4"]

    result = BackwardPlanResult(prod_nm=sku_id)
    bp = BackwardPlanner(sc_tree, config={"mom_constrained": True})
    bp._apply_mom_cap_backward(mom, n, result)

    # 閉鎖週 idx10：生産0（P/S 空）、需要は前へ carry-back
    assert mom.psi4demand[10][P] == [], "閉鎖週は生産0"
    assert mom.psi4demand[10][S] == [], "閉鎖週の S も空（前倒し済み）"
    assert len(mom.psi4demand[10][CO]) == 4, "displaced 4 lots が CO マーカに"

    # idx9：自前4 + carried4 = 8、cap 5 → P=5、overflow 3 を idx8 へ
    assert len(mom.psi4demand[9][P]) == 5, "cap_hard=5 を超えない"
    assert len(mom.psi4demand[8][S]) == 3, "cap 超過分はさらに手前へ分散"


# ---------------------------------------------------------------------------
# 2. どの週も cap_hard を超えない（山盛り＝over-cap の回避）
# ---------------------------------------------------------------------------

def test_carryback_never_exceeds_cap_hard():
    sc_tree, n, sku_id, mom = _demo_mom()
    for w in range(n):
        mom.set_capacity(w, cap_hard=5.0, cap_soft=0.0)
        mom.set_operating_shifts(w, 14)
    mom.set_operating_shifts(10, 0)

    mom.psi4demand[10][S] = [f"A{i}" for i in range(5)]   # 閉鎖週に5
    mom.psi4demand[9][S]  = [f"B{i}" for i in range(5)]   # 前週も5（合計10を cap5 で分散）

    result = BackwardPlanResult(prod_nm=sku_id)
    bp = BackwardPlanner(sc_tree, config={"mom_constrained": True})
    bp._apply_mom_cap_backward(mom, n, result)

    assert mom.psi4demand[10][P] == [], "閉鎖週は生産0"
    assert mom.psi4demand[10][S] == [], "閉鎖週の需要は前へ移動"
    assert len(mom.psi4demand[9][P]) == 5, "前週は cap_hard=5 で頭打ち（山盛りにしない）"
    for w in range(n):
        assert len(mom.psi4demand[w][P]) <= 5, (
            f"week {w}: P={len(mom.psi4demand[w][P])} が cap_hard=5 を超過")


# ---------------------------------------------------------------------------
# 3. 後方互換：op_shifts 未設定（0-shift 無し）は従来どおり
# ---------------------------------------------------------------------------

def test_no_calendar_backward_compatible():
    sc_tree, n, sku_id, mom = _demo_mom()
    for w in range(n):
        mom.set_capacity(w, cap_hard=5.0, cap_soft=0.0)
    # op_shifts は全て None（既定）

    mom.psi4demand[10][S] = ["A1", "A2", "A3"]   # cap 5 以下 → 無変更のはず

    result = BackwardPlanResult(prod_nm=sku_id)
    bp = BackwardPlanner(sc_tree, config={"mom_constrained": True})
    bp._apply_mom_cap_backward(mom, n, result)

    # cap 未超過・カレンダー無し → S はそのまま（clip の continue 経路）
    assert len(mom.psi4demand[10][S]) == 3
    assert mom.psi4demand[10][CO] == []


if __name__ == "__main__":
    for t in [
        test_closed_week_demand_carried_back_respecting_cap,
        test_carryback_never_exceeds_cap_hard,
        test_no_calendar_backward_compatible,
    ]:
        print(f"\n=== {t.__name__} ===")
        t()
        print("PASS")
    print("\nAll backward holiday carry-back (Slice 2-3b) tests passed.")
