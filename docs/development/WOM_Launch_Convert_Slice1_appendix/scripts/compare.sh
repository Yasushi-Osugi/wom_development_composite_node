set -e
PY=/c/Users/ohsug/anaconda3/python.exe; W=output/strategy_launch1/ws; O=output/strategy_launch1
OPT="--sku COS_Cream --market TH_Distributor --weekly 2027-W25 2028-W14 --holding-rates 0,0.05,0.10,0.15 --avoidable store_operating=1,0.5,0"
$PY -X utf8 -m tools.strategy_compare --ws $W --base C02 --cases C03 $OPT --protect $O/protect_floor_C02.csv --out $O/compare_C02_C03
$PY -X utf8 -m tools.strategy_compare --ws $W --base C04 --cases C05 $OPT --protect $O/protect_floor_C04.csv --out $O/compare_C04_C05
$PY -X utf8 -m tools.strategy_compare --ws $W --base C02 --cases C04 $OPT --protect $O/protect_floor_C02.csv --out $O/compare_C02_C04
