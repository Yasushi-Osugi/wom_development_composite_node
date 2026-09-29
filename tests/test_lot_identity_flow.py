# -*- coding: utf-8 -*-
"""
tests/test_lot_identity_flow.py — RequestLetter_LotIdentityFlow (C1-C5, K1-K6)
Decision record: docs/design/WOM_Forward_LotID_Decision_Record_2026-09-29.md

  Unit        : demo tree (SP -> DC(dad, decouple) -> Sales ; MFG(mom) -> T1 -> RAW)
  Integration : planning_config.csv -> headless runner -> ForwardPlanner;
                PPC bridge reads the actual shipment
  E2E golden  : tests/test_golden.py runs every golden in its recorded mode
                (legacy for all existing goldens)
"""
import os
import shutil
import sys
import warnings
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from wom.model.plan_node import S, CO, I, P
from wom.model.sc_tree import build_demo_sc_tree
from wom.model.lot_generator import assign_demand_lots_from_dict
from wom.engine.backward_planner import BackwardPlanner
from wom.engine.plan_copy import copy_demand_to_supply
from wom.engine.forward_planner import (ForwardPlanner, resolve_lot_flow_mode,
                                        DEFAULT_LOT_FLOW_MODE)
from wom.engine.push_pull import PushConfig, PushProductionPlanner

SKU = "SKU-A"
N = 26
WEEKS = [f"2024-W{i:02d}" for i in range(1, N + 1)]
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _tree(demand=None):
    rows = [{"sku_id": SKU, "sku_name": "A", "region": "JP", "lead_time_wks": 1}]
    t = build_demo_sc_tree(pd.DataFrame(rows), WEEKS, lt_wks_ot=1, lt_wks_in=2)
    assign_demand_lots_from_dict(t, demand or {(SKU, "JP", "2024-W10"): 4,
                                               (SKU, "JP", "2024-W12"): 4}, cpu_size=1)
    BackwardPlanner(t, config={"mom_constrained": False}).run(SKU)
    copy_demand_to_supply(t, SKU)
    return t


def _node(t, name_prefix):
    return next(n for n in t.iter_all_nodes(SKU) if n.node_name.startswith(name_prefix))


def _plan(mode, mom_cap=None, push=None, close=None):
    t = _tree()
    if push is not None:
        PushProductionPlanner(t).setup(SKU, push)
    mom = _node(t, "Mother Plant")
    if mom_cap is not None:
        for w in range(N):
            mom.set_capacity(w, cap_hard=float(mom_cap))
    if close is not None:
        close(t)
    fp = ForwardPlanner(t, lot_flow_mode=mode)
    res = fp.run(SKU)
    return t, fp, res


def _ids(node, bucket):
    return [x for w in range(N) for x in node.psi4supply[w][bucket]]


# ---------------------------------------------------------------------------
# C1  the switch
# ---------------------------------------------------------------------------

def test_c1_mode_resolution():
    assert DEFAULT_LOT_FLOW_MODE == "identity"
    assert resolve_lot_flow_mode(None) == "identity"
    assert resolve_lot_flow_mode("") == "identity"
    assert resolve_lot_flow_mode("Legacy") == "legacy"
    with pytest.raises(ValueError):
        resolve_lot_flow_mode("fifo")
    assert ForwardPlanner(_tree()).lot_flow_mode == "identity"


# ---------------------------------------------------------------------------
# C3  below the decouple point: legacy copies demand P, identity propagates
# ---------------------------------------------------------------------------

def test_c3_downstream_receives_parent_actual_only():
    for mode in ("legacy", "identity"):
        t, fp, _res = _plan(mode, mom_cap=2)          # upstream can ship 2 of 4 per week
        leaf, dc = _node(t, "Sales JP"), _node(t, "DC JP")
        leaf_actual = sum(len(v) for v in fp._actual_s.get(leaf.node_id, {}).values())
        dc_actual = sum(len(v) for v in fp._actual_s.get(dc.node_id, {}).values())
        if mode == "legacy":
            # exception 2: the leaf gets demand P and ships everything, although
            # the DC above it shipped less
            assert leaf_actual == 8 and dc_actual < 8
        else:
            # K1: every lot the leaf received was shipped by the DC, LT later
            assert leaf_actual <= dc_actual
            dc_ship = Counter(x for v in fp._actual_s[dc.node_id].values() for x in v)
            leaf_p = Counter(_ids(leaf, P))
            assert not (leaf_p - dc_ship), "leaf P must come from the DC's actual shipment"
            for w in range(N):
                for lot in leaf.psi4supply[w][P]:
                    assert lot in fp._actual_s[dc.node_id].get(w - leaf.lt_wks, [])
            # the shortage is visible at the market: Addendum1 A1 defers the
            # over-capacity production, so here it shows as LATE shipments
            # (shipped after the lot's S week; its request waits in CO meanwhile)
            s_week = {x: w for w in range(N) for x in leaf.psi4supply[w][S]}
            late = [x for w, v in fp._actual_s[leaf.node_id].items() for x in v
                    if w > s_week[x]]
            assert late
            assert any(leaf.psi4supply[w][CO] for w in range(N))


def test_c3_in_transit_at_end_is_recorded_not_dropped():
    t = _tree({(SKU, "JP", "2024-W26"): 3})
    # the DC ships in the last week; its child LT pushes arrival past the horizon
    dc, leaf = _node(t, "DC JP"), _node(t, "Sales JP")
    fp = ForwardPlanner(t, lot_flow_mode="identity")
    fp._actual_s = {dc.node_id: {N - 1: ["X1", "X2"]}}
    from wom.engine.forward_planner import ForwardPlanResult
    res = ForwardPlanResult(prod_nm=SKU)
    fp._propagate_to_child(dc, leaf, N, res)
    assert res.ot_in_transit_at_end == [(dc.node_id, leaf.node_id, WEEKS[N - 1], 2)]


# ---------------------------------------------------------------------------
# C2  push buffer matches by Lot_ID and keeps CO
# ---------------------------------------------------------------------------

def _mode4():
    return PushConfig(node_id=f"IN:MFG:{SKU}", sku_id=SKU, push_lead_time_weeks=4)


def test_c2_push_buffer_ships_only_requested_ids_and_keeps_co():
    t, fp, _res = _plan("identity", push=_mode4())
    mom = _node(t, "Mother Plant")
    assert mom.plan_mode == "push"
    for w in range(N):
        req = Counter(mom.psi4supply[w][S]) + Counter(mom.psi4supply[w][CO])
        assert not (Counter(fp._actual_s[mom.node_id].get(w, [])) - req), "K5: no early shipment"
        co = mom.psi4supply[w][CO]
        assert len(co) == len(set(co)), "K4: CO holds each Lot_ID once"
    assert mom._actual_ship is fp._actual_s[mom.node_id]


def test_c2_legacy_push_is_unchanged_arrival_order():
    t, fp, _res = _plan("legacy", push=PushConfig(node_id=f"IN:MFG:{SKU}", sku_id=SKU,
                                                  push_qty_per_week=6))
    mom = _node(t, "Mother Plant")
    assert all(mom.psi4supply[w][CO] == [] for w in range(N)), "legacy push keeps no CO"


def test_k2_k6_closed_push_week_keeps_thing_in_i_and_request_in_co():
    base_t, base_fp, _ = _plan("identity", push=_mode4())
    bmom = _node(base_t, "Mother Plant")
    wc = next(w for w in range(1, N - 2) if base_fp._actual_s[bmom.node_id].get(w))

    def close(t):
        m = _node(t, "Mother Plant")
        m.set_operating_shifts(wc, 0)
        m.set_operating_shifts(wc + 1, 0)

    t, fp, res = _plan("identity", push=_mode4(), close=close)
    mom = _node(t, "Mother Plant")
    assert fp._actual_s[mom.node_id].get(wc) == [] and fp._actual_s[mom.node_id].get(wc + 1) == [], "K6"
    # second closed week: the same Lot_ID is in I (thing) and CO (request)
    both = set(mom.psi4supply[wc + 1][I]) & set(mom.psi4supply[wc + 1][CO])
    assert both, "I and CO hold the same Lot_ID while shipping is stopped (K2, allowed)"
    # when it ships, it leaves I and CO in the same week
    for lot in both:
        s = next(w for w in range(wc + 2, N) if lot in fp._actual_s[mom.node_id].get(w, []))
        assert lot not in mom.psi4supply[s][I]
        assert s + 1 >= N or lot not in mom.psi4supply[s + 1][CO]


# ---------------------------------------------------------------------------
# C4  PPC reads the actual shipment
# ---------------------------------------------------------------------------

def test_c4_ppc_bridge_counts_actual_shipment():
    from wom.ppc.ppc_psi_bridge import psi_to_sales_records
    t, fp, _res = _plan("identity", mom_cap=2)
    leaf = _node(t, "Sales JP")
    df = psi_to_sales_records(t, WEEKS, use_node_name=True)
    shipped = sum(len(v) for v in fp._actual_s[leaf.node_id].values())
    assert int(df["qty"].sum()) == shipped
    # week by week the bridge follows the actual shipment, not the S plan
    by_week = df.groupby("week")["qty"].sum().to_dict()
    actual_by_week = {WEEKS[w]: len(v) for w, v in fp._actual_s[leaf.node_id].items() if v}
    plan_by_week = {WEEKS[w]: len(leaf.psi4supply[w][S]) for w in range(N) if leaf.psi4supply[w][S]}
    assert {k: int(v) for k, v in by_week.items() if v} == actual_by_week != plan_by_week
    # legacy: leaf S == actual, so the bridge total equals the planned S
    t2, fp2, _ = _plan("legacy", mom_cap=2)
    df2 = psi_to_sales_records(t2, WEEKS, use_node_name=True)
    assert int(df2["qty"].sum()) == len(_ids(_node(t2, "Sales JP"), S))


# ---------------------------------------------------------------------------
# C5  Modes 1-3 are deprecated (warning only)
# ---------------------------------------------------------------------------

def test_c5_mode1_to_3_warn_mode4_does_not():
    t = _tree()
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        r = PushProductionPlanner(t).setup(SKU, PushConfig(node_id=f"IN:MFG:{SKU}", sku_id=SKU,
                                                           push_qty_per_week=6))
    assert r.deprecation_warnings and any("非推奨" in str(w.message) for w in rec)
    t = _tree()
    r4 = PushProductionPlanner(t).setup(SKU, _mode4())
    assert r4.deprecation_warnings == []


# ---------------------------------------------------------------------------
# Addendum1 A1  Step 0a in identity: defer the excess to next week's P head
# ---------------------------------------------------------------------------

def _co_duplicates(t):
    return sum(c - 1 for n in t.iter_all_nodes(SKU) for w in range(N)
               for c in Counter(n.psi4supply[w][CO]).values() if c > 1)


def test_a1_identity_cap_hard_does_not_duplicate_co_and_loses_no_lot():
    t, fp, res = _plan("identity", mom_cap=2)
    mom = _node(t, "Mother Plant")
    assert res.cap_hard_sealed > 0, "the cap binds in this setup"
    assert _co_duplicates(t) == 0, "K4: CO holds each request once"
    assert all(len(mom.psi4supply[w][P]) <= 2 for w in range(N))
    # deferred, not dropped: every requested lot is eventually produced (horizon allows)
    shipped = Counter(x for v in fp._actual_s[mom.node_id].values() for x in v)
    assert sum(shipped.values()) == 8 and max(shipped.values()) == 1
    assert res.cap_hard_unplaced == []
    # legacy keeps the known defect (sealed P lot -> CO while its request is in S)
    t2, _fp2, _res2 = _plan("legacy", mom_cap=2)
    assert _co_duplicates(t2) > 0


def _bare_node():
    t = _tree({(SKU, "JP", "2024-W20"): 1})
    mom = _node(t, "Mother Plant")
    for w in range(N):
        for b in (S, CO, I, P):
            mom.psi4supply[w][b] = []
    return t, mom


def _fp(t, mode):
    fp = ForwardPlanner(t, lot_flow_mode=mode)
    fp._actual_s = {}          # normally initialised by run()
    return fp


def test_a1_excess_goes_to_head_of_next_p_and_end_of_horizon_is_recorded():
    from wom.engine.forward_planner import ForwardPlanResult
    t, mom = _bare_node()
    mom.psi4supply[5][P] = ["a", "b", "c"]
    mom.psi4supply[6][P] = ["d"]
    mom.set_capacity(5, cap_hard=2.0)
    mom.psi4supply[N - 1][P] = ["x", "y", "z"]
    mom.set_capacity(N - 1, cap_hard=1.0)
    fp = _fp(t, "identity")
    res = ForwardPlanResult(prod_nm=SKU)
    fp._process_node(mom, N, res, [])
    assert mom.psi4supply[5][P] == ["a", "b"]
    assert mom.psi4supply[6][P] == ["c", "d"], "older (deferred) lot first"
    assert all(mom.psi4supply[w][CO] == [] for w in range(N))
    assert res.cap_hard_unplaced == [(mom.node_id, WEEKS[N - 1], ["y", "z"])]
    assert res.co_generated == 0


def test_a1_e2_closure_deferral_goes_to_head_in_identity_tail_in_legacy():
    from wom.engine.forward_planner import ForwardPlanResult
    for mode, expect in (("identity", ["a", "b"]), ("legacy", ["b", "a"])):
        t, mom = _bare_node()
        mom.psi4supply[5][P] = ["a"]
        mom.psi4supply[6][P] = ["b"]
        mom.set_operating_shifts(5, 0)
        fp = _fp(t, mode)
        fp._process_node(mom, N, ForwardPlanResult(prod_nm=SKU), [])
        assert mom.psi4supply[6][P] == expect, mode


def test_a1_carry_over_from_several_weeks_keeps_oldest_first():
    """Addendum1 v1.1 A1-2: lots carried from several weeks keep their order
    (the older week's lot first)."""
    from wom.engine.forward_planner import ForwardPlanResult
    t, mom = _bare_node()
    mom.psi4supply[5][P] = ["a1", "a2", "a3"]
    mom.psi4supply[6][P] = ["b1", "b2"]
    mom.psi4supply[7][P] = ["c1"]
    for w in range(5, 11):
        mom.set_capacity(w, cap_hard=1.0)
    fp = _fp(t, "identity")
    res = ForwardPlanResult(prod_nm=SKU)
    fp._process_node(mom, N, res, [])
    produced = [mom.psi4supply[w][P] for w in range(5, 12)]
    assert produced == [["a1"], ["a2"], ["a3"], ["b1"], ["b2"], ["c1"], []]
    assert [e[2] for e in res.cap_hard_events] == [2, 3, 3, 2, 1]   # lots over cap per week
    assert all(mom.psi4supply[w][CO] == [] for w in range(N))


def test_a1_excess_into_closed_week_is_handed_on_by_e2():
    from wom.engine.forward_planner import ForwardPlanResult
    t, mom = _bare_node()
    mom.psi4supply[5][P] = ["a", "b", "c"]
    mom.psi4supply[6][P] = ["d"]
    mom.psi4supply[7][P] = ["e"]
    mom.set_capacity(5, cap_hard=2.0)
    mom.set_operating_shifts(6, 0)
    fp = _fp(t, "identity")
    fp._process_node(mom, N, ForwardPlanResult(prod_nm=SKU), [])
    assert mom.psi4supply[6][P] == []
    assert mom.psi4supply[7][P] == ["c", "d", "e"], "arrival order kept across the closed week"


# ---------------------------------------------------------------------------
# Addendum1 A3  decouple placement is evaluated in legacy whatever the run mode
# ---------------------------------------------------------------------------

def test_a3_plugin_evaluates_in_legacy_even_for_identity_runs(tmp_path, monkeypatch):
    import wom.engine.decouple_optimizer as dopt
    from wom.plugins.buffering_stock_optimizer import BufferingStockOptimizerPlugin
    seen = []
    orig = dopt.evaluate_decouple_placement

    def spy(*a, **k):
        seen.append(k.get("lot_flow_mode"))
        return orig(*a, **k)

    monkeypatch.setattr(dopt, "evaluate_decouple_placement", spy)
    t = _tree()
    pd.DataFrame([{"sku_id": SKU, "enabled": 1}]).to_csv(
        tmp_path / "decouple_optimizer_config.csv", index=False)
    plugin = BufferingStockOptimizerPlugin()
    plugin.on_post_backward(
        t, SKU, WEEKS, {"cap_path": str(tmp_path / "capacity_plan.csv"),
                        "lot_flow_mode": "identity"})
    # candidates: legacy (reference); the chosen placement: re-evaluated in identity (D6)
    assert len(seen) >= 2 and set(seen[:-1]) == {"legacy"} and seen[-1] == "identity"
    rec = plugin.last_results[SKU]
    assert rec["run_lot_flow_mode"] == "identity" and rec["re_evaluated"] is not None
    assert rec["re_evaluated"].decouple_node_ids == rec["legacy_reference"].decouple_node_ids
    # supply layer left cleared for the pipeline's copy_demand_to_supply
    assert all(n.psi4supply[w][b] == [] for n in t.iter_all_nodes(SKU)
               for w in range(N) for b in (S, CO, I, P))
    # a legacy run does not re-evaluate
    seen.clear()
    plugin.on_post_backward(
        _tree(), SKU, WEEKS, {"cap_path": str(tmp_path / "capacity_plan.csv"),
                              "lot_flow_mode": "legacy"})
    assert set(seen) == {"legacy"} and plugin.last_results[SKU]["re_evaluated"] is None


# ---------------------------------------------------------------------------
# Integration: planning_config.csv -> headless -> ForwardPlanner
# ---------------------------------------------------------------------------

def test_integration_planning_config_selects_mode(tmp_path, monkeypatch):
    import tools.run_headless_from_folder as rh
    import wom.engine.forward_planner as fpm
    src = os.path.join(REPO, "data", "sample", "bom-test-2026")
    seen = []
    orig = fpm.ForwardPlanner.run

    def spy(self, prod):
        seen.append(self.lot_flow_mode)
        return orig(self, prod)

    monkeypatch.setattr(fpm.ForwardPlanner, "run", spy)
    for value, expect in (("legacy", "legacy"), (None, "identity")):
        d = tmp_path / f"m_{expect}"
        shutil.copytree(src, d)
        cfg = d / "planning_config.csv"
        rows = []
        if cfg.exists():
            rows = [r for r in cfg.read_text(encoding="utf-8").splitlines()
                    if r and not r.startswith("lot_flow_mode")]
        if not rows:
            rows = ["key,value"]
        if value:
            rows.append(f"lot_flow_mode,{value}")
        cfg.write_text("\n".join(rows) + "\n", encoding="utf-8")
        seen.clear()
        snap = rh.run(str(d), plugins_spec="none", output_ppc_dir=str(tmp_path / f"ppc_{expect}"),
                      verbose=False)
        assert set(seen) == {expect}
        assert snap["config"].get("lot_flow_mode", "legacy") == expect
    # an explicit argument wins over planning_config.csv
    seen.clear()
    rh.run(str(tmp_path / "m_legacy"), plugins_spec="none",
           output_ppc_dir=str(tmp_path / "ppc_x"), verbose=False, lot_flow_mode="identity")
    assert set(seen) == {"identity"}
