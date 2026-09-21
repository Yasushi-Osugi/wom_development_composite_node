"""
wom/engine/plan_copy.py
=======================
WOM Planning Step 5 — Demand Layer → Supply Layer Copy

After Backward Planning fills psi4demand with the ideal demand allocation,
this step copies the demand plan into psi4supply as the supply commitment
baseline before Forward Planning applies capacity constraints.

Role of each PSI layer
──────────────────────
psi4demand[w][bucket]
    What each node NEEDS according to customer demand.
    Set by: Step 3 (leaf S assignment) + Step 4 (backward propagation).
    Never modified by Forward Planning — it is the demand truth.

psi4supply[w][bucket]
    What each node WILL DO according to the supply plan.
    Initialised here (Step 5) as a copy of psi4demand.
    Modified by: Step 6 Forward Planning (capacity sealing, PUSH/PULL,
                 carry-over generation).

Copy semantics
──────────────
Only S and P buckets are copied (I and CO are left empty):
    psi4supply[w][S] ← list(psi4demand[w][S])   supply ships these lots
    psi4supply[w][P] ← list(psi4demand[w][P])   supply receives these lots
    psi4supply[w][I]  = []    forward planner calculates rolling inventory
    psi4supply[w][CO] = []    forward planner generates CO when I+P < S

Each lot list is deep-copied (new list object) so that later modifications
to psi4supply never alias back into psi4demand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from wom.model.plan_node import PlanNode, S, CO, I, P, PSI_BUCKETS
from wom.model.sc_tree   import SCTree


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PlanCopyResult:
    """Summary of one demand→supply copy pass."""

    prod_nm:        str
    nodes_copied:   int = 0    # number of PlanNodes processed
    lots_s_copied:  int = 0    # total S lot-IDs copied across all weeks
    lots_p_copied:  int = 0    # total P lot-IDs copied across all weeks
    weeks_touched:  int = 0    # (node, week) pairs where any lot was copied

    def __str__(self) -> str:
        return (
            f"PlanCopyResult[{self.prod_nm}]  "
            f"nodes={self.nodes_copied}  "
            f"S_lots={self.lots_s_copied}  "
            f"P_lots={self.lots_p_copied}  "
            f"weeks_touched={self.weeks_touched}"
        )


# ---------------------------------------------------------------------------
# Core copy function (single node)
# ---------------------------------------------------------------------------

def _copy_node(node: PlanNode, n_weeks: int, result: PlanCopyResult) -> None:
    """
    Copy psi4demand[w][S] and psi4demand[w][P] into psi4supply for one node.
    I and CO buckets in psi4supply are left empty.
    """
    for w in range(n_weeks):
        s_lots = node.psi4demand[w][S]
        p_lots = node.psi4demand[w][P]

        if s_lots or p_lots:
            node.psi4supply[w][S] = list(s_lots)   # deep copy
            node.psi4supply[w][P] = list(p_lots)   # deep copy
            # I and CO stay as empty lists (already initialised by init_psi)

            result.lots_s_copied  += len(s_lots)
            result.lots_p_copied  += len(p_lots)
            result.weeks_touched  += 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def copy_demand_to_supply(
    sc_tree: SCTree,
    prod_nm: str,
) -> PlanCopyResult:
    """
    Copy the demand plan (psi4demand) to the supply layer (psi4supply)
    for every PlanNode of one product.

    Parameters
    ----------
    sc_tree:
        SCTree after backward planning has completed.
    prod_nm:
        Product name to process.

    Returns
    -------
    PlanCopyResult
    """
    result  = PlanCopyResult(prod_nm=prod_nm)
    n_weeks = sc_tree.num_weeks()

    for node in sc_tree.iter_all_nodes(prod_nm):
        _copy_node(node, n_weeks, result)
        result.nodes_copied += 1

    return result


def copy_demand_to_supply_all(sc_tree: SCTree) -> Dict[str, PlanCopyResult]:
    """
    Run copy_demand_to_supply for every product in the SCTree.

    Returns
    -------
    dict  product_name → PlanCopyResult
    """
    return {
        prod_nm: copy_demand_to_supply(sc_tree, prod_nm)
        for prod_nm in sc_tree.products
    }


# ---------------------------------------------------------------------------
# Verification helper
# ---------------------------------------------------------------------------

def verify_copy_integrity(
    sc_tree: SCTree,
    prod_nm: str,
) -> List[str]:
    """
    Sanity-check that psi4supply matches psi4demand for S and P buckets,
    and that I / CO in psi4supply are still empty.

    Returns a list of violation strings (empty = all OK).
    """
    violations: List[str] = []
    n_weeks = sc_tree.num_weeks()

    for node in sc_tree.iter_all_nodes(prod_nm):
        for w in range(n_weeks):
            wk = node.week_labels[w] if node.week_labels else str(w)

            # S must match
            d_s = node.psi4demand[w][S]
            sp_s = node.psi4supply[w][S]
            if d_s != sp_s:
                violations.append(
                    f"{node.node_id} {wk} S: "
                    f"demand={len(d_s)} supply={len(sp_s)}"
                )

            # P must match
            d_p = node.psi4demand[w][P]
            sp_p = node.psi4supply[w][P]
            if d_p != sp_p:
                violations.append(
                    f"{node.node_id} {wk} P: "
                    f"demand={len(d_p)} supply={len(sp_p)}"
                )

            # I in supply must be empty (forward planner fills it)
            if node.psi4supply[w][I]:
                violations.append(
                    f"{node.node_id} {wk} I in supply should be empty "
                    f"before forward planning"
                )

            # CO in supply must be empty (forward planner generates CO)
            if node.psi4supply[w][CO]:
                violations.append(
                    f"{node.node_id} {wk} CO in supply should be empty "
                    f"before forward planning"
                )

            # Aliasing check: S lists must be different objects
            if d_s and sp_s is d_s:
                violations.append(
                    f"{node.node_id} {wk} S: psi4supply aliases psi4demand "
                    f"(should be a copy)"
                )

            # Aliasing check: P lists must be different objects
            if d_p and sp_p is d_p:
                violations.append(
                    f"{node.node_id} {wk} P: psi4supply aliases psi4demand "
                    f"(should be a copy)"
                )

    return violations
