"""
wom/ppc/ppc_runner.py
=====================
High-level runner: PSI → PPC engine → CSV/JSON export.
"""

from __future__ import annotations

import os
import warnings
from typing import Dict, List, Optional

import pandas as pd

from .ppc_psi_bridge import psi_to_sales_records, summarize_psi_records
from .ppc_rules import PPCRuleSet, PPCRuleSources, resolve_ppc_rules
from .ppc_engine import (PPCSimulationEngine,
                          build_smartphone_vs_paths,
                          build_smartphone_global_vs_paths,
                          build_rice_vs_paths,
                          build_cookie_vs_paths,
                          detect_scenario)
from .ppc_export import export_results

# Valuation status of a PPC result (RequestLetter_PPC_NoSilentFallback B.2, D8)
VAL_DONE = "評価済み"         # every sales record valued with the model's rules
VAL_PARTIAL = "一部未評価"    # some product x market records had no rule: excluded
VAL_NONE = "未評価"           # rule files missing, or no record could be valued

# files a PPC run writes (ppc_export.export_results); removed at the start of a run
# so that a run that ends "未評価" leaves no previous plan's amounts behind
PPC_OUTPUT_FILES = ["ppc_event_ledger.csv", "ppc_node_week_summary.csv",
                    "ppc_profit_zone_summary.csv", "ppc_lot_reconciliation.csv",
                    "ppc_node_pl_summary.csv", "ppc_kpi_summary.json", "ppc_warnings.csv"]


def clear_ppc_outputs(output_dir: str) -> None:
    for name in PPC_OUTPUT_FILES:
        try:
            os.remove(os.path.join(output_dir, name))
        except OSError:
            pass


def _excluded_rows(sales: pd.DataFrame, cpu_size: float, reason: str) -> List[dict]:
    """Excluded product x market: PPC record count, WOM lot count, physical qty."""
    out = []
    for (p, c), g in sales.groupby(["product_id", "channel_node"]):
        qty = float(g["qty"].sum())
        out.append({"product_id": p, "channel_node": c, "reason": reason,
                    "ppc_records": int(len(g)),
                    "wom_lots": int(round(qty / cpu_size)) if cpu_size else None,
                    "qty": qty})
    return out


def run_ppc_from_psi(
    sc_tree,
    weeks: List[str],
    data_dir: str = "data/ppc",
    output_dir: str = "output/ppc",
    channel_map: Optional[Dict[str, str]] = None,
    product_id_map: Optional[Dict[str, str]] = None,
    base_currency: str = "JPY",
    verbose: bool = False,
    use_node_name: bool = False,
    run_info: Optional[dict] = None,
    rule_sources: Optional[PPCRuleSources] = None,
) -> dict:
    """
    Run the full PPC Simulation pipeline using PSI leaf-out quantities.

    rule_sources (RequestLetter_PPC_NoSilentFallback B.1): where each rule file
        comes from (`resolve_ppc_rules(model_dir)`). When None, `data_dir` is
        resolved the same way (its own files, plus a shared folder only if it
        declares one) -- nothing is read from data/ppc silently.
    The result carries `valuation_status` (B.2): 評価済み / 一部未評価 (records of
    a product x market without a price, or a product without a supplier cost,
    are excluded and listed) / 未評価 (rule files missing, or nothing valued:
    no amounts are written). Sample sales data are never used here (K4; the
    demo `python -m wom.ppc` keeps them).

    run_info (RequestLetter_StalePPC P1): {"run_id": ..., "model_dir": ...} of
        the planning run this PPC run belongs to. When given, the output folder
        is marked with ppc_run_info.json AFTER all files are written, so that a
        reader can check that the files are the result of that run (see
        wom/ppc/ppc_run_info.py). When None (headless runner, tests) no mark is
        written and the output files are exactly as before.

    Returned dict (P3): the KPI summary plus
        "_psi_mode"     True when amounts were computed from the plan's records
        "sales_source"  "psi" (sample data are no longer substituted)
    (these two keys are not written to ppc_kpi_summary.json).
    """
    from .ppc_run_info import (clear_run_info, write_run_info, SALES_PSI)
    import datetime as _dt
    import json as _json
    clear_run_info(output_dir)      # the folder is about to be overwritten
    clear_ppc_outputs(output_dir)   # no previous plan's amounts may remain (B.2)
    warnings.filterwarnings("ignore")
    src = rule_sources if rule_sources is not None else resolve_ppc_rules(data_dir)
    cpu = float(getattr(sc_tree, "cpu_size", 1) or 1) if sc_tree is not None else 1.0

    def _mark(status, extra):
        if run_info:
            write_run_info(output_dir, {
                "run_id": run_info.get("run_id", ""),
                "model_dir": run_info.get("model_dir", ""),
                "sales_source": SALES_PSI,
                "valuation_status": status,
                "reason": extra.get("reason", ""),
                "rule_sources": src.record(),
                "data_dir": src.rule_dir_for("ppc_market_price.csv"),
                "base_currency": base_currency,
                "first_week": weeks[0] if weeks else "",
                "n_weeks": len(weeks),
                "lot_flow_mode": getattr(sc_tree, "lot_flow_mode", None),
                "finished_at": _dt.datetime.now().isoformat(timespec="seconds"),
            })

    def _not_valued(reason, excluded=None):
        """未評価: no amounts. ppc_kpi_summary.json carries the status only."""
        body = {"valuation_status": VAL_NONE, "reason": reason, "base_currency": base_currency,
                "rule_sources": src.record(), "excluded": excluded or []}
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "ppc_kpi_summary.json"), "w", encoding="utf-8") as f:
            _json.dump(body, f, ensure_ascii=False, indent=2)
        _mark(VAL_NONE, body)
        if verbose:
            print(f"[PPC Runner] 財務：未評価（{reason}）")
        return dict(body, _psi_mode=False, sales_source=SALES_PSI)

    # ── Step 1: Load PPC rules (B.1: one resolver, no silent switch) ──────
    if verbose:
        print(f"[PPC Runner] Rules: {src.sources}  missing: {src.missing}")
    if src.missing:
        reason = "規則のファイルが無い（共有の規則の宣言も無い）: " + ", ".join(src.missing)
        # also say which planned products the rules that ARE there do not know
        if sc_tree is not None and "ppc_supplier_cost.csv" in src.paths:
            try:
                known = set(pd.read_csv(src.paths["ppc_supplier_cost.csv"], dtype=str)["product_id"].dropna())
                unknown = [p for p in sc_tree.products if p not in known]
                if unknown:
                    reason += "；製品が規則に無い: " + ", ".join(unknown)
            except Exception:
                pass
        return _not_valued(reason)
    rules = PPCRuleSet.load_from_sources(src)
    data_dir = src.rule_dir_for("ppc_market_price.csv")

    known_products = {p for p in rules.supplier_cost["product_id"].unique() if isinstance(p, str)}

    # ── Step 2: PSI → sales_records ───────────────────────────────────────
    sales = psi_to_sales_records(
        sc_tree, weeks,
        channel_map=channel_map,
        product_id_map=product_id_map,
        use_node_name=use_node_name,
    )
    if verbose:
        print(f"[PPC Runner] PSI bridge: {summarize_psi_records(sales)}")
    if sales.empty:
        return _not_valued("計画に販売記録が無い")

    # ── Step 3: keep records whose product x market has the rules (B.2) ───
    # Each record needs a price row for ITS (market, product) combination and a
    # supplier cost for its product. Records without them are excluded and listed
    # (formerly product and market were checked separately and the missing price
    # was valued as 0; the excluded records were dropped silently -- S3).
    no_cost = ~sales["product_id"].isin(known_products)
    no_price = ~sales.apply(lambda r: rules.has_market_price(str(r["channel_node"]),
                                                             str(r["product_id"])), axis=1)
    excluded = (_excluded_rows(sales[no_cost], cpu, "仕入れの原価が規則に無い製品")
                + _excluded_rows(sales[~no_cost & no_price], cpu, "製品 × 市場の価格が規則に無い"))
    sales = sales[~(no_cost | no_price)].copy()
    if sales.empty:
        return _not_valued("評価できる販売記録が無い（製品・市場が規則に無い）", excluded)
    if verbose and excluded:
        print(f"[PPC Runner] excluded (no rule): {excluded}")

    # ── Step 4 (removed, K4): sample sales are never substituted here ─────

    result, rules = _run_engine(sales, rules, sc_tree, known_products, verbose, base_currency)
    # a supplier the engine asked for has no cost rule (formerly valued as 0):
    # exclude that product's records and value the rest once more
    miss = {p for (k, _n, p) in rules.lookup_log if k in ("supplier_cost_missing",
                                                          "market_price_missing")}
    if miss:
        excluded += _excluded_rows(sales[sales["product_id"].isin(miss)], cpu,
                                   "仕入れの原価・価格の規則が見つからない組合せがある製品")
        sales = sales[~sales["product_id"].isin(miss)].copy()
        if sales.empty:
            return _not_valued("評価できる販売記録が無い（原価・価格の規則が無い）", excluded)
        rules.lookup_log.clear()
        result, rules = _run_engine(sales, rules, sc_tree, known_products, verbose, base_currency)

    status = VAL_PARTIAL if excluded else VAL_DONE
    before_first = [{"kind": k.replace("_before_first_rule_week", ""), "node": n, "product_id": p,
                     "lookups": c}
                    for (k, n, p), c in sorted(rules.lookup_log.items())
                    if k.endswith("_before_first_rule_week")]
    result.kpi_summary["valuation_status"] = status
    result.kpi_summary["rule_sources"] = src.record()
    if excluded:
        result.kpi_summary["reason"] = "規則の無い製品・市場の販売記録を除いて評価した"
        result.kpi_summary["excluded"] = excluded
    if before_first:
        # owner decision 2026-10-26 (a): valued with the first rule row, recorded
        result.kpi_summary["price_before_first_rule_week"] = before_first
        result.warnings = list(result.warnings or []) + [
            {"kind": "price_before_first_rule_week", "location": f"{b['kind']} {b['node']} x {b['product_id']}",
             "currency": "", "requested_week": "", "used_week": "first rule row",
             "count": b["lookups"], "detail": "week before the rule's first row: the first row's value used"}
            for b in before_first]

    # RequestLetter_StageD_Phase1 0-5: the Landed Cost engine's silent fx_rate
    # defaults of this model's edge_cost_master.csv go to the same warnings file.
    _ecm = os.path.join(data_dir, "edge_cost_master.csv")
    if os.path.exists(_ecm):
        try:
            from wom.engine.landed_cost import fx_rate_substitutions
            result.warnings = list(result.warnings or []) + fx_rate_substitutions(pd.read_csv(_ecm))
        except Exception as _exc:
            print(f"[PPC Runner] edge_cost_master fx_rate check failed: {_exc}")

    if verbose:
        kpi = result.kpi_summary
        print(
            f"[PPC Runner] Done -- {status}  lots={kpi['total_lots']:,}  "
            f"events={len(result.ppc_events):,}  "
            f"margin={kpi['gross_margin_pct']:.1%}  "
            f"trust_events={kpi['trust_event_count']}"
        )

    # ── Step 6: Export ────────────────────────────────────────────────────
    export_results(result, output_dir)
    _mark(status, result.kpi_summary)
    out = dict(result.kpi_summary)
    out["_psi_mode"] = True
    out["sales_source"] = SALES_PSI
    return out


def _run_engine(sales, rules, sc_tree, known_products, verbose, base_currency):
    """Scenario detection + engine run on the (rule-covered) sales records.
    Returns (result, rules). Unchanged logic of the former Step 5."""
    # ── Step 5: Auto-detect scenario and build engine parameters ─────────
    scenario = detect_scenario(sales)

    # dad_nodes_chain: ordered list of all DAD nodes per product (MOM-side first).
    # None for rice / smartphone_global (single-DAD chains).
    dad_nodes_chain = None
    # mom_nodes_chain: InBound counterpart of dad_nodes_chain (Problem B fix,
    # wom-v1r1m7-fix4all_case). Only populated by the GENERIC branch below;
    # the named scenarios (rice/cookie/smartphone_global) have no multi-tier
    # InBound chains in their hardcoded sc_paths.
    mom_nodes_chain = None
    # bom_qty_map: Letter B (request_letter_b_bom_qty.md, "1 set rule").
    # Only populated by the GENERIC branch below; the named scenarios have no
    # bom_qty column values (bom_qty is brand new -- no existing model besides
    # the Letter B verification model sets it), so they stay at the pre-Letter-B
    # default of bom_qty=1 everywhere.
    bom_qty_map = None

    if scenario == "rice":
        sc_paths      = build_rice_vs_paths()
        mom_node      = "Coop_Seihaku"
        supplier_node = "Farm_JP"
        dad_node      = "DC_Rice"

    elif scenario == "cookie":
        sc_paths      = build_cookie_vs_paths()
        mom_node      = {"Cookie_Import": "Factory_GP_CN", "Cookie_Local": "Factory_DP_JP"}
        supplier_node = {"Cookie_Import": "Ingredients_CN", "Cookie_Local": "Ingredients_JP"}
        dad_node      = {"Cookie_Import": "DC_Import_Buffer", "Cookie_Local": "DC_Local_JP"}
        dad_nodes_chain = {
            "Cookie_Import": ["DC_Import_Buffer", "DC_Import_Main"],
            "Cookie_Local":  ["DC_Local_JP"],
        }
        if verbose:
            print("[PPC Runner] Scenario: COOKIE_JP  "
                  "(Factory_GP_CN/DP_JP -> DC_Import_Buffer/DC_Import_Main/DC_Local_JP -> Retail_JP_*)")

    elif scenario == "smartphone_global":
        sc_paths      = build_smartphone_global_vs_paths()
        mom_node = {
            "Phone16": "EMS_A_CN",
            "Phone15": "EMS_A_CN_i15",
            "Phone17": "EMS_A_CN_i17",
        }
        supplier_node = mom_node
        dad_node = {
            "Phone16": "SP_Phone16",
            "Phone15": "SP_Phone15",
            "Phone17": "SP_Phone17",
        }
        if verbose:
            print("[PPC Runner] Scenario: SMARTPHONE_GLOBAL  "
                  "(EMS_A_CN/i15/i17 -> SP_Phone16/15/17 -> Retail_*)")

    else:
        # Generic: auto-detect mom/supplier/dad from SCTree structure.
        # Collects ALL DAD nodes per product in OT preorder as a legacy
        # per-product fallback (_dad_list_map), AND builds the preferred
        # per-Lot chains (_dad_chain_by_channel / _mom_chain_by_leaf) by
        # walking each leaf_out's / leaf_in's ACTUAL tree ancestry via
        # sc_tree.walk_ancestor_chain. This replaces the old assumption that
        # a single flat, preorder-collected list correctly represents "the"
        # DAD/MOM chain for every Lot of a product_id -- an assumption that
        # broke for products with multiple parallel branches (e.g.
        # smartx-2027-2029's SmartXPro: 3 independent regional DAD nodes
        # DC_AMER/DC_EMEA/DC_APAC under one supply_point, and 2 independent
        # InBound MOM roots AssemblyCN/AssemblyIN). See Coding Request
        # Letter smartx-2027-2029-fix-request-letter.md, Problems B and C+D.
        sc_paths = {}
        _mom_map: dict = {}
        _sup_list_map: dict = {}  # ALL leaf_in (Tier-1 supplier) nodes per product, OT preorder
        _dad_map: dict = {}       # first DAD per product (for tariff)
        _dad_list_map: dict = {}  # all DADs per product in OT preorder (legacy fallback)
        _dad_chain_by_channel: dict = {}  # (product_id, channel_node) -> mom-side-first DAD chain
        _mom_chain_by_leaf: dict = {}     # (product_id, leaf_in_node) -> leaf-side-first intermediate MOM chain
        _bom_qty_map: dict = {}           # (product_id, leaf_in_node) -> bom_qty (Letter B, "1 set rule")

        if sc_tree is not None:
            from wom.model.plan_node import (
                NODE_TYPE_MOM, NODE_TYPE_LEAF_IN, NODE_TYPE_DAD, NODE_TYPE_LEAF_OUT
            )
            for _prod in sc_tree.products:
                if _prod not in known_products:
                    continue
                _dad_list_map[_prod] = []
                _sup_list_map[_prod] = []
                _ot_root = sc_tree.get_ot_root(_prod)
                for _nd in sc_tree.iter_all_nodes(_prod):
                    _nt = getattr(_nd, "node_type", "")
                    _nm = getattr(_nd, "node_name",
                                  getattr(_nd, "node_id", ""))
                    if _nt == NODE_TYPE_DAD:
                        _dad_list_map[_prod].append(_nm)  # ordered OT preorder
                        if _prod not in _dad_map:
                            _dad_map[_prod] = _nm  # first DAD (for tariff compat)
                    elif _nt == NODE_TYPE_LEAF_OUT:
                        # Per-Lot DAD chain: walk THIS channel's actual tree
                        # ancestry back to the OT root (supply_point), rather
                        # than reusing the one flat _dad_list_map chain
                        # shared by every channel of the product_id.
                        _ch = sc_tree.walk_ancestor_chain(_nd, NODE_TYPE_DAD, _ot_root)
                        _ch.reverse()  # mom-side-first, matches legacy convention
                        _dad_chain_by_channel[(_prod, _nm)] = _ch
                    elif _nt == NODE_TYPE_MOM and _prod not in _mom_map:
                        _mom_map[_prod] = _nm
                    elif _nt == NODE_TYPE_LEAF_IN:
                        # Collect EVERY Tier-1 supplier (leaf_in) feeding this
                        # product's MOM -- e.g. Battery/Motor/ECU -- not just
                        # the first one encountered. See ppc_forward.py's
                        # _resolve_node_list for how this list is consumed.
                        _sup_list_map[_prod].append(_nm)
                        # Letter B (request_letter_b_bom_qty.md): only leaf_in
                        # nodes carry a meaningful bom_qty (default 1 -- see
                        # PlanNode.bom_qty). Only recorded when != 1, so an
                        # empty _bom_qty_map (every existing model) collapses
                        # to bom_qty_map=None below, identical to pre-Letter-B
                        # behavior.
                        if getattr(_nd, "bom_qty", 1) != 1:
                            _bom_qty_map[(_prod, _nm)] = _nd.bom_qty
                        # Per-supplier InBound tier chain: intermediate
                        # "mom"-type ancestors between this leaf_in and its
                        # own terminal MOM root. No explicit stop_node is
                        # needed -- walk_ancestor_chain auto-detects the root
                        # (a node with no parent), so this resolves correctly
                        # even while a product still has multiple InBound
                        # roots (pre-SKU-split state).
                        _mch = sc_tree.walk_ancestor_chain(_nd, NODE_TYPE_MOM, None)
                        if _mch:
                            _mom_chain_by_leaf[(_prod, _nm)] = _mch

        # dad_nodes_chain: per-Lot chains (checked first by ppc_tariff.py's
        # _resolve_chain / ppc_backward.py's _resolve_node_list) merged with
        # the legacy per-product flat list (fallback only; the two dicts'
        # keys never collide since one uses str keys and the other
        # (product_id, channel_node) tuple keys).
        dad_nodes_chain = (
            {**_dad_list_map, **_dad_chain_by_channel}
            if (_dad_list_map or _dad_chain_by_channel) else None
        )
        # mom_nodes_chain: per-leaf_in InBound tier chains (brand new
        # parameter, no legacy format to merge with -- see ppc_forward.py).
        mom_nodes_chain = _mom_chain_by_leaf if _mom_chain_by_leaf else None
        # bom_qty_map: per-leaf_in BOM multiplier (Letter B, "1 set rule").
        bom_qty_map = _bom_qty_map if _bom_qty_map else None

        if _mom_map:
            # Collapse to str when only one product
            mom_node = (
                _mom_map if len(_mom_map) != 1
                else next(iter(_mom_map.values()))
            )
            # supplier_node: dict[product_id -> list[node_id]] in the
            # multi-product case, or a bare list[node_id] when there's only
            # one product -- both forms are handled by
            # ppc_forward._resolve_node_list().
            supplier_node = (
                _sup_list_map if len(_sup_list_map) != 1
                else next(iter(_sup_list_map.values()))
            )
            dad_node = (
                _dad_map if len(_dad_map) != 1
                else next(iter(_dad_map.values()), "")
            )
            if verbose:
                print(f"[PPC Runner] Scenario: GENERIC  "
                      f"mom={mom_node}  "
                      f"supplier={supplier_node}  "
                      f"dad={dad_node}  "
                      f"dad_chain_by_channel={_dad_chain_by_channel}  "
                      f"mom_chain_by_leaf={_mom_chain_by_leaf}")
        else:
            # Final fallback: legacy smartphone (JP_Channel / US_Channel)
            sc_paths      = build_smartphone_vs_paths()
            mom_node      = "MOM_China"
            supplier_node = "Supplier_CN"
            dad_node      = "DAD_Japan"
            dad_nodes_chain = None
            mom_nodes_chain = None
            if verbose:
                print("[PPC Runner] Scenario: SMARTPHONE (legacy)  "
                      f"mom={mom_node}  "
                      f"supplier={supplier_node}  "
                      f"dad={dad_node}")

    if verbose and scenario != "smartphone_global":
        print(f"[PPC Runner] Scenario: {scenario.upper()}  "
              f"mom={mom_node}  supplier={supplier_node}  dad={dad_node}")

    if verbose:
        print(f"[PPC Runner] Running engine on {len(sales)} lot-records ...")

    eng = PPCSimulationEngine(
        sales_records=sales,
        sc_paths=sc_paths,
        rules=rules,
        base_currency=base_currency,
        mom_node=mom_node,
        supplier_node=supplier_node,
        dad_node=dad_node,
        dad_nodes_chain=dad_nodes_chain,
        mom_nodes_chain=mom_nodes_chain,
        bom_qty_map=bom_qty_map,
        verbose=False,
    )
    result = eng.run()
    return result, rules
