"""
wom/engine/tree_attrs.py
========================
Reading the per-node attribute cells of sc_tree_master.csv that must not be
defaulted silently (RequestLetter_WarmupSoft_BlankAttrs_ShelfLifeFIFO, Part B;
owner decision d, 2026-10-25):

    blank / no column = N/A (not set); 0 = an explicit 0.

| column            | blank / no column | valid                       | anything else |
|-------------------|-------------------|-----------------------------|---------------|
| ss_days           | not set (plan = 0)| 0 or a positive integer     | stop          |
| init_stock_days   | not set (plan = 0)| 0 or a positive integer     | stop          |
| demand_envelope   | "hard"            | hard / soft (case, spaces)  | stop          |

A stop raises TreeAttributeError with the file, line, column, node, product,
value and how to fix it (the same form as YieldRateError, which subclasses it).
Formerly a blank day cell stopped with a bare "cannot convert float NaN to
integer" and a misspelt envelope silently became "hard".
"""
from __future__ import annotations

import math
from typing import Optional

SOURCE = "sc_tree_master.csv"


class TreeAttributeError(ValueError):
    """A sc_tree_master.csv attribute the engine cannot use. The planning run stops."""


def where(node_name, product, line, source=SOURCE) -> str:
    loc = f"{source}" + (f" line {line}" if line is not None else "")
    return f"{loc}: node {node_name!r} (product {product!r})"


def is_blank(raw) -> bool:
    if raw is None:
        return True
    if isinstance(raw, float) and math.isnan(raw):
        return True
    s = str(raw).strip()
    return s == "" or s.lower() == "nan"


def parse_days(raw, *, column: str, node_name: str, product: str,
               line: Optional[int] = None, source: str = SOURCE) -> Optional[int]:
    """Day count cell -> None (blank = not set) or an int >= 0. Anything else stops.
    An integer-valued float (14.0, as pandas reads a column with blanks) is an integer."""
    if is_blank(raw):
        return None
    try:
        f = float(str(raw).strip())
    except (TypeError, ValueError):
        f = None
    if f is None or math.isnan(f) or f < 0 or f != int(f):
        raise TreeAttributeError(
            f"{where(node_name, product, line, source)}: {column}={raw!r} is not a "
            f"whole number of days >= 0. Write 0 or a positive integer (e.g. 14), "
            f"or leave the cell blank for 'not set'.")
    return int(f)


def parse_envelope(raw, *, node_name: str, product: str,
                   line: Optional[int] = None, source: str = SOURCE) -> str:
    """demand_envelope cell -> "hard" / "soft". Blank = "hard"; anything else stops."""
    if is_blank(raw):
        return "hard"
    v = str(raw).strip().lower()
    if v not in ("hard", "soft"):
        raise TreeAttributeError(
            f"{where(node_name, product, line, source)}: demand_envelope={raw!r} is "
            f"not 'hard' or 'soft'. Write hard or soft, or leave the cell blank for "
            f"hard.")
    return v
