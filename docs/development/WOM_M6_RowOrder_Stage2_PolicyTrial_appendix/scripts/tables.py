# -*- coding: utf-8 -*-
"""段 2：表を作る（output/roworder_stage2/tables.md と CSV）。

    python output/roworder_stage2/scripts/tables.py
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as CM  # noqa: E402

import pandas as pd  # noqa: E402
from tools import period_fulfillment as PF  # noqa: E402

O = CM.OUT
L = []


def pct(v):
    return "—" if v != v else f"{v * 100:.2f}%"


def load_scene(scene):
    p = os.path.join(O, scene, "cases.json")
    if not os.path.exists(p):
        return None
    cases = json.load(open(p, encoding="utf-8"))["cases"]
    keys = pd.read_csv(os.path.join(O, scene, "fulfillment", "period_fulfillment.csv"), encoding="utf-8-sig")
    per = pd.read_csv(os.path.join(O, scene, "fulfillment", "period_fulfillment_by_period.csv"), encoding="utf-8-sig")
    return cases, keys, per


def pdue_split(c):
    """(lots the factory capacity cut pushed before the first plan week = stage 0's "dropped",
    all past-due lots of the Backward run incl. the LT offset before the start)."""
    return c["cap_dropped_total"], c["past_due_total"]


def pdue_text(c):
    bym = {}
    for v in c["cap_dropped"].values():
        for m, n in v.items():
            bym[m] = bym.get(m, 0) + n
    det = "・".join(f"{m} {n:,}" for m, n in sorted(bym.items()))
    return f"{c['cap_dropped_total']:,}" + (f"（{det}）" if det else "") + f"〔past_due 全体 {c['past_due_total']:,}〕"


def burden_rows(c):
    out = []
    for fac, mk in sorted(c["burden"].items()):
        for m, v in sorted(mk.items()):
            out.append((fac.split(":")[2] if fac.count(":") >= 3 else fac, fac.split(":")[-1], m, v["pushed"],
                        v["denominator"], v["pushed"] / v["denominator"] if v["denominator"] else float("nan")))
    return out


def label(c):
    return f"{c['case']} {c['policy']}" + ("（入れ替え）" if c.get("reordered") else "")


def market_table(cases, keys, per, years=True, q2=False, tied=None):
    head = "| 案 | 製品 | 市場 | ① | " + ("② | ③ | " if q2 else "") + "④ 当週 | ④ 遅配 | ⑤ | ④÷① | " + \
        ("④÷② | " if q2 else "") + ("2027 | 2028 | 2029 |" if years else "")
    L.append(head)
    L.append("|" + "---|" * (head.count("|") - 1))
    for cid, c in cases.items():
        k = keys[(keys["case"] == cid) & (keys["region"] != "*")]
        for r in k.itertuples():
            cells = [label(c), r.sku_id, r.region, r.q1] + ([r.q2, r.q3] if q2 else []) + \
                [r.on_time, r.late, r.q5, pct(r.r41)] + ([pct(r.r42)] if q2 else [])
            if years:
                for y in ("2027", "2028", "2029"):
                    p = per[(per["case"] == cid) & (per["sku_id"] == r.sku_id) & (per["region"] == r.region) &
                            (per["period_kind"] == "year") & (per["period"].astype(str) == y)]
                    cells.append(pct(float(p["r41"].iloc[0])) if len(p) else "—")
            L.append("| " + " | ".join(str(x) for x in cells) + " |")


def spread_of(keys, cid, regions=None, sku=None):
    k = keys[(keys["case"] == cid) & (keys["region"] != "*")]
    if sku:
        k = k[k["sku_id"] == sku]
    if regions:
        k = k[k["region"].isin(regions)]
    return (k["r41"].max() - k["r41"].min()) * 100


def summary_table(cases, keys, scene, tied=None):
    L.append("| 案 | 総納品（④） | ⑤ の計 | ④÷① の開き" + ("（同順位 5 市場）" if tied else "（製品ごと、ポイント）") +
             " | 計画の前に落ちた lot | 在庫の lot・週（全期間／報告期間） | 年齢の最大（週） | 52 週超 | P0（報告期間） | PPC 売上 | PPC 粗利 | 実出荷の Lot_ID・週の digest |")
    L.append("|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|")
    for cid, c in cases.items():
        tot = keys[(keys["case"] == cid) & (keys["region"] == "*")].iloc[0]
        if tied:
            sp = f"{spread_of(keys, cid, tied):.2f}"
        else:
            sp = "；".join(f"{s} {spread_of(keys, cid, sku=s):.2f}" for s in
                          sorted(keys[(keys['case'] == cid) & (keys['region'] != '*')]['sku_id'].unique()))
        s = c["summary"]
        L.append(f"| {label(c)} | {int(tot.delivered):,} | {int(tot.q5):,} | {sp} | {pdue_text(c)} | "
                 f"{c['inventory_lot_weeks']:,}／{c['inventory_lot_weeks_report']:,} | {c['age_max']} | {c['over_52']} | "
                 f"{s['P0_report']:,.0f} | {s['ppc_revenue_full']:,.0f} | {s['ppc_gross_profit_full']:,.0f} | "
                 f"{c['ship_digest']['n']:,}・{c['ship_digest']['sha256']} |")


def burden_table(cases):
    mk = sorted({m for c in cases.values() for _f, _p, m, *_ in burden_rows(c)})
    prods = sorted({p for c in cases.values() for _f, p, *_ in burden_rows(c)})
    L.append("| 案 | 工場・製品 | " + " | ".join(mk) + " | 延べの計 |")
    L.append("|---|---|" + "---:|" * (len(mk) + 1))
    for cid, c in cases.items():
        br = burden_rows(c)
        for p in prods:
            rs = {m: (pu, de, r) for f, pr, m, pu, de, r in br if pr == p}
            if not rs:
                continue
            fac = [f for f, pr, *_ in br if pr == p][0]
            cells = [f"{rs[m][0]:,}／{rs[m][1]:,}（{rs[m][2]:.3f}）" if m in rs else "—" for m in mk]
            L.append(f"| {label(c)} | {fac}・{p} | " + " | ".join(cells) + f" | {sum(v[0] for v in rs.values()):,} |")


# ── §1 化粧品 ──────────────────────────────────────────────────────────
def cos():
    s = load_scene("cos")
    if not s:
        return
    cases, keys, per = s
    L.append("## §1 化粧品の能力不足の案（C3a）\n")
    L.append("### 要約\n")
    summary_table(cases, keys, "cos")
    L.append("\n### 市場別（報告期間の要求週。年は ④÷①）\n")
    market_table(cases, keys, per)
    L.append("\n### 工場 × 市場の延べの押し戻し／母数（累積押戻負担率）\n")
    burden_table(cases)
    L.append("")


def soy():
    for scene, title, tied, q2 in (("soy_c03", "§2.1 醤油 C03（同順位の配分 R1、proportional_even）",
                                    ["US_W", "US_E", "FR", "BE", "NL"], True),
                                   ("soy_alloc", "§2.2 soysauce-jpy-2027-alloc（能力 800、配分なし）", None, False)):
        s = load_scene(scene)
        if not s:
            continue
        cases, keys, per = s
        L.append(f"## {title}\n")
        summary_table(cases, keys, scene, tied=tied or ["US_W", "US_E", "FR", "BE", "NL"])
        L.append("\n### 市場別\n")
        market_table(cases, keys, per, years=False, q2=q2)
        L.append("\n### ⑤ の要求週（市場別：週の数、最初〜最後）\n")
        ws = os.path.join(O, scene, "ws")
        L.append("| 案 | " + " | ".join(["JP", "US_W", "US_E", "FR", "BE", "NL"]) + " |")
        L.append("|---|" + "---|" * 6)
        for cid, c in cases.items():
            req = PF.case_tables(ws, cid)["req"]
            cells = []
            for m in ["JP", "US_W", "US_E", "FR", "BE", "NL"]:
                g = req[(req["region"] == m) & (req["q5"] > 0)]
                cells.append(f"{len(g)} 週（{g['request_week'].min()}〜{g['request_week'].max()}）" if len(g) else "0")
            L.append(f"| {label(c)} | " + " | ".join(cells) + " |")
        L.append("\n### 工場 × 市場の延べの押し戻し／母数（累積押戻負担率）\n")
        burden_table(cases)
        L.append("")


# ── §3 golden ──────────────────────────────────────────────────────────
def golden():
    G = os.path.join(O, "golden")
    rows, mrows = [], []
    from golden_sweep import MODELS
    L.append("## §3 golden の 13 モデル（tail との差）\n")
    L.append("| モデル | 方式 | tail＝golden | 当週出荷の差 | 遅配の差 | 期末の注文残の差 | ④÷① の開き（製品ごとの最大、tail → 方式、ポイント） | 能力で計画の前に落ちた lot〔past_due 全体〕（tail → 方式） | 工場の P の差 | 工場の I の差 | PPC 売上の差 | PPC 粗利の差 | 粗利率（tail → 方式） | series_md5 が変わったノード | 市場の差（0 でないもの） |")
    L.append("|---|---|---|---:|---:|---:|---|---|---:|---:|---:|---:|---|---:|---|")
    for m in MODELS:
        tp = os.path.join(G, f"{m}_tail.json")
        if not os.path.exists(tp):
            L.append(f"| {m} | — | 未実行 | | | | | | | | | | | | |")
            continue
        t = json.load(open(tp, encoding="utf-8"))
        tm = {(x["product"], x["leaf"]): x for x in t["market"]}
        for pol in ("proportional_week", "balance_cut_ratio"):
            pp = os.path.join(G, f"{m}_{pol}.json")
            if not os.path.exists(pp):
                L.append(f"| {m} | {pol} | {t['golden_match']} | 未実行 | | | | | | | | | | | |")
                continue
            r = json.load(open(pp, encoding="utf-8"))
            rm = {(x["product"], x["leaf"]): x for x in r["market"]}
            d = {k: sum(rm[x][k] - tm[x][k] for x in tm) for k in ("on_time", "late", "backlog_end")}
            changes = []
            for x in tm:
                dd = {k: rm[x][k] - tm[x][k] for k in ("on_time", "late", "backlog_end")}
                if any(dd.values()):
                    changes.append(f"{x[1]} 当{dd['on_time']:+d}/遅{dd['late']:+d}/残{dd['backlog_end']:+d}")
                mrows.append({"model": m, "policy": pol, "product": x[0], "leaf": x[1], "demand": tm[x]["demand"],
                              **{f"{k}_tail": tm[x][k] for k in ("on_time", "late", "backlog_end")},
                              **{f"{k}_{pol}": rm[x][k] for k in ("on_time", "late", "backlog_end")}})

            def spread(mm):
                by = {}
                for (p, _l), v in mm.items():
                    if v["demand"] > 0:
                        by.setdefault(p, []).append((v["on_time"] + v["early"] + v["late"]) / v["demand"])
                return max(((max(v) - min(v)) * 100 for v in by.values() if len(v) > 1), default=0.0)
            fP = sum(v["P_supply"] for v in r["moms"].values()) - sum(v["P_supply"] for v in t["moms"].values())
            fI = sum(v["I_supply"] for v in r["moms"].values()) - sum(v["I_supply"] for v in t["moms"].values())
            tp_, rp_ = t["snapshot"]["ppc"], r["snapshot"]["ppc"]
            nmd5 = sum(1 for prod, nodes in t["snapshot"]["psi"].items() for n, v in nodes.items()
                       if r["snapshot"]["psi"].get(prod, {}).get(n, {}).get("series_md5") != v["series_md5"])
            L.append(f"| {m} | {pol} | {'一致' if t['golden_match'] else '不一致'} | {d['on_time']:+,} | {d['late']:+,} | "
                     f"{d['backlog_end']:+,} | {spread(tm):.2f} → {spread(rm):.2f} | {pdue_split(t)[0]:,}〔{pdue_split(t)[1]:,}〕 → "
                     f"{pdue_split(r)[0]:,}〔{pdue_split(r)[1]:,}〕 | {fP:+,} | {fI:+,} | {rp_['revenue_base'] - tp_['revenue_base']:+,.0f} | "
                     f"{rp_['gross_profit_base'] - tp_['gross_profit_base']:+,.0f} | "
                     f"{tp_['gross_margin_pct'] * 100:.3f}% → {rp_['gross_margin_pct'] * 100:.3f}% | {nmd5} | "
                     f"{'；'.join(changes) or 'なし'} |")
            rows.append({"model": m, "policy": pol, "tail_golden_match": t["golden_match"], **{f"d_{k}": v for k, v in d.items()},
                         "spread_tail": spread(tm), "spread_policy": spread(rm), "past_due_tail": t["past_due_total"],
                         "past_due_policy": r["past_due_total"], "d_factory_P": fP, "d_factory_I": fI,
                         "d_ppc_revenue": rp_["revenue_base"] - tp_["revenue_base"],
                         "d_ppc_gross_profit": rp_["gross_profit_base"] - tp_["gross_profit_base"],
                         "gm_tail": tp_["gross_margin_pct"], "gm_policy": rp_["gross_margin_pct"],
                         "series_md5_changed_nodes": nmd5, "seconds": r["seconds"]})
    pd.DataFrame(rows).to_csv(os.path.join(O, "golden_diff.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(mrows).to_csv(os.path.join(O, "golden_market.csv"), index=False, encoding="utf-8-sig")
    # closure-only factories
    L.append("\n### 休業だけで変わる工場：休業の週に押し戻した lot の市場別\n")
    L.append("| モデル | 工場 | 方式 | 休業の週 → 市場別の lot |")
    L.append("|---|---|---|---|")
    for m, fac in (("ev-europe-2026", "Factory_Local_DE"), ("ev-thailand-2026", "Factory_Local_TH"),
                   ("ev-thailand-2026_update", "Factory_Local_TH")):
        for pol in CM.POLICIES:
            pp = os.path.join(G, f"{m}_{pol}.json")
            if not os.path.exists(pp):
                continue
            r = json.load(open(pp, encoding="utf-8"))
            for nid, v in r["pushed"].items():
                if f":{fac}:" in nid:
                    cw = "；".join(f"{w}: " + ", ".join(f"{k} {n}" for k, n in sorted(c.items()))
                                  for w, c in sorted(v["closed_weeks"].items()))
                    L.append(f"| {m} | {nid.split(':')[-1]}@{fac} | {pol} | {cw or 'なし'}（休業以外の週の押し戻し "
                             f"{sum(v['open'].values()):,}） |")
    L.append("")


if __name__ == "__main__":
    cos()
    soy()
    golden()
    open(os.path.join(O, "tables.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("->", os.path.join(O, "tables.md"))
