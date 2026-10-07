# -*- coding: utf-8 -*-
"""
tools/gen_generation_line_capacity.py — 世代間で共有する組立ラインの能力の行を作る
（RequestLetter_GenerationLine_UpperLayer §3）

    python -m tools.gen_generation_line_capacity --model-dir data/sample/smartx-2027-2029 \
        --switch-week 2028-W40 [--gap 4] [--factor 1.1 | --cap-old 1438 --cap-new 3713] [--dry-run]

切り替えの週を s、空き期間を g とすると（s はラインの週）:

    週              旧世代のライン        新世代のライン
    s より前        cap_old               0
    s 〜 s+g-1      0（空き期間）         0（空き期間）
    s+g 以降        0                     cap_new

- 旧世代・新世代のノードの行を `capacity_plan.csv` から全部外し、計画期間の全週の行を書き直す
  （0 も明示する。空欄は「上限なし」になるため。RequestLetter_CapacityZeroBlank）。
- 能力は、指定が無ければ「その世代のピークの週の需要（全市場の合計）× factor」を切り上げた値。
- 助走の週（最初の非ゼロ需要週より前）の行は書かず、`materialize_warmup` に作らせる
  （その node の最初の実週の値をコピーする規約）。書いた後に materialize を走らせ、結果を確かめる。
- ほかの行は、順番も値も変えない。
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def build_rows(model_dir, old, new, switch_week, gap, cap_old, cap_new):
    """Return (header, rows, info). ``old``/``new`` = (product, node_name)."""
    from wom.engine.plan_period import detect_plan_period
    from wom.engine.warmup import first_nonzero_demand_week
    from wom.capacity_layer.generation_line import line_schedule
    cap_path = os.path.join(model_dir, "capacity_plan.csv")
    dem_path = os.path.join(model_dir, "demand_forecast.csv")
    with open(cap_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames)
        rows = list(reader)
    if "node_name" not in header:
        raise ValueError("capacity_plan.csv needs the node_name column for line rows")
    weeks = list(detect_plan_period(dem_path).weeks)
    real_start = first_nonzero_demand_week(dem_path)
    if switch_week not in weeks:
        raise ValueError(f"switch week {switch_week} is outside the plan period {weeks[0]}..{weeks[-1]}")
    s = weeks.index(switch_week)
    if s + gap >= len(weeks):
        raise ValueError("the new generation never starts inside the plan period")
    caps_old, caps_new = line_schedule(len(weeks), s, gap, cap_old, cap_new)
    targets = {tuple(old): caps_old, tuple(new): caps_new}
    region = {}
    first_pos = None
    kept = []
    for r in rows:
        key = (r["sku_id"], r["node_name"])
        if key in targets:
            if r.get("region") and not region.get(key):
                region[key] = r["region"]          # warm-up rows have a blank region
            if first_pos is None:
                first_pos = len(kept)
            continue
        kept.append(r)
    if first_pos is None:
        first_pos = len(kept)
    real = [i for i, w in enumerate(weeks) if real_start is None or w >= real_start]
    block = []
    for key, caps in targets.items():
        for i in real:
            row = {c: "" for c in header}
            row.update({"sku_id": key[0], "region": region.get(key, ""), "week": weeks[i],
                        "max_supply": str(int(caps[i])) if float(caps[i]).is_integer() else str(caps[i]),
                        "node_name": key[1]})
            block.append(row)
    out = kept[:first_pos] + block + kept[first_pos:]
    info = {"weeks": len(weeks), "real_start": real_start, "rows_written": len(block),
            "rows_removed": len(rows) - len(kept), "switch_week": switch_week,
            "resume_week": weeks[s + gap], "gap": gap,
            "last_old_week": weeks[s - 1] if s > 0 else None,
            "cap_old": cap_old, "cap_new": cap_new}
    return header, out, info


def write_rows(path, header, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, header, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--old", default="SmartX:AssemblyCN_g1")
    ap.add_argument("--new", default="SmartXNext:AssemblyCN_g3")
    ap.add_argument("--switch-week", required=True)
    ap.add_argument("--gap", type=int, default=4)
    ap.add_argument("--factor", type=float, default=1.1)
    ap.add_argument("--cap-old", type=float)
    ap.add_argument("--cap-new", type=float)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    sys.path.insert(0, REPO)
    from wom.capacity_layer.generation_line import line_capacity_from_demand
    from wom.engine.warmup import materialize_warmup
    old, new = tuple(a.old.split(":")), tuple(a.new.split(":"))
    with open(os.path.join(a.model_dir, "demand_forecast.csv"), encoding="utf-8-sig", newline="") as f:
        demand = list(csv.DictReader(f))
    cap_old = a.cap_old if a.cap_old is not None else line_capacity_from_demand(demand, old[0], a.factor).capacity
    cap_new = a.cap_new if a.cap_new is not None else line_capacity_from_demand(demand, new[0], a.factor).capacity
    header, rows, info = build_rows(a.model_dir, old, new, a.switch_week, a.gap, cap_old, cap_new)
    print(info)
    if a.dry_run:
        return 0
    write_rows(os.path.join(a.model_dir, "capacity_plan.csv"), header, rows)
    print(materialize_warmup(a.model_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
