# -*- coding: utf-8 -*-
"""Q3 / Q4 amounts for the unapplied groups (reads model CSVs and the run outputs only)."""
import json
import os

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(REPO, "data", "sample")
pd.set_option("display.width", 250, "display.max_rows", 200)


def led(m):
    d = pd.read_csv(os.path.join(OUT, m, "ppc", "ppc_event_ledger.csv"), dtype={"edge_id": str})
    d["edge_id"] = d["edge_id"].fillna("")
    d["total"] = d["amount_base"] * d["qty"]
    return d


def kpi(m):
    return json.load(open(os.path.join(OUT, m, "ppc", "ppc_kpi_summary.json"), encoding="utf-8"))


res = {}

# ── G-MOM: supplier_cost rows priced at a MOM node (never read; PPC reads leaf_in suppliers) ──
print("== supplier rows at a MOM node: value vs. what PPC books per unit before the transfer price")
rows = []
for m, pairs in {"smartx-2027-2029": None, "apparel-us-2026": None, "ev-europe-2026": None,
                 "ev-thailand-2026": None, "ev-thailand-2026_update": None, "smartphone-global-2026-2029": None}.items():
    d = led(m)
    sc = pd.read_csv(os.path.join(S, m, "ppc_supplier_cost.csv"), dtype=str)
    u = pd.read_csv(os.path.join(OUT, "unapplied_rows.csv"))
    un = u[(u.model == m) & (u.file == "ppc_supplier_cost.csv")]
    rev = d[d.ppc_event_type == "market_revenue"]
    for prod in sorted(set(rev.product_id)):
        q = rev[rev.product_id == prod].qty.sum()
        per = lambda t: d[(d.product_id == prod) & (d.ppc_event_type == t)].total.sum() / q
        mom_rows = [r for r in un.itertuples() if f"| {prod} |" in r.row]
        for r in mom_rows:
            node, val = r.row.split(" | ")[1], float(r.row.split(" | ")[3].split()[0])
            rows.append(dict(model=m, product=prod, mom_row_node=node, mom_row_value=val, qty=q,
                             booked_supplier_per_unit=round(per("supplier_cost"), 4),
                             booked_conversion_per_unit=round(per("conversion_cost"), 4),
                             transfer_price_per_unit=round(per("transfer_price_set"), 4),
                             if_applied_total=val * q))
g = pd.DataFrame(rows)
print(g.to_string(index=False))
g.to_csv(os.path.join(OUT, "q3_mom_supplier_rows.csv"), index=False, encoding="utf-8-sig")

# ── smartx: SmartX / SmartXNext supply-point edge freight and tariffs; DC node freight; Pro DC node freight ──
print("\n== smartx")
m = "smartx-2027-2029"
d = led(m)
k = kpi(m)
cost, gp, revt = k["total_cost_base"], k["gross_profit_base"], k["total_revenue_base"]
er = pd.read_csv(os.path.join(S, m, "ppc_edge_cost_rule.csv"))
tr = pd.read_csv(os.path.join(S, m, "ppc_tariff_rule.csv"))
nr = pd.read_csv(os.path.join(S, m, "ppc_node_cost_rule.csv"))
rev = d[d.ppc_event_type == "market_revenue"][["lot_id", "node_id", "product_id", "qty"]]
tp = d[d.ppc_event_type == "transfer_price_set"][["lot_id", "amount_base"]].rename(columns={"amount_base": "tp"})
x = rev.merge(tp, on="lot_id")
plan = []
add_freight = add_tariff = rm_node = 0.0
for prod, sp, sfx, dcs in [("SmartX", "SP_SmartX", "_g1", None), ("SmartXNext", "SP_SmartXNext", "_g3", None)]:
    mom = er[(er.product_id == prod) & er.edge_id.str.endswith("->" + sp)].iloc[0]
    for reg in ("AMER", "EMEA", "APAC"):
        ch, dc = f"Retail_{reg}{sfx}", f"DC_{reg}{sfx}"
        old = f"{sp}->{ch}"
        sub = x[(x.product_id == prod) & (x.node_id == ch)]
        q = int(sub.qty.sum())
        f_ = float(er[(er.product_id == prod) & (er.edge_id == old)].fixed_amount.iloc[0])
        t_ = float(tr[(tr.product_id == prod) & (tr.edge_id == old)].tariff_rate.iloc[0])
        dom = float(mom.fixed_amount)
        node_fr = float(nr[(nr.node_id == dc) & (nr.product_id == prod) & (nr.cost_type == "logistics_cost")].fixed_amount.iloc[0])
        tval = float((sub.qty * sub.tp).sum()) * t_
        add_freight += q * (f_ + dom)
        add_tariff += tval
        rm_node += q * node_fr
        plan.append(dict(product=prod, now_edge_freight=f"{old} {f_} (+ {mom.edge_id} {dom})",
                         after_edge_freight=f"{mom.edge_id.split('->')[0]}->{dc} {f_}; {dc}->{ch} {dom}",
                         now_tariff=f"{old} {t_}", after_tariff=f"{mom.edge_id.split('->')[0]}->{dc} {t_}",
                         dc_node_freight_removed=node_fr, qty=q, add_freight=q * (f_ + dom), add_tariff=round(tval, 2),
                         remove_node_freight=q * node_fr))
pro_rm = 0.0
for prod, dc in [("SmartXPro_IN", "DC_AMER"), ("SmartXPro_CN", "DC_APAC"), ("SmartXPro_CN", "DC_EMEA")]:
    v = d[(d.product_id == prod) & (d.node_id == dc) & (d.edge_id == "") & (d.ppc_event_type == "logistics_cost")].total.sum()
    pro_rm += v
    plan.append(dict(product=prod, now_edge_freight="(already on the physical edge)", after_edge_freight="unchanged",
                     now_tariff="(already on the physical edge)", after_tariff="unchanged",
                     dc_node_freight_removed=f"{dc}", qty="", add_freight=0, add_tariff=0, remove_node_freight=round(v, 2)))
p = pd.DataFrame(plan)
print(p.to_string(index=False))
p.to_csv(os.path.join(OUT, "smartx_fix_plan.csv"), index=False, encoding="utf-8-sig")
delta = add_freight + add_tariff - rm_node - pro_rm
print(f"cost now {cost:,.2f}  +freight {add_freight:,.2f} +tariff {add_tariff:,.2f} -SmartX/Next DC node freight {rm_node:,.2f}"
      f" -Pro DC node freight {pro_rm:,.2f}  = delta {delta:,.2f}")
print(f"GM {gp / revt:.5%} -> {(gp - delta) / revt:.5%}")
res["smartx"] = dict(cost=cost, add_freight=add_freight, add_tariff=add_tariff, remove_node_freight_x_next=rm_node,
                     remove_node_freight_pro=pro_rm, delta=delta, gm_now=gp / revt, gm_after=(gp - delta) / revt)

# smartx: other node logistics rows (what they are, booked amounts)
other = d[(d.source_rule == "ppc_node_cost_rule.csv") & (d.ppc_event_type == "logistics_cost")]
o = other.groupby(["product_id", "node_id"]).agg(unit=("amount_base", "first"), qty=("qty", "sum"), total=("total", "sum")).reset_index()
print(o.to_string(index=False))
o.to_csv(os.path.join(OUT, "smartx_node_logistics_booked.csv"), index=False, encoding="utf-8-sig")

# ── smartphone: named scenario, DC node rows and India MOM ──
print("\n== smartphone")
m = "smartphone-global-2026-2029"
d = led(m)
k = kpi(m)
rev = d[d.ppc_event_type == "market_revenue"]
qch = rev.groupby(["product_id", "node_id"]).qty.sum()
print(qch.to_string())
nr = pd.read_csv(os.path.join(S, m, "ppc_node_cost_rule.csv"))
rows = []
for r in nr.itertuples():
    if not r.node_id.startswith("DC_"):
        continue
    sfx = r.node_id[len("DC_AMER"):] if r.node_id.startswith(("DC_AMER", "DC_EMEA", "DC_APAC")) else ""
    reg = r.node_id[3:7]
    ch = f"Retail_{reg}{sfx}"
    q = int(qch.get((r.product_id, ch), 0))
    rows.append(dict(product=r.product_id, node=r.node_id, cost_type=r.cost_type, unit=r.fixed_amount, qty=q,
                     if_applied=q * r.fixed_amount))
sp = pd.DataFrame(rows)
print(sp.groupby("cost_type").if_applied.sum().to_string())
sp.to_csv(os.path.join(OUT, "smartphone_dc_rows.csv"), index=False, encoding="utf-8-sig")
edge = d[(d.source_rule == "ppc_edge_cost_rule.csv")].groupby(["product_id", "edge_id"]).agg(unit=("amount_base", "first"), total=("total", "sum"))
print(edge.to_string())
amer16 = int(qch.get(("Phone16", "Retail_AMER"), 0))
print(f"Phone16 Retail_AMER qty {amer16} (lane: EMS_A_IN in the plan; PPC books it on EMS_A_CN)")
res["smartphone"] = dict(cost=k["total_cost_base"], revenue=k["total_revenue_base"],
                         dc_conversion=float(sp[sp.cost_type == "conversion_cost"].if_applied.sum()),
                         dc_logistics=float(sp[sp.cost_type == "logistics_cost"].if_applied.sum()),
                         phone16_amer_qty=amer16)

# ── soysauce-us: EU rows, no EU demand ──
m = "soysauce-us-2027"
dem = pd.read_csv(os.path.join(S, m, "demand_forecast.csv"))
eu = dem[dem.region.isin(["EU_FR", "EU_BE", "EU_NL", "Rest_FR", "Rest_BE", "Rest_NL", "FR", "BE", "NL"])]
print("\n== soysauce-us demand by region:", dem.groupby("region").quantity.sum().to_dict())

json.dump(res, open(os.path.join(OUT, "amounts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
