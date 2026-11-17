#!/bin/bash
# 到達点 5 A1：化粧品の作業 output/cockpit_m5/cos（C01〜C07）
set -e
PY=/c/Users/ohsug/anaconda3/python.exe
export PYTHONIOENCODING=utf-8
W=output/cockpit_m5/cos
AP=docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix/inputs/market_entry_plan_A_late.csv
NOTE="発売直後の需要が想定より強い場合（立ち上がりの倍率 0.5→1.0）。到達点 5 の試行の仮説"
cc() { $PY -m tools.cockpit_cases "$@"; }
cc new --ws $W --model data/sample/cosmetics-sg-th-2027-2029 --max-age-weeks 52 --name 基準・後期
cc set --ws $W --case C01 entry-plan --file $AP
cc set --ws $W --case C01 capacity --sku COS_Serum --max-supply 17 --cap-soft 14
cc set --ws $W --case C01 capacity --sku COS_Cream --max-supply 13 --cap-soft 11
cc copy --ws $W --from C01 --name 増産・全期間
cc set --ws $W --case C02 planned-output --sku COS_Cream --cap-soft 12
cc copy --ws $W --from C01 --name 増産・88週
cc set --ws $W --case C03 planned-output --sku COS_Cream --cap-soft 12 --from-week 2028-W11 --to-week 2029-W46
$PY output/cockpit_m5/a1_raise.py helper
cc copy --ws $W --from C01 --name "基準＋強い立ち上がり"
cc set --ws $W --case C04 demand-hypothesis --sku COS_Cream --region TH_Distributor --ramp-ratio 1.0 --basis-note "$NOTE"
cc copy --ws $W --from C03 --name "88週＋強い立ち上がり"
cc set --ws $W --case C05 demand-hypothesis --sku COS_Cream --region TH_Distributor --ramp-ratio 1.0 --basis-note "$NOTE"
cc copy --ws $W --from C02 --name "全期間＋強い立ち上がり"
cc set --ws $W --case C06 demand-hypothesis --sku COS_Cream --region TH_Distributor --ramp-ratio 1.0 --basis-note "$NOTE"
cc copy --ws $W --from C05 --name "101週＋強い立ち上がり"
cc set --ws $W --case C07 planned-output --sku COS_Cream --cap-soft 12 --from-week 2027-W50 --to-week 2029-W46
$PY output/cockpit_m5/a1_raise.py c07
cc run --ws $W --case C01 C02 C03 C04 C05 C06 C07
for p in "C01 C02" "C01 C03" "C01 C04" "C03 C05" "C02 C06" "C05 C07"; do set -- $p; cc compare --ws $W --base $1 --alt $2; done
cc list --ws $W
