#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/run_allocation_map.py — ask_global_allocation エンジン CLI
================================================================
モデルフォルダの CSV から、配分比率 231 点をシナリオ別に評価し、§7 の出力 CSV を
`output/allocation/` に書き出す。Planning Engine には一切触れない（Management 層）。

使い方（リポジトリ直下）:
  python -m tools.run_allocation_map --model-dir data/sample/soysauce-jpy-2027-alloc
  python -m tools.run_allocation_map --model-dir <dir> --cap-wk 800 --out output/allocation

出力（§7）:
  ga_cost_block_derived.csv   市場別 通貨別ブロック（監査・§5.1/#5）
  ga_profit_surface.csv       scenario × 231点（profit/rev/cost/FCR/FRR/FXB/idle/unmet）
  ga_fx_balance.csv           scenario × 231点（FCR/FRR/FXB・fxb=1.0 近傍フラグ）
  ga_plateau.csv              scenario（plateau_size/argmax/max_profit/robust_point）
  ga_switching_point.csv      為替走査の順位反転（#14・statement_ja つき）
  ga_interaction.csv          代表点の為替×原料 交互作用分解（§3.2/§A.5）
  ga_constraint_cost.csv      国内20%フロアのコスト（§5.6b）

利益は粗利ベース（Request Letter #16。営業利益 wc/sga は Step9-10・未実装）。
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from dataclasses import replace
from typing import Dict, List, Optional, Tuple

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.transmission import CostBlock, Scenario
from wom.allocation.grid import (markets_of, scan_surface, best_point, chosen_point,
                                 demand_ceilings, evaluate_point)
from wom.allocation.analytics import (switching_points, interaction, robust_point,
                                      constraint_cost)


# ---------------------------------------------------------------------------
def _rows(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_scenarios(model_dir: str) -> List[dict]:
    """ga_scenario_master.csv → シナリオごとの代表パラメータ。

    各 dict: {id, fx_usd, material_usd, tariff{market:rate}, interest, time_series,
              tariff_preferential{market:rate}, preferential_threshold{market:lot}}
    s1〜s7 は全期間一定。時系列（s8）は time_series=True としてサーフェス対象外にする。

    Phase 5（cliff型の数量依存関税）: `tariff_rate_preferential` /
    `preferential_threshold_lot` の2列を読む。両方が空欄でない市場のみ
    `tariff_preferential` / `preferential_threshold` に入る。**列が存在しない
    古い CSV でも動く**（`csv.DictReader` の行 dict に無いキーは `.get()` で
    None として扱われる）。
    """
    rows = _rows(os.path.join(model_dir, "ga_scenario_master.csv"))
    by_id: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        by_id[r["scenario_id"]].append(r)

    scens: List[dict] = []
    for sid, rs in by_id.items():
        # USD レート（fx_spot）・原料・関税（先頭 quarter）
        # Phase 6-5・E2: market == "US"（3市場固定の決め打ち）から
        # currency == "USD" に変更。oil-global-2027 のように market が
        # leaf_out ノード名（Retail_US_TX 等）になる N市場モデルでは
        # market == "US" が一致しない（wom/gui/s1_view_model.py の
        # _load_scenario_row() が既に currency 基準で N市場対応している
        # のと同じ基準に揃える）。
        usd_rows = [r for r in rs if r["currency"] == "USD"]
        fx_usd = float(usd_rows[0]["fx_spot_jpy"])
        material = float(rs[0]["material_price_usd"])
        q0 = rs[0]["quarter"]
        tariff = {r["market"]: float(r["tariff_rate"]) for r in rs if r["quarter"] == q0}

        tariff_preferential: Dict[str, float] = {}
        preferential_threshold: Dict[str, float] = {}
        for r in rs:
            if r["quarter"] != q0:
                continue
            rate_str = (r.get("tariff_rate_preferential") or "").strip()
            thr_str = (r.get("preferential_threshold_lot") or "").strip()
            if rate_str and thr_str:
                tariff_preferential[r["market"]] = float(rate_str)
                preferential_threshold[r["market"]] = float(thr_str)

        interest = float(rs[0]["interest_rate_annual"])
        # 時系列判定：いずれかの市場で (fx, material, tariff) が quarter 間で変動するか
        # Phase 6-2: MARKETS（3市場固定）ではなく、行に現れた市場から導出する
        # （blocks が無いこの関数では markets_of() を使えないため）。
        # dict.fromkeys() で順序を保ったまま重複除去（set は順序非決定的なので不可）。
        scen_markets = tuple(dict.fromkeys(r["market"] for r in rs))
        time_series = any(
            len({(float(r["fx_spot_jpy"]), float(r["material_price_usd"]), float(r["tariff_rate"]))
                 for r in rs if r["market"] == m}) > 1
            for m in scen_markets)
        scens.append({"id": sid, "fx_usd": fx_usd, "material_usd": material,
                      "tariff": tariff, "interest": interest, "time_series": time_series,
                      "tariff_preferential": tariff_preferential,
                      "preferential_threshold": preferential_threshold})
    return scens


def _blocks_for(
    base_blocks: Dict[str, CostBlock], tariff: Dict[str, float],
    tariff_preferential: Optional[Dict[str, float]] = None,
    preferential_threshold: Optional[Dict[str, float]] = None,
) -> Dict[str, CostBlock]:
    """シナリオの関税率で CostBlock を上書き（tariff は Step3 で使用）。

    Phase 5: `tariff_preferential` / `preferential_threshold` は既定 None
    （＝上書きなし、従来動作）。指定された市場のみ cliff 型の特恵税率・閾値を
    CostBlock に載せる。
    """
    tariff_preferential = tariff_preferential or {}
    preferential_threshold = preferential_threshold or {}
    result: Dict[str, CostBlock] = {}
    for m in markets_of(base_blocks):
        kwargs = {"tariff_rate": tariff.get(m, base_blocks[m].tariff_rate)}
        if m in tariff_preferential:
            kwargs["tariff_rate_preferential"] = tariff_preferential[m]
        if m in preferential_threshold:
            kwargs["preferential_threshold_lot"] = preferential_threshold[m]
        result[m] = replace(base_blocks[m], **kwargs)
    return result


def _fmt_x(x) -> str:
    return f"{x[0]:.2f}|{x[1]:.2f}|{x[2]:.2f}"


# ---------------------------------------------------------------------------
def run(model_dir: str, cap_wk: float = 800.0, out_dir: str = "output/allocation",
        delta: float = 0.05, verbose: bool = True) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    base_blocks, tp = derive_cost_blocks(model_dir)
    scens = load_scenarios(model_dir)
    const_scens = [s for s in scens if not s["time_series"]]
    eval_scenarios = [Scenario(fx_usd=s["fx_usd"], material_usd=s["material_usd"])
                      for s in const_scens]

    # サーフェスをシナリオ別に計算（関税上書き込み、Phase 5: cliff型の特恵込み）
    surfaces: Dict[str, Tuple[list, Dict[str, CostBlock]]] = {}
    for s in const_scens:
        blocks = _blocks_for(base_blocks, s["tariff"],
                             s.get("tariff_preferential"), s.get("preferential_threshold"))
        S = Scenario(fx_usd=s["fx_usd"], material_usd=s["material_usd"])
        surfaces[s["id"]] = (scan_surface(blocks, tp, S, cap_wk, delta=delta), blocks)

    written: Dict[str, str] = {}

    def _w(name, header, rows):
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)
        written[name] = path

    # 1) ga_cost_block_derived.csv（監査）
    _w("ga_cost_block_derived.csv",
       ["market", "usd", "eur", "jpy", "tariff_rate", "price_local", "ccy", "demand_qty", "material_usd_base", "transfer_price_usd"],
       [[m, b.usd, b.eur, b.jpy, b.tariff_rate, b.price_local, b.ccy, b.demand_qty, b.material_usd_base, round(tp, 6)]
        for m, b in base_blocks.items()])

    # 2) ga_profit_surface.csv / 3) ga_fx_balance.csv
    ps_rows, fx_rows = [], []
    for sid, (surf, _b) in surfaces.items():
        for r in surf:
            x = r["x"]
            ps_rows.append([sid, x[0], x[1], x[2], round(r["profit"], 3), round(r["rev"], 3),
                            round(r["cost"], 3), round(r["idle"], 1),
                            r["unmet"]["JP"], r["unmet"]["US"], r["unmet"]["EU"],
                            round(r["FCR"], 6), round(r["FRR"], 6),
                            (round(r["FXB"], 6) if r["FXB"] != float("inf") else "")])
            fx_rows.append([sid, x[0], x[1], x[2], round(r["FCR"], 6), round(r["FRR"], 6),
                            (round(r["FXB"], 6) if r["FXB"] != float("inf") else ""),
                            (1 if (r["FXB"] != float("inf") and abs(r["FXB"] - 1.0) <= 0.02) else 0)])
    _w("ga_profit_surface.csv",
       ["scenario_id", "x_jp", "x_us", "x_eu", "profit", "rev", "cost", "idle",
        "unmet_jp", "unmet_us", "unmet_eu", "fcr", "frr", "fxb"], ps_rows)
    _w("ga_fx_balance.csv",
       ["scenario_id", "x_jp", "x_us", "x_eu", "fcr", "frr", "fxb", "fxb_neutral_near"], fx_rows)

    # 4) ga_plateau.csv（robust_point 込み）
    pl_rows = []
    for sid, (surf, blocks) in surfaces.items():
        best, plateau = best_point(surf)
        fxbs = [r["FXB"] for r in plateau if r["FXB"] != float("inf")]
        rp = robust_point(plateau, blocks, tp, eval_scenarios, cap_wk)
        argmax = chosen_point(surf)["x"]   # 格子の真の最良点（Phase 6-5・E1）
        argmax_worst = min(evaluate_point(argmax, blocks, tp, sc, cap_wk)["profit"]
                           for sc in eval_scenarios)
        pl_rows.append([sid, len(plateau), round(best, 1), _fmt_x(argmax),
                        (round(min(fxbs), 4) if fxbs else ""), (round(max(fxbs), 4) if fxbs else ""),
                        _fmt_x(rp["robust_point"]), round(rp["robust_worst_profit"], 1),
                        round(argmax_worst, 1)])
    _w("ga_plateau.csv",
       ["scenario_id", "plateau_size", "max_profit", "argmax", "fxb_min", "fxb_max",
        "robust_point", "robust_worst_profit", "argmax_worst_profit"], pl_rows)

    # 5) ga_switching_point.csv（基準関税で走査）
    base_blocks_for_switch = _blocks_for(base_blocks, {"JP": 0.0, "US": 0.125, "EU": 0.08})
    sw = switching_points(base_blocks_for_switch, tp, fx_lo=100, fx_hi=220)
    sw_rows = []
    for p in sw:
        order = " > ".join(p["order"])
        stmt = f"USD/JPY が {p['fx']} 円で市場順位 {order}"
        sw_rows.append([p["fx"], order, round(p["margins"]["JP"]), round(p["margins"]["US"]),
                        round(p["margins"]["EU"]), stmt])
    _w("ga_switching_point.csv",
       ["fx_threshold_jpy", "order", "margin_jp", "margin_us", "margin_eu", "statement_ja"], sw_rows)

    # 6) ga_interaction.csv（代表3点 × s4 基準の分解）
    inter_pts = [("base", (0.30, 0.35, 0.35)), ("optimum", (0.10, 0.45, 0.45)),
                 ("domestic_heavy", (0.60, 0.20, 0.20))]
    in_rows = []
    for label, x in inter_pts:
        r = interaction(x, base_blocks, tp, cap_wk)
        in_rows.append([label, _fmt_x(x), round(r["fx_only"], 1), round(r["mat_only"], 1),
                        round(r["total"], 1), round(r["interaction"], 1),
                        round(r["ratio"], 4), int(r["layer_decomposition_valid"])])
    _w("ga_interaction.csv",
       ["point_label", "x", "fx_only", "mat_only", "total", "interaction", "ratio",
        "layer_decomposition_valid"], in_rows)

    # 7) ga_constraint_cost.csv（国内20%フロア × 各シナリオ）
    cc_rows = []
    for s in const_scens:
        blocks = _blocks_for(base_blocks, s["tariff"],
                             s.get("tariff_preferential"), s.get("preferential_threshold"))
        S = Scenario(fx_usd=s["fx_usd"], material_usd=s["material_usd"])
        r = constraint_cost(blocks, tp, S, cap_wk, constraint=lambda x: x[0] >= 0.20, delta=delta)
        cc_rows.append([s["id"], "x_JP>=0.20", round(r["profit_unconstrained"], 1),
                        round(r["profit_constrained"], 1), round(r["cost_of_constraint"], 1),
                        r["feasible_points"]])
    _w("ga_constraint_cost.csv",
       ["scenario_id", "constraint", "profit_unconstrained", "profit_constrained",
        "cost_of_constraint", "feasible_points"], cc_rows)

    if verbose:
        ceil = demand_ceilings(base_blocks, cap_wk)
        mname = os.path.basename(model_dir.rstrip("/\\"))
        print(f"[allocation] model={mname} cap={cap_wk}/wk transfer_price=${tp:.2f}")
        print(f"[allocation] scenarios: {len(const_scens)} constant "
              f"(+{len(scens)-len(const_scens)} time-series skipped)")
        print(f"[allocation] demand ceilings: " +
              " ".join(f"x_{m}={ceil[m]:.3f}" for m in ceil))
        for sid, (surf, _b) in surfaces.items():
            best, plateau = best_point(surf)
            print(f"   {sid:18s} max={best/1e6:8.1f}M plateau={len(plateau):2d} "
                  f"argmax={_fmt_x(chosen_point(surf)['x'])}")   # Phase 6-5・E1
        print(f"[allocation] wrote {len(written)} files -> {out_dir}/")
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ask_global_allocation engine CLI (§7 outputs).")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--cap-wk", type=float, default=800.0)
    ap.add_argument("--out", default="output/allocation")
    ap.add_argument("--delta", type=float, default=0.05)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    run(a.model_dir, cap_wk=a.cap_wk, out_dir=a.out, delta=a.delta, verbose=not a.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
