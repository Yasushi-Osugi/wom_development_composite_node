# -*- coding: utf-8 -*-
"""
tests/test_demand_envelope_soft.py — Phase 2 Fork B（per-node demand_envelope）
=============================================================================
`_apply_mom_cap_backward` の充填ターゲットを node の `demand_envelope` で切り替える
（大杉さんと合意、2026-07-31）:

  - "hard"（既定）: cap_hard まで詰めて割当。超過は CO/carry-back。cap_soft はフラグのみ
                    （overtime）。＝現状挙動。生鮮・在庫不可・受注生産向け。
  - "soft"        : cap_soft で平準化。超過は FIFO で前週へ carry-back（前倒し在庫）。
                    cap_hard は物理天井（充填には使わない）。在庫可・平準化生産向け。

閉鎖週（op_shifts==0）は両モードで target=0（holiday skip と統一）。
既定 "hard" → 既存全ノード・全ケース不変 → golden 緑。soft は opt-in。
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
# 1. soft モード：cap_soft で平準化し、超過を前週へ前倒し（cap_hard は使わない）
# ---------------------------------------------------------------------------

def test_soft_mode_levels_at_cap_soft():
    sc_tree, n, sku_id, mom = _demo_mom()
    mom.demand_envelope = "soft"
    for w in range(n):
        mom.set_capacity(w, cap_hard=10.0, cap_soft=5.0)   # 天井10、平準化5
        mom.set_operating_shifts(w, 14)                     # 全週 open

    mom.psi4demand[10][S] = [f"A{i}" for i in range(8)]     # 需要8 > cap_soft5
    mom.psi4demand[9][S]  = [f"B{i}" for i in range(4)]     # 需要4

    result = BackwardPlanResult(prod_nm=sku_id)
    bp = BackwardPlanner(sc_tree, config={"mom_constrained": True})
    bp._apply_mom_cap_backward(mom, n, result)

    # cap_soft=5 で平準化（cap_hard=10 まで詰めない）
    assert len(mom.psi4demand[10][P]) == 5, "soft: cap_soft=5 で充填（cap_hard ではない）"
    assert len(mom.psi4demand[10][S]) == 5, "soft: S も cap_soft でレベル"
    # idx9: 自前4 + carried3 = 7 → cap_soft5、超過2を idx8 へ
    assert len(mom.psi4demand[9][P]) == 5
    assert len(mom.psi4demand[8][S]) == 2, "cap_soft 超過分がさらに手前へ前倒し"


# ---------------------------------------------------------------------------
# 2. hard モード（既定）：cap_hard 充填・cap_soft はフラグのみ（現状不変）
# ---------------------------------------------------------------------------

def test_hard_mode_unchanged_cap_soft_is_flag_only():
    sc_tree, n, sku_id, mom = _demo_mom()
    # demand_envelope は既定 "hard"
    assert mom.demand_envelope == "hard"
    for w in range(n):
        mom.set_capacity(w, cap_hard=10.0, cap_soft=5.0)
    mom.psi4demand[10][S] = [f"A{i}" for i in range(8)]     # 8 <= cap_hard10

    result = BackwardPlanResult(prod_nm=sku_id)
    bp = BackwardPlanner(sc_tree, config={"mom_constrained": True})
    bp._apply_mom_cap_backward(mom, n, result)

    # hard: 8 <= cap_hard10 → clip なし・lot 不動（S はそのまま8）
    assert len(mom.psi4demand[10][S]) == 8, "hard: cap_hard 以内は lot を動かさない"
    # cap_soft=5 超過（8>5）は overtime フラグとして記録（Fork A）
    assert len(result.cap_soft_envelope_violations) > 0, "hard: cap_soft はフラグのみ"


# ---------------------------------------------------------------------------
# 3. soft ＋ 閉鎖週：holiday は target=0、需要は cap_soft で前倒し分散
# ---------------------------------------------------------------------------

def test_soft_mode_holiday_spreads_at_cap_soft():
    sc_tree, n, sku_id, mom = _demo_mom()
    mom.demand_envelope = "soft"
    for w in range(n):
        mom.set_capacity(w, cap_hard=10.0, cap_soft=5.0)
        mom.set_operating_shifts(w, 14)
    mom.set_operating_shifts(10, 0)                         # idx10 閉鎖（お盆）

    mom.psi4demand[10][S] = [f"A{i}" for i in range(8)]     # 閉鎖週に8

    result = BackwardPlanResult(prod_nm=sku_id)
    bp = BackwardPlanner(sc_tree, config={"mom_constrained": True})
    bp._apply_mom_cap_backward(mom, n, result)

    assert mom.psi4demand[10][P] == [], "閉鎖週は生産0（穴）"
    assert len(mom.psi4demand[9][P]) == 5, "前週は cap_soft=5 で平準化（cap_hard ではない）"
    assert len(mom.psi4demand[8][S]) == 3, "cap_soft 超過分はさらに手前へ"


if __name__ == "__main__":
    for t in [
        test_soft_mode_levels_at_cap_soft,
        test_hard_mode_unchanged_cap_soft_is_flag_only,
        test_soft_mode_holiday_spreads_at_cap_soft,
    ]:
        print(f"\n=== {t.__name__} ===")
        t()
        print("PASS")
    print("\nAll demand_envelope soft-mode (Fork B) tests passed.")
