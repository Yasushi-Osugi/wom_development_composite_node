set -e
PY=/c/Users/ohsug/anaconda3/python.exe; W=output/strategy_slice3/ws; M=data/sample/cosmetics-sg-th-2027-2029; S=tests/data/strategy_slice1; S4=output/strategy_slice4/sheets
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name PROMO25_RAISE18
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C07 planned-output --sku COS_Cream --cap-soft 12 --from-week 2028-W06 --to-week 2028-W23
$PY -X utf8 -m tools.strategy_convert --ws $W --case C07 --plan P_PROMO_MID  --sheets $S --base-model $M
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name PROMO50_RAISE24
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C08 planned-output --sku COS_Cream --cap-soft 12 --from-week 2028-W06 --to-week 2028-W29
$PY -X utf8 -m tools.strategy_convert --ws $W --case C08 --plan P_PROMO_HIGH --sheets $S --base-model $M
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C02 --name PROMO25_RAISE12_REBOUND
$PY -X utf8 -m tools.strategy_convert --ws $W --case C09 --plan P_PROMO_MID_REBOUND --sheets $S4 --base-model $M
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C02 --name N4_PROMO0_RAISE12
$PY -X utf8 -m tools.strategy_convert --ws $W --case C10 --plan P_PROMO_LOW --sheets $S --base-model $M
