# -*- coding: utf-8 -*-
"""
段階 D 第 1 回：CSV → 実際のローダ → 台帳（結合のテスト）

- マスターの読み込み：同じ価格が 2 か所にあれば止める、運賃をノードに書けば止める
- soysauce-jpy-2027-alloc を実際に計画して台帳を作る（一時フォルダ）：
  出荷の記録が計画の実出荷と 1 対 1、原価の保存、外部売上の照合、未設定価格の一覧、
  為替が黙って 1 や前の週にならない、数量の PSI（headless の snapshot）が台帳で変わらない
"""
from __future__ import annotations

import os
import shutil

import pandas as pd
import pytest

from wom.valuechain.masters import MasterError, load_masters

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALLOC = os.path.join(REPO, "data", "sample", "soysauce-jpy-2027-alloc")
COOKIE = os.path.join(REPO, "data", "sample", "Cookie-jp-2026")


def _copy(src, tmp_path):
    dst = tmp_path / os.path.basename(src)
    shutil.copytree(src, dst)
    return str(dst)


def test_masters_load_for_both_subjects():
    for d, tm in ((ALLOC, {"Soy_Sauce": ["Bottling_Noda"]}),
                  (COOKIE, {"Cookie_Import": ["Factory_GP_CN"], "Cookie_Local": ["Factory_DP_JP"]})):
        m = load_masters(d, tm, {})
        assert m.hq_currency == "JPY" and m.common_currency == "USD"
        assert m.holding_rate_weekly is None                     # 未設定（0 として計算しない）


def test_price_written_twice_stops(tmp_path):
    d = _copy(ALLOC, tmp_path)
    with open(os.path.join(d, "vc_price_rule.csv"), "a", encoding="utf-8") as f:
        f.write("Bottling_Noda->FG_WH_Noda,Soy_Sauce,management,2027-W01,10,USD\n")
    with pytest.raises(MasterError, match="written twice"):
        load_masters(d, {"Soy_Sauce": ["Bottling_Noda"]}, {})


def test_duplicate_price_rule_row_stops(tmp_path):
    d = _copy(ALLOC, tmp_path)
    with open(os.path.join(d, "vc_price_rule.csv"), "a", encoding="utf-8") as f:
        f.write("FG_WH_Noda->DC_US_SF,Soy_Sauce,intercompany,2027-W01,20,USD\n")
        f.write("FG_WH_Noda->DC_US_SF,Soy_Sauce,intercompany,2027-W01,21,USD\n")
    with pytest.raises(MasterError, match="twice"):
        load_masters(d, {"Soy_Sauce": ["Bottling_Noda"]}, {})


def test_freight_on_a_node_stops(tmp_path):
    d = _copy(COOKIE, tmp_path)
    with open(os.path.join(d, "ppc_node_cost_rule.csv"), "a", encoding="utf-8") as f:
        f.write("DC_Import_Main,Cookie_Import,logistics_cost,per_lot,0,1000,JPY,dup\n")
    with pytest.raises(MasterError, match="physical edge"):
        load_masters(d, {"Cookie_Import": ["Factory_GP_CN"]}, {})


@pytest.fixture(scope="module")
def alloc_run(tmp_path_factory):
    # The "prices not set" path (judgment b): run on a copy whose vc_price_rule.csv has only
    # the header, so these tests do not depend on the provisional prices in the sample.
    from wom.valuechain.run import run_valuechain
    src = tmp_path_factory.mktemp("vc_alloc_src") / "soysauce-jpy-2027-alloc"
    shutil.copytree(ALLOC, src)
    with open(src / "vc_price_rule.csv", "w", encoding="utf-8") as f:
        f.write("edge_id,product_id,price_type,week,price,currency\n")
    out = tmp_path_factory.mktemp("vc_alloc")
    return run_valuechain(str(src), str(out)), out


def test_alloc_sample_prices_leave_nothing_unvalued(tmp_path):
    # The sample's provisional prices (README, 2026-10-01) fill every missing price.
    from wom.valuechain.run import run_valuechain
    r = run_valuechain(ALLOC, str(tmp_path))
    c = r["checks"]
    assert c["conservation_ok"] and c["external_sales"]["ok_identity"] and c["external_sales"]["ok_records"]
    m = pd.read_csv(tmp_path / "vc_missing_prices.csv")
    assert len(m) == 0
    # round 2 (RequestLetter_StageD_Phase2): the reconciliation holds in every week and over
    # the reporting period; the opening unrealized profit comes from the warmup weeks
    u = c["unrealized"]
    assert u["ok"], u
    p = u["period"]
    assert p["round1_minus_round2"] == pytest.approx(
        p["unrealized_closing_hq"] - p["unrealized_opening_hq"] + p["to_unvalued_in_period_hq"], abs=1e-3)
    assert p["unrealized_opening_hq"] == pytest.approx(1099305.0, abs=1e-3)
    assert p["to_unvalued_in_period_hq"] == 0
    d = pd.read_csv(tmp_path / "vc_unrealized_weekly.csv")
    assert {"owner", "location", "unrealized_hq", "eliminated_hq", "realized_hq", "to_unvalued_hq",
            "change_hq"} <= set(d.columns)
    assert set(d[d["unrealized_hq"] != 0]["owner"]) <= {"E_US", "E_EU"}    # the importers hold it
    v3 = r["views"]["v3"]
    assert {"profit_r2_hq_wk", "external_cogs_r2_hq_cum", "unrealized_change_hq_wk",
            "unrealized_balance_hq_wk", "inv_group_hq", "profit_hq_wk"} <= set(v3.columns)


def test_alloc_ledger_records_match_the_plan(alloc_run):
    r, out = alloc_run
    recs = r["records"]
    ids = [s.ship_id for s in recs.shipments]
    assert len(ids) == len(set(ids)) == 527037                  # one record per actual shipment
    assert recs.issues == [] and r["checks"]["issues"] == []
    kinds = r["checks"]["flow_counts"]
    assert kinds == {"purchase_in": 75291, "inbound_move": 75291, "handoff_to_sp": 75291,
                     "outbound_move": 225873, "consumer_sale": 75291}


def test_alloc_conservation_and_external_sales(alloc_run):
    r, out = alloc_run
    c = r["checks"]
    assert c["conservation_ok"]
    es = c["external_sales"]
    assert es["ok_identity"] and es["ok_records"]
    assert es["v3_external_revenue"] == pytest.approx(231673000.0 + 0.0)   # Rest_JP + Rest_US_West (known)


def test_alloc_missing_prices(alloc_run):
    r, out = alloc_run
    m = pd.read_csv(out / "vc_missing_prices.csv")
    got = set(zip(m["edge_id"], m["price_type"]))
    assert got == {("FG_WH_Noda->DC_US_SF", "intercompany"), ("FG_WH_Noda->DC_US_NY", "intercompany"),
                   ("FG_WH_Noda->DC_EU_RTM", "intercompany"),
                   ("DC_US_NY->Rest_US_East", "wholesale"), ("DC_EU_RTM->Rest_FR", "wholesale"),
                   ("DC_EU_RTM->Rest_BE", "wholesale"), ("DC_EU_RTM->Rest_NL", "wholesale")}
    assert set(m.columns) >= {"edge_id", "product_id", "price_type", "week", "price", "currency"}


def test_alloc_fx_is_never_silently_one_or_prior_week(alloc_run):
    r, out = alloc_run
    log = pd.read_csv(out / "vc_fx_log.csv")
    # only the warmup weeks (before the table's first week 2027-W01) use the first week's rate
    first = log[log["method"] == "first_week_rate_before_table"]
    assert (first["requested_week"] < "2027-W01").all() and (first["used_week"] == "2027-W01").all()
    assert set(log["method"]) <= {"first_week_rate_before_table", "missing_unvalued"}
    lines = pd.read_csv(out / "vc_money_lines.csv.gz", usecols=["fx_method", "currency_orig", "amt_hq",
                                                                 "amount_orig", "func_currency"])
    assert "prior_week" not in " ".join(lines["fx_method"].astype(str).unique())


def test_alloc_three_views_and_channels(alloc_run):
    r, out = alloc_run
    v = r["views"]
    assert set(v["v2"]["entity"]) == {"E_JP", "E_US", "E_EU"}
    obs = v["observation"]
    assert set(obs["node"]) == {"Rest_US_East", "Rest_FR", "Rest_BE", "Rest_NL"}   # ② only
    inv = v["inventory"]
    ext = inv[inv["external"] == 1]
    assert set(ext["owner"]) <= {"EXT_CH_US_EAST", "EXT_CH_FR", "EXT_CH_BE", "EXT_CH_NL"}


def test_alloc_round2_without_prices(alloc_run):
    """No intercompany price: the importers' lots are unvalued -- their unrealized profit is not
    0 but unvalued (counted), and round 1 - round 2 still reconciles every week."""
    r, out = alloc_run
    u = r["checks"]["unrealized"]
    assert u["ok"], u
    w = r["views"]["unrealized_week"]
    assert float(w["eliminated_hq"].sum()) == 0                  # no price, no internal profit
    assert int(w["lots_unvalued"].max()) > 0                     # counted, not 0
    assert os.path.exists(out / "vc_unrealized_weekly.csv")
