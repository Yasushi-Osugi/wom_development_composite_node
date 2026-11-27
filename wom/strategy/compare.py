# -*- coding: utf-8 -*-
"""
wom/strategy/compare.py — 変換した案の要約（P0・追加費用・控除後の比較値・①〜⑤・波及・押し戻し）
=================================================================================================
RequestLetter_Promo_Convert_Slice1 §4・§5・§7。計算は比較の道具の関数を使い、二重に作らない：

- P0・追加費用・控除後 ………… wom.cockpit.case_runner.compare_cases（tools.compare_scenarios の固定費の表）
- ①〜⑤ ……………………………… tools.period_fulfillment（①＝②＋③、②＝④＋⑤ を要求週で検査して止める）
- 在庫・年齢 …………………… tools.compare_scenarios.load_run（vc_inventory_weekly・shelf_life_summary）
- 押し戻し ……………………… wom.strategy.overflow（エンジンの overflow_by_node）

比較値の名前（業務定義 v0.1 §4）：
    P0       追加販促費の控除前の現行比較値（報告期間、vc_v3_weekly の profit_r2_hq_wk の合計）
    B_add    案の外の追加費用（報告通貨。案の inputs/fixed_cost.csv。P0 には入っていない）
    A        控除後の比較値 ＝ P0 − B_add（グループの営業利益や Net Cash ではない）
    ΔA       A − A（基準の案）
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional

import pandas as pd

from wom.cockpit import cases as C
from wom.strategy import StrategyError

SNAP_KEYS = ("period", "products", "forward", "backward", "ppc", "psi")


def _ensure_path():
    if C.REPO not in sys.path:
        sys.path.insert(0, C.REPO)


def _cost_cell(rows: List[dict], side: str) -> float:
    """B_add of one side from the fixed-cost table rows of compare_cases (the 合計 row if there is one)."""
    items = [r for r in rows if r.get("cost_item")]
    if not items:
        return 0.0
    tot = [r for r in items if r["cost_item"] == "合計"]
    r = tot[0] if tot else items[0]
    v = r.get(f"cost_{side}")
    if v in ("", None, "未算出"):
        raise StrategyError(f"費用の前提の {r['cost_item']} の {side} が未設定・未算出です（控除後が出せない）")
    return float(v)


def _item_costs(rows: List[dict], side: str) -> Dict[str, float]:
    """{cost_item: cost} of one side from the fixed-cost table rows of compare_cases (item rows, not 合計).
    An item the side does not bear is 0 (対象外); an unset weekly amount stops (no silent 0)."""
    out = {}
    for r in rows:
        it = r.get("cost_item")
        if not it or it == "合計":
            continue
        v = r.get(f"cost_{side}")
        if v in ("", None, "未算出"):
            raise StrategyError(f"費用の前提の {it} の {side} が未設定・未算出です（費目ごとの額が出せない）")
        out[it] = float(v)
    return out


def holding_columns(P0: float, B_add: float, B_inventory: float, rates: List[float]) -> Dict[str, float]:
    """Holding cost per annual rate (rate ÷ 52 × the group's valued inventory at consolidated cost × weeks,
    warm-up included: the holding-cost stage, wom.cockpit.after_cost) and A = P0 − B_add − H for each rate."""
    from wom.cockpit.after_cost import WEEKS_PER_YEAR, rate_text
    out = {}
    for r in rates:
        h = r / WEEKS_PER_YEAR * B_inventory
        t = rate_text(r if r else None)
        out[f"H_{t}"] = h
        out[f"A_{t}"] = P0 - B_add - h
    return out


def _demand_log_totals(ws: str, cid: str, sku: str, market: str, rs: str, re_: str) -> dict:
    p = os.path.join(C.case_dir(ws, cid), "inputs", "strategy_change_log.csv")
    if not os.path.exists(p):
        return {"plan_id": "", "d": 0, "residual": "", "log": False}
    log = pd.read_csv(p, dtype=str, keep_default_na=False)
    key = f"{sku}|{market}"
    dm = log[(log["key"] == key) & (log["column"] == "quantity") & (log["rule"] != "residual")]
    dm = dm[(dm["week"] >= rs) & (dm["week"] <= re_)]
    d = int(sum(int(a) - int(b) for a, b in zip(dm["after"], dm["before"])))
    res = log[(log["key"] == key) & (log["rule"] == "residual")]["after"].tolist()
    return {"plan_id": log["plan_id"].iloc[0] if len(log) else "", "d": d, "residual": ";".join(res), "log": True}


def _snapshot_same(a: Optional[dict], b: Optional[dict]) -> str:
    if not a or not b:
        return "比べられない（snapshot.json が無い）"
    diff = [k for k in SNAP_KEYS if a.get(k) != b.get(k)]
    return "同じ" if not diff else f"違う（{', '.join(diff)}）"


def compare_plans(ws: str, base: str, cases: List[str], sku: str, market: str, out: Optional[str] = None,
                  overflow: bool = True, weekly: Optional[tuple] = None,
                  holding_rates: Optional[List[float]] = None, avoidable: Optional[tuple] = None,
                  protect: Optional[str] = None) -> dict:
    """weekly=(start week, end week): also write the weekly table and the market tables (Slice 2 §3).
    holding_rates (e.g. [0, 0.10]): holding cost and A per rate (Slice 3 §3); B_add per cost item.
    avoidable=(cost item, [ratios]): A per avoidable ratio of that item (Slice 4 §2.1).
    protect=<table>: protected-supply check per case (Slice 4 §2.2), protect_check.csv / protect_need.csv."""
    _ensure_path()
    from wom.cockpit import case_runner as R
    from tools import compare_scenarios as CS
    from tools import period_fulfillment as PF
    from wom.strategy import overflow as OV
    wsj = C.open_workspace(ws)
    rs, re_ = wsj["report_period"]["start"], wsj["report_period"]["end"]
    out = out or os.path.join(ws, "strategy_compare", "_".join([base] + cases))
    os.makedirs(out, exist_ok=True)
    recs = {c: R.compare_cases(ws, base, c) for c in cases}

    # base demand B of the target key over the report period (the frozen base the converter reads)
    bdem = pd.read_csv(os.path.join(wsj["source_model"], C.DEMAND), dtype={"quantity": str})
    bk = bdem[(bdem["sku_id"] == sku) & (bdem["region"] == market) & (bdem["week"] >= rs) & (bdem["week"] <= re_)]
    B = int(sum(int(float(q)) for q in bk["quantity"]))

    allc = [base] + cases
    cts = {c: PF.case_tables(ws, c) for c in allc}
    keys = pd.DataFrame([r for c in allc for r in PF.key_rows(cts[c])])
    keys = keys[keys["region"] != "*"]
    runs = {}
    for c in allc:
        cd = C.case_dir(ws, c)
        rr = C.read_case(ws, c)["run"]
        runs[c] = CS.load_run(os.path.join(cd, "run"), os.path.join(cd, rr["money_model"]))

    ov_rows = []
    ov_total = {}
    if overflow:
        for c in allc:
            cd = C.case_dir(ws, c)
            rr = C.read_case(ws, c)["run"]
            mdir = os.path.join(cd, rr["money_model"])
            cache = os.path.join(out, f"overflow_{c}.json")
            inh = json.dumps(rr["input_hashes"], sort_keys=True)
            rec = None
            if os.path.exists(cache):
                j = json.load(open(cache, encoding="utf-8"))
                if j.get("input_hashes") == inh:
                    rec = j["record"]
            if rec is None:
                rec = OV.overflow_by_factory(mdir, R.recommended_plugins(mdir))
                json.dump({"input_hashes": inh, "record": rec}, open(cache, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
            ov_rows += OV.rows(rec, c)
            ov_total[c] = rec["pushed_total"]
    pd.DataFrame(ov_rows, columns=["case", "policy", "product", "factory", "market", "pushed", "denominator"]).to_csv(
        os.path.join(out, "overflow_by_factory_market.csv"), index=False, encoding="utf-8-sig")

    def krow(c, s, m):
        k = keys[(keys["case"] == c) & (keys["sku_id"] == s) & (keys["region"] == m)]
        if len(k) != 1:
            raise StrategyError(f"案 {c} の ①〜⑤ に {s} × {m} の行がありません")
        return k.iloc[0]

    rows = []
    p0b = recs[cases[0]]["P0_base"] if cases else C.read_case(ws, base)["run"]["summary"]["P0_report"]
    costb = _cost_cell(recs[cases[0]]["fixed_cost"], "base") if cases else 0.0
    A_base = p0b - costb
    items_base = _item_costs(recs[cases[0]]["fixed_cost"], "base") if cases else {}
    all_items = sorted({it for c in cases for it in _item_costs(recs[c]["fixed_cost"], "alt")} | set(items_base))
    hfacts = {}
    if holding_rates is not None:
        from wom.cockpit import after_cost as AC
        for c in allc:
            f = AC.case_facts(ws, c)
            hfacts[c] = f["B_report"] + f["B_warmup"]
    for c in allc:
        rec = recs.get(c)
        p0 = p0b if c == base else rec["P0_alt"]
        cost = costb if c == base else _cost_cell(rec["fixed_cost"], "alt")
        if c != base and abs(rec["P0_base"] - p0b) > 0.5:
            raise StrategyError(f"比較ごとに基準の P0 が違います（{rec['P0_base']} と {p0b}）")
        t = krow(c, sku, market)
        lg = _demand_log_totals(ws, c, sku, market, rs, re_)
        if int(t["q1"]) != B + lg["d"]:
            raise StrategyError(f"案 {c}：対象 {sku} × {market} の ① {int(t['q1'])} が B {B} ＋ d {lg['d']} と合いません")
        shelf = runs[c]["shelf"]
        sh_all = shelf[(shelf["product"] == "*") & (shelf["channel"] == "*")]
        sh_t = shelf[(shelf["product"] == sku) & (shelf["channel"] == t["market"])]
        inv = runs[c]["inv"]
        inv = inv[inv["external"].astype(int) == 0]
        inv_w = inv.groupby("week_index")["lots"].sum()
        other = keys[(keys["case"] == c) & ~((keys["sku_id"] == sku) & (keys["region"] == market))]
        otherb = keys[(keys["case"] == base) & ~((keys["sku_id"] == sku) & (keys["region"] == market))]
        mo = other.merge(otherb, on=["sku_id", "region"], suffixes=("", "_b"))
        d4 = (mo["delivered"] - mo["delivered_b"]).astype(int)
        d5 = (mo["q5"] - mo["q5_b"]).astype(int)
        moved = "; ".join(f"{r.sku_id}×{r.region} ④{int(a):+d} ⑤{int(b):+d}"
                          for r, a, b in zip(mo.itertuples(), d4, d5) if a or b)
        A = p0 - cost
        items = items_base if c == base else _item_costs(rec["fixed_cost"], "alt")
        if abs(sum(items.values()) - cost) > 0.5:
            raise StrategyError(f"案 {c}：費目ごとの額の和 {sum(items.values()):,.0f} が B_add {cost:,.0f} と合いません")
        extra = {f"cost_{it}": items.get(it, 0.0) for it in all_items}
        if holding_rates is not None:
            extra["inventory_B_group_hq"] = hfacts[c]
            extra.update(holding_columns(p0, cost, hfacts[c], holding_rates))
        rows.append({
            "case": c, "case_name": C.read_case(ws, c)["name"], "plan_id": lg["plan_id"],
            "P0": p0, "B_add": cost, "A": A, "dA_vs_base": A - A_base, "dP0_vs_base": p0 - p0b,
            "target": f"{sku}×{market}", "B_report": B, "d_report": lg["d"], "residual": lg["residual"],
            "q1": int(t["q1"]), "q2": int(t["q2"]), "q3": int(t["q3"]), "q4_delivered": int(t["delivered"]),
            "on_time": int(t["on_time"]), "early": int(t["early"]), "late": int(t["late"]), "q5": int(t["q5"]),
            "other_markets_d4_total": int(d4.sum()), "other_markets_d5_total": int(d5.sum()),
            "other_markets_changes": moved or "なし",
            "inventory_lots_max_week": int(inv_w.max()) if len(inv_w) else 0,
            "age_max_all": sh_all["fifo_age_max"].iloc[0] if len(sh_all) else "",
            "age_max_target": sh_t["fifo_age_max"].iloc[0] if len(sh_t) else "",
            "over_max_age_all": sh_all["over_max_age"].iloc[0] if len(sh_all) else "",
            "overflow_pushed_total": ov_total.get(c, "") if overflow else "未計測",
            "engine_vs_base": "（基準）" if c == base else _snapshot_same(runs[base].get("snapshot"),
                                                                       runs[c].get("snapshot")),
            "model_inputs_vs_base": "（基準）" if c == base else (
                "同じ" if C.read_case(ws, c)["run"]["input_hashes"] == C.read_case(ws, base)["run"]["input_hashes"]
                else "違う"),
            **extra,
        })
    if avoidable:
        item, ratios = avoidable
        amt = {c: expense_item_amount(runs[c], item) for c in allc}
        for r in rows:
            r[f"item_{item}"] = amt[r["case"]]
            r[f"d_item_{item}_vs_base"] = amt[r["case"]] - amt[base]
            r.update(avoidable_columns(r, item, amt[r["case"]], amt[base], ratios))
    summ = pd.DataFrame(rows)
    for k in [k for k in summ.columns if k.startswith("A_")]:
        summ["d" + k + "_vs_base"] = summ[k] - float(summ.loc[summ["case"] == base, k].iloc[0])
    if protect:
        pt = read_protect(protect, case_ids=C.case_ids(ws))
        fcase = target_floor_case(pt, cts[allc[0]]["market"], (sku, market))
        prow = []
        dbws = {}
        for c in allc:
            dbws[c] = net_increment_by_week(_d_by_week(ws, c, sku, market, rs, re_),
                                            _d_by_week(ws, fcase, sku, market, rs, re_) if fcase else None)
            prow += protect_rows(c, cts[c]["req"], cts[c]["market"], pt, (sku, market), dbws[c])
        pr = pd.DataFrame(prow)
        pr.to_csv(os.path.join(out, "protect_check.csv"), index=False, encoding="utf-8-sig")
        need = []
        prods = set(pt["sku_id"])
        for c in allc:
            dnet = sum(dbws[c].values())
            tot = int(keys[(keys["case"] == c) & keys["sku_id"].isin(prods)]["delivered"].sum())
            fl = int(pt["floor_lots"].astype(int).sum())
            need.append({"case": c, "floors_total": fl, "floor_case": fcase, "demand_increment_net": dnet,
                         "need": fl + dnet,
                         "delivered_total": tot, "surplus": tot - (fl + dnet),
                         "protected_markets_met": int((pr[(pr["case"] == c)]["status"] == "達成").sum()),
                         "protected_markets": len(pt)})
        pd.DataFrame(need).to_csv(os.path.join(out, "protect_need.csv"), index=False, encoding="utf-8-sig")
    summ.to_csv(os.path.join(out, "strategy_summary.csv"), index=False, encoding="utf-8-sig")
    keys.to_csv(os.path.join(out, "fulfillment_by_key.csv"), index=False, encoding="utf-8-sig")
    _write_md(summ, os.path.join(out, "strategy_summary.md"), ws, base, cases, rs, re_)
    wk = None
    if weekly:
        dP0 = {r.case: float(r.dP0_vs_base) for r in summ.itertuples()}
        wk = weekly_and_market(ws, base, cases, sku, market, weekly[0], weekly[1], out, dP0)
    return {"dir": out, "summary": summ, "keys": keys, "overflow": ov_rows, "compares": recs, "weekly": wk}


def _write_md(summ: pd.DataFrame, path: str, ws: str, base: str, cases: List[str], rs: str, re_: str) -> None:
    L = [f"# 施策の変換の要約（{base} を基準に {', '.join(cases)}）", "",
         f"- 作業：`{ws}`、報告期間 {rs}〜{re_}",
         "- P0＝追加費用の控除前の現行比較値、B_add＝案の外の追加費用（円）、A＝P0−B_add、ΔA＝A−A(基準)。"
         "A はグループの営業利益や Net Cash ではない", "",
         "| 案 | 名前 | P0 | B_add | A | ΔA | ① | ② | ③ | ④ | ⑤ | 他市場 ④差 | 他市場 ⑤差 | 押し戻し | エンジン（基準と） |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for r in summ.itertuples():
        L.append(f"| {r.case} | {r.case_name} | {r.P0:,.0f} | {r.B_add:,.0f} | {r.A:,.0f} | {r.dA_vs_base:+,.0f} | "
                 f"{r.q1} | {r.q2} | {r.q3} | {r.q4_delivered} | {r.q5} | {r.other_markets_d4_total:+d} | "
                 f"{r.other_markets_d5_total:+d} | {r.overflow_pushed_total} | {r.engine_vs_base} |")
    xc = [k for k in summ.columns if k.startswith("cost_") or k.startswith("H_") or k.startswith("A_")
          or (k.startswith("dA_") and k != "dA_vs_base") or k == "inventory_B_group_hq"]
    if xc:
        L += ["", "費目ごとの追加費用・在庫の保有費（年率 ÷ 52 × 連結原価の在庫・週、助走を含む）・A（＝P0 − 追加費用 − 保有費）：", ""]
        L += _md_table(summ[["case"] + xc], {k: ",.0f" for k in xc})
    L += ["", "他の市場の変化：", ""] + [f"- {r.case}：{r.other_markets_changes}" for r in summ.itertuples()]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


# ── 週別の表・市場別の金額・市場 × 年（RequestLetter_Promo_Convert_Slice2 §2.2・§2.3・§3） ──────────────────
#
# 計算は比較の道具の関数を使う：要求週別の ①〜⑤ は period_fulfillment.request_table、金額は
# compare_scenarios.money_by_week_market（money_by_week_sku と同じ明細）、工場の生産は compare_scenarios.factory_weekly、
# 在庫は vc_inventory_weekly（グループの所有）。ここでは案ごとの表を並べて差を取るだけ。

WEEKLY_COLS = ["cost_add", "target_on_time", "target_q5", "other_on_time", "other_q5", "production_all",
               "production_target_sku", "inventory_lots", "profit_r2", "profit_r2_target_market",
               "profit_r2_other_markets"]
MONEY = ["external_revenue", "external_cogs_group", "expense", "profit_r2"]   # = compare_scenarios.MONEY_COLS


def cost_by_week(cost_rows: List[dict], labels: List[str]) -> Dict[str, float]:
    """The case's cost premises (inputs/fixed_cost.csv rows) spread over their paid weeks (report currency)."""
    out = {w: 0.0 for w in labels}
    for r in cost_rows:
        amt = str(r.get("weekly_amount", "")).strip()
        if amt == "":
            raise StrategyError(f"費用の前提の {r.get('cost_item')} の週額が未設定です（週別の表に出せない）")
        a, b = r["paid_start_week"].strip(), r["paid_end_week"].strip()
        if a not in out or b not in out:
            raise StrategyError(f"費用の前提の {r.get('cost_item')} の週 {a}〜{b} が計画の週にありません")
        for w in labels[labels.index(a): labels.index(b) + 1]:
            out[w] += float(amt)
    return out


def case_frames(ws: str, cid: str) -> dict:
    """The per-case tables the weekly and market tables need (from the case's run)."""
    _ensure_path()
    from tools import compare_scenarios as CS
    from tools import period_fulfillment as PF
    cd = C.case_dir(ws, cid)
    rr = C.read_case(ws, cid)["run"]
    run = CS.load_run(os.path.join(cd, "run"), os.path.join(cd, rr["money_model"]))
    udp = os.path.join(cd, rr["udp_dir"]) if rr.get("udp_dir") else None
    labels = run["week_labels"]
    req = PF.request_table(run, udp, cid)
    money = CS.money_by_week_market(run, cid)
    fw = CS.factory_weekly(run, cid)
    inv = run["inv"]
    inv = inv[inv["external"].astype(int) == 0].groupby("week")["lots"].sum()
    p = os.path.join(cd, "inputs", C.FIXED_COST_FILE)
    cost_rows = pd.read_csv(p, dtype=str, keep_default_na=False).to_dict("records") if os.path.exists(p) else []
    return {"case": cid, "labels": labels, "req": req, "money": money,
            "prod": fw.groupby(["week", "product"])["production_lots"].sum().reset_index(),
            "inv": {w: int(inv.get(w, 0)) for w in labels}, "cost": cost_by_week(cost_rows, labels),
            "cost_items": {r["cost_item"]: cost_by_week([r], labels) for r in cost_rows}}


def _per_week(f: dict, sku: str, region: str, items: Optional[List[str]] = None) -> pd.DataFrame:
    labels = f["labels"]
    req = f["req"]
    tgt = (req["sku_id"] == sku) & (req["region"] == region)
    g_t = req[tgt].groupby("request_week")[["on_time", "q5"]].sum()
    g_o = req[~tgt].groupby("request_week")[["on_time", "q5"]].sum()
    m = f["money"]
    mt = (m["sku_id"] == sku) & (m["region"] == region)
    p_all = m.groupby("week")["profit_r2"].sum()
    p_t = m[mt].groupby("week")["profit_r2"].sum()
    prod = f["prod"]
    pr_all = prod.groupby("week")["production_lots"].sum()
    pr_s = prod[prod["product"] == sku].groupby("week")["production_lots"].sum()
    rows = []
    for w in labels:
        pa, pt = float(p_all.get(w, 0.0)), float(p_t.get(w, 0.0))
        rows.append({"week": w, "cost_add": f["cost"].get(w, 0.0),
                     "target_on_time": int(g_t["on_time"].get(w, 0)), "target_q5": int(g_t["q5"].get(w, 0)),
                     "other_on_time": int(g_o["on_time"].get(w, 0)), "other_q5": int(g_o["q5"].get(w, 0)),
                     "production_all": int(pr_all.get(w, 0)), "production_target_sku": int(pr_s.get(w, 0)),
                     "inventory_lots": int(f["inv"].get(w, 0)),
                     "profit_r2": pa, "profit_r2_target_market": pt, "profit_r2_other_markets": pa - pt,
                     **{f"cost_{it}": f.get("cost_items", {}).get(it, {}).get(w, 0.0) for it in (items or [])}})
    return pd.DataFrame(rows).set_index("week")


def _items(base: dict, alt: dict) -> List[str]:
    return sorted(set(base.get("cost_items", {})) | set(alt.get("cost_items", {})))


def weekly_table(base: dict, alt: dict, sku: str, region: str, w0: str, w1: str) -> pd.DataFrame:
    """Weekly differences alt − base (§2.3). Rows: the weeks w0..w1, every request week where ⑤ is not 0 in
    either case (any key), then 「その他の週」 and 「計」 so that every column adds up to the whole plan.
    ①〜⑤ columns are by request week; cost, production, inventory and profit by the week they happen."""
    if base["labels"] != alt["labels"]:
        raise StrategyError("2 案の計画の週が違います（週別の表を並べられない）")
    labels = base["labels"]
    for w in (w0, w1):
        if w not in labels:
            raise StrategyError(f"週 {w} が計画の週にありません")
    items = _items(base, alt)
    cols = WEEKLY_COLS + [f"cost_{it}" for it in items]
    d = _per_week(alt, sku, region, items)[cols] - _per_week(base, sku, region, items)[cols]
    q5w = set(base["req"].loc[base["req"]["q5"] > 0, "request_week"]) | set(
        alt["req"].loc[alt["req"]["q5"] > 0, "request_week"])
    sel = [w for w in labels if (w0 <= w <= w1) or w in q5w]
    out = d.loc[sel].copy()
    out.insert(0, "in_range", [w0 <= w <= w1 for w in sel])
    out.insert(1, "q5_week", [w in q5w for w in sel])
    out.loc["その他の週"] = [False, False] + d.drop(index=sel).sum().tolist()
    out.loc["計"] = [False, False] + d.sum().tolist()
    out.index.name = "week"
    return out.reset_index()


def _side_by_side(b: pd.DataFrame, a: pd.DataFrame) -> pd.DataFrame:
    idx = b.index.union(a.index)
    b, a = b.reindex(idx, fill_value=0), a.reindex(idx, fill_value=0)
    df = pd.concat({"base": b, "alt": a, "diff": a - b}, axis=1)
    df.columns = [f"{c}_{s}" for s, c in df.columns]
    return df.reset_index()


def market_money(base: dict, alt: dict) -> pd.DataFrame:
    """Report-period money by market (§2.2): external revenue, group COGS, expense, round-2 profit; base, alt,
    alt − base. The last row 「計」 is the whole (= ΔP0)."""
    def agg(f):
        m = f["money"]
        return m[m["in_report"]].groupby(["sku_id", "region", "market"])[MONEY].sum()
    df = _side_by_side(agg(base), agg(alt))
    tot = {"sku_id": "*", "region": "*", "market": "計",
           **df.drop(columns=["sku_id", "region", "market"]).sum().to_dict()}
    return pd.concat([df, pd.DataFrame([tot])], ignore_index=True)


def market_year(base: dict, alt: dict) -> pd.DataFrame:
    """Key x request year: ①・④ on time・④ delivered・⑤ for base, alt and alt − base (§2.2)."""
    cols = ["q1", "on_time", "delivered", "q5"]

    def agg(f):
        r = f["req"].assign(year=f["req"]["request_week"].str[:4])
        return r.groupby(["sku_id", "region", "year"])[cols].sum()
    return _side_by_side(agg(base), agg(alt))


def check_weekly_sums(wt: pd.DataFrame, mm: pd.DataFrame, base: dict, alt: dict, sku: str, region: str,
                      dP0: float, rs: str, re_: str) -> List[str]:
    """S4 checks: the rows of each weekly column add up to 計, and 計 equals the whole difference; the market rows
    add up to ΔP0 and to the report-period weekly profit difference. Returns the problems (empty = all add up)."""
    bad = []
    tot = wt[wt["week"] == "計"].iloc[0]
    parts = wt[wt["week"] != "計"]
    icols = [c for c in wt.columns if c.startswith("cost_") and c != "cost_add"]
    for c in WEEKLY_COLS + icols:
        if abs(parts[c].sum() - tot[c]) > 0.5:
            bad.append(f"週別の {c}：行の和 {parts[c].sum()} ≠ 計 {tot[c]}")
    if icols:
        s = wt[icols].sum(axis=1)
        if ((s - wt["cost_add"]).abs() > 0.5).any():
            bad.append("週別の費目ごとの追加費用の和が cost_add と合いません")

    def on(f, target):
        q = f["req"]
        k = (q["sku_id"] == sku) & (q["region"] == region)
        return int(q[k if target else ~k]["on_time"].sum())
    for c, target in (("target_on_time", True), ("other_on_time", False)):
        if int(tot[c]) != on(alt, target) - on(base, target):
            bad.append(f"週別の {c} の計 {int(tot[c])} ≠ 当週の差 {on(alt, target) - on(base, target)}")
    mt = mm[mm["market"] == "計"].iloc[0]
    if abs(mm[mm["market"] != "計"]["profit_r2_diff"].sum() - mt["profit_r2_diff"]) > 0.5:
        bad.append("市場別の試算利益の差の和が計と合いません")
    if abs(mt["profit_r2_diff"] - dP0) > 0.5:
        bad.append(f"市場別の試算利益の差の計 {mt['profit_r2_diff']:,.0f} ≠ ΔP0 {dP0:,.0f}")
    pw = _per_week(alt, sku, region)["profit_r2"] - _per_week(base, sku, region)["profit_r2"]
    rep = pw[(pw.index >= rs) & (pw.index <= re_)].sum()
    if abs(rep - dP0) > 0.5:
        bad.append(f"週別の試算利益の差（報告期間）{rep:,.0f} ≠ ΔP0 {dP0:,.0f}")
    return bad


def _md_table(df: pd.DataFrame, fmt: Dict[str, str]) -> List[str]:
    cols = list(df.columns)
    L = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in df.itertuples(index=False):
        cells = []
        for c, v in zip(cols, r):
            f = fmt.get(c)
            num = isinstance(v, (int, float)) and not isinstance(v, bool)
            cells.append(format(v, f) if f and num else str(v))
        L.append("| " + " | ".join(cells) + " |")
    return L


def weekly_and_market(ws: str, base: str, cases: List[str], sku: str, market: str, w0: str, w1: str, out: str,
                      dP0: Dict[str, float]) -> dict:
    """Write weekly_<case>.csv/.md, market_money_<case>.csv, market_year_<case>.csv for each case vs base;
    raise StrategyError when a sum does not add up (S4)."""
    wsj = C.open_workspace(ws)
    rs, re_ = wsj["report_period"]["start"], wsj["report_period"]["end"]
    fb = case_frames(ws, base)
    res = {}
    for c in cases:
        fa = case_frames(ws, c)
        wt = weekly_table(fb, fa, sku, market, w0, w1)
        mm = market_money(fb, fa)
        my = market_year(fb, fa)
        bad = check_weekly_sums(wt, mm, fb, fa, sku, market, dP0[c], rs, re_)
        if bad:
            raise StrategyError(f"{base} と {c}：差の和が合いません:\n  " + "\n  ".join(bad))
        wt.to_csv(os.path.join(out, f"weekly_{c}.csv"), index=False, encoding="utf-8-sig")
        mm.to_csv(os.path.join(out, f"market_money_{c}.csv"), index=False, encoding="utf-8-sig")
        my.to_csv(os.path.join(out, f"market_year_{c}.csv"), index=False, encoding="utf-8-sig")
        L = [f"# 週別の差（{c} − {base}、{w0}〜{w1} と ⑤ が出た週）", "",
             f"- 対象 {sku} × {market}。①〜⑤ の列（target_*・other_*）は要求週、費用・生産・在庫・試算利益は起きた週。",
             "- cost_add は案の外の追加費用（円、P0 に入っていない）。profit_r2 は P0 の週の値（試算）。保有費は未設定。",
             "- 「その他の週」と「計」まで足すと、どの列も計画全体の差になる。",
             "- ⑤ が出た週のうち、どの列にも差の無い週はここでは省いた（CSV には全部ある。省いた週は「その他の週」"
             "に入れていない）。", ""]
        num = [k for k in wt.columns if k not in ("week", "in_range", "q5_week")]
        nz = (wt[num].abs() > 0.5).any(axis=1)
        show = wt[wt["in_range"] | nz | wt["week"].isin(["その他の週", "計"])]
        L += _md_table(show, {k: ",.0f" for k in num})
        mmv = mm[[k for k in mm.columns if k.endswith("_diff") or k in ("sku_id", "region", "market")]]
        L += ["", f"## 市場別の金額の差（報告期間 {rs}〜{re_}、円）", ""]
        L += _md_table(mmv, {k: ",.0f" for k in mmv.columns if k.endswith("_diff")})
        myv = my[(my[[k for k in my.columns if k.endswith("_diff")]] != 0).any(axis=1)]
        L += ["", "## 市場 × 要求年の差（差のある行だけ）", ""] + (_md_table(myv, {}) if len(myv) else ["（差なし）"])
        with open(os.path.join(out, f"weekly_{c}.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(L) + "\n")
        res[c] = {"weekly": wt, "market_money": mm, "market_year": my}
    return res


# ── 費用の避けられる割合・守る供給の判定（RequestLetter_Promo_Convert_Slice4 §2） ─────────────────────────

def expense_item_amount(run: dict, item: str) -> float:
    """Report-period amount of one expense item (vc_money_lines price_type, e.g. store_operating) of the
    consolidated entities (the lines P0 subtracts)."""
    _ensure_path()
    from tools import compare_scenarios as CS
    _rev, _cogs, exp = CS.consolidated_money_frames(run)
    v3 = run["v3"][run["v3"]["group_key"] == "GROUP"]
    rep = set(v3.loc[v3["in_report"].astype(str) == "True", "week_index"].astype(int))
    e = exp[(exp["price_type"].astype(str) == item) & exp["week_index"].astype(int).isin(rep)]
    return float(e["amt_hq"].sum())


def ratio_text(r: float) -> str:
    return f"{r * 100:g}%"


def avoidable_columns(row: dict, item: str, item_alt: float, item_base: float, ratios: List[float]) -> Dict[str, float]:
    """The cost item is avoidable only by the ratio r: (1 − r) × (item(case) − item(base)) goes back into every
    A column of the row (r = 1 leaves A as it is). Works on A and on each A_<holding rate>."""
    out = {}
    back = {r: (1.0 - r) * (item_alt - item_base) for r in ratios}
    a_cols = [k for k in row if k == "A" or (k.startswith("A_") and "_avoid" not in k)]
    for k in a_cols:
        for r in ratios:
            out[f"{k}_avoid{ratio_text(r)}"] = row[k] + back[r]
    return out


PROTECT_COLS = ["sku_id", "market", "floor_lots", "basis", "note"]
PROTECT_OPTIONAL = ["floor_lots_2029", "floor_case"]


def read_protect(path: str, case_ids: Optional[List[str]] = None) -> pd.DataFrame:
    """The protected supply table: sku_id, market, floor_lots, basis, note (optional floor_lots_2029, floor_case).

    floor_case (Slice 2b) is the ID of the case whose deliveries the floor was taken from. When it is set on the
    target key's row, the demand increment subtracted from ④ is the case's increment minus that case's increment
    (the floor already contains the floor case's increment). Empty = subtract the whole increment (as before)."""
    t = pd.read_csv(path, dtype=str, keep_default_na=False)
    miss = [c for c in PROTECT_COLS if c not in t.columns]
    if miss:
        raise StrategyError(f"{path}: 列が足りません {miss}（列は {PROTECT_COLS}、任意で {PROTECT_OPTIONAL}）")
    if "floor_case" in t.columns and case_ids is not None:
        for i, v in enumerate(t["floor_case"], start=2):
            if v.strip() and v.strip() not in case_ids:
                raise StrategyError(f"{path} の {i} 行目: floor_case={v!r} はこの作業に無い案です（案は {case_ids}）")
    for c in ("floor_lots", "floor_lots_2029"):
        if c in t.columns:
            for i, v in enumerate(t[c], start=2):
                if v.strip() == "" and c == "floor_lots_2029":
                    continue
                try:
                    if int(v) < 0:
                        raise ValueError
                except ValueError:
                    raise StrategyError(f"{path} の {i} 行目: {c}={v!r} は 0 以上の整数")
    if t.duplicated(["sku_id", "market"]).any():
        raise StrategyError(f"{path}: 同じ sku_id・market の行が重複しています")
    return t


def protect_rows(case: str, req: pd.DataFrame, market_map: Dict[tuple, str], protect: pd.DataFrame,
                 target: tuple, d_by_week: Dict[str, int], year: str = "2029") -> List[dict]:
    """Check the delivered lots (④, request weeks of the report period) against the floors — a check of the
    result only, the engine is not told to protect anything. For the target key, the existing part is
    ④ − (net demand increment; with floor_case, the increment over the floor case's), and the increment is
    「届いた」 when every request week it raised was delivered in full on time (the increment's Lot_IDs are not told
    apart from the existing ones)."""
    inv = {(s, n): g for (s, g), n in market_map.items()}
    rows = []
    for p in protect.itertuples():
        reg = inv.get((p.sku_id, p.market))
        if reg is None:
            raise StrategyError(f"守る供給の表の {p.sku_id} × {p.market} に当たる市場がありません")
        k = req[(req["sku_id"] == p.sku_id) & (req["region"] == reg)]
        dlv = int(k["delivered"].sum())
        dlv_y = int(k.loc[k["request_week"].str[:4] == year, "delivered"].sum())
        is_t = (p.sku_id, reg) == target
        d_net = sum(d_by_week.values()) if is_t else 0
        existing = dlv - d_net
        r = {"case": case, "sku_id": p.sku_id, "market": p.market, "floor_lots": int(p.floor_lots),
             "delivered": dlv, "demand_increment_net": d_net, "existing_delivered": existing,
             "diff": existing - int(p.floor_lots), "status": "達成" if existing >= int(p.floor_lots) else "未達",
             f"delivered_{year}": dlv_y, "basis": p.basis,
             "floor_case": str(getattr(p, "floor_case", "")).strip()}
        f2 = getattr(p, "floor_lots_2029", "")
        if str(f2).strip() != "":
            ey = dlv_y - (sum(v for w, v in d_by_week.items() if w[:4] == year) if is_t else 0)
            r.update({f"floor_lots_{year}": int(f2), f"existing_delivered_{year}": ey,
                      f"diff_{year}": ey - int(f2), f"status_{year}": "達成" if ey >= int(f2) else "未達"})
        if is_t:
            up = [w for w, v in d_by_week.items() if v > 0]
            kk = k.set_index("request_week")
            full = [w for w in up if w in kk.index and int(kk.loc[w, "on_time"]) == int(kk.loc[w, "q1"])]
            r["demand_weeks_raised"] = len(up)
            r["demand_weeks_full_on_time"] = len(full)
            r["demand_increment_delivered"] = ("増分なし" if not up else
                                               ("届いた" if len(full) == len(up) else "一部届かない"))
        rows.append(r)
    return rows


def target_floor_case(protect: pd.DataFrame, market_map: Dict[tuple, str], target: tuple) -> str:
    """The floor_case of the target key's row ('' when the column or the value is absent)."""
    if "floor_case" not in protect.columns:
        return ""
    inv = {(s, n): g for (s, g), n in market_map.items()}
    for p in protect.itertuples():
        if (p.sku_id, inv.get((p.sku_id, p.market))) == target:
            return str(p.floor_case).strip()
    return ""


def net_increment_by_week(d_case: Dict[str, int], d_floor: Optional[Dict[str, int]]) -> Dict[str, int]:
    """The demand increment per request week to subtract from ④: the case's increment, minus the floor case's
    when a floor case is given (weeks whose difference is 0 are dropped)."""
    if d_floor is None:
        return dict(d_case)
    out = {}
    for w in sorted(set(d_case) | set(d_floor)):
        v = d_case.get(w, 0) - d_floor.get(w, 0)
        if v:
            out[w] = v
    return out


def _d_by_week(ws: str, cid: str, sku: str, market: str, rs: str, re_: str) -> Dict[str, int]:
    p = os.path.join(C.case_dir(ws, cid), "inputs", "strategy_change_log.csv")
    if not os.path.exists(p):
        return {}
    log = pd.read_csv(p, dtype=str, keep_default_na=False)
    dm = log[(log["key"] == f"{sku}|{market}") & (log["column"] == "quantity") & (log["rule"] != "residual")]
    return {w: int(a) - int(b) for w, a, b in zip(dm["week"], dm["after"], dm["before"])
            if rs <= w <= re_ and int(a) != int(b)}
