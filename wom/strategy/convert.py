# -*- coding: utf-8 -*-
"""
wom/strategy/convert.py — 施策シートから 1 つの案の入力を書き換える（エンジンを import しない）
=============================================================================================
RequestLetter_Promo_Convert_Slice1 §3。

書くもの（案の中だけ。元のモデル・正式なサンプルには書かない）：
    model/demand_forecast.csv        promo_demand_delta：対象のキーの、反応・反動の週の行だけ（D ＝ B ＋ d）
    inputs/fixed_cost.csv            promo_external_cost：報告通貨の週額 1 行（既存の他の行は残す。
                                     wom.cockpit.cases.set_fixed_cost で書く）
                                     launch_one_time_cost：発生の週の 1 週の行（週額＝総額）
                                     launch_weekly_cost：有償の週の週額の行（販促の費用と同じ書き方）
    model/market_entry_plan.csv      product_launch_week：対象の行の launch_week だけ。需要は投入の表から
    model/demand_forecast.csv        道具 1（tools.gen_demand_from_entry_plan）で作り直す（cockpit の
                                     set_launch_week と同じ経路。RequestLetter_Launch_Convert_Slice1 §2）
    inputs/strategy_change_log.csv   変更記録（変換の前後・規則・端数・ID と版）
    case.json の changes             変換したこと（plan_id と記録のファイル）

規則：
- 基準の需要 B は凍結した元のモデル（作業を作った時の元のモデル。sha256 を workspace.json と照合）から
  読む。案の写しの需要を基準にしない（二重の上乗せを防ぐ）。
- 冪等：同じシートで同じ案にもう一度変換したら、需要・費用の前提・変更記録が同じになる（「変更なし」）。
- 書き込みの前に全部を検査する（止めたら何も書かない）。
"""
from __future__ import annotations

import io
import csv
import os
import re
import subprocess
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from wom.cockpit import cases as C
from wom.strategy import StrategyError
from wom.strategy import rules as RU
from wom.strategy import sheets as SH

LOG_FILE = "strategy_change_log.csv"
LOG_COLS = ["plan_id", "campaign_id", "measure_id", "measure_version", "hypothesis_id", "hypothesis_version", "level",
            "env_id", "catalog_version", "base_model", "base_demand_sha256", "start_sha", "file", "key", "column",
            "week", "before", "after", "rule", "note"]
TAG = "strategy_convert"
_TAG_RE = re.compile(r"(?:^|;\s*)(campaign|measure|version)=([^;]+)")
RESIDUAL_NOTE = "未反映の端数（区間の終わり。後の週・別の施策・別の水準へ移さない）"
COST_WEEKS_NOTE = "paid_start_week・paid_end_week は費用の発生の週（現金の支払いの週を決めたものではない）"


def _git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=C.REPO, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:
        return ""


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _demand_map(path: str) -> Tuple[list, List[dict], str, bool, Dict[tuple, Decimal], Dict[tuple, int]]:
    fields, rows, term, bom = C._read_rows(path)
    for c in ("sku_id", "region", "week", "quantity"):
        if c not in fields:
            raise StrategyError(f"{path}: 列 {c} がありません")
    m, idx = {}, {}
    for i, r in enumerate(rows):
        k = (r["sku_id"].strip(), r["region"].strip(), r["week"].strip())
        if k in m:
            raise StrategyError(f"{path}: 同じ鍵 {k} の行が 2 つあります")
        m[k] = RU.dec(r["quantity"], f"{path} の {k} の quantity")
        idx[k] = i
    return fields, rows, term, bom, m, idx


def tag_of(note: str) -> Optional[dict]:
    """The conversion tag of a fixed-cost note: {"campaign":…, "measure":…, "version":…} or None."""
    if not (note or "").startswith(TAG):
        return None
    return {k: v.strip() for k, v in _TAG_RE.findall(note)}


def _kv_rows(path: str, key: str = "key", val: str = "value") -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    _f, rows, _t, _b = C._read_rows(path)
    return {r.get(key, "").strip(): (r.get(val) or "").strip() for r in rows}


# ── 対象の解決 ──────────────────────────────────────────────────────────
def resolve_target(model_dir: str, sku: str, market: str) -> dict:
    """(sku, market) -> the leaf_out node of the tree, the market price rows and the entity (if assigned)."""
    _f, tree, _t, _b = C._read_rows(os.path.join(model_dir, "sc_tree_master.csv"))
    nodes = [r["node_name"].strip() for r in tree if r.get("product_name", "").strip() == sku
             and r.get("node_type", "").strip() == "leaf_out" and r.get("region", "").strip() == market]
    if len(nodes) != 1:
        raise StrategyError(f"対象 {sku} × {market} が計画の木（sc_tree_master.csv）の leaf_out で 1 つに解決できません"
                            f"（{len(nodes)} 件）。直し方：market に需要の region（leaf_out の識別子）を書く")
    node = nodes[0]
    _f, price, _t, _b = C._read_rows(os.path.join(model_dir, "ppc_market_price.csv"))
    prows = [r for r in price if r.get("market_node", "").strip() == node and r.get("product_id", "").strip() == sku]
    if not prows:
        raise StrategyError(f"対象 {sku} × {market}（ノード {node}）の価格が ppc_market_price.csv にありません")
    entity = None
    pa = os.path.join(model_dir, "vc_node_assignment.csv")
    if os.path.exists(pa):
        _f, asg, _t, _b = C._read_rows(pa)
        e = [r["entity_id"].strip() for r in asg if r.get("node_id", "").strip() == node
             and r.get("product_id", "").strip() == sku]
        entity = e[0] if len(e) == 1 else None
    return {"node": node, "price_currency": sorted({r.get("currency", "").strip() for r in prows}), "entity": entity}


# ── 変換 ───────────────────────────────────────────────────────────────
def plan_changes(ws_dir: str, cid: str, plan_id: str, sheets_dir: str, base_model: str,
                 catalog_path: Optional[str] = None) -> dict:
    """Check everything and compute what to write (nothing is written). Raises StrategyError."""
    ws = C.open_workspace(ws_dir)
    cdir = C.case_dir(ws_dir, cid)
    mdir = os.path.join(cdir, "model")
    if not _same_path(base_model, ws["source_model"]):
        raise StrategyError(f"--base-model {base_model} が作業の元のモデル {ws['source_model']} と違います。"
                            "直し方：作業を作った元のモデルを渡す")
    base_model = os.path.abspath(base_model)
    for fn, h in (ws.get("source_model_sha256") or {}).items():
        p = os.path.join(base_model, fn)
        now = SH.sha256_file(p) if os.path.exists(p) else "missing"
        if now != h:
            raise StrategyError(f"元のモデルの {fn} が作業を作った時から変わっています（sha256 {h[:12]} → {now[:12]}）。"
                                "直し方：基準が凍結されていないので、作業を作り直す")
    catalog = SH.read_catalog(catalog_path)
    sheets = SH.read_sheets(sheets_dir, catalog)
    sel = SH.select_plan(sheets, plan_id)
    has_entry = os.path.exists(os.path.join(mdir, C.ENTRY_PLAN))
    mtypes = {m["measure_type"] for m in sel["measures"]}
    if has_entry and mtypes & set(SH.PROMO_TYPES):
        raise StrategyError(f"案 {cid} のモデルに {C.ENTRY_PLAN} があります。投入の表のある案に販促の型"
                            f"（{sorted(mtypes & set(SH.PROMO_TYPES))}）は書けません（基準需要の生成 → 販促の差分 → "
                            "需要の確定の経路をまだ定義していない。需要の正本が 2 つになる）")
    if not has_entry and SH.T_LAUNCH in mtypes:
        raise StrategyError(f"案 {cid} のモデルに {C.ENTRY_PLAN} がありません。{SH.T_LAUNCH} は投入の表の対象の行の "
                            "launch_week を書く型です。直し方：先に投入の表を案に置く（cockpit_cases set entry-plan）")
    plan_weeks = RU.week_range(ws["demand_period"]["start"], ws["demand_period"]["end"])

    base_csv = os.path.join(base_model, C.DEMAND)
    base_sha = SH.sha256_file(base_csv)
    _bf, _br, _bt, _bb, bmap, _bi = _demand_map(base_csv)
    case_csv = os.path.join(mdir, C.DEMAND)
    fields, rows, term, bom, cmap, cidx = _demand_map(case_csv)
    if set(bmap) != set(cmap):
        extra = sorted(set(cmap) ^ set(bmap))
        raise StrategyError(f"案 {cid} の需要の鍵が元のモデルと違います（{len(extra)} 件、例 {extra[0]}）。"
                            "基準がずれています。直し方：案を元のモデルから作り直す")
    start_sha = _git_head()
    common = {"plan_id": plan_id, "env_id": sel["env"]["env_id"], "catalog_version": catalog["version"],
              "base_model": os.path.relpath(base_model, C.REPO).replace("\\", "/") if
              os.path.commonpath([os.path.normcase(base_model), os.path.normcase(C.REPO)]) == os.path.normcase(C.REPO)
              else base_model, "base_demand_sha256": base_sha, "start_sha": start_sha, "level": sel["level"]}

    log: List[dict] = []
    new_q: Dict[tuple, Decimal] = {}          # demand key -> D (the weeks the measures touch)
    touched_keys = set()
    measures = sel["measures"]
    demand_ms = [m for m in measures if m["measure_type"] == SH.T_DEMAND]
    cost_ms = [m for m in measures if m["measure_type"] in SH.COST_TYPES]
    launch_ms = [m for m in measures if m["measure_type"] == SH.T_LAUNCH]
    targets = {}
    for m in measures:
        targets[(m["sku_id"], m["market"])] = resolve_target(mdir, m["sku_id"], m["market"])
    summary = []
    for m in demand_ms:
        sku, mk = m["sku_id"], m["market"]
        h = sel["hypotheses"][m["measure_id"]]
        base = {w: bmap[(sku, mk, w)] for w in plan_weeks if (sku, mk, w) in bmap}
        if not base:
            raise StrategyError(f"施策 {m['measure_id']}: 対象 {sku} × {mk} の需要の行が元のモデルにありません")
        res = RU.demand_delta(base, m["start_week"], m["end_week"], RU.dec(h["rate"], "rate"), int(h["lag_weeks"]),
                              RU.dec(h["rebound_rate"], "rebound_rate"), int(h["rebound_weeks"]), plan_weeks)
        D = RU.apply_delta(base, res["d"], f"施策 {m['measure_id']}（{sku} × {mk}）：")
        touched_keys.add((sku, mk))
        mc = {"campaign_id": m["campaign_id"], "measure_id": m["measure_id"], "measure_version": m["measure_version"],
              "hypothesis_id": h["hypothesis_id"], "hypothesis_version": h["version"]}
        for iv in res["intervals"]:
            for w, x, s in zip(iv["weeks"], iv["x"], iv["steps"]):
                k = (sku, mk, w)
                new_q[k] = D[w]
                note = f"x={RU.num_text(x)}; d={s:+d}"
                if cmap[k] not in (bmap[k], D[w]):
                    note += f"; 案の前の値 {RU.num_text(cmap[k])}（凍結した基準から作り直す）"
                log.append({**common, **mc, "file": f"model/{C.DEMAND}", "key": f"{sku}|{mk}", "column": "quantity",
                            "week": w, "before": RU.num_text(bmap[k]), "after": RU.num_text(D[w]),
                            "rule": f"{SH.T_DEMAND}/{iv['kind']} rate={h['rate'] if iv['kind'] == 'response' else h['rebound_rate']}"
                                    f" lag={h['lag_weeks']}", "note": note})
            log.append({**common, **mc, "file": f"model/{C.DEMAND}", "key": f"{sku}|{mk}", "column": "quantity",
                        "week": iv["weeks"][-1], "before": "", "after": RU.num_text(iv["residual"]),
                        "rule": "residual", "note": f"{iv['kind']} の区間 {iv['weeks'][0]}〜{iv['weeks'][-1]}："
                                                    f"{RESIDUAL_NOTE}"})
        summary.append({"measure_id": m["measure_id"], "key": f"{sku}|{mk}", "level": sel["level"],
                        "rate": h["rate"], "response_weeks": f"{res['response_weeks'][0]}〜{res['response_weeks'][-1]}",
                        "added_lots": sum(v for v in res["d"].values() if v > 0),
                        "removed_lots": -sum(v for v in res["d"].values() if v < 0),
                        "residuals": [RU.num_text(iv["residual"]) for iv in res["intervals"]]})

    entry = None
    if launch_ms:
        entry = _plan_launch(ws, mdir, cid, launch_ms, bmap, common, log, new_q, summary)

    # the inputs of every key the measures do not touch, and the untouched weeks of touched keys, are the base
    drift = [k for k in cmap if k not in new_q and cmap[k] != bmap[k]]
    if drift:
        raise StrategyError(f"案 {cid} の需要が、施策の対象の外で元のモデルと違います（{len(drift)} 行、例 {drift[0]}："
                            f"案 {RU.num_text(cmap[drift[0]])}、元 {RU.num_text(bmap[drift[0]])}）。基準がずれています。"
                            "直し方：案を元のモデルから作り直す（別の案を変換した写しを使わない）")

    # cost premises
    hq = _kv_rows(os.path.join(base_model, "vc_config.csv")).get("hq_currency", "")
    if cost_ms and not hq:
        raise StrategyError(f"{base_model}/vc_config.csv に hq_currency がありません（報告通貨が決まらない）")
    fx_path = os.path.join(base_model, "ppc_fx_rate.csv")
    fx_rows = C._read_rows(fx_path)[1] if cost_ms else []
    fc_rel = (C.read_case(ws_dir, cid).get("inputs") or {}).get("fixed_cost")
    fc_path = os.path.join(cdir, fc_rel) if fc_rel else None
    old_rows = C._read_rows(fc_path)[1] if fc_path and os.path.exists(fc_path) else []
    new_cost = []
    for m in cost_ms:
        t = targets[(m["sku_id"], m["market"])]
        if m["measure_type"] == SH.T_COST:
            if t["entity"] is not None and t["entity"] != m["entity"]:
                raise StrategyError(f"施策 {m['measure_id']}: 負担法人 {m['entity']} が対象の市場 {t['node']} の法人 {t['entity']}"
                                    "（vc_node_assignment.csv）と違います")
        else:
            _check_launch_cost_entity(mdir, m, t)
        weeks = RU.week_range(m["start_week"], m["end_week"])
        rate = RU.fx_rate_for_weeks(fx_rows, m["currency"], hq, weeks, "ppc_fx_rate.csv（元のモデル）")
        val = RU.dec(m["value"], "value")
        yen = val * rate
        if m["measure_type"] == SH.T_LAUNCH_ONE:
            # one week: the weekly amount is the total, so the comparison subtracts it once
            note = (f"{TAG}; campaign={m['campaign_id']}; measure={m['measure_id']}; version={m['measure_version']}; "
                    f"一時の費用 総額 {RU.num_text(val)} {m['currency']} × {RU.num_text(rate)} {hq}/{m['currency']}"
                    f"（ppc_fx_rate.csv、元のモデル） = {RU.num_text(yen)} {hq}、発生の週 {m['start_week']} の 1 週の行"
                    f"（週額 ＝ 総額）; {COST_WEEKS_NOTE}")
        else:
            note = (f"{TAG}; campaign={m['campaign_id']}; measure={m['measure_id']}; version={m['measure_version']}; "
                    f"{RU.num_text(val)} {m['currency']}/週 × {RU.num_text(rate)} {hq}/{m['currency']}（ppc_fx_rate.csv、元のモデル）"
                    f" = {RU.num_text(yen)} {hq}/週 × {len(weeks)} 週 = {RU.num_text(yen * len(weeks))} {hq}; {COST_WEEKS_NOTE}")
        row = {"cost_item": m["cost_item"], "entity": m["entity"], "paid_start_week": m["start_week"],
               "paid_end_week": m["end_week"], "weekly_amount": RU.num_text(yen), "currency": hq, "note": note,
               C.COUNT_OUTSIDE_COL: "", C.DISPLAY_COL: ""}
        new_cost.append((m, row, val, rate, weeks))
    new_items = {r["cost_item"]: (m, r) for m, r, _v, _r, _w in new_cost}
    if len(new_items) != len(new_cost):
        raise StrategyError("この案の費用の施策が同じ cost_item を 2 回使っています")
    keep, unchanged_cost = [], True
    old_by_item = {}
    for r in old_rows:
        item = r.get("cost_item", "").strip()
        old_by_item[item] = r
        tg = tag_of(r.get("note", ""))
        if item in new_items:
            m, nr = new_items[item]
            if not tg or tg.get("measure") != m["measure_id"]:
                raise StrategyError(f"案 {cid} の費用の前提に cost_item {item} の行が既にあり、別の出どころです"
                                    f"（{(r.get('note') or '')[:80]!r}）。直し方：費目名を分ける")
            if tg.get("version") != m["measure_version"]:
                raise StrategyError(f"案 {cid} の費用の前提の {item} は施策 {m['measure_id']} の版 {tg.get('version')} から"
                                    f"書いたものです（今は版 {m['measure_version']}）。直し方：案を作り直すか、行を消してから変換する")
            same = all((r.get(c) or "").strip() == nr[c] for c in C.FIXED_COST_COLS)
            if not same:
                raise StrategyError(f"案 {cid} の費用の前提の {item} は同じ施策・版なのに中身が違います"
                                    f"（週額 {r.get('weekly_amount')} → {nr['weekly_amount']} など）。直し方：シートか行を見直す")
            continue
        if tg:
            raise StrategyError(f"案 {cid} の費用の前提に、この案（{plan_id}）に無い施策 {tg.get('measure')} から書いた行 "
                                f"{item} があります。直し方：案を元のモデルから作り直す（費用を二重に数えない）")
        keep.append(r)
    added = [nr for item, (m, nr) in new_items.items() if item not in old_by_item]
    if added:
        unchanged_cost = False
    for m, row, val, rate, weeks in new_cost:
        before = ""     # the base has no such row (an existing row of the same item is this measure's own, or it stopped)
        log.append({**common, "campaign_id": m["campaign_id"], "measure_id": m["measure_id"],
                    "measure_version": m["measure_version"], "hypothesis_id": "", "hypothesis_version": "",
                    "file": f"inputs/{C.FIXED_COST_FILE}", "key": f"{row['cost_item']}|{row['entity']}",
                    "column": "weekly_amount", "week": f"{m['start_week']}..{m['end_week']}", "before": before,
                    "after": row["weekly_amount"], "rule": m["measure_type"],
                    "note": (f"一時の費用 {RU.num_text(val)} {m['currency']} × {RU.num_text(rate)} = {row['weekly_amount']} {hq}"
                             f"（{m['start_week']} の 1 週）" if m["measure_type"] == SH.T_LAUNCH_ONE else
                             f"{RU.num_text(val)} {m['currency']}/週 × {RU.num_text(rate)} = {row['weekly_amount']} {hq}/週、"
                             f"{len(weeks)} 週・計 {RU.num_text(val * rate * len(weeks))} {hq}（元 "
                             f"{RU.num_text(val * len(weeks))} {m['currency']}）") +
                            "。案の外の費用（PPC・Value Chain の規則には書かない）"})
    if not measures:
        log.append({**common, "campaign_id": "", "measure_id": "", "measure_version": "", "hypothesis_id": "",
                    "hypothesis_version": "", "file": "", "key": "", "column": "", "week": "", "before": "", "after": "",
                    "rule": "no_measure", "note": "施策なし（需要・費用の前提を変えない）"})

    new_rows = [dict(r) for r in rows]
    demand_changed = False
    for k, v in new_q.items():
        if cmap[k] != v:
            new_rows[cidx[k]]["quantity"] = RU.num_text(v)
            demand_changed = True
    if entry is not None and entry["changed"]:
        demand_changed = True
    log_path = os.path.join(cdir, "inputs", LOG_FILE)
    log_text = _log_text(log)
    old_log = open(log_path, encoding="utf-8").read() if os.path.exists(log_path) else None
    return {"ws": ws_dir, "case": cid, "plan_id": plan_id, "selection": sel, "catalog": catalog, "log": log,
            "log_text": log_text, "log_changed": old_log != log_text, "log_path": log_path,
            "demand": {"path": case_csv, "fields": fields, "rows": new_rows, "term": term, "bom": bom,
                       "changed": demand_changed, "entry_plan": entry, "expected": dict(new_q)},
            "cost": {"keep": keep, "new": [r for _m, r, _v, _r, _w in new_cost], "changed": not unchanged_cost},
            "summary": summary, "start_sha": start_sha, "base_demand_sha256": base_sha}


def _log_text(log: List[dict]) -> str:
    buf = io.StringIO(newline="")
    wr = csv.DictWriter(buf, fieldnames=LOG_COLS, lineterminator="\n")
    wr.writeheader()
    for r in log:
        wr.writerow({c: r.get(c, "") for c in LOG_COLS})
    return buf.getvalue()


def convert(ws_dir: str, cid: str, plan_id: str, sheets_dir: str, base_model: str, dry_run: bool = False,
            catalog_path: Optional[str] = None) -> dict:
    """Convert the plan into the case. Returns the plan of changes with "state": 変更なし / 変換した / 書かない（dry-run）."""
    C._guard_not_running(ws_dir, cid)
    pc = plan_changes(ws_dir, cid, plan_id, sheets_dir, base_model, catalog_path)
    changed = pc["demand"]["changed"] or pc["cost"]["changed"] or pc["log_changed"]
    if dry_run:
        pc["state"] = "書かない（dry-run）" + ("" if changed else "：変更なし")
        return pc
    if not changed:
        pc["state"] = "変更なし"
        return pc
    d = pc["demand"]
    if d["changed"] and d["entry_plan"] is not None:
        _write_launch(ws_dir, cid, d)
    elif d["changed"]:
        C._write_rows(d["path"], d["fields"], d["rows"], d["term"], d["bom"])
    if pc["cost"]["changed"]:
        C.set_fixed_cost(ws_dir, cid, rows=pc["cost"]["keep"] + pc["cost"]["new"])
    os.makedirs(os.path.dirname(pc["log_path"]), exist_ok=True)
    with open(pc["log_path"], "w", encoding="utf-8", newline="") as f:
        f.write(pc["log_text"])
    C._record_change(ws_dir, cid, "strategy_convert",
                     {"plan_id": plan_id, "log": f"inputs/{LOG_FILE}", "env_id": pc["selection"]["env"]["env_id"],
                      "campaigns": pc["selection"]["campaigns"], "level": pc["selection"]["level"],
                      "catalog_version": pc["catalog"]["version"], "base_demand_sha256": pc["base_demand_sha256"],
                      "start_sha": pc["start_sha"], "demand_changed": d["changed"],
                      "cost_changed": pc["cost"]["changed"]})
    pc["state"] = "変換した"
    return pc


# ── 投入週（RequestLetter_Launch_Convert_Slice1 §2.2・§2.3） ─────────────────────────────────
LAUNCH_NOTE = "投入の表の対象の行の launch_week だけを変え、道具 1（tools.gen_demand_from_entry_plan）で需要を作る"


def _gen():
    import sys
    if C.REPO not in sys.path:
        sys.path.insert(0, C.REPO)
    from tools import gen_demand_from_entry_plan as G
    return G


def _plan_launch(ws: dict, mdir: str, cid: str, launch_ms: List[dict], bmap: Dict[tuple, Decimal], common: dict,
                 log: List[dict], new_q: Dict[tuple, Decimal], summary: List[dict]) -> dict:
    """Put each measure's week into the case's entry plan (in memory), generate the demand with tool 1's
    functions and check it (§2.2): every key / week outside the targets equals the frozen base demand; only
    launch_week of the target rows changes. Fills new_q (every week of the target keys), the log and the
    summary. Returns the entry plan to write."""
    G = _gen()
    path = os.path.join(mdir, C.ENTRY_PLAN)
    try:
        prows, _raw, _p = G.read_plan(mdir)
    except G.EntryPlanError as e:
        raise StrategyError(f"案 {cid} の投入の表を読めません：{e}")
    fields, rows, term, bom = C._read_rows(path)
    before_rows = [dict(r) for r in rows]
    weeks = G.week_range(ws["demand_period"]["start"], ws["demand_period"]["end"])
    targets = {}
    for m in launch_ms:
        k = (m["sku_id"], m["market"])
        hit = [r for r in prows if (r["sku_id"], r["region"]) == k]
        raw = [r for r in rows if (r.get("sku_id", "").strip(), r.get("region", "").strip()) == k]
        if len(hit) != 1 or len(raw) != 1:
            raise StrategyError(f"案 {cid} の投入の表に鍵 {k[0]}:{k[1]} の行が {len(hit)} 行です（1 行のはず）")
        targets[k] = (m, hit[0]["launch_week"])
        hit[0]["launch_week"] = m["start_week"]
        raw[0]["launch_week"] = m["start_week"]
    # 2. only launch_week of the target rows differs from the entry plan the case has
    for a, b in zip(before_rows, rows):
        diff = [c for c in fields if (a.get(c) or "") != (b.get(c) or "")]
        k = (a.get("sku_id", "").strip(), a.get("region", "").strip())
        if diff and (k not in targets or diff != ["launch_week"]):
            raise StrategyError(f"投入の表の {k} で launch_week 以外の列 {diff} が変わります（変換の誤り）")
    try:
        lines = G.generate(prows, weeks, path)
    except G.EntryPlanError as e:
        raise StrategyError(f"案 {cid} の需要を投入の表から作れません：{e}")
    gmap = {(s_, g, w): Decimal(q) for s_, g, w, q in lines}
    if set(gmap) != set(bmap):
        extra = sorted(set(gmap) ^ set(bmap))
        raise StrategyError(f"投入の表から作った需要の鍵・週が元のモデルの需要と違います（{len(extra)} 件、例 {extra[0]}）。"
                            "投入の表と元のモデルの需要が食い違っています")
    # 1. outside the targets the generated demand must be the frozen base demand
    bad = [k for k in gmap if (k[0], k[1]) not in targets and gmap[k] != bmap[k]]
    if bad:
        raise StrategyError(f"投入の表から作った需要が、対象の外で元のモデルの需要と違います（{len(bad)} 行、例 {bad[0]}："
                            f"投入の表 {RU.num_text(gmap[bad[0]])}、元 {RU.num_text(bmap[bad[0]])}）。"
                            "投入の表と元のモデルの需要が食い違っています。直し方：投入の表を見直す")
    for (sku, mk), (m, plan_week) in targets.items():
        mc = {"campaign_id": m["campaign_id"], "measure_id": m["measure_id"], "measure_version": m["measure_version"],
              "hypothesis_id": "", "hypothesis_version": ""}
        base_nz = [w for w in weeks if bmap[(sku, mk, w)] != 0]
        base_week = base_nz[0] if base_nz else ""
        log.append({**common, **mc, "file": f"model/{C.ENTRY_PLAN}", "key": f"{sku}|{mk}", "column": "launch_week",
                    "week": "", "before": base_week, "after": m["start_week"], "rule": SH.T_LAUNCH,
                    # the case's pre-conversion value is not written here (it changes on a second run: idempotent)
                    "note": f"before は凍結した基準需要の最初の非ゼロの週。{LAUNCH_NOTE}"})
        tb = ta = Decimal(0)
        years: Dict[str, List[Decimal]] = {}
        for w in weeks:
            k = (sku, mk, w)
            new_q[k] = gmap[k]
            tb += bmap[k]
            ta += gmap[k]
            y = years.setdefault(w[:4], [Decimal(0), Decimal(0)])
            y[0] += bmap[k]
            y[1] += gmap[k]
            log.append({**common, **mc, "file": f"model/{C.DEMAND}", "key": f"{sku}|{mk}", "column": "quantity",
                        "week": w, "before": RU.num_text(bmap[k]), "after": RU.num_text(gmap[k]),
                        "rule": f"{SH.T_LAUNCH} launch_week={m['start_week']}",
                        "note": "before は凍結した基準需要、after は投入の表から作った需要"})
        for y, (b, a) in sorted(years.items()):
            log.append({**common, **mc, "file": f"model/{C.DEMAND}", "key": f"{sku}|{mk}",
                        "column": "quantity_year_total", "week": y, "before": RU.num_text(b), "after": RU.num_text(a),
                        "rule": "summary", "note": "年の合計（要約。週別の行と重ねて数えない）"})
        summary.append({"measure_id": m["measure_id"], "key": f"{sku}|{mk}", "type": SH.T_LAUNCH,
                        "launch_week_before": plan_week, "launch_week_after": m["start_week"],
                        "total_before": int(tb), "total_after": int(ta), "diff": int(ta - tb)})
    changed = any((a.get("launch_week") or "") != (b.get("launch_week") or "") for a, b in zip(before_rows, rows))
    return {"path": path, "fields": fields, "rows": rows, "term": term, "bom": bom, "changed": changed,
            "before_bytes": open(path, "rb").read()}


def _write_launch(ws_dir: str, cid: str, d: dict) -> None:
    """Write the entry plan and regenerate the demand with tool 1 (cockpit's path), then check the demand is the
    one planned; put the entry plan back if not."""
    e = d["entry_plan"]
    C._write_rows(e["path"], e["fields"], e["rows"], e["term"], e["bom"])
    try:
        C.regenerate_demand(ws_dir, cid)
        _f, _r, _t, _b, got, _i = _demand_map(d["path"])
        bad = [k for k, v in d["expected"].items() if got.get(k) != v]
        if bad:
            raise StrategyError(f"作り直した需要が変換の予定と違います（{len(bad)} 行、例 {bad[0]}）")
    except Exception:
        open(e["path"], "wb").write(e["before_bytes"])
        C.regenerate_demand(ws_dir, cid)
        raise


def _check_launch_cost_entity(mdir: str, m: dict, t: dict) -> None:
    """§2.3: the market's entity is external (vc_entity consolidated = 0) -> the entity of the parent node that
    sells to it must be the measure's entity; consolidated -> the market's entity itself; otherwise stop."""
    node, ent = t["node"], t["entity"]
    pe = os.path.join(mdir, "vc_entity.csv")
    cons = {}
    if os.path.exists(pe):
        _f, er, _t, _b = C._read_rows(pe)
        cons = {r["entity_id"].strip(): (r.get("consolidated") or "").strip() for r in er}
    flag = cons.get(ent or "")
    if flag == "1":
        if ent != m["entity"]:
            raise StrategyError(f"施策 {m['measure_id']}: 負担法人 {m['entity']} が対象の市場 {node} の法人 {ent} と違います")
        return
    if flag == "0":
        _f, tree, _t, _b = C._read_rows(os.path.join(mdir, "sc_tree_master.csv"))
        par = [r.get("parent_node", "").strip() for r in tree if r.get("node_name", "").strip() == node
               and r.get("product_name", "").strip() == m["sku_id"]]
        parent = par[0] if len(par) == 1 else ""
        _f, asg, _t, _b = C._read_rows(os.path.join(mdir, "vc_node_assignment.csv"))
        pe_ = [r["entity_id"].strip() for r in asg if r.get("node_id", "").strip() == parent
               and r.get("product_id", "").strip() == m["sku_id"]]
        pent = pe_[0] if len(pe_) == 1 else None
        if pent is None or pent != m["entity"]:
            raise StrategyError(f"施策 {m['measure_id']}: 対象の市場 {node} の法人 {ent} は外部なので、負担法人は"
                                f"その市場へ売る親のノード {parent or '（不明）'} の法人 {pent} のはずですが、{m['entity']} です")
        return
    raise StrategyError(f"施策 {m['measure_id']}: 対象の市場 {node} の法人 {ent!r} が vc_node_assignment.csv・vc_entity.csv で"
                        "決まりません（連結の内か外か）")
