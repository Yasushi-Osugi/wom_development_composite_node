# -*- coding: utf-8 -*-
"""
wom/allocation/regime_map.py — 生産配分のレジーム地図（Phase 4 ②）
================================================================================
配分空間ではなく、**外部環境パラメータ空間の2次元平面**を走査し、各点を
「そこで最適となる市場優先順位」で塗り分ける。境界線が決定反転面。

レジーム = `market_ranking()` が返す市場優先順位（既存 `analytics.py` の資産）。
描く平面は2次元に固定できるため、常に市場数 N に依存しない（設計正典 §4.1）。

`switching_points()` が1次元（FX軸）で走査しているものと同じ数学的対象の
2次元一般化にすぎない。`material_usd` を固定した水平断面が `switching_points()`
と一致することを回帰テストで確認する（§4.2、tests/test_allocation_regime_map.py）。

正典: requests/Phase4_DesignMD_AllocationMeritRegime.md §4
既存 A系統モジュール（transmission.py / analytics.py 等）は無変更。
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Tuple

from wom.allocation.transmission import CostBlock, DEFAULT_TRANSFER_PRICE_USD, Scenario, unit_pnl
from wom.allocation.grid import markets_of

_VALID_SCALAR_AXES = ("fx_usd", "material_usd")


def _validate_axis_name(axis_name: str, markets: Tuple[str, ...]) -> None:
    """軸名が 'fx_usd' / 'material_usd' / 'tariff_rate:<市場>' のいずれかであることを検証する。

    Phase 6-2: `markets` は markets_of(blocks) から呼び出し元が渡す
    （blocks を持たないこの関数自身は N を知らないため）。
    """
    if axis_name in _VALID_SCALAR_AXES:
        return
    if axis_name.startswith("tariff_rate:"):
        market = axis_name.split(":", 1)[1]
        if market in markets:
            return
        raise ValueError(
            f"Unknown market in axis {axis_name!r}: {market!r} "
            f"(must be one of {markets})"
        )
    raise ValueError(
        f"axis must be 'fx_usd', 'material_usd', or 'tariff_rate:<market>', "
        f"got {axis_name!r}"
    )


def _apply_axis(
    axis_name: str, value: float, scenario: Scenario, blocks: Dict[str, CostBlock]
) -> Tuple[Scenario, Dict[str, CostBlock]]:
    """軸1本分の値を scenario/blocks に適用する（他方は変更せず返す）。"""
    if axis_name == "fx_usd":
        return replace(scenario, fx_usd=value), blocks
    if axis_name == "material_usd":
        return replace(scenario, material_usd=value), blocks
    # tariff_rate:<market>
    market = axis_name.split(":", 1)[1]
    new_blocks = dict(blocks)
    new_blocks[market] = replace(blocks[market], tariff_rate=value)
    return scenario, new_blocks


def scan_regime_grid(
    blocks: Dict[str, CostBlock],
    axis_x: str, x_values: Sequence[float],
    axis_y: str, y_values: Sequence[float],
    *,
    transfer_price_usd: float = DEFAULT_TRANSFER_PRICE_USD,
    base_scenario: Optional[Scenario] = None,
) -> dict:
    """外部環境パラメータ平面を走査し、各点の市場優先順位を返す。

    Args:
        blocks: 市場 -> CostBlock（derive_cost_blocks() の戻り値。基準の関税率を含む）
        axis_x, axis_y: "fx_usd" | "material_usd" | "tariff_rate:<市場>"
        x_values, y_values: 各軸の走査値
        transfer_price_usd: 移転価格（USD）
        base_scenario: 軸で上書きされない成分（既定 fx_usd=150, material_usd=6.0）

    Returns:
        {
            "axis_x": "fx_usd", "x_values": [...],
            "axis_y": "material_usd", "y_values": [...],
            "regimes": [["EU>US>JP", ...], ...],   # [y][x] の順序ラベル
            "regime_ids": [[0, 0, 1, ...], ...],   # 描画用の整数ID
            "regime_labels": ["EU>US>JP", "US>EU>JP", ...],  # ID → ラベル（初出順）
            "margins": [[{"JP":..,"US":..,"EU":..}, ...], ...],
            "negative_margin_mask": [[["JP"], [], ...], ...],  # §3.2 と整合
        }

    Raises:
        ValueError: axis_x / axis_y が不正な軸名のとき
    """
    markets = markets_of(blocks)
    _validate_axis_name(axis_x, markets)
    _validate_axis_name(axis_y, markets)

    base_scenario = base_scenario or Scenario(fx_usd=150.0, material_usd=6.0)

    regimes: List[List[str]] = []
    regime_ids: List[List[int]] = []
    margins_grid: List[List[Dict[str, float]]] = []
    neg_mask_grid: List[List[List[str]]] = []

    label_to_id: Dict[str, int] = {}
    labels: List[str] = []

    for yv in y_values:
        sc_y, blocks_y = _apply_axis(axis_y, yv, base_scenario, blocks)

        row_labels: List[str] = []
        row_ids: List[int] = []
        row_margins: List[Dict[str, float]] = []
        row_neg: List[List[str]] = []

        for xv in x_values:
            sc_xy, blocks_xy = _apply_axis(axis_x, xv, sc_y, blocks_y)

            m = {mkt: unit_pnl(blocks_xy[mkt], sc_xy, transfer_price_usd)["margin"]
                 for mkt in markets}
            order = tuple(sorted(markets, key=lambda mkt: -m[mkt]))
            label = ">".join(order)

            if label not in label_to_id:
                label_to_id[label] = len(labels)
                labels.append(label)

            row_labels.append(label)
            row_ids.append(label_to_id[label])
            row_margins.append(m)
            row_neg.append([mkt for mkt in markets if m[mkt] <= 0])

        regimes.append(row_labels)
        regime_ids.append(row_ids)
        margins_grid.append(row_margins)
        neg_mask_grid.append(row_neg)

    return {
        "axis_x": axis_x, "x_values": list(x_values),
        "axis_y": axis_y, "y_values": list(y_values),
        "regimes": regimes,
        "regime_ids": regime_ids,
        "regime_labels": labels,
        "margins": margins_grid,
        "negative_margin_mask": neg_mask_grid,
    }
