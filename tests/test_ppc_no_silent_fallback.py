# -*- coding: utf-8 -*-
"""
tests/test_ppc_no_silent_fallback.py — RequestLetter_PPC_NoSilentFallback v0.2（D8）
==================================================================================
金額の結果は、この計画の数量を、このモデルが使うと決めた規則で評価したものだけを出す。

  - 規則の出どころは resolve_ppc_rules() 一か所（モデル → 宣言した共有の規則 → 無ければ未評価）
  - valuation_status：評価済み／一部未評価／未評価。未評価に金額のキーは無い（0 も入れない）
  - 見本の販売データ（SMARTPHONE）は計画からの PPC では作らない
  - 規則の最初の週より前の週の価格は最初の行の値で評価済みとし、件数を記録（大杉さんの判断 (a)）
T01（golden 不変）は tests/test_golden.py。
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import pytest

from wom.ppc.ppc_rules import resolve_ppc_rules, PPCRuleSet, REPO_ROOT
from wom.ppc import ppc_run_info as R

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SAMPLE = os.path.join(REPO, "data", "sample")


def _copy(tmp_path, case, name=None):
    d = str(tmp_path / (name or case))
    shutil.copytree(os.path.join(SAMPLE, case), d)
    return d


def _set_decl(model, value):
    p = os.path.join(model, "planning_config.csv")
    lines = [l for l in open(p, encoding="utf-8") if not l.startswith("ppc_shared_rules_dir")]
    if value is not None:
        lines.append(f"ppc_shared_rules_dir,{value}\n")
    open(p, "w", encoding="utf-8", newline="").writelines(lines)


def _edit_csv(model, name, keep):
    p = os.path.join(model, name)
    df = pd.read_csv(p, dtype=str)
    # row mask as a bool Series (apply() / df[[]] on 0 rows would drop the columns)
    mask = pd.Series([bool(keep(r)) for _, r in df.iterrows()], index=df.index, dtype=bool)
    df.loc[mask].to_csv(p, index=False)


def _run(model, out, **kw):
    from tools.run_headless_from_folder import run
    return run(model, verbose=False, output_ppc_dir=str(out), **kw)


def _kpi(out):
    with open(os.path.join(str(out), "ppc_kpi_summary.json"), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------

def test_t02_declared_shared_rules_fill_missing_files_same_values(tmp_path):
    base = _run(_copy(tmp_path, "bom-test-2026", "a"), tmp_path / "pa")["ppc"]
    m = _copy(tmp_path, "bom-test-2026", "b")
    shared = tmp_path / "shared"
    shared.mkdir()
    shutil.move(os.path.join(m, "ppc_fx_rate.csv"), shared / "ppc_fx_rate.csv")
    _set_decl(m, str(shared))
    src = resolve_ppc_rules(m)
    assert src.sources["ppc_fx_rate.csv"] == f"shared:{shared}" and not src.missing
    snap = _run(m, tmp_path / "pb")["ppc"]
    assert snap == base                                           # values unchanged
    assert _kpi(tmp_path / "pb")["rule_sources"]["sources"]["ppc_fx_rate.csv"].startswith("shared:")


def test_t03_missing_file_without_declaration_is_not_valued(tmp_path):
    m = _copy(tmp_path, "bom-test-2026")
    os.remove(os.path.join(m, "ppc_tariff_rule.csv"))
    snap = _run(m, tmp_path / "p")
    assert snap["psi"]                                             # the plan ran to the end
    p = snap["ppc"]
    assert p["valuation_status"] == "未評価" and "ppc_tariff_rule.csv" in p["reason"]
    assert "gross_margin_pct" not in p and "revenue_base" not in p and "total_lots" not in p
    k = _kpi(tmp_path / "p")
    assert k["rule_sources"]["missing"] == ["ppc_tariff_rule.csv"]
    assert not any(v.startswith("shared") for v in k["rule_sources"]["sources"].values())


def test_t04_header_only_rules_not_valued_no_sample(tmp_path):
    m = _copy(tmp_path, "bom-test-2026")
    for f in os.listdir(m):
        if f.startswith("ppc_"):
            _edit_csv(m, f, lambda r: False)                       # header row only
    snap = _run(m, tmp_path / "p")
    p = snap["ppc"]
    assert p["valuation_status"] == "未評価" and "評価できる販売記録が無い" in p["reason"]
    assert "total_lots" not in p
    assert sorted(os.listdir(tmp_path / "p")) == ["ppc_kpi_summary.json"]   # no ledger
    assert "SMARTPHONE" not in json.dumps(_kpi(tmp_path / "p"), ensure_ascii=False)


def _cookie(tmp_path, name):
    return _copy(tmp_path, "Cookie-jp-2026", name)


def test_t05_partial_products_valued_part_equals_that_product_alone(tmp_path):
    full = _cookie(tmp_path, "full")
    _run(full, tmp_path / "pf")
    ev = pd.read_csv(tmp_path / "pf" / "ppc_event_ledger.csv")
    m = _cookie(tmp_path, "part")
    _edit_csv(m, "ppc_supplier_cost.csv", lambda r: r["product_id"] != "Cookie_Import")
    snap = _run(m, tmp_path / "pp")["ppc"]
    assert snap["valuation_status"] == "一部未評価"
    ex = {(e["product_id"], e["channel_node"]): e for e in snap["excluded"]}
    assert {k[0] for k in ex} == {"Cookie_Import"} and len(ex) == 3
    assert all(e["wom_lots"] > 0 and e["ppc_records"] > 0 and e["qty"] > 0 for e in ex.values())
    loc = ev[(ev["product_id"] == "Cookie_Local") & (ev["ppc_event_type"] == "market_revenue")]
    assert snap["revenue_base"] == pytest.approx(round(float((loc["amount_base"] * loc["qty"]).sum()), 2))


def test_t06_t14_attach_realized_does_not_value_missing_money():
    import wom.planning_state as ps
    md = os.path.join(SAMPLE, "soysauce-jpy-2027-alloc")       # read only (leaf -> market)
    st = {"case": "x", "allocation": {"JP": 1.0}, "plan_eval": {"lots": 10, "profit": 5.0,
                                                               "fx_usd": 150, "material_usd": 6}}
    extras = {"planning_state_extras": {"leaf_out_S": {"A": {"Shop": 10.0}}, "leaf_out_CO": {}}}
    none = ps.attach_realized(st, {"ppc": {"valuation_status": "未評価", "reason": "r"}, **extras},
                              model_dir=md, cap_wk=10)
    r = none["realized"]
    assert "profit" not in r["ppc"] and r["ppc"]["valuation_status"] == "未評価"
    assert r["gap_decomposition"] is None and "保留" in r["ppc"]["comparison"]
    part = ps.attach_realized(st, {"ppc": {"valuation_status": "一部未評価", "reason": "r",
                                           "gross_profit_base": 3.0, "revenue_base": 9.0,
                                           "cost_base": 6.0, "excluded": [{"product_id": "B"}]},
                                   **extras}, model_dir=md, cap_wk=10)
    r = part["realized"]
    assert r["gap_decomposition"] is None and "profit" not in r["ppc"]
    assert r["ppc"]["profit_valued_part"] == 3.0 and "保留" in r["ppc"]["comparison"]


def test_t07_valuechain_fx_without_declaration_reads_no_data_ppc(tmp_path):
    from wom.valuechain.fx import FxTable
    m = _cookie(tmp_path, "c")
    _set_decl(m, None)
    fx = FxTable.load(m, "JPY")
    assert fx.source.startswith("未設定") and fx.base == "JPY"
    rate, method = fx.rate("USD", "JPY", "2027-W01")
    assert rate != rate and method == "missing_unvalued"           # NaN, not data/ppc
    _set_decl(m, "data/ppc")
    fx2 = FxTable.load(m, "JPY")
    assert fx2.source.startswith("shared:data/ppc") and fx2.rate("USD", "JPY", "2027-W01")[0] > 0


def test_t08_demo_still_uses_sample_data(tmp_path):
    r = subprocess.run([sys.executable, "-m", "wom.ppc", "--output-dir", str(tmp_path / "demo"),
                        "--weeks", "8"], cwd=REPO, capture_output=True, text=True,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    assert r.returncode == 0, r.stderr[-2000:]
    k = _kpi(tmp_path / "demo")
    assert k["total_lots"] > 0 and "valuation_status" not in k


def test_t09_product_market_combination_without_price_is_excluded(tmp_path):
    m = _cookie(tmp_path, "c")
    _edit_csv(m, "ppc_market_price.csv",
              lambda r: not (r["product_id"] == "Cookie_Import" and r["market_node"] == "Retail_JP_CVS"))
    snap = _run(m, tmp_path / "p")["ppc"]
    assert snap["valuation_status"] == "一部未評価"
    assert [(e["product_id"], e["channel_node"]) for e in snap["excluded"]] == [("Cookie_Import", "Retail_JP_CVS")]
    ev = pd.read_csv(tmp_path / "p" / "ppc_event_ledger.csv")
    assert not ((ev["product_id"] == "Cookie_Import") & (ev["node_id"] == "Retail_JP_CVS")).any()


def test_t10_explicit_zero_price_is_valued(tmp_path):
    m = _cookie(tmp_path, "c")
    p = os.path.join(m, "ppc_market_price.csv")
    df = pd.read_csv(p, dtype=str)
    df.loc[0, "market_price"] = "0"
    df.to_csv(p, index=False)
    snap = _run(m, tmp_path / "p")["ppc"]
    assert "valuation_status" not in snap                         # 評価済み: snapshot as before
    assert _kpi(tmp_path / "p")["valuation_status"] == "評価済み"


def test_t11_previous_amounts_do_not_survive_in_the_same_folder(tmp_path):
    out = tmp_path / "shared_out"
    _run(_cookie(tmp_path, "c"), out)
    assert os.path.exists(out / "ppc_event_ledger.csv")
    m = _copy(tmp_path, "bom-test-2026")
    os.remove(os.path.join(m, "ppc_market_price.csv"))
    snap = _run(m, out)
    assert snap["ppc"]["valuation_status"] == "未評価" and "revenue_base" not in snap["ppc"]
    assert sorted(os.listdir(out)) == ["ppc_kpi_summary.json"]
    assert "total_revenue_base" not in _kpi(out)
    # GUI gate: an older mark of a valued run must not let the files be read as this plan's
    R.write_run_info(str(out), {"run_id": "X", "model_dir": m, "sales_source": "psi",
                                "valuation_status": "未評価", "reason": "r"})
    ok, label = R.check_ppc_output(str(out), R.make_context(R.STATE_DONE, "X", m))
    assert not ok and "未評価" in label


def test_t12_valuechain_runs_when_ppc_is_not_valued(tmp_path):
    from wom.valuechain.run import run_valuechain
    m = _cookie(tmp_path, "c")
    _set_decl(m, None)                                             # PPC: no FX file -> 未評価
    r = run_valuechain(m, str(tmp_path / "vc"))
    assert r["checks"]["ppc_comparison"].startswith("比較不可")
    assert r["checks"]["conservation_ok"]
    assert os.path.exists(tmp_path / "vc" / "vc_v3_weekly.csv")
    cmp_ = pd.read_csv(tmp_path / "vc" / "vc_ppc_comparison.csv")
    assert len(cmp_) == 1 and "比較不可" in cmp_.loc[0, "explanation"]


def test_t13_relative_declaration_resolves_from_repo_root(tmp_path, monkeypatch):
    m = _copy(tmp_path, "bom-test-2026")
    os.remove(os.path.join(m, "ppc_fx_rate.csv"))
    _set_decl(m, "data/ppc")
    monkeypatch.chdir(tmp_path)
    src = resolve_ppc_rules(m)
    assert src.paths["ppc_fx_rate.csv"] == os.path.join(REPO_ROOT, "data", "ppc", "ppc_fx_rate.csv")
    _set_decl(m, "no/such/dir")
    src2 = resolve_ppc_rules(m)
    assert src2.missing == ["ppc_fx_rate.csv"]                     # no other place is tried


def test_price_before_first_rule_week_is_valued_and_recorded(tmp_path):
    """Owner decision (a), 2026-10-26: a week before the rule's first row uses the
    first row's value (evaluated) and the lookups are counted."""
    m = _copy(tmp_path, "bom-test-2026")
    p = os.path.join(m, "ppc_market_price.csv")
    df = pd.read_csv(p, dtype=str)
    df["week"] = "2099-W01"                                       # every rule row is after the plan
    df.to_csv(p, index=False)
    snap = _run(m, tmp_path / "p")["ppc"]
    assert "valuation_status" not in snap                         # 評価済み
    k = _kpi(tmp_path / "p")
    assert k["valuation_status"] == "評価済み"
    assert k["price_before_first_rule_week"] and all(b["lookups"] > 0 for b in k["price_before_first_rule_week"])
    w = pd.read_csv(tmp_path / "p" / "ppc_warnings.csv")
    assert (w["kind"] == "price_before_first_rule_week").any()


def test_load_without_fallback_stops_on_a_missing_file(tmp_path):
    d = tmp_path / "rules"
    shutil.copytree(os.path.join(REPO, "data", "ppc"), d)
    os.remove(d / "ppc_tariff_rule.csv")
    with pytest.raises(FileNotFoundError):
        PPCRuleSet.load(str(d))
