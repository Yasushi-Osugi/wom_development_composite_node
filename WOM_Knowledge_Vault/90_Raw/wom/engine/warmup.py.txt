# -*- coding: utf-8 -*-
"""
wom/engine/warmup.py — Planning Warm-up 行の materialize（案B-safe）
===================================================================
計画期間の助走区間（Planning Warm-up Period、横軸の前倒し）を、per-model の
`planning_config.csv`（`warmup_lt` / `planning_start`）に基づいて週次CSVへ materialize する。

設計文書：`requests/planning-horizon-warmup-parameter-request-letter.md`
関連：`docs/design/planning_warmup_and_reporting_horizon.md` §5–7・§13、同 §9.5。

確定した設計（同 letter D1–D3・§5.2 案B-safe）:
  - D1 埋め方：demand は助走週=quantity 0（W1コピー禁止）。capacity_plan / operating_calendar は
       各 node の「最初の実週（＝最初の非ゼロ需要週）」の値を後方コピー。holiday/ppc 等は対象外。
  - D2 パラメータ：`warmup_lt`（週数、既定0）が主。`planning_start`（週ラベル）は任意 override。
       effective_start = planning_start 指定あり: min(planning_start, real_start)
                         warmup_lt>0          : real_start − warmup_lt
                         それ以外              : real_start（助走なし）
  - D3 materialize：CSV に書く。生成物と原本の区別は「最初の“非ゼロ”需要週(real_start)より前の週の行」。
       idempotent（strip→再生成）、byte-stable（同 warmup_lt→同バイト列）、write-if-needed（整合なら書かない）。

冪等性＝この strip→再生成アルゴリズムが担保（サマリー出力ではない）。
監査性（durable）＝コミット済みの生成後CSV＋golden。サマリー＝実行時の観測性の層。

backward-compat：`planning_config.csv` が無く、かつ引数指定も無ければ**完全 no-op**（ファイルに触れない）。
→ 既存ケース（config 無し）は挙動不変・golden 緑。

`cpu_size`（Request Letter A: request_letter_a_cpu_size_to_plan.md）：
    同じ `planning_config.csv` の `cpu_size` キー（既定 1）。`warmup_lt`/`planning_start`
    と異なり CSV を書き換える materialize 処理は無く、`read_cpu_size()` で読んだ値を
    呼び出し元（app.py / run_headless_from_folder.py / sweep_flags.py）が
    `SCTree.cpu_size` へその都度代入する（計画全体で1つの値、ノード単位ではない）。
"""
from __future__ import annotations

import csv
import datetime
import io
import os
import re
from typing import List, Optional, Tuple

# materialize 対象の週次CSVと、その扱い
_DEMAND = "demand_forecast.csv"       # 助走週 = quantity 0
_CAPACITY = "capacity_plan.csv"       # 助走週 = node の最初の実週値を後方コピー
_OPCAL = "operating_calendar.csv"     # 助走週 = node の最初の実週 shift を後方コピー
_CONFIG = "planning_config.csv"

_WARMUP_TAG = "warmup"                # capacity_plan.source に入れる可読マーカー（任意）


# ──────────────────────────────────────────────────────────────────────
# ISO 週ユーティリティ（エンジンと同じ date.fromisocalendar 系）
# ──────────────────────────────────────────────────────────────────────
def _parse_week(label: str) -> datetime.date:
    m = re.match(r"(\d{4})-W(\d+)", label.strip())
    if not m:
        raise ValueError(f"invalid ISO week label: {label!r}")
    return datetime.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)


def _fmt_week(d: datetime.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def weeks_between(start: str, end_exclusive: str) -> List[str]:
    """[start, end_exclusive) の ISO 週ラベル（古い順）。年跨ぎ（W53）も正しく扱う。"""
    d = _parse_week(start)
    out: List[str] = []
    while _fmt_week(d) < end_exclusive:
        out.append(_fmt_week(d))
        d += datetime.timedelta(weeks=1)
    return out


def week_minus(label: str, n: int) -> str:
    """label の n 週前の ISO ラベル。"""
    if n <= 0:
        return label
    return _fmt_week(_parse_week(label) - datetime.timedelta(weeks=n))


def resolve_effective_start(real_start: str, warmup_lt: int, planning_start: str) -> str:
    """D2 の導出。real_start は「最初の非ゼロ需要週」。"""
    if planning_start:
        return min(planning_start, real_start)   # 既存の早いデータを失わない防御
    if warmup_lt and warmup_lt > 0:
        return week_minus(real_start, warmup_lt)
    return real_start


# ──────────────────────────────────────────────────────────────────────
# CSV 低レベル（行を verbatim 保持して byte-stable にする）
# ──────────────────────────────────────────────────────────────────────
def _read_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]        # 末尾改行由来の空要素を除去
    return lines


def _parse(line: str) -> List[str]:
    return next(csv.reader(io.StringIO(line)))


def _col(header_fields: List[str], name: str) -> int:
    return header_fields.index(name)


# ──────────────────────────────────────────────────────────────────────
# config 読み取り
# ──────────────────────────────────────────────────────────────────────
def read_planning_config(model_dir: str) -> Tuple[Optional[int], str]:
    """planning_config.csv（key,value）→ (warmup_lt or None, planning_start)。
    ファイルが無ければ (None, "")。"""
    path = os.path.join(model_dir, _CONFIG)
    if not os.path.exists(path):
        return None, ""
    warmup_lt: Optional[int] = None
    planning_start = ""
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            k = (row.get("key") or "").strip()
            v = (row.get("value") or "").strip()
            if k == "warmup_lt":
                warmup_lt = int(v) if v != "" else 0
            elif k == "planning_start":
                planning_start = v
    return warmup_lt, planning_start


def read_cpu_size(model_dir: str) -> int:
    """
    planning_config.csv（key,value）の cpu_size キーを読む（Request Letter A:
    request_letter_a_cpu_size_to_plan.md）。

    cpu_size is a plan-wide Common Planning Unit -- every node in a plan is
    meant to share one value, so (unlike warmup_lt/planning_start, which are
    read once and consumed immediately by materialize_warmup) it is exposed
    as its own function for callers to assign onto SCTree.cpu_size once per
    planning run (see wom.model.sc_tree.SCTree.__init__).

    既定 1（ファイルが無い場合・キーが無い場合・値が空の場合のいずれも）。
    既存モデルとの後方互換を保つための既定値であり、意図的な設計。
    """
    path = os.path.join(model_dir, _CONFIG)
    if not os.path.exists(path):
        return 1
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            k = (row.get("key") or "").strip()
            v = (row.get("value") or "").strip()
            if k == "cpu_size":
                return int(v) if v != "" else 1
    return 1


def first_nonzero_demand_week(demand_path: str) -> Optional[str]:
    """demand_forecast.csv の「最初の“非ゼロ”需要週」（＝real_start）。全ゼロ/空なら None。"""
    lines = _read_lines(demand_path)
    if len(lines) < 2:
        return None
    hf = _parse(lines[0])
    wi, qi = _col(hf, "week"), _col(hf, "quantity")
    weeks = []
    for ln in lines[1:]:
        f = _parse(ln)
        try:
            q = float(f[qi])
        except (ValueError, IndexError):
            q = 0.0
        if q != 0.0:
            weeks.append(f[wi])
    return min(weeks) if weeks else None   # "YYYY-WNN" は辞書順＝時系列順


# ──────────────────────────────────────────────────────────────────────
# 各CSVの新内容を構築（strip week<real_start → warm 行を先頭に prepend）
# ──────────────────────────────────────────────────────────────────────
def _rebuild(path: str, real_start: str, warm_weeks: List[str], kind: str) -> Tuple[str, int]:
    """(new_content, warm_row_count) を返す。実データ行は verbatim 保持。"""
    lines = _read_lines(path)
    header = lines[0]
    hf = _parse(header)
    wi = _col(hf, "week")

    kept: List[str] = []
    first_week_rows: List[List[str]] = []
    for ln in lines[1:]:
        f = _parse(ln)
        wk = f[wi]
        if wk >= real_start:            # 実データ（verbatim 保持）
            kept.append(ln)
            if wk == real_start:
                first_week_rows.append(f)
        # wk < real_start は既存の助走行 → strip（＝落とす）

    warm_lines = _build_warm_lines(kind, hf, first_week_rows, warm_weeks)
    new_content = "\n".join([header] + warm_lines + kept) + "\n"
    return new_content, len(warm_lines)


def _build_warm_lines(kind: str, hf: List[str], first_week_rows: List[List[str]],
                      warm_weeks: List[str]) -> List[str]:
    """D1 の埋め方でCSV種別ごとに助走行（文字列）を生成。決定的な並び順で byte-stable。"""
    if not warm_weeks:
        return []

    if kind == "demand":
        wi, qi = _col(hf, "week"), _col(hf, "quantity")
        si, ri = _col(hf, "sku_id"), _col(hf, "region")
        # 最初の実週に存在する (sku, region) を対象にゼロ需要行を生成
        pairs = sorted({(r[si], r[ri]) for r in first_week_rows})
        out = []
        for wk in warm_weeks:
            for sku, region in pairs:
                row = [""] * len(hf)
                row[si], row[ri], row[wi], row[qi] = sku, region, wk, "0"
                out.append(",".join(row))
        return out

    if kind == "capacity":
        wi = _col(hf, "week")
        si, ni, mi = _col(hf, "sku_id"), _col(hf, "node_name"), _col(hf, "max_supply")
        srci = hf.index("source") if "source" in hf else None
        # (sku, node) -> max_supply（最初の実週値）
        snap = {}
        for r in first_week_rows:
            snap[(r[si], r[ni])] = r[mi]
        out = []
        for wk in warm_weeks:
            for (sku, node) in sorted(snap):
                row = [""] * len(hf)
                row[si], row[ni], row[wi], row[mi] = sku, node, wk, snap[(sku, node)]
                if srci is not None:
                    row[srci] = _WARMUP_TAG
                out.append(",".join(row))
        return out

    if kind == "opcal":
        wi = _col(hf, "week")
        si, ni, shi = _col(hf, "sku_id"), _col(hf, "node_name"), _col(hf, "shifts")
        snap = {}
        for r in first_week_rows:
            snap[(r[si], r[ni])] = r[shi]
        out = []
        for wk in warm_weeks:
            for (sku, node) in sorted(snap):
                row = [""] * len(hf)
                row[si], row[ni], row[wi], row[shi] = sku, node, wk, snap[(sku, node)]
                out.append(",".join(row))
        return out

    raise ValueError(f"unknown kind: {kind}")


# ──────────────────────────────────────────────────────────────────────
# 公開 API
# ──────────────────────────────────────────────────────────────────────
def materialize_warmup(
    model_dir: str,
    warmup_lt: Optional[int] = None,
    planning_start: Optional[str] = None,
    write: bool = True,
    demand_file: str = _DEMAND,
) -> dict:
    """
    planning_config.csv（または明示引数）に基づき助走行を materialize する。

    Args:
        demand_file: 需要 CSV のファイル名（既定 "demand_forecast.csv"）。
            Phase 7（`requests/Phase7_RequestLetter_to_CodeKun.md` V2.4）：
            `run_headless_from_folder.run(demand_file=...)` で差し替えた需要 CSV
            （例 `demand_forecast_A03.csv`）を warmup 側にも同じ値で渡すこと。
            ここだけ既定値のまま呼ぶと、「需要は差し替わったのに warmup だけ
            元の demand_forecast.csv を見る」という噛み合わせのズレが起きる
            （Phase 6 で複数回踏んだ、2箇所に分かれた設定が片方だけ更新される形）。

    Returns（サマリー dict、stdout 出力・テスト・呼び出し側の判定に使う）:
      {
        "skipped": bool,          # config も引数も無く no-op
        "changed": bool,          # いずれかのファイルを書き換えた（write=False でも「差分あり」を示す）
        "warmup_lt": int,
        "planning_start": str,
        "real_start": str|None,   # 最初の非ゼロ需要週
        "effective_start": str|None,
        "warm_weeks": int,        # 生成した助走週数
        "files": {name: {"warm_rows": int, "changed": bool}},
      }
    """
    cfg_lt, cfg_ps = read_planning_config(model_dir)
    # 引数優先。両方 None かつ config 無し → 完全 no-op（既存ケース保護）。
    if warmup_lt is None and planning_start is None and cfg_lt is None and not cfg_ps:
        return {"skipped": True, "changed": False, "warmup_lt": 0, "planning_start": "",
                "real_start": None, "effective_start": None, "warm_weeks": 0, "files": {}}

    eff_lt = warmup_lt if warmup_lt is not None else (cfg_lt or 0)
    eff_ps = planning_start if planning_start is not None else cfg_ps

    dem_path = os.path.join(model_dir, demand_file)
    real_start = first_nonzero_demand_week(dem_path)
    if real_start is None:
        return {"skipped": True, "changed": False, "warmup_lt": eff_lt, "planning_start": eff_ps,
                "real_start": None, "effective_start": None, "warm_weeks": 0, "files": {}}

    effective_start = resolve_effective_start(real_start, eff_lt, eff_ps)
    warm_weeks = weeks_between(effective_start, real_start)

    summary = {
        "skipped": False, "changed": False, "warmup_lt": eff_lt, "planning_start": eff_ps,
        "real_start": real_start, "effective_start": effective_start,
        "warm_weeks": len(warm_weeks), "files": {},
    }

    targets = [(demand_file, "demand"), (_CAPACITY, "capacity"), (_OPCAL, "opcal")]
    for fname, kind in targets:
        path = os.path.join(model_dir, fname)
        if not os.path.exists(path):
            continue
        new_content, n_warm = _rebuild(path, real_start, warm_weeks, kind)
        with open(path, "r", encoding="utf-8") as f:
            cur = f.read()
        changed = new_content != cur
        if changed and write:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new_content)
        summary["files"][fname] = {"warm_rows": n_warm, "changed": changed}
        summary["changed"] = summary["changed"] or changed

    return summary


def format_summary(summary: dict) -> str:
    """サマリーの1行ブロック（stdout 用）。"""
    if summary.get("skipped"):
        return "[warmup] no planning_config / no demand -> skipped (no change)"
    if not summary.get("changed"):
        return (f"[warmup] already up to date (no change) "
                f"| effective_start={summary['effective_start']} warmup_lt={summary['warmup_lt']}")
    parts = [f"[warmup] materialized"]
    parts.append(f"effective_start={summary['effective_start']}")
    parts.append(f"warmup_lt={summary['warmup_lt']} weeks={summary['warm_weeks']}")
    for fname, info in summary["files"].items():
        if info["changed"]:
            parts.append(f"{fname}:+{info['warm_rows']}")
    return " | ".join(parts)
