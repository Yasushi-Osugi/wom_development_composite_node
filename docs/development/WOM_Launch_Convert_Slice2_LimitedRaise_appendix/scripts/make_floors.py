# -*- coding: utf-8 -*-
"""守る供給の下限：同じ投入週の全期間の案の実納品（報告期間の要求週。期間合計・2029 年）。8 つの鍵（タイのクリームを含む）。
    python output/strategy_launch2/make_floors.py"""
import os, sys
import pandas as pd
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
from tools import period_fulfillment as PF  # noqa: E402
W = os.path.join(REPO, "output", "strategy_launch1", "ws")
O = os.path.join(REPO, "output", "strategy_launch2")
for c, use in (("C04", "C06"), ("C05", "C07")):
    r = PF.case_tables(W, c)["req"]
    r = r[r["request_week"] >= "2027-W01"]
    g = r.groupby(["sku_id", "region"])["delivered"].sum()
    g29 = r[r["request_week"].str[:4] == "2029"].groupby(["sku_id", "region"])["delivered"].sum()
    rows = [{"sku_id": s, "market": m, "floor_lots": int(v), "floor_lots_2029": int(g29.get((s, m), 0)),
             "basis": f"{c}_actual_delivered",
             "note": f"投入週の 2 本目：{c}（同じ投入週の全期間の増産）の実納品を {use} の下限に。報告期間の要求週、期間合計・2029 年。許容 0 lot"}
            for (s, m), v in g.items()]
    pd.DataFrame(rows).to_csv(os.path.join(O, f"protect_floor_{c}.csv"), index=False, encoding="utf-8")
    print(c); print(pd.DataFrame(rows)[["sku_id", "market", "floor_lots", "floor_lots_2029"]].to_string(index=False))
