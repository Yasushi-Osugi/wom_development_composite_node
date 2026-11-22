# -*- coding: utf-8 -*-
"""段 2 §3：golden の 13 モデル × 3 方式。

    python output/roworder_stage2/scripts/golden_sweep.py [モデル ...]

写し output/roworder_stage2/golden/models/<モデル>_<方式>/ に planning_config.csv の overflow_policy を足し、golden と
同じプラグインの組・lot_flow_mode で headless を 1 回。結果を output/roworder_stage2/golden/<モデル>_<方式>.json に
書いてから次へ（あればとばす）。tail は golden と snapshot が一致することを確かめる（市場別の数は golden に無いので、
tail も回して差の基準にする）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as CM  # noqa: E402

MODELS = ["Cookie-jp-2026", "apparel-us-2026", "apparel-global-2028-2029", "ev-europe-2026", "ev-thailand-2026",
          "ev-thailand-2026_update", "oil-global-2027", "soysauce-eu-2027", "soysauce-us-2027", "soysauce-jpy-2027",
          "soysauce-jpy-2027-alloc", "smartx-2027-2029", "smartphone-global-2026-2029"]   # heavy ones last
GKEYS = ("period", "products", "config", "forward", "backward", "ppc", "psi")
G = os.path.join(CM.OUT, "golden")


def one(model, policy):
    path = os.path.join(G, f"{model}_{policy}.json")
    if os.path.exists(path):
        print("[skip]", model, policy, flush=True)
        return
    golden = json.load(open(os.path.join(CM.REPO, "tests", "golden", model + ".json"), encoding="utf-8"))
    plugins = ",".join(golden.get("config", {}).get("plugins", [])) or "none"
    mode = golden.get("config", {}).get("lot_flow_mode", "legacy")
    mdir = CM.copy_model(os.path.join(CM.REPO, "data", "sample", model),
                         os.path.join(G, "models", f"{model}_{policy}"), policy)
    res = CM.capture(mdir, os.path.join(G, "runs", f"{model}_{policy}"), plugins=plugins, lot_flow_mode=mode)
    snap = res["snapshot"]
    keys = [k for k in GKEYS if k != "config" or policy == "tail"]
    res["golden_diff_keys"] = [k for k in keys if k in golden and snap.get(k) != golden[k]]
    res["golden_match"] = not res["golden_diff_keys"]
    res["model"], res["overflow_policy"] = model, policy
    CM.save(res, path)
    print(f"[done] {model} {policy} {res['seconds']}s golden_match={res['golden_match']} "
          f"diff={res['golden_diff_keys']} past_due={res['past_due_total']}", flush=True)
    if policy == "tail" and not res["golden_match"]:
        raise SystemExit(f"STOP: tail of {model} does not match golden ({res['golden_diff_keys']})")


if __name__ == "__main__":
    for m in (sys.argv[1:] or MODELS):
        for p in CM.POLICIES:
            one(m, p)
