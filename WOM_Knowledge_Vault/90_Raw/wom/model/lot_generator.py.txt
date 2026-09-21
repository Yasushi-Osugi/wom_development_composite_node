"""
wom/model/lot_generator.py
==========================
WOM Planning Layer — Lot ID generation and leaf_out demand assignment.

Lot ID format:
    "{sku_id}:{region}:{week}:{seq:05d}"
    e.g.  "SKU-A:JP:2024-W01:00001"

    Parsing back:  lot_id.split(":")  →  [sku_id, region, week, seq]
    (sku_id and region may contain hyphens but not colons)

Step 3 of the WOM planning engine:
    For every (sku_id, region, week) in the demand forecast,
    generate cpu_size-chunked lot IDs and assign them to
    the corresponding leaf_out node's psi4demand[week_idx][S].
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

import pandas as pd

from wom.model.plan_node import PlanNode, S, NODE_TYPE_LEAF_OUT
from wom.model.sc_tree   import SCTree
from wom.data.schema     import Cols


# ---------------------------------------------------------------------------
# Lot ID Generator
# ---------------------------------------------------------------------------

class LotIDGenerator:
    """
    Stateful counter that mints unique lot IDs for one planning run.

    Lot ID format: "{sku_id}:{region}:{week}:{seq:05d}"

    The counter is per-(sku_id, region, week) so that sequences restart
    at 00001 for each demand bucket — making IDs short and readable.
    Across the whole run no two IDs are ever identical.
    """

    def __init__(self) -> None:
        # (sku_id, region, week) → next sequence number
        self._counters: Dict[Tuple[str, str, str], int] = {}

    def generate(
        self,
        sku_id:  str,
        region:  str,
        week:    str,
        count:   int,
    ) -> List[str]:
        """
        Mint `count` new lot IDs for (sku_id, region, week).

        Parameters
        ----------
        sku_id, region, week:
            Demand dimensions that become the lot ID prefix.
        count:
            Number of lot IDs to generate (>= 1).

        Returns
        -------
        list of str
            Newly minted lot IDs, length == count.
        """
        if count <= 0:
            return []
        key = (sku_id, region, week)
        seq = self._counters.get(key, 1)
        ids = [
            f"{sku_id}:{region}:{week}:{seq + i:05d}"
            for i in range(count)
        ]
        self._counters[key] = seq + count
        return ids

    def reset(self) -> None:
        """Clear all counters (call between planning runs)."""
        self._counters.clear()

    # -- Lot ID parsing -----------------------------------------------------

    @staticmethod
    def parse(lot_id: str) -> Tuple[str, str, str, int]:
        """
        Parse a lot ID back into (sku_id, region, week, seq).

        Raises ValueError if the format is invalid.
        """
        parts = lot_id.rsplit(":", 1)         # split off seq at rightmost ":"
        if len(parts) != 2:
            raise ValueError(f"Cannot parse lot_id: {lot_id!r}")
        prefix, seq_str = parts
        left = prefix.rsplit(":", 1)
        if len(left) != 2:
            raise ValueError(f"Cannot parse lot_id: {lot_id!r}")
        sku_region, week = left
        # sku_region = "{sku_id}:{region}"
        sr = sku_region.split(":", 1)
        if len(sr) != 2:
            raise ValueError(f"Cannot parse lot_id: {lot_id!r}")
        sku_id, region = sr
        return sku_id, region, week, int(seq_str)


# ---------------------------------------------------------------------------
# Assignment result
# ---------------------------------------------------------------------------

@dataclass
class LotAssignmentResult:
    """Summary of a demand lot assignment pass."""
    total_lots_assigned: int = 0
    # (sku_id, region, week) → list of lot IDs assigned
    lot_registry: Dict[Tuple[str, str, str], List[str]] = field(
        default_factory=dict
    )
    # nodes that had no matching leaf_out in the SCTree
    unmatched_keys: List[Tuple[str, str, str]] = field(default_factory=list)

    def get_lots(
        self, sku_id: str, region: str, week: str
    ) -> List[str]:
        return self.lot_registry.get((sku_id, region, week), [])


# ---------------------------------------------------------------------------
# Leaf-node lookup helpers
# ---------------------------------------------------------------------------

def _build_leaf_index(sc_tree: SCTree) -> Dict[Tuple[str, str], PlanNode]:
    """
    Build a dict  (sku_id, region) → leaf_out PlanNode
    by walking all OutBound trees and collecting leaf_out nodes.

    Leaf_out node_id convention from build_demo_sc_tree:
        "OUT:Sales:{region}:{sku_id}"
    This helper is convention-agnostic — it uses node_type and
    parses the stored `product` + searches all leaves.
    """
    index: Dict[Tuple[str, str], PlanNode] = {}
    for prod_nm in sc_tree.products:
        for node in sc_tree.get_ot_root(prod_nm).walk_preorder():
            if node.node_type == NODE_TYPE_LEAF_OUT:
                region = _infer_region_from_node(node)
                if region:
                    index[(node.product, region)] = node
    return index


def _infer_region_from_node(node: PlanNode) -> Optional[str]:
    """
    Extract region from a leaf_out PlanNode.

    Convention: node_id = "OUT:Sales:{region}:{sku_id}"
    Falls back to node_name parsing if needed.
    Returns None if region cannot be determined.
    """
    parts = node.node_id.split(":")
    # "OUT:Sales:{region}:{sku_id}"  →  4 parts
    if len(parts) >= 4 and parts[0] == "OUT":
        return parts[2]
    # Fallback: try node_name "Sales {region} [{sku_id}]"
    name = node.node_name
    if name.startswith("Sales "):
        tail = name[6:]              # e.g. "JP [SKU-A]"
        region = tail.split(" ")[0]
        return region
    return None


# ---------------------------------------------------------------------------
# Main assignment function
# ---------------------------------------------------------------------------

def assign_demand_lots_from_df(
    sc_tree:   SCTree,
    demand_df: "pd.DataFrame",
    cpu_size:  int = 1,
    lot_gen:   Optional[LotIDGenerator] = None,
) -> LotAssignmentResult:
    """
    Convert demand quantities into lot-ID lists on leaf_out nodes.

    For each (sku_id, region, week, qty) row in demand_df:
        lot_count = ceil(qty / cpu_size)      -- quantity → lot count
        lot_ids   = lot_gen.generate(...)     -- mint IDs
        leaf_out.add_lot_demand(week_idx, S, lot_id)  for each id

    Parameters
    ----------
    sc_tree:
        SCTree with init_psi() already called.
    demand_df:
        DataFrame with columns: sku_id, region, week, quantity.
        (Same schema as wom.data.loader.load_demand_forecast output.)
    cpu_size:
        Common Planning Unit size.  qty units per lot.
        Default 1 → each unit = one lot ID.
    lot_gen:
        Optional existing LotIDGenerator (for shared counters across
        multiple calls). A fresh one is created if None.

    Returns
    -------
    LotAssignmentResult
    """
    if lot_gen is None:
        lot_gen = LotIDGenerator()

    # Build leaf lookup index
    leaf_index = _build_leaf_index(sc_tree)

    result = LotAssignmentResult()

    for _, row in demand_df.iterrows():
        sku_id = str(row[Cols.SKU_ID]).strip()
        region = str(row[Cols.REGION]).strip()
        week   = str(row[Cols.WEEK]).strip()
        qty    = float(row[Cols.DEMAND_QTY])

        if qty <= 0:
            continue

        # Resolve week index
        try:
            w_idx = sc_tree.week_idx(week)
        except ValueError:
            continue    # week outside planning horizon — skip

        # Resolve leaf_out node
        leaf = leaf_index.get((sku_id, region))
        if leaf is None:
            key = (sku_id, region, week)
            if key not in result.unmatched_keys:
                result.unmatched_keys.append(key)
            continue

        # Generate lots
        lot_count = max(1, math.ceil(qty / cpu_size))
        lot_ids   = lot_gen.generate(sku_id, region, week, lot_count)

        # Assign to leaf S bucket
        for lot_id in lot_ids:
            leaf.add_lot_demand(w_idx, S, lot_id)

        # Record in registry
        key = (sku_id, region, week)
        if key not in result.lot_registry:
            result.lot_registry[key] = []
        result.lot_registry[key].extend(lot_ids)
        result.total_lots_assigned += lot_count

    return result


def assign_demand_lots_from_dict(
    sc_tree:      SCTree,
    demand_dict:  Dict[Tuple[str, str, str], float],
    cpu_size:     int = 1,
    lot_gen:      Optional[LotIDGenerator] = None,
) -> LotAssignmentResult:
    """
    Dict-based variant of assign_demand_lots_from_df.

    Parameters
    ----------
    demand_dict:
        { (sku_id, region, week_label): qty_float }
        e.g. { ("SKU-A", "JP", "2024-W01"): 10.0 }
    """
    rows = [
        {
            Cols.SKU_ID:     sku_id,
            Cols.REGION:     region,
            Cols.WEEK:       week,
            Cols.DEMAND_QTY: qty,
        }
        for (sku_id, region, week), qty in demand_dict.items()
    ]
    df = pd.DataFrame(rows)
    return assign_demand_lots_from_df(sc_tree, df, cpu_size, lot_gen)


# ---------------------------------------------------------------------------
# Demand quantity helper (lot count → physical qty)
# ---------------------------------------------------------------------------

def lots_to_qty(lot_ids: List[str], cpu_size: int = 1) -> float:
    """Convert a list of lot IDs back to demand quantity."""
    return len(lot_ids) * cpu_size


def qty_to_lot_count(qty: float, cpu_size: int = 1) -> int:
    """Convert a demand quantity to the number of lots (ceiling division)."""
    return max(0, math.ceil(qty / cpu_size))
