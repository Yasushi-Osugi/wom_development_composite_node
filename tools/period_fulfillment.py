# -*- coding: utf-8 -*-
"""
tools/period_fulfillment.py — 期間の充足の表（配分の規則の適合と、納品の結果を分けて）
================================================================================
RequestLetter_M6_R0_R1_GlobalAllocation A1（2026-11-18）。対応表 v0.1 §3.5、意味体系 v0.7 の ①〜⑤。

    python -m tools.period_fulfillment --ws <作業> --cases C02,C03,C04,C05
        [--protect JP] [--equalize US_W,US_E,FR,BE,NL] [--protect-min JP:29550] [--out <フォルダ>]

案ごと・鍵（SKU × 市場）ごとに、対象の需要 D（報告期間の要求週）について：
    ① 元の需要、② 供給対象、③ 未配分、④ 実納品（当週・前倒し・遅配）、⑤ 配分後の未充足（判定時点 T ＝ 計画の最後の週の末）
    ② ÷ ①（配分の規則）、④ ÷ ①、④ ÷ ②（納品の結果）、年別・四半期別の ④ ÷ ①、供給ゼロの週の数と最長の連続
- 配分をしない案：② ＝ ①、③ ＝ 0（Flow Check と同じ Lot_ID の照合から）。
- 配分をした案：上位 Demand Plan の台帳と、金額の実行の出荷の照合（比較の道具の allocation_table）。
- 供給ゼロの週：元の需要がある要求週のうち、その市場への実出荷（どの lot でも）が無い週。最長の連続も。
  上位 Demand Plan の udp_supply_runs.csv がある案では、それと突き合わせる。
- 規則の適合（同順位の鍵の ② ÷ ① の開きが 1 lot の端数以内か、保護する鍵の ② ＝ ①）と、結果
  （④ ÷ ① の最大 − 最小）を分けて出す。許容の幅は未決なので、結果の達否は「未判定」。どちらが良いかは書かない。

止める条件（StopError）：① ＝ ② ＋ ③ か ② ＝ ④ ＋ ⑤ が鍵・要求週で成り立たない、案が「済み」でない、
報告期間が案で違う（比較の道具の照合の止める条件も同じく止める）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from tools import compare_scenarios as CS   # noqa: E402

K = ["sku_id", "region", "request_week"]
NUM = ["q1", "q2", "q3", "on_time", "early", "late", "delivered", "q5"]
UNJUDGED = "未判定（許容の幅が未決）"


class StopError(ValueError):
    """The table cannot be made or an identity does not hold."""


def quarter_of(week: str) -> str:
    y, w = week.split("-W")
    return f"{y}-Q{min(4, (int(w) - 1) // 13 + 1)}"


def request_table(run: dict, udp_dir: Optional[str], name: str) -> pd.DataFrame:
    """key x request week: q1..q5 (and delivered = on_time + early + late)."""
    sup = CS.supply_by_request_week(run)
    udp = CS.load_udp(udp_dir) if udp_dir else None
    t = CS.allocation_table(sup, udp, name).drop(columns="allocation_source")
    t = t.rename(columns={"q1_original": "q1", "q2_in_scope": "q2", "q3_unallocated": "q3", "q5_backlog_end": "q5"})
    t["delivered"] = t["on_time"] + t["early"] + t["late"]
    bad = t[(t["q1"] != t["q2"] + t["q3"]) | (t["q2"] != t["delivered"] + t["q5"])]
    if len(bad):
        raise StopError(f"{name}: ①＝②＋③ か ②＝④＋⑤ が成り立たない要求週 {len(bad)} 件（例 {bad.iloc[0].to_dict()}）")
    return t


def zero_supply(run: dict, req: pd.DataFrame) -> Dict[tuple, dict]:
    """Per key: request weeks with original demand and no shipment to the market that week; longest run."""
    mm = CS.market_map(run)
    cs = run["ship"][run["ship"]["kind"] == CS.K_CONSUMER]
    ships = cs.groupby("node")["ship_week"].apply(set).to_dict()
    labels = run["week_labels"]
    out = {}
    for (sku, reg), g in req.groupby(["sku_id", "region"]):
        dem = set(g.loc[g["q1"] > 0, "request_week"])
        shipped = ships.get(mm[(sku, reg)], set())
        zero = run_ = best = 0
        start = best_from = ""
        first = next((i for i, w in enumerate(labels) if w in dem), len(labels))
        for w in labels[first:]:
            if w not in dem:
                continue
            if w in shipped:
                run_ = 0
                continue
            zero += 1
            run_ += 1
            if run_ == 1:
                start = w
            if run_ > best:
                best, best_from = run_, start
        out[(sku, reg)] = {"zero_supply_weeks": zero, "longest_zero_run": best, "longest_zero_run_from": best_from}
    return out


def _ratio(a, b):
    return a / b if b else float("nan")


def case_tables(ws: str, cid: str) -> dict:
    from wom.cockpit import cases as C
    st = C.status(ws, cid)
    if st["state"] != C.ST_DONE:
        raise StopError(f"案 {cid} は「{st['state']}」です（{st['reason']}）。並べられるのは「済み」の案だけ")
    case = C.read_case(ws, cid)
    run_rec = case["run"]
    cdir = C.case_dir(ws, cid)
    run = CS.load_run(os.path.join(cdir, "run"), os.path.join(cdir, run_rec["money_model"]))
    udp_dir = os.path.join(cdir, run_rec["udp_dir"]) if run_rec.get("udp_dir") else None
    rp = C._read_json(os.path.join(ws, C.WORKSPACE_FILE)).get("report_period") or {}
    rs, re_ = rp["start"], rp["end"]
    req = request_table(run, udp_dir, cid)
    req = req[(req["request_week"] >= rs) & (req["request_week"] <= re_)].copy()
    zs = zero_supply(run, req)
    udp_runs = None
    if udp_dir:
        p = os.path.join(CS._udp_dir(udp_dir), "udp_supply_runs.csv")
        if os.path.exists(p):
            udp_runs = pd.read_csv(p, dtype=str).set_index(["sku_id", "region"])
    mm = CS.market_map(run)
    pol = (case.get("inputs") or {}).get("policy") or {}
    return {"case": cid, "name": case.get("name", ""), "req": req, "zero": zs, "udp_runs": udp_runs, "market": mm,
            "allocation": udp_dir is not None, "week_rule": pol.get("week_rule") if udp_dir else "",
            "report_period": (rs, re_)}


def key_rows(ct: dict) -> List[dict]:
    rows = []
    for (sku, reg), g in ct["req"].groupby(["sku_id", "region"]):
        s = {c: int(g[c].sum()) for c in NUM}
        z = ct["zero"][(sku, reg)]
        r = {"case": ct["case"], "case_name": ct["name"], "week_rule": ct["week_rule"] or "（配分なし）",
             "sku_id": sku, "region": reg, "market": ct["market"].get((sku, reg), ""), **s,
             "r21": _ratio(s["q2"], s["q1"]), "r41": _ratio(s["delivered"], s["q1"]),
             "r42": _ratio(s["delivered"], s["q2"]), **z, "zero_check": ""}
        ur = ct["udp_runs"]
        if ur is not None and (sku, reg) in ur.index:
            u = ur.loc[(sku, reg)]
            same = (int(u["zero_supply_weeks"]), int(u["longest_zero_run"])) == (z["zero_supply_weeks"], z["longest_zero_run"])
            r["zero_check"] = "udp_supply_runs と一致" if same else \
                f"udp_supply_runs と違う（{u['zero_supply_weeks']}・{u['longest_zero_run']}）"
        rows.append(r)
    t = {c: sum(r[c] for r in rows) for c in NUM}
    rows.append({"case": ct["case"], "case_name": ct["name"], "week_rule": rows[0]["week_rule"], "sku_id": "*",
                 "region": "*", "market": "計", **t, "r21": _ratio(t["q2"], t["q1"]), "r41": _ratio(t["delivered"], t["q1"]),
                 "r42": _ratio(t["delivered"], t["q2"]), "zero_supply_weeks": "", "longest_zero_run": "",
                 "longest_zero_run_from": "", "zero_check": ""})
    return rows


def period_rows(ct: dict) -> List[dict]:
    req = ct["req"].copy()
    req["year"] = req["request_week"].str[:4]
    req["quarter"] = req["request_week"].map(quarter_of)
    rows = []
    for kind in ("year", "quarter"):
        for (sku, reg, p), g in req.groupby(["sku_id", "region", kind]):
            s = {c: int(g[c].sum()) for c in ("q1", "q2", "delivered", "q5")}
            rows.append({"case": ct["case"], "sku_id": sku, "region": reg, "period_kind": kind, "period": p, **s,
                         "r41": _ratio(s["delivered"], s["q1"]), "r42": _ratio(s["delivered"], s["q2"])})
    return rows


def judge(keys: pd.DataFrame, cid: str, allocation: bool, protect: List[str], equalize: List[str],
          protect_min: Dict[str, int]) -> dict:
    """Rule conformity and the result, kept apart."""
    k = keys[(keys["case"] == cid) & (keys["region"] != "*")].set_index("region")
    out = {"case": cid}
    eq = [r for r in equalize if r in k.index]
    if not allocation:
        out["rule"] = "配分なし（規則を置いていない）：② ＝ ①"
        out["rule_ok"] = ""
    else:
        r21 = k.loc[eq, "r21"]
        spread = float(r21.max() - r21.min()) if len(eq) else 0.0
        tol = max(1.0 / float(k.loc[r, "q1"]) for r in eq) if eq else 0.0
        prot_ok = all(int(k.loc[r, "q2"]) == int(k.loc[r, "q1"]) for r in protect if r in k.index)
        ok = spread <= tol + 1e-12 and prot_ok
        out["rule"] = (f"同順位 {','.join(eq)} の ②÷① {r21.min():.4%}〜{r21.max():.4%}（開き {spread:.4%}、"
                       f"1 lot の端数 {tol:.4%} 以内か）；保護 {','.join(protect)} の ② ＝ ① {'○' if prot_ok else '×'}")
        out["rule_ok"] = "合う" if ok else "合わない"
    r41 = k.loc[eq, "r41"]
    if len(eq):
        out["result"] = (f"同順位の ④÷① 最大 {r41.idxmax()} {r41.max():.2%}、最小 {r41.idxmin()} {r41.min():.2%}、"
                         f"開き {(r41.max() - r41.min()) * 100:.2f} ポイント")
    out["result_ok"] = UNJUDGED
    pm = []
    for r, v in protect_min.items():
        if r in k.index:
            d = int(k.loc[r, "delivered"])
            pm.append(f"{r} の ④ {d:,} {'≥' if d >= v else '<'} {v:,}（暫定の条件、{'満たす' if d >= v else '満たさない'}）")
    out["protect_min"] = "；".join(pm)
    return out


def fulfillment(ws: str, cases: List[str], protect: List[str], equalize: List[str],
                protect_min: Dict[str, int], out: Optional[str] = None) -> dict:
    cts = [case_tables(ws, c) for c in cases]
    if len({c["report_period"] for c in cts}) > 1:
        raise StopError("報告期間が案で違います")
    keys = pd.DataFrame([r for ct in cts for r in key_rows(ct)])
    per = pd.DataFrame([r for ct in cts for r in period_rows(ct)])
    jud = pd.DataFrame([judge(keys, ct["case"], ct["allocation"], protect, equalize, protect_min) for ct in cts])
    out = out or os.path.join(ws, "fulfillment", "_".join(cases))
    os.makedirs(out, exist_ok=True)
    keys.to_csv(os.path.join(out, "period_fulfillment.csv"), index=False, encoding="utf-8-sig")
    per.to_csv(os.path.join(out, "period_fulfillment_by_period.csv"), index=False, encoding="utf-8-sig")
    jud.to_csv(os.path.join(out, "period_fulfillment_judgement.csv"), index=False, encoding="utf-8-sig")
    write_md(keys, per, jud, cts, os.path.join(out, "period_fulfillment.md"))
    return {"dir": out, "keys": keys, "periods": per, "judgement": jud}


def _p(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return "—" if f != f else f"{f:.1%}"


def write_md(keys, per, jud, cts, path):
    rs, re_ = cts[0]["report_period"]
    L = [f"# 期間の充足（{' ・ '.join(c['case'] for c in cts)}）", "",
         f"対象の需要 D ＝ 報告期間 {rs}〜{re_} の要求週、判定時点 T ＝ {re_} の末。lot。",
         "① 元の需要、② 供給対象、③ 未配分、④ 実納品（当週＋前倒し＋遅配）、⑤ 配分後の未充足。", "",
         "## 鍵ごと", "",
         "| 案 | 週の規則 | 市場 | ① | ② | ③ | ④ 当週／前倒し／遅配 | ⑤ | ②÷① | ④÷① | ④÷② | 供給ゼロの週 | 最長の連続（から） |",
         "|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|"]
    for r in keys.itertuples():
        L.append(f"| {r.case} | {r.week_rule} | {r.market}（{r.region}） | {r.q1:,} | {r.q2:,} | {r.q3:,} | "
                 f"{r.delivered:,}（{r.on_time:,}／{r.early:,}／{r.late:,}） | {r.q5:,} | {_p(r.r21)} | {_p(r.r41)} | "
                 f"{_p(r.r42)} | {r.zero_supply_weeks} | {r.longest_zero_run}"
                 + (f"（{r.longest_zero_run_from}）" if r.longest_zero_run_from else "") + " |")
    L += ["", "## 規則の適合と結果（分けて記録）", "", "| 案 | 規則の適合 | 判定 | 結果 | 達否 | 保護の暫定の条件 |",
          "|---|---|---|---|---|---|"]
    for r in jud.itertuples():
        L.append(f"| {r.case} | {r.rule} | {r.rule_ok} | {getattr(r, 'result', '')} | {r.result_ok} | {r.protect_min} |")
    L += ["", "## 年別の ④÷①", ""]
    y = per[per["period_kind"] == "year"]
    ys = sorted(y["period"].unique())
    L += ["| 案 | 市場 | " + " | ".join(ys) + " |", "|---|---|" + "---:|" * len(ys)]
    for (c, reg), g in y.groupby(["case", "region"], sort=False):
        g = g.set_index("period")
        L.append(f"| {c} | {reg} | " + " | ".join(_p(g.loc[p, "r41"]) if p in g.index else "—" for p in ys) + " |")
    L += ["", "## 四半期別の ④÷①", ""]
    q = per[per["period_kind"] == "quarter"]
    qs = sorted(q["period"].unique())
    L += ["| 案 | 市場 | " + " | ".join(qs) + " |", "|---|---|" + "---:|" * len(qs)]
    for (c, reg), g in q.groupby(["case", "region"], sort=False):
        g = g.set_index("period")
        L.append(f"| {c} | {reg} | " + " | ".join(_p(g.loc[p, "r41"]) if p in g.index else "—" for p in qs) + " |")
    L += ["", "（数字を並べただけ。どちらの案が良いかは書かない）", ""]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Period fulfillment: rule conformity and delivery result apart")
    ap.add_argument("--ws", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--protect", default="")
    ap.add_argument("--equalize", default="")
    ap.add_argument("--protect-min", default="", help="REGION:LOTS, comma separated (a provisional check after the run)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]
    pm = {}
    for x in split(a.protect_min):
        r, v = x.split(":")
        pm[r.strip()] = int(v)
    try:
        res = fulfillment(a.ws, split(a.cases), split(a.protect), split(a.equalize), pm, a.out)
    except (StopError, CS.CompareError) as e:
        print(f"[period_fulfillment] 止めました: {e}", file=sys.stderr)
        return 2
    print(f"[period_fulfillment] -> {res['dir']}")
    for r in res["judgement"].itertuples():
        print(f"  {r.case}：規則 {r.rule_ok or '—'}；{getattr(r, 'result', '')}；{r.protect_min}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
