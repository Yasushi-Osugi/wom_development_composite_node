# -*- coding: utf-8 -*-
"""4b の表（依頼書 §2）：既存の比較の出力（strategy_summary.csv・market_year・protect_*）を並べるだけ。
    python output/strategy_slice4b/tables.py
出力：output/strategy_slice4b/tables.md・promo_value.csv・raise_value.csv・exec_table.csv"""
import pandas as pd

O = "output/strategy_slice4b"
PAIRS = [("C04", "C02", "12 週", "25%"), ("C07", "C11", "18 週", "25%"),
         ("C06", "C02", "12 週", "50%"), ("C08", "C12", "24 週", "50%")]
DIRS = {"C02": "vsC02", "C11": "C07vsC11", "C12": "C08vsC12"}
GRID = [(h, a) for h in ("なし", "10%") for a in ("100%", "50%", "0%")]
NAMES = {"C01": "基準（能力不足）", "C02": "増産だけ 12 週", "C11": "増産だけ 18 週", "C12": "増産だけ 24 週",
         "C03": "販促 25%", "C04": "販促 25%＋増産 12 週", "C05": "販促 50%", "C06": "販促 50%＋増産 12 週",
         "C07": "販促 25%＋増産 18 週", "C08": "販促 50%＋増産 24 週", "C09": "販促 25%＋増産 12 週＋反動減",
         "N4": "反応 0%＋増産 12 週（計算）"}
SAME_RAISE = {"C04": "C02", "C06": "C02", "C09": "C02", "C07": "C11", "C08": "C12", "N4": "C02"}


def summ(level, d):
    return pd.read_csv(f"{O}/compare_{level}_{d}/strategy_summary.csv").set_index("case")


def years(d, case):
    my = pd.read_csv(f"{O}/compare_low_{d}/market_year_{case}.csv")
    my = my[(my[["on_time_diff", "q5_diff"]] != 0).any(axis=1)]
    return my


def fmt(v):
    return f"{v:+,.0f}"


def main():
    L = ["# 4b の表", ""]
    # 1. 同じ増産の下で販促を足す価値
    rows = []
    for alt, base, raise_w, promo in PAIRS:
        d = DIRS[base]
        lo, mi = summ("low", d), summ("mid", d)
        my = years(d, alt)
        tgt = my[my["region"] == "SG_EC"]
        oth = my[(my["region"] != "SG_EC") & (my["year"] == 2029)]
        r = {"pair": f"{alt} − {base}", "raise_weeks": raise_w, "promo": promo,
             "dP0": lo.loc[alt, "dP0_vs_base"],
             "target_on_time": int(tgt["on_time_diff"].sum()),
             "target_2028": int(tgt[tgt["year"] == 2028]["on_time_diff"].sum()),
             "target_2029_q5": int(tgt[tgt["year"] == 2029]["q5_diff"].sum()),
             "others_2029_on_time": int(oth["on_time_diff"].sum()), "others_2029_q5": int(oth["q5_diff"].sum()),
             "others_detail": "; ".join(f"{x.region} {x.q5_diff:+d}" for x in oth.itertuples())}
        for lv, s in (("low", lo), ("mid", mi)):
            for h, a in GRID:
                r[f"dA_{lv}_{h}_{a}"] = s.loc[alt, f"dA_{h}_avoid{a}_vs_base"]
        rows.append(r)
    pv = pd.DataFrame(rows)
    pv.to_csv(f"{O}/promo_value.csv", index=False, encoding="utf-8-sig")
    L += ["## 1. 同じ増産の下で販促を足す価値", "",
          "| 比較 | 増産 | 販促 | ΔP0 | 対象の当週 ④（2028） | 対象の 2029 年の ⑤ | 他の市場の 2029 年の ④／⑤ | ΔA 低・なし 100%／50%／0% | ΔA 低・10% 100%／0% | ΔA 中・なし 100%／0% |",
          "|---|---|---|---:|---:|---:|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['pair']} | {r['raise_weeks']} | {r['promo']} | {fmt(r['dP0'])} | {r['target_on_time']:+d}（{r['target_2028']:+d}） | "
                 f"{r['target_2029_q5']:+d} | {r['others_2029_on_time']:+d}／{r['others_2029_q5']:+d}（{r['others_detail'] or '—'}） | "
                 f"{fmt(r['dA_low_なし_100%'])}／{fmt(r['dA_low_なし_50%'])}／{fmt(r['dA_low_なし_0%'])} | "
                 f"{fmt(r['dA_low_10%_100%'])}／{fmt(r['dA_low_10%_0%'])} | {fmt(r['dA_mid_なし_100%'])}／{fmt(r['dA_mid_なし_0%'])} |")
    # 2. 増産を延ばす価値
    lo, mi = summ("low", "vsC02"), summ("mid", "vsC02")
    rv = []
    L += ["", "## 2. 増産を延ばす価値（販促なし、C02 と）", "",
          "| 比較 | ΔP0 | ΔA 低／中（保有費なし） | ΔA 低／中（10%） | 埋めた不足（市場 × 年、⑤ の差） |", "|---|---:|---|---|---|"]
    for c in ("C11", "C12"):
        my = years("vsC02", c)
        det = "; ".join(f"{x.region} {x.year} {x.q5_diff:+d}" for x in my.itertuples())
        rv.append({"pair": f"{c} − C02", "dP0": lo.loc[c, "dP0_vs_base"], "dA_low": lo.loc[c, "dA_なし_vs_base"],
                   "dA_mid": mi.loc[c, "dA_なし_vs_base"], "dA_low_10": lo.loc[c, "dA_10%_vs_base"],
                   "dA_mid_10": mi.loc[c, "dA_10%_vs_base"], "filled": det})
        r = rv[-1]
        L.append(f"| {r['pair']} | {fmt(r['dP0'])} | {fmt(r['dA_low'])}／{fmt(r['dA_mid'])} | {fmt(r['dA_low_10'])}／{fmt(r['dA_mid_10'])} | {det} |")
    pd.DataFrame(rv).to_csv(f"{O}/raise_value.csv", index=False, encoding="utf-8-sig")
    # 3. 守る供給
    pc = pd.read_csv(f"{O}/compare_low_vsC01/protect_check.csv")
    nd = pd.read_csv(f"{O}/compare_low_vsC01/protect_need.csv").set_index("case")
    L += ["", "## 3. 守る供給の判定（4 本目と同じ下限）", "",
          "| 案 | SG の代理店 | SG の店舗 | タイの代理店 | SG の EC 既存分 | 達成 | 総納品／必要量 |", "|---|---:|---:|---:|---:|---|---|"]
    for c in ["C01", "C02", "C11", "C12", "C03", "C04", "C05", "C06", "C07", "C08", "C09"]:
        p = pc[pc["case"] == c].set_index("market")["diff"]
        L.append(f"| {c} | {p['SG_Distributor']:+d} | {p['SG_Store']:+d} | {p['TH_Distributor']:+d} | {p['SG_EC']:+d} | "
                 f"{int(nd.loc[c, 'protected_markets_met'])}/4 | {int(nd.loc[c, 'delivered_total']):,}／{int(nd.loc[c, 'need']):,} |")
    # 4. 1 枚の表
    l1, m1 = summ("low", "vsC01"), summ("mid", "vsC01")
    ex = []
    for c in ["C02", "C11", "C12", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "N4"]:
        cc = "C02" if c == "N4" else c
        promo = 276000.0 if c == "N4" else 0.0
        same = SAME_RAISE.get(c)
        row = {"case": c, "name": NAMES[c],
               "vsC01_low": l1.loc[cc, "dA_なし_vs_base"] - promo, "vsC01_mid": m1.loc[cc, "dA_なし_vs_base"] - promo,
               "vsC01_low_avoid0": l1.loc[cc, "dA_なし_avoid0%_vs_base"] - promo}
        if same:
            if c == "N4":
                row.update({"same_raise": "C02", "vs_same_low": -promo, "vs_same_low_avoid0": -promo})
            else:
                d = DIRS[same]
                s = summ("low", d)
                if c not in s.index:      # C09 − C02: the slice 4 comparison (same runs, same low cost rows)
                    s = pd.read_csv(f"output/strategy_slice4/compare_low_vsC02/strategy_summary.csv").set_index("case")
                row.update({"same_raise": same, "vs_same_low": s.loc[c, "dA_なし_vs_base"],
                            "vs_same_low_avoid0": s.loc[c, "dA_なし_avoid0%_vs_base"]})
        else:
            row.update({"same_raise": "—", "vs_same_low": None, "vs_same_low_avoid0": None})
        p = nd.loc[cc]
        row["protect"] = f"{int(p['protected_markets_met'])}/4"
        ex.append(row)
    et = pd.DataFrame(ex)
    et.to_csv(f"{O}/exec_table.csv", index=False, encoding="utf-8-sig")
    L += ["", "## 4. 経営者に示す 1 枚の表（増産の枠を何に使うか＝同じ増産の長さの「増産だけ」と比べた差）", "",
          "| 案 | 今より良くなるか（C01 と、低／中） | 増産の枠を何に使うか（同じ長さの増産だけと、低） | 費用の近似（割合 0%：C01 と／同じ増産と） | 守る供給 |",
          "|---|---|---|---|---|"]
    for r in ex:
        vs = "—" if r["vs_same_low"] is None else f"{fmt(r['vs_same_low'])}（{r['same_raise']} と）"
        v0 = "—" if r["vs_same_low_avoid0"] is None else fmt(r["vs_same_low_avoid0"])
        L.append(f"| {r['case']} {r['name']} | {fmt(r['vsC01_low'])}／{fmt(r['vsC01_mid'])} | {vs} | "
                 f"{fmt(r['vsC01_low_avoid0'])}／{v0} | {r['protect']} |")
    open(f"{O}/tables.md", "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
