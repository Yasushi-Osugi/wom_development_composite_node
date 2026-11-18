# -*- coding: utf-8 -*-
"""Row-order bias stage 0: join the candidates (§1.1) and the measured results (§1.2) into
measured.csv and tables.md (markdown tables for the report).

    python output/roworder_stage0/tables.py
"""
import csv
import glob
import json
import os

OUT = os.path.dirname(os.path.abspath(__file__))
cand = json.load(open(os.path.join(OUT, "candidates.json"), encoding="utf-8"))
meas = {}
for p in glob.glob(os.path.join(OUT, "*.json")):
    b = os.path.basename(p)[:-5]
    if b.startswith("candidates"):
        continue
    meas[b] = json.load(open(p, encoding="utf-8"))

rows = []
for tag, d in sorted(meas.items()):
    for f in d["factories"]:
        multi = f["overflow_weeks_multi_market"] + f["closed_weeks_pushed_multi_market"]
        rows.append({"run": tag, "model": d["model"], "legacy_golden": d["legacy_golden"], "product": f["product"],
                     "factory": f["factory"], "overflow_weeks": f["overflow_weeks"],
                     "overflow_weeks_multi_market": f["overflow_weeks_multi_market"],
                     "closed_weeks_pushed": f["closed_weeks_pushed"],
                     "closed_weeks_pushed_multi_market": f["closed_weeks_pushed_multi_market"],
                     "pushed_back_lots": f["pushed_back_lots"], "dropped_total": f["dropped_total"],
                     "dropped_by_market": " ".join(f"{k}:{v}" for k, v in sorted(f["dropped_by_market"].items())),
                     "first_week": f["first_overflow_week"], "last_week": f["last_overflow_week"],
                     "expected_change": multi > 0, "golden_match": d["golden_match"]})
with open(os.path.join(OUT, "measured.csv"), "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

L = ["## 候補（§1.1、CSV だけ）", "",
     "| モデル | 製品 | 工場 | 能力（cap_hard 行／cap_soft 行／partial） | 休業（supply_closure／0 shift） | 市場 | 候補 |",
     "|---|---|---|---|---|---:|---|"]
for c in cand:
    L.append(f"| {c['model']} | {c['product']} | {c['factory']} | {c['cap_hard_rows']}／{c['cap_soft_rows']}／"
             f"{c['partial_capacity_rows']} | {c['supply_closure_rows']}／{c['op_zero_shift_rows']} | {c['markets']} | "
             f"{'○' if c['candidate'] else '—'} |")
L += ["", "## 実測（§1.2、計画を回して）", "",
      "| 実行 | 製品 | 工場 | 超過の週 | うち複数市場 | 休業の週 | うち複数市場 | はみ出しの延べ | 落ちた lot | 最初〜最後の週 | 変わる見込み |",
      "|---|---|---|---:|---:|---:|---:|---:|---|---|---|"]
for r in rows:
    dr = f"{r['dropped_total']}（{r['dropped_by_market']}）" if r["dropped_total"] else "0"
    L.append(f"| {r['run']} | {r['product']} | {r['factory']} | {r['overflow_weeks']} | {r['overflow_weeks_multi_market']} | "
             f"{r['closed_weeks_pushed']} | {r['closed_weeks_pushed_multi_market']} | {r['pushed_back_lots']} | {dr} | "
             f"{r['first_week']}〜{r['last_week']} | {'○' if r['expected_change'] else '—'} |")
L += ["", "## 実行ごと", "", "| 実行 | 方式 | 秒 | golden と一致 | 変わる見込み |", "|---|---|---:|---|---|"]
for tag, d in sorted(meas.items()):
    ch = any(r["expected_change"] for r in rows if r["run"] == tag)
    L.append(f"| {tag} | {d['lot_flow_mode']} | {d['seconds']} | {'○' if d['golden_match'] else '× ' + ','.join(d['golden_diff_keys'])} | "
             f"{'○' if ch else '—'} |")
open(os.path.join(OUT, "tables.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
