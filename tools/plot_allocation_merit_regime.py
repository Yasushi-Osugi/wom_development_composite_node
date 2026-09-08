#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/plot_allocation_merit_regime.py — 生産配分のメリットオーダー曲線 + レジーム地図（Phase 4）
================================================================================================
A系統（`ask_global_allocation`・年次「どの市場に何個供給するか」）向けの静止画描画層。

Phase 3（`tools/plot_merit_order_suite.py`）とは**対象問題が異なる**ため、あえて別ファイルに
分離している（設計正典 §1.1 / §5.2）。図法は似ているが、並び順（単位マージン降順）・
交点の意味（能力のシャドープライス λ）が入れ替わる。

設計正典: requests/Phase4_DesignMD_AllocationMeritRegime.md §3-5
参照実装: tools/plot_allocation_map.py（matplotlib の書き方・慣行）

制約（Phase 3 §6.1 を継承）:
    - matplotlib のみ（plotly/bokeh/dash/streamlit/seaborn 禁止）
    - 新規依存パッケージなし
    - matplotlib.use("Agg") は pyplot import の前
    - 図中のテキストは全て英語
    - 各描画関数は出力パスを返す（plt.close(fig) を必ず呼ぶ）
    - 凡例をデータの上に重ねない（軸レンジを緩めて余白を作らない）
    - 禁足コア無接触

使い方（リポジトリ直下）:
    python -m tools.plot_allocation_merit_regime \\
        --model-dir data/sample/soysauce-jpy-2027-alloc --cap-wk 800 --scenario s1_base \\
        --out output/allocation/
    python -m tools.plot_allocation_merit_regime --model-dir <dir> --demo
"""
from __future__ import annotations

import argparse
import os
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")          # 必ず pyplot より前
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.transmission import Scenario
from wom.allocation.grid import MARKETS, scan_surface
from wom.allocation.merit_order import build_allocation_merit_order, compare_with_grid
from wom.allocation.regime_map import scan_regime_grid
from tools.run_allocation_map import load_scenarios, _blocks_for


# ---------------------------------------------------------------------------
# ① メリットオーダー曲線（配分版）
# ---------------------------------------------------------------------------

_DARK = "#2E6DB5"
_LIGHT = "#BFD3EA"
_EXCLUDED_HATCH_FC = "#F5E3E3"
_EXCLUDED_EDGE = "#B5504A"


def _draw_block(ax, x_left: float, width: float, height: float, color: str,
                *, hatch: Optional[str] = None, edgecolor: str = "white") -> None:
    if width <= 0:
        return
    ax.bar(x_left, height, width=width, align="edge", color=color,
           edgecolor=edgecolor, linewidth=0.8, zorder=2, hatch=hatch)


def plot_allocation_merit_order(
    mo: dict,
    out: str,
    *,
    comparison: Optional[dict] = None,
    title: Optional[str] = None,
) -> str:
    """メリットオーダー曲線（配分版）を描画し、保存先パスを返す。

    Args:
        mo: build_allocation_merit_order() の戻り値
        out: 出力 PNG パス
        comparison: compare_with_grid() の戻り値（渡すと格子最適との乖離を注記）
        title: 図タイトル（None なら自動生成）
    """
    cap = mo["cap"]

    fig, ax = plt.subplots(figsize=(9.5, 5.8))

    x_left = 0.0
    for b in mo["blocks"]:
        w = b["width"]
        h = b["margin"]
        x_right = x_left + w

        if x_right <= cap:
            _draw_block(ax, x_left, w, h, _DARK)
        elif x_left >= cap:
            _draw_block(ax, x_left, w, h, _LIGHT)
        else:
            _draw_block(ax, x_left, cap - x_left, h, _DARK)
            _draw_block(ax, cap, x_right - cap, h, _LIGHT)

        total_span = max(x_right, cap, 1.0)
        if w / total_span > 0.04:
            ax.text(x_left + w / 2, h / 2, b["market"], ha="center", va="center",
                    fontsize=9, color="white", zorder=3)

        x_left = x_right

    # 負マージン市場（除外）: Y の負側にハッチで描く。能力線とは無関係（常に非供給、§3.2 R1）。
    # 積み上げた供給ブロックの右側に、除外市場を並べて表示する（幅は未充足需要=全量）。
    excl_x = x_left
    for m in mo["excluded"]:
        w = mo["unmet"].get(m, 0.0)
        h = mo["excluded_margins"].get(m, 0.0)
        _draw_block(ax, excl_x, w, h, _EXCLUDED_HATCH_FC, hatch="////", edgecolor=_EXCLUDED_EDGE)
        if w > 0:
            ax.text(excl_x + w / 2, h / 2, m, ha="center", va="center",
                    fontsize=9, color=_EXCLUDED_EDGE, zorder=3)
        excl_x += w

    if mo["excluded"]:
        ax.text(
            0.02, 0.02,
            "Excluded (negative margin, not supplied): " + ", ".join(mo["excluded"]),
            transform=ax.transAxes, ha="left", va="bottom", fontsize=8.5, color=_EXCLUDED_EDGE,
        )

    if cap > 0:
        ax.axvline(cap, color="black", linestyle="--", linewidth=1.4, zorder=4,
                   label=f"capacity = {cap:,.0f} lots")

    lam = mo["lambda"]
    marginal = mo["marginal_market"]
    if marginal is not None:
        ax.axhline(lam, color="crimson", linestyle=":", linewidth=1.3, zorder=4)

    # G3: 単位マージン降順に積む以上、左上には必ず最も背の高いブロックが来て
    # 軸内に安全な置き場所が無い（Phase 3 の昇順とは前提が逆）。注記は軸の下へ。
    idle = mo["idle"]
    total_unmet = sum(mo["unmet"].values())

    notes = []
    if marginal is not None:
        notes.append((
            f"lambda = {lam:.1f} JPY/lot (shadow price of capacity, marginal market: {marginal})",
            "crimson",
        ))
    else:
        notes.append(("lambda = 0 (capacity not binding, idle capacity remains)", "dimgray"))
    notes.append((
        f"Idle capacity: {idle:,.0f} lots   |   Unmet demand: {total_unmet:,.0f} lots",
        "dimgray",
    ))

    if comparison is not None:
        gp = comparison["grid_best_profit"]
        mp = comparison["merit_order_profit"]
        pct = comparison["gap_pct"] * 100
        attrib = comparison["attributable_to_grid_resolution"]
        # 1行に収めると図の右端からはみ出すため2行に分ける。
        notes.append((
            f"Merit order (continuous): {mp/1e6:.2f}M JPY   |   "
            f"Grid-optimal (delta=0.05 grid maximum): {gp/1e6:.2f}M JPY",
            "#555555",
        ))
        notes.append((
            f"gap {pct:+.2f}%"
            + ("  (attributable to grid resolution)" if attrib else "  (structural gap)"),
            "#555555",
        ))

    # capacity = ... の凡例: 限界市場より右のブロックは必ず lambda 以下の高さに
    # なるため、能力線より右・lambda より上は構造的に空く。upper right のままでよい。
    ax.legend(fontsize=8, loc="upper right", framealpha=0.9)
    ax.set_xlabel("Cumulative allocated quantity (lots)")
    ax.set_ylabel("Unit margin (JPY/lot)")
    ax.set_title(title or f"Allocation Merit Order Curve  (capacity = {cap:,.0f} lots)")
    ax.set_xlim(left=0)

    # 注記は transAxes（軸フラクション）ではなく transFigure（図フラクション）で
    # 位置決めする。transAxes だと rect で軸の高さを変えるたびに「軸フラクション
    # 換算での絶対位置」が動いてしまい、xlabel との間隔が予測できなくなる
    # （transAxes 採用時に実際に発生した不具合）。tight_layout の rect を先に
    # 固定してから、xlabel より確実に下の figure-fraction 位置へ注記を積む。
    fig.tight_layout(rect=(0, 0.22, 1, 1))

    y = 0.175
    for text, color in notes:
        fig.text(0.06, y, text, transform=fig.transFigure, ha="left", va="top",
                 fontsize=8.5, color=color)
        y -= 0.037

    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def plot_allocation_merit_shift(
    mo_before: dict,
    mo_after: dict,
    out: str,
    *,
    labels: Tuple[str, str] = ("Before", "After"),
    title: Optional[str] = None,
) -> str:
    """FX等の変化で市場順位が入れ替わる様子を、2本の階段で重ねる（配分版）。"""
    fig, ax = plt.subplots(figsize=(9.5, 5.8))

    def _step_arrays(mo: dict) -> Tuple[np.ndarray, np.ndarray]:
        xs = [0.0]
        ys = []
        x = 0.0
        for b in mo["blocks"]:
            ys.append(b["margin"])
            x += b["width"]
            xs.append(x)
        if ys:
            ys.append(ys[-1])
        return np.array(xs), np.array(ys)

    x_before, y_before = _step_arrays(mo_before)
    x_after, y_after = _step_arrays(mo_after)

    ax.step(x_before, y_before, where="post", color="#888888", linestyle="--",
            linewidth=1.4, label=labels[0])
    ax.step(x_after, y_after, where="post", color="#C1432B", linestyle="-",
            linewidth=1.8, label=labels[1])

    cap_before = mo_before["cap"]
    cap_after = mo_after["cap"]
    if cap_before and cap_after and abs(cap_before - cap_after) < 1e-9:
        ax.axvline(cap_before, color="black", linestyle="--", linewidth=1.4,
                   label=f"capacity = {cap_before:,.0f} lots")
    else:
        if cap_before:
            ax.axvline(cap_before, color="#888888", linestyle="--", linewidth=1.2,
                       label=f"capacity ({labels[0]}) = {cap_before:,.0f}")
        if cap_after:
            ax.axvline(cap_after, color="#C1432B", linestyle="--", linewidth=1.2,
                       label=f"capacity ({labels[1]}) = {cap_after:,.0f}")

    lam_before, mkt_before = mo_before["lambda"], mo_before["marginal_market"]
    lam_after, mkt_after = mo_after["lambda"], mo_after["marginal_market"]
    legend_extra = []
    if mkt_before is not None:
        ax.axhline(lam_before, color="#888888", linestyle=":", linewidth=1.0)
        legend_extra.append(f"lambda_before = {lam_before:.1f}")
        if cap_before:
            ax.plot([cap_before], [lam_before], marker="o", markersize=6,
                    color="#888888", zorder=5)
    if mkt_after is not None:
        ax.axhline(lam_after, color="#C1432B", linestyle=":", linewidth=1.0)
        legend_extra.append(f"lambda_after = {lam_after:.1f}")
        if cap_after:
            ax.plot([cap_after], [lam_after], marker="o", markersize=6,
                    color="#C1432B", zorder=5)

    order_before = [b["market"] for b in mo_before["blocks"]]
    order_after = [b["market"] for b in mo_after["blocks"]]
    rank_before = {m: i + 1 for i, m in enumerate(order_before)}
    rank_after = {m: i + 1 for i, m in enumerate(order_after)}

    swapped = [m for m in rank_after
               if m in rank_before and rank_before[m] != rank_after[m]]
    notes = []
    if swapped:
        parts = [f"{m} (#{rank_before[m]}->#{rank_after[m]})" for m in swapped]
        notes.append("Rank changes: " + ", ".join(parts))
    if mo_before["excluded"] or mo_after["excluded"]:
        notes.append(
            f"Excluded ({labels[0]}): {', '.join(mo_before['excluded']) or 'none'}   "
            f"Excluded ({labels[1]}): {', '.join(mo_after['excluded']) or 'none'}"
        )
    if notes:
        ax.text(0.02, -0.14, "\n".join(notes), transform=ax.transAxes,
                ha="left", va="top", fontsize=8)

    handles, labels_ = ax.get_legend_handles_labels()
    for txt in legend_extra:
        handles.append(plt.Line2D([], [], color="none"))
        labels_.append(txt)
    # G4: 単位マージン降順に積む以上、左上には必ず最も高いブロックが来る（G3と同じ理由）。
    # lambda の水平線より下は全面的に空くため lower left は構造的に安全。
    ax.legend(handles, labels_, fontsize=8, loc="lower left", framealpha=0.9)

    ax.set_xlabel("Cumulative allocated quantity (lots)")
    ax.set_ylabel("Unit margin (JPY/lot)")
    ax.set_title(title or "Allocation Merit Order Shift — Before vs After")
    ax.set_xlim(left=0)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# ② レジーム地図（配分版）
# ---------------------------------------------------------------------------

_AXIS_LABELS = {
    "fx_usd": "USD/JPY",
    "material_usd": "Material price (USD/lot)",
}


def _axis_label(axis_name: str) -> str:
    if axis_name in _AXIS_LABELS:
        return _AXIS_LABELS[axis_name]
    if axis_name.startswith("tariff_rate:"):
        market = axis_name.split(":", 1)[1]
        return f"Tariff rate ({market})"
    return axis_name


_REGIME_CMAP_COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52",
    "#8172B2", "#937860", "#DA8BC3", "#8C8C8C",
]


def plot_regime_map(
    grid: dict,
    out: str,
    *,
    mark_points: Optional[List[Tuple[float, float, str]]] = None,
    title: Optional[str] = None,
) -> str:
    """外部環境パラメータ平面のレジーム地図を描画し、保存先パスを返す。

    Args:
        grid: scan_regime_grid() の戻り値
        out: 出力 PNG パス
        mark_points: [(x, y, label), ...] 図中にマークする点（例: 基準点・ショック点）
        title: 図タイトル
    """
    x_values = grid["x_values"]
    y_values = grid["y_values"]
    regime_ids = np.array(grid["regime_ids"], dtype=float)
    labels = grid["regime_labels"]

    n_labels = max(len(labels), 1)
    colors = [_REGIME_CMAP_COLORS[i % len(_REGIME_CMAP_COLORS)] for i in range(n_labels)]
    cmap = ListedColormap(colors)

    fig, ax = plt.subplots(figsize=(8.5, 6.5))

    extent = (x_values[0], x_values[-1], y_values[0], y_values[-1])
    im = ax.imshow(regime_ids, origin="lower", aspect="auto", extent=extent,
                   cmap=cmap, vmin=-0.5, vmax=n_labels - 0.5, zorder=1)

    # 境界線（決定反転面）
    if len(x_values) > 1 and len(y_values) > 1:
        levels = [i + 0.5 for i in range(n_labels - 1)]
        if levels:
            ax.contour(x_values, y_values, regime_ids, levels=levels,
                      colors="black", linewidths=0.9, alpha=0.8, zorder=2)

    # 負マージン領域: 斜線ハッチ
    neg_mask = grid["negative_margin_mask"]
    any_neg = np.array([[1.0 if cell else 0.0 for cell in row] for row in neg_mask])
    if any_neg.max() > 0:
        ax.contourf(x_values, y_values, any_neg, levels=[0.5, 1.5],
                   colors="none", hatches=["////"], zorder=3)
        ax.contour(x_values, y_values, any_neg, levels=[0.5],
                  colors="#B5504A", linewidths=1.2, linestyles="-", zorder=3)

    if mark_points:
        for mx, my, mlabel in mark_points:
            ax.plot(mx, my, marker="*" if mlabel.lower() == "shock" else "o",
                   markersize=13, mfc="white", mec="black", mew=1.4, zorder=6)
            ax.annotate(mlabel, (mx, my), textcoords="offset points", xytext=(8, 6),
                       fontsize=8, fontweight="bold", zorder=6)

    ax.set_xlabel(_axis_label(grid["axis_x"]))
    ax.set_ylabel(_axis_label(grid["axis_y"]))
    ax.set_xlim(x_values[0], x_values[-1])
    ax.set_ylim(y_values[0], y_values[-1])
    ax.set_title(title or f"Regime Map — {_axis_label(grid['axis_x'])} x {_axis_label(grid['axis_y'])}")

    handles = [plt.Rectangle((0, 0), 1, 1, color=colors[i]) for i in range(len(labels))]
    if any_neg.max() > 0:
        handles.append(plt.Rectangle((0, 0), 1, 1, facecolor="none", edgecolor="#B5504A",
                                     hatch="////", label="negative margin present"))
        legend_labels = list(labels) + ["negative margin present"]
    else:
        legend_labels = list(labels)
    ax.legend(handles, legend_labels, fontsize=7.5, loc="upper left",
             bbox_to_anchor=(1.02, 1.0), framealpha=0.9)

    fig.tight_layout(rect=(0, 0, 0.80, 1))
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_OUTPUT_FILES = {
    "merit_order": "alloc_merit_order.png",
    "merit_shift": "alloc_merit_shift.png",
    "regime_map": "alloc_regime_map.png",
    "regime_map_tariff": "alloc_regime_map_tariff.png",
}


def _build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Allocation merit-order curve + regime map visualization (Phase 4)."
    )
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--cap-wk", type=float, default=800.0)
    ap.add_argument("--scenario", default="s1_base")
    ap.add_argument("--out", default="output/allocation")
    ap.add_argument("--demo", action="store_true",
                    help="Force cap_wk=800 / scenario=s1_base for reproducible demo output.")
    return ap


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    return _build_arg_parser().parse_args(argv)


def run(args: argparse.Namespace) -> List[str]:
    """引数に従って4枚のPNGを生成し、生成したパスのリストを返す。"""
    os.makedirs(args.out, exist_ok=True)

    cap_wk = 800.0 if args.demo else args.cap_wk
    scenario_id = "s1_base" if args.demo else args.scenario

    base_blocks, tp = derive_cost_blocks(args.model_dir)
    scens = {s["id"]: s for s in load_scenarios(args.model_dir)}
    if scenario_id not in scens:
        raise ValueError(
            f"scenario {scenario_id!r} not found in {args.model_dir}/ga_scenario_master.csv "
            f"(available: {sorted(scens.keys())})"
        )
    s = scens[scenario_id]
    blocks = _blocks_for(base_blocks, s["tariff"])
    sc = Scenario(fx_usd=s["fx_usd"], material_usd=s["material_usd"])

    made: List[str] = []

    # --- ① Merit order curve ---
    mo = build_allocation_merit_order(blocks, sc, cap_wk, transfer_price_usd=tp)
    surface = scan_surface(blocks, tp, sc, cap_wk)
    cmp = compare_with_grid(mo, surface)
    made.append(plot_allocation_merit_order(
        mo, os.path.join(args.out, _OUTPUT_FILES["merit_order"]), comparison=cmp
    ))

    # --- ① Before/After (switching_points()117円/119円の前後、決定的) ---
    mo_before = build_allocation_merit_order(
        blocks, Scenario(fx_usd=115.0, material_usd=sc.material_usd), cap_wk, transfer_price_usd=tp
    )
    mo_after = build_allocation_merit_order(
        blocks, Scenario(fx_usd=125.0, material_usd=sc.material_usd), cap_wk, transfer_price_usd=tp
    )
    made.append(plot_allocation_merit_shift(
        mo_before, mo_after, os.path.join(args.out, _OUTPUT_FILES["merit_shift"]),
        labels=("FX=115", "FX=125"),
    ))

    # --- ② Regime map: fx_usd x material_usd（既定軸、R3） ---
    fx_values = list(range(100, 221, 2))
    mat_values = [4.0 + 0.5 * i for i in range(13)]  # 4.0..10.0
    grid_fm = scan_regime_grid(base_blocks, "fx_usd", fx_values, "material_usd", mat_values,
                               transfer_price_usd=tp)
    made.append(plot_regime_map(
        grid_fm, os.path.join(args.out, _OUTPUT_FILES["regime_map"]),
        mark_points=[(150.0, 6.0, "base"), (200.0, 8.0, "shock")],
    ))

    # --- ② Regime map: fx_usd x tariff_rate:US ---
    tariff_values = [round(0.02 * i, 2) for i in range(16)]  # 0.00..0.30
    grid_ft = scan_regime_grid(base_blocks, "fx_usd", fx_values, "tariff_rate:US", tariff_values,
                               transfer_price_usd=tp)
    made.append(plot_regime_map(
        grid_ft, os.path.join(args.out, _OUTPUT_FILES["regime_map_tariff"]),
        mark_points=[(150.0, 0.125, "base")],
    ))

    return made


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    made = run(args)
    for m in made:
        print(f"[plot] wrote {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
