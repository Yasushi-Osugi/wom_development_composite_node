# -*- coding: utf-8 -*-
"""
為替（RequestLetter_StageD_Phase1 §1-6、設計 §5.4、判断 d）

- 表は `ppc_fx_rate.csv`（week, currency, base_currency, rate：currency 1 単位 = rate 基準通貨）。
  モデルに無ければ `data/ppc/ppc_fx_rate.csv`（どちらを使ったかを記録）。Landed Cost の
  `edge_cost_master.csv` の fx_rate は使わない。
- 2 つの通貨の間は基準通貨を経由する：X→Y = (X→基準) ÷ (Y→基準)。これで同じ週の
  EUR→USD→JPY と EUR→JPY が一致する。同じ通貨どうしは 1（換算ではない）。
- 表の最初の週より前（助走週）：最初の週のレートを使い、記録する（判断 d）。
- 表の最後の週より後、表の範囲の中で週が抜けている、通貨そのものが無い：未評価（NaN）。
  記録する。**黙って 1 にしない。前の週への退避もしない。**
"""
from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

import pandas as pd

NAN = float("nan")

M_SAME = "same_currency"
M_TABLE = "table_week"
M_FIRST = "first_week_rate_before_table"      # decision d
M_MISSING = "missing_unvalued"


class FxTable:
    def __init__(self, df: pd.DataFrame, source: str):
        self.source = source
        bases = sorted({str(b) for b in df["base_currency"].dropna()})
        if len(bases) != 1:
            raise ValueError(f"ppc_fx_rate.csv ({source}) must have exactly one base_currency, got {bases}")
        self.base = bases[0]
        self._rate: Dict[Tuple[str, str], float] = {}
        self._weeks: Dict[str, List[str]] = {}
        for r in df.itertuples(index=False):
            v = float(r.rate)
            if not (v > 0) or math.isnan(v):
                raise ValueError(f"ppc_fx_rate.csv ({source}): rate must be > 0 "
                                 f"({r.week} {r.currency}: {r.rate})")
            self._rate[(str(r.week), str(r.currency))] = v
            self._weeks.setdefault(str(r.currency), []).append(str(r.week))
        for c in self._weeks:
            self._weeks[c] = sorted(set(self._weeks[c]))
        self.log: Dict[tuple, dict] = {}     # aggregated log rows

    @classmethod
    def load(cls, model_dir: str, fallback_dir: str = os.path.join("data", "ppc")) -> "FxTable":
        p = os.path.join(model_dir, "ppc_fx_rate.csv")
        src = "model"
        if not os.path.exists(p):
            p = os.path.join(fallback_dir, "ppc_fx_rate.csv")
            src = "data/ppc (fallback)"
        t = cls(pd.read_csv(p, dtype={"week": str, "currency": str, "base_currency": str}), f"{src}: {p}")
        return t

    def currencies(self) -> List[str]:
        return sorted(set(self._weeks) | {self.base})

    def _to_base(self, ccy: str, week: str) -> Tuple[float, str, str]:
        """(rate ccy->base, method, week used)."""
        if ccy == self.base:
            return 1.0, M_SAME, week
        weeks = self._weeks.get(ccy)
        if not weeks:
            return NAN, M_MISSING, ""
        v = self._rate.get((week, ccy))
        if v is not None:
            return v, M_TABLE, week
        if week < weeks[0]:
            return self._rate[(weeks[0], ccy)], M_FIRST, weeks[0]
        return NAN, M_MISSING, ""

    def rate(self, src: str, dst: str, week: str, context: str = "") -> Tuple[float, str]:
        """(rate src->dst for the week, method). NaN when not available (logged)."""
        if src == dst:
            return 1.0, M_SAME
        a, ma, wa = self._to_base(src, week)
        b, mb, wb = self._to_base(dst, week)
        method = M_TABLE
        for m in (ma, mb):
            if m == M_MISSING:
                method = M_MISSING
            elif m == M_FIRST and method != M_MISSING:
                method = M_FIRST
        if method != M_TABLE:
            key = (method, src, dst, week, wa if ma == M_FIRST else wb if mb == M_FIRST else "")
            rec = self.log.get(key)
            if rec is None:
                rec = {"method": method, "from_currency": src, "to_currency": dst,
                       "requested_week": week, "used_week": key[4], "count": 0,
                       "context": context, "table": self.source}
                self.log[key] = rec
            rec["count"] += 1
        if method == M_MISSING:
            return NAN, method
        return a / b, method

    def log_rows(self) -> List[dict]:
        return sorted(self.log.values(), key=lambda r: (r["method"], r["requested_week"],
                                                         r["from_currency"], r["to_currency"]))
