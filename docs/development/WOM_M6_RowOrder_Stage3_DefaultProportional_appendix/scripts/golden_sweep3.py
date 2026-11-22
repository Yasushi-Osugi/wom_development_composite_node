# -*- coding: utf-8 -*-
"""段 3 §3：新しい既定（overflow_policy を書かない）で golden 16 件と legacy 3 件を回して、golden と比べる。

    python output/roworder_stage3/scripts/golden_sweep3.py [default|legacy|tail] [モデル ...]

- default：写し output/roworder_stage3/golden/models/<モデル>/（planning_config.csv に overflow_policy の行なし）
  を golden と同じプラグインの組・lot_flow_mode で headless 1 回。golden と全キー（config も）を比べる。
- legacy：tests/golden/legacy の 3 件を lot_flow_mode=legacy で（新しい既定）。
- tail：差の基準（市場別の数）。overflow_policy,tail を明示した写し。既定で変わったモデルだけ回す。
結果は output/roworder_stage3/golden/<種類>/<モデル>.json に 1 件ずつ書く（あればとばす）。
押し戻し・計画の前に落ちた lot の記録は段 2 の common.capture（エンジンの呼び出しの包み）。
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "roworder_stage2", "scripts"))
import common as CM  # noqa: E402

OUT = os.path.join(CM.REPO, "output", "roworder_stage3", "golden")
GKEYS = ("period", "products", "config", "forward", "backward", "ppc", "psi")
HEAVY = ("smartx-2027-2029", "smartphone-global-2026-2029")


def golden_models(kind):
    d = os.path.join(CM.REPO, "tests", "golden", "legacy" if kind == "legacy" else "")
    ms = sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith(".json"))
    return [m for m in ms if m not in HEAVY] + [m for m in HEAVY if m in ms]


def write_policy(model_dir, policy):
    """policy=None：overflow_policy の行を消す（新しい既定）。それ以外：その値を 1 行。"""
    pc = os.path.join(model_dir, "planning_config.csv")
    lines = []
    if os.path.exists(pc):
        lines = [l for l in open(pc, encoding="utf-8-sig").read().splitlines()
                 if l.strip() and not l.startswith("overflow_policy,")]
    if policy:
        if not lines:
            lines = ["key,value"]
        lines.append(f"overflow_policy,{policy}")
    if lines:
        open(pc, "w", encoding="utf-8", newline="").write("\n".join(lines) + "\n")


def one(kind, model):
    path = os.path.join(OUT, kind, f"{model}.json")
    if os.path.exists(path):
        print("[skip]", kind, model, flush=True)
        return json.load(open(path, encoding="utf-8"))
    gpath = os.path.join(CM.REPO, "tests", "golden", *(["legacy"] if kind == "legacy" else []), model + ".json")
    golden = json.load(open(gpath, encoding="utf-8"))
    plugins = ",".join(golden.get("config", {}).get("plugins", [])) or "none"
    mode = "legacy" if kind == "legacy" else golden.get("config", {}).get("lot_flow_mode", "legacy")
    mdir = os.path.join(OUT, "models", f"{model}_{kind}")
    if not os.path.exists(mdir):
        shutil.copytree(os.path.join(CM.REPO, "data", "sample", model), mdir,
                        ignore=shutil.ignore_patterns("__pycache__", "output"))
    write_policy(mdir, "tail" if kind == "tail" else None)
    res = CM.capture(mdir, os.path.join(OUT, "runs", f"{model}_{kind}"), plugins=plugins, lot_flow_mode=mode)
    snap = res["snapshot"]
    keys = GKEYS if kind != "tail" else tuple(k for k in GKEYS if k != "config")
    res["golden_diff_keys"] = [k for k in keys if k in golden and snap.get(k) != golden[k]]
    res["golden_match"] = not res["golden_diff_keys"]
    res["model"], res["kind"] = model, kind
    CM.save(res, path)
    print(f"[done] {kind} {model} {res['seconds']}s golden_match={res['golden_match']} "
          f"diff={res['golden_diff_keys']} policy={res.get('policy')}", flush=True)
    if kind == "tail" and not res["golden_match"]:
        raise SystemExit(f"STOP: tail of {model} does not match golden ({res['golden_diff_keys']})")
    return res


if __name__ == "__main__":
    kind = sys.argv[1]
    ms = sys.argv[2:] or golden_models(kind)
    for m in ms:
        one(kind, m)
