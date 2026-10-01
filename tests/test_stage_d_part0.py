# -*- coding: utf-8 -*-
"""
段階 D 第 1 回 Part 0（RequestLetter_StageD_Phase1）

0-1  iphone の単位：cpu_size 1000、PPC の市場価格は 1 台当たり
0-2  Cookie の運賃は物理の区間だけ（ノード費用に運賃なし、supply point の行なし）
0-3  ev・oil の supply point の運賃の行を消した
0-4  DAD → DAD の区間の関税を PPC が読む（alloc：国境の区間 FG_WH_Noda → DC_*）
0-5  PPC の黙った扱い（前の週の為替、為替 0 → 1.0、Landed Cost の fx_rate）を ppc_warnings.csv に出す
"""
from __future__ import annotations

import os
import shutil

import pandas as pd
import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SAMPLE = os.path.join(REPO, "data", "sample")


def _run(model, tmp_path, plugins="safe"):
    from tools.run_headless_from_folder import run
    work = tmp_path / model
    shutil.copytree(os.path.join(SAMPLE, model), work)
    out = tmp_path / "ppc"
    snap = run(str(work), plugins_spec=plugins, output_ppc_dir=str(out), verbose=False)
    return snap, out


# ── 0-1 / 0-2 / 0-3: masters ─────────────────────────────────────────
def test_iphone_cpu_size_and_unit_prices():
    from wom.engine.warmup import read_cpu_size
    assert read_cpu_size(os.path.join(SAMPLE, "iphone_global")) == 1000
    mp = pd.read_csv(os.path.join(SAMPLE, "iphone_global", "ppc_market_price.csv"))
    sku = pd.read_csv(os.path.join(SAMPLE, "iphone_global", "sku_master.csv"))
    prices = set(sku["selling_price"].astype(float))
    assert set(mp["market_price"].astype(float)) <= prices         # 1 台当たり（sku_master と同じ値）


def test_cookie_freight_only_on_physical_edges():
    d = os.path.join(SAMPLE, "Cookie-jp-2026")
    nc = pd.read_csv(os.path.join(d, "ppc_node_cost_rule.csv"))
    assert (nc["cost_type"] != "logistics_cost").all()
    ec = pd.read_csv(os.path.join(d, "ppc_edge_cost_rule.csv"))
    assert not ec["edge_id"].str.contains("SP_").any()
    got = {r.edge_id: r.fixed_amount for r in ec.itertuples()}
    assert got["Factory_GP_CN->DC_Import_Buffer"] == 2500
    assert got["DC_Import_Buffer->DC_Import_Main"] == 1000
    assert got["Factory_DP_JP->DC_Local_JP"] == 200
    assert all(got[f"DC_Local_JP->Retail_JP_{c}"] == 300 for c in ("CVS", "SM", "EC"))


@pytest.mark.parametrize("model", ["ev-europe-2026", "ev-thailand-2026", "ev-thailand-2026_update",
                                   "oil-global-2027"])
def test_supply_point_freight_rows_removed(model):
    ec = pd.read_csv(os.path.join(SAMPLE, model, "ppc_edge_cost_rule.csv"))
    assert not ec["edge_id"].astype(str).str.contains("SP_").any()


# ── 0-4: tariff on a DAD -> DAD edge ──────────────────────────────────
def test_alloc_tariff_on_border_edges(tmp_path):
    snap, out = _run("soysauce-jpy-2027-alloc", tmp_path)
    ev = pd.read_csv(out / "ppc_event_ledger.csv", low_memory=False)
    t = ev[ev["ppc_event_type"] == "tariff_cost"]
    assert set(t["edge_id"]) == {"FG_WH_Noda->DC_US_SF", "FG_WH_Noda->DC_US_NY",
                                 "FG_WH_Noda->DC_EU_RTM", "FG_WH_Noda->DC_JP"}
    # the same total as before the move (the basis is the same transfer price)
    assert float((t["amount_base"] * t["qty"]).sum()) == pytest.approx(15670707.4425, rel=1e-9)
    assert snap["ppc"]["tariff_base"] == pytest.approx(15670707.44)


# ── 0-5: silent substitutions made visible ────────────────────────────
def test_fx_converter_records_prior_week_and_keeps_values():
    from wom.ppc.ppc_fx import FXConverter
    fx = FXConverter(pd.DataFrame([{"week": "2026-W01", "currency": "USD", "base_currency": "JPY",
                                    "rate": 150.0}]), "JPY")
    fx.location = "Step X"
    assert fx.convert(2.0, "USD", "2026-W03") == (150.0, 300.0)   # value unchanged (prior week)
    fx.convert(1.0, "USD", "2026-W03")
    assert fx.fallback_warnings == [{"kind": "fx_fallback_prior_week", "location": "Step X",
                                     "currency": "USD", "requested_week": "2026-W03",
                                     "used_week": "2026-W01", "count": 2,
                                     "detail": "rate 150.0 of 2026-W01 used for 2026-W03"}]


def test_landed_cost_fx_rate_substitutions_listed():
    from wom.engine.landed_cost import fx_rate_substitutions
    df = pd.DataFrame([{"scenario": "Base", "src_region": "CN", "dst_region": "JP", "fx_rate": 0.0,
                        "src_currency": "USD", "dst_currency": "JPY"},
                       {"scenario": "Base", "src_region": "JP", "dst_region": "JP", "fx_rate": float("nan"),
                        "src_currency": "JPY", "dst_currency": "JPY"},
                       {"scenario": "Base", "src_region": "CN", "dst_region": "US", "fx_rate": 1.0,
                        "src_currency": "USD", "dst_currency": "USD"}])
    kinds = [x["kind"] for x in fx_rate_substitutions(df)]
    assert kinds == ["landed_cost_fx_zero_as_1", "landed_cost_fx_blank_as_nan"]


def test_ppc_warnings_file_written(tmp_path):
    snap, out = _run("ev-thailand-2026", tmp_path, plugins="HolidayCalendarPlugin,"
                     "BufferingStockOptimizerPlugin,CapacityOverridePlugin")
    w = pd.read_csv(out / "ppc_warnings.csv")
    assert list(w.columns) == ["kind", "location", "currency", "requested_week", "used_week", "count", "detail"]
    assert set(w["kind"]) == {"fx_fallback_prior_week"} and int(w["count"].sum()) > 0
    assert snap["ppc"]["revenue_base"] == pytest.approx(319119580000.0)   # values unchanged
