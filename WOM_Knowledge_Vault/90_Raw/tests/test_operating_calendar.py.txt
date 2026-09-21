# -*- coding: utf-8 -*-
"""
tests/test_operating_calendar.py — Phase 2 Slice 2-1（per-node 操業カレンダー・0-shift skip）
==========================================================================================
Request Letter §5.1（操業カレンダーを per-node intrinsic 属性に）の第一歩。

データモデル（大杉さんと合意、2026-07-31）:
  1 week = 21 shifts（1日 3shift × 7日、1shift=8H）。
  - shifts(w)=0  -> OFF（閉鎖）。traversal で配置週を **skip**（SS_Days の遡りと同じ扱い）。
  - shifts(w)=N>0 -> ON。将来 cap_soft = N × (cap_hard/21) を導出（← Slice 2-2、本テストでは対象外）。
  - 未設定（None）-> 常時 open（既定・後方互換）。

本スライス（2-1）で検証する不変条件:
  1. PlanNode に per-node の shift 配列（既定 None＝常時 open）と is_open/operating_shifts。
  2. operating_calendar.csv を **実ローダ**で読み、node.operating_shifts(w) == CSV値。
  3. BackwardPlanner._offset_week が **shifts==0 の週を skip**（既存 explicit_closures と union）。
  4. 後方互換：カレンダー未設定なら _offset_week は従来どおり week-lt。

禁足コア（plan_node.py / backward_planner.py）改変を伴うため、本テスト緑 ＋ 既存全緑 ＋
golden 緑（skip は lot を動かすので psi md5 が捕捉）＋ オーナー差分レビューが受け入れ条件。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from wom.model.sc_tree import build_demo_sc_tree
from wom.engine.backward_planner import BackwardPlanner
from wom.engine.capacity_sealer import load_operating_calendar  # 新設（未実装なら RED）


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
# 1. 既定（カレンダー未設定）＝常時 open・_offset_week は従来どおり
# ---------------------------------------------------------------------------

def test_default_no_calendar_is_always_open():
    sc_tree, weeks, sku_id, mom = _demo()
    w10 = weeks.index("2024-W10")   # idx 9
    assert mom.operating_shifts(w10) is None, "未設定は None（常時 open）"
    assert mom.is_open(w10) is True

    bp = BackwardPlanner(sc_tree, config={})
    # W10(idx9) から lt=2 遡る -> 従来どおり idx7（=W08）
    assert bp._offset_week(9, 2, mom.node_name) == 7


# ---------------------------------------------------------------------------
# 2. per-node shift 設定 -> is_open / operating_shifts
# ---------------------------------------------------------------------------

def test_set_operating_shifts_open_closed():
    sc_tree, weeks, sku_id, mom = _demo()
    w09 = weeks.index("2024-W09")   # idx 8
    w10 = weeks.index("2024-W10")   # idx 9

    mom.set_operating_shifts(w09, 0)    # 閉鎖
    mom.set_operating_shifts(w10, 14)   # 通常2直（14 shift/週）

    assert mom.operating_shifts(w09) == 0
    assert mom.is_open(w09) is False
    assert mom.operating_shifts(w10) == 14
    assert mom.is_open(w10) is True


# ---------------------------------------------------------------------------
# 3. _offset_week が 0-shift 週を skip（既存 closure と同じ配置週スキップ）
# ---------------------------------------------------------------------------

def test_offset_week_skips_zero_shift_weeks():
    sc_tree, weeks, sku_id, mom = _demo()
    # W09(idx8) を閉鎖（0 shift）
    mom.set_operating_shifts(8, 0)

    bp = BackwardPlanner(sc_tree, config={})
    # W10(idx9) から lt=2 遡る。閉鎖 idx8 を飛ばすので idx6（=W07）に落ちる。
    assert bp._offset_week(9, 2, mom.node_name) == 6, (
        "0-shift の週を skip して1週手前に配置されるべき")


# ---------------------------------------------------------------------------
# 4. Integration：operating_calendar.csv -> 実ローダ -> node
# ---------------------------------------------------------------------------

def test_loader_reads_operating_calendar():
    sc_tree, weeks, sku_id, mom = _demo()
    cal_df = pd.DataFrame([
        {"sku_id": sku_id, "node_name": mom.node_name, "week": "2024-W09", "shifts": 0},
        {"sku_id": sku_id, "node_name": mom.node_name, "week": "2024-W10", "shifts": 14},
        {"sku_id": sku_id, "node_name": mom.node_name, "week": "2024-W11", "shifts": 21},
    ])
    load_operating_calendar(sc_tree, cal_df, weeks)

    assert mom.operating_shifts(weeks.index("2024-W09")) == 0
    assert mom.is_open(weeks.index("2024-W09")) is False
    assert mom.operating_shifts(weeks.index("2024-W10")) == 14
    assert mom.operating_shifts(weeks.index("2024-W11")) == 21
    # 未指定週は None（常時 open）のまま
    assert mom.operating_shifts(weeks.index("2024-W05")) is None


if __name__ == "__main__":
    for t in [
        test_default_no_calendar_is_always_open,
        test_set_operating_shifts_open_closed,
        test_offset_week_skips_zero_shift_weeks,
        test_loader_reads_operating_calendar,
    ]:
        print(f"\n=== {t.__name__} ===")
        t()
        print("PASS")
    print("\nAll operating-calendar (Slice 2-1) tests passed.")
