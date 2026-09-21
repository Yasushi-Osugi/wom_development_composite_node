---
tags: [wom, code]
---
# wom/ppc/ppc_rules.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/ppc/ppc_rules.py) · [原文テキスト](../../../90_Raw/wom/ppc/ppc_rules.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/04_Evaluation|Evaluation]]

## モジュール説明（docstring原文）

```text
wom/ppc/ppc_rules.py
====================
Rule master loader for PPC Simulation Engine.

Loads all CSV master files and provides typed lookup helpers.
No business logic here — pure data access layer.
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| ClassDef | `PPCRuleSet` | 20 | Complete set of PPC rule masters loaded from CSV files. |
| FunctionDef | `__post_init__` | 49 | Pre-build all lookup dicts to avoid per-call DataFrame filtering. |
| FunctionDef | `load` | 103 | Load all CSV masters from data_dir, falling back to fallback_dir for missing files. |
| FunctionDef | `get_market_price` | 156 | Return (price, currency) for a market node in a given week. |
| FunctionDef | `get_supplier_cost` | 172 | Return (purchase_price, currency) for a supplier in a given week. |
| FunctionDef | `get_node_costs` | 188 | Return all cost rules for a node+product combination. |
| FunctionDef | `get_edge_costs` | 198 | Return all cost rules for an edge+product combination. |
| FunctionDef | `get_tariff` | 208 | Return tariff rule row or None if no tariff on this edge. |
| FunctionDef | `get_transfer_price_rule` | 215 | Return transfer price rule row or None. |
| FunctionDef | `get_profit_zone` | 222 | Return profit_zone_role for a node, or OPERATION_NODE_COST_BASE if not found. |
| FunctionDef | `get_country` | 226 | Return country code for a node. |
| FunctionDef | `_read` | 105 | docstringなし（下のコード参照） |

## 全文（コメント・原文を省略せず収録）

````python
"""
wom/ppc/ppc_rules.py
====================
Rule master loader for PPC Simulation Engine.

Loads all CSV master files and provides typed lookup helpers.
No business logic here — pure data access layer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import pandas as pd


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
    def load(cls, data_dir: str, fallback_dir: str = "data/ppc") -> "PPCRuleSet":
        """Load all CSV masters from data_dir, falling back to fallback_dir for missing files."""
        def _read(name: str) -> pd.DataFrame:
            path = os.path.join(data_dir, name)
            if os.path.exists(path):
                return pd.read_csv(path, dtype=str)
            if fallback_dir and fallback_dir != data_dir:
                fb_path = os.path.join(fallback_dir, name)
                if os.path.exists(fb_path):
                    print(f"[PPC Rules] {name}: model-local not found, using fallback ({fallback_dir})")
                    return pd.read_csv(fb_path, dtype=str)
            raise FileNotFoundError(f"PPC rule CSV not found: {path}")

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
            return 0.0, "JPY"
        for w, price, cur in reversed(entries):
            if w <= week:
                return price, cur
        return entries[0][1], entries[0][2]

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
            return 0.0, "CNY"
        for w, price, cur in reversed(entries):
            if w <= week:
                return price, cur
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

````
