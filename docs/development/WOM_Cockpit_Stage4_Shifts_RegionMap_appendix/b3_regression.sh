#!/bin/bash
# 段 4（シフト・地域）B3：化粧品の回帰。段 1 の 6 案と前回の 88 週の案を新しい道具で実行し直し、並べ直す
PY=/c/Users/ohsug/anaconda3/python.exe
export PYTHONIOENCODING=utf-8
for W in output/cockpit_step4b/cos_stage1 output/cockpit_step4b/cos88; do
  cases=$(ls -d $W/C0* | xargs -n1 basename | tr '\n' ' ')
  $PY -m tools.cockpit_cases run --ws $W --case $cases
  for d in $(ls $W/compare); do
    $PY -m tools.cockpit_cases compare --ws $W --base ${d%__*} --alt ${d#*__}
  done
done
