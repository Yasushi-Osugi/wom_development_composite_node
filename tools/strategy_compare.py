# -*- coding: utf-8 -*-
"""
tools/strategy_compare.py — 変換した案を並べる（P0・追加費用・控除後の比較値・①〜⑤・波及・押し戻し）
======================================================================================================
RequestLetter_Promo_Convert_Slice1 §4・§5。wom/strategy/compare.py を呼ぶだけ。

    python -m tools.strategy_compare --ws <作業> --base C01 --cases C02,C03,C04 \
        [--sku COS_Cream --market SG_EC] [--out <フォルダ>] [--no-overflow] [--weekly 2028-W08 2028-W30]

出力（既定 <作業>/strategy_compare/<案>/）：strategy_summary.csv・strategy_summary.md・
fulfillment_by_key.csv・overflow_by_factory_market.csv（と compare/<基準>__<案>/ の比較の道具の出力）。
--holding-rates 0,0.10 を付けると、年率ごとの在庫の保有費 H と A（＝P0 − 追加費用 − H）の列を足す
（保有費は wom.cockpit.after_cost.case_facts の在庫の連結原価 × 週、助走を含む。Slice 3 §3）。
費用の前提の費目ごとの額（cost_<費目>）はいつも出す。
--avoidable store_operating=1,0.5,0 を付けると、その費目（Value Chain の明細の cost_item）のうち避けられる割合ごとに、
基準との費目の差 × (1 − 割合) を戻した A の列（A_…_avoid<割合>）を足す（割合 1 ＝ 今の A）。
--protect <表> を付けると、守る供給の判定（protect_check.csv：市場ごとの ④ と下限、2029 年の内訳）と両立の必要量
（protect_need.csv）を書く。判定は結果の確かめだけ（Slice 4 §2）。対象の鍵は ④ から需要の増分を引いた値を下限と比べる。
表に任意の列 floor_case（下限の数量を取った案の ID）があれば、引く増分は「その案の増分 − floor_case の増分」
（下限が floor_case の増分を含むため。投入週の 2 本目の補い）。空なら増分を全部引く。
--weekly を付けると、案ごとに weekly_<案>.csv・.md（週別の差。⑤ が出た週は範囲の外でも行を足す）、
market_money_<案>.csv（報告期間の市場別の売上・費用・試算利益）、market_year_<案>.csv（市場 × 要求年の ①・④・⑤）
（RequestLetter_Promo_Convert_Slice2 §3）。
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


def _avoidable(spec):
    """'store_operating=1,0.5,0' -> ('store_operating', [1.0, 0.5, 0.0])."""
    if not spec:
        return None
    if "=" not in spec:
        raise SystemExit("--avoidable は <費目>=<割合,…>（例 store_operating=1,0.5,0）")
    item, rs = spec.split("=", 1)
    ratios = [float(x) for x in rs.split(",") if x.strip()]
    if not item.strip() or not ratios or any(r < 0 or r > 1 for r in ratios):
        raise SystemExit("--avoidable の割合は 0〜1（例 store_operating=1,0.5,0）")
    return item.strip(), ratios


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Summarise converted strategy cases")
    ap.add_argument("--ws", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--cases", required=True, help="C02,C03,C04")
    ap.add_argument("--sku", default="COS_Cream")
    ap.add_argument("--market", default="SG_EC")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-overflow", action="store_true", help="skip the push-back record (one plan run per case)")
    ap.add_argument("--holding-rates", default=None,
                    help="annual holding rates, e.g. 0,0.10 (holding cost and A per rate; 0 = none)")
    ap.add_argument("--avoidable", default=None,
                    help="<cost item>=<ratios>, e.g. store_operating=1,0.5,0 (A per avoidable ratio of that item)")
    ap.add_argument("--protect", default=None,
                    help="protected supply table (sku_id,market,floor_lots,basis,note[,floor_lots_2029][,floor_case])")
    ap.add_argument("--weekly", nargs=2, metavar=("START", "END"), default=None,
                    help="weekly differences for these weeks (and every week with backlog), and market money")
    a = ap.parse_args(argv)
    from tools.period_fulfillment import StopError
    from tools.compare_scenarios import CompareError
    try:
        res = SC.compare_plans(a.ws, a.base, [c.strip() for c in a.cases.split(",") if c.strip()], a.sku, a.market,
                               a.out, overflow=not a.no_overflow, weekly=tuple(a.weekly) if a.weekly else None,
                               holding_rates=([float(x) for x in a.holding_rates.split(",")] if a.holding_rates
                                              else None),
                               avoidable=_avoidable(a.avoidable), protect=a.protect)
    except (StrategyError, C.CaseError, StopError, CompareError) as e:
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
