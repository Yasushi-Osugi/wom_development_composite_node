# -*- coding: utf-8 -*-
"""
tools/units_freight_compare.py — money の units と Landed Cost の Freight の前後比較（測定だけ）
（RequestLetter_StalePPC_Units_KittingView P4）

    python -m tools.units_freight_compare --out output/stale_ppc/P4 [--base-ref e575042]
                                          [--models all|<case>,<case>]

モデルごと・方式ごと（identity／legacy）に、モデルのコピーで headless 実行し、同じ計画結果に

  old  基準 commit（--base-ref）の money.py（units ＝ 市場 leaf の行＋DAD の行の合計）
  new  今の money.py（units ＝ 市場 leaf の行だけの合計）

の両方を当て、Landed Cost（`landed_cost.compare_lc_scenarios`）まで計算して比べる。

出力（<out>/ の下）:
  units_freight_compare.csv  モデル×方式×Landed Cost のシナリオの 1 行：units・Freight・
                             KD 組立費・Landed GM%（money の値）の前後、と
                             「units 以外の money の列が一致」「Freight・KD 組立費・それを使う列
                             以外の Landed Cost の列が一致」
  units_compare.csv          モデル×方式の 1 行：units の前後、市場の数量、DAD の段数
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Landed Cost columns that depend on the lot count (freight / KD assembly) ...
LC_UNITS_COLS = ["freight_total", "assembly_total", "landed_cogs", "landed_gross_profit",
                 "landed_gross_margin", "margin_impact_pp"]
# ... and those that do not
LC_OTHER_COLS = ["wom_scenario", "lc_scenario", "revenue", "cogs", "customs_duty", "fx_gain_loss",
                 "tariff_burden_pct", "original_gross_margin"]


def _load_old(ref, rel, name, tmp):
    src = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=REPO, capture_output=True, check=True).stdout
    path = os.path.join(tmp, name + ".py")
    with open(path, "wb") as f:
        f.write(src)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _jobs():
    gdir = os.path.join(REPO, "tests", "golden")
    jobs = []
    for fn in sorted(os.listdir(gdir)):
        if fn.endswith(".json"):
            with open(os.path.join(gdir, fn), encoding="utf-8") as f:
                jobs.append((fn[:-5], ",".join(json.load(f)["config"]["plugins"]) or "none"))
    jobs.append(("ev-thailand-2026_update", "safe"))
    jobs.append(("soysauce-jpy-2027-alloc", "safe"))
    return jobs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join("output", "stale_ppc", "P4"))
    ap.add_argument("--base-ref", default="e575042")
    ap.add_argument("--models", default="all")
    a = ap.parse_args(argv)
    import pandas as pd
    import tools.run_headless_from_folder as rh
    from wom.data.schema import Cols
    from wom.engine.sc_tree_to_df import sc_tree_to_planning_df, apply_inv_value
    from wom.engine.money import evaluate_money, build_scenario_money_kpi, is_dad_region
    from wom.engine.landed_cost import (load_edge_cost_master, load_route_master,
                                        build_route_index, compare_lc_scenarios)

    os.makedirs(a.out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="p4_old_")
    old_money = _load_old(a.base_ref, "wom/engine/money.py", "old_money_p4", tmp)
    store = {}
    o_sig = rh._psi_signature

    def sig(t, n):
        store["tree"] = t
        return o_sig(t, n)

    rh._psi_signature = sig
    only = None if a.models == "all" else set(a.models.split(","))
    lc_rows, unit_rows = [], []
    try:
        for case, plugins in _jobs():
            if only and case not in only:
                continue
            for mode in ("identity", "legacy"):
                work = os.path.join(tmp, f"{case}__{mode}")
                shutil.copytree(os.path.join(REPO, "data", "sample", case), work)
                rh.run(work, plugins_spec=plugins, output_ppc_dir=os.path.join(work, "_ppc"),
                       verbose=False, lot_flow_mode=mode)
                tree = store["tree"]
                sku_master = pd.read_csv(os.path.join(work, "sku_master.csv"))
                df = sc_tree_to_planning_df(tree)
                apply_inv_value(df, sku_master)
                _nw, new_sum = evaluate_money(df, sku_master)
                _ow, old_sum = old_money.evaluate_money(df, sku_master)
                new_kpi, old_kpi = build_scenario_money_kpi(new_sum), old_money.build_scenario_money_kpi(old_sum)
                money_same = all(new_sum[c].equals(old_sum[c]) for c in old_sum.columns if c != "total_units")
                kpi_same = all(new_kpi[c].equals(old_kpi[c]) for c in old_kpi.columns if c != "units")
                dad = is_dad_region(df[Cols.REGION])
                market_qty = float(df.loc[~dad, Cols.DEMAND_FULFILLED].sum())
                dad_tiers = max((sum(1 for nd in tree.get_ot_root(p).walk_preorder() if nd.node_type == "dad"
                                     and any(True for _ in [0]))
                                 for p in tree.products), default=0)
                u_old, u_new = float(old_kpi["units"].iloc[0]), float(new_kpi["units"].iloc[0])
                unit_rows.append({
                    "model": case, "mode": mode, "market_quantity": market_qty,
                    "units_old": u_old, "units_new": u_new,
                    "ratio_old_over_new": round(u_old / u_new, 4) if u_new else "",
                    "units_new_equals_market": u_new == market_qty,
                    "max_dad_nodes_in_a_product": dad_tiers,
                    "money_other_columns_identical": money_same and kpi_same,
                })
                edge, route = os.path.join(work, "edge_cost_master.csv"), os.path.join(work, "route_master.csv")
                if not os.path.exists(edge):
                    print(case, mode, "units", u_old, "->", u_new, "(no edge_cost_master)", flush=True)
                    continue
                lc_scens = load_edge_cost_master(edge)
                route_idx = build_route_index(load_route_master(route)) if os.path.exists(route) else {}
                lc_old = compare_lc_scenarios(old_kpi, lc_scens, route_idx)
                lc_new = compare_lc_scenarios(new_kpi, lc_scens, route_idx)
                other_same = all(lc_old[c].equals(lc_new[c]) for c in LC_OTHER_COLS if c in lc_old.columns)
                for (_i, o), (_j, n) in zip(lc_old.iterrows(), lc_new.iterrows()):
                    lc_rows.append({
                        "model": case, "mode": mode, "lc_scenario": n["lc_scenario"],
                        "units_old": u_old, "units_new": u_new,
                        "freight_old": o["freight_total"], "freight_new": n["freight_total"],
                        "assembly_old": o["assembly_total"], "assembly_new": n["assembly_total"],
                        "revenue": n["revenue"], "cogs": n["cogs"], "customs_duty": n["customs_duty"],
                        "landed_gm_money_old": o["landed_gross_margin"],
                        "landed_gm_money_new": n["landed_gross_margin"],
                        "lc_other_columns_identical": other_same,
                        "money_other_columns_identical": money_same and kpi_same,
                    })
                b_o, b_n = lc_old.iloc[0], lc_new.iloc[0]
                print(case, mode, "units", u_old, "->", u_new, "| freight", b_o["freight_total"], "->",
                      b_n["freight_total"], "| landed GM(money)", b_o["landed_gross_margin"], "->",
                      b_n["landed_gross_margin"], "| other same", other_same, money_same and kpi_same, flush=True)
    finally:
        rh._psi_signature = o_sig
        shutil.rmtree(tmp, ignore_errors=True)
    for name, rows in (("units_freight_compare.csv", lc_rows), ("units_compare.csv", unit_rows)):
        if not rows:
            continue
        with open(os.path.join(a.out, name), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
