set -e
PY=/c/Users/ohsug/anaconda3/python.exe; W=output/strategy_slice3/ws; L=$1; O=output/strategy_slice4b; P=output/strategy_slice4/protect_floor.csv
OPT="--holding-rates 0,0.10 --avoidable store_operating=1,0.5,0 --protect $P"
$PY -X utf8 -m tools.strategy_compare --ws $W --base C01 --cases C02,C03,C04,C05,C06,C07,C08,C09,C11,C12 $OPT --out $O/compare_${L}_vsC01
$PY -X utf8 -m tools.strategy_compare --ws $W --base C02 --cases C04,C06,C11,C12 $OPT --weekly 2028-W04 2028-W30 --out $O/compare_${L}_vsC02
$PY -X utf8 -m tools.strategy_compare --ws $W --base C11 --cases C07 $OPT --weekly 2028-W04 2028-W30 --out $O/compare_${L}_C07vsC11
$PY -X utf8 -m tools.strategy_compare --ws $W --base C12 --cases C08 $OPT --weekly 2028-W04 2028-W30 --out $O/compare_${L}_C08vsC12
