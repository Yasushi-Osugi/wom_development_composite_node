#!/bin/bash
# 段 4 A1：醤油の作業（output/cockpit_step4/soy）。S01 = C01、S02 = C02
set -e
PY=/c/Users/ohsug/anaconda3/python.exe
export PYTHONIOENCODING=utf-8
W=output/cockpit_step4/soy
$PY -m tools.cockpit_cases new --ws $W --model output/cockpit_step4/soy_model --max-age-weeks 130 --name "S01 基準（瓶詰 800）"
$PY -m tools.cockpit_cases copy --ws $W --from C01 --name "S02 瓶詰 900"
$PY -m tools.cockpit_cases set --ws $W --case C02 planned-output --sku Soy_Sauce --node Bottling_Noda --cap-soft 900
$PY -m tools.cockpit_cases run --ws $W --case C01 C02
$PY -m tools.cockpit_cases list --ws $W
