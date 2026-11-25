set -e
PY=/c/Users/ohsug/anaconda3/python.exe; W=output/strategy_launch1/ws; M=data/sample/cosmetics-sg-th-2027-2029; S=tests/data/strategy_launch1
EP=docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix/inputs/market_entry_plan_A_late.csv
$PY -X utf8 -m tools.cockpit_cases new  --ws $W --model $M --max-age-weeks 52 --name BASE_C3a_ENTRYPLAN
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C01 capacity --sku COS_Serum --max-supply 17 --cap-soft 14
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C01 capacity --sku COS_Cream --max-supply 13 --cap-soft 11
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C01 entry-plan --file $EP
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name LATE
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name EARLY
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name LATE_RAISE
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C04 planned-output --sku COS_Cream --cap-soft 12
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C04 --name EARLY_RAISE
$PY -X utf8 output/strategy_launch1/set_raise.py
$PY -X utf8 -m tools.strategy_convert --ws $W --case C02 --plan P_LAUNCH_LATE  --sheets $S --base-model $M
$PY -X utf8 -m tools.strategy_convert --ws $W --case C03 --plan P_LAUNCH_EARLY --sheets $S --base-model $M
$PY -X utf8 -m tools.strategy_convert --ws $W --case C04 --plan P_LAUNCH_LATE  --sheets $S --base-model $M
$PY -X utf8 -m tools.strategy_convert --ws $W --case C05 --plan P_LAUNCH_EARLY --sheets $S --base-model $M
