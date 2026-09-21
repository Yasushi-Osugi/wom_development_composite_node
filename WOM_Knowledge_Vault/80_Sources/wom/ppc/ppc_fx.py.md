---
tags: [wom, code]
---
# wom/ppc/ppc_fx.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/ppc/ppc_fx.py) · [原文テキスト](../../../90_Raw/wom/ppc/ppc_fx.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[10_Functions/04_Evaluation|Evaluation]]

## モジュール説明（docstring原文）

```text
wom/ppc/ppc_fx.py
=================
FX (Foreign Exchange) rate lookup and conversion for PPC engine.

Design Decision D1 (Rev.2):
    - Every PPCEvent carries amount_local, currency, fx_rate, amount_base.
    - Rate applied is the weekly rate for the event's own week.
    - If a week has no rate, fall back to the latest PRIOR week with a warning.
    - Base currency is a run-time parameter (default: JPY).
    - Base currency amounts are always 1:1 (rate = 1.0).
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| ClassDef | `FXConverter` | 21 | Loads ppc_fx_rate.csv and provides week-aware currency conversion. |
| FunctionDef | `__init__` | 33 | docstringなし（下のコード参照） |
| FunctionDef | `get_rate` | 50 | Return (rate, is_fallback). |
| FunctionDef | `convert` | 83 | Convert amount_local in `currency` to base currency. |
| FunctionDef | `from_csv` | 98 | docstringなし（下のコード参照） |

## 全文（コメント・原文を省略せず収録）

````python
"""
wom/ppc/ppc_fx.py
=================
FX (Foreign Exchange) rate lookup and conversion for PPC engine.

Design Decision D1 (Rev.2):
    - Every PPCEvent carries amount_local, currency, fx_rate, amount_base.
    - Rate applied is the weekly rate for the event's own week.
    - If a week has no rate, fall back to the latest PRIOR week with a warning.
    - Base currency is a run-time parameter (default: JPY).
    - Base currency amounts are always 1:1 (rate = 1.0).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import pandas as pd


class FXConverter:
    """
    Loads ppc_fx_rate.csv and provides week-aware currency conversion.

    Parameters
    ----------
    fx_df : pd.DataFrame
        Columns: week, currency, base_currency, rate
    base_currency : str
        Base currency for all amount_base fields (default "JPY").
    """

    def __init__(self, fx_df: pd.DataFrame, base_currency: str = "JPY"):
        self.base_currency = base_currency

        # Build lookup: (week, currency) → rate
        # Filter only rows where base_currency matches our chosen base
        sub = fx_df[fx_df["base_currency"] == base_currency].copy()
        self._rates: Dict[Tuple[str, str], float] = {}
        for _, row in sub.iterrows():
            self._rates[(str(row["week"]), str(row["currency"]))] = float(row["rate"])

        # Sorted unique weeks for fallback lookup
        self._weeks_sorted = sorted({k[0] for k in self._rates})

        # Track fallback warnings (lot_id → warning message) for event ledger
        self.fallback_warnings: list = []

    # ------------------------------------------------------------------
    def get_rate(self, week: str, currency: str) -> Tuple[float, bool]:
        """
        Return (rate, is_fallback).

        If currency == base_currency: returns (1.0, False).
        If exact week found: returns (rate, False).
        If not found: returns (latest prior week rate, True).
        Raises ValueError if no rate available at all.
        """
        if currency == self.base_currency:
            return 1.0, False

        key = (week, currency)
        if key in self._rates:
            return self._rates[key], False

        # Fallback: find latest prior week
        prior = [w for w in self._weeks_sorted if w <= week]
        for w in reversed(prior):
            fallback_key = (w, currency)
            if fallback_key in self._rates:
                self.fallback_warnings.append(
                    f"FX FALLBACK: week={week} currency={currency} "
                    f"→ used rate from {w}"
                )
                return self._rates[fallback_key], True

        raise ValueError(
            f"No FX rate found for currency={currency!r} on or before week={week!r}. "
            f"Add a row to ppc_fx_rate.csv."
        )

    # ------------------------------------------------------------------
    def convert(
        self, amount_local: float, currency: str, week: str
    ) -> Tuple[float, float]:
        """
        Convert amount_local in `currency` to base currency.

        Returns
        -------
        (fx_rate, amount_base)
        """
        rate, is_fallback = self.get_rate(week, currency)
        return rate, amount_local * rate

    # ------------------------------------------------------------------
    @classmethod
    def from_csv(cls, csv_path: str, base_currency: str = "JPY") -> "FXConverter":
        df = pd.read_csv(csv_path, dtype=str)
        df["rate"] = df["rate"].astype(float)
        return cls(df, base_currency)

````
