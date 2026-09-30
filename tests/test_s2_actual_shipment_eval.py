# -*- coding: utf-8 -*-
"""
tests/test_s2_actual_shipment_eval.py — RequestLetter_iPhoneWarmup_EVUpdateKitting_S2 C2・C3

S2：identity の充足・販売実績の計算を、実出荷（node._actual_ship）に合わせる。
要求（supply S）とは別の量として扱う。legacy の評価は変えない。

  Unit        合成ツリーの 1 ノードに、要求・CO・実出荷を固定値で置く（C3 の 1〜3・6）
  Integration 計画 → sc_tree_to_planning_df → evaluate_money／Strategic KPI／PPC ブリッジ
              （C3 の 4：上流の能力を減らしたコピーで、実出荷の変化が数量と金額に届く）
  legacy      旧い式（要求ベース）と 1 列ずつ一致する
"""
import csv
import math
import os
import shutil
import sys
import warnings

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from wom.data.schema import Cols
from wom.model.plan_node import S, CO, I, P
from wom.model.sc_tree import build_demo_sc_tree
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner
from wom.engine.plan_copy import copy_demand_to_supply
from wom.engine.forward_planner import ForwardPlanner
from wom.engine.sc_tree_to_df import sc_tree_to_planning_df
from wom.engine.money import evaluate_money, build_scenario_money_kpi
from wom.engine.strategic_kpi import compute_strategic_kpi

SKU = "SKU-A"
N = 12
WEEKS = [f"2024-W{i:02d}" for i in range(1, N + 1)]
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKU_MASTER = pd.DataFrame([{"sku_id": SKU, "region": "JP", "selling_price": 100.0, "unit_cost": 60.0,
                            "dso_wks": 6, "dpo_wks": 8}])


def _bare_tree(cpu_size=1):
    rows = [{"sku_id": SKU, "sku_name": "A", "region": "JP", "lead_time_wks": 1}]
    return build_demo_sc_tree(pd.DataFrame(rows), WEEKS, lt_wks_ot=1, lt_wks_in=2, cpu_size=cpu_size)


def _recorded(t):
    """全ノードに「実出荷の記録あり（出荷 0）」を付ける（Forward を通した状態の代わり）。"""
    for nd in t.iter_all_nodes(SKU):
        nd._actual_ship = {}
    return t


def _leaf(t):
    return next(nd for nd in t.get_ot_root(SKU).walk_preorder() if not nd.children)


def _leaf_rows(df):
    return df[~df[Cols.REGION].astype(str).str.startswith("DAD:")].reset_index(drop=True)


def _row(df, week):
    r = _leaf_rows(df)
    return r[r[Cols.WEEK] == week].iloc[0]


def _set(leaf, w, s=(), co=(), ship=None):
    leaf.psi4demand[w][S] = list(s)
    leaf.psi4supply[w][S] = list(s)
    leaf.psi4supply[w][CO] = list(co)
    if ship is not None:
        if not hasattr(leaf, "_actual_ship") or leaf._actual_ship is None:
            leaf._actual_ship = {}
        leaf._actual_ship[w] = list(ship)


# ---------------------------------------------------------------------------
# C3-1  要求 2 ID・実出荷 1 ID
# ---------------------------------------------------------------------------

def test_c3_1_two_requests_one_shipped():
    t = _recorded(_bare_tree())
    leaf = _leaf(t)
    _set(leaf, 4, s=["A", "B"], ship=["A"])
    df = sc_tree_to_planning_df(t, lot_flow_mode="identity")
    r = _row(df, WEEKS[4])
    assert r[Cols.QTY_BASIS] == "actual_ship"
    assert r[Cols.REQUEST_QTY] == 2
    assert r[Cols.SHIP_QTY] == 1            # 出荷 1
    assert r[Cols.ON_TIME_QTY] == 1         # 当週充足 1
    assert r[Cols.STOCKOUT_QTY] == 1        # 当週未充足（残）1
    assert r[Cols.CO_END_QTY] == 1          # 週末の CO 1
    assert r[Cols.FILL_RATE] == 0.5
    assert r[Cols.DEMAND_FULFILLED] == 1    # 評価に使う数量＝実出荷
    weekly, summary = evaluate_money(df, SKU_MASTER)
    wk = weekly[(weekly[Cols.WEEK] == WEEKS[4]) & (weekly[Cols.REGION] == "JP")].iloc[0]
    assert wk[Cols.REVENUE] == 100.0 and wk[Cols.COGS] == 60.0       # 売上は 1 lot 分
    assert wk[Cols.QTY_BASIS] == "actual_ship"
    assert summary[summary[Cols.REGION] == "JP"][Cols.REVENUE].iloc[0] == 100.0


# ---------------------------------------------------------------------------
# C3-2  前週の CO の 1 ID だけを今週出荷し、今週の要求 1 ID は未充足
# ---------------------------------------------------------------------------

def test_c3_2_carry_over_shipped_does_not_fill_this_weeks_request():
    t = _recorded(_bare_tree())
    leaf = _leaf(t)
    _set(leaf, 3, s=["OLD"], ship=[])             # 前週：要求したが出荷なし
    _set(leaf, 4, s=["NEW"], co=["OLD"], ship=["OLD"])
    df = sc_tree_to_planning_df(t, lot_flow_mode="identity")
    r = _row(df, WEEKS[4])
    assert r[Cols.SHIP_QTY] == 1            # 出荷 1（遅配分の出荷）
    assert r[Cols.ON_TIME_QTY] == 0         # 当週充足 0（総量では判定しない）
    assert r[Cols.FILL_RATE] == 0.0
    assert r[Cols.STOCKOUT_QTY] == 1        # 今週の要求 1 が未充足
    assert r["co_qty"] == 1                 # 週初の CO
    assert r[Cols.CO_END_QTY] == 1          # 週末の CO 1（NEW）
    # 単純な ship_qty / S なら 100% になってしまう形
    assert r[Cols.SHIP_QTY] / r[Cols.REQUEST_QTY] == 1.0
    # Strategic KPI の充足率も ID で判定する：2 要求のうち、当週に出荷したのは 0
    assert compute_strategic_kpi(t, lot_flow_mode="identity").fill_rate == 0.0
    # 売上は出荷した 1 lot 分（今週の要求の分ではない）
    weekly, _ = evaluate_money(df, SKU_MASTER)
    wk = weekly[(weekly[Cols.WEEK] == WEEKS[4]) & (weekly[Cols.REGION] == "JP")].iloc[0]
    assert wk[Cols.REVENUE] == 100.0


# ---------------------------------------------------------------------------
# C3-3  実出荷 0 は売上数量 0。実出荷の記録なしは「不明」で、要求 S へ戻さない
# ---------------------------------------------------------------------------

def test_c3_3_zero_shipment_is_zero_and_missing_record_is_unknown():
    # 実出荷 0（記録あり）
    t = _recorded(_bare_tree())
    leaf = _leaf(t)
    _set(leaf, 4, s=["A", "B"], ship=[])
    r = _row(sc_tree_to_planning_df(t, lot_flow_mode="identity"), WEEKS[4])
    assert r[Cols.QTY_BASIS] == "actual_ship"
    assert r[Cols.SHIP_QTY] == 0 and r[Cols.DEMAND_FULFILLED] == 0 and r[Cols.FILL_RATE] == 0.0
    # 記録が無い（その週のキーが無い）週も 0（記録の欠損ではない）
    r5 = _row(sc_tree_to_planning_df(t, lot_flow_mode="identity"), WEEKS[5])
    assert r5[Cols.SHIP_QTY] == 0 and r5[Cols.QTY_BASIS] == "actual_ship"

    # 実出荷の記録そのものが無い
    t2 = _bare_tree()
    leaf2 = _leaf(t2)
    _set(leaf2, 4, s=["A", "B"])
    assert getattr(leaf2, "_actual_ship", None) is None
    with pytest.warns(RuntimeWarning, match="no actual-shipment record"):
        df2 = sc_tree_to_planning_df(t2, lot_flow_mode="identity")
    r2 = _row(df2, WEEKS[4])
    assert r2[Cols.QTY_BASIS] == "unknown"
    assert r2[Cols.REQUEST_QTY] == 2                      # 要求は分かる
    for col in (Cols.SHIP_QTY, Cols.DEMAND_FULFILLED, Cols.ON_TIME_QTY, Cols.STOCKOUT_QTY,
                Cols.FILL_RATE, Cols.CO_END_QTY):
        assert math.isnan(r2[col]), col                   # 要求 S では代用しない
    weekly, summary = evaluate_money(df2, SKU_MASTER)
    wk = weekly[(weekly[Cols.WEEK] == WEEKS[4]) & (weekly[Cols.REGION] == "JP")].iloc[0]
    assert math.isnan(wk[Cols.REVENUE]) and wk[Cols.QTY_BASIS] == "unknown"
    sm = summary[summary[Cols.REGION] == "JP"].iloc[0]
    assert math.isnan(sm[Cols.REVENUE]) and sm[Cols.QTY_BASIS] == "unknown"   # 0 ではなく不明
    assert math.isnan(compute_strategic_kpi(t2, lot_flow_mode="identity").fill_rate)
    assert compute_strategic_kpi(t2, lot_flow_mode="identity").status_fill_rate() == "N/A"


def test_c3_3_ppc_bridge_does_not_fall_back_to_request_in_identity():
    from wom.ppc.ppc_psi_bridge import psi_to_sales_records
    t = _bare_tree()
    leaf = _leaf(t)
    _set(leaf, 4, s=["A", "B"])                           # 実出荷の記録なし
    with pytest.warns(RuntimeWarning, match="no actual-shipment record"):
        df = psi_to_sales_records(t, WEEKS, use_node_name=True, lot_flow_mode="identity")
    assert df.empty                                       # S の 2 件を売上にしない
    # ツリーに付いた印からも同じ判定になる（GUI・headless の経路）
    t.lot_flow_mode = "identity"
    with pytest.warns(RuntimeWarning):
        assert psi_to_sales_records(t, WEEKS, use_node_name=True).empty
    # legacy・方式の指定なし：これまでどおり S の件数（結果を変えない）
    t.lot_flow_mode = "legacy"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert int(psi_to_sales_records(t, WEEKS, use_node_name=True)["qty"].sum()) == 2
    del t.lot_flow_mode
    assert int(psi_to_sales_records(t, WEEKS, use_node_name=True)["qty"].sum()) == 2
    # 実出荷 0 の記録がある identity：売上 0（記録なしとは別）
    leaf._actual_ship = {}
    assert psi_to_sales_records(t, WEEKS, use_node_name=True, lot_flow_mode="identity").empty


# ---------------------------------------------------------------------------
# C3-6  cpu_size・bom_qty の換算を保つ
# ---------------------------------------------------------------------------

def test_c3_6_cpu_size_and_bom_qty_conversion_is_kept():
    t = _recorded(_bare_tree(cpu_size=12))
    leaf = _leaf(t)
    leaf.bom_qty = 4
    _set(leaf, 4, s=["A", "B", "C"], co=["Z"], ship=["A", "Z"])
    r = _row(sc_tree_to_planning_df(t, lot_flow_mode="identity"), WEEKS[4])
    k = 12 * 4
    assert r[Cols.REQUEST_QTY] == 3 * k and r[Cols.SHIP_QTY] == 2 * k
    assert r[Cols.ON_TIME_QTY] == 1 * k and r[Cols.STOCKOUT_QTY] == 2 * k
    assert r[Cols.CO_END_QTY] == 2 * k and r["co_qty"] == 1 * k
    assert r[Cols.DEMAND_FCST] == 3 * k
    assert r[Cols.FILL_RATE] == round(1 / 3, 4)           # 比は換算によらない


# ---------------------------------------------------------------------------
# 計画 → 評価（合成ツリー）：上流の能力の不足が、数量と金額に届く
# ---------------------------------------------------------------------------

def _planned(mode, mom_cap=None):
    t = _bare_tree()
    assign_demand_lots_from_dict(t, {(SKU, "JP", "2024-W08"): 4, (SKU, "JP", "2024-W10"): 4}, cpu_size=1)
    BackwardPlanner(t, config={"mom_constrained": False}).run(SKU)
    copy_demand_to_supply(t, SKU)
    if mom_cap is not None:
        mom = t.get_in_root(SKU)
        for w in range(N):
            mom.set_capacity(w, cap_hard=float(mom_cap))
    ForwardPlanner(t, lot_flow_mode=mode).run(SKU)
    t.lot_flow_mode = mode              # 計画の経路（GUI・headless）が付ける印
    return t


def test_upstream_capacity_shortage_reaches_quantity_and_money():
    free, tight = _planned("identity"), _planned("identity", mom_cap=1)
    out = {}
    for name, t in (("free", free), ("tight", tight)):
        df = sc_tree_to_planning_df(t)                   # 方式はツリーの印から
        rows = _leaf_rows(df)
        leaf = _leaf(t)
        ship = sum(len(v) for v in leaf._actual_ship.values())
        assert rows[Cols.SHIP_QTY].sum() == ship
        assert rows[Cols.DEMAND_FULFILLED].sum() == ship
        assert (rows[Cols.QTY_BASIS] == "actual_ship").all()
        assert rows[Cols.REQUEST_QTY].sum() == 8
        # 当週未充足の合計 ＝ 遅配 ＋ 期末注文残（各 ID を 1 回ずつ）
        on_time = sum(1 for w in range(N) for lot in leaf.psi4supply[w][S]
                      if lot in leaf._actual_ship.get(w, []))
        assert rows[Cols.ON_TIME_QTY].sum() == on_time
        assert rows[Cols.STOCKOUT_QTY].sum() == 8 - on_time
        assert (rows[Cols.FILL_RATE] <= 1.0).all()
        _weekly, summary = evaluate_money(df, SKU_MASTER)
        kpi = build_scenario_money_kpi(summary)
        assert kpi["revenue"].iloc[0] == ship * 100.0 and kpi["cogs"].iloc[0] == ship * 60.0
        leaf_sum = summary[~summary[Cols.REGION].astype(str).str.startswith("DAD:")]
        assert leaf_sum["total_units"].sum() == ship
        out[name] = (ship, on_time, kpi["revenue"].iloc[0], compute_strategic_kpi(t).fill_rate)
    assert out["free"][:3] == (8, 8, 800.0) and out["free"][3] == 1.0
    assert out["tight"][1] < 8 and out["tight"][3] < 1.0          # 能力の不足が充足率に届く
    assert out["tight"][2] <= out["free"][2]


# ---------------------------------------------------------------------------
# legacy：評価は 1 列も変わらない（旧い式と一致）。identity が混ざらない
# ---------------------------------------------------------------------------

def _old_rows(t):
    """変更前の sc_tree_to_planning_df の式（要求ベース）。"""
    out = []
    for kind in ("leaf", "dad"):
        for prod in t.products:
            nodes = [nd for nd in t.get_ot_root(prod).walk_preorder()
                     if (not nd.children if kind == "leaf" else nd.node_type == "dad")]
            for nd in nodes:
                cpu = t.cpu_size * nd.bom_qty
                for w in range(len(t.week_labels)):
                    dem = len(nd.psi4demand[w][S]) * cpu
                    ful = len(nd.psi4supply[w][S]) * cpu
                    act = getattr(nd, "_actual_ship", None) or {}
                    out.append((round(dem, 4), round(ful, 4), round(max(0.0, dem - ful), 4),
                                round(ful / dem if dem > 0 else 1.0, 4),
                                round(len(act.get(w, [])) * cpu, 4),
                                round(len(nd.psi4supply[w][CO]) * cpu, 4)))
    return out


@pytest.mark.parametrize("how", ["explicit", "tree_attribute", "not_given"])
def test_legacy_evaluation_is_unchanged(how):
    t = _planned("legacy", mom_cap=1)
    if how == "explicit":
        t.lot_flow_mode = "identity"          # 引数が優先：legacy の試走に identity が混ざらない
        df = sc_tree_to_planning_df(t, lot_flow_mode="legacy")
        kpi = compute_strategic_kpi(t, lot_flow_mode="legacy")
    elif how == "tree_attribute":
        df = sc_tree_to_planning_df(t)
        kpi = compute_strategic_kpi(t)
    else:
        del t.lot_flow_mode                   # 印も引数も無い：これまでどおり要求ベース
        df = sc_tree_to_planning_df(t)
        kpi = compute_strategic_kpi(t)
    got = list(zip(df[Cols.DEMAND_FCST], df[Cols.DEMAND_FULFILLED], df[Cols.STOCKOUT_QTY],
                   df[Cols.FILL_RATE], df[Cols.SHIP_QTY], df["co_qty"]))
    assert got == _old_rows(t)
    assert (df[Cols.QTY_BASIS] == "request").all()         # 要求ベースの旧い評価だと分かる
    assert (df[Cols.REQUEST_QTY] == df[Cols.DEMAND_FULFILLED]).all()
    leaf = _leaf(t)
    assert kpi.fill_rate == min(1.0, sum(len(leaf.psi4supply[w][S]) for w in range(N))
                                / sum(len(leaf.psi4demand[w][S]) for w in range(N)))
    weekly, summary = evaluate_money(df, SKU_MASTER)
    rows = _leaf_rows(df)
    assert build_scenario_money_kpi(summary)["revenue"].iloc[0] == rows[Cols.DEMAND_FULFILLED].sum() * 100.0
    assert (weekly[Cols.QTY_BASIS] == "request").all()


def test_demand_layer_columns_stay_the_request():
    """C3-5：需要の列（demand_fcst・request_qty）は、方式によらず要求のまま。"""
    a, b = _planned("identity", mom_cap=1), _planned("legacy", mom_cap=1)
    da, db = sc_tree_to_planning_df(a), sc_tree_to_planning_df(b)
    assert list(da[Cols.DEMAND_FCST]) == list(db[Cols.DEMAND_FCST])
    assert list(_leaf_rows(da)[Cols.REQUEST_QTY]) == list(_leaf_rows(db)[Cols.REQUEST_QTY])
    leaf = _leaf(a)
    assert list(_leaf_rows(da)[Cols.DEMAND_FCST]) == [len(leaf.psi4demand[w][S]) for w in range(N)]


def test_simulator_rows_without_basis_are_labelled():
    """シミュレーターのシナリオ（qty_basis 列なし）は「simulated」。値は変えない。"""
    df = pd.DataFrame([{Cols.SCENARIO: "Base", Cols.SKU_ID: SKU, Cols.REGION: "JP", Cols.WEEK: WEEKS[0],
                        Cols.DEMAND_FULFILLED: 3.0, Cols.CLOSING_INV: 1.0}])
    weekly, summary = evaluate_money(df, SKU_MASTER)
    assert weekly[Cols.REVENUE].iloc[0] == 300.0 and weekly[Cols.QTY_BASIS].iloc[0] == "simulated"
    assert summary[Cols.QTY_BASIS].iloc[0] == "simulated"


# ---------------------------------------------------------------------------
# C3-4  実モデルのコピーで上流の能力を減らす（原本の能力は変えない）
# ---------------------------------------------------------------------------

def _run_model(model_dir, tmp_path, mode):
    import tools.run_headless_from_folder as rh
    store = {}
    o_sig = rh._psi_signature

    def sig(t, n):
        store["tree"] = t
        return o_sig(t, n)

    rh._psi_signature = sig
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        snap = rh.run(model_dir, plugins_spec="safe", output_ppc_dir=str(tmp_path / f"ppc_{mode}"),
                      verbose=False, lot_flow_mode=mode)
    finally:
        os.chdir(cwd)
        rh._psi_signature = o_sig
    return snap, store["tree"]


def _cut_capacity(model_dir, node, weeks, cap):
    path = os.path.join(model_dir, "capacity_plan.csv")
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    h = rows[0]
    ni, wi, mi = h.index("node_name"), h.index("week"), h.index("max_supply")
    hit = 0
    for r in rows[1:]:
        if r[ni] == node and weeks[0] <= r[wi] <= weeks[1]:
            r[mi] = str(cap)
            hit += 1
    assert hit > 0
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def test_c3_4_capacity_cut_on_a_copy_reaches_node_quantity_and_money(tmp_path):
    src = os.path.join(REPO, "data", "sample", "ev-thailand-2026")
    base_dir, cut_dir = str(tmp_path / "base"), str(tmp_path / "cut")
    shutil.copytree(src, base_dir)
    shutil.copytree(src, cut_dir)
    # 上流（部品）の能力を、計画の終わりまで絞る（コピーだけ）
    _cut_capacity(cut_dir, "Components_CN", ("2027-W20", "2027-W52"), 20)
    sku_master = pd.read_csv(os.path.join(src, "sku_master.csv"))

    res = {}
    for name, d in (("base", base_dir), ("cut", cut_dir)):
        snap, tree = _run_model(d, tmp_path / name if False else tmp_path, "identity")
        assert tree.lot_flow_mode == "identity"           # headless が印を付ける
        df = sc_tree_to_planning_df(tree)
        leaf_rows = _leaf_rows(df)
        imp = leaf_rows[leaf_rows[Cols.SKU_ID] == "EVmaker_Import"]
        ship = sum(len(v) for nd in tree.get_ot_root("EVmaker_Import").walk_preorder() if not nd.children
                   for v in nd._actual_ship.values())
        assert imp[Cols.SHIP_QTY].sum() == ship == imp[Cols.DEMAND_FULFILLED].sum()
        _weekly, summary = evaluate_money(df, sku_master)
        rev = summary[(summary[Cols.SKU_ID] == "EVmaker_Import")
                      & ~summary[Cols.REGION].astype(str).str.startswith("DAD:")][Cols.REVENUE].sum()
        # 中間ノード（DC）の行も、その DC 自身の実出荷
        dc = next(nd for nd in tree.iter_all_nodes("EVmaker_Import") if nd.node_name == "DC_EV_Import")
        dc_rows = df[(df[Cols.SKU_ID] == "EVmaker_Import") & df[Cols.REGION].astype(str).str.startswith("DAD:")]
        assert dc_rows[Cols.SHIP_QTY].sum() == sum(len(v) for v in dc._actual_ship.values())
        res[name] = dict(request=imp[Cols.REQUEST_QTY].sum(), ship=ship, rev=rev,
                         stockout=imp[Cols.STOCKOUT_QTY].sum(),
                         dc_ship=dc_rows[Cols.SHIP_QTY].sum(),
                         ppc_rev=snap["ppc"]["revenue_base"],
                         fill=compute_strategic_kpi(tree, product_filter="EVmaker_Import").fill_rate)
    b, c = res["base"], res["cut"]
    assert b["request"] == c["request"]                    # 要求は同じ
    assert b["ship"] == b["request"] and b["stockout"] == 0 and b["fill"] == 1.0
    assert c["ship"] < b["ship"]                           # 実出荷が減る
    assert c["dc_ship"] < b["dc_ship"]                     # 中間ノードの数量にも届く
    assert c["rev"] < b["rev"]                             # money の売上にも届く
    assert c["rev"] == pytest.approx(b["rev"] * c["ship"] / b["ship"], rel=0.05)
    assert c["stockout"] > 0 and c["fill"] < 1.0
    assert c["ppc_rev"] < b["ppc_rev"]                     # PPC の台帳も同じ向き

    # legacy の同じコピー：評価は要求ベースのまま（能力を絞っても市場の S は同じ）
    _snap, ltree = _run_model(cut_dir, tmp_path, "legacy")
    assert ltree.lot_flow_mode == "legacy"
    ldf = sc_tree_to_planning_df(ltree)
    assert (ldf[Cols.QTY_BASIS] == "request").all()
    limp = _leaf_rows(ldf)
    limp = limp[limp[Cols.SKU_ID] == "EVmaker_Import"]
    assert limp[Cols.DEMAND_FULFILLED].sum() == limp[Cols.REQUEST_QTY].sum() == b["request"]
