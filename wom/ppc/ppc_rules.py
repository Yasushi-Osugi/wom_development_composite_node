"""
wom/ppc/ppc_rules.py
====================
Rule master loader for PPC Simulation Engine.

Loads all CSV master files and provides typed lookup helpers.
No business logic here — pure data access layer.
"""

from __future__ import annotations

import csv
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd

# ──────────────────────────────────────────────────────────────────────────
# Where the rules come from (RequestLetter_PPC_NoSilentFallback B.1, D8)
#
# One place decides the rule folder for the headless runner, the GUI, the PPC
# runner and the Value Chain FX: the model folder first; a file the model does
# not have is read from the SHARED rules folder only when the model declares it
# in planning_config.csv (`ppc_shared_rules_dir`, e.g. data/ppc). Without the
# declaration nothing is read from data/ppc: the missing files are returned and
# the money result is "未評価" (never a silent switch to the sample rules).
# A relative declaration resolves from the repository root (not the cwd).
# ──────────────────────────────────────────────────────────────────────────

PPC_RULE_FILES = [
    "ppc_market_price.csv", "ppc_supplier_cost.csv", "ppc_node_cost_rule.csv",
    "ppc_edge_cost_rule.csv", "ppc_tariff_rule.csv", "ppc_transfer_price_rule.csv",
    "ppc_profit_zone_rule.csv", "ppc_fx_rate.csv", "ppc_node_profit_zone.csv",
]
SHARED_RULES_KEY = "ppc_shared_rules_dir"
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read_shared_rules_dir(model_dir: str) -> Optional[str]:
    """The `ppc_shared_rules_dir` value of the model's planning_config.csv (raw), or None."""
    path = os.path.join(model_dir, "planning_config.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("key") or "").strip() == SHARED_RULES_KEY:
                v = (row.get("value") or "").strip()
                return v or None
    return None


def resolve_shared_dir(raw: Optional[str]) -> Optional[str]:
    """Declared shared folder -> absolute path (relative = from the repository root)."""
    if not raw:
        return None
    return os.path.normpath(raw if os.path.isabs(raw) else os.path.join(REPO_ROOT, raw))


@dataclass
class PPCRuleSources:
    """Where each rule file of one model comes from."""
    model_dir: str
    shared_declared: Optional[str]          # the raw declaration (None = not declared)
    shared_dir: Optional[str]               # its absolute path
    paths: Dict[str, str]                   # file -> path actually read
    sources: Dict[str, str]                 # file -> "model" / "shared:<declared>"
    missing: List[str]                      # files found nowhere allowed

    @property
    def complete(self) -> bool:
        return not self.missing

    def rule_dir_for(self, name: str) -> str:
        """The folder a rule file was read from (for files read next to it)."""
        p = self.paths.get(name)
        return os.path.dirname(p) if p else self.model_dir

    def record(self) -> dict:
        """Location-independent (no absolute paths): the PPC output files must be
        the same wherever the model folder is (LOVEM Q12 compares their hashes;
        the model folder itself is in ppc_run_info.json)."""
        return {"shared_rules_dir": self.shared_declared,
                "sources": dict(self.sources), "missing": list(self.missing)}


def resolve_ppc_rules(model_dir: str, files: Optional[List[str]] = None) -> PPCRuleSources:
    """Decide the source of each rule file: the model, else the declared shared
    folder, else missing (no other place is tried)."""
    files = list(files or PPC_RULE_FILES)
    raw = read_shared_rules_dir(model_dir)
    shared = resolve_shared_dir(raw)
    paths, sources, missing = {}, {}, []
    for name in files:
        p = os.path.join(model_dir, name)
        if os.path.exists(p):
            paths[name], sources[name] = p, "model"
            continue
        if shared:
            sp = os.path.join(shared, name)
            if os.path.exists(sp):
                paths[name], sources[name] = sp, f"shared:{raw}"
                continue
        missing.append(name)
    return PPCRuleSources(model_dir, raw, shared, paths, sources, missing)


def channel_uses_node_name(sources: PPCRuleSources) -> bool:
    """How sales channels are named for the rules (kept separate from the rule
    source): node names when the model has its own market prices; otherwise the
    region names of the shared rules -- the same result as before (S1)."""
    return sources.sources.get("ppc_market_price.csv") == "model"


def base_currency_of(sources: PPCRuleSources, default: str = "JPY") -> str:
    """base_currency of the FX file the rules use (one value), else `default`."""
    p = sources.paths.get("ppc_fx_rate.csv")
    if p:
        try:
            vals = pd.read_csv(p, dtype=str)["base_currency"].dropna().unique()
            if len(vals) == 1:
                return str(vals[0])
        except Exception:
            pass
    return default


@dataclass
class PPCRuleSet:
    """
    Complete set of PPC rule masters loaded from CSV files.

    All DataFrames are read-only after construction.
    Lookup dicts are built in __post_init__ to avoid repeated boolean indexing.
    """
    market_price:        pd.DataFrame   # market_node, product_id, week, market_price, currency
    supplier_cost:       pd.DataFrame   # supplier_node, product_id, week, purchase_price, currency
    node_cost_rule:      pd.DataFrame   # node_id, product_id, cost_type, basis, rate, fixed_amount, currency
    edge_cost_rule:      pd.DataFrame   # edge_id, product_id, cost_type, basis, rate, fixed_amount, currency
    tariff_rule:         pd.DataFrame   # edge_id, product_id, tariff_rate, tariff_basis, ...
    transfer_price_rule: pd.DataFrame   # mom_node, product_id, method, margin_rate, fixed_price, currency
    profit_zone_rule:    pd.DataFrame   # profit_zone_role, product_id, profit_type, basis, rate, fixed_amount
    fx_rate:             pd.DataFrame   # week, currency, base_currency, rate
    node_profit_zone:    pd.DataFrame   # node_id, product_id, profit_zone_role, country

    # ------------------------------------------------------------------
    # Internal caches (populated by __post_init__)
    # ------------------------------------------------------------------
    _market_price_idx:      Dict = field(default_factory=dict, init=False, repr=False)
    _supplier_cost_idx:     Dict = field(default_factory=dict, init=False, repr=False)
    _node_cost_cache:       Dict = field(default_factory=dict, init=False, repr=False)
    _edge_cost_cache:       Dict = field(default_factory=dict, init=False, repr=False)
    _tariff_cache:          Dict = field(default_factory=dict, init=False, repr=False)
    _tp_rule_cache:         Dict = field(default_factory=dict, init=False, repr=False)
    _profit_zone_cache:     Dict = field(default_factory=dict, init=False, repr=False)
    _country_cache:         Dict = field(default_factory=dict, init=False, repr=False)
    # (kind, node, product) -> count of price / supplier-cost lookups that found
    # NO rule row ("*_missing": today answered by 0 -- never evaluated) or asked
    # for a week before the rule's first row ("*_before_first_rule_week": the
    # first row's value is used -- evaluated, recorded; owner decision 2026-10-26)
    lookup_log:             Counter = field(default_factory=Counter, init=False, repr=False)

    def __post_init__(self) -> None:
        """Pre-build all lookup dicts to avoid per-call DataFrame filtering."""

        # market_price: (market_node, product_id) -> sorted list of (week, price, currency)
        mp = self.market_price
        for _, r in mp.iterrows():
            k = (str(r["market_node"]), str(r["product_id"]))
            self._market_price_idx.setdefault(k, []).append(
                (str(r["week"]), float(r["market_price"]), str(r["currency"]))
            )
        for k in self._market_price_idx:
            self._market_price_idx[k].sort(key=lambda x: x[0])

        # supplier_cost: (supplier_node, product_id) -> sorted list of (week, price, currency)
        sc = self.supplier_cost
        for _, r in sc.iterrows():
            k = (str(r["supplier_node"]), str(r["product_id"]))
            self._supplier_cost_idx.setdefault(k, []).append(
                (str(r["week"]), float(r["purchase_price"]), str(r["currency"]))
            )
        for k in self._supplier_cost_idx:
            self._supplier_cost_idx[k].sort(key=lambda x: x[0])

        # node_cost_rule: (node_id, product_id) -> DataFrame subset
        nc = self.node_cost_rule
        for key, grp in nc.groupby(["node_id", "product_id"]):
            self._node_cost_cache[key] = grp.reset_index(drop=True)

        # edge_cost_rule: (edge_id, product_id) -> DataFrame subset
        ec = self.edge_cost_rule
        for key, grp in ec.groupby(["edge_id", "product_id"]):
            self._edge_cost_cache[key] = grp.reset_index(drop=True)

        # tariff_rule: (edge_id, product_id) -> first matching Series or None
        tr = self.tariff_rule
        for key, grp in tr.groupby(["edge_id", "product_id"]):
            self._tariff_cache[key] = grp.iloc[0]

        # transfer_price_rule: (mom_node, product_id) -> first matching Series or None
        tp = self.transfer_price_rule
        for key, grp in tp.groupby(["mom_node", "product_id"]):
            self._tp_rule_cache[key] = grp.iloc[0]

        # node_profit_zone: (node_id, product_id) -> (profit_zone_role, country)
        npz = self.node_profit_zone
        for _, r in npz.iterrows():
            k = (str(r["node_id"]), str(r["product_id"]))
            self._profit_zone_cache[k] = str(r["profit_zone_role"])
            self._country_cache[k] = str(r["country"])

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------
    @classmethod
    def load_from_sources(cls, sources: PPCRuleSources) -> "PPCRuleSet":
        """Load the rule files decided by resolve_ppc_rules() (all must be found)."""
        if sources.missing:
            raise FileNotFoundError(f"PPC rule CSV(s) not found in {sources.model_dir} "
                                    f"(no shared rules declared there): {sources.missing}")
        return cls._load_paths(sources.paths)

    @classmethod
    def load(cls, data_dir: str, fallback_dir: Optional[str] = None) -> "PPCRuleSet":
        """Load all CSV masters from data_dir. A missing file stops (FileNotFoundError),
        unless `fallback_dir` is given explicitly (no silent default since D8)."""
        paths = {}
        for name in PPC_RULE_FILES:
            path = os.path.join(data_dir, name)
            if not os.path.exists(path) and fallback_dir and fallback_dir != data_dir:
                fb = os.path.join(fallback_dir, name)
                if os.path.exists(fb):
                    print(f"[PPC Rules] {name}: not in {data_dir}, read from {fallback_dir}")
                    path = fb
            if not os.path.exists(path):
                raise FileNotFoundError(f"PPC rule CSV not found: {path}")
            paths[name] = path
        return cls._load_paths(paths)

    @classmethod
    def _load_paths(cls, paths: Dict[str, str]) -> "PPCRuleSet":
        def _read(name: str) -> pd.DataFrame:
            return pd.read_csv(paths[name], dtype=str)

        market_price        = _read("ppc_market_price.csv")
        supplier_cost       = _read("ppc_supplier_cost.csv")
        node_cost_rule      = _read("ppc_node_cost_rule.csv")
        edge_cost_rule      = _read("ppc_edge_cost_rule.csv")
        tariff_rule         = _read("ppc_tariff_rule.csv")
        transfer_price_rule = _read("ppc_transfer_price_rule.csv")
        profit_zone_rule    = _read("ppc_profit_zone_rule.csv")
        fx_rate             = _read("ppc_fx_rate.csv")
        node_profit_zone    = _read("ppc_node_profit_zone.csv")

        # Cast numeric columns
        for df, cols in [
            (market_price,        ["market_price"]),
            (supplier_cost,       ["purchase_price"]),
            (node_cost_rule,      ["rate", "fixed_amount"]),
            (edge_cost_rule,      ["rate", "fixed_amount"]),
            (tariff_rule,         ["tariff_rate"]),
            (transfer_price_rule, ["margin_rate"]),
            (profit_zone_rule,    ["rate", "fixed_amount"]),
            (fx_rate,             ["rate"]),
        ]:
            for col in cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return cls(
            market_price=market_price,
            supplier_cost=supplier_cost,
            node_cost_rule=node_cost_rule,
            edge_cost_rule=edge_cost_rule,
            tariff_rule=tariff_rule,
            transfer_price_rule=transfer_price_rule,
            profit_zone_rule=profit_zone_rule,
            fx_rate=fx_rate,
            node_profit_zone=node_profit_zone,
        )

    # ------------------------------------------------------------------
    # Market Price
    # ------------------------------------------------------------------
    def get_market_price(
        self, market_node: str, product_id: str, week: str
    ) -> Tuple[float, str]:
        """Return (price, currency) for a market node in a given week."""
        k = (market_node, product_id)
        entries = self._market_price_idx.get(k)
        if not entries:
            self.lookup_log[("market_price_missing", market_node, product_id)] += 1
            return 0.0, "JPY"
        for w, price, cur in reversed(entries):
            if w <= week:
                return price, cur
        self.lookup_log[("market_price_before_first_rule_week", market_node, product_id)] += 1
        return entries[0][1], entries[0][2]

    def has_market_price(self, market_node: str, product_id: str) -> bool:
        """True when the rules hold at least one price row for this market x product."""
        return bool(self._market_price_idx.get((market_node, product_id)))

    # ------------------------------------------------------------------
    # Supplier Cost
    # ------------------------------------------------------------------
    def get_supplier_cost(
        self, supplier_node: str, product_id: str, week: str
    ) -> Tuple[float, str]:
        """Return (purchase_price, currency) for a supplier in a given week."""
        k = (supplier_node, product_id)
        entries = self._supplier_cost_idx.get(k)
        if not entries:
            self.lookup_log[("supplier_cost_missing", supplier_node, product_id)] += 1
            return 0.0, "CNY"
        for w, price, cur in reversed(entries):
            if w <= week:
                return price, cur
        self.lookup_log[("supplier_cost_before_first_rule_week", supplier_node, product_id)] += 1
        return entries[0][1], entries[0][2]

    # ------------------------------------------------------------------
    # Node Cost Rules
    # ------------------------------------------------------------------
    def get_node_costs(self, node_id: str, product_id: str) -> pd.DataFrame:
        """Return all cost rules for a node+product combination."""
        return self._node_cost_cache.get(
            (node_id, product_id),
            self.node_cost_rule.iloc[0:0]
        )

    # ------------------------------------------------------------------
    # Edge Cost Rules
    # ------------------------------------------------------------------
    def get_edge_costs(self, edge_id: str, product_id: str) -> pd.DataFrame:
        """Return all cost rules for an edge+product combination."""
        return self._edge_cost_cache.get(
            (edge_id, product_id),
            self.edge_cost_rule.iloc[0:0]
        )

    # ------------------------------------------------------------------
    # Tariff Rules
    # ------------------------------------------------------------------
    def get_tariff(self, edge_id: str, product_id: str) -> Optional[pd.Series]:
        """Return tariff rule row or None if no tariff on this edge."""
        return self._tariff_cache.get((edge_id, product_id))

    # ------------------------------------------------------------------
    # Transfer Price Rule
    # ------------------------------------------------------------------
    def get_transfer_price_rule(self, mom_node: str, product_id: str) -> Optional[pd.Series]:
        """Return transfer price rule row or None."""
        return self._tp_rule_cache.get((mom_node, product_id))

    # ------------------------------------------------------------------
    # Node Profit Zone
    # ------------------------------------------------------------------
    def get_profit_zone(self, node_id: str, product_id: str) -> str:
        """Return profit_zone_role for a node, or OPERATION_NODE_COST_BASE if not found."""
        return self._profit_zone_cache.get((node_id, product_id), "OPERATION_NODE_COST_BASE")

    def get_country(self, node_id: str, product_id: str) -> str:
        """Return country code for a node."""
        return self._country_cache.get((node_id, product_id), "")
