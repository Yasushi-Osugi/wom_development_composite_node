#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/sweep_flags.py
=====================
設定変化点スイープ・ツール（Request Letter: requests/request_impl_sweep_flags_tool.md）。

目的
----
GUI 経由の検証では「Apply Filters の押し忘れ」「Planning Config の再入力漏れ」
「プラグイン ON/OFF の記録漏れ」「複数設定を同時に変えて寄与が分離できない」
といった操作要因が混入する。本ツールは、ケースごとに **1つずつ設定を変えて**
`data/sample/<model>/` の CSV を一時的に書き換え、ヘッドレスで Planning + PPC を
実行し、結果を機械的に比較できる形で出力する。

守っていること（新規ファイルのみ追加。既存コードは変更しない）
----------------------------------------------------------------
- 保護対象コア6ファイル（backward_planner.py 等）はもちろん、
  `tools/run_headless_from_folder.py` / `wom/gui/` も一切変更しない。
  本ファイルは `run_headless_from_folder.py` の一部ヘルパー関数
  （`_detect_period` / `_build_week_labels` / `_select_plugins` / `_run_ppc`）を
  **import して再利用**する。ただし同モジュールの `run()` は内部で構築した
  `sc_tree`（plan_mode / is_decoupling / 週次系列を読むのに必要）を外に返さない
  ため、そこだけは同じ手順を本ファイル内に複製している
  （`_execute_pipeline()`。呼んでいる関数は run_headless_from_folder.py と
  完全に同一 — 新しいロジックではなく、同じ orchestration の写し）。
- `data/sample/` を恒久的に書き換えない。各ケースの実行前に対象ファイル
  （ops で触るファイル＋ warmup が触りうるファイル一式）を退避し、
  `try/finally` で必ず復元する（§4 安全要件）。
- 各ケースの PPC 出力は `output/sweep/<timestamp>/ppc_raw/<case>/` という
  ケース専用ディレクトリに書く（共有の `output/ppc/` には触れない）。
  これにより「前回ケースの出力が残ったまま読まれる」事故を構造的に防止する
  （§4.2 で懸念されている取り違えを、退避/クリアではなく分離で解決）。

使い方
------
    python -m tools.sweep_flags --spec tools/sweep_specs/apparel_s1.yaml
    python -m tools.sweep_flags --spec tools/sweep_specs/apparel_s1.yaml --cases base,B_flag1
    python -m tools.sweep_flags --model data/sample/apparel-us-2026 --spec tools/sweep_specs/apparel_s1.yaml

スペックファイル（YAML推奨。PyYAML が無い環境では .json でも可）:
    model: data/sample/apparel-us-2026       # --model で上書き可
    target_sku: Apparel_Outsourced_S1        # --sku で上書き可
    target_nodes: [Fabric_CN, Factory_Import_CN, SP_Apparel_Outsourced, DC_Import_Buffer]
    plugins: safe                            # --plugins で上書き可（safe/all/none/クラス名comma区切り）
    cases:
      - name: base
        ops: []
      - name: A_no_holiday
        ops:
          - op: remove_file
            file: holiday_calendar.csv
      - name: B_flag1
        ops:
          - op: set_cell
            file: sc_tree_master.csv
            match: {node_name: Factory_Import_CN, product_name: Apparel_Outsourced_S1}
            set:   {buffering_stock_flag: "1"}
      - name: C_flag1_push4
        ops:
          - op: set_cell
            file: sc_tree_master.csv
            match: {node_name: Factory_Import_CN, product_name: Apparel_Outsourced_S1}
            set:   {buffering_stock_flag: "1"}
          - op: write_file
            file: push_config.csv
            content: |
              sku_id,node_id,push_qty_per_week,buffer_lots,mode_only,mom_ref_node_id,pre_build_qty_per_week,pre_build_end_week,push_lead_time_weeks,push_eol_week
              Apparel_Outsourced_S1,Factory_Import_CN,0,0,False,,0,,4,

サポートする ops:
    set_cell    : CSV の行を match で絞り込み、set の列を上書きする（0件マッチはエラー、
                  allow_zero_match: true で許容可）
    write_file  : ファイルを作成/上書き（無ければ新規作成 = 「有」への切替に使える）
    remove_file : ファイルを退避（存在すれば削除 = 「無」への切替に使える。既に無ければ no-op）

出力（output/sweep/<timestamp>/ 配下）:
    summary.csv          — 全ケース横並び（item, <case1>, <case2>, ..., differs）。
                            differs=Y の行を先頭に、続けて differs=N の行（目視比較しやすい向き）
    detail_<case>.json   — ケースごとの詳細（週次系列 P/S/I/CO を含む）
    console_<case>.log   — ケースごとの標準出力（[warmup] / [AutoDetect] / [PushPull] /
                            [HolidayCalendar] / [PPC Export] 等をそのまま記録）
    ppc_raw/<case>/      — そのケースの生 PPC 出力一式（ppc_kpi_summary.json 等）
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import csv
import hashlib
import json
import os
import subprocess
import sys
import time

import pandas as pd

# --- PSI バケット定数。plan_node に無ければ既定値（run_headless_from_folder.py と同じ流儀）---
try:
    from wom.model.plan_node import S, CO, I, P            # type: ignore
except Exception:
    S, CO, I, P = 0, 1, 2, 3

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# CSV のうち、materialize_warmup（Phase 2, opt-in）が触りうるものを含め、
# ケースの ops に関わらず常に退避/復元の対象にしておくファイル一式。
BASE_GUARD_FILES = [
    "sc_tree_master.csv",
    "push_config.csv",
    "holiday_calendar.csv",
    "demand_forecast.csv",
    "capacity_plan.csv",
    "operating_calendar.csv",
    "planning_config.csv",
]


# ══════════════════════════════════════════════════════════════════════
# スペック読み込み
# ══════════════════════════════════════════════════════════════════════
def load_spec(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    ext = os.path.splitext(path)[1].lower()
    if ext in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise SystemExit(
                "PyYAML が見つかりません。`pip install pyyaml` するか、"
                "スペックを .json で書いてください。"
            ) from exc
        return yaml.safe_load(text)
    if ext == ".json":
        return json.loads(text)
    raise SystemExit(f"未対応のスペック拡張子です: {ext}（.yaml/.yml/.json のいずれかを使ってください）")


# ══════════════════════════════════════════════════════════════════════
# 安全要件（§4）: ファイルの退避・復元 / stdout の二重書き
# ══════════════════════════════════════════════════════════════════════
@contextlib.contextmanager
def guarded_files(model_dir: str, filenames):
    """`filenames`（model_dir 相対）の内容をバイト単位で退避し、ブロック終了時
    （例外発生時も含め）に必ず元へ復元する。存在しなかったファイルは削除して戻す。
    """
    filenames = sorted(set(filenames))
    backups = {}
    for fn in filenames:
        path = os.path.join(model_dir, fn)
        if os.path.exists(path):
            with open(path, "rb") as f:
                backups[fn] = f.read()
        else:
            backups[fn] = None
    try:
        yield
    finally:
        for fn in filenames:
            path = os.path.join(model_dir, fn)
            original = backups[fn]
            if original is None:
                if os.path.exists(path):
                    os.remove(path)
            else:
                with open(path, "wb") as f:
                    f.write(original)


class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            st.write(s)
        return len(s)

    def flush(self):
        for st in self._streams:
            st.flush()


@contextlib.contextmanager
def tee_stdout(log_path: str):
    with open(log_path, "w", encoding="utf-8") as f:
        old = sys.stdout
        sys.stdout = _Tee(old, f)
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stdout = old


# ══════════════════════════════════════════════════════════════════════
# ケース定義の適用（ops）
# ══════════════════════════════════════════════════════════════════════
def guard_files_for_case(ops) -> set:
    files = set(BASE_GUARD_FILES)
    for op in ops:
        fn = op.get("file")
        if fn:
            files.add(fn)
    return files


def apply_ops(model_dir: str, ops) -> None:
    for op in ops:
        kind = op.get("op")
        if kind == "set_cell":
            _op_set_cell(model_dir, op)
        elif kind == "write_file":
            _op_write_file(model_dir, op)
        elif kind == "remove_file":
            _op_remove_file(model_dir, op)
        else:
            raise ValueError(f"未知の op です: {kind!r}")


def _op_set_cell(model_dir: str, op: dict) -> None:
    fname = op["file"]
    match = op.get("match") or {}
    set_ = op.get("set") or {}
    path = os.path.join(model_dir, fname)
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    n_matched = 0
    for row in rows:
        if all(str(row.get(k, "")) == str(v) for k, v in match.items()):
            for k, v in set_.items():
                row[k] = str(v)
            n_matched += 1

    if n_matched == 0 and not op.get("allow_zero_match"):
        raise ValueError(
            f"set_cell({fname}): match={match!r} に一致する行が0件でした。"
            f" スペックのキー/値を確認してください"
            f"（意図的に0件を許容するなら allow_zero_match: true を追加）。"
        )

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[sweep] set_cell {fname}: matched={n_matched} match={match} set={set_}")


def _op_write_file(model_dir: str, op: dict) -> None:
    fname = op["file"]
    content = op.get("content", "")
    path = os.path.join(model_dir, fname)
    if content and not content.endswith("\n"):
        content += "\n"
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print(f"[sweep] write_file {fname}: {len(content)} bytes")


def _op_remove_file(model_dir: str, op: dict) -> None:
    fname = op["file"]
    path = os.path.join(model_dir, fname)
    if os.path.exists(path):
        os.remove(path)
        print(f"[sweep] remove_file {fname}: removed")
    else:
        print(f"[sweep] remove_file {fname}: already absent (no-op)")


# ══════════════════════════════════════════════════════════════════════
# Planning + PPC パイプライン
# （run_headless_from_folder.py の run() と同一の関数を同一の順序で呼ぶ。
#   sc_tree を外へ返す必要があるためオーケストレーション部分のみ複製している。
#   期間検出・プラグイン選択・PPC呼び出しヘルパーはそのまま import して再利用）
# ══════════════════════════════════════════════════════════════════════
def _execute_pipeline(model_dir: str, plugins_spec: str, ppc_out_dir: str,
                       target_sku: str, target_node_names) -> tuple:
    from wom.model.lot_generator import assign_demand_lots_from_dict
    from wom.engine.lane_assignment import LaneTable
    from wom.engine.hook_bus import (
        HookBus, HOOK_PRE_PLAN, HOOK_POST_BACKWARD,
        HOOK_POST_COPY, HOOK_POST_FORWARD, HOOK_POST_PLAN)
    from wom.engine.sc_tree_builder import build_sc_tree_from_master
    from wom.engine.backward_planner import BackwardPlanner
    from wom.engine.plan_copy import copy_demand_to_supply
    from wom.engine.forward_planner import ForwardPlanner
    from wom.engine.capacity_sealer import load_capacity_dataframe, load_operating_calendar
    from wom.engine.warmup import materialize_warmup, format_summary, read_cpu_size

    # run_headless_from_folder.py のヘルパーを再利用（複製しない）
    sys.path.insert(0, _REPO_ROOT) if _REPO_ROOT not in sys.path else None
    from tools.run_headless_from_folder import (   # noqa: E402
        _detect_period, _build_week_labels, _select_plugins, _run_ppc,
    )

    def _p(name):
        return os.path.join(model_dir, name)

    result: dict = {}

    # ── warm-up materialize（Phase 2, opt-in; run_headless_from_folder と同じ呼び出し）
    wsum = materialize_warmup(model_dir)
    print(format_summary(wsum))
    result["warmup"] = {
        "warmup_lt":        wsum.get("warmup_lt"),
        "planning_start":   wsum.get("planning_start"),
        "effective_start":  wsum.get("effective_start"),
        "changed":          bool(wsum.get("changed")),
        "skipped":          bool(wsum.get("skipped")),
    }

    # ── 期間の自動検出（GUI の [AutoDetect] と同じタグで記録）───────────
    dem_path = _p("demand_forecast.csv")
    start, n_weeks = _detect_period(dem_path)
    weeks = _build_week_labels(start, n_weeks)
    print(f"[AutoDetect] period: {start}  x  {n_weeks} weeks")
    result["period"] = {"start": start, "n_weeks": n_weeks}
    result["warmup_confirmed_in_period"] = (start == result["warmup"]["effective_start"])

    # ── SCTree 構築 ─────────────────────────────────────────────────
    sc_tree_df = pd.read_csv(_p("sc_tree_master.csv"))
    sc_tree = build_sc_tree_from_master(sc_tree_df, weeks)
    # Request Letter A (request_letter_a_cpu_size_to_plan.md) discrepancy,
    # resolved here and flagged for owner review: sc_tree.cpu_size is read
    # from planning_config.csv and used by the KPI/display conversion layer
    # ONLY. It is deliberately NOT passed to assign_demand_lots_from_dict()
    # below (which stays cpu_size=1) -- doing so would make ceil(qty/cpu_size)
    # change the LOT COUNT whenever cpu_size != 1, contradicting Letter A
    # section 4.2's explicit requirement that lot count is unchanged when
    # cpu_size goes 1 -> 12.
    sc_tree.cpu_size = read_cpu_size(model_dir)
    print(f"[Sweep] products: {list(sc_tree.products)}")

    # ── HookBus + プラグイン ────────────────────────────────────────
    bus = HookBus()
    cfg = {"n_weeks": n_weeks, "start_week": start,
           "cap_path": _p("capacity_plan.csv"),
           "holiday_cal_path": _p("holiday_calendar.csv")}
    active_plugins, harvest_plugin = _select_plugins(plugins_spec)
    for pl in active_plugins:
        pl.register(bus)
    print(f"[Sweep] plugins: {[type(p).__name__ for p in active_plugins]}")
    hol_plugin = next((p for p in active_plugins
                        if type(p).__name__ == "HolidayCalendarPlugin"), None)

    # ── 需要 → ロット ───────────────────────────────────────────────
    demand_dict = {}
    dem_df = pd.read_csv(dem_path)
    if {"sku_id", "region", "week", "quantity"}.issubset(dem_df.columns):
        for _, r in dem_df.iterrows():
            k = (str(r["sku_id"]), str(r["region"]), str(r["week"]))
            demand_dict[k] = demand_dict.get(k, 0) + int(r["quantity"])
    assign_demand_lots_from_dict(sc_tree, demand_dict, cpu_size=1)

    # ── 能力（cap_hard [+ cap_soft]）────────────────────────────────
    cap_path = _p("capacity_plan.csv")
    if os.path.exists(cap_path):
        try:
            load_capacity_dataframe(sc_tree, pd.read_csv(cap_path), weeks)
        except Exception as exc:
            print(f"[Sweep] capacity load failed: {exc}")

    # ── 操業カレンダー（Phase 2, opt-in）────────────────────────────
    opcal_path = _p("operating_calendar.csv")
    if os.path.exists(opcal_path):
        try:
            load_operating_calendar(sc_tree, pd.read_csv(opcal_path), weeks)
        except Exception as exc:
            print(f"[Sweep] operating calendar load failed: {exc}")

    # ── Lane / Push ─────────────────────────────────────────────────
    lane_path = _p("lane_assignment.csv")
    lane_table = (LaneTable.from_csv(lane_path)
                  if os.path.exists(lane_path) else LaneTable.empty())
    push_path = _p("push_config.csv")

    # ── Planning pipeline（run_headless_from_folder.run() と同順序）──
    bus.fire(HOOK_PRE_PLAN, sc_tree=sc_tree, weeks=weeks, config=cfg)

    if hol_plugin is None:
        result["holiday_calendar"] = {"active": False, "reason": "plugin not in spec",
                                       "rules_loaded": None}
    elif not os.path.exists(cfg["holiday_cal_path"]):
        result["holiday_calendar"] = {"active": False, "reason": "file absent",
                                       "rules_loaded": None}
        print("[HolidayCalendar] (sweep observation) file absent -> inactive")
    else:
        hol_rules = list(getattr(hol_plugin, "_rules", []) or [])
        result["holiday_calendar"] = {"active": bool(hol_rules), "reason": None,
                                       "rules_loaded": len(hol_rules)}

    cap_hard_sealed = 0
    cap_soft_viol = 0
    bwd_soft_env = 0
    push_pull_status = {"status": "not_run", "detail": None}

    for prod_nm in sc_tree.products:
        bres = BackwardPlanner(sc_tree, lane_table=lane_table, config=cfg).run(prod_nm)
        bwd_soft_env += len(getattr(bres, "cap_soft_envelope_violations", []) or [])
        bus.fire(HOOK_POST_BACKWARD, sc_tree=sc_tree, prod_nm=prod_nm, weeks=weeks, config=cfg)
        copy_demand_to_supply(sc_tree, prod_nm)
        bus.fire(HOOK_POST_COPY, sc_tree=sc_tree, prod_nm=prod_nm, weeks=weeks, config=cfg)

        # PUSH/PULL（run_headless_from_folder.py と同一処理。[PushPull] ログのみ追加）
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
                print(f"[PushPull] Applying push config for {prod_nm}: {cfgs[prod_nm]}")
                if prod_nm == target_sku:
                    push_pull_status = {"status": "applied", "detail": repr(cfgs[prod_nm])}
            else:
                print(f"[PushPull] push_config.csv loaded but no rows matched sku_id={prod_nm}")
                if prod_nm == target_sku:
                    push_pull_status = {"status": "no_rows_matched", "detail": None}
        else:
            if prod_nm == target_sku:
                push_pull_status = {"status": "file_not_found", "detail": None}

        opening_inv = getattr(harvest_plugin, "opening_inv", {}) if harvest_plugin else {}
        fres = ForwardPlanner(sc_tree, opening_inv=opening_inv).run(prod_nm)
        cap_hard_sealed += int(getattr(fres, "cap_hard_sealed", 0) or 0)
        cap_soft_viol += len(getattr(fres, "cap_soft_violations", []) or [])
        bus.fire(HOOK_POST_FORWARD, sc_tree=sc_tree, prod_nm=prod_nm, weeks=weeks, config=cfg)
    bus.fire(HOOK_POST_PLAN, sc_tree=sc_tree, weeks=weeks, config=cfg)

    result["forward"] = {"cap_hard_sealed": cap_hard_sealed,
                          "cap_soft_violation_count": cap_soft_viol}
    result["backward"] = {"cap_soft_envelope_count": bwd_soft_env}
    result["push_pull"] = push_pull_status
    result["config"] = {"plugins": sorted(type(p).__name__ for p in active_plugins)}

    # ── PPC（run_headless_from_folder.py の _run_ppc をそのまま呼ぶ）──
    result["ppc_all"] = _run_ppc(sc_tree, weeks, model_dir, ppc_out_dir, verbose=True)

    # ── sc_tree レベルの追加観測（run() には無い項目）──────────────
    result["psi"] = _extract_target_psi(sc_tree, target_sku, target_node_names, weeks)
    result["ppc_sku"] = _extract_sku_ppc(ppc_out_dir, target_sku)

    return result, sc_tree


def _compress_weeks(weeks, counts, head: int = 4, tail: int = 4) -> str:
    nz = [w for w, c in zip(weeks, counts) if c]
    n = len(nz)
    if n == 0:
        return "(none)"
    if n <= head + tail:
        return f"n={n}: " + ",".join(nz)
    return f"n={n}: " + ",".join(nz[:head]) + ",...," + ",".join(nz[-tail:])


def _extract_target_psi(sc_tree, target_sku: str, target_node_names, weeks) -> dict:
    out = {}
    found = set()
    for nd in sc_tree.iter_all_nodes(target_sku):
        if nd.node_name not in target_node_names:
            continue
        found.add(nd.node_name)
        sup = nd.psi4supply
        n = len(weeks)

        def series(bucket):
            return [len(sup[w][bucket]) for w in range(n)]

        p_s, s_s, i_s, co_s = series(P), series(S), series(I), series(CO)
        h = hashlib.md5(json.dumps([p_s, s_s, i_s, co_s]).encode()).hexdigest()[:12]
        out[nd.node_name] = {
            "plan_mode":         nd.plan_mode,
            "is_decoupling":     bool(nd.is_decoupling),
            "P_sum":             sum(p_s),
            "S_sum":             sum(s_s),
            "I_sum":             sum(i_s),
            "I_max":             max(i_s) if i_s else 0,
            "CO_sum":            sum(co_s),
            "CO_max":            max(co_s) if co_s else 0,
            "CO_last":           co_s[-1] if co_s else 0,
            "series_md5":        h,
            "P_nonzero_weeks":   _compress_weeks(weeks, p_s),
            "S_nonzero_weeks":   _compress_weeks(weeks, s_s),
            "I_nonzero_weeks":   _compress_weeks(weeks, i_s),
            "CO_nonzero_weeks":  _compress_weeks(weeks, co_s),
            "series":            {"P": p_s, "S": s_s, "I": i_s, "CO": co_s},
        }
    for name in target_node_names:
        if name not in found:
            out[name] = {"error": f"node {name!r} not found under product {target_sku!r}"}
    return out


def _extract_sku_ppc(ppc_out_dir: str, target_sku: str) -> dict:
    """`ppc_node_pl_summary.csv` / `ppc_event_ledger.csv` / `ppc_lot_reconciliation.csv`
    を対象SKUで絞り込んで集計する（"全体" は ppc_all 側の kpi_summary.json 由来の値を使う）。
    """
    result = {
        "lots": 0, "revenue_base": 0.0, "cost_base": 0.0, "gross_profit_base": 0.0,
        "gross_margin_pct": 0.0, "tariff_base": 0.0,
        "tariff_event_count": 0, "tariff_event_sum": 0.0,
        "trust_event_count": 0, "trust_breakdown": {},
    }

    node_pl_path = os.path.join(ppc_out_dir, "ppc_node_pl_summary.csv")
    if os.path.exists(node_pl_path):
        df = pd.read_csv(node_pl_path)
        sub = df[df["product_id"] == target_sku]
        rev = float(sub["revenue_base"].sum())
        cost = float(sub["cost_base"].sum())
        result["revenue_base"] = round(rev, 2)
        result["cost_base"] = round(cost, 2)
        result["tariff_base"] = round(float(sub["tariff_base"].sum()), 2)
        gp = rev - cost
        result["gross_profit_base"] = round(gp, 2)
        result["gross_margin_pct"] = round(gp / rev, 6) if rev else 0.0

    ledger_path = os.path.join(ppc_out_dir, "ppc_event_ledger.csv")
    if os.path.exists(ledger_path):
        ev = pd.read_csv(ledger_path)
        ev_sku = ev[ev["product_id"] == target_sku]
        rev_ev = ev_sku[ev_sku["ppc_event_type"] == "market_revenue"]
        result["lots"] = int(rev_ev["lot_id"].nunique())
        tariff_ev = ev_sku[ev_sku["ppc_event_type"] == "tariff_cost"]
        result["tariff_event_count"] = int(len(tariff_ev))
        result["tariff_event_sum"] = round(float(tariff_ev["amount_base"].sum()), 2)

    recon_path = os.path.join(ppc_out_dir, "ppc_lot_reconciliation.csv")
    if os.path.exists(recon_path):
        rec = pd.read_csv(recon_path)
        if "product_id" in rec.columns:
            rec = rec[rec["product_id"] == target_sku]
        breakdown: dict = {}
        if "trust_events_fired" in rec.columns:
            for s in rec["trust_events_fired"].dropna():
                for t in str(s).split("|"):
                    t = t.strip()
                    if t:
                        breakdown[t] = breakdown.get(t, 0) + 1
        result["trust_breakdown"] = breakdown
        result["trust_event_count"] = sum(breakdown.values())

    return result


# ══════════════════════════════════════════════════════════════════════
# 1ケースの実行（退避 → ops適用 → pipeline → 復元、を1本にまとめる）
# ══════════════════════════════════════════════════════════════════════
def run_one_case(model_dir: str, case: dict, plugins_spec: str, target_sku: str,
                  target_node_names, sweep_out_dir: str) -> dict:
    name = case["name"]
    ops = case.get("ops", [])
    guard_set = guard_files_for_case(ops)
    console_log_path = os.path.join(sweep_out_dir, f"console_{name}.log")
    ppc_out_dir = os.path.join(sweep_out_dir, "ppc_raw", name)
    os.makedirs(ppc_out_dir, exist_ok=True)

    result = None
    error = None
    t0 = time.time()
    with guarded_files(model_dir, guard_set):
        with tee_stdout(console_log_path):
            print(f"===== sweep case: {name} =====")
            print(f"[sweep] guarded files: {sorted(guard_set)}")
            try:
                apply_ops(model_dir, ops)
                result, _sc_tree = _execute_pipeline(
                    model_dir, plugins_spec, ppc_out_dir, target_sku, target_node_names)
            except Exception as exc:  # noqa: BLE001 -- 1ケースの失敗で全体を止めない
                error = f"{type(exc).__name__}: {exc}"
                print(f"[sweep] CASE FAILED: {error}")
    elapsed = time.time() - t0

    if result is None:
        result = {}
    result["case"] = name
    result["elapsed_sec"] = round(elapsed, 2)
    result["error"] = error
    return result


# ══════════════════════════════════════════════════════════════════════
# summary.csv 組み立て
# ══════════════════════════════════════════════════════════════════════
def _strip_series(result: dict) -> dict:
    """summary.csv 用に、週次系列（detail_<case>.json 側にのみ残す）を取り除いたコピー。"""
    r = copy.deepcopy(result)
    for node_data in (r.get("psi") or {}).values():
        if isinstance(node_data, dict):
            node_data.pop("series", None)
    return r


def _flatten(prefix: str, obj, out: dict) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    else:
        out[prefix] = obj


def build_summary_rows(case_results):
    """戻り値: (case_names, rows)  rows = [(item, [values...], "Y"/"N"), ...]
    differs=Y の行を先頭に、その中/後はアイテム名でソート。
    """
    case_names = [r["case"] for r in case_results]
    flat_per_case = {}
    all_items = []
    seen = set()
    for r in case_results:
        flat: dict = {}
        _flatten("", {k: v for k, v in r.items() if k != "case"}, flat)
        flat_per_case[r["case"]] = flat
        for k in flat.keys():
            if k not in seen:
                seen.add(k)
                all_items.append(k)

    rows = []
    for item in all_items:
        vals = [flat_per_case[c].get(item, None) for c in case_names]
        str_vals = [v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for v in vals]
        differs = "Y" if len(set(str_vals)) > 1 else "N"
        rows.append((item, vals, differs))
    rows.sort(key=lambda t: (t[2] != "Y", t[0]))
    return case_names, rows


def write_summary_csv(path: str, case_names, rows) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item"] + case_names + ["differs"])
        for item, vals, differs in rows:
            out_vals = []
            for v in vals:
                if v is None:
                    out_vals.append("")
                elif isinstance(v, str):
                    out_vals.append(v)
                else:
                    out_vals.append(json.dumps(v, ensure_ascii=False))
            w.writerow([item] + out_vals + [differs])


def _report_git_status(model_dir: str) -> None:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", model_dir],
            cwd=_REPO_ROOT, capture_output=True, text=True, timeout=30,
        )
        print("[sweep] git status (対象モデルフォルダのみ):")
        print(out.stdout if out.stdout.strip() else "  (no changes)")
        if out.returncode != 0:
            print(f"[sweep] git status stderr: {out.stderr}")
    except Exception as exc:  # noqa: BLE001
        print(f"[sweep] git status check skipped ({exc})")


# ══════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="ケース定義ファイル（.yaml/.yml/.json）")
    ap.add_argument("--model", default="", help="モデルフォルダ（spec の 'model' を上書き）")
    ap.add_argument("--sku", default="", help="対象SKU（spec の 'target_sku' を上書き）")
    ap.add_argument("--plugins", default="", help="safe/all/none/クラス名comma区切り（spec の 'plugins' を上書き）")
    ap.add_argument("--cases", default="", help="実行するケース名のcomma区切り（省略時は spec の全ケース）")
    ap.add_argument("--out-dir", default="output/sweep", help="出力ベースディレクトリ")
    a = ap.parse_args(argv)

    spec = load_spec(a.spec)
    model_dir = a.model or spec.get("model")
    if not model_dir:
        raise SystemExit("--model か spec の 'model' キーのいずれかでモデルフォルダを指定してください")
    target_sku = a.sku or spec.get("target_sku")
    if not target_sku:
        raise SystemExit("--sku か spec の 'target_sku' キーのいずれかで対象SKUを指定してください")
    target_nodes_spec = spec.get("target_nodes") or []
    target_node_names = [n["name"] if isinstance(n, dict) else str(n) for n in target_nodes_spec]
    plugins_spec = a.plugins or spec.get("plugins", "safe")

    all_cases = spec.get("cases") or []
    cases = all_cases
    if a.cases:
        wanted = {s.strip() for s in a.cases.split(",") if s.strip()}
        cases = [c for c in all_cases if c["name"] in wanted]
        missing = wanted - {c["name"] for c in cases}
        if missing:
            raise SystemExit(f"spec に無いケース名が指定されました: {sorted(missing)}")
    if not cases:
        raise SystemExit("実行対象ケースがありません（spec の 'cases' を確認してください）")

    ts = time.strftime("%Y%m%d_%H%M%S")
    sweep_out_dir = os.path.join(a.out_dir, ts)
    os.makedirs(sweep_out_dir, exist_ok=True)

    print(f"[sweep] model       = {model_dir}")
    print(f"[sweep] spec        = {a.spec}")
    print(f"[sweep] target_sku  = {target_sku}")
    print(f"[sweep] target_nodes= {target_node_names}")
    print(f"[sweep] plugins     = {plugins_spec}")
    print(f"[sweep] cases       = {[c['name'] for c in cases]}")
    print(f"[sweep] out_dir     = {sweep_out_dir}")

    case_results = []
    for case in cases:
        print(f"\n[sweep] ---- running case: {case['name']} ----")
        r = run_one_case(model_dir, case, plugins_spec, target_sku, target_node_names, sweep_out_dir)
        status = "OK" if not r.get("error") else f"FAILED ({r['error']})"
        print(f"[sweep] case {case['name']}: {status}  elapsed={r.get('elapsed_sec')}s")
        case_results.append(r)
        detail_path = os.path.join(sweep_out_dir, f"detail_{case['name']}.json")
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=2, sort_keys=True)

    summary_inputs = [_strip_series(r) for r in case_results]
    case_names, rows = build_summary_rows(summary_inputs)
    summary_path = os.path.join(sweep_out_dir, "summary.csv")
    write_summary_csv(summary_path, case_names, rows)

    n_diff = sum(1 for _, _, d in rows if d == "Y")
    print(f"\n[sweep] summary -> {summary_path}")
    print(f"[sweep] items: {len(rows)}  differing: {n_diff}  identical: {len(rows) - n_diff}")

    _report_git_status(model_dir)
    print(f"\n[sweep] done. outputs under: {sweep_out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
