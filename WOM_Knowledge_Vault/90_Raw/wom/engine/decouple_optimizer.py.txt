"""
wom/engine/decouple_optimizer.py
=================================
Buffering Stock Positioning Optimizer (OutBound side)

Answers the question: "for this SKU's OutBound lane (supply_point -> DAD ->
... -> leaf_out), which single node should hold the buffering stock
(decoupling point) at the lowest total inventory-holding cost?"

Design
------
Candidate generation is a port of the v1r0m0 PySI reference implementation
(pysi/plan/engines.py: make_nodes_decouple_all / find_all_leaves /
find_depth), adapted to WOM's SCTree / PlanNode (.node_id / .children /
.parent). Starting from "every leaf_out is its own decouple point" (the
finest granularity -- VMI/consignment at each channel), the algorithm
progressively merges siblings up into their parent, one merge per
candidate, until reaching the node(s) directly below supply_point. This
produces roughly (number of nodes in the lane) candidates per SKU -- NOT
a full 2^N combinatorial explosion -- matching the natural assumption
that a lane holds exactly one buffering-stock point at a time.

Each candidate is evaluated by resetting the supply layer to a clean
demand-anchored state (copy_demand_to_supply) and running one Forward
Planning pass with that candidate set forced as the OutBound decouple
boundary (ForwardPlanner(..., decouple_node_ids=candidate)). The
Lot_ID-identity-matching engine (see forward_planner.py) means placing
the decouple boundary at ANY node now correctly produces real
psi4supply[w][I] buffer stock there, so the resulting total inventory
lots/cost is a meaningful, comparable metric across candidates.

Scope note: this module only searches the OutBound (leaf_out -> DAD ->
supply_point) lane. InBound (leaf_in -> MOM) buffer positioning is a
separate, analogous problem not covered here (see CLAUDE.md "未対応・
次回検討事項").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from wom.model.plan_node import S, CO, I, P, NODE_TYPE_SUPPLY_POINT
from wom.model.sc_tree   import SCTree
from wom.engine.plan_copy import copy_demand_to_supply
from wom.engine.forward_planner import ForwardPlanner


# ---------------------------------------------------------------------------
# 1. Candidate generation (port of PySI make_nodes_decouple_all)
# ---------------------------------------------------------------------------

def _find_depth(node) -> int:
    depth = 0
    n = node
    while n.parent is not None:
        depth += 1
        n = n.parent
    return depth


def _find_all_leaves(node, leaves: List[Tuple], depth: int = 0) -> None:
    if not node.children:
        leaves.append((node, depth))
    else:
        for child in node.children:
            _find_all_leaves(child, leaves, depth + 1)


def build_decouple_candidates(ot_root) -> List[List[str]]:
    """
    Port of PySI's make_nodes_decouple_all(), adapted to PlanNode.

    Returns a list of candidate decouple-node-ID sets, ordered from
    finest (index 0: every leaf_out individually) to coarsest (last
    index: the node(s) directly below supply_point). Each candidate is
    a List[node_id] suitable for ForwardPlanner(..., decouple_node_ids=...).

    supply_point itself is EXCLUDED as a merge target: it is a virtual
    OutBound/InBound bridge node (lt_wks=0, no physical location a real
    company would ever hold inventory at), so the coarsest candidate
    returned is "the node(s) directly below supply_point", never
    supply_point itself. Without this exclusion, supply_point tends to
    look spuriously "free" in the evaluation step -- see
    find_optimal_decouple_placement()'s service-level filtering for why.
    """
    leaves: List[Tuple] = []
    _find_all_leaves(ot_root, leaves)

    # Deepest-first, matching the original algorithm's merge order.
    pickup_list = [nd for nd, _depth in
                   sorted(leaves, key=lambda x: x[1], reverse=True)]

    nodes_decouple = [nd.node_id for nd in pickup_list]
    nodes_decouple_all: List[List[str]] = []

    while pickup_list:
        nodes_decouple_all.append(nodes_decouple.copy())

        current_node = pickup_list.pop(0)
        del nodes_decouple[0]

        parent_node = current_node.parent
        if parent_node is None:
            break

        depth = _find_depth(parent_node)
        inserted = False
        for idx, nd in enumerate(pickup_list):
            if _find_depth(nd) <= depth:
                pickup_list.insert(idx, parent_node)
                nodes_decouple.insert(idx, parent_node.node_id)
                inserted = True
                break
        if not inserted:
            pickup_list.append(parent_node)
            nodes_decouple.append(parent_node.node_id)

        # Siblings of current_node (other children of parent_node) are
        # absorbed into parent_node's slot -- remove them from the pool.
        for child in list(parent_node.children):
            if child in pickup_list:
                pickup_list.remove(child)
                nodes_decouple.remove(child.node_id)

    # Drop any candidate that includes supply_point (virtual bridge node --
    # never a valid real-world buffering-stock location). In a simple
    # single-chain lane this just removes the final ['supply_point'] entry;
    # in branched topologies it conservatively drops any mixed candidate
    # that would otherwise pick supply_point as one of the decouple points.
    all_nodes = {}
    def _index_all(n):
        all_nodes[n.node_id] = n
        for c in n.children:
            _index_all(c)
    _index_all(ot_root)
    all_nodes[ot_root.node_id] = ot_root

    nodes_decouple_all = [
        cand for cand in nodes_decouple_all
        if not any(all_nodes.get(nid) is not None
                   and all_nodes[nid].node_type == NODE_TYPE_SUPPLY_POINT
                   for nid in cand)
    ]

    return nodes_decouple_all


# ---------------------------------------------------------------------------
# 2. Cost lookup (node_cost_master.csv)
# ---------------------------------------------------------------------------

def load_unit_cost_lookup(node_cost_master_path: str, prod_nm: str) -> Dict[str, float]:
    """{node_name: unit_cost_per_lot} for one product, from node_cost_master.csv."""
    df = pd.read_csv(node_cost_master_path)
    df = df[df["sku_id"] == prod_nm]
    return dict(zip(df["node_name"], df["unit_cost_per_lot"]))


# ---------------------------------------------------------------------------
# 3. Evaluation
# ---------------------------------------------------------------------------

@dataclass
class DecoupleEvalResult:
    decouple_node_ids:      List[str]
    decouple_node_names:    List[str]
    total_inventory_lots:   int
    total_inventory_cost:   float
    total_shortfall_lots:   int
    per_node_inventory:     Dict[str, int] = field(default_factory=dict)

    def __str__(self) -> str:
        names = ", ".join(self.decouple_node_names)
        return (
            f"[{names}]  inv_lots={self.total_inventory_lots}  "
            f"inv_cost={self.total_inventory_cost:,.0f}  "
            f"shortfall={self.total_shortfall_lots}"
        )


def _reset_supply_layer(sc_tree: SCTree, prod_nm: str, n_weeks: int) -> None:
    """
    Clear psi4supply[S/CO/I/P] for every node of prod_nm, then re-copy
    psi4demand -> psi4supply. Required between successive candidate runs
    because CO is only ever appended to (never cleared) by the identity-
    matching ForwardPlanner -- without this reset, CO would leak across
    candidates and corrupt the comparison.
    """
    for node in sc_tree.iter_all_nodes(prod_nm):
        for w in range(n_weeks):
            node.psi4supply[w][S]  = []
            node.psi4supply[w][CO] = []
            node.psi4supply[w][I]  = []
            node.psi4supply[w][P]  = []
    copy_demand_to_supply(sc_tree, prod_nm)


def evaluate_decouple_placement(
    sc_tree: SCTree,
    prod_nm: str,
    decouple_node_ids: List[str],
    unit_cost_lookup: Optional[Dict[str, float]] = None,
) -> DecoupleEvalResult:
    """
    Run one clean Forward Planning pass with `decouple_node_ids` forced as
    the OutBound decouple set, and measure total inventory (lots and, if
    unit_cost_lookup given, currency-equivalent cost) plus total shortfall.
    """
    n_weeks = sc_tree.num_weeks()
    _reset_supply_layer(sc_tree, prod_nm, n_weeks)

    fp     = ForwardPlanner(sc_tree, decouple_node_ids=set(decouple_node_ids))
    result = fp.run(prod_nm)

    per_node_inventory: Dict[str, int] = {}
    total_inventory_lots = 0
    total_inventory_cost = 0.0
    decouple_names: List[str] = []

    for node in sc_tree.iter_all_nodes(prod_nm):
        if node.node_id in decouple_node_ids:
            decouple_names.append(node.node_name)
        inv_lots = sum(len(node.psi4supply[w][I]) for w in range(n_weeks))
        if inv_lots:
            per_node_inventory[node.node_name] = inv_lots
            total_inventory_lots += inv_lots
            if unit_cost_lookup:
                total_inventory_cost += inv_lots * unit_cost_lookup.get(node.node_name, 0.0)

    return DecoupleEvalResult(
        decouple_node_ids=list(decouple_node_ids),
        decouple_node_names=decouple_names,
        total_inventory_lots=total_inventory_lots,
        total_inventory_cost=total_inventory_cost,
        total_shortfall_lots=result.co_generated,
        per_node_inventory=per_node_inventory,
    )


def find_optimal_decouple_placement(
    sc_tree: SCTree,
    prod_nm: str,
    node_cost_master_path: Optional[str] = None,
    max_shortfall_ratio: float = 1.10,
) -> Dict[str, object]:
    """
    Enumerate all candidate OutBound decouple placements for one SKU
    (via build_decouple_candidates), evaluate each, and select the
    cost-optimal one under a SERVICE-LEVEL CONSTRAINT.

    Why a constraint, not pure cost minimization
    ---------------------------------------------
    Placing the decouple point far upstream (near supply_point) forces
    every node below it into PULL mode (P is overridden to match demand),
    which trivially reports zero inventory AND zero visible shortfall at
    those nodes -- any real supply/demand mismatch is dumped entirely
    onto the decouple node's own CO. A naive "minimize total inventory
    cost" ranking is fooled by this: it rewards candidates that hide
    shortfall rather than ones that actually serve demand well.

    So the real question is: "holding service level roughly constant,
    which placement minimizes inventory cost?" -- not "which placement
    has the least reported inventory?"

    Algorithm
    ---------
    1. Evaluate every candidate (inventory cost/lots + total_shortfall_lots).
    2. min_shortfall = min(shortfall across all candidates).
    3. eligible = candidates whose shortfall <= min_shortfall * max_shortfall_ratio
       (default 10% tolerance above the best-observed shortfall).
    4. Rank `eligible` by inventory cost (or lot count) ascending; ranked[0]
       is "best". `ranked` (full, unconstrained) is still returned for
       transparency/inspection.
    """
    ot_root    = sc_tree.get_ot_root(prod_nm)
    candidates = build_decouple_candidates(ot_root)

    unit_cost_lookup = None
    if node_cost_master_path:
        unit_cost_lookup = load_unit_cost_lookup(node_cost_master_path, prod_nm)

    evaluations = [
        evaluate_decouple_placement(sc_tree, prod_nm, cand, unit_cost_lookup)
        for cand in candidates
    ]

    cost_key = ((lambda e: e.total_inventory_cost) if unit_cost_lookup
                else (lambda e: e.total_inventory_lots))
    ranked = sorted(evaluations, key=cost_key)

    if evaluations:
        min_shortfall = min(e.total_shortfall_lots for e in evaluations)
        shortfall_cap = min_shortfall * max_shortfall_ratio
        eligible = sorted(
            (e for e in evaluations if e.total_shortfall_lots <= shortfall_cap),
            key=cost_key,
        )
    else:
        min_shortfall, eligible = 0, []

    best = eligible[0] if eligible else (ranked[0] if ranked else None)

    return {
        "product":              prod_nm,
        "candidates_evaluated": len(evaluations),
        "ranked":               ranked,
        "eligible":             eligible,
        "min_shortfall":        min_shortfall,
        "max_shortfall_ratio":  max_shortfall_ratio,
        "best":                 best,
        "cost_basis":           "unit_cost_per_lot (node_cost_master.csv)" if unit_cost_lookup
                                 else "lot count (no cost data supplied)",
    }
