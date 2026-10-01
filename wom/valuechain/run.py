# -*- coding: utf-8 -*-
"""
モデルのフォルダから台帳を作り、CSV に出す（RequestLetter_StageD_Phase1 §1-8）

    from wom.valuechain.run import run_valuechain
    run_valuechain("data/sample/Cookie-jp-2026", "output/valuechain/Cookie-jp-2026/run_1")

手順：
  1  モデルを一時フォルダに複写し、headless（tools/run_headless_from_folder.run）で計画と PPC を
     実行する（原本には書かない）。計画の方式は identity だけ（legacy なら止める）。
  2  計画の結果（各ノードの実出荷）→ 出荷の記録（records.py）
  3  マスター（masters.py）・為替（fx.py）→ 台帳（ledger.py）→ 三つの視点（views.py）
  4  照合：原価の保存（受入 3）、外部売上（受入 4）、PPC との対応（受入 9）、
     LOVEM の実出荷（受入 2、--lovem-run のとき）

出力（out_dir）：
  vc_run_info.json         計画 ID・入力・条件・通貨・報告の開始週・件数
  vc_shipments.csv.gz      出荷の記録（1 行 ＝ 実出荷 1 件。ID は LOVEM と同じ）
  vc_money_lines.csv.gz    金額の明細
  vc_inventory_weekly.csv  在庫（週末の残高。所有者・所在・品目ごと）
  vc_v1_weekly.csv / vc_v2_weekly.csv / vc_v3_weekly.csv / vc_observation_weekly.csv
  vc_missing_prices.csv    未設定価格の一覧（そのまま vc_price_rule.csv に移せる列）
  vc_fx_log.csv            為替の記録（最初の週のレートを使った、未評価になった）
  vc_price_log.csv         価格の記録（有効な週より前に最初の行の価格を使った）
  vc_conservation.csv      原価の保存（法人 × 週）
  vc_ppc_comparison.csv    PPC との対応
  vc_edge_flows.csv        区間 × 週 × lot 数（World Map 用）
  vc_cost_policy.csv       費用の分け方の表（policy.py の写し）
  vc_checks.json           照合の結果
  ppc/                     同じ計画の PPC の出力（今の PPC のまま）
"""
from __future__ import annotations

import csv
import datetime
import gzip
import json
import os
import shutil
import tempfile
from typing import Optional

import pandas as pd

from wom.valuechain import policy as POL
from wom.valuechain.fx import FxTable
from wom.valuechain.ledger import LINE_COLS, Ledger
from wom.valuechain.masters import load_masters
from wom.valuechain.records import build_records, edge_flows
from wom.valuechain.views import build_views, check_conservation, check_external_sales

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SHIP_COLS = ["plan_id", "ship_id", "product", "lot_id", "item", "node", "node_id", "phys_from", "to",
             "edge", "kind", "ship_week_index", "ship_week", "arrival_week_index", "arrival_week",
             "arrival_in_horizon", "revenue_week", "lots", "units", "unit"]


def _plugins_for(model_dir: str) -> str:
    case = os.path.basename(os.path.abspath(model_dir).rstrip("/\\"))
    g = os.path.join(REPO, "tests", "golden", case + ".json")
    if os.path.exists(g):
        with open(g, encoding="utf-8") as f:
            return ",".join(json.load(f).get("config", {}).get("plugins", [])) or "none"
    return "safe"


def plan_model(model_dir: str, ppc_out: str, plugins: Optional[str] = None):
    """Headless plan + PPC on a temp copy; returns (sc_tree, snapshot, plugins, lot_flow_mode)."""
    import tools.run_headless_from_folder as H
    from wom.engine.warmup import read_lot_flow_mode
    mode = read_lot_flow_mode(model_dir) or "identity"
    if mode != "identity":
        raise ValueError(f"the ledger needs an identity plan; {model_dir} says lot_flow_mode={mode}")
    plugins = plugins or _plugins_for(model_dir)
    case = os.path.basename(os.path.abspath(model_dir).rstrip("/\\"))
    tmp = tempfile.mkdtemp(prefix="wom_vc_")
    work = os.path.join(tmp, case)
    shutil.copytree(model_dir, work)
    cap = {}
    orig = H._run_ppc

    def spy(sc_tree, weeks, mdir, out, verbose):
        cap["t"] = sc_tree
        return orig(sc_tree, weeks, mdir, out, verbose)
    H._run_ppc = spy
    try:
        snap = H.run(work, plugins_spec=plugins, output_ppc_dir=ppc_out, verbose=False,
                     lot_flow_mode="identity")
    finally:
        H._run_ppc = orig
        shutil.rmtree(tmp, ignore_errors=True)
    return cap["t"], snap, plugins, "identity"


def build_ledger(sc_tree, model_dir: str, plan_id: str, sink=None) -> dict:
    """Build the ledger from an already planned tree (the GUI uses this after its own
    Planning Engine run; no re-planning). Returns records / masters / fx / ledger / views /
    report_idx. `sink` receives every money line (None: lines are only aggregated)."""
    from wom.engine.warmup import first_nonzero_demand_week
    mode = str(getattr(sc_tree, "lot_flow_mode", "") or "").lower()
    if mode != "identity":
        raise ValueError(f"the ledger needs an identity plan (lot_flow_mode={mode or 'not set'})")
    records = build_records(sc_tree, plan_id)
    masters = load_masters(model_dir, records.terminal_moms(), records.physical_edges())
    fx = FxTable.load(model_dir, os.path.join(REPO, "data", "ppc"))
    labels = records.week_labels
    rs = masters.report_start or first_nonzero_demand_week(os.path.join(model_dir, "demand_forecast.csv"))
    report_idx = labels.index(rs) if rs in labels else 0
    led = Ledger(records, masters, fx, sink=sink).run()
    views = build_views(led, report_idx)
    return {"records": records, "masters": masters, "fx": fx, "ledger": led, "views": views,
            "report_idx": report_idx, "plan_id": plan_id, "model_dir": model_dir}


def has_ledger_masters(model_dir: str) -> bool:
    return all(os.path.exists(os.path.join(model_dir, f)) for f in
               ("vc_config.csv", "vc_entity.csv", "vc_node_assignment.csv", "vc_price_rule.csv"))


def run_valuechain(model_dir: str, out_dir: str, lovem_run: Optional[str] = None,
                   plugins: Optional[str] = None) -> dict:
    from wom.lovem.observer import git_state, model_hashes
    from wom.engine.warmup import first_nonzero_demand_week
    model_dir = os.path.abspath(model_dir)
    os.makedirs(out_dir, exist_ok=True)
    case = os.path.basename(model_dir.rstrip("/\\"))
    gs = git_state(REPO)
    plan_id = f"{case}@{gs['code_sha'][:7]}{'+dirty' if gs['dirty'] else ''}:vc"
    hashes_before = model_hashes(model_dir)

    sc_tree, snap, plugins, mode = plan_model(model_dir, os.path.join(out_dir, "ppc"), plugins)
    from tools.run_headless_from_folder import _select_plugins
    plugins = ",".join(sorted(type(p).__name__ for p in _select_plugins(plugins)[0]))
    records = build_records(sc_tree, plan_id)
    masters = load_masters(model_dir, records.terminal_moms(), records.physical_edges())
    fx = FxTable.load(model_dir, os.path.join(REPO, "data", "ppc"))
    labels = records.week_labels

    rs = masters.report_start or first_nonzero_demand_week(os.path.join(model_dir, "demand_forecast.csv"))
    report_idx = labels.index(rs) if rs in labels else 0

    # ── ledger (money lines streamed to disk) ──
    lines_path = os.path.join(out_dir, "vc_money_lines.csv.gz")
    with gzip.open(lines_path, "wt", encoding="utf-8", newline="") as gz:
        wr = csv.writer(gz)
        wr.writerow(LINE_COLS)
        led = Ledger(records, masters, fx, sink=wr.writerow).run()
    views = build_views(led, report_idx)

    # ── outputs ──
    _write_shipments(records, os.path.join(out_dir, "vc_shipments.csv.gz"))
    views["inventory"].to_csv(os.path.join(out_dir, "vc_inventory_weekly.csv"), index=False)
    for k in ("v1", "v2", "v3", "observation"):
        views[k].to_csv(os.path.join(out_dir, f"vc_{k}_weekly.csv"), index=False)
    miss = pd.DataFrame(list(led.missing.values()),
                        columns=["edge_id", "product_id", "price_type", "week", "price", "currency",
                                 "seller_entity", "buyer_entity", "lots", "units", "first_ship_week",
                                 "last_ship_week"])
    miss.to_csv(os.path.join(out_dir, "vc_missing_prices.csv"), index=False)
    pd.DataFrame(fx.log_rows(), columns=["method", "from_currency", "to_currency", "requested_week",
                                         "used_week", "count", "context", "table"]).to_csv(
        os.path.join(out_dir, "vc_fx_log.csv"), index=False)
    pd.DataFrame(list(masters.price_log.values()),
                 columns=["what", "key", "requested_week", "used_week", "count", "method"]).to_csv(
        os.path.join(out_dir, "vc_price_log.csv"), index=False)
    cons = check_conservation(led, views)
    cons.to_csv(os.path.join(out_dir, "vc_conservation.csv"), index=False)
    ext = check_external_sales(led, views, records)
    edge_flows(records.shipments, labels).to_csv(os.path.join(out_dir, "vc_edge_flows.csv"), index=False)
    pd.DataFrame(POL.policy_table_rows()).to_csv(os.path.join(out_dir, "vc_cost_policy.csv"), index=False)
    ppc_cmp = compare_with_ppc(views, os.path.join(out_dir, "ppc"), masters)
    ppc_cmp.to_csv(os.path.join(out_dir, "vc_ppc_comparison.csv"), index=False)

    checks = {
        "conservation_ok": bool(cons["ok"].all()), "conservation_rows": int(len(cons)),
        "conservation_max_abs_diff": float(cons["diff"].abs().max()) if len(cons) else 0.0,
        "external_sales": ext,
        "issues": led.issues + records.issues,
        "flow_counts": dict(led.flow_counts),
        "missing_price_rows": int(len(miss)),
        "fx_log_rows": len(fx.log_rows()),
        "fx_first_week_rate_uses": int(sum(r["count"] for r in fx.log_rows()
                                           if r["method"] == "first_week_rate_before_table")),
        "fx_unvalued_uses": int(sum(r["count"] for r in fx.log_rows() if r["method"] == "missing_unvalued")),
        "holding_rate": "未設定（holding_rate_weekly が空欄。0 として計算しない）"
                        if masters.holding_rate_weekly is None else masters.holding_rate_weekly,
        "unvalued_lines": int(views["agg"]["n_unvalued"].sum()),
    }
    if lovem_run:
        checks["lovem"] = compare_with_lovem(records, lovem_run, gs, hashes_before, plugins)
    with open(os.path.join(out_dir, "vc_checks.json"), "w", encoding="utf-8") as f:
        json.dump(checks, f, ensure_ascii=False, indent=1, default=str)

    info = {
        "plan_id": plan_id, "case": case, "model_dir": model_dir, "code": gs,
        "model_hashes": hashes_before, "model_unchanged_by_run": model_hashes(model_dir) == hashes_before,
        "plugins": plugins, "lot_flow_mode": mode, "cpu_size": records.cpu_size,
        "weeks": [labels[0], labels[-1], len(labels)], "report_start": labels[report_idx],
        "report_start_source": "vc_config.csv" if masters.report_start else "first nonzero demand week",
        "currencies": {"hq": masters.hq_currency, "common": masters.common_currency,
                       "fx_table": fx.source, "fx_base": fx.base},
        "entities": {k: vars(v) for k, v in masters.entities.items()},
        "shipments": len(records.shipments),
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "round": "第 1 回（内部の未実現利益の消去前）",
        "ppc_snapshot": snap.get("ppc"),
    }
    with open(os.path.join(out_dir, "vc_run_info.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1, default=str)
    return {"info": info, "checks": checks, "views": views, "ledger": led, "records": records,
            "ppc_comparison": ppc_cmp}


def _write_shipments(records, path):
    labels = records.week_labels
    with gzip.open(path, "wt", encoding="utf-8", newline="") as gz:
        wr = csv.writer(gz)
        wr.writerow(SHIP_COLS)
        for s in records.shipments:
            aw = s.arrival_week
            wr.writerow([records.plan_id, s.ship_id, s.product, s.lot_id, s.item, s.node, s.node_id,
                         s.phys_from, s.to, s.edge, s.kind, s.week, labels[s.week],
                         "" if aw is None else aw,
                         "" if aw is None or aw >= len(labels) else labels[aw],
                         int(s.arrival_in_horizon), labels[s.week], 1, s.units,
                         f"lot x cpu_size({records.cpu_size:g}) x bom_qty"])


# ──────────────────────────────────────────────────────────────────────
def compare_with_ppc(views, ppc_dir, masters) -> pd.DataFrame:
    """受入 9：PPC と台帳の V3（全期間・HQ 通貨）を並べ、違いを項目ごとに説明する。"""
    ev = pd.read_csv(os.path.join(ppc_dir, "ppc_event_ledger.csv"), low_memory=False)
    ev["total"] = ev["amount_base"] * ev["qty"]
    with open(os.path.join(ppc_dir, "ppc_kpi_summary.json"), encoding="utf-8") as f:
        kpi = json.load(f)
    a = views["agg"]
    cons = a[a["consolidated"]]
    rows = []

    def add(item, ppc, vc, n_unvalued, note):
        rows.append({"item": item, "ppc": ppc, "ledger_v3": vc,
                     "difference_ledger_minus_ppc": (vc - ppc) if (ppc is not None and vc is not None) else None,
                     "ledger_unvalued_lines": n_unvalued, "explanation": note})

    # revenue by channel
    rev = ev[ev["ppc_event_type"] == "market_revenue"].groupby(["product_id", "node_id"])["total"].sum()
    for (prod, ch), ppc_amt in rev.items():
        a_ = masters.assignment.get((ch, prod))
        ctype = a_.channel_type if a_ else ""
        if ctype == "external":
            ent = a_.entity_id
            x = cons[(cons["kind"] == "revenue") & (cons["scope"] == "external") &
                     (cons["product"] == prod) & (cons["counterparty"] == ent)]
            obs = a[(a["kind"] == "observation_sale") & (a["product"] == prod) & (a["node"] == ch)]
            add(f"売上 {prod} {ch}（②）", ppc_amt, float(x["hq"].sum()), int(x["n_unvalued"].sum()),
                f"PPC は消費者への販売（{ch} の市場価格）をグループの売上にしている。台帳では ② の外部"
                f"チャネルなので、グループの外部売上は DC→{ch} の卸価格（未設定なら未評価）。"
                f"消費者への販売は観測（{float(obs['hq'].sum()):,.0f}）で、グループの売上に足さない")
        else:
            x = cons[(cons["kind"] == "revenue") & (cons["scope"] == "external") &
                     (cons["product"] == prod) & (cons["node"] == ch)]
            add(f"売上 {prod} {ch}（{'①' if ctype == 'own' else '③' if ctype == 'online' else ctype}）",
                ppc_amt, float(x["hq_known"].sum()), int(x["n_unvalued"].sum()),
                "同じ市場価格 × 同じ実出荷。為替は両方とも販売週。未評価の件数は、原価が分からない販売"
                "（売上の額は分かるので、この列には含める）")
    ext_rev = cons[(cons["kind"] == "revenue") & (cons["scope"] == "external")]
    add("売上 合計（額の分かる外部売上）", float(kpi["total_revenue_base"]), float(ext_rev["hq_known"].sum()),
        int(ext_rev["n_unvalued"].sum()), "上の行の合計")
    # cost by family (group basis acquisitions + expenses), whole horizon
    fam_ppc = {"仕入（供給者）": ["supplier_cost"], "加工・取扱": ["conversion_cost"],
               "運賃": ["logistics_cost"], "関税": ["tariff_cost"], "保険": ["insurance_cost"],
               "保管": ["warehouse_cost"], "SGA": ["sga_cost"], "販促": ["marketing_cost"]}
    fam_vc = {"仕入（供給者）": ["purchase"], "加工・取扱": ["conversion_cost"], "運賃": ["freight"],
              "関税": ["tariff"], "保険": ["insurance"], "保管": ["warehouse_cost"], "SGA": ["sga_cost"],
              "販促": ["marketing_cost"]}
    acq = cons[(cons["kind"] == "acquisition") & cons["basis"].str.contains("group") &
               ~cons["scope"].isin(["intercompany", "management"])]
    exp = cons[cons["kind"] == "expense"]
    for name, types in fam_ppc.items():
        p = float(ev[ev["ppc_event_type"].isin(types)]["total"].sum())
        v = acq[acq["family"].isin(fam_vc[name])]
        e = exp[exp["family"].isin(fam_vc[name])]
        add(f"費用 {name}", p, float(v["hq_known"].sum() + e["hq_known"].sum()),
            int(v["n_unvalued"].sum() + e["n_unvalued"].sum()),
            "PPC は販売された lot の費用を販売週の為替でまとめて計上。台帳は発生した週（助走週を含む）"
            "の為替で、グループの外から得た原価・在庫原価・費用として計上（全期間の合計を比べる）。"
            "台帳の値は金額の分かる明細の合計（未評価の lot に付いた運賃・関税も含む）")
    ext_cogs = cons[(cons["kind"] == "cogs") & (cons["scope"] == "external") & (cons["basis"] == "entity")]
    add("原価 合計（PPC：総原価／台帳：外部売上の原価＋費用）", float(kpi["total_cost_base"]),
        float(ext_cogs["hq"].sum() + exp["hq"].sum()),
        int(ext_cogs["n_unvalued"].sum() + exp["n_unvalued"].sum()),
        "台帳の外部売上の原価は法人の帳簿の原価（法人間の価格を含む＝消去前）。② の CVS などへの"
        "出荷の原価も外部売上の原価に入る")
    ic = cons[(cons["kind"] == "revenue") & (cons["scope"] == "intercompany")]
    icc = cons[(cons["kind"] == "cogs") & (cons["scope"] == "intercompany") & (cons["basis"] == "entity")]
    add("内部取引の利益（消去前）", 0.0, float(ic["hq"].sum() - icc["hq"].sum()),
        int(ic["n_unvalued"].sum() + icc["n_unvalued"].sum()),
        "PPC は移転価格を売上にしない（Profit Zone の mom_profit にだけ使う）。台帳 V3（第 1 回）は"
        "法人間の売上と原価を消し、その差（内部の利益）を消去前として残す")
    v3 = views["v3"]
    prof = float(v3["profit_hq_wk"].sum()) if len(v3) else 0.0
    add("利益 合計（全期間、消去前）", float(kpi["gross_profit_base"]), prof,
        int(v3["n_unvalued_wk"].sum()) if "n_unvalued_wk" in v3 else 0,
        "差は上の項目（② の売上、未評価、費用の計上のしかた）の合計")
    return pd.DataFrame(rows)


def compare_with_lovem(records, lovem_run, gs, hashes, plugins) -> dict:
    """受入 2：出荷の記録 ↔ LOVEM の実出荷（actual_ship）を 1 対 1 で照合する。"""
    with open(os.path.join(lovem_run, "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    lev = {}
    dup = 0
    with gzip.open(os.path.join(lovem_run, "events.jsonl.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("event_type") != "actual_ship":
                continue
            if e["event_id"] in lev:
                dup += 1
            lev[e["event_id"]] = (e["product_id"], e["node_id"], e["week_index"], e["lot_id"],
                                  e.get("quantity"))
    mine = {}
    mdup = 0
    for s in records.shipments:
        if s.ship_id in mine:
            mdup += 1
        mine[s.ship_id] = (s.product, s.node_id, s.week, s.lot_id, 1)
    missing = sorted(set(lev) - set(mine))
    extra = sorted(set(mine) - set(lev))
    diff = [k for k in set(lev) & set(mine) if lev[k] != mine[k]]
    gaps = man.get("coverage", {}).get("known_gaps", [])
    return {
        "lovem_run": lovem_run, "lovem_run_id": man.get("run_id"), "ledger_plan_id": records.plan_id,
        "same_code_sha": man.get("code_sha") == gs["code_sha"],
        "same_model_inputs": man.get("model_hashes") == hashes,
        "same_plugins": sorted(man.get("plugins", [])) == sorted(p for p in plugins.split(",") if p),
        "lovem_lot_flow_mode": man.get("lot_flow_mode"),
        "lovem_actual_ship": len(lev), "ledger_shipments": len(mine),
        "matched": len(set(lev) & set(mine)) - len(diff), "field_mismatch": len(diff),
        "missing_in_ledger": len(missing), "extra_in_ledger": len(extra),
        "duplicates_lovem": dup, "duplicates_ledger": mdup,
        "examples": {"missing": missing[:5], "extra": extra[:5], "mismatch": diff[:5]},
        "lovem_known_gaps": [g.get("item") for g in gaps],
        "ok": not missing and not extra and not diff and not dup and not mdup,
    }
