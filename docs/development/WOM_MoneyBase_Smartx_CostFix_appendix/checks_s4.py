# -*- coding: utf-8 -*-
"""§4 checks of RequestLetter_MoneyBase_Smartx_CostFix on the run output (reads only)."""
import json
import os

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "output", "moneybase_costfix")
NEW = os.path.join(OUT, "run2", "smartx-2027-2029", "ppc")
OLD = os.path.join(REPO, "output", "moneybase_unapplied", "smartx-2027-2029", "ppc")   # before (golden run)
S = os.path.join(REPO, "data", "sample", "smartx-2027-2029")
pd.set_option("display.width", 250, "display.max_columns", 40)
res = {}

led = pd.read_csv(os.path.join(NEW, "ppc_event_ledger.csv"), dtype={"edge_id": str})
led["edge_id"] = led["edge_id"].fillna("")
led["total"] = led["amount_base"] * led["qty"]
old = pd.read_csv(os.path.join(OLD, "ppc_event_ledger.csv"), dtype={"edge_id": str})
old["edge_id"] = old["edge_id"].fillna("")
old["total"] = old["amount_base"] * old["qty"]
rec = pd.read_csv(os.path.join(NEW, "ppc_lot_reconciliation.csv"))

# 1. cost per unit by product x channel vs node_cost_master (retail unit cost)
ncm = pd.read_csv(os.path.join(S, "node_cost_master.csv"))
rec["fc_total"] = rec["forward_cost_base"] * rec["qty"]
g = rec.groupby(["product_id", "channel_node"]).agg(qty=("qty", "sum"), cost=("fc_total", "sum"),
                                                    revenue=("market_revenue_base", "first")).reset_index()
g["ppc_cost_per_unit"] = (g["cost"] / g["qty"]).round(2)
# composition per unit from the ledger
comp = []
for (p, ch), sub in led[led["ppc_event_type"].isin(["supplier_cost", "logistics_cost", "tariff_cost",
                                                     "conversion_cost", "warehouse_cost", "sga_cost",
                                                     "marketing_cost", "insurance_cost"])].groupby(
        ["product_id", led["lot_id"].str.split("-").str[2]]):
    q = rec[(rec.product_id == p) & (rec.channel_node == ch)]["qty"].sum()
    d = sub.groupby("ppc_event_type")["total"].sum() / q
    comp.append({"product_id": p, "channel_node": ch, **{f"per_unit_{k}": round(v, 2) for k, v in d.items()}})
comp = pd.DataFrame(comp)
g = g.merge(comp, on=["product_id", "channel_node"], how="left")
g = g.merge(ncm.rename(columns={"sku_id": "product_id", "node_name": "channel_node"})[
    ["product_id", "channel_node", "selling_price_per_lot", "unit_cost_per_lot"]], on=["product_id", "channel_node"],
    how="left")
g["gm_pct"] = ((g["revenue"] - g["ppc_cost_per_unit"]) / g["revenue"] * 100).round(1)
g.to_csv(os.path.join(OUT, "s4_1_cost_per_unit.csv"), index=False, encoding="utf-8-sig")
print(g.to_string(index=False))

# 2. margin
k_new = json.load(open(os.path.join(NEW, "ppc_kpi_summary.json"), encoding="utf-8"))
k_old = json.load(open(os.path.join(OLD, "ppc_kpi_summary.json"), encoding="utf-8"))
res["before_after"] = {x: {"before": k_old[x], "after": k_new[x]} for x in
                       ("total_revenue_base", "total_cost_base", "gross_profit_base", "gross_margin_pct",
                        "total_tariff_base", "trust_event_count", "mom_profit_base")}
print(json.dumps(res["before_after"], indent=1))

# 3. tariff = transfer price x rate x qty (per product x edge, and representative lots)
tp = led[led.ppc_event_type == "transfer_price_set"][["lot_id", "amount_base"]].rename(columns={"amount_base": "tp"})
tr = pd.read_csv(os.path.join(S, "ppc_tariff_rule.csv"))
t = led[led.ppc_event_type == "tariff_cost"].merge(tp, on="lot_id").merge(
    tr[["edge_id", "product_id", "tariff_rate"]], on=["edge_id", "product_id"])
t["expected"] = t["tp"] * t["tariff_rate"]
t["ok"] = (t["amount_base"] - t["expected"]).abs() < 1e-6
tt = t.groupby(["product_id", "edge_id"]).agg(rate=("tariff_rate", "first"), lots=("lot_id", "count"),
                                             qty=("qty", "sum"), tariff_total=("total", "sum"),
                                             tp_min=("tp", "min"), tp_max=("tp", "max"),
                                             all_rows_tp_x_rate=("ok", "all")).reset_index()
tt.to_csv(os.path.join(OUT, "s4_3_tariff_by_edge.csv"), index=False, encoding="utf-8-sig")
print(tt.to_string(index=False))
rep = t.sort_values(["product_id", "edge_id", "qty"]).groupby(["product_id", "edge_id"]).head(1)[
    ["product_id", "edge_id", "lot_id", "week", "qty", "tp", "tariff_rate", "amount_base", "expected", "ok"]]
rep.to_csv(os.path.join(OUT, "s4_3_tariff_representative_lots.csv"), index=False, encoding="utf-8-sig")
print(rep.to_string(index=False))
res["tariff_rows_all_tp_x_rate"] = bool(t["ok"].all())

# 4. freight: edge freight now vs before, DC node freight before
def freight(df):
    lg = df[df.ppc_event_type == "logistics_cost"]
    return {"edge": lg[lg.edge_id != ""].groupby("product_id")["total"].sum().round(2).to_dict(),
            "node": lg[lg.edge_id == ""].groupby(["product_id", "node_id"])["total"].sum().round(2).to_dict()}
fn, fo = freight(led), freight(old)
edge_added = {p: round(fn["edge"].get(p, 0) - fo["edge"].get(p, 0), 2) for p in sorted(set(fn["edge"]) | set(fo["edge"]))}
dc_removed = {f"{p}@{n}": v for (p, n), v in fo["node"].items() if n.startswith("DC_")}
up_removed = {f"{p}@{n}": v for (p, n), v in fo["node"].items() if not n.startswith("DC_")}
res["freight"] = {"edge_added_by_product": edge_added, "edge_added_total": round(sum(edge_added.values()), 2),
                  "dc_node_freight_removed_total": round(sum(dc_removed.values()), 2),
                  "upstream_node_freight_removed_total": round(sum(up_removed.values()), 2),
                  "node_freight_left": {f"{p}@{n}": v for (p, n), v in fn["node"].items()}}
print(json.dumps(res["freight"], indent=1, ensure_ascii=False))
json.dump(res, open(os.path.join(OUT, "s4_checks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
