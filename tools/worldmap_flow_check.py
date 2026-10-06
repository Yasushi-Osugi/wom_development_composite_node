# -*- coding: utf-8 -*-
"""
tools/worldmap_flow_check.py — World Map の流れの照合（RequestLetter_WorldMap_ActualFlows 受入 1）

    # Cookie・alloc：地図の 区間 × 週 の lot 数 ＝ tools/valuechain_run.py の vc_edge_flows.csv（全行）
    python -m tools.worldmap_flow_check --model-dir data/sample/Cookie-jp-2026 \
        --vc-run output/valuechain/Cookie-jp-2026/run_1

    # ev-thailand：区間ごとの全期間の lot 数 ＝ LOVEM の観測の実出荷の合計
    python -m tools.worldmap_flow_check --model-dir data/sample/ev-thailand-2026 \
        --lovem-run output/lovem/ev-thailand-2026/run_worldmap

地図の数字は、World Map タブと同じ関数（records.build_records → flows.FlowData）で作る。計画は
headless で、照合する相手（vc の run・LOVEM の run）と同じプラグインで立てる。

LOVEM の側は、出荷の記録を使わずに LOVEM の事象だけから区間を作る：受け手は `arrival` の事象
（`detail.from_node_id` が送り手）、supply point から出た lot の物理の送り手は、その lot の
`ship_to_bridge` の関係（MOM の actual_ship → supply point の bridge_arrival）の送り手の MOM。計画の期間の後に着く出荷は `arrival` が無い
ので、送り手ごとの件数を別に数える（地図の側は、その lot の需要の市場で受け手を決めている）。
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import tempfile
from collections import Counter

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def map_flows(model_dir: str, plugins: str):
    from wom.valuechain.run import plan_model
    from wom.valuechain.records import build_records
    from wom.worldmap_ne.flows import FlowData, records_problem
    sc_tree, _snap, plugins, _mode = plan_model(model_dir, tempfile.mkdtemp(prefix="wm_ppc_"), plugins)
    rec = build_records(sc_tree, "worldmap_check")
    prob = records_problem(rec)
    if prob:
        raise SystemExit(f"records problem: {prob}")
    return FlowData.from_records(rec, sc_tree), rec


def check_vc(model_dir: str, vc_run: str) -> dict:
    with open(os.path.join(vc_run, "vc_run_info.json"), encoding="utf-8") as f:
        info = json.load(f)
    F, rec = map_flows(model_dir, info["plugins"])
    vc = pd.read_csv(os.path.join(vc_run, "vc_edge_flows.csv"))
    vc = vc.groupby(["product", "edge", "ship_week_index"], as_index=False)["lots"].sum()
    mp = F.edge_week_table()
    m = vc.merge(mp, on=["product", "edge", "ship_week_index"], how="outer", suffixes=("_vc", "_map"))
    bad = m[(m["lots_vc"] != m["lots_map"])]
    return {"model": os.path.basename(model_dir), "vc_run": vc_run, "vc_code_sha": info["code"]["code_sha"],
            "plugins": info["plugins"], "vc_rows": len(vc), "map_rows": len(mp), "mismatch_rows": len(bad),
            "lots_vc": int(vc["lots"].sum()), "lots_map": int(mp["lots"].sum()),
            "examples": bad.head(5).to_dict("records"), "ok": len(bad) == 0 and len(vc) == len(mp)}


def check_lovem(model_dir: str, lovem_run: str) -> dict:
    with open(os.path.join(lovem_run, "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    nodes = pd.read_csv(os.path.join(lovem_run, "nodes.csv"))
    name = dict(zip(nodes["node_id"], nodes["node_name"]))
    ships, arrivals, bridge_from = Counter(), Counter(), {}
    arrived_from = Counter()
    with gzip.open(os.path.join(lovem_run, "events.jsonl.gz"), "rt", encoding="utf-8") as f:
        evs = [json.loads(line) for line in f]
    # MOM -> supply point: the bridge_arrival event has no sender; the ship_to_bridge relation
    # links the MOM's actual_ship event (its node) to the bridge_arrival event (its lot)
    by_id = {e["event_id"]: e for e in evs if e["event_type"] in ("actual_ship", "bridge_arrival")}
    with gzip.open(os.path.join(lovem_run, "relations.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("relation_type") != "ship_to_bridge":
                continue
            ship, arr = by_id[r["from_ref"]], by_id[r["to_ref"]]
            bridge_from[(arr["product_id"], arr["lot_id"])] = name[ship["node_id"]]
    for e in evs:
        t = e["event_type"]
        if t == "actual_ship":
            ships[(e["product_id"], name[e["node_id"]])] += 1
        elif t == "arrival":
            frm = name[e["detail"]["from_node_id"]]
            arrived_from[(e["product_id"], frm)] += 1
            ntype = nodes.loc[nodes["node_id"] == e["detail"]["from_node_id"], "node_type"].iloc[0]
            if ntype == "supply_point":
                frm = bridge_from[(e["product_id"], e["lot_id"])]
            arrivals[(e["product_id"], f"{frm}->{name[e['node_id']]}")] += 1
    plugins = ",".join(man.get("plugins", [])) or "none"
    F, rec = map_flows(model_dir, plugins)
    mine = Counter()
    mine_out = Counter()      # map: shipments that arrive after the horizon, by (product, sender)
    for s in rec.shipments:
        if s.edge:
            if s.arrival_in_horizon:
                mine[(s.product, s.edge)] += 1
            else:
                mine_out[(s.product, s.node)] += 1
    total_map = {k: int(F.ship[:, i].sum()) for i, k in enumerate(F.edge_keys)}
    rows = []
    for k in sorted(set(arrivals) | set(mine)):
        rows.append({"product": k[0], "edge": k[1], "lovem_arrived": arrivals.get(k, 0),
                     "map_arrived": mine.get(k, 0), "map_total": total_map.get(k, 0)})
    df = pd.DataFrame(rows)
    # shipments with no arrival in LOVEM (after the horizon), by sender: ships - arrivals
    after = []
    for (p, n), c in ships.items():
        a = arrived_from.get((p, n), 0)
        node_rows = nodes[(nodes["product_id"] == p) & (nodes["node_name"] == n)]
        if node_rows.empty or node_rows["node_type"].iloc[0] == "leaf_out":
            continue                     # consumer sales: not an edge
        if node_rows["node_type"].iloc[0] == "mom" and node_rows["parent_id"].isna().iloc[0]:
            continue                     # MOM root -> supply point: the virtual hand-off
        if c - a or mine_out.get((p, n), 0):
            after.append({"product": p, "sender": n, "lovem_no_arrival": c - a,
                          "map_after_horizon": mine_out.get((p, n), 0)})
    bad = df[df["lovem_arrived"] != df["map_arrived"]]
    bad_after = [x for x in after if x["lovem_no_arrival"] != x["map_after_horizon"]]
    return {"model": os.path.basename(model_dir), "lovem_run": lovem_run, "lovem_code_sha": man.get("code_sha"),
            "lovem_lot_flow_mode": man.get("lot_flow_mode"), "plugins": plugins,
            "edges": len(df), "mismatch_edges": len(bad), "table": df.to_dict("records"),
            "after_horizon": after, "after_horizon_mismatch": len(bad_after),
            "ok": len(bad) == 0 and not bad_after}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--vc-run")
    ap.add_argument("--lovem-run")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    os.chdir(REPO)
    res = check_vc(a.model_dir, a.vc_run) if a.vc_run else check_lovem(a.model_dir, a.lovem_run)
    out = a.out or os.path.join("output", "worldmap_check", f"flow_check_{res['model']}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    short = {k: v for k, v in res.items() if k not in ("table", "examples", "after_horizon")}
    print(json.dumps(short, ensure_ascii=False, default=str))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
