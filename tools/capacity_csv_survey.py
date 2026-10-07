# -*- coding: utf-8 -*-
"""
tools/capacity_csv_survey.py — 能力の CSV の「0・空欄・読めない行」の調べ（測定だけ）
（RequestLetter_CapacityZeroBlank 受入 1）

    python -m tools.capacity_csv_survey --out output/capacity_zero_blank/survey [--models all|a,b]

モデルごとに、モデルのコピーで headless の計画を 1 回流し、`capacity_plan.csv` を
読み込むときの計画の木・計画期間・最終的な休業の状態（`is_open`）を使って、CSV の
各行を分ける。原本には書かない。

行の分け方（max_supply と cap_soft のそれぞれ）
  blank        値が空（列が無い場合は数えない）
  zero_open    0 で、ノードがあり、計画期間の中で、その週は開いている
               → 0 の意味が「上限なし」から「能力ゼロ」に変わると、計画が変わりうる行
  zero_closed  0 で、その週は休業（休業が優先するので、意味の変更の影響なし）
  zero_out     0 で、計画期間の外
  positive     正の数
  invalid      数値でない、負の数（新しい規則では読み込みで止まる）
  node_not_found  計画の木に無いノード名（製品×ノード）。新しい規則では止まる
  week_out     計画期間の外の週（新しい規則では警告だけ）

旧書式（node_name 列なし。iphone）は、(製品, 週) で合計して MOM に入る。この場合は
製品の InBound root に入るとして数える。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import sys
import tempfile
from collections import Counter

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _models(only):
    out = []
    for d in sorted(os.listdir(os.path.join(REPO, "data", "sample"))):
        p = os.path.join(REPO, "data", "sample", d)
        if not os.path.isdir(p) or "_BK" in d or not os.path.exists(os.path.join(p, "capacity_plan.csv")):
            continue
        if only and d not in only:
            continue
        out.append(d)
    return out


def _plugins(case):
    gp = os.path.join(REPO, "tests", "golden", case + ".json")
    if os.path.exists(gp):
        with open(gp, encoding="utf-8") as f:
            return ",".join(json.load(f)["config"]["plugins"]) or "none"
    return "safe"


def _classify(v):
    if v is None:
        return "nocol"
    s = str(v).strip()
    if s == "" or s.lower() == "nan":
        return "blank"
    try:
        x = float(s)
    except ValueError:
        return "invalid"
    if math.isnan(x) or x < 0:
        return "invalid"
    return "zero" if x == 0 else "positive"


def survey_model(case, tmp):
    import tools.run_headless_from_folder as rh
    store = {}
    o_sig = rh._psi_signature

    def sig(t, n):
        store["tree"] = t
        return o_sig(t, n)

    rh._psi_signature = sig
    work = os.path.join(tmp, case)
    shutil.copytree(os.path.join(REPO, "data", "sample", case), work)
    err = None
    try:
        rh.run(work, plugins_spec=_plugins(case), output_ppc_dir=os.path.join(work, "_ppc"), verbose=False)
    except Exception as exc:                 # the model does not run (before or after the change)
        err = f"{type(exc).__name__}: {exc}"
    finally:
        rh._psi_signature = o_sig
    tree = store.get("tree")
    with open(os.path.join(work, "capacity_plan.csv"), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    res = {"model": case, "rows": len(rows), "run_error": err}
    if tree is None:
        return res, []
    weeks = {w: i for i, w in enumerate(tree.week_labels)}
    per_node = "node_name" in (rows[0].keys() if rows else [])
    lut = {}
    for p in tree.products:
        for nd in tree.iter_all_nodes(p):
            lut[(p, nd.node_name)] = nd
    counts = Counter()
    zero_open_by_node = Counter()
    not_found = Counter()
    details = []
    for i, r in enumerate(rows, start=2):        # line number in the file (header = 1)
        sku, wk = r.get("sku_id", ""), r.get("week", "")
        if per_node:
            nd = lut.get((sku, r.get("node_name", "")))
        else:
            try:
                nd = tree.get_in_root(sku)
            except Exception:
                nd = None
        if nd is None:
            counts["node_not_found"] += 1
            not_found[(sku, r.get("node_name", r.get("region", "")))] += 1
            continue
        wi = weeks.get(wk)
        for col in ("max_supply", "cap_soft"):
            c = _classify(r.get(col))
            if c == "nocol":
                continue
            key = f"{col}:{c}"
            if c == "zero":
                if wi is None:
                    key = f"{col}:zero_out"
                elif nd.is_open(wi):
                    key = f"{col}:zero_open"
                    zero_open_by_node[(col, sku, nd.node_name)] += 1
                    details.append({"model": case, "line": i, "column": col, "sku_id": sku,
                                    "node": nd.node_name, "week": wk})
                else:
                    key = f"{col}:zero_closed"
            counts[key] += 1
        if wi is None:
            counts["week_out"] += 1
    res.update(dict(counts))
    res["zero_open_by_node"] = {f"{c}|{s}|{n}": k for (c, s, n), k in zero_open_by_node.items()}
    res["node_not_found_by_key"] = {f"{s}|{n}": k for (s, n), k in not_found.items()}
    return res, details


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join("output", "capacity_zero_blank", "survey"))
    ap.add_argument("--models", default="all")
    a = ap.parse_args(argv)
    os.chdir(REPO)
    os.makedirs(a.out, exist_ok=True)
    only = None if a.models == "all" else set(a.models.split(","))
    tmp = tempfile.mkdtemp(prefix="capsurvey_")
    results, details = [], []
    try:
        for case in _models(only):
            r, d = survey_model(case, tmp)
            results.append(r)
            details += d
            print(json.dumps(r, ensure_ascii=False), flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with open(os.path.join(a.out, "survey.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, "zero_open_rows.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["model", "line", "column", "sku_id", "node", "week"])
        w.writeheader(); w.writerows(details)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
