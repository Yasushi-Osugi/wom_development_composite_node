"""
WOM Landed Cost Engine  —  Phase 1
===================================

Adds tariff_rate and FX adjustment to per-route cost calculation.
Enables Trump-tariff / KD-production / reroute scenario comparison
without changing the underlying lot-based planning model.

Calculation model
-----------------
revenue / cogs come from the WOM money engine already expressed in the
model's own reporting currency (whatever sku_master selling_price/unit_cost
use — JPY, THB, etc.). freight_usd_per_lot and assembly_cost_usd_per_lot are
quoted in USD (per their column names) and must be converted via fx_rate
(reporting_ccy per USD) before combining with cogs. tariff_rate and lot_count
need no such conversion.

For each WOM scenario row in scenario_money_kpi (revenue, cogs, units, ...):

  1. Collect all RouteProfiles for the chosen LC scenario (Phase 1: blended
     equally across routes; volume-weighting is Phase 2).
  2. Apply tariff:
       customs_duty  = cogs × blended_tariff_rate
  3. Add freight (USD → reporting currency):
       freight_total = freight_usd_per_lot × lot_count × blended_fx_rate
  4. Add KD assembly cost, if any route is product_type == "parts"
     (USD → reporting currency):
       assembly_total = assembly_cost_usd_per_lot × lot_count × blended_fx_rate
  5. Landed Gross Profit:
       landed_cogs = cogs + customs_duty + freight_total + assembly_total
       landed_gp   = revenue - landed_cogs
       landed_gm   = landed_gp / revenue  (if revenue > 0)
  6. Tariff burden %:
       tariff_burden_pct = customs_duty / revenue

Limitations (Phase 1)
---------------------
- Route blending is a simple average across all routes in the scenario,
  not volume-weighted by actual SKU×region shipments (Phase 2)
- Transfer pricing is not modelled (Phase 3)
- CIF vs FOB distinction is simplified to freight included in COGS
- Intra-company elimination is not applied (Phase 3)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class RouteProfile:
    """Cost parameters for one (src_region, dst_region) lane."""
    src_region: str
    dst_region: str
    tariff_rate: float = 0.0          # 0–1  (e.g., 0.25 = 25 %)
    fx_rate: float = 1.0              # reporting_ccy per trade_ccy
    src_currency: str = "USD"
    dst_currency: str = "USD"
    freight_usd_per_lot: float = 0.0  # flat freight cost per lot
    notes: str = ""


@dataclass
class LandedCostScenario:
    """Named set of RouteProfiles."""
    name: str
    profiles: List[RouteProfile] = field(default_factory=list)

    def get_profile(
        self, src_region: str, dst_region: str
    ) -> Optional[RouteProfile]:
        """Return the first matching RouteProfile, or None."""
        for p in self.profiles:
            if p.src_region == src_region and p.dst_region == dst_region:
                return p
        return None


@dataclass
class RouteAssignment:
    """Maps (sku_id, region) → (src_region, dst_region, hs_code, assembly_cost)."""
    sku_id: str
    region: str
    src_region: str
    dst_region: str
    hs_code: str = ""
    product_type: str = "finished_goods"  # "finished_goods" | "parts"
    assembly_cost_usd_per_lot: float = 0.0


# ──────────────────────────────────────────────────────────────────────
# Loaders
# ──────────────────────────────────────────────────────────────────────

def load_edge_cost_master(path: str) -> Dict[str, LandedCostScenario]:
    """
    Load edge_cost_master.csv into a dict of LandedCostScenario.

    CSV columns:
        scenario, src_region, dst_region, tariff_rate, fx_rate,
        src_currency, dst_currency, freight_usd_per_lot, [notes]
    """
    df = pd.read_csv(path)
    scenarios: Dict[str, LandedCostScenario] = {}

    for _, row in df.iterrows():
        scen_name = str(row["scenario"])
        if scen_name not in scenarios:
            scenarios[scen_name] = LandedCostScenario(name=scen_name)
        profile = RouteProfile(
            src_region=str(row["src_region"]),
            dst_region=str(row["dst_region"]),
            tariff_rate=float(row.get("tariff_rate", 0.0) or 0.0),
            fx_rate=float(row.get("fx_rate", 1.0) or 1.0),
            src_currency=str(row.get("src_currency", "USD") or "USD"),
            dst_currency=str(row.get("dst_currency", "USD") or "USD"),
            freight_usd_per_lot=float(row.get("freight_usd_per_lot", 0.0) or 0.0),
            notes=str(row.get("notes", "") or ""),
        )
        scenarios[scen_name].profiles.append(profile)

    return scenarios


def load_route_master(path: str) -> List[RouteAssignment]:
    """
    Load route_master.csv into a list of RouteAssignment.

    CSV columns:
        sku_id, region, src_region, dst_region, hs_code,
        product_type, assembly_cost_usd_per_lot
    """
    df = pd.read_csv(path)
    assignments = []
    for _, row in df.iterrows():
        assignments.append(RouteAssignment(
            sku_id=str(row["sku_id"]),
            region=str(row["region"]),
            src_region=str(row["src_region"]),
            dst_region=str(row["dst_region"]),
            hs_code=str(row.get("hs_code", "") or ""),
            product_type=str(row.get("product_type", "finished_goods") or "finished_goods"),
            assembly_cost_usd_per_lot=float(row.get("assembly_cost_usd_per_lot", 0.0) or 0.0),
        ))
    return assignments


def build_route_index(
    assignments: List[RouteAssignment],
) -> Dict[Tuple[str, str], RouteAssignment]:
    """Build (sku_id, region) → RouteAssignment lookup dict."""
    return {(a.sku_id, a.region): a for a in assignments}


# ──────────────────────────────────────────────────────────────────────
# Core calculation
# ──────────────────────────────────────────────────────────────────────

def compute_landed_cost_kpi(
    scenario_money_kpi: pd.DataFrame,
    lc_scenario: LandedCostScenario,
    route_index: Dict[Tuple[str, str], RouteAssignment],
    cpu_size_default: float = 1.0,
    sku_id: Optional[str] = None,
) -> pd.DataFrame:
    """
    Compute landed-cost-adjusted KPIs for one LandedCostScenario.

    Parameters
    ----------
    scenario_money_kpi : output of build_scenario_money_kpi()
        One row per WOM scenario with revenue, cogs, gross_profit,
        gross_margin, inv_value, ar_value, ap_value, ccc_wks, units
        (units = total demand_fulfilled lots for the scenario).
    lc_scenario : LandedCostScenario to apply. To scope this to a single
        SKU, pre-filter it with filter_scenario_by_sku() first — this
        function itself blends across whatever profiles it's given.
    route_index : (sku_id, region) → RouteAssignment mapping.
    cpu_size_default : lots per unit (default 1). Currently unused —
        lot_count comes directly from scenario_money_kpi["units"];
        kept for backward-compatible call signatures.
    sku_id : if given, only route_index entries for this sku_id are used
        for the KD-assembly-cost aggregation (None/"All" = every route,
        existing behavior).

    Returns
    -------
    DataFrame with columns:
        wom_scenario, lc_scenario,
        revenue, cogs, customs_duty, freight_total, assembly_total,
        landed_cogs, landed_gross_profit, landed_gross_margin,
        tariff_burden_pct, fx_gain_loss (retired, always 0),
        [revenue/cogs/etc. in the model's own reporting currency]
    """
    rows = []

    for _, kpi_row in scenario_money_kpi.iterrows():
        wom_scen = kpi_row.get("scenario", "")
        revenue  = float(kpi_row.get("revenue", 0) or 0)
        cogs     = float(kpi_row.get("cogs",    0) or 0)
        gp       = float(kpi_row.get("gross_profit", 0) or 0)

        # Aggregate tariff / freight across all routes that contributed
        # to this WOM scenario.  We use COGS as a proxy for trade value.
        # Split COGS proportionally across routes using route_index keys.
        # (Simplified: apply a blended rate across all registered routes)

        # Collect all routes in this LC scenario
        profiles = lc_scenario.profiles
        if not profiles:
            # No route data → return unadjusted
            rows.append(_no_adjustment_row(wom_scen, lc_scenario.name,
                                           revenue, cogs, gp))
            continue

        # Blended tariff / FX across routes (weighted equally — Phase 1 simplification)
        # In Phase 2, weight by SKU×region volume
        n = len(profiles)
        blended_tariff = sum(p.tariff_rate for p in profiles) / n
        blended_fx     = sum(p.fx_rate     for p in profiles) / n
        blended_freight_per_lot = sum(p.freight_usd_per_lot for p in profiles) / n

        # Actual lot count, supplied by build_scenario_money_kpi() as "units"
        # (sum of demand_fulfilled across the scenario). Falls back to the old
        # revenue/1000 proxy only if an older caller doesn't provide "units"
        # (that proxy assumed ~$1000 revenue per lot, which only happens to
        # hold for the iPhone model and silently breaks for any other
        # currency/price scale — e.g. it inflated a ~300-lot EV scenario into
        # 75 million "lots").
        lot_count = float(kpi_row.get("units", 0) or 0)
        if lot_count <= 0:
            lot_count = max(revenue / 1000.0, 1.0)  # legacy proxy fallback

        # revenue / cogs are already expressed in the model's own reporting
        # currency (JPY, THB, etc. — whatever sku_master price/cost use).
        # freight_usd_per_lot / assembly_cost_usd_per_lot are quoted in USD
        # (per their column names), so they need blended_fx (reporting_ccy
        # per USD, e.g. 145 JPY/USD or 35 THB/USD) to convert into reporting
        # currency before combining with cogs. Previously this code also
        # applied "(blended_fx - 1.0) * cogs" as a "fx_gain_loss" adjustment,
        # which assumed fx_rate was a ratio near 1.0 — but fx_rate here is an
        # absolute exchange rate, so that term swung landed_cogs by ~34x-144x
        # cogs and produced nonsensical Landed GM% (e.g. 1129%). Removed.
        customs_duty   = cogs * blended_tariff
        freight_total  = blended_freight_per_lot * lot_count * blended_fx
        # Assembly cost: sum from route assignments if product_type=="parts".
        # Scoped to sku_id's own routes when given, so a per-SKU Landed Cost
        # view doesn't pick up KD-assembly cost that belongs to other SKUs.
        scoped_routes = (
            [ra for (sid, _region), ra in route_index.items() if sid == sku_id]
            if sku_id else list(route_index.values())
        )
        assembly_total = 0.0
        for ra in scoped_routes:
            if ra.assembly_cost_usd_per_lot > 0:
                assembly_total += (ra.assembly_cost_usd_per_lot * blended_fx
                                   * (lot_count / max(len(scoped_routes), 1)))

        landed_cogs = cogs + customs_duty + freight_total + assembly_total
        landed_gp   = revenue - landed_cogs
        landed_gm   = landed_gp / revenue if revenue > 0 else 0.0
        tariff_burden_pct = customs_duty / revenue if revenue > 0 else 0.0

        rows.append({
            "wom_scenario":       wom_scen,
            "lc_scenario":        lc_scenario.name,
            "revenue":            round(revenue, 0),
            "cogs":               round(cogs, 0),
            "customs_duty":       round(customs_duty, 0),
            "freight_total":      round(freight_total, 0),
            "assembly_total":     round(assembly_total, 0),
            "fx_gain_loss":       0,  # retired; see comment above landed_cogs calc
            "landed_cogs":        round(landed_cogs, 0),
            "landed_gross_profit":round(landed_gp, 0),
            "landed_gross_margin":round(landed_gm, 4),
            "tariff_burden_pct":  round(tariff_burden_pct, 4),
            "original_gross_margin": round(float(kpi_row.get("gross_margin", 0) or 0), 4),
            "margin_impact_pp":   round(landed_gm - float(kpi_row.get("gross_margin", 0) or 0), 4),
        })

    return pd.DataFrame(rows)


def _no_adjustment_row(wom_scen, lc_scen, revenue, cogs, gp):
    gm = gp / revenue if revenue > 0 else 0.0
    return {
        "wom_scenario": wom_scen, "lc_scenario": lc_scen,
        "revenue": revenue, "cogs": cogs,
        "customs_duty": 0, "freight_total": 0,
        "assembly_total": 0, "fx_gain_loss": 0,
        "landed_cogs": cogs, "landed_gross_profit": gp,
        "landed_gross_margin": gm, "tariff_burden_pct": 0,
        "original_gross_margin": gm, "margin_impact_pp": 0,
    }


# ──────────────────────────────────────────────────────────────────────
# Scenario comparison
# ──────────────────────────────────────────────────────────────────────

def filter_scenario_by_sku(
    lc_scenario: LandedCostScenario,
    route_index: Dict[Tuple[str, str], RouteAssignment],
    sku_id: Optional[str],
) -> LandedCostScenario:
    """
    Scope a LandedCostScenario down to only the routes used by sku_id.

    route_master.csv assigns each (sku_id, region) to a (src_region,
    dst_region) lane; this keeps only the edge_cost_master.csv profiles
    matching those lanes, so a per-SKU Landed Cost view for e.g.
    Cookie_Local doesn't get blended with Cookie_Import's CN→JP profile.

    Returns the original (unfiltered) scenario unchanged when sku_id is
    None/"All", or when no routes are registered for it (safe fallback —
    preserves existing all-SKU blended behavior).
    """
    if not sku_id or sku_id == "All":
        return lc_scenario
    lanes = {
        (ra.src_region, ra.dst_region)
        for (sid, _region), ra in route_index.items()
        if sid == sku_id
    }
    if not lanes:
        return lc_scenario
    scoped_profiles = [
        p for p in lc_scenario.profiles
        if (p.src_region, p.dst_region) in lanes
    ]
    if not scoped_profiles:
        return lc_scenario
    return LandedCostScenario(name=lc_scenario.name, profiles=scoped_profiles)


def compare_lc_scenarios(
    scenario_money_kpi: pd.DataFrame,
    lc_scenarios: Dict[str, LandedCostScenario],
    route_index: Dict[Tuple[str, str], RouteAssignment],
    cpu_size_default: float = 1.0,
    sku_id: Optional[str] = None,
) -> pd.DataFrame:
    """
    Run compute_landed_cost_kpi for all LC scenarios and stack results.

    Pass sku_id to scope both the route blending (via
    filter_scenario_by_sku) and the KD-assembly cost lookup to that SKU's
    own registered routes. scenario_money_kpi should already be filtered/
    aggregated to that SKU (e.g. via a SKU-filtered summary_money row
    passed through build_scenario_money_kpi) — this function does not
    filter scenario_money_kpi itself.

    Returns a DataFrame with one row per (wom_scenario × lc_scenario).
    """
    frames = []
    for lc_name, lc_scen in lc_scenarios.items():
        scoped_scen = filter_scenario_by_sku(lc_scen, route_index, sku_id)
        df = compute_landed_cost_kpi(
            scenario_money_kpi, scoped_scen, route_index, cpu_size_default,
            sku_id=sku_id,
        )
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ──────────────────────────────────────────────────────────────────────
# Narrative builder
# ──────────────────────────────────────────────────────────────────────

def build_lc_narrative(comparison_df: pd.DataFrame,
                       base_lc: str = "Base",
                       currency_symbol: str = "$") -> str:
    """Build Japanese executive summary of landed cost scenario comparison.

    currency_symbol: prefix for money amounts so the narrative matches the
    run's reporting currency (e.g. "¥" for a JPY-base model). Defaults to
    "$" for backward compatibility with USD-base cases."""
    lines = ["【Landed Cost シナリオ分析サマリー】\n"]

    base_rows = comparison_df[comparison_df["lc_scenario"] == base_lc]
    if base_rows.empty:
        return "（Base シナリオデータなし）"

    base_gm  = base_rows["landed_gross_margin"].mean()
    base_rev = base_rows["revenue"].sum()

    for lc_scen in comparison_df["lc_scenario"].unique():
        if lc_scen == base_lc:
            continue
        scen_rows = comparison_df[comparison_df["lc_scenario"] == lc_scen]
        scen_gm   = scen_rows["landed_gross_margin"].mean()
        scen_duty = scen_rows["customs_duty"].sum()
        scen_rev  = scen_rows["revenue"].sum()
        margin_chg = (scen_gm - base_gm) * 100
        duty_pct   = scen_duty / scen_rev * 100 if scen_rev > 0 else 0

        icon = "🔴" if margin_chg < -2 else ("🟡" if margin_chg < 0 else "🟢")
        lines.append(
            f"{icon} [{lc_scen}]  粗利率変化: {margin_chg:+.1f}pp  "
            f"| 関税負担: {duty_pct:.1f}%  "
            f"| 関税額合計: {currency_symbol}{scen_duty:,.0f}"
        )

    lines.append("\n（関税・為替シナリオは Planning Engine 実行後に更新されます）")
    return "\n".join(lines)
