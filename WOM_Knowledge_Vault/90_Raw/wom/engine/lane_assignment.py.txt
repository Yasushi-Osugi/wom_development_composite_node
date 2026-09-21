"""
wom/engine/lane_assignment.py
==============================
Production Allocation Policy — Market-to-MOM Lane Assignment Table

Each (sku_id, leaf_node_name) pair maps to a specific MOM node_id.
This is a fixed, user-specified table that reflects:
  - Distance / transport cost optimisation
  - Tariff and trade-rule constraints
  - Local SG&A and profit-margin considerations
  - Quality / compliance requirements per market

Design rationale
----------------
Key = leaf_node_name (finest granularity)
  Each leaf_out node represents one sales channel in one market.
  Using leaf_node_name as the key allows per-channel MOM assignment,
  which is impossible with region-based keys.  Examples:
    - Retail_AMER  → Foxconn_IN  (AMER physical retail)
    - Online_AMER  → Foxconn_VN  (AMER e-commerce, different lane)
    - Online_GLOBAL → Foxconn_VN  (cross-region channel, no region tag)

Fallback hierarchy (BackwardPlanner Phase 2)
--------------------------------------------
  1. Exact match:  (sku_id, leaf_node_name)  → mom_node_id
  2. Region match: (sku_id, region)          → mom_node_id   ← bulk default
  3. Default:      primary MOM (first registered)

This allows mixing fine-grained overrides with coarse region defaults:
  iPhone16, Retail_AMER,  IN:mom:Foxconn_IN:iPhone16, 1   ← leaf override
  iPhone16, EMEA,         IN:mom:Foxconn_CN:iPhone16, 1   ← region default
  iPhone16, APAC,         IN:mom:Foxconn_CN:iPhone16, 1   ← region default

Usage in BackwardPlanner Phase 2
---------------------------------
For each lot arriving at supply_point[w][S]:
  1. Look up the lot's destination leaf_out  (via _lot_leaf_index)
  2. lane_table.resolve(sku_id, leaf.node_name, leaf.region) → mom_node_id
  3. Route lot to that MOM's psi4demand[w][S]
  4. If no match → fallback to primary MOM

CSV format  (lane_assignment.csv)
----------------------------------
sku_id, leaf_node_name, mom_node_id, priority
  sku_id         : product name (matches sc_tree products)
  leaf_node_name : node_name of the leaf_out node (sales channel)
                   OR region code (AMER / EMEA / APAC / …) for bulk default
  mom_node_id    : full node_id of the target MOM PlanNode
                   format: IN:mom:<node_name>:<sku_id>
  priority       : (future use) 1 = primary lane

Example
-------
iPhone16,Retail_AMER,IN:mom:Foxconn_IN:iPhone16,1
iPhone16,Online_AMER,IN:mom:Foxconn_VN:iPhone16,1
iPhone16,EMEA,IN:mom:Foxconn_CN:iPhone16,1
iPhone16,APAC,IN:mom:Foxconn_CN:iPhone16,1
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# LaneAssignment — one row from the CSV
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LaneAssignment:
    sku_id:         str
    leaf_node_name: str   # leaf_out node_name OR region code (for bulk default)
    mom_node_id:    str
    priority:       int = 1


# ---------------------------------------------------------------------------
# LaneTable — lookup engine
# ---------------------------------------------------------------------------

class LaneTable:
    """
    Lookup table with two-level fallback:
      1. (sku_id, leaf_node_name) — exact per-channel match
      2. (sku_id, region)         — region-level bulk default

    BackwardPlanner calls resolve(sku_id, leaf_node_name, region).
    """

    def __init__(self, rows: List[LaneAssignment]) -> None:
        # Last row wins on duplicate keys
        self._table: Dict[Tuple[str, str], str] = {
            (r.sku_id, r.leaf_node_name): r.mom_node_id for r in rows
        }
        self._rows = list(rows)

    # ------------------------------------------------------------------
    # Primary interface
    # ------------------------------------------------------------------

    def resolve(
        self,
        sku_id:         str,
        leaf_node_name: str,
        region:         str = "",
    ) -> Optional[str]:
        """
        Resolve mom_node_id with fallback hierarchy:
          1. Exact leaf_node_name match
          2. Region match (bulk default)
          3. None  →  caller uses primary MOM
        """
        # 1. exact leaf match
        result = self._table.get((sku_id, leaf_node_name))
        if result:
            return result
        # 2. region fallback
        if region:
            result = self._table.get((sku_id, region))
        return result

    # kept for backward compatibility
    def get_mom_node_id(self, sku_id: str, key: str) -> Optional[str]:
        """Direct key lookup (no fallback). Use resolve() for new code."""
        return self._table.get((sku_id, key))

    def is_empty(self) -> bool:
        return len(self._table) == 0

    def leaf_keys_for_sku(self, sku_id: str) -> List[str]:
        """All leaf_node_name / region keys defined for a given SKU."""
        return [k for (s, k) in self._table if s == sku_id]

    def mom_nodes_for_sku(self, sku_id: str) -> List[str]:
        """Distinct MOM node_ids assigned for a given SKU."""
        return list({v for (s, _), v in self._table.items() if s == sku_id})

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @staticmethod
    def from_csv(path: str | Path) -> "LaneTable":
        """Load from lane_assignment.csv."""
        rows: List[LaneAssignment] = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sku_id   = (row.get("sku_id")         or "").strip()
                leaf_key = (row.get("leaf_node_name") or "").strip()
                mom_id   = (row.get("mom_node_id")    or "").strip()
                if not (sku_id and leaf_key and mom_id):
                    continue
                rows.append(LaneAssignment(
                    sku_id=sku_id,
                    leaf_node_name=leaf_key,
                    mom_node_id=mom_id,
                    priority=int(row.get("priority") or 1),
                ))
        return LaneTable(rows)

    @staticmethod
    def empty() -> "LaneTable":
        return LaneTable([])

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"LaneTable({len(self._table)} entries)"
