# -*- coding: utf-8 -*-
"""
tools/s2_eval_compare.py — S2（実出荷ベースの評価）の前後比較（測定だけ）
（RequestLetter_SmartphoneWarmup_EVUpdateKitting_S2 C）

    python -m tools.s2_eval_compare --out output/smartphone_evupdate_s2/C [--base-ref 979cf7a]
                                    [--models all|<case>,<case>]

モデルごと・方式ごと（identity／legacy）に、モデルのコピーで headless 実行し、同じ計画結果に

  old  基準 commit（--base-ref）の sc_tree_to_df.py・money.py・strategic_kpi.py
  new  今の作業ツリーの同じ 3 本

の両方を当てて比べる。old のコードは `git show <ref>:<path>` で取り出し、別名のモジュールと
して読み込む（作業ツリーは変えない）。

出力（<out>/ の下）:
  s2_compare.csv   モデル×方式の 1 行：要求 Σ・実出荷 Σ・当週充足 Σ・当週未充足 Σ、
                   money の売上・原価（old／new）、PPC の売上、Strategic KPI の充足率（old／new）、
                   legacy の全列一致（legacy_identical）
  s2_compare.json  同じ内容と、市場 leaf ごとの内訳
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
OLD_COLS = ["scenario", "sku_id", "region", "week", "opening_inv", "supply_receipt", "gross_avail",
            "demand_fcst", "demand_fulfilled", "stockout_qty", "closing_inv", "safety_stock_qty",
            "reorder_qty", "fill_rate", "inv_cover_wks", "inv_value", "co_qty", "ship_qty"]


def _load_old(ref, rel, name, tmp):
    src = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=REPO, capture_output=True, check=True).stdout
    path = os.path.join(tmp, name + ".py")
    with open(path, "wb") as f:
        f.write(src)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # dataclasses need the module to be registered
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
    ap.add_argument("--out", default=os.path.join("output", "smartphone_evupdate_s2", "C"))
    ap.add_argument("--base-ref", default="979cf7a")
    ap.add_argument("--models", default="all")
    a = ap.parse_args(argv)
    import pandas as pd
    import tools.run_headless_from_folder as rh
    from wom.data.schema import Cols
    from wom.engine.sc_tree_to_df import sc_tree_to_planning_df, apply_inv_value
    from wom.engine.money import evaluate_money, build_scenario_money_kpi
    from wom.engine.strategic_kpi import compute_strategic_kpi

    os.makedirs(a.out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="s2_old_")
    old_df_mod = _load_old(a.base_ref, "wom/engine/sc_tree_to_df.py", "old_sc_tree_to_df", tmp)
    old_money = _load_old(a.base_ref, "wom/engine/money.py", "old_money", tmp)
    old_skpi = _load_old(a.base_ref, "wom/engine/strategic_kpi.py", "old_strategic_kpi", tmp)

    store = {}
    o_sig = rh._psi_signature

    def sig(t, n):
        store["tree"] = t
        return o_sig(t, n)

    rh._psi_signature = sig
    only = None if a.models == "all" else set(a.models.split(","))
    rows, detail = [], {}
    try:
        for case, plugins in _jobs():
            if only and case not in only:
                continue
            for mode in ("identity", "legacy"):
                work = os.path.join(tmp, f"{case}__{mode}")
                shutil.copytree(os.path.join(REPO, "data", "sample", case), work)
                try:
                    snap = rh.run(work, plugins_spec=plugins, output_ppc_dir=os.path.join(work, "_ppc"),
                                  verbose=False, lot_flow_mode=mode)
                except Exception as exc:                      # a model that does not run in this mode
                    rows.append({"model": case, "mode": mode, "error": f"{type(exc).__name__}: {exc}"})
                    print(case, mode, "ERROR", exc, flush=True)
                    continue
                tree = store["tree"]
                sku_master = pd.read_csv(os.path.join(work, "sku_master.csv"))
                new = sc_tree_to_planning_df(tree)             # mode from the tree marker
                old = old_df_mod.sc_tree_to_planning_df(tree)
                apply_inv_value(new, sku_master); old_df_mod.apply_inv_value(old, sku_master)
                _nw, new_sum = evaluate_money(new, sku_master)
                _ow, old_sum = old_money.evaluate_money(old, sku_master)
                new_kpi = build_scenario_money_kpi(new_sum).iloc[0]
                old_kpi = old_money.build_scenario_money_kpi(old_sum).iloc[0]
                leaf = ~new[Cols.REGION].astype(str).str.startswith("DAD:")
                oleaf = ~old[Cols.REGION].astype(str).str.startswith("DAD:")
                same_cols = all(
                    (new[c].equals(old[c])) for c in OLD_COLS if c in old.columns)
                money_cols = [c for c in old_sum.columns]
                same_money = all(new_sum[c].equals(old_sum[c]) for c in money_cols)
                r = {
                    "model": case, "mode": mode, "qty_basis": "/".join(sorted(set(new[Cols.QTY_BASIS]))),
                    "leaf_demand_fcst": float(new.loc[leaf, Cols.DEMAND_FCST].sum()),
                    "leaf_request": float(new.loc[leaf, Cols.REQUEST_QTY].sum()),
                    "leaf_ship": float(new.loc[leaf, Cols.SHIP_QTY].sum()),
                    "leaf_on_time": float(new.loc[leaf, Cols.ON_TIME_QTY].sum()) if mode == "identity" else "",
                    "leaf_fulfilled_old": float(old.loc[oleaf, Cols.DEMAND_FULFILLED].sum()),
                    "leaf_fulfilled_new": float(new.loc[leaf, Cols.DEMAND_FULFILLED].sum()),
                    "leaf_stockout_old": float(old.loc[oleaf, Cols.STOCKOUT_QTY].sum()),
                    "leaf_stockout_new": float(new.loc[leaf, Cols.STOCKOUT_QTY].sum()),
                    "leaf_fill_mean_old": float(old.loc[oleaf, Cols.FILL_RATE].mean()),
                    "leaf_fill_mean_new": float(new.loc[leaf, Cols.FILL_RATE].mean()),
                    "leaf_fill_max_new": float(new.loc[leaf, Cols.FILL_RATE].max()),
                    "dad_fulfilled_old": float(old.loc[~oleaf, Cols.DEMAND_FULFILLED].sum()),
                    "dad_fulfilled_new": float(new.loc[~leaf, Cols.DEMAND_FULFILLED].sum()),
                    "money_revenue_old": float(old_kpi["revenue"]), "money_revenue_new": float(new_kpi["revenue"]),
                    "money_cogs_old": float(old_kpi["cogs"]), "money_cogs_new": float(new_kpi["cogs"]),
                    "money_units_old": float(old_kpi["units"]), "money_units_new": float(new_kpi["units"]),
                    "ppc_revenue_base": snap["ppc"]["revenue_base"],
                    "ppc_base_currency": snap["ppc"]["base_currency"],
                    "skpi_fill_old": old_skpi.compute_strategic_kpi(tree).fill_rate,
                    "skpi_fill_new": compute_strategic_kpi(tree).fill_rate,
                    "legacy_identical": (same_cols and same_money) if mode == "legacy" else "",
                    "old_columns_identical": same_cols, "money_identical": same_money,
                }
                rows.append(r)
                g = new.loc[leaf].groupby([Cols.SKU_ID, Cols.REGION]).agg(
                    request=(Cols.REQUEST_QTY, "sum"), ship=(Cols.SHIP_QTY, "sum"),
                    stockout=(Cols.STOCKOUT_QTY, "sum")).reset_index()
                detail[f"{case}__{mode}"] = g.to_dict("records")
                print(case, mode, r["qty_basis"], "request", r["leaf_request"], "ship", r["leaf_ship"],
                      "rev old/new", r["money_revenue_old"], r["money_revenue_new"],
                      "ppc", r["ppc_revenue_base"], "fill old/new", round(r["skpi_fill_old"], 4),
                      round(r["skpi_fill_new"], 4), "legacy_identical", r["legacy_identical"], flush=True)
    finally:
        rh._psi_signature = o_sig
        shutil.rmtree(tmp, ignore_errors=True)
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(os.path.join(a.out, "s2_compare.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    with open(os.path.join(a.out, "s2_compare.json"), "w", encoding="utf-8") as f:
        json.dump({"base_ref": a.base_ref, "rows": rows, "leaf_detail": detail}, f,
                  ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
