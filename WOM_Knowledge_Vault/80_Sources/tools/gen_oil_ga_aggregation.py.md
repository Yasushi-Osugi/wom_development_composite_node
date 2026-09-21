---
tags: [wom, code]
---
# tools/gen_oil_ga_aggregation.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/tools/gen_oil_ga_aggregation.py) · [原文テキスト](../../90_Raw/tools/gen_oil_ga_aggregation.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## モジュール説明（docstring原文）

```text
tools/gen_oil_ga_aggregation.py — ga_market_aggregation.csv の生成器（Phase 6-3・V6.2）
==========================================================================================
`sc_tree_master.csv` の `leaf_out`（`oil-global-2027` では21件）と `demand_forecast.csv`
（sku_id × region × week）から、A系統（`ask_global_allocation`）用の
`ga_market_aggregation.csv` を機械生成する。

正典: requests/Phase6-3_RequestLetter_to_CodeKun.md V6.2
      requests/Phase6-3b_Addendum_to_CodeKun.md A5（uom 駆動への改修）
      requests/Phase6-3b_Addendum_to_CodeKun.md A8（絞り込みは derive_cost_blocks()
      の1箇所だけで行う方針に訂正——本ファイルはもう絞り込まない）

設計判断:
  - `market_group` / `market_node` は `leaf_out` ノード名そのもの（1市場1グループ、
    `internal_ratio` は常に 1.0000）。`oil-global-2027` は複数の `leaf_out` が
    同じ `region`（KANTO/KANSAI/CHUBU が3供給ラインぶん重複）を共有するため、
    `market_node` 列で明示する（`cost_block.py` の `resolve_leaf()` が
    `market_node` > `region` の優先順で解決し、重複 `region` を `market_node` 無しで
    引こうとしたら例外にする——V6.1 で別途保証済み）。
  - `base_qty_lot` は `demand_forecast.csv` を (sku_id, region) で全期間合計する
    （soysauce の既存 `ga_market_aggregation.csv` の値が同じ集計方法で作られている
    ことを実測で確認済み）。(sku_id, region) が leaf_out に一意に紐づかない場合は
    例外にして報告する——数字を作らない。
  - **`--uom`（既定 None＝絞り込まない）**（A8）。当初案（A5）は生成時に単一 uom へ
    絞り込んでいたが、これは絞り込みが「生成時」と「`derive_cost_blocks(uom=...)`
    の読み取り時」の2箇所に分かれ、生成時の絞り込みが読み取り時のガード
    （複数 uom 混在を検出する ValueError）を黙って無効化してしまっていた
    （A8 で訂正）。**絞り込みは `derive_cost_blocks(uom=...)` の1箇所だけで行う。**
    本スクリプトは既定で全 leaf_out を書き出し、`note` 列に**その行自身の**
    `uom` を記録する（A9-1。CLI 引数の値を全行に書くと、絞り込みを外した
    途端に嘘になるため）。`--uom` を明示すればなお絞り込めるが（他用途向けに
    残す）、`data/sample/oil-global-2027/ga_market_aggregation.csv` の既定生成物は
    21行すべてを含む。
  - 生成はスクリプトで行い、手書きの行をコミットしない。`ev-thailand-2026` 等
    他のケースも同じ1本（本スクリプトのロジック）を使い回せる見込み。

使い方（リポジトリ直下）:
  python -m tools.gen_oil_ga_aggregation --model-dir data/sample/oil-global-2027
  python -m tools.gen_oil_ga_aggregation --model-dir <dir> --uom KL100KBBL   # 絞り込みたい場合のみ
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_rows` | 54 | docstringなし（下のコード参照） |
| FunctionDef | `generate` | 59 | (sku_id, region) を鍵に demand_forecast.csv を集計し、leaf_out 1件=1行の |
| FunctionDef | `write_csv` | 129 | docstringなし（下のコード参照） |
| FunctionDef | `main` | 136 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/requests/Phase6-3_RequestLetter_to_CodeKun.md|requests/Phase6-3_RequestLetter_to_CodeKun.md]]
- [[80_Sources/requests/Phase6-3b_Addendum_to_CodeKun.md|requests/Phase6-3b_Addendum_to_CodeKun.md]]

## 全文（コメント・原文を省略せず収録）

````python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/gen_oil_ga_aggregation.py — ga_market_aggregation.csv の生成器（Phase 6-3・V6.2）
==========================================================================================
`sc_tree_master.csv` の `leaf_out`（`oil-global-2027` では21件）と `demand_forecast.csv`
（sku_id × region × week）から、A系統（`ask_global_allocation`）用の
`ga_market_aggregation.csv` を機械生成する。

正典: requests/Phase6-3_RequestLetter_to_CodeKun.md V6.2
      requests/Phase6-3b_Addendum_to_CodeKun.md A5（uom 駆動への改修）
      requests/Phase6-3b_Addendum_to_CodeKun.md A8（絞り込みは derive_cost_blocks()
      の1箇所だけで行う方針に訂正——本ファイルはもう絞り込まない）

設計判断:
  - `market_group` / `market_node` は `leaf_out` ノード名そのもの（1市場1グループ、
    `internal_ratio` は常に 1.0000）。`oil-global-2027` は複数の `leaf_out` が
    同じ `region`（KANTO/KANSAI/CHUBU が3供給ラインぶん重複）を共有するため、
    `market_node` 列で明示する（`cost_block.py` の `resolve_leaf()` が
    `market_node` > `region` の優先順で解決し、重複 `region` を `market_node` 無しで
    引こうとしたら例外にする——V6.1 で別途保証済み）。
  - `base_qty_lot` は `demand_forecast.csv` を (sku_id, region) で全期間合計する
    （soysauce の既存 `ga_market_aggregation.csv` の値が同じ集計方法で作られている
    ことを実測で確認済み）。(sku_id, region) が leaf_out に一意に紐づかない場合は
    例外にして報告する——数字を作らない。
  - **`--uom`（既定 None＝絞り込まない）**（A8）。当初案（A5）は生成時に単一 uom へ
    絞り込んでいたが、これは絞り込みが「生成時」と「`derive_cost_blocks(uom=...)`
    の読み取り時」の2箇所に分かれ、生成時の絞り込みが読み取り時のガード
    （複数 uom 混在を検出する ValueError）を黙って無効化してしまっていた
    （A8 で訂正）。**絞り込みは `derive_cost_blocks(uom=...)` の1箇所だけで行う。**
    本スクリプトは既定で全 leaf_out を書き出し、`note` 列に**その行自身の**
    `uom` を記録する（A9-1。CLI 引数の値を全行に書くと、絞り込みを外した
    途端に嘘になるため）。`--uom` を明示すればなお絞り込めるが（他用途向けに
    残す）、`data/sample/oil-global-2027/ga_market_aggregation.csv` の既定生成物は
    21行すべてを含む。
  - 生成はスクリプトで行い、手書きの行をコミットしない。`ev-thailand-2026` 等
    他のケースも同じ1本（本スクリプトのロジック）を使い回せる見込み。

使い方（リポジトリ直下）:
  python -m tools.gen_oil_ga_aggregation --model-dir data/sample/oil-global-2027
  python -m tools.gen_oil_ga_aggregation --model-dir <dir> --uom KL100KBBL   # 絞り込みたい場合のみ
"""
from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

FIELDNAMES = ["market_group", "region", "market_node", "internal_ratio", "base_qty_lot", "note"]


def _rows(model_dir: str, fname: str) -> List[dict]:
    with open(os.path.join(model_dir, fname), "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def generate(model_dir: str, uom: Optional[str] = None) -> List[dict]:
    """(sku_id, region) を鍵に demand_forecast.csv を集計し、leaf_out 1件=1行の
    ga_market_aggregation.csv 相当の行リストを返す（書き出しはしない）。

    `uom`（既定 None）を指定しない限り絞り込まない——単位の絞り込みは
    `derive_cost_blocks(uom=...)` の役割であり（A8）、本関数は事実（どの
    leaf_out がどの uom に属するか）を `note` 列に記録するだけである。
    `uom` を明示した場合のみ、一致しない leaf_out を除外し件数を報告する
    （他用途向けに残す。既定の生成物では使わない）。
    """
    sct_rows = _rows(model_dir, "sc_tree_master.csv")
    dem_rows = _rows(model_dir, "demand_forecast.csv")
    sku_rows = _rows(model_dir, "sku_master.csv")

    leaves = [r for r in sct_rows if r["node_type"] == "leaf_out"]
    if not leaves:
        raise ValueError(f"{model_dir}: sc_tree_master.csv has no leaf_out rows")

    sku_to_uom: Dict[str, str] = {}
    for r in sku_rows:
        sku_to_uom.setdefault(r["sku_id"], r["uom"])

    qty_by_key: Dict[Tuple[str, str], float] = defaultdict(float)
    for r in dem_rows:
        qty_by_key[(r["sku_id"], r["region"])] += float(r["quantity"])

    seen_keys: set = set()
    out_rows: List[dict] = []
    excluded_by_uom: Dict[str, int] = defaultdict(int)
    for r in leaves:
        sku = r["product_name"]
        leaf_uom = sku_to_uom.get(sku)
        if leaf_uom is None:
            raise ValueError(
                f"gen_oil_ga_aggregation: sku_master.csv has no uom for sku_id "
                f"{sku!r} (leaf_out {r['node_name']!r})"
            )
        if uom is not None and leaf_uom != uom:
            excluded_by_uom[leaf_uom] += 1
            continue

        key = (sku, r["region"])
        if key in seen_keys:
            raise ValueError(
                f"gen_oil_ga_aggregation: duplicate (sku_id, region) {key!r} across "
                f"leaf_out nodes — cannot derive a unique base_qty_lot. Fix "
                f"sc_tree_master.csv before regenerating."
            )
        seen_keys.add(key)
        if key not in qty_by_key:
            raise ValueError(
                f"gen_oil_ga_aggregation: demand_forecast.csv has no rows for "
                f"sku_id={key[0]!r} region={key[1]!r} (leaf_out {r['node_name']!r}). "
                f"Refusing to write a row with a fabricated base_qty_lot."
            )
        base_qty = qty_by_key[key]
        out_rows.append({
            "market_group": r["node_name"],
            "region": r["region"],
            "market_node": r["node_name"],
            "internal_ratio": "1.0000",
            "base_qty_lot": str(int(round(base_qty))),
            "note": f"uom={leaf_uom}",   # A9-1: その行自身の uom（CLI 引数ではない）
        })

    for excl_uom, n in excluded_by_uom.items():
        print(f"[gen_oil_ga_aggregation] {n} rows excluded: uom={excl_uom}")
    return out_rows


def write_csv(rows: List[dict], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate ga_market_aggregation.csv from sc_tree_master.csv + "
                    "demand_forecast.csv. Writes all leaf_out rows by default; "
                    "uom filtering happens at derive_cost_blocks(uom=...) read time, "
                    "not here (Phase 6-3 V6.2 / Addendum A5 -> A8).")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--uom", default=None,
                    help="lot の物理単位（sku_master.csv の uom 列）で絞り込む。"
                         "既定は絞り込まない（全 leaf_out を書く）")
    ap.add_argument("--out", default=None,
                    help="既定: <model-dir>/ga_market_aggregation.csv")
    a = ap.parse_args(argv)

    rows = generate(a.model_dir, uom=a.uom)
    out = a.out or os.path.join(a.model_dir, "ga_market_aggregation.csv")
    write_csv(rows, out)
    uom_desc = a.uom if a.uom is not None else "all"
    print(f"[gen_oil_ga_aggregation] wrote {len(rows)} rows (uom={uom_desc}) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

````
