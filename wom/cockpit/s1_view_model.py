# -*- coding: utf-8 -*-
"""
wom/cockpit/s1_view_model.py — S1 Allocate 画面が出す値を作る純関数（Phase 8-1・Phase 8-3a で wom/cockpit/ へ移設）
================================================================================
**tkinter に依存しない。** `build_s1_view()` が画面に出す値をすべて作り、
`wom/cockpit/s1_allocate.py` はそれを並べるだけにする（C9：計算と描画を分ける）。
tkinter は自動テストが難しいので、テストできる部分（本ファイル）とできない部分
（パネル）を先に切り分けるのが本 Phase の価値の半分である。

正典: requests/Phase8-1_RequestLetter_to_CodeKun.md V1
      requests/Phase8_DesignMD_CockpitGUI.md rev.3 §4 S1
      requests/Phase8-3a_RequestLetter_CockpitFrame_to_CodeKun.md（移設・F1）

【GUI 内の matplotlib は日本語可】（Phase 8-1・C4）: `wom/cockpit/__init__.py` が
`matplotlib.rcParams["font.family"] = ["Yu Gothic", "DejaVu Sans"]` を設定済み
（Phase 8-3a 追補で修正——移設直後は `wom/gui/app.py` の設定を当てにしたままで、
コックピットは `app.py` を import しないため日本語が豆腐化する欠陥だった）。
「図中テキストは全て英語」という制約は `tools/` の PNG 出力（`tools/plot_*.py`
はフォント未設定＝豆腐化する）に対するものであり、**GUI には及ばない**。本ファイル
が作る `lines_ja` 等の日本語ラベルはそのまま GUI の Label / 軸ラベルに使ってよい。
次にこのファイルを英語化してしまわないよう、ここに明記しておく。
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

from wom.allocation.analytics import switching_points
from wom.allocation.cost_block import derive_cost_blocks
from wom.allocation.grid import WEEKS, best_point, chosen_point, markets_of, scan_surface
from wom.allocation.hierarchical_simplex import build_hierarchy, scan_hierarchical
from wom.allocation.merit_order import (
    build_allocation_merit_order, compare_with_grid, true_continuous_optimum,
)
from wom.allocation.transmission import CostBlock, Scenario, unit_pnl_at_quantity
from wom.cockpit.plateau_band import default_band_yen, plateau_by_band

_AXIS_LABEL_JA = {"fx_usd": "USD/JPY", "material_usd": "原料価格"}

_UNALLOCATED_EPS = 1e-6   # cap_lots がこれ未満なら「配分ゼロ」とみなす（C2）


def format_market_name(name: str) -> str:
    """市場名の表示用整形（Phase 8-2・C3）。'Retail_' 前置きを落とす。

    **結論行・子ノードパネルの2箇所で必ずこの関数を使うこと**——別々に整形すると
    A5/A8（region の上書き／価格の最後勝ち）と同じ「フィルタを2箇所に置く」家族の
    欠陥になる（Phase 8-2 Request Letter §C3）。
    """
    prefix = "Retail_"
    return name[len(prefix):] if name.startswith(prefix) else name


# ---------------------------------------------------------------------------
# シナリオ解決（ga_scenario_master.csv → tariff 上書き + Scenario）
# ---------------------------------------------------------------------------
#
# tools/run_allocation_map.py の load_scenarios() は fx_usd の抽出に
# `market == "US"`（3市場固定の決め打ち）を使っており、oil-global-2027 のように
# market_group が leaf_out ノード名（"Retail_US_TX" 等）になる N 市場モデルでは
# 一致しない。A系統ファイルは「無変更」方針（Phase 8-1 対象ファイル表）のため、
# あちらを直すのではなく、ここに `currency == "USD"` を基準にした N 市場対応版を
# 独立実装する（tariff 上書きの適用自体は markets_of(blocks) を見る既存の
# _blocks_for() をそのまま再利用——そちらは元から N 市場対応）。
def _load_scenario_row(model_dir: str, scenario_id: str) -> dict:
    import csv

    path = os.path.join(model_dir, "ga_scenario_master.csv")
    with open(path, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["scenario_id"] == scenario_id]
    if not rows:
        raise ValueError(
            f"build_s1_view: scenario {scenario_id!r} not found in "
            f"{path} (ga_scenario_master.csv)"
        )
    usd_rows = [r for r in rows if r["currency"] == "USD"]
    if not usd_rows:
        raise ValueError(
            f"build_s1_view: scenario {scenario_id!r} has no currency=='USD' row "
            f"in ga_scenario_master.csv to determine fx_usd"
        )
    fx_usd = float(usd_rows[0]["fx_spot_jpy"])
    material = float(rows[0]["material_price_usd"])
    q0 = rows[0]["quarter"]
    tariff = {r["market"]: float(r["tariff_rate"]) for r in rows if r["quarter"] == q0}
    tariff_preferential: Dict[str, float] = {}
    preferential_threshold: Dict[str, float] = {}
    for r in rows:
        if r["quarter"] != q0:
            continue
        rate_str = (r.get("tariff_rate_preferential") or "").strip()
        thr_str = (r.get("preferential_threshold_lot") or "").strip()
        if rate_str and thr_str:
            tariff_preferential[r["market"]] = float(rate_str)
            preferential_threshold[r["market"]] = float(thr_str)
    return {"fx_usd": fx_usd, "material_usd": material, "tariff": tariff,
           "tariff_preferential": tariff_preferential,
           "preferential_threshold": preferential_threshold}


def _scenario_blocks(model_dir: str, scenario_id: str, uom: Optional[str]):
    from tools.run_allocation_map import _blocks_for  # 未改変のまま再利用（N市場対応済み）

    base_blocks, tp = derive_cost_blocks(model_dir, uom=uom)
    s = _load_scenario_row(model_dir, scenario_id)
    blocks = _blocks_for(base_blocks, s["tariff"],
                         s["tariff_preferential"], s["preferential_threshold"])
    sc = Scenario(fx_usd=s["fx_usd"], material_usd=s["material_usd"])
    return blocks, tp, sc


def compute_reversal(blocks, tp: float, sc: Scenario) -> dict:
    """現在のシナリオ fx から最も近い市場順位の反転点を返す（Phase 7a・A3.1 と同じ式）。"""
    sw = switching_points(blocks, tp, fx_lo=100, fx_hi=220, mat=sc.material_usd)
    current = sc.fx_usd
    candidates = []
    below = [p for p in sw if p["fx"] < current]
    above = [p for p in sw if p["fx"] > current]
    if below:
        p = max(below, key=lambda p: p["fx"])
        candidates.append((current - p["fx"], p, "below"))
    if above:
        p = min(above, key=lambda p: p["fx"])
        candidates.append((p["fx"] - current, p, "above"))
    if not candidates:
        return {}
    _dist, boundary_pt, direction = min(candidates, key=lambda c: c[0])
    return {
        "axis": "fx_usd", "current": current, "boundary": float(boundary_pt["fx"]),
        "direction": direction, "flips_to": ">".join(boundary_pt["order"]),
    }


# ---------------------------------------------------------------------------
# 階層ドリルダウン: node_path を歩く（surfaces は再計算しない・V1.3）
# ---------------------------------------------------------------------------

def _auto_skip_single_child(node: dict, cap_lots: float) -> Tuple[dict, float]:
    """子1のノードは素通りする（V1.2）。子1のノードには全量がそのまま渡る。"""
    while len(node["children"]) == 1:
        node = node["children"][0]
    return node, cap_lots


def _walk_hierarchy(tree: dict, surfaces: Dict[str, list], node_path: Sequence[str],
                    cap_wk: float, weeks: int) -> Tuple[dict, float, List[dict]]:
    """`tree` を `node_path` に沿って降り、(現在ノード, そのノードの能力, 経路上のノード列)。

    子ノードの能力は「親ノードの surfaces から chosen_point() で得た配分」——
    scan_hierarchical() が既に計算済みの `surfaces` を読むだけで、新たな
    `scan_surface()` は一切呼ばない（V1.3）。
    """
    cur, cap_lots = _auto_skip_single_child(tree, cap_wk * weeks)
    path_nodes = [cur]
    for name in node_path:
        if cur["name"] not in surfaces:
            raise ValueError(
                f"build_s1_view: node {cur['name']!r} has no children to descend "
                f"into (requested {name!r})"
            )
        chosen = chosen_point(surfaces[cur["name"]])   # 格子の真の最良点（Phase 6-5・E1）
        nxt = next((c for c in cur["children"] if c["name"] == name), None)
        if nxt is None:
            raise ValueError(
                f"build_s1_view: unknown child {name!r} under {cur['name']!r} "
                f"(children: {[c['name'] for c in cur['children']]})"
            )
        cap_lots = chosen["q"].get(name, 0.0)
        cur, cap_lots = _auto_skip_single_child(nxt, cap_lots)
        path_nodes.append(cur)
    return cur, cap_lots, path_nodes


def _plot_kind(n_children: int) -> str:
    if n_children == 3:
        return "triangle"
    if n_children == 2:
        return "line"
    return "none"          # 子0（葉）・子1（build_hierarchy() は通常作らない）


def _is_unallocated(cap_lots: float) -> bool:
    """cap_lots がゼロ（または浮動小数の誤差程度）か（Phase 8-2・C2）。

    判定はここに一本化する——パネル側で `cap_lots == 0` を書かないこと
    （計算と描画の分離、Phase 8-1 の設計の柱）。
    """
    return abs(cap_lots) < _UNALLOCATED_EPS


def _unallocated_message_ja(parent_name: Optional[str], current_name: str) -> str:
    """C2: 配分ゼロの枝に出す説明（child_x・図・台地サイズの代わりに1行）。

    **ゼロなのは上位ノード自身ではなく、上位ノードから見た「このノード」への
    配分**——Phase 8-2 検証で名指しが1つずれていると指摘された（旧実装は
    「上位ノードでALLの比率が0のため」のように書いており、ALL自身の比率が
    0であるかのように読めたが、実際に0なのは USD 側。「上位ノード {parent} に
    おいて {current} の配分が 0 のため」の形にし、current を明示する）。
    英数字（ノード名・数値）の前後には半角スペースを入れる（C6 と同じ理由）。
    """
    if parent_name:
        return (
            f"この枝には配分されていません（0 lot）。上位ノード {parent_name} において "
            f"{current_name} の配分が 0 のため、ここから下の比率に意味はありません。"
        )
    return "この枝には配分されていません（0 lot）。"


def _leaf_economics(name: str, cb: CostBlock, sc: Scenario, tp: float, cap_lots: float,
                    ranked_markets: Sequence[str], marginal_market: Optional[str]) -> dict:
    """葉ノード（末端市場）の単位経済（Phase 8-2・C4）。

    **マージン・売上は JPY 建て、`price_local` は現地通貨。混ぜないこと**
    ——一度混ぜて 14,191% という値を出した実例がある（Request Letter §C4）。
    """
    shipped = min(cap_lots, float(cb.demand_qty))
    u = unit_pnl_at_quantity(cb, sc, shipped, tp)
    margin_pct = (u["margin"] / u["rev"]) if u["rev"] else 0.0
    rank = ranked_markets.index(name) + 1
    marginal_rank = (ranked_markets.index(marginal_market) + 1
                     if marginal_market is not None else None)
    return {
        "ccy": cb.ccy,
        "price_local": cb.price_local,
        "rev": u["rev"],                 # JPY/lot
        "cost": u["cost"],                # JPY/lot
        "margin": u["margin"],            # JPY/lot
        "margin_pct": margin_pct,
        "rank": rank,
        "n_markets": len(ranked_markets),
        "demand_qty": float(cb.demand_qty),
        "cap_lots": cap_lots,
        "shipped": shipped,
        "tariff_rate": cb.tariff_rate,
        "marginal_market": (format_market_name(marginal_market)
                            if marginal_market is not None else None),
        "marginal_rank": marginal_rank,
    }


# ---------------------------------------------------------------------------
# 結論行・補助パネルの整形
# ---------------------------------------------------------------------------

def _format_market_share_ja(name: str, pct: float) -> str:
    """1市場分の『{名前} {比率}』表記（Phase 8-2a・D2）。

    名前と数字の間は**ノーブレークスペース**（`\\u00a0`）——通常の半角スペース
    だと、パネル側の `wraplength` 制約で折り返すときに名前と数字の間で改行
    されうる（実機で `US_NY` と `0` が分離して確認された。C3 で潰したはずの
    「答えが画面から消える」の再発）。区切りの `" / "`（通常スペース）でしか
    折れないようにする。整形は `format_market_name()` と同じくここ1箇所に置く
    （A5/A8の教訓——フィルタ／整形を2箇所に分けない）。
    """
    return f"{format_market_name(name)} {round(pct * 100)}"


def _format_allocation_summary_ja(markets: Sequence[str], x: Dict[str, float]) -> str:
    """結論行に収める配分の要約（Phase 8-2・C3）。

    15市場等をそのまま並べると1行が300文字超になり右端で切れ、しかも切れた
    部分（配分ゼロの市場）が答えの一部だった（C3 の事故）。上位4市場 + 残りの
    合計 + 配分ゼロの市場数、に畳む。**配分ゼロの市場を黙って落とさない**
    ——0件のときも「配分ゼロ なし」と明示する。
    """
    sorted_m = sorted(markets, key=lambda m: -x.get(m, 0.0))
    nonzero = [m for m in sorted_m if x.get(m, 0.0) > _UNALLOCATED_EPS]
    zero = [m for m in sorted_m if m not in nonzero]

    top = nonzero[:4]
    rest = nonzero[4:]

    parts = [_format_market_share_ja(m, x.get(m, 0.0)) for m in top]
    if rest:
        rest_pct = round(sum(x.get(m, 0.0) for m in rest) * 100)
        parts.append(f"他{len(rest)}市場 計{rest_pct}")
    parts.append(f"配分ゼロ {len(zero)}市場" if zero else "配分ゼロ なし")
    return " / ".join(parts)


def _format_full_allocation_ja(markets: Sequence[str], x: Dict[str, float]) -> str:
    """全市場の配分を省略なしで並べる（Phase 8-2・C3.3）。根拠パネルに全文で出す用。"""
    sorted_m = sorted(markets, key=lambda m: -x.get(m, 0.0))
    return " / ".join(_format_market_share_ja(m, x.get(m, 0.0)) for m in sorted_m)


def _format_structural_gap_ja(gap_val: Optional[float]) -> str:
    """構造由来の取りこぼしの文言（Phase 8-2・C6）。0 のとき「+0万」を出さない。"""
    if gap_val is None:
        return "構造由来の取りこぼし 不明"
    if gap_val == 0:
        return "構造由来の取りこぼしなし"
    return f"構造由来の取りこぼし {gap_val / 1e4:+.0f}万"


def _headline_lines(markets: Sequence[str], to: dict, line2: str, reversal: dict) -> List[str]:
    x = to["x"]
    alloc_str = _format_allocation_summary_ja(markets, x)
    line1 = f"推奨配分（連続最適）  {alloc_str}   利益 {to['profit'] / 1e8:.3f} 億"
    lines = [line1, line2]
    if reversal:
        verb = "割る" if reversal["direction"] == "below" else "上回る"
        leader = format_market_name(reversal["flips_to"].split(">")[0])
        axis_ja = _AXIS_LABEL_JA.get(reversal["axis"], reversal["axis"])
        lines.append(
            f"ただし {axis_ja} が {reversal['boundary']:.0f} 円を{verb}と "
            f"{leader} 優先へ判断反転"
        )
    return lines


def _levels_list(profit_levels: dict) -> List[dict]:
    """`levels` を値の降順で組む。P_greedy が P_grid を下回ったら highlight する
    （設計書 rev.2「貪欲法の行が格子の最良点より下に落ちたら、そこに構造がある」）。
    """
    names = ("P_opt", "P_greedy", "P_grid", "P_hier")
    entries = [{"name": n, "value": profit_levels[n]} for n in names
              if profit_levels.get(n) is not None]
    entries.sort(key=lambda e: -e["value"])
    greedy_below_grid = (
        profit_levels.get("P_greedy") is not None and profit_levels.get("P_grid") is not None
        and profit_levels["P_greedy"] < profit_levels["P_grid"]
    )
    for e in entries:
        e["highlight"] = (e["name"] == "P_greedy" and greedy_below_grid)
    return entries


def evaluate_allocation(model_dir: str, scenario_id: str, cap_wk: float,
                        allocation: Dict[str, float], uom: Optional[str] = None) -> dict:
    """選んだ配分1点を評価する（「⚑ この配分で計画する」用）。

    `wom.planning_state.new_state()` の `plan_eval` 引数にそのまま渡せる形で返す
    （Phase 7a・A1 のスキーマ）。パネル（tkinter 側）が `evaluate_point()` を
    直接呼ばずに済むよう、ここに切り出す（C9）。
    """
    from wom.allocation.grid import evaluate_point

    blocks, tp, sc = _scenario_blocks(model_dir, scenario_id, uom)
    markets = markets_of(blocks)
    x = tuple(float(allocation.get(m, 0.0)) for m in markets)
    ep = evaluate_point(x, blocks, tp, sc, cap_wk)
    return {
        "basis": "allocation_layer", "fx_usd": sc.fx_usd, "material_usd": sc.material_usd,
        "profit": ep["profit"], "revenue": ep["rev"], "cost": ep["cost"],
        "lots": sum(ep["q"].values()),
    }


# ---------------------------------------------------------------------------
# 本体
# ---------------------------------------------------------------------------

def build_s1_view(model_dir: str, *, scenario_id: str, cap_wk: float,
                  uom: Optional[str] = None,
                  node_path: Tuple[str, ...] = (),
                  band_yen: Optional[float] = None) -> dict:
    """S1 に出す値をすべて作る。tkinter に依存しない。

    Args:
        node_path: 階層ドリルダウンでいま見ているノードへの経路。() はルート
            （N=3・"triangle" モードでは常に () で、breadcrumb も常に []）。
        band_yen: 台地を数え直す絶対額の帯（円、Phase 8-3a・R4）。省略（None）
            すると `P_opt` の 0.01% あたりから既定値を作って使う——**呼び出し
            側がモデルを読み込んだときの値を持ち回り、以降の呼び出しではその
            値を渡すこと**。シナリオを切り替えるたびに省略して呼び直すと、
            そのたびに帯が作り直されてしまい、R4 が解決した「シナリオ間で
            台地サイズが比較できない」問題が形を変えて戻ってくる。
            実際に使った値は `view["band_yen"]` として返るので、呼び出し側は
            それを保持して次回以降に渡し戻せばよい。

    **`headline` と `levels` は `node_path` を変えても変わらない**（V1.1）。
    木のどこにいるかは `breadcrumb` / `node` だけが変わる——ノードを降りるたびに
    結論行の金額が変わると、経営者が「いま見ている数字が全体なのか一部なのか」
    を見失う。

    N==3（"triangle"）では `scan_surface()` を1回だけ、N>=4（"hierarchy"）では
    `scan_hierarchical()` を1回だけ呼ぶ（`node_path` の深さに関係なく1回。
    ドリルダウンは既に計算済みの `surfaces` を歩くだけ）。この関数自体は毎呼び出し
    ごとに再計算する（呼び出しをまたいだキャッシュはしない）——`node_path` が
    変わるたびに呼び出し元がこの関数を呼び直す設計なので、パネル側で model_dir/
    scenario_id/cap_wk が同じ呼び出しをキャッシュする余地はある（V1.3、Phase 8-2
    以降の最適化候補としてここに残す）。

    **`P_flat`（平坦格子全数）とは比較しない**（V1.4）。階層化は単なる間引きでは
    なく多重解像度であり、`P_hier - P_flat` の符号は Phase 6-3 の15通りの実測で
    定まらなかった（勝ち6・分け3・負け6）。符号の定まらない量を経営者に見せない
    ——誤差は常に0以上の `P_opt - P_hier` だけを使う。
    """
    blocks, tp, sc = _scenario_blocks(model_dir, scenario_id, uom)
    markets = markets_of(blocks)
    n_markets = len(markets)

    mo = build_allocation_merit_order(blocks, sc, cap_wk, transfer_price_usd=tp)
    to = true_continuous_optimum(blocks, sc, cap_wk, transfer_price_usd=tp)
    reversal = compute_reversal(blocks, tp, sc)

    # Phase 8-3a・R4: 台地の帯（絶対額）。省略時のみここで既定値を作る——
    # 呼び出し側が持ち回った値を渡してくれば、それをそのまま使う（上のdocstring参照）。
    if band_yen is None:
        band_yen = default_band_yen(to["profit"])

    if n_markets == 3:
        mode = "triangle"
        surf = scan_surface(blocks, tp, sc, cap_wk)
        grid_best, plateau = best_point(surf)
        cmp = compare_with_grid(mo, surf, true_optimum=to)

        profit_levels = {
            "P_opt": to["profit"], "P_greedy": mo["profit"], "P_grid": grid_best,
            "P_hier": None,
            "gap_amt": cmp["gap_amt"],
            "expected_gap": cmp["expected_gap_from_grid_resolution"],
            "structural_residual": cmp["structural_residual"],
            "structural_optimality_gap": cmp["structural_optimality_gap"],
            "grid_resolution_error": cmp["grid_resolution_error"],
            "residual_coverage": cmp["residual_coverage"],
            "hierarchy_gap": None, "n_markets": n_markets,
        }
        level_notes_ja = [
            f"格子解像度の誤差 {cmp['expected_gap_from_grid_resolution'] / 1e4:+.0f}万",
            _format_structural_gap_ja(cmp["structural_optimality_gap"]),
        ]
        headline_line2 = (
            f"格子の最良点との差 {cmp['gap_amt'] / 1e4:+.0f}万 = "
            + ("全量が格子解像度" if cmp["attributable_to_grid_resolution"]
               else "構造由来の乖離あり")
            + "。" + _format_structural_gap_ja(cmp["structural_optimality_gap"])
        )

        chosen = chosen_point(surf)   # 格子の真の最良点（Phase 6-5・E1）
        breadcrumb: List[str] = []
        node = {
            "name": "ALL", "children": list(markets),
            "child_x": dict(zip(markets, chosen["x"])),
            "cap_lots": cap_wk * WEEKS, "surface": surf, "plot_kind": "triangle",
            "is_unallocated": False, "unallocated_message": None,
            "leaf_economics": None,
        }
        # Phase 8-3a・R4: 台地は plateau_tol（相対値）ではなく band_yen（絶対額）
        # で数え直す——`grid_best`/`plateau`（best_point() の返り値）自体は
        # P_grid の値として上で使うので無変更、数え直すのは表示用の件数だけ。
        plateau_size: Optional[int] = len(plateau_by_band(surf, band_yen))

    else:
        mode = "hierarchy"
        tree = build_hierarchy(blocks, model_dir, max_children=3)
        hier = scan_hierarchical(blocks, tree, tp, sc, cap_wk)
        surfaces = hier["surfaces"]
        hierarchy_gap_value = to["profit"] - hier["profit"]   # 常に 0 以上（V1.4）

        # Phase 8-2・C5: 階層化の誤差を「配分ズレ」+「数量（出し切れず）」に分解する。
        # 割り算1個（率）や差分1個（円）だけで語らない（Phase 7a・gap_vs_plan_pct と
        # 同じ理由）。恒等式2本をテストで固定している（tests/test_s1_view_model.py）:
        #   hierarchy_gap == mix + vol（±1円）
        #   vol == unshipped × 限界市場の単位マージン（±1円）
        # 限界市場は「メリットオーダー上、能力が尽きた市場」＝ mo["marginal_market"]
        # （既に計算済みの mo をそのまま使う。再計算しない）。
        q_hier_total = sum(hier["q"].values())
        same = true_continuous_optimum(blocks, sc, cap_wk=q_hier_total / WEEKS,
                                       transfer_price_usd=tp)
        hier_mix = same["profit"] - hier["profit"]        # 配分ズレ（上位が下位を見ていない）
        hier_vol = to["profit"] - same["profit"]          # 数量（出し切れず）
        unshipped = sum(to["q"].values()) - q_hier_total
        marginal_market = mo["marginal_market"]

        profit_levels = {
            "P_opt": to["profit"], "P_greedy": mo["profit"], "P_grid": None,
            "P_hier": hier["profit"],
            "gap_amt": None, "expected_gap": None, "structural_residual": None,
            "structural_optimality_gap": None, "grid_resolution_error": None,
            "residual_coverage": None,
            "hierarchy_gap": hierarchy_gap_value, "n_markets": n_markets,
            "hierarchy_mix": hier_mix, "hierarchy_vol": hier_vol,
            "hierarchy_unshipped": unshipped,
            "hierarchy_marginal_market": marginal_market,
        }
        summary_line = (
            f"階層化の誤差 {-hierarchy_gap_value / 1e8:+.2f}億"
            f" = 配分ズレ {-hier_mix / 1e8:+.2f}億"
            f" ＋ 出し切れず {-hier_vol / 1e8:+.2f}億（未出荷 {unshipped:,.0f} lot）"
        )
        level_notes_ja = [
            summary_line,
            f"配分ズレ {-hier_mix / 1e8:+.2f}億: 上位で確定した配分が下位の事情を見ていない",
            f"出し切れず {-hier_vol / 1e8:+.2f}億: 下位の需要上限で能力が余ったため"
            + (f"（限界市場 {format_market_name(marginal_market)}）"
               if marginal_market else ""),
        ]
        headline_line2 = summary_line

        cur, cap_lots, path_nodes = _walk_hierarchy(tree, surfaces, node_path, cap_wk, WEEKS)
        breadcrumb = [n["name"] for n in path_nodes]

        children_names = [c["name"] for c in cur["children"]]
        is_leaf = not children_names
        if cur["name"] in surfaces:
            chosen_node = chosen_point(surfaces[cur["name"]])   # Phase 6-5・E1
            child_x = dict(zip(children_names, chosen_node["x"]))
            # Phase 8-3a・R4: 台地は band_yen（絶対額）で数え直す（上の triangle
            # 分岐と同じ理由）。
            plateau_size = len(plateau_by_band(surfaces[cur["name"]], band_yen))
            surface_for_node = surfaces[cur["name"]]
        else:
            child_x = {}
            plateau_size = None
            surface_for_node = []

        # Phase 8-2・C2: 配分ゼロの枝（葉ではない）に「意味の無い比率」を出さない。
        # 葉自身が cap_lots==0 のときは C4 の単位経済（出荷0・順位）で説明が付くので
        # is_unallocated 扱いにしない（葉が優先）。
        is_unallocated = (not is_leaf) and _is_unallocated(cap_lots)
        unallocated_parent = (format_market_name(path_nodes[-2]["name"])
                              if is_unallocated and len(path_nodes) >= 2 else None)
        unallocated_message = (
            _unallocated_message_ja(unallocated_parent, format_market_name(cur["name"]))
            if is_unallocated else None)

        leaf_economics = None
        if is_leaf:
            ranked_markets = [b["market"] for b in mo["blocks"]] + mo["excluded"]
            leaf_economics = _leaf_economics(
                cur["name"], blocks[cur["name"]], sc, tp, cap_lots,
                ranked_markets, marginal_market)

        node = {
            "name": cur["name"], "children": children_names, "child_x": child_x,
            "cap_lots": cap_lots, "surface": surface_for_node,
            "plot_kind": _plot_kind(len(cur["children"])),
            "is_unallocated": is_unallocated, "unallocated_message": unallocated_message,
            "leaf_economics": leaf_economics,
        }

    headline = {
        "recommended": dict(to["x"]),
        "profit": to["profit"],
        "profit_source": "P_opt",
        "lines_ja": _headline_lines(markets, to, headline_line2, reversal),
        # Phase 8-2・C3.3: 全市場の配分（省略なし）。根拠パネルに全文で出す用
        # （結論行は上位4市場+要約に畳むため、答えを画面外に落とさないための控え）。
        "full_allocation_ja": _format_full_allocation_ja(markets, to["x"]),
    }
    levels = _levels_list(profit_levels)

    return {
        "n_markets": n_markets,
        "mode": mode,
        "headline": headline,
        "levels": levels,
        "level_notes_ja": level_notes_ja,
        "breadcrumb": breadcrumb,
        "node": node,
        "plateau_size": plateau_size,
        "band_yen": band_yen,
        # robust_point は複数シナリオの集合が要る（analytics.robust_point()）。
        # build_s1_view() は単一シナリオしか受け取らないため、本 Phase では
        # 意味のある値を作れず None のまま返す（Phase 8-2 以降、シナリオ集合を
        # 引数化してから実装する）。
        "robust_point": None,
        "reversal": reversal,
        "profit_levels": profit_levels,
        # メリットオーダー曲線 Drill-down 用（build_allocation_merit_order() の
        # 生の返却。既にこの呼び出しで計算済みなので、パネル側で再計算しない）。
        "merit_order": mo,
    }
