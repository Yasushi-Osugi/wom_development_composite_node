# -*- coding: utf-8 -*-
"""段 1 §3 の比較と表：soy/<T>/result.json → soy_tables.md・soy_checks.json。"""
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soy")
R = {t: json.load(open(os.path.join(OUT, t, "result.json"), encoding="utf-8")) for t in
     ("T1", "T2", "T3", "T4", "T5", "T6")}
MK = ["Rest_US_West", "Rest_US_East", "Rest_JP", "Rest_FR", "Rest_BE", "Rest_NL"]
REG = {"Rest_US_West": "US_W", "Rest_US_East": "US_E", "Rest_JP": "JP", "Rest_FR": "FR", "Rest_BE": "BE",
       "Rest_NL": "NL"}

# 到達点 6 の数字（C02 と §3.3 の入れ替え）
REF_C02 = {"Rest_US_West": 350, "Rest_US_East": 350, "Rest_JP": 600, "Rest_FR": 300, "Rest_BE": 5726,
           "Rest_NL": 5800}
REF_SWAP = {"Rest_US_West": 350, "Rest_US_East": 350, "Rest_JP": 11726, "Rest_FR": 300, "Rest_BE": 200,
            "Rest_NL": 200}


def same(a, b):
    ra, rb = R[a], R[b]
    return {
        "market": all(ra["market"][m] == rb["market"][m] for m in MK),
        "ship_lots_and_weeks": ra["ship_week_by_lot"] == rb["ship_week_by_lot"],
        "burden": ra["burden"] == rb["burden"],
        "past_due": ra["past_due"] == rb["past_due"],
    }


checks = {
    "T2_eq_T3": same("T2", "T3"),
    "T4_eq_T5": same("T4", "T5"),
    "T1_reproduces_C02": {m: R["T1"]["market"][m]["backlog_end"] == REF_C02[m] for m in MK},
    "T6_reproduces_swap": {m: R["T6"]["market"][m]["backlog_end"] == REF_SWAP[m] for m in MK},
    "conservation": {t: {"demand": sum(r["market"][m]["demand"] for m in MK),
                         "on_time+late+backlog": sum(r["market"][m]["on_time"] + r["market"][m]["late"]
                                                     + r["market"][m]["backlog_end"] for m in MK),
                         "early": sum(r["market"][m]["early"] for m in MK)} for t, r in R.items()},
    "cap_violations": {t: {k: len(v["cap_violations"]) for k, v in r["mom"].items()} for t, r in R.items()},
    "total_delivered": {t: r["n_ships"] for t, r in R.items()},
    "seconds": {t: r["seconds"] for t, r in R.items()},
}
json.dump(checks, open(os.path.join(OUT, "..", "soy_checks.json"), "w", encoding="utf-8"), ensure_ascii=False,
          indent=1)

L = ["## 市場別（① 需要・④ 当週・⑤ 未充足〔期末の注文残〕、lot）", "",
     "| 写し | 方式 | 木 | " + " | ".join(REG[m] for m in MK) + " | 計 ⑤ | ④÷① の開き |",
     "|---|---|---|" + "---:|" * len(MK) + "---:|---:|"]
for t, r in R.items():
    cells, rates = [], []
    for m in MK:
        x = r["market"][m]
        rate = x["on_time"] / x["demand"] * 100
        rates.append(rate)
        cells.append(f"{x['on_time']:,}／{x['backlog_end']:,}（{rate:.2f}%）")
    L.append(f"| {t} | {r['policy']} | {r['tree']} | " + " | ".join(cells)
             + f" | {sum(r['market'][m]['backlog_end'] for m in MK):,} | {max(rates) - min(rates):.2f} pt |")
L += ["", "セルは ④／⑤（④÷①）。① は "
      + "・".join(f"{REG[m]} {R['T1']['market'][m]['demand']:,}" for m in MK) + "。", ""]

L += ["## 工場 × 市場の延べの押し戻し・母数・累積押戻負担率", "",
      "| 写し | 工場 | " + " | ".join(REG[m] for m in MK) + " |", "|---|---|" + "---:|" * len(MK)]
for t, r in R.items():
    for nid, mk in r["burden"].items():
        cells = []
        for m in MK:
            v = mk.get(REG[m])
            cells.append("—" if not v else f"{v['pushed']:,}／{v['denominator']:,}（{v['pushed'] / v['denominator']:.3f}）")
        L.append(f"| {t} | {nid} | " + " | ".join(cells) + " |")
L += ["", "セルは 延べの押し戻し／母数（負担率）。", ""]
L += ["## 一致の確かめ", "", "```json", json.dumps({k: checks[k] for k in
      ("T2_eq_T3", "T4_eq_T5", "T1_reproduces_C02", "T6_reproduces_swap", "cap_violations", "total_delivered",
       "seconds")}, ensure_ascii=False, indent=1), "```"]
open(os.path.join(OUT, "..", "soy_tables.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
