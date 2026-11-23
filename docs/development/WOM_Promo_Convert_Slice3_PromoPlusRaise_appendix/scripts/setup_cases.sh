set -e
PY=/c/Users/ohsug/anaconda3/python.exe; W=output/strategy_slice3/ws; M=data/sample/cosmetics-sg-th-2027-2029; S=tests/data/strategy_slice1
$PY -X utf8 -m tools.cockpit_cases new  --ws $W --model $M --max-age-weeks 52 --name BASE_SHORT
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C01 capacity --sku COS_Serum --max-supply 17 --cap-soft 14
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C01 capacity --sku COS_Cream --max-supply 13 --cap-soft 11
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name RAISE_ONLY
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C02 planned-output --sku COS_Cream --cap-soft 12 --from-week 2028-W06 --to-week 2028-W17
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name PROMO25
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C02 --name PROMO25_RAISE
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name PROMO50
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C02 --name PROMO50_RAISE
$PY -X utf8 -m tools.strategy_convert --ws $W --case C01 --plan P_BASE       --sheets $S --base-model $M
$PY -X utf8 -m tools.strategy_convert --ws $W --case C03 --plan P_PROMO_MID  --sheets $S --base-model $M
$PY -X utf8 -m tools.strategy_convert --ws $W --case C04 --plan P_PROMO_MID  --sheets $S --base-model $M
$PY -X utf8 -m tools.strategy_convert --ws $W --case C05 --plan P_PROMO_HIGH --sheets $S --base-model $M
$PY -X utf8 -m tools.strategy_convert --ws $W --case C06 --plan P_PROMO_HIGH --sheets $S --base-model $M
