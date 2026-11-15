# -*- coding: utf-8 -*-
"""MONEYBASE-002: money rule rows that are never applied (reads model CSVs and run outputs only).

For every golden model (outputs of run_all.py in this folder):
  PPC rules  -> PPC ledger (ppc_event_ledger.csv), keyed by source_rule / edge_id / node_id / product_id /
                ppc_event_type
  VC rules   -> Value Chain money lines (vc_money_lines.csv.gz) joined to shipments (vc_shipments.csv.gz)
                for the edge, VC models only
Writes: summary_by_file.csv (rows / zero / non-zero / applied / not applied per model x file),
        unapplied_rows.csv (every non-zero row not applied, with a first guess of the reason type).
"""
import json
import os
import sys
from collections import defaultdict

import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.dirname(os.path.abspath(__file__))
MODELS = sorted(f[:-5] for f in os.listdir(os.path.join(REPO, "tests", "golden")) if f.endswith(".json"))
VC_MODELS = {"cosmetics-sg-th-2027-2029", "Cookie-jp-2026", "soysauce-jpy-2027-alloc"}
PPC_FILES = ["ppc_edge_cost_rule.csv", "ppc_tariff_rule.csv", "ppc_node_cost_rule.csv",
             "ppc_supplier_cost.csv", "ppc_market_price.csv", "ppc_transfer_price_rule.csv"]


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def tree_of(model_dir):
    t = pd.read_csv(os.path.join(model_dir, "sc_tree_master.csv"), dtype=str, keep_default_na=False)
    nodes = defaultdict(dict)   # product -> name -> (type, parent)
    for r in t.itertuples():
        nodes[r.product_name][r.node_name] = (r.node_type, r.parent_node)
    return nodes


def buildable_edges(nodes_p):
    """Edges the PPC / VC build for one product: inbound parent-child pairs, mom root -> first DAD
    (the supply point is skipped), DAD -> DAD, DAD -> leaf_out."""
    out = set()
    sps = [n for n, (t, _p) in nodes_p.items() if t == "supply_point"]
    moms = [n for n, (t, p) in nodes_p.items() if t == "mom" and not p]
    for n, (t, p) in nodes_p.items():
        if not p:
            continue
        pt = nodes_p.get(p, ("", ""))[0]
        if pt == "supply_point":
            for m in moms:
                out.add(f"{m}->{n}")
        elif t in ("leaf_in", "mom"):          # inbound: child -> parent
            out.add(f"{n}->{p}")
        else:                                   # outbound: parent -> child
            out.add(f"{p}->{n}")
    return out, sps


def classify_edge(edge, prod, nodes):
    if prod not in nodes:
        return "b", f"製品 {prod} が計画の木に無い"
    np_ = nodes[prod]
    try:
        src, dst = edge.split("->")
    except ValueError:
        return "e", f"edge_id {edge!r} の形が src->dst ではない"
    miss = [x for x in (src, dst) if x not in np_]
    if miss:
        return "b", f"ノード {miss} が製品 {prod} の計画の木に無い"
    built, sps = buildable_edges(np_)
    if src in sps or dst in sps:
        return "a", "supply point 経由の鍵（PPC・VC は supply point を飛ばした区間を作る）"
    if edge in built:
        return "c?", "木の実在の区間。実出荷・計上の有無を確かめる"
    return "a", "木のノードだが、PPC・VC が作る区間の形と違う"


def classify_node(node, prod, nodes, ctype):
    if prod not in nodes:
        return "b", f"製品 {prod} が計画の木に無い"
    if node not in nodes[prod]:
        return "b", f"ノード {node} が製品 {prod} の計画の木に無い"
    t = nodes[prod][node][0]
    return "e?", f"木のノード（{t}）。PPC がこの種類のノード・費目を計上する経路を確かめる"


def ledger_keys(led):
    k = defaultdict(set)
    for r in led[["source_rule", "edge_id", "node_id", "product_id", "ppc_event_type"]].itertuples(index=False):
        src, e, n, p, t = r
        e = "" if pd.isna(e) else e
        if src == "ppc_edge_cost_rule.csv":
            k["edge"].add((e, p, t))
        elif src == "ppc_tariff_rule.csv":
            k["tariff"].add((e, p))
        elif src == "ppc_node_cost_rule.csv":
            k["node"].add((n, p, t))
        elif src == "ppc_supplier_cost.csv":
            k["supplier"].add((n, p))
        elif src == "ppc_market_price.csv":
            k["market"].add((n, p))
        elif src == "ppc_transfer_price_rule.csv":
            k["transfer"].add((n, p))
    return k


def survey_ppc(m):
    mdir = os.path.join(REPO, "data", "sample", m)
    run = os.path.join(OUT, m)
    kpi = json.load(open(os.path.join(run, "ppc", "ppc_kpi_summary.json"), encoding="utf-8"))
    sources = (kpi.get("rule_sources") or {}).get("sources", {})
    led = pd.read_csv(os.path.join(run, "ppc", "ppc_event_ledger.csv"), dtype={"edge_id": str})
    keys = ledger_keys(led)
    nodes = tree_of(mdir)
    prods = set(nodes)
    sold = set(led.loc[led.ppc_event_type == "market_revenue", "product_id"])
    summ, rows = [], []
    for f in PPC_FILES:
        src = sources.get(f, "model")
        path = os.path.join(mdir, f) if src == "model" else os.path.join(REPO, src.split(":", 1)[1], f)
        if not os.path.exists(path):
            summ.append(dict(model=m, file=f, source=src, rows=0, rows_for_model=0, zero=0, nonzero=0,
                             applied=0, not_applied=0, zero_applied=0, zero_not_applied=0))
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        if src != "model":                     # shared: only the rows the model reads (its products)
            mine = df[df["product_id"].isin(prods)]
        else:
            mine = df
        c = dict(model=m, file=f, source=src, rows=len(df), rows_for_model=len(mine), zero=0, nonzero=0,
                 applied=0, not_applied=0, zero_applied=0, zero_not_applied=0)
        for i, r in mine.iterrows():
            line = int(i) + 2
            if f == "ppc_edge_cost_rule.csv":
                key = (r.edge_id, r.product_id, r.cost_type)
                zero = num(r.rate) == 0 and num(r.fixed_amount) == 0
                hit = key in keys["edge"]
                ty, why = classify_edge(r.edge_id, r.product_id, nodes)
                desc = f"{r.edge_id} | {r.product_id} | {r.cost_type} | rate={r.rate} fixed={r.fixed_amount} {r.currency}"
            elif f == "ppc_tariff_rule.csv":
                key = (r.edge_id, r.product_id)
                zero = num(r.tariff_rate) == 0
                hit = key in keys["tariff"]
                ty, why = classify_edge(r.edge_id, r.product_id, nodes)
                desc = f"{r.edge_id} | {r.product_id} | tariff_rate={r.tariff_rate} {r.tariff_basis} ({r.from_country}->{r.to_country})"
            elif f == "ppc_node_cost_rule.csv":
                key = (r.node_id, r.product_id, r.cost_type)
                zero = num(r.rate) == 0 and num(r.fixed_amount) == 0
                hit = key in keys["node"]
                ty, why = classify_node(r.node_id, r.product_id, nodes, r.cost_type)
                desc = f"{r.node_id} | {r.product_id} | {r.cost_type} | rate={r.rate} fixed={r.fixed_amount} {r.currency} | {r.get('note', '')}"
            elif f == "ppc_supplier_cost.csv":
                key = (r.supplier_node, r.product_id)
                zero = num(r.purchase_price) == 0
                hit = key in keys["supplier"]
                ty, why = classify_node(r.supplier_node, r.product_id, nodes, "supplier")
                desc = f"{r.week} | {r.supplier_node} | {r.product_id} | {r.purchase_price} {r.currency}"
            elif f == "ppc_market_price.csv":
                key = (r.market_node, r.product_id)
                zero = num(r.market_price) == 0
                hit = key in keys["market"]
                ty, why = classify_node(r.market_node, r.product_id, nodes, "market")
                desc = f"{r.week} | {r.market_node} | {r.product_id} | {r.market_price} {r.currency}"
            else:
                key = (r.mom_node, r.product_id)
                zero = False
                hit = key in keys["transfer"]
                ty, why = classify_node(r.mom_node, r.product_id, nodes, "transfer")
                desc = f"{r.mom_node} | {r.product_id} | {r.method} margin={r.margin_rate} fixed={r.fixed_price} {r.currency}"
            if zero:
                c["zero"] += 1
                c["zero_applied" if hit else "zero_not_applied"] += 1
                if not hit:
                    ZERO.append(dict(model=m, ledger="PPC", file=f, line=line, row=desc, type=ty, why=why))
                continue
            c["nonzero"] += 1
            if hit:
                c["applied"] += 1
                continue
            c["not_applied"] += 1
            if ty in ("c?", "e?") and r.product_id in prods and r.product_id not in sold:
                ty, why = "c", f"製品 {r.product_id} に実出荷（市場の売上の明細）が無い"
            rows.append(dict(model=m, ledger="PPC", file=f, source=src, line=line, key=" | ".join(map(str, key)),
                             row=desc, type=ty, why=why))
        summ.append(c)
    return summ, rows


VC_PRICE_FAMILY = "sale"
ZERO = []


def survey_vc(m):
    mdir = os.path.join(REPO, "data", "sample", m)
    vc = os.path.join(OUT, m, "vc")
    ml = pd.read_csv(os.path.join(vc, "vc_money_lines.csv.gz"),
                     usecols=["src_id", "product", "node", "family", "price_type", "kind"], low_memory=False)
    sh = pd.read_csv(os.path.join(vc, "vc_shipments.csv.gz"), usecols=["ship_id", "edge"], dtype=str)
    ml = ml.merge(sh.drop_duplicates("ship_id"), left_on="src_id", right_on="ship_id", how="left")
    by_edge = set(zip(ml["edge"].fillna(""), ml["product"], ml["family"], ml["price_type"]))
    # the sale to the consumer: freight rows on "<leaf>->CONSUMER" are booked at the leaf (ledger.py)
    by_edge |= {(f"{n}->CONSUMER", p_, "freight", t) for n, p_, f_, t in
                zip(ml["node"], ml["product"], ml["family"], ml["price_type"]) if f_ == "freight"}
    nodes = tree_of(mdir)
    summ, rows = [], []
    specs = [("vc_price_rule.csv", lambda r: (r.edge_id, r.product_id, "sale", r.price_type),
              lambda r: num(r.price) == 0, lambda r: f"{r.week} | {r.edge_id} | {r.product_id} | {r.price_type} | {r.price} {r.currency}"),
             ("ppc_edge_cost_rule.csv", lambda r: (r.edge_id, r.product_id, "freight", r.cost_type),
              lambda r: num(r.rate) == 0 and num(r.fixed_amount) == 0,
              lambda r: f"{r.edge_id} | {r.product_id} | {r.cost_type} | rate={r.rate} fixed={r.fixed_amount} {r.currency}"),
             ("ppc_tariff_rule.csv", lambda r: (r.edge_id, r.product_id, "tariff", "tariff_cost"),
              lambda r: num(r.tariff_rate) == 0,
              lambda r: f"{r.edge_id} | {r.product_id} | tariff_rate={r.tariff_rate}")]
    for f, keyf, zf, df_ in specs:
        p = os.path.join(mdir, f)
        if not os.path.exists(p):
            continue
        df = pd.read_csv(p, dtype=str, keep_default_na=False)
        c = dict(model=m, file=f"VC: {f}", source="model", rows=len(df), rows_for_model=len(df), zero=0, nonzero=0,
                 applied=0, not_applied=0, zero_applied=0, zero_not_applied=0)
        seen_keys = set()
        for i, r in df.iterrows():
            k = keyf(r)
            if f == "ppc_edge_cost_rule.csv" and k[3] == "insurance_cost":
                k = (k[0], k[1], "freight", "insurance_cost")
            hit = k in by_edge
            if zf(r):
                c["zero"] += 1
                c["zero_applied" if hit else "zero_not_applied"] += 1
                if not hit:
                    ty, why = classify_edge(r.edge_id, r.product_id, nodes)
                    ZERO.append(dict(model=m, ledger="VC", file=f, line=int(i) + 2, row=df_(r), type=ty, why=why))
                continue
            c["nonzero"] += 1
            if hit:
                c["applied"] += 1
                continue
            c["not_applied"] += 1
            ty, why = classify_edge(r.edge_id, r.product_id, nodes)
            rows.append(dict(model=m, ledger="VC", file=f, source="model", line=int(i) + 2,
                             key=" | ".join(map(str, k)), row=df_(r), type=ty, why=why))
        summ.append(c)
    return summ, rows


def main():
    S, U = [], []
    for m in MODELS:
        s, u = survey_ppc(m)
        S += s
        U += u
        if m in VC_MODELS:
            s, u = survey_vc(m)
            S += s
            U += u
    pd.DataFrame(S).to_csv(os.path.join(OUT, "summary_by_file.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(U).to_csv(os.path.join(OUT, "unapplied_rows.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(ZERO).to_csv(os.path.join(OUT, "zero_rows_not_applied.csv"), index=False, encoding="utf-8-sig")
    s = pd.DataFrame(S)
    print(s.groupby("model")[["rows_for_model", "zero", "nonzero", "applied", "not_applied", "zero_not_applied"]].sum().to_string())
    u = pd.DataFrame(U)
    if len(u):
        print(u.groupby(["model", "file", "type"]).size().to_string())


if __name__ == "__main__":
    main()
