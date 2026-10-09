"""
wom/engine/report_start.py — the first week of the reporting period, in ONE place
（RequestLetter_RiceSeasonal_PolishAdvance1 作業 5）

The reporting period starts at ``report_start`` in the model's ``vc_config.csv``
(key,value). Without that value it starts at the first nonzero demand week.
Used by the World Map (wom/worldmap_ne/flows.report_start_index), the Rice
upper layer (wom/capacity_layer/rice_seasonal.load_inputs) and Flow Check;
Value Chain reads the same key through its masters. Do not keep the same
value in a second file.
"""
from __future__ import annotations

import csv
import os
from typing import List, Optional, Tuple

FALLBACK_SOURCE = "最初の非ゼロ需要週"


def read_report_start(model_dir: str) -> Tuple[Optional[str], str]:
    """(week label or None, source) -- vc_config.csv report_start, else the first
    nonzero demand week (None when the demand file has no nonzero week)."""
    cfg = os.path.join(model_dir, "vc_config.csv")
    if os.path.exists(cfg):
        with open(cfg, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("key") or "").strip() == "report_start" and (r.get("value") or "").strip():
                    return r["value"].strip(), "vc_config.csv"
    from wom.engine.warmup import first_nonzero_demand_week
    return first_nonzero_demand_week(os.path.join(model_dir, "demand_forecast.csv")), FALLBACK_SOURCE


def configured_report_start(model_dir: str, week_labels: List[str]) -> Optional[Tuple[int, str]]:
    """(index, week label) when the model SETS report_start in vc_config.csv and the
    week is in the plan; None otherwise (the model has no separate reporting period)."""
    rs, src = read_report_start(model_dir)
    if src == "vc_config.csv" and rs in week_labels:
        return week_labels.index(rs), rs
    return None


def report_start_index(model_dir: str, week_labels: List[str]) -> Tuple[int, str]:
    """(index into week_labels, source); 0 when the week is not in the plan."""
    rs, src = read_report_start(model_dir)
    if rs in week_labels:
        return week_labels.index(rs), src
    return 0, "（報告の開始週が計画の週に無いので、最初の週から）"
