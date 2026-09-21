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
from .ppc_rules import PPCRuleSet
from .ppc_engine import (PPCSimulationEngine,
                          build_iphone_vs_paths,
                          build_iphone_global_vs_paths,
                          build_rice_vs_paths,
                          build_cookie_vs_paths,
                          detect_scenario)
from .ppc_export import export_results


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
) -> dict:
    """
    Run the full PPC Simulation pipeline using PSI leaf-out quantities.
    """
    warnings.filterwarnings("ignore")

    # ── Step 1: Load PPC rules ─────────────────────────────────────────────
    if verbose:
        print(f"[PPC Runner] Loading rules from: {data_dir}")
    rules = PPCRuleSet.load(data_dir)

    known_products = {p for p in rules.supplier_cost["product_id"].unique() if isinstance(p, str)}
    known_channels = {c for c in rules.market_price["market_node"].unique() if isinstance(c, str)}

    if verbose:
        print(f"[PPC Runner] Known products: {sorted(known_products)}")
        print(f"[PPC Runner] Known channels: {sorted(known_channels)}")

    # ── Step 2: PSI → sales_records ───────────────────────────────────────
    sales = psi_to_sales_records(
        sc_tree, weeks,
        channel_map=channel_map,
        product_id_map=product_id_map,
        use_node_name=use_node_name,
    )
    if verbose:
        print(f"[PPC Runner] PSI bridge: {summarize_psi_records(sales)}")

    # ── Step 3: Filter to PPC-known products & channels ───────────────────
    psi_mode = False
    if not sales.empty:
        valid = (
            sales["product_id"].isin(known_products) &
            sales["channel_node"].isin(known_channels)
        )
        sales_filtered = sales[valid].copy()
        if not sales_filtered.empty:
            psi_mode = True
            sales = sales_filtered
            if verbose:
                print(
                    f"[PPC Runner] After filter: {len(sales)} records "
                    f"({int(sales['qty'].sum()):,} total units)"
                )

    # ── Step 4: Fallback to sample data ───────────────────────────────────
    if not psi_mode:
        if verbose:
            print(
                "[PPC Runner] No PSI<->PPC-compatible records found.\n"
                "             Falling back to sample data."
            )
        from wom.ppc.__main__ import generate_sample_sales
        start_week = weeks[0] if weeks else "2026-W01"
        sales = generate_sample_sales(
            start_week=start_week,
            n_weeks=len(weeks),
        )
        if verbose:
            print(
                f"[PPC Runner] Sample data: {len(sales)} records "
                f"(weeks {sales['week'].min()}..{sales['week'].max()})"
            )

    # ── Step 5: Auto-detect scenario and build engine parameters ─────────
    scenario = detect_scenario(sales)

    # dad_nodes_chain: ordered list of all DAD nodes per product (MOM-side first).
    # None for rice / iphone_global (single-DAD chains).
    dad_nodes_chain = None
    # mom_nodes_chain: InBound counterpart of dad_nodes_chain (Problem B fix,
    # wom-v1r1m7-fix4all_case). Only populated by the GENERIC branch below;
    # the named scenarios (rice/cookie/iphone_global) have no multi-tier
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
        mom_node      = "JA_Seihaku"
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

    elif scenario == "iphone_global":
        sc_paths      = build_iphone_global_vs_paths()
        mom_node = {
            "iPhone16": "Foxconn_CN",
            "iPhone15": "Foxconn_CN_i15",
            "iPhone17": "Foxconn_CN_i17",
        }
        supplier_node = mom_node
        dad_node = {
            "iPhone16": "SP_iPhone16",
            "iPhone15": "SP_iPhone15",
            "iPhone17": "SP_iPhone17",
        }
        if verbose:
            print("[PPC Runner] Scenario: IPHONE_GLOBAL  "
                  "(Foxconn_CN/i15/i17 -> SP_iPhone16/15/17 -> Retail_*)")

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
            # Final fallback: legacy iphone (JP_Channel / US_Channel)
            sc_paths      = build_iphone_vs_paths()
            mom_node      = "MOM_China"
            supplier_node = "Supplier_CN"
            dad_node      = "DAD_Japan"
            dad_nodes_chain = None
            mom_nodes_chain = None
            if verbose:
                print("[PPC Runner] Scenario: IPHONE (legacy)  "
                      f"mom={mom_node}  "
                      f"supplier={supplier_node}  "
                      f"dad={dad_node}")

    if verbose and scenario != "iphone_global":
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

    if verbose:
        kpi = result.kpi_summary
        print(
            f"[PPC Runner] Done -- lots={kpi['total_lots']:,}  "
            f"events={len(result.ppc_events):,}  "
            f"margin={kpi['gross_margin_pct']:.1%}  "
            f"trust_events={kpi['trust_event_count']}"
        )
        if not psi_mode:
            print("[PPC Runner] WARNING: Results based on SAMPLE data (PSI->PPC mapping missing)")

    # ── Step 6: Export ────────────────────────────────────────────────────
    export_results(result, output_dir)

    return result.kpi_summary
