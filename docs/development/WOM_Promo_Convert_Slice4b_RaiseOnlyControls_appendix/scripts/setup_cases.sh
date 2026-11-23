set -e
PY=/c/Users/ohsug/anaconda3/python.exe; W=output/strategy_slice3/ws
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name RAISE_ONLY18
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C11 planned-output --sku COS_Cream --cap-soft 12 --from-week 2028-W06 --to-week 2028-W23
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name RAISE_ONLY24
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C12 planned-output --sku COS_Cream --cap-soft 12 --from-week 2028-W06 --to-week 2028-W29
