# -*- coding: utf-8 -*-
"""P2-a measurements M2-M4 (RequestLetter_BSSEAF_Cosmetics_AllocationP2a §3.2).

    python output/bsseaf_cosmetics/p2a_work/measure.py P2a1 P2a2 P1    (from the repository root)

- Re-plans each copy exactly as tools/run_quantity_allocation.py did (the generated demand
  CSV, ppc=False, warmup_real_start = the run's base week) and checks the period equals Q01.json.
- M2: the (5) Lot_IDs (requested, never shipped), their request week and the week the
  factory's demand plan placed them; the factory's planned P vs its limit near both ends.
- M3: FIFO ages with the Part A CLI (tools.shelf_life_check --demand-file --warmup-real-start),
  cross-checked with check_tree() on the re-planned tree.
- M4: period / capacity fixed (Q01.json evidence hashes vs the files now and vs C3a).
Writes p2a_work/measure_<case>.json.
"""
import csv
import hashlib
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
COS = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(COS, "..", ".."))
sys.path[:0] = [REPO]
os.chdir(REPO)

from tools.run_headless_from_folder import run                       # noqa: E402
from tools import shelf_life_check as SL                             # noqa: E402
from wom.model.lot_generator import LotIDGenerator                   # noqa: E402
from wom.model.plan_node import P, S                                 # noqa: E402

PS = os.path.join(COS, "_planning_state")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def measure(case):
    st = json.load(open(os.path.join(PS, case, "Q01.json"), encoding="utf-8"))
    md = os.path.join(COS, case)
    gen, base = st["evidence"]["demand_csv"], st["period"]["warmup_real_start"]
    cap = SL._capture_plugin()
    snap = run(md, verbose=False, demand_file=gen, ppc=False, warmup_real_start=base,
               extra_plugins=[cap], output_ppc_dir=os.path.join(HERE, "_no_ppc", case))
    t = cap.tree
    wl = list(t.week_labels)
    out = {"case": case, "period_replan": snap["period"],
           "period_Q01": st["period"],
           "period_same": snap["period"]["start"] == st["period"]["start"]
           and snap["period"]["weeks"] == st["period"]["weeks"]}
    # M4
    hashes = st["evidence"]["capacity_hashes"]
    out["M4"] = {"Q01_capacity_hashes": hashes,
                 "files_now_same": {f: sha(os.path.join(md, f)) == h for f, h in hashes.items()},
                 "same_as_C3a": {f: sha(os.path.join(md, f)) == sha(os.path.join(COS, "C3a", f))
                                 for f in hashes},
                 "valuation": st["valuation"], "ppc": st["evidence"].get("ppc"),
                 "ppc_output_created": st["evidence"].get("ppc_output_created"),
                 "plugins": st["evidence"].get("plugins"), "commit": st["evidence"].get("commit")}
    # M2
    for prod in t.products:
        nd = {n.node_name: n for n in t.iter_all_nodes(prod)}
        f = nd["Factory_JP"]
        fd = {l: w for w in range(len(wl)) for l in f.psi4demand[w][S]}
        q5 = []
        for n in nd.values():
            if n.node_type != "leaf_out":
                continue
            shipped = {l for ls in (n._actual_ship or {}).values() for l in ls}
            for w in range(len(wl)):
                for l in n.psi4supply[w][S]:
                    if l not in shipped:
                        q5.append({"leaf": n.node_name, "request_week": wl[w], "lot": l,
                                   "in_factory_demand_week": wl[fd[l]] if l in fd else None,
                                   "demand_week_in_id": LotIDGenerator.parse(l)[2]})
        Ps = [len(f.psi4supply[w][P]) for w in range(len(wl))]
        dP = [len(f.psi4demand[w][P]) for w in range(len(wl))]
        lim = [f.shippable_planned(w) for w in range(len(wl))]
        ends = list(range(0, 3)) + list(range(len(wl) - 8, len(wl)))
        out[prod] = {"q5": q5, "q5_by_request_week": dict(sorted(Counter(x["request_week"] for x in q5).items())),
                     "q5_by_factory_week": dict(sorted(Counter(x["in_factory_demand_week"] for x in q5).items())),
                     "factory_P_total": sum(Ps), "factory_demand_P_total": sum(dP),
                     "factory_ends": {wl[w]: {"demand_P": dP[w], "supply_P": Ps[w], "limit": lim[w]} for w in ends},
                     "factory_slack_last8": sum(max(0, (lim[w] or 0) - dP[w]) for w in range(len(wl) - 8, len(wl)))}
    # M3: CLI (Part A) and the same function on the re-planned tree
    sl_out = os.path.join(HERE, "shelf_life", case)
    SL.main(["--model-dir", md, "--max-age-weeks", "52", "--out", sl_out,
             "--demand-file", gen, "--warmup-real-start", base])
    with open(os.path.join(sl_out, "shelf_life_summary.csv"), encoding="utf-8") as fh:
        summ = list(csv.DictReader(fh))
    chk = SL.check_tree(t, 52)
    same = {(s["product"], s["channel"]): (int(s["deliveries"]), int(s["fifo_age_min"]),
                                          int(s["fifo_age_max"]), int(s["over_max_age"])) for s in summ} == {
        (s["product"], s["channel"]): (s["deliveries"], s["fifo_age_min"], s["fifo_age_max"], s["over_max_age"])
        for s in chk["summary"]}
    out["M3"] = {"summary": summ, "cli_equals_check_tree": same, "backlog_end": chk["backlog_end"],
                 "in_transit_end": chk["in_transit_end"]}
    json.dump(out, open(os.path.join(HERE, f"measure_{case}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return out


if __name__ == "__main__":
    for c in sys.argv[1:]:
        o = measure(c)
        print("=====", c, o["period_same"], o["M4"]["files_now_same"], o["M4"]["same_as_C3a"], o["M4"]["valuation"])
        for prod in ("COS_Serum", "COS_Cream"):
            d = o[prod]
            print(prod, "q5", d["q5_by_request_week"], "factory weeks", d["q5_by_factory_week"],
                  "P", d["factory_P_total"], "slack_last8", d["factory_slack_last8"])
            for x in d["q5"]:
                print("   ", x)
        print("M3 cli==check_tree", o["M3"]["cli_equals_check_tree"], "backlog", o["M3"]["backlog_end"])
        for s in o["M3"]["summary"]:
            if s["channel"] == "*":
                print("  ", s["product"], s["deliveries"], s["fifo_age_min"], s["fifo_age_max"], s["over_max_age"])
