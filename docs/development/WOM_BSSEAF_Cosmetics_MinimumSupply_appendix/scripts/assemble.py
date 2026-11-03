# -*- coding: utf-8 -*-
"""Assemble the report and appendix from the generated tables.
    python output/bsseaf_cosmetics/ms_work/assemble.py <fill.json>
"""
import json
import os
import re
import shutil
import sys

W = "output/bsseaf_cosmetics/ms_work"
COS = "output/bsseaf_cosmetics"
D = "docs/development"
NAME = "WOM_BSSEAF_Cosmetics_MinimumSupply"
A = f"{D}/{NAME}_appendix"
RULE = "trim_to_capacity_latest"
LAB = {"COS_Serum": "美容液", "COS_Cream": "クリーム", "SG_Distributor": "代理店（SG）", "TH_Distributor": "代理店（TH）"}
t = open(W + "/report_tables.md", encoding="utf-8").read()
m = re.search(r"### まとめの表\n\n(.*?)\n\n(### M1.*)", t, re.S)
pre = json.load(open(W + "/pre.json", encoding="utf-8"))
s = open(W + "/report_template.md", encoding="utf-8").read()
b2 = ["| 案 | 鍵 | 週の需要 → 最低供給量（週の数） | 定常の週の上限 | ① | 最低供給量の合計 | 数量枠 |\n|---|---|---|---:|---:|---:|---:|"]
for c, by in pre["B2"].items():
    for k, v in by.items():
        a, b = k.split("|")
        w = "、".join(f"{x.replace('->', ' → ')}（{n}）" for x, n in v["weeks_by_q1_min"].items())
        b2.append(f"| {c} | {LAB[a]} {LAB[b]} | {w} | {v['max_cut_steady']} | {v['q1']} | {v['min_total']} | {v['quota']} |")
s = s.replace("{T_SUMMARY}", m.group(1)).replace("{T_REST}", m.group(2).rstrip()).replace("{T_B2}", "\n".join(b2))
for k, v in json.load(open(sys.argv[1], encoding="utf-8")).items():
    s = s.replace("{" + k + "}", v)
left = re.findall(r"\{T_[A-Z0-9_]+\}", s)
assert not left, left
open(f"{D}/{NAME}_Report.md", "w", encoding="utf-8", newline="\n").write(s)
for sub in ("udp", "scripts", "records", "policy"):
    os.makedirs(f"{A}/{sub}", exist_ok=True)
FILES = {"MS_base": ("udp_selection_ledger.csv", "udp_result_by_request.csv", "udp_capacity_check.csv", "udp_supply_runs.csv", "udp_plan.json"),
         "MS50": ("udp_selection_ledger.csv", "udp_result_by_request.csv", "udp_capacity_check.csv", "udp_supply_runs.csv", "udp_min_supply_check.csv", "udp_plan.json"),
         "MS70": ("udp_conflicts.csv", "udp_selection_reference.csv", "udp_plan.json")}
for c, fs in FILES.items():
    os.makedirs(f"{A}/udp/{c}", exist_ok=True)
    for f in fs:
        shutil.copyfile(f"{COS}/udp/{c}_{RULE}/{f}", f"{A}/udp/{c}/{f}")
for f in ("run_trial.py", "measure.py", "assemble.py"):
    shutil.copyfile(f"{W}/{f}", f"{A}/scripts/{f}")
for f in ("pre.json", "measure.json", "t2_all.csv", "knowledge.json"):
    shutil.copyfile(f"{W}/{f}", f"{A}/records/{f}")
for f in os.listdir(W + "/policy"):
    shutil.copyfile(f"{W}/policy/{f}", f"{A}/policy/{f}")
with open(f"{A}/README.md", "w", encoding="utf-8", newline="\n") as f:
    f.write(f"""# 付録：BS-SEAF 化粧品 代理店への最低供給量の再現用データ

本報告：`docs/development/{NAME}_Report.md`。

- `policy/`：方針のファイル（MS50・MS70）。
- `udp/MS_base`・`udp/MS50`：選択の台帳、要求週ごとの結果、時間の可否の診断、供給 0 の連続、`udp_plan.json`。MS50 は `udp_min_supply_check.csv`（二段階の確認）も。
- `udp/MS70`：`udp_conflicts.csv`（衝突の記録）、`udp_selection_reference.csv`（衝突の無い鍵の参考。採用できる台帳ではない）、`udp_plan.json`。
- `records/t2_all.csv`：基準・MS50 の要求週ごとの全期間の結果。`records/pre.json`：B2、試行の前の参考値、終了コード。`records/measure.json`：確かめと集計。`records/knowledge.json`：実行に渡した知識の版。
- `scripts/`：`output/bsseaf_cosmetics/ms_work/` に置いて、リポジトリの根から `run_trial.py`、`measure.py` の順に実行する。C3a の写し、P2-a の付録の `make_allocation.py`（`p2a_work/`）を要する。

金額は架空の仮定。評価の額は配分を比べるための比較値で、営業利益ではない。
""")
print("ok", len(s.splitlines()))
