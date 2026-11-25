# -*- coding: utf-8 -*-
"""投入週の 1 本目 §3.2：C04・C05 の費用の前提に増産の確保費（全期間の有償週、中 40,000 円／週。仮置き）。
有償の週は作業の需要の期間（＝計画の全週。助走を含む）、count_outside_report=1（報告期間の外の週も数える）。"""
import os, sys
sys.path.insert(0, os.getcwd())
from wom.cockpit import cases as C
W = "output/strategy_launch1/ws"
ws = C.open_workspace(W)
a, b = ws["demand_period"]["start"], ws["demand_period"]["end"]
for cid in ("C04", "C05"):
    C.set_fixed_cost(W, cid, rows=[{
        "cost_item": "planned_output_raise", "entity": "E_JP", "paid_start_week": a, "paid_end_week": b,
        "weekly_amount": "40000", "currency": "JPY", "count_outside_report": "1", "display_name": "増産の確保費",
        "note": "有償の週は COS_Cream の計画の生産量を 11→12（cap_soft）に上げた全期間（助走を含む）。中 40,000 円／週は "
                "GPT-MC 見積もりの全期間の仮置き（採用額ではない）。低 10,000・高 132,000 は算術で当てる"}])
    print(cid, a, b)
