# -*- coding: utf-8 -*-
"""
wom/cockpit/case_runner.py — 事業計画の案を実行し、2 案を並べる（画面に依存しない。Tk を import しない）
=====================================================================================================
RequestLetter_Cockpit_Stage3_Step1_CasesAndRunner §2.2、設計書 §4。

1 つの案の段（順に）：

    demand      投入の表から道具 1 で作った需要が、案の需要と同じかを確かめる（案のファイルは書かない）
    allocation  方針ありの案だけ：数量配分（tools.run_quantity_allocation）。案のモデルの写し
                （udp/work/<案>）で回し、配分後の需要を置いた写し（run/model_alloc）を作る
    plan_ppc    計画・PPC・Flow Check（tools.run_headless_from_folder）
    valuechain  Value Chain（tools.valuechain_run）
    shelf_life  製品の年齢（tools.shelf_life_check）
    check       突き合わせと結果の要点：Flow Check の表 2 ＝ 要求週別の供給、方針ありの案は金額の実行の
                出荷 ＝ 数量配分の結果（鍵 × 要求週）。実行の間に案の入力が変わっていないこと

プラグインはどの段も、案のモデルの recommended_plugins を明示して渡す。

既存の道具の呼び方：
- 道具 1（需要）・道具 2（並べる）は関数で呼ぶ（CSV を読み書きするだけで、止める理由を例外で返す）。
- 計画・数量配分・Value Chain・年齢の検査は子プロセスで呼ぶ（前回の手の手順と同じコマンド。
  計画のたびにプラグイン・木を作り直す道具なので、1 つのプロセスで続けて回したときの状態の持ち越しを
  避け、道具が出したメッセージをそのまま記録に残すため）。

既存の道具・エンジンのコードは変えない。
"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Callable, Dict, List, Optional, Tuple

from wom.cockpit import cases as C

REPO = C.REPO
PYTHON = sys.executable

STAGES_PLAIN = ["demand", "plan_ppc", "valuechain", "shelf_life", "check"]
STAGES_POLICY = ["demand", "allocation", "plan_ppc", "valuechain", "shelf_life", "check"]
STAGE_LABEL = {"demand": "需要", "allocation": "数量配分", "plan_ppc": "計画・PPC・Flow Check",
               "valuechain": "Value Chain", "shelf_life": "年齢の検査", "check": "突き合わせ"}

# exit codes of tools.run_quantity_allocation
EXIT_INCONSISTENT, EXIT_CONFLICT, EXIT_SHORT = 1, 3, 4


class StageStop(Exception):
    """A stage stopped. state: one of the cases.ST_* states; message: the tool's own words."""

    def __init__(self, state: str, message: str):
        self.state, self.message = state, message
        super().__init__(message)


# ── 道具の呼び出し（子プロセス。テストで差し替えられる） ───────────────────
def run_tool(module: str, args: List[str], log_path: str) -> Tuple[int, str]:
    """python -m <module> <args> in the repository; stdout+stderr go to log_path. (exit code, output)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    p = subprocess.run([PYTHON, "-m", module] + args, cwd=REPO, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"$ python -m {module} {' '.join(args)}\n{out}\n[exit {p.returncode}]\n")
    return p.returncode, out


def _tail(text: str, n: int = 40) -> str:
    lines = [l for l in (text or "").splitlines() if l.strip()]
    return "\n".join(lines[-n:])


def _rel(path: str, base: str) -> str:
    return os.path.relpath(path, base).replace("\\", "/")


def recommended_plugins(model_dir: str) -> str:
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from wom.plugins.selection import read_recommended_plugins
    names = read_recommended_plugins(model_dir)
    if not names:
        raise StageStop(C.ST_STOPPED, f"{model_dir}/planning_config.csv に recommended_plugins がありません。"
                        "直し方：planning_config.csv にプラグインの組を書く（黙って safe にしない）")
    return ",".join(names)


def _first_nonzero_week(demand_csv: str) -> Optional[str]:
    with open(demand_csv, encoding="utf-8-sig", newline="") as f:
        ws = [r["week"].strip() for r in csv.DictReader(f) if float(r["quantity"] or 0) != 0]
    return min(ws) if ws else None


def _hash_dir(d: str) -> Dict[str, str]:
    out = {}
    for root, _ds, fs in os.walk(d):
        for fn in fs:
            p = os.path.join(root, fn)
            out[os.path.relpath(p, d).replace("\\", "/")] = C._sha256_file(p)
    return out


# ── 段 ─────────────────────────────────────────────────────────────────
def _stage_demand(ctx) -> dict:
    mdir = ctx["model"]
    ep = os.path.join(mdir, C.ENTRY_PLAN)
    if not os.path.exists(ep):
        return {"note": "投入の表なし：モデルの需要をそのまま使う"}
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from tools.gen_demand_from_entry_plan import read_plan, week_range, generate, EntryPlanError
    ws = ctx["ws"]
    try:
        rows, _raw, ppath = read_plan(mdir)
        lines = generate(rows, week_range(ws["demand_period"]["start"], ws["demand_period"]["end"]), ppath)
    except EntryPlanError as e:
        raise StageStop(C.ST_STOPPED, f"道具 1：{e}")
    buf = io.StringIO()
    buf.write("sku_id,region,week,quantity\n")
    for s, g, w, q in lines:
        buf.write(f"{s},{g},{w},{q}\n")
    with open(os.path.join(mdir, C.DEMAND), "rb") as f:
        now = f.read()
    if now != buf.getvalue().encode("utf-8"):
        raise StageStop(C.ST_STOPPED, f"{mdir}/{C.DEMAND} が投入の表から道具 1 で作った需要と違います。"
                        "直し方：需要 CSV を直接書き換えず、投入の表を変える（cases.set_launch_week / "
                        "set_entry_plan が作り直す）")
    return {"total_lots": sum(q for *_x, q in lines), "rows": len(lines)}


def _stage_allocation(ctx) -> dict:
    cdir, pol = ctx["case_dir"], ctx["policy"]
    udp = os.path.join(cdir, "udp")
    if os.path.exists(udp):
        shutil.rmtree(udp)
    work = os.path.join(udp, "work", ctx["cid"])
    shutil.copytree(ctx["model"], work)
    args = ["--model-dir", work, "--allocation-file", os.path.join(cdir, pol["allocation_file"]),
            "--out-dir", os.path.join(udp, "planning_state"), "--plugins", ctx["plugins"],
            "--week-rule", pol["week_rule"], "--udp-out", os.path.join(udp, "out")]
    if pol.get("policy_file"):
        args += ["--policy-file", os.path.join(cdir, pol["policy_file"])]
    if pol.get("knowledge_file"):
        args += ["--knowledge-file", os.path.join(cdir, pol["knowledge_file"])]
    if pol.get("unallocated_note"):
        args += ["--unallocated-note", pol["unallocated_note"]]
    code, out = ctx["tool"]("tools.run_quantity_allocation", args, os.path.join(ctx["logs"], "allocation.log"))
    if code == EXIT_CONFLICT:
        raise StageStop(C.ST_CONFLICT, _tail(out))
    if code == EXIT_SHORT:
        raise StageStop(C.ST_SHORT, _tail(out))
    if code == EXIT_INCONSISTENT:
        raise StageStop(C.ST_INCONSISTENT, _tail(out))
    if code != 0:
        raise StageStop(C.ST_STOPPED, _tail(out))
    qdir = os.path.join(udp, "planning_state", ctx["cid"])
    qs = sorted(f for f in os.listdir(qdir) if f.startswith("Q") and f.endswith(".json"))
    if len(qs) != 1:
        raise StageStop(C.ST_STOPPED, f"{qdir}: 数量配分の記録（Q<nn>.json）が 1 つではありません：{qs}")
    q = C._read_json(os.path.join(qdir, qs[0]))
    gen = os.path.join(work, q["evidence"]["demand_csv"])
    udp_dir = os.path.join(udp, "out", f"{ctx['cid']}_{pol['week_rule']}")
    if not os.path.exists(os.path.join(udp_dir, "udp_result_by_request.csv")):
        raise StageStop(C.ST_STOPPED, f"{udp_dir}/udp_result_by_request.csv がありません")
    # money run model: the case model with the allocated demand as demand_forecast.csv
    mm = os.path.join(ctx["run"], "model_alloc")
    shutil.copytree(ctx["model"], mm)
    shutil.copyfile(gen, os.path.join(mm, C.DEMAND))
    a, b = _first_nonzero_week(os.path.join(ctx["model"], C.DEMAND)), _first_nonzero_week(gen)
    if a != b:
        raise StageStop(C.ST_STOPPED, f"配分後の需要の最初の非ゼロ需要週 {b} が元の需要 {a} と違います。"
                        "計画期間が動くので、金額の実行を止めた")
    ctx["money_model"] = mm
    ctx["udp_dir"] = udp_dir
    return {"allocation_id": q["allocation_id"], "totals": q["quantities"]["total"],
            "target_status": json.load(open(os.path.join(udp_dir, "udp_plan.json"), encoding="utf-8"))
            .get("target_status")}


def _stage_plan_ppc(ctx) -> dict:
    run, mm = ctx["run"], ctx["money_model"]
    args = ["--model-dir", mm, "--plugins", ctx["plugins"], "--out", os.path.join(run, "snapshot.json"),
            "--ppc-out", os.path.join(run, "ppc"), "--flow-check-out", os.path.join(run, "flow_check"), "--quiet"]
    code, out = ctx["tool"]("tools.run_headless_from_folder", args, os.path.join(ctx["logs"], "plan_ppc.log"))
    if code != 0:
        raise StageStop(C.ST_STOPPED, _tail(out))
    snap = C._read_json(os.path.join(run, "snapshot.json"))
    return {"period": snap.get("period"), "plugins": snap.get("config", {}).get("plugins")}


def _stage_valuechain(ctx) -> dict:
    args = ["--model-dir", ctx["money_model"], "--out", os.path.join(ctx["run"], "vc"), "--plugins", ctx["plugins"]]
    code, out = ctx["tool"]("tools.valuechain_run", args, os.path.join(ctx["logs"], "valuechain.log"))
    if code != 0:
        raise StageStop(C.ST_STOPPED, _tail(out))
    return {}


def _stage_shelf(ctx) -> dict:
    args = ["--model-dir", ctx["money_model"], "--max-age-weeks", str(ctx["ws"]["max_age_weeks"]),
            "--plugins", ctx["plugins"], "--out", os.path.join(ctx["run"], "shelf")]
    code, out = ctx["tool"]("tools.shelf_life_check", args, os.path.join(ctx["logs"], "shelf_life.log"))
    if code != 0:
        raise StageStop(C.ST_STOPPED, _tail(out))
    return {}


def _stage_check(ctx) -> dict:
    """Reconciliations (tool 2's functions) and the result summary. Reads outputs only."""
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from tools import compare_scenarios as CS
    mm = ctx["money_model"]
    if _hash_dir(mm) != ctx["money_model_hash"]:
        raise StageStop(C.ST_STOPPED, f"{mm} が実行の間に書き換わりました（道具がモデルに書いた）")
    try:
        r = CS.load_run(ctx["run"], mm)
        sup = CS.supply_by_request_week(r)
        CS.check_against_flow(sup, r, ctx["cid"])
        mb = CS.money_by_week_sku(r, ctx["cid"])          # checks Σ SKU == profit_r2_hq_wk per week
        unalloc = None
        if ctx.get("udp_dir"):
            udp = CS.load_udp(ctx["udp_dir"])
            at = CS.allocation_table(sup, udp, ctx["cid"])   # stops if shipments != allocation result
            g = at.groupby(["sku_id", "region"])["q3_unallocated"].sum()
            unalloc = {f"{s}:{g_}": int(v) for (s, g_), v in g.items()}
        p0, valuation, rs, re_ = CS.report_p0(r)
    except CS.CompareError as e:
        raise StageStop(C.ST_INCONSISTENT, f"突き合わせ：{e}")
    sup["delivered"] = sup["on_time"] + sup["early"] + sup["late"]
    by_sku = sup.groupby("sku_id")["delivered"].sum()
    bk = sup.groupby(["sku_id", "region"])["backlog_end"].sum()
    late = sup.groupby(["sku_id", "region"])["late"].sum()
    ppc = r["ppc"]
    summary = {
        "P0_report": p0, "report_period": [rs, re_], "valuation": valuation,
        "unvalued_consolidated_lines": int(mb.attrs.get("unvalued_consolidated_lines", 0)),
        "deliveries_by_sku": {k: int(v) for k, v in by_sku.items()},
        "demand_by_sku": {k: int(v) for k, v in sup.groupby("sku_id")["demand"].sum().items()},
        "backlog_end_by_key": {f"{s}:{g}": int(v) for (s, g), v in bk.items() if v},
        "late_by_key": {f"{s}:{g}": int(v) for (s, g), v in late.items() if v},
        "unallocated_by_key": None if unalloc is None else {k: v for k, v in unalloc.items() if v},
        "ppc_gross_profit_full": ppc.get("gross_profit_base"),
        "ppc_revenue_full": ppc.get("total_revenue_base"),
        "base_currency": ppc.get("base_currency"),
    }
    ctx["summary"] = summary
    return {"P0_report": p0}


STAGE_FUNCS = {"demand": _stage_demand, "allocation": _stage_allocation, "plan_ppc": _stage_plan_ppc,
               "valuechain": _stage_valuechain, "shelf_life": _stage_shelf, "check": _stage_check}


# ── 1 案の実行 ───────────────────────────────────────────────────────────
def run_case(ws_dir: str, cid: str, on_progress: Optional[Callable[[dict], None]] = None,
             tool: Callable = None, stage_funcs: Dict[str, Callable] = None) -> dict:
    """Run one case in the order of the design §4. Returns the run record (also in case.json).

    on_progress(event): event = {"case", "stage", "label", "index", "total", "event": "start"|"end"|"stop",
                                 "seconds", "message"} -- for the stage-3 screen.
    tool / stage_funcs: replace the subprocess call or whole stages (tests)."""
    ws = C.open_workspace(ws_dir)
    cdir = C.case_dir(ws_dir, cid)
    case = C.read_case(ws_dir, cid)
    if (case.get("run") or {}).get("state") == C.ST_RUNNING:
        raise C.CaseError(f"案 {cid} は実行中の記録があります（前の実行が途中で終わった可能性）。"
                          "直し方：case.json の run を確かめてから消す")
    funcs = dict(STAGE_FUNCS, **(stage_funcs or {}))
    pol = (case.get("inputs") or {}).get("policy")
    stages = STAGES_POLICY if pol else STAGES_PLAIN
    run_dir = os.path.join(cdir, "run")
    for d in (run_dir, os.path.join(cdir, "udp")):
        if os.path.exists(d):
            shutil.rmtree(d)
    os.makedirs(run_dir)
    hashes = C.input_hashes(ws_dir, cid)
    rec = {"state": C.ST_RUNNING, "started": C._now(), "finished": None, "stage": None,
           "stages": [], "input_hashes": hashes, "plugins": None, "reason": "", "message": "",
           "money_model": None, "udp_dir": None, "summary": None}
    case["run"] = rec
    C.write_case(ws_dir, cid, case)
    ctx = {"ws": ws, "cid": cid, "case_dir": cdir, "model": os.path.join(cdir, "model"), "run": run_dir,
           "logs": os.path.join(run_dir, "logs"), "policy": pol, "tool": tool or run_tool,
           "money_model": os.path.join(cdir, "model"), "udp_dir": None}

    def emit(**e):
        if on_progress:
            on_progress(dict(case=cid, total=len(stages), **e))

    try:
        ctx["plugins"] = recommended_plugins(ctx["model"])
        rec["plugins"] = ctx["plugins"]
        for i, st in enumerate(stages, start=1):
            if st == "plan_ppc":
                ctx["money_model_hash"] = _hash_dir(ctx["money_model"])
            rec["stage"] = st
            C.write_case(ws_dir, cid, dict(case, run=rec))
            emit(stage=st, label=STAGE_LABEL[st], index=i, event="start", seconds=None, message="")
            t0 = time.perf_counter()
            try:
                info = funcs[st](ctx) or {}
            except StageStop:
                raise
            except Exception as e:          # an unexpected error is a stop with the error text
                raise StageStop(C.ST_STOPPED, f"{type(e).__name__}: {e}")
            finally:
                sec = round(time.perf_counter() - t0, 2)
            rec["stages"].append({"stage": st, "seconds": sec, "info": info})
            emit(stage=st, label=STAGE_LABEL[st], index=i, event="end", seconds=sec, message="")
        if C.input_hashes(ws_dir, cid) != hashes:
            raise StageStop(C.ST_STOPPED, "実行の間に案の入力が変わりました。実行し直す")
        rec["state"] = C.ST_DONE
        rec["summary"] = ctx.get("summary")
    except StageStop as s:
        rec["state"], rec["reason"] = s.state, f"{STAGE_LABEL.get(rec['stage'], rec['stage'])} の段で止まった"
        rec["message"] = s.message
        rec["stages"].append({"stage": rec["stage"], "seconds": None, "stopped": s.state})
        emit(stage=rec["stage"], label=STAGE_LABEL.get(rec["stage"], ""), index=len(rec["stages"]),
             event="stop", seconds=None, message=s.message)
    rec["finished"] = C._now()
    rec["money_model"] = _rel(ctx["money_model"], cdir)
    rec["udp_dir"] = _rel(ctx["udp_dir"], cdir) if ctx.get("udp_dir") else None
    case = C.read_case(ws_dir, cid)
    case["run"] = rec
    C.write_case(ws_dir, cid, case)
    return rec


# ── 2 案を並べる ─────────────────────────────────────────────────────────
def _fixed_cost_plan(ws_dir: str, base: str, alt: str, out_csv: str) -> Optional[str]:
    rows = []
    for side, cid in (("base", base), ("alt", alt)):
        case = C.read_case(ws_dir, cid)
        fc = (case.get("inputs") or {}).get("fixed_cost")
        if not fc:
            continue
        _f, rs, _t, _b = C._read_rows(os.path.join(C.case_dir(ws_dir, cid), fc))
        for r in rs:
            rows.append(dict(case=side, **{k: r[k] for k in C.FIXED_COST_COLS},
                             **{C.COUNT_OUTSIDE_COL: (r.get(C.COUNT_OUTSIDE_COL) or "").strip()}))
    if not rows:
        return None
    cols = ["case"] + C.FIXED_COST_COLS + ([C.COUNT_OUTSIDE_COL] if any(r[C.COUNT_OUTSIDE_COL] for r in rows) else [])
    C._write_rows(out_csv, cols, rows, "\n", False)
    return out_csv


def compare_cases(ws_dir: str, base: str, alt: str) -> dict:
    """Tool 2 on two done cases -> <ws>/compare/<base>__<alt>/. Raises CaseError if a case is not done,
    StageStop(不整合) if a reconciliation of tool 2 fails."""
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    from tools import compare_scenarios as CS
    for cid in (base, alt):
        st = C.status(ws_dir, cid)
        if st["state"] != C.ST_DONE:
            raise C.CaseError(f"案 {cid} は「{st['state']}」です（{st['reason']}）。並べられるのは「済み」の案だけ")
    out = os.path.join(ws_dir, "compare", f"{base}__{alt}")
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    plan = _fixed_cost_plan(ws_dir, base, alt, os.path.join(out, "fixed_cost_plan.csv"))
    rb, ra = C.read_case(ws_dir, base)["run"], C.read_case(ws_dir, alt)["run"]
    bd, ad = C.case_dir(ws_dir, base), C.case_dir(ws_dir, alt)
    t0 = time.perf_counter()
    try:
        res = CS.compare(os.path.join(bd, "run"), os.path.join(ad, "run"),
                         os.path.join(bd, rb["money_model"]), os.path.join(ad, ra["money_model"]), out,
                         fixed_cost_plan=plan, base_name=base, alt_name=alt,
                         base_udp=os.path.join(bd, rb["udp_dir"]) if rb.get("udp_dir") else None,
                         alt_udp=os.path.join(ad, ra["udp_dir"]) if ra.get("udp_dir") else None)
    except CS.CompareError as e:
        rec = {"base": base, "alt": alt, "state": C.ST_INCONSISTENT, "message": str(e), "at": C._now()}
        C._write_json(os.path.join(out, "compare.json"), rec)
        raise StageStop(C.ST_INCONSISTENT, f"道具 2：{e}")
    fc = res["fixed_cost"]
    rows = json.loads(fc.to_json(orient="records", force_ascii=False))
    rec = {"base": base, "alt": alt, "state": C.ST_DONE, "at": C._now(),
           "seconds": round(time.perf_counter() - t0, 2),
           "base_input_hashes": rb["input_hashes"], "alt_input_hashes": ra["input_hashes"],
           "P0_base": float(fc["P0_base"].iloc[0]), "P0_alt": float(fc["P0_alt"].iloc[0]),
           "delta_P0": float(fc["delta_P0"].iloc[0]), "fixed_cost": rows,
           "fixed_cost_plan": "fixed_cost_plan.csv" if plan else None}
    C._write_json(os.path.join(out, "compare.json"), rec)
    return rec


def compare_status(ws_dir: str, base: str, alt: str) -> str:
    """済み / 未実行 / 入力が変わった (a case changed or was re-run after the comparison) / 不整合."""
    p = os.path.join(ws_dir, "compare", f"{base}__{alt}", "compare.json")
    if not os.path.exists(p):
        return C.ST_NOT_RUN
    rec = C._read_json(p)
    if rec["state"] != C.ST_DONE:
        return rec["state"]
    for cid, key in ((base, "base_input_hashes"), (alt, "alt_input_hashes")):
        run = C.read_case(ws_dir, cid).get("run") or {}
        if run.get("input_hashes") != rec[key] or C.status(ws_dir, cid)["state"] != C.ST_DONE:
            return C.ST_CHANGED
    return C.ST_DONE
