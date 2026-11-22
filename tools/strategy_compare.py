# -*- coding: utf-8 -*-
"""
tools/strategy_compare.py — 変換した案を並べる（P0・追加費用・控除後の比較値・①〜⑤・波及・押し戻し）
======================================================================================================
RequestLetter_Promo_Convert_Slice1 §4・§5。wom/strategy/compare.py を呼ぶだけ。

    python -m tools.strategy_compare --ws <作業> --base C01 --cases C02,C03,C04 \
        [--sku COS_Cream --market SG_EC] [--out <フォルダ>] [--no-overflow]

出力（既定 <作業>/strategy_compare/<案>/）：strategy_summary.csv・strategy_summary.md・
fulfillment_by_key.csv・overflow_by_factory_market.csv（と compare/<基準>__<案>/ の比較の道具の出力）。
終了コード：0 成功、2 止めた（理由を出す）。
"""
from __future__ import annotations

import argparse
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from wom.cockpit import cases as C            # noqa: E402
from wom.cockpit import case_runner as R      # noqa: E402
from wom.strategy import StrategyError        # noqa: E402
from wom.strategy import compare as SC        # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Summarise converted strategy cases")
    ap.add_argument("--ws", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--cases", required=True, help="C02,C03,C04")
    ap.add_argument("--sku", default="COS_Cream")
    ap.add_argument("--market", default="SG_EC")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-overflow", action="store_true", help="skip the push-back record (one plan run per case)")
    a = ap.parse_args(argv)
    from tools.period_fulfillment import StopError
    try:
        res = SC.compare_plans(a.ws, a.base, [c.strip() for c in a.cases.split(",") if c.strip()], a.sku, a.market,
                               a.out, overflow=not a.no_overflow)
    except (StrategyError, C.CaseError, StopError) as e:
        print(f"[strategy_compare] 止めました: {e}", file=sys.stderr)
        return 2
    except R.StageStop as e:
        print(f"[strategy_compare] {e.state}: {e.message}", file=sys.stderr)
        return 2
    for r in res["summary"].itertuples():
        print(f"  {r.case} {r.case_name}: P0 {r.P0:,.0f}  B_add {r.B_add:,.0f}  A {r.A:,.0f}  ΔA {r.dA_vs_base:+,.0f}  "
              f"①{r.q1} ④{r.q4_delivered} ⑤{r.q5}  押し戻し {r.overflow_pushed_total}  エンジン {r.engine_vs_base}")
    print(f"  -> {res['dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
