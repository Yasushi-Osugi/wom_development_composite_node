# -*- coding: utf-8 -*-
"""
tools/strategy_convert.py — 施策シートを 1 つの案の入力に変換する（画面なし）
============================================================================
RequestLetter_Promo_Convert_Slice1 §4。wom/strategy/convert.py を呼ぶだけ。

    python -m tools.strategy_convert --ws <作業> --case C02 --plan P_PROMO_LOW \
        --sheets <シートのフォルダ> --base-model data/sample/cosmetics-sg-th-2027-2029 [--dry-run]

--dry-run は書かずに、書く予定の変更（変更記録と同じ形）を出す。
終了コード：0 成功（変換した・変更なし・dry-run）、2 止めた（理由を出す。何も書いていない）。
"""
from __future__ import annotations

import argparse
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from wom.cockpit import cases as C            # noqa: E402
from wom.strategy import StrategyError        # noqa: E402
from wom.strategy import convert as CV        # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Convert a strategy measure sheet into a cockpit case")
    ap.add_argument("--ws", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--sheets", required=True)
    ap.add_argument("--base-model", required=True)
    ap.add_argument("--catalog", default=None, help="type catalog (default: wom/strategy/measure_type_catalog.csv)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        pc = CV.convert(a.ws, a.case, a.plan, a.sheets, a.base_model, dry_run=a.dry_run, catalog_path=a.catalog)
    except (StrategyError, C.CaseError) as e:
        print(f"[strategy_convert] 止めました（何も書いていません）: {e}", file=sys.stderr)
        return 2
    print(f"[strategy_convert] {a.case} ← {a.plan}：{pc['state']}（型カタログ {pc['catalog']['version']}）")
    for s in pc["summary"]:
        print(f"  需要 {s['key']}：水準 {s['level']}（率 {s['rate']}）、反応 {s['response_weeks']}、"
              f"追加 {s['added_lots']} lot・減 {s['removed_lots']} lot、未反映の端数 {s['residuals']}")
    for r in pc["cost"]["new"]:
        print(f"  費用の前提 {r['cost_item']}（{r['entity']}）：{r['paid_start_week']}〜{r['paid_end_week']} "
              f"週 {r['weekly_amount']} {r['currency']}")
    if a.dry_run:
        print(pc["log_text"], end="")
    else:
        print(f"  変更記録 -> {pc['log_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
