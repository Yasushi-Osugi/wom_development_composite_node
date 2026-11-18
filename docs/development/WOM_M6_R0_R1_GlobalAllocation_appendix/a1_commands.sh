#!/bin/bash
# 到達点 6：醤油の作業 output/cockpit_m6/soy。C01 = 18 シフト（S01）、C02 = R0 21 シフト（S02）
set -e
PY=/c/Users/ohsug/anaconda3/python.exe
export PYTHONIOENCODING=utf-8
W=output/cockpit_m6/soy
$PY -m tools.cockpit_cases new --ws $W --model output/cockpit_m6/soy_model --max-age-weeks 130 --name "参考 18 シフト"
$PY -m tools.cockpit_cases copy --ws $W --from C01 --name "R0 21 シフト・配分なし"
$PY -m tools.cockpit_cases set --ws $W --case C02 shifts --sku Soy_Sauce --node Bottling_Noda --shifts 21
$PY -m tools.cockpit_cases run --ws $W --case C01 C02
