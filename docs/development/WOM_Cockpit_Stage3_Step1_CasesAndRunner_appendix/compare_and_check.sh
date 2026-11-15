#!/bin/bash
# 5 つの組を並べ、§1 と照合し、「入力が変わった」と開き直しを確かめる（コマンドだけ）
set -e
export PYTHONIOENCODING=utf-8
PY=/c/Users/ohsug/anaconda3/python.exe
WS=output/cockpit_cases/stage1
cc() { echo "\$ python -m tools.cockpit_cases $*"; "$PY" -m tools.cockpit_cases "$@"; }

cc compare --ws $WS --base C01 --alt C02     # 基準 後期 → 早期
cc compare --ws $WS --base C03 --alt C04     # 方針ありの後期 → 早期（C1）
cc compare --ws $WS --base C05 --alt C06     # 生産量を上げるの後期 → 早期（C2）
cc compare --ws $WS --base C01 --alt C05     # 基準・後期 → 生産量を上げる・後期（C3）
cc compare --ws $WS --base C02 --alt C04     # 基準・早期 → 方針あり・早期（C4）
cc list --ws $WS

# S3: 済みの案の入力を 1 つ変える → 入力が変わった、戻す → 済み
cc set --ws $WS --case C05 planned-output --sku COS_Cream --cap-soft 11
cc status --ws $WS --case C05
cc list --ws $WS
cc set --ws $WS --case C05 planned-output --sku COS_Cream --cap-soft 12
cc status --ws $WS --case C05

# S3: 作業ごと別の場所に写して list
rm -rf output/cockpit_cases/stage1_moved
cp -r $WS output/cockpit_cases/stage1_moved
"$PY" -m tools.cockpit_cases list --ws $WS > output/cockpit_cases/list_original.txt
"$PY" -m tools.cockpit_cases list --ws output/cockpit_cases/stage1_moved > output/cockpit_cases/list_moved.txt
diff output/cockpit_cases/list_original.txt output/cockpit_cases/list_moved.txt && echo "list: same table after moving the workspace"
