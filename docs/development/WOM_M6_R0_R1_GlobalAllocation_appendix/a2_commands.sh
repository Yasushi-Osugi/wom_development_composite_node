#!/bin/bash
# 到達点 6：C03 = R1（同順位・proportional_even）、C04 = R1b-1（earliest_first）、C05 = R1b-2（proportional_early_tie）
set -e
PY=/c/Users/ohsug/anaconda3/python.exe
export PYTHONIOENCODING=utf-8
W=output/cockpit_m6/soy
Q=output/cockpit_m6/allocation_qty_R1_equal.csv
$PY -m tools.cockpit_cases compare --ws $W --base C01 --alt C02
$PY -m tools.cockpit_cases copy --ws $W --from C02 --name "R1 同順位・proportional_even"
$PY -m tools.cockpit_cases set --ws $W --case C03 policy --allocation-file $Q --week-rule proportional_even
$PY -m tools.cockpit_cases copy --ws $W --from C03 --name "R1b-1 earliest_first"
$PY -m tools.cockpit_cases set --ws $W --case C04 policy --allocation-file $Q --week-rule earliest_first
$PY -m tools.cockpit_cases copy --ws $W --from C03 --name "R1b-2 proportional_early_tie"
$PY -m tools.cockpit_cases set --ws $W --case C05 policy --allocation-file $Q --week-rule proportional_early_tie
$PY -m tools.cockpit_cases run --ws $W --case C03 C04 C05
for p in "C02 C03" "C03 C04" "C03 C05"; do set -- $p; $PY -m tools.cockpit_cases compare --ws $W --base $1 --alt $2; done
$PY -m tools.cockpit_cases list --ws $W
