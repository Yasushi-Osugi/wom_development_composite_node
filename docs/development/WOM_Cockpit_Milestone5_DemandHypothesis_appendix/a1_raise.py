# 到達点 5 A1：増産の確保費の行（有償の週 ＝ 引き上げた週の範囲、週額は空欄、表示名「増産の確保費」）
import sys
sys.path.insert(0, ".")
from wom.cockpit import case_actions as A
from wom.cockpit import compare_view_model as V

W = "output/cockpit_m5/cos"
mode = sys.argv[1]
if mode == "helper":                    # C02・C03：手助けの「親より上げた週」（親 C01、入力で比べる）
    for cid in ("C02", "C03"):
        c = [x for x in A.raise_week_candidates(W, cid) if x["kind"] == "raised" and x["sku"] == "COS_Cream"]
        assert len(c) == 1, c
        r = A.apply_raise_weeks(W, cid, c[0], "E_JP", "JPY")
        print(cid, r.ok, r.message)
elif mode == "c07":                     # C07：引き上げた週の全体 2027-W50〜2029-W46（親 C05 からの差 13 週ではなく）
    rows = [{"cost_item": f["cost_item"], "display_name": f["display_name"], "entity": f["entity"],
             "paid_start_week": "2027-W50" if f["cost_item"] == A.RAISE_ITEM else f["paid_start_week"],
             "paid_end_week": f["paid_end_week"], "weekly_amount": f["weekly_amount_raw"], "currency": f["currency"],
             "count_outside_report": f["count_outside_report"],
             "note": ("有償の週は COS_Cream の計画の生産量を C01 より上げた週 2027-W50〜2029-W46（11→12（cap_soft））"
                      if f["cost_item"] == A.RAISE_ITEM else f["note"])}
            for f in V.case_inputs(W, "C07")["fixed_cost"]]
    r = A.set_fixed_cost(W, "C07", rows)
    print("C07", r.ok, r.message)
