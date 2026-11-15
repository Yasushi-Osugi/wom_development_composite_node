#!/bin/bash
set -e
export PYTHONIOENCODING=utf-8
PY=/c/Users/ohsug/anaconda3/python.exe
WS=output/cockpit_cases/stage1
cc() { echo "\$ python -m tools.cockpit_cases $*"; "$PY" -m tools.cockpit_cases "$@"; }


cc status --ws $WS --case C05
for p in "C01 C02" "C03 C04" "C05 C06" "C01 C05" "C02 C04" "C02 C06"; do set -- $p; cc compare --ws $WS --base $1 --alt $2; done
