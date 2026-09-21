"""
wom/ppc/ppc_psi_bridge.py
==========================
Bridge: WOM Planning Engine PSI output → PPC sales_records input.

Converts leaf_out node supply quantities (psi4supply[w][S]) from
the SCTree into the lot-level DataFrame expected by PPCSimulationEngine.

Channel mapping logic
---------------------
SC tree leaf_out nodes have node_id of the form:
    "OUT:Sales:{region}:{sku_id}"

The region string is mapped to a PPC channel_node name via ``channel_map``.
Default mapping:

    JP, JAPAN, KANSAI, KANTO, TOHOKU, KYUSHU, CHUGOKU, HOKKAIDO
        -> "JP_Channel"
    US, USA, AMERICA, WEST, EAST
        -> "US_Channel"

Any region not matched falls back to "{region}_Channel".

Alternatively, set use_node_name=True to use node.node_name directly as
the channel_node (e.g. "Retail_AMER", "Retail_AMER_i15").  This is the
correct mode for models whose ppc_market_price.csv keys on actual node names.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

# ------------------------------------------------------------------
# Default region -> PPC channel_node mapping
# Keys are matched case-insensitively as prefix/substring.
# ------------------------------------------------------------------
_DEFAULT_CHANNEL_MAP: Dict[str, str] = {
    # Japanese domestic regions -> JP_Channel
    "JP":        "JP_Channel",
    "JAPAN":     "JP_Channel",
    "KANSAI":    "JP_Channel",
    "KANTO":     "JP_Channel",
    "TOHOKU":    "JP_Channel",
    "KYUSHU":    "JP_Channel",
    "CHUGOKU":   "JP_Channel",
    "HOKKAIDO":  "JP_Channel",
    "CHUBU":     "JP_Channel",
    "SHIKOKU":   "JP_Channel",
    "OKINAWA":   "JP_Channel",
    # US / North America -> US_Channel
    "US":        "US_Channel",
    "USA":       "US_Channel",
    "AMERICA":   "US_Channel",
    "WEST":      "US_Channel",
    "EAST":      "US_Channel",
}


def _region_to_channel(region: str, channel_map: Dict[str, str]) -> str:
    """
    Map a region string to a PPC channel_node name.

    Matching priority:
    1. Exact match (case-insensitive)
    2. Any key that is a substring of region (case-insensitive)
    3. Fallback: "{region}_Channel"
    """
    r_upper = region.upper()
    # 1. Exact match
    if r_upper in channel_map:
        return channel_map[r_upper]
    # 2. Substring match (longest key wins to avoid "JP" matching "JAPAN" wrongly)
    best_key, best_val = "", ""
    for k, v in channel_map.items():
        if k in r_upper and len(k) > len(best_key):
            best_key, best_val = k, v
    if best_val:
        return best_val
    # 3. Fallback
    return f"{region}_Channel"


def psi_to_sales_records(
    sc_tree,
    weeks: List[str],
    channel_map: Optional[Dict[str, str]] = None,
    product_id_map: Optional[Dict[str, str]] = None,
    use_node_name: bool = False,
) -> pd.DataFrame:
    """
    Extract leaf_out supply quantities from sc_tree and build sales_records.

    One aggregated record is created per (channel_node, week) combination
    where supply > 0.  The qty field carries the total physical quantity
    (lot count x sc_tree.cpu_size -- Letter A: request_letter_a_cpu_size_to_plan.md).

    Parameters
    ----------
    sc_tree : SCTree
        Post-ForwardPlanner SCTree instance.
    weeks : list[str]
        Ordered list of ISO week labels matching the planning horizon,
        e.g. ['2026-W01', '2026-W02', ...].
    channel_map : dict[str, str], optional
        region -> PPC channel_node override.  Merged on top of the defaults.
        Ignored when use_node_name=True.
    product_id_map : dict[str, str], optional
        sku_id -> PPC product_id override.
        Default: identity (sku_id used as product_id as-is).
    use_node_name : bool, optional
        If True, use node.node_name directly as channel_node instead of
        mapping from the region field.  Use this when ppc_market_price.csv
        keys on actual leaf_out node names (e.g. "Retail_AMER", "Retail_AMER_i15").
        Default: False (backward-compatible region-based mapping).

    Returns
    -------
    pd.DataFrame
        Columns: lot_id, week, channel_node, product_id, qty
    """
    from wom.model.plan_node import NODE_TYPE_LEAF_OUT, S as S_BUCKET

    # Merge caller's overrides with defaults (only used when use_node_name=False)
    merged_map = dict(_DEFAULT_CHANNEL_MAP)
    if channel_map:
        merged_map.update({k.upper(): v for k, v in channel_map.items()})

    if product_id_map is None:
        product_id_map = {}

    rows = []
    for prod_nm in sc_tree.products:
        ppc_product = product_id_map.get(prod_nm, prod_nm)

        for node in sc_tree.iter_all_nodes(prod_nm):
            if node.node_type != NODE_TYPE_LEAF_OUT:
                continue

            if use_node_name:
                # Use node_name directly as channel_node (e.g. "Retail_AMER_i15")
                channel_node = node.node_name
            else:
                # Extract region from node_id: "OUT:leaf_out:{region}:{sku_id}"
                parts = node.node_id.split(":")
                region = parts[2] if len(parts) >= 3 else "UNKNOWN"
                channel_node = _region_to_channel(region, merged_map)

            for w_idx, week_label in enumerate(weeks):
                lot_count = node.qty_supply(w_idx, S_BUCKET)
                if lot_count == 0:
                    continue
                # Letter A (request_letter_a_cpu_size_to_plan.md): cpu_size is
                # plan-wide, so it applies here uniformly. bom_qty does NOT
                # apply to leaf_out -- a channel sells finished units (e.g.
                # "5 vehicles"), not the components inside them (see Letter B:
                # request_letter_b_bom_qty.md, and the owner's own framing:
                # "EV を5台売ったのであってタイヤ20本を売ったのではない").
                qty = lot_count * sc_tree.cpu_size
                # One aggregated lot per (product, channel, week)
                lot_id = f"PSI-{ppc_product}-{channel_node}-{week_label}"
                rows.append({
                    "lot_id":       lot_id,
                    "week":         week_label,
                    "channel_node": channel_node,
                    "product_id":   ppc_product,
                    "qty":          qty,
                })

    if not rows:
        return pd.DataFrame(
            columns=["lot_id", "week", "channel_node", "product_id", "qty"]
        )
    return pd.DataFrame(rows)


def summarize_psi_records(df: pd.DataFrame) -> str:
    """Return a one-line summary string for logging."""
    if df.empty:
        return "0 PSI records (no supply)"
    total_qty = int(df["qty"].sum())
    n_weeks   = df["week"].nunique()
    channels  = ", ".join(sorted(df["channel_node"].unique()))
    products  = ", ".join(sorted(df["product_id"].unique()))
    return (
        f"{len(df)} records | qty={total_qty:,} | "
        f"{n_weeks} weeks | channels=[{channels}] | products=[{products}]"
    )
