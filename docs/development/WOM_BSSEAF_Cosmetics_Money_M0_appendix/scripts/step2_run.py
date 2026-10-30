# -*- coding: utf-8 -*-
"""Steps 1-3 (letter §5): unit check, run M0 / M0t / M0a and check A1-A8.

python output/bsseaf_cosmetics/money_m0_work/step2_run.py   (after gen_money.py)

Observation only: PPCRuleSet getters and ppc_runner._run_engine are wrapped in
this process to record which rule lookups found a row; standard code is unchanged.
Writes money_m0_work/<case>_result/ and money_m0_work/checks_ppc.json.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m0_common as C   # noqa: E402
import pandas as pd     # noqa: E402

from wom.ppc import ppc_runner                                   # noqa: E402
from wom.ppc.ppc_rules import PPCRuleSet, resolve_ppc_rules      # noqa: E402

TOL_UNIT = 1e-6


def tol_total(expected):
    return max(0.01, abs(expected) * 1e-9)


# ── §4.1 expected per unit (JPY, tariff 0%, before rounding) ──────────────
EXP = {
    ("COS_Serum", "SG_Store"): (18975, 10940.75, 8034.25),
    ("COS_Serum", "SG_EC"): (18055, 8163.50, 9891.50),
    ("COS_Serum", "SG_Distributor"): (8510, 2827.50, 5682.50),
    ("COS_Serum", "TH_Distributor"): (8550, 2837.50, 5712.50),
    ("COS_Cream", "SG_Store"): (15870, 9243.50, 6626.50),
    ("COS_Cream", "SG_EC"): (15065, 6966.50, 8098.50),
    ("COS_Cream", "SG_Distributor"): (7130, 2458.50, 4671.50),
    ("COS_Cream", "TH_Distributor"): (7200, 2470.00, 4730.00),
}
THAI_TARIFF = {"COS_Serum": 1800.0, "COS_Cream": 1500.0}        # §4.2 (current PPC: transfer price x 30%)

IGNORED = {"transfer_price_set", "landed_cost_total", "backward_allowable", "mom_profit"}


def category(ev):
    t, node, edge = ev["ppc_event_type"], ev["node_id"], ev["edge_id"]
    if t == "market_revenue":
        return "revenue"
    if t == "supplier_cost":
        return "material"
    if t == "conversion_cost" and node == "Factory_JP":
        return "processing"
    if t in ("logistics_cost", "insurance_cost") and isinstance(edge, str) and edge:
        return "freight"
    if t == "tariff_cost":
        return "tariff"
    if t in ("warehouse_cost", "conversion_cost") and node in ("WH_JP_Released", "DC_SG", "DC_TH"):
        return "node_cost"
    if t in ("sga_cost", "marketing_cost") and node in C.LEAVES:
        return "channel_cost"
    if t in IGNORED:
        return None
    raise ValueError(f"unclassified PPC event: {t} {node} {edge}")


# ── lookup observation ────────────────────────────────────────────────────
LOOK = collections.defaultdict(collections.Counter)     # getter -> Counter[(key, found)]


def _wrap(name, found):
    orig = getattr(PPCRuleSet, name)

    def f(self, a, b, *rest):
        r = orig(self, a, b, *rest)
        LOOK[name][(f"{a}|{b}", found(r))] += 1
        return r
    setattr(PPCRuleSet, name, f)


_wrap("get_node_costs", lambda r: len(r) > 0)
_wrap("get_edge_costs", lambda r: len(r) > 0)
_wrap("get_tariff", lambda r: r is not None)
_wrap("get_transfer_price_rule", lambda r: r is not None)
_orig_pz = PPCRuleSet.get_profit_zone


def _pz(self, node_id, product_id):
    LOOK["get_profit_zone"][(f"{node_id}|{product_id}", (node_id, product_id) in self._profit_zone_cache)] += 1
    return _orig_pz(self, node_id, product_id)


PPCRuleSet.get_profit_zone = _pz
LAST = {}
_orig_engine = ppc_runner._run_engine


def _engine(*a, **k):
    result, rules = _orig_engine(*a, **k)
    LAST["rules"] = rules
    LAST["engine_calls"] = LAST.get("engine_calls", 0) + 1
    return result, rules


ppc_runner._run_engine = _engine


# ── ledger analysis ───────────────────────────────────────────────────────
def analyse_ledger(ppc_dir):
    ev = pd.read_csv(os.path.join(ppc_dir, "ppc_event_ledger.csv"), low_memory=False,
                     dtype={"edge_id": str})
    ev["edge_id"] = ev["edge_id"].fillna("")
    ev["cat"] = ev.apply(category, axis=1)
    types = ev.groupby("ppc_event_type").size().to_dict()
    ev = ev[ev["cat"].notna()].copy()
    rev = ev[ev["cat"] == "revenue"]
    if rev["lot_id"].duplicated().any():
        raise ValueError("a PPC record has two market_revenue events")
    chan = dict(zip(rev["lot_id"], rev["node_id"]))
    ev["channel"] = ev["lot_id"].map(chan)
    if ev["channel"].isna().any():
        raise ValueError("cost events without a revenue record")
    ev["total"] = ev["amount_base"] * ev["qty"]
    # per unit: for each record, the per-unit sum by category (must be the same in every record)
    per_rec = ev.pivot_table(index=["lot_id", "product_id", "channel"], columns="cat",
                             values="amount_base", aggfunc="sum", fill_value=0.0).reset_index()
    cats = [c for c in ("revenue", "material", "processing", "freight", "node_cost", "tariff", "channel_cost")
            if c in per_rec.columns]
    for c in ("material", "processing", "freight", "node_cost", "tariff", "channel_cost"):
        if c not in per_rec.columns:
            per_rec[c] = 0.0
    per_rec["cost"] = per_rec[["material", "processing", "freight", "node_cost", "tariff", "channel_cost"]].sum(axis=1)
    per_rec["profit"] = per_rec["revenue"] - per_rec["cost"]
    # events per record by (type, node, edge): every one must appear exactly once per record
    cnt = ev.groupby(["lot_id", "ppc_event_type", "node_id", "edge_id"]).size()
    once = bool((cnt == 1).all())
    # detail per unit by component (first record of each SKU x channel; all records equal is checked below)
    comp = (ev.groupby(["product_id", "channel", "cat", "ppc_event_type", "node_id", "edge_id"])
            ["amount_base"].agg(["min", "max", "first"]).reset_index())
    comp_spread = float((comp["max"] - comp["min"]).abs().max())
    units = rev.groupby(["product_id", "node_id"])["qty"].sum()
    tot = ev.groupby(["product_id", "channel", "cat"])["total"].sum().unstack(fill_value=0.0)
    rows = []
    for (p, ch), g in per_rec.groupby(["product_id", "channel"]):
        spread = float((g[["revenue", "cost", "profit"]].max() - g[["revenue", "cost", "profit"]].min()).abs().max())
        t = tot.loc[(p, ch)]
        r = {"product_id": p, "channel": ch, "records": int(len(g)), "units": int(units[(p, ch)]),
             "lots": int(units[(p, ch)]) // C.CPU,
             "unit_revenue": float(g["revenue"].iloc[0]), "unit_cost": float(g["cost"].iloc[0]),
             "unit_profit": float(g["profit"].iloc[0]), "unit_spread_across_records": spread}
        for c in ("material", "processing", "freight", "node_cost", "tariff", "channel_cost"):
            r["unit_" + c] = float(g[c].iloc[0])
        for c in ("revenue", "material", "processing", "freight", "node_cost", "tariff", "channel_cost"):
            r["total_" + c] = float(t.get(c, 0.0))
        r["total_cost"] = sum(r["total_" + c] for c in
                              ("material", "processing", "freight", "node_cost", "tariff", "channel_cost"))
        r["total_profit"] = r["total_revenue"] - r["total_cost"]
        rows.append(r)
    return {"rows": rows, "event_types": types, "each_event_once_per_record": once,
            "component_spread": comp_spread, "categories": cats,
            "components": comp.rename(columns={"first": "amount_per_unit"}).to_dict("records"),
            "ev": ev}


def lookups_table():
    out = []
    for getter, c in LOOK.items():
        keys = collections.defaultdict(dict)
        for (k, found), n in c.items():
            keys[k][found] = n
        for k, d in sorted(keys.items()):
            out.append({"getter": getter, "key": k, "found": d.get(True, 0), "not_found": d.get(False, 0)})
    return out


def run_one(case):
    md = os.path.join(C.COS, case)
    out = os.path.join(C.HERE, case + "_result")
    LOOK.clear()
    LAST.clear()
    h_before = C.input_hashes(md), C.input_hashes(md, money=True)
    snap, tree = C.run_case(md, out)
    h_after = C.input_hashes(md), C.input_hashes(md, money=True)
    lots, wl = C.lot_record(tree)
    C.write_json(os.path.join(out, "lots.json"), lots)
    kpi = json.load(open(os.path.join(out, "ppc", "ppc_kpi_summary.json"), encoding="utf-8"))
    rules = LAST.get("rules")
    lk = dict(rules.lookup_log) if rules is not None else {}
    led = analyse_ledger(os.path.join(out, "ppc"))
    ev = led.pop("ev")
    lt = lookups_table()
    pd.DataFrame(lt).to_csv(os.path.join(out, "rule_lookups.csv"), index=False)
    pd.DataFrame(led["rows"]).to_csv(os.path.join(out, "sku_channel.csv"), index=False)
    pd.DataFrame(led["components"]).to_csv(os.path.join(out, "unit_components.csv"), index=False)
    return {"snap": snap, "tree": tree, "lots": lots, "wl": wl, "kpi": kpi, "lookup_log": lk,
            "ledger": led, "ev": ev, "lookups": lt, "engine_calls": LAST.get("engine_calls"),
            "inputs_unchanged_by_run": h_before == h_after, "out": out, "md": md}


def unit_check(r):
    """A4 (letter §5 step 1): the same rules on a small synthetic input -- 1 unit and
    24 units of every SKU x channel in one week. The per-unit amounts must be the same,
    the totals x24, and each cost event once per record (the EC SGD 3 once per unit)."""
    rules = PPCRuleSet.load_from_sources(resolve_ppc_rules(r["md"]))
    week = r["wl"][len(r["wl"]) // 2]
    rows = []
    for p in C.SKUS:
        for ch in C.LEAVES:
            for q in (1, 24):
                rows.append({"lot_id": f"SYN-{p}-{ch}-q{q}", "week": week, "channel_node": ch,
                             "product_id": p, "qty": q})
    sales = pd.DataFrame(rows)
    sales.to_csv(os.path.join(C.HERE, "unit_check_input.csv"), index=False)
    res, _ = _orig_engine(sales, rules, r["tree"], set(C.SKUS), False, "JPY")
    ev = pd.DataFrame([vars(e) for e in res.ppc_events])
    ev["edge_id"] = ev["edge_id"].fillna("")
    ev["cat"] = ev.apply(category, axis=1)
    ev = ev[ev["cat"].notna()]
    ev["total"] = ev["amount_base"] * ev["qty"]
    out = []
    for p in C.SKUS:
        for ch in C.LEAVES:
            a = ev[ev["lot_id"] == f"SYN-{p}-{ch}-q1"]
            b = ev[ev["lot_id"] == f"SYN-{p}-{ch}-q24"]
            rev1, rev24 = a[a["cat"] == "revenue"]["total"].sum(), b[b["cat"] == "revenue"]["total"].sum()
            c1, c24 = a[a["cat"] != "revenue"]["total"].sum(), b[b["cat"] != "revenue"]["total"].sum()
            ec_ship = b[(b["ppc_event_type"] == "sga_cost") & (b["node_id"] == "SG_EC")]
            out.append({
                "product_id": p, "channel": ch, "rev_1": rev1, "rev_24": rev24, "cost_1": c1, "cost_24": c24,
                "ratio_ok": abs(rev24 - 24 * rev1) <= tol_total(24 * rev1) and abs(c24 - 24 * c1) <= tol_total(24 * c1),
                "events_q1": int(len(a)), "events_q24": int(len(b)),
                "same_events": sorted(zip(a["ppc_event_type"], a["node_id"], a["edge_id"]))
                == sorted(zip(b["ppc_event_type"], b["node_id"], b["edge_id"])),
                "each_once": bool((b.groupby(["ppc_event_type", "node_id", "edge_id"]).size() == 1).all()),
                "ec_sga_events": int(len(ec_ship)),
                "ec_sga_per_unit_jpy": float(ec_ship["amount_base"].iloc[0]) if len(ec_ship) else None,
            })
    pd.DataFrame(out).to_csv(os.path.join(C.HERE, "unit_check_result.csv"), index=False)
    return {"week": week, "rows": out, "ok": all(x["ratio_ok"] and x["same_events"] and x["each_once"]
                                                 for x in out)}


def per_unit_checks(rows, case):
    res = []
    for r in rows:
        k = (r["product_id"], r["channel"])
        rev, cost, prof = EXP[k]
        if case == "M0t" and r["channel"] == "TH_Distributor":
            cost += THAI_TARIFF[r["product_id"]]
            prof -= THAI_TARIFF[r["product_id"]]
        d = max(abs(r["unit_revenue"] - rev), abs(r["unit_cost"] - cost), abs(r["unit_profit"] - prof))
        res.append({"product_id": k[0], "channel": k[1], "expected": (rev, cost, prof),
                    "actual": (r["unit_revenue"], r["unit_cost"], r["unit_profit"]),
                    "max_abs_diff": d, "ok": d <= TOL_UNIT and r["unit_spread_across_records"] <= TOL_UNIT})
    return res


def flow_tables(out):
    fc = os.path.join(out, "flow_check")
    return (C.read_csv(os.path.join(fc, "flow_check_nodes.csv")),
            C.read_csv(os.path.join(fc, "flow_check_market.csv")))


def ship_counts(lots):
    """{(prod, leaf, week): number of Lot_IDs actually shipped}"""
    return {(p, l, w): len(ids) for p, d in lots.items() for l, v in d.items() for w, ids in v["ship"].items()}


def ppc_qty_by_record(ev):
    rev = ev[ev["cat"] == "revenue"]
    return {r.lot_id: int(r.qty) for r in rev.itertuples()}


def main():
    base = json.load(open(os.path.join(C.HERE, "base", "base_record.json"), encoding="utf-8"))
    gen = json.load(open(os.path.join(C.HERE, "gen_record.json"), encoding="utf-8"))
    R = {c: run_one(c) for c in ("M0", "M0t", "M0a")}
    checks = {"unit_check": unit_check(R["M0"])}
    src_of = {"M0": "C3b", "M0t": "C3b", "M0a": "C3a"}
    for case, r in R.items():
        kpi, led = r["kpi"], r["ledger"]
        rows = led["rows"]
        c = {"period": r["snap"]["period"], "config": r["snap"]["config"],
             "inputs_unchanged_by_run": r["inputs_unchanged_by_run"], "engine_calls": r["engine_calls"]}
        # A1
        bad_log = {f"{k[0]} {k[1]} x {k[2]}": n for k, n in r["lookup_log"].items()}
        c["A1"] = {"valuation_status": kpi.get("valuation_status"), "excluded": kpi.get("excluded", []),
                   "lookup_log_missing_or_before_first": bad_log,
                   "price_before_first_rule_week": kpi.get("price_before_first_rule_week", []),
                   "ok": kpi.get("valuation_status") == "評価済み" and not kpi.get("excluded")
                   and not bad_log and not kpi.get("price_before_first_rule_week")}
        # A2
        srcs = (kpi.get("rule_sources") or {}).get("sources", {})
        c["A2"] = {"rule_sources": kpi.get("rule_sources"),
                   "ok": bool(srcs) and all(v == "model" for v in srcs.values())
                   and not (kpi.get("rule_sources") or {}).get("missing")
                   and not (kpi.get("rule_sources") or {}).get("shared_rules_dir")}
        # A3
        pu = per_unit_checks(rows, case)
        c["A3"] = {"rows": pu, "ok": all(x["ok"] for x in pu) and len(pu) == 8}
        # A4 (ledger side; the synthetic part is checks["unit_check"])
        c["A4"] = {"each_event_once_per_record": led["each_event_once_per_record"],
                   "per_unit_component_spread": led["component_spread"],
                   "ok": led["each_event_once_per_record"] and led["component_spread"] <= TOL_UNIT
                   and checks["unit_check"]["ok"]}
        # A5
        t_rev = sum(x["total_revenue"] for x in rows)
        t_cost = sum(x["total_cost"] for x in rows)
        t_prof = t_rev - t_cost
        k_rev, k_cost, k_prof = kpi["total_revenue_base"], kpi["total_cost_base"], kpi["gross_profit_base"]
        c["A5"] = {"ledger": {"revenue": t_rev, "cost": t_cost, "profit": t_prof},
                   "kpi": {"revenue": k_rev, "cost": k_cost, "profit": k_prof},
                   "ledger_by_category": {cat: sum(x["total_" + cat] for x in rows) for cat in
                                          ("material", "processing", "freight", "node_cost", "tariff", "channel_cost")},
                   "total_qty_units": kpi.get("total_qty_units"),
                   "ok": abs(t_rev - k_rev) <= tol_total(k_rev) and abs(t_cost - k_cost) <= tol_total(k_cost)
                   and abs(t_prof - k_prof) <= tol_total(k_prof)}
        # A6
        bn, bm = flow_tables(os.path.join(C.HERE, "base", src_of[case] + "_result"))
        mn, mm = flow_tables(r["out"])
        q_src = base[src_of[case]]["quantity_input_sha256"]
        q_now = C.input_hashes(r["md"])
        nodes_ok = all(x["status"] == "OK" and int(x["conservation_diff"]) == 0 for x in mn)
        c["A6"] = {"quantity_inputs_equal_to_base": q_src == q_now,
                   "flow_nodes_equal_to_base": bn == mn, "flow_market_equal_to_base": bm == mm,
                   "table1_conservation_ok": nodes_ok,
                   "ok": q_src == q_now and bn == mn and bm == mm and nodes_ok}
        # shipments (Lot_ID) x 24 == PPC record qty, per SKU x channel x week
        sc = ship_counts(r["lots"])
        pq = ppc_qty_by_record(r["ev"])
        mism = [(p, l, w, n * C.CPU, pq.get(f"PSI-{p}-{l}-{w}")) for (p, l, w), n in sc.items()
                if pq.get(f"PSI-{p}-{l}-{w}") != n * C.CPU]
        extra = [k for k in pq if not any(k == f"PSI-{p}-{l}-{w}" for (p, l, w) in sc)]
        c["ship_vs_ppc_qty"] = {"records": len(sc), "mismatch": mism[:10], "ppc_records_without_ship": extra[:10],
                                "ok": not mism and not extra}
        c["sku_channel"] = rows
        checks[case] = c
        print(case, {k: v.get("ok") for k, v in c.items() if isinstance(v, dict) and "ok" in v}, flush=True)

    # §4.2 M0t vs M0
    m0 = {(x["product_id"], x["channel"]): x for x in checks["M0"]["sku_channel"]}
    mt = {(x["product_id"], x["channel"]): x for x in checks["M0t"]["sku_channel"]}
    thai_units = {p: m0[(p, "TH_Distributor")]["units"] for p in C.SKUS}
    exp_drop = sum(thai_units[p] * THAI_TARIFF[p] for p in C.SKUS)
    drop = checks["M0"]["A5"]["kpi"]["profit"] - checks["M0t"]["A5"]["kpi"]["profit"]
    sg_same = all(abs(m0[k][f] - mt[k][f]) <= TOL_UNIT for k in m0 if k[1] != "TH_Distributor"
                  for f in ("units", "unit_revenue", "unit_cost", "unit_profit", "total_profit"))
    th_rev_same = all(m0[(p, "TH_Distributor")]["units"] == mt[(p, "TH_Distributor")]["units"]
                      and abs(m0[(p, "TH_Distributor")]["unit_revenue"] - mt[(p, "TH_Distributor")]["unit_revenue"])
                      <= TOL_UNIT for p in C.SKUS)
    tariff_unit = {p: mt[(p, "TH_Distributor")]["unit_tariff"] for p in C.SKUS}
    checks["M0t_vs_M0"] = {"thai_units": thai_units, "expected_profit_drop": exp_drop, "profit_drop": drop,
                           "tariff_per_unit": tariff_unit, "sg_unchanged": sg_same,
                           "thai_qty_and_price_unchanged": th_rev_same,
                           "ok": abs(drop - exp_drop) <= tol_total(exp_drop) and sg_same and th_rev_same
                           and all(abs(tariff_unit[p] - THAI_TARIFF[p]) <= TOL_UNIT for p in C.SKUS)}

    # §4.3 / A7 M0a
    la, l0 = R["M0a"]["lots"], R["M0"]["lots"]
    unmet = {p: {l: sorted(set(v["demand"]) - {i for ids in v["ship"].values() for i in ids})
                 for l, v in la[p].items()} for p in la}
    unmet0 = {p: {l: sorted(set(v["demand"]) - {i for ids in v["ship"].values() for i in ids})
                  for l, v in l0[p].items()} for p in l0}
    demand_same = all(set(la[p][l]["demand"]) == set(l0[p][l]["demand"]) for p in la for l in la[p])
    demand_lots = sum(len(v["demand"]) for d in la.values() for v in d.values())
    ship_lots_a = sum(len(ids) for d in la.values() for v in d.values() for ids in v["ship"].values())
    sc0, sca = ship_counts(l0), ship_counts(la)
    non_thai_same = ({k: n for k, n in sc0.items() if k[1] != "TH_Distributor"}
                     == {k: n for k, n in sca.items() if k[1] != "TH_Distributor"})
    ma = {(x["product_id"], x["channel"]): x for x in checks["M0a"]["sku_channel"]}
    rev_diff = {p: m0[(p, "TH_Distributor")]["total_revenue"] - ma[(p, "TH_Distributor")]["total_revenue"]
                for p in C.SKUS}
    exp_diff = {"COS_Serum": 104 * 24 * 1900 * 4.5, "COS_Cream": 88 * 24 * 1600 * 4.5}
    total_diff = checks["M0"]["A5"]["kpi"]["revenue"] - checks["M0a"]["A5"]["kpi"]["revenue"]
    rev_units_a = int(R["M0a"]["ev"][R["M0a"]["ev"]["cat"] == "revenue"]["qty"].sum())
    # representative lots: one unmet Thai lot per SKU, and where it would have been booked
    rep = {}
    for p in C.SKUS:
        lid = unmet[p]["TH_Distributor"][0]
        dem_w = next(R["M0a"]["wl"][w] for w in range(len(R["M0a"]["wl"]))
                     if lid in next(n for n in R["M0a"]["tree"].iter_all_nodes(p)
                                    if n.node_name == "TH_Distributor").psi4demand[w][0])
        ship_w0 = next((w for w, ids in l0[p]["TH_Distributor"]["ship"].items() if lid in ids), None)
        rep[p] = {"lot_id": lid, "demand_week": dem_w, "M0_ship_week": ship_w0,
                  "M0a_shipped": False,
                  "M0_ppc_record": f"PSI-{p}-TH_Distributor-{ship_w0}",
                  "M0_ppc_record_qty": ppc_qty_by_record(R["M0"]["ev"]).get(f"PSI-{p}-TH_Distributor-{ship_w0}"),
                  "M0a_ppc_record_qty": ppc_qty_by_record(R["M0a"]["ev"]).get(f"PSI-{p}-TH_Distributor-{ship_w0}")}
    checks["A7"] = {
        "demand_lots": demand_lots, "ship_lots": ship_lots_a,
        "unmet_lots": {p: {l: len(v) for l, v in d.items() if v} for p, d in unmet.items()},
        "M0_unmet_lots": sum(len(v) for d in unmet0.values() for v in d.values()),
        "demand_same_as_M0": demand_same, "non_thai_shipments_same_as_M0": non_thai_same,
        "ship_lots_M0_minus_M0a": sum(sc0.values()) - sum(sca.values()),
        "revenue_units_M0a": rev_units_a, "expected_units": 3864 * 24,
        "revenue_diff_by_sku": rev_diff, "expected_diff_by_sku": exp_diff,
        "revenue_diff_total": total_diff, "expected_total": 36547200.0,
        "representative": rep,
        "unit_price_same_as_M0": checks["M0a"]["A3"]["ok"],
    }
    a7 = checks["A7"]
    a7["ok"] = (demand_lots == 4056 and ship_lots_a == 3864
                and a7["unmet_lots"] == {"COS_Serum": {"TH_Distributor": 104}, "COS_Cream": {"TH_Distributor": 88}}
                and a7["M0_unmet_lots"] == 0 and demand_same and non_thai_same
                and a7["ship_lots_M0_minus_M0a"] == 192 and rev_units_a == 92736
                and all(abs(rev_diff[p] - exp_diff[p]) <= tol_total(exp_diff[p]) for p in C.SKUS)
                and abs(total_diff - 36547200.0) <= tol_total(36547200.0))

    # A8: every rule row vs lookups (M0 and M0t share the rows; M0a the same files)
    a8 = {}
    for case, r in R.items():
        rows = collections.defaultdict(lambda: [0, 0])
        for x in r["lookups"]:
            rows[(x["getter"], x["key"])][0] += x["found"]
            rows[(x["getter"], x["key"])][1] += x["not_found"]
        md = r["md"]
        table = []
        for fn, getter, key_cols in (("ppc_node_cost_rule.csv", "get_node_costs", ("node_id", "product_id")),
                                     ("ppc_edge_cost_rule.csv", "get_edge_costs", ("edge_id", "product_id")),
                                     ("ppc_tariff_rule.csv", "get_tariff", ("edge_id", "product_id")),
                                     ("ppc_transfer_price_rule.csv", "get_transfer_price_rule",
                                      ("mom_node", "product_id"))):
            for row in C.read_csv(os.path.join(md, fn)):
                key = "|".join(row[k] for k in key_cols)
                amt = row.get("fixed_amount", row.get("tariff_rate", row.get("fixed_price", "")))
                rate = row.get("rate", "")
                nonzero = any(v not in ("", "0", "0.0") for v in (amt, rate))
                looked = rows.get((getter, key), [0, 0])[0]
                state = ("費用あり" if nonzero else "明示の 0") if looked else "行はあるが計算が参照しない"
                table.append({"file": fn, "key": key, "cost_type": row.get("cost_type", row.get("tariff_basis", "")),
                              "basis": row.get("basis", ""), "rate": rate, "amount": amt,
                              "currency": row.get("currency", ""), "lookups": looked, "state": state})
        missing = [{"getter": g, "key": k, "lookups": v[1]} for (g, k), v in rows.items()
                   if v[1] and not v[0] and g != "get_profit_zone"]
        pz = sorted({k for (g, k), v in rows.items() if g == "get_profit_zone" and v[1]})
        pd.DataFrame(table).to_csv(os.path.join(r["out"], "rule_rows_state.csv"), index=False)
        a8[case] = {"rows": table, "lookups_without_rule": missing,
                    "profit_zone_lookups_without_row": pz,
                    "ok": not missing}
    checks["A8"] = {c: {k: v for k, v in a.items() if k != "rows"} for c, a in a8.items()}
    checks["A8"]["ok"] = all(a["ok"] for a in a8.values())
    checks["A8_rows_M0"] = a8["M0"]["rows"]
    checks["A8_rows_M0t_tariff"] = [x for x in a8["M0t"]["rows"] if x["file"] == "ppc_tariff_rule.csv"]
    checks["gen_record"] = gen
    C.write_json(os.path.join(C.HERE, "checks_ppc.json"), checks)
    print("unit_check", checks["unit_check"]["ok"], "| M0t_vs_M0", checks["M0t_vs_M0"]["ok"],
          "| A7", a7["ok"], "| A8", checks["A8"]["ok"])


if __name__ == "__main__":
    main()
