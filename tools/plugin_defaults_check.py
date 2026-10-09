# -*- coding: utf-8 -*-
"""
tools/plugin_defaults_check.py — 全サンプルで「headless の既定（--plugins なし）＝golden」を確かめる
（RequestLetter_PublicReadiness_Plugins 受入 P-1）

    python -m tools.plugin_defaults_check --out output/public_readiness/p1

各モデルのコピーを、プラグインを指定せずに headless で計画する（＝モデルの recommended_plugins）。
golden のあるモデルは、golden の psi・ppc・forward・period・products とプラグインの組を比べる。
golden の無いモデルは、明示の safe（GUI・headless の既定にした組）での計画と比べる。
出力：<out>/p1.csv、<out>/p1.json。golden・モデルは変えない（コピーで実行）。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KEYS = ("psi", "ppc", "forward", "period", "products")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", default="", help="comma 区切り（省略時は data/sample の全モデル）")
    a = ap.parse_args(argv)
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    import tools.run_headless_from_folder as rh
    os.makedirs(a.out, exist_ok=True)
    sample = os.path.join(REPO, "data", "sample")
    models = [m for m in (a.models.split(",") if a.models else sorted(os.listdir(sample)))
              if m and "_BK" not in m and os.path.isfile(os.path.join(sample, m, "sc_tree_master.csv"))]
    rows = []
    for m in models:
        t0 = time.perf_counter()
        tmp = tempfile.mkdtemp(prefix="p1_")
        row = {"model": m}
        try:
            work = os.path.join(tmp, m)
            shutil.copytree(os.path.join(sample, m), work)
            snap = rh.run(work, output_ppc_dir=os.path.join(tmp, "_ppc"), verbose=False)
            row["plugins_source"] = snap["config"].get("plugins_source")
            row["plugins"] = "+".join(snap["config"]["plugins"])
            g = os.path.join(REPO, "tests", "golden", f"{m}.json")
            if os.path.exists(g):
                with open(g, encoding="utf-8") as f:
                    ref = json.load(f)
                row["compared_with"] = "golden"
                row["plugins_equal"] = snap["config"]["plugins"] == ref["config"]["plugins"]
                row["lot_flow_mode_equal"] = (snap["config"].get("lot_flow_mode")
                                              == ref["config"].get("lot_flow_mode"))
            else:
                work2 = os.path.join(tmp, m + "_safe")
                shutil.copytree(os.path.join(sample, m), work2)
                ref = rh.run(work2, plugins_spec="safe", output_ppc_dir=os.path.join(tmp, "_ppc2"),
                             verbose=False)
                row["compared_with"] = "explicit safe (no golden)"
                row["plugins_equal"] = snap["config"]["plugins"] == ref["config"]["plugins"]
                row["lot_flow_mode_equal"] = True
            for k in KEYS:
                row[f"{k}_equal"] = (snap.get(k) == ref.get(k)) if k in ref else "n/a"
            ppc = snap.get("ppc") or {}
            row["revenue_base"] = ppc.get("revenue_base")
            row["gross_margin_pct"] = ppc.get("gross_margin_pct")
            row["all_equal"] = all(v is True or v == "n/a" for k, v in row.items() if k.endswith("_equal"))
        except Exception as exc:     # report it, keep checking the other models
            row["error"] = f"{type(exc).__name__}: {exc}"[:300]
            row["all_equal"] = False
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        row["seconds"] = round(time.perf_counter() - t0, 1)
        rows.append(row)
        print(f"[P-1] {m}: {'OK' if row['all_equal'] else 'DIFF'} "
              f"({row.get('compared_with', '')}, {row.get('plugins_source', '')}, {row['seconds']} s)"
              + (f" {row['error']}" if "error" in row else ""), flush=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(os.path.join(a.out, "p1.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(a.out, "p1.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1, default=str)
    return 0 if all(r["all_equal"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
