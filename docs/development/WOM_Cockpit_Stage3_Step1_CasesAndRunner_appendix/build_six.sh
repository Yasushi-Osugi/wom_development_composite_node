#!/bin/bash
# 6 案を作る（コマンドだけ。ファイルを手で書き換えない）
set -e
export PYTHONIOENCODING=utf-8
PY=/c/Users/ohsug/anaconda3/python.exe
WS=output/cockpit_cases/stage1
IN=docs/development/WOM_Cockpit_FirstComparison_PolicyAndCapacity_appendix/inputs
NOTE="当該期間は供給の対象にしない予測需要（仮定、化粧品設計書 v0.5 D18）"
cc() { echo "\$ python -m tools.cockpit_cases $*"; "$PY" -m tools.cockpit_cases "$@"; }

cc new --ws $WS --model data/sample/cosmetics-sg-th-2027-2029 --max-age-weeks 52 --name "基準・後期"
cc set --ws $WS --case C01 entry-plan --file $IN/market_entry_plan_A_late.csv
cc set --ws $WS --case C01 capacity --sku COS_Serum --max-supply 17 --cap-soft 14
cc set --ws $WS --case C01 capacity --sku COS_Cream --max-supply 13 --cap-soft 11
cc set --ws $WS --case C01 fixed-cost --file $IN/fixed_cost_late_late.csv --side base

cc copy --ws $WS --from C01 --name "基準・早期"
cc set --ws $WS --case C02 launch-week --sku COS_Cream --region TH_Distributor --week 2027-W27
cc set --ws $WS --case C02 fixed-cost --file $IN/fixed_cost_late_early.csv --side alt

cc copy --ws $WS --from C01 --name "方針あり・後期"
cc set --ws $WS --case C03 policy --allocation-file $IN/allocation_qty_TH70.csv --policy-file $IN/udp_policy_MS50TH70.csv --week-rule trim_to_capacity_latest --knowledge-file $IN/knowledge.json --unallocated-note "$NOTE"

cc copy --ws $WS --from C02 --name "方針あり・早期"
cc set --ws $WS --case C04 policy --allocation-file $IN/allocation_qty_TH70_early.csv --policy-file $IN/udp_policy_MS50TH70.csv --week-rule trim_to_capacity_latest --knowledge-file $IN/knowledge.json --unallocated-note "$NOTE"

cc copy --ws $WS --from C01 --name "生産量を上げる・後期"
cc set --ws $WS --case C05 planned-output --sku COS_Cream --cap-soft 12

cc copy --ws $WS --from C02 --name "生産量を上げる・早期"
cc set --ws $WS --case C06 planned-output --sku COS_Cream --cap-soft 12

cc list --ws $WS
