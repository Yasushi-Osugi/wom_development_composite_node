# -*- coding: utf-8 -*-
"""RequestLetter_RiceSeasonal_Implementation — the Rice upper layer (module + plugin).

Unit        : timings (two dates, closures), aggregation and expansion to the
              original IDs, staged solve (served / earliest / proportional),
              shortages by cause (K-R4), shared mill once (K-R5), mass (K-R6).
Integration : the rice_*.csv inputs -> load_inputs -> problem on the plan tree.
E2E         : the plugin in a headless plan of the one-ID fixture (K-R1, K-R2)
              and of the migration copy of Rice (K-R10); Forward as an
              independent gate (K-R7).
The hand values come from data/trial/rice-seasonal-one-id/scenario.json
("expected" is never changed to fit a result).
"""
from __future__ import annotations

import csv
import json
import os
import shutil
from fractions import Fraction

import pytest

from wom.capacity_layer import rice_seasonal as rs

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ONE = os.path.join(REPO, "data", "trial", "rice-seasonal-one-id")
SPEC = json.load(open(os.path.join(ONE, "scenario.json"), encoding="utf-8"))
HAND = SPEC["expected"]
LOT = HAND["lot_id"]


def _w(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, header, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def make_model(tmp, *, products=("Koshihikari",), shared_mill=True, demand=None,
               storage="100/9", lookback=None, max_storage=None, polish_adv=None, harvest=None,
               crop="100/3", mill_week_zero=None, other=None, white=None):
    """A copy of the one-ID fixture with the Rice inputs written from scenario.json.

    Sol's lookback (13) counts harvest -> request; here the window is
    lookback + route lead time (1+1+2+1+1 = 6), so 7 reproduces it.
    """
    d = os.path.join(str(tmp), "model")
    shutil.copytree(ONE, d)
    pol = SPEC["policy"]
    if len(products) > 1 or demand:
        tree_rows = list(csv.DictReader(open(os.path.join(ONE, "sc_tree_master.csv"), encoding="utf-8")))
        allr = []
        for p in products:
            for r in tree_rows:
                allr.append({**r, "product_name": p})
        _w(os.path.join(d, "sc_tree_master.csv"), list(tree_rows[0]), allr)
        cap = list(csv.DictReader(open(os.path.join(ONE, "capacity_plan.csv"), encoding="utf-8")))
        _w(os.path.join(d, "capacity_plan.csv"), list(cap[0]),
           [{**r, "sku_id": p} for p in products for r in cap])
        dem = list(csv.DictReader(open(os.path.join(ONE, "demand_forecast.csv"), encoding="utf-8")))
        rows = []
        for p in products:
            for r in dem:
                q = int(r["quantity"])
                if demand and r["week"] in demand:
                    q = demand[r["week"]]
                rows.append({**r, "sku_id": p, "quantity": q})
        _w(os.path.join(d, "demand_forecast.csv"), list(dem[0]), rows)
    _w(os.path.join(d, "rice_seasonal_config.csv"), ["key", "value"], [
        {"key": "harvest_lookback_weeks", "value": 7 if lookback is None else lookback},
        {"key": "max_brown_storage_weeks", "value": pol["max_brown_storage_weeks"] if max_storage is None else max_storage},
        {"key": "max_polish_advance_weeks", "value": pol["max_polish_advance_weeks"] if polish_adv is None else polish_adv}])
    # the report start lives in vc_config.csv (one place, RequestLetter_RiceSeasonal_PolishAdvance1 work 5)
    _w(os.path.join(d, "vc_config.csv"), ["key", "value"], [{"key": "report_start", "value": SPEC["report_start"]}])
    _w(os.path.join(d, "rice_recipe.csv"), ["product", "white_kg_per_lot", "milling_yield"],
       [{"product": p, "white_kg_per_lot": SPEC["white_kg_per_lot"], "milling_yield": SPEC["milling_yield"]}
        for p in products])
    res, rmap = [], []
    other = SPEC["other_raw_capacity_kg_week"] if other is None else other
    white = SPEC["white_capacity_kg_week"] if white is None else white
    for p in products:
        sfx = "" if shared_mill else f"_{p}"
        for role, node, rid, kind, unit, dflt in (
                ("harvest", "Tanbo_Niigata", f"FIELD_{p}", "raw_kg_week", "raw_kg", "0"),
                ("collection", "Sanchiku_Niigata", f"COLLECT_{p}", "raw_kg_week", "raw_kg", other),
                ("store_receipt", "Genmai_Souko_Niigata", f"RECEIPT_{p}", "raw_kg_week", "raw_kg", other),
                ("storage", "Genmai_Souko_Niigata", f"STORE_{p}", "brown_stock_kg", "raw_kg", storage),
                ("polish", "Seihaku_W", f"MILL_W{sfx}", "raw_kg_week", "raw_kg", other),
                ("dc", "DC_Nishi", f"DC_{p}", "white_kg_week", "white_kg", white),
                ("market", "Retail_KANSAI", f"MKT_{p}", "white_kg_week", "white_kg", white)):
            if rid not in {r["resource_id"] for r in res}:
                res.append({"resource_id": rid, "kind": kind, "capacity_unit": unit, "default_capacity": dflt})
            rmap.append({"product": p, "node_name": node, "role": role, "resource_id": rid})
    _w(os.path.join(d, "rice_resources.csv"), ["resource_id", "kind", "capacity_unit", "default_capacity"], res)
    _w(os.path.join(d, "rice_resource_map.csv"), ["product", "node_name", "role", "resource_id"], rmap)
    hw = SPEC["harvest_weeks"] if harvest is None else harvest
    caprows = [{"resource_id": f"FIELD_{p}", "week": w, "capacity": SPEC["harvest_capacity_raw_kg"],
                "crop_season": "2026"} for p in products for w in hw]
    if mill_week_zero:
        caprows.append({"resource_id": "MILL_W" if shared_mill else f"MILL_W_{products[0]}",
                        "week": mill_week_zero, "capacity": "0", "crop_season": ""})
    _w(os.path.join(d, "rice_resource_capacity.csv"), ["resource_id", "week", "capacity", "crop_season"], caprows)
    _w(os.path.join(d, "rice_crop_limit.csv"), ["resource_id", "crop_season", "limit", "unit"],
       [{"resource_id": f"FIELD_{p}", "crop_season": "2026", "limit": crop, "unit": "raw_kg"} for p in products])
    return d


def headless(model, plugin=True):
    import tools.run_headless_from_folder as rh
    import wom.engine.forward_planner as fpm
    st = {"fres": {}}
    o_sig, o_run = rh._psi_signature, fpm.ForwardPlanner.run

    def sig(t, n):
        st["tree"] = t
        return o_sig(t, n)

    def frun(self, prod):
        r = o_run(self, prod)
        st["fres"][prod] = r
        return r
    rh._psi_signature, fpm.ForwardPlanner.run = sig, frun
    try:
        snap = rh.run(model, plugins_spec="RiceSeasonalPlugin" if plugin else "none",
                      output_ppc_dir=os.path.join(model, "_ppc"), verbose=False)
    finally:
        rh._psi_signature, fpm.ForwardPlanner.run = o_sig, o_run
    return snap, st["tree"], st["fres"]


def market_outcome(tree):
    out = {"on_time": 0, "late": 0, "early": 0, "backlog_end": 0}
    for p in tree.products:
        for nd in tree.iter_all_nodes(p):
            if nd.node_type != "leaf_out":
                continue
            ship = {l: w for w, ls in nd._actual_ship.items() for l in ls}
            for d in range(tree.num_weeks()):
                for l in nd.psi4demand[d][0]:
                    s = ship.get(l)
                    out["on_time" if s == d else "late" if s is not None and s > d
                        else "early" if s is not None else "backlog_end"] += 1
    return out


def reforward(tree, product):
    """Re-run copy + Forward on a tree that was already planned once.

    copy_demand_to_supply only writes the weeks that have demand, so the supply
    of the earlier run is cleared first (a fresh plan starts empty anyway)."""
    from wom.engine.plan_copy import copy_demand_to_supply
    from wom.engine.forward_planner import ForwardPlanner
    for nd in tree.iter_all_nodes(product):
        nd.psi4supply = [[[], [], [], []] for _ in range(tree.num_weeks())]
        nd._actual_ship = {}
    copy_demand_to_supply(tree, product)
    return ForwardPlanner(tree, lot_flow_mode="identity").run(product)


def problem(model):
    _s, tree, _f = headless(model, plugin=False)
    inputs = rs.load_inputs(model, list(tree.week_labels))
    rp = rs.build_problem(tree, list(tree.products), inputs)
    return tree, rp


# ── K-R1 / K-R2: the one ID, end to end with the plugin ────────────────────
def test_k_r1_one_id_hand_calculation_through_the_plugin(tmp_path):
    from tools.rice_seasonal_check import flow_identities
    from wom.model.plan_node import I, P
    snap, tree, fres = headless(make_model(tmp_path))
    wl = tree.week_labels
    rows = tree.rice_seasonal_results["Koshihikari"]["rows"]
    assert [r["lot_id"] for r in rows] == [LOT]
    t = rows[0]["timing"]
    assert [wl[x] for x in (t.harvest, t.collection, t.store_arrival, t.store_departure, t.polish, t.dc)] == [
        HAND[k] for k in ("harvest", "collection", "store_arrival", "store_departure", "polish", "dc")]
    nodes = {n.node_name: n for n in tree.iter_all_nodes("Koshihikari")}
    store = nodes["Genmai_Souko_Niigata"]
    assert [wl[w] for w in range(len(wl)) if store.psi4supply[w][I]] == HAND["brown_inventory_weeks"]
    assert all(store.psi4supply[w][I] in ([], [LOT]) for w in range(len(wl)))
    assert nodes["Retail_KANSAI"]._actual_ship[wl.index(HAND["market"])] == [LOT]
    assert market_outcome(tree) == {"on_time": 1, "late": 0, "early": 0, "backlog_end": 0}
    errs, _ex = flow_identities(tree, fres)
    assert errs == {}                                         # P = upstream actual + LT, I/CO identities
    assert fres["Koshihikari"].opening_inv_counts == {} and snap["forward"]["cap_hard_deferred_lots"] == 0
    # physical: 100/9 kg brown for 5 weeks; milling gives 10 kg white + 10/9 kg other
    rp = tree.rice_seasonal_results["_problem"]
    led = rs.physical_ledger(rp, rows)
    wh = [r for r in led if r.get("brown_warehouse")]
    assert [r["week"] for r in wh] == HAND["brown_inventory_weeks"]
    assert all(Fraction(r["brown_warehouse"]).limit_denominator(1000) == Fraction(100, 9) for r in wh)
    rec = rp.inputs.recipes["Koshihikari"]
    assert rec.raw_kg_per_lot == Fraction(100, 9) and rec.raw_kg_per_lot - rec.white_kg_per_lot == Fraction(10, 9)
    assert tree.rice_seasonal_results["_solution"].objective["brown_kg_weeks"] == pytest.approx(500 / 9)


def test_plugin_off_plan_cannot_assign_the_past_harvest(tmp_path):
    _s, tree, _f = headless(make_model(tmp_path), plugin=False)
    assert market_outcome(tree)["backlog_end"] == 1


# ── K-R4: shortages by cause, the IDs stay listed ──────────────────────────
@pytest.mark.parametrize("case,kw,reason", [
    ("harvest", {"harvest": []}, "no_feasible_option"),
    ("storage", {"storage": "10"}, "capacity_or_crop"),
    ("age", {"max_storage": 4}, "no_feasible_option"),
    ("lookback", {"lookback": 3}, "no_feasible_option"),
    ("mill", {"mill_week_zero": "2026-W52"}, "capacity_or_crop"),
])
def test_k_r4_shortage_causes_keep_the_id(tmp_path, case, kw, reason):
    tree, rp = problem(make_model(tmp_path, **kw))
    sol = rs.solve(rp)
    rows = rs.expand(rp, sol)
    assert sol.served == 0 and [(r["lot_id"], r["status"], r["reason"]) for r in rows] == [
        (LOT, "unallocated", reason)]


def test_k_r4_mill_closed_week_can_use_an_earlier_milling_week_when_allowed(tmp_path):
    tree, rp = problem(make_model(tmp_path, mill_week_zero="2026-W52", polish_adv=1))
    sol = rs.solve(rp)
    t = rs.expand(rp, sol)[0]["timing"]
    assert sol.served == 1 and rp.weeks[t.polish] == "2026-W51"
    assert sol.objective["milling_advance_lot_weeks"] == 1


def test_k_r4_crop_season_limit_is_separate_from_weekly_harvest(tmp_path):
    # two IDs, weekly harvest allows one per week (3 weeks), the crop only one
    tree, rp = problem(make_model(tmp_path, demand={"2027-W01": 2}, crop="100/9"))
    sol = rs.solve(rp)
    assert sol.served == 1 and sum(sol.unallocated.values()) == 1


def test_k_r4_plan_start_edge_has_no_option(tmp_path):
    # a request in 2026-W44 cannot be reached from any harvest inside the plan
    tree, rp = problem(make_model(tmp_path, demand={"2026-W44": 1, "2027-W01": 0}))
    sol = rs.solve(rp)
    rows = rs.expand(rp, sol)
    assert sol.served == 0 and rows[0]["reason"] == "no_feasible_option"


# ── aggregation, expansion, distribution ───────────────────────────────────
def test_aggregated_request_expands_to_original_ids_in_market_order(tmp_path):
    # 3 IDs in one request week; the crop holds 2 -> the first two IDs, the third unallocated
    # (the mill, the warehouse and the market are widened so that only the crop binds)
    tree, rp = problem(make_model(tmp_path, demand={"2027-W01": 3}, crop="200/9",
                                  storage="1000", other="1000", white="1000"))
    assert rp.stats["requests"] == 1 and rp.stats["lots"] == 3
    sol = rs.solve(rp)
    rows = rs.expand(rp, sol)
    mkt = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_type == "leaf_out")
    ids = list(mkt.psi4demand[tree.week_labels.index("2027-W01")][0])
    assert [r["lot_id"] for r in rows] == ids
    assert [r["status"] for r in rows] == ["assigned", "assigned", "unallocated"]


def test_largest_remainder_split():
    assert rs.largest_remainder(10, {"A": 7, "B": 7, "C": 1}) == {"A": 5, "B": 5, "C": 0}
    assert rs.largest_remainder(3, {"A": 1, "B": 1, "C": 1, "D": 1}) == {"A": 1, "B": 1, "C": 1, "D": 0}
    assert rs.largest_remainder(7, {"A": 4, "B": 3}) == {"A": 4, "B": 3}
    assert sum(rs.largest_remainder(13, {"A": 9, "B": 5, "C": 3}).values()) == 13


# ── K-R5: a mill shared by two products is limited once ────────────────────
def test_k_r5_shared_mill_is_one_constraint_across_products(tmp_path):
    shared_d = make_model(tmp_path / "s", products=("Koshihikari", "Yumepirika"), shared_mill=True)
    _t, rp = problem(shared_d)
    assert rs.solve(rp).served == 1                    # one mill week of 100/9 kg for two IDs
    own_d = make_model(tmp_path / "o", products=("Koshihikari", "Yumepirika"), shared_mill=False)
    _t, rp2 = problem(own_d)
    assert rs.solve(rp2).served == 2                   # separate mills: both


def test_k_r5_plugin_solves_once_for_both_products(tmp_path):
    snap, tree, fres = headless(make_model(tmp_path, products=("Koshihikari", "Yumepirika")))
    res = tree.rice_seasonal_results
    assert res["_joint"]["served"] == 1 and res["_joint"]["unallocated"] == 1
    assert market_outcome(tree) == {"on_time": 1, "late": 0, "early": 0, "backlog_end": 1}
    assert snap["forward"]["cap_hard_deferred_lots"] == 0


# ── K-R6: mass and counts are separate ─────────────────────────────────────
def test_k_r6_mass_balance_and_id_count(tmp_path):
    tree, rp = problem(make_model(tmp_path, demand={"2027-W01": 2},
                                  storage="1000", other="1000", white="1000"))
    sol = rs.solve(rp)
    rows = rs.expand(rp, sol)
    assert sol.served == 2
    led = rs.physical_ledger(rp, rows)
    sold = [r for r in led if r.get("sold")]
    assert sold and sold[-1]["sold"] == pytest.approx(20)                # 2 lots x 10 kg white
    assert sold[-1]["other_output_cumulative"] == pytest.approx(20 / 9)
    assert sum(len(r) for r in [[x for x in rows if x["status"] == "assigned"]]) == 2   # IDs, not kg


# ── K-R7: Forward is an independent gate ───────────────────────────────────
def test_k_r7_capacity_changed_after_allocation_is_caught_by_forward(tmp_path):
    from wom.engine.plan_copy import copy_demand_to_supply
    from wom.engine.forward_planner import ForwardPlanner
    tree, rp = problem(make_model(tmp_path))
    rows = rs.expand(rp, rs.solve(rp))
    rs.apply_positions(tree, "Koshihikari", rp, rows)
    mill = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_name == "Seihaku_W")
    mill.set_capacity(tree.week_labels.index("2026-W52"), cap_hard=0)
    res = reforward(tree, "Koshihikari")
    assert res.cap_hard_deferred_lots == 1
    out = market_outcome(tree)
    assert out["on_time"] == 0 and out["early"] == 0


# ── closures follow Forward's rule ─────────────────────────────────────────
def test_closed_dc_week_moves_the_lot_to_the_next_open_week(tmp_path):
    from wom.engine.plan_copy import copy_demand_to_supply
    from wom.engine.forward_planner import ForwardPlanner
    from tools.rice_seasonal_check import flow_identities
    model = make_model(tmp_path)
    _s, tree, _f = headless(model, plugin=False)
    dc = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_name == "DC_Nishi")
    dc.set_operating_shifts(tree.week_labels.index("2026-W53"), 0)      # DC closed in W53
    inputs = rs.load_inputs(model, list(tree.week_labels))
    rp = rs.build_problem(tree, ["Koshihikari"], inputs)
    sol = rs.solve(rp)
    rows = rs.expand(rp, sol)
    t = rows[0]["timing"]
    wl = tree.week_labels
    # milling in W52 would reach the DC in the closed W53, be processed in W01 and
    # reach the market in W02 (late). The latest milling week is therefore W51:
    # DC W52, market W53 -- one week before the request, unavoidably.
    assert sol.served == 1
    assert [wl[t.polish], wl[t.dc], wl[t.market_arrival]] == ["2026-W51", "2026-W52", "2026-W53"]
    assert sol.objective["milling_advance_lot_weeks"] == 1
    rs.apply_positions(tree, "Koshihikari", rp, rows)
    fres = {"Koshihikari": reforward(tree, "Koshihikari")}
    assert flow_identities(tree, fres)[0] == {}
    assert market_outcome(tree) == {"on_time": 1, "late": 0, "early": 0, "backlog_end": 0}


# ── inputs ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("fname,rows,match", [
    ("rice_resources.csv", [{"resource_id": "X", "kind": "raw_kg_week", "capacity_unit": "lot", "default_capacity": ""}],
     "default_capacity is required"),
    ("rice_resources.csv", [{"resource_id": "X", "kind": "raw_kg_week", "capacity_unit": "ton", "default_capacity": "1"}],
     "unknown capacity_unit"),
    ("rice_crop_limit.csv", [], "no limit"),
])
def test_input_errors_stop(tmp_path, fname, rows, match):
    model = make_model(tmp_path)
    path = os.path.join(model, fname)
    old = list(csv.DictReader(open(path, encoding="utf-8")))
    header = list(old[0]) if old else ["resource_id", "crop_season", "limit", "unit"]
    _w(path, header, (old + rows) if fname == "rice_resources.csv" else rows)
    _s, tree, _f = headless(model, plugin=False)
    with pytest.raises(rs.RiceInputError, match=match):
        rs.load_inputs(model, list(tree.week_labels))


def test_missing_input_file_stops_the_plugin(tmp_path):
    model = make_model(tmp_path)
    os.remove(os.path.join(model, "rice_recipe.csv"))
    with pytest.raises(rs.RiceInputError, match="rice_recipe.csv"):
        headless(model)


def test_role_with_the_wrong_resource_kind_stops(tmp_path):
    model = make_model(tmp_path)
    path = os.path.join(model, "rice_resource_map.csv")
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    for r in rows:
        if r["role"] == "storage":
            r["resource_id"] = "MILL_W"
    _w(path, list(rows[0]), rows)
    _s, tree, _f = headless(model, plugin=False)
    with pytest.raises(rs.RiceInputError, match="brown_stock_kg"):
        rs.load_inputs(model, list(tree.week_labels))


def test_legacy_lot_flow_is_refused(tmp_path):
    model = make_model(tmp_path)
    _w(os.path.join(model, "planning_config.csv"), ["key", "value"], [{"key": "lot_flow_mode", "value": "legacy"}])
    with pytest.raises(rs.RiceInputError, match="identity"):
        headless(model)


def test_plugin_is_off_by_default_and_registered_last():
    import tools.run_headless_from_folder as rh
    from wom.plugins import ALL_BUILTIN_PLUGINS
    from wom.plugins.rice_seasonal import RiceSeasonalPlugin
    assert ALL_BUILTIN_PLUGINS[-1] is RiceSeasonalPlugin
    assert "RiceSeasonalPlugin" not in rh.SAFE_DEFAULT


# ── K-R10: the migration copy of Rice ──────────────────────────────────────
MIG = os.path.join(REPO, "data", "trial", "rice-japan-2027-2028-seasonal")


@pytest.mark.skipif(not os.path.isdir(MIG), reason="migration copy not generated")
def test_k_r10_migration_copy_regression():
    from tools.rice_seasonal_check import plan, flow_identities
    snap, tree, fres = plan(MIG)
    # milling advance up to 1 week (RequestLetter_RiceSeasonal_PolishAdvance1, 2026-10-09).
    # Before (0 weeks): served 141,188, unallocated 95,749, Koshihikari report 28,578 --
    # the 22 lots short at the shared mills are now allocated.
    j = tree.rice_seasonal_results["_joint"]
    assert j["served"] == 141210 and j["unallocated"] == 95727
    assert j["unallocated_by_product_period"] == {"Koshihikari|report": 28556, "Koshihikari|warmup": 52163,
                                                  "Yumepirika|report": 2, "Yumepirika|warmup": 15006}
    assert j["report_start"] == "2027-W01"                      # from vc_config.csv
    out = market_outcome(tree)
    assert out == {"on_time": 141210, "late": 0, "early": 0, "backlog_end": 95727}
    assert flow_identities(tree, fres)[0] == {}
    assert snap["forward"]["cap_hard_deferred_lots"] == 0
