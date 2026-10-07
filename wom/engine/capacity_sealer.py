"""
wom/engine/capacity_sealer.py
==============================
WOM Step 7 — Capacity Profile Management

Provides utilities for:
  1. Defining CapHard / CapSoft capacity profiles per node per week
  2. Bulk-applying profiles to SCTree PlanNodes
  3. Summarising capacity vs load for management reporting

CapHard vs CapSoft
──────────────────
CapHard  [CAP_HARD = 0]
    Physical equipment limit.  P[w] is HARD-SEALED at this ceiling.
    Excess lots are moved to CO[w+1] during Forward Planning.
    Cannot be overridden.

CapSoft  [CAP_SOFT = 1]
    Operational plan limit (preferred ceiling, e.g. regular-shift target).
    Excess lots are NOT moved — they are FLAGGED as a management alert.
    This models overtime / burst capacity that is possible but costly.

Integration with ForwardPlanner
────────────────────────────────
Capacity sealing is applied inside ForwardPlanner._process_node()
BEFORE the normal PSI roll-forward calculation:

    step 0a: if CapHard > 0 and P[w] > CapHard → seal P, push excess → CO[w+1]
    step 0b: if CapSoft > 0 and P[w] > CapSoft → record violation, no movement
    step 1+: normal available = I[w-1] + P[w] calculation (with sealed P)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

from wom.model.plan_node import PlanNode, CAP_HARD, CAP_SOFT, MAX_SHIFTS
from wom.model.sc_tree   import SCTree


# ---------------------------------------------------------------------------
# CapacityEntry — one node × one week specification
# ---------------------------------------------------------------------------

@dataclass
class CapacityEntry:
    """
    Capacity specification for one node in one week.

    Parameters
    ----------
    node_id:   PlanNode.node_id string
    week:      ISO week label, e.g. "2024-W10"
    cap_hard:  Hard ceiling in lots (None = not set / no ceiling, 0 = zero capacity)
    cap_soft:  Soft ceiling in lots (None = not set / no ceiling, 0 = zero capacity)
    """
    node_id:  str
    week:     str
    cap_hard: float = 0.0
    cap_soft: float = 0.0


# ---------------------------------------------------------------------------
# CapacityProfile — full profile for a product / all products
# ---------------------------------------------------------------------------

@dataclass
class CapacityProfile:
    """
    Collection of CapacityEntry records that can be applied to an SCTree.
    """
    entries: List[CapacityEntry] = field(default_factory=list)

    def add(
        self,
        node_id:  str,
        week:     str,
        cap_hard: Optional[float] = None,
        cap_soft: Optional[float] = None,
    ) -> "CapacityProfile":
        """Append one entry (returns self for chaining)."""
        self.entries.append(
            CapacityEntry(node_id=node_id, week=week,
                          cap_hard=cap_hard, cap_soft=cap_soft)
        )
        return self

    def add_flat(
        self,
        node_id:   str,
        weeks:     List[str],
        cap_hard:  Optional[float] = None,
        cap_soft:  Optional[float] = None,
    ) -> "CapacityProfile":
        """
        Apply the same CapHard/CapSoft to a list of weeks for one node.
        Convenient for setting a constant weekly capacity across a horizon.
        """
        for wk in weeks:
            self.add(node_id, wk, cap_hard, cap_soft)
        return self


# ---------------------------------------------------------------------------
# Apply profile to SCTree
# ---------------------------------------------------------------------------

def apply_capacity_profile(
    sc_tree: SCTree,
    profile: CapacityProfile,
) -> Dict[str, int]:
    """
    Write CapHard / CapSoft from a CapacityProfile onto the corresponding
    PlanNode instances in the SCTree.

    Parameters
    ----------
    sc_tree:
        SCTree with init_psi() already called.
    profile:
        CapacityProfile containing the entries to apply.

    Returns
    -------
    dict
        Summary: {"applied": N, "node_not_found": M, "week_out_of_range": K}
    """
    # Build a flat node_id → PlanNode index across all products
    node_index: Dict[str, PlanNode] = {}
    for prod_nm in sc_tree.products:
        for node in sc_tree.iter_all_nodes(prod_nm):
            node_index[node.node_id] = node

    stats = {"applied": 0, "node_not_found": 0, "week_out_of_range": 0}

    for entry in profile.entries:
        node = node_index.get(entry.node_id)
        if node is None:
            stats["node_not_found"] += 1
            continue

        if not node.week_labels:
            stats["week_out_of_range"] += 1
            continue

        try:
            w_idx = node.week_idx(entry.week)
        except ValueError:
            stats["week_out_of_range"] += 1
            continue

        node.set_capacity(w_idx, entry.cap_hard, entry.cap_soft)
        stats["applied"] += 1

    return stats


# ---------------------------------------------------------------------------
# Convenience builder — uniform capacity from sku_master
# ---------------------------------------------------------------------------

def build_mom_capacity_profile(
    sc_tree:      SCTree,
    cap_hard_per_week: float,
    cap_soft_per_week: float,
    prod_nm:      Optional[str] = None,
) -> CapacityProfile:
    """
    Build a CapacityProfile that applies uniform CapHard / CapSoft
    to all MOM (InBound root) nodes across the full planning horizon.

    Parameters
    ----------
    sc_tree:
        SCTree with week_labels set.
    cap_hard_per_week:
        Hard capacity ceiling in lots per week (0 = unlimited).
    cap_soft_per_week:
        Soft capacity target in lots per week (0 = unlimited).
    prod_nm:
        If given, apply only to that product; otherwise apply to all.

    Returns
    -------
    CapacityProfile
    """
    from wom.model.plan_node import NODE_TYPE_MOM

    profile  = CapacityProfile()
    products = [prod_nm] if prod_nm else sc_tree.products

    for p in products:
        in_root = sc_tree.get_in_root(p)
        # Apply to all MOM nodes (tier-0 and deeper) in the InBound tree
        for node in in_root.walk_preorder():
            if node.node_type == NODE_TYPE_MOM:
                profile.add_flat(
                    node_id  = node.node_id,
                    weeks    = sc_tree.week_labels,
                    cap_hard = cap_hard_per_week,
                    cap_soft = cap_soft_per_week,
                )
    return profile


# ---------------------------------------------------------------------------
# Capacity load summary
# ---------------------------------------------------------------------------

@dataclass
class CapacityLoadSummary:
    """
    Per-node, per-week capacity utilisation report generated
    AFTER forward planning (reads psi4supply[P] vs capacity).
    """
    node_id:  str
    week:     str
    p_qty:    int    # lots received (P)
    cap_hard: float
    cap_soft: float
    hard_util: float  # p_qty / cap_hard  (0.0 if cap_hard=0)
    soft_util: float  # p_qty / cap_soft  (0.0 if cap_soft=0)
    over_hard: bool
    over_soft: bool


def build_capacity_load_report(
    sc_tree:  SCTree,
    prod_nm:  str,
) -> List[CapacityLoadSummary]:
    """
    Scan all PlanNodes for a product and return capacity utilisation
    records for weeks where either CapHard or CapSoft is set.

    Call this AFTER forward planning to see the post-sealing load.
    """
    report: List[CapacityLoadSummary] = []
    n_weeks = sc_tree.num_weeks()

    for node in sc_tree.iter_all_nodes(prod_nm):
        if not node.week_labels:
            continue
        for w in range(n_weeks):
            # Closure-aware limits (Explicit Closure v1r5m0 §4.6):
            # closed week -> 0.0, unset -> None. The raw values are still
            # reported in cap_hard / cap_soft (cap_hard = physical ceiling).
            lim = node.processing_limit(w)
            pc = node.planned_capacity(w)
            if lim is None and pc is None:
                continue   # no capacity set for this (open) week

            from wom.model.plan_node import P as P_IDX
            p_qty = len(node.psi4supply[w][P_IDX])

            hard_util = (p_qty / lim) if lim else 0.0
            soft_util = (p_qty / pc) if pc else 0.0

            report.append(CapacityLoadSummary(
                node_id   = node.node_id,
                week      = node.week_labels[w],
                p_qty     = p_qty,
                cap_hard  = node.cap_hard(w),
                cap_soft  = node.cap_soft(w),
                hard_util = hard_util,
                soft_util = soft_util,
                over_hard = (lim is not None and p_qty > lim),
                over_soft = (pc is not None and p_qty > pc),
            ))

    return report


# ---------------------------------------------------------------------------
# capacity_plan.csv loader (single source of truth for GUI + headless)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Capacity value rule (RequestLetter_CapacityZeroBlank, 2026-10-07)
# ---------------------------------------------------------------------------

class CapacityDataError(ValueError):
    """A capacity input that cannot be read. The planning run stops: the rows
    are listed with how to fix them (no silent default is made up)."""


def parse_capacity_value(value, *, source: str = "", line=None, column: str = ""):
    """One capacity cell -> None (blank: not set, no ceiling) / 0.0 (zero
    capacity) / a positive float. A non-number or a negative number raises
    CapacityDataError naming the file, line and value."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    s = str(value).strip()
    if s == "":
        return None
    try:
        x = float(s)
    except ValueError:
        x = None
    if x is None or x != x or x < 0:
        where = f"{source} {line} 行目" if line is not None else source
        raise CapacityDataError(
            f"{where} の {column} が読めません：{value!r}（空欄＝未設定・0＝能力ゼロ・"
            f"正の数＝上限のどれかにしてください。負の数や数値でない値は使えません）")
    return x


def _raise_not_found(source: str, rows: List[Tuple[int, str, str]], what: str = "ノード") -> None:
    shown = "\n".join(f"  {source} {ln} 行目：製品 {sku!r}・{what} {name!r}" for ln, sku, name in rows[:30])
    more = f"\n  ほか {len(rows) - 30} 行" if len(rows) > 30 else ""
    raise CapacityDataError(
        f"{source}：計画の木に無い{what}の行が {len(rows)} 行あります。能力が入らないので止めます。\n"
        f"{shown}{more}\n"
        f"直し方：{what}名の綴りが sc_tree_master.csv の node_name と同じか、その{what}が"
        f"その製品（product_name）の木にあるかを確かめてください。")


def _warn_out_of_range(source: str, n: int) -> None:
    if n:
        import warnings
        msg = (f"{source}：計画期間の外の週の行 {n} 件を読み飛ばしました"
               f"（能力の表が計画期間より長いのは普通です）")
        warnings.warn(msg, RuntimeWarning, stacklevel=3)
        print(f"[Capacity] {msg}")


def load_capacity_dataframe(
    sc_tree:  SCTree,
    cap_df:   "pd.DataFrame",
    weeks:    List[str],
    source:   str = "capacity_plan.csv",
) -> Dict[str, int]:
    """
    Apply a `capacity_plan.csv` DataFrame to the SCTree's PlanNodes.

    This is the **single, testable data path** shared by the GUI
    (`wom/gui/app.py`) and the headless runner
    (`tools/run_headless_from_folder.py`).  Previously each caller had its own
    inline loader that mapped only ``max_supply -> cap_hard`` — the missing
    ``cap_soft`` column was the root cause of cap_soft lying dormant (see the
    "operating-constraint-layer" request letter §3/§11.1).

    Columns
    -------
    Required : ``sku_id``, ``week``, ``max_supply``
    Optional : ``node_name``  — if present, capacity is applied to that named
               node; otherwise ``max_supply`` is aggregated by (sku_id, week)
               and applied to each product's InBound root (MOM).
    Optional : ``cap_soft``   — operational/shift ceiling.  When the column is
               absent, ``cap_soft`` stays not set (no ceiling).

    Values (RequestLetter_CapacityZeroBlank, 2026-10-07), both columns:
      blank      -> not set: no ceiling (the node keeps None)
      0          -> ZERO capacity: nothing can be processed in that week
                    (formerly 0 meant "no ceiling")
      > 0        -> the ceiling
      a negative number / not a number -> CapacityDataError (file, line, value)
    A row whose (product, node_name) is not in the plan tree also raises
    CapacityDataError, listing every such row (formerly it was only counted
    as node_not_found and silently ignored). Rows outside the plan horizon are
    skipped with a warning (a capacity table longer than the horizon is
    normal).

    cap_soft semantics (Forward Step 0b) : a *flag only* — lots are never moved
    by cap_soft.  Physical sealing/CO is governed solely by ``cap_hard``.

    Old format without ``node_name`` (aggregated by (sku_id, week) into the
    product's InBound root): a blank in any row of a group makes the group
    not set (one source without a ceiling = no ceiling for the sum).

    Returns
    -------
    dict : {"applied": N, "node_not_found": 0, "week_out_of_range": K}
    """
    stats = {"applied": 0, "node_not_found": 0, "week_out_of_range": 0}

    if cap_df is None or not {"sku_id", "week", "max_supply"}.issubset(set(cap_df.columns)):
        return stats

    has_soft = "cap_soft" in cap_df.columns
    widx = {str(w): i for i, w in enumerate(weeks)}

    # 1. read every value first (stop on an unreadable one before applying any)
    parsed = []          # (line, sku, node_name or None, week, hard, soft)
    for i, row in enumerate(cap_df.to_dict("records")):
        line = i + 2                       # header is line 1
        hard = parse_capacity_value(row.get("max_supply"), source=source, line=line,
                                    column="max_supply")
        soft = (parse_capacity_value(row.get("cap_soft"), source=source, line=line,
                                     column="cap_soft") if has_soft else None)
        node_name = str(row["node_name"]) if "node_name" in cap_df.columns else None
        parsed.append((line, str(row["sku_id"]), node_name, str(row["week"]), hard, soft))

    if "node_name" in cap_df.columns:
        # per-node path
        lut: Dict[Tuple[str, str], PlanNode] = {}
        for pn in sc_tree.products:
            for nd in sc_tree.iter_all_nodes(pn):
                lut[(pn, nd.node_name)] = nd
        missing = [(ln, sku, nm) for ln, sku, nm, _wk, _h, _s in parsed if (sku, nm) not in lut]
        if missing:
            _raise_not_found(source, missing, "ノード")
        for ln, sku, nm, wk, hard, soft in parsed:
            wi = widx.get(wk)
            if wi is None:
                stats["week_out_of_range"] += 1
                continue
            lut[(sku, nm)].set_capacity(wi, cap_hard=hard, cap_soft=soft)
            stats["applied"] += 1
    else:
        # sku-aggregate → MOM (InBound root) path
        roots: Dict[str, PlanNode] = {}
        for pn in sc_tree.products:
            try:
                roots[pn] = sc_tree.get_in_root(pn)
            except Exception:
                pass
        missing = [(ln, sku, "(InBound root)") for ln, sku, _nm, _wk, _h, _s in parsed
                   if sku not in roots]
        if missing:
            _raise_not_found(source, missing, "製品")
        groups: Dict[Tuple[str, str], list] = {}
        for ln, sku, _nm, wk, hard, soft in parsed:
            groups.setdefault((sku, wk), []).append((hard, soft))

        def _sum(vals):
            return None if any(v is None for v in vals) else float(sum(vals))

        for (sku, wk), vals in groups.items():
            wi = widx.get(wk)
            if wi is None:
                stats["week_out_of_range"] += 1
                continue
            hard = _sum([h for h, _s in vals])
            soft = _sum([s for _h, s in vals]) if has_soft else None
            roots[sku].set_capacity(wi, cap_hard=hard, cap_soft=soft)
            stats["applied"] += 1

    _warn_out_of_range(source, stats["week_out_of_range"])
    return stats


# ---------------------------------------------------------------------------
# operating_calendar.csv loader (Phase 2: per-node shift plan)
# ---------------------------------------------------------------------------

def load_operating_calendar(
    sc_tree:  SCTree,
    cal_df:   "pd.DataFrame",
    weeks:    List[str],
) -> Dict[str, int]:
    """
    Apply an `operating_calendar.csv` DataFrame to the SCTree's PlanNodes as a
    per-week operating **shift count** (0..MAX_SHIFTS).

    Columns (all required): ``sku_id``, ``node_name``, ``week``, ``shifts``.

    Semantics (data model agreed 2026-07-31):
      - ``shifts == 0`` -> the node is **closed** that week; BackwardPlanner's
        `_offset_week` skips it (same "place on the adjacent open week" behaviour
        as SS_Days / holidays).
      - ``shifts == N > 0`` -> open with N shifts/week. Future (Slice 2-2):
        ``cap_soft = N * cap_hard / MAX_SHIFTS``.
      - Weeks/nodes not listed keep ``None`` (no calendar entry = always open),
        so models without this file are byte-for-byte unchanged (opt-in).

    Returns
    -------
    dict : {"applied": N, "node_not_found": M, "week_out_of_range": K}
    """
    stats = {"applied": 0, "node_not_found": 0, "week_out_of_range": 0}

    if cal_df is None or not {"sku_id", "node_name", "week", "shifts"}.issubset(set(cal_df.columns)):
        return stats

    widx = {str(w): i for i, w in enumerate(weeks)}
    lut: Dict[Tuple[str, str], PlanNode] = {}
    for pn in sc_tree.products:
        for nd in sc_tree.iter_all_nodes(pn):
            lut[(pn, nd.node_name)] = nd

    for _, row in cal_df.iterrows():
        nd = lut.get((str(row["sku_id"]), str(row["node_name"])))
        if nd is None:
            stats["node_not_found"] += 1
            continue
        wi = widx.get(str(row["week"]))
        if wi is None:
            stats["week_out_of_range"] += 1
            continue
        try:
            sh = int(row["shifts"])
        except (TypeError, ValueError):
            continue
        sh = max(0, min(MAX_SHIFTS, sh))   # clamp to [0, 21]
        nd.set_operating_shifts(wi, sh)

        # Slice 2-2: derive cap_soft from the planned shift level.
        #   cap_soft(w) = round(sh * cap_hard(w) / MAX_SHIFTS)   for sh > 0.
        #   21 shifts => cap_soft == cap_hard (physical ceiling); cap_hard unchanged.
        #   0-shift (closed) weeks are handled by the backward skip; cap_soft left
        #   as-is. cap_hard must already be set (capacity_plan loads first) —
        #   weeks without a physical ceiling (cap_hard==0) are not derived.
        if sh > 0:
            ch = nd.cap_hard(wi)
            if ch is not None:          # None = no physical ceiling: nothing to derive
                nd.set_capacity(wi, cap_hard=ch,
                                cap_soft=float(round(sh * ch / MAX_SHIFTS)))

        stats["applied"] += 1

    return stats
