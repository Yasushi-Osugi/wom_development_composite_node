# -*- coding: utf-8 -*-
"""
マスターの読み込み（RequestLetter_StageD_Phase1 §1-2）

新しいマスター（題材のモデルのフォルダ）：
    vc_config.csv            key,value：hq_currency, common_currency, report_start, holding_rate_weekly
    vc_entity.csv            entity_id, entity_name, kind, functional_currency, consolidated
    vc_node_assignment.csv   node_id, product_id, entity_id, channel_type, local_currency
    vc_price_rule.csv        edge_id, product_id, price_type, week, price, currency
    vc_sales_cost_rule.csv   （任意、G1）node_id, product_id, cost_item, ppc_cost_type, basis, rate,
                             currency, note。直販の売上比率の費用の費目と、外部の代理店への卸売の
                             MDF（G2、distributor_mdf）（load_sales_cost_rule）
    vc_customs_valuation_rule.csv （任意、G4）edge_id, product_id, goods_value_basis,
                             goods_value_per_unit, currency, freight_in_goods_value,
                             insurance_added_per_unit, duty_week, note。関税の課税価格の決め方
                             （load_customs_valuation_rule）

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
    # vc_sales_cost_rule.csv (G1 C1): (leaf, product) -> [{cost_item, ppc_cost_type, rate, currency, note}]
    # Empty when the file is absent (the ledger then behaves as before).
    sales_cost: Dict[Tuple[str, str], List[dict]] = field(default_factory=dict)
    # vc_customs_valuation_rule.csv (G4 D1): (edge, product) -> rule dict. Empty when the file is
    # absent (the tariff is then computed as before: ppc_tariff_rule.csv's basis x rate at the ship week).
    customs_valuation: Dict[Tuple[str, str], dict] = field(default_factory=dict)

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

    sales_cost = load_sales_cost_rule(model_dir, ents, assign, mp, node_cost, edge_cost, price_rules)
    customs = load_customs_valuation_rule(model_dir, ents, assign, tariff, edge_cost, physical_edges)

    return VCMasters(model_dir=model_dir, hq_currency=cfg["hq_currency"],
                     common_currency=cfg["common_currency"],
                     report_start=cfg.get("report_start") or None,
                     holding_rate_weekly=holding, entities=ents, assignment=assign,
                     price_rules=price_rules, market_price=mp, supplier_cost=sc,
                     node_cost=node_cost, edge_cost=edge_cost, tariff=tariff, transfer_price=tp,
                     sales_cost=sales_cost, customs_valuation=customs)


SALES_COST_FILE = "vc_sales_cost_rule.csv"
SALES_COST_COLS = ("node_id", "product_id", "cost_item", "ppc_cost_type", "basis", "rate", "currency", "note")
_TOL = 1e-9


def load_sales_cost_rule(model_dir, ents, assign, market_price, node_cost, edge_cost,
                         price_rules=None) -> Dict[tuple, List[dict]]:
    """vc_sales_cost_rule.csv（G1 C1、G2 D2。任意）。無ければ {}（今の動き）。

    1 行 ＝ leaf × SKU × 費目。leaf の種類で計上のしかたが違う：
      直販の leaf（own / online）      その販売の週に「率 × その販売の売上」を売り手の販売費として
                                       1 行ずつ（ledger._consumer）
      外部の代理店の leaf（external）  その leaf への卸売の週に「率 × その卸売の売上」を売り手の販売費
                                       として 1 行ずつ（ledger._transfer。費目は distributor_mdf だけ）
    読み込みで次を確かめ、違えば MasterError：
      - 列がそろっている。ノード・SKU・費目の重複が無い
      - 費目は policy.SALES_COST_ITEMS、ppc_cost_type は sga_cost / marketing_cost、basis は revenue だけ
      - rate は 0 以上 1 以下の数
      - ノードの種類（vc_node_assignment.csv）と費目：
          channel_type が own / online、法人がグループ → distributor_mdf 以外。currency はその leaf・SKU の
            市場価格（ppc_market_price.csv）の通貨と同じ
          channel_type が external、法人が external_channel → distributor_mdf だけ。currency はその leaf に
            入る区間の卸価格（vc_price_rule.csv、price_type=wholesale）の通貨と同じ。卸価格の行が無ければ止める
          それ以外のノード → 止める
      各行の辞書には "external"（外部の代理店の leaf なら True）を付ける。
    C4（二つのファイルのずれ。どちらの leaf にも同じ規則）：行のあるノード・SKU ごとに、
      1. ppc_cost_type ごとの率の合計 ＝ ppc_node_cost_rule.csv の同じ種類の basis=revenue の行の率
      2. その PPC の行（basis=revenue）の固定額の合計 ＝ 区間 <leaf>->CONSUMER の費用の行の 1 個当たりの
         額（rate ＋ fixed。台帳の _consumer が計上する額）の合計（行が無ければ 0）
      3. PPC に basis=revenue の行がある種類に、この表の行が無い
    """
    from wom.valuechain import policy as POL
    df = _read(model_dir, SALES_COST_FILE, required=False)
    if df is None:
        return {}
    fn = SALES_COST_FILE
    miss = [c for c in SALES_COST_COLS if c not in df.columns]
    if miss:
        raise MasterError(f"{fn}: missing columns {miss} (needs {list(SALES_COST_COLS)})")
    out: Dict[tuple, List[dict]] = {}
    seen = set()
    for i, r in enumerate(df.to_dict("records"), start=2):
        where = f"{fn} line {i}"
        node, prod, item = r["node_id"].strip(), r["product_id"].strip(), r["cost_item"].strip()
        k = (node, prod)
        if (k, item) in seen:
            raise MasterError(f"{where}: {node} / {prod} / {item} written twice")
        seen.add((k, item))
        if item not in POL.SALES_COST_ITEMS:
            raise MasterError(f"{where}: cost_item {item!r} not in {sorted(POL.SALES_COST_ITEMS)} "
                              f"(wom/valuechain/policy.py SALES_COST_ITEMS)")
        ptype = r["ppc_cost_type"].strip()
        if ptype not in POL.SALES_COST_PPC_TYPES:
            raise MasterError(f"{where}: ppc_cost_type {ptype!r} not in {POL.SALES_COST_PPC_TYPES}")
        if r["basis"].strip() != "revenue":
            raise MasterError(f"{where}: basis {r['basis']!r}; only 'revenue' is supported")
        rate = _num(r["rate"], f"{where} rate")
        if not (0.0 <= rate <= 1.0):
            raise MasterError(f"{where}: rate {rate} must be between 0 and 1")
        a = assign.get(k)
        if a is None:
            raise MasterError(f"{where}: no vc_node_assignment.csv row for {node} / {prod}")
        ent = ents[a.entity_id]
        direct = a.channel_type in ("own", "online") and ent.is_group
        external = a.channel_type == "external" and ent.kind == "external_channel"
        ccy = r["currency"].strip()
        if external:
            if item not in POL.EXTERNAL_SALES_COST_ITEMS:
                raise MasterError(f"{where}: cost_item {item!r} is for a direct-sales leaf (own / online); "
                                  f"{node} / {prod} is an external distributor leaf (entity {a.entity_id}), "
                                  f"which takes only {list(POL.EXTERNAL_SALES_COST_ITEMS)}")
            ccys = {c for (edge, p, t), rows in (price_rules or {}).items()
                    if p == prod and t == "wholesale" and edge.split("->")[-1] == node
                    for _, _, c in rows}
            if not ccys:
                raise MasterError(f"{where}: no wholesale price (vc_price_rule.csv, price_type=wholesale) "
                                  f"on an edge into {node} / {prod}; the distributor_mdf rate needs the "
                                  f"wholesale revenue")
            if ccys != {ccy}:
                raise MasterError(f"{where}: currency {ccy!r} differs from the wholesale price currency "
                                  f"{sorted(ccys)} of the edge into {node} / {prod}")
        elif direct:
            if item in POL.EXTERNAL_SALES_COST_ITEMS:
                raise MasterError(f"{where}: cost_item {item!r} is only for an external distributor leaf "
                                  f"(channel_type 'external', entity kind external_channel); {node} / {prod} "
                                  f"is a direct-sales leaf (channel_type {a.channel_type!r})")
            ccys = {c for _, _, c in market_price.get(k, [])}
            if not ccys:
                raise MasterError(f"{where}: no ppc_market_price.csv row for {node} / {prod}")
            if ccys != {ccy}:
                raise MasterError(f"{where}: currency {ccy!r} differs from the market price currency "
                                  f"{sorted(ccys)} of {node} / {prod}")
        else:
            raise MasterError(f"{where}: {node} / {prod} is not a direct-sales leaf (channel_type "
                              f"{a.channel_type!r}, entity {a.entity_id}); the table is for own / online "
                              f"leaves of a group entity, or external leaves of an external_channel entity "
                              f"(distributor_mdf)")
        out.setdefault(k, []).append({"cost_item": item, "ppc_cost_type": ptype, "rate": rate,
                                      "currency": ccy, "note": r.get("note", ""), "external": external})

    # ── C4: the two files must agree ──
    for (node, prod), rows in out.items():
        ppc_rows = [x for x in node_cost.get((node, prod), []) if x["basis"] == "revenue"]
        ppc_types = {x["cost_type"] for x in ppc_rows}
        mine = {}
        for x in rows:
            mine[x["ppc_cost_type"]] = mine.get(x["ppc_cost_type"], 0.0) + x["rate"]
        for t in sorted(ppc_types - set(mine)):
            raise MasterError(f"{fn}: ppc_node_cost_rule.csv has a basis=revenue {t} row for {node} / {prod} "
                              f"but {fn} has no {t} item for it (the PPC row would not be booked)")
        for t in sorted(set(mine) | ppc_types):
            ppc_rate = sum(x["rate"] for x in ppc_rows if x["cost_type"] == t)
            if abs(mine.get(t, 0.0) - ppc_rate) > _TOL:
                raise MasterError(f"{fn}: {node} / {prod} {t}: the items sum to {mine.get(t, 0.0):g} but "
                                  f"ppc_node_cost_rule.csv says {ppc_rate:g}")
        ppc_fixed = sum(x["fixed"] for x in ppc_rows)
        erows = edge_cost.get((f"{node}->CONSUMER", prod), [])
        edge_fixed = sum(x["rate"] + x["fixed"] for x in erows)
        bad_ccy = {x["currency"] for x in ppc_rows if x["fixed"]} | {x["currency"] for x in erows}
        if len(bad_ccy) > 1:
            raise MasterError(f"{fn}: {node} / {prod}: the fixed amounts of ppc_node_cost_rule.csv and "
                              f"ppc_edge_cost_rule.csv ({node}->CONSUMER) use different currencies "
                              f"{sorted(bad_ccy)}")
        if abs(ppc_fixed - edge_fixed) > _TOL:
            raise MasterError(f"{fn}: {node} / {prod}: the basis=revenue rows of ppc_node_cost_rule.csv have "
                              f"a fixed amount of {ppc_fixed:g} per unit, but the {node}->CONSUMER rows of "
                              f"ppc_edge_cost_rule.csv add up to {edge_fixed:g} (write the delivery / packing "
                              f"cost on that edge)")
    return out


CUSTOMS_FILE = "vc_customs_valuation_rule.csv"
CUSTOMS_COLS = ("edge_id", "product_id", "goods_value_basis", "goods_value_per_unit", "currency",
                "freight_in_goods_value", "insurance_added_per_unit", "duty_week", "note")
CUSTOMS_GOODS_BASES = ("transfer_price", "explicit")
CUSTOMS_DUTY_WEEKS = ("receipt",)


def load_customs_valuation_rule(model_dir, ents, assign, tariff, edge_cost,
                                physical_edges) -> Dict[tuple, dict]:
    """vc_customs_valuation_rule.csv（G4 D1。任意）。無ければ {}（関税は今のまま）。

    1 行 ＝ 物理の区間 × SKU。その区間の関税を
        課税価格 ＝ 評価用の商品価額 ＋ 価額に含まれない運賃（1 回）＋ 保険・その他
        税額     ＝ 課税価格 × ppc_tariff_rule.csv の tariff_rate
    で計算し、受け手の受入の週に計上する（ledger）。読み込みで次を確かめ、違えば MasterError：
      - 列がそろっている。区間・SKU の重複が無い
      - 物理の区間である。ppc_tariff_rule.csv に同じ区間・SKU の行がある（税率はそちら）
      - 受け手のノードの法人がグループの法人（輸入する法人の在庫原価に計上するため）
      - goods_value_basis は transfer_price / explicit。explicit なら goods_value_per_unit（0 以上の数）
        と currency が要る。transfer_price なら goods_value_per_unit は空欄
      - freight_in_goods_value は 0 / 1。0（価額は運賃別）なら、その区間の ppc_edge_cost_rule.csv に
        logistics_cost の行が要る（足す運賃が無いのに 0 として扱わない）
      - insurance_added_per_unit は空欄（未確認 → 課税価格は未評価）か 0 以上の数（明示の 0 を書く）
      - duty_week は receipt だけ（通関の確定の週は表せないので受入の週で代用。2026-11-12 の決定）
    """
    df = _read(model_dir, CUSTOMS_FILE, required=False)
    if df is None:
        return {}
    fn = CUSTOMS_FILE
    miss = [c for c in CUSTOMS_COLS if c not in df.columns]
    if miss:
        raise MasterError(f"{fn}: missing columns {miss} (needs {list(CUSTOMS_COLS)})")
    out: Dict[tuple, dict] = {}
    for i, r in enumerate(df.to_dict("records"), start=2):
        where = f"{fn} line {i}"
        edge, prod = r["edge_id"].strip(), r["product_id"].strip()
        k = (edge, prod)
        if k in out:
            raise MasterError(f"{where}: {edge} / {prod} written twice (one row per edge x SKU)")
        if prod in physical_edges and edge not in physical_edges[prod]:
            raise MasterError(f"{where}: {edge} is not a physical edge of {prod} "
                              f"(write the edge as '<from node>-><to node>' of the planning tree)")
        if "->" not in edge:
            raise MasterError(f"{where}: edge_id {edge!r} is not '<from node>-><to node>'")
        if k not in tariff:
            raise MasterError(f"{where}: ppc_tariff_rule.csv has no row for {edge} / {prod} "
                              f"(the tariff rate is read from there; add the row)")
        dst = edge.split("->")[-1]
        a = assign.get((dst, prod))
        if a is None or not ents[a.entity_id].is_group:
            raise MasterError(f"{where}: the receiving node {dst} / {prod} is not held by a group entity "
                              f"({a.entity_id if a else 'no vc_node_assignment.csv row'}); the duty is "
                              f"booked as the importer's inventory cost")
        basis = r["goods_value_basis"].strip()
        if basis not in CUSTOMS_GOODS_BASES:
            raise MasterError(f"{where}: goods_value_basis {basis!r} not in {CUSTOMS_GOODS_BASES}")
        gv_raw, ccy = r["goods_value_per_unit"].strip(), r["currency"].strip()
        if basis == "explicit":
            if gv_raw == "" or ccy == "":
                raise MasterError(f"{where}: goods_value_basis=explicit needs goods_value_per_unit and "
                                  f"currency (the value per unit used for the customs value)")
            gv = _num(gv_raw, f"{where} goods_value_per_unit")
            if gv < 0:
                raise MasterError(f"{where}: goods_value_per_unit {gv} must be 0 or more")
        else:
            if gv_raw != "":
                raise MasterError(f"{where}: goods_value_basis=transfer_price takes the lot's transfer price; "
                                  f"leave goods_value_per_unit blank (or use goods_value_basis=explicit)")
            gv = None
        fig = r["freight_in_goods_value"].strip()
        if fig not in ("0", "1"):
            raise MasterError(f"{where}: freight_in_goods_value {fig!r} must be 0 (the value excludes the "
                              f"freight: add it) or 1 (the value includes it: add nothing)")
        if fig == "0" and not any(x["cost_type"] == "logistics_cost" for x in edge_cost.get(k, [])):
            raise MasterError(f"{where}: freight_in_goods_value=0 but ppc_edge_cost_rule.csv has no "
                              f"logistics_cost row for {edge} / {prod} (no freight to add; write the "
                              f"freight row, or set freight_in_goods_value=1)")
        ins_raw = r["insurance_added_per_unit"].strip()
        if ins_raw == "":
            ins = None                           # not confirmed -> the customs value is unvalued
        else:
            ins = _num(ins_raw, f"{where} insurance_added_per_unit")
            if ins < 0:
                raise MasterError(f"{where}: insurance_added_per_unit {ins} must be 0 or more")
        dw = r["duty_week"].strip()
        if dw not in CUSTOMS_DUTY_WEEKS:
            raise MasterError(f"{where}: duty_week {dw!r}; only {CUSTOMS_DUTY_WEEKS} is supported "
                              f"(the receipt week stands for the customs clearance week)")
        out[k] = {"goods_value_basis": basis, "goods_value_per_unit": gv, "currency": ccy,
                  "freight_in_goods_value": fig == "1", "insurance_added_per_unit": ins,
                  "duty_week": dw, "note": r.get("note", "")}
    return out
