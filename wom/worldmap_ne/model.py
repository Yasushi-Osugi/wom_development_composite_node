# -*- coding: utf-8 -*-
"""
サンプルモデルの、地図に描くもの：拠点（node_master.csv の緯度・経度）、拠点間の線
（sc_tree_master.csv の親子。InBound の MOM → OutBound の supply_point のつなぎも、今の World Map
と同じく合成する）、週ごとの流れ。

週ごとの流れ（試作の再生用）：
    demand_forecast.csv の (sku_id, region, week) の数量を、その製品の leaf_out ノード
    （sc_tree_master の region 列で対応）に置き、親へたどって、通る線に足す。InBound の線
    （leaf_in → MOM、MOM → supply_point）には、その製品のその週の需要の合計を置く。
    リードタイムのずれ・能力の制約は入れない（計画の結果ではなく、需要の流れ）。
    描く速さを測るための試作なので、Planning Engine は動かさない。計画の結果（lot の流れ）に
    差し替えるのは、案 A を採る場合の次の段階である。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from wom.worldmap_ne.data import REPO, project

# Same colours as the World Map tab (wom/gui/app.py _MAP_NODE_STYLE); node_master's
# node_type (procurement / mother_plant / sku_supplier / region_dc / marketing)
NODE_COLOURS = {
    "procurement":  "#FF9800",
    "mother_plant": "#9C27B0",
    "sku_supplier": "#4CAF50",
    "region_dc":    "#2196F3",
    "marketing":    "#F44336",
}
DEFAULT_COLOUR = "#607D8B"


@dataclass
class MapModel:
    name: str
    node_ids: List[str]
    lon: np.ndarray
    lat: np.ndarray
    x: np.ndarray                      # projected
    y: np.ndarray
    colours: List[str]
    labels: List[str]
    edges: List[Tuple[int, int, str]]  # (child index, parent index, product)
    weeks: List[str] = field(default_factory=list)
    edge_flow: np.ndarray = None       # (n_weeks, n_edges)
    node_flow: np.ndarray = None       # (n_weeks, n_nodes)
    edge_outbound: np.ndarray = None   # (n_edges,) True = OutBound edge (demand walk)

    def extent(self, pad_frac: float = 0.15, min_deg: float = 2.0):
        """(x0, y0, x1, y1) projected, around the nodes."""
        x0, x1 = float(self.x.min()), float(self.x.max())
        y0, y1 = float(self.y.min()), float(self.y.max())
        w, h = max(x1 - x0, min_deg), max(y1 - y0, min_deg)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = w * (1 + 2 * pad_frac), h * (1 + 2 * pad_frac)
        return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def load_model(model: str) -> MapModel:
    d = model if os.path.isdir(model) else os.path.join(REPO, "data", "sample", model)
    nm = pd.read_csv(os.path.join(d, "node_master.csv"))
    nm = nm.dropna(subset=["lat", "lon"])
    ids = [str(v) for v in nm["node_id"]]
    idx = {n: i for i, n in enumerate(ids)}
    lon = nm["lon"].astype(float).to_numpy()
    lat = nm["lat"].astype(float).to_numpy()
    x, y = project(lon, lat)
    colours = [NODE_COLOURS.get(str(t), DEFAULT_COLOUR) for t in nm["node_type"]]
    labels = [str(v) for v in nm.get("node_name", nm["node_id"])]

    st = pd.read_csv(os.path.join(d, "sc_tree_master.csv"))
    edges: List[Tuple[int, int, str]] = []
    parent_of: Dict[Tuple[str, str], str] = {}
    leaf_by_region: Dict[Tuple[str, str], str] = {}
    mom_roots: Dict[str, List[str]] = {}
    sp_root: Dict[str, str] = {}
    for _, r in st.iterrows():
        node = str(r.get("node_name", "")).strip()
        par = str(r.get("parent_node", "") or "").strip()
        prod = str(r.get("product_name", "")).strip()
        typ = str(r.get("node_type", "")).strip()
        if not node or not prod:
            continue
        if par and par.lower() != "nan":
            parent_of[(prod, node)] = par
            if node in idx and par in idx:
                edges.append((idx[node], idx[par], prod))
        elif typ == "mom":
            mom_roots.setdefault(prod, []).append(node)
        elif typ == "supply_point":
            sp_root[prod] = node
        if typ == "leaf_out":
            reg = str(r.get("region", "") or "").strip()
            if reg and reg.lower() != "nan":
                leaf_by_region[(prod, reg)] = node
    for prod, moms in mom_roots.items():         # the InBound <-> OutBound bridge
        sp = sp_root.get(prod)
        for m in moms:
            if sp and sp in idx and m in idx:
                parent_of.setdefault((prod, sp), m)
                edges.append((idx[sp], idx[m], prod))

    mm = MapModel(os.path.basename(os.path.normpath(d)), ids, lon, lat, x, y, colours, labels, edges)
    _weekly_flows(mm, d, parent_of, leaf_by_region, sp_root)
    return mm


def _weekly_flows(mm: MapModel, d: str, parent_of, leaf_by_region, sp_root) -> None:
    dem = pd.read_csv(os.path.join(d, "demand_forecast.csv"))
    dem = dem[dem["quantity"] > 0]
    weeks = sorted(dem["week"].astype(str).unique().tolist())
    widx = {w: i for i, w in enumerate(weeks)}
    eidx = {(c, p, prod): k for k, (c, p, prod) in enumerate(mm.edges)}
    nidx = {n: i for i, n in enumerate(mm.node_ids)}
    ef = np.zeros((len(weeks), len(mm.edges)))
    nf = np.zeros((len(weeks), len(mm.node_ids)))
    total = {}
    g = dem.groupby(["sku_id", "region", "week"])["quantity"].sum()
    for (sku, reg, wk), q in g.items():
        sku, reg, wk = str(sku), str(reg), str(wk)
        w = widx[wk]
        total[(sku, w)] = total.get((sku, w), 0.0) + q
        node = leaf_by_region.get((sku, reg)) or (reg if (sku, reg) in parent_of else None)
        seen = set()
        while node and node not in seen:          # walk up the OutBound tree
            seen.add(node)
            if node in nidx:
                nf[w, nidx[node]] += q
            par = parent_of.get((sku, node))
            if par is None or node == sp_root.get(sku):
                break
            k = eidx.get((nidx.get(node), nidx.get(par), sku))
            if k is not None:
                ef[w, k] += q
            node = par
    # InBound edges (and the bridge): the product's total demand of the week
    touched = ef.sum(axis=0) > 0
    for k, (c, p, prod) in enumerate(mm.edges):
        if touched[k]:
            continue
        for w in range(len(weeks)):
            ef[w, k] = total.get((prod, w), 0.0)
            nf[w, c] = max(nf[w, c], ef[w, k])
            nf[w, p] = max(nf[w, p], ef[w, k])
    mm.weeks, mm.edge_flow, mm.node_flow, mm.edge_outbound = weeks, ef, nf, touched
