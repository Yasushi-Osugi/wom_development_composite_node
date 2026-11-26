set -e
PY=/c/Users/ohsug/anaconda3/python.exe; W=output/strategy_launch1/ws; O=output/strategy_launch2
OPT="--sku COS_Cream --market TH_Distributor --weekly 2027-W25 2028-W14 --holding-rates 0,0.05,0.10,0.15 --avoidable store_operating=1,0.5,0"
$PY -X utf8 -m tools.strategy_compare --ws $W --base C04 --cases C06 $OPT --protect $O/protect_floor_C04.csv --out $O/compare_C04_C06
$PY -X utf8 -m tools.strategy_compare --ws $W --base C05 --cases C07 $OPT --protect $O/protect_floor_C05.csv --out $O/compare_C05_C07
$PY -X utf8 -m tools.strategy_compare --ws $W --base C06 --cases C07 $OPT --protect $O/protect_floor_C05.csv --out $O/compare_C06_C07
