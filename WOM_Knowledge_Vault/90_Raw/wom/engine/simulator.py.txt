"""
WOMSimulator – top-level orchestrator.
"""
from __future__ import annotations
import os, time
from typing import Optional
import pandas as pd
from wom.config import WOMConfig
from wom.data.loader import WOMInputs
from wom.data.schema import Cols
from wom.engine.demand import DemandEngine
from wom.engine.capacity import CapacityEngine
from wom.engine.inventory import InventorySimulator
from wom.engine.scenario import ScenarioManager
from wom.engine.money import evaluate_money, build_scenario_money_kpi
from wom.engine.management import analyze_all_scenarios


class WOMSimulator:
    def __init__(self, config: WOMConfig):
        self.config = config
        self._inputs: Optional[WOMInputs] = None
        self._demand_engine   = DemandEngine(config)
        self._capacity_engine = CapacityEngine(config)
        self._inv_simulator   = InventorySimulator(config)
        self.scenario_manager = ScenarioManager()
        self._sku_params: dict = {}

    def load(self, inputs: WOMInputs) -> None:
        self._inputs = inputs
        self._demand_engine.load(inputs.demand_forecast, inputs.sku_master)
        self._capacity_engine.load(inputs.capacity_plan)
        for _, row in inputs.sku_master.iterrows():
            key = (row[Cols.SKU_ID], row[Cols.REGION])
            self._sku_params[key] = {
                "ss_wks":        row[Cols.SS_WKS] or self.config.safety_stock_weeks,
                "lt_wks":        int(row[Cols.LT_WKS]) or self.config.lead_time_weeks,
                "order_mult":    row[Cols.ORDER_MULT] or self.config.order_multiple,
                "max_order_qty": row[Cols.MAX_ORDER_QTY],
            }
        self._opening_inv: dict = {}
        self._initial_on_order: dict = {}
        for _, row in inputs.inventory_master.iterrows():
            key = (row[Cols.SKU_ID], row[Cols.REGION])
            self._opening_inv[key] = float(row[Cols.ON_HAND])
            oo = float(row[Cols.ON_ORDER])
            receipt_wk = row[Cols.FIRST_RECEIPT]
            if oo > 0 and receipt_wk:
                idx = self.config.week_index(receipt_wk)
                if idx is not None:
                    self._initial_on_order[key] = (oo, idx)

    def run(self, verbose: bool = True) -> ScenarioManager:
        if self._inputs is None:
            raise RuntimeError("Call .load(inputs) before .run()")
        all_keys = self._demand_engine.keys()
        for scenario in self.config.scenarios:
            t0 = time.time()
            if verbose:
                print(f"  ▶ Scenario: {scenario.name:12s}  "
                      f"(demand ×{scenario.demand_multiplier:.2f}  "
                      f"supply ×{scenario.supply_multiplier:.2f})")
            demand_arrays = {
                key: self._demand_engine.get_demand(key[0], key[1], scenario)
                for key in all_keys
            }
            avg_demand = {
                key: self._demand_engine.avg_weekly_demand(key[0], key[1])
                for key in all_keys
            }
            cap_state = self._capacity_engine.for_scenario(scenario)
            result_df = self._inv_simulator.simulate(
                scenario_name=scenario.name,
                demand_arrays=demand_arrays,
                avg_demand=avg_demand,
                opening_inv=self._opening_inv,
                initial_on_order=self._initial_on_order,
                sku_params=self._sku_params,
                capacity_state=cap_state,
            )
            unit_costs = {
                (r[Cols.SKU_ID], r[Cols.REGION]): float(r[Cols.UNIT_COST])
                for _, r in self._inputs.sku_master.iterrows()
            }
            result_df[Cols.INV_VALUE] = result_df.apply(
                lambda x: x[Cols.CLOSING_INV] * unit_costs.get(
                    (x[Cols.SKU_ID], x[Cols.REGION]), 0.0),
                axis=1,
            ).round(2)
            self.scenario_manager.add(scenario.name, result_df)
            elapsed = time.time() - t0
            rows = len(result_df)
            if verbose:
                fill = result_df[Cols.FILL_RATE].mean()
                so   = result_df[Cols.STOCKOUT_QTY].sum()
                print(f"    ✔ {rows:,} rows  |  avg fill rate: {fill:.1%}  |  "
                      f"total stockout: {so:,.0f}  ({elapsed:.2f}s)")

        # Money PSI evaluation
        if verbose:
            print("\n  ▶ Evaluating Money PSI ...")
        combined = self.scenario_manager.combined()
        weekly_money, summary_money = evaluate_money(combined, self._inputs.sku_master)
        scenario_money_kpi = build_scenario_money_kpi(summary_money)
        self.scenario_manager.weekly_money = weekly_money
        self.scenario_manager.summary_money = summary_money
        self.scenario_manager.scenario_money_kpi = scenario_money_kpi

        # Management Issue Analysis
        ops_kpi = self.scenario_manager.kpi_summary()
        mgmt_results = analyze_all_scenarios(scenario_money_kpi, scenario_ops_kpi=ops_kpi)
        self.scenario_manager.management_results = mgmt_results
        if verbose:
            for scen, res in mgmt_results.items():
                print(f"    {scen}: {len(res.issues)} issues, {len(res.risks)} risks")

        return self.scenario_manager

    def demand_coverage_report(self) -> pd.DataFrame:
        return self._demand_engine.coverage_report()

    def summary(self) -> str:
        lines = [str(self.config)]
        if self._inputs:
            lines.append(self._inputs.summary())
        return "\n".join(lines)
