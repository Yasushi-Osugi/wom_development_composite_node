# -*- coding: utf-8 -*-
"""
wom/strategy/overflow.py — 工場の押し戻しの記録（工場 × 市場）。エンジンは変えない
=================================================================================
RequestLetter_Promo_Convert_Slice1 §5。

Backward が工場（MOM）の能力を超えた lot を前の週へ押し戻した数を、工場 × 市場（Lot_ID の region）で数える。
数えるのはエンジン自身（BackwardPlanResult.overflow_by_node、RequestLetter_M6_RowOrder_Stage1）。ここでは
headless（tools.run_headless_from_folder.run、PPC なし）を 1 回回し、BackwardPlanner.run の戻り値を
包んで受け取るだけ（段 0 の調査のスクリプトと同じ包み方。エンジンのファイルは変えない）。
"""
from __future__ import annotations

import os
import sys
import tempfile
from typing import Dict


def overflow_by_factory(model_dir: str, plugins_spec: str) -> dict:
    """{"policy": …, "by_product": {product: {factory: {market: {"pushed": n, "denominator": n}}}},
    "pushed_total": n}. Runs the plan once (no PPC)."""
    from wom.cockpit import cases as C
    if C.REPO not in sys.path:
        sys.path.insert(0, C.REPO)
    import wom.engine.backward_planner as BPm
    from tools.run_headless_from_folder import run as headless_run
    rec: Dict[str, dict] = {}
    policy = {}
    orig = BPm.BackwardPlanner.run

    def wrapped(self, prod_nm, *a, **k):
        res = orig(self, prod_nm, *a, **k)
        rec[prod_nm] = {n: {m: dict(v) for m, v in mk.items()} for n, mk in (res.overflow_by_node or {}).items()}
        policy[prod_nm] = res.overflow_policy
        return res

    BPm.BackwardPlanner.run = wrapped
    try:
        with tempfile.TemporaryDirectory() as td:
            headless_run(model_dir, plugins_spec=plugins_spec, output_ppc_dir=os.path.join(td, "ppc"),
                         verbose=False, ppc=False)
    finally:
        BPm.BackwardPlanner.run = orig
    total = sum(v["pushed"] for f in rec.values() for mk in f.values() for v in mk.values())
    return {"policy": sorted(set(policy.values())), "by_product": rec, "pushed_total": total}


def rows(rec: dict, case: str) -> list:
    """One row per case x product x factory x market (pushed > 0 or not)."""
    out = []
    for prod, facs in sorted(rec["by_product"].items()):
        for fac, mk in sorted(facs.items()):
            for m, v in sorted(mk.items()):
                out.append({"case": case, "policy": ",".join(rec["policy"]), "product": prod, "factory": fac,
                            "market": m, "pushed": v["pushed"], "denominator": v["denominator"]})
    return out
