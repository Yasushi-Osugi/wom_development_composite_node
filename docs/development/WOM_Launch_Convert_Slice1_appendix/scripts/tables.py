# -*- coding: utf-8 -*-
"""投入週の 1 本目 §4 の表（報告書）。案の実行の出力と strategy_compare の出力を読むだけ（計画は回さない）。
    python output/strategy_launch1/tables.py
出力：output/strategy_launch1/tables.md と CSV（key_year.csv・th_continuation.csv・money.csv・breakeven.csv・
rep_weeks.csv・inventory_age.csv・where.csv）"""
import os
import sys

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
from wom.cockpit import cases as C            # noqa: E402
from tools import compare_scenarios as CS     # noqa: E402
from tools import period_fulfillment as PF    # noqa: E402

W = os.path.join(REPO, "output", "strategy_launch1", "ws")
O = os.path.join(REPO, "output", "strategy_launch1")
CASES = ["C02", "C03", "C04", "C05"]
NAMES = {"C02": "遅く入る（LATE）", "C03": "早く入る（EARLY）", "C04": "遅く入る＋増産", "C05": "早く入る＋増産"}
PAIRS = [("C02", "C03", "compare_C02_C03"), ("C04", "C05", "compare_C04_C05")]
TH = ("COS_Cream", "TH_Distributor")
CONT = ("2028-W01", "2029-W52")          # the continuing demand: request weeks
FEE_WEEKS = {"C02": 104, "C03": 130, "C04": 104, "C05": 130}
LEVEL = {"低": {"L": 100000, "F": 40000, "R": 10000}, "中": {"L": 300000, "F": 50000, "R": 40000},
         "高": {"L": 600000, "F": 60000, "R": 132000}}
RAISE_WEEKS = 173
RATES = ["なし", "5%", "10%", "15%"]
ALPHAS = [1.0, 0.5, 0.0]
REP_WEEKS = ["2027-W26", "2027-W27", "2027-W39", "2027-W40", "2028-W01", "2028-W13", "2028-W14"]


def fmt(v, sign=False):
    return f"{v:+,.0f}" if sign else f"{v:,.0f}"


def load():
    runs, req = {}, {}
    for c in CASES:
        cd = C.case_dir(W, c)
        rr = C.read_case(W, c)["run"]
        runs[c] = CS.load_run(os.path.join(cd, "run"), os.path.join(cd, rr["money_model"]))
        req[c] = PF.case_tables(W, c)["req"]
    return runs, req


def key_year(req):
    rows = []
    for c in CASES:
        r = req[c].assign(year=req[c]["request_week"].str[:4])
        g = r.groupby(["sku_id", "region", "year"])[["q1", "q2", "q3", "delivered", "on_time", "early", "late", "q5"]].sum()
        bad = g[(g["q1"] != g["q2"] + g["q3"]) | (g["q2"] != g["delivered"] + g["q5"])]
        if len(bad):
            raise SystemExit(f"{c}: ①＝②＋③ か ②＝④＋⑤ が合わない行 {len(bad)}")
        for (s, rg, y), v in g.iterrows():
            rows.append({"case": c, "sku_id": s, "region": rg, "year": y, **{k: int(x) for k, x in v.items()}})
    return pd.DataFrame(rows)


def th_continuation(runs, req):
    """§4.2: the continuing TH cream demand (request weeks 2028-W01..2029-W52). The early plan's extra lots in
    those weeks are the Lot_IDs whose sequence number is above the late plan's quantity of that week."""
    base = req["C02"]
    bq = {w: int(q) for w, q in zip(base[(base["sku_id"] == TH[0]) & (base["region"] == TH[1])]["request_week"],
                                    base[(base["sku_id"] == TH[0]) & (base["region"] == TH[1])]["q1"])}
    out = []
    for late, early, _d in PAIRS:
        rl = req[late]
        kl = rl[(rl["sku_id"] == TH[0]) & (rl["region"] == TH[1]) & rl["request_week"].between(*CONT)]
        F = int(kl["delivered"].sum())
        re_ = req[early]
        ke = re_[(re_["sku_id"] == TH[0]) & (re_["region"] == TH[1]) & re_["request_week"].between(*CONT)]
        ship = runs[early]["ship"]
        sold = set(ship.loc[ship["kind"] == CS.K_CONSUMER, "lot_id"])
        extra, extra_dlv = 0, 0
        for w, q in zip(ke["request_week"], ke["q1"]):
            for seq in range(bq.get(w, 0) + 1, int(q) + 1):
                extra += 1
                extra_dlv += f"{TH[0]}:{TH[1]}:{w}:{seq:05d}" in sold
        De = int(ke["delivered"].sum())
        cont = De - extra_dlv
        cons = De - extra
        out.append({"pair": f"{early} − {late}", "late_delivered_F_TH": F, "early_delivered": De,
                    "extra_demand": extra, "extra_delivered_by_seq": extra_dlv,
                    "early_continuing_by_seq": cont, "early_continuing_conservative": cons,
                    "status_by_seq": "保護" if cont >= F else "保護未確認",
                    "status_conservative": "保護" if cons >= F else "保護未確認"})
    return pd.DataFrame(out)


def money():
    rows, be = [], []
    for late, early, d in PAIRS:
        s = pd.read_csv(os.path.join(O, d, "strategy_summary.csv")).set_index("case")
        raise_ = "cost_planned_output_raise" in s.columns and s.loc[late, "cost_planned_output_raise"] > 0
        for c in (late, early):
            for lv, k in LEVEL.items():
                L = k["L"]
                F = k["F"] * FEE_WEEKS[c]
                R = k["R"] * RAISE_WEEKS if raise_ else 0
                for rt in RATES:
                    H = float(s.loc[c, f"H_{rt}"])
                    rows.append({"pair": d, "case": c, "level": lv, "holding": rt, "P0": float(s.loc[c, "P0"]),
                                 "L": L, "F": F, "R": R, "H": H, "A": float(s.loc[c, "P0"]) - L - F - R - H,
                                 "E_store": float(s.loc[c, "item_store_operating"])})
        dP0 = float(s.loc[early, "P0"] - s.loc[late, "P0"])
        dE = float(s.loc[early, "item_store_operating"] - s.loc[late, "item_store_operating"])
        for rt in RATES:
            dH = float(s.loc[early, f"H_{rt}"] - s.loc[late, f"H_{rt}"])
            for a in ALPHAS:
                num = dP0 + (1 - a) * dE - 0 - 0 - dH
                be.append({"pair": d, "holding": rt, "alpha": a, "dP0": dP0, "dE_store": dE, "dH": dH,
                           "numerator": num, "f_star": num / 26 if num > 0 else None})
    m = pd.DataFrame(rows)
    # the A differences per pair (ΔA = ΔP0 − ΔL − ΔF − ΔR − ΔH ＋ (1 − α) ΔE)
    da = []
    for late, early, d in PAIRS:
        for lv in LEVEL:
            for rt in RATES:
                a_ = m[(m["pair"] == d) & (m["level"] == lv) & (m["holding"] == rt)].set_index("case")
                for al in ALPHAS:
                    dd = (a_.loc[early, "A"] - a_.loc[late, "A"]) + (1 - al) * (a_.loc[early, "E_store"] - a_.loc[late, "E_store"])
                    da.append({"pair": d, "level": lv, "holding": rt, "alpha": al,
                               "dP0": a_.loc[early, "P0"] - a_.loc[late, "P0"], "dL": a_.loc[early, "L"] - a_.loc[late, "L"],
                               "dF": a_.loc[early, "F"] - a_.loc[late, "F"], "dR": a_.loc[early, "R"] - a_.loc[late, "R"],
                               "dH": a_.loc[early, "H"] - a_.loc[late, "H"], "dA": dd})
    # the mid / 100% column equals strategy_compare's dA (a check of this arithmetic)
    for late, early, d in PAIRS:
        s = pd.read_csv(os.path.join(O, d, "strategy_summary.csv")).set_index("case")
        for rt in RATES:
            mine = [x["dA"] for x in da if x["pair"] == d and x["level"] == "中" and x["holding"] == rt and x["alpha"] == 1.0][0]
            if abs(mine - float(s.loc[early, f"dA_{rt}_vs_base"])) > 0.5:
                raise SystemExit(f"{d} {rt}: ΔA の手計算 {mine} が strategy_compare {s.loc[early, f'dA_{rt}_vs_base']} と違う")
            for al in ALPHAS:
                mine = [x["dA"] for x in da if x["pair"] == d and x["level"] == "中" and x["holding"] == rt and x["alpha"] == al][0]
                ref = float(s.loc[early, f"dA_{rt}_avoid{al * 100:g}%_vs_base"])
                if abs(mine - ref) > 0.5:
                    raise SystemExit(f"{d} {rt} α={al}: ΔA {mine} ≠ {ref}")
    return m, pd.DataFrame(da), pd.DataFrame(be)


def rep_weeks(req):
    rows = []
    for c in CASES:
        r = req[c]
        k = r[(r["sku_id"] == TH[0]) & (r["region"] == TH[1])].set_index("request_week")
        fc = pd.read_csv(os.path.join(C.case_dir(W, c), "inputs", C.FIXED_COST_FILE), dtype=str, keep_default_na=False)
        for w in REP_WEEKS:
            x = k.loc[w] if w in k.index else None
            act = [it for it, a, b in zip(fc["cost_item"], fc["paid_start_week"], fc["paid_end_week"]) if a <= w <= b]
            rows.append({"case": c, "week": w, "q1": int(x["q1"]) if x is not None else 0,
                         "on_time": int(x["on_time"]) if x is not None else 0, "late": int(x["late"]) if x is not None else 0,
                         "q5": int(x["q5"]) if x is not None else 0, "cost_rows": len(act), "cost_items": ";".join(act)})
    return pd.DataFrame(rows)


def inventory_age(runs):
    rows = []
    for c in CASES:
        inv = runs[c]["inv"]
        inv = inv[(inv["external"].astype(int) == 0) & (inv["product"] == "COS_Cream")]
        by = inv.groupby("week_index")["lots"].sum()
        sh = runs[c]["shelf"]
        sc = sh[(sh["product"] == "COS_Cream") & (sh["channel"] == "*")]
        rows.append({"case": c, "cream_lot_weeks": int(by.sum()), "cream_end": int(by.iloc[-1]) if len(by) else 0,
                     "cream_max_week": int(by.max()) if len(by) else 0,
                     "age_max_cream": sc["fifo_age_max"].iloc[0] if len(sc) else "",
                     "over52_cream": sc["over_max_age"].iloc[0] if len(sc) else ""})
    return pd.DataFrame(rows)


def where(runs, req):
    rows, lots = [], []
    for late, early, d in PAIRS:
        my = pd.read_csv(os.path.join(O, d, f"market_year_{early}.csv"))
        my = my[(my[["on_time_diff", "delivered_diff", "q5_diff"]] != 0).any(axis=1)]
        for r in my.itertuples():
            rows.append({"pair": d, "sku_id": r.sku_id, "region": r.region, "year": r.year,
                         "q1_diff": r.q1_diff, "delivered_diff": r.delivered_diff, "q5_diff": r.q5_diff})
        sl = runs[late]["ship"]
        se = runs[early]["ship"]
        dl = dict(zip(sl.loc[sl["kind"] == CS.K_CONSUMER, "lot_id"], sl.loc[sl["kind"] == CS.K_CONSUMER, "ship_week"]))
        de = dict(zip(se.loc[se["kind"] == CS.K_CONSUMER, "lot_id"], se.loc[se["kind"] == CS.K_CONSUMER, "ship_week"]))
        new = sorted(l for l in de if l not in dl and l.startswith(f"{TH[0]}:{TH[1]}:2027"))
        lost = sorted(l for l in dl if l not in de)
        if new:
            lots.append({"pair": d, "kind": "早い案で届いた（遅い案には無い需要）", "lot_id": new[0], "ship_week_early": de[new[0]],
                         "ship_week_late": ""})
        if lost:
            lots.append({"pair": d, "kind": "遅い案で届き、早い案で届かなかった", "lot_id": lost[0], "ship_week_early": "",
                         "ship_week_late": dl[lost[0]]})
    return pd.DataFrame(rows), pd.DataFrame(lots)


def main():
    runs, req = load()
    ky = key_year(req)
    ky.to_csv(os.path.join(O, "key_year.csv"), index=False, encoding="utf-8-sig")
    tc = th_continuation(runs, req)
    tc.to_csv(os.path.join(O, "th_continuation.csv"), index=False, encoding="utf-8-sig")
    m, da, be = money()
    m.to_csv(os.path.join(O, "money_cases.csv"), index=False, encoding="utf-8-sig")
    da.to_csv(os.path.join(O, "money_diff.csv"), index=False, encoding="utf-8-sig")
    be.to_csv(os.path.join(O, "breakeven.csv"), index=False, encoding="utf-8-sig")
    rw = rep_weeks(req)
    rw.to_csv(os.path.join(O, "rep_weeks.csv"), index=False, encoding="utf-8-sig")
    ia = inventory_age(runs)
    ia.to_csv(os.path.join(O, "inventory_age.csv"), index=False, encoding="utf-8-sig")
    wh, lots = where(runs, req)
    wh.to_csv(os.path.join(O, "where.csv"), index=False, encoding="utf-8-sig")
    lots.to_csv(os.path.join(O, "where_lots.csv"), index=False, encoding="utf-8-sig")
    print("== TH cream key x year"); print(ky[(ky["sku_id"] == TH[0]) & (ky["region"] == TH[1])].to_string(index=False))
    tot = ky.groupby(["case", "sku_id", "region"])[["q1", "delivered", "q5"]].sum().reset_index()
    print("== key totals"); print(tot.pivot_table(index=["sku_id", "region"], columns="case", values=["delivered", "q5"]).to_string())
    print("== TH continuation"); print(tc.to_string(index=False))
    print("== money diff (mid)"); print(da[(da["level"] == "中")].to_string(index=False))
    print("== money diff (low/high, holding none)"); print(da[(da["holding"] == "なし")].to_string(index=False))
    print("== breakeven"); print(be.to_string(index=False))
    print("== rep weeks"); print(rw.to_string(index=False))
    print("== inventory/age"); print(ia.to_string(index=False))
    print("== where"); print(wh.to_string(index=False)); print(lots.to_string(index=False))


if __name__ == "__main__":
    main()
