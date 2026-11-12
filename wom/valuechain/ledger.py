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
                        卸売なら、受け手の leaf の vc_sales_cost_rule.csv の行（distributor_mdf、G2）ごとに
                        「率 × 卸売の売上」（取引通貨で小数第 2 位に四捨五入）を売り手の卸売の週の販売費に
                        1 行ずつ。代理店の受入・代理店から消費者への観測の販売では使わない。
                        外部チャネルの leaf の ppc_node_cost_rule.csv の basis=revenue の行に表の行が無ければ
                        issues（revenue_based_cost_on_external_channel_not_booked）
    外部の供給者→       ppc_supplier_cost（外部からの仕入）
    leaf_out→消費者     ppc_market_price。owner がグループなら外部売上、外部チャネルなら「観測」
                        直販の売上比率の費用（vc_sales_cost_rule.csv、G1）は、その販売の週に費目ごとに
                        「率 × 売上」を売り手の販売費として 1 行ずつ。表のあるノードでは
                        ppc_node_cost_rule.csv の basis=revenue の行を PPC 用として使わない

関税の課税価格（G4、vc_customs_valuation_rule.csv に載った区間・SKU だけ）
    出荷の週に「課税価格 ＝ 評価用の商品価額 ＋ 価額に含まれない運賃（その区間の logistics_cost、1 回）
    ＋ 保険・その他」と「税額 ＝ 課税価格 × tariff_rate（取引通貨で小数第 2 位に四捨五入）」を決めて
    おき、受入の週（_receipt。通関の確定の週の代用）に受け手の在庫原価として関税の行を 1 行立てる。
    税額 0 なら行を立てない。どちらでも課税価格の記録（customs_rows → vc_customs_valuation.csv）を
    1 行残す。計画の期間の後に着く出荷は計上せず status=after_horizon。表に載らない区間は今のまま
    （出荷の週に ppc_tariff_rule.csv の tariff_basis × 率）。

取引条件（G5、vc_trade_terms.csv で seller・1〔CIF 型〕を宣言した法人間の区間だけ）
    区間の運賃は、出荷の週に売り手の法人が負担する。売り手の取得の行（v1,entity,group）を 1 行立てて
    すぐに売り手の法人間売上に対応する原価（cogs、intercompany、v1 と entity の 2 行）として払い出す。
    lot のグループの原価にだけ足し、受け手の法人の原価（V1・法人）には足さない。内部の未実現利益の
    eliminated はその分小さくなる（120,000 − (C ＋ 運賃)）。表に無い区間・buyer・0 は今のまま。

費用の分け方は policy.py（1 か所）。為替は fx.py（取引の週の為替。在庫原価は取得時の換算額のまま）。
未評価（NaN）の明細は、その lot の記録を「未評価」にし、その後の明細にも印を付ける（合計に 0 として
足さない）。

内部の未実現利益（RequestLetter_StageD_Phase2）
    連結の法人が持つ評価済みの在庫の lot ごとに U ＝ 法人の原価（entity）− グループの原価（group）。
    U の動きを、法人・製品・所在ごとの事象として `unreal` に記録する（HQ・共通の 2 つの額）：
      eliminated    法人間の販売で新しく生じた内部の利益（買い手の在庫に入る）
      transfer_out / transfer_in   法人間の販売で、売り手の在庫にあった U が買い手へ移る
      realized      外部への評価済みの販売で実現した U（売り手）
      to_unvalued   lot が未評価になって、評価済みの残高から外れた U（価格・為替が無い）
    週末の残高の増減 ＝ eliminated ＋ transfer_in − transfer_out − realized − to_unvalued（法人ごと）。
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
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
        # G1 C3: basis=revenue rows of ppc_node_cost_rule.csv not used here (vc_sales_cost_rule.csv
        # books them at the sale); (node, product, cost_type) -> receipts skipped
        self.ppc_only_node_cost: Dict[tuple, int] = defaultdict(int)
        # G2 D4: basis=revenue rows of ppc_node_cost_rule.csv on an external channel leaf with no
        # vc_sales_cost_rule.csv row (nothing books them: the stock there is outside the group).
        # (node, product, cost_type) -> receipts at the leaf; reported in issues at the end of run()
        self.ext_revenue_cost_unbooked: Dict[tuple, int] = {}
        for (node, prod), a in masters.assignment.items():
            if a.channel_type != "external" or (node, prod) in masters.sales_cost:
                continue
            for row in masters.node_cost.get((node, prod), []):
                if row["basis"] == "revenue":
                    self.ext_revenue_cost_unbooked[(node, prod, row["cost_type"])] = 0
        self.holding_unset = masters.holding_rate_weekly is None
        self.unvalued_out: Dict[tuple, float] = defaultdict(float)
        # cost issued by a sale whose price is not set (the cost leaves the seller's books,
        # but the sale cannot be valued in the P&L) -- for the conservation check
        self.unpriced_issue: Dict[tuple, float] = defaultdict(float)
        # internal unrealized profit events: (w, owner, product, loc_kind, loc, event) -> [hq, common]
        self.unreal: Dict[tuple, List[float]] = defaultdict(lambda: [0.0, 0.0])
        # G4: customs valuations decided at the ship week, booked at the receipt week.
        # (ship_id, rid) -> valuation dict; customs_rows = vc_customs_valuation.csv rows
        self.customs_pending: Dict[tuple, dict] = {}
        self.customs_rows: List[dict] = []
        self.customs_unvalued: Dict[tuple, dict] = {}   # (edge, product, reason) -> {shipments}

    # ── internal unrealized profit (round 2) ───────────────────────
    def _u(self, rec) -> Optional[Tuple[float, float]]:
        """U = entity cost - group cost of a valued lot held by a consolidated group entity;
        None when the lot is not part of the valued group inventory."""
        if rec.external or not rec.valued:
            return None
        ent = self.m.entities.get(rec.owner)
        if ent is None or not (ent.is_group and ent.consolidated):
            return None
        e, g = rec.cost["entity"], rec.cost["group"]
        return (e[0] - g[0], e[1] - g[1])

    def _uev(self, w, rec, event, u, owner=None):
        if u is None:
            return
        if rec.location.startswith("transit:"):
            lk, loc = "transit", rec.transit_edge
        else:
            lk, loc = "node", rec.location
        a = self.unreal[(w, owner or rec.owner, rec.product, lk, loc, event)]
        a[0] += u[0]
        a[1] += u[1] if not _isnan(u[1]) else 0.0

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
            self._uev(w, rec, "to_unvalued", self._u(rec))
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
        for key in sorted(self.customs_pending, key=lambda k: (self.customs_pending[k]["ship_week_index"], k)):
            v = self.customs_pending[key]          # not received in the horizon: no duty booked
            self.customs_rows.append(self._customs_row(v, "", "", "after_horizon"))
        self.customs_pending.clear()
        for (edge, prod, reason), x in sorted(self.customs_unvalued.items()):
            self.issues.append({"issue": "customs_value_unvalued", "edge": edge, "product": prod,
                                "reason": reason, "shipments": x["shipments"],
                                "note": "課税価格が未評価（関税の行は NaN、lot は未評価）"})
        for (node, prod, ctype), n_rec in sorted(self.ext_revenue_cost_unbooked.items()):
            self.issues.append({"issue": "revenue_based_cost_on_external_channel_not_booked",
                                "node": node, "product": prod, "cost_type": ctype, "receipts": n_rec,
                                "note": "外部チャネルの leaf の basis=revenue の行（PPC）に、"
                                        "vc_sales_cost_rule.csv の行が無い（Value Chain では計上しない）"})
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
        u0 = self._u(rec)                    # the lot's unrealized profit before the transfer
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
            if scope == "external" and ptype == "wholesale":
                self._distributor_sales_costs(s, w, seller, buyer, amount, ccy)
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
                if u0 is not None:
                    if _isnan(bhq):
                        self._uev(w, rec, "to_unvalued", u0)
                    else:
                        self._uev(w, rec, "transfer_out", u0)
                        new_u = (bhq - ent_func[0], (bcm - ent_func[1]) if not _isnan(bcm) else NAN)
                        unreal_after = (u0, new_u)
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
                if u0 is not None:     # the lot's unrealized profit is realized by a priced sale
                    self._uev(w, rec, "realized" if priced else "to_unvalued", u0)
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
        if ptype != "cost_transfer" and scope == "intercompany" and u0 is not None and not _isnan(bhq):
            self._uev(w, rec, "transfer_in", unreal_after[0])
            self._uev(w, rec, "eliminated", unreal_after[1])
        self._edge_costs(s, rec, seller, buyer)

    def _distributor_sales_costs(self, s: Shipment, w, seller, buyer, amount, ccy):
        """G2 D3: the sales-based costs of a wholesale to an external distributor leaf
        (vc_sales_cost_rule.csv rows of the receiving leaf, distributor_mdf). One line per row at the
        wholesale week: rate x the wholesale revenue, rounded half up to 2 decimals in the
        transaction currency (NaN when the wholesale is not valued); the seller's selling expense."""
        f = seller.functional_currency
        for row in self.m.sales_cost.get((s.to, s.product), []):
            if not row.get("external", False):
                continue
            if _isnan(amount):
                amt = NAN
            else:
                amt = float((Decimal(repr(float(row["rate"]))) * Decimal(repr(float(amount))))
                            .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            hq, cm, fn, lc, mth = self._conv(amt, ccy, w, f, "", f"sales cost {row['cost_item']} {s.edge}")
            self._line(s.ship_id, w, s.product, s.lot_id, seller.entity_id, s.phys_from, buyer.entity_id,
                       "expense", "selling", ALL, row["ppc_cost_type"], row["cost_item"], amt, ccy, mth,
                       hq, cm, fn, f, lc, f, True, f"販促の対象：{s.to}")

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
        cv_rule = m.customs_valuation.get((s.edge, s.product))
        if t is not None and cv_rule is not None:
            # G4: valued now, booked at the receipt week (_receipt -> _book_customs)
            self.customs_pending[(s.ship_id, rec.rid)] = self._customs_value(s, rec, seller, buyer, t, cv_rule)
        elif t is not None:
            basis = rec.purchase if t["basis"] == "material_cost" else rec.tp
            amt = basis[0] * t["rate"] if not _isnan(basis[0]) else NAN
            items.append(("tariff", "tariff_cost", amt, basis[1] or seller.functional_currency))
        cif = m.cif_freight(s.edge, s.product)
        for fam, ctype, amt, ccy in items:
            treat = POL.classify_edge_cost(fam, ecls)
            if treat is None:
                continue
            if cif and fam == "freight":
                self._cif_freight(s, rec, seller, buyer, ctype, amt, ccy)
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

    # ── customs value (G4) ────────────────────────────────────────
    @staticmethod
    def _duty(cv, rate):
        """cv x rate in Decimal, rounded half up to 2 decimals (like the G2 MDF)."""
        return float((Decimal(repr(float(cv))) * Decimal(repr(float(rate))))
                     .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def _customs_value(self, s: Shipment, rec: Rec, seller, buyer, t, rule) -> dict:
        """Customs value and duty of one shipment on a table edge (amounts in the customs value
        currency; freight converted at the ship week's rate)."""
        wk = self.labels[s.week]
        status = "valued"
        if rule["goods_value_basis"] == "transfer_price":
            goods, ccy = rec.tp[0], (rec.tp[1] or seller.functional_currency)
            if _isnan(goods):
                status = "unvalued_goods_value"
        else:
            goods, ccy = rule["goods_value_per_unit"] * s.units, rule["currency"]
        freight = 0.0
        if not rule["freight_in_goods_value"]:
            for row in self.m.edge_cost.get((s.edge, s.product), []):
                if row["cost_type"] != "logistics_cost":
                    continue
                amt = (row["rate"] * 1 + row["fixed"]) * s.units
                r, _ = self.fx.rate(row["currency"], ccy, wk, f"customs value freight {s.edge}")
                if math.isnan(r):
                    freight = NAN
                    if status == "valued":
                        status = "unvalued_fx"
                    break
                freight += amt * r
        ins_pu = rule["insurance_added_per_unit"]
        if ins_pu is None:
            insurance = NAN
            if status == "valued":
                status = "unvalued_insurance"
        else:
            insurance = ins_pu * s.units
        cv = goods + freight + insurance
        rate = t["rate"]
        duty = NAN if _isnan(cv) else self._duty(cv, rate)
        if status != "valued":
            x = self.customs_unvalued.setdefault((s.edge, s.product, status), {"shipments": 0})
            x["shipments"] += 1
        return {"ship_id": s.ship_id, "lot_id": s.lot_id, "product": s.product, "edge": s.edge,
                "ship_week_index": s.week, "ship_week": wk, "entity": buyer.entity_id,
                "seller": seller.entity_id, "units": s.units,
                "goods_value_basis": rule["goods_value_basis"], "goods_value": goods,
                "freight_added": freight, "insurance_added": insurance, "customs_value": cv,
                "currency": ccy, "tariff_rate": rate, "duty": duty, "status": status}

    @staticmethod
    def _customs_row(v, duty_week, duty_line_id, status) -> dict:
        return {"ship_id": v["ship_id"], "lot_id": v["lot_id"], "product": v["product"], "edge": v["edge"],
                "ship_week": v["ship_week"], "duty_week": duty_week, "entity": v["entity"],
                "units": v["units"], "goods_value_basis": v["goods_value_basis"],
                "goods_value": v["goods_value"], "freight_added": v["freight_added"],
                "insurance_added": v["insurance_added"], "customs_value": v["customs_value"],
                "currency": v["currency"], "tariff_rate": v["tariff_rate"], "duty": v["duty"],
                "duty_line_id": duty_line_id, "status": status}

    def _book_customs(self, s: Shipment, rec: Rec, v: dict):
        """G4 D2: the duty at the receipt week (stands for the customs clearance week): one
        acquisition line on the importer's inventory cost unless the duty is 0; always one
        customs valuation row."""
        w = s.arrival_week
        duty, ccy = v["duty"], v["currency"]
        line_id = ""
        if _isnan(duty) or duty != 0.0:
            buyer = self._ent(v["entity"])
            f = buyer.functional_currency
            hq, cm, fn, lc, mth = self._conv(duty, ccy, w, f, "", f"tariff_cost {s.edge}")
            cv = v["customs_value"]
            cv_s = "未評価" if _isnan(cv) else f"{cv:,.2f} {ccy}"
            self._line(s.ship_id, w, s.product, s.lot_id, buyer.entity_id, s.to, v["seller"],
                       "acquisition", "internal", ALL, "tariff", "tariff_cost", duty, ccy, mth,
                       hq, cm, fn, f, lc, f, rec.valued,
                       f"課税価格 {cv_s} × {v['tariff_rate']:g}（受入の週で代用）")
            line_id = self._lid
            self._add_cost(rec, BASES, hq, cm, fn, w)
        self.customs_rows.append(self._customs_row(v, self.labels[w], line_id, v["status"]))

    def _cif_freight(self, s: Shipment, rec: Rec, seller, buyer, ctype, amt, ccy):
        """G5 D2: the freight of a CIF intercompany edge (vc_trade_terms.csv seller / 1).

        The seller bears it at the ship week: one acquisition line on the seller (v1,entity,group: the
        group part is the group's inventory cost of the lot; v1 / entity balance the seller's books)
        and the cost of the intercompany sale (cogs, intercompany, v1 and entity) on the seller. The
        lot's group cost grows; the receiver's V1 / entity cost does not (its acquisition is the
        price only). The eliminated internal profit shrinks by the freight."""
        w = s.week
        f = seller.functional_currency
        hq, cm, fn, lc, mth = self._conv(amt, ccy, w, f, "", f"{ctype} {s.edge} (CIF, seller)")
        node = s.phys_from
        self._line(s.ship_id, w, s.product, s.lot_id, seller.entity_id, node, buyer.entity_id,
                   "acquisition", "internal", ALL, "freight", ctype, amt, ccy, mth, hq, cm, fn, f, lc, f,
                   rec.valued, "CIF：価格に含む運賃（売り手の負担。グループの在庫原価に入る）")
        for b in ("v1", "entity"):
            self._line(s.ship_id, w, s.product, s.lot_id, seller.entity_id, node, buyer.entity_id,
                       "cogs", "intercompany", b, "freight", ctype, amt, ccy, mth, hq, cm, fn, f, lc, f,
                       rec.valued, "CIF：価格に含む運賃（売り手の負担）")
        # the lot's group cost (func column in the receiver's functional currency, as before)
        bhq, bcm, bfn, _, _ = self._conv(amt, ccy, w, buyer.functional_currency, "",
                                         f"{ctype} {s.edge} (CIF, group)")
        if not _isnan(bhq) and self._u(rec) is not None:
            self._uev(w, rec, "eliminated", (-bhq, -bcm if not _isnan(bcm) else 0.0))
        self._add_cost(rec, ("group",), bhq, bcm, bfn, w)

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
                self._uev(w, rec, "realized" if not _isnan(price) else "to_unvalued", self._u(rec))
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
                # sales-based costs of the direct sale (vc_sales_cost_rule.csv, G1 C2): one line per
                # cost item, rate x the revenue of this sale, the seller's selling expense of the week.
                # No price -> NaN (unvalued), like the revenue line.
                for row in m.sales_cost.get((s.node, s.product), []):
                    if row.get("external", False):   # G2: booked at the wholesale (_transfer)
                        continue
                    amt = row["rate"] * amount if not _isnan(amount) else NAN
                    hq, cm, fn, lc, mth = self._conv(amt, ccy or row["currency"], w, f, local,
                                                     f"sales cost {row['cost_item']} {s.node}")
                    self._line(s.ship_id, w, s.product, s.lot_id, owner.entity_id, s.node, s.to,
                               "expense", "selling", ALL, row["ppc_cost_type"], row["cost_item"], amt,
                               ccy or row["currency"], mth, hq, cm, fn, f, lc, local or f, True)
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
            v = self.customs_pending.pop((s.ship_id, rec.rid), None)
            if v is not None:
                self._book_customs(s, rec, v)
        if self.ext_revenue_cost_unbooked:
            for k in self.ext_revenue_cost_unbooked:
                if k[0] == s.to and k[1] == s.product:
                    self.ext_revenue_cost_unbooked[k] += 1
        info = self.r.nodes[(s.product, s.to)]
        if info.node_type == "mom":         # production / assembly: one record per lot at the node
            here = self._at(s.product, s.lot_id, s.to)
            if len(here) > 1:
                us = [(r_, self._u(r_)) for r_ in here]
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
                if not keep.valued:     # a valued part merged with an unvalued one: its U leaves
                    for r_, u_ in us:
                        if u_ is not None:
                            self._uev(s.arrival_week, keep, "to_unvalued", u_, owner=r_.owner)
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
        sales_cost_here = (info.name, s.product) in self.m.sales_cost
        for row in self.m.node_cost.get((info.name, s.product), []):
            treat = POL.classify_node_cost(row["cost_type"])
            if row["basis"] == "revenue" and sales_cost_here:
                # G1 C3: the row is for PPC; vc_sales_cost_rule.csv books it at the sale (no issue)
                self.ppc_only_node_cost[(info.name, s.product, row["cost_type"])] += 1
                continue
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
