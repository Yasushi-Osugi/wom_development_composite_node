# -*- coding: utf-8 -*-
"""Assemble the report and appendix from the generated tables.
    python output/bsseaf_cosmetics/cap_work/assemble.py <names result> <end HH:MM> <minutes text>
"""
import os
import re
import shutil
import sys

W = "output/bsseaf_cosmetics/cap_work"
COS = "output/bsseaf_cosmetics"
D = "docs/development"
NAME = "WOM_BSSEAF_Cosmetics_CapacityAwareWeekRule_U4"
A = f"{D}/{NAME}_appendix"
t = open(W + "/report_tables.md", encoding="utf-8").read()
m = re.search(r"### まとめの表\n\n(.*?)\n\n(### T1.*)", t, re.S)
s = open(W + "/report_template.md", encoding="utf-8").read()
s = s.replace("{T_SUMMARY}", m.group(1)).replace("{T_REST}", m.group(2).rstrip())
s = s.replace("{NAMES}", sys.argv[1]).replace("{T_END}", sys.argv[2]).replace("{T_END_D}", sys.argv[3])
left = re.findall(r"\{[A-Z_]+\}", s)
assert not left, left
open(f"{D}/{NAME}_Report.md", "w", encoding="utf-8", newline="\n").write(s)
for sub in ("udp", "scripts", "records"):
    os.makedirs(f"{A}/{sub}", exist_ok=True)
for case, rule in (("U4_A0e_r2", "proportional_even"), ("U4_A3", "trim_to_capacity_latest")):
    src, dst = f"{COS}/udp/{case}_{rule}", f"{A}/udp/{case}"
    os.makedirs(dst, exist_ok=True)
    for f in ("udp_selection_ledger.csv", "udp_result_by_request.csv", "udp_capacity_check.csv", "udp_supply_runs.csv", "udp_plan.json"):
        shutil.copyfile(f"{src}/{f}", f"{dst}/{f}")
for f in ("pre_checks.py", "run_trial.py", "measure.py", "assemble.py"):
    shutil.copyfile(f"{W}/{f}", f"{A}/scripts/{f}")
for f in ("pre_checks.json", "measure.json", "t2_all.csv"):
    shutil.copyfile(f"{W}/{f}", f"{A}/records/{f}")
with open(f"{A}/README.md", "w", encoding="utf-8", newline="\n") as f:
    f.write(f"""# 付録：BS-SEAF 化粧品 U4 能力に合わせて減らす週を選ぶ規則の再現用データ

本報告：`docs/development/{NAME}_Report.md`。

- `udp/<案>/`：選択の台帳、要求週ごとの結果、時間の可否の診断、供給 0 の連続、`udp_plan.json`。
- `records/t2_all.csv`：A0e・A3 の要求週ごとの全期間の結果。A0・A1 は `WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4_appendix/records/t2_all.csv`。
- `records/pre_checks.json`：B1・B2 と試行の前の参考値。`records/measure.json`：B3・T8 の確かめと集計。
- `scripts/`：`output/bsseaf_cosmetics/cap_work/` に置いて、リポジトリの根から `pre_checks.py`、`run_trial.py`、`measure.py` の順に実行する。C3a の写し、U4 の作業フォルダ（`U4_A0` など、年齢の要約）、P2-a の付録の `make_allocation.py` と `evaluation.json` を `p2a_work/` に要する。

金額は架空の仮定。評価の額は配分を比べるための比較値で、営業利益ではない。
""")
print("ok", len(s.splitlines()))
