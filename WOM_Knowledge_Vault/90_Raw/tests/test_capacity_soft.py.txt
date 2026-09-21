# -*- coding: utf-8 -*-
"""
tests/test_capacity_soft.py — Phase 1b（cap_soft データ経路の復活）
=================================================================
Request Letter「操業制約レイヤー」§5.2 / §11.1 に対応する **test-first** の3層のうち、
本スライス（データ経路のみ先行）で扱う **Integration 層** と **Unit 層**。

背景（Letter §3 / §11.1）:
  cap_soft が「休眠」していた真因は2つ——
    (i) Backward の demand envelope としての cap_soft 使用（未実装＝次スライス）
    (ii) **CSV → ローダ → ノード のデータ経路**（capacity_plan に列が無く、
         ローダが cap_hard しか読まない）← 本スライスで解消する層
  既存テスト（test_step7_capacity.py）は node.set_capacity() で CSV をバイパスして
  いたため、この (ii) の穴を誰も踏まなかった。

  → 本テストは **実ローダ `load_capacity_dataframe()` 経由**で cap_soft を流し込み、
     「ローダが列を無視した瞬間に赤くなる」ことを保証する（§11.1 layer 2）。

後方互換（重要）:
  - cap_soft 列が **無い** capacity_plan は従来どおり cap_hard のみ設定
    （cap_soft は既定 0.0=無制限のまま）。既存6ケースの挙動・golden は不変。
  - Forward の Step 0b（cap_soft 違反フラグ）は既存機構。lot は動かさない（配置不変）。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from wom.model.plan_node import S, CO, I, P
from wom.model.sc_tree import build_demo_sc_tree
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner
from wom.engine.plan_copy import copy_demand_to_supply
from wom.engine.forward_planner import ForwardPlanner

# ── 本スライスで新設する共有ローダ（未実装なら ImportError = RED）───────────
from wom.engine.capacity_sealer import load_capacity_dataframe


# ---------------------------------------------------------------------------
# 共有フィクスチャ
# ---------------------------------------------------------------------------

def _demo_tree():
    """single-SKU / single-region の demo tree（W01..W26）。MOM = get_in_root。"""
    sku_id = "SKU-A"
    region = "JP"
    weeks = [f"2024-W{i:02d}" for i in range(1, 27)]
    sku_master = pd.DataFrame([
        {"sku_id": sku_id, "sku_name": "Product A", "region": region,
         "lead_time_wks": 1},
    ])
    sc_tree = build_demo_sc_tree(sku_master, weeks, lt_wks_ot=1, lt_wks_in=2)
    mom = sc_tree.get_in_root(sku_id)
    return sc_tree, weeks, sku_id, region, mom


# ---------------------------------------------------------------------------
# Integration 層：CSV → 実ローダ → ノード
# ---------------------------------------------------------------------------

def test_loader_reads_cap_soft_column_sku_aggregate():
    """
    node_name 列なしの capacity_plan（sku 集約→MOM）で cap_soft 列を読む。
    ローダが cap_hard=max_supply と cap_soft=CSV値 の両方をノードに書く事。
    """
    sc_tree, weeks, sku_id, region, mom = _demo_tree()

    cap_df = pd.DataFrame(
        [{"sku_id": sku_id, "week": w, "max_supply": 4, "cap_soft": 2} for w in weeks]
    )
    load_capacity_dataframe(sc_tree, cap_df, weeks)

    w06 = weeks.index("2024-W06")
    assert mom.cap_hard(w06) == 4.0, f"cap_hard should be 4, got {mom.cap_hard(w06)}"
    assert mom.cap_soft(w06) == 2.0, f"cap_soft should be 2 (from CSV), got {mom.cap_soft(w06)}"


def test_loader_reads_cap_soft_column_node_name():
    """node_name 列ありの capacity_plan でも cap_soft が対象ノードに乗る事。"""
    sc_tree, weeks, sku_id, region, mom = _demo_tree()

    cap_df = pd.DataFrame(
        [{"sku_id": sku_id, "node_name": mom.node_name, "week": w,
          "max_supply": 5, "cap_soft": 3} for w in weeks]
    )
    load_capacity_dataframe(sc_tree, cap_df, weeks)

    w10 = weeks.index("2024-W10")
    assert mom.cap_hard(w10) == 5.0
    assert mom.cap_soft(w10) == 3.0, f"cap_soft should be 3 (node_name path), got {mom.cap_soft(w10)}"


def test_loader_absent_cap_soft_column_is_backward_compatible():
    """
    cap_soft 列が **無い** 従来 CSV：cap_hard は設定され、cap_soft は既定 0.0 のまま
    （＝無制限。既存6ケースの挙動・golden 不変）。
    """
    sc_tree, weeks, sku_id, region, mom = _demo_tree()

    cap_df = pd.DataFrame(
        [{"sku_id": sku_id, "week": w, "max_supply": 4} for w in weeks]  # cap_soft 列なし
    )
    load_capacity_dataframe(sc_tree, cap_df, weeks)

    w06 = weeks.index("2024-W06")
    assert mom.cap_hard(w06) == 4.0
    assert mom.cap_soft(w06) == 0.0, (
        f"cap_soft 列が無い場合は 0.0（無制限）のままであるべき, got {mom.cap_soft(w06)}"
    )


# ---------------------------------------------------------------------------
# Unit 層：ローダ経由で流した cap_soft が Forward の違反フラグを駆動する
# ---------------------------------------------------------------------------

def test_cap_soft_from_csv_drives_forward_violation_no_movement():
    """
    §11.1 の Unit 例：cap_soft=2 / cap_hard=4 / 需要=6。
    **ローダ経由**（set_capacity バイパスではなく）で能力を流し込み、
      - Forward が cap_hard=4 で 2 lot を seal（demand 6 - cap 4）
      - cap_soft=2 の帯超過（4 > 2）を over_by=2 で flag（lot は動かさない）
    を確認。データ経路が死ぬと（ローダが cap_soft を無視）flag が出ず赤。
    """
    sc_tree, weeks, sku_id, region, mom = _demo_tree()

    # 能力は CSV ローダ経由で設定（＝データ経路を実際に通す）
    cap_df = pd.DataFrame(
        [{"sku_id": sku_id, "week": w, "max_supply": 4, "cap_soft": 2} for w in weeks]
    )
    load_capacity_dataframe(sc_tree, cap_df, weeks)

    # 需要 6 lots を leaf_out に
    assign_demand_lots_from_dict(sc_tree, {(sku_id, region, "2024-W10"): 6}, cpu_size=1)

    # v1r0m2 セマンティクス（full demand 伝播）で Forward に cap 判定を委ねる
    BackwardPlanner(sc_tree, config={"mom_constrained": False}).run(sku_id)
    copy_demand_to_supply(sc_tree, sku_id)
    result = ForwardPlanner(sc_tree).run(sku_id)

    # 物理上限 cap_hard=4：6-4=2 lot が seal される
    assert result.cap_hard_sealed == 2, (
        f"cap_hard=4, demand=6 -> 2 sealed, got {result.cap_hard_sealed}"
    )
    # ソフト能力 cap_soft=2：seal 後 P=4 > 2 なので over_by=2 の違反が1件
    assert any(over == 2 for (_nid, _wk, over) in result.cap_soft_violations), (
        f"cap_soft=2 の帯超過(4>2, over_by=2)が flag される事; "
        f"violations={result.cap_soft_violations}"
    )


if __name__ == "__main__":
    for t in [
        test_loader_reads_cap_soft_column_sku_aggregate,
        test_loader_reads_cap_soft_column_node_name,
        test_loader_absent_cap_soft_column_is_backward_compatible,
        test_cap_soft_from_csv_drives_forward_violation_no_movement,
    ]:
        print(f"\n=== {t.__name__} ===")
        t()
        print("PASS")
    print("\nAll cap_soft data-path tests passed.")
