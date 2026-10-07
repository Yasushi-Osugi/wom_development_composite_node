# -*- coding: utf-8 -*-
"""
tools/smartx_capacity_compare.py — smartx の能力 408 行を直す前後の比較（測定だけ）
（RequestLetter_CapacityZeroBlank 受入 4）

    python tools/smartx_capacity_compare.py <repo_root> <model_dir> <out.json>

`<repo_root>` のコードで、`<model_dir>` のモデル（のコピー）を headless で計画し、製品ごとに
市場の結果（需要・当週出荷・遅配・期末注文残）と、能力による繰り延べ（identity の
Step 0a）・Backward の MOM の能力の押し戻しで計画期間の前に出た件数を書き出す。
基準のコード（`git archive` で取り出したもの）と今のコードの両方で同じスクリプトを
使えるように、リポジトリの根を引数で受け取る。
"""
import json
import os
import shutil
import sys
import tempfile
from collections import Counter, defaultdict


def main(repo, model_dir, out_path):
    sys.path.insert(0, repo)
    os.chdir(repo)
    import tools.run_headless_from_folder as rh
    import wom.engine.forward_planner as fpm
    import wom.engine.backward_planner as bpm
    store = {"fres": {}, "bres": {}}
    o_sig, o_frun, o_brun = rh._psi_signature, fpm.ForwardPlanner.run, bpm.BackwardPlanner.run

    def sig(t, n):
        store["tree"] = t
        return o_sig(t, n)

    def frun(self, prod):
        r = o_frun(self, prod); store["fres"][prod] = r; return r

    def brun(self, prod):
        r = o_brun(self, prod); store["bres"][prod] = r; return r

    rh._psi_signature, fpm.ForwardPlanner.run, bpm.BackwardPlanner.run = sig, frun, brun
    tmp = tempfile.mkdtemp(prefix="smartx_cmp_")
    work = os.path.join(tmp, os.path.basename(model_dir.rstrip("/\\")))
    shutil.copytree(model_dir, work)
    out = {"repo": repo, "model_dir": model_dir}
    try:
        snap = rh.run(work, plugins_spec="BufferingStockOptimizerPlugin,CapacityOverridePlugin,HolidayCalendarPlugin",
                      output_ppc_dir=os.path.join(work, "_ppc"), verbose=False)
        out["ppc"] = snap["ppc"]
        out["forward"] = snap["forward"]
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    tree = store["tree"]
    try:
        from wom.engine.flow_check import compute_flow_check
        fc = compute_flow_check(tree, store["fres"])
        out["market"] = {r["product"]: {k: r[k] for k in ("demand", "on_time", "late", "backlog_end")}
                         for r in fc["market"] if r["leaf"] == "Σ（製品）"}
    except Exception as exc:
        out["market_error"] = str(exc)
    per = {}
    for prod, r in store["fres"].items():
        by_node = Counter()
        for nid, _wl, cnt in getattr(r, "cap_hard_events", []) or []:
            by_node[nid.split(":")[2] if nid.count(":") >= 3 else nid] += cnt
        per[prod] = {
            "cap_hard_deferred_lots": getattr(r, "cap_hard_deferred_lots", None),
            "cap_hard_deferred_lot_weeks": getattr(r, "cap_hard_deferred_lot_weeks", None),
            "cap_hard_sealed": getattr(r, "cap_hard_sealed", None),
            "cap_hard_events_by_node": dict(by_node),
        }
    for prod, b in store["bres"].items():
        pd_ = getattr(b, "past_due_lots", []) or []
        per.setdefault(prod, {})["backward_past_due"] = len(pd_)
        per[prod]["backward_past_due_by_node"] = dict(Counter(
            (x[0].split(":")[2] if x[0].count(":") >= 3 else x[0]) for x in pd_))
    out["per_product"] = per
    # assembly capacity actually set on the per-generation lines
    cap = {}
    for prod in tree.products:
        for nd in tree.iter_all_nodes(prod):
            if nd.node_name.startswith("AssemblyCN"):
                vals = [nd.cap_hard(w) for w in range(tree.num_weeks())]
                cap[f"{prod}|{nd.node_name}"] = {
                    "weeks_set": sum(1 for v in vals if v is not None and v != 0)
                    if not all(isinstance(v, float) for v in vals) else sum(1 for v in vals if v > 0),
                    "weeks_zero_or_unset": sum(1 for v in vals if not v),
                    "sum_ceiling": float(sum(v for v in vals if v)),
                }
    out["assembly_capacity"] = cap
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
