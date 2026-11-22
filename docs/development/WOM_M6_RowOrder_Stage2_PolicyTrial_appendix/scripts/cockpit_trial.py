# -*- coding: utf-8 -*-
"""段 2 §1・§2：コックピットの案で 3 方式を回す（化粧品 C3a、醤油 C03、soysauce-jpy-2027-alloc）。

    python output/roworder_stage2/scripts/cockpit_trial.py cos|soy_c03|soy_alloc

- 作業は output/roworder_stage2/<場>/ws。案のモデルの planning_config.csv に overflow_policy を 1 行足すだけ
  （コックピットの案の写し。元のモデル・正式なサンプルは変えない）。
- 案の実行（計画・PPC・Value Chain・年齢の検査）は wom.cockpit.case_runner.run_case（既存の道具）。
- 押し戻し（延べ・負担率）と計画の前に落ちた lot は、案の計画の写し（money_model）を common.capture で
  もう 1 回回して受け取る（エンジンの記録）。①〜⑤ は tools.period_fulfillment。
"""
import csv
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as CM  # noqa: E402

from wom.cockpit import cases as C  # noqa: E402
from wom.cockpit import case_runner as R  # noqa: E402
from tools import period_fulfillment as PF  # noqa: E402
from tools import compare_scenarios as CS  # noqa: E402

COS = os.path.join(CM.REPO, "data", "sample", "cosmetics-sg-th-2027-2029")
SOY_C03 = os.path.join(CM.REPO, "output", "cockpit_m6", "soy", "C03")
SOY_ALLOC = os.path.join(CM.REPO, "output", "cockpit_m6", "soy_model")   # the sample + report_start 2027-W01 only (M6)


def reorder_tree(model_dir):
    """Reverse the sibling order in sc_tree_master.csv (parents still before children; roots keep their order)."""
    p = os.path.join(model_dir, "sc_tree_master.csv")
    fields, rows, term, bom = C._read_rows(p)
    out = []
    for prod in dict.fromkeys(r["product_name"] for r in rows):
        rs = [r for r in rows if r["product_name"] == prod]
        kids = {}
        for r in rs:
            kids.setdefault(r["parent_node"].strip(), []).append(r)

        def emit(r):
            out.append(r)
            for c in reversed(kids.get(r["node_name"].strip(), [])):
                emit(c)
        for r in kids.get("", []):
            emit(r)
        if len([r for r in out if r["product_name"] == prod]) != len(rs):
            raise SystemExit(f"reorder: rows lost for {prod}")
    C._write_rows(p, fields, out, term, bom)


def setup(scene):
    ws = os.path.join(CM.OUT, scene, "ws")
    if os.path.exists(os.path.join(ws, C.WORKSPACE_FILE)):
        return ws, json.load(open(os.path.join(ws, "trial_cases.json"), encoding="utf-8"))
    if scene == "cos":
        C.create_workspace(ws, COS, max_age_weeks=52, first_name="C3a tail")
        C.set_capacity(ws, "C01", "COS_Serum", 17, 14)
        C.set_capacity(ws, "C01", "COS_Cream", 13, 11)
        names = [("C3a proportional_week", "proportional_week", False), ("C3a balance_cut_ratio", "balance_cut_ratio", False),
                 ("C3a balance_cut_ratio 行の順を入れ替え", "balance_cut_ratio", True),
                 ("C3a tail 行の順を入れ替え（参考）", "tail", True)]
    elif scene == "soy_c03":
        C.create_workspace(ws, os.path.join(SOY_C03, "model"), max_age_weeks=52, first_name="C03 tail")
        pol = json.load(open(os.path.join(SOY_C03, "case.json"), encoding="utf-8"))["inputs"]["policy"]
        C.set_policy(ws, "C01", allocation_file=os.path.join(SOY_C03, pol["allocation_file"]),
                     week_rule=pol["week_rule"], unallocated_note=pol.get("unallocated_note"))
        names = [("C03 proportional_week", "proportional_week", False), ("C03 balance_cut_ratio", "balance_cut_ratio", False)]
    else:
        C.create_workspace(ws, SOY_ALLOC, max_age_weeks=52, first_name="alloc tail")
        names = [("alloc proportional_week", "proportional_week", False),
                 ("alloc balance_cut_ratio", "balance_cut_ratio", False)]
    cases = {"C01": {"policy": "tail", "reordered": False}}
    for name, policy, swap in names:
        cid = C.copy_case(ws, "C01", name)
        m = os.path.join(ws, cid, "model")
        CM.set_policy(m, policy)
        if swap:
            reorder_tree(m)
        cases[cid] = {"policy": policy, "reordered": swap}
    json.dump(cases, open(os.path.join(ws, "trial_cases.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return ws, cases


def run_all(scene):
    ws, cases = setup(scene)
    for cid in cases:
        if C.status(ws, cid)["state"] != C.ST_DONE:
            rec = R.run_case(ws, cid)
            print(f"[{scene}] {cid} {rec['state']} {rec.get('reason', '')}", flush=True)
            if rec["state"] != C.ST_DONE:
                raise SystemExit(f"{cid}: {rec.get('message')}")
    rows = {}
    for cid, meta in cases.items():
        path = os.path.join(CM.OUT, scene, f"{cid}.json")
        case = C.read_case(ws, cid)
        run = case["run"]
        if os.path.exists(path):
            j = json.load(open(path, encoding="utf-8"))
            if j.get("input_hashes") == run["input_hashes"]:
                rows[cid] = j
                continue
        cdir = C.case_dir(ws, cid)
        mm = os.path.join(cdir, run["money_model"])
        cap = CM.capture(mm, os.path.join(CM.OUT, scene, "capture", cid))
        lr = CS.load_run(os.path.join(cdir, "run"), mm)
        inv = lr["inv"]
        inv = inv[inv["external"].astype(int) == 0]
        shelf = lr["shelf"]
        star = shelf[(shelf["product"] == "*") & (shelf["channel"] == "*")].iloc[0]
        j = {"case": cid, "name": case["name"], **meta, "input_hashes": run["input_hashes"],
             "summary": run["summary"], "burden": cap["burden"], "past_due": cap["past_due"],
             "past_due_total": cap["past_due_total"], "cap_dropped": cap["cap_dropped"], "cap_dropped_total": cap["cap_dropped_total"], "pushed": cap["pushed"], "capture_policy": cap["policy"],
             "capture_market": cap["market"], "inventory_lot_weeks": int(inv["lots"].sum()),
             "inventory_lot_weeks_report": int(inv[inv["week"] >= run["summary"]["report_period"][0]]["lots"].sum()),
             "age_max": int(star["fifo_age_max"]), "over_52": int(star["over_max_age"]),
             "ship_digest": ship_digest(cdir)}
        CM.save(j, path)
        rows[cid] = j
    res = PF.fulfillment(ws, list(cases), [], [], {}, out=os.path.join(CM.OUT, scene, "fulfillment"))
    CM.save({"cases": rows}, os.path.join(CM.OUT, scene, "cases.json"))
    print(f"[{scene}] done -> {os.path.join(CM.OUT, scene)}", flush=True)
    return ws, rows, res


def ship_digest(cdir):
    """sha256 of the sorted consumer-sale (lot, ship week) pairs of the case's Value Chain run."""
    import gzip
    import hashlib
    p = os.path.join(cdir, "run", "vc", "vc_shipments.csv.gz")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        pairs = sorted((r["lot_id"], r["ship_week"]) for r in rd if r.get("kind") == "consumer_sale")
    return {"n": len(pairs), "sha256": hashlib.sha256(repr(pairs).encode()).hexdigest()[:16]}


if __name__ == "__main__":
    run_all(sys.argv[1])
