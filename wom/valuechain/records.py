# -*- coding: utf-8 -*-
"""
計画の結果 → 出荷の記録（RequestLetter_StageD_Phase1 §1-3）

計画（ForwardPlanner）が各ノードに残す実出荷 `node._actual_ship[w] = [Lot_ID, ...]` を、1 件ずつ
1 行の出荷の記録にする。ID は LOVEM の実出荷の事象と同じ `ship:{product}:{node_id}:{w}:{seq}`。
計画のコードは変えず、読むだけ。

区間（物理）：
- leaf_in → 親（MOM・置場）               外部の供給者からの仕入
- InBound の MOM → 親の MOM、置場 → 組立   グループの中の移動
- MOM（root）→ supply point               **仮想の受け渡し**（物は MOM にとどまる。金額なし）
- supply point → 子（DC など）            物理の区間は「その lot を受け渡した MOM → 子」
                                           （supply point を飛ばす。依頼 §0.3）
- 親 → 子（OutBound）                     受け手は、その lot が P に入った子
- leaf_out → 消費者 `CONSUMER:<leaf>`      販売（①③）、または外部チャネルの販売の観測（②）

到着週は、受け手のノードの P にその Lot_ID が入った週（計画の記録そのもの）。P に無い（計画の
期間の後に着く）ときは「出荷週 ＋ 区間の LT」で、`arrival_in_horizon=False`。

`edge_flows()`：区間 × 週 × lot 数（World Map を実出荷で動かすとき用。今回は集計の関数だけ）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

P_IDX = 3   # plan_node bucket P

K_PURCHASE = "purchase_in"         # leaf_in -> parent (external supplier)
K_INBOUND = "inbound_move"         # inbound mom -> parent mom, yard -> assembly
K_HANDOFF = "handoff_to_sp"        # MOM root -> supply point (virtual)
K_OUTBOUND = "outbound_move"       # supply point / DC -> child
K_CONSUMER = "consumer_sale"       # leaf_out -> consumer


@dataclass
class NodeInfo:
    product: str
    name: str
    node_id: str
    node_type: str
    parent: Optional[str]
    children: List[str]
    lt: int
    transit_lt: int
    bom_qty: int = 1
    side: str = ""        # "in" / "out"
    rank: int = 0         # processing order inside a week (upstream first)

    @property
    def is_terminal_mom(self) -> bool:
        return self.node_type == "mom" and self.parent is None


@dataclass
class Shipment:
    ship_id: str
    product: str
    lot_id: str
    node: str             # engine node that shipped (supply point for its ships)
    node_id: str
    week: int
    seq: int
    kind: str
    phys_from: str        # physical shipper (the origin MOM for supply-point ships)
    to: str               # receiver node, or CONSUMER:<leaf>
    edge: str             # physical edge "A->B" ("" for the virtual hand-off)
    arrival_week: Optional[int]
    arrival_in_horizon: bool
    units: float          # lots x cpu_size x bom_qty
    item: str             # finished / material:<leaf_in> / wip:<mom>


@dataclass
class PlanRecords:
    plan_id: str
    week_labels: List[str]
    cpu_size: float
    nodes: Dict[Tuple[str, str], NodeInfo]
    shipments: List[Shipment]
    origin_mom: Dict[Tuple[str, str], str] = field(default_factory=dict)   # (product, lot) -> MOM
    issues: List[dict] = field(default_factory=list)

    def physical_edges(self) -> Dict[str, set]:
        out: Dict[str, set] = {}
        for s in self.shipments:
            if s.edge:
                out.setdefault(s.product, set()).add(s.edge)
        return out

    def terminal_moms(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for (p, n), ni in self.nodes.items():
            if ni.is_terminal_mom:
                out.setdefault(p, []).append(n)
        return out


def _node_infos(sc_tree) -> Dict[Tuple[str, str], NodeInfo]:
    out = {}
    for prod in sc_tree.products:
        rank = 0
        for mom in sc_tree.get_in_roots(prod).values():
            for nd in mom.walk_postorder():
                out[(prod, nd.node_name)] = _info(prod, nd, "in", rank)
                rank += 1
        for nd in sc_tree.get_ot_root(prod).walk_preorder():
            out[(prod, nd.node_name)] = _info(prod, nd, "out", rank)
            rank += 1
    return out


def _info(prod, nd, side, rank):
    tlt = getattr(nd, "transit_lt_wks", 0) or 0
    return NodeInfo(product=prod, name=nd.node_name, node_id=nd.node_id, node_type=nd.node_type,
                    parent=nd.parent.node_name if nd.parent is not None else None,
                    children=[c.node_name for c in nd.children],
                    lt=int(nd.lt_wks or 0), transit_lt=int(tlt if tlt > 0 else (nd.lt_wks or 0)),
                    bom_qty=int(getattr(nd, "bom_qty", 1) or 1), side=side, rank=rank)


def build_records(sc_tree, plan_id: str) -> PlanRecords:
    """Read the planned tree (after ForwardPlanner.run) into shipment records."""
    labels = list(sc_tree.week_labels)
    n = len(labels)
    cpu = float(getattr(sc_tree, "cpu_size", 1) or 1)
    infos = _node_infos(sc_tree)
    ships: List[Shipment] = []
    origin: Dict[Tuple[str, str], str] = {}
    issues: List[dict] = []

    for prod in sc_tree.products:
        nodes = {nd.node_name: nd for nd in sc_tree.iter_all_nodes(prod)}
        # where each lot entered P (receipt = arrival), per node
        p_week: Dict[str, Dict[str, int]] = {}
        for name, nd in nodes.items():
            idx: Dict[str, int] = {}
            for w in range(n):
                for lot in nd.psi4supply[w][P_IDX]:
                    idx.setdefault(lot, w)
            p_week[name] = idx
        sp = sc_tree.get_ot_root(prod)
        in_roots = list(sc_tree.get_in_roots(prod).values())

        # process the inbound first so origin MOM of each lot is known for the SP ships
        order = []
        for mom in in_roots:
            order += list(mom.walk_postorder())
        order += list(sp.walk_preorder())
        for nd in order:
            actual = getattr(nd, "_actual_ship", None)
            if actual is None:
                issues.append({"issue": "no_actual_ship_record", "product": prod, "node": nd.node_name})
                continue
            info = infos[(prod, nd.node_name)]
            for w in sorted(actual):
                for seq, lot in enumerate(actual[w]):
                    sid = f"ship:{prod}:{nd.node_id}:{w}:{seq}"
                    ships.append(_one(sid, prod, lot, nd, info, w, seq, nodes, p_week, sp,
                                      in_roots, origin, cpu, n, issues))
    return PlanRecords(plan_id=plan_id, week_labels=labels, cpu_size=cpu, nodes=infos,
                       shipments=ships, origin_mom=origin, issues=issues)


def _one(sid, prod, lot, nd, info, w, seq, nodes, p_week, sp, in_roots, origin, cpu, n, issues):
    t = nd.node_type
    units = cpu
    if t == "leaf_out":
        return Shipment(sid, prod, lot, nd.node_name, nd.node_id, w, seq, K_CONSUMER, nd.node_name,
                        f"CONSUMER:{nd.node_name}", "", None, False, units, "finished")
    if nd.side == "inbound" or info.side == "in":
        parent = nd.parent
        if parent is None:                    # MOM root -> supply point (virtual hand-off)
            origin[(prod, lot)] = nd.node_name
            aw = p_week[sp.node_name].get(lot)
            if aw is None:
                issues.append({"issue": "handoff_not_in_sp_P", "ship_id": sid, "lot": lot})
            return Shipment(sid, prod, lot, nd.node_name, nd.node_id, w, seq, K_HANDOFF, nd.node_name,
                            sp.node_name, "", aw if aw is not None else w, aw is not None, units, "finished")
        kind = K_PURCHASE if t == "leaf_in" else K_INBOUND
        if t == "leaf_in":
            units = cpu * info.bom_qty
            item = f"material:{nd.node_name}"
        elif t == "stockyard":
            child_leaf = nd.children[0].node_name if nd.children else nd.node_name
            item = f"material:{child_leaf}"
        else:
            item = f"wip:{nd.node_name}"
        aw = p_week[parent.node_name].get(lot)
        in_h = aw is not None
        if aw is None:
            aw = w + info.transit_lt
        return Shipment(sid, prod, lot, nd.node_name, nd.node_id, w, seq, kind, nd.node_name,
                        parent.node_name, f"{nd.node_name}->{parent.node_name}", aw, in_h, units, item)
    # outbound: supply point or DC -> the child whose P the lot entered
    child = None
    for c in nd.children:
        if lot in p_week[c.node_name]:
            child = c
            break
    if child is None:
        # arrival after the horizon: route by the lot's demand leaf
        child = _child_by_demand(nd, lot, nodes)
        if child is None:
            issues.append({"issue": "receiver_not_found", "ship_id": sid, "lot": lot})
            return Shipment(sid, prod, lot, nd.node_name, nd.node_id, w, seq, K_OUTBOUND, nd.node_name,
                            "", "", None, False, units, "finished")
        aw, in_h = w + child.lt_wks, False
    else:
        aw, in_h = p_week[child.node_name][lot], True
    phys_from = nd.node_name
    if nd is sp:
        phys_from = origin.get((prod, lot))
        if phys_from is None:
            issues.append({"issue": "origin_mom_unknown", "ship_id": sid, "lot": lot})
            phys_from = nd.node_name
    return Shipment(sid, prod, lot, nd.node_name, nd.node_id, w, seq, K_OUTBOUND, phys_from,
                    child.node_name, f"{phys_from}->{child.node_name}", aw, in_h, units, "finished")


def _child_by_demand(parent, lot, nodes):
    for c in parent.children:
        stack = [c]
        while stack:
            x = stack.pop()
            if not x.children:
                if any(lot in x.psi4demand[w][0] for w in range(len(x.psi4demand))):
                    return c
            stack.extend(x.children)
    return None


def edge_flows(shipments: List[Shipment], week_labels: List[str]):
    """区間 × 週 × lot 数（物理の区間だけ）。World Map を実出荷で動かすとき用。"""
    import pandas as pd
    rows = {}
    for s in shipments:
        if not s.edge:
            continue
        k = (s.product, s.edge, s.ship_week if hasattr(s, "ship_week") else s.week, s.arrival_week)
        rows[k] = rows.get(k, 0) + 1
    out = [{"product": p, "edge": e, "from_node": e.split("->")[0], "to_node": e.split("->")[1],
            "ship_week_index": w, "ship_week": week_labels[w],
            "arrival_week_index": a, "lots": c} for (p, e, w, a), c in rows.items()]
    return pd.DataFrame(out, columns=["product", "edge", "from_node", "to_node", "ship_week_index",
                                      "ship_week", "arrival_week_index", "lots"])
