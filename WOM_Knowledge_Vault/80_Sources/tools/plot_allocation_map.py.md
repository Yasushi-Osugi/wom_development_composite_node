---
tags: [wom, code]
---
# tools/plot_allocation_map.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tools/plot_allocation_map.py) · [原文テキスト](../../90_Raw/tools/plot_allocation_map.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## モジュール説明（docstring原文）

```text
tools/plot_allocation_map.py — 配分地形図（静止画・Phase 2）
===========================================================
`ask_global_allocation` エンジンの 231 点評価から、経営判断用の静止画を生成する。

  左: 配分地形図（直角三角形・X=x_US, Y=x_EU, x_JP=残余）
       利益等高線 + 尾根線（需要天井）+ 最適点★ + 基準点● + FXB=1.0 線
  右: 層別断面（円安×原油の複合ショックの分解。交互作用をハッチで明示。§3.2）
  タイル: 全シナリオの等高線を共通カラースケールで並べ、最適点を赤点で（§3.3）

設計正典：docs/design/ask_global_allocation_spec.md §3 / Request Letter §3
参照：docs/images/terrain_prototype.png / terrain_layers.png

使い方（リポジトリ直下）:
  python -m tools.plot_allocation_map --model-dir data/sample/soysauce-jpy-2027-alloc --tile --out out/tile.png
  python -m tools.plot_allocation_map --model-dir <dir> --scenario s4_compound --point 0.45,0.55 --out out/s4.png
  python -m tools.plot_allocation_map --model-dir <dir> --layers --out out/layers.png
  （引数なしの --out 省略時は out/ に tile.png / layers.png を生成）
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_engine` | 48 | docstringなし（下のコード参照） |
| FunctionDef | `_surface` | 54 | docstringなし（下のコード参照） |
| FunctionDef | `_arrays` | 60 | docstringなし（下のコード参照） |
| FunctionDef | `_require_three_markets` | 68 | 三角図は単体の2次元射影なので N=3 専用。N≥4 は明示エラーで止める（Phase 6-2 V6）。 |
| FunctionDef | `_draw_terrain` | 82 | docstringなし（下のコード参照） |
| FunctionDef | `plot_single` | 119 | docstringなし（下のコード参照） |
| FunctionDef | `plot_terrain_only` | 145 | 1 シナリオ＝大きな直角三角形の地形図 1 枚（層別断面なし・訴求用）。 |
| FunctionDef | `plot_each_scenario` | 163 | 全定常シナリオの単独地形図を out_dir/terrain_<id>.png に 1 枚ずつ書き出す。 |
| FunctionDef | `plot_tile` | 174 | docstringなし（下のコード参照） |
| FunctionDef | `_draw_layers_bar` | 203 | docstringなし（下のコード参照） |
| FunctionDef | `plot_layers` | 226 | docstringなし（下のコード参照） |
| FunctionDef | `_legend_terrain` | 241 | docstringなし（下のコード参照） |
| FunctionDef | `bx_s` | 253 | docstringなし（下のコード参照） |
| FunctionDef | `main` | 257 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/docs/design/ask_global_allocation_spec.md|docs/design/ask_global_allocation_spec.md]]
- [[80_Sources/wom/allocation/cost_block.py|wom/allocation/cost_block.py]]
- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]
- [[80_Sources/wom/allocation/grid.py|wom/allocation/grid.py]]
- [[80_Sources/wom/allocation/analytics.py|wom/allocation/analytics.py]]
- [[80_Sources/tools/run_allocation_map.py|tools/run_allocation_map.py]]

## 全文（コメント・原文を省略せず収録）

````python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/plot_allocation_map.py — 配分地形図（静止画・Phase 2）
===========================================================
`ask_global_allocation` エンジンの 231 点評価から、経営判断用の静止画を生成する。

  左: 配分地形図（直角三角形・X=x_US, Y=x_EU, x_JP=残余）
       利益等高線 + 尾根線（需要天井）+ 最適点★ + 基準点● + FXB=1.0 線
  右: 層別断面（円安×原油の複合ショックの分解。交互作用をハッチで明示。§3.2）
  タイル: 全シナリオの等高線を共通カラースケールで並べ、最適点を赤点で（§3.3）

設計正典：docs/design/ask_global_allocation_spec.md §3 / Request Letter §3
参照：docs/images/terrain_prototype.png / terrain_layers.png

使い方（リポジトリ直下）:
  python -m tools.plot_allocation_map --model-dir data/sample/soysauce-jpy-2027-alloc --tile --out out/tile.png
  python -m tools.plot_allocation_map --model-dir <dir> --scenario s4_compound --point 0.45,0.55 --out out/s4.png
  python -m tools.plot_allocation_map --model-dir <dir> --layers --out out/layers.png
  （引数なしの --out 省略時は out/ に tile.png / layers.png を生成）
"""
from __future__ import annotations

import argparse
import os
from dataclasses import replace
from typing import Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Patch
import numpy as np

from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.transmission import Scenario
from wom.allocation.grid import (
    markets_of, scan_surface, best_point, chosen_point, demand_ceilings, evaluate_point,
)
from wom.allocation.analytics import interaction
from tools.run_allocation_map import load_scenarios, _blocks_for

BASE_ALLOC = (0.30, 0.35, 0.35)


# ---------------------------------------------------------------------------
def _engine(model_dir: str, cap_wk: float):
    base_blocks, tp = derive_cost_blocks(model_dir)
    scens = [s for s in load_scenarios(model_dir) if not s["time_series"]]
    return base_blocks, tp, scens


def _surface(base_blocks, tp, s, cap_wk):
    blocks = _blocks_for(base_blocks, s["tariff"])
    S = Scenario(fx_usd=s["fx_usd"], material_usd=s["material_usd"])
    return scan_surface(blocks, tp, S, cap_wk), blocks


def _arrays(surf) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    xus = np.array([r["x"][1] for r in surf])
    xeu = np.array([r["x"][2] for r in surf])
    z = np.array([r["profit"] / 1e6 for r in surf])
    fxb = np.array([min(r["FXB"], 5.0) if r["FXB"] != float("inf") else 5.0 for r in surf])
    return xus, xeu, z, fxb


def _require_three_markets(blocks) -> None:
    """三角図は単体の2次元射影なので N=3 専用。N≥4 は明示エラーで止める（Phase 6-2 V6）。

    「黙って上位3市場だけ描く」という挙動は禁止する——利用者が3市場の図を
    全体だと誤解するリスクがあるため（Request Letter §9 R4 で大杉さん確認済み）。
    """
    markets = markets_of(blocks)
    if len(markets) != 3:
        raise ValueError(
            f"Triangle plot supports exactly 3 markets, got {len(markets)}: {markets}. "
            f"For N>=4, use the hierarchical drill-down (Phase 6-3)."
        )


def _draw_terrain(ax, surf, blocks, cap_wk, title, norm=None, cmap="RdYlGn",
                  show_fxb=True, mark_point=None):
    _require_three_markets(blocks)
    xus, xeu, z, fxb = _arrays(surf)
    if norm is None:
        norm = Normalize(vmin=z.min(), vmax=z.max())
    tcf = ax.tricontourf(xus, xeu, z, levels=14, cmap=cmap, norm=norm)
    ax.tricontour(xus, xeu, z, levels=14, colors="k", linewidths=0.3, alpha=0.35)

    # 需要天井（尾根線）: x_US=ceil_US, x_EU=ceil_EU, x_JP=ceil_JP → x_US+x_EU=1-ceil_JP
    c = demand_ceilings(blocks, cap_wk)
    ax.axvline(c["US"], color="#C1432B", ls="--", lw=1.2, alpha=0.8)
    ax.axhline(c["EU"], color="#7B3FB5", ls="--", lw=1.2, alpha=0.8)
    lim = 1.0 - c["JP"]
    ax.plot([0, lim], [lim, 0], color="#2E6DB5", ls="--", lw=1.2, alpha=0.8)  # x_US+x_EU=1-ceil_JP

    # FXB=1.0（為替中立線）
    if show_fxb and fxb.min() < 1.0 < fxb.max():
        ax.tricontour(xus, xeu, fxb, levels=[1.0], colors="k", linestyles=":", linewidths=1.6)

    # 最適点★・基準点●
    best, _plateau = best_point(surf)
    bx = chosen_point(surf)["x"]   # 格子の真の最良点（Phase 6-5・E1）
    ax.plot(bx[1], bx[2], marker="*", ms=17, mfc="#111", mec="w", mew=0.8, zorder=6)
    ax.plot(BASE_ALLOC[1], BASE_ALLOC[2], marker="o", ms=8, mfc="none", mec="#111", mew=1.6, zorder=6)
    if mark_point is not None:
        ax.plot(mark_point[0], mark_point[1], marker="D", ms=9, mfc="#E8A33D", mec="#111", mew=1.0, zorder=7)

    # 三角形境界（斜辺 = 輸出100%）
    ax.plot([0, 1], [1, 0], color="#555", lw=1.0)
    ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("x_US  (US allocation)"); ax.set_ylabel("x_EU  (EU allocation)")
    ax.set_title(title, fontsize=10)
    ax.set_aspect("equal")
    return tcf, best, bx


def plot_single(model_dir, scenario_id, cap_wk, out, point=None):
    base_blocks, tp, scens = _engine(model_dir, cap_wk)
    s = next(x for x in scens if x["id"] == scenario_id)
    surf, blocks = _surface(base_blocks, tp, s, cap_wk)
    best0, _plateau0 = best_point(surf)
    bx0 = chosen_point(surf)["x"]   # 格子の真の最良点（Phase 6-5・E1）
    mname = os.path.basename(model_dir.rstrip("/\\"))

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.4), gridspec_kw={"width_ratios": [1.05, 1]})
    tcf, best, bx = _draw_terrain(
        axL, surf, blocks, cap_wk,
        f"Profit terrain — {scenario_id}  (JPY M)\noptimum * ({bx_s(bx0)})  max {best0/1e6:.1f}M",
        mark_point=point)
    fig.colorbar(tcf, ax=axL, fraction=0.046, pad=0.04, label="Profit (JPY M)")
    _legend_terrain(axL)

    # 右: 層別断面（複合ショックの分解）。point 指定があればその点、無ければ最適点。
    px = (1 - point[0] - point[1], point[0], point[1]) if point else bx
    _draw_layers_bar(axR, base_blocks, tp, cap_wk,
                     [(f"selected ({bx_s(px)})", px)])
    fig.suptitle(f"{mname} | cap {cap_wk}/wk", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out, dpi=140); plt.close(fig)
    return out


def plot_terrain_only(model_dir, scenario_id, cap_wk, out, point=None):
    """1 シナリオ＝大きな直角三角形の地形図 1 枚（層別断面なし・訴求用）。"""
    base_blocks, tp, scens = _engine(model_dir, cap_wk)
    s = next(x for x in scens if x["id"] == scenario_id)
    surf, blocks = _surface(base_blocks, tp, s, cap_wk)
    best, _plateau = best_point(surf)
    bx = chosen_point(surf)["x"]   # 格子の真の最良点（Phase 6-5・E1）
    fig, ax = plt.subplots(figsize=(6.6, 6.2))
    title = (f"{scenario_id}   cap {cap_wk:.0f}/wk   USD {s['fx_usd']:.0f}   material ${s['material_usd']:.1f}\n"
             f"optimum * ({bx_s(bx)})   max = {best/1e6:.0f}M JPY")
    tcf, _b, _x = _draw_terrain(ax, surf, blocks, cap_wk, title, mark_point=point)
    fig.colorbar(tcf, ax=ax, fraction=0.046, pad=0.04, label="Profit (JPY M)")
    _legend_terrain(ax)
    fig.tight_layout()
    fig.savefig(out, dpi=150); plt.close(fig)
    return out


def plot_each_scenario(model_dir, cap_wk, out_dir):
    """全定常シナリオの単独地形図を out_dir/terrain_<id>.png に 1 枚ずつ書き出す。"""
    os.makedirs(out_dir, exist_ok=True)
    _bb, _tp, scens = _engine(model_dir, cap_wk)
    made = []
    for s in scens:
        p = os.path.join(out_dir, f"terrain_{s['id']}.png")
        made.append(plot_terrain_only(model_dir, s["id"], cap_wk, p))
    return made


def plot_tile(model_dir, cap_wk, out):
    mname = os.path.basename(model_dir.rstrip("/\\"))
    base_blocks, tp, scens = _engine(model_dir, cap_wk)
    surfaces = [(s["id"], *_surface(base_blocks, tp, s, cap_wk)) for s in scens]
    zmin = min(min(r["profit"] for r in surf) for _, surf, _ in surfaces) / 1e6
    zmax = max(max(r["profit"] for r in surf) for _, surf, _ in surfaces) / 1e6
    norm = Normalize(vmin=zmin, vmax=zmax)
    n = len(surfaces)
    cols = 4; rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4.0 * cols, 4.0 * rows))
    axes = np.array(axes).reshape(-1)
    tcf = None
    for ax, (sid, surf, blocks) in zip(axes, surfaces):
        b0, _pl0 = best_point(surf)
        bx0 = chosen_point(surf)["x"]   # 格子の真の最良点（Phase 6-5・E1）
        tcf, _b, _x = _draw_terrain(ax, surf, blocks, cap_wk,
                                    f"{sid}\nmax {b0/1e6:.0f}M  opt {bx_s(bx0)}",
                                    norm=norm, show_fxb=True)
    for ax in axes[n:]:
        ax.axis("off")
    fig.suptitle(f"Allocation profit terrain by scenario (common scale) — "
                 f"{mname} cap {cap_wk}/wk", fontsize=12)
    fig.subplots_adjust(right=0.9, top=0.9, hspace=0.55, wspace=0.32)
    cax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
    fig.colorbar(tcf, cax=cax, label="Profit (JPY M)")
    fig.savefig(out, dpi=130, bbox_inches="tight"); plt.close(fig)
    return out


def _draw_layers_bar(ax, base_blocks, tp, cap_wk, points):
    labels = ["FX (USD150->200)", "Material ($6->$8)", "Interaction"]
    colors = ["#3E6DB5", "#E07B54", "#9AA0A6"]
    # 単一点なら横棒、複数点は簡易グループ（ここでは単一点想定の呼び出し）
    lab, x = points[0]
    r = interaction(x, base_blocks, tp, cap_wk)
    vals = [r["fx_only"] / 1e6, r["mat_only"] / 1e6, r["interaction"] / 1e6]
    ypos = [2, 1, 0]
    bars = ax.barh(ypos, vals, color=colors, edgecolor="k", linewidth=0.6)
    bars[2].set_hatch("////")               # 交互作用はハッチ（層ではない）
    for yp, v in zip(ypos, vals):
        ax.text(v + (1 if v >= 0 else -1), yp, f"{v:+.1f}M",
                va="center", ha="left" if v >= 0 else "right", fontsize=9)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_yticks(ypos); ax.set_yticklabels(labels)
    ax.set_xlabel("delta profit vs base scenario (JPY M)")
    warn = "" if r["layer_decomposition_valid"] else "   [!] >5%: layers NOT additive"
    ax.set_title(f"{lab}\ntotal={r['total']/1e6:+.1f}M   interaction={r['ratio']*100:+.0f}%{warn}",
                 fontsize=9)
    pad = max(abs(min(vals)), abs(max(vals))) * 0.25 + 5
    ax.set_xlim(min(vals) - pad, max(vals) + pad)


def plot_layers(model_dir, cap_wk, out):
    base_blocks, tp, scens = _engine(model_dir, cap_wk)
    pts = [("base (0.30/0.35/0.35)", (0.30, 0.35, 0.35)),
           ("optimum (0.10/0.45/0.45)", (0.10, 0.45, 0.45)),
           ("domestic-heavy (0.60/0.20/0.20)", (0.60, 0.20, 0.20))]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, p in zip(axes, pts):
        _draw_layers_bar(ax, base_blocks, tp, cap_wk, [p])
    fig.suptitle("Layer decomposition (compound shock: weak yen × oil) — "
                 "interaction is a lead actor, not a residual", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(out, dpi=130); plt.close(fig)
    return out


def _legend_terrain(ax):
    handles = [
        plt.Line2D([], [], color="#C1432B", ls="--", label="US demand ceiling (ridge)"),
        plt.Line2D([], [], color="#7B3FB5", ls="--", label="EU demand ceiling"),
        plt.Line2D([], [], color="#2E6DB5", ls="--", label="JP demand ceiling"),
        plt.Line2D([], [], color="k", ls=":", lw=1.6, label="FXB = 1.0 (FX neutral)"),
        plt.Line2D([], [], color="none", marker="*", mfc="#111", mec="w", ms=12, label="optimum"),
        plt.Line2D([], [], color="none", marker="o", mfc="none", mec="#111", ms=8, label="base alloc"),
    ]
    ax.legend(handles=handles, fontsize=7.5, loc="upper right", framealpha=0.9)


def bx_s(x) -> str:
    return f"{x[0]:.2f}/{x[1]:.2f}/{x[2]:.2f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ask_global_allocation static plots (Phase 2).")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--cap-wk", type=float, default=800.0)
    ap.add_argument("--scenario", default=None)
    ap.add_argument("--tile", action="store_true")
    ap.add_argument("--layers", action="store_true")
    ap.add_argument("--each", action="store_true", help="全シナリオの単独地形図を1枚ずつ（--out はディレクトリ）")
    ap.add_argument("--terrain-only", action="store_true", help="--scenario で地形図のみ（層別断面なし）")
    ap.add_argument("--point", default=None, help="x_us,x_eu（断面/選択点を描く点）")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    pt = None
    if a.point:
        xs = [float(v) for v in a.point.split(",")]
        pt = (xs[0], xs[1])

    made = []
    if a.each:
        made.extend(plot_each_scenario(a.model_dir, a.cap_wk, a.out or "out/terrains"))
    elif a.scenario:
        out = a.out or f"out/terrain_{a.scenario}.png"
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        if a.terrain_only:
            made.append(plot_terrain_only(a.model_dir, a.scenario, a.cap_wk, out, point=pt))
        else:
            made.append(plot_single(a.model_dir, a.scenario, a.cap_wk, out, point=pt))
    elif a.tile:
        out = a.out or "out/tile.png"
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        made.append(plot_tile(a.model_dir, a.cap_wk, out))
    elif a.layers:
        out = a.out or "out/layers.png"
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        made.append(plot_layers(a.model_dir, a.cap_wk, out))
    else:
        # 既定：タイル＋層別断面＋各シナリオの単独地形図（訴求用の必須出力を含む）
        os.makedirs("out", exist_ok=True)
        made.append(plot_tile(a.model_dir, a.cap_wk, "out/tile.png"))
        made.append(plot_layers(a.model_dir, a.cap_wk, "out/layers.png"))
        made.extend(plot_each_scenario(a.model_dir, a.cap_wk, "out/terrains"))
    for m in made:
        print(f"[plot] wrote {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

````
