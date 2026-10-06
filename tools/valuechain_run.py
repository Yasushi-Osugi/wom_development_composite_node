# -*- coding: utf-8 -*-
"""
tools/valuechain_run.py — 段階 D 第 1 回：Value Chain の台帳を作る

    python -m tools.valuechain_run --model-dir data\\sample\\Cookie-jp-2026 --out output\\valuechain\\Cookie-jp-2026\\run_1
    python -m tools.valuechain_run --model-dir data\\sample\\soysauce-jpy-2027-alloc --out output\\valuechain\\alloc\\run_1 --lovem-run output\\lovem\\alloc\\run_A

出力の一覧は wom/valuechain/run.py の説明を見る。モデルのフォルダは一時フォルダに複写して計画するので、
原本には書かない。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Value Chain ledger (stage D, rounds 1 and 2)")
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lovem-run", default=None, help="LOVEM run folder (tools.lovem_observe) to reconcile with")
    ap.add_argument("--plugins", default=None, help="default: the golden's plugins, else 'safe'")
    a = ap.parse_args(argv)
    os.chdir(REPO)
    from wom.valuechain.run import run_valuechain
    t0 = time.perf_counter()
    r = run_valuechain(a.model_dir, a.out, lovem_run=a.lovem_run, plugins=a.plugins)
    c = r["checks"]
    print(f"[valuechain] plan {r['info']['plan_id']}  shipments {r['info']['shipments']:,}  "
          f"report from {r['info']['report_start']}  ({time.perf_counter() - t0:.1f}s)")
    print(f"[valuechain] conservation {'OK' if c['conservation_ok'] else 'NG'}  "
          f"external sales identity {c['external_sales']['ok_identity']} / records x price "
          f"{c['external_sales']['ok_records']}  missing prices {c['missing_price_rows']}  "
          f"fx first-week {c['fx_first_week_rate_uses']}  fx unvalued {c['fx_unvalued_uses']}  "
          f"unvalued lines {c['unvalued_lines']}  issues {len(c['issues'])}")
    u = c["unrealized"]
    if "period" in u:
        pr = u["period"]
        print(f"[valuechain] round 2 (unrealized profit eliminated) {'OK' if u['ok'] else 'NG'}: "
              f"weekly diff {u['weekly_max_abs_diff_hq']:.6g}  period round1 {pr['profit_round1_hq']:,.0f} "
              f"round2 {pr['profit_round2_hq']:,.0f}  unrealized opening {pr['unrealized_opening_hq']:,.0f} "
              f"closing {pr['unrealized_closing_hq']:,.0f}  to unvalued {pr['to_unvalued_in_period_hq']:,.0f}")
    if "lovem" in c:
        lv = c["lovem"]
        print(f"[valuechain] LOVEM {lv['ok']}: matched {lv['matched']:,} / lovem {lv['lovem_actual_ship']:,} "
              f"/ ledger {lv['ledger_shipments']:,}")
    print(f"[valuechain] -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, REPO)
    raise SystemExit(main())
