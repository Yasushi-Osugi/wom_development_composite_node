# -*- coding: utf-8 -*-
"""4 本目・4b：増産の案の費用の前提の planned_output_raise（既存の行は残す）。低 11,500／中 46,000 円（仮置き）。
    python output/strategy_slice4/set_raise.py low|mid"""
import os, sys
import pandas as pd
sys.path.insert(0, os.getcwd())
from wom.cockpit import cases as C
W = "output/strategy_slice3/ws"
AMT = {"low": "11500", "mid": "46000"}[sys.argv[1]]
NOTE = (f"共有応援・{'低' if sys.argv[1] == 'low' else '中'}（期間を絞った 15% 割増）。GPT-MC 見積もり v0.1 の仮置き"
        "（採用額ではない。延ばした期間でも同じ週額で確保できるかは未確認）")
END = {"C02": "2028-W17", "C04": "2028-W17", "C06": "2028-W17", "C07": "2028-W23", "C08": "2028-W29",
       "C09": "2028-W17", "C10": "2028-W17", "C11": "2028-W23", "C12": "2028-W29"}
for cid, end in END.items():
    p = os.path.join(C.case_dir(W, cid), "inputs", C.FIXED_COST_FILE)
    rows = pd.read_csv(p, dtype=str, keep_default_na=False).to_dict("records") if os.path.exists(p) else []
    rows = [r for r in rows if r["cost_item"] != "planned_output_raise"]
    rows.append({"cost_item": "planned_output_raise", "entity": "E_JP", "paid_start_week": "2028-W06",
                 "paid_end_week": end, "weekly_amount": AMT, "currency": "JPY", "note": NOTE})
    C.set_fixed_cost(W, cid, rows=rows)
    print(cid, [(r["cost_item"], r["paid_start_week"], r["paid_end_week"], r["weekly_amount"]) for r in rows])
