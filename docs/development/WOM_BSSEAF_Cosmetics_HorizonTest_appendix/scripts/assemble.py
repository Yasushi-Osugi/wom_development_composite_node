# -*- coding: utf-8 -*-
"""Assemble the report and appendix from the generated tables.
    python output/bsseaf_cosmetics/hz_work/assemble.py <fill.json>
fill.json holds only what comes from the test runs and the clock (T_SMOKE ... T_TIME).
"""
import json
import os
import re
import shutil
import sys

W = "output/bsseaf_cosmetics/hz_work"
COS = "output/bsseaf_cosmetics"
D = "docs/development"
NAME = "WOM_BSSEAF_Cosmetics_HorizonTest"
A = f"{D}/{NAME}_appendix"
SKU = {"COS_Serum": "美容液", "COS_Cream": "クリーム"}
t = open(W + "/report_tables.md", encoding="utf-8").read()
m = re.search(r"### まとめの表\n\n(.*?)\n\n(### H1.*)", t, re.S)
pre = json.load(open(W + "/pre.json", encoding="utf-8"))
ms = json.load(open(W + "/measure.json", encoding="utf-8"))
s = open(W + "/report_template.md", encoding="utf-8").read()

b2 = ["| 写し | 計画の始まり | 終わり | 週 | warmup |\n|---|---|---|---:|---:|"]
b2.append("| E0（U4_A3） | 2026-W37 | 2029-W52 | " + str(ms["checks"]["period"]["U4_A3"]["weeks"]) + " | 17 |")
b3 = ["| 写し | 足した需要の行 | 足した能力の行 | 需要と能力の週がそろう | 週ごとの行（需要 8・能力 2） | 元の需要は同じ | 元の能力は C3a と同じ | 休業の行 |\n|---|---:|---:|---|---|---|---|---:|"]
yn = lambda x: "はい" if x else "いいえ"
for c, v in pre["copies"].items():
    b2.append(f"| {c} | {v['plan_start']} | {v['plan_end']} | {v['weeks']} | {v['warmup_lt']} |")
    b3.append(f"| {c} | {v['added_demand_rows']} | {v['added_capacity_rows']} | {yn(v['weeks_same_demand_capacity'])} | {yn(v['rows_per_week_ok'])} | {yn(v['demand_prefix_same_as_sample'])} | {yn(v['capacity_prefix_same_as_C3a'])} | {v['holiday_rows']} |")
s4 = ["| 案 | SKU | 参考値（試行の前） | 期末の未充足 | 一致 |\n|---|---|---:|---:|---|"]
for c, v in pre["refs_before"].items():
    e, a = c.split("_")[1:]
    for k in ("COS_Serum", "COS_Cream"):
        q = None
        import csv
        q = 0
        rule = {"A0e": "proportional_even", "A3": "trim_to_capacity_latest"}[a]
        for r in csv.DictReader(open(f"{COS}/udp/{c}_{rule}/udp_result_by_request.csv", encoding="utf-8-sig")):
            if r["source_demand_ref"].startswith(k + "|"):
                q += int(r["q5"])
        s4.append(f"| {e} {a} | {SKU[k]} | {v[k]} | {q} | {yn(v[k] == q)} |")
s = (s.replace("{T_SUMMARY}", m.group(1)).replace("{T_REST}", m.group(2).rstrip()).replace("{T_B2}", "\n".join(b2))
     .replace("{T_B3}", "\n".join(b3)).replace("{T_S4}", "\n".join(s4)))
for k, v in json.load(open(sys.argv[1], encoding="utf-8")).items():
    s = s.replace("{" + k + "}", v)
left = re.findall(r"\{T_[A-Z0-9_]+\}", s)
assert not left, left
open(f"{D}/{NAME}_Report.md", "w", encoding="utf-8", newline="\n").write(s)
for sub in ("udp", "scripts", "records", "quota"):
    os.makedirs(f"{A}/{sub}", exist_ok=True)
for c in pre["refs_before"]:
    rule = {"A0e": "proportional_even", "A3": "trim_to_capacity_latest"}[c.split("_")[2]]
    src, dst = f"{COS}/udp/{c}_{rule}", f"{A}/udp/{c}"
    os.makedirs(dst, exist_ok=True)
    for f in ("udp_selection_ledger.csv", "udp_result_by_request.csv", "udp_capacity_check.csv", "udp_supply_runs.csv", "udp_plan.json"):
        shutil.copyfile(f"{src}/{f}", f"{dst}/{f}")
for f in ("build.py", "run_trial.py", "measure.py", "assemble.py"):
    shutil.copyfile(f"{W}/{f}", f"{A}/scripts/{f}")
for f in ("pre.json", "measure.json", "t2_all.csv", "h2_diff.csv", "knowledge.json"):
    shutil.copyfile(f"{W}/{f}", f"{A}/records/{f}")
for e in ("E13", "E26"):
    shutil.copyfile(f"{W}/quota/allocation_qty_{e}.csv", f"{A}/quota/allocation_qty_{e}.csv")
with open(f"{A}/README.md", "w", encoding="utf-8", newline="\n") as f:
    f.write(f"""# 付録：BS-SEAF 化粧品 計画の期間を延ばす試験の再現用データ

本報告：`docs/development/{NAME}_Report.md`。

- `udp/<案>/`：4 通りの選択の台帳、要求週ごとの結果、時間の可否の診断、供給 0 の連続、`udp_plan.json`。
- `quota/`：E13・E26 の数量枠。合計の内訳は `records/pre.json` の `quota`。
- `records/t2_all.csv`：E0・E13・E26 × A0e・A3 の要求週ごとの全期間の結果。
- `records/h2_diff.csv`：共通の期間で E0 と違う鍵・週の全件。
- `records/pre.json`：B1〜B3、試行の前の参考値。`records/measure.json`：確かめと集計。`records/knowledge.json`：実行に渡した知識の版。
- `scripts/`：`output/bsseaf_cosmetics/hz_work/` に置いて、リポジトリの根から `build.py`、`run_trial.py`、`measure.py` の順に実行する。`build.py` が写しの作り方。C3a の写し、前回の `U4_A0e_r2`・`U4_A3`（年齢の要約を含む）、P2-a の付録の `make_allocation.py`（`p2a_work/`）、M0 の `checks_ppc.json` を要する。

金額は架空の仮定。評価の額は配分を比べるための比較値で、営業利益ではない。
""")
print("ok", len(s.splitlines()))
