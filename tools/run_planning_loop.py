#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/run_planning_loop.py — WOM 三層の閉ループを1コマンドで（Phase 7・GUI なし）
================================================================================
第1層（A系統・配分）→ 第2層（Planning Engine・配置）→ 第3層（Forward+PPC・実行/損益評価）
を headless で1周させ、`output/planning_state/<case>/<allocation_id>.json` に記録する。

正典: requests/Phase7_RequestLetter_to_CodeKun.md V3

使い方（リポジトリ直下）:
  python -m tools.run_planning_loop --model-dir data/sample/soysauce-jpy-2027-alloc \
         --scenario s1_base --cap-wk 800 --allocation 0.10,0.45,0.45
  python -m tools.run_planning_loop --model-dir <case> --scenario s1_base --cap-wk 800 --from P_opt

処理順（V3）:
  1. derive_cost_blocks() → build_allocation_merit_order() / true_continuous_optimum() /
     scan_surface()（N>=4 なら scan_hierarchical() も）
  2. --allocation 明示、または --from {P_opt|P_greedy|P_grid|P_hier} でその水準の配分を採る
     （既定 P_opt。Phase 6-1 で計算できるようになったので格子の最良点を推奨する理由はもう無い）
  3. new_state() → save()（state="pre_plan"）
  4. write_demand_for_allocation() → demand_forecast_<id>.csv
  5. run(model_dir, demand_file=…, planning_state=True)
  6. attach_placement() / attach_realized() → save()（state="feasible_plan"）
  7. 結論を日本語1行で標準出力に出す（matplotlib ではなく stdout なので図中テキスト
     英語の制約とは衝突しない。大杉さん判断・2026-09-12）
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Dict, Optional

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.grid import WEEKS, best_point, markets_of, scan_surface
from wom.allocation.handoff import write_demand_for_allocation
from wom.allocation.hierarchical_simplex import build_hierarchy, scan_hierarchical
from wom.allocation.merit_order import (
    build_allocation_merit_order, compare_with_grid, true_continuous_optimum,
)
from wom.allocation.transmission import Scenario
from tools.run_allocation_map import load_scenarios, _blocks_for
from tools.run_headless_from_folder import run as run_headless
import wom.planning_state as planning_state

LEVELS = ("P_opt", "P_greedy", "P_grid", "P_hier")


def _scenario_blocks(model_dir: str, scenario_id: str, uom: Optional[str]):
    base_blocks, tp = derive_cost_blocks(model_dir, uom=uom)
    scens = {s["id"]: s for s in load_scenarios(model_dir)}
    if scenario_id not in scens:
        raise ValueError(
            f"run_planning_loop: scenario {scenario_id!r} not found in "
            f"ga_scenario_master.csv (available: {sorted(scens)})"
        )
    s = scens[scenario_id]
    blocks = _blocks_for(base_blocks, s["tariff"],
                         s.get("tariff_preferential"), s.get("preferential_threshold"))
    sc = Scenario(fx_usd=s["fx_usd"], material_usd=s["material_usd"])
    return blocks, tp, sc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--scenario", required=True, help="ga_scenario_master.csv の scenario_id")
    ap.add_argument("--cap-wk", type=float, required=True)
    ap.add_argument("--uom", default=None, help="複数 uom 混在モデルの絞り込み")
    ap.add_argument("--allocation", default=None,
                    help="markets_of(blocks) の順の比率を comma 区切りで明示（例 0.10,0.45,0.45）")
    ap.add_argument("--from", dest="from_level", default="P_opt", choices=LEVELS,
                    help="--allocation 省略時にこの水準の配分を採用する（既定 P_opt）")
    ap.add_argument("--mode", default="cockpit")
    ap.add_argument("--out-dir", default="output/planning_state")
    ap.add_argument("--ppc-out", default="output/ppc")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    verbose = not a.quiet
    model_dir = a.model_dir
    case = os.path.basename(model_dir.rstrip("/\\"))

    # 1) 配分エンジン
    blocks, tp, sc = _scenario_blocks(model_dir, a.scenario, a.uom)
    markets = markets_of(blocks)
    n_markets = len(markets)

    mo = build_allocation_merit_order(blocks, sc, a.cap_wk, transfer_price_usd=tp)
    to = true_continuous_optimum(blocks, sc, a.cap_wk, transfer_price_usd=tp)

    grid_x: Optional[Dict[str, float]] = None
    cmp: dict = {}
    try:
        surf = scan_surface(blocks, tp, sc, a.cap_wk)
        grid_best, plateau = best_point(surf)
        cmp = compare_with_grid(mo, surf, true_optimum=to)
        grid_x = dict(zip(markets, plateau[0]["x"]))
    except ValueError:
        pass

    hier_x: Optional[Dict[str, float]] = None
    p_hier = None
    if n_markets >= 4:
        try:
            tree = build_hierarchy(blocks, model_dir, max_children=3)
            hier = scan_hierarchical(blocks, tree, tp, sc, a.cap_wk)
            cap_total = a.cap_wk * WEEKS
            hier_x = {m: (hier["q"].get(m, 0.0) / cap_total if cap_total else 0.0)
                     for m in markets}
            p_hier = hier["profit"]
        except Exception:
            pass   # build_hierarchy が model_dir の CSV から木を組めない等。P_hier 無しで続行。

    profit_levels = {
        "P_opt": to["profit"],
        "P_greedy": mo["profit"],
        "P_grid": cmp.get("grid_best_profit"),
        "P_hier": p_hier,
        "gap_amt": cmp.get("gap_amt"),
        "expected_gap": cmp.get("expected_gap_from_grid_resolution"),
        "structural_residual": cmp.get("structural_residual"),
        "structural_optimality_gap": cmp.get("structural_optimality_gap"),
        "grid_resolution_error": cmp.get("grid_resolution_error"),
        "residual_coverage": cmp.get("residual_coverage"),
        "hierarchy_gap": ((to["profit"] - p_hier) if p_hier is not None else None),
        "n_markets": n_markets,
    }
    level_x = {"P_opt": dict(to["x"]), "P_greedy": dict(mo["x"]),
              "P_grid": grid_x, "P_hier": hier_x}

    # 2) 配分の決定
    if a.allocation:
        vals = [float(v) for v in a.allocation.split(",")]
        if len(vals) != n_markets:
            raise ValueError(
                f"--allocation has {len(vals)} values but markets_of(blocks) has "
                f"{n_markets}: {markets}"
            )
        allocation = dict(zip(markets, vals))
        source = "manual"
    else:
        chosen = level_x.get(a.from_level)
        if chosen is None:
            raise ValueError(
                f"--from {a.from_level} is not available for this model "
                f"(n_markets={n_markets}); pass --allocation explicitly"
            )
        allocation = chosen
        source = a.from_level
    profit_levels["source"] = source

    # 3) pre_plan の保存（allocation_id 未指定なら save() が連番を確定する）
    state = planning_state.new_state(case, a.scenario, allocation, profit_levels, mode=a.mode)
    path = planning_state.save(state, out_dir=a.out_dir)
    allocation_id = _id_from_path(path)
    state["allocation_id"] = allocation_id

    # 4) 第1層 → 第2層のハンドオフ
    handoff = write_demand_for_allocation(
        model_dir, allocation, allocation_id, cap_wk=a.cap_wk, uom=a.uom)
    demand_file = os.path.basename(handoff["path"])

    # 5) Planning Engine + PPC
    snap = run_headless(model_dir, demand_file=demand_file, planning_state=True,
                        output_ppc_dir=a.ppc_out, verbose=verbose)

    # 6) 配置・実績を記録して feasible_plan へ
    extras = snap.get("planning_state_extras", {})
    state = planning_state.attach_placement(
        state, earliest_start_week=snap["period"]["start"],
        backward_envelope_violations=extras.get("backward_envelope_weeks", []))
    state = planning_state.attach_realized(state, snap, model_dir=model_dir)
    path = planning_state.save(state, out_dir=a.out_dir)

    # 7) 結論（日本語1行、stdout）
    print(_format_conclusion(state, markets))
    print(f"  -> {path}")
    return 0


def _id_from_path(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _format_conclusion(state: dict, markets) -> str:
    aid = state["allocation_id"]
    case = state["case"]
    scenario = state["scenario_id"]
    plan_x = state["allocation"]
    p_opt = state["profit_levels"].get("P_opt")
    realized = state["realized"] or {}
    real_x = realized.get("allocation", {})
    profit_ppc = realized.get("profit_ppc")
    gap_pct = realized.get("gap_vs_plan_pct")
    unmet = realized.get("unmet_lots")
    cap_weeks = realized.get("capacity_violation_weeks", [])
    inv_weeks = realized.get("peak_inventory_weeks", [])

    def pct_row(d):
        return " / ".join(f"{m} {round(d.get(m, 0.0) * 100)}" for m in markets)

    lines = [f"[planning_loop] {aid} {case} / {scenario}"]
    lines.append(f"  計画   {pct_row(plan_x)}    P_opt {p_opt:,.0f} 円"
                if p_opt is not None else f"  計画   {pct_row(plan_x)}")
    if profit_ppc is not None:
        gap_str = f"   計画比 {gap_pct:+.1f}%" if gap_pct is not None else ""
        lines.append(f"  実績   {pct_row(real_x)}    PPC   {profit_ppc:,.0f} 円{gap_str}")
    cap_str = (f"{len(cap_weeks)}週（{cap_weeks[0]}〜{cap_weeks[-1]}）"
              if cap_weeks else "0週")
    inv_str = f"{len(inv_weeks)}週" if inv_weeks else "0週"
    lines.append(f"  未充足 {unmet:.0f} lot   能力超過 {cap_str}   在庫ピーク {inv_str}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
