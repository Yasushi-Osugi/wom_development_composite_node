# -*- coding: utf-8 -*-
"""
tools/cockpit_cases.py — 事業計画の案を作る・複製する・入力を変える・実行する・並べる（画面なし）
================================================================================================
RequestLetter_Cockpit_Stage3_Step1_CasesAndRunner §2.3。wom/cockpit/cases.py・case_runner.py を呼ぶだけ。

    python -m tools.cockpit_cases new     --ws <作業> --model <元のモデル> --max-age-weeks 52 [--name 基準・後期]
    python -m tools.cockpit_cases copy    --ws <作業> --from C01 --name 基準・早期
    python -m tools.cockpit_cases set     --ws <作業> --case C02 entry-plan  --file <market_entry_plan.csv>
    python -m tools.cockpit_cases set     --ws <作業> --case C02 launch-week --sku COS_Cream --region TH_Distributor --week 2027-W27
    python -m tools.cockpit_cases set     --ws <作業> --case C02 planned-output --sku COS_Cream --cap-soft 12 [--node Factory_JP] [--from-week 2028-W11 --to-week 2029-W46]
    python -m tools.cockpit_cases set     --ws <作業> --case C01 capacity    --sku COS_Cream --max-supply 13 --cap-soft 11 [--node …]
    python -m tools.cockpit_cases set     --ws <作業> --case C03 policy      --allocation-file … --policy-file … --week-rule trim_to_capacity_latest [--knowledge-file …] [--unallocated-note …]
    python -m tools.cockpit_cases set     --ws <作業> --case C03 policy      --none
    python -m tools.cockpit_cases set     --ws <作業> --case C01 fixed-cost  --file <表> [--side base|alt]
    python -m tools.cockpit_cases set     --ws <作業> --case C01 fixed-cost  --cost-item … --entity … --paid-start … --paid-end … [--weekly-amount …] --currency JPY [--note …]
    python -m tools.cockpit_cases run     --ws <作業> --case C01 [C02 …]
    python -m tools.cockpit_cases compare --ws <作業> --base C03 --alt C04
    python -m tools.cockpit_cases list    --ws <作業> [--json]
    python -m tools.cockpit_cases status  --ws <作業> --case C01

終了コード：0 成功、2 止めた（入力の誤り・状態）、3 実行が止まった・衝突・未達・不整合（理由は case.json）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from wom.cockpit import cases as C          # noqa: E402
from wom.cockpit import case_runner as R    # noqa: E402


def _print_progress(e: dict) -> None:
    if e["event"] == "start":
        print(f"[{e['case']}] {e['index']}/{e['total']} {e['label']} …", flush=True)
    elif e["event"] == "end":
        print(f"[{e['case']}] {e['index']}/{e['total']} {e['label']} 済み（{e['seconds']:.1f} 秒）", flush=True)
    else:
        print(f"[{e['case']}] {e['label']} で止まった：\n{e['message']}", flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Business plan cases (no screen)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new")
    p.add_argument("--ws", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--max-age-weeks", required=True, type=int)
    p.add_argument("--name", default="基準")

    p = sub.add_parser("copy")
    p.add_argument("--ws", required=True)
    p.add_argument("--from", dest="src", required=True)
    p.add_argument("--name", required=True)

    p = sub.add_parser("set")
    p.add_argument("--ws", required=True)
    p.add_argument("--case", required=True)
    s2 = p.add_subparsers(dest="what", required=True)
    q = s2.add_parser("entry-plan")
    q.add_argument("--file", required=True)
    q = s2.add_parser("launch-week")
    q.add_argument("--sku", required=True)
    q.add_argument("--region", required=True)
    q.add_argument("--week", required=True)
    q = s2.add_parser("planned-output")
    q.add_argument("--sku", required=True)
    q.add_argument("--cap-soft", required=True)
    q.add_argument("--node", default=None)
    q.add_argument("--from-week", default=None, help="first week of the range (with --to-week; default: all weeks)")
    q.add_argument("--to-week", default=None, help="last week of the range (both ends included)")
    q = s2.add_parser("capacity")
    q.add_argument("--sku", required=True)
    q.add_argument("--max-supply", required=True)
    q.add_argument("--cap-soft", required=True)
    q.add_argument("--node", default=None)
    q = s2.add_parser("policy")
    q.add_argument("--none", action="store_true")
    q.add_argument("--allocation-file")
    q.add_argument("--policy-file")
    q.add_argument("--week-rule")
    q.add_argument("--knowledge-file")
    q.add_argument("--unallocated-note")
    q = s2.add_parser("fixed-cost")
    q.add_argument("--file")
    q.add_argument("--side", choices=["base", "alt"])
    q.add_argument("--clear", action="store_true")
    for c in ("cost-item", "entity", "paid-start", "paid-end", "weekly-amount", "currency", "note"):
        q.add_argument(f"--{c}", default=None)

    p = sub.add_parser("run")
    p.add_argument("--ws", required=True)
    p.add_argument("--case", required=True, nargs="+")

    p = sub.add_parser("compare")
    p.add_argument("--ws", required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--alt", required=True)

    p = sub.add_parser("list")
    p.add_argument("--ws", required=True)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("status")
    p.add_argument("--ws", required=True)
    p.add_argument("--case", required=True)

    a = ap.parse_args(argv)
    try:
        if a.cmd == "new":
            cid = C.create_workspace(a.ws, a.model, max_age_weeks=a.max_age_weeks, first_name=a.name)
            print(f"[cockpit_cases] 作業 {a.ws}、最初の案 {cid}（{a.name}）")
        elif a.cmd == "copy":
            cid = C.copy_case(a.ws, a.src, a.name)
            print(f"[cockpit_cases] {a.src} → {cid}（{a.name}）")
        elif a.cmd == "set":
            r = None
            if a.what == "entry-plan":
                r = C.set_entry_plan(a.ws, a.case, a.file)
                r = {"total_lots": r["total_lots"], "rows": r["rows_written"]}
            elif a.what == "launch-week":
                r = C.set_launch_week(a.ws, a.case, a.sku, a.region, a.week)
                r = {"total_lots": r["total_lots"], "totals_by_key": r["totals_by_key"]}
            elif a.what == "planned-output":
                r = C.set_planned_output(a.ws, a.case, a.sku, a.cap_soft, a.node, a.from_week, a.to_week)
            elif a.what == "capacity":
                r = C.set_capacity(a.ws, a.case, a.sku, a.max_supply, a.cap_soft, a.node)
            elif a.what == "policy":
                r = C.set_policy(a.ws, a.case, none=a.none, allocation_file=a.allocation_file,
                                 policy_file=a.policy_file, week_rule=a.week_rule,
                                 knowledge_file=a.knowledge_file, unallocated_note=a.unallocated_note)
            elif a.what == "fixed-cost":
                if a.clear:
                    r = C.set_fixed_cost(a.ws, a.case, clear=True)
                elif a.file:
                    r = C.set_fixed_cost(a.ws, a.case, file=a.file, side=a.side)
                else:
                    row = {"cost_item": a.cost_item, "entity": a.entity, "paid_start_week": a.paid_start,
                           "paid_end_week": a.paid_end, "weekly_amount": a.weekly_amount or "",
                           "currency": a.currency, "note": a.note or ""}
                    r = C.set_fixed_cost(a.ws, a.case, rows=[row])
            print(f"[cockpit_cases] {a.case} {a.what}: {json.dumps(r, ensure_ascii=False)}")
            print(f"[cockpit_cases] {a.case} の状態：{C.status(a.ws, a.case)['state']}")
        elif a.cmd == "run":
            bad = 0
            for cid in a.case:
                rec = R.run_case(a.ws, cid, on_progress=_print_progress)
                tot = sum(s["seconds"] or 0 for s in rec["stages"])
                print(f"[cockpit_cases] {cid}：{rec['state']}（{tot:.1f} 秒）"
                      + (f"  P0 {rec['summary']['P0_report']:,.0f}" if rec.get("summary") else ""))
                if rec["state"] != C.ST_DONE:
                    print(f"  {rec['reason']}：{rec['message']}")
                    bad += 1
            return 3 if bad else 0
        elif a.cmd == "compare":
            rec = R.compare_cases(a.ws, a.base, a.alt)
            print(f"[cockpit_cases] {a.base} → {a.alt}：ΔP0 {rec['delta_P0']:,.0f}")
            for r in rec["fixed_cost"]:
                print(f"  {r.get('cost_item') or '(固定費の表なし)'}：ΔW {r.get('delta_W')}  {r.get('boundary')}  "
                      f"f* {r.get('f_star_per_week')}")
            print(f"  -> {os.path.join(a.ws, 'compare', f'{a.base}__{a.alt}')}")
        elif a.cmd == "list":
            rows = C.list_cases(a.ws)
            if a.json:
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            else:
                print(C.format_list(rows))
        elif a.cmd == "status":
            print(json.dumps(C.status(a.ws, a.case), ensure_ascii=False, indent=2))
    except C.CaseError as e:
        print(f"[cockpit_cases] 止めました: {e}", file=sys.stderr)
        return 2
    except R.StageStop as e:
        print(f"[cockpit_cases] {e.state}: {e.message}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
