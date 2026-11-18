# -*- coding: utf-8 -*-
"""
tools/allocation_equal_quota.py — 重要市場を同順位にそろえる数量枠（allocation_qty_*.csv）を作る
==========================================================================================
RequestLetter_M6_R0_R1_GlobalAllocation A2（2026-11-18）。対応表 v0.1 §3.3・§3.5。

    python -m tools.allocation_equal_quota --model-dir <モデル> --sku Soy_Sauce
        --protect JP --equalize US_W,US_E,FR,BE,NL --total-a 57825 --out <フォルダ>/allocation_qty_R1.csv

- 保護する鍵（--protect）：② ＝ 元の需要（計画期間の合計）。
- 同順位の鍵（--equalize）：同順位に渡す量 Q_A を元の需要に比例して配り、最大剰余法で lot にする。
  端数の大きい順に 1 lot ずつ足し、端数が同じなら市場キー（region）の順。
- 元の需要は demand_forecast.csv の鍵（SKU × region）ごとの計画期間の合計（数量配分の alloc_lots と同じ範囲）。
- 出力の列：sku_id, region, alloc_lots（数量配分が読む 3 列）に、q1_original・group・raw_quota・
  remainder_lot・quota_source を足す（数量配分は余分な列を読まない）。

止める条件：需要がある鍵がどちらの一覧にも無い、一覧の鍵が需要に無い、同じ鍵が両方にある、
Q_A が 0 未満か同順位の鍵の需要の合計を超える。
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from fractions import Fraction
from typing import Dict, List

import pandas as pd

OUT_COLS = ["sku_id", "region", "alloc_lots", "q1_original", "group", "raw_quota", "remainder_lot", "quota_source"]


class QuotaError(ValueError):
    """The inputs cannot make the quota."""


def demand_totals(demand_csv: str, sku: str) -> Dict[str, int]:
    d = pd.read_csv(demand_csv, dtype={"week": str})
    g = d[d["sku_id"] == sku].groupby("region")["quantity"].sum()
    if g.empty:
        raise QuotaError(f"{demand_csv}: SKU {sku} の需要がありません")
    return {r: int(v) for r, v in g.items()}


def equal_priority_quota(q1: Dict[str, int], sku: str, protect: List[str], equalize: List[str],
                         total_a: int, source: str = "") -> pd.DataFrame:
    """Protected keys keep their original demand; the equal-priority keys share total_a in proportion to their
    original demand (largest remainder; ties broken by the region key order). Exact arithmetic (fractions)."""
    both = sorted(set(protect) & set(equalize))
    if both:
        raise QuotaError(f"同じ鍵が保護と同順位の両方にあります：{both}")
    unknown = sorted((set(protect) | set(equalize)) - set(q1))
    if unknown:
        raise QuotaError(f"需要に無い鍵：{unknown}（需要のある鍵：{sorted(q1)}）")
    left = sorted(k for k, v in q1.items() if v > 0 and k not in protect and k not in equalize)
    if left:
        raise QuotaError(f"需要のある鍵 {left} がどちらの一覧にもありません。直し方：--protect か --equalize に入れる")
    if not equalize:
        raise QuotaError("同順位の鍵（--equalize）がありません")
    d_a = sum(q1[k] for k in equalize)
    if total_a < 0 or total_a > d_a:
        raise QuotaError(f"同順位に渡す量 {total_a:,} は 0 以上、同順位の鍵の需要の合計 {d_a:,} 以下にする")
    raw = {k: Fraction(total_a * q1[k], d_a) if d_a else Fraction(0) for k in equalize}
    base = {k: math.floor(raw[k]) for k in equalize}
    rest = total_a - sum(base.values())
    order = sorted(equalize, key=lambda k: (-(raw[k] - base[k]), k))
    plus = set(order[:rest])
    src = source or f"equal priority: Q_A={total_a} over {','.join(sorted(equalize))} (largest remainder)"
    rows = []
    for k in sorted(q1):
        if k in protect:
            rows.append({"sku_id": sku, "region": k, "alloc_lots": q1[k], "q1_original": q1[k], "group": "protect",
                         "raw_quota": float(q1[k]), "remainder_lot": 0, "quota_source": "protect: original demand"})
        elif k in equalize:
            rows.append({"sku_id": sku, "region": k, "alloc_lots": base[k] + (1 if k in plus else 0),
                         "q1_original": q1[k], "group": "equalize", "raw_quota": round(float(raw[k]), 6),
                         "remainder_lot": 1 if k in plus else 0, "quota_source": src})
        else:                                   # a key with no demand: 0
            rows.append({"sku_id": sku, "region": k, "alloc_lots": 0, "q1_original": q1[k], "group": "none",
                         "raw_quota": 0.0, "remainder_lot": 0, "quota_source": "no demand"})
    return pd.DataFrame(rows, columns=OUT_COLS)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Equal-priority quantity quota (largest remainder)")
    ap.add_argument("--model-dir", required=True, help="model folder (its demand_forecast.csv is the original demand)")
    ap.add_argument("--sku", required=True)
    ap.add_argument("--protect", default="", help="regions kept at their original demand, comma separated")
    ap.add_argument("--equalize", required=True, help="regions on the same priority, comma separated")
    ap.add_argument("--total-a", required=True, type=int, help="lots given to the equal-priority regions")
    ap.add_argument("--out", required=True, help="allocation_qty_<id>.csv")
    a = ap.parse_args(argv)
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]
    try:
        q1 = demand_totals(os.path.join(a.model_dir, "demand_forecast.csv"), a.sku)
        t = equal_priority_quota(q1, a.sku, split(a.protect), split(a.equalize), a.total_a)
    except QuotaError as e:
        print(f"[equal_quota] 止めました: {e}", file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    t.to_csv(a.out, index=False)
    for r in t.itertuples():
        print(f"  {r.sku_id} × {r.region}：① {r.q1_original:,} → ② {r.alloc_lots:,}（{r.group}、丸め前 {r.raw_quota:,.3f}）")
    print(f"  計 ② {int(t['alloc_lots'].sum()):,}／① {int(t['q1_original'].sum()):,} -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
