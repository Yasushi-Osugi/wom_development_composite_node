# -*- coding: utf-8 -*-
"""P2-a (RequestLetter_BSSEAF_Cosmetics_AllocationP2a §2): make the quantity allocation files.

    python output/bsseaf_cosmetics/p2a_work/make_allocation.py      (from the repository root)

1. Check the contribution margins of the letter §2.1 against the M0 PPC results
   (PPC trial profit per unit + the fixed-cost part added back). Stop if they differ.
2. Count the demand (1) from the copy's demand CSV.
3. P2-a1: per SKU, channels by contribution margin (desc; ties by region name), each
   gets min(demand, rest).  P2-a2: same order, channels within 5% of the group's first
   are one group; a group that does not fit gets the rest in proportion to demand
   (largest remainder; ties by region name).
4. Write allocation_qty_P2a1.csv / allocation_qty_P2a2.csv (sku_id, region, alloc_lots).

Case-specific (the criterion U3 was adopted for the cosmetics case only): not in tools/.
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COS = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(COS, "..", ".."))

SKUS = ("COS_Serum", "COS_Cream")
# letter §2.1 (U3 §2.2): contribution margin per unit, JPY
CM = {
    ("COS_Serum", "SG_Store"): 16573.00, ("COS_Serum", "SG_EC"): 11697.00,
    ("COS_Serum", "TH_Distributor"): 5712.50, ("COS_Serum", "SG_Distributor"): 5682.50,
    ("COS_Cream", "SG_Store"): 13768.00, ("COS_Cream", "SG_EC"): 9605.00,
    ("COS_Cream", "TH_Distributor"): 4730.00, ("COS_Cream", "SG_Distributor"): 4671.50,
}
# the fixed-cost part added back to the PPC trial profit (share of revenue)
ADD_BACK = {"SG_Store": 0.45, "SG_EC": 0.10, "SG_Distributor": 0.0, "TH_Distributor": 0.0}
SUPPLY = {"COS_Serum": 2184, "COS_Cream": 1680}           # (2) total per SKU (= P1, C3a capacity)
GROUP_TOL = 0.05
TOL = 1e-6


def check_cm():
    p = json.load(open(os.path.join(COS, "money_m0_work", "checks_ppc.json"), encoding="utf-8"))
    rows = []
    for r in p["M0"]["sku_channel"]:
        k = (r["product_id"], r["channel"])
        derived = r["unit_profit"] + r["unit_revenue"] * ADD_BACK[r["channel"]]
        rows.append({"sku_id": k[0], "region": k[1], "ppc_unit_profit": r["unit_profit"],
                     "unit_revenue": r["unit_revenue"], "add_back_rate": ADD_BACK[r["channel"]],
                     "derived": derived, "letter": CM[k], "diff": derived - CM[k]})
    bad = [r for r in rows if abs(r["diff"]) > TOL]
    return rows, bad


def demand(model_dir):
    d = {}
    with open(os.path.join(model_dir, "demand_forecast.csv"), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            q = float(r["quantity"])
            if q != int(q):
                raise ValueError(f"non-integer demand {r}")
            k = (r["sku_id"], r["region"])
            d[k] = d.get(k, 0) + int(q)
    return d


def order(sku, dem):
    chans = [k[1] for k in dem if k[0] == sku]
    return sorted(chans, key=lambda ch: (-CM[(sku, ch)], ch))


def p2a1(dem):
    out = {}
    for s in SKUS:
        rest = SUPPLY[s]
        for ch in order(s, dem):
            a = min(dem[(s, ch)], rest)
            out[(s, ch)] = a
            rest -= a
        if rest:
            raise ValueError(f"{s}: supply {SUPPLY[s]} exceeds demand (rest {rest})")
    return out


def groups(sku, dem):
    gs = []
    for ch in order(sku, dem):
        c = CM[(sku, ch)]
        if gs and (CM[(sku, gs[-1][0])] - c) / CM[(sku, gs[-1][0])] < GROUP_TOL:
            gs[-1].append(ch)
        else:
            gs.append([ch])
    return gs


def p2a2(dem):
    out, gsave = {}, {}
    for s in SKUS:
        rest = SUPPLY[s]
        gsave[s] = groups(s, dem)
        for g in gsave[s]:
            need = sum(dem[(s, ch)] for ch in g)
            if need <= rest:
                for ch in g:
                    out[(s, ch)] = dem[(s, ch)]
                rest -= need
                continue
            # proportional to demand, largest remainder (ties by region name)
            quota = {ch: rest * dem[(s, ch)] / need for ch in g}
            base = {ch: int(quota[ch]) for ch in g}
            left = rest - sum(base.values())
            for ch in sorted(g, key=lambda ch: (-(quota[ch] - base[ch]), ch))[:left]:
                base[ch] += 1
            out.update({(s, ch): base[ch] for ch in g})
            rest = 0
        if rest:
            raise ValueError(f"{s}: supply exceeds demand")
    return out, gsave


def write(path, alloc):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["sku_id", "region", "alloc_lots"])
        for (s, r) in sorted(alloc):
            w.writerow([s, r, alloc[(s, r)]])


def main():
    rows, bad = check_cm()
    for r in rows:
        print(f"  {r['sku_id']:<10}{r['region']:<16} PPC {r['ppc_unit_profit']:>10.2f} + "
              f"{r['unit_revenue']:>9.2f} x {r['add_back_rate']:.2f} = {r['derived']:>10.2f}"
              f"  letter {r['letter']:>10.2f}  diff {r['diff']:.6f}")
    if bad:
        print("STOP: the contribution margins of the letter §2.1 are not reproduced from M0", bad)
        return 1
    res = {"cm_check": rows}
    for case, fn in (("P2a1", p2a1), ("P2a2", p2a2)):
        md = os.path.join(COS, case)
        dem = demand(md)
        r = fn(dem)
        alloc, gs = (r if isinstance(r, tuple) else (r, None))
        path = os.path.join(md, f"allocation_qty_{case}.csv")
        write(path, alloc)
        res[case] = {"demand": {f"{k[0]}|{k[1]}": v for k, v in sorted(dem.items())},
                     "alloc": {f"{k[0]}|{k[1]}": v for k, v in sorted(alloc.items())},
                     "unallocated": {f"{k[0]}|{k[1]}": dem[k] - alloc[k] for k in sorted(dem)
                                     if dem[k] - alloc[k]},
                     "supply_by_sku": {s: sum(v for k, v in alloc.items() if k[0] == s) for s in SKUS},
                     "order": {s: order(s, dem) for s in SKUS},
                     "groups": gs, "file": os.path.relpath(path, REPO).replace("\\", "/")}
        print(case, res[case]["alloc"], "unallocated", res[case]["unallocated"],
              "groups", gs if gs else "-")
    json.dump(res, open(os.path.join(HERE, "allocation_record.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
