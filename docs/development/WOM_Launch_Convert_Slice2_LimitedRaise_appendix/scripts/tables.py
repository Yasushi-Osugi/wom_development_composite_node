# -*- coding: utf-8 -*-
"""投入週の 2 本目 §2 の表（報告書）。案の実行の出力と strategy_compare の出力を読むだけ（計画は回さない）。
    python output/strategy_launch2/tables.py
出力：output/strategy_launch2/ の CSV（key_year・raise_usage・raise_usage_weeks・money_cases・money_diff・
money_decomp・inventory_age・protect_summary）"""
import os
import sys

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO)
from wom.cockpit import cases as C            # noqa: E402
from tools import compare_scenarios as CS     # noqa: E402
from tools import period_fulfillment as PF    # noqa: E402

W = os.path.join(REPO, "output", "strategy_launch1", "ws")
O1 = os.path.join(REPO, "output", "strategy_launch1")
O = os.path.join(REPO, "output", "strategy_launch2")
CASES = ["C02", "C04", "C05", "C06", "C07"]
RUNS = ["C04", "C05", "C06", "C07"]
TH = ("COS_Cream", "TH_Distributor")
FEE_WEEKS = {"C02": 104, "C04": 104, "C05": 130, "C06": 104, "C07": 130}
# the weeks whose planned output (cap_soft) was raised 11 -> 12 = the paid weeks
WINDOW = {"C02": None, "C04": ("2026-W37", "2029-W52"), "C05": ("2026-W37", "2029-W52"),
          "C06": ("2028-W11", "2029-W46"), "C07": ("2026-W37", "2029-W46")}
LIMITED = {"C06", "C07"}                    # the limited-window cases (the 15% premium applies only to these)
LEVEL = {"低": {"L": 100000, "F": 40000, "R": 10000}, "中": {"L": 300000, "F": 50000, "R": 40000},
         "高": {"L": 600000, "F": 60000, "R": 132000}}
PREMIUM = {"0%": 1.0, "15%": 1.15}
HOLD = ["なし", "10%"]
DIFFS = [("C04", "C06"), ("C05", "C07"), ("C06", "C07"), ("C02", "C07"), ("C02", "C06")]


def summaries():
    s = {}
    for d in ("compare_C04_C06", "compare_C05_C07", "compare_C06_C07"):
        t = pd.read_csv(os.path.join(O, d, "strategy_summary.csv")).set_index("case")
        for c in t.index:
            s.setdefault(c, t.loc[c])
    t = pd.read_csv(os.path.join(O1, "compare_C02_C04", "strategy_summary.csv")).set_index("case")
    s["C02"] = t.loc["C02"]
    # the same case read from two compare runs must agree
    for d in ("compare_C04_C06", "compare_C05_C07", "compare_C06_C07"):
        t = pd.read_csv(os.path.join(O, d, "strategy_summary.csv")).set_index("case")
        for c in t.index:
            for k in ("P0", "H_10%", "item_store_operating"):
                if abs(float(t.loc[c, k]) - float(s[c][k])) > 0.5:
                    raise SystemExit(f"{c} {k}: {d} の値が違う")
    return s


def windows_weeks(c):
    w = WINDOW[c]
    if w is None:
        return 0
    cap = pd.read_csv(os.path.join(C.case_dir(W, c), "model", "capacity_plan.csv"), dtype=str, keep_default_na=False)
    cw = cap[(cap["sku_id"] == "COS_Cream") & cap["week"].between(*w)]
    if not (cw["cap_soft"] == "12").all():
        raise SystemExit(f"{c}: 窓の週に 12 でない行")
    fc = pd.read_csv(os.path.join(C.case_dir(W, c), "inputs", C.FIXED_COST_FILE), dtype=str, keep_default_na=False)
    r = fc[fc["cost_item"] == "planned_output_raise"]
    if (r["paid_start_week"].iloc[0], r["paid_end_week"].iloc[0]) != w:
        raise SystemExit(f"{c}: 確保費の行の週が窓と違う")
    return len(cw)


def key_year():
    rows = []
    for c in RUNS:
        r = PF.case_tables(W, c)["req"]
        r = r.assign(year=r["request_week"].str[:4])
        g = r.groupby(["sku_id", "region", "year"])[["q1", "q2", "q3", "delivered", "on_time", "early", "late", "q5"]].sum()
        bad = g[(g["q1"] != g["q2"] + g["q3"]) | (g["q2"] != g["delivered"] + g["q5"])]
        if len(bad):
            raise SystemExit(f"{c}: ①＝②＋③ か ②＝④＋⑤ が合わない行 {len(bad)}")
        for (s, rg, y), v in g.iterrows():
            rows.append({"case": c, "sku_id": s, "region": rg, "year": y, **{k: int(x) for k, x in v.items()}})
    return pd.DataFrame(rows)


def raise_usage():
    """the good cream output of the factory per week (the factory's handoff to the supply point) inside each window"""
    rows, wk = [], []
    for c in RUNS:
        cd = C.case_dir(W, c)
        rr = C.read_case(W, c)["run"]
        run = CS.load_run(os.path.join(cd, "run"), os.path.join(cd, rr["money_model"]))
        sh = run["ship"]
        f = sh[(sh["product"] == "COS_Cream") & (sh["phys_from"] == "Factory_JP") & (sh["kind"] == "handoff_to_sp")]
        by = f.groupby("ship_week")["lots"].sum()
        capu = run["capacity_used"]
        capu = capu[(capu["product"] == "COS_Cream")].set_index("week")
        a, b = WINDOW[c]
        weeks = [w for w in run["week_labels"] if a <= w <= b]
        n11 = n_le10 = other = 0
        for w in weeks:
            q = int(by.get(w, 0))
            kind = "11（使った）" if q == 11 else ("10 以下（使わなかった）" if q <= 10 else "その他")
            n11 += q == 11
            n_le10 += q <= 10
            other += q > 11
            wk.append({"case": c, "week": w, "good_output": q, "shippable_soft": capu.loc[w, "shippable_soft"], "kind": kind})
        prod_total = int(by.sum())
        rows.append({"case": c, "window": f"{a}〜{b}", "window_weeks": len(weeks), "used_11": n11, "unused_le10": n_le10,
                     "other": other, "good_output_in_window": int(sum(by.get(w, 0) for w in weeks)),
                     "good_output_total": prod_total})
    wk = pd.DataFrame(wk)
    # the unused weeks as runs of consecutive weeks
    runs_ = []
    for c in RUNS:
        x = wk[wk["case"] == c].reset_index(drop=True)
        start = prev = None
        for i, r in x.iterrows():
            un = r["good_output"] <= 10
            if un and start is None:
                start = r["week"]
            if not un and start is not None:
                runs_.append({"case": c, "from": start, "to": prev}); start = None
            prev = r["week"]
        if start is not None:
            runs_.append({"case": c, "from": start, "to": prev})
    return pd.DataFrame(rows), wk, pd.DataFrame(runs_)


def money(s, nweeks):
    rows = []
    for c in CASES:
        for lv, k in LEVEL.items():
            for pm, mul in PREMIUM.items():
                r_week = k["R"] * (mul if c in LIMITED else 1.0)
                for h in HOLD:
                    P0 = float(s[c]["P0"])
                    L = k["L"]
                    F = k["F"] * FEE_WEEKS[c]
                    R = r_week * nweeks[c]
                    H = float(s[c][f"H_{h}"])
                    rows.append({"case": c, "level": lv, "premium": pm, "holding": h, "P0": P0, "L": L, "F": F,
                                 "R_week": r_week, "R_weeks": nweeks[c], "R": R, "H": H, "A": P0 - L - F - R - H})
    m = pd.DataFrame(rows)
    # check against strategy_compare: mid, premium 0% -> A_なし / A_10%
    for c in CASES:
        for h in HOLD:
            mine = m[(m["case"] == c) & (m["level"] == "中") & (m["premium"] == "0%") & (m["holding"] == h)]["A"].iloc[0]
            if abs(mine - float(s[c][f"A_{h}"])) > 0.5:
                raise SystemExit(f"{c} {h}: A の手計算 {mine} が strategy_compare {s[c][f'A_{h}']} と違う")
    d = []
    for base, alt in DIFFS:
        for lv in LEVEL:
            for pm in PREMIUM:
                for h in HOLD:
                    x = m[(m["level"] == lv) & (m["premium"] == pm) & (m["holding"] == h)].set_index("case")
                    d.append({"diff": f"{alt} − {base}", "level": lv, "premium": pm, "holding": h,
                              **{f"d{k}": x.loc[alt, k] - x.loc[base, k] for k in ("P0", "L", "F", "R", "H", "A")}})
    d = pd.DataFrame(d)
    # A(C07) − A(C06) = [A(C05) − A(C04)] + [A(C07) − A(C05)] − [A(C06) − A(C04)]
    dec = []
    for lv in LEVEL:
        for pm in PREMIUM:
            for h in HOLD:
                x = m[(m["level"] == lv) & (m["premium"] == pm) & (m["holding"] == h)].set_index("case")["A"]
                t1 = x["C05"] - x["C04"]
                t2 = x["C07"] - x["C05"]
                t3 = x["C06"] - x["C04"]
                lhs = x["C07"] - x["C06"]
                if abs(lhs - (t1 + t2 - t3)) > 0.5:
                    raise SystemExit("分解が合わない")
                dec.append({"level": lv, "premium": pm, "holding": h, "A_C07_minus_C06": lhs,
                            "C05_minus_C04": t1, "C07_minus_C05": t2, "C06_minus_C04": t3})
    return m, d, pd.DataFrame(dec)


def inventory_age():
    rows = []
    for c in RUNS:
        cd = C.case_dir(W, c)
        rr = C.read_case(W, c)["run"]
        run = CS.load_run(os.path.join(cd, "run"), os.path.join(cd, rr["money_model"]))
        inv = run["inv"]
        inv = inv[(inv["external"].astype(int) == 0) & (inv["product"] == "COS_Cream")]
        by = inv.groupby("week_index")["lots"].sum()
        sh = run["shelf"]
        sc = sh[(sh["product"] == "COS_Cream") & (sh["channel"] == "*")]
        rows.append({"case": c, "cream_lot_weeks": int(by.sum()), "cream_max_week": int(by.max()),
                     "cream_end": int(by.iloc[-1]), "age_max_cream": sc["fifo_age_max"].iloc[0],
                     "over52_cream": sc["over_max_age"].iloc[0]})
    return pd.DataFrame(rows)


def protect():
    rows = []
    for d in ("compare_C04_C06", "compare_C05_C07", "compare_C06_C07"):
        p = pd.read_csv(os.path.join(O, d, "protect_check.csv"), encoding="utf-8-sig")
        n = pd.read_csv(os.path.join(O, d, "protect_need.csv"), encoding="utf-8-sig")
        for c in p["case"].unique():
            x = p[p["case"] == c]
            y = n[n["case"] == c].iloc[0]
            rows.append({"compare": d, "case": c, "basis": x["basis"].iloc[0],
                         "keys_met": int((x["status"] == "達成").sum()), "keys": len(x),
                         "keys_met_2029": int((x["status_2029"] == "達成").sum()),
                         "diff_min": int(x["diff"].min()), "diff_2029_min": int(x["diff_2029"].min()),
                         "floors_total": int(y["floors_total"]), "delivered_total": int(y["delivered_total"]),
                         "surplus": int(y["surplus"]),
                         # the target key (TH cream): the tool subtracts the net demand increment over the frozen base
                         # demand (78 lots in the early cases) from ④ before comparing; here ④ itself against the floor
                         "th_cream_delivered": 
                         int(x[(x["sku_id"] == TH[0]) & (x["market"] == TH[1])]["delivered"].iloc[0]),
                         "th_cream_floor": int(x[(x["sku_id"] == TH[0]) & (x["market"] == TH[1])]["floor_lots"].iloc[0]),
                         "th_cream_increment_subtracted":
                             int(x[(x["sku_id"] == TH[0]) & (x["market"] == TH[1])]["promo_increment_net"].iloc[0]),
                         "keys_met_by_delivered": int((x["delivered"] >= x["floor_lots"]).sum())})
    return pd.DataFrame(rows)


def main():
    s = summaries()
    nweeks = {c: windows_weeks(c) for c in CASES}
    print("有償の週", nweeks)
    ky = key_year()
    ky.to_csv(os.path.join(O, "key_year.csv"), index=False, encoding="utf-8-sig")
    ru, ruw, runs_ = raise_usage()
    ru.to_csv(os.path.join(O, "raise_usage.csv"), index=False, encoding="utf-8-sig")
    ruw.to_csv(os.path.join(O, "raise_usage_weeks.csv"), index=False, encoding="utf-8-sig")
    runs_.to_csv(os.path.join(O, "raise_unused_runs.csv"), index=False, encoding="utf-8-sig")
    m, d, dec = money(s, nweeks)
    m.to_csv(os.path.join(O, "money_cases.csv"), index=False, encoding="utf-8-sig")
    d.to_csv(os.path.join(O, "money_diff.csv"), index=False, encoding="utf-8-sig")
    dec.to_csv(os.path.join(O, "money_decomp.csv"), index=False, encoding="utf-8-sig")
    ia = inventory_age()
    ia.to_csv(os.path.join(O, "inventory_age.csv"), index=False, encoding="utf-8-sig")
    pr = protect()
    pr.to_csv(os.path.join(O, "protect_summary.csv"), index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 250)
    tot = ky.groupby(["case", "sku_id", "region"])[["q1", "delivered", "on_time", "early", "late", "q5"]].sum().reset_index()
    print("== key totals"); print(tot.to_string(index=False))
    cr = ky[ky["sku_id"] == "COS_Cream"]
    print("== cream key x year"); print(cr.to_string(index=False))
    print("== raise usage"); print(ru.to_string(index=False)); print(runs_.to_string(index=False))
    print("== money cases"); print(m.to_string(index=False))
    print("== money diff"); print(d.to_string(index=False))
    print("== decomposition"); print(dec.to_string(index=False))
    print("== inventory/age"); print(ia.to_string(index=False))
    print("== protect"); print(pr.to_string(index=False))


if __name__ == "__main__":
    main()
