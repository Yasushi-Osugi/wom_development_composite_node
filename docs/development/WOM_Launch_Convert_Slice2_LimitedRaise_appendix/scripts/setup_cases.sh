set -e
# C07: 依頼書の窓は 2026-W38 開始（166 週）。助走の行の作り直しが 2026-W37 も 12 にするため、大杉さんの判断で 2026-W37 開始（167 週）にした（報告書 §2）
PY=/c/Users/ohsug/anaconda3/python.exe; W=output/strategy_launch1/ws; M=data/sample/cosmetics-sg-th-2027-2029; S=tests/data/strategy_launch1
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name LATE_RAISE88
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C06 planned-output --sku COS_Cream --cap-soft 12 --from-week 2028-W11 --to-week 2029-W46
$PY -X utf8 output/strategy_launch2/set_raise.py C06 2028-W11 2029-W46
$PY -X utf8 -m tools.strategy_convert --ws $W --case C06 --plan P_LAUNCH_LATE --sheets $S --base-model $M
$PY -X utf8 -m tools.cockpit_cases copy --ws $W --from C01 --name EARLY_RAISE166
$PY -X utf8 -m tools.cockpit_cases set --ws $W --case C07 planned-output --sku COS_Cream --cap-soft 12 --from-week 2026-W37 --to-week 2029-W46
$PY -X utf8 output/strategy_launch2/set_raise.py C07 2026-W37 2029-W46
$PY -X utf8 -m tools.strategy_convert --ws $W --case C07 --plan P_LAUNCH_EARLY --sheets $S --base-model $M
$PY -X utf8 -m tools.cockpit_cases run --ws $W --case C06 C07
