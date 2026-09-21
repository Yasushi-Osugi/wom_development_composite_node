#!/usr/bin/env python3
"""
gen_tariff_edges.py — Phase 1 of tariff/trade-lane master unification.

Generate the per-edge `ppc_tariff_rule.csv` (intermediate) from a single
canonical master `edge_cost_master.csv` (product x country-pair x scenario)
plus the SC tree topology. This makes `edge_cost_master.csv` the single
source of truth for tariff rates, and `ppc_tariff_rule.csv` a *generated*
artifact rather than a hand-maintained master.

See requests/tariff-lane-master-unification-request-letter.md (Phase 1).

Design (matches the existing WOM convention, e.g. apparel-global):
  - Tariff is levied at destination clearance and attributed to the final
    "DC -> leaf_out" edge, with from_country = product ORIGIN (terminal MOM
    country) and to_country = the market (leaf_out) country.
  - Country per node is read from ppc_node_profit_zone.csv (node_id,
    product_id -> country). Region (e.g. US_W) may be sub-national; country
    (US) is what tariff keys on.
  - hs_code is read from route_master.csv (sku_id, region -> hs_code).

Canonical `edge_cost_master.csv` columns (product_id is the Phase-1 addition;
if the column is absent or blank, the row is treated as a wildcard applying
to all products, preserving backward compatibility):
    scenario, from_country, to_country, [product_id], tariff_rate,
    tariff_basis?, hs_code?, fx_rate, src_currency, dst_currency,
    freight_usd_per_lot, notes

Output `ppc_tariff_rule.csv` columns (unchanged, consumed by wom/ppc):
    edge_id, from_country, to_country, product_id, hs_code,
    tariff_rate, tariff_basis

Usage:
    python -m tools.gen_tariff_edges --model-dir data/sample/soysauce-us-2027
    python -m tools.gen_tariff_edges --model-dir <dir> --scenario Base \
           --out ppc_tariff_rule.csv [--check]

`--check` compares the freshly generated rows against the existing
ppc_tariff_rule.csv (if present) and reports differences WITHOUT overwriting
— use this to prove the generated file matches the hand-made one.
"""
from __future__ import annotations
import argparse
import csv
import os
import sys
from typing import Dict, List, Optional, Tuple


def _read_csv(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _node_country_map(model_dir: str) -> Dict[Tuple[str, str], str]:
    """(node_id, product_id) -> country, from ppc_node_profit_zone.csv."""
    rows = _read_csv(os.path.join(model_dir, "ppc_node_profit_zone.csv"))
    m: Dict[Tuple[str, str], str] = {}
    for r in rows:
        m[(r["node_id"], r["product_id"])] = (r.get("country") or "").strip()
    return m


def _hs_code_map(model_dir: str) -> Dict[Tuple[str, str], str]:
    """(sku_id, region) -> hs_code, from route_master.csv (best effort)."""
    rows = _read_csv(os.path.join(model_dir, "route_master.csv"))
    m: Dict[Tuple[str, str], str] = {}
    for r in rows:
        m[(r.get("sku_id", ""), r.get("region", ""))] = (r.get("hs_code") or "").strip()
    return m


def _load_canonical(model_dir: str, scenario: str
                    ) -> Dict[Tuple[str, str, str], dict]:
    """
    Load canonical edge_cost_master for one scenario.
    Key: (from_country, to_country, product_id_or_'*') -> row dict.
    A row with blank/missing product_id is stored under '*' (wildcard).
    """
    rows = _read_csv(os.path.join(model_dir, "edge_cost_master.csv"))
    table: Dict[Tuple[str, str, str], dict] = {}
    for r in rows:
        if (r.get("scenario") or "").strip() != scenario:
            continue
        prod = (r.get("product_id") or "").strip() or "*"
        key = (r.get("src_region", "").strip(),   # src_region carries country here
               r.get("dst_region", "").strip(),
               prod)
        table[key] = r
    return table


def _lookup_canonical(table: Dict[Tuple[str, str, str], dict],
                      frm: str, to: str, product: str) -> Optional[dict]:
    """Prefer an exact product row, fall back to the '*' wildcard row."""
    return table.get((frm, to, product)) or table.get((frm, to, "*"))


def generate(model_dir: str, scenario: str = "Base"
             ) -> List[dict]:
    """Return the list of generated ppc_tariff_rule rows (dicts)."""
    tree = _read_csv(os.path.join(model_dir, "sc_tree_master.csv"))
    if not tree:
        raise FileNotFoundError(f"sc_tree_master.csv not found in {model_dir}")

    node_country = _node_country_map(model_dir)
    hs_map = _hs_code_map(model_dir)
    canonical = _load_canonical(model_dir, scenario)

    # region -> country fallback (if a node is missing from profit_zone):
    # strip a sub-national suffix, e.g. US_W -> US.
    def country_of(node_name: str, region: str, product: str) -> str:
        c = node_country.get((node_name, product))
        if c:
            return c
        return (region or "").split("_")[0]

    # index nodes
    by_name = {r["node_name"]: r for r in tree}

    out: List[dict] = []
    # products present
    products = sorted({r["product_name"] for r in tree})
    for product in products:
        nodes = [r for r in tree if r["product_name"] == product]
        # origin country = terminal MOM (inbound, mom, no parent)
        terminal_moms = [r for r in nodes
                         if r["node_type"] == "mom" and r["side"] == "inbound"
                         and not (r.get("parent_node") or "").strip()]
        origin_country = ""
        if terminal_moms:
            tm = terminal_moms[0]
            origin_country = country_of(tm["node_name"], tm.get("region", ""), product)

        # each leaf_out -> (parent DC -> leaf) edge, market country
        for lf in [r for r in nodes if r["node_type"] == "leaf_out"]:
            parent = (lf.get("parent_node") or "").strip()
            if not parent:
                continue
            edge_id = f"{parent}->{lf['node_name']}"
            market_country = country_of(lf["node_name"], lf.get("region", ""), product)
            row = _lookup_canonical(canonical, origin_country, market_country, product)
            if row is None:
                # No canonical lane -> emit a 0% row so the edge is defined
                # (keeps PPC lookups total); flag via notes.
                tariff_rate, tariff_basis = "0.0", "transfer_price"
                missing = True
            else:
                tariff_rate = str(row.get("tariff_rate", "0.0"))
                tariff_basis = (row.get("tariff_basis") or "transfer_price").strip()
                missing = False
            hs_code = (hs_map.get((product, lf.get("region", "")))
                       or (row.get("hs_code") if row else "") or "")
            out.append({
                "edge_id": edge_id,
                "from_country": origin_country,
                "to_country": market_country,
                "product_id": product,
                "hs_code": hs_code,
                "tariff_rate": tariff_rate,
                "tariff_basis": tariff_basis,
                "_missing_canonical": missing,
            })
    return out


HEADER = ["edge_id", "from_country", "to_country", "product_id",
          "hs_code", "tariff_rate", "tariff_basis"]


def _write(rows: List[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in HEADER})


def _norm(v: str) -> str:
    """Normalise a numeric-ish string for comparison (0.10 == 0.1)."""
    s = (v or "").strip()
    try:
        return f"{float(s):.6g}"
    except ValueError:
        return s


def _check(rows: List[dict], existing_path: str) -> int:
    existing = _read_csv(existing_path)
    if not existing:
        print(f"[check] no existing {existing_path}; nothing to compare.")
        return 0
    gen_idx = {(r["edge_id"], r["product_id"]): r for r in rows}
    ex_idx = {(r["edge_id"], r["product_id"]): r for r in existing}
    diffs = 0
    for k in sorted(set(gen_idx) | set(ex_idx)):
        g, e = gen_idx.get(k), ex_idx.get(k)
        if g is None:
            print(f"[diff] only in existing: {k}"); diffs += 1; continue
        if e is None:
            print(f"[diff] only in generated: {k}"); diffs += 1; continue
        for col in ("from_country", "to_country", "tariff_rate", "tariff_basis"):
            gv, ev = _norm(g.get(col, "")), _norm(e.get(col, ""))
            if gv != ev:
                print(f"[diff] {k} {col}: generated={gv!r} existing={ev!r}")
                diffs += 1
    print(f"[check] {'MATCH (0 diffs)' if diffs == 0 else f'{diffs} difference(s)'} "
          f"— {len(rows)} generated vs {len(existing)} existing rows")
    return diffs


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model-dir", required=True)
    p.add_argument("--scenario", default="Base")
    p.add_argument("--out", default="ppc_tariff_rule.csv",
                   help="output filename (relative to model-dir)")
    p.add_argument("--check", action="store_true",
                   help="compare against existing ppc_tariff_rule.csv, do NOT write")
    a = p.parse_args(argv)

    rows = generate(a.model_dir, a.scenario)
    miss = [r for r in rows if r.get("_missing_canonical")]
    if miss:
        print(f"[warn] {len(miss)} edge(s) had no canonical lane "
              f"(emitted 0%): {[r['edge_id'] for r in miss]}")

    if a.check:
        return 1 if _check(rows, os.path.join(a.model_dir, a.out)) else 0

    out_path = os.path.join(a.model_dir, a.out)
    _write(rows, out_path)
    print(f"[gen_tariff_edges] wrote {len(rows)} rows -> {out_path} "
          f"(scenario={a.scenario})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
