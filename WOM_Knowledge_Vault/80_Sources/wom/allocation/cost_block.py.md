---
tags: [wom, code]
---
# wom/allocation/cost_block.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/allocation/cost_block.py) · [原文テキスト](../../../90_Raw/wom/allocation/cost_block.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/02_Demand_Allocation|Optimization on Demand Allocation]]

## モジュール説明（docstring原文）

```text
wom/allocation/cost_block.py — Step 0.5 原価ブロック導出器
=========================================================
**原価ブロックは入力ではなく導出物である。** 既存 21 CSV から、市場（JP/US/EU）ごとの
通貨別ブロック（USD / EUR / JPY・関税前）＋販売条件を機械的に導出し、`transmission.py`
の `CostBlock` を組み立てる。関税は transmission.py 側（Step 3）で `tariff_rate ×
transfer_price` として加算されるため、本モジュールのブロックには含めない。

正典：docs/design/ask_global_allocation_spec.md §5 Step 0.5 / §5.1（導出表）
参照：tools/proto_terrain2.py（CHANNELS の固定値と一致すること）

導出元:
  経路      sc_tree（実体は ppc_edge_cost_rule の "A->B" フロー）を leaf_out から遡る
  ノード費  ppc_node_cost_rule（node × currency の fixed_amount）
  エッジ費  ppc_edge_cost_rule（edge × currency の fixed_amount）
  原料費    ppc_supplier_cost（leaf_in・base_week の latest-prior 参照）
  関税率    ppc_tariff_rule（leaf_out への最終エッジ）
  販売価格  ppc_market_price（region × base_week）
  移転価格  sku_master.unit_cost / base_fx × (1 + ppc_transfer_price_rule.margin_rate)
  市場集約  ga_market_aggregation（region → market・internal_ratio）

【要確認・設計判断】移転価格の base（$16）は sku_master.unit_cost(2400 JPY) ÷ base_fx(150)
として導出した（proto_terrain2 の 16.0 と一致）。「終端 MOM 累積 unit_cost」からの厳密導出
とは僅かに異なりうる（cumulative ≒ $16.7）。回帰値（付録 A / #10）は 17.6 前提のため本式を採る。

【Phase 6-3（6-3b・V6.1）】`region` は一意であるとは限らない——`oil-global-2027` は
21 の `leaf_out` に対して `region` が 15 種類しかなく（`KANTO`/`KANSAI`/`CHUBU` が
`Local`/`Local_H`/`Local_R` の3供給ラインで重複）、旧実装は後の行が前の行を黙って
上書きしていた（サイレントなデータ欠落）。本改修で、`ga_market_aggregation.csv` に
任意の `market_node` 列（`leaf_out` ノード名を直接指定）を追加し、`region` が重複する
場合は `market_node` 無しでは明示 ValueError にする（黙って上書きしない）。

【Phase 6-3b（Addendum・A2）】市場内の価格解決も同じ家族のバグを持っていた——
「市場内で共通」という前提を検査せず、ループの最後の region の価格を黙って採用
していた。本改修で `price_local` は `internal_ratio` による加重平均にし、`ccy`
（通貨）が市場内で混在していたら明示 ValueError にする（黙って上書きしない）。

【Phase 6-3b（Addendum・A3/A4）】lot の物理的な単位（`sku_master.csv` の `uom`）が
市場ごとに異なりうる（`oil-global-2027` は通常の `KL` と、タンカー単位の
`KL100KBBL` が混在——CLAUDE.md L528 に記載の意図的設計）。A系統は「1つの能力
プールを複数市場が lot 単位で奪い合う」モデルであり、lot の物理的意味が市場ごとに
違えばこの前提自体が成立しない。`derive_cost_blocks(uom=...)` で単位を1種類に
絞り込めるようにし、絞り込み無しで複数単位が混在していたら ValueError にする。
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_rows` | 59 | docstringなし（下のコード参照） |
| FunctionDef | `_latest_prior` | 65 | docstringなし（下のコード参照） |
| FunctionDef | `derive_cost_blocks` | 70 | (market -> CostBlock, transfer_price_usd) を返す。 |
| FunctionDef | `resolve_leaf` | 163 | ga_market_aggregation.csv の1行から leaf_out ノード名を決める。 |
| FunctionDef | `row_uom` | 203 | docstringなし（下のコード参照） |
| FunctionDef | `leaf_block` | 270 | 1 leaf_out の通貨別コストブロック・関税率・販売条件・到達ホップ数。 |

## 関連する知識源

- [[80_Sources/docs/design/ask_global_allocation_spec.md|docs/design/ask_global_allocation_spec.md]]
- [[80_Sources/tools/proto_terrain2.py|tools/proto_terrain2.py]]
- [[80_Sources/wom/allocation/transmission.py|wom/allocation/transmission.py]]

## 全文（コメント・原文を省略せず収録）

````python
# -*- coding: utf-8 -*-
"""
wom/allocation/cost_block.py — Step 0.5 原価ブロック導出器
=========================================================
**原価ブロックは入力ではなく導出物である。** 既存 21 CSV から、市場（JP/US/EU）ごとの
通貨別ブロック（USD / EUR / JPY・関税前）＋販売条件を機械的に導出し、`transmission.py`
の `CostBlock` を組み立てる。関税は transmission.py 側（Step 3）で `tariff_rate ×
transfer_price` として加算されるため、本モジュールのブロックには含めない。

正典：docs/design/ask_global_allocation_spec.md §5 Step 0.5 / §5.1（導出表）
参照：tools/proto_terrain2.py（CHANNELS の固定値と一致すること）

導出元:
  経路      sc_tree（実体は ppc_edge_cost_rule の "A->B" フロー）を leaf_out から遡る
  ノード費  ppc_node_cost_rule（node × currency の fixed_amount）
  エッジ費  ppc_edge_cost_rule（edge × currency の fixed_amount）
  原料費    ppc_supplier_cost（leaf_in・base_week の latest-prior 参照）
  関税率    ppc_tariff_rule（leaf_out への最終エッジ）
  販売価格  ppc_market_price（region × base_week）
  移転価格  sku_master.unit_cost / base_fx × (1 + ppc_transfer_price_rule.margin_rate)
  市場集約  ga_market_aggregation（region → market・internal_ratio）

【要確認・設計判断】移転価格の base（$16）は sku_master.unit_cost(2400 JPY) ÷ base_fx(150)
として導出した（proto_terrain2 の 16.0 と一致）。「終端 MOM 累積 unit_cost」からの厳密導出
とは僅かに異なりうる（cumulative ≒ $16.7）。回帰値（付録 A / #10）は 17.6 前提のため本式を採る。

【Phase 6-3（6-3b・V6.1）】`region` は一意であるとは限らない——`oil-global-2027` は
21 の `leaf_out` に対して `region` が 15 種類しかなく（`KANTO`/`KANSAI`/`CHUBU` が
`Local`/`Local_H`/`Local_R` の3供給ラインで重複）、旧実装は後の行が前の行を黙って
上書きしていた（サイレントなデータ欠落）。本改修で、`ga_market_aggregation.csv` に
任意の `market_node` 列（`leaf_out` ノード名を直接指定）を追加し、`region` が重複する
場合は `market_node` 無しでは明示 ValueError にする（黙って上書きしない）。

【Phase 6-3b（Addendum・A2）】市場内の価格解決も同じ家族のバグを持っていた——
「市場内で共通」という前提を検査せず、ループの最後の region の価格を黙って採用
していた。本改修で `price_local` は `internal_ratio` による加重平均にし、`ccy`
（通貨）が市場内で混在していたら明示 ValueError にする（黙って上書きしない）。

【Phase 6-3b（Addendum・A3/A4）】lot の物理的な単位（`sku_master.csv` の `uom`）が
市場ごとに異なりうる（`oil-global-2027` は通常の `KL` と、タンカー単位の
`KL100KBBL` が混在——CLAUDE.md L528 に記載の意図的設計）。A系統は「1つの能力
プールを複数市場が lot 単位で奪い合う」モデルであり、lot の物理的意味が市場ごとに
違えばこの前提自体が成立しない。`derive_cost_blocks(uom=...)` で単位を1種類に
絞り込めるようにし、絞り込み無しで複数単位が混在していたら ValueError にする。
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from wom.allocation.transmission import CostBlock

BASE_WEEK = "2027-W01"
BASE_FX = 150.0


def _rows(model_dir: str, fname: str) -> List[dict]:
    path = os.path.join(model_dir, fname)
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _latest_prior(rows: List[dict], week_key: str, base_week: str) -> dict:
    cand = [r for r in rows if r[week_key] <= base_week]
    return max(cand, key=lambda r: r[week_key]) if cand else max(rows, key=lambda r: r[week_key])


def derive_cost_blocks(model_dir: str, base_week: str = BASE_WEEK,
                       base_fx: float = BASE_FX,
                       level: str = "market",
                       uom: Optional[str] = None,
                       require_full_path: bool = True,
                       incomplete_paths: Optional[List[str]] = None,
                       ) -> Tuple[Dict[str, CostBlock], float]:
    """(market -> CostBlock, transfer_price_usd) を返す。

    Args:
        level: "market"（既定）— `ga_market_aggregation.csv` の `market_group` で
               集約した従来どおりのブロック（既存の全呼び出しは無変更で通る・C8）。
               "region" — 集約せず、`region` を1市場として返す（Phase 6-3・
               `build_hierarchy()` / `aggregate_block()` の検証に使う。
               `internal_ratio` は同一グループ内での重みなので、1市場1行に
               なれば重み1になり、集約規則自体は変わらない）。
        uom: lot の物理単位（`sku_master.csv` の `uom` 列）で市場を絞り込む
             （Phase 6-3b・Addendum A4）。既定 None：モデル内の `uom` が1種類
             ならそのまま返す（soysauce 等・C8で挙動不変）。2種類以上あれば
             絞り込みを促す ValueError。"KL" 等を指定すると、その `uom` の
             SKU に属する市場だけを返す。
        require_full_path: leaf から上流への経路が1ホップも無い（コスト表にも
             outbound sc_tree にも上流が無い）市場が見つかったとき、既定 True
             では ValueError で止める（A9-6.3・「黙ってゼロ原価を返さない」）。
             False にすると止めずに続行し（原価は mat_usd のみのゼロ相当で
             構成される・旧来の黙った挙動と同じ結果になる）、到達できなかった
             leaf_out ノード名を `incomplete_paths`（渡されていれば）に追記する。
        incomplete_paths: `require_full_path=False` のときに使う out 引数。
             呼び出し側がリストを渡すと、到達できなかった leaf_out ノード名が
             そこに追記される（返り値のタプル形は変えない・呼び出し互換のため）。
    """
    if level not in ("market", "region"):
        raise ValueError(f"derive_cost_blocks(): level must be 'market' or 'region', got {level!r}")

    # --- CSV 読み込み ---
    agg = _rows(model_dir, "ga_market_aggregation.csv")
    node_rows = _rows(model_dir, "ppc_node_cost_rule.csv")
    edge_rows = _rows(model_dir, "ppc_edge_cost_rule.csv")
    sup_rows = _rows(model_dir, "ppc_supplier_cost.csv")
    tar_rows = _rows(model_dir, "ppc_tariff_rule.csv")
    price_rows = _rows(model_dir, "ppc_market_price.csv")
    sct_rows = _rows(model_dir, "sc_tree_master.csv")
    sku_rows = _rows(model_dir, "sku_master.csv")
    tp_rows = _rows(model_dir, "ppc_transfer_price_rule.csv")

    # node_id -> {currency: amount}
    node_cost: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in node_rows:
        node_cost[r["node_id"]][r["currency"]] += float(r["fixed_amount"])
    # edge_id -> {currency: amount}
    edge_cost: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in edge_rows:
        edge_cost[r["edge_id"]][r["currency"]] += float(r["fixed_amount"])
    # フロー先行ノード（"A->B" → pred[B]=A）。コスト表（ppc_edge_cost_rule.csv）
    # が正典で、流れの向きをここから決める。
    pred: Dict[str, str] = {}
    for eid in edge_cost:
        a, b = eid.split("->")
        pred[b] = a

    # node_name -> node_type（sc_tree_master.csv 全行。A9-6.2 の畳みエッジ判定に使う）
    node_type_of: Dict[str, str] = {r["node_name"]: r["node_type"] for r in sct_rows}

    # A9-6.1: outbound 側の sc_tree で、pred に無い子だけを補う。
    # コスト行が全区間に存在するモデル（soysauce）ではこの追加は何も補わない
    # （実測: 0本）。効くのは「経路はあるがコスト行が無い区間」を持つモデル
    # （oil-global-2027: Tank_*->Retail_* が21本、実測確認済み）だけである。
    # side=="outbound" に限る——inbound 側は親子が流れと逆を向いており
    # （例: soysauce の Materials_JP(leaf_in) の parent_node は Brewing_Noda）、
    # 素朴に辿ると製造原価を取りこぼし、コスト表と混ぜると二重計上する（実測確認済み）。
    # すでに pred にある子は上書きしない（コスト表が正典）。
    for r in sct_rows:
        if r.get("side") != "outbound":
            continue
        child, parent = r["node_name"], r["parent_node"]
        if parent and child not in pred:
            pred[child] = parent

    # region -> leaf_out node（重複検出つき、V6.1）。
    # `region` は必ずしも一意ではない（同じ地域に複数の販路を持つモデルがある）ため、
    # 最初の1件だけを覚えて黙って上書きするのではなく、重複を dup_regions に記録し、
    # resolve_leaf() が `market_node` 列無しでの解決を明示的に拒否する。
    leaf_names: Set[str] = set()
    leaf_of_region: Dict[str, str] = {}
    region_leaf_list: Dict[str, List[str]] = defaultdict(list)
    for r in sct_rows:
        if r["node_type"] != "leaf_out":
            continue
        leaf_names.add(r["node_name"])
        region_leaf_list[r["region"]].append(r["node_name"])
        leaf_of_region[r["region"]] = r["node_name"]
    dup_regions = {region for region, leaves in region_leaf_list.items() if len(leaves) > 1}

    def resolve_leaf(row: dict) -> str:
        """ga_market_aggregation.csv の1行から leaf_out ノード名を決める。

        解決は `market_node` 列（任意）> `region` 列の順。`region` が複数の
        `leaf_out` を指す場合、`market_node` 無しでは黙って上書きせず ValueError
        にする（V6.1）。`market_node` 列を持たない CSV（soysauce 等）では
        `.get()` が None を返すため、重複が無い限り挙動は完全に不変（C8）。
        """
        node = (row.get("market_node") or "").strip()
        if node:
            if node not in leaf_names:
                raise ValueError(
                    f"ga_market_aggregation.csv: market_node {node!r} "
                    f"(market_group={row.get('market_group')!r}) is not a leaf_out "
                    f"node in sc_tree_master.csv"
                )
            return node
        region = row["region"]
        if region in dup_regions:
            raise ValueError(
                f"ga_market_aggregation.csv: region {region!r} maps to multiple "
                f"leaf_out nodes {sorted(region_leaf_list[region])!r} "
                f"(market_group={row.get('market_group')!r}). Add a market_node "
                f"column to ga_market_aggregation.csv to disambiguate."
            )
        if region not in leaf_of_region:
            raise ValueError(f"ga_market_aggregation.csv: unknown region {region!r}")
        return leaf_of_region[region]

    # --- A4: uom（lot の物理単位）で市場を絞り込む ---
    # leaf_out ノード名 -> sku_id（product_name）。sku_id -> uom（sku_master.csv、
    # 同一 sku_id 内で複数行あっても uom は共通のはずなので最初の1件を採る）。
    leaf_to_sku: Dict[str, str] = {r["node_name"]: r["product_name"]
                                   for r in sct_rows if r["node_type"] == "leaf_out"}
    sku_to_uom: Dict[str, str] = {}
    for r in sku_rows:
        sku_to_uom.setdefault(r["sku_id"], r["uom"])

    group_key = "region" if level == "region" else "market_group"

    def row_uom(row: dict) -> str:
        leaf = resolve_leaf(row)
        sku = leaf_to_sku.get(leaf)
        if sku is None:
            raise ValueError(
                f"ga_market_aggregation.csv: leaf_out {leaf!r} has no matching row "
                f"in sc_tree_master.csv"
            )
        u = sku_to_uom.get(sku)
        if u is None:
            raise ValueError(f"sku_master.csv: unknown uom for sku_id {sku!r}")
        return u

    row_uoms = [row_uom(r) for r in agg]
    distinct_uoms = sorted(set(row_uoms))

    if uom is None:
        if len(distinct_uoms) > 1:
            counts: Dict[str, Set[str]] = defaultdict(set)
            for r, u in zip(agg, row_uoms):
                counts[u].add(r[group_key])
            opts = " or ".join(f"uom={u!r} ({len(counts[u])} markets)" for u in distinct_uoms)
            raise ValueError(
                f"derive_cost_blocks(): model has markets in {len(distinct_uoms)} "
                f"different lot units {distinct_uoms}; an allocation problem must use "
                f"a single unit (spec v0r5 §2.4). Pass {opts}."
            )
        filtered_agg = agg                     # 単一 uom: 絞り込み無し（C8）
    else:
        if uom not in distinct_uoms:
            raise ValueError(
                f"derive_cost_blocks(): uom={uom!r} not found in this model; "
                f"available: {distinct_uoms}"
            )
        filtered_agg = [r for r, u in zip(agg, row_uoms) if u == uom]

    # A9-2: transfer_price_usd / mat_usd を「絞り込み後の SKU 集合」から導出する。
    # 旧実装は sku_rows[0] / sup_rows の先頭一致というモデル全体で唯一の値を
    # 使っており、uom で絞り込んでもこの前提の外側にあった（oil の
    # uom="KL100KBBL" 側に Gasoline_Local の unit_cost が紛れ込む）。
    # 【まだ残る前提】この修正は uom 単位までの改善であり、1つの uom グループに
    # 複数 SKU が混在する場合（oil の uom="KL" は6 SKU）は、なお「最初に一致した
    # 行」を代表として使う——transfer_price_usd の導出自体が「モデル全体で
    # 1 SKU」を仮定した設計であり（soysauce はこれで正しく動く）、SKU 跨ぎの
    # 移転価格は本修正でも解決していない（Phase 6-3c Addendum A9-2 申し送り）。
    filtered_skus = {leaf_to_sku[resolve_leaf(r)] for r in filtered_agg}

    # 経路上の関税照合表（A9-6.2）
    tariff_of_edge = {r["edge_id"]: float(r["tariff_rate"]) for r in tar_rows}
    # leaf_out node -> (price, currency)
    price_by_market_node = {r["market_node"]: (float(r["market_price"]), r["currency"])
                            for r in price_rows}
    # 原料 base（USD）: 絞り込み後の SKU に属する行だけから latest-prior
    sup_rows_in_scope = [r for r in sup_rows if r["product_id"] in filtered_skus]
    if not sup_rows_in_scope:
        raise ValueError(
            f"ppc_supplier_cost.csv: no rows for sku_id in {sorted(filtered_skus)}"
        )
    mat_usd = float(_latest_prior(sup_rows_in_scope, "week", base_week)["purchase_price"])
    # 移転価格（USD）: 絞り込み後の SKU に属する行だけから先頭一致
    sku_rows_in_scope = [r for r in sku_rows if r["sku_id"] in filtered_skus]
    if not sku_rows_in_scope:
        raise ValueError(f"sku_master.csv: no rows for sku_id in {sorted(filtered_skus)}")
    unit_cost_jpy = float(sku_rows_in_scope[0]["unit_cost"])
    margin_rate = float(tp_rows[0]["margin_rate"])
    transfer_price_usd = (unit_cost_jpy / base_fx) * (1.0 + margin_rate)

    def leaf_block(leaf: str):
        """1 leaf_out の通貨別コストブロック・関税率・販売条件・到達ホップ数。

        A9-6.2: 関税は「leaf 直前の1エッジ」ではなく経路上の全エッジ（＋
        supply_point を1つ飛ばした畳みエッジ）を関税表に照合する（課税点は
        国境であって leaf の直前とは限らないため）。ヒットが2件以上なら
        課税点が一意に決まらないので ValueError。

        A9-6.3: 1ホップも遡れない（コスト表にも outbound sc_tree にも上流が
        無い）場合は hops=0 を返す。呼び出し側が require_full_path に従って
        処理する。
        """
        blk = defaultdict(float)          # currency -> amount（関税前）
        cur = leaf
        hops = 0
        candidate_edges: List[str] = []
        while cur in pred:
            a = pred[cur]
            eid = f"{a}->{cur}"
            candidate_edges.append(eid)
            # 畳みエッジ: a が supply_point ノードなら、その親を飛ばしたエッジも
            # 関税表の照合候補に含める（PPC の "MOM->first_DAD" 規約に合わせる）。
            if node_type_of.get(a) == "supply_point" and a in pred:
                candidate_edges.append(f"{pred[a]}->{cur}")
            for ccy, amt in edge_cost.get(eid, {}).items():
                blk[ccy] += amt
            for ccy, amt in node_cost.get(cur, {}).items():
                blk[ccy] += amt
            cur = a
            hops += 1
        # ルート（例: Materials_JP）のノード費
        for ccy, amt in node_cost.get(cur, {}).items():
            blk[ccy] += amt
        blk["USD"] += mat_usd             # 原料

        hits = sorted({tariff_of_edge[e] for e in candidate_edges if e in tariff_of_edge})
        if len(hits) > 1:
            raise ValueError(
                f"leaf {leaf!r}: multiple tariff rows on the path {candidate_edges} "
                f"({hits}); ambiguous taxation point"
            )
        trate = hits[0] if hits else 0.0

        price, pccy = price_by_market_node[leaf]
        return blk, trate, price, pccy, hops

    # 市場（level="market"）または地域（level="region"）ごとに集約
    by_group: Dict[str, List[dict]] = defaultdict(list)
    for r in filtered_agg:
        by_group[r[group_key]].append(r)

    result: Dict[str, CostBlock] = {}
    for group, regs in by_group.items():
        tot_ratio = sum(float(r["internal_ratio"]) for r in regs)
        usd = eur = jpy = trate = price = 0.0
        ccys_seen: Set[str] = set()
        demand = 0
        for r in regs:
            leaf = resolve_leaf(r)
            w = float(r["internal_ratio"]) / tot_ratio
            blk, tr, pr, pc, hops = leaf_block(leaf)
            if hops == 0:
                # A9-6.3: 黙ってゼロ原価を返さない。ppc_edge_cost_rule.csv にも
                # outbound sc_tree にも上流が無い leaf は、コストが全く積まれて
                # いない（mat_usd のみ）まま通ってしまう——region 重複の
                # サイレント上書き（V6.1）・価格の最後勝ち（A2）と同じ家族の欠陥。
                if require_full_path:
                    raise ValueError(
                        f"leaf {leaf!r} has no upstream edge: neither "
                        f"ppc_edge_cost_rule.csv nor the outbound sc_tree links it "
                        f"to a parent. The cost block would be all-zero (mat_usd "
                        f"only). Pass require_full_path=False to proceed anyway."
                    )
                if incomplete_paths is not None:
                    incomplete_paths.append(leaf)
            usd += w * blk.get("USD", 0.0)
            eur += w * blk.get("EUR", 0.0)
            jpy += w * blk.get("JPY", 0.0)
            trate += w * tr
            price += w * pr               # A2: 加重平均（「市場内で共通」を検査せず
                                           # 最後の1件を黙って採るバグを修正）
            ccys_seen.add(pc)
            demand += int(r["base_qty_lot"])
        if len(ccys_seen) != 1:
            raise ValueError(
                f"ga_market_aggregation.csv: market_group {group!r} mixes currencies "
                f"{sorted(ccys_seen)} — a group must be currency-uniform."
            )
        ccy = next(iter(ccys_seen))
        result[group] = CostBlock(
            usd=round(usd, 6), eur=round(eur, 6), jpy=round(jpy, 6),
            tariff_rate=round(trate, 6), price_local=round(price, 6), ccy=ccy,
            demand_qty=demand, material_usd_base=mat_usd)
    return result, transfer_price_usd

````
