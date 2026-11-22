# -*- coding: utf-8 -*-
"""
wom/strategy/sheets.py — 入力のシートと型カタログを読む・検査する（ファイルは書かない）
=====================================================================================
RequestLetter_Promo_Convert_Slice1 §1・§2・§3.3（キャンペーンのそろい）。

シート（フォルダに 4 本）：
    measures.csv             施策（行ごとに型。campaign_id で需要の行と費用の行を結ぶ）
    hypotheses.csv           反応の仮説（hypothesis_id × level）
    external_conditions.csv  外部環境（初版は ENV_BASE_v01 の 1 行。行の形だけ）
    plans.csv                案の組み立て（キャンペーンと仮説の水準で選ぶ）
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
from decimal import Decimal
from typing import Dict, List, Optional

from wom.strategy import StrategyError, CATALOG_VERSION
from wom.strategy.rules import dec, week_range

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_FILE = os.path.join(HERE, "measure_type_catalog.csv")

CATALOG_COLS = ["measure_type", "p4", "input_unit", "target", "rule", "mark", "stop_conditions", "note"]
MEASURE_COLS = ["campaign_id", "measure_id", "measure_version", "p4", "measure_type", "sku_id", "market",
                "start_week", "end_week", "value", "unit", "currency", "entity", "cost_item", "hypothesis_id",
                "rationale"]
HYPOTHESIS_COLS = ["hypothesis_id", "version", "level", "kind", "rate", "lag_weeks", "rebound_rate",
                   "rebound_weeks", "basis", "evidence"]
ENV_COLS = ["env_id", "version", "description"]
PLAN_COLS = ["plan_id", "case_name", "campaign_ids", "hypothesis_level", "env_id"]

P4 = ("Product", "Price", "Place", "Promotion")
T_DEMAND = "promo_demand_delta"
T_COST = "promo_external_cost"
IMPLEMENTED = (T_DEMAND, T_COST)
LEVELS = ("low", "base", "high")
KINDS = ("promotion_response",)
BASES = ("validation_placeholder",)
COST_UNITS = ("amount_per_week",)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_csv(path: str, cols: List[str]) -> List[dict]:
    """Rows as dict of stripped text; stops on missing file or columns."""
    if not os.path.exists(path):
        raise StrategyError(f"{path} がありません")
    with open(path, "rb") as f:
        text = f.read().decode("utf-8-sig")
    rd = csv.DictReader(io.StringIO(text, newline=""))
    miss = [c for c in cols if c not in (rd.fieldnames or [])]
    if miss:
        raise StrategyError(f"{path}: 列が足りません {miss}（列は {cols}）")
    rows = []
    for i, r in enumerate(rd, start=2):
        x = {k: (v or "").strip() for k, v in r.items() if k is not None}
        x["_line"] = i
        rows.append(x)
    return rows


def _at(path: str, r: dict) -> str:
    return f"{os.path.basename(path)} の {r['_line']} 行目"


# ── 型カタログ ──────────────────────────────────────────────────────────
def read_catalog(path: Optional[str] = None) -> dict:
    """{"rows": {type: row}, "version": "v0.1 (sha256:…)", "path": …}. A type whose mark starts with × is
    listed but cannot be converted."""
    path = path or CATALOG_FILE
    rows = read_csv(path, CATALOG_COLS)
    out = {}
    for r in rows:
        t = r["measure_type"]
        if not t:
            raise StrategyError(f"{_at(path, r)}: measure_type が空欄です")
        if t in out:
            raise StrategyError(f"{_at(path, r)}: 型 {t} が重複しています")
        if r["p4"] not in P4:
            raise StrategyError(f"{_at(path, r)}: p4={r['p4']!r} は {P4} のどれか")
        out[t] = r
    return {"rows": out, "version": f"{CATALOG_VERSION} (sha256:{sha256_file(path)[:12]})", "path": path}


# ── シート ──────────────────────────────────────────────────────────────
def read_sheets(sheets_dir: str, catalog: dict) -> dict:
    """Read and check the four sheets (row-level checks; the plan-level checks are in select_plan)."""
    pm = os.path.join(sheets_dir, "measures.csv")
    ph = os.path.join(sheets_dir, "hypotheses.csv")
    pe = os.path.join(sheets_dir, "external_conditions.csv")
    pp = os.path.join(sheets_dir, "plans.csv")
    measures = read_csv(pm, MEASURE_COLS)
    hyps = read_csv(ph, HYPOTHESIS_COLS)
    envs = read_csv(pe, ENV_COLS)
    plans = read_csv(pp, PLAN_COLS)
    cat = catalog["rows"]

    seen = set()
    for r in measures:
        at = _at(pm, r)
        for c in ("campaign_id", "measure_id", "measure_version", "p4", "measure_type", "sku_id", "market",
                  "start_week", "end_week"):
            if not r[c]:
                raise StrategyError(f"{at}: {c} が空欄です")
        t = r["measure_type"]
        if t not in cat:
            raise StrategyError(f"{at}: 知らない型 {t!r}（型カタログ {os.path.basename(catalog['path'])} にありません。"
                                f"使える型：{sorted(cat)}）")
        if cat[t]["mark"].startswith("×"):
            raise StrategyError(f"{at}: 型 {t} は「今は表せない」（×）型です（{cat[t]['note']}）。直し方：型カタログの"
                                "代わりの型にする")
        if t not in IMPLEMENTED:
            raise StrategyError(f"{at}: 型 {t} はカタログにありますが、変換の規則がまだありません（初版は {IMPLEMENTED}）")
        if r["p4"] != cat[t]["p4"]:
            raise StrategyError(f"{at}: p4={r['p4']!r} が型 {t} の p4 {cat[t]['p4']!r} と違います")
        week_range(r["start_week"], r["end_week"])
        key = (r["measure_id"], r["measure_version"])
        if key in seen:
            raise StrategyError(f"{at}: 施策 {key[0]} の版 {key[1]} が重複しています（同じ施策を二重に入れない）")
        seen.add(key)
        if t == T_DEMAND:
            if not r["hypothesis_id"]:
                raise StrategyError(f"{at}: {T_DEMAND} には hypothesis_id が要ります（量は仮説から）")
            if r["value"]:
                raise StrategyError(f"{at}: {T_DEMAND} の value は空欄にしてください（量は仮説 {r['hypothesis_id']} から）")
        else:
            for c in ("value", "unit", "currency", "entity", "cost_item"):
                if not r[c]:
                    raise StrategyError(f"{at}: {T_COST} の {c} が空欄です")
            if r["unit"] not in COST_UNITS:
                raise StrategyError(f"{at}: unit={r['unit']!r} は {COST_UNITS}（初版）")
            v = dec(r["value"], f"{at} の value")
            if v < 0:
                raise StrategyError(f"{at}: value={r['value']} は 0 以上にしてください")
            if r["hypothesis_id"]:
                raise StrategyError(f"{at}: {T_COST} に hypothesis_id は使いません（{r['hypothesis_id']}）")

    hseen = set()
    for r in hyps:
        at = _at(ph, r)
        for c in HYPOTHESIS_COLS:
            if not r[c]:
                raise StrategyError(f"{at}: {c} が空欄です（根拠・区分も空欄にしない）")
        if r["level"] not in LEVELS:
            raise StrategyError(f"{at}: level={r['level']!r} は {LEVELS}")
        if r["kind"] not in KINDS:
            raise StrategyError(f"{at}: kind={r['kind']!r} は {KINDS}（初版）")
        if r["basis"] not in BASES:
            raise StrategyError(f"{at}: basis={r['basis']!r} は {BASES}（初版）")
        for c in ("rate", "rebound_rate"):
            if dec(r[c], f"{at} の {c}") < 0:
                raise StrategyError(f"{at}: {c}={r[c]} は 0 以上")
        for c in ("lag_weeks", "rebound_weeks"):
            v = dec(r[c], f"{at} の {c}")
            if v < 0 or v != v.to_integral_value():
                raise StrategyError(f"{at}: {c}={r[c]} は 0 以上の整数")
        k = (r["hypothesis_id"], r["level"])
        if k in hseen:
            raise StrategyError(f"{at}: 仮説 {k[0]} の水準 {k[1]} が重複しています（版を変えるなら hypothesis_id を分ける）")
        hseen.add(k)

    eseen = set()
    for r in envs:
        if not r["env_id"] or not r["version"]:
            raise StrategyError(f"{_at(pe, r)}: env_id・version が空欄です")
        if r["env_id"] in eseen:
            raise StrategyError(f"{_at(pe, r)}: env_id {r['env_id']} が重複しています")
        eseen.add(r["env_id"])

    pseen = set()
    for r in plans:
        if not r["plan_id"] or not r["env_id"]:
            raise StrategyError(f"{_at(pp, r)}: plan_id・env_id が空欄です")
        if r["plan_id"] in pseen:
            raise StrategyError(f"{_at(pp, r)}: plan_id {r['plan_id']} が重複しています")
        pseen.add(r["plan_id"])
    return {"dir": sheets_dir, "measures": measures, "hypotheses": hyps, "envs": envs, "plans": plans}


def select_plan(sheets: dict, plan_id: str) -> dict:
    """The plan's measures (by campaign) and hypothesis rows, with the campaign checks of §3.3:
    each chosen campaign has both a demand row and a cost row, with the same target, weeks and version."""
    plans = {r["plan_id"]: r for r in sheets["plans"]}
    if plan_id not in plans:
        raise StrategyError(f"plans.csv に案 {plan_id} がありません（ある案：{sorted(plans)}）")
    p = plans[plan_id]
    envs = {r["env_id"]: r for r in sheets["envs"]}
    if p["env_id"] not in envs:
        raise StrategyError(f"案 {plan_id} の env_id {p['env_id']} が external_conditions.csv にありません")
    camps = [c.strip() for c in p["campaign_ids"].split(";") if c.strip()]
    level = p["hypothesis_level"]
    if len(set(camps)) != len(camps):
        raise StrategyError(f"案 {plan_id}: campaign_ids に同じキャンペーンが 2 回あります（{camps}）")
    if camps and level not in LEVELS:
        raise StrategyError(f"案 {plan_id}: キャンペーンがあるのに hypothesis_level={level!r}（{LEVELS} のどれか）")
    if not camps and level:
        raise StrategyError(f"案 {plan_id}: キャンペーンが無いのに hypothesis_level={level!r} です")
    chosen = []
    for c in camps:
        rows = [r for r in sheets["measures"] if r["campaign_id"] == c]
        if not rows:
            raise StrategyError(f"案 {plan_id}: キャンペーン {c} の行が measures.csv にありません")
        dem = [r for r in rows if r["measure_type"] == T_DEMAND]
        cost = [r for r in rows if r["measure_type"] == T_COST]
        if len(dem) != 1 or len(cost) != 1:
            raise StrategyError(f"キャンペーン {c}: {T_DEMAND} と {T_COST} の行が 1 つずつ要ります（今 {len(dem)}・"
                                f"{len(cost)}）。需要だけ・費用だけのキャンペーンは作れません")
        a, b = dem[0], cost[0]
        for col in ("sku_id", "market", "start_week", "end_week", "measure_version"):
            if a[col] != b[col]:
                raise StrategyError(f"キャンペーン {c}: 需要の行と費用の行の {col} が違います（{a[col]} と {b[col]}）")
        chosen += [a, b]
    # one demand measure per key with overlapping weeks is not allowed in the first version
    dem = [r for r in chosen if r["measure_type"] == T_DEMAND]
    for i, a in enumerate(dem):
        for b in dem[i + 1:]:
            if (a["sku_id"], a["market"]) == (b["sku_id"], b["market"]) and \
                    not (a["end_week"] < b["start_week"] or b["end_week"] < a["start_week"]):
                raise StrategyError(f"案 {plan_id}: 同じ対象 {a['sku_id']} × {a['market']} の需要の施策 {a['measure_id']} と "
                                    f"{b['measure_id']} の週が重なります（初版は許しません）")
    hyps = {}
    for r in dem:
        k = (r["hypothesis_id"], level)
        h = [x for x in sheets["hypotheses"] if (x["hypothesis_id"], x["level"]) == k]
        if not h:
            raise StrategyError(f"施策 {r['measure_id']}: 仮説 {k[0]} の水準 {k[1]} が hypotheses.csv にありません")
        hyps[r["measure_id"]] = h[0]
    return {"plan": p, "env": envs[p["env_id"]], "campaigns": camps, "level": level, "measures": chosen,
            "hypotheses": hyps}
