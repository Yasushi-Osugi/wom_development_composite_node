---
tags: [wom, code]
---
# wom/allocation/hierarchical_simplex.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/allocation/hierarchical_simplex.py) · [原文テキスト](../../../90_Raw/wom/allocation/hierarchical_simplex.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/02_Demand_Allocation|Optimization on Demand Allocation]]

## モジュール説明（docstring原文）

```text
wom/allocation/hierarchical_simplex.py — 階層化単体格子（Phase 6-3）
================================================================================
平坦な単体格子は N=6（53,130点）で頭打ちになる。市場を木にまとめ、**各ノードで
3市場以下の単体を走査する**ことで、N が大きいケース（`oil-global-2027` の21市場）
を現実的な点数で扱えるようにする。

正典: requests/Phase6_DesignMD_NMarketHierarchy.md §5（rev.6）
依頼: requests/Phase6-3_RequestLetter_to_CodeKun.md

方式（案B・逐次確定型、設計書 §5.3）:
  上位ノードを `scan_surface()` + `best_point()` で確定してから、その配分
  （`q[g]`、需要で頭打ちされた後の実現量）を子ノードの能力として渡して降りる。
  これ自体が貪欲法であり、真の最適を外しうる——その誤差は `hierarchy_gap()` が
  `true_continuous_optimum()`（格子を経由しない）を基準に金額で測る。

グルーピングの原則（設計書 §5.4、この順に適用）:
  1. 供給元 Mother Plant（`sc_tree_master.csv` を leaf_out から `parent_node` で
     遡り、最初に見つかる `supply_point` ノードでまとめる）
  2. 通貨圏（`CostBlock.ccy`）
  3. 供給モード（供給ライン名に "Import" を含むかどうか）
  ある principle が「効かない」（1グループにしかならない）場合は次の principle へ
  進む。それでも `max_children` に収まらなければ `ValueError`（黙って割らない）。

既存モジュール（grid.py / merit_order.py / analytics.py / regime_map.py）は
**読むだけ**——本ファイルは新規モジュールであり、既存の返却値は1円も変えない（C8）。
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_rows` | 44 | docstringなし（下のコード参照） |
| FunctionDef | `_leaf_node` | 54 | docstringなし（下のコード参照） |
| FunctionDef | `_group_node` | 58 | docstringなし（下のコード参照） |
| FunctionDef | `_group_by` | 63 | items を key_fn(item) でグルーピングする（初出順を保持・決定的）。 |
| FunctionDef | `_supply_point_of` | 72 | leaf_out ノードから parent_node を遡り、最初の supply_point ノード名を返す。 |
| FunctionDef | `_resolve_market_leaves` | 96 | blocks の各キー（market または region）を leaf_out ノード名へ解決する。 |
| FunctionDef | `_cluster_to_node` | 156 | docstringなし（下のコード参照） |
| FunctionDef | `_build` | 170 | docstringなし（下のコード参照） |
| FunctionDef | `build_hierarchy` | 198 | 市場を「各ノードの子が max_children 以下」の木に組む（設計書 §5.4）。 |
| FunctionDef | `aggregate_block` | 253 | 子ブロックを需要加重平均で1つに集約する。 |
| FunctionDef | `scan_hierarchical` | 323 | 案B（逐次確定型）。上位を確定してから、その配分のもとで下位へ降りる。 |
| FunctionDef | `hierarchy_gap` | 386 | 階層化の誤差を測る。N が小さく平坦全数が計算できるときだけ P_flat も返す。 |
| FunctionDef | `resolve_row` | 117 | docstringなし（下のコード参照） |
| FunctionDef | `supply_point_of_market` | 216 | docstringなし（下のコード参照） |
| FunctionDef | `ccy_of` | 231 | docstringなし（下のコード参照） |
| FunctionDef | `mode_of` | 241 | docstringなし（下のコード参照） |
| FunctionDef | `_descend` | 343 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/requests/Phase6_DesignMD_NMarketHierarchy.md|requests/Phase6_DesignMD_NMarketHierarchy.md]]
- [[80_Sources/requests/Phase6-3_RequestLetter_to_CodeKun.md|requests/Phase6-3_RequestLetter_to_CodeKun.md]]
- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]
- [[80_Sources/wom/allocation/grid.py|wom/allocation/grid.py]]
- [[80_Sources/wom/allocation/merit_order.py|wom/allocation/merit_order.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
wom/allocation/hierarchical_simplex.py — 階層化単体格子（Phase 6-3）
================================================================================
平坦な単体格子は N=6（53,130点）で頭打ちになる。市場を木にまとめ、**各ノードで
3市場以下の単体を走査する**ことで、N が大きいケース（`oil-global-2027` の21市場）
を現実的な点数で扱えるようにする。

正典: requests/Phase6_DesignMD_NMarketHierarchy.md §5（rev.6）
依頼: requests/Phase6-3_RequestLetter_to_CodeKun.md

方式（案B・逐次確定型、設計書 §5.3）:
  上位ノードを `scan_surface()` + `best_point()` で確定してから、その配分
  （`q[g]`、需要で頭打ちされた後の実現量）を子ノードの能力として渡して降りる。
  これ自体が貪欲法であり、真の最適を外しうる——その誤差は `hierarchy_gap()` が
  `true_continuous_optimum()`（格子を経由しない）を基準に金額で測る。

グルーピングの原則（設計書 §5.4、この順に適用）:
  1. 供給元 Mother Plant（`sc_tree_master.csv` を leaf_out から `parent_node` で
     遡り、最初に見つかる `supply_point` ノードでまとめる）
  2. 通貨圏（`CostBlock.ccy`）
  3. 供給モード（供給ライン名に "Import" を含むかどうか）
  ある principle が「効かない」（1グループにしかならない）場合は次の principle へ
  進む。それでも `max_children` に収まらなければ `ValueError`（黙って割らない）。

既存モジュール（grid.py / merit_order.py / analytics.py / regime_map.py）は
**読むだけ**——本ファイルは新規モジュールであり、既存の返却値は1円も変えない（C8）。
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from wom.allocation.transmission import CostBlock, Scenario, unit_pnl_at_quantity
from wom.allocation.grid import (
    MAX_GRID_POINTS, WEEKS, best_point, chosen_point, grid_point_count, markets_of,
    scan_surface,
)
from wom.allocation.merit_order import true_continuous_optimum


def _rows(model_dir: str, fname: str) -> List[dict]:
    path = os.path.join(model_dir, fname)
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# V1: build_hierarchy() — 木を組む
# ---------------------------------------------------------------------------

def _leaf_node(market: str) -> dict:
    return {"name": market, "children": [], "markets": (market,)}


def _group_node(name: str, children: List[dict]) -> dict:
    markets = tuple(m for c in children for m in c["markets"])
    return {"name": name, "children": children, "markets": markets}


def _group_by(items: Sequence, key_fn: Callable) -> "dict":
    """items を key_fn(item) でグルーピングする（初出順を保持・決定的）。"""
    groups: Dict = {}
    for it in items:
        k = key_fn(it)
        groups.setdefault(k, []).append(it)
    return groups


def _supply_point_of(leaf: str, node_info: Dict[str, dict]) -> str:
    """leaf_out ノードから parent_node を遡り、最初の supply_point ノード名を返す。"""
    cur = leaf
    seen: Set[str] = set()
    while True:
        info = node_info.get(cur)
        if info is None:
            raise ValueError(
                f"build_hierarchy(): node {cur!r} not found while walking up "
                f"from leaf_out {leaf!r} (sc_tree_master.csv)"
            )
        if info["node_type"] == "supply_point":
            return cur
        if cur in seen:
            raise ValueError(f"build_hierarchy(): cycle detected walking up from {leaf!r}")
        seen.add(cur)
        parent = info["parent_node"]
        if not parent:
            raise ValueError(
                f"build_hierarchy(): no supply_point ancestor found for leaf_out {leaf!r}"
            )
        cur = parent


def _resolve_market_leaves(blocks: Dict[str, CostBlock],
                           model_dir: str) -> Tuple[Dict[str, str], List[dict]]:
    """blocks の各キー（market または region）を leaf_out ノード名へ解決する。

    `ga_market_aggregation.csv` の行を、まず `market_group` が blocks のキーと
    1:1（ちょうど1行）で一致するかを試し（oil-global-2027 のように market_group
    自体が1市場1leaf_outのケース）、だめなら `region` が1:1で一致するかを試す
    （soysauce の `derive_cost_blocks(..., level="region")` のケース）。
    どちらでも一意に決まらない場合は build_hierarchy() が受け取った blocks が
    「最も細かい粒度」でないということなので、その旨を報告して止める。
    """
    agg = _rows(model_dir, "ga_market_aggregation.csv")
    sct_rows = _rows(model_dir, "sc_tree_master.csv")
    leaf_names: Set[str] = {r["node_name"] for r in sct_rows if r["node_type"] == "leaf_out"}

    by_market_group: Dict[str, List[dict]] = defaultdict(list)
    by_region: Dict[str, List[dict]] = defaultdict(list)
    for r in agg:
        by_market_group[r["market_group"]].append(r)
        by_region[r["region"]].append(r)

    def resolve_row(row: dict) -> str:
        node = (row.get("market_node") or "").strip()
        if node:
            if node not in leaf_names:
                raise ValueError(
                    f"build_hierarchy(): market_node {node!r} is not a leaf_out node"
                )
            return node
        region = row["region"]
        candidates = sorted({r2["node_name"] for r2 in sct_rows
                            if r2["node_type"] == "leaf_out" and r2["region"] == region})
        if len(candidates) != 1:
            raise ValueError(
                f"build_hierarchy(): region {region!r} does not map to exactly one "
                f"leaf_out node ({candidates}); add a market_node column to "
                f"ga_market_aggregation.csv to disambiguate"
            )
        return candidates[0]

    leaf_of_key: Dict[str, str] = {}
    for key in blocks:
        rows_mg = by_market_group.get(key, [])
        if len(rows_mg) == 1:
            leaf_of_key[key] = resolve_row(rows_mg[0])
            continue
        rows_rg = by_region.get(key, [])
        if len(rows_rg) == 1:
            leaf_of_key[key] = resolve_row(rows_rg[0])
            continue
        raise ValueError(
            f"build_hierarchy(): cannot resolve a unique leaf_out for market key {key!r} "
            f"(found {len(rows_mg)} rows with market_group={key!r}, {len(rows_rg)} rows "
            f"with region={key!r}). build_hierarchy() requires blocks at the finest "
            f"granularity — derive_cost_blocks(..., level='region'), or a market_group "
            f"that is already 1:1 with a leaf_out (e.g. oil-global-2027)."
        )
    return leaf_of_key, sct_rows


def _cluster_to_node(cluster: dict, max_children: int) -> dict:
    markets = cluster["markets"]
    if len(markets) == 1:
        return _leaf_node(markets[0])
    if len(markets) > max_children:
        raise ValueError(
            f"build_hierarchy(): group {cluster['id']!r} has {len(markets)} markets "
            f"{markets}, exceeds max_children={max_children}. It represents a single "
            f"undividable unit (e.g. one supply line) — no grouping principle applies "
            f"inside it."
        )
    return _group_node(cluster["id"], [_leaf_node(m) for m in markets])


def _build(name: str, clusters: List[dict], remaining_principles: List[str],
          attr_fns: Dict[str, Callable[[dict], object]], max_children: int) -> dict:
    if len(clusters) == 1:
        return _cluster_to_node(clusters[0], max_children)
    if len(clusters) <= max_children:
        return _group_node(name, [_cluster_to_node(c, max_children) for c in clusters])
    if not remaining_principles:
        n_markets = sum(len(c["markets"]) for c in clusters)
        raise ValueError(
            f"build_hierarchy(): {len(clusters)} groups ({n_markets} markets) under "
            f"{name!r} exceed max_children={max_children}, and no more grouping "
            f"principles are available (supply_point / currency / mode all tried)."
        )
    principle, rest = remaining_principles[0], remaining_principles[1:]
    buckets = _group_by(clusters, attr_fns[principle])
    if len(buckets) <= 1:
        # この principle は効かない（1グループにしかならない）: 次の principle へ
        return _build(name, clusters, rest, attr_fns, max_children)
    if len(buckets) > max_children:
        raise ValueError(
            f"build_hierarchy(): {principle} grouping under {name!r} produced "
            f"{len(buckets)} groups, exceeds max_children={max_children}"
        )
    children = [_build(str(bkey), members, rest, attr_fns, max_children)
               for bkey, members in buckets.items()]
    return _group_node(name, children)


def build_hierarchy(blocks: Dict[str, CostBlock], model_dir: str,
                    max_children: int = 3) -> dict:
    """市場を「各ノードの子が max_children 以下」の木に組む（設計書 §5.4）。

    返却: {"name": str, "children": [...], "markets": (...)} の再帰構造。
          葉は {"name": market, "children": [], "markets": (market,)}。

    ケースが `max_children` 以下ならそもそも階層化は不要——その場合は
    ルート直下に全市場を並べた1段の木を返す（`scan_hierarchical()` で
    平坦スキャン1回と等価になる）。
    """
    markets = list(blocks.keys())          # blocks の挿入順（決定的、markets_of() と同じ）
    if len(markets) <= max_children:
        return _group_node("ALL", [_leaf_node(m) for m in markets])

    leaf_of_key, sct_rows = _resolve_market_leaves(blocks, model_dir)
    node_info: Dict[str, dict] = {r["node_name"]: r for r in sct_rows}

    def supply_point_of_market(m: str) -> str:
        return _supply_point_of(leaf_of_key[m], node_info)

    # 第一原則: 供給元 Mother Plant（供給ライン）でまとめる。市場の物理的な
    # 供給経路に基づく属性なので、生のマーケットにのみ意味を持ち、一度だけ適用する。
    clusters = [{"id": m, "markets": (m,)} for m in markets]
    sl_buckets = _group_by(clusters, lambda c: supply_point_of_market(c["markets"][0]))

    if len(sl_buckets) > 1:
        # 効いた: 供給ライングループを以降の「アイテム」として扱う
        clusters = [{"id": sl, "markets": tuple(c["markets"][0] for c in members)}
                   for sl, members in sl_buckets.items()]
    # else: 効かない（例: soysauce の SP_Soy 単独）。クラスタは生マーケットのまま
    #       第二原則（通貨）へ進む。

    def ccy_of(c: dict) -> str:
        ccys = {blocks[m].ccy for m in c["markets"]}
        if len(ccys) > 1:
            raise ValueError(
                f"build_hierarchy(): group {c['id']!r} mixes currencies "
                f"{sorted(ccys)} — a group must be currency-uniform (C10; "
                f"averaging price_local across currencies is meaningless)."
            )
        return next(iter(ccys))

    def mode_of(c: dict) -> str:
        # 供給ライン名（クラスタID）に "Import" を含むかどうか（第三原則）
        return "Import" if "Import" in c["id"] else "Local"

    attr_fns = {"currency": ccy_of, "mode": mode_of}
    return _build("ALL", clusters, ["currency", "mode"], attr_fns, max_children)


# ---------------------------------------------------------------------------
# V2: aggregate_block() — グループノードの CostBlock
# ---------------------------------------------------------------------------

def aggregate_block(children: Sequence[CostBlock]) -> CostBlock:
    """子ブロックを需要加重平均で1つに集約する。

    - usd / eur / jpy / tariff_rate / price_local : 需要加重平均（demand_qty 比、
      CSV の internal_ratio は「需要シェアそのもの」なので、列を新しく読む必要はない）
    - demand_qty                    : 単純合計
    - ccy / material_usd_base       : 子で同一であること（違えば ValueError・C10）

    【Phase 6-3b（Addendum・A1）】当初案は `price_local` も子で同一であることを
    要求していたが、これは設計の誤りだった——soysauce ではグループ内がたまたま
    同価（FR/BE/NL・US_W/US_E）だったため気づかなかったが、グループ内で販売価格が
    違うのは異常ではなく普通である（oil の KANTO/KANSAI/CHUBU 等）。`price_local`
    も原価と同じ需要加重平均にする。同一を要求するのは `ccy` と
    `material_usd_base` だけ（通貨混在は無意味、原料単価の基準がずれるのは異常）。

    cliff（数量依存関税、`tariff_rate_preferential`）を持つ市場が混ざるグループは
    本 Phase では非対応とし ValueError を投げる。閾値は数量に対して定義されて
    おり、加重平均に意味がないためである（Phase 6-4 以降の課題）。
    """
    children = list(children)
    if not children:
        raise ValueError("aggregate_block(): children must be non-empty")
    if len(children) == 1:
        return children[0]

    if any(c.tariff_rate_preferential is not None or c.preferential_threshold_lot is not None
          for c in children):
        raise ValueError(
            "aggregate_block(): cliff (quantity-dependent preferential tariff) is not "
            "supported when aggregating multiple CostBlocks — the threshold is defined "
            "against quantity, so a weighted average has no meaning here "
            "(Phase 6-3 scope limit, see Request Letter V2)."
        )

    ccys = {c.ccy for c in children}
    if len(ccys) != 1:
        raise ValueError(
            f"aggregate_block(): children mix currencies {sorted(ccys)} — a group must "
            f"be currency-uniform (C10)."
        )
    mat_bases = {c.material_usd_base for c in children}
    if len(mat_bases) != 1:
        raise ValueError(
            f"aggregate_block(): children have differing material_usd_base "
            f"{sorted(mat_bases)}; they must be identical within a group."
        )

    total_demand = sum(c.demand_qty for c in children)
    if total_demand > 0:
        weights = [c.demand_qty / total_demand for c in children]
    else:
        weights = [1.0 / len(children)] * len(children)   # 需要ゼロ集団のフォールバック

    usd = sum(w * c.usd for w, c in zip(weights, children))
    eur = sum(w * c.eur for w, c in zip(weights, children))
    jpy = sum(w * c.jpy for w, c in zip(weights, children))
    tariff_rate = sum(w * c.tariff_rate for w, c in zip(weights, children))
    price_local = sum(w * c.price_local for w, c in zip(weights, children))

    return CostBlock(
        usd=usd, eur=eur, jpy=jpy, tariff_rate=tariff_rate,
        price_local=price_local, ccy=children[0].ccy,
        demand_qty=total_demand, material_usd_base=children[0].material_usd_base,
    )


# ---------------------------------------------------------------------------
# V3: scan_hierarchical() — 木を降りながら走査（案B・逐次確定型）
# ---------------------------------------------------------------------------

def scan_hierarchical(blocks: Dict[str, CostBlock], tree: dict,
                      transfer_price_usd: float, sc: Scenario, cap_wk: float,
                      weeks: int = WEEKS, delta: float = 0.05) -> dict:
    """案B（逐次確定型）。上位を確定してから、その配分のもとで下位へ降りる。

    子ノードに渡す能力は、上位ノードで確定した実現量 `q[g]`（需要で頭打ちされた
    後の値）であって `x[g] × cap` ではない（`cap_wk` 換算で渡す）。子が1つの
    ノードは `scan_surface()` を呼ばない（`simplex_grid()` は `n_dim>=2` しか
    作れないため）——そのまま能力を子へ通す。

    返却:
      {"profit": float,              # P_hier
       "q": {market: qty},           # 葉まで降りた最終配分
       "points": int,                # 実際に評価した格子点の総数
       "nodes": int,                 # 走査したノード数（子1のノードは数えない）
       "surfaces": {node_name: [...]}}  # 各ノードの走査結果（ドリルダウン描画用）
    """
    surfaces: Dict[str, list] = {}
    counters = {"points": 0, "nodes": 0}

    def _descend(node: dict, cap_wk_here: float) -> Dict[str, float]:
        children = node["children"]
        if not children:
            m = node["name"]
            q = min(cap_wk_here * weeks, float(blocks[m].demand_qty))
            return {m: max(q, 0.0)}
        if len(children) == 1:
            return _descend(children[0], cap_wk_here)

        sub_blocks = {c["name"]: aggregate_block([blocks[m] for m in c["markets"]])
                     for c in children}
        surf = scan_surface(sub_blocks, transfer_price_usd, sc, cap_wk_here,
                            weeks=weeks, delta=delta)
        chosen = chosen_point(surf)             # 格子の真の最良点（Phase 6-5・E1）
        surfaces[node["name"]] = surf
        counters["points"] += len(surf)
        counters["nodes"] += 1

        q_out: Dict[str, float] = {}
        for c in children:
            qty = chosen["q"][c["name"]]
            child_cap_wk = (qty / weeks) if weeks else 0.0
            q_out.update(_descend(c, child_cap_wk))
        return q_out

    q_final = _descend(tree, cap_wk)
    profit = sum(
        q * unit_pnl_at_quantity(blocks[m], sc, q, transfer_price_usd)["margin"]
        for m, q in q_final.items()
    )
    return {
        "profit": profit,
        "q": q_final,
        "points": counters["points"],
        "nodes": counters["nodes"],
        "surfaces": surfaces,
    }


# ---------------------------------------------------------------------------
# V4: hierarchy_gap() — 誤差を金額で出す
# ---------------------------------------------------------------------------

def hierarchy_gap(blocks: Dict[str, CostBlock], tree: dict,
                  transfer_price_usd: float, sc: Scenario, cap_wk: float,
                  weeks: int = WEEKS, delta: float = 0.05,
                  max_flat_points: int = MAX_GRID_POINTS) -> dict:
    """階層化の誤差を測る。N が小さく平坦全数が計算できるときだけ P_flat も返す。

    誤差の基準は `P_opt`（`true_continuous_optimum()`、格子を経由しない）である
    ——`P_flat`（平坦格子）ではない。理由（設計書 §5・Request Letter (1)）:
    階層化は単なる間引きではなく多重解像度であり、「上位の判断が下位の事情を
    見ていない」ことによる悪化と「グループ内では絶対量で細かい5%刻みになる」
    ことによる改善が逆向きに働くため、`P_hier` と `P_flat` のどちらが上かは
    ケースごとに変わる（`hier_minus_flat` に符号の仮定を置かないこと）。

    返却:
      {"P_opt":  float,          # true_continuous_optimum()（格子を経由しない）
       "P_hier": float,
       "P_flat": float | None,   # 平坦全数。max_flat_points 超過なら None
       "hierarchy_gap":     P_opt − P_hier,   # ← 誤差の基準。常に 0 以上
       "flat_grid_gap":     P_opt − P_flat,   # P_flat が None なら None
       "hier_minus_flat":   P_hier − P_flat,  # 符号は定まらない（参考値）
       "points_hier": int, "points_flat": int | None}
    """
    p_opt = true_continuous_optimum(blocks, sc, cap_wk,
                                    transfer_price_usd=transfer_price_usd,
                                    weeks=weeks)["profit"]
    hier = scan_hierarchical(blocks, tree, transfer_price_usd, sc, cap_wk,
                             weeks=weeks, delta=delta)

    markets = markets_of(blocks)
    n_flat = grid_point_count(delta, len(markets))
    p_flat: Optional[float] = None
    points_flat: Optional[int] = None
    if n_flat <= max_flat_points:
        surf = scan_surface(blocks, transfer_price_usd, sc, cap_wk, weeks=weeks,
                            delta=delta, max_points=max_flat_points)
        p_flat, _plateau = best_point(surf)
        points_flat = len(surf)

    return {
        "P_opt": p_opt,
        "P_hier": hier["profit"],
        "P_flat": p_flat,
        "hierarchy_gap": p_opt - hier["profit"],
        "flat_grid_gap": (p_opt - p_flat) if p_flat is not None else None,
        "hier_minus_flat": (hier["profit"] - p_flat) if p_flat is not None else None,
        "points_hier": hier["points"],
        "points_flat": points_flat,
    }

````
