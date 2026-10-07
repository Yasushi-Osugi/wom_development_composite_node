"""Serial-tree adapter between a WOM plan tree and the upper capacity solver.

RequestLetter_GenerationLine_UpperLayer §4 (production version of Astra's
``smartx_trial.SmartxAdapter``; the footprint logic is the same, the data now
comes from the live plan tree after Backward instead of exported CSV files).

What it does, per product:

* requests  -- one per (market leaf, market week): the ORIGINAL market lots
  (``leaf.psi4demand[w][S]``, Lot_IDs and request weeks are never changed).
* options   -- for each request, every internal plan week from
  ``due - max_advance`` to ``due`` whose footprint reaches the market by the
  request week. A footprint lists the (resource, week) slots one lot uses:
  the processing (P) week at every capacity-holding node.
* capacities -- ``processing_limit(w)`` of every node except push decoupling
  nodes (their receipt is not sealed by the engine). None = not set (no
  ceiling), 0 = zero capacity (RequestLetter_CapacityZeroBlank).
* apply_positions -- after the solver, rewrites the internal demand positions
  (``psi4demand`` of every non-leaf node) so that the engine plans each lot at
  its assigned week. Market S and IDs are untouched; unallocated lots are not
  placed internally and stay as market backlog (listed, never dropped).

Supported trees: serial inbound (one leaf_in, no branching, bom_qty 1). Other
trees raise ``UnsupportedTreeError`` (no silent fallback).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .solver import Option, Problem, Request, validate_solution


class UnsupportedTreeError(ValueError):
    """The product's tree is outside what the serial adapter can represent."""


def push_modes(tree, product: str, push_nodes: Iterable[str]) -> Dict[str, str]:
    """plan_mode per node_id, as PushProductionPlanner.setup_all will set it.

    The upper layer runs right after Backward, before the push setup, so the
    modes are derived here with the same rule (wom/engine/push_pull.py): the
    decoupling node is "push", its subtree and its ancestors are "push_sub",
    every other node keeps its current mode.
    """
    nodes = list(tree.iter_all_nodes(product))
    modes = {n.node_id: n.plan_mode for n in nodes}
    for name in push_nodes:
        dec = next((n for n in nodes if n.node_name == name), None)
        if dec is None:
            raise UnsupportedTreeError(f"{product}: push node {name!r} is not in the tree")
        modes[dec.node_id] = "push"
        for n in dec.walk_preorder():
            if n is not dec:
                modes[n.node_id] = "push_sub"
        up = dec.parent
        while up is not None:
            modes[up.node_id] = "push_sub"
            up = up.parent
    return modes


class SerialLineAdapter:
    """Time/resource footprints of one or more serial product trees.

    ``nodes``  : node_id -> dict(product, node_id, node_name, node_type, side,
                 plan_mode, parent_id, lt_wks, transit_lt_wks, ss_wks, bom_qty)
    ``state``  : (node_id, week_index) -> dict(processing_limit: float|None,
                 is_open: bool)
    ``weeks``  : week labels of the plan horizon
    ``push_leads`` : node_id -> Mode 4 push_lead_time_weeks
    """

    def __init__(self, nodes: dict, state: dict, weeks: List[str], *, push_leads: dict):
        self.nodes = dict(nodes)
        self.state = dict(state)
        self.weeks = list(weeks)
        self.widx = {w: i for i, w in enumerate(self.weeks)}
        self.push_leads = dict(push_leads)
        self.products = sorted({r["product"] for r in self.nodes.values()})
        self.by_product = {p: [n for n, r in self.nodes.items() if r["product"] == p]
                           for p in self.products}
        n_w = len(self.weeks)
        self.closed = {n: {w for w in range(n_w) if not self.state[n, w]["is_open"]}
                       for n in self.nodes}
        self.children = defaultdict(list)
        for nid, r in self.nodes.items():
            if r["parent_id"]:
                self.children[r["parent_id"]].append(nid)
        for p in self.products:
            ins = [n for n in self.by_product[p] if self.nodes[n]["side"] == "inbound"]
            if any(len(self.children[n]) > 1 for n in ins):
                raise UnsupportedTreeError(f"{p}: branched inbound needs a BOM/Kitting adapter")
            if sum(self.nodes[n]["node_type"] == "leaf_in" for n in ins) != 1:
                raise UnsupportedTreeError(f"{p}: exactly one inbound source (leaf_in) required")
            if any(int(self.nodes[n]["bom_qty"]) != 1 for n in ins):
                raise UnsupportedTreeError(f"{p}: physical-unit BOM conversion (bom_qty != 1) must be explicit")
        self.capacities: Dict[tuple, Optional[float]] = {}
        self.unset_nodes: List[str] = []
        for nid, r in self.nodes.items():
            if r["plan_mode"] == "push":
                continue   # receipt is not sealed in the current engine
            for w in range(n_w):
                self.capacities[nid, w] = self.state[nid, w]["processing_limit"]
            if all(self.capacities[nid, w] is None for w in range(n_w)):
                self.unset_nodes.append(nid)
            if r["side"] == "inbound" and not r["parent_id"]:
                # Backward also clips the root S at that week. This envelope is
                # the SAME machine, not extra capacity.
                for w in range(n_w):
                    self.capacities["backward_root:" + nid, w] = self.capacities[nid, w]
        self.lots: Dict[str, List[str]] = {}

    # ── construction from the live plan tree ─────────────────────────────
    @classmethod
    def from_tree(cls, tree, products: Iterable[str], *, push_leads_by_name: Optional[dict] = None):
        """Read node attributes, open weeks and processing limits from the tree.

        ``push_leads_by_name``: {(product, node_name): push_lead_time_weeks}
        for Mode 4 decoupling nodes (from push_config.csv).
        """
        push_leads_by_name = dict(push_leads_by_name or {})
        weeks = list(tree.week_labels)
        nodes, state, leads = {}, {}, {}
        for prod in products:
            modes = push_modes(tree, prod, [n for (p, n) in push_leads_by_name if p == prod])
            for nd in tree.iter_all_nodes(prod):
                nid = nd.node_id
                nodes[nid] = {"product": prod, "node_id": nid, "node_name": nd.node_name,
                              "node_type": nd.node_type, "side": nd.side,
                              "plan_mode": modes[nid],
                              "parent_id": nd.parent.node_id if nd.parent else "",
                              "lt_wks": int(nd.lt_wks), "transit_lt_wks": int(nd.transit_lt_wks or 0),
                              "ss_wks": int(nd.ss_wks), "bom_qty": int(nd.bom_qty)}
                for w in range(len(weeks)):
                    state[nid, w] = {"processing_limit": nd.processing_limit(w),
                                     "is_open": bool(nd.is_open(w))}
                if (prod, nd.node_name) in push_leads_by_name:
                    leads[nid] = int(push_leads_by_name[prod, nd.node_name])
        return cls(nodes, state, weeks, push_leads=leads)

    # ── footprint (Astra's prototype logic, unchanged) ──────────────────
    def _back(self, w, lt, nid):
        if not self.closed[nid]:
            return w - lt
        left = lt
        v = w - 1
        while left > 0:
            if v not in self.closed[nid]:
                left -= 1
            v -= 1
        return v + 1

    def _open(self, nid, w):
        return next((x for x in range(max(w, 0), len(self.weeks)) if x not in self.closed[nid]),
                    len(self.weeks))

    def root_of(self, product, side):
        return next(n for n in self.by_product[product]
                    if self.nodes[n]["side"] == side and not self.nodes[n]["parent_id"])

    def footprint(self, product, market, plan_week, market_due=None):
        """Internal demand positions and processing weeks of one lot.

        Physical capacity is reserved on the processing (P) week, not on the
        planned S. ``market`` is the leaf_out node_name.
        """
        ids = self.by_product[product]
        leaf = next(n for n in ids if self.nodes[n]["node_name"] == market)
        due = {leaf: plan_week}
        n = leaf
        while self.nodes[n]["parent_id"]:
            parent = self.nodes[n]["parent_id"]
            r = self.nodes[n]
            due[parent] = self._back(due[n], int(r["lt_wks"]) + int(r["ss_wks"]), parent)
            n = parent
        ot_root = n
        root = self.root_of(product, "inbound")
        due[root] = due[ot_root]
        n = root
        chain = [n]
        while self.children[n]:
            child = self.children[n][0]
            r = self.nodes[child]
            due[child] = self._back(due[n], int(r["lt_wks"]) + int(r["ss_wks"]), child)
            n = child
            chain.append(n)
        if min(due.values()) < 0:
            return None
        source = chain[-1]
        pushed = next((n for n in chain if self.nodes[n]["plan_mode"] == "push"), None)
        source_p = due[source]
        if pushed:
            if pushed not in self.push_leads:
                raise UnsupportedTreeError("Missing Mode 4 lead-time definition for " + pushed)
            source_p = due[pushed] - self.push_leads[pushed]
            if source_p < 0:
                return None
            if source_p in self.closed[source]:
                prev = next((w for w in range(source_p - 1, -1, -1) if w not in self.closed[source]), None)
                source_p = prev if prev is not None else self._open(source, source_p + 1)
        actual, processed, uses = {}, {}, []
        p_w = source_p
        for nid in reversed(chain):
            r = self.nodes[nid]
            if nid != source:
                child = self.children[nid][0]
                cr = self.nodes[child]
                # Push-buffer handoff uses its lt; normal handoff uses transit.
                transit = int(cr["lt_wks"]) if cr["plan_mode"] == "push" else int(cr["transit_lt_wks"])
                if transit <= 0:
                    transit = int(cr["lt_wks"])
                p_w = actual[child] + transit
            if r["plan_mode"] == "push":
                processed[nid] = p_w
                actual[nid] = self._open(nid, max(p_w, due[nid]))
            else:
                processed[nid] = self._open(nid, p_w)
                uses.append((nid, processed[nid], 1.))
                actual[nid] = (processed[nid] if r["plan_mode"] == "push_sub"
                               else self._open(nid, max(processed[nid], due[nid])))
            if not r["parent_id"]:
                uses.append(("backward_root:" + nid, due[nid], 1.))
        actual[ot_root] = max(actual[root], due[ot_root])
        processed[ot_root] = actual[root]
        uses.append((ot_root, processed[ot_root], 1.))
        path = []
        n = leaf
        while n != ot_root:
            path.append(n)
            n = self.nodes[n]["parent_id"]
        for nid in reversed(path):
            r = self.nodes[nid]
            parent = r["parent_id"]
            processed[nid] = self._open(nid, actual[parent] + int(r["lt_wks"]))
            requested = market_due if nid == leaf and market_due is not None else due[nid]
            actual[nid] = self._open(nid, max(processed[nid], requested))
            uses.append((nid, processed[nid], 1.))
        if max(max(due.values()), max(processed.values()), max(actual.values())) >= len(self.weeks):
            return None
        return {"positions": due, "processed": processed, "actual": actual,
                "uses": tuple(uses), "market_week": actual[leaf]}

    # ── the problem ──────────────────────────────────────────────────────
    def problem_from_tree(self, tree, product: str, max_advance: int) -> Problem:
        """Requests from the market leaves' original lots; options up to max_advance."""
        if max_advance < 0:
            raise ValueError("max_advance must be >= 0")
        requests, options = [], []
        no_option = []
        for nd in tree.iter_all_nodes(product):
            if nd.node_type != "leaf_out":
                continue
            for dw in range(len(self.weeks)):
                lots = list(nd.psi4demand[dw][0])          # S bucket
                if not lots:
                    continue
                key = f"{product}|{nd.node_name}|{self.weeks[dw]}"
                self.lots[key] = lots
                requests.append(Request(key, product, nd.node_name, dw, len(lots)))
                n_opt = 0
                for pw in range(max(0, dw - max_advance), dw + 1):
                    fp = self.footprint(product, nd.node_name, pw)
                    if fp is None or fp["market_week"] > dw:
                        continue
                    options.append(Option(f"{key}@{pw}", key, pw, fp["uses"]))
                    n_opt += 1
                if not n_opt:
                    no_option.append(key)
        caps = {k: v for k, v in self.capacities.items() if self.nodes[k[0].split("backward_root:")[-1]]["product"] == product}
        return Problem(requests, options, caps, metadata={
            "adapter": "serial_tree_v1", "product": product, "max_advance_weeks": max_advance,
            "requests_without_option": no_option,
            "unset_capacity_nodes": [self.nodes[n]["node_name"] for n in self.unset_nodes
                                     if self.nodes[n]["product"] == product],
            "resource_unit": "one market lot (cpu_size=1, bom_qty=1)"})

    # ── expansion to the original lots ──────────────────────────────────
    def expand(self, problem: Problem, solution) -> List[dict]:
        """Assign the ORIGINAL lots of each request to plan weeks; never mint IDs.

        Within a request the lots keep their order; the latest plan week is
        taken first (as in the prototype), the remainder is "unallocated".
        """
        validate_solution(problem, solution)
        opts = {o.key: o for o in problem.options}
        grouped = defaultdict(list)
        for a in solution.allocations:
            grouped[opts[a.option_key].request_key].append(a)
        rows = []
        for r in problem.requests:
            lots = iter(self.lots[r.key])
            for a in sorted(grouped[r.key], key=lambda x: (-opts[x.option_key].plan_week, x.option_key)):
                o = opts[a.option_key]
                for _ in range(a.quantity):
                    rows.append({"lot_id": next(lots), "product": r.product, "market": r.market,
                                 "due_index": r.due_week, "due_week": self.weeks[r.due_week],
                                 "plan_index": o.plan_week, "plan_week": self.weeks[o.plan_week],
                                 "status": "assigned"})
            for lot in lots:
                rows.append({"lot_id": lot, "product": r.product, "market": r.market,
                             "due_index": r.due_week, "due_week": self.weeks[r.due_week],
                             "plan_index": "", "plan_week": "", "status": "unallocated"})
        return rows

    def apply_positions(self, tree, product: str, assignments: List[dict]) -> int:
        """Rewrite the internal demand positions after Backward; return lots placed.

        Market S and Lot_IDs are untouched. Capacities, modes and Forward are
        not changed -- Forward still checks the offered schedule on its own.
        """
        from wom.model.plan_node import S, P
        by_id = {n.node_id: n for n in tree.iter_all_nodes(product)}
        for nd in by_id.values():
            if nd.node_type == "leaf_out":
                continue
            for w in range(len(self.weeks)):
                nd.psi4demand[w] = [[], [], [], []]
        placed = 0
        for r in assignments:
            if r["product"] != product or r["status"] != "assigned":
                continue
            fp = self.footprint(product, r["market"], int(r["plan_index"]))
            if fp is None:
                raise RuntimeError(f"Invalid allocated footprint for {r['lot_id']}")
            for nid, w in fp["positions"].items():
                nd = by_id[nid]
                if nd.node_type == "leaf_out":
                    continue
                nd.psi4demand[w][S].append(r["lot_id"])
                nd.psi4demand[w][P].append(r["lot_id"])
            placed += 1
        return placed
