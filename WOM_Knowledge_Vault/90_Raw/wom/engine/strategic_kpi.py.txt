"""
WOM Strategic KPI Engine  –  Strategic Layer

Computes lot-based operational KPIs from a post-planning SCTree.
These KPIs reflect the "cost structure sustainability" and
"operational stability" objectives of WOM's design philosophy.

KPIs
----
1. Fixed Cost Coverage Rate  (固定費吸収率)
     = Σ P_lots / Σ CapHard  (nodes with CapHard > 0)
     Target ≥ 0.75 | Warning < 0.60
     Interpretation: how well fixed capacity is being absorbed.
     Under-absorption = fixed cost per unit rises.

2. Production Leveling Index  (生産平準化指数)
     = 1 - CoV(weekly_production)  where CoV = σ/μ
     Target ≥ 0.80 | Warning < 0.60
     Interpretation: stability of production volumes week-over-week.
     High variance → labour/machine surge costs, social disruption.

3. Buffer Retention Rate  (在庫滞留率)
     = node-weeks with I_count > 0 / total node-weeks
     Target 0.20–0.50 | Warning > 0.70 (over-accumulation)
     Interpretation: fraction of time/nodes holding buffer stock.
     Too high → capital tied up; too low → stockout risk.

4. SC Fill Rate  (需要充足率)
     = Σ leaf_out psi4supply[S] / Σ leaf_out psi4demand[S]
     Target ≥ 0.95 | Warning < 0.85
     Interpretation: share of final demand fulfilled on time.

5. Capacity Utilisation  (平均設備稼働率)
     = mean(P_lots / CapHard) over all constrained (node, week) pairs
     Target 0.70–0.90 | Warning < 0.60 or > 0.95
     Interpretation: average loading of constrained resources.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from wom.model.plan_node import (
    P, S, I,
    NODE_TYPE_LEAF_OUT,
    NODE_TYPE_MOM,
)


# ──────────────────────────────────────────────────────────────────────
# Data class
# ──────────────────────────────────────────────────────────────────────

@dataclass
class StrategicKPI:
    """Strategic-layer KPIs derived from a post-planning SCTree."""

    # Core KPIs (0–1 range, or 0–1+ for coverage)
    fixed_cost_coverage: float = 0.0   # target ≥ 0.75
    production_leveling: float = 0.0   # target ≥ 0.80
    buffer_retention: float = 0.0      # target 0.20–0.50
    fill_rate: float = 0.0             # target ≥ 0.95
    avg_cap_utilization: float = 0.0   # target 0.70–0.90

    # Context
    n_weeks: int = 0
    n_products: int = 0
    n_constrained_nodes: int = 0       # nodes with CapHard > 0 in any week

    def status_fixed_cost_coverage(self) -> str:
        """Return 'OK', 'WARN', or 'ISSUE'."""
        v = self.fixed_cost_coverage
        if v >= 0.75:
            return "OK"
        if v >= 0.60:
            return "WARN"
        return "ISSUE"

    def status_production_leveling(self) -> str:
        v = self.production_leveling
        if v >= 0.80:
            return "OK"
        if v >= 0.60:
            return "WARN"
        return "ISSUE"

    def status_buffer_retention(self) -> str:
        v = self.buffer_retention
        if 0.20 <= v <= 0.50:
            return "OK"
        if 0.10 <= v <= 0.65:
            return "WARN"
        return "ISSUE"

    def status_fill_rate(self) -> str:
        v = self.fill_rate
        if v >= 0.95:
            return "OK"
        if v >= 0.85:
            return "WARN"
        return "ISSUE"

    def status_cap_utilization(self) -> str:
        v = self.avg_cap_utilization
        if 0.70 <= v <= 0.90:
            return "OK"
        if 0.55 <= v <= 0.95:
            return "WARN"
        return "ISSUE"

    def overall_status(self) -> str:
        statuses = [
            self.status_fixed_cost_coverage(),
            self.status_production_leveling(),
            self.status_buffer_retention(),
            self.status_fill_rate(),
            self.status_cap_utilization(),
        ]
        if "ISSUE" in statuses:
            return "ISSUE"
        if "WARN" in statuses:
            return "WARN"
        return "OK"

    def to_narrative_ja(self) -> str:
        """Short Japanese summary of strategic KPI status."""
        lines = ["【Strategic KPI サマリー】\n"]
        lines.append(
            f"▶ 固定費吸収率: {self.fixed_cost_coverage:.1%}  "
            f"| 生産平準化: {self.production_leveling:.1%}  "
            f"| 在庫滞留率: {self.buffer_retention:.1%}\n"
            f"▶ 需要充足率: {self.fill_rate:.1%}  "
            f"| 設備稼働率: {self.avg_cap_utilization:.1%}  "
            f"| 製品数: {self.n_products}  週数: {self.n_weeks}\n"
        )
        issues = []
        if self.status_fixed_cost_coverage() == "ISSUE":
            issues.append(f"  🔴 固定費吸収率 {self.fixed_cost_coverage:.1%} — 目標 75%未満。生産量不足により固定費の未吸収が発生しています。")
        elif self.status_fixed_cost_coverage() == "WARN":
            issues.append(f"  🟡 固定費吸収率 {self.fixed_cost_coverage:.1%} — やや低め。稼働水準の引き上げを検討してください。")

        if self.status_production_leveling() == "ISSUE":
            issues.append(f"  🔴 生産平準化指数 {self.production_leveling:.1%} — 週次生産量のばらつきが大きく、人員・設備の負荷集中が懸念されます。")
        elif self.status_production_leveling() == "WARN":
            issues.append(f"  🟡 生産平準化指数 {self.production_leveling:.1%} — 平準化余地があります。需要変動バッファの最適化を検討してください。")

        if self.status_buffer_retention() == "ISSUE":
            v = self.buffer_retention
            if v > 0.65:
                issues.append(f"  🔴 在庫滞留率 {v:.1%} — バッファ在庫の過剰滞留。運転資本の圧迫リスクがあります。")
            else:
                issues.append(f"  🔴 在庫滞留率 {v:.1%} — バッファ不足。欠品リスクが高まっています。")
        elif self.status_buffer_retention() == "WARN":
            issues.append(f"  🟡 在庫滞留率 {self.buffer_retention:.1%} — 適正範囲（20–50%）の外縁です。")

        if self.status_fill_rate() == "ISSUE":
            issues.append(f"  🔴 需要充足率 {self.fill_rate:.1%} — 目標 95%未満。顧客サービス水準の改善が急務です。")
        elif self.status_fill_rate() == "WARN":
            issues.append(f"  🟡 需要充足率 {self.fill_rate:.1%} — 目標水準まであと一歩です。")

        if self.status_cap_utilization() == "ISSUE":
            v = self.avg_cap_utilization
            if v > 0.90:
                issues.append(f"  🔴 設備稼働率 {v:.1%} — 過負荷。突発対応余力がなく、生産遅延リスクが高い状態です。")
            else:
                issues.append(f"  🔴 設備稼働率 {v:.1%} — 過少稼働。固定費回収の観点から稼働率向上が必要です。")
        elif self.status_cap_utilization() == "WARN":
            issues.append(f"  🟡 設備稼働率 {self.avg_cap_utilization:.1%} — 適正稼働範囲（70–90%）の外縁です。")

        if not issues:
            lines.append("✅ 全 Strategic KPI が目標範囲内です。")
        else:
            lines.extend(issues)

        lines.append("\n（Strategic KPI は Planning Engine 実行後に更新されます）")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def compute_strategic_kpi(
    sc_tree,
    product_filter: Optional[str] = None,
) -> StrategicKPI:
    """
    Compute Strategic KPIs from a post-planning SCTree.

    Parameters
    ----------
    sc_tree : SCTree
        Must have been processed by BackwardPlanner + ForwardPlanner.
        Reads psi4supply, psi4demand, and cap_hard() from all nodes.
    product_filter : if given (and not "All"), only this product's nodes
        are included — lets the Management tab show per-SKU Strategic KPI
        instead of the all-products blend.

    Returns
    -------
    StrategicKPI
    """
    products = sc_tree.products
    if product_filter and product_filter != "All":
        products = [p for p in products if p == product_filter]
    if not products:
        return StrategicKPI()

    n_weeks = 0

    # Accumulators ─────────────────────────────────────────────────────
    # 1. Fixed cost coverage + 5. Cap utilization
    total_p_lots: float = 0.0
    total_cap_hard: float = 0.0
    cap_util_values: list[float] = []
    constrained_node_ids: set[str] = set()

    # 2. Production leveling (MOM nodes only, sum across per week)
    weekly_prod: Optional[list[float]] = None

    # 3. Buffer retention
    buffer_node_weeks = 0
    total_node_weeks = 0

    # 4. Fill rate (leaf_out nodes only)
    total_demand_lots = 0
    total_fulfilled_lots = 0

    for prod_nm in products:
        for node in sc_tree.iter_all_nodes(prod_nm):
            nw = len(node.psi4supply)
            if nw == 0:
                continue

            if n_weeks == 0:
                n_weeks = nw
                weekly_prod = [0.0] * nw
            elif nw > n_weeks:
                # extend if needed
                weekly_prod.extend([0.0] * (nw - n_weeks))
                n_weeks = nw

            for w in range(nw):
                p_count = len(node.psi4supply[w][P])
                i_count = len(node.psi4supply[w][I])
                ch = node.cap_hard(w)

                # Buffer retention: every (node, week)
                total_node_weeks += 1
                if i_count > 0:
                    buffer_node_weeks += 1

                # Capacity-constrained nodes
                if ch > 0.0:
                    total_p_lots += p_count
                    total_cap_hard += ch
                    util = min(float(p_count) / ch, 1.5)  # cap at 150%
                    cap_util_values.append(util)
                    constrained_node_ids.add(node.node_id)

                # Production leveling: MOM nodes
                if node.node_type == NODE_TYPE_MOM and weekly_prod is not None:
                    if w < len(weekly_prod):
                        weekly_prod[w] += p_count

            # Fill rate: leaf_out only
            if node.node_type == NODE_TYPE_LEAF_OUT:
                for w in range(nw):
                    total_demand_lots    += len(node.psi4demand[w][S])
                    total_fulfilled_lots += len(node.psi4supply[w][S])

    # ── Compute indices ───────────────────────────────────────────────

    # 1. Fixed Cost Coverage
    if total_cap_hard > 0.0:
        fixed_cost_coverage = min(total_p_lots / total_cap_hard, 1.5)
    else:
        # No CapHard set → planning ran unconstrained
        # Use MOM P-bucket fill as proxy (assume target = n_weeks × 1 lot/wk)
        fixed_cost_coverage = 0.0

    # 2. Production Leveling: 1 - CoV  (higher = more level)
    if weekly_prod:
        arr = np.array([v for v in weekly_prod if v > 0], dtype=float)
        if len(arr) >= 2 and arr.mean() > 0:
            cov = arr.std() / arr.mean()
            production_leveling = float(max(0.0, 1.0 - cov))
        elif len(arr) >= 1:
            production_leveling = 1.0   # all production in one week — not necessarily bad
        else:
            production_leveling = 0.0
    else:
        production_leveling = 0.0

    # 3. Buffer Retention
    buffer_retention = (
        float(buffer_node_weeks) / total_node_weeks
        if total_node_weeks > 0 else 0.0
    )

    # 4. Fill Rate
    fill_rate = (
        float(total_fulfilled_lots) / total_demand_lots
        if total_demand_lots > 0 else 0.0
    )
    fill_rate = min(fill_rate, 1.0)

    # 5. Avg Cap Utilization
    avg_cap_utilization = (
        float(np.mean(cap_util_values))
        if cap_util_values else 0.0
    )

    return StrategicKPI(
        fixed_cost_coverage=fixed_cost_coverage,
        production_leveling=production_leveling,
        buffer_retention=buffer_retention,
        fill_rate=fill_rate,
        avg_cap_utilization=avg_cap_utilization,
        n_weeks=n_weeks,
        n_products=len(products),
        n_constrained_nodes=len(constrained_node_ids),
    )
