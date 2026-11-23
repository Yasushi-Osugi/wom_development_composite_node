set -e
PY=/c/Users/ohsug/anaconda3/python.exe; W=output/strategy_slice2/ws; M=data/sample/cosmetics-sg-th-2027-2029; S=tests/data/strategy_slice1
$PY -X utf8 -m tools.cockpit_cases new  --ws $W --model $M --max-age-weeks 52 --name P_BASE_SHORT
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C01 capacity --sku COS_Serum --max-supply 17 --cap-soft 14
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C01 capacity --sku COS_Cream --max-supply 13 --cap-soft 11
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name P_PROMO_LOW_SHORT
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name P_PROMO_MID_SHORT
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name P_PROMO_HIGH_SHORT
$PY -X utf8 -m tools.strategy_convert --ws $W --case C01 --plan P_BASE       --sheets $S --base-model $M
$PY -X utf8 -m tools.strategy_convert --ws $W --case C02 --plan P_PROMO_LOW  --sheets $S --base-model $M
$PY -X utf8 -m tools.strategy_convert --ws $W --case C03 --plan P_PROMO_MID  --sheets $S --base-model $M
$PY -X utf8 -m tools.strategy_convert --ws $W --case C04 --plan P_PROMO_HIGH --sheets $S --base-model $M
$PY -X utf8 -m tools.cockpit_cases run --ws $W --case C01 C02 C03 C04
