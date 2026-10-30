# -*- coding: utf-8 -*-
"""Step 4 (letter §5 step 4, §6): observe the existing Value Chain on M0 / M0t / M0a
and quantify G1-G5 against the PPC trial. Observation only.

Run the Value Chain first (from the repository root), e.g.
  python -m tools.valuechain_run --model-dir output/bsseaf_cosmetics/M0 \
      --out output/bsseaf_cosmetics/money_m0_work/M0_vc \
      --plugins "HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin"
then: python output/bsseaf_cosmetics/money_m0_work/step4_vc.py
Writes money_m0_work/checks_vc.json and g*_*.csv.
"""
import collections
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m0_common as C   # noqa: E402
import pandas as pd     # noqa: E402

W = C.HERE
PAYER = {"SG_Distributor": "E_SG（シンガポール販社）", "TH_Distributor": "E_JP（日本本社）"}
TP = {"COS_Serum": 6000.0, "COS_Cream": 5000.0}
FREIGHT_TH = 70.0


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load(case):
    d = os.path.join(W, case + "_vc")
    return {"checks": json.load(open(os.path.join(d, "vc_checks.json"), encoding="utf-8")),
            "info": json.load(open(os.path.join(d, "vc_run_info.json"), encoding="utf-8")),
            "lines": pd.read_csv(os.path.join(d, "vc_money_lines.csv.gz"), low_memory=False),
            "ships": pd.read_csv(os.path.join(d, "vc_shipments.csv.gz"), low_memory=False),
            "cmp": pd.read_csv(os.path.join(d, "vc_ppc_comparison.csv")),
            "cons": pd.read_csv(os.path.join(d, "vc_conservation.csv")),
            "ppc": pd.read_csv(os.path.join(W, case + "_result", "ppc", "ppc_event_ledger.csv"),
                               low_memory=False),
            "lots": json.load(open(os.path.join(W, case + "_result", "lots.json"), encoding="utf-8")),
            "same_plan": sha(os.path.join(d, "ppc", "ppc_event_ledger.csv"))
            == sha(os.path.join(W, case + "_result", "ppc", "ppc_event_ledger.csv"))}


def channel_of(ppc):
    rev = ppc[ppc["ppc_event_type"] == "market_revenue"]
    return dict(zip(rev["lot_id"], rev["node_id"]))


def ppc_channel_costs(ppc):
    ch = channel_of(ppc)
    x = ppc[ppc["ppc_event_type"].isin(["sga_cost", "marketing_cost"]) & ppc["node_id"].isin(C.LEAVES)].copy()
    x["channel"] = x["lot_id"].map(ch)
    x["total"] = x["amount_base"] * x["qty"]
    return x.groupby(["product_id", "node_id", "ppc_event_type"])["total"].sum()


def g1_g2(d):
    pc = ppc_channel_costs(d["ppc"])
    ln = d["lines"]
    issues = collections.Counter((i.get("node"), i.get("cost_type")) for i in d["checks"]["issues"]
                                 if i["issue"] == "revenue_based_node_cost_not_supported")
    rows = []
    for (p, node, ct), amt in pc.items():
        vc = ln[(ln["product"] == p) & (ln["node"] == node) & (ln["price_type"] == ct)]["amt_hq"].sum()
        g = "G2" if node in PAYER else "G1"
        rows.append({"G": g, "product_id": p, "node": node, "cost_type": ct, "ppc_jpy": amt,
                     "vc_jpy": float(vc), "not_in_vc_jpy": amt - float(vc),
                     "vc_issue_count": issues.get((node, ct), 0),
                     "payer_candidate": PAYER.get(node, "E_SG（シンガポール販社）")})
    return rows


def g3(d, case):
    """sell-in timing: DC ship week (VC revenue) vs the leaf's actual ship week (PPC revenue)."""
    s = d["ships"]
    out, reps = [], {}
    for leaf, dc in (("SG_Distributor", "DC_SG"), ("TH_Distributor", "DC_TH")):
        mv = s[(s["kind"] == "outbound_move") & (s["edge"] == f"{dc}->{leaf}")]
        cs = s[(s["kind"] == "consumer_sale") & (s["node"] == leaf)]
        m = mv.merge(cs[["lot_id", "ship_week", "ship_week_index"]], on="lot_id", suffixes=("_dc", "_leaf"))
        m["lag"] = m["ship_week_index_leaf"] - m["ship_week_index_dc"]
        for p, g in m.groupby("product"):
            lag = collections.Counter(g["lag"])
            out.append({"case": case, "product_id": p, "leaf": leaf, "lots": int(len(g)),
                        "lag_weeks_hist": dict(sorted((int(k), int(v)) for k, v in lag.items())),
                        "arrival_minus_dc_ship": dict(collections.Counter(
                            (g["arrival_week_index"] - g["ship_week_index_dc"]).astype(int)))})
            r = g.sort_values("ship_week_index_dc").iloc[len(g) // 2]
            lid = r["lot_id"]
            lines = d["lines"][d["lines"]["lot_id"] == lid]
            vrev = lines[(lines["kind"] == "revenue") & (lines["scope"] == "external")]
            obs = lines[lines["kind"] == "observation_sale"]
            prec = f"PSI-{p}-{leaf}-{r['ship_week_leaf']}"
            pev = d["ppc"][(d["ppc"]["lot_id"] == prec) & (d["ppc"]["ppc_event_type"] == "market_revenue")]
            reps[f"{p} {leaf}"] = {
                "lot_id": lid, "dc_ship_week": r["ship_week_dc"], "leaf_receipt_week(P)": r["arrival_week"],
                "leaf_actual_ship_week(S)": r["ship_week_leaf"],
                "vc_revenue_week": vrev["week"].tolist(), "vc_revenue_price_local":
                    (vrev["amount_orig"] / 24).tolist(), "vc_revenue_currency": vrev["currency_orig"].tolist(),
                "vc_revenue_node": vrev["node"].tolist(),
                "vc_observation_week": obs["week"].tolist(),
                "vc_observation_price_local": (obs["amount_orig"] / 24).tolist(),
                "ppc_record": prec, "ppc_revenue_week": r["ship_week_leaf"] if len(pev) else None,
                "ppc_price_local": float(pev["amount_local"].iloc[0]) if len(pev) else None}
    # revenue by week, distributors: VC (DC ship week) vs PPC (leaf ship week)
    vr = d["lines"][(d["lines"]["kind"] == "revenue") & (d["lines"]["price_type"] == "wholesale")]
    vw = vr.groupby("week")["amt_hq"].sum()
    pp = d["ppc"][(d["ppc"]["ppc_event_type"] == "market_revenue") & d["ppc"]["node_id"].isin(PAYER)].copy()
    pp["total"] = pp["amount_base"] * pp["qty"]
    pw = pp.groupby("week")["total"].sum()
    wk = pd.concat([vw.rename("vc"), pw.rename("ppc")], axis=1).fillna(0.0)
    wk["diff_vc_minus_ppc"] = wk["vc"] - wk["ppc"]
    wk.to_csv(os.path.join(W, f"g3_distributor_revenue_by_week_{case}.csv"))
    return out, reps, {"total_vc": float(wk["vc"].sum()), "total_ppc": float(wk["ppc"].sum()),
                       "weeks_with_diff": int((wk["diff_vc_minus_ppc"].abs() > 0.01).sum()),
                       "max_abs_week_diff": float(wk["diff_vc_minus_ppc"].abs().max())}


def unmet_in_vc(d, d0):
    """M0a: where the unmet Thai Lot_IDs are in the Value Chain shipments."""
    la = d["lots"]
    out = {}
    for p in C.SKUS:
        v = la[p]["TH_Distributor"]
        shipped = {i for ids in v["ship"].values() for i in ids}
        um = sorted(set(v["demand"]) - shipped)
        s = d["ships"][d["ships"]["lot_id"].isin(um)]
        out[p] = {"unmet_lots": len(um), "vc_shipment_rows": int(len(s)),
                  "vc_kinds": dict(collections.Counter(s["kind"])),
                  "vc_revenue_lines": int(len(d["lines"][d["lines"]["lot_id"].isin(um)
                                                        & (d["lines"]["kind"] == "revenue")])),
                  "example": um[0]}
    return out


def g5(d):
    """WH_JP_Released->DC_SG freight (CIF: Japan pays). VC: receiver's inventory cost."""
    ln = d["lines"]
    f = ln[(ln["price_type"] == "logistics_cost") & (ln["node"] == "DC_SG") & (ln["kind"] == "acquisition")]
    s = d["ships"]
    mv = s[(s["kind"] == "outbound_move") & (s["edge"] == "WH_JP_Released->DC_SG")]
    sold = s[(s["kind"] == "consumer_sale") & s["node"].isin(["SG_Store", "SG_EC", "SG_Distributor"])]
    out_dc = s[(s["kind"] == "outbound_move") & (s["edge"] == "DC_SG->SG_Distributor")]
    # E_SG keeps the lot (and the 60 JPY/unit in its cost) from DC_SG arrival until the external sale
    # (consumer sale for own channels, DC ship for the external distributor)
    end_w = {}
    for r in sold.itertuples():
        end_w[r.lot_id] = r.ship_week_index
    for r in out_dc.itertuples():
        end_w[r.lot_id] = r.ship_week_index
    labels = d["info"]["weeks"]
    wl = json.load(open(os.path.join(W, "base", "week_labels.json"), encoding="utf-8"))
    rs = wl.index(d["info"]["report_start"])
    held = lambda w: sum(1 for r in mv.itertuples() if r.arrival_week_index <= w < end_w.get(r.lot_id, 10**9))
    return {"vc_freight_lines": int(len(f)), "vc_entity": sorted(f["entity"].unique().tolist()),
            "vc_kind": sorted(f["kind"].unique().tolist()), "vc_amount_jpy": float(f["amt_hq"].sum()),
            "units": float(mv["units"].sum()), "per_unit_jpy": float(f["amt_hq"].sum() / mv["units"].sum()),
            "lots_in_E_SG_stock_end_of_week_before_report": held(rs - 1),
            "jpy_in_E_SG_stock_before_report": held(rs - 1) * 24 * 60.0,
            "lots_in_E_SG_stock_last_week": held(len(wl) - 1),
            "jpy_in_E_SG_stock_last_week": held(len(wl) - 1) * 24 * 60.0, "horizon": labels}


def main():
    D = {c: load(c) for c in ("M0", "M0t", "M0a")}
    res = {}
    for c, d in D.items():
        k = d["checks"]
        led_ship = collections.Counter()
        for p, dd in d["lots"].items():
            for leaf, v in dd.items():
                led_ship[(p, leaf)] = sum(len(x) for x in v["ship"].values())
        cs = d["ships"][d["ships"]["kind"] == "consumer_sale"].groupby(["product", "node"]).size()
        same_ship = all(cs.get(k_, 0) == n for k_, n in led_ship.items())
        g12 = g1_g2(d)
        pd.DataFrame(g12).to_csv(os.path.join(W, f"g1_g2_{c}.csv"), index=False)
        g3rows, reps, g3tot = g3(d, c)
        res[c] = {
            "run": "OK", "plugins": d["info"]["plugins"], "weeks": d["info"]["weeks"],
            "report_start": d["info"]["report_start"], "fx_table": d["info"]["currencies"]["fx_table"],
            "same_plan_as_ppc_trial(ppc ledger sha)": d["same_plan"],
            "consumer_sales_equal_actual_ships": same_ship,
            "model_unchanged_by_run": d["info"]["model_unchanged_by_run"],
            "conservation_ok": k["conservation_ok"], "conservation_rows": k["conservation_rows"],
            "missing_price_rows": k["missing_price_rows"], "unvalued_lines": k["unvalued_lines"],
            "fx_first_week_rate_uses": k["fx_first_week_rate_uses"], "fx_unvalued_uses": k["fx_unvalued_uses"],
            "holding_rate": k["holding_rate"], "external_sales": k["external_sales"],
            "issues": {f"{i[0]} {i[1]} {i[2]}": n for i, n in collections.Counter(
                (x["issue"], x.get("node", ""), x.get("cost_type", "")) for x in k["issues"]).items()},
            "unrealized": k.get("unrealized"), "ppc_comparison": k["ppc_comparison"],
            "ppc_comparison_rows": d["cmp"].to_dict("records"),
            "G1_G2": g12, "G3": g3rows, "G3_representative": reps, "G3_weekly": g3tot,
            "G5": g5(d),
            "tariff_vc_jpy": float(d["lines"][d["lines"]["price_type"] == "tariff_cost"]["amt_hq"].sum()),
        }
        print(c, "same plan", d["same_plan"], "| ships", same_ship, "| G3", g3tot, flush=True)
    res["M0a"]["unmet_lots_in_vc"] = unmet_in_vc(D["M0a"], D["M0"])
    # G4: tariff valuation (Thai, M0t). current PPC: transfer price x 30%; CIF assumption: (TP + 70) x 30%
    m0t = D["M0t"]["ppc"]
    th = m0t[(m0t["ppc_event_type"] == "tariff_cost") & (m0t["edge_id"] == "WH_JP_Released->DC_TH")]
    g4 = []
    for p in C.SKUS:
        x = th[th["product_id"] == p]
        units = float(x["qty"].sum())
        cur = float(x["amount_base"].iloc[0])
        cif = (TP[p] + FREIGHT_TH) * 0.30
        g4.append({"product_id": p, "units": units, "ppc_per_unit": cur, "cif_assumption_per_unit": cif,
                   "diff_per_unit": cif - cur, "ppc_total": cur * units, "cif_total": cif * units,
                   "diff_total": (cif - cur) * units})
    vct = D["M0t"]["lines"][D["M0t"]["lines"]["price_type"] == "tariff_cost"]
    res["G4"] = {"rows": g4, "vc_M0t_tariff_jpy": float(vct["amt_hq"].sum()),
                 "vc_M0t_tariff_by_entity_kind": vct.groupby(["entity", "node", "kind"])["amt_hq"].sum()
                 .reset_index().to_dict("records")}
    pd.DataFrame(g4).to_csv(os.path.join(W, "g4_tariff.csv"), index=False)
    C.write_json(os.path.join(W, "checks_vc.json"), res)
    print(json.dumps({"G4": res["G4"], "unmet": res["M0a"]["unmet_lots_in_vc"],
                      "G5": res["M0"]["G5"]}, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
