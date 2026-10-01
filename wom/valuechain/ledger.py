# -*- coding: utf-8 -*-
"""
台帳の本体（RequestLetter_StageD_Phase1 §1-3〜§1-7、設計 §1〜§5）

入力：出荷の記録（records.PlanRecords）、マスター（masters.VCMasters）、為替（fx.FxTable）。
出力：金額の明細（行ごとに書き出す sink）、週ごとの集計（views が使う）、在庫の週末の残高。

在庫の記録（Lot_ID ごと）
    物の所在（ノード、または輸送中＝その出荷の ID）と、原価を持つ法人（owner）を別に持つ。
    原価は三つの基準で持つ（どれも HQ・共通・owner の機能通貨の 3 つの額）：
      v1      V1（ノード・区間の管理評価）。法人内の管理価格を含む
      entity  V2・V3（第 1 回）。法人の帳簿：取得原価＋その法人で発生した在庫原価。管理利益を含まない
      group   第 2 回（未実現利益の消去後）の期待値のため。グループの外から得た原価＋在庫原価
    到着は所在の振替だけ（原価は変わらない、設計 §2.3）。組立・加工（lot が MOM の P に入った週）は、
    そのノードにある同じ Lot_ID の記録をまとめて 1 つにし、加工費を加える（部材の在庫と完成品の在庫に
    同じ原価を残さない、設計 §2.4）。ノード費用は、lot がそのノードの P に入った週に 1 回だけ。

売上と仕入（区間ごと。売り手＝出荷する物理のノードの owner、買い手＝受け手のノードの法人）
    同じ法人            管理価格（あれば）。無ければ原価振替（管理利益 0、price_type=cost_transfer）
    連結の中の別の法人  法人間の価格。無ければ未評価（NaN）＋未設定価格の一覧
    それ以外（外部）    外部への販売。外部チャネル（②）なら卸価格、無ければ NaN＋一覧
    外部の供給者→       ppc_supplier_cost（外部からの仕入）
    leaf_out→消費者     ppc_market_price。owner がグループなら外部売上、外部チャネルなら「観測」

費用の分け方は policy.py（1 か所）。為替は fx.py（取引の週の為替。在庫原価は取得時の換算額のまま）。
未評価（NaN）の明細は、その lot の記録を「未評価」にし、その後の明細にも印を付ける（合計に 0 として
足さない）。
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from wom.valuechain import policy as POL
from wom.valuechain.records import (K_CONSUMER, K_HANDOFF, K_INBOUND, K_OUTBOUND, K_PURCHASE,
                                    PlanRecords, Shipment)

NAN = float("nan")
BASES = ("v1", "entity", "group")
ALL = "v1,entity,group"

LINE_COLS = ["line_id", "src_id", "week_index", "week", "product", "lot_id", "entity", "node",
             "counterparty", "kind", "scope", "basis", "family", "price_type",
             "amount_orig", "currency_orig", "fx_method",
             "amt_hq", "amt_common", "amt_func", "func_currency", "amt_local", "local_currency",
             "valued", "note"]


def _isnan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


@dataclass
class Rec:
    rid: int
    product: str
    lot: str
    item: str
    units: float
    owner: str
    location: str              # node name, or "transit:<ship_id>"
    cost: Dict[str, List[float]]   # basis -> [hq, common, func]
    valued: bool = True
    tp: Tuple[float, str] = (NAN, "")         # transfer price of the lot (amount, ccy)
    purchase: Tuple[float, str] = (NAN, "")   # external purchase price (amount, ccy)
    external: bool = False      # left the group (external channel stock: observation only)
    transit_edge: str = ""      # the physical edge while in transit
    costs_done: set = field(default_factory=set)   # nodes whose node costs were applied


class Ledger:
    def __init__(self, records: PlanRecords, masters, fx, sink: Optional[Callable] = None):
        self.r = records
        self.m = masters
        self.fx = fx
        self.sink = sink                      # sink(line_tuple) for every money line
        self.labels = records.week_labels
        self.hq, self.common = masters.hq_currency, masters.common_currency
        self.recs: Dict[int, Rec] = {}
        self.by_lot: Dict[Tuple[str, str], set] = defaultdict(set)
        self._rid = 0
        self._lid = 0
        # aggregates for the views
        # [hq, common, func, local, n_valued, n_unvalued, n_lines, hq_known]
        #   valued sums: the line amount is known AND the lot record is valued
        #   hq_known:    every known line amount (also on an unvalued record), for cost comparisons
        self.agg: Dict[tuple, List[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0.0])
        self.inv_rows: List[dict] = []        # weekly closing inventory (aggregated)
        self.missing: Dict[tuple, dict] = {}  # missing prices
        self.issues: List[dict] = []
        self.flow_counts = defaultdict(int)
        self.holding_unset = masters.holding_rate_weekly is None
        self.unvalued_out: Dict[tuple, float] = defaultdict(float)
        # cost issued by a sale whose price is not set (the cost leaves the seller's books,
        # but the sale cannot be valued in the P&L) -- for the conservation check
        self.unpriced_issue: Dict[tuple, float] = defaultdict(float)

    # ── currency ────────────────────────────────────────────────────
    def _conv(self, amount, ccy, w, func_ccy, local_ccy, context):
        """(hq, common, func, local, method) of `amount ccy` at week index w."""
        if _isnan(amount):
            return NAN, NAN, NAN, NAN, "unvalued_amount"
        wk = self.labels[w]
        out, methods = [], set()
        for tgt in (self.hq, self.common, func_ccy, local_ccy or func_ccy):
            r, mth = self.fx.rate(ccy, tgt, wk, context)
            methods.add(mth)
            out.append(amount * r if not math.isnan(r) else NAN)
        method = ("missing_unvalued" if "missing_unvalued" in methods else
                  "first_week_rate_before_table" if "first_week_rate_before_table" in methods else
                  "table_week" if "table_week" in methods else "same_currency")
        return out[0], out[1], out[2], out[3], method

    # ── lines ──────────────────────────────────────────────────────
    def _line(self, s_id, w, product, lot, entity, node, cpty, kind, scope, basis, family, ptype,
              amount, ccy, method, hq, common, func, func_ccy, local, local_ccy, valued, note=""):
        self._lid += 1
        valued = bool(valued) and not _isnan(hq)
        if self.sink is not None:
            self.sink((self._lid, s_id, w, self.labels[w], product, lot, entity, node, cpty, kind, scope,
                       basis, family, ptype, amount, ccy, method, hq, common, func, func_ccy, local,
                       local_ccy, int(valued), note))
        key = (w, product, entity, node, cpty, kind, scope, basis, family, ptype)
        a = self.agg[key]
        if valued:
            a[0] += hq
            a[1] += common if not _isnan(common) else 0.0
            a[2] += func if not _isnan(func) else 0.0
            a[3] += local if not _isnan(local) else 0.0
            a[4] += 1
        else:
            a[5] += 1
        a[6] += 1
        if not _isnan(hq):
            a[7] += hq

    def _ent(self, eid):
        return self.m.entities[eid]

    # ── records ────────────────────────────────────────────────────
    def _new_rec(self, product, lot, item, units, owner, location):
        self._rid += 1
        rec = Rec(self._rid, product, lot, item, units, owner, location,
                  {b: [0.0, 0.0, 0.0] for b in BASES})
        self.recs[rec.rid] = rec
        self.by_lot[(product, lot)].add(rec.rid)
        return rec

    def _drop(self, rec):
        self.by_lot[(rec.product, rec.lot)].discard(rec.rid)
        del self.recs[rec.rid]

    def _at(self, product, lot, location):
        return [self.recs[i] for i in self.by_lot.get((product, lot), ()) if self.recs[i].location == location]

    def _add_cost(self, rec, bases, hq, common, func, w):
        if _isnan(hq) and rec.valued:
            # the record's valued cost leaves the valued balance (conservation check)
            self.unvalued_out[(w, rec.owner)] += rec.cost["entity"][0]
            rec.valued = False
        for b in bases:
            c = rec.cost[b]
            c[0] += hq
            c[1] += common
            c[2] += func

    # ── main ───────────────────────────────────────────────────────
    def run(self):
        nodes = self.r.nodes
        events = []
        for i, s in enumerate(self.r.shipments):
            rank = nodes[(s.product, s.node)].rank if (s.product, s.node) in nodes else 0
            events.append((s.week, rank, 1, i))
            if s.kind in (K_PURCHASE, K_INBOUND, K_OUTBOUND) and s.arrival_in_horizon and s.to:
                rrank = nodes[(s.product, s.to)].rank
                events.append((s.arrival_week, rrank, 0, i))
        events.sort()
        n = len(self.labels)
        ei = 0
        for w in range(n):
            while ei < len(events) and events[ei][0] == w:
                _, _, phase, i = events[ei]
                s = self.r.shipments[i]
                if phase == 0:
                    self._receipt(s)
                else:
                    self._ship(s)
                ei += 1
            self._week_end(w)
        if ei < len(events):
            self.issues.append({"issue": "events_after_horizon", "count": len(events) - ei})
        return self

    # ── shipments ─────────────────────────────────────────────────
    def _ship(self, s: Shipment):
        self.flow_counts[s.kind] += 1
        if s.kind == K_HANDOFF:
            if not self._at(s.product, s.lot_id, s.phys_from):
                self.issues.append({"issue": "handoff_without_stock", "ship_id": s.ship_id})
            return
        if s.kind == K_PURCHASE:
            return self._purchase(s)
        if s.kind == K_CONSUMER:
            return self._consumer(s)
        recs = self._at(s.product, s.lot_id, s.phys_from)
        if not recs:
            self.issues.append({"issue": "ship_without_stock", "ship_id": s.ship_id, "at": s.phys_from})
            return
        for rec in recs:
            self._transfer(s, rec)

    def _purchase(self, s: Shipment):
        m = self.m
        w, wk = s.week, self.labels[s.week]
        seller = m.entity_of(s.phys_from, s.product)
        buyer = m.entity_of(s.to, s.product)
        price, ccy, _ = m.supplier(s.phys_from, s.product, wk)
        amount = price * s.units if not _isnan(price) else NAN
        if _isnan(price):
            self._missing(s, "supplier_cost", seller.entity_id, buyer.entity_id)
            ccy = ccy or buyer.functional_currency
        rec = self._new_rec(s.product, s.lot_id, s.item, s.units, buyer.entity_id, f"transit:{s.ship_id}")
        rec.transit_edge = s.edge
        rec.purchase = (amount, ccy)
        hq, cm, fn, lc, mth = self._conv(amount, ccy, w, buyer.functional_currency, "", "purchase")
        scope = "external" if not seller.is_group else ("intercompany" if seller.entity_id != buyer.entity_id else "management")
        self._line(s.ship_id, w, s.product, s.lot_id, buyer.entity_id, s.to, seller.entity_id,
                   "acquisition", scope, ALL, "purchase", "external_purchase", amount, ccy, mth,
                   hq, cm, fn, buyer.functional_currency, lc, buyer.functional_currency, True)
        self._add_cost(rec, BASES, hq, cm, fn, w)
        self._edge_costs(s, rec, seller, buyer)

    def _price(self, s: Shipment, rec: Rec, seller, buyer, scope):
        """(amount, ccy, price_type) of the transfer; amount NaN when not set."""
        m = self.m
        wk = self.labels[s.week]
        src = s.phys_from
        tp = m.transfer_price.get((src, s.product)) if self.r.nodes[(s.product, src)].is_terminal_mom else None
        if tp is not None:
            ptype = "intercompany" if scope == "intercompany" else ("management" if scope == "management" else "transfer_to_outside")
            if tp["method"] == "fixed":
                return (tp["fixed_price"] * s.units, tp["currency"], ptype)
            if tp["method"] == "cost_plus":
                r, _ = self.fx.rate(tp["currency"], self.hq, wk, "cost_plus")
                cost_hq = rec.cost["entity"][0]
                amt = cost_hq / r * (1.0 + tp["margin_rate"]) if not math.isnan(r) else NAN
                return (amt, tp["currency"], ptype)
            raise ValueError(f"unknown transfer price method {tp['method']!r}")
        ptype = ("wholesale" if buyer.kind == "external_channel" else
                 "management" if scope == "management" else "intercompany")
        price, ccy, _ = m.price_rule(s.edge, s.product, ptype, wk)
        if not _isnan(price):
            return (price * s.units, ccy, ptype)
        if scope == "management":
            return (None, "", "cost_transfer")
        self._missing(s, ptype, seller.entity_id, buyer.entity_id)
        return (NAN, seller.functional_currency, ptype)

    def _transfer(self, s: Shipment, rec: Rec):
        m = self.m
        w = s.week
        seller = self._ent(rec.owner)
        buyer = m.entity_of(s.to, s.product)
        if rec.external:                     # outside the group: just follow the stock (observation)
            rec.location = f"transit:{s.ship_id}"
            rec.transit_edge = s.edge
            rec.owner = buyer.entity_id
            return
        if buyer.entity_id == seller.entity_id:
            scope = "management"
        elif buyer.is_group and buyer.consolidated and seller.consolidated:
            scope = "intercompany"
        else:
            scope = "external"
        amount, ccy, ptype = self._price(s, rec, seller, buyer, scope)
        node = s.phys_from
        sf = seller.functional_currency
        if ptype == "cost_transfer":
            c = rec.cost["v1"]
            self._line(s.ship_id, w, s.product, s.lot_id, seller.entity_id, node, buyer.entity_id,
                       "revenue", "management", "v1", "transfer", "cost_transfer", c[0], self.hq,
                       "carried", c[0], c[1], c[2], sf, c[2], sf, rec.valued, "原価振替（管理利益 0）")
            self._line(s.ship_id, w, s.product, s.lot_id, seller.entity_id, node, buyer.entity_id,
                       "cogs", "management", "v1", "transfer", "cost_transfer", c[0], self.hq,
                       "carried", c[0], c[1], c[2], sf, c[2], sf, rec.valued, "原価振替")
        else:
            hq, cm, fn, lc, mth = self._conv(amount, ccy, w, sf, "", f"{ptype} {s.edge}")
            if self.r.nodes[(s.product, node)].is_terminal_mom:
                rec.tp = (amount, ccy)
            # valued = the whole sale (price AND cost) is known; the known price alone stays in
            # hq_known (views: revenue_known), so a sale with an unknown cost has no profit
            self._line(s.ship_id, w, s.product, s.lot_id, seller.entity_id, node, buyer.entity_id,
                       "revenue", scope, "all", "sale", ptype, amount, ccy, mth, hq, cm, fn, sf, fn, sf,
                       rec.valued and not _isnan(amount),
                       "" if rec.valued else "原価が未評価の販売（売上の額は分かる）")
            cogs_bases = ("v1",) if scope == "management" else ("v1", "entity") if scope == "intercompany" else BASES
            priced = not _isnan(amount)
            if not priced and rec.valued and scope != "management":
                self.unpriced_issue[(w, seller.entity_id)] += rec.cost["entity"][0]
            for b in cogs_bases:
                c = rec.cost[b]
                self._line(s.ship_id, w, s.product, s.lot_id, seller.entity_id, node, buyer.entity_id,
                           "cogs", scope, b, "sale", ptype, c[0], self.hq, "carried", c[0], c[1], c[2],
                           sf, c[2], sf, rec.valued and priced,
                           "" if priced else "価格が未設定の販売の原価（未評価）")
            # the buyer's side
            bf = buyer.functional_currency
            bhq, bcm, bfn, blc, bm = self._conv(amount, ccy, w, bf, "", f"{ptype} {s.edge} (buyer)")
            if scope == "management":
                rec.cost["v1"] = [bhq, bcm, bfn]
                self._line(s.ship_id, w, s.product, s.lot_id, buyer.entity_id, s.to, seller.entity_id,
                           "acquisition", scope, "v1", "purchase", ptype, amount, ccy, bm, bhq, bcm, bfn,
                           bf, blc, bf, rec.valued and not _isnan(amount))
                # only the V1 basis is affected (NaN there); the entity book is unchanged,
                # so the record stays valued for V2 / V3
            elif scope == "intercompany":
                ent_func = rec.cost["entity"]
                rec.cost["v1"] = [bhq, bcm, bfn]
                rec.cost["entity"] = [bhq, bcm, bfn]
                g = rec.cost["group"]
                rec.cost["group"] = [g[0], g[1], NAN]
                self._line(s.ship_id, w, s.product, s.lot_id, buyer.entity_id, s.to, seller.entity_id,
                           "acquisition", scope, "v1,entity", "purchase", ptype, amount, ccy, bm, bhq, bcm,
                           bfn, bf, blc, bf, rec.valued and not _isnan(amount))
                if _isnan(bhq):
                    rec.valued = False
            else:   # left the consolidated group
                if buyer.is_group:   # a group company outside consolidation: its own book starts here
                    for b in BASES:
                        rec.cost[b] = [bhq, bcm, bfn]
                    rec.valued = not _isnan(bhq)
                    self._line(s.ship_id, w, s.product, s.lot_id, buyer.entity_id, s.to, seller.entity_id,
                               "acquisition", "external", ALL, "purchase", ptype, amount, ccy, bm, bhq, bcm,
                               bfn, bf, blc, bf, rec.valued)
                else:
                    rec.external = True
                    for b in BASES:
                        rec.cost[b] = [NAN, NAN, NAN]
            rec.owner = buyer.entity_id
        rec.owner = buyer.entity_id
        rec.location = f"transit:{s.ship_id}"
        rec.transit_edge = s.edge
        self._edge_costs(s, rec, seller, buyer)

    def _edge_costs(self, s: Shipment, rec: Rec, seller, buyer):
        """freight / insurance / tariff of the physical edge (policy.py)."""
        m = self.m
        w = s.week
        if buyer.is_group:
            ecls = POL.EDGE_INTO_OR_IN_GROUP
        elif seller.is_group:
            ecls = POL.EDGE_GROUP_TO_EXTERNAL
        else:
            ecls = POL.EDGE_OUTSIDE_GROUP
        items = []
        for row in m.edge_cost.get((s.edge, s.product), []):
            fam = POL.EDGE_COST_FAMILY.get(row["cost_type"])
            if fam is None:
                raise ValueError(f"edge cost_type {row['cost_type']!r} has no rule in policy.py")
            if fam == "insurance":
                amt = row["rate"] * rec.tp[0] + row["fixed"] * s.units if not _isnan(rec.tp[0]) else NAN
                ccy = row["currency"] if not _isnan(rec.tp[0]) else row["currency"]
            else:
                amt = (row["rate"] * 1 + row["fixed"]) * s.units
                ccy = row["currency"]
            items.append((fam, row["cost_type"], amt, ccy))
        t = m.tariff.get((s.edge, s.product))
        if t is not None:
            basis = rec.purchase if t["basis"] == "material_cost" else rec.tp
            amt = basis[0] * t["rate"] if not _isnan(basis[0]) else NAN
            items.append(("tariff", "tariff_cost", amt, basis[1] or seller.functional_currency))
        for fam, ctype, amt, ccy in items:
            treat = POL.classify_edge_cost(fam, ecls)
            if treat is None:
                continue
            if treat == POL.INVENTORY:
                f = buyer.functional_currency
                hq, cm, fn, lc, mth = self._conv(amt, ccy, w, f, "", f"{ctype} {s.edge}")
                self._line(s.ship_id, w, s.product, s.lot_id, buyer.entity_id, s.to, seller.entity_id,
                           "acquisition", "internal", ALL, fam, ctype, amt, ccy, mth, hq, cm, fn, f, lc, f,
                           rec.valued)
                self._add_cost(rec, BASES, hq, cm, fn, w)
            else:   # seller's selling expense of the week
                f = seller.functional_currency
                hq, cm, fn, lc, mth = self._conv(amt, ccy, w, f, "", f"{ctype} {s.edge}")
                self._line(s.ship_id, w, s.product, s.lot_id, seller.entity_id, s.phys_from, buyer.entity_id,
                           "expense", "selling", ALL, fam, ctype, amt, ccy, mth, hq, cm, fn, f, lc, f, True)

    def _consumer(self, s: Shipment):
        m = self.m
        w, wk = s.week, self.labels[s.week]
        recs = self._at(s.product, s.lot_id, s.node)
        if not recs:
            self.issues.append({"issue": "consumer_sale_without_stock", "ship_id": s.ship_id})
            return
        a = m.assignment.get((s.node, s.product))
        local = a.local_currency if a is not None else ""
        price, ccy, _ = m.market(s.node, s.product, wk)
        amount = price * s.units if not _isnan(price) else NAN
        for rec in recs:
            owner = self._ent(rec.owner)
            if rec.external or not owner.is_group:
                hq, cm, fn, lc, mth = self._conv(amount, ccy, w, owner.functional_currency, local,
                                                 "observation consumer sale")
                self._line(s.ship_id, w, s.product, s.lot_id, owner.entity_id, s.node, s.to,
                           "observation_sale", "observation", "obs", "sale", "market", amount, ccy, mth,
                           hq, cm, fn, owner.functional_currency, lc, local or owner.functional_currency,
                           not _isnan(amount), "外部チャネルの消費者への販売（観測。グループの売上ではない）")
            else:
                if _isnan(price):
                    self._missing(s, "market_price", owner.entity_id, s.to)
                    if rec.valued:
                        self.unpriced_issue[(w, owner.entity_id)] += rec.cost["entity"][0]
                f = owner.functional_currency
                hq, cm, fn, lc, mth = self._conv(amount, ccy, w, f, local, "consumer sale")
                self._line(s.ship_id, w, s.product, s.lot_id, owner.entity_id, s.node, s.to,
                           "revenue", "external", "all", "sale", "market", amount, ccy, mth, hq, cm, fn, f,
                           lc, local or f, rec.valued and not _isnan(amount),
                           "" if rec.valued else "原価が未評価の販売（売上の額は分かる）")
                for b in BASES:
                    c = rec.cost[b]
                    self._line(s.ship_id, w, s.product, s.lot_id, owner.entity_id, s.node, s.to,
                               "cogs", "external", b, "sale", "market", c[0], self.hq, "carried",
                               c[0], c[1], c[2], f, c[2], f, rec.valued and not _isnan(price))
                # freight of the sale to the consumer (edge "<leaf>->CONSUMER"): the seller's
                # selling expense (policy.py: group -> external)
                for row in m.edge_cost.get((f"{s.node}->CONSUMER", s.product), []):
                    fam = POL.EDGE_COST_FAMILY.get(row["cost_type"])
                    if POL.classify_edge_cost(fam, POL.EDGE_GROUP_TO_EXTERNAL) != POL.SELLING:
                        continue
                    amt = (row["rate"] * 1 + row["fixed"]) * s.units
                    hq, cm, fn, lc, mth = self._conv(amt, row["currency"], w, f, local, "consumer freight")
                    self._line(s.ship_id, w, s.product, s.lot_id, owner.entity_id, s.node, s.to,
                               "expense", "selling", ALL, fam, row["cost_type"], amt, row["currency"], mth,
                               hq, cm, fn, f, lc, local or f, True)
            self._drop(rec)

    # ── receipts ──────────────────────────────────────────────────
    def _receipt(self, s: Shipment):
        recs = [self.recs[i] for i in self.by_lot.get((s.product, s.lot_id), ())
                if self.recs[i].location == f"transit:{s.ship_id}"]
        if not recs:
            self.issues.append({"issue": "receipt_without_transit", "ship_id": s.ship_id})
            return
        for rec in recs:
            rec.location = s.to
        info = self.r.nodes[(s.product, s.to)]
        if info.node_type == "mom":         # production / assembly: one record per lot at the node
            here = self._at(s.product, s.lot_id, s.to)
            if len(here) > 1:
                keep = here[0]
                for other in here[1:]:
                    if other.owner != keep.owner:
                        self.issues.append({"issue": "merge_different_owner", "lot": s.lot_id})
                    for b in BASES:
                        for k in range(3):
                            keep.cost[b][k] += other.cost[b][k]
                    keep.valued = keep.valued and other.valued
                    if _isnan(keep.purchase[0]) is False and not _isnan(other.purchase[0]):
                        if keep.purchase[1] == other.purchase[1]:
                            keep.purchase = (keep.purchase[0] + other.purchase[0], keep.purchase[1])
                    self._drop(other)
                recs = [keep]
            for rec in recs:
                rec.item = "finished" if info.is_terminal_mom else f"wip:{s.to}"
        for rec in recs:
            self._node_costs(s, rec, info, s.arrival_week)

    def _node_costs(self, s, rec, info, w):
        if info.name in rec.costs_done or rec.external:
            return
        rec.costs_done.add(info.name)
        owner = self._ent(rec.owner)
        if not owner.is_group:
            return
        for row in self.m.node_cost.get((info.name, s.product), []):
            treat = POL.classify_node_cost(row["cost_type"])
            if row["basis"] == "revenue":
                self.issues.append({"issue": "revenue_based_node_cost_not_supported",
                                    "node": info.name, "cost_type": row["cost_type"]})
                continue
            amt = (row["rate"] * 1 + row["fixed"]) * rec.units
            f = owner.functional_currency
            hq, cm, fn, lc, mth = self._conv(amt, row["currency"], w, f, "", f"{row['cost_type']} {info.name}")
            if treat == POL.INVENTORY:
                self._line(s.ship_id, w, s.product, s.lot_id, owner.entity_id, info.name, "",
                           "acquisition", "internal", ALL, row["cost_type"], row["cost_type"], amt,
                           row["currency"], mth, hq, cm, fn, f, lc, f, rec.valued)
                self._add_cost(rec, BASES, hq, cm, fn, w)
            else:
                self._line(s.ship_id, w, s.product, s.lot_id, owner.entity_id, info.name, "",
                           "expense", "selling" if treat == POL.SELLING else "period", ALL,
                           row["cost_type"], row["cost_type"], amt, row["currency"], mth, hq, cm, fn, f,
                           lc, f, True)

    # ── week end ──────────────────────────────────────────────────
    def _week_end(self, w):
        agg = {}
        for rec in self.recs.values():
            if rec.location.startswith("transit:"):
                loc_kind, loc = "transit", rec.transit_edge
            else:
                loc_kind, loc = "node", rec.location
            k = (rec.owner, loc_kind, loc, rec.product, rec.item, rec.valued, rec.external)
            a = agg.get(k)
            if a is None:
                a = agg[k] = [0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            a[0] += 1
            if not rec.external:
                a[1] += rec.cost["v1"][0]
                a[2] += rec.cost["entity"][0]
                a[3] += rec.cost["group"][0]
                a[4] += rec.cost["entity"][1]
                a[5] += rec.cost["entity"][2]
                a[6] += rec.cost["v1"][1]
                a[7] += rec.cost["group"][1]
        for (owner, lk, loc, prod, item, valued, ext), a in agg.items():
            self.inv_rows.append({"week_index": w, "week": self.labels[w], "owner": owner,
                                  "location_kind": lk, "location": loc, "product": prod, "item": item,
                                  "valued": int(valued), "external": int(ext), "lots": a[0],
                                  "v1_hq": a[1], "entity_hq": a[2], "group_hq": a[3],
                                  "entity_common": a[4], "entity_func": a[5], "v1_common": a[6],
                                  "group_common": a[7]})
        if not self.holding_unset:
            rate = self.m.holding_rate_weekly
            for (owner, lk, loc, prod, item, valued, ext), a in agg.items():
                ent = self._ent(owner)
                if ext or not ent.is_group or not valued:
                    continue
                hq = a[2] * rate
                self._line(f"holding:{w}:{owner}:{loc}", w, prod, "", owner, loc if lk == "node" else "",
                           "", "expense", "period", ALL, "holding", "holding", hq, self.hq, "carried",
                           hq, a[4] * rate, a[5] * rate, ent.functional_currency, a[5] * rate,
                           ent.functional_currency, True, "在庫の保有費用（独立した項目）")

    # ── missing prices ────────────────────────────────────────────
    def _missing(self, s: Shipment, ptype, seller, buyer):
        k = (s.edge or s.node, s.product, ptype)
        rec = self.missing.get(k)
        if rec is None:
            rec = self.missing[k] = {"edge_id": s.edge or s.node, "product_id": s.product,
                                     "price_type": ptype, "week": self.labels[s.week], "price": "",
                                     "currency": "", "seller_entity": seller, "buyer_entity": buyer,
                                     "lots": 0, "units": 0.0, "first_ship_week": self.labels[s.week],
                                     "last_ship_week": self.labels[s.week]}
        rec["lots"] += 1
        rec["units"] += s.units
        rec["last_ship_week"] = self.labels[s.week]
