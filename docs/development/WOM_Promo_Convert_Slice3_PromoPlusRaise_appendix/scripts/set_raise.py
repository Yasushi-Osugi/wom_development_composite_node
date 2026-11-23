# -*- coding: utf-8 -*-
"""段 3 §1：増産の案（C02・C04・C06）の費用の前提に planned_output_raise を足す（既存の行は残す）。
    python output/strategy_slice3/set_raise.py low|mid"""
import os, sys
import pandas as pd
sys.path.insert(0, os.getcwd())
from wom.cockpit import cases as C
W = "output/strategy_slice3/ws"
AMT = {"low": "11500", "mid": "46000"}[sys.argv[1]]
NOTE = {"low": "共有応援・低（期間を絞った 15% 割増）。GPT-MC 見積もり v0.1 の仮置き（採用額ではない）",
        "mid": "共有応援・中（期間を絞った 15% 割増）。GPT-MC 見積もり v0.1 の仮置き（採用額ではない）"}[sys.argv[1]]
for cid in ("C02", "C04", "C06"):
    p = os.path.join(C.case_dir(W, cid), "inputs", C.FIXED_COST_FILE)
    rows = pd.read_csv(p, dtype=str, keep_default_na=False).to_dict("records") if os.path.exists(p) else []
    rows = [r for r in rows if r["cost_item"] != "planned_output_raise"]
    rows.append({"cost_item": "planned_output_raise", "entity": "E_JP", "paid_start_week": "2028-W06",
                 "paid_end_week": "2028-W17", "weekly_amount": AMT, "currency": "JPY", "note": NOTE})
    C.set_fixed_cost(W, cid, rows=rows)
    print(cid, [(r["cost_item"], r["weekly_amount"]) for r in rows])
