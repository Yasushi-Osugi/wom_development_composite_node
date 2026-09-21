# -*- coding: utf-8 -*-
"""
tests/test_init_stock_days_wiring.py — X2 (init_stock_days) データ経路の回帰テスト
================================================================================
`init_stock_days`（X2：立ち上げ初期在庫のカバレッジ日数、OutBound 専用）を
`sc_tree_master.csv` の列から PlanNode まで確実に届けるための Anti-Degrade テスト。

背景（2026-08-02）:
  X2 の初回実装（commit 2ccbf43）は `plan_node.py`（フィールド＋`init_stock_wks`）と
  `backward_planner.py`（OutBound offset への加算）だけで、**CSV を読む
  `sc_tree_builder.py` の配線が欠けていた**。列を書いても値がノードに届かず、
  機能が休眠する状態だった（cap_soft 休眠と同型の「CSV→ローダ→ノード データ経路欠落」）。
  配線を commit 23ae8ee で追加。本テストはその経路が再び切れないよう機械的に固定する。

層（CLAUDE.md anti-degrade 3層のうち）:
  - Unit        : `PlanNode.init_stock_wks` の ceil セマンティクス。
  - Integration : 合成 sc_tree_master DataFrame → **実ローダ**
                  `build_sc_tree_from_master` → ノードの init_stock_days / init_stock_wks。
                  ← 休眠の真因（欠けていた層）をここで守る。
  - E2E         : golden（soysauce-jpy ほか）で担保済み（既定 0 で挙動不変）。
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from wom.model.plan_node import PlanNode
from wom.engine.sc_tree_builder import build_sc_tree_from_master


WEEKS = [f"2027-W{i:02d}" for i in range(1, 9)]


def _rows(with_init_stock_days: bool, dc_init_stock_days: int = 0):
    """最小の有効ツリー（InBound: leaf_in->mom, OutBound: supply_point->dad->leaf_out）。

    with_init_stock_days=False の場合は init_stock_days 列自体を持たない
    （＝既存モデルと同じ状況。後方互換の検証用）。
    """
    common = dict(cpu_size=1, buffering_stock_flag=0, demand_envelope="hard")
    rows = [
        # InBound
        dict(node_name="Leaf_In", parent_node="MOM_X", product_name="P",
             node_type="leaf_in", side="inbound", lt_wks=2, region="JP", ss_days=0, **common),
        dict(node_name="MOM_X", parent_node="", product_name="P",
             node_type="mom", side="inbound", lt_wks=1, region="JP", ss_days=0, **common),
        # OutBound
        dict(node_name="SP_X", parent_node="", product_name="P",
             node_type="supply_point", side="outbound", lt_wks=0, region="", ss_days=0, **common),
        dict(node_name="DC_X", parent_node="SP_X", product_name="P",
             node_type="dad", side="outbound", lt_wks=1, region="JP", ss_days=21,
             buffering_stock_flag=1, cpu_size=1, demand_envelope="hard"),
        dict(node_name="Rest_X", parent_node="DC_X", product_name="P",
             node_type="leaf_out", side="outbound", lt_wks=1, region="JP", ss_days=0, **common),
    ]
    df = pd.DataFrame(rows)
    if with_init_stock_days:
        # 全ノード 0、OutBound の DC_X だけ値を持たせる
        df["init_stock_days"] = 0
        df.loc[df["node_name"] == "DC_X", "init_stock_days"] = dc_init_stock_days
    return df


def _find(node, name):
    if node.node_name == name:
        return node
    for c in node.children:
        r = _find(c, name)
        if r:
            return r
    return None


def _dc_node(sc_tree):
    """OutBound の supply_point root 配下から DC_X を取得。"""
    root = sc_tree.get_ot_root("P")
    dc = _find(root, "DC_X")
    assert dc is not None, "DC_X node not found in OutBound tree"
    return dc


# ---------------------------------------------------------------------------
# Unit: init_stock_wks の ceil セマンティクス（ss_wks と同じ流儀）
# ---------------------------------------------------------------------------

def test_init_stock_wks_ceil_semantics():
    for days, expect_wks in [(0, 0), (1, 1), (6, 1), (7, 1), (8, 2),
                             (14, 2), (15, 3), (21, 3), (28, 4)]:
        node = PlanNode(node_id="n", node_name="n", product="P", side="outbound",
                        node_type="dad", tier=0, init_stock_days=days)
        assert node.init_stock_wks == expect_wks, (
            f"init_stock_days={days} -> init_stock_wks expected {expect_wks}, "
            f"got {node.init_stock_wks}")
        assert node.init_stock_wks == (math.ceil(days / 7) if days > 0 else 0)


def test_init_stock_days_default_is_zero_on_plannode():
    node = PlanNode(node_id="n", node_name="n", product="P", side="outbound",
                    node_type="dad", tier=0)
    assert node.init_stock_days == 0
    assert node.init_stock_wks == 0


# ---------------------------------------------------------------------------
# Integration: CSV(列あり) -> 実ローダ -> ノードへ届く（休眠の真因を守る層）
# ---------------------------------------------------------------------------

def test_csv_init_stock_days_reaches_node():
    df = _rows(with_init_stock_days=True, dc_init_stock_days=14)
    sc_tree = build_sc_tree_from_master(df, WEEKS)
    dc = _dc_node(sc_tree)
    assert dc.init_stock_days == 14, "CSV の init_stock_days=14 がノードに届いていない（配線欠落の再発）"
    assert dc.init_stock_wks == 2, "init_stock_wks が ceil(14/7)=2 になっていない"


def test_csv_init_stock_days_various_values_reach_node():
    for days, wks in [(7, 1), (21, 3), (28, 4)]:
        df = _rows(with_init_stock_days=True, dc_init_stock_days=days)
        sc_tree = build_sc_tree_from_master(df, WEEKS)
        dc = _dc_node(sc_tree)
        assert dc.init_stock_days == days
        assert dc.init_stock_wks == wks


# ---------------------------------------------------------------------------
# Integration: 列が無い既存モデルは 0（後方互換・挙動不変）
# ---------------------------------------------------------------------------

def test_missing_column_defaults_to_zero():
    df = _rows(with_init_stock_days=False)
    assert "init_stock_days" not in df.columns
    sc_tree = build_sc_tree_from_master(df, WEEKS)
    root_ot = sc_tree.get_ot_root("P")
    root_in = sc_tree.get_in_root("P")
    for root in (root_ot, root_in):
        stack = [root]
        while stack:
            n = stack.pop()
            assert n.init_stock_days == 0, f"{n.node_name}: 列が無いのに init_stock_days!=0"
            assert n.init_stock_wks == 0
            stack.extend(n.children)


if __name__ == "__main__":
    for t in [
        test_init_stock_wks_ceil_semantics,
        test_init_stock_days_default_is_zero_on_plannode,
        test_csv_init_stock_days_reaches_node,
        test_csv_init_stock_days_various_values_reach_node,
        test_missing_column_defaults_to_zero,
    ]:
        print(f"=== {t.__name__} ===")
        t()
        print("PASS")
    print("\nAll init_stock_days (X2) wiring tests passed.")
