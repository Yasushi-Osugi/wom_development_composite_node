# -*- coding: utf-8 -*-
"""4 本目 §3.3〜§3.5：N4（反応 0%＋増産、回さない）と、経営者に示す 1 枚の表。
    python output/strategy_slice4/exec_table.py
N4 は C02 と入力の hash が同じ（確かめ済み）なので、P0・保有費・数量・判定は C02、費用は販促費 276,000 円を足す。"""
import os
import pandas as pd

O = "output/strategy_slice4"
PROMO = 276000.0
CASES = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09"]
NAMES = {"C01": "基準（能力不足）", "C02": "増産だけ 12 週", "C03": "販促 25%", "C04": "販促 25%＋増産 12 週",
         "C05": "販促 50%", "C06": "販促 50%＋増産 12 週", "C07": "販促 25%＋増産 18 週",
         "C08": "販促 50%＋増産 24 週", "C09": "販促 25%＋増産 12 週＋反動減", "N4": "反応 0%＋増産 12 週（計算）"}


def load(level, vs):
    return pd.read_csv(f"{O}/compare_{level}_vs{vs}/strategy_summary.csv").set_index("case")


def add_n4(s: pd.DataFrame, base: str) -> pd.DataFrame:
    """N4 = C02's row with the promotion cost added (A columns minus 276,000)."""
    r = s.loc["C02"].copy()
    r["B_add"] = r["B_add"] + PROMO
    r["cost_promo_campaign_add"] = PROMO
    for k in [k for k in s.columns if k == "A" or (k.startswith("A_"))]:
        r[k] = r[k] - PROMO
    for k in [k for k in s.columns if k.startswith("dA")]:
        src = k[1:].replace("_vs_base", "") if k != "dA_vs_base" else "A"
        r[k] = r[src] - s.loc[base, src]
    r["case_name"] = "N4"
    s = pd.concat([s, pd.DataFrame([r], index=["N4"])])
    return s


def main():
    low1, mid1 = add_n4(load("low", "C01"), "C01"), add_n4(load("mid", "C01"), "C01")
    low2, mid2 = add_n4(load("low", "C02"), "C02"), add_n4(load("mid", "C02"), "C02")
    pc = pd.read_csv(f"{O}/compare_low_vsC01/protect_check.csv")
    need = pd.read_csv(f"{O}/compare_low_vsC01/protect_need.csv").set_index("case")
    rows = []
    for c in CASES + ["N4"]:
        cc = "C02" if c == "N4" else c
        p = pc[pc["case"] == cc]
        short = "; ".join(f"{r.market} {r.diff:+d}" for r in p.itertuples() if r.status == "未達")
        inc = p[p["market"] == "SG_EC"]["demand_increment_delivered"].iloc[0]
        if c == "N4":
            inc = "増分なし（反応 0%）"
        row = {"case": c, "name": NAMES[c],
               "vsC01_low_none": low1.loc[c, "dA_なし_vs_base"], "vsC01_mid_none": mid1.loc[c, "dA_なし_vs_base"],
               "vsC01_low_10": low1.loc[c, "dA_10%_vs_base"], "vsC01_mid_10": mid1.loc[c, "dA_10%_vs_base"],
               "vsC02_low_none": low2.loc[c, "dA_なし_vs_base"] if c in low2.index else "",
               "vsC02_mid_none": mid2.loc[c, "dA_なし_vs_base"] if c in mid2.index else "",
               "store_d_vsC01": low1.loc[c, "d_item_store_operating_vs_base"],
               "vsC01_low_none_avoid100": low1.loc[c, "dA_なし_avoid100%_vs_base"],
               "vsC01_low_none_avoid50": low1.loc[c, "dA_なし_avoid50%_vs_base"],
               "vsC01_low_none_avoid0": low1.loc[c, "dA_なし_avoid0%_vs_base"],
               "vsC02_low_none_avoid0": low2.loc[c, "dA_なし_avoid0%_vs_base"] if c in low2.index else "",
               "protect_met": f"{int(need.loc[cc, 'protected_markets_met'])}/4",
               "protect_short": short or "—", "promo_increment": inc,
               "delivered_cream": int(need.loc[cc, "delivered_total"]), "need": int(need.loc[cc, "floors_total"])
               + (0 if c == "N4" else int(need.loc[cc, "demand_increment_net"]))}
        rows.append(row)
    t = pd.DataFrame(rows)
    t.to_csv(f"{O}/exec_table.csv", index=False, encoding="utf-8-sig")
    n4 = pd.DataFrame([low1.loc["N4"], mid1.loc["N4"]], index=["low", "mid"])
    n4.to_csv(f"{O}/n4_vsC01.csv", encoding="utf-8-sig")
    print(t.to_string())
    print(n4[["P0", "B_add", "A", "dA_vs_base", "A_10%", "dA_10%_vs_base"]].to_string())


if __name__ == "__main__":
    main()
