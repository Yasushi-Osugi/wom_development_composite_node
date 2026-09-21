---
tags: [wom, code]
---
# wom/allocation/handoff.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/allocation/handoff.py) · [原文テキスト](../../../90_Raw/wom/allocation/handoff.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/02_Demand_Allocation|Optimization on Demand Allocation]]

## モジュール説明（docstring原文）

```text
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
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_rows` | 37 | docstringなし（下のコード参照） |
| FunctionDef | `_largest_remainder` | 43 | `weights`（非負）の比率で整数 `total` を配る。合計は厳密に `total` になる。 |
| FunctionDef | `write_demand_for_allocation` | 67 | 配分比率から `demand_forecast_<allocation_id>.csv` を生成する。 |

## 関連する知識源

- [[80_Sources/requests/Phase7_RequestLetter_to_CodeKun.md|requests/Phase7_RequestLetter_to_CodeKun.md]]
- [[80_Sources/wom/allocation/cost_block.py|wom/allocation/cost_block.py]]
- [[80_Sources/wom/allocation/grid.py|wom/allocation/grid.py]]

## 全文（コメント・原文を省略せず収録）

````python
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

````
