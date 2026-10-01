# -*- coding: utf-8 -*-
"""
マスターの読み込み（RequestLetter_StageD_Phase1 §1-2）

新しいマスター（題材のモデルのフォルダ）：
    vc_config.csv            key,value：hq_currency, common_currency, report_start, holding_rate_weekly
    vc_entity.csv            entity_id, entity_name, kind, functional_currency, consolidated
    vc_node_assignment.csv   node_id, product_id, entity_id, channel_type, local_currency
    vc_price_rule.csv        edge_id, product_id, price_type, week, price, currency

価格の出どころ（1 つの価格は 1 か所だけ）：
    最終市場の価格                   ppc_market_price.csv
    終端の MOM から次の物理の区間     ppc_transfer_price_rule.csv（法人間／法人内は区間の両端の法人で決まる）
    それ以外の法人間の価格・卸価格    vc_price_rule.csv
    外部の供給者からの仕入           ppc_supplier_cost.csv
    運賃・関税・ノード費用            ppc_edge_cost_rule.csv・ppc_tariff_rule.csv・ppc_node_cost_rule.csv

同じ区間の同じ種類の価格が 2 か所に書かれていたら、`MasterError` で止める（運賃をノードに書くことも
止める。運賃は物理の区間だけに書く：Part 0-2）。

時系列の価格（week の列＝その週から有効）は、その週以前で最も新しい行を使う。最初の行より前の週
（助走週）は、最初の行の価格を使い、`price_log` に記録する（為替の判断 d と同じ扱い）。
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

NAN = float("nan")

ENTITY_KINDS = ("group", "external_supplier", "external_channel", "external_customer")
CHANNEL_TYPES = {"own": "①", "external": "②", "online": "③"}
PRICE_TYPES = ("intercompany", "management", "wholesale")


class MasterError(ValueError):
    """A master is inconsistent (e.g. the same price written in two places)."""


@dataclass
class Entity:
    entity_id: str
    name: str
    kind: str
    functional_currency: str
    consolidated: bool

    @property
    def is_group(self) -> bool:
        return self.kind == "group"


@dataclass
class Assignment:
    node_id: str
    product_id: str
    entity_id: str
    channel_type: str = ""      # own / external / online (leaf_out only)
    local_currency: str = ""    # market leaves only


@dataclass
class VCMasters:
    model_dir: str
    hq_currency: str
    common_currency: str
    report_start: Optional[str]
    holding_rate_weekly: Optional[float]
    entities: Dict[str, Entity]
    assignment: Dict[Tuple[str, str], Assignment]
    price_rules: Dict[Tuple[str, str, str], List[Tuple[str, float, str]]]  # (edge, prod, type) -> [(week, price, ccy)]
    market_price: Dict[Tuple[str, str], List[Tuple[str, float, str]]]
    supplier_cost: Dict[Tuple[str, str], List[Tuple[str, float, str]]]
    node_cost: Dict[Tuple[str, str], List[dict]]
    edge_cost: Dict[Tuple[str, str], List[dict]]
    tariff: Dict[Tuple[str, str], dict]
    transfer_price: Dict[Tuple[str, str], dict]
    price_log: Dict[tuple, dict] = field(default_factory=dict)

    # ── lookups ──────────────────────────────────────────────────────
    def entity_of(self, node: str, product: str) -> Entity:
        a = self.assignment.get((node, product))
        if a is None:
            raise MasterError(f"vc_node_assignment.csv: no row for node {node!r} / product {product!r}")
        return self.entities[a.entity_id]

    def _series(self, table, key, week, what) -> Tuple[float, str, str]:
        """(price, currency, method) at `week`; NaN/'' when there is no row."""
        rows = table.get(key)
        if not rows:
            return NAN, "", "missing"
        best = None
        for w, p, c in rows:
            if w <= week:
                best = (p, c)
        if best is not None:
            return best[0], best[1], "effective"
        w0, p0, c0 = rows[0]
        k = (what, key, week)
        rec = self.price_log.get(k)
        if rec is None:
            rec = {"what": what, "key": "|".join(key), "requested_week": week,
                   "used_week": w0, "count": 0,
                   "method": "first_row_before_effective_week"}
            self.price_log[k] = rec
        rec["count"] += 1
        return p0, c0, "first_row_before_effective_week"

    def market(self, leaf: str, product: str, week: str):
        return self._series(self.market_price, (leaf, product), week, "ppc_market_price")

    def supplier(self, node: str, product: str, week: str):
        return self._series(self.supplier_cost, (node, product), week, "ppc_supplier_cost")

    def price_rule(self, edge: str, product: str, price_type: str, week: str):
        return self._series(self.price_rules, (edge, product, price_type), week, f"vc_price_rule:{price_type}")


# ──────────────────────────────────────────────────────────────────────

def _read(model_dir, name, required=True, fallback_dir=None):
    p = os.path.join(model_dir, name)
    if os.path.exists(p):
        return pd.read_csv(p, dtype=str, keep_default_na=False)
    if fallback_dir and os.path.exists(os.path.join(fallback_dir, name)):
        return pd.read_csv(os.path.join(fallback_dir, name), dtype=str, keep_default_na=False)
    if required:
        raise MasterError(f"{name} not found in {model_dir}")
    return None


def _num(v, what):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise MasterError(f"{what}: not a number: {v!r}")
    if math.isnan(x):
        raise MasterError(f"{what}: not a number: {v!r}")
    return x


def _series_table(df, key_cols, price_col, what):
    out: Dict[tuple, List[Tuple[str, float, str]]] = {}
    seen = set()
    for r in df.to_dict("records"):
        key = tuple(str(r[c]) for c in key_cols)
        wk = str(r["week"])
        if (key, wk) in seen:
            raise MasterError(f"{what}: the same price is written twice: {key} week {wk}")
        seen.add((key, wk))
        out.setdefault(key, []).append((wk, _num(r[price_col], f"{what} {key} {wk}"), str(r["currency"])))
    for k in out:
        out[k].sort()
    return out


def load_masters(model_dir: str, terminal_moms: Dict[str, List[str]],
                 physical_edges: Dict[str, set]) -> VCMasters:
    """terminal_moms: product -> [terminal MOM node names];
    physical_edges: product -> {"A->B", ...} (the ledger's physical edges, for checks)."""
    cfg = {r["key"]: r["value"] for r in _read(model_dir, "vc_config.csv").to_dict("records")}
    for k in ("hq_currency", "common_currency"):
        if not cfg.get(k):
            raise MasterError(f"vc_config.csv: {k} is required")
    hold = cfg.get("holding_rate_weekly", "")
    holding = None if hold in ("", None) else _num(hold, "vc_config holding_rate_weekly")

    ents = {}
    for r in _read(model_dir, "vc_entity.csv").to_dict("records"):
        if r["kind"] not in ENTITY_KINDS:
            raise MasterError(f"vc_entity.csv: kind {r['kind']!r} not in {ENTITY_KINDS}")
        cons = str(r.get("consolidated", "")).strip().lower()
        if cons not in ("1", "0", "true", "false", "yes", "no"):
            raise MasterError(f"vc_entity.csv: consolidated must be 1/0 for {r['entity_id']}")
        if r["entity_id"] in ents:
            raise MasterError(f"vc_entity.csv: entity {r['entity_id']} twice")
        ents[r["entity_id"]] = Entity(r["entity_id"], r.get("entity_name", ""), r["kind"],
                                      r["functional_currency"], cons in ("1", "true", "yes"))

    assign = {}
    for r in _read(model_dir, "vc_node_assignment.csv").to_dict("records"):
        k = (r["node_id"], r["product_id"])
        if k in assign:
            raise MasterError(f"vc_node_assignment.csv: {k} twice")
        if r["entity_id"] not in ents:
            raise MasterError(f"vc_node_assignment.csv: unknown entity {r['entity_id']} for {k}")
        ct = r.get("channel_type", "")
        if ct and ct not in CHANNEL_TYPES:
            raise MasterError(f"vc_node_assignment.csv: channel_type {ct!r} (own / external / online)")
        assign[k] = Assignment(r["node_id"], r["product_id"], r["entity_id"], ct, r.get("local_currency", ""))

    pr_df = _read(model_dir, "vc_price_rule.csv")
    for t in pr_df.get("price_type", []):
        if t not in PRICE_TYPES:
            raise MasterError(f"vc_price_rule.csv: price_type {t!r} not in {PRICE_TYPES}")
    price_rules = _series_table(pr_df, ["edge_id", "product_id", "price_type"], "price", "vc_price_rule.csv")

    mp = _series_table(_read(model_dir, "ppc_market_price.csv").rename(columns={"market_price": "price"}),
                       ["market_node", "product_id"], "price", "ppc_market_price.csv")
    sc = _series_table(_read(model_dir, "ppc_supplier_cost.csv").rename(columns={"purchase_price": "price"}),
                       ["supplier_node", "product_id"], "price", "ppc_supplier_cost.csv")

    node_cost: Dict[tuple, List[dict]] = {}
    seen = set()
    for r in _read(model_dir, "ppc_node_cost_rule.csv").to_dict("records"):
        k = (r["node_id"], r["product_id"])
        if r["cost_type"] == "logistics_cost":
            raise MasterError(f"ppc_node_cost_rule.csv: freight (logistics_cost) on node {k}. "
                              f"Freight is written on the physical edge only "
                              f"(ppc_edge_cost_rule.csv; RequestLetter_StageD_Phase1 Part 0-2)")
        if (k, r["cost_type"]) in seen:
            raise MasterError(f"ppc_node_cost_rule.csv: {k} {r['cost_type']} written twice")
        seen.add((k, r["cost_type"]))
        node_cost.setdefault(k, []).append({
            "cost_type": r["cost_type"], "basis": r["basis"],
            "rate": _num(r["rate"], f"node cost {k}"), "fixed": _num(r["fixed_amount"], f"node cost {k}"),
            "currency": r["currency"], "note": r.get("note", "")})

    edge_cost: Dict[tuple, List[dict]] = {}
    seen = set()
    for r in _read(model_dir, "ppc_edge_cost_rule.csv").to_dict("records"):
        k = (r["edge_id"], r["product_id"])
        if (k, r["cost_type"]) in seen:
            raise MasterError(f"ppc_edge_cost_rule.csv: {k} {r['cost_type']} written twice")
        seen.add((k, r["cost_type"]))
        edge_cost.setdefault(k, []).append({
            "cost_type": r["cost_type"], "basis": r["basis"],
            "rate": _num(r["rate"], f"edge cost {k}"), "fixed": _num(r["fixed_amount"], f"edge cost {k}"),
            "currency": r["currency"]})

    tariff = {}
    for r in _read(model_dir, "ppc_tariff_rule.csv").to_dict("records"):
        k = (r["edge_id"], r["product_id"])
        if k in tariff:
            raise MasterError(f"ppc_tariff_rule.csv: {k} written twice")
        tariff[k] = {"rate": _num(r["tariff_rate"], f"tariff {k}"), "basis": r.get("tariff_basis", ""),
                     "from": r.get("from_country", ""), "to": r.get("to_country", "")}

    tp = {}
    for r in _read(model_dir, "ppc_transfer_price_rule.csv").to_dict("records"):
        k = (r["mom_node"], r["product_id"])
        if k in tp:
            raise MasterError(f"ppc_transfer_price_rule.csv: {k} written twice")
        tp[k] = {"method": r["method"], "margin_rate": float(r["margin_rate"] or 0),
                 "fixed_price": float(r["fixed_price"] or 0) if r.get("fixed_price", "") != "" else None,
                 "currency": r["currency"]}

    # ── the same price in two places -> stop ──────────────────────────
    for (edge, prod, ptype), rows in price_rules.items():
        src = edge.split("->")[0]
        if src in terminal_moms.get(prod, []) and (src, prod) in tp:
            raise MasterError(
                f"price written twice: {edge} {prod} has a {ptype} price in vc_price_rule.csv and a "
                f"transfer price in ppc_transfer_price_rule.csv ({src}). Keep one.")
        if prod in physical_edges and edge not in physical_edges[prod]:
            raise MasterError(f"vc_price_rule.csv: {edge} is not a physical edge of {prod}")

    return VCMasters(model_dir=model_dir, hq_currency=cfg["hq_currency"],
                     common_currency=cfg["common_currency"],
                     report_start=cfg.get("report_start") or None,
                     holding_rate_weekly=holding, entities=ents, assignment=assign,
                     price_rules=price_rules, market_price=mp, supplier_cost=sc,
                     node_cost=node_cost, edge_cost=edge_cost, tariff=tariff, transfer_price=tp)
