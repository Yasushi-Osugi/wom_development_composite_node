# -*- coding: utf-8 -*-
"""
wom/allocation/handoff.py — 第1層(A系統) → 第2層(Planning Engine) のハンドオフ
================================================================================
配分比率 `x[m]` から `demand_forecast_<allocation_id>.csv` を生成する。これが
note 記事で「生産配分の確定の意思入れ」と呼んだ操作の実体である。Planning Engine
は生成された CSV を通常どおり読むだけなので、禁足コアは無変更。

正典: requests/Phase7_RequestLetter_to_CodeKun.md V2

スケーリングの規則（V2.2、曖昧にしない）:
  1. 市場ごとの目標数量 q[m] = min(x[m] × cap_wk × weeks, demand[m])
     （`evaluate_point()` と同じ式。配分は需要を増やさない）
  2. 市場 → 地域は `ga_market_aggregation.csv` の `internal_ratio` で按分する
  3. 地域 → 週は元の週次形状に比例させる（季節性を壊さない）
  4. 端数は最大剰余法（largest remainder）で配る。合計が1 lot もずれないこと
  5. 需要ゼロの週はゼロのまま（warmup の助走行を潰さない）
  6. 列・行順は元と同一にする（差分が読めるように）

`uom` で絞り込んだ配分問題に含まれない地域（他 SKU 系統の需要行）は、この関数の
対象外として**元の値のまま素通し**する——このハンドオフは「対象市場の配分を
確定する」操作であり、無関係な系統の需要を勝手にゼロにしない。
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict
from typing import Dict, List, Optional

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.grid import WEEKS, markets_of

DEMAND_COLUMNS = ["sku_id", "region", "week", "quantity"]


def _rows(model_dir: str, fname: str) -> List[dict]:
    path = os.path.join(model_dir, fname)
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _largest_remainder(weights: Dict[str, float], total: int) -> Dict[str, int]:
    """`weights`（非負）の比率で整数 `total` を配る。合計は厳密に `total` になる。

    重み 0 のキーは常に 0 のまま（Step 5: 需要ゼロの週はゼロのまま・端数の
    +1 を受け取らない）。重みの合計が 0 なら（total も通常 0 のはずだが）
    全キーに 0 を割り当てる。
    """
    keys = list(weights.keys())
    wsum = sum(weights.values())
    if wsum <= 0 or total <= 0:
        return {k: 0 for k in keys}

    raw = {k: total * weights[k] / wsum for k in keys}
    floors = {k: int(raw[k]) for k in keys}
    remainder = total - sum(floors.values())

    # 端数の大きい順（同値は決定的にキー順）に +1 を配る。重み0のキーは
    # raw==floor==0 なので remainder==0 となり、自動的に対象外になる。
    order = sorted(keys, key=lambda k: (-(raw[k] - floors[k]), k))
    for k in order[:remainder]:
        floors[k] += 1
    return floors


def write_demand_for_allocation(model_dir: str, allocation: Dict[str, float],
                                allocation_id: str, *, cap_wk: float,
                                weeks: int = WEEKS, uom: Optional[str] = None,
                                demand_file: str = "demand_forecast.csv",
                                out_path: Optional[str] = None) -> dict:
    """配分比率から `demand_forecast_<allocation_id>.csv` を生成する。

    Args:
        model_dir: モデルフォルダ
        allocation: {market: x[m]}（`Σx=1` を仮定するが検査はしない——
            `evaluate_point()` と同じく `q[m]=min(x[m]*cap, demand[m])` を
            そのまま適用する）
        allocation_id: 出力ファイル名に使う ID（例 "A03"）
        cap_wk: 週次能力（lot/週）
        weeks: 計画期間（週数、既定 `wom.allocation.grid.WEEKS`=104）
        uom: `derive_cost_blocks(uom=...)` に渡す（複数 uom 混在モデル用）
        demand_file: 読み込む元の需要 CSV（既定 "demand_forecast.csv"）
        out_path: 出力先（既定 `<model_dir>/demand_forecast_<allocation_id>.csv`）

    Returns:
        {"path": str, "per_market": {market: qty}, "per_region": {region: qty},
         "scale": {market: float}, "total_before": int, "total_after": int}

    Raises:
        ValueError: 検算（Σper_region == Σper_market、total_after <= total_before）
            が破れた場合。書き出しはしない。
    """
    blocks, _tp = derive_cost_blocks(model_dir, uom=uom)
    markets = markets_of(blocks)

    # 1) 市場ごとの目標数量（Step 1）。市場ごとに独立に丸める。
    cap = cap_wk * weeks
    per_market: Dict[str, int] = {}
    for m in markets:
        x = float(allocation.get(m, 0.0))
        q = min(x * cap, float(blocks[m].demand_qty))
        per_market[m] = round(q)

    # 2) 市場 → 地域（Step 2・ga_market_aggregation.csv の internal_ratio）
    agg_rows = _rows(model_dir, "ga_market_aggregation.csv")
    rows_for_market: Dict[str, List[dict]] = defaultdict(list)
    for r in agg_rows:
        if r["market_group"] in markets:
            rows_for_market[r["market_group"]].append(r)

    per_region: Dict[str, int] = {}
    for m in markets:
        regs = rows_for_market.get(m, [])
        region_weights = {r["region"]: float(r["internal_ratio"]) for r in regs}
        per_region.update(_largest_remainder(region_weights, per_market[m]))

    if sum(per_region.values()) != sum(per_market.values()):
        raise ValueError(
            f"write_demand_for_allocation(): region total "
            f"({sum(per_region.values())}) != market total "
            f"({sum(per_market.values())}) after largest-remainder split"
        )

    # 3) 地域 → 週（Step 3・元の週次形状に比例、Step 4 最大剰余法、Step 5 ゼロ週維持）。
    #    per_region に無い地域（uom で絞り込んだ配分問題の対象外＝他 SKU 系統）は
    #    元の値のまま素通しする（勝手にゼロにしない）。
    dem_rows = _rows(model_dir, demand_file)

    # RequestLetter_QuantityAllocationMode C.4: the weights below are per region
    # over ALL sku rows and every row of a region-week gets the same quantity, so
    # a region shared by 2+ SKUs would be counted twice (even a 0 row of the second
    # SKU receives the region-week quantity). Stop instead of passing.
    skus_by_region: Dict[str, set] = defaultdict(set)
    for r in dem_rows:
        if r["region"] in per_region:
            skus_by_region[r["region"]].add(r["sku_id"])
    shared = {reg: sorted(s) for reg, s in skus_by_region.items() if len(s) > 1}
    if shared:
        raise ValueError(
            "write_demand_for_allocation(): a region to allocate has demand rows of "
            "2+ sku_id, so the ratio route would count it twice (not supported; use "
            "the quantity route keyed by (sku_id, region)): "
            + "; ".join(f"{reg}: {skus}" for reg, skus in sorted(shared.items())))
    region_week_weight: Dict[str, Dict[str, float]] = defaultdict(dict)
    for r in dem_rows:
        wk = r["week"]
        region_week_weight[r["region"]][wk] = \
            region_week_weight[r["region"]].get(wk, 0.0) + float(r["quantity"])

    new_qty_by_region_week: Dict[str, Dict[str, int]] = {}
    for region in per_region:
        week_weights = region_week_weight.get(region, {})
        new_qty_by_region_week[region] = _largest_remainder(week_weights, per_region[region])

    # 4) 元の行順・列を保ったまま quantity だけ差し替える（Step 6）
    out_rows: List[dict] = []
    total_before = 0
    total_after = 0
    for r in dem_rows:
        region, week = r["region"], r["week"]
        orig_q = int(float(r["quantity"]))
        total_before += orig_q
        if region in new_qty_by_region_week:
            new_q = new_qty_by_region_week[region].get(week, 0)
        else:
            new_q = orig_q            # 対象外の地域は素通し
        total_after += new_q
        out_rows.append({"sku_id": r["sku_id"], "region": region, "week": week,
                         "quantity": str(new_q)})

    if total_after > total_before:
        raise ValueError(
            f"write_demand_for_allocation(): total_after ({total_after}) > "
            f"total_before ({total_before}) — allocation must not increase demand"
        )

    out_path = out_path or os.path.join(model_dir, f"demand_forecast_{allocation_id}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DEMAND_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)

    scale = {m: (per_market[m] / blocks[m].demand_qty if blocks[m].demand_qty else 0.0)
            for m in markets}

    return {
        "path": out_path,
        "per_market": per_market,
        "per_region": dict(per_region),
        "scale": scale,
        "total_before": total_before,
        "total_after": total_after,
    }


# ──────────────────────────────────────────────────────────────────────────
# Quantity allocation mode (RequestLetter_QuantityAllocationMode C.1)
# ──────────────────────────────────────────────────────────────────────────
#
# A person decides the allocation in LOTS per (sku_id, region). No price, cost,
# FX or ga_* file is read (derive_cost_blocks is not called): only the demand
# CSV and the allocation file. Quantities, per key (same demand set, same unit):
#   q1 original demand = q2 in supply scope + q3 not in supply scope

ALLOC_QTY_COLUMNS = ["sku_id", "region", "alloc_lots"]


class QuantityAllocationError(ValueError):
    """The allocation file cannot be used. Nothing is written."""


def read_quantity_allocation(alloc_path: str) -> Dict[tuple, int]:
    """allocation_qty_<id>.csv -> {(sku_id, region): alloc_lots}. Stops (listing
    every bad row at once) on a missing column, a duplicate key, or a value that
    is not an integer >= 0."""
    with open(alloc_path, "r", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        missing = [c for c in ALLOC_QTY_COLUMNS if c not in (rd.fieldnames or [])]
        if missing:
            raise QuantityAllocationError(f"{alloc_path}: missing column(s) {missing}")
        rows = list(rd)
    out: Dict[tuple, int] = {}
    errors: List[str] = []
    for n, r in enumerate(rows, start=2):
        key = (r["sku_id"].strip(), r["region"].strip())
        raw = (r["alloc_lots"] or "").strip()
        try:
            v = float(raw)
            ok = v >= 0 and v == int(v)
        except ValueError:
            ok = False
        if not ok:
            errors.append(f"line {n} {key}: alloc_lots={raw!r} is not an integer >= 0")
            continue
        if key in out:
            errors.append(f"line {n} {key}: duplicate key")
            continue
        out[key] = int(v)
    if errors:
        raise QuantityAllocationError(f"{alloc_path}: " + "; ".join(errors))
    return out


def write_demand_for_quantity_allocation(model_dir: str, alloc_path: str, allocation_id: str,
                                         *, demand_file: str = "demand_forecast.csv",
                                         out_path: Optional[str] = None) -> dict:
    """Write `demand_forecast_<allocation_id>.csv` from lot quantities per (sku_id, region).

    - Each key's `alloc_lots` is spread over that key's rows in proportion to their
      weekly quantity (largest remainder); weeks with 0 demand stay 0.
    - A key with alloc_lots == its original total keeps its rows verbatim.
    - Columns and row order are those of the demand CSV (0 rows are kept).
    - Stops (nothing written, every bad key listed): alloc_lots > the key's
      original total; a key with >= 1 lot of demand missing from the file; a key
      not in the demand CSV; duplicate / non-integer / negative values.
    - After writing, the file is read back and q2 per key must equal alloc_lots.

    Returns {"path", "keys": [{sku_id, region, q1_original, q2_in_supply_scope,
    q3_not_in_supply_scope}], "totals": {...}}.
    """
    alloc = read_quantity_allocation(alloc_path)
    src = os.path.join(model_dir, demand_file)
    with open(src, "r", encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        fieldnames = list(rd.fieldnames or [])
        dem_rows = list(rd)
    for c in DEMAND_COLUMNS:
        if c not in fieldnames:
            raise QuantityAllocationError(f"{src}: missing column {c!r}")

    def _q(r):
        return int(float(r["quantity"] or 0))

    rows_by_key: Dict[tuple, List[int]] = defaultdict(list)
    for i, r in enumerate(dem_rows):
        rows_by_key[(r["sku_id"], r["region"])].append(i)
    q1 = {k: sum(_q(dem_rows[i]) for i in idx) for k, idx in rows_by_key.items()}

    errors: List[str] = []
    for k in sorted(alloc):
        if k not in q1:
            errors.append(f"{k}: not in {demand_file}")
        elif alloc[k] > q1[k]:
            errors.append(f"{k}: alloc_lots {alloc[k]} > original demand {q1[k]} "
                          f"(an allocation never adds demand)")
    for k in sorted(q1):
        if q1[k] >= 1 and k not in alloc:
            errors.append(f"{k}: has {q1[k]} lot(s) of demand but no row in the allocation file")
    if errors:
        raise QuantityAllocationError(
            f"{os.path.basename(alloc_path)}: " + "; ".join(errors))

    new_q: Dict[int, str] = {}
    for k, idx in rows_by_key.items():
        a = alloc.get(k, 0)               # only keys with 0 demand can be absent here
        if a == q1[k]:
            continue                      # verbatim
        shares = _largest_remainder({i: float(_q(dem_rows[i])) for i in idx}, a)
        for i in idx:
            new_q[i] = str(shares[i])

    out_path = out_path or os.path.join(model_dir, f"demand_forecast_{allocation_id}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        for i, r in enumerate(dem_rows):
            w.writerow(dict(r, quantity=new_q[i]) if i in new_q else r)

    # read back: q2 per key must equal alloc_lots
    with open(out_path, "r", encoding="utf-8", newline="") as f:
        back = list(csv.DictReader(f))
    q2: Dict[tuple, int] = defaultdict(int)
    for r in back:
        q2[(r["sku_id"], r["region"])] += _q(r)
    bad = [f"{k}: written {q2.get(k, 0)} != alloc_lots {alloc.get(k, 0)}"
           for k in sorted(q1) if q2.get(k, 0) != alloc.get(k, 0)]
    if bad or len(back) != len(dem_rows):
        raise QuantityAllocationError(
            f"write_demand_for_quantity_allocation(): read-back mismatch: " + "; ".join(bad))

    keys = [{"sku_id": k[0], "region": k[1], "q1_original": q1[k],
             "q2_in_supply_scope": alloc.get(k, 0),
             "q3_not_in_supply_scope": q1[k] - alloc.get(k, 0)} for k in sorted(q1)]
    totals = {c: sum(r[c] for r in keys)
              for c in ("q1_original", "q2_in_supply_scope", "q3_not_in_supply_scope")}
    return {"path": out_path, "keys": keys, "totals": totals}
