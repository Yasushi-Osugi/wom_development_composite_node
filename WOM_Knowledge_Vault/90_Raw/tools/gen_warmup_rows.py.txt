#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/gen_warmup_rows.py — Planning Warm-up 行 materialize の薄いCLI
===================================================================
`wom.engine.warmup.materialize_warmup` を叩くだけの明示ツール。
planning 初期処理（Phase 2）が内蔵で呼ぶのと同じ関数を、手動で作り直したいとき用に提供する。

使い方（リポジトリ直下で）:
  python -m tools.gen_warmup_rows --model-dir data/sample/soysauce-jpy-2027
  python -m tools.gen_warmup_rows --model-dir <dir> --warmup-lt 26      # config を上書き
  python -m tools.gen_warmup_rows --model-dir <dir> --dry-run           # 書かずに差分有無だけ表示

冪等（何度実行しても同じ結果）・byte-stable・write-if-needed（整合なら書かない）。
設計：requests/planning-horizon-warmup-parameter-request-letter.md
"""
from __future__ import annotations

import argparse
import sys

from wom.engine.warmup import materialize_warmup, format_summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Materialize planning warm-up rows into a model's CSVs.")
    ap.add_argument("--model-dir", required=True, help="モデルフォルダ（planning_config.csv を含む）")
    ap.add_argument("--warmup-lt", type=int, default=None,
                    help="warmup_lt を明示指定（省略時は planning_config.csv を使用）")
    ap.add_argument("--planning-start", default=None,
                    help="planning_start を明示指定（週ラベル、例 2026-W28）")
    ap.add_argument("--dry-run", action="store_true", help="書き込まず差分有無だけ報告")
    a = ap.parse_args(argv)

    summary = materialize_warmup(
        a.model_dir,
        warmup_lt=a.warmup_lt,
        planning_start=a.planning_start,
        write=not a.dry_run,
    )
    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
