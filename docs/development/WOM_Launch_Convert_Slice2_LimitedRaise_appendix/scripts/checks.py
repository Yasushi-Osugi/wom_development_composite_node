# -*- coding: utf-8 -*-
"""投入週の 2 本目 §4 の S1・S2・S4 と、クリームの総納品（C08 を回すかの判断）。計画は回さない。
    python output/strategy_launch2/checks.py"""
import hashlib
import os
import sys

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
from wom.cockpit import cases as C            # noqa: E402
from tools import period_fulfillment as PF    # noqa: E402

W = os.path.join(REPO, "output", "strategy_launch1", "ws")
CASES = ["C01", "C02", "C03", "C04", "C05", "C06", "C07"]
WIN = {"C06": ("2028-W11", "2029-W46"), "C07": ("2026-W37", "2029-W46")}
SAME_DEMAND = {"C06": "C02", "C07": "C03"}
FULL = {"C06": "C04", "C07": "C05"}


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def cap(c):
    return pd.read_csv(os.path.join(C.case_dir(W, c), "model", "capacity_plan.csv"), dtype=str, keep_default_na=False)


def fc(c):
    return pd.read_csv(os.path.join(C.case_dir(W, c), "inputs", C.FIXED_COST_FILE), dtype=str, keep_default_na=False)


def main():
    print("== 状態")
    for c in CASES:
        print(c, C.read_case(W, c)["name"], C.status(W, c)["state"])
    print("== S1 需要（全週・全行）")
    for c, b in SAME_DEMAND.items():
        a = os.path.join(C.case_dir(W, c), "model", "demand_forecast.csv")
        bb = os.path.join(C.case_dir(W, b), "model", "demand_forecast.csv")
        e = os.path.join(C.case_dir(W, c), "model", "market_entry_plan.csv")
        ee = os.path.join(C.case_dir(W, b), "model", "market_entry_plan.csv")
        print(c, "vs", b, "demand", md5(a) == md5(bb), "entry_plan", md5(e) == md5(ee))
    print("== S1 L・F の行")
    for c, b in SAME_DEMAND.items():
        x = fc(c)
        y = fc(b)
        lf = ["th_cream_launch_prep", "th_cream_channel_fee"]
        xs = x[x["cost_item"].isin(lf)][list(y.columns)].reset_index(drop=True)  # the columns of the base case
        ys = y[y["cost_item"].isin(lf)].reset_index(drop=True)
        print(c, "vs", b, "L/F rows equal", xs.equals(ys), "rows", list(x["cost_item"]))
    print("== S2 計画の生産量（C01 と比べ、窓の週だけ違う）")
    base = cap("C01")
    for c, (a, b) in WIN.items():
        x = cap(c)
        if list(x.columns) != list(base.columns) or len(x) != len(base):
            print(c, "形が違う", len(x), len(base)); continue
        m = x.merge(base, on=["sku_id", "node_name", "week"], suffixes=("", "_b"), how="outer", indicator=True)
        assert (m["_merge"] == "both").all()
        diff = m[(m["cap_soft"] != m["cap_soft_b"]) | (m["max_supply"] != m["max_supply_b"])]
        other_cols = [k for k in x.columns if k not in ("sku_id", "node_name", "week", "cap_soft", "max_supply")]
        od = m[[ (m[k] != m[k + "_b"]).any() for k in other_cols].count(True) > 0] if False else None
        inwin = diff["week"].between(a, b)
        print(c, "差の行", len(diff), "窓の中", int(inwin.sum()), "窓の外", int((~inwin).sum()),
              "max_supply の差", int((diff["max_supply"] != diff["max_supply_b"]).sum()),
              "sku", sorted(diff["sku_id"].unique()), "値", sorted(set(zip(diff["cap_soft_b"], diff["cap_soft"]))))
        cw = x[(x["sku_id"] == "COS_Cream") & x["week"].between(a, b)]
        print("   窓の週の数（COS_Cream の行）", len(cw), "全部 12", (cw["cap_soft"] == "12").all())
        for k in other_cols:
            nd = int((m[k] != m[k + "_b"]).sum())
            if nd:
                print("   列", k, "の差", nd)
        f = fc(c)
        r = f[f["cost_item"] == "planned_output_raise"]
        print("   確保費の行", r[["paid_start_week", "paid_end_week", "weekly_amount", "count_outside_report"]].to_dict("records"))
    print("== クリームの総納品・美容液")
    req = {c: PF.case_tables(W, c)["req"] for c in CASES[1:]}
    for c in CASES[1:]:
        r = req[c]
        g = r.groupby("sku_id")[["q1", "delivered", "q5"]].sum()
        print(c, g.to_dict("index"))
    ser = {c: req[c][req[c]["sku_id"] != "COS_Cream"].sort_values(["sku_id", "region", "request_week"])
           [["sku_id", "region", "request_week", "q1", "delivered", "on_time", "late", "q5"]].reset_index(drop=True)
           for c in CASES[1:]}
    for c in CASES[2:]:
        print("美容液", c, "== C02", ser[c].equals(ser["C02"]))
    for c, b in FULL.items():
        x = req[c][req[c]["sku_id"] == "COS_Cream"].set_index(["region", "request_week"])
        y = req[b][req[b]["sku_id"] == "COS_Cream"].set_index(["region", "request_week"])
        d = (x["delivered"] - y["delivered"]).fillna(0)
        q5 = x["q5"]
        print(c, "−", b, "クリームの納品の差", int(d.sum()))
        print("   差の出た行", d[d != 0].to_dict())
        print("   ⑤ が出た行", q5[q5 != 0].to_dict())


if __name__ == "__main__":
    main()
