#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_headless_from_folder.py
===========================
GUI 抜きで「モデルフォルダ → Planning Engine（SCTree＋プラグイン＋Backward/copy/Forward）
→ PPC」を実行し、主要 KPI の**スナップショット JSON** を出力するヘッドレス・ランナー。

目的（Anti-Degrade / Phase 1a）：
  操業制約レイヤー等のエンジン改修に着手する**前に**、既存ケースの挙動を golden として
  固定するための "網"。GUI の `_planning_thread` / `_run_ppc_from_planning`（wom/gui/app.py）
  と同じ順序・同じエンジン関数を呼ぶ（＝orchestration の忠実な移植。既存コードは無変更）。

使い方（リポジトリ直下で）：
  python -m tools.run_headless_from_folder --model-dir data/sample/soysauce-us-2027
  python -m tools.run_headless_from_folder --model-dir data/sample/soysauce-us-2027 \
         --out tests/golden/soysauce-us-2027.json
  # 全ケースを golden 化（例）
  #   for d in data/sample/*/ ; do python -m tools.run_headless_from_folder --model-dir "$d" \
  #       --out "tests/golden/$(basename $d).json" ; done

プラグイン（--plugins）：
  safe（既定）= HolidayCalendarPlugin, BufferingStockOptimizerPlugin, CapacityOverridePlugin
              （いずれもデータ/設定が無ければ no-op。DemandSmoothing は需要を変えるため既定で除外）
  all  = 全ビルトイン / none = 無効 / それ以外 = クラス名の comma 区切りで明示
  rice 等 収穫ケースは：--plugins HolidayCalendarPlugin,BufferingStockOptimizerPlugin,CapacityOverridePlugin,HarvestBatchPlugin

忠実性の検証：本ランナーの出力（GM・trust events 等）が GUI の実値と一致する事を人手で確認してから
golden として採用する（＝ハーネス自体が正しい事の担保）。
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys

import pandas as pd

# --- PSI バケット定数（psi4supply[w][bucket]）。plan_node に無ければ既定値 ---
try:
    from wom.model.plan_node import S, CO, I, P            # type: ignore
except Exception:
    S, CO, I, P = 0, 1, 2, 3

SAFE_DEFAULT = {
    "HolidayCalendarPlugin",
    "BufferingStockOptimizerPlugin",
    "CapacityOverridePlugin",
}


# ──────────────────────────────────────────────────────────────────────
def _detect_period(dem_path: str):
    """demand_forecast.csv から (start_week, n_weeks) を自動検出（GUI と同じ関数
    wom/engine/plan_period.detect_plan_period：最初の週から最後の週までの連続した暦の週。
    CSV に無い週は需要 0 として含め、警告を出す。RequestLetter_PeriodDetection_Fix）。"""
    from wom.engine.plan_period import detect_plan_period
    p = detect_plan_period(dem_path)
    if p.filled_weeks:
        print(f"[Period] WARNING {p.warning()}")
    return p.start, p.n_weeks


def _build_week_labels(start: str, n_weeks: int):
    import re, datetime
    m = re.match(r"(\d{4})-W(\d+)", start)
    yr, wk = (int(m.group(1)), int(m.group(2))) if m else (2024, 1)
    weeks, d = [], datetime.date.fromisocalendar(yr, wk, 1)
    for _ in range(n_weeks):
        y2, w2, _ = d.isocalendar()
        weeks.append(f"{y2}-W{w2:02d}")
        d += datetime.timedelta(weeks=1)
    return weeks


def _select_plugins(spec: str):
    """--plugins 指定から (active_instances, harvest_instance) を返す。"""
    from wom.plugins import ALL_BUILTIN_PLUGINS
    spec = (spec or "safe").strip()
    active, harvest = [], None
    if spec == "none":
        names = set()
    elif spec == "all":
        names = None  # all
    elif spec == "safe":
        names = SAFE_DEFAULT
    else:
        names = {s.strip() for s in spec.split(",") if s.strip()}
    for cls in ALL_BUILTIN_PLUGINS:
        inst = cls()
        cn = cls.__name__
        take = (names is None) or (cn in names) or (getattr(inst, "name", "") in names)
        if take:
            active.append(inst)
            if "Harvest" in cn:
                harvest = inst
    return active, harvest


# ──────────────────────────────────────────────────────────────────────
def run(model_dir: str, plugins_spec: str = "safe", output_ppc_dir: str = "output/ppc",
        verbose: bool = True, demand_file: str = "demand_forecast.csv",
        planning_state: bool = False, lot_flow_mode: str = None,
        flow_check_dir: str = None, extra_plugins: list = None) -> dict:
    """GUI の planning + PPC を再現し、KPI スナップショット dict を返す。

    lot_flow_mode（RequestLetter_LotIdentityFlow C1）："identity"／"legacy"。
        優先順：この引数 → モデルの planning_config.csv の lot_flow_mode →
        既定 "identity"。snapshot の config には、legacy 以外のときだけ
        "lot_flow_mode" を記録する（既存 golden＝legacy の config と一致させるため）。
    flow_check_dir（RequestLetter_FlowCheck V3）：指定したときだけ、Flow Check の
        表1・表2（wom/engine/flow_check.py）を CSV で書き出す。snapshot には入れない。
    forward（RequestLetter_FlowCheck Part 2）：legacy は従来どおり cap_hard_sealed。
        identity は cap_hard_deferred_lots／cap_hard_deferred_lot_weeks を書き、
        cap_hard_sealed は書かない（identity では封印せず繰り延べるため）。

    Args:
        demand_file: 需要 CSV のファイル名（既定 "demand_forecast.csv"）。
            Phase 7（`requests/Phase7_RequestLetter_to_CodeKun.md` V2.3）：
            `"demand_forecast_A03.csv"` のように、A系統の配分から生成した
            需要ファイルを差し替えて読める。`materialize_warmup()` にも
            **同じ値**を渡す（V2.4・`demand_file` の分岐が2箇所あることに注意）。
        extra_plugins: 名前の指定とは別に、このプラグインの実体も登録する（測定の道具が、
            設定を持たせたプラグインを渡すため。RequestLetter_GenerationLine_UpperLayer）。
            既定 None のときの動きは変わらない。snapshot の config にはクラス名が入る。
        planning_state: True のときだけ、返却に `"planning_state_extras"` キーを
            足す（週リスト・市場別 S/CO）。既定 False のときの返却は**現行と
            1バイトも変わらない**（C8）。golden 13ケースはこの経路を通らない。
    """
    from wom.model.lot_generator import assign_demand_lots_from_dict
    from wom.engine.lane_assignment import LaneTable
    from wom.engine.hook_bus import (
        HookBus, HOOK_PRE_PLAN, HOOK_POST_BACKWARD,
        HOOK_POST_COPY, HOOK_POST_FORWARD, HOOK_POST_PLAN)
    from wom.engine.sc_tree_builder import build_sc_tree_from_master
    from wom.engine.backward_planner import BackwardPlanner
    from wom.engine.plan_copy import copy_demand_to_supply
    from wom.engine.forward_planner import ForwardPlanner

    def _p(name):  # model-local file path
        return os.path.join(model_dir, name)

    # ── Planning warm-up（Phase 2, opt-in）─────────────────────────
    #   planning_config.csv があれば助走行を materialize（demand=0 / cap・opcal コピー）。
    #   period 検出より前に走らせる（＝早い start 週を含める）。config 無し→no-op。
    from wom.engine.warmup import (materialize_warmup, format_summary, read_cpu_size,
                                   read_lot_flow_mode)
    from wom.engine.forward_planner import resolve_lot_flow_mode, LOT_FLOW_LEGACY
    _wsum = materialize_warmup(model_dir, demand_file=demand_file)
    if verbose:
        print("[Headless]", format_summary(_wsum))
    lot_flow_mode = resolve_lot_flow_mode(lot_flow_mode or read_lot_flow_mode(model_dir))
    if verbose:
        print(f"[Headless] lot_flow_mode={lot_flow_mode}")

    # ── 期間の自動検出 ─────────────────────────────────────────────
    dem_path = _p(demand_file)
    from wom.engine.plan_period import detect_plan_period
    period = detect_plan_period(dem_path)
    if period.filled_weeks:
        print(f"[Headless] WARNING {period.warning()}")
    start, n_weeks = period.start, period.n_weeks
    weeks = _build_week_labels(start, n_weeks)
    assert weeks == period.weeks
    if verbose:
        print(f"[Headless] {os.path.basename(model_dir.rstrip('/'))}: "
              f"period {start} x {n_weeks} weeks")

    # ── SCTree 構築 ────────────────────────────────────────────────
    sc_tree_df = pd.read_csv(_p("sc_tree_master.csv"))
    sc_tree = build_sc_tree_from_master(sc_tree_df, weeks)
    # 評価（sc_tree_to_planning_df・Strategic KPI・PPC ブリッジ）が、どの方式の計画かを
    # 知るための印（RequestLetter_iPhoneWarmup_EVUpdateKitting_S2 C2）。計画は変えない。
    sc_tree.lot_flow_mode = lot_flow_mode
    sc_tree.period_filled_weeks = list(period.filled_weeks)   # weeks not in the demand CSV (demand 0)
    # Request Letter A (request_letter_a_cpu_size_to_plan.md) discrepancy,
    # resolved here and flagged for owner review: sc_tree.cpu_size is read
    # from planning_config.csv and used by the KPI/display conversion layer
    # (sc_tree_to_df.py, GUI charts) ONLY. It is deliberately NOT passed to
    # assign_demand_lots_from_dict() below (which stays cpu_size=1) -- doing
    # so would make ceil(qty/cpu_size) change the LOT COUNT whenever cpu_size
    # != 1, contradicting Letter A section 4.2's explicit requirement that
    # lot count is unchanged when cpu_size goes 1 -> 12.
    sc_tree.cpu_size = read_cpu_size(model_dir)
    if verbose:
        print(f"[Headless] products: {sc_tree.products}")

    # ── HookBus + プラグイン ───────────────────────────────────────
    bus = HookBus()
    cfg = {"n_weeks": n_weeks, "start_week": start,
           "cap_path": _p("capacity_plan.csv"),
           "holiday_cal_path": _p("holiday_calendar.csv"),
           # read by plugins that trial-run ForwardPlanner (BufferingStockOptimizer)
           "lot_flow_mode": lot_flow_mode}
    active_plugins, harvest_plugin = _select_plugins(plugins_spec)
    active_plugins = active_plugins + list(extra_plugins or [])
    for pl in active_plugins:
        pl.register(bus)
    if verbose:
        print(f"[Headless] plugins: {[type(p).__name__ for p in active_plugins]}")

    # ── 需要 → ロット ──────────────────────────────────────────────
    demand_dict = {}
    dem_df = pd.read_csv(dem_path)
    if {"sku_id", "region", "week", "quantity"}.issubset(dem_df.columns):
        for _, r in dem_df.iterrows():
            k = (str(r["sku_id"]), str(r["region"]), str(r["week"]))
            demand_dict[k] = demand_dict.get(k, 0) + int(r["quantity"])
    # NOTE: cpu_size stays 1 here deliberately -- see the note by
    # sc_tree.cpu_size assignment above (Request Letter A discrepancy).
    assign_demand_lots_from_dict(sc_tree, demand_dict, cpu_size=1)

    # ── 能力（capacity_plan → cap_hard [+ cap_soft]、共有ローダ）───
    #   GUI(app.py) と同一の単一ローダ。cap_soft 列は opt-in（無ければ従来どおり）。
    from wom.engine.capacity_sealer import load_capacity_dataframe, load_operating_calendar
    cap_path = _p("capacity_plan.csv")
    if os.path.exists(cap_path):
        # RequestLetter_CapacityZeroBlank: an unreadable capacity row stops the
        # run (formerly every error was swallowed and the capacity was lost).
        load_capacity_dataframe(sc_tree, pd.read_csv(cap_path, dtype={"max_supply": str}),
                                weeks, source=cap_path)

    # ── 操業カレンダー（per-node shift plan; Phase 2、opt-in）─────────
    #   BackwardPlanner 生成より前に node.op_shifts をセットしておく必要がある。
    opcal_path = _p("operating_calendar.csv")
    if os.path.exists(opcal_path):
        try:
            load_operating_calendar(sc_tree, pd.read_csv(opcal_path), weeks)
        except Exception:
            pass

    # ── Lane / Push ────────────────────────────────────────────────
    lane_path = _p("lane_assignment.csv")
    lane_table = (LaneTable.from_csv(lane_path)
                  if os.path.exists(lane_path) else LaneTable.empty())
    push_path = _p("push_config.csv")

    # ── Planning pipeline（app.py _planning_thread と同順序）───────
    bus.fire(HOOK_PRE_PLAN, sc_tree=sc_tree, weeks=weeks, config=cfg)
    _cap_hard_sealed = 0      # Forward が cap_hard で seal した lot 総数（legacy）
    _cap_def_lots    = 0      # identity：cap_hard で繰り延べた lot（重複なし）
    _cap_def_weeks   = 0      # identity：繰り延べの のべ lot 週
    _fres_by_prod: dict = {}  # Flow Check 用
    _cap_soft_viol   = 0      # Forward の cap_soft 違反（残業要）件数
    _bwd_soft_env    = 0      # Backward の cap_soft envelope 違反（計画段階の残業帯）件数
    _bres_all: list = []      # Phase 7: planning_state=True のときだけ使う（週リスト用）
    _fres_all: list = []
    for prod_nm in sc_tree.products:
        _bres = BackwardPlanner(sc_tree, lane_table=lane_table, config=cfg).run(prod_nm)
        _bres_all.append(_bres)
        _bwd_soft_env += len(getattr(_bres, "cap_soft_envelope_violations", []) or [])
        bus.fire(HOOK_POST_BACKWARD, sc_tree=sc_tree, prod_nm=prod_nm, weeks=weeks, config=cfg)
        copy_demand_to_supply(sc_tree, prod_nm)
        bus.fire(HOOK_POST_COPY, sc_tree=sc_tree, prod_nm=prod_nm, weeks=weeks, config=cfg)
        # PUSH/PULL
        if os.path.exists(push_path):
            import csv as _csv
            from wom.engine.push_pull import PushProductionPlanner, PushConfig
            cfgs = {}
            with open(push_path, newline="", encoding="utf-8") as pf:
                for pr in _csv.DictReader(pf):
                    if pr.get("sku_id", "").strip() == prod_nm:
                        cfgs[prod_nm] = PushConfig(
                            node_id=pr.get("node_id", "").strip(),
                            push_qty_per_week=int(pr.get("push_qty_per_week") or 0),
                            buffer_lots=int(pr.get("buffer_lots") or 0),
                            sku_id=prod_nm,
                            mode_only=pr.get("mode_only", "").strip().lower() == "true",
                            mom_ref_node_id=pr.get("mom_ref_node_id", "").strip(),
                            pre_build_qty_per_week=int(pr.get("pre_build_qty_per_week") or 0),
                            pre_build_end_week=pr.get("pre_build_end_week", "").strip(),
                            push_lead_time_weeks=int(pr.get("push_lead_time_weeks") or 0),
                        )
            if cfgs:
                PushProductionPlanner(sc_tree).setup_all(cfgs)
        opening_inv = getattr(harvest_plugin, "opening_inv", {}) if harvest_plugin else {}
        _fres = ForwardPlanner(sc_tree, opening_inv=opening_inv,
                               lot_flow_mode=lot_flow_mode).run(prod_nm)
        _fres_all.append(_fres)
        _fres_by_prod[prod_nm] = _fres
        _cap_hard_sealed += int(getattr(_fres, "cap_hard_sealed", 0) or 0)
        _cap_def_lots    += int(getattr(_fres, "cap_hard_deferred_lots", 0) or 0)
        _cap_def_weeks   += int(getattr(_fres, "cap_hard_deferred_lot_weeks", 0) or 0)
        _cap_soft_viol   += len(getattr(_fres, "cap_soft_violations", []) or [])
        # B4（RequestLetter_iPhoneWarmup_EVUpdateKitting_S2、記録だけ）：供給側に同じ
        # Lot_ID が 2 件以上あった（ノード・週・ID）。照合で 1 件だけが出荷され、残りは
        # 在庫にも残らない。--quiet でも警告を 1 行出す。snapshot には入れない。
        _dups = list(getattr(_fres, "supply_duplicate_ids", []) or [])
        if _dups:
            _d0 = _dups[0]
            print(f"[Headless] WARNING {prod_nm}: 供給側に同じ Lot_ID が 2 件以上 "
                  f"{len(_dups)} 件（ノード・週・ID）。例 {_d0[0]} {_d0[1]} {_d0[2]} ×{_d0[3]}"
                  f"（Flow Check 表 1 の「同一ID重複」）")
        bus.fire(HOOK_POST_FORWARD, sc_tree=sc_tree, prod_nm=prod_nm, weeks=weeks, config=cfg)
    bus.fire(HOOK_POST_PLAN, sc_tree=sc_tree, weeks=weeks, config=cfg)

    # ── Flow Check（RequestLetter_FlowCheck V3、指定時のみ）──────────
    if flow_check_dir:
        from wom.engine.flow_check import compute_flow_check, write_flow_check_csv
        from wom.engine.report_start import configured_report_start
        _crs = configured_report_start(model_dir, list(sc_tree.week_labels))
        write_flow_check_csv(compute_flow_check(sc_tree, _fres_by_prod,
                                                report_start_index=_crs[0] if _crs else None),
                             flow_check_dir)

    # ── PPC（app.py _run_ppc_from_planning と同じ）─────────────────
    ppc_kpi = _run_ppc(sc_tree, weeks, model_dir, output_ppc_dir, verbose)

    # ── スナップショット組み立て ───────────────────────────────────
    if lot_flow_mode == LOT_FLOW_LEGACY:
        _forward = {"cap_hard_sealed": _cap_hard_sealed,
                    "cap_soft_violation_count": _cap_soft_viol}
    else:
        # RequestLetter_FlowCheck Part 2：identity は封印ではなく繰り延べ
        _forward = {"cap_hard_deferred_lots": _cap_def_lots,
                    "cap_hard_deferred_lot_weeks": _cap_def_weeks,
                    "cap_soft_violation_count": _cap_soft_viol}
    snap = {
        "case": os.path.basename(model_dir.rstrip("/\\")),
        "config": {"plugins": sorted(type(p).__name__ for p in active_plugins),
                   **({} if lot_flow_mode == LOT_FLOW_LEGACY else {"lot_flow_mode": lot_flow_mode})},
        "period": dict({"start": start, "weeks": n_weeks},
                       # only when the demand CSV skips weeks (they are planned with demand 0)
                       **({"filled_weeks": list(period.filled_weeks)} if period.filled_weeks else {})),
        "products": list(sc_tree.products),
        "forward": _forward,
        "backward": {"cap_soft_envelope_count": _bwd_soft_env},
        "ppc": ppc_kpi,
        "psi": _psi_signature(sc_tree, n_weeks),
    }
    if planning_state:
        # opt-in のみ。既定 False の返却（golden が依存する4キー）には一切触れない（C8）。
        snap["planning_state_extras"] = _planning_state_extras(
            sc_tree, n_weeks, _fres_all, _bres_all)
    return snap


def _run_ppc(sc_tree, weeks, model_dir, output_ppc_dir, verbose) -> dict:
    from wom.ppc.ppc_runner import run_ppc_from_psi
    data_dir = "data/ppc"
    use_node_name = False
    if os.path.exists(os.path.join(model_dir, "ppc_market_price.csv")):
        data_dir = model_dir
        use_node_name = True
    base_currency = "JPY"
    fx = os.path.join(data_dir, "ppc_fx_rate.csv")
    if os.path.exists(fx):
        try:
            vals = pd.read_csv(fx, dtype=str)["base_currency"].dropna().unique()
            if len(vals) == 1:
                base_currency = str(vals[0])
        except Exception:
            pass
    kpi = run_ppc_from_psi(
        sc_tree=sc_tree, weeks=list(sc_tree.week_labels) or weeks,
        data_dir=data_dir, output_dir=output_ppc_dir,
        base_currency=base_currency, verbose=verbose, use_node_name=use_node_name)
    # ppc_kpi_summary.json（唯一の真実源）を優先して読む
    js = os.path.join(output_ppc_dir, "ppc_kpi_summary.json")
    if os.path.exists(js):
        with open(js, encoding="utf-8") as f:
            k = json.load(f)
    else:
        k = kpi or {}
    return {
        "base_currency":  k.get("base_currency", base_currency),
        "total_lots":     int(k.get("total_lots", 0) or 0),
        "revenue_base":   round(float(k.get("total_revenue_base", 0) or 0), 2),
        "cost_base":      round(float(k.get("total_cost_base", 0) or 0), 2),
        "gross_profit_base": round(float(k.get("gross_profit_base", 0) or 0), 2),
        "gross_margin_pct":  round(float(k.get("gross_margin_pct", 0) or 0), 6),
        "tariff_base":    round(float(k.get("total_tariff_base", 0) or 0), 2),
        "trust_event_count": int(k.get("trust_event_count", 0) or 0),
    }


def _planning_state_extras(sc_tree, n_weeks, fres_all, bres_all) -> dict:
    """Phase 7（opt-in・`planning_state=True` のときだけ呼ばれる）: `realized` の
    7項目のうち `_psi_signature()`（golden 依存・変更禁止）に無い週リストを作る。
    `wom.planning_state.PEAK_INVENTORY_MULTIPLE` を「在庫が安全在庫の何倍を
    超えたら記録するか」の閾値として使う（既定 2.0）。
    """
    from wom.planning_state import PEAK_INVENTORY_MULTIPLE

    # node_id -> (product, node_name)。cap_hard_events/cap_soft_violations は
    # node.node_id を記録するが、capacity_series 等の他の extras はすべて
    # node_name をキーにしている——node_id は node_name とは別物（例:
    # "IN:mom:Bottling_Noda:Soy_Sauce" vs "Bottling_Noda"）。Phase 8-3c 追補で
    # 発見（cap_hard "超過" vs "sealed" バグの根因）。sc_tree.iter_all_nodes()
    # を1回先に回して対応表を作り、文字列パースには頼らない。
    node_id_to_name: dict = {}
    for _prod in sc_tree.products:
        for _nd in sc_tree.iter_all_nodes(_prod):
            node_id_to_name[_nd.node_id] = (_prod, _nd.node_name)

    cap_hard_weeks: set = set()
    cap_soft_weeks: set = set()
    bwd_env_weeks: set = set()
    capacity_events: dict = {}   # {product: {node_name: {"cap_hard_weeks":[...], "cap_soft_weeks":[...]}}}
    for _fres in fres_all:
        for _node_id, wk, _cnt in getattr(_fres, "cap_hard_events", []) or []:
            cap_hard_weeks.add(wk)
            _prod_name = node_id_to_name.get(_node_id)
            if _prod_name:
                _prod, _name = _prod_name
                capacity_events.setdefault(_prod, {}).setdefault(
                    _name, {"cap_hard_weeks": [], "cap_soft_weeks": []}
                )["cap_hard_weeks"].append(wk)
        for _node_id, wk, _over in getattr(_fres, "cap_soft_violations", []) or []:
            cap_soft_weeks.add(wk)
            _prod_name = node_id_to_name.get(_node_id)
            if _prod_name:
                _prod, _name = _prod_name
                capacity_events.setdefault(_prod, {}).setdefault(
                    _name, {"cap_hard_weeks": [], "cap_soft_weeks": []}
                )["cap_soft_weeks"].append(wk)
    for _bres in bres_all:
        for _node_id, wk, _over in getattr(_bres, "cap_soft_envelope_violations", []) or []:
            bwd_env_weeks.add(wk)

    inventory_peak_weeks: dict = {}
    leaf_out_S: dict = {}
    leaf_out_CO: dict = {}
    leaf_out_S_weekly: dict = {}     # Phase 7a・A2.4: fx_effective の出荷数量加重に使う
    capacity_series: dict = {}       # Phase 8-3c・N4: S3 の「処理能力 vs 負荷」図用
    for prod in sc_tree.products:
        peaks_prod: dict = {}
        s_prod: dict = {}
        co_prod: dict = {}
        s_weekly_prod: dict = {}
        cap_series_prod: dict = {}
        for nd in sc_tree.iter_all_nodes(prod):
            sup = nd.psi4supply
            i_series = [len(sup[w][I]) for w in range(n_weeks)]
            s_series = [len(sup[w][S]) for w in range(n_weeks)]
            avg_s = (sum(s_series) / n_weeks) if n_weeks else 0.0
            ss_wks = getattr(nd, "ss_wks", 0) or 0
            threshold = PEAK_INVENTORY_MULTIPLE * avg_s * ss_wks
            labels = nd.week_labels if getattr(nd, "week_labels", None) else None
            if threshold > 0:
                over_weeks = [(labels[w] if labels else str(w))
                             for w, v in enumerate(i_series) if v > threshold]
                if over_weeks:
                    peaks_prod[nd.node_name] = over_weeks
            if nd.node_type == "leaf_out":
                co_series = [len(sup[w][CO]) for w in range(n_weeks)]
                s_prod[nd.node_name] = sum(s_series)
                co_prod[nd.node_name] = sum(co_series)
                s_weekly_prod[nd.node_name] = {
                    (labels[w] if labels else str(w)): s_series[w] for w in range(n_weeks)
                }
            # Phase 8-3c・N4: 能力を持つノードだけ（cap_hard/cap_soft が全週ゼロなら
            # 入れない——S1 の is_unallocated と同じ規律で、意味の無い行を出さない）。
            # Explicit Closure v1r5m0 §4.7: cap_hard stays the raw physical
            # ceiling (a closure does not rewrite it); cap_soft is the planned
            # operating capacity (closed week = 0, unset -> 0 as before).
            # RequestLetter_CapacityZeroBlank: None = not set (shown as 0 in
            # this display series, as before); zero capacity is 0 too, but the
            # node still counts as a node with capacity.
            _ch_raw = [nd.cap_hard(w) for w in range(n_weeks)]
            _cs_raw = [nd.planned_capacity(w) for w in range(n_weeks)]
            cap_hard_series = [(v if v is not None else 0.0) for v in _ch_raw]
            cap_soft_series = [(v if v is not None else 0.0) for v in _cs_raw]
            closed_idx = [w for w in range(n_weeks) if not nd.is_open(w)]
            if any(v is not None for v in _ch_raw) or any(v > 0 for v in cap_soft_series):
                # Phase 8-3c-4・X1: cap_hard と比べるべき系列を「1本だけ」出し、
                # それが何かを series_kind で宣言する（画面に選ばせない）。
                # push ノード（decoupling 点）の P は入庫であって生産ではない
                # （ForwardPlanner は push ノードの P を能力で制限しない）——処理能力と
                # 比べるべきは処理量＝実際に出荷できた量: S から「物が無くて出せなかった
                # 分」（_push_shortfall）を引いたもの。それ以外のノードは、Step 0a が
                # 実際に P を cap_hard と比べているので P（生産量）。超過分は legacy
                # では封印（CO へ）、identity では翌週の P へ繰り延べ（決定記録 D4）。
                # plan_mode の判定は、系列の選択としてはここ1箇所だけ。
                # `shortfall` は「物が無くて通せなかった量」（能力で縛られたのでは
                # ない）。実出荷が低い週の原因を、図の上で「能力」と取り違えない
                # ための情報（push ノードのみ。他は 0）。`nd._push_shortfall` は
                # ForwardPlanner が push ノードに置く private 属性の直読みで、
                # 論点3 で forward_planner.py を触るときに公開属性へ格上げする。
                if nd.plan_mode == "push":
                    pushed_short = getattr(nd, "_push_shortfall", None) or {}
                    shortfall = [pushed_short.get(w, 0) for w in range(n_weeks)]
                    # RequestLetter_LotIdentityFlow C2: the processed quantity is
                    # the ACTUAL shipment count (ForwardPlanner exposes it as
                    # nd._actual_ship). In legacy it equals len(S) - shortfall;
                    # in identity S - shortfall is not the shipment (CO also ships).
                    actual_ship = getattr(nd, "_actual_ship", None)
                    if actual_ship is not None:
                        series = [len(actual_ship.get(w, [])) for w in range(n_weeks)]
                    else:
                        series = [len(sup[w][S]) - shortfall[w] for w in range(n_weeks)]
                    series_kind = "throughput"
                    series_label_ja = "処理量（lot）"
                else:
                    shortfall = [0] * n_weeks
                    series = [len(sup[w][P]) for w in range(n_weeks)]
                    series_kind = "production"
                    series_label_ja = "生産量（lot）"
                cap_series_prod[nd.node_name] = {
                    "week_labels": list(labels) if labels else [str(w) for w in range(n_weeks)],
                    "series": series,
                    "series_kind": series_kind,
                    "series_label_ja": series_label_ja,   # 語はここにだけ置く（K1）
                    "shortfall": shortfall,
                    "cap_hard": cap_hard_series,
                    "cap_soft": cap_soft_series,
                    # closed weeks (op_shifts==0) as week labels; drawn as a
                    # grey background only (§4.7).
                    "closed_weeks": [(labels[w] if labels else str(w)) for w in closed_idx],
                }
        if peaks_prod:
            inventory_peak_weeks[prod] = peaks_prod
        leaf_out_S[prod] = s_prod
        leaf_out_CO[prod] = co_prod
        leaf_out_S_weekly[prod] = s_weekly_prod
        if cap_series_prod:
            capacity_series[prod] = cap_series_prod

    for _by_node in capacity_events.values():
        for _rec in _by_node.values():
            _rec["cap_hard_weeks"] = sorted(set(_rec["cap_hard_weeks"]))
            _rec["cap_soft_weeks"] = sorted(set(_rec["cap_soft_weeks"]))

    return {
        "cap_hard_violation_weeks": sorted(cap_hard_weeks),
        "cap_soft_violation_weeks": sorted(cap_soft_weeks),
        "backward_envelope_weeks": sorted(bwd_env_weeks),
        "inventory_peak_weeks": inventory_peak_weeks,
        "leaf_out_S": leaf_out_S,
        "leaf_out_CO": leaf_out_CO,
        "leaf_out_S_weekly": leaf_out_S_weekly,
        "capacity_series": capacity_series,   # {product: {node_name: {...}}}（Phase 8-3c・N4）
        "capacity_events": capacity_events,   # {product: {node_name: {cap_hard_weeks, cap_soft_weeks}}}（追補）
    }


def _psi_signature(sc_tree, n_weeks) -> dict:
    """各ノードの psi4supply の P/S/I/CO を集計＋週次系列ハッシュ（timing ドリフト検知）。"""
    out = {}
    for prod in sc_tree.products:
        pnodes = {}
        for nd in sc_tree.iter_all_nodes(prod):
            sup = nd.psi4supply
            def series(bucket):
                return [len(sup[w][bucket]) for w in range(n_weeks)]
            p_s, s_s, i_s, co_s = series(P), series(S), series(I), series(CO)
            h = hashlib.md5(
                json.dumps([p_s, s_s, i_s, co_s]).encode()).hexdigest()[:12]
            pnodes[nd.node_name] = {
                "P": sum(p_s), "S": sum(s_s),
                "I_sum": sum(i_s), "I_max": max(i_s) if i_s else 0,
                "CO": sum(co_s), "series_md5": h,
            }
        out[prod] = pnodes
    return out


# ──────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-dir", required=True, help="モデルフォルダ（sc_tree_master.csv 等）")
    ap.add_argument("--plugins", default="safe",
                    help="safe(既定)/all/none/クラス名 comma 区切り")
    ap.add_argument("--out", default="", help="スナップショット JSON 出力先（省略時 stdout）")
    ap.add_argument("--ppc-out", default="output/ppc", help="PPC 出力先")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--lot-flow-mode", default=None, choices=["identity", "legacy"],
                    help="Forward の方式（省略時：planning_config.csv の lot_flow_mode、無ければ identity）")
    ap.add_argument("--flow-check-out", default="output/flow_check",
                    help="Flow Check の表1・表2 の CSV の出力先の親フォルダ（<これ>/<モデル名>/ に書く）。"
                         "空文字で書き出さない")
    a = ap.parse_args(argv)

    fc_dir = (os.path.join(a.flow_check_out, os.path.basename(a.model_dir.rstrip("/\\")))
              if a.flow_check_out else None)
    snap = run(a.model_dir, plugins_spec=a.plugins,
               output_ppc_dir=a.ppc_out, verbose=not a.quiet,
               lot_flow_mode=a.lot_flow_mode, flow_check_dir=fc_dir)
    text = json.dumps(snap, ensure_ascii=False, indent=2, sort_keys=True)
    fw = snap["forward"]
    cap_txt = (f"cap_hard_sealed={fw['cap_hard_sealed']} " if "cap_hard_sealed" in fw else
               f"cap_hard_deferred={fw['cap_hard_deferred_lots']} lots/"
               f"{fw['cap_hard_deferred_lot_weeks']} lot-weeks ")
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[Headless] snapshot -> {a.out}  (GM={snap['ppc']['gross_margin_pct']*100:.1f}% "
              f"trust={snap['ppc']['trust_event_count']} "
              + cap_txt +
              f"cap_soft_viol={snap['forward']['cap_soft_violation_count']} "
              f"bwd_env={snap['backward']['cap_soft_envelope_count']})")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
