#!/bin/bash
# 段 4 B1：化粧品の作業（output/cockpit_step4/cos）
set -e
PY=/c/Users/ohsug/anaconda3/python.exe
W=output/cockpit_step4/cos
AP=docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix/inputs/market_entry_plan_A_late.csv
$PY -m tools.cockpit_cases new --ws $W --model data/sample/cosmetics-sg-th-2027-2029 --max-age-weeks 52 --name 基準・後期
$PY -m tools.cockpit_cases set --ws $W --case C01 entry-plan --file $AP
$PY -m tools.cockpit_cases set --ws $W --case C01 capacity --sku COS_Serum --max-supply 17 --cap-soft 14
$PY -m tools.cockpit_cases set --ws $W --case C01 capacity --sku COS_Cream --max-supply 13 --cap-soft 11
$PY -m tools.cockpit_cases copy --ws $W --from C01 --name 増産・全期間
$PY -m tools.cockpit_cases set --ws $W --case C02 planned-output --sku COS_Cream --cap-soft 12
$PY -m tools.cockpit_cases copy --ws $W --from C01 --name 増産・88週
$PY -m tools.cockpit_cases set --ws $W --case C03 planned-output --sku COS_Cream --cap-soft 12 --from-week 2028-W11 --to-week 2029-W46
$PY -m tools.cockpit_cases run --ws $W --case C01 C02 C03
$PY -m tools.cockpit_cases list --ws $W
