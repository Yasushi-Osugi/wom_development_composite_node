# -*- coding: utf-8 -*-
"""
wom/ppc/ppc_unused_rules.py — 一度も引かれなかった金額の規則の行（警告だけ）
==========================================================================
RequestLetter_MoneyBase_Smartx_CostFix B（2026-11-15、調査 MONEYBASE-002 の §4 の案 A ＋ C）。

PPC を回した後、読み込んだ規則の行のうち、PPC の明細（PPCEvent）に一度も現れなかった行を数える。
**止めない。trust_events に入れない。trust_event_count を変えない**（R12 の作法：規則の無い組合せは止めずに件数を残す）。

「引かれた」の判定は、規則を検索したかどうかではなく、**その行が明細に計上されたか**で決める（検索しても、額 0 の行や、
その場所では使わない費目の行は計上されないため）。鍵は調査と同じ：

    ppc_edge_cost_rule.csv       edge_id × product_id × cost_type
    ppc_tariff_rule.csv          edge_id × product_id
    ppc_node_cost_rule.csv       node_id × product_id × cost_type
    ppc_supplier_cost.csv        supplier_node × product_id
    ppc_market_price.csv         market_node × product_id
    ppc_transfer_price_rule.csv  mom_node × product_id

共有の規則（data/ppc）から読んだファイルは、そのモデルの製品の行だけを対象にする。
率も額も 0 の行は別の種類（unused_rule_row_zero）で数える。

理由の区別：
    ppc_unused_edge   PPC が作らない形の区間（<leaf>->CONSUMER：Value Chain だけが使う消費者への販売）
    no_shipment       その製品、またはその行の先の市場に実出荷（市場の売上の明細）が無い
    key_or_place      それ以外（鍵が PPC の作る区間と合わない、または PPC がその場所の行を読まない）
"""
from __future__ import annotations

import os
from collections import Counter
from typing import Dict, Iterable, List, Optional, Set

import pandas as pd

KIND = "unused_rule_row"
KIND_ZERO = "unused_rule_row_zero"
REASON_TEXT = {
    "ppc_unused_edge": "PPC が使わない区間（消費者への販売。Value Chain だけが使う）",
    "no_shipment": "実出荷なし（その製品・市場の売上の明細が無い）",
    "key_or_place": "鍵が合わない、または PPC がその場所の行を読まない",
}
FILES = ["ppc_edge_cost_rule.csv", "ppc_tariff_rule.csv", "ppc_node_cost_rule.csv", "ppc_supplier_cost.csv",
         "ppc_market_price.csv", "ppc_transfer_price_rule.csv"]


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _booked(events: Iterable) -> Dict[str, Set[tuple]]:
    k: Dict[str, Set[tuple]] = {f: set() for f in FILES}
    for e in events:
        src, edge, node, prod, t = e.source_rule, e.edge_id or "", e.node_id, e.product_id, e.ppc_event_type
        if src == "ppc_edge_cost_rule.csv":
            k[src].add((edge, prod, t))
        elif src == "ppc_tariff_rule.csv":
            k[src].add((edge, prod))
        elif src == "ppc_node_cost_rule.csv":
            k[src].add((node, prod, t))
        elif src in ("ppc_supplier_cost.csv", "ppc_market_price.csv", "ppc_transfer_price_rule.csv"):
            k[src].add((node, prod))
    return k


class _Tree:
    """product -> node -> (type, children names); leaf_out descendants of a node."""

    def __init__(self, sc_tree):
        self.nodes: Dict[str, Dict[str, tuple]] = {}
        if sc_tree is None:
            return
        for p in sc_tree.products:
            d = {}
            for n in sc_tree.iter_all_nodes(p):
                d[n.node_name] = (n.node_type, [c.node_name for c in n.children])
            self.nodes[p] = d

    def leaves_under(self, prod: str, node: str) -> Optional[Set[str]]:
        d = self.nodes.get(prod)
        if not d or node not in d:
            return None
        t = d[node][0]
        if t in ("leaf_in", "mom"):                 # inbound: every market of the product
            return {n for n, (tt, _c) in d.items() if tt == "leaf_out"}
        out, stack = set(), [node]
        while stack:
            x = stack.pop()
            tt, ch = d.get(x, ("", []))
            if tt == "leaf_out":
                out.add(x)
            stack.extend(ch)
        return out


def find_unused_rule_rows(paths: Dict[str, str], sources: Dict[str, str], events: Iterable, sc_tree=None,
                          use_node_name: bool = True) -> dict:
    """{"warnings": [rows for ppc_warnings.csv], "summary": {...}} -- reads the rule files again for line numbers."""
    events = list(events)
    booked = _booked(events)
    tree = _Tree(sc_tree)
    prods = set(tree.nodes)
    sold_prod = {e.product_id for e in events if e.ppc_event_type == "market_revenue"}
    sold_leaf = {(e.product_id, e.node_id) for e in events if e.ppc_event_type == "market_revenue"}
    rows, counts, by_reason = [], Counter(), Counter()
    for f in FILES:
        p = paths.get(f)
        if not p or not os.path.exists(p):
            continue
        shared = (sources.get(f, "model") != "model")
        df = pd.read_csv(p, dtype=str, keep_default_na=False)
        for i, r in df.iterrows():
            prod = r.get("product_id", "")
            if shared and prods and prod not in prods:
                continue                            # a shared row of another model
            if f == "ppc_edge_cost_rule.csv":
                key, zero = (r["edge_id"], prod, r["cost_type"]), _num(r["rate"]) == 0 and _num(r["fixed_amount"]) == 0
                amount, where = f"rate={r['rate']} fixed={r['fixed_amount']} {r['currency']}", r["edge_id"].split("->")[-1]
            elif f == "ppc_tariff_rule.csv":
                key, zero = (r["edge_id"], prod), _num(r["tariff_rate"]) == 0
                amount, where = f"tariff_rate={r['tariff_rate']}", r["edge_id"].split("->")[-1]
            elif f == "ppc_node_cost_rule.csv":
                key, zero = (r["node_id"], prod, r["cost_type"]), _num(r["rate"]) == 0 and _num(r["fixed_amount"]) == 0
                amount, where = f"rate={r['rate']} fixed={r['fixed_amount']} {r['currency']}", r["node_id"]
            elif f == "ppc_supplier_cost.csv":
                key, zero = (r["supplier_node"], prod), _num(r["purchase_price"]) == 0
                amount, where = f"{r['week']} {r['purchase_price']} {r['currency']}", r["supplier_node"]
            elif f == "ppc_market_price.csv":
                key, zero = (r["market_node"], prod), _num(r["market_price"]) == 0
                amount, where = f"{r['week']} {r['market_price']} {r['currency']}", r["market_node"]
            else:
                key, zero = (r["mom_node"], prod), False
                amount, where = f"{r['method']} margin={r['margin_rate']} fixed={r.get('fixed_price', '')}", r["mom_node"]
            if key in booked[f]:
                continue
            # reason
            if f in ("ppc_edge_cost_rule.csv", "ppc_tariff_rule.csv") and "CONSUMER" in r["edge_id"].split("->"):
                reason = "ppc_unused_edge"
            elif prod not in sold_prod:
                reason = "no_shipment"
            else:
                reason = "key_or_place"
                if use_node_name:
                    leaves = tree.leaves_under(prod, where)
                    if leaves is not None and leaves and not any((prod, x) in sold_leaf for x in leaves):
                        reason = "no_shipment"
            kind = KIND_ZERO if zero else KIND
            counts[kind] += 1
            if not zero:
                by_reason[reason] += 1
            rows.append({"kind": kind, "location": f"{f}:{int(i) + 2} {' | '.join(map(str, key))}",
                         "currency": "", "requested_week": "", "used_week": "", "count": 1,
                         "detail": f"{REASON_TEXT[reason]}（{reason}）。{amount}"
                                   + ("（共有の規則）" if shared else "")})
    summary = {"count": counts[KIND], "zero_count": counts[KIND_ZERO], "by_reason": dict(by_reason),
               "note": "警告だけ（止めない。trust_event_count に数えない）。一覧は ppc_warnings.csv"}
    return {"warnings": rows, "summary": summary}
