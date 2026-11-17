#!/bin/bash
# 段 4（シフト・地域）B1：醤油の作業 output/cockpit_step4b/soy。S01 = C01、S02 = C02
set -e
PY=/c/Users/ohsug/anaconda3/python.exe
export PYTHONIOENCODING=utf-8
W=output/cockpit_step4b/soy
$PY -m tools.cockpit_cases new --ws $W --model output/cockpit_step4b/soy_model --max-age-weeks 130 --name "S01 基準（18 シフト）"
$PY -m tools.cockpit_cases copy --ws $W --from C01 --name "S02 シフトを増やす（21 シフト）"
$PY -m tools.cockpit_cases set --ws $W --case C02 shifts --sku Soy_Sauce --node Bottling_Noda --shifts 21
$PY -m tools.cockpit_cases run --ws $W --case C01 C02
$PY -m tools.cockpit_cases compare --ws $W --base C01 --alt C02
$PY -m tools.cockpit_cases list --ws $W
