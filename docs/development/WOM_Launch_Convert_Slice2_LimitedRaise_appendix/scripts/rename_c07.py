# -*- coding: utf-8 -*-
"""投入週の 2 本目の補い §1-4：C07 の案の名前だけを EARLY_RAISE167 に直す（入力・計画の結果は変えない）。"""
import os, sys
sys.path.insert(0, os.getcwd())
from wom.cockpit import cases as C
W = "output/strategy_launch1/ws"
before = C.status(W, "C07")["state"]
case = C.read_case(W, "C07")
old = case["name"]
if old != "EARLY_RAISE167":
    case["name"] = "EARLY_RAISE167"
    case.setdefault("notes", []).append({"when": C._now(), "what": "rename",
                                         "detail": f"{old} -> EARLY_RAISE167（中身は窓 2026-W37〜2029-W46 の 167 週。名前だけ直した）"})
    C.write_case(W, "C07", case)
print(old, "->", C.read_case(W, "C07")["name"], "| state", before, "->", C.status(W, "C07")["state"])
