# 段 4（シフト・地域）B2-6：追加シフトの確保費の行を、手助けの「シフトを引き上げた週」から入れる
import json, sys
sys.path.insert(0, ".")
from wom.cockpit import case_actions as A
W = "output/cockpit_step4b/soy"
cands = A.raise_week_candidates(W, "C02")
print("候補:", json.dumps(cands, ensure_ascii=False))
c = [x for x in cands if x["kind"] == "raised" and x["factory"] == "Bottling_Noda"]
assert len(c) == 1, c
r = A.apply_raise_weeks(W, "C02", c[0], "E_JP", "JPY", display_name="追加シフトの確保費")
print(r.ok, r.message)
