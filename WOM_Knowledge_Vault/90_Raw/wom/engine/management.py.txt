"""
WOM Management Issue Analyzer  –  Management Layer

Compares scenario money KPIs against the Base scenario and generates:
  - ManagementIssue  : confirmed degradation (要対応)
  - ManagementRisk   : potential / early-warning risk (要注意)
  - narrative        : Japanese-language executive summary

Mirrors the spirit of pysi/reporting/management_issue_analyzer.py
but is self-contained (no dependency on the GitHub repo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np

from wom.data.schema import Cols


# ──────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ManagementIssue:
    """Confirmed management issue (degradation vs Base)."""
    code: str                   # e.g. "PROFIT_DECLINE"
    severity: str               # "HIGH" | "MEDIUM" | "LOW"
    title_ja: str               # Short Japanese title
    detail_ja: str              # Japanese explanation with numbers
    scenario: str = ""
    delta_pct: float = 0.0      # % change vs Base (negative = worse)


@dataclass
class ManagementRisk:
    """Early-warning / potential risk."""
    code: str
    severity: str
    title_ja: str
    detail_ja: str
    scenario: str = ""


@dataclass
class ManagementAnalysisResult:
    issues: list[ManagementIssue] = field(default_factory=list)
    risks:  list[ManagementRisk]  = field(default_factory=list)
    narrative: str = ""


# ──────────────────────────────────────────────────────────────────────
# Thresholds
# ──────────────────────────────────────────────────────────────────────

THRESHOLDS = {
    # (issue_pct, risk_pct)  — negative = deterioration threshold
    "revenue":      (-0.05, -0.02),   # -5% = issue, -2% = risk
    "gross_profit": (-0.08, -0.03),
    "gross_margin": (-0.03, -0.01),   # absolute percentage-point drop
    "stockout":     ( 0.20,  0.10),   # +20% = issue (positive = worse for stockout)
    "fill_rate":    (-0.03, -0.01),   # -3pp = issue
    "inv_value":    ( 0.30,  0.15),   # +30% bloat = issue
    "ccc":          ( 2.0,   1.0),    # +2 weeks = issue
}


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def analyze_management_delta(
    base_money: dict,
    scenario_money: dict,
    base_ops: Optional[dict] = None,
    scenario_ops: Optional[dict] = None,
    scenario_name: str = "",
) -> ManagementAnalysisResult:
    """
    Compare scenario KPIs against base and produce issues/risks/narrative.

    Parameters
    ----------
    base_money, scenario_money : dicts with keys:
        revenue, cogs, gross_profit, gross_margin, ccc_wks,
        ar_value, ap_value, inv_value
    base_ops, scenario_ops (optional): dicts with keys:
        total_stockout, avg_fill_rate
    scenario_name : name of the scenario being evaluated

    Returns
    -------
    ManagementAnalysisResult
    """
    issues: list[ManagementIssue] = []
    risks:  list[ManagementRisk]  = []

    def _delta_pct(base_val, scen_val):
        if abs(base_val) < 1e-9:
            return 0.0
        return (scen_val - base_val) / abs(base_val)

    # ── 1. Revenue ───────────────────────────────────────────────────
    rev_b  = base_money.get("revenue", 0)
    rev_s  = scenario_money.get("revenue", 0)
    rev_d  = _delta_pct(rev_b, rev_s)
    thr_i, thr_r = THRESHOLDS["revenue"]

    if rev_d <= thr_i:
        issues.append(ManagementIssue(
            code="REVENUE_DECLINE", severity="HIGH",
            title_ja="売上高の悪化",
            detail_ja=f"売上高が基準比 {rev_d*100:+.1f}% 減少しています（基準: {rev_b:,.0f} → シナリオ: {rev_s:,.0f}）。需要減少または欠品拡大が主因として疑われます。",
            scenario=scenario_name, delta_pct=rev_d,
        ))
    elif rev_d <= thr_r:
        risks.append(ManagementRisk(
            code="REVENUE_RISK", severity="MEDIUM",
            title_ja="売上高の軽度低下リスク",
            detail_ja=f"売上高に {rev_d*100:+.1f}% の低下傾向が見られます。早期モニタリングを推奨します。",
            scenario=scenario_name,
        ))

    # ── 2. Gross Profit ──────────────────────────────────────────────
    gp_b = base_money.get("gross_profit", 0)
    gp_s = scenario_money.get("gross_profit", 0)
    gp_d = _delta_pct(gp_b, gp_s)
    thr_i, thr_r = THRESHOLDS["gross_profit"]

    if gp_d <= thr_i:
        issues.append(ManagementIssue(
            code="PROFIT_DECLINE", severity="HIGH",
            title_ja="粗利益の悪化",
            detail_ja=f"粗利益が基準比 {gp_d*100:+.1f}% 低下しています（基準: {gp_b:,.0f} → シナリオ: {gp_s:,.0f}）。コスト構造または販売ミックスの見直しが必要です。",
            scenario=scenario_name, delta_pct=gp_d,
        ))
    elif gp_d <= thr_r:
        risks.append(ManagementRisk(
            code="PROFIT_RISK", severity="MEDIUM",
            title_ja="粗利益の軽度低下リスク",
            detail_ja=f"粗利益に {gp_d*100:+.1f}% の低下傾向が見られます。",
            scenario=scenario_name,
        ))

    # ── 3. Gross Margin rate (absolute pp change) ───────────────────
    gm_b = base_money.get("gross_margin", 0)
    gm_s = scenario_money.get("gross_margin", 0)
    gm_abs_d = gm_s - gm_b   # absolute pp
    thr_i, thr_r = THRESHOLDS["gross_margin"]

    if gm_abs_d <= thr_i:
        issues.append(ManagementIssue(
            code="MARGIN_DECLINE", severity="MEDIUM",
            title_ja="粗利率の悪化",
            detail_ja=f"粗利率が {gm_abs_d*100:+.1f}pp 低下しています（基準: {gm_b*100:.1f}% → シナリオ: {gm_s*100:.1f}%）。価格圧力またはコスト上昇が疑われます。",
            scenario=scenario_name, delta_pct=gm_abs_d,
        ))
    elif gm_abs_d <= thr_r:
        risks.append(ManagementRisk(
            code="MARGIN_RISK", severity="LOW",
            title_ja="粗利率の軽度低下リスク",
            detail_ja=f"粗利率に {gm_abs_d*100:+.1f}pp の低下傾向が見られます。",
            scenario=scenario_name,
        ))

    # ── 4. CCC ───────────────────────────────────────────────────────
    ccc_b = base_money.get("ccc_wks", 0)
    ccc_s = scenario_money.get("ccc_wks", 0)
    ccc_d = ccc_s - ccc_b   # weeks increase (positive = worse)
    thr_i, thr_r = THRESHOLDS["ccc"]

    if ccc_d >= thr_i:
        issues.append(ManagementIssue(
            code="CCC_DETERIORATION", severity="MEDIUM",
            title_ja="CCC（キャッシュ・コンバージョン・サイクル）の悪化",
            detail_ja=f"CCC が {ccc_d:+.1f} 週悪化しています（基準: {ccc_b:.1f}週 → シナリオ: {ccc_s:.1f}週）。在庫滞留または回収遅延の可能性があります。",
            scenario=scenario_name, delta_pct=ccc_d,
        ))
    elif ccc_d >= thr_r:
        risks.append(ManagementRisk(
            code="CCC_RISK", severity="LOW",
            title_ja="CCC 悪化リスク",
            detail_ja=f"CCC が {ccc_d:+.1f} 週増加傾向です。運転資本の推移をモニタリングしてください。",
            scenario=scenario_name,
        ))

    # ── 5. Inventory bloat ───────────────────────────────────────────
    inv_b = base_money.get("inv_value", 0)
    inv_s = scenario_money.get("inv_value", 0)
    inv_d = _delta_pct(inv_b, inv_s)
    thr_i, thr_r = THRESHOLDS["inv_value"]

    if inv_d >= thr_i:
        issues.append(ManagementIssue(
            code="INVENTORY_BLOAT", severity="MEDIUM",
            title_ja="在庫評価額の過剰増加",
            detail_ja=f"在庫評価額が {inv_d*100:+.1f}% 増加しています（基準: {inv_b:,.0f} → シナリオ: {inv_s:,.0f}）。過剰発注または需要減による滞留在庫が懸念されます。",
            scenario=scenario_name, delta_pct=inv_d,
        ))
    elif inv_d >= thr_r:
        risks.append(ManagementRisk(
            code="INVENTORY_RISK", severity="LOW",
            title_ja="在庫滞留リスク",
            detail_ja=f"在庫評価額に {inv_d*100:+.1f}% の増加傾向が見られます。",
            scenario=scenario_name,
        ))

    # ── 6. Ops: Stockout & Fill Rate ─────────────────────────────────
    if base_ops and scenario_ops:
        so_b = base_ops.get("total_stockout", 0)
        so_s = scenario_ops.get("total_stockout", 0)
        so_d = _delta_pct(so_b + 1e-9, so_s)   # avoid div/0 when base=0
        thr_i, thr_r = THRESHOLDS["stockout"]

        if so_d >= thr_i:
            issues.append(ManagementIssue(
                code="STOCKOUT_INCREASE", severity="HIGH",
                title_ja="欠品数量の大幅増加",
                detail_ja=f"欠品数量が {so_d*100:+.1f}% 増加しています（{so_b:,.0f} → {so_s:,.0f}）。サービス率の悪化により顧客離れのリスクがあります。",
                scenario=scenario_name, delta_pct=so_d,
            ))
        elif so_d >= thr_r:
            risks.append(ManagementRisk(
                code="STOCKOUT_RISK", severity="MEDIUM",
                title_ja="欠品増加リスク",
                detail_ja=f"欠品数量が {so_d*100:+.1f}% 増加傾向です。",
                scenario=scenario_name,
            ))

        fr_b = base_ops.get("avg_fill_rate", 1.0)
        fr_s = scenario_ops.get("avg_fill_rate", 1.0)
        fr_d = fr_s - fr_b
        thr_i, thr_r = THRESHOLDS["fill_rate"]

        if fr_d <= thr_i:
            issues.append(ManagementIssue(
                code="FILLRATE_DECLINE", severity="HIGH",
                title_ja="サービス率（充足率）の低下",
                detail_ja=f"サービス率が {fr_d*100:+.1f}pp 低下しています（基準: {fr_b*100:.1f}% → シナリオ: {fr_s*100:.1f}%）。",
                scenario=scenario_name, delta_pct=fr_d,
            ))
        elif fr_d <= thr_r:
            risks.append(ManagementRisk(
                code="FILLRATE_RISK", severity="LOW",
                title_ja="サービス率の軽度低下リスク",
                detail_ja=f"サービス率に {fr_d*100:+.1f}pp の低下傾向が見られます。",
                scenario=scenario_name,
            ))

        # ── 7. Revenue opportunity (positive upsides) ─────────────
        if rev_d >= 0.05:
            risks.append(ManagementRisk(
                code="REVENUE_UPSIDE", severity="LOW",
                title_ja="収益拡大機会",
                detail_ja=f"このシナリオでは売上高が基準比 {rev_d*100:+.1f}% 増加しています。供給能力の確保と在庫投資の適正化を検討してください。",
                scenario=scenario_name,
            ))

    # ── Build narrative ──────────────────────────────────────────────
    narrative = _build_narrative(scenario_name, issues, risks,
                                 base_money, scenario_money)

    return ManagementAnalysisResult(issues=issues, risks=risks, narrative=narrative)


# ──────────────────────────────────────────────────────────────────────
# Narrative builder
# ──────────────────────────────────────────────────────────────────────

def _build_narrative(
    scenario_name: str,
    issues: list[ManagementIssue],
    risks:  list[ManagementRisk],
    base_money: dict,
    scenario_money: dict,
) -> str:
    lines = [f"【{scenario_name} シナリオ 経営分析サマリー】\n"]

    rev_d = _pct_diff(base_money.get("revenue", 0), scenario_money.get("revenue", 0))
    gp_d  = _pct_diff(base_money.get("gross_profit", 0), scenario_money.get("gross_profit", 0))
    gm_b  = base_money.get("gross_margin", 0) * 100
    gm_s  = scenario_money.get("gross_margin", 0) * 100
    ccc_b = base_money.get("ccc_wks", 0)
    ccc_s = scenario_money.get("ccc_wks", 0)

    lines.append(
        f"▶ 売上高: 基準比 {rev_d:+.1f}%　"
        f"| 粗利益: 基準比 {gp_d:+.1f}%　"
        f"| 粗利率: {gm_b:.1f}% → {gm_s:.1f}%　"
        f"| CCC: {ccc_b:.1f}週 → {ccc_s:.1f}週\n"
    )

    high = [i for i in issues if i.severity == "HIGH"]
    med  = [i for i in issues if i.severity == "MEDIUM"]

    if not issues and not risks:
        lines.append("✅ 主要KPIに重大な懸念事項は検出されませんでした。")
    else:
        if high:
            lines.append(f"🔴 重要課題 ({len(high)}件):")
            for i in high:
                lines.append(f"  ・{i.title_ja}")
        if med:
            lines.append(f"🟡 中程度の課題 ({len(med)}件):")
            for i in med:
                lines.append(f"  ・{i.title_ja}")
        if risks:
            sev_risks = sorted(risks, key=lambda r: ["HIGH","MEDIUM","LOW"].index(r.severity))
            lines.append(f"⚪ 注意事項 ({len(sev_risks)}件):")
            for r in sev_risks[:3]:
                lines.append(f"  ・{r.title_ja}")

    lines.append("\n（本分析はルールベース自動分析です。経営判断には追加調査が必要です。）")
    return "\n".join(lines)


def _pct_diff(base_val, scen_val):
    if abs(base_val) < 1e-9:
        return 0.0
    return (scen_val - base_val) / abs(base_val) * 100


# ──────────────────────────────────────────────────────────────────────
# Convenience: analyze all non-Base scenarios from ScenarioManager
# ──────────────────────────────────────────────────────────────────────

def analyze_all_scenarios(
    scenario_money_kpi: pd.DataFrame,
    scenario_ops_kpi: Optional[pd.DataFrame] = None,
    base_scenario: str = "Base",
) -> dict[str, ManagementAnalysisResult]:
    """
    Analyze all non-Base scenarios and return a dict of results.

    Parameters
    ----------
    scenario_money_kpi : output of build_scenario_money_kpi()
    scenario_ops_kpi   : output of ScenarioManager.kpi_summary() (optional)
    base_scenario      : name of the baseline scenario (default "Base")

    Returns
    -------
    dict mapping scenario_name -> ManagementAnalysisResult
    """
    base_row = scenario_money_kpi[scenario_money_kpi[Cols.SCENARIO] == base_scenario]
    if base_row.empty:
        # Fallback: use first scenario as base
        base_row = scenario_money_kpi.iloc[:1]

    base_money = _row_to_money_dict(base_row.iloc[0])
    results = {}

    for _, row in scenario_money_kpi.iterrows():
        scen = row[Cols.SCENARIO]
        if scen == base_scenario:
            continue
        scen_money = _row_to_money_dict(row)

        # Ops KPIs (optional)
        base_ops = scen_ops = None
        if scenario_ops_kpi is not None:
            b = scenario_ops_kpi[scenario_ops_kpi[Cols.SCENARIO] == base_scenario]
            s = scenario_ops_kpi[scenario_ops_kpi[Cols.SCENARIO] == scen]
            if not b.empty and not s.empty:
                base_ops = _row_to_ops_dict(b.groupby(Cols.SCENARIO).sum().reset_index().iloc[0])
                scen_ops = _row_to_ops_dict(s.groupby(Cols.SCENARIO).sum().reset_index().iloc[0])

        results[scen] = analyze_management_delta(
            base_money, scen_money, base_ops, scen_ops, scenario_name=scen
        )

    return results


def _row_to_money_dict(row) -> dict:
    return {
        "revenue":       float(row.get(Cols.REVENUE,       0) or 0),
        "cogs":          float(row.get(Cols.COGS,          0) or 0),
        "gross_profit":  float(row.get(Cols.GROSS_PROFIT,  0) or 0),
        "gross_margin":  float(row.get(Cols.GROSS_MARGIN,  0) or 0),
        "ccc_wks":       float(row.get(Cols.CCC_WKS,       0) or 0),
        "ar_value":      float(row.get(Cols.AR_VALUE,       0) or 0),
        "ap_value":      float(row.get(Cols.AP_VALUE,       0) or 0),
        "inv_value":     float(row.get(Cols.INV_VALUE_COST, 0) or 0),
    }


def _row_to_ops_dict(row) -> dict:
    return {
        "total_stockout": float(row.get("total_stockout", 0) or 0),
        "avg_fill_rate":  float(row.get("avg_fill_rate",  1) or 1),
    }
