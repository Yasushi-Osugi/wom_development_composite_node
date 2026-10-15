# -*- coding: utf-8 -*-
"""
tools/lesson000_variants.py — Lesson 000 comparison models (RequestLetter_Lesson000_Public)

Builds three comparison models from data/sample/rice-japan-2027-2028 by changing a
fixed set of rows (CHANGES below), and optionally runs them with
tools.rice_seasonal_check and writes the comparison table.

    python -m tools.lesson000_variants                  # build the 3 models in output/lesson000/models/
    python -m tools.lesson000_variants --out <folder>
    python -m tools.lesson000_variants --run            # build, run base + 3, write the table
    python -m tools.lesson000_variants --list           # print the table of changed values only

The models are NOT kept under data/sample/ (they would join the golden / identity /
recommended-plugin tests and the GUI model list, and go stale when the base changes).

If a row condition matches no row, or a different number of rows than expected,
the tool stops: the base model has changed and CHANGES must be checked.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from fractions import Fraction

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_NAME = "rice-japan-2027-2028"
BASE_DIR = os.path.join(REPO, "data", "sample", BASE_NAME)
OUT_MODELS = os.path.join(REPO, "output", "lesson000", "models")
OUT_RESULTS = os.path.join(REPO, "output", "lesson000", "results")
NOTE = "比較用：+30%"
FACTOR = Fraction(13, 10)

# ── the one table of changes ─────────────────────────────────────────────
# group, file, row condition (column -> value), base value (column, value),
# expected number of matching rows, column for the note, label
CHANGES = (
    ("harvest", "rice_resource_capacity.csv", {"resource_id": "FIELD_NIIGATA"}, ("capacity", 15500), 9, "note",
     "FIELD_NIIGATA の収穫週（各年 W41〜W43）"),
    ("harvest", "rice_crop_limit.csv", {"resource_id": "FIELD_NIIGATA"}, ("limit", 46500), 3, "note",
     "FIELD_NIIGATA の年産上限（2026・2027・2028）"),
    ("harvest", "capacity_plan.csv", {"sku_id": "Koshihikari", "node_name": "Tanbo_Niigata"}, ("max_supply", 15500), 9, "source",
     "Koshihikari,Tanbo_Niigata の収穫週"),
    ("mill", "rice_resources.csv", {"resource_id": "MILL_E"}, ("default_capacity", 1300), 1, "note",
     "MILL_E（精米センター東、二品目で共用）"),
    ("mill", "rice_resources.csv", {"resource_id": "MILL_W"}, ("default_capacity", 1000), 1, "note",
     "MILL_W（精米センター西、二品目で共用）"),
    ("mill", "capacity_plan.csv", {"node_name": "Seihaku_E"}, ("max_supply", 1300), 314, "source",
     "Seihaku_E の全行（両品目）"),
    ("mill", "capacity_plan.csv", {"node_name": "Seihaku_W"}, ("max_supply", 1000), 314, "source",
     "Seihaku_W の全行（両品目）"),
    # The upper layer has no weekly mill rows in the base model. If they appear, this stops.
    ("mill", "rice_resource_capacity.csv", {"resource_id": "MILL_E"}, ("capacity", None), 0, "note",
     "精米の週ごとの行（基準には無い）"),
    ("mill", "rice_resource_capacity.csv", {"resource_id": "MILL_W"}, ("capacity", None), 0, "note",
     "精米の週ごとの行（基準には無い）"),
)

VARIANTS = (
    ("rice_harvest_plus30", "新潟の収穫 +30%", ("harvest",)),
    ("rice_mill_plus30", "精米センター +30%（二品目で共用）", ("mill",)),
    ("rice_harvest_mill_plus30", "収穫 +30% と精米 +30% の両方", ("harvest", "mill")),
)


class BaseModelChanged(SystemExit):
    pass


def _new_value(old_text):
    v = Fraction(old_text) * FACTOR
    if v.denominator != 1:
        raise BaseModelChanged(f"[lesson000] {old_text} x 1.3 is not a whole number")
    return f"{int(v)}.0" if "." in old_text else str(int(v))


def _matches(row, cond, base):
    if any(row.get(k) != v for k, v in cond.items()):
        return False
    col, val = base
    return val is None or float(row[col]) == val


def apply_changes(model_dir, groups):
    """Change the rows of CHANGES for the given groups in model_dir (in place).
    Returns [(file, label, column, old -> new, rows)]."""
    done = []
    for group, fname, cond, base, expected, note_col, label in CHANGES:
        if group not in groups:
            continue
        path = os.path.join(model_dir, fname)
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
        rows = list(csv.reader(io.StringIO(text)))
        head = rows[0]
        idx = {c: i for i, c in enumerate(head)}
        col = base[0]
        hits, olds, news = 0, set(), set()
        for r in rows[1:]:
            if not r:
                continue
            d = dict(zip(head, r))
            if not _matches(d, cond, base):
                continue
            hits += 1
            old = r[idx[col]]
            new = _new_value(old)
            olds.add(old); news.add(new)
            r[idx[col]] = new
            if note_col in idx:
                r[idx[note_col]] = NOTE
        if hits != expected:
            raise BaseModelChanged(
                f"[lesson000] {fname}: condition {cond} with {col}={base[1]} matched {hits} rows, "
                f"expected {expected}. The base model changed; check CHANGES in tools/lesson000_variants.py.")
        if hits:
            buf = io.StringIO()
            csv.writer(buf, lineterminator="\r\n" if "\r\n" in text else "\n").writerows(rows)
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(buf.getvalue())
            done.append((fname, label, col, f"{_fmt(base[1])} → {_fmt(next(iter(news)))}", hits))
    return done


def _fmt(v):
    return f"{int(float(v)):,}"


def changes_table(groups=("harvest", "mill")):
    lines = ["| ファイル | 変える行 | 列 | 前 → 後 | 行数 |", "|---|---|---|---|---:|"]
    for group, fname, cond, base, expected, _n, label in CHANGES:
        if group in groups and expected:
            new = int(Fraction(base[1]) * FACTOR)
            lines.append(f"| `{fname}` | {label} | `{base[0]}` | {base[1]:,} → {new:,}（×1.3） | {expected} |")
    return "\n".join(lines)


def build(out_dir, base_dir=BASE_DIR):
    os.makedirs(out_dir, exist_ok=True)
    built = {}
    for name, title, groups in VARIANTS:
        d = os.path.join(out_dir, name)
        if os.path.exists(d):
            shutil.rmtree(d)
        shutil.copytree(base_dir, d, ignore=shutil.ignore_patterns("__pycache__", "_ppc"))
        apply_changes(d, groups)
        readme = os.path.join(d, "README.md")
        with open(readme, encoding="utf-8") as f:
            orig = f.read()
        head = (f"# {title}\n\n**授業の比較モデル。基準からの変更は次のとおり。**"
                f"（基準：`data/sample/{BASE_NAME}`。`tools/lesson000_variants.py` が作った。"
                "上位の層とエンジンの両方の上限を揃えて変える。ほかの値は基準のまま）\n\n"
                + changes_table(groups) + "\n\n---\n\n（以下は基準のモデルの README のまま）\n\n")
        with open(readme, "w", encoding="utf-8", newline="\n") as f:
            f.write(head + orig)
        built[name] = d
        print(f"[lesson000] built {d}")
    return built


# ── run and summarize ───────────────────────────────────────────────────
RAW_KG_PER_LOT = Fraction(3000) / Fraction(9, 10)
REPORT_YEARS = ("2027", "2028")
MARKETS = ("KANTO", "TOHOKU", "KANSAI", "KYUSHU")
MARKET_JA = {"KANTO": "関東", "TOHOKU": "東北", "KANSAI": "関西", "KYUSHU": "九州"}


def _mill_caps(model_dir):
    with open(os.path.join(model_dir, "rice_resources.csv"), encoding="utf-8") as f:
        return {r["resource_id"]: float(r["default_capacity"]) for r in csv.DictReader(f)
                if r["resource_id"] in ("MILL_E", "MILL_W")}


def collect(res_dir, model_dir):
    S = json.load(open(os.path.join(res_dir, "summary.json"), encoding="utf-8"))
    m = S["market"]
    o = {"checks": {"flow_identity_errors": sum(S["flow_identity_errors"].values()) if S["flow_identity_errors"] else 0,
                    "resource_over_capacity": len(S["resource_over_capacity"]),
                    "early_ids": S["early_ids"],
                    "route_trace_mismatch": sum(S["route_trace_mismatch"].values()) if S["route_trace_mismatch"] else 0,
                    "layer_vs_actual_mismatch": m.get("layer_vs_actual_mismatch", 0),
                    "mass_balanced": bool(S["mass_balance"]["balanced"])}}
    for p in ("Koshihikari", "Yumepirika"):
        o[p] = {s: m.get(f"{p}|report|{s}", 0) for s in ("on_time", "late", "early", "backlog_end")}
    back = Counter()
    with gzip.open(os.path.join(res_dir, "market_ids.csv.gz"), "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["period"] == "report" and r["product"] == "Koshihikari" and r["status"] == "backlog_end":
                back[r["market"].replace("Retail_", "")] += 1
    o["market_backlog"] = {k: back[k] for k in MARKETS}
    zero = defaultdict(list)
    with open(os.path.join(res_dir, "weekly_market.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["product"] != "Koshihikari" or r["request_week"][:4] not in REPORT_YEARS:
                continue
            if int(r["on_time"]) == 0 and sum(int(r[k]) for k in ("late", "early", "backlog_end")):
                zero[r["request_week"][:4]].append(r["request_week"][5:])
    o["zero_weeks"] = {y: zero[y] for y in REPORT_YEARS}
    caps = _mill_caps(model_dir)
    mill, peak = defaultdict(list), (0.0, "")
    with open(os.path.join(res_dir, "resource_usage.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            lots = float(Fraction(r["kg_actual"]) / RAW_KG_PER_LOT)
            if r["resource_id"] in caps and r["week"][:4] in REPORT_YEARS:
                mill[r["resource_id"]].append(lots)
            if r["resource_id"] == "BROWN_STORE_NIIGATA|peak" and lots > peak[0]:
                peak = (lots, r["week"])
    o["mill"] = {k: {"cap": caps[k], "max": max(v), "weeks_at_cap": sum(1 for x in v if x >= caps[k] - 0.5)}
                 for k, v in mill.items()}
    o["brown_peak"] = peak
    o["crop"] = {r["crop_season"]: (int(r["harvested_lots"]), float(r["limit_lots"]))
                 for r in S["crop_year"] if r["resource_id"] == "FIELD_NIIGATA"}
    return o


def check_ok(o):
    c = o["checks"]
    return (c["flow_identity_errors"] == 0 and c["resource_over_capacity"] == 0 and c["early_ids"] == 0
            and c["route_trace_mismatch"] == 0 and c["layer_vs_actual_mismatch"] == 0 and c["mass_balanced"])


def _weeks(ws):
    if not ws:
        return "なし"
    return f"{ws[0]}〜{ws[-1]}（{len(ws)} 週）" if len(ws) > 1 else ws[0]


def summary_md(res, labels, cmd_note):
    names = list(res)
    col = lambda f: " | ".join(f(res[n]) for n in names)
    L = ["# Lesson 000 — 比較モデルの結果", "",
         f"`python -m tools.lesson000_variants --run` が作った表（{cmd_note}）。"
         f"モデルは架空のサンプル `data/sample/{BASE_NAME}` と、そこから作った比較モデル 3 つ。", "",
         "範囲：「報告期間」＝2027-W01〜2028-W52 に要求週がある市場の要求。「当週出荷」＝要求週に出荷された lot。"
         "「注文残」＝計画期間の終わりにまだ出荷されていない lot。精米の使用は lot（玄米 3,333.3 kg＝精米 3 t）に換算。", "",
         "## 照合", "",
         "| 検査 | " + " | ".join(labels[n] for n in names) + " |", "|---|" + "---:|" * len(names),
         "| flow identity の誤り | " + col(lambda o: str(o["checks"]["flow_identity_errors"])) + " |",
         "| 資源・年産上限の超過 | " + col(lambda o: str(o["checks"]["resource_over_capacity"])) + " |",
         "| 早出し | " + col(lambda o: str(o["checks"]["early_ids"])) + " |",
         "| 経路の照合・上位の層と実出荷の不一致 | " + col(lambda o: str(o["checks"]["route_trace_mismatch"] + o["checks"]["layer_vs_actual_mismatch"])) + " |",
         "| 物量の保存（玄米＝精米＋その他） | " + col(lambda o: "合" if o["checks"]["mass_balanced"] else "否") + " |", "",
         "## 並べる表", "",
         "| 項目 | " + " | ".join(labels[n] for n in names) + " |", "|---|" + "---:|" * len(names)]
    k = lambda o: o["Koshihikari"]
    L.append(f"| コシヒカリ・報告期間の当週出荷／注文残（要求 {k(res[names[0]])['on_time'] + k(res[names[0]])['backlog_end'] + k(res[names[0]])['late']:,}） | "
             + col(lambda o: f"{k(o)['on_time']:,}／{k(o)['backlog_end']:,}") + " |")
    L.append("| 全品目・報告期間の注文残 | " + col(lambda o: f"{k(o)['backlog_end'] + o['Yumepirika']['backlog_end']:,}") + " |")
    L.append("| 遅配・早出し（コシヒカリ・報告期間） | " + col(lambda o: f"{k(o)['late']}・{k(o)['early']}") + " |")
    for mk in MARKETS:
        L.append(f"| コシヒカリ・報告期間の注文残：{MARKET_JA[mk]} | " + col(lambda o, mk=mk: f"{o['market_backlog'][mk]:,}") + " |")
    for y in REPORT_YEARS:
        L.append(f"| コシヒカリ・当週の出荷が 0 の要求週：{y} 年 | " + col(lambda o, y=y: _weeks(o["zero_weeks"][y])) + " |")
    for mid, ja in (("MILL_E", "東"), ("MILL_W", "西")):
        L.append(f"| 精米センター{ja}（{mid}）の使用の最大／上限に当たった週（2027〜2028、両品目） | "
                 + col(lambda o, mid=mid: f"{o['mill'][mid]['max']:,.0f}／{o['mill'][mid]['weeks_at_cap']} 週（上限 {o['mill'][mid]['cap']:,.0f}）") + " |")
    for season in sorted(res[names[0]]["crop"]):
        L.append(f"| 新潟の {season} 年産の収穫／上限（lot） | "
                 + col(lambda o, s=season: f"{o['crop'][s][0]:,}／{o['crop'][s][1]:,.0f}") + " |")
    L.append("| 新潟の玄米倉庫の週内のピーク（lot、全期間） | "
             + col(lambda o: f"{o['brown_peak'][0]:,.0f}（{o['brown_peak'][1]}）") + " |")
    L += ["", "注：精米の上限 0 の休業週（GW）は数えていない。玄米倉庫のピーク＝前週末の在庫＋当週の受入れ。"
          "2028 年産は、計画期間の中で要求があるのは W46 以降だけなので、上限まで使わない。", "",
          "## 比較モデルの変える値", "", changes_table(), ""]
    return "\n".join(L)


def run_all(models, out_results, summary_path):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    dirs = {"base": BASE_DIR, **models}
    labels = {"base": "基準"}
    labels.update({n: t.replace("（二品目で共用）", "") for n, t, _g in VARIANTS})
    res = {}
    for name, d in dirs.items():
        out = os.path.join(out_results, name)
        os.makedirs(out, exist_ok=True)
        t0 = time.time()
        with open(os.path.join(out, "run.log"), "w", encoding="utf-8") as log:
            r = subprocess.run([sys.executable, "-m", "tools.rice_seasonal_check", "--model-dir", d, "--out", out],
                               cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
        print(f"[lesson000] ran {name}: exit {r.returncode}, {time.time() - t0:.0f} s", flush=True)
        if r.returncode != 0:
            raise SystemExit(f"[lesson000] rice_seasonal_check failed for {name}; see {out}/run.log")
        res[name] = collect(out, d)
        if not check_ok(res[name]):
            raise SystemExit(f"[lesson000] the checks failed for {name}: {res[name]['checks']} -- no table written")
    with open(os.path.join(out_results, "collected.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    os.makedirs(os.path.dirname(os.path.abspath(summary_path)), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(summary_md(res, labels, time.strftime("%Y-%m-%d")))
    print(f"[lesson000] wrote {summary_path}")
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build (and run) the Lesson 000 comparison models.")
    ap.add_argument("--out", default=OUT_MODELS, help="folder for the 3 models (default output/lesson000/models)")
    ap.add_argument("--run", action="store_true", help="also run base + 3 and write the table")
    ap.add_argument("--results", default=OUT_RESULTS, help="folder for the raw results (default output/lesson000/results)")
    ap.add_argument("--summary", default=None, help="table path (default <results>/summary.md)")
    ap.add_argument("--list", action="store_true", help="print the table of changed values only")
    a = ap.parse_args(argv)
    if a.list:
        for name, title, groups in VARIANTS:
            print(f"\n## {name}：{title}\n")
            print(changes_table(groups))
        return 0
    models = build(os.path.abspath(a.out))
    if a.run:
        run_all(models, os.path.abspath(a.results), os.path.abspath(a.summary or os.path.join(a.results, "summary.md")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
