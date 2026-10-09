# -*- coding: utf-8 -*-
"""
World Map に描くもの（RequestLetter_WorldMap_ActualFlows §1）

- `MapLayout.load(model_dir)`：拠点（node_master.csv の緯度・経度）と、計画の前に描く物理の区間
  （sc_tree_master.csv の親子。supply point を飛ばして「MOM → supply point の子」を結ぶ）。
  supply point は仮想のノード（グローバル需給センター）なので、区間の端にしない。
  MOM → supply point の仮想の受け渡しは `handoff`（既定では描かない）。
- `FlowData.from_records(records, sc_tree)`：計画の実出荷（段階 D の出荷の記録
  `wom/valuechain/records.py`）から、区間 × 週の lot 数（出荷・輸送中）と、拠点 × 週の
  P・S・I・CO の lot 数、市場（leaf_out）の販売の lot 数を作る。計画の S は使わない。

黙った既定値は作らない：座標の無い拠点・描けない区間は一覧（`missing_coords`・`undrawable_edges`）に
出し、描かない。例外は Stock Yard（node_type stockyard、工場の構内の置場）だけで、座標が無ければ親の
組立工場の位置に置き、`placed_at_parent` の一覧に出す（node_master に座標があればそちらを使う）。出荷の記録が作れない（記録に食い違いがある）ときは流れを作らず、理由を返す。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from wom.worldmap_ne.data import project

S_IDX, CO_IDX, I_IDX, P_IDX = 0, 1, 2, 3

# node_master.csv node_type -> colour (the same as the World Map tab's _MAP_NODE_STYLE)
NODE_STYLE = {
    "procurement":  ("#FF9800", "#E65100"),
    "mother_plant": ("#9C27B0", "#4A148C"),
    "sku_supplier": ("#4CAF50", "#1B5E20"),
    "region_dc":    ("#2196F3", "#0D47A1"),
    "marketing":    ("#F44336", "#B71C1C"),
}
# a node_master type outside the table (e.g. iphone's "retail", "supply_point") takes the
# colour of the same role in the plan tree (sc_tree_master node_type). Listed in the info.
TREE_TYPE_TO_STYLE = {"leaf_in": "sku_supplier", "mom": "mother_plant", "dad": "region_dc",
                      "leaf_out": "marketing", "stockyard": "sku_supplier"}
OTHER_COLOUR = ("#607D8B", "#455A64")


def _s(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


@dataclass
class MapNode:
    node_id: str
    name: str                 # node_master node_name (the label)
    master_type: str          # node_master node_type
    tree_types: Set[str]      # sc_tree_master node_type(s) (may be several products)
    products: Set[str]
    lon: float
    lat: float
    x: float
    y: float
    colour: str
    colour_source: str        # "node_master" / "sc_tree" / "none"
    info: dict                # the node_master row

    @property
    def is_supply_point(self) -> bool:
        return "supply_point" in self.tree_types or self.master_type == "supply_point"

    @property
    def is_market(self) -> bool:
        return "leaf_out" in self.tree_types


@dataclass
class MapEdge:
    product: str
    edge: str                 # "A->B" (the shipment record's physical edge)
    a: str
    b: str
    side: str                 # "in" / "out"
    kind: str = "physical"    # "physical" / "handoff"


@dataclass
class MapLayout:
    model_dir: str
    nodes: Dict[str, MapNode]                    # drawable nodes (with coordinates)
    edges: List[MapEdge]                         # physical edges from sc_tree (both ends drawable)
    handoff: List[MapEdge]                       # MOM -> supply point (virtual; drawable ends)
    products: List[str]
    missing_coords: List[dict]                   # nodes of the plan tree with no lat/lon
    undrawable_edges: List[dict]                 # physical edges with an end without lat/lon
    tree_nodes: Dict[str, Set[str]]              # product -> node names in its tree
    colour_notes: List[str] = field(default_factory=list)
    placed_at_parent: List[dict] = field(default_factory=list)   # Stock Yards drawn at their plant

    @classmethod
    def load(cls, model_dir: str) -> "MapLayout":
        nm_path = os.path.join(model_dir, "node_master.csv")
        st_path = os.path.join(model_dir, "sc_tree_master.csv")
        nm = pd.read_csv(nm_path) if os.path.exists(nm_path) else pd.DataFrame(
            columns=["node_id", "node_name", "node_type", "lat", "lon"])
        st = pd.read_csv(st_path) if os.path.exists(st_path) else pd.DataFrame(
            columns=["node_name", "parent_node", "product_name", "node_type", "side"])

        tree_types: Dict[str, Set[str]] = {}
        tree_nodes: Dict[str, Set[str]] = {}
        node_products: Dict[str, Set[str]] = {}
        parent: Dict[Tuple[str, str], str] = {}
        side_of: Dict[Tuple[str, str], str] = {}
        mom_roots: Dict[str, List[str]] = {}
        sp_root: Dict[str, str] = {}
        for r in st.to_dict("records"):
            n, p, prod, t = _s(r.get("node_name")), _s(r.get("parent_node")), \
                _s(r.get("product_name")), _s(r.get("node_type"))
            if not n or not prod:
                continue
            tree_types.setdefault(n, set()).add(t)
            tree_nodes.setdefault(prod, set()).add(n)
            node_products.setdefault(n, set()).add(prod)
            side_of[(prod, n)] = "in" if _s(r.get("side")) == "inbound" else "out"
            if p:
                parent[(prod, n)] = p
            elif t == "mom":
                mom_roots.setdefault(prod, []).append(n)
            elif t == "supply_point":
                sp_root[prod] = n

        nodes: Dict[str, MapNode] = {}
        missing: List[dict] = []
        notes: List[str] = []
        seen_master: Set[str] = set()
        for r in nm.to_dict("records"):
            nid = _s(r.get("node_id"))
            if not nid:
                continue
            seen_master.add(nid)
            try:
                lat, lon = float(r.get("lat")), float(r.get("lon"))
                ok = np.isfinite(lat) and np.isfinite(lon)
            except (TypeError, ValueError):
                ok = False
            mtype = _s(r.get("node_type"))
            ttypes = tree_types.get(nid, set())
            if not ok:
                missing.append({"node_id": nid, "name": _s(r.get("node_name")) or nid,
                                "in_plan_tree": nid in tree_types,
                                "reason": "node_master.csv に緯度・経度が無い"})
                continue
            if mtype in NODE_STYLE:
                colour, src = NODE_STYLE[mtype][0], "node_master"
            else:
                st_style = next((TREE_TYPE_TO_STYLE[t] for t in sorted(ttypes) if t in TREE_TYPE_TO_STYLE),
                                None)
                if st_style:
                    colour, src = NODE_STYLE[st_style][0], "sc_tree"
                    notes.append(f"{nid}: node_master の node_type「{mtype}」は色の表に無いので、"
                                 f"計画の木の役割（{'/'.join(sorted(ttypes))}）の色")
                else:
                    colour, src = OTHER_COLOUR[0], "none"
            x, y = project([lon], [lat])
            nodes[nid] = MapNode(nid, _s(r.get("node_name")) or nid, mtype, ttypes,
                                 node_products.get(nid, set()), lon, lat, float(x[0]), float(y[0]),
                                 colour, src, {k: _s(v) for k, v in r.items()})
        for n in sorted(tree_types):
            if n not in seen_master:
                missing.append({"node_id": n, "name": n, "in_plan_tree": True,
                                "reason": "node_master.csv に行が無い"})

        # Stock Yard rule (owner's decision, 2026-10): a Yard is a staging area inside its
        # assembly plant's site. A Yard with no coordinates is drawn at its parent's position
        # and listed as such ("placed_at_parent"); coordinates written in node_master win.
        # Only node_type "stockyard" (never guessed from a name); a Yard whose parents differ
        # between products, or whose parent has no coordinates, stays in the missing list.
        placed: List[dict] = []
        still: List[dict] = []
        for m in missing:
            nid = m["node_id"]
            if "stockyard" not in tree_types.get(nid, set()):
                still.append(m)
                continue
            parents = sorted({p for (prod, n), p in parent.items() if n == nid})
            if len(parents) == 1 and parents[0] in nodes:
                pn = nodes[parents[0]]
                info = {"node_id": nid, "node_name": nid, "placed_at_parent": parents[0]}
                nodes[nid] = MapNode(nid, nid, "", tree_types[nid], node_products.get(nid, set()),
                                     pn.lon, pn.lat, pn.x, pn.y, NODE_STYLE["sku_supplier"][0],
                                     "sc_tree", info)
                placed.append({"node_id": nid, "parent": parents[0],
                               "reason": "Stock Yard（工場の構内の置場）。座標が無いので親の組立工場の位置に合わせた"})
            else:
                why = ("親が製品ごとに違う" if len(parents) > 1 else "親の拠点にも座標が無い")
                still.append(dict(m, reason=m["reason"] + f"（Stock Yard だが{why}ので、親の位置に合わせられない）"))
        missing = still

        edges: List[MapEdge] = []
        handoff: List[MapEdge] = []
        undrawable: List[dict] = []

        def add(prod, a, b, side, kind="physical"):
            e = MapEdge(prod, f"{a}->{b}", a, b, side, kind)
            if a in nodes and b in nodes:
                (edges if kind == "physical" else handoff).append(e)
            elif kind == "physical":
                undrawable.append({"product": prod, "edge": e.edge,
                                   "missing": ", ".join(x for x in (a, b) if x not in nodes)})

        for (prod, n), p in sorted(parent.items()):
            side = side_of.get((prod, n), "out")
            if side == "in":                       # InBound: child ships to its parent
                add(prod, n, p, "in")
            elif p == sp_root.get(prod):           # first DAD under the supply point: from each MOM
                for m in mom_roots.get(prod, []):
                    add(prod, m, n, "out")
            else:
                add(prod, p, n, "out")
        for prod, moms in mom_roots.items():
            sp = sp_root.get(prod)
            for m in moms:
                if sp:
                    add(prod, m, sp, "in", kind="handoff")
        return cls(model_dir, nodes, edges, handoff, sorted(tree_nodes), missing, undrawable,
                   tree_nodes, notes, placed)

    def extent(self, node_ids=None, pad_frac: float = 0.15, min_deg: float = 2.0):
        ids = [n for n in (node_ids if node_ids is not None else self.nodes) if n in self.nodes]
        if not ids:
            return -180.0, -60.0, 180.0, 80.0
        xs = np.array([self.nodes[n].x for n in ids])
        ys = np.array([self.nodes[n].y for n in ids])
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        w, h = max(x1 - x0, min_deg), max(y1 - y0, min_deg)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = w * (1 + 2 * pad_frac), h * (1 + 2 * pad_frac)
        return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


@dataclass
class FlowData:
    """Weekly flows of ONE plan, from its shipment records (never from the planned S)."""
    plan_id: str
    week_labels: List[str]
    edge_keys: List[Tuple[str, str]]             # (product, edge)
    ship: np.ndarray                             # (n_weeks, n_edges) lots shipped in week w
    transit: np.ndarray                          # (n_weeks, n_edges) lots on the edge at the end of w
    lt_master: Dict[Tuple[str, str], int]
    lt_observed: Dict[Tuple[str, str], float]    # median(arrival - ship) of in-horizon arrivals
    node_keys: List[Tuple[str, str]]             # (product, node)
    psi: np.ndarray                              # (n_weeks, n_nodes, 4) lots: S, CO, I, P (supply)
    sales: np.ndarray                            # (n_weeks, n_nodes) consumer sales (leaf_out)
    handoff_keys: List[Tuple[str, str]] = field(default_factory=list)
    handoff: np.ndarray = None                   # (n_weeks, n_handoff)
    n_shipments: int = 0
    lot_flow_mode: str = ""

    @classmethod
    def from_records(cls, records, sc_tree=None) -> "FlowData":
        labels = list(records.week_labels)
        n = len(labels)
        ekey: Dict[Tuple[str, str], int] = {}
        hkey: Dict[Tuple[str, str], int] = {}
        nkey: Dict[Tuple[str, str], int] = {}
        ship_rows, tr_rows, h_rows, sale_rows = [], [], [], []
        lt_obs: Dict[Tuple[str, str], List[int]] = {}
        for s in records.shipments:
            if s.edge:
                k = ekey.setdefault((s.product, s.edge), len(ekey))
                ship_rows.append((s.week, k))
                a = s.arrival_week if s.arrival_week is not None else n
                tr_rows.append((s.week, min(a, n), k))
                if s.arrival_in_horizon and s.arrival_week is not None:
                    lt_obs.setdefault((s.product, s.edge), []).append(s.arrival_week - s.week)
            elif s.kind == "handoff_to_sp":
                k = hkey.setdefault((s.product, f"{s.node}->{s.to}"), len(hkey))
                h_rows.append((s.week, k))
            elif s.kind == "consumer_sale":
                k = nkey.setdefault((s.product, s.node), len(nkey))
                sale_rows.append((s.week, k))
        for (p, name) in records.nodes:
            nkey.setdefault((p, name), len(nkey))

        ship = np.zeros((n, len(ekey)), dtype=np.int32)
        delta = np.zeros((n + 1, len(ekey)), dtype=np.int32)
        if ship_rows:
            w, k = np.array(ship_rows).T
            np.add.at(ship, (w, k), 1)
            w0, w1, k = np.array(tr_rows).T
            m = w1 > w0                            # LT 0: never in transit
            np.add.at(delta, (w0[m], k[m]), 1)
            np.add.at(delta, (w1[m], k[m]), -1)
        transit = np.cumsum(delta, axis=0)[:n].astype(np.int32)
        handoff = np.zeros((n, len(hkey)), dtype=np.int32)
        if h_rows:
            w, k = np.array(h_rows).T
            np.add.at(handoff, (w, k), 1)
        sales = np.zeros((n, len(nkey)), dtype=np.int32)
        if sale_rows:
            w, k = np.array(sale_rows).T
            np.add.at(sales, (w, k), 1)

        lt_master = {}
        for (p, e) in ekey:
            a, b = e.split("->")
            ib, ia = records.nodes.get((p, b)), records.nodes.get((p, a))
            if ib is not None and ib.side == "out":
                lt_master[(p, e)] = ib.lt
            elif ia is not None:
                lt_master[(p, e)] = ia.transit_lt

        psi = np.zeros((n, len(nkey), 4), dtype=np.int32)
        if sc_tree is not None:
            for prod in sc_tree.products:
                for nd in sc_tree.iter_all_nodes(prod):
                    k = nkey.get((prod, nd.node_name))
                    if k is None:
                        continue
                    sup = nd.psi4supply
                    for w in range(min(n, len(sup))):
                        b = sup[w]
                        psi[w, k] = (len(b[S_IDX]), len(b[CO_IDX]), len(b[I_IDX]), len(b[P_IDX]))
        return cls(records.plan_id, labels, list(ekey), ship, transit, lt_master,
                   {k: float(np.median(v)) for k, v in lt_obs.items()}, list(nkey), psi, sales,
                   list(hkey), handoff, len(records.shipments),
                   str(getattr(sc_tree, "lot_flow_mode", "") or "") if sc_tree is not None else "")

    def edge_week_table(self) -> pd.DataFrame:
        """(product, edge, ship_week_index, lots) — the map's numbers, for the check against
        vc_edge_flows.csv (acceptance 1)."""
        w, k = np.nonzero(self.ship)
        return pd.DataFrame({"product": [self.edge_keys[i][0] for i in k],
                             "edge": [self.edge_keys[i][1] for i in k],
                             "ship_week_index": w.astype(int), "lots": self.ship[w, k].astype(int)})


def records_problem(records) -> Optional[str]:
    """None if the records can drive the map; otherwise the reason (shown on the band)."""
    if records is None:
        return "出荷の記録がありません"
    if records.issues:
        kinds = sorted({i.get("issue", "?") for i in records.issues})
        return (f"出荷の記録に食い違いが {len(records.issues):,} 件あるため、流れを出しません"
                f"（{', '.join(kinds)}）。計画の S で代わりに描くことはしません")
    if not records.shipments:
        return "出荷の記録が 0 件です（この計画には実出荷がありません）"
    return None


def report_start_index(model_dir: str, week_labels: List[str]) -> Tuple[int, str]:
    """The first week of the reporting period (vc_config.csv report_start, else the first
    nonzero demand week). Returns (index, source). The reading lives in
    wom/engine/report_start.py (one place for World Map, Rice and Flow Check)."""
    from wom.engine.report_start import report_start_index as _rsi
    return _rsi(model_dir, week_labels)
