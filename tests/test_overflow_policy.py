# -*- coding: utf-8 -*-
"""
tests/test_overflow_policy.py — 行の順の偏りの直し方 段 1（RequestLetter_M6_RowOrder_Stage1_OverflowPolicy）

能力を超えた週に、どの市場のどの lot を前の週へ回すかを選ぶ ``overflow_policy``
（tail〔既定・今の動き〕／proportional_week／balance_cut_ratio）の 3 層のうち単体・結合。

- 単体：設計書 v0.3 §4 の例 1〜6（期待値は参照計算 requests/WOM_M6_RowOrderBias_ref_examples.py
  の出力を数で書いた）。合成の木で、木の CSV の行の順を入れ替えた 2 つの結果が一致すること。
- 結合：planning_config.csv → read_overflow_policy → BackwardPlanner、headless の snapshot の config。
- E2E は test_golden.py（既定 tail で golden 全件不変）。

保護対象のコア（backward_planner.py）を変えた依頼の受け入れ条件。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from wom.engine.overflow_policy import (
    OverflowPolicyError, OverflowTracker, resolve_overflow_policy,
)
from wom.engine.backward_planner import BackwardPlanner
from wom.engine.sc_tree_builder import build_sc_tree_from_master
from wom.engine.warmup import read_overflow_policy
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.model.plan_node import S, P, CO

PC, BC = "proportional_week", "balance_cut_ratio"


# ---------------------------------------------------------------------------
# 参照計算と同じ枠組みで OverflowTracker を動かす（エンジンの外）
# ---------------------------------------------------------------------------

def _lot(m, i, seq):
    # 参照計算の lot (市場, 処理の番号 i, 連番)。要求週は i が大きいほど「遅い」として
    # 並べる（参照計算の pick_within と同じ向き）。
    return f"SKU:{m}:W{i:03d}:{seq:05d}"


def _market(lot):
    return lot.split(":")[1]


def _independent(policy, weeks):
    """押し戻しを次の週に入れない（参照計算 independent_weeks）。"""
    tr, tot = OverflowTracker(policy), {}
    for i, (by_m, n) in enumerate(weeks):
        lots = [_lot(m, i, j) for m, k in by_m.items() for j in range(k)]
        tr.observe(lots)
        _keep, push = tr.split(lots, n)
        for l in push:
            tot[_market(l)] = tot.get(_market(l), 0) + 1
    return tot


def _carry(policy, rounds, caps, order=None):
    """押し戻しは次に処理する週の並びに入る（参照計算 run）。戻り値 (押し戻し, 落ちる, 落ちる Lot_ID)。"""
    tr = OverflowTracker(policy)
    carry, pushed, seq = [], {}, {}
    for i, (new, c) in enumerate(zip(rounds, caps)):
        lots = []
        for m in (order or sorted(new)):
            for _ in range(new.get(m, 0)):
                seq[m] = seq.get(m, 0) + 1
                lots.append(_lot(m, i, seq[m]))
        lots = lots + carry
        tr.observe(lots)
        n = max(0, len(lots) - c)
        carry = []
        if n == 0:
            continue
        _keep, carry = tr.split(lots, n)
        for l in carry:
            pushed[_market(l)] = pushed.get(_market(l), 0) + 1
    lost = {}
    for l in carry:
        lost[_market(l)] = lost.get(_market(l), 0) + 1
    return pushed, lost, sorted(carry)


# ---------------------------------------------------------------------------
# 単体：設計書 §4 の例 1〜6
# ---------------------------------------------------------------------------

def test_example1_fraction_by_cumulative_rounding_error():
    assert _independent(PC, [({"A": 3, "B": 1}, 2)] * 4) == {"A": 6, "B": 2}


def test_example2_market_order_does_not_matter():
    assert _independent(PC, [({"B": 1, "A": 3}, 2)] * 4) == {"A": 6, "B": 2}


def test_example3_small_market():
    assert _independent(PC, [({"A": 10, "B": 1}, 2)] * 10) == {"A": 18, "B": 2}
    assert _independent(BC, [({"A": 10, "B": 1}, 2)] * 10) == {"A": 19, "B": 1}


R6 = [{"A": 3, "B": 1}] * 6
CLOSED = [3, 3, 0, 3, 3, 3]


def test_example4_closed_week():
    assert _carry(PC, R6, CLOSED)[:2] == ({"A": 24, "B": 9}, {"A": 7, "B": 2})
    assert _carry(BC, R6, CLOSED)[:2] == ({"A": 25, "B": 8}, {"A": 7, "B": 2})


def test_example5_continuous_shortage():
    assert _carry(PC, R6, [3] * 6)[:2] == ({"A": 16, "B": 5}, {"A": 5, "B": 1})
    assert _carry(BC, R6, [3] * 6)[:2] == ({"A": 16, "B": 5}, {"A": 4, "B": 2})


@pytest.mark.parametrize("policy", [PC, BC])
def test_example6_row_order_swapped(policy):
    a = _carry(policy, R6, CLOSED, order=["A", "B"])
    b = _carry(policy, R6, CLOSED, order=["B", "A"])
    assert a == b


def test_split_orders_lists_week_market_seq():
    tr = OverflowTracker(PC)
    lots = [_lot("B", 1, 2), _lot("A", 2, 1), _lot("B", 0, 1), _lot("A", 0, 3), _lot("A", 1, 9)]
    tr.observe(lots)
    keep, push = tr.split(lots, 2)
    key = lambda l: (l.split(":")[2], l.split(":")[1], int(l.split(":")[3]))  # noqa: E731
    assert keep == sorted(keep, key=key) and push == sorted(push, key=key)
    assert sorted(keep + push) == sorted(lots)
    # 市場の中では要求週の遅いものから押し戻す
    assert _lot("A", 2, 1) in push


def test_balance_counts_every_push_back():
    """延べ：同じ Lot_ID を 2 回押し戻すと 2 と数える。母数は 1 回。"""
    tr = OverflowTracker(BC)
    lots = [_lot("A", 0, 1), _lot("A", 0, 2)]
    tr.observe(lots)
    _k, push = tr.split(lots, 1)
    tr.observe(push)
    tr.split(push, 1)
    assert tr.summary() == {"A": {"pushed": 2, "denominator": 2}}


# ---------------------------------------------------------------------------
# 単体：設定の値
# ---------------------------------------------------------------------------

def test_resolve_policy_blank_is_tail_and_unknown_stops():
    assert resolve_overflow_policy(None) == "tail"
    assert resolve_overflow_policy("  ") == "tail"
    assert resolve_overflow_policy(" balance_cut_ratio ") == BC
    with pytest.raises(OverflowPolicyError) as e:
        resolve_overflow_policy("proportional", "x.csv")
    msg = str(e.value)
    assert "x.csv" in msg and "proportional" in msg and "tail" in msg and BC in msg
    with pytest.raises(OverflowPolicyError):
        BackwardPlanner(None, config={"overflow_policy": "fifo"})


# ---------------------------------------------------------------------------
# 単体：合成の木（工場 1・市場 3）で行の順を入れ替えても結果が同じ
# ---------------------------------------------------------------------------

WEEKS = [f"2027-W{i:02d}" for i in range(1, 13)]
PROD = "SKU-A"
_MARKETS = ["MkA", "MkB", "MkC"]


def _tree_rows(swap):
    rows = [
        {"node_name": "SP", "parent_node": "", "node_type": "supply_point", "side": "outbound", "lt_wks": 0},
        {"node_name": "DC", "parent_node": "SP", "node_type": "dad", "side": "outbound", "lt_wks": 1},
    ]
    leaves = [{"node_name": m, "parent_node": "DC", "node_type": "leaf_out", "side": "outbound", "lt_wks": 1,
               "region": m}
              for m in _MARKETS]
    rows += (leaves[::-1] if swap else leaves)
    rows += [{"node_name": "MOM", "parent_node": "", "node_type": "mom", "side": "inbound", "lt_wks": 0},
             {"node_name": "SUP", "parent_node": "MOM", "node_type": "leaf_in", "side": "inbound", "lt_wks": 1}]
    if swap:
        rows = rows[::-1]
    for r in rows:
        r["product_name"] = PROD
    return pd.DataFrame(rows)


# 需要：MkA 多い・MkB 中・MkC 少量（ときどき）
_DEMAND = {}
for _w in range(4, 12):
    _DEMAND[(PROD, "MkA", WEEKS[_w])] = 5
    _DEMAND[(PROD, "MkB", WEEKS[_w])] = 3
    if _w % 3 == 0:
        _DEMAND[(PROD, "MkC", WEEKS[_w])] = 1


def _run_synthetic(policy, swap):
    tree = build_sc_tree_from_master(_tree_rows(swap), WEEKS)
    mom = tree.get_in_root(PROD)
    for w in range(len(WEEKS)):
        mom.set_capacity(w, cap_hard=6)            # 能力の不足が続く
    mom.set_operating_shifts(5, 0)                 # 休業の週
    items = list(_DEMAND.items())
    assign_demand_lots_from_dict(tree, dict(items[::-1] if swap else items), cpu_size=1)
    res = BackwardPlanner(tree, config={"overflow_policy": policy}).run(PROD)
    n = len(WEEKS)
    view = {b: [sorted(mom.psi4demand[w][b]) for w in range(n)] for b in (S, P, CO)}
    pushed = sorted(l for w in range(n) for l in mom.psi4demand[w][CO])
    past_due = sorted(l for (nid, l, _w) in res.past_due_lots if nid == mom.node_id)
    return view, pushed, past_due, res


@pytest.mark.parametrize("policy", [PC, BC])
def test_synthetic_tree_row_order_invariant(policy):
    a = _run_synthetic(policy, swap=False)
    b = _run_synthetic(policy, swap=True)
    assert a[0] == b[0]
    assert a[1] == b[1] and a[1]          # 押し戻しが起きている
    assert a[2] == b[2] and a[2]          # 最初の週で落ちる lot がある
    assert a[3].overflow_by_node == b[3].overflow_by_node
    assert a[3].overflow_policy == policy


@pytest.mark.parametrize("policy", ["tail", PC, BC])
def test_synthetic_tree_conserves_lots_and_respects_capacity(policy):
    view, pushed, past_due, res = _run_synthetic(policy, swap=False)
    tree = build_sc_tree_from_master(_tree_rows(False), WEEKS)
    total = sum(_DEMAND.values())
    placed = sum(len(view[S][w]) for w in range(len(WEEKS)))
    assert placed + len(past_due) == total
    for w in range(len(WEEKS)):
        assert len(view[S][w]) <= (0 if w == 5 else 6)
    s = res.overflow_by_node["MOM:" + PROD] if ("MOM:" + PROD) in res.overflow_by_node \
        else next(iter(res.overflow_by_node.values()))
    assert sum(v["pushed"] for v in s.values()) == len(pushed)
    assert {m: v["denominator"] for m, v in s.items()} == {
        "MkA": 40, "MkB": 24, "MkC": 2}
    del tree


# ---------------------------------------------------------------------------
# 結合：planning_config.csv → read_overflow_policy → BackwardPlanner／headless
# ---------------------------------------------------------------------------

def test_read_overflow_policy(tmp_path):
    d = str(tmp_path)
    assert read_overflow_policy(d) == "tail"                     # ファイルなし
    (tmp_path / "planning_config.csv").write_text("key,value\nwarmup_lt,4\n", encoding="utf-8")
    assert read_overflow_policy(d) == "tail"                     # キーなし
    (tmp_path / "planning_config.csv").write_text("key,value\noverflow_policy,\n", encoding="utf-8")
    assert read_overflow_policy(d) == "tail"                     # 空欄
    (tmp_path / "planning_config.csv").write_text(
        "key,value\noverflow_policy,proportional_week\n", encoding="utf-8")
    assert read_overflow_policy(d) == PC
    (tmp_path / "planning_config.csv").write_text("key,value\noverflow_policy,even\n", encoding="utf-8")
    with pytest.raises(OverflowPolicyError) as e:
        read_overflow_policy(d)
    assert "planning_config.csv" in str(e.value) and "even" in str(e.value)


def _copy_model(tmp_path, policy):
    import shutil
    src = os.path.join(os.path.dirname(__file__), "..", "data", "sample", "soysauce-us-2027")
    dst = tmp_path / "soy"
    shutil.copytree(src, dst)
    if policy is not None:
        pc = dst / "planning_config.csv"
        text = pc.read_text(encoding="utf-8-sig") if pc.exists() else "key,value\n"
        if not text.endswith("\n"):
            text += "\n"
        pc.write_text(text + f"overflow_policy,{policy}\n", encoding="utf-8")
    return str(dst)


def test_headless_config_records_policy_only_when_not_tail(tmp_path):
    from tools.run_headless_from_folder import run
    import json
    golden = json.load(open(os.path.join(os.path.dirname(__file__), "golden", "soysauce-us-2027.json"),
                            encoding="utf-8"))
    plugins = ",".join(golden["config"]["plugins"]) or "none"
    snap_tail = run(_copy_model(tmp_path / "a", "tail"), plugins_spec=plugins,
                    output_ppc_dir=str(tmp_path / "ppc_a"), verbose=False)
    assert snap_tail["config"] == golden["config"]
    assert snap_tail["psi"] == golden["psi"]
    snap_pc = run(_copy_model(tmp_path / "b", PC), plugins_spec=plugins,
                  output_ppc_dir=str(tmp_path / "ppc_b"), verbose=False)
    assert snap_pc["config"]["overflow_policy"] == PC
    assert {k: v for k, v in snap_pc["config"].items() if k != "overflow_policy"} == golden["config"]


def test_headless_unknown_policy_stops(tmp_path):
    from tools.run_headless_from_folder import run
    with pytest.raises(OverflowPolicyError):
        run(_copy_model(tmp_path, "random"), plugins_spec="none",
            output_ppc_dir=str(tmp_path / "ppc"), verbose=False)


def test_balance_bulk_equals_one_lot_at_a_time():
    """まとめての割り当て（速さのため）が、1 lot ずつの素朴な選び方と同じ結果になる。"""
    import random
    from fractions import Fraction as F
    rnd = random.Random(7)
    for _ in range(400):
        mk = [f"M{i}" for i in range(rnd.randint(1, 6))]
        avail = {m: rnd.randint(0, 300) for m in mk}
        avail[mk[0]] = max(avail[mk[0]], 1)
        num = {m: rnd.randint(0, 2000) for m in mk}
        den = {m: rnd.randint(1, 500) + avail[m] for m in mk}
        n = rnd.randint(1, sum(avail.values()))
        naive = {m: 0 for m in mk}
        for _k in range(n):
            cand = [m for m in mk if naive[m] < avail[m]]
            m = sorted(cand, key=lambda m: (F(num[m] + naive[m] + 1, den[m]), -avail[m], m))[0]
            naive[m] += 1
        tr = OverflowTracker(BC)
        tr.pushed, tr.den = dict(num), dict(den)
        by_m = {m: [f"S:{m}:W001:{j:05d}" for j in range(avail[m])] for m in mk if avail[m]}
        got = tr._alloc_balance(by_m, n)
        assert {m: got.get(m, 0) for m in mk} == naive
