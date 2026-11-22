# -*- coding: utf-8 -*-
"""段 3 S2：段 1 の醤油 T1（C02、tail）を、overflow_policy,tail を明示した写しで回し直し、段 1 の結果と比べる。
もう 1 回、キーなし（新しい既定）でも回し、段 1 の T2（proportional_week）と比べる。

    python output/roworder_stage3/scripts/soy_t1_tail.py
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "roworder_stage2", "scripts"))
import common as CM  # noqa: E402
from golden_sweep3 import write_policy  # noqa: E402

S1 = os.path.join(CM.REPO, "output", "roworder_stage1", "soy")
OUT = os.path.join(CM.REPO, "output", "roworder_stage3", "soy_t1")
SUB = "Σ"


def rows(market):
    if isinstance(market, dict):   # 段 1 の result.json：{leaf: {...}}
        return sorted((leaf, r["demand"], r["on_time"], r["early"], r["late"], r["backlog_end"])
                      for leaf, r in market.items() if leaf and not leaf.startswith(SUB))
    return sorted((r["leaf"], r["demand"], r["on_time"], r["early"], r["late"], r["backlog_end"])
                  for r in market if r["leaf"] and not str(r["leaf"]).startswith(SUB))


def one(tag, policy, ref):
    mdir = os.path.join(OUT, tag, "model")
    if not os.path.exists(mdir):
        shutil.copytree(os.path.join(S1, "T1", "model"), mdir)
    write_policy(mdir, policy)
    res = CM.capture(mdir, os.path.join(OUT, tag, "run"))
    old = json.load(open(os.path.join(S1, ref, "result.json"), encoding="utf-8"))
    same_market = rows(res["market"]) == rows(old["market"])
    old_pd = old["past_due"] if isinstance(old["past_due"], int) else old.get("past_due")
    out = {"tag": tag, "policy_written": policy, "engine_policy": res["policy"], "ref": ref,
           "same_market": same_market, "market_rows": rows(res["market"]),
           "burden": res["burden"], "burden_stage1": old["burden"], "past_due_total": res["past_due_total"],
           "past_due_stage1": old_pd}
    CM.save(out, os.path.join(OUT, f"{tag}.json"))
    print(f"[{tag}] policy={res['policy']} vs stage1 {ref}: same_market={same_market}", flush=True)
    return out


if __name__ == "__main__":
    one("T1_tail_explicit", "tail", "T1")
    one("T1_default", None, "T2")
