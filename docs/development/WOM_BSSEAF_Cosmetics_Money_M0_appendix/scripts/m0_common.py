# -*- coding: utf-8 -*-
"""M0-PPC trial (RequestLetter_BSSEAF_Cosmetics_Money v0.2): shared parts.

Standard code is not changed. Runs go through tools.run_headless_from_folder.run
with one extra observing plugin (Capture) that keeps the planned tree, so that the
demand Lot_IDs and the actual shipments (_actual_ship) can be read after the run.
"""
import csv
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COS = os.path.dirname(HERE)                       # output/bsseaf_cosmetics
REPO = os.path.abspath(os.path.join(COS, "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
os.chdir(REPO)

from wom.engine.plugin_base import WOMPlugin      # noqa: E402

MONEY_FILES = {                                   # written by gen_money.py (not quantity inputs)
    "ppc_market_price.csv", "ppc_supplier_cost.csv", "ppc_transfer_price_rule.csv",
    "ppc_node_cost_rule.csv", "ppc_edge_cost_rule.csv", "ppc_tariff_rule.csv",
    "ppc_fx_rate.csv", "ppc_node_profit_zone.csv", "ppc_profit_zone_rule.csv",
    "vc_price_rule.csv",
}
NOT_INPUT = {"_result", "README.md"}
SKUS = ("COS_Serum", "COS_Cream")
LEAVES = ("SG_Store", "SG_EC", "SG_Distributor", "TH_Distributor")
CPU = 24


class Capture(WOMPlugin):
    name = "capture"
    label = "capture"

    def on_post_plan(self, sc_tree, weeks, config, **kw):
        self.tree = sc_tree


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def input_hashes(model_dir, money=False):
    """sha256 of the model's input CSVs. money=False: quantity inputs only
    (every CSV except the money files); money=True: the money files only."""
    out = {}
    for fn in sorted(os.listdir(model_dir)):
        p = os.path.join(model_dir, fn)
        if not fn.endswith(".csv") or not os.path.isfile(p):
            continue
        if (fn in MONEY_FILES) == money:
            out[fn] = sha(p)
    return out


def copy_inputs(src, dst):
    """Copy only the input files (no _result, no old PPC / Value Chain outputs)."""
    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for fn in sorted(os.listdir(src)):
        if fn in NOT_INPUT:
            continue
        p = os.path.join(src, fn)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(dst, fn))


def run_case(model_dir, out_dir):
    """Plan + PPC with the model's recommended_plugins. Returns (snapshot, tree)."""
    from tools import run_headless_from_folder as H
    cap = Capture()
    os.makedirs(out_dir, exist_ok=True)
    snap = H.run(model_dir, plugins_spec=None, output_ppc_dir=os.path.join(out_dir, "ppc"),
                 verbose=False, flow_check_dir=os.path.join(out_dir, "flow_check"),
                 extra_plugins=[cap])
    with open(os.path.join(out_dir, "snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1, sort_keys=True, default=str)
    return snap, cap.tree


def lot_record(tree):
    """{product: {leaf: {"demand": [ids], "ship": {week_label: [ids]}}}} + week labels."""
    wl = list(tree.week_labels)
    out = {}
    for prod in tree.products:
        for n in tree.iter_all_nodes(prod):
            if n.node_type != "leaf_out":
                continue
            dem = sorted({l for w in range(len(wl)) for l in n.psi4demand[w][0]})
            ships = {wl[w]: list(ls) for w, ls in (getattr(n, "_actual_ship", None) or {}).items() if ls}
            out.setdefault(prod, {})[n.node_name] = {"demand": dem, "ship": ships}
    return out, wl


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
