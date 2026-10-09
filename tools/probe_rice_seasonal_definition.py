"""Pinned, additive Rice seasonal prototype measurement; no core/CSV writes.

python -m tools.probe_rice_seasonal_definition --out output/rice_seasonal_definition
Outputs small full-ID evidence. Protected originals / canonical goldens untouched.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import date, timedelta, datetime, timezone
from fractions import Fraction
import csv
import hashlib
import json
from pathlib import Path
import subprocess

import pandas as pd

from wom.capacity_layer.rice_trial import (
    ROLES, RiceDemand, RicePolicy, RiceRoute, build_problem,
    solve, assignments, physical_ledger, apply_to_tree,
)

BASE_SHA = "26a1e8eb7bc2f899246168a60c8f480857a0b614"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/trial/rice-seasonal-one-id"


def week_labels(start, end):
    def parse(label):
        year, week = label.split("-W")
        return date.fromisocalendar(int(year), int(week), 1)
    value, last = parse(start), parse(end)
    labels = []
    while value <= last:
        y, w, _ = value.isocalendar()
        labels.append(f"{y}-W{w:02d}")
        value += timedelta(weeks=1)
    return labels


def fixture_problem(*, demand_count=1, policy=None, mutate=None):
    spec = json.loads((FIXTURE / "scenario.json").read_text(encoding="utf-8"))
    weeks = week_labels(spec["start_week"], spec["end_week"])
    route = RiceRoute(
        key="Koshihikari/KANSAI", product="Koshihikari", market="Retail_KANSAI",
        field="Tanbo_Niigata", collection="Sanchiku_Niigata", supply_point="SP_Kome",
        warehouse="Genmai_Souko_Niigata", polisher="Seihaku_W", dc="DC_Nishi",
        resources={
            "harvest": "FIELD_NIIGATA_RAW_KG", "collection": "COLLECT_NIIGATA_RAW_KG",
            "store_receipt": "STORE_RECEIPT_NIIGATA_RAW_KG",
            "storage": "BROWN_STORE_NIIGATA_KG", "polish": "MILL_W_RAW_KG",
            "dc": "DC_W_WHITE_KG", "market": "KANSAI_WHITE_KG",
        },
        white_kg_per_lot=Fraction(spec["white_kg_per_lot"]),
        milling_yield=Fraction(spec["milling_yield"]),
        field_to_collection=1, collection_to_store=1, store_to_polish=2,
        polish_to_dc=1, dc_to_market=1,
    )
    capacities = {}
    harvest_seasons = {}
    for w, label in enumerate(weeks):
        for role in ROLES:
            value = spec["other_raw_capacity_kg_week"]
            if role in ("dc", "market"):
                value = spec["white_capacity_kg_week"]
            elif role == "storage":
                value = spec["storage_capacity_raw_kg"]
            elif role == "harvest":
                value = spec["harvest_capacity_raw_kg"] if label in spec["harvest_weeks"] else "0"
            capacities[route.resources[role], w] = float(Fraction(value))
        if label in spec["harvest_weeks"]:
            harvest_seasons[route.resources["harvest"], w] = "2026_crop"
    season_limits = {(route.resources["harvest"], "2026_crop"):
                     float(Fraction(spec["crop_yield_raw_kg"]))}
    if mutate:
        mutate(capacities, season_limits, route, weeks)
    demands = [RiceDemand(f"Koshihikari:KANSAI:2027-W01:{i:05d}", route.key,
                          weeks.index("2027-W01")) for i in range(1, demand_count + 1)]
    rice = build_problem(demands, [route], weeks, policy or RicePolicy(**spec["policy"]),
                         capacities, harvest_seasons, season_limits)
    return rice, spec


def fixture_tree(demand_count=1):
    from wom.engine.sc_tree_builder import build_sc_tree_from_master
    from wom.engine.capacity_sealer import load_capacity_dataframe
    from wom.model.lot_generator import assign_demand_lots_from_dict
    from wom.engine.backward_planner import BackwardPlanner
    spec = json.loads((FIXTURE / "scenario.json").read_text())
    weeks = week_labels(spec["start_week"], spec["end_week"])
    tree = build_sc_tree_from_master(pd.read_csv(FIXTURE / "sc_tree_master.csv").fillna(""), weeks)
    load_capacity_dataframe(tree, pd.read_csv(FIXTURE / "capacity_plan.csv", dtype={"max_supply": str}),
                            weeks, source=str(FIXTURE / "capacity_plan.csv"))
    # Production headless Planning treats demand CSV quantity as lot count
    # and deliberately uses cpu_size=1 for ID generation. cpu_size=10 is
    # the physical conversion label here, not a second division of demand.
    dem = pd.read_csv(FIXTURE / "demand_forecast.csv")
    demand = {(str(x.sku_id), str(x.region), str(x.week)): int(x.quantity) * demand_count
              for x in dem.itertuples()}
    assign_demand_lots_from_dict(tree, demand, cpu_size=1)
    BackwardPlanner(tree).run("Koshihikari")
    return tree


def snapshot_tree(tree):
    return {
        n.node_name: {
            "node_id": n.node_id, "node_type": n.node_type, "side": n.side,
            "parent": n.parent.node_name if n.parent else "",
            "lt": n.lt_wks, "plan_mode": n.plan_mode,
            "demand": n.psi4demand, "supply": n.psi4supply,
            "actual_ship": {str(w): list(lots) for w, lots in n._actual_ship.items()},
        } for n in tree.iter_all_nodes("Koshihikari")
    }


def verify_forward(tree, original_market_s):
    """Independent full-ID inventory / carry-over / arrival / due reconciliation."""
    from wom.model.plan_node import S, CO, I, P
    nodes = {n.node_name: n for n in tree.iter_all_nodes("Koshihikari")}
    market = nodes["Retail_KANSAI"]
    inv_errors, co_errors, arrival_errors, duplicate_supply = [], [], [], []
    for n in nodes.values():
        prev_i, prev_co = Counter(), Counter()
        for w, cells in enumerate(n.psi4supply):
            shipped = Counter(n._actual_ship.get(w, []))
            available = prev_i + Counter(cells[P])
            if any(q > 1 for q in available.values()):
                duplicate_supply.append((n.node_name, w))
            if available - shipped != Counter(cells[I]) or shipped - available:
                inv_errors.append((n.node_name, w))
            demand = prev_co + Counter(cells[S])
            if shipped - demand:
                co_errors.append((n.node_name, w, "unexpected/early ID"))
            expected_co = demand - shipped
            if w + 1 < len(tree.week_labels) and expected_co != Counter(n.psi4supply[w + 1][CO]):
                co_errors.append((n.node_name, w, "carry-over"))
            prev_i, prev_co = Counter(cells[I]), expected_co
    # All receipt lists must be actual upstream deliveries, except external source.
    for name, n in nodes.items():
        if n.node_type == "leaf_in":
            continue
        if name == "SP_Kome":
            parent, lt = nodes["Sanchiku_Niigata"], 0
        elif n.side == "inbound":
            parent, lt = nodes["Tanbo_Niigata"], nodes["Tanbo_Niigata"].lt_wks
        else:
            parent, lt = n.parent, n.lt_wks
        for w in range(len(tree.week_labels)):
            expected = Counter(parent._actual_ship.get(w - lt, [])) if w >= lt else Counter()
            if Counter(n.psi4supply[w][P]) != expected:
                arrival_errors.append((name, w))
    original = {lot: w for w, lots in enumerate(original_market_s) for lot in lots}
    actual = {lot: w for w, lots in market._actual_ship.items() for lot in lots}
    unchanged = [list(x[S]) for x in market.psi4demand] == original_market_s
    on_time = sum(actual.get(lot) == due for lot, due in original.items())
    late = sum(lot in actual and actual[lot] > due for lot, due in original.items())
    early = sum(lot in actual and actual[lot] < due for lot, due in original.items())
    return {"market_S_unchanged": unchanged, "on_time_IDs": on_time, "late_IDs": late,
            "early_IDs": early, "end_unmet_IDs": sorted(set(original) - set(actual)),
            "inventory_errors": inv_errors, "CO_errors": co_errors,
            "receipt_from_actual_errors": arrival_errors, "duplicate_supply": duplicate_supply,
            "actual_ship_events": sum(len(v) for n in nodes.values() for v in n._actual_ship.values())}


def run_forward_variant(kind, rice, solution=None):
    from wom.capacity_layer.serial_adapter import SerialLineAdapter
    from wom.capacity_layer.solver import solve_lp
    from wom.engine.plan_copy import copy_demand_to_supply
    from wom.engine.forward_planner import ForwardPlanner
    tree = fixture_tree()
    market = next(n for n in tree.iter_all_nodes("Koshihikari") if n.node_type == "leaf_out")
    original = [list(c[0]) for c in market.psi4demand]
    if kind == "serial":
        a = SerialLineAdapter.from_tree(tree, ["Koshihikari"])
        problem = a.problem_from_tree(tree, "Koshihikari", 13)
        sol = solve_lp(problem)
        a.apply_positions(tree, "Koshihikari", a.expand(problem, sol))
    elif kind == "seasonal":
        apply_to_tree(rice, solution, tree)
    elif kind != "plain":
        raise ValueError(kind)
    copy_demand_to_supply(tree, "Koshihikari")
    result = ForwardPlanner(tree, lot_flow_mode="identity").run("Koshihikari")
    return tree, result, verify_forward(tree, original)


def tracked_hashes():
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in paths if p and (ROOT / p).is_file()}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "output/rice_seasonal_definition")
    # RequestLetter_RiceSeasonal_Implementation §8: the pinned SHA check stays the
    # default (reproducing the recorded run); --allow-head measures at the current
    # HEAD and records both SHAs in manifest.json.
    parser.add_argument("--allow-head", action="store_true",
                        help="measure at the current HEAD instead of the pinned baseline SHA")
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != BASE_SHA and not args.allow_head:
        raise SystemExit(f"Baseline SHA mismatch: {head} != {BASE_SHA} (use --allow-head to measure at HEAD)")
    before = tracked_hashes()
    args.out.mkdir(parents=True, exist_ok=True)
    rice, spec = fixture_problem()
    solution = solve(rice)
    material = physical_ledger(rice, solution)
    method_rows = {}
    for method in ("greedy", "lp", "milp"):
        sol = solve(rice, method)
        method_rows[method] = {"solution": asdict(sol), "assignments":
                               {k: asdict(t) for k, t in assignments(rice, sol).items()}}
    write_json(args.out / "methods.json", method_rows)
    write_json(args.out / "resource_problem.json", {
        "requests": [asdict(x) for x in rice.problem.requests],
        "options": [asdict(x) for x in rice.problem.options],
        "capacities": [{"resource": k[0], "week_index": k[1], "limit": v}
                       for k, v in rice.problem.capacities.items()],
        "metadata": rice.problem.metadata})
    write_json(args.out / "physical_ledger.json", material)
    variants, weekly = {}, []
    for kind in ("plain", "serial", "seasonal"):
        tree, res, verification = run_forward_variant(kind, rice, solution)
        snapshot = snapshot_tree(tree)
        write_json(args.out / f"{kind}_full_PSI.json", snapshot)
        write_json(args.out / f"{kind}_forward_result.json", asdict(res))
        variants[kind] = verification
        for name, node in snapshot.items():
            for w, label in enumerate(rice.weeks):
                s, co, inv, p = node["supply"][w]
                weekly.append({"variant": kind, "node": name, "week": label,
                               "P_IDs": len(p), "I_IDs": len(inv), "CO_IDs": len(co),
                               "S_request_IDs": len(s),
                               "actual_S_IDs": len(node["actual_ship"].get(str(w), []))})
    with (args.out / "weekly_PSI.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(weekly[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(weekly)
    write_json(args.out / "forward_verification.json", variants)
    after = tracked_hashes()
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    write_json(args.out / "tracked_integrity.json",
               {"tracked_count": len(before), "changed": changed, "before": before, "after": after})
    write_json(args.out / "manifest.json", {
        "base_sha": head, "pinned_sha": BASE_SHA, "allow_head": bool(args.allow_head),
        "measured_utc": datetime.now(timezone.utc).isoformat(),
        "tracked_originals_changed": changed, "core_modified": False,
        "model": "isolated one-ID trial", "lot_flow_mode": "identity", "HarvestBatch": False,
        "hypothetical_physical_values": True, "cpu_size_white_kg": 10,
        "canonical_golden_regenerated": False,
        "external_milling_mass_ledger": True, "Forward_has_new_mass_conversion": False,
    })
    assert not changed, changed
    seasonal = variants["seasonal"]
    assert seasonal["on_time_IDs"] == 1 and seasonal["early_IDs"] == seasonal["late_IDs"] == 0
    assert not any(seasonal[k] for k in
                   ("inventory_errors", "CO_errors", "receipt_from_actual_errors", "duplicate_supply"))
    print(json.dumps({"SHA": head, "results": variants, "tracked_changed": changed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
