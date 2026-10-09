# -*- coding: utf-8 -*-
"""
tests/test_ev_update_kitting.py — RequestLetter_SmartphoneWarmup_EVUpdateKitting_S2 B3・B4

ev-thailand-2026_update の Factory_Local_TH（2 部材 → 1 完成品）を、既存の
Stockyard／Kitting Gate の標準構成にしたことの回帰テスト。

  B3-1  各部材の入庫・払出・残高の保存（Flow Check 表 3 の置場の行）
  B3-2  Gate の成立による完成 ID ＝ Factory の P。1 需要から完成品が 2 つできない
  B3-3  片方の部材を遅らせたコピー：早い部材は置場に残り、そろう前の完成・出荷は 0、
        回復後は同じ ID で充足する
  B3-4  Flow Check の NG が 0（既知の保存差 52,400 が無い）
  B4    供給側の同じ ID の重複の記録：置場を外したコピーで件数が出て、今の構成で 0。
        記録は計画を変えない（legacy・identity とも）
"""
import csv
import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from wom.model.plan_node import S, CO, I, P

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL = os.path.join(REPO, "data", "sample", "ev-thailand-2026_update")
PROD = "EVmaker_Local"
YARDS = ("Platform_Unit_Assy_Yard", "Motor_Unit_Assy_Yard")


def _run(model_dir, tmp_path, mode="identity"):
    """headless 実行。(snapshot, sc_tree, {product: ForwardPlanResult}) を返す。"""
    import tools.run_headless_from_folder as rh
    import wom.engine.forward_planner as fpm
    store = {}
    o_sig, o_run = rh._psi_signature, fpm.ForwardPlanner.run

    def sig(t, n):
        store["tree"] = t
        return o_sig(t, n)

    def frun(self, prod):
        r = o_run(self, prod)
        store.setdefault("fres", {})[prod] = r
        return r

    rh._psi_signature, fpm.ForwardPlanner.run = sig, frun
    cwd = os.getcwd()
    os.chdir(REPO)
    try:
        snap = rh.run(model_dir, plugins_spec="safe", output_ppc_dir=str(tmp_path / "ppc"),
                      verbose=False, lot_flow_mode=mode)
    finally:
        os.chdir(cwd)
        rh._psi_signature, fpm.ForwardPlanner.run = o_sig, o_run
    return snap, store["tree"], store["fres"]


def _node(tree, name, prod=PROD):
    return next(nd for nd in tree.iter_all_nodes(prod) if nd.node_name == name)


def _copy(tmp_path, name="model"):
    dst = str(tmp_path / name)
    shutil.copytree(MODEL, dst)
    return dst


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("evu_base")
    return _run(_copy(tmp), tmp)


def test_tree_uses_the_standard_stockyard_layout():
    with open(os.path.join(MODEL, "sc_tree_master.csv"), encoding="utf-8-sig", newline="") as f:
        rows = {r["node_name"]: r for r in csv.DictReader(f) if r["product_name"] == PROD}
    for yard, part, lt in (("Platform_Unit_Assy_Yard", "Platform_Unit_Assy", "4"),
                           ("Motor_Unit_Assy_Yard", "Motor_Unit_Assy", "1")):
        assert rows[yard]["node_type"] == "stockyard" and rows[yard]["parent_node"] == "Factory_Local_TH"
        assert rows[yard]["lt_wks"] == "0"                      # 経路の LT の合計を変えない
        assert rows[part]["parent_node"] == yard and rows[part]["lt_wks"] == lt
        assert rows[part]["node_type"] == "leaf_in"


def test_flow_check_has_no_ng_and_no_duplicate_ids(base):
    from wom.engine.flow_check import compute_flow_check
    _snap, tree, fres = base
    fc = compute_flow_check(tree, fres)
    assert fc["summary"]["ng"] == 0, [r for r in fc["nodes"] if r["status"] == "NG"]
    assert fc["summary"]["dup_supply_ids"] == 0
    assert all(not r.supply_duplicate_ids for r in fres.values())
    assert fc["summary"]["market_check_nonzero"] == 0
    fac = next(r for r in fc["nodes"] if r["node"] == "Factory_Local_TH")
    assert fac["conservation_diff"] == 0 and fac["status"] == "対象外"
    assert "表 3 の照合は一致" in fac["reason"]


def test_components_are_conserved_and_kits_are_made_once(base):
    from wom.engine.flow_check import compute_kitting_check
    _snap, tree, _fres = base
    rows = [r for r in compute_kitting_check(tree) if r["assembly"] == "Factory_Local_TH"]
    asm = next(r for r in rows if r["row"] == "完成品（組立）")
    yards = {r["node"]: r for r in rows if r["row"] == "部材（置場）"}
    assert set(yards) == set(YARDS)
    for y in yards.values():                                   # B3-1 部材ごとの保存
        assert y["component_diff"] == 0 and y["payout_not_in_kits"] == 0 and y["status"] == "OK"
        assert y["receipt_sum"] == y["payout_sum"] + y["closing_I"]
    # B3-2 完成 ID ＝ Factory の P、二重生成なし
    assert asm["status"] == "OK"
    assert (asm["kits_dup"], asm["incomplete"], asm["premature"]) == (0, 0, 0)
    fac = _node(tree, "Factory_Local_TH")
    p_lots = [lot for w in range(tree.num_weeks()) for lot in fac.psi4supply[w][P]]
    assert len(p_lots) == len(set(p_lots)) == asm["kits"] == 52700
    for y in YARDS:
        paid = [lot for lots in _node(tree, y)._actual_ship.values() for lot in lots]
        assert sorted(paid) == sorted(p_lots)                  # 部材 1 つ ⇔ 完成品 1 つ


def test_market_is_fully_served(base):
    from wom.engine.flow_check import compute_flow_check
    snap, tree, fres = base
    tot = compute_flow_check(tree, fres)["market"][-1]
    assert (tot["demand"], tot["on_time"], tot["late"], tot["backlog_end"]) == (63240, 63240, 0, 0)
    assert snap["ppc"]["revenue_base"] == pytest.approx(319119580000.0)
    assert snap["ppc"]["cost_base"] == pytest.approx(138830903750.0)


def _delay_motor(model_dir, weeks, cap):
    """コピーの capacity_plan.csv で、Motor_Unit_Assy の能力を指定の週だけ絞る。"""
    path = os.path.join(model_dir, "capacity_plan.csv")
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    h = rows[0]
    ni, wi, mi = h.index("node_name"), h.index("week"), h.index("max_supply")
    hit = 0
    for r in rows[1:]:
        if r[ni] == "Motor_Unit_Assy" and r[wi] in weeks:
            r[mi] = str(cap)
            hit += 1
    assert hit == len(weeks)
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def test_late_part_keeps_the_early_part_and_makes_no_kit_until_both_arrive(tmp_path):
    """B3-3：モーターを 3 週間だけ遅らせる（原本は変えない）。"""
    from wom.engine.flow_check import compute_flow_check, compute_kitting_check
    model = _copy(tmp_path)
    delay_weeks = ["2026-W20", "2026-W21", "2026-W22"]
    _delay_motor(model, delay_weeks, 100)
    _snap, tree, fres = _run(model, tmp_path)
    n, wl = tree.num_weeks(), list(tree.week_labels)
    fac = _node(tree, "Factory_Local_TH")
    plat, motor = _node(tree, YARDS[0]), _node(tree, YARDS[1])

    def first_week(node, bucket):
        out = {}
        for w in range(n):
            for lot in node.psi4supply[w][bucket]:
                out.setdefault(lot, w)
        return out

    plat_arr, motor_arr, kit = first_week(plat, P), first_week(motor, P), first_week(fac, P)
    late = [lot for lot in kit if motor_arr[lot] > plat_arr[lot]]
    assert late, "the delay must make the motor arrive after the platform for some Lot_IDs"

    # 早い部材（プラットフォーム）は消えず、モーターを待つ間、置場の I に残る
    for lot in late[:200]:
        for w in range(plat_arr[lot], motor_arr[lot]):
            assert lot in plat.psi4supply[w][I], (lot, wl[w])
    assert max(len(plat.psi4supply[w][I]) for w in range(n)) > 0
    # そろう前の完成・出荷は 0
    ship = {}
    for w, lots in fac._actual_ship.items():
        for lot in lots:
            ship.setdefault(lot, w)
    for lot in late:
        assert kit[lot] >= motor_arr[lot] and ship[lot] >= motor_arr[lot]
    # 回復後は、同じ ID で完成し、1 回だけ作られる
    rows = [r for r in compute_kitting_check(tree) if r["assembly"] == "Factory_Local_TH"]
    asm = next(r for r in rows if r["row"] == "完成品（組立）")
    assert asm["status"] == "OK" and asm["kits"] == 52700
    assert (asm["kits_dup"], asm["incomplete"], asm["premature"]) == (0, 0, 0)
    assert all(r["status"] == "OK" for r in rows)
    # 部材がそろうまで、工場の出荷要求は注文残（CO）になる
    assert max(len(fac.psi4supply[w][CO]) for w in range(n)) > 0
    fc = compute_flow_check(tree, fres)
    assert fc["summary"]["ng"] == 0 and fc["summary"]["dup_supply_ids"] == 0
    tot = fc["market"][-1]
    assert tot["check"] == 0 and tot["demand"] == 63240
    assert tot["on_time"] + tot["late"] + tot["backlog_end"] == 63240


def _remove_yards(model_dir):
    """置場を外した（修正前の）構成のコピーを作る：部材を工場へ直接つなぐ。"""
    path = os.path.join(model_dir, "sc_tree_master.csv")
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    h = rows[0]
    ni, pi = h.index("node_name"), h.index("parent_node")
    out = [h]
    for r in rows[1:]:
        if r[ni] in YARDS:
            continue
        if r[pi] in YARDS:
            r[pi] = "Factory_Local_TH"
        out.append(r)
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(out)


@pytest.mark.parametrize("mode", ["identity", "legacy"])
def test_duplicate_supply_ids_are_recorded_without_the_yards(tmp_path, mode):
    """B4：置場が無い構成では、同じ ID が工場の供給側に 2 件ずつ入る。記録され、
    Flow Check が NG にする。"""
    from wom.engine.flow_check import compute_flow_check
    model = _copy(tmp_path)
    _remove_yards(model)
    _snap, tree, fres = _run(model, tmp_path, mode)
    dups = fres[PROD].supply_duplicate_ids
    assert len(dups) == 52400
    assert all(nid.startswith("IN:mom:Factory_Local_TH") and cnt == 2 for nid, _w, _lot, cnt in dups)
    assert not fres["EVmaker_Import"].supply_duplicate_ids
    fc = compute_flow_check(tree, fres)
    fac = next(r for r in fc["nodes"] if r["node"] == "Factory_Local_TH")
    assert fac["dup_supply_ids"] == 52400 and fac["status"] == "NG"
    assert "同じ ID が供給側に 2 件以上" in fac["reason"]
    assert fc["summary"]["dup_supply_ids"] == 52400


def test_recording_duplicates_does_not_change_the_plan():
    """B4：記録だけ。重複のある合成の供給でも、照合の結果は記録の有無で変わらない。"""
    from wom.engine.forward_planner import ForwardPlanner, ForwardPlanResult
    r = ForwardPlanResult(prod_nm="X")
    r.record_supply_duplicates("N", "2026-W01", ["a", "b", "a", "c", "a", "b"])
    assert sorted(r.supply_duplicate_ids) == [("N", "2026-W01", "a", 3), ("N", "2026-W01", "b", 2)]
    m, ud, us = ForwardPlanner._match_by_identity(["a", "b", "z"], ["a", "b", "a", "c", "a", "b"])
    assert (m, ud, us) == (["a", "b"], ["z"], ["c"])      # 2 件目以降の a・b は在庫にも残らない


# ---------------------------------------------------------------------------
# RequestLetter_StalePPC_Units_KittingView P5：表 3 の「完成した ID の数 ＝ 組立の P Σ」
# ---------------------------------------------------------------------------

def test_table3_completed_ids_equal_assembly_p(base):
    from wom.engine.flow_check import compute_flow_check, KITTING_COLUMNS
    _snap, tree, fres = base
    fc = compute_flow_check(tree, fres)
    rows = [r for r in fc["kitting"] if r["assembly"] == "Factory_Local_TH"]
    asm = next(r for r in rows if r["row"] == "完成品（組立）")
    assert asm["completed_ids"] == asm["assembly_p_sum"] == 52700
    assert asm["completed_minus_p"] == 0 and asm["status"] == "OK"
    yards = [r for r in rows if r["row"] == "部材（置場）"]
    assert [r["node"] for r in yards] == list(YARDS)                 # 置場 2 つの行
    assert all((r["receipt_sum"], r["payout_sum"], r["closing_I"]) == (52700, 52700, 0) for r in yards)
    assert {"completed_ids", "assembly_p_sum", "completed_minus_p"} <= set(KITTING_COLUMNS)
    # Kitting の無い製品（EVmaker_Import）の行は無い
    assert {r["product"] for r in fc["kitting"]} == {PROD}


def test_table3_flags_a_difference_between_completed_ids_and_p(base):
    """完成した ID と組立の P が食い違えば NG（P から 1 件を抜いて確かめ、元に戻す）。"""
    from wom.engine.flow_check import compute_flow_check, compute_kitting_check
    _snap, tree, fres = base
    fac = _node(tree, "Factory_Local_TH")
    w = next(w for w in range(tree.num_weeks()) if fac.psi4supply[w][P])
    lot = fac.psi4supply[w][P].pop()
    try:
        asm = next(r for r in compute_kitting_check(tree)
                   if r["assembly"] == "Factory_Local_TH" and r["row"] == "完成品（組立）")
        assert asm["completed_minus_p"] == 1 and asm["status"] == "NG"
        assert "完成した ID の数と P Σ の差" in asm["reason"]
        fc = compute_flow_check(tree, fres)
        fac_row = next(r for r in fc["nodes"] if r["node"] == "Factory_Local_TH")
        assert fac_row["status"] == "NG" and fc["summary"]["kitting_ng"] >= 1
    finally:
        fac.psi4supply[w][P].append(lot)
    assert compute_flow_check(tree, fres)["summary"]["kitting_ng"] == 0


def test_model_without_kitting_has_no_table3_rows():
    import pandas as pd
    from wom.model.sc_tree import build_demo_sc_tree
    from wom.engine.flow_check import compute_flow_check
    weeks = [f"2024-W{i:02d}" for i in range(1, 9)]
    tree = build_demo_sc_tree(pd.DataFrame([{"sku_id": "A", "sku_name": "A", "region": "JP",
                                             "lead_time_wks": 1}]), weeks)
    fc = compute_flow_check(tree, {})
    assert fc["kitting"] == [] and fc["summary"]["kitting_assemblies"] == 0
