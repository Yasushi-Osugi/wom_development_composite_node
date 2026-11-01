# -*- coding: utf-8 -*-
"""Assemble the U4 report and appendix from the generated tables."""
import os
import re
import shutil

W = "output/bsseaf_cosmetics/u4_work"
COS = "output/bsseaf_cosmetics"
D = "docs/development"
NAME = "WOM_BSSEAF_Cosmetics_UpperDemandPlan_U4"
A = f"{D}/{NAME}_appendix"
t = open(W + "/report_tables.md", encoding="utf-8").read()
m = re.search(r"### まとめの表\n\n(.*?)\n\n(### T1.*)", t, re.S)
s = open(W + "/report_template.md", encoding="utf-8").read()
s = s.replace("{T_SUMMARY}", m.group(1)).replace("{T_REST}", m.group(2).rstrip())
s = s.replace("{COMMIT}", "commit_msg170.txt")
left = re.findall(r"\{[A-Z_]+\}", s)
assert not left, left
open(f"{D}/{NAME}_Report.md", "w", encoding="utf-8", newline="\n").write(s)
for sub in ("udp", "scripts", "records"):
    os.makedirs(f"{A}/{sub}", exist_ok=True)
for case, rule in (("U4_A0", "proportional_early_tie"), ("U4_A0e", "proportional_even"), ("U4_A1", "earliest_first")):
    src = f"{COS}/udp/{case}_{rule}"
    dst = f"{A}/udp/{case}"
    os.makedirs(dst, exist_ok=True)
    for f in ("udp_selection_ledger.csv", "udp_result_by_request.csv", "udp_capacity_check.csv", "udp_supply_runs.csv", "udp_plan.json"):
        shutil.copyfile(f"{src}/{f}", f"{dst}/{f}")
for f in ("run_trial.py", "measure.py", "b_checks.py", "assemble.py"):
    shutil.copyfile(f"{W}/{f}", f"{A}/scripts/{f}")
for f in ("b_checks.json", "t2_all.csv", "allocation_qty_P2a2.csv"):
    shutil.copyfile(f"{W}/{f}", f"{A}/records/{f}")
with open(f"{A}/README.md", "w", encoding="utf-8", newline="\n") as f:
    f.write(f"""# 付録：BS-SEAF 化粧品 U4 の再現用データ

本報告：`docs/development/{NAME}_Report.md`。

- `udp/<案>/`：選択の台帳、要求週ごとの結果、時間の可否の診断（参考値）、供給 0 の連続、`udp_plan.json`。
- `records/t2_all.csv`：要求週ごとの全期間の結果（T2）。`b_checks.json`：B1〜B4 の確かめ。`allocation_qty_P2a2.csv`：`quota_source` の列を足した数量枠。
- `scripts/`：`output/bsseaf_cosmetics/u4_work/` に置いて、リポジトリの根から実行する。順に `run_trial.py`、`measure.py`（P2-a の付録の `make_allocation.py` と `evaluation.json` を `p2a_work/` に要する）。

金額は架空の仮定。評価の額は配分を比べるための比較値で、営業利益ではない。
""")
print("ok", len(s.splitlines()))
