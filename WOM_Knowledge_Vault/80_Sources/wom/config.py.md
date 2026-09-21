---
tags: [wom, code]
---
# wom/config.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/config.py) · [原文テキスト](../../90_Raw/wom/config.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## モジュール説明（docstring原文）

```text
WOMConfig – Planning horizon and global parameters.
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| FunctionDef | `_iso_week_to_date` | 13 | Convert 'YYYY-WNN' to the Monday of that ISO week. |
| FunctionDef | `_date_to_iso_week` | 19 | docstringなし（下のコード参照） |
| ClassDef | `ScenarioSpec` | 25 | Definition of a planning scenario. |
| ClassDef | `WOMConfig` | 38 | Master configuration for a WOM planning run. |
| FunctionDef | `__post_init__` | 32 | docstringなし（下のコード参照） |
| FunctionDef | `weeks` | 82 | Return ordered list of ISO week strings for the planning horizon. |
| FunctionDef | `week_dates` | 91 | Return list of Monday dates for each planning week. |
| FunctionDef | `week_index` | 96 | Return 0-based index of *iso_week* in the horizon, or None. |
| FunctionDef | `to_dict` | 107 | docstringなし（下のコード参照） |
| FunctionDef | `from_dict` | 124 | docstringなし（下のコード参照） |
| FunctionDef | `from_json` | 132 | docstringなし（下のコード参照） |
| FunctionDef | `to_json` | 136 | docstringなし（下のコード参照） |
| FunctionDef | `__str__` | 140 | docstringなし（下のコード参照） |

## 全文（コメント・原文を省略せず収録）

````python
"""
WOMConfig – Planning horizon and global parameters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional


def _iso_week_to_date(iso_week: str) -> date:
    """Convert 'YYYY-WNN' to the Monday of that ISO week."""
    year, week = iso_week.split("-W")
    return date.fromisocalendar(int(year), int(week), 1)


def _date_to_iso_week(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


@dataclass
class ScenarioSpec:
    """Definition of a planning scenario."""
    name: str
    demand_multiplier: float = 1.0          # scales all demand forecasts
    supply_multiplier: float = 1.0          # scales capacity/receipts
    description: str = ""

    def __post_init__(self):
        if self.demand_multiplier <= 0 or self.supply_multiplier <= 0:
            raise ValueError("Multipliers must be > 0")


@dataclass
class WOMConfig:
    """
    Master configuration for a WOM planning run.

    Parameters
    ----------
    start_week : str
        First planning week in 'YYYY-WNN' format (e.g. '2024-W01').
    num_weeks : int
        Number of weekly buckets in the planning horizon (default 26).
    safety_stock_weeks : float
        Global default safety stock expressed as weeks of demand cover
        (can be overridden per SKU in the master data).
    lead_time_weeks : int
        Global default procurement / replenishment lead time in weeks.
    order_multiple : float
        Minimum order quantity multiple (MOQ multiple). 1.0 = no constraint.
    capacity_constrained : bool
        When True the simulator caps replenishment orders at available
        capacity. When False, supply is unconstrained.
    scenarios : list[ScenarioSpec]
        Scenarios to simulate. Defaults to Base / Upside (+20%) / Downside (-20%).
    output_dir : str
        Directory where reports are written.
    """

    start_week: str = "2024-W01"
    num_weeks: int = 26
    safety_stock_weeks: float = 2.0
    lead_time_weeks: int = 4
    order_multiple: float = 1.0
    capacity_constrained: bool = True
    scenarios: List[ScenarioSpec] = field(default_factory=lambda: [
        ScenarioSpec("Base",     1.00, 1.00, "Base plan"),
        ScenarioSpec("Upside",   1.20, 1.00, "Demand +20%"),
        ScenarioSpec("Downside", 0.80, 1.00, "Demand -20%"),
    ])
    output_dir: str = "output"

    # ------------------------------------------------------------------ #
    #  Derived helpers                                                     #
    # ------------------------------------------------------------------ #

    @property
    def weeks(self) -> List[str]:
        """Return ordered list of ISO week strings for the planning horizon."""
        start = _iso_week_to_date(self.start_week)
        return [
            _date_to_iso_week(start + timedelta(weeks=i))
            for i in range(self.num_weeks)
        ]

    @property
    def week_dates(self) -> List[date]:
        """Return list of Monday dates for each planning week."""
        start = _iso_week_to_date(self.start_week)
        return [start + timedelta(weeks=i) for i in range(self.num_weeks)]

    def week_index(self, iso_week: str) -> Optional[int]:
        """Return 0-based index of *iso_week* in the horizon, or None."""
        try:
            return self.weeks.index(iso_week)
        except ValueError:
            return None

    # ------------------------------------------------------------------ #
    #  Serialisation                                                       #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        return {
            "start_week": self.start_week,
            "num_weeks": self.num_weeks,
            "safety_stock_weeks": self.safety_stock_weeks,
            "lead_time_weeks": self.lead_time_weeks,
            "order_multiple": self.order_multiple,
            "capacity_constrained": self.capacity_constrained,
            "scenarios": [
                {"name": s.name, "demand_multiplier": s.demand_multiplier,
                 "supply_multiplier": s.supply_multiplier, "description": s.description}
                for s in self.scenarios
            ],
            "output_dir": self.output_dir,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WOMConfig":
        scenarios = [ScenarioSpec(**s) for s in d.pop("scenarios", [])] or None
        obj = cls(**{k: v for k, v in d.items() if k != "scenarios"})
        if scenarios:
            obj.scenarios = scenarios
        return obj

    @classmethod
    def from_json(cls, path: str) -> "WOMConfig":
        with open(path) as f:
            return cls.from_dict(json.load(f))

    def to_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def __str__(self) -> str:
        scen_names = ", ".join(s.name for s in self.scenarios)
        return (
            f"WOMConfig | {self.start_week} + {self.num_weeks}w | "
            f"SS={self.safety_stock_weeks}w LT={self.lead_time_weeks}w | "
            f"Scenarios: [{scen_names}]"
        )

````
