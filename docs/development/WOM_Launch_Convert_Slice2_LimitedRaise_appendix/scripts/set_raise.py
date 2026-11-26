# -*- coding: utf-8 -*-
"""投入週の 2 本目：期間を絞った増産の案の確保費の行（有償の週＝計画の生産量を引き上げた全週、40,000 円／週。仮置き）。
    python output/strategy_launch2/set_raise.py C06 2028-W11 2029-W46"""
import os, sys
sys.path.insert(0, os.getcwd())
from wom.cockpit import cases as C
W = "output/strategy_launch1/ws"
cid, a, b = sys.argv[1:4]
C.set_fixed_cost(W, cid, rows=[{
    "cost_item": "planned_output_raise", "entity": "E_JP", "paid_start_week": a, "paid_end_week": b,
    "weekly_amount": "40000", "currency": "JPY", "count_outside_report": "1", "display_name": "増産の確保費",
    "note": f"有償の週は COS_Cream の計画の生産量を 11→12（cap_soft）に上げた週 {a}〜{b}。中 40,000 円／週は割増なしの仮置き"
            "（採用額ではない）。期間を絞った割増 15% と低・高は報告書で算術で当てる"}])
print(cid, a, b)
