---
tags: [wom, code]
---
# wom/engine/scenario.py

静的コード資料（実行検証ではない）。

[GitHub原本・固定SHA](https://github.com/Yasushi-Osugi/wom_development_composite_node/blob/7d6c7d734ebdcb7b213bab3116ca59d3d4935f55/wom/engine/scenario.py) · [原文テキスト](../../../90_Raw/wom/engine/scenario.py.txt)

基準: `7d6c7d734ebdcb7b213bab3116ca59d3d4935f55`。[[00_Start/Source_Policy|出典と読み方]]

関連機能: [[00_Start/Source_Index|資料総覧]]

## モジュール説明（docstring原文）

```text
Scenario manager - compares simulation results across multiple scenarios.
```

## 定義一覧（静的抽出）

| 種別 | 名前 | 行 | 説明の先頭行 |
|---|---|---:|---|
| ClassDef | `ScenarioManager` | 10 | docstringなし（下のコード参照） |
| FunctionDef | `__init__` | 11 | docstringなし（下のコード参照） |
| FunctionDef | `add` | 24 | docstringなし（下のコード参照） |
| FunctionDef | `scenarios` | 27 | docstringなし（下のコード参照） |
| FunctionDef | `get` | 30 | docstringなし（下のコード参照） |
| FunctionDef | `combined` | 33 | docstringなし（下のコード参照） |
| FunctionDef | `kpi_summary` | 36 | docstringなし（下のコード参照） |
| FunctionDef | `weekly_summary` | 59 | docstringなし（下のコード参照） |
| FunctionDef | `delta_vs_base` | 73 | docstringなし（下のコード参照） |
| FunctionDef | `at_risk_skus` | 86 | docstringなし（下のコード参照） |

## 関連する知識源

- [[80_Sources/wom/data/schema.py|wom/data/schema.py]]

## 全文（コメント・原文を省略せず収録）

````python
"""
Scenario manager - compares simulation results across multiple scenarios.
"""
from __future__ import annotations
from typing import Dict, List, Optional
import pandas as pd
from wom.data.schema import Cols


class ScenarioManager:
    def __init__(self):
        self._results: Dict[str, pd.DataFrame] = {}
        # Money PSI (populated by WOMSimulator after run)
        self.weekly_money: Optional[pd.DataFrame] = None
        self.summary_money: Optional[pd.DataFrame] = None
        self.scenario_money_kpi: Optional[pd.DataFrame] = None
        self.management_results: dict = {}
        self.strategic_kpi = None   # StrategicKPI (set after Planning Engine run)
        # Kept for by-SKU Management tab recompute without a full re-run:
        self.sc_tree = None                  # SCTree (post-planning)
        self.lc_scens: dict = {}             # name -> LandedCostScenario
        self.route_idx: dict = {}            # (sku_id, region) -> RouteAssignment

    def add(self, scenario_name: str, df: pd.DataFrame) -> None:
        self._results[scenario_name] = df.copy()

    def scenarios(self) -> List[str]:
        return list(self._results.keys())

    def get(self, scenario_name: str) -> pd.DataFrame:
        return self._results[scenario_name]

    def combined(self) -> pd.DataFrame:
        return pd.concat(list(self._results.values()), ignore_index=True)

    def kpi_summary(self, by=None) -> pd.DataFrame:
        if by is None:
            by = [Cols.SCENARIO, Cols.SKU_ID, Cols.REGION]
        df = self.combined()
        agg = (
            df.groupby(by)
            .agg(
                total_demand=(Cols.DEMAND_FCST, "sum"),
                total_fulfilled=(Cols.DEMAND_FULFILLED, "sum"),
                total_stockout=(Cols.STOCKOUT_QTY, "sum"),
                avg_fill_rate=(Cols.FILL_RATE, "mean"),
                avg_closing_inv=(Cols.CLOSING_INV, "mean"),
                avg_inv_cover_wks=(Cols.INV_COVER_WKS, "mean"),
                total_reorder_qty=(Cols.REORDER_QTY, "sum"),
                max_stockout_wk=(Cols.STOCKOUT_QTY, "max"),
            )
            .reset_index()
        )
        agg["overall_fill_rate"] = (
            agg["total_fulfilled"] / agg["total_demand"].replace(0, float("nan"))
        ).fillna(1.0).round(4)
        return agg

    def weekly_summary(self) -> pd.DataFrame:
        df = self.combined()
        return (
            df.groupby([Cols.SCENARIO, Cols.WEEK])
            .agg(
                total_demand=(Cols.DEMAND_FCST, "sum"),
                total_fulfilled=(Cols.DEMAND_FULFILLED, "sum"),
                total_stockout=(Cols.STOCKOUT_QTY, "sum"),
                total_closing_inv=(Cols.CLOSING_INV, "sum"),
                total_reorder_qty=(Cols.REORDER_QTY, "sum"),
            )
            .reset_index()
        )

    def delta_vs_base(self, scenario_name, base_name="Base", kpi_cols=None):
        if kpi_cols is None:
            kpi_cols = [
                Cols.DEMAND_FCST, Cols.CLOSING_INV,
                Cols.STOCKOUT_QTY, Cols.FILL_RATE, Cols.INV_COVER_WKS,
            ]
        key_cols = [Cols.SKU_ID, Cols.REGION, Cols.WEEK]
        base = self._results[base_name].set_index(key_cols)[kpi_cols]
        comp = self._results[scenario_name].set_index(key_cols)[kpi_cols]
        delta_abs = (comp - base).add_suffix("_delta")
        delta_pct = ((comp - base) / base.replace(0, float("nan"))).add_suffix("_pct_chg")
        return pd.concat([base, comp, delta_abs, delta_pct], axis=1).reset_index()

    def at_risk_skus(self, fill_rate_threshold=0.95, cover_wks_threshold=1.0, scenario=None):
        scenarios = [scenario] if scenario else list(self._results.keys())
        frames = []
        for s in scenarios:
            df = self._results[s]
            risk = df[
                (df[Cols.FILL_RATE] < fill_rate_threshold) |
                ((df[Cols.INV_COVER_WKS] < cover_wks_threshold) & (df[Cols.DEMAND_FCST] > 0))
            ].copy()
            risk[Cols.SCENARIO] = s
            frames.append(risk)
        if not frames:
            return pd.DataFrame()
        return (
            pd.concat(frames)
            .sort_values([Cols.SCENARIO, Cols.SKU_ID, Cols.REGION, Cols.WEEK])
            .reset_index(drop=True)
        )

````
