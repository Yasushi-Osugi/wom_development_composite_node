set -e
PY=/c/Users/ohsug/anaconda3/python.exe; W=output/strategy_slice3/ws; L=$1
$PY -X utf8 -m tools.strategy_compare --ws $W --base C01 --cases C02,C03,C04,C05,C06 --weekly 2028-W04 2028-W30 --holding-rates 0,0.10 --out output/strategy_slice3/compare_${L}_vsC01
$PY -X utf8 -m tools.strategy_compare --ws $W --base C02 --cases C04,C06 --weekly 2028-W04 2028-W30 --holding-rates 0,0.10 --out output/strategy_slice3/compare_${L}_vsC02
