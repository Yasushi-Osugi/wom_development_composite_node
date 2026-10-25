"""
wom/engine/yield_rate.py
========================
Yield of the finished product at the factory's shipment point
(RequestLetter_YieldRate_PartA, 2026-10-25).

    Ship_Qty = Production_Qty x yield_rate

Read from sc_tree_master.csv's ``yield_rate`` column (on MOM rows). Blank or
no column = 1.0. The value is NOT defaulted silently when it cannot be used
(unlike bom_qty): the planning run stops with the file, line, node, product,
value and how to fix it.

Stop conditions
---------------
At load (``parse_yield_rate``, called by sc_tree_builder):
  * not a number, <= 0, or > 1
  * a value other than 1.0 on a node that is not a MOM
At the start of the planning pipeline (``check_yield_rate_context``):
  * lot_flow_mode = legacy (legacy is not changed, Decision Record D3)
  * RiceSeasonalPlugin is ON (Rice keeps its yield in rice_recipe.csv)
At the start of Forward (``check_forward_yield``, in ForwardPlanner.run):
  * a push decoupling MOM (its P is a receipt and is not sealed in Step 0a,
    so the yield would silently not apply). Also re-checks legacy, so paths
    that skip the pipeline check (plugins trial-running Forward) still stop.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

from wom.engine.tree_attrs import TreeAttributeError

SOURCE = "sc_tree_master.csv"


class YieldRateError(TreeAttributeError):
    """A yield_rate the engine cannot use. The planning run stops.
    (A TreeAttributeError, so the GUI's re-raise covers both.)"""


def _where(node_name, product, line, source=SOURCE) -> str:
    loc = f"{source}" + (f" line {line}" if line is not None else "")
    return f"{loc}: node {node_name!r} (product {product!r})"


def parse_yield_rate(raw, *, node_name: str, product: str, node_type: str,
                     line: Optional[int] = None, source: str = SOURCE) -> float:
    """Parse one yield_rate cell. Blank / NaN / None -> 1.0."""
    s = str(raw).strip() if raw is not None else ""
    if s == "" or s.lower() == "nan":
        return 1.0
    where = _where(node_name, product, line, source)
    try:
        y = float(s)
    except (TypeError, ValueError):
        raise YieldRateError(
            f"{where}: yield_rate={raw!r} is not a number. "
            f"Write a value in (0, 1] (e.g. 0.97), or leave it blank for 1.0.")
    if math.isnan(y) or y <= 0.0 or y > 1.0:
        raise YieldRateError(
            f"{where}: yield_rate={raw!r} is out of range. "
            f"Write a value in (0, 1] (e.g. 0.97), or leave it blank for 1.0.")
    if y != 1.0 and node_type != "mom":
        raise YieldRateError(
            f"{where}: yield_rate={raw!r} is set on a {node_type!r} node. "
            f"The yield is defined once, at the finished product's shipment "
            f"point: write it on the factory (node_type='mom') row and leave "
            f"this row blank.")
    return y


def _yield_nodes(sc_tree):
    for prod in sc_tree.products:
        for nd in sc_tree.iter_all_nodes(prod):
            if nd.yield_rate != 1.0:
                yield prod, nd


def check_yield_rate_context(sc_tree, *, lot_flow_mode: Optional[str],
                             plugin_names: Iterable[str] = ()) -> None:
    """Stop if a yield_rate other than 1.0 meets legacy mode or Rice Seasonal."""
    nodes = list(_yield_nodes(sc_tree))
    if not nodes:
        return
    prod, nd = nodes[0]
    where = _where(nd.node_name, prod, nd.yield_rate_line)
    if (lot_flow_mode or "").strip().lower() == "legacy":
        raise YieldRateError(
            f"{where}: yield_rate={nd.yield_rate} cannot be used with "
            f"lot_flow_mode=legacy (legacy is kept unchanged). Use "
            f"lot_flow_mode=identity in planning_config.csv, or leave "
            f"yield_rate blank.")
    if "RiceSeasonalPlugin" in set(plugin_names):
        raise YieldRateError(
            f"{where}: yield_rate={nd.yield_rate} cannot be used while "
            f"RiceSeasonalPlugin is ON (Rice keeps its yield in "
            f"rice_recipe.csv; it must not be applied twice). Turn the plugin "
            f"off, or leave yield_rate blank.")


def check_forward_yield(sc_tree, prod_nm: str, *, lot_flow_mode: str) -> None:
    """Stop if a push MOM, or a legacy run, carries a yield_rate other than 1.0."""
    for nd in sc_tree.iter_all_nodes(prod_nm):
        if nd.yield_rate == 1.0:
            continue
        where = _where(nd.node_name, prod_nm, nd.yield_rate_line)
        if lot_flow_mode == "legacy":
            raise YieldRateError(
                f"{where}: yield_rate={nd.yield_rate} cannot be used with "
                f"lot_flow_mode=legacy (legacy is kept unchanged). Use "
                f"lot_flow_mode=identity, or leave yield_rate blank.")
        if nd.plan_mode == "push":
            raise YieldRateError(
                f"{where}: yield_rate={nd.yield_rate} is set on a push "
                f"decoupling node (push_config.csv). Its P is a receipt and is "
                f"not sealed, so the yield would not apply. Leave yield_rate "
                f"blank on this node, or remove it from push_config.csv.")
