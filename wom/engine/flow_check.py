"""
wom/engine/flow_check.py
========================
Flow Check -- network-wide flow integrity of a finished plan
(RequestLetter_FlowCheck_CapNaming_WarmupTrial, Part 1 V3).

Read-only: takes the planned SCTree (psi4supply, node._actual_ship set by
ForwardPlanner.run) and the ForwardPlanResult of each product, and builds two
tables so that a person can check, without computing by hand:

  Table 1 (per node)   is the stock conserved, and did the node receive what
                       its supplier shipped towards it?
  Table 2 (per market) how did the market demand end: shipped in its request
                       week, shipped late, or still open at the end?

No Tk dependency: the GUI (Network -> Flow Check), the headless runner and the
tests call the same functions. The plan is never modified.

Definitions (lots; each table also has *_qty = lots x sc_tree.cpu_size)
-----------------------------------------------------------------------
Table 1
  opening_I        opening lots given to the node (ForwardPlanResult
                   .opening_inv_counts)
  receipt_sum      sum over the horizon of supply P (after the planner moved
                   lots between weeks: closure E2, identity Step 0a deferral)
  ship_sum         sum of node._actual_ship (actual shipment)
  closing_I        supply I of the last week
  conservation_diff  opening_I + receipt_sum - ship_sum - closing_I  (0 = OK)
  upstream_ship_sum  what the supplier(s) actually shipped TOWARDS this node,
                   computed independently from the supplier's actual shipment
                   and the routing (OutBound: parent, Lot_ID -> leaf_out ->
                   child; supply_point: MOM roots; InBound: children)
  in_transit_end   of which the arrival week is beyond the horizon
  unplaced_end     lots removed from P because no week was left to move them
                   to (closure_p_unplaced, identity cap_hard_unplaced)
  sealed_legacy    lots removed from P by legacy Step 0a sealing (legacy only)
  arrival_diff     upstream_ship_sum - in_transit_end - receipt_sum
                   - unplaced_end - sealed_legacy                  (0 = OK)
  recorded_arrivals  deliveries recorded by the planner into this node within
                   the horizon (ForwardPlanResult.edge_flows) -- cross-check
  closing_CO       supply CO of the last week
  status / reason  OK / NG / 対象外 (see _judge)

Table 2 (leaf_out; per leaf, product total, model total)
  demand           distinct Lot_IDs in the leaf's supply S (its requests)
  on_time          shipped in the request week (the S week of the Lot_ID)
  early            shipped before the request week (expected 0)
  late             shipped after the request week
  backlog_end      never shipped within the horizon
  check            demand - (on_time + early + late + backlog_end)  (0 = OK)
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from wom.model.plan_node import S, CO, I, P

NODE_COLUMNS = [
    "product", "node", "node_id", "node_type", "plan_mode",
    "opening_I", "receipt_sum", "ship_sum", "closing_I", "conservation_diff",
    "upstream_ship_sum", "in_transit_end", "unplaced_end", "sealed_legacy",
    "arrival_diff", "recorded_arrivals", "closing_CO", "status", "reason",
]
MARKET_COLUMNS = [
    "product", "leaf", "demand", "on_time", "early", "late", "backlog_end", "check",
]
QTY_SUFFIX = "_qty"
_NODE_QTY_COLS = ["opening_I", "receipt_sum", "ship_sum", "closing_I",
                  "upstream_ship_sum", "in_transit_end", "closing_CO"]
_MARKET_QTY_COLS = ["demand", "on_time", "early", "late", "backlog_end"]

STATUS_OK, STATUS_NG, STATUS_NA = "OK", "NG", "対象外"


def _actual(node) -> Optional[Dict[int, List[str]]]:
    return getattr(node, "_actual_ship", None)


def _ship_weeks(node, n_weeks):
    a = _actual(node) or {}
    return {w: a.get(w, []) for w in range(n_weeks) if a.get(w)}


def _is_kitting_assembly(node) -> bool:
    return bool(node.children) and all(c.node_type == "stockyard" for c in node.children)


def _leaf_index(ot_root) -> Dict[str, object]:
    idx = {}
    for nd in ot_root.walk_preorder():
        if not nd.children:
            for w_psi in nd.psi4demand:
                for lot in w_psi[S]:
                    idx[lot] = nd
    return idx


def _routed_child(parent, lot, leaf_idx):
    """The direct child of `parent` whose subtree owns `lot` (None if none)."""
    leaf = leaf_idx.get(lot)
    node = leaf
    while node is not None and node.parent is not parent:
        node = node.parent
    return node


def _upstream_shipments(sc_tree, prod, n_weeks):
    """{node_id: [(arrive_w, count), ...]} of what each node's supplier(s)
    actually shipped towards it -- independent of the planner's delivery."""
    out = defaultdict(list)
    ot_root = sc_tree.get_ot_root(prod)
    in_roots = list(sc_tree.get_in_roots(prod).values())
    leaf_idx = _leaf_index(ot_root)
    ot_ids = {n.node_id for n in ot_root.walk_preorder()}

    # supply_point <- MOM roots (same-week bridge)
    for mom in in_roots:
        for w, lots in _ship_weeks(mom, n_weeks).items():
            out[ot_root.node_id].append((w, len(lots)))

    # OutBound child <- parent
    for parent in ot_root.walk_preorder():
        if not parent.children:
            continue
        for w, lots in _ship_weeks(parent, n_weeks).items():
            if len(parent.children) == 1:
                child = parent.children[0]
                out[child.node_id].append((w + child.lt_wks, len(lots)))
                continue
            per_child = defaultdict(int)          # PlanNode is unhashable -> key by id
            child_by_id = {c.node_id: c for c in parent.children}
            for lot in lots:
                ch = _routed_child(parent, lot, leaf_idx)
                if ch is not None:
                    per_child[ch.node_id] += 1
            for cid, cnt in per_child.items():
                out[cid].append((w + child_by_id[cid].lt_wks, cnt))

    # InBound parent <- child
    for mom in in_roots:
        for child in mom.walk_preorder():
            parent = child.parent
            if parent is None or child.node_id in ot_ids:
                continue
            if child.is_decoupling and child.plan_mode == "push":
                lt = child.lt_wks                       # inline push hand-off
            else:
                lt = child.transit_lt_wks if child.transit_lt_wks > 0 else child.lt_wks
            if parent.node_type != "stockyard" and child.node_type == "stockyard":
                lt = 0                                  # yard -> assembly payout
            for w, lots in _ship_weeks(child, n_weeks).items():
                out[parent.node_id].append((w + lt, len(lots)))
    return out


def _demand_ids(ot_root) -> set:
    ids = set()
    for nd in ot_root.walk_preorder():
        if not nd.children:
            for w_psi in nd.psi4demand:
                ids.update(w_psi[S])
    return ids


def _judge(row, node, flags) -> None:
    if row["conservation_diff"] != 0:
        row["status"], row["reason"] = STATUS_NG, "保存差"
        return
    if flags.get("no_record"):
        row["status"], row["reason"] = STATUS_NA, "対象外（計画の記録なし）"
        return
    if flags.get("kitting"):
        row["status"], row["reason"] = STATUS_NA, "対象外（Kitting）"
    elif flags.get("p_copied"):
        row["status"], row["reason"] = STATUS_NA, "対象外（P はコピー。出所なし）"
    elif flags.get("non_demand"):
        row["status"], row["reason"] = STATUS_NA, "対象外（需要に無い ID）"
    elif node.plan_mode == "push_sub" or flags.get("source"):
        # no supplier to reconcile with: the arrival difference is meaningless
        row["arrival_diff"] = None
        row["status"], row["reason"] = STATUS_OK, (
            "push_sub（保存差のみ判定）" if node.plan_mode == "push_sub"
            else "供給元（上流なし。保存差のみ判定）")
    elif row["arrival_diff"] != 0:
        row["status"], row["reason"] = STATUS_NG, "到着差"
    else:
        row["status"], row["reason"] = STATUS_OK, ""


def compute_flow_check(sc_tree, results: Optional[Dict[str, object]] = None) -> dict:
    """Build Flow Check tables 1 and 2.

    results: {product: ForwardPlanResult}. When missing for a product, the
    arrival columns cannot be reconciled (status 対象外（計画の記録なし）)."""
    results = results or {}
    n = sc_tree.num_weeks()
    cpu = getattr(sc_tree, "cpu_size", 1) or 1
    node_rows: List[dict] = []
    market_rows: List[dict] = []

    for prod in sc_tree.products:
        res = results.get(prod)
        ot_root = sc_tree.get_ot_root(prod)
        demand_ids = _demand_ids(ot_root)
        upstream = _upstream_shipments(sc_tree, prod, n)
        legacy = res is not None and getattr(res, "lot_flow_mode", None) != "identity"
        p_copied = set(getattr(res, "p_copied_node_ids", []) or []) if res else set()
        opening = dict(getattr(res, "opening_inv_counts", {}) or {}) if res else {}
        unplaced = defaultdict(int)
        sealed = defaultdict(int)
        recorded = defaultdict(int)
        if res is not None:
            for nid, _wl, lots in (list(getattr(res, "closure_p_unplaced", []) or [])
                                   + list(getattr(res, "cap_hard_unplaced", []) or [])):
                unplaced[nid] += len(lots)
            if legacy:
                for nid, _wl, cnt in getattr(res, "cap_hard_events", []) or []:
                    sealed[nid] += cnt
            for _f, to_id, _sw, aw, cnt in getattr(res, "edge_flows", []) or []:
                if 0 <= aw < n:
                    recorded[to_id] += cnt

        for nd in sc_tree.iter_all_nodes(prod):
            sup = nd.psi4supply
            receipt = sum(len(sup[w][P]) for w in range(n))
            ship_map = _actual(nd)
            ship = sum(len(v) for v in ship_map.values()) if ship_map is not None else 0
            closing_i = len(sup[n - 1][I]) if n else 0
            closing_co = len(sup[n - 1][CO]) if n else 0
            op = opening.get(nd.node_id, 0)
            ups = upstream.get(nd.node_id, [])
            up_sum = sum(c for _w, c in ups)
            in_transit = sum(c for aw, c in ups if aw >= n)
            row = {
                "product": prod, "node": nd.node_name, "node_id": nd.node_id,
                "node_type": nd.node_type, "plan_mode": nd.plan_mode,
                "opening_I": op, "receipt_sum": receipt, "ship_sum": ship,
                "closing_I": closing_i,
                "conservation_diff": op + receipt - ship - closing_i,
                "upstream_ship_sum": up_sum, "in_transit_end": in_transit,
                "unplaced_end": unplaced.get(nd.node_id, 0),
                "sealed_legacy": sealed.get(nd.node_id, 0),
                "arrival_diff": (up_sum - in_transit - receipt
                                 - unplaced.get(nd.node_id, 0) - sealed.get(nd.node_id, 0)),
                "recorded_arrivals": recorded.get(nd.node_id, 0),
                "closing_CO": closing_co,
            }
            # supply built with Lot_IDs that no market demand owns (e.g. rice
            # HarvestBatch OI_ lots, given as opening inventory: they may stay
            # in I unmatched, or be received / shipped)
            non_demand = bool(demand_ids) and (
                any(lot not in demand_ids for w in range(n) for lot in sup[w][P])
                or any(lot not in demand_ids for w in range(n) for lot in sup[w][I])
                or any(lot not in demand_ids
                       for lots in (ship_map or {}).values() for lot in lots))
            flags = {
                "no_record": res is None or ship_map is None,
                "kitting": _is_kitting_assembly(nd),
                "p_copied": nd.node_id in p_copied,
                "non_demand": non_demand,
                "source": not ups and nd.node_type == "leaf_in" and not nd.children,
            }
            if flags["no_record"]:
                row["conservation_diff"] = 0 if ship_map is None else row["conservation_diff"]
            _judge(row, nd, flags)
            for c in _NODE_QTY_COLS:
                row[c + QTY_SUFFIX] = row[c] * cpu
            node_rows.append(row)

        # Table 2
        prod_tot = {k: 0 for k in ("demand", "on_time", "early", "late", "backlog_end")}
        for leaf in ot_root.walk_preorder():
            if leaf.children:
                continue
            s_week = {}
            for w in range(n):
                for lot in leaf.psi4supply[w][S]:
                    s_week.setdefault(lot, w)
            ship_map = _actual(leaf) or {}
            first_ship = {}
            for w in sorted(ship_map):
                for lot in ship_map[w]:
                    first_ship.setdefault(lot, w)
            r = {"product": prod, "leaf": leaf.node_name, "demand": len(s_week),
                 "on_time": 0, "early": 0, "late": 0, "backlog_end": 0}
            for lot, sw in s_week.items():
                w = first_ship.get(lot)
                if w is None:
                    r["backlog_end"] += 1
                elif w == sw:
                    r["on_time"] += 1
                elif w < sw:
                    r["early"] += 1
                else:
                    r["late"] += 1
            r["check"] = r["demand"] - (r["on_time"] + r["early"] + r["late"] + r["backlog_end"])
            for k in prod_tot:
                prod_tot[k] += r[k]
            market_rows.append(r)
        pt = {"product": prod, "leaf": "Σ（製品）", **prod_tot}
        pt["check"] = pt["demand"] - (pt["on_time"] + pt["early"] + pt["late"] + pt["backlog_end"])
        market_rows.append(pt)

    model = {k: sum(r[k] for r in market_rows if r["leaf"] == "Σ（製品）")
             for k in ("demand", "on_time", "early", "late", "backlog_end")}
    mt = {"product": "Σ（モデル全体）", "leaf": "", **model}
    mt["check"] = mt["demand"] - (mt["on_time"] + mt["early"] + mt["late"] + mt["backlog_end"])
    market_rows.append(mt)
    for r in market_rows:
        for c in _MARKET_QTY_COLS:
            r[c + QTY_SUFFIX] = r[c] * cpu

    summary = {
        "nodes": len(node_rows),
        "ng": sum(1 for r in node_rows if r["status"] == STATUS_NG),
        "not_applicable": sum(1 for r in node_rows if r["status"] == STATUS_NA),
        "market_check_nonzero": sum(1 for r in market_rows if r["check"] != 0),
        "cpu_size": cpu,
    }
    return {"nodes": node_rows, "market": market_rows, "summary": summary}


def write_flow_check_csv(fc: dict, out_dir: str) -> List[str]:
    """Write flow_check_nodes.csv / flow_check_market.csv (utf-8-sig for Excel)."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name, cols, rows in (
            ("flow_check_nodes.csv",
             NODE_COLUMNS + [c + QTY_SUFFIX for c in _NODE_QTY_COLS], fc["nodes"]),
            ("flow_check_market.csv",
             MARKET_COLUMNS + [c + QTY_SUFFIX for c in _MARKET_QTY_COLS], fc["market"])):
        path = os.path.join(out_dir, name)
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            wr.writeheader()
            wr.writerows(rows)
        paths.append(path)
    return paths
