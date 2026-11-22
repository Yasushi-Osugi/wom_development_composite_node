# -*- coding: utf-8 -*-
"""
tests/test_shelf_life_row_order.py — 年齢の検査が木の行の順に依らない（RequestLetter_M6_RowOrder_Stage3 §2）

同じ所（supply point）から同じ週に兄弟の市場へ出る納品に、古い札（製造週）を渡す順は
（行き先のノード名の文字の順 → Lot_ID の順）。出荷の記録の並びと、木の順（rank）を入れ替えても、
納品ごとの年齢が同じ。
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wom.valuechain.records import Shipment
from tools.shelf_life_check import K_CONSUMER, K_HANDOFF, K_OUTBOUND, compute_fifo

P = "SKU"
WEEKS = [f"2027-W{i:02d}" for i in range(1, 7)]


def _s(i, lot, node, week, kind, to, arrival=None):
    return Shipment(ship_id=f"s{i}", product=P, lot_id=lot, node=node, node_id=node, week=week, seq=i,
                    kind=kind, phys_from=node, to=to, edge="", arrival_week=arrival,
                    arrival_in_horizon=arrival is not None, units=1.0, item="finished")


def _shipments():
    return [
        # production: one lot in week 0, one in week 1 (both into the supply point)
        _s(1, f"{P}:MkB:2027-W04:00001", "MOM", 0, K_HANDOFF, "SP", 0),
        _s(2, f"{P}:MkA:2027-W04:00001", "MOM", 1, K_HANDOFF, "SP", 1),
        # week 2: the supply point ships one lot to each market (siblings)
        _s(3, f"{P}:MkB:2027-W04:00001", "SP", 2, K_OUTBOUND, "Mk_B", 3),
        _s(4, f"{P}:MkA:2027-W04:00001", "SP", 2, K_OUTBOUND, "Mk_A", 3),
        # week 3: each market sells
        _s(5, f"{P}:MkB:2027-W04:00001", "Mk_B", 3, K_CONSUMER, "CONSUMER:Mk_B"),
        _s(6, f"{P}:MkA:2027-W04:00001", "Mk_A", 3, K_CONSUMER, "CONSUMER:Mk_A"),
    ]


def _ages(shipments, ranks):
    res = compute_fifo(shipments, ranks, WEEKS)
    return sorted((r["channel"], r["lot_id"], r["fifo_age"], r["manufacture_week"]) for r in res["deliveries"])


def test_sibling_exits_do_not_depend_on_row_order():
    ranks_a = {(P, "SP"): 0, (P, "Mk_A"): 1, (P, "Mk_B"): 2}
    ranks_b = {(P, "SP"): 0, (P, "Mk_B"): 1, (P, "Mk_A"): 2}
    a = _ages(_shipments(), ranks_a)
    b = _ages(_shipments()[::-1], ranks_b)
    c = _ages(_shipments()[::-1], ranks_a)
    assert a == b == c
    # the oldest tag (made in week 0) goes to the receiver first in name order (Mk_A)
    assert a == [("Mk_A", f"{P}:MkA:2027-W04:00001", 3, 0), ("Mk_B", f"{P}:MkB:2027-W04:00001", 2, 1)]
