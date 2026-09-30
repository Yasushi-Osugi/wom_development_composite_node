# -*- coding: utf-8 -*-
"""
tools/ev_update_kitting_trial.py — ev-thailand-2026_update の組立（2 部材 → 1 完成品）の測定
（RequestLetter_iPhoneWarmup_EVUpdateKitting_S2 B1・B3。測定だけ。原本には書かない）

    python -m tools.ev_update_kitting_trial --out output/iphone_evupdate_s2/B

モデルのコピーで、次の 3 つの構成を実行する（identity と legacy）:

  after      今の原本（部材置場 Platform_Unit_Assy_Yard・Motor_Unit_Assy_Yard を入れた構成）
  before     置場を外した構成（部材を工場へ直接つなぐ。修正前の構成の再現）
  delay      今の構成で、モーター（Motor_Unit_Assy）の能力を 2026-W20〜W22 の 3 週だけ
             100／週に絞る（片方の部材の遅着。identity だけ）

出力（<out>/ の下）:
  <条件>_<方式>/                 コピーしたモデル（_out_ppc/・_out_flow_check/ を含む。
                                 flow_check_kitting.csv が表 3＝部材の消費と完成の照合）
  <条件>_<方式>__psi_nodes.csv   ノードごとの P（のべ・異なる ID）・S・実出荷・期末 I・期末 CO
  <条件>_<方式>__supply_duplicates.csv  供給側の同じ ID の重複（ノード・週・ID・件数）
  <条件>_<方式>__leaf_lots.csv.gz／__backlog_lots.csv  市場 leaf の全 ID の結果
  delay_identity__late_kits.csv  遅れた部材の ID ごとの履歴（両部材の到着週・完成週・出荷週）
  summary.json                   条件ごとの集計
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys

S, CO, I, P = 0, 1, 2, 3
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL = "ev-thailand-2026_update"
YARDS = ("Platform_Unit_Assy_Yard", "Motor_Unit_Assy_Yard")
DELAY_WEEKS = ("2026-W20", "2026-W21", "2026-W22")
DELAY_CAP = 100


def _remove_yards(model_dir):
    path = os.path.join(model_dir, "sc_tree_master.csv")
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    h = rows[0]
    ni, pi = h.index("node_name"), h.index("parent_node")
    out = [h]
    for r in rows[1:]:
        if r[ni] in YARDS:
            continue
        if r[pi] in YARDS:
            r[pi] = "Factory_Local_TH"
        out.append(r)
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(out)


def _delay_motor(model_dir):
    path = os.path.join(model_dir, "capacity_plan.csv")
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    h = rows[0]
    ni, wi, mi = h.index("node_name"), h.index("week"), h.index("max_supply")
    for r in rows[1:]:
        if r[ni] == "Motor_Unit_Assy" and r[wi] in DELAY_WEEKS:
            r[mi] = str(DELAY_CAP)
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def _first_week(node, bucket, n):
    out = {}
    for w in range(n):
        for lot in node.psi4supply[w][bucket]:
            out.setdefault(lot, w)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=os.path.join("output", "iphone_evupdate_s2", "B"))
    a = ap.parse_args(argv)
    from tools.warmup_trial import run_trial, _Hooks
    os.makedirs(a.out, exist_ok=True)
    summary = {}
    for cond, prep, modes in (("after", None, ("identity", "legacy")),
                              ("before", _remove_yards, ("identity", "legacy")),
                              ("delay", _delay_motor, ("identity",))):
        for mode in modes:
            tag = f"{cond}_{mode}"
            h = _Hooks(); h.install()
            try:
                r = run_trial(MODEL, None, a.out, mode=mode, plugins="safe", hooks=h, prepare=prep)
                tree, fres = h.store["tree"], h.store["fres"]
            finally:
                h.uninstall()
            d = os.path.join(a.out, tag)
            if os.path.exists(d):
                shutil.rmtree(d)
            os.rename(os.path.join(a.out, f"{MODEL}__wNone"), d)
            for suf in ("__leaf_lots.csv.gz", "__backlog_lots.csv"):
                os.replace(os.path.join(a.out, f"{MODEL}__wNone{suf}"), os.path.join(a.out, tag + suf))
            n, wl = tree.num_weeks(), list(tree.week_labels)
            dups = [x for p in fres.values() for x in p.supply_duplicate_ids]
            with open(os.path.join(a.out, f"{tag}__supply_duplicates.csv"), "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f); w.writerow(["node_id", "week", "lot_id", "count"]); w.writerows(dups)
            rows = []
            for prod in tree.products:
                for nd in tree.iter_all_nodes(prod):
                    act = getattr(nd, "_actual_ship", None) or {}
                    pl = [x for w in range(n) for x in nd.psi4supply[w][P]]
                    rows.append({"product": prod, "node": nd.node_name, "type": nd.node_type,
                                 "P_sum": len(pl), "P_distinct": len(set(pl)),
                                 "S_sum": sum(len(nd.psi4supply[w][S]) for w in range(n)),
                                 "ship_sum": sum(len(v) for v in act.values()),
                                 "I_end": len(nd.psi4supply[n - 1][I]),
                                 "I_max": max(len(nd.psi4supply[w][I]) for w in range(n)),
                                 "I_weeks_sum": sum(len(nd.psi4supply[w][I]) for w in range(n)),
                                 "CO_end": len(nd.psi4supply[n - 1][CO]),
                                 "CO_max": max(len(nd.psi4supply[w][CO]) for w in range(n))})
            with open(os.path.join(a.out, f"{tag}__psi_nodes.csv"), "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
            kit_csv = os.path.join(d, "_out_flow_check", "flow_check_kitting.csv")
            kitting = []
            if os.path.exists(kit_csv):
                with open(kit_csv, encoding="utf-8-sig", newline="") as f:
                    kitting = list(csv.DictReader(f))
            r["supply_duplicates"] = len(dups)
            r["supply_duplicate_example"] = dups[0] if dups else None
            r["kitting"] = kitting
            r["psi_local"] = [x for x in rows if x["product"] == "EVmaker_Local"]
            if cond == "delay":
                node = {nd.node_name: nd for nd in tree.iter_all_nodes("EVmaker_Local")}
                fac, plat, motor = node["Factory_Local_TH"], node[YARDS[0]], node[YARDS[1]]
                pa, ma, kit = _first_week(plat, P, n), _first_week(motor, P, n), _first_week(fac, P, n)
                ship = {}
                for w_, lots in fac._actual_ship.items():
                    for lot in lots:
                        ship.setdefault(lot, w_)
                req = _first_week(fac, S, n)
                late = [lot for lot in kit if ma[lot] > pa[lot]]
                with open(os.path.join(a.out, f"{tag}__late_kits.csv"), "w", encoding="utf-8-sig", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["lot_id", "factory_request_week", "platform_arrival_week",
                                "motor_arrival_week", "kit_week", "factory_ship_week",
                                "platform_waiting_weeks", "kit_before_motor"])
                    for lot in late:
                        w.writerow([lot, wl[req[lot]], wl[pa[lot]], wl[ma[lot]], wl[kit[lot]],
                                    wl[ship[lot]] if lot in ship else "", ma[lot] - pa[lot],
                                    int(kit[lot] < ma[lot])])
                r["delay"] = {
                    "weeks": list(DELAY_WEEKS), "motor_cap": DELAY_CAP,
                    "lots_with_motor_later_than_platform": len(late),
                    "kits_before_motor_arrival": sum(1 for lot in late if kit[lot] < ma[lot]),
                    "ships_before_motor_arrival": sum(1 for lot in late if lot in ship and ship[lot] < ma[lot]),
                    "late_lots_completed": sum(1 for lot in late if lot in kit),
                    "max_platform_waiting_weeks": max((ma[lot] - pa[lot] for lot in late), default=0),
                    "platform_yard_I_max": max(len(plat.psi4supply[w][I]) for w in range(n)),
                    "motor_yard_I_max": max(len(motor.psi4supply[w][I]) for w in range(n)),
                    "factory_CO_max": max(len(fac.psi4supply[w][CO]) for w in range(n)),
                    "factory_CO_end": len(fac.psi4supply[n - 1][CO]),
                }
            summary[tag] = r
            print(f"{tag}: market={r['market']} flow_ng={r['flow_ng']} {r['ng_rows']} dups={len(dups)} "
                  f"rev={r['ppc']['revenue_base']} cost={r['ppc']['cost_base']}"
                  + (f" delay={r['delay']}" if cond == "delay" else ""), flush=True)
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
