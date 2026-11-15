# -*- coding: utf-8 -*-
"""
wom/cockpit/compare_view_model.py — 事業計画の比較の 1 画面に出す表（画面に依存しない。Tk を import しない）
=========================================================================================================
RequestLetter_Cockpit_Stage3_Step2 B、設計書 `requests/Cockpit_Stage3_DesignMD_PlanCompareScreen_v0.1.md`
§1・§2。

段 1 の関数（`wom/cockpit/cases.py`・`case_runner.py`）と、道具 2（`tools/compare_scenarios.py`）の出力から、
① 案の表、② 選んだ案の入力、③ 基準と相手の比較（供給・工場・金額と境目）、④ 読むときの注意 を作る。
**数字を作り直さない**（ファイルを読み、並べ替え、見出しを付けるだけ）。ファイルは書かない。

黙って誤らないための決まり（設計書 §2.2）：
1. 案の状態が「入力が変わった」なら、結果を出さず「実行し直す」と変わったファイルの名前を出す。
2. 比較の状態が「済み」でなければ（未実行・入力が変わった・不整合）、③ の数字を出さず理由だけを出す。
3. 未設定と 0 を分ける：固定費の表の週額が空欄の行は「未設定」、控除後の利益は「未算出」。
4. どちらの案が良いかは言わない（差・境目・順位を決められない理由まで）。
5. 衝突・未達・止まった・不整合の案は、状態と理由を出す。
"""
from __future__ import annotations

import glob
import json
import math
import os
from typing import Dict, List, Optional

import pandas as pd

from wom.cockpit import cases as C
from wom.cockpit import case_runner as R

UNSET = "未設定"
NOT_COMPUTED = "未算出"
NOT_APPLICABLE = "対象外"
PENDING = "保留"
RERUN = "実行し直す"
STATE_DISPLAY = {C.ST_CHANGED: RERUN}


# ── 小道具 ─────────────────────────────────────────────────────────────
def _csv(path: str, **kw) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig", **kw)


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() in ("", "nan")


def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def fmt_yen(v) -> str:
    f = _num(v)
    if f is None:
        return str(v) if not _blank(v) else ""
    return f"{f:,.0f}" if abs(f - round(f)) < 1e-6 else f"{f:,.2f}"


def compare_dir(ws: str, base: str, alt: str) -> str:
    return os.path.join(ws, "compare", f"{base}__{alt}")


def available_comparisons(ws: str) -> List[tuple]:
    out = []
    for d in sorted(glob.glob(os.path.join(ws, "compare", "*__*"))):
        b, a = os.path.basename(d).split("__", 1)
        out.append((b, a))
    return out


# ── ① 案の表 ───────────────────────────────────────────────────────────
def case_table(ws: str) -> dict:
    """{"columns": [...], "rows": [ {"id", "cells": [...], "state", "show_result", "reason"} ]}.
    Only the inputs that differ between cases get a column (as cases.format_list)."""
    rows = C.list_cases(ws)

    def varying(getter):
        keys = sorted({k for r in rows for k in getter(r)})
        return [k for k in keys if len({getter(r).get(k) for r in rows}) > 1]

    lw = varying(lambda r: r["inputs"]["launch_week"])
    cap = varying(lambda r: r["inputs"]["capacity"])
    skus = sorted({s for r in rows for s in ((r["result"] or {}).get("deliveries_by_sku") or {})})
    cols = ["ID", "案の名前", "親"] + [f"投入 {k}" for k in lw] + [f"能力 {k}（hard/soft）" for k in cap] + \
        ["供給の方針"] + [f"納品 {s}" for s in skus] + ["未配分", "未充足（期末）", "P0（円、報告期間）", "状態"]
    out = []
    for r in rows:
        pol = r["inputs"]["policy"]
        res = r["result"] or {}
        show = r["state"] == C.ST_DONE and bool(res)
        cells = [r["id"], r["name"], r["parent"] or "—"] + [r["inputs"]["launch_week"].get(k, "") for k in lw] + \
            [r["inputs"]["capacity"].get(k, "") for k in cap] + \
            ["なし" if not pol else f"{pol['allocation']} ＋ {pol['min_supply'] or '—'}（{pol['week_rule']}）"]
        if show:
            ua = res.get("unallocated_by_key")
            cells += [f"{(res.get('deliveries_by_sku') or {}).get(s, 0):,}" for s in skus]
            cells += ["—" if ua is None else _kv(ua), _kv(res.get("backlog_end_by_key")), fmt_yen(res.get("P0_report"))]
        else:
            cells += [""] * (len(skus) + 3)
        st = STATE_DISPLAY.get(r["state"], r["state"])
        cells.append(st)
        out.append({"id": r["id"], "name": r["name"], "cells": cells, "state": r["state"], "show_result": show,
                    "reason": r["reason"], "result": res if show else None})
    return {"columns": cols, "rows": out}


def _kv(d) -> str:
    d = {k: v for k, v in (d or {}).items() if v}
    return "、".join(f"{k} {v}" for k, v in sorted(d.items())) or "0"


# ── ② 選んだ案の入力 ─────────────────────────────────────────────────────
def case_inputs(ws: str, cid: str) -> dict:
    cdir = C.case_dir(ws, cid)
    case = C.read_case(ws, cid)
    st = C.status(ws, cid)
    out = {"id": cid, "name": case["name"], "parent": case.get("parent"), "state": st["state"],
           "state_display": STATE_DISPLAY.get(st["state"], st["state"]), "reason": st["reason"],
           "changed_files": st.get("changed_files", []), "entry_plan": [], "capacity": [], "policy": None,
           "fixed_cost": [], "note": "読むだけ。入力を変えるのは次の段（段 3）"}
    ep = os.path.join(cdir, "model", C.ENTRY_PLAN)
    if os.path.exists(ep):
        d = _csv(ep, dtype=str, keep_default_na=False)
        out["entry_plan"] = d[["sku_id", "region", "launch_week", "steady_lots_per_week", "ramp_weeks",
                               "ramp_ratio"]].to_dict("records")
    cap = _csv(os.path.join(cdir, "model", C.CAPACITY), dtype=str, keep_default_na=False)
    for (sku, node), g in cap.groupby(["sku_id", "node_name"]):
        pairs = sorted({(r["max_supply"], r["cap_soft"]) for _, r in g.iterrows()})
        out["capacity"].append({"sku_id": sku, "node": node, "rows": len(g),
                                "max_supply": pairs[0][0] if len(pairs) == 1 else "週で違う",
                                "cap_soft": pairs[0][1] if len(pairs) == 1 else "週で違う"})
    pol = case["inputs"].get("policy")
    if pol:
        out["policy"] = {"allocation_file": pol.get("allocation_file"), "policy_file": pol.get("policy_file"),
                         "week_rule": pol.get("week_rule"), "knowledge_file": pol.get("knowledge_file")}
    fc = case["inputs"].get("fixed_cost")
    if fc and os.path.exists(os.path.join(cdir, fc)):
        d = _csv(os.path.join(cdir, fc), dtype=str, keep_default_na=False)
        for _, r in d.iterrows():
            out["fixed_cost"].append({
                "cost_item": r["cost_item"], "entity": r["entity"],
                "paid": f"{r['paid_start_week']}〜{r['paid_end_week']}",
                "weekly_amount": r["weekly_amount"] if r["weekly_amount"].strip() else UNSET,
                "currency": r["currency"],
                "count_outside_report": (r.get(C.COUNT_OUTSIDE_COL, "") or "").strip() == "1",
                "note": r.get("note", "")})
    out["fixed_cost_note"] = "生産量を上げる費用は、増産の確保費の行（週額は未設定）として比べる" \
        if not any("raise" in f["cost_item"] for f in out["fixed_cost"]) else ""
    return out


# ── ③ 比較 ─────────────────────────────────────────────────────────────
def _min_supply_exact(ws: str, cid: str) -> Dict[tuple, bool]:
    """(sku, region, request week) -> True when the supply in scope equals the minimum supply
    (udp_min_supply_check.csv of a policy case). The value says whether the week was cut to the minimum
    (unallocated > 0) or the demand itself equals the minimum."""
    run = (C.read_case(ws, cid).get("run") or {})
    if not run.get("udp_dir"):
        return {}
    p = os.path.join(C.case_dir(ws, cid), run["udp_dir"], "udp_min_supply_check.csv")
    if not os.path.exists(p):
        return {}
    d = _csv(p)
    sel = os.path.join(C.case_dir(ws, cid), run["udp_dir"], "udp_selection_ledger.csv")
    q3 = {}
    if os.path.exists(sel):
        s = _csv(sel, dtype=str)
        q3 = {r["source_demand_ref"]: int(r["q3"]) for _, r in s.iterrows()}
    out = {}
    for _, r in d.iterrows():
        if int(r["min_supply_lots"]) > 0 and int(r["q2"]) == int(r["min_supply_lots"]):
            sku, reg, wk = r["source_demand_ref"].split("|")
            out[(sku, reg, wk)] = q3.get(r["source_demand_ref"], 0) > 0
    return out


def comparison(ws: str, base: str, alt: str) -> dict:
    """③ and the comparison part of ④. When the comparison is not 済み, only state and reason."""
    st = R.compare_status(ws, base, alt)
    d = compare_dir(ws, base, alt)
    out = {"base": base, "alt": alt, "state": st, "reason": "", "available": False}
    if st != C.ST_DONE:
        if st == C.ST_NOT_RUN:
            out["reason"] = "この 2 案はまだ並べていない（tools.cockpit_cases compare）"
        elif st == C.ST_CHANGED:
            out["reason"] = "比べた後に案の入力が変わったか、案を実行し直した。並べ直す"
        else:
            rec = json.load(open(os.path.join(d, "compare.json"), encoding="utf-8"))
            out["reason"] = rec.get("message", "")
        return out
    out["available"] = True
    out["record"] = json.load(open(os.path.join(d, "compare.json"), encoding="utf-8"))
    out["supply"] = supply_view(ws, base, alt)
    out["factory"] = factory_view(d, base, alt)
    out["money"] = money_view(d, base, alt)
    return out


def supply_view(ws: str, base: str, alt: str) -> dict:
    """Key x request week for both cases: demand, on time, early, late, unallocated (③),
    backlog after allocation (⑤), and the minimum-supply-exact mark."""
    d = compare_dir(ws, base, alt)
    p = os.path.join(d, "supply_allocation_by_request_week.csv")
    if os.path.exists(p):
        s = _csv(p, dtype={"request_week": str})
        m = {"demand": "q1_original", "in_scope": "q2_in_scope", "unallocated": "q3_unallocated",
             "on_time": "on_time", "early": "early", "late": "late", "backlog": "q5_backlog_end"}
        allocation = True
    else:
        s = _csv(os.path.join(d, "supply_by_request_week.csv"), dtype={"request_week": str})
        m = {"demand": "demand", "in_scope": "demand", "unallocated": None, "on_time": "on_time", "early": "early",
             "late": "late", "backlog": "backlog_end"}
        allocation = False
    marks = {base: _min_supply_exact(ws, base), alt: _min_supply_exact(ws, alt)}
    cells, totals = [], []
    for side, cid in (("base", base), ("alt", alt)):
        for _, r in s.iterrows():
            k = (r["sku_id"], r["region"], r["request_week"])
            x = {"case": cid, "side": side, "sku_id": k[0], "region": k[1], "request_week": k[2]}
            for name, col in m.items():
                x[name] = 0 if col is None else int(r[f"{col}_{side}"])
            x["min_supply_exact"] = k in marks[cid]
            x["cut_to_minimum"] = bool(marks[cid].get(k, False))
            cells.append(x)
    cdf = pd.DataFrame(cells)
    keys = ["demand", "in_scope", "unallocated", "on_time", "early", "late", "backlog"]
    for (cid, sku, reg), g in cdf.groupby(["case", "sku_id", "region"], sort=False):
        t = {"case": cid, "sku_id": sku, "region": reg, **{k: int(g[k].sum()) for k in keys},
             "min_supply_exact_weeks": int(g["min_supply_exact"].sum()),
             "cut_to_minimum_weeks": int(g["cut_to_minimum"].sum())}
        totals.append(t)
    return {"allocation": allocation, "cells": cdf, "totals": pd.DataFrame(totals),
            "weeks": list(dict.fromkeys(s["request_week"])),
            "keys": list(dict.fromkeys(zip(s["sku_id"], s["region"])))}


def factory_view(d: str, base: str, alt: str) -> dict:
    fw = _csv(os.path.join(d, "factory_weekly.csv"), dtype={"week": str})
    inv = _csv(os.path.join(d, "inventory_by_week_sku.csv"), dtype={"week": str})
    age = _csv(os.path.join(d, "age_summary.csv"), dtype=str)
    pw_p = os.path.join(d, "planned_output_weeks.csv")
    pw = _csv(pw_p, dtype=str, keep_default_na=False) if os.path.exists(pw_p) else pd.DataFrame()
    idle = _csv(os.path.join(d, "factory_idle_weeks.csv"), dtype={"week": str})
    inv_sum = []
    for p, g in inv.groupby("product"):
        last = g[g["week_index"] == g["week_index"].max()]
        inv_sum.append({"product": p, "lot_weeks_base": int(g["lots_base"].sum()),
                        "lot_weeks_alt": int(g["lots_alt"].sum()), "max_base": int(g["lots_base"].max()),
                        "max_alt": int(g["lots_alt"].max()), "end_base": int(last["lots_base"].sum()),
                        "end_alt": int(last["lots_alt"].sum())})
    a = age[age["channel"] == "*"][["case", "product", "deliveries", "fifo_age_max", "over_max_age"]]
    labels = list(dict.fromkeys(fw["week"]))
    return {"weekly": fw, "inventory": inv, "inventory_summary": pd.DataFrame(inv_sum), "age": a,
            "planned_output_weeks": pw, "idle": idle, "labels": labels,
            "boundary_weeks": [labels[0]] + labels[-4:] if len(labels) >= 5 else labels,
            "note": "計画の上限は soft の値（良品＝floor(cap_soft × 歩留まり)）。物理の上限（hard）は計画には使わない"}


def _fc_display(r: pd.Series) -> dict:
    """One row of fixed_cost_breakeven.csv for the screen: blank weekly amount of a present row = 未設定,
    the P0 after cost of such a row = 未算出 (the CSV keeps blanks; rule 3)."""
    x = {k: ("" if _blank(v) else v) for k, v in r.items()}
    total = x.get("cost_item") == "合計"
    for c in ("base", "alt"):
        has = not _blank(x.get(f"paid_start_{c}")) or total
        wa = x.get(f"weekly_amount_{c}", "")
        if total:
            pass
        elif not has:
            x[f"weekly_amount_{c}"] = NOT_APPLICABLE
            x[f"cost_{c}"] = 0
        elif wa == "":
            x[f"weekly_amount_{c}"] = UNSET
            x[f"cost_{c}"] = UNSET
            x[f"P_after_{c}"] = NOT_COMPUTED
    if not total and x.get("delta_P_after", "") == "" and UNSET in (x.get("weekly_amount_base"),
                                                                      x.get("weekly_amount_alt")):
        x["delta_P_after"] = NOT_COMPUTED
    return x


def money_view(d: str, base: str, alt: str) -> dict:
    tot = _csv(os.path.join(d, "money_totals.csv"), dtype=str)
    rep = tot[tot["period"] == "report"]
    full = tot[tot["period"] == "full"]
    mb = _csv(os.path.join(d, "money_by_week_sku.csv"), dtype={"week": str})
    star = mb.groupby(["week_index", "week", "in_report"])[["profit_r2_base", "profit_r2_alt"]].sum().reset_index()
    r_ = star[star["in_report"].astype(str) == "True"].sort_values("week_index").copy()
    r_["cum_base"] = r_["profit_r2_base"].cumsum()
    r_["cum_alt"] = r_["profit_r2_alt"].cumsum()
    fc = _csv(os.path.join(d, "fixed_cost_breakeven.csv"), dtype=str, keep_default_na=False)
    rows = [_fc_display(r) for _, r in fc.iterrows()]
    unset = sorted({r["cost_item"] for r in rows if r.get("cost_item") not in ("", "合計")
                    and UNSET in (r.get("weekly_amount_base"), r.get("weekly_amount_alt"))})
    ranking = PENDING if (unset or any(r.get("cost_item", "") == "" for r in rows)) else "週額が設定済み：控除後の利益の差を見る"
    return {"report_by_product": rep, "full_by_product": full, "cumulative_report": r_,
            "fixed_cost": rows, "unset_costs": unset, "ranking": ranking}


# ── ④ 読むときの注意 ─────────────────────────────────────────────────────
def notes(ws: str, base: Optional[str], alt: Optional[str], cmp: Optional[dict] = None) -> List[str]:
    out = []
    table = case_table(ws)
    for r in table["rows"]:
        if r["state"] == C.ST_CHANGED:
            out.append(f"{r['id']}（{r['name']}）：{RERUN}。{r['reason']}")
        elif r["state"] not in (C.ST_DONE,):
            out.append(f"{r['id']}（{r['name']}）：{r['state']}" + (f"。{r['reason']}" if r["reason"] else ""))
        elif r["result"] and r["result"].get("unvalued_consolidated_lines"):
            out.append(f"{r['id']}：連結の法人の未評価の明細 {r['result']['unvalued_consolidated_lines']} 件")
    if not (base and alt):
        out.append("基準（◎）と相手（○）を選ぶと、2 案の比較を出す")
        return out
    cmp = cmp or comparison(ws, base, alt)
    if not cmp["available"]:
        out.append(f"比較 {base} → {alt}：{cmp['state']}。{cmp['reason']}（数字は出さない）")
        return out
    mv = cmp["money"]
    if mv["unset_costs"]:
        out.append(f"週額が未設定の費用：{', '.join(mv['unset_costs'])} → 控除後の利益は{NOT_COMPUTED}、"
                   f"採算の順位は{PENDING}（出すのは差と境目だけ）")
    elif mv["ranking"] == PENDING:
        out.append(f"固定費の表が無い → 採算の順位は{PENDING}")
    for r in mv["fixed_cost"]:
        if r.get("boundary_assumption"):
            out.append(f"{r['cost_item']} の境目：{r['boundary_assumption']}")
    fv = cmp["factory"]
    out.append(f"計画の境界の週（最初の週・最後の 4 週）：{', '.join(fv['boundary_weeks'])}。"
               "ここで工場が計画値より少なく作るのは計画の端の効果")
    sv = cmp["supply"]
    t = sv["totals"]
    ex = t[t["min_supply_exact_weeks"] > 0]
    for x in ex.itertuples():
        cut = f"（うち削って最低ちょうど {x.cut_to_minimum_weeks} 週）" if x.cut_to_minimum_weeks else "（需要が最低供給量と同じ）"
        out.append(f"{x.case} {x.sku_id}:{x.region}：最低供給量ちょうどの週 {x.min_supply_exact_weeks}{cut}")
    out.append("突き合わせ：要求週別の供給の合計 ＝ Flow Check の表 2、SKU 別の試算利益の合計 ＝ 連結の値"
               + ("、金額の実行の出荷 ＝ 数量配分の結果" if sv["allocation"] else "") + "（道具 2 で確認済み）")
    out.append("どちらの案が良いかは、この画面は言わない（差・境目・決められない理由まで）")
    return out
