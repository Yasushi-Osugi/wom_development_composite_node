# -*- coding: utf-8 -*-
"""
tests/test_shift_cap_soft.py — Phase 2 Slice 2-2（shifts -> cap_soft 導出）
========================================================================
操業カレンダーの shift 数から cap_soft を導出する（大杉さんと合意、2026-07-31）:

    cap_soft(w) = round( op_shifts(w) * cap_hard(w) / MAX_SHIFTS )    (op_shifts(w) > 0)

  - 21 shift（3直×7日）= 物理天井 -> cap_soft = cap_hard。
  - 14 shift（2直×7日）        -> cap_soft = 2/3 * cap_hard。
  -  0 shift = 閉鎖（skip、Slice 2-1）; cap_soft は据え置き（週は skip される）。
  - cap_hard は不変（物理天井のまま）。cap_hard 未設定(0)の週は導出しない。

これにより operating_calendar.csv 1枚で「休み(0)・通常(14)・フル(21)」を表現でき、
cap_soft は shift 計画からの導出値になる（capacity_plan の cap_soft を上書き）。

非コア（capacity_sealer のローダ層）で完結。既存ケースは operating_calendar.csv 無し＝
導出走らず golden 不変。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from wom.model.sc_tree import build_demo_sc_tree
from wom.engine.capacity_sealer import load_operating_calendar


def _demo():
    sku_id, region = "SKU-A", "JP"
    weeks = [f"2024-W{i:02d}" for i in range(1, 27)]
    sku_master = pd.DataFrame([
        {"sku_id": sku_id, "sku_name": "Product A", "region": region, "lead_time_wks": 1},
    ])
    sc_tree = build_demo_sc_tree(sku_master, weeks, lt_wks_ot=1, lt_wks_in=2)
    mom = sc_tree.get_in_root(sku_id)
    return sc_tree, weeks, sku_id, mom


# ---------------------------------------------------------------------------
# 1. shifts -> cap_soft 導出（cap_hard=1500）
# ---------------------------------------------------------------------------

def test_shifts_derive_cap_soft():
    sc_tree, weeks, sku_id, mom = _demo()
    for w in range(len(weeks)):
        mom.set_capacity(w, cap_hard=1500.0, cap_soft=0.0)   # 物理天井 1500

    cal_df = pd.DataFrame([
        {"sku_id": sku_id, "node_name": mom.node_name, "week": "2024-W10", "shifts": 14},
        {"sku_id": sku_id, "node_name": mom.node_name, "week": "2024-W11", "shifts": 21},
        {"sku_id": sku_id, "node_name": mom.node_name, "week": "2024-W12", "shifts": 7},
    ])
    load_operating_calendar(sc_tree, cal_df, weeks)

    assert mom.cap_soft(weeks.index("2024-W10")) == 1000   # 14*1500/21
    assert mom.cap_soft(weeks.index("2024-W11")) == 1500   # 21*1500/21 = cap_hard
    assert mom.cap_soft(weeks.index("2024-W12")) == 500    # 7*1500/21
    # cap_hard は不変
    assert mom.cap_hard(weeks.index("2024-W10")) == 1500.0
    assert mom.cap_hard(weeks.index("2024-W11")) == 1500.0


# ---------------------------------------------------------------------------
# 2. 0-shift（閉鎖）は cap_soft 据え置き＋ is_open False
# ---------------------------------------------------------------------------

def test_zero_shift_leaves_cap_soft_and_is_closed():
    sc_tree, weeks, sku_id, mom = _demo()
    w10 = weeks.index("2024-W10")
    mom.set_capacity(w10, cap_hard=1500.0, cap_soft=0.0)

    cal_df = pd.DataFrame([
        {"sku_id": sku_id, "node_name": mom.node_name, "week": "2024-W10", "shifts": 0},
    ])
    load_operating_calendar(sc_tree, cal_df, weeks)

    assert mom.is_open(w10) is False           # 閉鎖（skip 対象）
    assert mom.cap_soft(w10) == 0.0            # 導出せず据え置き


# ---------------------------------------------------------------------------
# 3. cap_hard 未設定(0) の週は導出しない（0除算・無意味値の回避）
# ---------------------------------------------------------------------------

def test_no_cap_hard_no_derivation():
    sc_tree, weeks, sku_id, mom = _demo()
    w10 = weeks.index("2024-W10")
    # cap_hard を設定しない（既定 0.0 のまま）

    cal_df = pd.DataFrame([
        {"sku_id": sku_id, "node_name": mom.node_name, "week": "2024-W10", "shifts": 14},
    ])
    load_operating_calendar(sc_tree, cal_df, weeks)

    assert mom.operating_shifts(w10) == 14     # shift は記録される
    assert mom.cap_soft(w10) == 0.0            # cap_hard=0 なので cap_soft 導出せず


if __name__ == "__main__":
    for t in [
        test_shifts_derive_cap_soft,
        test_zero_shift_leaves_cap_soft_and_is_closed,
        test_no_cap_hard_no_derivation,
    ]:
        print(f"\n=== {t.__name__} ===")
        t()
        print("PASS")
    print("\nAll shift->cap_soft (Slice 2-2) tests passed.")
