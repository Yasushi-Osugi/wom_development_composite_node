# 段 4 B2：増産の確保費の行を、手助けの候補から入れる（C02 = 実測の候補、C03 = 親より上げた週の候補）
import json, sys
sys.path.insert(0, ".")
from wom.cockpit import case_actions as A
W = "output/cockpit_step4/cos"
for cid, kind in (("C02", "measured"), ("C03", "raised")):
    cands = A.raise_week_candidates(W, cid)
    print(cid, "候補:", json.dumps(cands, ensure_ascii=False))
    c = [x for x in cands if x["kind"] == kind and x["sku"] == "COS_Cream"][0]
    r = A.apply_raise_weeks(W, cid, c, "E_JP", "JPY")
    print(" ", r.ok, r.message)
